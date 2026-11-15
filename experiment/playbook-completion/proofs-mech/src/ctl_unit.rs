//! M-10 located controls. Each block exists only under its feature and is the departing variant's attempt to
//! discharge the mechanism trait: the kept obligations are discharged by the baseline's `keep_*` lemmas, each broken
//! one is asserted on the line marked `LOCATE <feature> <law>` and must fail there (its negation is proved in the
//! baseline by `refute_*`, and the law itself is broken by the run in src/cx10_unit.rs).
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m10_unit::*;
#[allow(unused_imports)]
use crate::i10_unit::*;

verus! {

// CONTROL unit_per_chunk_commit_as_built mech=M-10 check=unit-per-chunk-commit-as-built kind=as-built objects=03/caller-transaction findings=F-0305 violates=M10-L1 refute=i10_unit::refute_per_chunk_commit_l1 cx=cx10_unit::cx_per_chunk_commit_l1
#[cfg(feature = "unit_per_chunk_commit_as_built")]
impl UnitObject for PerChunkCommitAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE unit_per_chunk_commit_as_built M10-L1
    }
    proof fn discharge_l2() { keep_per_chunk_commit_l2(); }
    proof fn discharge_l3() { keep_per_chunk_commit_l3(); }
}

// CONTROL unit_rollback_all_levels_as_built mech=M-10 check=unit-rollback-all-levels-as-built kind=as-built objects=07/bm25-index,04/adjacency-entry findings=F-C0702,F-0704,F-0409 violates=M10-L2 refute=i10_unit::refute_rollback_all_levels_l2 cx=cx10_unit::cx_rollback_all_levels_l2
#[cfg(feature = "unit_rollback_all_levels_as_built")]
impl UnitObject for RollbackAllLevelsAsBuilt {
    proof fn discharge_l1() { keep_rollback_all_levels_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE unit_rollback_all_levels_as_built M10-L2
    }
    proof fn discharge_l3() { keep_rollback_all_levels_l3(); }
}

// CONTROL unit_per_statement_commit_as_built mech=M-10 check=unit-per-statement-commit-as-built kind=as-built objects=16/bolt-session-with-a-key-set,16/cypher-http-call,15/reifier,16/bolt-explicit-transaction findings=F-1601,F-1610,F-1609,F-C1502 violates=M10-L1 refute=i10_unit::refute_per_statement_commit_l1 cx=cx10_unit::cx_per_statement_commit_l1
#[cfg(feature = "unit_per_statement_commit_as_built")]
impl UnitObject for PerStatementCommitAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE unit_per_statement_commit_as_built M10-L1
    }
    proof fn discharge_l2() { keep_per_statement_commit_l2(); }
    proof fn discharge_l3() { keep_per_statement_commit_l3(); }
}

// CONTROL unit_no_transaction_as_built mech=M-10 check=unit-no-transaction-as-built kind=as-built objects=15/fhir-graph,06/route,05/temporal-coordinates findings=F-1511,F-C1501,F-0615,F-C0501 violates=M10-L1 refute=i10_unit::refute_no_transaction_l1 cx=cx10_unit::cx_no_transaction_l1
#[cfg(feature = "unit_no_transaction_as_built")]
impl UnitObject for NoTransactionAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE unit_no_transaction_as_built M10-L1
    }
    proof fn discharge_l2() { keep_no_transaction_l2(); }
    proof fn discharge_l3() { keep_no_transaction_l3(); }
}

// CONTROL unit_wrong_reply_as_built mech=M-10 check=unit-wrong-reply-as-built kind=as-built objects=08/cypher-call findings=F-0807,F-0804,F-0817 violates=M10-L3 refute=i10_unit::refute_wrong_reply_l3 cx=cx10_unit::cx_wrong_reply_l3
#[cfg(feature = "unit_wrong_reply_as_built")]
impl UnitObject for WrongReplyAsBuilt {
    proof fn discharge_l1() { keep_wrong_reply_l1(); }
    proof fn discharge_l2() { keep_wrong_reply_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE unit_wrong_reply_as_built M10-L3
    }
}

// CONTROL unit_hidden_failure_as_built mech=M-10 check=unit-hidden-failure-as-built kind=as-built objects=03/node-in-one-graph,07/fused-search,15/cypher-anchors,16/fraud-server-call findings=F-0306,F-0307,F-0709,F-1508,F-1615 violates=M10-L3 refute=i10_unit::refute_hidden_failure_l3 cx=cx10_unit::cx_hidden_failure_l3
#[cfg(feature = "unit_hidden_failure_as_built")]
impl UnitObject for HiddenFailureAsBuilt {
    proof fn discharge_l1() { keep_hidden_failure_l1(); }
    proof fn discharge_l2() { keep_hidden_failure_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE unit_hidden_failure_as_built M10-L3
    }
}

// CONTROL unit_control_c1_per_statement mech=M-10 check=unit-control-C1-per-statement kind=mutant objects=11/caller-transaction,17/link findings= violates=M10-L1 refute=i10_unit::refute_ctl_per_statement_l1 cx=cx10_unit::cx_ctl_per_statement_l1
#[cfg(feature = "unit_control_c1_per_statement")]
impl UnitObject for CtlPerStatement {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE unit_control_c1_per_statement M10-L1
    }
    proof fn discharge_l2() { keep_ctl_per_statement_l2(); }
    proof fn discharge_l3() { keep_ctl_per_statement_l3(); }
}

// CONTROL unit_control_c2_rollback_all_levels mech=M-10 check=unit-control-C2-rollback-all-levels kind=mutant objects=11/caller-transaction,17/link findings= violates=M10-L2 refute=i10_unit::refute_ctl_rollback_all_levels_l2 cx=cx10_unit::cx_ctl_rollback_all_levels_l2
#[cfg(feature = "unit_control_c2_rollback_all_levels")]
impl UnitObject for CtlRollbackAllLevels {
    proof fn discharge_l1() { keep_ctl_rollback_all_levels_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE unit_control_c2_rollback_all_levels M10-L2
    }
    proof fn discharge_l3() { keep_ctl_rollback_all_levels_l3(); }
}

// CONTROL unit_control_c3_ok_on_failure mech=M-10 check=unit-control-C3-ok-on-failure kind=mutant objects=11/caller-transaction,17/link findings= violates=M10-L3 refute=i10_unit::refute_ctl_ok_on_failure_l3 cx=cx10_unit::cx_ctl_ok_on_failure_l3
#[cfg(feature = "unit_control_c3_ok_on_failure")]
impl UnitObject for CtlOkOnFailure {
    proof fn discharge_l1() { keep_ctl_ok_on_failure_l1(); }
    proof fn discharge_l2() { keep_ctl_ok_on_failure_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE unit_control_c3_ok_on_failure M10-L3
    }
}

} // verus!
