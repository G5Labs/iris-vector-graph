//! M-03 counterexamples: for each departing variant and each law it breaks, a schedule (the process taking each
//! step) from the initial state to a violation, as in the explorer.
use vstd::prelude::*;
use crate::exec::*;
use crate::m03_excl::*;
use crate::i03_excl::*;

verus! {

pub proof fn cx_redaction_marker_l3()
    ensures ({
        let r = run::<ExclM<RedactionMarkerAsBuilt>>(x_s0::<RedactionMarkerAsBuilt>(), seq![0nat, 0nat, 2nat, 2nat, 2nat, 2nat, 0nat, 0nat]);
        r is Some && !law_l3(r->0)
    })
{
    reveal_with_fuel(run, 9);
    let s0 = x_s0::<RedactionMarkerAsBuilt>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<RedactionMarkerAsBuilt>(s0, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s0, 0) is Some);
    let s2 = x_step::<RedactionMarkerAsBuilt>(s1, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s1, 0) is Some);
    let s3 = x_step::<RedactionMarkerAsBuilt>(s2, 2)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s2, 2) is Some);
    let s4 = x_step::<RedactionMarkerAsBuilt>(s3, 2)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s3, 2) is Some);
    let s5 = x_step::<RedactionMarkerAsBuilt>(s4, 2)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s4, 2) is Some);
    let s6 = x_step::<RedactionMarkerAsBuilt>(s5, 2)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s5, 2) is Some);
    let s7 = x_step::<RedactionMarkerAsBuilt>(s6, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s6, 0) is Some);
    let s8 = x_step::<RedactionMarkerAsBuilt>(s7, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s7, 0) is Some);
    assert(run::<ExclM<RedactionMarkerAsBuilt>>(x_s0::<RedactionMarkerAsBuilt>(), seq![0nat, 0nat, 2nat, 2nat, 2nat, 2nat, 0nat, 0nat]) == Some(s8));
}

pub proof fn cx_redaction_marker_l4()
    ensures ({
        let r = run::<ExclM<RedactionMarkerAsBuilt>>(x_s0::<RedactionMarkerAsBuilt>(), seq![1nat, 1nat, 0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 1nat, 1nat, 1nat, 1nat, 1nat, 1nat]);
        r is Some && x_step::<RedactionMarkerAsBuilt>(r->0, 1) is Some && !law_l4(r->0, 1, x_step::<RedactionMarkerAsBuilt>(r->0, 1)->0)
    })
{
    reveal_with_fuel(run, 15);
    let s0 = x_s0::<RedactionMarkerAsBuilt>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<RedactionMarkerAsBuilt>(s0, 1)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s0, 1) is Some);
    let s2 = x_step::<RedactionMarkerAsBuilt>(s1, 1)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s1, 1) is Some);
    let s3 = x_step::<RedactionMarkerAsBuilt>(s2, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s2, 0) is Some);
    let s4 = x_step::<RedactionMarkerAsBuilt>(s3, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s3, 0) is Some);
    let s5 = x_step::<RedactionMarkerAsBuilt>(s4, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s4, 0) is Some);
    let s6 = x_step::<RedactionMarkerAsBuilt>(s5, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s5, 0) is Some);
    let s7 = x_step::<RedactionMarkerAsBuilt>(s6, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s6, 0) is Some);
    let s8 = x_step::<RedactionMarkerAsBuilt>(s7, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s7, 0) is Some);
    let s9 = x_step::<RedactionMarkerAsBuilt>(s8, 1)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s8, 1) is Some);
    let s10 = x_step::<RedactionMarkerAsBuilt>(s9, 1)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s9, 1) is Some);
    let s11 = x_step::<RedactionMarkerAsBuilt>(s10, 1)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s10, 1) is Some);
    let s12 = x_step::<RedactionMarkerAsBuilt>(s11, 1)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s11, 1) is Some);
    let s13 = x_step::<RedactionMarkerAsBuilt>(s12, 1)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s12, 1) is Some);
    let s14 = x_step::<RedactionMarkerAsBuilt>(s13, 1)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s13, 1) is Some);
    assert(run::<ExclM<RedactionMarkerAsBuilt>>(x_s0::<RedactionMarkerAsBuilt>(), seq![1nat, 1nat, 0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 1nat, 1nat, 1nat, 1nat, 1nat, 1nat]) == Some(s14));
    let u = x_step::<RedactionMarkerAsBuilt>(s14, 1);
    assert(u is Some);
}

