//! Level 3: protocol `TopP` composes **Mid** (level 2's outer contract: ledger, redactor, store) and the **Writer**
//! (the ledger-bypassing writers) into **Biz**.
//!
//! The reviewed decisions (`biz::top_ok`): Start waits for every open bypass transaction (G-B); the eraser waits for
//! open bypass transactions on its target (G-BE); a ledger commit waits for rows an open bypass transaction wrote and a
//! bypass write waits for rows the open erasure deleted (row locks, as built). A bypass write records the row and
//! provenance it found (its undo record), and its rollback gives them back to the store.
//!
//! Controls (each must fail `step_binds` in this file, `lemma_p3_binds`; each has a proved counterexample):
//! - `control_bypass_start` (F-C1301): Start does not wait for open bypass transactions, as at the pin (no writer
//!   takes a lock the redaction takes); a bypass delete that rolls back after the check restores content whose history
//!   was tombstoned (`cx_bypass_start`; core model `m2-reviewed-bypass-nonserializing`).
//! - `control_bypass_erase`: the eraser does not wait for open bypass transactions on its target; a bypass delete
//!   hides a row from the erasure's DELETE, the erasure kills its statement, and the bypass rollback brings the row
//!   back without it (`cx_bypass_erase`).
//! - `control_f1350_bypass_ignores_marker` (D-9c, review R4-01; F-C1350, live): a bypass writer writes a marked
//!   target's rows, as at the pin (no non-ledger writer reads `^IVG.Ledger("redacting")`); the batches then tombstone
//!   the history of content that is live again (`cx_f1350`).
//! - `control_f1306_replay_direct_sql` (D-9c, review R4-03; F-1306, live): a replayed retry is answered from the
//!   stored revision and the client then writes its post-commit properties **by direct SQL, without a ledger record
//!   and without reading the marker** (client.py:445-481 after Ledger.cls:457-462): at this level a Writer step in
//!   place of the reviewed replay's no-op (`cx_f1306`).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::writer::*;
use crate::mid::*;
use crate::biz::*;
use crate::compose::*;

verus! {

pub open spec fn p3_guard(m: MidS, w: WrS, l: BizL) -> bool {
    match l {
        BizL::Start { p, fresh } => if cfg!(feature = "control_bypass_start") { true } else { top_ok(m, w, l) },
        BizL::EraseRows { e } => if cfg!(feature = "control_bypass_erase") { true } else { top_ok(m, w, l) },
        // As built: a bypass writer takes no notice of the marker (F-C1350); only the row locks remain.
        BizL::BBegin { k, v } => if cfg!(feature = "control_f1350_bypass_ignores_marker") { !saved_in(m.st, k) } else { top_ok(m, w, l) },
        // As built: the replay is answered (Ledger.cls:457-462: enabled, unlocked, key bound) and the client writes its
        // first post-commit property row by direct SQL; the row locks remain, the marker is not read.
        BizL::Replay { key, props } =>
            if replay_writes_directly() {
                props.len() > 0 && m.rl.l.enabled && !m.rl.l.locked && m.rl.l.idem.contains_key(key) && !saved_in(m.st, props[0].k)
            } else { top_ok(m, w, l) },
        _ => top_ok(m, w, l),
    }
}

pub open spec fn replay_writes_directly() -> bool { cfg!(feature = "control_f1306_replay_direct_sql") }

/// The value a post-commit property write gives its row.
pub open spec fn pcp_val(c: Content) -> Option<int> { match c.eff { Eff::Put(v) => Some(v), _ => None } }

/// The Mid operation of each step (reviewed: `top_lab_m`; the F-1306 control replaces the replay by its direct write).
pub open spec fn p3_lab_m(m: MidS, w: WrS, l: BizL) -> Option<MidL> {
    match l {
        BizL::Replay { key, props } =>
            if replay_writes_directly() { Some(MidL::Write { k: props[0].k, v: pcp_val(props[0]) }) } else { top_lab_m(m, w, l) },
        _ => top_lab_m(m, w, l),
    }
}

/// The writer operation of each step (reviewed: `top_lab_w`).
pub open spec fn p3_lab_w(m: MidS, w: WrS, l: BizL) -> Option<WrL> {
    match l {
        BizL::Replay { key, props } =>
            if replay_writes_directly() {
                Some(WrL::Begin { k: props[0].k, before: oget(m.st.rows, props[0].k), was: m.st.unrec.contains(props[0].k) })
            } else { top_lab_w(m, w, l) },
        _ => top_lab_w(m, w, l),
    }
}

pub open spec fn top_abs(a: MidS, b: WrS) -> BizS { BizS { rl: a.rl, st: a.st, pend: a.pend, wr: b } }

pub struct TopP;

impl Protocol2 for TopP {
    type Outer = Biz;
    type A = Mid;
    type B = Writer;
    type Own = ();

    open spec fn abs(a: MidS, b: WrS, o: ()) -> BizS { top_abs(a, b) }
    open spec fn guard(a: MidS, b: WrS, o: (), l: BizL) -> bool { p3_guard(a, b, l) }
    open spec fn lab_a(a: MidS, b: WrS, o: (), l: BizL) -> Option<MidL> { p3_lab_m(a, b, l) }
    open spec fn lab_b(a: MidS, b: WrS, o: (), l: BizL) -> Option<WrL> { p3_lab_w(a, b, l) }
    open spec fn own_next(a: MidS, b: WrS, o: (), l: BizL, o2: ()) -> bool { true }

    proof fn step_binds(a: MidS, b: WrS, o: (), l: BizL, a2: MidS, b2: WrS, o2: ()) {
        lemma_p3_binds(a, b, l, a2, b2);
    }

    proof fn step_enabled(a: MidS, b: WrS, o: (), l: BizL, t: BizS) {
        lemma_p3_enabled(a, b, l, t);
        assert(Self::abs(mid_of(t), t.wr, ()) == t);
    }
}

impl ProtocolInit for TopP {
    open spec fn own_init(o: ()) -> bool { true }
    proof fn init_binds(a: MidS, b: WrS, o: ()) {
        assert(mid_of(top_abs(a, b)) == a);
    }
}

/// REFINES: every synchronized step of Mid and the writers is one Biz step.
pub proof fn lemma_p3_binds(a: MidS, b: WrS, l: BizL, a2: MidS, b2: WrS)
    requires
        p3_guard(a, b, l),
        step_or_stutter::<Mid>(a, p3_lab_m(a, b, l), a2),
        step_or_stutter::<Writer>(b, p3_lab_w(a, b, l), b2),
    ensures biz_next(top_abs(a, b), l, top_abs(a2, b2)),
{
    assert(mid_of(top_abs(a, b)) == a);
    assert(mid_of(top_abs(a2, b2)) == a2);
}

/// Non-vacuity: every Biz step from a represented state is realized by Mid and the writers.
pub proof fn lemma_p3_enabled(a: MidS, b: WrS, l: BizL, t: BizS)
    requires biz_next(top_abs(a, b), l, t),
    ensures
        p3_guard(a, b, l),
        step_or_stutter::<Mid>(a, p3_lab_m(a, b, l), mid_of(t)),
        step_or_stutter::<Writer>(b, p3_lab_w(a, b, l), t.wr),
{
    assert(mid_of(top_abs(a, b)) == a);
}

} // verus!
