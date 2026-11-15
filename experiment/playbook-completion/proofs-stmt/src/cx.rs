//! Proved counterexamples of the controls (always compiled): each departing program, run in the contract model on a
//! concrete seven-cell world, fails the Store step (or the Store invariant, or `disc`) its control's located line
//! needs. The world (graph 7 holds one edge e = (7, 1)):
//!   0 `^IVG.Ledger("head")` (the head lock)     1 `^IVG.Ledger("stmt")` (the walk's root)
//!   2 `^IVG.Ledger("stmt", 1)` = Str(0), decoding to (graph 7, tuple cell 3)
//!   3 `^IVG.Ledger("tuple", e)` = 1              4 e's rdf_edges row (table 1)
//!   5 one derived global (every ^KG / ^NKG / ^IVG.* cell the program kills or steps)
//!   6 `^IVG.AdjW(7)` (RemoveGraph's lock); every other table is table 0.
use vstd::prelude::*;
use actors::protocol::*;
use ivg_proofs_env2::spec::*;
use ivg_proofs_env2::clauses::*;
use ivg_proofs_env2::effects::*;
use ivg_proofs_env2::headlock::*;
use ivg_core_proofs::vocab::{Key, edges_ok, member, outside};
use ivg_core_proofs::store::*;
use crate::lay::*;
use crate::prog::*;
use crate::oplem::*;
use crate::runs::*;
use crate::stmts::*;
use crate::eg::*;

