// IVG temporal edges — write modes and statistics, the marked structural row, the temporal-only
// opt-out, and the ledger temporal op at its commit boundary. Verus model (initial uplift, 2026-11-13).
//
// Product baseline 3eaa79cf. This file is a model and a transcription; it does not verify the
// product's ObjectScript or Python bodies. Bindings (L3) are named in the comments and in NOTES.md.
//
// Layers
//   L1  rules from spec 254 (FR-001..FR-004, Decisions 1-2), ADR-0009 (+ spec 254 amendment),
//       ADR-0015, ADR-0010 / USER_GUIDE "Writes inside your transaction", commit 43efd473 (decided
//       2026-10-19), spec 224 (Changeset.create_temporal_edge docstring).
//   L2  the as-built mechanism of Graph.KG.TemporalIndex (WriteStores, BulkInsertCounts,
//       DeleteTemporalEdge, RemoveTemporalRow, RebuildBucketAggregate, PurgeRawBefore/RetireExpired),
//       Graph.KG.Adjacency (AssertTemporalRow, RetractTemporalRow(s)), Graph.KG.TemporalPolicy,
//       Graph.KG.Ledger.Commit / LedgerApply, iris_sql_store.bulk_write_temporal_edges, ledger/replay.verify.
//   Proofs connect L2 to L1 and name every premise; witnesses are concrete traces where L2 violates L1.
//
// Run:  $VERUS_BIN temporal.rs --crate-type=lib --num-threads 4 --triggers-mode silent
use vstd::prelude::*;

