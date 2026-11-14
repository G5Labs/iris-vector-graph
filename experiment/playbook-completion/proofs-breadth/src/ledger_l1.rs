//! Module 11 (ledger), L1: the abstract business machine of the revision ledger and the strict-mode guard.
//!
//! One step per user-visible operation (Graph.KG.Ledger Enable / Disable / SetStrict / Commit at pin 3eaa79cf, and a
//! governed engine write that the strict-mode guard either lets land or refuses). Every answer is part of the label,
//! so the contract fixes what the operation answers, not only what it changes.
//!
//! Business rules, each a transition rule or an invariant (`inv1`), traced to the ledger contract:
//! - commit precedence lock -> state -> idempotency -> expected_head -> size -> apply (Ledger.cls:13-14, FR-019);
//! - **a revision exists iff its mutations are recorded** (FR-047, Ledger.cls:388-396): a commit appends the revision
//!   and applies its records in one step; `rows` agree with the replay of the history on every key no write outside
//!   the ledger touched (`drift`);
//! - **an idempotency key binds one fingerprint and replays its revision** (LED-B4.7.5, LED-B10.5): a bound key with
//!   the same fingerprint answers `Replayed(seq)` of its revision and changes nothing; with another fingerprint it is
//!   refused;
//! - **expected-head refusal** (LED-B4.3): an expected head that is not a revision, or not the head, is refused;
//! - **strict mode refuses governed writes** (LED-B11, ledger-api.md:82-92): a governed write lands only when the
//!   ledger is not enabled in strict mode;
//! - the stats row counts exactly the kept revisions (LED-B13.2, LED-B13.4: `ok`).
//!
//! A busy answer (head lock timeout, Ledger.cls:440-444) is always allowed and changes nothing.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

// ------------------------------------------------------------------------------------------------ vocabulary

/// A governed row key (graph tables nodes / rdf_labels / rdf_props / rdf_edges reduced to one key); `edge` marks an
/// edge row, which has a live statement entry `^IVG.Ledger("tuple", s, p, o, graphKey)` (Ledger.cls:8-9).
pub struct K { pub id: int, pub edge: bool }

pub type V = int;
/// An idempotency key (`^IVG.Ledger("idem", key)`).
pub type IKey = int;
/// A changeset fingerprint (changeset.py:365-385).
pub type Fp = int;
/// A revision id (`Graph.KG.Ledger.NewId`, a GUID).
pub type Id = int;

/// One mutation record `^IVG.Ledger("rec", seq, ord)` reduced to the key it touches and its new value (None: delete).
pub struct Op { pub k: K, pub v: Option<V> }

/// `^IVG.Ledger("meta", "state")`: never-enabled, enabled, disabled.
pub enum LState { Never, Enabled, Disabled }

pub enum Reason { NotEnabled, Disabled, IdemConflict, UnknownHead, StaleHead, Empty, Busy }

/// A commit's answer: a new revision, the bound revision of a replayed key, or a refusal.
pub enum COut { Applied(nat), Replayed(nat), Refused(Reason) }

pub struct Rev { pub id: Id, pub recs: Seq<Op>, pub key: Option<IKey> }

pub open spec fn val(m: Map<K, V>, k: K) -> Option<V> {
    if m.contains_key(k) { Some(m[k]) } else { None }
}

pub open spec fn apply_op(m: Map<K, V>, op: Op) -> Map<K, V> {
    match op.v { Some(v) => m.insert(op.k, v), None => m.remove(op.k) }
}

/// Applying records in order (a commit applies its changeset; replay applies each revision).
pub open spec fn apply_recs(m: Map<K, V>, rs: Seq<Op>) -> Map<K, V>
    decreases rs.len()
{
    if rs.len() == 0 { m } else { apply_op(apply_recs(m, rs.drop_last()), rs.last()) }
}

/// Replay of a history from the empty graph (replay.py reconstruct).
pub open spec fn replay(h: Seq<Rev>) -> Map<K, V>
    decreases h.len()
{
    if h.len() == 0 { Map::empty() } else { apply_recs(replay(h.drop_last()), h.last().recs) }
}

/// a and b hold the same value at every key outside d.
pub open spec fn agree(a: Map<K, V>, b: Map<K, V>, d: Set<K>) -> bool {
    forall|k: K| #![trigger val(a, k)] #![trigger val(b, k)] !d.contains(k) ==> val(a, k) == val(b, k)
}

