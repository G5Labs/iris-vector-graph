//! M-02 Retry and idempotency binding (axioms AX-06, AX-12). Generic machine over `RetryObject`.
//!
//! One request identity (a retry key or a business identity), two payloads (1, 2). The client sends; the server
//! answers (first answer, replay, conflict, or redacted refusal) per the object's dedup policy; the answer is
//! delivered or lost (an ambiguous outcome); the client may retry per its policy and, after an ok answer, run a
//! post-commit step per its policy. A redaction of the bound revision moves the binding to redacted (Ledger.cls
//! 454-473 idemRedacted) or, in a variant, keeps it.
//! Canonical (Ledger.Commit, iris_src/src/Graph/KG/Ledger.cls:454-473): the binding is written in the commit's
//! transaction; same fingerprint -> the first answer, no effect; another fingerprint -> idempotency_conflict.
//!
//! Laws: M02-L1 (invariant) effects <= 1 and post-commit effects <= 1; M02-L2 (action) a replay changes nothing (no
//! effect, no post-commit step on a replayed answer); M02-L3 (action) another payload under a bound key changes
//! nothing; M02-L4 (invariant) after redaction the binding is not bound.
//! Bounds: at most 3 sends.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Dedup { Atomic, TwoStep, NoDedup, ApplyConflict }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum ClientRetry { AppRetry, ResendOnLost, Never }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Post { Always, SkipOnReplay, NoPost }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Redact { Moves, Keeps }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Policy { pub dedup: Dedup, pub client: ClientRetry, pub post: Post, pub redact: Redact, pub rerun: bool }

pub trait RetryObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn as_built(&self) -> Policy;
    fn reviewed(&self) -> Policy;
    fn departs(&self) -> (&'static str, &'static [&'static str]);
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Bind { Free, Bound(u8), Redacted }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Reply { First, Replay, Conflict, Refused }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Client { Idle, InFlight(u8, Reply), Answered(Reply), Lost(u8), Done }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub bind: Bind,
    pub effects: u8,
    pub post: u8,
    pub client: Client,
    pub sends: u8,
    pub mid: bool,
    pub reran: bool,
    pub redacted: bool,
}

#[derive(Clone, Debug)]
pub enum A { Send(u8), Deliver, Lose, PostStep, Skip, Stop, FinishBind, Rerun, RedactRev }

pub struct Machine<'a, O: RetryObject> { pub o: &'a O, pub p: Policy }

pub const L1: &str = "M02-L1 at most one effect per identity";
pub const L2: &str = "M02-L2 a replay changes nothing";
pub const L3: &str = "M02-L3 a conflicting payload changes nothing";
pub const L4: &str = "M02-L4 redaction removes the binding";

