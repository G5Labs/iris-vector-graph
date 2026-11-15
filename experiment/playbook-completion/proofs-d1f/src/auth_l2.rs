//! Modules 16 and 17, L2: a running server at pin 3eaa79cf (its HTTP listener with the middleware stack, its Bolt TCP
//! listener) and the SDK's mapping of answers to exceptions; refinement of `auth_l1` for every step, the invariant,
//! and the controls F-1614, F-C1603 and F-1714.
//!
//! State: the operator's settings, whether the server was started by `ivg server start` (`via_cli`), the address the
//! Bolt TCP listener bound (`bolt`, None until the app's lifespan opens it), and the route code that ran.
//!
//! The HTTP decision is the app's middleware stack (cypher_api.py:95-118; api_auth.py:77-187): uvicorn binds the host;
//! CORSMiddleware answers preflights (not modelled); ApiKeyMiddleware refuses 401 unless the path is public
//! (api_auth.py:104-123); ReadOnlyMiddleware refuses writes under /admin/ with 403, and each Cypher route refuses a
//! mutation itself (cypher_api.py:353-354, 381-385, 438). The Bolt decision: the listener's address, HELLO/LOGON with the
//! key (in protocol), RUN's AccessMode refusal under IVG_READ_ONLY (bolt_server.py:570-577).
//!
//! **Reviewed design**:
//! - R16-3 (CHANGELOG.md:994-996, every app needs the key): every app the product serves has the key gate. As built
//!   the demo server's app has no ApiKeyMiddleware (src/iris_demo_server/app.py:1-22): control F-1614.
//! - R16-4 (ADMIN_API.md:26-28): the Bolt listener binds the host the operator named, however the app is started.
//!   As built `_lifespan` defaults BOLT_TCP_HOST to 0.0.0.0 (cypher_api.py:51) and only `ivg server start` sets it from
//!   --host (cli.py:429): control F-C1603.
//! - R17-2 (sdk.py:195-201): every SDK call maps 401/403 through `_refused`. As built `explain`, `load_ndjson` and
//!   AsyncIVGClient call `raise_for_status()` directly (sdk.py:166-182, 254-281): control F-1714.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::auth_l1::*;