pub open spec fn touches(rs: Seq<Op>, k: K) -> bool {
    exists|j: int| 0 <= j < rs.len() && (#[trigger] rs[j]).k == k
}

pub open spec fn is_rev(h: Seq<Rev>, e: Id) -> bool {
    exists|i: int| 0 <= i < h.len() && (#[trigger] h[i]).id == e
}

// ------------------------------------------------------------------------------------------------ vocabulary lemmas

pub proof fn lemma_val_apply_op(m: Map<K, V>, op: Op, k: K)
    ensures val(apply_op(m, op), k) == if op.k == k { op.v } else { val(m, k) },
{
}

/// The value at k after applying records depends only on the value at k before.
pub proof fn lemma_apply_local(m1: Map<K, V>, m2: Map<K, V>, rs: Seq<Op>, k: K)
    requires val(m1, k) == val(m2, k),
    ensures val(apply_recs(m1, rs), k) == val(apply_recs(m2, rs), k),
    decreases rs.len(),
{
    if rs.len() > 0 {
        lemma_apply_local(m1, m2, rs.drop_last(), k);
        lemma_val_apply_op(apply_recs(m1, rs.drop_last()), rs.last(), k);
        lemma_val_apply_op(apply_recs(m2, rs.drop_last()), rs.last(), k);
    }
}

pub proof fn lemma_agree_apply(a: Map<K, V>, b: Map<K, V>, d: Set<K>, rs: Seq<Op>)
    requires agree(a, b, d),
    ensures agree(apply_recs(a, rs), apply_recs(b, rs), d),
{
    assert forall|k: K| !d.contains(k) implies #[trigger] val(apply_recs(a, rs), k) == val(apply_recs(b, rs), k) by {
        assert(val(a, k) == val(b, k));
        lemma_apply_local(a, b, rs, k);
    }
}

/// Records that do not touch k leave its value.
pub proof fn lemma_apply_untouched(m: Map<K, V>, rs: Seq<Op>, k: K)
    requires !touches(rs, k),
    ensures val(apply_recs(m, rs), k) == val(m, k),
    decreases rs.len(),
{
    if rs.len() > 0 {
        let rd = rs.drop_last();
        assert(!touches(rd, k)) by {
            if touches(rd, k) {
                let j = choose|j: int| 0 <= j < rd.len() && (#[trigger] rd[j]).k == k;
                assert(rs[j] == rd[j]);
            }
        }
        lemma_apply_untouched(m, rd, k);
        assert(rs.last() == rs[rs.len() - 1]);
        lemma_val_apply_op(apply_recs(m, rd), rs.last(), k);
    }
}

/// Maps with the same values everywhere are equal.
pub proof fn lemma_val_ext(a: Map<K, V>, b: Map<K, V>)
    requires forall|k: K| #[trigger] val(a, k) == val(b, k),
    ensures a == b,
{
    assert forall|k: K| #[trigger] a.dom().contains(k) == b.dom().contains(k) by {
        assert(val(a, k) == val(b, k));
    }
    assert(a.dom() =~= b.dom());
    assert forall|k: K| #[trigger] a.dom().contains(k) implies a[k] == b[k] by {
        assert(val(a, k) == val(b, k));
    }
    assert(a =~= b);
}

pub proof fn lemma_replay_push(h: Seq<Rev>, r: Rev)
    ensures replay(h.push(r)) == apply_recs(replay(h), r.recs),
{
    assert(h.push(r).drop_last() =~= h);
    assert(h.push(r).last() == r);
}

// ------------------------------------------------------------------------------------------------ the contract

pub struct S1 {
    pub st: LState,
    pub strict: bool,
    /// revision seq i+1 is hist[i]; genesis is hist[0]
    pub hist: Seq<Rev>,
    /// key -> (seq, fingerprint)
    pub idem: Map<IKey, (nat, Fp)>,
    /// the governed content tables
    pub rows: Map<K, V>,
    /// ghost: keys a write outside the ledger touched (strict off, or before genesis)
    pub drift: Set<K>,
    /// the stats row's commit counter (CommitsOk)
    pub ok: nat,
}

