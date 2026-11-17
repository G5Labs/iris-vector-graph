// product 3eaa79cf: operator reports (W58, iteration 52). Writer history -> namespace facts -> report -> operator action.
//   Writers: create_edge -> row insert, ^KG through the declared adjacency index (structure.adjacency.declared), and
//     Graph.KG.Adjacency.Put 80-108 (interns into ^NKG only when ^NKG("$meta","nodeCount") exists; edgeCount +1 only
//     for a triple ^NKG does not hold yet, merged across graphs); sync() (_engine/schema.py 2859-2911: BuildKG, then
//     TraversalBuild.BuildNKG 288-310 / RewritePass 324-373: ^NKG rewritten from every graph's ^KG("out") with no graph
//     dimension, edgeCount = distinct (s,p,o) rows the sweep counted; this engine's _nkg_dirty := False and its cached
//     capabilities.kg_built := True); delete_node / erase (Eraser drops ^NKG, engine flag cleared: nodes_edges.py
//     1518-1520, 2267); bulk_load_session inside a caller transaction (this engine's _nkg_dirty := True; ^NKG untouched);
//     setup (schema.py 3320-3358 bootstrap_kg_global: the Graph.KG.Meta markers kg_built/nkg_built are set only when
//     rdf_edges has rows and the marker is unset; an empty namespace gets no ^NKG skeleton, observed);
//     store_embeddings(graph=g) (a routed table kg_emb_<16 hex> and its registry row); bm25_build / bm25_drop.
//   Readers: AdminMixin.status 396-411 / _status_probes 439-703 (tables, KGEdgeCount, NKGPopulated, pending_sync =
//     this engine's _nkg_dirty, bfs_path, BM25 List()), _embedding_tables 305-355 (SELECT DISTINCT table_name over the
//     registry, kept only when security.is_routed_embedding_table(name): ^kg_emb_[0-9a-f]{16}$), _embedding_row_count
//     357-376; EngineStatus properties status.py 159-214 and report 216-355; verify_sync admin.py 756-848;
//     capabilities engine.py 1742-1756 -> _detect_capabilities 1788-1814 -> GraphSchema.check_objectscript_classes
//     schema.py 2782-2850 (kg_built/nkg_built read from Graph.KG.Meta markers); HTTP /server 498-525, /metrics
//     527-555, /stats 558-568 (cypher_api.py); get_schema_visualization _engine/schema.py 2772-2856; snapshot_info
//     _engine/snapshot.py 1051-1074 over save_snapshot's metadata 835-1007.
// Provider premise P-COLLATE (observed on IRIS 2026.1, iteration 52): SELECT DISTINCT over a default-collation
// VARCHAR answers the SQLUPPER form of the value, so the registry reader sees each table name upper-cased.
use vstd::prelude::*;

