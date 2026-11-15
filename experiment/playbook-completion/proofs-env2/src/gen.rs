//! Generic consequences of the contract's clauses, each with the clause it needs as an explicit precondition (so a
//! control that weakens the clause makes exactly the premise theorems that call it fail, at the call).
use vstd::prelude::*;
use crate::spec::*;
use crate::wf::*;
use crate::effects::*;
use crate::headlock::*;
use crate::ext::*;

verus! {

pub open spec fn ready(s: State, p: usize) -> bool {
    (p as int) < s.procs.len() && s.procs[p as int].alive && s.procs[p as int].pending is None
}

pub open spec fn row_ok(u: U, r: usize) -> bool {
    (r as int) < u.n() && u.is_row[r as int] && u.texists[u.table[r as int] as int] && !u.long[r as int]
}

/// q is at the start of its first level (TSTART from level 0): one mark at 0, nothing logged.
pub open spec fn fresh_txn(pr: Proc) -> bool {
    pr.marks == seq![0nat] && pr.undo.len() == 0
}

// ------------------------------------------------------------------------------------------------ the head lock

pub open spec fn hl_hyp(sem: Sem, u: U, s: State, p: usize, op: Op, hl: usize, R: spec_fn(int) -> bool, h: usize) -> bool {
    &&& inv_h(sem, u, s, hl, R)
    &&& disc(u, s, p, op, hl, R)
    &&& wf_op(u, op)
    &&& (p as int) < s.procs.len()
    &&& r_glob(u, R)
    &&& is_glob(u, hl as int)
    &&& (h as int) < s.procs.len()
    &&& excl(s.procs[h as int].locks[hl as int])
    &&& level(s.procs[h as int]) > 0
}

pub open spec fn hl_concl(sem: Sem, u: U, s: State, p: usize, op: Op, ch: bool, hl: usize, R: spec_fn(int) -> bool, h: usize) -> bool {
    let s2 = step(sem, u, s, p, op, ch).0;
    &&& inv_h(sem, u, s2, hl, R)
    &&& holder_rel(sem, s, s2, h as int, R)
    &&& (level(s2.procs[h as int]) > 0 && s2.procs[h as int].alive ==> excl(s2.procs[h as int].locks[hl as int]))
}

/// G1: inv_h is inductive and the holder's transaction is one atomic step (headlock.rs), under its clauses.
pub proof fn gen_head_lock(sem: Sem, u: U, s: State, p: usize, op: Op, ch: bool, hl: usize, R: spec_fn(int) -> bool, h: usize)
    requires hl_sem(sem), hl_hyp(sem, u, s, p, op, hl, R, h),
    ensures hl_concl(sem, u, s, p, op, ch, hl, R, h),
{
    theorem_inv_h(sem, u, s, p, op, ch, hl, R);
    theorem_atomic(sem, u, s, p, op, ch, hl, R, h);
}

/// G2: the initial state satisfies inv_h (every process alive at level 0 with nothing held or logged).
pub proof fn gen_init_inv_h(sem: Sem, u: U, case: Case, hl: usize, R: spec_fn(int) -> bool)
    requires u.n() <= usize::MAX, case.nprocs <= usize::MAX,
    ensures inv_h(sem, u, init_state(u, case), hl, R),
{
    let s = init_state(u, case);
    assert forall|q: int| 0 <= q < s.procs.len() implies wf_proc(u, #[trigger] s.procs[q]) && clean_proc(s.procs[q]) by {
        assert(s.procs[q] == init_proc(u, kind_of(case, q)));
    }
    assert forall|q1: int, q2: int, m1: int, m2: int|
        0 <= q1 < s.procs.len() && 0 <= q2 < s.procs.len() && q1 != q2 && s.procs[q1].alive && s.procs[q2].alive
            && 0 <= m1 < u.n() && 0 <= m2 < u.n() && related(sem, u, m1, m2) && excl(#[trigger] s.procs[q1].locks[m1])
        implies !any(#[trigger] s.procs[q2].locks[m2]) by {
        assert(s.procs[q1] == init_proc(u, kind_of(case, q1)));
    }
    assert forall|q: int| 0 <= q < s.procs.len() && has_r(#[trigger] s.procs[q].undo, R)
        implies excl(s.procs[q].locks[hl as int]) && s.procs[q].alive by {
        assert(s.procs[q] == init_proc(u, kind_of(case, q)));
    }
}

/// G18 (P-C04 is not implied): any live process may stop any other at any moment; the stopped process's open
/// transaction (for example an erasure between its two steps) is then ended by the engine.
pub proof fn gen_abort_permitted(sem: Sem, u: U, s: State, p: usize, t: usize)
    requires wf(u, s), ready(s, p), (t as int) < s.procs.len(), s.procs[t as int].alive, level(s.procs[t as int]) > 0,
    ensures permits(sem, u, s, p, Op::Terminate { target: t }, stop(sem, s, t), Obs::Ok),
        !stop(sem, s, t).procs[t as int].alive,
{
    lemma_stop_wf(sem, u, s, t);
    assert(!choice_point(sem, u, s, p, Op::Terminate { target: t }));
    assert(outcomes(sem, u, s, p, Op::Terminate { target: t })[0] == (stop(sem, s, t), Obs::Ok));
}

/// G19 (E-NEST, P-B2): an inner TCOMMIT only lowers the level: the log (so what an outer rollback undoes) and the
/// globals are unchanged.
pub proof fn gen_inner_commit(sem: Sem, u: U, s: State, p: usize)
    requires wf(u, s), ready(s, p), level(s.procs[p as int]) >= 2,
    ensures ({
        let s2 = step(sem, u, s, p, Op::TCommit, false).0;
        &&& level(s2.procs[p as int]) == level(s.procs[p as int]) - 1
        &&& s2.procs[p as int].undo == s.procs[p as int].undo
        &&& s2.g == s.g
    }),
{
}

// ------------------------------------------------------------------------------------------------ stop and locks

/// G17 (E-STOP, P-0001): a stop rolls back every level of the stopped process and releases all its locks.
pub proof fn gen_stop_all_levels(sem: Sem, u: U, s: State, p: usize, t: usize)
    requires sem.stop_rolls_back && sem.stop_all_levels, wf(u, s), ready(s, p), (t as int) < s.procs.len(),
        s.procs[t as int].alive,
    ensures ({
        let s2 = step(sem, u, s, p, Op::Terminate { target: t }, false).0;
        &&& s2.g == rollback_all(sem, s, t).g
        &&& level(s2.procs[t as int]) == 0
        &&& !s2.procs[t as int].alive
        &&& forall|m: int| 0 <= m < u.n() ==> !any(#[trigger] s2.procs[t as int].locks[m])
    }),
{
    let l = level(s.procs[t as int]);
    lemma_rollback_n_level(sem, u, s, t, l);
    lemma_rollback_n_wf(sem, u, s, t, l);
    let s2 = step(sem, u, s, p, Op::Terminate { target: t }, false).0;
    assert(s2 == stop(sem, s, t));
    let pr = rollback_all(sem, s, t).procs[t as int];
    assert(wf_proc(u, pr));
    assert forall|m: int| 0 <= m < u.n() implies !any(#[trigger] s2.procs[t as int].locks[m]) by {
        assert(s2.procs[t as int].locks[m] == zero_hold());
    }
}

/// G13 (E-LOCK-DEFER, P-0003): an unlock inside a transaction keeps the lock until the outermost end: the process
/// still holds it exclusively and another process's request is refused.
pub proof fn gen_deferred_unlock(sem: Sem, u: U, s: State, p: usize, q: usize, c: usize)
    requires sem.unlock_deferred, wf(u, s), ready(s, p), ready(s, q), p != q, level(s.procs[p as int]) > 0,
        is_glob(u, c as int), s.procs[p as int].locks[c as int].e > 0, s.procs[p as int].locks[c as int].de < u64::MAX,
    ensures ({
        let s2 = step(sem, u, s, p, Op::Unlock { c, mode: Mode::E, immediate: false }, false).0;
        &&& excl(s2.procs[p as int].locks[c as int])
        &&& step(sem, u, s2, q, Op::Lock { c, mode: Mode::E, wait: false }, false).1 == Obs::Test(false)
    }),
{
    let s2 = step(sem, u, s, p, Op::Unlock { c, mode: Mode::E, immediate: false }, false).0;
    assert(wf_proc(u, s.procs[p as int]));
    assert(u.paths[c as int].subrange(0, u.paths[c as int].len() as int) =~= u.paths[c as int]);
    assert(covers(u, c as int, c as int));
    assert(s2.procs[q as int] == s.procs[q as int]);
    assert(conflicts(sem, u, s2, q, c, Mode::E)) by {
        assert(hold_conflicts(sem, s2.procs[p as int].locks[c as int], Mode::E));
    }
}

/// No other live process (besides `t`) holds a hold conflicting with `mode` on a name related to c.
pub open spec fn only_t_conflicts(sem: Sem, u: U, s: State, q: usize, t: usize, c: usize, mode: Mode) -> bool {
    forall|y: int, m: int| 0 <= y < s.procs.len() && y != q && y != t && s.procs[y].alive && 0 <= m < u.n()
        && related(sem, u, m, c as int) ==> !hold_conflicts(sem, #[trigger] s.procs[y].locks[m], mode)
}

/// G14 (E-LOCK-WAIT with E-STOP; PF-3, P-F4): a process waiting for a lock that only t holds is granted it at its
/// next `Await` once t is stopped.
pub proof fn gen_waiter_after_stop(sem: Sem, u: U, s: State, p: usize, q: usize, t: usize, c: usize, mode: Mode)
    requires sem.lock_wait_grants, wf(u, s), ready(s, p), p != q, q != t, (q as int) < s.procs.len(), s.procs[q as int].alive,
        s.procs[q as int].pending == Some(Op::Lock { c, mode, wait: true }), (t as int) < s.procs.len(), s.procs[t as int].alive,
        (c as int) < u.n(), only_t_conflicts(sem, u, s, q, t, c, mode),
        s.procs[q as int].locks[c as int].e < u64::MAX, s.procs[q as int].locks[c as int].s < u64::MAX,
    ensures ({
        let s2 = step(sem, u, s, p, Op::Terminate { target: t }, false).0;
        step(sem, u, s2, q, Op::Await, false).1 == Obs::Test(true)
    }),
{
    let s2 = step(sem, u, s, p, Op::Terminate { target: t }, false).0;
    lemma_stop_wf(sem, u, s, t);
    assert(s2 == stop(sem, s, t));
    let w = |x: int| false;
    lemma_stop_eff(sem, u, s, t, w);
    assert(s2.procs[q as int] == s.procs[q as int]);
    assert(!conflicts(sem, u, s2, q, c, mode)) by {
        assert forall|y: int, m: int| 0 <= y < s2.procs.len() && y != q && s2.procs[y].alive && 0 <= m < u.n()
            && related(sem, u, m, c as int) implies !hold_conflicts(sem, #[trigger] s2.procs[y].locks[m], mode) by {
            if y != t as int { assert(s2.procs[y] == s.procs[y]); }
        }
    }
}

/// G14b (PF-3 "every erasure ends: its commit releases the head lock"): at the outermost commit, the holds a
/// process released inside its transaction are gone.
pub proof fn gen_commit_releases(sem: Sem, u: U, s: State, p: usize, c: usize)
    requires wf(u, s), ready(s, p), level(s.procs[p as int]) == 1, (c as int) < u.n(),
        s.procs[p as int].locks[c as int].e == 0, s.procs[p as int].locks[c as int].s == 0,
    ensures !any(step(sem, u, s, p, Op::TCommit, false).0.procs[p as int].locks[c as int]),
{
    assert(wf_proc(u, s.procs[p as int]));
}

/// G15 (E-LOCK-NAMES; R04-5's guard in proofs-pa3): an exclusive lock on a name excludes every lock on its
/// descendants.
pub proof fn gen_hierarchy(sem: Sem, u: U, s: State, p: usize, q: usize, a: usize, b: usize, mode: Mode)
    requires sem.hierarchical, wf(u, s), (p as int) < s.procs.len(), s.procs[p as int].alive, ready(s, q), p != q,
        covers(u, a as int, b as int), excl(s.procs[p as int].locks[a as int]),
    ensures step(sem, u, s, q, Op::Lock { c: b, mode, wait: false }, false).1 == Obs::Test(false),
{
    assert(related(sem, u, a as int, b as int));
    assert(hold_conflicts(sem, s.procs[p as int].locks[a as int], mode));
    assert(conflicts(sem, u, s, q, b, mode));
}

/// G16 (E-LOCK-MODES; P-A4 of proofs-breadth): shared holds are compatible: a shared request is granted while
/// another process holds the name shared.
pub proof fn gen_shared_compat(sem: Sem, u: U, s: State, p: usize, q: usize, c: usize)
    requires sem.shared_compatible, wf(u, s), ready(s, p), (q as int) < s.procs.len(), q != p, s.procs[q as int].alive,
        (c as int) < u.n(), s.procs[q as int].locks[c as int].s > 0,
        forall|y: int, m: int| 0 <= y < s.procs.len() && y != p && s.procs[y].alive && 0 <= m < u.n()
            && related(sem, u, m, c as int) ==> !excl(#[trigger] s.procs[y].locks[m]),
        s.procs[p as int].locks[c as int].s < u64::MAX,
    ensures step(sem, u, s, p, Op::Lock { c, mode: Mode::S, wait: false }, false).1 == Obs::Test(true),
{
    assert(wf_proc(u, s.procs[p as int]));
    assert(!conflicts(sem, u, s, p, c, Mode::S));
}

// ------------------------------------------------------------------------------------------------ row locks

/// G4 (E-ROWLOCK; P-1201, P-D9-2, P-L5, P-A2): after q updates a visible row inside its transaction, another process's
/// UPDATE or DELETE of the row waits (writes nothing).
pub proof fn gen_wait_after_update(sem: Sem, u: U, s: State, q: usize, p: usize, r: usize, v: Val, op2: Op, ch: bool)
    requires sem.dml_waits && sem.row_lock_held, wf(u, s), ready(s, q), ready(s, p), p != q, level(s.procs[q as int]) > 0,
        row_ok(u, r), s.g[r as int] is Some, !row_held(s, q, r),
        op2 == (Op::Update { r, v }) || op2 == (Op::Delete { r }),
    ensures ({
        let s1 = step(sem, u, s, q, Op::Update { r, v }, false).0;
        &&& s1.procs[q as int].rlocks[r as int]
        &&& step(sem, u, s1, p, op2, ch) == (set_pending(s1, p, Some(op2)), Obs::Pending)
    }),
{
    let s1 = step(sem, u, s, q, Op::Update { r, v }, false).0;
    assert(wf_proc(u, s.procs[q as int]));
    assert(s1.procs[p as int] == s.procs[p as int]);
    assert(s1.g[r as int] == Some(v));
    assert(s1.procs[q as int].rlocks[r as int]);
    assert(row_held(s1, p, r));
}

/// G4b (E-ROWLOCK; P-1201): after q inserts a row inside its transaction, another process's UPDATE or DELETE of it
/// waits.
pub proof fn gen_wait_after_insert(sem: Sem, u: U, s: State, q: usize, p: usize, r: usize, v: Val, op2: Op, ch: bool)
    requires sem.dml_waits && sem.row_lock_held, wf(u, s), ready(s, q), ready(s, p), p != q,
        level(s.procs[q as int]) > 0, row_ok(u, r), s.g[r as int] is None, !row_held(s, q, r),
        op2 == (Op::Update { r, v }) || op2 == (Op::Delete { r }),
    ensures ({
        let s1 = step(sem, u, s, q, Op::Insert { r, v }, false).0;
        &&& s1.procs[q as int].rlocks[r as int]
        &&& step(sem, u, s1, p, op2, ch) == (set_pending(s1, p, Some(op2)), Obs::Pending)
    }),
{
    let s1 = step(sem, u, s, q, Op::Insert { r, v }, false).0;
    assert(wf_proc(u, s.procs[q as int]));
    assert(!freedom_cond(sem, s, q, r));
    assert(s1.procs[p as int] == s.procs[p as int]);
    assert(s1.g[r as int] == Some(v));
    assert(s1.procs[q as int].alive);
    assert(s1.procs[q as int].rlocks[r as int]);
    assert(row_held(s1, p, r));
}

/// G4c (P-L5): the row lock of a write made inside a nested level survives the inner TCOMMIT: another process's
/// UPDATE or DELETE of the row still waits.
pub proof fn gen_wait_after_inner_commit(sem: Sem, u: U, s: State, q: usize, p: usize, r: usize, v: Val, op2: Op, ch: bool)
    requires sem.dml_waits && sem.row_lock_held, wf(u, s), ready(s, q), ready(s, p), p != q, level(s.procs[q as int]) >= 2,
        row_ok(u, r), s.g[r as int] is Some, !row_held(s, q, r),
        op2 == (Op::Update { r, v }) || op2 == (Op::Delete { r }),
    ensures ({
        let s1 = step(sem, u, s, q, Op::Update { r, v }, false).0;
        let s2 = step(sem, u, s1, q, Op::TCommit, false).0;
        &&& level(s2.procs[q as int]) >= 1
        &&& step(sem, u, s2, p, op2, ch) == (set_pending(s2, p, Some(op2)), Obs::Pending)
    }),
{
    let s1 = step(sem, u, s, q, Op::Update { r, v }, false).0;
    assert(wf_proc(u, s.procs[q as int]));
    assert(s1.procs[q as int].rlocks[r as int]);
    let s2 = step(sem, u, s1, q, Op::TCommit, false).0;
    assert(s2.procs[q as int].rlocks[r as int]);
    assert(s2.procs[p as int] == s.procs[p as int]);
    assert(row_held(s2, p, r));
}

/// G5 (E-UNIQUE; P-D9-2's insert case, `_write_txn.is_duplicate`): an INSERT of a key whose row is visible (another
/// transaction's uncommitted insert included) fails at once with -119; it does not wait.
pub proof fn gen_insert_dup_fails(sem: Sem, u: U, s: State, p: usize, r: usize, v: Val, ch: bool)
    requires !sem.insert_dup_waits, wf(u, s), ready(s, p), row_ok(u, r), s.g[r as int] is Some,
    ensures step(sem, u, s, p, Op::Insert { r, v }, ch).1 == Obs::SqlError(-119i64),
{
}

/// G6 (the Freedom; P-D9-2's "a bypass write waits for a row the open erasure deleted"): an INSERT of a key whose row
/// another open transaction deleted may wait AND may proceed: both outcomes are permitted, so the wait is not implied.
pub proof fn gen_freedom_both(sem: Sem, u: U, s: State, p: usize, q: usize, r: usize, v: Val)
    requires sem.freedom == FreedomSem::Both && sem.dml_waits, wf(u, s), ready(s, p), (q as int) < s.procs.len(), q != p,
        s.procs[q as int].alive, s.procs[q as int].rlocks[r as int], row_ok(u, r), s.g[r as int] is None,
    ensures
        permits(sem, u, s, p, Op::Insert { r, v }, set_pending(s, p, Some(Op::Insert { r, v })), Obs::Pending),
        permits(sem, u, s, p, Op::Insert { r, v }, step(sem, u, s, p, Op::Insert { r, v }, true).0, Obs::Count(1i64)),
{
    let op = Op::Insert { r, v };
    assert(row_held(s, p, r));
    assert(choice_point(sem, u, s, p, op));
    assert(outcomes(sem, u, s, p, op)[0] == (set_pending(s, p, Some(op)), Obs::Pending));
    assert(outcomes(sem, u, s, p, op)[1] == step(sem, u, s, p, op, true));
    assert(step(sem, u, s, p, op, true).1 == Obs::Count(1i64));
}

// ------------------------------------------------------------------------------------------------ visibility

/// G7 (E-VIS; P-U2 and P-C5 shown false, P-0002): a reader sees another transaction's uncommitted write, which that
/// transaction then rolls back: the value read was never committed.
pub proof fn gen_dirty_read(sem: Sem, u: U, s: State, q: usize, p: usize, c: usize, v: Val)
    requires sem.dirty_reads, wf(u, s), ready(s, q), ready(s, p), p != q, fresh_txn(s.procs[q as int]), is_glob(u, c as int),
        s.g[c as int] != Some(v),
    ensures ({
        let s1 = step(sem, u, s, q, Op::Set { c, v }, false).0;
        let r2 = step(sem, u, s1, p, Op::Get { c }, false);
        let s3 = step(sem, u, r2.0, q, Op::TRollback, false).0;
        &&& r2.1 == Obs::Value(Some(v))
        &&& s3.g[c as int] == s.g[c as int]
        &&& s3.g[c as int] != Some(v)
    }),
{
    let s1 = step(sem, u, s, q, Op::Set { c, v }, false).0;
    assert(wf_proc(u, s.procs[q as int]));
    let r2 = step(sem, u, s1, p, Op::Get { c }, false);
    assert(r2.0 == s1);
    lemma_fresh_set_rollback(sem, u, s, q, c, v);
}

/// One logged SET at the start of a transaction, then TROLLBACK, restores the cell (any rollback reading).
pub proof fn lemma_fresh_set_rollback(sem: Sem, u: U, s: State, q: usize, c: usize, v: Val)
    requires wf(u, s), ready(s, q), fresh_txn(s.procs[q as int]), (c as int) < u.n(),
    ensures step(sem, u, step(sem, u, s, q, Op::Set { c, v }, false).0, q, Op::TRollback, false).0.g[c as int] == s.g[c as int],
{
    reveal_with_fuel(rb, 3);
    reveal_with_fuel(rollback_n, 3);
    let s1 = step(sem, u, s, q, Op::Set { c, v }, false).0;
    assert(wf_proc(u, s.procs[q as int]));
    let pr1 = s1.procs[q as int];
    assert(pr1.undo == seq![Undo { c, old: s.g[c as int], written: Some(v), ppg: false }]);
    assert(level(pr1) == 1);
    let u1 = undo_top(sem, s1, q);
    assert(top_mark(pr1) == 0);
    assert(pr1.undo.subrange(0, 1) =~= pr1.undo);
    assert(pr1.undo.subrange(0, 1).drop_last() =~= Seq::<Undo>::empty());
    assert(u1.g[c as int] == s.g[c as int]);
    lemma_write_wf(u, s, q, c, Some(v), true);
    lemma_undo_top_level(sem, u, s1, q);
    assert(rollback_n(sem, s1, q, 1) == rollback_n(sem, u1, q, 0));
}

/// G8 (E-VIS for SQL; P-0002 of proofs-d1d): a SELECT in another process lists a row another transaction inserted
/// and has not committed.
pub proof fn gen_select_sees_insert(sem: Sem, u: U, s: State, q: usize, p: usize, r: usize, v: Val)
    requires sem.select_dirty, wf(u, s), ready(s, q), ready(s, p), p != q,
        level(s.procs[q as int]) > 0, row_ok(u, r), s.g[r as int] is None, !row_held(s, q, r),
    ensures ({
        let s1 = step(sem, u, s, q, Op::Insert { r, v }, false).0;
        let r2 = step(sem, u, s1, p, Op::Select { t: u.table[r as int] }, false);
        &&& s1.g[r as int] == Some(v)
        &&& r2.1 == select_obs(u, s1.g, u.table[r as int])
    }),
{
    assert(wf_proc(u, s.procs[q as int]));
    assert(!freedom_cond(sem, s, q, r));
}

/// G8b (E-VIS; MA-6 of the core models): a SELECT in another process does not list a row another transaction deleted
/// and has not committed.
pub proof fn gen_select_sees_delete(sem: Sem, u: U, s: State, q: usize, p: usize, r: usize)
    requires sem.select_dirty, wf(u, s), ready(s, q), ready(s, p), p != q,
        level(s.procs[q as int]) > 0, row_ok(u, r), s.g[r as int] is Some, !row_held(s, q, r),
    ensures ({
        let s1 = step(sem, u, s, q, Op::Delete { r }, false).0;
        let r2 = step(sem, u, s1, p, Op::Select { t: u.table[r as int] }, false);
        &&& s1.g[r as int] is None
        &&& r2.1 == select_obs(u, s1.g, u.table[r as int])
    }),
{
    assert(wf_proc(u, s.procs[q as int]));
}

// ------------------------------------------------------------------------------------------------ rollback

/// G9 (E-ROLLBACK-OTHER; P-A6's caveat, the core models' M2): a rollback leaves a cell another process wrote after this
/// transaction wrote it.
pub proof fn gen_rollback_keeps_other(sem: Sem, u: U, s: State, q: usize, p: usize, c: usize, v: Val, w: Val)
    requires !sem.rollback_physical, wf(u, s), ready(s, q), ready(s, p), p != q, fresh_txn(s.procs[q as int]),
        (c as int) < u.n(), v != w,
    ensures ({
        let s1 = step(sem, u, s, q, Op::Set { c, v }, false).0;
        let s2 = step(sem, u, s1, p, Op::Set { c, v: w }, false).0;
        step(sem, u, s2, q, Op::TRollback, false).0.g[c as int] == Some(w)
    }),
{
    reveal_with_fuel(rb, 3);
    reveal_with_fuel(rollback_n, 3);
    let s1 = step(sem, u, s, q, Op::Set { c, v }, false).0;
    assert(wf_proc(u, s.procs[q as int]));
    lemma_write_wf(u, s, q, c, Some(v), true);
    let s2 = step(sem, u, s1, p, Op::Set { c, v: w }, false).0;
    assert(s2.procs[q as int] == s1.procs[q as int]);
    lemma_write_wf(u, s1, p, c, Some(w), true);
    let pr2 = s2.procs[q as int];
    assert(pr2.undo == seq![Undo { c, old: s.g[c as int], written: Some(v), ppg: false }]);
    let u2 = undo_top(sem, s2, q);
    assert(top_mark(pr2) == 0);
    assert(pr2.undo.subrange(0, 1) =~= pr2.undo);
    assert(pr2.undo.subrange(0, 1).drop_last() =~= Seq::<Undo>::empty());
    assert(u2.g[c as int] == Some(w));
    lemma_undo_top_level(sem, u, s2, q);
    assert(rollback_n(sem, s2, q, 1) == rollback_n(sem, u2, q, 0));
}

/// G9b (E-ROLLBACK-OTHER for an erasure; proofs-d9's EraseAbort): q deletes a row inside its transaction; another
/// process's INSERT of the key proceeds (a permitted outcome of the Freedom); q's rollback then leaves the new row.
pub proof fn gen_erasure_rollback_keeps_insert(sem: Sem, u: U, s: State, q: usize, p: usize, r: usize, y: Val)
    requires !sem.rollback_physical && sem.freedom != FreedomSem::WaitOnly, wf(u, s), ready(s, q), ready(s, p), p != q,
        fresh_txn(s.procs[q as int]), row_ok(u, r), s.g[r as int] is Some, !row_held(s, q, r),
    ensures ({
        let s1 = step(sem, u, s, q, Op::Delete { r }, false).0;
        let s2 = step(sem, u, s1, p, Op::Insert { r, v: y }, true).0;
        &&& s2.g[r as int] == Some(y)
        &&& step(sem, u, s2, q, Op::TRollback, false).0.g[r as int] == Some(y)
    }),
{
    reveal_with_fuel(rb, 3);
    reveal_with_fuel(rollback_n, 3);
    let s1 = step(sem, u, s, q, Op::Delete { r }, false).0;
    assert(wf_proc(u, s.procs[q as int]));
    assert(s1.g[r as int] is None);
    assert(s1.procs[p as int] == s.procs[p as int]);
    let pr1 = s1.procs[q as int];
    assert(pr1.undo == seq![Undo { c: r, old: s.g[r as int], written: None, ppg: false }]);
    lemma_run_dml_wf(sem, u, s, q, Op::Delete { r });
    let s2 = step(sem, u, s1, p, Op::Insert { r, v: y }, true).0;
    lemma_step_wf(sem, u, s1, p, Op::Insert { r, v: y }, true);
    lemma_step_eff(sem, u, s1, p, Op::Insert { r, v: y }, true);
    assert(actor(s1, p, Op::Insert { r, v: y }) == p);
    assert(s2.procs[q as int] == s1.procs[q as int]);
    assert(s2.g[r as int] == Some(y)) by {
        if sem.dml_waits && sem.row_lock_held {
            assert(s1.procs[q as int].rlocks[r as int]);
            assert(freedom_cond(sem, s1, p, r));
        }
    }
    let pr2 = s2.procs[q as int];
    let u2 = undo_top(sem, s2, q);
    assert(top_mark(pr2) == 0);
    assert(pr2.undo.subrange(0, 1) =~= pr2.undo);
    assert(pr2.undo.subrange(0, 1).drop_last() =~= Seq::<Undo>::empty());
    assert(u2.g[r as int] == Some(y));
    lemma_undo_top_level(sem, u, s2, q);
    assert(rollback_n(sem, s2, q, 1) == rollback_n(sem, u2, q, 0));
}

/// G20 (E-GLOBALS; P-A6): a KILL inside a transaction is undone by its rollback.
pub proof fn gen_kill_rollback(sem: Sem, u: U, s: State, q: usize, c: usize)
    requires sem.kill_logged, wf(u, s), ready(s, q), fresh_txn(s.procs[q as int]), is_glob(u, c as int), s.g[c as int] is Some,
        forall|j: int| 0 <= j < u.n() && j != c as int ==> !covers(u, c as int, j),
    ensures step(sem, u, step(sem, u, s, q, Op::Kill { c }, false).0, q, Op::TRollback, false).0.g[c as int] == s.g[c as int],
{
    reveal_with_fuel(rb, 3);
    reveal_with_fuel(rollback_n, 3);
    let s1 = step(sem, u, s, q, Op::Kill { c }, false).0;
    assert(wf_proc(u, s.procs[q as int]));
    lemma_kill_single(sem, u, s, q, c, 0);
    let pr1 = s1.procs[q as int];
    assert(pr1.undo == seq![Undo { c, old: s.g[c as int], written: None, ppg: false }]);
    lemma_kill_wf(sem, u, s, q, c, 0);
    let u1 = undo_top(sem, s1, q);
    assert(level(pr1) == 1);
    assert(top_mark(pr1) == 0);
    assert(pr1.undo.subrange(0, 1) =~= pr1.undo);
    assert(pr1.undo.subrange(0, 1).drop_last() =~= Seq::<Undo>::empty());
    assert(u1.g[c as int] == s.g[c as int]);
    lemma_undo_top_level(sem, u, s1, q);
    assert(rollback_n(sem, s1, q, 1) == rollback_n(sem, u1, q, 0));
}

/// KILL of a node that covers no other cell writes exactly that cell (logged).
pub proof fn lemma_kill_single(sem: Sem, u: U, s: State, q: usize, c: usize, j: nat)
    requires sem.kill_logged, wf(u, s), (q as int) < s.procs.len(), is_glob(u, c as int), j <= c as int + 1,
        forall|k: int| 0 <= k < u.n() && k != c as int ==> !covers(u, c as int, k),
    ensures j <= c as int && s.g[c as int] is Some ==> kill_from(sem, u, s, q, c, j) == write(s, q, c, None, true),
        j <= c as int && s.g[c as int] is None ==> kill_from(sem, u, s, q, c, j) == s,
        j == c as int + 1 ==> kill_from(sem, u, s, q, c, j) == s,
    decreases u.n() - j,
{
    if j < u.n() {
        assert(u.paths[c as int].subrange(0, u.paths[c as int].len() as int) =~= u.paths[c as int]);
        assert(covers(u, c as int, c as int));
        if j == c as int {
            if s.g[c as int] is Some {
                let s1 = write(s, q, c, None, true);
                lemma_write_wf(u, s, q, c, None, true);
                lemma_kill_rest(sem, u, s1, q, c, j + 1);
            } else {
                lemma_kill_rest(sem, u, s, q, c, j + 1);
            }
        } else if j < c as int {
            lemma_kill_single(sem, u, s, q, c, j + 1);
        } else {
            lemma_kill_rest(sem, u, s, q, c, j);
        }
    }
}

pub proof fn lemma_kill_rest(sem: Sem, u: U, s: State, q: usize, c: usize, j: nat)
    requires j > c as int, forall|k: int| 0 <= k < u.n() && k != c as int ==> !covers(u, c as int, k),
    ensures kill_from(sem, u, s, q, c, j) == s,
    decreases u.n() - j,
{
    if j < u.n() {
        lemma_kill_rest(sem, u, s, q, c, j + 1);
    }
}

/// G10 (E-INCR; P-T3, P-A6): $INCREMENT logs nothing, so no rollback undoes it.
pub proof fn gen_incr_unlogged(sem: Sem, u: U, s: State, p: usize, c: usize)
    requires sem.incr_survives, wf(u, s), ready(s, p), (c as int) < u.n(),
    ensures step(sem, u, s, p, Op::Incr { c }, false).0.procs[p as int].undo == s.procs[p as int].undo,
{
}

/// G10b (E-INCR; P-L3 of proofs-d1c for $INCREMENT counters): a cell that only $INCREMENT writes is in no undo log and
/// never goes back: every step leaves it or increments it.
pub proof fn gen_counter(sem: Sem, u: U, s: State, p: usize, op: Op, ch: bool, c: usize)
    requires sem.incr_survives, wf(u, s), wf_op(u, op), (p as int) < s.procs.len(), is_glob(u, c as int),
        forall|q: int| 0 <= q < s.procs.len() ==> !log_has(#[trigger] s.procs[q].undo, c as int),
        wr_of(u, s, p, op)(c as int) ==> op == (Op::Incr { c }),
    ensures ({
        let s2 = step(sem, u, s, p, op, ch).0;
        &&& forall|q: int| 0 <= q < s2.procs.len() ==> !log_has(#[trigger] s2.procs[q].undo, c as int)
        &&& s2.g[c as int] == s.g[c as int] || (op == (Op::Incr { c }) && s2.g[c as int] == Some(Val::Num((num_of(u, s.g[c as int]) + 1) as i64)))
    }),
{
    let s2 = step(sem, u, s, p, op, ch).0;
    let x = actor(s, p, op);
    let w = wr_of(u, s, p, op);
    lemma_step_eff(sem, u, s, p, op, ch);
    lemma_step_wf(sem, u, s, p, op, ch);
    assert forall|q: int| 0 <= q < s2.procs.len() implies !log_has(#[trigger] s2.procs[q].undo, c as int) by {
        if q != x as int {
            assert(s2.procs[q] == s.procs[q]);
        } else if log_has(s2.procs[q].undo, c as int) {
            let b = s2.procs[q].undo;
            let a = s.procs[q].undo;
            let i = choose|i: int| 0 <= i < b.len() && !(#[trigger] b[i]).ppg && b[i].c as int == c as int;
            if i < a.len() && b[i] == a[i] {
                assert(log_has(a, c as int));
            } else {
                assert(w(c as int));
                assert(op == (Op::Incr { c }));
                assert(b == a);
            }
        }
    }
    assert(s2.g[c as int] == s.g[c as int] || (op == (Op::Incr { c }) && s2.g[c as int] == Some(Val::Num((num_of(u, s.g[c as int]) + 1) as i64)))) by {
        if s2.g[c as int] != s.g[c as int] {
            assert(w(c as int) || log_has(s.procs[x as int].undo, c as int));
            assert(w(c as int));
        }
    }
}

// ------------------------------------------------------------------------------------------------ partial rollback, SQL COMMIT

/// G11 (E-PARTIAL; Txn_Undo / `_write_txn`): TROLLBACK 1 at a nested level ends only the top level: the outer
/// level's log entries stay (and stay undoable).
pub proof fn gen_partial(sem: Sem, u: U, s: State, p: usize)
    requires sem.rollback_one_is_one_level, wf(u, s), ready(s, p), level(s.procs[p as int]) >= 2,
    ensures ({
        let s2 = step(sem, u, s, p, Op::TRollbackOne, false).0;
        &&& level(s2.procs[p as int]) == level(s.procs[p as int]) - 1
        &&& s2.procs[p as int].undo == s.procs[p as int].undo.subrange(0, top_mark(s.procs[p as int]) as int)
    }),
{
}

/// G12 (E-SQL-END; the product premise of Txn.cls:8 / _write_txn.py:15 is false here): SQL COMMIT at a nested level
/// ends one level; a transaction stays open.
pub proof fn gen_sql_commit_one(sem: Sem, u: U, s: State, p: usize)
    requires sem.sql_commit == Ends::One, wf(u, s), ready(s, p), level(s.procs[p as int]) >= 2,
    ensures level(step(sem, u, s, p, Op::SqlCommit, false).0.procs[p as int]) == level(s.procs[p as int]) - 1,
        level(step(sem, u, s, p, Op::SqlCommit, false).0.procs[p as int]) >= 1,
{
    lemma_commit_n_level(u, s, p, 1);
    lemma_commit_n_wf(u, s, p, 1);
    let s2 = commit_n(s, p, 1);
    assert(end_levels(s, sem, p, Ends::One, true) == set_sqlflag(s2, p, false));
    assert(level(set_sqlflag(s2, p, false).procs[p as int]) == level(s2.procs[p as int]));
}

// ------------------------------------------------------------------------------------------------ E-1 (proofs-env2)

/// G21 (E-1, TRUST.md "Embedded SQL (&sql) behaves as dynamic SQL for the clauses used"): the pin's embedded DML has the
/// dynamic statement's effect and answer, its SELECT INTO sees what a dynamic SELECT sees (uncommitted rows included),
/// and its DELETE waits exactly when the dynamic DELETE does (its INSERT over another's uncommitted DELETE is the same
/// Freedom).
pub proof fn gen_e1(sem: Sem, u: U, s: State, p: usize, r: usize, ins: Option<Val>)
    requires !sem.emb_own_txn && !sem.emb_ignores_autocommit && !sem.emb_select_committed_only && !sem.emb_ignores_row_locks,
    ensures emb_dml(sem, u, s, p, r, ins) == plain_dml(sem, u, s, p, r, ins),
        emb_visible(sem, s, p, r) == (s.g[r as int] is Some),
        blocked(sem, u, s, p, Op::EmbRetract { r }) == blocked(sem, u, s, p, Op::Delete { r }),
        blocked(sem, u, s, p, Op::EmbRegister { r }) == freedom_cond(sem, s, p, r),
{
}

/// G22 (X-STMT, contract r6): an INSERT ... SELECT one of whose rows fails (its key present in the target) writes none of
/// its rows and answers -119: the statement is atomic.
pub proof fn gen_stmt_atomic(sem: Sem, u: U, s: State, p: usize, from: usize, to: usize)
    requires sem.statement_atomic, !others_hold_rows(s, p), u.texists[from as int], u.texists[to as int],
        twins_ok(u, to, rows_from(u, s.g, from, 0)), first_fail(u, s.g, to, rows_from(u, s.g, from, 0), 0) is Some,
    ensures insert_select(sem, u, s, p, from, to).0.g == s.g, insert_select(sem, u, s, p, from, to).1 == Obs::SqlError(-119i64),
{
}

} // verus!
