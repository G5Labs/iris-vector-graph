"""cypher_clauses binding: Cypher clauses over API-written data on the run-isolated continuation fixture
(ivg-cont-20261117-iris, USER, fresh tag per run). Reads go through execute_cypher on the SQL path (engine with
native_cypher=False) and, for grouping, the native executor's own answer (_try_native on an engine with the native
executor on). Writes go through execute_cypher and are read back by MATCH, get_node() and the native walk over ^KG.
Outcomes are classified and compared with a port of cypher_clauses.rs; every control has a mutation here, and one
observation is tampered to check detection. Data are written by create_node / create_edge (the Python API)."""
import hashlib, json, os, sys, time
from itertools import combinations
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("CC_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
P = f"i54k_{TAG}_"
MUTS = ["group_by_typed", "return_distinct_text", "native_text_key", "int_unmarked", "prop_default_unknown",
        "float_literal_int", "int_read_exact", "union_keeps_decoders", "union_drops_bool", "typed_read_plain",
        "bool_literal_text", "page_int_only", "page_no_negative_check", "page_no_fraction_check",
        "count_guard_sees_union", "shortcut_newline_from", "ensure_from_always", "endpoint_reads_json",
        "type_reads_alias", "delete_outgoing_only", "delete_no_check",
        "opt_guard_in_on", "range_guarded", "iris_accepts_outer_on", "opt_cond_in_where",
        "fixed_length_from_row", "varlen_length_from_pattern", "anchor_null_ignored"]
# ---- I (iteration 56, bug-cyp-146): path functions of a named OPTIONAL path over i1->i2->i3.
# case: (pattern, hops or None for var-length, anchor node or None for a null anchor, row lengths bound, function)
PATH_CASES = {
    "fix1_unmatched_len": ("Fixed", 1, "i3", [], "Length"), "fix1_unmatched_nodes": ("Fixed", 1, "i3", [], "Nodes"),
    "fix1_unmatched_rels": ("Fixed", 1, "i3", [], "Rels"), "fix1_matched_len": ("Fixed", 1, "i1", [1], "Length"),
    "fix1_matched_nodes": ("Fixed", 1, "i1", [1], "Nodes"), "fix1_matched_rels": ("Fixed", 1, "i1", [1], "Rels"),
    "fix2_unmatched_len": ("Fixed", 2, "i2", [], "Length"), "fix2_matched_len": ("Fixed", 2, "i1", [2], "Length"),
    "var_unmatched_len": ("VarLen", None, "i3", [], "Length"), "var_matched_len": ("VarLen", None, "i1", [1, 2], "Length"),
    "fix1_anchor_null_len": ("Fixed", 1, None, [], "Length"),
}
# ---- H: a WHERE inside OPTIONAL MATCH; outer nodes h1 (v 1), h2 (v 2), h3 (no v); edges h1->h2, h2->h3
OPT_CONDS = {"OptOnly": "b.v = 2", "EqProps": "b.v = a.v", "NeProps": "b.v <> a.v", "RangeProps": "b.v > a.v",
             "OuterLitAndOpt": "a.v = 1 AND b.v = 2", "OuterArith": "b.v = a.v + 1", "OuterOrOpt": "a.v = 1 OR b.v = 5"}

# ---- A: stored values (kind, python value, stored text)
VALS = {"Int1": ("Int", 1, "1"), "Str1": ("Str", "1", "1"), "Int2": ("Int", 2, "2"), "Str2": ("Str", "2", "2"),
        "Bool": ("Bool", True, "true"), "StrTrue": ("Str", "true", "true"), "List": ("List", [1], "[1]"),
        "StrList": ("Str", "[1]", "[1]"), "StrX": ("Str", "x", "x")}
PAIRS = [("Int1", "Str1"), ("Int2", "Str2"), ("Int1", "Int2"), ("Str1", "StrX"), ("Int1", "Bool"),
         ("Bool", "StrTrue"), ("List", "StrList"), ("Int1", "List"), ("Str1", "Str1"), ("Int2", "Int2")]
# ---- B: datasets (v integers, f floats) and columns; h = total in half units
DATA_B = {"b13": ([1, 2], [2.5, 1.0]), "b5": ([1], [1.5]), "b8": ([2], [2.0]), "b3": ([1], [0.5])}
COLS_B = {"sumv_plus_sumf": ("Arith", "SumProp", "SumProp"), "sumf_plus_sumv": ("Arith", "SumProp", "SumProp"),
          "sumv_plus_half": ("Arith", "SumProp", "LitFloat"), "bare_sumf": ("BareSum", "Prop", None),
          "count_plus_half": ("Arith", "Count", "LitFloat")}
# ---- D: SKIP / LIMIT values
PAGES = {"lit_2": ("LitInt", 2), "lit_-1": ("LitInt", -1), "int_2": ("Int", 2), "int_-1": ("Int", -1),
         "float_1.5": ("Float", 1.5), "float_2.0": ("Float", 2.0), "str_2": ("Str", "2"), "str_-1": ("Str", "-1"),
         "str_x": ("Str", "x"), "bool_true": ("Bool", True), "bool_false": ("Bool", False), "null": ("Null", None),
         "missing": ("Missing", None)}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- port of cypher_clauses.rs
def mark(kind, m):
    if kind == "Int":
        return "Plain" if m.get("int_unmarked") else "N"
    return "D" if kind == "Float" else "Plain"


def key_of(ex, op, m):
    if ex == "Native":
        return "Text" if m.get("native_text_key") else "Typed"
    if m.get("group_by_typed"):
        return "Typed"
    if m.get("return_distinct_text"):
        return "Text"
    return "Typed" if op == "ReturnDistinct" else "Text"


def together(ex, op, a, b, m):
    (ka, _, ta), (kb, _, tb) = VALS[a], VALS[b]
    if key_of(ex, op, m) == "Text":
        return ta == tb
    return mark(ka, m) == mark(kb, m) and ta == tb


def operand_type(o, m):
    if o == "LitFloat":
        return "Int" if m.get("float_literal_int") else "Float"
    if o == "SumProp":
        return "Unknown" if m.get("prop_default_unknown") else "Int"
    if o == "Count":
        return "Int"
    return "Unknown"


def answered(col, h, m):
    kind, l, r = COLS_B[col]
    if kind == "BareSum":
        return h
    lt, rt = operand_type(l, m), operand_type(r, m)
    t = "Float" if "Float" in (lt, rt) else ("Int" if lt == rt == "Int" else "Unknown")
    if t == "Int" and not m.get("int_read_exact"):
        if h % 2 == 0:
            return h
        lo = (h - 1) // 2
        return 2 * (lo if lo % 2 == 0 else lo + 1)
    return h


def union_dec(first, rest, m):
    if m.get("union_keeps_decoders"):
        return first
    if m.get("union_drops_bool"):
        return "Plain"
    return "Bool" if first == "Bool" and all(r == "Bool" for r in rest) else "Plain"


def read(dec, raw, m):
    k, v = raw
    if k == "Marked":
        return ["number", v] if (dec == "Typed" and not m.get("typed_read_plain")) else ["marked_text", v]
    if k == "Text":
        return ["text", v]
    return ["bool", v != 0] if dec == "Bool" else ["number", v]


def raw_lit_bool(b, m):
    return ("Text" if m.get("bool_literal_text") else "Num", 1 if b else 0)


def built_validate(i, m):
    return ["rows", i] if (i >= 0 or m.get("page_no_negative_check")) else "NegativeIntegerArgument"


def as_built_page(kind, v, m):
    if m.get("page_int_only") and kind not in ("LitInt", "Int", "Missing"):
        return "InvalidArgumentType"
    if kind in ("LitInt", "Int"):
        return built_validate(v, m)
    if kind in ("Missing", "Null"):
        return "NotProvided"
    if kind == "Float":
        if v != int(v) and not m.get("page_no_fraction_check"):
            return "InvalidArgumentType"
        return built_validate(int(v), m)
    if kind == "Str":
        try:
            return built_validate(int(v), m)
        except ValueError:
            return "RawValueError"
    if kind == "Bool":
        return ["rows", 1 if v else 0]


def prepares(shape, in_union, m):
    branch_field = bool(m.get("count_guard_sees_union"))
    shortcut = shape == "LoneLabelCount" and not branch_field
    newline = True if m.get("shortcut_newline_from") else not shortcut
    if m.get("ensure_from_always"):
        shortcut_alone = shape == "LoneLabelCount"
        return True if m.get("shortcut_newline_from") else not shortcut_alone
    return newline if in_union else True


def reads_existing(v, f, m):
    if f == "Type":
        return v == "MatchedEdge" if m.get("type_reads_alias") else True
    return True if m.get("endpoint_reads_json") else v == "MatchedEdge"


def delete_out(detach, out_e, in_e, m):
    if m.get("delete_no_check"):
        return "Deleted"
    touching = out_e if m.get("delete_outgoing_only") else out_e + in_e
    return "Refused" if (not detach and touching > 0) else "Deleted"


def as_built_opt(c, outer_missing, m):
    accepts = True if m.get("iris_accepts_outer_on") else c not in ("OuterArith", "OuterOrOpt")
    if c != "OptOnly" and not accepts:
        return "Refused"
    if m.get("opt_cond_in_where"):
        return "Dropped"
    guarded = c in ("EqProps", "NeProps", "OuterLitAndOpt") or (c == "RangeProps" and m.get("range_guarded"))
    if guarded and not m.get("opt_guard_in_on") and outer_missing:
        return "Dropped"
    return "KeptWithNull"


DELETES = {"out_only": (1, 0), "in_only": (0, 1), "both": (1, 1), "none": (0, 0)}


def path_fn(pat, hops, row, f, anchor_null, m):
    """cypher_clauses.rs as_built_path_fn; row = None (unmatched) or the bound length."""
    if anchor_null and not m.get("anchor_null_ignored"):
        return None
    from_pattern = (f == "Length") and ((pat == "Fixed" and not m.get("fixed_length_from_row")) or
                                        (pat == "VarLen" and m.get("varlen_length_from_pattern")))
    if from_pattern:
        return hops if pat == "Fixed" else None
    if row is None:
        return None
    return {"Length": row, "Nodes": ["list", row + 1], "Rels": ["list", row]}[f]


def predict(m):
    out = {}
    for a, b in PAIRS:
        out[f"A_{a}_{b}_sql_group"] = together("Sql", "GroupBy", a, b, m)
        out[f"A_{a}_{b}_sql_countd"] = together("Sql", "CountDistinct", a, b, m)
        out[f"A_{a}_{b}_sql_distinct"] = together("Sql", "ReturnDistinct", a, b, m)
        out[f"A_{a}_{b}_native_group"] = together("Native", "GroupBy", a, b, m)
    for ds, (vs, fs) in DATA_B.items():
        for col in COLS_B:
            h = {"sumv_plus_sumf": 2 * sum(vs) + int(2 * sum(fs)), "sumf_plus_sumv": 2 * sum(vs) + int(2 * sum(fs)),
                 "sumv_plus_half": 2 * sum(vs) + 1, "bare_sumf": int(2 * sum(fs)), "count_plus_half": 2 * len(vs) + 1}[col]
            out[f"B_{ds}_{col}"] = answered(col, h, m)
    out["B_rel_w_plus_weight"] = answered("sumv_plus_sumf", 7, m)
    out["C_union_stored_int"] = read(union_dec("Typed", ["Plain"], m), ("Marked", 1), m)
    out["C_union_all_stored_int"] = read(union_dec("Typed", ["Typed"], m), ("Marked", 1), m)
    out["C_single_stored_int"] = read("Typed", ("Marked", 1), m)
    out["C_union_bools"] = [read(union_dec("Bool", ["Bool"], m), raw_lit_bool(b, m), m) for b in (True, False)]
    out["C_dedup_stored_vs_literal_rows"] = 1 if ("Marked", 1) == ("Num", 1) else 2
    out["C_dedup_one_vs_true_rows"] = 1 if ("Num", 1) == raw_lit_bool(True, m) else 2
    for k, (kind, v) in PAGES.items():
        out[f"D_{k}"] = as_built_page(kind, v, m)
    out["E_count_union_all"] = prepares("LoneLabelCount", True, m)
    out["E_count_union"] = prepares("LoneLabelCount", True, m)
    out["E_count_alone"] = prepares("LoneLabelCount", False, m)
    out["E_other_union_all"] = prepares("Other", True, m)
    for f in ("StartNode", "EndNode", "Type"):
        out[f"F_var_{f}"] = reads_existing("PathElement", f, m)
        out[f"F_fixed_{f}"] = reads_existing("PathElement", f, m)
        out[f"F_matched_{f}"] = reads_existing("MatchedEdge", f, m)
    for k, (o, i) in DELETES.items():
        out[f"G_delete_{k}"] = delete_out(False, o, i, m)
        out[f"G_detach_{k}"] = delete_out(True, o, i, m)
    out["G_delete_cross_graph"] = delete_out(False, 0, 0, m)
    for k in OPT_CONDS:
        out[f"H_{k}_missing"] = as_built_opt(k, True, m)
    for k in ("OptOnly", "EqProps", "OuterLitAndOpt"):
        out[f"H_{k}_present"] = as_built_opt(k, False, m)
    for k, (pat, hops, anchor, rows, f) in PATH_CASES.items():
        vals = [path_fn(pat, hops, r, f, anchor is None, m) for r in (rows or [None])]
        out[f"I_{k}"] = vals
        if k == "fix1_unmatched_len":
            out[f"I_{k}_native_on"] = vals
    return out


def main():
    t0 = time.time()
    from iris_vector_graph.cypher.parser import parse_query
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = runtime.engine(c); en = IRISGraphEngine(c, embedding_dimension=768)
    native_declined = []

    def run(q, params=None):
        try:
            r = e.execute_cypher(q, params or {})
            if getattr(r, "error", None):
                return None, str(r.error)
            return [list(x) for x in r.rows], None
        except Exception as x:
            return None, f"{type(x).__name__}: {x}"

    got = {}
    # A: one label per pair, two API-written nodes
    for a, b in PAIRS:
        L = f"I54K{TAG}{a}{b}"
        for i, name in enumerate((a, b)):
            e.create_node(f"{P}{a}{b}{i}", labels=[L], properties={"k": VALS[name][1]})
        rows, err = run(f"MATCH (n:{L}) RETURN n.k AS k, count(*) AS c")
        got[f"A_{a}_{b}_sql_group"] = (len(rows) == 1) if rows is not None else f"error:{err}"
        rows, err = run(f"MATCH (n:{L}) RETURN count(DISTINCT n.k)")
        got[f"A_{a}_{b}_sql_countd"] = (rows[0][0] == 1) if rows is not None else f"error:{err}"
        rows, err = run(f"MATCH (n:{L}) RETURN DISTINCT n.k AS k")
        got[f"A_{a}_{b}_sql_distinct"] = (len(rows) == 1) if rows is not None else f"error:{err}"
        q = f"MATCH (n:{L}) RETURN n.k AS k, count(*) AS c"
        nr = en._try_native(parse_query(q), {})
        if nr is None:
            native_declined.append(q); got[f"A_{a}_{b}_native_group"] = "declined"
        else:
            got[f"A_{a}_{b}_native_group"] = len(nr[1].rows) == 1
    # B
    for ds, (vs, fs) in DATA_B.items():
        L = f"I54K{TAG}{ds}"
        for i, v in enumerate(vs):
            e.create_node(f"{P}{ds}{i}", labels=[L], properties={"v": v, "f": fs[i]})
        exprs = {"sumv_plus_sumf": "sum(n.v) + sum(n.f)", "sumf_plus_sumv": "sum(n.f) + sum(n.v)",
                 "sumv_plus_half": "sum(n.v) + 0.5", "bare_sumf": "sum(n.f)", "count_plus_half": "count(*) + 0.5"}
        for col, ex in exprs.items():
            rows, err = run(f"MATCH (n:{L}) RETURN {ex}")
            got[f"B_{ds}_{col}"] = round(2 * rows[0][0]) if rows is not None else f"error:{err}"
    e.create_node(P + "r1", labels=[f"I54K{TAG}R"]); e.create_node(P + "r2", labels=[f"I54K{TAG}R"]); e.create_node(P + "r3", labels=[f"I54K{TAG}R"])
    e.create_edge(P + "r1", f"KK{TAG}", P + "r2", qualifiers={"w": 1}); e.create_edge(P + "r1", f"KK{TAG}", P + "r3", weight=2.5)
    rows, err = run(f"MATCH (a {{id: '{P}r1'}})-[r:KK{TAG}]->() RETURN sum(r.w) + sum(r.weight)")
    got["B_rel_w_plus_weight"] = round(2 * rows[0][0]) if rows is not None else f"error:{err}"

    # C
    LC = f"I54K{TAG}C"; e.create_node(P + "c1", labels=[LC], properties={"v": 1})

    def cls(v):
        if isinstance(v, bool):
            return ["bool", v]
        if isinstance(v, str) and v.startswith("\x01N"):
            return ["marked_text", int(v[2:])]
        if isinstance(v, (int, float)):
            return ["number", v]
        return ["other", repr(v)]
    rows, err = run(f"MATCH (n:{LC}) RETURN n.v AS x UNION RETURN 0 AS x")
    got["C_union_stored_int"] = next((cls(r[0]) for r in rows if r[0] != 0), None) if rows else f"error:{err}"
    rows, err = run(f"MATCH (n:{LC}) RETURN n.v AS x UNION ALL MATCH (n:{LC}) RETURN n.v AS x")
    got["C_union_all_stored_int"] = cls(rows[0][0]) if rows else f"error:{err}"
    rows, err = run(f"MATCH (n:{LC}) RETURN n.v AS x")
    got["C_single_stored_int"] = cls(rows[0][0]) if rows else f"error:{err}"
    rows, err = run("RETURN true AS x UNION ALL RETURN false AS x")
    got["C_union_bools"] = [cls(r[0]) for r in rows] if rows else f"error:{err}"
    rows, err = run(f"MATCH (n:{LC}) RETURN n.v AS x UNION RETURN 1 AS x")
    got["C_dedup_stored_vs_literal_rows"] = len(rows) if rows is not None else f"error:{err}"
    rows, err = run("RETURN 1 AS x UNION RETURN true AS x")
    got["C_dedup_one_vs_true_rows"] = len(rows) if rows is not None else f"error:{err}"

    # D: three nodes, ordered
    LD = f"I54K{TAG}D"
    for i in range(3):
        e.create_node(f"{P}d{i}", labels=[LD], properties={"name": f"d{i}"})
    for k, (kind, v) in PAGES.items():
        if kind == "LitInt":
            q, params = f"MATCH (n:{LD}) RETURN n.name ORDER BY n.name LIMIT {v}", {}
        else:
            q, params = f"MATCH (n:{LD}) RETURN n.name ORDER BY n.name LIMIT $l", ({} if kind == "Missing" else {"l": v})
        rows, err = run(q, params)
        if rows is not None:
            got[f"D_{k}"] = ["rows", len(rows)]
        elif "NegativeIntegerArgument" in err:
            got[f"D_{k}"] = "NegativeIntegerArgument"
        elif "InvalidArgumentType" in err:
            got[f"D_{k}"] = "InvalidArgumentType"
        elif "not provided" in err:
            got[f"D_{k}"] = "NotProvided"
        elif "invalid literal for int()" in err:
            got[f"D_{k}"] = "RawValueError"
        else:
            got[f"D_{k}"] = f"other:{err[:120]}"

    # E
    for k, q in (("E_count_union_all", f"MATCH (n:{LD}) RETURN count(n) AS x UNION ALL RETURN 0 AS x"),
                 ("E_count_union", f"MATCH (n:{LD}) RETURN count(*) AS x UNION RETURN 7 AS x"),
                 ("E_count_alone", f"MATCH (n:{LD}) RETURN count(n) AS x"),
                 ("E_other_union_all", f"MATCH (n:{LD}) RETURN n.name AS x UNION ALL RETURN 'z' AS x")):
        rows, err = run(q)
        got[k] = rows is not None if (rows is not None or "SQLCODE: <-1>" in (err or "")) else f"other:{err[:120]}"

    # F: path a->b->c, API edges
    LF = f"I54K{TAG}F"; KF = f"KF{TAG}"
    for n in ("fa", "fb", "fc"):
        e.create_node(P + n, labels=[LF], properties={"name": n})
    e.create_edge(P + "fa", KF, P + "fb"); e.create_edge(P + "fb", KF, P + "fc")
    fx = {"StartNode": "startNode(r).name", "EndNode": "endNode(r).name", "Type": "type(r)"}
    for f, ex in fx.items():
        for shape, pat in (("var", f"-[:{KF}*1..2]->"), ("fixed", f"-[:{KF}]->")):
            rows, err = run(f"MATCH p = (a:{LF} {{name: 'fa'}}){pat}(c) RETURN [r IN relationships(p) | {ex}]")
            got[f"F_{shape}_{f}"] = rows is not None if (rows is not None or "SQLCODE: <-29>" in (err or "")) else f"other:{err[:120]}"
        rows, err = run(f"MATCH (a:{LF} {{name: 'fa'}})-[r:{KF}]->(b) RETURN {ex}")
        got[f"F_matched_{f}"] = rows is not None if (rows is not None or "SQLCODE: <-29>" in (err or "")) else f"other:{err[:120]}"

    # G: each case on fresh nodes (target t, partner u)
    KG = f"KG{TAG}"
    for detach in (False, True):
        for k, (o, i) in DELETES.items():
            LG = f"I54K{TAG}G{int(detach)}{k}"; t, u, w = f"{P}g{int(detach)}{k}t", f"{P}g{int(detach)}{k}u", f"{P}g{int(detach)}{k}w"
            for n in (t, u, w):
                e.create_node(n, labels=[LG])
            if o:
                e.create_edge(t, KG, u)
            if i:
                e.create_edge(w, KG, t)
            rows, err = run(f"MATCH (n:{LG} {{id: '{t}'}}) {'DETACH ' if detach else ''}DELETE n")
            gone = e.get_node(t) is None
            if err and "Cannot delete node with existing relationships" in err and not gone:
                obs = "Refused"
            elif err is None and gone:
                q = f"MATCH (a {{node_id: '{w}'}})-[:{KG}]->(b) RETURN count(*)"
                nr = en._try_native(parse_query(q), {})
                adj = (nr[1].rows[0][0] if nr is not None else "declined")
                obs = "Deleted" if adj in (0, "declined") else f"Deleted_adjacency_left:{adj}"
            else:
                obs = f"other:{err!r}:{gone}"
            got[f"G_{'detach' if detach else 'delete'}_{k}"] = obs
    # G cross-graph: z in the default graph without edges; z in a named graph with an edge
    NGx = f"i54kg{TAG}"; LZ = f"I54K{TAG}Z"; z = f"{P}z"
    e.create_node(z, labels=[LZ]); e.create_node(z, labels=[LZ + "N"], graph=NGx); e.create_edge(z, KG, P + "zz", graph=NGx)
    rows, err = run(f"MATCH (n:{LZ} {{id: '{z}'}}) DELETE n")
    gone = e.get_node(z) is None
    still_named = e.get_node(z, graph=NGx) is not None
    got["G_delete_cross_graph"] = ("Deleted" if (err is None and gone and still_named) else
                                   "Refused" if (err and "existing relationships" in err and not gone) else f"other:{err!r}:{gone}:{still_named}")
    # H: h3 (no v) and h4 (v 9) each have one optional match that fails every condition
    LH = f"I54K{TAG}H"; KH = f"KH{TAG}"
    e.create_node(P + "h1", labels=[LH], properties={"name": "h1", "v": 1})
    e.create_node(P + "h2", labels=[LH], properties={"name": "h2", "v": 2})
    e.create_node(P + "h3", labels=[LH], properties={"name": "h3"})
    e.create_node(P + "h4", labels=[LH], properties={"name": "h4", "v": 9})
    e.create_edge(P + "h1", KH, P + "h2"); e.create_edge(P + "h2", KH, P + "h3"); e.create_edge(P + "h3", KH, P + "h4"); e.create_edge(P + "h4", KH, P + "h3")
    for k, cond in OPT_CONDS.items():
        rows, err = run(f"MATCH (a:{LH}) OPTIONAL MATCH (a)-[:{KH}]->(b) WHERE {cond} RETURN a.name, b.name")
        if rows is None:
            got[f"H_{k}_missing"] = "Refused" if "SQLCODE: <-94>" in err else f"other:{err[:100]}"
            if k in ("OptOnly", "EqProps", "OuterLitAndOpt"):
                got[f"H_{k}_present"] = got[f"H_{k}_missing"]
            continue
        byname = {}
        for a_, b_ in rows:
            byname.setdefault(a_, []).append(b_)
        # h3 lacks v and its only match (h4, v 9) fails every condition: kept with null, or dropped
        got[f"H_{k}_missing"] = ("KeptWithNull" if byname.get("h3") == [None] else "Dropped" if "h3" not in byname else f"other:{byname.get('h3')}")
        # h4 has v 9 and its only match (h3, no v) fails every condition
        if k in ("OptOnly", "EqProps", "OuterLitAndOpt"):
            got[f"H_{k}_present"] = ("KeptWithNull" if byname.get("h4") == [None] else "Dropped" if "h4" not in byname else f"other:{byname.get('h4')}")
    # I: path functions of a named OPTIONAL path (bug-cyp-146); i1->i2->i3 written by create_edge
    LI = f"I56C{TAG}I"; KI = f"KI{TAG}"
    for n in ("i1", "i2", "i3"):
        e.create_node(P + n, labels=[LI], properties={"name": n})
    e.create_edge(P + "i1", KI, P + "i2"); e.create_edge(P + "i2", KI, P + "i3")
    en_on = IRISGraphEngine(c, embedding_dimension=768, native_cypher=True)

    def path_val(v, f):
        if v is None:
            return None
        if f == "Length":
            return v
        return ["list", len(v)] if isinstance(v, list) else f"other:{v!r}"
    for k, (pat, hops, anchor, rows_, f) in PATH_CASES.items():
        pattern = {1: f"(a)-[:{KI}]->(b)", 2: f"(a)-[:{KI}]->(b)-[:{KI}]->(c)", None: f"(a)-[:{KI}*1..2]->(b)"}[hops]
        fx = {"Length": "length(p)", "Nodes": "nodes(p)", "Rels": "relationships(p)"}[f]
        head = (f"MATCH (a:{LI} {{name: '{anchor}'}})" if anchor else f"OPTIONAL MATCH (a:{LI} {{name: 'none'}})")
        q = f"{head} OPTIONAL MATCH p = {pattern} RETURN {fx} AS v ORDER BY length(p)"
        rows, err = run(q)
        got[f"I_{k}"] = [path_val(r[0], f) for r in rows] if rows is not None else f"error:{err[:120]}"
        if k == "fix1_unmatched_len":
            try:
                r2 = en_on.execute_cypher(q, {})
                got[f"I_{k}_native_on"] = [path_val(x[0], f) for x in r2.rows]
            except Exception as x:
                got[f"I_{k}_native_on"] = f"error:{x}"
    c.close()

    norm = lambda d: json.loads(json.dumps(d))
    got = norm(got); want = norm(predict({}))
    mism = [{"case": k, "observed": got.get(k), "expected": want[k]} for k in want if got.get(k) != want[k]]
    sens = {mm: sum(1 for k, v in norm(predict({mm: True})).items() if v != got.get(k)) for mm in MUTS}
    tampered = dict(got); tampered["B_b13_sumv_plus_sumf"] = 13
    tamper_detected = any(tampered.get(k) != want[k] for k in want)
    tampered_i = dict(got); tampered_i["I_fix1_unmatched_len"] = [None]   # the repaired answer must be detected too
    tamper_detected = tamper_detected and any(tampered_i.get(k) != want[k] for k in want)
    body = {"kind": "binding", "model": "cypher_clauses", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES",
            "cases": len(want), "mismatches": mism, "observed": got, "native_declined": len(native_declined),
            "native_declined_queries": native_declined[:6],
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q_.relative_to(REPO)): sha(q_) for q_ in [HERE / "binding.py", HERE / "cypher_clauses.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/cypher/translator.py", "iris_vector_graph/_engine/query.py",
                                                                   "iris_vector_graph/stores/iris_sql_store.py", "iris_src/src/Graph/KG/Cypher/Exec.cls"]}},
            "scope": "Actual execute_cypher on IRIS 2026.1 (pin 3eaa79cf), driver 5.3.2, data written by create_node/create_edge in the "
                     "default single-edge graph (one named graph for the cross-graph DELETE): A 10 stored-value pairs (integer, string, "
                     "boolean, list kinds) under GROUP BY, count(DISTINCT), RETURN DISTINCT on the SQL path and GROUP BY on the native "
                     "executor; B 4 datasets x 5 aggregate columns plus a relationship sum pair; C UNION / UNION ALL of a stored integer, "
                     "booleans and duplicate removal; D 13 SKIP/LIMIT values (literal and parameter kinds); E a whole-label count as a "
                     "UNION branch and its neighbors; F startNode/endNode/type of relationships(p) elements (fixed and variable length) "
                     "and of a matched edge; G DELETE and DETACH DELETE over out-only, in-only, both and no edges (adjacency read by the "
                     "native walk), and a default-graph DELETE of an id a named graph also holds with an edge; H a WHERE inside OPTIONAL MATCH in seven "
                     "shapes, on a node lacking the property the condition reads and on one that has it, with no passing match; I (iteration 56) "
                     "length/nodes/relationships of a named OPTIONAL path, fixed (1 and 2 hops) and variable-length, unmatched, matched and "
                     "under a null anchor, plus the native-on engine for the unmatched fixed length."}
    d = REPO / ".g5/Verus_verification/results/cypher_clauses" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "native_declined", "all_sensitivities_detected", "sensitivities_detected_cases", "observation_tamper_detected", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