pub enum L1Label {
    /// Graph.KG.Ledger.Enable: genesis (never-enabled), re-enable (disabled), no-op (enabled); or busy.
    Enable { strict: bool, id: Id, recs: Seq<Op>, busy: bool },
    Disable,
    SetStrict { on: bool },
    /// Graph.KG.Ledger.Commit of a changeset with its retry key, fingerprint, expected head and new revision id.
    Commit { recs: Seq<Op>, key: Option<IKey>, fp: Fp, exp: Option<Id>, id: Id, out: COut },
    /// A governed engine write (engine API, Cypher, bulk paths) that lands.
    GovWrite { k: K, v: Option<V> },
    /// A governed engine write that the guard refuses.
    GovRefused,
}

/// The commit's answer, by the precedence state -> idempotency -> expected_head -> size -> apply.
pub open spec fn out1(st: LState, h: Seq<Rev>, idem: Map<IKey, (nat, Fp)>, recs: Seq<Op>, key: Option<IKey>, fp: Fp,
    exp: Option<Id>) -> COut
{
    if st is Never { COut::Refused(Reason::NotEnabled) }
    else if st is Disabled { COut::Refused(Reason::Disabled) }
    else if key is Some && idem.contains_key(key->0) {
        if idem[key->0].1 == fp { COut::Replayed(idem[key->0].0) } else { COut::Refused(Reason::IdemConflict) }
    }
    else if exp is Some && !is_rev(h, exp->0) { COut::Refused(Reason::UnknownHead) }
    else if exp is Some && exp->0 != h.last().id { COut::Refused(Reason::StaleHead) }
    else if recs.len() == 0 { COut::Refused(Reason::Empty) }
    else { COut::Applied((h.len() + 1) as nat) }
}

pub open spec fn commit1(s: S1, recs: Seq<Op>, key: Option<IKey>, fp: Fp, id: Id) -> S1 {
    S1 {
        hist: s.hist.push(Rev { id, recs, key }),
        idem: match key { Some(k) => s.idem.insert(k, ((s.hist.len() + 1) as nat, fp)), None => s.idem },
        rows: apply_recs(s.rows, recs),
        ok: s.ok + 1,
        ..s
    }
}

pub open spec fn strict_on1(s: S1) -> bool { s.st is Enabled && s.strict }

pub struct L1;

impl Contract for L1 {
    type S = S1;
    type L = L1Label;

    open spec fn init(s: S1) -> bool {
        &&& s.st is Never && !s.strict
        &&& s.hist.len() == 0
        &&& s.idem == Map::<IKey, (nat, Fp)>::empty()
        &&& s.rows == Map::<K, V>::empty()
        &&& s.drift == Set::<K>::empty()
        &&& s.ok == 0
    }

    open spec fn next(s: S1, l: L1Label, t: S1) -> bool {
        match l {
            L1Label::Enable { strict, id, recs, busy } =>
                if busy { t == s } else {
                    match s.st {
                        LState::Never => apply_recs(Map::empty(), recs) == s.rows && t == S1 {
                            st: LState::Enabled, strict, hist: seq![Rev { id, recs, key: None }], drift: Set::empty(),
                            ok: s.ok + 1, ..s },
                        LState::Disabled => t == S1 { st: LState::Enabled, strict, ..s },
                        LState::Enabled => t == s,
                    }
                },
            L1Label::Disable => t == if s.st is Enabled { S1 { st: LState::Disabled, ..s } } else { s },
            L1Label::SetStrict { on } => t == if s.st is Never { s } else { S1 { strict: on, ..s } },
            L1Label::Commit { recs, key, fp, exp, id, out } =>
                if out == COut::Refused(Reason::Busy) { t == s } else {
                    &&& out == out1(s.st, s.hist, s.idem, recs, key, fp, exp)
                    &&& out is Applied ==> !is_rev(s.hist, id)
                    &&& t == if out is Applied { commit1(s, recs, key, fp, id) } else { s }
                },
            L1Label::GovWrite { k, v } =>
                !strict_on1(s) && t == S1 { rows: apply_op(s.rows, Op { k, v }), drift: s.drift.insert(k), ..s },
            L1Label::GovRefused => t == s,
        }
    }
}

// ------------------------------------------------------------------------------------------------ the invariant

