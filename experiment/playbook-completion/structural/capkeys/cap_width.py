#!/usr/bin/env python3
"""§3.6 capacity, key widths: every writer of a node/edge at and one past the widest key it accepts (AUDITD, live).

    locks.sh iris python cap_width.py OUT.json

For each writer W (module in brackets) and graph-name length G in {0, 100}, the widest edge W accepts is found by
bisection over s = o = n characters, p = n // 2 (each attempt from an empty namespace). At the widest accepted width
and one past it the outcome is classified with independent oracles:
  - rows (SQL), adjacency ^KG("out"/"in", G, ...) and label index ^KG("label", G, label, s) per row (Native API
    $Data; a reference IRIS cannot form is reported as SUBSCRIPT), the temporal read for temporal writers, the
    product's own get_node read-back, and the journal (net effect of the attempt in AUDITD's database).
  - ok: success answer and every row has its adjacency/label/temporal entries;
    silent-loss: success answer but a store lacks an entry (or a row is missing);
    clean-refusal: error or False answer and the journal shows no net change;
    partial: error or False answer and a net change remains.
Then a cross-writer phase: the widest row the most permissive writer accepted is put through the other modules'
readers/derivers (sync, rebuild_kg, verify_graph, Cypher MATCH, save_snapshot/restore_snapshot, erase_graph).
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
import lib  # noqa: E402
from lib import J  # noqa: E402

TS = 1_700_000_000


def names(n, G, tag):
    g = ("g" * (G - 1) + tag) if G else None
    return "s" * (n - 1) + tag, "p" * (max(n // 2, 1) - 1) + tag, "o" * (n - 1) + tag, g


def kg_defined(c, *subs):
    try:
        return bool(int(c.o.isDefined("^KG", *subs)))
    except Exception as ex:  # noqa: BLE001
        return "SUBSCRIPT" if "SUBSCRIPT" in str(ex).upper() else f"<{type(ex).__name__}>"


def gkey(g):
    return 0 if not g else g


def state_check(c, eng, expect_edge, ts=None):
    """Oracle: rows vs adjacency/label index; product read-back."""
    rows = {"nodes": c.sql("SELECT node_id, graph_id FROM Graph_KG.nodes"),
            "edges": c.sql("SELECT s, p, o_id, graph_id FROM Graph_KG.rdf_edges"),
            "labels": c.sql("SELECT s, label, graph_id FROM Graph_KG.rdf_labels")}
    problems = []
    for s, p, o, g in rows["edges"]:
        g = "" if g in (None, "\x00") else str(g)
        for d, a, b in (("out", s, o), ("in", o, s)):
            v = kg_defined(c, d, gkey(g), a, p, b)
            if v is not True:
                problems.append({"edge_row": [len(s), len(p), len(o), len(g)], "adjacency": d, "defined": v})
    for s, label, g in rows["labels"]:
        g = "" if g in (None, "\x00") else str(g)
        v = kg_defined(c, "label", gkey(g), label, s)
        if v is not True:
            problems.append({"label_row": [len(s), label, len(g)], "label_index": v})
    if expect_edge:
        s, p, o, g = expect_edge
        if not any(r[0] == s and r[1] == p and r[2] == o and (r[3] or "") == (g or "") for r in rows["edges"]):
            problems.append({"missing_edge_row": [len(s), len(p), len(o), len(g or "")]})
        if ts is not None:
            try:
                w = eng.get_edges_in_window(source=s, predicate=p, start=ts - 1, end=ts + 1, graph=g)
                if not any(e.get("o") == o for e in w):
                    problems.append({"temporal_read_missing": True, "window": len(w)})
            except Exception as ex:  # noqa: BLE001
                problems.append({"temporal_read_error": f"{type(ex).__name__}: {str(ex)[:160]}"})
        for nid in (s, o):
            try:
                if eng.get_node(nid, graph=g) is None:
                    problems.append({"get_node_none": len(nid)})
            except Exception as ex:  # noqa: BLE001
                problems.append({"get_node_error": f"{type(ex).__name__}: {str(ex)[:160]}"})
    return {"counts": {k: len(v) for k, v in rows.items()}, "problems": problems}


# --------------------------------------------------------------------------------------------- writers
# Each writer is a list of steps; every step is journal-captured on its own, so a failing step's own net effect
# (what it left behind) is told apart from rows earlier, successful steps wrote.

def w_create(c, eng, s, p, o, g):
    return [("create_node_s", lambda: eng.create_node(s, labels=["L"], graph=g)),
            ("create_node_o", lambda: eng.create_node(o, labels=["L"], graph=g)),
            ("create_edge", lambda: eng.create_edge(s, p, o, graph=g))]


def w_bulk(c, eng, s, p, o, g):
    return [("bulk_create_nodes", lambda: len(eng.bulk_create_nodes([{"id": s, "labels": ["L"]}, {"id": o, "labels": ["L"]}], graph=g)) == 2),
            ("bulk_create_edges", lambda: eng.bulk_create_edges([{"source_id": s, "predicate": p, "target_id": o}], graph=g) == 1)]


def w_temporal(c, eng, s, p, o, g):
    return [("create_node_s", lambda: eng.create_node(s, labels=["L"], graph=g)),
            ("create_node_o", lambda: eng.create_node(o, labels=["L"], graph=g)),
            ("create_edge_temporal", lambda: eng.create_edge_temporal(s, p, o, timestamp=TS, graph=g))]


def w_cypher(c, eng, s, p, o, g):
    use = f"USE GRAPH '{g}' " if g else ""

    def f():
        r = eng.execute_cypher(use + "CREATE (a:L {id: $s})-[:" + p + "]->(b:L {id: $o})", {"s": s, "o": o})
        if r.error:
            raise RuntimeError(str(r.error)[:400])
        return True
    return [("execute_cypher CREATE", f)]


def w_store(c, eng, s, p, o, g):
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    st = IRISGraphStore(c.conn, namespace=lib.NS)

    def f(call):
        r = call()
        if r.error:
            raise RuntimeError(str(r.error)[:400])
        return True
    return [("write_nodes", lambda: f(lambda: st.write_nodes([{"id": s, "labels": ["L"], "properties": {}},
                                                                {"id": o, "labels": ["L"], "properties": {}}]))),
            ("write_edges", lambda: f(lambda: st.write_edges([{"source": s, "predicate": p, "target": o}])))]


def w_node_create(c, eng, s, p, o, g):
    return [("create_node", lambda: eng.create_node(s, labels=["L"], properties={"k": "v"}, graph=g))]


def w_node_bulk(c, eng, s, p, o, g):
    return [("bulk_create_nodes", lambda: len(eng.bulk_create_nodes([{"id": s, "labels": ["L"], "properties": {"k": "v"}}], graph=g)) == 1)]


WRITERS = {"03:create_node+create_edge": w_create, "03/04:bulk_create_nodes+bulk_create_edges": w_bulk,
           "05:create_edge_temporal": w_temporal, "08:cypher CREATE": w_cypher, "17:IRISGraphStore.write_nodes+write_edges": w_store}
NODE_WRITERS = {"03:create_node(node only)": w_node_create, "03:bulk_create_nodes(node only)": w_node_bulk}


def is_counter(node):
    """Non-transactional counters IRIS keeps outside the transaction: a data global's row-id counter (the root node,
    no subscripts) and IVG's version stamps (^KG("__version"), ^NKG("$meta", ...))."""
    if "(" not in node:
        return True
    return node.startswith(('^KG("__version"', '^NKG("$meta"'))


