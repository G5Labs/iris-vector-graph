"""sort_key binding: the product's Graph_KG.CY_SORT_KEY on the run-isolated fixture vs the model's rank, plus actual
ORDER BY on nodes and relationships. Provider $IsValidNum is approximated by a declared regex and checked here.
Ordinary data on the identity-checked fixture only."""
import hashlib, json, os, re, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(Path(os.environ.get("IVG_RUNTIME_DIR", str(REPO / ".g5/uplift/consolidated/iteration-15")))))
import runtime  # noqa: E402
TEXTS = ["9", "10", "2.5", "-3", "+1", ".5", "1e5", "1.", "007", " 1", "1 ", "abc", "B", "x9", "true", "false", "True",
         "NaN", "nan", "", "Infinity", "-", "1,000", "0x10", "$5", "5%"]
NUM_RE = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def is_valid_num(v): return bool(NUM_RE.match(v))  # provider guess for $IsValidNum
def rank(v, t="x", rules=None):
    rules = rules or {}
    if v is None or t == "null": return "a" if rules.get("null_first") else "z"
    if v == "": return "z" if rules.get("empty_string_as_null") else "l"
    if t == "string": return "l"
    if t == "boolean": return "m"
    if t == "x" and v in ("true", "false"): return "p" if rules.get("boolean_after_number") else "m"
    if t == "x" and v == "NaN": return "o"
    if t == "number" or (t == "x" and is_valid_num(v) and not rules.get("untyped_number_as_string")): return "n"
    return "l"
def main():
    start = time.monotonic(); c = runtime.connect(); cur = c.cursor(); cells = []
    for v in TEXTS:
        cur.execute("SELECT Graph_KG.CY_SORT_KEY(?, 'x')", [v]); key = cur.fetchone()[0]
        cells.append({"text": v, "key": key, "observed_rank": key[:1], "expected_rank": rank(v)})
    cur.execute("SELECT Graph_KG.CY_SORT_KEY(NULL, 'x')"); nk = cur.fetchone()[0]
    cells.append({"text": None, "key": nk, "observed_rank": (nk or "")[:1], "expected_rank": rank(None)})
    for v, t in [("9", "string"), ("true", "boolean"), ("9", "number")]:
        cur.execute("SELECT Graph_KG.CY_SORT_KEY(?, ?)", [v, t]); key = cur.fetchone()[0]
        cells.append({"text": v, "type": t, "key": key, "observed_rank": key[:1], "expected_rank": rank(v, t)})
    # the native executor's key: Graph.KG.Cypher.SortKey.Key, called directly over the Native API
    import iris
    native = iris.createIRIS(c)
    for x in cells:
        if x["text"] is None:
            continue
        k = native.classMethodValue("Graph.KG.Cypher.SortKey", "Key", x["text"], x.get("type", "x"))
        x["class_key"] = k
        x["class_rank"] = (k or "")[:1]
        # Native API transport: an empty text arrives as ObjectScript "" (the native executor's argument), i.e. rank(None)
        x["class_expected_rank"] = rank(None) if x["text"] == "" else rank(x["text"], x.get("type", "x"))
        x["class_equals_sql"] = (k == x["key"])
    cur.close(); c.close()
    mism = [x for x in cells if x["observed_rank"] != x["expected_rank"] or ("class_rank" in x and x["class_rank"] != x["class_expected_rank"])]
    sens = {r: sum(1 for x in cells if rank(x["text"], x.get("type", "x"), {r: True}) != x["observed_rank"])
            for r in ["untyped_number_as_string", "boolean_after_number", "empty_string_as_null", "null_first"]}
    body = {"kind": "binding", "model": "sort_key", "fixture": runtime.NAME, "product_baseline": runtime.PRODUCT,
            "verdict": "AGREES" if not mism else "DISAGREES", "cells": cells, "comparisons": len(cells) + sum(1 for x in cells if "class_rank" in x), "class_key_differs_from_sql": [x for x in cells if x.get("class_equals_sql") is False], "mismatches": mism,
            "sensitivities_detected_cells": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "elapsed_s": time.monotonic() - start,
            "inputs": {str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "sort_key.rs", HERE / "model.json"]},
            "scope": "Actual Graph_KG.CY_SORT_KEY SQL function (the SQL path's sort key; SortKey.Key is held to the same code by the "
                     "product's test_257) on IRIS 2026.1; ordinary scalar texts; $IsValidNum approximated by a declared regex."}
    out = REPO / ".g5/Verus_verification/results/sort_key" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True); (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "comparisons", "all_sensitivities_detected", "sensitivities_detected_cells")}))
    for m in mism: print("MISMATCH", m)
    print(out / "receipt.json")
if __name__ == "__main__":
    main()