impl<'a, O: RetryObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { bind: Bind::Free, effects: 0, post: 0, client: Client::Idle, sends: 0, mid: false, reran: false, redacted: false }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::Send(1), A::Send(2), A::Deliver, A::Lose, A::PostStep, A::Skip, A::Stop, A::FinishBind, A::Rerun, A::RedactRev]
    }
    fn within_bounds(&self, s: &S) -> bool { s.sends < 3 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let p = self.p;
        let mut u = s.clone();
        match *a {
            A::Send(x) => {
                let may = match (s.client, p.client) {
                    (Client::Idle, _) => s.sends == 0 || p.client == ClientRetry::AppRetry,
                    (Client::Done, ClientRetry::AppRetry) => true,
                    (Client::Lost(y), ClientRetry::ResendOnLost) | (Client::Lost(y), ClientRetry::AppRetry) => y == x,
                    _ => false,
                };
                if !may || s.mid { return None; }
                if x == 2 && s.sends == 0 { return None; } // the first request carries payload 1
                u.sends += 1;
                let reply = match (p.dedup, s.bind) {
                    (Dedup::NoDedup, _) => { u.effects += 1; Reply::First }
                    (_, Bind::Redacted) => Reply::Refused,
                    (Dedup::Atomic, Bind::Free) | (Dedup::ApplyConflict, Bind::Free) => { u.effects += 1; u.bind = Bind::Bound(x); Reply::First }
                    (Dedup::TwoStep, Bind::Free) => { u.effects += 1; u.mid = true; Reply::First }
                    (Dedup::ApplyConflict, Bind::Bound(y)) if y != x => { u.effects += 1; u.bind = Bind::Bound(x); Reply::First }
                    (_, Bind::Bound(y)) if y == x => Reply::Replay,
                    (_, Bind::Bound(_)) => Reply::Conflict,
                };
                u.client = Client::InFlight(x, reply);
            }
            A::FinishBind => { if !s.mid { return None; } u.mid = false; if let Client::InFlight(x, _) = s.client { u.bind = Bind::Bound(x); } else { return None; } }
            A::Stop => { if !s.mid { return None; } u.mid = false; if let Client::InFlight(x, _) = s.client { u.client = Client::Lost(x); } else { return None; } }
            A::Deliver => { if s.mid { return None; } let Client::InFlight(_, r) = s.client else { return None }; u.client = Client::Answered(r); }
            A::Lose => { if s.mid { return None; } let Client::InFlight(x, _) = s.client else { return None }; u.client = Client::Lost(x); }
            A::Rerun => {
                // the server runs the request again after an error raised after its commit (cypher_api.py:250-268)
                if !p.rerun || s.reran || s.mid { return None; }
                let Client::InFlight(x, Reply::First) = s.client else { return None };
                u.reran = true;
                if p.dedup == Dedup::NoDedup { u.effects += 1; }
                u.client = Client::InFlight(x, Reply::First);
            }
            A::PostStep => {
                let Client::Answered(r) = s.client else { return None };
                if !matches!(r, Reply::First | Reply::Replay) { return None; }
                let runs = match p.post { Post::Always => true, Post::SkipOnReplay => r == Reply::First, Post::NoPost => false };
                if runs { u.post += 1; }
                u.client = Client::Done;
            }
            A::Skip => { let Client::Answered(r) = s.client else { return None }; if matches!(r, Reply::First | Reply::Replay) && p.post != Post::NoPost { return None; } u.client = Client::Done; }
            A::RedactRev => {
                if s.redacted || !matches!(s.bind, Bind::Bound(_)) || s.mid { return None; }
                u.redacted = true;
                if p.redact == Redact::Moves { u.bind = Bind::Redacted; }
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(L1, |s: &S| s.effects <= 1 && s.post <= 1),
            invariant(L4, |s: &S| !s.redacted || !matches!(s.bind, Bind::Bound(_))),
        ]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![
            action_property(L2, |o: &S, a: &A, n: &S| match a {
                A::PostStep => !(matches!(o.client, Client::Answered(Reply::Replay)) && n.post != o.post),
                A::Send(_) => !matches!(n.client, Client::InFlight(_, Reply::Replay)) || n.effects == o.effects,
                _ => true,
            }),
            action_property(L3, |o: &S, a: &A, n: &S| match (a, o.bind) {
                (A::Send(x), Bind::Bound(y)) if *x != y => n.effects == o.effects,
                _ => true,
            }),
        ]
    }
}

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], $ab:expr, $rv:expr, $law:expr, [$($f:expr),*]) => {
        pub struct $t;
        impl RetryObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn as_built(&self) -> Policy { $ab }
            fn reviewed(&self) -> Policy { $rv }
            fn departs(&self) -> (&'static str, &'static [&'static str]) { ($law, &[$($f),*]) }
        }
    };
}

const LEDGER_RV: Policy = Policy { dedup: Dedup::Atomic, client: ClientRetry::AppRetry, post: Post::SkipOnReplay, redact: Redact::Moves, rerun: false };

// Ledger retry key: the client re-applies post-commit properties after a replayed answer
// (iris_vector_graph/ledger/client.py:418-487, F-1101, F-1306).
object!(LedgerKey, "ledger-key", ["11/retry-key"],
        Policy { post: Post::Always, ..LEDGER_RV }, LEDGER_RV, L2, ["F-1101", "F-1306"]);
// A revision whose changeset recorded nothing keeps its key bound through the tenant's redaction (F-CS01).
object!(ZeroRecordRevision, "zero-record-revision", ["13/redaction-target"],
        Policy { redact: Redact::Keeps, ..LEDGER_RV }, LEDGER_RV, L4, ["F-CS01"]);