verus! {

// ============================================================================ keys

/// ^KG("tout", g, ts, s, p, o): g is GraphKey.ForIndex (0 = default graph, else the name). Ids and
/// predicates are strings in the product; any injective encoding to int is faithful here.
pub struct Coord {
    pub g: int,
    pub ts: int,
    pub s: int,
    pub p: int,
    pub o: int,
}

/// A structural triple in one graph: Graph_KG.rdf_edges (s, p, o_id, graph_id) — one row per triple
/// (the multigraph edge key is not represented).
pub struct Triple {
    pub g: int,
    pub s: int,
    pub p: int,
    pub o: int,
}

/// ^KG("tagg", g, bucket, s, p, "count"|"sum")
pub struct AKey {
    pub g: int,
    pub b: int,
    pub s: int,
    pub p: int,
}

/// ^KG("bucket", g, bucket, s) — per source, every predicate
pub struct BKey {
    pub g: int,
    pub b: int,
    pub s: int,
}

/// TemporalIndex: Parameter BUCKET = 300; tBucket = pTs \ tBucketDiv (seconds precision).
pub open spec fn bkt(ts: int) -> int {
    ts / 300
}

pub open spec fn akey(c: Coord) -> AKey {
    AKey { g: c.g, b: bkt(c.ts), s: c.s, p: c.p }
}

pub open spec fn bkey(c: Coord) -> BKey {
    BKey { g: c.g, b: bkt(c.ts), s: c.s }
}

pub open spec fn tri(c: Coord) -> Triple {
    Triple { g: c.g, s: c.s, p: c.p, o: c.o }
}

/// $Get(counter, 0): GetAggregate reads +$Get(^KG("tagg",...,"count"), 0); GetVelocity $Get(..., 0).
pub open spec fn get0<K>(m: Map<K, int>, k: K) -> int {
    if m.contains_key(k) { m[k] } else { 0 }
}

// ============================================================================ raw-store statistics (L1 side)

/// The raw edges of one aggregate key.
pub open spec fn aset(tout: Map<Coord, int>, k: AKey) -> Set<Coord> {
    tout.dom().filter(|c: Coord| akey(c) == k)
}

/// The raw edges of one bucket-count key.
pub open spec fn bset(tout: Map<Coord, int>, k: BKey) -> Set<Coord> {
    tout.dom().filter(|c: Coord| bkey(c) == k)
}

/// Sum of the weights w[c] over a finite set of coordinates.
pub open spec fn wsum(cs: Set<Coord>, w: Map<Coord, int>) -> int
    decreases cs.len(),
{
    if cs.len() == 0 {
        0
    } else {
        let c = cs.choose();
        w[c] + wsum(cs.remove(c), w)
    }
}

pub proof fn lemma_wsum_remove(cs: Set<Coord>, w: Map<Coord, int>, x: Coord)
    requires
        cs.contains(x),
    ensures
        wsum(cs, w) == w[x] + wsum(cs.remove(x), w),
    decreases cs.len(),
{
    assert(cs.len() > 0);
    let c = cs.choose();
    if c != x {
        let r = cs.remove(c);
        assert(r.contains(x));
        lemma_wsum_remove(r, w, x);
        let rx = cs.remove(x);
        assert(rx.contains(c));
        lemma_wsum_remove(rx, w, c);
        assert(r.remove(x) =~= rx.remove(c));
    }
}

pub proof fn lemma_wsum_insert(cs: Set<Coord>, w: Map<Coord, int>, x: Coord)
    requires
        !cs.contains(x),
    ensures
        wsum(cs.insert(x), w) == wsum(cs, w) + w[x],
{
    lemma_wsum_remove(cs.insert(x), w, x);
    assert(cs.insert(x).remove(x) =~= cs);
}

pub proof fn lemma_wsum_frame(cs: Set<Coord>, w1: Map<Coord, int>, w2: Map<Coord, int>)
    requires
        forall|c: Coord| cs.contains(c) ==> w1[c] == w2[c],
    ensures
        wsum(cs, w1) == wsum(cs, w2),
    decreases cs.len(),
{
    if cs.len() > 0 {
        let c = cs.choose();
        lemma_wsum_frame(cs.remove(c), w1, w2);
    }
}

pub proof fn lemma_wsum_empty(cs: Set<Coord>, w: Map<Coord, int>)
    requires
        cs.len() == 0,
    ensures
        wsum(cs, w) == 0,
{
}


// ============================================================================ state (L2)

/// The journaled stores at a TSTART (what TROLLBACK restores). The $Increment counters are carried
/// so that the variant "counters are rolled back" (not IRIS behaviour) can restore them. The three journals
/// hold, per counter node Set or Killed in this level, its before-image at the level's first such op: TROLLBACK
/// applies the before-images of journaled ops in reverse, so such a node returns to that value, while a node only
/// ever $Increment'ed in the level keeps its current value (premise P-INCR).
pub struct Snap {
    pub tout: Map<Coord, int>,
    pub eprop: Map<Coord, int>,
    pub rows: Map<Triple, bool>,
    pub nodes: Set<(int, int)>,
    pub optout: Set<(int, int)>,
    pub gov_nodes: Set<int>,
    pub gov_rels: Set<Triple>,
    pub purged: Set<Coord>,
    pub bucket: Map<BKey, int>,
    pub cnt: Map<AKey, int>,
    pub sum: Map<AKey, int>,
    pub jbucket: Map<BKey, Option<int>>,
    pub jcnt: Map<AKey, Option<int>>,
    pub jsum: Map<AKey, Option<int>>,
}

/// A purge or temporal delete in flight in one process: its decision (RetireExpired's candidate set and survivor
/// walk, or DeleteTemporalEdge's HasTemporalEdge test) taken on an earlier state, its effects still to come.
/// Process-private (^||IVG.TPurge, locals): not journaled.
pub struct Plan {
    pub doomed: Set<Triple>,
    /// the raw kill loop still to run: (graph, lo, hi); None for a delete
    pub kill: Option<(int, int, int)>,
    pub retracted: bool,
}

pub struct St {
    /// ^KG("tout", g, ts, s, p, o) = weight  (^KG("tin") mirrors it unless suppressed: not represented)
    pub tout: Map<Coord, int>,
    /// ^KG("edgeprop", g, ts, s, p, o, key): present with an abstract payload
    pub eprop: Map<Coord, int>,
    /// ^KG("bucket", g, b, s)          — $Increment only (WriteStores :102), -1 / Kill on delete (:357-358)
    pub bucket: Map<BKey, int>,
    /// ^KG("tagg", g, b, s, p, "count") — $Increment (:117); Set by RebuildBucketAggregate
    pub cnt: Map<AKey, int>,
    /// ^KG("tagg", g, b, s, p, "sum")   — $Increment by w (:118); Set by RebuildBucketAggregate
    pub sum: Map<AKey, int>,
    /// Graph_KG.rdf_edges: true = qualifiers carry {"temporal": true} (ADR-0009 marker); false = explicit row.
    /// With the adjacency functional index (spec 252) ^KG("out", g, s, p, o) exists iff a row exists (premise P-IDX).
    pub rows: Map<Triple, bool>,
    /// Graph_KG.nodes (graph key, node id)
    pub nodes: Set<(int, int)>,
    /// ^IVG.TemporalStructural(g, p) = 0: the temporal-only registry (ADR-0015)
    pub optout: Set<(int, int)>,
    /// ledger replay (Graph.KG.Ledger records → replay.GraphState): governed node ids (graph-blind, as
    /// replay.read_canonical keys nodes by node_id) and governed relationships
    pub gov_nodes: Set<int>,
    pub gov_rels: Set<Triple>,
    /// ghost: every coordinate a purge removed (its bucket's aggregate "describes the past", ADR-0009:49)
    pub purged: Set<Coord>,
    /// the TSTART stack of the process ($TLEVEL = txn.len()); each entry the journaled stores at that TSTART
    pub txn: Seq<Snap>,
    /// purges and deletes in flight, by process (the phased actions; see "races")
    pub plans: Map<int, Plan>,
}

pub open spec fn snap(s: St) -> Snap {
    Snap {
        tout: s.tout, eprop: s.eprop, rows: s.rows, nodes: s.nodes, optout: s.optout,
        gov_nodes: s.gov_nodes, gov_rels: s.gov_rels, purged: s.purged,
        bucket: s.bucket, cnt: s.cnt, sum: s.sum,
        jbucket: Map::empty(), jcnt: Map::empty(), jsum: Map::empty(),
    }
}

/// Two snapshots that agree on every store (journals aside).
pub open spec fn snap_frame(a: Snap, b: Snap) -> bool {
    &&& a.tout == b.tout && a.eprop == b.eprop && a.rows == b.rows && a.nodes == b.nodes && a.optout == b.optout
    &&& a.gov_nodes == b.gov_nodes && a.gov_rels == b.gov_rels && a.purged == b.purged
    &&& a.bucket == b.bucket && a.cnt == b.cnt && a.sum == b.sum
}

pub open spec fn txn_frame(a: Seq<Snap>, b: Seq<Snap>) -> bool {
    a.len() == b.len() && forall|i: int| 0 <= i < a.len() ==> snap_frame(#[trigger] a[i], b[i])
}

pub open spec fn at<K>(m: Map<K, int>, k: K) -> Option<int> {
    if m.contains_key(k) { Some(m[k]) } else { None }
}

pub open spec fn jnote<K>(j: Map<K, Option<int>>, k: K, before: Option<int>) -> Map<K, Option<int>> {
    if j.contains_key(k) { j } else { j.insert(k, before) }
}

/// A journaled Set/Kill of ^KG("bucket", ...) inside a transaction: record the before-image in the top level.
pub open spec fn journal_bucket(s: St, k: BKey, before: Option<int>) -> St {
    if s.txn.len() == 0 {
        s
    } else {
        let i = s.txn.len() - 1;
        let top = s.txn[i];
        St { txn: s.txn.update(i, Snap { jbucket: jnote(top.jbucket, k, before), ..top }), ..s }
    }
}

/// A journaled Set/Kill of ^KG("tagg", g, b, s, p) (RebuildBucketAggregate) inside a transaction.
pub open spec fn journal_agg(s: St, k: AKey) -> St {
    if s.txn.len() == 0 {
        s
    } else {
        let i = s.txn.len() - 1;
        let top = s.txn[i];
        St { txn: s.txn.update(i, Snap { jcnt: jnote(top.jcnt, k, at(s.cnt, k)), jsum: jnote(top.jsum, k, at(s.sum, k)), ..top }), ..s }
    }
}

/// TROLLBACK of a counter store: journaled nodes return to their before-image (None = undefined); the others
/// keep their current value, $Increments included.
pub open spec fn restore_j<K>(cur: Map<K, int>, j: Map<K, Option<int>>) -> Map<K, int> {
    Map::new(cur.dom().filter(|k: K| !j.contains_key(k)).union(j.dom().filter(|k: K| j[k] is Some)),
        |k: K| if j.contains_key(k) { j[k]->Some_0 } else { cur[k] })
}

pub proof fn lemma_restore_empty<K>(cur: Map<K, int>)
    ensures
        restore_j(cur, Map::<K, Option<int>>::empty()) == cur,
{
    assert(restore_j(cur, Map::<K, Option<int>>::empty()) =~= cur);
}

/// Variant switches. as_built() is the product at the pin; the others are the repairs that the
/// findings propose, used to show which mechanism a violation depends on.
pub struct Variant {
    /// S2: the structural step (AssertTemporalRow) runs before the first Set, so a throw leaves no temporal store
    pub assert_first: bool,
    /// counters are taken back by TROLLBACK (IRIS does not do this for $Increment: ADR-0010, USER_GUIDE)
    pub incr_undone: bool,
    /// Q1 option (b): "update" at occupied coordinates rebuilds the bucket's tagg and leaves ^KG("bucket")
    pub update_rebuilds: bool,
    /// Q4 repair: opting a predicate back in is refused while a marked row of it has no timestamp
    pub optin_guard: bool,
    /// bug-tmp-011 repair: the retraction re-tests "no surviving timestamp" when it runs, and the raw kill loop
    /// re-retracts the triples it left without a timestamp — each atomically with respect to a writer of the same
    /// triple (premise P-LOCK: a per-triple lock that AssertTemporalRow also takes; proposed, not in the product)
    pub race_recheck: bool,
}

pub open spec fn as_built() -> Variant {
    Variant { assert_first: false, incr_undone: false, update_rebuilds: false, optin_guard: false, race_recheck: false }
}

pub open spec fn repaired() -> Variant {
    Variant { assert_first: true, incr_undone: true, update_rebuilds: true, optin_guard: true, race_recheck: true }
}

pub open spec fn raced() -> Variant {
    Variant { race_recheck: true, ..as_built() }
}

// ============================================================================ WriteStores (L2)

pub enum Mode {
    Insert,
    Skip,
    Update,
}

/// Where Adjacency.AssertTemporalRow throws (a SQL error: privilege, lock timeout, -119 under a
/// concurrent writer, three -121 retries, a value over the column's length): before its node INSERTs,
/// or at the edge INSERT after both node rows were written (no transaction of its own).
pub enum Fail {
    No,
    BeforeNodes,
    AtEdge,
}

pub enum WRes {
    Written,
    Skipped,
    Collided,
    /// $$$ThrowOnError(AssertTemporalRow(...)) at WriteStores :111
    Threw,
}

/// TemporalPolicy.IsStructuralKey(g, p) = '$Data(^IVG.TemporalStructural(g, p))
pub open spec fn structural(s: St, g: int, p: int) -> bool {
    !s.optout.contains((g, p))
}

/// The structural step will throw: only when there is no row, because with pTrustIndex=1
/// AssertTemporalRow returns before any SQL when ^KG("out") holds the triple (Adjacency.cls:577-579).
pub open spec fn row_step_fails(s: St, c: Coord, f: Fail) -> bool {
    structural(s, c.g, c.p) && f != Fail::No && !s.rows.contains_key(tri(c))
}

/// Adjacency.AssertTemporalRow(pGKey, s, p, o, w, pTrustIndex=1) when it succeeds: both endpoint
/// nodes in the edge's graph (INSERT ... WHERE NOT EXISTS) then the marked row.
pub open spec fn assert_row(s: St, t: Triple) -> St {
    if s.rows.contains_key(t) {
        s
    } else {
        St { nodes: s.nodes.insert((t.g, t.s)).insert((t.g, t.o)), rows: s.rows.insert(t, true), ..s }
    }
}

/// What a throwing AssertTemporalRow leaves.
pub open spec fn assert_row_partial(s: St, t: Triple, f: Fail) -> St {
    if f == Fail::AtEdge {
        St { nodes: s.nodes.insert((t.g, t.s)).insert((t.g, t.o)), ..s }
    } else {
        s
    }
}

/// WriteStores :82-85 — the guard. True when the write stops here without changing any store.
pub open spec fn guard_stops(s: St, c: Coord, mode: Mode) -> bool {
    mode != Mode::Update && s.tout.contains_key(c)
}

/// The raw part, :82-83 and :95-102: "update" kills edgeprop; tout (and tin, tlast) Set; bucket $Increment.
pub open spec fn raw_part(s: St, c: Coord, w: int, mode: Mode, v: Variant) -> St {
    let occupied = s.tout.contains_key(c);
    let bk = bkey(c);
    St {
        tout: s.tout.insert(c, w),
        eprop: if mode == Mode::Update { s.eprop.remove(c) } else { s.eprop },
        bucket: if v.update_rebuilds && occupied { s.bucket } else { s.bucket.insert(bk, get0(s.bucket, bk) + 1) },
        ..s
    }
}

/// RebuildBucketAggregate(g, b, s, p): count/sum Set from the surviving raw edges, or the node killed.
pub open spec fn rebuild(s: St, k: AKey) -> St {
    let n = aset(s.tout, k).len();
    if n == 0 {
        St { cnt: s.cnt.remove(k), sum: s.sum.remove(k), ..s }
    } else {
        St { cnt: s.cnt.insert(k, n as int), sum: s.sum.insert(k, wsum(aset(s.tout, k), s.tout)), ..s }
    }
}

/// The aggregate part, :117-131: tagg count $Increment, sum $Increment by w (min/max/HLL not represented),
/// then edgeprop.
pub open spec fn agg_part(s: St, c: Coord, w: int, attrs: Option<int>, occupied: bool, v: Variant) -> St {
    let k = akey(c);
    let s1 = if v.update_rebuilds && occupied {
        rebuild(s, k)
    } else {
        St { cnt: s.cnt.insert(k, get0(s.cnt, k) + 1), sum: s.sum.insert(k, get0(s.sum, k) + w), ..s }
    };
    match attrs {
        Some(a) => St { eprop: s1.eprop.insert(c, a), ..s1 },
        None => s1,
    }
}

/// Everything WriteStores does once its guard has let the write through (the "effect"). Kept apart from
/// the guard because nothing locks between them (no Lock in WriteStores): two writers can both pass the guard.
pub open spec fn write_effect(s: St, c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail, v: Variant) -> (St, WRes) {
    let t = tri(c);
    let occupied = s.tout.contains_key(c);
    let st = structural(s, c.g, c.p);
    let fails = row_step_fails(s, c, f);
    if v.assert_first {
        // repaired order: the structural step before any temporal Set
        if fails {
            (assert_row_partial(s, t, f), WRes::Threw)
        } else {
            let s1 = if st { assert_row(s, t) } else { s };
            (agg_part(raw_part(s1, c, w, mode, v), c, w, attrs, occupied, v), WRes::Written)
        }
    } else {
        let s1 = raw_part(s, c, w, mode, v);
        if fails {
            (assert_row_partial(s1, t, f), WRes::Threw)
        } else {
            let s2 = if st { assert_row(s1, t) } else { s1 };
            (agg_part(s2, c, w, attrs, occupied, v), WRes::Written)
        }
    }
}

/// TemporalIndex.WriteStores(pGKey, pTs, pS, pP, pO, pW, pSuppR, pMode, pAttrs) — TemporalIndex.cls:80-133.
pub open spec fn write_stores(s: St, c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail, v: Variant) -> (St, WRes) {
    if guard_stops(s, c, mode) {
        (s, if mode == Mode::Skip { WRes::Skipped } else { WRes::Collided })
    } else {
        write_effect(s, c, w, attrs, mode, f, v)
    }
}

// ============================================================================ delete, purge, policy (L2)

pub open spec fn has_ts(tout: Map<Coord, int>, t: Triple) -> bool {
    exists|c: Coord| #[trigger] tout.contains_key(c) && tri(c) == t
}

/// Adjacency.RetractTemporalRow: the triple's rows are deleted only while IsTemporalMarked.
pub open spec fn retract(s: St, t: Triple) -> St {
    if s.rows.contains_key(t) && s.rows[t] { St { rows: s.rows.remove(t), ..s } } else { s }
}

/// RemoveTemporalRow (TemporalIndex.cls:348-360): kill tout/tin/edgeprop (journaled), bucket $Increment(-1)
/// (:357, not journaled) and Kill at <= 0 (:358, journaled: its before-image is the decremented value),
/// then RebuildBucketAggregate(g, b, s, p) (:359; its Sets/Kill journaled).
pub open spec fn remove_raw(s: St, c: Coord) -> St {
    let bk = bkey(c);
    let nb = get0(s.bucket, bk) - 1;
    let s1 = St { tout: s.tout.remove(c), eprop: s.eprop.remove(c), bucket: s.bucket.insert(bk, nb), ..s };
    if nb <= 0 {
        let s2 = journal_bucket(s1, bk, Some(nb));
        St { bucket: s2.bucket.remove(bk), ..s2 }
    } else {
        s1
    }
}

pub open spec fn remove_temporal_row(s: St, c: Coord) -> St {
    rebuild(journal_agg(remove_raw(s, c), akey(c)), akey(c))
}

/// DeleteTemporalEdge (TemporalIndex.cls:325-345), indexed install: does not consult the registry.
pub open spec fn delete_temporal(s: St, c: Coord) -> (St, bool) {
    if !s.tout.contains_key(c) {
        (s, false)
    } else {
        let s1 = remove_temporal_row(s, c);
        let s2 = if !has_ts(s1.tout, tri(c)) { retract(s1, tri(c)) } else { s1 };
        (s2, true)
    }
}

pub open spec fn in_range(c: Coord, g: int, lo: int, hi: int) -> bool {
    c.g == g && lo <= c.ts && c.ts < hi
}

/// RetireExpired's candidate set ^||IVG.TPurge: the distinct (s, p, o) of the range, structural predicates only (:966).
pub open spec fn purge_candidate(s: St, t: Triple, g: int, lo: int, hi: int) -> bool {
    t.g == g && structural(s, g, t.p)
        && exists|c: Coord| #[trigger] s.tout.contains_key(c) && in_range(c, g, lo, hi) && tri(c) == t
}

pub open spec fn tout_after_purge(s: St, g: int, lo: int, hi: int) -> Map<Coord, int> {
    Map::new(s.tout.dom().filter(|c: Coord| !in_range(c, g, lo, hi)), |c: Coord| s.tout[c])
}

/// RetractTemporalRows over the candidates no surviving timestamp holds (marked rows only).
pub open spec fn purge_doomed(s: St, t: Triple, g: int, lo: int, hi: int) -> bool {
    purge_candidate(s, t, g, lo, hi) && !has_ts(tout_after_purge(s, g, lo, hi), t)
        && s.rows.contains_key(t) && s.rows[t]
}

/// PurgeRawBefore(g, tsEnd=hi, tsStart=lo, retire=0) — TemporalIndex.cls:866-920: RetireExpired (rows first),
/// then the raw kill loop (tout, tin, edgeprop); tagg/bucket stay. `stop_after_rows`: the purge fails
/// between the two (no transaction: the retract statements autocommit).
pub open spec fn purge(s: St, g: int, lo: int, hi: int, stop_after_rows: bool) -> St {
    let rows1 = Map::new(s.rows.dom().filter(|t: Triple| !purge_doomed(s, t, g, lo, hi)), |t: Triple| s.rows[t]);
    if stop_after_rows {
        St { rows: rows1, ..s }
    } else {
        St { rows: rows1, ..kill_raw(s, g, lo, hi) }
    }
}

/// PurgeRawBefore's raw kill loop (:876-915): tout/tin/edgeprop of the range as they are when it runs.
pub open spec fn kill_raw(s: St, g: int, lo: int, hi: int) -> St {
    St {
        tout: tout_after_purge(s, g, lo, hi),
        eprop: Map::new(s.eprop.dom().filter(|c: Coord| !in_range(c, g, lo, hi)), |c: Coord| s.eprop[c]),
        purged: s.purged.union(s.tout.dom().filter(|c: Coord| in_range(c, g, lo, hi))),
        ..s
    }
}

/// A marked row of (g, p) that no timestamp holds.
pub open spec fn stranded(s: St, g: int, p: int) -> bool {
    exists|t: Triple| #[trigger] s.rows.contains_key(t) && t.g == g && t.p == p && s.rows[t] && !has_ts(s.tout, t)
}

/// TemporalPolicy.Set(g, p, enabled) (TemporalPolicy.cls:41-58); with optin_guard the repair's refusal.
pub open spec fn set_structural(s: St, g: int, p: int, enabled: bool, v: Variant) -> St {
    if enabled {
        if v.optin_guard && stranded(s, g, p) { s } else { St { optout: s.optout.remove((g, p)), ..s } }
    } else {
        St { optout: s.optout.insert((g, p)), ..s }
    }
}

/// TemporalPolicy.DropRows(g, p): refused for a structural predicate (:132-134); else deletes every row of
/// (g, p) that is still marked (bounded transactions; node retirement not represented).
pub open spec fn drop_rows(s: St, g: int, p: int) -> St {
    if structural(s, g, p) {
        s
    } else {
        St { rows: Map::new(s.rows.dom().filter(|t: Triple| !(t.g == g && t.p == p && s.rows[t])), |t: Triple| s.rows[t]), ..s }
    }
}

/// The triples of (g, p) that have a timestamp and no row.
pub open spec fn backfill_set(s: St, g: int, p: int) -> Set<Coord> {
    s.tout.dom().filter(|c: Coord| c.g == g && c.p == p && !s.rows.contains_key(tri(c)))
}

/// TemporalPolicy.BackfillRows(g, p): refused for a registered predicate (:264-266); else
/// BackfillWalk asserts a marked row (pTrustIndex=0) and both nodes for every triple of (g, p) with a timestamp.
pub open spec fn backfill(s: St, g: int, p: int) -> St {
    if !structural(s, g, p) {
        s
    } else {
        let add = backfill_set(s, g, p);
        St {
            rows: Map::new(s.rows.dom().union(add.map(|c: Coord| tri(c))),
                |t: Triple| if s.rows.contains_key(t) { s.rows[t] } else { true }),
            nodes: s.nodes.union(add.map(|c: Coord| (c.g, c.s))).union(add.map(|c: Coord| (c.g, c.o))),
            ..s
        }
    }
}

/// engine.create_edge / bulk_create_edges on a triple: a marked row is adopted (qualifiers become the explicit
/// ones, the marker goes: nodes_edges._adopt_temporal_row, _ADOPT_TEMPORAL_ROW_SQL); otherwise an unmarked row.
pub open spec fn create_edge(s: St, t: Triple) -> St {
    St { rows: s.rows.insert(t, false), nodes: s.nodes.insert((t.g, t.s)).insert((t.g, t.o)), ..s }
}

// ============================================================================ transactions (L2)

/// TSTART: push the journaled stores.
pub open spec fn tstart(s: St) -> St {
    St { txn: s.txn.push(snap(s)), ..s }
}

/// TCOMMIT: the level ends and its writes stay (in the enclosing level if any).
pub open spec fn tcommit(s: St) -> St {
    if s.txn.len() == 0 { s } else { St { txn: s.txn.drop_last(), ..s } }
}

/// TROLLBACK 1: the journaled stores return to the level's TSTART. The $Increment counters are not taken
/// back (premise P-INCR: ADR-0010 "Context", USER_GUIDE "Writes inside your transaction") unless the variant says so.
pub open spec fn trollback(s: St, v: Variant) -> St {
    if s.txn.len() == 0 {
        s
    } else {
        let sn = s.txn.last();
        St {
            tout: sn.tout, eprop: sn.eprop, rows: sn.rows, nodes: sn.nodes, optout: sn.optout,
            gov_nodes: sn.gov_nodes, gov_rels: sn.gov_rels, purged: sn.purged,
            bucket: if v.incr_undone { sn.bucket } else { restore_j(s.bucket, sn.jbucket) },
            cnt: if v.incr_undone { sn.cnt } else { restore_j(s.cnt, sn.jcnt) },
            sum: if v.incr_undone { sn.sum } else { restore_j(s.sum, sn.jsum) },
            txn: s.txn.drop_last(),
            plans: s.plans,
        }
    }
}

// ============================================================================ ledger commit (L2)

pub enum LOp {
    /// LedgerApply.OpCreateNode(pUpsert=0): node_exists when NodeExists (graph-blind, :79-84); else INSERT in
    /// the default graph and a create_node record
    CreateNode { id: int },
    /// OpCreateNode(pUpsert=1): an existing node gets no record
    UpsertNode { id: int },
    /// OpCreateTemporalEdge (:617-641): InsertEdge(..., upsert=0, sri=0, mode) — mode defaults to "update"
    /// (:628; Changeset.create_temporal_edge mode="update"); InsertEdge answers 1 for written, skip and collision
    Temporal { c: Coord, w: int, mode: Mode, f: Fail },
    /// OpCreateRel (pUpsert=0, :450-500): node_not_found unless both ids exist (graph-blind); relationship_exists
    /// for an unmarked row; adopts a marked row; EnsureEndpoint writes the endpoints into the rel's graph
    CreateRel { t: Triple },
}

pub enum Out {
    Ok,
    Refused,
    Threw,
}

pub open spec fn known(nodes: Set<(int, int)>, id: int) -> bool {
    exists|g: int| #[trigger] nodes.contains((g, id))
}

pub open spec fn node_known(s: St, id: int) -> bool {
    known(s.nodes, id)
}

pub open spec fn apply_op(s: St, op: LOp, v: Variant) -> (St, Out) {
    match op {
        LOp::CreateNode { id } =>
            if node_known(s, id) { (s, Out::Refused) } else {
                (St { nodes: s.nodes.insert((0, id)), gov_nodes: s.gov_nodes.insert(id), ..s }, Out::Ok)
            },
        LOp::UpsertNode { id } =>
            if node_known(s, id) { (s, Out::Ok) } else {
                (St { nodes: s.nodes.insert((0, id)), gov_nodes: s.gov_nodes.insert(id), ..s }, Out::Ok)
            },
        LOp::Temporal { c, w, mode, f } => {
            let (s1, r) = write_stores(s, c, w, None, mode, f, v);
            (s1, if r == WRes::Threw { Out::Threw } else { Out::Ok })
        },
        LOp::CreateRel { t } =>
            if !node_known(s, t.s) || !node_known(s, t.o) {
                (s, Out::Refused)
            } else if s.rows.contains_key(t) && !s.rows[t] {
                (s, Out::Refused)
            } else {
                (St {
                    rows: s.rows.insert(t, false),
                    nodes: s.nodes.insert((t.g, t.s)).insert((t.g, t.o)),
                    gov_rels: s.gov_rels.insert(t),
                    ..s
                }, Out::Ok)
            },
    }
}

/// LedgerApply.ApplyAll: ops in order; the first refusal returns its reason; a throw propagates.
pub open spec fn apply_ops(s: St, ops: Seq<LOp>, v: Variant) -> (St, Out)
    decreases ops.len(),
{
    if ops.len() == 0 {
        (s, Out::Ok)
    } else {
        let (s1, r) = apply_op(s, ops[0], v);
        if r != Out::Ok { (s1, r) } else { apply_ops(s1, ops.subrange(1, ops.len() as int), v) }
    }
}

/// Graph.KG.Ledger.Commit (Ledger.cls:397-415): TSTART; CommitInTxn (ApplyAll, then BlocksCommit while a
/// redaction runs, then WriteRevision); TCOMMIT when pOk, else TROLLBACK 1; a throw is caught and every level
/// this call opened is rolled back. `blocked` stands for LedgerRedact.BlocksCommit refusing the records.
pub open spec fn commit(s: St, ops: Seq<LOp>, blocked: bool, v: Variant) -> (St, Out) {
    let s0 = tstart(s);
    let (s1, r) = apply_ops(s0, ops, v);
    if r == Out::Ok && !blocked {
        (tcommit(s1), Out::Ok)
    } else {
        (trollback(s1, v), if r == Out::Ok { Out::Refused } else { r })
    }
}

// ============================================================================ phased purge / delete (L2, races)

/// ^||IVG.TPurge after RetireExpired's survivor walk (TemporalIndex.cls:956-1013): every triple of a structural
/// predicate with a timestamp in the range and none outside it — whether or not it has a row now (review R2-2).
/// RetractTemporalRows tests the marker only when its DELETE runs (Adjacency.cls:674).
pub open spec fn doomed_set(s: St, g: int, lo: int, hi: int) -> Set<Triple> {
    s.tout.dom().filter(|c: Coord| in_range(c, g, lo, hi) && structural(s, g, c.p)
        && !has_ts(tout_after_purge(s, g, lo, hi), tri(c))).map(|c: Coord| tri(c))
}

pub proof fn lemma_doomed_set_iff(s: St, g: int, lo: int, hi: int, t: Triple)
    ensures
        doomed_set(s, g, lo, hi).contains(t) == (purge_candidate(s, t, g, lo, hi) && !has_ts(tout_after_purge(s, g, lo, hi), t)),
{
    let f = s.tout.dom().filter(|c: Coord| in_range(c, g, lo, hi) && structural(s, g, c.p)
        && !has_ts(tout_after_purge(s, g, lo, hi), tri(c)));
    if doomed_set(s, g, lo, hi).contains(t) {
        let c = choose|c: Coord| f.contains(c) && t == tri(c);
        assert(s.tout.contains_key(c) && in_range(c, g, lo, hi) && tri(c) == t);
    }
    if purge_candidate(s, t, g, lo, hi) && !has_ts(tout_after_purge(s, g, lo, hi), t) {
        let c = choose|c: Coord| #[trigger] s.tout.contains_key(c) && in_range(c, g, lo, hi) && tri(c) == t;
        assert(f.contains(c));
        assert(f.map(|x: Coord| tri(x)).contains(tri(c)));
    }
}

/// The repair's re-test at effect time: the doomed triple still has no surviving timestamp.
pub open spec fn still_doomed(s: St, pl: Plan, t: Triple) -> bool {
    match pl.kill {
        Some(k) => !has_ts(tout_after_purge(s, k.0, k.1, k.2), t),
        None => !has_ts(s.tout, t),
    }
}

/// The structural triples whose timestamps the raw kill loop removes when it runs.
pub open spec fn kill_touch(s: St, g: int, lo: int, hi: int) -> Set<Triple> {
    s.tout.dom().filter(|c: Coord| in_range(c, g, lo, hi) && structural(s, g, c.p)).map(|c: Coord| tri(c))
}

pub open spec fn purge_decide(s: St, p: int, g: int, lo: int, hi: int) -> St {
    if s.plans.contains_key(p) {
        s
    } else {
        St { plans: s.plans.insert(p, Plan { doomed: doomed_set(s, g, lo, hi), kill: Some((g, lo, hi)), retracted: false }), ..s }
    }
}

pub open spec fn delete_decide(s: St, p: int, c: Coord) -> St {
    if s.plans.contains_key(p) || !s.tout.contains_key(c) {
        s
    } else {
        let s1 = remove_temporal_row(s, c);
        let d = if !has_ts(s1.tout, tri(c)) { set![tri(c)] } else { Set::<Triple>::empty() };
        St { plans: s1.plans.insert(p, Plan { doomed: d, kill: None, retracted: false }), ..s1 }
    }
}

/// The retraction of a plan: a doomed triple's row is deleted only while it is still marked.
pub open spec fn retract_plan(s: St, p: int, v: Variant) -> St {
    if !s.plans.contains_key(p) || s.plans[p].retracted {
        s
    } else {
        let pl = s.plans[p];
        St {
            rows: Map::new(s.rows.dom().filter(|t: Triple| !(pl.doomed.contains(t) && s.rows[t]
                && (!v.race_recheck || still_doomed(s, pl, t)))), |t: Triple| s.rows[t]),
            plans: if pl.kill is None { s.plans.remove(p) } else { s.plans.insert(p, Plan { retracted: true, ..pl }) },
            ..s
        }
    }
}

pub open spec fn purge_kill(s: St, p: int, v: Variant) -> St {
    if !s.plans.contains_key(p) || !s.plans[p].retracted || s.plans[p].kill is None {
        s
    } else {
        let pl = s.plans[p];
        let (g, lo, hi) = pl.kill->Some_0;
        let k = kill_raw(s, g, lo, hi);
        let touched = pl.doomed.union(kill_touch(s, g, lo, hi));
        St {
            rows: if v.race_recheck {
                Map::new(k.rows.dom().filter(|t: Triple| !(touched.contains(t) && k.rows[t] && !has_ts(k.tout, t))), |t: Triple| k.rows[t])
            } else {
                k.rows
            },
            plans: s.plans.remove(p),
            ..k
        }
    }
}

pub open spec fn phased(a: Action) -> bool {
    match a {
        Action::PurgeDecide { .. } | Action::DeleteDecide { .. } | Action::Retract { .. } | Action::PurgeKill { .. } => true,
        _ => false,
    }
}

// ============================================================================ actions

pub enum Action {
    /// create_edge_temporal → write_temporal_edge → InsertEdge → WriteStores (no transaction of its own)
    Write { c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail },
    /// delete_edge_temporal → DeleteTemporalEdge, run as one step (serial); joins a caller's open transaction
    Delete { c: Coord },
    /// purge_raw_before(ts_end=hi, ts_start=lo, graph, retire_bare_nodes=False), run as one step (serial)
    Purge { g: int, lo: int, hi: int, stop_after_rows: bool },
    /// the same two operations split where another process can interleave (no lock in TemporalIndex):
    /// RetireExpired's candidate collection and survivor walk (:944-1013)
    PurgeDecide { p: int, g: int, lo: int, hi: int },
    /// DeleteTemporalEdge up to its HasTemporalEdge test (:327-334)
    DeleteDecide { p: int, c: Coord },
    /// RetractTemporalRows (:1016, the DELETE re-tests the marker) / RetractTemporalRow (:337, re-reads it)
    Retract { p: int },
    /// PurgeRawBefore's raw kill loop (:876-915)
    PurgeKill { p: int },
    CreateEdge { t: Triple },
    /// engine.delete_edge: the row goes, its timestamps stay
    DeleteEdge { t: Triple },
    SetStructural { g: int, p: int, enabled: bool },
    DropRows { g: int, p: int },
    Backfill { g: int, p: int },
    /// a caller's START TRANSACTION / COMMIT / ROLLBACK on the engine's connection (same server process)
    Begin,
    End,
    Rollback,
    /// GraphLedger.commit(changeset)
    Commit { ops: Seq<LOp>, blocked: bool },
}

pub open spec fn step(s: St, a: Action, v: Variant) -> St {
    match a {
        Action::Write { c, w, attrs, mode, f } => write_stores(s, c, w, attrs, mode, f, v).0,
        Action::Delete { c } => delete_temporal(s, c).0,
        Action::Purge { g, lo, hi, stop_after_rows } => purge(s, g, lo, hi, stop_after_rows),
        Action::PurgeDecide { p, g, lo, hi } => purge_decide(s, p, g, lo, hi),
        Action::DeleteDecide { p, c } => delete_decide(s, p, c),
        Action::Retract { p } => retract_plan(s, p, v),
        Action::PurgeKill { p } => purge_kill(s, p, v),
        Action::CreateEdge { t } => create_edge(s, t),
        Action::DeleteEdge { t } => St { rows: s.rows.remove(t), ..s },
        Action::SetStructural { g, p, enabled } => set_structural(s, g, p, enabled, v),
        Action::DropRows { g, p } => drop_rows(s, g, p),
        Action::Backfill { g, p } => backfill(s, g, p),
        Action::Begin => tstart(s),
        Action::End => tcommit(s),
        Action::Rollback => trollback(s, v),
        Action::Commit { ops, blocked } => commit(s, ops, blocked, v).0,
    }
}


// ============================================================================ L1 — statistics equal the raw store

/// A bucket key whose raw edges a purge removed: its aggregate "describes the past" (ADR-0009:49), so the
/// rule below does not cover it (the purge-cut bucket question, F10/Q2 of the intent notes, is out of scope).
pub open spec fn cut(purged: Set<Coord>, k: AKey) -> bool {
    exists|c: Coord| #[trigger] purged.contains(c) && akey(c) == k
}

pub open spec fn bcut(purged: Set<Coord>, k: BKey) -> bool {
    exists|c: Coord| #[trigger] purged.contains(c) && bkey(c) == k
}

/// L1-AGG (spec 254 US2 / FR-003: a collision is "not stored and not counted"; the problem statement "the
/// aggregates count an edge the raw store no longer holds"; RebuildBucketAggregate's rule "the aggregate
/// describes the surviving edges"): for every key no purge has cut, tagg count = number of raw edges,
/// tagg sum = sum of their weights, and the per-source bucket count = number of raw edges of the source.
///
/// A counter of a key with no raw edge must be ABSENT, not 0 (review R2-4): "A zero counter is not neutral: it still
/// claims the source was active in this bucket, which is what FindBursts and GetVelocity read" (TemporalIndex.cls
/// :355-357); FindBursts lists every source present in a bucket (:784-803), so a 0 node is a reportable source.
pub open spec fn exact(sn: Snap) -> bool {
    &&& forall|k: AKey| !cut(sn.purged, k) ==> #[trigger] get0(sn.cnt, k) == aset(sn.tout, k).len() as int
    &&& forall|k: AKey| !cut(sn.purged, k) ==> #[trigger] get0(sn.sum, k) == wsum(aset(sn.tout, k), sn.tout)
    &&& forall|k: BKey| !bcut(sn.purged, k) ==> #[trigger] get0(sn.bucket, k) == bset(sn.tout, k).len() as int
    &&& forall|k: BKey| !bcut(sn.purged, k) ==> (#[trigger] sn.bucket.contains_key(k) <==> bset(sn.tout, k).len() > 0)
    &&& forall|k: AKey| !cut(sn.purged, k) ==> (#[trigger] sn.cnt.contains_key(k) <==> aset(sn.tout, k).len() > 0)
}

pub open spec fn agg_exact(s: St) -> bool {
    exact(snap(s))
}

pub open spec fn snaps_exact(s: St) -> bool {
    forall|i: int| 0 <= i < s.txn.len() ==> exact(#[trigger] s.txn[i])
}

// ---------------------------------------------------------------------------- set lemmas

pub proof fn lemma_aset_insert(tout: Map<Coord, int>, c: Coord, w: int, k: AKey)
    requires
        !tout.contains_key(c),
    ensures
        aset(tout.insert(c, w), k) == (if akey(c) == k { aset(tout, k).insert(c) } else { aset(tout, k) }),
        aset(tout.insert(c, w), k).len() == aset(tout, k).len() + (if akey(c) == k { 1int } else { 0int }),
        wsum(aset(tout.insert(c, w), k), tout.insert(c, w)) == wsum(aset(tout, k), tout) + (if akey(c) == k { w } else { 0int }),
{
    let t2 = tout.insert(c, w);
    let a = aset(tout, k);
    if akey(c) == k {
        assert(aset(t2, k) =~= a.insert(c));
        assert(!a.contains(c));
        lemma_wsum_insert(a, t2, c);
    } else {
        assert(aset(t2, k) =~= a);
    }
    assert forall|x: Coord| a.contains(x) implies t2[x] == tout[x] by {
        assert(x != c);
    }
    lemma_wsum_frame(a, t2, tout);
}

pub proof fn lemma_bset_insert(tout: Map<Coord, int>, c: Coord, w: int, k: BKey)
    requires
        !tout.contains_key(c),
    ensures
        bset(tout.insert(c, w), k).len() == bset(tout, k).len() + (if bkey(c) == k { 1int } else { 0int }),
{
    let a = bset(tout, k);
    if bkey(c) == k {
        assert(bset(tout.insert(c, w), k) =~= a.insert(c));
        assert(!a.contains(c));
    } else {
        assert(bset(tout.insert(c, w), k) =~= a);
    }
}

/// Overwriting the weight at an occupied coordinate leaves every key's edge set alone and every other
/// key's sum.
pub proof fn lemma_aset_overwrite(tout: Map<Coord, int>, c: Coord, w: int, k: AKey)
    requires
        tout.contains_key(c),
    ensures
        aset(tout.insert(c, w), k) == aset(tout, k),
        bset(tout.insert(c, w), bkey(c)) == bset(tout, bkey(c)),
        akey(c) != k ==> wsum(aset(tout.insert(c, w), k), tout.insert(c, w)) == wsum(aset(tout, k), tout),
{
    let t2 = tout.insert(c, w);
    assert(t2.dom() =~= tout.dom());
    assert(aset(t2, k) =~= aset(tout, k));
    assert(bset(t2, bkey(c)) =~= bset(tout, bkey(c)));
    if akey(c) != k {
        assert forall|x: Coord| aset(tout, k).contains(x) implies t2[x] == tout[x] by {
            assert(x != c);
        }
        lemma_wsum_frame(aset(tout, k), t2, tout);
    }
}

pub proof fn lemma_bset_overwrite(tout: Map<Coord, int>, c: Coord, w: int, k: BKey)
    requires
        tout.contains_key(c),
    ensures
        bset(tout.insert(c, w), k) == bset(tout, k),
{
    assert(tout.insert(c, w).dom() =~= tout.dom());
    assert(bset(tout.insert(c, w), k) =~= bset(tout, k));
}

pub proof fn lemma_aset_remove(tout: Map<Coord, int>, c: Coord, k: AKey)
    requires
        tout.contains_key(c),
        akey(c) != k,
    ensures
        aset(tout.remove(c), k) == aset(tout, k),
        wsum(aset(tout.remove(c), k), tout.remove(c)) == wsum(aset(tout, k), tout),
{
    let t2 = tout.remove(c);
    assert(aset(t2, k) =~= aset(tout, k));
    assert forall|x: Coord| aset(tout, k).contains(x) implies t2[x] == tout[x] by {
        assert(x != c);
    }
    lemma_wsum_frame(aset(tout, k), t2, tout);
}

pub proof fn lemma_bset_remove(tout: Map<Coord, int>, c: Coord, k: BKey)
    requires
        tout.contains_key(c),
    ensures
        bset(tout.remove(c), k).len() == bset(tout, k).len() - (if bkey(c) == k { 1int } else { 0int }),
{
    let a = bset(tout, k);
    if bkey(c) == k {
        assert(bset(tout.remove(c), k) =~= a.remove(c));
        assert(a.contains(c));
    } else {
        assert(bset(tout.remove(c), k) =~= a);
    }
}

/// RebuildBucketAggregate makes its key exact and leaves the others.
pub proof fn lemma_rebuild_exact(s: St, k: AKey)
    ensures
        get0(rebuild(s, k).cnt, k) == aset(s.tout, k).len() as int,
        get0(rebuild(s, k).sum, k) == wsum(aset(s.tout, k), s.tout),
        rebuild(s, k).cnt.contains_key(k) <==> aset(s.tout, k).len() > 0,
        forall|k2: AKey| k2 != k ==> get0(#[trigger] rebuild(s, k).cnt, k2) == get0(s.cnt, k2) && get0(rebuild(s, k).sum, k2) == get0(s.sum, k2)
            && rebuild(s, k).cnt.contains_key(k2) == s.cnt.contains_key(k2),
        rebuild(s, k).tout == s.tout,
        rebuild(s, k).bucket == s.bucket,
        rebuild(s, k).rows == s.rows,
        rebuild(s, k).purged == s.purged,
        rebuild(s, k).txn == s.txn,
{
    if aset(s.tout, k).len() == 0 {
        lemma_wsum_empty(aset(s.tout, k), s.tout);
    }
}

/// exact() reads only tout, the three counters and purged.
pub proof fn lemma_exact_frame(a: Snap, b: Snap)
    requires
        exact(a),
        a.tout == b.tout,
        a.cnt == b.cnt,
        a.sum == b.sum,
        a.bucket == b.bucket,
        a.purged == b.purged,
    ensures
        exact(b),
{
}

// ---------------------------------------------------------------------------- write

/// When a write is "exact-safe": no throw in the as-built order, and no "update" over an occupied coordinate
/// unless the update rebuilds.
pub open spec fn write_ok(s: St, c: Coord, mode: Mode, f: Fail, v: Variant) -> bool {
    &&& (v.assert_first || !row_step_fails(s, c, f))
    &&& (v.update_rebuilds || !(mode == Mode::Update && s.tout.contains_key(c)))
}

/// A complete write at a free coordinate, or a rebuilding overwrite, keeps the statistics exact.
pub proof fn lemma_write_exact(s: St, c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail, v: Variant)
    requires
        agg_exact(s),
        write_ok(s, c, mode, f, v),
    ensures
        agg_exact(write_stores(s, c, w, attrs, mode, f, v).0),
        write_stores(s, c, w, attrs, mode, f, v).0.txn == s.txn,
{
    if guard_stops(s, c, mode) {
        return;
    }
    let s2 = write_stores(s, c, w, attrs, mode, f, v).0;
    let occupied = s.tout.contains_key(c);
    let fails = row_step_fails(s, c, f);
    if v.assert_first && fails {
        assert(s2.tout == s.tout && s2.cnt == s.cnt && s2.sum == s.sum && s2.bucket == s.bucket && s2.purged == s.purged);
        lemma_exact_frame(snap(s), snap(s2));
        return;
    }
    assert(!fails);
    // the stores that matter, whatever the order
    assert(s2.tout == s.tout.insert(c, w));
    assert(s2.purged == s.purged);
    assert(s2.txn == s.txn);
    let sn = snap(s);
    let sn2 = snap(s2);
    if !occupied {
        assert(s2.bucket == s.bucket.insert(bkey(c), get0(s.bucket, bkey(c)) + 1));
        assert(s2.cnt == s.cnt.insert(akey(c), get0(s.cnt, akey(c)) + 1));
        assert(s2.sum == s.sum.insert(akey(c), get0(s.sum, akey(c)) + w));
        assert forall|k: AKey| #![trigger get0(sn2.cnt, k)] #![trigger get0(sn2.sum, k)] !cut(sn2.purged, k) implies get0(sn2.cnt, k) == aset(sn2.tout, k).len() as int
            && get0(sn2.sum, k) == wsum(aset(sn2.tout, k), sn2.tout) by {
            assert(!cut(sn.purged, k));
        assert(get0(sn.cnt, k) == aset(sn.tout, k).len() as int);
        assert(get0(sn.sum, k) == wsum(aset(sn.tout, k), sn.tout));
            assert(get0(sn.cnt, k) == aset(sn.tout, k).len() as int);
            assert(get0(sn.sum, k) == wsum(aset(sn.tout, k), sn.tout));
            lemma_aset_insert(s.tout, c, w, k);
        }
        assert forall|k: BKey| !bcut(sn2.purged, k) implies #[trigger] get0(sn2.bucket, k) == bset(sn2.tout, k).len() as int by {
            assert(!bcut(sn.purged, k));
        assert(get0(sn.bucket, k) == bset(sn.tout, k).len() as int);
            assert(get0(sn.bucket, k) == bset(sn.tout, k).len() as int);
            lemma_bset_insert(s.tout, c, w, k);
        }
        assert forall|k: AKey| !cut(sn2.purged, k) implies (#[trigger] sn2.cnt.contains_key(k) <==> aset(sn2.tout, k).len() > 0) by {
            assert(!cut(sn.purged, k));
            assert(sn.cnt.contains_key(k) <==> aset(sn.tout, k).len() > 0);
            lemma_aset_insert(s.tout, c, w, k);
        }
        assert forall|k: BKey| !bcut(sn2.purged, k) implies (#[trigger] sn2.bucket.contains_key(k) <==> bset(sn2.tout, k).len() > 0) by {
            assert(!bcut(sn.purged, k));
            assert(sn.bucket.contains_key(k) <==> bset(sn.tout, k).len() > 0);
            lemma_bset_insert(s.tout, c, w, k);
        }
    } else {
        assert(v.update_rebuilds && mode == Mode::Update);
        assert(s2.bucket == s.bucket);
        let mid = if v.assert_first {
            let s1 = if structural(s, c.g, c.p) { assert_row(s, tri(c)) } else { s };
            raw_part(s1, c, w, mode, v)
        } else {
            let s1 = raw_part(s, c, w, mode, v);
            if structural(s, c.g, c.p) { assert_row(s1, tri(c)) } else { s1 }
        };
        assert(mid.tout == s.tout.insert(c, w) && mid.cnt == s.cnt && mid.sum == s.sum);
        lemma_rebuild_exact(mid, akey(c));
        assert(get0(s2.cnt, akey(c)) == get0(rebuild(mid, akey(c)).cnt, akey(c)));
        assert forall|k: AKey| #![trigger get0(sn2.cnt, k)] #![trigger get0(sn2.sum, k)] !cut(sn2.purged, k) implies get0(sn2.cnt, k) == aset(sn2.tout, k).len() as int
            && get0(sn2.sum, k) == wsum(aset(sn2.tout, k), sn2.tout) by {
            assert(!cut(sn.purged, k));
        assert(get0(sn.cnt, k) == aset(sn.tout, k).len() as int);
        assert(get0(sn.sum, k) == wsum(aset(sn.tout, k), sn.tout));
            assert(get0(sn.cnt, k) == aset(sn.tout, k).len() as int);
            assert(get0(sn.sum, k) == wsum(aset(sn.tout, k), sn.tout));
            lemma_aset_overwrite(s.tout, c, w, k);
            if k != akey(c) {
                assert(get0(s2.cnt, k) == get0(rebuild(mid, akey(c)).cnt, k));
            }
        }
        assert forall|k: BKey| !bcut(sn2.purged, k) implies #[trigger] get0(sn2.bucket, k) == bset(sn2.tout, k).len() as int by {
            assert(!bcut(sn.purged, k));
        assert(get0(sn.bucket, k) == bset(sn.tout, k).len() as int);
            assert(get0(sn.bucket, k) == bset(sn.tout, k).len() as int);
            lemma_bset_overwrite(s.tout, c, w, k);
        }
        assert forall|k: AKey| !cut(sn2.purged, k) implies (#[trigger] sn2.cnt.contains_key(k) <==> aset(sn2.tout, k).len() > 0) by {
            assert(!cut(sn.purged, k));
            assert(sn.cnt.contains_key(k) <==> aset(sn.tout, k).len() > 0);
            lemma_aset_overwrite(s.tout, c, w, k);
            assert(s2.cnt == rebuild(mid, akey(c)).cnt);
        }
        assert forall|k: BKey| !bcut(sn2.purged, k) implies (#[trigger] sn2.bucket.contains_key(k) <==> bset(sn2.tout, k).len() > 0) by {
            assert(!bcut(sn.purged, k));
            assert(sn.bucket.contains_key(k) <==> bset(sn.tout, k).len() > 0);
            lemma_bset_overwrite(s.tout, c, w, k);
        }
    }
}

/// L1-W (spec 254 FR-003, Decision 2): "insert" (and "skip") at coordinates that hold an edge changes no
/// store and is reported as a collision (a skip). Holds in every variant.
pub proof fn lemma_collision_changes_nothing(s: St, c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail, v: Variant)
    requires
        mode != Mode::Update,
        s.tout.contains_key(c),
    ensures
        write_stores(s, c, w, attrs, mode, f, v).0 == s,
        write_stores(s, c, w, attrs, mode, f, v).1 == (if mode == Mode::Skip { WRes::Skipped } else { WRes::Collided }),
{
}

// ---------------------------------------------------------------------------- delete, purge

pub proof fn lemma_txn_frame_refl(a: Seq<Snap>)
    ensures
        txn_frame(a, a),
{
}

pub proof fn lemma_txn_frame_trans(a: Seq<Snap>, b: Seq<Snap>, c: Seq<Snap>)
    requires
        txn_frame(a, b),
        txn_frame(b, c),
    ensures
        txn_frame(a, c),
{
    assert forall|i: int| 0 <= i < a.len() implies snap_frame(#[trigger] a[i], c[i]) by {
        assert(snap_frame(a[i], b[i]) && snap_frame(b[i], c[i]));
    }
}

/// Journaling touches only the top level's journals.
pub proof fn lemma_journal_bucket_shape(s: St, k: BKey, before: Option<int>)
    ensures
        ({
            let r = journal_bucket(s, k, before);
            &&& r.tout == s.tout && r.eprop == s.eprop && r.bucket == s.bucket && r.cnt == s.cnt && r.sum == s.sum
            &&& r.rows == s.rows && r.nodes == s.nodes && r.optout == s.optout && r.purged == s.purged
            &&& r.gov_nodes == s.gov_nodes && r.gov_rels == s.gov_rels && r.plans == s.plans
            &&& txn_frame(r.txn, s.txn)
        }),
{
    if s.txn.len() > 0 {
        let r = journal_bucket(s, k, before);
        assert forall|i: int| 0 <= i < r.txn.len() implies snap_frame(#[trigger] r.txn[i], s.txn[i]) by {}
    }
}

pub proof fn lemma_journal_agg_shape(s: St, k: AKey)
    ensures
        ({
            let r = journal_agg(s, k);
            &&& r.tout == s.tout && r.eprop == s.eprop && r.bucket == s.bucket && r.cnt == s.cnt && r.sum == s.sum
            &&& r.rows == s.rows && r.nodes == s.nodes && r.optout == s.optout && r.purged == s.purged
            &&& r.gov_nodes == s.gov_nodes && r.gov_rels == s.gov_rels && r.plans == s.plans
            &&& txn_frame(r.txn, s.txn)
        }),
{
    if s.txn.len() > 0 {
        let r = journal_agg(s, k);
        assert forall|i: int| 0 <= i < r.txn.len() implies snap_frame(#[trigger] r.txn[i], s.txn[i]) by {}
    }
}

/// RemoveTemporalRow's raw part: what it does to each store.
pub proof fn lemma_remove_raw_shape(s: St, c: Coord)
    ensures
        ({
            let r = remove_raw(s, c);
            let nb = get0(s.bucket, bkey(c)) - 1;
            &&& r.tout == s.tout.remove(c) && r.eprop == s.eprop.remove(c)
            &&& r.cnt == s.cnt && r.sum == s.sum && r.rows == s.rows && r.nodes == s.nodes && r.optout == s.optout
            &&& r.purged == s.purged && r.gov_nodes == s.gov_nodes && r.gov_rels == s.gov_rels && r.plans == s.plans
            &&& txn_frame(r.txn, s.txn)
            &&& get0(r.bucket, bkey(c)) == (if nb <= 0 { 0 } else { nb })
            &&& forall|k: BKey| k != bkey(c) ==> #[trigger] get0(r.bucket, k) == get0(s.bucket, k)
        }),
{
    let bk = bkey(c);
    let nb = get0(s.bucket, bk) - 1;
    let s1 = St { tout: s.tout.remove(c), eprop: s.eprop.remove(c), bucket: s.bucket.insert(bk, nb), ..s };
    lemma_txn_frame_refl(s.txn);
    if nb <= 0 {
        lemma_journal_bucket_shape(s1, bk, Some(nb));
    }
}

/// RemoveTemporalRow as a whole.
pub proof fn lemma_remove_temporal_row_shape(s: St, c: Coord)
    ensures
        ({
            let r = remove_temporal_row(s, c);
            let r0 = remove_raw(s, c);
            &&& r.tout == s.tout.remove(c) && r.bucket == r0.bucket && r.rows == s.rows && r.nodes == s.nodes
            &&& r.optout == s.optout && r.purged == s.purged && r.gov_nodes == s.gov_nodes && r.gov_rels == s.gov_rels
            &&& r.plans == s.plans
            &&& txn_frame(r.txn, s.txn)
            &&& r == rebuild(journal_agg(r0, akey(c)), akey(c))
        }),
{
    let r0 = remove_raw(s, c);
    lemma_remove_raw_shape(s, c);
    lemma_journal_agg_shape(r0, akey(c));
    let r1 = journal_agg(r0, akey(c));
    lemma_rebuild_exact(r1, akey(c));
    lemma_txn_frame_trans(r1.txn, r0.txn, s.txn);
}

pub proof fn lemma_delete_exact(s: St, c: Coord)
    requires
        agg_exact(s),
    ensures
        agg_exact(delete_temporal(s, c).0),
        txn_frame(delete_temporal(s, c).0.txn, s.txn),
{
    if !s.tout.contains_key(c) {
        lemma_txn_frame_refl(s.txn);
        return;
    }
    let bk = bkey(c);
    let s0 = remove_raw(s, c);
    // RemoveTemporalRow's raw part, from its definition (not from lemma_remove_raw_shape, so that a faulty
    // counter step is caught here, by the L1 obligation)
    let nb = get0(s.bucket, bk) - 1;
    let sx = St { tout: s.tout.remove(c), eprop: s.eprop.remove(c), bucket: s.bucket.insert(bk, nb), ..s };
    lemma_journal_bucket_shape(sx, bk, Some(nb));
    lemma_txn_frame_refl(s.txn);
    assert(s0.tout == s.tout.remove(c) && s0.cnt == s.cnt && s0.sum == s.sum && s0.purged == s.purged);
    assert(txn_frame(s0.txn, s.txn));
    lemma_journal_agg_shape(s0, akey(c));
    let s1 = journal_agg(s0, akey(c));
    let r = rebuild(s1, akey(c));
    assert(r == remove_temporal_row(s, c));
    lemma_remove_temporal_row_shape(s, c);
    lemma_rebuild_exact(s1, akey(c));
    let s2 = delete_temporal(s, c).0;
    assert(s2.tout == r.tout && s2.cnt == r.cnt && s2.sum == r.sum && s2.bucket == r.bucket && s2.purged == r.purged);
    assert(s2.txn == r.txn);
    let sn = snap(s);
    let sn2 = snap(s2);
    assert forall|k: AKey| #![trigger get0(sn2.cnt, k)] #![trigger get0(sn2.sum, k)] !cut(sn2.purged, k) implies get0(sn2.cnt, k) == aset(sn2.tout, k).len() as int
        && get0(sn2.sum, k) == wsum(aset(sn2.tout, k), sn2.tout) by {
        assert(!cut(sn.purged, k));
        assert(get0(sn.cnt, k) == aset(sn.tout, k).len() as int);
        assert(get0(sn.sum, k) == wsum(aset(sn.tout, k), sn.tout));
        if k != akey(c) {
            lemma_aset_remove(s.tout, c, k);
        }
    }
    assert forall|k: BKey| !bcut(sn2.purged, k) implies #[trigger] get0(sn2.bucket, k) == bset(sn2.tout, k).len() as int by {
        assert(!bcut(sn.purged, k));
        assert(get0(sn.bucket, k) == bset(sn.tout, k).len() as int);
        lemma_bset_remove(s.tout, c, k);
        if k == bk {
            assert(bset(s.tout, k).contains(c));
            assert(bset(s.tout, k).len() >= 1);
        } else {
            assert(get0(s0.bucket, k) == get0(s.bucket, k));
        }
    }
    assert forall|k: AKey| !cut(sn2.purged, k) implies (#[trigger] sn2.cnt.contains_key(k) <==> aset(sn2.tout, k).len() > 0) by {
        assert(!cut(sn.purged, k));
        assert(sn.cnt.contains_key(k) <==> aset(sn.tout, k).len() > 0);
        if k != akey(c) {
            lemma_aset_remove(s.tout, c, k);
        }
    }
    assert forall|k: BKey| !bcut(sn2.purged, k) implies (#[trigger] sn2.bucket.contains_key(k) <==> bset(sn2.tout, k).len() > 0) by {
        assert(!bcut(sn.purged, k));
        assert(sn.bucket.contains_key(k) <==> bset(sn.tout, k).len() > 0);
        lemma_bset_remove(s.tout, c, k);
        if k == bk {
            assert(bset(s.tout, k).contains(c));
        } else {
            assert(s0.bucket.contains_key(k) == s.bucket.contains_key(k));
        }
    }
}

pub proof fn lemma_purge_exact(s: St, g: int, lo: int, hi: int, stop: bool)
    requires
        agg_exact(s),
    ensures
        agg_exact(purge(s, g, lo, hi, stop)),
        purge(s, g, lo, hi, stop).txn == s.txn,
{
    let s2 = purge(s, g, lo, hi, stop);
    if stop {
        lemma_exact_frame(snap(s), snap(s2));
    } else {
        lemma_kill_exact(s, g, lo, hi);
        lemma_exact_frame(snap(kill_raw(s, g, lo, hi)), snap(s2));
    }
}

/// The raw kill loop keeps the statistics exact for every bucket it does not cut.
pub proof fn lemma_kill_exact(s: St, g: int, lo: int, hi: int)
    requires
        agg_exact(s),
    ensures
        agg_exact(kill_raw(s, g, lo, hi)),
        kill_raw(s, g, lo, hi).txn == s.txn,
{
    let s2 = kill_raw(s, g, lo, hi);
    let sn = snap(s);
    let sn2 = snap(s2);
    let t2 = tout_after_purge(s, g, lo, hi);
    assert(s2.tout == t2);
    assert(t2.dom() == s.tout.dom().filter(|c: Coord| !in_range(c, g, lo, hi)));
    assert forall|k: AKey| #![trigger get0(sn2.cnt, k)] #![trigger get0(sn2.sum, k)] !cut(sn2.purged, k) implies get0(sn2.cnt, k) == aset(sn2.tout, k).len() as int
        && get0(sn2.sum, k) == wsum(aset(sn2.tout, k), sn2.tout) by {
        assert forall|x: Coord| #[trigger] sn.purged.contains(x) implies akey(x) != k by {
            assert(sn2.purged.contains(x));
        }
        assert(!cut(sn.purged, k));
        assert(get0(sn.cnt, k) == aset(sn.tout, k).len() as int);
        assert(get0(sn.sum, k) == wsum(aset(sn.tout, k), sn.tout));
        assert forall|x: Coord| aset(s.tout, k).contains(x) implies !in_range(x, g, lo, hi) by {
            if in_range(x, g, lo, hi) {
                assert(sn2.purged.contains(x));
            }
        }
        assert(aset(t2, k) =~= aset(s.tout, k));
        assert forall|x: Coord| aset(s.tout, k).contains(x) implies t2[x] == s.tout[x] by {}
        lemma_wsum_frame(aset(s.tout, k), t2, s.tout);
    }
    assert forall|k: BKey| !bcut(sn2.purged, k) implies #[trigger] get0(sn2.bucket, k) == bset(sn2.tout, k).len() as int by {
        assert forall|x: Coord| #[trigger] sn.purged.contains(x) implies bkey(x) != k by {
            assert(sn2.purged.contains(x));
        }
        assert(!bcut(sn.purged, k));
        assert(get0(sn.bucket, k) == bset(sn.tout, k).len() as int);
        assert forall|x: Coord| bset(s.tout, k).contains(x) implies !in_range(x, g, lo, hi) by {
            if in_range(x, g, lo, hi) {
                assert(sn2.purged.contains(x));
            }
        }
        assert(bset(t2, k) =~= bset(s.tout, k));
    }
    assert forall|k: AKey| !cut(sn2.purged, k) implies (#[trigger] sn2.cnt.contains_key(k) <==> aset(sn2.tout, k).len() > 0) by {
        assert forall|x: Coord| #[trigger] sn.purged.contains(x) implies akey(x) != k by {
            assert(sn2.purged.contains(x));
        }
        assert(!cut(sn.purged, k));
        assert(sn.cnt.contains_key(k) <==> aset(sn.tout, k).len() > 0);
        assert forall|x: Coord| aset(s.tout, k).contains(x) implies !in_range(x, g, lo, hi) by {
            if in_range(x, g, lo, hi) {
                assert(sn2.purged.contains(x));
            }
        }
        assert(aset(t2, k) =~= aset(s.tout, k));
    }
    assert forall|k: BKey| !bcut(sn2.purged, k) implies (#[trigger] sn2.bucket.contains_key(k) <==> bset(sn2.tout, k).len() > 0) by {
        assert forall|x: Coord| #[trigger] sn.purged.contains(x) implies bkey(x) != k by {
            assert(sn2.purged.contains(x));
        }
        assert(!bcut(sn.purged, k));
        assert(sn.bucket.contains_key(k) <==> bset(sn.tout, k).len() > 0);
        assert forall|x: Coord| bset(s.tout, k).contains(x) implies !in_range(x, g, lo, hi) by {
            if in_range(x, g, lo, hi) {
                assert(sn2.purged.contains(x));
            }
        }
        assert(bset(t2, k) =~= bset(s.tout, k));
    }
}


