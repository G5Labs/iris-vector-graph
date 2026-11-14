//! Shared vocabulary of the erase -> redact -> replay slice: content keys, records, replay, the statement index,
//! and the lemmas every layer uses. Nothing here is a contract; contracts live in `ledger`, `store`, `redactor`,
//! `protocol_rl` (RL) and `biz`.
//!
//! Production mapping (pin 3eaa79cf):
//! - `Key { g, id, edge }`: one row of the content tables keyed by (graph, id) (nodes, rdf_labels, rdf_props,
//!   rdf_edges). `edge` marks an edge row; a live edge also has a live statement entry
//!   `^IVG.Ledger("tuple", s, p, o, graphKey) = stmtId` (Ledger.cls:8-9, "live statements only").
//! - `Content { k, eff }`: one mutation record `^IVG.Ledger("rec", seq, ord)` (Ledger.cls:7) reduced to the key it
//!   touches and its effect (`Put`: create/set, `Del`: delete), as `replay.py` GraphState.apply keys them.
//! - `Rec::Tomb(c)`: the tombstone `$LB("redacted", digest, ...)` (LedgerRedact.cls:331); `c` is kept as ghost so
//!   that "the record this replaced" can be stated. `Rec::Audit { t, n }`: the content-free redaction revision
//!   (LedgerRedact.cls:418-441) naming its target (its `target_sha256`) and its record count.
//! - `Tgt`: a redaction/erasure target, any predicate on keys (graph, prefix and endpoint rules of
//!   LedgerRedact.Matches and Eraser, lifted to keys: premise P-1301 of the original submission).
use vstd::prelude::*;

