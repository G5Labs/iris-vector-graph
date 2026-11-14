//! Shared vocabulary of the erase -> redact -> replay slice (D-9 generalisation of `proofs/src/vocab.rs`): content
//! keys, records, replay, the statement index, **three target predicates**, and the per-key lemmas every layer uses.
//! Nothing here is a contract.
//!
//! Production mapping (pin 3eaa79cf):
//! - `Key { g, id, edge }`: one row of the content tables keyed by (graph, id) (nodes, rdf_labels, rdf_props,
//!   rdf_edges). A live edge recorded by the ledger also has a live statement entry
//!   `^IVG.Ledger("tuple", s, p, o, graphKey)` (Ledger.cls:8-9).
//! - `Content { k, eff }`: one mutation record `^IVG.Ledger("rec", seq, ord)` reduced to the row it describes and its
//!   effect. For a graph-blind node record (graph "", LedgerGenesis.cls:14-20) `k` is the ghost key of the row it
//!   describes (as core model M1 does), so "its content is live" can be stated.
//! - `Dom`: a key predicate. `Tgt { rm, lv, sc }`: a redaction target is **three** predicates, not one (premise P-C03
//!   of `proofs/` is dropped):
//!     `rm` record match   LedgerRedact.Matches (cls:89-112), also used by BlocksCommit (cls:258-269);
//!     `lv` liveness       LedgerRedact.LiveRows (cls:149-178);
//!     `sc` statement cleanup  LedgerRedact.DropStatements (cls:446-471).
//!   F-1304 (Matches on graph-blind node records vs LiveRows of the default graph), F-1305 and F-C1308 (Matches
//!   matches temporal-edge records that LiveRows does not count) are cases where they differ.
//! - An erasure's target is one `Dom` (Eraser's SQL and its EraseLedgerFor on the same graph/id set, premise P-D9-4).
use vstd::prelude::*;

