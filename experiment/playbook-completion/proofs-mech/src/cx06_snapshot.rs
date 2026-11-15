//! M-06 counterexamples: for each departing variant and each law it breaks, a run of the generic machine with the
//! variant's parameters from the initial state to a violation (the explorer's shortest counterexample). Always
//! compiled: the baseline proves them.
use vstd::prelude::*;
use crate::exec::*;
use crate::m06_snapshot::*;
use crate::i06_snapshot::*;

verus! {

/// F-C1804: save, then restore at once: the routed edge vectors come back empty.
pub proof fn cx_edge_vectors_missing_l1()
    ensures ({
        let t = run::<SnapshotM<EdgeVectorsMissingAsBuilt>>(snapshot_s0(), seq![SA::Save, SA::RestoreReplace]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// F-1801: save, commit, replacing restore: the head goes back below the live commit.
pub proof fn cx_replacing_restore_l2()
    ensures ({
        let s = run::<SnapshotM<ReplacingRestoreAsBuilt>>(snapshot_s0(), seq![SA::Save, SA::Write(0)]);
        let a = SA::RestoreReplace;
        s is Some && snapshot_step::<ReplacingRestoreAsBuilt>(s->0, a) is Some
            && !law_l2(s->0, a, snapshot_step::<ReplacingRestoreAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// F-1805: save, merge restore: the aggregates are overwritten, not added.
pub proof fn cx_merge_aggregates_l3()
    ensures ({
        let s = run::<SnapshotM<MergeAggregatesAsBuilt>>(snapshot_s0(), seq![SA::Save]);
        let a = SA::RestoreMerge;
        s is Some && snapshot_step::<MergeAggregatesAsBuilt>(s->0, a) is Some
            && !law_l3(s->0, a, snapshot_step::<MergeAggregatesAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// C1: save, restore at once: the temporal aggregates come back empty.
pub proof fn cx_ctl_store_left_out_l1()
    ensures ({
        let t = run::<SnapshotM<CtlStoreLeftOut>>(snapshot_s0(), seq![SA::Save, SA::RestoreReplace]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// C2: save, commit, replacing restore: the head goes back below the live commit.
pub proof fn cx_ctl_head_laid_over_l2()
    ensures ({
        let s = run::<SnapshotM<CtlHeadLaidOver>>(snapshot_s0(), seq![SA::Save, SA::Write(0)]);
        let a = SA::RestoreReplace;
        s is Some && snapshot_step::<CtlHeadLaidOver>(s->0, a) is Some
            && !law_l2(s->0, a, snapshot_step::<CtlHeadLaidOver>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// C3: save, merge restore: the aggregates are overwritten, not added.
pub proof fn cx_ctl_aggregates_overwritten_l3()
    ensures ({
        let s = run::<SnapshotM<CtlAggregatesOverwritten>>(snapshot_s0(), seq![SA::Save]);
        let a = SA::RestoreMerge;
        s is Some && snapshot_step::<CtlAggregatesOverwritten>(s->0, a) is Some
            && !law_l3(s->0, a, snapshot_step::<CtlAggregatesOverwritten>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 3);
}

} // verus!
