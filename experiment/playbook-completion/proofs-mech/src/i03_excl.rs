//! M-03 instances: one type per object variant of mechanisms.json (family `excl`, models/semantics/src/excl.rs at the
//! semantics lane's commit 50911c4a). Programs are free spec functions so the obligations (`holds_all` over the
//! programs) are decided by computation; each `rules_*` lemma states the truth value of every structural rule for
//! one variant, checked by `compute`.
use vstd::prelude::*;
use crate::exec::*;
use crate::m03_excl::*;

verus! {

/// head-lock-commit: Ledger.Commit takes the head lock around the marker check and the apply (Ledger.cls:440-444, 404). Objects: 11/ledger,10/interned-snapshot.
pub open spec fn progs_head_lock_commit() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::CheckNoMarker(0), Step::MakeLive(0), Step::Unlock], seq![Step::LockX, Step::CheckNoMarker(1), Step::MakeLive(1), Step::Unlock]] }
pub struct HeadLockCommit;
impl ExclPolicy for HeadLockCommit {
    open spec fn progs() -> Seq<Seq<Step>> { progs_head_lock_commit() }
    open spec fn init_live() -> Seq<bool> { seq![false, false] }
}
pub proof fn rules_head_lock_commit()
    ensures
        holds_all(Rule::Discipline, progs_head_lock_commit()),
        holds_all(Rule::GuardedLocked, progs_head_lock_commit()),
        holds_all(Rule::MarkerSet, progs_head_lock_commit()),
        holds_all(Rule::MakeLiveChecked, progs_head_lock_commit()),
        holds_all(Rule::NoClearAny, progs_head_lock_commit()),
        holds_all(Rule::TombChecked, progs_head_lock_commit()),
        holds_all(Rule::MakeLiveInX, progs_head_lock_commit()),
        !holds_all(Rule::NoMarkerUse, progs_head_lock_commit()),
        holds_all(Rule::NoTomb, progs_head_lock_commit()),
{
    assert(holds_all(Rule::Discipline, progs_head_lock_commit())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_head_lock_commit())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_head_lock_commit())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_head_lock_commit())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_head_lock_commit())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_head_lock_commit())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_head_lock_commit())) by (compute);
    assert(!holds_all(Rule::NoMarkerUse, progs_head_lock_commit())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_head_lock_commit())) by (compute);
}
impl ExclObject for HeadLockCommit {
    proof fn discharge_l1() { rules_head_lock_commit(); }
    proof fn discharge_l2() { rules_head_lock_commit(); }
    proof fn discharge_l3() { rules_head_lock_commit(); }
    proof fn discharge_l4() { rules_head_lock_commit(); }
    proof fn discharge_l5() { rules_head_lock_commit(); }
}
pub proof fn laws_head_lock_commit(s0: XS, ls: Seq<nat>, t: XS, q: nat) requires reached::<ExclM<HeadLockCommit>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_excl::<HeadLockCommit>(s0, ls, t, q); }

/// adjacency-no-lock-mark: writers take the shared lock or, after 5 s, set the no-lock mark (Adjacency.cls:55-75). Objects: 04/no-lock-mark.
pub open spec fn progs_adjacency_no_lock_mark() -> Seq<Seq<Step>> { seq![seq![Step::LockSOrMark, Step::Write, Step::Unlock], seq![Step::LockSOrMark, Step::Write, Step::Unlock], seq![Step::LockX, Step::Write, Step::Unlock]] }
pub struct AdjacencyNoLockMark;
impl ExclPolicy for AdjacencyNoLockMark {
    open spec fn progs() -> Seq<Seq<Step>> { progs_adjacency_no_lock_mark() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_adjacency_no_lock_mark()
    ensures
        holds_all(Rule::Discipline, progs_adjacency_no_lock_mark()),
        holds_all(Rule::GuardedLocked, progs_adjacency_no_lock_mark()),
        holds_all(Rule::MarkerSet, progs_adjacency_no_lock_mark()),
        holds_all(Rule::MakeLiveChecked, progs_adjacency_no_lock_mark()),
        holds_all(Rule::NoClearAny, progs_adjacency_no_lock_mark()),
        holds_all(Rule::TombChecked, progs_adjacency_no_lock_mark()),
        holds_all(Rule::MakeLiveInX, progs_adjacency_no_lock_mark()),
        holds_all(Rule::NoMarkerUse, progs_adjacency_no_lock_mark()),
        holds_all(Rule::NoTomb, progs_adjacency_no_lock_mark()),
{
    assert(holds_all(Rule::Discipline, progs_adjacency_no_lock_mark())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_adjacency_no_lock_mark())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_adjacency_no_lock_mark())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_adjacency_no_lock_mark())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_adjacency_no_lock_mark())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_adjacency_no_lock_mark())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_adjacency_no_lock_mark())) by (compute);
    assert(holds_all(Rule::NoMarkerUse, progs_adjacency_no_lock_mark())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_adjacency_no_lock_mark())) by (compute);
}
impl ExclObject for AdjacencyNoLockMark {
    proof fn discharge_l1() { rules_adjacency_no_lock_mark(); }
    proof fn discharge_l2() { rules_adjacency_no_lock_mark(); }
    proof fn discharge_l3() { rules_adjacency_no_lock_mark(); }
    proof fn discharge_l4() { rules_adjacency_no_lock_mark(); }
    proof fn discharge_l5() { rules_adjacency_no_lock_mark(); }
}
pub proof fn laws_adjacency_no_lock_mark(s0: XS, ls: Seq<nat>, t: XS, q: nat) requires reached::<ExclM<AdjacencyNoLockMark>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_excl::<AdjacencyNoLockMark>(s0, ls, t, q); }

/// redaction-marker, reviewed: locked liveness check and marker, Final clears its own marker. Objects: 13/redaction-target,13/redaction-run.
pub open spec fn progs_redaction_marker_reviewed() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::CheckNoMarkerAny, Step::CheckNotLive(0), Step::SetMarker(0), Step::Tomb(0), Step::Unlock, Step::LockX, Step::CheckNotLive(0), Step::ClearOwn, Step::Unlock], seq![Step::LockX, Step::CheckNoMarkerAny, Step::CheckNotLive(1), Step::SetMarker(1), Step::Tomb(1), Step::Unlock, Step::LockX, Step::CheckNotLive(1), Step::ClearOwn, Step::Unlock], seq![Step::LockX, Step::CheckNoMarker(0), Step::MakeLive(0), Step::Unlock]] }
pub struct RedactionMarkerReviewed;
impl ExclPolicy for RedactionMarkerReviewed {
    open spec fn progs() -> Seq<Seq<Step>> { progs_redaction_marker_reviewed() }
    open spec fn init_live() -> Seq<bool> { seq![false, false] }
}
pub proof fn rules_redaction_marker_reviewed()
    ensures
        holds_all(Rule::Discipline, progs_redaction_marker_reviewed()),
        holds_all(Rule::GuardedLocked, progs_redaction_marker_reviewed()),
        holds_all(Rule::MarkerSet, progs_redaction_marker_reviewed()),
        holds_all(Rule::MakeLiveChecked, progs_redaction_marker_reviewed()),
        holds_all(Rule::NoClearAny, progs_redaction_marker_reviewed()),
        holds_all(Rule::TombChecked, progs_redaction_marker_reviewed()),
        holds_all(Rule::MakeLiveInX, progs_redaction_marker_reviewed()),
        !holds_all(Rule::NoMarkerUse, progs_redaction_marker_reviewed()),
        !holds_all(Rule::NoTomb, progs_redaction_marker_reviewed()),
{
    assert(holds_all(Rule::Discipline, progs_redaction_marker_reviewed())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_redaction_marker_reviewed())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_redaction_marker_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_redaction_marker_reviewed())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_redaction_marker_reviewed())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_redaction_marker_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_redaction_marker_reviewed())) by (compute);
    assert(!holds_all(Rule::NoMarkerUse, progs_redaction_marker_reviewed())) by (compute);
    assert(!holds_all(Rule::NoTomb, progs_redaction_marker_reviewed())) by (compute);
}
impl ExclObject for RedactionMarkerReviewed {
    proof fn discharge_l1() { rules_redaction_marker_reviewed(); }
    proof fn discharge_l2() { rules_redaction_marker_reviewed(); }
    proof fn discharge_l3() { rules_redaction_marker_reviewed(); }
    proof fn discharge_l4() { rules_redaction_marker_reviewed(); }
    proof fn discharge_l5() { rules_redaction_marker_reviewed(); }
}
pub proof fn laws_redaction_marker_reviewed(s0: XS, ls: Seq<nat>, t: XS, q: nat) requires reached::<ExclM<RedactionMarkerReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_excl::<RedactionMarkerReviewed>(s0, ls, t, q); }

