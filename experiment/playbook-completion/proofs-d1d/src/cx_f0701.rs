//! Proved counterexample for control `control_f0701_build_in_place` (F-0701), compiled only with it.
//!
//! The live check b-07-f0701-race: an Insert from a second process landed during a Build; a concurrent reader saw
//! N=1, schema 2 mid-build, and the finished index had N=3000 for 3001 documents. Here: a build over documents 0 and
//! 1 indexes 0 in place (Build has killed the live index and takes no lock, BM25Index.cls:97-175); an Insert of 2
//! creates a header over the half-built index (not an L1 step: searchers see document 0 of an unfinished build); the
//! build indexes 1 and writes its header from its own count, so N and totalLen count {0, 1} of {0, 1, 2}, and a
//! search scores three documents with the counters of two (not an L1 step, TXT-I2).
use vstd::prelude::*;
use actors::protocol::*;
use crate::bmw_l1::*;
use crate::bmw_l2::*;
use crate::bmw_runs::*;

verus! {

pub open spec fn ta() -> Set<int> { Set::empty().insert(1int) }
pub open spec fn tb() -> Set<int> { Set::empty().insert(2int) }
pub open spec fn cc() -> Map<int, Set<int>> { Map::empty().insert(0int, ta()).insert(1int, tb()) }
pub open spec fn f1() -> BW2 { p_bstart(w0(), cc()) }
pub open spec fn f2() -> BW2 { p_bdoc(f1(), 0) }
pub open spec fn f3() -> BW2 { p_ins(f2(), 2, ta(), false) }
pub open spec fn f4() -> BW2 { p_bdoc(f3(), 1) }
pub open spec fn f5() -> BW2 { p_bheader(f4(), false) }

pub proof fn counterexample_f0701()
    ensures
        init2(w0()),
        step2(w0(), BWL2::BStart { corpus: cc() }, f1()),
        step2(f1(), BWL2::BDoc { d: 0 }, f2()),
        step2(f2(), BWL2::Ins { d: 2, toks: ta(), fail: false }, f3()),
        !step_or_stutter::<BwL1>(absw(f2()), labw(BWL2::Ins { d: 2, toks: ta(), fail: false }), absw(f3())),
        step2(f3(), BWL2::BDoc { d: 1 }, f4()),
        step2(f4(), BWL2::BHeader { corpus: cc(), refused: false }, f5()),
        f5().cur.hdr && f5().cur.docs.contains_key(2) && !f5().cur.counted.contains(2),
        step2(f5(), BWL2::Search { ans: view2(f5()) }, f5()),
        !step_or_stutter::<BwL1>(absw(f5()), labw(BWL2::Search { ans: view2(f5()) }), absw(f5())),
{
    assert(ne(ta())) by { assert(ta().contains(1)); }
    assert(ne(tb())) by { assert(tb().contains(2)); }
    lemma_w_steps(w0(), 0, 0, ta(), false, cc(), false);
    assert(cc().dom().contains(0) && cc().dom().contains(1));
    lemma_w_steps(f1(), 0, 0, ta(), false, cc(), false);
    lemma_w_steps(f2(), 0, 2, ta(), false, cc(), false);
    // the L1 Insert into "no index" gives {2}; the layout shows {0, 2}
    assert(f3().cur.docs.contains_key(0));
    assert(!put(curm(absw(f2()).db.idx), 2, ta()).contains_key(0));
    assert(absw(f3()).db.idx != Some(put(curm(absw(f2()).db.idx), 2, ta())));
    lemma_w_steps(f3(), 0, 1, ta(), false, cc(), false);
    let b4 = f4().b->Some_0;
    assert(b4.todo =~= Set::<int>::empty()) by {
        assert(cc().dom() =~= Set::<int>::empty().insert(0int).insert(1int));
    }
    lemma_w_steps(f4(), 0, 1, ta(), false, cc(), false);
    assert(b4.corpus == cc());
    assert(f5().cur.docs.contains_key(2));
    assert(!f5().cur.counted.contains(2));
    lemma_w_steps(f5(), 0, 1, ta(), false, cc(), false);
    assert(f5().cur.counted != f5().cur.docs.dom());
    assert(view2(f5()) != view(absw(f5()).db.idx));
}

} // verus!
