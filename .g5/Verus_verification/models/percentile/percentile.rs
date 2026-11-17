// product 3eaa79cf: percentileDisc / percentileCont (W59, iteration 53). Values -> sorted list -> index -> answer.
//   Translator: _scalar_statistical (iris_vector_graph/cypher/translator.py 28570-28618) emits
//     Graph_KG.Percentile_PDISC|PCONT(JSON_ARRAYAGG(CAST(x AS DOUBLE)), p); the single-percentile rewrite 6138-6150
//     emits the same over a subquery. JSON_ARRAYAGG leaves out nulls (observed premise P-AGG-NULL).
//   SQL: SqlProcs.PercentilePDISC / PercentilePCONT (iris_src/src/Graph/KG/SqlProcs.cls 109-117) forward to
//     IVG.Percentile.PDISC (iris_src/src/IVG/Percentile.cls 6-18), PCONT (21-36), SortArray (39-54, ascending
//     insertion sort, a delegate: the model takes the sorted list).
//   PDISC: p outside [0, 1] -> ArgumentError NumberOutOfRange; no values -> "" (SQL NULL); i = ((n - 1) * p) \ 1,
//     clamped to [0, n - 1]; the answer is sorted[i].
//   PCONT: the same checks; pos = (n - 1) * p, lower = pos \ 1; lower >= n - 1 -> the last value; otherwise
//     lo + (pos - lower) * (hi - lo).
//   Reader: _engine/query.py _float_expr_value 1243-1260 (the column is FLOAT: an integer answer reads as a float).
// p is a rational pn / pd (pd > 0); values are integers; a continuous answer is an exact rational (num, den).
use vstd::prelude::*;