/// eraser-no-head-lock, reviewed: the eraser takes the head lock (review R11-7). Objects: 12/graph-content.
pub open spec fn progs_eraser_no_head_lock_reviewed() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::Erase(0), Step::Write, Step::Unlock], seq![Step::LockX, Step::CheckNoMarker(0), Step::MakeLive(0), Step::Unlock]] }
pub struct EraserNoHeadLockReviewed;
impl ExclPolicy for EraserNoHeadLockReviewed {
    open spec fn progs() -> Seq<Seq<Step>> { progs_eraser_no_head_lock_reviewed() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_eraser_no_head_lock_reviewed()
    ensures
        holds_all(Rule::Discipline, progs_eraser_no_head_lock_reviewed()),
        holds_all(Rule::GuardedLocked, progs_eraser_no_head_lock_reviewed()),
        holds_all(Rule::MarkerSet, progs_eraser_no_head_lock_reviewed()),
        holds_all(Rule::MakeLiveChecked, progs_eraser_no_head_lock_reviewed()),
        holds_all(Rule::NoClearAny, progs_eraser_no_head_lock_reviewed()),
        holds_all(Rule::TombChecked, progs_eraser_no_head_lock_reviewed()),
        holds_all(Rule::MakeLiveInX, progs_eraser_no_head_lock_reviewed()),
        !holds_all(Rule::NoMarkerUse, progs_eraser_no_head_lock_reviewed()),
        holds_all(Rule::NoTomb, progs_eraser_no_head_lock_reviewed()),
{
    assert(holds_all(Rule::Discipline, progs_eraser_no_head_lock_reviewed())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_eraser_no_head_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_eraser_no_head_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_eraser_no_head_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_eraser_no_head_lock_reviewed())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_eraser_no_head_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_eraser_no_head_lock_reviewed())) by (compute);
    assert(!holds_all(Rule::NoMarkerUse, progs_eraser_no_head_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_eraser_no_head_lock_reviewed())) by (compute);
}
impl ExclObject for EraserNoHeadLockReviewed {
    proof fn discharge_l1() { rules_eraser_no_head_lock_reviewed(); }
    proof fn discharge_l2() { rules_eraser_no_head_lock_reviewed(); }
    proof fn discharge_l3() { rules_eraser_no_head_lock_reviewed(); }
    proof fn discharge_l4() { rules_eraser_no_head_lock_reviewed(); }
    proof fn discharge_l5() { rules_eraser_no_head_lock_reviewed(); }
}
pub proof fn laws_eraser_no_head_lock_reviewed(s0: XS, ls: Seq<nat>, t: XS, q: nat) requires reached::<ExclM<EraserNoHeadLockReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_excl::<EraserNoHeadLockReviewed>(s0, ls, t, q); }

/// adjacency-writer-lock, reviewed: Reweight takes the writer lock too. Objects: 04/graph-writer-lock.
pub open spec fn progs_adjacency_writer_lock_reviewed() -> Seq<Seq<Step>> { seq![seq![Step::LockSOrMark, Step::Write, Step::Unlock], seq![Step::LockSOrMark, Step::Write, Step::Unlock], seq![Step::LockX, Step::Write, Step::Unlock]] }
pub struct AdjacencyWriterLockReviewed;
impl ExclPolicy for AdjacencyWriterLockReviewed {
    open spec fn progs() -> Seq<Seq<Step>> { progs_adjacency_writer_lock_reviewed() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_adjacency_writer_lock_reviewed()
    ensures
        holds_all(Rule::Discipline, progs_adjacency_writer_lock_reviewed()),
        holds_all(Rule::GuardedLocked, progs_adjacency_writer_lock_reviewed()),
        holds_all(Rule::MarkerSet, progs_adjacency_writer_lock_reviewed()),
        holds_all(Rule::MakeLiveChecked, progs_adjacency_writer_lock_reviewed()),
        holds_all(Rule::NoClearAny, progs_adjacency_writer_lock_reviewed()),
        holds_all(Rule::TombChecked, progs_adjacency_writer_lock_reviewed()),
        holds_all(Rule::MakeLiveInX, progs_adjacency_writer_lock_reviewed()),
        holds_all(Rule::NoMarkerUse, progs_adjacency_writer_lock_reviewed()),
        holds_all(Rule::NoTomb, progs_adjacency_writer_lock_reviewed()),
{
    assert(holds_all(Rule::Discipline, progs_adjacency_writer_lock_reviewed())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_adjacency_writer_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_adjacency_writer_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_adjacency_writer_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_adjacency_writer_lock_reviewed())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_adjacency_writer_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_adjacency_writer_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoMarkerUse, progs_adjacency_writer_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_adjacency_writer_lock_reviewed())) by (compute);
}
impl ExclObject for AdjacencyWriterLockReviewed {
    proof fn discharge_l1() { rules_adjacency_writer_lock_reviewed(); }
    proof fn discharge_l2() { rules_adjacency_writer_lock_reviewed(); }
    proof fn discharge_l3() { rules_adjacency_writer_lock_reviewed(); }
    proof fn discharge_l4() { rules_adjacency_writer_lock_reviewed(); }
    proof fn discharge_l5() { rules_adjacency_writer_lock_reviewed(); }
}
pub proof fn laws_adjacency_writer_lock_reviewed(s0: XS, ls: Seq<nat>, t: XS, q: nat) requires reached::<ExclM<AdjacencyWriterLockReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_excl::<AdjacencyWriterLockReviewed>(s0, ls, t, q); }

