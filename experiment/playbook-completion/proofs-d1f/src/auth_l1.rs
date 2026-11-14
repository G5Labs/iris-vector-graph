//! Modules 16 and 17, L1: the authorization boundary of a server the operator started (the Cypher HTTP server with
//! its Bolt listener, or another app of the product), and what the HTTP client raises for a refusal.
//!
//! State: the operator's settings (`cfg`: IVG_API_KEY, IVG_READ_ONLY, the host it named) and the route code that ran
//! (`runs`, `writes`). A request carries where it comes from (`remote`: another machine), the key it shows, whether
//! its path is public, whether it writes, and the graph it names.
//!
//! Business rules (the contract `decide`):
//! - a server the operator started on the loopback address is not reachable from another machine, on any of its
//!   listeners (docs/ADMIN_API.md:26-28: Bolt "listens on the address --host names"; HD-1705: the open default on
//!   0.0.0.0 is the documented contract, and the address the operator names is honoured);
//! - with a key set, no route code runs for a request without it, except on a public path (API-T1, API-B1.2,
//!   API-X1.5; CHANGELOG.md:994-996: every app needs the key);
//! - read-only mode refuses writes, after the key gate (API-T3, API-D12);
//! - a graph name confers no authorization (HD-1601, supported: the namespace is the boundary);
//! - the client raises IVGClientError for a 401 or a 403, for every request (sdk.py:195-201, R225; IVGClientError
//!   docstring sdk.py:22-25).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub enum Host { Loopback, Any }
pub enum Kind { Read, Write }
pub struct Cfg { pub key: Option<nat>, pub ro: bool, pub host: Host }
pub struct Req { pub remote: bool, pub shown: Option<nat>, pub public: bool, pub kind: Kind, pub graph: nat }
pub enum Status { Unreachable, Unauthorized, ReadOnly, Ran }
pub enum Cls { IvgClientError, HttpStatusError, NoError }

pub struct A1 { pub cfg: Cfg, pub runs: nat, pub writes: nat }

pub enum AL1 {
    Request { r: Req, st: Status },
    /// what the client raises (or returns) for an answer of status `st` (401, 403 or 200)
    ClientSees { st: Status, cls: Cls },
}

pub open spec fn decide(c: Cfg, r: Req) -> Status {
    if r.remote && c.host is Loopback { Status::Unreachable }
    else if c.key is Some && !r.public && r.shown != c.key { Status::Unauthorized }
    else if c.ro && r.kind is Write { Status::ReadOnly }
    else { Status::Ran }
}

pub open spec fn ran(s: A1, r: Req, st: Status) -> A1 {
    if st is Ran { A1 { runs: s.runs + 1, writes: s.writes + (if r.kind is Write { 1nat } else { 0nat }), ..s } } else { s }
}

pub open spec fn client_class(st: Status) -> Cls { if st is Ran { Cls::NoError } else { Cls::IvgClientError } }

pub struct AuthL1;

impl Contract for AuthL1 {
    type S = A1;
    type L = AL1;

    open spec fn init(s: A1) -> bool { s.runs == 0 && s.writes == 0 }

    open spec fn next(s: A1, l: AL1, t: A1) -> bool {
        match l {
            AL1::Request { r, st } => (r.public ==> r.kind is Read) && st == decide(s.cfg, r) && t == ran(s, r, st),
            AL1::ClientSees { st, cls } => !(st is Unreachable) && cls == client_class(st) && t == s,
        }
    }
}

pub open spec fn inv1(s: A1) -> bool { s.writes <= s.runs }

impl SafeContract for AuthL1 {
    open spec fn inv(s: A1) -> bool { inv1(s) }
    proof fn init_safe(s: A1) {}
    proof fn step_safe(s: A1, l: AL1, t: A1) {}
}

/// API-T1, API-X1.5: with a key set, a request to a non-public path without it runs no route code.
pub proof fn theorem_no_route_code_without_the_key(s: A1, r: Req, st: Status, t: A1)
    requires AuthL1::next(s, AL1::Request { r, st }, t), s.cfg.key is Some, !r.public, r.shown != s.cfg.key,
    ensures t == s, !(st is Ran),
{
}

/// API-T3: read-only mode runs no write, and a caller without the key learns nothing of the mode (401, not 403).
pub proof fn theorem_read_only_after_the_key_gate(s: A1, r: Req, st: Status, t: A1)
    requires AuthL1::next(s, AL1::Request { r, st }, t), s.cfg.ro, r.kind is Write,
    ensures t.writes == s.writes, (s.cfg.key is Some && r.shown != s.cfg.key && !r.public && !r.remote) ==> st is Unauthorized,
{
}

/// ADMIN_API.md:26-28: a server started on the loopback address answers no other machine, on any listener.
pub proof fn theorem_loopback_server_unreachable_from_other_machines(s: A1, r: Req, st: Status, t: A1)
    requires AuthL1::next(s, AL1::Request { r, st }, t), s.cfg.host is Loopback, r.remote,
    ensures st is Unreachable, t == s,
{
}

/// HD-1601 (supported): two requests that differ only in the graph they name get the same answer.
pub proof fn theorem_graph_is_not_authorization(c: Cfg, r: Req, g: nat)
    ensures decide(c, r) == decide(c, Req { graph: g, ..r }),
{
}

/// sdk.py:195-201 (R225): a 401 or a 403 reaches the caller as IVGClientError.
pub proof fn theorem_refusals_raise_ivg_client_error(s: A1, st: Status, cls: Cls, t: A1)
    requires AuthL1::next(s, AL1::ClientSees { st, cls }, t), st is Unauthorized || st is ReadOnly,
    ensures cls is IvgClientError,
{
}

} // verus!
