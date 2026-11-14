//! The validated contract (iris-contract round r6, contract-2's S-1) as a `Sem` value, and the controls.
//!
//! `contract_sem()` is the validated reading of every clause (the harness runs the exec model with it).
//! `validated()` is what every premise theorem (premises.rs) is stated over: in the baseline build it IS
//! `contract_sem()`; each control feature weakens exactly one clause there, so the premise theorems that need the clause
//! fail at the lines marked `// LOCATE <feature>` (their call of the generic lemma whose precondition is the clause),
//! while the control's counterexample (cx.rs, always compiled) proves the premise false under the weakened clause.
use vstd::prelude::*;
use crate::spec::*;

verus! {

pub open spec fn contract_sem() -> Sem {
    Sem {
        unlock_deferred: true,
        rollback_one_is_one_level: true,
        incr_survives: true,
        dirty_reads: true,
        hierarchical: true,
        shared_compatible: true,
        incremental: true,
        sql_start: SqlStartSem::NothingIfOpen,
        sql_commit: Ends::One,
        sql_rollback: Ends::One,
        drv_rollback: Ends::All,
        drv_commit: Ends::One,
        autocommit_on_commits: true,
        dml_waits: true,
        stop_rolls_back: true,
        rollback_physical: false,
        ppg_rolled_back: false,
        failed_dml_opens_txn: true,
        empty_dml_opens_txn: false,
        select_opens_txn: false,
        sqlproc_levels_end_with_statement: false,
        freedom: FreedomSem::Both,
        insert_dup_waits: false,
        row_lock_held: true,
        lock_wait_grants: true,
        stop_all_levels: true,
        kill_logged: true,
        select_dirty: true,
    }
}

/// The exec constant the harness uses: verified equal to the validated contract.
pub fn e_contract_sem() -> (s: Sem)
    ensures s == contract_sem(),
{
    Sem {
        unlock_deferred: true,
        rollback_one_is_one_level: true,
        incr_survives: true,
        dirty_reads: true,
        hierarchical: true,
        shared_compatible: true,
        incremental: true,
        sql_start: SqlStartSem::NothingIfOpen,
        sql_commit: Ends::One,
        sql_rollback: Ends::One,
        drv_rollback: Ends::All,
        drv_commit: Ends::One,
        autocommit_on_commits: true,
        dml_waits: true,
        stop_rolls_back: true,
        rollback_physical: false,
        ppg_rolled_back: false,
        failed_dml_opens_txn: true,
        empty_dml_opens_txn: false,
        select_opens_txn: false,
        sqlproc_levels_end_with_statement: false,
        freedom: FreedomSem::Both,
        insert_dup_waits: false,
        row_lock_held: true,
        lock_wait_grants: true,
        stop_all_levels: true,
        kill_logged: true,
        select_dirty: true,
    }
}

// ------------------------------------------------------------------------------------------------ the weakened clauses

pub open spec fn m_unlock_immediate() -> Sem { Sem { unlock_deferred: false, ..contract_sem() } }
pub open spec fn m_stop_commits() -> Sem { Sem { stop_rolls_back: false, ..contract_sem() } }
pub open spec fn m_stop_top_level_only() -> Sem { Sem { stop_all_levels: false, ..contract_sem() } }
pub open spec fn m_kill_not_logged() -> Sem { Sem { kill_logged: false, ..contract_sem() } }
pub open spec fn m_dml_ignores_row_locks() -> Sem { Sem { dml_waits: false, ..contract_sem() } }
pub open spec fn m_row_lock_statement_only() -> Sem { Sem { row_lock_held: false, ..contract_sem() } }
pub open spec fn m_insert_dup_waits() -> Sem { Sem { insert_dup_waits: true, ..contract_sem() } }
pub open spec fn m_freedom_wait_only() -> Sem { Sem { freedom: FreedomSem::WaitOnly, ..contract_sem() } }
pub open spec fn m_no_dirty_reads() -> Sem { Sem { dirty_reads: false, ..contract_sem() } }
pub open spec fn m_select_committed_only() -> Sem { Sem { select_dirty: false, ..contract_sem() } }
pub open spec fn m_rollback_physical() -> Sem { Sem { rollback_physical: true, ..contract_sem() } }
pub open spec fn m_incr_rolled_back() -> Sem { Sem { incr_survives: false, ..contract_sem() } }
pub open spec fn m_rollback_one_undoes_all() -> Sem { Sem { rollback_one_is_one_level: false, ..contract_sem() } }
pub open spec fn m_sql_commit_ends_all() -> Sem { Sem { sql_commit: Ends::All, ..contract_sem() } }
pub open spec fn m_lock_wait_never_granted() -> Sem { Sem { lock_wait_grants: false, ..contract_sem() } }
pub open spec fn m_flat_lock_names() -> Sem { Sem { hierarchical: false, ..contract_sem() } }
pub open spec fn m_shared_conflicts_shared() -> Sem { Sem { shared_compatible: false, ..contract_sem() } }

#[cfg(not(any(feature = "ctl_unlock_immediate", feature = "ctl_stop_commits", feature = "ctl_stop_top_level_only",
    feature = "ctl_kill_not_logged", feature = "ctl_dml_ignores_row_locks", feature = "ctl_row_lock_statement_only",
    feature = "ctl_insert_dup_waits", feature = "ctl_freedom_wait_only", feature = "ctl_no_dirty_reads",
    feature = "ctl_select_committed_only", feature = "ctl_rollback_physical", feature = "ctl_incr_rolled_back",
    feature = "ctl_rollback_one_undoes_all", feature = "ctl_sql_commit_ends_all", feature = "ctl_lock_wait_never_granted",
    feature = "ctl_flat_lock_names", feature = "ctl_shared_conflicts_shared")))]
