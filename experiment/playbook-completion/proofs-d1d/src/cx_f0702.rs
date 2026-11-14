//! Proved counterexample for control `control_f0702_erase_keeps_index` (F-0702), compiled only with it.
//!
//! The live check b-07-f0702-f0703: after erase_graph('b07g2') (no node rows left; the journal footprint has no
//! ^BM25Idx), bm25_search on the index built for b07g2 still answers both erased node ids. Here: index 3 is built for
//! graph 2 over document 5; the erasure of graph 2 leaves it (not an L1 step); a search for graph 2 still answers 5.
use vstd::prelude::*;
use actors::protocol::*;
use crate::bmw_l1::ne;
use crate::bmn_l1::*;
use crate::bmn_l2::*;
use crate::bmn_runs::*;

verus! {

pub open spec fn tw() -> Set<int> { Set::empty().insert(20int) }
pub open spec fn cw() -> Map<int, Set<int>> { Map::empty().insert(5int, tw()) }
pub open spec fn a1() -> BN2 { build2(n0(), 3, 2, cw()) }
pub open spec fn a2() -> BN2 { p_erase(a1(), 2) }

pub proof fn counterexample_f0702()
    ensures
        init2(n0()),
        step2(n0(), BNL2::Build { n: 3, g: 2, corpus: cw(), ok: true }, a1()),
        step2(a1(), BNL2::Erase { g: 2 }, a2()),
        !step_or_stutter::<BnL1>(absn(a1()), labn(BNL2::Erase { g: 2 }), absn(a2())),
        step2(a2(), BNL2::Search { n: 3, g: 2, q: tw(), ans: ans2(a2(), 3, 2, tw(), Surf::UseGraph), surf: Surf::UseGraph }, p_search(a2())),
        ans2(a2(), 3, 2, tw(), Surf::UseGraph) == Some(Set::<int>::empty().insert(5int)),
{
    lemma_n_steps(n0(), 3, 2, cw(), 5, tw(), tw(), Surf::UseGraph);
    assert(eff(n0().stop) == sw()) by { assert(sw().contains(the())); }
    assert(tw().difference(sw()) =~= tw());
    assert(ne(tw())) by { assert(tw().contains(20)); }
    lemma_n_steps(a1(), 3, 2, cw(), 5, tw(), tw(), Surf::UseGraph);
    assert(a2() == a1());
    assert(a1().gl.contains_key(3));
    assert(!erase(a1().gl, 2).contains_key(3));
    assert(absn(a2()).idx != erase(absn(a1()).idx, 2));
    lemma_n_steps(a2(), 3, 2, cw(), 5, tw(), tw(), Surf::UseGraph);
    assert(eff(a2().stop) == sw()) by { assert(sw().contains(the())); }
    assert(a2().gl[3].docs.contains_key(5));
    assert(a2().gl[3].docs[5] == tw());
    assert(hits(a2().gl[3].docs, toks(tw(), eff(a2().stop))) =~= Set::<int>::empty().insert(5int)) by {
        assert(a2().gl[3].docs.dom() =~= Set::<int>::empty().insert(5int));
        assert(tw().intersect(tw()).contains(20));
    }
}

} // verus!
