//! M-05 located controls (see src/ctl_ledger.rs for the form).
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m05_removal::*;
#[allow(unused_imports)]
use crate::i05_removal::*;

verus! {

// CONTROL removal_bm25_as_built mech=M-05 check=removal-bm25-as-built,removal-bm25-as-built-M05-L3 kind=as-built objects=07/bm25-index findings=F-0702 violates=M05-L1,M05-L3 refute=i05_removal::refute_bm25_l1,i05_removal::refute_bm25_l3 cx=cx05_removal::cx_bm25_l1,cx05_removal::cx_bm25_l3
#[cfg(feature = "removal_bm25_as_built")]
impl RemovalObject for Bm25AsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE removal_bm25_as_built M05-L1
    }
    proof fn discharge_l2() { keep_bm25_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE removal_bm25_as_built M05-L3
    }
}

// CONTROL removal_vector_indexes_as_built mech=M-05 check=removal-vector-indexes-as-built,removal-vector-indexes-as-built-M05-L3 kind=as-built objects=06/ivf-index findings=F-0606 violates=M05-L1,M05-L3 refute=i05_removal::refute_vector_indexes_l1,i05_removal::refute_vector_indexes_l3 cx=cx05_removal::cx_vector_indexes_l1,cx05_removal::cx_vector_indexes_l3
#[cfg(feature = "removal_vector_indexes_as_built")]
impl RemovalObject for VectorIndexesAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE removal_vector_indexes_as_built M05-L1
    }
    proof fn discharge_l2() { keep_vector_indexes_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE removal_vector_indexes_as_built M05-L3
    }
}

// CONTROL removal_quarantine_as_built mech=M-05 check=removal-quarantine-as-built kind=as-built objects=06/quarantined-row findings=F-C1305 violates=M05-L1,M05-L3 refute=i05_removal::refute_quarantine_l1,i05_removal::refute_quarantine_l3 cx=cx05_removal::cx_quarantine_l1,cx05_removal::cx_quarantine_l3
#[cfg(feature = "removal_quarantine_as_built")]
impl RemovalObject for QuarantineAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE removal_quarantine_as_built M05-L1
    }
    proof fn discharge_l2() { keep_quarantine_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE removal_quarantine_as_built M05-L3
    }
}

// CONTROL removal_snapshot_archives_as_built mech=M-05 check=removal-snapshot-archives-as-built kind=as-built objects=18/snapshot-archive findings=F-C1304 violates=M05-L1,M05-L3 refute=i05_removal::refute_snapshot_archives_l1,i05_removal::refute_snapshot_archives_l3 cx=cx05_removal::cx_snapshot_archives_l1,cx05_removal::cx_snapshot_archives_l3
#[cfg(feature = "removal_snapshot_archives_as_built")]
impl RemovalObject for SnapshotArchivesAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE removal_snapshot_archives_as_built M05-L1
    }
    proof fn discharge_l2() { keep_snapshot_archives_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE removal_snapshot_archives_as_built M05-L3
    }
}

// CONTROL removal_reifier_default_graph_as_built mech=M-05 check=removal-reifier-default-graph-as-built kind=as-built objects=15/reifier findings=F-1502 violates=M05-L1,M05-L3 refute=i05_removal::refute_reifier_default_graph_l1,i05_removal::refute_reifier_default_graph_l3 cx=cx05_removal::cx_reifier_default_graph_l1,cx05_removal::cx_reifier_default_graph_l3
#[cfg(feature = "removal_reifier_default_graph_as_built")]
impl RemovalObject for ReifierDefaultGraphAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE removal_reifier_default_graph_as_built M05-L1
    }
    proof fn discharge_l2() { keep_reifier_default_graph_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE removal_reifier_default_graph_as_built M05-L3
    }
}

