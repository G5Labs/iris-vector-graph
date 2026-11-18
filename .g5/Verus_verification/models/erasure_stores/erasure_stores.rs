// IVG erasure across stores — Verus model (iteration 65, 2026-11-18). Product baseline 3eaa79cf.
//
// What each erase entry point removes, keeps and returns, over ONE store map that holds every store the ontology names
// (features/erasure.g5.md Definitions "Store"): node/label/property/relationship rows, documents, node and edge vectors
// (legacy tables and routed kg_emb_/kg_eemb_ tables), the embedding registry and the routed tables themselves,
// reifications, FHIR side tables and the FHIR registration with its watermarks, the embedding quarantine, adjacency and
// the degree cache (^KG out/in/gen/degc/degw, ^IVG.AdjNoLock), ^KG label/prop/deg2p, the temporal subtrees, temporal-only
// settings, multigraph mode, the algorithm cache, ledger statements/tuple lookups/records, the unscoped stores (^NKG,
// ^KG("labelset"), ^KG("deg2p_exact_merged"), ^ArnoKG) and the named search indexes (^BM25Idx, ^IVF, ^PLAID, ^VecIdx).
//
// L2 as built: Graph.KG.Eraser (EraseGraph, EraseNodes, EraseNodeIds, EraseEdges, EraseAll, EraseIdSet, EraseEdgeRow,
// InvalidateDerived, CollectOrphanRoutes, EraseLedgerFor, EraseFHIRGraphRows), Graph.KG.GraphKey.Validate,
// Graph.KG.Adjacency.RemoveGraph/RemoveNode, Graph.KG.TemporalIndex.EraseGraph/EraseNodes, and the Python callers
// (nodes_edges.py erase_graph/drop_graph/erase_all/delete_nodes_by_prefix/delete_node/bulk_delete_nodes/
// bulk_delete_adjacency/delete_edge, iris_sql_store.py delete_nodes/delete_edges/delete_nodes_by_prefix/_eraser_txn,
// _write_txn.WriteTxn). Each entry point's effect is derived from its own selection rule: the graph predicate
// COALESCE(graph_id,'') = COALESCE(name,'') (both default spellings), the prefix through node rows, the ID list as
// given, the relationship list through the triple's rows. The transaction boundary is represented where it changes the
// outcome: the Eraser's own TSTART/TROLLBACK-to-entry-level, $Increment counters a rollback keeps, the post-commit DROP
// of claimed routes, the 500-entry chunk calls of the store, and the caller's transaction (joined on the caller's
// connection, or not joined on a from_connect engine's dedicated Native API connection).
//
// This is a transcription, not a proof of the ObjectScript or Python bodies. Bindings: BINDINGS.md, binding.py,
// ../../crosswalk/decision-links.tsv.
//
// Run: python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/erasure_stores
use vstd::prelude::*;

