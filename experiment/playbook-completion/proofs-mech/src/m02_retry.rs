//! M-02 Retry and idempotency binding (AX-06, AX-12), generic over `RetryPolicy` / `RetryObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/retry.rs` (read at commit b0433157) restated without
//! its bound on sends: one request identity (a retry key or a business identity); the client sends a payload (the
//! first request carries payload 1); the server answers by the object's dedup policy (first answer, replay,
//! conflict, or a refusal after redaction); the answer is delivered or lost (an ambiguous outcome); the client may
//! retry by its policy and, after an answer, runs a post-commit step by its policy; the server may re-run a request
//! after an error raised after its commit; a redaction of the bound revision moves the binding to `Redacted`
//! (Ledger.cls:454-473 idemRedacted) or keeps it. Canonical: Ledger.Commit writes the binding in the commit's
//! transaction (Ledger.cls:454-473).
//!
//! Laws (MECHANISMS.md M-02): M02-L1 (invariant) at most one effect and one post-commit effect per identity;
//! M02-L2 (action) a replay changes nothing; M02-L3 (action) another payload under a bound key changes nothing;
//! M02-L4 (invariant) after redaction the binding is gone.
//!
//! Obligations (design rules on the instance's policy): L1 the binding is written atomically with the effect and
//! post-commit steps run on the first answer only, or the request is never repeated by anyone (no client retry, no
//! server re-run); L2 no post-commit step runs on a replayed answer; L3 a conflicting payload is never applied;
//! L4 redaction of the bound revision moves its binding.
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub enum Dedup { Atomic, TwoStep, NoDedup, ApplyConflict }
pub enum ClientRetry { AppRetry, ResendOnLost, Never }
pub enum Post { Always, SkipOnReplay, NoPost }
pub enum Redact { Moves, Keeps }

pub struct RetryCfg { pub dedup: Dedup, pub client: ClientRetry, pub post: Post, pub redact: Redact, pub rerun: bool }

pub enum Bind { Free, Bound(nat), Redacted }
pub enum Reply { First, Replay, Conflict, Refused }
pub enum Client { Idle, InFlight(nat, Reply), Answered(Reply), Lost(nat), Done }

pub struct RS {
    pub bind: Bind,
    pub effects: nat,
    pub post: nat,
    pub client: Client,
    pub sends: nat,
    pub mid: bool,
    pub reran: bool,
    pub redacted: bool,
}

pub enum RA { Send(nat), Deliver, Lose, PostStep, Skip, Stop, FinishBind, Rerun, RedactRev }

pub trait RetryPolicy: Sized {
    spec fn cfg() -> RetryCfg;
}

pub open spec fn retry_s0() -> RS {
    RS { bind: Bind::Free, effects: 0, post: 0, client: Client::Idle, sends: 0, mid: false, reran: false, redacted: false }
}

/// Whether the client may send payload `x` now (explorer `may`).
pub open spec fn may_send(c: RetryCfg, s: RS, x: nat) -> bool {
    match s.client {
        Client::Idle => s.sends == 0 || c.client is AppRetry,
        Client::Done => c.client is AppRetry,
        Client::Lost(y) => (c.client is ResendOnLost || c.client is AppRetry) && y == x,
        _ => false,
    }
}

/// The server's answer to `x` and its effect (explorer `Send`).
pub open spec fn serve(c: RetryCfg, s: RS, x: nat) -> RS {
    let u = RS { sends: s.sends + 1, ..s };
    match (c.dedup, s.bind) {
        (Dedup::NoDedup, _) => RS { effects: s.effects + 1, client: Client::InFlight(x, Reply::First), ..u },
        (_, Bind::Redacted) => RS { client: Client::InFlight(x, Reply::Refused), ..u },
        (Dedup::Atomic, Bind::Free) | (Dedup::ApplyConflict, Bind::Free) =>
            RS { effects: s.effects + 1, bind: Bind::Bound(x), client: Client::InFlight(x, Reply::First), ..u },
        (Dedup::TwoStep, Bind::Free) => RS { effects: s.effects + 1, mid: true, client: Client::InFlight(x, Reply::First), ..u },
        (Dedup::ApplyConflict, Bind::Bound(y)) => {
            if y != x { RS { effects: s.effects + 1, bind: Bind::Bound(x), client: Client::InFlight(x, Reply::First), ..u } }
            else { RS { client: Client::InFlight(x, Reply::Replay), ..u } }
        },
        (_, Bind::Bound(y)) => {
            if y == x { RS { client: Client::InFlight(x, Reply::Replay), ..u } }
            else { RS { client: Client::InFlight(x, Reply::Conflict), ..u } }
        },
    }
}

