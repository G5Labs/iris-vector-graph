//! Shared vocabulary of the IVG erasure -> redaction -> replay slice: records, replay and tombstoning.
//!
//! Production mapping (pin 3eaa79cf):
//! - `Content` is one mutation record `^IVG.Ledger("rec", seq, ordinal) = $LB(op, kind, id, attr, prior, new, graph,
//!   flags)` (iris_src/src/Graph/KG/Ledger.cls:7). `id` abstracts the replay key the record touches: a node id
//!   (create_node, add_label, set_prop, ...) or a statement id (create_rel, set_qual, delete_rel, ...), as
//!   iris_vector_graph/ledger/replay.py GraphState.apply (lines 170-210) keys them.
//! - `Eff` abstracts what apply does to that key: `Put` (create, set), `Upd` (change only if present: set_prop on a
//!   missing node is skipped, replay.py:181-183), `Del` (delete).
//! - `Rec::Tomb(c)` is a tombstone `$LB("redacted", sha256(CanonicalRecord), flags, op, kind)`
//!   (LedgerRedact.cls:337). The stored value holds only the digest; the model keeps `c` as ghost state so that the
//!   digest's meaning ("the record this replaced") can be stated. `Rec::Audit` is a `redact` record of a revision of
//!   kind redaction (LedgerRedact.cls:427). Both contribute nothing to replay (replay.py:24-26).
//! - `member(t, id)` is target membership, for any predicate t. It is a property of the replay key, not of the record: P-1301 (the
//!   separability premise) says every record that touches one key is in a target or none is. The live scenarios check
//!   it on every observed ledger (native/trace_check.py).
use vstd::prelude::*;

