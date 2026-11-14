#!/usr/bin/env python3
"""§3.6 capacity, value sizes: each module's writers at and past the column widths and IRIS's long-string limit
(3,641,144 characters), with an exact read-back oracle (AUDITD, live).

    locks.sh iris python cap_values.py OUT.json [case-prefix ...]

Each case starts from an empty namespace, runs one write through the product's public API and reads the value back
through the product's own reader (and SQL where the reader is not the store). The journal (net effect in AUDITD's
database during the write) tells a clean refusal from a partial write.
Outcomes: exact (accepted, read back equal), silent-truncation / silent-change (accepted, read back different or
missing), clean-refusal (error or False, no net change), partial (error or False, a net change remains),
reader-failure (accepted, the module's own reader raises).
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))
import lib  # noqa: E402
from lib import J  # noqa: E402

MAXSTR = 3_641_144
TS = 1_700_000_000


def h(v):
    if v is None:
        return None
    s = v if isinstance(v, str) else json.dumps(v, sort_keys=True, default=str)
    return {"len": len(s), "sha": hashlib.sha256(s.encode("utf-8", "surrogatepass")).hexdigest()[:16]}


BENIGN = ('^KG("__version"', '^NKG("$meta"', '^KG("gen"', '^t52S.DMCe.7("W"')


def benign(node):
    """Nodes IRIS or IVG change outside the transaction on purpose: a data global's row-id counter (no subscripts),
    IVG's version and generation stamps, and the iFind word dictionary of rdf_props (index 7, ("W", id))."""
    return "(" not in node or node.startswith(BENIGN)


def classify(err, residue, rb, rerr, expect):
    if err is None:
        if rerr:
            return "reader-failure"
        if rb == expect:
            return "exact"
        if rb is None:
            return "silent-loss"
        if isinstance(rb, str) and isinstance(expect, str) and expect.startswith(rb):
            return "silent-truncation"
        return "silent-change"
    return "clean-refusal" if not residue else "partial"


def run_case(name, module, write, read, expect, note="", setup=None):
    c = lib.conn()
    t0 = time.time()
    try:
        lib.reset(c)
        eng = lib.engine(c)
        if setup:
            setup(c, eng)
            c.conn.commit()
        m = J.mark()
        try:
            ans = write(c, eng)
            err = None
            if ans is False or (hasattr(ans, "error") and getattr(ans, "error", None)):
                err = f"answer {getattr(ans, 'error', ans)!s:.300}"
        except Exception as ex:  # noqa: BLE001
            ans, err = None, f"{type(ex).__name__}: {str(ex)[:400]}"
            try:
                c.conn.rollback()
            except Exception:  # noqa: BLE001
                pass
        try:
            c.conn.commit()
        except Exception:  # noqa: BLE001
            pass
        recs = J.records_since(m, dbs={lib.DB})
        net = J.net_effect(recs)
        residue = sorted(x for x in net if not benign(x))
        roots = sorted({J.global_root(x) for x in residue})
        rb, rerr = None, None
        try:
            rb = read(c, eng)
        except Exception as ex:  # noqa: BLE001
            rerr = f"{type(ex).__name__}: {str(ex)[:400]}"
        outcome = classify(err, residue, rb, rerr, expect)
        r = {"case": name, "module": module, "note": note, "outcome": outcome, "write_error": err,
             "read_error": rerr, "expected": h(expect), "read_back": h(rb) if not isinstance(rb, (int, float, bool)) else rb,
             "net_nodes": len(net), "residue_roots": roots, "residue": [x[:140] for x in residue[:10]],
             "secs": round(time.time() - t0, 2)}
    except Exception:  # noqa: BLE001
        r = {"case": name, "module": module, "outcome": "harness-error", "trace": traceback.format_exc()[-1500:]}
    finally:
        try:
            lib.reset(c)
        except Exception:  # noqa: BLE001
            pass
        c.close()
    print(json.dumps(r, default=str)[:700], flush=True)
    return r


# ------------------------------------------------------------------------------------------------ readers

def node_prop(nid, key, graph=None):
    def f(c, eng):
        n = eng.get_node(nid, graph=graph)
        if n is None:
            return None
        props = n.get("properties", n)
        v = props.get(key) if isinstance(props, dict) else None
        return v
    return f