// ---------------------------------------------------------------------------- ledger ops and transactions

pub proof fn lemma_apply_op_txn(s: St, op: LOp, v: Variant)
    ensures
        apply_op(s, op, v).0.txn == s.txn,
{
    match op {
        LOp::Temporal { c, w, mode, f } => {
            let s1 = write_stores(s, c, w, None, mode, f, v).0;
            assert(s1.txn == s.txn);
        },
        _ => {},
    }
}

pub proof fn lemma_apply_ops_txn(s: St, ops: Seq<LOp>, v: Variant)
    ensures
        apply_ops(s, ops, v).0.txn == s.txn,
    decreases ops.len(),
{
    if ops.len() > 0 {
        lemma_apply_op_txn(s, ops[0], v);
        let s1 = apply_op(s, ops[0], v).0;
        lemma_apply_ops_txn(s1, ops.subrange(1, ops.len() as int), v);
    }
}

/// Under a variant whose writes are all exact-safe, a changeset's ops keep the statistics exact.
pub proof fn lemma_apply_ops_exact(s: St, ops: Seq<LOp>, v: Variant)
    requires
        agg_exact(s),
        v.assert_first,
        v.update_rebuilds,
    ensures
        agg_exact(apply_ops(s, ops, v).0),
    decreases ops.len(),
{
    if ops.len() > 0 {
        let op = ops[0];
        let s1 = apply_op(s, op, v).0;
        match op {
            LOp::Temporal { c, w, mode, f } => {
                lemma_write_exact(s, c, w, None, mode, f, v);
            },
            _ => {
                lemma_exact_frame(snap(s), snap(s1));
            },
        }
        lemma_apply_ops_exact(s1, ops.subrange(1, ops.len() as int), v);
    }
}

