//! M-04 located controls (see src/ctl_ledger.rs for the form): each block exists only under its feature; kept
//! obligations are discharged by the baseline's keep_ lemmas, each broken one fails on its LOCATE line.
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m04_derived::*;
#[allow(unused_imports)]
use crate::i04_derived::*;

verus! {

// CONTROL derived_degree_cache_as_built_f0402 mech=M-04 check=derived-degree-cache-as-built-F0402 kind=as-built objects=04/degree-cache-entry findings=F-0402 violates=M04-L1,M04-L4 refute=i04_derived::refute_degree_cache_f0402_l1,i04_derived::refute_degree_cache_f0402_l4 cx=cx04_derived::cx_degree_cache_f0402_l1,cx04_derived::cx_degree_cache_f0402_l4
#[cfg(feature = "derived_degree_cache_as_built_f0402")]
impl DerivedObject for DegreeCacheF0402 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_degree_cache_as_built_f0402 M04-L1
    }
    proof fn discharge_l2() { keep_degree_cache_f0402_l2(); }
    proof fn discharge_l3() { keep_degree_cache_f0402_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_degree_cache_as_built_f0402 M04-L4
    }
}

// CONTROL derived_degree_cache_as_built_fc0401 mech=M-04 check=derived-degree-cache-as-built-FC0401 kind=as-built objects=04/degree-cache-entry findings=F-C0401 violates=M04-L1,M04-L4 refute=i04_derived::refute_degree_cache_fc0401_l1,i04_derived::refute_degree_cache_fc0401_l4 cx=cx04_derived::cx_degree_cache_fc0401_l1,cx04_derived::cx_degree_cache_fc0401_l4
#[cfg(feature = "derived_degree_cache_as_built_fc0401")]
impl DerivedObject for DegreeCacheFC0401 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_degree_cache_as_built_fc0401 M04-L1
    }
    proof fn discharge_l2() { keep_degree_cache_fc0401_l2(); }
    proof fn discharge_l3() { keep_degree_cache_fc0401_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_degree_cache_as_built_fc0401 M04-L4
    }
}

// CONTROL derived_degree_cache_as_built_f0406 mech=M-04 check=derived-degree-cache-as-built-F0406 kind=as-built objects=04/degree-cache-entry findings=F-0406 violates=M04-L1,M04-L4 refute=i04_derived::refute_degree_cache_f0406_l1,i04_derived::refute_degree_cache_f0406_l4 cx=cx04_derived::cx_degree_cache_f0406_l1,cx04_derived::cx_degree_cache_f0406_l4
#[cfg(feature = "derived_degree_cache_as_built_f0406")]
impl DerivedObject for DegreeCacheF0406 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_degree_cache_as_built_f0406 M04-L1
    }
    proof fn discharge_l2() { keep_degree_cache_f0406_l2(); }
    proof fn discharge_l3() { keep_degree_cache_f0406_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_degree_cache_as_built_f0406 M04-L4
    }
}

// CONTROL derived_result_cache_04_as_built_f0402 mech=M-04 check=derived-result-cache-04-as-built-F0402 kind=as-built objects=04/result-cache-entry findings=F-0402 violates=M04-L1,M04-L4 refute=i04_derived::refute_result_cache_04_f0402_l1,i04_derived::refute_result_cache_04_f0402_l4 cx=cx04_derived::cx_result_cache_04_f0402_l1,cx04_derived::cx_result_cache_04_f0402_l4
#[cfg(feature = "derived_result_cache_04_as_built_f0402")]
impl DerivedObject for ResultCache04F0402 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_result_cache_04_as_built_f0402 M04-L1
    }
    proof fn discharge_l2() { keep_result_cache_04_f0402_l2(); }
    proof fn discharge_l3() { keep_result_cache_04_f0402_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_result_cache_04_as_built_f0402 M04-L4
    }
}

