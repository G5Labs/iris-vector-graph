//! M-03 located controls (see src/ctl_ledger.rs for the form).
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m03_excl::*;
#[allow(unused_imports)]
use crate::i03_excl::*;

verus! {

// CONTROL excl_redaction_marker_as_built mech=M-03 check=excl-redaction-marker-as-built,excl-redaction-marker-as-built-F1302-marker,excl-redaction-marker-as-built-F1302-tomb-live kind=as-built objects=13/redaction-target,13/redaction-run findings=F-1302,F-1303 violates=M03-L3,M03-L4,M03-L5 refute=i03_excl::refute_redaction_marker_l3,i03_excl::refute_redaction_marker_l4,i03_excl::refute_redaction_marker_l5 cx=cx03_excl::cx_redaction_marker_l3,cx03_excl::cx_redaction_marker_l4,cx03_excl::cx_redaction_marker_l5
#[cfg(feature = "excl_redaction_marker_as_built")]
impl ExclObject for RedactionMarkerAsBuilt {
    proof fn discharge_l1() { keep_redaction_marker_l1(); }
    proof fn discharge_l2() { keep_redaction_marker_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE excl_redaction_marker_as_built M03-L3
    }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE excl_redaction_marker_as_built M03-L4
    }
    proof fn discharge_l5() {
        assert(obl_l5::<Self>()); // LOCATE excl_redaction_marker_as_built M03-L5
    }
}

// CONTROL excl_eraser_no_head_lock_as_built mech=M-03 check=excl-eraser-no-head-lock-as-built kind=as-built objects=12/graph-content findings=F-1201,F-1114,F-C1201 violates=M03-L2 refute=i03_excl::refute_eraser_no_head_lock_l2 cx=cx03_excl::cx_eraser_no_head_lock_l2
#[cfg(feature = "excl_eraser_no_head_lock_as_built")]
impl ExclObject for EraserNoHeadLockAsBuilt {
    proof fn discharge_l1() { keep_eraser_no_head_lock_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE excl_eraser_no_head_lock_as_built M03-L2
    }
    proof fn discharge_l3() { keep_eraser_no_head_lock_l3(); }
    proof fn discharge_l4() { keep_eraser_no_head_lock_l4(); }
    proof fn discharge_l5() { keep_eraser_no_head_lock_l5(); }
}

// CONTROL excl_adjacency_writer_lock_as_built mech=M-03 check=excl-adjacency-writer-lock-as-built kind=as-built objects=04/graph-writer-lock findings=F-0407 violates=M03-L2 refute=i03_excl::refute_adjacency_writer_lock_l2 cx=cx03_excl::cx_adjacency_writer_lock_l2
#[cfg(feature = "excl_adjacency_writer_lock_as_built")]
impl ExclObject for AdjacencyWriterLockAsBuilt {
    proof fn discharge_l1() { keep_adjacency_writer_lock_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE excl_adjacency_writer_lock_as_built M03-L2
    }
    proof fn discharge_l3() { keep_adjacency_writer_lock_l3(); }
    proof fn discharge_l4() { keep_adjacency_writer_lock_l4(); }
    proof fn discharge_l5() { keep_adjacency_writer_lock_l5(); }
}

// CONTROL excl_bm25_write_lock_as_built mech=M-03 check=excl-bm25-write-lock-as-built kind=as-built objects=07/bm25-index findings=F-0701 violates=M03-L2 refute=i03_excl::refute_bm25_write_lock_l2 cx=cx03_excl::cx_bm25_write_lock_l2
#[cfg(feature = "excl_bm25_write_lock_as_built")]
impl ExclObject for Bm25WriteLockAsBuilt {
    proof fn discharge_l1() { keep_bm25_write_lock_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE excl_bm25_write_lock_as_built M03-L2
    }
    proof fn discharge_l3() { keep_bm25_write_lock_l3(); }
    proof fn discharge_l4() { keep_bm25_write_lock_l4(); }
    proof fn discharge_l5() { keep_bm25_write_lock_l5(); }
}

// CONTROL excl_plan_build_lock_as_built mech=M-03 check=excl-plan-build-lock-as-built kind=as-built objects=09/compiled-shape findings=F-0905 violates=M03-L2 refute=i03_excl::refute_plan_build_lock_l2 cx=cx03_excl::cx_plan_build_lock_l2
#[cfg(feature = "excl_plan_build_lock_as_built")]
impl ExclObject for PlanBuildLockAsBuilt {
    proof fn discharge_l1() { keep_plan_build_lock_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE excl_plan_build_lock_as_built M03-L2
    }
    proof fn discharge_l3() { keep_plan_build_lock_l3(); }
    proof fn discharge_l4() { keep_plan_build_lock_l4(); }
    proof fn discharge_l5() { keep_plan_build_lock_l5(); }
}

// CONTROL excl_mode_switch_as_built mech=M-03 check=excl-mode-switch-as-built kind=as-built objects=02/graph-mode findings=F-0207 violates=M03-L2 refute=i03_excl::refute_mode_switch_l2 cx=cx03_excl::cx_mode_switch_l2
#[cfg(feature = "excl_mode_switch_as_built")]
impl ExclObject for ModeSwitchAsBuilt {
    proof fn discharge_l1() { keep_mode_switch_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE excl_mode_switch_as_built M03-L2
    }
    proof fn discharge_l3() { keep_mode_switch_l3(); }
    proof fn discharge_l4() { keep_mode_switch_l4(); }
    proof fn discharge_l5() { keep_mode_switch_l5(); }
}

