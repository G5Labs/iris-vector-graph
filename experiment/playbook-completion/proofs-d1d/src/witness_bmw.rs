//! Non-vacuity of the reviewed bmw model (compiled without its controls): the caller begins and writes row 1; a failed
//! Insert keeps the caller's transaction and row; an Insert inside it goes with the caller's rollback; a build is
//! refused with nothing changed; a build publishes its generation; a search sees consistent counters.
use vstd::prelude::*;
use crate::bmw_l1::*;
use crate::bmw_l2::*;
use crate::bmw_runs::*;

verus! {

pub open spec fn ta() -> Set<int> { Set::empty().insert(1int) }
pub open spec fn c1() -> Map<int, Set<int>> { Map::empty().insert(0int, ta()) }
pub open spec fn c0() -> Map<int, Set<int>> { Map::empty() }
pub open spec fn v1() -> BW2 { p_cbegin(w0()) }
pub open spec fn v2() -> BW2 { p_cwrite(v1(), 1) }
pub open spec fn v3() -> BW2 { p_ins(v2(), 5, ta(), true) }
pub open spec fn v4() -> BW2 { p_ins(v3(), 5, ta(), false) }
pub open spec fn v5() -> BW2 { p_crollback(v4()) }
pub open spec fn v6() -> BW2 { p_bstart(v5(), c0()) }
pub open spec fn v7() -> BW2 { p_bheader(v6(), true) }
pub open spec fn v8() -> BW2 { p_bstart(v7(), c1()) }
pub open spec fn v9() -> BW2 { p_bdoc(v8(), 0) }
pub open spec fn v10() -> BW2 { p_bheader(v9(), false) }

pub proof fn witness_bmw()
    ensures
        init2(w0()),
        step2(w0(), BWL2::CBegin, v1()),
        step2(v1(), BWL2::CWrite { r: 1 }, v2()),
        step2(v2(), BWL2::Ins { d: 5, toks: ta(), fail: true }, v3()),
        v3().caller is Some && v3().cur.rows.contains(1),
        step2(v3(), BWL2::Ins { d: 5, toks: ta(), fail: false }, v4()),
        v4().cur.hdr && v4().cur.docs.contains_key(5),
        step2(v4(), BWL2::CRollback, v5()),
        v5().cur == w0().cur,
        step2(v5(), BWL2::BStart { corpus: c0() }, v6()),
        step2(v6(), BWL2::BHeader { corpus: c0(), refused: true }, v7()),
        v7() == v5(),
        step2(v7(), BWL2::BStart { corpus: c1() }, v8()),
        step2(v8(), BWL2::BDoc { d: 0 }, v9()),
        step2(v9(), BWL2::BHeader { corpus: c1(), refused: false }, v10()),
        v10().cur.docs == c1() && v10().cur.counted == c1().dom(),
        step2(v10(), BWL2::Search { ans: Some((c1(), c1().dom())) }, v10()),
{
    assert(ne(ta())) by { assert(ta().contains(1)); }
    lemma_w_steps(w0(), 1, 5, ta(), true, c0(), true);
    lemma_w_steps(v1(), 1, 5, ta(), true, c0(), true);
    lemma_w_steps(v2(), 1, 5, ta(), true, c0(), true);
    lemma_w_steps(v3(), 1, 5, ta(), false, c0(), true);
    lemma_w_steps(v4(), 1, 5, ta(), false, c0(), true);
    lemma_w_steps(v5(), 1, 5, ta(), false, c0(), true);
    assert(v6().b->Some_0.todo =~= Set::<int>::empty());
    lemma_w_steps(v6(), 1, 5, ta(), false, c0(), true);
    lemma_w_steps(v7(), 1, 0, ta(), false, c1(), false);
    assert(c1().dom().contains(0));
    lemma_w_steps(v8(), 1, 0, ta(), false, c1(), false);
    assert(v9().b->Some_0.todo =~= Set::<int>::empty()) by { assert(c1().dom() =~= Set::<int>::empty().insert(0int)); }
    lemma_w_steps(v9(), 1, 0, ta(), false, c1(), false);
    assert(v10().cur.docs =~= c1());
    assert(v10().cur.counted =~= c1().dom());
    lemma_w_steps(v10(), 1, 0, ta(), false, c1(), false);
}

} // verus!
