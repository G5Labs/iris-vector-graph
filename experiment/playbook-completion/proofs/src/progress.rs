//! Progress of one redaction run under explicit fairness (actors::fairness).
//!
//! The watched run is the redaction of target `t` from the moment t is marked (`RunProgress::init`). Its rank is
//! the records and revision boundaries left between the run's cursor (kept with the marker) and its scan bound, plus
//! one for the pending final step; it is 0 once a final step of t has succeeded (`done`). `FairWork` holds: a scan
//! step or a successful final step of the run lowers the rank, and **no step raises it**: commits append after the
//! scan bound, the cursor survives process stops, a resume continues from it, and the marker of t cannot be replaced
//! while the run is unfinished. `theorem_redaction_completes` (from `actors::fairness::eventually_drained`): under
//! productive fairness the run finishes.
//!
//! Productive fairness is the premise. What makes it reasonable is proved (`theorem_work_available`): while the run
//! is unfinished, the ledger is enabled and no erasure holds the head lock, a process of t at the marker's cursor can
//! scan or go to its final step, a process at its final step can finish (it is **never refused**: nothing of t can be
//! live while t is marked), and a process that is not running can open and resume from the marker's cursor. The
//! environmental premises that turn this into productive fairness are named in PROOFS.md: PF-1 the operator re-runs
//! the redaction after a stop; PF-2 the ledger is enabled again and stays enabled long enough; PF-3 every erasure
//! releases the head lock (it ends); PF-4 a process with an enabled step is eventually scheduled. (Commits into the
//! target are refused while it is marked; that is proved, not assumed, and it is why the scan bound can stay fixed.)
//!
//! Progress-only control `control_progress_rewind`: a resume rewinds the run's cursor to the first record (the pin's
//! re-run rescans, LedgerRedact.cls:213). Every safety proof still verifies; `nonincreasing` below fails.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use actors::fairness::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::redactor::*;
use crate::protocol_rl::*;
use crate::biz::*;

