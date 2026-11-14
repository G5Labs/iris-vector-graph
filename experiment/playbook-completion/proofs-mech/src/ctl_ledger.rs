//! M-01 located controls. Each block exists only under its feature and is the departing variant's attempt to
//! discharge the mechanism trait: the kept obligations are discharged by the baseline's `keep_*` lemmas, each broken
//! one is asserted on the line marked `LOCATE <feature> <law>` and must fail there (its negation is proved in the
//! baseline by `refute_*`, and the law itself is broken by the run in src/cx01_ledger.rs).
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m01_ledger::*;
#[allow(unused_imports)]
use crate::i01_ledger::*;

verus! {

// CONTROL ledger_node_delete_named_only_as_built mech=M-01 check=ledger-node-delete-named-only-as-built kind=as-built objects=11/node-id findings=F-1105 violates=M01-L2 refute=i01_ledger::refute_node_delete_named_only_l2 cx=cx01_ledger::cx_node_delete_named_only_l2
#[cfg(feature = "ledger_node_delete_named_only_as_built")]
impl LedgerObject for NodeDeleteNamedOnlyAsBuilt {
    proof fn discharge_l1() { keep_node_delete_named_only_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE ledger_node_delete_named_only_as_built M01-L2
    }
    proof fn discharge_l3() { keep_node_delete_named_only_l3(); }
    proof fn discharge_l4() { keep_node_delete_named_only_l4(); }
}

// CONTROL ledger_temporal_insert_collision_as_built mech=M-01 check=ledger-temporal-insert-collision-as-built kind=as-built objects=05/temporal-coordinates findings=F-0511 violates=M01-L2 refute=i01_ledger::refute_temporal_insert_collision_l2 cx=cx01_ledger::cx_temporal_insert_collision_l2
#[cfg(feature = "ledger_temporal_insert_collision_as_built")]
impl LedgerObject for TemporalInsertCollisionAsBuilt {
    proof fn discharge_l1() { keep_temporal_insert_collision_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE ledger_temporal_insert_collision_as_built M01-L2
    }
    proof fn discharge_l3() { keep_temporal_insert_collision_l3(); }
    proof fn discharge_l4() { keep_temporal_insert_collision_l4(); }
}

// CONTROL ledger_strict_cached_guard_as_built mech=M-01 check=ledger-strict-cached-guard-as-built kind=as-built objects=03/ledger-state,08/cypher-node,08/cypher-edge,08/cypher-call findings=F-0302,F-0801 violates=M01-L4 refute=i01_ledger::refute_strict_cached_guard_l4 cx=cx01_ledger::cx_strict_cached_guard_l4
#[cfg(feature = "ledger_strict_cached_guard_as_built")]
impl LedgerObject for StrictCachedGuardAsBuilt {
    proof fn discharge_l1() { keep_strict_cached_guard_l1(); }
    proof fn discharge_l2() { keep_strict_cached_guard_l2(); }
    proof fn discharge_l3() { keep_strict_cached_guard_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE ledger_strict_cached_guard_as_built M01-L4
    }
}

// CONTROL ledger_bypass_unchecked_as_built mech=M-01 check=ledger-bypass-unchecked-as-built kind=as-built objects=03/node-in-one-graph,03/edge-in-one-graph findings=F-0301,F-0504,F-1108,F-0503 violates=M01-L4 refute=i01_ledger::refute_bypass_unchecked_l4 cx=cx01_ledger::cx_bypass_unchecked_l4
#[cfg(feature = "ledger_bypass_unchecked_as_built")]
impl LedgerObject for BypassUncheckedAsBuilt {
    proof fn discharge_l1() { keep_bypass_unchecked_l1(); }
    proof fn discharge_l2() { keep_bypass_unchecked_l2(); }
    proof fn discharge_l3() { keep_bypass_unchecked_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE ledger_bypass_unchecked_as_built M01-L4
    }
}

// CONTROL ledger_control_c1_two_step_record mech=M-01 check=ledger-control-C1-two-step-record kind=mutant objects=11/ledger,11/edge-statement,14/ledger-view findings= violates=M01-L2 refute=i01_ledger::refute_ctl_two_step_record_l2 cx=cx01_ledger::cx_ctl_two_step_record_l2
#[cfg(feature = "ledger_control_c1_two_step_record")]
impl LedgerObject for CtlTwoStepRecord {
    proof fn discharge_l1() { keep_ctl_two_step_record_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE ledger_control_c1_two_step_record M01-L2
    }
    proof fn discharge_l3() { keep_ctl_two_step_record_l3(); }
    proof fn discharge_l4() { keep_ctl_two_step_record_l4(); }
}

// CONTROL ledger_control_c2_overwrite_record mech=M-01 check=ledger-control-C2-overwrite-record kind=mutant objects=11/ledger,11/edge-statement,14/ledger-view findings= violates=M01-L1 refute=i01_ledger::refute_ctl_overwrite_record_l1 cx=cx01_ledger::cx_ctl_overwrite_record_l1
#[cfg(feature = "ledger_control_c2_overwrite_record")]
impl LedgerObject for CtlOverwriteRecord {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE ledger_control_c2_overwrite_record M01-L1
    }
    proof fn discharge_l2() { keep_ctl_overwrite_record_l2(); }
    proof fn discharge_l3() { keep_ctl_overwrite_record_l3(); }
    proof fn discharge_l4() { keep_ctl_overwrite_record_l4(); }
}

// CONTROL ledger_control_c3_ignore_head mech=M-01 check=ledger-control-C3-ignore-head kind=mutant objects=11/ledger,11/edge-statement,14/ledger-view findings= violates=M01-L3 refute=i01_ledger::refute_ctl_ignore_head_l3 cx=cx01_ledger::cx_ctl_ignore_head_l3
#[cfg(feature = "ledger_control_c3_ignore_head")]
impl LedgerObject for CtlIgnoreHead {
    proof fn discharge_l1() { keep_ctl_ignore_head_l1(); }
    proof fn discharge_l2() { keep_ctl_ignore_head_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE ledger_control_c3_ignore_head M01-L3
    }
    proof fn discharge_l4() { keep_ctl_ignore_head_l4(); }
}

// CONTROL ledger_control_c4_unguarded_bypass mech=M-01 check=ledger-control-C4-unguarded-bypass kind=mutant objects=11/ledger,11/edge-statement,14/ledger-view findings= violates=M01-L4 refute=i01_ledger::refute_ctl_unguarded_bypass_l4 cx=cx01_ledger::cx_ctl_unguarded_bypass_l4
#[cfg(feature = "ledger_control_c4_unguarded_bypass")]
impl LedgerObject for CtlUnguardedBypass {
    proof fn discharge_l1() { keep_ctl_unguarded_bypass_l1(); }
    proof fn discharge_l2() { keep_ctl_unguarded_bypass_l2(); }
    proof fn discharge_l3() { keep_ctl_unguarded_bypass_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE ledger_control_c4_unguarded_bypass M01-L4
    }
}

} // verus!
