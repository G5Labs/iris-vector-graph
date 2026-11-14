//! Participant contract **Ledger**: the revision history and the redaction bookkeeping kept in `^IVG.Ledger`.
//! (D-9: a target is three predicates. D-9b: each revision's metadata, the idempotency bindings with their move to
//! `idemRedacted`, and the redaction epoch.) It sees only its own state; every operation is one transaction of the
//! ledger component (premise P-C01: a transaction holding `^IVG.Ledger("head")` commits or rolls back as a whole).
//!
//! State (pin 3eaa79cf):
//! - `hist[i][j]`  `^IVG.Ledger("rec", i+1, j+1)` (Ledger.cls:7); `hist.len()` is `^IVG.Ledger("head")`.
//! - `meta[i]`     (D-9b) revision i's row in Graph_KG.ledger_revisions (Ledger.cls:530-560, WriteRevision): `txt`
//!                 its free text (message, source, correlation_id: present, or cleared by ClearRevision,
//!                 LedgerRedact.cls:353-377), `key` its idempotency_key column, and two ghost fields: `okey` the key
//!                 the commit carried, and `named` the keys the changeset's **operations** addressed (the tenant the
//!                 free text may name; premise P-D9b-1).
//! - `idem`        `^IVG.Ledger("idem", key) = seq` (Ledger.cls:10, 525); `idemr` (D-9b) `^IVG.Ledger("idemRedacted",
//!                 sha256(key))` (LedgerRedact.cls:362-363), modelled by the key itself.
//! - `locked`      the head lock `^IVG.Ledger("head")` held *across* steps (only an eraser holds it that way in the
//!                 reviewed design, HD-1201); every ledger transaction needs it free (it takes and releases it).
//! - `enabled`     `^IVG.Ledger("meta","state") = "enabled"`.
//! - `marker`      `^IVG.Ledger("redacting")`, naming its owner target (its target digest, LedgerRedact.cls:323): the
//!                 three predicates of the target (`vocab::Tgt`); BlocksCommit uses its record match.
//! - `mi, mj, mend` the run's cursor and scan bound, kept with the marker. **Reviewed design, not the pin**: each
//!                 batch commits its cursor with its tombstones, so a re-run continues from it (at the pin the cursor
//!                 is process-local and a re-run rescans from the first record, LedgerRedact.cls:213). The bound is
//!                 the head when the run was marked (reviewed element D-2); the progress-only control
//!                 `control_bound_follows_tail` moves it to the head at every commit while a marker exists, as the
//!                 pin's scan does (it scans until `$Order` finds no further revision, LedgerRedact.cls:308-313).
//! - `count`       `^IVG.Ledger("redacting","n","records")` (LedgerRedact.cls:344), and `tally` the records it
//!                 counts (the per-revision tallies `("redacting","revs",seq)`, LedgerRedact.cls:343).
//! - `epoch`       (D-9b, **reviewed design, not the pin**; HD-1401 working answer (b2)) a redaction epoch every
//!                 redaction start (Mark) and finish (Audit) advances; readers compare it before and after a read.
//!
//! Operations are the ledger component's, *as built*: `Commit` counts the changeset's **operations**, not its records
//! (Ledger.cls:489-492), so a changeset whose operations all record nothing still writes a revision row with its
//! metadata and binds its key (Ledger.cls:520-525; F-CS01); `Batch` sets the marker when none exists (the pin's late
//! marker, LedgerRedact.cls:322-324), and its tombstone clears its revision's metadata and moves its key to
//! `idemRedacted` (LedgerRedact.cls:332-377; clearing an already cleared revision changes nothing, which is what the
//! pin's `redactedRev` test, cls:345, skips); `Audit` removes whichever marker exists (LedgerRedact.cls:437). Which of
//! them the reviewed design may use, and when, is the protocols' decision (`protocol_rl`), not this contract's.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;

