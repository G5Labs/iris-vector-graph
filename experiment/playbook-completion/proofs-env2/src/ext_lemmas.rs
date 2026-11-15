//! proofs-env2: the extension's operations in the footprint, well-formedness and head-lock proofs.
//! `xok`: one construct of the actor x keeps the state well formed, stays inside its footprint (`full_eff`), keeps x's
//! user locks (x clean), x clean and alive, and -- when x is inside a transaction -- its level and its committed state on
//! R (the cells it writes outside R may change only by logged writes, which `base` undoes).
use vstd::prelude::*;
use crate::spec::*;
use crate::ext::*;
use crate::wf::*;
use crate::effects::*;
use crate::headlock::*;

verus! {

pub open spec fn xok(sem: Sem, u: U, s: State, s2: State, x: usize, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool) -> bool {
    &&& wf(u, s2)
    &&& s2.procs.len() == s.procs.len()
    &&& full_eff(sem, u, s, s2, x, w)
    &&& (clean_proc(s.procs[x as int]) ==> s2.procs[x as int].locks == s.procs[x as int].locks && clean_proc(s2.procs[x as int]))
    &&& s2.procs[x as int].alive == s.procs[x as int].alive
    &&& (level(s.procs[x as int]) > 0 ==> level(s2.procs[x as int]) == level(s.procs[x as int])
            && eq_r(base(sem, s2, x as int), base(sem, s, x as int), R))
}

/// The writes outside a transaction or unlogged go to cells outside R.
pub open spec fn w_out(w: spec_fn(int) -> bool, R: spec_fn(int) -> bool) -> bool {
    forall|c: int| #[trigger] w(c) ==> !R(c)
}

pub proof fn lemma_xok_refl(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(),
    ensures xok(sem, u, s, s, x, w, R),
{
    lemma_eff_refl(sem, u, s, x, w);
}

pub proof fn lemma_xok_trans(sem: Sem, u: U, s: State, s1: State, s2: State, x: usize, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), xok(sem, u, s, s1, x, w, R), xok(sem, u, s1, s2, x, w, R),
    ensures xok(sem, u, s, s2, x, w, R),
{
    lemma_eff_trans(sem, u, s, s1, s2, x, w);
    assert(wf_proc(u, s.procs[x as int]) && wf_proc(u, s1.procs[x as int]) && wf_proc(u, s2.procs[x as int]));
    lemma_rb_len(sem, s.g, s.procs[x as int].ppg, s.procs[x as int].undo);
    lemma_rb_len(sem, s1.g, s1.procs[x as int].ppg, s1.procs[x as int].undo);
    lemma_rb_len(sem, s2.g, s2.procs[x as int].ppg, s2.procs[x as int].undo);
}

// ------------------------------------------------------------------------------------------------ primitives

pub proof fn lemma_write_xok(sem: Sem, u: U, s: State, x: usize, c: usize, v: Option<Val>, logged: bool,
    w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), (c as int) < u.n(), w(c as int), w_out(w, R), s.procs[x as int].alive,
    ensures xok(sem, u, s, write(s, x, c, v, logged), x, w, R),
{
    let s2 = write(s, x, c, v, logged);
    lemma_write_eff(sem, u, s, x, c, v, logged, w);
    lemma_write_wf(u, s, x, c, v, logged);
    assert(wf_proc(u, s.procs[x as int]));
    if level(s.procs[x as int]) > 0 {
        if logged {
            lemma_base_write(sem, u, s, x, c, v);
        } else {
            assert(!R(c as int));
            lemma_rb_len(sem, s2.g, s2.procs[x as int].ppg, s2.procs[x as int].undo);
            lemma_rb_len(sem, s.g, s.procs[x as int].ppg, s.procs[x as int].undo);
            assert forall|d: int| 0 <= d < base(sem, s2, x as int).len() && (#[trigger] R(d))
                implies base(sem, s2, x as int)[d] == base(sem, s, x as int)[d] by {
                lemma_base_unlogged(sem, u, s, x, x, c, v, d);
            }
        }
    }
}

pub proof fn lemma_upd_same_xok(sem: Sem, u: U, s: State, x: usize, pr: Proc, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), wf_proc(u, pr), pr.locks == s.procs[x as int].locks,
        pr.rlocks.len() == s.procs[x as int].rlocks.len(), pr.alive == s.procs[x as int].alive, pr.undo == s.procs[x as int].undo,
        pr.marks == s.procs[x as int].marks, pr.alive || pr.pending is None, pr.ppg.len() == s.procs[x as int].ppg.len(),
        !pr.alive ==> forall|r: int| 0 <= r < pr.rlocks.len() ==> !(#[trigger] pr.rlocks[r]),
    ensures xok(sem, u, s, upd(s, x, pr), x, w, R),
{
    let s2 = upd(s, x, pr);
    lemma_upd_wf(u, s, x, pr);
    assert(wf_proc(u, s.procs[x as int]));
    lemma_base_eq(sem, u, s, s2, x as int);
}

pub proof fn lemma_set_rlock_xok(sem: Sem, u: U, s: State, x: usize, r: usize, b: bool, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), (r as int) < u.n(), s.procs[x as int].alive,
    ensures xok(sem, u, s, set_rlock(s, x, r, b), x, w, R),
{
    lemma_set_rlock_eff(sem, u, s, x, r, b, w);
    lemma_set_rlock_wf(u, s, x, r, b);
    lemma_base_eq(sem, u, s, set_rlock(s, x, r, b), x as int);
}

pub proof fn lemma_set_pending_xok(sem: Sem, u: U, s: State, x: usize, op: Option<Op>, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), s.procs[x as int].alive, op matches Some(o) ==> wf_op(u, o),
    ensures xok(sem, u, s, set_pending(s, x, op), x, w, R),
{
    lemma_set_pending_eff(sem, u, s, x, op, w);
    lemma_set_pending_wf(u, s, x, op);
    lemma_base_eq(sem, u, s, set_pending(s, x, op), x as int);
}

pub proof fn lemma_set_autocommit_xok(sem: Sem, u: U, s: State, x: usize, on: bool, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), s.procs[x as int].alive,
    ensures xok(sem, u, s, set_autocommit(s, x, on), x, w, R),
{
    assert(wf_proc(u, s.procs[x as int]));
    lemma_upd_eff(sem, u, s, x, Proc { autocommit: on, ..s.procs[x as int] }, w);
    lemma_upd_same_xok(sem, u, s, x, Proc { autocommit: on, ..s.procs[x as int] }, w, R);
}

/// select_txn (a query with autocommit off at level 0 opens a level under the mutant only).
pub proof fn lemma_select_txn_xok(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), s.procs[x as int].alive,
    ensures xok(sem, u, s, select_txn(sem, s, x), x, w, R),
{
    lemma_select_txn_eff(sem, u, s, x, w);
    lemma_select_txn_wf(sem, u, s, x);
    let pr = s.procs[x as int];
    assert(wf_proc(u, pr));
    if level(pr) == 0 && sem.select_opens_txn && !pr.autocommit {
        let s2 = select_txn(sem, s, x);
        assert(clean_proc(pr) ==> s2.procs[x as int].locks == pr.locks && clean_proc(s2.procs[x as int]));
    } else {
        assert(select_txn(sem, s, x) == s);
    }
}

pub proof fn lemma_failed_stmt_xok(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), s.procs[x as int].alive,
    ensures xok(sem, u, s, failed_stmt(sem, s, x), x, w, R),
{
    lemma_failed_stmt_eff(sem, u, s, x, w);
    lemma_failed_stmt_wf(sem, u, s, x);
    let pr = s.procs[x as int];
    assert(wf_proc(u, pr));
    if sem.failed_dml_opens_txn && level(pr) == 0 && !pr.autocommit {
        let s2 = failed_stmt(sem, s, x);
        assert(clean_proc(pr) ==> s2.procs[x as int].locks == pr.locks && clean_proc(s2.procs[x as int]));
    } else {
        assert(failed_stmt(sem, s, x) == s);
    }
}

/// One DML statement (INSERT, or UPDATE / DELETE by key): the statement transaction, the logged write, the row lock.
pub proof fn lemma_dml_xok(sem: Sem, u: U, s: State, x: usize, r: usize, nv: Option<Val>, insert: bool,
    w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), (r as int) < u.n(), u.is_row[r as int], w(r as int), w_out(w, R),
        s.procs[x as int].alive,
    ensures insert && nv is Some ==> xok(sem, u, s, dml_insert(sem, u, s, x, r, nv->Some_0).0, x, w, R),
        !insert ==> xok(sem, u, s, dml_change(sem, u, s, x, r, nv).0, x, w, R),
{
    let pr = s.procs[x as int];
    assert(wf_proc(u, pr));
    lemma_dml_eff(sem, u, s, x, r, nv, insert, w);
    lemma_failed_stmt_xok(sem, u, s, x, w, R);
    lemma_xok_refl(sem, u, s, x, w, R);
    if (insert && s.g[r as int] is None) || (!insert && s.g[r as int] is Some) {
        let b = stmt_begin(s, x);
        lemma_stmt_begin_wf(u, s, x);
        let s2 = write(b.0, x, r, nv, true);
        lemma_write_wf(u, b.0, x, r, nv, true);
        if level(pr) > 0 {
            assert(b.0 == s && !b.1);
            lemma_write_xok(sem, u, s, x, r, nv, true, w, R);
            lemma_set_rlock_xok(sem, u, s2, x, r, true, w, R);
            lemma_xok_trans(sem, u, s, s2, set_rlock(s2, x, r, true), x, w, R);
        } else {
            // a level opened for the statement: implicit (committed at its end) or SQL-owned (autocommit off)
            lemma_dml_eff(sem, u, s, x, r, nv, insert, w);
            lemma_run_dml_like_wf(sem, u, s, x, r, nv);
            let fin = if b.1 { commit_top(s2, x) } else if sem.row_lock_held { set_rlock(s2, x, r, true) } else { s2 };
            lemma_commit_top_wf(u, s2, x);
            lemma_set_rlock_wf(u, s2, x, r, true);
            assert(clean_proc(pr) ==> fin.procs[x as int].locks == pr.locks && clean_proc(fin.procs[x as int])) by {
                if clean_proc(pr) {
                    assert(s2.procs[x as int].locks == pr.locks);
                    if b.1 {
                        assert forall|m: int| 0 <= m < pr.locks.len() implies fin.procs[x as int].locks[m] == pr.locks[m] by {
                            assert(pr.locks[m].de == 0 && pr.locks[m].ds == 0);
                        }
                        assert(fin.procs[x as int].locks =~= pr.locks);
                    }
                }
            }
        }
    }
}

pub proof fn lemma_run_dml_like_wf(sem: Sem, u: U, s: State, x: usize, r: usize, nv: Option<Val>)
    requires wf(u, s), (x as int) < s.procs.len(), (r as int) < u.n(),
    ensures wf(u, write(stmt_begin(s, x).0, x, r, nv, true)),
{
    lemma_stmt_begin_wf(u, s, x);
    lemma_write_wf(u, stmt_begin(s, x).0, x, r, nv, true);
}

// ------------------------------------------------------------------------------------------------ E-1

pub proof fn lemma_own_dml_xok(sem: Sem, u: U, s: State, x: usize, r: usize, ins: Option<Val>, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), (r as int) < u.n(), w(r as int), w_out(w, R), s.procs[x as int].alive,
    ensures xok(sem, u, s, own_dml(sem, u, s, x, r, ins).0, x, w, R),
{
    lemma_xok_refl(sem, u, s, x, w, R);
    lemma_failed_stmt_xok(sem, u, s, x, w, R);
    lemma_write_xok(sem, u, s, x, r, ins, false, w, R);
}

pub proof fn lemma_plain_dml_xok(sem: Sem, u: U, s: State, x: usize, r: usize, ins: Option<Val>, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), (r as int) < u.n(), u.is_row[r as int], w(r as int), w_out(w, R),
        s.procs[x as int].alive,
    ensures xok(sem, u, s, plain_dml(sem, u, s, x, r, ins).0, x, w, R),
{
    match ins {
        Some(v) => lemma_dml_xok(sem, u, s, x, r, Some(v), true, w, R),
        None => lemma_dml_xok(sem, u, s, x, r, None, false, w, R),
    }
}

pub proof fn lemma_emb_dml_xok(sem: Sem, u: U, s: State, x: usize, r: usize, ins: Option<Val>, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), (r as int) < u.n(), u.is_row[r as int], w(r as int), w_out(w, R),
        s.procs[x as int].alive,
    ensures xok(sem, u, s, emb_dml(sem, u, s, x, r, ins).0, x, w, R),
{
    if sem.emb_own_txn {
        lemma_own_dml_xok(sem, u, s, x, r, ins, w, R);
    } else if sem.emb_ignores_autocommit && level(s.procs[x as int]) == 0 {
        let ac = s.procs[x as int].autocommit;
        let s1 = set_autocommit(s, x, true);
        lemma_set_autocommit_xok(sem, u, s, x, true, w, R);
        lemma_plain_dml_xok(sem, u, s1, x, r, ins, w, R);
        let o = plain_dml(sem, u, s1, x, r, ins);
        lemma_xok_trans(sem, u, s, s1, o.0, x, w, R);
        lemma_set_autocommit_xok(sem, u, o.0, x, ac, w, R);
        lemma_xok_trans(sem, u, s, o.0, set_autocommit(o.0, x, ac), x, w, R);
    } else {
        lemma_plain_dml_xok(sem, u, s, x, r, ins, w, R);
    }
}

pub proof fn lemma_emb_register_xok(sem: Sem, u: U, s: State, x: usize, r: usize, choice: bool, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), (r as int) < u.n(), u.is_row[r as int], w(r as int), w_out(w, R),
        s.procs[x as int].alive,
    ensures xok(sem, u, s, emb_register(sem, u, s, x, r, choice).0, x, w, R),
{
    lemma_xok_refl(sem, u, s, x, w, R);
    lemma_failed_stmt_xok(sem, u, s, x, w, R);
    lemma_emb_dml_xok(sem, u, s, x, r, Some(Val::Empty), w, R);
    lemma_set_pending_xok(sem, u, s, x, Some(Op::EmbRegister { r }), w, R);
    let o = emb_dml(sem, u, s, x, r, Some(Val::Empty));
    lemma_set_rlock_xok(sem, u, o.0, x, r, false, w, R);
    lemma_xok_trans(sem, u, s, o.0, set_rlock(o.0, x, r, false), x, w, R);
}

pub proof fn lemma_emb_assert_xok(sem: Sem, u: U, s: State, x: usize, rn: usize, rr: usize, empty: bool, vt: Val,
    w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), (rn as int) < u.n(), u.is_row[rn as int], (rr as int) < u.n(), u.is_row[rr as int],
        w(rn as int), w(rr as int), w_out(w, R), s.procs[x as int].alive,
    ensures xok(sem, u, s, emb_assert(sem, u, s, x, rn, rr, empty, vt).0, x, w, R),
{
    lemma_xok_refl(sem, u, s, x, w, R);
    lemma_failed_stmt_xok(sem, u, s, x, w, R);
    let o1 = if !emb_visible(sem, s, x, rn) { emb_dml(sem, u, s, x, rn, Some(Val::Empty)) } else { (s, Obs::Ok) };
    lemma_emb_dml_xok(sem, u, s, x, rn, Some(Val::Empty), w, R);
    assert(xok(sem, u, s, o1.0, x, w, R));
    let o2 = if !emb_visible(sem, o1.0, x, rr) { emb_dml(sem, u, o1.0, x, rr, Some(vt)) } else { (o1.0, Obs::Ok) };
    lemma_xok_refl(sem, u, o1.0, x, w, R);
    lemma_emb_dml_xok(sem, u, o1.0, x, rr, Some(vt), w, R);
    lemma_xok_trans(sem, u, s, o1.0, o2.0, x, w, R);
}

// ------------------------------------------------------------------------------------------------ INSERT ... SELECT

pub proof fn lemma_rows_from(u: U, g: Seq<Option<Val>>, t: usize, j: nat)
    requires g.len() == u.n(), u.n() <= usize::MAX,
    ensures forall|i: int| 0 <= i < rows_from(u, g, t, j).len() ==> {
        let e = #[trigger] rows_from(u, g, t, j)[i];
        &&& j <= e.0 < u.n() && u.is_row[e.0 as int] && u.table[e.0 as int] == t && g[e.0 as int] == Some(e.1)
    },
    decreases u.n() - j,
{
    if j < u.n() {
        lemma_rows_from(u, g, t, j + 1);
        let rest = rows_from(u, g, t, j + 1);
        if u.is_row[j as int] && u.table[j as int] == t && g[j as int] is Some {
            let l = seq![(j as usize, g[j as int]->Some_0)] + rest;
            assert forall|i: int| 0 <= i < l.len() implies {
                let e = #[trigger] l[i];
                &&& j <= e.0 < u.n() && u.is_row[e.0 as int] && u.table[e.0 as int] == t && g[e.0 as int] == Some(e.1)
            } by {
                if i > 0 { assert(l[i] == rest[i - 1]); }
            }
        }
    }
}

pub proof fn lemma_find_twin(u: U, t: usize, k: usize, j: nat)
    requires u.n() <= usize::MAX,
    ensures find_twin(u, t, k, j) matches Some(x) ==> (x as int) < u.n() && u.is_row[x as int] && u.table[x as int] == t,
    decreases u.n() - j,
{
    if j < u.n() { lemma_find_twin(u, t, k, j + 1); }
}

pub open spec fn src_ok(u: U, to: usize, src: Seq<(usize, Val)>) -> bool {
    forall|i: int| 0 <= i < src.len() ==> {
        let tw = twin(u, to, (#[trigger] src[i]).0);
        (tw as int) < u.n() && u.is_row[tw as int] && u.table[tw as int] == to
    }
}

pub proof fn lemma_src_ok(u: U, g: Seq<Option<Val>>, from: usize, to: usize)
    requires g.len() == u.n(),  u.n() <= usize::MAX, twins_ok(u, to, rows_from(u, g, from, 0)),
    ensures src_ok(u, to, rows_from(u, g, from, 0)),
{
    let src = rows_from(u, g, from, 0);
    lemma_rows_from(u, g, from, 0);
    assert forall|i: int| 0 <= i < src.len() implies {
        let tw = twin(u, to, (#[trigger] src[i]).0);
        (tw as int) < u.n() && u.is_row[tw as int] && u.table[tw as int] == to
    } by {
        lemma_find_twin(u, to, u.key[src[i].0 as int], 0);
    }
}

pub open spec fn w_to(u: U, to: usize, w: spec_fn(int) -> bool) -> bool {
    forall|c: int| 0 <= c < u.n() && u.is_row[c] && u.table[c] == to ==> #[trigger] w(c)
}

pub proof fn lemma_is_write_xok(sem: Sem, u: U, s: State, x: usize, to: usize, src: Seq<(usize, Val)>, i: nat, n: nat,
    w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), src_ok(u, to, src), w_to(u, to, w), w_out(w, R), s.procs[x as int].alive,
        level(s.procs[x as int]) > 0,
    ensures xok(sem, u, s, is_write(u, s, x, to, src, i, n), x, w, R),
        level(is_write(u, s, x, to, src, i, n).procs[x as int]) == level(s.procs[x as int]),
    decreases n - i,
{
    lemma_xok_refl(sem, u, s, x, w, R);
    if i < n && i < src.len() {
        let tw = twin(u, to, src[i as int].0);
        assert((tw as int) < u.n() && u.is_row[tw as int] && u.table[tw as int] == to);
        let s1 = write(s, x, tw, Some(src[i as int].1), true);
        lemma_write_xok(sem, u, s, x, tw, Some(src[i as int].1), true, w, R);
        lemma_is_write_xok(sem, u, s1, x, to, src, i + 1, n, w, R);
        lemma_xok_trans(sem, u, s, s1, is_write(u, s1, x, to, src, i + 1, n), x, w, R);
    }
}

pub proof fn lemma_is_lock_xok(sem: Sem, u: U, s: State, x: usize, to: usize, src: Seq<(usize, Val)>, i: nat, n: nat,
    w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), src_ok(u, to, src), s.procs[x as int].alive,
    ensures xok(sem, u, s, is_lock(u, s, x, to, src, i, n), x, w, R),
        level(is_lock(u, s, x, to, src, i, n).procs[x as int]) == level(s.procs[x as int]),
    decreases n - i,
{
    lemma_xok_refl(sem, u, s, x, w, R);
    if i < n && i < src.len() {
        let tw = twin(u, to, src[i as int].0);
        let s1 = set_rlock(s, x, tw, true);
        lemma_set_rlock_xok(sem, u, s, x, tw, true, w, R);
        lemma_is_lock_xok(sem, u, s1, x, to, src, i + 1, n, w, R);
        lemma_xok_trans(sem, u, s, s1, is_lock(u, s1, x, to, src, i + 1, n), x, w, R);
    }
}

/// The statement's level opened at level 0 (implicit or SQL-owned) and its writes: the ending keeps the locks (they
/// held nothing deferred at level 0).
pub proof fn lemma_insert_select_xok(sem: Sem, u: U, s: State, x: usize, from: usize, to: usize, w: spec_fn(int) -> bool,
    R: spec_fn(int) -> bool)
    requires wf(u, s),  (x as int) < s.procs.len(), (from as int) < u.texists.len(), (to as int) < u.texists.len(),
        w_to(u, to, w), w_out(w, R), s.procs[x as int].alive,
    ensures xok(sem, u, s, insert_select(sem, u, s, x, from, to).0, x, w, R),
{
    let pr = s.procs[x as int];
    assert(wf_proc(u, pr));
    lemma_xok_refl(sem, u, s, x, w, R);
    lemma_failed_stmt_xok(sem, u, s, x, w, R);
    if !others_hold_rows(s, x) && u.texists[from as int] && u.texists[to as int] {
        let src = rows_from(u, s.g, from, 0);
        if twins_ok(u, to, src) {
            lemma_src_ok(u, s.g, from, to);
            let fail = first_fail(u, s.g, to, src, 0);
            if !(fail is Some && (sem.statement_atomic || fail->Some_0 == 0)) {
                let n: nat = match fail { Some(i) => i, None => src.len() };
                let b = stmt_begin(s, x);
                lemma_stmt_begin_wf(u, s, x);
                lemma_stmt_begin_eff(sem, u, s, x, w);
                assert(level(b.0.procs[x as int]) > 0);
                let s2 = is_write(u, b.0, x, to, src, 0, n);
                lemma_is_write_xok(sem, u, b.0, x, to, src, 0, n, w, R);
                let s3 = if b.1 { commit_top(s2, x) } else if sem.row_lock_held { is_lock(u, s2, x, to, src, 0, n) } else { s2 };
                if level(pr) > 0 {
                    assert(b.0 == s);
                    lemma_is_lock_xok(sem, u, s2, x, to, src, 0, n, w, R);
                    lemma_xok_trans(sem, u, s, s2, is_lock(u, s2, x, to, src, 0, n), x, w, R);
                } else {
                    lemma_eff_trans(sem, u, s, b.0, s2, x, w);
                    lemma_commit_top_wf(u, s2, x);
                    lemma_commit_top_eff(sem, u, s2, x, w);
                    lemma_eff_trans(sem, u, s, s2, commit_top(s2, x), x, w);
                    lemma_is_lock_xok(sem, u, s2, x, to, src, 0, n, w, R);
                    lemma_eff_trans(sem, u, s, s2, is_lock(u, s2, x, to, src, 0, n), x, w);
                    assert(clean_proc(pr) ==> s3.procs[x as int].locks == pr.locks && clean_proc(s3.procs[x as int])) by {
                        if clean_proc(pr) {
                            assert(b.0.procs[x as int].locks == pr.locks);
                            assert(s2.procs[x as int].locks == pr.locks);
                            if b.1 {
                                assert forall|m: int| 0 <= m < pr.locks.len() implies s3.procs[x as int].locks[m] == pr.locks[m] by {
                                    assert(pr.locks[m].de == 0 && pr.locks[m].ds == 0);
                                }
                                assert(s3.procs[x as int].locks =~= pr.locks);
                            }
                        }
                    }
                }
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ X2-BATCH, X2-IOU

pub proof fn lemma_batch_run_xok(sem: Sem, u: U, s: State, x: usize, t: usize, rows: Seq<(usize, Val)>, i: nat, n: nat,
    w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), batch_ok(u, t, rows), w_to(u, t, w), w_out(w, R), s.procs[x as int].alive,
    ensures xok(sem, u, s, batch_run(sem, u, s, x, rows, i, n).0, x, w, R),
    decreases rows.len() - i,
{
    lemma_xok_refl(sem, u, s, x, w, R);
    if i < rows.len() {
        let r = rows[i as int].0;
        assert((r as int) < u.n() && u.is_row[r as int] && u.table[r as int] == t);
        assert(w(r as int));
        let o = dml_insert(sem, u, s, x, r, rows[i as int].1);
        lemma_dml_xok(sem, u, s, x, r, Some(rows[i as int].1), true, w, R);
        lemma_batch_run_xok(sem, u, o.0, x, t, rows, i + 1, n + 1, w, R);
        lemma_batch_run_xok(sem, u, o.0, x, t, rows, i + 1, n, w, R);
        lemma_xok_trans(sem, u, s, o.0, batch_run(sem, u, o.0, x, rows, i + 1, n + 1).0, x, w, R);
        lemma_xok_trans(sem, u, s, o.0, batch_run(sem, u, o.0, x, rows, i + 1, n).0, x, w, R);
    }
}

pub proof fn lemma_insert_many_xok(sem: Sem, u: U, s: State, x: usize, t: usize, rows: Seq<(usize, Val)>,
    w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), batch_ok(u, t, rows), w_to(u, t, w), w_out(w, R), s.procs[x as int].alive,
    ensures xok(sem, u, s, insert_many(sem, u, s, x, rows).0, x, w, R),
{
    lemma_xok_refl(sem, u, s, x, w, R);
    lemma_failed_stmt_xok(sem, u, s, x, w, R);
    lemma_batch_run_xok(sem, u, s, x, t, rows, 0, 0, w, R);
    if rows.len() == 1 {
        let r = rows[0].0;
        assert((r as int) < u.n() && u.is_row[r as int] && u.table[r as int] == t);
        assert(w(r as int));
        lemma_dml_xok(sem, u, s, x, r, Some(rows[0].1), true, w, R);
    }
}

pub proof fn lemma_upsert_run_xok(sem: Sem, u: U, s: State, x: usize, r: usize, v: Val, aw: bool,
    w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s), (x as int) < s.procs.len(), (r as int) < u.n(), u.is_row[r as int], w(r as int), w_out(w, R),
        s.procs[x as int].alive,
    ensures xok(sem, u, s, upsert_run(sem, u, s, x, r, v, aw).0, x, w, R),
{
    lemma_xok_refl(sem, u, s, x, w, R);
    lemma_failed_stmt_xok(sem, u, s, x, w, R);
    lemma_dml_xok(sem, u, s, x, r, Some(v), true, w, R);
    lemma_dml_xok(sem, u, s, x, r, Some(v), false, w, R);
}

// ------------------------------------------------------------------------------------------------ one operation

pub open spec fn ext_w(u: U, op: Op) -> spec_fn(int) -> bool { |c: int| wr(u, op, c) }

pub proof fn lemma_r_glob_rows(u: U, op: Op, R: spec_fn(int) -> bool)
    requires r_glob(u, R), is_ext_op(op), wf_op(u, op),
    ensures w_out(ext_w(u, op), R),
{
    assert forall|c: int| #[trigger] ext_w(u, op)(c) implies !R(c) by {
        if R(c) { assert(is_glob(u, c)); }
    }
}

/// Every extension operation: well formed, inside its footprint, user locks and level kept, committed state on R kept.
pub proof fn lemma_ext_step_xok(sem: Sem, u: U, s: State, p: usize, op: Op, choice: bool, w: spec_fn(int) -> bool,
    R: spec_fn(int) -> bool)
    requires wf(u, s),  wf_op(u, op), is_ext_op(op), (p as int) < s.procs.len(), s.procs[p as int].alive,
        forall|c: int| wr(u, op, c) ==> #[trigger] w(c), w_out(w, R),
    ensures xok(sem, u, s, ext_step(sem, u, s, p, op, choice).0, p, w, R),
{
    lemma_xok_refl(sem, u, s, p, w, R);
    lemma_select_txn_xok(sem, u, s, p, w, R);
    let kind = s.procs[p as int].kind;
    match op {
        Op::PutE { r, v, literal } => {
            assert(wr(u, op, r as int));
            lemma_dml_xok(sem, u, s, p, r, Some(stored(sem, kind, v, literal)), true, w, R);
        },
        Op::InsertSelect { from, to } => {
            assert forall|c: int| 0 <= c < u.n() && u.is_row[c] && u.table[c] == to implies #[trigger] w(c) by {
                assert(wr(u, op, c));
            }
            lemma_insert_select_xok(sem, u, s, p, from, to, w, R);
        },
        Op::EmbRegister { r } => {
            assert(wr(u, op, r as int));
            lemma_emb_register_xok(sem, u, s, p, r, choice, w, R);
        },
        Op::EmbRetract { r } => {
            assert(wr(u, op, r as int));
            lemma_set_pending_xok(sem, u, s, p, Some(op), w, R);
            lemma_emb_dml_xok(sem, u, s, p, r, None, w, R);
        },
        Op::EmbAssert { rn, rr, empty, vt } => {
            assert(wr(u, op, rn as int) && wr(u, op, rr as int));
            lemma_emb_assert_xok(sem, u, s, p, rn, rr, empty, vt, w, R);
        },
        Op::Upsert { r, v } => {
            assert(wr(u, op, r as int));
            lemma_set_pending_xok(sem, u, s, p, Some(op), w, R);
            lemma_upsert_run_xok(sem, u, s, p, r, v, false, w, R);
        },
        Op::InsertMany { t, b } => {
            assert forall|c: int| 0 <= c < u.n() && u.is_row[c] && u.table[c] == t implies #[trigger] w(c) by {
                assert(wr(u, op, c));
            }
            lemma_insert_many_xok(sem, u, s, p, t, u.batches[b as int], w, R);
        },
        _ => {},
    }
}

/// An `Await` completing a pending embedded statement.
pub proof fn lemma_await_emb_xok(sem: Sem, u: U, s1: State, p: usize, pend: Op, w: spec_fn(int) -> bool, R: spec_fn(int) -> bool)
    requires wf(u, s1),  wf_op(u, pend), (pend is EmbRegister || pend is EmbRetract || pend is Upsert), (p as int) < s1.procs.len(),
        s1.procs[p as int].alive, forall|c: int| wr(u, pend, c) ==> #[trigger] w(c), w_out(w, R),
    ensures pend matches Op::EmbRegister { r } ==> xok(sem, u, s1, emb_dml(sem, u, s1, p, r, Some(Val::Empty)).0, p, w, R),
        pend matches Op::EmbRetract { r } ==> xok(sem, u, s1, emb_dml(sem, u, s1, p, r, None).0, p, w, R),
        pend matches Op::Upsert { r, v } ==> xok(sem, u, s1, upsert_run(sem, u, s1, p, r, v, true).0, p, w, R),
{
    match pend {
        Op::Upsert { r, v } => { assert(wr(u, pend, r as int)); lemma_upsert_run_xok(sem, u, s1, p, r, v, true, w, R); },
        Op::EmbRegister { r } => { assert(wr(u, pend, r as int)); lemma_emb_dml_xok(sem, u, s1, p, r, Some(Val::Empty), w, R); },
        Op::EmbRetract { r } => { assert(wr(u, pend, r as int)); lemma_emb_dml_xok(sem, u, s1, p, r, None, w, R); },
        _ => {},
    }
}

} // verus!
