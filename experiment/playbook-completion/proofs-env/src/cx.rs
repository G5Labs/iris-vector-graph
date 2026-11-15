//! Counterexamples (always compiled): for every control, a concrete instance that satisfies every hypothesis of the
//! generic lemma the control's premise theorems call, except the weakened clause, and whose conclusion is FALSE under
//! the weakened clause. So each clause is necessary for the premises that cite it, and each control's failure is a
//! real one (not an artefact of the proof).
//!
//! Universe `cu()`: cell 0 = global `^H` (the head lock / protected-lock name), cell 1 = global `^X` (a protected
//! cell), cell 2 = a row of table 0, cell 3 = global `^H(5)` (a descendant of `^H`).
use vstd::prelude::*;
use crate::spec::*;
use crate::effects::*;
use crate::headlock::*;
use crate::clauses::*;
use crate::gen::*;

verus! {

pub open spec fn cu() -> U {
    U {
        paths: seq![seq![1u64], seq![2u64], Seq::<u64>::empty(), seq![1u64, 5u64]],
        is_row: seq![false, false, true, false],
        table: seq![0usize, 0usize, 0usize, 0usize],
        texists: seq![true],
        parse: Seq::empty(),
    }
}

pub open spec fn zh() -> Hold { Hold { e: 0, s: 0, de: 0, ds: 0 } }
pub open spec fn he1() -> Hold { Hold { e: 1, s: 0, de: 0, ds: 0 } }
pub open spec fn hs1() -> Hold { Hold { e: 0, s: 1, de: 0, ds: 0 } }

pub open spec fn mk(marks: Seq<nat>, undo: Seq<Undo>, h0: Hold, rl2: bool, pending: Option<Op>) -> Proc {
    Proc {
        alive: true,
        sqlflag: false,
        autocommit: true,
        kind: Kind::Dbapi,
        marks,
        undo,
        locks: seq![h0, zh(), zh(), zh()],
        rlocks: seq![false, false, rl2, false],
        ppg: seq![None, None, None, None],
        pending,
    }
}

pub open spec fn idle() -> Proc { mk(Seq::empty(), Seq::empty(), zh(), false, None) }

pub open spec fn st(g: Seq<Option<Val>>, procs: Seq<Proc>) -> State { State { g, procs } }

pub open spec fn r1() -> spec_fn(int) -> bool { |c: int| c == 1 }

/// x = 7 written by the holder in its open transaction (committed state: none).
pub open spec fn e_x7() -> Undo { Undo { c: 1, old: None, written: Some(Val::Num(7)), ppg: false } }

pub proof fn lemma_cu_wf(s: State)
    requires s.g.len() == 4, 2 <= s.procs.len() <= 3,
        forall|q: int| 0 <= q < s.procs.len() ==> (#[trigger] s.procs[q]).locks.len() == 4 && s.procs[q].rlocks.len() == 4
            && s.procs[q].ppg.len() == 4 && s.procs[q].pending is None
            && (forall|i: int| 0 <= i < s.procs[q].undo.len() ==> (s.procs[q].undo[i].c as int) < 4),
    ensures wf(cu(), s),
{
}

/// One process (0) may hold locks and R entries; every other process holds nothing and logged nothing.
pub proof fn lemma_cu_inv(sem: Sem, s: State, R: spec_fn(int) -> bool)
    requires wf(cu(), s), clean_all(s), s.procs[0].alive,
        forall|q: int, m: int| 1 <= q < s.procs.len() && 0 <= m < 4 ==> !any(#[trigger] s.procs[q].locks[m]),
        forall|q: int| 1 <= q < s.procs.len() ==> (#[trigger] s.procs[q]).undo.len() == 0,
        has_r(s.procs[0].undo, R) ==> excl(s.procs[0].locks[0]),
    ensures inv_h(sem, cu(), s, 0, R),
{
    assert forall|q: int| 0 <= q < s.procs.len() && has_r(#[trigger] s.procs[q].undo, R)
        implies excl(s.procs[q].locks[0]) && s.procs[q].alive by {
        if q >= 1 {
            let i = choose|i: int| 0 <= i < s.procs[q].undo.len() && !(#[trigger] s.procs[q].undo[i]).ppg && R(s.procs[q].undo[i].c as int);
        }
    }
}

// ------------------------------------------------------------------------------------------------ head lock (G1)

/// The holder (process 0) at level 1 holding ^H once, having set ^X = 7.
pub open spec fn s_holder() -> State {
    st(seq![None, Some(Val::Num(7)), None, None], seq![mk(seq![0nat], seq![e_x7()], he1(), false, None), idle()])
}

pub proof fn lemma_s_holder_hyp(sem: Sem, p: usize, op: Op)
    requires p < 2, !(op == (Op::Unlock { c: 0, mode: Mode::E, immediate: true })), forall|c: int| !#[trigger] wr(cu(), op, c), !(op is Await),
        wf_op(cu(), op),
    ensures hl_hyp(sem, cu(), s_holder(), p, op, 0, r1(), 0),
{
    let s = s_holder();
    lemma_cu_wf(s);
    assert(has_r(s.procs[0].undo, r1()) ==> excl(s.procs[0].locks[0]));
    lemma_cu_inv(sem, s, r1());
    assert(u_glob0());
}

pub open spec fn u_glob0() -> bool { is_glob(cu(), 0) && is_glob(cu(), 1) && is_glob(cu(), 3) }

/// CONTROL ctl_unlock_immediate: without deferral, the holder's unlock inside its transaction releases ^H at once while
/// its write to ^X is still uncommitted: G1's conclusion fails (the holder, still in its transaction, no longer holds H;
/// another commit could now build on a head the holder may still roll back, Ledger.cls:390-396).
pub proof fn cx_unlock_immediate()
    ensures ({
        let op = Op::Unlock { c: 0, mode: Mode::E, immediate: false };
        hl_hyp(m_unlock_immediate(), cu(), s_holder(), 0, op, 0, r1(), 0)
            && !hl_concl(m_unlock_immediate(), cu(), s_holder(), 0, op, false, 0, r1(), 0)
    }),
{
    let op = Op::Unlock { c: 0, mode: Mode::E, immediate: false };
    lemma_s_holder_hyp(m_unlock_immediate(), 0, op);
    let s2 = step(m_unlock_immediate(), cu(), s_holder(), 0, op, false).0;
    assert(s2.procs[0].locks[0] == zh());
    assert(level(s2.procs[0]) == 1 && s2.procs[0].alive);
}

/// CONTROL ctl_stop_commits: a stop that commits leaves the holder's uncommitted ^X = 7 (G1's "a stopped one leaves
/// nothing" fails).
pub proof fn cx_stop_commits()
    ensures ({
        let op = Op::Terminate { target: 0 };
        hl_hyp(m_stop_commits(), cu(), s_holder(), 1, op, 0, r1(), 0)
            && !hl_concl(m_stop_commits(), cu(), s_holder(), 1, op, false, 0, r1(), 0)
    }),
{
    reveal_with_fuel(rb, 3);
    reveal_with_fuel(commit_n, 3);
    let op = Op::Terminate { target: 0 };
    lemma_s_holder_hyp(m_stop_commits(), 1, op);
    let s = s_holder();
    let s2 = step(m_stop_commits(), cu(), s, 1, op, false).0;
    assert(s.procs[0].undo.drop_last() =~= Seq::<Undo>::empty());
    assert(base(m_stop_commits(), s, 0)[1] == None::<Val>);
    assert(commit_n(s, 0, 1) == commit_n(commit_top(s, 0), 0, 0));
    assert(s2.g[1] == Some(Val::Num(7)));
    assert(!s2.procs[0].alive);
    assert(r1()(1));
}

/// The holder at level 2 (TSTART again after setting ^X = 7 at level 1).
pub open spec fn s_holder2() -> State {
    st(seq![None, Some(Val::Num(7)), None, None], seq![mk(seq![0nat, 1nat], seq![e_x7()], he1(), false, None), idle()])
}

/// CONTROL ctl_stop_top_level_only: a stop that rolls back only the top level leaves the outer level's ^X = 7.
pub proof fn cx_stop_top_level_only()
    ensures ({
        let op = Op::Terminate { target: 0 };
        hl_hyp(m_stop_top_level_only(), cu(), s_holder2(), 1, op, 0, r1(), 0)
            && !hl_concl(m_stop_top_level_only(), cu(), s_holder2(), 1, op, false, 0, r1(), 0)
    }),
{
    reveal_with_fuel(rb, 3);
    reveal_with_fuel(rollback_n, 3);
    let op = Op::Terminate { target: 0 };
    let s = s_holder2();
    lemma_cu_wf(s);
    lemma_cu_inv(m_stop_top_level_only(), s, r1());
    let s2 = step(m_stop_top_level_only(), cu(), s, 1, op, false).0;
    assert(s.procs[0].undo.subrange(1, 1) =~= Seq::<Undo>::empty());
    assert(s.procs[0].undo.subrange(0, 1) =~= s.procs[0].undo);
    assert(s.procs[0].undo.drop_last() =~= Seq::<Undo>::empty());
    assert(base(m_stop_top_level_only(), s, 0)[1] == None::<Val>);
    assert(rollback_n(m_stop_top_level_only(), s, 0, 1) == rollback_n(m_stop_top_level_only(), undo_top(m_stop_top_level_only(), s, 0), 0, 0));
    assert(s2.g[1] == Some(Val::Num(7)));
    assert(r1()(1));
    assert(u_glob0());
}

/// The holder at level 1 holding ^H, nothing logged yet, ^X = 7 committed.
pub open spec fn s_holder_k() -> State {
    st(seq![None, Some(Val::Num(7)), None, None], seq![mk(seq![0nat], Seq::empty(), he1(), false, None), idle()])
}

/// CONTROL ctl_kill_not_logged: an unlogged KILL of ^X inside the holder's transaction moves the committed state
/// (G1's "unchanged while the transaction is open" fails; a rollback would not restore ^X).
pub proof fn cx_kill_not_logged()
    ensures ({
        let op = Op::Kill { c: 1 };
        hl_hyp(m_kill_not_logged(), cu(), s_holder_k(), 0, op, 0, r1(), 0)
            && !hl_concl(m_kill_not_logged(), cu(), s_holder_k(), 0, op, false, 0, r1(), 0)
    }),
{
    reveal_with_fuel(kill_from, 6);
    let op = Op::Kill { c: 1 };
    let s = s_holder_k();
    lemma_cu_wf(s);
    lemma_cu_inv(m_kill_not_logged(), s, r1());
    assert(cu().paths[1].subrange(0, 1) =~= cu().paths[1]);
    assert(covers(cu(), 1, 1));
    assert(!covers(cu(), 1, 0)) by { assert(cu().paths[0].subrange(0, 1)[0] != cu().paths[1][0]); }
    assert(!covers(cu(), 1, 3)) by { assert(cu().paths[3].subrange(0, 1)[0] != cu().paths[1][0]); }
    assert(disc(cu(), s, 0, op, 0, r1()));
    let s2 = step(m_kill_not_logged(), cu(), s, 0, op, false).0;
    assert(s2.g[1] is None);
    assert(s2.procs[0].undo.len() == 0);
    assert(base(m_kill_not_logged(), s2, 0)[1] is None);
    assert(base(m_kill_not_logged(), s, 0)[1] == Some(Val::Num(7)));
    assert(r1()(1));
    assert(u_glob0());
}

// ------------------------------------------------------------------------------------------------ row locks (G4, G4b, G5, G6)

/// Process 0 at level 1, nothing logged; process 1 idle; no row.
pub open spec fn s_rows() -> State {
    st(seq![None, None, None, None], seq![mk(seq![0nat], Seq::empty(), zh(), false, None), idle()])
}

pub open spec fn rcx_concl(sem: Sem) -> bool {
    let s1 = step(sem, cu(), s_rows(), 0, Op::Insert { r: 2, v: Val::Num(1) }, false).0;
    step(sem, cu(), s1, 1, Op::Delete { r: 2 }, false) == (set_pending(s1, 1, Some(Op::Delete { r: 2 })), Obs::Pending)
}

pub proof fn lemma_rows_hyp()
    ensures wf(cu(), s_rows()), ready(s_rows(), 0), ready(s_rows(), 1), level(s_rows().procs[0]) > 0, row_ok(cu(), 2),
        s_rows().g[2] is None, !row_held(s_rows(), 0, 2),
{
    lemma_cu_wf(s_rows());
}

/// CONTROL ctl_dml_ignores_row_locks: the DELETE does not wait for the row another open transaction inserted.
pub proof fn cx_dml_ignores_row_locks()
    ensures !rcx_concl(m_dml_ignores_row_locks()),
{
    lemma_rows_hyp();
    let s1 = step(m_dml_ignores_row_locks(), cu(), s_rows(), 0, Op::Insert { r: 2, v: Val::Num(1) }, false).0;
    assert(s1.g[2] == Some(Val::Num(1)));
    assert(step(m_dml_ignores_row_locks(), cu(), s1, 1, Op::Delete { r: 2 }, false).1 == Obs::Count(1i64));
}

/// CONTROL ctl_row_lock_statement_only: the inserter keeps no row lock to its end; the DELETE does not wait.
pub proof fn cx_row_lock_statement_only()
    ensures !rcx_concl(m_row_lock_statement_only()),
{
    lemma_rows_hyp();
    let s1 = step(m_row_lock_statement_only(), cu(), s_rows(), 0, Op::Insert { r: 2, v: Val::Num(1) }, false).0;
    assert(s1.g[2] == Some(Val::Num(1)));
    assert(!s1.procs[0].rlocks[2]);
    assert(!row_held(s1, 1, 2));
    assert(step(m_row_lock_statement_only(), cu(), s1, 1, Op::Delete { r: 2 }, false).1 == Obs::Count(1i64));
}

/// Process 0 inserted row 2 in its open transaction (visible, row-locked).
pub open spec fn s_inserted() -> State {
    st(seq![None, None, Some(Val::Num(1)), None],
       seq![mk(seq![0nat], seq![Undo { c: 2, old: None, written: Some(Val::Num(1)), ppg: false }], zh(), true, None), idle()])
}

/// CONTROL ctl_insert_dup_waits: an INSERT of a key another open transaction inserted waits instead of failing -119.
pub proof fn cx_insert_dup_waits()
    ensures wf(cu(), s_inserted()) && ready(s_inserted(), 1) && row_ok(cu(), 2) && s_inserted().g[2] is Some,
        step(m_insert_dup_waits(), cu(), s_inserted(), 1, Op::Insert { r: 2, v: Val::Num(2) }, false).1 != Obs::SqlError(-119i64),
{
    lemma_cu_wf(s_inserted());
    assert(row_held(s_inserted(), 1, 2));
    assert(step(m_insert_dup_waits(), cu(), s_inserted(), 1, Op::Insert { r: 2, v: Val::Num(2) }, false).1 == Obs::Pending);
}

/// Process 0 deleted row 2 in its open transaction (gone from view, row-locked).
pub open spec fn s_deleted() -> State {
    st(seq![None, None, None, None],
       seq![mk(seq![0nat], seq![Undo { c: 2, old: Some(Val::Num(1)), written: None, ppg: false }], zh(), true, None), idle()])
}

/// CONTROL ctl_freedom_wait_only: with the Freedom sharpened to "waits", the INSERT over the uncommitted DELETE has no
/// permitted outcome in which it proceeds (so "not implied" turns into "implied": the Freedom is what keeps P-D9-2's
/// second half a sharpening).
pub proof fn cx_freedom_wait_only()
    ensures wf(cu(), s_deleted()) && ready(s_deleted(), 1) && s_deleted().procs[0].rlocks[2] && row_ok(cu(), 2)
            && s_deleted().g[2] is None,
        !permits(m_freedom_wait_only(), cu(), s_deleted(), 1, Op::Insert { r: 2, v: Val::Num(2) },
            step(m_freedom_wait_only(), cu(), s_deleted(), 1, Op::Insert { r: 2, v: Val::Num(2) }, true).0, Obs::Count(1i64)),
{
    lemma_cu_wf(s_deleted());
    let m = m_freedom_wait_only();
    let op = Op::Insert { r: 2, v: Val::Num(2) };
    assert(!choice_point(m, s_deleted(), 1, op));
    assert(row_held(s_deleted(), 1, 2));
    assert(step(m, cu(), s_deleted(), 1, op, false).1 == Obs::Pending);
    assert(outcomes(m, cu(), s_deleted(), 1, op) =~= seq![step(m, cu(), s_deleted(), 1, op, false)]);
}

// ------------------------------------------------------------------------------------------------ visibility (G7, G8)

/// Process 0 at the start of its transaction; process 1 idle; nothing written.
pub open spec fn s_fresh() -> State {
    st(seq![None, None, None, None], seq![mk(seq![0nat], Seq::empty(), zh(), false, None), idle()])
}

/// CONTROL ctl_no_dirty_reads: a $GET in another process does not see the open transaction's write.
pub proof fn cx_no_dirty_reads()
    ensures wf(cu(), s_fresh()) && fresh_txn(s_fresh().procs[0]) && is_glob(cu(), 1),
        step(m_no_dirty_reads(), cu(), step(m_no_dirty_reads(), cu(), s_fresh(), 0, Op::Set { c: 1, v: Val::Num(7) }, false).0,
            1, Op::Get { c: 1 }, false).1 != Obs::Value(Some(Val::Num(7))),
{
    reveal_with_fuel(rb, 3);
    reveal_with_fuel(rollback_n, 3);
    reveal_with_fuel(cv_from, 4);
    lemma_cu_wf(s_fresh());
    let m = m_no_dirty_reads();
    let s1 = step(m, cu(), s_fresh(), 0, Op::Set { c: 1, v: Val::Num(7) }, false).0;
    let ph = Sem { rollback_physical: true, ..m };
    assert(s1.procs[0].undo.subrange(0, 1) =~= s1.procs[0].undo);
    assert(s1.procs[0].undo.subrange(0, 1).drop_last() =~= Seq::<Undo>::empty());
    assert(rollback_n(ph, s1, 0, 1) == rollback_n(ph, undo_top(ph, s1, 0), 0, 0));
    assert(rollback_all(ph, s1, 0).g[1] is None);
    assert(cv_from(m, s1, 1, 0).g[1] is None);
}

/// CONTROL ctl_select_committed_only: a SELECT in another process does not list the open transaction's inserted row.
pub proof fn cx_select_committed_only()
    ensures ({
        let m = m_select_committed_only();
        let s1 = step(m, cu(), s_rows(), 0, Op::Insert { r: 2, v: Val::Num(1) }, false).0;
        step(m, cu(), s1, 1, Op::Select { t: 0 }, false).1 != select_obs(cu(), s1.g, 0)
    }),
{
    reveal_with_fuel(rb, 3);
    reveal_with_fuel(rollback_n, 3);
    reveal_with_fuel(cv_from, 4);
    reveal_with_fuel(rows_from, 6);
    lemma_rows_hyp();
    let m = m_select_committed_only();
    let s1 = step(m, cu(), s_rows(), 0, Op::Insert { r: 2, v: Val::Num(1) }, false).0;
    let ph = Sem { rollback_physical: true, ..m };
    assert(s1.g[2] == Some(Val::Num(1)));
    assert(s1.procs[0].undo =~= seq![Undo { c: 2, old: None, written: Some(Val::Num(1)), ppg: false }]);
    assert(s1.procs[0].undo.subrange(0, 1) =~= s1.procs[0].undo);
    assert(s1.procs[0].undo.subrange(0, 1).drop_last() =~= Seq::<Undo>::empty());
    assert(rollback_n(ph, s1, 0, 1) == rollback_n(ph, undo_top(ph, s1, 0), 0, 0));
    assert(cv_from(m, s1, 1, 0).g[2] is None);
    assert(rows_from(cu(), s1.g, 0, 0).len() == 1);
    assert(rows_from(cu(), cv_from(m, s1, 1, 0).g, 0, 0).len() == 0);
}

// ------------------------------------------------------------------------------------------------ rollback (G9, G9b, G20, G10)

/// CONTROL ctl_rollback_physical: the rollback overwrites the other process's later write.
pub proof fn cx_rollback_physical()
    ensures ({
        let m = m_rollback_physical();
        let s1 = step(m, cu(), s_fresh(), 0, Op::Set { c: 1, v: Val::Num(1) }, false).0;
        let s2 = step(m, cu(), s1, 1, Op::Set { c: 1, v: Val::Num(2) }, false).0;
        step(m, cu(), s2, 0, Op::TRollback, false).0.g[1] != Some(Val::Num(2))
    }),
{
    reveal_with_fuel(rb, 3);
    reveal_with_fuel(rollback_n, 3);
    lemma_cu_wf(s_fresh());
    let m = m_rollback_physical();
    let s1 = step(m, cu(), s_fresh(), 0, Op::Set { c: 1, v: Val::Num(1) }, false).0;
    let s2 = step(m, cu(), s1, 1, Op::Set { c: 1, v: Val::Num(2) }, false).0;
    assert(s2.procs[0].undo =~= seq![Undo { c: 1, old: None, written: Some(Val::Num(1)), ppg: false }]);
    assert(s2.procs[0].undo.subrange(0, 1) =~= s2.procs[0].undo);
    assert(s2.procs[0].undo.subrange(0, 1).drop_last() =~= Seq::<Undo>::empty());
    assert(rollback_n(m, s2, 0, 1) == rollback_n(m, undo_top(m, s2, 0), 0, 0));
    assert(step(m, cu(), s2, 0, Op::TRollback, false).0.g[1] is None);
}

/// CONTROL ctl_incr_rolled_back: $INCREMENT inside a transaction is logged (so a rollback would undo it).
pub proof fn cx_incr_rolled_back()
    ensures step(m_incr_rolled_back(), cu(), s_fresh(), 0, Op::Incr { c: 1 }, false).0.procs[0].undo != s_fresh().procs[0].undo,
{
    lemma_cu_wf(s_fresh());
    assert(step(m_incr_rolled_back(), cu(), s_fresh(), 0, Op::Incr { c: 1 }, false).0.procs[0].undo.len() == 1);
}

// ------------------------------------------------------------------------------------------------ levels (G11, G12)

pub open spec fn s_level2() -> State {
    st(seq![None, None, None, None], seq![mk(seq![0nat, 0nat], Seq::empty(), zh(), false, None), idle()])
}

/// CONTROL ctl_rollback_one_undoes_all: TROLLBACK 1 at level 2 ends both levels.
pub proof fn cx_rollback_one_undoes_all()
    ensures level(step(m_rollback_one_undoes_all(), cu(), s_level2(), 0, Op::TRollbackOne, false).0.procs[0]) != 1,
{
    reveal_with_fuel(rollback_n, 4);
    lemma_cu_wf(s_level2());
    let m = m_rollback_one_undoes_all();
    let s = s_level2();
    let a = undo_top(m, s, 0);
    assert(level(a.procs[0]) == 1);
    let b = undo_top(m, a, 0);
    assert(level(b.procs[0]) == 0);
    assert(rollback_n(m, s, 0, 2) == rollback_n(m, a, 0, 1));
    assert(rollback_n(m, a, 0, 1) == rollback_n(m, b, 0, 0));
}

/// CONTROL ctl_sql_commit_ends_all (the product's premise, Txn.cls:8): SQL COMMIT at level 2 ends both levels.
pub proof fn cx_sql_commit_ends_all()
    ensures level(step(m_sql_commit_ends_all(), cu(), s_level2(), 0, Op::SqlCommit, false).0.procs[0]) == 0,
{
    reveal_with_fuel(commit_n, 4);
    lemma_cu_wf(s_level2());
    let m = m_sql_commit_ends_all();
    let s = s_level2();
    let a = commit_top(s, 0);
    let b = commit_top(a, 0);
    assert(commit_n(s, 0, 2) == commit_n(a, 0, 1));
    assert(commit_n(a, 0, 1) == commit_n(b, 0, 0));
}

// ------------------------------------------------------------------------------------------------ locks (G14, G15, G16)

/// Process 0 holds ^H; process 1 waits for it; process 2 is idle.
pub open spec fn s_wait() -> State {
    st(seq![None, None, None, None],
       seq![mk(Seq::empty(), Seq::empty(), he1(), false, None), mk(Seq::empty(), Seq::empty(), zh(), false,
            Some(Op::Lock { c: 0, mode: Mode::E, wait: true })), idle()])
}

/// CONTROL ctl_lock_wait_never_granted: the waiter is still blocked after the holder is stopped.
pub proof fn cx_lock_wait_never_granted()
    ensures only_t_conflicts(m_lock_wait_never_granted(), cu(), s_wait(), 1, 0, 0, Mode::E),
        step(m_lock_wait_never_granted(), cu(), step(m_lock_wait_never_granted(), cu(), s_wait(), 2, Op::Terminate { target: 0 }, false).0,
            1, Op::Await, false).1 == Obs::Blocked,
{
    let m = m_lock_wait_never_granted();
    let s = s_wait();
    assert forall|y: int, mm: int| 0 <= y < s.procs.len() && y != 1 && y != 0 && s.procs[y].alive && 0 <= mm < cu().n()
        && related(m, cu(), mm, 0) implies !hold_conflicts(m, #[trigger] s.procs[y].locks[mm], Mode::E) by {
        assert(y == 2);
    }
}

/// Process 0 holds ^H exclusively.
pub open spec fn s_parent() -> State {
    st(seq![None, None, None, None], seq![mk(Seq::empty(), Seq::empty(), he1(), false, None), idle()])
}

/// CONTROL ctl_flat_lock_names: with flat names, a lock on ^H(5) is granted while ^H is held exclusively.
pub proof fn cx_flat_lock_names()
    ensures covers(cu(), 0, 3),
        step(m_flat_lock_names(), cu(), s_parent(), 1, Op::Lock { c: 3, mode: Mode::S, wait: false }, false).1 == Obs::Test(true),
{
    assert(cu().paths[3].subrange(0, 1) =~= cu().paths[0]);
    let m = m_flat_lock_names();
    assert(!conflicts(m, cu(), s_parent(), 1, 3, Mode::S)) by {
        assert forall|q: int, mm: int| 0 <= q < 2 && q != 1 && s_parent().procs[q].alive && 0 <= mm < 4 && related(m, cu(), mm, 3)
            implies !hold_conflicts(m, #[trigger] s_parent().procs[q].locks[mm], Mode::S) by {
            assert(mm == 3);
        }
    }
}

/// Process 0 holds ^H shared.
pub open spec fn s_shared() -> State {
    st(seq![None, None, None, None], seq![mk(Seq::empty(), Seq::empty(), hs1(), false, None), idle()])
}

/// CONTROL ctl_shared_conflicts_shared: a second shared request is refused.
pub proof fn cx_shared_conflicts_shared()
    ensures step(m_shared_conflicts_shared(), cu(), s_shared(), 1, Op::Lock { c: 0, mode: Mode::S, wait: false }, false).1 == Obs::Test(false),
{
    let m = m_shared_conflicts_shared();
    assert(cu().paths[0].subrange(0, 1) =~= cu().paths[0]);
    assert(covers(cu(), 0, 0));
    assert(hold_conflicts(m, s_shared().procs[0].locks[0], Mode::S));
    assert(conflicts(m, cu(), s_shared(), 1, 0, Mode::S));
}

} // verus!
