// product 3eaa79cf: Cypher clauses over API-written data, default (single-edge) mode and parameters (W59, iteration 54).
//   Translator choices (iris_vector_graph/cypher/translator.py):
//     A grouping and distinctness keys: translate_return_clause's RETURN item 30676 (a stored property read is selected
//       through CY_TYPED) and 30777 (a non-aggregate item joins GROUP BY as its plain `sql`, the stored text);
//       _expr_aggregation 24431 (COUNT(DISTINCT arg) over the plain argument). Native: iris_src Graph.KG.Cypher.Exec
//       GroupOf 1349-1380 with KeyValues 1742 (the group is found by the keys' $List, "a number stays a number").
//     B arithmetic over aggregates: _numeric_static_type 22046-22117 (an aggregate's type is _arith_operand_type of its
//       argument; + - * % / of two 'int' operands is 'int') and _arith_operand_type 22136-22153 (a bare property defaults
//       to 'int'); translate_return_clause 30741-30743 (an 'int' column joins int_expr_aliases); the reader
//       iris_vector_graph/_engine/query.py _int_expr_value 1219-1241 (int(round(v)), Python's half-to-even round).
//       A bare sum takes the typed-sum path (_expr_aggregation 24432-24445), not this one.
//     C UNION: _tts_union_branches 4632-4714 (each branch translated alone; the result SQLQuery carries only the
//       boolean columns every branch has; IRIS UNION removes duplicates of the raw column values).
//     D SKIP/LIMIT: _resolve_pagination_value 8095-8134 with _validate_pagination_int 8137.
//     E a whole-label count as a UNION branch: _lone_label_count 7413-7458 (guard reads the branch copy's emptied
//       union_queries, 4690; writes `SELECT ... FROM rdf_labels WHERE ...` on one line) and _ensure_from 4701 (tests
//       for a "\nFROM " and otherwise appends "\nFROM (SELECT 1) __dual").
//     F startNode/endNode of a variable: _scalar_graph_fn 28993-29005 ({alias}.s / {alias}.o_id); type() has the
//       path-element branch (JSON_VALUE $.type, 28989-28990).
//     G DELETE of a node: the DELETE clause translation 10731-10770 (`touching` = s IN ids OR o_id IN ids, scoped to the
//       node's graph; a non-DETACH delete adds the __constraint_check_delete_connected__ sentinel) and
//       iris_vector_graph/stores/iris_sql_store.py execute_transaction 1746-1756 (count > 0 raises _DELETE_CONNECTED).
//   Reader: the execute_cypher result row on the SQL path, the native executor's own answer where it accepts the shape
//   (_try_native), and for DELETE a later MATCH, get_node() and the native walk over ^KG.
use vstd::prelude::*;
verus! {

// ======================================================================== A. grouping and distinctness keys
/// The kinds of a stored node property value in this model's domain. Float is represented so that its storage mark
/// is stated, but no openCypher grouping claim is made for it (whether 1 and 1.0 group together is excluded).
pub enum Kind { Int, Float, Str, Bool, List }
/// A stored value: its kind and its stored text (an abstract spelling: the integer 1 and the string "1" have the same
/// text; the boolean true and the string "true" have the same text).
pub struct Val { pub kind: Kind, pub text: int }
/// The storage mark CY_TYPED reads (query.values): an N-marked integer, a D-marked double, and plain text for strings,
/// booleans ('true'/'false' text) and lists (JSON text).
pub enum Mark { N, D, Plain }
pub open spec fn mark(k: Kind) -> Mark {
    match k { Kind::Int => Mark::N, Kind::Float => Mark::D, _ => Mark::Plain }
}
pub enum Exec { Sql, Native }
pub enum Op { GroupBy, CountDistinct, ReturnDistinct }
pub enum Key { Text, Typed }
/// The key each operator compares, derived from the operator and the executor (the translator's choice):
/// SQL GROUP BY keeps the item's plain `sql` (30777) and COUNT(DISTINCT) its plain argument (24431); a RETURN item that
/// reads a stored property is selected through CY_TYPED (30676), so SELECT DISTINCT compares the marked text. The native
/// executor finds a group by the keys' $List, which keeps a number a number (GroupOf/KeyValues).
pub open spec fn key_of(e: Exec, op: Op) -> Key {
    match e {
        Exec::Native => Key::Typed,
        Exec::Sql => match op { Op::ReturnDistinct => Key::Typed, _ => Key::Text },
    }
}
pub open spec fn same_key(k: Key, a: Val, b: Val) -> bool {
    match k { Key::Text => a.text == b.text, Key::Typed => mark(a.kind) == mark(b.kind) && a.text == b.text }
}
/// Two stored values fall in one group (or count once under DISTINCT) on executor e for operator op.
pub open spec fn together(e: Exec, op: Op, a: Val, b: Val) -> bool { same_key(key_of(e, op), a, b) }
/// openCypher equivalence inside the domain (no Float): same kind and same value.
pub open spec fn rule_together(a: Val, b: Val) -> bool { a.kind == b.kind && a.text == b.text }
/// The documented storage collision (KNOWN_ISSUES "A stored string that spells a boolean, a list or a map reads as
/// one"): two plain-stored values of different kinds with the same text are one stored value.
pub open spec fn documented_collision(a: Val, b: Val) -> bool {
    mark(a.kind) == Mark::Plain && mark(b.kind) == Mark::Plain && a.kind != b.kind && a.text == b.text
}
pub open spec fn in_domain(v: Val) -> bool { v.kind != Kind::Float }

/// bug-cyp-135: on the SQL path a stored integer and the stored string spelling it are one group and count once
/// under count(DISTINCT), for every spelling t; openCypher keeps them apart.
pub proof fn theorem_sql_group_merges_number_and_its_text(t: int)
    ensures
        together(Exec::Sql, Op::GroupBy, Val { kind: Kind::Int, text: t }, Val { kind: Kind::Str, text: t }),
        together(Exec::Sql, Op::CountDistinct, Val { kind: Kind::Int, text: t }, Val { kind: Kind::Str, text: t }),
        !rule_together(Val { kind: Kind::Int, text: t }, Val { kind: Kind::Str, text: t }),
{}
/// Neighbor: RETURN DISTINCT over the same stored values keeps them apart, as openCypher does.
pub proof fn theorem_sql_return_distinct_keeps_kinds(t: int)
    ensures !together(Exec::Sql, Op::ReturnDistinct, Val { kind: Kind::Int, text: t }, Val { kind: Kind::Str, text: t }),
{}
/// Neighbor: the native executor's grouping follows openCypher on the domain, apart from the documented collision.
pub proof fn theorem_native_group_follows_rule(a: Val, b: Val)
    requires in_domain(a), in_domain(b), !documented_collision(a, b),
    ensures together(Exec::Native, Op::GroupBy, a, b) == rule_together(a, b),
{}
/// bug-cyp-136 (general): the SQL path and the native executor put two stored values in different groupings exactly
/// when their text is equal and their storage marks differ, for every pair of values of every kind.
pub proof fn theorem_paths_disagree_exactly_on_marked_text(a: Val, b: Val)
    ensures
        (together(Exec::Sql, Op::GroupBy, a, b) != together(Exec::Native, Op::GroupBy, a, b))
            == (a.text == b.text && mark(a.kind) != mark(b.kind)),
{}
/// General: on the SQL path grouping and RETURN DISTINCT disagree exactly on the same pairs.
pub proof fn theorem_sql_group_and_distinct_disagree_on_marked_text(a: Val, b: Val)
    ensures
        (together(Exec::Sql, Op::GroupBy, a, b) != together(Exec::Sql, Op::ReturnDistinct, a, b))
            == (a.text == b.text && mark(a.kind) != mark(b.kind)),
{}

// ======================================================================== B. arithmetic over aggregates
pub enum NumT { Int, Float, Unknown }
/// An aggregate's or literal's argument as the translator sees it.
pub enum Arg { Prop, LitInt, LitFloat }
pub enum Operand { LitInt, LitFloat, Prop, Count, Avg, SumOf(Arg), MinMaxOf(Arg) }
/// _numeric_static_type of a literal / argument, then _arith_operand_type's default for a bare property.
pub open spec fn arg_type(a: Arg) -> NumT {
    match a { Arg::LitInt => NumT::Int, Arg::LitFloat => NumT::Float, Arg::Prop => NumT::Int }
}
pub open spec fn operand_type(o: Operand) -> NumT {
    match o {
        Operand::LitInt => NumT::Int,
        Operand::LitFloat => NumT::Float,
        Operand::Prop => NumT::Int,
        Operand::Count => NumT::Int,
        Operand::Avg => NumT::Float,
        Operand::SumOf(a) => arg_type(a),
        Operand::MinMaxOf(a) => arg_type(a),
    }
}
/// A RETURN column: a bare sum (typed-sum path, CY_TYPED) or one arithmetic operator over two operands.
pub enum Column { BareSum(Arg), Arith(Operand, Operand) }
/// The column's static type: + - * % / of a float operand is float, of two int operands int, else unknown.
pub open spec fn column_type(c: Column) -> NumT {
    match c {
        Column::BareSum(_) => NumT::Unknown,
        Column::Arith(l, r) => {
            let (lt, rt) = (operand_type(l), operand_type(r));
            if lt == NumT::Float || rt == NumT::Float { NumT::Float }
            else if lt == NumT::Int && rt == NumT::Int { NumT::Int } else { NumT::Unknown }
        }
    }
}
/// Values in half units (h stands for h / 2), the domain of the probes (sums of x.0 and x.5 values).
/// Python's round() of h / 2 rounds half to even.
pub open spec fn round_half_even_half(h: int) -> int {
    if h % 2 == 0 { h / 2 } else {
        let lo = (h - 1) / 2;
        if lo % 2 == 0 { lo } else { lo + 1 }
    }
}
/// The answer the reader gives, in half units: an 'int' column is int(round(v)) (_int_expr_value); other columns keep v.
pub open spec fn answered(c: Column, h: int) -> int {
    if column_type(c) == NumT::Int { 2 * round_half_even_half(h) } else { h }
}
/// bug-cyp-137: the sum of two stored-property sums is an 'int' column whatever the stored values are.
pub proof fn theorem_sum_of_property_sums_is_int_column()
    ensures
        column_type(Column::Arith(Operand::SumOf(Arg::Prop), Operand::SumOf(Arg::Prop))) == NumT::Int,
        column_type(Column::Arith(Operand::MinMaxOf(Arg::Prop), Operand::LitInt)) == NumT::Int,
{}
/// bug-cyp-137 (general): every total with a half in it is answered as a whole number half a unit away.
pub proof fn theorem_int_column_loses_any_half(h: int)
    requires h % 2 != 0,
    ensures
        answered(Column::Arith(Operand::SumOf(Arg::Prop), Operand::SumOf(Arg::Prop)), h) != h,
        answered(Column::Arith(Operand::SumOf(Arg::Prop), Operand::SumOf(Arg::Prop)), h) % 2 == 0,
        answered(Column::Arith(Operand::SumOf(Arg::Prop), Operand::SumOf(Arg::Prop)), h) - h == 1
            || h - answered(Column::Arith(Operand::SumOf(Arg::Prop), Operand::SumOf(Arg::Prop)), h) == 1,
{}
/// The probe's totals: 3 + 3.5 = 6.5 answers 6, and 1 + 2.5 = 3.5 answers 4 (half to even both ways).
pub proof fn theorem_probe_totals()
    ensures
        answered(Column::Arith(Operand::SumOf(Arg::Prop), Operand::SumOf(Arg::Prop)), 13) == 12,
        answered(Column::Arith(Operand::SumOf(Arg::Prop), Operand::SumOf(Arg::Prop)), 7) == 8,
{}
/// Neighbors: a float literal operand, a bare sum and an avg operand keep the value.
pub proof fn theorem_float_operand_or_bare_sum_keeps_value(h: int, a: Arg)
    ensures
        answered(Column::Arith(Operand::SumOf(Arg::Prop), Operand::LitFloat), h) == h,
        answered(Column::Arith(Operand::Count, Operand::LitFloat), h) == h,
        answered(Column::Arith(Operand::Avg, Operand::LitInt), h) == h,
        answered(Column::BareSum(a), h) == h,
{}
/// Neighbor: a whole total is answered unchanged on the int column too.
pub proof fn theorem_whole_total_unchanged(h: int)
    requires h % 2 == 0,
    ensures answered(Column::Arith(Operand::SumOf(Arg::Prop), Operand::SumOf(Arg::Prop)), h) == h,
{}

// ======================================================================== C. UNION
/// A column's decoder as one translated query marks it.
pub enum Dec { Plain, Typed, Json, Bool }
/// _tts_union_branches: the combined SQLQuery carries only bool_expr_columns common to every branch; nothing else.
pub open spec fn union_dec(first: Dec, rest: Seq<Dec>) -> Dec {
    if first == Dec::Bool && (forall|i: int| 0 <= i < rest.len() ==> rest[i] == Dec::Bool) { Dec::Bool } else { Dec::Plain }
}
/// What a stored value looks like in its SQL column: a marked number ("\x01N1"), or text; literals are SQL numbers.
pub enum Raw { Marked(Mark, int), Text(int), Num(int) }
pub enum Out { Number(int), Text(int), MarkedText(int), Bool(bool) }
/// The reader: a typed column decodes the mark; a plain column answers what IRIS gave.
pub open spec fn read(d: Dec, r: Raw) -> Out {
    match r {
        Raw::Marked(m, t) => if d == Dec::Typed { Out::Number(t) } else { Out::MarkedText(t) },
        Raw::Text(t) => Out::Text(t),
        Raw::Num(n) => if d == Dec::Bool { Out::Bool(n != 0) } else { Out::Number(n) },
    }
}
/// The raw value of a stored integer read through CY_TYPED, of an integer literal and of a boolean literal (IRIS has
/// no boolean: true is 1, so `RETURN true AS x` is a bool column only by its mark).
pub open spec fn raw_stored_int(t: int) -> Raw { Raw::Marked(Mark::N, t) }
pub open spec fn raw_lit_int(n: int) -> Raw { Raw::Num(n) }
pub open spec fn raw_lit_bool(b: bool) -> Raw { Raw::Num(if b { 1 } else { 0 }) }
/// IRIS UNION removes rows with equal raw values.
pub open spec fn union_merges(a: Raw, b: Raw) -> bool { a == b }

/// bug-cyp-138: in any UNION, a stored integer column reaches the reader as its marked text, for every value and every
/// other branch.
pub proof fn theorem_union_answers_marked_text(t: int, rest: Seq<Dec>)
    requires rest.len() >= 1,
    ensures read(union_dec(Dec::Typed, rest), raw_stored_int(t)) == Out::MarkedText(t),
{}
/// Neighbor: the same column outside a UNION answers the number.
pub proof fn theorem_single_query_decodes(t: int)
    ensures read(Dec::Typed, raw_stored_int(t)) == Out::Number(t),
{}
/// Neighbor: a boolean column in every branch stays boolean.
pub proof fn theorem_all_bool_union_stays_bool(rest: Seq<Dec>, b: bool)
    requires forall|i: int| 0 <= i < rest.len() ==> rest[i] == Dec::Bool,
    ensures read(union_dec(Dec::Bool, rest), raw_lit_bool(b)) == Out::Bool(b),
{}
/// bug-cyp-138 (duplicates): UNION keeps a stored 1 and a literal 1 as two rows, and merges the literals 1 and true.
pub proof fn theorem_union_dedup_by_raw(n: int)
    ensures
        !union_merges(raw_stored_int(n), raw_lit_int(n)),
        union_merges(raw_lit_int(1), raw_lit_bool(true)),
{}

// ======================================================================== D. SKIP / LIMIT values
pub enum StrV { Num(int), Other }
/// A SKIP or LIMIT value: written as an integer literal, or a parameter of some kind; Missing = not in the params dict.
pub enum PV { LitInt(int), Missing, Null, Int(int), Float(int, bool), Str(StrV), Bool(bool) }
pub enum POut { Rows(int), NegativeIntegerArgument, InvalidArgumentType, NotProvided, RawValueError }
/// The rule's integer check (TCK: a negative value is NegativeIntegerArgument).
pub open spec fn validate(i: int) -> POut { if i < 0 { POut::NegativeIntegerArgument } else { POut::Rows(i) } }
/// _validate_pagination_int, the product's own check.
pub open spec fn built_validate(i: int) -> POut { if i < 0 { POut::NegativeIntegerArgument } else { POut::Rows(i) } }
/// _resolve_pagination_value: a literal int is validated; a parameter: None → "not provided"; a float with a fraction
/// → InvalidArgumentType; anything else → int(resolved), then validated. Float(v, whole) carries its integer part v.
pub open spec fn as_built_page(p: PV) -> POut {
    match p {
        PV::LitInt(i) => built_validate(i),
        PV::Missing => POut::NotProvided,
        PV::Null => POut::NotProvided,
        PV::Int(i) => built_validate(i),
        PV::Float(v, whole) => if !whole { POut::InvalidArgumentType } else { built_validate(v) },
        PV::Str(s) => match s { StrV::Num(i) => built_validate(i), StrV::Other => POut::RawValueError },
        PV::Bool(b) => POut::Rows(if b { 1 } else { 0 }),
    }
}
/// openCypher (TCK ReturnSkipLimit1-3): an integer is used, a negative one is NegativeIntegerArgument, a value of
/// another type is InvalidArgumentType; a parameter not supplied is a missing parameter.
pub open spec fn rule_page(p: PV) -> POut {
    match p {
        PV::LitInt(i) => validate(i),
        PV::Int(i) => validate(i),
        PV::Missing => POut::NotProvided,
        _ => POut::InvalidArgumentType,
    }
}
/// bug-cyp-139: a string, boolean or whole float parameter is used as a row count; a null parameter is reported as not
/// provided.
pub proof fn theorem_non_integer_parameter_used(i: int, b: bool, v: int)
    requires i >= 0, v >= 0,
    ensures
        as_built_page(PV::Str(StrV::Num(i))) == POut::Rows(i),
        as_built_page(PV::Bool(b)) == POut::Rows(if b { 1 } else { 0 }),
        as_built_page(PV::Float(v, true)) == POut::Rows(v),
        as_built_page(PV::Null) == POut::NotProvided,
        rule_page(PV::Str(StrV::Num(i))) == POut::InvalidArgumentType,
        rule_page(PV::Bool(b)) == POut::InvalidArgumentType,
        rule_page(PV::Float(v, true)) == POut::InvalidArgumentType,
{}
/// Neighbors: integers (literal or parameter, any sign), a fractional float and a missing parameter follow the rule.
pub proof fn theorem_integer_and_fraction_follow_rule(i: int, v: int)
    ensures
        as_built_page(PV::LitInt(i)) == rule_page(PV::LitInt(i)),
        as_built_page(PV::Int(i)) == rule_page(PV::Int(i)),
        as_built_page(PV::Float(v, false)) == rule_page(PV::Float(v, false)),
        as_built_page(PV::Missing) == rule_page(PV::Missing),
{}

// ======================================================================== E. a whole-label count as a UNION branch
/// The branch's shape: a lone label count (one MATCH of one labelled node, every item a count of it) or another read.
pub enum Shape { LoneLabelCount, Other }
/// _lone_label_count runs on the branch copy, whose union_queries the union translation has emptied (4690); on a
/// whole query with a UNION it does not run. It writes its FROM on the SELECT's line.
pub open spec fn shortcut(s: Shape, has_union_field: bool) -> bool { s == Shape::LoneLabelCount && !has_union_field }
pub open spec fn newline_from(s: Shape, has_union_field: bool) -> bool { !shortcut(s, has_union_field) }
/// Prepare succeeds unless _ensure_from (UNION only) adds a second FROM to a SELECT that has one.
pub open spec fn prepares(s: Shape, in_union: bool) -> bool {
    let branch_field = false;  // the copy each branch is translated from has union_queries = []
    if in_union { newline_from(s, branch_field) } else { true }
}
/// bug-cyp-140: a whole-label count as a UNION branch fails Prepare.
pub proof fn theorem_label_count_branch_fails()
    ensures !prepares(Shape::LoneLabelCount, true),
{}
/// Neighbors: the same count alone prepares, and any other branch in a UNION prepares.
pub proof fn theorem_count_alone_and_other_branches_prepare()
    ensures prepares(Shape::LoneLabelCount, false), prepares(Shape::Other, true),
{}

// ======================================================================== F. startNode / endNode of a variable
/// How a relationship variable is bound: a matched edge (an rdf_edges alias), or an element of relationships(p) in a
/// comprehension or UNWIND (a JSON_TABLE row holding {"type","props"} with no endpoint columns).
pub enum RelVar { MatchedEdge, PathElement }
pub enum FnK { StartNode, EndNode, Type }
/// Whether the column the translator reads exists in the alias's table.
pub open spec fn reads_existing_column(v: RelVar, f: FnK) -> bool {
    match f {
        FnK::Type => true,  // the path-element branch reads JSON_VALUE(x, '$.type'); an edge alias has p
        _ => v == RelVar::MatchedEdge,  // {alias}.s / {alias}.o_id: only rdf_edges has them
    }
}
/// bug-cyp-141: startNode(r) and endNode(r) of an element of relationships(p) fail Prepare (SQLCODE -29).
pub proof fn theorem_path_element_endpoints_fail()
    ensures
        !reads_existing_column(RelVar::PathElement, FnK::StartNode),
        !reads_existing_column(RelVar::PathElement, FnK::EndNode),
{}
/// Neighbors: type() of the element, and startNode/endNode of a matched edge, work.
pub proof fn theorem_type_and_matched_endpoints_work()
    ensures
        reads_existing_column(RelVar::PathElement, FnK::Type),
        reads_existing_column(RelVar::MatchedEdge, FnK::StartNode),
        reads_existing_column(RelVar::MatchedEdge, FnK::EndNode),
{}

// ======================================================================== G. DELETE of a node
pub enum DelOut { Refused, Deleted }
/// The relationships of the node in its own graph, by direction (any writer: create_edge, bulk, Cypher).
pub open spec fn touching(out_edges: nat, in_edges: nat) -> nat { out_edges + in_edges }
pub open spec fn as_built_delete(detach: bool, out_edges: nat, in_edges: nat) -> DelOut {
    if !detach && touching(out_edges, in_edges) > 0 { DelOut::Refused } else { DelOut::Deleted }
}
/// openCypher and USER_GUIDE: DELETE of a node with any relationship is refused and deletes nothing; DETACH DELETE
/// removes the node with its relationships.
pub open spec fn rule_delete(detach: bool, out_edges: nat, in_edges: nat) -> DelOut {
    if !detach && (out_edges > 0 || in_edges > 0) { DelOut::Refused } else { DelOut::Deleted }
}
/// Agreement for every edge count and both clauses (held on API-written edges, incoming-only included).
pub proof fn theorem_delete_follows_rule(detach: bool, out_edges: nat, in_edges: nat)
    ensures as_built_delete(detach, out_edges, in_edges) == rule_delete(detach, out_edges, in_edges),
{}
/// The incoming-only case on its own (DL2), since an outgoing-only check would pass the other cases.
pub proof fn theorem_incoming_only_refused(in_edges: nat)
    requires in_edges > 0,
    ensures as_built_delete(false, 0, in_edges) == DelOut::Refused,
{}

fn main() {}
} // verus!
