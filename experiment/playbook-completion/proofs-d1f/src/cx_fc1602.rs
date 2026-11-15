//! Proved counterexample for control `control_fc1602_unknown_as_client_error` (F-C1602), compiled only with it.
//!
//! The probe c16-s6-status-maps (stub engine, no IRIS) shows a lost IRIS connection answered HTTP 400 on /api/cypher
//! (cypher_api.py:369-376). Here the write committed and the connection broke before the server learned it: the
//! server answers 400, so the caller is told the write failed although it was applied (not an L1 step: a definite
//! failure applied nothing), and may run it again itself.
use vstd::prelude::*;
use actors::protocol::*;
use crate::call_l1::*;
use crate::call_l2::*;
use crate::call_runs::*;

verus! {

pub open spec fn h1() -> C2 { p_send(k0(Op::Write)) }
pub open spec fn h2() -> C2 { exec_post(h1(), false, true, false) }
pub open spec fn h3() -> C2 { p_reply(h2()) }

pub proof fn counterexample_fc1602()
    ensures
        init2(k0(Op::Write)),
        step2(k0(Op::Write), CL2::Send { delivered: true, ans: None }, h1()),
        step2(h1(), CL2::Exec { pre_send: false, committed: true, ack: false, applies: true }, h2()),
        h2().server == Server::Replied(false) && h2().applied == 1,
        step2(h2(), CL2::Reply { delivered: true, ans: Some(Outcome::Failed) }, h3()),
        !step_or_stutter::<CallL1>(absc(h2()), labc(CL2::Reply { delivered: true, ans: Some(Outcome::Failed) }), absc(h3())),
        h3().client == Client::Done(Outcome::Failed) && h3().applied == 1,
{
    lemma_c_steps(k0(Op::Write), false, true, false);
    lemma_c_steps(h1(), false, true, false);
    lemma_c_steps(h2(), false, true, false);
}

} // verus!
