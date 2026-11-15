//! Level 1: protocol `RLP` composes the **Ledger** and the **Redactor** into the contract `RL` (the redaction
//! ledger: the ledger with its redaction processes, without the content tables). `RL` is in turn participant A of the
//! level-2 protocol (`protocol_sys`) and of the readers' protocol (`protocol_rd`).
//!
//! The reviewed design (HD-1301, the own-marker Final, and a durable cursor), as the protocol's decisions:
//! - **Start** is one transaction under the head lock: a fresh run writes its marker (with the run's cursor at the
//!   first record and its bound at the head) in the same step as it opens, and only when no marker exists; a resumed
//!   run needs its own target's marker and continues from the marker's cursor. (The liveness check reads the store and
//!   is the level-2 protocol's part of the same step.)
//! - **Scan** (one record of a batch, under the head lock) runs only while the marker names the process's target and
//!   only from the marker's cursor; it writes the cursor back with the tombstone.
//! - **Final** runs only under the process's own marker, at the bound, so its audit counts only its own target.
//! - **Commit** (D-9b, reviewed design R-1 for F-CS01): every operation of the changeset leaves a record — a no-op
//!   operation a content-free no-op record (`Eff::Nop`) naming its entity — so every key the changeset's operations
//!   address is named by a record of its revision (`ops_recorded`). Hence no revision is attributable to a target
//!   without a record the target's record match can tombstone, which is what clears its metadata and moves its key.
//!
//! Controls of this level (each must fail `lemma_p1_binds` here; each has a proved counterexample):
//! - `control_fcs01_noop_unrecorded` (F-CS01, live `sim-fcs01-minimal`): a commit records only operations that changed
//!   something and writes the revision row and key binding regardless (Ledger.cls:489-492, 520-525; LedgerApply.cls:
//!   229-233, 252-263): a zero-record revision keeps its metadata and its key through a complete redaction (`cx_fcs01`).
//! - `control_f1302_unlocked_start` (F-1302, re-run of the original control in this crate): Start checks without the
//!   head lock and writes no marker; a batch runs with no marker and its first tombstone writes it
//!   (LedgerRedact.cls:202-211, 322-324; `cx_f1302`).
//! - `control_f1303_other_marker` (F-1303): Final runs under whatever marker exists (FinalInLock, cls:409-441;
//!   `cx_f1303`).
//!
//! Progress-only controls: `control_progress_rewind` (a resume rewinds the run's cursor, LedgerRedact.cls:213) and
//! `control_bound_follows_tail` (D-12: the bound follows the tail, `ledger::bound_after_commit`). Every safety proof
//! must still verify with either, and the progress proof must fail (`progress.rs`).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::redactor::*;
use crate::compose::*;

