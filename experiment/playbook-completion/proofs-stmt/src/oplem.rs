//! The effect of one contract operation by one process, as the statement programs use them (proofs-env2
//! `spec::step` under the validated contract `contract_sem`): what it does to the globals and rows, and that it leaves
//! every other process and the actor's level, liveness and (except lock operations) locks alone.
use vstd::prelude::*;
use ivg_proofs_env2::spec::*;
use ivg_proofs_env2::ext::*;
use ivg_proofs_env2::wf::*;
use ivg_proofs_env2::clauses::*;

verus! {

/// p can take its next operation now (a run of its program): alive, nothing pending.
pub open spec fn ready(u: U, s: State, p: usize) -> bool {
    &&& wf(u, s)
    &&& (p as int) < s.procs.len()
    &&& s.procs[p as int].alive
    &&& s.procs[p as int].pending is None
}

/// Only p changed among the processes.
pub open spec fn others(a: State, b: State, p: usize) -> bool {
    &&& b.procs.len() == a.procs.len()
    &&& forall|q: int| 0 <= q < a.procs.len() && q != p as int ==> #[trigger] b.procs[q] == a.procs[q]
}

/// p's level, liveness and pending operation unchanged.
pub open spec fn pctl(a: State, b: State, p: usize) -> bool {
    &&& b.procs[p as int].marks == a.procs[p as int].marks
    &&& b.procs[p as int].alive == a.procs[p as int].alive
    &&& b.procs[p as int].pending == a.procs[p as int].pending
}

/// p's lock table unchanged.
pub open spec fn plocks(a: State, b: State, p: usize) -> bool { b.procs[p as int].locks == a.procs[p as int].locks }

/// p's row locks unchanged.
pub open spec fn prl(a: State, b: State, p: usize) -> bool { b.procs[p as int].rlocks == a.procs[p as int].rlocks }

pub open spec fn one_hold(mode: Mode) -> Hold {
    match mode { Mode::E => Hold { e: 1, s: 0, de: 0, ds: 0 }, Mode::S => Hold { e: 0, s: 1, de: 0, ds: 0 } }
}

pub open spec fn def_hold(mode: Mode) -> Hold {
    match mode { Mode::E => Hold { e: 0, s: 0, de: 1, ds: 0 }, Mode::S => Hold { e: 0, s: 0, de: 0, ds: 1 } }
}

// ------------------------------------------------------------------------------------------------ frame lemmas

pub proof fn lemma_others_trans(a: State, b: State, c: State, p: usize)
    requires others(a, b, p), others(b, c, p),
    ensures others(a, c, p),
{
    assert forall|q: int| 0 <= q < a.procs.len() && q != p as int implies #[trigger] c.procs[q] == a.procs[q] by {
        assert(c.procs[q] == b.procs[q]);
    }
}

pub proof fn lemma_others_row_held(a: State, b: State, p: usize, r: usize)
    requires others(a, b, p),
    ensures row_held(b, p, r) == row_held(a, p, r),
{
    if row_held(b, p, r) {
        let q = choose|q: int| 0 <= q < b.procs.len() && q != p && b.procs[q].alive && #[trigger] b.procs[q].rlocks[r as int];
        assert(a.procs[q] == b.procs[q]);
    }
    if row_held(a, p, r) {
        let q = choose|q: int| 0 <= q < a.procs.len() && q != p && a.procs[q].alive && #[trigger] a.procs[q].rlocks[r as int];
        assert(b.procs[q] == a.procs[q]);
    }
}

