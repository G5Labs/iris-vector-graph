//! A transaction under an exclusive lock is one atomic step on the cells the lock protects (premises P-C01 of
//! `proofs/`, P-D9-1 of `proofs-d9`..`proofs-d9c`, P-L3 of `proofs-breadth`/`proofs-pa3`, P-B2 of `proofs-d1c`).
//!
//! Setting: a lock name H (the ledger's `^IVG.Ledger("head")`) and a set R of global cells it protects (the ledger's
//! globals). Discipline `disc` (product discipline, not the contract): a process writes a cell of R only while it
//! holds H exclusively inside a transaction, never with $INCREMENT, and never releases H with an immediate unlock.
//! Under the contract's clauses (lock modes and names, deferred unlock, KILL logged, stop rolls back every level)
//! `inv_h` is inductive over EVERY operation of EVERY process (theorem_inv_h), and for the process h holding H
//! (theorem_holder_step):
//! (A) while h's transaction is open, the committed state of R (`base`: what rolling back h's log leaves) does not
//!     change, whatever any process does, and h keeps H;
//! (B) when h's transaction ends, R holds either all of its writes (commit: R as just before) or none (rollback:
//!     the committed state);
//! (C) when h is stopped, R holds the committed state (a stopped one leaves nothing).
//! With no holder, R is committed (`base` of no one = the globals) and only a process holding H can change it
//! (theorem_no_holder_step); a process holding H in any mode reads R's committed state (theorem_reader_under_lock).
use vstd::prelude::*;
use crate::spec::*;
use crate::wf::*;
use crate::effects::*;