verus! {

pub open spec fn cx_u() -> U {
    U {
        paths: seq![seq![1u64, 2u64], seq![1u64, 3u64], seq![1u64, 3u64, 10u64], seq![1u64, 4u64, 11u64], Seq::<u64>::empty(),
                    seq![5u64, 6u64], seq![8u64, 9u64]],
        is_row: seq![false, false, false, false, true, false, false],
        table: seq![0usize, 0usize, 0usize, 0usize, 1usize, 0usize, 0usize],
        texists: seq![true, true],
        parse: Seq::empty(),
        names: Seq::empty(),
        zargs: Seq::empty(),
        long: seq![false, false, false, false, false, false, false],
        key: seq![0usize, 0usize, 0usize, 0usize, 0usize, 0usize, 0usize],
        batches: Seq::empty(),
    }
}

pub open spec fn cx_ly() -> Lay {
    Lay {
        kind: seq![CK::Other, CK::Other, CK::Stmt, CK::Tuple, CK::Gov, CK::Other, CK::Other],
        gr: seq![0int, 0int, 7int, 7int, 7int, 0int, 0int],
        id: seq![0int, 0int, 1int, 1int, 1int, 0int, 0int],
        edge: seq![false, false, true, true, true, false, false],
        dec: seq![Some((7int, 3usize))],
    }
}

pub open spec fn cx_fr() -> Fr {
    Fr {
        t_labels: 0, t_props: 0, t_docs: 0, t_nemb: 0, t_nembo: 0, t_reif: 0, t_eemb: 0, t_edges: 1, t_nodes: 0,
        adjw: 6, head: 0, stmt_root: 1,
        kg_out: 5, kg_in: 5, kg_gen: 5, kg_degc: 5, kg_degw: 5, adjnolock: 5, kg_deg: 5, kg_degp: 5, kg_ver: 5,
        tout: 5, tin: 5, bucket: 5, tagg: 5, edgeprop: 5, tlast: 5,
        kg_prop: 5, kg_label: 5, deg2p: 5, deg2p_exact: 5, gmode: 5, algo_g: 5,
        nkg_ni: 5, nkg_ver: 5, nkg_inval: 5, nkg: 5, algo_all: 5,
    }
}

pub open spec fn cx_proc() -> Proc { init_proc(cx_u(), Kind::Term) }

pub open spec fn cx_state(gv: Seq<Option<Val>>, n: nat) -> State { State { g: gv, procs: Seq::new(n, |q: int| cx_proc()) } }

/// Nothing stored.
pub open spec fn cx_g0() -> Seq<Option<Val>> { seq![None::<Val>, None, None, None, None, None, None] }

/// e's row only.
pub open spec fn cx_grow() -> Seq<Option<Val>> { seq![None::<Val>, None, None, None, Some(Val::Num(1)), None, None] }

/// e's row, its statement and its tuple entry.
pub open spec fn cx_g1() -> Seq<Option<Val>> {
    seq![None::<Val>, None, Some(Val::Str(0)), Some(Val::Num(1)), Some(Val::Num(1)), None, None]
}

pub open spec fn ek() -> Key { Key { g: 7, id: 1, edge: true } }

// ------------------------------------------------------------------------------------------------ the world's facts

pub proof fn lemma_not_covers_at(u: U, a: int, b: int, k: int)
    requires is_glob(u, a), is_glob(u, b), 0 <= k < u.paths[a].len(), k < u.paths[b].len(), u.paths[a][k] != u.paths[b][k],
    ensures !covers(u, a, b),
{
    if covers(u, a, b) {
        assert(u.paths[b].subrange(0, u.paths[a].len() as int)[k] == u.paths[b][k]);
    }
}

pub proof fn lemma_cx_cells(c: int)
    requires 0 <= c < 7,
    ensures
        cx_ly().kind[c] == (if c == 2 { CK::Stmt } else if c == 3 { CK::Tuple } else if c == 4 { CK::Gov } else { CK::Other }),
        cx_u().is_row[c] == (c == 4),
        cx_ly().gr[c] == (if 2 <= c <= 4 { 7int } else { 0int }),
        cx_ly().id[c] == (if 2 <= c <= 4 { 1int } else { 0int }),
        cx_ly().edge[c] == (2 <= c <= 4),
        cx_u().table[c] == (if c == 4 { 1usize } else { 0usize }),
        !cx_u().long[c],
{
    let u = cx_u();
    let ly = cx_ly();
    if c == 0 {} else if c == 1 {} else if c == 2 {} else if c == 3 {} else if c == 4 {} else if c == 5 {} else {
        assert(c == 6);
    }
}

pub proof fn lemma_cx_lay()
    ensures lay_ok(cx_u(), cx_ly()),
{
    let u = cx_u();
    let ly = cx_ly();
    assert(u.n() == 7);
    assert forall|c: int| 0 <= c < u.n() && u.is_row[c] implies (u.table[c] as int) < u.texists.len() by { lemma_cx_cells(c); }
    assert(wf_univ(u));
    assert forall|t: int| 0 <= t < u.texists.len() implies #[trigger] u.texists[t] by { if t == 0 {} else { assert(t == 1); } }
    assert forall|c: int| #[trigger] is_gov(u, ly, c) implies u.is_row[c] by { lemma_cx_cells(c); }
    assert forall|c: int| #[trigger] is_led(u, ly, c) implies is_glob(u, c) by { lemma_cx_cells(c); }
    assert forall|c: int, j: int| is_led(u, ly, c) && 0 <= j < u.n() && j != c implies !#[trigger] covers(u, c, j) by {
        lemma_cx_cells(c);
        lemma_cx_cells(j);
        if c == 2 && j == 3 { lemma_not_covers_at(u, 2, 3, 1); }
        if c == 3 && j == 2 { lemma_not_covers_at(u, 3, 2, 1); }
        if j != 2 && j != 3 && j != 4 { assert(u.paths[j].len() == 2); }
    }
    assert forall|c: int| #[trigger] is_tup(u, ly, c) implies ly.edge[c] by { lemma_cx_cells(c); }
    assert forall|c1: int, c2: int| #[trigger] is_gov(u, ly, c1) && #[trigger] is_gov(u, ly, c2) && key_of(ly, c1) == key_of(ly, c2)
        implies c1 == c2 by {
        lemma_cx_cells(c1);
        lemma_cx_cells(c2);
    }
    assert forall|i: int| 0 <= i < ly.dec.len() && (#[trigger] ly.dec[i]) is Some implies
        is_tup(u, ly, odc(ly.dec[i]) as int) && ly.gr[odc(ly.dec[i]) as int] == odg(ly.dec[i]) by {
        assert(i == 0);
        lemma_cx_cells(3);
    }
}

pub proof fn lemma_cx_derived5()
    ensures derived_cell(cx_u(), cx_ly(), 5usize), plain_cell(cx_u(), cx_ly(), 5usize),
{
    let u = cx_u();
    let ly = cx_ly();
    lemma_cx_cells(5);
    assert forall|x: int| 0 <= x < u.n() && #[trigger] covers(u, 5, x) implies !is_led(u, ly, x) by {
        lemma_cx_cells(x);
        if x == 2 { lemma_not_covers_at(u, 5, 2, 0); }
        if x == 3 { lemma_not_covers_at(u, 5, 3, 0); }
    }
}

pub proof fn lemma_cx_fr()
    ensures fr_ok(cx_u(), cx_ly(), cx_fr()),
{
    let u = cx_u();
    let ly = cx_ly();
    lemma_cx_derived5();
    assert forall|c: int| #[trigger] is_gov(u, ly, c) implies u.table[c] == cx_fr().t_edges by { lemma_cx_cells(c); }
    lemma_cx_cells(0);
    lemma_cx_cells(1);
    lemma_cx_cells(6);
}