pub proof fn lemma_others_conflicts(sem: Sem, u: U, a: State, b: State, p: usize, c: usize, mode: Mode)
    requires others(a, b, p),
    ensures conflicts(sem, u, b, p, c, mode) == conflicts(sem, u, a, p, c, mode),
{
    if conflicts(sem, u, b, p, c, mode) {
        let (q, m) = choose|q: int, m: int| 0 <= q < b.procs.len() && q != p && b.procs[q].alive && 0 <= m < u.n()
            && related(sem, u, m, c as int) && hold_conflicts(sem, #[trigger] b.procs[q].locks[m], mode);
        assert(a.procs[q] == b.procs[q]);
    }
    if conflicts(sem, u, a, p, c, mode) {
        let (q, m) = choose|q: int, m: int| 0 <= q < a.procs.len() && q != p && a.procs[q].alive && 0 <= m < u.n()
            && related(sem, u, m, c as int) && hold_conflicts(sem, #[trigger] a.procs[q].locks[m], mode);
        assert(b.procs[q] == a.procs[q]);
    }
}

/// A global cell covers itself.
pub proof fn lemma_covers_self(u: U, c: int)
    requires is_glob(u, c),
    ensures covers(u, c, c),
{
    assert(u.paths[c].subrange(0, u.paths[c].len() as int) =~= u.paths[c]);
}

// ------------------------------------------------------------------------------------------------ globals

pub proof fn lemma_kill_from(sem: Sem, u: U, s: State, p: usize, node: usize, j: nat)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures ({
        let b = kill_from(sem, u, s, p, node, j);
        &&& wf(u, b)
        &&& others(s, b, p)
        &&& pctl(s, b, p)
        &&& plocks(s, b, p)
        &&& prl(s, b, p)
        &&& b.g.len() == s.g.len()
        &&& forall|c: int| 0 <= c < s.g.len() ==>
                #[trigger] b.g[c] == (if j <= c && covers(u, node as int, c) { None::<Val> } else { s.g[c] })
    }),
    decreases u.n() - j,
{
    lemma_kill_wf(sem, u, s, p, node, j);
    if j < u.n() {
        let s1 = if covers(u, node as int, j as int) && s.g[j as int] is Some { write(s, p, j as usize, None, sem.kill_logged) } else { s };
        lemma_write_wf(u, s, p, j as usize, None, sem.kill_logged);
        lemma_kill_from(sem, u, s1, p, node, j + 1);
        let b = kill_from(sem, u, s, p, node, j);
        assert(b == kill_from(sem, u, s1, p, node, j + 1));
        lemma_others_trans(s, s1, b, p);
        assert forall|c: int| 0 <= c < s.g.len() implies
            #[trigger] b.g[c] == (if j <= c && covers(u, node as int, c) { None::<Val> } else { s.g[c] }) by {
            if c == j as int {
                assert(b.g[c] == s1.g[c]);
            }
        }
    }
}

pub proof fn lemma_op_kill(sem: Sem, u: U, s: State, p: usize, c: usize)
    requires ready(u, s, p), (c as int) < u.n(),
    ensures ({
        let b = step(sem, u, s, p, Op::Kill { c }, false).0;
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p)
        &&& forall|x: int| 0 <= x < u.n() ==> #[trigger] b.g[x] == (if covers(u, c as int, x) { None::<Val> } else { s.g[x] })
    }),
{
    lemma_kill_from(sem, u, s, p, c, 0);
    assert(step(sem, u, s, p, Op::Kill { c }, false).0 == kill_from(sem, u, s, p, c, 0));
}

pub proof fn lemma_op_incr(sem: Sem, u: U, s: State, p: usize, c: usize)
    requires ready(u, s, p), (c as int) < u.n(),
    ensures ({
        let b = step(sem, u, s, p, Op::Incr { c }, false).0;
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p)
        &&& b.g.len() == s.g.len()
        &&& forall|x: int| 0 <= x < u.n() && x != c as int ==> #[trigger] b.g[x] == s.g[x]
    }),
{
    let cur = num_of(u, s.g[c as int]);
    if cur != i64::MAX {
        lemma_write_wf(u, s, p, c, Some(Val::Num((cur + 1) as i64)), !sem.incr_survives);
    }
}

pub proof fn lemma_op_set(sem: Sem, u: U, s: State, p: usize, c: usize, v: Val)
    requires ready(u, s, p), (c as int) < u.n(),
    ensures ({
        let b = step(sem, u, s, p, Op::Set { c, v }, false).0;
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p)
        &&& b.g == s.g.update(c as int, Some(v))
    }),
{
    lemma_write_wf(u, s, p, c, Some(v), true);
}

/// Reads change nothing.
pub proof fn lemma_op_read(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires ready(u, s, p), op is Get || op is Order || op is Data,
    ensures step(sem, u, s, p, op, false).0 == s,
{
}

// ------------------------------------------------------------------------------------------------ rows

pub proof fn lemma_op_delete(sem: Sem, u: U, s: State, p: usize, r: usize)
    requires sem == contract_sem(), ready(u, s, p), level(s.procs[p as int]) > 0, (r as int) < u.n(), u.is_row[r as int],
        u.texists[u.table[r as int] as int], !row_held(s, p, r),
    ensures ({
        let b = step(sem, u, s, p, Op::Delete { r }, false).0;
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p)
        &&& b.g == s.g.update(r as int, None)
        &&& s.g[r as int] is None ==> b == s
    }),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    let op = Op::Delete { r };
    let b = step(sem, u, s, p, op, false).0;
    assert(!blocked(sem, u, s, p, op));
    assert(b == dml_change(sem, u, s, p, r, None).0);
    if s.g[r as int] is Some {
        assert(stmt_begin(s, p) == (s, false));
        let s1 = write(s, p, r, None, true);
        lemma_write_wf(u, s, p, r, None, true);
        lemma_set_rlock_wf(u, s1, p, r, true);
        assert(b == set_rlock(s1, p, r, true));
    } else {
        assert(s.g.update(r as int, None) =~= s.g);
        assert(b == s);
    }
}