def sql_prop(nid, key, graph=""):
    def f(c, eng):
        r = c.sql('SELECT val FROM Graph_KG.rdf_props WHERE s = ? AND "key" = ? AND graph_id = ?', nid, key, graph)
        return str(r[0][0]) if r and r[0][0] is not None else None
    return f


def node_labels(nid, graph=None):
    def f(c, eng):
        n = eng.get_node(nid, graph=graph)
        return None if n is None else sorted(n.get("labels") or [])
    return f


def cypher_val(q, params, col):
    def f(c, eng):
        r = eng.execute_cypher(q, params)
        if r.error:
            raise RuntimeError(r.error)
        if not r.rows:
            return None
        row = r.rows[0]
        if isinstance(row, dict):
            return row.get(col)
        return row[r.columns.index(col)] if col in r.columns else row[0]
    return f


def edge_qual(s, p, o, key):
    def f(c, eng):
        r = eng.execute_cypher("MATCH (a {id: $s})-[r]->(b {id: $o}) RETURN r." + key + " AS v", {"s": s, "o": o})
        if r.error:
            raise RuntimeError(r.error)
        if not r.rows:
            return None
        row = r.rows[0]
        return row.get("v") if isinstance(row, dict) else row[0]
    return f


def sql_qual(s, key):
    def f(c, eng):
        r = c.sql("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ?", s)
        if not r or r[0][0] in (None, ""):
            return None
        return json.loads(str(r[0][0])).get(key)
    return f


def big(n, ch="v"):
    return ch * n