/// Snapshot invariants read only the snapshot's stores, never its journals.
pub proof fn lemma_snaps_exact_frame(s: St, s2: St)
    requires
        snaps_exact(s),
        txn_frame(s2.txn, s.txn),
    ensures
        snaps_exact(s2),
{
    assert forall|i: int| 0 <= i < s2.txn.len() implies exact(#[trigger] s2.txn[i]) by {
        assert(snap_frame(s2.txn[i], s.txn[i]));
        lemma_exact_frame(s.txn[i], s2.txn[i]);
    }
}

pub proof fn lemma_snaps_rows_frame(s: St, s2: St)
    requires
        snaps_rows_ok(s),
        txn_frame(s2.txn, s.txn),
    ensures
        snaps_rows_ok(s2),
{
    assert forall|i: int| 0 <= i < s2.txn.len() implies rows_ok_parts(#[trigger] s2.txn[i].tout, s2.txn[i].rows, s2.txn[i].optout) by {
        assert(snap_frame(s2.txn[i], s.txn[i]));
        assert(rows_ok_parts(s.txn[i].tout, s.txn[i].rows, s.txn[i].optout));
    }
}

/// What each action needs for the statistics to stay exact, per variant.
pub open spec fn stats_ok(s: St, a: Action, v: Variant) -> bool {
    match a {
        Action::Write { c, w, attrs, mode, f } => write_ok(s, c, mode, f, v),
        Action::Rollback => v.incr_undone,
        Action::Commit { ops, blocked } => v.incr_undone && v.assert_first && v.update_rebuilds,
        _ => true,
    }
}

pub proof fn lemma_step_stats(s: St, a: Action, v: Variant)
    requires
        agg_exact(s),
        snaps_exact(s),
        stats_ok(s, a, v),
    ensures
        agg_exact(step(s, a, v)),
        snaps_exact(step(s, a, v)),
{
    let s2 = step(s, a, v);
    match a {
        Action::Write { c, w, attrs, mode, f } => {
            lemma_write_exact(s, c, w, attrs, mode, f, v);
        },
        Action::Delete { c } => {
            lemma_delete_exact(s, c);
            lemma_snaps_exact_frame(s, s2);
        },
        Action::Purge { g, lo, hi, stop_after_rows } => {
            lemma_purge_exact(s, g, lo, hi, stop_after_rows);
        },
        Action::DeleteDecide { p, c } => {
            if !s.plans.contains_key(p) && s.tout.contains_key(c) {
                lemma_delete_exact(s, c);
                lemma_remove_temporal_row_shape(s, c);
                let d = delete_temporal(s, c).0;
                let r = remove_temporal_row(s, c);
                assert(d.tout == r.tout && d.cnt == r.cnt && d.sum == r.sum && d.bucket == r.bucket && d.purged == r.purged);
                lemma_exact_frame(snap(d), snap(s2));
                assert(s2.txn == r.txn);
                lemma_snaps_exact_frame(s, s2);
            }
        },
        Action::PurgeKill { p } => {
            if s.plans.contains_key(p) && s.plans[p].retracted && s.plans[p].kill is Some {
                let (g, lo, hi) = s.plans[p].kill->Some_0;
                lemma_kill_exact(s, g, lo, hi);
                lemma_exact_frame(snap(kill_raw(s, g, lo, hi)), snap(s2));
            }
        },
        Action::Begin => {
            lemma_exact_frame(snap(s), snap(s2));
            assert forall|i: int| 0 <= i < s2.txn.len() implies exact(#[trigger] s2.txn[i]) by {
                if i < s.txn.len() { assert(s2.txn[i] == s.txn[i]); } else { assert(s2.txn[i] == snap(s)); }
            }
        },
        Action::End => {
            lemma_exact_frame(snap(s), snap(s2));
            assert forall|i: int| 0 <= i < s2.txn.len() implies exact(#[trigger] s2.txn[i]) by {
                assert(s2.txn[i] == s.txn[i]);
            }
        },
        Action::Rollback => {
            if s.txn.len() > 0 {
                let sn = s.txn.last();
                assert(exact(s.txn[s.txn.len() - 1]));
                lemma_exact_frame(sn, snap(s2));
                assert forall|i: int| 0 <= i < s2.txn.len() implies exact(#[trigger] s2.txn[i]) by {
                    assert(s2.txn[i] == s.txn[i]);
                }
            }
        },
        Action::Commit { ops, blocked } => {
            let s0 = tstart(s);
            lemma_exact_frame(snap(s), snap(s0));
            lemma_apply_ops_txn(s0, ops, v);
            lemma_apply_ops_exact(s0, ops, v);
            let (s1, r) = apply_ops(s0, ops, v);
            assert(s1.txn == s.txn.push(snap(s)));
            if r == Out::Ok && !blocked {
                lemma_exact_frame(snap(s1), snap(s2));
                assert forall|i: int| 0 <= i < s2.txn.len() implies exact(#[trigger] s2.txn[i]) by {
                    assert(s2.txn[i] == s.txn[i]);
                }
            } else {
                assert(s1.txn.last() == snap(s));
                lemma_exact_frame(snap(s), snap(s2));
                assert forall|i: int| 0 <= i < s2.txn.len() implies exact(#[trigger] s2.txn[i]) by {
                    assert(s2.txn[i] == s.txn[i]);
                }
            }
        },
        _ => {
            lemma_exact_frame(snap(s), snap(s2));
        },
    }
}

/// THEOREM (as built, statistics): outside the three mechanisms the findings name — an "update" over an
/// occupied coordinate, a throw from the structural step, and any rollback (TROLLBACK of a caller or of a
/// ledger commit) — every step keeps every unpurged bucket's count, sum and per-source count equal to
/// the raw store. Inserts and skips at occupied coordinates are included (first write wins).
pub open spec fn as_built_fragment(s: St, a: Action) -> bool {
    match a {
        Action::Write { c, w, attrs, mode, f } => !row_step_fails(s, c, f) && !(mode == Mode::Update && s.tout.contains_key(c)),
        Action::Rollback => false,
        Action::Commit { ops, blocked } => false,
        _ => true,
    }
}

pub proof fn theorem_stats_as_built_fragment(s: St, a: Action)
    requires
        agg_exact(s),
        snaps_exact(s),
        as_built_fragment(s, a),
    ensures
        agg_exact(step(s, a, as_built())),
        snaps_exact(step(s, a, as_built())),
{
    lemma_step_stats(s, a, as_built());
}

/// THEOREM (repaired, statistics): with the structural step first (S2), counters a rollback takes back, and an
/// "update" that rebuilds its bucket (Q1 option b), EVERY step — any mode, any throw, any rollback, any
/// changeset — keeps the statistics exact.
pub proof fn theorem_stats_repaired_total(s: St, a: Action)
    requires
        agg_exact(s),
        snaps_exact(s),
    ensures
        agg_exact(step(s, a, repaired())),
        snaps_exact(step(s, a, repaired())),
{
    lemma_step_stats(s, a, repaired());
}


// ============================================================================ bulk path (L2)

pub struct Edge {
    pub c: Coord,
    pub w: int,
}

pub struct Counts {
    pub st: St,
    pub written: int,
    pub collided: int,
    pub skipped: int,
    pub threw: bool,
}

/// TemporalIndex.BulkInsertCounts (:151-182): WriteStores per edge in order (one mode for the batch); a throw
/// leaves the edges before it written and propagates (no transaction).
pub open spec fn bulk_counts(s: St, es: Seq<Edge>, mode: Mode, fs: Seq<Fail>, v: Variant) -> Counts
    decreases es.len(),
{
    if es.len() == 0 {
        Counts { st: s, written: 0, collided: 0, skipped: 0, threw: false }
    } else {
        let f = if fs.len() > 0 { fs[0] } else { Fail::No };
        let (s1, r) = write_stores(s, es[0].c, es[0].w, None, mode, f, v);
        if r == WRes::Threw {
            Counts { st: s1, written: 0, collided: 0, skipped: 0, threw: true }
        } else {
            let rest = bulk_counts(s1, es.subrange(1, es.len() as int), mode,
                if fs.len() > 0 { fs.subrange(1, fs.len() as int) } else { fs }, v);
            Counts {
                st: rest.st,
                written: rest.written + if r == WRes::Written { 1int } else { 0int },
                collided: rest.collided + if r == WRes::Collided { 1int } else { 0int },
                skipped: rest.skipped + if r == WRes::Skipped { 1int } else { 0int },
                threw: rest.threw,
            }
        }
    }
}

/// The per-edge fallback of iris_sql_store.bulk_write_temporal_edges (:2759-2785): every edge of the batch is
/// sent again through write_temporal_edge → InsertEdge, which answers 1 for written, skip and collision; an edge
/// without an error counts as "inserted"; the result has only the "inserted" column.
pub open spec fn fallback(s: St, es: Seq<Edge>, mode: Mode, fs: Seq<Fail>, v: Variant) -> (St, int, bool)
    decreases es.len(),
{
    if es.len() == 0 {
        (s, 0, false)
    } else {
        let f = if fs.len() > 0 { fs[0] } else { Fail::No };
        let (s1, r) = write_stores(s, es[0].c, es[0].w, None, mode, f, v);
        let (s2, n, err) = fallback(s1, es.subrange(1, es.len() as int), mode,
            if fs.len() > 0 { fs.subrange(1, fs.len() as int) } else { fs }, v);
        (s2, n + if r == WRes::Threw { 0int } else { 1int }, err || r == WRes::Threw)
    }
}

/// bulk_create_edges_temporal → bulk_write_temporal_edges: BulkInsertCounts; on its exception the fallback.
/// Returns (state, written, collisions, error).
pub open spec fn bulk_write(s: St, es: Seq<Edge>, mode: Mode, fs1: Seq<Fail>, fs2: Seq<Fail>, v: Variant) -> (St, int, int, bool) {
    let r = bulk_counts(s, es, mode, fs1, v);
    if !r.threw {
        (r.st, r.written, r.collided, false)
    } else {
        let (s2, n, err) = fallback(r.st, es, mode, fs2, v);
        (s2, n, 0, err)
    }
}

/// FR-004 (batch size): BulkInsertCounts is a left fold of WriteStores, so splitting a batch that does not throw
/// leaves the same stores (the per-batch node memory pNodes only skips INSERTs of rows that exist: premise P-NODES).
pub proof fn lemma_batch_split(s: St, a: Seq<Edge>, b: Seq<Edge>, mode: Mode, v: Variant)
    requires
        !bulk_counts(s, a, mode, Seq::empty(), v).threw,
    ensures
        bulk_counts(s, a + b, mode, Seq::empty(), v).st == bulk_counts(bulk_counts(s, a, mode, Seq::empty(), v).st, b, mode, Seq::empty(), v).st,
        bulk_counts(s, a + b, mode, Seq::empty(), v).threw == bulk_counts(bulk_counts(s, a, mode, Seq::empty(), v).st, b, mode, Seq::empty(), v).threw,
    decreases a.len(),
{
    if a.len() == 0 {
        assert(a + b =~= b);
    } else {
        let (s1, r) = write_stores(s, a[0].c, a[0].w, None, mode, Fail::No, v);
        assert((a + b)[0] == a[0]);
        assert((a + b).subrange(1, (a + b).len() as int) =~= a.subrange(1, a.len() as int) + b);
        lemma_batch_split(s1, a.subrange(1, a.len() as int), b, mode, v);
    }
}

// ============================================================================ witnesses (statistics)

pub open spec fn empty_st() -> St {
    St {
        tout: Map::empty(), eprop: Map::empty(), bucket: Map::empty(), cnt: Map::empty(), sum: Map::empty(),
        rows: Map::empty(), nodes: Set::empty(), optout: Set::empty(), gov_nodes: Set::empty(),
        gov_rels: Set::empty(), purged: Set::empty(), txn: Seq::empty(), plans: Map::empty(),
    }
}

/// (ts 600, s 1, p 2, o 3) in the default graph: bucket 2.
pub open spec fn c1() -> Coord { Coord { g: 0, ts: 600, s: 1, p: 2, o: 3 } }

pub proof fn lemma_single(c: Coord, w: int)
    ensures
        aset(Map::empty().insert(c, w), akey(c)) == set![c],
        aset(Map::empty().insert(c, w), akey(c)).len() == 1,
        bset(Map::empty().insert(c, w), bkey(c)).len() == 1,
        wsum(aset(Map::empty().insert(c, w), akey(c)), Map::empty().insert(c, w)) == w,
{
    let m = Map::<Coord, int>::empty().insert(c, w);
    assert(aset(m, akey(c)) =~= set![c]);
    assert(bset(m, bkey(c)) =~= set![c]);
    assert(Set::<Coord>::empty().insert(c) == set![c]);
    lemma_wsum_insert(Set::<Coord>::empty(), m, c);
}

/// A state whose statistics are not exact at akey(c), with the purge ghost empty.
pub open spec fn count_off(s: St, c: Coord) -> bool {
    get0(s.cnt, akey(c)) != aset(s.tout, akey(c)).len() as int
}

pub proof fn lemma_count_off_breaks(s: St, c: Coord)
    requires
        count_off(s, c),
        s.purged == Set::<Coord>::empty(),
    ensures
        !agg_exact(s),
{
    assert(!cut(snap(s).purged, akey(c)));
    assert(get0(snap(s).cnt, akey(c)) != aset(snap(s).tout, akey(c)).len() as int);
}

pub proof fn lemma_bucket_off_breaks(s: St, c: Coord)
    requires
        get0(s.bucket, bkey(c)) != bset(s.tout, bkey(c)).len() as int,
        s.purged == Set::<Coord>::empty(),
    ensures
        !agg_exact(s),
{
    assert(!bcut(snap(s).purged, bkey(c)));
    assert(get0(snap(s).bucket, bkey(c)) != bset(snap(s).tout, bkey(c)).len() as int);
}

/// W-F1 — "update" at an occupied coordinate (TemporalIndex.cls:82-83, no early return) counts the edge again:
/// one raw edge of weight 9, tagg count 2 and sum 11, bucket 2. Neither the documented "original value"
/// (temporal.py:273-279: count 1, sum 2; CHANGELOG "not adjusted") nor the raw store (count 1, sum 9) holds.
/// A later DeleteTemporalEdge rebuilds tagg but leaves bucket 1 over no edge at all.
pub proof fn witness_update_double_counts() {
    let v = as_built();
    let c = c1();
    let s0 = empty_st();
    let (s1, r1) = write_stores(s0, c, 2, None, Mode::Insert, Fail::No, v);
    assert(r1 == WRes::Written);
    assert(s1.tout == Map::<Coord, int>::empty().insert(c, 2));
    assert(get0(s1.cnt, akey(c)) == 1 && get0(s1.sum, akey(c)) == 2 && get0(s1.bucket, bkey(c)) == 1);
    let (s2, r2) = write_stores(s1, c, 9, None, Mode::Update, Fail::No, v);
    assert(r2 == WRes::Written);
    assert(s2.tout =~= Map::<Coord, int>::empty().insert(c, 9));
    lemma_single(c, 9);
    assert(aset(s2.tout, akey(c)).len() == 1);
    assert(wsum(aset(s2.tout, akey(c)), s2.tout) == 9);
    assert(get0(s2.cnt, akey(c)) == 2);
    assert(get0(s2.sum, akey(c)) == 11);
    assert(get0(s2.bucket, bkey(c)) == 2);
    assert(s2.purged == Set::<Coord>::empty());
    lemma_count_off_breaks(s2, c);
    // the documented reading (aggregates keep the original value: count 1, sum 2) fails as well
    assert(get0(s2.cnt, akey(c)) != 1 && get0(s2.sum, akey(c)) != 2);
    // delete the only edge: tagg is rebuilt (gone), the per-source bucket count stays at 1
    let (s3, d) = delete_temporal(s2, c);
    assert(d);
    assert(s3.tout =~= Map::<Coord, int>::empty());
    assert(bset(s3.tout, bkey(c)) =~= Set::<Coord>::empty());
    assert(get0(s3.bucket, bkey(c)) == 1);
    lemma_bucket_off_breaks(s3, c);
}

/// W-F2 — AssertTemporalRow throws after tout/tin/tlast/bucket were Set (WriteStores :95-111, no transaction):
/// one raw edge, bucket 1, no tagg, no row. The retry in "insert" mode is a collision (:84-85) and changes
/// nothing, so the row and the aggregates are never written; a retry in "update" mode writes them but counts
/// the bucket twice.
pub proof fn witness_partial_write_is_not_repaired_by_retry() {
    let v = as_built();
    let c = c1();
    let s0 = empty_st();
    let (s1, r1) = write_stores(s0, c, 2, None, Mode::Insert, Fail::BeforeNodes, v);
    assert(row_step_fails(s0, c, Fail::BeforeNodes));
    assert(r1 == WRes::Threw);
    assert(s1.tout == Map::<Coord, int>::empty().insert(c, 2));
    lemma_single(c, 2);
    assert(get0(s1.cnt, akey(c)) == 0);
    assert(get0(s1.bucket, bkey(c)) == 1);
    assert(!s1.rows.contains_key(tri(c)));
    lemma_count_off_breaks(s1, c);
    // ADR-0009: a temporal edge of a structural predicate implies its row — here a timestamp with no row
    assert(has_ts(s1.tout, tri(c)) && structural(s1, c.g, c.p) && !s1.rows.contains_key(tri(c)));
    // retry, insert mode, the cause gone: a collision, nothing changes
    let (s2, r2) = write_stores(s1, c, 2, None, Mode::Insert, Fail::No, v);
    assert(r2 == WRes::Collided && s2 == s1);
    // retry, update mode: the row and tagg appear, the bucket counts the edge twice
    let (s3, r3) = write_stores(s1, c, 2, None, Mode::Update, Fail::No, v);
    assert(r3 == WRes::Written);
    assert(s3.rows.contains_key(tri(c)));
    assert(s3.tout =~= Map::<Coord, int>::empty().insert(c, 2));
    assert(get0(s3.bucket, bkey(c)) == 2);
    lemma_bucket_off_breaks(s3, c);
}

/// Under S2 (structural step first) the same throw leaves no temporal store, and the retry writes everything.
pub proof fn witness_assert_first_repairs_the_retry() {
    let v = Variant { assert_first: true, ..as_built() };
    let c = c1();
    let s0 = empty_st();
    let (s1, r1) = write_stores(s0, c, 2, None, Mode::Insert, Fail::BeforeNodes, v);
    assert(r1 == WRes::Threw);
    assert(s1 == s0);
    let (s2, r2) = write_stores(s1, c, 2, None, Mode::Insert, Fail::No, v);
    assert(r2 == WRes::Written);
    assert(s2.rows.contains_key(tri(c)) && s2.rows[tri(c)]);
    assert(s2.tout == Map::<Coord, int>::empty().insert(c, 2));
    lemma_single(c, 2);
    assert(get0(s2.cnt, akey(c)) == 1 && get0(s2.sum, akey(c)) == 2 && get0(s2.bucket, bkey(c)) == 1);
}

/// W-F2b — the bulk fallback hides the partial write. Batch [e0, e1], mode "insert": BulkInsertCounts writes e0,
/// e1's structural step throws; the fallback re-sends both, both are collisions that InsertEdge answers 1 for,
/// and bulk_create_edges_temporal returns written=2, collisions=0, no error — while e1 has no row and no
/// aggregate. FR-003 ("report written and collision counts separately") and L1-AGG both fail.
pub proof fn witness_bulk_fallback_reports_success() {
    reveal_with_fuel(bulk_counts, 3);
    reveal_with_fuel(fallback, 3);
    let v = as_built();
    let c0 = Coord { g: 0, ts: 600, s: 1, p: 2, o: 3 };
    let c1 = Coord { g: 0, ts: 601, s: 1, p: 2, o: 4 };
    let es = seq![Edge { c: c0, w: 1 }, Edge { c: c1, w: 1 }];
    let fs1 = seq![Fail::No, Fail::BeforeNodes];
    let fs2 = seq![Fail::No, Fail::No];
    let s0 = empty_st();
    let (sa, ra) = write_stores(s0, c0, 1, None, Mode::Insert, Fail::No, v);
    assert(ra == WRes::Written);
    assert(!sa.rows.contains_key(tri(c1))) by { assert(tri(c1) != tri(c0)); }
    let (sb, rb) = write_stores(sa, c1, 1, None, Mode::Insert, Fail::BeforeNodes, v);
    assert(rb == WRes::Threw);
    assert(es.subrange(1, 2) =~= seq![Edge { c: c1, w: 1 }]);
    assert(fs1.subrange(1, 2) =~= seq![Fail::BeforeNodes]);
    let first = bulk_counts(s0, es, Mode::Insert, fs1, v);
    assert(first.threw && first.st == sb);
    // fallback: both edges are collisions now
    let (sc, rc) = write_stores(sb, c0, 1, None, Mode::Insert, Fail::No, v);
    assert(rc == WRes::Collided && sc == sb);
    let (sd, rd) = write_stores(sc, c1, 1, None, Mode::Insert, Fail::No, v);
    assert(sb.tout.contains_key(c1));
    assert(rd == WRes::Collided && sd == sb);
    assert(fs2.subrange(1, 2) =~= seq![Fail::No]);
    assert(seq![Edge { c: c1, w: 1 }].subrange(1, 1) =~= Seq::<Edge>::empty());
    assert(seq![Fail::No].subrange(1, 1) =~= Seq::<Fail>::empty());
    let (sf, n, err) = fallback(sb, es, Mode::Insert, fs2, v);
    assert(fallback(sb, Seq::<Edge>::empty(), Mode::Insert, Seq::<Fail>::empty(), v) == (sb, 0int, false));
    assert(fallback(sb, seq![Edge { c: c1, w: 1 }], Mode::Insert, seq![Fail::No], v) == (sb, 1int, false));
    assert(sf == sb && n == 2 && !err);
    let out = bulk_write(s0, es, Mode::Insert, fs1, fs2, v);
    assert(out == (sb, 2int, 0int, false));
    // what the caller is told vs what the stores hold for e1
    assert(!sb.rows.contains_key(tri(c1)));
    assert(aset(sb.tout, akey(c1)).contains(c1));
    assert(get0(sb.cnt, akey(c1)) == 1);  // c0's count: c0 and c1 share the key (s 1, p 2, bucket 2)
    assert(sb.tout.dom() =~= set![c0, c1]);
    assert(aset(sb.tout, akey(c1)) =~= set![c0, c1]);
    assert(set![c0, c1].len() == 2) by {
        assert(set![c0, c1] == Set::<Coord>::empty().insert(c0).insert(c1));
        assert(!Set::<Coord>::empty().insert(c0).contains(c1));
    }
    assert(sb.purged == Set::<Coord>::empty());
    lemma_count_off_breaks(sb, c1);
}