verus! {

pub open spec fn rows_between(h: Seq<Seq<Rec>>, i: nat, end: nat) -> nat
    decreases end - i
{
    if i >= end || i >= h.len() { 0 } else { h[i as int].len() + 1 + rows_between(h, i + 1, end) }
}

/// Work left for the run: records and boundaries from the marker's cursor to its bound, plus the final step.
pub open spec fn run_rank(x: BizS) -> nat {
    let l = x.rl.l;
    let rb = rows_between(l.hist, l.mi, l.mend);
    if l.mi < l.mend && l.mj <= rb { (rb - l.mj) as nat + 1 } else { 1 }
}

pub struct W { pub s: BizS, pub t: Tgt, pub done: bool }

pub struct WStep { pub l: BizL, pub work: bool }

pub open spec fn finishes(w: W, l: BizL) -> bool {
    match l {
        BizL::Final { p, ok } => ok && w.s.rl.r.procs.contains_key(p) && tgt_of(w.s.rl.r, p) == w.t,
        _ => false,
    }
}

pub open spec fn is_work(w: W, l: BizL) -> bool {
    !w.done && (l is Scan || finishes(w, l))
}

/// While the run is unfinished, its target holds the marker.
pub open spec fn watch_ok(w: W) -> bool {
    !w.done ==> w.s.rl.l.marker == Some(w.t)
}

pub struct RunProgress;

impl Contract for RunProgress {
    type S = W;
    type L = WStep;

    open spec fn init(w: W) -> bool { biz_inv(w.s) && !w.done && w.s.rl.l.marker == Some(w.t) }

    open spec fn next(w: W, x: WStep, v: W) -> bool {
        &&& biz_inv(w.s) && watch_ok(w)
        &&& biz_next(w.s, x.l, v.s)
        &&& v.t == w.t
        &&& v.done == (w.done || finishes(w, x.l))
        &&& x.work == is_work(w, x.l)
    }
}

pub open spec fn rank_w(w: W) -> nat { if w.done { 0 } else { run_rank(w.s) } }

// ------------------------------------------------------------------------------------------------ rank lemmas

pub proof fn lemma_rb_push(h: Seq<Seq<Rec>>, rs: Seq<Rec>, i: nat, end: nat)
    requires end <= h.len(),
    ensures rows_between(h.push(rs), i, end) == rows_between(h, i, end),
    decreases end - i,
{
    if i < end {
        assert(h.push(rs)[i as int] == h[i as int]);
        lemma_rb_push(h, rs, i + 1, end);
    }
}

pub proof fn lemma_rb_same(h1: Seq<Seq<Rec>>, h2: Seq<Seq<Rec>>, i: nat, end: nat)
    requires h1.len() == h2.len(), forall|k: int| 0 <= k < h1.len() ==> (#[trigger] h1[k]).len() == h2[k].len(),
    ensures rows_between(h1, i, end) == rows_between(h2, i, end),
    decreases end - i,
{
    if i < end && i < h1.len() {
        lemma_rb_same(h1, h2, i + 1, end);
    }
}

/// A scan step of the run lowers its rank by one.
pub proof fn lemma_scan_rank(x: BizS, p: nat, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Scan { p }, y),
    ensures run_rank(y) < run_rank(x),
{
    let l = x.rl.l;
    let h = l.hist;
    let c = pcur(x.rl.r, p);
    assert(c == dcur(l));
    assert(cursor_ok(h, c));
    let h2 = y.rl.l.hist;
    assert(h2.len() == h.len());
    assert forall|k: int| 0 <= k < h2.len() implies (#[trigger] h2[k]).len() == h[k].len() by {}
    let rb = rows_between(h, c.i, c.end);
    assert(rb == h[c.i as int].len() + 1 + rows_between(h, c.i + 1, c.end));
    lemma_rb_same(h2, h, c.i, c.end);
    lemma_rb_same(h2, h, c.i + 1, c.end);
    assert(y.rl.l.mend == c.end);
    if row_end(l, c) {
        assert(c.j == h[c.i as int].len());
        assert(y.rl.l.mi == c.i + 1 && y.rl.l.mj == 0);
    } else {
        assert(y.rl.l.mi == c.i && y.rl.l.mj == c.j + 1);
    }
}

// ------------------------------------------------------------------------------------------------ FairWork

impl RankedWork for RunProgress {
    open spec fn rank(w: W) -> nat { rank_w(w) }
    open spec fn work(x: WStep) -> bool { x.work }

    proof fn decreases(w: W, x: WStep, v: W) {
        match x.l {
            BizL::Scan { p } => { lemma_scan_rank(w.s, p, v.s); }
            _ => {}
        }
    }
}

impl FairWork for RunProgress {
    /// No step raises the rank of an unfinished run.
    proof fn nonincreasing(w: W, x: WStep, v: W) {
        if !w.done {
            let s = w.s;
            let h = s.rl.l.hist;
            match x.l {
                BizL::Commit { cs, key } => {
                    assert(cursor_ok(h, dcur(s.rl.l)));
                    lemma_rb_push(h, lives(cs), s.rl.l.mi, s.rl.l.mend);
                }
                BizL::Scan { p } => { lemma_scan_rank(s, p, v.s); }
                BizL::Start { p, fresh } => {
                    // A resume continues from the marker's cursor; a fresh start needs no marker (excluded here).
                    assert(!fresh);
                    assert(v.s.rl.l == start_ledger(s.rl.l, s.rl.r, p, false));
                    assert(run_rank(v.s) <= run_rank(s));
                }
                BizL::Final { p, ok } => {
                    if ok { assert(finishes(w, x.l)); }
                }
                _ => {}
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ theorems

/// The watched run's bookkeeping is kept by every business step, so `RunProgress` restricts no execution of Biz
/// that starts with t marked.
pub proof fn lemma_watch_step(w: W, l: BizL, s2: BizS)
    requires biz_inv(w.s), watch_ok(w), biz_next(w.s, l, s2),
    ensures biz_inv(s2), watch_ok(W { s: s2, t: w.t, done: w.done || finishes(w, l) }),
{
    lemma_biz_safe(w.s, l, s2);
}

/// **Progress.** Under productive fairness, a marked redaction finishes: a successful final step of its target
/// happens, and (`theorem_audit_counts_own_target`, `lemma_cursor_done`) no live record of the target is then left in
/// the history and the marker is gone.
pub proof fn theorem_redaction_completes(s: spec_fn(nat) -> W, l: spec_fn(nat) -> WStep, i: nat)
    requires infinite_execution::<RunProgress>(s, l), productive_fairness::<RunProgress>(s, l),
    ensures exists|k: nat| k >= i && #[trigger] s(k).done,
{
    eventually_drained::<RunProgress>(s, l, i);
    let k = choose|k: nat| k >= i && #[trigger] RunProgress::rank(s(k)) == 0;
    assert(s(k).done);
}

/// What a successful final step of the run leaves: no marker, no live record of the target in the history (so its
/// replay holds nothing of it).
pub proof fn theorem_final_effect(x: BizS, p: nat, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Final { p, ok: true }, y),
    ensures y.rl.l.marker is None, no_member(y.rl.l.hist, tgt_of(x.rl.r, p)),
        !live_in(replay(y.rl.l.hist), tgt_of(x.rl.r, p)),
{
    let t = tgt_of(x.rl.r, p);
    let h = x.rl.l.hist;
    lemma_cursor_done(h, dcur(x.rl.l));
    let h2 = y.rl.l.hist;
    assert forall|i: int, j: int| 0 <= i < h2.len() && 0 <= j < h2[i].len() implies !live_member(#[trigger] h2[i][j], t) by {
        if i < h.len() { assert(h2[i] == h[i]); }
    }
    lemma_replay_no_member(h2, t);
}

/// **Work is always available** to an unfinished run while the ledger is enabled and no erasure holds the head lock:
/// a process of t in its batches at the marker's cursor can scan, or go to its final step at the bound; a process at
/// its final step can finish and is never refused (nothing of t can be live while t is marked); and a process that is
/// not running can open and resume the run (the operator's re-run after a stop), continuing from the marker's cursor.
pub proof fn theorem_work_available(w: W, p: nat)
    requires biz_inv(w.s), watch_ok(w), !w.done, w.s.rl.l.enabled, !w.s.rl.l.locked,
    ensures ({
        let s = w.s;
        let l = s.rl.l;
        let r = s.rl.r;
        let mine = r.procs.contains_key(p) && r.procs[p].t == w.t && synced(l, r, p);
        &&& (mine && has_phase(r, p, Phase::Batches) && l.mi < l.mend) ==> exists|y: BizS| #[trigger] biz_next(s, BizL::Scan { p }, y)
        &&& (mine && has_phase(r, p, Phase::Batches) && l.mi == l.mend) ==> exists|y: BizS| #[trigger] biz_next(s, BizL::ToFinal { p }, y)
        &&& (mine && has_phase(r, p, Phase::Final) && l.mi == l.mend) ==> exists|y: BizS| #[trigger] biz_next(s, BizL::Final { p, ok: true }, y)
        &&& !r.procs.contains_key(p) ==> exists|y1: BizS, y2: BizS| #[trigger] biz_next(s, BizL::Open { p, t: w.t }, y1)
                && #[trigger] biz_next(y1, BizL::Start { p, fresh: false }, y2)
                && has_phase(y2.rl.r, p, Phase::Batches) && synced(y2.rl.l, y2.rl.r, p)
    }),
{
    let s = w.s;
    let l = s.rl.l;
    let r = s.rl.r;
    let c = dcur(l);
    assert(cursor_ok(l.hist, c));
    let mine = r.procs.contains_key(p) && r.procs[p].t == w.t && synced(l, r, p);
    if mine && has_phase(r, p, Phase::Batches) && l.mi < l.mend {
        let pc = pcur(r, p);
        let y = BizS {
            rl: RLS {
                l: ledger_batch(l, pc.i, pc.j, pc.t, hit(l, pc), next_i(l, pc), next_j(l, pc)),
                r: red_step(r, RedL::Advance { p, row_end: row_end(l, pc) }),
            },
            ..s
        };
        assert(biz_next(s, BizL::Scan { p }, y));
    }
    if mine && has_phase(r, p, Phase::Batches) && l.mi == l.mend {
        let y = BizS { rl: RLS { l, r: red_step(r, RedL::ToFinal { p }) }, ..s };
        assert(biz_next(s, BizL::ToFinal { p }, y));
    }
    if mine && has_phase(r, p, Phase::Final) && l.mi == l.mend {
        let y = BizS { rl: RLS { l: ledger_audit(l, w.t), r: red_step(r, RedL::Finish { p }) }, st: s.st, pend: s.pend.remove(w.t) };
        assert(biz_next(s, BizL::Final { p, ok: true }, y));
    }
    if !r.procs.contains_key(p) {
        let y1 = BizS { rl: RLS { l, r: red_step(r, RedL::Open { p, t: w.t }) }, ..s };
        assert(biz_next(s, BizL::Open { p, t: w.t }, y1));
        let l2 = start_ledger(l, y1.rl.r, p, false);
        let y2 = BizS { rl: RLS { l: l2, r: red_step(y1.rl.r, RedL::Attach { p, i: l2.mi, j: l2.mj, end: l2.mend }) }, ..s };
        assert(tgt_of(y1.rl.r, p) == w.t);
        assert(biz_next(y1, BizL::Start { p, fresh: false }, y2));
    }
}

} // verus!
