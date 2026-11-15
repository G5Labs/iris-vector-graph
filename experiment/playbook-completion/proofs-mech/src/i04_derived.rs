//! M-04 instances: one type per object variant of mechanisms.json (family `derived`, models/semantics/src/derived.rs).
//! Write paths as in the explorer: NONE (no maintenance, no token), TOKEN (writer lock, token before and after),
//! POST_ONLY (writer lock, token after), SYNC (maintained in the write's own transaction, a functional index).
use vstd::prelude::*;
use crate::exec::*;
use crate::m04_derived::*;

verus! {

/// The reviewed configuration of every object (explorer `reviewed_cfg`): TOKEN writers, probing fills, a clear that
/// invalidates the stamp, a checked gate, a recomputing rebuild.
pub open spec fn reviewed_cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: true, post: true, sync: false, wrong: false, survives: false }], fill: Fill::Probe, clear: Clear::Restamp, gate: Gate::Checked, rebuild: Rebuild::Correct } }

/// adjacency-functional: 04/adjacency-entry, 05/latest-event-index, 09/compiled-shape, 05/triple-row (canonical: a
/// declared functional index, every row writer maintains the entry in its own transaction; AdjIndex.cls:12-23).
pub struct AdjacencyFunctional;
impl DerivedPolicy for AdjacencyFunctional { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: false, pre: false, post: false, sync: true, wrong: false, survives: false }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
impl DerivedObject for AdjacencyFunctional {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_adjacency_functional(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<AdjacencyFunctional>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<AdjacencyFunctional>(s0, ls, t, a); }

/// degree-cache, reviewed: 04/degree-cache-entry.
pub struct DegreeCacheReviewed;
impl DerivedPolicy for DegreeCacheReviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for DegreeCacheReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_degree_cache_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<DegreeCacheReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<DegreeCacheReviewed>(s0, ls, t, a); }

/// result-cache-04, reviewed: 04/result-cache-entry.
pub struct ResultCache04Reviewed;
impl DerivedPolicy for ResultCache04Reviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for ResultCache04Reviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_result_cache_04_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<ResultCache04Reviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<ResultCache04Reviewed>(s0, ls, t, a); }

/// algo-cache-edgeless, reviewed: 10/result-cache-entry.
pub struct AlgoCacheEdgelessReviewed;
impl DerivedPolicy for AlgoCacheEdgelessReviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for AlgoCacheEdgelessReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_algo_cache_edgeless_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<AlgoCacheEdgelessReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<AlgoCacheEdgelessReviewed>(s0, ls, t, a); }

/// interned-snapshot, reviewed: 10/interned-snapshot.
pub struct InternedSnapshotReviewed;
impl DerivedPolicy for InternedSnapshotReviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for InternedSnapshotReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_interned_snapshot_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<InternedSnapshotReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<InternedSnapshotReviewed>(s0, ls, t, a); }

/// bm25-text-change, reviewed: 07/bm25-index, 17/index-handle.
pub struct Bm25TextChangeReviewed;
impl DerivedPolicy for Bm25TextChangeReviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for Bm25TextChangeReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_bm25_text_change_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<Bm25TextChangeReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<Bm25TextChangeReviewed>(s0, ls, t, a); }

/// statement-map-direct-delete, reviewed: 11/edge-statement.
pub struct StatementMapDirectDeleteReviewed;
impl DerivedPolicy for StatementMapDirectDeleteReviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for StatementMapDirectDeleteReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_statement_map_direct_delete_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<StatementMapDirectDeleteReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<StatementMapDirectDeleteReviewed>(s0, ls, t, a); }

/// bucket-aggregate-update, reviewed: 05/temporal-coordinates.
pub struct BucketAggregateUpdateReviewed;
impl DerivedPolicy for BucketAggregateUpdateReviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for BucketAggregateUpdateReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_bucket_aggregate_update_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<BucketAggregateUpdateReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<BucketAggregateUpdateReviewed>(s0, ls, t, a); }

