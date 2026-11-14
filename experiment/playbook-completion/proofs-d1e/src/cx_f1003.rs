//! Proved counterexample for control `control_f1003_owner_cap` (F-1003), compiled only with it.
//!
//! The live traces b-10-live-cap and ib-HD1004-pagerank-cap (with 10,051 default-graph nodes the owner route
//! answered 10,000 rows, listed scores summing to 0.995; 51 nodes silently not listed): on 10,001 nodes, ids 0..10000,
//! the owner's answer lists ids 0..9999 (any 10,000 rows satisfy the as-built step), which is not an L1 step (every
//! node is listed; node 10000 is not).
use vstd::prelude::*;
use vstd::set_lib::*;
use actors::protocol::*;
use crate::acache_l1::*;
use crate::acache_l2::*;
use crate::acache_runs::*;

verus! {

pub open spec fn top() -> Ans { Ans { rows: Set::<int>::range(0, 10000), over: Set::empty() } }
pub open spec fn c0() -> AS2 { a_init(Set::<int>::range(0, 10001), Set::empty(), Set::empty(), Set::empty()) }
pub open spec fn c1() -> AS2 { p_miss(c0(), 0, Q::PageRank) }
pub open spec fn c2() -> AS2 { p_compute(c1(), 0, Q::PageRank, top()) }

pub proof fn counterexample_f1003()
    ensures
        init2(c0()),
        c0().nodes.len() == 10001,
        step2(c0(), AL2::LookupMiss { c: 0, q: Q::PageRank }, c1()),
        step2(c1(), AL2::Compute { c: 0, q: Q::PageRank, ans: top() }, c2()),
        top().rows.len() == 10000,
        !step_or_stutter::<CacheL1>(absa(c1()), laba(AL2::Compute { c: 0, q: Q::PageRank, ans: top() }), absa(c2())),
{
    lemma_int_range(0, 10001);
    lemma_int_range(0, 10000);
    assert(set_int_range(0, 10001) == Set::<int>::range(0, 10001));
    assert(set_int_range(0, 10000) == Set::<int>::range(0, 10000));
    lemma_a_steps(c0(), 0, Q::PageRank, top(), 0);
    assert(top().rows.subset_of(c1().nodes));
    assert(computes(c1(), Q::PageRank, top()));
    lemma_a_steps(c1(), 0, Q::PageRank, top(), 0);
    assert(c1().nodes.contains(10000) && !top().rows.contains(10000));
    assert(fresh(absa(c1()), Q::PageRank) != top());
}

} // verus!