/// bm25-write-lock, reviewed: Build and Drop take the index write lock. Objects: 07/bm25-index.
pub open spec fn progs_bm25_write_lock_reviewed() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::Write, Step::Unlock], seq![Step::LockX, Step::Write, Step::Write, Step::Unlock]] }
pub struct Bm25WriteLockReviewed;
impl ExclPolicy for Bm25WriteLockReviewed {
    open spec fn progs() -> Seq<Seq<Step>> { progs_bm25_write_lock_reviewed() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_bm25_write_lock_reviewed()
    ensures
        holds_all(Rule::Discipline, progs_bm25_write_lock_reviewed()),
        holds_all(Rule::GuardedLocked, progs_bm25_write_lock_reviewed()),
        holds_all(Rule::MarkerSet, progs_bm25_write_lock_reviewed()),
        holds_all(Rule::MakeLiveChecked, progs_bm25_write_lock_reviewed()),
        holds_all(Rule::NoClearAny, progs_bm25_write_lock_reviewed()),
        holds_all(Rule::TombChecked, progs_bm25_write_lock_reviewed()),
        holds_all(Rule::MakeLiveInX, progs_bm25_write_lock_reviewed()),
        holds_all(Rule::NoMarkerUse, progs_bm25_write_lock_reviewed()),
        holds_all(Rule::NoTomb, progs_bm25_write_lock_reviewed()),
{
    assert(holds_all(Rule::Discipline, progs_bm25_write_lock_reviewed())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_bm25_write_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_bm25_write_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_bm25_write_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_bm25_write_lock_reviewed())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_bm25_write_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_bm25_write_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoMarkerUse, progs_bm25_write_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_bm25_write_lock_reviewed())) by (compute);
}
impl ExclObject for Bm25WriteLockReviewed {
    proof fn discharge_l1() { rules_bm25_write_lock_reviewed(); }
    proof fn discharge_l2() { rules_bm25_write_lock_reviewed(); }
    proof fn discharge_l3() { rules_bm25_write_lock_reviewed(); }
    proof fn discharge_l4() { rules_bm25_write_lock_reviewed(); }
    proof fn discharge_l5() { rules_bm25_write_lock_reviewed(); }
}
pub proof fn laws_bm25_write_lock_reviewed(s0: XS, ls: Seq<nat>, t: XS, q: nat) requires reached::<ExclM<Bm25WriteLockReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_excl::<Bm25WriteLockReviewed>(s0, ls, t, q); }

/// plan-build-lock, reviewed: a deploy's drop waits for the build lock. Objects: 09/compiled-shape.
pub open spec fn progs_plan_build_lock_reviewed() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::Write, Step::Unlock], seq![Step::LockX, Step::Write, Step::Unlock]] }
pub struct PlanBuildLockReviewed;
impl ExclPolicy for PlanBuildLockReviewed {
    open spec fn progs() -> Seq<Seq<Step>> { progs_plan_build_lock_reviewed() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_plan_build_lock_reviewed()
    ensures
        holds_all(Rule::Discipline, progs_plan_build_lock_reviewed()),
        holds_all(Rule::GuardedLocked, progs_plan_build_lock_reviewed()),
        holds_all(Rule::MarkerSet, progs_plan_build_lock_reviewed()),
        holds_all(Rule::MakeLiveChecked, progs_plan_build_lock_reviewed()),
        holds_all(Rule::NoClearAny, progs_plan_build_lock_reviewed()),
        holds_all(Rule::TombChecked, progs_plan_build_lock_reviewed()),
        holds_all(Rule::MakeLiveInX, progs_plan_build_lock_reviewed()),
        holds_all(Rule::NoMarkerUse, progs_plan_build_lock_reviewed()),
        holds_all(Rule::NoTomb, progs_plan_build_lock_reviewed()),
{
    assert(holds_all(Rule::Discipline, progs_plan_build_lock_reviewed())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_plan_build_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_plan_build_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_plan_build_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_plan_build_lock_reviewed())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_plan_build_lock_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_plan_build_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoMarkerUse, progs_plan_build_lock_reviewed())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_plan_build_lock_reviewed())) by (compute);
}
impl ExclObject for PlanBuildLockReviewed {
    proof fn discharge_l1() { rules_plan_build_lock_reviewed(); }
    proof fn discharge_l2() { rules_plan_build_lock_reviewed(); }
    proof fn discharge_l3() { rules_plan_build_lock_reviewed(); }
    proof fn discharge_l4() { rules_plan_build_lock_reviewed(); }
    proof fn discharge_l5() { rules_plan_build_lock_reviewed(); }
}
pub proof fn laws_plan_build_lock_reviewed(s0: XS, ls: Seq<nat>, t: XS, q: nat) requires reached::<ExclM<PlanBuildLockReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_excl::<PlanBuildLockReviewed>(s0, ls, t, q); }

/// mode-switch, reviewed: the mode switch is exclusive, writes shared. Objects: 02/graph-mode.
pub open spec fn progs_mode_switch_reviewed() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::Write, Step::Unlock], seq![Step::LockS, Step::Write, Step::Unlock]] }
pub struct ModeSwitchReviewed;
impl ExclPolicy for ModeSwitchReviewed {
    open spec fn progs() -> Seq<Seq<Step>> { progs_mode_switch_reviewed() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_mode_switch_reviewed()
    ensures
        holds_all(Rule::Discipline, progs_mode_switch_reviewed()),
        holds_all(Rule::GuardedLocked, progs_mode_switch_reviewed()),
        holds_all(Rule::MarkerSet, progs_mode_switch_reviewed()),
        holds_all(Rule::MakeLiveChecked, progs_mode_switch_reviewed()),
        holds_all(Rule::NoClearAny, progs_mode_switch_reviewed()),
        holds_all(Rule::TombChecked, progs_mode_switch_reviewed()),
        holds_all(Rule::MakeLiveInX, progs_mode_switch_reviewed()),
        holds_all(Rule::NoMarkerUse, progs_mode_switch_reviewed()),
        holds_all(Rule::NoTomb, progs_mode_switch_reviewed()),
{
    assert(holds_all(Rule::Discipline, progs_mode_switch_reviewed())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_mode_switch_reviewed())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_mode_switch_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_mode_switch_reviewed())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_mode_switch_reviewed())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_mode_switch_reviewed())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_mode_switch_reviewed())) by (compute);
    assert(holds_all(Rule::NoMarkerUse, progs_mode_switch_reviewed())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_mode_switch_reviewed())) by (compute);
}
impl ExclObject for ModeSwitchReviewed {
    proof fn discharge_l1() { rules_mode_switch_reviewed(); }
    proof fn discharge_l2() { rules_mode_switch_reviewed(); }
    proof fn discharge_l3() { rules_mode_switch_reviewed(); }
    proof fn discharge_l4() { rules_mode_switch_reviewed(); }
    proof fn discharge_l5() { rules_mode_switch_reviewed(); }
}
pub proof fn laws_mode_switch_reviewed(s0: XS, ls: Seq<nat>, t: XS, q: nat) requires reached::<ExclM<ModeSwitchReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l3(t) { theorem_excl::<ModeSwitchReviewed>(s0, ls, t, q); }

