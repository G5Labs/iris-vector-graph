//! Contract `Mid`: the outer contract of level 2 (RL x Store, `protocol_sys`) and participant A of level 3
//! (`protocol_top`). Its state is the redaction ledger, the store and `pend` (the domains whose erasure or redaction
//! is under way); its steps are the reviewed design's level-2 transactions. Non-ledger writes (`Write`, `Undo`) are
//! steps of Mid at any time (the store accepts them as built); level 3 decides when, together with the writers.
//!
//! The reviewed design at this level (HD-1201, HD-1301, HD-1303/HD-1304 working answers):
//! - **Erasure serializes through the head lock for its whole transaction** (HD-1201): `EraseRows` takes the lock
//!   (`RL::Lock`), the cleanup keeps it, and the outermost commit or the rollback releases it (`RL::Unlock`; an IRIS
//!   unlock inside a transaction takes effect at its end, E-LOCK-DEFER). So no ledger transaction, and in particular
//!   no liveness check of a Start or Final, runs while an erasure is open: **liveness is checked under the eraser's
//!   lock** (D-9 guard G-L).
//! - **Start** (one locked step, HD-1301) refuses a target whose three predicates are not aligned
//!   (`vocab::aligned`, D-9 guard G-P) and checks liveness with the target's liveness predicate.
//! - **Final** re-checks liveness and, when it succeeds, drops the target's statements with its statement-cleanup
//!   predicate (DropStatements).
//! - `pend`: an erasure's domain joins at its commit; a fresh run's record match joins at Start; a successful Final
//!   removes every pending domain its record match covers.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
use crate::protocol_rl::*;

verus! {

pub struct MidS { pub rl: RLS, pub st: StoreS, pub pend: Set<Dom> }

pub enum MidL {
    Commit { cs: Seq<Content>, key: Option<IKey> },
    Replay { key: IKey },
    EraseRows { e: Dom },
    EraseIndex,
    EraseCommit,
    EraseAbort,
    SetEnabled { on: bool },
    Open { p: nat, t: Tgt },
    Start { p: nat, fresh: bool },
    Scan { p: nat },
    ToFinal { p: nat },
    Final { p: nat, ok: bool },
    Stop { p: nat },
    Write { k: Key, v: Option<int> },
    Undo { k: Key, before: Option<int>, was: bool },
}

/// The reviewed level-2 decision on the participants' read views.
pub open spec fn mid_ok(a: RLS, b: StoreS, l: MidL) -> bool {
    match l {
        MidL::Start { p, fresh } => aligned(tgt_of(a.r, p)) && !live_in(b.rows, tgt_of(a.r, p).lv),
        MidL::Final { p, ok } => ok == !live_in(b.rows, tgt_of(a.r, p).lv),
        _ => true,
    }
}

/// The RL operation of each step (reviewed).
pub open spec fn mid_rl(l: MidL) -> Option<RLL> {
    match l {
        MidL::Commit { cs, key } => Some(RLL::Commit { cs, key }),
        MidL::Replay { key } => Some(RLL::Replay { key }),
        MidL::EraseRows { e } => Some(RLL::Lock),
        MidL::EraseIndex => None,
        MidL::EraseCommit => Some(RLL::Unlock),
        MidL::EraseAbort => Some(RLL::Unlock),
        MidL::SetEnabled { on } => Some(RLL::SetEnabled { on }),
        MidL::Open { p, t } => Some(RLL::Open { p, t }),
        MidL::Start { p, fresh } => Some(RLL::Start { p, fresh }),
        MidL::Scan { p } => Some(RLL::Scan { p }),
        MidL::ToFinal { p } => Some(RLL::ToFinal { p }),
        MidL::Final { p, ok } => Some(RLL::Final { p, ok }),
        MidL::Stop { p } => Some(RLL::Stop { p }),
        MidL::Write { k, v } => None,
        MidL::Undo { k, before, was } => None,
    }
}

/// The store operation of each step.
pub open spec fn mid_st(a: RLS, l: MidL) -> Option<StoreL> {
    match l {
        MidL::Commit { cs, key } => Some(StoreL::Apply { cs }),
        MidL::EraseRows { e } => Some(StoreL::EraseRows { e }),
        MidL::EraseIndex => Some(StoreL::EraseIndex),
        MidL::EraseCommit => Some(StoreL::EraseCommit),
        MidL::EraseAbort => Some(StoreL::EraseAbort),
        MidL::Final { p, ok } => if ok { Some(StoreL::Drop { sc: tgt_of(a.r, p).sc }) } else { None },
        MidL::Write { k, v } => Some(StoreL::Write { k, v }),
        MidL::Undo { k, before, was } => Some(StoreL::Undo { k, before, was }),
        _ => None,
    }
}

pub open spec fn pend_after(a: RLS, b: StoreS, pend: Set<Dom>, l: MidL) -> Set<Dom> {
    match l {
        MidL::EraseCommit => pend.insert(b.erasing->0.e),
        MidL::Start { p, fresh } => if fresh { pend.insert(tgt_of(a.r, p).rm) } else { pend },
        MidL::Final { p, ok } => if ok { pend.filter(|d: Dom| !covers(tgt_of(a.r, p).rm, d)) } else { pend },
        _ => pend,
    }
}

pub open spec fn mid_next(x: MidS, l: MidL, y: MidS) -> bool {
    &&& mid_ok(x.rl, x.st, l)
    &&& step_or_stutter::<RL>(x.rl, mid_rl(l), y.rl)
    &&& step_or_stutter::<Store>(x.st, mid_st(x.rl, l), y.st)
    &&& y.pend == pend_after(x.rl, x.st, x.pend, l)
}

pub struct Mid;

impl Contract for Mid {
    type S = MidS;
    type L = MidL;

    open spec fn init(x: MidS) -> bool { RL::init(x.rl) && Store::init(x.st) && x.pend == Set::<Dom>::empty() }

    open spec fn next(x: MidS, l: MidL, y: MidS) -> bool { mid_next(x, l, y) }
}

/// Mid's own invariant is its participants'. The business invariants need the writers' transactions and live at
/// level 3 (`biz`).
pub open spec fn mid_inv(x: MidS) -> bool { rl_inv(x.rl) && store_inv(x.st) }

pub proof fn lemma_mid_safe(x: MidS, l: MidL, y: MidS)
    requires mid_inv(x), mid_next(x, l, y),
    ensures mid_inv(y),
{
    match mid_rl(l) { Some(m) => { lemma_rl_safe(x.rl, m, y.rl); } None => {} }
    match mid_st(x.rl, l) { Some(m) => { lemma_store_safe(x.st, m); } None => {} }
}

impl SafeContract for Mid {
    open spec fn inv(x: MidS) -> bool { mid_inv(x) }
    proof fn init_safe(x: MidS) {}
    proof fn step_safe(x: MidS, l: MidL, y: MidS) { lemma_mid_safe(x, l, y); }
}

} // verus!