/// engine-mode-cache, reviewed: 02/graph-mode.
pub struct EngineModeCacheReviewed;
impl DerivedPolicy for EngineModeCacheReviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for EngineModeCacheReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_engine_mode_cache_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<EngineModeCacheReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<EngineModeCacheReviewed>(s0, ls, t, a); }

/// ttl-cache, reviewed: 03/ledger-state, 06/route.
pub struct TtlCacheReviewed;
impl DerivedPolicy for TtlCacheReviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for TtlCacheReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_ttl_cache_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<TtlCacheReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<TtlCacheReviewed>(s0, ls, t, a); }

/// native-gate-label-index, reviewed: 09/engine-native-path.
pub struct NativeGateLabelIndexReviewed;
impl DerivedPolicy for NativeGateLabelIndexReviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for NativeGateLabelIndexReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_native_gate_label_index_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<NativeGateLabelIndexReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<NativeGateLabelIndexReviewed>(s0, ls, t, a); }

/// ivf-erase, reviewed: 06/ivf-index.
pub struct IvfEraseReviewed;
impl DerivedPolicy for IvfEraseReviewed { open spec fn cfg() -> DCfg { reviewed_cfg() } }
impl DerivedObject for IvfEraseReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_ivf_erase_reviewed(s0: DS, ls: Seq<DA>, t: DS, a: DA) requires reached::<DerivedM<IvfEraseReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_derived::<IvfEraseReviewed>(s0, ls, t, a); }

// ---------------------------------------------------------------- as-built variants and generic mutants (parameters only)

/// derived-degree-cache-as-built-F0402: as-built 04/degree-cache-entry (F-0402): the writer bumps after its write; a reader fill stores the dirty count with a current stamp (Adjacency.cls:80-160).
pub struct DegreeCacheF0402;
impl DerivedPolicy for DegreeCacheF0402 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: false, post: true, sync: false, wrong: false, survives: false }], fill: Fill::Plain, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_degree_cache_f0402_l1() ensures !obl_l1::<DegreeCacheF0402>() {
}
pub proof fn keep_degree_cache_f0402_l2() ensures obl_l2::<DegreeCacheF0402>() {}
pub proof fn keep_degree_cache_f0402_l3() ensures obl_l3::<DegreeCacheF0402>() {}
pub proof fn refute_degree_cache_f0402_l4() ensures !obl_l4::<DegreeCacheF0402>() {
}

/// derived-degree-cache-as-built-FC0401: as-built 04/degree-cache-entry (F-C0401): the probe passes before the writer starts; the writer is stopped between its write and its bump.
pub struct DegreeCacheFC0401;
impl DerivedPolicy for DegreeCacheFC0401 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: false, post: true, sync: false, wrong: false, survives: false }], fill: Fill::Probe, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_degree_cache_fc0401_l1() ensures !obl_l1::<DegreeCacheFC0401>() {
    assert(!path_probe_safe(DegreeCacheFC0401::cfg().paths[0]));
}
pub proof fn keep_degree_cache_fc0401_l2() ensures obl_l2::<DegreeCacheFC0401>() {}
pub proof fn keep_degree_cache_fc0401_l3() ensures obl_l3::<DegreeCacheFC0401>() {}
pub proof fn refute_degree_cache_fc0401_l4() ensures !obl_l4::<DegreeCacheFC0401>() {
    assert(!path_probe_safe(DegreeCacheFC0401::cfg().paths[0]));
}

/// derived-degree-cache-as-built-F0406: as-built 04/degree-cache-entry (F-0406): clearing the cache keeps the warm stamp; the cleared entry reads as 0 with a current stamp.
pub struct DegreeCacheF0406;
impl DerivedPolicy for DegreeCacheF0406 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: true, post: true, sync: false, wrong: false, survives: false }], fill: Fill::Probe, clear: Clear::KeepStamp, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_degree_cache_f0406_l1() ensures !obl_l1::<DegreeCacheF0406>() {
}
pub proof fn keep_degree_cache_f0406_l2() ensures obl_l2::<DegreeCacheF0406>() {}
pub proof fn keep_degree_cache_f0406_l3() ensures obl_l3::<DegreeCacheF0406>() {}
pub proof fn refute_degree_cache_f0406_l4() ensures !obl_l4::<DegreeCacheF0406>() {
}

