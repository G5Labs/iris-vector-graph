//! M-08 located controls. Each block exists only under its feature and is the departing variant's attempt to
//! discharge the mechanism trait: the kept obligations are discharged by the baseline's `keep_*` lemmas, the broken
//! one is asserted on the line marked `LOCATE <feature> <law>` and must fail there (its negation is proved in the
//! baseline by `refute_*`, and the law itself is broken by the run in src/cx08_install.rs). The generic mutants
//! (install-control-C1..C4) are their own instance types and controls, although their parameters equal the as-built
//! variants'.
#[allow(unused_imports)]
use vstd::prelude::*;
#[allow(unused_imports)]
use crate::m08_install::*;
#[allow(unused_imports)]
use crate::i08_install::*;

verus! {

// CONTROL install_first_use_no_record_as_built mech=M-08 check=install-first-use-no-record-as-built kind=as-built objects=01/namespace findings=F-0103 violates=M08-L1 refute=i08_install::refute_first_use_no_record_l1 cx=cx08_install::cx_first_use_no_record_l1
#[cfg(feature = "install_first_use_no_record_as_built")]
impl InstallObject for FirstUseNoRecordAsBuilt {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE install_first_use_no_record_as_built M08-L1
    }
    proof fn discharge_l2() { keep_first_use_no_record_l2(); }
    proof fn discharge_l3() { keep_first_use_no_record_l3(); }
    proof fn discharge_l4() { keep_first_use_no_record_l4(); }
}

// CONTROL install_unqualified_drop_as_built mech=M-08 check=install-unqualified-drop-as-built kind=as-built objects=01/setup-routine findings=F-0107 violates=M08-L3 refute=i08_install::refute_unqualified_drop_l3 cx=cx08_install::cx_unqualified_drop_l3
#[cfg(feature = "install_unqualified_drop_as_built")]
impl InstallObject for UnqualifiedDropAsBuilt {
    proof fn discharge_l1() { keep_unqualified_drop_l1(); }
    proof fn discharge_l2() { keep_unqualified_drop_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE install_unqualified_drop_as_built M08-L3
    }
    proof fn discharge_l4() { keep_unqualified_drop_l4(); }
}

// CONTROL install_unchecked_setting_as_built mech=M-08 check=install-unchecked-setting-as-built kind=as-built objects=09/process-mode,15/rdf-extra findings=F-0903,F-1506 violates=M08-L4 refute=i08_install::refute_unchecked_setting_l4 cx=cx08_install::cx_unchecked_setting_l4
#[cfg(feature = "install_unchecked_setting_as_built")]
impl InstallObject for UncheckedSettingAsBuilt {
    proof fn discharge_l1() { keep_unchecked_setting_l1(); }
    proof fn discharge_l2() { keep_unchecked_setting_l2(); }
    proof fn discharge_l3() { keep_unchecked_setting_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE install_unchecked_setting_as_built M08-L4
    }
}

// CONTROL install_concurrent_first_enable_as_built mech=M-08 check=install-concurrent-first-enable-as-built kind=as-built objects=11/ledger findings=F-1104 violates=M08-L2 refute=i08_install::refute_concurrent_first_enable_l2 cx=cx08_install::cx_concurrent_first_enable_l2
#[cfg(feature = "install_concurrent_first_enable_as_built")]
impl InstallObject for ConcurrentFirstEnableAsBuilt {
    proof fn discharge_l1() { keep_concurrent_first_enable_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE install_concurrent_first_enable_as_built M08-L2
    }
    proof fn discharge_l3() { keep_concurrent_first_enable_l3(); }
    proof fn discharge_l4() { keep_concurrent_first_enable_l4(); }
}