// CONTROL excl_control_c1_lock_admits_two mech=M-03 check=excl-control-C1-lock-admits-two kind=mutant objects=13/redaction-target,13/redaction-run findings= violates=M03-L1 refute=i03_excl::refute_ctl_lock_admits_two_l1 cx=cx03_excl::cx_ctl_lock_admits_two_l1
#[cfg(feature = "excl_control_c1_lock_admits_two")]
impl ExclObject for CtlLockAdmitsTwo {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE excl_control_c1_lock_admits_two M03-L1
    }
    proof fn discharge_l2() { keep_ctl_lock_admits_two_l2(); }
    proof fn discharge_l3() { keep_ctl_lock_admits_two_l3(); }
    proof fn discharge_l4() { keep_ctl_lock_admits_two_l4(); }
    proof fn discharge_l5() { keep_ctl_lock_admits_two_l5(); }
}

// CONTROL excl_control_c2_writer_without_lock mech=M-03 check=excl-control-C2-writer-without-lock kind=mutant objects=13/redaction-target,13/redaction-run findings= violates=M03-L2,M03-L3,M03-L5 refute=i03_excl::refute_ctl_writer_without_lock_l2,i03_excl::refute_ctl_writer_without_lock_l3,i03_excl::refute_ctl_writer_without_lock_l5 cx=cx03_excl::cx_ctl_writer_without_lock_l2,cx03_excl::cx_ctl_writer_without_lock_l3,cx03_excl::cx_ctl_writer_without_lock_l5
#[cfg(feature = "excl_control_c2_writer_without_lock")]
impl ExclObject for CtlWriterWithoutLock {
    proof fn discharge_l1() { keep_ctl_writer_without_lock_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE excl_control_c2_writer_without_lock M03-L2
    }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE excl_control_c2_writer_without_lock M03-L3
    }
    proof fn discharge_l4() { keep_ctl_writer_without_lock_l4(); }
    proof fn discharge_l5() {
        assert(obl_l5::<Self>()); // LOCATE excl_control_c2_writer_without_lock M03-L5
    }
}

// CONTROL excl_control_c3_check_before_lock mech=M-03 check=excl-control-C3-check-before-lock kind=mutant objects=13/redaction-target,13/redaction-run findings= violates=M03-L3,M03-L5 refute=i03_excl::refute_ctl_check_before_lock_l3,i03_excl::refute_ctl_check_before_lock_l5 cx=cx03_excl::cx_ctl_check_before_lock_l3,cx03_excl::cx_ctl_check_before_lock_l5
#[cfg(feature = "excl_control_c3_check_before_lock")]
impl ExclObject for CtlCheckBeforeLock {
    proof fn discharge_l1() { keep_ctl_check_before_lock_l1(); }
    proof fn discharge_l2() { keep_ctl_check_before_lock_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE excl_control_c3_check_before_lock M03-L3
    }
    proof fn discharge_l4() { keep_ctl_check_before_lock_l4(); }
    proof fn discharge_l5() {
        assert(obl_l5::<Self>()); // LOCATE excl_control_c3_check_before_lock M03-L5
    }
}

// CONTROL excl_control_c4_clear_any mech=M-03 check=excl-control-C4-clear-any kind=mutant objects=13/redaction-target,13/redaction-run findings= violates=M03-L4 refute=i03_excl::refute_ctl_clear_any_l4 cx=cx03_excl::cx_ctl_clear_any_l4
#[cfg(feature = "excl_control_c4_clear_any")]
impl ExclObject for CtlClearAny {
    proof fn discharge_l1() { keep_ctl_clear_any_l1(); }
    proof fn discharge_l2() { keep_ctl_clear_any_l2(); }
    proof fn discharge_l3() { keep_ctl_clear_any_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE excl_control_c4_clear_any M03-L4
    }
    proof fn discharge_l5() { keep_ctl_clear_any_l5(); }
}

// CONTROL excl_control_c5_tomb_without_check mech=M-03 check=excl-control-C5-tomb-without-check kind=mutant objects=13/redaction-target,13/redaction-run findings= violates=M03-L3,M03-L5 refute=i03_excl::refute_ctl_tomb_without_check_l3,i03_excl::refute_ctl_tomb_without_check_l5 cx=cx03_excl::cx_ctl_tomb_without_check_l3,cx03_excl::cx_ctl_tomb_without_check_l5
#[cfg(feature = "excl_control_c5_tomb_without_check")]
impl ExclObject for CtlTombWithoutCheck {
    proof fn discharge_l1() { keep_ctl_tomb_without_check_l1(); }
    proof fn discharge_l2() { keep_ctl_tomb_without_check_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE excl_control_c5_tomb_without_check M03-L3
    }
    proof fn discharge_l4() { keep_ctl_tomb_without_check_l4(); }
    proof fn discharge_l5() {
        assert(obl_l5::<Self>()); // LOCATE excl_control_c5_tomb_without_check M03-L5
    }
}

} // verus!