verus! {

/// One revision's row: free text present, its idempotency_key column, and (ghost) the key it was committed with and
/// the keys its changeset's operations addressed.
pub struct Meta { pub txt: bool, pub key: Option<IKey>, pub okey: Option<IKey>, pub named: Seq<Key> }

pub struct LedgerS {
    pub hist: Seq<Seq<Rec>>,
    pub meta: Seq<Meta>,
    pub idem: Map<IKey, nat>,
    pub idemr: Set<IKey>,
    pub locked: bool,
    pub enabled: bool,
    pub marker: Option<Tgt>,
    pub mi: nat,
    pub mj: nat,
    pub mend: nat,
    pub count: nat,
    pub tally: Seq<Content>,
    pub epoch: nat,
}

pub enum LedgerL {
    /// Graph.KG.Ledger.Commit of a changeset (first attempt): its records `cs` and (ghost) the keys `named` its
    /// operations addressed (a superset of the records' keys: a no-op operation leaves no record at the pin).
    Commit { cs: Seq<Content>, named: Seq<Key>, key: Option<IKey> },
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

/// BlocksCommit (Ledger.cls:514-518, LedgerRedact.cls:258-269): a commit with a record the marker's target **matches**
/// (`Matches`, the record-match predicate) is refused. A commit into the liveness predicate only is not.
pub open spec fn blocks_commit(l: LedgerS, cs: Seq<Content>) -> bool {
    l.marker is Some && touches(cs, l.marker->0.rm)
}

/// A key a first attempt may bind: not bound (a bound key is a replay or an idempotency conflict, Ledger.cls:457-465)
/// and not redacted (idempotency_redacted, Ledger.cls:468-473).
pub open spec fn key_free(l: LedgerS, key: Option<IKey>) -> bool {
    key is None || (!l.idem.contains_key(key->0) && !l.idemr.contains(key->0))
}

pub open spec fn ledger_pre(l: LedgerS, x: LedgerL) -> bool {
    match x {
        // As built: the empty check counts operations (Ledger.cls:489-492); BlocksCommit looks at records only
        // (LedgerRedact.cls:258-269), so a changeset with no record passes it.
        LedgerL::Commit { cs, named, key } => l.enabled && !l.locked && named.len() > 0
            && key_free(l, key) && !blocks_commit(l, cs),
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

/// D-12 progress-only control: the run's scan bound follows the tail (each commit while a marker exists moves it to
/// the new head), as the pin's scan does. Reviewed (D-2): the bound stays the head at marking.
pub open spec fn bound_follows_tail() -> bool { cfg!(feature = "control_bound_follows_tail") }

/// The run's bound after a commit.
pub open spec fn bound_after_commit(l: LedgerS) -> nat {
    if bound_follows_tail() && l.marker is Some { (l.hist.len() + 1) as nat } else { l.mend }
}

/// The metadata row a first attempt writes (WriteRevision, Ledger.cls:530-560).
pub open spec fn commit_meta(named: Seq<Key>, key: Option<IKey>) -> Meta { Meta { txt: true, key, okey: key, named } }

pub open spec fn ledger_commit(l: LedgerS, cs: Seq<Content>, named: Seq<Key>, key: Option<IKey>) -> LedgerS {
    LedgerS {
        hist: l.hist.push(lives(cs)),
        meta: l.meta.push(commit_meta(named, key)),
        idem: match key { Some(k) => l.idem.insert(k, l.hist.len()), None => l.idem },
        mend: bound_after_commit(l),
        ..l
    }
}

pub open spec fn ledger_mark(l: LedgerS, t: Tgt) -> LedgerS {
    LedgerS { marker: Some(t), mi: 0, mj: 0, mend: l.hist.len(), epoch: l.epoch + 1, ..l }
}

/// ClearRevision (LedgerRedact.cls:353-377): free text and idempotency_key cleared.
pub open spec fn cleared(m: Meta) -> Meta { Meta { txt: false, key: None, ..m } }

pub open spec fn ledger_tomb(l: LedgerS, i: nat, j: nat, t: Tgt) -> LedgerS {
    let c = l.hist[i as int][j as int]->Live_0;
    let m = l.meta[i as int];
    LedgerS {
        hist: l.hist.update(i as int, l.hist[i as int].update(j as int, Rec::Tomb(c))),
        meta: l.meta.update(i as int, cleared(m)),
        idem: match m.key { Some(k) => l.idem.remove(k), None => l.idem },
        idemr: match m.key { Some(k) => l.idemr.insert(k), None => l.idemr },
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

/// The redaction revision's row: content-free text ("redaction: n record(s) in m revision(s)", LedgerRedact.cls:434),
/// no key, naming nothing.
pub open spec fn audit_meta() -> Meta { Meta { txt: true, key: None, okey: None, named: Seq::empty() } }

pub open spec fn ledger_audit(l: LedgerS, t: Tgt) -> LedgerS {
    LedgerS {
        hist: if l.marker is Some && l.count > 0 { l.hist.push(seq![Rec::Audit { t, n: l.count }]) } else { l.hist },
        meta: if l.marker is Some && l.count > 0 { l.meta.push(audit_meta()) } else { l.meta },
        epoch: l.epoch + 1,
        marker: None,
        count: 0,
        tally: Seq::empty(),
        ..l
    }
}

pub open spec fn ledger_step(l: LedgerS, x: LedgerL) -> LedgerS {
    match x {
        LedgerL::Commit { cs, named, key } => ledger_commit(l, cs, named, key),
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
        &&& s.meta.len() == 0
        &&& s.idem == Map::<IKey, nat>::empty()
        &&& s.idemr == Set::<IKey>::empty()
        &&& !s.locked
        &&& s.marker is None
        &&& s.count == 0
        &&& s.tally.len() == 0
    }

    open spec fn next(s: LedgerS, x: LedgerL, u: LedgerS) -> bool {
        ledger_pre(s, x) && u == ledger_step(s, x)
    }
}

/// Revision metadata and retry bindings (D-9b), the ledger's own facts:
/// - one row per revision; a bound key names a revision whose row carries it, and a row's key is bound to it;
/// - `idemRedacted` and `idem` are disjoint;
/// - a row with free text carries the key it was committed with; a cleared row carries none, and the key it was
///   committed with is in `idemRedacted` (**INV-retry**, plan.md:25);
/// - **Decision 2** (spec.md:156, ADR-0013:15, HD-1302 "any"): a revision with a tombstone has no free text.
pub open spec fn meta_ok(l: LedgerS) -> bool {
    &&& l.meta.len() == l.hist.len()
    &&& forall|k: IKey| #[trigger] l.idem.contains_key(k) ==> l.idem[k] < l.hist.len() && l.meta[l.idem[k] as int].key == Some(k)
    &&& forall|i: int| 0 <= i < l.meta.len() && (#[trigger] l.meta[i]).key is Some
            ==> l.idem.contains_key(l.meta[i].key->0) && l.idem[l.meta[i].key->0] == i
    &&& forall|k: IKey| #[trigger] l.idemr.contains(k) ==> !l.idem.contains_key(k)
    &&& forall|i: int| 0 <= i < l.meta.len() && (#[trigger] l.meta[i]).txt ==> l.meta[i].key == l.meta[i].okey
    &&& forall|i: int| 0 <= i < l.meta.len() && !(#[trigger] l.meta[i]).txt
            ==> l.meta[i].key is None && (l.meta[i].okey is Some ==> l.idemr.contains(l.meta[i].okey->0))
    &&& forall|i: int, j: int| 0 <= i < l.hist.len() && 0 <= j < l.hist[i].len() && (#[trigger] l.hist[i][j]) is Tomb
            ==> !l.meta[i].txt
}

/// The ledger's own invariant: the counter counts its tally; no marker, no count; metadata and bindings (`meta_ok`).
pub open spec fn ledger_inv(l: LedgerS) -> bool {
    &&& l.count == l.tally.len()
    &&& l.marker is None ==> l.count == 0
    &&& meta_ok(l)
}

pub proof fn lemma_meta_commit(l: LedgerS, cs: Seq<Content>, named: Seq<Key>, key: Option<IKey>)
    requires meta_ok(l), key_free(l, key),
    ensures meta_ok(ledger_commit(l, cs, named, key)),
{
    let u = ledger_commit(l, cs, named, key);
    let n = l.hist.len() as int;
    assert(u.hist.len() == n + 1 && u.meta.len() == n + 1);
    assert forall|i: int| 0 <= i < n implies #[trigger] u.meta[i] == l.meta[i] && u.hist[i] == l.hist[i] by {}
    assert(u.meta[n] == commit_meta(named, key));
    assert(u.hist[n] == lives(cs));
    assert forall|k: IKey| #[trigger] u.idem.contains_key(k) implies u.idem[k] < u.hist.len() && u.meta[u.idem[k] as int].key == Some(k) by {
        if key != Some(k) { assert(l.idem.contains_key(k)); assert(u.meta[l.idem[k] as int] == l.meta[l.idem[k] as int]); }
    }
    assert forall|i: int| 0 <= i < u.meta.len() && (#[trigger] u.meta[i]).key is Some
        implies u.idem.contains_key(u.meta[i].key->0) && u.idem[u.meta[i].key->0] == i by {
        if i < n {
            assert(l.meta[i].key is Some);
            let k = l.meta[i].key->0;
            assert(l.idem.contains_key(k));
            assert(key != Some(k));
        }
    }
    assert forall|k: IKey| #[trigger] u.idemr.contains(k) implies !u.idem.contains_key(k) by {
        assert(l.idemr.contains(k));
    }
    assert forall|i: int| 0 <= i < u.meta.len() && !(#[trigger] u.meta[i]).txt
        implies u.meta[i].key is None && (u.meta[i].okey is Some ==> u.idemr.contains(u.meta[i].okey->0)) by {
        assert(i < n);
        assert(!l.meta[i].txt);
    }
    assert forall|i: int, j: int| 0 <= i < u.hist.len() && 0 <= j < u.hist[i].len() && (#[trigger] u.hist[i][j]) is Tomb
        implies !u.meta[i].txt by {
        if i == n { assert(u.hist[i][j] == Rec::Live(cs[j])); } else { assert(l.hist[i][j] is Tomb); }
    }
}

pub proof fn lemma_meta_tomb(l: LedgerS, i0: nat, j0: nat, t: Tgt)
    requires meta_ok(l), i0 < l.hist.len(), j0 < l.hist[i0 as int].len(), l.hist[i0 as int][j0 as int] is Live,
    ensures meta_ok(ledger_tomb(l, i0, j0, t)),
{
    let u = ledger_tomb(l, i0, j0, t);
    let m = l.meta[i0 as int];
    assert(u.meta.len() == l.meta.len() && u.hist.len() == l.hist.len());
    assert(u.meta[i0 as int] == cleared(m));
    assert forall|i: int| 0 <= i < l.meta.len() && i != i0 implies #[trigger] u.meta[i] == l.meta[i] by {}
    if m.key is Some {
        assert(l.idem.contains_key(m.key->0) && l.idem[m.key->0] == i0);
    }
    assert forall|k: IKey| #[trigger] u.idem.contains_key(k) implies u.idem[k] < u.hist.len() && u.meta[u.idem[k] as int].key == Some(k) by {
        assert(l.idem.contains_key(k));
        assert(m.key != Some(k));
        if l.idem[k] == i0 { assert(l.meta[i0 as int].key == Some(k)); }
    }
    assert forall|i: int| 0 <= i < u.meta.len() && (#[trigger] u.meta[i]).key is Some
        implies u.idem.contains_key(u.meta[i].key->0) && u.idem[u.meta[i].key->0] == i by {
        assert(i != i0);
        assert(u.meta[i] == l.meta[i]);
        let k = l.meta[i].key->0;
        assert(l.idem[k] == i);
        assert(m.key != Some(k));
    }
    assert forall|k: IKey| #[trigger] u.idemr.contains(k) implies !u.idem.contains_key(k) by {
        if m.key != Some(k) { assert(l.idemr.contains(k)); }
    }
    assert forall|i: int| 0 <= i < u.meta.len() && (#[trigger] u.meta[i]).txt implies u.meta[i].key == u.meta[i].okey by {
        assert(i != i0);
        assert(u.meta[i] == l.meta[i]);
    }
    assert forall|i: int| 0 <= i < u.meta.len() && !(#[trigger] u.meta[i]).txt
        implies u.meta[i].key is None && (u.meta[i].okey is Some ==> u.idemr.contains(u.meta[i].okey->0)) by {
        if i == i0 {
            if m.txt { assert(m.key == m.okey); } else { assert(m.okey is Some ==> l.idemr.contains(m.okey->0)); }
        } else {
            assert(u.meta[i] == l.meta[i]);
        }
    }
    assert forall|i: int, j: int| 0 <= i < u.hist.len() && 0 <= j < u.hist[i].len() && (#[trigger] u.hist[i][j]) is Tomb
        implies !u.meta[i].txt by {
        if i == i0 {
        } else {
            assert(u.hist[i] == l.hist[i]);
            assert(l.hist[i][j] is Tomb);
            assert(u.meta[i] == l.meta[i]);
        }
    }
}

pub proof fn lemma_meta_audit(l: LedgerS, t: Tgt)
    requires meta_ok(l),
    ensures meta_ok(ledger_audit(l, t)),
{
    let u = ledger_audit(l, t);
    let n = l.hist.len() as int;
    if l.marker is Some && l.count > 0 {
        assert(u.hist.len() == n + 1 && u.meta.len() == n + 1);
        assert forall|i: int| 0 <= i < n implies #[trigger] u.meta[i] == l.meta[i] && u.hist[i] == l.hist[i] by {}
        assert(u.meta[n] == audit_meta());
        assert(u.hist[n] == seq![Rec::Audit { t, n: l.count }]);
        assert forall|k: IKey| #[trigger] u.idem.contains_key(k) implies u.idem[k] < u.hist.len() && u.meta[u.idem[k] as int].key == Some(k) by {
            assert(u.meta[l.idem[k] as int] == l.meta[l.idem[k] as int]);
        }
        assert forall|i: int| 0 <= i < u.meta.len() && (#[trigger] u.meta[i]).key is Some
            implies u.idem.contains_key(u.meta[i].key->0) && u.idem[u.meta[i].key->0] == i by {
            assert(i < n);
        }
        assert forall|i: int| 0 <= i < u.meta.len() && !(#[trigger] u.meta[i]).txt
            implies u.meta[i].key is None && (u.meta[i].okey is Some ==> u.idemr.contains(u.meta[i].okey->0)) by {
            assert(i < n);
        }
        assert forall|i: int, j: int| 0 <= i < u.hist.len() && 0 <= j < u.hist[i].len() && (#[trigger] u.hist[i][j]) is Tomb
            implies !u.meta[i].txt by {
            if i < n { assert(l.hist[i][j] is Tomb); }
        }
    }
}

pub proof fn lemma_ledger_safe(l: LedgerS, x: LedgerL)
    requires ledger_inv(l), ledger_pre(l, x),
    ensures ledger_inv(ledger_step(l, x)),
{
    match x {
        LedgerL::Commit { cs, named, key } => { lemma_meta_commit(l, cs, named, key); }
        LedgerL::Batch { i, j, t, tomb, ni, nj } => { if tomb { lemma_meta_tomb(l, i, j, t); } }
        LedgerL::Audit { t } => { lemma_meta_audit(l, t); }
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