/// redaction-marker as built (LedgerRedact.cls:185-211, 302-330, 384-430): the liveness check is unlocked, the marker is set in the first batch under the head lock, Final clears the one global marker whoever set it. Objects: 13/redaction-target; findings F-1302,F-1303,F-C1350.
pub open spec fn progs_redaction_marker() -> Seq<Seq<Step>> { seq![seq![Step::CheckNoMarkerAny, Step::CheckNotLive(0), Step::LockX, Step::SetMarker(0), Step::Tomb(0), Step::Unlock, Step::LockX, Step::CheckNotLive(0), Step::ClearAny, Step::Unlock], seq![Step::CheckNoMarkerAny, Step::CheckNotLive(1), Step::LockX, Step::SetMarker(1), Step::Tomb(1), Step::Unlock, Step::LockX, Step::CheckNotLive(1), Step::ClearAny, Step::Unlock], seq![Step::LockX, Step::CheckNoMarker(0), Step::MakeLive(0), Step::Unlock]] }
pub struct RedactionMarkerAsBuilt;
impl ExclPolicy for RedactionMarkerAsBuilt {
    open spec fn progs() -> Seq<Seq<Step>> { progs_redaction_marker() }
    open spec fn init_live() -> Seq<bool> { seq![false, false] }
}
pub proof fn rules_redaction_marker()
    ensures
        holds_all(Rule::Discipline, progs_redaction_marker()),
        holds_all(Rule::GuardedLocked, progs_redaction_marker()),
        !holds_all(Rule::MarkerSet, progs_redaction_marker()),
        holds_all(Rule::MakeLiveChecked, progs_redaction_marker()),
        !holds_all(Rule::NoClearAny, progs_redaction_marker()),
        !holds_all(Rule::TombChecked, progs_redaction_marker()),
        holds_all(Rule::MakeLiveInX, progs_redaction_marker()),
        !holds_all(Rule::NoMarkerUse, progs_redaction_marker()),
        !holds_all(Rule::NoTomb, progs_redaction_marker()),
{
    assert(holds_all(Rule::Discipline, progs_redaction_marker())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_redaction_marker())) by (compute);
    assert(!holds_all(Rule::MarkerSet, progs_redaction_marker())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_redaction_marker())) by (compute);
    assert(!holds_all(Rule::NoClearAny, progs_redaction_marker())) by (compute);
    assert(!holds_all(Rule::TombChecked, progs_redaction_marker())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_redaction_marker())) by (compute);
    assert(!holds_all(Rule::NoMarkerUse, progs_redaction_marker())) by (compute);
    assert(!holds_all(Rule::NoTomb, progs_redaction_marker())) by (compute);
}
pub proof fn keep_redaction_marker_l1() ensures obl_l1::<RedactionMarkerAsBuilt>() { rules_redaction_marker(); }
pub proof fn keep_redaction_marker_l2() ensures obl_l2::<RedactionMarkerAsBuilt>() { rules_redaction_marker(); }
pub proof fn refute_redaction_marker_l3() ensures !obl_l3::<RedactionMarkerAsBuilt>() { rules_redaction_marker(); }
pub proof fn refute_redaction_marker_l4() ensures !obl_l4::<RedactionMarkerAsBuilt>() { rules_redaction_marker(); }
pub proof fn refute_redaction_marker_l5() ensures !obl_l5::<RedactionMarkerAsBuilt>() { rules_redaction_marker(); }

/// eraser-no-head-lock as built (Eraser.cls:665-678, 809-811): erasure changes the rows and statement maps a commit also writes, without the head lock. Objects: 12/graph-content; findings F-1201,F-1114,F-C1201.
pub open spec fn progs_eraser_no_head_lock() -> Seq<Seq<Step>> { seq![seq![Step::Erase(0), Step::Write], seq![Step::LockX, Step::CheckNoMarker(0), Step::MakeLive(0), Step::Unlock]] }
pub struct EraserNoHeadLockAsBuilt;
impl ExclPolicy for EraserNoHeadLockAsBuilt {
    open spec fn progs() -> Seq<Seq<Step>> { progs_eraser_no_head_lock() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_eraser_no_head_lock()
    ensures
        holds_all(Rule::Discipline, progs_eraser_no_head_lock()),
        !holds_all(Rule::GuardedLocked, progs_eraser_no_head_lock()),
        holds_all(Rule::MarkerSet, progs_eraser_no_head_lock()),
        holds_all(Rule::MakeLiveChecked, progs_eraser_no_head_lock()),
        holds_all(Rule::NoClearAny, progs_eraser_no_head_lock()),
        holds_all(Rule::TombChecked, progs_eraser_no_head_lock()),
        holds_all(Rule::MakeLiveInX, progs_eraser_no_head_lock()),
        !holds_all(Rule::NoMarkerUse, progs_eraser_no_head_lock()),
        holds_all(Rule::NoTomb, progs_eraser_no_head_lock()),
{
    assert(holds_all(Rule::Discipline, progs_eraser_no_head_lock())) by (compute);
    assert(!holds_all(Rule::GuardedLocked, progs_eraser_no_head_lock())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_eraser_no_head_lock())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_eraser_no_head_lock())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_eraser_no_head_lock())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_eraser_no_head_lock())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_eraser_no_head_lock())) by (compute);
    assert(!holds_all(Rule::NoMarkerUse, progs_eraser_no_head_lock())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_eraser_no_head_lock())) by (compute);
}
pub proof fn keep_eraser_no_head_lock_l1() ensures obl_l1::<EraserNoHeadLockAsBuilt>() { rules_eraser_no_head_lock(); }
pub proof fn refute_eraser_no_head_lock_l2() ensures !obl_l2::<EraserNoHeadLockAsBuilt>() { rules_eraser_no_head_lock(); }
pub proof fn keep_eraser_no_head_lock_l3() ensures obl_l3::<EraserNoHeadLockAsBuilt>() { rules_eraser_no_head_lock(); }
pub proof fn keep_eraser_no_head_lock_l4() ensures obl_l4::<EraserNoHeadLockAsBuilt>() { rules_eraser_no_head_lock(); }
pub proof fn keep_eraser_no_head_lock_l5() ensures obl_l5::<EraserNoHeadLockAsBuilt>() { rules_eraser_no_head_lock(); }

/// adjacency-writer-lock as built (Adjacency.cls:61-75): Reweight writes without the writer lock. Objects: 04/graph-writer-lock; findings F-0407.
pub open spec fn progs_adjacency_writer_lock() -> Seq<Seq<Step>> { seq![seq![Step::LockSOrMark, Step::Write, Step::Unlock], seq![Step::Write], seq![Step::LockX, Step::Write, Step::Unlock]] }
pub struct AdjacencyWriterLockAsBuilt;
impl ExclPolicy for AdjacencyWriterLockAsBuilt {
    open spec fn progs() -> Seq<Seq<Step>> { progs_adjacency_writer_lock() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_adjacency_writer_lock()
    ensures
        holds_all(Rule::Discipline, progs_adjacency_writer_lock()),
        !holds_all(Rule::GuardedLocked, progs_adjacency_writer_lock()),
        holds_all(Rule::MarkerSet, progs_adjacency_writer_lock()),
        holds_all(Rule::MakeLiveChecked, progs_adjacency_writer_lock()),
        holds_all(Rule::NoClearAny, progs_adjacency_writer_lock()),
        holds_all(Rule::TombChecked, progs_adjacency_writer_lock()),
        holds_all(Rule::MakeLiveInX, progs_adjacency_writer_lock()),
        holds_all(Rule::NoMarkerUse, progs_adjacency_writer_lock()),
        holds_all(Rule::NoTomb, progs_adjacency_writer_lock()),
{
    assert(holds_all(Rule::Discipline, progs_adjacency_writer_lock())) by (compute);
    assert(!holds_all(Rule::GuardedLocked, progs_adjacency_writer_lock())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_adjacency_writer_lock())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_adjacency_writer_lock())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_adjacency_writer_lock())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_adjacency_writer_lock())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_adjacency_writer_lock())) by (compute);
    assert(holds_all(Rule::NoMarkerUse, progs_adjacency_writer_lock())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_adjacency_writer_lock())) by (compute);
}
pub proof fn keep_adjacency_writer_lock_l1() ensures obl_l1::<AdjacencyWriterLockAsBuilt>() { rules_adjacency_writer_lock(); }
pub proof fn refute_adjacency_writer_lock_l2() ensures !obl_l2::<AdjacencyWriterLockAsBuilt>() { rules_adjacency_writer_lock(); }
pub proof fn keep_adjacency_writer_lock_l3() ensures obl_l3::<AdjacencyWriterLockAsBuilt>() { rules_adjacency_writer_lock(); }
pub proof fn keep_adjacency_writer_lock_l4() ensures obl_l4::<AdjacencyWriterLockAsBuilt>() { rules_adjacency_writer_lock(); }
pub proof fn keep_adjacency_writer_lock_l5() ensures obl_l5::<AdjacencyWriterLockAsBuilt>() { rules_adjacency_writer_lock(); }

