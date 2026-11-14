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
        _ => top_ok(m, w, l),
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
    open spec fn lab_a(a: MidS, b: WrS, o: (), l: BizL) -> Option<MidL> { top_lab_m(a, b, l) }
    open spec fn lab_b(a: MidS, b: WrS, o: (), l: BizL) -> Option<WrL> { top_lab_w(a, b, l) }
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
        step_or_stutter::<Mid>(a, top_lab_m(a, b, l), a2),
        step_or_stutter::<Writer>(b, top_lab_w(a, b, l), b2),
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
        step_or_stutter::<Mid>(a, top_lab_m(a, b, l), mid_of(t)),
        step_or_stutter::<Writer>(b, top_lab_w(a, b, l), t.wr),
{
    assert(mid_of(top_abs(a, b)) == a);
}

} // verus!