verus! {

pub enum Ans { Value(int), Rat(int, int), Null, OutOfRange }

pub open spec fn sorted(xs: Seq<int>) -> bool { forall|i: int, j: int| 0 <= i < j < xs.len() ==> xs[i] <= xs[j] }
pub open spec fn in_range(pn: int, pd: int) -> bool { pd > 0 && 0 <= pn <= pd }

// =============================================================== as built
/// PDISC's index: floor((n - 1) * p), clamped (Percentile.cls 13-15).
pub open spec fn disc_index(n: int, pn: int, pd: int) -> int {
    let i = ((n - 1) * pn) / pd;
    if i < 0 { 0 } else if i >= n { n - 1 } else { i }
}
pub open spec fn pdisc(xs: Seq<int>, pn: int, pd: int) -> Ans {
    if !in_range(pn, pd) { Ans::OutOfRange } else if xs.len() == 0 { Ans::Null } else { Ans::Value(xs[disc_index(xs.len() as int, pn, pd)]) }
}
/// PCONT: lower = floor(pos); at or past the last index the last value; otherwise lo + frac * (hi - lo), with
/// frac = pos - lower = ((n - 1) * pn - lower * pd) / pd.
pub open spec fn pcont(xs: Seq<int>, pn: int, pd: int) -> Ans {
    if !in_range(pn, pd) { Ans::OutOfRange } else if xs.len() == 0 { Ans::Null } else {
        let n = xs.len() as int;
        let lower = ((n - 1) * pn) / pd;
        if lower >= n - 1 { Ans::Rat(xs[n - 1], 1) } else {
            let r = (n - 1) * pn - lower * pd;
            Ans::Rat(xs[lower] * pd + r * (xs[lower + 1] - xs[lower]), pd)
        }
    }
}

// =============================================================== the rule (owner query.functions.percentile; Neo4j)
/// Nearest rank: the smallest value with at least p * n values at or below it, i.e. index ceil(p * n) - 1, and the
/// first value at p = 0.
pub open spec fn rule_disc_index(n: int, pn: int, pd: int) -> int {
    let c = (n * pn + pd - 1) / pd;   // ceil(n * p)
    if c <= 0 { 0 } else { c - 1 }
}
pub open spec fn rule_disc(xs: Seq<int>, pn: int, pd: int) -> Ans {
    if !in_range(pn, pd) { Ans::OutOfRange } else if xs.len() == 0 { Ans::Null } else { Ans::Value(xs[rule_disc_index(xs.len() as int, pn, pd)]) }
}
/// Linear interpolation at position (n - 1) * p between the values at floor and ceil of it.
pub open spec fn rule_cont(xs: Seq<int>, pn: int, pd: int) -> Ans {
    if !in_range(pn, pd) { Ans::OutOfRange } else if xs.len() == 0 { Ans::Null } else {
        let n = xs.len() as int;
        let fl = ((n - 1) * pn) / pd;
        let r = (n - 1) * pn - fl * pd;
        let ce = if r == 0 { fl } else { fl + 1 };
        Ans::Rat(xs[fl] * pd + r * (xs[ce] - xs[fl]), pd)
    }
}
pub open spec fn rat_eq(a: Ans, b: Ans) -> bool {
    match (a, b) {
        (Ans::Rat(x, y), Ans::Rat(u, v)) => x * v == u * y,
        _ => a == b,
    }
}

// =============================================================== lemmas
proof fn lemma_index_bounds(n: int, pn: int, pd: int)
    requires n >= 1, in_range(pn, pd),
    ensures 0 <= ((n - 1) * pn) / pd <= n - 1, 0 <= (n - 1) * pn - (((n - 1) * pn) / pd) * pd < pd,
{
    assert(0 <= (n - 1) * pn <= (n - 1) * pd) by (nonlinear_arith) requires n >= 1, 0 <= pn <= pd;
    let q = ((n - 1) * pn) / pd;
    vstd::arithmetic::div_mod::lemma_fundamental_div_mod((n - 1) * pn, pd);
    assert(q * pd <= (n - 1) * pd) by (nonlinear_arith) requires q * pd + ((n - 1) * pn) % pd == (n - 1) * pn, (n - 1) * pn <= (n - 1) * pd, 0 <= ((n - 1) * pn) % pd;
    assert(q <= n - 1) by (nonlinear_arith) requires q * pd <= (n - 1) * pd, pd > 0;
    assert(q >= 0) by (nonlinear_arith) requires q * pd + ((n - 1) * pn) % pd == (n - 1) * pn, (n - 1) * pn >= 0, ((n - 1) * pn) % pd < pd, pd > 0;
}

// =============================================================== theorems
/// percentileCont follows the rule for every non-empty list and every p in [0, 1], the branch at the last index
/// included (p = 1 answers the last value).
pub proof fn theorem_cont_follows_rule(xs: Seq<int>, pn: int, pd: int)
    ensures rat_eq(pcont(xs, pn, pd), rule_cont(xs, pn, pd)),
{
    if in_range(pn, pd) && xs.len() > 0 {
        let n = xs.len() as int;
        lemma_index_bounds(n, pn, pd);
        let fl = ((n - 1) * pn) / pd;
        let r = (n - 1) * pn - fl * pd;
        if fl >= n - 1 {
            assert(fl == n - 1);
            assert((n - 1) * pn <= (n - 1) * pd) by (nonlinear_arith) requires n >= 1, pn <= pd;
            assert(r == 0) by (nonlinear_arith) requires fl == n - 1, r == (n - 1) * pn - fl * pd, (n - 1) * pn <= (n - 1) * pd, r >= 0, pn <= pd, n >= 1;
            assert(xs[n - 1] * pd == (xs[fl] * pd + r * (xs[fl] - xs[fl])) * 1) by (nonlinear_arith) requires fl == n - 1, r == 0;
        } else {
            if r == 0 {
                assert(xs[fl] * pd + r * (xs[fl + 1] - xs[fl]) == xs[fl] * pd + r * (xs[fl] - xs[fl])) by (nonlinear_arith) requires r == 0;
            }
        }
    }
}

/// percentileDisc rounds the position (n - 1) * p down, never up: its index is at most the nearest-rank index, for
/// every n and p.
pub proof fn theorem_disc_never_above_rule(n: int, pn: int, pd: int)
    requires n >= 1, in_range(pn, pd),
    ensures disc_index(n, pn, pd) <= rule_disc_index(n, pn, pd),
{
    lemma_index_bounds(n, pn, pd);
    let q = ((n - 1) * pn) / pd;
    let c = (n * pn + pd - 1) / pd;
    vstd::arithmetic::div_mod::lemma_fundamental_div_mod(n * pn + pd - 1, pd);
    vstd::arithmetic::div_mod::lemma_fundamental_div_mod((n - 1) * pn, pd);
    let rc = (n * pn + pd - 1) % pd;
    let rq = ((n - 1) * pn) % pd;
    // (q + 1) * pd <= n * pn + pd - 1 whenever q * pd <= (n - 1) * pn, so c >= q + 1 when pn >= 1; at pn = 0 both are 0
    if pn == 0 {
        assert((n - 1) * pn == 0) by (nonlinear_arith) requires pn == 0;
        assert(q == 0);
    } else {
        assert(q * pd + pd <= n * pn + pd - 1) by (nonlinear_arith)
            requires q * pd + rq == (n - 1) * pn, rq >= 0, pn >= 1;
        assert(c >= q + 1) by (nonlinear_arith)
            requires c * pd + rc == n * pn + pd - 1, rc < pd, pd > 0, q * pd + pd <= n * pn + pd - 1;
    }
}

/// The departure (bug-cyp-134), the observed cases: over four values p = 9/10 takes index 2 where nearest rank takes
/// 3 ([10, 20, 30, 40] answers 30 for 40), p = 6/10 index 1 for 2 (20 for 30), and p = 95/100 over ten values index 8
/// for 9.
pub proof fn theorem_disc_rounds_down_p90()
    ensures
        disc_index(4, 9, 10) == 2, rule_disc_index(4, 9, 10) == 3,
        disc_index(4, 6, 10) == 1, rule_disc_index(4, 6, 10) == 2,
        disc_index(10, 95, 100) == 8, rule_disc_index(10, 95, 100) == 9,
{}
/// For every n >= 2 the as-built index is below the rule's whenever p * n is within one value of n, i.e. the top
/// percentiles p >= (n - 1) / n with p < 1 answer the second-largest value instead of the largest.
pub proof fn theorem_disc_top_percentile_misses_max(n: int, pn: int, pd: int)
    requires n >= 2, in_range(pn, pd), pn < pd, pn * n > (n - 1) * pd,
    ensures disc_index(n, pn, pd) == n - 2, rule_disc_index(n, pn, pd) == n - 1,
{
    lemma_index_bounds(n, pn, pd);
    let q = ((n - 1) * pn) / pd;
    vstd::arithmetic::div_mod::lemma_fundamental_div_mod((n - 1) * pn, pd);
    let rq = ((n - 1) * pn) % pd;
    // (n - 1) * pn < (n - 1) * pd, and (n - 1) * pn >= (n - 2) * pd because pn * n > (n - 1) * pd and pn < pd
    assert((n - 1) * pn < (n - 1) * pd) by (nonlinear_arith) requires n >= 2, pn < pd;
    assert((n - 1) * pn >= (n - 2) * pd) by (nonlinear_arith) requires pn * n > (n - 1) * pd, pn < pd, n >= 2, pd > 0;
    assert(q < n - 1) by (nonlinear_arith) requires q * pd + rq == (n - 1) * pn, rq >= 0, (n - 1) * pn < (n - 1) * pd, pd > 0;
    assert(q >= n - 2) by (nonlinear_arith) requires q * pd + rq == (n - 1) * pn, rq < pd, (n - 1) * pn >= (n - 2) * pd, pd > 0;
    let c = (n * pn + pd - 1) / pd;
    vstd::arithmetic::div_mod::lemma_fundamental_div_mod(n * pn + pd - 1, pd);
    let rc = (n * pn + pd - 1) % pd;
    assert(n * pn + pd - 1 >= n * pd) by (nonlinear_arith) requires pn * n > (n - 1) * pd;
    assert(n * pn + pd - 1 < n * pd + pd) by (nonlinear_arith) requires pn < pd, n >= 2;
    assert(c >= n) by (nonlinear_arith) requires c * pd + rc == n * pn + pd - 1, rc < pd, n * pn + pd - 1 >= n * pd, pd > 0;
    assert(c <= n) by (nonlinear_arith) requires c * pd + rc == n * pn + pd - 1, rc >= 0, n * pn + pd - 1 < n * pd + pd, pd > 0;
}

/// Valid neighbors: at p = 0 and p = 1 the two agree (the smallest and largest value), and at p = 1/2 over four values
/// both take the second (the owner's example: 20 over 10, 20, 30, 40).
pub proof fn theorem_disc_agrees_at_ends_and_median(n: int)
    requires n >= 1,
    ensures disc_index(n, 0, 1) == rule_disc_index(n, 0, 1), disc_index(n, 1, 1) == rule_disc_index(n, 1, 1),
            disc_index(4, 1, 2) == rule_disc_index(4, 1, 2),
{
    assert(((n - 1) * 0) / 1 == 0);
    assert(((n - 1) * 1) / 1 == n - 1);
    assert((n * 1 + 1 - 1) / 1 == n);
    assert((n * 0 + 1 - 1) / 1 == 0);
}

/// No values (all null or no rows) answer null; p outside [0, 1] is refused, for both functions.
pub proof fn theorem_empty_and_out_of_range(xs: Seq<int>, pn: int, pd: int)
    ensures
        in_range(pn, pd) && xs.len() == 0 ==> pdisc(xs, pn, pd) == Ans::Null && pcont(xs, pn, pd) == Ans::Null,
        !in_range(pn, pd) ==> pdisc(xs, pn, pd) == Ans::OutOfRange && pcont(xs, pn, pd) == Ans::OutOfRange,
        !in_range(pn, pd) ==> rule_disc(xs, pn, pd) == Ans::OutOfRange,
{}

// =============================================================== answer type and the p argument (iteration 56, review 53-55 minors)
//   Type: _scalar_statistical emits JSON_ARRAYAGG(CAST(x AS DOUBLE)) and the translator types the column FLOAT, so the
//   reader _float_expr_value (query.py 1243-1260) turns every number into a float. Neo4j (and the TCK's Aggregation6
//   result tables) answer percentileDisc in the input's type: over integers an integer (20, not 20.0); percentileCont is
//   always a float. bug-cyp-147.
//   p argument: a `$p` parameter goes through Python float(context.input_params[p]) (translator.py 28595-28603); a literal
//   null p is pasted as SQL NULL, which Percentile.cls reads as "" and so as 0 in its arithmetic (provider premise
//   P-OS-EMPTY-ZERO, observed). bug-cyp-148.
pub enum NKind { Int, Float }
/// The values the CAST reads are all doubles; the FLOAT column reader answers a float for every input kind.
pub open spec fn cast_kind(input: NKind) -> NKind { NKind::Float }
pub open spec fn disc_answer_kind(input: NKind) -> NKind { cast_kind(input) }
pub open spec fn cont_answer_kind(input: NKind) -> NKind { NKind::Float }
/// The rule: percentileDisc returns one of the values, so it keeps their type; percentileCont answers a float.
pub open spec fn rule_disc_kind(input: NKind) -> NKind { input }
pub open spec fn rule_cont_kind(input: NKind) -> NKind { NKind::Float }

/// bug-cyp-147: over integers percentileDisc answers a float, where the rule answers an integer.
pub proof fn theorem_disc_over_ints_answers_float()
    ensures disc_answer_kind(NKind::Int) == NKind::Float, rule_disc_kind(NKind::Int) == NKind::Int,
{}
/// Neighbors: over floats percentileDisc, and percentileCont over anything, keep the rule's type.
pub proof fn theorem_float_and_cont_kinds_follow_rule(k: NKind)
    ensures disc_answer_kind(NKind::Float) == rule_disc_kind(NKind::Float), cont_answer_kind(k) == rule_cont_kind(k),
{}

/// What the caller supplies for p.
pub enum PVal { Num, Null, NumText, OtherText, Bool }
pub enum PSrc { Lit(PVal), Param(PVal), Missing }
pub enum PRes { Run, RunAtZero, RawTypeError, RawValueError, Undefined, Refused }
/// Python float() of a parameter value: a number, a numeric string and a boolean convert; None raises TypeError,
/// other text ValueError.
pub open spec fn py_float(v: PVal) -> PRes {
    match v {
        PVal::Num => PRes::Run, PVal::NumText => PRes::Run, PVal::Bool => PRes::Run,
        PVal::Null => PRes::RawTypeError, PVal::OtherText => PRes::RawValueError,
    }
}
/// As built: a parameter goes through float(); a literal null arrives as SQL NULL and reads as 0 (P-OS-EMPTY-ZERO);
/// a literal number runs; a parameter not supplied is an undefined variable. Other literal kinds are not in scope.
pub open spec fn as_built_p(s: PSrc) -> PRes {
    match s {
        PSrc::Param(v) => py_float(v),
        PSrc::Lit(v) => match v { PVal::Null => PRes::RunAtZero, _ => PRes::Run },
        PSrc::Missing => PRes::Undefined,
    }
}
/// The rule: p is a number; anything else is refused as a Cypher argument error (openCypher leaves a null p unstated;
/// a null answer would be the other acceptable reading, see NOTES), and a missing parameter is a missing parameter.
pub open spec fn rule_p(s: PSrc) -> PRes {
    match s {
        PSrc::Param(v) => if v == PVal::Num { PRes::Run } else { PRes::Refused },
        PSrc::Lit(v) => if v == PVal::Num { PRes::Run } else { PRes::Refused },
        PSrc::Missing => PRes::Undefined,
    }
}
/// bug-cyp-148: a null p parameter raises Python's raw TypeError, other text a raw ValueError, a numeric string and a
/// boolean are used as numbers, and a literal null p answers the p = 0 value.
pub proof fn theorem_non_number_p_not_refused()
    ensures
        as_built_p(PSrc::Param(PVal::Null)) == PRes::RawTypeError,
        as_built_p(PSrc::Param(PVal::OtherText)) == PRes::RawValueError,
        as_built_p(PSrc::Param(PVal::NumText)) == PRes::Run,
        as_built_p(PSrc::Param(PVal::Bool)) == PRes::Run,
        as_built_p(PSrc::Lit(PVal::Null)) == PRes::RunAtZero,
        rule_p(PSrc::Param(PVal::Null)) == PRes::Refused,
        rule_p(PSrc::Lit(PVal::Null)) == PRes::Refused,
{}
/// General: as built follows the rule exactly for numbers and a missing parameter, and departs for every other value.
pub proof fn theorem_p_departs_exactly_on_non_numbers(s: PSrc)
    ensures (as_built_p(s) == rule_p(s)) == (s is Missing || s == PSrc::Param(PVal::Num) || s == PSrc::Lit(PVal::Num)),
{}

} // verus!
