//! The proof crates' environment premises, each proved from the contract's clauses as validated (`validated()`), or
//! shown not implied (a witness the contract permits), or shown false (the contract implies its negation).
//!
//! Every theorem here is one call of a generic lemma (gen.rs) whose precondition is the clause it needs; the line of the
//! call carries `// LOCATE <control>` for every control (clauses.rs) that weakens that clause, so the control must make
//! this theorem fail exactly there. Crate and premise ids are those of the crates' PROOFS.md premise tables.
use vstd::prelude::*;
use crate::spec::*;
use crate::effects::*;
use crate::headlock::*;
use crate::clauses::*;
use crate::gen::*;
use crate::ext::*;

verus! {

// ================================================================================================ head lock: atomic steps

/// proofs/PROOFS.md section 8, P-C01: "Every protocol step is one atomic transaction holding ^IVG.Ledger("head")
/// (commit, replay, start, batch record, final) ... a stopped process loses only its own state". Under the discipline
/// `disc` (the product's: R written only by the exclusive head-lock holder inside its transaction, no immediate unlock
/// of H, no $INCREMENT on R), for every step of every process: inv_h is kept, the holder's committed state of R does
/// not move while its transaction is open, its end leaves all or none of its writes, a stop leaves none.
pub proof fn premise_proofs_p_c01(u: U, s: State, p: usize, op: Op, ch: bool, hl: usize, R: spec_fn(int) -> bool, h: usize)
    requires hl_hyp(validated(), u, s, p, op, hl, R, h),
    ensures hl_concl(validated(), u, s, p, op, ch, hl, R, h),
{
    gen_head_lock(validated(), u, s, p, op, ch, hl, R, h); // LOCATE ctl_unlock_immediate ctl_stop_commits ctl_stop_top_level_only ctl_kill_not_logged
}

/// proofs-d9/PROOFS.md section 5, P-D9-1 (carried unchanged by proofs-d9b and proofs-d9c): "Ledger commits, replays and
/// the redaction's Start, batches and Final are one atomic transaction each, holding the head lock (a stopped one
/// leaves nothing)". Same theorem as P-C01 for the head-locked steps.
pub proof fn premise_d9_p_d9_1(u: U, s: State, p: usize, op: Op, ch: bool, hl: usize, R: spec_fn(int) -> bool, h: usize)
    requires hl_hyp(validated(), u, s, p, op, hl, R, h),
    ensures hl_concl(validated(), u, s, p, op, ch, hl, R, h),
{
    gen_head_lock(validated(), u, s, p, op, ch, hl, R, h); // LOCATE ctl_unlock_immediate ctl_stop_commits ctl_stop_top_level_only ctl_kill_not_logged
}

/// proofs-d9 P-D9-1, second sentence: "Erasures and bypass writes are not atomic: they stay open across steps and may
/// roll back." The contract permits a stop of any open transaction at any moment (no clause excludes it).
pub proof fn premise_d9_p_d9_1_may_roll_back(u: U, s: State, p: usize, t: usize)
    requires wf(u, s), ready(s, p), (t as int) < s.procs.len(), s.procs[t as int].alive, level(s.procs[t as int]) > 0,
    ensures permits(validated(), u, s, p, Op::Terminate { target: t }, stop(validated(), s, t), Obs::Ok),
{
    gen_abort_permitted(validated(), u, s, p, t);
}

/// proofs-breadth/PROOFS.md section 4, P-L3 (proofs-pa3 unchanged): "every L2 step is one transaction under the locks the
/// code takes (IRIS contract: Nesting, Locks deferral, Process stop, Visibility = dirty reads)".
pub proof fn premise_breadth_p_l3(u: U, s: State, p: usize, op: Op, ch: bool, hl: usize, R: spec_fn(int) -> bool, h: usize)
    requires hl_hyp(validated(), u, s, p, op, hl, R, h),
    ensures hl_concl(validated(), u, s, p, op, ch, hl, R, h),
{
    gen_head_lock(validated(), u, s, p, op, ch, hl, R, h); // LOCATE ctl_unlock_immediate ctl_stop_commits ctl_stop_top_level_only ctl_kill_not_logged
}

/// proofs-d1b/PROOFS.md, P-S1: "a ledger commit (rows and revision) is one step".
pub proof fn premise_d1b_p_s1(u: U, s: State, p: usize, op: Op, ch: bool, hl: usize, R: spec_fn(int) -> bool, h: usize)
    requires hl_hyp(validated(), u, s, p, op, hl, R, h),
    ensures hl_concl(validated(), u, s, p, op, ch, hl, R, h),
{
    gen_head_lock(validated(), u, s, p, op, ch, hl, R, h); // LOCATE ctl_unlock_immediate ctl_stop_commits ctl_stop_top_level_only ctl_kill_not_logged
}

/// The invariant of the head-lock theorems holds in the initial state, so (by the theorems above) in every state any
/// schedule under the discipline reaches.
pub proof fn premise_head_lock_init(u: U, case: Case, hl: usize, R: spec_fn(int) -> bool)
    requires u.n() <= usize::MAX, case.nprocs <= usize::MAX,
    ensures inv_h(validated(), u, init_state(u, case), hl, R),
{
    gen_init_inv_h(validated(), u, case, hl, R);
}

/// proofs-d9 design G-L (the liveness check runs under the eraser's lock) and P-D9-1's locked Start / Final reads: a
/// process holding the head lock in any mode reads every protected cell at its committed value.
pub proof fn premise_d9_g_l_reader_under_lock(u: U, s: State, hl: usize, R: spec_fn(int) -> bool, q: usize)
    requires inv_h(validated(), u, s, hl, R), is_glob(u, hl as int), (q as int) < s.procs.len(), s.procs[q as int].alive,
        any(s.procs[q as int].locks[hl as int]), !has_r(s.procs[q as int].undo, R),
    ensures forall|y: int, c: int| 0 <= y < s.procs.len() && 0 <= c < s.g.len() && R(c) ==> #[trigger] base(validated(), s, y)[c] == s.g[c],
{
    theorem_reader_under_lock(validated(), u, s, hl, R, q);
}

/// proofs/PROOFS.md section 8, P-C04: "An erasure is not rolled back between its two steps (no abort modelled)".
/// NOT IMPLIED by the contract: a stop of the erasure's process is permitted at any point and ends its transaction.
pub proof fn premise_proofs_p_c04_not_implied(u: U, s: State, p: usize, t: usize)
    requires wf(u, s), ready(s, p), (t as int) < s.procs.len(), s.procs[t as int].alive, level(s.procs[t as int]) > 0,
    ensures permits(validated(), u, s, p, Op::Terminate { target: t }, stop(validated(), s, t), Obs::Ok),
        !stop(validated(), s, t).procs[t as int].alive,
{
    gen_abort_permitted(validated(), u, s, p, t);
}

/// proofs-d1c/PROOFS.md section 7, P-B2: "Nested transactions: an inner TCOMMIT only lowers $TLEVEL and an outer
/// rollback undoes inner work" (the log is kept; the holder theorem rolls back the whole log).
pub proof fn premise_d1c_p_b2(u: U, s: State, p: usize)
    requires wf(u, s), ready(s, p), level(s.procs[p as int]) >= 2,
    ensures ({
        let s2 = step(validated(), u, s, p, Op::TCommit, false).0;
        &&& level(s2.procs[p as int]) == level(s.procs[p as int]) - 1
        &&& s2.procs[p as int].undo == s.procs[p as int].undo
        &&& s2.g == s.g
    }),
{
    gen_inner_commit(validated(), u, s, p);
}

// ================================================================================================ stop, locks, waits

/// TRUST.md P-0001 (and P-C01's "a stopped one leaves nothing"): "a stopped process's open transaction is rolled back
/// (every level)"; its locks are released.
pub proof fn premise_trust_p_0001(u: U, s: State, p: usize, t: usize)
    requires wf(u, s), ready(s, p), (t as int) < s.procs.len(), s.procs[t as int].alive,
    ensures ({
        let s2 = step(validated(), u, s, p, Op::Terminate { target: t }, false).0;
        &&& s2.g == rollback_all(validated(), s, t).g
        &&& level(s2.procs[t as int]) == 0
        &&& !s2.procs[t as int].alive
        &&& forall|m: int| 0 <= m < u.n() ==> !any(#[trigger] s2.procs[t as int].locks[m])
    }),
{
    gen_stop_all_levels(validated(), u, s, p, t); // LOCATE ctl_stop_commits ctl_stop_top_level_only
}

/// TRUST.md P-0003: "an unlock inside a transaction takes effect at the outermost end".
pub proof fn premise_trust_p_0003(u: U, s: State, p: usize, q: usize, c: usize)
    requires wf(u, s), ready(s, p), ready(s, q), p != q, level(s.procs[p as int]) > 0, is_glob(u, c as int),
        s.procs[p as int].locks[c as int].e > 0, s.procs[p as int].locks[c as int].de < u64::MAX,
    ensures ({
        let s2 = step(validated(), u, s, p, Op::Unlock { c, mode: Mode::E, immediate: false }, false).0;
        &&& excl(s2.procs[p as int].locks[c as int])
        &&& step(validated(), u, s2, q, Op::Lock { c, mode: Mode::E, wait: false }, false).1 == Obs::Test(false)
    }),
{
    gen_deferred_unlock(validated(), u, s, p, q, c); // LOCATE ctl_unlock_immediate
}

/// proofs/PROOFS.md section 5, PF-3 (and proofs-d9 / -d9b / -d9c PF-3): "a lock waiter proceeds when the holder
/// releases; a stopped holder's locks are released". (That every erasure ENDS is a progress premise the contract does
/// not imply.)
pub proof fn premise_proofs_pf_3(u: U, s: State, p: usize, q: usize, t: usize, c: usize, mode: Mode)
    requires wf(u, s), ready(s, p), p != q, q != t, (q as int) < s.procs.len(), s.procs[q as int].alive,
        s.procs[q as int].pending == Some(Op::Lock { c, mode, wait: true }), (t as int) < s.procs.len(), s.procs[t as int].alive,
        (c as int) < u.n(), only_t_conflicts(validated(), u, s, q, t, c, mode),
        s.procs[q as int].locks[c as int].e < u64::MAX, s.procs[q as int].locks[c as int].s < u64::MAX,
    ensures step(validated(), u, step(validated(), u, s, p, Op::Terminate { target: t }, false).0, q, Op::Await, false).1 == Obs::Test(true),
{
    gen_waiter_after_stop(validated(), u, s, p, q, t, c, mode); // LOCATE ctl_lock_wait_never_granted
}

/// PF-3's commit case: "its commit or rollback releases the head lock": at the outermost commit the holds released
/// inside the transaction are gone.
pub proof fn premise_proofs_pf_3_commit(u: U, s: State, p: usize, c: usize)
    requires wf(u, s), ready(s, p), level(s.procs[p as int]) == 1, (c as int) < u.n(),
        s.procs[p as int].locks[c as int].e == 0, s.procs[p as int].locks[c as int].s == 0,
    ensures !any(step(validated(), u, s, p, Op::TCommit, false).0.procs[p as int].locks[c as int]),
{
    gen_commit_releases(validated(), u, s, p, c);
}

/// proofs-d1f/PROOFS.md section 9, P-F4: "the sync lock admits one sync per graph; a killed holder's lock is freed by
/// IRIS (SYS-P4)": once the holder is stopped, a waiter on the lock is granted it.
pub proof fn premise_d1f_p_f4(u: U, s: State, p: usize, q: usize, t: usize, c: usize)
    requires wf(u, s), ready(s, p), p != q, q != t, (q as int) < s.procs.len(), s.procs[q as int].alive,
        s.procs[q as int].pending == Some(Op::Lock { c, mode: Mode::E, wait: true }), (t as int) < s.procs.len(),
        s.procs[t as int].alive, (c as int) < u.n(), only_t_conflicts(validated(), u, s, q, t, c, Mode::E),
        s.procs[q as int].locks[c as int].e < u64::MAX, s.procs[q as int].locks[c as int].s < u64::MAX,
    ensures step(validated(), u, step(validated(), u, s, p, Op::Terminate { target: t }, false).0, q, Op::Await, false).1 == Obs::Test(true),
{
    gen_waiter_after_stop(validated(), u, s, p, q, t, c, Mode::E); // LOCATE ctl_lock_wait_never_granted
}

/// proofs-pa3 reviewed guard R04-5 (an exclusive `^IVG.AdjW` excludes the writers' `^IVG.AdjW(g)`; Adjacency.cls:449-455):
/// an exclusive lock on a name refuses every lock on a descendant name.
pub proof fn premise_pa3_r04_5_names(u: U, s: State, p: usize, q: usize, a: usize, b: usize, mode: Mode)
    requires wf(u, s), (p as int) < s.procs.len(), s.procs[p as int].alive, ready(s, q), p != q, covers(u, a as int, b as int),
        excl(s.procs[p as int].locks[a as int]),
    ensures step(validated(), u, s, q, Op::Lock { c: b, mode, wait: false }, false).1 == Obs::Test(false),
{
    gen_hierarchy(validated(), u, s, p, q, a, b, mode); // LOCATE ctl_flat_lock_names
}

/// proofs-breadth/PROOFS.md section 4, P-A4 ("a rebuild overlaps no writer, eraser or second rebuild"; violated at the
/// pin: BeginRebuild takes ^IVG.AdjW#"S", F-C0402): the contract makes shared holds compatible, so a shared lock
/// excludes no other shared holder; the pin's lock choice cannot give P-A4 (the pin's violation, not a contract gap).
pub proof fn premise_breadth_p_a4_shared(u: U, s: State, p: usize, q: usize, c: usize)
    requires wf(u, s), ready(s, p), (q as int) < s.procs.len(), q != p, s.procs[q as int].alive, (c as int) < u.n(),
        s.procs[q as int].locks[c as int].s > 0,
        forall|y: int, m: int| 0 <= y < s.procs.len() && y != p && s.procs[y].alive && 0 <= m < u.n()
            && related(validated(), u, m, c as int) ==> !excl(#[trigger] s.procs[y].locks[m]),
        s.procs[p as int].locks[c as int].s < u64::MAX,
    ensures step(validated(), u, s, p, Op::Lock { c, mode: Mode::S, wait: false }, false).1 == Obs::Test(true),
{
    gen_shared_compat(validated(), u, s, p, q, c); // LOCATE ctl_shared_conflicts_shared
}

// ================================================================================================ row locks and keys

/// TRUST.md P-1201: "a SQL delete waits for a row another transaction holds": a DELETE/UPDATE waits for a row another
/// open transaction inserted.
pub proof fn premise_trust_p_1201(u: U, s: State, q: usize, p: usize, r: usize, v: Val, op2: Op, ch: bool)
    requires wf(u, s), ready(s, q), ready(s, p), p != q, level(s.procs[q as int]) > 0, row_ok(u, r), s.g[r as int] is None,
        !row_held(s, q, r), op2 == (Op::Update { r, v }) || op2 == (Op::Delete { r }),
    ensures ({
        let s1 = step(validated(), u, s, q, Op::Insert { r, v }, false).0;
        step(validated(), u, s1, p, op2, ch) == (set_pending(s1, p, Some(op2)), Obs::Pending)
    }),
{
    gen_wait_after_insert(validated(), u, s, q, p, r, v, op2, ch); // LOCATE ctl_dml_ignores_row_locks ctl_row_lock_statement_only
}

/// proofs-d9/PROOFS.md section 5, P-D9-2 (first half; carried by d9b, d9c): "a ledger commit waits for a row an open
/// bypass txn wrote" -- implied for the commit's UPDATE / DELETE of the row.
pub proof fn premise_d9_p_d9_2_wait(u: U, s: State, q: usize, p: usize, r: usize, v: Val, op2: Op, ch: bool)
    requires wf(u, s), ready(s, q), ready(s, p), p != q, level(s.procs[q as int]) > 0, row_ok(u, r), s.g[r as int] is Some,
        !row_held(s, q, r), op2 == (Op::Update { r, v }) || op2 == (Op::Delete { r }),
    ensures ({
        let s1 = step(validated(), u, s, q, Op::Update { r, v }, false).0;
        step(validated(), u, s1, p, op2, ch) == (set_pending(s1, p, Some(op2)), Obs::Pending)
    }),
{
    gen_wait_after_update(validated(), u, s, q, p, r, v, op2, ch); // LOCATE ctl_dml_ignores_row_locks ctl_row_lock_statement_only
}

/// P-D9-2 (first half) for an INSERT of a key the open bypass transaction inserted: the contract does NOT make the commit
/// wait; it fails at once with -119 (E-UNIQUE). The premise as worded is not implied for inserts; what is implied is an
/// immediate refusal.
pub proof fn premise_d9_p_d9_2_insert_fails(u: U, s: State, p: usize, r: usize, v: Val, ch: bool)
    requires wf(u, s), ready(s, p), row_ok(u, r), s.g[r as int] is Some,
    ensures step(validated(), u, s, p, Op::Insert { r, v }, ch).1 == Obs::SqlError(-119i64),
{
    gen_insert_dup_fails(validated(), u, s, p, r, v, ch); // LOCATE ctl_insert_dup_waits
}

/// P-D9-2 (second half): "a bypass write waits for a row the open erasure deleted (insert over uncommitted delete: a
/// Freedom)" -- NOT IMPLIED: the contract permits both the wait and the insert proceeding (under a new row id).
pub proof fn premise_d9_p_d9_2_freedom(u: U, s: State, p: usize, q: usize, r: usize, v: Val)
    requires wf(u, s), ready(s, p), (q as int) < s.procs.len(), q != p, s.procs[q as int].alive, s.procs[q as int].rlocks[r as int],
        row_ok(u, r), s.g[r as int] is None,
    ensures
        permits(validated(), u, s, p, Op::Insert { r, v }, set_pending(s, p, Some(Op::Insert { r, v })), Obs::Pending),
        permits(validated(), u, s, p, Op::Insert { r, v }, step(validated(), u, s, p, Op::Insert { r, v }, true).0, Obs::Count(1i64)),
{
    gen_freedom_both(validated(), u, s, p, q, r, v); // LOCATE ctl_freedom_wait_only ctl_dml_ignores_row_locks
}

/// proofs-breadth/PROOFS.md section 4, P-L5 (proofs-pa3 unchanged): "a governed write waits for the row locks of an open
/// nested commit": the row lock of a write inside the nested ledger level survives its TCOMMIT.
pub proof fn premise_breadth_p_l5(u: U, s: State, q: usize, p: usize, r: usize, v: Val, op2: Op, ch: bool)
    requires wf(u, s), ready(s, q), ready(s, p), p != q, level(s.procs[q as int]) >= 2, row_ok(u, r), s.g[r as int] is Some,
        !row_held(s, q, r), op2 == (Op::Update { r, v }) || op2 == (Op::Delete { r }),
    ensures ({
        let s1 = step(validated(), u, s, q, Op::Update { r, v }, false).0;
        let s2 = step(validated(), u, s1, q, Op::TCommit, false).0;
        step(validated(), u, s2, p, op2, ch) == (set_pending(s2, p, Some(op2)), Obs::Pending)
    }),
{
    gen_wait_after_inner_commit(validated(), u, s, q, p, r, v, op2, ch); // LOCATE ctl_dml_ignores_row_locks ctl_row_lock_statement_only
}

/// proofs-breadth/PROOFS.md section 4, P-A2 (proofs-pa3 unchanged): "no two open writers on one edge" (row lock on the
/// edge row): a second writer's UPDATE / DELETE of the row waits for the first's transaction.
pub proof fn premise_breadth_p_a2(u: U, s: State, q: usize, p: usize, r: usize, v: Val, op2: Op, ch: bool)
    requires wf(u, s), ready(s, q), ready(s, p), p != q, level(s.procs[q as int]) > 0, row_ok(u, r), s.g[r as int] is Some,
        !row_held(s, q, r), op2 == (Op::Update { r, v }) || op2 == (Op::Delete { r }),
    ensures ({
        let s1 = step(validated(), u, s, q, Op::Update { r, v }, false).0;
        step(validated(), u, s1, p, op2, ch) == (set_pending(s1, p, Some(op2)), Obs::Pending)
    }),
{
    gen_wait_after_update(validated(), u, s, q, p, r, v, op2, ch); // LOCATE ctl_dml_ignores_row_locks ctl_row_lock_statement_only
}

// ================================================================================================ visibility

/// proofs-d1f/PROOFS.md section 9, P-U2 ("readers see committed state only"): SHOWN FALSE by the contract: a reader
/// reads a value the writer's transaction then rolls back.
pub proof fn premise_d1f_p_u2_false(u: U, s: State, q: usize, p: usize, c: usize, v: Val)
    requires wf(u, s), ready(s, q), ready(s, p), p != q, fresh_txn(s.procs[q as int]), is_glob(u, c as int), s.g[c as int] != Some(v),
    ensures ({
        let s1 = step(validated(), u, s, q, Op::Set { c, v }, false).0;
        let r2 = step(validated(), u, s1, p, Op::Get { c }, false);
        let s3 = step(validated(), u, r2.0, q, Op::TRollback, false).0;
        &&& r2.1 == Obs::Value(Some(v))
        &&& s3.g[c as int] != Some(v)
    }),
{
    gen_dirty_read(validated(), u, s, q, p, c, v); // LOCATE ctl_no_dirty_reads
}

/// proofs-d1e/PROOFS.md section 8, P-C5 ("writes commit as they are made: no reader sees an uncommitted write and none is
/// rolled back"): SHOWN FALSE (the same witness).
pub proof fn premise_d1e_p_c5_false(u: U, s: State, q: usize, p: usize, c: usize, v: Val)
    requires wf(u, s), ready(s, q), ready(s, p), p != q, fresh_txn(s.procs[q as int]), is_glob(u, c as int), s.g[c as int] != Some(v),
    ensures ({
        let s1 = step(validated(), u, s, q, Op::Set { c, v }, false).0;
        let r2 = step(validated(), u, s1, p, Op::Get { c }, false);
        let s3 = step(validated(), u, r2.0, q, Op::TRollback, false).0;
        &&& r2.1 == Obs::Value(Some(v))
        &&& s3.g[c as int] != Some(v)
    }),
{
    gen_dirty_read(validated(), u, s, q, p, c, v); // LOCATE ctl_no_dirty_reads
}

/// proofs-d1d/PROOFS.md (the model's read "runs in another process than the writer's and still sees its rows, by dirty
/// reads (premise P-0002)"): a SELECT lists a row another transaction inserted and has not committed.
pub proof fn premise_d1d_p_0002(u: U, s: State, q: usize, p: usize, r: usize, v: Val)
    requires wf(u, s), ready(s, q), ready(s, p), p != q, level(s.procs[q as int]) > 0, row_ok(u, r), s.g[r as int] is None,
        !row_held(s, q, r),
    ensures ({
        let s1 = step(validated(), u, s, q, Op::Insert { r, v }, false).0;
        let r2 = step(validated(), u, s1, p, Op::Select { t: u.table[r as int] }, false);
        &&& s1.g[r as int] == Some(v)
        &&& r2.1 == select_obs(u, s1.g, u.table[r as int])
    }),
{
    gen_select_sees_insert(validated(), u, s, q, p, r, v); // LOCATE ctl_select_committed_only
}

/// models/core MA-6: "a reader sees another txn's uncommitted DELETE": a SELECT reads the state with the row gone.
pub proof fn premise_core_ma_6(u: U, s: State, q: usize, p: usize, r: usize)
    requires wf(u, s), ready(s, q), ready(s, p), p != q, level(s.procs[q as int]) > 0, row_ok(u, r), s.g[r as int] is Some,
        !row_held(s, q, r),
    ensures ({
        let s1 = step(validated(), u, s, q, Op::Delete { r }, false).0;
        let r2 = step(validated(), u, s1, p, Op::Select { t: u.table[r as int] }, false);
        &&& s1.g[r as int] is None
        &&& r2.1 == select_obs(u, s1.g, u.table[r as int])
    }),
{
    gen_select_sees_delete(validated(), u, s, q, p, r); // LOCATE ctl_select_committed_only
}

// ================================================================================================ rollback

/// models/core MA-5 and TRUST.md's narrowed P-1306 (E-ROLLBACK-OTHER): a rollback leaves a cell another process wrote
/// after this transaction wrote it.
pub proof fn premise_core_ma_5_rollback_other(u: U, s: State, q: usize, p: usize, c: usize, v: Val, w: Val)
    requires wf(u, s), ready(s, q), ready(s, p), p != q, fresh_txn(s.procs[q as int]), (c as int) < u.n(), v != w,
    ensures ({
        let s1 = step(validated(), u, s, q, Op::Set { c, v }, false).0;
        let s2 = step(validated(), u, s1, p, Op::Set { c, v: w }, false).0;
        step(validated(), u, s2, q, Op::TRollback, false).0.g[c as int] == Some(w)
    }),
{
    gen_rollback_keeps_other(validated(), u, s, q, p, c, v, w); // LOCATE ctl_rollback_physical
}

/// The erasure's rollback (proofs-d9's EraseAbort; E-ROLLBACK-OTHER): a row the open erasure deleted and another process
/// then inserted (a permitted outcome) survives the erasure's rollback.
pub proof fn premise_d9_erasure_rollback(u: U, s: State, q: usize, p: usize, r: usize, y: Val)
    requires wf(u, s), ready(s, q), ready(s, p), p != q, fresh_txn(s.procs[q as int]), row_ok(u, r), s.g[r as int] is Some,
        !row_held(s, q, r),
    ensures ({
        let s1 = step(validated(), u, s, q, Op::Delete { r }, false).0;
        let s2 = step(validated(), u, s1, p, Op::Insert { r, v: y }, true).0;
        &&& s2.g[r as int] == Some(y)
        &&& step(validated(), u, s2, q, Op::TRollback, false).0.g[r as int] == Some(y)
    }),
{
    gen_erasure_rollback_keeps_insert(validated(), u, s, q, p, r, y); // LOCATE ctl_rollback_physical ctl_freedom_wait_only
}

/// proofs-breadth/PROOFS.md section 4, P-A6 (proofs-pa3 unchanged): "rollback restores before-images of nodes the
/// transaction set or killed; $Increment is not undone". KILL part (SET: lemma_fresh_set_rollback, any reading; the
/// caveat for a node another process wrote since: premise_core_ma_5_rollback_other).
pub proof fn premise_breadth_p_a6_kill(u: U, s: State, q: usize, c: usize)
    requires wf(u, s), ready(s, q), fresh_txn(s.procs[q as int]), is_glob(u, c as int), s.g[c as int] is Some,
        forall|j: int| 0 <= j < u.n() && j != c as int ==> !covers(u, c as int, j),
    ensures step(validated(), u, step(validated(), u, s, q, Op::Kill { c }, false).0, q, Op::TRollback, false).0.g[c as int] == s.g[c as int],
{
    gen_kill_rollback(validated(), u, s, q, c); // LOCATE ctl_kill_not_logged
}

/// P-A6, $INCREMENT part (and proofs-d1c P-T3 below): $INCREMENT logs nothing.
pub proof fn premise_breadth_p_a6_incr(u: U, s: State, p: usize, c: usize)
    requires wf(u, s), ready(s, p), (c as int) < u.n(),
    ensures step(validated(), u, s, p, Op::Incr { c }, false).0.procs[p as int].undo == s.procs[p as int].undo,
{
    gen_incr_unlogged(validated(), u, s, p, c); // LOCATE ctl_incr_rolled_back
}

/// proofs-d1c/PROOFS.md section 7, P-T3: "the bucket's writes are not rolled back" ($Increment).
pub proof fn premise_d1c_p_t3(u: U, s: State, p: usize, c: usize)
    requires wf(u, s), ready(s, p), (c as int) < u.n(),
    ensures step(validated(), u, s, p, Op::Incr { c }, false).0.procs[p as int].undo == s.procs[p as int].undo,
{
    gen_incr_unlogged(validated(), u, s, p, c); // LOCATE ctl_incr_rolled_back
}

/// proofs-d1c/PROOFS.md section 7, P-L3 ("statement ids and edge_ids are fresh: stmtNext and the %ID counter only grow"),
/// for counters written only by $INCREMENT: such a cell is in no undo log and every step leaves or increments it.
/// (stmtNext is a SET inside the head-locked commit, LedgerApply.cls:162-163: P-C01's theorem; the %ID counter is
/// outside the contract.)
pub proof fn premise_d1c_p_l3_counter(u: U, s: State, p: usize, op: Op, ch: bool, c: usize)
    requires wf(u, s), wf_op(u, op), (p as int) < s.procs.len(), is_glob(u, c as int),
        forall|q: int| 0 <= q < s.procs.len() ==> !log_has(#[trigger] s.procs[q].undo, c as int),
        wr_of(u, s, p, op)(c as int) ==> op == (Op::Incr { c }),
    ensures ({
        let s2 = step(validated(), u, s, p, op, ch).0;
        &&& forall|q: int| 0 <= q < s2.procs.len() ==> !log_has(#[trigger] s2.procs[q].undo, c as int)
        &&& s2.g[c as int] == s.g[c as int] || (op == (Op::Incr { c }) && s2.g[c as int] == Some(Val::Num((num_of(u, s.g[c as int]) + 1) as i64)))
    }),
{
    gen_counter(validated(), u, s, p, op, ch, c); // LOCATE ctl_incr_rolled_back
}

/// contract-2 S-1 (Txn_Undo) and `_write_txn` (E-PARTIAL): TROLLBACK 1 at a nested level ends only that level.
pub proof fn premise_contract2_s1_partial(u: U, s: State, p: usize)
    requires wf(u, s), ready(s, p), level(s.procs[p as int]) >= 2,
    ensures ({
        let s2 = step(validated(), u, s, p, Op::TRollbackOne, false).0;
        &&& level(s2.procs[p as int]) == level(s.procs[p as int]) - 1
        &&& s2.procs[p as int].undo == s.procs[p as int].undo.subrange(0, top_mark(s.procs[p as int]) as int)
    }),
{
    gen_partial(validated(), u, s, p); // LOCATE ctl_rollback_one_undoes_all
}

/// TRUST.md, product premise of Txn.cls:8 / _write_txn.py:15 ("SQL COMMIT and ROLLBACK end every level", measured on
/// 2026.3): SHOWN FALSE for this engine: SQL COMMIT at a nested level leaves a transaction open.
pub proof fn premise_trust_txn_cls_8_false(u: U, s: State, p: usize)
    requires wf(u, s), ready(s, p), level(s.procs[p as int]) >= 2,
    ensures level(step(validated(), u, s, p, Op::SqlCommit, false).0.procs[p as int]) >= 1,
{
    gen_sql_commit_one(validated(), u, s, p); // LOCATE ctl_sql_commit_ends_all
}

// ================================================================================================ E-1 (proofs-env2)

/// TRUST.md, new premise "Embedded SQL (&sql) behaves as dynamic SQL for the clauses used" (contract-2 E-1, validated
/// executably by env2-e1-r1): the embedded statement equals the dynamic one in effect, visibility and waiting.
pub proof fn premise_trust_e1(u: U, s: State, p: usize, r: usize, ins: Option<Val>)
    ensures emb_dml(validated(), u, s, p, r, ins) == plain_dml(validated(), u, s, p, r, ins),
        emb_visible(validated(), s, p, r) == (s.g[r as int] is Some),
        blocked(validated(), u, s, p, Op::EmbRetract { r }) == blocked(validated(), u, s, p, Op::Delete { r }),
        blocked(validated(), u, s, p, Op::EmbRegister { r }) == freedom_cond(validated(), s, p, r),
{
    gen_e1(validated(), u, s, p, r, ins); // LOCATE ctl_emb_own_txn ctl_emb_ignores_autocommit ctl_emb_select_committed_only ctl_emb_ignores_row_locks
}

/// proofs-d1e P-M2, the part the contract states (X-STMT): one SQL statement is one atomic step even when it writes
/// several rows -- an INSERT ... SELECT that fails on a row leaves the globals as they were.
pub proof fn premise_d1e_p_m2_stmt_atomic(u: U, s: State, p: usize, from: usize, to: usize)
    requires !others_hold_rows(s, p), u.texists[from as int], u.texists[to as int],
        twins_ok(u, to, rows_from(u, s.g, from, 0)), first_fail(u, s.g, to, rows_from(u, s.g, from, 0), 0) is Some,
    ensures insert_select(validated(), u, s, p, from, to).0.g == s.g,
        insert_select(validated(), u, s, p, from, to).1 == Obs::SqlError(-119i64),
{
    gen_stmt_atomic(validated(), u, s, p, from, to); // LOCATE ctl_statement_not_atomic
}

} // verus!