// The HTTP client resends a POST after a timeout or a 5xx, with no identity the server dedups on (sdk.py:209-228).
object!(ClientResend, "client-resend", ["17/client-request"],
        Policy { dedup: Dedup::NoDedup, client: ClientRetry::ResendOnLost, post: Post::NoPost, redact: Redact::Moves, rerun: false },
        Policy { dedup: Dedup::NoDedup, client: ClientRetry::Never, post: Post::NoPost, redact: Redact::Moves, rerun: false },
        L1, ["F-C1703"]);
// The Cypher HTTP server runs the query again after any exception, writes included (cypher_api.py:239-268).
object!(ServerRerun, "server-rerun", ["16/cypher-http-call"],
        Policy { dedup: Dedup::NoDedup, client: ClientRetry::Never, post: Post::NoPost, redact: Redact::Moves, rerun: true },
        Policy { dedup: Dedup::NoDedup, client: ClientRetry::Never, post: Post::NoPost, redact: Redact::Moves, rerun: false },
        L1, ["F-C1604"]);
// Business-identity idempotence: setup on a current install, setting the same model again, one queue entry per node.
object!(IdempotentSetup, "idempotent-setup", ["01/setup-routine", "06/registry-row", "06/queue-entry"],
        Policy { dedup: Dedup::Atomic, client: ClientRetry::AppRetry, post: Post::NoPost, redact: Redact::Moves, rerun: false },
        Policy { dedup: Dedup::Atomic, client: ClientRetry::AppRetry, post: Post::NoPost, redact: Redact::Moves, rerun: false },
        "", []);

fn instance_checks<O: RetryObject>(o: &O) -> Vec<Outcome> {
    let (law, f) = o.departs();
    let n = o.name();
    let ab = Machine { o, p: o.as_built() };
    let rv = Machine { o, p: o.reviewed() };
    let mut out = vec![];
    if law.is_empty() {
        out.push(check(&format!("retry-{n}-as-built"), meta("M-02", "retry", n, o.objects(), "as-built", "safety", "all", f, ""), Expect::Pass, &Keep::safety(&ab)));
    } else {
        out.push(check(&format!("retry-{n}-as-built"), meta("M-02", "retry", n, o.objects(), "as-built", "safety", law, f, ""), Expect::Violation(law), &Keep::only(&ab, &[law])));
    }
    out.push(check(&format!("retry-{n}-reviewed"), meta("M-02", "retry", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)));
    out
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&LedgerKey));
    out.extend(instance_checks(&ZeroRecordRevision));
    out.extend(instance_checks(&ClientResend));
    out.extend(instance_checks(&ServerRerun));
    out.extend(instance_checks(&IdempotentSetup));
    let o = &LedgerKey;
    let ctl = |id: &str, law: &'static str, p: Policy| {
        let m = Machine { o, p };
        check(id, meta("M-02", "retry", "ledger-key", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    out.push(ctl("retry-control-C1-bind-after-effect", L1, Policy { dedup: Dedup::TwoStep, ..LEDGER_RV }));
    out.push(ctl("retry-control-C2-post-on-replay", L2, Policy { post: Post::Always, ..LEDGER_RV }));
    out.push(ctl("retry-control-C3-apply-conflict", L3, Policy { dedup: Dedup::ApplyConflict, ..LEDGER_RV }));
    out.push(ctl("retry-control-C4-redaction-keeps-binding", L4, Policy { redact: Redact::Keeps, ..LEDGER_RV }));
    let rv = Machine { o, p: LEDGER_RV };
    let sm = || meta("M-02", "retry", "ledger-key", LedgerKey.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("retry-sharp-replay", sm(), &rv, "never: a replayed answer delivered", |s: &S| s.client == Client::Answered(Reply::Replay)));
    out.push(reach("retry-sharp-conflict", sm(), &rv, "never: a conflict refusal delivered", |s: &S| s.client == Client::Answered(Reply::Conflict)));
    out.push(reach("retry-sharp-redacted-refusal", sm(), &rv, "never: a retry refused after redaction", |s: &S| s.client == Client::Answered(Reply::Refused)));
    out
}