/// The world's states meet EraseGraph(7)'s precondition (p = 0; one or two processes, all fresh).
pub proof fn lemma_cx_pre(gv: Seq<Option<Val>>, n: nat, head: bool)
    requires gv.len() == 7, 1 <= n <= 2, sx_ok(cx_u(), cx_ly(), gv),
    ensures eg_pre(contract_sem(), cx_u(), cx_ly(), cx_fr(), cx_state(gv, n), 0, 7, head),
{
    let sem = contract_sem();
    let u = cx_u();
    let ly = cx_ly();
    let s = cx_state(gv, n);
    lemma_cx_lay();
    lemma_cx_fr();
    assert forall|q: int| 0 <= q < s.procs.len() implies wf_proc(u, #[trigger] s.procs[q]) by {
        assert(s.procs[q] == cx_proc());
    }
    assert(wf(u, s));
    assert(s.procs[0] == cx_proc());
    assert(!conflicts(sem, u, s, 0, 6, Mode::S)) by {
        if conflicts(sem, u, s, 0, 6, Mode::S) {
            let (q, m) = choose|q: int, m: int| 0 <= q < s.procs.len() && q != 0 && s.procs[q].alive && 0 <= m < u.n()
                && related(sem, u, m, 6) && hold_conflicts(sem, #[trigger] s.procs[q].locks[m], Mode::S);
            assert(s.procs[q] == cx_proc());
        }
    }
    assert(!conflicts(sem, u, s, 0, 0, Mode::E)) by {
        if conflicts(sem, u, s, 0, 0, Mode::E) {
            let (q, m) = choose|q: int, m: int| 0 <= q < s.procs.len() && q != 0 && s.procs[q].alive && 0 <= m < u.n()
                && related(sem, u, m, 0) && hold_conflicts(sem, #[trigger] s.procs[q].locks[m], Mode::E);
            assert(s.procs[q] == cx_proc());
        }
    }
    assert forall|c: int| 0 <= c < u.n() && u.is_row[c] && ly.gr[c] == 7 as int implies !#[trigger] row_held(s, 0, c as usize) by {
        if row_held(s, 0, c as usize) {
            let q = choose|q: int| 0 <= q < s.procs.len() && q != 0 && s.procs[q].alive && #[trigger] s.procs[q].rlocks[c];
            assert(s.procs[q] == cx_proc());
        }
    }
}

pub proof fn lemma_cx_sx(gv: Seq<Option<Val>>)
    requires gv.len() == 7, gv[3] is None || (gv[3] is Some && gv[2] == Some(Val::Str(0))),
    ensures sx_ok(cx_u(), cx_ly(), gv),
{
    let u = cx_u();
    let ly = cx_ly();
    assert forall|c: int| #[trigger] is_tup(u, ly, c) && gv[c] is Some implies exists|j: int| #[trigger] named(u, ly, gv, j, c) by {
        lemma_cx_cells(c);
        assert(c == 3);
        lemma_cx_cells(2);
        assert(named(u, ly, gv, 2, 3));
    }
}

/// e is a governed row; key of row 4 and of tuple 3.
pub proof fn lemma_cx_keys()
    ensures key_of(cx_ly(), 4) == ek(), key_of(cx_ly(), 3) == ek(), is_gov(cx_u(), cx_ly(), 4), is_tup(cx_u(), cx_ly(), 3),
        forall|c: int| #[trigger] is_gov(cx_u(), cx_ly(), c) ==> c == 4,
        forall|c: int| #[trigger] is_tup(cx_u(), cx_ly(), c) ==> c == 3,
{
    lemma_cx_cells(3);
    lemma_cx_cells(4);
    assert forall|c: int| #[trigger] is_gov(cx_u(), cx_ly(), c) implies c == 4 by { lemma_cx_cells(c); }
    assert forall|c: int| #[trigger] is_tup(cx_u(), cx_ly(), c) implies c == 3 by { lemma_cx_cells(c); }
}

// ------------------------------------------------------------------------------------------------ mutants

