//! Proved counterexample for control `control_fc1706_driver_floor` (F-C1706), compiled only with it.
//!
//! The validation runs val-driver532-1 against val-driver540-1 (F-C1706): uv sync of the pin installs
//! intersystems-irispython 5.3.2 (uv.lock:1358-1371; pyproject.toml:42 admits it), under which a duplicate INSERT inside
//! write_txn surfaces as '<LIST ERROR> ...', which is_duplicate does not recognise, so write_nodes raises
//! GraphWriteError instead of skipping the row. Here the locked install is not an L1 step (the driver does not work
//! with the product) and the duplicate write fails (not an L1 step: a duplicate is skipped).
use vstd::prelude::*;
use actors::protocol::*;
use crate::opsc_l1::*;
use crate::opsc_l2::*;

verus! {

pub open spec fn d0() -> O2 { O2 { deployed: Set::empty(), drv: None, rows: 0 } }
pub open spec fn d1() -> O2 { O2 { drv: Some(532), ..d0() } }

pub proof fn counterexample_fc1706()
    ensures
        init2(d0()),
        step2(d0(), OL2::Install { v: 532, locked: true }, d1()),
        !step_or_stutter::<OpscL1>(abso(d0()), labo(OL2::Install { v: 532, locked: true }), abso(d1())),
        step2(d0(), OL2::Install { v: 100, locked: false }, O2 { drv: Some(100), ..d0() }),
        step2(d1(), OL2::WriteNodes { dup: true, ok: false }, d1()),
        !step_or_stutter::<OpscL1>(abso(d1()), labo(OL2::WriteNodes { dup: true, ok: false }), abso(d1())),
{
}

} // verus!
