//! Statement lemmas (playbook 3.4, proof debt D-2): each translated storage statement of EraseGraph, run by its
//! process in the contract model, has the stated effect on the cells the Store abstraction reads. One lemma per
//! statement kind; the segment lemmas lift them to the program's statement lists.
use vstd::prelude::*;
use ivg_proofs_env2::spec::*;
use ivg_proofs_env2::clauses::*;
use crate::lay::*;
use crate::prog::*;
use crate::oplem::*;
use crate::runs::*;

verus! {

/// No other process holds the row lock of a row of graph g (else the DELETE waits for it: P-1201).
pub open spec fn rows_free(u: U, ly: Lay, s: State, p: usize, g: i64) -> bool {
    forall|c: int| 0 <= c < u.n() && u.is_row[c] && ly.gr[c] == g as int ==> !#[trigger] row_held(s, p, c as usize)
}

pub proof fn lemma_rows_free_others(u: U, ly: Lay, a: State, b: State, p: usize, g: i64)
    requires rows_free(u, ly, a, p, g), others(a, b, p),
    ensures rows_free(u, ly, b, p, g),
{
    assert forall|c: int| 0 <= c < u.n() && u.is_row[c] && ly.gr[c] == g as int implies !#[trigger] row_held(b, p, c as usize) by {
        lemma_others_row_held(a, b, p, c as usize);
    }
}

/// A global cell a Kill may take: it covers no ledger cell (and, being a global, no row).
pub open spec fn derived_cell(u: U, ly: Lay, c: usize) -> bool {
    &&& (c as int) < u.n()
    &&& forall|x: int| 0 <= x < u.n() && #[trigger] covers(u, c as int, x) ==> !is_led(u, ly, x)
}

/// A cell a Set / $Increment may take: a global that is not a ledger cell.
pub open spec fn plain_cell(u: U, ly: Lay, c: usize) -> bool {
    (c as int) < u.n() && is_glob(u, c as int) && !is_led(u, ly, c as int)
}

/// A statement that touches neither the governed rows nor the ledger cells nor p's locks.
pub open spec fn st_derived(u: U, ly: Lay, st: St) -> bool {
    match st {
        St::O { op } => match op {
            Op::Kill { c } => derived_cell(u, ly, c),
            Op::Incr { c } => plain_cell(u, ly, c),
            _ => false,
        },
        St::DropNkg { ni, ver, inval, root } => (ni as int) < u.n() && plain_cell(u, ly, ver) && plain_cell(u, ly, inval) && derived_cell(u, ly, root),
        _ => false,
    }
}

