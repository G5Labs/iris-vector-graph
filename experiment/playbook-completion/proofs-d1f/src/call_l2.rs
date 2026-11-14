//! Modules 16 and 17, L2: one call through IVGClient and the Cypher HTTP server at pin 3eaa79cf, with ambiguous
//! acknowledgements; refinement of `call_l1` for every step, the invariant, and the controls F-C1604, F-C1602 and
//! F-C1703 (executable twin: models/breadth-c/src/retry.rs, machine M1).
//!
//! State: the client (`Ready` to send, `Waiting` for a reply, `Done` with the answer it raised or returned) and its
//! attempts (IVGClient max_retries = 3, sdk.py:93); the server's handling of the delivered request (`Executing`,
//! `Replied(ok)`, `Lost`: an answer that says the outcome is unknown) and its attempts (`_run_cypher` range(2),
//! cypher_api.py:241); the committed applications of the write in IRIS (`applied`); ghost `sent`: some server attempt
//! of this call sent its statement to IRIS.
//!
//! **Reviewed design** (HD-1603, HD-1702 working answers, one protocol):
//! - R16-1: the server runs a query again only when it is a read or its statement never left (the IRIS connection
//!   was found dead before the statement was sent). As built `_run_cypher` re-runs after ANY exception of the first
//!   attempt (cypher_api.py:239-250): control F-C1604.
//! - R16-2 (status map): a write whose statement left and whose outcome the server did not learn is answered as an
//!   unknown outcome, never as a definite client error. As built every exception is HTTP 400 with the error text
//!   (cypher_api.py:369-376; Neo.ClientError.Statement.SyntaxError on the Neo4j routes and Bolt): control F-C1602.
//! - R17-1: the client resends a request after a connect error (nothing left the client) and, after a timeout or a
//!   5xx, only a read; an ambiguous write is reported as unknown. As built IVGClient._post resends the same POST after
//!   a TimeoutException, a ConnectError or a 5xx whatever the query, and raises IVGClientError after the last attempt
//!   (sdk.py:209-228): control F-C1703.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::call_l1::*;

