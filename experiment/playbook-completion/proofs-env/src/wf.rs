//! Well-formedness is preserved by every operation (the exec model relies on it for its indexing; the premise
//! theorems carry it as part of their invariants).
use vstd::prelude::*;
use crate::spec::*;

verus! {

pub proof fn lemma_upd_wf(u: U, s: State, p: usize, pr: Proc)
    requires wf(u, s), (p as int) < s.procs.len(), wf_proc(u, pr),
    ensures wf(u, upd(s, p, pr)), upd(s, p, pr).procs.len() == s.procs.len(),
{
    let s2 = upd(s, p, pr);
    assert forall|q: int| 0 <= q < s2.procs.len() implies wf_proc(u, #[trigger] s2.procs[q]) by {
        if q != p as int { assert(s2.procs[q] == s.procs[q]); }
    }
}

pub proof fn lemma_write_wf(u: U, s: State, p: usize, c: usize, v: Option<Val>, logged: bool)
    requires wf(u, s), (p as int) < s.procs.len(), (c as int) < u.n(),
    ensures wf(u, write(s, p, c, v, logged)), write(s, p, c, v, logged).procs.len() == s.procs.len(),
{
    let s2 = write(s, p, c, v, logged);
    assert(wf_proc(u, s.procs[p as int]));
    assert forall|q: int| 0 <= q < s2.procs.len() implies wf_proc(u, #[trigger] s2.procs[q]) by {
        if q != p as int { assert(s2.procs[q] == s.procs[q]); } else {
            let pr = s.procs[p as int];
            assert forall|i: int| 0 <= i < s2.procs[q].undo.len() implies (s2.procs[q].undo[i].c as int) < u.n() by {
                if i < pr.undo.len() { assert(s2.procs[q].undo[i] == pr.undo[i]); }
            }
        }
    }
}

pub proof fn lemma_kill_wf(sem: Sem, u: U, s: State, p: usize, node: usize, j: nat)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, kill_from(sem, u, s, p, node, j)), kill_from(sem, u, s, p, node, j).procs.len() == s.procs.len(),
    decreases u.n() - j,
{
    if j < u.n() {
        let s2 = if covers(u, node as int, j as int) && s.g[j as int] is Some { write(s, p, j as usize, None, sem.kill_logged) } else { s };
        if covers(u, node as int, j as int) && s.g[j as int] is Some { lemma_write_wf(u, s, p, j as usize, None, sem.kill_logged); }
        lemma_kill_wf(sem, u, s2, p, node, j + 1);
    }
}

pub proof fn lemma_rb_len_n(sem: Sem, g: Seq<Option<Val>>, pp: Seq<Option<Val>>, es: Seq<Undo>, n: nat)
    requires g.len() == n, pp.len() == n, forall|i: int| 0 <= i < es.len() ==> (es[i].c as int) < n,
    ensures rb(sem, g, pp, es).0.len() == n, rb(sem, g, pp, es).1.len() == n,
    decreases es.len(),
{
    if es.len() > 0 {
        let r = restore1(sem, g, pp, es.last());
        lemma_rb_len_n(sem, r.0, r.1, es.drop_last(), n);
    }
}

pub proof fn lemma_tstart_wf(u: U, s: State, p: usize)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, tstart(s, p)), tstart(s, p).procs.len() == s.procs.len(),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    lemma_upd_wf(u, s, p, Proc { marks: pr.marks.push(pr.undo.len()), ..pr });
}

pub proof fn lemma_txn_end_wf(u: U, s: State, p: usize)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, txn_end(s, p)), txn_end(s, p).procs.len() == s.procs.len(),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    lemma_upd_wf(u, s, p, Proc {
        sqlflag: false,
        undo: Seq::empty(),
        marks: Seq::empty(),
        locks: Seq::new(pr.locks.len(), |i: int| Hold { de: 0, ds: 0, ..pr.locks[i] }),
        rlocks: Seq::new(pr.rlocks.len(), |i: int| false),
        ..pr
    });
}

