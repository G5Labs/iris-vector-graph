//! M-05 instances: one type per object variant of mechanisms.json (family `removal`, models/semantics/src/removal.rs).
//! Store k is bit 2^k of the explorer's bitmask; each type's comment names its stores in order.
use vstd::prelude::*;
use crate::exec::*;
use crate::m05_removal::*;

verus! {

/// rows-adjacency-temporal: 12/graph-content (canonical; Eraser.cls:47-260, GraphStores.cls:26-133).
/// Stores: rows, adjacency, temporal, statement maps, history (records).
pub struct RowsAdjacencyTemporal;
impl RemovalPolicy for RowsAdjacencyTemporal { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1, 3, 4], set![2, 0, 4]], inventory: set![0, 1, 2, 3], redact: set![4], receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
impl RemovalObject for RowsAdjacencyTemporal {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}
pub proof fn laws_rows_adjacency_temporal(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA) requires reached::<RemovalM<RowsAdjacencyTemporal>>(s0, ls, t)
    ensures law_l1::<RowsAdjacencyTemporal>(t), law_l3::<RowsAdjacencyTemporal>(t) { theorem_removal::<RowsAdjacencyTemporal>(s0, ls, t, a); }

/// bm25, reviewed: 07/bm25-index. Stores: rows, bm25, history.
pub struct Bm25Reviewed;
impl RemovalPolicy for Bm25Reviewed { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 2], set![1]], inventory: set![0, 1], redact: set![2], receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
impl RemovalObject for Bm25Reviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}
pub proof fn laws_bm25_reviewed(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA) requires reached::<RemovalM<Bm25Reviewed>>(s0, ls, t)
    ensures law_l1::<Bm25Reviewed>(t), law_l3::<Bm25Reviewed>(t) { theorem_removal::<Bm25Reviewed>(s0, ls, t, a); }

/// bm25 as built: 07/bm25-index (F-0702). Stores: rows, bm25, history.
pub struct Bm25AsBuilt;
impl RemovalPolicy for Bm25AsBuilt { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 2], set![1]], inventory: set![0], redact: set![2], receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
pub proof fn refute_bm25_l1() ensures !obl_l1::<Bm25AsBuilt>() {
    assert(Bm25AsBuilt::cfg().paths[1].contains(1nat) && !reached_by_removal::<Bm25AsBuilt>(1nat));
}
pub proof fn keep_bm25_l2() ensures obl_l2::<Bm25AsBuilt>() {}
pub proof fn refute_bm25_l3() ensures !obl_l3::<Bm25AsBuilt>() {
    assert(Bm25AsBuilt::cfg().paths[1].contains(1nat) && !reached_by_removal::<Bm25AsBuilt>(1nat));
}

/// vector-indexes, reviewed: 06/ivf-index. Stores: rows, route, ivf.
pub struct VectorIndexesReviewed;
impl RemovalPolicy for VectorIndexesReviewed { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0], set![1], set![2]], inventory: set![0, 1, 2], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
impl RemovalObject for VectorIndexesReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}
pub proof fn laws_vector_indexes_reviewed(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA) requires reached::<RemovalM<VectorIndexesReviewed>>(s0, ls, t)
    ensures law_l1::<VectorIndexesReviewed>(t), law_l3::<VectorIndexesReviewed>(t) { theorem_removal::<VectorIndexesReviewed>(s0, ls, t, a); }

/// vector-indexes as built: 06/ivf-index (F-0606). Stores: rows, route, ivf.
pub struct VectorIndexesAsBuilt;
impl RemovalPolicy for VectorIndexesAsBuilt { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0], set![1], set![2]], inventory: set![0, 1], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
pub proof fn refute_vector_indexes_l1() ensures !obl_l1::<VectorIndexesAsBuilt>() {
    assert(VectorIndexesAsBuilt::cfg().paths[2].contains(2nat) && !reached_by_removal::<VectorIndexesAsBuilt>(2nat));
}
pub proof fn keep_vector_indexes_l2() ensures obl_l2::<VectorIndexesAsBuilt>() {}
pub proof fn refute_vector_indexes_l3() ensures !obl_l3::<VectorIndexesAsBuilt>() {
    assert(VectorIndexesAsBuilt::cfg().paths[2].contains(2nat) && !reached_by_removal::<VectorIndexesAsBuilt>(2nat));
}