/// derived-result-cache-04-as-built-F0402: as-built 04/result-cache-entry (F-0402): the result cache read through the adjacency token stores dirty answers (AlgoCache.cls:1-50).
pub struct ResultCache04F0402;
impl DerivedPolicy for ResultCache04F0402 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: false, post: true, sync: false, wrong: false, survives: false }], fill: Fill::Plain, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_result_cache_04_f0402_l1() ensures !obl_l1::<ResultCache04F0402>() {
}
pub proof fn keep_result_cache_04_f0402_l2() ensures obl_l2::<ResultCache04F0402>() {}
pub proof fn keep_result_cache_04_f0402_l3() ensures obl_l3::<ResultCache04F0402>() {}
pub proof fn refute_result_cache_04_f0402_l4() ensures !obl_l4::<ResultCache04F0402>() {
}

/// derived-algo-cache-edgeless-as-built-F1004: as-built 10/result-cache-entry (F-1004): a node written without an edge moves no token (iris_sql_store.py:921-983, 2231-2275).
pub struct AlgoCacheEdgelessF1004;
impl DerivedPolicy for AlgoCacheEdgelessF1004 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: true, post: true, sync: false, wrong: false, survives: false }, WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false }], fill: Fill::Probe, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_algo_cache_edgeless_f1004_l1() ensures !obl_l1::<AlgoCacheEdgelessF1004>() {
    assert(!path_maintains(AlgoCacheEdgelessF1004::cfg().paths[1]));
}
pub proof fn refute_algo_cache_edgeless_f1004_l2() ensures !obl_l2::<AlgoCacheEdgelessF1004>() {
    assert(!path_signals(AlgoCacheEdgelessF1004::cfg().paths[1]));
}
pub proof fn keep_algo_cache_edgeless_f1004_l3() ensures obl_l3::<AlgoCacheEdgelessF1004>() {}
pub proof fn refute_algo_cache_edgeless_f1004_l4() ensures !obl_l4::<AlgoCacheEdgelessF1004>() {
    assert(!path_maintains(AlgoCacheEdgelessF1004::cfg().paths[1]));
}

/// derived-interned-snapshot-as-built-F1005: as-built 10/interned-snapshot (F-1005): some edge writers leave the interned snapshot with nothing saying it is out of date (TemporalIndex.cls:104-112).
pub struct InternedSnapshotF1005;
impl DerivedPolicy for InternedSnapshotF1005 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: true, post: true, sync: false, wrong: false, survives: false }, WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_interned_snapshot_f1005_l1() ensures !obl_l1::<InternedSnapshotF1005>() {
    assert(!path_maintains(InternedSnapshotF1005::cfg().paths[1]));
}
pub proof fn refute_interned_snapshot_f1005_l2() ensures !obl_l2::<InternedSnapshotF1005>() {
    assert(!path_signals(InternedSnapshotF1005::cfg().paths[1]));
}
pub proof fn keep_interned_snapshot_f1005_l3() ensures obl_l3::<InternedSnapshotF1005>() {}
pub proof fn refute_interned_snapshot_f1005_l4() ensures !obl_l4::<InternedSnapshotF1005>() {
    assert(!path_maintains(InternedSnapshotF1005::cfg().paths[1]));
}

