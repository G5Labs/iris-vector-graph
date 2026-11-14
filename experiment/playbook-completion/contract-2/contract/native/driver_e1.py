#!/usr/bin/env python3
"""Premise E-1 cases: the pin's OWN compiled embedded SQL (&sql) in AUDITCORE, driven as the contract drives dynamic SQL.

    python driver_e1.py cases.json observed.json [--only ID ...] [--journal journal.json]

Nothing is compiled. The pin's classes are in AUDITCORE because the pin's own deploy path put them there
(`IRISGraphEngine.initialize_schema()`, tools/deploy_namespace.py). Every process is one DB-API connection with the
Native API on that same connection (the product's client path, `dbapi` in driver.py): transaction verbs, the
driver's commit / rollback / autocommit and dynamic SQL work as in driver.py; the `emb_*` operations call a pin
method through `classMethodValue` on that connection, so the method's embedded statements run in the same server
process and transaction as the case's other operations.

Model tables (src/lib.rs, contract-2) and the AUDITCORE rows they stand for (all under the test prefix, emptied
before every case; the rest of AUDITCORE is never written):
  N   Graph_KG.nodes, default graph ('')       node_id 'env2e1-n*'                     value ''
  R   Graph_KG.rdf_edges, graph 'env2e1g'      s 'env2e1-r*', p 'env2e1p', o 'env2e1-o'  value 't' (temporal marker)
  R0  Graph_KG.rdf_edges, default graph        s = o = 'env2e1-n*', p 'env2e1p'         value 't'
  G   Graph_KG.embedding_registry, 'env2e1g'   table_name 'Graph_KG.<k>', kind 'node'   value 'g'
The endpoint nodes of R (graph 'env2e1g') are setup rows, committed before every case and not observed.

The pin methods (cited at the pin):
  emb_register  Graph.KG.EdgeScan.RegisterDefaultNode(k, .seen)          EdgeScan.cls:247-258
  emb_retract   Graph.KG.Adjacency.RetractTemporalRows("env2e1g", root)  Adjacency.cls:650-692 (root: ^IVGAuditE1(n))
  emb_count     Graph.KG.GraphVerify.VerifyGraph("env2e1g")              GraphVerify.cls:40-79 (counts.sqlEdges)
  emb_route     Graph.KG.GraphStores.VectorRouteGuard("env2e1g")         GraphStores.cls:304-318
  emb_assert    Graph.KG.Adjacency.AssertTemporalRow(gk, k, p, k, 1, 0)  Adjacency.cls:575-620
  sql_txn_*     SELECT Graph_KG.Txn_Begin / Txn_End / Txn_Undo (?) on the cursor: the pin's compiled [SqlProc]
                wrappers (SqlProcs.cls:168-180) over Graph.KG.Txn (Txn.cls:19-58), the product's main write path
                (_write_txn.py)
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE.parents[2] / "traces"))
import driver as base  # noqa: E402  (the copied r6 driver: Async, norm_err, ISSUE_WAIT, AWAIT_WAIT)
from iris_conn import Conn, version  # noqa: E402

NS = "AUDITCORE"
G = "env2e1g"
P = "env2e1p"
O = "env2e1-o"
PREFIX = "env2e1-"
SETUP_NODES = [f"{PREFIX}r{i}" for i in range(1, 7)] + [O]
SCRATCH = "^IVGAuditE1"
TEMPORAL = '{"temporal":true'
_calls = [0]


def q(c: Conn, sql: str, *params):
    return c.sql(sql, *params)


def select_rows(c, table: str) -> List[List[str]]:
    if table == "N":
        rows = q(c, "SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id %STARTSWITH ?", PREFIX + "n")
        return sorted([str(a), "<null>" if b is None else str(b)] for a, b in rows)
    if table in ("R", "R0"):
        g = G if table == "R" else ""
        rows = q(c, "SELECT s, qualifiers FROM Graph_KG.rdf_edges WHERE graph_id = ? AND s %STARTSWITH ? AND p = ?",
                 g, PREFIX, P)
        return sorted([str(a), "t" if (b is not None and str(b).replace(" ", "").startswith(TEMPORAL)) else str(b)]
                      for a, b in rows)
    if table == "G":
        rows = q(c, "SELECT table_name FROM Graph_KG.embedding_registry WHERE graph_id = ?", G)
        return sorted([str(a).split(".")[-1], "g"] for (a,) in rows)
    raise ValueError(table)


class CoreProc(base.DbapiProc):
    """A DbapiProc on AUDITCORE whose SQL rows are the test prefix's rows of the pin's tables."""

    def __init__(self, ctl: Conn) -> None:  # noqa: D107
        self.c = Conn(NS)
        self.o = self.c.o
        self.pid = self.c.pid
        self.pending = None
        self.ctl = ctl

    def _dml(self, op: Dict) -> Dict:
        cur = self.c.conn.cursor()
        t, k = op.get("table", "T"), op.get("k")
        try:
            if t == "N":
                if op["op"] == "insert":
                    cur.execute("INSERT INTO Graph_KG.nodes (node_id, graph_id) VALUES (?, '')", (k,))
                elif op["op"] == "update":
                    cur.execute("UPDATE Graph_KG.nodes SET created_at = created_at WHERE node_id = ? AND graph_id = ''", (k,))
                else:
                    cur.execute("DELETE FROM Graph_KG.nodes WHERE node_id = ? AND graph_id = ''", (k,))
            elif t == "R":
                if op["op"] == "insert":
                    cur.execute("INSERT INTO Graph_KG.rdf_edges (s, p, o_id, graph_id, qualifiers) VALUES (?, ?, ?, ?, ?)",
                                (k, P, O, G, '{"temporal":true}'))
                elif op["op"] == "update":
                    cur.execute("UPDATE Graph_KG.rdf_edges SET ekey = ekey WHERE s = ? AND p = ? AND o_id = ? AND graph_id = ?",
                                (k, P, O, G))
                else:
                    cur.execute("DELETE FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ? AND graph_id = ?",
                                (k, P, O, G))
            elif t == "G":
                if op["op"] == "insert":
                    cur.execute("INSERT INTO Graph_KG.embedding_registry (table_name, graph_id, kind) VALUES (?, ?, 'node')",
                                ("Graph_KG." + k, G))
                elif op["op"] == "delete":
                    cur.execute("DELETE FROM Graph_KG.embedding_registry WHERE table_name = ? AND graph_id = ?",
                                ("Graph_KG." + k, G))
                else:
                    return {"obs": "refused", "what": "update on G"}
            else:
                return {"obs": "refused", "what": f"table {t} on core"}
            return {"obs": "count", "rowcount": max(cur.rowcount, 0)}
        except Exception as e:  # noqa: BLE001
            return base.norm_err(e)
        finally:
            cur.close()

    # ------------------------------------------------------------------------------------------ the pin's methods
    @staticmethod
    def _status(st) -> str:
        if str(st) == "1":
            return "1"
        m = re.search(r"SQLCODE:?\s*<?(-?\d+)", str(st)) or re.search(r"SQLCODE (-?\d+)", str(st))
        return f"err:{m.group(1)}" if m else "err:" + str(st)[:80]

    def _emb(self, op: Dict) -> Dict:
        k = op["op"]
        o = self.o
        try:
            if k == "emb_register":
                return {"obs": "value", "value": str(o.classMethodValue("Graph.KG.EdgeScan", "RegisterDefaultNode", op["k"], ""))}
            if k == "emb_retract":
                _calls[0] += 1
                n = _calls[0]
                self.ctl.o.set("", SCRATCH, n, op["k"], P, O)
                try:
                    st = o.classMethodValue("Graph.KG.Adjacency", "RetractTemporalRows", G, f"{SCRATCH}({n})")
                    if str(st) != "1":
                        st = self.ctl.call("%SYSTEM.Status", "GetErrorText", st)
                    return {"obs": "value", "value": self._status(st)}
                finally:
                    pass  # ^IVGAuditE1 is killed by reset(); a pending call still walks its own subtree
            if k == "emb_count":
                rep = json.loads(str(o.classMethodValue("Graph.KG.GraphVerify", "VerifyGraph", G)))
                return {"obs": "value", "value": str(rep["counts"]["sqlEdges"])}
            if k == "emb_route":
                try:
                    r = o.classMethodValue("Graph.KG.GraphStores", "VectorRouteGuard", G, "kg_KNN_VEC")
                    return {"obs": "value", "value": str(r)}
                except Exception as e:  # noqa: BLE001
                    if "keeps its vectors in its own table" in str(e) or "IVGRouteRefused" in str(e):
                        return {"obs": "value", "value": "refused"}
                    raise
            if k == "emb_assert":
                gk = 0 if op["mode"] == "zero" else ""
                st = o.classMethodValue("Graph.KG.Adjacency", "AssertTemporalRow", gk, op["k"], P, op["k"], "1.0", 0, "")
                if str(st) != "1":
                    st = self.ctl.call("%SYSTEM.Status", "GetErrorText", st)
                return {"obs": "value", "value": self._status(st)}
        except Exception as e:  # noqa: BLE001
            return base.norm_err(e)
        return {"obs": "refused", "what": f"{k} on core"}

    def run(self, op: Dict) -> Dict:
        k = op["op"]
        if k == "select":
            if self.pending is not None:
                return {"obs": "error", "error": "busy"}
            try:
                return {"obs": "rows", "rows": select_rows(self.c, op.get("table", "N"))}
            except Exception as e:  # noqa: BLE001
                return base.norm_err(e)
        if k in ("emb_register", "emb_retract"):
            if self.pending is not None:
                return {"obs": "error", "error": "busy"}
            a = base.Async(lambda: self._emb(op))
            r = a.wait(base.ISSUE_WAIT)
            if r is None:
                self.pending = a
                return {"obs": "pending"}
            return r
        if k in ("sql_txn_begin", "sql_txn_end", "sql_txn_undo"):
            if self.pending is not None:
                return {"obs": "error", "error": "busy"}
            fn = {"sql_txn_begin": "Txn_Begin", "sql_txn_end": "Txn_End", "sql_txn_undo": "Txn_Undo"}[k]
            arg = int(op["hold"]) if k == "sql_txn_begin" else int(op["level"])
            try:
                return {"obs": "value", "value": str(int(self.c.sql(f"SELECT Graph_KG.{fn}(?)", arg)[0][0]))}
            except Exception as e:  # noqa: BLE001
                return base.norm_err(e)
        if k in ("emb_count", "emb_route", "emb_assert"):
            if self.pending is not None:
                return {"obs": "error", "error": "busy"}
            return self._emb(op)
        if k in ("insert", "update", "delete") and op.get("table") in ("N", "R", "G"):
            if self.pending is not None:
                return {"obs": "error", "error": "busy"}
            a = base.Async(lambda: self._dml(op))
            r = a.wait(base.ISSUE_WAIT)
            if r is None:
                self.pending = a
                return {"obs": "pending"}
            return r
        return super().run(op)


def reset(ctl: Conn) -> None:
    """Remove every row of the test prefix (edges first: their foreign keys name the nodes) and the scratch global,
    then write the committed setup nodes of the test graph."""
    q(ctl, "DELETE FROM Graph_KG.rdf_edges WHERE graph_id = ?", G)
    q(ctl, "DELETE FROM Graph_KG.rdf_edges WHERE graph_id = '' AND s %STARTSWITH ?", PREFIX)
    q(ctl, "DELETE FROM Graph_KG.embedding_registry WHERE graph_id = ?", G)
    q(ctl, "DELETE FROM Graph_KG.nodes WHERE graph_id = '' AND node_id %STARTSWITH ?", PREFIX)
    ctl.o.kill(SCRATCH)
    have = {str(r[0]) for r in q(ctl, "SELECT node_id FROM Graph_KG.nodes WHERE graph_id = ?", G)}
    for n in SETUP_NODES:
        if n not in have:
            q(ctl, "INSERT INTO Graph_KG.nodes (node_id, graph_id) VALUES (?, ?)", n, G)


def cleanup(ctl: Conn) -> Dict:
    """After the last case: remove the setup nodes too; report what the test prefix still holds anywhere."""
    reset(ctl)
    q(ctl, "DELETE FROM Graph_KG.nodes WHERE graph_id = ?", G)
    left = {
        "nodes": q(ctl, "SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH ?", PREFIX)[0][0],
        "edges": q(ctl, "SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s %STARTSWITH ? OR graph_id = ?", PREFIX, G)[0][0],
        "registry": q(ctl, "SELECT COUNT(*) FROM Graph_KG.embedding_registry WHERE graph_id = ?", G)[0][0],
        "kg_out_graph": int(ctl.o.isDefined("^KG", "out", G)),
        "kg_in_graph": int(ctl.o.isDefined("^KG", "in", G)),
        "scratch": int(ctl.o.isDefined(SCRATCH)),
    }
    default_out = 0
    for i in range(1, 10):
        default_out += int(ctl.o.isDefined("^KG", "out", 0, f"{PREFIX}n{i}"))
    left["kg_out_default_prefix"] = default_out
    return left


def run_case(case: Dict, ctl: Conn, journal: Optional[Dict] = None) -> Dict:
    reset(ctl)
    procs: List[Any] = [CoreProc(ctl) for _ in range(case["procs"])]
    mark = None
    if journal is not None:
        import journal as jr
        mark = jr.mark()
    dead = set()
    obs = []
    try:
        for p, op in case["steps"]:
            if op["op"] == "terminate":
                t = op["target"]
                if t not in dead:
                    ctl.call("%SYSTEM.Process", "Terminate", procs[t].pid)
                    if not base.gone(ctl, procs[t].pid):
                        raise RuntimeError("terminated process did not exit")
                    dead.add(t)
                obs.append(base.ok())
                continue
            if p in dead:
                obs.append({"obs": "error", "error": "dead"})
                continue
            obs.append(procs[p].run(op))
        finals = []
        for t in case.get("observe_tables", []):
            try:
                finals.append({"obs": "rows", "rows": select_rows(ctl, t)})
            except Exception as e:  # noqa: BLE001
                finals.append(base.norm_err(e))
        return {"obs": obs, "finals": finals}
    finally:
        pids = {i: pr.pid for i, pr in enumerate(procs)}
        for i, pr in enumerate(procs):
            if i not in dead:
                if pr.pending is not None:
                    ctl.call("%SYSTEM.Process", "Terminate", pr.pid)
                    base.gone(ctl, pr.pid)
                    pr.c.close()
                else:
                    pr.close()
        if journal is not None and mark is not None:
            import journal as jr
            recs = jr.records_since(mark, dbs={"/usr/irissys/mgr/auditcore/"}, pids=set(pids.values()))
            smap = jr.storage_map(ctl)
            journal[case["id"]] = {
                "pids": pids,
                "records": [{"p": r["p"], "t": r["t"], "x": r["x"], "store": jr.store_of(r["g"], smap) if r["g"] else "",
                             "g": r["g"][:160]} for r in recs],
            }


def main() -> int:
    cases = json.loads(Path(sys.argv[1]).read_text())
    out_path = Path(sys.argv[2])
    # flags: [--journal FILE] before [--only ID ...] (everything after --only is an id)
    jpath = Path(sys.argv[sys.argv.index("--journal") + 1]) if "--journal" in sys.argv else None
    only = set(sys.argv[sys.argv.index("--only") + 1:]) if "--only" in sys.argv else None
    journal: Optional[Dict] = (json.loads(jpath.read_text()) if jpath and jpath.exists() else {}) if jpath else None
    observed: Dict[str, List[Dict]] = json.loads(out_path.read_text()) if out_path.exists() else {}
    ctl = Conn(NS)
    try:
        print("engine:", version(ctl), "namespace:", NS, flush=True)
        for c in cases:
            if only and c["id"] not in only:
                continue
            t = time.time()
            observed[c["id"]] = [run_case(c, ctl, journal)]
            print(f"{c['id']}: {time.time() - t:.2f}s", flush=True)
            out_path.write_text(json.dumps(observed, indent=1))
            if jpath is not None:
                jpath.write_text(json.dumps(journal, indent=1))
    finally:
        left = cleanup(ctl)
        print("cleanup:", json.dumps(left), flush=True)
        ctl.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