verus! {

pub struct Key { pub g: int, pub id: int, pub edge: bool }

/// A key predicate (the rows, records or statements a rule selects).
pub type Dom = spec_fn(Key) -> bool;

/// A redaction target: record match, liveness, statement cleanup.
pub struct Tgt { pub rm: Dom, pub lv: Dom, pub sc: Dom }

/// An idempotency key (`^IVG.Ledger("idem", key)`, Ledger.cls:10).
pub type IKey = int;

/// A record's effect on its row. `Nop` (D-9b, reviewed design R-1 for F-CS01): the record of an operation that changed
/// nothing (FR-009c: upsert of an existing node, add_label of a present label, set_property with the current value).
/// At the pin such an operation writes **no** record (LedgerApply.cls:229-233, 252-263); in the reviewed design it
/// writes a content-free record carrying the entity's key, so the target predicate can match it and its revision's
/// metadata is cleared by its tombstone. It changes no row, statement entry or provenance.
pub enum Eff { Put(int), Del, Nop }

pub struct Content { pub k: Key, pub eff: Eff }

pub enum Rec { Live(Content), Tomb(Content), Audit { t: Tgt, n: nat } }

pub open spec fn member(d: Dom, k: Key) -> bool { d(k) }

/// **The predicates' side condition** (reviewed design; HD-1303(b1) "graph-blind liveness for every default-graph
/// target" makes the liveness check cover whatever the record match covers; HD-1304 "refuse unattributable targets"):
/// liveness covers record match, and on edges record match and statement cleanup coincide (`lv ⊇ rm`, `rm = sc` on
/// edges). D-9 had `rm ⊇ sc`; D-9b adds `rm ⊆ sc` on edges, so the final DropStatements removes the statement
/// history (live and closed entries) of every edge the run's records describe (SC-001 for `^IVG.Ledger("stmt")`).
/// At the pin both hold for graph and prefix targets on relationships (Matches and DropStatements both use graph plus
/// endpoint prefix, LedgerRedact.cls:93-111, 453-456), up to qualifier records Matches cannot attribute (-1).
/// The reviewed Start refuses a target that does not satisfy it.
pub open spec fn aligned(t: Tgt) -> bool { rm_in_lv(t) && sc_in_rm(t) && rm_in_sc(t) }

/// Statement cleanup covers record match on edges: Final drops the statement history of every edge the run owns.
pub open spec fn rm_in_sc(t: Tgt) -> bool { forall|k: Key| #[trigger] member(t.rm, k) && k.edge ==> member(t.sc, k) }

/// Liveness covers record match: whatever the run may tombstone, the liveness check looks at (F-1304, F-C1308 break it).
pub open spec fn rm_in_lv(t: Tgt) -> bool { forall|k: Key| #[trigger] member(t.rm, k) ==> member(t.lv, k) }

/// Record match covers statement cleanup on edges: Final drops only statements of edges the run owns.
pub open spec fn sc_in_rm(t: Tgt) -> bool { forall|k: Key| #[trigger] member(t.sc, k) && k.edge ==> member(t.rm, k) }

/// Domain d lies inside a.
pub open spec fn covers(a: Dom, d: Dom) -> bool { forall|k: Key| #[trigger] member(d, k) ==> member(a, k) }

pub open spec fn oget(m: Map<Key, int>, k: Key) -> Option<int> { if m.contains_key(k) { Some(m[k]) } else { None } }

pub open spec fn oset(m: Map<Key, int>, k: Key, v: Option<int>) -> Map<Key, int> {
    match v { Some(x) => m.insert(k, x), None => m.remove(k) }
}

pub open spec fn apply_rec(m: Map<Key, int>, r: Rec) -> Map<Key, int> {
    match r {
        Rec::Live(c) => match c.eff {
            Eff::Put(v) => m.insert(c.k, v),
            Eff::Del => m.remove(c.k),
            Eff::Nop => m,
        },
        _ => m,
    }
}

pub open spec fn replay_recs(m: Map<Key, int>, rs: Seq<Rec>) -> Map<Key, int>
    decreases rs.len()
{
    if rs.len() == 0 { m } else { apply_rec(replay_recs(m, rs.drop_last()), rs.last()) }
}

/// Replay of the whole history from the empty graph (`replay.py` reconstruct).
pub open spec fn replay(h: Seq<Seq<Rec>>) -> Map<Key, int>
    decreases h.len()
{
    if h.len() == 0 { Map::empty() } else { replay_recs(replay(h.drop_last()), h.last()) }
}

/// The statement index a record maintains (LedgerApply create_rel / delete_rel).
pub open spec fn stmt_rec(st: Set<Key>, r: Rec) -> Set<Key> {
    match r {
        Rec::Live(c) => if c.k.edge {
            match c.eff {
                Eff::Put(v) => st.insert(c.k),
                Eff::Del => st.remove(c.k),
                Eff::Nop => st,
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

/// Ghost provenance: a ledger write of k makes k's row the ledger's (k leaves the unrecorded set).
pub open spec fn unrec_rec(u: Set<Key>, r: Rec) -> Set<Key> {
    match r {
        Rec::Live(c) => if c.eff is Nop { u } else { u.remove(c.k) },
        _ => u,
    }
}

pub open spec fn unrec_recs(u: Set<Key>, rs: Seq<Rec>) -> Set<Key>
    decreases rs.len()
{
    if rs.len() == 0 { u } else { unrec_rec(unrec_recs(u, rs.drop_last()), rs.last()) }
}

pub open spec fn lives(cs: Seq<Content>) -> Seq<Rec> {
    cs.map_values(|c: Content| Rec::Live(c))
}

/// What an erasure of d leaves of the content tables.
pub open spec fn outside(m: Map<Key, int>, d: Dom) -> Map<Key, int> {
    Map::new(m.dom().filter(|k: Key| !member(d, k)), |k: Key| m[k])
}

/// The rows of d (what an erasure of d deleted, kept for its rollback).
pub open spec fn inside(m: Map<Key, int>, d: Dom) -> Map<Key, int> {
    Map::new(m.dom().filter(|k: Key| member(d, k)), |k: Key| m[k])
}

pub open spec fn live_in(m: Map<Key, int>, d: Dom) -> bool {
    exists|k: Key| #[trigger] m.contains_key(k) && member(d, k)
}

pub open spec fn touches(cs: Seq<Content>, d: Dom) -> bool {
    exists|i: int| 0 <= i < cs.len() && member(d, #[trigger] cs[i].k)
}

pub open spec fn live_member(r: Rec, d: Dom) -> bool {
    match r {
        Rec::Live(c) => member(d, c.k),
        _ => false,
    }
}

/// A redaction cursor over the record-match predicate `t`: revision `i`, record `j`, scan bound `end`.
pub struct Cur { pub t: Dom, pub i: nat, pub j: nat, pub end: nat }

pub open spec fn no_member(h: Seq<Seq<Rec>>, d: Dom) -> bool {
    forall|i: int, j: int| 0 <= i < h.len() && 0 <= j < h[i].len() ==> !live_member(#[trigger] h[i][j], d)
}

/// r is a live record that writes k (a no-op record writes nothing).
pub open spec fn rec_key(r: Rec, k: Key) -> bool {
    match r {
        Rec::Live(c) => c.k == k && !(c.eff is Nop),
        _ => false,
    }
}

/// r is a record (live or tombstoned, any effect) whose content names key k: what the target predicates match.
pub open spec fn rec_names(r: Rec, k: Key) -> bool {
    match r {
        Rec::Live(c) => c.k == k,
        Rec::Tomb(c) => c.k == k,
        _ => false,
    }
}

/// Some record of revision rs names key k.
pub open spec fn rev_names(rs: Seq<Rec>, k: Key) -> bool {
    exists|j: int| 0 <= j < rs.len() && #[trigger] rec_names(rs[j], k)
}

/// The statement **history** a record maintains (`^IVG.Ledger("stmt", id)`, live or closed; Ledger.cls:8): an edge's
/// create opens an entry; its delete closes it (`deletedSeq`), and the closed entry stays until an erasure of its graph
/// (EraseLedgerFor, Eraser.cls:1117-1144) or a redaction's DropStatements (LedgerRedact.cls:444-471) removes it.
pub open spec fn shist_rec(sh: Set<Key>, r: Rec) -> Set<Key> {
    match r {
        Rec::Live(c) => if c.k.edge && c.eff is Put { sh.insert(c.k) } else { sh },
        _ => sh,
    }
}

pub open spec fn shist_recs(sh: Set<Key>, rs: Seq<Rec>) -> Set<Key>
    decreases rs.len()
{
    if rs.len() == 0 { sh } else { shist_rec(shist_recs(sh, rs.drop_last()), rs.last()) }
}

/// Some live record of rs writes key k.
pub open spec fn recs_touch(rs: Seq<Rec>, k: Key) -> bool {
    exists|j: int| 0 <= j < rs.len() && #[trigger] rec_key(rs[j], k)
}

// ------------------------------------------------------------------------------------------------ per-key replay

/// Applying records, at one key: a record that writes k decides the row, its statement entry and its provenance
/// there, whatever the state before; records that do not write k leave all three alone.
pub proof fn lemma_recs_at(m1: Map<Key, int>, m2: Map<Key, int>, st: Set<Key>, u: Set<Key>, rs: Seq<Rec>, k: Key)
    ensures
        recs_touch(rs, k) ==> oget(replay_recs(m1, rs), k) == oget(replay_recs(m2, rs), k),
        recs_touch(rs, k) ==> !unrec_recs(u, rs).contains(k),
        recs_touch(rs, k) && k.edge ==> (stmt_recs(st, rs).contains(k) <==> replay_recs(m1, rs).contains_key(k)),
        !recs_touch(rs, k) ==> oget(replay_recs(m1, rs), k) == oget(m1, k),
        !recs_touch(rs, k) ==> unrec_recs(u, rs).contains(k) == u.contains(k),
        (!recs_touch(rs, k) || !k.edge) ==> stmt_recs(st, rs).contains(k) == st.contains(k),
    decreases rs.len(),
{
    if rs.len() > 0 {
        let p = rs.drop_last();
        let r = rs.last();
        lemma_recs_at(m1, m2, st, u, p, k);
        let last = rs.len() - 1;
        assert(rs[last] == r);
        if recs_touch(p, k) {
            let j = choose|j: int| 0 <= j < p.len() && #[trigger] rec_key(p[j], k);
            assert(rs[j] == p[j]);
            assert(rec_key(rs[j], k));
        }
        if rec_key(r, k) {
            assert(rec_key(rs[last], k));
        }
        if recs_touch(rs, k) && !rec_key(r, k) {
            let j = choose|j: int| 0 <= j < rs.len() && #[trigger] rec_key(rs[j], k);
            assert(j != last);
            assert(p[j] == rs[j]);
            assert(rec_key(p[j], k));
        }
        let a1 = replay_recs(m1, p);
        let a2 = replay_recs(m2, p);
        let s0 = stmt_recs(st, p);
        let u0 = unrec_recs(u, p);
        match r {
            Rec::Live(c) => {
                if c.k == k && !(c.eff is Nop) {
                    match c.eff {
                        Eff::Put(v) => {
                            assert(apply_rec(a1, r).contains_key(k) && apply_rec(a1, r)[k] == v);
                            assert(apply_rec(a2, r).contains_key(k) && apply_rec(a2, r)[k] == v);
                        }
                        Eff::Del => {
                            assert(!apply_rec(a1, r).contains_key(k));
                            assert(!apply_rec(a2, r).contains_key(k));
                        }
                        Eff::Nop => {}
                    }
                    assert(!unrec_rec(u0, r).contains(k));
                } else {
                    assert(oget(apply_rec(a1, r), k) == oget(a1, k));
                    assert(unrec_rec(u0, r).contains(k) == u0.contains(k));
                    assert(stmt_rec(s0, r).contains(k) == s0.contains(k));
                }
            }
            _ => {}
        }
    }
}

pub open spec fn writes_at(c: Content, k: Key) -> bool { c.k == k && !(c.eff is Nop) }

pub proof fn lemma_lives_touch(cs: Seq<Content>, k: Key)
    ensures
        recs_touch(lives(cs), k) ==> exists|i: int| 0 <= i < cs.len() && #[trigger] writes_at(cs[i], k),
        (exists|i: int| 0 <= i < cs.len() && #[trigger] writes_at(cs[i], k)) ==> recs_touch(lives(cs), k),
{
    if recs_touch(lives(cs), k) {
        let j = choose|j: int| 0 <= j < lives(cs).len() && #[trigger] rec_key(lives(cs)[j], k);
        assert(lives(cs)[j] == Rec::Live(cs[j]));
        assert(writes_at(cs[j], k));
    }
    if exists|i: int| 0 <= i < cs.len() && #[trigger] writes_at(cs[i], k) {
        let i = choose|i: int| 0 <= i < cs.len() && #[trigger] writes_at(cs[i], k);
        assert(lives(cs)[i] == Rec::Live(cs[i]));
        assert(rec_key(lives(cs)[i], k));
    }
}

/// Every operation of a changeset left a record: each key the operations name has a record of the changeset
/// (reviewed design R-1; at the pin a no-op operation leaves none, F-CS01).
pub open spec fn ops_recorded(cs: Seq<Content>, named: Seq<Key>) -> bool {
    forall|j: int| 0 <= j < named.len() ==> has_rec_key(cs, #[trigger] named[j])
}

/// Some record of the changeset is about key k.
pub open spec fn has_rec_key(cs: Seq<Content>, k: Key) -> bool { exists|i: int| 0 <= i < cs.len() && (#[trigger] cs[i]).k == k }

/// Applying records, at one key, to the statement history: an edge create opens k's entry; nothing else adds one,
/// and nothing here removes one.
pub proof fn lemma_shist_at(sh: Set<Key>, rs: Seq<Rec>, k: Key)
    ensures
        sh.contains(k) ==> shist_recs(sh, rs).contains(k),
        shist_recs(sh, rs).contains(k) ==> sh.contains(k) || k.edge,
    decreases rs.len(),
{
    if rs.len() > 0 { lemma_shist_at(sh, rs.drop_last(), k); }
}

// ------------------------------------------------------------------------------------------------ agreement

/// m1 and m2 agree on every key outside d.
pub open spec fn agree(m1: Map<Key, int>, m2: Map<Key, int>, d: spec_fn(Key) -> bool) -> bool {
    forall|k: Key| #![trigger m1.contains_key(k)] #![trigger m2.contains_key(k)]
        !d(k) ==> (m1.contains_key(k) <==> m2.contains_key(k)) && (m1.contains_key(k) ==> m1[k] == m2[k])
}

pub open spec fn affects_only(r: Rec, d: spec_fn(Key) -> bool) -> bool {
    match r {
        Rec::Live(c) => d(c.k),
        _ => true,
    }
}

pub open spec fn rec_eqv(x: Rec, y: Rec, d: spec_fn(Key) -> bool) -> bool {
    x == y || (affects_only(x, d) && affects_only(y, d))
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
    }
}

// ------------------------------------------------------------------------------------------------ replay facts

pub proof fn lemma_replay_push(h: Seq<Seq<Rec>>, rs: Seq<Rec>)
    ensures replay(h.push(rs)) == replay_recs(replay(h), rs),
{
    assert(h.push(rs).drop_last() =~= h);
}

pub proof fn lemma_replay_audit(h: Seq<Seq<Rec>>, t: Tgt, n: nat)
    ensures replay(h.push(seq![Rec::Audit { t, n }])) == replay(h),
{
    let a = seq![Rec::Audit { t, n }];
    lemma_replay_push(h, a);
    assert(a.drop_last() =~= Seq::<Rec>::empty());
    assert(replay_recs(replay(h), a.drop_last()) == replay(h));
}

pub proof fn lemma_recs_no_member(m: Map<Key, int>, rs: Seq<Rec>, d: Dom)
    requires !live_in(m, d), forall|j: int| 0 <= j < rs.len() ==> !live_member(#[trigger] rs[j], d),
    ensures !live_in(replay_recs(m, rs), d),
    decreases rs.len(),
{
    if rs.len() > 0 {
        let p = rs.drop_last();
        assert forall|j: int| 0 <= j < p.len() implies !live_member(#[trigger] p[j], d) by { assert(p[j] == rs[j]); }
        lemma_recs_no_member(m, p, d);
        let a = replay_recs(m, p);
        let x = rs.last();
        assert(!live_member(rs[rs.len() - 1], d));
        let b = apply_rec(a, x);
        if live_in(b, d) {
            let k = choose|k: Key| #[trigger] b.contains_key(k) && member(d, k);
            match x {
                Rec::Live(c) => { if k != c.k { assert(a.contains_key(k)); } }
                _ => { assert(a.contains_key(k)); }
            }
        }
    }
}

/// A history with no live record matched by d replays to a state with nothing of d.
pub proof fn lemma_replay_no_member(h: Seq<Seq<Rec>>, d: Dom)
    requires no_member(h, d),
    ensures !live_in(replay(h), d),
    decreases h.len(),
{
    if h.len() > 0 {
        let p = h.drop_last();
        assert forall|i: int, j: int| 0 <= i < p.len() && 0 <= j < p[i].len() implies !live_member(#[trigger] p[i][j], d) by {
            assert(p[i] == h[i]);
        }
        lemma_replay_no_member(p, d);
        let l = h.len() - 1;
        assert forall|j: int| 0 <= j < h.last().len() implies !live_member(#[trigger] h.last()[j], d) by {
            assert(!live_member(h[l][j], d));
        }
        lemma_recs_no_member(replay(p), h.last(), d);
    }
}

pub proof fn lemma_lives_no_member(cs: Seq<Content>, d: Dom)
    requires !touches(cs, d),
    ensures forall|j: int| 0 <= j < lives(cs).len() ==> !live_member(#[trigger] lives(cs)[j], d),
{
    assert forall|j: int| 0 <= j < lives(cs).len() implies !live_member(#[trigger] lives(cs)[j], d) by {
        assert(!member(d, cs[j].k));
    }
}

} // verus!