// CONTROL derived_algo_cache_edgeless_as_built_f1004 mech=M-04 check=derived-algo-cache-edgeless-as-built-F1004 kind=as-built objects=10/result-cache-entry findings=F-1004 violates=M04-L1,M04-L2,M04-L4 refute=i04_derived::refute_algo_cache_edgeless_f1004_l1,i04_derived::refute_algo_cache_edgeless_f1004_l2,i04_derived::refute_algo_cache_edgeless_f1004_l4 cx=cx04_derived::cx_algo_cache_edgeless_f1004_l1,cx04_derived::cx_algo_cache_edgeless_f1004_l2,cx04_derived::cx_algo_cache_edgeless_f1004_l4
#[cfg(feature = "derived_algo_cache_edgeless_as_built_f1004")]
impl DerivedObject for AlgoCacheEdgelessF1004 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_algo_cache_edgeless_as_built_f1004 M04-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE derived_algo_cache_edgeless_as_built_f1004 M04-L2
    }
    proof fn discharge_l3() { keep_algo_cache_edgeless_f1004_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_algo_cache_edgeless_as_built_f1004 M04-L4
    }
}

// CONTROL derived_interned_snapshot_as_built_f1005 mech=M-04 check=derived-interned-snapshot-as-built-F1005 kind=as-built objects=10/interned-snapshot findings=F-1005 violates=M04-L1,M04-L2,M04-L4 refute=i04_derived::refute_interned_snapshot_f1005_l1,i04_derived::refute_interned_snapshot_f1005_l2,i04_derived::refute_interned_snapshot_f1005_l4 cx=cx04_derived::cx_interned_snapshot_f1005_l1,cx04_derived::cx_interned_snapshot_f1005_l2,cx04_derived::cx_interned_snapshot_f1005_l4
#[cfg(feature = "derived_interned_snapshot_as_built_f1005")]
impl DerivedObject for InternedSnapshotF1005 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_interned_snapshot_as_built_f1005 M04-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE derived_interned_snapshot_as_built_f1005 M04-L2
    }
    proof fn discharge_l3() { keep_interned_snapshot_f1005_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_interned_snapshot_as_built_f1005 M04-L4
    }
}

// CONTROL derived_interned_snapshot_as_built_fc0801 mech=M-04 check=derived-interned-snapshot-as-built-FC0801 kind=as-built objects=10/interned-snapshot findings=F-C0801 violates=M04-L1,M04-L4 refute=i04_derived::refute_interned_snapshot_fc0801_l1,i04_derived::refute_interned_snapshot_fc0801_l4 cx=cx04_derived::cx_interned_snapshot_fc0801_l1,cx04_derived::cx_interned_snapshot_fc0801_l4
#[cfg(feature = "derived_interned_snapshot_as_built_fc0801")]
impl DerivedObject for InternedSnapshotFC0801 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_interned_snapshot_as_built_fc0801 M04-L1
    }
    proof fn discharge_l2() { keep_interned_snapshot_fc0801_l2(); }
    proof fn discharge_l3() { keep_interned_snapshot_fc0801_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_interned_snapshot_as_built_fc0801 M04-L4
    }
}

// CONTROL derived_bm25_text_change_as_built_f0703 mech=M-04 check=derived-bm25-text-change-as-built-F0703 kind=as-built objects=07/bm25-index,17/index-handle findings=F-0703 violates=M04-L1,M04-L2,M04-L4 refute=i04_derived::refute_bm25_text_change_f0703_l1,i04_derived::refute_bm25_text_change_f0703_l2,i04_derived::refute_bm25_text_change_f0703_l4 cx=cx04_derived::cx_bm25_text_change_f0703_l1,cx04_derived::cx_bm25_text_change_f0703_l2,cx04_derived::cx_bm25_text_change_f0703_l4
#[cfg(feature = "derived_bm25_text_change_as_built_f0703")]
impl DerivedObject for Bm25TextChangeF0703 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_bm25_text_change_as_built_f0703 M04-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE derived_bm25_text_change_as_built_f0703 M04-L2
    }
    proof fn discharge_l3() { keep_bm25_text_change_f0703_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_bm25_text_change_as_built_f0703 M04-L4
    }
}

