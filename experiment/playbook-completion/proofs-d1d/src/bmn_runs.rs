//! The bmn L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::bmn_l1::*;
use crate::bmn_l2::*;

verus! {

pub open spec fn n0() -> BN2 { BN2 { gl: Map::empty(), stop: sw() } }
pub open spec fn p_search(s: BN2) -> BN2 { BN2 { stop: eff(s.stop), ..s } }
pub open spec fn ans2(s: BN2, n: int, g: int, q: Set<int>, surf: Surf) -> Option<Set<int>> {
    if answers(s, n, g, surf) { Some(hits(s.gl[n].docs, toks(q, eff(s.stop)))) } else { None }
}
pub open spec fn p_erase(s: BN2, g: int) -> BN2 { BN2 { gl: if f0702() { s.gl } else { erase(s.gl, g) }, ..s } }

pub proof fn lemma_n_steps(s: BN2, n: int, g: int, corpus: Map<int, Set<int>>, d: int, text: Set<int>, q: Set<int>, surf: Surf)
    ensures
        init2(n0()),
        accepts(n) ==> step2(s, BNL2::Build { n, g, corpus, ok: true }, build2(s, n, g, corpus)),
        step2(s, BNL2::Build { n, g, corpus, ok: false }, s),
        accepts(n) ==> step2(s, BNL2::Insert { n, d, text, ok: true }, insert2(s, n, d, text)),
        step2(s, BNL2::Insert { n, d, text, ok: false }, s),
        accepts(n) ==> step2(s, BNL2::Drop { n, ok: true }, drop2(s, n)),
        step2(s, BNL2::Drop { n, ok: false }, s),
        step2(s, BNL2::Search { n, g, q, ans: ans2(s, n, g, q, surf), surf }, p_search(s)),
        step2(s, BNL2::Erase { g }, p_erase(s, g)),
{
}

} // verus!
