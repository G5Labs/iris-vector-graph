"""bulk_load binding: the actual BulkLoader.load_nodes / rebuild_all_indices and the actual get_node reader on the
run-isolated retest fixture, compared with a port of bulk_load.rs over an enumerated domain.

Domain (72 histories, fresh ids per history, loader graph named per run): first call index mode {indexed, %NOINDEX}
x how it ends {done, fails at the label insert, fails at the property insert} x re-run {none, indexed, %NOINDEX}
x rebuild afterwards {no, yes} x the first id already present in the default graph {no, yes}. Failures are injected
by a connection wrapper at the first executemany into rdf_labels / rdf_props (the state a lost connection leaves).
Observed per node: get_node(n, graph) present, its labels, its property keys; also the re-run's returned counts and,
when seeded, the default-graph node's unchanged read. Six port mutations mirror the model's controls.
Ordinary data, fixture only."""
import hashlib, itertools, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(Path(os.environ.get("IVG_RUNTIME_DIR", str(REPO / ".g5/uplift/consolidated/iteration-25")))))
import runtime  # noqa: E402
RUN = os.environ.get("BL_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
TAG = RUN.replace("T", "").replace("Z", "")[-8:]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class FailAt:
    """Wrap a DB-API connection: the first executemany whose SQL names `table` raises (injected interruption)."""
    def __init__(self, conn, table):
        self._c, self.table, self.fired = conn, table, False
    def __getattr__(self, k): return getattr(self._c, k)
    def cursor(self):
        cur, outer = self._c.cursor(), self
        class Cur:
            def __getattr__(self, k): return getattr(cur, k)
            def executemany(self, sql, rows):
                if outer.table and outer.table in sql and not outer.fired:
                    outer.fired = True
                    raise RuntimeError(f"injected: connection lost during {outer.table} insert")
                return cur.executemany(sql, rows)
        return Cur()


# ---- port of bulk_load.rs (rules=mutations mirroring model.json controls) ----
def port(history, inp, rules):
    """history: list of ("load", graph, noindex, stop) / ("rebuild",); db: {(g,n): rec}; returns db and last stats."""
    db, stats = dict(history[0]), None
    for step in history[1:]:
        if step[0] == "rebuild":
            for k, r in db.items():
                db[k] = dict(r, node_ix=True, labels_ix=r["labels_ix"] if rules.get("rebuild_skips_labels") else True, props_ix=True)
            continue
        _, g, noindex, stop = step
        def exists(n):
            if rules.get("skip_across_graphs"): return any(k[1] == n for k in db)
            if rules.get("skip_sees_indexed_only"): return (g, n) in db and db[(g, n)]["node_ix"]
            return (g, n) in db
        def new(n):
            if rules.get("rerun_completes_stranded") and (g, n) in db and not db[(g, n)]["labels"] and not db[(g, n)]["props"]:
                return True
            return not exists(n)
        targets = [n for n in inp if new(n)]
        d0 = dict(db)
        for n in targets:
            db[(g, n)] = dict(node_ix=not noindex, labels=frozenset(), labels_ix=True, props=frozenset(), props_ix=True)
        if stop == "labels":
            if rules.get("phase1_not_committed"): db = d0
            stats = None; continue
        for n in targets:
            db[(g, n)] = dict(db[(g, n)], labels=frozenset(inp[n]["labels"]), labels_ix=not noindex)
        if stop == "props":
            stats = None; continue
        for n in targets:
            db[(g, n)] = dict(db[(g, n)], props=frozenset(inp[n]["props"]) | {"id"}, props_ix=not noindex)
        stats = {"nodes": len(targets), "labels": sum(len(inp[n]["labels"]) for n in targets),
                 "props": sum(len(inp[n]["props"]) + 1 for n in targets)}
    return db, stats


def view(db, g, n, rules):
    r = db.get((g, n))
    if r is None or not (r["node_ix"] or rules.get("reader_ignores_index")): return None
    return {"labels": sorted(r["labels"]) if r["labels_ix"] else [], "props": sorted(r["props"]) if r["props_ix"] else []}


def observe(e, n, g):
    x = e.get_node(n, graph=g)
    if x is None: return None
    keys = sorted({"id" if k == "p_id" else k for k in x if k not in ("id", "labels")})
    return {"labels": sorted(x.get("labels", [])), "props": keys}


def main():
    from iris_vector_graph.bulk_loader import BulkLoader
    t0 = time.time()
    c = runtime.connect(); e = runtime.engine(c)
    graph = f"blg{TAG}"
    RULES = ["phase1_not_committed", "rerun_completes_stranded", "skip_sees_indexed_only", "skip_across_graphs",
             "reader_ignores_index", "rebuild_skips_labels"]
    cells, mism, sens = [], [], {r: 0 for r in RULES}
    domain = list(itertools.product([False, True], ["done", "labels", "props"], [None, False, True], [False, True], [False, True]))
    for i, (ni1, stop, rerun, rebuild, seeded) in enumerate(domain):
        a, b, L = f"bl{TAG}h{i}a", f"bl{TAG}h{i}b", f"BL{TAG}"
        inp = {a: {"labels": [L], "props": ["p"]}, b: {"labels": [L], "props": ["p"]}}
        rows = [(a, {"namespace": L, "p": 1}), (b, {"namespace": L, "p": 2})]
        db0 = {}
        if seeded:
            e.create_node(a, labels=[L], properties={"p": 0})
            db0[("", a)] = dict(node_ix=True, labels=frozenset([L]), labels_ix=True, props=frozenset(["id", "p"]), props_ix=True)
        history = [db0, ("load", graph, ni1, stop)]
        conn = FailAt(c, {"done": None, "labels": "rdf_labels", "props": "rdf_props"}[stop])
        first_err = None
        try:
            BulkLoader(conn, graph=graph).load_nodes(rows, use_noindex=ni1)
        except Exception as x:
            first_err = f"{type(x).__name__}: {str(x)[:160]}"
        second = None
        if rerun is not None:
            history.append(("load", graph, rerun, "done"))
            second = BulkLoader(c, graph=graph).load_nodes(rows, use_noindex=rerun)
            second = {k: second[k] for k in ("nodes", "labels", "props")}
        if rebuild:
            history.append(("rebuild",)); BulkLoader(c).rebuild_all_indices()
        got = {"a": observe(e, a, graph), "b": observe(e, b, graph), "rerun_stats": second,
               "default_a": observe(e, a, None) if seeded else None, "first_raised": first_err is not None}
        db, st = port(history, inp, {})
        want = {"a": view(db, graph, a, {}), "b": view(db, graph, b, {}), "rerun_stats": st if rerun is not None else None,
                "default_a": view(db, "", a, {}) if seeded else None, "first_raised": stop != "done"}
        cell = {"history": [ni1, stop, rerun, rebuild, seeded], "first_error": first_err, "fault_fired": conn.fired,
                "observed": got, "expected": want}
        cells.append(cell)
        if got != want or (stop != "done" and not conn.fired): mism.append(cell)
        for r in RULES:
            dbm, stm = port(history, inp, {r: True})
            alt = {"a": view(dbm, graph, a, {r: True}), "b": view(dbm, graph, b, {r: True}),
                   "rerun_stats": stm if rerun is not None else None,
                   "default_a": view(dbm, "", a, {r: True}) if seeded else None, "first_raised": stop != "done"}
            if alt != got: sens[r] += 1
    # bug-plt-012 (iteration 31): namespace W37 whose IVG Schema is Kg2 (set up by iteration-31/schema_probe.py)
    import iris.dbapi
    from iris_vector_graph.engine import IRISGraphEngine
    from tests import conftest as fx
    w = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace="W37", username="_SYSTEM", password="SYS")
    assert fx.container_hostname_matches(fx.probe_instance_hostname(w), fx.docker_container_hostname(runtime.NAME), fx.docker_container_id(runtime.NAME))
    ew = IRISGraphEngine(w, embedding_dimension=768, schema_prefix="Kg2", native_cypher=False)
    schema_cells = []
    for label, schema, noindex in [("S1 default schema", None, False), ("S2 Kg2 indexed", "Kg2", False), ("S3 Kg2 noindex + rebuild", "Kg2", True)]:
        n = f"bls{TAG}{label[:2]}"
        L = BulkLoader(w) if schema is None else BulkLoader(w, schema=schema)
        try:
            L.load_nodes([(n, {"namespace": "BLS", "p": 1})], use_noindex=noindex); raised = False
        except Exception:
            raised = True
        rb = L.rebuild_all_indices() if (noindex and not raised) else None
        readable = ew.get_node(n) is not None
        exp = {"S1 default schema": (True, False, None), "S2 Kg2 indexed": (False, True, None), "S3 Kg2 noindex + rebuild": (False, False, False)}[label]
        got = (raised, readable, None if rb is None else any(rb.values()))
        cell = {"history": label, "observed": {"raised": raised, "readable": readable, "rebuild_any_true": got[2]}, "expected": list(exp)}
        schema_cells.append(cell); cells.append(cell)
        if got != exp: mism.append(cell)
        if label.startswith("S1") and not got[0] is False: sens["default_schema_follows_namespace"] = sens.get("default_schema_follows_namespace", 0) + 1
        if label.startswith("S3") and not got[1]: sens["rebuild_follows_schema"] = sens.get("rebuild_follows_schema", 0) + 1
    w.close()
    c.close()
    body = {"kind": "binding", "model": "bulk_load", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": RUN, "graph": graph,
            "verdict": "AGREES" if not mism else "DISAGREES", "histories": len(cells), "comparisons": 5 * (len(cells) - 3) + 3 * 3,
            "mismatches": mism, "sensitivities_detected_histories": sens,
            "all_sensitivities_detected": all(v > 0 for v in sens.values()), "cells": cells,
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "bulk_load.rs", HERE / "model.json"]},
                       **{q: sha(Path(runtime.PIN) / q) for q in ["iris_vector_graph/bulk_loader.py", "iris_vector_graph/_engine/nodes_edges.py"]}},
            "scope": "Actual BulkLoader.load_nodes, rebuild_all_indices and get_node on IRIS 2026.1 (pin 3eaa79cf), one batch per "
                     "phase, two fresh nodes per history, skip_existing=True. Interruptions injected at the first label or "
                     "property executemany. load_edges, endpoint registration, Cypher readers and duplicate-vs-refusal "
                     "classification by error text are outside this binding. Three schema histories run in namespace W37 (IVG Schema Kg2)."}
    out = REPO / ".g5/Verus_verification/results/bulk_load" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True); (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "histories", "comparisons", "all_sensitivities_detected",
                                           "sensitivities_detected_histories", "elapsed_s")}))
    for m in mism[:5]: print("MISMATCH", json.dumps(m, default=str)[:700])


if __name__ == "__main__":
    main()