pub open spec fn all_derived(u: U, ly: Lay, seg: Seq<(St, u32)>) -> bool {
    forall|i: int| 0 <= i < seg.len() ==> st_derived(u, ly, (#[trigger] seg[i]).0)
}

/// Gov and ledger cells unchanged.
pub open spec fn same_gl(u: U, ly: Lay, a: Seq<Option<Val>>, b: Seq<Option<Val>>) -> bool {
    &&& b.len() == a.len()
    &&& forall|c: int| 0 <= c < b.len() && (is_gov(u, ly, c) || is_led(u, ly, c)) ==> #[trigger] b[c] == a[c]
}

// ------------------------------------------------------------------------------------------------ DELETE

/// `DELETE FROM t WHERE COALESCE(graph_id, '') = COALESCE(:g, '')` from cell j on.
pub proof fn lemma_delg_from(sem: Sem, u: U, ly: Lay, s: State, p: usize, t: usize, g: i64, j: nat)
    requires sem == contract_sem(), lay_ok(u, ly), ready(u, s, p), level(s.procs[p as int]) > 0, rows_free(u, ly, s, p, g),
    ensures ({
        let b = run_ops(sem, u, s, p, delg_ops(u, ly, t, g, j));
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && rows_free(u, ly, b, p, g)
        &&& forall|c: int| 0 <= c < u.n() ==> #[trigger] b.g[c] ==
                (if j <= c && u.is_row[c] && u.table[c] == t && ly.gr[c] == g as int { None::<Val> } else { s.g[c] })
        &&& (forall|c: int| j <= c < u.n() && u.is_row[c] && ly.gr[c] == g as int ==> #[trigger] s.g[c] is None) ==> b == s
    }),
    decreases u.n() - j,
{
    if j < u.n() {
        if u.is_row[j as int] && u.table[j as int] == t && ly.gr[j as int] == g as int {
            let rest = delg_ops(u, ly, t, g, j + 1);
            lemma_run_ops_cons(sem, u, s, p, Op::Delete { r: j as usize }, rest);
            assert(u.texists[u.table[j as int] as int]);
            assert(!row_held(s, p, j as usize));
            lemma_op_delete(sem, u, s, p, j as usize);
            let s1 = step(sem, u, s, p, Op::Delete { r: j as usize }, false).0;
            lemma_rows_free_others(u, ly, s, s1, p, g);
            lemma_delg_from(sem, u, ly, s1, p, t, g, j + 1);
            let b = run_ops(sem, u, s1, p, rest);
            lemma_others_trans(s, s1, b, p);
            if forall|c: int| j <= c < u.n() && u.is_row[c] && ly.gr[c] == g as int ==> #[trigger] s.g[c] is None {
                assert(s.g[j as int] is None);
                assert(s1 == s);
            }
            assert forall|c: int| 0 <= c < u.n() implies #[trigger] b.g[c] ==
                (if j <= c && u.is_row[c] && u.table[c] == t && ly.gr[c] == g as int { None::<Val> } else { s.g[c] }) by {
                if c == j as int {
                    assert(s1.g[c] == None::<Val>);
                }
            }
        } else {
            lemma_delg_from(sem, u, ly, s, p, t, g, j + 1);
        }
    }
}

/// The statement.
pub proof fn lemma_st_delg(sem: Sem, u: U, ly: Lay, s: State, p: usize, t: usize, g: i64)
    requires sem == contract_sem(), lay_ok(u, ly), ready(u, s, p), level(s.procs[p as int]) > 0, rows_free(u, ly, s, p, g),
    ensures ({
        let b = run_st(sem, u, ly, s, p, St::DelG { t, g });
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && rows_free(u, ly, b, p, g)
        &&& forall|c: int| 0 <= c < u.n() ==> #[trigger] b.g[c] ==
                (if u.is_row[c] && u.table[c] == t && ly.gr[c] == g as int { None::<Val> } else { s.g[c] })
        &&& (forall|c: int| 0 <= c < u.n() && u.is_row[c] && ly.gr[c] == g as int ==> #[trigger] s.g[c] is None) ==> b == s
    }),
{
    lemma_delg_from(sem, u, ly, s, p, t, g, 0);
}

pub open spec fn in_tabs(tabs: Seq<(usize, u32)>, t: usize) -> bool {
    exists|i: int| 0 <= i < tabs.len() && (#[trigger] tabs[i]).0 == t
}

/// A list of scoped DELETEs of graph g (EraseGraph's S2).
pub proof fn lemma_delg_seg(sem: Sem, u: U, ly: Lay, s: State, p: usize, tabs: Seq<(usize, u32)>, g: i64)
    requires sem == contract_sem(), lay_ok(u, ly), ready(u, s, p), level(s.procs[p as int]) > 0, rows_free(u, ly, s, p, g),
    ensures ({
        let b = run_prog(sem, u, ly, s, p, delg_seg(tabs, g));
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && rows_free(u, ly, b, p, g)
        &&& forall|c: int| 0 <= c < u.n() ==> #[trigger] b.g[c] ==
                (if u.is_row[c] && ly.gr[c] == g as int && in_tabs(tabs, u.table[c]) { None::<Val> } else { s.g[c] })
        &&& (forall|c: int| 0 <= c < u.n() && u.is_row[c] && ly.gr[c] == g as int ==> #[trigger] s.g[c] is None) ==> b == s
    }),
    decreases tabs.len(),
{
    let seg = delg_seg(tabs, g);
    if tabs.len() == 0 {
        assert(seg =~= Seq::<(St, u32)>::empty());
    } else {
        let t0 = tabs[0].0;
        assert(seg[0] == (St::DelG { t: t0, g }, tabs[0].1));
        assert(seg.drop_first() =~= delg_seg(tabs.drop_first(), g));
        lemma_st_delg(sem, u, ly, s, p, t0, g);
        let s1 = run_st(sem, u, ly, s, p, St::DelG { t: t0, g });
        lemma_delg_seg(sem, u, ly, s1, p, tabs.drop_first(), g);
        let b = run_prog(sem, u, ly, s, p, seg);
        assert(b == run_prog(sem, u, ly, s1, p, delg_seg(tabs.drop_first(), g)));
        lemma_others_trans(s, s1, b, p);
        if forall|c: int| 0 <= c < u.n() && u.is_row[c] && ly.gr[c] == g as int ==> #[trigger] s.g[c] is None {
            assert(s1 == s);
            assert(b == s);
        }
        assert forall|c: int| 0 <= c < u.n() implies #[trigger] b.g[c] ==
            (if u.is_row[c] && ly.gr[c] == g as int && in_tabs(tabs, u.table[c]) { None::<Val> } else { s.g[c] }) by {
            let rest = tabs.drop_first();
            if in_tabs(rest, u.table[c]) {
                let i = choose|i: int| 0 <= i < rest.len() && (#[trigger] rest[i]).0 == u.table[c];
                assert(tabs[i + 1] == rest[i]);
                assert(in_tabs(tabs, u.table[c]));
            }
            if u.table[c] == t0 {
                assert(tabs[0].0 == t0);
                assert(in_tabs(tabs, u.table[c]));
            }
            if in_tabs(tabs, u.table[c]) && u.table[c] != t0 {
                let i = choose|i: int| 0 <= i < tabs.len() && (#[trigger] tabs[i]).0 == u.table[c];
                assert(i != 0);
                assert(rest[i - 1] == tabs[i]);
                assert(in_tabs(rest, u.table[c]));
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ derived statements

pub proof fn lemma_kill_derived(sem: Sem, u: U, ly: Lay, s: State, p: usize, c: usize)
    requires lay_ok(u, ly), ready(u, s, p), derived_cell(u, ly, c),
    ensures ({
        let b = step(sem, u, s, p, Op::Kill { c }, false).0;
        ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p) && same_gl(u, ly, s.g, b.g)
    }),
{
    lemma_op_kill(sem, u, s, p, c);
    let b = step(sem, u, s, p, Op::Kill { c }, false).0;
    assert forall|x: int| 0 <= x < b.g.len() && (is_gov(u, ly, x) || is_led(u, ly, x)) implies #[trigger] b.g[x] == s.g[x] by {
        if covers(u, c as int, x) {
            assert(!is_led(u, ly, x));
            assert(!u.is_row[x]);
        }
    }
}

pub proof fn lemma_incr_plain(sem: Sem, u: U, ly: Lay, s: State, p: usize, c: usize)
    requires lay_ok(u, ly), ready(u, s, p), plain_cell(u, ly, c),
    ensures ({
        let b = step(sem, u, s, p, Op::Incr { c }, false).0;
        ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p) && same_gl(u, ly, s.g, b.g)
    }),
{
    lemma_op_incr(sem, u, s, p, c);
}

pub proof fn lemma_set_plain(sem: Sem, u: U, ly: Lay, s: State, p: usize, c: usize, v: Val)
    requires lay_ok(u, ly), ready(u, s, p), plain_cell(u, ly, c),
    ensures ({
        let b = step(sem, u, s, p, Op::Set { c, v }, false).0;
        ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p) && same_gl(u, ly, s.g, b.g)
    }),
{
    lemma_op_set(sem, u, s, p, c, v);
}

pub proof fn lemma_st_dropnkg(sem: Sem, u: U, ly: Lay, s: State, p: usize, ni: usize, ver: usize, inval: usize, root: usize)
    requires lay_ok(u, ly), ready(u, s, p), (ni as int) < u.n(), plain_cell(u, ly, ver), plain_cell(u, ly, inval), derived_cell(u, ly, root),
    ensures ({
        let b = run_st(sem, u, ly, s, p, St::DropNkg { ni, ver, inval, root });
        ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p) && same_gl(u, ly, s.g, b.g)
    }),
{
    let gv = s.g;
    let o1 = Op::Order { c: ni };
    let o2 = Op::Get { c: ver };
    let o3 = Op::Kill { c: root };
    let o4 = Op::Set { c: ver, v: nkg_next(u, gv[ver as int]) };
    let tail: Seq<Op> = if has_kids(u, gv, ni as int) { seq![Op::Set { c: inval, v: Val::Num(1) }] } else { Seq::empty() };
    let ops = nkg_ops(u, gv, ni, ver, inval, root);
    assert(ops =~= seq![o1] + (seq![o2] + (seq![o3] + (seq![o4] + tail))));
    lemma_run_ops_cons(sem, u, s, p, o1, seq![o2] + (seq![o3] + (seq![o4] + tail)));
    lemma_op_read(sem, u, s, p, o1);
    lemma_run_ops_cons(sem, u, s, p, o2, seq![o3] + (seq![o4] + tail));
    lemma_op_read(sem, u, s, p, o2);
    lemma_run_ops_cons(sem, u, s, p, o3, seq![o4] + tail);
    lemma_kill_derived(sem, u, ly, s, p, root);
    let s3 = step(sem, u, s, p, o3, false).0;
    lemma_run_ops_cons(sem, u, s3, p, o4, tail);
    lemma_set_plain(sem, u, ly, s3, p, ver, nkg_next(u, gv[ver as int]));
    let s4 = step(sem, u, s3, p, o4, false).0;
    lemma_others_trans(s, s3, s4, p);
    if has_kids(u, gv, ni as int) {
        lemma_run_ops_one(sem, u, s4, p, Op::Set { c: inval, v: Val::Num(1) });
        lemma_set_plain(sem, u, ly, s4, p, inval, Val::Num(1));
        let s5 = step(sem, u, s4, p, Op::Set { c: inval, v: Val::Num(1) }, false).0;
        lemma_others_trans(s, s4, s5, p);
    } else {
        lemma_run_ops_empty(sem, u, s4, p);
    }
}

pub proof fn lemma_st_derived(sem: Sem, u: U, ly: Lay, s: State, p: usize, st: St)
    requires lay_ok(u, ly), ready(u, s, p), st_derived(u, ly, st),
    ensures ({
        let b = run_st(sem, u, ly, s, p, st);
        ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p) && same_gl(u, ly, s.g, b.g)
    }),
{
    match st {
        St::O { op } => {
            lemma_run_ops_one(sem, u, s, p, op);
            match op {
                Op::Kill { c } => lemma_kill_derived(sem, u, ly, s, p, c),
                Op::Incr { c } => lemma_incr_plain(sem, u, ly, s, p, c),
                _ => {},
            }
        },
        St::DropNkg { ni, ver, inval, root } => lemma_st_dropnkg(sem, u, ly, s, p, ni, ver, inval, root),
        _ => {},
    }
}

pub proof fn lemma_derived_seg(sem: Sem, u: U, ly: Lay, s: State, p: usize, seg: Seq<(St, u32)>)
    requires lay_ok(u, ly), ready(u, s, p), all_derived(u, ly, seg),
    ensures ({
        let b = run_prog(sem, u, ly, s, p, seg);
        ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p) && same_gl(u, ly, s.g, b.g)
    }),
    decreases seg.len(),
{
    if seg.len() > 0 {
        assert(st_derived(u, ly, seg[0].0));
        lemma_st_derived(sem, u, ly, s, p, seg[0].0);
        let s1 = run_st(sem, u, ly, s, p, seg[0].0);
        assert(all_derived(u, ly, seg.drop_first())) by {
            assert forall|i: int| 0 <= i < seg.drop_first().len() implies st_derived(u, ly, (#[trigger] seg.drop_first()[i]).0) by {
                assert(seg.drop_first()[i] == seg[i + 1]);
            }
        }
        lemma_derived_seg(sem, u, ly, s1, p, seg.drop_first());
        let b = run_prog(sem, u, ly, s1, p, seg.drop_first());
        lemma_others_trans(s, s1, b, p);
    }
}

// ------------------------------------------------------------------------------------------------ EraseLedgerFor

pub open spec fn lf_killed(u: U, ly: Lay, gv: Seq<Option<Val>>, g: i64, j: nat, c: int) -> bool
    decreases u.n() - j
{
    if j >= u.n() {
        false
    } else {
        (doomed(u, ly, gv, g, j as int) && (c == j as int || c == tcell(ly, gv, j as int) as int)) || lf_killed(u, ly, gv, g, j + 1, c)
    }
}

pub proof fn lemma_decv(u: U, ly: Lay, v: Val)
    requires lay_ok(u, ly), decv(ly, v) is Some,
    ensures is_tup(u, ly, odc(decv(ly, v)) as int), ly.gr[odc(decv(ly, v)) as int] == odg(decv(ly, v)),
{
    match v {
        Val::Str(i) => { assert(ly.dec[i as int] is Some); },
        _ => {},
    }
}

pub proof fn lemma_lf_killed_intro(u: U, ly: Lay, gv: Seq<Option<Val>>, g: i64, j: nat, d: int, c: int)
    requires j <= d < u.n(), doomed(u, ly, gv, g, d), c == d || c == tcell(ly, gv, d) as int,
    ensures lf_killed(u, ly, gv, g, j, c),
    decreases d - j,
{
    if j < d {
        lemma_lf_killed_intro(u, ly, gv, g, j + 1, d, c);
    }
}

pub proof fn lemma_lf_killed_elim(u: U, ly: Lay, gv: Seq<Option<Val>>, g: i64, j: nat, c: int)
    requires lf_killed(u, ly, gv, g, j, c),
    ensures exists|d: int| j <= d < u.n() && #[trigger] doomed(u, ly, gv, g, d) && (c == d || c == tcell(ly, gv, d) as int),
    decreases u.n() - j,
{
    if j < u.n() {
        if doomed(u, ly, gv, g, j as int) && (c == j as int || c == tcell(ly, gv, j as int) as int) {
            assert(doomed(u, ly, gv, g, j as int));
        } else {
            lemma_lf_killed_elim(u, ly, gv, g, j + 1, c);
        }
    }
}

/// A ledger cell is a leaf: a Kill of it removes exactly it.
pub proof fn lemma_kill_led(sem: Sem, u: U, ly: Lay, s: State, p: usize, c: usize)
    requires lay_ok(u, ly), ready(u, s, p), is_led(u, ly, c as int),
    ensures ({
        let b = step(sem, u, s, p, Op::Kill { c }, false).0;
        ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p) && b.g == s.g.update(c as int, None)
    }),
{
    lemma_op_kill(sem, u, s, p, c);
    lemma_covers_self(u, c as int);
    let b = step(sem, u, s, p, Op::Kill { c }, false).0;
    assert(b.g =~= s.g.update(c as int, None));
}

/// The kills of EraseLedgerFor (Eraser.cls:1133-1142) for the statements gv names as doomed, cells j.. on.
pub proof fn lemma_lf_kills(sem: Sem, u: U, ly: Lay, s: State, p: usize, gv: Seq<Option<Val>>, g: i64, j: nat)
    requires lay_ok(u, ly), ready(u, s, p), gv.len() == u.n(),
    ensures ({
        let b = run_ops(sem, u, s, p, lf_kills(u, ly, gv, g, j));
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p)
        &&& forall|c: int| 0 <= c < u.n() ==> #[trigger] b.g[c] == (if lf_killed(u, ly, gv, g, j, c) { None::<Val> } else { s.g[c] })
    }),
    decreases u.n() - j,
{
    if j < u.n() {
        if doomed(u, ly, gv, g, j as int) {
            let tc = tcell(ly, gv, j as int);
            lemma_decv(u, ly, gv[j as int]->Some_0);
            let rest = lf_kills(u, ly, gv, g, j + 1);
            let k1 = Op::Kill { c: tc };
            let k2 = Op::Kill { c: j as usize };
            assert(lf_kills(u, ly, gv, g, j) =~= seq![k1] + (seq![k2] + rest));
            lemma_run_ops_cons(sem, u, s, p, k1, seq![k2] + rest);
            lemma_kill_led(sem, u, ly, s, p, tc);
            let s1 = step(sem, u, s, p, k1, false).0;
            lemma_run_ops_cons(sem, u, s1, p, k2, rest);
            lemma_kill_led(sem, u, ly, s1, p, j as usize);
            let s2 = step(sem, u, s1, p, k2, false).0;
            lemma_lf_kills(sem, u, ly, s2, p, gv, g, j + 1);
            let b = run_ops(sem, u, s2, p, rest);
            lemma_others_trans(s, s1, s2, p);
            lemma_others_trans(s, s2, b, p);
            assert forall|c: int| 0 <= c < u.n() implies
                #[trigger] b.g[c] == (if lf_killed(u, ly, gv, g, j, c) { None::<Val> } else { s.g[c] }) by {
                if c == j as int || c == tc as int {
                    assert(s2.g[c] == None::<Val>);
                }
            }
        } else {
            lemma_lf_kills(sem, u, ly, s, p, gv, g, j + 1);
        }
    }
}

/// The `$Get` reads of the walk change nothing.
pub proof fn lemma_lf_reads(sem: Sem, u: U, ly: Lay, s: State, p: usize, gv: Seq<Option<Val>>, j: nat)
    requires ready(u, s, p),
    ensures run_ops(sem, u, s, p, lf_reads(u, ly, gv, j)) == s,
    decreases u.n() - j,
{
    if j < u.n() {
        if is_stm(u, ly, j as int) && gv[j as int] is Some {
            lemma_run_ops_cons(sem, u, s, p, Op::Get { c: j as usize }, lf_reads(u, ly, gv, j + 1));
            lemma_op_read(sem, u, s, p, Op::Get { c: j as usize });
        }
        lemma_lf_reads(sem, u, ly, s, p, gv, j + 1);
    }
}

/// EraseLedgerFor(g), control part: p stays ready, nothing else moves.
pub proof fn lemma_st_lf_ctl(sem: Sem, u: U, ly: Lay, s: State, p: usize, root: usize, g: i64)
    requires lay_ok(u, ly), ready(u, s, p),
    ensures ({
        let b = run_st(sem, u, ly, s, p, St::LedgerFor { root, g });
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p)
        &&& forall|c: int| 0 <= c < u.n() ==> #[trigger] b.g[c] == (if lf_killed(u, ly, s.g, g, 0, c) { None::<Val> } else { s.g[c] })
    }),
{
    let gv = s.g;
    let rd = lf_reads(u, ly, gv, 0);
    let kl = lf_kills(u, ly, gv, g, 0);
    let o = Op::Order { c: root };
    lemma_run_ops_concat(sem, u, s, p, seq![o] + rd, kl);
    lemma_run_ops_concat(sem, u, s, p, seq![o], rd);
    lemma_run_ops_one(sem, u, s, p, o);
    lemma_op_read(sem, u, s, p, o);
    lemma_lf_reads(sem, u, ly, s, p, gv, 0);
    lemma_lf_kills(sem, u, ly, s, p, gv, g, 0);
}