pub proof fn lemma_undo_top_wf(sem: Sem, u: U, s: State, p: usize)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, undo_top(sem, s, p)), undo_top(sem, s, p).procs.len() == s.procs.len(),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    let m = top_mark(pr);
    let es = pr.undo.subrange(m as int, pr.undo.len() as int);
    assert forall|i: int| 0 <= i < es.len() implies (es[i].c as int) < u.n() by { assert(es[i] == pr.undo[m + i]); }
    lemma_rb_len_n(sem, s.g, pr.ppg, es, u.n());
    let r = rb(sem, s.g, pr.ppg, es);
    let pr2 = Proc { undo: pr.undo.subrange(0, m as int), marks: pr.marks.drop_last(), ppg: r.1, ..pr };
    let s2 = State { g: r.0, procs: s.procs.update(p as int, pr2) };
    assert forall|i: int| 0 <= i < pr2.undo.len() implies (pr2.undo[i].c as int) < u.n() by { assert(pr2.undo[i] == pr.undo[i]); }
    assert(wf_proc(u, pr2));
    assert forall|q: int| 0 <= q < s2.procs.len() implies wf_proc(u, #[trigger] s2.procs[q]) by {
        if q != p as int { assert(s2.procs[q] == s.procs[q]); }
    }
    assert(wf(u, s2));
    if pr2.marks.len() == 0 { lemma_txn_end_wf(u, s2, p); }
}

pub proof fn lemma_commit_top_wf(u: U, s: State, p: usize)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, commit_top(s, p)), commit_top(s, p).procs.len() == s.procs.len(),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    if pr.marks.len() > 0 {
        let s2 = upd(s, p, Proc { marks: pr.marks.drop_last(), ..pr });
        lemma_upd_wf(u, s, p, Proc { marks: pr.marks.drop_last(), ..pr });
        if pr.marks.len() == 1 { lemma_txn_end_wf(u, s2, p); }
    }
}

pub proof fn lemma_rollback_n_wf(sem: Sem, u: U, s: State, p: usize, n: nat)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, rollback_n(sem, s, p, n)), rollback_n(sem, s, p, n).procs.len() == s.procs.len(),
    decreases n,
{
    if !(n == 0 || level(s.procs[p as int]) == 0) {
        lemma_undo_top_wf(sem, u, s, p);
        lemma_rollback_n_wf(sem, u, undo_top(sem, s, p), p, (n - 1) as nat);
    }
}

pub proof fn lemma_commit_n_wf(u: U, s: State, p: usize, n: nat)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, commit_n(s, p, n)), commit_n(s, p, n).procs.len() == s.procs.len(),
    decreases n,
{
    if !(n == 0 || level(s.procs[p as int]) == 0) {
        lemma_commit_top_wf(u, s, p);
        lemma_commit_n_wf(u, commit_top(s, p), p, (n - 1) as nat);
    }
}

pub proof fn lemma_set_sqlflag_wf(u: U, s: State, p: usize, b: bool)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, set_sqlflag(s, p, b)), set_sqlflag(s, p, b).procs.len() == s.procs.len(),
{
    assert(wf_proc(u, s.procs[p as int]));
    lemma_upd_wf(u, s, p, Proc { sqlflag: b, ..s.procs[p as int] });
}

pub proof fn lemma_set_pending_wf(u: U, s: State, p: usize, op: Option<Op>)
    requires wf(u, s), (p as int) < s.procs.len(), op matches Some(o) ==> wf_op(u, o),
    ensures wf(u, set_pending(s, p, op)), set_pending(s, p, op).procs.len() == s.procs.len(),
{
    assert(wf_proc(u, s.procs[p as int]));
    lemma_upd_wf(u, s, p, Proc { pending: op, ..s.procs[p as int] });
}

pub proof fn lemma_end_levels_wf(u: U, s: State, sem: Sem, p: usize, ends: Ends, commit: bool)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, end_levels(s, sem, p, ends, commit)), end_levels(s, sem, p, ends, commit).procs.len() == s.procs.len(),
{
    let l = level(s.procs[p as int]);
    let n: nat = match ends { Ends::One => 1, Ends::All => l };
    let s2 = if l == 0 { s } else if commit { commit_n(s, p, n) } else { rollback_n(sem, s, p, n) };
    if l != 0 { if commit { lemma_commit_n_wf(u, s, p, n); } else { lemma_rollback_n_wf(sem, u, s, p, n); } }
    lemma_set_sqlflag_wf(u, s2, p, false);
}

