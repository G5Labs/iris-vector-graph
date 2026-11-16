"""write_routing binding: actual engine calls inside a caller's transaction on the run-isolated retest fixture, compared
with a port of write_routing.rs.

Domain: engine {on the caller's connection, from_connect} x call {create_node+create_edge, create_edge_temporal (stores and marked row observed separately),
purge_before (retired nodes and killed stores), set_temporal_structural(False)} x how the caller opened its transaction {SQL START TRANSACTION, driver
autocommit off} x how it ends {commit, rollback}: 32 histories, each read afterwards on a separate observer
connection. Plus 4 loader-refusal histories: {START TRANSACTION, autocommit off} x {nothing written, after an engine
write}, observing whether BulkLoader.load_nodes refuses. Six port mutations mirror the model's controls.
The failed-write case (theorem_failed_write_keeps_caller_work) is not exercised here. Ordinary data, fixture only."""
import hashlib, itertools, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(Path(os.environ.get("IVG_RUNTIME_DIR", str(REPO / ".g5/uplift/consolidated/iteration-25")))))
import runtime  # noqa: E402
RUN = os.environ.get("WR_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
TAG = RUN.replace("T", "").replace("Z", "")[-8:]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---- port of write_routing.rs ----
STEPS = {"ordinary": "S", "temporal_edge": "GS", "purge": "SG", "policy": "G"}
def route(engine, op, m):
    native = "own" if engine == "from_connect" else "caller"
    if op == "temporal_edge": return native if m.get("temporal_on_own_connection") else "caller"
    if op == "purge": return "caller" if m.get("purge_on_caller_connection") else native
    if op == "policy": return native
    return "caller"
def kept(engine, op, start, end, m):
    """Per step of the call: is its effect kept after the caller's end?"""
    steps = STEPS[op]
    if op == "temporal_edge" and m.get("temporal_sql_first"): steps = "SG"
    if route(engine, op, m) == "own":
        return [end == "commit" if m.get("own_process_joins") else True for _ in steps]
    hold = start == "autocommit_off"
    tlevel = 1 if start == "sql" else 0
    if op == "ordinary":                                   # WriteTxn: the caller's level is opened first
        return [True if m.get("commit_ends_all_levels") else end == "commit" for _ in steps]
    out = []
    for k in steps:
        if tlevel == 0:
            if k == "S" and hold and not m.get("no_implicit_level"):
                tlevel = 1; out.append(end == "commit")
            else:
                out.append(True)
        else:
            out.append(end == "commit")
    return out
def refuses(start, wrote, m):
    if m.get("refuse_only_after_a_write"): return wrote
    return (start == "sql" or wrote)
MUTS = ["commit_ends_all_levels", "temporal_on_own_connection", "purge_on_caller_connection", "undo_ends_all_levels",
        "refuse_only_after_a_write", "own_process_joins", "temporal_sql_first", "no_implicit_level"]


def main():
    import iris
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.bulk_loader import BulkLoader
    from iris_vector_graph.errors import CallerTransactionOpenError
    from tests import conftest as fx
    t0 = time.time()
    c = runtime.connect(); C = runtime.engine(c)
    o = runtime.connect(); O = runtime.engine(o)
    F = IRISGraphEngine.from_connect("127.0.0.1", runtime.PORT, "USER", "_SYSTEM", "SYS", embedding_dimension=768, native_cypher=False)
    assert fx.container_hostname_matches(fx.probe_instance_hostname(F.conn), fx.docker_container_hostname(runtime.NAME),
                                         fx.docker_container_id(runtime.NAME))
    engines = {"caller_conn": C, "from_connect": F}

    def open_txn(eng, start):
        if start == "sql":
            cur = eng.conn.cursor(); cur.execute("START TRANSACTION"); cur.close()
        else:
            eng.conn.setAutoCommit(False)
    def end_txn(eng, start, end):
        if start == "sql":
            cur = eng.conn.cursor(); cur.execute("COMMIT" if end == "commit" else "ROLLBACK"); cur.close()
        else:
            (eng.conn.commit if end == "commit" else eng.conn.rollback)(); eng.conn.setAutoCommit(True)

    cells, mism, sens = [], [], {m: 0 for m in MUTS}
    for i, (ek, op, start, end) in enumerate(itertools.product(engines, ["ordinary", "temporal_edge", "purge", "policy"],
                                                                ["sql", "autocommit_off"], ["commit", "rollback"])):
        eng = engines[ek]; a, b, p = f"wr{TAG}h{i}a", f"wr{TAG}h{i}b", f"WR{TAG}H{i}"
        if op == "purge":
            O.create_edge_temporal(a, p, b, timestamp=1000 + i, weight=1.0)     # committed beforehand
        err = None
        open_txn(eng, start)
        try:
            if op == "ordinary":
                eng.create_node(a); eng.create_node(b); eng.create_edge(a, p, b)
            elif op == "temporal_edge":
                eng.create_edge_temporal(a, p, b, timestamp=2_000_000_000, weight=2.0)
            elif op == "purge":
                eng.purge_before(1001 + i)
            else:
                eng.set_temporal_structural(p, False)
        except Exception as x:
            err = f"{type(x).__name__}: {str(x)[:200]}"
        end_txn(eng, start, end)
        def edges():
            r = O.execute_cypher(f"MATCH (x)-[r:{p}]->(y) RETURN count(r)")
            return (r.rows if hasattr(r, "rows") else r["rows"])[0][0]
        window = len(O.get_edges_in_window(a, p, 0, 2 ** 31))
        if op == "ordinary":
            effect = [edges() == 1 and O.get_node(a) is not None]
        elif op == "temporal_edge":                      # step G: temporal stores; step S: marked row and nodes
            effect = [window == 1, edges() == 1 and O.get_node(a) is not None]
        elif op == "purge":                              # step S: endpoint nodes retired; step G: stores killed
            effect = [O.get_node(a) is None, window == 0]
        else:
            effect = [O.get_temporal_structural(p) is False]
        want = kept(ek, op, start, end, {})
        cell = {"engine": ek, "op": op, "start": start, "end": end, "error": err, "effect_kept": effect, "expected": want}
        cells.append(cell)
        if effect != want or err: mism.append(cell)
        for m in MUTS:
            if kept(ek, op, start, end, {m: True}) != effect: sens[m] += 1

    for start, wrote in itertools.product(["sql", "autocommit_off"], [False, True]):
        y = f"wr{TAG}ref{start}{int(wrote)}"
        open_txn(C, start)
        if wrote: C.create_node(y + "w")
        try:
            BulkLoader(C.conn).load_nodes([(y, {"namespace": "WR"})], use_noindex=False); refused = False
        except CallerTransactionOpenError:
            refused = True
        end_txn(C, start, "rollback")
        want = refuses(start, wrote, {})
        cell = {"refusal": True, "start": start, "caller_wrote": wrote, "refused": refused, "expected": want,
                "loaded_after_rollback": O.get_node(y) is not None}
        cells.append(cell)
        if refused != want or cell["loaded_after_rollback"] == refused: mism.append(cell)
        for m in MUTS:
            if refuses(start, wrote, {m: True}) != refused: sens[m] += 1

    for x in (c, o, F.conn):
        try: x.close()
        except Exception: pass
    # undo_ends_all_levels concerns a failed write, not exercised natively: reported, not required
    required = [m for m in MUTS if m != "undo_ends_all_levels"]
    body = {"kind": "binding", "model": "write_routing", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES",
            "histories": len(cells), "comparisons": sum(len(c["effect_kept"]) if "effect_kept" in c else 1 for c in cells), "mismatches": mism,
            "sensitivities_detected_histories": sens,
            "all_required_sensitivities_detected": all(sens[m] > 0 for m in required),
            "not_exercised": ["undo_ends_all_levels (a write that fails inside the caller's transaction)"],
            "cells": cells, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "write_routing.rs", HERE / "model.json"]},
                       **{q: sha(Path(runtime.PIN) / q) for q in ["iris_vector_graph/_write_txn.py", "iris_vector_graph/engine.py",
                          "iris_vector_graph/_engine/temporal.py", "iris_vector_graph/stores/iris_sql_store.py",
                          "iris_vector_graph/bulk_loader.py"]}},
            "scope": "Actual engine calls on IRIS 2026.1 (pin 3eaa79cf), engine on the caller's connection and from_connect, "
                     "caller transaction by SQL START TRANSACTION or driver autocommit off; effects read after the caller's "
                     "commit or rollback on a separate connection. Declared adjacency index. Other engine._iris_obj writers "
                     "(rebuild_temporal_latest, drop/backfill structural rows, BM25, vector, ledger) are not exercised."}
    out = REPO / ".g5/Verus_verification/results/write_routing" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True); (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "histories", "all_required_sensitivities_detected",
                                           "sensitivities_detected_histories", "elapsed_s")}))
    for m in mism[:6]: print("MISMATCH", json.dumps(m, default=str)[:500])


if __name__ == "__main__":
    main()