/// derived-interned-snapshot-as-built-FC0801: as-built 10/interned-snapshot (F-C0801): a rolled-back edge write leaves its counters raised ($Increment survives the rollback; Adjacency.cls:111-140).
pub struct InternedSnapshotFC0801;
impl DerivedPolicy for InternedSnapshotFC0801 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: false, pre: false, post: false, sync: true, wrong: false, survives: true }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_interned_snapshot_fc0801_l1() ensures !obl_l1::<InternedSnapshotFC0801>() {
    assert(!path_maintains(InternedSnapshotFC0801::cfg().paths[0]));
}
pub proof fn keep_interned_snapshot_fc0801_l2() ensures obl_l2::<InternedSnapshotFC0801>() {}
pub proof fn keep_interned_snapshot_fc0801_l3() ensures obl_l3::<InternedSnapshotFC0801>() {}
pub proof fn refute_interned_snapshot_fc0801_l4() ensures !obl_l4::<InternedSnapshotFC0801>() {
    assert(!path_maintains(InternedSnapshotFC0801::cfg().paths[0]));
}

/// derived-bm25-text-change-as-built-F0703: as-built 07/bm25-index,17/index-handle (F-0703): a node text change neither reindexes nor marks the BM25 index stale (USER_GUIDE.md:893-894).
pub struct Bm25TextChangeF0703;
impl DerivedPolicy for Bm25TextChangeF0703 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: false, pre: false, post: false, sync: true, wrong: false, survives: false }, WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_bm25_text_change_f0703_l1() ensures !obl_l1::<Bm25TextChangeF0703>() {
    assert(!path_maintains(Bm25TextChangeF0703::cfg().paths[1]));
}
pub proof fn refute_bm25_text_change_f0703_l2() ensures !obl_l2::<Bm25TextChangeF0703>() {
    assert(!path_signals(Bm25TextChangeF0703::cfg().paths[1]));
}
pub proof fn keep_bm25_text_change_f0703_l3() ensures obl_l3::<Bm25TextChangeF0703>() {}
pub proof fn refute_bm25_text_change_f0703_l4() ensures !obl_l4::<Bm25TextChangeF0703>() {
    assert(!path_maintains(Bm25TextChangeF0703::cfg().paths[1]));
}

/// derived-statement-map-direct-delete-as-built-F0303: as-built 11/edge-statement (F-0303): a direct edge delete leaves the ledger's live statement link (nodes_edges.py, direct delete_edge).
pub struct StatementMapDirectDeleteF0303;
impl DerivedPolicy for StatementMapDirectDeleteF0303 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: false, pre: false, post: false, sync: true, wrong: false, survives: false }, WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_statement_map_direct_delete_f0303_l1() ensures !obl_l1::<StatementMapDirectDeleteF0303>() {
    assert(!path_maintains(StatementMapDirectDeleteF0303::cfg().paths[1]));
}
pub proof fn refute_statement_map_direct_delete_f0303_l2() ensures !obl_l2::<StatementMapDirectDeleteF0303>() {
    assert(!path_signals(StatementMapDirectDeleteF0303::cfg().paths[1]));
}
pub proof fn keep_statement_map_direct_delete_f0303_l3() ensures obl_l3::<StatementMapDirectDeleteF0303>() {}
pub proof fn refute_statement_map_direct_delete_f0303_l4() ensures !obl_l4::<StatementMapDirectDeleteF0303>() {
    assert(!path_maintains(StatementMapDirectDeleteF0303::cfg().paths[1]));
}

/// derived-bucket-aggregate-update-as-built-F0501: as-built 05/temporal-coordinates (F-0501): an update-mode write counts its edge again in the temporal bucket aggregate.
pub struct BucketAggregateUpdateF0501;
impl DerivedPolicy for BucketAggregateUpdateF0501 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: false, pre: false, post: false, sync: true, wrong: true, survives: false }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_bucket_aggregate_update_f0501_l1() ensures !obl_l1::<BucketAggregateUpdateF0501>() {
    assert(!path_maintains(BucketAggregateUpdateF0501::cfg().paths[0]));
}
pub proof fn keep_bucket_aggregate_update_f0501_l2() ensures obl_l2::<BucketAggregateUpdateF0501>() {}
pub proof fn keep_bucket_aggregate_update_f0501_l3() ensures obl_l3::<BucketAggregateUpdateF0501>() {}
pub proof fn refute_bucket_aggregate_update_f0501_l4() ensures !obl_l4::<BucketAggregateUpdateF0501>() {
    assert(!path_maintains(BucketAggregateUpdateF0501::cfg().paths[0]));
}

