//! Proved counterexample for control `control_f0801_fail_open` (F-0801 / LED-B11.3), compiled only with it.
//!
//! Strict mode is on; the guard's probe fails (it reads as never-enabled, guard.py:55-56) and create_node lands:
//! a governed write landing while the ledger is enabled in strict mode, not an L1 step.
use vstd::prelude::*;
use actors::protocol::*;
use crate::ledger_l1::*;
use crate::ledger_l2::*;
use crate::cx_ledger_common::*;

verus! {

pub open spec fn k1() -> K { K { id: 1, edge: false } }
pub open spec fn c2() -> LS2 { LS2 { probe_fails: true, ..c_genesis(true) } }
pub open spec fn l3() -> L2Label { L2Label::EngineWrite { w: Wr::Api, k: k1(), v: Some(7), landed: true } }
pub open spec fn c3() -> LS2 { engine_write(c2(), Wr::Api, k1(), Some(7)) }

pub proof fn counterexample_f0801_failopen()
    ensures
        init2(c_init()),
        step2(c_init(), L2Label::Enable { strict: true, id: 1, recs: seq![], busy: false }, c_genesis(true)),
        step2(c_genesis(true), L2Label::ProbeFails { on: true }, c2()),
        step2(c2(), l3(), c3()),
        strict_on(c2().meta) && c3().rows.contains_key(k1()),
        !step_or_stutter::<L1>(abs11(c2()), lab11(l3()), abs11(c3())),
{
    lemma_genesis_step(true);
    assert(step2(c_genesis(true), L2Label::ProbeFails { on: true }, c2()));
    assert(!refuses(c2(), Wr::Api));
    assert(step2(c2(), l3(), c3()));
}

} // verus!
