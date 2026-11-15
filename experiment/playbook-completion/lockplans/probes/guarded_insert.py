#!/usr/bin/env python3
"""Concurrent guarded inserts, live on AUDITD (gate 3.5-lockplans, modules 08 and 17).

    locks.sh iris python guarded_insert.py OUT_DIR [--only CASE ...] [--race-trials N]

The writers under test check-then-insert without a lock of their own:
- module 08, Cypher CREATE of a node: INSERT ... SELECT ... WHERE NOT EXISTS on nodes, rdf_labels, rdf_props
  (iris_vector_graph/cypher/translator.py:9699-9756); of an edge between matched nodes: INSERT ... SELECT DISTINCT
  ... WHERE NOT EXISTS on rdf_edges (translator.py:10345-10360); of an edge between literal endpoints: INSERT ...
  VALUES, no guard (translator.py:10233-10248, F-0805);
- module 17, IRISGraphStore.write_nodes: INSERT ... VALUES with a -119 refusal skipped as "already there"
  (iris_vector_graph/stores/iris_sql_store.py:1214-1251, 755-761; _write_txn.is_duplicate :46-49); write_edges:
  guarded endpoint INSERT ... WHERE NOT EXISTS, then the edge INSERT ... VALUES with -119 skipped (:1253-1303).
The only locks on these paths are IRIS's own SQL row locks (an INSERT holds its new row's lock to the end of the
transaction; E-ROWLOCK, iris-contract/CONTRACT.md:44), the unique-key check (-119 at once against another
transaction's uncommitted key; E-UNIQUE :45), the foreign keys' check, and the shared ^IVG.AdjW(graph) the edge
functional index takes (Adjacency.cls:61-74), which never excludes another writer ("writers never wait for
writers", Adjacency.cls:25). SQL SELECT, the NOT EXISTS guard included, reads uncommitted rows (E-VIS :31).

Interleavings (deterministic, per case and per ending):
  A opens a caller transaction (SQL START TRANSACTION; the product write joins it as a nested level, CYP-B6.2,
  _write_txn.py:1-30) and runs its write W_A, then HOLDS it open. B (autocommit) starts W_B on the same key in a
  thread. While A holds: B's process state, B's answer if it returned, the lock table rows owned by A or B, and the
  rows visible (dirty) under the key. Then A ends: COMMIT or ROLLBACK. B is joined, the final rows are read.
Serial references (measured live, same seed): B alone; A then B; B then A.
Oracle (serializability of committed work, the IRIS isolation premise the product relies on):
  - A COMMIT: the final rows equal those of A;B or of B;A, and B's answer class (ok / refused) is that order's.
  - A ROLLBACK: A never happened, so the final rows equal those of "B alone" and B's answer is that run's (ok),
    or B was refused and wrote nothing.
  - integrity: no rdf_labels / rdf_props / rdf_edges row under the key without its node row.
Race (no hold): 2 connections released together run W_A and W_B on a fresh key, N trials; each trial's final rows
and answers are classed as serializable (rows of A;B or B;A with both answers ok), refused (one answer an error, the
rows exactly the other's) or anomalous (anything else).
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lpcommon as L  # noqa: E402

HOLD = 3.0


def snapshot(c, ids):
    """Rows under the key (the ids the case writes), sorted; with ^KG("out", 0, s, p, o) for edges."""
    ph = ",".join("?" for _ in ids)
    q = lambda s: sorted([tuple("" if v is None else str(v) for v in r) for r in c.sql(s, *ids)])  # noqa: E731
    snap = {
        "nodes": q(f"SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id IN ({ph})"),
        "labels": q(f"SELECT s, label, graph_id FROM Graph_KG.rdf_labels WHERE s IN ({ph})"),
        "props": q(f'SELECT s, "key", val, graph_id FROM Graph_KG.rdf_props WHERE s IN ({ph})'),
        "edges": q(f"SELECT s, p, o_id, graph_id FROM Graph_KG.rdf_edges WHERE s IN ({ph})"),
    }
    kg = []
    for s, p, o, g in snap["edges"]:
        kg.append((s, p, o, int(c.o.isDefined("^KG", "out", 0 if g == "" else g, s, p, o))))
    snap["kg_out"] = sorted(kg)
    return snap


def orphans(snap):
    have = {(n, g) for n, g in snap["nodes"]}
    out = []
    for s, lab, g in snap["labels"]:
        if (s, g) not in have:
            out.append(["label", s, lab, g])
    for s, k, v, g in snap["props"]:
        if (s, g) not in have:
            out.append(["prop", s, k, g])
    for s, p, o, g in snap["edges"]:
        for end in (s, o):
            if (end, g) not in have:
                out.append(["edge-end", s, p, o, end])
    return out


def norm(snap, key_from, key_to):
    """The snapshot with one trial's ids renamed, for comparing a race trial with the reference rows."""
    return json.loads(json.dumps(snap).replace(key_from, key_to))


