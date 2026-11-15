//! Handler theorems for Graph.KG.Eraser.EraseGraph (playbook 3.5, proof debt D-3; lock plan, D-4), about the
//! hand-translated program (`prog.rs`) in the contract model:
//! - `theorem_erase_graph`: run by its process from any state meeting `eg_pre` (no other process acting during the
//!   run), the program performs the core Store contract's `EraseRows{tg(g)}` (at the end of its row DELETEs) and then
//!   `EraseIndex{tg(g)}` (at the end of EraseLedgerFor, inside its transaction), under `alpha`; its commit changes no
//!   storage; it returns at its entry level. For the as-built and the reviewed program alike (`head`).
//! - `theorem_eg_disc`: every operation of the reviewed program's run meets proofs-env2's discipline `disc` for the head
//!   lock H = `^IVG.Ledger("head")` and R = the ledger cells; so (proofs-env2 `theorem_inv_h`, `theorem_atomic`) its
//!   writes to the statement index are atomic towards every process that also keeps `disc`. Control
//!   `ctl_f1201_erase_no_head_lock` (the pin) fails it at EraseLedgerFor.
use vstd::prelude::*;
use actors::protocol::*;
use ivg_proofs_env2::spec::*;
use ivg_proofs_env2::clauses::*;
use ivg_proofs_env2::effects::*;
use ivg_proofs_env2::headlock::*;
use ivg_core_proofs::store::*;
use crate::lay::*;
use crate::prog::*;
use crate::oplem::*;
use crate::runs::*;
use crate::stmts::*;

