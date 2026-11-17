"""Binding for percentile (W59, iteration 53) on the run-isolated continuation fixture.

Cypher percentileDisc / percentileCont over literal UNWIND lists (with literal p), over stored node values in a fresh
graph (with a $p parameter, nulls and no rows), and the SQL functions Graph_KG.Percentile_PDISC / PCONT directly.
Expected answers come from a Python port of percentile.rs (floor((n - 1) p) for Disc; interpolation for Cont; null for
no values; NumberOutOfRange outside [0, 1]); the lists are sorted by the port (SortArray is a delegate) and nulls
are left out before the call (premise P-AGG-NULL, JSON_ARRAYAGG). Values compared as floats with tolerance 1e-9 (the
reader casts to DOUBLE). One port mutation per control; one observation is tampered. A list parameter
(`UNWIND $xs`) is not used: with this driver it fails before reaching the function (bug-cyp-125).

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/percentile/binding.py)
"""
import hashlib, json, math, os, sys, time
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); T = RUN[-7:-1]
P = f"i53s_{T}_"; G = f"i53spg{T}"
TOL = 1e-9
MUTS = ["disc-nearest-rank", "cont-floor-only", "no-range-check", "empty-is-zero",
        "disc-keeps-input-kind", "null-param-refused", "literal-null-refused"]
# iteration 56: answer kinds (bug-cyp-147) and the p argument (bug-cyp-148) over [10, 20, 30]
KINDS = {"int": [10, 20, 30, 40], "float": [1.5, 2.5, 3.5]}
PARGS = {"param_num": ("Param", "Num", 0.5), "param_null": ("Param", "Null", None), "param_numtext": ("Param", "NumText", "0.5"),
         "param_othertext": ("Param", "OtherText", "x"), "param_true": ("Param", "Bool", True), "param_false": ("Param", "Bool", False),
         "missing": ("Missing", None, None), "lit_null": ("Lit", "Null", None), "lit_num": ("Lit", "Num", 0.5)}


def answer_kind(fn, input_kind, m):
    if fn == "cont":
        return "float"
    return input_kind if m.get("disc-keeps-input-kind") else "float"


def as_built_p(src, kind, value, m):
    """percentile.rs as_built_p, and the value the run answers over [10, 20, 30] (floor((n - 1) p))."""
    xs = [10.0, 20.0, 30.0]
    if src == "Missing":
        return "Undefined"
    if src == "Lit":
        if kind == "Null":
            return "Refused" if m.get("literal-null-refused") else ["run", xs[0]]
        return ["run", xs[int(2 * float(value))]]
    if kind == "Null":
        return "Refused" if m.get("null-param-refused") else "RawTypeError"
    if kind == "OtherText":
        return "RawValueError"
    return ["run", xs[int(2 * float(value))]]
LISTS = {"four": [10, 20, 30, 40], "three": [10, 20, 30], "ten": list(range(1, 11)), "unsorted": [30, 10, 40, 20],
         "dups": [10, 10, 20, 30], "neg": [-5, 3, -1], "one": [7], "floats": [1.5, 2.5, 3.5], "nulls": [10, None, 30]}
