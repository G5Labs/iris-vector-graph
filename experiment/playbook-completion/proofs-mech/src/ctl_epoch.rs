//! M-13 located controls. Each block exists only under its feature and is the departing variant's attempt to
//! discharge the mechanism trait: its one obligation is asserted on the line marked `LOCATE <feature> <law>` and
//! must fail there (its negation is proved in the baseline by `refute_*`, and the law itself is broken by the run in
//! src/cx13_epoch.rs).
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m13_epoch::*;
#[allow(unused_imports)]
use crate::i13_epoch::*;

verus! {

// CONTROL epoch_check_at_start_as_built mech=M-13 check=epoch-check-at-start-as-built kind=as-built objects=14/ledger-view findings=F-1402 violates=M13-L1 refute=i13_epoch::refute_check_at_start_l1 cx=cx13_epoch::cx_check_at_start_l1
#[cfg(feature = "epoch_check_at_start_as_built")]
impl EpochObject for CheckAtStartAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE epoch_check_at_start_as_built M13-L1
    }
}

// CONTROL epoch_no_check_as_built mech=M-13 check=epoch-no-check-as-built kind=as-built objects=18/snapshot-archive findings=F-C1801 violates=M13-L1 refute=i13_epoch::refute_no_check_l1 cx=cx13_epoch::cx_no_check_l1
#[cfg(feature = "epoch_no_check_as_built")]
impl EpochObject for NoCheckAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE epoch_no_check_as_built M13-L1
    }
}

// CONTROL epoch_control_c1_no_end_check mech=M-13 check=epoch-control-C1-no-end-check kind=mutant objects=14/ledger-view findings= violates=M13-L1 refute=i13_epoch::refute_ctl_no_end_check_l1 cx=cx13_epoch::cx_ctl_no_end_check_l1
#[cfg(feature = "epoch_control_c1_no_end_check")]
impl EpochObject for CtlNoEndCheck {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE epoch_control_c1_no_end_check M13-L1
    }
}

} // verus!
