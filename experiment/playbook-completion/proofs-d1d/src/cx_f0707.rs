//! Proved counterexample for control `control_f0707_no_scope_check` (F-0707), compiled only with it.
//!
//! The live check b-07-f0705-f0707: USE GRAPH 'b07g1' CALL ivg.bm25.search('b07g2idx','pineapple',5) answered b07g2's
//! node b07_g2a. Here: index 3 is built for graph 2 over document 5; a search under USE GRAPH 1 answers document 5 (not
//! an L1 step: a search for graph 1 answers only from an index recorded for graph 1).
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

pub proof fn counterexample_f0707()
    ensures
        init2(n0()),
        step2(n0(), BNL2::Build { n: 3, g: 2, corpus: cw(), ok: true }, a1()),
        step2(a1(), BNL2::Search { n: 3, g: 1, q: tw(), ans: ans2(a1(), 3, 1, tw(), Surf::UseGraph), surf: Surf::UseGraph }, p_search(a1())),
        ans2(a1(), 3, 1, tw(), Surf::UseGraph) == Some(Set::<int>::empty().insert(5int)),
        !step_or_stutter::<BnL1>(absn(a1()),
            labn(BNL2::Search { n: 3, g: 1, q: tw(), ans: ans2(a1(), 3, 1, tw(), Surf::UseGraph), surf: Surf::UseGraph }),
            absn(p_search(a1()))),
{
    lemma_n_steps(n0(), 3, 2, cw(), 5, tw(), tw(), Surf::UseGraph);
    assert(eff(n0().stop) == sw()) by { assert(sw().contains(the())); }
    assert(tw().difference(sw()) =~= tw());
    assert(ne(tw())) by { assert(tw().contains(20)); }
    lemma_n_steps(a1(), 3, 1, cw(), 5, tw(), tw(), Surf::UseGraph);
    assert(eff(a1().stop) == sw()) by { assert(sw().contains(the())); }
    assert(a1().gl[3].docs.contains_key(5));
    assert(a1().gl[3].docs[5] == tw());
    assert(hits(a1().gl[3].docs, toks(tw(), eff(a1().stop))) =~= Set::<int>::empty().insert(5int)) by {
        assert(a1().gl[3].docs.dom() =~= Set::<int>::empty().insert(5int));
        assert(tw().intersect(tw()).contains(20));
    }
    assert(!scoped(absn(a1()).idx, 3, 1));
}

} // verus!