/// EraseLedgerFor(g) (Eraser.cls:1117-1144): with every live tuple entry named by a statement (sx_ok), the tuple
/// entries of graph g go and no other; the statements of g go and no other; nothing else changes.
pub proof fn lemma_st_ledger_for(sem: Sem, u: U, ly: Lay, s: State, p: usize, root: usize, g: i64)
    requires lay_ok(u, ly), ready(u, s, p), sx_ok(u, ly, s.g),
    ensures ({
        let b = run_st(sem, u, ly, s, p, St::LedgerFor { root, g });
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p)
        &&& b.g.len() == s.g.len()
        &&& forall|c: int| 0 <= c < u.n() && !#[trigger] is_led(u, ly, c) ==> b.g[c] == s.g[c]
        &&& forall|c: int| #[trigger] is_tup(u, ly, c) ==> b.g[c] == (if ly.gr[c] == g as int { None::<Val> } else { s.g[c] })
        &&& forall|c: int| #[trigger] is_stm(u, ly, c) ==> b.g[c] == (if doomed(u, ly, s.g, g, c) { None::<Val> } else { s.g[c] })
        &&& sx_ok(u, ly, b.g)
    }),
{
    lemma_st_lf_ctl(sem, u, ly, s, p, root, g);
    let gv = s.g;
    let b = run_st(sem, u, ly, s, p, St::LedgerFor { root, g });
    assert forall|c: int| 0 <= c < u.n() && !#[trigger] is_led(u, ly, c) implies b.g[c] == s.g[c] by {
        if lf_killed(u, ly, gv, g, 0, c) {
            lemma_lf_killed_elim(u, ly, gv, g, 0, c);
            let d = choose|d: int| 0 <= d < u.n() && #[trigger] doomed(u, ly, gv, g, d) && (c == d || c == tcell(ly, gv, d) as int);
            lemma_decv(u, ly, gv[d]->Some_0);
        }
    }
    assert forall|c: int| #[trigger] is_tup(u, ly, c) implies b.g[c] == (if ly.gr[c] == g as int { None::<Val> } else { s.g[c] }) by {
        if ly.gr[c] == g as int {
            if gv[c] is Some {
                let j = choose|j: int| #[trigger] named(u, ly, gv, j, c);
                lemma_decv(u, ly, gv[j]->Some_0);
                assert(doomed(u, ly, gv, g, j));
                lemma_lf_killed_intro(u, ly, gv, g, 0, j, c);
            }
        } else if lf_killed(u, ly, gv, g, 0, c) {
            lemma_lf_killed_elim(u, ly, gv, g, 0, c);
            let d = choose|d: int| 0 <= d < u.n() && #[trigger] doomed(u, ly, gv, g, d) && (c == d || c == tcell(ly, gv, d) as int);
            lemma_decv(u, ly, gv[d]->Some_0);
            assert(c == tcell(ly, gv, d) as int);
        }
    }
    assert forall|c: int| #[trigger] is_stm(u, ly, c) implies b.g[c] == (if doomed(u, ly, gv, g, c) { None::<Val> } else { s.g[c] }) by {
        if doomed(u, ly, gv, g, c) {
            lemma_lf_killed_intro(u, ly, gv, g, 0, c, c);
        } else if lf_killed(u, ly, gv, g, 0, c) {
            lemma_lf_killed_elim(u, ly, gv, g, 0, c);
            let d = choose|d: int| 0 <= d < u.n() && #[trigger] doomed(u, ly, gv, g, d) && (c == d || c == tcell(ly, gv, d) as int);
            lemma_decv(u, ly, gv[d]->Some_0);
            assert(c != d);
        }
    }
    assert(sx_ok(u, ly, b.g)) by {
        assert forall|c: int| #[trigger] is_tup(u, ly, c) && b.g[c] is Some implies exists|j: int| #[trigger] named(u, ly, b.g, j, c) by {
            assert(ly.gr[c] != g as int);
            assert(gv[c] is Some);
            let j = choose|j: int| #[trigger] named(u, ly, gv, j, c);
            lemma_decv(u, ly, gv[j]->Some_0);
            assert(!doomed(u, ly, gv, g, j));
            assert(b.g[j] == gv[j]);
            assert(named(u, ly, b.g, j, c));
        }
    }
}