/// bm25-write-lock as built (BM25Index.cls:97-175, 403-410, 587-591): Insert takes the index write lock, Build and Drop write without it. Objects: 07/bm25-index; findings F-0701.
pub open spec fn progs_bm25_write_lock() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::Write, Step::Unlock], seq![Step::Write, Step::Write]] }
pub struct Bm25WriteLockAsBuilt;
impl ExclPolicy for Bm25WriteLockAsBuilt {
    open spec fn progs() -> Seq<Seq<Step>> { progs_bm25_write_lock() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_bm25_write_lock()
    ensures
        holds_all(Rule::Discipline, progs_bm25_write_lock()),
        !holds_all(Rule::GuardedLocked, progs_bm25_write_lock()),
        holds_all(Rule::MarkerSet, progs_bm25_write_lock()),
        holds_all(Rule::MakeLiveChecked, progs_bm25_write_lock()),
        holds_all(Rule::NoClearAny, progs_bm25_write_lock()),
        holds_all(Rule::TombChecked, progs_bm25_write_lock()),
        holds_all(Rule::MakeLiveInX, progs_bm25_write_lock()),
        holds_all(Rule::NoMarkerUse, progs_bm25_write_lock()),
        holds_all(Rule::NoTomb, progs_bm25_write_lock()),
{
    assert(holds_all(Rule::Discipline, progs_bm25_write_lock())) by (compute);
    assert(!holds_all(Rule::GuardedLocked, progs_bm25_write_lock())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_bm25_write_lock())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_bm25_write_lock())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_bm25_write_lock())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_bm25_write_lock())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_bm25_write_lock())) by (compute);
    assert(holds_all(Rule::NoMarkerUse, progs_bm25_write_lock())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_bm25_write_lock())) by (compute);
}
pub proof fn keep_bm25_write_lock_l1() ensures obl_l1::<Bm25WriteLockAsBuilt>() { rules_bm25_write_lock(); }
pub proof fn refute_bm25_write_lock_l2() ensures !obl_l2::<Bm25WriteLockAsBuilt>() { rules_bm25_write_lock(); }
pub proof fn keep_bm25_write_lock_l3() ensures obl_l3::<Bm25WriteLockAsBuilt>() { rules_bm25_write_lock(); }
pub proof fn keep_bm25_write_lock_l4() ensures obl_l4::<Bm25WriteLockAsBuilt>() { rules_bm25_write_lock(); }
pub proof fn keep_bm25_write_lock_l5() ensures obl_l5::<Bm25WriteLockAsBuilt>() { rules_bm25_write_lock(); }

/// plan-build-lock as built (Gen.cls:166, 225-230): a deploy's drop does not wait for the build lock. Objects: 09/compiled-shape; findings F-0905.
pub open spec fn progs_plan_build_lock() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::Write, Step::Unlock], seq![Step::Write]] }
pub struct PlanBuildLockAsBuilt;
impl ExclPolicy for PlanBuildLockAsBuilt {
    open spec fn progs() -> Seq<Seq<Step>> { progs_plan_build_lock() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_plan_build_lock()
    ensures
        holds_all(Rule::Discipline, progs_plan_build_lock()),
        !holds_all(Rule::GuardedLocked, progs_plan_build_lock()),
        holds_all(Rule::MarkerSet, progs_plan_build_lock()),
        holds_all(Rule::MakeLiveChecked, progs_plan_build_lock()),
        holds_all(Rule::NoClearAny, progs_plan_build_lock()),
        holds_all(Rule::TombChecked, progs_plan_build_lock()),
        holds_all(Rule::MakeLiveInX, progs_plan_build_lock()),
        holds_all(Rule::NoMarkerUse, progs_plan_build_lock()),
        holds_all(Rule::NoTomb, progs_plan_build_lock()),
{
    assert(holds_all(Rule::Discipline, progs_plan_build_lock())) by (compute);
    assert(!holds_all(Rule::GuardedLocked, progs_plan_build_lock())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_plan_build_lock())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_plan_build_lock())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_plan_build_lock())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_plan_build_lock())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_plan_build_lock())) by (compute);
    assert(holds_all(Rule::NoMarkerUse, progs_plan_build_lock())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_plan_build_lock())) by (compute);
}
pub proof fn keep_plan_build_lock_l1() ensures obl_l1::<PlanBuildLockAsBuilt>() { rules_plan_build_lock(); }
pub proof fn refute_plan_build_lock_l2() ensures !obl_l2::<PlanBuildLockAsBuilt>() { rules_plan_build_lock(); }
pub proof fn keep_plan_build_lock_l3() ensures obl_l3::<PlanBuildLockAsBuilt>() { rules_plan_build_lock(); }
pub proof fn keep_plan_build_lock_l4() ensures obl_l4::<PlanBuildLockAsBuilt>() { rules_plan_build_lock(); }
pub proof fn keep_plan_build_lock_l5() ensures obl_l5::<PlanBuildLockAsBuilt>() { rules_plan_build_lock(); }

/// mode-switch as built (GraphMode.cls:26-61): turning the mode off races a write that adds a parallel edge. Objects: 02/graph-mode; findings F-0207.
pub open spec fn progs_mode_switch() -> Seq<Seq<Step>> { seq![seq![Step::Write], seq![Step::Write]] }
pub struct ModeSwitchAsBuilt;
impl ExclPolicy for ModeSwitchAsBuilt {
    open spec fn progs() -> Seq<Seq<Step>> { progs_mode_switch() }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}