pub proof fn cx_redaction_marker_l5()
    ensures ({
        let r = run::<ExclM<RedactionMarkerAsBuilt>>(x_s0::<RedactionMarkerAsBuilt>(), seq![0nat, 0nat, 2nat, 2nat, 2nat, 2nat, 0nat, 0nat]);
        r is Some && x_step::<RedactionMarkerAsBuilt>(r->0, 0) is Some && !law_l5::<RedactionMarkerAsBuilt>(r->0, 0)
    })
{
    reveal_with_fuel(run, 9);
    let s0 = x_s0::<RedactionMarkerAsBuilt>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<RedactionMarkerAsBuilt>(s0, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s0, 0) is Some);
    let s2 = x_step::<RedactionMarkerAsBuilt>(s1, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s1, 0) is Some);
    let s3 = x_step::<RedactionMarkerAsBuilt>(s2, 2)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s2, 2) is Some);
    let s4 = x_step::<RedactionMarkerAsBuilt>(s3, 2)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s3, 2) is Some);
    let s5 = x_step::<RedactionMarkerAsBuilt>(s4, 2)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s4, 2) is Some);
    let s6 = x_step::<RedactionMarkerAsBuilt>(s5, 2)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s5, 2) is Some);
    let s7 = x_step::<RedactionMarkerAsBuilt>(s6, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s6, 0) is Some);
    let s8 = x_step::<RedactionMarkerAsBuilt>(s7, 0)->0;
    assert(x_step::<RedactionMarkerAsBuilt>(s7, 0) is Some);
    assert(run::<ExclM<RedactionMarkerAsBuilt>>(x_s0::<RedactionMarkerAsBuilt>(), seq![0nat, 0nat, 2nat, 2nat, 2nat, 2nat, 0nat, 0nat]) == Some(s8));
    let u = x_step::<RedactionMarkerAsBuilt>(s8, 0);
    assert(u is Some);
}

pub proof fn cx_eraser_no_head_lock_l2()
    ensures ({
        let r = run::<ExclM<EraserNoHeadLockAsBuilt>>(x_s0::<EraserNoHeadLockAsBuilt>(), seq![]);
        r is Some && x_step::<EraserNoHeadLockAsBuilt>(r->0, 0) is Some && !law_l2::<EraserNoHeadLockAsBuilt>(r->0, 0)
    })
{
    reveal_with_fuel(run, 1);
    let s0 = x_s0::<EraserNoHeadLockAsBuilt>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    assert(run::<ExclM<EraserNoHeadLockAsBuilt>>(x_s0::<EraserNoHeadLockAsBuilt>(), seq![]) == Some(s0));
    let u = x_step::<EraserNoHeadLockAsBuilt>(s0, 0);
    assert(u is Some);
}

pub proof fn cx_adjacency_writer_lock_l2()
    ensures ({
        let r = run::<ExclM<AdjacencyWriterLockAsBuilt>>(x_s0::<AdjacencyWriterLockAsBuilt>(), seq![]);
        r is Some && x_step::<AdjacencyWriterLockAsBuilt>(r->0, 1) is Some && !law_l2::<AdjacencyWriterLockAsBuilt>(r->0, 1)
    })
{
    reveal_with_fuel(run, 1);
    let s0 = x_s0::<AdjacencyWriterLockAsBuilt>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    assert(run::<ExclM<AdjacencyWriterLockAsBuilt>>(x_s0::<AdjacencyWriterLockAsBuilt>(), seq![]) == Some(s0));
    let u = x_step::<AdjacencyWriterLockAsBuilt>(s0, 1);
    assert(u is Some);
}

pub proof fn cx_bm25_write_lock_l2()
    ensures ({
        let r = run::<ExclM<Bm25WriteLockAsBuilt>>(x_s0::<Bm25WriteLockAsBuilt>(), seq![]);
        r is Some && x_step::<Bm25WriteLockAsBuilt>(r->0, 1) is Some && !law_l2::<Bm25WriteLockAsBuilt>(r->0, 1)
    })
{
    reveal_with_fuel(run, 1);
    let s0 = x_s0::<Bm25WriteLockAsBuilt>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    assert(run::<ExclM<Bm25WriteLockAsBuilt>>(x_s0::<Bm25WriteLockAsBuilt>(), seq![]) == Some(s0));
    let u = x_step::<Bm25WriteLockAsBuilt>(s0, 1);
    assert(u is Some);
}

