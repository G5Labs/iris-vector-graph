//! Proved counterexamples for controls `control_hd1701_read_only_ignored` and `control_hd1701_write_reported_failed`
//! (HD-1701), each compiled only with its control.
//!
//! The live probe ib-HD1701-readonly-flag (AUDITIB): with read_only=True an INSERT into Graph_KG.nodes and a CREATE
//! TABLE both executed, and each answer carried IVGResult.error '<USAGE ERROR> ... did not return a result set'.
use vstd::prelude::*;
use actors::protocol::*;
use crate::sqla_l1::*;
use crate::sqla_l2::*;
use crate::sqla_runs::*;

verus! {

pub open spec fn qw() -> Q2 { Q2 { writes: 1, ..q0() } }

/// read_only ignored: the INSERT runs under read_only=True (not an L1 step: a read-only call writes nothing).
#[cfg(feature = "control_hd1701_read_only_ignored")]
pub proof fn counterexample_hd1701_read_only()
    ensures
        init2(q0()),
        step2(q0(), QL2::Exec { write: true, ro: true, ok: true }, qw()),
        !step_or_stutter::<SqlaL1>(absq(q0()), labq(QL2::Exec { write: true, ro: true, ok: true }), absq(qw())),
{
}

/// The INSERT that ran is answered with an error (not an L1 step: an error answer means nothing ran).
#[cfg(feature = "control_hd1701_write_reported_failed")]
pub proof fn counterexample_hd1701_write_reported()
    ensures
        init2(q0()),
        step2(q0(), QL2::Exec { write: true, ro: false, ok: false }, qw()),
        !step_or_stutter::<SqlaL1>(absq(q0()), labq(QL2::Exec { write: true, ro: false, ok: false }), absq(qw())),
{
}

} // verus!