pub open spec fn post_runs(c: RetryCfg, r: Reply) -> bool {
    match c.post { Post::Always => true, Post::SkipOnReplay => r is First, Post::NoPost => false }
}

pub open spec fn retry_step<O: RetryPolicy>(s: RS, a: RA) -> Option<RS> {
    let c = O::cfg();
    match a {
        RA::Send(x) => {
            if !may_send(c, s, x) || s.mid || (s.sends == 0 && x != 1) { None } else { Some(serve(c, s, x)) }
        },
        RA::FinishBind => {
            if !s.mid { None } else {
                match s.client { Client::InFlight(x, _) => Some(RS { mid: false, bind: Bind::Bound(x), ..s }), _ => None }
            }
        },
        RA::Stop => {
            if !s.mid { None } else {
                match s.client { Client::InFlight(x, _) => Some(RS { mid: false, client: Client::Lost(x), ..s }), _ => None }
            }
        },
        RA::Deliver => {
            if s.mid { None } else {
                match s.client { Client::InFlight(_, r) => Some(RS { client: Client::Answered(r), ..s }), _ => None }
            }
        },
        RA::Lose => {
            if s.mid { None } else {
                match s.client { Client::InFlight(x, _) => Some(RS { client: Client::Lost(x), ..s }), _ => None }
            }
        },
        RA::Rerun => {
            // the server runs the request again after an error raised after its commit (cypher_api.py:250-268)
            if !c.rerun || s.reran || s.mid { None } else {
                match s.client {
                    Client::InFlight(x, Reply::First) =>
                        Some(RS { reran: true, effects: if c.dedup is NoDedup { s.effects + 1 } else { s.effects }, ..s }),
                    _ => None,
                }
            }
        },
        RA::PostStep => {
            match s.client {
                Client::Answered(r) => {
                    if !(r is First || r is Replay) { None }
                    else { Some(RS { post: if post_runs(c, r) { s.post + 1 } else { s.post }, client: Client::Done, ..s }) }
                },
                _ => None,
            }
        },
        RA::Skip => {
            match s.client {
                Client::Answered(r) => {
                    if (r is First || r is Replay) && !(c.post is NoPost) { None } else { Some(RS { client: Client::Done, ..s }) }
                },
                _ => None,
            }
        },
        RA::RedactRev => {
            if s.redacted || !(s.bind is Bound) || s.mid { None }
            else { Some(RS { redacted: true, bind: if c.redact is Moves { Bind::Redacted } else { s.bind }, ..s }) }
        },
    }
}

pub struct RetryM<O> { pub o: O }