// CONTROL removal_temporal_only_prefix_as_built mech=M-05 check=removal-temporal-only-prefix-as-built kind=as-built objects=05/edge-type-in-a-graph findings=F-C1203,F-C1308 violates=M05-L1,M05-L3 refute=i05_removal::refute_temporal_only_prefix_l1,i05_removal::refute_temporal_only_prefix_l3 cx=cx05_removal::cx_temporal_only_prefix_l1,cx05_removal::cx_temporal_only_prefix_l3
#[cfg(feature = "removal_temporal_only_prefix_as_built")]
impl RemovalObject for TemporalOnlyPrefixAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE removal_temporal_only_prefix_as_built M05-L1
    }
    proof fn discharge_l2() { keep_temporal_only_prefix_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE removal_temporal_only_prefix_as_built M05-L3
    }
}

// CONTROL removal_history_text_as_built mech=M-05 check=removal-history-text-as-built kind=as-built objects=13/redaction-target findings=F-C1306,F-CS01,F-C1309 violates=M05-L1,M05-L3 refute=i05_removal::refute_history_text_l1,i05_removal::refute_history_text_l3 cx=cx05_removal::cx_history_text_l1,cx05_removal::cx_history_text_l3
#[cfg(feature = "removal_history_text_as_built")]
impl RemovalObject for HistoryTextAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE removal_history_text_as_built M05-L1
    }
    proof fn discharge_l2() { keep_history_text_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE removal_history_text_as_built M05-L3
    }
}

// CONTROL removal_default_routed_vectors_as_built mech=M-05 check=removal-default-routed-vectors-as-built kind=as-built objects=06/route findings=F-0618 violates=M05-L1,M05-L3 refute=i05_removal::refute_default_routed_vectors_l1,i05_removal::refute_default_routed_vectors_l3 cx=cx05_removal::cx_default_routed_vectors_l1,cx05_removal::cx_default_routed_vectors_l3
#[cfg(feature = "removal_default_routed_vectors_as_built")]
impl RemovalObject for DefaultRoutedVectorsAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE removal_default_routed_vectors_as_built M05-L1
    }
    proof fn discharge_l2() { keep_default_routed_vectors_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE removal_default_routed_vectors_as_built M05-L3
    }
}

// CONTROL removal_temporal_purge_all_graphs_as_built mech=M-05 check=removal-temporal-purge-all-graphs-as-built kind=as-built objects=05/temporal-coordinates findings=F-0507 violates=M05-L2 refute=i05_removal::refute_temporal_purge_all_graphs_l2 cx=cx05_removal::cx_temporal_purge_all_graphs_l2
#[cfg(feature = "removal_temporal_purge_all_graphs_as_built")]
impl RemovalObject for TemporalPurgeAllGraphsAsBuilt {
    proof fn discharge_l1() { keep_temporal_purge_all_graphs_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE removal_temporal_purge_all_graphs_as_built M05-L2
    }
    proof fn discharge_l3() { keep_temporal_purge_all_graphs_l3(); }
}

// CONTROL removal_control_c1_store_dropped mech=M-05 check=removal-control-C1-store-dropped,removal-control-C1b-store-dropped-inventory kind=mutant objects=12/graph-content,12/whole-namespace,12/node-in-a-sweep findings= violates=M05-L1,M05-L3 refute=i05_removal::refute_ctl_store_dropped_l1,i05_removal::refute_ctl_store_dropped_l3 cx=cx05_removal::cx_ctl_store_dropped_l1,cx05_removal::cx_ctl_store_dropped_l3
#[cfg(feature = "removal_control_c1_store_dropped")]
impl RemovalObject for CtlStoreDropped {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE removal_control_c1_store_dropped M05-L1
    }
    proof fn discharge_l2() { keep_ctl_store_dropped_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE removal_control_c1_store_dropped M05-L3
    }
}

// CONTROL removal_control_c2_cross_target mech=M-05 check=removal-control-C2-cross-target kind=mutant objects=12/graph-content,12/whole-namespace,12/node-in-a-sweep findings= violates=M05-L2 refute=i05_removal::refute_ctl_cross_target_l2 cx=cx05_removal::cx_ctl_cross_target_l2
#[cfg(feature = "removal_control_c2_cross_target")]
impl RemovalObject for CtlCrossTarget {
    proof fn discharge_l1() { keep_ctl_cross_target_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE removal_control_c2_cross_target M05-L2
    }
    proof fn discharge_l3() { keep_ctl_cross_target_l3(); }
}

} // verus!
