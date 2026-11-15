//! M-10 instances: one type per object variant of mechanisms.json (family `unit`, models/semantics/src/unit.rs).
//!
//! An instance is its configuration (`UnitPolicy::cfg`) and, when it keeps every law, its discharge of the
//! obligations (`UnitObject`): the generic theorem `theorem_unit` then applies with no proof work of its own.
//! As-built variants that depart and the generic mutants (the semantics lane's negative controls) have parameters
//! only here; their kept obligations are proved (`keep_*`), their broken ones refuted (`refute_*`), and their
//! `UnitObject` impl exists only under their control feature (src/ctl_unit.rs).
use vstd::prelude::*;
use crate::exec::*;
use crate::m10_unit::*;

verus! {

// ---------------------------------------------------------------- canonical and reviewed instances (baseline)

/// canonical: 11/caller-transaction, 17/link (Ledger.cls:390-415, _write_txn.py:15-90): one nested level, a refusal takes back its own level alone.
pub struct Canonical;
impl UnitPolicy for Canonical { open spec fn cfg() -> UnitCfg { canon() } }
impl UnitObject for Canonical {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// per-chunk-commit, reviewed: 03/caller-transaction; the loader's writes join one level.
pub struct PerChunkCommitReviewed;
impl UnitPolicy for PerChunkCommitReviewed { open spec fn cfg() -> UnitCfg { canon() } }
impl UnitObject for PerChunkCommitReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// rollback-all-levels, reviewed: 07/bm25-index, 04/adjacency-entry; a refusal rolls back its own level.
pub struct RollbackAllLevelsReviewed;
impl UnitPolicy for RollbackAllLevelsReviewed { open spec fn cfg() -> UnitCfg { canon() } }
impl UnitObject for RollbackAllLevelsReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// per-statement-commit, reviewed: 16/bolt-session-with-a-key-set, 16/cypher-http-call, 15/reifier; one level per unit.
pub struct PerStatementCommitReviewed;
impl UnitPolicy for PerStatementCommitReviewed { open spec fn cfg() -> UnitCfg { canon() } }
impl UnitObject for PerStatementCommitReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// no-transaction, reviewed: 15/fhir-graph, 06/route, 05/temporal-coordinates; A is written inside the unit's level.
pub struct NoTransactionReviewed;
impl UnitPolicy for NoTransactionReviewed { open spec fn cfg() -> UnitCfg { canon() } }
impl UnitObject for NoTransactionReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// wrong-reply, reviewed: 08/cypher-call; a refusal replies with a code of the product's family.
pub struct WrongReplyReviewed;
impl UnitPolicy for WrongReplyReviewed { open spec fn cfg() -> UnitCfg { canon() } }
impl UnitObject for WrongReplyReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// hidden-failure, reviewed: 03/node-in-one-graph, 07/fused-search; a failure is reported, never ok.
pub struct HiddenFailureReviewed;
impl UnitPolicy for HiddenFailureReviewed { open spec fn cfg() -> UnitCfg { canon() } }
impl UnitObject for HiddenFailureReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
}

/// The generic theorem, instantiated: each line is the whole proof work of one instance.
pub proof fn laws_canonical(s0: US, ls: Seq<UA>, t: US) requires reached::<UnitM<Canonical>>(s0, ls, t)
    ensures law_l1(t), law_l2(t), law_l3(t) { theorem_unit::<Canonical>(s0, ls, t); }
pub proof fn laws_per_chunk_commit_reviewed(s0: US, ls: Seq<UA>, t: US) requires reached::<UnitM<PerChunkCommitReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l2(t), law_l3(t) { theorem_unit::<PerChunkCommitReviewed>(s0, ls, t); }
pub proof fn laws_rollback_all_levels_reviewed(s0: US, ls: Seq<UA>, t: US) requires reached::<UnitM<RollbackAllLevelsReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l2(t), law_l3(t) { theorem_unit::<RollbackAllLevelsReviewed>(s0, ls, t); }
pub proof fn laws_per_statement_commit_reviewed(s0: US, ls: Seq<UA>, t: US) requires reached::<UnitM<PerStatementCommitReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l2(t), law_l3(t) { theorem_unit::<PerStatementCommitReviewed>(s0, ls, t); }
pub proof fn laws_no_transaction_reviewed(s0: US, ls: Seq<UA>, t: US) requires reached::<UnitM<NoTransactionReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l2(t), law_l3(t) { theorem_unit::<NoTransactionReviewed>(s0, ls, t); }
pub proof fn laws_wrong_reply_reviewed(s0: US, ls: Seq<UA>, t: US) requires reached::<UnitM<WrongReplyReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l2(t), law_l3(t) { theorem_unit::<WrongReplyReviewed>(s0, ls, t); }
pub proof fn laws_hidden_failure_reviewed(s0: US, ls: Seq<UA>, t: US) requires reached::<UnitM<HiddenFailureReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l2(t), law_l3(t) { theorem_unit::<HiddenFailureReviewed>(s0, ls, t); }

// ---------------------------------------------------------------- as-built variants that depart and generic mutants (parameters only)

/// per-chunk-commit as built: 03/caller-transaction (F-0305; bulk_loader.py server-loader path): each chunk commits on its own.
pub struct PerChunkCommitAsBuilt;
impl UnitPolicy for PerChunkCommitAsBuilt { open spec fn cfg() -> UnitCfg { UnitCfg { commit: Commit::PerStatement, ..canon() } } }
pub proof fn refute_per_chunk_commit_l1() ensures !obl_l1::<PerChunkCommitAsBuilt>() {}
pub proof fn keep_per_chunk_commit_l2() ensures obl_l2::<PerChunkCommitAsBuilt>() {}
pub proof fn keep_per_chunk_commit_l3() ensures obl_l3::<PerChunkCommitAsBuilt>() {}

/// rollback-all-levels as built: 07/bm25-index, 04/adjacency-entry (F-C0702, F-0704, F-0409; BM25Index.cls insert in a caller transaction, Adjacency.cls rebuild): a refusal rolls back the caller's transaction too.
pub struct RollbackAllLevelsAsBuilt;
impl UnitPolicy for RollbackAllLevelsAsBuilt { open spec fn cfg() -> UnitCfg { UnitCfg { undo: Undo::AllLevels, ..canon() } } }
pub proof fn keep_rollback_all_levels_l1() ensures obl_l1::<RollbackAllLevelsAsBuilt>() {}
pub proof fn refute_rollback_all_levels_l2() ensures !obl_l2::<RollbackAllLevelsAsBuilt>() {}
pub proof fn keep_rollback_all_levels_l3() ensures obl_l3::<RollbackAllLevelsAsBuilt>() {}

/// per-statement-commit as built: 16/bolt-session-with-a-key-set, 16/cypher-http-call, 15/reifier (F-1601, F-1610, F-1609, F-C1502; bolt_server.py:500-510, 567-622, cypher_api.py:379-410, nodes_edges.py:2176-2199): each statement commits on its own.
pub struct PerStatementCommitAsBuilt;
impl UnitPolicy for PerStatementCommitAsBuilt { open spec fn cfg() -> UnitCfg { UnitCfg { commit: Commit::PerStatement, ..canon() } } }
pub proof fn refute_per_statement_commit_l1() ensures !obl_l1::<PerStatementCommitAsBuilt>() {}
pub proof fn keep_per_statement_commit_l2() ensures obl_l2::<PerStatementCommitAsBuilt>() {}
pub proof fn keep_per_statement_commit_l3() ensures obl_l3::<PerStatementCommitAsBuilt>() {}

/// no-transaction as built: 15/fhir-graph, 06/route, 05/temporal-coordinates (F-1511, F-C1501, F-0615, F-C0501; FHIRGraph.cls:167-279, embeddings.py route creation, TemporalIndex.cls refused write): A is written before or outside the transaction.
pub struct NoTransactionAsBuilt;
impl UnitPolicy for NoTransactionAsBuilt { open spec fn cfg() -> UnitCfg { UnitCfg { commit: Commit::NoTxn, ..canon() } } }
pub proof fn refute_no_transaction_l1() ensures !obl_l1::<NoTransactionAsBuilt>() {}
pub proof fn keep_no_transaction_l2() ensures obl_l2::<NoTransactionAsBuilt>() {}
pub proof fn keep_no_transaction_l3() ensures obl_l3::<NoTransactionAsBuilt>() {}

/// wrong-reply as built: 08/cypher-call (F-0807, F-0804, F-0817; query.py:1946-1966): refusals of the wrong class or answered as no rows.
pub struct WrongReplyAsBuilt;
impl UnitPolicy for WrongReplyAsBuilt { open spec fn cfg() -> UnitCfg { UnitCfg { reply: Reply::WrongClass, ..canon() } } }
pub proof fn keep_wrong_reply_l1() ensures obl_l1::<WrongReplyAsBuilt>() {}
pub proof fn keep_wrong_reply_l2() ensures obl_l2::<WrongReplyAsBuilt>() {}
pub proof fn refute_wrong_reply_l3() ensures !obl_l3::<WrongReplyAsBuilt>() {}

/// hidden-failure as built: 03/node-in-one-graph, 07/fused-search (F-0306, F-0307, F-0709; nodes_edges.py create_node, fusion): a failure is hidden in an ok answer.
pub struct HiddenFailureAsBuilt;
impl UnitPolicy for HiddenFailureAsBuilt { open spec fn cfg() -> UnitCfg { UnitCfg { reply: Reply::OkOnFailure, ..canon() } } }
pub proof fn keep_hidden_failure_l1() ensures obl_l1::<HiddenFailureAsBuilt>() {}
pub proof fn keep_hidden_failure_l2() ensures obl_l2::<HiddenFailureAsBuilt>() {}
pub proof fn refute_hidden_failure_l3() ensures !obl_l3::<HiddenFailureAsBuilt>() {}

/// unit-control-C1-per-statement: each write commits on its own.
pub struct CtlPerStatement;
impl UnitPolicy for CtlPerStatement { open spec fn cfg() -> UnitCfg { UnitCfg { commit: Commit::PerStatement, ..canon() } } }
pub proof fn refute_ctl_per_statement_l1() ensures !obl_l1::<CtlPerStatement>() {}
pub proof fn keep_ctl_per_statement_l2() ensures obl_l2::<CtlPerStatement>() {}
pub proof fn keep_ctl_per_statement_l3() ensures obl_l3::<CtlPerStatement>() {}

/// unit-control-C2-rollback-all-levels: a refusal rolls back every level.
pub struct CtlRollbackAllLevels;
impl UnitPolicy for CtlRollbackAllLevels { open spec fn cfg() -> UnitCfg { UnitCfg { undo: Undo::AllLevels, ..canon() } } }
pub proof fn keep_ctl_rollback_all_levels_l1() ensures obl_l1::<CtlRollbackAllLevels>() {}
pub proof fn refute_ctl_rollback_all_levels_l2() ensures !obl_l2::<CtlRollbackAllLevels>() {}
pub proof fn keep_ctl_rollback_all_levels_l3() ensures obl_l3::<CtlRollbackAllLevels>() {}

/// unit-control-C3-ok-on-failure: a failure replies ok.
pub struct CtlOkOnFailure;
impl UnitPolicy for CtlOkOnFailure { open spec fn cfg() -> UnitCfg { UnitCfg { reply: Reply::OkOnFailure, ..canon() } } }
pub proof fn keep_ctl_ok_on_failure_l1() ensures obl_l1::<CtlOkOnFailure>() {}
pub proof fn keep_ctl_ok_on_failure_l2() ensures obl_l2::<CtlOkOnFailure>() {}
pub proof fn refute_ctl_ok_on_failure_l3() ensures !obl_l3::<CtlOkOnFailure>() {}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// unit-sharp-refused-inside-caller: inside a caller's transaction, a refused unit keeps the caller's write.
pub proof fn sharp_refused_inside_caller()
    ensures ({
        let t = run::<UnitM<Canonical>>(unit_s0(true), seq![UA::Begin, UA::WriteA, UA::Fail]);
        t is Some && t->0.pc == 4 && t->0.caller_open && t->0.w && t->0.reply == UR::Refused(true)
    })
{
    reveal_with_fuel(run, 4);
}

/// unit-sharp-ok: an ok unit with both writes.
pub proof fn sharp_ok()
    ensures ({
        let t = run::<UnitM<Canonical>>(unit_s0(false), seq![UA::Begin, UA::WriteA, UA::WriteB, UA::End]);
        t is Some && t->0.pc == 4 && t->0.a && t->0.b && t->0.reply == UR::Ok
    })
{
    reveal_with_fuel(run, 5);
}

} // verus!
