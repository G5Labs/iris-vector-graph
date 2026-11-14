//! M-10 counterexamples: for each departing variant and each law it breaks, a run of the generic machine with that
//! variant's configuration from an initial state to a violation (the explorer's shortest counterexample, restated).
//! Always compiled: the baseline proves them.
use vstd::prelude::*;
use crate::exec::*;
use crate::m10_unit::*;
use crate::i10_unit::*;

verus! {

/// PerChunkCommitAsBuilt: A is kept, B never written: the unit ends with one of its two writes.
pub proof fn cx_per_chunk_commit_l1()
    ensures ({
        let t = run::<UnitM<PerChunkCommitAsBuilt>>(unit_s0(false), seq![UA::Begin, UA::WriteA, UA::Fail]);
        UnitM::<PerChunkCommitAsBuilt>::init(unit_s0(false)) && t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// RollbackAllLevelsAsBuilt: inside the caller's transaction, the refusal also takes back the caller's earlier write.
pub proof fn cx_rollback_all_levels_l2()
    ensures ({
        let t = run::<UnitM<RollbackAllLevelsAsBuilt>>(unit_s0(true), seq![UA::Begin, UA::WriteA, UA::Fail]);
        UnitM::<RollbackAllLevelsAsBuilt>::init(unit_s0(true)) && t is Some && !law_l2(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// PerStatementCommitAsBuilt: A is kept, B never written: the unit ends with one of its two writes.
pub proof fn cx_per_statement_commit_l1()
    ensures ({
        let t = run::<UnitM<PerStatementCommitAsBuilt>>(unit_s0(false), seq![UA::Begin, UA::WriteA, UA::Fail]);
        UnitM::<PerStatementCommitAsBuilt>::init(unit_s0(false)) && t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// NoTransactionAsBuilt: A is kept, B never written: the unit ends with one of its two writes.
pub proof fn cx_no_transaction_l1()
    ensures ({
        let t = run::<UnitM<NoTransactionAsBuilt>>(unit_s0(false), seq![UA::Begin, UA::WriteA, UA::Fail]);
        UnitM::<NoTransactionAsBuilt>::init(unit_s0(false)) && t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// WrongReplyAsBuilt: the refused unit's reply does not say refused with a code of the family.
pub proof fn cx_wrong_reply_l3()
    ensures ({
        let t = run::<UnitM<WrongReplyAsBuilt>>(unit_s0(false), seq![UA::Begin, UA::WriteA, UA::Fail]);
        UnitM::<WrongReplyAsBuilt>::init(unit_s0(false)) && t is Some && !law_l3(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// HiddenFailureAsBuilt: the refused unit's reply does not say refused with a code of the family.
pub proof fn cx_hidden_failure_l3()
    ensures ({
        let t = run::<UnitM<HiddenFailureAsBuilt>>(unit_s0(false), seq![UA::Begin, UA::WriteA, UA::Fail]);
        UnitM::<HiddenFailureAsBuilt>::init(unit_s0(false)) && t is Some && !law_l3(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// CtlPerStatement: A is kept, B never written: the unit ends with one of its two writes.
pub proof fn cx_ctl_per_statement_l1()
    ensures ({
        let t = run::<UnitM<CtlPerStatement>>(unit_s0(false), seq![UA::Begin, UA::WriteA, UA::Fail]);
        UnitM::<CtlPerStatement>::init(unit_s0(false)) && t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// CtlRollbackAllLevels: inside the caller's transaction, the refusal also takes back the caller's earlier write.
pub proof fn cx_ctl_rollback_all_levels_l2()
    ensures ({
        let t = run::<UnitM<CtlRollbackAllLevels>>(unit_s0(true), seq![UA::Begin, UA::WriteA, UA::Fail]);
        UnitM::<CtlRollbackAllLevels>::init(unit_s0(true)) && t is Some && !law_l2(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// CtlOkOnFailure: the refused unit's reply does not say refused with a code of the family.
pub proof fn cx_ctl_ok_on_failure_l3()
    ensures ({
        let t = run::<UnitM<CtlOkOnFailure>>(unit_s0(false), seq![UA::Begin, UA::WriteA, UA::Fail]);
        UnitM::<CtlOkOnFailure>::init(unit_s0(false)) && t is Some && !law_l3(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

} // verus!