class Case:
    def __init__(self, name, module, ids, wa, wb, seed=None, tag="", note="", extra=None, cleanup=None):
        self.name, self.module, self.ids, self.wa, self.wb = name, module, ids, wa, wb
        self.seed, self.tag, self.note = seed, tag, note
        self.extra, self.cleanup = extra, cleanup


def W(kind, *a):
    """A product write: kind 'cy' (engine.execute_cypher(text)), 'wn' (store.write_nodes(list)), 'we'
    (store.write_edges(list)). Returns fn(conn, engine, store)."""
    if kind == "cy":
        return lambda c, e, s: e.execute_cypher(a[0])
    if kind == "wn":
        return lambda c, e, s: s.write_nodes(a[0])
    if kind == "we":
        return lambda c, e, s: s.write_edges(a[0])
    if kind == "map":
        return lambda c, e, s: e.map_sql_table(*a)
    raise ValueError(kind)


def _ident(k):
    """A label map_sql_table accepts (sanitize_identifier refuses '-'; run-2 used 'gi-Map' and was refused)."""
    return k.replace("-", "_")


def _remove_mapping(e, label):
    """The product's own remove_table_mapping; it raises ValueError when the label is not mapped (fhir.py:237-250)."""
    try:
        e.remove_table_mapping(label)
    except ValueError:
        pass


