// product 3eaa79cf: Cypher expressions whose argument is known only at run time (W55, iteration 48).
//   Translator choices (iris_vector_graph/cypher/translator.py): _expr_slice 23679-23791 (slice bounds);
//   translate_boolean_expression 18638 / _translate_boolean_expression 18651-18716 (a CASE WHEN or WHERE condition);
//   _create_resolve_prop_value 9594-9671 with _fold_constant 9319 / _fold_or_raise 9543 (a node CREATE map value,
//   called from _create_node_literal 9726, _create_node_from_alias 9812, _create_node_per_row 10002);
//   _create_clause_relationship_entry 10183-10246 (a relationship CREATE map value between new nodes; a parameter too);
//   _expr_case 22189-22238 (a simple CASE's WHENs by static kind); engine.py IRISGraphEngine._prop_set_deployed 1762-1781;
//   _is_typed_coalesce 7620 / _scalar_coalesce 24455 (coalesce's result type); _scalar_string 24475-24494 (substring);
//   _prop_set 12961 (a node property UPDATE). Parser: iris_vector_graph/cypher/parser.py Parser.parse_primary_expression
//   1621-1641 (an identifier followed by `.`). ObjectScript: Graph.KG.SqlProcs.PropSet (Prop_Set) forwarding to
//   Graph.KG.PropWrite.SetVal. Reader: the execute_cypher result row (SQL path; the native executor declines these
//   shapes on the fixture) and, for writes, a later MATCH ... RETURN and get_node().
use vstd::prelude::*;
verus! {

/// How an argument reaches the translator: its syntax, which is what the translator decides on.
pub enum Syntax { Literal, PropertyRead, MapAccess, Comparison, RowVar, Param }

// ---------------------------------------------------------------- list slices
/// A list slice's answer: the elements at positions [from, to) of the list (empty when to <= from).
pub struct Slice { pub from: int, pub to: int }

pub open spec fn same_elements(a: Slice, b: Slice) -> bool {
    (a.to <= a.from && b.to <= b.from) || (a.from == b.from && a.to == b.to)
}
pub open spec fn clamp(x: int, len: int) -> int { if x < 0 { 0 } else if x > len { len } else { x } }
/// openCypher (TCK List2): a negative bound counts from the end; bounds are clamped to the list.
pub open spec fn rule_pos(x: int, len: int) -> int {
    if x < 0 { if len + x > 0 { len + x } else { 0 } } else if x > len { len } else { x }
}
pub open spec fn rule_slice(len: int, s: int, e: int) -> Slice { Slice { from: rule_pos(s, len), to: rule_pos(e, len) } }

/// The bound's SQL in _expr_slice. A literal negative bound is GREATEST(0, JSON_ARRAYLENGTH(l) + n); a literal
/// non-negative bound is n; any other bound is its translated value as it is.
pub open spec fn translated_bound(syn: Syntax, n: int, len: int) -> int {
    match syn {
        Syntax::Literal => if n < 0 { if len + n > 0 { len + n } else { 0 } } else { n },
        _ => n,
    }
}
/// _slice_sql keeps the elements whose 1-based row number rn satisfies rn > start AND rn <= end, i.e. the 0-based
/// positions i with start <= i < end inside the list. (Two literal non-negative bounds with end <= start take the
/// fast path to the empty list, which is the same answer.)
pub open spec fn as_built_slice(syn: Syntax, len: int, s: int, e: int) -> Slice {
    Slice { from: clamp(translated_bound(syn, s, len), len), to: clamp(translated_bound(syn, e, len), len) }
}

/// A list value: null, or a list of that length.
pub enum ListIn { Null, Of(int) }
pub enum SliceOut { Null, Elems(Slice) }
/// _expr_slice / _slice_sql read the list through JSON_TABLE and test only an explicit null bound for null: a null list
/// has no rows to keep, so the aggregate answers the empty list.
pub open spec fn as_built_slice_of(syn: Syntax, l: ListIn, s: int, e: int) -> SliceOut {
    match l { ListIn::Null => SliceOut::Elems(Slice { from: 0, to: 0 }), ListIn::Of(len) => SliceOut::Elems(as_built_slice(syn, len, s, e)) }
}
/// openCypher (TCK List2 and the null rules): slicing a null list gives null.
pub open spec fn rule_slice_of(l: ListIn, s: int, e: int) -> SliceOut {
    match l { ListIn::Null => SliceOut::Null, ListIn::Of(len) => SliceOut::Elems(rule_slice(len, s, e)) }
}
/// Iteration 50 (new, bug-cyp-129; review m1): `n.missing[0..2]` answers [] for every bound syntax and value.
pub proof fn theorem_null_list_slice_is_empty(syn: Syntax, s: int, e: int)
    ensures as_built_slice_of(syn, ListIn::Null, s, e) == SliceOut::Elems(Slice { from: 0, to: 0 }),
            rule_slice_of(ListIn::Null, s, e) == SliceOut::Null,
{}

/// Neighbor: literal bounds of any sign follow the rule, for every list length.
pub proof fn theorem_literal_slice_follows_rule(len: int, s: int, e: int)
    requires len >= 0,
    ensures same_elements(as_built_slice(Syntax::Literal, len, s, e), rule_slice(len, s, e)),
{}
/// Neighbor: non-negative run-time bounds (UNWIND row, WITH column, parameter) follow the rule.
pub proof fn theorem_row_nonnegative_slice_follows_rule(syn: Syntax, len: int, s: int, e: int)
    requires len >= 0, s >= 0, e >= 0,
    ensures same_elements(as_built_slice(syn, len, s, e), rule_slice(len, s, e)),
{}
/// W55 L1 (new finding): a negative run-time bound is clamped to 0 instead of counting from the end. For every list
/// of length len and 0 < k < len, `l[-k..len]` from a row answers the whole list (rule: the last k elements) and
/// `l[0..-k]` answers [] (rule: the first len - k elements).
pub proof fn theorem_row_negative_slice_departs(len: int, k: int)
    requires 0 < k, k < len,
    ensures
        as_built_slice(Syntax::RowVar, len, -k, len) == (Slice { from: 0, to: len }),
        rule_slice(len, -k, len) == (Slice { from: len - k, to: len }),
        !same_elements(as_built_slice(Syntax::RowVar, len, -k, len), rule_slice(len, -k, len)),
        as_built_slice(Syntax::Param, len, 0, -k).to <= as_built_slice(Syntax::Param, len, 0, -k).from,
        !same_elements(as_built_slice(Syntax::Param, len, 0, -k), rule_slice(len, 0, -k)),
{}

// ---------------------------------------------------------------- a boolean as a CASE WHEN / WHERE condition
/// The SQL a condition becomes: a predicate, or the value's own scalar in a predicate position.
pub enum CondSql { Predicate, RawScalar }
/// _translate_boolean_expression: a boolean literal folds to (1=1)/(1=0); a property read becomes _stored_bool_in(...);
/// a map access `= 'true'`; a comparison its predicate; a bare row variable or parameter falls through to
/// translate_expression, its scalar.
pub open spec fn condition_sql(syn: Syntax) -> CondSql {
    match syn {
        Syntax::RowVar => CondSql::RawScalar,
        Syntax::Param => CondSql::RawScalar,
        _ => CondSql::Predicate,
    }
}
/// Provider premise observed on IRIS 2026.1: a scalar in a CASE WHEN or WHERE predicate position fails at Prepare
/// (SQLCODE -14, "A comparison operator is required here").
pub open spec fn iris_accepts_scalar_condition() -> bool { false }
pub enum CaseOut { Branch(bool), PrepareFails }
pub open spec fn case_when(syn: Syntax, v: bool) -> CaseOut {
    match condition_sql(syn) {
        CondSql::Predicate => CaseOut::Branch(v),
        CondSql::RawScalar => if iris_accepts_scalar_condition() { CaseOut::Branch(v) } else { CaseOut::PrepareFails },
    }
}
/// openCypher: CASE WHEN b takes the branch exactly when b is true.
pub open spec fn rule_case_when(v: bool) -> CaseOut { CaseOut::Branch(v) }

/// W55 C4 (new finding): a boolean from an UNWIND row, a WITH column or a parameter as a condition fails the query.
pub proof fn theorem_row_boolean_condition_fails(v: bool)
    ensures
        case_when(Syntax::RowVar, v) == CaseOut::PrepareFails,
        case_when(Syntax::Param, v) == CaseOut::PrepareFails,
        rule_case_when(v) != CaseOut::PrepareFails,
{}
/// Neighbor: a stored boolean property, a literal and a comparison (`f = true`, the known-issues workaround) follow the rule.
pub proof fn theorem_predicate_condition_follows_rule(v: bool)
    ensures
        case_when(Syntax::PropertyRead, v) == rule_case_when(v),
        case_when(Syntax::Literal, v) == rule_case_when(v),
        case_when(Syntax::Comparison, v) == rule_case_when(v),
{}

// ---------------------------------------------------------------- simple CASE across value kinds
pub enum Kind { Num, Str }
/// A value: its kind and its text (numbered). The domain is numbers in canonical spelling and strings that spell one.
pub struct V { pub kind: Kind, pub text: int }
/// _static_value_kind knows the kind only of a literal (a property, a row variable or a parameter is unknown).
pub open spec fn kind_known(syn: Syntax) -> bool { syn == Syntax::Literal }
/// Provider (IRIS SQL, observed on 2026.1): `CASE x WHEN y` compares a number with text that spells it as equal.
pub open spec fn sql_case_eq(t: V, w: V) -> bool { t.text == w.text }
/// _expr_case for `CASE test WHEN w ...`: a WHEN is dropped when both kinds are known and differ; every other WHEN is
/// left to SQL's comparison.
pub open spec fn simple_case_takes(ts: Syntax, t: V, ws: Syntax, w: V) -> bool {
    if kind_known(ts) && kind_known(ws) && t.kind != w.kind { false } else { sql_case_eq(t, w) }
}
/// openCypher and query.values.equality: the WHEN is taken when the test equals it; '1' does not equal 1.
pub open spec fn rule_simple_case(t: V, w: V) -> bool { t.kind == w.kind && t.text == w.text }

/// Iteration 50 (new, bug-cyp-127; review 47-49 item 7): with a test from a property or a row, `CASE n.s1 WHEN 1`
/// takes the branch for the string '1', and `CASE n.i1 WHEN '1'` for the integer 1.
pub proof fn theorem_simple_case_coerces_across_kinds(ts: Syntax, t: V, w: V)
    requires !kind_known(ts), t.kind != w.kind, t.text == w.text,
    ensures simple_case_takes(ts, t, Syntax::Literal, w), !rule_simple_case(t, w),
{}
/// Neighbors: a literal test against a literal WHEN, and any test against a WHEN of the same kind, follow the rule.
pub proof fn theorem_simple_case_same_kind_or_literal_follows_rule(ts: Syntax, t: V, w: V)
    ensures
        simple_case_takes(Syntax::Literal, t, Syntax::Literal, w) == rule_simple_case(t, w),
        t.kind == w.kind ==> simple_case_takes(ts, t, Syntax::Literal, w) == rule_simple_case(t, w),
{}

// ---------------------------------------------------------------- a function value in a CREATE map
/// A CREATE map value that is a function call, by function and argument type.
pub enum Fn { ToUpper, ToLower, Trim, Coalesce, ToStringFn, ToIntegerOfNumber, ToFloatOfNumber, Arith,
              ToIntegerOfString, Size, Abs, RandomUuid, Rand, Substring, Replace }
/// _fold_constant works out coalesce, the case and trim functions (_FOLDED_STRING_FNS), toString, toFloat and
/// toInteger of a number, and arithmetic over literals, parameters and UNWIND literals; anything else is _NOT_CONSTANT.
pub open spec fn folds(f: Fn) -> bool {
    match f {
        Fn::ToUpper | Fn::ToLower | Fn::Trim | Fn::Coalesce | Fn::ToStringFn | Fn::ToIntegerOfNumber
        | Fn::ToFloatOfNumber | Fn::Arith => true,
        _ => false,
    }
}
pub enum WriteOut { Written, RefusedNothingWritten, WrittenWithoutProperty }
/// Provider premise observed on IRIS 2026.1 (intersystems-irispython): binding an AST object as a statement argument
/// raises `<LIST ERROR> Cannot write argument in list`; the write transaction then takes back everything.
pub open spec fn driver_accepts_ast() -> bool { false }
/// _create_resolve_prop_value: a folded value is bound as itself; an unfolded call is returned as the AST, which the
/// node INSERT binds.
pub open spec fn create_node_value(f: Fn) -> WriteOut {
    if folds(f) { WriteOut::Written } else if driver_accepts_ast() { WriteOut::Written } else { WriteOut::RefusedNothingWritten }
}
/// SET n.p = f(...): the value's SQL goes into the UPDATE (through Prop_Set), whatever the function.
pub open spec fn set_value(f: Fn) -> WriteOut { WriteOut::Written }
/// A relationship CREATE map value: a literal, a FOREACH/UNWIND literal variable, a parameter (`$k`), or a call.
pub enum RelValue { Lit, ForeachVar, Param, Call(Fn) }
/// _create_clause_relationship_entry (literal endpoints, translator.py 10213-10226): a Literal is kept, a FOREACH/UNWIND
/// literal variable is looked up, and any other expression, an ast.Parameter included, becomes None; "null props are
/// not stored", so the edge is inserted without it.
pub open spec fn create_rel_value(v: RelValue) -> WriteOut {
    match v {
        RelValue::Lit => WriteOut::Written,
        RelValue::ForeachVar => WriteOut::Written,
        RelValue::Param => WriteOut::WrittenWithoutProperty,
        RelValue::Call(_) => WriteOut::WrittenWithoutProperty,
    }
}
/// The neighbors a caller compares with: a node CREATE binds a parameter value, and a relationship CREATE between
/// matched nodes (the alias path) writes a literal or a parameter.
pub open spec fn create_node_param() -> WriteOut { WriteOut::Written }
pub open spec fn create_rel_matched_value(v: RelValue) -> WriteOut {
    match v { RelValue::Lit | RelValue::ForeachVar | RelValue::Param => WriteOut::Written, RelValue::Call(_) => WriteOut::RefusedNothingWritten }
}
/// openCypher: a CREATE stores each property value the map computes.
pub open spec fn rule_write() -> WriteOut { WriteOut::Written }

/// W55 W2/W3 (new finding, extends bug-cyp-114): a node CREATE map value from a function the folder does not work out
/// (size, abs, toInteger of a string, randomUUID, rand, substring, replace) is refused with nothing written.
pub proof fn theorem_unfolded_create_value_refused(f: Fn)
    requires !folds(f),
    ensures create_node_value(f) == WriteOut::RefusedNothingWritten, create_node_value(f) != rule_write(),
{}
/// Neighbor: a folded function value (toUpper, as observed) is written, and SET writes any function value.
pub proof fn theorem_folded_create_value_written(f: Fn)
    ensures
        create_node_value(Fn::ToUpper) == rule_write(),
        folds(f) ==> create_node_value(f) == rule_write(),
        set_value(f) == rule_write(),
{}
/// W55 follow-up (new finding): a relationship CREATE between new nodes drops every computed property value, folded
/// or not, and reports success.
pub proof fn theorem_inline_rel_expression_dropped(f: Fn)
    ensures create_rel_value(RelValue::Call(f)) == WriteOut::WrittenWithoutProperty,
            create_rel_value(RelValue::Call(f)) != rule_write(),
{}
/// Iteration 50 (bug-cyp-120, widened; review 47-49 item 5): `CREATE (a {id: ...})-[r {k: $k}]->(b {id: ...})` stores the
/// relationship without k, while the same parameter is written on a node and between matched nodes.
pub proof fn theorem_inline_rel_param_dropped()
    ensures
        create_rel_value(RelValue::Param) == WriteOut::WrittenWithoutProperty,
        create_rel_value(RelValue::Param) != rule_write(),
        create_node_param() == rule_write(),
        create_rel_matched_value(RelValue::Param) == rule_write(),
{}
/// Neighbor: a literal or an UNWIND literal variable is stored.
pub proof fn theorem_inline_rel_literal_written()
    ensures create_rel_value(RelValue::Lit) == rule_write(), create_rel_value(RelValue::ForeachVar) == rule_write(),
{}

// ---------------------------------------------------------------- coalesce's result type
/// The kind of one coalesce() argument.
pub enum CoArg { NodeProp, ScalarLiteral, ListLiteral, ScalarParam, RowVar }
/// _is_typed_coalesce: typed (read through CY_TYPED) when some argument is a node property and every other is a
/// node property, a scalar literal or a scalar parameter; otherwise _scalar_coalesce CASTs the first argument (and
/// any later non-string literal) to VARCHAR.
pub open spec fn scalar_ok(x: CoArg) -> bool {
    x == CoArg::NodeProp || x == CoArg::ScalarLiteral || x == CoArg::ScalarParam
}
pub open spec fn typed_coalesce(a: CoArg, b: CoArg) -> bool {
    (a == CoArg::NodeProp || b == CoArg::NodeProp) && scalar_ok(a) && scalar_ok(b)
}
pub enum Out { Int, Text }
/// The type a reader gets for coalesce(a, b) when the winning value is an integer.
pub open spec fn coalesce_number(a: CoArg, b: CoArg) -> Out { if typed_coalesce(a, b) { Out::Int } else { Out::Text } }

/// W55 C3 follow-up (new finding): coalesce over row values, literals or parameters answers a number as text.
pub proof fn theorem_row_coalesce_number_as_text()
    ensures
        coalesce_number(CoArg::RowVar, CoArg::ScalarLiteral) == Out::Text,
        coalesce_number(CoArg::ScalarLiteral, CoArg::ScalarLiteral) == Out::Text,
        coalesce_number(CoArg::ScalarParam, CoArg::ScalarLiteral) == Out::Text,
{}
/// Neighbor: with a node property among scalar arguments the stored type is kept.
pub proof fn theorem_node_coalesce_keeps_type(b: CoArg)
    requires b != CoArg::ListLiteral, b != CoArg::RowVar,
    ensures coalesce_number(CoArg::NodeProp, b) == Out::Int, coalesce_number(b, CoArg::NodeProp) == Out::Int,
{}

// ---------------------------------------------------------------- the parser: a slice's lower bound
pub enum Lower { IntLiteral, Identifier, Subscript, Param }
/// What follows `..` in the slice: an integer (`a..3`), an identifier (`a..b`) or the closing bracket (`a..]`).
pub enum Upper { Int, Ident, Close }
pub enum Tok { Dot, FloatLit, Ident, Other }
/// The lexer, as observed: after `a`, `..3` is DOT then FLOAT('.3'); `..b` and `..]` are DOT then DOT.
pub open spec fn tokens_after_lower(u: Upper) -> (Tok, Tok) {
    match u { Upper::Int => (Tok::Dot, Tok::FloatLit), Upper::Ident => (Tok::Dot, Tok::Dot), Upper::Close => (Tok::Dot, Tok::Dot) }
}
/// Parser.parse_primary_expression after an identifier (parser.py 1621-1641): `matches(DOT)` is taken as a property
/// access, then `expect(IDENTIFIER)`, so the token after the dot must be an identifier. (Iteration 50: decided from the
/// tokens, replacing the premise constant `identifier_branch_looks_ahead`.)
pub open spec fn identifier_branch_parses(next: Tok, after: Tok) -> bool {
    if next == Tok::Dot { after == Tok::Ident } else { true }
}
/// An integer, a subscript or a parameter lower bound reaches the postfix loop of parse_power_expression, which looks
/// ahead for the second dot.
pub open spec fn parses(lo: Lower, u: Upper) -> bool {
    match lo {
        Lower::Identifier => { let (n, a) = tokens_after_lower(u); identifier_branch_parses(n, a) },
        _ => true,
    }
}
/// W55 L1 follow-up (bug-cyp-122): `l[a..3]`, `l[a..b]`, `l[a..]` with an identifier lower bound do not parse.
pub proof fn theorem_identifier_lower_bound_refused(u: Upper)
    ensures !parses(Lower::Identifier, u),
{}
/// Neighbor: an integer, a subscript or a parameter lower bound parses, whatever follows.
pub proof fn theorem_other_lower_bounds_parse(u: Upper)
    ensures parses(Lower::IntLiteral, u), parses(Lower::Subscript, u), parses(Lower::Param, u),
{}

// ---------------------------------------------------------------- substring() with a negative start
pub enum SubOut { Chars(int, int), Error }   // Chars(first 0-based position, count)
/// _scalar_string: substring(s, start, len) is SQL SUBSTRING(s, (start) + 1, len), with no check of start. IRIS
/// SUBSTRING(s, p, l) over a string of n characters returns positions max(1, p) .. min(n, p + l - 1).
pub open spec fn iris_substring(n: int, p: int, l: int) -> SubOut {
    let lo = if p < 1 { 1 } else { p };
    let hi = if p + l - 1 > n { n } else { p + l - 1 };
    SubOut::Chars(lo - 1, if hi >= lo { hi - lo + 1 } else { 0 })
}
pub open spec fn as_built_substring(n: int, start: int, l: int) -> SubOut { iris_substring(n, start + 1, l) }
/// openCypher (Cypher 9 reference): a negative start or length is an error; otherwise the characters from start,
/// at most l of them.
pub open spec fn rule_substring(n: int, start: int, l: int) -> SubOut {
    if start < 0 || l < 0 { SubOut::Error } else {
        let from = if start > n { n } else { start };
        let to = if start + l > n { n } else { start + l };
        SubOut::Chars(from, to - from)
    }
}
/// W55 S2 (new finding): a negative start answers the leading characters instead of an error, for every string and
/// length: substring(s, -k, l) answers the first l - k characters (for k < l <= n + k).
pub proof fn theorem_negative_start_answers_prefix(n: int, k: int, l: int)
    requires 0 < k, k < l, l - k <= n,
    ensures as_built_substring(n, -k, l) == SubOut::Chars(0, l - k), rule_substring(n, -k, l) == SubOut::Error,
{}
/// Neighbor: a start and length inside the string follow the rule (a literal or a run-time argument alike).
pub proof fn theorem_inside_substring_follows_rule(n: int, start: int, l: int)
    requires 0 <= start, 1 <= l, start + l <= n,
    ensures as_built_substring(n, start, l) == rule_substring(n, start, l),
{}

// ---------------------------------------------------------------- Prop_Set: a node property UPDATE that retypes
/// A stored node value: its text (abstracted to a number) and whether it is held as a number.
pub struct Stored { pub text: int, pub num: bool }
/// Provider premise (measured by the product on IRIS 2026.3, KNOWN_ISSUES and PropWrite.cls; consistent with the
/// fixture): IRIS's filer writes no value whose text equals the stored one.
pub open spec fn filer_writes_same_text() -> bool { false }
pub open spec fn filer_update(old: Stored, new: Stored) -> Stored {
    if old.text == new.text && !filer_writes_same_text() { old } else { new }
}
/// Graph.KG.PropWrite.SetVal (SQL Graph_KG.Prop_Set(%ID, val, new)): when the new value has the stored text and
/// another type, it writes the new value into the row first; it answers the new value for the UPDATE to file.
pub open spec fn setval(old: Stored, new: Stored) -> Stored {
    if old.text == new.text && old.num != new.num { new } else { old }
}
/// The dictionary read engine._prop_set_deployed makes: the forwarder's PropSet method found, absent, or unreadable
/// (the read raised).
pub enum DictCheck { Found, Absent, Unreadable }
/// engine._prop_set_deployed (engine.py 1762-1781): the cached answer if any (cleared when capabilities are set), else
/// compiled_method_exists(<schema>.<forwarder>, "PropSet"); a dictionary that cannot be read is taken as deployed.
/// (Iteration 50: the member's own logic, replacing the bare `deployed` input.)
pub open spec fn prop_set_deployed(cached: Option<bool>, check: DictCheck) -> bool {
    match cached {
        Some(b) => b,
        None => match check { DictCheck::Found => true, DictCheck::Absent => false, DictCheck::Unreadable => true },
    }
}
/// _prop_set: the UPDATE's SET is Prop_Set(...) when the namespace has it (engine._prop_set_deployed), else the value.
pub open spec fn node_update(deployed: bool, old: Stored, new: Stored) -> Stored {
    if deployed { filer_update(setval(old, new), new) } else { filer_update(old, new) }
}
/// W55 W4 (held): with Prop_Set deployed, SET stores the new value and type for every old and new value
/// (`SET n.age = toInteger(n.age)` over the string '30' stores the integer 30).
pub proof fn theorem_prop_set_retypes(old: Stored, new: Stored)
    ensures node_update(true, old, new) == new,
{}
/// Iteration 50 (review 47-49 item 4): the switch decides the retype. A namespace whose dictionary lacks PropSet keeps a
/// same-text old value; an unreadable dictionary is taken as deployed, so the retype is written (the docstring's choice:
/// a missing function would then fail the write rather than keep the old type silently).
pub proof fn theorem_prop_set_switch_decides_retype(old: Stored, new: Stored)
    requires old.text == new.text, old.num != new.num,
    ensures
        node_update(prop_set_deployed(None, DictCheck::Found), old, new) == new,
        node_update(prop_set_deployed(None, DictCheck::Unreadable), old, new) == new,
        node_update(prop_set_deployed(None, DictCheck::Absent), old, new) == old,
        node_update(prop_set_deployed(Some(false), DictCheck::Found), old, new) == old,
{}
/// Neighbor: on a namespace without Prop_Set (classes before 4.7.0) a same-text retype keeps the old string, as the
/// known-issues guide says; a value with another text is written either way.
pub proof fn theorem_without_prop_set_same_text_keeps_old(old: Stored, new: Stored)
    ensures
        (old.text == new.text) ==> node_update(false, old, new) == old,
        (old.text != new.text) ==> node_update(false, old, new) == new && node_update(true, old, new) == new,
{}

} // verus!