def attempt(wname, n, G, writers=None):
    writers = writers or WRITERS
    c = lib.conn()
    try:
        lib.reset(c)
        eng = lib.engine(c)
        s, p, o, g = names(n, G, "x")
        if writers is NODE_WRITERS:
            s = "s" * (n - 1) + "x"
        t0 = time.time()
        steps = []
        ok, err, failing_net = True, None, []
        for label, f in writers[wname](c, eng, s, p, o, g):
            m = J.mark()
            try:
                a = f()
                e = None if a else f"{label} answered {a!r}"
            except Exception as ex:  # noqa: BLE001
                e = f"{label}: {type(ex).__name__}: {str(ex)[:300]}"
                try:
                    c.conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
            try:
                c.conn.commit()
            except Exception:  # noqa: BLE001
                pass
            net = J.net_effect(J.records_since(m, dbs={lib.DB}))
            residue = sorted(x for x in net if not is_counter(x))
            steps.append({"step": label, "error": e, "net_nodes": len(net), "residue": [x[:160] for x in residue[:12]],
                          "residue_count": len(residue)})
            if e:
                ok, err, failing_net = False, e, residue
                break
        edge = None if writers is NODE_WRITERS else (s, p, o, g)
        chk = state_check(c, eng, edge if ok else None, TS if (ok and wname.startswith("05")) else None)
        if ok and writers is NODE_WRITERS:
            try:
                if eng.get_node(s, graph=g) is None:
                    chk["problems"].append({"get_node_none": len(s)})
            except Exception as ex:  # noqa: BLE001
                chk["problems"].append({"get_node_error": str(ex)[:160]})
        if ok:
            outcome = "ok" if not chk["problems"] else "silent-loss"
        else:
            outcome = "clean-refusal" if not failing_net else "partial"
        return {"writer": wname, "n": n, "p": len(p), "G": G, "outcome": outcome, "error": err, "steps": steps,
                "check": chk, "secs": round(time.time() - t0, 2)}
    finally:
        c.close()


