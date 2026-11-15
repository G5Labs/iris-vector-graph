//! Proved counterexample for control `control_fc0701_stop_name_accepted` (F-C0701, F-0706), compiled only with it.
//!
//! The live check b-07-f0706: after bm25_build('__stop__', ['name'], graph='b07g1') the words 'doc', 'tf', 'len',
//! 'cfg', 'df' are stopwords for every index; a rebuild of index b07w drops them. Here: the build of "__stop__" is
//! accepted (not an L1 step: the name is reserved); a later build of index 3 over a document with the words "doc" (12)
//! and 20 indexes only 20 (not an L1 step: the 77 stopwords are the only ones); a search for "doc" finds nothing.
use vstd::prelude::*;
use actors::protocol::*;
use crate::bmw_l1::ne;
use crate::bmn_l1::*;
use crate::bmn_l2::*;
use crate::bmn_runs::*;

verus! {

pub open spec fn tdoc() -> Set<int> { Set::empty().insert(12int) }
pub open spec fn tx() -> Set<int> { Set::empty().insert(12int).insert(20int) }
pub open spec fn cs() -> Map<int, Set<int>> { Map::empty().insert(9int, tdoc()) }
pub open spec fn cw() -> Map<int, Set<int>> { Map::empty().insert(5int, tx()) }
pub open spec fn k1() -> BN2 { build2(n0(), stopn(), 1, cs()) }
pub open spec fn k2() -> BN2 { build2(k1(), 3, 1, cw()) }

pub proof fn counterexample_fc0701()
    ensures
        init2(n0()),
        step2(n0(), BNL2::Build { n: stopn(), g: 1, corpus: cs(), ok: true }, k1()),
        !step_or_stutter::<BnL1>(absn(n0()), labn(BNL2::Build { n: stopn(), g: 1, corpus: cs(), ok: true }), absn(k1())),
        step2(k1(), BNL2::Build { n: 3, g: 1, corpus: cw(), ok: true }, k2()),
        !step_or_stutter::<BnL1>(absn(k1()), labn(BNL2::Build { n: 3, g: 1, corpus: cw(), ok: true }), absn(k2())),
        step2(k2(), BNL2::Search { n: 3, g: 1, q: tdoc(), ans: Some(Set::empty()), surf: Surf::UseGraph }, p_search(k2())),
{
    lemma_n_steps(n0(), stopn(), 1, cs(), 0, tdoc(), tdoc(), Surf::UseGraph);
    lemma_n_steps(k1(), 3, 1, cw(), 0, tdoc(), tdoc(), Surf::UseGraph);
    // the stopwords in force now include "doc"
    assert(k1().stop.contains(the()));
    assert(eff(k1().stop) == k1().stop);
    assert(eff(k1().stop).contains(12));
    let m2 = tokenize(cw(), eff(k1().stop));
    let m1 = tokenize(cw(), sw());
    assert(tx().difference(sw()).contains(12));
    assert(ne(tx().difference(sw())));
    assert(m1.contains_key(5) && m1[5].contains(12));
    assert(tx().difference(eff(k1().stop)).contains(20));
    assert(m2.contains_key(5) && !m2[5].contains(12));
    assert(absn(k2()).idx[3].docs != m1);
    lemma_n_steps(k2(), 3, 1, cw(), 0, tdoc(), tdoc(), Surf::UseGraph);
    assert(eff(k2().stop) == k2().stop);
    assert(answers(k2(), 3, 1, Surf::UseGraph));
    assert(k2().stop == k1().stop);
    assert(k2().stop.contains(12));
    let qt = toks(tdoc(), eff(k2().stop));
    assert(qt =~= Set::<int>::empty());
    let dk = k2().gl[3].docs;
    assert forall|d: int| !#[trigger] hits(dk, qt).contains(d) by {
        assert(dk[d].intersect(qt) =~= Set::<int>::empty());
    }
    assert(hits(dk, qt) =~= Set::<int>::empty());
}

} // verus!