pub proof fn rules_mode_switch()
    ensures
        holds_all(Rule::Discipline, progs_mode_switch()),
        !holds_all(Rule::GuardedLocked, progs_mode_switch()),
        holds_all(Rule::MarkerSet, progs_mode_switch()),
        holds_all(Rule::MakeLiveChecked, progs_mode_switch()),
        holds_all(Rule::NoClearAny, progs_mode_switch()),
        holds_all(Rule::TombChecked, progs_mode_switch()),
        holds_all(Rule::MakeLiveInX, progs_mode_switch()),
        holds_all(Rule::NoMarkerUse, progs_mode_switch()),
        holds_all(Rule::NoTomb, progs_mode_switch()),
{
    assert(holds_all(Rule::Discipline, progs_mode_switch())) by (compute);
    assert(!holds_all(Rule::GuardedLocked, progs_mode_switch())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_mode_switch())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_mode_switch())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_mode_switch())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_mode_switch())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_mode_switch())) by (compute);
    assert(holds_all(Rule::NoMarkerUse, progs_mode_switch())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_mode_switch())) by (compute);
}
pub proof fn keep_mode_switch_l1() ensures obl_l1::<ModeSwitchAsBuilt>() { rules_mode_switch(); }
pub proof fn refute_mode_switch_l2() ensures !obl_l2::<ModeSwitchAsBuilt>() { rules_mode_switch(); }
pub proof fn keep_mode_switch_l3() ensures obl_l3::<ModeSwitchAsBuilt>() { rules_mode_switch(); }
pub proof fn keep_mode_switch_l4() ensures obl_l4::<ModeSwitchAsBuilt>() { rules_mode_switch(); }
pub proof fn keep_mode_switch_l5() ensures obl_l5::<ModeSwitchAsBuilt>() { rules_mode_switch(); }

/// excl-control-C1-lock-admits-two: a lock that ignores other holders. Objects: 13/redaction-target,13/redaction-run.
pub open spec fn progs_ctl_lock_admits_two() -> Seq<Seq<Step>> { seq![seq![Step::LockXBad, Step::Write, Step::Unlock], seq![Step::LockX, Step::Write, Step::Unlock]] }
pub struct CtlLockAdmitsTwo;
impl ExclPolicy for CtlLockAdmitsTwo {
    open spec fn progs() -> Seq<Seq<Step>> { progs_ctl_lock_admits_two() }
    open spec fn init_live() -> Seq<bool> { seq![false, false] }
}
pub proof fn rules_ctl_lock_admits_two()
    ensures
        !holds_all(Rule::Discipline, progs_ctl_lock_admits_two()),
        holds_all(Rule::GuardedLocked, progs_ctl_lock_admits_two()),
        holds_all(Rule::MarkerSet, progs_ctl_lock_admits_two()),
        holds_all(Rule::MakeLiveChecked, progs_ctl_lock_admits_two()),
        holds_all(Rule::NoClearAny, progs_ctl_lock_admits_two()),
        holds_all(Rule::TombChecked, progs_ctl_lock_admits_two()),
        holds_all(Rule::MakeLiveInX, progs_ctl_lock_admits_two()),
        holds_all(Rule::NoMarkerUse, progs_ctl_lock_admits_two()),
        holds_all(Rule::NoTomb, progs_ctl_lock_admits_two()),
{
    assert(!holds_all(Rule::Discipline, progs_ctl_lock_admits_two())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_ctl_lock_admits_two())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_ctl_lock_admits_two())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_ctl_lock_admits_two())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_ctl_lock_admits_two())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_ctl_lock_admits_two())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_ctl_lock_admits_two())) by (compute);
    assert(holds_all(Rule::NoMarkerUse, progs_ctl_lock_admits_two())) by (compute);
    assert(holds_all(Rule::NoTomb, progs_ctl_lock_admits_two())) by (compute);
}
pub proof fn refute_ctl_lock_admits_two_l1() ensures !obl_l1::<CtlLockAdmitsTwo>() { rules_ctl_lock_admits_two(); }
pub proof fn keep_ctl_lock_admits_two_l2() ensures obl_l2::<CtlLockAdmitsTwo>() { rules_ctl_lock_admits_two(); }
pub proof fn keep_ctl_lock_admits_two_l3() ensures obl_l3::<CtlLockAdmitsTwo>() { rules_ctl_lock_admits_two(); }
pub proof fn keep_ctl_lock_admits_two_l4() ensures obl_l4::<CtlLockAdmitsTwo>() { rules_ctl_lock_admits_two(); }
pub proof fn keep_ctl_lock_admits_two_l5() ensures obl_l5::<CtlLockAdmitsTwo>() { rules_ctl_lock_admits_two(); }

/// excl-control-C2-writer-without-lock: a commit checks the marker but takes no lock. Objects: 13/redaction-target,13/redaction-run.
pub open spec fn progs_ctl_writer_without_lock() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::CheckNoMarkerAny, Step::CheckNotLive(0), Step::SetMarker(0), Step::Tomb(0), Step::Unlock, Step::LockX, Step::CheckNotLive(0), Step::ClearOwn, Step::Unlock], seq![Step::CheckNoMarker(0), Step::MakeLive(0)]] }
pub struct CtlWriterWithoutLock;
impl ExclPolicy for CtlWriterWithoutLock {
    open spec fn progs() -> Seq<Seq<Step>> { progs_ctl_writer_without_lock() }
    open spec fn init_live() -> Seq<bool> { seq![false, false] }
}
pub proof fn rules_ctl_writer_without_lock()
    ensures
        holds_all(Rule::Discipline, progs_ctl_writer_without_lock()),
        !holds_all(Rule::GuardedLocked, progs_ctl_writer_without_lock()),
        holds_all(Rule::MarkerSet, progs_ctl_writer_without_lock()),
        !holds_all(Rule::MakeLiveChecked, progs_ctl_writer_without_lock()),
        holds_all(Rule::NoClearAny, progs_ctl_writer_without_lock()),
        holds_all(Rule::TombChecked, progs_ctl_writer_without_lock()),
        !holds_all(Rule::MakeLiveInX, progs_ctl_writer_without_lock()),
        !holds_all(Rule::NoMarkerUse, progs_ctl_writer_without_lock()),
        !holds_all(Rule::NoTomb, progs_ctl_writer_without_lock()),
{
    assert(holds_all(Rule::Discipline, progs_ctl_writer_without_lock())) by (compute);
    assert(!holds_all(Rule::GuardedLocked, progs_ctl_writer_without_lock())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_ctl_writer_without_lock())) by (compute);
    assert(!holds_all(Rule::MakeLiveChecked, progs_ctl_writer_without_lock())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_ctl_writer_without_lock())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_ctl_writer_without_lock())) by (compute);
    assert(!holds_all(Rule::MakeLiveInX, progs_ctl_writer_without_lock())) by (compute);
    assert(!holds_all(Rule::NoMarkerUse, progs_ctl_writer_without_lock())) by (compute);
    assert(!holds_all(Rule::NoTomb, progs_ctl_writer_without_lock())) by (compute);
}
pub proof fn keep_ctl_writer_without_lock_l1() ensures obl_l1::<CtlWriterWithoutLock>() { rules_ctl_writer_without_lock(); }
pub proof fn refute_ctl_writer_without_lock_l2() ensures !obl_l2::<CtlWriterWithoutLock>() { rules_ctl_writer_without_lock(); }
pub proof fn refute_ctl_writer_without_lock_l3() ensures !obl_l3::<CtlWriterWithoutLock>() { rules_ctl_writer_without_lock(); }
pub proof fn keep_ctl_writer_without_lock_l4() ensures obl_l4::<CtlWriterWithoutLock>() { rules_ctl_writer_without_lock(); }
pub proof fn refute_ctl_writer_without_lock_l5() ensures !obl_l5::<CtlWriterWithoutLock>() { rules_ctl_writer_without_lock(); }