/// quarantine, reviewed: 06/quarantined-row. Stores: rows, quarantine.
pub struct QuarantineReviewed;
impl RemovalPolicy for QuarantineReviewed { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0], set![1]], inventory: set![0, 1], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
impl RemovalObject for QuarantineReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}
pub proof fn laws_quarantine_reviewed(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA) requires reached::<RemovalM<QuarantineReviewed>>(s0, ls, t)
    ensures law_l1::<QuarantineReviewed>(t), law_l3::<QuarantineReviewed>(t) { theorem_removal::<QuarantineReviewed>(s0, ls, t, a); }

/// quarantine as built: 06/quarantined-row (F-C1305). Stores: rows, quarantine.
pub struct QuarantineAsBuilt;
impl RemovalPolicy for QuarantineAsBuilt { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0], set![1]], inventory: set![0], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
pub proof fn refute_quarantine_l1() ensures !obl_l1::<QuarantineAsBuilt>() {
    assert(QuarantineAsBuilt::cfg().paths[1].contains(1nat) && !reached_by_removal::<QuarantineAsBuilt>(1nat));
}
pub proof fn keep_quarantine_l2() ensures obl_l2::<QuarantineAsBuilt>() {}
pub proof fn refute_quarantine_l3() ensures !obl_l3::<QuarantineAsBuilt>() {
    assert(QuarantineAsBuilt::cfg().paths[1].contains(1nat) && !reached_by_removal::<QuarantineAsBuilt>(1nat));
}

/// snapshot-archives, reviewed: 18/snapshot-archive. Stores: rows, history, archive.
pub struct SnapshotArchivesReviewed;
impl RemovalPolicy for SnapshotArchivesReviewed { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1], set![2]], inventory: set![0], redact: set![1], receipt: set![2], cross: Set::<nat>::empty() } } }
impl RemovalObject for SnapshotArchivesReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}
pub proof fn laws_snapshot_archives_reviewed(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA) requires reached::<RemovalM<SnapshotArchivesReviewed>>(s0, ls, t)
    ensures law_l1::<SnapshotArchivesReviewed>(t), law_l3::<SnapshotArchivesReviewed>(t) { theorem_removal::<SnapshotArchivesReviewed>(s0, ls, t, a); }

/// snapshot-archives as built: 18/snapshot-archive (F-C1304). Stores: rows, history, archive.
pub struct SnapshotArchivesAsBuilt;
impl RemovalPolicy for SnapshotArchivesAsBuilt { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1], set![2]], inventory: set![0], redact: set![1], receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
pub proof fn refute_snapshot_archives_l1() ensures !obl_l1::<SnapshotArchivesAsBuilt>() {
    assert(SnapshotArchivesAsBuilt::cfg().paths[1].contains(2nat) && !reached_by_removal::<SnapshotArchivesAsBuilt>(2nat));
}
pub proof fn keep_snapshot_archives_l2() ensures obl_l2::<SnapshotArchivesAsBuilt>() {}
pub proof fn refute_snapshot_archives_l3() ensures !obl_l3::<SnapshotArchivesAsBuilt>() {
    assert(SnapshotArchivesAsBuilt::cfg().paths[1].contains(2nat) && !reached_by_removal::<SnapshotArchivesAsBuilt>(2nat));
}

/// reifier-default-graph, reviewed: 15/reifier. Stores: rows, reifier in default graph.
pub struct ReifierDefaultGraphReviewed;
impl RemovalPolicy for ReifierDefaultGraphReviewed { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1]], inventory: set![0, 1], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
impl RemovalObject for ReifierDefaultGraphReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}
pub proof fn laws_reifier_default_graph_reviewed(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA) requires reached::<RemovalM<ReifierDefaultGraphReviewed>>(s0, ls, t)
    ensures law_l1::<ReifierDefaultGraphReviewed>(t), law_l3::<ReifierDefaultGraphReviewed>(t) { theorem_removal::<ReifierDefaultGraphReviewed>(s0, ls, t, a); }

