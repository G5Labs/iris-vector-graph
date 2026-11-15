//! L1: the abstract business machine of erasure, redaction and the ledger records they touch.
//!
//! One step per user-visible command. A refused command is not a step (it changes nothing; SYS-I3). A redaction is
//! two steps: `Begin` makes every record of the target a tombstone at once and marks the run in progress; `Finish`
//! writes the content-free audit revision and clears the mark. Between them, readers see "in progress" (ADR-0013,
//! spec 256 Decision 3), so the L2 batches that do the work in between are stutters.
//!
//! Business rules as invariants (`inv`), each traced in the ontology (13-redaction.md):
//! - shape: every revision keeps its records; each record is its original or that original's tombstone;
//! - isolation: a tombstone exists only for an entity of a target whose redaction began;
//! - Decision 2: a revision with any tombstone has no free text and no retry key;
//! - retry keys: a bound key names an untouched revision with that key; a used key is never free again;
//! - the marker: while a redaction runs, no live record of its target exists, and the audit is due only then.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::model::*;

verus! {

pub struct Rev { pub recs: Seq<Rec>, pub text: bool, pub key: Option<Key> }

pub enum KeyState { Bound(nat), Redacted }

pub struct S {
    pub hist: Seq<Rev>,
    pub live: Map<Id, int>,
    pub keys: Map<Key, KeyState>,
    pub redacting: Option<Tgt>,
    pub audit_due: bool,
    pub enabled: bool,
    /// ghost: every revision's records as committed
    pub orig: Seq<Seq<Rec>>,
    /// ghost: the targets whose redaction began
    pub begun: Set<Tgt>,
}

pub enum Label {
    /// Ledger commit of a changeset (Graph.KG.Ledger.Commit).
    Commit { cs: Seq<Content>, key: Option<Key> },
    /// A write that bypasses the ledger (engine, SQL, Cypher, bulk paths): the environment's freedom.
    Write { id: Id, v: Option<int> },
    /// Erasure of a target (Graph.KG.Eraser.EraseGraph / EraseNodes).
    Erase { t: Tgt },
    /// The redaction takes effect.
    Begin { t: Tgt },
    /// The redaction's final step.
    Finish { t: Tgt },
    /// Ledger enable / disable.
    SetEnabled { on: bool },
}

pub open spec fn recs_of(h: Seq<Rev>) -> Seq<Seq<Rec>> {
    h.map_values(|r: Rev| r.recs)
}

pub open spec fn redact_rev(r: Rev, t: Tgt) -> Rev {
    Rev {
        recs: tomb_all(r.recs, t),
        text: r.text && !has_tomb(tomb_all(r.recs, t)),
        key: if has_tomb(tomb_all(r.recs, t)) { None } else { r.key },
    }
}

pub open spec fn redact_hist(h: Seq<Rev>, t: Tgt) -> Seq<Rev> {
    h.map_values(|r: Rev| redact_rev(r, t))
}

pub open spec fn key_after(ks: KeyState, h: Seq<Rev>) -> KeyState {
    match ks {
        KeyState::Bound(i) => if i < h.len() && has_tomb(h[i as int].recs) { KeyState::Redacted } else { ks },
        KeyState::Redacted => KeyState::Redacted,
    }
}

pub open spec fn redact_keys(keys: Map<Key, KeyState>, h: Seq<Rev>) -> Map<Key, KeyState> {
    Map::new(keys.dom(), |k: Key| key_after(keys[k], h))
}

pub open spec fn any_member(h: Seq<Rev>, t: Tgt) -> bool {
    exists|i: int, j: int| 0 <= i < h.len() && 0 <= j < h[i].recs.len() && #[trigger] live_member(h[i].recs[j], t)
}

pub open spec fn commit_ok(s: S, cs: Seq<Content>, key: Option<Key>) -> bool {
    &&& s.enabled
    &&& cs.len() > 0
    &&& !(s.redacting is Some && touches(cs, s.redacting->0))
    &&& (key is None || !s.keys.contains_key(key->0))
}

pub open spec fn commit(s: S, cs: Seq<Content>, key: Option<Key>) -> S {
    S {
        hist: s.hist.push(Rev { recs: lives(cs), text: true, key }),
        live: replay_recs(s.live, lives(cs)),
        keys: match key { Some(k) => s.keys.insert(k, KeyState::Bound(s.hist.len())), None => s.keys },
        orig: s.orig.push(lives(cs)),
        ..s
    }
}

pub open spec fn begin_ok(s: S, t: Tgt) -> bool {
    s.enabled && s.redacting is None && !live_in(s.live, t)
}

pub open spec fn begin(s: S, t: Tgt) -> S {
    S {
        hist: redact_hist(s.hist, t),
        keys: redact_keys(s.keys, redact_hist(s.hist, t)),
        redacting: Some(t),
        audit_due: any_member(s.hist, t),
        begun: s.begun.insert(t),
        ..s
    }
}

pub open spec fn finish_ok(s: S, t: Tgt) -> bool {
    s.enabled && s.redacting == Some(t) && !live_in(s.live, t)
}

pub open spec fn audit_rev() -> Rev { Rev { recs: seq![Rec::Audit], text: false, key: None } }

pub open spec fn finish(s: S) -> S {
    S {
        hist: if s.audit_due { s.hist.push(audit_rev()) } else { s.hist },
        orig: if s.audit_due { s.orig.push(seq![Rec::Audit]) } else { s.orig },
        redacting: None,
        audit_due: false,
        ..s
    }
}

pub open spec fn write(s: S, id: Id, v: Option<int>) -> S {
    S { live: match v { Some(x) => s.live.insert(id, x), None => s.live.remove(id) }, ..s }
}

pub open spec fn erase(s: S, t: Tgt) -> S { S { live: outside(s.live, t), ..s } }

pub struct L1;

impl Contract for L1 {
    type S = S;
    type L = Label;

    open spec fn init(s: S) -> bool {
        &&& s.hist.len() == 0
        &&& s.orig.len() == 0
        &&& s.live == Map::<Id, int>::empty()
        &&& s.keys == Map::<Key, KeyState>::empty()
        &&& s.redacting is None
        &&& !s.audit_due
        &&& s.begun == Set::<Tgt>::empty()
    }

    open spec fn next(s: S, l: Label, u: S) -> bool {
        match l {
            Label::Commit { cs, key } => commit_ok(s, cs, key) && u == commit(s, cs, key),
            Label::Write { id, v } => u == write(s, id, v),
            Label::Erase { t } => u == erase(s, t),
            Label::Begin { t } => begin_ok(s, t) && u == begin(s, t),
            Label::Finish { t } => finish_ok(s, t) && u == finish(s),
            Label::SetEnabled { on } => u == S { enabled: on, ..s },
        }
    }
}

// ------------------------------------------------------------------------------------------------ the invariant

pub open spec fn rec_ok(o: Rec, r: Rec) -> bool {
    r == o || (o is Live && r == Rec::Tomb(o->Live_0))
}

pub open spec fn begun_member(b: Set<Tgt>, id: Id) -> bool {
    exists|t: Tgt| #[trigger] b.contains(t) && member(t, id)
}

pub open spec fn shape_ok(s: S) -> bool {
    &&& s.orig.len() == s.hist.len()
    &&& forall|i: int| 0 <= i < s.hist.len() ==> (#[trigger] s.hist[i]).recs.len() == s.orig[i].len()
    &&& forall|i: int, j: int| 0 <= i < s.hist.len() && 0 <= j < s.hist[i].recs.len()
            ==> rec_ok(s.orig[i][j], #[trigger] s.hist[i].recs[j])
}

pub open spec fn tombs_ok(s: S) -> bool {
    forall|i: int, j: int| 0 <= i < s.hist.len() && 0 <= j < s.hist[i].recs.len() && #[trigger] is_tomb(s.hist[i].recs[j])
        ==> begun_member(s.begun, s.hist[i].recs[j]->Tomb_0.id)
}

pub open spec fn text_ok(s: S) -> bool {
    forall|i: int| 0 <= i < s.hist.len() && has_tomb((#[trigger] s.hist[i]).recs) ==> !s.hist[i].text && s.hist[i].key is None
}

pub open spec fn keys_ok(s: S) -> bool {
    &&& forall|k: Key| #[trigger] s.keys.contains_key(k) && s.keys[k] is Bound ==> {
            let i = s.keys[k]->Bound_0;
            i < s.hist.len() && !has_tomb(s.hist[i as int].recs) && s.hist[i as int].key == Some(k)
        }
    &&& forall|i: int| 0 <= i < s.hist.len() && (#[trigger] s.hist[i]).key is Some ==>
            s.keys.contains_key(s.hist[i].key->0) && s.keys[s.hist[i].key->0] == KeyState::Bound(i as nat)
}

pub open spec fn marker_ok(s: S) -> bool {
    &&& s.redacting is Some ==> !any_member(s.hist, s.redacting->0) && s.begun.contains(s.redacting->0)
    &&& s.redacting is None ==> !s.audit_due
}

pub open spec fn inv(s: S) -> bool {
    shape_ok(s) && tombs_ok(s) && text_ok(s) && keys_ok(s) && marker_ok(s)
}

// ------------------------------------------------------------------------------------------------ step lemmas

proof fn lemma_push_rev(s: S, rev: Rev, o: Seq<Rec>)
    requires inv(s), rev.recs.len() == o.len(),
        forall|j: int| 0 <= j < rev.recs.len() ==> rec_ok(o[j], #[trigger] rev.recs[j]),
        forall|j: int| 0 <= j < rev.recs.len() ==> !is_tomb(#[trigger] rev.recs[j]),
    ensures ({
        let u = S { hist: s.hist.push(rev), orig: s.orig.push(o), ..s };
        shape_ok(u) && tombs_ok(u) && !has_tomb(u.hist.last().recs)
    }),
{
    let u = S { hist: s.hist.push(rev), orig: s.orig.push(o), ..s };
    assert forall|i: int| 0 <= i < u.hist.len() implies (#[trigger] u.hist[i]).recs.len() == u.orig[i].len() by {
        if i < s.hist.len() { assert(u.hist[i] == s.hist[i]); }
    }
    assert forall|i: int, j: int| 0 <= i < u.hist.len() && 0 <= j < u.hist[i].recs.len()
        implies rec_ok(u.orig[i][j], #[trigger] u.hist[i].recs[j]) by {
        if i < s.hist.len() { assert(u.hist[i] == s.hist[i]); }
    }
    assert forall|i: int, j: int| 0 <= i < u.hist.len() && 0 <= j < u.hist[i].recs.len() && #[trigger] is_tomb(u.hist[i].recs[j])
        implies begun_member(u.begun, u.hist[i].recs[j]->Tomb_0.id) by {
        if i < s.hist.len() { assert(u.hist[i] == s.hist[i]); }
    }
}

proof fn lemma_commit_safe(s: S, cs: Seq<Content>, key: Option<Key>)
    requires inv(s), commit_ok(s, cs, key),
    ensures inv(commit(s, cs, key)),
{
    let u = commit(s, cs, key);
    let rev = Rev { recs: lives(cs), text: true, key };
    lemma_push_rev(s, rev, lives(cs));
    assert(u.hist == s.hist.push(rev));
    assert forall|i: int| 0 <= i < u.hist.len() && has_tomb((#[trigger] u.hist[i]).recs) implies !u.hist[i].text && u.hist[i].key is None by {
        if i < s.hist.len() { assert(u.hist[i] == s.hist[i]); }
    }
    assert forall|k: Key| #[trigger] u.keys.contains_key(k) && u.keys[k] is Bound implies {
            let i = u.keys[k]->Bound_0;
            i < u.hist.len() && !has_tomb(u.hist[i as int].recs) && u.hist[i as int].key == Some(k)
        } by {
        if key == Some(k) {
        } else {
            assert(s.keys.contains_key(k));
            let i = s.keys[k]->Bound_0;
            assert(u.hist[i as int] == s.hist[i as int]);
        }
    }
    assert forall|i: int| 0 <= i < u.hist.len() && (#[trigger] u.hist[i]).key is Some implies
            u.keys.contains_key(u.hist[i].key->0) && u.keys[u.hist[i].key->0] == KeyState::Bound(i as nat) by {
        if i < s.hist.len() {
            assert(u.hist[i] == s.hist[i]);
            let k = s.hist[i].key->0;
            if key == Some(k) { assert(s.keys.contains_key(k)); }
        }
    }
    if s.redacting is Some {
        let t = s.redacting->0;
        if any_member(u.hist, t) {
            let (i, j) = choose|i: int, j: int| 0 <= i < u.hist.len() && 0 <= j < u.hist[i].recs.len() && #[trigger] live_member(u.hist[i].recs[j], t);
            if i < s.hist.len() {
                assert(u.hist[i] == s.hist[i]);
                assert(any_member(s.hist, t));
            } else {
                assert(member(t, cs[j].id));
                assert(touches(cs, t));
            }
        }
    }
}

proof fn lemma_redact_rev_index(h: Seq<Rev>, t: Tgt, i: int, j: int)
    requires 0 <= i < h.len(), 0 <= j < h[i].recs.len(),
    ensures
        redact_hist(h, t).len() == h.len(),
        redact_hist(h, t)[i] == redact_rev(h[i], t),
        redact_hist(h, t)[i].recs.len() == h[i].recs.len(),
        redact_hist(h, t)[i].recs[j] == tomb(h[i].recs[j], t),
{
}

proof fn lemma_begin_safe(s: S, t: Tgt)
    requires inv(s), begin_ok(s, t),
    ensures inv(begin(s, t)),
{
    let u = begin(s, t);
    let h = u.hist;
    assert(h.len() == s.hist.len());
    assert forall|i: int| 0 <= i < h.len() implies (#[trigger] h[i]).recs.len() == u.orig[i].len() by {
        assert(h[i] == redact_rev(s.hist[i], t));
    }
    assert forall|i: int, j: int| 0 <= i < h.len() && 0 <= j < h[i].recs.len() implies rec_ok(u.orig[i][j], #[trigger] h[i].recs[j]) by {
        assert(h[i] == redact_rev(s.hist[i], t));
        lemma_redact_rev_index(s.hist, t, i, j);
        assert(rec_ok(s.orig[i][j], s.hist[i].recs[j]));
    }
    assert forall|i: int, j: int| 0 <= i < h.len() && 0 <= j < h[i].recs.len() && #[trigger] is_tomb(h[i].recs[j])
        implies begun_member(u.begun, h[i].recs[j]->Tomb_0.id) by {
        assert(h[i] == redact_rev(s.hist[i], t));
        lemma_redact_rev_index(s.hist, t, i, j);
        match s.hist[i].recs[j] {
            Rec::Live(c) => { assert(u.begun.contains(t)); }
            Rec::Tomb(c) => {
                assert(is_tomb(s.hist[i].recs[j]));
                let g = choose|g: Tgt| #[trigger] s.begun.contains(g) && member(g, c.id);
                assert(u.begun.contains(g));
            }
            Rec::Audit => {}
        }
    }
    assert forall|i: int| 0 <= i < h.len() && has_tomb((#[trigger] h[i]).recs) implies !h[i].text && h[i].key is None by {
        assert(h[i] == redact_rev(s.hist[i], t));
    }
    assert forall|k: Key| #[trigger] u.keys.contains_key(k) && u.keys[k] is Bound implies {
            let i = u.keys[k]->Bound_0;
            i < h.len() && !has_tomb(h[i as int].recs) && h[i as int].key == Some(k)
        } by {
        assert(s.keys.contains_key(k));
        let i = s.keys[k]->Bound_0;
        assert(u.keys[k] == key_after(s.keys[k], h));
        assert(h[i as int] == redact_rev(s.hist[i as int], t));
    }
    assert forall|i: int| 0 <= i < h.len() && (#[trigger] h[i]).key is Some implies
            u.keys.contains_key(h[i].key->0) && u.keys[h[i].key->0] == KeyState::Bound(i as nat) by {
        assert(h[i] == redact_rev(s.hist[i], t));
        let k = h[i].key->0;
        assert(s.hist[i].key == Some(k));
        assert(u.keys[k] == key_after(s.keys[k], h));
    }
    if any_member(h, t) {
        let (i, j) = choose|i: int, j: int| 0 <= i < h.len() && 0 <= j < h[i].recs.len() && #[trigger] live_member(h[i].recs[j], t);
        lemma_redact_rev_index(s.hist, t, i, j);
    }
}

proof fn lemma_finish_safe(s: S, t: Tgt)
    requires inv(s), finish_ok(s, t),
    ensures inv(finish(s)),
{
    let u = finish(s);
    if s.audit_due {
        let rev = audit_rev();
        assert forall|j: int| 0 <= j < rev.recs.len() implies !is_tomb(#[trigger] rev.recs[j]) by {}
        lemma_push_rev(s, rev, seq![Rec::Audit]);
        assert forall|i: int| 0 <= i < u.hist.len() && has_tomb((#[trigger] u.hist[i]).recs) implies !u.hist[i].text && u.hist[i].key is None by {
            if i < s.hist.len() { assert(u.hist[i] == s.hist[i]); }
        }
        assert forall|k: Key| #[trigger] u.keys.contains_key(k) && u.keys[k] is Bound implies {
                let i = u.keys[k]->Bound_0;
                i < u.hist.len() && !has_tomb(u.hist[i as int].recs) && u.hist[i as int].key == Some(k)
            } by {
            let i = s.keys[k]->Bound_0;
            assert(u.hist[i as int] == s.hist[i as int]);
        }
        assert forall|i: int| 0 <= i < u.hist.len() && (#[trigger] u.hist[i]).key is Some implies
                u.keys.contains_key(u.hist[i].key->0) && u.keys[u.hist[i].key->0] == KeyState::Bound(i as nat) by {
            if i < s.hist.len() { assert(u.hist[i] == s.hist[i]); }
        }
    }
}

pub open spec fn l1_inv(s: S) -> bool { inv(s) }

impl SafeContract for L1 {
    open spec fn inv(s: S) -> bool { inv(s) }

    proof fn init_safe(s: S) {}

    proof fn step_safe(s: S, l: Label, u: S) {
        match l {
            Label::Commit { cs, key } => lemma_commit_safe(s, cs, key),
            Label::Begin { t } => lemma_begin_safe(s, t),
            Label::Finish { t } => lemma_finish_safe(s, t),
            _ => {}
        }
    }
}

// ------------------------------------------------------------------------------------------------ business theorems

/// Redaction never removes the history of live content: every record `Begin` turns into a tombstone belongs to an
/// entity that is not live at that moment (spec 256 FR-005, ADR-0013 "Redaction only follows erasure").
pub proof fn theorem_begin_spares_live(s: S, t: Tgt, i: int, j: int)
    requires begin_ok(s, t), 0 <= i < s.hist.len(), 0 <= j < s.hist[i].recs.len(), live_member(s.hist[i].recs[j], t),
    ensures !s.live.contains_key(s.hist[i].recs[j]->Live_0.id),
{
    let c = s.hist[i].recs[j]->Live_0;
    if s.live.contains_key(c.id) { assert(live_in(s.live, t)); }
}

/// Isolation: a record of an entity outside every redacted target keeps its original bytes (spec 256 SC-004,
/// "other tenants' records retain their bytes").
pub proof fn theorem_isolation(s: S, i: int, j: int)
    requires inv(s), 0 <= i < s.hist.len(), 0 <= j < s.hist[i].recs.len(),
        s.orig[i][j] is Live, !begun_member(s.begun, s.orig[i][j]->Live_0.id),
    ensures s.hist[i].recs[j] == s.orig[i][j],
{
    if is_tomb(s.hist[i].recs[j]) {
        assert(rec_ok(s.orig[i][j], s.hist[i].recs[j]));
    }
}

/// A retry key bound to a revision that has any tombstone is not bound any more, and a commit naming it is refused:
/// a retry cannot replay into, or re-create, a redacted revision (ADR-0013, `idempotency_redacted`).
pub proof fn theorem_retry_refused(s: S, k: Key, cs: Seq<Content>)
    requires inv(s), s.keys.contains_key(k),
    ensures !commit_ok(s, cs, Some(k)),
{
}

pub proof fn lemma_recs_of_redact(h: Seq<Rev>, t: Tgt)
    ensures recs_of(redact_hist(h, t)) =~= tomb_hist(recs_of(h), t),
{
}

pub proof fn lemma_recs_of_push(h: Seq<Rev>, r: Rev)
    ensures recs_of(h.push(r)) =~= recs_of(h).push(r.recs),
{
}

/// **Erase, redact, replay.** From a state whose replay equals the store, erasing t and then redacting it (Begin,
/// Finish) gives a state whose replay equals the store again (spec 256 FR-007). With
/// `model::theorem_erasure_alone_diverges`, this is the before/after oracle of the upstream e2e test, for every
/// history, every target and every separable record layout.
pub proof fn theorem_erase_then_redact(s: S, t: Tgt)
    requires consistent(recs_of(s.hist), s.live), s.enabled, s.redacting is None,
    ensures ({
        let s1 = erase(s, t);
        let s2 = begin(s1, t);
        let s3 = finish(s2);
        begin_ok(s1, t) && finish_ok(s2, t) && consistent(recs_of(s3.hist), s3.live)
    }),
{
    let s1 = erase(s, t);
    theorem_erase_leaves_except(recs_of(s.hist), s.live, t);
    let s2 = begin(s1, t);
    theorem_redaction_restores(recs_of(s1.hist), s1.live, t);
    lemma_recs_of_redact(s1.hist, t);
    let s3 = finish(s2);
    if s2.audit_due {
        lemma_recs_of_push(s2.hist, audit_rev());
        theorem_audit_changes_nothing(recs_of(s2.hist));
    }
}

/// Commits outside the target between the erasure and the redaction keep the theorem: the replay matches the
/// store outside t, and the redaction then restores full agreement.
pub proof fn theorem_commit_between(s: S, t: Tgt, cs: Seq<Content>, key: Option<Key>)
    requires consistent_except(recs_of(s.hist), s.live, t), commit_ok(s, cs, key), !touches(cs, t),
    ensures consistent_except(recs_of(commit(s, cs, key).hist), commit(s, cs, key).live, t),
{
    lemma_recs_of_push(s.hist, Rev { recs: lives(cs), text: true, key });
    theorem_commit_keeps_except(recs_of(s.hist), s.live, t, cs);
}

} // verus!