verus! {

pub open spec fn has_r(es: Seq<Undo>, R: spec_fn(int) -> bool) -> bool {
    exists|i: int| 0 <= i < es.len() && !(#[trigger] es[i]).ppg && R(es[i].c as int)
}

/// No two live processes hold conflicting locks on related names.
pub open spec fn lock_ok(sem: Sem, u: U, s: State) -> bool {
    forall|q1: int, q2: int, m1: int, m2: int|
        0 <= q1 < s.procs.len() && 0 <= q2 < s.procs.len() && q1 != q2 && s.procs[q1].alive && s.procs[q2].alive
            && 0 <= m1 < u.n() && 0 <= m2 < u.n() && related(sem, u, m1, m2) && excl(#[trigger] s.procs[q1].locks[m1])
            ==> !any(#[trigger] s.procs[q2].locks[m2])
}

/// Entries for R cells are only in the log of a live process holding H exclusively.
pub open spec fn rown(s: State, h: usize, R: spec_fn(int) -> bool) -> bool {
    forall|q: int| 0 <= q < s.procs.len() && has_r(#[trigger] s.procs[q].undo, R)
        ==> excl(s.procs[q].locks[h as int]) && s.procs[q].alive
}

pub open spec fn clean_all(s: State) -> bool {
    forall|q: int| 0 <= q < s.procs.len() ==> clean_proc(#[trigger] s.procs[q])
}

pub open spec fn inv_h(sem: Sem, u: U, s: State, h: usize, R: spec_fn(int) -> bool) -> bool {
    &&& wf(u, s)
    &&& clean_all(s)
    &&& lock_ok(sem, u, s)
    &&& rown(s, h, R)
}

/// The product's discipline for the protected cells (not a contract clause).
pub open spec fn disc(u: U, s: State, p: usize, op: Op, h: usize, R: spec_fn(int) -> bool) -> bool {
    &&& forall|c: int| (#[trigger] R(c)) && wr_of(u, s, p, op)(c)
            ==> excl(s.procs[p as int].locks[h as int]) && level(s.procs[p as int]) > 0 && !(op is Incr)
    &&& !(op == Op::Unlock { c: h, mode: Mode::E, immediate: true })
}

pub open spec fn r_glob(u: U, R: spec_fn(int) -> bool) -> bool {
    forall|c: int| #[trigger] R(c) ==> is_glob(u, c)
}

/// The clauses this theorem needs: deferred unlock, stop rolls back every level, KILL logged. (Dirty reads, value-based rollback and $INCREMENT are not needed: nobody else writes R.)
pub open spec fn hl_sem(sem: Sem) -> bool {
    &&& sem.unlock_deferred
    &&& sem.stop_rolls_back
    &&& sem.stop_all_levels
    &&& sem.kill_logged
}

/// The committed state as h's rollback would leave it.
pub open spec fn base(sem: Sem, s: State, h: int) -> Seq<Option<Val>> {
    rb(sem, s.g, s.procs[h].ppg, s.procs[h].undo).0
}

pub open spec fn eq_r(a: Seq<Option<Val>>, b: Seq<Option<Val>>, R: spec_fn(int) -> bool) -> bool {
    forall|c: int| 0 <= c < a.len() && (#[trigger] R(c)) ==> a[c] == b[c]
}

// ------------------------------------------------------------------------------------------------ locks

pub proof fn lemma_mutex(sem: Sem, u: U, s: State, q1: int, q2: int, m: int)
    requires lock_ok(sem, u, s), 0 <= q1 < s.procs.len(), 0 <= q2 < s.procs.len(), q1 != q2, s.procs[q1].alive,
        s.procs[q2].alive, is_glob(u, m), excl(s.procs[q1].locks[m]),
    ensures !any(s.procs[q2].locks[m]), !excl(s.procs[q2].locks[m]),
{
    assert(u.paths[m].subrange(0, u.paths[m].len() as int) =~= u.paths[m]);
    assert(covers(u, m, m));
    assert(related(sem, u, m, m));
}

pub proof fn lemma_lock_ok_step(sem: Sem, u: U, s: State, s2: State, x: usize, w: spec_fn(int) -> bool)
    requires lock_ok(sem, u, s), full_eff(sem, u, s, s2, x, w), (x as int) < s.procs.len(), wf(u, s), wf(u, s2),
        forall|a: int, b: int| related(sem, u, a, b) ==> related(sem, u, b, a),
    ensures lock_ok(sem, u, s2),
{
    assert forall|q1: int, q2: int, m1: int, m2: int|
        0 <= q1 < s2.procs.len() && 0 <= q2 < s2.procs.len() && q1 != q2 && s2.procs[q1].alive && s2.procs[q2].alive
            && 0 <= m1 < u.n() && 0 <= m2 < u.n() && related(sem, u, m1, m2) && excl(#[trigger] s2.procs[q1].locks[m1])
        implies !any(#[trigger] s2.procs[q2].locks[m2]) by {
        if q1 == x as int {
            assert(s2.procs[q2] == s.procs[q2]);
            assert(s.procs[x as int].alive);
            if !excl(s.procs[x as int].locks[m1]) {
                assert(no_other_any(sem, u, s, x, m1));
                assert(related(sem, u, m2, m1));
            }
        } else if q2 == x as int {
            assert(s2.procs[q1] == s.procs[q1]);
            assert(s.procs[x as int].alive);
            if any(s2.procs[x as int].locks[m2]) && !any(s.procs[x as int].locks[m2]) {
                assert(no_other_excl(sem, u, s, x, m2));
            }
        } else {
            assert(s2.procs[q1] == s.procs[q1]);
            assert(s2.procs[q2] == s.procs[q2]);
        }
    }
}

pub open spec fn related_sym(sem: Sem, u: U) -> bool {
    forall|a: int, b: int| related(sem, u, a, b) ==> related(sem, u, b, a)
}

pub proof fn lemma_related_sym(sem: Sem, u: U)
    ensures related_sym(sem, u),
{
}

// ------------------------------------------------------------------------------------------------ the holder keeps H

/// The actor's locks are the same afterwards, or its transaction ended (or it is dead).
pub open spec fn locks_or_end(s: State, s2: State, x: usize) -> bool {
    s2.procs[x as int].locks == s.procs[x as int].locks || level(s2.procs[x as int]) == 0 || !s2.procs[x as int].alive
}

pub proof fn lemma_rollback_n_locks(sem: Sem, u: U, s: State, x: usize, n: nat)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures locks_or_end(s, rollback_n(sem, s, x, n), x),
    decreases n,
{
    if !(n == 0 || level(s.procs[x as int]) == 0) {
        let s1 = undo_top(sem, s, x);
        lemma_undo_top_wf(sem, u, s, x);
        lemma_undo_top_level(sem, u, s, x);
        lemma_rollback_n_locks(sem, u, s1, x, (n - 1) as nat);
        if level(s1.procs[x as int]) == 0 {
            assert(rollback_n(sem, s1, x, (n - 1) as nat) == s1);
        }
    }
}

pub proof fn lemma_commit_n_locks(u: U, s: State, x: usize, n: nat)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures locks_or_end(s, commit_n(s, x, n), x),
    decreases n,
{
    if !(n == 0 || level(s.procs[x as int]) == 0) {
        let s1 = commit_top(s, x);
        lemma_commit_top_wf(u, s, x);
        lemma_commit_top_level(u, s, x);
        lemma_commit_n_locks(u, s1, x, (n - 1) as nat);
        if level(s1.procs[x as int]) == 0 {
            assert(commit_n(s1, x, (n - 1) as nat) == s1);
        }
    }
}

pub proof fn lemma_end_levels_locks(sem: Sem, u: U, s: State, x: usize, ends: Ends, commit: bool)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures locks_or_end(s, end_levels(s, sem, x, ends, commit), x),
{
    let l = level(s.procs[x as int]);
    let n: nat = match ends { Ends::One => 1, Ends::All => l };
    let s2 = if l == 0 { s } else if commit { commit_n(s, x, n) } else { rollback_n(sem, s, x, n) };
    lemma_commit_n_locks(u, s, x, n);
    lemma_rollback_n_locks(sem, u, s, x, n);
    lemma_commit_n_wf(u, s, x, n);
    lemma_rollback_n_wf(sem, u, s, x, n);
    assert(locks_or_end(s, s2, x));
    let s3 = set_sqlflag(s2, x, false);
    assert(s3.procs[x as int].locks == s2.procs[x as int].locks);
    assert(level(s3.procs[x as int]) == level(s2.procs[x as int]));
    assert(s3.procs[x as int].alive == s2.procs[x as int].alive);
}

pub proof fn lemma_txn_locks(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires wf(u, s), (p as int) < s.procs.len(), is_txn_op(op), s.procs[p as int].alive,
    ensures locks_or_end(s, txn_step(sem, s, p, op).0, p),
{
    let pr = s.procs[p as int];
    let l = level(pr);
    if l > 0 { lemma_undo_top_level(sem, u, s, p); lemma_commit_top_level(u, s, p); }
    lemma_undo_top_wf(sem, u, s, p);
    lemma_commit_top_wf(u, s, p);
    lemma_tstart_wf(u, s, p);
    lemma_rollback_n_locks(sem, u, s, p, l);
    lemma_rollback_n_wf(sem, u, s, p, l);
    match op {
        Op::SqlCommit => lemma_end_levels_locks(sem, u, s, p, sem.sql_commit, true),
        Op::SqlRollback => lemma_end_levels_locks(sem, u, s, p, sem.sql_rollback, false),
        Op::DrvCommit => lemma_end_levels_locks(sem, u, s, p, sem.drv_commit, true),
        Op::DrvRollback => lemma_end_levels_locks(sem, u, s, p, sem.drv_rollback, false),
        Op::SetAutocommit { on } => {
            lemma_end_levels_locks(sem, u, s, p, sem.drv_commit, true);
            lemma_end_levels_wf(u, s, sem, p, sem.drv_commit, true);
        },
        Op::SqlTxnBegin { hold } => {
            let s1 = select_txn(sem, s, p);
            lemma_select_txn_wf(sem, u, s, p);
            let before = level(s1.procs[p as int]);
            let s2b = if hold && before == 0 { tstart(s1, p) } else { s1 };
            lemma_tstart_wf(u, s1, p);
            let s3 = tstart(s2b, p);
            lemma_tstart_wf(u, s2b, p);
            lemma_commit_n_locks(u, s3, p, (level(s3.procs[p as int]) - before) as nat);
            lemma_commit_n_wf(u, s3, p, (level(s3.procs[p as int]) - before) as nat);
            assert(s1.procs[p as int].locks == s.procs[p as int].locks);
            assert(s3.procs[p as int].locks == s.procs[p as int].locks);
        },
        Op::SqlTxnEnd { level: lv } => {
            let s1 = select_txn(sem, s, p);
            lemma_select_txn_wf(sem, u, s, p);
            lemma_commit_n_locks(u, s1, p, (level(s1.procs[p as int]) - lv + 1) as nat);
            lemma_commit_n_wf(u, s1, p, (level(s1.procs[p as int]) - lv + 1) as nat);
            assert(s1.procs[p as int].locks == s.procs[p as int].locks);
        },
        Op::SqlTxnUndo { level: lv } => {
            let s1 = select_txn(sem, s, p);
            lemma_select_txn_wf(sem, u, s, p);
            lemma_rollback_n_locks(sem, u, s1, p, (level(s1.procs[p as int]) - lv + 1) as nat);
            lemma_rollback_n_locks(sem, u, s1, p, level(s1.procs[p as int]));
            lemma_rollback_n_wf(sem, u, s1, p, (level(s1.procs[p as int]) - lv + 1) as nat);
            lemma_rollback_n_wf(sem, u, s1, p, level(s1.procs[p as int]));
            assert(s1.procs[p as int].locks == s.procs[p as int].locks);
        },
        _ => {},
    }
}

pub proof fn lemma_row_locks(sem: Sem, u: U, s: State, p: usize, op: Op, ch: bool)
    requires wf(u, s), wf_op(u, op), (p as int) < s.procs.len(), is_row_op(op), s.procs[p as int].alive,
    ensures locks_or_end(s, row_step(sem, u, s, p, op, ch).0, p),
{
    lemma_dml_locks(sem, u, s, p, op);
    lemma_select_txn_wf(sem, u, s, p);
}

/// Every operation leaves the actor's exclusive hold on H while its transaction stays open (deferred unlock), except
/// an immediate unlock of H (excluded by the discipline).
pub open spec fn keeps_h(s: State, s2: State, x: usize, h: usize) -> bool {
    excl(s.procs[x as int].locks[h as int]) && level(s.procs[x as int]) > 0 && level(s2.procs[x as int]) > 0
        && s2.procs[x as int].alive ==> excl(s2.procs[x as int].locks[h as int])
}

pub proof fn lemma_dml_locks(sem: Sem, u: U, s: State, x: usize, op: Op)
    requires (x as int) < s.procs.len(), wf(u, s), wf_op(u, op), s.procs[x as int].alive,
    ensures locks_or_end(s, run_dml(sem, u, s, x, op).0, x),
        locks_or_end(s, failed_stmt(sem, s, x), x),
{
    match op {
        Op::Insert { r, v } | Op::Update { r, v } => {
            let b = stmt_begin(s, x);
            lemma_stmt_begin_wf(u, s, x);
            let s2 = write(b.0, x, r, Some(v), true);
            lemma_write_wf(u, b.0, x, r, Some(v), true);
            lemma_commit_top_level(u, s2, x);
        },
        Op::Delete { r } => {
            let b = stmt_begin(s, x);
            lemma_stmt_begin_wf(u, s, x);
            let s2 = write(b.0, x, r, None, true);
            lemma_write_wf(u, b.0, x, r, None, true);
            lemma_commit_top_level(u, s2, x);
        },
        _ => {},
    }
}

pub proof fn lemma_step_keeps_h(sem: Sem, u: U, s: State, p: usize, op: Op, ch: bool, h: usize)
    requires wf(u, s), wf_op(u, op), (p as int) < s.procs.len(), sem.unlock_deferred, clean_all(s),
        !(op == Op::Unlock { c: h, mode: Mode::E, immediate: true }), (h as int) < u.n(),
    ensures keeps_h(s, step(sem, u, s, p, op, ch).0, actor(s, p, op), h),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    if pr.alive && !(pr.pending is Some && !(op is Await)) {
        if is_txn_op(op) {
            lemma_txn_locks(sem, u, s, p, op);
        } else if is_glob_op(op) {
            match op {
                Op::Kill { c } => lemma_kill_locks(sem, u, s, p, c, 0),
                _ => {},
            }
        } else if is_lock_op(op) {
            lemma_lock_step_keeps_h(sem, u, s, p, op, h);
        } else if is_row_op(op) {
            lemma_row_locks(sem, u, s, p, op, ch);
        } else {
            match op {
                Op::Terminate { target } => {
                    if (target as int) < s.procs.len() && s.procs[target as int].alive {
                        lemma_stop_wf(sem, u, s, target);
                        assert(!stop(sem, s, target).procs[target as int].alive);
                    }
                },
                Op::Await => lemma_await_keeps_h(sem, u, s, p, h),
                _ => {},
            }
        }
    }
}

pub proof fn lemma_kill_locks(sem: Sem, u: U, s: State, x: usize, node: usize, j: nat)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures kill_from(sem, u, s, x, node, j).procs[x as int].locks == s.procs[x as int].locks,
        level(kill_from(sem, u, s, x, node, j).procs[x as int]) == level(s.procs[x as int]),
    decreases u.n() - j,
{
    if j < u.n() {
        let s1 = if covers(u, node as int, j as int) && s.g[j as int] is Some { write(s, x, j as usize, None, sem.kill_logged) } else { s };
        lemma_write_wf(u, s, x, j as usize, None, sem.kill_logged);
        lemma_kill_locks(sem, u, s1, x, node, j + 1);
    }
}

pub proof fn lemma_lock_step_keeps_h(sem: Sem, u: U, s: State, p: usize, op: Op, h: usize)
    requires wf(u, s), wf_op(u, op), (p as int) < s.procs.len(), sem.unlock_deferred, is_lock_op(op),
        s.procs[p as int].alive, !(op == Op::Unlock { c: h, mode: Mode::E, immediate: true }), (h as int) < u.n(),
    ensures keeps_h(s, lock_step(sem, u, s, p, op).0, p, h),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    match op {
        Op::Lock { c, mode, .. } => {},
        Op::Unlock { c, mode, immediate } => {},
        Op::LockOnly { c, .. } => {
            if let Some(s1) = release_all(sem, s, p) {
                if level(pr) > 0 && excl(pr.locks[h as int]) {
                    assert(!defer_overflows(pr.locks[h as int]));
                    assert(s1.procs[p as int].locks[h as int] == defer_hold(pr.locks[h as int]));
                    assert(excl(s1.procs[p as int].locks[h as int]));
                }
            }
        },
        Op::ReleaseAll => {
            if let Some(s1) = release_all(sem, s, p) {
                if level(pr) > 0 && excl(pr.locks[h as int]) {
                    assert(!defer_overflows(pr.locks[h as int]));
                    assert(s1.procs[p as int].locks[h as int] == defer_hold(pr.locks[h as int]));
                }
            }
        },
        _ => {},
    }
}

pub proof fn lemma_await_keeps_h(sem: Sem, u: U, s: State, p: usize, h: usize)
    requires wf(u, s), (p as int) < s.procs.len(), s.procs[p as int].alive, (h as int) < u.n(),
    ensures keeps_h(s, await_step(sem, u, s, p).0, p, h),
{
    assert(wf_proc(u, s.procs[p as int]));
    if let Some(pend) = s.procs[p as int].pending {
        let s1 = set_pending(s, p, None);
        lemma_set_pending_wf(u, s, p, None);
        match pend {
            Op::Insert { .. } | Op::Update { .. } | Op::Delete { .. } => lemma_dml_locks(sem, u, s1, p, pend),
            _ => {},
        }
    }
}

// ------------------------------------------------------------------------------------------------ the invariant

/// inv_h is inductive: every permitted outcome of every operation of every process keeps it.
pub proof fn theorem_inv_h(sem: Sem, u: U, s: State, p: usize, op: Op, ch: bool, h: usize, R: spec_fn(int) -> bool)
    requires hl_sem(sem), inv_h(sem, u, s, h, R), disc(u, s, p, op, h, R), wf_op(u, op), (p as int) < s.procs.len(),
        r_glob(u, R), is_glob(u, h as int),
    ensures inv_h(sem, u, step(sem, u, s, p, op, ch).0, h, R),
{
    let s2 = step(sem, u, s, p, op, ch).0;
    let x = actor(s, p, op);
    let w = wr_of(u, s, p, op);
    lemma_step_wf(sem, u, s, p, op, ch);
    lemma_step_eff(sem, u, s, p, op, ch);
    lemma_related_sym(sem, u);
    lemma_lock_ok_step(sem, u, s, s2, x, w);
    lemma_step_keeps_h(sem, u, s, p, op, ch, h);
    assert(clean_all(s2)) by {
        assert forall|q: int| 0 <= q < s2.procs.len() implies clean_proc(#[trigger] s2.procs[q]) by {
            if q != x as int { assert(s2.procs[q] == s.procs[q]); }
        }
    }
    assert(rown(s2, h, R)) by {
        assert forall|q: int| 0 <= q < s2.procs.len() && has_r(#[trigger] s2.procs[q].undo, R)
            implies excl(s2.procs[q].locks[h as int]) && s2.procs[q].alive by {
            if q != x as int {
                assert(s2.procs[q] == s.procs[q]);
            } else {
                let b = s2.procs[q].undo;
                let a = s.procs[q].undo;
                let i = choose|i: int| 0 <= i < b.len() && !(#[trigger] b[i]).ppg && R(b[i].c as int);
                // the entry is old, or new for a cell the operation writes
                assert(b[i].ppg || (i < a.len() && b[i] == a[i]) || w(b[i].c as int));
                if i < a.len() && b[i] == a[i] {
                    assert(has_r(a, R));
                } else {
                    assert(w(b[i].c as int) && R(b[i].c as int));
                    assert(x == p);
                }
                // so x held H exclusively inside a transaction before the step, and its log is not empty after
                assert(excl(s.procs[q].locks[h as int]) && level(s.procs[q]) > 0) by {
                    if i < a.len() && b[i] == a[i] {
                        assert(clean_proc(s.procs[q]));
                    }
                }
                assert(clean_proc(s2.procs[q]));
                assert(level(s2.procs[q]) > 0);
                assert(s2.procs[q].alive) by {
                    if !s2.procs[q].alive { assert(level(s2.procs[q]) == 0); }
                }
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ the committed state

pub proof fn lemma_base_eq(sem: Sem, u: U, s: State, s2: State, x: int)
    requires 0 <= x < s.procs.len(), 0 <= x < s2.procs.len(), wf(u, s), s2.g == s.g, s2.procs[x].undo == s.procs[x].undo,
    ensures base(sem, s2, x) == base(sem, s, x),
{
    assert(wf_proc(u, s.procs[x]));
    lemma_rb_len(sem, s.g, s.procs[x].ppg, s.procs[x].undo);
    lemma_rb_len(sem, s.g, s2.procs[x].ppg, s.procs[x].undo);
    assert forall|c: int| 0 <= c < s.g.len() implies base(sem, s2, x)[c] == base(sem, s, x)[c] by {
        lemma_rb_pointwise(sem, s.g, s.g, s2.procs[x].ppg, s.procs[x].ppg, s.procs[x].undo, c);
    }
    assert(base(sem, s2, x) =~= base(sem, s, x));
}

/// A logged write inside a transaction does not move the committed state.
pub proof fn lemma_base_write(sem: Sem, u: U, s: State, x: usize, c: usize, v: Option<Val>)
    requires (x as int) < s.procs.len(), wf(u, s), (c as int) < u.n(), level(s.procs[x as int]) > 0,
    ensures base(sem, write(s, x, c, v, true), x as int) == base(sem, s, x as int),
{
    lemma_rb_push_write(sem, s.g, s.procs[x as int].ppg, s.procs[x as int].undo, c, v);
}

/// A write that is not logged moves the committed state only at its own cell.
pub proof fn lemma_base_unlogged(sem: Sem, u: U, s: State, x: usize, y: usize, c: usize, v: Option<Val>, d: int)
    requires (x as int) < s.procs.len(), (y as int) < s.procs.len(), wf(u, s), (c as int) < u.n(), 0 <= d < u.n(), d != c as int,
    ensures base(sem, write(s, y, c, v, false), x as int)[d] == base(sem, s, x as int)[d],
{
    let s2 = write(s, y, c, v, false);
    assert(s2.procs[x as int].undo == s.procs[x as int].undo);
    assert(wf_proc(u, s.procs[x as int]));
    lemma_rb_pointwise(sem, s2.g, s.g, s2.procs[x as int].ppg, s.procs[x as int].ppg, s.procs[x as int].undo, d);
}

pub proof fn lemma_base_kill(sem: Sem, u: U, s: State, x: usize, node: usize, j: nat)
    requires (x as int) < s.procs.len(), wf(u, s), level(s.procs[x as int]) > 0, sem.kill_logged,
    ensures base(sem, kill_from(sem, u, s, x, node, j), x as int) == base(sem, s, x as int),
    decreases u.n() - j,
{
    if j < u.n() {
        let s1 = if covers(u, node as int, j as int) && s.g[j as int] is Some { write(s, x, j as usize, None, true) } else { s };
        if covers(u, node as int, j as int) && s.g[j as int] is Some { lemma_base_write(sem, u, s, x, j as usize, None); }
        lemma_write_wf(u, s, x, j as usize, None, true);
        lemma_base_kill(sem, u, s1, x, node, j + 1);
    }
}

pub proof fn lemma_base_undo_top(sem: Sem, u: U, s: State, x: usize)
    requires (x as int) < s.procs.len(), wf(u, s), level(s.procs[x as int]) > 0, clean_proc(s.procs[x as int]),
    ensures level(s.procs[x as int]) >= 2 ==> base(sem, undo_top(sem, s, x), x as int) == base(sem, s, x as int),
        level(s.procs[x as int]) == 1 ==> undo_top(sem, s, x).g == base(sem, s, x as int),
{
    let pr = s.procs[x as int];
    let m = top_mark(pr);
    let pre = pr.undo.subrange(0, m as int);
    let suf = pr.undo.subrange(m as int, pr.undo.len() as int);
    assert(pre + suf =~= pr.undo);
    lemma_rb_split(sem, s.g, pr.ppg, pre, suf);
    if level(pr) == 1 {
        assert(m == 0);
        assert(pre.len() == 0);
        assert(suf =~= pr.undo);
    }
}

pub proof fn lemma_base_rollback_n(sem: Sem, u: U, s: State, x: usize, k: nat)
    requires (x as int) < s.procs.len(), wf(u, s), level(s.procs[x as int]) > 0, clean_proc(s.procs[x as int]),
    ensures level(rollback_n(sem, s, x, k).procs[x as int]) > 0 ==> base(sem, rollback_n(sem, s, x, k), x as int) == base(sem, s, x as int),
        level(rollback_n(sem, s, x, k).procs[x as int]) == 0 ==> rollback_n(sem, s, x, k).g == base(sem, s, x as int),
        clean_proc(rollback_n(sem, s, x, k).procs[x as int]),
    decreases k,
{
    let w = |c: int| false;
    lemma_rollback_n_eff(sem, u, s, x, k, w);
    if k > 0 {
        let s1 = undo_top(sem, s, x);
        lemma_base_undo_top(sem, u, s, x);
        lemma_undo_top_wf(sem, u, s, x);
        lemma_undo_top_level(sem, u, s, x);
        lemma_undo_top_eff(sem, u, s, x, w);
        if level(s1.procs[x as int]) > 0 {
            lemma_base_rollback_n(sem, u, s1, x, (k - 1) as nat);
        } else {
            assert(rollback_n(sem, s1, x, (k - 1) as nat) == s1);
        }
    }
}

pub proof fn lemma_base_commit_n(sem: Sem, u: U, s: State, x: usize, k: nat)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures level(commit_n(s, x, k).procs[x as int]) > 0 ==> base(sem, commit_n(s, x, k), x as int) == base(sem, s, x as int),
        commit_n(s, x, k).g == s.g,
{
    let w = |c: int| false;
    lemma_commit_n_eff(sem, u, s, x, k, w);
    lemma_commit_n_level(u, s, x, k);
    lemma_commit_n_wf(u, s, x, k);
    if level(commit_n(s, x, k).procs[x as int]) > 0 {
        lemma_base_eq(sem, u, s, commit_n(s, x, k), x as int);
    }
}

/// What a step of the holder itself does to the committed state: unchanged while its transaction stays open; at its
/// end, R holds all (commit) or none (rollback) of its writes.
pub open spec fn holder_rel(sem: Sem, s: State, s2: State, h: int, R: spec_fn(int) -> bool) -> bool {
    &&& (level(s2.procs[h]) > 0 && s2.procs[h].alive ==> eq_r(base(sem, s2, h), base(sem, s, h), R))
    &&& (level(s2.procs[h]) == 0 && s2.procs[h].alive ==> eq_r(s2.g, s.g, R) || eq_r(s2.g, base(sem, s, h), R))
    &&& (!s2.procs[h].alive ==> eq_r(s2.g, base(sem, s, h), R))
}

pub proof fn lemma_end_levels_base(sem: Sem, u: U, s: State, x: usize, ends: Ends, commit: bool, R: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), level(s.procs[x as int]) > 0, clean_proc(s.procs[x as int]), s.procs[x as int].alive,
    ensures holder_rel(sem, s, end_levels(s, sem, x, ends, commit), x as int, R),
        level(end_levels(s, sem, x, ends, commit).procs[x as int]) > 0 ==> end_levels(s, sem, x, ends, commit).procs[x as int].alive,
{
    let l = level(s.procs[x as int]);
    let n: nat = match ends { Ends::One => 1, Ends::All => l };
    let s2 = if commit { commit_n(s, x, n) } else { rollback_n(sem, s, x, n) };
    lemma_base_commit_n(sem, u, s, x, n);
    lemma_base_rollback_n(sem, u, s, x, n);
    lemma_commit_n_level(u, s, x, n);
    lemma_rollback_n_level(sem, u, s, x, n);
    lemma_commit_n_wf(u, s, x, n);
    lemma_rollback_n_wf(sem, u, s, x, n);
    let s3 = set_sqlflag(s2, x, false);
    assert(s3.g == s2.g);
    assert(s3.procs[x as int].undo == s2.procs[x as int].undo);
    lemma_base_eq(sem, u, s2, s3, x as int);
}

pub proof fn lemma_holder_commit_top(sem: Sem, u: U, s: State, h: usize, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), level(s.procs[h as int]) > 0, s.procs[h as int].alive,
    ensures holder_rel(sem, s, commit_top(s, h), h as int, R),
{
    lemma_commit_top_level(u, s, h);
    lemma_commit_top_wf(u, s, h);
    let w = |c: int| false;
    lemma_commit_top_eff(sem, u, s, h, w);
    if level(commit_top(s, h).procs[h as int]) > 0 {
        lemma_base_eq(sem, u, s, commit_top(s, h), h as int);
    }
}

pub proof fn lemma_holder_undo_top(sem: Sem, u: U, s: State, h: usize, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), level(s.procs[h as int]) > 0, s.procs[h as int].alive, clean_proc(s.procs[h as int]),
    ensures holder_rel(sem, s, undo_top(sem, s, h), h as int, R),
{
    lemma_undo_top_level(sem, u, s, h);
    lemma_base_undo_top(sem, u, s, h);
}

pub proof fn lemma_holder_rollback_n(sem: Sem, u: U, s: State, h: usize, k: nat, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), level(s.procs[h as int]) > 0, s.procs[h as int].alive, clean_proc(s.procs[h as int]),
    ensures holder_rel(sem, s, rollback_n(sem, s, h, k), h as int, R),
{
    lemma_base_rollback_n(sem, u, s, h, k);
    lemma_rollback_n_level(sem, u, s, h, k);
}

pub proof fn lemma_holder_commit_n(sem: Sem, u: U, s: State, h: usize, k: nat, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), level(s.procs[h as int]) > 0, s.procs[h as int].alive,
    ensures holder_rel(sem, s, commit_n(s, h, k), h as int, R),
{
    lemma_base_commit_n(sem, u, s, h, k);
    lemma_commit_n_level(u, s, h, k);
}

pub proof fn lemma_holder_same(sem: Sem, u: U, s: State, s2: State, h: usize, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), (h as int) < s2.procs.len(), wf(u, s), s2.g == s.g,
        s2.procs[h as int].undo == s.procs[h as int].undo, s2.procs[h as int].alive, level(s2.procs[h as int]) > 0,
    ensures holder_rel(sem, s, s2, h as int, R),
{
    lemma_base_eq(sem, u, s, s2, h as int);
}

pub proof fn lemma_holder_txn(sem: Sem, u: U, s: State, h: usize, op: Op, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), level(s.procs[h as int]) > 0, clean_proc(s.procs[h as int]),
        s.procs[h as int].alive, is_txn_op(op),
    ensures holder_rel(sem, s, txn_step(sem, s, h, op).0, h as int, R),
{
    let pr = s.procs[h as int];
    let l = level(pr);
    lemma_tstart_wf(u, s, h);
    match op {
        Op::TStart => lemma_holder_same(sem, u, s, tstart(s, h), h, R),
        Op::TCommit => lemma_holder_commit_top(sem, u, s, h, R),
        Op::TRollbackOne => {
            lemma_holder_undo_top(sem, u, s, h, R);
            lemma_holder_rollback_n(sem, u, s, h, l, R);
        },
        Op::TRollback => lemma_holder_rollback_n(sem, u, s, h, l, R),
        Op::SqlStart => {
            lemma_set_sqlflag_wf(u, tstart(s, h), h, true);
            lemma_holder_same(sem, u, s, set_sqlflag(tstart(s, h), h, true), h, R);
        },
        Op::SqlCommit => lemma_end_levels_base(sem, u, s, h, sem.sql_commit, true, R),
        Op::SqlRollback => lemma_end_levels_base(sem, u, s, h, sem.sql_rollback, false, R),
        Op::DrvCommit => lemma_end_levels_base(sem, u, s, h, sem.drv_commit, true, R),
        Op::DrvRollback => lemma_end_levels_base(sem, u, s, h, sem.drv_rollback, false, R),
        Op::SetAutocommit { on } => lemma_holder_autocommit(sem, u, s, h, on, R),
        Op::TLevel => {},
        Op::SqlTxnBegin { hold } => lemma_holder_txn_begin(sem, u, s, h, hold, R),
        Op::SqlTxnEnd { level: lv } => {
            assert(select_txn(sem, s, h) == s);
            lemma_holder_commit_n(sem, u, s, h, (l - lv + 1) as nat, R);
        },
        Op::SqlTxnUndo { level: lv } => {
            assert(select_txn(sem, s, h) == s);
            lemma_holder_rollback_n(sem, u, s, h, (l - lv + 1) as nat, R);
            lemma_holder_rollback_n(sem, u, s, h, l, R);
        },
        _ => {},
    }
}

pub proof fn lemma_holder_autocommit(sem: Sem, u: U, s: State, h: usize, on: bool, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), level(s.procs[h as int]) > 0, clean_proc(s.procs[h as int]),
        s.procs[h as int].alive,
    ensures holder_rel(sem, s, txn_step(sem, s, h, Op::SetAutocommit { on }).0, h as int, R),
{
    let l = level(s.procs[h as int]);
    if !(l > 0 && !on && s.procs[h as int].autocommit) {
        lemma_end_levels_base(sem, u, s, h, sem.drv_commit, true, R);
        lemma_end_levels_wf(u, s, sem, h, sem.drv_commit, true);
        lemma_end_levels_alive(sem, u, s, h, sem.drv_commit, true);
        let s1 = if on && sem.autocommit_on_commits { end_levels(s, sem, h, sem.drv_commit, true) } else { s };
        let s3 = upd(s1, h, Proc { autocommit: on, ..s1.procs[h as int] });
        lemma_base_eq(sem, u, s1, s3, h as int);
        assert(s3.g == s1.g);
    }
}

pub proof fn lemma_holder_txn_begin(sem: Sem, u: U, s: State, h: usize, hold: bool, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), level(s.procs[h as int]) > 0, clean_proc(s.procs[h as int]),
        s.procs[h as int].alive,
    ensures holder_rel(sem, s, txn_step(sem, s, h, Op::SqlTxnBegin { hold }).0, h as int, R),
{
    let l = level(s.procs[h as int]);
    assert(select_txn(sem, s, h) == s);
    let s3 = tstart(s, h);
    lemma_tstart_wf(u, s, h);
    lemma_base_eq(sem, u, s, s3, h as int);
    lemma_base_commit_n(sem, u, s3, h, (level(s3.procs[h as int]) - l) as nat);
    lemma_commit_n_level(u, s3, h, (level(s3.procs[h as int]) - l) as nat);
}

pub proof fn lemma_holder_dml(sem: Sem, u: U, s: State, h: usize, op: Op)
    requires (h as int) < s.procs.len(), wf(u, s), level(s.procs[h as int]) > 0, wf_op(u, op),
    ensures base(sem, run_dml(sem, u, s, h, op).0, h as int) == base(sem, s, h as int),
        level(run_dml(sem, u, s, h, op).0.procs[h as int]) > 0,
        run_dml(sem, u, s, h, op).0.procs[h as int].alive == s.procs[h as int].alive,
{
    match op {
        Op::Insert { r, v } | Op::Update { r, v } => {
            lemma_base_write(sem, u, s, h, r, Some(v));
            lemma_write_wf(u, s, h, r, Some(v), true);
            let s2 = write(s, h, r, Some(v), true);
            lemma_base_eq(sem, u, s2, set_rlock(s2, h, r, true), h as int);
        },
        Op::Delete { r } => {
            lemma_base_write(sem, u, s, h, r, None);
            lemma_write_wf(u, s, h, r, None, true);
            let s2 = write(s, h, r, None, true);
            lemma_base_eq(sem, u, s2, set_rlock(s2, h, r, true), h as int);
        },
        _ => {},
    }
}

pub proof fn lemma_holder_own(sem: Sem, u: U, s: State, h: usize, op: Op, ch: bool, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), wf_op(u, op), level(s.procs[h as int]) > 0, clean_proc(s.procs[h as int]),
        s.procs[h as int].alive, hl_sem(sem), !(op is Terminate),
        forall|c: int| (#[trigger] R(c)) && wr(u, op, c) ==> !(op is Incr),
    ensures holder_rel(sem, s, step(sem, u, s, h, op, ch).0, h as int, R),
{
    let pr = s.procs[h as int];
    let s2 = step(sem, u, s, h, op, ch).0;
    assert(wf_proc(u, pr));
    if pr.pending is Some && !(op is Await) {
    } else if is_txn_op(op) {
        lemma_holder_txn(sem, u, s, h, op, R);
    } else if is_glob_op(op) {
        lemma_holder_glob(sem, u, s, h, op, R);
    } else if is_lock_op(op) {
        lemma_lock_step_same(sem, u, s, h, op);
        lemma_lock_step_wf(sem, u, s, h, op);
        lemma_lock_step_alive(sem, u, s, h, op);
        lemma_base_eq(sem, u, s, s2, h as int);
    } else if is_row_op(op) {
        lemma_holder_row(sem, u, s, h, op, ch, R);
    } else {
        lemma_holder_await(sem, u, s, h, R);
    }
}

pub proof fn lemma_holder_glob(sem: Sem, u: U, s: State, h: usize, op: Op, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), wf_op(u, op), level(s.procs[h as int]) > 0, clean_proc(s.procs[h as int]),
        s.procs[h as int].alive, hl_sem(sem), is_glob_op(op),
        forall|c: int| (#[trigger] R(c)) && wr(u, op, c) ==> !(op is Incr),
    ensures holder_rel(sem, s, glob_step(sem, u, s, h, op).0, h as int, R),
{
    let pr = s.procs[h as int];
    let s2 = glob_step(sem, u, s, h, op).0;
    assert(wf_proc(u, pr));
    match op {
        Op::Set { c, v } => lemma_base_write(sem, u, s, h, c, Some(v)),
        Op::Kill { c } => {
            lemma_base_kill(sem, u, s, h, c, 0);
            lemma_kill_locks(sem, u, s, h, c, 0);
            lemma_kill_wf(sem, u, s, h, c, 0);
            lemma_kill_alive(sem, u, s, h, c, 0);
        },
        Op::Incr { c } => {
            let cur = num_of(u, s.g[c as int]);
            if cur != i64::MAX {
                let nv = Some(Val::Num((cur + 1) as i64));
                if !sem.incr_survives {
                    lemma_base_write(sem, u, s, h, c, nv);
                } else {
                    assert(wr(u, op, c as int));
                    assert(!R(c as int));
                    lemma_write_wf(u, s, h, c, nv, false);
                    assert(s2 == write(s, h, c, nv, false));
                    lemma_rb_len(sem, s2.g, s2.procs[h as int].ppg, s2.procs[h as int].undo);
                    lemma_rb_len(sem, s.g, s.procs[h as int].ppg, s.procs[h as int].undo);
                    assert forall|d: int| 0 <= d < base(sem, s2, h as int).len() && (#[trigger] R(d)) implies base(sem, s2, h as int)[d] == base(sem, s, h as int)[d] by {
                        assert(d != c as int);
                        lemma_base_unlogged(sem, u, s, h, h, c, nv, d);
                    }
                }
            }
        },
        Op::PpgSet { c, v } => {
            let pr2 = Proc {
                ppg: pr.ppg.update(c as int, Some(v)),
                undo: pr.undo.push(Undo { c, old: pr.ppg[c as int], written: Some(v), ppg: true }),
                ..pr
            };
            lemma_rb_push_ppg(sem, s.g, pr2.ppg, pr.ppg, pr.undo, Undo { c, old: pr.ppg[c as int], written: Some(v), ppg: true });
        },
        _ => {},
    }
}

pub proof fn lemma_kill_alive(sem: Sem, u: U, s: State, x: usize, node: usize, j: nat)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures kill_from(sem, u, s, x, node, j).procs[x as int].alive == s.procs[x as int].alive,
        kill_from(sem, u, s, x, node, j).procs.len() == s.procs.len(),
    decreases u.n() - j,
{
    if j < u.n() {
        let s1 = if covers(u, node as int, j as int) && s.g[j as int] is Some { write(s, x, j as usize, None, sem.kill_logged) } else { s };
        lemma_write_wf(u, s, x, j as usize, None, sem.kill_logged);
        lemma_kill_alive(sem, u, s1, x, node, j + 1);
    }
}

pub proof fn lemma_lock_step_alive(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires (p as int) < s.procs.len(), wf(u, s), is_lock_op(op), wf_op(u, op),
    ensures lock_step(sem, u, s, p, op).0.procs[p as int].alive == s.procs[p as int].alive,
{
}

pub proof fn lemma_holder_row(sem: Sem, u: U, s: State, h: usize, op: Op, ch: bool, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), wf_op(u, op), level(s.procs[h as int]) > 0, clean_proc(s.procs[h as int]),
        s.procs[h as int].alive, hl_sem(sem), is_row_op(op),
    ensures holder_rel(sem, s, row_step(sem, u, s, h, op, ch).0, h as int, R),
{
    lemma_set_pending_wf(u, s, h, Some(op));
    match op {
        Op::Insert { r, v } => {
            lemma_holder_dml(sem, u, s, h, op);
            lemma_run_dml_wf(sem, u, s, h, op);
            let o = run_dml(sem, u, s, h, op);
            lemma_set_rlock_wf(u, o.0, h, r, false);
            lemma_base_eq(sem, u, o.0, set_rlock(o.0, h, r, false), h as int);
            lemma_base_eq(sem, u, s, set_pending(s, h, Some(op)), h as int);
        },
        Op::Update { .. } | Op::Delete { .. } => {
            lemma_holder_dml(sem, u, s, h, op);
            lemma_base_eq(sem, u, s, set_pending(s, h, Some(op)), h as int);
        },
        _ => {
            assert(select_txn(sem, s, h) == s);
        },
    }
}

pub proof fn lemma_holder_await(sem: Sem, u: U, s: State, h: usize, R: spec_fn(int) -> bool)
    requires (h as int) < s.procs.len(), wf(u, s), level(s.procs[h as int]) > 0, clean_proc(s.procs[h as int]),
        s.procs[h as int].alive, hl_sem(sem),
    ensures holder_rel(sem, s, await_step(sem, u, s, h).0, h as int, R),
{
    let pr = s.procs[h as int];
    assert(wf_proc(u, pr));
    if let Some(pend) = pr.pending {
        let s1 = set_pending(s, h, None);
        lemma_set_pending_wf(u, s, h, None);
        lemma_base_eq(sem, u, s, s1, h as int);
        match pend {
            Op::Lock { c, mode, .. } => {
                lemma_acquire_wf(sem, u, s1, h, c, mode);
                if let Some(s3) = acquire(sem, s1, h, c, mode) { lemma_base_eq(sem, u, s1, s3, h as int); }
            },
            Op::LockOnly { c, .. } => {
                lemma_acquire_wf(sem, u, s1, h, c, Mode::E);
                if let Some(s3) = acquire(sem, s1, h, c, Mode::E) { lemma_base_eq(sem, u, s1, s3, h as int); }
            },
            Op::Insert { .. } | Op::Update { .. } | Op::Delete { .. } => lemma_holder_dml(sem, u, s1, h, pend),
            _ => {},
        }
    }
}

/// Lock operations change neither the globals nor the log.
pub proof fn lemma_lock_step_same(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires (p as int) < s.procs.len(), wf(u, s), is_lock_op(op), wf_op(u, op),
    ensures lock_step(sem, u, s, p, op).0.g == s.g, lock_step(sem, u, s, p, op).0.procs[p as int].undo == s.procs[p as int].undo,
        level(lock_step(sem, u, s, p, op).0.procs[p as int]) == level(s.procs[p as int]),
        lock_step(sem, u, s, p, op).0.procs[p as int].alive == s.procs[p as int].alive,
{
    assert(wf_proc(u, s.procs[p as int]));
}

/// THEOREM (P-C01, P-D9-1, P-L3): the process h holding H exclusively inside a transaction is one atomic step on R.
/// Whatever process takes whatever permitted step (under the discipline): while h's transaction is open the
/// committed state of R (`base`) is unchanged and h keeps H; when it ends alive, R holds all of h's writes (as just
/// before) or none (the committed state); when h is stopped, R holds the committed state.
pub proof fn theorem_atomic(sem: Sem, u: U, s: State, p: usize, op: Op, ch: bool, hl: usize, R: spec_fn(int) -> bool, h: usize)
    requires hl_sem(sem), inv_h(sem, u, s, hl, R), disc(u, s, p, op, hl, R), wf_op(u, op), (p as int) < s.procs.len(),
        r_glob(u, R), is_glob(u, hl as int), (h as int) < s.procs.len(), excl(s.procs[h as int].locks[hl as int]),
        level(s.procs[h as int]) > 0,
    ensures
        holder_rel(sem, s, step(sem, u, s, p, op, ch).0, h as int, R),
        level(step(sem, u, s, p, op, ch).0.procs[h as int]) > 0 && step(sem, u, s, p, op, ch).0.procs[h as int].alive
            ==> excl(step(sem, u, s, p, op, ch).0.procs[h as int].locks[hl as int]),
{
    let s2 = step(sem, u, s, p, op, ch).0;
    let x = actor(s, p, op);
    let w = wr_of(u, s, p, op);
    lemma_step_wf(sem, u, s, p, op, ch);
    lemma_step_eff(sem, u, s, p, op, ch);
    lemma_step_keeps_h(sem, u, s, p, op, ch, hl);
    assert(clean_proc(s.procs[h as int]));
    assert(s.procs[h as int].alive) by {
        if !s.procs[h as int].alive { assert(!any(s.procs[h as int].locks[hl as int])); }
    }
    assert(wf_proc(u, s.procs[h as int]));
    if x != h {
        assert(s2.procs[h as int] == s.procs[h as int]);
        // nobody else writes R or holds an R entry: R is unchanged, so is h's committed state
        assert forall|c: int| 0 <= c < s.g.len() && (#[trigger] R(c)) implies s2.g[c] == s.g[c] by {
            if s2.g[c] != s.g[c] {
                if w(c) {
                    assert(x == p);
                    assert(excl(s.procs[p as int].locks[hl as int]));
                    assert(s.procs[p as int].alive && s.procs[p as int].pending is None || op is Await);
                    lemma_mutex(sem, u, s, h as int, p as int, hl as int);
                } else {
                    assert(log_has(s.procs[x as int].undo, c));
                    assert(has_r(s.procs[x as int].undo, R)) by {
                        let i = choose|i: int| 0 <= i < s.procs[x as int].undo.len() && !(#[trigger] s.procs[x as int].undo[i]).ppg
                            && s.procs[x as int].undo[i].c as int == c;
                    }
                    assert(excl(s.procs[x as int].locks[hl as int]) && s.procs[x as int].alive);
                    lemma_mutex(sem, u, s, h as int, x as int, hl as int);
                }
            }
        }
        assert forall|c: int| 0 <= c < base(sem, s2, h as int).len() && (#[trigger] R(c)) implies base(sem, s2, h as int)[c] == base(sem, s, h as int)[c] by {
            lemma_rb_len(sem, s2.g, s.procs[h as int].ppg, s.procs[h as int].undo);
            lemma_rb_pointwise(sem, s2.g, s.g, s.procs[h as int].ppg, s.procs[h as int].ppg, s.procs[h as int].undo, c);
        }
    } else if op is Terminate {
        let t = op->target;
        if (p as int) < s.procs.len() && s.procs[p as int].alive && s.procs[p as int].pending is None
            && (t as int) < s.procs.len() && s.procs[t as int].alive {
            // h is stopped: every level rolled back
            assert(t == h);
            lemma_base_rollback_n(sem, u, s, h, level(s.procs[h as int]));
            lemma_rollback_n_level(sem, u, s, h, level(s.procs[h as int]));
            lemma_rollback_n_wf(sem, u, s, h, level(s.procs[h as int]));
            assert(s2 == stop(sem, s, h));
            assert(s2.g == rollback_all(sem, s, h).g);
        } else {
            assert(s2 == s);
        }
    } else {
        assert(x == p && p == h);
        assert forall|c: int| (#[trigger] R(c)) && wr(u, op, c) implies !(op is Incr) by {
            assert(w(c));
        }
        lemma_holder_own(sem, u, s, h, op, ch, R);
    }
}

/// THEOREM (G-L, the liveness check under the eraser's lock; P-D9-1's Start/Final reads): a process holding H in any
/// mode, with no R entry of its own, reads every R cell at its committed value: nobody has an open write to R.
pub proof fn theorem_reader_under_lock(sem: Sem, u: U, s: State, hl: usize, R: spec_fn(int) -> bool, q: usize)
    requires inv_h(sem, u, s, hl, R), is_glob(u, hl as int), (q as int) < s.procs.len(), s.procs[q as int].alive,
        any(s.procs[q as int].locks[hl as int]), !has_r(s.procs[q as int].undo, R),
    ensures forall|y: int| 0 <= y < s.procs.len() ==> !has_r(#[trigger] s.procs[y].undo, R),
        forall|y: int, c: int| 0 <= y < s.procs.len() && 0 <= c < s.g.len() && R(c) ==> #[trigger] base(sem, s, y)[c] == s.g[c],
{
    assert forall|y: int| 0 <= y < s.procs.len() implies !has_r(#[trigger] s.procs[y].undo, R) by {
        if y != q as int && has_r(s.procs[y].undo, R) {
            lemma_mutex(sem, u, s, y, q as int, hl as int);
        }
    }
    assert forall|y: int, c: int| 0 <= y < s.procs.len() && 0 <= c < s.g.len() && R(c) implies #[trigger] base(sem, s, y)[c] == s.g[c] by {
        assert(!has_r(s.procs[y].undo, R));
        assert(!log_has(s.procs[y].undo, c)) by {
            if log_has(s.procs[y].undo, c) {
                let i = choose|i: int| 0 <= i < s.procs[y].undo.len() && !(#[trigger] s.procs[y].undo[i]).ppg && s.procs[y].undo[i].c as int == c;
            }
        }
        assert(wf_proc(u, s.procs[y]));
        lemma_rb_untouched(sem, s.g, s.procs[y].ppg, s.procs[y].undo, c);
    }
}

} // verus!
