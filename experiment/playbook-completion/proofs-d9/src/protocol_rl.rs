//! Level 1: protocol `RLP` composes the **Ledger** and the **Redactor** into the contract `RL` (the redaction
//! ledger: the ledger with its redaction processes, without the content tables). `RL` is in turn participant A of the
//! level-2 protocol (`protocol_sys`).
//!
//! The reviewed design (HD-1301, the own-marker Final, and a durable cursor), as the protocol's decisions:
//! - **Start** is one transaction under the head lock: a fresh run writes its marker (with the run's cursor at the
//!   first record and its bound at the head) in the same step as it opens, and only when no marker exists; a resumed
//!   run needs its own target's marker and continues from the marker's cursor. (The liveness check reads the store and
//!   is the level-2 protocol's part of the same step.)
//! - **Scan** (one record of a batch, under the head lock) runs only while the marker names the process's target and
//!   only from the marker's cursor; it writes the cursor back with the tombstone.
//! - **Final** runs only under the process's own marker, at the bound, so its audit counts only its own target.
//!
//! D-9: unchanged from `proofs/src/protocol_rl.rs` except that a target is three predicates (the cursor scans with
//! the record-match predicate `rm`). The original controls of this level (F-1302, F-1303) are not carried over: their
//! guards here are unchanged (see PROOFS.md).
//!
//! Progress-only control `control_progress_rewind`: a resume rewinds the run's cursor to the first record (the pin's
//! re-run rescans, LedgerRedact.cls:213). It changes this contract and this protocol consistently; every safety proof
//! must still verify and the progress proof must fail (`progress.rs`).
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
    Commit { cs: Seq<Content>, key: Option<IKey> },
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
        RLL::Commit { cs, key } => ledger_pre(l, LedgerL::Commit { cs, key }) && u == RLS { l: ledger_commit(l, cs, key), r },
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

/// RL's invariant is its participants' invariants.
pub open spec fn rl_inv(s: RLS) -> bool { ledger_inv(s.l) && red_inv(s.r) }

pub proof fn lemma_rl_safe(s: RLS, x: RLL, u: RLS)
    requires rl_inv(s), rl_next(s, x, u),
    ensures rl_inv(u),
{
    let l = s.l;
    let r = s.r;
    match x {
        RLL::Commit { cs, key } => { lemma_ledger_safe(l, LedgerL::Commit { cs, key }); }
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
        }
        RLL::ToFinal { p } => { lemma_red_safe(r, RedL::ToFinal { p }); }
        RLL::Final { p, ok } => {
            lemma_red_safe(r, RedL::Finish { p });
            if ok { lemma_ledger_safe(l, LedgerL::Audit { t: tgt_of(r, p) }); }
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
        RLL::Start { p, fresh } => start_ok(l, r, p, fresh),
        RLL::Scan { p } => scan_ok(l, r, p),
        RLL::Final { p, ok } => final_ok(l, r, p),
        _ => true,
    }
}

/// USES edges: the ledger operation of each step.
pub open spec fn p1_lab_l(l: LedgerS, r: RedS, x: RLL) -> Option<LedgerL> {
    match x {
        RLL::Commit { cs, key } => Some(LedgerL::Commit { cs, key }),
        RLL::Replay { key } => Some(LedgerL::Replay { key }),
        RLL::Lock => Some(LedgerL::Lock),
        RLL::Unlock => Some(LedgerL::Unlock),
        RLL::SetEnabled { on } => Some(LedgerL::SetEnabled { on }),
        RLL::Start { p, fresh } =>
            if fresh { Some(LedgerL::Mark { t: tgt_of(r, p) }) }
            else if resume_rewinds() { Some(LedgerL::Rewind) } else { None },
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