def make_cases(k):
    """Cases over key prefix k (a trial or interleaving gets its own k)."""
    return [
        Case("08-node-label", "08", [f"{k}n"],
             W("cy", f"CREATE (n:LA {{id: '{k}n', pa: 'a'}})"), W("cy", f"CREATE (n:LB {{id: '{k}n', pb: 'b'}})"),
             note="CYP-B6.7.2: a CREATE of an id that exists adds to that node (USER_GUIDE.md:142-147)"),
        Case("08-node-nolabel", "08", [f"{k}m"],
             W("cy", f"CREATE (n {{id: '{k}m', pa: 'a'}})"), W("cy", f"CREATE (n {{id: '{k}m', pb: 'b'}})"),
             note="as 08-node-label without labels: rdf_props has no foreign key to nodes (schema.py:411-418)"),
        Case("08-edge-matched", "08", [f"{k}a", f"{k}b"],
             W("cy", f"MATCH (a {{id: '{k}a'}}), (b {{id: '{k}b'}}) CREATE (a)-[:R]->(b)"),
             W("cy", f"MATCH (a {{id: '{k}a'}}), (b {{id: '{k}b'}}) CREATE (a)-[:R]->(b)"),
             seed=W("cy", f"CREATE (:N {{id: '{k}a'}}), (:N {{id: '{k}b'}})"),
             note="CYP-B6.7.6: outside multigraph mode a second create of the same edge adds nothing and raises no "
                  "error (KNOWN_ISSUES.md:25-41)"),
        Case("08-edge-literal", "08", [f"{k}c", f"{k}d"],
             W("cy", f"CREATE (a:N {{id: '{k}c'}})-[:R]->(b:N {{id: '{k}d'}})"),
             W("cy", f"CREATE (a:N {{id: '{k}c'}})-[:R]->(b:N {{id: '{k}d'}})"),
             note="CYP-B6.7.7 / F-0805: the literal-endpoint edge INSERT ... VALUES has no guard"),
        Case("08-map-sql-table", "08", [f"{k}Map"],
             W("map", "Graph_KG.nodes", "node_id", _ident(k) + "Map", ["a"]),
             W("map", "Graph_KG.nodes", "node_id", _ident(k) + "Map", ["b"]),
             extra=("SELECT label, sql_table, id_column, prop_columns FROM Graph_KG.table_mappings WHERE label = ?",
                    _ident(k) + "Map"),
             cleanup=lambda c, e, s, lab=_ident(k) + "Map": _remove_mapping(e, lab),
             note="map_sql_table: UPDATE ... WHERE label, then INSERT when no row was updated, in one write_txn "
                  "(iris_vector_graph/_engine/fhir.py:129-138); the positive case: E-ROWLOCK makes the UPDATE wait"),
        Case("17-write-nodes", "17", [f"{k}s"],
             W("wn", [{"id": f"{k}s", "labels": ["LA"], "properties": {"pa": "a"}}]),
             W("wn", [{"id": f"{k}s", "labels": ["LB"], "properties": {"pb": "b"}}]),
             note="iris_sql_store.py:1215-1220: a duplicate row is skipped; is_duplicate (-119) = 'the row is "
                  "already there' (_write_txn.py:46-49)"),
        Case("17-write-edges", "17", [f"{k}e", f"{k}f"],
             W("we", [{"s": f"{k}e", "p": "R", "o": f"{k}f"}]), W("we", [{"s": f"{k}e", "p": "R", "o": f"{k}f"}]),
             note="iris_sql_store.py:1253-1303: guarded endpoint inserts, edge INSERT with -119 skipped"),
    ]


class Side:
    """One identity-checked connection with its engine and store."""

    def __init__(self):
        self.c = L.conn()
        self.e = L.engine(self.c)
        self.s = L.store(self.c)

    def run(self, w):
        return L.call(lambda: w(self.c, self.e, self.s))

    def close(self):
        self.c.close()


def fresh(ctl, case):
    L.reset(ctl)
    if case.cleanup:
        side = ctl_side(ctl)
        case.cleanup(side.c, side.e, side.s)
        ctl.conn.commit()
    if case.seed:
        r = ctl_side(ctl).run(case.seed)
        ctl.conn.commit()
        if not r["ok"]:
            raise RuntimeError(f"seed failed: {r}")


_ctl_cache = {}


def ctl_side(ctl):
    s = _ctl_cache.get(id(ctl))
    if s is None:
        s = Side.__new__(Side)
        s.c, s.e, s.s = ctl, L.engine(ctl), L.store(ctl)
        _ctl_cache[id(ctl)] = s
    return s


def serial_refs(ctl, case):
    side = ctl_side(ctl)
    refs = {}
    for name, order in (("A alone", ["wa"]), ("B alone", ["wb"]), ("A;B", ["wa", "wb"]), ("B;A", ["wb", "wa"])):
        fresh(ctl, case)
        answers = []
        for w in order:
            answers.append(side.run(getattr(case, w)))
            ctl.conn.commit()
        snap = L_snapshot(ctl, case)
        refs[name] = {"answers": answers, "rows": snap}
    return refs


def L_snapshot(c, case):
    snap = snapshot(c, case.ids)
    if case.extra:
        q, *args = case.extra
        snap["extra"] = sorted([tuple("" if v is None else str(v) for v in r) for r in c.sql(q, *args)])
    return snap