pub open spec fn ids_unique(h: Seq<Rev>) -> bool {
    forall|i: int, j: int| 0 <= i < h.len() && 0 <= j < h.len() && i != j ==> (#[trigger] h[i]).id != (#[trigger] h[j]).id
}

pub open spec fn idem_ok(s: S1) -> bool {
    &&& forall|k: IKey| #[trigger] s.idem.contains_key(k) ==>
            1 <= s.idem[k].0 <= s.hist.len() && s.hist[s.idem[k].0 - 1].key == Some(k)
    &&& forall|i: int| 0 <= i < s.hist.len() && (#[trigger] s.hist[i]).key is Some ==>
            s.idem.contains_key(s.hist[i].key->0) && s.idem[s.hist[i].key->0].0 == i + 1
}

pub open spec fn inv1(s: S1) -> bool {
    &&& (s.st is Never) == (s.hist.len() == 0)
    &&& s.ok == s.hist.len()
    &&& ids_unique(s.hist)
    &&& idem_ok(s)
    &&& agree(s.rows, replay(s.hist), s.drift)
}

proof fn lemma_commit1_inv(s: S1, recs: Seq<Op>, key: Option<IKey>, fp: Fp, id: Id)
    requires
        inv1(s), !(s.st is Never), !is_rev(s.hist, id), key is None || !s.idem.contains_key(key->0),
    ensures inv1(commit1(s, recs, key, fp, id)),
{
    let t = commit1(s, recs, key, fp, id);
    let r = Rev { id, recs, key };
    let n = s.hist.len();
    assert forall|i: int| 0 <= i < n implies #[trigger] t.hist[i] == s.hist[i] by {}
    assert(t.hist[n as int] == r);
    assert(ids_unique(t.hist)) by {
        assert forall|i: int, j: int| 0 <= i < t.hist.len() && 0 <= j < t.hist.len() && i != j
            implies (#[trigger] t.hist[i]).id != (#[trigger] t.hist[j]).id by {
            if i == n { assert(!(0 <= j < n && s.hist[j].id == id)); }
            else if j == n { assert(!(0 <= i < n && s.hist[i].id == id)); }
        }
    }
    assert(idem_ok(t)) by {
        assert forall|k: IKey| #[trigger] t.idem.contains_key(k) implies
            1 <= t.idem[k].0 <= t.hist.len() && t.hist[t.idem[k].0 - 1].key == Some(k) by {
            if key == Some(k) {} else { assert(s.idem.contains_key(k)); }
        }
        assert forall|i: int| 0 <= i < t.hist.len() && (#[trigger] t.hist[i]).key is Some implies
            t.idem.contains_key(t.hist[i].key->0) && t.idem[t.hist[i].key->0].0 == i + 1 by {
            if i < n {
                assert(t.hist[i] == s.hist[i]);
                let k = s.hist[i].key->0;
                assert(s.idem.contains_key(k));
                if key == Some(k) { assert(s.idem.contains_key(key->0)); }
            }
        }
    }
    lemma_replay_push(s.hist, r);
    lemma_agree_apply(s.rows, replay(s.hist), s.drift, recs);
}

impl SafeContract for L1 {
    open spec fn inv(s: S1) -> bool { inv1(s) }

    proof fn init_safe(s: S1) {
        assert(s.hist =~= Seq::<Rev>::empty());
        assert(replay(s.hist) == Map::<K, V>::empty());
    }

    proof fn step_safe(s: S1, l: L1Label, t: S1) {
        match l {
            L1Label::Enable { strict, id, recs, busy } => {
                if !busy && s.st is Never {
                    let r = Rev { id, recs, key: None };
                    assert(s.hist =~= Seq::<Rev>::empty());
                    assert(t.hist =~= s.hist.push(r));
                    lemma_replay_push(s.hist, r);
                    assert(replay(t.hist) == s.rows);
                    assert(s.idem =~= Map::<IKey, (nat, Fp)>::empty()) by {
                        assert forall|k: IKey| !s.idem.contains_key(k) by {}
                    }
                    assert(idem_ok(t)) by {
                        assert forall|i: int| 0 <= i < t.hist.len() && (#[trigger] t.hist[i]).key is Some implies
                            t.idem.contains_key(t.hist[i].key->0) && t.idem[t.hist[i].key->0].0 == i + 1 by {
                            assert(t.hist[i] == r);
                        }
                    }
                }
            }
            L1Label::Disable => {}
            L1Label::SetStrict { on } => {}
            L1Label::Commit { recs, key, fp, exp, id, out } => {
                if out != COut::Refused(Reason::Busy) && out is Applied {
                    lemma_commit1_inv(s, recs, key, fp, id);
                }
            }
            L1Label::GovWrite { k, v } => {
                let op = Op { k, v };
                assert forall|k2: K| !t.drift.contains(k2) implies #[trigger] val(t.rows, k2) == val(replay(t.hist), k2) by {
                    lemma_val_apply_op(s.rows, op, k2);
                    assert(val(s.rows, k2) == val(replay(s.hist), k2));
                }
            }
            L1Label::GovRefused => {}
        }
    }
}

// ------------------------------------------------------------------------------------------------ business theorems

/// A replayed commit answers the revision its key is bound to, with the same fingerprint, and changes nothing.
pub proof fn theorem_replay_returns_bound_revision(s: S1, recs: Seq<Op>, key: Option<IKey>, fp: Fp, exp: Option<Id>,
    id: Id, seq: nat, t: S1)
    requires
        inv1(s),
        L1::next(s, L1Label::Commit { recs, key, fp, exp, id, out: COut::Replayed(seq) }, t),
    ensures
        t == s,
        key is Some,
        s.idem[key->0] == (seq, fp),
        1 <= seq <= s.hist.len(),
        s.hist[seq - 1].key == key,
{
}

/// A retry key bound to one fingerprint refuses every other fingerprint (or the commit is busy); nothing changes.
pub proof fn theorem_key_binds_one_fingerprint(s: S1, recs: Seq<Op>, k: IKey, fp: Fp, exp: Option<Id>, id: Id,
    out: COut, t: S1)
    requires
        inv1(s), s.st is Enabled, s.idem.contains_key(k), s.idem[k].1 != fp,
        L1::next(s, L1Label::Commit { recs, key: Some(k), fp, exp, id, out }, t),
    ensures
        out == COut::Refused(Reason::IdemConflict) || out == COut::Refused(Reason::Busy),
        t == s,
{
}

/// An expected head that is not the current head is refused (unknown or stale) unless the key replays; nothing changes.
pub proof fn theorem_expected_head_refusal(s: S1, recs: Seq<Op>, key: Option<IKey>, fp: Fp, e: Id, id: Id, out: COut,
    t: S1)
    requires
        inv1(s), s.st is Enabled, key is None || !s.idem.contains_key(key->0), e != s.hist.last().id,
        L1::next(s, L1Label::Commit { recs, key, fp, exp: Some(e), id, out }, t),
    ensures
        out == COut::Refused(Reason::UnknownHead) || out == COut::Refused(Reason::StaleHead)
            || out == COut::Refused(Reason::Busy),
        t == s,
{
}

/// An applied commit appends exactly one revision on top of the head it was given (if any) and binds its key.
pub proof fn theorem_applied_appends(s: S1, recs: Seq<Op>, key: Option<IKey>, fp: Fp, exp: Option<Id>, id: Id,
    seq: nat, t: S1)
    requires
        inv1(s),
        L1::next(s, L1Label::Commit { recs, key, fp, exp, id, out: COut::Applied(seq) }, t),
    ensures
        seq == s.hist.len() + 1,
        t.hist == s.hist.push(Rev { id, recs, key }),
        exp is Some ==> exp->0 == s.hist.last().id,
        key is Some ==> t.idem[key->0] == (seq, fp),
        t.rows == apply_recs(s.rows, recs),
        t.ok == s.ok + 1,
{
}

/// Strict mode refuses governed writes: while the ledger is enabled in strict mode no step lands a governed write,
/// so no step adds a key to the unrecorded writes.
pub proof fn theorem_strict_refuses_governed_writes(s: S1, l: L1Label, t: S1)
    requires inv1(s), strict_on1(s), L1::next(s, l, t),
    ensures !(l is GovWrite), t.drift == s.drift,
{
}

/// A revision exists iff its mutations are recorded: with no write outside the ledger, the content is exactly the
/// replay of the revisions.
pub proof fn theorem_revision_iff_recorded(s: S1)
    requires inv1(s), s.drift == Set::<K>::empty(),
    ensures s.rows == replay(s.hist),
{
    assert forall|k: K| #[trigger] val(s.rows, k) == val(replay(s.hist), k) by {
        assert(!s.drift.contains(k));
    }
    lemma_val_ext(s.rows, replay(s.hist));
}

/// The stats row counts exactly the kept revisions.
pub proof fn theorem_stats_count_kept_revisions(s: S1)
    requires inv1(s),
    ensures s.ok == s.hist.len(),
{
}

} // verus!
