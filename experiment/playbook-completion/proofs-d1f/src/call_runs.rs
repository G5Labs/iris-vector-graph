//! The call L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::call_l1::*;
use crate::call_l2::*;

verus! {

pub open spec fn k0(op: Op) -> C2 {
    C2 { op, client: Client::Ready, catt: 0, server: Server::Idle, satt: 0, applied: 0, sent: false }
}
pub open spec fn p_send(s: C2) -> C2 { C2 { client: Client::Waiting, catt: s.catt + 1, server: Server::Executing, satt: 0, ..s } }
pub open spec fn p_refused(s: C2) -> C2 {
    if s.catt + 1 >= cmax() { C2 { client: Client::Done(Outcome::Failed), catt: s.catt + 1, ..s } } else { C2 { catt: s.catt + 1, ..s } }
}
pub open spec fn p_reply(s: C2) -> C2 { C2 { client: Client::Done(answer_of(s.server)), server: Server::Idle, ..s } }
pub open spec fn p_lost(s: C2) -> C2 {
    if client_resends(s.op) && s.catt < cmax() { C2 { client: Client::Ready, server: Server::Idle, ..s } }
    else if client_resends(s.op) { C2 { client: Client::Done(Outcome::Failed), server: Server::Idle, ..s } }
    else { C2 { client: Client::Done(Outcome::Unknown), server: Server::Idle, ..s } }
}
pub open spec fn lost_ans(s: C2) -> Option<Outcome> {
    if client_resends(s.op) && s.catt < cmax() { None } else if client_resends(s.op) { Some(Outcome::Failed) } else { Some(Outcome::Unknown) }
}

pub proof fn lemma_c_steps(s: C2, pre_send: bool, committed: bool, ack: bool)
    ensures
        s.client is Ready && s.catt < cmax() ==> step2(s, CL2::Send { delivered: true, ans: None }, p_send(s)),
        s.client is Ready && s.catt < cmax() ==> step2(s, CL2::Send { delivered: false,
            ans: if s.catt + 1 >= cmax() { Some(Outcome::Failed) } else { None } }, p_refused(s)),
        s.server is Executing && s.satt < smax() && !(pre_send && committed) ==> step2(s, CL2::Exec { pre_send, committed, ack,
            applies: !pre_send && committed && s.op is Write }, exec_post(s, pre_send, committed, ack)),
        s.client is Waiting && replied(s.server) ==> step2(s, CL2::Reply { delivered: true, ans: Some(answer_of(s.server)) }, p_reply(s)),
        s.client is Waiting && replied(s.server) ==> step2(s, CL2::Reply { delivered: false, ans: lost_ans(s) }, p_lost(s)),
{
}

} // verus!