verus! {

pub enum Client { Ready, Waiting, Done(Outcome) }
pub enum Server { Idle, Executing, Replied(bool), Lost }

pub struct C2 {
    pub op: Op, pub client: Client, pub catt: nat, pub server: Server, pub satt: nat, pub applied: nat, pub sent: bool,
}

pub enum CL2 {
    /// the client sends POST /api/cypher; `delivered` false is a connect error (nothing left the client); `ans` is the
    /// answer this step gives the caller, if any
    Send { delivered: bool, ans: Option<Outcome> },
    /// one server attempt: `pre_send` the connection was dead before the statement left (nothing ran, and the server
    /// knows it); else the statement ran, `committed` whether IRIS committed it and `ack` whether the server learned the
    /// outcome; `applies` whether this attempt applied the write
    Exec { pre_send: bool, committed: bool, ack: bool, applies: bool },
    /// the server's reply reaches the client (`delivered`), or the client times out / a proxy answers 5xx
    Reply { delivered: bool, ans: Option<Outcome> },
}

pub open spec fn fc1604() -> bool { cfg!(feature = "control_fc1604_server_reruns_write") }
pub open spec fn fc1602() -> bool { cfg!(feature = "control_fc1602_unknown_as_client_error") }
pub open spec fn fc1703() -> bool { cfg!(feature = "control_fc1703_client_resends_write") }

pub open spec fn cmax() -> nat { 3 }
pub open spec fn smax() -> nat { 2 }

pub open spec fn client_resends(op: Op) -> bool { op is Read || fc1703() }
pub open spec fn server_reruns(op: Op) -> bool { op is Read || fc1604() }
pub open spec fn reports_failed(op: Op) -> bool { op is Read || fc1602() }

pub open spec fn exec_server(s: C2, pre_send: bool, committed: bool, ack: bool) -> Server {
    let more = s.satt + 1 < smax();
    if pre_send { if more { Server::Executing } else { Server::Replied(false) } }
    else if ack { Server::Replied(committed || s.op is Read) }
    else if server_reruns(s.op) && more { Server::Executing }
    else if reports_failed(s.op) { Server::Replied(false) }
    else { Server::Lost }
}

pub open spec fn exec_post(s: C2, pre_send: bool, committed: bool, ack: bool) -> C2 {
    C2 { satt: s.satt + 1, server: exec_server(s, pre_send, committed, ack),
         applied: if !pre_send && committed && s.op is Write { s.applied + 1 } else { s.applied },
         sent: s.sent || !pre_send, ..s }
}

pub open spec fn answer_of(sv: Server) -> Outcome {
    match sv { Server::Replied(ok) => if ok { Outcome::Success } else { Outcome::Failed }, _ => Outcome::Unknown }
}

pub open spec fn replied(sv: Server) -> bool { sv is Replied || sv is Lost }

pub open spec fn init2(s: C2) -> bool {
    s.client is Ready && s.catt == 0 && s.server is Idle && s.satt == 0 && s.applied == 0 && !s.sent
}

pub open spec fn step2(s: C2, l: CL2, t: C2) -> bool {
    match l {
        CL2::Send { delivered, ans } =>
            s.client is Ready && s.catt < cmax() && if delivered {
                ans is None && t == C2 { client: Client::Waiting, catt: s.catt + 1, server: Server::Executing, satt: 0, ..s }
            } else if s.catt + 1 >= cmax() {
                ans == Some(Outcome::Failed) && t == C2 { client: Client::Done(Outcome::Failed), catt: s.catt + 1, ..s }
            } else {
                ans is None && t == C2 { catt: s.catt + 1, ..s }
            },
        CL2::Exec { pre_send, committed, ack, applies } =>
            s.server is Executing && s.satt < smax() && !(pre_send && committed)
                && applies == (!pre_send && committed && s.op is Write)
                && t == exec_post(s, pre_send, committed, ack),
        CL2::Reply { delivered, ans } =>
            s.client is Waiting && replied(s.server) && if delivered {
                ans == Some(answer_of(s.server)) && t == C2 { client: Client::Done(answer_of(s.server)), server: Server::Idle, ..s }
            } else if client_resends(s.op) && s.catt < cmax() {
                ans is None && t == C2 { client: Client::Ready, server: Server::Idle, ..s }
            } else if client_resends(s.op) {
                ans == Some(Outcome::Failed) && t == C2 { client: Client::Done(Outcome::Failed), server: Server::Idle, ..s }
            } else {
                ans == Some(Outcome::Unknown) && t == C2 { client: Client::Done(Outcome::Unknown), server: Server::Idle, ..s }
            },
    }
}

pub open spec fn absc(s: C2) -> C1 {
    C1 { op: s.op, applied: s.applied, answer: match s.client { Client::Done(o) => Some(o), _ => None } }
}

pub open spec fn ans_lab(ans: Option<Outcome>) -> Option<CL1> { match ans { Some(o) => Some(CL1::Answer { o }), None => None } }

pub open spec fn labc(l: CL2) -> Option<CL1> {
    match l {
        CL2::Send { delivered, ans } => ans_lab(ans),
        CL2::Exec { pre_send, committed, ack, applies } => if applies { Some(CL1::Apply) } else { None },
        CL2::Reply { delivered, ans } => ans_lab(ans),
    }
}

/// What a write's call has done so far, by the client's and the server's states.
pub open spec fn write_ok(s: C2) -> bool {
    &&& s.server is Executing ==> !s.sent
    &&& s.server == Server::Replied(true) ==> s.applied == 1
    &&& s.server == Server::Replied(false) ==> s.applied == 0
    &&& s.client is Ready ==> !s.sent
}

pub open spec fn inv16c(s: C2) -> bool {
    &&& inv1(absc(s))
    &&& s.server is Executing ==> s.client is Waiting
    &&& s.client is Done ==> s.server is Idle
    &&& s.client is Ready ==> s.server is Idle
    &&& s.client is Waiting ==> !(s.server is Idle)
    &&& !s.sent ==> s.applied == 0
    &&& s.op is Write ==> write_ok(s)
}

pub struct CallL2;

impl Contract for CallL2 {
    type S = C2;
    type L = CL2;
    open spec fn init(s: C2) -> bool { init2(s) }
    open spec fn next(s: C2, l: CL2, t: C2) -> bool { inv16c(s) && step2(s, l, t) }
}

pub struct CallRaw;

impl Contract for CallRaw {
    type S = C2;
    type L = CL2;
    open spec fn init(s: C2) -> bool { init2(s) }
    open spec fn next(s: C2, l: CL2, t: C2) -> bool { step2(s, l, t) }
}

proof fn lemma_exec(s: C2, pre_send: bool, committed: bool, ack: bool, applies: bool, t: C2)
    requires inv16c(s), step2(s, CL2::Exec { pre_send, committed, ack, applies }, t),
    ensures inv16c(t), step_or_stutter::<CallL1>(absc(s), labc(CL2::Exec { pre_send, committed, ack, applies }), absc(t)),
{
    if s.op is Write && !pre_send {
        // R16-1: once a write's statement has left, the server never runs it again (control F-C1604 fails here)
        assert(!(t.server is Executing));
        // R16-2: an unacknowledged write is answered "outcome unknown", not a definite failure (control F-C1602 fails here)
        assert(!ack ==> t.server is Lost);
    }
}

proof fn lemma_reply(s: C2, delivered: bool, ans: Option<Outcome>, t: C2)
    requires inv16c(s), step2(s, CL2::Reply { delivered, ans }, t),
    ensures inv16c(t), step_or_stutter::<CallL1>(absc(s), labc(CL2::Reply { delivered, ans }), absc(t)),
{
    if s.op is Write && !delivered {
        // R17-1: after a timeout or a 5xx the client reports a write's outcome as unknown and never resends it
        // (control F-C1703 fails here)
        assert(t.client == Client::Done(Outcome::Unknown));
    }
}

pub proof fn lemma_step(s: C2, l: CL2, t: C2)
    requires inv16c(s), step2(s, l, t),
    ensures inv16c(t), step_or_stutter::<CallL1>(absc(s), labc(l), absc(t)),
{
    match l {
        CL2::Exec { pre_send, committed, ack, applies } => lemma_exec(s, pre_send, committed, ack, applies, t),
        CL2::Reply { delivered, ans } => lemma_reply(s, delivered, ans, t),
        CL2::Send { delivered, ans } => {}
    }
}

impl Refines<CallL1> for CallL2 {
    open spec fn abs(s: C2) -> C1 { absc(s) }
    open spec fn lab(l: CL2) -> Option<CL1> { labc(l) }
    proof fn init_refines(s: C2) {}
    proof fn step_refines(s: C2, l: CL2, t: C2) { lemma_step(s, l, t); }
}

impl SafeContract for CallL2 {
    open spec fn inv(s: C2) -> bool { inv16c(s) }
    proof fn init_safe(s: C2) {}
    proof fn step_safe(s: C2, l: CL2, t: C2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<C2>, labels: Seq<CL2>, k: int)
    requires execution::<CallRaw>(states, labels), 0 <= k < states.len(),
    ensures inv16c(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution: one call applies its write at most once and answers honestly, across both retry layers.
pub proof fn theorem_raw_executions_refine(states: Seq<C2>, labels: Seq<CL2>)
    requires execution::<CallRaw>(states, labels),
    ensures
        execution::<CallL2>(states, labels),
        abstract_execution::<CallL1>(Seq::new(states.len(), |i: int| absc(states[i])),
                                     Seq::new(labels.len(), |i: int| labc(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv16c(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv16c(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<CallL2>(states, labels));
    trace_refines::<CallL2, CallL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absc(states[i])) =~= Seq::new(states.len(), |i: int| <CallL2 as Refines<CallL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labc(labels[i])) =~= Seq::new(labels.len(), |i: int| <CallL2 as Refines<CallL1>>::lab(labels[i])));
}

/// The status map on the layout: a server answer of success for a write means it was applied once; a server answer
/// of failure for a write means nothing was applied.
pub proof fn theorem_server_answers_are_honest(s: C2)
    requires inv16c(s), s.op is Write,
    ensures s.server == Server::Replied(true) ==> s.applied == 1, s.server == Server::Replied(false) ==> s.applied == 0,
{
}

} // verus!
