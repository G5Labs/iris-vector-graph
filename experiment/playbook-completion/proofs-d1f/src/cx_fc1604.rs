//! Proved counterexample for control `control_fc1604_server_reruns_write` (F-C1604), compiled only with it.
//!
//! The live trace c16-s4-server-retry (the pin's FastAPI app on AUDITC, a lost acknowledgement injected after the
//! engine's commit): one request, the write committed, the connection is lost before the server learns the outcome,
//! `_run_cypher` resets the engine and runs the query again (cypher_api.py:239-250), which commits a second time (not
//! an L1 step: a write applies at most once), and the caller is answered 200 (counter 1 -> 3, two C16R2 nodes).
use vstd::prelude::*;
use actors::protocol::*;
use crate::call_l1::*;
use crate::call_l2::*;
use crate::call_runs::*;

verus! {

pub open spec fn g1() -> C2 { p_send(k0(Op::Write)) }
pub open spec fn g2() -> C2 { exec_post(g1(), false, true, false) }
pub open spec fn g3() -> C2 { exec_post(g2(), false, true, true) }
pub open spec fn g4() -> C2 { p_reply(g3()) }

pub proof fn counterexample_fc1604()
    ensures
        init2(k0(Op::Write)),
        step2(k0(Op::Write), CL2::Send { delivered: true, ans: None }, g1()),
        step2(g1(), CL2::Exec { pre_send: false, committed: true, ack: false, applies: true }, g2()),
        g2().server is Executing && g2().applied == 1,
        step2(g2(), CL2::Exec { pre_send: false, committed: true, ack: true, applies: true }, g3()),
        !step_or_stutter::<CallL1>(absc(g2()), labc(CL2::Exec { pre_send: false, committed: true, ack: true, applies: true }), absc(g3())),
        step2(g3(), CL2::Reply { delivered: true, ans: Some(Outcome::Success) }, g4()),
        g4().client == Client::Done(Outcome::Success) && g4().applied == 2,
        !inv1(absc(g4())),
{
    lemma_c_steps(k0(Op::Write), false, true, false);
    lemma_c_steps(g1(), false, true, false);
    lemma_c_steps(g2(), false, true, true);
    lemma_c_steps(g3(), false, true, true);
}

} // verus!
