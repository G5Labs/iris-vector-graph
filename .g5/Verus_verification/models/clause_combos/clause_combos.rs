// product 3eaa79cf: clause combinations over API-written data, default (single-edge) mode (W62, iteration 58).
//   Translator choices (iris_vector_graph/cypher/translator.py at the pin):
//     A OPTIONAL MATCH aggregates. After a MATCH the optional pattern is a LEFT OUTER JOIN and the aggregates are SQL
//       aggregates over the joined rows: count(b) is COUNT(n2.node_id) (a null row contributes nothing), count(*) is
//       COUNT(*), sum is `CASE WHEN SUM(x) IS NULL THEN CAST(0 AS INTEGER) ELSE SUM(x) END` (18600), collect is
//       `COALESCE('[' || LIST(...) || ']', '[]')` (21666), avg/min/max are SQL AVG/MIN/MAX (null over no value).
//       A leading OPTIONAL MATCH with no row: with aggregates alone, count(*) is patched `CASE WHEN c = 0 THEN 1`
//       (translate_return_clause 30574-30582, R298); with a grouping key, the synthetic null row's items come from
//       `_null_row_aggregate` (5412-5422) through `optional_null_row_items` (30790-30791): count(*) '1', count(x) '0',
//       collect '[]', every other aggregate NULL (sum included: bug-agg-001).
//     B UNWIND of a list the query holds: translate_return_clause selects the row through the flag route
//       (`_unwind_bool_flag` 21457, 30655-30672: a list mixing booleans with other kinds; CY_LIST_KINDS' JSON column
//       `_unwind_json_text` 21533 when the list holds a list or map) or plainly (`u0.x`); the GROUP BY key is the
//       plain `sql` (30777), i.e. the bound row value `u0.x`, never the kind column (x__t / x__b / x__k) beside it;
//       count(DISTINCT) is COUNT(DISTINCT u0.x) (_expr_aggregation 24431). IRIS binds true as 1, false as 0; a list
//       element's row value is its JSON text. SELECT DISTINCT compares the selected (decoded) item.
//     C a WHERE inside OPTIONAL MATCH: translate_where_clause 17031-17188 places the condition in the outer join's ON
//       (17128-17175). Provider premise P-OUTER-ON (IRIS 2026.1, observed): with negation pushed to the comparisons,
//       an ON holding arithmetic over an earlier alias's property, or a disjunction one of whose sides reads an earlier
//       alias, fails Prepare with SQLCODE -94 (refuses_p).
//   Reader: the execute_cypher result row on the SQL path (driver intersystems-irispython 5.3.2).
use vstd::prelude::*;
verus! {

// ======================================================================== A. OPTIONAL MATCH aggregates
/// One outgoing edge of the anchor: its relationship type and the target's integer property v.
pub struct Edge { pub ty: int, pub v: int }
pub enum Agg { CountVar, CountStar, Sum, Avg, Min, Collect }
pub enum AVal { Int(int), Null, AvgOf(int, nat), List(Seq<int>) }

/// The targets' values the optional pattern `(a)-[:t]->(b)` matches, in edge order (derived from the data).
pub open spec fn matched(edges: Seq<Edge>, t: int) -> Seq<int>
    decreases edges.len(),
{
    if edges.len() == 0 { Seq::empty() } else {
        let rest = matched(edges.drop_last(), t);
        if edges.last().ty == t { rest.push(edges.last().v) } else { rest }
    }
}
pub open spec fn wrap(vs: Seq<int>) -> Seq<Option<int>> { vs.map_values(|v: int| Some(v)) }
/// The rows the LEFT OUTER JOIN gives one anchor: one row per match, or one null row.
pub open spec fn opt_rows(edges: Seq<Edge>, t: int) -> Seq<Option<int>> {
    if matched(edges, t).len() == 0 { seq![None] } else { wrap(matched(edges, t)) }
}
/// The non-null values among rows (SQL aggregates leave nulls out).
pub open spec fn somes(rows: Seq<Option<int>>) -> Seq<int>
    decreases rows.len(),
{
    if rows.len() == 0 { Seq::empty() } else {
        let rest = somes(rows.drop_last());
        match rows.last() { Some(v) => rest.push(v), None => rest }
    }
}
pub open spec fn sum_seq(vs: Seq<int>) -> int
    decreases vs.len(),
{ if vs.len() == 0 { 0 } else { sum_seq(vs.drop_last()) + vs.last() } }
pub open spec fn min_seq(vs: Seq<int>) -> int
    decreases vs.len(),
{
    if vs.len() <= 1 { if vs.len() == 0 { 0 } else { vs[0] } } else {
        let m = min_seq(vs.drop_last());
        if vs.last() < m { vs.last() } else { m }
    }
}
/// As built: the SQL aggregate over the joined rows (translate_return_clause / _expr_aggregation; sum 18600,
/// collect 21666).
pub open spec fn as_built_sql(k: Agg, rows: Seq<Option<int>>) -> AVal {
    let vs = somes(rows);
    match k {
        Agg::CountVar => AVal::Int(vs.len() as int),
        Agg::CountStar => AVal::Int(rows.len() as int),
        Agg::Sum => AVal::Int(sum_seq(vs)),
        Agg::Avg => if vs.len() == 0 { AVal::Null } else { AVal::AvgOf(sum_seq(vs), vs.len()) },
        Agg::Min => if vs.len() == 0 { AVal::Null } else { AVal::Int(min_seq(vs)) },
        Agg::Collect => AVal::List(vs),
    }
}
/// As built: `_null_row_aggregate` (5412-5422), the synthetic null row of a leading grouped OPTIONAL MATCH.
pub open spec fn null_row_aggregate(k: Agg) -> AVal {
    match k {
        Agg::CountStar => AVal::Int(1),
        Agg::CountVar => AVal::Int(0),
        Agg::Collect => AVal::List(Seq::empty()),
        _ => AVal::Null,
    }
}
/// As built: R298's patch of a pure-aggregate leading OPTIONAL MATCH (30574-30582): count(*) of 0 reads 1.
pub open spec fn leading_star_patch(k: Agg, v: AVal) -> AVal {
    if k == Agg::CountStar && v == AVal::Int(0) { AVal::Int(1) } else { v }
}
/// The query shape: `leading` = the OPTIONAL MATCH opens the query (no earlier MATCH binds the anchor);
/// `grouped` = the RETURN has a non-aggregate key beside the aggregates. The answer is derived from shape and data.
pub open spec fn as_built_answer(leading: bool, grouped: bool, edges: Seq<Edge>, t: int, k: Agg) -> AVal {
    if !leading { as_built_sql(k, opt_rows(edges, t)) }
    else if matched(edges, t).len() > 0 { as_built_sql(k, wrap(matched(edges, t))) }
    else if grouped { null_row_aggregate(k) }
    else { leading_star_patch(k, as_built_sql(k, Seq::empty())) }
}
/// openCypher (owner query.optional, query.aggregation): aggregates leave nulls out; count(*) counts the rows
/// (one null row when nothing matched); sum of no value is 0; avg/min of no value null; collect of none [].
pub open spec fn rule(k: Agg, vs: Seq<int>, nrows: int) -> AVal {
    match k {
        Agg::CountVar => AVal::Int(vs.len() as int),
        Agg::CountStar => AVal::Int(nrows),
        Agg::Sum => AVal::Int(sum_seq(vs)),
        Agg::Avg => if vs.len() == 0 { AVal::Null } else { AVal::AvgOf(sum_seq(vs), vs.len()) },
        Agg::Min => if vs.len() == 0 { AVal::Null } else { AVal::Int(min_seq(vs)) },
        Agg::Collect => AVal::List(vs),
    }
}
pub open spec fn rule_rows(edges: Seq<Edge>, t: int) -> int {
    if matched(edges, t).len() == 0 { 1 } else { matched(edges, t).len() as int }
}

pub proof fn lemma_somes_wrap(vs: Seq<int>)
    ensures somes(wrap(vs)) == vs, wrap(vs).len() == vs.len(),
    decreases vs.len(),
{
    if vs.len() > 0 {
        assert(wrap(vs).drop_last() =~= wrap(vs.drop_last()));
        lemma_somes_wrap(vs.drop_last());
        assert(somes(wrap(vs)) =~= vs);
    } else {
        assert(wrap(vs) =~= Seq::<Option<int>>::empty());
    }
}
pub proof fn lemma_null_row()
    ensures somes(seq![None::<int>]) == Seq::<int>::empty(),
{
    let r = seq![None::<int>];
    assert(r.drop_last() =~= Seq::<Option<int>>::empty());
    assert(r.last() == None::<int>);
    assert(somes(Seq::<Option<int>>::empty()) == Seq::<int>::empty());
    assert(somes(r) == somes(r.drop_last()));
}

/// For every anchor's edges, pattern type and aggregate, the OPTIONAL MATCH after a MATCH answers the rule.
pub proof fn theorem_after_match_follows_rule(edges: Seq<Edge>, t: int, k: Agg)
    ensures as_built_answer(false, true, edges, t, k) == rule(k, matched(edges, t), rule_rows(edges, t)),
            as_built_answer(false, false, edges, t, k) == rule(k, matched(edges, t), rule_rows(edges, t)),
{
    if matched(edges, t).len() == 0 {
        lemma_null_row();
        assert(matched(edges, t) =~= Seq::<int>::empty());
        assert(opt_rows(edges, t) == seq![None::<int>]);
        assert(somes(opt_rows(edges, t)) == matched(edges, t));
    } else {
        lemma_somes_wrap(matched(edges, t));
        assert(somes(opt_rows(edges, t)) == matched(edges, t));
    }
}
/// The null row (C1): count(b) is 0 and count(*) 1 for every row set with no match; sum 0, avg null, collect [].
pub proof fn theorem_null_row_counts(edges: Seq<Edge>, t: int)
    requires matched(edges, t).len() == 0,
    ensures as_built_answer(false, true, edges, t, Agg::CountVar) == AVal::Int(0),
            as_built_answer(false, true, edges, t, Agg::CountStar) == AVal::Int(1),
            as_built_answer(false, true, edges, t, Agg::Sum) == AVal::Int(0),
            as_built_answer(false, true, edges, t, Agg::Avg) == AVal::Null,
            as_built_answer(false, true, edges, t, Agg::Collect) == AVal::List(Seq::empty()),
{ lemma_null_row(); }
/// A matched anchor: count(b) = count(*) = the number of matches.
pub proof fn theorem_matched_counts(edges: Seq<Edge>, t: int)
    requires matched(edges, t).len() > 0,
    ensures as_built_answer(false, true, edges, t, Agg::CountVar) == AVal::Int(matched(edges, t).len() as int),
            as_built_answer(false, true, edges, t, Agg::CountStar) == AVal::Int(matched(edges, t).len() as int),
{ lemma_somes_wrap(matched(edges, t)); }
/// A leading OPTIONAL MATCH with aggregates alone follows the rule for every aggregate.
pub proof fn theorem_leading_pure_follows_rule(edges: Seq<Edge>, t: int, k: Agg)
    ensures as_built_answer(true, false, edges, t, k) == rule(k, matched(edges, t), rule_rows(edges, t)),
{
    if matched(edges, t).len() > 0 { lemma_somes_wrap(matched(edges, t)); }
    else {
        assert(somes(Seq::<Option<int>>::empty()) =~= Seq::<int>::empty());
        assert(matched(edges, t) =~= Seq::<int>::empty());
    }
}
/// A leading grouped OPTIONAL MATCH with no match: every aggregate but sum follows the rule.
pub proof fn theorem_leading_grouped_others_follow_rule(edges: Seq<Edge>, t: int, k: Agg)
    requires matched(edges, t).len() == 0, k != Agg::Sum,
    ensures as_built_answer(true, true, edges, t, k) == rule(k, matched(edges, t), rule_rows(edges, t)),
{
    assert(matched(edges, t) =~= Seq::<int>::empty());
}
/// Rejects the probe-confirmed outcome (bug-agg-001): its sum is null, where the rule says 0.
pub proof fn theorem_leading_grouped_sum_is_null(edges: Seq<Edge>, t: int)
    requires matched(edges, t).len() == 0,
    ensures as_built_answer(true, true, edges, t, Agg::Sum) == AVal::Null,
            rule(Agg::Sum, matched(edges, t), rule_rows(edges, t)) == AVal::Int(0),
            as_built_answer(true, true, edges, t, Agg::Sum) != rule(Agg::Sum, matched(edges, t), rule_rows(edges, t)),
{
    assert(matched(edges, t) =~= Seq::<int>::empty());
}

// ======================================================================== B. UNWIND of a held list: keys
/// A string element, by what its text spells (the only property the key functions read).
pub enum StrV { SpellsInt(int), SpellsTrue, SpellsList(int), Other(nat) }
/// An element of the held list: integer, boolean, string, or a list (by its JSON text's identity).
pub enum Val { Int(int), Bool(bool), Str(StrV), List(int) }
/// The row value IRIS holds (`u0.x`): a number's text, a boolean bound as 1 / 0, a string's text, a list's JSON.
pub enum Txt { Num(int), Word(int), Json(int) }
pub open spec fn bound_text(v: Val) -> Txt {
    match v {
        Val::Int(i) => Txt::Num(i),
        Val::Bool(b) => Txt::Num(if b { 1 } else { 0 }),
        Val::Str(s) => match s {
            StrV::SpellsInt(i) => Txt::Num(i),
            StrV::SpellsTrue => Txt::Word(-1),
            StrV::SpellsList(j) => Txt::Json(j),
            StrV::Other(k) => Txt::Word(k as int),
        },
        Val::List(j) => Txt::Json(j),
    }
}
pub enum Route { Plain, Flag, JsonCol }
pub open spec fn has_list(l: Seq<Val>) -> bool { exists|i: int| 0 <= i < l.len() && l[i] is List }
pub open spec fn has_bool(l: Seq<Val>) -> bool { exists|i: int| 0 <= i < l.len() && l[i] is Bool }
pub open spec fn has_non_bool(l: Seq<Val>) -> bool { exists|i: int| 0 <= i < l.len() && !(l[i] is Bool) }
/// As built: the RETURN item's route, from the list's kinds (30655-30672; _unwind_bool_flag 21457 / _unwind_json_text 21533).
pub open spec fn route(l: Seq<Val>) -> Route {
    if has_list(l) { Route::JsonCol } else if has_bool(l) && has_non_bool(l) { Route::Flag } else { Route::Plain }
}
/// The selected item SELECT DISTINCT compares: the JSON column keeps each kind; the flag route tells a boolean
/// from the rest; the plain route is the bound text.
pub enum SelKey { Text(Txt), Flagged(bool, Txt), Typed(Val) }
pub open spec fn select_key(l: Seq<Val>, v: Val) -> SelKey {
    match route(l) {
        Route::JsonCol => SelKey::Typed(v),
        Route::Flag => SelKey::Flagged(v is Bool, bound_text(v)),
        Route::Plain => SelKey::Text(bound_text(v)),
    }
}
/// As built: GROUP BY the plain `sql` (30777) and COUNT(DISTINCT u0.x) (24431) compare the bound row value.
pub open spec fn group_key(l: Seq<Val>, v: Val) -> Txt { bound_text(v) }
pub open spec fn as_built_group(l: Seq<Val>, v: Val, w: Val) -> bool { group_key(l, v) == group_key(l, w) }
pub open spec fn as_built_distinct(l: Seq<Val>, v: Val, w: Val) -> bool { select_key(l, v) == select_key(l, w) }
/// openCypher: values of different types are never equivalent; same-kind values by value.
pub open spec fn rule_same(v: Val, w: Val) -> bool { v == w }

/// Two elements group together iff their bound row text is equal, for every list.
pub proof fn theorem_group_iff_bound_text(l: Seq<Val>, v: Val, w: Val)
    ensures as_built_group(l, v, w) <==> bound_text(v) == bound_text(w),
{}
/// Rejects the probe-confirmed outcomes: 1 and true, a list and the string spelling its JSON, an integer and the
/// string spelling it are one group (and one count(DISTINCT) value), for every list holding them.
pub proof fn theorem_group_merges_kinds(l: Seq<Val>, j: int, i: int)
    ensures as_built_group(l, Val::Int(1), Val::Bool(true)), !rule_same(Val::Int(1), Val::Bool(true)),
            as_built_group(l, Val::Int(0), Val::Bool(false)),
            as_built_group(l, Val::List(j), Val::Str(StrV::SpellsList(j))), !rule_same(Val::List(j), Val::Str(StrV::SpellsList(j))),
            as_built_group(l, Val::Int(i), Val::Str(StrV::SpellsInt(i))),
{}
/// Same-kind integers and booleans, and a boolean beside the string 'true', group as the rule says.
pub proof fn theorem_group_neighbors_follow_rule(l: Seq<Val>, i: int, i2: int, a: bool, b: bool)
    ensures as_built_group(l, Val::Int(i), Val::Int(i2)) == rule_same(Val::Int(i), Val::Int(i2)),
            as_built_group(l, Val::Bool(a), Val::Bool(b)) == rule_same(Val::Bool(a), Val::Bool(b)),
            as_built_group(l, Val::Bool(a), Val::Str(StrV::SpellsTrue)) == rule_same(Val::Bool(a), Val::Str(StrV::SpellsTrue)),
{}
/// On the JSON-column route (a list holding a list) RETURN DISTINCT follows the rule for every pair.
pub proof fn theorem_distinct_json_route_follows_rule(l: Seq<Val>, v: Val, w: Val)
    requires has_list(l),
    ensures as_built_distinct(l, v, w) == rule_same(v, w),
{}
/// On the flag route a boolean is told apart from every other kind.
pub proof fn theorem_distinct_flag_route_keeps_bool_apart(l: Seq<Val>, i: int)
    requires !has_list(l), has_bool(l), has_non_bool(l),
    ensures !as_built_distinct(l, Val::Int(i), Val::Bool(true)), !as_built_distinct(l, Val::Int(i), Val::Bool(false)),
{}
/// Hence grouping and DISTINCT disagree on [1, true] and on [[1], '[1]'].
pub proof fn theorem_group_and_distinct_disagree(j: int)
    ensures ({ let l = seq![Val::Int(1), Val::Bool(true)];
               as_built_group(l, l[0], l[1]) && !as_built_distinct(l, l[0], l[1]) }),
            ({ let l = seq![Val::List(j), Val::Str(StrV::SpellsList(j))];
               as_built_group(l, l[0], l[1]) && !as_built_distinct(l, l[0], l[1]) }),
{
    let l = seq![Val::Int(1), Val::Bool(true)];
    assert(l[1] is Bool && !(l[0] is Bool));
    assert(!has_list(l)) by { assert(forall|i: int| 0 <= i < l.len() ==> !(l[i] is List)); }
    let l2 = seq![Val::List(j), Val::Str(StrV::SpellsList(j))];
    assert(l2[0] is List);
}
/// The plain route ([1, '1']): DISTINCT merges too (the owner's Today note).
pub proof fn theorem_plain_route_merges_int_and_spelling(i: int)
    ensures ({ let l = seq![Val::Int(i), Val::Str(StrV::SpellsInt(i))];
               as_built_group(l, l[0], l[1]) && as_built_distinct(l, l[0], l[1]) }),
{
    let l = seq![Val::Int(i), Val::Str(StrV::SpellsInt(i))];
    assert(!has_list(l)) by { assert(forall|k: int| 0 <= k < l.len() ==> !(l[k] is List)); }
    assert(!has_bool(l)) by { assert(forall|k: int| 0 <= k < l.len() ==> !(l[k] is Bool)); }
}

// ======================================================================== C. the SQLCODE -94 boundary
pub enum Operand { NewProp, EarlierProp, Lit(int), Arith(Box<Operand>, Box<Operand>) }
pub enum Cond { Cmp(Operand, Operand), And(Box<Cond>, Box<Cond>), Or(Box<Cond>, Box<Cond>), Not(Box<Cond>) }
pub open spec fn op_reads_earlier(o: Operand) -> bool
    decreases o,
{
    match o { Operand::EarlierProp => true, Operand::Arith(x, y) => op_reads_earlier(*x) || op_reads_earlier(*y), _ => false }
}
pub open spec fn op_arith_over_earlier(o: Operand) -> bool {
    match o { Operand::Arith(x, y) => op_reads_earlier(*x) || op_reads_earlier(*y), _ => false }
}
pub open spec fn reads_earlier(c: Cond) -> bool
    decreases c,
{
    match c {
        Cond::Cmp(x, y) => op_reads_earlier(x) || op_reads_earlier(y),
        Cond::And(p, q) => reads_earlier(*p) || reads_earlier(*q),
        Cond::Or(p, q) => reads_earlier(*p) || reads_earlier(*q),
        Cond::Not(p) => reads_earlier(*p),
    }
}
/// Provider premise P-OUTER-ON (observed, IRIS 2026.1): with negation pushed to the comparisons (`pos` is the
/// polarity; a negated AND is an OR, a negated OR an AND), the ON fails Prepare with SQLCODE -94 when it holds a
/// disjunction one of whose sides reads an earlier alias, or a comparison with arithmetic over an earlier alias.
pub open spec fn refuses_p(c: Cond, pos: bool) -> bool
    decreases c,
{
    match c {
        Cond::Cmp(x, y) => op_arith_over_earlier(x) || op_arith_over_earlier(y),
        Cond::Not(p) => refuses_p(*p, !pos),
        Cond::And(p, q) => if pos { refuses_p(*p, pos) || refuses_p(*q, pos) }
                           else { reads_earlier(*p) || reads_earlier(*q) || refuses_p(*p, pos) || refuses_p(*q, pos) },
        Cond::Or(p, q) => if pos { reads_earlier(*p) || reads_earlier(*q) || refuses_p(*p, pos) || refuses_p(*q, pos) }
                          else { refuses_p(*p, pos) || refuses_p(*q, pos) },
    }
}
pub open spec fn iris_refuses(c: Cond) -> bool { refuses_p(c, true) }
/// translate_where_clause places the whole condition in the optional group's ON (17128-17175).
pub open spec fn placed_in_on(c: Cond) -> bool { true }
pub enum OptOut { KeptWithNull, Refused, ReadsEarlier, Dropped }
/// The unmatched anchor's row (a condition in the query's WHERE would drop it). A condition that also reads an earlier alias and runs is the cypher_clauses model's
/// (bug-cyp-143 guard), reported here as ReadsEarlier.
pub open spec fn as_built_opt(c: Cond) -> OptOut {
    if !placed_in_on(c) { OptOut::Dropped }
    else if iris_refuses(c) { OptOut::Refused }
    else if reads_earlier(c) { OptOut::ReadsEarlier }
    else { OptOut::KeptWithNull }
}
pub open spec fn rule_opt(c: Cond) -> OptOut { OptOut::KeptWithNull }

pub proof fn lemma_no_earlier_not_refused(c: Cond, pos: bool)
    requires !reads_earlier(c),
    ensures !refuses_p(c, pos),
    decreases c,
{
    match c {
        Cond::Cmp(x, y) => {},
        Cond::And(p, q) => { lemma_no_earlier_not_refused(*p, pos); lemma_no_earlier_not_refused(*q, pos); },
        Cond::Or(p, q) => { lemma_no_earlier_not_refused(*p, pos); lemma_no_earlier_not_refused(*q, pos); },
        Cond::Not(p) => { lemma_no_earlier_not_refused(*p, !pos); },
    }
}
/// Every condition over the new alias only (any AND/OR/NOT nesting, any arithmetic) runs and keeps the row.
pub proof fn theorem_new_alias_only_keeps_row(c: Cond)
    requires !reads_earlier(c),
    ensures as_built_opt(c) == rule_opt(c),
{ lemma_no_earlier_not_refused(c, true); }
/// Rejects the probe-confirmed outcome (bug-cyp-142): b.v = a.v + 1 and b.v = a.v OR b.v = 10 are refused.
/// Negation decides: NOT (b.v = a.v OR b.v = n) runs (a conjunction once negation is pushed in), while
/// NOT (b.v = n AND b.v = a.v) and NOT NOT (b.v = a.v OR b.v = n) are refused.
pub proof fn theorem_negation_polarity(n: int)
    ensures as_built_opt(Cond::Not(Box::new(Cond::Or(Box::new(Cond::Cmp(Operand::NewProp, Operand::EarlierProp)), Box::new(Cond::Cmp(Operand::NewProp, Operand::Lit(n))))))) == OptOut::ReadsEarlier,
            as_built_opt(Cond::Not(Box::new(Cond::And(Box::new(Cond::Cmp(Operand::NewProp, Operand::Lit(n))), Box::new(Cond::Cmp(Operand::NewProp, Operand::EarlierProp)))))) == OptOut::Refused,
            as_built_opt(Cond::Not(Box::new(Cond::Not(Box::new(Cond::Or(Box::new(Cond::Cmp(Operand::NewProp, Operand::EarlierProp)), Box::new(Cond::Cmp(Operand::NewProp, Operand::Lit(n))))))))) == OptOut::Refused,
{
    reveal_with_fuel(refuses_p, 4);
    reveal_with_fuel(reads_earlier, 4);
    reveal_with_fuel(op_reads_earlier, 3);
}
pub proof fn theorem_mixing_earlier_refused(n: int)
    ensures as_built_opt(Cond::Cmp(Operand::NewProp, Operand::Arith(Box::new(Operand::EarlierProp), Box::new(Operand::Lit(n))))) == OptOut::Refused,
            as_built_opt(Cond::Or(Box::new(Cond::Cmp(Operand::NewProp, Operand::EarlierProp)), Box::new(Cond::Cmp(Operand::NewProp, Operand::Lit(n))))) == OptOut::Refused,
            rule_opt(Cond::Cmp(Operand::NewProp, Operand::Arith(Box::new(Operand::EarlierProp), Box::new(Operand::Lit(n))))) != OptOut::Refused,
{}
/// Valid neighbors (C3): OR over the new alias, arithmetic over the new alias, an equality reading the earlier alias.
pub proof fn theorem_neighbors(n: int, m: int)
    ensures as_built_opt(Cond::Or(Box::new(Cond::Cmp(Operand::NewProp, Operand::Lit(n))), Box::new(Cond::Cmp(Operand::NewProp, Operand::Lit(m))))) == OptOut::KeptWithNull,
            as_built_opt(Cond::Cmp(Operand::Arith(Box::new(Operand::NewProp), Box::new(Operand::Lit(n))), Operand::Lit(m))) == OptOut::KeptWithNull,
            as_built_opt(Cond::Not(Box::new(Cond::Cmp(Operand::NewProp, Operand::Lit(n))))) == OptOut::KeptWithNull,
            as_built_opt(Cond::Cmp(Operand::NewProp, Operand::EarlierProp)) == OptOut::ReadsEarlier,
{
    reveal_with_fuel(refuses_p, 3);
    reveal_with_fuel(reads_earlier, 3);
    reveal_with_fuel(op_reads_earlier, 3);
}

fn main() {}
} // verus!
