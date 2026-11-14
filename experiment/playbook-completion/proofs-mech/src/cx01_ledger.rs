//! M-01 counterexamples: for each departing variant, a run of the generic machine with that variant's parameters
//! from the initial state to a violation of the law it breaks (the explorer's shortest counterexample, restated).
//! Always compiled: the baseline proves them.
use vstd::prelude::*;
use crate::exec::*;
use crate::m01_ledger::*;
use crate::i01_ledger::*;

verus! {

/// F-1105: commit a node, then a delete aimed at another scope is recorded: replay deletes what the store kept.
pub proof fn cx_node_delete_named_only_l2()
    ensures ({
        let t = run::<LedgerM<NodeDeleteNamedOnlyAsBuilt>>(ledger_s0(), seq![LA::Write(0, 1), LA::Write(1, 0)]);
        t is Some && !law_l2(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// F-0511: an insert-mode op that collides is recorded although it changed nothing.
pub proof fn cx_temporal_insert_collision_l2()
    ensures ({
        let t = run::<LedgerM<TemporalInsertCollisionAsBuilt>>(ledger_s0(), seq![LA::Write(0, 1), LA::Write(1, 2)]);
        t is Some && !law_l2(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// F-0302 / F-0801: strict is set, the engine's cached flag is still off, a bypass write changes the content.
pub proof fn cx_strict_cached_guard_l4()
    ensures ({
        let s = run::<LedgerM<StrictCachedGuardAsBuilt>>(ledger_s0(), seq![LA::SetStrict(true)]);
        let a = LA::Write(1, 1);
        s is Some && ledger_step::<StrictCachedGuardAsBuilt>(s->0, a) is Some
            && !law_l4::<StrictCachedGuardAsBuilt>(s->0, a, ledger_step::<StrictCachedGuardAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// F-0301, F-0504, F-1108, F-0503: strict is on and an unchecked write path changes the content.
pub proof fn cx_bypass_unchecked_l4()
    ensures ({
        let s = run::<LedgerM<BypassUncheckedAsBuilt>>(ledger_s0(), seq![LA::SetStrict(true)]);
        let a = LA::Write(1, 1);
        s is Some && ledger_step::<BypassUncheckedAsBuilt>(s->0, a) is Some
            && !law_l4::<BypassUncheckedAsBuilt>(s->0, a, ledger_step::<BypassUncheckedAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// C1: the content step commits, a stop comes before the record step.
pub proof fn cx_ctl_two_step_record_l2()
    ensures ({
        let t = run::<LedgerM<CtlTwoStepRecord>>(ledger_s0(), seq![LA::Write(0, 1), LA::Stop]);
        t is Some && !law_l2(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// C2: an update rewrites the first record.
pub proof fn cx_ctl_overwrite_record_l1()
    ensures ({
        let s = run::<LedgerM<CtlOverwriteRecord>>(ledger_s0(), seq![LA::Write(0, 1)]);
        let a = LA::Write(1, 2);
        s is Some && ledger_step::<CtlOverwriteRecord>(s->0, a) is Some && !law_l1(s->0, ledger_step::<CtlOverwriteRecord>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 4);
    let s = run::<LedgerM<CtlOverwriteRecord>>(ledger_s0(), seq![LA::Write(0, 1)])->0;
    let t = ledger_step::<CtlOverwriteRecord>(s, LA::Write(1, 2))->0;
    assert(t.records.subrange(0, s.records.len() as int)[0] != s.records[0]);
}

/// C3: a commit with a stale expected head is applied.
pub proof fn cx_ctl_ignore_head_l3()
    ensures ({
        let s = run::<LedgerM<CtlIgnoreHead>>(ledger_s0(), seq![LA::Write(0, 1)]);
        let a = LA::CommitStale(0, 1);
        s is Some && ledger_step::<CtlIgnoreHead>(s->0, a) is Some && !law_l3(s->0, a, ledger_step::<CtlIgnoreHead>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// C4: strict is on and the unguarded bypass changes the content.
pub proof fn cx_ctl_unguarded_bypass_l4()
    ensures ({
        let s = run::<LedgerM<CtlUnguardedBypass>>(ledger_s0(), seq![LA::SetStrict(true)]);
        let a = LA::Write(1, 1);
        s is Some && ledger_step::<CtlUnguardedBypass>(s->0, a) is Some
            && !law_l4::<CtlUnguardedBypass>(s->0, a, ledger_step::<CtlUnguardedBypass>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 4);
}

} // verus!