/// The batch [same coordinates, two weights] in "insert" mode: 1 written, 1 collision, the first weight stays
/// (test_254_collisions_e2e). A valid outcome the model keeps.
pub proof fn witness_same_batch_collision_first_write_wins() {
    reveal_with_fuel(bulk_counts, 3);
    let v = as_built();
    let c = c1();
    let es = seq![Edge { c, w: 2 }, Edge { c, w: 9 }];
    let s0 = empty_st();
    let (s1, r1) = write_stores(s0, c, 2, None, Mode::Insert, Fail::No, v);
    assert(r1 == WRes::Written);
    assert(es.subrange(1, 2) =~= seq![Edge { c, w: 9 }]);
    assert(seq![Edge { c, w: 9 }].subrange(1, 1) =~= Seq::<Edge>::empty());
    let r = bulk_counts(s0, es, Mode::Insert, Seq::empty(), v);
    assert(bulk_counts(s1, seq![Edge { c, w: 9 }], Mode::Insert, Seq::empty(), v).st == s1);
    assert(r.written == 1 && r.collided == 1 && !r.threw && r.st == s1);
    assert(r.st.tout[c] == 2);
}

/// W-F3a — a changeset [create_temporal_edge, create_relationship(to an unknown node)]: the second op is refused,
/// Commit takes back its level (TROLLBACK 1), the Sets go and the $Increments stay: no raw edge, tagg count 1,
/// bucket 1. Committing the temporal edge again then counts it twice. The same holds for BlocksCommit and for a
/// throw caught by Commit.
pub proof fn witness_refused_changeset_leaves_counts() {
    reveal_with_fuel(apply_ops, 3);
    let v = as_built();
    let c = c1();
    let s0 = St { nodes: set![(0int, 1int), (0int, 3int)], gov_nodes: set![1int, 3int], ..empty_st() };
    let bad = LOp::CreateRel { t: Triple { g: 0, s: 1, p: 7, o: 99 } };
    let tw = LOp::Temporal { c, w: 2, mode: Mode::Insert, f: Fail::No };
    let ops = seq![tw, bad];
    let sa = tstart(s0);
    let (sb, rb) = apply_op(sa, tw, v);
    assert(rb == Out::Ok);
    assert(get0(sb.cnt, akey(c)) == 1 && get0(sb.bucket, bkey(c)) == 1);
    assert(!node_known(sb, 99)) by {
        assert forall|g: int| !sb.nodes.contains((g, 99int)) by {}
    }
    let (sc, rc) = apply_op(sb, bad, v);
    assert(rc == Out::Refused);
    assert(ops.subrange(1, 2) =~= seq![bad]);
    assert(seq![bad].subrange(1, 1) =~= Seq::<LOp>::empty());
    assert(apply_ops(sa, ops, v) == (sc, Out::Refused));
    let (s1, r1) = commit(s0, ops, false, v);
    assert(r1 == Out::Refused);
    assert(s1.tout == s0.tout && s1.rows == s0.rows && s1.txn == s0.txn);
    assert(s1.tout =~= Map::<Coord, int>::empty());
    assert(aset(s1.tout, akey(c)) =~= Set::<Coord>::empty());
    assert(get0(s1.cnt, akey(c)) == 1 && get0(s1.sum, akey(c)) == 2 && get0(s1.bucket, bkey(c)) == 1);
    lemma_count_off_breaks(s1, c);
    // the retry commits: one raw edge, counted twice
    let (s2, r2) = commit(s1, seq![tw], false, v);
    assert(seq![tw].subrange(1, 1) =~= Seq::<LOp>::empty());
    assert(r2 == Out::Ok);
    assert(s2.tout =~= Map::<Coord, int>::empty().insert(c, 2));
    lemma_single(c, 2);
    assert(get0(s2.cnt, akey(c)) == 2 && get0(s2.sum, akey(c)) == 4 && get0(s2.bucket, bkey(c)) == 2);
    lemma_count_off_breaks(s2, c);
}

/// W-F3b — BlocksCommit (a redaction in progress refuses the records) after the temporal op: the same residue.
pub proof fn witness_blocked_changeset_leaves_counts() {
    reveal_with_fuel(apply_ops, 3);
    let v = as_built();
    let c = c1();
    let s0 = empty_st();
    let tw = LOp::Temporal { c, w: 2, mode: Mode::Insert, f: Fail::No };
    assert(seq![tw].subrange(1, 1) =~= Seq::<LOp>::empty());
    let (s1, r1) = commit(s0, seq![tw], true, v);
    assert(r1 == Out::Refused);
    assert(s1.tout =~= Map::<Coord, int>::empty());
    assert(aset(s1.tout, akey(c)) =~= Set::<Coord>::empty());
    assert(get0(s1.cnt, akey(c)) == 1);
    lemma_count_off_breaks(s1, c);
}

/// W-F3c — a throw from the structural step inside a changeset: Commit's Catch rolls back; bucket stays 1.
pub proof fn witness_throw_in_changeset_leaves_bucket() {
    reveal_with_fuel(apply_ops, 3);
    let v = as_built();
    let c = c1();
    let s0 = empty_st();
    let tw = LOp::Temporal { c, w: 2, mode: Mode::Update, f: Fail::BeforeNodes };
    assert(seq![tw].subrange(1, 1) =~= Seq::<LOp>::empty());
    let (s1, r1) = commit(s0, seq![tw], false, v);
    assert(r1 == Out::Threw);
    assert(s1.tout =~= Map::<Coord, int>::empty());
    assert(bset(s1.tout, bkey(c)) =~= Set::<Coord>::empty());
    assert(get0(s1.bucket, bkey(c)) == 1);
    lemma_bucket_off_breaks(s1, c);
}

/// W-F3d — a direct create_edge_temporal inside the caller's transaction (same server process), then the
/// caller's ROLLBACK: no raw edge, tagg count 1, bucket 1.
pub proof fn witness_caller_rollback_leaves_counts() {
    let v = as_built();
    let c = c1();
    let s0 = empty_st();
    let s1 = step(s0, Action::Begin, v);
    let s2 = step(s1, Action::Write { c, w: 2, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(get0(s2.cnt, akey(c)) == 1);
    let s3 = step(s2, Action::Rollback, v);
    assert(s3.tout =~= Map::<Coord, int>::empty());
    assert(aset(s3.tout, akey(c)) =~= Set::<Coord>::empty());
    assert(get0(s3.cnt, akey(c)) == 1 && get0(s3.bucket, bkey(c)) == 1);
    lemma_count_off_breaks(s3, c);
}

/// Control (valid outcome): if TROLLBACK took the counters back, the refused changeset would leave the
/// statistics exact — the violation rests on premise P-INCR, nothing else.
pub proof fn witness_counters_undone_keep_exact() {
    reveal_with_fuel(apply_ops, 3);
    let v = Variant { incr_undone: true, ..as_built() };
    let c = c1();
    let s0 = empty_st();
    let tw = LOp::Temporal { c, w: 2, mode: Mode::Insert, f: Fail::No };
    assert(seq![tw].subrange(1, 1) =~= Seq::<LOp>::empty());
    let (s1, r1) = commit(s0, seq![tw], true, v);
    assert(r1 == Out::Refused);
    assert(s1.tout == s0.tout && s1.cnt == s0.cnt && s1.sum == s0.sum && s1.bucket == s0.bucket && s1.purged == s0.purged);
    assert(agg_exact(s0)) by {
        assert forall|k: AKey| !cut(snap(s0).purged, k) implies (#[trigger] snap(s0).cnt.contains_key(k) <==> aset(snap(s0).tout, k).len() > 0) by {
            assert(aset(snap(s0).tout, k) =~= Set::<Coord>::empty());
        }
        assert forall|k: BKey| !bcut(snap(s0).purged, k) implies (#[trigger] snap(s0).bucket.contains_key(k) <==> bset(snap(s0).tout, k).len() > 0) by {
            assert(bset(snap(s0).tout, k) =~= Set::<Coord>::empty());
        }
        assert forall|k: AKey| #![trigger get0(snap(s0).cnt, k)] #![trigger get0(snap(s0).sum, k)] !cut(snap(s0).purged, k)
            implies get0(snap(s0).cnt, k) == aset(snap(s0).tout, k).len() as int
                && get0(snap(s0).sum, k) == wsum(aset(snap(s0).tout, k), snap(s0).tout) by {
            assert(aset(snap(s0).tout, k) =~= Set::<Coord>::empty());
        }
        assert forall|k: BKey| !bcut(snap(s0).purged, k) implies #[trigger] get0(snap(s0).bucket, k) == bset(snap(s0).tout, k).len() as int by {
            assert(bset(snap(s0).tout, k) =~= Set::<Coord>::empty());
        }
    }
    lemma_exact_frame(snap(s0), snap(s1));
    assert(agg_exact(s1));
}

/// The commit boundary (Ledger.Commit): a refused, blocked or throwing changeset restores every journaled store
/// — raw edges, attributes, rows, nodes, registry, ledger state — whatever its ops did; the $Increment counters are
/// restored only if TROLLBACK took them back. So the counters are the whole residue (F3).
pub proof fn lemma_refused_commit_restores_journaled(s: St, ops: Seq<LOp>, blocked: bool, v: Variant)
    requires
        commit(s, ops, blocked, v).1 != Out::Ok,
    ensures
        commit(s, ops, blocked, v).0.tout == s.tout,
        commit(s, ops, blocked, v).0.eprop == s.eprop,
        commit(s, ops, blocked, v).0.rows == s.rows,
        commit(s, ops, blocked, v).0.nodes == s.nodes,
        commit(s, ops, blocked, v).0.optout == s.optout,
        commit(s, ops, blocked, v).0.gov_nodes == s.gov_nodes,
        commit(s, ops, blocked, v).0.gov_rels == s.gov_rels,
        commit(s, ops, blocked, v).0.txn == s.txn,
        v.incr_undone ==> commit(s, ops, blocked, v).0.cnt == s.cnt && commit(s, ops, blocked, v).0.bucket == s.bucket,
{
    let s0 = tstart(s);
    lemma_apply_ops_txn(s0, ops, v);
    let s1 = apply_ops(s0, ops, v).0;
    assert(s1.txn == s.txn.push(snap(s)));
    assert(s1.txn.last() == snap(s));
    assert(s1.txn.drop_last() =~= s.txn);
}

/// W-F3e — the caller's ROLLBACK of a ledger commit nested in its transaction (4.7.0): the revision and the raw
/// edge go, the counters stay.
pub proof fn witness_caller_rollback_of_ledger_commit_leaves_counts() {
    reveal_with_fuel(apply_ops, 2);
    let v = as_built();
    let c = c1();
    let s0 = empty_st();
    let tw = LOp::Temporal { c, w: 2, mode: Mode::Insert, f: Fail::No };
    assert(seq![tw].subrange(1, 1) =~= Seq::<LOp>::empty());
    let s1 = step(s0, Action::Begin, v);
    let s2 = step(s1, Action::Commit { ops: seq![tw], blocked: false }, v);
    assert(commit(s1, seq![tw], false, v).1 == Out::Ok);
    assert(s2.tout.contains_key(c) && s2.txn.len() == 1);
    let s3 = step(s2, Action::Rollback, v);
    assert(s3.tout =~= Map::<Coord, int>::empty());
    assert(aset(s3.tout, akey(c)) =~= Set::<Coord>::empty());
    assert(get0(s3.cnt, akey(c)) == 1 && get0(s3.bucket, bkey(c)) == 1);
    lemma_count_off_breaks(s3, c);
}

/// W-F7 — two "insert" writers at one free coordinate: both pass the $Data guard (no lock between :84 and the
/// Sets), both count. One raw edge (the last weight), tagg count 2.
pub proof fn witness_concurrent_inserts_double_count() {
    let v = as_built();
    let c = c1();
    let s0 = empty_st();
    assert(!guard_stops(s0, c, Mode::Insert));  // writer 1 reads $Data(tout) = 0
    assert(!guard_stops(s0, c, Mode::Insert));  // writer 2 reads $Data(tout) = 0 before writer 1's Set
    let (s1, _) = write_effect(s0, c, 2, None, Mode::Insert, Fail::No, v);
    let (s2, _) = write_effect(s1, c, 9, None, Mode::Insert, Fail::No, v);
    assert(s2.tout =~= Map::<Coord, int>::empty().insert(c, 9));
    lemma_single(c, 9);
    assert(get0(s2.cnt, akey(c)) == 2);
    lemma_count_off_breaks(s2, c);
}


// ============================================================================ L1 — the marked structural row (ADR-0009, ADR-0015)

/// L1-ROW (ADR-0009 Decision + spec 254 amendment "the implication ends when the last timestamp goes";
/// ADR-0015 "the purge leaves the old rows of a predicate registered later" until the drop): a marked row says
/// "this edge exists at some time", so its triple has a timestamp — unless its predicate is registered
/// temporal-only in its graph and the row awaits drop_temporal_structural_rows.
pub open spec fn rows_ok_parts(tout: Map<Coord, int>, rows: Map<Triple, bool>, optout: Set<(int, int)>) -> bool {
    forall|t: Triple| #[trigger] rows.contains_key(t) && rows[t] ==> has_ts(tout, t) || optout.contains((t.g, t.p))
}

pub open spec fn rows_ok(s: St) -> bool {
    rows_ok_parts(s.tout, s.rows, s.optout)
}

pub open spec fn snaps_rows_ok(s: St) -> bool {
    forall|i: int| 0 <= i < s.txn.len() ==> rows_ok_parts(#[trigger] s.txn[i].tout, s.txn[i].rows, s.txn[i].optout)
}

/// The shape of every write: the registry is untouched, timestamps only grow, an existing row keeps its
/// marker, and a new row is the written triple's marked row.
pub proof fn lemma_write_shape(s: St, c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail, v: Variant)
    ensures
        ({
            let s2 = write_stores(s, c, w, attrs, mode, f, v).0;
            &&& s2.optout == s.optout
            &&& s2.txn == s.txn
            &&& forall|x: Coord| s.tout.contains_key(x) ==> #[trigger] s2.tout.contains_key(x)
            &&& forall|t: Triple| #[trigger] s.rows.contains_key(t) ==> s2.rows.contains_key(t) && s2.rows[t] == s.rows[t]
            &&& forall|t: Triple| #[trigger] s2.rows.contains_key(t) && !s.rows.contains_key(t) ==>
                    t == tri(c) && s2.rows[t] && s2.tout.contains_key(c) && structural(s, c.g, c.p)
            &&& (!structural(s, c.g, c.p) ==> s2.rows == s.rows && s2.nodes == s.nodes)
        }),
{
}

pub proof fn lemma_has_ts_grow(t1: Map<Coord, int>, t2: Map<Coord, int>, t: Triple)
    requires
        has_ts(t1, t),
        forall|x: Coord| t1.contains_key(x) ==> #[trigger] t2.contains_key(x),
    ensures
        has_ts(t2, t),
{
    let x = choose|x: Coord| #[trigger] t1.contains_key(x) && tri(x) == t;
    assert(t2.contains_key(x));
}

pub proof fn lemma_write_rows(s: St, c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail, v: Variant)
    requires
        rows_ok(s),
    ensures
        rows_ok(write_stores(s, c, w, attrs, mode, f, v).0),
{
    lemma_write_shape(s, c, w, attrs, mode, f, v);
    let s2 = write_stores(s, c, w, attrs, mode, f, v).0;
    assert forall|t: Triple| #[trigger] s2.rows.contains_key(t) && s2.rows[t] implies has_ts(s2.tout, t) || s2.optout.contains((t.g, t.p)) by {
        if s.rows.contains_key(t) {
            if !s.optout.contains((t.g, t.p)) {
                lemma_has_ts_grow(s.tout, s2.tout, t);
            }
        } else {
            assert(s2.tout.contains_key(c) && tri(c) == t);
        }
    }
}

pub proof fn lemma_delete_rows(s: St, c: Coord)
    requires
        rows_ok(s),
    ensures
        rows_ok(delete_temporal(s, c).0),
        txn_frame(delete_temporal(s, c).0.txn, s.txn),
        delete_temporal(s, c).0.optout == s.optout,
{
    if !s.tout.contains_key(c) {
        lemma_txn_frame_refl(s.txn);
        return;
    }
    lemma_remove_temporal_row_shape(s, c);
    let s1 = remove_temporal_row(s, c);
    let s2 = delete_temporal(s, c).0;
    assert(s2.txn == s1.txn);
    assert(s1.tout == s.tout.remove(c));
    assert(s1.rows == s.rows);
    assert forall|t: Triple| #[trigger] s2.rows.contains_key(t) && s2.rows[t] implies has_ts(s2.tout, t) || s2.optout.contains((t.g, t.p)) by {
        assert(s.rows.contains_key(t) && s.rows[t]);
        if t != tri(c) && has_ts(s.tout, t) {
            let x = choose|x: Coord| #[trigger] s.tout.contains_key(x) && tri(x) == t;
            assert(x != c);
            assert(s2.tout.contains_key(x));
        }
    }
}

pub proof fn lemma_purge_rows(s: St, g: int, lo: int, hi: int, stop: bool)
    requires
        rows_ok(s),
    ensures
        rows_ok(purge(s, g, lo, hi, stop)),
        purge(s, g, lo, hi, stop).txn == s.txn,
        purge(s, g, lo, hi, stop).optout == s.optout,
{
    let s2 = purge(s, g, lo, hi, stop);
    let t2 = tout_after_purge(s, g, lo, hi);
    assert(t2.dom() == s.tout.dom().filter(|c: Coord| !in_range(c, g, lo, hi)));
    assert forall|t: Triple| #[trigger] s2.rows.contains_key(t) && s2.rows[t] implies has_ts(s2.tout, t) || s2.optout.contains((t.g, t.p)) by {
        assert(s.rows.contains_key(t) && s.rows[t] && !purge_doomed(s, t, g, lo, hi));
        if !stop && !s.optout.contains((t.g, t.p)) {
            assert(has_ts(s.tout, t));
            let x = choose|x: Coord| #[trigger] s.tout.contains_key(x) && tri(x) == t;
            if !has_ts(t2, t) {
                // every timestamp of t was in the range, so t was a candidate and is doomed
                assert(in_range(x, g, lo, hi)) by {
                    if !in_range(x, g, lo, hi) { assert(t2.contains_key(x)); }
                }
                assert(purge_candidate(s, t, g, lo, hi));
                assert(false);
            }
        }
    }
}

pub proof fn lemma_backfill_rows(s: St, g: int, p: int)
    requires
        rows_ok(s),
    ensures
        rows_ok(backfill(s, g, p)),
{
    if structural(s, g, p) {
        let s2 = backfill(s, g, p);
        let add = backfill_set(s, g, p);
        assert forall|t: Triple| #[trigger] s2.rows.contains_key(t) && s2.rows[t] implies has_ts(s2.tout, t) || s2.optout.contains((t.g, t.p)) by {
            if !s.rows.contains_key(t) {
                assert(add.map(|c: Coord| tri(c)).contains(t));
                let x = choose|x: Coord| add.contains(x) && t == tri(x);
                assert(s.tout.contains_key(x));
            }
        }
    }
}

pub proof fn lemma_apply_ops_rows(s: St, ops: Seq<LOp>, v: Variant)
    requires
        rows_ok(s),
    ensures
        rows_ok(apply_ops(s, ops, v).0),
    decreases ops.len(),
{
    if ops.len() > 0 {
        let op = ops[0];
        let s1 = apply_op(s, op, v).0;
        match op {
            LOp::Temporal { c, w, mode, f } => { lemma_write_rows(s, c, w, None, mode, f, v); },
            LOp::CreateRel { t } => {
                assert forall|t2: Triple| #[trigger] s1.rows.contains_key(t2) && s1.rows[t2] implies has_ts(s1.tout, t2) || s1.optout.contains((t2.g, t2.p)) by {
                    assert(s.rows.contains_key(t2) && s.rows[t2]);
                }
            },
            _ => {},
        }
        lemma_apply_ops_rows(s1, ops.subrange(1, ops.len() as int), v);
    }
}

pub open spec fn rows_step_ok(a: Action, v: Variant) -> bool {
    match a {
        Action::SetStructural { g, p, enabled } => !enabled || v.optin_guard,
        _ => true,
    }
}