/// excl-control-C3-check-before-lock: the liveness check runs before the lock. Objects: 13/redaction-target,13/redaction-run.
pub open spec fn progs_ctl_check_before_lock() -> Seq<Seq<Step>> { seq![seq![Step::CheckNotLive(0), Step::LockX, Step::CheckNoMarkerAny, Step::SetMarker(0), Step::Tomb(0), Step::Unlock, Step::LockX, Step::CheckNotLive(0), Step::ClearOwn, Step::Unlock], seq![Step::LockX, Step::CheckNoMarker(0), Step::MakeLive(0), Step::Unlock]] }
pub struct CtlCheckBeforeLock;
impl ExclPolicy for CtlCheckBeforeLock {
    open spec fn progs() -> Seq<Seq<Step>> { progs_ctl_check_before_lock() }
    open spec fn init_live() -> Seq<bool> { seq![false, false] }
}
pub proof fn rules_ctl_check_before_lock()
    ensures
        holds_all(Rule::Discipline, progs_ctl_check_before_lock()),
        holds_all(Rule::GuardedLocked, progs_ctl_check_before_lock()),
        !holds_all(Rule::MarkerSet, progs_ctl_check_before_lock()),
        holds_all(Rule::MakeLiveChecked, progs_ctl_check_before_lock()),
        holds_all(Rule::NoClearAny, progs_ctl_check_before_lock()),
        !holds_all(Rule::TombChecked, progs_ctl_check_before_lock()),
        holds_all(Rule::MakeLiveInX, progs_ctl_check_before_lock()),
        !holds_all(Rule::NoMarkerUse, progs_ctl_check_before_lock()),
        !holds_all(Rule::NoTomb, progs_ctl_check_before_lock()),
{
    assert(holds_all(Rule::Discipline, progs_ctl_check_before_lock())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_ctl_check_before_lock())) by (compute);
    assert(!holds_all(Rule::MarkerSet, progs_ctl_check_before_lock())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_ctl_check_before_lock())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_ctl_check_before_lock())) by (compute);
    assert(!holds_all(Rule::TombChecked, progs_ctl_check_before_lock())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_ctl_check_before_lock())) by (compute);
    assert(!holds_all(Rule::NoMarkerUse, progs_ctl_check_before_lock())) by (compute);
    assert(!holds_all(Rule::NoTomb, progs_ctl_check_before_lock())) by (compute);
}
pub proof fn keep_ctl_check_before_lock_l1() ensures obl_l1::<CtlCheckBeforeLock>() { rules_ctl_check_before_lock(); }
pub proof fn keep_ctl_check_before_lock_l2() ensures obl_l2::<CtlCheckBeforeLock>() { rules_ctl_check_before_lock(); }
pub proof fn refute_ctl_check_before_lock_l3() ensures !obl_l3::<CtlCheckBeforeLock>() { rules_ctl_check_before_lock(); }
pub proof fn keep_ctl_check_before_lock_l4() ensures obl_l4::<CtlCheckBeforeLock>() { rules_ctl_check_before_lock(); }
pub proof fn refute_ctl_check_before_lock_l5() ensures !obl_l5::<CtlCheckBeforeLock>() { rules_ctl_check_before_lock(); }

/// excl-control-C4-clear-any: Final clears whatever marker exists. Objects: 13/redaction-target,13/redaction-run.
pub open spec fn progs_ctl_clear_any() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::CheckNoMarkerAny, Step::CheckNotLive(0), Step::SetMarker(0), Step::Tomb(0), Step::Unlock, Step::LockX, Step::ClearAny, Step::Unlock], seq![Step::LockX, Step::CheckNotLive(1), Step::Tomb(1), Step::Unlock, Step::LockX, Step::ClearAny, Step::Unlock]] }
pub struct CtlClearAny;
impl ExclPolicy for CtlClearAny {
    open spec fn progs() -> Seq<Seq<Step>> { progs_ctl_clear_any() }
    open spec fn init_live() -> Seq<bool> { seq![false, false] }
}
pub proof fn rules_ctl_clear_any()
    ensures
        holds_all(Rule::Discipline, progs_ctl_clear_any()),
        holds_all(Rule::GuardedLocked, progs_ctl_clear_any()),
        holds_all(Rule::MarkerSet, progs_ctl_clear_any()),
        holds_all(Rule::MakeLiveChecked, progs_ctl_clear_any()),
        !holds_all(Rule::NoClearAny, progs_ctl_clear_any()),
        holds_all(Rule::TombChecked, progs_ctl_clear_any()),
        holds_all(Rule::MakeLiveInX, progs_ctl_clear_any()),
        !holds_all(Rule::NoMarkerUse, progs_ctl_clear_any()),
        !holds_all(Rule::NoTomb, progs_ctl_clear_any()),
{
    assert(holds_all(Rule::Discipline, progs_ctl_clear_any())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_ctl_clear_any())) by (compute);
    assert(holds_all(Rule::MarkerSet, progs_ctl_clear_any())) by (compute);
    assert(holds_all(Rule::MakeLiveChecked, progs_ctl_clear_any())) by (compute);
    assert(!holds_all(Rule::NoClearAny, progs_ctl_clear_any())) by (compute);
    assert(holds_all(Rule::TombChecked, progs_ctl_clear_any())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_ctl_clear_any())) by (compute);
    assert(!holds_all(Rule::NoMarkerUse, progs_ctl_clear_any())) by (compute);
    assert(!holds_all(Rule::NoTomb, progs_ctl_clear_any())) by (compute);
}
pub proof fn keep_ctl_clear_any_l1() ensures obl_l1::<CtlClearAny>() { rules_ctl_clear_any(); }
pub proof fn keep_ctl_clear_any_l2() ensures obl_l2::<CtlClearAny>() { rules_ctl_clear_any(); }
pub proof fn keep_ctl_clear_any_l3() ensures obl_l3::<CtlClearAny>() { rules_ctl_clear_any(); }
pub proof fn refute_ctl_clear_any_l4() ensures !obl_l4::<CtlClearAny>() { rules_ctl_clear_any(); }
pub proof fn keep_ctl_clear_any_l5() ensures obl_l5::<CtlClearAny>() { rules_ctl_clear_any(); }