def interleave(case, ending, A, B, obs, hold=HOLD):
    fresh(obs, case)
    res = {"case": case.name, "module": case.module, "ending": ending, "hold_s": hold,
           "pids": {"A": A.c.pid, "B": B.c.pid}}
    A.c.sql("START TRANSACTION")
    res["A_tlevel_after_start"] = L.tlevel(A.c)
    res["A"] = A.run(case.wa)
    res["A_tlevel_after_write"] = L.tlevel(A.c)
    res["dirty_after_A"] = L_snapshot(obs, case)
    done = {}

    def work():
        done["r"] = B.run(case.wb)
        done["at"] = round(time.time() - t0, 3)
    t0 = time.time()
    th = threading.Thread(target=work)
    th.start()
    samples = []
    while time.time() - t0 < hold:
        time.sleep(0.5)
        samples.append({"t": round(time.time() - t0, 2), "B_returned": "r" in done,
                        **L.proc_state(obs, B.c.pid)})
    res["B_state_while_A_holds"] = samples
    res["locks_while_A_holds"] = L.lock_table(obs, pids={A.c.pid, B.c.pid})
    res["B_returned_before_A_ended"] = "r" in done
    res["B_answer_before_A_ended"] = done.get("r")
    res["dirty_while_A_holds"] = L_snapshot(obs, case)
    t_end = time.time() - t0
    try:
        A.c.sql(ending.upper())
    except Exception as ex:  # noqa: BLE001
        res["A_end_error"] = str(ex)[:300]
    res["A_ended_at_s"] = round(t_end, 2)
    th.join(90)
    res["B"] = done.get("r")
    res["B_returned_at_s"] = done.get("at")
    with_b = B.c.sql("SELECT $TLEVEL")[0][0]
    res["B_tlevel_after"] = int(with_b)
    res["final"] = L_snapshot(obs, case)
    res["orphans"] = orphans(res["final"])
    res["locks_after"] = L.lock_table(obs, pids={A.c.pid, B.c.pid})
    return res


def judge(r, refs):
    ok = lambda a: bool(a and a.get("ok"))  # noqa: E731
    fin = r["final"]
    if r["ending"] == "commit":
        matches = [n for n in ("A;B", "B;A") if refs[n]["rows"] == fin and ok(refs[n]["answers"][1 if n == "A;B" else 0]) == ok(r["B"])]
        r["serial_match"] = matches
        r["serializable"] = bool(matches) and not r["orphans"]
    else:
        b_alone = refs["B alone"]
        empty = all(not v for v in fin.values()) or fin == refs["_seed"]["rows"]
        if ok(r["B"]):
            r["serializable"] = fin == b_alone["rows"] and not r["orphans"]
            r["serial_match"] = ["B alone"] if r["serializable"] else []
        else:
            # a refusal is serializable only if B wrote nothing (the rows are the seed's)
            r["serializable"] = empty and not r["orphans"]
            r["serial_match"] = ["B refused, nothing written"] if r["serializable"] else []
    r["B_answered_ok_but_lost"] = ok(r["B"]) and not r["serializable"] and r["ending"] == "rollback"
    return r


def seed_ref(ctl, case):
    fresh(ctl, case)
    return {"answers": [], "rows": L_snapshot(ctl, case)}


