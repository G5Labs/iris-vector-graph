"""W26 native probe: BM25 index build/insert/replace/delete and scores vs an owner-formula reference (fixture only)."""
import json, math, os, re, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W26_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
STOP = {"the", "and", "of", "a", "at", "for"}  # subset sufficient for this corpus (owner: 77 words)
def terms(t): return [w for w in re.split(r"[^0-9a-z]+", t.lower()) if w and w not in STOP]
def ref(docs, q, k1=1.5, b=0.75):
    d = {i: terms(t) for i, t in docs.items() if terms(t)}
    N = len(d); avg = sum(map(len, d.values())) / N if N else 0
    out = {}
    for i, ts in d.items():
        s = 0.0
        for qt in terms(q):
            df = sum(1 for x in d.values() if qt in x); tf = ts.count(qt)
            if tf: s += math.log(1 + (N - df + 0.5) / (df + 0.5)) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(ts) / avg))
        if s: out[i] = s
    return {"N": N, "avgdl": avg, "vocab": len({w for x in d.values() for w in x}), "scores": out}
def main():
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    prop = f"w26txt{RUN}".lower(); name = f"w26idx{RUN}".lower()
    docs = {"d1": "graph database graph", "d2": "graph theory", "d3": "The cat sat", "d4": "Graph-DB, fast!"}
    ids = {k: f"w26{RUN}{k}" for k in ["d1", "d2", "d3", "d4", "d5"]}
    for k, t in docs.items(): e.create_node(ids[k], labels=["W26"], properties={prop: t})
    log = []
    def snap(step, queries=("graph", "graph graph", "the", "theory")):
        info = e.bm25_info(name); r = {}
        for q in queries:
            got = e.bm25_search(name, q, k=10)
            r[q] = {"observed": {next(k for k, v in ids.items() if v == i): s for i, s in got},
                    "reference": ref(cur, q)["scores"]}
        rf = ref(cur, "")
        log.append({"step": step, "info": info, "reference_counts": {"N": rf["N"], "avgdl": rf["avgdl"], "vocab": rf["vocab"]}, "searches": r})
    cur = dict(docs)
    b = e.bm25_build(name, [prop]); log.append({"step": "build returned", "result": b}); snap("after build")
    e.bm25_insert(name, ids["d5"], "graph"); cur["d5"] = "graph"; snap("insert d5")
    e.bm25_insert(name, ids["d3"], "the and of"); cur["d3"] = "the and of"; snap("replace d3 with stopwords")
    e.bm25_delete(name, "nope-" + RUN); snap("delete absent")
    e.bm25_insert(name, ids["d1"], "theory"); cur["d1"] = "theory"; snap("replace d1")
    e.bm25_drop(name); c.close()
    path = HERE / f"bm25-observed-{RUN}.json"; path.write_text(json.dumps({"run": RUN, "fixture": runtime.NAME, "log": log}, indent=1, default=str) + "\n"); print(path)
    for s in log:
        if "info" not in s: print(s["step"], s["result"]); continue
        i, rc = s["info"], s["reference_counts"]
        print(s["step"], "| N", i.get("N"), rc["N"], "| avgdl", i.get("avgdl"), rc["avgdl"], "| vocab", i.get("vocab_size"), rc["vocab"])
        for q, x in s["searches"].items():
            o, rr = x["observed"], x["reference"]
            ok = set(o) == set(rr) and all(abs(o[k] - rr[k]) <= 1e-6 * max(1, abs(rr[k])) for k in o)
            print("   ", repr(q), "OK" if ok else "DIFF", {k: round(v, 6) for k, v in o.items()}, "" if ok else {k: round(v, 6) for k, v in rr.items()})
if __name__ == "__main__":
    main()
