//! Participant contract **Ledger**: the revision history and the redaction bookkeeping kept in `^IVG.Ledger`.
//! It sees only its own state; every operation is one transaction of the ledger component (premise P-C01: a
//! transaction holding `^IVG.Ledger("head")` commits or rolls back as a whole).
//!
//! State (pin 3eaa79cf):
//! - `hist[i][j]`  `^IVG.Ledger("rec", i+1, j+1)` (Ledger.cls:7); `hist.len()` is `^IVG.Ledger("head")`.
//! - `idem`        `^IVG.Ledger("idem", key) = seq` (Ledger.cls:10).
//! - `locked`      the head lock `^IVG.Ledger("head")` held *across* steps (only an eraser holds it that way in the
//!                 reviewed design, HD-1201); every ledger transaction needs it free (it takes and releases it).
//! - `enabled`     `^IVG.Ledger("meta","state") = "enabled"`.
//! - `marker`      `^IVG.Ledger("redacting")`, naming its owner target (its target digest, LedgerRedact.cls:323).
//! - `mi, mj, mend` the run's cursor and scan bound, kept with the marker. **Reviewed design, not the pin**: each
//!                 batch commits its cursor with its tombstones, so a re-run continues from it (at the pin the cursor
//!                 is process-local and a re-run rescans from the first record, LedgerRedact.cls:213).
//! - `count`       `^IVG.Ledger("redacting","n","records")` (LedgerRedact.cls:344), and `tally` the records it
//!                 counts (the per-revision tallies `("redacting","revs",seq)`, LedgerRedact.cls:343).
//!
//! Operations are the ledger component's, *as built*: `Batch` sets the marker when none exists (the pin's late
//! marker, LedgerRedact.cls:322-324) and `Audit` removes whichever marker exists (LedgerRedact.cls:437). Which of
//! them the reviewed design may use, and when, is the protocols' decision (`protocol_rl`), not this contract's.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;

