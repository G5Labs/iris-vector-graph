//! M-13 instances: one type per object variant of mechanisms.json (family `epoch`, models/semantics/src/epoch.rs).
//!
//! Reviewed instances discharge the obligation (`EpochObject`) and get `theorem_epoch` with no proof work of their
//! own. As-built variants and the generic mutant have parameters only here; their broken obligation is refuted
//! (`refute_*`), and their `EpochObject` impl exists only under their control feature (src/ctl_epoch.rs).
//! 05/reader-handle (canonical, TemporalWindow.cls) is not modelled by the semantics lane (HD-1401/HD-0903 working
//! answers) and has no instance here.
use vstd::prelude::*;
use crate::exec::*;
use crate::m13_epoch::*;

verus! {

// ---------------------------------------------------------------- reviewed instances (baseline)

/// check-at-start, reviewed: 14/ledger-view; record readers compare the epoch and marker after reading.
pub struct CheckAtStartReviewed;
impl EpochPolicy for CheckAtStartReviewed { open spec fn reader() -> Reader { Reader::CheckStartEnd } }
impl EpochObject for CheckAtStartReviewed {
    proof fn discharge_l1() {}
}

/// no-check, reviewed: 18/snapshot-archive; save_snapshot reads behind an epoch barrier.
pub struct NoCheckReviewed;
impl EpochPolicy for NoCheckReviewed { open spec fn reader() -> Reader { Reader::CheckStartEnd } }
impl EpochObject for NoCheckReviewed {
    proof fn discharge_l1() {}
}

/// The generic theorem, instantiated: each line is the whole proof work of one instance.
pub proof fn laws_check_at_start_reviewed(s0: ES, ls: Seq<EA>, t: ES) requires reached::<EpochM<CheckAtStartReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_epoch::<CheckAtStartReviewed>(s0, ls, t); }
pub proof fn laws_no_check_reviewed(s0: ES, ls: Seq<EA>, t: ES) requires reached::<EpochM<NoCheckReviewed>>(s0, ls, t)
    ensures law_l1(t) { theorem_epoch::<NoCheckReviewed>(s0, ls, t); }

// ---------------------------------------------------------------- as-built variants that depart (parameters only)

/// check-at-start as built (F-1402): 14/ledger-view; record readers check the redaction marker before reading only.
pub struct CheckAtStartAsBuilt;
impl EpochPolicy for CheckAtStartAsBuilt { open spec fn reader() -> Reader { Reader::CheckStart } }
pub proof fn refute_check_at_start_l1() ensures !obl_l1::<CheckAtStartAsBuilt>() {}

/// no-check as built (F-C1801): 18/snapshot-archive; save_snapshot reads table by table with no barrier
/// (snapshot.py:864-1034).
pub struct NoCheckAsBuilt;
impl EpochPolicy for NoCheckAsBuilt { open spec fn reader() -> Reader { Reader::NoCheck } }
pub proof fn refute_no_check_l1() ensures !obl_l1::<NoCheckAsBuilt>() {}

// ---------------------------------------------------------------- generic mutant of the reviewed instance

/// epoch-control-C1-no-end-check: the reader drops the check after reading (the same reader as check-at-start as
/// built, a separate explorer check).
pub struct CtlNoEndCheck;
impl EpochPolicy for CtlNoEndCheck { open spec fn reader() -> Reader { Reader::CheckStart } }
pub proof fn refute_ctl_no_end_check_l1() ensures !obl_l1::<CtlNoEndCheck>() {}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// epoch-sharp-interrupted: a reviewed read reports itself interrupted.
pub proof fn sharp_interrupted()
    ensures ({
        let t = run::<EpochM<CheckAtStartReviewed>>(epoch_s0(), seq![EA::Start, EA::RBegin]);
        t is Some && t->0.r is Done && t->0.r->interrupted
    })
{
    reveal_with_fuel(run, 3);
}

/// epoch-sharp-new-state-read: a reviewed read returns the changed state consistently and uninterrupted.
pub proof fn sharp_new_state_read()
    ensures ({
        let t = run::<EpochM<CheckAtStartReviewed>>(epoch_s0(),
            seq![EA::Start, EA::Change1, EA::Change2, EA::Finish, EA::RBegin, EA::RRead1, EA::RRead2, EA::REnd]);
        t is Some && t->0.r == (Rd::Done { consistent: true, interrupted: false }) && t->0.p1 == 1 && t->0.p2 == 1
    })
{
    reveal_with_fuel(run, 9);
}

} // verus!
