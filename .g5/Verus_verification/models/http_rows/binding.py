"""http_rows binding: UNWIND queries of 999, 1000, 1001 and 1200 rows through execute_cypher and the three HTTP routes
(in-process FastAPI TestClient; no port opened), plus /api/cypher with limitRows 5 and 2000; compared with a port of
http_rows.rs. Three port mutations mirror the controls. Fixture only."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("HR_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def kept(n, limit, m):
    if m.get("no_limit"): return n
    if m.get("cut_one_short"): return n if n < limit else limit - 1
    return min(n, limit)
def main():
    os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE="USER", IRIS_USERNAME="_SYSTEM", IRIS_PASSWORD="SYS")
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"): os.environ.pop(k, None)
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c)
    MUTS = ["no_limit", "api_counts_total", "cut_one_short"]
    cells, mism, sens = [], [], {m: 0 for m in MUTS}
    with TestClient(cypher_api.app) as client:
        for n, limit_rows in [(999, None), (1000, None), (1001, None), (1200, None), (20, 5), (1200, 2000)]:
            q = f"UNWIND range(1, {n}) AS i RETURN i"
            eng = len(e.execute_cypher(q).rows)
            body = {"query": q} if limit_rows is None else {"query": q, "limitRows": limit_rows}
            a = client.post("/api/cypher", json=body).json()
            t = client.post("/db/neo4j/tx/commit", json={"statements": [{"statement": q}]}).json()
            v = client.post("/db/neo4j/query/v2", json={"statement": q}).json()
            got = {"engine": eng, "api": len(a["rows"]), "api_rowCount": a["rowCount"], "tx": len(t["results"][0]["data"]), "v2": len(v["data"]["values"]),
                   "api_first_last": [a["rows"][0][0], a["rows"][-1][0]] if a["rows"] else None}
            lim = 1000 if limit_rows is None else limit_rows
            def predict(m):
                ka = kept(n, lim, m)
                return {"engine": n, "api": ka, "api_rowCount": (n if m.get("api_counts_total") else ka), "tx": kept(n, 1000, m), "v2": kept(n, 1000, m),
                        "api_first_last": [1, ka] if ka else None}
            want = predict({})
            cell = {"rows": n, "limitRows": limit_rows, "observed": got, "expected": want}
            cells.append(cell)
            if got != want: mism.append(cell)
            for m in MUTS:
                if predict({m: True}) != got: sens[m] += 1
    c.close()
    out = {"kind": "binding", "model": "http_rows", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT, "run": RUN,
           "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(cells), "comparisons": 6 * len(cells), "mismatches": mism,
           "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()), "cells": cells,
           "elapsed_s": round(time.time() - t0, 1),
           "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "http_rows.rs", HERE / "model.json"]},
                      "iris_vector_graph/cypher_api.py": sha(Path(runtime.PIN) / "iris_vector_graph/cypher_api.py")},
           "scope": "Actual cypher_api routes in-process (FastAPI TestClient, no listener) over the fixture engine; row counts and ends of answers. "
                    "Bolt and the sdk client are outside."}
    d = REPO / ".g5/Verus_verification/results/http_rows" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(out, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: out[k] for k in ("verdict", "cases", "comparisons", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism: print("MISMATCH", json.dumps(x)[:500])
if __name__ == "__main__":
    main()