pub proof fn cx_plan_build_lock_l2()
    ensures ({
        let r = run::<ExclM<PlanBuildLockAsBuilt>>(x_s0::<PlanBuildLockAsBuilt>(), seq![]);
        r is Some && x_step::<PlanBuildLockAsBuilt>(r->0, 1) is Some && !law_l2::<PlanBuildLockAsBuilt>(r->0, 1)
    })
{
    reveal_with_fuel(run, 1);
    let s0 = x_s0::<PlanBuildLockAsBuilt>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    assert(run::<ExclM<PlanBuildLockAsBuilt>>(x_s0::<PlanBuildLockAsBuilt>(), seq![]) == Some(s0));
    let u = x_step::<PlanBuildLockAsBuilt>(s0, 1);
    assert(u is Some);
}

pub proof fn cx_mode_switch_l2()
    ensures ({
        let r = run::<ExclM<ModeSwitchAsBuilt>>(x_s0::<ModeSwitchAsBuilt>(), seq![]);
        r is Some && x_step::<ModeSwitchAsBuilt>(r->0, 0) is Some && !law_l2::<ModeSwitchAsBuilt>(r->0, 0)
    })
{
    reveal_with_fuel(run, 1);
    let s0 = x_s0::<ModeSwitchAsBuilt>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    assert(run::<ExclM<ModeSwitchAsBuilt>>(x_s0::<ModeSwitchAsBuilt>(), seq![]) == Some(s0));
    let u = x_step::<ModeSwitchAsBuilt>(s0, 0);
    assert(u is Some);
}

pub proof fn cx_ctl_lock_admits_two_l1()
    ensures ({
        let r = run::<ExclM<CtlLockAdmitsTwo>>(x_s0::<CtlLockAdmitsTwo>(), seq![1nat, 0nat]);
        r is Some && !law_l1(r->0)
    })
{
    reveal_with_fuel(run, 3);
    let s0 = x_s0::<CtlLockAdmitsTwo>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<CtlLockAdmitsTwo>(s0, 1)->0;
    assert(x_step::<CtlLockAdmitsTwo>(s0, 1) is Some);
    let s2 = x_step::<CtlLockAdmitsTwo>(s1, 0)->0;
    assert(x_step::<CtlLockAdmitsTwo>(s1, 0) is Some);
    assert(run::<ExclM<CtlLockAdmitsTwo>>(x_s0::<CtlLockAdmitsTwo>(), seq![1nat, 0nat]) == Some(s2));
    assert(s2.excl.contains(0) && s2.excl.contains(1));
}

pub proof fn cx_ctl_writer_without_lock_l2()
    ensures ({
        let r = run::<ExclM<CtlWriterWithoutLock>>(x_s0::<CtlWriterWithoutLock>(), seq![1nat]);
        r is Some && x_step::<CtlWriterWithoutLock>(r->0, 1) is Some && !law_l2::<CtlWriterWithoutLock>(r->0, 1)
    })
{
    reveal_with_fuel(run, 2);
    let s0 = x_s0::<CtlWriterWithoutLock>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<CtlWriterWithoutLock>(s0, 1)->0;
    assert(x_step::<CtlWriterWithoutLock>(s0, 1) is Some);
    assert(run::<ExclM<CtlWriterWithoutLock>>(x_s0::<CtlWriterWithoutLock>(), seq![1nat]) == Some(s1));
    let u = x_step::<CtlWriterWithoutLock>(s1, 1);
    assert(u is Some);
}

