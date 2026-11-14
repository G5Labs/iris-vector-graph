//! M-08 counterexamples: for each departing variant and the law it breaks, a run of the generic machine with the
//! variant's parameters from the initial state to a violation (the explorer's shortest counterexample). Always
//! compiled: the baseline proves them.
use vstd::prelude::*;
use crate::exec::*;
use crate::m08_install::*;
use crate::i08_install::*;

verus! {

/// F-0103: an engine uses schema 0 on an unrecorded namespace, then setup records schema 1.
pub proof fn cx_first_use_no_record_l1()
    ensures ({
        let t = run::<InstallM<FirstUseNoRecordAsBuilt>>(install_s0(), seq![IA::FirstUse(0), IA::Setup(1)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let t = run::<InstallM<FirstUseNoRecordAsBuilt>>(install_s0(), seq![IA::FirstUse(0), IA::Setup(1)])->0;
    assert(in_schemas(t, 0) && in_schemas(t, 1));
}

/// F-0107: the first setup drops the foreign object.
pub proof fn cx_unqualified_drop_l3()
    ensures ({
        let s = run::<InstallM<UnqualifiedDropAsBuilt>>(install_s0(), Seq::empty());
        let a = IA::Setup(0);
        s is Some && install_step::<UnqualifiedDropAsBuilt>(s->0, a) is Some
            && !law_l3(s->0, a, install_step::<UnqualifiedDropAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// F-0903, F-1506: a value outside the domain is read as another value.
pub proof fn cx_unchecked_setting_l4()
    ensures ({
        let s = run::<InstallM<UncheckedSettingAsBuilt>>(install_s0(), Seq::empty());
        let a = IA::SetMode(3);
        s is Some && install_step::<UncheckedSettingAsBuilt>(s->0, a) is Some
            && !law_l4(s->0, a, install_step::<UncheckedSettingAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// F-1104: two first enables check the never-enabled ledger; the first creates the genesis; the second
/// fails instead of returning it.
pub proof fn cx_concurrent_first_enable_l2()
    ensures ({
        let s = run::<InstallM<ConcurrentFirstEnableAsBuilt>>(install_s0(), seq![IA::Check(0), IA::Check(1), IA::Create(0)]);
        let a = IA::Create(1);
        s is Some && install_step::<ConcurrentFirstEnableAsBuilt>(s->0, a) is Some
            && !law_l2(s->0, a, install_step::<ConcurrentFirstEnableAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 5);
}

/// C1: first use accepts any schema on a namespace with no record: an engine uses schema 0, then setup records schema 1.
pub proof fn cx_ctl_first_use_accepts_any_l1()
    ensures ({
        let t = run::<InstallM<CtlFirstUseAcceptsAny>>(install_s0(), seq![IA::FirstUse(0), IA::Setup(1)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
    let t = run::<InstallM<CtlFirstUseAcceptsAny>>(install_s0(), seq![IA::FirstUse(0), IA::Setup(1)])->0;
    assert(in_schemas(t, 0) && in_schemas(t, 1));
}

/// C2: setup drops an unqualified name.
pub proof fn cx_ctl_unqualified_drop_l3()
    ensures ({
        let s = run::<InstallM<CtlUnqualifiedDrop>>(install_s0(), Seq::empty());
        let a = IA::Setup(0);
        s is Some && install_step::<CtlUnqualifiedDrop>(s->0, a) is Some
            && !law_l3(s->0, a, install_step::<CtlUnqualifiedDrop>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// C3: a setting outside its domain is not checked.
pub proof fn cx_ctl_setting_unchecked_l4()
    ensures ({
        let s = run::<InstallM<CtlSettingUnchecked>>(install_s0(), Seq::empty());
        let a = IA::SetMode(3);
        s is Some && install_step::<CtlSettingUnchecked>(s->0, a) is Some
            && !law_l4(s->0, a, install_step::<CtlSettingUnchecked>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 2);
}

/// C4: the loser of a first-enable race errors.
pub proof fn cx_ctl_enable_race_errors_l2()
    ensures ({
        let s = run::<InstallM<CtlEnableRaceErrors>>(install_s0(), seq![IA::Check(0), IA::Check(1), IA::Create(0)]);
        let a = IA::Create(1);
        s is Some && install_step::<CtlEnableRaceErrors>(s->0, a) is Some
            && !law_l2(s->0, a, install_step::<CtlEnableRaceErrors>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 5);
}
} // verus!
