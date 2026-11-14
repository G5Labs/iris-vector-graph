//! M-06 instances: one type per object variant (family `snapshot`, models/semantics/src/snapshot.rs).
//!
//! Canonical and reviewed instances discharge `SnapshotObject` (the generic theorem `theorem_snapshot` then applies
//! with no proof work of their own). As-built variants that depart and the generic mutants have parameters only
//! here: kept obligations proved (`keep_*`), broken ones refuted (`refute_*`); their `SnapshotObject` impl exists only
//! under their control feature (src/ctl_snapshot.rs). A generic mutant is its own type even where its parameters
//! equal an as-built variant's (one control per instance type).
use vstd::prelude::*;
use crate::exec::*;
use crate::m06_snapshot::*;

verus! {

// ---------------------------------------------------------------- reviewed instances (baseline)

/// edge-vectors-missing, reviewed: 18/snapshot-archive; the archive carries every store.
pub struct EdgeVectorsMissingReviewed;
impl SnapshotPolicy for EdgeVectorsMissingReviewed {
    open spec fn carried(k: nat) -> bool { true }
    open spec fn head_policy() -> Head { Head::Refuses }
    open spec fn agg_policy() -> Agg { Agg::Combine }
}
impl SnapshotObject for EdgeVectorsMissingReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// replacing-restore, reviewed: 18/namespace; a replacing restore refuses when the live head is ahead.
pub struct ReplacingRestoreReviewed;
impl SnapshotPolicy for ReplacingRestoreReviewed {
    open spec fn carried(k: nat) -> bool { true }
    open spec fn head_policy() -> Head { Head::Refuses }
    open spec fn agg_policy() -> Agg { Agg::Combine }
}
impl SnapshotObject for ReplacingRestoreReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// merge-aggregates, reviewed: 18/namespace; a merge restore combines the temporal aggregates.
pub struct MergeAggregatesReviewed;
impl SnapshotPolicy for MergeAggregatesReviewed {
    open spec fn carried(k: nat) -> bool { true }
    open spec fn head_policy() -> Head { Head::Refuses }
    open spec fn agg_policy() -> Agg { Agg::Combine }
}
impl SnapshotObject for MergeAggregatesReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// The generic theorem, instantiated: each line is the whole proof work of one instance.
pub proof fn laws_edge_vectors_missing_reviewed(s0: SS, ls: Seq<SA>, t: SS, a: SA) requires reached::<SnapshotM<EdgeVectorsMissingReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_snapshot::<EdgeVectorsMissingReviewed>(s0, ls, t, a); }
pub proof fn laws_replacing_restore_reviewed(s0: SS, ls: Seq<SA>, t: SS, a: SA) requires reached::<SnapshotM<ReplacingRestoreReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_snapshot::<ReplacingRestoreReviewed>(s0, ls, t, a); }
pub proof fn laws_merge_aggregates_reviewed(s0: SS, ls: Seq<SA>, t: SS, a: SA) requires reached::<SnapshotM<MergeAggregatesReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_snapshot::<MergeAggregatesReviewed>(s0, ls, t, a); }

// ---------------------------------------------------------------- as-built variants that depart (parameters only)

/// edge-vectors-missing as built: 18/snapshot-archive (F-C1804; also F-1803, F-1804; snapshot.py:299-344, 960-1025):
/// the archive carries no routed edge vectors (store 2).
pub struct EdgeVectorsMissingAsBuilt;
impl SnapshotPolicy for EdgeVectorsMissingAsBuilt {
    open spec fn carried(k: nat) -> bool { k != 2 }
    open spec fn head_policy() -> Head { Head::Refuses }
    open spec fn agg_policy() -> Agg { Agg::Combine }
}
pub proof fn refute_edge_vectors_missing_l1() ensures !obl_l1::<EdgeVectorsMissingAsBuilt>() {}
pub proof fn keep_edge_vectors_missing_l2() ensures obl_l2::<EdgeVectorsMissingAsBuilt>() {}
pub proof fn keep_edge_vectors_missing_l3() ensures obl_l3::<EdgeVectorsMissingAsBuilt>() {}

/// replacing-restore as built: 18/namespace (F-1801; snapshot.py:1554-1588): a replacing restore lays the archive's
/// ledger head over the live one.
pub struct ReplacingRestoreAsBuilt;
impl SnapshotPolicy for ReplacingRestoreAsBuilt {
    open spec fn carried(k: nat) -> bool { true }
    open spec fn head_policy() -> Head { Head::Lays }
    open spec fn agg_policy() -> Agg { Agg::Combine }
}
pub proof fn keep_replacing_restore_l1() ensures obl_l1::<ReplacingRestoreAsBuilt>() {}
pub proof fn refute_replacing_restore_l2() ensures !obl_l2::<ReplacingRestoreAsBuilt>() {}
pub proof fn keep_replacing_restore_l3() ensures obl_l3::<ReplacingRestoreAsBuilt>() {}