/// derived-engine-mode-cache-as-built-F0208: as-built 02/graph-mode (F-0208): an engine keeps a graph's mode forever: another engine's change is never seen.
pub struct EngineModeCacheF0208;
impl DerivedPolicy for EngineModeCacheF0208 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_engine_mode_cache_f0208_l1() ensures !obl_l1::<EngineModeCacheF0208>() {
    assert(!path_maintains(EngineModeCacheF0208::cfg().paths[0]));
}
pub proof fn refute_engine_mode_cache_f0208_l2() ensures !obl_l2::<EngineModeCacheF0208>() {
    assert(!path_signals(EngineModeCacheF0208::cfg().paths[0]));
}
pub proof fn keep_engine_mode_cache_f0208_l3() ensures obl_l3::<EngineModeCacheF0208>() {}
pub proof fn refute_engine_mode_cache_f0208_l4() ensures !obl_l4::<EngineModeCacheF0208>() {
    assert(!path_maintains(EngineModeCacheF0208::cfg().paths[0]));
}

/// derived-ttl-cache-as-built-F0302: as-built 03/ledger-state (F-0302): the strict-mode guard's 5 s cache has no staleness signal (guard.py:20-59).
pub struct TtlCacheF0302;
impl DerivedPolicy for TtlCacheF0302 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_ttl_cache_f0302_l1() ensures !obl_l1::<TtlCacheF0302>() {
    assert(!path_maintains(TtlCacheF0302::cfg().paths[0]));
}
pub proof fn refute_ttl_cache_f0302_l2() ensures !obl_l2::<TtlCacheF0302>() {
    assert(!path_signals(TtlCacheF0302::cfg().paths[0]));
}
pub proof fn keep_ttl_cache_f0302_l3() ensures obl_l3::<TtlCacheF0302>() {}
pub proof fn refute_ttl_cache_f0302_l4() ensures !obl_l4::<TtlCacheF0302>() {
    assert(!path_maintains(TtlCacheF0302::cfg().paths[0]));
}

/// derived-ttl-cache-as-built-EXC05: exception 06/route (EXC-05): the documented 30 s route memory (VEC-T2.13; exception EXC-05).
pub struct TtlCacheEXC05;
impl DerivedPolicy for TtlCacheEXC05 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_ttl_cache_exc05_l1() ensures !obl_l1::<TtlCacheEXC05>() {
    assert(!path_maintains(TtlCacheEXC05::cfg().paths[0]));
}
pub proof fn refute_ttl_cache_exc05_l2() ensures !obl_l2::<TtlCacheEXC05>() {
    assert(!path_signals(TtlCacheEXC05::cfg().paths[0]));
}
pub proof fn keep_ttl_cache_exc05_l3() ensures obl_l3::<TtlCacheEXC05>() {}
pub proof fn refute_ttl_cache_exc05_l4() ensures !obl_l4::<TtlCacheEXC05>() {
    assert(!path_maintains(TtlCacheEXC05::cfg().paths[0]));
}

/// derived-native-gate-label-index-as-built-F0906: as-built 09/engine-native-path (F-0906): the native gate checks the edge index's declaration but reads the label index unchecked (native_plan.py:528-529).
pub struct NativeGateLabelIndexF0906;
impl DerivedPolicy for NativeGateLabelIndexF0906 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Unchecked, rebuild: Rebuild::Correct } } }
pub proof fn refute_native_gate_label_index_f0906_l1() ensures !obl_l1::<NativeGateLabelIndexF0906>() {
    assert(!path_maintains(NativeGateLabelIndexF0906::cfg().paths[0]));
}
pub proof fn refute_native_gate_label_index_f0906_l2() ensures !obl_l2::<NativeGateLabelIndexF0906>() {
    assert(!path_signals(NativeGateLabelIndexF0906::cfg().paths[0]));
}
pub proof fn keep_native_gate_label_index_f0906_l3() ensures obl_l3::<NativeGateLabelIndexF0906>() {}
pub proof fn refute_native_gate_label_index_f0906_l4() ensures !obl_l4::<NativeGateLabelIndexF0906>() {
}

