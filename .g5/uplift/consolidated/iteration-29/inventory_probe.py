"""W34: embedding_inventory and `ivg embeddings inventory --json-output` (run-isolated retest fixture only)."""
import json, os, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W34_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def rows(e):
    from dataclasses import asdict
    return [asdict(r) for r in e.embedding_inventory()]
def cli():
    env = dict(os.environ, IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE="USER", IRIS_USERNAME="_SYSTEM", IRIS_PASSWORD="SYS")
    p = subprocess.run([sys.executable, "-B", "-c", "from iris_vector_graph.cli import main; main()", "embeddings", "inventory", "--json-output"],
                       capture_output=True, text=True, env=env, cwd=str(runtime.PIN), timeout=300)
    txt = subprocess.run([sys.executable, "-B", "-c", "from iris_vector_graph.cli import main; main()", "embeddings", "inventory"],
                         capture_output=True, text=True, env=env, cwd=str(runtime.PIN), timeout=300)
    try: payload = json.loads(p.stdout)
    except Exception: payload = {"raw": p.stdout[-800:], "stderr": p.stderr[-800:], "rc": p.returncode}
    return {"rc": p.returncode, "payload": payload, "text_tail": txt.stdout.strip().splitlines()[-3:], "text_rc": txt.returncode}
def pick(rs, g): return [r for r in rs if r["graph_id"] == g]
def main():
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "steps": {}}
    g = f"w34g{TAG}"
    r0 = rows(e); out["steps"]["I1_start"] = {"default": pick(r0, ""), "n": len(r0), "graphs": sorted({r["graph_id"] for r in r0})}
    r0b = rows(e); out["steps"]["I5_read_twice_same"] = r0 == r0b
    e.create_node(f"w34{TAG}n1", graph=g) if "graph" in e.create_node.__code__.co_varnames else e.execute_cypher(f"USE GRAPH '{g}' CREATE (:W34 {{id: 'w34{TAG}n1'}})")
    r1 = rows(e); out["steps"]["I2_graph_no_route"] = pick(r1, g); out["steps"]["I2_cli"] = cli()
    before = sum(r["row_count"] for r in pick(r1, "") if r["table_name"] == "kg_NodeEmbeddings")
    e.create_node(f"w34{TAG}d1"); e.store_embedding(f"w34{TAG}d1", [0.01] * 768)
    r2 = rows(e); after = sum(r["row_count"] for r in pick(r2, "") if r["table_name"] == "kg_NodeEmbeddings")
    out["steps"]["I3_default_count"] = {"before": before, "after": after}
    try:
        e.store_embedding(f"w34{TAG}n1", [0.02] * 768, graph=g); out["steps"]["I4_store"] = "ok"
    except Exception as x:
        out["steps"]["I4_store"] = f"{type(x).__name__}: {str(x)[:300]}"
    r3 = rows(e); out["steps"]["I4_graph_rows"] = pick(r3, g); out["steps"]["I4_cli"] = cli()
    c.close(); path = HERE / f"inventory-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, v in out["steps"].items(): print("==", k, json.dumps(v, default=str)[:900])
if __name__ == "__main__":
    main()
