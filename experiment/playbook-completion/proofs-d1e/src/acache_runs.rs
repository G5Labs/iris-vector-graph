//! The module 10 cache L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::acache_l1::*;
use crate::acache_l2::*;

verus! {

pub open spec fn a_init(nodes: Set<int>, out: Set<Ed>, dict: Set<int>, rrec: Set<int>) -> AS2 {
    AS2 { nodes, out, ver: 0, nver: 0, cache: Map::empty(), calls: Map::empty(), dict, rrec }
}
pub open spec fn p_create(s: AS2, n: int) -> AS2 { AS2 { nodes: s.nodes.insert(n), nver: if f1004() { s.nver } else { s.nver + 1 }, ..s } }
pub open spec fn p_miss(s: AS2, c: int, q: Q) -> AS2 {
    AS2 { calls: s.calls.insert(c, Call { q, ph: Ph::Missed { ver: s.ver, nver: s.nver } }), ..s }
}
pub open spec fn p_compute(s: AS2, c: int, q: Q, ans: Ans) -> AS2 {
    AS2 { calls: s.calls.insert(c, Call { q, ph: Ph::Computed { ver: s.calls[c].ph->Missed_ver, nver: s.calls[c].ph->Missed_nver, ans } }), ..s }
}
pub open spec fn p_put(s: AS2, c: int) -> AS2 {
    AS2 { cache: s.cache.insert(s.calls[c].q, Ent { ver: s.calls[c].ph->Computed_ver, nver: s.calls[c].ph->Computed_nver,
                                                    ans: s.calls[c].ph->Computed_ans }),
          calls: s.calls.remove(c), ..s }
}
pub open spec fn p_tri(s: AS2) -> AS2 {
    if fc1001() { AS2 { dict: s.dict.union(zf().difference(s.rrec)), rrec: s.rrec.union(zf()), ..s } } else { s }
}

pub proof fn lemma_a_steps(s: AS2, c: int, q: Q, ans: Ans, n: int)
    ensures
        !s.nodes.contains(n) ==> step2(s, AL2::CreateNode { n }, p_create(s, n)),
        !s.calls.contains_key(c) && hit(s, q) ==> step2(s, AL2::LookupHit { c, q, ans: s.cache[q].ans }, s),
        !s.calls.contains_key(c) && !hit(s, q) ==> step2(s, AL2::LookupMiss { c, q }, p_miss(s, c, q)),
        s.calls.contains_key(c) && s.calls[c].q == q && s.calls[c].ph is Missed && computes(s, q, ans)
            ==> step2(s, AL2::Compute { c, q, ans }, p_compute(s, c, q, ans)),
        s.calls.contains_key(c) && s.calls[c].ph is Computed ==> step2(s, AL2::Put { c }, p_put(s, c)),
        step2(s, AL2::TriCount, p_tri(s)),
{
}

} // verus!
