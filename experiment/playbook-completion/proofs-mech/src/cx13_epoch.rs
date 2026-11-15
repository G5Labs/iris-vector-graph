//! M-13 counterexamples: for each departing variant, a run of the generic machine with that variant's parameters
//! from the initial state to a violation of M13-L1. Always compiled: the baseline proves them.
use vstd::prelude::*;
use crate::exec::*;
use crate::m13_epoch::*;
use crate::i13_epoch::*;

verus! {

/// F-1402: the reader checks before reading (no marker yet), reads part 1, the whole change runs to part 2, the
/// reader reads part 2 and returns a mixed view uninterrupted.
pub proof fn cx_check_at_start_l1()
    ensures ({
        let t = run::<EpochM<CheckAtStartAsBuilt>>(epoch_s0(),
            seq![EA::RBegin, EA::RRead1, EA::Start, EA::Change1, EA::Change2, EA::RRead2, EA::REnd]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 8);
}

/// F-C1801: save_snapshot starts while the change is half done and reads a mixed state.
pub proof fn cx_no_check_l1()
    ensures ({
        let t = run::<EpochM<NoCheckAsBuilt>>(epoch_s0(),
            seq![EA::Start, EA::Change1, EA::RBegin, EA::RRead1, EA::RRead2, EA::REnd]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 7);
}

/// C1: without the end check a change inside the read goes unnoticed.
pub proof fn cx_ctl_no_end_check_l1()
    ensures ({
        let t = run::<EpochM<CtlNoEndCheck>>(epoch_s0(),
            seq![EA::RBegin, EA::RRead1, EA::Start, EA::Change1, EA::Change2, EA::RRead2, EA::REnd]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 8);
}

} // verus!
