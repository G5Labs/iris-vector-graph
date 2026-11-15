//! Proved counterexample for control `control_f1601_bolt_run_commits` (F-1601), compiled only with it.
//!
//! The live trace c16-s1-cypher-http (neo4j driver 6.4.1): a managed transaction whose second statement fails keeps
//! the first statement's node; ROLLBACK undoes nothing. Here RUN w1 commits at once (not an L1 step), RUN w2 fails, the
//! driver's ROLLBACK leaves w1 visible without w2 (a reader sees half a unit), and the driver's retry runs the unit
//! again: w1 is then visible twice (not at most once).
use vstd::prelude::*;
use actors::protocol::*;
use crate::unit_l1::*;
use crate::unit_l2::*;
use crate::unit_runs::*;

verus! {

pub proof fn counterexample_f1601()
    ensures
        init2(u0(Entry::Bolt)),
        step2(u0(Entry::Bolt), UL2::Begin, b1()),
        step2(b1(), UL2::Run1, b2()),
        !step_or_stutter::<UnitL1>(absu(b1()), labu(UL2::Run1), absu(b2())),
        step2(b2(), UL2::Run2 { ok: false, http: false }, b3()),
        step2(b3(), UL2::Rollback, b4()),
        step2(b4(), UL2::Read { a: 1, b: 0 }, b4()),
        !inv1(absu(b4())),
        step2(b4(), UL2::Retry, b5()),
        step2(b5(), UL2::Run1, b6()),
        step2(b6(), UL2::Run2 { ok: true, http: false }, b7()),
        step2(b7(), UL2::Commit, b8()),
        b8().w1 == 2 && b8().w2 == 1,
{
}

} // verus!