/// reifier-default-graph as built: 15/reifier (F-1502). Stores: rows, reifier in default graph.
pub struct ReifierDefaultGraphAsBuilt;
impl RemovalPolicy for ReifierDefaultGraphAsBuilt { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1]], inventory: set![0], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
pub proof fn refute_reifier_default_graph_l1() ensures !obl_l1::<ReifierDefaultGraphAsBuilt>() {
    assert(ReifierDefaultGraphAsBuilt::cfg().paths[0].contains(1nat) && !reached_by_removal::<ReifierDefaultGraphAsBuilt>(1nat));
}
pub proof fn keep_reifier_default_graph_l2() ensures obl_l2::<ReifierDefaultGraphAsBuilt>() {}
pub proof fn refute_reifier_default_graph_l3() ensures !obl_l3::<ReifierDefaultGraphAsBuilt>() {
    assert(ReifierDefaultGraphAsBuilt::cfg().paths[0].contains(1nat) && !reached_by_removal::<ReifierDefaultGraphAsBuilt>(1nat));
}

/// temporal-only-prefix, reviewed: 05/edge-type-in-a-graph. Stores: rows, temporal shadow rows, temporal-only edges.
pub struct TemporalOnlyPrefixReviewed;
impl RemovalPolicy for TemporalOnlyPrefixReviewed { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1], set![2]], inventory: set![0, 1, 2], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
impl RemovalObject for TemporalOnlyPrefixReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}
pub proof fn laws_temporal_only_prefix_reviewed(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA) requires reached::<RemovalM<TemporalOnlyPrefixReviewed>>(s0, ls, t)
    ensures law_l1::<TemporalOnlyPrefixReviewed>(t), law_l3::<TemporalOnlyPrefixReviewed>(t) { theorem_removal::<TemporalOnlyPrefixReviewed>(s0, ls, t, a); }

/// temporal-only-prefix as built: 05/edge-type-in-a-graph (F-C1203,F-C1308). Stores: rows, temporal shadow rows, temporal-only edges.
pub struct TemporalOnlyPrefixAsBuilt;
impl RemovalPolicy for TemporalOnlyPrefixAsBuilt { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1], set![2]], inventory: set![0, 1], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
pub proof fn refute_temporal_only_prefix_l1() ensures !obl_l1::<TemporalOnlyPrefixAsBuilt>() {
    assert(TemporalOnlyPrefixAsBuilt::cfg().paths[1].contains(2nat) && !reached_by_removal::<TemporalOnlyPrefixAsBuilt>(2nat));
}
pub proof fn keep_temporal_only_prefix_l2() ensures obl_l2::<TemporalOnlyPrefixAsBuilt>() {}
pub proof fn refute_temporal_only_prefix_l3() ensures !obl_l3::<TemporalOnlyPrefixAsBuilt>() {
    assert(TemporalOnlyPrefixAsBuilt::cfg().paths[1].contains(2nat) && !reached_by_removal::<TemporalOnlyPrefixAsBuilt>(2nat));
}

/// history-text, reviewed: 13/redaction-target. Stores: rows, records, revision text, legacy rows, zero-record text, name digest.
pub struct HistoryTextReviewed;
impl RemovalPolicy for HistoryTextReviewed { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1, 2], set![3], set![4], set![5]], inventory: set![0], redact: set![1, 2, 3, 4, 5], receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
impl RemovalObject for HistoryTextReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}
pub proof fn laws_history_text_reviewed(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA) requires reached::<RemovalM<HistoryTextReviewed>>(s0, ls, t)
    ensures law_l1::<HistoryTextReviewed>(t), law_l3::<HistoryTextReviewed>(t) { theorem_removal::<HistoryTextReviewed>(s0, ls, t, a); }

/// history-text as built: 13/redaction-target (F-C1306,F-CS01,F-C1309). Stores: rows, records, revision text, legacy rows, zero-record text, name digest.
pub struct HistoryTextAsBuilt;
impl RemovalPolicy for HistoryTextAsBuilt { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1, 2], set![3], set![4], set![5]], inventory: set![0], redact: set![1, 2], receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
pub proof fn refute_history_text_l1() ensures !obl_l1::<HistoryTextAsBuilt>() {
    assert(HistoryTextAsBuilt::cfg().paths[1].contains(3nat) && !reached_by_removal::<HistoryTextAsBuilt>(3nat));
}
pub proof fn keep_history_text_l2() ensures obl_l2::<HistoryTextAsBuilt>() {}
pub proof fn refute_history_text_l3() ensures !obl_l3::<HistoryTextAsBuilt>() {
    assert(HistoryTextAsBuilt::cfg().paths[1].contains(3nat) && !reached_by_removal::<HistoryTextAsBuilt>(3nat));
}