pub open spec fn validated() -> Sem { contract_sem() }

// CONTROL ctl_unlock_immediate clause=E-LOCK-DEFER mutant=unlock-immediate-in-txn cx=cx_unlock_immediate
#[cfg(feature = "ctl_unlock_immediate")]
pub open spec fn validated() -> Sem { m_unlock_immediate() }
// CONTROL ctl_stop_commits clause=E-STOP mutant=stop-commits cx=cx_stop_commits
#[cfg(feature = "ctl_stop_commits")]
pub open spec fn validated() -> Sem { m_stop_commits() }
// CONTROL ctl_stop_top_level_only clause=E-STOP mutant=stop-rolls-back-top-level-only cx=cx_stop_top_level_only
#[cfg(feature = "ctl_stop_top_level_only")]
pub open spec fn validated() -> Sem { m_stop_top_level_only() }
// CONTROL ctl_kill_not_logged clause=E-GLOBALS mutant=kill-not-logged cx=cx_kill_not_logged
#[cfg(feature = "ctl_kill_not_logged")]
pub open spec fn validated() -> Sem { m_kill_not_logged() }
// CONTROL ctl_dml_ignores_row_locks clause=E-ROWLOCK mutant=dml-ignores-row-locks cx=cx_dml_ignores_row_locks
#[cfg(feature = "ctl_dml_ignores_row_locks")]
pub open spec fn validated() -> Sem { m_dml_ignores_row_locks() }
// CONTROL ctl_row_lock_statement_only clause=E-ROWLOCK mutant=row-lock-statement-only cx=cx_row_lock_statement_only
#[cfg(feature = "ctl_row_lock_statement_only")]
pub open spec fn validated() -> Sem { m_row_lock_statement_only() }
// CONTROL ctl_insert_dup_waits clause=E-UNIQUE mutant=insert-dup-waits cx=cx_insert_dup_waits
#[cfg(feature = "ctl_insert_dup_waits")]
pub open spec fn validated() -> Sem { m_insert_dup_waits() }
// CONTROL ctl_freedom_wait_only clause=Freedom mutant=freedom-waits-only cx=cx_freedom_wait_only
#[cfg(feature = "ctl_freedom_wait_only")]
pub open spec fn validated() -> Sem { m_freedom_wait_only() }
// CONTROL ctl_no_dirty_reads clause=E-VIS mutant=no-dirty-reads cx=cx_no_dirty_reads
#[cfg(feature = "ctl_no_dirty_reads")]
pub open spec fn validated() -> Sem { m_no_dirty_reads() }
// CONTROL ctl_select_committed_only clause=E-VIS mutant=sql-select-committed-only cx=cx_select_committed_only
#[cfg(feature = "ctl_select_committed_only")]
pub open spec fn validated() -> Sem { m_select_committed_only() }
// CONTROL ctl_rollback_physical clause=E-ROLLBACK-OTHER mutant=rollback-physical cx=cx_rollback_physical
#[cfg(feature = "ctl_rollback_physical")]
pub open spec fn validated() -> Sem { m_rollback_physical() }
// CONTROL ctl_incr_rolled_back clause=E-INCR mutant=incr-rolled-back cx=cx_incr_rolled_back
#[cfg(feature = "ctl_incr_rolled_back")]
pub open spec fn validated() -> Sem { m_incr_rolled_back() }
// CONTROL ctl_rollback_one_undoes_all clause=E-PARTIAL mutant=rollback-one-undoes-all cx=cx_rollback_one_undoes_all
#[cfg(feature = "ctl_rollback_one_undoes_all")]
pub open spec fn validated() -> Sem { m_rollback_one_undoes_all() }
// CONTROL ctl_sql_commit_ends_all clause=E-SQL-END mutant=sql-commit-ends-all cx=cx_sql_commit_ends_all
#[cfg(feature = "ctl_sql_commit_ends_all")]
pub open spec fn validated() -> Sem { m_sql_commit_ends_all() }
// CONTROL ctl_lock_wait_never_granted clause=E-LOCK-WAIT mutant=lock-wait-never-granted cx=cx_lock_wait_never_granted
#[cfg(feature = "ctl_lock_wait_never_granted")]
pub open spec fn validated() -> Sem { m_lock_wait_never_granted() }
// CONTROL ctl_flat_lock_names clause=E-LOCK-NAMES mutant=flat-lock-names cx=cx_flat_lock_names
#[cfg(feature = "ctl_flat_lock_names")]
pub open spec fn validated() -> Sem { m_flat_lock_names() }
// CONTROL ctl_shared_conflicts_shared clause=E-LOCK-MODES mutant=shared-conflicts-shared cx=cx_shared_conflicts_shared
#[cfg(feature = "ctl_shared_conflicts_shared")]
pub open spec fn validated() -> Sem { m_shared_conflicts_shared() }

} // verus!