pub proof fn cx_ctl_writer_without_lock_l3()
    ensures ({
        let r = run::<ExclM<CtlWriterWithoutLock>>(x_s0::<CtlWriterWithoutLock>(), seq![1nat, 0nat, 0nat, 0nat, 0nat, 1nat]);
        r is Some && !law_l3(r->0)
    })
{
    reveal_with_fuel(run, 7);
    let s0 = x_s0::<CtlWriterWithoutLock>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<CtlWriterWithoutLock>(s0, 1)->0;
    assert(x_step::<CtlWriterWithoutLock>(s0, 1) is Some);
    let s2 = x_step::<CtlWriterWithoutLock>(s1, 0)->0;
    assert(x_step::<CtlWriterWithoutLock>(s1, 0) is Some);
    let s3 = x_step::<CtlWriterWithoutLock>(s2, 0)->0;
    assert(x_step::<CtlWriterWithoutLock>(s2, 0) is Some);
    let s4 = x_step::<CtlWriterWithoutLock>(s3, 0)->0;
    assert(x_step::<CtlWriterWithoutLock>(s3, 0) is Some);
    let s5 = x_step::<CtlWriterWithoutLock>(s4, 0)->0;
    assert(x_step::<CtlWriterWithoutLock>(s4, 0) is Some);
    let s6 = x_step::<CtlWriterWithoutLock>(s5, 1)->0;
    assert(x_step::<CtlWriterWithoutLock>(s5, 1) is Some);
    assert(run::<ExclM<CtlWriterWithoutLock>>(x_s0::<CtlWriterWithoutLock>(), seq![1nat, 0nat, 0nat, 0nat, 0nat, 1nat]) == Some(s6));
}

pub proof fn cx_ctl_writer_without_lock_l5()
    ensures ({
        let r = run::<ExclM<CtlWriterWithoutLock>>(x_s0::<CtlWriterWithoutLock>(), seq![1nat, 0nat, 0nat, 0nat, 1nat, 0nat]);
        r is Some && x_step::<CtlWriterWithoutLock>(r->0, 0) is Some && !law_l5::<CtlWriterWithoutLock>(r->0, 0)
    })
{
    reveal_with_fuel(run, 7);
    let s0 = x_s0::<CtlWriterWithoutLock>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<CtlWriterWithoutLock>(s0, 1)->0;
    assert(x_step::<CtlWriterWithoutLock>(s0, 1) is Some);
    let s2 = x_step::<CtlWriterWithoutLock>(s1, 0)->0;
    assert(x_step::<CtlWriterWithoutLock>(s1, 0) is Some);
    let s3 = x_step::<CtlWriterWithoutLock>(s2, 0)->0;
    assert(x_step::<CtlWriterWithoutLock>(s2, 0) is Some);
    let s4 = x_step::<CtlWriterWithoutLock>(s3, 0)->0;
    assert(x_step::<CtlWriterWithoutLock>(s3, 0) is Some);
    let s5 = x_step::<CtlWriterWithoutLock>(s4, 1)->0;
    assert(x_step::<CtlWriterWithoutLock>(s4, 1) is Some);
    let s6 = x_step::<CtlWriterWithoutLock>(s5, 0)->0;
    assert(x_step::<CtlWriterWithoutLock>(s5, 0) is Some);
    assert(run::<ExclM<CtlWriterWithoutLock>>(x_s0::<CtlWriterWithoutLock>(), seq![1nat, 0nat, 0nat, 0nat, 1nat, 0nat]) == Some(s6));
    let u = x_step::<CtlWriterWithoutLock>(s6, 0);
    assert(u is Some);
}

pub proof fn cx_ctl_check_before_lock_l3()
    ensures ({
        let r = run::<ExclM<CtlCheckBeforeLock>>(x_s0::<CtlCheckBeforeLock>(), seq![0nat, 1nat, 1nat, 1nat, 1nat, 0nat, 0nat, 0nat]);
        r is Some && !law_l3(r->0)
    })
{
    reveal_with_fuel(run, 9);
    let s0 = x_s0::<CtlCheckBeforeLock>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<CtlCheckBeforeLock>(s0, 0)->0;
    assert(x_step::<CtlCheckBeforeLock>(s0, 0) is Some);
    let s2 = x_step::<CtlCheckBeforeLock>(s1, 1)->0;
    assert(x_step::<CtlCheckBeforeLock>(s1, 1) is Some);
    let s3 = x_step::<CtlCheckBeforeLock>(s2, 1)->0;
    assert(x_step::<CtlCheckBeforeLock>(s2, 1) is Some);
    let s4 = x_step::<CtlCheckBeforeLock>(s3, 1)->0;
    assert(x_step::<CtlCheckBeforeLock>(s3, 1) is Some);
    let s5 = x_step::<CtlCheckBeforeLock>(s4, 1)->0;
    assert(x_step::<CtlCheckBeforeLock>(s4, 1) is Some);
    let s6 = x_step::<CtlCheckBeforeLock>(s5, 0)->0;
    assert(x_step::<CtlCheckBeforeLock>(s5, 0) is Some);
    let s7 = x_step::<CtlCheckBeforeLock>(s6, 0)->0;
    assert(x_step::<CtlCheckBeforeLock>(s6, 0) is Some);
    let s8 = x_step::<CtlCheckBeforeLock>(s7, 0)->0;
    assert(x_step::<CtlCheckBeforeLock>(s7, 0) is Some);
    assert(run::<ExclM<CtlCheckBeforeLock>>(x_s0::<CtlCheckBeforeLock>(), seq![0nat, 1nat, 1nat, 1nat, 1nat, 0nat, 0nat, 0nat]) == Some(s8));
}

