//! Non-vacuity of the reviewed call model (compiled without its controls): a read whose reply is lost is resent and
//! succeeds; a write applied once is answered with success; a write whose acknowledgement is lost is answered
//! "unknown" (applied once, not resent); a write whose server connection was dead before the statement left is run
//! again on a fresh connection and succeeds; a write that never leaves the client (three connect errors) is a definite
//! failure with nothing applied.
use vstd::prelude::*;
use crate::call_l1::*;
use crate::call_l2::*;
use crate::call_runs::*;

verus! {

pub open spec fn r1() -> C2 { p_send(k0(Op::Read)) }
pub open spec fn r2() -> C2 { exec_post(r1(), false, false, true) }
pub open spec fn r3() -> C2 { p_lost(r2()) }
pub open spec fn r4() -> C2 { p_send(r3()) }
pub open spec fn r5() -> C2 { exec_post(r4(), false, false, true) }
pub open spec fn r6() -> C2 { p_reply(r5()) }

pub open spec fn x1() -> C2 { p_send(k0(Op::Write)) }
pub open spec fn x2() -> C2 { exec_post(x1(), false, true, true) }
pub open spec fn x3() -> C2 { p_reply(x2()) }
pub open spec fn y2() -> C2 { exec_post(x1(), false, true, false) }
pub open spec fn y3() -> C2 { p_reply(y2()) }
pub open spec fn z2() -> C2 { exec_post(x1(), true, false, false) }
pub open spec fn z3() -> C2 { exec_post(z2(), false, true, true) }
pub open spec fn z4() -> C2 { p_reply(z3()) }
pub open spec fn q1() -> C2 { p_refused(k0(Op::Write)) }
pub open spec fn q2() -> C2 { p_refused(q1()) }
pub open spec fn q3() -> C2 { p_refused(q2()) }

pub proof fn witness_call()
    ensures
        init2(k0(Op::Read)), init2(k0(Op::Write)),
        step2(k0(Op::Read), CL2::Send { delivered: true, ans: None }, r1()),
        step2(r1(), CL2::Exec { pre_send: false, committed: false, ack: true, applies: false }, r2()),
        step2(r2(), CL2::Reply { delivered: false, ans: None }, r3()),
        r3().client is Ready,
        step2(r3(), CL2::Send { delivered: true, ans: None }, r4()),
        step2(r4(), CL2::Exec { pre_send: false, committed: false, ack: true, applies: false }, r5()),
        step2(r5(), CL2::Reply { delivered: true, ans: Some(Outcome::Success) }, r6()),
        r6().client == Client::Done(Outcome::Success),
        step2(k0(Op::Write), CL2::Send { delivered: true, ans: None }, x1()),
        step2(x1(), CL2::Exec { pre_send: false, committed: true, ack: true, applies: true }, x2()),
        step2(x2(), CL2::Reply { delivered: true, ans: Some(Outcome::Success) }, x3()),
        x3().client == Client::Done(Outcome::Success) && x3().applied == 1,
        step2(x1(), CL2::Exec { pre_send: false, committed: true, ack: false, applies: true }, y2()),
        step2(y2(), CL2::Reply { delivered: true, ans: Some(Outcome::Unknown) }, y3()),
        y3().client == Client::Done(Outcome::Unknown) && y3().applied == 1,
        step2(x1(), CL2::Exec { pre_send: true, committed: false, ack: false, applies: false }, z2()),
        z2().server is Executing,
        step2(z2(), CL2::Exec { pre_send: false, committed: true, ack: true, applies: true }, z3()),
        step2(z3(), CL2::Reply { delivered: true, ans: Some(Outcome::Success) }, z4()),
        z4().client == Client::Done(Outcome::Success) && z4().applied == 1,
        step2(k0(Op::Write), CL2::Send { delivered: false, ans: None }, q1()),
        step2(q1(), CL2::Send { delivered: false, ans: None }, q2()),
        step2(q2(), CL2::Send { delivered: false, ans: Some(Outcome::Failed) }, q3()),
        q3().client == Client::Done(Outcome::Failed) && q3().applied == 0,
{
    lemma_c_steps(k0(Op::Read), false, false, true);
    lemma_c_steps(r1(), false, false, true);
    lemma_c_steps(r2(), false, false, true);
    lemma_c_steps(r3(), false, false, true);
    lemma_c_steps(r4(), false, false, true);
    lemma_c_steps(r5(), false, false, true);
    lemma_c_steps(k0(Op::Write), false, true, true);
    lemma_c_steps(x1(), false, true, true);
    lemma_c_steps(x2(), false, true, true);
    lemma_c_steps(x1(), false, true, false);
    lemma_c_steps(y2(), false, true, false);
    lemma_c_steps(x1(), true, false, false);
    lemma_c_steps(z2(), false, true, true);
    lemma_c_steps(z3(), false, true, true);
    lemma_c_steps(q1(), false, false, false);
    lemma_c_steps(q2(), false, false, false);
}

} // verus!