/// ctl_mut_drop_edges_delete: without the DELETE FROM rdf_edges (Eraser.cls:217), e's row survives the row DELETEs:
/// no EraseRows step.
pub proof fn cx_mut_drop_edges_delete()
    ensures ({
        let sem = contract_sem();
        let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
        let s0 = cx_state(cx_grow(), 1);
        let t = tg(7);
        let sr = at_rows(sem, u, ly, s0, 0, Mut::DropEdges, true, fr, 7);
        &&& eg_pre(sem, u, ly, fr, s0, 0, 7, true)
        &&& sr.g[4] == Some(Val::Num(1))
        &&& !Store::next(alpha(u, ly, s0.g, None), StoreL::EraseRows { t }, alpha(u, ly, sr.g, Some(t)))
    }),
{
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    let s0 = cx_state(cx_grow(), 1);
    let t = tg(7);
    lemma_cx_sx(cx_grow());
    lemma_cx_pre(cx_grow(), 1, true);
    lemma_eg_points(sem, u, ly, fr, s0, 0, 7, false, true, Mut::DropEdges);
    let s1 = run_prog(sem, u, ly, s0, 0, eg_s1(true, fr));
    let sa = run_prog(sem, u, ly, s1, 0, eg_s0(Mut::DropEdges, fr, 7));
    let sr = at_rows(sem, u, ly, s0, 0, Mut::DropEdges, true, fr, 7);
    let tabs = eg_tables(Mut::DropEdges, fr);
    assert(!in_tabs(tabs, 1usize)) by {
        assert forall|i: int| 0 <= i < tabs.len() implies (#[trigger] tabs[i]).0 == 0usize by {
            if i == 0 {} else if i == 1 {} else if i == 2 {} else if i == 3 {} else if i == 4 {} else if i == 5 {} else if i == 6 {} else { assert(i == 7); }
        }
    }
    lemma_cx_cells(4);
    assert(sr.g[4] == sa.g[4]);
    assert(sr.g[4] == Some(Val::Num(1)));
    lemma_cx_keys();
    lemma_rows_from(u, ly, sr.g, 0, ek());
    assert(alpha(u, ly, sr.g, Some(t)).rows.contains_key(ek()));
    assert(!outside(alpha(u, ly, s0.g, None).rows, t).contains_key(ek())) by {
        assert(member(t, ek()));
    }
}

/// ctl_mut_drop_ledger_cleanup: without EraseLedgerFor (Eraser.cls:256), e's tuple entry outlives its graph's
/// erasure: no EraseIndex step.
pub proof fn cx_mut_drop_ledger_cleanup()
    ensures ({
        let sem = contract_sem();
        let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
        let s0 = cx_state(cx_g1(), 1);
        let t = tg(7);
        let sr = at_rows(sem, u, ly, s0, 0, Mut::DropLedger, true, fr, 7);
        let sc = at_clean(sem, u, ly, s0, 0, Mut::DropLedger, true, fr, 7, false);
        &&& eg_pre(sem, u, ly, fr, s0, 0, 7, true)
        &&& sc.g[3] == Some(Val::Num(1))
        &&& !Store::next(alpha(u, ly, sr.g, Some(t)), StoreL::EraseIndex { t }, alpha(u, ly, sc.g, None))
    }),
{
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    let s0 = cx_state(cx_g1(), 1);
    let t = tg(7);
    lemma_cx_sx(cx_g1());
    lemma_cx_pre(cx_g1(), 1, true);
    lemma_eg_points(sem, u, ly, fr, s0, 0, 7, false, true, Mut::DropLedger);
    let s1 = run_prog(sem, u, ly, s0, 0, eg_s1(true, fr));
    let sa = run_prog(sem, u, ly, s1, 0, eg_s0(Mut::DropLedger, fr, 7));
    let sr = run_prog(sem, u, ly, sa, 0, eg_s2(Mut::DropLedger, fr, 7));
    let s3 = run_prog(sem, u, ly, sr, 0, eg_s3(fr, false));
    let sc = at_clean(sem, u, ly, s0, 0, Mut::DropLedger, true, fr, 7, false);
    lemma_cx_cells(3);
    lemma_cx_keys();
    assert(sr.g[3] == sa.g[3]);
    assert(is_led(u, ly, 3));
    assert(s3.g[3] == sr.g[3]);
    assert(sc.g[3] == Some(Val::Num(1)));
    lemma_stmts_from(u, ly, sc.g, 0, ek());
    assert(alpha(u, ly, sc.g, None).stmts.contains(ek()));
    assert(!alpha(u, ly, sr.g, Some(t)).stmts.filter(|k: Key| !member(t, k)).contains(ek())) by {
        assert(member(t, ek()));
    }
}

