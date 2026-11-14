//! Proved counterexample for control `control_f1610_tx_commit_per_statement` (F-1610), compiled only with it.
//!
//! The live trace c16-s1-cypher-http: POST /db/neo4j/tx/commit with CREATE c16:t1, an unparsable line and CREATE
//! c16:t3 answered 400 and committed both CREATEs. Here the first statement commits through `_run_cypher` (not an L1
//! step: nothing of the request is visible before it succeeds), the second fails, the request answers 400, and a
//! reader sees the first write without the second.
use vstd::prelude::*;
use actors::protocol::*;
use crate::unit_l1::*;
use crate::unit_l2::*;
use crate::unit_runs::*;

verus! {

pub proof fn counterexample_f1610()
    ensures
        init2(u0(Entry::Http)),
        step2(u0(Entry::Http), UL2::Begin, h1()),
        step2(h1(), UL2::Run1, h2()),
        !step_or_stutter::<UnitL1>(absu(h1()), labu(UL2::Run1), absu(h2())),
        step2(h2(), UL2::Run2 { ok: false, http: true }, h3()),
        step2(h3(), UL2::Read { a: 1, b: 0 }, h3()),
        !inv1(absu(h3())),
{
}

} // verus!