/// default-routed-vectors, reviewed: 06/route. Stores: rows, legacy vectors, routed vectors.
pub struct DefaultRoutedVectorsReviewed;
impl RemovalPolicy for DefaultRoutedVectorsReviewed { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 2]], inventory: set![0, 1, 2], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
impl RemovalObject for DefaultRoutedVectorsReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}
pub proof fn laws_default_routed_vectors_reviewed(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA) requires reached::<RemovalM<DefaultRoutedVectorsReviewed>>(s0, ls, t)
    ensures law_l1::<DefaultRoutedVectorsReviewed>(t), law_l3::<DefaultRoutedVectorsReviewed>(t) { theorem_removal::<DefaultRoutedVectorsReviewed>(s0, ls, t, a); }

/// default-routed-vectors as built: 06/route (F-0618). Stores: rows, legacy vectors, routed vectors.
pub struct DefaultRoutedVectorsAsBuilt;
impl RemovalPolicy for DefaultRoutedVectorsAsBuilt { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 2]], inventory: set![0, 1], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
pub proof fn refute_default_routed_vectors_l1() ensures !obl_l1::<DefaultRoutedVectorsAsBuilt>() {
    assert(DefaultRoutedVectorsAsBuilt::cfg().paths[0].contains(2nat) && !reached_by_removal::<DefaultRoutedVectorsAsBuilt>(2nat));
}
pub proof fn keep_default_routed_vectors_l2() ensures obl_l2::<DefaultRoutedVectorsAsBuilt>() {}
pub proof fn refute_default_routed_vectors_l3() ensures !obl_l3::<DefaultRoutedVectorsAsBuilt>() {
    assert(DefaultRoutedVectorsAsBuilt::cfg().paths[0].contains(2nat) && !reached_by_removal::<DefaultRoutedVectorsAsBuilt>(2nat));
}

/// temporal-purge-all-graphs, reviewed: 05/temporal-coordinates. Stores: rows, temporal index.
pub struct TemporalPurgeAllGraphsReviewed;
impl RemovalPolicy for TemporalPurgeAllGraphsReviewed { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1]], inventory: set![0, 1], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
impl RemovalObject for TemporalPurgeAllGraphsReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}
pub proof fn laws_temporal_purge_all_graphs_reviewed(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA) requires reached::<RemovalM<TemporalPurgeAllGraphsReviewed>>(s0, ls, t)
    ensures law_l1::<TemporalPurgeAllGraphsReviewed>(t), law_l3::<TemporalPurgeAllGraphsReviewed>(t) { theorem_removal::<TemporalPurgeAllGraphsReviewed>(s0, ls, t, a); }

/// temporal-purge-all-graphs as built: 05/temporal-coordinates (F-0507). Stores: rows, temporal index.
pub struct TemporalPurgeAllGraphsAsBuilt;
impl RemovalPolicy for TemporalPurgeAllGraphsAsBuilt { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1]], inventory: set![0, 1], redact: Set::<nat>::empty(), receipt: Set::<nat>::empty(), cross: set![1] } } }
pub proof fn keep_temporal_purge_all_graphs_l1() ensures obl_l1::<TemporalPurgeAllGraphsAsBuilt>() {}
pub proof fn refute_temporal_purge_all_graphs_l2() ensures !obl_l2::<TemporalPurgeAllGraphsAsBuilt>() {
    assert(TemporalPurgeAllGraphsAsBuilt::cfg().paths[0].contains(1nat) && TemporalPurgeAllGraphsAsBuilt::cfg().cross.contains(1nat));
}
pub proof fn keep_temporal_purge_all_graphs_l3() ensures obl_l3::<TemporalPurgeAllGraphsAsBuilt>() {}