// CONTROL derived_statement_map_direct_delete_as_built_f0303 mech=M-04 check=derived-statement-map-direct-delete-as-built-F0303 kind=as-built objects=11/edge-statement findings=F-0303 violates=M04-L1,M04-L2,M04-L4 refute=i04_derived::refute_statement_map_direct_delete_f0303_l1,i04_derived::refute_statement_map_direct_delete_f0303_l2,i04_derived::refute_statement_map_direct_delete_f0303_l4 cx=cx04_derived::cx_statement_map_direct_delete_f0303_l1,cx04_derived::cx_statement_map_direct_delete_f0303_l2,cx04_derived::cx_statement_map_direct_delete_f0303_l4
#[cfg(feature = "derived_statement_map_direct_delete_as_built_f0303")]
impl DerivedObject for StatementMapDirectDeleteF0303 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_statement_map_direct_delete_as_built_f0303 M04-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE derived_statement_map_direct_delete_as_built_f0303 M04-L2
    }
    proof fn discharge_l3() { keep_statement_map_direct_delete_f0303_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_statement_map_direct_delete_as_built_f0303 M04-L4
    }
}

// CONTROL derived_bucket_aggregate_update_as_built_f0501 mech=M-04 check=derived-bucket-aggregate-update-as-built-F0501 kind=as-built objects=05/temporal-coordinates findings=F-0501 violates=M04-L1,M04-L4 refute=i04_derived::refute_bucket_aggregate_update_f0501_l1,i04_derived::refute_bucket_aggregate_update_f0501_l4 cx=cx04_derived::cx_bucket_aggregate_update_f0501_l1,cx04_derived::cx_bucket_aggregate_update_f0501_l4
#[cfg(feature = "derived_bucket_aggregate_update_as_built_f0501")]
impl DerivedObject for BucketAggregateUpdateF0501 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_bucket_aggregate_update_as_built_f0501 M04-L1
    }
    proof fn discharge_l2() { keep_bucket_aggregate_update_f0501_l2(); }
    proof fn discharge_l3() { keep_bucket_aggregate_update_f0501_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_bucket_aggregate_update_as_built_f0501 M04-L4
    }
}

// CONTROL derived_engine_mode_cache_as_built_f0208 mech=M-04 check=derived-engine-mode-cache-as-built-F0208 kind=as-built objects=02/graph-mode findings=F-0208 violates=M04-L1,M04-L2,M04-L4 refute=i04_derived::refute_engine_mode_cache_f0208_l1,i04_derived::refute_engine_mode_cache_f0208_l2,i04_derived::refute_engine_mode_cache_f0208_l4 cx=cx04_derived::cx_engine_mode_cache_f0208_l1,cx04_derived::cx_engine_mode_cache_f0208_l2,cx04_derived::cx_engine_mode_cache_f0208_l4
#[cfg(feature = "derived_engine_mode_cache_as_built_f0208")]
impl DerivedObject for EngineModeCacheF0208 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_engine_mode_cache_as_built_f0208 M04-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE derived_engine_mode_cache_as_built_f0208 M04-L2
    }
    proof fn discharge_l3() { keep_engine_mode_cache_f0208_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_engine_mode_cache_as_built_f0208 M04-L4
    }
}

// CONTROL derived_ttl_cache_as_built_f0302 mech=M-04 check=derived-ttl-cache-as-built-F0302 kind=as-built objects=03/ledger-state,06/route findings=F-0302 violates=M04-L1,M04-L2,M04-L4 refute=i04_derived::refute_ttl_cache_f0302_l1,i04_derived::refute_ttl_cache_f0302_l2,i04_derived::refute_ttl_cache_f0302_l4 cx=cx04_derived::cx_ttl_cache_f0302_l1,cx04_derived::cx_ttl_cache_f0302_l2,cx04_derived::cx_ttl_cache_f0302_l4
#[cfg(feature = "derived_ttl_cache_as_built_f0302")]
impl DerivedObject for TtlCacheF0302 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_ttl_cache_as_built_f0302 M04-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE derived_ttl_cache_as_built_f0302 M04-L2
    }
    proof fn discharge_l3() { keep_ttl_cache_f0302_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_ttl_cache_as_built_f0302 M04-L4
    }
}

