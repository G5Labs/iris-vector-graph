//! Proved counterexample for control `control_f1004_create_moves_no_token` (F-1004), compiled only with it.
//!
//! The live trace b-10-live-cache (kg_PERSONALIZED_PAGERANK(['b10_x']) answered {} and was cached; create_node('b10_x')
//! with no edge moved no token; the same call answered {} from the cache while a fresh run answered b10_x with 1.0)
//! and m10-cache-as-built-ppr: the served entry is not an L1 step (L1 answers the fresh result, which lists node 9).
use vstd::prelude::*;
use actors::protocol::*;
use crate::acache_l1::*;
use crate::acache_l2::*;
use crate::acache_runs::*;

verus! {

pub open spec fn none() -> Ans { Ans { rows: Set::empty(), over: Set::empty() } }
pub open spec fn c0() -> AS2 { a_init(Set::empty().insert(1int), Set::empty(), Set::empty(), Set::empty()) }
pub open spec fn c1() -> AS2 { p_miss(c0(), 0, Q::Ppr { seed: 9 }) }
pub open spec fn c2() -> AS2 { p_compute(c1(), 0, Q::Ppr { seed: 9 }, none()) }
pub open spec fn c3() -> AS2 { p_put(c2(), 0) }
pub open spec fn c4() -> AS2 { p_create(c3(), 9) }

pub proof fn counterexample_f1004()
    ensures
        init2(c0()),
        step2(c0(), AL2::LookupMiss { c: 0, q: Q::Ppr { seed: 9 } }, c1()),
        step2(c1(), AL2::Compute { c: 0, q: Q::Ppr { seed: 9 }, ans: none() }, c2()),
        step2(c2(), AL2::Put { c: 0 }, c3()),
        step2(c3(), AL2::CreateNode { n: 9 }, c4()),
        step2(c4(), AL2::LookupHit { c: 1, q: Q::Ppr { seed: 9 }, ans: none() }, c4()),
        !step_or_stutter::<CacheL1>(absa(c4()), laba(AL2::LookupHit { c: 1, q: Q::Ppr { seed: 9 }, ans: none() }), absa(c4())),
{
    let p = Q::Ppr { seed: 9 };
    lemma_a_steps(c0(), 0, p, none(), 9);
    assert(fresh2(c1(), p) == none());
    lemma_a_steps(c1(), 0, p, none(), 9);
    lemma_a_steps(c2(), 0, p, none(), 9);
    lemma_a_steps(c3(), 1, p, none(), 9);
    assert(hit(c4(), p));
    lemma_a_steps(c4(), 1, p, none(), 9);
    assert(fresh(absa(c4()), p).rows.contains(9));
}

} // verus!