/// merge-aggregates as built: 18/namespace (F-1805; snapshot.py:1679): a merge restore overwrites the temporal
/// aggregates.
pub struct MergeAggregatesAsBuilt;
impl SnapshotPolicy for MergeAggregatesAsBuilt {
    open spec fn carried(k: nat) -> bool { true }
    open spec fn head_policy() -> Head { Head::Refuses }
    open spec fn agg_policy() -> Agg { Agg::Overwrite }
}
pub proof fn keep_merge_aggregates_l1() ensures obl_l1::<MergeAggregatesAsBuilt>() {}
pub proof fn keep_merge_aggregates_l2() ensures obl_l2::<MergeAggregatesAsBuilt>() {}
pub proof fn refute_merge_aggregates_l3() ensures !obl_l3::<MergeAggregatesAsBuilt>() {}

// ---------------------------------------------------------------- generic mutants of the reviewed instance

/// snapshot-control-C1-store-left-out: the archive leaves out the temporal aggregates (store 3).
pub struct CtlStoreLeftOut;
impl SnapshotPolicy for CtlStoreLeftOut {
    open spec fn carried(k: nat) -> bool { k != 3 }
    open spec fn head_policy() -> Head { Head::Refuses }
    open spec fn agg_policy() -> Agg { Agg::Combine }
}
pub proof fn refute_ctl_store_left_out_l1() ensures !obl_l1::<CtlStoreLeftOut>() {}
pub proof fn keep_ctl_store_left_out_l2() ensures obl_l2::<CtlStoreLeftOut>() {}
pub proof fn keep_ctl_store_left_out_l3() ensures obl_l3::<CtlStoreLeftOut>() {}

/// snapshot-control-C2-head-laid-over: a replacing restore lays the archived head over the live one.
pub struct CtlHeadLaidOver;
impl SnapshotPolicy for CtlHeadLaidOver {
    open spec fn carried(k: nat) -> bool { true }
    open spec fn head_policy() -> Head { Head::Lays }
    open spec fn agg_policy() -> Agg { Agg::Combine }
}
pub proof fn keep_ctl_head_laid_over_l1() ensures obl_l1::<CtlHeadLaidOver>() {}
pub proof fn refute_ctl_head_laid_over_l2() ensures !obl_l2::<CtlHeadLaidOver>() {}
pub proof fn keep_ctl_head_laid_over_l3() ensures obl_l3::<CtlHeadLaidOver>() {}

/// snapshot-control-C3-aggregates-overwritten: a merge restore overwrites the aggregates.
pub struct CtlAggregatesOverwritten;
impl SnapshotPolicy for CtlAggregatesOverwritten {
    open spec fn carried(k: nat) -> bool { true }
    open spec fn head_policy() -> Head { Head::Refuses }
    open spec fn agg_policy() -> Agg { Agg::Overwrite }
}
pub proof fn keep_ctl_aggregates_overwritten_l1() ensures obl_l1::<CtlAggregatesOverwritten>() {}
pub proof fn keep_ctl_aggregates_overwritten_l2() ensures obl_l2::<CtlAggregatesOverwritten>() {}
pub proof fn refute_ctl_aggregates_overwritten_l3() ensures !obl_l3::<CtlAggregatesOverwritten>() {}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// snapshot-sharp-restore-refused: the reviewed design refuses a replacing restore after a later commit.
pub proof fn sharp_restore_refused()
    ensures ({
        let t = run::<SnapshotM<EdgeVectorsMissingReviewed>>(snapshot_s0(), seq![SA::Save, SA::Write(0), SA::RestoreReplace]);
        t is Some && t->0.refused > 0
    })
{
    reveal_with_fuel(run, 5);
}

/// snapshot-sharp-round-trip: a replacing restore after a later write to a non-ledger store gives the saved state.
pub proof fn sharp_round_trip()
    ensures ({
        let t = run::<SnapshotM<EdgeVectorsMissingReviewed>>(snapshot_s0(), seq![SA::Save, SA::Write(1), SA::RestoreReplace]);
        t is Some && t->0.restores >= 1 && t->0.saves == 1 && t->0.refused == 0 && t->0.live == t->0.saved && t->0.writes >= 1
    })
{
    reveal_with_fuel(run, 5);
}

} // verus!