pub proof fn lemma_step_rows(s: St, a: Action, v: Variant)
    requires
        rows_ok(s),
        snaps_rows_ok(s),
        rows_step_ok(a, v),
        !phased(a),
    ensures
        rows_ok(step(s, a, v)),
        snaps_rows_ok(step(s, a, v)),
{
    let s2 = step(s, a, v);
    match a {
        Action::Write { c, w, attrs, mode, f } => {
            lemma_write_rows(s, c, w, attrs, mode, f, v);
            lemma_write_shape(s, c, w, attrs, mode, f, v);
        },
        Action::Delete { c } => { lemma_delete_rows(s, c); lemma_snaps_rows_frame(s, s2); },
        Action::Purge { g, lo, hi, stop_after_rows } => { lemma_purge_rows(s, g, lo, hi, stop_after_rows); },
        Action::PurgeDecide { .. } | Action::DeleteDecide { .. } | Action::Retract { .. } | Action::PurgeKill { .. } => {},
        Action::CreateEdge { t } => {
            assert forall|t2: Triple| #[trigger] s2.rows.contains_key(t2) && s2.rows[t2] implies has_ts(s2.tout, t2) || s2.optout.contains((t2.g, t2.p)) by {
                assert(s.rows.contains_key(t2) && s.rows[t2]);
            }
        },
        Action::DeleteEdge { t } => {
            assert forall|t2: Triple| #[trigger] s2.rows.contains_key(t2) && s2.rows[t2] implies has_ts(s2.tout, t2) || s2.optout.contains((t2.g, t2.p)) by {
                assert(s.rows.contains_key(t2) && s.rows[t2]);
            }
        },
        Action::SetStructural { g, p, enabled } => {
            if enabled && !stranded(s, g, p) {
                assert forall|t: Triple| #[trigger] s2.rows.contains_key(t) && s2.rows[t] implies has_ts(s2.tout, t) || s2.optout.contains((t.g, t.p)) by {
                    if t.g == g && t.p == p && !has_ts(s.tout, t) {
                        assert(stranded(s, g, p));
                    }
                }
            }
        },
        Action::DropRows { g, p } => {
            if !structural(s, g, p) {
                assert forall|t: Triple| #[trigger] s2.rows.contains_key(t) && s2.rows[t] implies has_ts(s2.tout, t) || s2.optout.contains((t.g, t.p)) by {
                    assert(s.rows.contains_key(t) && s.rows[t]);
                }
            }
        },
        Action::Backfill { g, p } => { lemma_backfill_rows(s, g, p); },
        Action::Begin => {
            assert forall|i: int| 0 <= i < s2.txn.len() implies rows_ok_parts(#[trigger] s2.txn[i].tout, s2.txn[i].rows, s2.txn[i].optout) by {
                if i < s.txn.len() { assert(s2.txn[i] == s.txn[i]); } else { assert(s2.txn[i] == snap(s)); }
            }
        },
        Action::End => {
            assert forall|i: int| 0 <= i < s2.txn.len() implies rows_ok_parts(#[trigger] s2.txn[i].tout, s2.txn[i].rows, s2.txn[i].optout) by {
                assert(s2.txn[i] == s.txn[i]);
            }
        },
        Action::Rollback => {
            if s.txn.len() > 0 {
                assert(rows_ok_parts(s.txn[s.txn.len() - 1].tout, s.txn[s.txn.len() - 1].rows, s.txn[s.txn.len() - 1].optout));
                assert forall|i: int| 0 <= i < s2.txn.len() implies rows_ok_parts(#[trigger] s2.txn[i].tout, s2.txn[i].rows, s2.txn[i].optout) by {
                    assert(s2.txn[i] == s.txn[i]);
                }
            }
        },
        Action::Commit { ops, blocked } => {
            let s0 = tstart(s);
            lemma_apply_ops_txn(s0, ops, v);
            lemma_apply_ops_rows(s0, ops, v);
            let (s1, r) = apply_ops(s0, ops, v);
            assert(s1.txn == s.txn.push(snap(s)));
            if !(r == Out::Ok && !blocked) {
                assert(s1.txn.last() == snap(s));
            }
            assert forall|i: int| 0 <= i < s2.txn.len() implies rows_ok_parts(#[trigger] s2.txn[i].tout, s2.txn[i].rows, s2.txn[i].optout) by {
                assert(s2.txn[i] == s.txn[i]);
            }
        },
    }
}

/// THEOREM (as built, rows): every step except opting a predicate back in keeps L1-ROW — temporal writes
/// (any mode, a throw included: it leaves a timestamp without a row, never a row without a timestamp), delete,
/// purge (complete or stopped after its row step), explicit create/delete, opt-out, drop, backfill, transactions
/// and changesets.
pub proof fn theorem_rows_as_built(s: St, a: Action)
    requires
        rows_ok(s),
        snaps_rows_ok(s),
        !(a matches Action::SetStructural { enabled: true, .. }),
        !phased(a),
    ensures
        rows_ok(step(s, a, as_built())),
        snaps_rows_ok(step(s, a, as_built())),
{
    lemma_step_rows(s, a, as_built());
}

pub open spec fn guarded() -> Variant {
    Variant { optin_guard: true, ..as_built() }
}

/// THEOREM (Q4 repair, rows): when opting back in is refused while a marked row of the predicate has no
/// timestamp, EVERY step keeps L1-ROW.
pub proof fn theorem_rows_optin_guarded(s: St, a: Action)
    requires
        rows_ok(s),
        snaps_rows_ok(s),
        !phased(a),
    ensures
        rows_ok(step(s, a, guarded())),
        snaps_rows_ok(step(s, a, guarded())),
{
    lemma_step_rows(s, a, guarded());
}

// ---------------------------------------------------------------------------- the marker's lifecycle

pub open spec fn temporal_action(a: Action) -> bool {
    match a {
        Action::Write { .. } | Action::Delete { .. } | Action::Purge { .. } | Action::SetStructural { .. }
        | Action::DropRows { .. } | Action::Backfill { .. } | Action::PurgeDecide { .. } | Action::DeleteDecide { .. }
        | Action::Retract { .. } | Action::PurgeKill { .. } => true,
        _ => false,
    }
}

/// ADR-0009 / FR-002: no temporal operation removes an unmarked (explicit) row or marks an existing row; the
/// marker of a surviving row never changes under them. This includes the phased steps under any interleaving:
/// the retraction re-tests the marker when it runs.
pub proof fn lemma_temporal_ops_keep_explicit_rows(s: St, a: Action, v: Variant, t: Triple)
    requires
        temporal_action(a),
        s.rows.contains_key(t),
    ensures
        !s.rows[t] ==> step(s, a, v).rows.contains_key(t),
        step(s, a, v).rows.contains_key(t) ==> step(s, a, v).rows[t] == s.rows[t],
{
    match a {
        Action::Write { c, w, attrs, mode, f } => { lemma_write_shape(s, c, w, attrs, mode, f, v); },
        Action::Delete { c } => {
            if s.tout.contains_key(c) {
                lemma_remove_temporal_row_shape(s, c);
            }
        },
        Action::Purge { g, lo, hi, stop_after_rows } => {
            if !s.rows[t] {
                assert(!purge_doomed(s, t, g, lo, hi));
            }
        },
        Action::DeleteDecide { p, c } => {
            if !s.plans.contains_key(p) && s.tout.contains_key(c) {
                lemma_remove_temporal_row_shape(s, c);
            }
        },
        Action::PurgeKill { p } => {},
        Action::Backfill { g, p } => {},
        _ => {},
    }
}

/// ADR-0009: a marked row goes with the triple's last timestamp — by DeleteTemporalEdge or by a complete purge —
/// and at no other time.
pub proof fn lemma_marked_row_goes_with_last_timestamp(s: St, a: Action, v: Variant, t: Triple)
    requires
        (a matches Action::Delete { .. }) || (a matches Action::Purge { stop_after_rows: false, .. }),
        s.rows.contains_key(t),
        s.rows[t],
        !step(s, a, v).rows.contains_key(t),
    ensures
        !has_ts(step(s, a, v).tout, t),
{
    match a {
        Action::Delete { c } => {
            if s.tout.contains_key(c) {
                lemma_remove_temporal_row_shape(s, c);
            }
        },
        Action::Purge { g, lo, hi, stop_after_rows } => {
            assert(purge_doomed(s, t, g, lo, hi));
            assert(step(s, a, v).tout == tout_after_purge(s, g, lo, hi));
        },
        _ => {},
    }
}

/// ADR-0015: a write of a registered predicate writes no row and no node.
pub proof fn lemma_optout_write_writes_no_row(s: St, c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail, v: Variant)
    requires
        s.optout.contains((c.g, c.p)),
    ensures
        write_stores(s, c, w, attrs, mode, f, v).0.rows == s.rows,
        write_stores(s, c, w, attrs, mode, f, v).0.nodes == s.nodes,
{
    lemma_write_shape(s, c, w, attrs, mode, f, v);
}

/// ADR-0009: an explicit create clears the marker (whatever the registry says, ADR-0015:68-70), and the row is
/// then out of reach of every temporal operation.
pub proof fn lemma_explicit_create_clears_marker(s: St, t: Triple, a: Action, v: Variant)
    requires
        temporal_action(a),
    ensures
        create_edge(s, t).rows.contains_key(t),
        !create_edge(s, t).rows[t],
        step(create_edge(s, t), a, v).rows.contains_key(t),
        !step(create_edge(s, t), a, v).rows[t],
{
    lemma_temporal_ops_keep_explicit_rows(create_edge(s, t), a, v, t);
}

/// ADR-0009 "rows first": a purge stopped after its row step and run again lands the same state as one run.
pub proof fn lemma_purge_rerun_finishes(s: St, g: int, lo: int, hi: int)
    ensures
        purge(purge(s, g, lo, hi, true), g, lo, hi, false) == purge(s, g, lo, hi, false),
{
    let s1 = purge(s, g, lo, hi, true);
    assert(s1.tout == s.tout && s1.optout == s.optout && s1.eprop == s.eprop && s1.purged == s.purged);
    assert(tout_after_purge(s1, g, lo, hi) == tout_after_purge(s, g, lo, hi));
    assert forall|t: Triple| purge_candidate(s1, t, g, lo, hi) == purge_candidate(s, t, g, lo, hi) by {}
    let r2 = purge(s1, g, lo, hi, false).rows;
    assert forall|t: Triple| s1.rows.contains_key(t) implies !purge_doomed(s1, t, g, lo, hi) by {
        assert(!purge_doomed(s, t, g, lo, hi));
        assert(s1.rows[t] == s.rows[t]);
    }
    assert(r2 =~= s1.rows);
}

/// ADR-0015 (decided): "the purge leaves the old rows of a predicate registered later" — a registered
/// predicate's rows are not in the purge's retract set.
pub proof fn lemma_purge_leaves_registered_rows(s: St, t: Triple, g: int, lo: int, hi: int, stop: bool)
    requires
        s.rows.contains_key(t),
        s.optout.contains((t.g, t.p)),
    ensures
        purge(s, g, lo, hi, stop).rows.contains_key(t),
        purge(s, g, lo, hi, stop).rows[t] == s.rows[t],
{
    assert(!purge_doomed(s, t, g, lo, hi));
}

// ---------------------------------------------------------------------------- witnesses (rows)

pub open spec fn s_marked() -> St {
    St { tout: Map::empty().insert(c1(), 1), rows: Map::empty().insert(tri(c1()), true), ..empty_st() }
}

/// W-F8 — register the predicate, purge all its timestamps (the purge skips a registered predicate: the row
/// stays, as ADR-0015 decided), then opt back in before dropping: a marked row whose triple has no timestamp,
/// of a structural predicate. No temporal maintenance reaches it: DeleteTemporalEdge finds no timestamp,
/// no purge range makes it a candidate, DropRows refuses a structural predicate, BackfillRows adds only.
pub proof fn witness_optin_strands_marked_row() {
    let v = as_built();
    let c = c1();
    let t = tri(c);
    let s0 = s_marked();
    assert(rows_ok(s0)) by {
        assert forall|t2: Triple| #[trigger] s0.rows.contains_key(t2) && s0.rows[t2] implies has_ts(s0.tout, t2) || s0.optout.contains((t2.g, t2.p)) by {
            assert(t2 == t);
            assert(s0.tout.contains_key(c));
        }
    }
    let s1 = step(s0, Action::SetStructural { g: 0, p: 2, enabled: false }, v);
    let s2 = step(s1, Action::Purge { g: 0, lo: 0, hi: 1000, stop_after_rows: false }, v);
    assert(!purge_candidate(s1, t, 0, 0, 1000));
    assert(!purge_doomed(s1, t, 0, 0, 1000));
    assert(s2.rows.contains_key(t) && s2.rows[t]);
    assert(s2.tout =~= Map::<Coord, int>::empty());
    assert(!has_ts(s2.tout, t));
    let s3 = step(s2, Action::SetStructural { g: 0, p: 2, enabled: true }, v);
    assert(s3.optout =~= Set::<(int, int)>::empty());
    assert(s3.rows.contains_key(t) && s3.rows[t] && !has_ts(s3.tout, t) && !s3.optout.contains((t.g, t.p)));
    assert(!rows_ok(s3));
    // every temporal maintenance path leaves it
    assert(!delete_temporal(s3, c).1);
    assert(step(s3, Action::Delete { c }, v).rows.contains_key(t));
    assert(step(s3, Action::DropRows { g: 0, p: 2 }, v) == s3);
    lemma_stranded_row_survives_purge(s3, t, 0, 0, 1000000);
    lemma_backfill_keeps_rows(s3, 0, 2, t);
}

pub proof fn lemma_stranded_row_survives_purge(s: St, t: Triple, g: int, lo: int, hi: int)
    requires
        s.rows.contains_key(t),
        s.rows[t],
        !has_ts(s.tout, t),
    ensures
        step(s, Action::Purge { g, lo, hi, stop_after_rows: false }, as_built()).rows.contains_key(t),
{
    assert(!purge_candidate(s, t, g, lo, hi));
}

pub proof fn lemma_backfill_keeps_rows(s: St, g: int, p: int, t: Triple)
    requires
        s.rows.contains_key(t),
    ensures
        backfill(s, g, p).rows.contains_key(t),
        backfill(s, g, p).rows[t] == s.rows[t],
{
}

/// The same trace under the Q4 repair: opting back in is refused while the row is stranded.
pub proof fn witness_optin_guard_refuses() {
    let v = guarded();
    let c = c1();
    let t = tri(c);
    let s0 = s_marked();
    let s1 = step(s0, Action::SetStructural { g: 0, p: 2, enabled: false }, v);
    let s2 = step(s1, Action::Purge { g: 0, lo: 0, hi: 1000, stop_after_rows: false }, v);
    assert(!purge_doomed(s1, t, 0, 0, 1000));
    assert(s2.rows.contains_key(t) && s2.rows[t]);
    assert(s2.tout =~= Map::<Coord, int>::empty());
    assert(stranded(s2, 0, 2));
    assert(step(s2, Action::SetStructural { g: 0, p: 2, enabled: true }, v) == s2);
}

/// Valid outcome under the Q4 repair: a predicate whose marked rows all have timestamps is opted back in.
pub proof fn witness_optin_guard_allows_clean_optin() {
    let v = guarded();
    let c = c1();
    let s0 = St { optout: set![(0int, 2int)], ..s_marked() };
    assert(!stranded(s0, 0, 2)) by {
        assert forall|t: Triple| #[trigger] s0.rows.contains_key(t) && t.g == 0 && t.p == 2 && s0.rows[t] implies has_ts(s0.tout, t) by {
            assert(t == tri(c));
            assert(s0.tout.contains_key(c));
        }
    }
    let s1 = step(s0, Action::SetStructural { g: 0, p: 2, enabled: true }, v);
    assert(!s1.optout.contains((0int, 2int)));
}

/// The way out as built: re-register, drop, then opt in (backfill restores rows for live triples).
pub proof fn witness_optin_strand_recovery_by_drop() {
    let v = as_built();
    let c = c1();
    let t = tri(c);
    let s3 = St { tout: Map::empty(), ..s_marked() };
    let s4 = step(s3, Action::SetStructural { g: 0, p: 2, enabled: false }, v);
    let s5 = step(s4, Action::DropRows { g: 0, p: 2 }, v);
    assert(!s5.rows.contains_key(t));
    let s6 = step(s5, Action::SetStructural { g: 0, p: 2, enabled: true }, v);
    assert(s6.rows =~= Map::<Triple, bool>::empty());
    assert(rows_ok(s6));
}

/// Open (C3 asymmetry): with the predicate registered, deleting the last timestamp retracts the old marked row
/// (DeleteTemporalEdge does not read the registry, TemporalIndex.cls:333-341) while purging it leaves the row
/// (RetireExpired :966). Both keep L1-ROW; ADR-0015 decides only the purge.
pub proof fn witness_delete_and_purge_disagree_when_opted_out() {
    let v = as_built();
    let c = c1();
    let t = tri(c);
    let s0 = St { optout: set![(0int, 2int)], ..s_marked() };
    let sd = step(s0, Action::Delete { c }, v);
    assert(remove_temporal_row(s0, c).tout =~= Map::<Coord, int>::empty());
    assert(!has_ts(remove_temporal_row(s0, c).tout, t));
    assert(!sd.rows.contains_key(t));
    let sp = step(s0, Action::Purge { g: 0, lo: 0, hi: 1000, stop_after_rows: false }, v);
    assert(!purge_doomed(s0, t, 0, 0, 1000));
    assert(sp.rows.contains_key(t) && sp.rows[t]);
    assert(sp.tout =~= Map::<Coord, int>::empty());
}

/// Design check (ADR-0009:43-44): had the purge killed the raw entries first and failed before the rows, the
/// marked row would be left with no timestamp and no later purge could find it.
pub proof fn witness_raw_first_order_would_strand() {
    let c = c1();
    let t = tri(c);
    let s0 = s_marked();
    let raw_first_failed = St { tout: tout_after_purge(s0, 0, 0, 1000), ..s0 };
    assert(raw_first_failed.tout =~= Map::<Coord, int>::empty());
    assert(raw_first_failed.rows.contains_key(t) && raw_first_failed.rows[t] && !has_ts(raw_first_failed.tout, t));
    assert(!rows_ok(raw_first_failed));
}


// ============================================================================ L1 — ledger governance of temporal writes

/// replay.verify → "equal" (replay.py:806-850): read_canonical takes every Graph_KG.nodes row by node_id (graph-
/// blind, :598-600) and every rdf_edges row except those whose qualifiers carry "temporal": true (:617-620); the
/// replayed ledger gives the governed nodes and relationships (create_temporal_edge records contribute nothing).
pub open spec fn verify_parts(nodes: Set<(int, int)>, gov_nodes: Set<int>, rows: Map<Triple, bool>, gov_rels: Set<Triple>) -> bool {
    &&& forall|id: int| #![trigger known(nodes, id)] #![trigger gov_nodes.contains(id)] known(nodes, id) <==> gov_nodes.contains(id)
    &&& forall|t: Triple| #![trigger rows.contains_key(t)] #![trigger gov_rels.contains(t)]
            (rows.contains_key(t) && !rows[t]) <==> gov_rels.contains(t)
}

pub open spec fn verify_equal(s: St) -> bool {
    verify_parts(s.nodes, s.gov_nodes, s.rows, s.gov_rels)
}

/// L1-GOV (decided 2026-10-19, commit 43efd473; spec 213 US11): temporal writes create no revisions and "a temporal
/// mirror is no longer an unrecorded write" — a temporal write must not turn verify from "equal" to "diverges".
/// Proved for the writes whose endpoints the ledger already knows (any graph) or whose predicate is temporal-only.
pub proof fn lemma_temporal_write_keeps_verify(s: St, c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail, v: Variant)
    requires
        verify_equal(s),
        (node_known(s, c.s) && node_known(s, c.o)) || !structural(s, c.g, c.p),
    ensures
        verify_equal(write_stores(s, c, w, attrs, mode, f, v).0),
{
    lemma_write_shape(s, c, w, attrs, mode, f, v);
    let s2 = write_stores(s, c, w, attrs, mode, f, v).0;
    assert(s2.gov_nodes == s.gov_nodes && s2.gov_rels == s.gov_rels);
    assert(s2.nodes == s.nodes || s2.nodes == s.nodes.insert((c.g, c.s)).insert((c.g, c.o)));
    assert forall|id: int| #[trigger] known(s2.nodes, id) implies known(s.nodes, id) by {
        let g = choose|g: int| #[trigger] s2.nodes.contains((g, id));
        if !s.nodes.contains((g, id)) {
            assert((g, id) == (c.g, c.s) || (g, id) == (c.g, c.o));
        }
    }
    assert forall|id: int| #[trigger] known(s.nodes, id) implies known(s2.nodes, id) by {
        let g = choose|g: int| #[trigger] s.nodes.contains((g, id));
        assert(s2.nodes.contains((g, id)));
    }
    assert forall|t: Triple| #![trigger s2.rows.contains_key(t)] #![trigger s.rows.contains_key(t)] (s2.rows.contains_key(t) && !s2.rows[t]) == (s.rows.contains_key(t) && !s.rows[t]) by {
        if s2.rows.contains_key(t) && !s.rows.contains_key(t) { assert(s2.rows[t]); }
    }
}

pub open spec fn s_gov() -> St {
    St { nodes: set![(0int, 1int)], gov_nodes: set![1int], ..empty_st() }
}

pub proof fn lemma_s_gov_equal()
    ensures
        verify_equal(s_gov()),
{
    let s = s_gov();
    assert forall|id: int| #[trigger] known(s.nodes, id) <==> s.gov_nodes.contains(id) by {
        if known(s.nodes, id) {
            let g = choose|g: int| #[trigger] s.nodes.contains((g, id));
            assert((g, id) == (0int, 1int));
        }
        if s.gov_nodes.contains(id) { assert(s.nodes.contains((0int, id))); }
    }
}

pub proof fn lemma_node_known_3(s: St)
    requires
        s.nodes.contains((0int, 3int)),
    ensures
        node_known(s, 3),
{
}