verus! {

pub struct Key { pub g: int, pub id: int, pub edge: bool }

pub type Tgt = spec_fn(Key) -> bool;

/// An idempotency key (`^IVG.Ledger("idem", key)`, Ledger.cls:10).
pub type IKey = int;

pub enum Eff { Put(int), Del }

pub struct Content { pub k: Key, pub eff: Eff }

pub enum Rec { Live(Content), Tomb(Content), Audit { t: Tgt, n: nat } }

pub open spec fn member(t: Tgt, k: Key) -> bool { t(k) }

pub open spec fn apply_rec(m: Map<Key, int>, r: Rec) -> Map<Key, int> {
    match r {
        Rec::Live(c) => match c.eff {
            Eff::Put(v) => m.insert(c.k, v),
            Eff::Del => m.remove(c.k),
        },
        _ => m,
    }
}

/// Applying records in order (a commit applies its changeset; replay applies each revision).
pub open spec fn replay_recs(m: Map<Key, int>, rs: Seq<Rec>) -> Map<Key, int>
    decreases rs.len()
{
    if rs.len() == 0 { m } else { apply_rec(replay_recs(m, rs.drop_last()), rs.last()) }
}

/// Replay of the whole history from the empty graph (`replay.py` reconstruct). Tombstones and audit records
/// contribute nothing (`replay.py` contributes).
pub open spec fn replay(h: Seq<Seq<Rec>>) -> Map<Key, int>
    decreases h.len()
{
    if h.len() == 0 { Map::empty() } else { replay_recs(replay(h.drop_last()), h.last()) }
}

/// The statement index a record maintains: creating an edge adds its live statement, deleting it removes it
/// (LedgerApply create_rel / delete_rel).
pub open spec fn stmt_rec(st: Set<Key>, r: Rec) -> Set<Key> {
    match r {
        Rec::Live(c) => if c.k.edge {
            match c.eff {
                Eff::Put(v) => st.insert(c.k),
                Eff::Del => st.remove(c.k),
            }
        } else { st },
        _ => st,
    }
}

pub open spec fn stmt_recs(st: Set<Key>, rs: Seq<Rec>) -> Set<Key>
    decreases rs.len()
{
    if rs.len() == 0 { st } else { stmt_rec(stmt_recs(st, rs.drop_last()), rs.last()) }
}

pub open spec fn lives(cs: Seq<Content>) -> Seq<Rec> {
    cs.map_values(|c: Content| Rec::Live(c))
}

/// What an erasure of t leaves of the content tables (Eraser.EraseGraph / EraseIdSet).
pub open spec fn outside(m: Map<Key, int>, t: Tgt) -> Map<Key, int> {
    Map::new(m.dom().filter(|k: Key| !member(t, k)), |k: Key| m[k])
}

pub open spec fn live_in(m: Map<Key, int>, t: Tgt) -> bool {
    exists|k: Key| #[trigger] m.contains_key(k) && member(t, k)
}

pub open spec fn touches(cs: Seq<Content>, t: Tgt) -> bool {
    exists|i: int| 0 <= i < cs.len() && member(t, #[trigger] cs[i].k)
}

pub open spec fn live_member(r: Rec, t: Tgt) -> bool {
    match r {
        Rec::Live(c) => member(t, c.k),
        _ => false,
    }
}

/// A redaction cursor: target, revision `i`, record `j`, and the scan bound `end` (the head when the run was marked).
pub struct Cur { pub t: Tgt, pub i: nat, pub j: nat, pub end: nat }

/// No live record of t anywhere in a history.
pub open spec fn no_member(h: Seq<Seq<Rec>>, t: Tgt) -> bool {
    forall|i: int, j: int| 0 <= i < h.len() && 0 <= j < h[i].len() ==> !live_member(#[trigger] h[i][j], t)
}

// ------------------------------------------------------------------------------------------------ agreement

/// m1 and m2 agree on every key outside d.
pub open spec fn agree(m1: Map<Key, int>, m2: Map<Key, int>, d: spec_fn(Key) -> bool) -> bool {
    forall|k: Key| #![trigger m1.contains_key(k)] #![trigger m2.contains_key(k)]
        !d(k) ==> (m1.contains_key(k) <==> m2.contains_key(k)) && (m1.contains_key(k) ==> m1[k] == m2[k])
}

/// A record whose replay effect, if any, falls inside d.
pub open spec fn affects_only(r: Rec, d: spec_fn(Key) -> bool) -> bool {
    match r {
        Rec::Live(c) => d(c.k),
        _ => true,
    }
}

pub open spec fn rec_eqv(x: Rec, y: Rec, d: spec_fn(Key) -> bool) -> bool {
    x == y || (affects_only(x, d) && affects_only(y, d))
}

pub proof fn lemma_agree_refl(m: Map<Key, int>, d: spec_fn(Key) -> bool)
    ensures agree(m, m, d),
{
}

pub proof fn lemma_agree_symm(m1: Map<Key, int>, m2: Map<Key, int>, d: spec_fn(Key) -> bool)
    requires agree(m1, m2, d),
    ensures agree(m2, m1, d),
{
}

pub proof fn lemma_agree_trans(m1: Map<Key, int>, m2: Map<Key, int>, m3: Map<Key, int>, d: spec_fn(Key) -> bool)
    requires agree(m1, m2, d), agree(m2, m3, d),
    ensures agree(m1, m3, d),
{
    assert forall|k: Key| #![trigger m1.contains_key(k)] #![trigger m3.contains_key(k)]
        !d(k) implies (m1.contains_key(k) <==> m3.contains_key(k)) && (m1.contains_key(k) ==> m1[k] == m3[k]) by {
        assert(m2.contains_key(k) == m1.contains_key(k));
    }
}

pub proof fn lemma_agree_mono(m1: Map<Key, int>, m2: Map<Key, int>, d: spec_fn(Key) -> bool, d2: spec_fn(Key) -> bool)
    requires agree(m1, m2, d), forall|k: Key| #[trigger] d(k) ==> d2(k),
    ensures agree(m1, m2, d2),
{
}

pub proof fn lemma_agree_step(m1: Map<Key, int>, m2: Map<Key, int>, r: Rec, d: spec_fn(Key) -> bool)
    requires agree(m1, m2, d),
    ensures agree(apply_rec(m1, r), apply_rec(m2, r), d),
{
    let a1 = apply_rec(m1, r);
    let a2 = apply_rec(m2, r);
    assert forall|k: Key| #![trigger a1.contains_key(k)] #![trigger a2.contains_key(k)]
        !d(k) implies (a1.contains_key(k) <==> a2.contains_key(k)) && (a1.contains_key(k) ==> a1[k] == a2[k]) by {
        assert(m1.contains_key(k) == m2.contains_key(k));
    }
}

pub proof fn lemma_agree_affects(m: Map<Key, int>, r: Rec, d: spec_fn(Key) -> bool)
    requires affects_only(r, d),
    ensures agree(apply_rec(m, r), m, d),
{
    let a = apply_rec(m, r);
    assert forall|k: Key| #![trigger a.contains_key(k)] #![trigger m.contains_key(k)]
        !d(k) implies (a.contains_key(k) <==> m.contains_key(k)) && (a.contains_key(k) ==> a[k] == m[k]) by {
        match r {
            Rec::Live(c) => { assert(k != c.k); }
            _ => {}
        }
    }
}

/// Replaying record sequences that differ only by records inside d, from states that agree outside d, gives
/// states that agree outside d.
pub proof fn lemma_agree_recs(m1: Map<Key, int>, m2: Map<Key, int>, rs1: Seq<Rec>, rs2: Seq<Rec>, d: spec_fn(Key) -> bool)
    requires
        agree(m1, m2, d),
        rs1.len() == rs2.len(),
        forall|j: int| 0 <= j < rs1.len() ==> rec_eqv(#[trigger] rs1[j], rs2[j], d),
    ensures agree(replay_recs(m1, rs1), replay_recs(m2, rs2), d),
    decreases rs1.len(),
{
    if rs1.len() > 0 {
        let p1 = rs1.drop_last();
        let p2 = rs2.drop_last();
        assert forall|j: int| 0 <= j < p1.len() implies rec_eqv(#[trigger] p1[j], p2[j], d) by {
            assert(p1[j] == rs1[j] && p2[j] == rs2[j]);
        }
        lemma_agree_recs(m1, m2, p1, p2, d);
        let a1 = replay_recs(m1, p1);
        let a2 = replay_recs(m2, p2);
        let x1 = rs1.last();
        let x2 = rs2.last();
        assert(rec_eqv(rs1[rs1.len() - 1], rs2[rs1.len() - 1], d));
        if x1 == x2 {
            lemma_agree_step(a1, a2, x1, d);
        } else {
            lemma_agree_affects(a1, x1, d);
            lemma_agree_affects(a2, x2, d);
            lemma_agree_symm(apply_rec(a2, x2), a2, d);
            lemma_agree_trans(apply_rec(a1, x1), a1, a2, d);
            lemma_agree_trans(apply_rec(a1, x1), a2, apply_rec(a2, x2), d);
        }
    }
}

/// Two histories of the same shape whose records differ only inside d replay to states that agree outside d.
pub proof fn lemma_agree_hist(h1: Seq<Seq<Rec>>, h2: Seq<Seq<Rec>>, d: spec_fn(Key) -> bool)
    requires
        h1.len() == h2.len(),
        forall|i: int| 0 <= i < h1.len() ==> (#[trigger] h1[i]).len() == h2[i].len(),
        forall|i: int, j: int| 0 <= i < h1.len() && 0 <= j < h1[i].len() ==> rec_eqv(#[trigger] h1[i][j], h2[i][j], d),
    ensures agree(replay(h1), replay(h2), d),
    decreases h1.len(),
{
    if h1.len() > 0 {
        let p1 = h1.drop_last();
        let p2 = h2.drop_last();
        assert forall|i: int| 0 <= i < p1.len() implies (#[trigger] p1[i]).len() == p2[i].len() by {
            assert(p1[i] == h1[i] && p2[i] == h2[i]);
        }
        assert forall|i: int, j: int| 0 <= i < p1.len() && 0 <= j < p1[i].len() implies rec_eqv(#[trigger] p1[i][j], p2[i][j], d) by {
            assert(p1[i] == h1[i] && p2[i] == h2[i]);
        }
        lemma_agree_hist(p1, p2, d);
        let l = h1.len() - 1;
        assert forall|j: int| 0 <= j < h1.last().len() implies rec_eqv(#[trigger] h1.last()[j], h2.last()[j], d) by {
            assert(rec_eqv(h1[l][j], h2[l][j], d));
        }
        lemma_agree_recs(replay(p1), replay(p2), h1.last(), h2.last(), d);
    } else {
        lemma_agree_refl(Map::<Key, int>::empty(), d);
    }
}

// ------------------------------------------------------------------------------------------------ replay facts

pub proof fn lemma_replay_push(h: Seq<Seq<Rec>>, rs: Seq<Rec>)
    ensures replay(h.push(rs)) == replay_recs(replay(h), rs),
{
    assert(h.push(rs).drop_last() =~= h);
}

/// The audit revision changes no replay.
pub proof fn lemma_replay_audit(h: Seq<Seq<Rec>>, t: Tgt, n: nat)
    ensures replay(h.push(seq![Rec::Audit { t, n }])) == replay(h),
{
    let a = seq![Rec::Audit { t, n }];
    lemma_replay_push(h, a);
    assert(a.drop_last() =~= Seq::<Rec>::empty());
    assert(replay_recs(replay(h), a.drop_last()) == replay(h));
}

pub proof fn lemma_recs_no_member(m: Map<Key, int>, rs: Seq<Rec>, t: Tgt)
    requires !live_in(m, t), forall|j: int| 0 <= j < rs.len() ==> !live_member(#[trigger] rs[j], t),
    ensures !live_in(replay_recs(m, rs), t),
    decreases rs.len(),
{
    if rs.len() > 0 {
        let p = rs.drop_last();
        assert forall|j: int| 0 <= j < p.len() implies !live_member(#[trigger] p[j], t) by { assert(p[j] == rs[j]); }
        lemma_recs_no_member(m, p, t);
        let a = replay_recs(m, p);
        let x = rs.last();
        assert(!live_member(rs[rs.len() - 1], t));
        let b = apply_rec(a, x);
        if live_in(b, t) {
            let k = choose|k: Key| #[trigger] b.contains_key(k) && member(t, k);
            match x {
                Rec::Live(c) => { if k != c.k { assert(a.contains_key(k)); } }
                _ => { assert(a.contains_key(k)); }
            }
        }
    }
}

/// A history with no live record of t replays to a state with nothing of t.
pub proof fn lemma_replay_no_member(h: Seq<Seq<Rec>>, t: Tgt)
    requires no_member(h, t),
    ensures !live_in(replay(h), t),
    decreases h.len(),
{
    if h.len() > 0 {
        let p = h.drop_last();
        assert forall|i: int, j: int| 0 <= i < p.len() && 0 <= j < p[i].len() implies !live_member(#[trigger] p[i][j], t) by {
            assert(p[i] == h[i]);
        }
        lemma_replay_no_member(p, t);
        let l = h.len() - 1;
        assert forall|j: int| 0 <= j < h.last().len() implies !live_member(#[trigger] h.last()[j], t) by {
            assert(!live_member(h[l][j], t));
        }
        lemma_recs_no_member(replay(p), h.last(), t);
    }
}

pub proof fn lemma_lives_no_member(cs: Seq<Content>, t: Tgt)
    requires !touches(cs, t),
    ensures forall|j: int| 0 <= j < lives(cs).len() ==> !live_member(#[trigger] lives(cs)[j], t),
{
    assert forall|j: int| 0 <= j < lives(cs).len() implies !live_member(#[trigger] lives(cs)[j], t) by {
        assert(!member(t, cs[j].k));
    }
}

pub proof fn lemma_lives_no_tomb(cs: Seq<Content>)
    ensures forall|j: int| 0 <= j < lives(cs).len() ==> (#[trigger] lives(cs)[j]) is Live,
{
}

// ------------------------------------------------------------------------------------------------ statement index

/// Store-local: every statement entry is an edge's, and names a live edge unless an open erasure covers it.
pub open spec fn stmts_ok(rows: Map<Key, int>, st: Set<Key>, e: spec_fn(Key) -> bool) -> bool {
    forall|k: Key| #[trigger] st.contains(k) ==> k.edge && (rows.contains_key(k) || e(k))
}

/// Every live edge outside e has its statement entry.
pub open spec fn edges_ok(rows: Map<Key, int>, st: Set<Key>, e: spec_fn(Key) -> bool) -> bool {
    forall|k: Key| #[trigger] rows.contains_key(k) && k.edge && !e(k) ==> st.contains(k)
}

pub proof fn lemma_stmts_step(rows: Map<Key, int>, st: Set<Key>, r: Rec, e: spec_fn(Key) -> bool)
    ensures
        stmts_ok(rows, st, e) ==> stmts_ok(apply_rec(rows, r), stmt_rec(st, r), e),
        edges_ok(rows, st, e) ==> edges_ok(apply_rec(rows, r), stmt_rec(st, r), e),
{
    let a = apply_rec(rows, r);
    let b = stmt_rec(st, r);
    if stmts_ok(rows, st, e) {
        assert forall|k: Key| #[trigger] b.contains(k) implies k.edge && (a.contains_key(k) || e(k)) by {
            match r {
                Rec::Live(c) => { if k != c.k { assert(st.contains(k)); } }
                _ => {}
            }
        }
    }
    if edges_ok(rows, st, e) {
        assert forall|k: Key| #[trigger] a.contains_key(k) && k.edge && !e(k) implies b.contains(k) by {
            match r {
                Rec::Live(c) => { if k != c.k { assert(rows.contains_key(k)); } }
                _ => {}
            }
        }
    }
}

pub proof fn lemma_stmts_recs(rows: Map<Key, int>, st: Set<Key>, rs: Seq<Rec>, e: spec_fn(Key) -> bool)
    ensures
        stmts_ok(rows, st, e) ==> stmts_ok(replay_recs(rows, rs), stmt_recs(st, rs), e),
        edges_ok(rows, st, e) ==> edges_ok(replay_recs(rows, rs), stmt_recs(st, rs), e),
    decreases rs.len(),
{
    if rs.len() > 0 {
        lemma_stmts_recs(rows, st, rs.drop_last(), e);
        lemma_stmts_step(replay_recs(rows, rs.drop_last()), stmt_recs(st, rs.drop_last()), rs.last(), e);
    }
}

} // verus!