/// ctl_mut_ledger_first: EraseLedgerFor before the row DELETEs removes e's tuple entry while e's row is live: the
/// row DELETEs' end is no EraseRows step (the statement index moved).
pub proof fn cx_mut_ledger_first()
    ensures ({
        let sem = contract_sem();
        let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
        let s0 = cx_state(cx_g1(), 1);
        let t = tg(7);
        let sr = at_rows(sem, u, ly, s0, 0, Mut::LedgerFirst, true, fr, 7);
        &&& eg_pre(sem, u, ly, fr, s0, 0, 7, true)
        &&& sr.g[3] is None
        &&& !Store::next(alpha(u, ly, s0.g, None), StoreL::EraseRows { t }, alpha(u, ly, sr.g, Some(t)))
    }),
{
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    let s0 = cx_state(cx_g1(), 1);
    let t = tg(7);
    lemma_cx_sx(cx_g1());
    lemma_cx_pre(cx_g1(), 1, true);
    lemma_cx_lay();
    lemma_eg_points(sem, u, ly, fr, s0, 0, 7, false, true, Mut::LedgerFirst);
    let s1 = run_prog(sem, u, ly, s0, 0, eg_s1(true, fr));
    let sa = run_prog(sem, u, ly, s1, 0, eg_s0(Mut::LedgerFirst, fr, 7));
    let sr = at_rows(sem, u, ly, s0, 0, Mut::LedgerFirst, true, fr, 7);
    lemma_run_prog_one(sem, u, ly, s1, 0, (St::LedgerFor { root: fr.stmt_root, g: 7 }, 10256u32));
    lemma_st_ledger_for(sem, u, ly, s1, 0, fr.stmt_root, 7);
    lemma_cx_cells(3);
    lemma_cx_keys();
    assert(sa.g[3] is None);
    assert(sr.g[3] == sa.g[3]);
    lemma_stmts_from(u, ly, s0.g, 0, ek());
    lemma_stmts_from(u, ly, sr.g, 0, ek());
    assert(alpha(u, ly, s0.g, None).stmts.contains(ek()));
    assert(!alpha(u, ly, sr.g, Some(t)).stmts.contains(ek()));
}

/// ctl_mut_cleanup_after_commit: EraseLedgerFor after TCOMMIT leaves a committed state (no transaction open) where
/// e's tuple entry names a row that is gone: the Store invariant fails at a quiescent point.
pub proof fn cx_mut_cleanup_after_commit()
    ensures ({
        let sem = contract_sem();
        let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
        let s0 = cx_state(cx_g1(), 1);
        let s5 = run_prog(sem, u, ly, at_clean(sem, u, ly, s0, 0, Mut::AfterCommit, true, fr, 7, false), 0, eg_s5(true, fr));
        &&& eg_pre(sem, u, ly, fr, s0, 0, 7, true)
        &&& level(s5.procs[0]) == 0
        &&& !store_inv(alpha(u, ly, s5.g, None))
    }),
{
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    let s0 = cx_state(cx_g1(), 1);
    lemma_cx_sx(cx_g1());
    lemma_cx_pre(cx_g1(), 1, true);
    lemma_eg_points(sem, u, ly, fr, s0, 0, 7, false, true, Mut::AfterCommit);
    let s1 = run_prog(sem, u, ly, s0, 0, eg_s1(true, fr));
    let sa = run_prog(sem, u, ly, s1, 0, eg_s0(Mut::AfterCommit, fr, 7));
    let sr = run_prog(sem, u, ly, sa, 0, eg_s2(Mut::AfterCommit, fr, 7));
    let s3 = run_prog(sem, u, ly, sr, 0, eg_s3(fr, false));
    let s4 = run_prog(sem, u, ly, s3, 0, eg_s4(Mut::AfterCommit, fr, 7));
    let s5 = run_prog(sem, u, ly, s4, 0, eg_s5(true, fr));
    assert(s0.procs[0] == cx_proc());
    let tabs = eg_tables(Mut::AfterCommit, fr);
    assert(tabs[7].0 == 1usize);
    assert(in_tabs(tabs, 1usize));
    lemma_cx_cells(3);
    lemma_cx_cells(4);
    lemma_cx_keys();
    assert(sr.g[4] is None);
    assert(s3.g[4] == sr.g[4]);
    assert(sr.g[3] == s0.g[3]);
    assert(s3.g[3] == sr.g[3]);
    assert(s5.g[3] == Some(Val::Num(1)));
    assert(s5.g[4] is None);
    lemma_stmts_from(u, ly, s5.g, 0, ek());
    lemma_rows_from(u, ly, s5.g, 0, ek());
    let a = alpha(u, ly, s5.g, None);
    assert(a.stmts.contains(ek()));
    assert(!a.rows.contains_key(ek()));
    assert(!in_erasing(a.erasing)(ek()));
}

// ------------------------------------------------------------------------------------------------ F-1201

/// The ledger commit's storage operations in the F-1201 run (Ledger.cls:402 TSTART, :440 the head lock, LedgerApply
/// create_rel's row INSERT, AllocStmt's statement and tuple entries (LedgerApply.cls:164-165), :404 `Lock -`, :405
/// TCOMMIT), creating edge e of graph 7.
pub open spec fn f1201_commit_ops() -> Seq<Op> {
    seq![Op::TStart, Op::Lock { c: 0, mode: Mode::E, wait: true }, Op::Insert { r: 4, v: Val::Num(1) },
         Op::Set { c: 2, v: Val::Str(0) }, Op::Set { c: 3, v: Val::Num(1) }, Op::Unlock { c: 0, mode: Mode::E, immediate: false },
         Op::TCommit]
}