pub proof fn cx_ctl_check_before_lock_l5()
    ensures ({
        let r = run::<ExclM<CtlCheckBeforeLock>>(x_s0::<CtlCheckBeforeLock>(), seq![0nat, 1nat, 1nat, 1nat, 1nat, 0nat, 0nat, 0nat]);
        r is Some && x_step::<CtlCheckBeforeLock>(r->0, 0) is Some && !law_l5::<CtlCheckBeforeLock>(r->0, 0)
    })
{
    reveal_with_fuel(run, 9);
    let s0 = x_s0::<CtlCheckBeforeLock>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<CtlCheckBeforeLock>(s0, 0)->0;
    assert(x_step::<CtlCheckBeforeLock>(s0, 0) is Some);
    let s2 = x_step::<CtlCheckBeforeLock>(s1, 1)->0;
    assert(x_step::<CtlCheckBeforeLock>(s1, 1) is Some);
    let s3 = x_step::<CtlCheckBeforeLock>(s2, 1)->0;
    assert(x_step::<CtlCheckBeforeLock>(s2, 1) is Some);
    let s4 = x_step::<CtlCheckBeforeLock>(s3, 1)->0;
    assert(x_step::<CtlCheckBeforeLock>(s3, 1) is Some);
    let s5 = x_step::<CtlCheckBeforeLock>(s4, 1)->0;
    assert(x_step::<CtlCheckBeforeLock>(s4, 1) is Some);
    let s6 = x_step::<CtlCheckBeforeLock>(s5, 0)->0;
    assert(x_step::<CtlCheckBeforeLock>(s5, 0) is Some);
    let s7 = x_step::<CtlCheckBeforeLock>(s6, 0)->0;
    assert(x_step::<CtlCheckBeforeLock>(s6, 0) is Some);
    let s8 = x_step::<CtlCheckBeforeLock>(s7, 0)->0;
    assert(x_step::<CtlCheckBeforeLock>(s7, 0) is Some);
    assert(run::<ExclM<CtlCheckBeforeLock>>(x_s0::<CtlCheckBeforeLock>(), seq![0nat, 1nat, 1nat, 1nat, 1nat, 0nat, 0nat, 0nat]) == Some(s8));
    let u = x_step::<CtlCheckBeforeLock>(s8, 0);
    assert(u is Some);
}

pub proof fn cx_ctl_clear_any_l4()
    ensures ({
        let r = run::<ExclM<CtlClearAny>>(x_s0::<CtlClearAny>(), seq![0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 1nat, 1nat, 1nat, 1nat, 1nat]);
        r is Some && x_step::<CtlClearAny>(r->0, 1) is Some && !law_l4(r->0, 1, x_step::<CtlClearAny>(r->0, 1)->0)
    })
{
    reveal_with_fuel(run, 12);
    let s0 = x_s0::<CtlClearAny>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<CtlClearAny>(s0, 0)->0;
    assert(x_step::<CtlClearAny>(s0, 0) is Some);
    let s2 = x_step::<CtlClearAny>(s1, 0)->0;
    assert(x_step::<CtlClearAny>(s1, 0) is Some);
    let s3 = x_step::<CtlClearAny>(s2, 0)->0;
    assert(x_step::<CtlClearAny>(s2, 0) is Some);
    let s4 = x_step::<CtlClearAny>(s3, 0)->0;
    assert(x_step::<CtlClearAny>(s3, 0) is Some);
    let s5 = x_step::<CtlClearAny>(s4, 0)->0;
    assert(x_step::<CtlClearAny>(s4, 0) is Some);
    let s6 = x_step::<CtlClearAny>(s5, 0)->0;
    assert(x_step::<CtlClearAny>(s5, 0) is Some);
    let s7 = x_step::<CtlClearAny>(s6, 1)->0;
    assert(x_step::<CtlClearAny>(s6, 1) is Some);
    let s8 = x_step::<CtlClearAny>(s7, 1)->0;
    assert(x_step::<CtlClearAny>(s7, 1) is Some);
    let s9 = x_step::<CtlClearAny>(s8, 1)->0;
    assert(x_step::<CtlClearAny>(s8, 1) is Some);
    let s10 = x_step::<CtlClearAny>(s9, 1)->0;
    assert(x_step::<CtlClearAny>(s9, 1) is Some);
    let s11 = x_step::<CtlClearAny>(s10, 1)->0;
    assert(x_step::<CtlClearAny>(s10, 1) is Some);
    assert(run::<ExclM<CtlClearAny>>(x_s0::<CtlClearAny>(), seq![0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 1nat, 1nat, 1nat, 1nat, 1nat]) == Some(s11));
    let u = x_step::<CtlClearAny>(s11, 1);
    assert(u is Some);
}

