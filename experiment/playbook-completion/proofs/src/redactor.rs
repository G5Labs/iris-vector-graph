//! Participant contract **Redactor**: the processes running Graph.KG.LedgerRedact.Redact, each with its own cursor
//! (as at the pin: `tSeq`, `tOrd` are local to the call, LedgerRedact.cls:213). It sees only its own state; what the
//! ledger holds reaches it only through the labels the protocol gives it (`Attach { i, j, end }`, `Advance { row_end }`).
//!
//! `procs[p]`: process p inside Redact(t), in phase `Opening` (called; opening checks not yet passed), `Batches`
//! (scanning from its cursor (i, j) to its bound `end`) or `Final` (scan done; final transaction next).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;

verus! {

pub enum Phase { Opening, Batches, Final }

pub struct Proc { pub t: Tgt, pub phase: Phase, pub i: nat, pub j: nat, pub end: nat }

pub struct RedS { pub procs: Map<nat, Proc> }

pub enum RedL {
    /// Process p calls Redact(t).
    Open { p: nat, t: Tgt },
    /// p's opening checks passed: it scans from (i, j) up to revision `end`.
    Attach { p: nat, i: nat, j: nat, end: nat },
    /// One record scanned (or, with `row_end`, the end of a revision).
    Advance { p: nat, row_end: bool },
    /// The cursor reached the bound: p goes to its final transaction.
    ToFinal { p: nat },
    /// p's final transaction ended (finished or refused).
    Finish { p: nat },
    /// p stops or returns early (max_batches, an error, a killed process).
    Stop { p: nat },
}

pub open spec fn has_phase(r: RedS, p: nat, ph: Phase) -> bool {
    r.procs.contains_key(p) && r.procs[p].phase == ph
}

pub open spec fn red_pre(r: RedS, x: RedL) -> bool {
    match x {
        RedL::Open { p, t } => !r.procs.contains_key(p),
        RedL::Attach { p, i, j, end } => has_phase(r, p, Phase::Opening) && i <= end && (i == end ==> j == 0),
        RedL::Advance { p, row_end } => has_phase(r, p, Phase::Batches) && r.procs[p].i < r.procs[p].end,
        RedL::ToFinal { p } => has_phase(r, p, Phase::Batches) && r.procs[p].i == r.procs[p].end,
        RedL::Finish { p } => has_phase(r, p, Phase::Final),
        RedL::Stop { p } => r.procs.contains_key(p),
    }
}

pub open spec fn red_step(r: RedS, x: RedL) -> RedS {
    match x {
        RedL::Open { p, t } => RedS { procs: r.procs.insert(p, Proc { t, phase: Phase::Opening, i: 0, j: 0, end: 0 }) },
        RedL::Attach { p, i, j, end } => RedS { procs: r.procs.insert(p, Proc { phase: Phase::Batches, i, j, end, ..r.procs[p] }) },
        RedL::Advance { p, row_end } => {
            let q = r.procs[p];
            RedS { procs: r.procs.insert(p, if row_end { Proc { i: q.i + 1, j: 0, ..q } } else { Proc { j: q.j + 1, ..q } }) }
        }
        RedL::ToFinal { p } => RedS { procs: r.procs.insert(p, Proc { phase: Phase::Final, ..r.procs[p] }) },
        RedL::Finish { p } => RedS { procs: r.procs.remove(p) },
        RedL::Stop { p } => RedS { procs: r.procs.remove(p) },
    }
}

pub struct Redactor;

impl Contract for Redactor {
    type S = RedS;
    type L = RedL;

    open spec fn init(s: RedS) -> bool { s.procs == Map::<nat, Proc>::empty() }

    open spec fn next(s: RedS, x: RedL, u: RedS) -> bool {
        red_pre(s, x) && u == red_step(s, x)
    }
}

/// The redactor's own invariant: no cursor passes its bound, and a cursor at its bound is at the bound's first record.
pub open spec fn red_inv(r: RedS) -> bool {
    forall|p: nat| #[trigger] r.procs.contains_key(p) ==> r.procs[p].i <= r.procs[p].end
        && (r.procs[p].i == r.procs[p].end ==> r.procs[p].j == 0)
}

pub proof fn lemma_red_safe(r: RedS, x: RedL)
    requires red_inv(r), red_pre(r, x),
    ensures red_inv(red_step(r, x)),
{
    let u = red_step(r, x);
    assert forall|q: nat| #[trigger] u.procs.contains_key(q) implies u.procs[q].i <= u.procs[q].end
        && (u.procs[q].i == u.procs[q].end ==> u.procs[q].j == 0) by {
        if r.procs.contains_key(q) { assert(r.procs[q].i <= r.procs[q].end); }
    }
}

impl SafeContract for Redactor {
    open spec fn inv(s: RedS) -> bool { red_inv(s) }

    proof fn init_safe(s: RedS) {}

    proof fn step_safe(s: RedS, x: RedL, u: RedS) {
        lemma_red_safe(s, x);
    }
}

} // verus!