/// W-F4a — create_edge_temporal(1, P, 3) with the ledger on and node 3 unknown to it: AssertTemporalRow inserts the
/// endpoint node row (Adjacency.cls:597) with no record; verify then reports a node the ledger never created.
pub proof fn witness_direct_temporal_write_makes_verify_diverge() {
    let v = as_built();
    let c = c1();
    let s0 = s_gov();
    lemma_s_gov_equal();
    let s1 = step(s0, Action::Write { c, w: 1, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(s1.nodes.contains((0int, 3int)));
    lemma_node_known_3(s1);
    assert(!s1.gov_nodes.contains(3));
    assert(!verify_equal(s1));
}

/// W-F4b — the same through the ledger: a changeset [create_temporal_edge(1, P, 3)] commits one revision whose only
/// record is create_temporal_edge (which replay ignores); verify diverges on node 3.
pub proof fn witness_ledger_temporal_op_makes_verify_diverge() {
    reveal_with_fuel(apply_ops, 3);
    let v = as_built();
    let c = c1();
    let s0 = s_gov();
    lemma_s_gov_equal();
    let tw = LOp::Temporal { c, w: 1, mode: Mode::Update, f: Fail::No };
    assert(seq![tw].subrange(1, 1) =~= Seq::<LOp>::empty());
    let (s1, r) = commit(s0, seq![tw], false, v);
    assert(r == Out::Ok);
    assert(s1.nodes.contains((0int, 3int)));
    lemma_node_known_3(s1);
    assert(!verify_equal(s1));
}

/// W-F4c — op order inside one changeset decides the outcome. [temporal(1,P,3), upsert_node(3)] commits and leaves
/// node 3 ungoverned (the upsert finds the row AssertTemporalRow wrote, so it records nothing);
/// [temporal(1,P,3), create_node(3)] is refused (node_exists); [create_node(3), temporal(1,P,3)] commits with
/// verify equal.
pub proof fn witness_changeset_op_order_decides() {
    reveal_with_fuel(apply_ops, 4);
    let v = as_built();
    let c = c1();
    let s0 = s_gov();
    lemma_s_gov_equal();
    let tw = LOp::Temporal { c, w: 1, mode: Mode::Update, f: Fail::No };
    let up = LOp::UpsertNode { id: 3 };
    let cr = LOp::CreateNode { id: 3 };
    let sa = tstart(s0);
    let (sb, rb) = apply_op(sa, tw, v);
    assert(rb == Out::Ok);
    assert(sb.nodes.contains((0int, 3int)));
    lemma_node_known_3(sb);
    assert(seq![tw, up].subrange(1, 2) =~= seq![up]);
    assert(seq![up].subrange(1, 1) =~= Seq::<LOp>::empty());
    let (s1, r1) = commit(s0, seq![tw, up], false, v);
    assert(r1 == Out::Ok);
    assert(!s1.gov_nodes.contains(3));
    lemma_node_known_3(s1);
    assert(!verify_equal(s1));
    assert(seq![tw, cr].subrange(1, 2) =~= seq![cr]);
    let (s2, r2) = commit(s0, seq![tw, cr], false, v);
    assert(r2 == Out::Refused);
    // the other order
    assert(!node_known(sa, 3)) by {
        assert forall|g: int| !sa.nodes.contains((g, 3int)) by {}
    }
    let (sc, rc) = apply_op(sa, cr, v);
    assert(rc == Out::Ok);
    assert(seq![cr, tw].subrange(1, 2) =~= seq![tw]);
    assert(seq![tw].subrange(1, 1) =~= Seq::<LOp>::empty());
    let s4 = apply_op(sc, tw, v).0;
    assert(apply_op(sc, tw, v).1 == Out::Ok);
    assert(s4 == write_stores(sc, c, 1, None, Mode::Update, Fail::No, v).0);
    assert(apply_ops(sa, seq![cr, tw], v) == (s4, Out::Ok));
    let (s3, r3) = commit(s0, seq![cr, tw], false, v);
    assert(r3 == Out::Ok);
    assert(s3.nodes == s4.nodes && s3.gov_nodes == s4.gov_nodes && s3.rows == s4.rows && s3.gov_rels == s4.gov_rels);
    assert(s3.gov_nodes.contains(3));
    assert(verify_equal(sc)) by {
        assert forall|id: int| #[trigger] known(sc.nodes, id) <==> sc.gov_nodes.contains(id) by {
            if known(sc.nodes, id) {
                let g = choose|g: int| #[trigger] sc.nodes.contains((g, id));
                assert((g, id) == (0int, 1int) || (g, id) == (0int, 3int));
            }
            if sc.gov_nodes.contains(id) { assert(sc.nodes.contains((0int, id))); }
        }
    }
    assert(node_known(sc, c.s)) by { assert(sc.nodes.contains((0int, 1int))); }
    assert(node_known(sc, c.o)) by { assert(sc.nodes.contains((0int, 3int))); }
    lemma_temporal_write_keeps_verify(sc, c, 1, None, Mode::Update, Fail::No, v);
    assert(verify_equal(s3));
}

/// Valid outcome kept (test_ledger_us11_temporal_coexist::test_mirrored_temporal_row_classification): a temporal
/// edge in a named graph between nodes the ledger knows in the default graph writes node rows in that graph, and
/// verify stays equal — read_canonical keys nodes by id only.
pub proof fn witness_known_endpoints_in_named_graph_keep_verify() {
    let v = as_built();
    let s0 = St { nodes: set![(0int, 1int), (0int, 3int)], gov_nodes: set![1int, 3int], ..empty_st() };
    assert(verify_equal(s0)) by {
        assert forall|id: int| #[trigger] known(s0.nodes, id) <==> s0.gov_nodes.contains(id) by {
            if known(s0.nodes, id) {
                let g = choose|g: int| #[trigger] s0.nodes.contains((g, id));
                assert((g, id) == (0int, 1int) || (g, id) == (0int, 3int));
            }
            if s0.gov_nodes.contains(id) { assert(s0.nodes.contains((0int, id))); }
        }
    }
    let c = Coord { g: 7, ts: 600, s: 1, p: 2, o: 3 };
    assert(node_known(s0, 1)) by { assert(s0.nodes.contains((0int, 1int))); }
    assert(node_known(s0, 3)) by { assert(s0.nodes.contains((0int, 3int))); }
    lemma_temporal_write_keeps_verify(s0, c, 1, None, Mode::Insert, Fail::No, v);
    let s1 = write_stores(s0, c, 1, None, Mode::Insert, Fail::No, v).0;
    assert(s1.nodes.contains((7int, 3int)));
    assert(verify_equal(s1));
}

/// Valid outcome kept: a temporal-only predicate writes no node (ADR-0015), so verify stays equal.
pub proof fn witness_optout_temporal_write_keeps_verify() {
    let v = as_built();
    let c = c1();
    let s0 = St { optout: set![(0int, 2int)], ..s_gov() };
    assert(verify_equal(s0)) by { lemma_s_gov_equal(); }
    lemma_temporal_write_keeps_verify(s0, c, 1, None, Mode::Insert, Fail::No, v);
}


// ============================================================================ L1 — the forward rule (ADR-0009 Decision; review R1-7)

/// L1-FWD (ADR-0009 Decision: "Writing a Temporal Edge for a (source, predicate, target) triple also asserts a
/// Structural Edge row for that triple in the same graph"): with the adjacency index declared, every timestamp of a
/// predicate that is structural in its graph has its triple's row (marked or explicit).
pub open spec fn fwd_parts(tout: Map<Coord, int>, rows: Map<Triple, bool>, optout: Set<(int, int)>) -> bool {
    forall|c: Coord| #[trigger] tout.contains_key(c) && !optout.contains((c.g, c.p)) ==> rows.contains_key(tri(c))
}

pub open spec fn fwd_ok(s: St) -> bool {
    fwd_parts(s.tout, s.rows, s.optout)
}

pub open spec fn snaps_fwd_ok(s: St) -> bool {
    forall|i: int| 0 <= i < s.txn.len() ==> fwd_parts(#[trigger] s.txn[i].tout, s.txn[i].rows, s.txn[i].optout)
}

/// The steps L1-FWD is claimed for, and the enumerated exceptions with their governing source:
///  - a write whose structural step throws (F2: a defect, unless S2 puts the step first);
///  - a purge stopped after its row step (ADR-0009:43-44 accepts it: the rerun finishes, lemma_purge_rerun_finishes);
///  - opting a predicate back in (ADR-0015 "Rollback": "the window in between has temporal entries and no rows",
///    until backfill_temporal_structural_rows; lemma_backfill_restores_fwd);
///  - engine.delete_edge of a row whose triple still has timestamps (no source decides it; test_254_purge_e2e:322
///    pins "the row goes, the timestamps stay"; open question);
///  - the phased steps, i.e. a purge or delete interleaved with a writer (spec 254 tasks.md:80-81, open defect).
pub open spec fn fwd_step_ok(s: St, a: Action, v: Variant) -> bool {
    match a {
        Action::Write { c, w, attrs, mode, f } => v.assert_first || !row_step_fails(s, c, f),
        Action::Purge { g, lo, hi, stop_after_rows } => !stop_after_rows,
        Action::SetStructural { g, p, enabled } => !enabled,
        Action::DeleteEdge { t } => !has_ts(s.tout, t) || s.optout.contains((t.g, t.p)),
        Action::PurgeDecide { .. } | Action::DeleteDecide { .. } | Action::Retract { .. } | Action::PurgeKill { .. } => false,
        _ => true,
    }
}

pub proof fn lemma_write_fwd(s: St, c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail, v: Variant)
    requires
        fwd_ok(s),
        v.assert_first || !row_step_fails(s, c, f) || guard_stops(s, c, mode),
    ensures
        fwd_ok(write_stores(s, c, w, attrs, mode, f, v).0),
{
    lemma_write_shape(s, c, w, attrs, mode, f, v);
    let s2 = write_stores(s, c, w, attrs, mode, f, v).0;
    if guard_stops(s, c, mode) {
        return;
    }
    let t = tri(c);
    let fails = row_step_fails(s, c, f);
    if v.assert_first && fails {
        assert(s2.tout == s.tout);
    } else {
        assert(!fails);
        assert(s2.tout == s.tout.insert(c, w));
        assert(structural(s, c.g, c.p) ==> s2.rows.contains_key(t));
    }
    assert forall|x: Coord| #[trigger] s2.tout.contains_key(x) && !s2.optout.contains((x.g, x.p)) implies s2.rows.contains_key(tri(x)) by {
        if s.tout.contains_key(x) {
            assert(s.rows.contains_key(tri(x)));
        } else {
            assert(x == c);
        }
    }
}

pub proof fn lemma_apply_ops_fwd(s: St, ops: Seq<LOp>, v: Variant)
    requires
        fwd_ok(s),
    ensures
        apply_ops(s, ops, v).1 == Out::Ok ==> fwd_ok(apply_ops(s, ops, v).0),
    decreases ops.len(),
{
    if ops.len() > 0 {
        let op = ops[0];
        let (s1, r) = apply_op(s, op, v);
        if r == Out::Ok {
            match op {
                LOp::Temporal { c, w, mode, f } => {
                    let (sw, rw) = write_stores(s, c, w, None, mode, f, v);
                    assert(rw != WRes::Threw);
                    lemma_write_fwd(s, c, w, None, mode, f, v);
                },
                LOp::CreateRel { t } => {
                    assert forall|x: Coord| #[trigger] s1.tout.contains_key(x) && !s1.optout.contains((x.g, x.p)) implies s1.rows.contains_key(tri(x)) by {
                        assert(s.rows.contains_key(tri(x)));
                    }
                },
                _ => {},
            }
            lemma_apply_ops_fwd(s1, ops.subrange(1, ops.len() as int), v);
        }
    }
}

pub proof fn lemma_snaps_fwd_frame(s: St, s2: St)
    requires
        snaps_fwd_ok(s),
        txn_frame(s2.txn, s.txn),
    ensures
        snaps_fwd_ok(s2),
{
    assert forall|i: int| 0 <= i < s2.txn.len() implies fwd_parts(#[trigger] s2.txn[i].tout, s2.txn[i].rows, s2.txn[i].optout) by {
        assert(snap_frame(s2.txn[i], s.txn[i]));
        assert(fwd_parts(s.txn[i].tout, s.txn[i].rows, s.txn[i].optout));
    }
}

pub proof fn lemma_step_fwd(s: St, a: Action, v: Variant)
    requires
        fwd_ok(s),
        snaps_fwd_ok(s),
        fwd_step_ok(s, a, v),
    ensures
        fwd_ok(step(s, a, v)),
        snaps_fwd_ok(step(s, a, v)),
{
    let s2 = step(s, a, v);
    match a {
        Action::Write { c, w, attrs, mode, f } => {
            lemma_write_fwd(s, c, w, attrs, mode, f, v);
            lemma_write_shape(s, c, w, attrs, mode, f, v);
        },
        Action::Delete { c } => {
            if !s.tout.contains_key(c) {
                lemma_txn_frame_refl(s.txn);
            }
            if s.tout.contains_key(c) {
                lemma_remove_temporal_row_shape(s, c);
                let s1 = remove_temporal_row(s, c);
                assert(s2.txn == s1.txn);
                assert forall|x: Coord| #[trigger] s2.tout.contains_key(x) && !s2.optout.contains((x.g, x.p)) implies s2.rows.contains_key(tri(x)) by {
                    assert(s1.tout.contains_key(x));
                    assert(s.tout.contains_key(x));
                    assert(s.rows.contains_key(tri(x)));
                    if tri(x) == tri(c) {
                        assert(has_ts(s1.tout, tri(c)));
                    }
                }
            }
            lemma_snaps_fwd_frame(s, s2);
        },
        Action::Purge { g, lo, hi, stop_after_rows } => {
            let t2 = tout_after_purge(s, g, lo, hi);
            assert(s2.tout == t2);
            assert(t2.dom() == s.tout.dom().filter(|c: Coord| !in_range(c, g, lo, hi)));
            assert forall|x: Coord| #[trigger] s2.tout.contains_key(x) && !s2.optout.contains((x.g, x.p)) implies s2.rows.contains_key(tri(x)) by {
                assert(s.tout.contains_key(x));
                assert(s.rows.contains_key(tri(x)));
                assert(has_ts(t2, tri(x)));
                assert(!purge_doomed(s, tri(x), g, lo, hi));
            }
        },
        Action::CreateEdge { t } => {
            assert forall|x: Coord| #[trigger] s2.tout.contains_key(x) && !s2.optout.contains((x.g, x.p)) implies s2.rows.contains_key(tri(x)) by {
                assert(s.rows.contains_key(tri(x)));
            }
        },
        Action::DeleteEdge { t } => {
            assert forall|x: Coord| #[trigger] s2.tout.contains_key(x) && !s2.optout.contains((x.g, x.p)) implies s2.rows.contains_key(tri(x)) by {
                assert(s.rows.contains_key(tri(x)));
                if tri(x) == t {
                    assert(has_ts(s.tout, t));
                }
            }
        },
        Action::SetStructural { g, p, enabled } => {
            assert forall|x: Coord| #[trigger] s2.tout.contains_key(x) && !s2.optout.contains((x.g, x.p)) implies s2.rows.contains_key(tri(x)) by {
                assert(!s.optout.contains((x.g, x.p)));
            }
        },
        Action::DropRows { g, p } => {
            if !structural(s, g, p) {
                assert forall|x: Coord| #[trigger] s2.tout.contains_key(x) && !s2.optout.contains((x.g, x.p)) implies s2.rows.contains_key(tri(x)) by {
                    assert(s.rows.contains_key(tri(x)));
                }
            }
        },
        Action::Backfill { g, p } => {
            if structural(s, g, p) {
                assert forall|x: Coord| #[trigger] s2.tout.contains_key(x) && !s2.optout.contains((x.g, x.p)) implies s2.rows.contains_key(tri(x)) by {
                    assert(s.rows.contains_key(tri(x)));
                }
            }
        },
        Action::Begin => {
            assert forall|i: int| 0 <= i < s2.txn.len() implies fwd_parts(#[trigger] s2.txn[i].tout, s2.txn[i].rows, s2.txn[i].optout) by {
                if i < s.txn.len() { assert(s2.txn[i] == s.txn[i]); } else { assert(s2.txn[i] == snap(s)); }
            }
        },
        Action::End => {
            assert forall|i: int| 0 <= i < s2.txn.len() implies fwd_parts(#[trigger] s2.txn[i].tout, s2.txn[i].rows, s2.txn[i].optout) by {
                assert(s2.txn[i] == s.txn[i]);
            }
        },
        Action::Rollback => {
            if s.txn.len() > 0 {
                assert(fwd_parts(s.txn[s.txn.len() - 1].tout, s.txn[s.txn.len() - 1].rows, s.txn[s.txn.len() - 1].optout));
                assert forall|i: int| 0 <= i < s2.txn.len() implies fwd_parts(#[trigger] s2.txn[i].tout, s2.txn[i].rows, s2.txn[i].optout) by {
                    assert(s2.txn[i] == s.txn[i]);
                }
            }
        },
        Action::Commit { ops, blocked } => {
            let s0 = tstart(s);
            lemma_apply_ops_txn(s0, ops, v);
            lemma_apply_ops_fwd(s0, ops, v);
            let (s1, r) = apply_ops(s0, ops, v);
            assert(s1.txn == s.txn.push(snap(s)));
            if !(r == Out::Ok && !blocked) {
                assert(s1.txn.last() == snap(s));
            }
            assert forall|i: int| 0 <= i < s2.txn.len() implies fwd_parts(#[trigger] s2.txn[i].tout, s2.txn[i].rows, s2.txn[i].optout) by {
                assert(s2.txn[i] == s.txn[i]);
            }
        },
        _ => {},
    }
}

/// THEOREM (as built, forward rule): every serial step outside the enumerated exceptions keeps L1-FWD —
/// complete writes in every mode (collisions and skips included), delete, complete purge, explicit create,
/// opt-out, drop, backfill, transactions, rollbacks and changesets (a changeset whose temporal op throws is rolled
/// back whole).
pub proof fn theorem_fwd_as_built(s: St, a: Action)
    requires
        fwd_ok(s),
        snaps_fwd_ok(s),
        fwd_step_ok(s, a, as_built()),
    ensures
        fwd_ok(step(s, a, as_built())),
        snaps_fwd_ok(step(s, a, as_built())),
{
    lemma_step_fwd(s, a, as_built());
}

/// THEOREM (S2, forward rule): with the structural step first, every write — a throwing one included — keeps L1-FWD.
pub proof fn theorem_fwd_assert_first_writes(s: St, c: Coord, w: int, attrs: Option<int>, mode: Mode, f: Fail)
    requires
        fwd_ok(s),
        snaps_fwd_ok(s),
    ensures
        fwd_ok(step(s, Action::Write { c, w, attrs, mode, f }, Variant { assert_first: true, ..as_built() })),
{
    lemma_step_fwd(s, Action::Write { c, w, attrs, mode, f }, Variant { assert_first: true, ..as_built() });
}

/// ADR-0015's way back: after opting a predicate in, BackfillRows gives every timestamp of it a row.
pub proof fn lemma_backfill_restores_fwd(s: St, g: int, p: int, x: Coord)
    requires
        structural(s, g, p),
        x.g == g,
        x.p == p,
        backfill(s, g, p).tout.contains_key(x),
    ensures
        backfill(s, g, p).rows.contains_key(tri(x)),
{
    let add = backfill_set(s, g, p);
    if !s.rows.contains_key(tri(x)) {
        assert(add.contains(x));
        assert(add.map(|c: Coord| tri(c)).contains(tri(x)));
    }
}

// ---------------------------------------------------------------------------- witnesses (forward rule)

/// W-F2 (forward form): the throwing write leaves a timestamp of a structural predicate with no row.
pub proof fn witness_partial_write_breaks_fwd() {
    let v = as_built();
    let c = c1();
    let s0 = empty_st();
    let s1 = step(s0, Action::Write { c, w: 2, attrs: None, mode: Mode::Insert, f: Fail::BeforeNodes }, v);
    assert(s1.tout.contains_key(c) && !s1.optout.contains((c.g, c.p)) && !s1.rows.contains_key(tri(c)));
    assert(!fwd_ok(s1));
}