pub proof fn cx_ctl_tomb_without_check_l3()
    ensures ({
        let r = run::<ExclM<CtlTombWithoutCheck>>(x_s0::<CtlTombWithoutCheck>(), seq![1nat, 1nat, 1nat, 0nat, 0nat]);
        r is Some && !law_l3(r->0)
    })
{
    reveal_with_fuel(run, 6);
    let s0 = x_s0::<CtlTombWithoutCheck>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<CtlTombWithoutCheck>(s0, 1)->0;
    assert(x_step::<CtlTombWithoutCheck>(s0, 1) is Some);
    let s2 = x_step::<CtlTombWithoutCheck>(s1, 1)->0;
    assert(x_step::<CtlTombWithoutCheck>(s1, 1) is Some);
    let s3 = x_step::<CtlTombWithoutCheck>(s2, 1)->0;
    assert(x_step::<CtlTombWithoutCheck>(s2, 1) is Some);
    let s4 = x_step::<CtlTombWithoutCheck>(s3, 0)->0;
    assert(x_step::<CtlTombWithoutCheck>(s3, 0) is Some);
    let s5 = x_step::<CtlTombWithoutCheck>(s4, 0)->0;
    assert(x_step::<CtlTombWithoutCheck>(s4, 0) is Some);
    assert(run::<ExclM<CtlTombWithoutCheck>>(x_s0::<CtlTombWithoutCheck>(), seq![1nat, 1nat, 1nat, 0nat, 0nat]) == Some(s5));
}

pub proof fn cx_ctl_tomb_without_check_l5()
    ensures ({
        let r = run::<ExclM<CtlTombWithoutCheck>>(x_s0::<CtlTombWithoutCheck>(), seq![1nat, 1nat, 1nat, 0nat, 0nat]);
        r is Some && x_step::<CtlTombWithoutCheck>(r->0, 0) is Some && !law_l5::<CtlTombWithoutCheck>(r->0, 0)
    })
{
    reveal_with_fuel(run, 6);
    let s0 = x_s0::<CtlTombWithoutCheck>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<CtlTombWithoutCheck>(s0, 1)->0;
    assert(x_step::<CtlTombWithoutCheck>(s0, 1) is Some);
    let s2 = x_step::<CtlTombWithoutCheck>(s1, 1)->0;
    assert(x_step::<CtlTombWithoutCheck>(s1, 1) is Some);
    let s3 = x_step::<CtlTombWithoutCheck>(s2, 1)->0;
    assert(x_step::<CtlTombWithoutCheck>(s2, 1) is Some);
    let s4 = x_step::<CtlTombWithoutCheck>(s3, 0)->0;
    assert(x_step::<CtlTombWithoutCheck>(s3, 0) is Some);
    let s5 = x_step::<CtlTombWithoutCheck>(s4, 0)->0;
    assert(x_step::<CtlTombWithoutCheck>(s4, 0) is Some);
    assert(run::<ExclM<CtlTombWithoutCheck>>(x_s0::<CtlTombWithoutCheck>(), seq![1nat, 1nat, 1nat, 0nat, 0nat]) == Some(s5));
    let u = x_step::<CtlTombWithoutCheck>(s5, 0);
    assert(u is Some);
}

} // verus!
