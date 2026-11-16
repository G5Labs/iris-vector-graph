"""W38: the same Cypher through execute_cypher and three HTTP routes, in-process (FastAPI TestClient; no port opened).
Run-isolated retest fixture only."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W38_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def main():
    os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE="USER", IRIS_USERNAME="_SYSTEM", IRIS_PASSWORD="SYS")
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"): os.environ.pop(k, None)
    c = runtime.connect(); e = runtime.engine(c)
    vals = {"i": 7, "f": 7.5, "s": "7", "b": True, "l": [1, 2]}
    for k, v in vals.items(): e.create_node(f"h{TAG}{k}", labels=[f"H{TAG}"], properties={"p": v})
    e.create_node(f"h{TAG}n", labels=[f"H{TAG}"])
    e.create_node(f"h{TAG}ra"); e.create_node(f"h{TAG}rb"); e.create_edge(f"h{TAG}ra", "HR", f"h{TAG}rb", qualifiers={"w": 1.5})
    queries = {
        "values": f"MATCH (x:H{TAG}) RETURN x.id AS id, x.p AS p ORDER BY id",
        "rel": f"MATCH (a {{id: 'h{TAG}ra'}})-[r:HR]->(b) RETURN r.w AS w",
        "agg": f"MATCH (x:H{TAG}) WHERE x.id IN ['h{TAG}i', 'h{TAG}f'] RETURN avg(x.p) AS a, sum(x.p) AS s, count(x) AS n",
        "big": "UNWIND range(1, 1200) AS i RETURN i",
    }
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    with TestClient(cypher_api.app) as client:
        for name, q in queries.items():
            r0 = e.execute_cypher(q); eng = {"columns": r0.columns, "rows": r0.rows, "n": len(r0.rows), "types": [[type(x).__name__ for x in row] for row in r0.rows[:6]]}
            a = client.post("/api/cypher", json={"query": q}); aj = a.json()
            t = client.post("/db/neo4j/tx/commit", json={"statements": [{"statement": q}]})
            try: tj = t.json()
            except Exception: tj = {"raw": t.text[:300]}
            v = client.post("/db/neo4j/query/v2", json={"statement": q}); vj = v.json()
            def rows_of(kind, j):
                try:
                    if kind == "api": return j["rows"]
                    if kind == "tx": return [d["row"] for d in j["results"][0]["data"]]
                    return j["data"]["values"]
                except Exception: return None
            case = {"engine": {"n": eng["n"], "rows_head": eng["rows"][:6], "types": eng["types"]},
                    "api": {"status": a.status_code, "n": len(rows_of("api", aj) or []), "rowCount": aj.get("rowCount") if isinstance(aj, dict) else None, "rows_head": (rows_of("api", aj) or [])[:6]},
                    "tx": {"status": t.status_code, "n": len(rows_of("tx", tj) or []), "errors": tj.get("errors") if isinstance(tj, dict) else None, "rows_head": (rows_of("tx", tj) or [])[:6]},
                    "v2": {"status": v.status_code, "n": len(rows_of("v2", vj) or []), "rows_head": (rows_of("v2", vj) or [])[:6]}}
            case["same_head_as_engine_json"] = all(json.loads(json.dumps(eng["rows"][:6], default=str)) == case[k]["rows_head"] for k in ("api", "tx", "v2"))
            out["cases"][name] = case
    c.close(); path = HERE / f"http-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, v in out["cases"].items(): print("==", k, json.dumps(v, default=str)[:700])
if __name__ == "__main__":
    main()
