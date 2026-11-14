//! Proved counterexample for control `control_fc1001_read_creates_routines` (F-C1001), compiled only with it.
//!
//! The live traces b-10-live-fp and b-10-live-fp-detail (the first triangle_count in AUDITB, Arno library absent,
//! wrote ^IVG.Deploy, ^oddDEP and ^oddTSQL and created the Graph.KG.funcivgarnozf* classes, then answered from the
//! LazyKG walk): on a namespace without the wrappers, triangle_count creates them and records them, which is not an L1
//! step (a read changes no content).
use vstd::prelude::*;
use actors::protocol::*;
use crate::acache_l1::*;
use crate::acache_l2::*;
use crate::acache_runs::*;

verus! {

pub open spec fn c0() -> AS2 { a_init(Set::empty().insert(1int), Set::empty(), Set::empty(), Set::empty()) }
pub open spec fn c1() -> AS2 { p_tri(c0()) }

pub proof fn counterexample_fc1001()
    ensures
        init2(c0()),
        step2(c0(), AL2::TriCount, c1()),
        c1().dict.contains(1000) && !c0().dict.contains(1000) && c1().rrec.contains(1000),
        !step_or_stutter::<CacheL1>(absa(c0()), laba(AL2::TriCount), absa(c1())),
{
    lemma_a_steps(c0(), 0, Q::PageRank, Ans { rows: Set::empty(), over: Set::empty() }, 0);
    assert(zf().contains(1000));
    assert(c1().dict.contains(1000));
}

} // verus!