/// excl-control-C5-tomb-without-check: tombstones without a liveness check. Objects: 13/redaction-target,13/redaction-run.
pub open spec fn progs_ctl_tomb_without_check() -> Seq<Seq<Step>> { seq![seq![Step::LockX, Step::SetMarker(0), Step::Tomb(0), Step::Unlock], seq![Step::LockX, Step::MakeLive(0), Step::Unlock]] }
pub struct CtlTombWithoutCheck;
impl ExclPolicy for CtlTombWithoutCheck {
    open spec fn progs() -> Seq<Seq<Step>> { progs_ctl_tomb_without_check() }
    open spec fn init_live() -> Seq<bool> { seq![false, false] }
}
pub proof fn rules_ctl_tomb_without_check()
    ensures
        holds_all(Rule::Discipline, progs_ctl_tomb_without_check()),
        holds_all(Rule::GuardedLocked, progs_ctl_tomb_without_check()),
        !holds_all(Rule::MarkerSet, progs_ctl_tomb_without_check()),
        !holds_all(Rule::MakeLiveChecked, progs_ctl_tomb_without_check()),
        holds_all(Rule::NoClearAny, progs_ctl_tomb_without_check()),
        !holds_all(Rule::TombChecked, progs_ctl_tomb_without_check()),
        holds_all(Rule::MakeLiveInX, progs_ctl_tomb_without_check()),
        !holds_all(Rule::NoMarkerUse, progs_ctl_tomb_without_check()),
        !holds_all(Rule::NoTomb, progs_ctl_tomb_without_check()),
{
    assert(holds_all(Rule::Discipline, progs_ctl_tomb_without_check())) by (compute);
    assert(holds_all(Rule::GuardedLocked, progs_ctl_tomb_without_check())) by (compute);
    assert(!holds_all(Rule::MarkerSet, progs_ctl_tomb_without_check())) by (compute);
    assert(!holds_all(Rule::MakeLiveChecked, progs_ctl_tomb_without_check())) by (compute);
    assert(holds_all(Rule::NoClearAny, progs_ctl_tomb_without_check())) by (compute);
    assert(!holds_all(Rule::TombChecked, progs_ctl_tomb_without_check())) by (compute);
    assert(holds_all(Rule::MakeLiveInX, progs_ctl_tomb_without_check())) by (compute);
    assert(!holds_all(Rule::NoMarkerUse, progs_ctl_tomb_without_check())) by (compute);
    assert(!holds_all(Rule::NoTomb, progs_ctl_tomb_without_check())) by (compute);
}
pub proof fn keep_ctl_tomb_without_check_l1() ensures obl_l1::<CtlTombWithoutCheck>() { rules_ctl_tomb_without_check(); }
pub proof fn keep_ctl_tomb_without_check_l2() ensures obl_l2::<CtlTombWithoutCheck>() { rules_ctl_tomb_without_check(); }
pub proof fn refute_ctl_tomb_without_check_l3() ensures !obl_l3::<CtlTombWithoutCheck>() { rules_ctl_tomb_without_check(); }
pub proof fn keep_ctl_tomb_without_check_l4() ensures obl_l4::<CtlTombWithoutCheck>() { rules_ctl_tomb_without_check(); }
pub proof fn refute_ctl_tomb_without_check_l5() ensures !obl_l5::<CtlTombWithoutCheck>() { rules_ctl_tomb_without_check(); }

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// excl-sharp-redaction-finishes: target 0 tombstoned, not live, unmarked, its run done.
pub proof fn sharp_redaction_finishes()
    ensures ({
        let r = run::<ExclM<RedactionMarkerReviewed>>(x_s0::<RedactionMarkerReviewed>(), seq![0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 0nat]);
        r is Some && ({ let t = r->0; t.tomb[0] && !t.live[0] && t.marker is None && t.pc[0] == Pc::Done })
    })
{
    reveal_with_fuel(run, 11);
    let s0 = x_s0::<RedactionMarkerReviewed>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<RedactionMarkerReviewed>(s0, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s0, 0) is Some);
    let s2 = x_step::<RedactionMarkerReviewed>(s1, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s1, 0) is Some);
    let s3 = x_step::<RedactionMarkerReviewed>(s2, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s2, 0) is Some);
    let s4 = x_step::<RedactionMarkerReviewed>(s3, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s3, 0) is Some);
    let s5 = x_step::<RedactionMarkerReviewed>(s4, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s4, 0) is Some);
    let s6 = x_step::<RedactionMarkerReviewed>(s5, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s5, 0) is Some);
    let s7 = x_step::<RedactionMarkerReviewed>(s6, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s6, 0) is Some);
    let s8 = x_step::<RedactionMarkerReviewed>(s7, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s7, 0) is Some);
    let s9 = x_step::<RedactionMarkerReviewed>(s8, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s8, 0) is Some);
    let s10 = x_step::<RedactionMarkerReviewed>(s9, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s9, 0) is Some);
    assert(run::<ExclM<RedactionMarkerReviewed>>(x_s0::<RedactionMarkerReviewed>(), seq![0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 0nat]) == Some(s10));
}

/// excl-sharp-commit-refused-by-marker: the commit is refused by the marker.
pub proof fn sharp_commit_refused_by_marker()
    ensures ({
        let r = run::<ExclM<RedactionMarkerReviewed>>(x_s0::<RedactionMarkerReviewed>(), seq![0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 2nat, 2nat]);
        r is Some && ({ let t = r->0; t.pc[2] == Pc::Refused })
    })
{
    reveal_with_fuel(run, 9);
    let s0 = x_s0::<RedactionMarkerReviewed>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<RedactionMarkerReviewed>(s0, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s0, 0) is Some);
    let s2 = x_step::<RedactionMarkerReviewed>(s1, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s1, 0) is Some);
    let s3 = x_step::<RedactionMarkerReviewed>(s2, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s2, 0) is Some);
    let s4 = x_step::<RedactionMarkerReviewed>(s3, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s3, 0) is Some);
    let s5 = x_step::<RedactionMarkerReviewed>(s4, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s4, 0) is Some);
    let s6 = x_step::<RedactionMarkerReviewed>(s5, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s5, 0) is Some);
    let s7 = x_step::<RedactionMarkerReviewed>(s6, 2)->0;
    assert(x_step::<RedactionMarkerReviewed>(s6, 2) is Some);
    let s8 = x_step::<RedactionMarkerReviewed>(s7, 2)->0;
    assert(x_step::<RedactionMarkerReviewed>(s7, 2) is Some);
    assert(run::<ExclM<RedactionMarkerReviewed>>(x_s0::<RedactionMarkerReviewed>(), seq![0nat, 0nat, 0nat, 0nat, 0nat, 0nat, 2nat, 2nat]) == Some(s8));
}

/// excl-sharp-run-refused-live: a redaction is refused because its target is live.
pub proof fn sharp_run_refused_live()
    ensures ({
        let r = run::<ExclM<RedactionMarkerReviewed>>(x_s0::<RedactionMarkerReviewed>(), seq![2nat, 2nat, 2nat, 2nat, 0nat, 0nat, 0nat]);
        r is Some && ({ let t = r->0; t.pc[0] == Pc::Refused && t.live[0] })
    })
{
    reveal_with_fuel(run, 8);
    let s0 = x_s0::<RedactionMarkerReviewed>();
    assert(s0.pc[0] == Pc::At(0) && s0.pc[1] == Pc::At(0));
    let s1 = x_step::<RedactionMarkerReviewed>(s0, 2)->0;
    assert(x_step::<RedactionMarkerReviewed>(s0, 2) is Some);
    let s2 = x_step::<RedactionMarkerReviewed>(s1, 2)->0;
    assert(x_step::<RedactionMarkerReviewed>(s1, 2) is Some);
    let s3 = x_step::<RedactionMarkerReviewed>(s2, 2)->0;
    assert(x_step::<RedactionMarkerReviewed>(s2, 2) is Some);
    let s4 = x_step::<RedactionMarkerReviewed>(s3, 2)->0;
    assert(x_step::<RedactionMarkerReviewed>(s3, 2) is Some);
    let s5 = x_step::<RedactionMarkerReviewed>(s4, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s4, 0) is Some);
    let s6 = x_step::<RedactionMarkerReviewed>(s5, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s5, 0) is Some);
    let s7 = x_step::<RedactionMarkerReviewed>(s6, 0)->0;
    assert(x_step::<RedactionMarkerReviewed>(s6, 0) is Some);
    assert(run::<ExclM<RedactionMarkerReviewed>>(x_s0::<RedactionMarkerReviewed>(), seq![2nat, 2nat, 2nat, 2nat, 0nat, 0nat, 0nat]) == Some(s7));
}

} // verus!