// CONTROL derived_ttl_cache_as_built_exc05 mech=M-04 check=derived-ttl-cache-as-built-EXC05 kind=exception objects=03/ledger-state,06/route findings= violates=M04-L1,M04-L2,M04-L4 refute=i04_derived::refute_ttl_cache_exc05_l1,i04_derived::refute_ttl_cache_exc05_l2,i04_derived::refute_ttl_cache_exc05_l4 cx=cx04_derived::cx_ttl_cache_exc05_l1,cx04_derived::cx_ttl_cache_exc05_l2,cx04_derived::cx_ttl_cache_exc05_l4
#[cfg(feature = "derived_ttl_cache_as_built_exc05")]
impl DerivedObject for TtlCacheEXC05 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_ttl_cache_as_built_exc05 M04-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE derived_ttl_cache_as_built_exc05 M04-L2
    }
    proof fn discharge_l3() { keep_ttl_cache_exc05_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_ttl_cache_as_built_exc05 M04-L4
    }
}

// CONTROL derived_native_gate_label_index_as_built_f0906 mech=M-04 check=derived-native-gate-label-index-as-built-F0906 kind=as-built objects=09/engine-native-path findings=F-0906 violates=M04-L1,M04-L2,M04-L4 refute=i04_derived::refute_native_gate_label_index_f0906_l1,i04_derived::refute_native_gate_label_index_f0906_l2,i04_derived::refute_native_gate_label_index_f0906_l4 cx=cx04_derived::cx_native_gate_label_index_f0906_l1,cx04_derived::cx_native_gate_label_index_f0906_l2,cx04_derived::cx_native_gate_label_index_f0906_l4
#[cfg(feature = "derived_native_gate_label_index_as_built_f0906")]
impl DerivedObject for NativeGateLabelIndexF0906 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_native_gate_label_index_as_built_f0906 M04-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE derived_native_gate_label_index_as_built_f0906 M04-L2
    }
    proof fn discharge_l3() { keep_native_gate_label_index_f0906_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_native_gate_label_index_as_built_f0906 M04-L4
    }
}

// CONTROL derived_ivf_erase_as_built_f0606 mech=M-04 check=derived-ivf-erase-as-built-F0606 kind=as-built objects=06/ivf-index findings=F-0606 violates=M04-L1,M04-L2,M04-L4 refute=i04_derived::refute_ivf_erase_f0606_l1,i04_derived::refute_ivf_erase_f0606_l2,i04_derived::refute_ivf_erase_f0606_l4 cx=cx04_derived::cx_ivf_erase_f0606_l1,cx04_derived::cx_ivf_erase_f0606_l2,cx04_derived::cx_ivf_erase_f0606_l4
#[cfg(feature = "derived_ivf_erase_as_built_f0606")]
impl DerivedObject for IvfEraseF0606 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_ivf_erase_as_built_f0606 M04-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE derived_ivf_erase_as_built_f0606 M04-L2
    }
    proof fn discharge_l3() { keep_ivf_erase_f0606_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_ivf_erase_as_built_f0606 M04-L4
    }
}

// CONTROL derived_control_c1_unmaintained_path mech=M-04 check=derived-control-C1-unmaintained-path kind=mutant objects=04/degree-cache-entry findings= violates=M04-L1,M04-L2,M04-L4 refute=i04_derived::refute_ctl_unmaintained_path_l1,i04_derived::refute_ctl_unmaintained_path_l2,i04_derived::refute_ctl_unmaintained_path_l4 cx=cx04_derived::cx_ctl_unmaintained_path_l1,cx04_derived::cx_ctl_unmaintained_path_l2,cx04_derived::cx_ctl_unmaintained_path_l4
#[cfg(feature = "derived_control_c1_unmaintained_path")]
impl DerivedObject for CtlUnmaintainedPath {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_control_c1_unmaintained_path M04-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE derived_control_c1_unmaintained_path M04-L2
    }
    proof fn discharge_l3() { keep_ctl_unmaintained_path_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_control_c1_unmaintained_path M04-L4
    }
}

