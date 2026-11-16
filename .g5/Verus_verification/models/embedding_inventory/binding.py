"""embedding_inventory binding: the actual engine report and the actual CLI JSON on the run-isolated retest fixture,
compared with the model's report built from the engine's route rows and an independent read of the graphs that have
nodes (SELECT DISTINCT over Graph_KG.nodes). Two states: before and after a new named graph gets its first embedding.
Three port mutations mirror the controls. Ordinary data, fixture only."""
import hashlib, json, os, subprocess, sys, time
from dataclasses import asdict
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("EI_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def port(routes, graphs, m):
    routed = {r["graph_id"] for r in routes}
    extra = [g for g in graphs if (True if m.get("every_graph_gets_empty_row") else g not in routed)]
    if m.get("omit_unrouted_graphs"): extra = []
    empties = [{"graph_id": g, "table_name": ("?" if m.get("empty_row_names_a_table") else None), "row_count": 0, "index_state": "absent"} for g in extra]
    rows = [{k: r[k] for k in ("graph_id", "table_name", "row_count", "index_state")} for r in routes] + empties
    return sorted(rows, key=lambda r: (r["graph_id"], r["table_name"] or "")), sum(1 for r in rows if r["table_name"])
def cli():
    env = dict(os.environ, IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE="USER", IRIS_USERNAME="_SYSTEM", IRIS_PASSWORD="SYS")
    p = subprocess.run([sys.executable, "-B", "-c", "from iris_vector_graph.cli import main; main()", "embeddings", "inventory", "--json-output"],
                       capture_output=True, text=True, env=env, cwd=str(runtime.PIN), timeout=300)
    return json.loads(p.stdout)
def main():
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c)
    MUTS = ["omit_unrouted_graphs", "every_graph_gets_empty_row", "empty_row_names_a_table"]
    cells, mism, sens = [], [], {m: 0 for m in MUTS}
    g = f"eib{TAG}"
    e.create_node(f"eib{TAG}n1", graph=g)
    def state(label):
        rows = [asdict(r) for r in e.embedding_inventory()]
        cur = c.cursor(); cur.execute("SELECT DISTINCT COALESCE(graph_id, '') FROM Graph_KG.nodes"); graphs = sorted(r[0] for r in cur.fetchall()); cur.close()
        got = sorted(({k: r[k] for k in ("graph_id", "table_name", "row_count", "index_state")} for r in rows), key=lambda r: (r["graph_id"], r["table_name"] or ""))
        payload = cli()
        routes = [r for r in rows if r["table_name"]]
        want, want_count = port(routes, graphs, {})
        cli_rows = sorted(({k: r[k] for k in ("graph_id", "table_name", "row_count", "index_state")} for r in payload["inventory"]), key=lambda r: (r["graph_id"], r["table_name"] or ""))
        cell = {"state": label, "graphs_with_nodes": graphs, "engine_rows": got, "expected_rows": want, "cli_rows_equal_engine": cli_rows == got,
                "cli_routed_tables": payload["routed_tables"], "expected_routed_tables": want_count}
        cells.append(cell)
        if got != want or cli_rows != got or payload["routed_tables"] != want_count: mism.append(cell)
        for m in MUTS:
            w, n = port(routes, graphs, {m: True})
            if w != got or n != payload["routed_tables"]: sens[m] += 1
    state("new graph, no embedding")
    e.store_embedding(f"eib{TAG}n1", [0.03] * 768, graph=g)
    state("after its first embedding")
    c.close()
    body = {"kind": "binding", "model": "embedding_inventory", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES", "states": len(cells), "comparisons": 3 * len(cells), "mismatches": mism,
            "sensitivities_detected_states": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()), "cells": cells,
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "embedding_inventory.rs", HERE / "model.json"]},
                       **{q: sha(Path(runtime.PIN) / q) for q in ["iris_vector_graph/_engine/schema.py", "iris_vector_graph/cli.py"]}},
            "scope": "Actual SchemaMixin.embedding_inventory and `ivg embeddings inventory --json-output` on IRIS 2026.1 (pin 3eaa79cf); "
                     "route rows taken from the engine's report (registry, counts and index state not re-derived); the set of graphs "
                     "with nodes read independently. Two states."}
    out = REPO / ".g5/Verus_verification/results/embedding_inventory" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True); (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "states", "comparisons", "all_sensitivities_detected", "sensitivities_detected_states", "elapsed_s")}))
    for x in mism: print("MISMATCH", json.dumps(x, default=str)[:600])
if __name__ == "__main__":
    main()