pub proof fn lemma_set_hold_wf(u: U, s: State, p: usize, c: usize, h: Hold)
    requires wf(u, s), (p as int) < s.procs.len(), (c as int) < u.n(),
    ensures wf(u, set_hold(s, p, c, h)), set_hold(s, p, c, h).procs.len() == s.procs.len(),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    lemma_upd_wf(u, s, p, Proc { locks: pr.locks.update(c as int, h), ..pr });
}

pub proof fn lemma_set_rlock_wf(u: U, s: State, p: usize, r: usize, b: bool)
    requires wf(u, s), (p as int) < s.procs.len(), (r as int) < u.n(),
    ensures wf(u, set_rlock(s, p, r, b)), set_rlock(s, p, r, b).procs.len() == s.procs.len(),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    lemma_upd_wf(u, s, p, Proc { rlocks: pr.rlocks.update(r as int, b), ..pr });
}

pub proof fn lemma_acquire_wf(sem: Sem, u: U, s: State, p: usize, c: usize, mode: Mode)
    requires wf(u, s), (p as int) < s.procs.len(), (c as int) < u.n(),
    ensures acquire(sem, s, p, c, mode) matches Some(s2) ==> wf(u, s2) && s2.procs.len() == s.procs.len(),
{
    let h = s.procs[p as int].locks[c as int];
    lemma_set_hold_wf(u, s, p, c, Hold { e: 1, ..h });
    lemma_set_hold_wf(u, s, p, c, Hold { s: 1, ..h });
    lemma_set_hold_wf(u, s, p, c, Hold { e: (h.e + 1) as u64, ..h });
    lemma_set_hold_wf(u, s, p, c, Hold { s: (h.s + 1) as u64, ..h });
}

pub proof fn lemma_release_wf(sem: Sem, u: U, s: State, p: usize, c: usize, mode: Mode, immediate: bool)
    requires wf(u, s), (p as int) < s.procs.len(), (c as int) < u.n(),
    ensures release(sem, s, p, c, mode, immediate) matches Some(s2) ==> wf(u, s2) && s2.procs.len() == s.procs.len(),
{
    let h = s.procs[p as int].locks[c as int];
    lemma_set_hold_wf(u, s, p, c, Hold { e: (h.e - 1) as u64, ..h });
    lemma_set_hold_wf(u, s, p, c, Hold { e: (h.e - 1) as u64, de: (h.de + 1) as u64, ..h });
    lemma_set_hold_wf(u, s, p, c, Hold { s: (h.s - 1) as u64, ..h });
    lemma_set_hold_wf(u, s, p, c, Hold { s: (h.s - 1) as u64, ds: (h.ds + 1) as u64, ..h });
}

pub proof fn lemma_release_all_wf(sem: Sem, u: U, s: State, p: usize)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures release_all(sem, s, p) matches Some(s2) ==> wf(u, s2) && s2.procs.len() == s.procs.len(),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    lemma_upd_wf(u, s, p, Proc { locks: Seq::new(pr.locks.len(), |i: int| defer_hold(pr.locks[i])), ..pr });
    lemma_upd_wf(u, s, p, Proc {
        locks: Seq::new(pr.locks.len(), |i: int| zero_hold()),
        rlocks: Seq::new(pr.rlocks.len(), |i: int| false),
        ..pr
    });
}

pub proof fn lemma_stmt_begin_wf(u: U, s: State, p: usize)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, stmt_begin(s, p).0), stmt_begin(s, p).0.procs.len() == s.procs.len(),
{
    lemma_tstart_wf(u, s, p);
    lemma_set_sqlflag_wf(u, tstart(s, p), p, true);
}

pub proof fn lemma_failed_stmt_wf(sem: Sem, u: U, s: State, p: usize)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, failed_stmt(sem, s, p)), failed_stmt(sem, s, p).procs.len() == s.procs.len(),
{
    lemma_tstart_wf(u, s, p);
    lemma_set_sqlflag_wf(u, tstart(s, p), p, true);
}