impl<O: RetryPolicy> Machine for RetryM<O> {
    type S = RS;
    type A = RA;
    open spec fn init(s: RS) -> bool { s == retry_s0() }
    open spec fn step(s: RS, a: RA) -> Option<RS> { retry_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

pub open spec fn in_flight_with(c: Client, r: Reply) -> bool {
    match c { Client::InFlight(_, q) => q == r, _ => false }
}

/// M02-L1 (invariant): at most one effect per identity, post-commit effects included.
pub open spec fn law_l1(s: RS) -> bool { s.effects <= 1 && s.post <= 1 }

/// M02-L2 (action): a replay changes nothing.
pub open spec fn law_l2(s: RS, a: RA, t: RS) -> bool {
    match a {
        RA::PostStep => !(s.client == Client::Answered(Reply::Replay) && t.post != s.post),
        RA::Send(_) => !in_flight_with(t.client, Reply::Replay) || t.effects == s.effects,
        _ => true,
    }
}

/// M02-L3 (action): another payload under a bound key changes nothing.
pub open spec fn law_l3(s: RS, a: RA, t: RS) -> bool {
    match (a, s.bind) {
        (RA::Send(x), Bind::Bound(y)) => x == y || t.effects == s.effects,
        _ => true,
    }
}

/// M02-L4 (invariant): after the bound revision is redacted, the binding is gone.
pub open spec fn law_l4(s: RS) -> bool { !s.redacted || !(s.bind is Bound) }

// ------------------------------------------------------------------------------------------------ obligations

pub open spec fn obl_l1<O: RetryPolicy>() -> bool {
    let c = O::cfg();
    (c.dedup is Atomic && !(c.post is Always)) || (c.dedup is NoDedup && c.client is Never && !c.rerun)
}
pub open spec fn obl_l2<O: RetryPolicy>() -> bool { !(O::cfg().post is Always) }
pub open spec fn obl_l3<O: RetryPolicy>() -> bool { !(O::cfg().dedup is ApplyConflict) }
pub open spec fn obl_l4<O: RetryPolicy>() -> bool { O::cfg().redact is Moves }

pub trait RetryObject: RetryPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
    proof fn discharge_l4() ensures obl_l4::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemmas

/// Structural invariant, every policy: a pending two-step binding is a first answer on a free key; a key without
/// dedup is never bound; a redacted revision's key is not free.
pub open spec fn inv_struct<O: RetryPolicy>(s: RS) -> bool {
    &&& s.mid ==> (O::cfg().dedup is TwoStep && s.bind is Free && !s.redacted && in_flight_with(s.client, Reply::First))
    &&& O::cfg().dedup is NoDedup ==> s.bind is Free
    &&& s.redacted ==> !(s.bind is Free)
}

pub open spec fn carries_first(c: Client) -> bool {
    match c { Client::InFlight(_, r) => r is First, Client::Answered(r) => r is First, _ => false }
}

/// The inductive form of M02-L1 under its obligation (one case per allowed policy shape).
pub open spec fn ind_l1<O: RetryPolicy>(s: RS) -> bool {
    let c = O::cfg();
    &&& inv_struct::<O>(s)
    &&& law_l1(s)
    &&& (c.dedup is Atomic ==> {
            &&& (s.bind is Free ==> s.effects == 0 && s.post == 0 && s.client is Idle)
            &&& (!(s.bind is Free) ==> s.effects == 1)
            &&& (carries_first(s.client) ==> s.post == 0)
        })
    &&& (c.dedup is NoDedup && c.client is Never && !c.rerun ==> {
            &&& s.effects == s.sends && s.sends <= 1
            &&& (s.sends == 0 <==> s.client is Idle)
            &&& (carries_first(s.client) ==> s.post == 0)
            &&& (s.post == 1 ==> s.client is Done)
        })
}

pub proof fn lemma_struct_step<O: RetryPolicy>(s: RS, a: RA)
    requires inv_struct::<O>(s), retry_step::<O>(s, a) is Some,
    ensures inv_struct::<O>(retry_step::<O>(s, a)->0),
{
}

pub proof fn lemma_l1_step<O: RetryPolicy>(s: RS, a: RA)
    requires obl_l1::<O>(), ind_l1::<O>(s), retry_step::<O>(s, a) is Some,
    ensures ind_l1::<O>(retry_step::<O>(s, a)->0),
{
    lemma_struct_step::<O>(s, a);
}

pub proof fn lemma_l2_step<O: RetryPolicy>(s: RS, a: RA)
    requires obl_l2::<O>(), retry_step::<O>(s, a) is Some,
    ensures law_l2(s, a, retry_step::<O>(s, a)->0),
{
}

pub proof fn lemma_l3_step<O: RetryPolicy>(s: RS, a: RA)
    requires obl_l3::<O>(), inv_struct::<O>(s), retry_step::<O>(s, a) is Some,
    ensures law_l3(s, a, retry_step::<O>(s, a)->0),
{
}

pub open spec fn ind_l4<O: RetryPolicy>(s: RS) -> bool {
    inv_struct::<O>(s) && (s.redacted ==> s.bind is Redacted)
}

pub proof fn lemma_l4_step<O: RetryPolicy>(s: RS, a: RA)
    requires obl_l4::<O>(), ind_l4::<O>(s), retry_step::<O>(s, a) is Some,
    ensures ind_l4::<O>(retry_step::<O>(s, a)->0),
{
    lemma_struct_step::<O>(s, a);
}

// ------------------------------------------------------------------------------------------------ theorems

pub proof fn theorem_struct<O: RetryPolicy>(s0: RS, ls: Seq<RA>, t: RS)
    requires reached::<RetryM<O>>(s0, ls, t),
    ensures inv_struct::<O>(t),
{
    let inv = |s: RS| inv_struct::<O>(s);
    assert forall|x: RS, a: RA| inv(x) && (#[trigger] RetryM::<O>::step(x, a)) is Some implies inv(RetryM::<O>::step(x, a)->0) by {
        lemma_struct_step::<O>(x, a);
    }
    lemma_reached_inv::<RetryM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l1<O: RetryPolicy>(s0: RS, ls: Seq<RA>, t: RS)
    requires obl_l1::<O>(), reached::<RetryM<O>>(s0, ls, t),
    ensures law_l1(t),
{
    let inv = |s: RS| ind_l1::<O>(s);
    assert forall|x: RS, a: RA| inv(x) && (#[trigger] RetryM::<O>::step(x, a)) is Some implies inv(RetryM::<O>::step(x, a)->0) by {
        lemma_l1_step::<O>(x, a);
    }
    lemma_reached_inv::<RetryM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l2<O: RetryPolicy>(s: RS, a: RA)
    requires obl_l2::<O>(), retry_step::<O>(s, a) is Some,
    ensures law_l2(s, a, retry_step::<O>(s, a)->0),
{
    lemma_l2_step::<O>(s, a);
}

pub proof fn theorem_l3<O: RetryPolicy>(s0: RS, ls: Seq<RA>, t: RS, a: RA)
    requires obl_l3::<O>(), reached::<RetryM<O>>(s0, ls, t), retry_step::<O>(t, a) is Some,
    ensures law_l3(t, a, retry_step::<O>(t, a)->0),
{
    theorem_struct::<O>(s0, ls, t);
    lemma_l3_step::<O>(t, a);
}

pub proof fn theorem_l4<O: RetryPolicy>(s0: RS, ls: Seq<RA>, t: RS)
    requires obl_l4::<O>(), reached::<RetryM<O>>(s0, ls, t),
    ensures law_l4(t),
{
    let inv = |s: RS| ind_l4::<O>(s);
    assert forall|x: RS, a: RA| inv(x) && (#[trigger] RetryM::<O>::step(x, a)) is Some implies inv(RetryM::<O>::step(x, a)->0) by {
        lemma_l4_step::<O>(x, a);
    }
    lemma_reached_inv::<RetryM<O>>(inv, s0, ls, t);
}

/// The mechanism's theorem, once for every object.
pub proof fn theorem_retry<O: RetryObject>(s0: RS, ls: Seq<RA>, t: RS, a: RA)
    requires reached::<RetryM<O>>(s0, ls, t),
    ensures
        law_l1(t),
        law_l4(t),
        retry_step::<O>(t, a) is Some ==> law_l2(t, a, retry_step::<O>(t, a)->0) && law_l3(t, a, retry_step::<O>(t, a)->0),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    O::discharge_l4();
    theorem_l1::<O>(s0, ls, t);
    theorem_l4::<O>(s0, ls, t);
    if retry_step::<O>(t, a) is Some {
        theorem_l2::<O>(t, a);
        theorem_l3::<O>(s0, ls, t, a);
    }
}

} // verus!
