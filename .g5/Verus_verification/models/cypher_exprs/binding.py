"""cypher_exprs binding: Cypher expressions over run-time values on the run-isolated continuation fixture
(ivg-cont-20261117-iris), through execute_cypher (reads: the SQL path, recording whether the native executor declined;
writes: execute_cypher, read back by a later MATCH and get_node()). Outcomes are compared with a port of
cypher_exprs.rs; mutations mirror the controls; one observation is tampered to check detection. Ordinary data, fresh
prefix per run. The Prop_Set premise is varied through the product's own switch for a namespace without Prop_Set
(engine._prop_set_deployed, cached as _prop_set_ok)."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("CE_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
MUTS = ["row_slice_wrapped", "literal_slice_unwrapped", "row_condition_compared", "property_condition_raw",
        "iris_accepts_scalar_condition", "create_value_translated", "toupper_not_folded", "rel_value_kept",
        "rel_literal_dropped", "coalesce_always_typed", "coalesce_needs_two_props", "identifier_lookahead",
        "substring_checks_start", "substring_zero_based", "setval_skips_retype", "prop_set_not_emitted",
        "filer_writes_same_text"]
LIST = [10, 20, 30, 40, 50]
BOUNDS = [-7, -3, -1, 0, 2, 5, 8]
FNS = {"ToUpper": "toUpper('ab')", "ToLower": "toLower('AB')", "Trim": "trim(' a ')", "Coalesce": "coalesce(null, 'x')",
       "ToStringFn": "toString(1)", "ToIntegerOfNumber": "toInteger(2.5)", "ToFloatOfNumber": "toFloat(2)",
       "Arith": "1 + 1", "ToIntegerOfString": "toInteger('5')", "Size": "size('ab')", "Abs": "abs(-1)",
       "RandomUuid": "randomUUID()", "Rand": "rand()", "Substring": "substring('abc', 1)", "Replace": "replace('a', 'a', 'b')"}
FOLDED = {"ToUpper", "ToLower", "Trim", "Coalesce", "ToStringFn", "ToIntegerOfNumber", "ToFloatOfNumber", "Arith"}
REL_FNS = ["ToUpper", "Arith", "Size", "ToStringFn"]
STR = "abcde"
SUBS = [(s, l) for s in (-3, -1, 0, 1, 4) for l in (1, 2, 4, 7)]
COAL = [("RowVar", "ScalarLiteral"), ("ScalarLiteral", "ScalarLiteral"), ("ScalarParam", "ScalarLiteral"),
        ("NodeProp", "ScalarLiteral"), ("ScalarLiteral", "NodeProp"), ("NodeProp", "ScalarParam"),
        ("NodeProp", "RowVar"), ("NodeProp", "ListLiteral")]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---- port of cypher_exprs.rs
def clamp(x, n):
    return 0 if x < 0 else (n if x > n else x)


def rule_pos(x, n):
    return (n + x if n + x > 0 else 0) if x < 0 else (n if x > n else x)


def translated_bound(syn, v, n, m):
    if syn == "Literal" and not m.get("literal_slice_unwrapped"):
        return (n + v if n + v > 0 else 0) if v < 0 else v
    if syn != "Literal" and m.get("row_slice_wrapped"):
        return (n + v if n + v > 0 else 0) if v < 0 else v
    return v


def norm_slice(f, t):
    return "empty" if t <= f else [f, t]


def as_built_slice(syn, n, s, e, m):
    return norm_slice(clamp(translated_bound(syn, s, n, m), n), clamp(translated_bound(syn, e, n, m), n))


def condition_sql(syn, m):
    if syn in ("RowVar", "Param"):
        return "Predicate" if m.get("row_condition_compared") else "RawScalar"
    return "RawScalar" if m.get("property_condition_raw") else "Predicate"


def case_when(syn, v, m):
    if condition_sql(syn, m) == "Predicate" or m.get("iris_accepts_scalar_condition"):
        return ["branch", v]
    return "prepare_fails"


def folds(f, m):
    if f == "ToUpper" and m.get("toupper_not_folded"):
        return False
    return f in FOLDED


def create_node_value(f, m):
    return "written" if (folds(f, m) or m.get("create_value_translated")) else "refused_nothing_written"


def create_rel_value(kind, f, m):
    if kind == "Lit":
        return "written_without_property" if m.get("rel_literal_dropped") else "written"
    if kind == "ForeachVar":
        return "written"
    return create_node_value(f, m) if m.get("rel_value_kept") else "written_without_property"


def coalesce_number(a, b, m):
    if m.get("coalesce_always_typed"):
        return "int"
    ok = lambda x: x in ("NodeProp", "ScalarLiteral", "ScalarParam")
    typed = (a == "NodeProp" and b == "NodeProp") if m.get("coalesce_needs_two_props") else \
        ((a == "NodeProp" or b == "NodeProp") and ok(a) and ok(b))
    return "int" if typed else "text"


def parses(lo, m):
    return m.get("identifier_lookahead", False) if lo == "Identifier" else True


def iris_substring(n, p, l):
    lo = 1 if p < 1 else p
    hi = n if p + l - 1 > n else p + l - 1
    return ["chars", lo - 1, hi - lo + 1] if hi >= lo else ["chars", 0]


def as_built_substring(n, s, l, m):
    if m.get("substring_checks_start") and (s < 0 or l < 0):
        return "error"
    return iris_substring(n, s if m.get("substring_zero_based") else s + 1, l)


def node_update(deployed, old, new, m):
    def filer(o, nw):
        return o if (o[0] == nw[0] and not m.get("filer_writes_same_text")) else nw

    def setval(o, nw):
        if m.get("setval_skips_retype"):
            return o
        return nw if (o[0] == nw[0] and o[1] != nw[1]) else o
    if deployed and not m.get("prop_set_not_emitted"):
        return filer(setval(old, new), new)
    return filer(old, new)


PROPSET = [("same_text_to_int", ("30", False), ("30", True)), ("same_text_to_str", ("30", True), ("30", False)),
           ("other_text", ("30", False), ("31", True))]


def main():
    t0 = time.time(); c = runtime.connect()
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.cypher.parser import parse_query
    e = IRISGraphEngine(c, embedding_dimension=768)
    p, L = f"ce{TAG}_", f"CE{TAG}"
    e.execute_cypher(f"CREATE (n:{L} {{id: '{p}c', l: {LIST}, s: '{STR}', i: 7, t: true, f: false}})")
    C = f"MATCH (n:{L} {{id: '{p}c'}})"
    declined = []

    def run(q, params=None):
        params = params or {}
        try:
            if e._try_native(parse_query(q), params) is None:
                declined.append(q)
        except Exception:
            pass
        try:
            r = e.execute_cypher(q, params)
            return [list(x) for x in r.rows], (str(r.error) if getattr(r, "error", None) else None)
        except Exception as x:
            return None, f"{type(x).__name__}: {x}"

    def slice_of(v):
        if not isinstance(v, list):
            return f"other:{v!r}"
        if not v:
            return "empty"
        f = LIST.index(v[0]); return [f, f + len(v)]

    got = {}
    # slices: literal bounds, row bounds (an UNWIND pair), parameter bounds
    pairs = [[s, t] for s in BOUNDS for t in BOUNDS]
    # an UNWIND of a parameter list of pairs answered no rows here (first binding run); the literal list is the probe's form
    rows, err = run(f"{C} UNWIND {json.dumps(pairs)} AS ab RETURN ab, n.l[ab[0]..ab[1]]")
    got["slice_row_query_error"] = err
    for ab, v in (rows or []):
        got[f"slice_row_{ab[0]}_{ab[1]}"] = slice_of(v)
    for s, t in pairs:
        r, _ = run(f"{C} RETURN n.l[{s}..{t}]"); got[f"slice_literal_{s}_{t}"] = slice_of(r[0][0]) if r else "error"
    for s, t in [(-3, 5), (0, -1), (2, 5), (-1, 8)]:
        r, _ = run(f"{C} RETURN n.l[$a..$b]", {"a": s, "b": t}); got[f"slice_param_{s}_{t}"] = slice_of(r[0][0]) if r else "error"

    def branch(rows, err):
        if err:
            return "prepare_fails" if "comparison operator is required" in err else "error:" + err[-80:]
        return ["branch", rows[0][-1] == "y"]
    for v in (True, False):
        lv = str(v).lower(); prop = "t" if v else "f"
        got[f"cond_RowVar_{lv}"] = branch(*run(f"UNWIND [{lv}] AS b RETURN CASE WHEN b THEN 'y' ELSE 'n' END"))
        got[f"cond_Param_{lv}"] = branch(*run("RETURN CASE WHEN $b THEN 'y' ELSE 'n' END", {"b": v}))
        got[f"cond_PropertyRead_{lv}"] = branch(*run(f"{C} RETURN CASE WHEN n.{prop} THEN 'y' ELSE 'n' END"))
        got[f"cond_Literal_{lv}"] = branch(*run(f"RETURN CASE WHEN {lv} THEN 'y' ELSE 'n' END"))
        got[f"cond_Comparison_{lv}"] = branch(*run(f"UNWIND [{lv}] AS b RETURN CASE WHEN b = true THEN 'y' ELSE 'n' END"))
        got[f"where_RowVar_{lv}"] = (lambda r: "prepare_fails" if r[1] and "comparison operator" in r[1] else ["branch", bool(r[0])])(
            run(f"UNWIND [{lv}] AS b WITH b WHERE b RETURN b"))

    # node CREATE / SET values
    e.execute_cypher(f"CREATE (:{L}S {{id: '{p}set'}})")
    for i, (f, expr) in enumerate(FNS.items()):
        rows, err = run(f"CREATE (:{L}N {{id: '{p}n{i}', v: {expr}}})")
        r2, _ = run(f"MATCH (x:{L}N {{id: '{p}n{i}'}}) RETURN x.v")
        if err is None and r2 and r2[0][0] is not None:
            got[f"create_node_{f}"] = "written"
        elif err and "nothing written" in err and not r2:
            got[f"create_node_{f}"] = "refused_nothing_written"
        else:
            got[f"create_node_{f}"] = f"other:{err!r}:{r2!r}"
        rows, err = run(f"MATCH (x:{L}S {{id: '{p}set'}}) SET x.v{i} = {expr}")
        r2, _ = run(f"MATCH (x:{L}S {{id: '{p}set'}}) RETURN x.v{i}")
        got[f"set_node_{f}"] = "written" if (err is None and r2 and r2[0][0] is not None) else f"other:{err!r}:{r2!r}"

    # relationship CREATE values between new nodes
    def rel_case(k, q, params=None):
        rows, err = run(q, params)
        r2, _ = run(f"MATCH (a {{id: '{p}{k}a'}})-[r:T{TAG}]->(b) RETURN r.v")
        if err or not r2:
            return f"other:{err!r}:{r2!r}"
        return "written" if r2[0][0] is not None else "written_without_property"
    got["create_rel_Lit"] = rel_case("rl", f"CREATE (:{L}R {{id: '{p}rla'}})-[:T{TAG} {{v: 'ab'}}]->(:{L}R {{id: '{p}rlb'}})")
    got["create_rel_ForeachVar"] = rel_case("rv", f"UNWIND ['ab'] AS w CREATE (:{L}R {{id: '{p}rva'}})-[:T{TAG} {{v: w}}]->(:{L}R {{id: '{p}rvb'}})")
    for f in REL_FNS:
        k = "r" + f.lower()[:6]
        got[f"create_rel_Call_{f}"] = rel_case(k, f"CREATE (:{L}R {{id: '{p}{k}a'}})-[:T{TAG} {{v: {FNS[f]}}}]->(:{L}R {{id: '{p}{k}b'}})")

    # coalesce result type for a winning integer 7
    q = {("RowVar", "ScalarLiteral"): ("UNWIND [7] AS x RETURN coalesce(x, 1)", {}),
         ("ScalarLiteral", "ScalarLiteral"): ("RETURN coalesce(null, 7)", {}),
         ("ScalarParam", "ScalarLiteral"): ("RETURN coalesce($p, 1)", {"p": 7}),
         ("NodeProp", "ScalarLiteral"): (f"{C} RETURN coalesce(n.i, 1)", {}),
         ("ScalarLiteral", "NodeProp"): (f"{C} RETURN coalesce(null, n.i)", {}),
         ("NodeProp", "ScalarParam"): (f"{C} RETURN coalesce(n.i, $p)", {"p": 1}),
         ("NodeProp", "RowVar"): (f"{C} UNWIND [1] AS x RETURN coalesce(n.i, x)", {}),
         ("NodeProp", "ListLiteral"): (f"{C} RETURN coalesce(n.i, [1])", {})}
    for a, b in COAL:
        rows, err = run(*q[(a, b)])
        v = rows[0][-1] if rows else None
        got[f"coalesce_{a}_{b}"] = "int" if (v == 7 and isinstance(v, int)) else ("text" if v == "7" else f"other:{v!r}:{err}")

    # parser: a slice's lower bound
    for lo, text, params in (("Identifier", "WITH [1, 2, 3] AS l, 1 AS a RETURN l[a..3]", {}),
                             ("IntLiteral", "WITH [1, 2, 3] AS l RETURN l[1..3]", {}),
                             ("Subscript", "WITH [1, 2, 3] AS l, [1] AS a RETURN l[a[0]..3]", {}),
                             ("Param", "WITH [1, 2, 3] AS l RETURN l[$a..3]", {"a": 1})):
        try:
            parse_query(text); got[f"parse_{lo}"] = True
        except Exception as x:
            got[f"parse_{lo}"] = False if "CypherParseError" in type(x).__name__ else f"other:{x}"

    # substring over a stored 'abcde': literal arguments and row arguments
    def sub_of(rows, err):
        if err:
            return "error"
        v = rows[0][-1]
        if v in (None, ""):
            return ["chars", 0]
        return ["chars", STR.index(v), len(v)] if v in STR else f"other:{v!r}"
    for s, l in SUBS:
        got[f"substring_literal_{s}_{l}"] = sub_of(*run(f"{C} RETURN substring(n.s, {s}, {l})"))
        got[f"substring_row_{s}_{l}"] = sub_of(*run(f"{C} UNWIND [[{s}, {l}]] AS a RETURN substring(n.s, a[0], a[1])"))

    # Prop_Set: deployed (the fixture) and the product's path for a namespace without it
    deployed_seen = bool(e._prop_set_deployed)
    for deployed in (True, False):
        for k, old, new in PROPSET:
            nid = f"{p}ps{int(deployed)}{k}"
            oldv = old[0] if old[1] else f"'{old[0]}'"
            e.execute_cypher(f"CREATE (:{L}P {{id: '{nid}', a: {oldv}}})")
            newv = f"toInteger(x.a) + {int(new[0]) - int(old[0])}" if new[1] else f"toString({new[0]})"
            if new[1] and new[0] == old[0]:
                newv = "toInteger(x.a)"
            if not deployed:
                e.__dict__["_prop_set_ok"] = False
            try:
                e.execute_cypher(f"MATCH (x:{L}P {{id: '{nid}'}}) SET x.a = {newv}")
            finally:
                e.__dict__.pop("_prop_set_ok", None)
            r = e.execute_cypher(f"MATCH (x:{L}P {{id: '{nid}'}}) RETURN x.a").rows[0][0]
            got[f"propset_{int(deployed)}_{k}"] = [str(r), isinstance(r, int) and not isinstance(r, bool)]
    c.close()

    def predict(m):
        out = {"slice_row_query_error": None}
        n = len(LIST)
        for s, t in pairs:
            out[f"slice_row_{s}_{t}"] = as_built_slice("RowVar", n, s, t, m)
            out[f"slice_literal_{s}_{t}"] = as_built_slice("Literal", n, s, t, m)
        for s, t in [(-3, 5), (0, -1), (2, 5), (-1, 8)]:
            out[f"slice_param_{s}_{t}"] = as_built_slice("Param", n, s, t, m)
        for v in (True, False):
            lv = str(v).lower()
            for syn in ("RowVar", "Param", "PropertyRead", "Literal", "Comparison"):
                out[f"cond_{syn}_{lv}"] = case_when(syn, v, m)
            out[f"where_RowVar_{lv}"] = case_when("RowVar", v, m)
        for f in FNS:
            out[f"create_node_{f}"] = create_node_value(f, m)
            out[f"set_node_{f}"] = "written"
        out["create_rel_Lit"] = create_rel_value("Lit", None, m)
        out["create_rel_ForeachVar"] = create_rel_value("ForeachVar", None, m)
        for f in REL_FNS:
            out[f"create_rel_Call_{f}"] = create_rel_value("Call", f, m)
        for a, b in COAL:
            out[f"coalesce_{a}_{b}"] = coalesce_number(a, b, m)
        for lo in ("Identifier", "IntLiteral", "Subscript", "Param"):
            out[f"parse_{lo}"] = parses(lo, m)
        for s, l in SUBS:
            out[f"substring_literal_{s}_{l}"] = as_built_substring(len(STR), s, l, m)
            out[f"substring_row_{s}_{l}"] = as_built_substring(len(STR), s, l, m)
        for deployed in (True, False):
            for k, old, new in PROPSET:
                out[f"propset_{int(deployed)}_{k}"] = list(node_update(deployed, old, new, m))
        return out

    norm = lambda d: json.loads(json.dumps(d))
    got = norm(got); want = norm(predict({}))
    mism = [{"case": k, "observed": got.get(k), "expected": want[k]} for k in want if got.get(k) != want[k]]
    sens = {mm: sum(1 for k, v in norm(predict({mm: True})).items() if v != got.get(k)) for mm in MUTS}
    tampered = dict(got); tampered["slice_row_-3_5"] = [2, 5]
    tamper_detected = any(tampered.get(k) != want[k] for k in want)
    body = {"kind": "binding", "model": "cypher_exprs", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "prop_set_deployed_on_fixture": deployed_seen,
            "native_declined": len(declined), "native_declined_queries": declined[:6],
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q_.relative_to(REPO)): sha(q_) for q_ in [HERE / "binding.py", HERE / "cypher_exprs.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/cypher/translator.py", "iris_vector_graph/cypher/parser.py",
                                                                   "iris_vector_graph/engine.py", "iris_src/src/Graph/KG/PropWrite.cls",
                                                                   "iris_src/src/Graph/KG/SqlProcs.cls"]}},
            "scope": "Actual execute_cypher on IRIS 2026.1 (pin 3eaa79cf): slices over a stored 5-element list with 49 bound pairs "
                     "(row and literal) and 4 parameter pairs; CASE WHEN / WHERE over row, parameter, stored, literal and compared "
                     "booleans; 15 functions in a node CREATE map and in SET; 6 relationship CREATE values; 8 coalesce argument "
                     "shapes; 4 slice lower-bound syntaxes; 20 substring (start, length) pairs with length >= 1, literal and row; "
                     "3 Prop_Set retypes with Prop_Set and through the product's path for a namespace without it."}
    d = REPO / ".g5/Verus_verification/results/cypher_exprs" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "native_declined", "prop_set_deployed_on_fixture", "all_sensitivities_detected", "sensitivities_detected_cases", "observation_tamper_detected", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