pub proof fn lemma_run_dml_wf(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires wf(u, s), (p as int) < s.procs.len(), wf_op(u, op),
    ensures wf(u, run_dml(sem, u, s, p, op).0), run_dml(sem, u, s, p, op).0.procs.len() == s.procs.len(),
{
    match op {
        Op::Insert { r, v } | Op::Update { r, v } => {
            lemma_failed_stmt_wf(sem, u, s, p);
            lemma_stmt_begin_wf(u, s, p);
            let b = stmt_begin(s, p);
            let nv = if op is Insert { Some(v) } else { Some(v) };
            lemma_write_wf(u, b.0, p, r, Some(v), true);
            let s2 = write(b.0, p, r, Some(v), true);
            lemma_commit_top_wf(u, s2, p);
            lemma_set_rlock_wf(u, s2, p, r, true);
        },
        Op::Delete { r } => {
            lemma_failed_stmt_wf(sem, u, s, p);
            lemma_stmt_begin_wf(u, s, p);
            let b = stmt_begin(s, p);
            lemma_write_wf(u, b.0, p, r, None, true);
            let s2 = write(b.0, p, r, None, true);
            lemma_commit_top_wf(u, s2, p);
            lemma_set_rlock_wf(u, s2, p, r, true);
        },
        _ => {},
    }
}

pub proof fn lemma_select_txn_wf(sem: Sem, u: U, s: State, p: usize)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, select_txn(sem, s, p)), select_txn(sem, s, p).procs.len() == s.procs.len(),
{
    lemma_tstart_wf(u, s, p);
    lemma_set_sqlflag_wf(u, tstart(s, p), p, true);
}

pub proof fn lemma_cv_wf(sem: Sem, u: U, s: State, p: usize, q: nat)
    requires wf(u, s),
    ensures wf(u, cv_from(sem, s, p, q)), cv_from(sem, s, p, q).procs == s.procs,
    decreases s.procs.len() - q,
{
    if q < s.procs.len() {
        let s2 = if q != p { rollback_all(Sem { rollback_physical: true, ..sem }, s, q as usize) } else { s };
        if q != p { lemma_rollback_n_wf(Sem { rollback_physical: true, ..sem }, u, s, q as usize, level(s.procs[q as int])); }
        let s3 = State { g: s2.g, procs: s.procs };
        lemma_cv_wf(sem, u, s3, p, q + 1);
    }
}

pub proof fn lemma_stop_wf(sem: Sem, u: U, s: State, t: usize)
    requires wf(u, s), (t as int) < s.procs.len(),
    ensures wf(u, stop(sem, s, t)), stop(sem, s, t).procs.len() == s.procs.len(),
{
    lemma_commit_n_wf(u, s, t, level(s.procs[t as int]));
    lemma_rollback_n_wf(sem, u, s, t, level(s.procs[t as int]));
    lemma_rollback_n_wf(sem, u, s, t, 1);
    let s1 = if !sem.stop_rolls_back { commit_all(s, t) } else if sem.stop_all_levels { rollback_all(sem, s, t) } else { rollback_n(sem, s, t, 1) };
    let pr = s1.procs[t as int];
    assert(wf_proc(u, pr));
    lemma_upd_wf(u, s1, t, Proc {
        locks: Seq::new(pr.locks.len(), |i: int| zero_hold()),
        rlocks: Seq::new(pr.rlocks.len(), |i: int| false),
        ppg: Seq::new(pr.ppg.len(), |i: int| None),
        pending: None,
        alive: false,
        ..pr
    });
}

