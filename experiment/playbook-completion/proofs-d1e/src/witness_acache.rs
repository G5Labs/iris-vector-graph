//! Non-vacuity of the reviewed cache model (compiled without its controls): a personalized PageRank answer is
//! computed, stored and served from the cache; a start node is then written with no edge; the next call misses and
//! answers it; global PageRank lists every node; triangle_count changes nothing.
use vstd::prelude::*;
use crate::acache_l1::*;
use crate::acache_l2::*;
use crate::acache_runs::*;

verus! {

pub open spec fn none() -> Ans { Ans { rows: Set::empty(), over: Set::empty() } }
pub open spec fn both() -> Ans { Ans { rows: Set::empty().insert(1int).insert(9int), over: Set::empty() } }
pub open spec fn w0() -> AS2 { a_init(Set::empty().insert(1int), Set::empty(), Set::empty(), Set::empty()) }
pub open spec fn w1() -> AS2 { p_miss(w0(), 0, Q::Ppr { seed: 9 }) }
pub open spec fn w2() -> AS2 { p_compute(w1(), 0, Q::Ppr { seed: 9 }, none()) }
pub open spec fn w3() -> AS2 { p_put(w2(), 0) }
pub open spec fn w4() -> AS2 { p_create(w3(), 9) }
pub open spec fn w5() -> AS2 { p_miss(w4(), 1, Q::Ppr { seed: 9 }) }
pub open spec fn w6() -> AS2 { p_compute(w5(), 1, Q::Ppr { seed: 9 }, both()) }
pub open spec fn w7() -> AS2 { p_miss(w6(), 2, Q::PageRank) }
pub open spec fn w8() -> AS2 { p_compute(w7(), 2, Q::PageRank, both()) }

pub proof fn witness_acache()
    ensures
        init2(w0()),
        step2(w0(), AL2::LookupMiss { c: 0, q: Q::Ppr { seed: 9 } }, w1()),
        step2(w1(), AL2::Compute { c: 0, q: Q::Ppr { seed: 9 }, ans: none() }, w2()),
        step2(w2(), AL2::Put { c: 0 }, w3()),
        step2(w3(), AL2::LookupHit { c: 1, q: Q::Ppr { seed: 9 }, ans: none() }, w3()),
        step2(w3(), AL2::CreateNode { n: 9 }, w4()),
        step2(w4(), AL2::LookupMiss { c: 1, q: Q::Ppr { seed: 9 } }, w5()),
        step2(w5(), AL2::Compute { c: 1, q: Q::Ppr { seed: 9 }, ans: both() }, w6()),
        step2(w6(), AL2::LookupMiss { c: 2, q: Q::PageRank }, w7()),
        step2(w7(), AL2::Compute { c: 2, q: Q::PageRank, ans: both() }, w8()),
        step2(w8(), AL2::TriCount, w8()),
{
    let p = Q::Ppr { seed: 9 };
    lemma_a_steps(w0(), 0, p, none(), 9);
    assert(fresh2(w1(), p) == none());
    lemma_a_steps(w1(), 0, p, none(), 9);
    lemma_a_steps(w2(), 0, p, none(), 9);
    assert(hit(w3(), p));
    lemma_a_steps(w3(), 1, p, none(), 9);
    assert(!hit(w4(), p));
    lemma_a_steps(w4(), 1, p, none(), 9);
    assert(w5().nodes =~= Set::empty().insert(1int).insert(9int));
    assert(fresh2(w5(), p) == both());
    lemma_a_steps(w5(), 1, p, both(), 9);
    lemma_a_steps(w6(), 2, Q::PageRank, both(), 9);
    assert(fresh2(w7(), Q::PageRank) == both());
    lemma_a_steps(w7(), 2, Q::PageRank, both(), 9);
    lemma_a_steps(w8(), 2, Q::PageRank, both(), 9);
}

} // verus!