verus! {

// ------------------------------------------------------------------------------------------------ preconditions

/// The frame of EraseGraph(g) in the universe: governed rows live in the four governed tables; lock names and the
/// statement root are globals; every derived global the program kills covers no ledger cell; the counters it steps
/// are neither ledger cells nor rows.
pub open spec fn fr_ok(u: U, ly: Lay, fr: Fr) -> bool {
    &&& forall|c: int| #[trigger] is_gov(u, ly, c) ==>
            u.table[c] == fr.t_labels || u.table[c] == fr.t_props || u.table[c] == fr.t_edges || u.table[c] == fr.t_nodes
    &&& (fr.adjw as int) < u.n() && (fr.head as int) < u.n() && fr.adjw != fr.head
    &&& is_glob(u, fr.head as int) && is_glob(u, fr.stmt_root as int)
    &&& derived_cell(u, ly, fr.kg_out) && derived_cell(u, ly, fr.kg_in) && derived_cell(u, ly, fr.kg_gen)
    &&& derived_cell(u, ly, fr.kg_degc) && derived_cell(u, ly, fr.kg_degw) && derived_cell(u, ly, fr.adjnolock)
    &&& derived_cell(u, ly, fr.kg_deg) && derived_cell(u, ly, fr.kg_degp)
    &&& derived_cell(u, ly, fr.tout) && derived_cell(u, ly, fr.tin) && derived_cell(u, ly, fr.bucket)
    &&& derived_cell(u, ly, fr.tagg) && derived_cell(u, ly, fr.edgeprop) && derived_cell(u, ly, fr.tlast)
    &&& derived_cell(u, ly, fr.kg_prop) && derived_cell(u, ly, fr.kg_label) && derived_cell(u, ly, fr.deg2p)
    &&& derived_cell(u, ly, fr.deg2p_exact) && derived_cell(u, ly, fr.gmode) && derived_cell(u, ly, fr.algo_g)
    &&& derived_cell(u, ly, fr.nkg) && derived_cell(u, ly, fr.algo_all)
    &&& plain_cell(u, ly, fr.kg_ver) && plain_cell(u, ly, fr.nkg_ver) && plain_cell(u, ly, fr.nkg_inval)
    &&& (fr.nkg_ni as int) < u.n()
}

/// The stated invariant and discipline of a solo run of EraseGraph(g) by p (D-3's "from any state satisfying the
/// invariant"): the validated contract; the layout; p can run and holds neither lock it takes; nothing conflicts with
/// the locks it takes and no other process row-locks a row of g (else the run waits there: P-1201); every live
/// tuple entry is named by its statement (sx_ok).
pub open spec fn eg_pre(sem: Sem, u: U, ly: Lay, fr: Fr, s: State, p: usize, g: i64, head: bool) -> bool {
    &&& sem == contract_sem()
    &&& lay_ok(u, ly)
    &&& fr_ok(u, ly, fr)
    &&& ready(u, s, p)
    &&& s.procs[p as int].locks[fr.adjw as int] == zero_hold()
    &&& s.procs[p as int].locks[fr.head as int] == zero_hold()
    &&& !conflicts(sem, u, s, p, fr.adjw, Mode::S)
    &&& (head ==> !conflicts(sem, u, s, p, fr.head, Mode::E))
    &&& rows_free(u, ly, s, p, g)
    &&& sx_ok(u, ly, s.g)
}

// ------------------------------------------------------------------------------------------------ the derived lists

pub proof fn lemma_s3b_derived(u: U, ly: Lay, fr: Fr)
    requires fr_ok(u, ly, fr),
    ensures all_derived(u, ly, eg_s3b(fr)),
{
    let s = eg_s3b(fr);
    assert forall|i: int| 0 <= i < s.len() implies st_derived(u, ly, (#[trigger] s[i]).0) by {
        if i == 0 { assert(s[0].0 == St::O { op: Op::Kill { c: fr.kg_out } }); }
        else if i == 1 { assert(s[1].0 == St::O { op: Op::Kill { c: fr.kg_in } }); }
        else if i == 2 { assert(s[2].0 == St::O { op: Op::Kill { c: fr.kg_gen } }); }
        else if i == 3 { assert(s[3].0 == St::O { op: Op::Kill { c: fr.kg_degc } }); }
        else if i == 4 { assert(s[4].0 == St::O { op: Op::Kill { c: fr.kg_degw } }); }
        else if i == 5 { assert(s[5].0 == St::O { op: Op::Kill { c: fr.adjnolock } }); }
        else if i == 6 { assert(s[6].0 == St::O { op: Op::Kill { c: fr.kg_deg } }); }
        else if i == 7 { assert(s[7].0 == St::O { op: Op::Kill { c: fr.kg_degp } }); }
        else { assert(s[8].0 == St::O { op: Op::Incr { c: fr.kg_ver } }); }
    }
}

pub proof fn lemma_all_derived_concat(u: U, ly: Lay, a: Seq<(St, u32)>, b: Seq<(St, u32)>)
    requires all_derived(u, ly, a), all_derived(u, ly, b),
    ensures all_derived(u, ly, a + b),
{
    assert forall|i: int| 0 <= i < (a + b).len() implies st_derived(u, ly, (#[trigger] (a + b)[i]).0) by {
        if i < a.len() { assert((a + b)[i] == a[i]); } else { assert((a + b)[i] == b[i - a.len()]); }
    }
}

pub proof fn lemma_s3d_derived(u: U, ly: Lay, fr: Fr, nkg: bool)
    requires fr_ok(u, ly, fr),
    ensures all_derived(u, ly, eg_s3d(fr, nkg)),
{
    let a = eg_ti(fr);
    assert forall|i: int| 0 <= i < a.len() implies st_derived(u, ly, (#[trigger] a[i]).0) by {
        if i == 0 { assert(a[0].0 == St::O { op: Op::Kill { c: fr.tout } }); }
        else if i == 1 { assert(a[1].0 == St::O { op: Op::Kill { c: fr.tin } }); }
        else if i == 2 { assert(a[2].0 == St::O { op: Op::Kill { c: fr.bucket } }); }
        else if i == 3 { assert(a[3].0 == St::O { op: Op::Kill { c: fr.tagg } }); }
        else if i == 4 { assert(a[4].0 == St::O { op: Op::Kill { c: fr.edgeprop } }); }
        else { assert(a[5].0 == St::O { op: Op::Kill { c: fr.tlast } }); }
    }
    let b = eg_er(fr);
    assert forall|i: int| 0 <= i < b.len() implies st_derived(u, ly, (#[trigger] b[i]).0) by {
        if i == 0 { assert(b[0].0 == St::O { op: Op::Kill { c: fr.kg_prop } }); }
        else if i == 1 { assert(b[1].0 == St::O { op: Op::Kill { c: fr.kg_label } }); }
        else if i == 2 { assert(b[2].0 == St::O { op: Op::Kill { c: fr.deg2p } }); }
        else if i == 3 { assert(b[3].0 == St::O { op: Op::Kill { c: fr.deg2p_exact } }); }
        else if i == 4 { assert(b[4].0 == St::O { op: Op::Kill { c: fr.gmode } }); }
        else { assert(b[5].0 == St::O { op: Op::Kill { c: fr.algo_g } }); }
    }
    let c = eg_nkg(fr, nkg);
    assert forall|i: int| 0 <= i < c.len() implies st_derived(u, ly, (#[trigger] c[i]).0) by {
        assert(c[0].0 == St::DropNkg { ni: fr.nkg_ni, ver: fr.nkg_ver, inval: fr.nkg_inval, root: fr.nkg });
    }
    let d = eg_bump(fr);
    assert forall|i: int| 0 <= i < d.len() implies st_derived(u, ly, (#[trigger] d[i]).0) by {
        if i == 0 { assert(d[0].0 == St::O { op: Op::Incr { c: fr.kg_ver } }); }
        else if i == 1 { assert(d[1].0 == St::O { op: Op::Incr { c: fr.nkg_ver } }); }
        else { assert(d[2].0 == St::O { op: Op::Kill { c: fr.algo_all } }); }
    }
    lemma_all_derived_concat(u, ly, a, b);
    lemma_all_derived_concat(u, ly, a + b, c);
    lemma_all_derived_concat(u, ly, a + b + c, d);
}

// ------------------------------------------------------------------------------------------------ segments

/// S1: TSTART, and (reviewed) the head lock.
pub proof fn lemma_s1(sem: Sem, u: U, ly: Lay, fr: Fr, s: State, p: usize, head: bool)
    requires sem == contract_sem(), ready(u, s, p), (fr.head as int) < u.n(), s.procs[p as int].locks[fr.head as int] == zero_hold(),
        head ==> !conflicts(sem, u, s, p, fr.head, Mode::E),
    ensures ({
        let b = run_prog(sem, u, ly, s, p, eg_s1(head, fr));
        &&& ready(u, b, p) && others(s, b, p) && prl(s, b, p)
        &&& b.g == s.g
        &&& level(b.procs[p as int]) == level(s.procs[p as int]) + 1
        &&& b.procs[p as int].locks == (if head { s.procs[p as int].locks.update(fr.head as int, one_hold(Mode::E)) } else { s.procs[p as int].locks })
    }),
{
    let x1 = (St::O { op: Op::TStart }, 10056u32);
    lemma_op_tstart(sem, u, s, p);
    lemma_run_ops_one(sem, u, s, p, Op::TStart);
    let s1 = run_st(sem, u, ly, s, p, x1.0);
    if head {
        let x2 = (St::O { op: Op::Lock { c: fr.head, mode: Mode::E, wait: true } }, 90001u32);
        assert(eg_s1(head, fr) =~= seq![x1] + seq![x2]);
        lemma_run_prog_concat(sem, u, ly, s, p, seq![x1], seq![x2]);
        lemma_run_prog_one(sem, u, ly, s, p, x1);
        lemma_run_prog_one(sem, u, ly, s1, p, x2);
        lemma_others_conflicts(sem, u, s, s1, p, fr.head, Mode::E);
        lemma_run_ops_one(sem, u, s1, p, Op::Lock { c: fr.head, mode: Mode::E, wait: true });
        lemma_op_lock_fresh(sem, u, s1, p, fr.head, Mode::E);
        let s2 = run_st(sem, u, ly, s1, p, x2.0);
        lemma_others_trans(s, s1, s2, p);
    } else {
        lemma_run_prog_one(sem, u, ly, s, p, x1);
    }
}

/// S3: RemoveGraph, TemporalIndex.EraseGraph, the graph-scoped kills, InvalidateDerived.
pub proof fn lemma_s3(sem: Sem, u: U, ly: Lay, fr: Fr, s: State, p: usize, nkg: bool)
    requires sem == contract_sem(), lay_ok(u, ly), fr_ok(u, ly, fr), ready(u, s, p), level(s.procs[p as int]) > 0,
        s.procs[p as int].locks[fr.adjw as int] == zero_hold(), !conflicts(sem, u, s, p, fr.adjw, Mode::S),
    ensures ({
        let b = run_prog(sem, u, ly, s, p, eg_s3(fr, nkg));
        &&& ready(u, b, p) && others(s, b, p) && pctl(s, b, p) && prl(s, b, p) && same_gl(u, ly, s.g, b.g)
        &&& b.procs[p as int].locks == s.procs[p as int].locks.update(fr.adjw as int, def_hold(Mode::S))
    }),
{
    let a = eg_s3a(fr);
    let bb = eg_s3b(fr);
    let c = eg_s3c(fr);
    let d = eg_s3d(fr, nkg);
    lemma_run_prog_concat(sem, u, ly, s, p, a + bb + c, d);
    lemma_run_prog_concat(sem, u, ly, s, p, a + bb, c);
    lemma_run_prog_concat(sem, u, ly, s, p, a, bb);
    // Lock +^IVG.AdjW(g)#"S" (Adjacency.cls:431)
    let lk = Op::Lock { c: fr.adjw, mode: Mode::S, wait: true };
    lemma_run_prog_one(sem, u, ly, s, p, a[0]);
    lemma_run_ops_one(sem, u, s, p, lk);
    lemma_op_lock_fresh(sem, u, s, p, fr.adjw, Mode::S);
    let s1 = run_prog(sem, u, ly, s, p, a);
    // kills and the version step (Adjacency.cls:435-444)
    lemma_s3b_derived(u, ly, fr);
    lemma_derived_seg(sem, u, ly, s1, p, bb);
    let s2 = run_prog(sem, u, ly, s1, p, bb);
    // Lock -^IVG.AdjW(g)#"S" (Adjacency.cls:445), deferred inside the transaction
    let ul = Op::Unlock { c: fr.adjw, mode: Mode::S, immediate: false };
    lemma_run_prog_one(sem, u, ly, s2, p, c[0]);
    lemma_run_ops_one(sem, u, s2, p, ul);
    lemma_op_unlock_one(sem, u, s2, p, fr.adjw, Mode::S);
    let s3 = run_prog(sem, u, ly, s2, p, c);
    assert(s3.procs[p as int].locks =~= s.procs[p as int].locks.update(fr.adjw as int, def_hold(Mode::S)));
    // the rest
    lemma_s3d_derived(u, ly, fr, nkg);
    lemma_derived_seg(sem, u, ly, s3, p, d);
    let s4 = run_prog(sem, u, ly, s3, p, d);
    lemma_others_trans(s, s1, s2, p);
    lemma_others_trans(s, s2, s3, p);
    lemma_others_trans(s, s3, s4, p);
    assert(same_gl(u, ly, s.g, s4.g));
}

/// S5: (reviewed) `Lock -` of the head lock, deferred; TCOMMIT.
pub proof fn lemma_s5(sem: Sem, u: U, ly: Lay, fr: Fr, s: State, p: usize, head: bool)
    requires sem == contract_sem(), ready(u, s, p), level(s.procs[p as int]) > 0, (fr.head as int) < u.n(),
        head ==> s.procs[p as int].locks[fr.head as int] == one_hold(Mode::E),
    ensures ({
        let b = run_prog(sem, u, ly, s, p, eg_s5(head, fr));
        &&& ready(u, b, p) && others(s, b, p)
        &&& b.g == s.g
        &&& level(b.procs[p as int]) == level(s.procs[p as int]) - 1
    }),
{
    let xc = (St::O { op: Op::TCommit }, 10258u32);
    if head {
        let xu = (St::O { op: Op::Unlock { c: fr.head, mode: Mode::E, immediate: false } }, 90002u32);
        assert(eg_s5(head, fr) =~= seq![xu] + seq![xc]);
        lemma_run_prog_concat(sem, u, ly, s, p, seq![xu], seq![xc]);
        lemma_run_prog_one(sem, u, ly, s, p, xu);
        lemma_run_ops_one(sem, u, s, p, Op::Unlock { c: fr.head, mode: Mode::E, immediate: false });
        lemma_op_unlock_one(sem, u, s, p, fr.head, Mode::E);
        let s1 = run_st(sem, u, ly, s, p, xu.0);
        lemma_run_prog_one(sem, u, ly, s1, p, xc);
        lemma_run_ops_one(sem, u, s1, p, Op::TCommit);
        lemma_op_tcommit(sem, u, s1, p);
        let s2 = run_st(sem, u, ly, s1, p, xc.0);
        lemma_others_trans(s, s1, s2, p);
    } else {
        lemma_run_prog_one(sem, u, ly, s, p, xc);
        lemma_run_ops_one(sem, u, s, p, Op::TCommit);
        lemma_op_tcommit(sem, u, s, p);
    }
}

/// S0, S4 and S6 are each empty or the one EraseLedgerFor statement, whatever the mutant.
pub proof fn lemma_lf_shapes(m: Mut, fr: Fr, g: i64)
    ensures
        eg_s0(m, fr, g).len() == 0 || eg_s0(m, fr, g) == lf_seg(fr, g),
        eg_s4(m, fr, g).len() == 0 || eg_s4(m, fr, g) == lf_seg(fr, g),
        eg_s6(m, fr, g).len() == 0 || eg_s6(m, fr, g) == lf_seg(fr, g),
{
}

// ------------------------------------------------------------------------------------------------ shape facts

/// The row DELETEs reach the four governed tables (Eraser.cls:130, 134, 217, 222).
pub proof fn shape_rows(fr: Fr)
    ensures
        in_tabs(eg_tables(active_mut(), fr), fr.t_labels), in_tabs(eg_tables(active_mut(), fr), fr.t_props),
        in_tabs(eg_tables(active_mut(), fr), fr.t_edges), in_tabs(eg_tables(active_mut(), fr), fr.t_nodes),
{
    let tabs = eg_tables(active_mut(), fr);
    assert(tabs[0].0 == fr.t_labels);
    assert(tabs[1].0 == fr.t_props);
    assert(tabs[tabs.len() - 2].0 == fr.t_edges); // LOCATE ctl_mut_drop_edges_delete
    assert(tabs[tabs.len() - 1].0 == fr.t_nodes);
}

/// Nothing runs between TSTART and the row DELETEs.
pub proof fn shape_s0(fr: Fr, g: i64)
    ensures eg_s0(active_mut(), fr, g).len() == 0,
{
    assert(eg_s0(active_mut(), fr, g).len() == 0); // LOCATE ctl_mut_ledger_first
}

/// EraseLedgerFor runs after the derived kills, inside the transaction (Eraser.cls:256).
pub proof fn shape_s4(fr: Fr, g: i64)
    ensures eg_s4(active_mut(), fr, g) == lf_seg(fr, g),
{
    assert(eg_s4(active_mut(), fr, g) == lf_seg(fr, g)); // LOCATE ctl_mut_drop_ledger_cleanup ctl_mut_ledger_first ctl_mut_cleanup_after_commit
}

/// Nothing of the program's storage statements runs after TCOMMIT.
pub proof fn shape_s6(fr: Fr, g: i64)
    ensures eg_s6(active_mut(), fr, g).len() == 0,
{
    assert(eg_s6(active_mut(), fr, g).len() == 0); // LOCATE ctl_mut_cleanup_after_commit
}

// ------------------------------------------------------------------------------------------------ program points

pub open spec fn at_rows(sem: Sem, u: U, ly: Lay, s0: State, p: usize, m: Mut, head: bool, fr: Fr, g: i64) -> State {
    run_prog(sem, u, ly, s0, p, eg_s1(head, fr) + eg_s0(m, fr, g) + eg_s2(m, fr, g))
}

pub open spec fn at_clean(sem: Sem, u: U, ly: Lay, s0: State, p: usize, m: Mut, head: bool, fr: Fr, g: i64, nkg: bool) -> State {
    run_prog(sem, u, ly, at_rows(sem, u, ly, s0, p, m, head, fr, g), p, eg_s3(fr, nkg) + eg_s4(m, fr, g))
}

pub open spec fn at_end(sem: Sem, u: U, ly: Lay, s0: State, p: usize, m: Mut, head: bool, fr: Fr, g: i64, nkg: bool) -> State {
    run_prog(sem, u, ly, s0, p, eg_prog_m(m, head, fr, g, nkg))
}

/// The run's state at the boundaries of its segments, whatever the mutant (control facts only).
pub proof fn lemma_eg_points(sem: Sem, u: U, ly: Lay, fr: Fr, s0: State, p: usize, g: i64, nkg: bool, head: bool, m: Mut)
    requires eg_pre(sem, u, ly, fr, s0, p, g, head),
    ensures ({
        let s1 = run_prog(sem, u, ly, s0, p, eg_s1(head, fr));
        let sa = run_prog(sem, u, ly, s1, p, eg_s0(m, fr, g));
        let sr = run_prog(sem, u, ly, sa, p, eg_s2(m, fr, g));
        let s3 = run_prog(sem, u, ly, sr, p, eg_s3(fr, nkg));
        let s4 = run_prog(sem, u, ly, s3, p, eg_s4(m, fr, g));
        let s5 = run_prog(sem, u, ly, s4, p, eg_s5(head, fr));
        let s6 = run_prog(sem, u, ly, s5, p, eg_s6(m, fr, g));
        let l0 = level(s0.procs[p as int]);
        let hl = if head { s0.procs[p as int].locks.update(fr.head as int, one_hold(Mode::E)) } else { s0.procs[p as int].locks };
        &&& ready(u, s1, p) && others(s0, s1, p) && s1.g == s0.g && level(s1.procs[p as int]) == l0 + 1 && s1.procs[p as int].locks == hl
        &&& prl(s0, s1, p)
        &&& ready(u, sa, p) && others(s0, sa, p) && pctl(s1, sa, p) && plocks(s1, sa, p) && prl(s1, sa, p)
        &&& (eg_s0(m, fr, g).len() == 0 ==> sa == s1)
        &&& ready(u, sr, p) && others(s0, sr, p) && pctl(sa, sr, p) && plocks(sa, sr, p)
        &&& (eg_s0(m, fr, g).len() == 0 && (forall|c: int| 0 <= c < u.n() && u.is_row[c] && ly.gr[c] == g as int ==> #[trigger] s0.g[c] is None))
                ==> sr == sa
        &&& forall|c: int| 0 <= c < u.n() ==> #[trigger] sr.g[c] ==
                (if u.is_row[c] && ly.gr[c] == g as int && in_tabs(eg_tables(m, fr), u.table[c]) { None::<Val> } else { sa.g[c] })
        &&& ready(u, s3, p) && others(s0, s3, p) && pctl(sr, s3, p) && prl(sr, s3, p) && same_gl(u, ly, sr.g, s3.g)
        &&& s3.procs[p as int].locks == sr.procs[p as int].locks.update(fr.adjw as int, def_hold(Mode::S))
        &&& ready(u, s4, p) && others(s0, s4, p) && pctl(s3, s4, p) && plocks(s3, s4, p) && prl(s3, s4, p)
        &&& (eg_s4(m, fr, g).len() == 0 ==> s4 == s3)
        &&& ready(u, s5, p) && others(s0, s5, p) && s5.g == s4.g && level(s5.procs[p as int]) == l0
        &&& ready(u, s6, p) && others(s0, s6, p)
        &&& (eg_s6(m, fr, g).len() == 0 ==> s6 == s5)
        &&& run_prog(sem, u, ly, s0, p, eg_prog_m(m, head, fr, g, nkg)) == s6
        &&& at_rows(sem, u, ly, s0, p, m, head, fr, g) == sr
        &&& at_clean(sem, u, ly, s0, p, m, head, fr, g, nkg) == s4
    }),
{
    let s1 = run_prog(sem, u, ly, s0, p, eg_s1(head, fr));
    let sa = run_prog(sem, u, ly, s1, p, eg_s0(m, fr, g));
    let sr = run_prog(sem, u, ly, sa, p, eg_s2(m, fr, g));
    let s3 = run_prog(sem, u, ly, sr, p, eg_s3(fr, nkg));
    let s4 = run_prog(sem, u, ly, s3, p, eg_s4(m, fr, g));
    let s5 = run_prog(sem, u, ly, s4, p, eg_s5(head, fr));
    let s6 = run_prog(sem, u, ly, s5, p, eg_s6(m, fr, g));
    lemma_s1(sem, u, ly, fr, s0, p, head);
    lemma_lf_shapes(m, fr, g);
    lemma_lf_seg_ctl(sem, u, ly, s1, p, eg_s0(m, fr, g), fr, g);
    lemma_others_trans(s0, s1, sa, p);
    lemma_rows_free_others(u, ly, s0, sa, p, g);
    lemma_delg_seg(sem, u, ly, sa, p, eg_tables(m, fr), g);
    lemma_others_trans(s0, sa, sr, p);
    if eg_s0(m, fr, g).len() == 0 && (forall|c: int| 0 <= c < u.n() && u.is_row[c] && ly.gr[c] == g as int ==> #[trigger] s0.g[c] is None) {
        assert(sa == s1);
        assert(forall|c: int| 0 <= c < u.n() && u.is_row[c] && ly.gr[c] == g as int ==> #[trigger] sa.g[c] is None);
    }
    lemma_others_conflicts(sem, u, s0, sr, p, fr.adjw, Mode::S);
    lemma_s3(sem, u, ly, fr, sr, p, nkg);
    lemma_others_trans(s0, sr, s3, p);
    lemma_lf_seg_ctl(sem, u, ly, s3, p, eg_s4(m, fr, g), fr, g);
    lemma_others_trans(s0, s3, s4, p);
    assert(head ==> s4.procs[p as int].locks[fr.head as int] == one_hold(Mode::E));
    lemma_s5(sem, u, ly, fr, s4, p, head);
    lemma_others_trans(s0, s4, s5, p);
    lemma_lf_seg_ctl(sem, u, ly, s5, p, eg_s6(m, fr, g), fr, g);
    lemma_others_trans(s0, s5, s6, p);
    // the whole program
    let p1 = eg_s1(head, fr);
    let p0 = eg_s0(m, fr, g);
    let p2 = eg_s2(m, fr, g);
    let p3 = eg_s3(fr, nkg);
    let p4 = eg_s4(m, fr, g);
    let p5 = eg_s5(head, fr);
    let p6 = eg_s6(m, fr, g);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2 + p3 + p4 + p5, p6);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2 + p3 + p4, p5);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2 + p3, p4);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2, p3);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1 + p0, p2);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1, p0);
    lemma_run_prog_concat(sem, u, ly, sr, p, p3, p4);
}

// ------------------------------------------------------------------------------------------------ THEOREM (3.5)

/// THEOREM: EraseGraph(g)'s translated program, run by p from any state meeting `eg_pre`, performs the Store
/// contract's `EraseRows{tg(g)}` with its row DELETEs and `EraseIndex{tg(g)}` with EraseLedgerFor, before its TCOMMIT;
/// TCOMMIT and nothing after it changes storage; p ends at its entry level. As-built (`head` false) and reviewed.
pub proof fn theorem_erase_graph(sem: Sem, u: U, ly: Lay, fr: Fr, s0: State, p: usize, g: i64, nkg: bool, head: bool)
    requires eg_pre(sem, u, ly, fr, s0, p, g, head),
    ensures ({
        let m = active_mut();
        let t = tg(g as int);
        let sr = at_rows(sem, u, ly, s0, p, m, head, fr, g);
        let sc = at_clean(sem, u, ly, s0, p, m, head, fr, g, nkg);
        let se = at_end(sem, u, ly, s0, p, m, head, fr, g, nkg);
        &&& Store::next(alpha(u, ly, s0.g, None), StoreL::EraseRows { t }, alpha(u, ly, sr.g, Some(t)))
        &&& Store::next(alpha(u, ly, sr.g, Some(t)), StoreL::EraseIndex { t }, alpha(u, ly, sc.g, None))
        &&& se.g == sc.g
        &&& ready(u, se, p) && others(s0, se, p)
        &&& level(se.procs[p as int]) == level(s0.procs[p as int])
    }),
{
    let m = active_mut();
    let t = tg(g as int);
    lemma_eg_points(sem, u, ly, fr, s0, p, g, nkg, head, m);
    let s1 = run_prog(sem, u, ly, s0, p, eg_s1(head, fr));
    let sa = run_prog(sem, u, ly, s1, p, eg_s0(m, fr, g));
    let sr = run_prog(sem, u, ly, sa, p, eg_s2(m, fr, g));
    let s3 = run_prog(sem, u, ly, sr, p, eg_s3(fr, nkg));
    let s4 = run_prog(sem, u, ly, s3, p, eg_s4(m, fr, g));
    let s5 = run_prog(sem, u, ly, s4, p, eg_s5(head, fr));
    // the program's shape
    shape_s0(fr, g);
    shape_rows(fr);
    shape_s4(fr, g);
    shape_s6(fr, g);
    assert(sa == s1);
    // EraseRows: the governed rows of g are gone, every other governed row and the statement index are as before
    assert forall|c: int| #[trigger] is_gov(u, ly, c) implies sr.g[c] == (if ly.gr[c] == g as int { None::<Val> } else { s0.g[c] }) by {
        assert(u.is_row[c]);
    }
    lemma_rows_outside(u, ly, s0.g, sr.g, g as int);
    assert forall|c: int| #[trigger] is_tup(u, ly, c) implies sr.g[c] == s0.g[c] by {
        assert(is_led(u, ly, c));
        assert(!u.is_row[c]);
    }
    lemma_stmts_same(u, ly, s0.g, sr.g);
    assert(Store::next(alpha(u, ly, s0.g, None), StoreL::EraseRows { t }, alpha(u, ly, sr.g, Some(t))));
    // EraseIndex: EraseLedgerFor (S4), after the derived kills (S3), before TCOMMIT
    assert forall|c: int| #[trigger] is_led(u, ly, c) implies s3.g[c] == s0.g[c] by {
        assert(!u.is_row[c]);
        assert(sr.g[c] == s0.g[c]);
    }
    lemma_sx_ok_same(u, ly, s0.g, s3.g);
    lemma_run_prog_one(sem, u, ly, s3, p, (St::LedgerFor { root: fr.stmt_root, g }, 10256u32));
    lemma_st_ledger_for(sem, u, ly, s3, p, fr.stmt_root, g);
    assert forall|c: int| #[trigger] is_gov(u, ly, c) implies s4.g[c] == sr.g[c] by {
        assert(!is_led(u, ly, c));
        assert(s3.g[c] == sr.g[c]);
    }
    lemma_rows_same(u, ly, sr.g, s4.g);
    assert forall|c: int| #[trigger] is_tup(u, ly, c) implies s4.g[c] == (if ly.gr[c] == g as int { None::<Val> } else { sr.g[c] }) by {
        assert(is_led(u, ly, c));
        assert(s3.g[c] == sr.g[c]);
    }
    lemma_stmts_clean(u, ly, sr.g, s4.g, g as int);
    assert(Store::next(alpha(u, ly, sr.g, Some(t)), StoreL::EraseIndex { t }, alpha(u, ly, s4.g, None)));
}