pub proof fn lemma_txn_step_wf(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires wf(u, s), (p as int) < s.procs.len(), is_txn_op(op),
    ensures wf(u, txn_step(sem, s, p, op).0), txn_step(sem, s, p, op).0.procs.len() == s.procs.len(),
{
    if op is SqlTxnBegin || op is SqlTxnEnd || op is SqlTxnUndo {
        lemma_txn_sqlproc_wf(sem, u, s, p, op);
    } else if op is SqlCommit || op is SqlRollback || op is DrvCommit || op is DrvRollback || op is SetAutocommit {
        lemma_txn_ends_wf(sem, u, s, p, op);
    } else {
        lemma_txn_basic_wf(sem, u, s, p, op);
    }
}

pub proof fn lemma_txn_basic_wf(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires wf(u, s), (p as int) < s.procs.len(),
        op is TStart || op is TCommit || op is TRollbackOne || op is TRollback || op is SqlStart || op is TLevel,
    ensures wf(u, txn_step(sem, s, p, op).0), txn_step(sem, s, p, op).0.procs.len() == s.procs.len(),
{
    let l = level(s.procs[p as int]);
    lemma_tstart_wf(u, s, p);
    lemma_commit_top_wf(u, s, p);
    lemma_undo_top_wf(sem, u, s, p);
    lemma_rollback_n_wf(sem, u, s, p, l);
    lemma_set_sqlflag_wf(u, tstart(s, p), p, true);
}

pub proof fn lemma_txn_ends_wf(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires wf(u, s), (p as int) < s.procs.len(),
        op is SqlCommit || op is SqlRollback || op is DrvCommit || op is DrvRollback || op is SetAutocommit,
    ensures wf(u, txn_step(sem, s, p, op).0), txn_step(sem, s, p, op).0.procs.len() == s.procs.len(),
{
    let l = level(s.procs[p as int]);
    match op {
        Op::SqlCommit => lemma_end_levels_wf(u, s, sem, p, sem.sql_commit, true),
        Op::SqlRollback => lemma_end_levels_wf(u, s, sem, p, sem.sql_rollback, false),
        Op::DrvCommit => lemma_end_levels_wf(u, s, sem, p, sem.drv_commit, true),
        Op::DrvRollback => lemma_end_levels_wf(u, s, sem, p, sem.drv_rollback, false),
        Op::SetAutocommit { on } => {
            lemma_end_levels_wf(u, s, sem, p, sem.drv_commit, true);
            let s2 = if on && l > 0 && sem.autocommit_on_commits { end_levels(s, sem, p, sem.drv_commit, true) } else { s };
            assert(wf_proc(u, s2.procs[p as int]));
            lemma_upd_wf(u, s2, p, Proc { autocommit: on, ..s2.procs[p as int] });
        },
        _ => {},
    }
}

pub proof fn lemma_txn_sqlproc_wf(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires wf(u, s), (p as int) < s.procs.len(), op is SqlTxnBegin || op is SqlTxnEnd || op is SqlTxnUndo,
    ensures wf(u, txn_step(sem, s, p, op).0), txn_step(sem, s, p, op).0.procs.len() == s.procs.len(),
{
    lemma_select_txn_wf(sem, u, s, p);
    let s1 = select_txn(sem, s, p);
    let l1 = level(s1.procs[p as int]);
    match op {
        Op::SqlTxnBegin { hold } => {
            let before = l1;
            lemma_tstart_wf(u, s1, p);
            let s2 = if hold && before == 0 { tstart(s1, p) } else { s1 };
            lemma_tstart_wf(u, s2, p);
            let s3 = tstart(s2, p);
            let answer = level(s3.procs[p as int]);
            lemma_commit_n_wf(u, s3, p, (answer - before) as nat);
        },
        Op::SqlTxnEnd { level: lv } => {
            lemma_commit_n_wf(u, s1, p, (l1 - lv + 1) as nat);
        },
        Op::SqlTxnUndo { level: lv } => {
            lemma_rollback_n_wf(sem, u, s1, p, (l1 - lv + 1) as nat);
            lemma_rollback_n_wf(sem, u, s1, p, l1);
        },
        _ => {},
    }
}

pub proof fn lemma_glob_step_wf(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires wf(u, s), (p as int) < s.procs.len(), is_glob_op(op), wf_op(u, op),
    ensures wf(u, glob_step(sem, u, s, p, op).0), glob_step(sem, u, s, p, op).0.procs.len() == s.procs.len(),
{
    let pr = s.procs[p as int];
    assert(wf_proc(u, pr));
    match op {
        Op::Set { c, v } => lemma_write_wf(u, s, p, c, Some(v), true),
        Op::Kill { c } => lemma_kill_wf(sem, u, s, p, c, 0),
        Op::Incr { c } => {
            let cur = num_of(u, s.g[c as int]);
            lemma_write_wf(u, s, p, c, Some(Val::Num((cur + 1) as i64)), !sem.incr_survives);
        },
        Op::PpgSet { c, v } => {
            let pr2 = Proc {
                ppg: pr.ppg.update(c as int, Some(v)),
                undo: if level(pr) > 0 { pr.undo.push(Undo { c, old: pr.ppg[c as int], written: Some(v), ppg: true }) } else { pr.undo },
                ..pr
            };
            assert forall|i: int| 0 <= i < pr2.undo.len() implies (pr2.undo[i].c as int) < u.n() by {
                if i < pr.undo.len() { assert(pr2.undo[i] == pr.undo[i]); }
            }
            lemma_upd_wf(u, s, p, pr2);
        },
        _ => {},
    }
}

pub proof fn lemma_lock_step_wf(sem: Sem, u: U, s: State, p: usize, op: Op)
    requires wf(u, s), (p as int) < s.procs.len(), is_lock_op(op), wf_op(u, op),
    ensures wf(u, lock_step(sem, u, s, p, op).0), lock_step(sem, u, s, p, op).0.procs.len() == s.procs.len(),
{
    lemma_set_pending_wf(u, s, p, Some(op));
    lemma_release_all_wf(sem, u, s, p);
    match op {
        Op::Lock { c, mode, .. } => lemma_acquire_wf(sem, u, s, p, c, mode),
        Op::Unlock { c, mode, immediate } => lemma_release_wf(sem, u, s, p, c, mode, immediate),
        Op::LockOnly { c, .. } => {
            if let Some(s1) = release_all(sem, s, p) {
                lemma_set_pending_wf(u, s1, p, Some(op));
                lemma_acquire_wf(sem, u, s1, p, c, Mode::E);
            }
        },
        _ => {},
    }
}

pub proof fn lemma_row_step_wf(sem: Sem, u: U, s: State, p: usize, op: Op, choice: bool)
    requires wf(u, s), (p as int) < s.procs.len(), is_row_op(op), wf_op(u, op),
    ensures wf(u, row_step(sem, u, s, p, op, choice).0), row_step(sem, u, s, p, op, choice).0.procs.len() == s.procs.len(),
{
    lemma_set_pending_wf(u, s, p, Some(op));
    lemma_run_dml_wf(sem, u, s, p, op);
    lemma_select_txn_wf(sem, u, s, p);
    match op {
        Op::Insert { r, .. } => {
            let o = run_dml(sem, u, s, p, op);
            lemma_set_rlock_wf(u, o.0, p, r, false);
        },
        _ => {},
    }
}

pub proof fn lemma_await_wf(sem: Sem, u: U, s: State, p: usize)
    requires wf(u, s), (p as int) < s.procs.len(),
    ensures wf(u, await_step(sem, u, s, p).0), await_step(sem, u, s, p).0.procs.len() == s.procs.len(),
{
    assert(wf_proc(u, s.procs[p as int]));
    if let Some(pend) = s.procs[p as int].pending {
        lemma_set_pending_wf(u, s, p, None);
        let s1 = set_pending(s, p, None);
        match pend {
            Op::Lock { c, mode, .. } => lemma_acquire_wf(sem, u, s1, p, c, mode),
            Op::LockOnly { c, .. } => lemma_acquire_wf(sem, u, s1, p, c, Mode::E),
            Op::Insert { .. } | Op::Update { .. } | Op::Delete { .. } => lemma_run_dml_wf(sem, u, s1, p, pend),
            _ => {},
        }
    }
}

/// Every permitted outcome of a well-formed operation is well-formed.
pub proof fn lemma_step_wf(sem: Sem, u: U, s: State, p: usize, op: Op, choice: bool)
    requires wf(u, s), wf_op(u, op),
    ensures wf(u, step(sem, u, s, p, op, choice).0), step(sem, u, s, p, op, choice).0.procs.len() == s.procs.len(),
{
    if (p as int) < s.procs.len() && s.procs[p as int].alive && !(s.procs[p as int].pending is Some && !(op is Await)) {
        if is_txn_op(op) {
            lemma_txn_step_wf(sem, u, s, p, op);
        } else if is_glob_op(op) {
            lemma_glob_step_wf(sem, u, s, p, op);
        } else if is_lock_op(op) {
            lemma_lock_step_wf(sem, u, s, p, op);
        } else if is_row_op(op) {
            lemma_row_step_wf(sem, u, s, p, op, choice);
        } else {
            match op {
                Op::Terminate { target } => if (target as int) < s.procs.len() && s.procs[target as int].alive {
                    lemma_stop_wf(sem, u, s, target);
                },
                Op::Await => lemma_await_wf(sem, u, s, p),
                _ => {},
            }
        }
    }
}

} // verus!
