//! M-06 located controls. Each block exists only under its feature and is the departing variant's attempt to
//! discharge the mechanism trait: the kept obligations are discharged by the baseline's `keep_*` lemmas, each broken
//! one is asserted on the line marked `LOCATE <feature> <law>` and must fail there (its negation is proved in the
//! baseline by `refute_*`, and the law itself is broken by the run in src/cx06_snapshot.rs).
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m06_snapshot::*;
#[allow(unused_imports)]
use crate::i06_snapshot::*;

verus! {

// CONTROL snapshot_edge_vectors_missing_as_built mech=M-06 check=snapshot-edge-vectors-missing-as-built kind=as-built objects=18/snapshot-archive findings=F-C1804,F-1803,F-1804 violates=M06-L1 refute=i06_snapshot::refute_edge_vectors_missing_l1 cx=cx06_snapshot::cx_edge_vectors_missing_l1
#[cfg(feature = "snapshot_edge_vectors_missing_as_built")]
impl SnapshotObject for EdgeVectorsMissingAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE snapshot_edge_vectors_missing_as_built M06-L1
    }
    proof fn discharge_l2() { keep_edge_vectors_missing_l2(); }
    proof fn discharge_l3() { keep_edge_vectors_missing_l3(); }
}

// CONTROL snapshot_replacing_restore_as_built mech=M-06 check=snapshot-replacing-restore-as-built kind=as-built objects=18/namespace findings=F-1801 violates=M06-L2 refute=i06_snapshot::refute_replacing_restore_l2 cx=cx06_snapshot::cx_replacing_restore_l2
#[cfg(feature = "snapshot_replacing_restore_as_built")]
impl SnapshotObject for ReplacingRestoreAsBuilt {
    proof fn discharge_l1() { keep_replacing_restore_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE snapshot_replacing_restore_as_built M06-L2
    }
    proof fn discharge_l3() { keep_replacing_restore_l3(); }
}

// CONTROL snapshot_merge_aggregates_as_built mech=M-06 check=snapshot-merge-aggregates-as-built kind=as-built objects=18/namespace findings=F-1805 violates=M06-L3 refute=i06_snapshot::refute_merge_aggregates_l3 cx=cx06_snapshot::cx_merge_aggregates_l3
#[cfg(feature = "snapshot_merge_aggregates_as_built")]
impl SnapshotObject for MergeAggregatesAsBuilt {
    proof fn discharge_l1() { keep_merge_aggregates_l1(); }
    proof fn discharge_l2() { keep_merge_aggregates_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE snapshot_merge_aggregates_as_built M06-L3
    }
}

// CONTROL snapshot_control_c1_store_left_out mech=M-06 check=snapshot-control-C1-store-left-out kind=mutant objects=18/snapshot-archive findings= violates=M06-L1 refute=i06_snapshot::refute_ctl_store_left_out_l1 cx=cx06_snapshot::cx_ctl_store_left_out_l1
#[cfg(feature = "snapshot_control_c1_store_left_out")]
impl SnapshotObject for CtlStoreLeftOut {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE snapshot_control_c1_store_left_out M06-L1
    }
    proof fn discharge_l2() { keep_ctl_store_left_out_l2(); }
    proof fn discharge_l3() { keep_ctl_store_left_out_l3(); }
}

// CONTROL snapshot_control_c2_head_laid_over mech=M-06 check=snapshot-control-C2-head-laid-over kind=mutant objects=18/snapshot-archive findings= violates=M06-L2 refute=i06_snapshot::refute_ctl_head_laid_over_l2 cx=cx06_snapshot::cx_ctl_head_laid_over_l2
#[cfg(feature = "snapshot_control_c2_head_laid_over")]
impl SnapshotObject for CtlHeadLaidOver {
    proof fn discharge_l1() { keep_ctl_head_laid_over_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE snapshot_control_c2_head_laid_over M06-L2
    }
    proof fn discharge_l3() { keep_ctl_head_laid_over_l3(); }
}

// CONTROL snapshot_control_c3_aggregates_overwritten mech=M-06 check=snapshot-control-C3-aggregates-overwritten kind=mutant objects=18/snapshot-archive findings= violates=M06-L3 refute=i06_snapshot::refute_ctl_aggregates_overwritten_l3 cx=cx06_snapshot::cx_ctl_aggregates_overwritten_l3
#[cfg(feature = "snapshot_control_c3_aggregates_overwritten")]
impl SnapshotObject for CtlAggregatesOverwritten {
    proof fn discharge_l1() { keep_ctl_aggregates_overwritten_l1(); }
    proof fn discharge_l2() { keep_ctl_aggregates_overwritten_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE snapshot_control_c3_aggregates_overwritten M06-L3
    }
}

} // verus!
