//! Footprints of the contract's operations, proved once: what one operation of process x may change.
//! `eff`: every other process is unchanged; a global or row changes only if the operation writes it or x's undo log
//! held an entry for it (a rollback); x's log grows only by entries for cells the operation writes.
//! `locks_eff`: x gains a hold only where no other live process holds a conflicting one; `rlocks_eff` likewise for
//! row locks. These are the facts every premise theorem (headlock.rs, premises.rs) reasons from.
use vstd::prelude::*;
use crate::spec::*;
use crate::wf::*;

verus! {

// ------------------------------------------------------------------------------------------------ vocabulary

/// The log has a (non-ppg) entry for cell c.
pub open spec fn log_has(es: Seq<Undo>, c: int) -> bool {
    exists|i: int| 0 <= i < es.len() && !(#[trigger] es[i]).ppg && es[i].c as int == c
}

/// Every non-ppg entry of b is a's entry at the same index or an entry for a cell w selects.
pub open spec fn log_grows_by(a: Seq<Undo>, b: Seq<Undo>, w: spec_fn(int) -> bool) -> bool {
    forall|i: int| 0 <= i < b.len() ==> (#[trigger] b[i]).ppg || (i < a.len() && b[i] == a[i]) || w(b[i].c as int)
}

pub open spec fn clean_proc(pr: Proc) -> bool {
    &&& (level(pr) == 0 ==> pr.undo.len() == 0)
    &&& (level(pr) > 0 ==> pr.marks[0] == 0)
    &&& (!pr.alive ==> level(pr) == 0 && pr.pending is None
            && (forall|m: int| 0 <= m < pr.locks.len() ==> !any(#[trigger] pr.locks[m]))
            && (forall|r: int| 0 <= r < pr.rlocks.len() ==> !(#[trigger] pr.rlocks[r])))
}

/// x's operation from s to s2 changes only what w and x's own log allow.
pub open spec fn eff(s: State, s2: State, x: usize, w: spec_fn(int) -> bool) -> bool {
    &&& s2.procs.len() == s.procs.len()
    &&& s2.g.len() == s.g.len()
    &&& forall|q: int| 0 <= q < s.procs.len() && q != x ==> #[trigger] s2.procs[q] == s.procs[q]
    &&& forall|c: int| 0 <= c < s.g.len() ==> #[trigger] s2.g[c] == s.g[c] || w(c) || log_has(s.procs[x as int].undo, c)
    &&& log_grows_by(s.procs[x as int].undo, s2.procs[x as int].undo, w)
    &&& (s2.procs[x as int].alive ==> s.procs[x as int].alive)
}

/// x stays clean (needed only where a stop must end every level).
pub open spec fn clean_eff(sem: Sem, s: State, s2: State, x: usize) -> bool {
    stop_clean(sem) && clean_proc(s.procs[x as int]) ==> clean_proc(s2.procs[x as int])
}

pub open spec fn no_other_any(sem: Sem, u: U, s: State, x: usize, m: int) -> bool {
    forall|q: int, m2: int| 0 <= q < s.procs.len() && q != x && s.procs[q].alive && 0 <= m2 < u.n()
        && related(sem, u, m2, m) ==> !any(#[trigger] s.procs[q].locks[m2])
}

pub open spec fn no_other_excl(sem: Sem, u: U, s: State, x: usize, m: int) -> bool {
    forall|q: int, m2: int| 0 <= q < s.procs.len() && q != x && s.procs[q].alive && 0 <= m2 < u.n()
        && related(sem, u, m2, m) ==> !excl(#[trigger] s.procs[q].locks[m2])
}

/// x gains an exclusive hold only where nobody else holds anything related, a hold only where nobody else holds an
/// exclusive one.
pub open spec fn locks_eff(sem: Sem, u: U, s: State, s2: State, x: usize) -> bool {
    forall|m: int| 0 <= m < u.n() ==> {
        &&& (excl(#[trigger] s2.procs[x as int].locks[m]) ==> excl(s.procs[x as int].locks[m]) || no_other_any(sem, u, s, x, m))
        &&& (any(s2.procs[x as int].locks[m]) ==> any(s.procs[x as int].locks[m]) || no_other_excl(sem, u, s, x, m))
    }
}

pub open spec fn rlocks_eff(s: State, s2: State, x: usize) -> bool {
    forall|r: int| 0 <= r < s.g.len() ==> (#[trigger] s2.procs[x as int].rlocks[r] ==> s.procs[x as int].rlocks[r] || !row_held(s, x, r as usize))
}

pub open spec fn full_eff(sem: Sem, u: U, s: State, s2: State, x: usize, w: spec_fn(int) -> bool) -> bool {
    &&& eff(s, s2, x, w)
    &&& clean_eff(sem, s, s2, x)
    &&& locks_eff(sem, u, s, s2, x)
    &&& (sem.dml_waits ==> rlocks_eff(s, s2, x))
}

/// The cells an operation writes (Await: its pending operation's).
pub open spec fn wr(u: U, op: Op, c: int) -> bool {
    match op {
        Op::Set { c: c2, .. } | Op::Incr { c: c2 } => c == c2 as int,
        Op::Kill { c: c2 } => covers(u, c2 as int, c),
        Op::Insert { r, .. } | Op::Update { r, .. } | Op::Delete { r } => c == r as int,
        _ => false,
    }
}

pub open spec fn wr_of(u: U, s: State, x: usize, op: Op) -> spec_fn(int) -> bool {
    |c: int| wr(u, op, c) || (op is Await && s.procs[x as int].pending is Some && wr(u, s.procs[x as int].pending->Some_0, c))
}

// ------------------------------------------------------------------------------------------------ rb (rollback) laws

pub proof fn lemma_rb_untouched(sem: Sem, g: Seq<Option<Val>>, pp: Seq<Option<Val>>, es: Seq<Undo>, c: int)
    requires !log_has(es, c), forall|i: int| 0 <= i < es.len() ==> (es[i].c as int) < g.len(), 0 <= c < g.len(),
    ensures rb(sem, g, pp, es).0[c] == g[c], rb(sem, g, pp, es).0.len() == g.len(),
    decreases es.len(),
{
    if es.len() > 0 {
        let e = es.last();
        let r = restore1(sem, g, pp, e);
        assert(!log_has(es.drop_last(), c)) by {
            if log_has(es.drop_last(), c) {
                let i = choose|i: int| 0 <= i < es.drop_last().len() && !(#[trigger] es.drop_last()[i]).ppg && es.drop_last()[i].c as int == c;
                assert(es[i] == es.drop_last()[i]);
            }
        }
        assert(!(!e.ppg && e.c as int == c)) by { if !e.ppg && e.c as int == c { assert(es[es.len() - 1] == e); } }
        lemma_rb_untouched(sem, r.0, r.1, es.drop_last(), c);
    }
}

pub proof fn lemma_rb_len(sem: Sem, g: Seq<Option<Val>>, pp: Seq<Option<Val>>, es: Seq<Undo>)
    requires forall|i: int| 0 <= i < es.len() ==> (es[i].c as int) < g.len(),
    ensures rb(sem, g, pp, es).0.len() == g.len(),
    decreases es.len(),
{
    if es.len() > 0 {
        let r = restore1(sem, g, pp, es.last());
        lemma_rb_len(sem, r.0, r.1, es.drop_last());
    }
}

/// The globals a rollback leaves at c depend on c's value only (and not on the ppg).
pub proof fn lemma_rb_pointwise(sem: Sem, g1: Seq<Option<Val>>, g2: Seq<Option<Val>>, pp1: Seq<Option<Val>>,
    pp2: Seq<Option<Val>>, es: Seq<Undo>, c: int)
    requires g1.len() == g2.len(), 0 <= c < g1.len(), g1[c] == g2[c],
        forall|i: int| 0 <= i < es.len() ==> (es[i].c as int) < g1.len(),
    ensures rb(sem, g1, pp1, es).0[c] == rb(sem, g2, pp2, es).0[c],
    decreases es.len(),
{
    if es.len() > 0 {
        let e = es.last();
        let r1 = restore1(sem, g1, pp1, e);
        let r2 = restore1(sem, g2, pp2, e);
        assert(r1.0.len() == g1.len() && r2.0.len() == g2.len());
        assert(r1.0[c] == r2.0[c]);
        lemma_rb_pointwise(sem, r1.0, r2.0, r1.1, r2.1, es.drop_last(), c);
    }
}

/// A logged write then its rollback is no write at all (any rollback reading).
pub proof fn lemma_rb_push_write(sem: Sem, g: Seq<Option<Val>>, pp: Seq<Option<Val>>, es: Seq<Undo>, c: usize, v: Option<Val>)
    requires (c as int) < g.len(),
    ensures rb(sem, g.update(c as int, v), pp, es.push(Undo { c, old: g[c as int], written: v, ppg: false })) == rb(sem, g, pp, es),
{
    let es2 = es.push(Undo { c, old: g[c as int], written: v, ppg: false });
    assert(es2.drop_last() =~= es);
    assert(g.update(c as int, v).update(c as int, g[c as int]) =~= g);
}

/// A ppg entry does not affect the globals a rollback leaves.
pub proof fn lemma_rb_push_ppg(sem: Sem, g: Seq<Option<Val>>, pp: Seq<Option<Val>>, pp2: Seq<Option<Val>>, es: Seq<Undo>, e: Undo)
    requires e.ppg, forall|i: int| 0 <= i < es.len() ==> (es[i].c as int) < g.len(),
    ensures rb(sem, g, pp, es.push(e)).0 == rb(sem, g, pp2, es).0,
{
    let es2 = es.push(e);
    assert(es2.drop_last() =~= es);
    let r = restore1(sem, g, pp, e);
    assert(r.0 == g);
    lemma_rb_len(sem, g, r.1, es);
    lemma_rb_len(sem, g, pp2, es);
    assert forall|c: int| 0 <= c < g.len() implies rb(sem, g, r.1, es).0[c] == rb(sem, g, pp2, es).0[c] by {
        lemma_rb_pointwise(sem, g, g, r.1, pp2, es, c);
    }
    assert(rb(sem, g, r.1, es).0 =~= rb(sem, g, pp2, es).0);
}

/// Rolling back a + b is rolling back b, then a.
pub proof fn lemma_rb_split(sem: Sem, g: Seq<Option<Val>>, pp: Seq<Option<Val>>, a: Seq<Undo>, b: Seq<Undo>)
    ensures rb(sem, g, pp, a + b) == ({ let r = rb(sem, g, pp, b); rb(sem, r.0, r.1, a) }),
    decreases b.len(),
{
    if b.len() == 0 {
        assert(a + b =~= a);
    } else {
        let e = b.last();
        let r = restore1(sem, g, pp, e);
        assert((a + b).last() == e);
        assert((a + b).drop_last() =~= a + b.drop_last());
        lemma_rb_split(sem, r.0, r.1, a, b.drop_last());
    }
}

// ------------------------------------------------------------------------------------------------ effect algebra

pub proof fn lemma_eff_refl(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(),
    ensures full_eff(sem, u, s, s, x, w),
{
}

pub proof fn lemma_eff_trans(sem: Sem, u: U, s: State, s1: State, s2: State, x: usize, w: spec_fn(int) -> bool)
    requires full_eff(sem, u, s, s1, x, w), full_eff(sem, u, s1, s2, x, w), (x as int) < s.procs.len(),
        s.g.len() == u.n(),
    ensures full_eff(sem, u, s, s2, x, w),
{
    let a = s.procs[x as int].undo;
    let b = s1.procs[x as int].undo;
    let c2 = s2.procs[x as int].undo;
    assert forall|c: int| 0 <= c < s.g.len() implies #[trigger] s2.g[c] == s.g[c] || w(c) || log_has(a, c) by {
        if s2.g[c] != s.g[c] && !w(c) {
            if s2.g[c] != s1.g[c] {
                assert(log_has(b, c));
                let i = choose|i: int| 0 <= i < b.len() && !(#[trigger] b[i]).ppg && b[i].c as int == c;
                assert(i < a.len() && b[i] == a[i]);
            } else {
                assert(s1.g[c] != s.g[c]);
            }
        }
    }
    assert forall|i: int| 0 <= i < c2.len() implies (#[trigger] c2[i]).ppg || (i < a.len() && c2[i] == a[i]) || w(c2[i].c as int) by {
        if !c2[i].ppg && !w(c2[i].c as int) {
            assert(i < b.len() && c2[i] == b[i]);
        }
    }
    assert forall|m: int| 0 <= m < u.n() implies #[trigger] no_other_any(sem, u, s1, x, m) == no_other_any(sem, u, s, x, m)
        && no_other_excl(sem, u, s1, x, m) == no_other_excl(sem, u, s, x, m) by {
        lemma_others_same_locks(sem, u, s, s1, x, m);
    }
    assert forall|r: int| 0 <= r < s.g.len() implies #[trigger] row_held(s1, x, r as usize) == row_held(s, x, r as usize) by {
        lemma_others_same_rows(s, s1, x, r as usize);
    }
}

pub proof fn lemma_others_same_locks(sem: Sem, u: U, s: State, s1: State, x: usize, m: int)
    requires s1.procs.len() == s.procs.len(), forall|q: int| 0 <= q < s.procs.len() && q != x ==> #[trigger] s1.procs[q] == s.procs[q],
    ensures no_other_any(sem, u, s1, x, m) == no_other_any(sem, u, s, x, m),
        no_other_excl(sem, u, s1, x, m) == no_other_excl(sem, u, s, x, m),
{
    if no_other_any(sem, u, s1, x, m) {
        assert forall|q: int, m2: int| 0 <= q < s.procs.len() && q != x && s.procs[q].alive && 0 <= m2 < u.n()
            && related(sem, u, m2, m) implies !any(#[trigger] s.procs[q].locks[m2]) by { assert(s1.procs[q] == s.procs[q]); }
    }
    if no_other_any(sem, u, s, x, m) {
        assert forall|q: int, m2: int| 0 <= q < s1.procs.len() && q != x && s1.procs[q].alive && 0 <= m2 < u.n()
            && related(sem, u, m2, m) implies !any(#[trigger] s1.procs[q].locks[m2]) by { assert(s1.procs[q] == s.procs[q]); }
    }
    if no_other_excl(sem, u, s1, x, m) {
        assert forall|q: int, m2: int| 0 <= q < s.procs.len() && q != x && s.procs[q].alive && 0 <= m2 < u.n()
            && related(sem, u, m2, m) implies !excl(#[trigger] s.procs[q].locks[m2]) by { assert(s1.procs[q] == s.procs[q]); }
    }
    if no_other_excl(sem, u, s, x, m) {
        assert forall|q: int, m2: int| 0 <= q < s1.procs.len() && q != x && s1.procs[q].alive && 0 <= m2 < u.n()
            && related(sem, u, m2, m) implies !excl(#[trigger] s1.procs[q].locks[m2]) by { assert(s1.procs[q] == s.procs[q]); }
    }
}

pub proof fn lemma_others_same_rows(s: State, s1: State, x: usize, r: usize)
    requires s1.procs.len() == s.procs.len(), forall|q: int| 0 <= q < s.procs.len() && q != x ==> #[trigger] s1.procs[q] == s.procs[q],
    ensures row_held(s1, x, r) == row_held(s, x, r),
{
    if row_held(s1, x, r) {
        let q = choose|q: int| 0 <= q < s1.procs.len() && q != x && s1.procs[q].alive && #[trigger] s1.procs[q].rlocks[r as int];
        assert(s1.procs[q] == s.procs[q]);
    }
    if row_held(s, x, r) {
        let q = choose|q: int| 0 <= q < s.procs.len() && q != x && s.procs[q].alive && #[trigger] s.procs[q].rlocks[r as int];
        assert(s1.procs[q] == s.procs[q]);
    }
}

// ------------------------------------------------------------------------------------------------ helpers' effects

pub proof fn lemma_upd_eff(sem: Sem, u: U, s: State, x: usize, pr: Proc, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), pr.locks == s.procs[x as int].locks, pr.rlocks == s.procs[x as int].rlocks,
        pr.alive == s.procs[x as int].alive, pr.undo == s.procs[x as int].undo, pr.marks == s.procs[x as int].marks,
        pr.alive || pr.pending is None,
    ensures full_eff(sem, u, s, upd(s, x, pr), x, w),
{
}

pub proof fn lemma_write_eff(sem: Sem, u: U, s: State, x: usize, c: usize, v: Option<Val>, logged: bool, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), (c as int) < u.n(), w(c as int),
    ensures full_eff(sem, u, s, write(s, x, c, v, logged), x, w),
{
    let s2 = write(s, x, c, v, logged);
    let a = s.procs[x as int].undo;
    let b = s2.procs[x as int].undo;
    assert forall|i: int| 0 <= i < b.len() implies (#[trigger] b[i]).ppg || (i < a.len() && b[i] == a[i]) || w(b[i].c as int) by {
        if i >= a.len() { assert(b[i].c == c); }
    }
}

pub proof fn lemma_kill_eff(sem: Sem, u: U, s: State, x: usize, node: usize, j: nat, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), forall|c: int| covers(u, node as int, c) ==> w(c),
    ensures full_eff(sem, u, s, kill_from(sem, u, s, x, node, j), x, w),
    decreases u.n() - j,
{
    if j >= u.n() {
        lemma_eff_refl(sem, u, s, x, w);
    } else {
        let s1 = if covers(u, node as int, j as int) && s.g[j as int] is Some { write(s, x, j as usize, None, sem.kill_logged) } else { s };
        if covers(u, node as int, j as int) && s.g[j as int] is Some {
            lemma_write_eff(sem, u, s, x, j as usize, None, sem.kill_logged, w);
            lemma_write_wf(u, s, x, j as usize, None, sem.kill_logged);
        } else {
            lemma_eff_refl(sem, u, s, x, w);
        }
        lemma_kill_eff(sem, u, s1, x, node, j + 1, w);
        lemma_eff_trans(sem, u, s, s1, kill_from(sem, u, s, x, node, j), x, w);
    }
}

pub proof fn lemma_tstart_eff(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), s.procs[x as int].alive,
    ensures full_eff(sem, u, s, tstart(s, x), x, w), level(tstart(s, x).procs[x as int]) > 0,
        tstart(s, x).procs[x as int].undo == s.procs[x as int].undo,
{
    let pr = s.procs[x as int];
    let s2 = tstart(s, x);
    assert(clean_proc(pr) ==> clean_proc(s2.procs[x as int]));
}

pub proof fn lemma_txn_end_eff(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures full_eff(sem, u, s, txn_end(s, x), x, w), txn_end(s, x).procs[x as int].undo.len() == 0,
        level(txn_end(s, x).procs[x as int]) == 0, txn_end(s, x).g == s.g,
{
    let pr = s.procs[x as int];
    let s2 = txn_end(s, x);
    assert(wf_proc(u, pr));
    assert forall|m: int| 0 <= m < u.n() implies {
        &&& (excl(#[trigger] s2.procs[x as int].locks[m]) ==> excl(s.procs[x as int].locks[m]) || no_other_any(sem, u, s, x, m))
        &&& (any(s2.procs[x as int].locks[m]) ==> any(s.procs[x as int].locks[m]) || no_other_excl(sem, u, s, x, m))
    } by {
        assert(s2.procs[x as int].locks[m] == Hold { de: 0, ds: 0, ..pr.locks[m] });
    }
    assert(clean_proc(pr) ==> clean_proc(s2.procs[x as int])) by {
        if clean_proc(pr) && !s2.procs[x as int].alive {
            assert forall|m: int| 0 <= m < s2.procs[x as int].locks.len() implies !any(#[trigger] s2.procs[x as int].locks[m]) by {
                assert(s2.procs[x as int].locks[m] == Hold { de: 0, ds: 0, ..pr.locks[m] });
            }
        }
    }
}

pub proof fn lemma_undo_top_eff(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), level(s.procs[x as int]) > 0,
    ensures full_eff(sem, u, s, undo_top(sem, s, x), x, w),
{
    let pr = s.procs[x as int];
    assert(wf_proc(u, pr));
    let m = top_mark(pr);
    let es = pr.undo.subrange(m as int, pr.undo.len() as int);
    let r = rb(sem, s.g, pr.ppg, es);
    let pr2 = Proc { undo: pr.undo.subrange(0, m as int), marks: pr.marks.drop_last(), ppg: r.1, ..pr };
    let s2 = State { g: r.0, procs: s.procs.update(x as int, pr2) };
    let fin = undo_top(sem, s, x);
    assert forall|i: int| 0 <= i < es.len() implies (es[i].c as int) < s.g.len() by { assert(es[i] == pr.undo[m + i]); }
    lemma_rb_len(sem, s.g, pr.ppg, es);
    assert forall|c: int| 0 <= c < s.g.len() implies #[trigger] s2.g[c] == s.g[c] || w(c) || log_has(pr.undo, c) by {
        if !log_has(pr.undo, c) {
            assert(!log_has(es, c)) by {
                if log_has(es, c) {
                    let i = choose|i: int| 0 <= i < es.len() && !(#[trigger] es[i]).ppg && es[i].c as int == c;
                    assert(es[i] == pr.undo[m + i]);
                }
            }
            lemma_rb_untouched(sem, s.g, pr.ppg, es, c);
        }
    }
    if pr2.marks.len() > 0 {
        assert(fin == s2);
        assert(full_eff(sem, u, s, s2, x, w));
    } else {
        let tp = Proc {
            sqlflag: false,
            undo: Seq::empty(),
            marks: Seq::empty(),
            locks: Seq::new(pr2.locks.len(), |i: int| Hold { de: 0, ds: 0, ..pr2.locks[i] }),
            rlocks: Seq::new(pr2.rlocks.len(), |i: int| false),
            ..pr2
        };
        assert(fin == upd(s2, x, tp));
        assert(fin.g == s2.g);
        assert forall|m2: int| 0 <= m2 < u.n() implies {
            &&& (excl(#[trigger] fin.procs[x as int].locks[m2]) ==> excl(s.procs[x as int].locks[m2]) || no_other_any(sem, u, s, x, m2))
            &&& (any(fin.procs[x as int].locks[m2]) ==> any(s.procs[x as int].locks[m2]) || no_other_excl(sem, u, s, x, m2))
        } by {
            assert(fin.procs[x as int].locks[m2] == Hold { de: 0, ds: 0, ..pr.locks[m2] });
        }
        assert(clean_proc(pr) ==> clean_proc(fin.procs[x as int])) by {
            if clean_proc(pr) && !fin.procs[x as int].alive {
                assert forall|m2: int| 0 <= m2 < fin.procs[x as int].locks.len() implies !any(#[trigger] fin.procs[x as int].locks[m2]) by {
                    assert(fin.procs[x as int].locks[m2] == Hold { de: 0, ds: 0, ..pr.locks[m2] });
                }
            }
        }
        assert(full_eff(sem, u, s, fin, x, w));
    }
}

pub proof fn lemma_commit_top_eff(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures full_eff(sem, u, s, commit_top(s, x), x, w), commit_top(s, x).g == s.g,
{
    let pr = s.procs[x as int];
    if pr.marks.len() > 1 {
        let s2 = upd(s, x, Proc { marks: pr.marks.drop_last(), ..pr });
        assert(clean_proc(pr) ==> clean_proc(s2.procs[x as int]));
        assert(full_eff(sem, u, s, s2, x, w));
    } else if pr.marks.len() == 1 {
        let s2 = upd(s, x, Proc { marks: pr.marks.drop_last(), ..pr });
        let fin = txn_end(s2, x);
        assert(fin == commit_top(s, x));
        assert(fin.procs[x as int].undo.len() == 0 && level(fin.procs[x as int]) == 0);
        assert(forall|q: int| 0 <= q < s.procs.len() && q != x ==> #[trigger] fin.procs[q] == s.procs[q]);
        assert forall|m2: int| 0 <= m2 < u.n() implies {
            &&& (excl(#[trigger] fin.procs[x as int].locks[m2]) ==> excl(s.procs[x as int].locks[m2]) || no_other_any(sem, u, s, x, m2))
            &&& (any(fin.procs[x as int].locks[m2]) ==> any(s.procs[x as int].locks[m2]) || no_other_excl(sem, u, s, x, m2))
        } by {
            assert(wf_proc(u, pr));
            assert(fin.procs[x as int].locks[m2] == Hold { de: 0, ds: 0, ..pr.locks[m2] });
        }
        assert(clean_proc(pr) ==> clean_proc(fin.procs[x as int])) by {
            if clean_proc(pr) && !fin.procs[x as int].alive {
                assert forall|m2: int| 0 <= m2 < fin.procs[x as int].locks.len() implies !any(#[trigger] fin.procs[x as int].locks[m2]) by {
                    assert(fin.procs[x as int].locks[m2] == Hold { de: 0, ds: 0, ..pr.locks[m2] });
                }
            }
        }
        assert(full_eff(sem, u, s, fin, x, w));
    } else {
        lemma_eff_refl(sem, u, s, x, w);
    }
}

pub proof fn lemma_rollback_n_eff(sem: Sem, u: U, s: State, x: usize, n: nat, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures full_eff(sem, u, s, rollback_n(sem, s, x, n), x, w),
    decreases n,
{
    if n == 0 || level(s.procs[x as int]) == 0 {
        lemma_eff_refl(sem, u, s, x, w);
    } else {
        let s1 = undo_top(sem, s, x);
        lemma_undo_top_eff(sem, u, s, x, w);
        lemma_undo_top_wf(sem, u, s, x);
        lemma_rollback_n_eff(sem, u, s1, x, (n - 1) as nat, w);
        lemma_eff_trans(sem, u, s, s1, rollback_n(sem, s, x, n), x, w);
    }
}

pub proof fn lemma_commit_n_eff(sem: Sem, u: U, s: State, x: usize, n: nat, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures full_eff(sem, u, s, commit_n(s, x, n), x, w), commit_n(s, x, n).g == s.g,
    decreases n,
{
    if n == 0 || level(s.procs[x as int]) == 0 {
        lemma_eff_refl(sem, u, s, x, w);
    } else {
        let s1 = commit_top(s, x);
        lemma_commit_top_eff(sem, u, s, x, w);
        lemma_commit_top_wf(u, s, x);
        lemma_commit_n_eff(sem, u, s1, x, (n - 1) as nat, w);
        lemma_eff_trans(sem, u, s, s1, commit_n(s, x, n), x, w);
    }
}

pub proof fn lemma_set_sqlflag_eff(sem: Sem, u: U, s: State, x: usize, b: bool, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures full_eff(sem, u, s, set_sqlflag(s, x, b), x, w),
{
    assert(clean_proc(s.procs[x as int]) ==> clean_proc(set_sqlflag(s, x, b).procs[x as int]));
}

pub proof fn lemma_set_pending_eff(sem: Sem, u: U, s: State, x: usize, op: Option<Op>, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), s.procs[x as int].alive || op is None,
    ensures full_eff(sem, u, s, set_pending(s, x, op), x, w),
{
    assert(clean_proc(s.procs[x as int]) ==> clean_proc(set_pending(s, x, op).procs[x as int]));
}

pub proof fn lemma_end_levels_eff(sem: Sem, u: U, s: State, x: usize, ends: Ends, commit: bool, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures full_eff(sem, u, s, end_levels(s, sem, x, ends, commit), x, w),
{
    let l = level(s.procs[x as int]);
    let n: nat = match ends { Ends::One => 1, Ends::All => l };
    let s2 = if l == 0 { s } else if commit { commit_n(s, x, n) } else { rollback_n(sem, s, x, n) };
    if l == 0 { lemma_eff_refl(sem, u, s, x, w); } else if commit {
        lemma_commit_n_eff(sem, u, s, x, n, w);
        lemma_commit_n_wf(u, s, x, n);
    } else {
        lemma_rollback_n_eff(sem, u, s, x, n, w);
        lemma_rollback_n_wf(sem, u, s, x, n);
    }
    if l == 0 {} else if commit { lemma_commit_n_wf(u, s, x, n); } else { lemma_rollback_n_wf(sem, u, s, x, n); }
    lemma_set_sqlflag_eff(sem, u, s2, x, false, w);
    lemma_eff_trans(sem, u, s, s2, end_levels(s, sem, x, ends, commit), x, w);
}

pub proof fn lemma_set_hold_reduce_eff(sem: Sem, u: U, s: State, x: usize, c: usize, h: Hold, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), (c as int) < u.n(),
        excl(h) ==> excl(s.procs[x as int].locks[c as int]), any(h) ==> any(s.procs[x as int].locks[c as int]),
    ensures full_eff(sem, u, s, set_hold(s, x, c, h), x, w),
{
    let s2 = set_hold(s, x, c, h);
    assert(wf_proc(u, s.procs[x as int]));
    assert(clean_proc(s.procs[x as int]) ==> clean_proc(s2.procs[x as int])) by {
        if clean_proc(s.procs[x as int]) && !s2.procs[x as int].alive {
            assert forall|m: int| 0 <= m < s2.procs[x as int].locks.len() implies !any(#[trigger] s2.procs[x as int].locks[m]) by {
                if m != c as int { assert(s2.procs[x as int].locks[m] == s.procs[x as int].locks[m]); }
            }
        }
    }
    assert forall|m: int| 0 <= m < u.n() implies {
        &&& (excl(#[trigger] s2.procs[x as int].locks[m]) ==> excl(s.procs[x as int].locks[m]) || no_other_any(sem, u, s, x, m))
        &&& (any(s2.procs[x as int].locks[m]) ==> any(s.procs[x as int].locks[m]) || no_other_excl(sem, u, s, x, m))
    } by {
        if m != c as int { assert(s2.procs[x as int].locks[m] == s.procs[x as int].locks[m]); }
    }
}

pub proof fn lemma_acquire_eff(sem: Sem, u: U, s: State, x: usize, c: usize, mode: Mode, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), (c as int) < u.n(), !conflicts(sem, u, s, x, c, mode), s.procs[x as int].alive,
    ensures acquire(sem, s, x, c, mode) matches Some(s2) ==> full_eff(sem, u, s, s2, x, w),
{
    let h = s.procs[x as int].locks[c as int];
    assert(wf_proc(u, s.procs[x as int]));
    match mode {
        Mode::E => {
            assert(no_other_any(sem, u, s, x, c as int)) by {
                assert forall|q: int, m2: int| 0 <= q < s.procs.len() && q != x && s.procs[q].alive && 0 <= m2 < u.n()
                    && related(sem, u, m2, c as int) implies !any(#[trigger] s.procs[q].locks[m2]) by {
                    if any(s.procs[q].locks[m2]) { assert(hold_conflicts(sem, s.procs[q].locks[m2], Mode::E)); }
                }
            }
        },
        Mode::S => {
            assert(no_other_excl(sem, u, s, x, c as int)) by {
                assert forall|q: int, m2: int| 0 <= q < s.procs.len() && q != x && s.procs[q].alive && 0 <= m2 < u.n()
                    && related(sem, u, m2, c as int) implies !excl(#[trigger] s.procs[q].locks[m2]) by {
                    if excl(s.procs[q].locks[m2]) { assert(hold_conflicts(sem, s.procs[q].locks[m2], Mode::S)); }
                }
            }
        },
    }
    if let Some(s2) = acquire(sem, s, x, c, mode) {
        assert(forall|q: int| 0 <= q < s.procs.len() && q != x ==> #[trigger] s2.procs[q] == s.procs[q]);
        assert forall|m: int| 0 <= m < u.n() implies {
            &&& (excl(#[trigger] s2.procs[x as int].locks[m]) ==> excl(s.procs[x as int].locks[m]) || no_other_any(sem, u, s, x, m))
            &&& (any(s2.procs[x as int].locks[m]) ==> any(s.procs[x as int].locks[m]) || no_other_excl(sem, u, s, x, m))
        } by {
            if m != c as int { assert(s2.procs[x as int].locks[m] == s.procs[x as int].locks[m]); }
            else if mode == Mode::E {
                assert(no_other_any(sem, u, s, x, m));
                if !no_other_excl(sem, u, s, x, m) {
                    let (q, m2) = choose|q: int, m2: int| 0 <= q < s.procs.len() && q != x && s.procs[q].alive && 0 <= m2 < u.n()
                        && related(sem, u, m2, m) && excl(#[trigger] s.procs[q].locks[m2]);
                    assert(any(s.procs[q].locks[m2]));
                }
            }
        }
    }
}

pub proof fn lemma_release_eff(sem: Sem, u: U, s: State, x: usize, c: usize, mode: Mode, immediate: bool, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), (c as int) < u.n(),
    ensures release(sem, s, x, c, mode, immediate) matches Some(s2) ==> full_eff(sem, u, s, s2, x, w),
{
    let h = s.procs[x as int].locks[c as int];
    lemma_eff_refl(sem, u, s, x, w);
    if mode == Mode::E && h.e > 0 {
        lemma_set_hold_reduce_eff(sem, u, s, x, c, Hold { e: (h.e - 1) as u64, ..h }, w);
        if h.de < u64::MAX {
            lemma_set_hold_reduce_eff(sem, u, s, x, c, Hold { e: (h.e - 1) as u64, de: (h.de + 1) as u64, ..h }, w);
        }
    }
    if mode == Mode::S && h.s > 0 {
        lemma_set_hold_reduce_eff(sem, u, s, x, c, Hold { s: (h.s - 1) as u64, ..h }, w);
        if h.ds < u64::MAX {
            lemma_set_hold_reduce_eff(sem, u, s, x, c, Hold { s: (h.s - 1) as u64, ds: (h.ds + 1) as u64, ..h }, w);
        }
    }
}

pub proof fn lemma_release_all_eff(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures release_all(sem, s, x) matches Some(s2) ==> full_eff(sem, u, s, s2, x, w),
{
    let pr = s.procs[x as int];
    assert(wf_proc(u, pr));
    if let Some(s2) = release_all(sem, s, x) {
        if sem.unlock_deferred && level(pr) > 0 {
            assert forall|m: int| 0 <= m < u.n() implies {
                &&& (excl(#[trigger] s2.procs[x as int].locks[m]) ==> excl(s.procs[x as int].locks[m]) || no_other_any(sem, u, s, x, m))
                &&& (any(s2.procs[x as int].locks[m]) ==> any(s.procs[x as int].locks[m]) || no_other_excl(sem, u, s, x, m))
            } by {
                assert(!defer_overflows(pr.locks[m]));
                assert(s2.procs[x as int].locks[m] == defer_hold(pr.locks[m]));
            }
        } else {
            assert forall|m: int| 0 <= m < u.n() implies !any(#[trigger] s2.procs[x as int].locks[m]) by {
                assert(s2.procs[x as int].locks[m] == zero_hold());
            }
            assert(clean_proc(pr) ==> clean_proc(s2.procs[x as int])) by {
                if clean_proc(pr) && !s2.procs[x as int].alive {
                    assert forall|m: int| 0 <= m < s2.procs[x as int].locks.len() implies !any(#[trigger] s2.procs[x as int].locks[m]) by {
                        assert(s2.procs[x as int].locks[m] == zero_hold());
                    }
                }
            }
        }
    }
}

pub proof fn lemma_set_rlock_eff(sem: Sem, u: U, s: State, x: usize, r: usize, b: bool, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), (r as int) < u.n(), b && sem.dml_waits ==> !row_held(s, x, r), b ==> s.procs[x as int].alive,
    ensures full_eff(sem, u, s, set_rlock(s, x, r, b), x, w),
{
    let s2 = set_rlock(s, x, r, b);
    assert(wf_proc(u, s.procs[x as int]));
    assert(clean_proc(s.procs[x as int]) ==> clean_proc(s2.procs[x as int])) by {
        if clean_proc(s.procs[x as int]) && !s2.procs[x as int].alive {
            assert forall|r2: int| 0 <= r2 < s2.procs[x as int].rlocks.len() implies !(#[trigger] s2.procs[x as int].rlocks[r2]) by {
                if r2 != r as int { assert(s2.procs[x as int].rlocks[r2] == s.procs[x as int].rlocks[r2]); }
            }
        }
    }
    if sem.dml_waits {
        assert forall|r2: int| 0 <= r2 < s.g.len() implies (#[trigger] s2.procs[x as int].rlocks[r2] ==> s.procs[x as int].rlocks[r2] || !row_held(s, x, r2 as usize)) by {
            if r2 != r as int { assert(s2.procs[x as int].rlocks[r2] == s.procs[x as int].rlocks[r2]); }
        }
    }
}

pub proof fn lemma_stmt_begin_eff(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), s.procs[x as int].alive,
    ensures full_eff(sem, u, s, stmt_begin(s, x).0, x, w), stmt_begin(s, x).0.g == s.g,
        stmt_begin(s, x).1 ==> level(stmt_begin(s, x).0.procs[x as int]) == 1,
        stmt_begin(s, x).0.procs[x as int].alive,
        level(stmt_begin(s, x).0.procs[x as int]) > 0,
        stmt_begin(s, x).0.procs[x as int].undo == s.procs[x as int].undo,
{
    lemma_tstart_eff(sem, u, s, x, w);
    lemma_tstart_wf(u, s, x);
    lemma_set_sqlflag_eff(sem, u, tstart(s, x), x, true, w);
    lemma_eff_trans(sem, u, s, tstart(s, x), set_sqlflag(tstart(s, x), x, true), x, w);
}

pub proof fn lemma_failed_stmt_eff(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), s.procs[x as int].alive,
    ensures full_eff(sem, u, s, failed_stmt(sem, s, x), x, w), failed_stmt(sem, s, x).g == s.g,
{
    lemma_tstart_eff(sem, u, s, x, w);
    lemma_tstart_wf(u, s, x);
    lemma_set_sqlflag_eff(sem, u, tstart(s, x), x, true, w);
    lemma_eff_trans(sem, u, s, tstart(s, x), set_sqlflag(tstart(s, x), x, true), x, w);
    lemma_eff_refl(sem, u, s, x, w);
}

/// One DML statement's effect (the row lock is taken only where nobody else holds it, when `free`).
pub proof fn lemma_dml_eff(sem: Sem, u: U, s: State, x: usize, r: usize, nv: Option<Val>, insert: bool, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), (r as int) < u.n(), w(r as int), s.procs[x as int].alive,
        sem.dml_waits ==> (!row_held(s, x, r) || (insert && s.g[r as int] is Some) || (!insert && s.g[r as int] is None)),
    ensures
        insert && nv is Some ==> full_eff(sem, u, s, dml_insert(sem, u, s, x, r, nv->Some_0).0, x, w),
        !insert ==> full_eff(sem, u, s, dml_change(sem, u, s, x, r, nv).0, x, w),
{
    lemma_failed_stmt_eff(sem, u, s, x, w);
    lemma_eff_refl(sem, u, s, x, w);
    if (insert && s.g[r as int] is None) || (!insert && s.g[r as int] is Some) {
        let b = stmt_begin(s, x);
        lemma_stmt_begin_eff(sem, u, s, x, w);
        lemma_stmt_begin_wf(u, s, x);
        let s2 = write(b.0, x, r, nv, true);
        lemma_write_eff(sem, u, b.0, x, r, nv, true, w);
        lemma_write_wf(u, b.0, x, r, nv, true);
        lemma_eff_trans(sem, u, s, b.0, s2, x, w);
        assert(s2.procs[x as int].alive);
        if b.1 {
            assert(level(s2.procs[x as int]) == 1);
            lemma_commit_top_eff(sem, u, s2, x, w);
            lemma_eff_trans(sem, u, s, s2, commit_top(s2, x), x, w);
        } else {
            assert(row_held(s2, x, r) == row_held(s, x, r)) by {
                lemma_others_same_rows(s, s2, x, r);
            }
            lemma_set_rlock_eff(sem, u, s2, x, r, true, w);
            lemma_eff_trans(sem, u, s, s2, set_rlock(s2, x, r, true), x, w);
        }
    }
}

pub proof fn lemma_undo_top_level(sem: Sem, u: U, s: State, x: usize)
    requires (x as int) < s.procs.len(), wf(u, s), level(s.procs[x as int]) > 0,
    ensures level(undo_top(sem, s, x).procs[x as int]) == level(s.procs[x as int]) - 1,
        level(undo_top(sem, s, x).procs[x as int]) == 0 ==> undo_top(sem, s, x).procs[x as int].undo.len() == 0,
        undo_top(sem, s, x).procs[x as int].alive == s.procs[x as int].alive,
{
}

pub proof fn lemma_commit_top_level(u: U, s: State, x: usize)
    requires (x as int) < s.procs.len(), wf(u, s), level(s.procs[x as int]) > 0,
    ensures level(commit_top(s, x).procs[x as int]) == level(s.procs[x as int]) - 1,
        level(commit_top(s, x).procs[x as int]) == 0 ==> commit_top(s, x).procs[x as int].undo.len() == 0,
        commit_top(s, x).procs[x as int].alive == s.procs[x as int].alive,
        level(commit_top(s, x).procs[x as int]) > 0 ==> commit_top(s, x).procs[x as int].undo == s.procs[x as int].undo,
{
}

pub proof fn lemma_rollback_n_level(sem: Sem, u: U, s: State, x: usize, n: nat)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures n >= level(s.procs[x as int]) ==> level(rollback_n(sem, s, x, n).procs[x as int]) == 0,
        n < level(s.procs[x as int]) ==> level(rollback_n(sem, s, x, n).procs[x as int]) == level(s.procs[x as int]) - n,
        level(rollback_n(sem, s, x, n).procs[x as int]) == 0 && level(s.procs[x as int]) > 0 ==> rollback_n(sem, s, x, n).procs[x as int].undo.len() == 0,
        rollback_n(sem, s, x, n).procs[x as int].alive == s.procs[x as int].alive,
    decreases n,
{
    if !(n == 0 || level(s.procs[x as int]) == 0) {
        lemma_undo_top_level(sem, u, s, x);
        lemma_undo_top_wf(sem, u, s, x);
        lemma_rollback_n_level(sem, u, undo_top(sem, s, x), x, (n - 1) as nat);
    }
}

pub proof fn lemma_commit_n_level(u: U, s: State, x: usize, n: nat)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures n >= level(s.procs[x as int]) ==> level(commit_n(s, x, n).procs[x as int]) == 0,
        n < level(s.procs[x as int]) ==> level(commit_n(s, x, n).procs[x as int]) == level(s.procs[x as int]) - n,
        n < level(s.procs[x as int]) ==> commit_n(s, x, n).procs[x as int].undo == s.procs[x as int].undo,
        level(commit_n(s, x, n).procs[x as int]) == 0 && level(s.procs[x as int]) > 0 ==> commit_n(s, x, n).procs[x as int].undo.len() == 0,
        commit_n(s, x, n).procs[x as int].alive == s.procs[x as int].alive,
    decreases n,
{
    if !(n == 0 || level(s.procs[x as int]) == 0) {
        lemma_commit_top_level(u, s, x);
        lemma_commit_top_wf(u, s, x);
        lemma_commit_n_level(u, commit_top(s, x), x, (n - 1) as nat);
    }
}

/// The readings under which a stopped process is left clean (every level ended).
pub open spec fn stop_clean(sem: Sem) -> bool {
    sem.stop_rolls_back ==> sem.stop_all_levels
}

pub proof fn lemma_stop_eff(sem: Sem, u: U, s: State, t: usize, w: spec_fn(int) -> bool)
    requires (t as int) < s.procs.len(), wf(u, s),
    ensures full_eff(sem, u, s, stop(sem, s, t), t, w), !stop(sem, s, t).procs[t as int].alive,
        stop_clean(sem) && clean_proc(s.procs[t as int]) ==> clean_proc(stop(sem, s, t).procs[t as int]),
{
    let l = level(s.procs[t as int]);
    let s1 = if !sem.stop_rolls_back { commit_all(s, t) } else if sem.stop_all_levels { rollback_all(sem, s, t) } else { rollback_n(sem, s, t, 1) };
    if !sem.stop_rolls_back {
        lemma_commit_n_eff(sem, u, s, t, l, w);
        lemma_commit_n_wf(u, s, t, l);
        lemma_commit_n_level(u, s, t, l);
    } else if sem.stop_all_levels {
        lemma_rollback_n_eff(sem, u, s, t, l, w);
        lemma_rollback_n_wf(sem, u, s, t, l);
        lemma_rollback_n_level(sem, u, s, t, l);
    } else {
        lemma_rollback_n_eff(sem, u, s, t, 1, w);
        lemma_rollback_n_wf(sem, u, s, t, 1);
        lemma_rollback_n_level(sem, u, s, t, 1);
    }
    let pr = s1.procs[t as int];
    assert(wf_proc(u, pr));
    let pr2 = Proc {
        locks: Seq::new(pr.locks.len(), |i: int| zero_hold()),
        rlocks: Seq::new(pr.rlocks.len(), |i: int| false),
        ppg: Seq::new(pr.ppg.len(), |i: int| None),
        pending: None,
        alive: false,
        ..pr
    };
    let s2 = upd(s1, t, pr2);
    assert(s2 == stop(sem, s, t));
    assert(stop_clean(sem) && clean_proc(s.procs[t as int]) ==> clean_proc(pr2));
    assert forall|m: int| 0 <= m < u.n() implies {
        &&& (excl(#[trigger] s2.procs[t as int].locks[m]) ==> excl(s1.procs[t as int].locks[m]) || no_other_any(sem, u, s1, t, m))
        &&& (any(s2.procs[t as int].locks[m]) ==> any(s1.procs[t as int].locks[m]) || no_other_excl(sem, u, s1, t, m))
    } by {
        assert(s2.procs[t as int].locks[m] == zero_hold());
    }
    assert(full_eff(sem, u, s1, s2, t, w));
    lemma_eff_trans(sem, u, s, s1, s2, t, w);
}

pub open spec fn base_ok(sem: Sem) -> bool {
    true
}

pub proof fn lemma_select_txn_eff(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), s.procs[x as int].alive,
    ensures full_eff(sem, u, s, select_txn(sem, s, x), x, w), select_txn(sem, s, x).g == s.g,
        select_txn(sem, s, x).procs[x as int].alive,
{
    lemma_tstart_eff(sem, u, s, x, w);
    lemma_tstart_wf(u, s, x);
    lemma_set_sqlflag_eff(sem, u, tstart(s, x), x, true, w);
    lemma_eff_trans(sem, u, s, tstart(s, x), set_sqlflag(tstart(s, x), x, true), x, w);
    lemma_eff_refl(sem, u, s, x, w);
}

pub proof fn lemma_txn_step_eff(sem: Sem, u: U, s: State, x: usize, op: Op, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), is_txn_op(op), s.procs[x as int].alive,
    ensures full_eff(sem, u, s, txn_step(sem, s, x, op).0, x, w),
{
    if op is TStart || op is TCommit || op is TRollbackOne || op is TRollback || op is SqlStart || op is TLevel {
        lemma_txn_basic_eff(sem, u, s, x, op, w);
    } else if op is SqlTxnBegin || op is SqlTxnEnd || op is SqlTxnUndo {
        lemma_txn_sqlproc_eff(sem, u, s, x, op, w);
    } else {
        lemma_txn_ends_eff(sem, u, s, x, op, w);
    }
}

pub proof fn lemma_txn_basic_eff(sem: Sem, u: U, s: State, x: usize, op: Op, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), s.procs[x as int].alive,
        op is TStart || op is TCommit || op is TRollbackOne || op is TRollback || op is SqlStart || op is TLevel,
    ensures full_eff(sem, u, s, txn_step(sem, s, x, op).0, x, w),
{
    let l = level(s.procs[x as int]);
    lemma_eff_refl(sem, u, s, x, w);
    match op {
        Op::TStart => lemma_tstart_eff(sem, u, s, x, w),
        Op::TCommit => lemma_commit_top_eff(sem, u, s, x, w),
        Op::TRollbackOne => {
            if l > 0 { lemma_undo_top_eff(sem, u, s, x, w); }
            lemma_rollback_n_eff(sem, u, s, x, l, w);
        },
        Op::TRollback => lemma_rollback_n_eff(sem, u, s, x, l, w),
        Op::SqlStart => {
            lemma_tstart_eff(sem, u, s, x, w);
            lemma_tstart_wf(u, s, x);
            lemma_set_sqlflag_eff(sem, u, tstart(s, x), x, true, w);
            lemma_eff_trans(sem, u, s, tstart(s, x), set_sqlflag(tstart(s, x), x, true), x, w);
        },
        _ => {},
    }
}

pub proof fn lemma_txn_ends_eff(sem: Sem, u: U, s: State, x: usize, op: Op, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), s.procs[x as int].alive,
        op is SqlCommit || op is SqlRollback || op is DrvCommit || op is DrvRollback || op is SetAutocommit,
    ensures full_eff(sem, u, s, txn_step(sem, s, x, op).0, x, w),
{
    let l = level(s.procs[x as int]);
    lemma_eff_refl(sem, u, s, x, w);
    match op {
        Op::SqlCommit => lemma_end_levels_eff(sem, u, s, x, sem.sql_commit, true, w),
        Op::SqlRollback => lemma_end_levels_eff(sem, u, s, x, sem.sql_rollback, false, w),
        Op::DrvCommit => lemma_end_levels_eff(sem, u, s, x, sem.drv_commit, true, w),
        Op::DrvRollback => lemma_end_levels_eff(sem, u, s, x, sem.drv_rollback, false, w),
        Op::SetAutocommit { on } => {
            lemma_end_levels_eff(sem, u, s, x, sem.drv_commit, true, w);
            lemma_end_levels_wf(u, s, sem, x, sem.drv_commit, true);
            lemma_end_levels_alive(sem, u, s, x, sem.drv_commit, true);
            let s2 = if on && l > 0 && sem.autocommit_on_commits { end_levels(s, sem, x, sem.drv_commit, true) } else { s };
            assert(wf_proc(u, s2.procs[x as int]));
            lemma_upd_eff(sem, u, s2, x, Proc { autocommit: on, ..s2.procs[x as int] }, w);
            lemma_eff_trans(sem, u, s, s2, upd(s2, x, Proc { autocommit: on, ..s2.procs[x as int] }), x, w);
        },
        _ => {},
    }
}

pub proof fn lemma_txn_sqlproc_eff(sem: Sem, u: U, s: State, x: usize, op: Op, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), s.procs[x as int].alive,
        op is SqlTxnBegin || op is SqlTxnEnd || op is SqlTxnUndo,
    ensures full_eff(sem, u, s, txn_step(sem, s, x, op).0, x, w),
{
    lemma_select_txn_eff(sem, u, s, x, w);
    lemma_select_txn_wf(sem, u, s, x);
    let s1 = select_txn(sem, s, x);
    let l1 = level(s1.procs[x as int]);
    match op {
        Op::SqlTxnBegin { hold } => {
            let before = l1;
            let s2 = if hold && before == 0 { tstart(s1, x) } else { s1 };
            lemma_tstart_eff(sem, u, s1, x, w);
            lemma_tstart_wf(u, s1, x);
            if hold && before == 0 { lemma_eff_trans(sem, u, s, s1, s2, x, w); }
            assert(s2.procs[x as int].alive);
            lemma_tstart_eff(sem, u, s2, x, w);
            lemma_tstart_wf(u, s2, x);
            let s3 = tstart(s2, x);
            lemma_eff_trans(sem, u, s, s2, s3, x, w);
            let answer = level(s3.procs[x as int]);
            lemma_commit_n_eff(sem, u, s3, x, (answer - before) as nat, w);
            lemma_eff_trans(sem, u, s, s3, commit_n(s3, x, (answer - before) as nat), x, w);
        },
        Op::SqlTxnEnd { level: lv } => {
            lemma_commit_n_eff(sem, u, s1, x, (l1 - lv + 1) as nat, w);
            lemma_eff_trans(sem, u, s, s1, commit_n(s1, x, (l1 - lv + 1) as nat), x, w);
        },
        Op::SqlTxnUndo { level: lv } => {
            lemma_rollback_n_eff(sem, u, s1, x, (l1 - lv + 1) as nat, w);
            lemma_eff_trans(sem, u, s, s1, rollback_n(sem, s1, x, (l1 - lv + 1) as nat), x, w);
            lemma_rollback_n_eff(sem, u, s1, x, l1, w);
            lemma_eff_trans(sem, u, s, s1, rollback_n(sem, s1, x, l1), x, w);
        },
        _ => {},
    }
}

pub proof fn lemma_end_levels_alive(sem: Sem, u: U, s: State, x: usize, ends: Ends, commit: bool)
    requires (x as int) < s.procs.len(), wf(u, s),
    ensures end_levels(s, sem, x, ends, commit).procs[x as int].alive == s.procs[x as int].alive,
{
    let l = level(s.procs[x as int]);
    let n: nat = match ends { Ends::One => 1, Ends::All => l };
    let s2 = if l == 0 { s } else if commit { commit_n(s, x, n) } else { rollback_n(sem, s, x, n) };
    lemma_commit_n_level(u, s, x, n);
    lemma_rollback_n_level(sem, u, s, x, n);
    assert(s2.procs[x as int].alive == s.procs[x as int].alive);
    lemma_commit_n_wf(u, s, x, n);
    lemma_rollback_n_wf(sem, u, s, x, n);
    assert(set_sqlflag(s2, x, false).procs[x as int].alive == s2.procs[x as int].alive);
}

pub proof fn lemma_glob_step_eff(sem: Sem, u: U, s: State, x: usize, op: Op, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), is_glob_op(op), wf_op(u, op), s.procs[x as int].alive,
        forall|c: int| wr(u, op, c) ==> w(c),
    ensures full_eff(sem, u, s, glob_step(sem, u, s, x, op).0, x, w),
{
    let pr = s.procs[x as int];
    assert(wf_proc(u, pr));
    lemma_eff_refl(sem, u, s, x, w);
    match op {
        Op::Set { c, v } => { assert(wr(u, op, c as int)); lemma_write_eff(sem, u, s, x, c, Some(v), true, w) },
        Op::Kill { c } => {
            assert forall|c2: int| covers(u, c as int, c2) implies w(c2) by { assert(wr(u, op, c2)); }
            lemma_kill_eff(sem, u, s, x, c, 0, w)
        },
        Op::Incr { c } => {
            assert(wr(u, op, c as int));
            let cur = num_of(u, s.g[c as int]);
            lemma_write_eff(sem, u, s, x, c, Some(Val::Num((cur + 1) as i64)), !sem.incr_survives, w);
        },
        Op::PpgSet { c, v } => {
            let pr2 = Proc {
                ppg: pr.ppg.update(c as int, Some(v)),
                undo: if level(pr) > 0 { pr.undo.push(Undo { c, old: pr.ppg[c as int], written: Some(v), ppg: true }) } else { pr.undo },
                ..pr
            };
            let s2 = upd(s, x, pr2);
            assert(log_grows_by(pr.undo, pr2.undo, w)) by {
                assert forall|i: int| 0 <= i < pr2.undo.len() implies (#[trigger] pr2.undo[i]).ppg || (i < pr.undo.len() && pr2.undo[i] == pr.undo[i]) || w(pr2.undo[i].c as int) by {
                    if i < pr.undo.len() { assert(pr2.undo[i] == pr.undo[i]); }
                }
            }
            assert(clean_proc(pr) ==> clean_proc(pr2));
            assert(full_eff(sem, u, s, s2, x, w));
        },
        _ => {},
    }
}

pub proof fn lemma_lock_step_eff(sem: Sem, u: U, s: State, x: usize, op: Op, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), is_lock_op(op), wf_op(u, op), s.procs[x as int].alive,
    ensures full_eff(sem, u, s, lock_step(sem, u, s, x, op).0, x, w),
{
    lemma_eff_refl(sem, u, s, x, w);
    lemma_set_pending_eff(sem, u, s, x, Some(op), w);
    match op {
        Op::Lock { c, mode, .. } => {
            if !conflicts(sem, u, s, x, c, mode) { lemma_acquire_eff(sem, u, s, x, c, mode, w); }
        },
        Op::Unlock { c, mode, immediate } => lemma_release_eff(sem, u, s, x, c, mode, immediate, w),
        Op::LockOnly { c, .. } => {
            lemma_release_all_eff(sem, u, s, x, w);
            if let Some(s1) = release_all(sem, s, x) {
                lemma_release_all_wf(sem, u, s, x);
                assert(s1.procs[x as int].alive);
                lemma_set_pending_eff(sem, u, s1, x, Some(op), w);
                lemma_eff_trans(sem, u, s, s1, set_pending(s1, x, Some(op)), x, w);
                if !conflicts(sem, u, s1, x, c, Mode::E) {
                    lemma_acquire_eff(sem, u, s1, x, c, Mode::E, w);
                    if let Some(s2) = acquire(sem, s1, x, c, Mode::E) { lemma_eff_trans(sem, u, s, s1, s2, x, w); }
                }
            }
        },
        Op::ReleaseAll => lemma_release_all_eff(sem, u, s, x, w),
        _ => {},
    }
}

pub proof fn lemma_run_dml_eff(sem: Sem, u: U, s: State, x: usize, op: Op, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), wf_op(u, op), s.procs[x as int].alive,
        forall|c: int| wr(u, op, c) ==> w(c), !blocked(sem, u, s, x, op),
    ensures full_eff(sem, u, s, run_dml(sem, u, s, x, op).0, x, w),
{
    lemma_eff_refl(sem, u, s, x, w);
    match op {
        Op::Insert { r, v } => { assert(wr(u, op, r as int)); lemma_dml_eff(sem, u, s, x, r, Some(v), true, w) },
        Op::Update { r, v } => { assert(wr(u, op, r as int)); lemma_dml_eff(sem, u, s, x, r, Some(v), false, w) },
        Op::Delete { r } => { assert(wr(u, op, r as int)); lemma_dml_eff(sem, u, s, x, r, None, false, w) },
        _ => {},
    }
}

pub proof fn lemma_row_step_eff(sem: Sem, u: U, s: State, x: usize, op: Op, choice: bool, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), is_row_op(op), wf_op(u, op), s.procs[x as int].alive,
        forall|c: int| wr(u, op, c) ==> w(c),
    ensures full_eff(sem, u, s, row_step(sem, u, s, x, op, choice).0, x, w),
{
    lemma_eff_refl(sem, u, s, x, w);
    lemma_set_pending_eff(sem, u, s, x, Some(op), w);
    match op {
        Op::Insert { r, v } => {
            if freedom_cond(sem, s, x, r) {
                // the world that proceeds: the statement's own row lock is not the key's (cleared after)
                assert(wr(u, op, r as int));
                lemma_dml_free_world(sem, u, s, x, r, v, w);
                lemma_run_dml_wf(sem, u, s, x, op);
            } else if !blocked(sem, u, s, x, op) {
                lemma_run_dml_eff(sem, u, s, x, op, w);
            }
        },
        Op::Update { .. } | Op::Delete { .. } => {
            if !blocked(sem, u, s, x, op) { lemma_run_dml_eff(sem, u, s, x, op, w); }
        },
        Op::Select { .. } => lemma_select_txn_eff(sem, u, s, x, w),
        _ => {},
    }
}

/// The Freedom's proceeding world: an INSERT of an invisible key another process holds; x ends without the key's lock.
pub proof fn lemma_dml_free_world(sem: Sem, u: U, s: State, x: usize, r: usize, v: Val, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), (r as int) < u.n(), u.is_row[r as int], w(r as int), s.procs[x as int].alive,
        s.g[r as int] is None,
    ensures full_eff(sem, u, s, set_rlock(dml_insert(sem, u, s, x, r, v).0, x, r, false), x, w),
{
    let op = Op::Insert { r, v };
    if !u.texists[u.table[r as int] as int] {
        lemma_set_rlock_eff(sem, u, s, x, r, false, w);
    } else {
        let b = stmt_begin(s, x);
        lemma_stmt_begin_eff(sem, u, s, x, w);
        lemma_stmt_begin_wf(u, s, x);
        let s2 = write(b.0, x, r, Some(v), true);
        lemma_write_eff(sem, u, b.0, x, r, Some(v), true, w);
        lemma_write_wf(u, b.0, x, r, Some(v), true);
        lemma_eff_trans(sem, u, s, b.0, s2, x, w);
        let s3 = stmt_end(sem, s2, x, b.1, r);
        if b.1 {
            lemma_commit_top_eff(sem, u, s2, x, w);
            lemma_eff_trans(sem, u, s, s2, s3, x, w);
            lemma_commit_top_wf(u, s2, x);
            lemma_set_rlock_eff(sem, u, s3, x, r, false, w);
            lemma_eff_trans(sem, u, s, s3, set_rlock(s3, x, r, false), x, w);
        } else {
            // setting then clearing the flag: the final flag is false; everything else as s2's
            let fin = set_rlock(s3, x, r, false);
            assert(fin == set_rlock(s2, x, r, false)) by {
                assert(fin.procs[x as int].rlocks =~= s2.procs[x as int].rlocks.update(r as int, false));
                assert(fin.procs =~= set_rlock(s2, x, r, false).procs);
            }
            lemma_set_rlock_eff(sem, u, s2, x, r, false, w);
            lemma_eff_trans(sem, u, s, s2, fin, x, w);
        }
    }
}

pub proof fn lemma_await_eff(sem: Sem, u: U, s: State, x: usize, w: spec_fn(int) -> bool)
    requires (x as int) < s.procs.len(), wf(u, s), s.procs[x as int].alive,
        s.procs[x as int].pending matches Some(pend) ==> forall|c: int| wr(u, pend, c) ==> w(c),
    ensures full_eff(sem, u, s, await_step(sem, u, s, x).0, x, w),
{
    lemma_eff_refl(sem, u, s, x, w);
    assert(wf_proc(u, s.procs[x as int]));
    if let Some(pend) = s.procs[x as int].pending {
        let lockwait = pend is Lock || pend is LockOnly;
        if !(blocked(sem, u, s, x, pend) || (lockwait && !sem.lock_wait_grants)) {
            let s1 = set_pending(s, x, None);
            lemma_set_pending_eff(sem, u, s, x, None, w);
            lemma_set_pending_wf(u, s, x, None);
            assert(conflicts(sem, u, s1, x, 0, Mode::E) == conflicts(sem, u, s, x, 0, Mode::E) || true);
            assert(forall|q: int| 0 <= q < s.procs.len() && q != x ==> #[trigger] s1.procs[q] == s.procs[q]);
            match pend {
                Op::Lock { c, mode, .. } => {
                    assert(!conflicts(sem, u, s1, x, c, mode)) by {
                        if conflicts(sem, u, s1, x, c, mode) {
                            let (q, m) = choose|q: int, m: int| 0 <= q < s1.procs.len() && q != x && s1.procs[q].alive && 0 <= m < u.n()
                                && related(sem, u, m, c as int) && hold_conflicts(sem, #[trigger] s1.procs[q].locks[m], mode);
                            assert(s1.procs[q] == s.procs[q]);
                        }
                    }
                    lemma_acquire_eff(sem, u, s1, x, c, mode, w);
                    if let Some(s2) = acquire(sem, s1, x, c, mode) { lemma_eff_trans(sem, u, s, s1, s2, x, w); }
                },
                Op::LockOnly { c, .. } => {
                    assert(!conflicts(sem, u, s1, x, c, Mode::E)) by {
                        if conflicts(sem, u, s1, x, c, Mode::E) {
                            let (q, m) = choose|q: int, m: int| 0 <= q < s1.procs.len() && q != x && s1.procs[q].alive && 0 <= m < u.n()
                                && related(sem, u, m, c as int) && hold_conflicts(sem, #[trigger] s1.procs[q].locks[m], Mode::E);
                            assert(s1.procs[q] == s.procs[q]);
                        }
                    }
                    lemma_acquire_eff(sem, u, s1, x, c, Mode::E, w);
                    if let Some(s2) = acquire(sem, s1, x, c, Mode::E) { lemma_eff_trans(sem, u, s, s1, s2, x, w); }
                },
                Op::Insert { r, .. } | Op::Update { r, .. } | Op::Delete { r } => {
                    assert(row_held(s1, x, r) == row_held(s, x, r)) by { lemma_others_same_rows(s, s1, x, r); }
                    assert(!blocked(sem, u, s1, x, pend));
                    lemma_run_dml_eff(sem, u, s1, x, pend, w);
                    lemma_eff_trans(sem, u, s, s1, run_dml(sem, u, s1, x, pend).0, x, w);
                },
                _ => {},
            }
        }
    }
}

/// The footprint of one operation: the actor's (or, for a stop, the stopped process's) effect.
pub open spec fn actor(s: State, p: usize, op: Op) -> usize {
    match op {
        Op::Terminate { target } => if (p as int) < s.procs.len() && s.procs[p as int].alive && s.procs[p as int].pending is None
            && (target as int) < s.procs.len() && s.procs[target as int].alive { target } else { p },
        _ => p,
    }
}

pub proof fn lemma_step_eff(sem: Sem, u: U, s: State, p: usize, op: Op, choice: bool)
    requires wf(u, s), wf_op(u, op), (p as int) < s.procs.len(),
    ensures full_eff(sem, u, s, step(sem, u, s, p, op, choice).0, actor(s, p, op), wr_of(u, s, p, op)),
{
    let w = wr_of(u, s, p, op);
    let x = actor(s, p, op);
    lemma_eff_refl(sem, u, s, x, w);
    if s.procs[p as int].alive && !(s.procs[p as int].pending is Some && !(op is Await)) {
        if is_txn_op(op) {
            lemma_txn_step_eff(sem, u, s, p, op, w);
        } else if is_glob_op(op) {
            lemma_glob_step_eff(sem, u, s, p, op, w);
        } else if is_lock_op(op) {
            lemma_lock_step_eff(sem, u, s, p, op, w);
        } else if is_row_op(op) {
            lemma_row_step_eff(sem, u, s, p, op, choice, w);
        } else {
            match op {
                Op::Terminate { target } => if (target as int) < s.procs.len() && s.procs[target as int].alive {
                    lemma_stop_eff(sem, u, s, target, w);
                },
                Op::Await => lemma_await_eff(sem, u, s, p, w),
                _ => {},
            }
        }
    }
}

} // verus!