verus! {

pub enum CallKind { Cypher, Explain, Load, Async }

pub struct A2 { pub cfg: Cfg, pub via_cli: bool, pub bolt: Option<Host>, pub runs: nat, pub writes: nat }

pub enum AL2 {
    /// the app's lifespan opens the Bolt TCP listener (cypher_api.py:47-63)
    ListenBolt,
    /// an HTTP request through the middleware stack to a route
    Http { r: Req, st: Status },
    /// a Bolt session's HELLO/LOGON and RUN on the TCP listener
    Bolt { r: Req, st: Status },
    /// an SDK call of kind `call` gets an answer of status `st` and raises (or returns) `cls`
    ClientSees { st: Status, call: CallKind, cls: Cls },
}

pub open spec fn f1614() -> bool { cfg!(feature = "control_f1614_app_without_key_gate") }
pub open spec fn fc1603() -> bool { cfg!(feature = "control_fc1603_bolt_binds_every_interface") }
pub open spec fn f1714() -> bool { cfg!(feature = "control_f1714_unmapped_refusal") }

pub open spec fn bolt_bind(s: A2) -> Host { if fc1603() && !s.via_cli { Host::Any } else { s.cfg.host } }

pub open spec fn http_decide(s: A2, r: Req) -> Status {
    if r.remote && s.cfg.host is Loopback { Status::Unreachable }
    else if !f1614() && s.cfg.key is Some && !r.public && r.shown != s.cfg.key { Status::Unauthorized }
    else if s.cfg.ro && r.kind is Write { Status::ReadOnly }
    else { Status::Ran }
}

pub open spec fn bolt_decide(s: A2, h: Host, r: Req) -> Status {
    if r.remote && h is Loopback { Status::Unreachable }
    else if s.cfg.key is Some && r.shown != s.cfg.key { Status::Unauthorized }
    else if s.cfg.ro && r.kind is Write { Status::ReadOnly }
    else { Status::Ran }
}

pub open spec fn client_cls(call: CallKind, st: Status) -> Cls {
    if st is Ran { Cls::NoError }
    else if f1714() && !(call is Cypher) { Cls::HttpStatusError }
    else { Cls::IvgClientError }
}

pub open spec fn ran2(s: A2, r: Req, st: Status) -> A2 {
    if st is Ran { A2 { runs: s.runs + 1, writes: s.writes + (if r.kind is Write { 1nat } else { 0nat }), ..s } } else { s }
}

pub open spec fn init2(s: A2) -> bool { s.bolt is None && s.runs == 0 && s.writes == 0 }

pub open spec fn step2(s: A2, l: AL2, t: A2) -> bool {
    match l {
        AL2::ListenBolt => s.bolt is None && t == A2 { bolt: Some(bolt_bind(s)), ..s },
        AL2::Http { r, st } => (r.public ==> r.kind is Read) && st == http_decide(s, r) && t == ran2(s, r, st),
        AL2::Bolt { r, st } =>
            s.bolt is Some && !r.public && st == bolt_decide(s, s.bolt->Some_0, r) && t == ran2(s, r, st),
        AL2::ClientSees { st, call, cls } => !(st is Unreachable) && cls == client_cls(call, st) && t == s,
    }
}

pub open spec fn absa(s: A2) -> A1 { A1 { cfg: s.cfg, runs: s.runs, writes: s.writes } }

pub open spec fn laba(l: AL2) -> Option<AL1> {
    match l {
        AL2::ListenBolt => None,
        AL2::Http { r, st } => Some(AL1::Request { r, st }),
        AL2::Bolt { r, st } => Some(AL1::Request { r, st }),
        AL2::ClientSees { st, call, cls } => Some(AL1::ClientSees { st, cls }),
    }
}

/// The Bolt listener is bound where the operator said.
pub open spec fn inv16a(s: A2) -> bool { inv1(absa(s)) && (s.bolt is Some ==> s.bolt->Some_0 == s.cfg.host) }

pub struct AuthL2;

impl Contract for AuthL2 {
    type S = A2;
    type L = AL2;
    open spec fn init(s: A2) -> bool { init2(s) }
    open spec fn next(s: A2, l: AL2, t: A2) -> bool { inv16a(s) && step2(s, l, t) }
}

pub struct AuthRaw;

impl Contract for AuthRaw {
    type S = A2;
    type L = AL2;
    open spec fn init(s: A2) -> bool { init2(s) }
    open spec fn next(s: A2, l: AL2, t: A2) -> bool { step2(s, l, t) }
}

proof fn lemma_listen(s: A2, t: A2)
    requires inv16a(s), step2(s, AL2::ListenBolt, t),
    ensures inv16a(t), step_or_stutter::<AuthL1>(absa(s), laba(AL2::ListenBolt), absa(t)),
{
    // R16-4: the Bolt listener binds the host the operator named (control F-C1603 fails here)
    assert(t.bolt->Some_0 == s.cfg.host);
}

proof fn lemma_http(s: A2, r: Req, st: Status, t: A2)
    requires inv16a(s), step2(s, AL2::Http { r, st }, t),
    ensures inv16a(t), step_or_stutter::<AuthL1>(absa(s), laba(AL2::Http { r, st }), absa(t)),
{
    // R16-3: the app's middleware decides as the contract does: key gate, then read-only (control F-1614 fails here)
    assert(st == decide(s.cfg, r));
}

proof fn lemma_bolt(s: A2, r: Req, st: Status, t: A2)
    requires inv16a(s), step2(s, AL2::Bolt { r, st }, t),
    ensures inv16a(t), step_or_stutter::<AuthL1>(absa(s), laba(AL2::Bolt { r, st }), absa(t)),
{
    assert(st == decide(s.cfg, r));
}

proof fn lemma_client(s: A2, st: Status, call: CallKind, cls: Cls, t: A2)
    requires inv16a(s), step2(s, AL2::ClientSees { st, call, cls }, t),
    ensures inv16a(t), step_or_stutter::<AuthL1>(absa(s), laba(AL2::ClientSees { st, call, cls }), absa(t)),
{
    // R17-2: every SDK call raises IVGClientError for a 401 or a 403 (control F-1714 fails here)
    assert(cls == client_class(st));
}

pub proof fn lemma_step(s: A2, l: AL2, t: A2)
    requires inv16a(s), step2(s, l, t),
    ensures inv16a(t), step_or_stutter::<AuthL1>(absa(s), laba(l), absa(t)),
{
    match l {
        AL2::ListenBolt => lemma_listen(s, t),
        AL2::Http { r, st } => lemma_http(s, r, st, t),
        AL2::Bolt { r, st } => lemma_bolt(s, r, st, t),
        AL2::ClientSees { st, call, cls } => lemma_client(s, st, call, cls, t),
    }
}

impl Refines<AuthL1> for AuthL2 {
    open spec fn abs(s: A2) -> A1 { absa(s) }
    open spec fn lab(l: AL2) -> Option<AL1> { laba(l) }
    proof fn init_refines(s: A2) {}
    proof fn step_refines(s: A2, l: AL2, t: A2) { lemma_step(s, l, t); }
}

impl SafeContract for AuthL2 {
    open spec fn inv(s: A2) -> bool { inv16a(s) }
    proof fn init_safe(s: A2) {}
    proof fn step_safe(s: A2, l: AL2, t: A2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<A2>, labels: Seq<AL2>, k: int)
    requires execution::<AuthRaw>(states, labels), 0 <= k < states.len(),
    ensures inv16a(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution: every request on every listener is decided as the contract says.
pub proof fn theorem_raw_executions_refine(states: Seq<A2>, labels: Seq<AL2>)
    requires execution::<AuthRaw>(states, labels),
    ensures
        execution::<AuthL2>(states, labels),
        abstract_execution::<AuthL1>(Seq::new(states.len(), |i: int| absa(states[i])),
                                     Seq::new(labels.len(), |i: int| laba(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv16a(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv16a(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<AuthL2>(states, labels));
    trace_refines::<AuthL2, AuthL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absa(states[i])) =~= Seq::new(states.len(), |i: int| <AuthL2 as Refines<AuthL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| laba(labels[i])) =~= Seq::new(labels.len(), |i: int| <AuthL2 as Refines<AuthL1>>::lab(labels[i])));
}

} // verus!