/// ADR-0015's accepted gap: a triple written while opted out has no row; after opting back in L1-FWD fails until
/// backfill_temporal_structural_rows, which restores it.
pub proof fn witness_optin_gap_closed_by_backfill() {
    let v = as_built();
    let c = c1();
    let s0 = St { optout: set![(0int, 2int)], ..empty_st() };
    let s1 = step(s0, Action::Write { c, w: 1, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(s1.rows == s0.rows);
    assert(s1.tout.contains_key(c));
    let s2 = step(s1, Action::SetStructural { g: 0, p: 2, enabled: true }, v);
    assert(!s2.optout.contains((0int, 2int)));
    assert(!fwd_ok(s2));
    let s3 = step(s2, Action::Backfill { g: 0, p: 2 }, v);
    assert(s3.tout == s2.tout);
    assert(s2.tout =~= Map::<Coord, int>::empty().insert(c, 1));
    assert(fwd_ok(s3)) by {
        assert forall|x: Coord| #[trigger] s3.tout.contains_key(x) && !s3.optout.contains((x.g, x.p)) implies s3.rows.contains_key(tri(x)) by {
            assert(x == c);
            lemma_backfill_restores_fwd(s2, 0, 2, x);
        }
    }
}

/// Open question: engine.delete_edge of a marked row whose triple still has timestamps removes the row and keeps
/// the timestamps (test_254_purge_e2e.py:322 pins this); L1-FWD then fails until the next write of the triple.
pub proof fn witness_explicit_delete_edge_drops_live_row() {
    let v = as_built();
    let c = c1();
    let s0 = s_marked();
    let s1 = step(s0, Action::DeleteEdge { t: tri(c) }, v);
    assert(s1.tout.contains_key(c) && !s1.rows.contains_key(tri(c)));
    assert(!fwd_ok(s1));
    let s2 = step(s1, Action::Write { c: Coord { ts: 601, ..c }, w: 1, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(tri(Coord { ts: 601, ..c }) == tri(c));
    assert(s2.rows.contains_key(tri(c)));
}

// ============================================================================ races (spec 254 tasks.md:80-81; review R1-7)

/// The phased purge run without interleaving is the atomic purge.
pub proof fn lemma_phased_purge_serial(s: St, p: int, g: int, lo: int, hi: int)
    requires
        !s.plans.contains_key(p),
    ensures
        step(step(step(s, Action::PurgeDecide { p, g, lo, hi }, as_built()), Action::Retract { p }, as_built()),
            Action::PurgeKill { p }, as_built()) == purge(s, g, lo, hi, false),
{
    let v = as_built();
    let s1 = step(s, Action::PurgeDecide { p, g, lo, hi }, v);
    let s2 = step(s1, Action::Retract { p }, v);
    let s3 = step(s2, Action::PurgeKill { p }, v);
    let d = doomed_set(s, g, lo, hi);
    assert(s1.plans[p] == Plan { doomed: d, kill: Some((g, lo, hi)), retracted: false });
    let rows1 = Map::new(s.rows.dom().filter(|t: Triple| !purge_doomed(s, t, g, lo, hi)), |t: Triple| s.rows[t]);
    assert forall|t: Triple| s.rows.dom().contains(t) implies (d.contains(t) && s.rows[t]) == purge_doomed(s, t, g, lo, hi) by {
        lemma_doomed_set_iff(s, g, lo, hi, t);
    }
    assert(s.rows.dom().filter(|t: Triple| !(d.contains(t) && s.rows[t])) =~= s.rows.dom().filter(|t: Triple| !purge_doomed(s, t, g, lo, hi)));
    assert(s2.rows == rows1);
    assert(s2.tout == s.tout && s2.eprop == s.eprop && s2.purged == s.purged);
    assert(s2.plans[p].retracted && s2.plans[p].kill == Some((g, lo, hi)));
    assert(s2.plans.remove(p) =~= s.plans);
    assert(s3 =~= purge(s, g, lo, hi, false));
}

/// The phased delete run without interleaving is the atomic delete.
pub proof fn lemma_phased_delete_serial(s: St, p: int, c: Coord)
    requires
        !s.plans.contains_key(p),
        s.tout.contains_key(c),
    ensures
        step(step(s, Action::DeleteDecide { p, c }, as_built()), Action::Retract { p }, as_built()) == delete_temporal(s, c).0,
{
    let v = as_built();
    lemma_remove_temporal_row_shape(s, c);
    let r = remove_temporal_row(s, c);
    let s1 = step(s, Action::DeleteDecide { p, c }, v);
    let s2 = step(s1, Action::Retract { p }, v);
    let t = tri(c);
    assert(s1.plans.remove(p) =~= s.plans);
    if !has_ts(r.tout, t) {
        assert(s1.plans[p].doomed == set![t]);
        if r.rows.contains_key(t) && r.rows[t] {
            assert(s2.rows =~= r.rows.remove(t));
        } else {
            assert(s2.rows =~= r.rows);
        }
    } else {
        assert(s2.rows =~= r.rows);
    }
    assert(s2 =~= delete_temporal(s, c).0);
}

/// A later timestamp of c1()'s triple, outside the purge range [0, 1000).
pub open spec fn c_late() -> Coord { Coord { g: 0, ts: 1200, s: 1, p: 2, o: 3 } }

/// W-RACE-1 — retention purge of [0, 1000) decides that c1()'s triple has no surviving timestamp; an ingest of a
/// later timestamp commits before the retraction (AssertTemporalRow trusts ^KG("out"): the row is there, nothing is
/// written); the retraction then deletes the still-marked row. A live timestamp of a structural predicate, no row:
/// L1-FWD fails while L1-ROW holds (reviewer Check C).
pub proof fn witness_purge_write_race_drops_row() {
    let v = as_built();
    let c = c1();
    let cl = c_late();
    let t = tri(c);
    let s0 = s_marked();
    assert(tri(cl) == t);
    assert(s0.tout.contains_key(c) && in_range(c, 0, 0, 1000));
    assert(tout_after_purge(s0, 0, 0, 1000) =~= Map::<Coord, int>::empty());
    assert(purge_doomed(s0, t, 0, 0, 1000));
    lemma_doomed_set_iff(s0, 0, 0, 1000, t);
    let s1 = step(s0, Action::PurgeDecide { p: 1, g: 0, lo: 0, hi: 1000 }, v);
    assert(s1.plans[1].doomed.contains(t));
    let s2 = step(s1, Action::Write { c: cl, w: 5, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(s2.rows == s0.rows && s2.tout.contains_key(cl) && s2.plans == s1.plans);
    let s3 = step(s2, Action::Retract { p: 1 }, v);
    assert(!s3.rows.contains_key(t));
    let s4 = step(s3, Action::PurgeKill { p: 1 }, v);
    assert(!in_range(cl, 0, 0, 1000));
    assert(s4.tout.contains_key(cl) && !s4.rows.contains_key(t) && !s4.optout.contains((cl.g, cl.p)));
    assert(!fwd_ok(s4));
    assert(s4.rows =~= Map::<Triple, bool>::empty());
    assert(rows_ok(s4));
}

/// W-RACE-2 — the other window: the purge has retracted the row, an ingest of a timestamp inside the range asserts
/// a fresh marked row, and the raw kill loop then removes that timestamp. A marked row with no timestamp, of a
/// structural predicate: L1-ROW (the spec 254 amendment) fails, and no later purge can find it.
pub proof fn witness_purge_write_race_strands_row() {
    let v = as_built();
    let c = c1();
    let cm = Coord { ts: 500, ..c };
    let t = tri(c);
    let s0 = s_marked();
    assert(s0.tout.contains_key(c) && in_range(c, 0, 0, 1000) && tri(c) == t);
    assert(tout_after_purge(s0, 0, 0, 1000) =~= Map::<Coord, int>::empty());
    assert(purge_doomed(s0, t, 0, 0, 1000));
    lemma_doomed_set_iff(s0, 0, 0, 1000, t);
    let s1 = step(s0, Action::PurgeDecide { p: 1, g: 0, lo: 0, hi: 1000 }, v);
    let s2 = step(s1, Action::Retract { p: 1 }, v);
    assert(!s2.rows.contains_key(t));
    assert(tri(cm) == t);
    let s3 = step(s2, Action::Write { c: cm, w: 5, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(s3.rows.contains_key(t) && s3.rows[t]);
    let s4 = step(s3, Action::PurgeKill { p: 1 }, v);
    assert(in_range(cm, 0, 0, 1000));
    assert(s4.tout =~= Map::<Coord, int>::empty());
    assert(s4.rows.contains_key(t) && s4.rows[t] && !has_ts(s4.tout, t) && !s4.optout.contains((t.g, t.p)));
    assert(!rows_ok(s4));
}

/// W-RACE-3 — DeleteTemporalEdge of the last timestamp decides to retract; an ingest of a new timestamp commits
/// before RetractTemporalRow: the row goes, the new timestamp stays.
pub proof fn witness_delete_write_race_drops_row() {
    let v = as_built();
    let c = c1();
    let cl = c_late();
    let t = tri(c);
    let s0 = s_marked();
    lemma_remove_temporal_row_shape(s0, c);
    assert(remove_temporal_row(s0, c).tout =~= Map::<Coord, int>::empty());
    let s1 = step(s0, Action::DeleteDecide { p: 1, c }, v);
    assert(s1.plans[1].doomed == set![t]);
    let s2 = step(s1, Action::Write { c: cl, w: 5, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(s2.rows.contains_key(t) && s2.rows[t] && s2.plans == s1.plans);
    let s3 = step(s2, Action::Retract { p: 1 }, v);
    assert(set![t].contains(t));
    assert(s3.tout.contains_key(cl) && !s3.rows.contains_key(t));
    assert(!fwd_ok(s3));
}

/// Valid outcome under interleaving: an explicit create_edge that adopts the row between the purge's decision and
/// its retraction keeps the row (the DELETE re-tests the marker), with or without timestamps.
pub proof fn witness_adoption_between_decide_and_retract_survives() {
    let v = as_built();
    let c = c1();
    let t = tri(c);
    let s0 = s_marked();
    assert(s0.tout.contains_key(c) && in_range(c, 0, 0, 1000) && tri(c) == t);
    assert(tout_after_purge(s0, 0, 0, 1000) =~= Map::<Coord, int>::empty());
    assert(purge_doomed(s0, t, 0, 0, 1000));
    let s1 = step(s0, Action::PurgeDecide { p: 1, g: 0, lo: 0, hi: 1000 }, v);
    let s2 = step(s1, Action::CreateEdge { t }, v);
    assert(s2.rows.contains_key(t) && !s2.rows[t]);
    let s3 = step(s2, Action::Retract { p: 1 }, v);
    assert(s3.rows.contains_key(t) && !s3.rows[t]);
    let s4 = step(s3, Action::PurgeKill { p: 1 }, v);
    assert(s4.rows.contains_key(t) && !s4.rows[t]);
}

/// Valid outcome serially: purge then write re-asserts the row (L1-FWD and L1-ROW hold).
pub proof fn witness_purge_then_write_reasserts_row() {
    let v = as_built();
    let c = c1();
    let cl = c_late();
    let t = tri(c);
    let s0 = s_marked();
    assert(s0.tout.contains_key(c) && in_range(c, 0, 0, 1000) && tri(c) == t);
    assert(tout_after_purge(s0, 0, 0, 1000) =~= Map::<Coord, int>::empty());
    assert(purge_doomed(s0, t, 0, 0, 1000));
    let s1 = step(s0, Action::Purge { g: 0, lo: 0, hi: 1000, stop_after_rows: false }, v);
    assert(!s1.rows.contains_key(t));
    let s2 = step(s1, Action::Write { c: cl, w: 5, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(s2.rows.contains_key(t));
    assert(s2.tout =~= Map::<Coord, int>::empty().insert(cl, 5));
    assert(fwd_ok(s2)) by {
        assert forall|x: Coord| #[trigger] s2.tout.contains_key(x) && !s2.optout.contains((x.g, x.p)) implies s2.rows.contains_key(tri(x)) by {
            assert(x == cl);
        }
    }
}

/// The reachable start of the rowless route: a triple written while its predicate was opted out, then opted back in
/// (ADR-0015's accepted gap until backfill): timestamp c1(), no row, predicate structural.
pub open spec fn s_rowless() -> St {
    step(step(step(empty_st(), Action::SetStructural { g: 0, p: 2, enabled: false }, as_built()),
        Action::Write { c: c1(), w: 1, attrs: None, mode: Mode::Insert, f: Fail::No }, as_built()),
        Action::SetStructural { g: 0, p: 2, enabled: true }, as_built())
}

pub proof fn lemma_rowless_shape()
    ensures
        s_rowless().tout == Map::<Coord, int>::empty().insert(c1(), 1),
        s_rowless().rows == Map::<Triple, bool>::empty(),
        s_rowless().optout =~= Set::<(int, int)>::empty(),
        s_rowless().plans == Map::<int, Plan>::empty(),
        s_rowless().txn == Seq::<Snap>::empty(),
{
    let v = as_built();
    let s1 = step(empty_st(), Action::SetStructural { g: 0, p: 2, enabled: false }, v);
    let s2 = step(s1, Action::Write { c: c1(), w: 1, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(s2.rows == s1.rows);
}

/// W-RACE-4 (review R2-2) — the purge decides on a triple that has a timestamp in the range and NO row (the
/// rowless start above): RetireExpired still puts it in ^||IVG.TPurge. A concurrent write at ts 1200 finds no row and
/// asserts a marked one; RetractTemporalRows then deletes it (the row is marked when the DELETE runs). A live
/// timestamp of a structural predicate with no row: L1-FWD fails.
pub proof fn witness_purge_write_race_rowless_route() {
    let v = as_built();
    let c = c1();
    let cl = c_late();
    let t = tri(c);
    lemma_rowless_shape();
    let s0 = s_rowless();
    assert(s0.tout.contains_key(c) && in_range(c, 0, 0, 1000) && tri(c) == t);
    assert(tout_after_purge(s0, 0, 0, 1000) =~= Map::<Coord, int>::empty());
    assert(!has_ts(tout_after_purge(s0, 0, 0, 1000), t));
    assert(purge_candidate(s0, t, 0, 0, 1000));
    // membership from doomed_set's definition (not from lemma_doomed_set_iff, so that a narrower decision is caught here)
    let ff = s0.tout.dom().filter(|x: Coord| in_range(x, 0, 0, 1000) && structural(s0, 0, x.p)
        && !has_ts(tout_after_purge(s0, 0, 0, 1000), tri(x)));
    assert(ff.contains(c));
    assert(ff.map(|x: Coord| tri(x)).contains(tri(c)));
    assert(!s0.rows.contains_key(t));
    let s1 = step(s0, Action::PurgeDecide { p: 1, g: 0, lo: 0, hi: 1000 }, v);
    assert(s1.plans[1].doomed.contains(t));
    let s2 = step(s1, Action::Write { c: cl, w: 5, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(tri(cl) == t);
    assert(s2.rows.contains_key(t) && s2.rows[t] && s2.plans == s1.plans);
    let s3 = step(s2, Action::Retract { p: 1 }, v);
    assert(!s3.rows.contains_key(t));
    let s4 = step(s3, Action::PurgeKill { p: 1 }, v);
    assert(!in_range(cl, 0, 0, 1000));
    assert(s4.tout.contains_key(cl) && !s4.rows.contains_key(t) && !s4.optout.contains((cl.g, cl.p)));
    assert(!fwd_ok(s4));
}

/// A new triple (s 1, p 2, o 4) at ts 500.
pub open spec fn c_new() -> Coord { Coord { g: 0, ts: 500, s: 1, p: 2, o: 4 } }

/// W-RACE-5 — a triple the purge never decided on: an ingest of a back-dated event inside the range, after the
/// retraction and before the raw kill loop, asserts its marked row; the kill loop removes its only timestamp. A marked
/// row with no timestamp, of a structural predicate (L1-ROW fails), stranded as in F8.
pub proof fn witness_purge_write_race_strands_new_triple() {
    let v = as_built();
    let cn = c_new();
    let tn = tri(cn);
    let s0 = empty_st();
    let s1 = step(s0, Action::PurgeDecide { p: 1, g: 0, lo: 0, hi: 1000 }, v);
    let s2 = step(s1, Action::Retract { p: 1 }, v);
    assert(s2.rows =~= Map::<Triple, bool>::empty());
    let s3 = step(s2, Action::Write { c: cn, w: 1, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(s3.rows.contains_key(tn) && s3.rows[tn]);
    let s4 = step(s3, Action::PurgeKill { p: 1 }, v);
    assert(in_range(cn, 0, 0, 1000));
    assert(s4.tout =~= Map::<Coord, int>::empty());
    assert(s4.rows.contains_key(tn) && s4.rows[tn] && !has_ts(s4.tout, tn) && !s4.optout.contains((tn.g, tn.p)));
    assert(!rows_ok(s4));
}

// ---------------------------------------------------------------------------- the bug-tmp-011 repair covers every route

pub proof fn lemma_fwd_single(s: St, x0: Coord)
    requires
        s.tout == Map::<Coord, int>::empty().insert(x0, 5) || s.tout =~= Map::<Coord, int>::empty().insert(x0, 5),
        s.rows.contains_key(tri(x0)),
    ensures
        fwd_ok(s),
{
    assert forall|x: Coord| #[trigger] s.tout.contains_key(x) && !s.optout.contains((x.g, x.p)) implies s.rows.contains_key(tri(x)) by {
        assert(x == x0);
    }
}

/// RACE-1 under the repair: the retraction re-tests the survivors, finds ts 1200, keeps the row.
pub proof fn witness_recheck_closes_race_row_at_decide() {
    let v = raced();
    let c = c1();
    let cl = c_late();
    let t = tri(c);
    let s0 = s_marked();
    assert(s0.tout.contains_key(c) && in_range(c, 0, 0, 1000) && tri(c) == t);
    assert(tout_after_purge(s0, 0, 0, 1000) =~= Map::<Coord, int>::empty());
    assert(purge_doomed(s0, t, 0, 0, 1000));
    lemma_doomed_set_iff(s0, 0, 0, 1000, t);
    let s1 = step(s0, Action::PurgeDecide { p: 1, g: 0, lo: 0, hi: 1000 }, v);
    let s2 = step(s1, Action::Write { c: cl, w: 5, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(tri(cl) == t && !in_range(cl, 0, 0, 1000));
    assert(tout_after_purge(s2, 0, 0, 1000).contains_key(cl));
    assert(!still_doomed(s2, s2.plans[1], t));
    let s3 = step(s2, Action::Retract { p: 1 }, v);
    assert(s3.rows.contains_key(t));
    let s4 = step(s3, Action::PurgeKill { p: 1 }, v);
    assert(s4.tout =~= Map::<Coord, int>::empty().insert(cl, 5));
    assert(has_ts(s4.tout, t));
    assert(s4.rows.contains_key(t));
    lemma_fwd_single(s4, cl);
}

/// The rowless route (R2-2) under the repair.
pub proof fn witness_recheck_closes_race_rowless_route() {
    let v = raced();
    let c = c1();
    let cl = c_late();
    let t = tri(c);
    lemma_rowless_shape();
    let s0 = s_rowless();
    assert(s0.tout.contains_key(c) && in_range(c, 0, 0, 1000) && tri(c) == t);
    assert(tout_after_purge(s0, 0, 0, 1000) =~= Map::<Coord, int>::empty());
    lemma_doomed_set_iff(s0, 0, 0, 1000, t);
    let s1 = step(s0, Action::PurgeDecide { p: 1, g: 0, lo: 0, hi: 1000 }, v);
    let s2 = step(s1, Action::Write { c: cl, w: 5, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(tri(cl) == t && !in_range(cl, 0, 0, 1000));
    assert(s2.rows.contains_key(t));
    assert(tout_after_purge(s2, 0, 0, 1000).contains_key(cl));
    assert(!still_doomed(s2, s2.plans[1], t));
    let s3 = step(s2, Action::Retract { p: 1 }, v);
    assert(s3.rows.contains_key(t));
    let s4 = step(s3, Action::PurgeKill { p: 1 }, v);
    assert(s4.tout =~= Map::<Coord, int>::empty().insert(cl, 5));
    assert(has_ts(s4.tout, t));
    assert(s4.rows.contains_key(t));
    lemma_fwd_single(s4, cl);
}

/// RACE-3 (delete) under the repair.
pub proof fn witness_recheck_closes_delete_race() {
    let v = raced();
    let c = c1();
    let cl = c_late();
    let t = tri(c);
    let s0 = s_marked();
    lemma_remove_temporal_row_shape(s0, c);
    assert(remove_temporal_row(s0, c).tout =~= Map::<Coord, int>::empty());
    let s1 = step(s0, Action::DeleteDecide { p: 1, c }, v);
    let s2 = step(s1, Action::Write { c: cl, w: 5, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(tri(cl) == t);
    assert(s2.tout.contains_key(cl));
    assert(!still_doomed(s2, s2.plans[1], t));
    let s3 = step(s2, Action::Retract { p: 1 }, v);
    assert(s3.rows.contains_key(t));
    assert(s3.tout =~= Map::<Coord, int>::empty().insert(cl, 5));
    lemma_fwd_single(s3, cl);
}

/// RACE-2 and RACE-5 under the repair: the kill loop re-retracts every triple it left without a timestamp.
pub proof fn witness_recheck_closes_kill_window() {
    let v = raced();
    let c = c1();
    let cm = Coord { ts: 500, ..c };
    let t = tri(c);
    let s0 = s_marked();
    assert(s0.tout.contains_key(c) && in_range(c, 0, 0, 1000) && tri(c) == t);
    assert(tout_after_purge(s0, 0, 0, 1000) =~= Map::<Coord, int>::empty());
    lemma_doomed_set_iff(s0, 0, 0, 1000, t);
    let s1 = step(s0, Action::PurgeDecide { p: 1, g: 0, lo: 0, hi: 1000 }, v);
    assert(still_doomed(s1, s1.plans[1], t));
    let s2 = step(s1, Action::Retract { p: 1 }, v);
    assert(!s2.rows.contains_key(t));
    let s3 = step(s2, Action::Write { c: cm, w: 5, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(tri(cm) == t);
    assert(s3.rows.contains_key(t) && s3.rows[t]);
    let s4 = step(s3, Action::PurgeKill { p: 1 }, v);
    assert(s4.tout =~= Map::<Coord, int>::empty());
    assert(!s4.rows.contains_key(t));
    assert(s4.rows =~= Map::<Triple, bool>::empty());
    assert(rows_ok(s4));
    // the new-triple form
    let cn = c_new();
    let tn = tri(cn);
    let n1 = step(empty_st(), Action::PurgeDecide { p: 1, g: 0, lo: 0, hi: 1000 }, v);
    let n2 = step(n1, Action::Retract { p: 1 }, v);
    let n3 = step(n2, Action::Write { c: cn, w: 1, attrs: None, mode: Mode::Insert, f: Fail::No }, v);
    assert(n3.rows.contains_key(tn) && n3.rows[tn]);
    assert(n3.tout.contains_key(cn) && in_range(cn, 0, 0, 1000) && structural(n3, 0, cn.p));
    let ff = n3.tout.dom().filter(|c: Coord| in_range(c, 0, 0, 1000) && structural(n3, 0, c.p));
    assert(ff.contains(cn));
    assert(ff.map(|c: Coord| tri(c)).contains(tri(cn)));
    assert(kill_touch(n3, 0, 0, 1000).contains(tn));
    let n4 = step(n3, Action::PurgeKill { p: 1 }, v);
    assert(n4.tout =~= Map::<Coord, int>::empty());
    assert(!n4.rows.contains_key(tn));
    assert(n4.rows =~= Map::<Triple, bool>::empty());
    assert(rows_ok(n4));
}

// ============================================================================ rolled-back delete (review R1-9)

/// One edge (c1, w 2) written outside any transaction: statistics exact.
pub open spec fn s_one() -> St {
    write_stores(empty_st(), c1(), 2, None, Mode::Insert, Fail::No, as_built()).0
}

/// W-R1-9a — the caller's transaction deletes the only edge of a source's bucket and is rolled back. tout, edgeprop
/// and the row come back; RebuildBucketAggregate's Kill of tagg was journaled, so count 1 / sum 2 come back; the
/// bucket's $Increment(-1) was not, and its Kill at 0 was journaled with before-image 0, so ^KG("bucket") comes
/// back as 0: one raw edge, per-source bucket count 0.
pub proof fn witness_rolled_back_delete_undercounts() {
    let v = as_built();
    let c = c1();
    let bk = bkey(c);
    let k = akey(c);
    let s1 = s_one();
    lemma_single(c, 2);
    assert(s1.tout == Map::<Coord, int>::empty().insert(c, 2));
    assert(get0(s1.bucket, bk) == 1 && get0(s1.cnt, k) == 1 && get0(s1.sum, k) == 2);
    let s2 = step(s1, Action::Begin, v);
    let s3 = step(s2, Action::Delete { c }, v);
    let r0 = remove_raw(s2, c);
    assert(r0.tout =~= Map::<Coord, int>::empty());
    assert(r0.txn[0].jbucket == Map::<BKey, Option<int>>::empty().insert(bk, Some(0int)));
    let r1 = journal_agg(r0, k);
    assert(r1.txn[0].jcnt == Map::<AKey, Option<int>>::empty().insert(k, Some(1int)));
    assert(s3.txn == rebuild(r1, k).txn);
    assert(s3.txn[0].jcnt == r1.txn[0].jcnt && s3.txn[0].jbucket == r0.txn[0].jbucket);
    assert(!s3.bucket.contains_key(bk));
    let s4 = step(s3, Action::Rollback, v);
    assert(s4.tout == s1.tout);
    let jb = s3.txn[0].jbucket;
    assert(jb.dom().filter(|x: BKey| jb[x] is Some).contains(bk));
    assert(s4.bucket.contains_key(bk) && s4.bucket[bk] == 0);
    let jc = s3.txn[0].jcnt;
    assert(jc.dom().filter(|x: AKey| jc[x] is Some).contains(k));
    assert(get0(s4.cnt, k) == 1);
    assert(get0(s4.bucket, bk) == 0);
    assert(bset(s4.tout, bk).len() == 1);
    assert(s4.purged == Set::<Coord>::empty());
    lemma_bucket_off_breaks(s4, c);
}

/// Valid outcome: had TROLLBACK taken the counters back, the rolled-back delete would leave the statistics exact.
pub proof fn witness_rolled_back_delete_exact_if_counters_undone() {
    let v = Variant { incr_undone: true, ..as_built() };
    let c = c1();
    let s1 = s_one();
    assert(s_one() == write_stores(empty_st(), c1(), 2, None, Mode::Insert, Fail::No, v).0);
    let s2 = step(s1, Action::Begin, v);
    let s3 = step(s2, Action::Delete { c }, v);
    lemma_remove_temporal_row_shape(s2, c);
    let s4 = step(s3, Action::Rollback, v);
    assert(s3.txn.len() == 1);
    assert(snap_frame(s3.txn[0], s2.txn[0]));
    assert(s4.tout == s1.tout && s4.bucket == s1.bucket && s4.cnt == s1.cnt && s4.sum == s1.sum && s4.purged == s1.purged);
}

} // verus!