verus! {

pub struct RLS { pub l: LedgerS, pub r: RedS }

pub enum RLL {
    Commit { cs: Seq<Content>, named: Seq<Key>, key: Option<IKey> },
    Replay { key: IKey },
    Lock,
    Unlock,
    SetEnabled { on: bool },
    Open { p: nat, t: Tgt },
    Start { p: nat, fresh: bool },
    Scan { p: nat },
    ToFinal { p: nat },
    Final { p: nat, ok: bool },
    Stop { p: nat },
}

pub open spec fn resume_rewinds() -> bool { cfg!(feature = "control_progress_rewind") }

// ------------------------------------------------------------------------------------------------ read views

pub open spec fn tgt_of(r: RedS, p: nat) -> Tgt { r.procs[p].t }

/// Process p's cursor.
pub open spec fn pcur(r: RedS, p: nat) -> Cur {
    Cur { t: r.procs[p].t.rm, i: r.procs[p].i, j: r.procs[p].j, end: r.procs[p].end }
}

/// The run's cursor kept with the marker.
pub open spec fn dcur(l: LedgerS) -> Cur { Cur { t: l.marker->0.rm, i: l.mi, j: l.mj, end: l.mend } }

/// Process p's cursor is the marker's.
pub open spec fn synced(l: LedgerS, r: RedS, p: nat) -> bool {
    r.procs[p].i == l.mi && r.procs[p].j == l.mj && r.procs[p].end == l.mend
}

/// The cursor stands past the last record of its revision.
pub open spec fn row_end(l: LedgerS, c: Cur) -> bool { c.j >= l.hist[c.i as int].len() }

/// The record under the cursor is a live record the cursor's target matches (`Matches`).
pub open spec fn hit(l: LedgerS, c: Cur) -> bool {
    !row_end(l, c) && live_member(l.hist[c.i as int][c.j as int], c.t)
}

pub open spec fn next_i(l: LedgerS, c: Cur) -> nat { if row_end(l, c) { c.i + 1 } else { c.i } }

pub open spec fn next_j(l: LedgerS, c: Cur) -> nat { if row_end(l, c) { 0 } else { c.j + 1 } }

// ------------------------------------------------------------------------------------------------ the RL contract

/// Start (reviewed, HD-1301): under the head lock; fresh exactly when no marker exists; a resume needs its own marker.
pub open spec fn start_ok(l: LedgerS, r: RedS, p: nat, fresh: bool) -> bool {
    &&& has_phase(r, p, Phase::Opening)
    &&& l.enabled && !l.locked
    &&& fresh == (l.marker is None)
    &&& !fresh ==> l.marker == Some(tgt_of(r, p))
}

/// Scan (reviewed): under the head lock, from the marker's cursor, while the marker names the process's target.
pub open spec fn scan_ok(l: LedgerS, r: RedS, p: nat) -> bool {
    &&& has_phase(r, p, Phase::Batches) && synced(l, r, p)
    &&& r.procs[p].i < r.procs[p].end && r.procs[p].i < l.hist.len()
    &&& l.enabled && !l.locked
    &&& l.marker == Some(tgt_of(r, p))
}

/// Final (reviewed): under the head lock and the process's own marker, with the marker's cursor at the bound.
pub open spec fn final_ok(l: LedgerS, r: RedS, p: nat) -> bool {
    &&& has_phase(r, p, Phase::Final) && synced(l, r, p)
    &&& r.procs[p].i == r.procs[p].end
    &&& l.enabled && !l.locked
    &&& l.marker == Some(tgt_of(r, p))
}

/// The ledger after a start: a fresh run's marker and cursor; a resume keeps the marker's cursor.
pub open spec fn start_ledger(l: LedgerS, r: RedS, p: nat, fresh: bool) -> LedgerS {
    if fresh { ledger_mark(l, tgt_of(r, p)) } else if resume_rewinds() { LedgerS { mi: 0, mj: 0, ..l } } else { l }
}

pub open spec fn rl_next(s: RLS, x: RLL, u: RLS) -> bool {
    let l = s.l;
    let r = s.r;
    match x {
        RLL::Commit { cs, named, key } => ops_recorded(cs, named) && ledger_pre(l, LedgerL::Commit { cs, named, key })
            && u == RLS { l: ledger_commit(l, cs, named, key), r },
        RLL::Replay { key } => ledger_pre(l, LedgerL::Replay { key }) && u == s,
        RLL::Lock => !l.locked && u == RLS { l: LedgerS { locked: true, ..l }, r },
        RLL::Unlock => l.locked && u == RLS { l: LedgerS { locked: false, ..l }, r },
        RLL::SetEnabled { on } => u == RLS { l: LedgerS { enabled: on, ..l }, r },
        RLL::Open { p, t } => red_pre(r, RedL::Open { p, t }) && u == RLS { l, r: red_step(r, RedL::Open { p, t }) },
        RLL::Start { p, fresh } => {
            let l2 = start_ledger(l, r, p, fresh);
            let y = RedL::Attach { p, i: l2.mi, j: l2.mj, end: l2.mend };
            &&& start_ok(l, r, p, fresh) && red_pre(r, y)
            &&& u == RLS { l: l2, r: red_step(r, y) }
        }
        RLL::Scan { p } => {
            let c = pcur(r, p);
            &&& scan_ok(l, r, p)
            &&& u == RLS {
                    l: ledger_batch(l, c.i, c.j, tgt_of(r, p), hit(l, c), next_i(l, c), next_j(l, c)),
                    r: red_step(r, RedL::Advance { p, row_end: row_end(l, c) }),
                }
        }
        RLL::ToFinal { p } => red_pre(r, RedL::ToFinal { p }) && u == RLS { l, r: red_step(r, RedL::ToFinal { p }) },
        RLL::Final { p, ok } => {
            &&& final_ok(l, r, p)
            &&& u == RLS { l: if ok { ledger_audit(l, tgt_of(r, p)) } else { l }, r: red_step(r, RedL::Finish { p }) }
        }
        RLL::Stop { p } => red_pre(r, RedL::Stop { p }) && u == RLS { l, r: red_step(r, RedL::Stop { p }) },
    }
}

pub struct RL;

impl Contract for RL {
    type S = RLS;
    type L = RLL;

    open spec fn init(s: RLS) -> bool { Ledger::init(s.l) && Redactor::init(s.r) }

    open spec fn next(s: RLS, x: RLL, u: RLS) -> bool { rl_next(s, x, u) }
}

/// Every key a revision's operations addressed is named by a record of that revision (live or tombstoned): the
/// reviewed Commit (`ops_recorded`) gives it; tombstones keep the key; audit revisions name nothing.
pub open spec fn attr_ok(l: LedgerS) -> bool {
    forall|i: int, j: int| 0 <= i < l.meta.len() && 0 <= j < l.meta[i].named.len()
        ==> rev_names(l.hist[i], #[trigger] l.meta[i].named[j])
}

/// RL's invariant: its participants' invariants, and the attribution of every revision's operations to its records.
pub open spec fn rl_inv(s: RLS) -> bool { ledger_inv(s.l) && red_inv(s.r) && attr_ok(s.l) }

pub proof fn lemma_attr_commit(l: LedgerS, cs: Seq<Content>, named: Seq<Key>, key: Option<IKey>)
    requires ledger_inv(l), attr_ok(l), ops_recorded(cs, named),
    ensures attr_ok(ledger_commit(l, cs, named, key)),
{
    let u = ledger_commit(l, cs, named, key);
    let n = l.hist.len() as int;
    assert forall|i: int, j: int| 0 <= i < u.meta.len() && 0 <= j < u.meta[i].named.len()
        implies rev_names(u.hist[i], #[trigger] u.meta[i].named[j]) by {
        if i < n {
            assert(u.meta[i] == l.meta[i] && u.hist[i] == l.hist[i]);
        } else {
            assert(u.meta[i].named == named);
            assert(has_rec_key(cs, named[j]));
            let a = choose|a: int| 0 <= a < cs.len() && (#[trigger] cs[a]).k == named[j];
            assert(u.hist[i] == lives(cs));
            assert(lives(cs)[a] == Rec::Live(cs[a]));
            assert(rec_names(u.hist[i][a], named[j]));
        }
    }
}

pub proof fn lemma_attr_tomb(l: LedgerS, i0: nat, j0: nat, t: Tgt)
    requires ledger_inv(l), attr_ok(l), i0 < l.hist.len(), j0 < l.hist[i0 as int].len(), l.hist[i0 as int][j0 as int] is Live,
    ensures attr_ok(ledger_tomb(l, i0, j0, t)),
{
    let u = ledger_tomb(l, i0, j0, t);
    assert forall|i: int, j: int| 0 <= i < u.meta.len() && 0 <= j < u.meta[i].named.len()
        implies rev_names(u.hist[i], #[trigger] u.meta[i].named[j]) by {
        assert(u.meta[i].named == l.meta[i].named);
        let k = l.meta[i].named[j];
        assert(rev_names(l.hist[i], k));
        let a = choose|a: int| 0 <= a < l.hist[i].len() && #[trigger] rec_names(l.hist[i][a], k);
        if i == i0 && a == j0 {
            assert(u.hist[i][a] == Rec::Tomb(l.hist[i][a]->Live_0));
        } else {
            assert(u.hist[i][a] == l.hist[i][a]);
        }
        assert(rec_names(u.hist[i][a], k));
    }
}

pub proof fn lemma_attr_audit(l: LedgerS, t: Tgt)
    requires ledger_inv(l), attr_ok(l),
    ensures attr_ok(ledger_audit(l, t)),
{
    let u = ledger_audit(l, t);
    let n = l.hist.len() as int;
    assert forall|i: int, j: int| 0 <= i < u.meta.len() && 0 <= j < u.meta[i].named.len()
        implies rev_names(u.hist[i], #[trigger] u.meta[i].named[j]) by {
        if i < n {
            assert(u.meta[i] == l.meta[i] && u.hist[i] == l.hist[i]);
        } else {
            assert(u.meta[i] == audit_meta());
        }
    }
}

pub proof fn lemma_rl_safe(s: RLS, x: RLL, u: RLS)
    requires rl_inv(s), rl_next(s, x, u),
    ensures rl_inv(u),
{
    let l = s.l;
    let r = s.r;
    match x {
        RLL::Commit { cs, named, key } => {
            lemma_ledger_safe(l, LedgerL::Commit { cs, named, key });
            lemma_attr_commit(l, cs, named, key);
        }
        RLL::Lock => { lemma_ledger_safe(l, LedgerL::Lock); }
        RLL::Unlock => { lemma_ledger_safe(l, LedgerL::Unlock); }
        RLL::SetEnabled { on } => { lemma_ledger_safe(l, LedgerL::SetEnabled { on }); }
        RLL::Open { p, t } => { lemma_red_safe(r, RedL::Open { p, t }); }
        RLL::Start { p, fresh } => {
            let l2 = start_ledger(l, r, p, fresh);
            lemma_red_safe(r, RedL::Attach { p, i: l2.mi, j: l2.mj, end: l2.mend });
            if fresh { lemma_ledger_safe(l, LedgerL::Mark { t: tgt_of(r, p) }); }
            else if resume_rewinds() { lemma_ledger_safe(l, LedgerL::Rewind); }
        }
        RLL::Scan { p } => {
            let c = pcur(r, p);
            lemma_red_safe(r, RedL::Advance { p, row_end: row_end(l, c) });
            lemma_ledger_safe(l, LedgerL::Batch { i: c.i, j: c.j, t: tgt_of(r, p), tomb: hit(l, c), ni: next_i(l, c), nj: next_j(l, c) });
            if hit(l, c) { lemma_attr_tomb(l, c.i, c.j, tgt_of(r, p)); }
        }
        RLL::ToFinal { p } => { lemma_red_safe(r, RedL::ToFinal { p }); }
        RLL::Final { p, ok } => {
            lemma_red_safe(r, RedL::Finish { p });
            if ok { lemma_ledger_safe(l, LedgerL::Audit { t: tgt_of(r, p) }); lemma_attr_audit(l, tgt_of(r, p)); }
        }
        RLL::Stop { p } => { lemma_red_safe(r, RedL::Stop { p }); }
        _ => {}
    }
}

impl SafeContract for RL {
    open spec fn inv(s: RLS) -> bool { rl_inv(s) }
    proof fn init_safe(s: RLS) {}
    proof fn step_safe(s: RLS, x: RLL, u: RLS) { lemma_rl_safe(s, x, u); }
}

// ------------------------------------------------------------------------------------------------ the protocol

/// The protocol's decision on the participants' read views (reviewed design; the controls replace parts of it).
pub open spec fn p1_guard(l: LedgerS, r: RedS, x: RLL) -> bool {
    match x {
        RLL::Commit { cs, named, key } =>
            if cfg!(feature = "control_fcs01_noop_unrecorded") {
                // Ledger.cls:489-492 counts operations; a no-op operation writes no record (LedgerApply.cls:229-263).
                true
            } else {
                ops_recorded(cs, named)
            },
        RLL::Start { p, fresh } =>
            if cfg!(feature = "control_f1302_unlocked_start") {
                // LedgerRedact.cls:202-211: "another redaction?" read without the head lock.
                has_phase(r, p, Phase::Opening) && fresh == (l.marker is None) && (!fresh ==> l.marker == Some(tgt_of(r, p)))
            } else {
                start_ok(l, r, p, fresh)
            },
        RLL::Scan { p } =>
            if cfg!(feature = "control_f1302_unlocked_start") {
                // A batch runs from the process's own cursor whether or not a marker exists (cls:213-226, 322-324).
                has_phase(r, p, Phase::Batches) && r.procs[p].i < r.procs[p].end && r.procs[p].i < l.hist.len()
                    && l.enabled && !l.locked && (l.marker is None || l.marker == Some(tgt_of(r, p)))
            } else {
                scan_ok(l, r, p)
            },
        RLL::Final { p, ok } =>
            if cfg!(feature = "control_f1303_other_marker") {
                // FinalInLock re-checks only its own target's liveness and removes whichever marker exists.
                has_phase(r, p, Phase::Final) && r.procs[p].i == r.procs[p].end && l.enabled && !l.locked && l.marker is Some
            } else {
                final_ok(l, r, p)
            },
        _ => true,
    }
}

/// USES edges: the ledger operation of each step.
pub open spec fn p1_lab_l(l: LedgerS, r: RedS, x: RLL) -> Option<LedgerL> {
    match x {
        RLL::Commit { cs, named, key } => Some(LedgerL::Commit { cs, named, key }),
        RLL::Replay { key } => Some(LedgerL::Replay { key }),
        RLL::Lock => Some(LedgerL::Lock),
        RLL::Unlock => Some(LedgerL::Unlock),
        RLL::SetEnabled { on } => Some(LedgerL::SetEnabled { on }),
        RLL::Start { p, fresh } =>
            if fresh {
                if cfg!(feature = "control_f1302_unlocked_start") { None } else { Some(LedgerL::Mark { t: tgt_of(r, p) }) }
            } else if resume_rewinds() { Some(LedgerL::Rewind) } else { None },
        RLL::Scan { p } => {
            let c = pcur(r, p);
            Some(LedgerL::Batch { i: c.i, j: c.j, t: tgt_of(r, p), tomb: hit(l, c), ni: next_i(l, c), nj: next_j(l, c) })
        }
        RLL::Final { p, ok } => if ok { Some(LedgerL::Audit { t: tgt_of(r, p) }) } else { None },
        _ => None,
    }
}

/// USES edges: the redactor operation of each step (a fresh run scans from the first record to the head; a resumed
/// one from the marker's cursor).
pub open spec fn p1_lab_r(l: LedgerS, r: RedS, x: RLL) -> Option<RedL> {
    match x {
        RLL::Open { p, t } => Some(RedL::Open { p, t }),
        RLL::Start { p, fresh } =>
            if fresh { Some(RedL::Attach { p, i: 0, j: 0, end: l.hist.len() }) }
            else if resume_rewinds() { Some(RedL::Attach { p, i: 0, j: 0, end: l.mend }) }
            else { Some(RedL::Attach { p, i: l.mi, j: l.mj, end: l.mend }) },
        RLL::Scan { p } => Some(RedL::Advance { p, row_end: row_end(l, pcur(r, p)) }),
        RLL::ToFinal { p } => Some(RedL::ToFinal { p }),
        RLL::Final { p, ok } => Some(RedL::Finish { p }),
        RLL::Stop { p } => Some(RedL::Stop { p }),
        _ => None,
    }
}

pub struct RLP;

impl Protocol2 for RLP {
    type Outer = RL;
    type A = Ledger;
    type B = Redactor;
    type Own = ();

    open spec fn abs(a: LedgerS, b: RedS, o: ()) -> RLS { RLS { l: a, r: b } }
    open spec fn guard(a: LedgerS, b: RedS, o: (), x: RLL) -> bool { p1_guard(a, b, x) }
    open spec fn lab_a(a: LedgerS, b: RedS, o: (), x: RLL) -> Option<LedgerL> { p1_lab_l(a, b, x) }
    open spec fn lab_b(a: LedgerS, b: RedS, o: (), x: RLL) -> Option<RedL> { p1_lab_r(a, b, x) }
    open spec fn own_next(a: LedgerS, b: RedS, o: (), x: RLL, o2: ()) -> bool { true }

    proof fn step_binds(a: LedgerS, b: RedS, o: (), x: RLL, a2: LedgerS, b2: RedS, o2: ()) {
        lemma_p1_binds(a, b, x, a2, b2);
    }

    proof fn step_enabled(a: LedgerS, b: RedS, o: (), x: RLL, t: RLS) {
        lemma_p1_enabled(a, b, x, t);
        assert(Self::abs(t.l, t.r, ()) == t);
    }
}

impl ProtocolInit for RLP {
    open spec fn own_init(o: ()) -> bool { true }
    proof fn init_binds(a: LedgerS, b: RedS, o: ()) {}
}

pub open spec fn side_l(a: LedgerS, y: Option<LedgerL>, a2: LedgerS) -> bool { step_or_stutter::<Ledger>(a, y, a2) }

pub open spec fn side_r(b: RedS, y: Option<RedL>, b2: RedS) -> bool { step_or_stutter::<Redactor>(b, y, b2) }

/// REFINES: every synchronized step of the ledger and the redactor is one RL step.
pub proof fn lemma_p1_binds(a: LedgerS, b: RedS, x: RLL, a2: LedgerS, b2: RedS)
    requires
        p1_guard(a, b, x),
        side_l(a, p1_lab_l(a, b, x), a2),
        side_r(b, p1_lab_r(a, b, x), b2),
    ensures rl_next(RLS { l: a, r: b }, x, RLS { l: a2, r: b2 }),
{
    match x {
        RLL::Start { p, fresh } => {
            assert(a2 == start_ledger(a, b, p, fresh));
        }
        RLL::Final { p, ok } => {
            if ok { assert(a2 == ledger_audit(a, tgt_of(b, p))); } else { assert(a2 == a); }
        }
        _ => {}
    }
}

/// Non-vacuity: every RL step from a represented state is realized by the ledger and the redactor.
pub proof fn lemma_p1_enabled(a: LedgerS, b: RedS, x: RLL, t: RLS)
    requires rl_next(RLS { l: a, r: b }, x, t),
    ensures
        p1_guard(a, b, x),
        side_l(a, p1_lab_l(a, b, x), t.l),
        side_r(b, p1_lab_r(a, b, x), t.r),
{
    match x {
        RLL::Scan { p } => {
            let c = pcur(b, p);
            if hit(a, c) { assert(c.j < a.hist[c.i as int].len()); }
        }
        _ => {}
    }
}

} // verus!
