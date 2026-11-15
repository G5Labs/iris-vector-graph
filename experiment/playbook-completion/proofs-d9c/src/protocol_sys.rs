//! Level 2: protocol `SysP` composes the redaction ledger **RL** (level 1's outer contract) and the **Store** into
//! **Mid** (`mid`). It owns `pend`.
//!
//! The reviewed decisions (`mid::mid_ok`, `mid::mid_rl`, `mid::mid_st`): the eraser holds the head lock from its row
//! deletes to its commit or rollback; Start checks the target's predicates are aligned and that nothing its liveness
//! predicate selects is live, in the same locked step as its ledger part; Final re-checks liveness and drops
//! statements with the statement-cleanup predicate.
//!
//! Controls (each must fail `step_binds` in this file, `lemma_p2_binds`; each has a proved counterexample):
//! - `control_liveness_dirty` (F-C1201, guard G-L dropped): the liveness check runs when the redaction is called,
//!   without the head lock, on the rows other processes see (READ UNCOMMITTED, E-VIS), as the pin's LiveRows does
//!   (LedgerRedact.cls:206-210); the locked Start does not check again. An open erasure's uncommitted deletes pass the
//!   check and its rollback restores the target (`cx_liveness_dirty`).
//! - `control_unaligned_rm` (F-1304, F-C1308; side condition `rm ⊆ lv` dropped): Start accepts a target whose record
//!   match selects rows its liveness check does not look at (`cx_unaligned_rm`).
//! - `control_unaligned_sc` (side condition `sc ⊆ rm` dropped): Start accepts a target whose statement cleanup
//!   selects statements outside its record match (core model control `m1-control-dropstatements-all-graphs`;
//!   `cx_unaligned_sc`).
//! - `control_f1201_erase_unlocked` (F-1201, regression of an original guard): the eraser takes no head lock
//!   (`cx_f1201`).
//! - `control_sc_narrow` (D-9b, side condition `rm ⊆ sc` on edges dropped): Start accepts a target whose statement
//!   cleanup misses edges its record match owns; the closed statement history of a redacted edge survives a complete
//!   redaction (`cx_sc_narrow`). Not a pin finding (the pin's predicates coincide on relationships): it shows the
//!   statement-history theorem needs the guard.
//! (D-9c: the F-1306 control moved to level 3, `protocol_top`, where the pin's direct-SQL write is a Writer step.)
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::store::*;
use crate::protocol_rl::*;
use crate::mid::*;
use crate::compose::*;

verus! {

pub struct Own2 { pub pend: Set<Dom> }

/// The protocol's decision (reviewed, or a control's replacement of one guard).
pub open spec fn p2_guard(a: RLS, b: StoreS, l: MidL) -> bool {
    match l {
        MidL::Open { p, t } =>
            if cfg!(feature = "control_liveness_dirty") {
                // LedgerRedact.cls:206-210: LiveRows at the call, no lock, READ UNCOMMITTED.
                !live_in(b.rows, t.lv)
            } else { true },
        MidL::Start { p, fresh } => {
            let t = tgt_of(a.r, p);
            if cfg!(feature = "control_liveness_dirty") {
                aligned(t)
            } else if cfg!(feature = "control_unaligned_rm") {
                sc_in_rm(t) && rm_in_sc(t) && !live_in(b.rows, t.lv)
            } else if cfg!(feature = "control_unaligned_sc") {
                rm_in_lv(t) && rm_in_sc(t) && !live_in(b.rows, t.lv)
            } else if cfg!(feature = "control_sc_narrow") {
                rm_in_lv(t) && sc_in_rm(t) && !live_in(b.rows, t.lv)
            } else {
                mid_ok(a, b, l)
            }
        }
        _ => mid_ok(a, b, l),
    }
}

/// USES edges: the RL operation of each step.
pub open spec fn p2_lab_rl(a: RLS, b: StoreS, l: MidL) -> Option<RLL> {
    match l {
        MidL::EraseRows { e } => if cfg!(feature = "control_f1201_erase_unlocked") { None } else { mid_rl(l) },
        MidL::EraseCommit => if cfg!(feature = "control_f1201_erase_unlocked") { None } else { mid_rl(l) },
        MidL::EraseAbort => if cfg!(feature = "control_f1201_erase_unlocked") { None } else { mid_rl(l) },
        _ => mid_rl(l),
    }
}

/// USES edges: the store operation of each step.
pub open spec fn p2_lab_st(a: RLS, b: StoreS, l: MidL) -> Option<StoreL> { mid_st(a, l) }

pub struct SysP;

impl Protocol2 for SysP {
    type Outer = Mid;
    type A = RL;
    type B = Store;
    type Own = Own2;

    open spec fn abs(a: RLS, b: StoreS, o: Own2) -> MidS { MidS { rl: a, st: b, pend: o.pend } }
    open spec fn guard(a: RLS, b: StoreS, o: Own2, l: MidL) -> bool { p2_guard(a, b, l) }
    open spec fn lab_a(a: RLS, b: StoreS, o: Own2, l: MidL) -> Option<RLL> { p2_lab_rl(a, b, l) }
    open spec fn lab_b(a: RLS, b: StoreS, o: Own2, l: MidL) -> Option<StoreL> { p2_lab_st(a, b, l) }
    open spec fn own_next(a: RLS, b: StoreS, o: Own2, l: MidL, o2: Own2) -> bool { o2.pend == pend_after(a, b, o.pend, l) }

    proof fn step_binds(a: RLS, b: StoreS, o: Own2, l: MidL, a2: RLS, b2: StoreS, o2: Own2) {
        lemma_p2_binds(a, b, o, l, a2, b2, o2);
    }

    proof fn step_enabled(a: RLS, b: StoreS, o: Own2, l: MidL, t: MidS) {
        lemma_p2_enabled(a, b, o, l, t);
        assert(Self::abs(t.rl, t.st, Own2 { pend: t.pend }) == t);
    }
}

impl ProtocolInit for SysP {
    open spec fn own_init(o: Own2) -> bool { o.pend == Set::<Dom>::empty() }
    proof fn init_binds(a: RLS, b: StoreS, o: Own2) {}
}

/// REFINES: every synchronized step of the redaction ledger and the store is one Mid step.
pub proof fn lemma_p2_binds(a: RLS, b: StoreS, o: Own2, l: MidL, a2: RLS, b2: StoreS, o2: Own2)
    requires
        p2_guard(a, b, l),
        step_or_stutter::<RL>(a, p2_lab_rl(a, b, l), a2),
        step_or_stutter::<Store>(b, p2_lab_st(a, b, l), b2),
        o2.pend == pend_after(a, b, o.pend, l),
    ensures mid_next(MidS { rl: a, st: b, pend: o.pend }, l, MidS { rl: a2, st: b2, pend: o2.pend }),
{
}

/// Non-vacuity: every Mid step from a represented state is realized by the redaction ledger and the store.
pub proof fn lemma_p2_enabled(a: RLS, b: StoreS, o: Own2, l: MidL, t: MidS)
    requires mid_next(MidS { rl: a, st: b, pend: o.pend }, l, t),
    ensures
        p2_guard(a, b, l),
        step_or_stutter::<RL>(a, p2_lab_rl(a, b, l), t.rl),
        step_or_stutter::<Store>(b, p2_lab_st(a, b, l), t.st),
        t.pend == pend_after(a, b, o.pend, l),
{
}

} // verus!
