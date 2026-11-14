//! M-08 instances: one type per object variant (family `install`, models/semantics/src/install.rs).
//!
//! Canonical and reviewed instances discharge `InstallObject` (the generic theorem `theorem_install` then applies with
//! no proof work of their own). As-built variants that depart have parameters only here: kept obligations proved
//! (`keep_*`), the broken one refuted (`refute_*`); their `InstallObject` impl exists only under their control feature
//! (src/ctl_install.rs). The generic mutants of the explorer (install-control-C1..C4) are their own types although
//! their parameters equal the as-built variants' (one control per instance type).
use vstd::prelude::*;
use crate::exec::*;
use crate::m08_install::*;

verus! {

// ---------------------------------------------------------------- canonical and reviewed instances (baseline)

/// canonical: 01/class-set, 01/legacy-object, 16/rest-web-app-path, 16/mcp-tool-set, 17/namespace, 03/ledger-state,
/// 15/prefix-registry, 15/ivg-fhir-cli (schema.py deploy, legacy.py, admin.py, Ledger.cls:252-380): every flag off.
pub struct Canonical;
impl InstallPolicy for Canonical {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { false }
}
impl InstallObject for Canonical {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// first-use-no-record, reviewed: 01/namespace; first use refuses a namespace with no schema record.
pub struct FirstUseNoRecordReviewed;
impl InstallPolicy for FirstUseNoRecordReviewed {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { false }
}
impl InstallObject for FirstUseNoRecordReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// unqualified-drop, reviewed: 01/setup-routine; setup drops only its own schema's names.
pub struct UnqualifiedDropReviewed;
impl InstallPolicy for UnqualifiedDropReviewed {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { false }
}
impl InstallObject for UnqualifiedDropReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// unchecked-setting, reviewed: 09/process-mode, 15/rdf-extra; a value outside the domain is refused.
pub struct UncheckedSettingReviewed;
impl InstallPolicy for UncheckedSettingReviewed {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { false }
}
impl InstallObject for UncheckedSettingReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// concurrent-first-enable, reviewed: 11/ledger; the second of two first enables returns the genesis.
pub struct ConcurrentFirstEnableReviewed;
impl InstallPolicy for ConcurrentFirstEnableReviewed {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { false }
}
impl InstallObject for ConcurrentFirstEnableReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// The generic theorem, instantiated: each line is the whole proof work of one instance.
pub proof fn laws_canonical(s0: IS, ls: Seq<IA>, t: IS, a: IA) requires reached::<InstallM<Canonical>>(s0, ls, t)
    ensures law_l1(t) { theorem_install::<Canonical>(s0, ls, t, a); }
pub proof fn laws_first_use_no_record_reviewed(s0: IS, ls: Seq<IA>, t: IS, a: IA) requires reached::<InstallM<FirstUseNoRecordReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_install::<FirstUseNoRecordReviewed>(s0, ls, t, a); }
pub proof fn laws_unqualified_drop_reviewed(s0: IS, ls: Seq<IA>, t: IS, a: IA) requires reached::<InstallM<UnqualifiedDropReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_install::<UnqualifiedDropReviewed>(s0, ls, t, a); }
pub proof fn laws_unchecked_setting_reviewed(s0: IS, ls: Seq<IA>, t: IS, a: IA) requires reached::<InstallM<UncheckedSettingReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_install::<UncheckedSettingReviewed>(s0, ls, t, a); }
pub proof fn laws_concurrent_first_enable_reviewed(s0: IS, ls: Seq<IA>, t: IS, a: IA) requires reached::<InstallM<ConcurrentFirstEnableReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_install::<ConcurrentFirstEnableReviewed>(s0, ls, t, a); }

// ---------------------------------------------------------------- as-built variants that depart (parameters only)

/// first-use-no-record as built: 01/namespace (F-0103; schema_name.py:220-235): first use accepts a namespace with no
/// schema record.
pub struct FirstUseNoRecordAsBuilt;
impl InstallPolicy for FirstUseNoRecordAsBuilt {
    open spec fn first_use_accepts_unrecorded() -> bool { true }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { false }
}
pub proof fn refute_first_use_no_record_l1() ensures !obl_l1::<FirstUseNoRecordAsBuilt>() {}
pub proof fn keep_first_use_no_record_l2() ensures obl_l2::<FirstUseNoRecordAsBuilt>() {}
pub proof fn keep_first_use_no_record_l3() ensures obl_l3::<FirstUseNoRecordAsBuilt>() {}
pub proof fn keep_first_use_no_record_l4() ensures obl_l4::<FirstUseNoRecordAsBuilt>() {}

/// unqualified-drop as built: 01/setup-routine (F-0107; schema.py:655-658): setup runs an unqualified DROP INDEX.
pub struct UnqualifiedDropAsBuilt;
impl InstallPolicy for UnqualifiedDropAsBuilt {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { true }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { false }
}
pub proof fn keep_unqualified_drop_l1() ensures obl_l1::<UnqualifiedDropAsBuilt>() {}
pub proof fn keep_unqualified_drop_l2() ensures obl_l2::<UnqualifiedDropAsBuilt>() {}
pub proof fn refute_unqualified_drop_l3() ensures !obl_l3::<UnqualifiedDropAsBuilt>() {}
pub proof fn keep_unqualified_drop_l4() ensures obl_l4::<UnqualifiedDropAsBuilt>() {}