// CONTROL derived_control_c2_token_after_compute mech=M-04 check=derived-control-C2-token-after-compute kind=mutant objects=04/degree-cache-entry findings= violates=M04-L1,M04-L4 refute=i04_derived::refute_ctl_token_after_compute_l1,i04_derived::refute_ctl_token_after_compute_l4 cx=cx04_derived::cx_ctl_token_after_compute_l1,cx04_derived::cx_ctl_token_after_compute_l4
#[cfg(feature = "derived_control_c2_token_after_compute")]
impl DerivedObject for CtlTokenAfterCompute {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_control_c2_token_after_compute M04-L1
    }
    proof fn discharge_l2() { keep_ctl_token_after_compute_l2(); }
    proof fn discharge_l3() { keep_ctl_token_after_compute_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_control_c2_token_after_compute M04-L4
    }
}

// CONTROL derived_control_c3_rebuild_stamp_only mech=M-04 check=derived-control-C3-rebuild-stamp-only kind=mutant objects=04/degree-cache-entry findings= violates=M04-L1,M04-L3,M04-L4 refute=i04_derived::refute_ctl_rebuild_stamp_only_l1,i04_derived::refute_ctl_rebuild_stamp_only_l3,i04_derived::refute_ctl_rebuild_stamp_only_l4 cx=cx04_derived::cx_ctl_rebuild_stamp_only_l1,cx04_derived::cx_ctl_rebuild_stamp_only_l3,cx04_derived::cx_ctl_rebuild_stamp_only_l4
#[cfg(feature = "derived_control_c3_rebuild_stamp_only")]
impl DerivedObject for CtlRebuildStampOnly {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_control_c3_rebuild_stamp_only M04-L1
    }
    proof fn discharge_l2() { keep_ctl_rebuild_stamp_only_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE derived_control_c3_rebuild_stamp_only M04-L3
    }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_control_c3_rebuild_stamp_only M04-L4
    }
}

// CONTROL derived_control_c4_unchecked_gate mech=M-04 check=derived-control-C4-unchecked-gate kind=mutant objects=04/degree-cache-entry findings= violates=M04-L4 refute=i04_derived::refute_ctl_unchecked_gate_l4 cx=cx04_derived::cx_ctl_unchecked_gate_l4
#[cfg(feature = "derived_control_c4_unchecked_gate")]
impl DerivedObject for CtlUncheckedGate {
    proof fn discharge_l1() { keep_ctl_unchecked_gate_l1(); }
    proof fn discharge_l2() { keep_ctl_unchecked_gate_l2(); }
    proof fn discharge_l3() { keep_ctl_unchecked_gate_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_control_c4_unchecked_gate M04-L4
    }
}

// CONTROL derived_control_c5_probe_late mech=M-04 check=derived-control-C5-probe-late kind=mutant objects=04/degree-cache-entry findings= violates=M04-L1,M04-L4 refute=i04_derived::refute_ctl_probe_late_l1,i04_derived::refute_ctl_probe_late_l4 cx=cx04_derived::cx_ctl_probe_late_l1,cx04_derived::cx_ctl_probe_late_l4
#[cfg(feature = "derived_control_c5_probe_late")]
impl DerivedObject for CtlProbeLate {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE derived_control_c5_probe_late M04-L1
    }
    proof fn discharge_l2() { keep_ctl_probe_late_l2(); }
    proof fn discharge_l3() { keep_ctl_probe_late_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE derived_control_c5_probe_late M04-L4
    }
}

} // verus!
