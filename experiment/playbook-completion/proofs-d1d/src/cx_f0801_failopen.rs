//! Proved counterexample for control `control_f0801_fail_open` (F-0801, fail-open), compiled only with it.
//!
//! guard.py:42-56 reads any probe failure as never-enabled (pinned by tests/unit/test_ledger_guard.py
//! test_probe_failure_fails_open, b-08-run-unit). Here: the ledger is enabled in strict mode; a write whose probe
//! cannot run passes the guard and commits (not an L1 step).
use vstd::prelude::*;
use actors::protocol::*;
use crate::cyw_l1::*;
use crate::cyw_l2::*;
use crate::cyw_runs::*;

verus! {

pub open spec fn q2() -> Q { Q::CreateLit { ns: Set::empty().insert(2int), es: Set::empty() } }
pub open spec fn y1() -> CW2 { p_meta(c0(), true, true) }
pub open spec fn y2() -> CW2 { p_exec(y1(), q2(), false, (0, 0)) }

pub proof fn counterexample_f0801_failopen()
    ensures
        init2(c0()),
        step2(c0(), CWL2::Meta { en: true, strict: true }, y1()),
        step2(y1(), CWL2::Exec { q: q2(), pok: false, top: (0, 0) }, y2()),
        y2().nodes.contains(2),
        !step_or_stutter::<CwL1>(absc(y1()), labc(CWL2::Exec { q: q2(), pok: false, top: (0, 0) }), absc(y2())),
{
    lemma_c_steps(c0(), q2(), false, (0, 0), true, true, Why::Env);
    lemma_c_steps(y1(), q2(), false, (0, 0), true, true, Why::Env);
    assert(y2().nodes.contains(2));
}

} // verus!