def cases():
    out = []
    # ---- 03 direct writes: property value, label, key widths
    for n, note in ((64_000, "rdf_props.val VARCHAR(64000)"), (64_001, "one past the column"),
                    (1_000_000, "~1 MB"), (MAXSTR, "IRIS long-string limit")):
        v = big(n)
        out.append((f"03-create_node-prop-{n}", "03",
                    lambda c, e, v=v: e.create_node("cv:1", labels=["L"], properties={"v": v}),
                    node_prop("cv:1", "v"), v, note))
    out.append(("03-create_node-label-128", "03", lambda c, e: e.create_node("cv:1", labels=["L" * 128]),
                node_labels("cv:1"), ["L" * 128], "rdf_labels.label VARCHAR(128)"))
    out.append(("03-create_node-label-129", "03", lambda c, e: e.create_node("cv:1", labels=["L" * 129]),
                node_labels("cv:1"), ["L" * 129], "one past"))
    out.append(("03-create_node-key-129", "03", lambda c, e: e.create_node("cv:1", properties={"k" * 129: "x"}),
                node_prop("cv:1", "k" * 129), "x", "rdf_props.key VARCHAR(128)"))
    for n in (64_001, 1_000_000):
        v = big(n, "b")
        out.append((f"03-bulk_create_nodes-prop-{n}", "03",
                    lambda c, e, v=v: (len(e.bulk_create_nodes([{"id": "cv:b", "labels": ["L"], "properties": {"v": v}}])) == 1),
                    node_prop("cv:b", "v"), v, "server loader / SQL batch path"))
    for n, note in ((1_000_000, "~1 MB qualifier"), (MAXSTR - 20, "qualifier JSON near the long-string limit"),
                    (4_000_000, "past the long-string limit")):
        v = big(n, "q")
        out.append((f"03-create_edge-qualifier-{n}", "03",
                    lambda c, e, v=v: e.create_edge("cq:1", "R", "cq:2", qualifiers={"big": v}),
                    edge_qual("cq:1", "R", "cq:2", "big"), v, note,
                    lambda c, e: (e.create_node("cq:1"), e.create_node("cq:2"))))
    # ---- 08 Cypher writes
    for n in (64_000, 64_001, 1_000_000):
        v = big(n, "c")
        out.append((f"08-cypher-create-prop-{n}", "08",
                    lambda c, e, v=v: e.execute_cypher("CREATE (n:L {id: 'cy:1', p: $v})", {"v": v}),
                    cypher_val("MATCH (n {id: 'cy:1'}) RETURN n.p AS p", {}, "p"), v, ""))
    for n in (64_001, 1_000_000):
        v = big(n, "s")
        out.append((f"08-cypher-set-prop-{n}", "08",
                    lambda c, e, v=v: e.execute_cypher("MATCH (n {id: 'cy:2'}) SET n.p = $v", {"v": v}),
                    cypher_val("MATCH (n {id: 'cy:2'}) RETURN n.p AS p", {}, "p"), v, "",
                    lambda c, e: e.execute_cypher("CREATE (n:L {id: 'cy:2'})")))
    for n in (10, 1_000_000, 4_000_000):
        v = big(n, "r")
        out.append((f"08-cypher-create-relprop-{n}", "08",
                    lambda c, e, v=v: e.execute_cypher("CREATE (a:L {id: 'cr:1'})-[:R {q: $v}]->(b:L {id: 'cr:2'})", {"v": v}),
                    edge_qual("cr:1", "R", "cr:2", "q"), v, "relationship property in qualifiers"))
        out.append((f"08-cypher-create-relprop-{n}-sqlread", "08",
                    lambda c, e, v=v: e.execute_cypher("CREATE (a:L {id: 'cr:1'})-[:R {q: $v}]->(b:L {id: 'cr:2'})", {"v": v}),
                    sql_qual("cr:1", "q"), v, "same write; rdf_edges.qualifiers read by SQL"))
    # ---- 17 store adapter
    for n in (64_001, 1_000_000):
        v = big(n, "a")

        def w(c, e, v=v):
            from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
            return IRISGraphStore(c.conn, namespace=lib.NS).write_nodes([{"id": "sa:1", "labels": ["L"], "properties": {"v": v}}])

        def rd(c, e):
            from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
            r = IRISGraphStore(c.conn, namespace=lib.NS).get_nodes(["sa:1"])
            if r.error:
                raise RuntimeError(r.error)
            for row in r.rows:
                d = row if isinstance(row, dict) else dict(zip(r.columns, row))
                props = d.get("properties") or {}
                if isinstance(props, str):
                    props = json.loads(props)
                if "v" in props:
                    return props["v"]
                if "v" in d:
                    return d["v"]
            return None
        out.append((f"17-store-write_nodes-prop-{n}", "17", w, rd, v, "IRISGraphStore.write_nodes / get_nodes"))
    # ---- 05 temporal edge attributes (^KG("edgeprop"))
    for n in (1_000_000, MAXSTR, 4_000_000):
        v = big(n, "t")
        out.append((f"05-temporal-attrs-{n}", "05",
                    lambda c, e, v=v: e.create_edge_temporal("ct:1", "R", "ct:2", timestamp=TS, attrs={"a": v}),
                    lambda c, e: (e.get_edge_attrs(TS, "ct:1", "R", "ct:2") or {}).get("a"), v, "^KG(edgeprop) value",
                    lambda c, e: (e.create_node("ct:1"), e.create_node("ct:2"))))
    # ---- 15 reification props
    for n in (64_001, 1_000_000):
        v = big(n, "z")

        def w(c, e, v=v):
            eid = c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s = 'rf:1'")[0][0]
            return e.reify_edge(int(eid), reifier_id="rf:reif", props={"v": v}) is not None
        out.append((f"15-reify_edge-prop-{n}", "15", w, node_prop("rf:reif", "v"), v, "reifier node property",
                    lambda c, e: (e.create_node("rf:1"), e.create_node("rf:2"), e.create_edge("rf:1", "R", "rf:2"))))
    # ---- 06 vector metadata
    for n in (1_000_000, 4_000_000):
        v = big(n, "m")

        def w(c, e, v=v):
            return e.store_embedding("ve:1", [0.1, 0.2, 0.3, 0.4], metadata={"m": v})

        def rd(c, e):
            r = c.sql("SELECT metadata FROM Graph_KG.kg_NodeEmbeddings WHERE node_id = 've:1'")
            if not r:
                return None
            md = r[0][0]
            md = json.loads(str(md)) if md not in (None, "") else {}
            return md.get("m")
        out.append((f"06-store_embedding-metadata-{n}", "06", w, rd, v, "kg_NodeEmbeddings.metadata %DynamicObject",
                    lambda c, e: e.create_node("ve:1")))
    return out


def main() -> int:
    outp = Path(sys.argv[1])
    sel = sys.argv[2:]
    res = []
    for cs in cases():
        name, module, w, r, exp, note = cs[:6]
        setup = cs[6] if len(cs) > 6 else None
        if sel and not any(name.startswith(s) for s in sel):
            continue
        res.append(run_case(name, module, w, r, exp, note, setup))
        lib.dump(outp, res)
    summary = {}
    for x in res:
        summary.setdefault(x["module"], {})[x["case"]] = x["outcome"]
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