// ------------------------------------------------------------------------------------------------ the discipline (D-4)

pub open spec fn rset(u: U, ly: Lay) -> spec_fn(int) -> bool { |c: int| is_led(u, ly, c) }

pub open spec fn disc_all(u: U, ly: Lay, tr: Seq<(State, Op)>, p: usize, h: usize) -> bool {
    forall|i: int| 0 <= i < tr.len() ==> disc(u, (#[trigger] tr[i]).0, p, tr[i].1, h, rset(u, ly))
}

/// The operation writes no ledger cell and is no immediate release of H.
pub open spec fn no_r(u: U, ly: Lay, op: Op, h: usize) -> bool {
    &&& forall|c: int| #[trigger] is_led(u, ly, c) ==> !wr(u, op, c)
    &&& !(op == Op::Unlock { c: h, mode: Mode::E, immediate: true })
    &&& !(op is Await)
}

pub open spec fn st_no_r(u: U, ly: Lay, st: St, h: usize) -> bool {
    match st {
        St::O { op } => no_r(u, ly, op, h),
        St::DelG { .. } => true,
        St::DropNkg { ni, ver, inval, root } => plain_cell(u, ly, ver) && plain_cell(u, ly, inval) && derived_cell(u, ly, root),
        St::LedgerFor { .. } => false,
    }
}

pub open spec fn all_no_r(u: U, ly: Lay, seg: Seq<(St, u32)>, h: usize) -> bool {
    forall|i: int| 0 <= i < seg.len() ==> st_no_r(u, ly, (#[trigger] seg[i]).0, h)
}

pub proof fn lemma_disc_all_concat(u: U, ly: Lay, a: Seq<(State, Op)>, b: Seq<(State, Op)>, p: usize, h: usize)
    requires disc_all(u, ly, a, p, h), disc_all(u, ly, b, p, h),
    ensures disc_all(u, ly, a + b, p, h),
{
    assert forall|i: int| 0 <= i < (a + b).len() implies disc(u, (#[trigger] (a + b)[i]).0, p, (a + b)[i].1, h, rset(u, ly)) by {
        if i < a.len() { assert((a + b)[i] == a[i]); } else { assert((a + b)[i] == b[i - a.len()]); }
    }
}

pub proof fn lemma_no_r_disc(u: U, ly: Lay, s: State, p: usize, op: Op, h: usize)
    requires no_r(u, ly, op, h),
    ensures disc(u, s, p, op, h, rset(u, ly)),
{
    assert forall|c: int| (#[trigger] rset(u, ly)(c)) && wr_of(u, s, p, op)(c) implies
        excl(s.procs[p as int].locks[h as int]) && level(s.procs[p as int]) > 0 && !(op is Incr) by {
        assert(is_led(u, ly, c));
    }
}

pub proof fn lemma_trace_no_r(sem: Sem, u: U, ly: Lay, s: State, p: usize, ops: Seq<Op>, h: usize)
    requires forall|i: int| 0 <= i < ops.len() ==> no_r(u, ly, #[trigger] ops[i], h),
    ensures disc_all(u, ly, trace_ops(sem, u, s, p, ops), p, h),
    decreases ops.len(),
{
    if ops.len() > 0 {
        let s1 = step(sem, u, s, p, ops[0], false).0;
        assert forall|i: int| 0 <= i < ops.drop_first().len() implies no_r(u, ly, #[trigger] ops.drop_first()[i], h) by {
            assert(ops.drop_first()[i] == ops[i + 1]);
        }
        lemma_trace_no_r(sem, u, ly, s1, p, ops.drop_first(), h);
        assert(no_r(u, ly, ops[0], h));
        lemma_no_r_disc(u, ly, s, p, ops[0], h);
        let x = seq![(s, ops[0])];
        assert(disc_all(u, ly, x, p, h)) by {
            assert forall|i: int| 0 <= i < x.len() implies disc(u, (#[trigger] x[i]).0, p, x[i].1, h, rset(u, ly)) by {
                assert(x[i] == (s, ops[0]));
            }
        }
        lemma_disc_all_concat(u, ly, x, trace_ops(sem, u, s1, p, ops.drop_first()), p, h);
    }
}

pub open spec fn row_delete(u: U, op: Op) -> bool {
    match op { Op::Delete { r } => (r as int) < u.n() && u.is_row[r as int], _ => false }
}

pub proof fn lemma_delg_ops_rows(u: U, ly: Lay, t: usize, g: i64, j: nat)
    requires u.n() <= usize::MAX,
    ensures forall|i: int| 0 <= i < delg_ops(u, ly, t, g, j).len() ==> row_delete(u, #[trigger] delg_ops(u, ly, t, g, j)[i]),
    decreases u.n() - j,
{
    if j < u.n() {
        lemma_delg_ops_rows(u, ly, t, g, j + 1);
        let rest = delg_ops(u, ly, t, g, j + 1);
        if u.is_row[j as int] && u.table[j as int] == t && ly.gr[j as int] == g as int {
            let x = seq![Op::Delete { r: j as usize }] + rest;
            assert forall|i: int| 0 <= i < x.len() implies row_delete(u, #[trigger] x[i]) by {
                if i > 0 { assert(x[i] == rest[i - 1]); }
            }
        }
    }
}

/// Every operation of a statement that writes no ledger cell.
pub proof fn lemma_st_ops_no_r(u: U, ly: Lay, gv: Seq<Option<Val>>, st: St, h: usize)
    requires lay_ok(u, ly), st_no_r(u, ly, st, h),
    ensures forall|i: int| 0 <= i < ops_of(u, ly, gv, st).len() ==> no_r(u, ly, #[trigger] ops_of(u, ly, gv, st)[i], h),
{
    let ops = ops_of(u, ly, gv, st);
    match st {
        St::O { op } => {
            assert forall|i: int| 0 <= i < ops.len() implies no_r(u, ly, #[trigger] ops[i], h) by { assert(ops[i] == op); }
        },
        St::DelG { t, g } => {
            lemma_delg_ops_rows(u, ly, t, g, 0);
            assert forall|i: int| 0 <= i < ops.len() implies no_r(u, ly, #[trigger] ops[i], h) by {
                assert(row_delete(u, ops[i]));
                assert forall|c: int| #[trigger] is_led(u, ly, c) implies !wr(u, ops[i], c) by {
                    assert(is_glob(u, c));
                }
            }
        },
        St::DropNkg { ni, ver, inval, root } => {
            let o1 = Op::Order { c: ni };
            let o2 = Op::Get { c: ver };
            let o3 = Op::Kill { c: root };
            let o4 = Op::Set { c: ver, v: nkg_next(u, gv[ver as int]) };
            let o5 = Op::Set { c: inval, v: Val::Num(1) };
            assert(no_r(u, ly, o3, h)) by {
                assert forall|c: int| #[trigger] is_led(u, ly, c) implies !wr(u, o3, c) by {
                    if covers(u, root as int, c) { assert(!is_led(u, ly, c)); }
                }
            }
            assert(no_r(u, ly, o1, h));
            assert(no_r(u, ly, o2, h));
            assert(no_r(u, ly, o4, h));
            assert(no_r(u, ly, o5, h));
            assert forall|i: int| 0 <= i < ops.len() implies no_r(u, ly, #[trigger] ops[i], h) by {
                if i == 0 { assert(ops[i] == o1); }
                else if i == 1 { assert(ops[i] == o2); }
                else if i == 2 { assert(ops[i] == o3); }
                else if i == 3 { assert(ops[i] == o4); }
                else { assert(ops[i] == o5); }
            }
        },
        St::LedgerFor { .. } => {},
    }
}

pub proof fn lemma_trace_prog_no_r(sem: Sem, u: U, ly: Lay, s: State, p: usize, seg: Seq<(St, u32)>, h: usize)
    requires lay_ok(u, ly), all_no_r(u, ly, seg, h),
    ensures disc_all(u, ly, trace_prog(sem, u, ly, s, p, seg), p, h),
    decreases seg.len(),
{
    if seg.len() > 0 {
        assert(st_no_r(u, ly, seg[0].0, h));
        lemma_st_ops_no_r(u, ly, s.g, seg[0].0, h);
        lemma_trace_no_r(sem, u, ly, s, p, ops_of(u, ly, s.g, seg[0].0), h);
        let s1 = run_st(sem, u, ly, s, p, seg[0].0);
        assert(all_no_r(u, ly, seg.drop_first(), h)) by {
            assert forall|i: int| 0 <= i < seg.drop_first().len() implies st_no_r(u, ly, (#[trigger] seg.drop_first()[i]).0, h) by {
                assert(seg.drop_first()[i] == seg[i + 1]);
            }
        }
        lemma_trace_prog_no_r(sem, u, ly, s1, p, seg.drop_first(), h);
        lemma_disc_all_concat(u, ly, trace_ops(sem, u, s, p, ops_of(u, ly, s.g, seg[0].0)),
            trace_prog(sem, u, ly, s1, p, seg.drop_first()), p, h);
    } else {
        assert(trace_prog(sem, u, ly, s, p, seg) =~= Seq::<(State, Op)>::empty());
    }
}

pub proof fn lemma_derived_no_r(u: U, ly: Lay, seg: Seq<(St, u32)>, h: usize)
    requires lay_ok(u, ly), all_derived(u, ly, seg),
    ensures all_no_r(u, ly, seg, h),
{
    assert forall|i: int| 0 <= i < seg.len() implies st_no_r(u, ly, (#[trigger] seg[i]).0, h) by {
        assert(st_derived(u, ly, seg[i].0));
        match seg[i].0 {
            St::O { op } => {
                assert forall|c: int| #[trigger] is_led(u, ly, c) implies !wr(u, op, c) by {
                    match op {
                        Op::Kill { c: k } => { if covers(u, k as int, c) { assert(!is_led(u, ly, c)); } },
                        _ => {},
                    }
                }
            },
            _ => {},
        }
    }
}

pub proof fn lemma_all_no_r_concat(u: U, ly: Lay, a: Seq<(St, u32)>, b: Seq<(St, u32)>, h: usize)
    requires all_no_r(u, ly, a, h), all_no_r(u, ly, b, h),
    ensures all_no_r(u, ly, a + b, h),
{
    assert forall|i: int| 0 <= i < (a + b).len() implies st_no_r(u, ly, (#[trigger] (a + b)[i]).0, h) by {
        if i < a.len() { assert((a + b)[i] == a[i]); } else { assert((a + b)[i] == b[i - a.len()]); }
    }
}

/// The segments other than EraseLedgerFor write no ledger cell.
pub proof fn lemma_segs_no_r(u: U, ly: Lay, fr: Fr, g: i64, nkg: bool, head: bool, m: Mut)
    requires lay_ok(u, ly), fr_ok(u, ly, fr),
    ensures all_no_r(u, ly, eg_s1(head, fr), fr.head), all_no_r(u, ly, eg_s2(m, fr, g), fr.head),
        all_no_r(u, ly, eg_s3(fr, nkg), fr.head), all_no_r(u, ly, eg_s5(head, fr), fr.head),
{
    let h = fr.head;
    let a1 = eg_s1(head, fr);
    assert forall|i: int| 0 <= i < a1.len() implies st_no_r(u, ly, (#[trigger] a1[i]).0, h) by {
        if i == 0 { assert(a1[0].0 == St::O { op: Op::TStart }); }
        else { assert(a1[1].0 == St::O { op: Op::Lock { c: fr.head, mode: Mode::E, wait: true } }); }
    }
    let a2 = eg_s2(m, fr, g);
    assert forall|i: int| 0 <= i < a2.len() implies st_no_r(u, ly, (#[trigger] a2[i]).0, h) by {
        assert(a2[i].0 == St::DelG { t: eg_tables(m, fr)[i].0, g });
    }
    let a3a = eg_s3a(fr);
    assert forall|i: int| 0 <= i < a3a.len() implies st_no_r(u, ly, (#[trigger] a3a[i]).0, h) by {
        assert(a3a[0].0 == St::O { op: Op::Lock { c: fr.adjw, mode: Mode::S, wait: true } });
    }
    let a3c = eg_s3c(fr);
    assert forall|i: int| 0 <= i < a3c.len() implies st_no_r(u, ly, (#[trigger] a3c[i]).0, h) by {
        assert(a3c[0].0 == St::O { op: Op::Unlock { c: fr.adjw, mode: Mode::S, immediate: false } });
    }
    lemma_s3b_derived(u, ly, fr);
    lemma_s3d_derived(u, ly, fr, nkg);
    lemma_derived_no_r(u, ly, eg_s3b(fr), h);
    lemma_derived_no_r(u, ly, eg_s3d(fr, nkg), h);
    lemma_all_no_r_concat(u, ly, a3a, eg_s3b(fr), h);
    lemma_all_no_r_concat(u, ly, a3a + eg_s3b(fr), a3c, h);
    lemma_all_no_r_concat(u, ly, a3a + eg_s3b(fr) + a3c, eg_s3d(fr, nkg), h);
    let a5 = eg_s5(head, fr);
    assert forall|i: int| 0 <= i < a5.len() implies st_no_r(u, ly, (#[trigger] a5[i]).0, h) by {
        if head && i == 0 { assert(a5[0].0 == St::O { op: Op::Unlock { c: fr.head, mode: Mode::E, immediate: false } }); }
        else { assert(a5[i].0 == St::O { op: Op::TCommit }); }
    }
}

/// An operation EraseLedgerFor issues: a read, or a Kill of a cell of the universe.
pub open spec fn rd_or_kill(u: U, op: Op) -> bool {
    match op { Op::Order { .. } => true, Op::Get { .. } => true, Op::Kill { c } => (c as int) < u.n(), _ => false }
}

pub proof fn lemma_trace_held(sem: Sem, u: U, ly: Lay, s: State, p: usize, ops: Seq<Op>, h: usize)
    requires ready(u, s, p), excl(s.procs[p as int].locks[h as int]), level(s.procs[p as int]) > 0,
        forall|i: int| 0 <= i < ops.len() ==> rd_or_kill(u, #[trigger] ops[i]),
    ensures disc_all(u, ly, trace_ops(sem, u, s, p, ops), p, h),
    decreases ops.len(),
{
    if ops.len() > 0 {
        let op = ops[0];
        assert(rd_or_kill(u, op));
        let s1 = step(sem, u, s, p, op, false).0;
        match op {
            Op::Kill { c } => lemma_op_kill(sem, u, s, p, c),
            _ => lemma_op_read(sem, u, s, p, op),
        }
        assert forall|i: int| 0 <= i < ops.drop_first().len() implies rd_or_kill(u, #[trigger] ops.drop_first()[i]) by {
            assert(ops.drop_first()[i] == ops[i + 1]);
        }
        lemma_trace_held(sem, u, ly, s1, p, ops.drop_first(), h);
        let x = seq![(s, op)];
        assert(disc_all(u, ly, x, p, h)) by {
            assert forall|i: int| 0 <= i < x.len() implies disc(u, (#[trigger] x[i]).0, p, x[i].1, h, rset(u, ly)) by {
                assert(x[i] == (s, op));
            }
        }
        lemma_disc_all_concat(u, ly, x, trace_ops(sem, u, s1, p, ops.drop_first()), p, h);
    }
}

pub proof fn lemma_lf_ops_shape(u: U, ly: Lay, gv: Seq<Option<Val>>, root: usize, g: i64)
    requires lay_ok(u, ly), gv.len() == u.n(),
    ensures forall|i: int| 0 <= i < ops_of(u, ly, gv, St::LedgerFor { root, g }).len() ==>
        rd_or_kill(u, #[trigger] ops_of(u, ly, gv, St::LedgerFor { root, g })[i]),
{
    lemma_lf_reads_shape(u, ly, gv, 0);
    lemma_lf_kills_shape(u, ly, gv, g, 0);
    let a = seq![Op::Order { c: root }];
    let b = lf_reads(u, ly, gv, 0);
    let c = lf_kills(u, ly, gv, g, 0);
    assert forall|i: int| 0 <= i < (a + b + c).len() implies rd_or_kill(u, #[trigger] (a + b + c)[i]) by {
        if i < a.len() { assert((a + b + c)[i] == a[i]); }
        else if i < a.len() + b.len() { assert((a + b + c)[i] == b[i - a.len()]); }
        else { assert((a + b + c)[i] == c[i - a.len() - b.len()]); }
    }
}

pub proof fn lemma_lf_reads_shape(u: U, ly: Lay, gv: Seq<Option<Val>>, j: nat)
    ensures forall|i: int| 0 <= i < lf_reads(u, ly, gv, j).len() ==> rd_or_kill(u, #[trigger] lf_reads(u, ly, gv, j)[i]),
    decreases u.n() - j,
{
    if j < u.n() {
        lemma_lf_reads_shape(u, ly, gv, j + 1);
        let rest = lf_reads(u, ly, gv, j + 1);
        if is_stm(u, ly, j as int) && gv[j as int] is Some {
            let x = seq![Op::Get { c: j as usize }] + rest;
            assert forall|i: int| 0 <= i < x.len() implies rd_or_kill(u, #[trigger] x[i]) by {
                if i > 0 { assert(x[i] == rest[i - 1]); }
            }
        }
    }
}

pub proof fn lemma_lf_kills_shape(u: U, ly: Lay, gv: Seq<Option<Val>>, g: i64, j: nat)
    requires lay_ok(u, ly), gv.len() == u.n(),
    ensures forall|i: int| 0 <= i < lf_kills(u, ly, gv, g, j).len() ==> rd_or_kill(u, #[trigger] lf_kills(u, ly, gv, g, j)[i]),
    decreases u.n() - j,
{
    if j < u.n() {
        lemma_lf_kills_shape(u, ly, gv, g, j + 1);
        let rest = lf_kills(u, ly, gv, g, j + 1);
        if doomed(u, ly, gv, g, j as int) {
            lemma_decv(u, ly, gv[j as int]->Some_0);
            let x = seq![Op::Kill { c: tcell(ly, gv, j as int) }, Op::Kill { c: j as usize }] + rest;
            assert forall|i: int| 0 <= i < x.len() implies rd_or_kill(u, #[trigger] x[i]) by {
                if i > 1 { assert(x[i] == rest[i - 2]); }
            }
        }
    }
}

/// A segment of EraseLedgerFor statements run by p while it holds H exclusively inside a transaction meets `disc`.
pub proof fn lemma_lf_seg_disc(sem: Sem, u: U, ly: Lay, s: State, p: usize, seg: Seq<(St, u32)>, fr: Fr, g: i64)
    requires lay_ok(u, ly), ready(u, s, p), seg.len() == 0 || seg == lf_seg(fr, g),
        seg.len() > 0 ==> excl(s.procs[p as int].locks[fr.head as int]) && level(s.procs[p as int]) > 0,
    ensures disc_all(u, ly, trace_prog(sem, u, ly, s, p, seg), p, fr.head),
{
    if seg.len() == 0 {
        assert(trace_prog(sem, u, ly, s, p, seg) =~= Seq::<(State, Op)>::empty());
    } else {
        let x = (St::LedgerFor { root: fr.stmt_root, g }, 10256u32);
        lemma_trace_prog_one(sem, u, ly, s, p, x);
        lemma_lf_ops_shape(u, ly, s.g, fr.stmt_root, g);
        lemma_trace_held(sem, u, ly, s, p, ops_of(u, ly, s.g, x.0), fr.head);
    }
}

/// THEOREM (D-4, the head-lock plan): every operation of the reviewed EraseGraph program's run meets proofs-env2's
/// discipline `disc` for H = ^IVG.Ledger("head") and R = the ledger cells. Control ctl_f1201_erase_no_head_lock (the
/// pin, F-1201) fails it at EraseLedgerFor; control ctl_mut_cleanup_after_commit fails it after TCOMMIT.
pub proof fn theorem_eg_disc(sem: Sem, u: U, ly: Lay, fr: Fr, s0: State, p: usize, g: i64, nkg: bool)
    requires eg_pre(sem, u, ly, fr, s0, p, g, design_head()),
    ensures disc_all(u, ly, trace_prog(sem, u, ly, s0, p, eg_prog(design_head(), fr, g, nkg)), p, fr.head),
{
    let head = design_head();
    let m = active_mut();
    let h = fr.head;
    lemma_eg_points(sem, u, ly, fr, s0, p, g, nkg, head, m);
    lemma_lf_shapes(m, fr, g);
    lemma_segs_no_r(u, ly, fr, g, nkg, head, m);
    let p1 = eg_s1(head, fr);
    let p0 = eg_s0(m, fr, g);
    let p2 = eg_s2(m, fr, g);
    let p3 = eg_s3(fr, nkg);
    let p4 = eg_s4(m, fr, g);
    let p5 = eg_s5(head, fr);
    let p6 = eg_s6(m, fr, g);
    let s1 = run_prog(sem, u, ly, s0, p, p1);
    let sa = run_prog(sem, u, ly, s1, p, p0);
    let sr = run_prog(sem, u, ly, sa, p, p2);
    let s3 = run_prog(sem, u, ly, sr, p, p3);
    let s4 = run_prog(sem, u, ly, s3, p, p4);
    let s5 = run_prog(sem, u, ly, s4, p, p5);
    lemma_trace_prog_no_r(sem, u, ly, s0, p, p1, h);
    // EraseLedgerFor, wherever the program has it, runs under H inside the transaction
    assert(p0.len() > 0 ==> excl(s1.procs[p as int].locks[h as int]) && level(s1.procs[p as int]) > 0);
    lemma_lf_seg_disc(sem, u, ly, s1, p, p0, fr, g);
    lemma_trace_prog_no_r(sem, u, ly, sa, p, p2, h);
    lemma_trace_prog_no_r(sem, u, ly, sr, p, p3, h);
    assert(p4.len() > 0 ==> excl(s3.procs[p as int].locks[h as int]) && level(s3.procs[p as int]) > 0); // LOCATE ctl_f1201_erase_no_head_lock
    lemma_lf_seg_disc(sem, u, ly, s3, p, p4, fr, g);
    lemma_trace_prog_no_r(sem, u, ly, s4, p, p5, h);
    assert(p6.len() > 0 ==> excl(s5.procs[p as int].locks[h as int]) && level(s5.procs[p as int]) > 0); // LOCATE ctl_mut_cleanup_after_commit
    lemma_lf_seg_disc(sem, u, ly, s5, p, p6, fr, g);
    // the whole trace
    lemma_trace_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2 + p3 + p4 + p5, p6);
    lemma_trace_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2 + p3 + p4, p5);
    lemma_trace_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2 + p3, p4);
    lemma_trace_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2, p3);
    lemma_trace_prog_concat(sem, u, ly, s0, p, p1 + p0, p2);
    lemma_trace_prog_concat(sem, u, ly, s0, p, p1, p0);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2 + p3 + p4, p5);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2 + p3, p4);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1 + p0 + p2, p3);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1 + p0, p2);
    lemma_run_prog_concat(sem, u, ly, s0, p, p1, p0);
    let t1 = trace_prog(sem, u, ly, s0, p, p1);
    let t0 = trace_prog(sem, u, ly, s1, p, p0);
    let t2 = trace_prog(sem, u, ly, sa, p, p2);
    let t3 = trace_prog(sem, u, ly, sr, p, p3);
    let t4 = trace_prog(sem, u, ly, s3, p, p4);
    let t5 = trace_prog(sem, u, ly, s4, p, p5);
    let t6 = trace_prog(sem, u, ly, s5, p, p6);
    lemma_disc_all_concat(u, ly, t1, t0, p, h);
    lemma_disc_all_concat(u, ly, t1 + t0, t2, p, h);
    lemma_disc_all_concat(u, ly, t1 + t0 + t2, t3, p, h);
    lemma_disc_all_concat(u, ly, t1 + t0 + t2 + t3, t4, p, h);
    lemma_disc_all_concat(u, ly, t1 + t0 + t2 + t3 + t4, t5, p, h);
    lemma_disc_all_concat(u, ly, t1 + t0 + t2 + t3 + t4 + t5, t6, p, h);
}

} // verus!