/// derived-ivf-erase-as-built-F0606: as-built 06/ivf-index (F-0606): the erasure path removes vectors without maintaining the IVF / tree / PLAID indexes.
pub struct IvfEraseF0606;
impl DerivedPolicy for IvfEraseF0606 { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: false, pre: false, post: false, sync: true, wrong: false, survives: false }, WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false }], fill: Fill::Off, clear: Clear::NoClear, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_ivf_erase_f0606_l1() ensures !obl_l1::<IvfEraseF0606>() {
    assert(!path_maintains(IvfEraseF0606::cfg().paths[1]));
}
pub proof fn refute_ivf_erase_f0606_l2() ensures !obl_l2::<IvfEraseF0606>() {
    assert(!path_signals(IvfEraseF0606::cfg().paths[1]));
}
pub proof fn keep_ivf_erase_f0606_l3() ensures obl_l3::<IvfEraseF0606>() {}
pub proof fn refute_ivf_erase_f0606_l4() ensures !obl_l4::<IvfEraseF0606>() {
    assert(!path_maintains(IvfEraseF0606::cfg().paths[1]));
}

/// derived-control-C1-unmaintained-path: mutant: C1: a second write path moves no token.
pub struct CtlUnmaintainedPath;
impl DerivedPolicy for CtlUnmaintainedPath { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: true, post: true, sync: false, wrong: false, survives: false }, WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false }], fill: Fill::Probe, clear: Clear::Restamp, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_ctl_unmaintained_path_l1() ensures !obl_l1::<CtlUnmaintainedPath>() {
    assert(!path_maintains(CtlUnmaintainedPath::cfg().paths[1]));
}
pub proof fn refute_ctl_unmaintained_path_l2() ensures !obl_l2::<CtlUnmaintainedPath>() {
    assert(!path_signals(CtlUnmaintainedPath::cfg().paths[1]));
}
pub proof fn keep_ctl_unmaintained_path_l3() ensures obl_l3::<CtlUnmaintainedPath>() {}
pub proof fn refute_ctl_unmaintained_path_l4() ensures !obl_l4::<CtlUnmaintainedPath>() {
    assert(!path_maintains(CtlUnmaintainedPath::cfg().paths[1]));
}

/// derived-control-C2-token-after-compute: mutant: C2: the reader reads the token after computing.
pub struct CtlTokenAfterCompute;
impl DerivedPolicy for CtlTokenAfterCompute { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: true, post: true, sync: false, wrong: false, survives: false }], fill: Fill::TokenAfter, clear: Clear::Restamp, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_ctl_token_after_compute_l1() ensures !obl_l1::<CtlTokenAfterCompute>() {
}
pub proof fn keep_ctl_token_after_compute_l2() ensures obl_l2::<CtlTokenAfterCompute>() {}
pub proof fn keep_ctl_token_after_compute_l3() ensures obl_l3::<CtlTokenAfterCompute>() {}
pub proof fn refute_ctl_token_after_compute_l4() ensures !obl_l4::<CtlTokenAfterCompute>() {
}