def widest(wname, G, lo=8, hi=256, writers=None):
    log = []
    while lo < hi:
        mid = (lo + hi + 1) // 2
        r = attempt(wname, mid, G, writers)
        log.append([mid, r["outcome"]])
        lo, hi = (mid, hi) if r["outcome"] == "ok" else (lo, mid - 1)
    return lo, log


def cross(n, G):
    """The widest edge (as the bulk writer stores it) through other modules' readers and derivers."""
    out = {}
    c = lib.conn()
    try:
        lib.reset(c)
        eng = lib.engine(c)
        s, p, o, g = names(n, G, "x")
        ok = all(f() for _, f in w_bulk(c, eng, s, p, o, g))
        c.conn.commit()
        out["write"] = {"ok": ok, "check": state_check(c, eng, (s, p, o, g))}
        for name, f in (("sync", lambda: eng.sync()), ("rebuild_kg", lambda: eng.rebuild_kg()),
                        ("verify_graph", lambda: eng.verify_graph(graph=g)),
                        ("cypher_match", lambda: (eng.execute_cypher((f"USE GRAPH '{g}' " if g else "") +
                                                                     "MATCH (a {id: $s})-[r]->(b) RETURN b.id AS b",
                                                                     {"s": s}).rows))):
            try:
                v = f()
                c.conn.commit()
                out[name] = {"result": str(v)[:400], "check": state_check(c, eng, (s, p, o, g))}
            except Exception as ex:  # noqa: BLE001
                out[name] = {"error": f"{type(ex).__name__}: {str(ex)[:300]}"}
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "snap.zip")
            try:
                out["save_snapshot"] = str(eng.save_snapshot(path))[:400]
                lib.reset(c)
                out["restore_snapshot"] = str(eng.restore_snapshot(path))[:600]
                c.conn.commit()
                out["after_restore"] = state_check(c, eng, (s, p, o, g))
            except Exception as ex:  # noqa: BLE001
                out["snapshot_error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
        try:
            out["erase_graph"] = str(eng.erase_graph(g))
            c.conn.commit()
            out["after_erase"] = state_check(c, eng, None)
            out["after_erase_kg_out"] = kg_defined(c, "out", gkey(g))
        except Exception as ex:  # noqa: BLE001
            out["erase_error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
    finally:
        lib.reset(c)
        c.close()
    return out


def main() -> int:
    outp = Path(sys.argv[1])
    res = {"engine": None, "writers": {}, "cross": {}}
    c = lib.conn()
    res["engine"] = lib.version(c)
    c.close()
    for G in (0, 100):
        for w in WRITERS:
            if G and w.startswith("17:"):
                continue
            t0 = time.time()
            try:
                lo, log = widest(w, G)
                at = attempt(w, lo, G)
                past = attempt(w, lo + 1, G)
                res["writers"][f"{w}|G={G}"] = {"widest_ok_n": lo, "bisection": log, "at_widest": at, "one_past": past}
                print(json.dumps({"writer": w, "G": G, "widest": lo, "at": at["outcome"], "past": past["outcome"],
                                  "past_err": (past["error"] or "")[:120], "past_problems": past["check"]["problems"][:2],
                                  "secs": round(time.time() - t0, 1)}, default=str), flush=True)
            except Exception:  # noqa: BLE001
                res["writers"][f"{w}|G={G}"] = {"harness_error": traceback.format_exc()[-1500:]}
                print("HARNESS ERROR", w, G, traceback.format_exc()[-600:], flush=True)
            lib.dump(outp, res)
    for G in (0, 100, 256):
        for w in NODE_WRITERS:
            try:
                lo, log = widest(w, G, writers=NODE_WRITERS)
                at = attempt(w, lo, G, NODE_WRITERS)
                past = attempt(w, lo + 1, G, NODE_WRITERS) if lo < 256 else None
                res["writers"][f"{w}|G={G}"] = {"widest_ok_n": lo, "bisection": log, "at_widest": at, "one_past": past}
                print(json.dumps({"writer": w, "G": G, "widest": lo, "at": at["outcome"],
                                  "past": past and past["outcome"], "past_err": past and (past["error"] or "")[:160]}), flush=True)
            except Exception:  # noqa: BLE001
                res["writers"][f"{w}|G={G}"] = {"harness_error": traceback.format_exc()[-1500:]}
            lib.dump(outp, res)
    for G in (0, 100):
        ws = [v.get("widest_ok_n", 0) for k, v in res["writers"].items() if k.endswith(f"G={G}") and "widest_ok_n" in v
              and "node only" not in k]
        n = max(ws) if ws else 64
        res["cross"][f"G={G}"] = cross(n, G)
        print(json.dumps({"cross": G, "n": n, "summary": {k: (str(v)[:200]) for k, v in res["cross"][f"G={G}"].items()}},
                         default=str)[:2500], flush=True)
        lib.dump(outp, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