/// An INSERT of an absent row nobody else row-locks, inside a transaction (the commit's row write in the F-1201 run).
pub proof fn lemma_op_insert(sem: Sem, u: U, s: State, p: usize, r: usize, v: Val)
    requires sem == contract_sem(), ready(u, s, p), level(s.procs[p as int]) > 0, (r as int) < u.n(), u.is_row[r as int],
        u.texists[u.table[r as int] as int], !row_held(s, p, r), s.g[r as int] is None, !u.long[r as int],
    ensures ({
        let b = step(sem, u, s, p, Op::Insert { r, v }, false).0;
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p)
        &&& b.g == s.g.update(r as int, Some(v))
    }),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    let op = Op::Insert { r, v };
    let b = step(sem, u, s, p, op, false).0;
    assert(!freedom_cond(sem, s, p, r));
    assert(!blocked(sem, u, s, p, op));
    assert(b == dml_insert(sem, u, s, p, r, v).0);
    assert(stmt_begin(s, p) == (s, false));
    let s1 = write(s, p, r, Some(v), true);
    lemma_write_wf(u, s, p, r, Some(v), true);
    lemma_set_rlock_wf(u, s1, p, r, true);
    assert(b == set_rlock(s1, p, r, true));
}

// ------------------------------------------------------------------------------------------------ transactions

pub proof fn lemma_op_tstart(sem: Sem, u: U, s: State, p: usize)
    requires ready(u, s, p),
    ensures ({
        let b = step(sem, u, s, p, Op::TStart, false).0;
        &&& ready(u, b, p) && others(s, b, p) && plocks(s, b, p) && prl(s, b, p)
        &&& b.g == s.g
        &&& b.procs[p as int].alive && b.procs[p as int].pending is None
        &&& level(b.procs[p as int]) == level(s.procs[p as int]) + 1
    }),
{
    lemma_tstart_wf(u, s, p);
}

/// TCOMMIT at a level above 0: one level fewer; at the outermost end the deferred releases happen and the log goes.
pub proof fn lemma_op_tcommit(sem: Sem, u: U, s: State, p: usize)
    requires ready(u, s, p), level(s.procs[p as int]) > 0,
    ensures ({
        let b = step(sem, u, s, p, Op::TCommit, false).0;
        &&& ready(u, b, p) && others(s, b, p)
        &&& b.g == s.g
        &&& level(b.procs[p as int]) == level(s.procs[p as int]) - 1
        &&& level(s.procs[p as int]) > 1 ==> plocks(s, b, p)
        &&& level(s.procs[p as int]) == 1 ==> forall|m: int| 0 <= m < b.procs[p as int].locks.len() ==>
                #[trigger] b.procs[p as int].locks[m] == Hold { de: 0, ds: 0, ..s.procs[p as int].locks[m] }
        &&& level(s.procs[p as int]) == 1 ==> b.procs[p as int].undo.len() == 0
    }),
{
    lemma_commit_top_wf(u, s, p);
    let pr = s.procs[p as int];
    let s2 = upd(s, p, Proc { marks: pr.marks.drop_last(), ..pr });
    assert(wf_proc(u, pr));
    if pr.marks.len() == 1 {
        lemma_txn_end_wf(u, s2, p);
    }
}

// ------------------------------------------------------------------------------------------------ locks

/// LOCK + of a name p does not hold, with nothing conflicting: granted at once.
pub proof fn lemma_op_lock_fresh(sem: Sem, u: U, s: State, p: usize, c: usize, mode: Mode)
    requires sem == contract_sem(), ready(u, s, p), (c as int) < u.n(), !conflicts(sem, u, s, p, c, mode),
        s.procs[p as int].locks[c as int] == zero_hold(),
    ensures ({
        let b = step(sem, u, s, p, Op::Lock { c, mode, wait: true }, false).0;
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && prl(s, b, p)
        &&& b.g == s.g
        &&& b.procs[p as int].locks == s.procs[p as int].locks.update(c as int, one_hold(mode))
    }),
{
    let h = s.procs[p as int].locks[c as int];
    assert(wf_proc(u, s.procs[p as int]));
    let h2 = match mode { Mode::E => Hold { e: (h.e + 1) as u64, ..h }, Mode::S => Hold { s: (h.s + 1) as u64, ..h } };
    assert(h2 == one_hold(mode));
    lemma_set_hold_wf(u, s, p, c, h2);
    assert(step(sem, u, s, p, Op::Lock { c, mode, wait: true }, false).0 == set_hold(s, p, c, h2));
}

/// LOCK - of a single hold inside a transaction: deferred to the outermost end (E-LOCK-DEFER).
pub proof fn lemma_op_unlock_one(sem: Sem, u: U, s: State, p: usize, c: usize, mode: Mode)
    requires sem == contract_sem(), ready(u, s, p), (c as int) < u.n(), level(s.procs[p as int]) > 0,
        s.procs[p as int].locks[c as int] == one_hold(mode),
    ensures ({
        let b = step(sem, u, s, p, Op::Unlock { c, mode, immediate: false }, false).0;
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && prl(s, b, p)
        &&& b.g == s.g
        &&& b.procs[p as int].locks == s.procs[p as int].locks.update(c as int, def_hold(mode))
    }),
{
    assert(wf_proc(u, s.procs[p as int]));
    lemma_set_hold_wf(u, s, p, c, def_hold(mode));
    assert(step(sem, u, s, p, Op::Unlock { c, mode, immediate: false }, false).0 == set_hold(s, p, c, def_hold(mode)));
}

} // verus!
