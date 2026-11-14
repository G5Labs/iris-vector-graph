//! Non-vacuity of the reviewed bmn model (compiled without its controls): Build, Insert and Drop of "__stop__" are
//! refused; index 3 is built for graph 2; a search for graph 2 answers its document, one for graph 1 is refused; an
//! Insert creates index 4 with no recorded graph, which a default-graph search does not answer; erasing graph 2 drops
//! index 3 and keeps index 4.
use vstd::prelude::*;
use crate::bmw_l1::ne;
use crate::bmn_l1::*;
use crate::bmn_l2::*;
use crate::bmn_runs::*;

verus! {

pub open spec fn tw() -> Set<int> { Set::empty().insert(20int) }
pub open spec fn cw() -> Map<int, Set<int>> { Map::empty().insert(5int, tw()) }
pub open spec fn u1() -> BN2 { build2(n0(), 3, 2, cw()) }
pub open spec fn u2() -> BN2 { insert2(u1(), 4, 6, tw()) }
pub open spec fn u3() -> BN2 { p_erase(u2(), 2) }

pub proof fn witness_bmn()
    ensures
        init2(n0()),
        step2(n0(), BNL2::Build { n: stopn(), g: 1, corpus: cw(), ok: false }, n0()),
        step2(n0(), BNL2::Insert { n: stopn(), d: 5, text: tw(), ok: false }, n0()),
        step2(n0(), BNL2::Drop { n: stopn(), ok: false }, n0()),
        step2(n0(), BNL2::Build { n: 3, g: 2, corpus: cw(), ok: true }, u1()),
        step2(u1(), BNL2::Search { n: 3, g: 2, q: tw(), ans: Some(Set::<int>::empty().insert(5int)), surf: Surf::UseGraph }, u1()),
        step2(u1(), BNL2::Search { n: 3, g: 1, q: tw(), ans: None, surf: Surf::UseGraph }, u1()),
        step2(u1(), BNL2::Insert { n: 4, d: 6, text: tw(), ok: true }, u2()),
        step2(u2(), BNL2::Search { n: 4, g: dflt(), q: tw(), ans: None, surf: Surf::Engine }, u2()),
        step2(u2(), BNL2::Erase { g: 2 }, u3()),
        !u3().gl.contains_key(3) && u3().gl.contains_key(4),
{
    assert(sw().contains(the()));
    lemma_n_steps(n0(), stopn(), 1, cw(), 5, tw(), tw(), Surf::UseGraph);
    lemma_n_steps(n0(), 3, 2, cw(), 5, tw(), tw(), Surf::UseGraph);
    assert(tw().difference(sw()) =~= tw());
    assert(ne(tw())) by { assert(tw().contains(20)); }
    lemma_n_steps(u1(), 3, 2, cw(), 5, tw(), tw(), Surf::UseGraph);
    assert(p_search(u1()) == u1());
    assert(u1().gl[3].docs.contains_key(5));
    assert(hits(u1().gl[3].docs, toks(tw(), eff(u1().stop))) =~= Set::<int>::empty().insert(5int)) by {
        assert(u1().gl[3].docs.dom() =~= Set::<int>::empty().insert(5int));
        assert(tw().intersect(tw()).contains(20));
    }
    lemma_n_steps(u1(), 3, 1, cw(), 5, tw(), tw(), Surf::UseGraph);
    lemma_n_steps(u1(), 4, 1, cw(), 6, tw(), tw(), Surf::UseGraph);
    lemma_n_steps(u2(), 4, dflt(), cw(), 6, tw(), tw(), Surf::Engine);
    assert(p_search(u2()) == u2());
    assert(u2().gl[4].graph is None);
    lemma_n_steps(u2(), 4, 2, cw(), 6, tw(), tw(), Surf::Engine);
    assert(u2().gl[3].graph == Some(2int));
}

} // verus!