verus! {

pub struct LedgerS {
    pub hist: Seq<Seq<Rec>>,
    pub idem: Map<IKey, nat>,
    pub locked: bool,
    pub enabled: bool,
    pub marker: Option<Tgt>,
    pub mi: nat,
    pub mj: nat,
    pub mend: nat,
    pub count: nat,
    pub tally: Seq<Content>,
}

pub enum LedgerL {
    /// Graph.KG.Ledger.Commit of a changeset (first attempt).
    Commit { cs: Seq<Content>, key: Option<IKey> },
    /// Graph.KG.Ledger.Commit with a bound idempotency key: answered from the stored revision (Ledger.cls:457-462).
    Replay { key: IKey },
    /// Take / release the head lock across steps.
    Lock,
    Unlock,
    SetEnabled { on: bool },
    /// Write the marker for target t, with the run's cursor at the first record and its bound at the head
    /// (the reviewed design's opening step; HD-1301).
    Mark { t: Tgt },
    /// One record of a batch (LedgerRedact.BatchInLock / Tombstone, cls:302-345): tombstone record (i, j) and count it
    /// when `tomb`; then write the run's cursor (ni, nj).
    Batch { i: nat, j: nat, t: Tgt, tomb: bool, ni: nat, nj: nat },
    /// Move the run's cursor back to the first record.
    Rewind,
    /// The final transaction's ledger part: the audit revision when something was counted, then no marker
    /// (LedgerRedact.FinalInLock, cls:409-441).
    Audit { t: Tgt },
}

/// BlocksCommit (Ledger.cls:514-518): a commit touching the marker's target is refused.
pub open spec fn blocks_commit(l: LedgerS, cs: Seq<Content>) -> bool {
    l.marker is Some && touches(cs, l.marker->0)
}

pub open spec fn ledger_pre(l: LedgerS, x: LedgerL) -> bool {
    match x {
        LedgerL::Commit { cs, key } => l.enabled && !l.locked && cs.len() > 0
            && (key is None || !l.idem.contains_key(key->0)) && !blocks_commit(l, cs),
        LedgerL::Replay { key } => l.enabled && !l.locked && l.idem.contains_key(key),
        LedgerL::Lock => !l.locked,
        LedgerL::Unlock => l.locked,
        LedgerL::SetEnabled { on } => true,
        LedgerL::Mark { t } => l.enabled && !l.locked && l.marker is None,
        LedgerL::Batch { i, j, t, tomb, ni, nj } => l.enabled && !l.locked
            && (tomb ==> i < l.hist.len() && j < l.hist[i as int].len() && l.hist[i as int][j as int] is Live),
        LedgerL::Rewind => l.enabled && !l.locked,
        LedgerL::Audit { t } => l.enabled && !l.locked,
    }
}

pub open spec fn ledger_commit(l: LedgerS, cs: Seq<Content>, key: Option<IKey>) -> LedgerS {
    LedgerS {
        hist: l.hist.push(lives(cs)),
        idem: match key { Some(k) => l.idem.insert(k, l.hist.len()), None => l.idem },
        ..l
    }
}

pub open spec fn ledger_mark(l: LedgerS, t: Tgt) -> LedgerS {
    LedgerS { marker: Some(t), mi: 0, mj: 0, mend: l.hist.len(), ..l }
}

pub open spec fn ledger_tomb(l: LedgerS, i: nat, j: nat, t: Tgt) -> LedgerS {
    let c = l.hist[i as int][j as int]->Live_0;
    LedgerS {
        hist: l.hist.update(i as int, l.hist[i as int].update(j as int, Rec::Tomb(c))),
        count: l.count + 1,
        tally: l.tally.push(c),
        marker: if l.marker is None { Some(t) } else { l.marker },
        ..l
    }
}

pub open spec fn ledger_batch(l: LedgerS, i: nat, j: nat, t: Tgt, tomb: bool, ni: nat, nj: nat) -> LedgerS {
    let l1 = if tomb { ledger_tomb(l, i, j, t) } else { l };
    LedgerS { mi: ni, mj: nj, ..l1 }
}

pub open spec fn ledger_audit(l: LedgerS, t: Tgt) -> LedgerS {
    LedgerS {
        hist: if l.marker is Some && l.count > 0 { l.hist.push(seq![Rec::Audit { t, n: l.count }]) } else { l.hist },
        marker: None,
        count: 0,
        tally: Seq::empty(),
        ..l
    }
}

pub open spec fn ledger_step(l: LedgerS, x: LedgerL) -> LedgerS {
    match x {
        LedgerL::Commit { cs, key } => ledger_commit(l, cs, key),
        LedgerL::Replay { key } => l,
        LedgerL::Lock => LedgerS { locked: true, ..l },
        LedgerL::Unlock => LedgerS { locked: false, ..l },
        LedgerL::SetEnabled { on } => LedgerS { enabled: on, ..l },
        LedgerL::Mark { t } => ledger_mark(l, t),
        LedgerL::Batch { i, j, t, tomb, ni, nj } => ledger_batch(l, i, j, t, tomb, ni, nj),
        LedgerL::Rewind => LedgerS { mi: 0, mj: 0, ..l },
        LedgerL::Audit { t } => ledger_audit(l, t),
    }
}

pub struct Ledger;

impl Contract for Ledger {
    type S = LedgerS;
    type L = LedgerL;

    open spec fn init(s: LedgerS) -> bool {
        &&& s.hist.len() == 0
        &&& s.idem == Map::<IKey, nat>::empty()
        &&& !s.locked
        &&& s.marker is None
        &&& s.count == 0
        &&& s.tally.len() == 0
    }

    open spec fn next(s: LedgerS, x: LedgerL, u: LedgerS) -> bool {
        ledger_pre(s, x) && u == ledger_step(s, x)
    }
}

/// The ledger's own invariant: the counter counts its tally; no marker, no count; a bound key names a revision.
pub open spec fn ledger_inv(l: LedgerS) -> bool {
    &&& l.count == l.tally.len()
    &&& l.marker is None ==> l.count == 0
    &&& forall|k: IKey| #[trigger] l.idem.contains_key(k) ==> l.idem[k] < l.hist.len()
}

pub proof fn lemma_ledger_safe(l: LedgerS, x: LedgerL)
    requires ledger_inv(l), ledger_pre(l, x),
    ensures ledger_inv(ledger_step(l, x)),
{
    let u = ledger_step(l, x);
    match x {
        LedgerL::Commit { cs, key } => {
            assert forall|k: IKey| #[trigger] u.idem.contains_key(k) implies u.idem[k] < u.hist.len() by {
                if key != Some(k) { assert(l.idem.contains_key(k)); }
            }
        }
        LedgerL::Audit { t } => {
            assert forall|k: IKey| #[trigger] u.idem.contains_key(k) implies u.idem[k] < u.hist.len() by {
                assert(l.idem.contains_key(k));
            }
        }
        _ => {}
    }
}

impl SafeContract for Ledger {
    open spec fn inv(s: LedgerS) -> bool { ledger_inv(s) }

    proof fn init_safe(s: LedgerS) {}

    proof fn step_safe(s: LedgerS, x: LedgerL, u: LedgerS) {
        lemma_ledger_safe(s, x);
    }
}

} // verus!
