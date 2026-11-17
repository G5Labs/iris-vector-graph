"""clause_combos binding: clause combinations over API-written data on the run-isolated continuation fixture
(ivg-cont-20261117-iris, USER, fresh i58c_ tag per run). Reads go through execute_cypher on the SQL path (engine with
native_cypher=False). Data are written by create_node / create_edge (the Python API). Each case's outcome is
classified and compared with an independent Python port of clause_combos.rs; every model control has a mutation of
the port here, and observations are tampered to check detection. No sync() is run."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("CC_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
P = f"i58c_{TAG}_"; L = f"I58C{TAG}"; K = f"K58C{TAG}"
MUTS = ["sum-null-over-no-value", "count-var-counts-rows", "leading-star-unpatched", "null-row-sum-zero",
        "null-row-count-var-one", "grouped-leading-uses-sql", "group-by-kind-column", "bool-bound-as-word",
        "distinct-plain-on-flag", "json-route-plain", "iris-accepts-or", "iris-accepts-arith", "iris-refuses-any-or",
        "iris-refuses-any-arith", "negation-ignored",
        "collect-null-over-no-value", "condition-in-where"]
AGGS = ["CountVar", "CountStar", "Sum", "Avg", "Min", "Collect"]
AGG_SQL = {"CountVar": "count(b)", "CountStar": "count(*)", "Sum": "sum(b.v)", "Avg": "avg(b.v)", "Min": "min(b.v)",
           "Collect": "collect(b.v)"}
# ---- A data: anchors a1 (K edges to b1 v 10, b2 v 20) and a2 (none); NONE type has no edge
EDGES = {"a1": [(K, 10), (K, 20)], "a2": []}
# ---- B lists (Cypher text, port values). Val: ("Int", i) ("Bool", b) ("Str", spell) ("List", j)
LISTS = {"int_str1": ("[1, '1']", [("Int", 1), ("Str", ("SpellsInt", 1))]),
         "int_true": ("[1, true]", [("Int", 1), ("Bool", True)]),
         "zero_false": ("[0, false]", [("Int", 0), ("Bool", False)]),
         "list_spelled": ("[[1], '[1]']", [("List", 1), ("Str", ("SpellsList", 1))]),
         "strtrue_true": ("['true', true]", [("Str", ("SpellsTrue",)), ("Bool", True)]),
         "int_int": ("[1, 2]", [("Int", 1), ("Int", 2)]),
         "int_int_same": ("[2, 2]", [("Int", 2), ("Int", 2)]),
         "true_false": ("[true, false]", [("Bool", True), ("Bool", False)]),
         "int_word": ("[1, 'x']", [("Int", 1), ("Str", ("Other", 0))]),
         "list_int": ("[[1], 1]", [("List", 1), ("Int", 1)])}
# ---- C conditions: AST (Cmp l r) / (And p q) / (Or p q) / (Not p); operands New / Earlier / ("Lit", n) / ("Arith", op, x, y)
N, E = "New", "Earlier"
def lit(n): return ("Lit", n)
def ar(op, x, y): return ("Arith", op, x, y)
CONDS = {"earlier_arith": ("Cmp", N, ar("+", E, lit(1))),
         "earlier_arith_left": ("Cmp", ar("+", E, lit(9)), N),
         "or_with_earlier": ("Or", ("Cmp", N, E), ("Cmp", N, lit(10))),
         "or_new_only": ("Or", ("Cmp", N, lit(10)), ("Cmp", N, lit(30))),
         "arith_new_only": ("Cmp", ar("-", N, lit(1)), lit(9)),
         "mul_new_only": ("Cmp", ar("*", N, lit(2)), lit(40)),
         "not_new_only": ("Not", ("Cmp", N, lit(10))),
         "eq_earlier": ("Cmp", N, E),
         "or_new_and_eq_earlier": ("And", ("Or", ("Cmp", N, lit(10)), ("Cmp", N, lit(20))), ("Cmp", N, E)),
         "not_or_with_earlier": ("Not", ("Or", ("Cmp", N, E), ("Cmp", N, lit(10)))),
         "not_and_with_earlier": ("Not", ("And", ("Cmp", N, lit(10)), ("Cmp", N, E))),
         "not_not_or_with_earlier": ("Not", ("Not", ("Or", ("Cmp", N, E), ("Cmp", N, lit(10))))),
         "or_with_earlier_and_new": ("And", ("Or", ("Cmp", N, E), ("Cmp", N, lit(10))), ("Cmp", N, lit(10))),
         "not_arith_earlier": ("Not", ("Cmp", N, ar("+", E, lit(1)))),
         "not_or_arith_new_eq_earlier": ("Not", ("Or", ("Cmp", ar("+", N, lit(1)), lit(11)), ("Cmp", N, E)))}
# excluded from the domain (NOTES): a comparison reading only the earlier alias (`a.v = 1`): NOT ((b.v = 10) OR (a.v = 1))
# is refused, which the polarity premise does not decide


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- port of clause_combos.rs
def matched(edges, t):
    return [v for ty, v in edges if ty == t]


def as_built_sql(k, rows, m):
    vs = [r for r in rows if r is not None]
    if k == "CountVar":
        return len(rows) if m.get("count-var-counts-rows") else len(vs)
    if k == "CountStar":
        return len(rows)
    if k == "Sum":
        return None if (not vs and m.get("sum-null-over-no-value")) else sum(vs)
    if k == "Avg":
        return None if not vs else sum(vs) / len(vs)
    if k == "Min":
        return None if not vs else min(vs)
    return None if (not vs and m.get("collect-null-over-no-value")) else sorted(vs)


def null_row_aggregate(k, m):
    if k == "CountStar":
        return 1
    if k == "CountVar":
        return 1 if m.get("null-row-count-var-one") else 0
    if k == "Collect":
        return []
    if k == "Sum" and m.get("null-row-sum-zero"):
        return 0
    return None


def leading_star_patch(k, v, m):
    return 1 if (k == "CountStar" and v == 0 and not m.get("leading-star-unpatched")) else v


def as_built_answer(leading, grouped, edges, t, k, m):
    ms = matched(edges, t)
    if not leading:
        return as_built_sql(k, ms if ms else [None], m)
    if ms:
        return as_built_sql(k, ms, m)
    if grouped and not m.get("grouped-leading-uses-sql"):
        return null_row_aggregate(k, m)
    return leading_star_patch(k, as_built_sql(k, [], m), m)


def bound_text(v, m):
    kind = v[0]
    if kind == "Int":
        return ("Num", v[1])
    if kind == "Bool":
        return ("Word", -1 if v[1] else -2) if m.get("bool-bound-as-word") else ("Num", 1 if v[1] else 0)
    if kind == "List":
        return ("Json", v[1])
    s = v[1]
    return {"SpellsInt": lambda: ("Num", s[1]), "SpellsTrue": lambda: ("Word", -1),
            "SpellsList": lambda: ("Json", s[1]), "Other": lambda: ("Word", s[1])}[s[0]]()


def route(l):
    if any(v[0] == "List" for v in l):
        return "JsonCol"
    if any(v[0] == "Bool" for v in l) and any(v[0] != "Bool" for v in l):
        return "Flag"
    return "Plain"


def select_key(l, v, m):
    r = route(l)
    if r == "JsonCol":
        return ("Text", bound_text(v, m)) if m.get("json-route-plain") else ("Typed", v)
    if r == "Flag":
        return ("Text", bound_text(v, m)) if m.get("distinct-plain-on-flag") else ("Flagged", v[0] == "Bool", bound_text(v, m))
    return ("Text", bound_text(v, m))


def as_built_group(l, v, w, m):
    return v == w if m.get("group-by-kind-column") else bound_text(v, m) == bound_text(w, m)


def op_reads_earlier(o):
    if o == E:
        return True
    return isinstance(o, tuple) and o[0] == "Arith" and (op_reads_earlier(o[2]) or op_reads_earlier(o[3]))


def op_arith_over_earlier(o, m):
    if isinstance(o, tuple) and o[0] == "Arith":
        return True if m.get("iris-refuses-any-arith") else (op_reads_earlier(o[2]) or op_reads_earlier(o[3]))
    return False


def reads_earlier(c):
    if c[0] == "Cmp":
        return op_reads_earlier(c[1]) or op_reads_earlier(c[2])
    if c[0] == "Not":
        return reads_earlier(c[1])
    return reads_earlier(c[1]) or reads_earlier(c[2])


def refuses_p(c, pos, m):
    """clause_combos.rs refuses_p: negation pushed to the comparisons (a negated AND is an OR, a negated OR an AND)."""
    if c[0] == "Cmp":
        return False if m.get("iris-accepts-arith") else (op_arith_over_earlier(c[1], m) or op_arith_over_earlier(c[2], m))
    if c[0] == "Not":
        return refuses_p(c[1], pos if m.get("negation-ignored") else not pos, m)
    sides = refuses_p(c[1], pos, m) or refuses_p(c[2], pos, m)
    disj = (c[0] == "Or") == pos
    if not disj:
        return sides
    if m.get("iris-refuses-any-or") and c[0] == "Or":
        return True
    if m.get("iris-accepts-or") and c[0] == "Or":
        return sides
    return reads_earlier(c[1]) or reads_earlier(c[2]) or sides


def iris_refuses(c, m):
    return refuses_p(c, True, m)


def as_built_opt(c, m):
    if m.get("condition-in-where"):
        return "DroppedSome"
    if iris_refuses(c, m):
        return "Refused"
    # a condition reading the earlier alias that runs: the cypher_clauses model's guard; every anchor here has v,
    # so the row is kept (cypher_clauses as_built_opt with outer_missing false)
    return "KeptAll"


def predict(m):
    out = {}
    for anchor, edges in EDGES.items():
        for t in (K, "NONE"):
            for k in AGGS:
                out[f"A_after_{anchor}_{'K' if t == K else 'NONE'}_{k}"] = as_built_answer(False, True, edges, t, k, m)
    lb = [(K, 10), (K, 20)]  # leading pattern over the B label: matches b1, b2
    for k in AGGS:
        out[f"A_leading_pure_nomatch_{k}"] = as_built_answer(True, False, [], K, k, m)
        out[f"A_leading_grouped_nomatch_{k}"] = as_built_answer(True, True, [], K, k, m)
        out[f"A_leading_pure_matched_{k}"] = as_built_answer(True, False, lb, K, k, m)
    for name, (_, l) in LISTS.items():
        v, w = l
        g = as_built_group(l, v, w, m)
        out[f"B_{name}_groups"] = 1 if g else 2
        out[f"B_{name}_count_distinct"] = 1 if g else 2
        out[f"B_{name}_distinct_rows"] = 1 if select_key(l, v, m) == select_key(l, w, m) else 2
    for name, c in CONDS.items():
        out[f"C_{name}"] = as_built_opt(c, m)
    return out


def render_op(o):
    if o == N:
        return "b.v"
    if o == E:
        return "a.v"
    if o[0] == "Lit":
        return str(o[1])
    return f"{render_op(o[2])} {o[1]} {render_op(o[3])}"


def render(c):
    if c[0] == "Cmp":
        return f"{render_op(c[1])} = {render_op(c[2])}"
    if c[0] == "Not":
        return f"NOT ({render(c[1])})"
    return f"({render(c[1])}) {c[0].upper()} ({render(c[2])})"


def main():
    t0 = time.time()
    from importlib.metadata import version
    driver = version("intersystems-irispython")
    c = runtime.connect(); e = runtime.engine(c)
    queries = {}

    def run(key, q):
        queries[key] = q
        try:
            r = e.execute_cypher(q, {})
            if getattr(r, "error", None):
                return None, str(r.error)
            return [list(x) for x in r.rows], None
        except Exception as x:
            return None, f"{type(x).__name__}: {x}"

    got = {}
    A, B = L + "A", L + "B"
    e.create_node(P + "a1", labels=[A], properties={"name": "a1", "v": 1})
    e.create_node(P + "a2", labels=[A], properties={"name": "a2", "v": 2})
    e.create_node(P + "b1", labels=[B], properties={"name": "b1", "v": 10})
    e.create_node(P + "b2", labels=[B], properties={"name": "b2", "v": 20})
    e.create_edge(P + "a1", K, P + "b1"); e.create_edge(P + "a1", K, P + "b2")
    items = ", ".join(AGG_SQL[k] for k in AGGS)

    def norm(k, v):
        if k == "Collect" and isinstance(v, list):
            return sorted(v)
        if k == "Avg" and v is not None:
            return float(v)
        return v
    for t, tn in ((K, "K"), (f"NONE{TAG}", "NONE")):
        rows, err = run(f"A_after_{tn}", f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{t}]->(b) RETURN a.name, {items} ORDER BY a.name")
        for anchor in EDGES:
            row = next((r for r in (rows or []) if r[0] == anchor), None)
            for i, k in enumerate(AGGS):
                got[f"A_after_{anchor}_{tn}_{k}"] = norm(k, row[1 + i]) if row else f"error:{err}"
    for key, q in (("A_leading_pure_nomatch", f"OPTIONAL MATCH (b:{L}NONE) RETURN {items}"),
                   ("A_leading_grouped_nomatch", f"OPTIONAL MATCH (b:{L}NONE) RETURN b.v AS kk, {items}"),
                   ("A_leading_pure_matched", f"OPTIONAL MATCH (b:{B}) RETURN {items}")):
        rows, err = run(key, q)
        off = 1 if "grouped" in key else 0
        for i, k in enumerate(AGGS):
            got[f"{key}_{k}"] = norm(k, rows[0][off + i]) if rows and len(rows) == 1 else f"error:{err}:{rows}"
    for name, (txt, _) in LISTS.items():
        rows, err = run(f"B_{name}_groups", f"UNWIND {txt} AS x RETURN x, count(*) AS c")
        got[f"B_{name}_groups"] = len(rows) if rows is not None else f"error:{err}"
        rows, err = run(f"B_{name}_count_distinct", f"UNWIND {txt} AS x RETURN count(DISTINCT x)")
        got[f"B_{name}_count_distinct"] = rows[0][0] if rows else f"error:{err}"
        rows, err = run(f"B_{name}_distinct_rows", f"UNWIND {txt} AS x RETURN DISTINCT x")
        got[f"B_{name}_distinct_rows"] = len(rows) if rows is not None else f"error:{err}"
    for name, cnd in CONDS.items():
        rows, err = run(f"C_{name}", f"MATCH (a:{A}) OPTIONAL MATCH (a)-[:{K}]->(b) WHERE {render(cnd)} RETURN a.name, b.name")
        if rows is None:
            got[f"C_{name}"] = "Refused" if "SQLCODE: <-94>" in err else f"other:{err[:120]}"
        else:
            got[f"C_{name}"] = "KeptAll" if {r[0] for r in rows} == {"a1", "a2"} else f"DroppedSome:{rows}"
    c.close()

    nrm = lambda d: json.loads(json.dumps(d))
    got = nrm(got); want = nrm(predict({}))
    mism = [{"case": k, "observed": got.get(k), "expected": want[k]} for k in want if got.get(k) != want[k]]
    sens = {mm: sum(1 for k, v in nrm(predict({mm: True})).items() if v != got.get(k)) for mm in MUTS}
    tamper = {}
    for key, bad in (("A_leading_grouped_nomatch_Sum", 0), ("B_int_true_groups", 2), ("C_or_new_only", "Refused"),
                     ("A_after_a2_K_CountVar", 1)):
        t_ = dict(got); t_[key] = bad
        tamper[key] = any(t_.get(k) != want[k] for k in want)
    body = {"kind": "binding", "model": "clause_combos", "fixture": runtime.NAME, "port": runtime.PORT,
            "driver": f"intersystems-irispython {driver}", "product_baseline": runtime.PRODUCT, "run": RUN,
            "prefix": P, "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "agrees": len(want) - len(mism),
            "mismatches": mism, "observed": got, "queries": queries,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": all(tamper.values()), "tamper_cases": tamper,
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q_.relative_to(REPO)): sha(q_) for q_ in [HERE / "binding.py", HERE / "clause_combos.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/cypher/translator.py", "iris_vector_graph/_engine/query.py"]}},
            "scope": "Actual execute_cypher (SQL path, native_cypher=False) on IRIS 2026.1, pin 3eaa79cf, data written by "
                     "create_node/create_edge in the default graph: A count(b), count(*), sum, avg, min, collect after a MATCH "
                     "(matched and unmatched anchors, a type with no edge), a leading OPTIONAL MATCH with aggregates alone "
                     "(no match and matched) and with a grouping key (no match); B 10 two-element UNWIND literal lists under "
                     "GROUP BY, count(DISTINCT), RETURN DISTINCT; C 11 WHERE shapes inside OPTIONAL MATCH (arithmetic, OR, "
                     "NOT, AND nesting over the new alias and an earlier one), every anchor having the property read."}
    d = REPO / ".g5/Verus_verification/results/clause_combos" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "agrees", "driver", "all_sensitivities_detected",
                                           "sensitivities_detected_cases", "observation_tamper_detected", "elapsed_s")}))
    print("receipt", d / "receipt.json")
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