def race(case_fn, trials, A, B, obs):
    """No hold: A and B released together on a fresh key per trial."""
    out = []
    # reference rows on key "rk" (renamed per trial)
    base = case_fn("rk-")
    refs = json.loads(json.dumps(serial_refs(obs, base), default=str))   # rows as lists, as norm() gives them
    for t in range(trials):
        k = f"rt{t}-"
        case = case_fn(k)
        if case.seed:
            r0 = ctl_side(obs).run(case.seed)
            obs.conn.commit()
            if not r0["ok"]:
                raise RuntimeError(f"seed failed: {r0}")
        bar = threading.Barrier(2)
        ans = {}

        def go(side, w, tag):
            bar.wait(30)
            ans[tag] = side.run(w)
        ths = [threading.Thread(target=go, args=(A, case.wa, "A")), threading.Thread(target=go, args=(B, case.wb, "B"))]
        for th in ths:
            th.start()
        for th in ths:
            th.join(90)
        fin = norm(L_snapshot(obs, case), k, "rk-")
        ok_a, ok_b = ans.get("A", {}).get("ok"), ans.get("B", {}).get("ok")
        cls = "anomalous"
        if ok_a and ok_b and (fin == refs["A;B"]["rows"] or fin == refs["B;A"]["rows"]):
            cls = "serializable"
        elif ok_a != ok_b:
            # one refused: the rows must be exactly what the other alone writes
            survivor = refs["A alone" if ok_a else "B alone"]["rows"]
            cls = "refused-clean" if fin == survivor else "refused-other"
        if orphans(fin):
            cls = "anomalous-orphans"
        out.append({"trial": t, "A": ans.get("A"), "B": ans.get("B"), "class": cls, "final": fin})
    summary = {}
    for r in out:
        summary[r["class"]] = summary.get(r["class"], 0) + 1
    return {"case": base.name, "refs": refs, "trials": out, "summary": summary}


def main() -> int:
    out = Path(sys.argv[1])
    only = []
    if "--only" in sys.argv:
        i = sys.argv.index("--only") + 1
        while i < len(sys.argv) and not sys.argv[i].startswith("--"):
            only.append(sys.argv[i])
            i += 1
    trials = int(sys.argv[sys.argv.index("--race-trials") + 1]) if "--race-trials" in sys.argv else 0
    obs = L.conn()
    print("engine:", L.version(obs), "namespace", obs.namespace, flush=True)
    A, B = Side(), Side()
    results = {"interleavings": [], "races": []}
    try:
        for idx, case in enumerate(make_cases("gi-")):
            if only and case.name not in only:
                continue
            refs = serial_refs(obs, case)
            refs["_seed"] = seed_ref(obs, case)
            for ending in ("commit", "rollback"):
                r = interleave(case, ending, A, B, obs)
                r["refs"] = {k: v for k, v in refs.items()}
                r["note"] = case.note
                judge(r, refs)
                results["interleavings"].append(r)
                dump_one = {k: r[k] for k in ("case", "ending", "A", "B", "B_returned_before_A_ended",
                                              "B_returned_at_s", "A_ended_at_s", "serializable", "serial_match",
                                              "B_answered_ok_but_lost", "orphans")}
                dump_one["B_state_last"] = r["B_state_while_A_holds"][-1:] if r["B_state_while_A_holds"] else None
                dump_one["final"] = r["final"]
                print(json.dumps(dump_one, default=str)[:2500], flush=True)
                L.dump(out / f"{case.name}-{ending}.json", r)
        if trials:
            for name in ("08-node-label", "08-edge-matched", "17-write-nodes", "17-write-edges"):
                if only and name not in only:
                    continue
                fn = (lambda nm: (lambda k: next(c for c in make_cases(k) if c.name == nm)))(name)
                L.reset(obs)
                rr = race(fn, trials, A, B, obs)
                results["races"].append(rr)
                print(json.dumps({"race": rr["case"], "summary": rr["summary"]}), flush=True)
                L.dump(out / f"race-{name}.json", rr)
        for case in make_cases("gi-"):
            if case.cleanup:
                fresh(obs, case)
        L.reset(obs)
    finally:
        A.close()
        B.close()
        obs.close()
    L.dump(out / "guarded_insert.json", results)
    summ = {"interleavings": [{k: r[k] for k in ("case", "ending", "serializable", "B_answered_ok_but_lost")}
                              | {"orphans": len(r["orphans"]), "B_ok": bool(r["B"] and r["B"].get("ok"))}
                              for r in results["interleavings"]],
            "races": [{"case": r["case"], "summary": r["summary"]} for r in results["races"]]}
    L.dump(out / "summary.json", summ)
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
