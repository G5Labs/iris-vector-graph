//! Proved counterexample for control `control_f0704_late_refusal` (F-0704), compiled only with it.
//!
//! The live check b-07-f0704: engine.index('b07h').build(properties=['no_such_property']) raised IndexNotBuiltError
//! after Build had replaced the 2-document index with an empty header (N=0). Here: a build publishes {0}; a second
//! build over a corpus with no indexable document is refused by the index handle (vector.py:306-307) after its
//! generation was published: the refusal is not an L1 step (L1: a refused build changes nothing).
use vstd::prelude::*;
use actors::protocol::*;
use crate::bmw_l1::*;
use crate::bmw_l2::*;
use crate::bmw_runs::*;

verus! {

pub open spec fn ta() -> Set<int> { Set::empty().insert(1int) }
pub open spec fn c1() -> Map<int, Set<int>> { Map::empty().insert(0int, ta()) }
pub open spec fn c0() -> Map<int, Set<int>> { Map::empty() }
pub open spec fn e1() -> BW2 { p_bstart(w0(), c1()) }
pub open spec fn e2() -> BW2 { p_bdoc(e1(), 0) }
pub open spec fn e3() -> BW2 { p_bheader(e2(), false) }
pub open spec fn e4() -> BW2 { p_bstart(e3(), c0()) }
pub open spec fn e5() -> BW2 { p_bheader(e4(), true) }

pub proof fn counterexample_f0704()
    ensures
        init2(w0()),
        step2(w0(), BWL2::BStart { corpus: c1() }, e1()),
        step2(e1(), BWL2::BDoc { d: 0 }, e2()),
        step2(e2(), BWL2::BHeader { corpus: c1(), refused: false }, e3()),
        absw(e3()).db.idx == Some(c1()),
        step2(e3(), BWL2::BStart { corpus: c0() }, e4()),
        step2(e4(), BWL2::BHeader { corpus: c0(), refused: true }, e5()),
        !step_or_stutter::<BwL1>(absw(e4()), labw(BWL2::BHeader { corpus: c0(), refused: true }), absw(e5())),
{
    assert(ne(ta())) by { assert(ta().contains(1)); }
    lemma_w_steps(w0(), 0, 0, ta(), false, c1(), false);
    assert(c1().dom().contains(0));
    lemma_w_steps(e1(), 0, 0, ta(), false, c1(), false);
    assert(e2().b->Some_0.todo =~= Set::<int>::empty()) by { assert(c1().dom() =~= Set::<int>::empty().insert(0int)); }
    lemma_w_steps(e2(), 0, 0, ta(), false, c1(), false);
    assert(e3().cur.docs =~= c1());
    lemma_w_steps(e3(), 0, 0, ta(), false, c0(), true);
    assert(e4().b->Some_0.todo =~= Set::<int>::empty());
    lemma_w_steps(e4(), 0, 0, ta(), true, c0(), true);
    assert(e5().cur.docs =~= Map::<int, Set<int>>::empty());
    assert(e4().cur.docs.contains_key(0));
    assert(absw(e5()) != absw(e4()));
}

} // verus!