/// unchecked-setting as built: 09/process-mode, 15/rdf-extra (F-0903, F-1506; Gen.cls:41-44, _rdf_utils.py:125-133): a
/// setting outside its domain is read as another value.
pub struct UncheckedSettingAsBuilt;
impl InstallPolicy for UncheckedSettingAsBuilt {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { true }
    open spec fn enable_race_errors() -> bool { false }
}
pub proof fn keep_unchecked_setting_l1() ensures obl_l1::<UncheckedSettingAsBuilt>() {}
pub proof fn keep_unchecked_setting_l2() ensures obl_l2::<UncheckedSettingAsBuilt>() {}
pub proof fn keep_unchecked_setting_l3() ensures obl_l3::<UncheckedSettingAsBuilt>() {}
pub proof fn refute_unchecked_setting_l4() ensures !obl_l4::<UncheckedSettingAsBuilt>() {}

/// concurrent-first-enable as built: 11/ledger (F-1104; Ledger.cls:252-329): the second of two first enables fails
/// instead of returning the genesis.
pub struct ConcurrentFirstEnableAsBuilt;
impl InstallPolicy for ConcurrentFirstEnableAsBuilt {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { true }
}
pub proof fn keep_concurrent_first_enable_l1() ensures obl_l1::<ConcurrentFirstEnableAsBuilt>() {}
pub proof fn refute_concurrent_first_enable_l2() ensures !obl_l2::<ConcurrentFirstEnableAsBuilt>() {}
pub proof fn keep_concurrent_first_enable_l3() ensures obl_l3::<ConcurrentFirstEnableAsBuilt>() {}
pub proof fn keep_concurrent_first_enable_l4() ensures obl_l4::<ConcurrentFirstEnableAsBuilt>() {}

// ---------------------------------------------------------------- generic mutants of the canonical instance

/// install-control-C1-first-use-accepts-any: first use accepts any schema on a namespace with no record.
pub struct CtlFirstUseAcceptsAny;
impl InstallPolicy for CtlFirstUseAcceptsAny {
    open spec fn first_use_accepts_unrecorded() -> bool { true }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { false }
}
pub proof fn refute_ctl_first_use_accepts_any_l1() ensures !obl_l1::<CtlFirstUseAcceptsAny>() {}
pub proof fn keep_ctl_first_use_accepts_any_l2() ensures obl_l2::<CtlFirstUseAcceptsAny>() {}
pub proof fn keep_ctl_first_use_accepts_any_l3() ensures obl_l3::<CtlFirstUseAcceptsAny>() {}
pub proof fn keep_ctl_first_use_accepts_any_l4() ensures obl_l4::<CtlFirstUseAcceptsAny>() {}

/// install-control-C2-unqualified-drop: setup drops an unqualified name.
pub struct CtlUnqualifiedDrop;
impl InstallPolicy for CtlUnqualifiedDrop {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { true }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { false }
}
pub proof fn keep_ctl_unqualified_drop_l1() ensures obl_l1::<CtlUnqualifiedDrop>() {}
pub proof fn keep_ctl_unqualified_drop_l2() ensures obl_l2::<CtlUnqualifiedDrop>() {}
pub proof fn refute_ctl_unqualified_drop_l3() ensures !obl_l3::<CtlUnqualifiedDrop>() {}
pub proof fn keep_ctl_unqualified_drop_l4() ensures obl_l4::<CtlUnqualifiedDrop>() {}

/// install-control-C3-setting-unchecked: a setting outside its domain is not checked.
pub struct CtlSettingUnchecked;
impl InstallPolicy for CtlSettingUnchecked {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { true }
    open spec fn enable_race_errors() -> bool { false }
}
pub proof fn keep_ctl_setting_unchecked_l1() ensures obl_l1::<CtlSettingUnchecked>() {}
pub proof fn keep_ctl_setting_unchecked_l2() ensures obl_l2::<CtlSettingUnchecked>() {}
pub proof fn keep_ctl_setting_unchecked_l3() ensures obl_l3::<CtlSettingUnchecked>() {}
pub proof fn refute_ctl_setting_unchecked_l4() ensures !obl_l4::<CtlSettingUnchecked>() {}

/// install-control-C4-enable-race-errors: the loser of a first-enable race errors.
pub struct CtlEnableRaceErrors;
impl InstallPolicy for CtlEnableRaceErrors {
    open spec fn first_use_accepts_unrecorded() -> bool { false }
    open spec fn drop_unqualified() -> bool { false }
    open spec fn invalid_setting_accepted() -> bool { false }
    open spec fn enable_race_errors() -> bool { true }
}
pub proof fn keep_ctl_enable_race_errors_l1() ensures obl_l1::<CtlEnableRaceErrors>() {}
pub proof fn refute_ctl_enable_race_errors_l2() ensures !obl_l2::<CtlEnableRaceErrors>() {}
pub proof fn keep_ctl_enable_race_errors_l3() ensures obl_l3::<CtlEnableRaceErrors>() {}
pub proof fn keep_ctl_enable_race_errors_l4() ensures obl_l4::<CtlEnableRaceErrors>() {}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// install-sharp-other-schema-refused: a setup for another schema is refused.
pub proof fn sharp_other_schema_refused()
    ensures ({
        let t = run::<InstallM<Canonical>>(install_s0(), seq![IA::Setup(0), IA::Setup(1)]);
        t is Some && !t->0.last_ok
    })
{
    reveal_with_fuel(run, 4);
}

/// install-sharp-both-enables-ok: both of two concurrent first enables answer ok.
pub proof fn sharp_both_enables_ok()
    ensures ({
        let t = run::<InstallM<Canonical>>(install_s0(), seq![IA::Check(0), IA::Check(1), IA::Create(0), IA::Create(1)]);
        t is Some && t->0.en.len() == 2 && t->0.en[0] == En::Done(true) && t->0.en[1] == En::Done(true)
    })
{
    reveal_with_fuel(run, 6);
}

} // verus!
