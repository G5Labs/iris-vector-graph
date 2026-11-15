//! M-01 instances: one type per object variant of mechanisms.json (family `ledger`, models/semantics/src/ledger.rs).
//!
//! An instance is its parameters (`LedgerPolicy::paths`) and, when it keeps every law, its discharge of the
//! obligations (`LedgerObject`): the generic theorem `theorem_ledger` then applies with no proof work of its own.
//! As-built variants that depart and the generic mutants (the semantics lane's negative controls) have parameters
//! only here; their kept obligations are proved (`keep_*`), their broken ones refuted (`refute_*`), and their
//! `LedgerObject` impl exists only under their control feature (src/ctl_ledger.rs).
use vstd::prelude::*;
use crate::exec::*;
use crate::m01_ledger::*;

verus! {

// ---------------------------------------------------------------- canonical and reviewed instances (baseline)

/// commit-core: 11/ledger, 11/edge-statement, 14/ledger-view (canonical; Ledger.cls:397-528, replay.py:155-210).
pub struct CommitCore;
impl LedgerPolicy for CommitCore { open spec fn paths() -> Seq<Path> { seq![Path::Commit] } }
impl LedgerObject for CommitCore {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// node-delete-named-only, reviewed: 11/node-id; a delete that removes nothing writes no record.
pub struct NodeDeleteNamedOnlyReviewed;
impl LedgerPolicy for NodeDeleteNamedOnlyReviewed {
    open spec fn paths() -> Seq<Path> { seq![Path::Commit, Path::DeleteAbsent { record_anyway: false }] }
}
impl LedgerObject for NodeDeleteNamedOnlyReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// temporal-insert-collision, reviewed: 05/temporal-coordinates; a colliding insert is counted, not recorded.
pub struct TemporalInsertCollisionReviewed;
impl LedgerPolicy for TemporalInsertCollisionReviewed {
    open spec fn paths() -> Seq<Path> { seq![Path::Commit, Path::InsertIfAbsent { record_on_collision: false }] }
}
impl LedgerObject for TemporalInsertCollisionReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// strict-cached-guard, reviewed: 03/ledger-state, 08/cypher-node, 08/cypher-edge, 08/cypher-call; the bypass
/// guard is the server's strict flag.
pub struct StrictCachedGuardReviewed;
impl LedgerPolicy for StrictCachedGuardReviewed {
    open spec fn paths() -> Seq<Path> { seq![Path::Commit, Path::Bypass(Guard::Server)] }
}
impl LedgerObject for StrictCachedGuardReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// bypass-unchecked, reviewed: 03/node-in-one-graph, 03/edge-in-one-graph; every bypass path checks the server flag.
pub struct BypassUncheckedReviewed;
impl LedgerPolicy for BypassUncheckedReviewed {
    open spec fn paths() -> Seq<Path> { seq![Path::Commit, Path::Bypass(Guard::Server)] }
}
impl LedgerObject for BypassUncheckedReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// The generic theorem, instantiated: each line is the whole proof work of one instance.
pub proof fn laws_commit_core(s0: LS, ls: Seq<LA>, t: LS, a: LA) requires reached::<LedgerM<CommitCore>>(s0, ls, t)
    ensures law_l2(t) { theorem_ledger::<CommitCore>(s0, ls, t, a); }
pub proof fn laws_node_delete_named_only_reviewed(s0: LS, ls: Seq<LA>, t: LS, a: LA) requires reached::<LedgerM<NodeDeleteNamedOnlyReviewed>>(s0, ls, t)
    ensures law_l2(t) { theorem_ledger::<NodeDeleteNamedOnlyReviewed>(s0, ls, t, a); }
pub proof fn laws_temporal_insert_collision_reviewed(s0: LS, ls: Seq<LA>, t: LS, a: LA) requires reached::<LedgerM<TemporalInsertCollisionReviewed>>(s0, ls, t)
    ensures law_l2(t) { theorem_ledger::<TemporalInsertCollisionReviewed>(s0, ls, t, a); }
pub proof fn laws_strict_cached_guard_reviewed(s0: LS, ls: Seq<LA>, t: LS, a: LA) requires reached::<LedgerM<StrictCachedGuardReviewed>>(s0, ls, t)
    ensures law_l2(t) { theorem_ledger::<StrictCachedGuardReviewed>(s0, ls, t, a); }
pub proof fn laws_bypass_unchecked_reviewed(s0: LS, ls: Seq<LA>, t: LS, a: LA) requires reached::<LedgerM<BypassUncheckedReviewed>>(s0, ls, t)
    ensures law_l2(t) { theorem_ledger::<BypassUncheckedReviewed>(s0, ls, t, a); }

// ---------------------------------------------------------------- as-built variants that depart (parameters only)

/// node-delete-named-only as built: 11/node-id (F-1105; LedgerApply.cls:79-84, 354-385): a delete of a node only a
/// named graph holds is recorded although it removed nothing.
pub struct NodeDeleteNamedOnlyAsBuilt;
impl LedgerPolicy for NodeDeleteNamedOnlyAsBuilt {
    open spec fn paths() -> Seq<Path> { seq![Path::Commit, Path::DeleteAbsent { record_anyway: true }] }
}
pub proof fn keep_node_delete_named_only_l1() ensures obl_l1::<NodeDeleteNamedOnlyAsBuilt>() {}
pub proof fn refute_node_delete_named_only_l2() ensures !obl_l2::<NodeDeleteNamedOnlyAsBuilt>() {
    assert(!path_records_its_change(NodeDeleteNamedOnlyAsBuilt::paths()[1]));
}
pub proof fn keep_node_delete_named_only_l3() ensures obl_l3::<NodeDeleteNamedOnlyAsBuilt>() {}
pub proof fn keep_node_delete_named_only_l4() ensures obl_l4::<NodeDeleteNamedOnlyAsBuilt>() {}

/// temporal-insert-collision as built: 05/temporal-coordinates (F-0511): an insert-mode op is recorded although it
/// collided and changed nothing.
pub struct TemporalInsertCollisionAsBuilt;
impl LedgerPolicy for TemporalInsertCollisionAsBuilt {
    open spec fn paths() -> Seq<Path> { seq![Path::Commit, Path::InsertIfAbsent { record_on_collision: true }] }
}
pub proof fn keep_temporal_insert_collision_l1() ensures obl_l1::<TemporalInsertCollisionAsBuilt>() {}
pub proof fn refute_temporal_insert_collision_l2() ensures !obl_l2::<TemporalInsertCollisionAsBuilt>() {
    assert(!path_records_its_change(TemporalInsertCollisionAsBuilt::paths()[1]));
}
pub proof fn keep_temporal_insert_collision_l3() ensures obl_l3::<TemporalInsertCollisionAsBuilt>() {}
pub proof fn keep_temporal_insert_collision_l4() ensures obl_l4::<TemporalInsertCollisionAsBuilt>() {}

/// strict-cached-guard as built: 03/ledger-state, 08/cypher-* (F-0302, F-0801; guard.py:20-59, query.py:2299-2301):
/// strict mode is a client-side check over a 5 s cache.
pub struct StrictCachedGuardAsBuilt;
impl LedgerPolicy for StrictCachedGuardAsBuilt {
    open spec fn paths() -> Seq<Path> { seq![Path::Commit, Path::Bypass(Guard::CachedClient)] }
}
pub proof fn keep_strict_cached_guard_l1() ensures obl_l1::<StrictCachedGuardAsBuilt>() {}
pub proof fn keep_strict_cached_guard_l2() ensures obl_l2::<StrictCachedGuardAsBuilt>() {}
pub proof fn keep_strict_cached_guard_l3() ensures obl_l3::<StrictCachedGuardAsBuilt>() {}
pub proof fn refute_strict_cached_guard_l4() ensures !obl_l4::<StrictCachedGuardAsBuilt>() {
    assert(!path_guard_authoritative(StrictCachedGuardAsBuilt::paths()[1]));
}

/// bypass-unchecked as built: 03/node-in-one-graph, 03/edge-in-one-graph (F-0301, F-0504, F-1108, F-0503;
/// bulk_loader.py:252-272, temporal.py:623-641, Adjacency.cls:575-603): write paths with no strict check.
pub struct BypassUncheckedAsBuilt;
impl LedgerPolicy for BypassUncheckedAsBuilt {
    open spec fn paths() -> Seq<Path> { seq![Path::Commit, Path::Bypass(Guard::NoGuard)] }
}
pub proof fn keep_bypass_unchecked_l1() ensures obl_l1::<BypassUncheckedAsBuilt>() {}
pub proof fn keep_bypass_unchecked_l2() ensures obl_l2::<BypassUncheckedAsBuilt>() {}
pub proof fn keep_bypass_unchecked_l3() ensures obl_l3::<BypassUncheckedAsBuilt>() {}
pub proof fn refute_bypass_unchecked_l4() ensures !obl_l4::<BypassUncheckedAsBuilt>() {
    assert(!path_guard_authoritative(BypassUncheckedAsBuilt::paths()[1]));
}

// ---------------------------------------------------------------- generic mutants of the canonical instance

/// ledger-control-C1-two-step-record: the record is written in a second step; a stop may come between.
pub struct CtlTwoStepRecord;
impl LedgerPolicy for CtlTwoStepRecord { open spec fn paths() -> Seq<Path> { seq![Path::CommitTwoStep] } }
pub proof fn keep_ctl_two_step_record_l1() ensures obl_l1::<CtlTwoStepRecord>() {}
pub proof fn refute_ctl_two_step_record_l2() ensures !obl_l2::<CtlTwoStepRecord>() {
    assert(!path_records_its_change(CtlTwoStepRecord::paths()[0]));
}
pub proof fn keep_ctl_two_step_record_l3() ensures obl_l3::<CtlTwoStepRecord>() {}
pub proof fn keep_ctl_two_step_record_l4() ensures obl_l4::<CtlTwoStepRecord>() {}

/// ledger-control-C2-overwrite-record: an update rewrites the last record in place.
pub struct CtlOverwriteRecord;
impl LedgerPolicy for CtlOverwriteRecord { open spec fn paths() -> Seq<Path> { seq![Path::Commit, Path::CommitOverwrite] } }
pub proof fn refute_ctl_overwrite_record_l1() ensures !obl_l1::<CtlOverwriteRecord>() {
    assert(!path_appends(CtlOverwriteRecord::paths()[1]));
}
pub proof fn keep_ctl_overwrite_record_l2() ensures obl_l2::<CtlOverwriteRecord>() {}
pub proof fn keep_ctl_overwrite_record_l3() ensures obl_l3::<CtlOverwriteRecord>() {}
pub proof fn keep_ctl_overwrite_record_l4() ensures obl_l4::<CtlOverwriteRecord>() {}

/// ledger-control-C3-ignore-head: a stale expected head is applied.
pub struct CtlIgnoreHead;
impl LedgerPolicy for CtlIgnoreHead { open spec fn paths() -> Seq<Path> { seq![Path::CommitIgnoreHead] } }
pub proof fn keep_ctl_ignore_head_l1() ensures obl_l1::<CtlIgnoreHead>() {}
pub proof fn keep_ctl_ignore_head_l2() ensures obl_l2::<CtlIgnoreHead>() {}
pub proof fn refute_ctl_ignore_head_l3() ensures !obl_l3::<CtlIgnoreHead>() {
    assert(!path_checks_head(CtlIgnoreHead::paths()[0]));
}
pub proof fn keep_ctl_ignore_head_l4() ensures obl_l4::<CtlIgnoreHead>() {}

/// ledger-control-C4-unguarded-bypass: one bypass path checks no strict flag.
pub struct CtlUnguardedBypass;
impl LedgerPolicy for CtlUnguardedBypass { open spec fn paths() -> Seq<Path> { seq![Path::Commit, Path::Bypass(Guard::NoGuard)] } }
pub proof fn keep_ctl_unguarded_bypass_l1() ensures obl_l1::<CtlUnguardedBypass>() {}
pub proof fn keep_ctl_unguarded_bypass_l2() ensures obl_l2::<CtlUnguardedBypass>() {}
pub proof fn keep_ctl_unguarded_bypass_l3() ensures obl_l3::<CtlUnguardedBypass>() {}
pub proof fn refute_ctl_unguarded_bypass_l4() ensures !obl_l4::<CtlUnguardedBypass>() {
    assert(!path_guard_authoritative(CtlUnguardedBypass::paths()[1]));
}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// ledger-sharp-two-records: the reviewed bypass-guarded design reaches two records with live content.
pub proof fn sharp_two_records()
    ensures ({
        let t = run::<LedgerM<StrictCachedGuardReviewed>>(ledger_s0(), seq![LA::Write(0, 1), LA::Write(0, 2)]);
        t is Some && t->0.records.len() == 2 && t->0.content != 0
    })
{
    reveal_with_fuel(run, 4);
}

/// ledger-sharp-strict-refusal: the reviewed design refuses a bypass write while strict.
pub proof fn sharp_strict_refusal()
    ensures ({
        let t = run::<LedgerM<StrictCachedGuardReviewed>>(ledger_s0(), seq![LA::SetStrict(true), LA::Write(1, 1)]);
        t is Some && t->0.refusals > 0 && t->0.strict
    })
{
    reveal_with_fuel(run, 4);
}

} // verus!