/// mutant (removal-control-C1-store-dropped,removal-control-C1b-store-dropped-inventory): the erasure inventory drops the adjacency store.
pub struct CtlStoreDropped;
impl RemovalPolicy for CtlStoreDropped { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1, 3, 4], set![2, 0, 4]], inventory: set![0, 2, 3], redact: set![4], receipt: Set::<nat>::empty(), cross: Set::<nat>::empty() } } }
pub proof fn refute_ctl_store_dropped_l1() ensures !obl_l1::<CtlStoreDropped>() {
    assert(CtlStoreDropped::cfg().paths[0].contains(1nat) && !reached_by_removal::<CtlStoreDropped>(1nat));
}
pub proof fn keep_ctl_store_dropped_l2() ensures obl_l2::<CtlStoreDropped>() {}
pub proof fn refute_ctl_store_dropped_l3() ensures !obl_l3::<CtlStoreDropped>() {
    assert(CtlStoreDropped::cfg().paths[0].contains(1nat) && !reached_by_removal::<CtlStoreDropped>(1nat));
}

/// mutant (removal-control-C2-cross-target): erasing one target also removes the other's temporal content.
pub struct CtlCrossTarget;
impl RemovalPolicy for CtlCrossTarget { open spec fn cfg() -> RmCfg { RmCfg { paths: seq![set![0, 1, 3, 4], set![2, 0, 4]], inventory: set![0, 1, 2, 3], redact: set![4], receipt: Set::<nat>::empty(), cross: set![2] } } }
pub proof fn keep_ctl_cross_target_l1() ensures obl_l1::<CtlCrossTarget>() {}
pub proof fn refute_ctl_cross_target_l2() ensures !obl_l2::<CtlCrossTarget>() {
    assert(CtlCrossTarget::cfg().paths[1].contains(2nat) && CtlCrossTarget::cfg().cross.contains(2nat));
}
pub proof fn keep_ctl_cross_target_l3() ensures obl_l3::<CtlCrossTarget>() {}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// removal-sharp-removed-other-kept: target 0 is erased and redacted to nothing while target 1 keeps its content.
pub proof fn sharp_removed_other_kept()
    ensures ({
        let t = run::<RemovalM<RowsAdjacencyTemporal>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Write(1, 0), RmA::Erase(0), RmA::Redact(0)]);
        t is Some && t->0.redacted[0] && t->0.content[0] == Set::<nat>::empty() && t->0.content[1] != Set::<nat>::empty()
    })
{
    reveal_with_fuel(run, 5);
    let s0 = removal_s0();
    assert(RowsAdjacencyTemporal::cfg().paths[0].contains(0nat) && !s0.content[0].contains(0nat));
    let s1 = removal_step::<RowsAdjacencyTemporal>(s0, RmA::Write(0, 0))->0;
    assert(!s1.content[1].contains(0nat));
    let s2 = removal_step::<RowsAdjacencyTemporal>(s1, RmA::Write(1, 0))->0;
    assert(s1.content[0].contains(0nat));
    let s3 = removal_step::<RowsAdjacencyTemporal>(s2, RmA::Erase(0))->0;
    let s4 = removal_step::<RowsAdjacencyTemporal>(s3, RmA::Redact(0))->0;
    assert(s4.content[0] =~= Set::<nat>::empty());
    assert(s4.content[1].contains(0nat));
    assert(run::<RemovalM<RowsAdjacencyTemporal>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Write(1, 0), RmA::Erase(0), RmA::Redact(0)]) == Some(s4));
}

/// removal-sharp-erased-history-kept: after erasure (before redaction) only the history store holds target 0.
pub proof fn sharp_erased_history_kept()
    ensures ({
        let t = run::<RemovalM<RowsAdjacencyTemporal>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Erase(0)]);
        t is Some && t->0.erased[0] && !t->0.redacted[0] && t->0.content[0] == set![4nat]
    })
{
    reveal_with_fuel(run, 3);
    let s0 = removal_s0();
    assert(RowsAdjacencyTemporal::cfg().paths[0].contains(0nat) && !s0.content[0].contains(0nat));
    let s1 = removal_step::<RowsAdjacencyTemporal>(s0, RmA::Write(0, 0))->0;
    assert(s1.content[0].contains(0nat));
    let s2 = removal_step::<RowsAdjacencyTemporal>(s1, RmA::Erase(0))->0;
    assert(s2.content[0] =~= set![4nat]);
    assert(run::<RemovalM<RowsAdjacencyTemporal>>(removal_s0(), seq![RmA::Write(0, 0), RmA::Erase(0)]) == Some(s2));
}

} // verus!