/// The as-built EraseGraph(7) by process 0 up to its row DELETEs and derived kills, the commit by process 1, then
/// EraseLedgerFor and TCOMMIT by process 0 (the live interleaving, live-f1201-reproduced).
pub open spec fn f1201_mid() -> State {
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    let s0 = cx_state(cx_g0(), 2);
    let sr = at_rows(sem, u, ly, s0, 0, Mut::None, false, fr, 7);
    let s3 = run_prog(sem, u, ly, sr, 0, eg_s3(fr, false));
    run_ops(sem, u, s3, 1, f1201_commit_ops())
}

pub open spec fn f1201_end() -> State {
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    run_prog(sem, u, ly, f1201_mid(), 0, eg_s4(Mut::None, fr, 7) + eg_s5(false, fr) + eg_s6(Mut::None, fr, 7))
}

/// The eraser's state just before the commit lands (after its row DELETEs and the derived kills).
pub open spec fn f1201_s3() -> State {
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    run_prog(sem, u, ly, at_rows(sem, u, ly, cx_state(cx_g0(), 2), 0, Mut::None, false, fr, 7), 0, eg_s3(fr, false))
}

pub proof fn lemma_f1201_prefix()
    ensures ({
        let s3 = f1201_s3();
        &&& eg_pre(contract_sem(), cx_u(), cx_ly(), cx_fr(), cx_state(cx_g0(), 2), 0, 7, false)
        &&& ready(cx_u(), s3, 0) && s3.procs.len() == 2
        &&& s3.procs[0].rlocks == cx_proc().rlocks
        &&& s3.procs[0].locks == cx_proc().locks.update(6, def_hold(Mode::S))
        &&& level(s3.procs[0]) == 1
        &&& s3.procs[1] == cx_proc()
        &&& s3.g[2] is None && s3.g[3] is None && s3.g[4] is None
    }),
{
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    let s0 = cx_state(cx_g0(), 2);
    lemma_cx_sx(cx_g0());
    lemma_cx_pre(cx_g0(), 2, false);
    lemma_eg_points(sem, u, ly, fr, s0, 0, 7, false, false, Mut::None);
    assert forall|c: int| 0 <= c < u.n() && u.is_row[c] && ly.gr[c] == 7 as int implies #[trigger] s0.g[c] is None by {
        lemma_cx_cells(c);
    }
    let s1 = run_prog(sem, u, ly, s0, 0, eg_s1(false, fr));
    let sa = run_prog(sem, u, ly, s1, 0, eg_s0(Mut::None, fr, 7));
    let sr = run_prog(sem, u, ly, sa, 0, eg_s2(Mut::None, fr, 7));
    let s3 = run_prog(sem, u, ly, sr, 0, eg_s3(fr, false));
    assert(sr == sa);
    assert(s0.procs[0] == cx_proc());
    assert(s0.procs[1] == cx_proc());
    lemma_cx_cells(2);
    lemma_cx_cells(3);
    lemma_cx_cells(4);
    assert(s3.g[2] == sr.g[2]);
    assert(s3.g[3] == sr.g[3]);
    assert(s3.g[4] == sr.g[4]);
}