// CONTROL install_control_c1_first_use_accepts_any mech=M-08 check=install-control-C1-first-use-accepts-any kind=mutant objects=01/class-set,01/legacy-object,16/rest-web-app-path,16/mcp-tool-set,17/namespace,03/ledger-state,15/prefix-registry,15/ivg-fhir-cli findings= violates=M08-L1 refute=i08_install::refute_ctl_first_use_accepts_any_l1 cx=cx08_install::cx_ctl_first_use_accepts_any_l1
#[cfg(feature = "install_control_c1_first_use_accepts_any")]
impl InstallObject for CtlFirstUseAcceptsAny {
    proof fn discharge_l1() {
        assert(obl_l1::<Self>()); // LOCATE install_control_c1_first_use_accepts_any M08-L1
    }
    proof fn discharge_l2() { keep_ctl_first_use_accepts_any_l2(); }
    proof fn discharge_l3() { keep_ctl_first_use_accepts_any_l3(); }
    proof fn discharge_l4() { keep_ctl_first_use_accepts_any_l4(); }
}

// CONTROL install_control_c2_unqualified_drop mech=M-08 check=install-control-C2-unqualified-drop kind=mutant objects=01/class-set,01/legacy-object,16/rest-web-app-path,16/mcp-tool-set,17/namespace,03/ledger-state,15/prefix-registry,15/ivg-fhir-cli findings= violates=M08-L3 refute=i08_install::refute_ctl_unqualified_drop_l3 cx=cx08_install::cx_ctl_unqualified_drop_l3
#[cfg(feature = "install_control_c2_unqualified_drop")]
impl InstallObject for CtlUnqualifiedDrop {
    proof fn discharge_l1() { keep_ctl_unqualified_drop_l1(); }
    proof fn discharge_l2() { keep_ctl_unqualified_drop_l2(); }
    proof fn discharge_l3() {
        assert(obl_l3::<Self>()); // LOCATE install_control_c2_unqualified_drop M08-L3
    }
    proof fn discharge_l4() { keep_ctl_unqualified_drop_l4(); }
}

// CONTROL install_control_c3_setting_unchecked mech=M-08 check=install-control-C3-setting-unchecked kind=mutant objects=01/class-set,01/legacy-object,16/rest-web-app-path,16/mcp-tool-set,17/namespace,03/ledger-state,15/prefix-registry,15/ivg-fhir-cli findings= violates=M08-L4 refute=i08_install::refute_ctl_setting_unchecked_l4 cx=cx08_install::cx_ctl_setting_unchecked_l4
#[cfg(feature = "install_control_c3_setting_unchecked")]
impl InstallObject for CtlSettingUnchecked {
    proof fn discharge_l1() { keep_ctl_setting_unchecked_l1(); }
    proof fn discharge_l2() { keep_ctl_setting_unchecked_l2(); }
    proof fn discharge_l3() { keep_ctl_setting_unchecked_l3(); }
    proof fn discharge_l4() {
        assert(obl_l4::<Self>()); // LOCATE install_control_c3_setting_unchecked M08-L4
    }
}

// CONTROL install_control_c4_enable_race_errors mech=M-08 check=install-control-C4-enable-race-errors kind=mutant objects=01/class-set,01/legacy-object,16/rest-web-app-path,16/mcp-tool-set,17/namespace,03/ledger-state,15/prefix-registry,15/ivg-fhir-cli findings= violates=M08-L2 refute=i08_install::refute_ctl_enable_race_errors_l2 cx=cx08_install::cx_ctl_enable_race_errors_l2
#[cfg(feature = "install_control_c4_enable_race_errors")]
impl InstallObject for CtlEnableRaceErrors {
    proof fn discharge_l1() { keep_ctl_enable_race_errors_l1(); }
    proof fn discharge_l2() {
        assert(obl_l2::<Self>()); // LOCATE install_control_c4_enable_race_errors M08-L2
    }
    proof fn discharge_l3() { keep_ctl_enable_race_errors_l3(); }
    proof fn discharge_l4() { keep_ctl_enable_race_errors_l4(); }
}
} // verus!
