//! The module 10 traversal L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::atrav_l1::*;
use crate::atrav_l2::*;

verus! {

pub open spec fn t_init(nodes0: Set<int>) -> TS2 { TS2 { nodes0, out: Set::empty(), inn: Set::empty(), cdlp: Map::empty() } }
pub open spec fn p_addedge(s: TS2, g: int, a: int, b: int) -> TS2 {
    TS2 { out: s.out.insert(E { g, a, b }), inn: s.inn.insert(E { g, a: b, b: a }), ..s }
}
pub open spec fn p_cinit(s: TS2, c: int) -> TS2 { TS2 { cdlp: s.cdlp.insert(c, init_labels(s.nodes0, s.out, s.inn)), ..s } }
pub open spec fn p_cround(s: TS2, c: int, nl: Map<int, int>) -> TS2 { TS2 { cdlp: s.cdlp.insert(c, nl), ..s } }
pub open spec fn p_cend(s: TS2, c: int) -> TS2 { TS2 { cdlp: s.cdlp.remove(c), ..s } }

pub proof fn lemma_t_steps(s: TS2, g: int, a: int, b: int, c: int, nl: Map<int, int>)
    ensures
        s.cdlp == Map::<int, Map<int, int>>::empty() && (g == 0 ==> s.nodes0.contains(a) && s.nodes0.contains(b))
            ==> step2(s, TL2::AddEdge { g, a, b }, p_addedge(s, g, a, b)),
        !s.cdlp.contains_key(c) ==> step2(s, TL2::CdlpInit { c }, p_cinit(s, c)),
        s.cdlp.contains_key(c) && round_ok(s.out, s.inn, s.cdlp[c], nl) ==> step2(s, TL2::CdlpRound { c, nl }, p_cround(s, c, nl)),
        s.cdlp.contains_key(c) ==> step2(s, TL2::CdlpEnd { c, labels: end_labels(s.nodes0, s.out, s.inn, s.cdlp[c]) }, p_cend(s, c)),
{
}

} // verus!
