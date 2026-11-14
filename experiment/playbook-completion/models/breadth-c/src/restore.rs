//! M5: a replacing restore against the live revision ledger (HD-1801, F-1801, SNP-I3.6, SNP-B3.7; module 18, with
//! the ledger effects of modules 11 and 13 seen at this module's level).
//!
//! Abstract state: revision sequence numbers 1..N. Per seq the record content (absent, live content, tombstone), the
//! LedgerRevision row (its storage global `Graph.KG.LedgerRevisionD`, IdKey Seq: LedgerRevision.cls:44), `head`, the
//! `redactedRev` marks, one idempotency binding (key -> seq), and at most one archive.
//!
//! As built at 3eaa79cf:
//! - commit: seq = head + 1; records, then `LedgerRevision.%Save()` (an insert at IdKey seq: refused when a row with
//!   that seq exists: "revision row save failed", the transaction rolls back), then head and the bindings
//!   (iris_src/src/Graph/KG/Ledger.cls:500-567);
//! - redact: a record becomes a tombstone and `redactedRev(seq)` is set (LedgerRedact.cls);
//! - replacing restore: `erase_all()` kills only `^IVG.Ledger("stmt")` and `("tuple")` (Eraser.cls:806-812), then every
//!   archived global node is set over the live one, nothing killed (iris_vector_graph/_engine/snapshot.py:1554-1588,
//!   1654-1692): live records, revision rows, marks and bindings past the archive survive, `head` takes the archive's
//!   value, and each archived record overwrites a live tombstone of the same seq.
//! Reviewed (decisions.md HD-1801): treat the archive's history as a unit; refuse before any mutation when the live
//! history is not a prefix of the archive's (here: live head beyond the archive's head); keep current redaction
//! obligations (a live tombstone stays a tombstone; its mark stays).
//!
//! Properties:
//! - `one history`: every record, revision row and binding is at or below head (SNP-I3.6);
//! - `a redacted record holds no content`: every marked seq, and every seq a redaction ever emptied (ghost), holds
//!   no live content (ADR-0013, SNP-B3.7);
//! - action property `the ledger only grows`: no step moves head back (SYS-I5);
//! - always possibly: a new commit can succeed (or the ledger is full within the bounds).
use explorer::*;

pub const N: usize = 3;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, ControlReviewedForgetsMarks }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Rec { None, Live, Tomb }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Ledger {
    pub recs: [Rec; N],
    /// LedgerRevision rows present, by seq
    pub revs: [bool; N],
    pub head: u8,
    pub marks: [bool; N],
    /// the idempotency key's bound seq (0: unbound)
    pub idem: u8,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub live: Ledger,
    pub archive: Option<Ledger>,
    pub restores: u8,
    pub refused_commits: u8,
    /// ghost: seqs whose content a redaction removed (the obligation outlives any mark a restore may drop)
    pub redacted_ever: [bool; N],
    /// ghost (witness only): a commit succeeded after a restore
    pub committed_after_restore: bool,
}

#[derive(Clone, Debug)]
pub enum A { Commit { keyed: bool }, Save, Redact { seq: u8 }, Restore }

