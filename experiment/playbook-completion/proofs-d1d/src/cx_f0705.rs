//! Proved counterexample for control `control_f0705_absent_graph_is_default` (F-0705), compiled only with it.
//!
//! The live check b-07-f0705-f0707: an index created by bm25_insert has no cfg graph subscript; Info answers graph '';
//! default-graph kg_RRF_FUSE answered node b07_n3, which exists only in graph b07g3. Here: an Insert creates index 3
//! holding document 5 (no recorded graph); the engine's default-graph search answers document 5 (not an L1 step: an
//! index with no recorded graph answers no scoped search).
use vstd::prelude::*;
use actors::protocol::*;
use crate::bmw_l1::ne;
use crate::bmn_l1::*;
use crate::bmn_l2::*;
use crate::bmn_runs::*;

verus! {

pub open spec fn tw() -> Set<int> { Set::empty().insert(20int) }
pub open spec fn a1() -> BN2 { insert2(n0(), 3, 5, tw()) }

pub proof fn counterexample_f0705()
    ensures
        init2(n0()),
        step2(n0(), BNL2::Insert { n: 3, d: 5, text: tw(), ok: true }, a1()),
        a1().gl[3].graph is None,
        step2(a1(), BNL2::Search { n: 3, g: dflt(), q: tw(), ans: ans2(a1(), 3, dflt(), tw(), Surf::Engine), surf: Surf::Engine }, p_search(a1())),
        ans2(a1(), 3, dflt(), tw(), Surf::Engine) == Some(Set::<int>::empty().insert(5int)),
        !step_or_stutter::<BnL1>(absn(a1()),
            labn(BNL2::Search { n: 3, g: dflt(), q: tw(), ans: ans2(a1(), 3, dflt(), tw(), Surf::Engine), surf: Surf::Engine }),
            absn(p_search(a1()))),
{
    lemma_n_steps(n0(), 3, dflt(), Map::empty(), 5, tw(), tw(), Surf::Engine);
    assert(eff(n0().stop) == sw()) by { assert(sw().contains(the())); }
    assert(tw().difference(sw()) =~= tw());
    assert(ne(tw())) by { assert(tw().contains(20)); }
    lemma_n_steps(a1(), 3, dflt(), Map::empty(), 5, tw(), tw(), Surf::Engine);
    assert(eff(a1().stop) == sw()) by { assert(sw().contains(the())); }
    assert(a1().gl[3].docs.contains_key(5));
    assert(a1().gl[3].docs[5] == tw());
    assert(hits(a1().gl[3].docs, toks(tw(), eff(a1().stop))) =~= Set::<int>::empty().insert(5int)) by {
        assert(a1().gl[3].docs.dom() =~= Set::<int>::empty().insert(5int));
        assert(tw().intersect(tw()).contains(20));
    }
    assert(!scoped(absn(a1()).idx, 3, dflt()));
}

} // verus!
