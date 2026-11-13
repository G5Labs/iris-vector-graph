//! Progress of one redaction run (playbook §3.3 "protocols ... with progress under named fairness").
//!
//! The run of process 0 is the contract `Run0`: the L2 machine restricted to process 0's Scan and Final steps.
//! - `RankedWork`: each Scan or Final of the run lowers a natural-number rank (records and revisions left after the
//!   cursor, plus one for the final step), so an uninterrupted run takes at most `rank` steps
//!   (actors::hierarchy::work_bound).
//! - `theorem_run_can_step`: while the run holds the marker and the ledger is enabled, it always has a step.
//!
//! Premises (named, not proved): commits that append records raise the rank, so a run finishes only if commits stop
//! for long enough or the scan outpaces them (P-1306); a disabled ledger or a stopped process pauses the run until
//! someone calls Redact again (P-1307). LedgerRedact.Redact loops batches until the cursor passes the last record
//! (LedgerRedact.cls:216-226), so with a steady stream of commits it follows the tail.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::model::*;
use crate::l2::*;

verus! {

/// Records left after the cursor, counting one for each revision boundary.
pub open spec fn rows_from(rec: Seq<Seq<Rec>>, i: nat) -> nat
    decreases rec.len() - i
{
    if i >= rec.len() { 0 } else { rec[i as int].len() + 1 + rows_from(rec, i + 1) }
}

pub open spec fn rank0(s: S2) -> nat {
    if s.runs.contains_key(0) {
        let r = s.runs[0];
        if r.i < s.rec.len() && r.j <= s.rec[r.i as int].len() { (rows_from(s.rec, r.i) - r.j + 1) as nat } else { 1 }
    } else { 0 }
}

pub open spec fn work0(l: L2Label) -> bool {
    match l {
        L2Label::Scan { p } => p == 0,
        L2Label::Final { p, t, ok } => p == 0,
        _ => false,
    }
}

pub struct Run0;

impl Contract for Run0 {
    type S = S2;
    type L = L2Label;
    open spec fn init(s: S2) -> bool { L2::init(s) }
    open spec fn next(s: S2, l: L2Label, u: S2) -> bool { L2::next(s, l, u) && work0(l) }
}

proof fn lemma_rows_from_ge(rec: Seq<Seq<Rec>>, i: nat)
    requires i < rec.len(),
    ensures rows_from(rec, i) >= rec[i as int].len() + 1,
{
}

proof fn lemma_rows_from_same(a: Seq<Seq<Rec>>, b: Seq<Seq<Rec>>, i: nat)
    requires a.len() == b.len(), forall|k: int| 0 <= k < a.len() ==> (#[trigger] a[k]).len() == b[k].len(),
    ensures rows_from(a, i) == rows_from(b, i),
    decreases a.len() - i,
{
    if i < a.len() { lemma_rows_from_same(a, b, i + 1); }
}

impl RankedWork for Run0 {
    open spec fn rank(s: S2) -> nat { rank0(s) }
    open spec fn work(l: L2Label) -> bool { work0(l) }

    proof fn decreases(s: S2, l: L2Label, u: S2) {
        match l {
            L2Label::Scan { p } => {
                let r = s.runs[0];
                assert(cursor_ok(s, r));
                lemma_rows_from_ge(s.rec, r.i);
                if r.j >= s.rec[r.i as int].len() {
                    assert(u.rec == s.rec);
                } else {
                    let u_rec = u.rec;
                    assert(u_rec.len() == s.rec.len());
                    assert forall|k: int| 0 <= k < u_rec.len() implies (#[trigger] u_rec[k]).len() == s.rec[k].len() by {}
                    lemma_rows_from_same(u_rec, s.rec, r.i);
                }
            }
            L2Label::Final { p, t, ok } => {}
            _ => {}
        }
    }
}

/// An uninterrupted run of process 0 takes at most rank0 steps.
pub proof fn theorem_run_bounded(states: Seq<S2>, labels: Seq<L2Label>)
    requires segment::<Run0>(states, labels), forall|i: int| 0 <= i < labels.len() ==> work0(labels[i]),
    ensures labels.len() <= rank0(states[0]),
{
    work_bound::<Run0>(states, labels);
}

/// While the run of process p holds the marker and the ledger is enabled, it can always take a step: a Scan before
/// the end, a Final (finishing or refusing on live content) at the end.
pub proof fn theorem_run_can_step(s: S2, p: nat)
    requires inv2(s), s.enabled, s.runs.contains_key(p), s.marker == Some(s.runs[p].t),
    ensures
        s.runs[p].i < s.rec.len() ==> step2(s, L2Label::Scan { p }, scan(s, p)),
        s.runs[p].i == s.rec.len() ==> ({
            let ok = !live_in(s.live, s.runs[p].t);
            step2(s, L2Label::Final { p, t: s.runs[p].t, ok }, final_step(s, p, ok))
        }),
{
    assert(cursor_ok(s, s.runs[p]));
}

} // verus!