/// derived-control-C3-rebuild-stamp-only: mutant: C3: a rebuild restamps without recomputing.
pub struct CtlRebuildStampOnly;
impl DerivedPolicy for CtlRebuildStampOnly { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: true, post: true, sync: false, wrong: false, survives: false }], fill: Fill::Probe, clear: Clear::Restamp, gate: Gate::Checked, rebuild: Rebuild::StampOnly } } }
pub proof fn refute_ctl_rebuild_stamp_only_l1() ensures !obl_l1::<CtlRebuildStampOnly>() {
}
pub proof fn keep_ctl_rebuild_stamp_only_l2() ensures obl_l2::<CtlRebuildStampOnly>() {}
pub proof fn refute_ctl_rebuild_stamp_only_l3() ensures !obl_l3::<CtlRebuildStampOnly>() {
}
pub proof fn refute_ctl_rebuild_stamp_only_l4() ensures !obl_l4::<CtlRebuildStampOnly>() {
}

/// derived-control-C4-unchecked-gate: mutant: C4: the gate reads the derived value without checking the stamp.
pub struct CtlUncheckedGate;
impl DerivedPolicy for CtlUncheckedGate { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: true, post: true, sync: false, wrong: false, survives: false }], fill: Fill::Probe, clear: Clear::Restamp, gate: Gate::Unchecked, rebuild: Rebuild::Correct } } }
pub proof fn keep_ctl_unchecked_gate_l1() ensures obl_l1::<CtlUncheckedGate>() {}
pub proof fn keep_ctl_unchecked_gate_l2() ensures obl_l2::<CtlUncheckedGate>() {}
pub proof fn keep_ctl_unchecked_gate_l3() ensures obl_l3::<CtlUncheckedGate>() {}
pub proof fn refute_ctl_unchecked_gate_l4() ensures !obl_l4::<CtlUncheckedGate>() {
}

/// derived-control-C5-probe-late: mutant: C5: the reader probes the writer lock after computing.
pub struct CtlProbeLate;
impl DerivedPolicy for CtlProbeLate { open spec fn cfg() -> DCfg { DCfg { paths: seq![WPath { lock: true, pre: true, post: true, sync: false, wrong: false, survives: false }], fill: Fill::ProbeLate, clear: Clear::Restamp, gate: Gate::Checked, rebuild: Rebuild::Correct } } }
pub proof fn refute_ctl_probe_late_l1() ensures !obl_l1::<CtlProbeLate>() {
}
pub proof fn keep_ctl_probe_late_l2() ensures obl_l2::<CtlProbeLate>() {}
pub proof fn keep_ctl_probe_late_l3() ensures obl_l3::<CtlProbeLate>() {}
pub proof fn refute_ctl_probe_late_l4() ensures !obl_l4::<CtlProbeLate>() {
}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// derived-sharp-stale: a committed TOKEN write leaves the entry stale (stamp behind the token) with no writer open.
pub proof fn sharp_stale()
    ensures ({
        let t = run::<DerivedM<DegreeCacheReviewed>>(derived_s0(), seq![DA::Begin(0), DA::PreBump, DA::Write(2), DA::PostBump, DA::Commit]);
        t is Some && t->0.w is Idle && t->0.stamp != Some(t->0.token)
    })
{
    reveal_with_fuel(run, 6);
}

/// derived-sharp-fill-current: after a committed write, a probing fill makes the entry current with the new value.
pub proof fn sharp_fill_current()
    ensures ({
        let t = run::<DerivedM<DegreeCacheReviewed>>(derived_s0(), seq![DA::Begin(0), DA::PreBump, DA::Write(2), DA::PostBump, DA::Commit,
            DA::RToken, DA::RProbe, DA::RCompute, DA::RStore]);
        t is Some && t->0.stamp == Some(t->0.token) && t->0.der == Some(t->0.src) && t->0.src != 1
    })
{
    reveal_with_fuel(run, 10);
}

/// derived-sharp-rebuilt: after a committed write, a rebuild makes the entry current.
pub proof fn sharp_rebuilt()
    ensures ({
        let t = run::<DerivedM<DegreeCacheReviewed>>(derived_s0(), seq![DA::Begin(0), DA::PreBump, DA::Write(2), DA::PostBump, DA::Commit, DA::Rebuild]);
        t is Some && t->0.src != 1 && t->0.stamp == Some(t->0.token)
    })
{
    reveal_with_fuel(run, 7);
}

} // verus!