PS = ["0", "0.25", "1/3", "0.5", "0.6", "0.75", "0.9", "0.95", "1"]
BAD = ["1.5", "-0.1"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def frac(p):
    """The exact value of the double the product receives (1/3 arrives as 0.33333333333333331483...)."""
    return Fraction(float(Fraction(p)))


# ------------------------------------------------------------------ port of percentile.rs
def pdisc(xs, p, m):
    if not (0 <= p <= 1) and not m.get("no-range-check"):
        return "OutOfRange"
    xs = sorted(x for x in xs if x is not None)
    n = len(xs)
    if n == 0:
        return None
    if m.get("disc-nearest-rank"):
        c = math.ceil(p * n); i = 0 if c <= 0 else c - 1
    else:
        i = math.floor((n - 1) * p)
    i = max(0, min(i, n - 1))
    return float(xs[i])


def pcont(xs, p, m):
    if not (0 <= p <= 1):
        return "OutOfRange"
    xs = sorted(x for x in xs if x is not None)
    n = len(xs)
    if n == 0:
        return 0.0 if m.get("empty-is-zero") else None
    pos = (n - 1) * p
    lower = math.floor(pos)
    if lower >= n - 1:
        return float(xs[n - 1])
    if m.get("cont-floor-only"):
        return float(xs[lower])
    return float(Fraction(xs[lower]) + (pos - lower) * (Fraction(xs[lower + 1]) - Fraction(xs[lower])))


def main():
    t0 = time.time()
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768); cur = c.cursor()
    got = {}

    def cy(q, params=None):
        r = e.execute_cypher(q, params or {})
        if getattr(r, "error", None):
            return "OutOfRange" if "NumberOutOfRange" in str(r.error) else f"error:{str(r.error)[:120]}"
        return [None if v is None else float(v) for v in r.rows[0]] if r.rows else "norows"

    def lit(xs):
        return "[" + ", ".join("null" if x is None else repr(x) for x in xs) + "]"

    for ln, xs in LISTS.items():
        for ps in PS + BAD:
            pv = float(frac(ps))
            got[f"unwind:{ln}:{ps}"] = cy(f"UNWIND {lit(xs)} AS x RETURN percentileDisc(x, {pv!r}) AS d, percentileCont(x, {pv!r}) AS c")
    # stored values in a fresh graph, $p parameter, a null value and an empty match
    for i, v in enumerate([10, 20, None, 30, 40]):
        e.create_node(f"{P}v{i}", labels=["I53SV"], properties={} if v is None else {"v": v}, graph=G)
    for ps in PS + BAD:
        got[f"match:{ps}"] = cy(f"USE GRAPH '{G}' MATCH (n:I53SV) RETURN percentileDisc(n.v, $p) AS d, percentileCont(n.v, $p) AS c",
                                {"p": float(frac(ps))})
    got["match:none"] = cy(f"USE GRAPH '{G}' MATCH (n:I53SV) WHERE n.v > 100 RETURN percentileDisc(n.v, 0.5) AS d, percentileCont(n.v, 0.5) AS c")
    # iteration 56: answer kinds through Cypher (UNWIND literals and stored integers), and the p argument
    for kn, xs in KINDS.items():
        r = e.execute_cypher(f"UNWIND {lit(xs)} AS x RETURN percentileDisc(x, 0.5) AS d, percentileCont(x, 0.5) AS c")
        got[f"kind:unwind:{kn}"] = [type(v).__name__ for v in r.rows[0]]
    r = e.execute_cypher(f"USE GRAPH '{G}' MATCH (n:I53SV) RETURN percentileDisc(n.v, 0.5) AS d, percentileCont(n.v, 0.5) AS c, min(n.v) AS mn")
    got["kind:match:int"] = [type(v).__name__ for v in r.rows[0]]
    for pk, (src, kind, value) in PARGS.items():
        q = "UNWIND [10, 20, 30] AS x RETURN percentileDisc(x, " + ("null" if (src == "Lit" and kind == "Null") else repr(value) if src == "Lit" else "$p") + ") AS d"
        params = {} if src in ("Missing", "Lit") else {"p": value}
        try:
            r = e.execute_cypher(q, params)
            if getattr(r, "error", None):
                got[f"p:{pk}"] = "Refused" if ("InvalidArgumentType" in str(r.error) or "NumberOutOfRange" in str(r.error)) else f"error:{str(r.error)[:100]}"
            else:
                got[f"p:{pk}"] = ["run", None if r.rows[0][0] is None else float(r.rows[0][0])]
        except TypeError as x:
            got[f"p:{pk}"] = "RawTypeError" if "NoneType" in str(x) else f"TypeError:{x}"
        except ValueError as x:
            got[f"p:{pk}"] = "RawValueError" if "could not convert" in str(x) else f"ValueError:{x}"
        except SyntaxError as x:
            got[f"p:{pk}"] = "Undefined" if "Undefined variable" in str(x) else f"SyntaxError:{x}"
        except Exception as x:
            got[f"p:{pk}"] = f"{type(x).__name__}:{str(x)[:100]}"
    # the SQL functions directly
    for ln, xs in LISTS.items():
        for ps in ("0.5", "0.9", "1") + tuple(BAD):
            pv = float(frac(ps)); vals = json.dumps([x for x in xs if x is not None]); row = []
            for proc in ("PDISC", "PCONT"):
                try:
                    cur.execute(f"SELECT {e._ivg_schema}.Percentile_{proc}(?, ?)", [vals, pv]); v = cur.fetchone()[0]
                    row.append(None if v is None else float(v))
                except Exception as x:
                    row.append("OutOfRange" if "NumberOutOfRange" in str(x) else f"error:{str(x)[:80]}")
            got[f"sql:{ln}:{ps}"] = row if all(not isinstance(v, str) for v in row) else (row[0] if row[0] == row[1] else row)
    c.close()

    def predict(m):
        out = {}
        def both(xs, p):
            d, cc = pdisc(xs, p, m), pcont(xs, p, m)
            if d == "OutOfRange" or cc == "OutOfRange":
                return "OutOfRange"      # either function's refusal fails the row
            return [d, cc]
        for ln, xs in LISTS.items():
            for ps in PS + BAD:
                out[f"unwind:{ln}:{ps}"] = both(xs, frac(ps))
        stored = [10, 20, 30, 40]
        for ps in PS + BAD:
            out[f"match:{ps}"] = both(stored, frac(ps))
        out["match:none"] = both([], Fraction(1, 2))
        for kn in KINDS:
            out[f"kind:unwind:{kn}"] = [answer_kind("disc", kn, m), answer_kind("cont", kn, m)]
        out["kind:match:int"] = [answer_kind("disc", "int", m), answer_kind("cont", "int", m), "int"]
        for pk, (src, kind, value) in PARGS.items():
            out[f"p:{pk}"] = as_built_p(src, kind, value, m)
        for ln, xs in LISTS.items():
            for ps in ("0.5", "0.9", "1") + tuple(BAD):
                d, cc = pdisc(xs, frac(ps), m), pcont(xs, frac(ps), m)
                out[f"sql:{ln}:{ps}"] = [d, cc] if d != "OutOfRange" and cc != "OutOfRange" else (d if d == cc else [d, cc])
        return out

    def same(a, b):
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        if isinstance(a, float) and isinstance(b, float):
            return abs(a - b) <= TOL * max(1.0, abs(b))
        return a == b

    want = predict({})
    mism = [{"case": k, "observed": got.get(k), "expected": want[k]} for k in want if not same(got.get(k), want[k])]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if not same(got.get(k), v)) for mm in MUTS}
    tampered = json.loads(json.dumps(got)); tampered["unwind:four:0.9"] = [40.0, 37.0]
    tamper_detected = any(not same(tampered.get(k), want[k]) for k in want)
    body = {"kind": "binding", "model": "percentile", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": RUN, "prefix": P, "graph": G, "tolerance_relative": TOL,
            "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q_.relative_to(REPO)): sha(q_) for q_ in [HERE / "binding.py", HERE / "percentile.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_src/src/IVG/Percentile.cls", "iris_src/src/Graph/KG/SqlProcs.cls",
                                                                   "iris_vector_graph/cypher/translator.py", "iris_vector_graph/_engine/query.py"]}},
            "scope": "Actual execute_cypher and the SQL functions on IRIS 2026.1 (pin 3eaa79cf): 9 lists (even, odd, ten, "
                     "unsorted, duplicates, negatives, one value, floats, a null) x 11 percentiles (9 in range, 2 out) through "
                     "UNWIND of a literal list; stored values with a null through MATCH with a $p parameter (11 p) and an empty "
                     "match; the SQL functions on 9 lists x 5 p. Iteration 56: the answer kind of each function over integers and floats "
                     "(UNWIND and stored integers, beside min() as the int-keeping neighbor) and p supplied as a number, null, numeric "
                     "text, other text, a boolean, a missing parameter, a literal null and a literal number."}
    d = REPO / ".g5/Verus_verification/results/percentile" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "all_sensitivities_detected", "sensitivities_detected_cases", "observation_tamper_detected", "elapsed_s")}))
    for x in mism[:20]:
        print("MISMATCH", json.dumps(x, default=str)[:300])


if __name__ == "__main__":
    main()