pub struct M { pub design: Design }

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        let empty = Ledger { recs: [Rec::None; N], revs: [false; N], head: 0, marks: [false; N], idem: 0 };
        vec![S { live: empty, archive: None, restores: 0, refused_commits: 0, redacted_ever: [false; N],
                 committed_after_restore: false }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![A::Commit { keyed: false }, A::Commit { keyed: true }, A::Save, A::Restore];
        for seq in 1..=N as u8 { v.push(A::Redact { seq }); }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut t = s.clone();
        let l = &mut t.live;
        match *a {
            A::Commit { keyed } => {
                let seq = s.live.head + 1;
                if seq as usize > N { return None; }
                if keyed && s.live.idem != 0 {
                    return None; // a retry with the bound key replays; not a new revision
                }
                let i = seq as usize - 1;
                if s.live.revs[i] {
                    // LedgerRevision IdKey conflict: "revision row save failed", TROLLBACK 1: nothing changes
                    if s.refused_commits >= 1 { return None; }
                    t.refused_commits += 1;
                    return Some(t);
                }
                l.recs[i] = Rec::Live;
                l.revs[i] = true;
                l.head = seq;
                if keyed { l.idem = seq; }
                if s.restores > 0 { t.committed_after_restore = true; }
            }
            A::Save => {
                if s.archive.is_some() { return None; }
                t.archive = Some(s.live);
            }
            A::Redact { seq } => {
                let i = seq as usize - 1;
                if s.live.recs[i] != Rec::Live { return None; }
                l.recs[i] = Rec::Tomb;
                l.marks[i] = true;
                t.redacted_ever[i] = true;
            }
            A::Restore => {
                let Some(ar) = s.archive else { return None };
                if s.restores >= 1 { return None; }
                t.restores += 1;
                let l = &mut t.live;
                match self.design {
                    Design::AsBuilt => {
                        for i in 0..N {
                            if ar.recs[i] != Rec::None { l.recs[i] = ar.recs[i]; }
                            if ar.revs[i] { l.revs[i] = true; }
                            if ar.marks[i] { l.marks[i] = true; }
                        }
                        l.head = ar.head;
                        if ar.idem != 0 { l.idem = ar.idem; }
                    }
                    Design::Reviewed | Design::ControlReviewedForgetsMarks => {
                        // refuse before mutation unless the live history is a prefix of the archive's
                        let prefix = s.live.head <= ar.head
                            && (0..s.live.head as usize).all(|i| s.live.revs[i] == ar.revs[i]
                                && (s.live.recs[i] == ar.recs[i]
                                    || (s.live.recs[i] == Rec::Tomb && ar.recs[i] == Rec::Live)));
                        if !prefix { return Some(S { restores: s.restores + 1, ..s.clone() }); }
                        let keep_marks = self.design == Design::Reviewed;
                        let live_before = s.live;
                        *l = ar;
                        if keep_marks {
                            for i in 0..N {
                                if live_before.marks[i] { l.marks[i] = true; l.recs[i] = Rec::Tomb; }
                            }
                        }
                    }
                }
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant("one history", |s: &S| {
                let l = &s.live;
                (0..N).all(|i| (i as u8) < l.head || (l.recs[i] == Rec::None && !l.revs[i])) && l.idem <= l.head
            }),
            invariant("a redacted record holds no content", |s: &S|
                (0..N).all(|i| !(s.live.marks[i] || s.redacted_ever[i]) || s.live.recs[i] != Rec::Live)),
        ]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![action_property("the ledger only grows", |a: &S, _: &A, b: &S| b.live.head >= a.live.head)]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("a new commit can succeed", |s: &S| {
            let seq = s.live.head as usize + 1;
            seq > N || !s.live.revs[seq - 1]
        })]
    }
}

/// Keep only the named properties of a model (each as-built check targets one property, so a counterexample is
/// attributed to one finding).
pub struct Witness { pub m: M }
impl Model for Witness {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { self.m.init_states() }
    fn actions(&self, s: &S) -> Vec<A> { self.m.actions(s) }
    fn next(&self, s: &S, a: &A) -> Option<S> { self.m.next(s, a) }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant("a restore of a newer archive succeeds and the ledger commits on", |s: &S|
            !(s.restores == 1 && s.committed_after_restore && s.archive.map_or(false, |a| a.head >= 1)))]
    }
}

pub fn show(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    for (i, (a, s)) in c.steps.iter().enumerate() {
        let l = &s.live;
        out += &format!("  {:>2}. {:<22} head={} recs={:?} revs={:?} marks={:?} idem={} archive_head={:?} refused_commits={}\n",
                        i + 1, format!("{:?}", a), l.head, l.recs, l.revs, l.marks, l.idem,
                        s.archive.map(|x| x.head), s.refused_commits);
    }
    out
}
