//! Level 2: protocol `SysP` composes the redaction ledger **RL** (level 1's outer contract, used here as a
//! participant) and the **Store** into the outer business contract **Biz**. It owns `pend`, the table of targets
//! whose erasure or redaction is under way.
//!
//! The reviewed design, as the protocol's decisions:
//! - **Erasure serializes with commits and with redaction through the head lock** (HD-1201): the eraser's row
//!   deletes take the ledger head lock (`RL::Lock`) and its statement cleanup releases it (`RL::Unlock`); every
//!   ledger transaction (commit, replay, start, scan, final) needs the lock free.
//! - **Start and Final read liveness in the same step** as their ledger part (HD-1301; FinalInLock re-checks).
//! - **A replayed retry changes nothing** (HD-1305): the store takes no step.
//!
//! Broken-implementation controls (each the pin's behaviour; each must fail `step_binds` in this file):
//! - `control_f1201_erase_unlocked` (F-1201): the eraser takes no head lock (Eraser.cls:47-261), so a commit can land
//!   between its row deletes and its statement cleanup.
//! - `control_f1306_replay_reapplies` (F-1306): a replayed retry re-applies its post-commit properties to the store
//!   (client.py:430-435).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::store::*;
use crate::protocol_rl::*;
use crate::biz::*;
use crate::compose::*;

verus! {

pub struct Own2 { pub pend: Set<Tgt> }

/// The liveness reads that share a step with the ledger part.
pub open spec fn p2_guard(a: RLS, b: StoreS, x: BizL) -> bool {
    match x {
        BizL::Start { p, fresh } => !live_in(b.rows, tgt_of(a.r, p)),
        BizL::Final { p, ok } => ok == !live_in(b.rows, tgt_of(a.r, p)),
        _ => true,
    }
}

/// USES edges: the RL operation of each step.
pub open spec fn p2_lab_rl(a: RLS, b: StoreS, x: BizL) -> Option<RLL> {
    match x {
        BizL::EraseRows { t } => if cfg!(feature = "control_f1201_erase_unlocked") { None } else { Some(RLL::Lock) },
        BizL::EraseIndex { t } => if cfg!(feature = "control_f1201_erase_unlocked") { None } else { Some(RLL::Unlock) },
        _ => Some(rl_label(x)),
    }
}

/// USES edges: the store operation of each step.
pub open spec fn p2_lab_st(a: RLS, b: StoreS, x: BizL) -> Option<StoreL> {
    match x {
        BizL::Commit { cs, key } => Some(StoreL::Apply { cs }),
        BizL::Replay { key, props } =>
            if cfg!(feature = "control_f1306_replay_reapplies") { Some(StoreL::Apply { cs: props }) } else { None },
        BizL::EraseRows { t } => Some(StoreL::EraseRows { t }),
        BizL::EraseIndex { t } => Some(StoreL::EraseIndex { t }),
        _ => None,
    }
}

pub struct SysP;

impl Protocol2 for SysP {
    type Outer = Biz;
    type A = RL;
    type B = Store;
    type Own = Own2;

    open spec fn abs(a: RLS, b: StoreS, o: Own2) -> BizS { BizS { rl: a, st: b, pend: o.pend } }
    open spec fn guard(a: RLS, b: StoreS, o: Own2, x: BizL) -> bool { p2_guard(a, b, x) }
    open spec fn lab_a(a: RLS, b: StoreS, o: Own2, x: BizL) -> Option<RLL> { p2_lab_rl(a, b, x) }
    open spec fn lab_b(a: RLS, b: StoreS, o: Own2, x: BizL) -> Option<StoreL> { p2_lab_st(a, b, x) }
    open spec fn own_next(a: RLS, b: StoreS, o: Own2, x: BizL, o2: Own2) -> bool { o2.pend == pend_after(a, o.pend, x) }

    proof fn step_binds(a: RLS, b: StoreS, o: Own2, x: BizL, a2: RLS, b2: StoreS, o2: Own2) {
        lemma_p2_binds(a, b, o, x, a2, b2, o2);
    }

    proof fn step_enabled(a: RLS, b: StoreS, o: Own2, x: BizL, t: BizS) {
        lemma_p2_enabled(a, b, o, x, t);
        assert(Self::abs(t.rl, t.st, Own2 { pend: t.pend }) == t);
    }
}

impl ProtocolInit for SysP {
    open spec fn own_init(o: Own2) -> bool { o.pend == Set::<Tgt>::empty() }
    proof fn init_binds(a: RLS, b: StoreS, o: Own2) {}
}

/// REFINES: every synchronized step of the redaction ledger and the store is one Biz step.
pub proof fn lemma_p2_binds(a: RLS, b: StoreS, o: Own2, x: BizL, a2: RLS, b2: StoreS, o2: Own2)
    requires
        p2_guard(a, b, x),
        step_or_stutter::<RL>(a, p2_lab_rl(a, b, x), a2),
        step_or_stutter::<Store>(b, p2_lab_st(a, b, x), b2),
        o2.pend == pend_after(a, o.pend, x),
    ensures biz_next(BizS { rl: a, st: b, pend: o.pend }, x, BizS { rl: a2, st: b2, pend: o2.pend }),
{
    match x {
        BizL::EraseRows { t } => { assert(rl_next(a, RLL::Lock, a2)); assert(b2 == store_erase_rows(b, t)); }
        BizL::EraseIndex { t } => { assert(rl_next(a, RLL::Unlock, a2)); assert(b2 == store_erase_index(b, t)); }
        BizL::Replay { key, props } => { assert(b2 == b); }
        _ => {}
    }
}

/// Non-vacuity: every Biz step from a represented state is realized by the redaction ledger and the store.
pub proof fn lemma_p2_enabled(a: RLS, b: StoreS, o: Own2, x: BizL, t: BizS)
    requires biz_next(BizS { rl: a, st: b, pend: o.pend }, x, t),
    ensures
        p2_guard(a, b, x),
        step_or_stutter::<RL>(a, p2_lab_rl(a, b, x), t.rl),
        step_or_stutter::<Store>(b, p2_lab_st(a, b, x), t.st),
        t.pend == pend_after(a, o.pend, x),
{
    match x {
        BizL::Replay { key, props } => { assert(t.st == b); }
        _ => {}
    }
}

} // verus!
