//! M-02 located controls (see src/ctl_ledger.rs for the form): each block exists only under its feature; kept
//! obligations are discharged by the baseline's keep_ lemmas, each broken one fails on its LOCATE line.
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m02_retry::*;
#[allow(unused_imports)]
use crate::i02_retry::*;

verus! {

// CONTROL retry_ledger_key_as_built mech=M-02 check=retry-ledger-key-as-built kind=as-built objects=11/retry-key findings=F-1101,F-1306 violates=M02-L1,M02-L2 refute=i02_retry::refute_ledger_key_l1,i02_retry::refute_ledger_key_l2 cx=cx02_retry::cx_ledger_key_l1,cx02_retry::cx_ledger_key_l2
#[cfg(feature = "retry_ledger_key_as_built")]
impl RetryObject for LedgerKeyAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE retry_ledger_key_as_built M02-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE retry_ledger_key_as_built M02-L2
    }
    proof fn discharge_l3() { keep_ledger_key_l3(); }
    proof fn discharge_l4() { keep_ledger_key_l4(); }
}

// CONTROL retry_zero_record_revision_as_built mech=M-02 check=retry-zero-record-revision-as-built kind=as-built objects=13/redaction-target findings=F-CS01 violates=M02-L4 refute=i02_retry::refute_zero_record_revision_l4 cx=cx02_retry::cx_zero_record_revision_l4
#[cfg(feature = "retry_zero_record_revision_as_built")]
impl RetryObject for ZeroRecordRevisionAsBuilt {
    proof fn discharge_l1() { keep_zero_record_revision_l1(); }
    proof fn discharge_l2() { keep_zero_record_revision_l2(); }
    proof fn discharge_l3() { keep_zero_record_revision_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE retry_zero_record_revision_as_built M02-L4
    }
}

// CONTROL retry_client_resend_as_built mech=M-02 check=retry-client-resend-as-built kind=as-built objects=17/client-request findings=F-C1703 violates=M02-L1 refute=i02_retry::refute_client_resend_l1 cx=cx02_retry::cx_client_resend_l1
#[cfg(feature = "retry_client_resend_as_built")]
impl RetryObject for ClientResendAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE retry_client_resend_as_built M02-L1
    }
    proof fn discharge_l2() { keep_client_resend_l2(); }
    proof fn discharge_l3() { keep_client_resend_l3(); }
    proof fn discharge_l4() { keep_client_resend_l4(); }
}

// CONTROL retry_server_rerun_as_built mech=M-02 check=retry-server-rerun-as-built kind=as-built objects=16/cypher-http-call findings=F-C1604 violates=M02-L1 refute=i02_retry::refute_server_rerun_l1 cx=cx02_retry::cx_server_rerun_l1
#[cfg(feature = "retry_server_rerun_as_built")]
impl RetryObject for ServerRerunAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE retry_server_rerun_as_built M02-L1
    }
    proof fn discharge_l2() { keep_server_rerun_l2(); }
    proof fn discharge_l3() { keep_server_rerun_l3(); }
    proof fn discharge_l4() { keep_server_rerun_l4(); }
}

// CONTROL retry_control_c1_bind_after_effect mech=M-02 check=retry-control-C1-bind-after-effect kind=mutant objects=11/retry-key findings= violates=M02-L1 refute=i02_retry::refute_ctl_bind_after_effect_l1 cx=cx02_retry::cx_ctl_bind_after_effect_l1
#[cfg(feature = "retry_control_c1_bind_after_effect")]
impl RetryObject for CtlBindAfterEffect {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE retry_control_c1_bind_after_effect M02-L1
    }
    proof fn discharge_l2() { keep_ctl_bind_after_effect_l2(); }
    proof fn discharge_l3() { keep_ctl_bind_after_effect_l3(); }
    proof fn discharge_l4() { keep_ctl_bind_after_effect_l4(); }
}

// CONTROL retry_control_c2_post_on_replay mech=M-02 check=retry-control-C2-post-on-replay kind=mutant objects=11/retry-key findings= violates=M02-L1,M02-L2 refute=i02_retry::refute_ctl_post_on_replay_l1,i02_retry::refute_ctl_post_on_replay_l2 cx=cx02_retry::cx_ctl_post_on_replay_l1,cx02_retry::cx_ctl_post_on_replay_l2
#[cfg(feature = "retry_control_c2_post_on_replay")]
impl RetryObject for CtlPostOnReplay {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE retry_control_c2_post_on_replay M02-L1
    }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE retry_control_c2_post_on_replay M02-L2
    }
    proof fn discharge_l3() { keep_ctl_post_on_replay_l3(); }
    proof fn discharge_l4() { keep_ctl_post_on_replay_l4(); }
}

// CONTROL retry_control_c3_apply_conflict mech=M-02 check=retry-control-C3-apply-conflict kind=mutant objects=11/retry-key findings= violates=M02-L1,M02-L3 refute=i02_retry::refute_ctl_apply_conflict_l1,i02_retry::refute_ctl_apply_conflict_l3 cx=cx02_retry::cx_ctl_apply_conflict_l1,cx02_retry::cx_ctl_apply_conflict_l3
#[cfg(feature = "retry_control_c3_apply_conflict")]
impl RetryObject for CtlApplyConflict {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE retry_control_c3_apply_conflict M02-L1
    }
    proof fn discharge_l2() { keep_ctl_apply_conflict_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE retry_control_c3_apply_conflict M02-L3
    }
    proof fn discharge_l4() { keep_ctl_apply_conflict_l4(); }
}

// CONTROL retry_control_c4_redaction_keeps_binding mech=M-02 check=retry-control-C4-redaction-keeps-binding kind=mutant objects=11/retry-key findings= violates=M02-L4 refute=i02_retry::refute_ctl_redaction_keeps_binding_l4 cx=cx02_retry::cx_ctl_redaction_keeps_binding_l4
#[cfg(feature = "retry_control_c4_redaction_keeps_binding")]
impl RetryObject for CtlRedactionKeepsBinding {
    proof fn discharge_l1() { keep_ctl_redaction_keeps_binding_l1(); }
    proof fn discharge_l2() { keep_ctl_redaction_keeps_binding_l2(); }
    proof fn discharge_l3() { keep_ctl_redaction_keeps_binding_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE retry_control_c4_redaction_keeps_binding M02-L4
    }
}

} // verus!
