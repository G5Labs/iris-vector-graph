//! Proved counterexample for control `control_fc1703_client_resends_write` (F-C1703), compiled only with it.
//!
//! The live trace c17-live-server (IVGClient timeout 2 s, max_retries 3, a proxy holding the first reply 4 s): the
//! CREATE commits and is answered, the reply is late, the client times out and resends the same POST
//! (sdk.py:209-228), the server runs it again (not an L1 step: a write applies at most once), and the caller gets the
//! second answer: success, with two C17Dup nodes in AUDITC.
use vstd::prelude::*;
use actors::protocol::*;
use crate::call_l1::*;
use crate::call_l2::*;
use crate::call_runs::*;

verus! {

pub open spec fn m1() -> C2 { p_send(k0(Op::Write)) }
pub open spec fn m2() -> C2 { exec_post(m1(), false, true, true) }
pub open spec fn m3() -> C2 { p_lost(m2()) }
pub open spec fn m4() -> C2 { p_send(m3()) }
pub open spec fn m5() -> C2 { exec_post(m4(), false, true, true) }
pub open spec fn m6() -> C2 { p_reply(m5()) }

pub proof fn counterexample_fc1703()
    ensures
        init2(k0(Op::Write)),
        step2(k0(Op::Write), CL2::Send { delivered: true, ans: None }, m1()),
        step2(m1(), CL2::Exec { pre_send: false, committed: true, ack: true, applies: true }, m2()),
        step2(m2(), CL2::Reply { delivered: false, ans: None }, m3()),
        m3().client is Ready && m3().applied == 1,
        step2(m3(), CL2::Send { delivered: true, ans: None }, m4()),
        step2(m4(), CL2::Exec { pre_send: false, committed: true, ack: true, applies: true }, m5()),
        !step_or_stutter::<CallL1>(absc(m4()), labc(CL2::Exec { pre_send: false, committed: true, ack: true, applies: true }), absc(m5())),
        step2(m5(), CL2::Reply { delivered: true, ans: Some(Outcome::Success) }, m6()),
        m6().client == Client::Done(Outcome::Success) && m6().applied == 2,
        !inv1(absc(m6())),
{
    lemma_c_steps(k0(Op::Write), false, true, true);
    lemma_c_steps(m1(), false, true, true);
    lemma_c_steps(m2(), false, true, true);
    assert(lost_ans(m2()) is None);
    lemma_c_steps(m3(), false, true, true);
    lemma_c_steps(m4(), false, true, true);
    lemma_c_steps(m5(), false, true, true);
}

} // verus!
