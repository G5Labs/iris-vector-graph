//! M-07 located controls (see src/ctl_ledger.rs for the form): each block exists only under its feature; kept
//! obligations are discharged by the baseline's keep_ lemmas, each broken one fails on its LOCATE line.
//! The explorer's liveness and progress checks (FC0605-fair-lasso, C1b-lifo-fair-lasso, bounded-redaction-resume,
//! C4-restart-scan) record an empty "violates" list in models/semantics/RESULTS.json; their expectation is
//! Violation(M07-L4), which is the law named on their CONTROL lines.
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m07_queue::*;
#[allow(unused_imports)]
use crate::i07_queue::*;

verus! {

// CONTROL queue_embed_queue_as_built_f0604 mech=M-07 check=queue-embed-queue-as-built-F0604 kind=as-built objects=06/queue-entry findings=F-0604 violates=M07-L1 refute=i07_queue::refute_embed_queue_f0604_l1 cx=cx07_queue::cx_embed_queue_f0604_l1
#[cfg(feature = "queue_embed_queue_as_built_f0604")]
impl QueueEntryObject for EmbedQueueF0604 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE queue_embed_queue_as_built_f0604 M07-L1
    }
    proof fn discharge_l2() { keep_embed_queue_f0604_l2(); }
}

// CONTROL queue_embed_queue_as_built_fc0601 mech=M-07 check=queue-embed-queue-as-built-FC0601 kind=as-built objects=06/queue-entry findings=F-C0601 violates=M07-L1 refute=i07_queue::refute_embed_queue_fc0601_l1 cx=cx07_queue::cx_embed_queue_fc0601_l1
#[cfg(feature = "queue_embed_queue_as_built_fc0601")]
impl QueueEntryObject for EmbedQueueFC0601 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE queue_embed_queue_as_built_fc0601 M07-L1
    }
    proof fn discharge_l2() { keep_embed_queue_fc0601_l2(); }
}

// CONTROL queue_embed_queue_as_built_hd0604 mech=M-07 check=queue-embed-queue-as-built-HD0604 kind=as-built objects=06/queue-entry findings=F-C0670 violates=M07-L1,M07-L2 refute=i07_queue::refute_embed_queue_hd0604_l1,i07_queue::refute_embed_queue_hd0604_l2 cx=cx07_queue::cx_embed_queue_hd0604_l1,cx07_queue::cx_embed_queue_hd0604_l2
#[cfg(feature = "queue_embed_queue_as_built_hd0604")]
impl QueueEntryObject for EmbedQueueHD0604 {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE queue_embed_queue_as_built_hd0604 M07-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE queue_embed_queue_as_built_hd0604 M07-L2
    }
}

// CONTROL queue_control_c2_two_consumers mech=M-07 check=queue-control-C2-two-consumers kind=mutant objects=06/queue-entry findings= violates=M07-L1,M07-L2 refute=i07_queue::refute_ctl_two_consumers_l1,i07_queue::refute_ctl_two_consumers_l2 cx=cx07_queue::cx_ctl_two_consumers_l1,cx07_queue::cx_ctl_two_consumers_l2
#[cfg(feature = "queue_control_c2_two_consumers")]
impl QueueEntryObject for CtlTwoConsumers {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE queue_control_c2_two_consumers M07-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE queue_control_c2_two_consumers M07-L2
    }
}

// CONTROL queue_control_c3_mark_always mech=M-07 check=queue-control-C3-mark-always kind=mutant objects=06/queue-entry findings= violates=M07-L1 refute=i07_queue::refute_ctl_mark_always_l1 cx=cx07_queue::cx_ctl_mark_always_l1
#[cfg(feature = "queue_control_c3_mark_always")]
impl QueueEntryObject for CtlMarkAlways {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE queue_control_c3_mark_always M07-L1
    }
    proof fn discharge_l2() { keep_ctl_mark_always_l2(); }
}

// CONTROL queue_embed_queue_as_built_fc0605_overtaking mech=M-07 check=queue-embed-queue-as-built-FC0605-overtaking,queue-embed-queue-as-built-FC0605-fair-lasso kind=as-built objects=06/queue-entry findings=F-C0605 violates=M07-L3,M07-L4 refute=i07_queue::refute_embed_queue_order_l3,i07_queue::refute_embed_queue_order_l4 cx=cx07_queue::cx_embed_queue_order_l3,cx07_queue::cx_embed_queue_order_l4
#[cfg(feature = "queue_embed_queue_as_built_fc0605_overtaking")]
impl QueueOrderObject for EmbedQueueOrderAsBuilt {
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE queue_embed_queue_as_built_fc0605_overtaking M07-L3
    }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE queue_embed_queue_as_built_fc0605_overtaking M07-L4
    }
}

// CONTROL queue_control_c1_lifo_overtaking mech=M-07 check=queue-control-C1-lifo-overtaking,queue-control-C1b-lifo-fair-lasso kind=mutant objects=06/queue-entry findings= violates=M07-L3,M07-L4 refute=i07_queue::refute_ctl_lifo_l3,i07_queue::refute_ctl_lifo_l4 cx=cx07_queue::cx_ctl_lifo_l3,cx07_queue::cx_ctl_lifo_l4
#[cfg(feature = "queue_control_c1_lifo_overtaking")]
impl QueueOrderObject for CtlLifo {
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE queue_control_c1_lifo_overtaking M07-L3
    }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE queue_control_c1_lifo_overtaking M07-L4
    }
}

// CONTROL queue_bounded_redaction_resume_as_built mech=M-07 check=queue-bounded-redaction-resume-as-built kind=as-built objects=13/redaction-run findings=F-C1303 violates=M07-L4 refute=i07_queue::refute_bounded_redaction_resume_l4 cx=cx07_queue::cx_bounded_redaction_resume_l4
#[cfg(feature = "queue_bounded_redaction_resume_as_built")]
impl ResumeObject for BoundedRedactionResumeAsBuilt {
    proof fn discharge_l4() {
        assert(obl_l4_resume::<Self>()); // LOCATE queue_bounded_redaction_resume_as_built M07-L4
    }
}

// CONTROL queue_control_c4_restart_scan mech=M-07 check=queue-control-C4-restart-scan kind=mutant objects=13/redaction-run findings= violates=M07-L4 refute=i07_queue::refute_ctl_restart_scan_l4 cx=cx07_queue::cx_ctl_restart_scan_l4
#[cfg(feature = "queue_control_c4_restart_scan")]
impl ResumeObject for CtlRestartScan {
    proof fn discharge_l4() {
        assert(obl_l4_resume::<Self>()); // LOCATE queue_control_c4_restart_scan M07-L4
    }
}

} // verus!