verus! {

// =============================================================== state
/// One rdf_edges row (unique on g, s, p, o: the primary key); g = 0 is the default graph.
pub struct Edge { pub g: int, pub s: int, pub p: int, pub o: int }

/// One routed node-vector table: its registry name (characters as codes), its graph and its rows.
pub struct Route { pub name: Seq<int>, pub g: int, pub rows: nat }

/// The namespace's facts every reader consults.
pub struct Ns {
    pub rows: Seq<Edge>,
    pub node_graphs: Seq<int>,      // one entry per node row: its graph key
    pub nkg_skeleton: bool,         // ^NKG("$meta","nodeCount") defined
    pub nkg_dict: bool,             // ^NKG("$NI") non-empty (NKGPopulated)
    pub nkg_triples: spec_fn((int, int, int)) -> bool,
    pub nkg_count: int,             // ^NKG("$meta","edgeCount")
    pub marker_kg: bool,            // Graph.KG.Meta "kg_built"
    pub marker_nkg: bool,           // Graph.KG.Meta "nkg_built"
    pub legacy_vecs: nat,           // kg_NodeEmbeddings rows
    pub routes: Seq<Route>,
    pub hnsw: bool,                 // an HNSW index on the legacy table
    pub bm25: Set<int>,             // BM25 index names (BM25Index.List)
}

/// One engine's own memory: the pending-sync flag and its cached capabilities (None until first read).
pub struct Eng { pub dirty: bool, pub caps: Option<Caps> }

pub struct Caps { pub os: bool, pub kg_built: bool, pub nkg_built: bool }

pub open spec fn tri(e: Edge) -> (int, int, int) { (e.s, e.p, e.o) }

pub open spec fn has_key(rows: Seq<Edge>, e: Edge) -> bool { exists|k: int| 0 <= k < rows.len() && rows[k] == e }

pub open spec fn triples_of(rows: Seq<Edge>) -> spec_fn((int, int, int)) -> bool {
    |t: (int, int, int)| exists|k: int| 0 <= k < rows.len() && tri(rows[k]) == t
}

// =============================================================== distinct triples (what BuildNKG counts)
pub open spec fn seen_before(rows: Seq<Edge>, j: int) -> bool {
    exists|k: int| 0 <= k < j && tri(rows[k]) == tri(rows[j])
}

pub open spec fn ndistinct(rows: Seq<Edge>) -> nat
    decreases rows.len()
{
    if rows.len() == 0 { 0 } else {
        ndistinct(rows.drop_last()) + if seen_before(rows, rows.len() - 1) { 0nat } else { 1nat }
    }
}

pub proof fn lemma_ndistinct_le(rows: Seq<Edge>)
    ensures ndistinct(rows) <= rows.len()
    decreases rows.len()
{
    if rows.len() > 0 { lemma_ndistinct_le(rows.drop_last()); }
}

pub proof fn lemma_ndistinct_lt(rows: Seq<Edge>, i: int, j: int)
    requires 0 <= i < j < rows.len(), tri(rows[i]) == tri(rows[j]),
    ensures ndistinct(rows) < rows.len()
    decreases rows.len()
{
    let d = rows.drop_last();
    if j == rows.len() - 1 {
        assert(seen_before(rows, j));
        lemma_ndistinct_le(d);
    } else {
        assert(d[i] == rows[i] && d[j] == rows[j]);
        lemma_ndistinct_lt(d, i, j);
    }
}

pub open spec fn unique_triples(rows: Seq<Edge>) -> bool {
    forall|i: int, j: int| 0 <= i < j < rows.len() ==> tri(rows[i]) != tri(rows[j])
}

pub proof fn lemma_ndistinct_eq(rows: Seq<Edge>)
    requires unique_triples(rows),
    ensures ndistinct(rows) == rows.len()
    decreases rows.len()
{
    if rows.len() > 0 {
        let d = rows.drop_last();
        assert forall|i: int, j: int| 0 <= i < j < d.len() implies tri(d[i]) != tri(d[j]) by {
            assert(d[i] == rows[i] && d[j] == rows[j]);
        }
        lemma_ndistinct_eq(d);
        assert(!seen_before(rows, rows.len() - 1));
    }
}

// =============================================================== writers
/// initialize_schema(): declares the adjacency index (premise), and sets both markers only when edges exist and the
/// kg marker is unset (bootstrap_kg_global). An empty namespace gets no ^NKG skeleton.
pub open spec fn setup(ns: Ns) -> Ns {
    if ns.rows.len() > 0 && !ns.marker_kg { Ns { marker_kg: true, marker_nkg: true, ..ns } } else { ns }
}

pub open spec fn fresh_setup() -> Ns {
    setup(Ns { rows: Seq::empty(), node_graphs: Seq::empty(), nkg_skeleton: false, nkg_dict: false,
               nkg_triples: |t: (int, int, int)| false, nkg_count: 0, marker_kg: false, marker_nkg: false, legacy_vecs: 0,
               routes: Seq::empty(), hnsw: false, bm25: Set::empty() })
}

/// create_edge: the row (and ^KG with it); Adjacency.Put interns into ^NKG only when the skeleton exists.
pub open spec fn create_edge(ns: Ns, e: Edge) -> Ns {
    let rows = ns.rows.push(e);
    if ns.nkg_skeleton {
        if (ns.nkg_triples)(tri(e)) { Ns { rows, nkg_dict: true, ..ns } }
        else { Ns { rows, nkg_dict: true, nkg_triples: |t: (int, int, int)| (ns.nkg_triples)(t) || t == tri(e), nkg_count: ns.nkg_count + 1, ..ns } }
    } else { Ns { rows, ..ns } }
}

/// sync(): ^NKG rewritten from every graph's ^KG("out"), merged on (s, p, o).
pub open spec fn sync_ns(ns: Ns) -> Ns {
    Ns { nkg_skeleton: true, nkg_dict: ns.rows.len() > 0, nkg_triples: triples_of(ns.rows),
         nkg_count: ndistinct(ns.rows) as int, ..ns }
}

/// sync() on the calling engine: its flag cleared, its cached kg_built set (detected first when not cached).
pub open spec fn sync_eng(ns: Ns, eng: Eng) -> Eng {
    let c = match eng.caps { Some(c) => c, None => detect(ns) };
    Eng { dirty: false, caps: Some(Caps { kg_built: true, ..c }) }
}

/// delete_node / erase: rows go; the Eraser drops ^NKG (rebuilt by its next reader); the engine flag is cleared.
pub open spec fn delete_ns(ns: Ns, keep: Seq<Edge>) -> Ns {
    Ns { rows: keep, nkg_skeleton: false, nkg_dict: false, nkg_triples: |t: (int, int, int)| false, nkg_count: 0, ..ns }
}

/// bulk_load_session inside a caller transaction, committed: each row goes through the declared adjacency index
/// (Adjacency.RowPut -> Put), so ^NKG interns it when its skeleton exists; the loading engine is flagged.
pub open spec fn bulk_ns(ns: Ns, more: Seq<Edge>) -> Ns
    decreases more.len()
{
    if more.len() == 0 { ns } else { create_edge(bulk_ns(ns, more.drop_last()), more.last()) }
}

pub open spec fn bulk_eng(eng: Eng) -> Eng { Eng { dirty: true, ..eng } }

pub open spec fn store_routed(ns: Ns, r: Route) -> Ns { Ns { routes: ns.routes.push(r), ..ns } }

pub open spec fn store_legacy(ns: Ns, n: nat) -> Ns { Ns { legacy_vecs: ns.legacy_vecs + n, ..ns } }

pub open spec fn bm25_build(ns: Ns, name: int) -> Ns { Ns { bm25: ns.bm25.insert(name), ..ns } }

pub open spec fn bm25_drop(ns: Ns, name: int) -> Ns { Ns { bm25: ns.bm25.remove(name), ..ns } }

// =============================================================== the registry reader and its provider
pub open spec fn up(c: int) -> int { if 97 <= c <= 122 { c - 32 } else { c } }

/// P-COLLATE: what SELECT DISTINCT table_name answers for a stored name.
pub open spec fn registry_text(name: Seq<int>) -> Seq<int> { Seq::new(name.len(), |i: int| up(name[i])) }

pub open spec fn lower_hex(c: int) -> bool { (48 <= c <= 57) || (97 <= c <= 102) }

/// security.is_routed_embedding_table: ^kg_emb_[0-9a-f]{16}$ (case-sensitive).
pub open spec fn is_route(n: Seq<int>) -> bool {
    n.len() == 23 && n[0] == 107 && n[1] == 103 && n[2] == 95 && n[3] == 101 && n[4] == 109 && n[5] == 98
        && n[6] == 95 && forall|i: int| 7 <= i < 23 ==> lower_hex(#[trigger] n[i])
}

pub open spec fn counted(r: Route) -> nat { if is_route(registry_text(r.name)) { r.rows } else { 0 } }

pub open spec fn routed_sum(rs: Seq<Route>) -> nat
    decreases rs.len()
{
    if rs.len() == 0 { 0 } else { routed_sum(rs.drop_last()) + counted(rs.last()) }
}

/// The routed rows a route-aware reader (vector search on graph g) reads: the table itself, whatever its name's case.
pub open spec fn route_rows(rs: Seq<Route>, g: int) -> nat
    decreases rs.len()
{
    if rs.len() == 0 { 0 } else { route_rows(rs.drop_last(), g) + if rs.last().g == g { rs.last().rows } else { 0 } }
}

// =============================================================== status (derived) and its properties
pub enum Path { None, ObjectScript }
pub enum IdxState { Absent, Empty, Ready }
pub enum SyncLine { InSync, NeedsSync }

pub struct Status {
    pub nodes: nat, pub edges: nat, pub node_vecs: nat,
    pub kg_populated: bool, pub kg_edge_count: nat, pub nkg_populated: bool,
    pub bfs_path: Path, pub pending: bool, pub hnsw: bool, pub bm25: Set<int>,
}

/// _status_probes over a namespace whose classes are deployed and whose adjacency index is declared (so ^KG holds
/// exactly the rows: KGEdgeCount = rows, below its 10000 cap).
pub open spec fn status(ns: Ns, eng: Eng) -> Status {
    let kgp = ns.rows.len() > 0;
    Status {
        nodes: ns.node_graphs.len(), edges: ns.rows.len(), node_vecs: ns.legacy_vecs + routed_sum(ns.routes),
        kg_populated: kgp, kg_edge_count: ns.rows.len(), nkg_populated: ns.nkg_dict,
        bfs_path: if kgp { Path::ObjectScript } else { Path::None }, pending: eng.dirty, hnsw: ns.hnsw, bm25: ns.bm25,
    }
}

pub open spec fn ready_for_bfs(s: Status) -> bool { s.kg_populated && s.edges > 0 }
pub open spec fn ready_for_multihop_bfs(s: Status) -> bool { ready_for_bfs(s) && s.bfs_path != Path::None }
pub open spec fn ready_for_vector_search(s: Status) -> bool { s.node_vecs > 0 }
pub open spec fn ready_for_full_text(s: Status) -> bool { s.bm25 != Set::<int>::empty() }
pub open spec fn vector_state(s: Status) -> IdxState {
    if s.node_vecs == 0 { IdxState::Absent } else if s.hnsw { IdxState::Ready } else { IdxState::Empty }
}
pub open spec fn sync_line(s: Status) -> SyncLine { if s.pending { SyncLine::NeedsSync } else { SyncLine::InSync } }

// =============================================================== verify_sync
pub struct SyncReport { pub in_sync: bool, pub sql: nat, pub glob: int, pub pending: bool, pub healed: bool }

pub open spec fn verify(ns: Ns, eng: Eng) -> SyncReport {
    let sql_exceeds = ns.rows.len() > ns.nkg_count;
    SyncReport { in_sync: !sql_exceeds && !eng.dirty, sql: ns.rows.len(), glob: ns.nkg_count, pending: eng.dirty,
                 healed: false }
}

/// verify_sync(heal=True): on drift it runs sync() and stamps the report in sync without reading again.
pub open spec fn verify_heal(ns: Ns, eng: Eng) -> (SyncReport, Ns, Eng) {
    let r = verify(ns, eng);
    if r.in_sync { (r, ns, eng) }
    else { (SyncReport { in_sync: true, healed: true, ..r }, sync_ns(ns), sync_eng(ns, eng)) }
}

// =============================================================== capabilities
/// _detect_capabilities: the classes, then the Graph.KG.Meta markers.
pub open spec fn detect(ns: Ns) -> Caps { Caps { os: true, kg_built: ns.marker_kg, nkg_built: ns.marker_nkg } }

/// engine.capabilities: detected once, then this engine's cache.
pub open spec fn caps_of(ns: Ns, eng: Eng) -> Caps { match eng.caps { Some(c) => c, None => detect(ns) } }

pub enum Act { Create(Edge), Sync, Delete(Seq<Edge>), Bulk(Seq<Edge>), Routed(Route), Legacy(nat), Build(int), Drop(int) }

pub open spec fn step(ns: Ns, a: Act) -> Ns {
    match a {
        Act::Create(e) => create_edge(ns, e),
        Act::Sync => sync_ns(ns),
        Act::Delete(keep) => delete_ns(ns, keep),
        Act::Bulk(more) => bulk_ns(ns, more),
        Act::Routed(r) => store_routed(ns, r),
        Act::Legacy(n) => store_legacy(ns, n),
        Act::Build(x) => bm25_build(ns, x),
        Act::Drop(x) => bm25_drop(ns, x),
    }
}

pub open spec fn run(ns: Ns, acts: Seq<Act>) -> Ns
    decreases acts.len()
{
    if acts.len() == 0 { ns } else { step(run(ns, acts.drop_last()), acts.last()) }
}

// =============================================================== HTTP readers
pub open spec fn count_in(gs: Seq<int>, g: int) -> nat
    decreases gs.len()
{
    if gs.len() == 0 { 0 } else { count_in(gs.drop_last(), g) + if gs.last() == g { 1nat } else { 0nat } }
}

/// GET /server: part of status(); GET /metrics: the same fields as gauges; GET /stats: the default graph's nodes.
pub struct Server { pub nodes: nat, pub edges: nat, pub embeddings: nat, pub kg: bool, pub nkg: bool }
pub open spec fn server(s: Status) -> Server {
    Server { nodes: s.nodes, edges: s.edges, embeddings: s.node_vecs, kg: s.kg_populated, nkg: s.nkg_populated }
}
pub open spec fn metrics_nkg(s: Status) -> int { if s.nkg_populated { 1 } else { 0 } }
pub open spec fn stats_nodes(ns: Ns) -> nat { count_in(ns.node_graphs, 0) }

// =============================================================== schema diagram and snapshot info
/// get_schema_visualization: a label's id is its position in the sorted label list; an endpoint without a label gets 0.
pub open spec fn label_id(labels: Seq<int>, l: Option<int>) -> int {
    match l {
        Some(x) => if exists|i: int| 0 <= i < labels.len() && labels[i] == x {
            choose|i: int| 0 <= i < labels.len() && labels[i] == x } else { 0 },
        None => 0,
    }
}

pub struct Info { pub nodes: nat, pub edges: nat }
/// save_snapshot's metadata tables (every graph's rows) as snapshot_info returns them.
pub open spec fn info_of(ns: Ns) -> Info { Info { nodes: ns.node_graphs.len(), edges: ns.rows.len() } }
/// restore_snapshot (replacing): the archive's rows replace every graph's.
pub open spec fn restore(ns: Ns, arch: Ns) -> Ns { Ns { rows: arch.rows, node_graphs: arch.node_graphs, ..ns } }

// =============================================================== theorems: verify_sync and ^NKG
/// Two graphs holding the same (s, p, o): after sync() verify_sync reports drift, on every engine.
pub proof fn theorem_shared_triple_never_in_sync(ns: Ns, eng: Eng, other: Eng, i: int, j: int)
    requires 0 <= i < j < ns.rows.len(), tri(ns.rows[i]) == tri(ns.rows[j]), !other.dirty,
    ensures
        !verify(sync_ns(ns), sync_eng(ns, eng)).in_sync,
        !verify(sync_ns(ns), other).in_sync,
{
    lemma_ndistinct_lt(ns.rows, i, j);
}

/// The neighbor: every triple in one graph only, so after sync() the report is in sync.
pub proof fn theorem_unique_triples_in_sync_after_sync(ns: Ns, eng: Eng)
    requires unique_triples(ns.rows),
    ensures verify(sync_ns(ns), sync_eng(ns, eng)).in_sync,
{
    lemma_ndistinct_eq(ns.rows);
}

/// heal=True on a synced namespace whose graphs share a triple: the report answers healed and in sync, and the next
/// verify_sync (on the healing engine or any other) answers drift again; sync() never clears it.
pub proof fn theorem_heal_claims_in_sync_then_drift(n0: Ns, eng: Eng, other: Eng, i: int, j: int)
    requires 0 <= i < j < n0.rows.len(), tri(n0.rows[i]) == tri(n0.rows[j]), !other.dirty,
    ensures ({
        let ns = sync_ns(n0);
        let e1 = sync_eng(n0, eng);
        let (r, ns2, eng2) = verify_heal(ns, e1);
        &&& !verify(ns, e1).in_sync
        &&& r.in_sync && r.healed
        &&& !verify(ns2, eng2).in_sync
        &&& !verify(ns2, other).in_sync
    }),
{
    lemma_ndistinct_lt(n0.rows, i, j);
}

/// A freshly set-up empty namespace: the first edges are rows and ^KG, not ^NKG. status() says ready for
/// (multi-hop) BFS and "in sync", ^NKG not built, while verify_sync says drift.
pub proof fn theorem_fresh_namespace_edges_skip_nkg(e: Edge, eng: Eng)
    requires !eng.dirty,
    ensures ({
        let ns = create_edge(fresh_setup(), e);
        let s = status(ns, eng);
        &&& ready_for_bfs(s) && ready_for_multihop_bfs(s)
        &&& !s.nkg_populated && sync_line(s) == SyncLine::InSync
        &&& !verify(ns, eng).in_sync
    }),
{
}

/// The neighbor: after a sync(), a new triple is interned by Put and verify_sync stays in sync.
pub proof fn theorem_put_after_sync_counted(ns: Ns, eng: Eng, e: Edge)
    requires unique_triples(ns.rows), !(triples_of(ns.rows))(tri(e)),
    ensures ({
        let n2 = create_edge(sync_ns(ns), e);
        &&& n2.nkg_dict
        &&& verify(n2, sync_eng(ns, eng)).in_sync
    }),
{
    lemma_ndistinct_eq(ns.rows);
}

/// A delete leaves rows: ^NKG is dropped (its next reader rebuilds it), status() on either engine says "in sync" and
/// ^NKG not built, and verify_sync on either says drift.
pub proof fn theorem_delete_status_vs_verify(ns: Ns, keep: Seq<Edge>, eng: Eng, other: Eng)
    requires keep.len() > 0, !other.dirty,
    ensures ({
        let n2 = delete_ns(ns, keep);
        let e2 = Eng { dirty: false, ..eng };
        &&& sync_line(status(n2, e2)) == SyncLine::InSync && sync_line(status(n2, other)) == SyncLine::InSync
        &&& !status(n2, e2).nkg_populated
        &&& !verify(n2, e2).in_sync && !verify(n2, other).in_sync
    }),
{
}

/// bulk_load_session inside a caller transaction: only the loading engine reports pending sync.
pub proof fn theorem_bulk_pending_is_engine_local(ns: Ns, more: Seq<Edge>, eng: Eng, other: Eng)
    requires !other.dirty,
    ensures
        status(bulk_ns(ns, more), bulk_eng(eng)).pending,
        sync_line(status(bulk_ns(ns, more), bulk_eng(eng))) == SyncLine::NeedsSync,
        !status(bulk_ns(ns, more), other).pending,
        !verify(bulk_ns(ns, more), bulk_eng(eng)).in_sync,
{
}

// =============================================================== theorems: vectors
pub proof fn lemma_upper_never_route(n: Seq<int>)
    ensures !is_route(registry_text(n)),
{
    if n.len() > 0 {
        let t = registry_text(n);
        assert(t[0] == up(n[0]));
        assert(t[0] != 107);
    }
}

pub proof fn lemma_routed_sum_zero(rs: Seq<Route>)
    ensures routed_sum(rs) == 0,
    decreases rs.len()
{
    if rs.len() > 0 {
        lemma_routed_sum_zero(rs.drop_last());
        lemma_upper_never_route(rs.last().name);
    }
}

/// status() never counts a routed table's vectors: node_embeddings is the legacy table's rows, for every registry.
pub proof fn theorem_routed_never_counted(ns: Ns, eng: Eng)
    ensures status(ns, eng).node_vecs == ns.legacy_vecs,
{
    lemma_routed_sum_zero(ns.routes);
}

/// Routed vectors only: the report says absent and not ready, while a search on that graph reads them.
pub proof fn theorem_routed_only_not_ready_but_searchable(ns: Ns, eng: Eng, r: Route)
    requires ns.legacy_vecs == 0, r.rows > 0,
    ensures ({
        let n2 = store_routed(ns, r);
        let s = status(n2, eng);
        &&& !ready_for_vector_search(s) && vector_state(s) == IdxState::Absent
        &&& server(s).embeddings == 0
        &&& route_rows(n2.routes, r.g) > 0
    }),
{
    lemma_routed_sum_zero(ns.routes.push(r));
    assert(ns.routes.push(r).drop_last() == ns.routes);
}

/// The neighbor: vectors in the legacy table make the report ready, an un-indexed table "empty" (searched by a scan).
pub proof fn theorem_legacy_vectors_ready(ns: Ns, eng: Eng, n: nat)
    requires n > 0, !ns.hnsw,
    ensures ({
        let s = status(store_legacy(ns, n), eng);
        ready_for_vector_search(s) && vector_state(s) == IdxState::Empty
    }),
{
    lemma_routed_sum_zero(ns.routes);
}

// =============================================================== theorems: readiness and indexes
/// With the adjacency index declared, ready_for_bfs is exactly "some edge row exists", in every graph together.
pub proof fn theorem_ready_for_bfs_iff_rows(ns: Ns, eng: Eng)
    ensures ready_for_bfs(status(ns, eng)) == (ns.rows.len() > 0),
{
}

/// ready_for_full_text follows the BM25 index list: true after a build, false after its only index is dropped.
pub proof fn theorem_full_text_follows_index(ns: Ns, eng: Eng, x: int)
    requires ns.bm25 == Set::<int>::empty(),
    ensures
        ready_for_full_text(status(bm25_build(ns, x), eng)),
        !ready_for_full_text(status(bm25_drop(bm25_build(ns, x), x), eng)),
{
    assert(bm25_build(ns, x).bm25.contains(x));
    assert(bm25_drop(bm25_build(ns, x), x).bm25 =~= Set::<int>::empty());
}

// =============================================================== theorems: capabilities
pub proof fn lemma_bulk_markers(ns: Ns, more: Seq<Edge>)
    ensures bulk_ns(ns, more).marker_kg == ns.marker_kg, bulk_ns(ns, more).marker_nkg == ns.marker_nkg,
    decreases more.len()
{
    if more.len() > 0 { lemma_bulk_markers(ns, more.drop_last()); }
}

pub proof fn lemma_markers_kept(ns: Ns, acts: Seq<Act>)
    ensures run(ns, acts).marker_kg == ns.marker_kg, run(ns, acts).marker_nkg == ns.marker_nkg,
    decreases acts.len()
{
    if acts.len() > 0 {
        lemma_markers_kept(ns, acts.drop_last());
        if let Act::Bulk(more) = acts.last() { lemma_bulk_markers(run(ns, acts.drop_last()), more); }
    }
}

/// A namespace set up before it held edges: every engine that detects its capabilities, after any later history of
/// writes, syncs, deletes, loads and index builds, reads kg_built and nkg_built False; only the engine that ran
/// sync() holds kg_built True, in its own memory, and no engine ever holds nkg_built True.
pub proof fn theorem_markers_never_set_after_empty_setup(acts: Seq<Act>, eng: Eng)
    requires eng.caps.is_none(),
    ensures ({
        let ns = run(fresh_setup(), acts);
        &&& !detect(ns).kg_built && !detect(ns).nkg_built
        &&& caps_of(ns, sync_eng(ns, eng)).kg_built
        &&& !caps_of(ns, sync_eng(ns, eng)).nkg_built
    }),
{
    lemma_markers_kept(fresh_setup(), acts);
}

/// The neighbor: setup run again while edges exist sets both markers, and a fresh engine then reads them.
pub proof fn theorem_setup_with_edges_sets_markers(ns: Ns)
    requires ns.rows.len() > 0, !ns.marker_kg,
    ensures detect(setup(ns)).kg_built && detect(setup(ns)).nkg_built,
{
}

/// Running setup again once edges exist sets both markers, from any engine: setup replaces the engine's cached
/// capabilities with the deploy's fresh detection before the bootstrap decides (_engine/schema.py 2583, 2674).
pub proof fn theorem_setup_again_sets_markers(acts: Seq<Act>)
    ensures ({
        let ns = run(fresh_setup(), acts);
        ns.rows.len() > 0 ==> detect(setup(ns)).kg_built && detect(setup(ns)).nkg_built
    }),
{
    lemma_markers_kept(fresh_setup(), acts);
}

// =============================================================== theorems: HTTP readers, diagram, snapshot info
pub proof fn lemma_count_in_le(gs: Seq<int>, g: int)
    ensures count_in(gs, g) <= gs.len(),
    decreases gs.len()
{
    if gs.len() > 0 { lemma_count_in_le(gs.drop_last(), g); }
}

pub proof fn lemma_count_in_lt(gs: Seq<int>, g: int, k: int)
    requires 0 <= k < gs.len(), gs[k] != g,
    ensures count_in(gs, g) < gs.len(),
    decreases gs.len()
{
    let d = gs.drop_last();
    if k == gs.len() - 1 { lemma_count_in_le(d, g); } else { assert(d[k] == gs[k]); lemma_count_in_lt(d, g, k); }
}

/// A node in a named graph: /stats answers fewer nodes than /server and /metrics, which read status().
pub proof fn theorem_stats_default_vs_server_every_graph(ns: Ns, eng: Eng, k: int)
    requires 0 <= k < ns.node_graphs.len(), ns.node_graphs[k] != 0,
    ensures stats_nodes(ns) < server(status(ns, eng)).nodes,
{
    lemma_count_in_lt(ns.node_graphs, 0, k);
}

/// /server and /metrics carry status()'s adjacency facts unchanged.
pub proof fn theorem_server_and_metrics_project_status(ns: Ns, eng: Eng)
    ensures ({
        let s = status(ns, eng);
        &&& server(s).kg == s.kg_populated && server(s).nkg == s.nkg_populated
        &&& (metrics_nkg(s) == 1) == s.nkg_populated
    }),
{
}

/// An edge whose endpoint has no label is drawn from (or to) the first label: "none" and "label 0" are one id.
pub proof fn theorem_unlabeled_endpoint_is_first_label(labels: Seq<int>)
    requires labels.len() > 0, forall|i: int, j: int| 0 <= i < j < labels.len() ==> labels[i] != labels[j],
    ensures label_id(labels, None) == label_id(labels, Some(labels[0])),
{
    let x = labels[0];
    assert(exists|i: int| 0 <= i < labels.len() && labels[i] == x) by { assert(labels[0] == x); }
    let c = choose|i: int| 0 <= i < labels.len() && labels[i] == x;
    if c != 0 { assert(labels[0] != labels[c]); }
}

/// snapshot_info's table counts are every graph's rows at save time, and a replacing restore brings status() to them.
pub proof fn theorem_snapshot_info_matches_restore(ns: Ns, later: Ns, eng: Eng)
    ensures ({
        let i = info_of(ns);
        let s = status(restore(later, ns), eng);
        &&& i.nodes == status(ns, eng).nodes && i.edges == status(ns, eng).edges
        &&& s.nodes == i.nodes && s.edges == i.edges
    }),
{
}

} // verus!