verus! {

pub type Id = int;
pub type Key = int;
/// A redaction target: which replay keys it covers (graph, prefix and endpoint rule of LedgerRedact.Matches,
/// lifted to keys by P-1301). Any predicate: the theorems hold for every target.
pub type Tgt = spec_fn(Id) -> bool;

pub enum Eff { Put(int), Upd(int), Del }

pub struct Content { pub id: Id, pub eff: Eff }

pub enum Rec { Live(Content), Tomb(Content), Audit }

/// Target membership of a replay key (P-1301).
pub open spec fn member(t: Tgt, id: Id) -> bool { t(id) }

pub open spec fn apply(m: Map<Id, int>, c: Content) -> Map<Id, int> {
    match c.eff {
        Eff::Put(v) => m.insert(c.id, v),
        Eff::Upd(v) => if m.contains_key(c.id) { m.insert(c.id, v) } else { m },
        Eff::Del => m.remove(c.id),
    }
}

/// Tombstones and audit records contribute nothing (replay.py `contributes`).
pub open spec fn apply_rec(m: Map<Id, int>, r: Rec) -> Map<Id, int> {
    match r {
        Rec::Live(c) => apply(m, c),
        _ => m,
    }
}

pub open spec fn replay_recs(m: Map<Id, int>, rs: Seq<Rec>) -> Map<Id, int>
    decreases rs.len()
{
    if rs.len() == 0 { m } else { apply_rec(replay_recs(m, rs.drop_last()), rs.last()) }
}

/// Replay of a whole history, revision by revision, from the empty graph (replay.py `reconstruct`).
pub open spec fn replay(h: Seq<Seq<Rec>>) -> Map<Id, int>
    decreases h.len()
{
    if h.len() == 0 { Map::empty() } else { replay_recs(replay(h.drop_last()), h.last()) }
}

/// The part of a state outside target t: what an erasure of t leaves (Eraser.EraseGraph / EraseNodes).
pub open spec fn outside(m: Map<Id, int>, t: Tgt) -> Map<Id, int> {
    Map::new(m.dom().filter(|k: Id| !member(t, k)), |k: Id| m[k])
}

pub open spec fn live_in(m: Map<Id, int>, t: Tgt) -> bool {
    exists|k: Id| #[trigger] m.contains_key(k) && member(t, k)
}

pub open spec fn tomb(r: Rec, t: Tgt) -> Rec {
    match r {
        Rec::Live(c) => if member(t, c.id) { Rec::Tomb(c) } else { r },
        _ => r,
    }
}

pub open spec fn tomb_all(rs: Seq<Rec>, t: Tgt) -> Seq<Rec> {
    rs.map_values(|r: Rec| tomb(r, t))
}

pub open spec fn tomb_hist(h: Seq<Seq<Rec>>, t: Tgt) -> Seq<Seq<Rec>> {
    h.map_values(|rs: Seq<Rec>| tomb_all(rs, t))
}

pub open spec fn is_tomb(r: Rec) -> bool { r is Tomb }

pub open spec fn has_tomb(rs: Seq<Rec>) -> bool {
    exists|j: int| 0 <= j < rs.len() && #[trigger] is_tomb(rs[j])
}

pub open spec fn live_member(r: Rec, t: Tgt) -> bool {
    match r {
        Rec::Live(c) => member(t, c.id),
        _ => false,
    }
}

pub open spec fn touches(cs: Seq<Content>, t: Tgt) -> bool {
    exists|i: int| 0 <= i < cs.len() && member(t, #[trigger] cs[i].id)
}

pub open spec fn lives(cs: Seq<Content>) -> Seq<Rec> {
    cs.map_values(|c: Content| Rec::Live(c))
}

// ------------------------------------------------------------------------------------------------ lemmas

/// One step commutes with erasure of t: applying a record and then removing t equals removing t and then applying
/// the record's tombstoned form.
pub proof fn lemma_apply_outside(m: Map<Id, int>, r: Rec, t: Tgt)
    ensures apply_rec(outside(m, t), tomb(r, t)) =~= outside(apply_rec(m, r), t),
{
    match r {
        Rec::Live(c) => {
            if member(t, c.id) {
                assert(outside(apply(m, c), t) =~= outside(m, t));
            } else {
                match c.eff {
                    Eff::Put(v) => { assert(outside(m, t).insert(c.id, v) =~= outside(m.insert(c.id, v), t)); }
                    Eff::Upd(v) => {
                        if m.contains_key(c.id) {
                            assert(outside(m, t).insert(c.id, v) =~= outside(m.insert(c.id, v), t));
                        }
                    }
                    Eff::Del => { assert(outside(m, t).remove(c.id) =~= outside(m.remove(c.id), t)); }
                }
            }
        }
        _ => {}
    }
}

pub proof fn lemma_tomb_all_drop_last(rs: Seq<Rec>, t: Tgt)
    requires rs.len() > 0,
    ensures
        tomb_all(rs, t).drop_last() =~= tomb_all(rs.drop_last(), t),
        tomb_all(rs, t).last() == tomb(rs.last(), t),
        tomb_all(rs, t).len() == rs.len(),
{
}

/// Replaying the tombstoned records from the erased state gives the erased replay.
pub proof fn lemma_replay_recs_tomb(m: Map<Id, int>, rs: Seq<Rec>, t: Tgt)
    ensures replay_recs(outside(m, t), tomb_all(rs, t)) =~= outside(replay_recs(m, rs), t),
    decreases rs.len(),
{
    if rs.len() > 0 {
        lemma_tomb_all_drop_last(rs, t);
        lemma_replay_recs_tomb(m, rs.drop_last(), t);
        lemma_apply_outside(replay_recs(m, rs.drop_last()), rs.last(), t);
    } else {
        assert(tomb_all(rs, t) =~= Seq::<Rec>::empty());
    }
}

pub proof fn lemma_tomb_hist_drop_last(h: Seq<Seq<Rec>>, t: Tgt)
    requires h.len() > 0,
    ensures
        tomb_hist(h, t).drop_last() =~= tomb_hist(h.drop_last(), t),
        tomb_hist(h, t).last() == tomb_all(h.last(), t),
        tomb_hist(h, t).len() == h.len(),
{
}

/// **Replay after redaction.** Replaying a history whose records of t are tombstones gives the replay of the
/// original history with t removed. Spec 256 US2: replay omits the target's content and nothing else.
pub proof fn lemma_replay_tomb(h: Seq<Seq<Rec>>, t: Tgt)
    ensures replay(tomb_hist(h, t)) =~= outside(replay(h), t),
    decreases h.len(),
{
    if h.len() > 0 {
        lemma_tomb_hist_drop_last(h, t);
        lemma_replay_tomb(h.drop_last(), t);
        lemma_replay_recs_tomb(replay(h.drop_last()), h.last(), t);
    } else {
        assert(outside(Map::<Id, int>::empty(), t) =~= Map::<Id, int>::empty());
        assert(tomb_hist(h, t) =~= Seq::<Seq<Rec>>::empty());
    }
}

pub proof fn lemma_replay_push(h: Seq<Seq<Rec>>, rs: Seq<Rec>)
    ensures replay(h.push(rs)) == replay_recs(replay(h), rs),
{
    assert(h.push(rs).drop_last() =~= h);
}

/// Records that hold no member of t replay the same with or without tombstoning for t.
pub proof fn lemma_tomb_all_noop(rs: Seq<Rec>, t: Tgt)
    requires forall|j: int| 0 <= j < rs.len() ==> !live_member(#[trigger] rs[j], t),
    ensures tomb_all(rs, t) =~= rs,
{
    assert forall|j: int| 0 <= j < rs.len() implies #[trigger] tomb_all(rs, t)[j] == rs[j] by {
        match rs[j] { Rec::Live(c) => { assert(!member(t, c.id)); } _ => {} }
    }
}

pub proof fn lemma_lives_no_member(cs: Seq<Content>, t: Tgt)
    requires !touches(cs, t),
    ensures forall|j: int| 0 <= j < lives(cs).len() ==> !live_member(#[trigger] lives(cs)[j], t),
{
    assert forall|j: int| 0 <= j < lives(cs).len() implies !live_member(#[trigger] lives(cs)[j], t) by {
        assert(!member(t, cs[j].id));
    }
}

/// An erased target stays out of a replay that only adds records outside it.
pub proof fn lemma_outside_idem(m: Map<Id, int>, t: Tgt)
    requires !live_in(m, t),
    ensures outside(m, t) =~= m,
{
    assert forall|k: Id| #[trigger] m.contains_key(k) implies !member(t, k) by {
        if member(t, k) { assert(live_in(m, t)); }
    }
}

// ------------------------------------------------------------------------------------------------ the replay theorems

/// The store and the replay agree (`verify()` reports `equal`; replay.py `verify`, `compare`).
pub open spec fn consistent(h: Seq<Seq<Rec>>, live: Map<Id, int>) -> bool {
    replay(h) =~= live
}

/// The store and the replay agree outside t, and nothing of t is live: the state an erasure of t leaves.
pub open spec fn consistent_except(h: Seq<Seq<Rec>>, live: Map<Id, int>, t: Tgt) -> bool {
    outside(replay(h), t) =~= live && !live_in(live, t)
}

/// Erasure of t from a consistent state leaves it consistent except t.
pub proof fn theorem_erase_leaves_except(h: Seq<Seq<Rec>>, live: Map<Id, int>, t: Tgt)
    requires consistent(h, live),
    ensures consistent_except(h, outside(live, t), t),
{
    assert(!live_in(outside(live, t), t));
}

/// **Erasure alone diverges** (spec 256 plan, "verify() after EraseGraph alone diverges"): when the replay held some
/// key of t, the store after erasure differs from the replay.
pub proof fn theorem_erasure_alone_diverges(h: Seq<Seq<Rec>>, live: Map<Id, int>, t: Tgt, k: Id)
    requires consistent(h, live), member(t, k), live.contains_key(k),
    ensures !consistent(h, outside(live, t)),
{
    assert(!outside(live, t).contains_key(k));
    assert(replay(h).contains_key(k));
}

/// A commit of records outside t keeps the state consistent except t.
pub proof fn theorem_commit_keeps_except(h: Seq<Seq<Rec>>, live: Map<Id, int>, t: Tgt, cs: Seq<Content>)
    requires consistent_except(h, live, t), !touches(cs, t),
    ensures consistent_except(h.push(lives(cs)), replay_recs(live, lives(cs)), t),
{
    lemma_replay_push(h, lives(cs));
    lemma_lives_no_member(cs, t);
    lemma_tomb_all_noop(lives(cs), t);
    lemma_replay_recs_tomb(replay(h), lives(cs), t);
    let m2 = replay_recs(live, lives(cs));
    assert(outside(replay(h.push(lives(cs))), t) =~= m2);
    if live_in(m2, t) {
        let k = choose|k: Id| #[trigger] m2.contains_key(k) && member(t, k);
        assert(outside(replay(h.push(lives(cs))), t).contains_key(k));
    }
}

/// **Redaction restores agreement** (spec 256 FR-007, US2 scenario 1): from the state an erasure of t leaves,
/// tombstoning every record of t makes the replay equal the store.
pub proof fn theorem_redaction_restores(h: Seq<Seq<Rec>>, live: Map<Id, int>, t: Tgt)
    requires consistent_except(h, live, t),
    ensures consistent(tomb_hist(h, t), live),
{
    lemma_replay_tomb(h, t);
}

/// The audit revision that ends a redaction holds no content, so it changes no replay.
pub proof fn theorem_audit_changes_nothing(h: Seq<Seq<Rec>>)
    ensures replay(h.push(seq![Rec::Audit])) =~= replay(h),
{
    let a = seq![Rec::Audit];
    lemma_replay_push(h, a);
    assert(a.drop_last() =~= Seq::<Rec>::empty());
    assert(a.last() == Rec::Audit);
    assert(replay_recs(replay(h), a.drop_last()) == replay(h));
    assert(replay_recs(replay(h), a) == apply_rec(replay_recs(replay(h), a.drop_last()), a.last()));
}

} // verus!