/// The commit by process 1 on the eraser's state.
pub proof fn lemma_f1201_commit()
    ensures ({
        let s3 = f1201_s3();
        let t7 = f1201_mid();
        &&& ready(cx_u(), t7, 0) && t7.procs.len() == 2
        &&& t7.procs[0] == s3.procs[0]
        &&& level(t7.procs[1]) == 0
        &&& t7.g[2] == Some(Val::Str(0)) && t7.g[3] == Some(Val::Num(1)) && t7.g[4] == Some(Val::Num(1))
    }),
{
    let sem = contract_sem();
    let u = cx_u();
    lemma_f1201_prefix();
    let s3 = f1201_s3();
    assert(f1201_mid() == run_ops(sem, u, s3, 1, f1201_commit_ops()));
    lemma_cx_cells(4);
    let o = f1201_commit_ops();
    assert(o =~= seq![o[0]] + (seq![o[1]] + (seq![o[2]] + (seq![o[3]] + (seq![o[4]] + (seq![o[5]] + seq![o[6]]))))));
    lemma_op_tstart(sem, u, s3, 1);
    let t1 = step(sem, u, s3, 1, o[0], false).0;
    assert(t1.procs[0] == s3.procs[0]);
    assert(!conflicts(sem, u, t1, 1, 0, Mode::E)) by {
        if conflicts(sem, u, t1, 1, 0, Mode::E) {
            let (q, m) = choose|q: int, m: int| 0 <= q < t1.procs.len() && q != 1 && t1.procs[q].alive && 0 <= m < u.n()
                && related(sem, u, m, 0) && hold_conflicts(sem, #[trigger] t1.procs[q].locks[m], Mode::E);
            assert(q == 0);
            lemma_cx_cells(0);
            lemma_cx_cells(6);
            if m == 6 {
                lemma_not_covers_at(u, 6, 0, 0);
                lemma_not_covers_at(u, 0, 6, 0);
            }
        }
    }
    lemma_op_lock_fresh(sem, u, t1, 1, 0, Mode::E);
    let t2 = step(sem, u, t1, 1, o[1], false).0;
    assert(t2.procs[0] == s3.procs[0]);
    assert(!row_held(t2, 1, 4)) by {
        if row_held(t2, 1, 4) {
            let q = choose|q: int| 0 <= q < t2.procs.len() && q != 1 && t2.procs[q].alive && #[trigger] t2.procs[q].rlocks[4];
            assert(q == 0);
        }
    }
    lemma_op_insert(sem, u, t2, 1, 4, Val::Num(1));
    let t3 = step(sem, u, t2, 1, o[2], false).0;
    lemma_op_set(sem, u, t3, 1, 2, Val::Str(0));
    let t4 = step(sem, u, t3, 1, o[3], false).0;
    lemma_op_set(sem, u, t4, 1, 3, Val::Num(1));
    let t5 = step(sem, u, t4, 1, o[4], false).0;
    lemma_op_unlock_one(sem, u, t5, 1, 0, Mode::E);
    let t6 = step(sem, u, t5, 1, o[5], false).0;
    lemma_op_tcommit(sem, u, t6, 1);
    let t7 = step(sem, u, t6, 1, o[6], false).0;
    lemma_run_ops_cons(sem, u, s3, 1, o[0], seq![o[1]] + (seq![o[2]] + (seq![o[3]] + (seq![o[4]] + (seq![o[5]] + seq![o[6]])))));
    lemma_run_ops_cons(sem, u, t1, 1, o[1], seq![o[2]] + (seq![o[3]] + (seq![o[4]] + (seq![o[5]] + seq![o[6]]))));
    lemma_run_ops_cons(sem, u, t2, 1, o[2], seq![o[3]] + (seq![o[4]] + (seq![o[5]] + seq![o[6]])));
    lemma_run_ops_cons(sem, u, t3, 1, o[3], seq![o[4]] + (seq![o[5]] + seq![o[6]]));
    lemma_run_ops_cons(sem, u, t4, 1, o[4], seq![o[5]] + seq![o[6]]);
    lemma_run_ops_cons(sem, u, t5, 1, o[5], seq![o[6]]);
    lemma_run_ops_one(sem, u, t6, 1, o[6]);
    assert(t3.procs[0] == s3.procs[0]);
    assert(t5.procs[0] == s3.procs[0]);
    assert(t7.procs[0] == s3.procs[0]);
}

/// The eraser's end: EraseLedgerFor and TCOMMIT after the commit.
pub proof fn lemma_f1201_suffix()
    ensures ({
        let t7 = f1201_mid();
        let e = f1201_end();
        &&& level(e.procs[0]) == 0 && e.procs[1] == t7.procs[1]
        &&& e.g[4] == Some(Val::Num(1)) && e.g[3] is None
        &&& e.g.len() == 7
    }),
{
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    lemma_f1201_prefix();
    lemma_f1201_commit();
    lemma_cx_lay();
    let t7 = f1201_mid();
    lemma_cx_sx(t7.g);
    lemma_cx_cells(3);
    lemma_cx_cells(4);
    lemma_run_prog_one(sem, u, ly, t7, 0, (St::LedgerFor { root: fr.stmt_root, g: 7 }, 10256u32));
    lemma_st_ledger_for(sem, u, ly, t7, 0, fr.stmt_root, 7);
    let u4 = run_prog(sem, u, ly, t7, 0, eg_s4(Mut::None, fr, 7));
    assert(level(u4.procs[0]) == 1);
    lemma_s5(sem, u, ly, fr, u4, 0, false);
    let u5 = run_prog(sem, u, ly, u4, 0, eg_s5(false, fr));
    lemma_run_prog_empty(sem, u, ly, u5, 0);
    lemma_run_prog_concat(sem, u, ly, t7, 0, eg_s4(Mut::None, fr, 7) + eg_s5(false, fr), eg_s6(Mut::None, fr, 7));
    lemma_run_prog_concat(sem, u, ly, t7, 0, eg_s4(Mut::None, fr, 7), eg_s5(false, fr));
    assert(eg_s6(Mut::None, fr, 7) =~= Seq::<(St, u32)>::empty());
    assert(f1201_end() == u5);
    assert(is_tup(u, ly, 3));
    assert(!is_led(u, ly, 4));
    assert(u4.g[3] is None);
    assert(u4.g[4] == t7.g[4]);
    assert(u5.g[4] == u4.g[4]);
    assert(u5.g[3] is None);
    assert(u5.procs[1] == u4.procs[1]);
    assert(u4.procs[1] == t7.procs[1]);
    assert(level(u5.procs[0]) == 0);
    assert(u5.g.len() == 7);
}

/// ctl_f1201_erase_no_head_lock: the as-built program issues EraseLedgerFor's Kill of a ledger cell without the head
/// lock (`disc` fails there), and a ledger commit into graph 7 landing between its row DELETEs and EraseLedgerFor
/// leaves, with both committed and nothing open, the committed edge e live without its statement entry.
pub proof fn cx_f1201_interleaving()
    ensures ({
        let sem = contract_sem();
        let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
        let t = f1201_mid();
        let e = f1201_end();
        let a = alpha(u, ly, e.g, None);
        &&& eg_pre(sem, u, ly, fr, cx_state(cx_g0(), 2), 0, 7, false)
        &&& !disc(u, t, 0, Op::Kill { c: 3 }, fr.head, rset(u, ly))
        &&& level(e.procs[0]) == 0 && level(e.procs[1]) == 0
        &&& e.g[4] == Some(Val::Num(1)) && e.g[3] is None
        &&& a.rows.contains_key(ek()) && !a.stmts.contains(ek())
        &&& !edges_ok(a.rows, a.stmts, in_erasing(a.erasing))
    }),
{
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    lemma_f1201_prefix();
    lemma_f1201_commit();
    lemma_f1201_suffix();
    lemma_cx_lay();
    lemma_cx_keys();
    let t7 = f1201_mid();
    let e = f1201_end();
    // disc fails at EraseLedgerFor's kill of e's tuple entry: process 0 holds no head lock
    lemma_cx_cells(3);
    lemma_covers_self(u, 3);
    assert(!disc(u, t7, 0, Op::Kill { c: 3 }, fr.head, rset(u, ly))) by {
        assert(rset(u, ly)(3));
        assert(wr_of(u, t7, 0, Op::Kill { c: 3 })(3));
        assert(t7.procs[0].locks[0] == zero_hold());
    }
    lemma_rows_from(u, ly, e.g, 0, ek());
    lemma_stmts_from(u, ly, e.g, 0, ek());
    let a = alpha(u, ly, e.g, None);
    assert(a.rows.contains_key(ek()));
    assert(!a.stmts.contains(ek()));
    assert(!in_erasing(a.erasing)(ek()));
}

/// The reviewed program at the same point: process 0 holds the head lock from its TSTART, so the commit's head lock
/// waits (Pending) until the erasure ends.
pub proof fn cx_f1201_reviewed_waits()
    ensures ({
        let sem = contract_sem();
        let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
        let s1 = run_prog(sem, u, ly, cx_state(cx_g0(), 2), 0, eg_s1(true, fr));
        let t1 = step(sem, u, s1, 1, Op::TStart, false).0;
        step(sem, u, t1, 1, Op::Lock { c: 0, mode: Mode::E, wait: true }, false).1 == Obs::Pending
    }),
{
    let sem = contract_sem();
    let (u, ly, fr) = (cx_u(), cx_ly(), cx_fr());
    let s0 = cx_state(cx_g0(), 2);
    lemma_cx_sx(cx_g0());
    lemma_cx_pre(cx_g0(), 2, true);
    lemma_s1(sem, u, ly, fr, s0, 0, true);
    let s1 = run_prog(sem, u, ly, s0, 0, eg_s1(true, fr));
    assert(s0.procs[1] == cx_proc());
    assert(s1.procs[1] == s0.procs[1]);
    lemma_op_tstart(sem, u, s1, 1);
    let t1 = step(sem, u, s1, 1, Op::TStart, false).0;
    assert(t1.procs[0] == s1.procs[0]);
    lemma_cx_cells(0);
    lemma_covers_self(u, 0);
    assert(t1.procs[0].locks[0] == one_hold(Mode::E));
    assert(conflicts(sem, u, t1, 1, 0, Mode::E)) by {
        assert(related(sem, u, 0, 0));
        assert(hold_conflicts(sem, t1.procs[0].locks[0], Mode::E));
    }
}

} // verus!
