"""bm25_counts binding: actual Graph.KG.BM25Index writes on the run-isolated fixture; after every operation the stored
^BM25Idx df/N/doc/vocab_size are read over the Native API and compared with (a) a port of the model's pointwise update
and (b) a recount from the documents. Four port mutations mirror the controls. Ordinary data, fixture only."""
import hashlib, json, os, random, re, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(Path(os.environ.get("IVG_RUNTIME_DIR", str(REPO / ".g5/uplift/consolidated/iteration-15")))))
import runtime  # noqa: E402
RUN = os.environ.get("BM_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
WORDS = ["graph", "node", "edge", "path", "vector", "index", "the", "and"]  # last two are stopwords
STOP = {"the", "and"}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def terms(t): return {w for w in re.split(r"[^a-z0-9]+", t.lower()) if w and w not in STOP}
def step(st, op, d, text, rules):
    docs, df, n = dict(st["docs"]), dict(st["df"]), st["n"]
    def remove():
        nonlocal n
        if d not in docs:
            if rules.get("absent_delete_decrements"): n -= 1
            return
        for t in docs.pop(d):
            if not rules.get("remove_keeps_df"): df[t] = df.get(t, 0) - 1
            if df.get(t, 0) <= 0: df.pop(t, None)
        n -= 1
    if op == "delete" or not rules.get("insert_without_remove"): remove()
    if op == "insert":
        ts = terms(text)
        if ts or rules.get("empty_text_indexed"):
            docs[d] = ts; n += 1
            for t in ts: df[t] = df.get(t, 0) + 1
    return {"docs": docs, "df": df, "n": n}
def main():
    from iris_vector_graph.engine import IRISGraphEngine
    import iris
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768); nat = iris.createIRIS(c)
    name = f"bmc{RUN}".lower(); prop = f"bmcp{RUN}".lower()
    e.create_node(f"bmc{RUN}seed", labels=["BMC"], properties={prop: "graph node"})
    e.bm25_build(name, [prop])
    rng = random.Random(20261116); ids = [f"bmc{RUN}seed"] + [f"bmc{RUN}d{i}" for i in range(5)]
    ops = []
    for _ in range(60):
        d = rng.choice(ids)
        if rng.random() < 0.25: ops.append(("delete", d, None))
        else: ops.append(("insert", d, " ".join(rng.choice(WORDS) for _ in range(rng.randint(0, 4)))))
    ops.append(("delete", f"bmc{RUN}absent", None))
    st = {"docs": {f"bmc{RUN}seed": {"graph", "node"}}, "df": {"graph": 1, "node": 1}, "n": 1}
    alts = {r: dict(st) for r in ["remove_keeps_df", "insert_without_remove", "empty_text_indexed", "absent_delete_decrements"]}
    cells, mism, sens = [], [], {r: 0 for r in alts}
    def stored():
        df = {}
        for w in WORDS:
            if nat.isDefined("^BM25Idx", name, "df", w): df[w] = int(nat.get("^BM25Idx", name, "df", w))
        docs = {d for d in ids + [f"bmc{RUN}absent"] if nat.isDefined("^BM25Idx", name, "doc", d)}
        return {"df": df, "n": int(nat.get("^BM25Idx", name, "cfg", "N")), "docs": sorted(docs), "vocab_size": int(nat.get("^BM25Idx", name, "cfg", "vocab_size"))}
    for op, d, text in ops:
        if op == "insert": e.bm25_insert(name, d, text)
        else: e.bm25_delete(name, d)
        st = step(st, op, d, text, {})
        for r in alts: alts[r] = step(alts[r], op, d, text, {r: True})
        got = stored()
        recount = {}
        for ts in st["docs"].values():
            for t in ts: recount[t] = recount.get(t, 0) + 1
        want = {"df": st["df"], "n": st["n"], "docs": sorted(st["docs"]), "vocab_size": len(recount)}
        cell = {"op": op, "doc": d, "text": text, "observed": got, "expected": want, "recount_df": recount,
                "consistent_with_recount": got["df"] == recount and got["n"] == len(st["docs"])}
        cells.append(cell)
        if got != want or not cell["consistent_with_recount"]: mism.append(cell)
        for r, a in alts.items():
            if {"df": {k: v for k, v in a["df"].items() if v > 0}, "n": a["n"], "docs": sorted(a["docs"])} != {k: got[k] for k in ("df", "n", "docs")}: sens[r] += 1
    e.bm25_drop(name); c.close()
    body = {"kind": "binding", "model": "bm25_counts", "fixture": runtime.NAME, "product_baseline": runtime.PRODUCT, "run": RUN,
            "verdict": "AGREES" if not mism else "DISAGREES", "operations": len(cells), "comparisons": 4 * len(cells), "mismatches": mism,
            "sensitivities_detected_operations": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "cells": cells, "seed": 20261116, "elapsed_s": None,
            "inputs": {str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "bm25_counts.rs", HERE / "model.json"]},
            "scope": "Actual Graph.KG.BM25Index Insert/Delete through bm25_insert/bm25_delete on IRIS 2026.1; stored globals read directly; "
                     "a seeded sequence of 61 operations over six documents and an eight-word vocabulary with two stopwords. "
                     "vocab_size is compared against a recount but is not part of the formal model."}
    out = REPO / ".g5/Verus_verification/results/bm25_counts" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True); (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "operations", "comparisons", "all_sensitivities_detected", "sensitivities_detected_operations")}))
    for m in mism[:5]: print("MISMATCH", json.dumps(m, default=str)[:500])
if __name__ == "__main__":
    main()