verus! {

// ============================================================================ names and spellings

/// A string as its code points (a node ID, a graph name, a prefix).
pub type Str = Seq<int>;

/// A SQL graph_id cell: NULL, or a string ('' is the default graph). Globals carry the canonical name (Sp::S).
pub enum Sp { Null, S(Str) }

/// COALESCE(graph_id, ''): the Eraser's predicate on both sides of every graph test (Eraser.cls:117-123).
pub open spec fn canon(sp: Sp) -> Str {
    match sp { Sp::Null => Seq::<int>::empty(), Sp::S(n) => n }
}

pub open spec fn ctl(ch: int) -> bool { ch < 32 || ch == 127 }

/// GraphKey.Validate / _validate.validate_graph_name: "0" is reserved, a control character is refused.
pub open spec fn valid(n: Str) -> bool {
    n != seq![48int] && forall|i: int| 0 <= i < n.len() ==> !ctl(#[trigger] n[i])
}

pub open spec fn has_prefix(id: Str, m: Str) -> bool {
    m.len() <= id.len() && id.subrange(0, m.len() as int) == m
}

// ============================================================================ the store map

pub enum K {
    Node, Label, Prop, Edge,                     // Graph_KG.nodes, rdf_labels, rdf_props, rdf_edges (eid = edge_id)
    Doc, NEmb, NEmbOpt, EEmb,                    // docs, kg_NodeEmbeddings(_optimized), kg_EdgeEmbeddings
    NRoute, ERoute,                              // a row of a routed table kg_emb_<h> / kg_eemb_<h> (tbl)
    Registry, RouteTable,                        // embedding_registry row (g, tbl); the routed table itself (tbl)
    Reif,                                        // rdf_reifications (eid); no graph column (GraphStores Unscoped)
    FhirSide, FhirReg,                           // fhir_unresolved/definitions/canonical_refs; fhir_graphs (wm)
    Quar,                                        // embedding_quarantine: no graph
    Adj, Gen, Degc, Degw, NoLock,                // ^KG out/in (one entry per triple), gen, degc, degw; ^IVG.AdjNoLock
    KLabel, KProp, Deg2p, Temporal,              // ^KG label, prop, deg2p(+_exact); tout/tin/bucket/tagg/edgeprop/tlast
    TStruct, GMode, ACache,                      // ^IVG.TemporalStructural, ^IVG.GraphMode, ^IVG.AlgoCache
    Stmt, Tuple, Rec,                            // ^IVG.Ledger stmt, tuple, rec (history)
    Nkg, Labelset, Merged, Arno,                 // unscoped: ^NKG (s = interned id), ^KG("labelset"), deg2p_exact_merged, ^ArnoKG
    Bm25, Ivf, Plaid, VecIdx,                    // named search indexes (^BM25Idx records its graph; the others none)
}

/// One stored entry. Fields a kind does not use are 0 / empty.
pub struct E { pub k: K, pub g: Sp, pub s: Str, pub p: int, pub o: Str, pub eid: int, pub tbl: int, pub wm: int }

pub struct St { pub rows: Seq<E>, pub version: nat }

pub open spec fn in_g(e: E, c: Str) -> bool { canon(e.g) == c }

pub open spec fn nkg(id: Str) -> E {
    E { k: K::Nkg, g: Sp::S(Seq::<int>::empty()), s: id, p: 0, o: Seq::<int>::empty(), eid: 0, tbl: 0, wm: 0 }
}

pub open spec fn interned(r: Seq<E>, id: Str) -> bool { r.contains(nkg(id)) }

/// The kinds EraseGraph removes for its graph (Eraser.cls:130-256; Adjacency.RemoveGraph; TemporalIndex.EraseGraph;
/// EraseLedgerFor; EraseFHIRGraphRows; route rows of every routed table, Eraser.cls:167-178).
pub open spec fn graph_kill(k: K) -> bool {
    match k {
        K::Node | K::Label | K::Prop | K::Edge | K::Doc | K::NEmb | K::NEmbOpt | K::EEmb | K::NRoute | K::ERoute
        | K::FhirSide | K::Adj | K::Gen | K::Degc | K::Degw | K::NoLock | K::KLabel | K::KProp | K::Deg2p
        | K::Temporal | K::GMode | K::ACache | K::Stmt | K::Tuple => true,
        _ => false,
    }
}

/// GraphStores.Scoped as GraphStores.Digest walks it (the ledger's stmt/tuple are listed under "skipped").
pub open spec fn digest_kind(k: K) -> bool {
    match k {
        K::Node | K::Label | K::Prop | K::Edge | K::Doc | K::NEmb | K::NEmbOpt | K::EEmb | K::Registry | K::FhirSide
        | K::Adj | K::Gen | K::Degc | K::Degw | K::KLabel | K::KProp | K::Deg2p | K::Temporal | K::GMode | K::TStruct
        | K::ACache => true,
        _ => false,
    }
}

// ============================================================================ EraseGraph(g)

/// GraphEdgesInNKG || GraphNodesInNKG (Eraser.cls:215, 868-956): an edge (row or adjacency) of the graph with both
/// ends interned, or a node row of the graph that is interned.
pub open spec fn at_risk_graph(r: Seq<E>, c: Str) -> bool {
    exists|i: int| 0 <= i < r.len() && in_g(#[trigger] r[i], c) && (
        ((r[i].k == K::Edge || r[i].k == K::Adj) && interned(r, r[i].s) && interned(r, r[i].o))
        || (r[i].k == K::Node && interned(r, r[i].s)))
}

/// A registry row of graph c names this routed table (tbl > 0 stands for IsRouteName). Eraser.cls:84-97.
pub open spec fn claimed(r: Seq<E>, c: Str, tbl: int) -> bool {
    tbl > 0 && exists|i: int| 0 <= i < r.len() && (#[trigger] r[i]).k == K::Registry && in_g(r[i], c) && r[i].tbl == tbl
}

pub open spec fn reif_of_graph(r: Seq<E>, c: Str, eid: int) -> bool {
    exists|i: int| 0 <= i < r.len() && (#[trigger] r[i]).k == K::Edge && in_g(r[i], c) && r[i].eid == eid
}

/// EraseFHIRGraphRows(name, 0): UPDATE fhir_graphs SET wm_rsrc = 0, wm_ver = 0 for the graph; the row survives.
pub open spec fn reset_in(e: E, c: Str) -> E {
    if e.k == K::FhirReg && in_g(e, c) { E { wm: 0, ..e } } else { e }
}

/// df: the claimed routes whose post-commit DROP TABLE fails (caught and left, Eraser.cls:287-298).
pub open spec fn keep_graph(r: Seq<E>, c: Str, df: Set<int>, e: E) -> bool {
    if graph_kill(e.k) && in_g(e, c) { false }
    else if e.k == K::ACache { false }                          // InvalidateDerived: Kill ^IVG.AlgoCache, every graph
    else if e.k == K::Nkg { !at_risk_graph(r, c) }              // DropNKG when at risk: every graph's interning
    else if e.k == K::Reif { !reif_of_graph(r, c, e.eid) }      // edge_id IN (the graph's edges)
    else if e.k == K::RouteTable { !(claimed(r, c, e.tbl) && !df.contains(e.tbl)) }
    else if e.k == K::Registry && in_g(e, c) { !(claimed(r, c, e.tbl) && !df.contains(e.tbl)) }
    else { true }
}

pub open spec fn erase_graph(r: Seq<E>, c: Str, df: Set<int>) -> Seq<E> {
    r.map_values(|e: E| reset_in(e, c)).filter(|e: E| keep_graph(r, c, df, e))
}

pub open spec fn row_of(e: E, c: Str) -> bool { (e.k == K::Node || e.k == K::Edge) && in_g(e, c) }

/// EraseGraph's return: the %ROWCOUNT of the rdf_edges DELETE plus that of the nodes DELETE.
pub open spec fn count_graph(r: Seq<E>, c: Str) -> nat { r.filter(|e: E| row_of(e, c)).len() }

// ============================================================================ EraseIdSet (EraseNodes, EraseNodeIds)

pub open spec fn incident(e: E, c: Str, d: spec_fn(Str) -> bool) -> bool {
    e.k == K::Edge && in_g(e, c) && (d(e.s) || d(e.o))
}

pub open spec fn incident_triple(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool, e: E) -> bool {
    exists|i: int| 0 <= i < r.len() && incident(#[trigger] r[i], c, d) && r[i].s == e.s && r[i].p == e.p && r[i].o == e.o
}

pub open spec fn incident_eid(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool, eid: int) -> bool {
    exists|i: int| 0 <= i < r.len() && incident(#[trigger] r[i], c, d) && r[i].eid == eid
}

/// tHadEdges: an incident edge row, or adjacency of an id in either direction (Eraser.cls:532-546).
pub open spec fn had_edges(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool) -> bool {
    exists|i: int| 0 <= i < r.len() && in_g(#[trigger] r[i], c) && (r[i].k == K::Edge || r[i].k == K::Adj)
        && (d(r[i].s) || d(r[i].o))
}

pub open spec fn removed_node(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool) -> bool {
    exists|i: int| 0 <= i < r.len() && (#[trigger] r[i]).k == K::Node && in_g(r[i], c) && d(r[i].s)
}

/// tNkgAtRisk (an incident edge with both ends interned) || NKGMayHoldAny (an id of the set interned).
pub open spec fn ids_at_risk(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool) -> bool {
    (exists|i: int| 0 <= i < r.len() && incident(#[trigger] r[i], c, d) && interned(r, r[i].s) && interned(r, r[i].o))
    || (exists|id: Str| #[trigger] d(id) && interned(r, id))
}

/// The node's own stores in graph c (Eraser.cls:551-590) and its degree-cache entries (Adjacency.RemoveSource).
pub open spec fn node_kill(k: K) -> bool {
    match k {
        K::Node | K::Label | K::Prop | K::Doc | K::NEmb | K::NEmbOpt | K::NRoute | K::FhirSide | K::KLabel | K::KProp
        | K::Gen | K::Degc => true,
        _ => false,
    }
}

pub open spec fn keep_ids(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool, e: E) -> bool {
    if in_g(e, c) && node_kill(e.k) && d(e.s) { false }
    else if incident(e, c, d) { false }                                                      // EraseEdgeRow
    else if e.k == K::Reif { !incident_eid(r, c, d, e.eid) }
    else if (e.k == K::EEmb || e.k == K::ERoute || e.k == K::Stmt || e.k == K::Tuple) && in_g(e, c) {
        !incident_triple(r, c, d, e)                                                         // only through a row
    }
    else if (e.k == K::Adj || e.k == K::Temporal) && in_g(e, c) { !(d(e.s) || d(e.o)) }
    else if e.k == K::Deg2p && in_g(e, c) { !had_edges(r, c, d) }
    else if e.k == K::ACache { !(removed_node(r, c, d) || had_edges(r, c, d)) }
    else if e.k == K::Nkg { !((removed_node(r, c, d) || had_edges(r, c, d)) && ids_at_risk(r, c, d)) }
    else { true }
}

pub open spec fn erase_ids(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool) -> Seq<E> { r.filter(|e: E| keep_ids(r, c, d, e)) }

/// EraseIdSet's return: node rows only (Eraser.cls:587-590).
pub open spec fn count_ids(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool) -> nat {
    r.filter(|e: E| e.k == K::Node && in_g(e, c) && d(e.s)).len()
}

/// EraseNodes: ids collected from node rows of the graph (Eraser.cls:333-347).
pub open spec fn prefix_sel(r: Seq<E>, c: Str, pfx: Str) -> spec_fn(Str) -> bool {
    |id: Str| exists|i: int| 0 <= i < r.len() && (#[trigger] r[i]).k == K::Node && in_g(r[i], c)
        && r[i].s == id && has_prefix(id, pfx)
}

/// EraseNodeIds: the ids named, present or not; "" skipped (Eraser.cls:382-386).
pub open spec fn list_sel(ids: Seq<Str>) -> spec_fn(Str) -> bool {
    |id: Str| ids.contains(id) && id.len() > 0
}

// ============================================================================ EraseEdges(g, [{s,p,o}])

pub open spec fn tri(e: E) -> (Str, int, Str) { (e.s, e.p, e.o) }

pub open spec fn edge_sel(e: E, c: Str, t: spec_fn((Str, int, Str)) -> bool) -> bool {
    e.k == K::Edge && in_g(e, c) && t(tri(e))
}

pub open spec fn row_for(r: Seq<E>, c: Str, t: spec_fn((Str, int, Str)) -> bool, x: (Str, int, Str)) -> bool {
    exists|i: int| 0 <= i < r.len() && edge_sel(#[trigger] r[i], c, t) && tri(r[i]) == x
}

pub open spec fn removed_any_edge(r: Seq<E>, c: Str, t: spec_fn((Str, int, Str)) -> bool) -> bool {
    exists|i: int| 0 <= i < r.len() && in_g(#[trigger] r[i], c) && (r[i].k == K::Edge || r[i].k == K::Adj)
        && t(tri(r[i]))
}

pub open spec fn keep_edges(r: Seq<E>, c: Str, t: spec_fn((Str, int, Str)) -> bool, e: E) -> bool {
    if edge_sel(e, c, t) { false }
    else if e.k == K::Reif { !(exists|i: int| 0 <= i < r.len() && edge_sel(#[trigger] r[i], c, t) && r[i].eid == e.eid) }
    else if (e.k == K::EEmb || e.k == K::ERoute || e.k == K::Stmt || e.k == K::Tuple) && in_g(e, c) {
        !row_for(r, c, t, tri(e))
    }
    else if e.k == K::Adj && in_g(e, c) { !t(tri(e)) }                         // Adjacency.Remove per triple
    else if (e.k == K::Deg2p && in_g(e, c)) || e.k == K::ACache || e.k == K::Nkg { !removed_any_edge(r, c, t) }
    else { true }
}

pub open spec fn erase_edges(r: Seq<E>, c: Str, t: spec_fn((Str, int, Str)) -> bool) -> Seq<E> {
    r.filter(|e: E| keep_edges(r, c, t, e))
}

pub open spec fn count_edges(r: Seq<E>, c: Str, t: spec_fn((Str, int, Str)) -> bool) -> nat {
    r.filter(|e: E| edge_sel(e, c, t)).len()
}

// ============================================================================ EraseAll

pub open spec fn claimed_any(r: Seq<E>, tbl: int) -> bool {
    tbl > 0 && exists|i: int| 0 <= i < r.len() && (#[trigger] r[i]).k == K::Registry && r[i].tbl == tbl
}

pub open spec fn reset_all(e: E) -> E { if e.k == K::FhirReg { E { wm: 0, ..e } } else { e } }

/// Eraser.cls:709-845. The registry is deleted whole inside the transaction; claimed routes dropped after the commit.
pub open spec fn keep_all(r: Seq<E>, df: Set<int>, e: E) -> bool {
    match e.k {
        K::Quar | K::Rec | K::FhirReg | K::Bm25 | K::Ivf | K::Plaid | K::VecIdx => true,
        K::RouteTable => !(claimed_any(r, e.tbl) && !df.contains(e.tbl)),
        _ => false,
    }
}

pub open spec fn erase_all(r: Seq<E>, df: Set<int>) -> Seq<E> {
    r.map_values(|e: E| reset_all(e)).filter(|e: E| keep_all(r, df, e))
}

pub open spec fn count_all(r: Seq<E>) -> nat { r.filter(|e: E| e.k == K::Node || e.k == K::Edge).len() }

// ============================================================================ the bypass: delete_edge

/// nodes_edges.py delete_edge (1382-1456): DELETE FROM rdf_edges for the triple in the graph (COALESCE), the
/// adjacency index clears ^KG out/in per row; nothing else.
pub open spec fn delete_edge(r: Seq<E>, c: Str, x: (Str, int, Str)) -> Seq<E> {
    r.filter(|e: E| !((e.k == K::Edge || e.k == K::Adj) && in_g(e, c) && tri(e) == x))
}

// ============================================================================ one Eraser call, its transaction

pub enum Ep {
    Graph { g: Option<Str> },
    Prefix { g: Option<Str>, pfx: Str },
    Ids { g: Option<Str>, ids: Seq<Str> },
    Edges { g: Option<Str>, t: spec_fn((Str, int, Str)) -> bool },
    All,
}

pub enum Out { Refused, Failed, Count(nat) }

pub open spec fn gname(g: Option<Str>) -> Str { match g { None => Seq::<int>::empty(), Some(n) => n } }

/// Refusals raised before TSTART (and, on the engine, before the Native call): the empty prefix first
/// (Eraser.cls:324; nodes_edges.py:1554), then the name (GraphKey.ForIndex/ForName; validate_graph_name).
pub open spec fn refused(ep: Ep) -> bool {
    match ep {
        Ep::Graph { g } => !valid(gname(g)),
        Ep::Prefix { g, pfx } => pfx.len() == 0 || !valid(gname(g)),
        Ep::Ids { g, ids } => !valid(gname(g)),
        Ep::Edges { g, t } => !valid(gname(g)),
        Ep::All => false,
    }
}

pub open spec fn effect(r: Seq<E>, ep: Ep, df: Set<int>) -> Seq<E> {
    match ep {
        Ep::Graph { g } => erase_graph(r, gname(g), df),
        Ep::Prefix { g, pfx } => erase_ids(r, gname(g), prefix_sel(r, gname(g), pfx)),
        Ep::Ids { g, ids } => erase_ids(r, gname(g), list_sel(ids)),
        Ep::Edges { g, t } => erase_edges(r, gname(g), t),
        Ep::All => erase_all(r, df),
    }
}

pub open spec fn count(r: Seq<E>, ep: Ep) -> nat {
    match ep {
        Ep::Graph { g } => count_graph(r, gname(g)),
        Ep::Prefix { g, pfx } => count_ids(r, gname(g), prefix_sel(r, gname(g), pfx)),
        Ep::Ids { g, ids } => count_ids(r, gname(g), list_sel(ids)),
        Ep::Edges { g, t } => count_edges(r, gname(g), t),
        Ep::All => count_all(r),
    }
}

/// One Eraser class-method call. `fail`: None, no step fails; Some(late), a step throws and the Catch rolls back to
/// the level it found (While $TLevel > tTxnLevel { TROLLBACK 1 }); `late` = after Adjacency's $Increment of
/// ^KG("__version"), which a rollback does not take back (Adjacency.cls:57). A success bumps the version.
pub open spec fn call(st: St, ep: Ep, fail: Option<bool>, df: Set<int>) -> (Out, St) {
    if refused(ep) { (Out::Refused, st) }
    else {
        match fail {
            Some(late) => (Out::Failed, St { rows: st.rows, version: if late { st.version + 1 } else { st.version } }),
            None => (Out::Count(count(st.rows, ep)), St { rows: effect(st.rows, ep, df), version: st.version + 1 }),
        }
    }
}

// ============================================================================ the caller's transaction

/// Joined: the Eraser runs in the caller's process (engine on the caller's connection: _iris_obj = createIRIS(conn);
/// the store's _eraser_txn), its TSTART nests under the caller's level, and its post-commit DROP TABLE runs inside the
/// caller's transaction (observed I65Y: the caller's rollback brings the table and its registry row back).
/// Not joined: a from_connect engine's erase_graph/erase_all/bulk_delete_adjacency run on its dedicated Native API
/// connection (engine.py _iris_obj), committing on their own. w = the caller's own uncommitted rows (other graphs).
pub open spec fn joined_then(base: St, w: Seq<E>, ep: Ep, fail: Option<bool>, df: Set<int>, commit: bool) -> (Out, St) {
    let (o, p2) = call(St { rows: base.rows + w, version: base.version }, ep, fail, df);
    (o, if commit { p2 } else { St { rows: base.rows, version: p2.version } })
}

pub open spec fn dedicated_then(base: St, w: Seq<E>, ep: Ep, fail: Option<bool>, df: Set<int>, commit: bool) -> (Out, St) {
    let (o, b2) = call(base, ep, fail, df);
    (o, if commit { St { rows: b2.rows + w, version: b2.version } } else { b2 })
}

// ============================================================================ the store's chunked list erase

/// iris_sql_store.delete_nodes: one EraseNodeIds call per chunk of _DELETE_CHUNK (500) ids. Not joined, each call owns
/// its transaction and commits; the first failing call raises, earlier chunks stay erased (bug-led-011).
pub open spec fn list_erase(st: St, g: Option<Str>, chunks: Seq<Seq<Str>>, fail_at: int, acc: nat) -> (Out, St)
    decreases chunks.len()
{
    if chunks.len() == 0 { (Out::Count(acc), st) }
    else {
        let (o, s1) = call(st, Ep::Ids { g, ids: chunks[0] }, if fail_at == 0 { Some(false) } else { None }, Set::empty());
        match o {
            Out::Count(n) => list_erase(s1, g, chunks.drop_first(), fail_at - 1, acc + n),
            _ => (o, s1),
        }
    }
}

/// Inside a caller's transaction (_eraser_txn joined: WriteTxn level over the caller's), a failing chunk raises and
/// the `with txn` exit rolls IVG's level back: every chunk of this call, none of the caller's earlier work.
pub open spec fn list_erase_joined(st: St, g: Option<Str>, chunks: Seq<Seq<Str>>, fail_at: int) -> (Out, St) {
    let (o, s1) = list_erase(st, g, chunks, fail_at, 0);
    match o { Out::Count(n) => (o, s1), _ => (o, St { rows: st.rows, version: s1.version }) }
}

// ============================================================================ the engine's erase methods

pub enum Method {
    EraseGraph, DropGraph, EraseAll, DeleteNodesByPrefix, DeleteNode, BulkDeleteNodes, StoreDeleteNodes,
    StoreDeleteEdges, StoreDeleteNodesByPrefix, BulkDeleteAdjacency, EraseBareNodes, DeleteEdge,
}

pub enum EraserEp { Graph, All, Nodes, NodeIds, Edges, BareNodes }

/// Which Eraser entry point each method reaches (nodes_edges.py:1473-1595, 2176-2340; iris_sql_store.py:1324-1500,
/// 2816-2840). delete_edge runs its own DELETE FROM rdf_edges (nodes_edges.py:1426-1440).
pub open spec fn eraser_of(m: Method) -> Option<EraserEp> {
    match m {
        Method::EraseGraph | Method::DropGraph => Some(EraserEp::Graph),
        Method::EraseAll => Some(EraserEp::All),
        Method::DeleteNodesByPrefix | Method::StoreDeleteNodesByPrefix => Some(EraserEp::Nodes),
        Method::DeleteNode | Method::BulkDeleteNodes | Method::StoreDeleteNodes => Some(EraserEp::NodeIds),
        Method::StoreDeleteEdges | Method::BulkDeleteAdjacency => Some(EraserEp::Edges),
        Method::EraseBareNodes => Some(EraserEp::BareNodes),
        Method::DeleteEdge => None,
    }
}

/// drop_graph(g) is `return self.erase_graph(graph_id)` (nodes_edges.py:1588-1595).
pub open spec fn method_ep(m: Method, g: Option<Str>) -> Ep {
    match m { Method::DropGraph => Ep::Graph { g }, _ => Ep::Graph { g } }
}

/// bulk_delete_adjacency(ids) for one graph: the triples of every edge row of c with an id as an end, then
/// EraseEdges(c, those triples) (nodes_edges.py:2318-2335). Returns len(ids).
pub open spec fn bda_triples(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool) -> spec_fn((Str, int, Str)) -> bool {
    |x: (Str, int, Str)| exists|i: int| 0 <= i < r.len() && incident(#[trigger] r[i], c, d) && tri(r[i]) == x
}

// ============================================================================ the empty-graph reader

/// GraphStores.Digest(g) reports 0 entries in every scoped CONTENT store it walks. Two scoped stores it walks are
/// configuration EraseGraph keeps on purpose: ^IVG.TemporalStructural and the registry rows of non-route tables.
pub open spec fn config_kind(k: K) -> bool { k == K::TStruct || k == K::Registry }

pub open spec fn digest_empty(r: Seq<E>, c: Str) -> bool {
    forall|i: int| 0 <= i < r.len() ==> !(digest_kind((#[trigger] r[i]).k) && !config_kind(r[i].k) && in_g(r[i], c))
}

// ============================================================================ helper lemmas

pub proof fn lemma_not_in_filter(s: Seq<E>, f: spec_fn(E) -> bool, e: E)
    requires !f(e),
    ensures !s.filter(f).contains(e),
{
    if s.filter(f).contains(e) {
        let j = choose|j: int| 0 <= j < s.filter(f).len() && s.filter(f)[j] == e;
        s.lemma_filter_pred(f, j);
    }
}

pub proof fn lemma_in_filter(s: Seq<E>, f: spec_fn(E) -> bool, i: int)
    requires 0 <= i < s.len(), f(s[i]),
    ensures s.filter(f).contains(s[i]),
{
    s.lemma_filter_contains(f, i);
}

pub proof fn lemma_in_mapped(r: Seq<E>, m: spec_fn(E) -> E, f: spec_fn(E) -> bool, i: int)
    requires 0 <= i < r.len(), f(m(r[i])),
    ensures r.map_values(m).filter(f).contains(m(r[i])),
{
    let mv = r.map_values(m);
    assert(mv[i] == m(r[i]));
    mv.lemma_filter_contains(f, i);
}

pub proof fn lemma_filter_sub(s: Seq<E>, f: spec_fn(E) -> bool, e: E)
    requires s.filter(f).contains(e),
    ensures s.contains(e), f(e),
{
    let j = choose|j: int| 0 <= j < s.filter(f).len() && s.filter(f)[j] == e;
    s.lemma_filter_pred(f, j);
    s.lemma_filter_contains_rev(f, e);
}

// ============================================================================ erasure.scope

/// erasure.scope#o01, #o03, #o04, #o05 (in part), search.erasure#o01/#o02, erasure.kept#o04,
/// structure.degree.cache.erase#o01 (graph case): every entry of a graph-scoped kind spelled in graph c is gone after
/// EraseGraph(c), whatever its spelling.
pub proof fn theorem_graph_erase_removes_scoped(r: Seq<E>, c: Str, df: Set<int>, e: E)
    requires graph_kill(e.k), in_g(e, c),
    ensures !erase_graph(r, c, df).contains(e),
{
    let mv = r.map_values(|x: E| reset_in(x, c));
    lemma_not_in_filter(mv, |x: E| keep_graph(r, c, df, x), e);
}

/// erasure.scope#o07: the default graph in both spellings, NULL and ''.
pub proof fn theorem_default_graph_both_spellings(r: Seq<E>, df: Set<int>, k: K, s: Str, p: int, o: Str, eid: int)
    requires graph_kill(k),
    ensures
        !erase_graph(r, Seq::<int>::empty(), df).contains(E { k, g: Sp::Null, s, p, o, eid, tbl: 0, wm: 0 }),
        !erase_graph(r, Seq::<int>::empty(), df).contains(E { k, g: Sp::S(Seq::<int>::empty()), s, p, o, eid, tbl: 0, wm: 0 }),
        erase_graph(r, gname(None), df) == erase_graph(r, gname(Some(Seq::<int>::empty())), df),
{
    theorem_graph_erase_removes_scoped(r, Seq::<int>::empty(), df, E { k, g: Sp::Null, s, p, o, eid, tbl: 0, wm: 0 });
    theorem_graph_erase_removes_scoped(r, Seq::<int>::empty(), df, E { k, g: Sp::S(Seq::<int>::empty()), s, p, o, eid, tbl: 0, wm: 0 });
}

/// erasure.scope#o02: the reifications of the graph's edges and the FHIR side rows go.
pub proof fn theorem_graph_erase_removes_reifications_and_fhir_side(r: Seq<E>, c: Str, df: Set<int>, i: int, f: E)
    requires 0 <= i < r.len(), r[i].k == K::Edge, in_g(r[i], c), f.k == K::Reif, f.eid == r[i].eid,
    ensures
        !erase_graph(r, c, df).contains(f),
        forall|x: E| x.k == K::FhirSide && in_g(x, c) ==> !(#[trigger] erase_graph(r, c, df).contains(x)),
{
    assert(reif_of_graph(r, c, f.eid));
    let mv = r.map_values(|x: E| reset_in(x, c));
    lemma_not_in_filter(mv, |x: E| keep_graph(r, c, df, x), f);
    assert forall|x: E| x.k == K::FhirSide && in_g(x, c) implies !(#[trigger] erase_graph(r, c, df).contains(x)) by {
        theorem_graph_erase_removes_scoped(r, c, df, x);
    }
}

/// The frame kinds: what EraseGraph(c) leaves alone outside c, as built (the derived caches it clears for every graph,
/// the unscoped interning and the reifications / routes it decides through c are not in it).
pub open spec fn frame_kind(k: K) -> bool {
    match k { K::ACache | K::Nkg | K::Reif | K::RouteTable | K::Registry => false, _ => true }
}

/// erasure.scope#o06, search.erasure#o03: another graph's entries are kept, even with the same node IDs; a reification
/// is kept when its edge is not one of c's (edge_id is the table's identity: one row per eid, premise `eid_unique`).
pub proof fn theorem_graph_erase_frame(r: Seq<E>, c: Str, df: Set<int>, i: int)
    requires 0 <= i < r.len(), !in_g(r[i], c), frame_kind(r[i].k),
    ensures erase_graph(r, c, df).contains(r[i]),
{
    assert(reset_in(r[i], c) == r[i]);
    lemma_in_mapped(r, |x: E| reset_in(x, c), |x: E| keep_graph(r, c, df, x), i);
}

pub open spec fn eid_unique(r: Seq<E>) -> bool {
    forall|i: int, j: int| 0 <= i < r.len() && 0 <= j < r.len() && (#[trigger] r[i]).k == K::Edge
        && (#[trigger] r[j]).k == K::Edge && r[i].eid == r[j].eid ==> i == j
}

pub proof fn theorem_graph_erase_keeps_other_reifications(r: Seq<E>, c: Str, df: Set<int>, i: int, j: int)
    requires eid_unique(r), 0 <= i < r.len(), 0 <= j < r.len(), r[i].k == K::Edge, !in_g(r[i], c),
        r[j].k == K::Reif, r[j].eid == r[i].eid,
    ensures erase_graph(r, c, df).contains(r[j]),
{
    assert(!reif_of_graph(r, c, r[j].eid));
    assert(reset_in(r[j], c) == r[j]);
    lemma_in_mapped(r, |x: E| reset_in(x, c), |x: E| keep_graph(r, c, df, x), j);
}

/// erasure.scope#o08, erasure.entry-points#o04: a refused call changes nothing and returns Refused.
pub proof fn theorem_refusal_changes_nothing(st: St, ep: Ep, fail: Option<bool>, df: Set<int>)
    requires refused(ep),
    ensures call(st, ep, fail, df) == (Out::Refused, st),
{}

pub proof fn theorem_unsafe_or_empty_refused(st: St, g: Str, pfx: Str, fail: Option<bool>, df: Set<int>)
    ensures
        g == seq![48int] ==> call(st, Ep::Graph { g: Some(g) }, fail, df) == (Out::Refused, st),
        (g.len() == 1 && g[0] == 1) ==> call(st, Ep::Graph { g: Some(g) }, fail, df) == (Out::Refused, st),
        pfx.len() == 0 ==> call(st, Ep::Prefix { g: Some(g), pfx }, fail, df) == (Out::Refused, st),
{
    if g.len() == 1 && g[0] == 1 {
        assert(ctl(g[0]));
        assert(!valid(g));
    }
}

// ============================================================================ erasure.live-statements

/// erasure.live-statements#o02: every statement and tuple entry of the graph goes; another graph's stay.
pub proof fn theorem_graph_erase_statements(r: Seq<E>, c: Str, df: Set<int>, i: int)
    requires 0 <= i < r.len(), r[i].k == K::Stmt || r[i].k == K::Tuple,
    ensures erase_graph(r, c, df).contains(r[i]) <==> !in_g(r[i], c),
{
    if in_g(r[i], c) { theorem_graph_erase_removes_scoped(r, c, df, r[i]); }
    else { theorem_graph_erase_frame(r, c, df, i); }
}

/// erasure.live-statements#o03: an ID-list or prefix erase removes the statement (and tuple) of each relationship
/// whose row it deletes, and only those; a relationship-list erase likewise.
pub proof fn theorem_ids_erase_statements(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool, i: int)
    requires 0 <= i < r.len(), r[i].k == K::Stmt || r[i].k == K::Tuple,
    ensures erase_ids(r, c, d).contains(r[i]) <==> !(in_g(r[i], c) && incident_triple(r, c, d, r[i])),
{
    if in_g(r[i], c) && incident_triple(r, c, d, r[i]) {
        lemma_not_in_filter(r, |x: E| keep_ids(r, c, d, x), r[i]);
    } else {
        lemma_in_filter(r, |x: E| keep_ids(r, c, d, x), i);
    }
}

pub proof fn theorem_edges_erase_statements(r: Seq<E>, c: Str, t: spec_fn((Str, int, Str)) -> bool, i: int)
    requires 0 <= i < r.len(), r[i].k == K::Stmt || r[i].k == K::Tuple,
    ensures erase_edges(r, c, t).contains(r[i]) <==> !(in_g(r[i], c) && row_for(r, c, t, tri(r[i]))),
{
    if in_g(r[i], c) && row_for(r, c, t, tri(r[i])) {
        lemma_not_in_filter(r, |x: E| keep_edges(r, c, t, x), r[i]);
    } else {
        lemma_in_filter(r, |x: E| keep_edges(r, c, t, x), i);
    }
}

// ============================================================================ erasure.history

/// erasure.history#o01: no entry point removes or changes a ledger record.
pub proof fn theorem_no_erase_touches_history(st: St, ep: Ep, fail: Option<bool>, df: Set<int>, i: int)
    requires 0 <= i < st.rows.len(), st.rows[i].k == K::Rec,
    ensures call(st, ep, fail, df).1.rows.contains(st.rows[i]),
{
    theorem_no_erase_touches_kind(st, ep, fail, df, i);
}

/// The kinds no entry point ever removes or rewrites: history, the quarantine and every named search index
/// (search.erasure.indexes "Today no erase empties a named index"; bug-srch-117, bug-srch-001).
pub open spec fn never_kind(k: K) -> bool {
    match k { K::Rec | K::Quar | K::Bm25 | K::Ivf | K::Plaid | K::VecIdx => true, _ => false }
}

pub proof fn theorem_no_erase_touches_kind(st: St, ep: Ep, fail: Option<bool>, df: Set<int>, i: int)
    requires 0 <= i < st.rows.len(), never_kind(st.rows[i].k),
    ensures call(st, ep, fail, df).1.rows.contains(st.rows[i]),
{
    let r = st.rows;
    if refused(ep) || fail.is_some() {
        assert(r[i] == r[i]);
        assert(r.contains(r[i]));
    } else {
        match ep {
            Ep::Graph { g } => {
                assert(reset_in(r[i], gname(g)) == r[i]);
                lemma_in_mapped(r, |x: E| reset_in(x, gname(g)), |x: E| keep_graph(r, gname(g), df, x), i);
            },
            Ep::Prefix { g, pfx } => { lemma_in_filter(r, |x: E| keep_ids(r, gname(g), prefix_sel(r, gname(g), pfx), x), i); },
            Ep::Ids { g, ids } => { lemma_in_filter(r, |x: E| keep_ids(r, gname(g), list_sel(ids), x), i); },
            Ep::Edges { g, t } => { lemma_in_filter(r, |x: E| keep_edges(r, gname(g), t, x), i); },
            Ep::All => {
                assert(reset_all(r[i]) == r[i]);
                lemma_in_mapped(r, |x: E| reset_all(x), |x: E| keep_all(r, df, x), i);
            },
        }
    }
}

/// erasure.history#o03: after EraseGraph(c), GraphStores.Digest(c) reports every scoped store empty.
pub proof fn theorem_graph_erase_digest_empty(r: Seq<E>, c: Str, df: Set<int>)
    ensures digest_empty(erase_graph(r, c, df), c),
{
    let post = erase_graph(r, c, df);
    let mv = r.map_values(|x: E| reset_in(x, c));
    assert forall|i: int| 0 <= i < post.len() implies !(digest_kind((#[trigger] post[i]).k) && !config_kind(post[i].k) && in_g(post[i], c)) by {
        mv.lemma_filter_pred(|x: E| keep_graph(r, c, df, x), i);
    }
}

// ============================================================================ erasure.kept

/// erasure.kept#o02, #o03, #o05: the temporal-only setting is kept; the FHIR registration is kept with its watermarks
/// reset to 0.
pub proof fn theorem_graph_erase_keeps_settings(r: Seq<E>, c: Str, df: Set<int>, i: int)
    requires 0 <= i < r.len(), r[i].k == K::TStruct || r[i].k == K::FhirReg,
    ensures
        r[i].k == K::TStruct ==> erase_graph(r, c, df).contains(r[i]),
        r[i].k == K::FhirReg && in_g(r[i], c) ==> erase_graph(r, c, df).contains(E { wm: 0, ..r[i] }),
        r[i].k == K::FhirReg && in_g(r[i], c) && r[i].wm != 0 ==> !erase_graph(r, c, df).contains(r[i]),
{
    lemma_in_mapped(r, |x: E| reset_in(x, c), |x: E| keep_graph(r, c, df, x), i);
    if r[i].k == K::FhirReg && in_g(r[i], c) && r[i].wm != 0 {
        let mv = r.map_values(|x: E| reset_in(x, c));
        if erase_graph(r, c, df).contains(r[i]) {
            lemma_filter_sub(mv, |x: E| keep_graph(r, c, df, x), r[i]);
            let j = choose|j: int| 0 <= j < mv.len() && mv[j] == r[i];
            assert(mv[j] == reset_in(r[j], c));
        }
    }
}

/// erasure.kept#o01 (the half that holds): the label-set interning, Arno's merged counts and snapshot survive a
/// single-graph erase, and ^NKG survives when the graph has nothing interned. The other half is refuted below.
pub proof fn theorem_graph_erase_keeps_unscoped_except_nkg(r: Seq<E>, c: Str, df: Set<int>, i: int)
    requires 0 <= i < r.len(), r[i].k == K::Labelset || r[i].k == K::Merged || r[i].k == K::Arno
        || (r[i].k == K::Nkg && !at_risk_graph(r, c)),
    ensures erase_graph(r, c, df).contains(r[i]),
{
    assert(reset_in(r[i], c) == r[i]);
    lemma_in_mapped(r, |x: E| reset_in(x, c), |x: E| keep_graph(r, c, df, x), i);
}

/// erasure.kept#o06: no entry point changes the embedding quarantine (also history and the graphless indexes).
pub proof fn theorem_no_erase_touches_quarantine(st: St, ep: Ep, fail: Option<bool>, df: Set<int>, i: int)
    requires 0 <= i < st.rows.len(), st.rows[i].k == K::Quar,
    ensures call(st, ep, fail, df).1.rows.contains(st.rows[i]),
{
    theorem_no_erase_touches_kind(st, ep, fail, df, i);
}

/// erasure.kept#o07, erasure.entry-points#o02: EraseAll leaves nothing but the quarantine, history, the FHIR
/// registrations (watermarks reset), the named search indexes and the routed tables it may not or could not drop.
pub proof fn theorem_erase_all_empties(r: Seq<E>, df: Set<int>, e: E)
    requires !(e.k == K::Quar || e.k == K::Rec || e.k == K::FhirReg || e.k == K::Bm25 || e.k == K::Ivf
        || e.k == K::Plaid || e.k == K::VecIdx || e.k == K::RouteTable),
    ensures !erase_all(r, df).contains(e),
{
    lemma_not_in_filter(r.map_values(|x: E| reset_all(x)), |x: E| keep_all(r, df, x), e);
}

// ============================================================================ erasure.count

/// erasure.count#o03: adding a derived entry (anything but a node or relationship row) never changes the count.
pub proof fn theorem_count_ignores_derived(r: Seq<E>, c: Str, e: E)
    requires !(e.k == K::Node || e.k == K::Edge),
    ensures count_graph(r.push(e), c) == count_graph(r, c), count_all(r.push(e)) == count_all(r),
{
    let f = |x: E| row_of(x, c);
    let h = |x: E| x.k == K::Node || x.k == K::Edge;
    reveal_with_fuel(Seq::filter, 1);
    assert(r.push(e).drop_last() =~= r);
    assert(r.push(e).filter(f) == r.filter(f));
    assert(r.push(e).filter(h) == r.filter(h));
}

/// erasure.count#o04: the count is a sum of row effects. Each relationship row counts (a multigraph's two rows of
/// one triple count twice) and the node rows add to it.
pub proof fn theorem_count_adds_rows(r: Seq<E>, c: Str, e: E)
    requires row_of(e, c),
    ensures count_graph(r.push(e), c) == count_graph(r, c) + 1,
{
    let f = |x: E| row_of(x, c);
    reveal_with_fuel(Seq::filter, 1);
    assert(r.push(e).drop_last() =~= r);
}

// ============================================================================ erasure.entry-points

/// erasure.entry-points#o03 / #o05 and the ID path of algorithms.cache.erasure, structure.degree.cache.erase: the
/// selected nodes' own stores in c and every relationship of c with one of them as an end go; the same IDs in
/// another graph are kept.
pub proof fn theorem_ids_erase(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool, i: int)
    requires 0 <= i < r.len(),
    ensures
        (in_g(r[i], c) && node_kill(r[i].k) && d(r[i].s)) ==> !erase_ids(r, c, d).contains(r[i]),
        incident(r[i], c, d) ==> !erase_ids(r, c, d).contains(r[i]),
        ((r[i].k == K::Adj || r[i].k == K::Temporal) && in_g(r[i], c) && (d(r[i].s) || d(r[i].o)))
            ==> !erase_ids(r, c, d).contains(r[i]),
        (!in_g(r[i], c) && r[i].k != K::ACache && r[i].k != K::Nkg && r[i].k != K::Reif)
            ==> erase_ids(r, c, d).contains(r[i]),
        (r[i].k == K::ACache && (removed_node(r, c, d) || had_edges(r, c, d))) ==> !erase_ids(r, c, d).contains(r[i]),
{
    if keep_ids(r, c, d, r[i]) { lemma_in_filter(r, |x: E| keep_ids(r, c, d, x), i); }
    else { lemma_not_in_filter(r, |x: E| keep_ids(r, c, d, x), r[i]); }
}

/// erasure.entry-points#o03: the prefix erase selects through node rows of c (Eraser.cls:333-347).
pub proof fn theorem_prefix_selects_node_rows(r: Seq<E>, c: Str, pfx: Str, id: Str)
    ensures (prefix_sel(r, c, pfx))(id) <==>
        (has_prefix(id, pfx) && exists|i: int| 0 <= i < r.len() && (#[trigger] r[i]).k == K::Node && in_g(r[i], c) && r[i].s == id),
{}

/// erasure.entry-points#o06: a relationship-list erase removes the listed relationships' rows and adjacency in c and
/// never a node row.
pub proof fn theorem_edges_erase_keeps_nodes(r: Seq<E>, c: Str, t: spec_fn((Str, int, Str)) -> bool, i: int)
    requires 0 <= i < r.len(),
    ensures
        r[i].k == K::Node ==> erase_edges(r, c, t).contains(r[i]),
        edge_sel(r[i], c, t) ==> !erase_edges(r, c, t).contains(r[i]),
        (r[i].k == K::Adj && in_g(r[i], c) && t(tri(r[i]))) ==> !erase_edges(r, c, t).contains(r[i]),
        (!in_g(r[i], c) && r[i].k != K::ACache && r[i].k != K::Nkg && r[i].k != K::Reif) ==> erase_edges(r, c, t).contains(r[i]),
{
    if keep_edges(r, c, t, r[i]) { lemma_in_filter(r, |x: E| keep_edges(r, c, t, x), i); }
    else { lemma_not_in_filter(r, |x: E| keep_edges(r, c, t, x), r[i]); }
}

/// erasure.entry-points#o01: every engine/store erase method reaches an Eraser entry point except delete_edge.
pub proof fn theorem_methods_reach_eraser(m: Method)
    ensures m != Method::DeleteEdge <==> eraser_of(m).is_some(),
{}

/// erasure.entry-points.single-path#o02: drop_graph(g) is erase_graph(g), outcome and stores.
pub proof fn theorem_drop_graph_is_erase_graph(st: St, g: Option<Str>, fail: Option<bool>, df: Set<int>)
    ensures call(st, method_ep(Method::DropGraph, g), fail, df) == call(st, method_ep(Method::EraseGraph, g), fail, df),
{}

/// erasure.entry-points.single-path#o03: bulk_delete_adjacency(ids) on one graph is EraseEdges(c, the triples of c's
/// rows incident to ids): the same rows go as an ID erase would take as incident edges, and no node.
pub proof fn theorem_bda_is_erase_edges(r: Seq<E>, c: Str, d: spec_fn(Str) -> bool, i: int)
    requires 0 <= i < r.len(),
    ensures
        incident(r[i], c, d) ==> !erase_edges(r, c, bda_triples(r, c, d)).contains(r[i]),
        r[i].k == K::Node ==> erase_edges(r, c, bda_triples(r, c, d)).contains(r[i]),
{
    if incident(r[i], c, d) {
        assert((bda_triples(r, c, d))(tri(r[i])));
        assert(edge_sel(r[i], c, bda_triples(r, c, d)));
    }
    theorem_edges_erase_keeps_nodes(r, c, bda_triples(r, c, d), i);
}

// ============================================================================ erasure.atomic

/// erasure.atomic#o01/#o02 (own failure): a failed call returns Failed and leaves every store as it found it; only the
/// ^KG("__version") stamp may have moved ($Increment survives TROLLBACK).
pub proof fn theorem_failed_call_leaves_stores(st: St, ep: Ep, late: bool, df: Set<int>)
    requires !refused(ep),
    ensures call(st, ep, Some(late), df).0 == Out::Failed, call(st, ep, Some(late), df).1.rows == st.rows,
        call(st, ep, Some(late), df).1.version >= st.version,
{}

/// erasure.atomic#o03/#o04 (joined): the erase never ends the caller's transaction. Its own failure keeps the
/// caller's earlier work pending (a later commit keeps it); the caller's rollback restores everything the erase
/// removed, routed tables included; the caller's commit makes the erase final.
pub proof fn theorem_joined_caller_decides(base: St, w: Seq<E>, ep: Ep, fail: Option<bool>, df: Set<int>)
    requires !refused(ep),
    ensures
        joined_then(base, w, ep, fail, df, false).1.rows == base.rows,
        fail.is_some() ==> joined_then(base, w, ep, fail, df, true).1.rows == base.rows + w,
        fail.is_none() ==> joined_then(base, w, ep, fail, df, true).1.rows == effect(base.rows + w, ep, df),
{}

// ============================================================================ erasure.atomic.routes

/// erasure.atomic.routes#o01: the graph's rows in every routed table go inside the transaction.
/// #o02/#o04: after the commit a routed table is dropped only when c's registry claims it and the drop succeeds; an
/// unregistered (orphan) table is never dropped. #o03: a failed drop keeps the table and its registry row.
pub proof fn theorem_graph_erase_routes(r: Seq<E>, c: Str, df: Set<int>, i: int)
    requires 0 <= i < r.len(), r[i].k == K::NRoute || r[i].k == K::ERoute || r[i].k == K::RouteTable || r[i].k == K::Registry,
    ensures
        ((r[i].k == K::NRoute || r[i].k == K::ERoute) && in_g(r[i], c)) ==> !erase_graph(r, c, df).contains(r[i]),
        (r[i].k == K::RouteTable && !claimed(r, c, r[i].tbl)) ==> erase_graph(r, c, df).contains(r[i]),
        (r[i].k == K::RouteTable && claimed(r, c, r[i].tbl) && !df.contains(r[i].tbl)) ==> !erase_graph(r, c, df).contains(r[i]),
        ((r[i].k == K::RouteTable || r[i].k == K::Registry) && df.contains(r[i].tbl)) ==> erase_graph(r, c, df).contains(r[i]),
{
    assert(reset_in(r[i], c) == r[i]);
    if keep_graph(r, c, df, r[i]) {
        lemma_in_mapped(r, |x: E| reset_in(x, c), |x: E| keep_graph(r, c, df, x), i);
    } else {
        lemma_not_in_filter(r.map_values(|x: E| reset_in(x, c)), |x: E| keep_graph(r, c, df, x), r[i]);
    }
}

/// EraseAll's variant: the registry row goes inside the transaction, so a failed drop leaves the table without it.
pub proof fn theorem_erase_all_failed_drop(r: Seq<E>, df: Set<int>, i: int)
    requires 0 <= i < r.len(), r[i].k == K::RouteTable, df.contains(r[i].tbl),
    ensures erase_all(r, df).contains(r[i]),
        forall|x: E| x.k == K::Registry ==> !(#[trigger] erase_all(r, df).contains(x)),
{
    assert(reset_all(r[i]) == r[i]);
    lemma_in_mapped(r, |x: E| reset_all(x), |x: E| keep_all(r, df, x), i);
    assert forall|x: E| x.k == K::Registry implies !(#[trigger] erase_all(r, df).contains(x)) by {
        theorem_erase_all_empties(r, df, x);
    }
}

// ============================================================================ concrete witnesses

pub open spec fn n_a() -> Str { seq![97int] }

pub proof fn lemma_valid_one(ch: int)
    requires ch != 48, !ctl(ch),
    ensures valid(seq![ch]),
{
    assert(seq![ch].len() == 1);
    assert(seq![ch][0] == ch);
    assert(seq![ch] != seq![48int]) by { assert(seq![ch][0] != seq![48int][0]); }
}

pub proof fn lemma_g_valid()
    ensures valid(g1()), valid(g2()), g1() != none(), g1() != g2(),
{
    lemma_valid_one(103);
    lemma_valid_one(104);
    assert(g1().len() != none().len());
    assert(g1()[0] != g2()[0]);
}
pub open spec fn n_b() -> Str { seq![98int] }
pub open spec fn g1() -> Str { seq![103int] }
pub open spec fn g2() -> Str { seq![104int] }
pub open spec fn none() -> Str { Seq::<int>::empty() }

pub open spec fn ent(k: K, g: Str, s: Str, o: Str, eid: int, tbl: int) -> E {
    E { k, g: Sp::S(g), s, p: 1, o, eid, tbl, wm: 0 }
}

/// erasure.kept#o01 refuted as built: a single-graph erase drops ^NKG, an unscoped store, with every other graph's
/// interning in it, when the erased graph has an interned node (InvalidateDerived -> GraphIndex.DropNKG).
pub proof fn witness_graph_erase_drops_unscoped_nkg()
    ensures ({
        let r = seq![ent(K::Node, g1(), n_a(), none(), 0, 0), nkg(n_a()), nkg(n_b())];
        &&& at_risk_graph(r, g1())
        &&& !erase_graph(r, g1(), Set::empty()).contains(nkg(n_b()))
        &&& r.contains(nkg(n_b()))
    }),
{
    let r = seq![ent(K::Node, g1(), n_a(), none(), 0, 0), nkg(n_a()), nkg(n_b())];
    assert(r[1] == nkg(n_a()));
    assert(interned(r, n_a()));
    assert(in_g(r[0], g1()));
    assert(at_risk_graph(r, g1()));
    assert(r[2] == nkg(n_b()));
    lemma_not_in_filter(r.map_values(|x: E| reset_in(x, g1())), |x: E| keep_graph(r, g1(), Set::empty(), x), nkg(n_b()));
}

/// search.erasure.indexes#o01 (graph) and erasure.history#o03 refuted as built: after EraseGraph(g) the digest
/// reports g empty while the BM25 index recorded for g still holds g's node.
pub proof fn witness_empty_digest_bm25_survives()
    ensures ({
        let r = seq![ent(K::Node, g1(), n_a(), none(), 0, 0), ent(K::Bm25, g1(), n_a(), none(), 0, 0)];
        let post = erase_graph(r, g1(), Set::empty());
        &&& digest_empty(post, g1())
        &&& post.contains(ent(K::Bm25, g1(), n_a(), none(), 0, 0))
    }),
{
    let r = seq![ent(K::Node, g1(), n_a(), none(), 0, 0), ent(K::Bm25, g1(), n_a(), none(), 0, 0)];
    theorem_graph_erase_digest_empty(r, g1(), Set::empty());
    assert(reset_in(r[1], g1()) == r[1]);
    lemma_in_mapped(r, |x: E| reset_in(x, g1()), |x: E| keep_graph(r, g1(), Set::empty(), x), 1);
}

/// search.erasure.indexes#o03 refuted as built: erasing every graph empties no named index.
pub proof fn witness_erase_all_keeps_named_indexes()
    ensures ({
        let r = seq![ent(K::Bm25, g1(), n_a(), none(), 0, 0), ent(K::Ivf, none(), n_a(), none(), 0, 0),
                     ent(K::Plaid, none(), n_a(), none(), 0, 0), ent(K::VecIdx, none(), n_a(), none(), 0, 0)];
        let post = erase_all(r, Set::empty());
        &&& post.contains(r[0]) &&& post.contains(r[1]) &&& post.contains(r[2]) &&& post.contains(r[3])
    }),
{
    let r = seq![ent(K::Bm25, g1(), n_a(), none(), 0, 0), ent(K::Ivf, none(), n_a(), none(), 0, 0),
                 ent(K::Plaid, none(), n_a(), none(), 0, 0), ent(K::VecIdx, none(), n_a(), none(), 0, 0)];
    assert(reset_all(r[0]) == r[0]); assert(reset_all(r[1]) == r[1]);
    assert(reset_all(r[2]) == r[2]); assert(reset_all(r[3]) == r[3]);
    lemma_in_mapped(r, |x: E| reset_all(x), |x: E| keep_all(r, Set::empty(), x), 0);
    lemma_in_mapped(r, |x: E| reset_all(x), |x: E| keep_all(r, Set::empty(), x), 1);
    lemma_in_mapped(r, |x: E| reset_all(x), |x: E| keep_all(r, Set::empty(), x), 2);
    lemma_in_mapped(r, |x: E| reset_all(x), |x: E| keep_all(r, Set::empty(), x), 3);
}

/// erasure.count#o01 refuted for node erases: an ID erase that removes one node row and its one relationship row
/// returns 1 (node rows only), while the graph erase of the same content returns 2.
pub proof fn witness_id_erase_count_omits_relationships()
    ensures ({
        let r = seq![ent(K::Node, g1(), n_a(), none(), 0, 0), ent(K::Edge, g1(), n_a(), n_b(), 7, 0)];
        &&& count_ids(r, g1(), list_sel(seq![n_a()])) == 1
        &&& count_graph(r, g1()) == 2
        &&& !erase_ids(r, g1(), list_sel(seq![n_a()])).contains(r[1])
    }),
{
    let r = seq![ent(K::Node, g1(), n_a(), none(), 0, 0), ent(K::Edge, g1(), n_a(), n_b(), 7, 0)];
    let d = list_sel(seq![n_a()]);
    assert(seq![n_a()][0] == n_a());
    assert(d(n_a()));
    reveal_with_fuel(Seq::filter, 3);
    assert(r.filter(|e: E| e.k == K::Node && in_g(e, g1()) && d(e.s)) =~= seq![r[0]]);
    assert(r.filter(|e: E| row_of(e, g1())) =~= r);
    assert(incident(r[1], g1(), d));
    lemma_not_in_filter(r, |x: E| keep_ids(r, g1(), d, x), r[1]);
}

/// erasure.count#o02: a graph whose only content is a temporal-only event erases it and returns 0, not an error.
pub proof fn witness_zero_count_with_content_removed()
    ensures ({
        let st = St { rows: seq![ent(K::Temporal, g1(), n_a(), n_b(), 0, 0)], version: 0 };
        let (o, s2) = call(st, Ep::Graph { g: Some(g1()) }, None, Set::empty());
        &&& o == Out::Count(0)
        &&& !s2.rows.contains(st.rows[0])
    }),
{
    let st = St { rows: seq![ent(K::Temporal, g1(), n_a(), n_b(), 0, 0)], version: 0 };
    lemma_g_valid();
    reveal_with_fuel(Seq::filter, 2);
    assert(st.rows.filter(|e: E| row_of(e, g1())) =~= Seq::<E>::empty());
    theorem_graph_erase_removes_scoped(st.rows, g1(), Set::empty(), st.rows[0]);
}

/// erasure.prefix-match#o03 contrast: the prefix erase leaves a temporal-only event of an id with no node row, the
/// explicit-ID erase of the same id removes it (EraseNodeIds sweeps every id named, present or not).
pub proof fn witness_prefix_leaves_event_ids_remove()
    ensures ({
        let r = seq![ent(K::Temporal, g1(), n_a(), n_b(), 0, 0)];
        &&& erase_ids(r, g1(), prefix_sel(r, g1(), n_a())).contains(r[0])
        &&& !erase_ids(r, g1(), list_sel(seq![n_a()])).contains(r[0])
    }),
{
    let r = seq![ent(K::Temporal, g1(), n_a(), n_b(), 0, 0)];
    let dp = prefix_sel(r, g1(), n_a());
    assert(!dp(n_a()));
    assert(!dp(n_b()));
    lemma_in_filter(r, |x: E| keep_ids(r, g1(), dp, x), 0);
    let dl = list_sel(seq![n_a()]);
    assert(seq![n_a()][0] == n_a());
    assert(dl(n_a()));
    lemma_not_in_filter(r, |x: E| keep_ids(r, g1(), dl, x), r[0]);
}

/// erasure.entry-points.single-path#o01 / erasure.live-statements#o01 refuted as built: delete_edge removes the row
/// and its adjacency and leaves the live statement, its tuple lookup, the reification and the edge vector.
pub proof fn witness_delete_edge_leaves_statement()
    ensures ({
        let r = seq![ent(K::Edge, g1(), n_a(), n_b(), 7, 0), ent(K::Stmt, g1(), n_a(), n_b(), 0, 0),
                     ent(K::Reif, none(), none(), none(), 7, 0), ent(K::EEmb, g1(), n_a(), n_b(), 0, 0)];
        let post = delete_edge(r, g1(), (n_a(), 1, n_b()));
        &&& !post.contains(r[0]) &&& post.contains(r[1]) &&& post.contains(r[2]) &&& post.contains(r[3])
        &&& !erase_edges(r, g1(), |x: (Str, int, Str)| x == (n_a(), 1int, n_b())).contains(r[1])
    }),
{
    let r = seq![ent(K::Edge, g1(), n_a(), n_b(), 7, 0), ent(K::Stmt, g1(), n_a(), n_b(), 0, 0),
                 ent(K::Reif, none(), none(), none(), 7, 0), ent(K::EEmb, g1(), n_a(), n_b(), 0, 0)];
    let x = (n_a(), 1int, n_b());
    let f = |e: E| !((e.k == K::Edge || e.k == K::Adj) && in_g(e, g1()) && tri(e) == x);
    lemma_not_in_filter(r, f, r[0]);
    lemma_in_filter(r, f, 1); lemma_in_filter(r, f, 2); lemma_in_filter(r, f, 3);
    let t = |x: (Str, int, Str)| x == (n_a(), 1int, n_b());
    assert(edge_sel(r[0], g1(), t));
    assert(row_for(r, g1(), t, tri(r[1])));
    lemma_not_in_filter(r, |e: E| keep_edges(r, g1(), t, e), r[1]);
}

/// erasure.scope#o02 residue (as built): a named graph's erase removes the reification row of its edge but keeps the
/// reifier node, which reify_edge writes in the default graph with the edge's properties.
pub proof fn witness_named_erase_keeps_reifier_node()
    ensures ({
        let r = seq![ent(K::Edge, g1(), n_a(), n_b(), 7, 0), ent(K::Reif, none(), none(), none(), 7, 0),
                     ent(K::Node, none(), seq![114int], none(), 0, 0), ent(K::Prop, none(), seq![114int], none(), 0, 0)];
        let post = erase_graph(r, g1(), Set::empty());
        &&& !post.contains(r[1]) &&& post.contains(r[2]) &&& post.contains(r[3])
    }),
{
    let r = seq![ent(K::Edge, g1(), n_a(), n_b(), 7, 0), ent(K::Reif, none(), none(), none(), 7, 0),
                 ent(K::Node, none(), seq![114int], none(), 0, 0), ent(K::Prop, none(), seq![114int], none(), 0, 0)];
    lemma_g_valid();
    theorem_graph_erase_removes_reifications_and_fhir_side(r, g1(), Set::empty(), 0, r[1]);
    theorem_graph_erase_frame(r, g1(), Set::empty(), 2);
    theorem_graph_erase_frame(r, g1(), Set::empty(), 3);
}

/// erasure.atomic#o05 (as built): without a caller's transaction the store's list erase commits each chunk; a failure
/// in the second chunk raises and leaves the first chunk erased. Inside a caller's transaction nothing is erased.
pub proof fn witness_list_erase_commits_earlier_chunk()
    ensures ({
        let st = St { rows: seq![ent(K::Node, g1(), n_a(), none(), 0, 0), ent(K::Node, g1(), n_b(), none(), 0, 0)], version: 0 };
        let chunks = seq![seq![n_a()], seq![n_b()]];
        let (o, s2) = list_erase(st, Some(g1()), chunks, 1, 0);
        let (oj, sj) = list_erase_joined(st, Some(g1()), chunks, 1);
        &&& o == Out::Failed &&& !s2.rows.contains(st.rows[0]) &&& s2.rows.contains(st.rows[1])
        &&& oj == Out::Failed &&& sj.rows == st.rows
    }),
{
    let st = St { rows: seq![ent(K::Node, g1(), n_a(), none(), 0, 0), ent(K::Node, g1(), n_b(), none(), 0, 0)], version: 0 };
    let chunks = seq![seq![n_a()], seq![n_b()]];
    lemma_g_valid();
    assert(chunks[0] == seq![n_a()]);
    assert(chunks.drop_first() =~= seq![seq![n_b()]]);
    assert(chunks.drop_first()[0] == seq![n_b()]);
    assert(chunks.drop_first().drop_first() =~= Seq::<Seq<Str>>::empty());
    let d = list_sel(seq![n_a()]);
    assert(seq![n_a()][0] == n_a());
    assert(d(n_a()));
    assert(!d(n_b())) by { if d(n_b()) { let j = choose|j: int| 0 <= j < 1 && seq![n_a()][j] == n_b(); assert(n_a()[0] != n_b()[0]); } }
    let r1 = erase_ids(st.rows, g1(), d);
    lemma_not_in_filter(st.rows, |x: E| keep_ids(st.rows, g1(), d, x), st.rows[0]);
    lemma_in_filter(st.rows, |x: E| keep_ids(st.rows, g1(), d, x), 1);
    reveal_with_fuel(list_erase, 3);
}

/// q-plt-006 (erasure.atomic#o04 scope): on a from_connect engine the graph erase runs on its own connection and
/// survives the caller's rollback; joined, the caller's rollback restores it.
pub proof fn witness_dedicated_erase_survives_caller_rollback()
    ensures ({
        let base = St { rows: seq![ent(K::Node, g1(), n_a(), none(), 0, 0)], version: 0 };
        let w = seq![ent(K::Node, g2(), n_b(), none(), 0, 0)];
        let ep = Ep::Graph { g: Some(g1()) };
        &&& !dedicated_then(base, w, ep, None, Set::empty(), false).1.rows.contains(base.rows[0])
        &&& joined_then(base, w, ep, None, Set::empty(), false).1.rows.contains(base.rows[0])
    }),
{
    let base = St { rows: seq![ent(K::Node, g1(), n_a(), none(), 0, 0)], version: 0 };
    lemma_g_valid();
    theorem_graph_erase_removes_scoped(base.rows, g1(), Set::empty(), base.rows[0]);
    assert(base.rows[0] == base.rows[0]);
}

/// structure.degree.cache.uncommitted bullet 3 (as built): a graph erase also clears the graph's "caching off" mark.
pub proof fn witness_graph_erase_clears_nolock()
    ensures ({
        let r = seq![ent(K::NoLock, g1(), none(), none(), 0, 0)];
        !erase_graph(r, g1(), Set::empty()).contains(r[0])
    }),
{
    let r = seq![ent(K::NoLock, g1(), none(), none(), 0, 0)];
    theorem_graph_erase_removes_scoped(r, g1(), Set::empty(), r[0]);
}

/// erasure.history#o03 reader: GraphStores.Digest(g) after EraseGraph(g) still reports the kept temporal-only setting,
/// so "Digest empty" is not the empty-graph check; the content stores it walks are empty (theorem above).
pub proof fn witness_digest_reports_kept_setting()
    ensures ({
        let r = seq![ent(K::TStruct, g1(), none(), none(), 0, 0), ent(K::Node, g1(), n_a(), none(), 0, 0)];
        let post = erase_graph(r, g1(), Set::empty());
        &&& post.contains(r[0]) &&& digest_kind(r[0].k) &&& !post.contains(r[1])
    }),
{
    let r = seq![ent(K::TStruct, g1(), none(), none(), 0, 0), ent(K::Node, g1(), n_a(), none(), 0, 0)];
    theorem_graph_erase_keeps_settings(r, g1(), Set::empty(), 0);
    theorem_graph_erase_removes_scoped(r, g1(), Set::empty(), r[1]);
}

/// algorithms.cache.erasure#o01 (graph and relationship paths): the graph erase drops every graph's cached algorithm
/// answers (InvalidateDerived kills ^IVG.AlgoCache whole); so does a relationship erase that removed anything.
pub proof fn theorem_erase_clears_algo_cache(r: Seq<E>, c: Str, df: Set<int>, t: spec_fn((Str, int, Str)) -> bool, e: E)
    requires e.k == K::ACache,
    ensures !erase_graph(r, c, df).contains(e),
        removed_any_edge(r, c, t) ==> !erase_edges(r, c, t).contains(e),
        !erase_all(r, df).contains(e),
{
    lemma_not_in_filter(r.map_values(|x: E| reset_in(x, c)), |x: E| keep_graph(r, c, df, x), e);
    if removed_any_edge(r, c, t) { lemma_not_in_filter(r, |x: E| keep_edges(r, c, t, x), e); }
    theorem_erase_all_empties(r, df, e);
}

} // verus!