/// sx_ok reads only the ledger cells.
pub proof fn lemma_sx_ok_same(u: U, ly: Lay, a: Seq<Option<Val>>, b: Seq<Option<Val>>)
    requires sx_ok(u, ly, a), a.len() == u.n(), b.len() == u.n(), forall|c: int| #[trigger] is_led(u, ly, c) ==> b[c] == a[c],
    ensures sx_ok(u, ly, b),
{
    assert forall|c: int| #[trigger] is_tup(u, ly, c) && b[c] is Some implies exists|j: int| #[trigger] named(u, ly, b, j, c) by {
        assert(is_led(u, ly, c));
        let j = choose|j: int| #[trigger] named(u, ly, a, j, c);
        assert(is_led(u, ly, j));
        assert(named(u, ly, b, j, c));
    }
}

/// A list of EraseLedgerFor statements of length at most one (S0, S4, S6), control part.
pub proof fn lemma_lf_seg_ctl(sem: Sem, u: U, ly: Lay, s: State, p: usize, seg: Seq<(St, u32)>, fr: Fr, g: i64)
    requires lay_ok(u, ly), ready(u, s, p), seg.len() == 0 || seg == lf_seg(fr, g),
    ensures ({
        let b = run_prog(sem, u, ly, s, p, seg);
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && plocks(s, b, p) && prl(s, b, p)
        &&& seg.len() == 0 ==> b == s
    }),
{
    if seg.len() == 0 {
        assert(seg =~= Seq::<(St, u32)>::empty());
        lemma_run_prog_empty(sem, u, ly, s, p);
    } else {
        lemma_run_prog_one(sem, u, ly, s, p, (St::LedgerFor { root: fr.stmt_root, g }, 10256u32));
        lemma_st_lf_ctl(sem, u, ly, s, p, fr.stmt_root, g);
    }
}

} // verus!
