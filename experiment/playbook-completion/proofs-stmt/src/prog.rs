//! The statement language, the hand translation of Graph.KG.Eraser.EraseGraph (pin 3eaa79cf) into it, and its run in
//! the contract model (proofs-env2 `spec::step`, the validated contract `clauses::contract_sem`).
//!
//! A statement expands, in the state where it starts, into contract operations (`ops_of`) that its process then runs
//! one after another (`run_ops`). Reads that decide later writes (EraseLedgerFor's `$Order` / `$Get` walk, DropNKG's
//! `$Get`) are taken at the statement's start; the statement's own writes never change what it reads. Each program
//! element carries its source location as `file * 10000 + line`: 1 Eraser.cls, 2 Adjacency.cls, 3 TemporalIndex.cls,
//! 4 GraphIndex.cls, 5 ArnoAccel.cls, 9 the reviewed design's insertion (no source line).
//!
//! Translation (trusted, premise ST-TR; checked against the journal by harness/ and tools/replay.py):
//! - `&sql(DELETE FROM T WHERE COALESCE(graph_id, '') = COALESCE(:tName, ''))` (embedded SQL, E-1: proofs-env2's
//!   `premise_trust_e1`) is `DelG { t, g }`: the keyed DELETE of every row cell of table t whose graph is g, in cell order
//!   (premise ST-SCAN: the predicate selects exactly those rows, X-NULL's COALESCE folding NULL and '';
//!   a multi-row DELETE inside the open transaction is its rows' keyed DELETEs, each row locked to the transaction's end);
//! - `Kill ^G(...)`, `$Increment`, `Set`, `Lock +/-` are the contract operations of the same name; a timed `Lock ...:5`
//!   is a waiting lock (its expiry is the error branch, Eraser.cls:259-261);
//! - EraseLedgerFor (Eraser.cls:1117-1144) is `LedgerFor`: the `$Order` walk of `^IVG.Ledger("stmt")` (the defined
//!   statement cells, premise ST-WALK), `$Get` of each, then for each statement of graph g (`$ListGet`, X2-LIST: `dec`)
//!   the Kill of its tuple entry and of itself, in walk order.
use vstd::prelude::*;
use ivg_proofs_env2::spec::*;
use crate::lay::*;

verus! {

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum St {
    /// One contract operation.
    O { op: Op },
    /// A scoped DELETE of table t's rows of graph g.
    DelG { t: usize, g: i64 },
    /// EraseLedgerFor(g); `root` is the cell `^IVG.Ledger("stmt")`.
    LedgerFor { root: usize, g: i64 },
    /// InvalidateDerived's structural branch (Eraser.cls:1040-1045): `$Order(^NKG("$NI",""))`, DropNKG
    /// (GraphIndex.cls:24-26: `+$Get` of the version, `Kill ^NKG`, `Set` version + 1), the invalidation flag.
    DropNkg { ni: usize, ver: usize, inval: usize, root: usize },
}

/// The cells and tables EraseGraph(g) names (one graph): tables, lock names, the graph's derived globals.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Fr {
    pub t_labels: usize, pub t_props: usize, pub t_docs: usize, pub t_nemb: usize, pub t_nembo: usize,
    pub t_reif: usize, pub t_eemb: usize, pub t_edges: usize, pub t_nodes: usize,
    /// `^IVG.AdjW(key)`, `^IVG.Ledger("head")`, `^IVG.Ledger("stmt")`.
    pub adjw: usize, pub head: usize, pub stmt_root: usize,
    /// RemoveGraph (Adjacency.cls:435-444).
    pub kg_out: usize, pub kg_in: usize, pub kg_gen: usize, pub kg_degc: usize, pub kg_degw: usize,
    pub adjnolock: usize, pub kg_deg: usize, pub kg_degp: usize, pub kg_ver: usize,
    /// TemporalIndex.EraseGraph (TemporalIndex.cls:370-375).
    pub tout: usize, pub tin: usize, pub bucket: usize, pub tagg: usize, pub edgeprop: usize, pub tlast: usize,
    /// Eraser.cls:239-249.
    pub kg_prop: usize, pub kg_label: usize, pub deg2p: usize, pub deg2p_exact: usize, pub gmode: usize, pub algo_g: usize,
    /// InvalidateDerived (Eraser.cls:1040-1052), BumpVersion (ArnoAccel.cls:301-302).
    pub nkg_ni: usize, pub nkg_ver: usize, pub nkg_inval: usize, pub nkg: usize, pub algo_all: usize,
}

/// Statement mutants (controls): the reviewed / as-built program is `Mut::None`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Mut { None, DropEdges, DropLedger, LedgerFirst, AfterCommit }

// ------------------------------------------------------------------------------------------------ expansion

/// Keyed DELETEs of the rows of table t in graph g, cells j.. in order.
pub open spec fn delg_ops(u: U, ly: Lay, t: usize, g: i64, j: nat) -> Seq<Op>
    decreases u.n() - j
{
    if j >= u.n() {
        Seq::empty()
    } else if u.is_row[j as int] && u.table[j as int] == t && ly.gr[j as int] == g as int {
        seq![Op::Delete { r: j as usize }] + delg_ops(u, ly, t, g, j + 1)
    } else {
        delg_ops(u, ly, t, g, j + 1)
    }
}

/// The walk's `$Get` of every defined statement cell, cells j.. in order (Eraser.cls:1121-1125).
pub open spec fn lf_reads(u: U, ly: Lay, gv: Seq<Option<Val>>, j: nat) -> Seq<Op>
    decreases u.n() - j
{
    if j >= u.n() {
        Seq::empty()
    } else if is_stm(u, ly, j as int) && gv[j as int] is Some {
        seq![Op::Get { c: j as usize }] + lf_reads(u, ly, gv, j + 1)
    } else {
        lf_reads(u, ly, gv, j + 1)
    }
}

/// Statement j belongs to graph g (Eraser.cls:1124-1130: defined, not "", `ForName($ListGet(tRow, 4)) = pName`).
pub open spec fn doomed(u: U, ly: Lay, gv: Seq<Option<Val>>, g: i64, j: int) -> bool {
    &&& is_stm(u, ly, j)
    &&& gv[j] is Some
    &&& gv[j]->Some_0 != Val::Empty
    &&& decv(ly, gv[j]->Some_0) is Some
    &&& odg(decv(ly, gv[j]->Some_0)) == g as int
}

/// The tuple cell statement j names.
pub open spec fn tcell(ly: Lay, gv: Seq<Option<Val>>, j: int) -> usize { odc(decv(ly, gv[j]->Some_0)) }

/// The kills of Eraser.cls:1139-1140 for every doomed statement, cells j.. in order.
pub open spec fn lf_kills(u: U, ly: Lay, gv: Seq<Option<Val>>, g: i64, j: nat) -> Seq<Op>
    decreases u.n() - j
{
    if j >= u.n() {
        Seq::empty()
    } else if doomed(u, ly, gv, g, j as int) {
        seq![Op::Kill { c: tcell(ly, gv, j as int) }, Op::Kill { c: j as usize }] + lf_kills(u, ly, gv, g, j + 1)
    } else {
        lf_kills(u, ly, gv, g, j + 1)
    }
}

/// `tVer + 1` of DropNKG (GraphIndex.cls:24-26), with `+$Get` the contract's numeric reading.
pub open spec fn nkg_next(u: U, v: Option<Val>) -> Val {
    if num_of(u, v) < i64::MAX { Val::Num((num_of(u, v) + 1) as i64) } else { Val::Num(num_of(u, v)) }
}

pub open spec fn nkg_ops(u: U, gv: Seq<Option<Val>>, ni: usize, ver: usize, inval: usize, root: usize) -> Seq<Op> {
    seq![Op::Order { c: ni }, Op::Get { c: ver }, Op::Kill { c: root }, Op::Set { c: ver, v: nkg_next(u, gv[ver as int]) }]
        + if has_kids(u, gv, ni as int) { seq![Op::Set { c: inval, v: Val::Num(1) }] } else { Seq::empty() }
}

pub open spec fn ops_of(u: U, ly: Lay, gv: Seq<Option<Val>>, st: St) -> Seq<Op> {
    match st {
        St::O { op } => seq![op],
        St::DelG { t, g } => delg_ops(u, ly, t, g, 0),
        St::LedgerFor { root, g } => seq![Op::Order { c: root }] + lf_reads(u, ly, gv, 0) + lf_kills(u, ly, gv, g, 0),
        St::DropNkg { ni, ver, inval, root } => nkg_ops(u, gv, ni, ver, inval, root),
    }
}

// ------------------------------------------------------------------------------------------------ runs (one process)

pub open spec fn run_ops(sem: Sem, u: U, s: State, p: usize, ops: Seq<Op>) -> State
    decreases ops.len()
{
    if ops.len() == 0 { s } else { run_ops(sem, u, step(sem, u, s, p, ops[0], false).0, p, ops.drop_first()) }
}

pub open spec fn run_st(sem: Sem, u: U, ly: Lay, s: State, p: usize, st: St) -> State {
    run_ops(sem, u, s, p, ops_of(u, ly, s.g, st))
}

pub open spec fn run_prog(sem: Sem, u: U, ly: Lay, s: State, p: usize, prog: Seq<(St, u32)>) -> State
    decreases prog.len()
{
    if prog.len() == 0 { s } else { run_prog(sem, u, ly, run_st(sem, u, ly, s, p, prog[0].0), p, prog.drop_first()) }
}

/// The operations of a run with the state each starts from (for the discipline `disc`).
pub open spec fn trace_ops(sem: Sem, u: U, s: State, p: usize, ops: Seq<Op>) -> Seq<(State, Op)>
    decreases ops.len()
{
    if ops.len() == 0 {
        Seq::empty()
    } else {
        seq![(s, ops[0])] + trace_ops(sem, u, step(sem, u, s, p, ops[0], false).0, p, ops.drop_first())
    }
}

pub open spec fn trace_prog(sem: Sem, u: U, ly: Lay, s: State, p: usize, prog: Seq<(St, u32)>) -> Seq<(State, Op)>
    decreases prog.len()
{
    if prog.len() == 0 {
        Seq::empty()
    } else {
        trace_ops(sem, u, s, p, ops_of(u, ly, s.g, prog[0].0))
            + trace_prog(sem, u, ly, run_st(sem, u, ly, s, p, prog[0].0), p, prog.drop_first())
    }
}

// ------------------------------------------------------------------------------------------------ EraseGraph

/// The control features: which mutant is compiled, and whether the design takes the head lock.
pub open spec fn active_mut() -> Mut {
    if cfg!(feature = "ctl_mut_drop_edges_delete") { Mut::DropEdges }
    else if cfg!(feature = "ctl_mut_drop_ledger_cleanup") { Mut::DropLedger }
    else if cfg!(feature = "ctl_mut_ledger_first") { Mut::LedgerFirst }
    else if cfg!(feature = "ctl_mut_cleanup_after_commit") { Mut::AfterCommit }
    else { Mut::None }
}

/// R11-7 (reviewed design, HD-1201): EraseGraph holds the ledger head lock from before its row DELETEs to its end.
/// The pin does not (F-1201): control `ctl_f1201_erase_no_head_lock` puts the as-built program back.
pub open spec fn design_head() -> bool { !cfg!(feature = "ctl_f1201_erase_no_head_lock") }

/// S1: TSTART (Eraser.cls:56) and, reviewed, `Lock +^IVG.Ledger("head")`.
pub open spec fn eg_s1(head: bool, fr: Fr) -> Seq<(St, u32)> {
    if head {
        seq![(St::O { op: Op::TStart }, 10056u32), (St::O { op: Op::Lock { c: fr.head, mode: Mode::E, wait: true } }, 90001u32)]
    } else {
        seq![(St::O { op: Op::TStart }, 10056u32)]
    }
}

pub open spec fn lf_seg(fr: Fr, g: i64) -> Seq<(St, u32)> { seq![(St::LedgerFor { root: fr.stmt_root, g }, 10256u32)] }

/// S0: nothing between TSTART and the row DELETEs (mutant LedgerFirst: EraseLedgerFor there).
pub open spec fn eg_s0(m: Mut, fr: Fr, g: i64) -> Seq<(St, u32)> {
    if m == Mut::LedgerFirst { lf_seg(fr, g) } else { Seq::empty() }
}

/// The scoped row DELETEs in program order (table, source line): Eraser.cls:130, 134, 145, 153, 157, 186, 198, 217, 222.
/// Not in the program (exact open obligations, PROOFS.md): the routed tables' DELETEs (167-178) and the FHIR side tables
/// (183, 1151-1180), both X-DDL.
pub open spec fn eg_tables(m: Mut, fr: Fr) -> Seq<(usize, u32)> {
    if m == Mut::DropEdges {
        seq![(fr.t_labels, 10130u32), (fr.t_props, 10134u32), (fr.t_docs, 10145u32), (fr.t_nemb, 10153u32),
             (fr.t_nembo, 10157u32), (fr.t_reif, 10186u32), (fr.t_eemb, 10198u32), (fr.t_nodes, 10222u32)]
    } else {
        seq![(fr.t_labels, 10130u32), (fr.t_props, 10134u32), (fr.t_docs, 10145u32), (fr.t_nemb, 10153u32),
             (fr.t_nembo, 10157u32), (fr.t_reif, 10186u32), (fr.t_eemb, 10198u32), (fr.t_edges, 10217u32),
             (fr.t_nodes, 10222u32)]
    }
}

pub open spec fn delg_seg(tabs: Seq<(usize, u32)>, g: i64) -> Seq<(St, u32)> {
    tabs.map_values(|x: (usize, u32)| (St::DelG { t: x.0, g }, x.1))
}

/// S2: the row DELETEs.
pub open spec fn eg_s2(m: Mut, fr: Fr, g: i64) -> Seq<(St, u32)> { delg_seg(eg_tables(m, fr), g) }

/// S3a / S3c: RemoveGraph's lock (Adjacency.cls:431, 445).
pub open spec fn eg_s3a(fr: Fr) -> Seq<(St, u32)> {
    seq![(St::O { op: Op::Lock { c: fr.adjw, mode: Mode::S, wait: true } }, 20431u32)]
}

pub open spec fn eg_s3c(fr: Fr) -> Seq<(St, u32)> {
    seq![(St::O { op: Op::Unlock { c: fr.adjw, mode: Mode::S, immediate: false } }, 20445u32)]
}

/// S3b: RemoveGraph's kills and version step (Adjacency.cls:435-444).
pub open spec fn eg_s3b(fr: Fr) -> Seq<(St, u32)> {
    seq![
        (St::O { op: Op::Kill { c: fr.kg_out } }, 20435u32),
        (St::O { op: Op::Kill { c: fr.kg_in } }, 20436u32),
        (St::O { op: Op::Kill { c: fr.kg_gen } }, 20437u32),
        (St::O { op: Op::Kill { c: fr.kg_degc } }, 20438u32),
        (St::O { op: Op::Kill { c: fr.kg_degw } }, 20439u32),
        (St::O { op: Op::Kill { c: fr.adjnolock } }, 20440u32),
        (St::O { op: Op::Kill { c: fr.kg_deg } }, 20442u32),
        (St::O { op: Op::Kill { c: fr.kg_degp } }, 20443u32),
        (St::O { op: Op::Incr { c: fr.kg_ver } }, 20444u32)
    ]
}

/// S3d: TemporalIndex.EraseGraph (TemporalIndex.cls:370-375), Eraser.cls:239-249, InvalidateDerived (1040-1052) with
/// BumpVersion (ArnoAccel.cls:301-302). `nkg` is the value of Eraser.cls:215 (reads of ^NKG and ^KG("out") outside the
/// replayed state; a free parameter of every theorem).
pub open spec fn eg_ti(fr: Fr) -> Seq<(St, u32)> {
    seq![
        (St::O { op: Op::Kill { c: fr.tout } }, 30370u32),
        (St::O { op: Op::Kill { c: fr.tin } }, 30371u32),
        (St::O { op: Op::Kill { c: fr.bucket } }, 30372u32),
        (St::O { op: Op::Kill { c: fr.tagg } }, 30373u32),
        (St::O { op: Op::Kill { c: fr.edgeprop } }, 30374u32),
        (St::O { op: Op::Kill { c: fr.tlast } }, 30375u32)
    ]
}

pub open spec fn eg_er(fr: Fr) -> Seq<(St, u32)> {
    seq![
        (St::O { op: Op::Kill { c: fr.kg_prop } }, 10239u32),
        (St::O { op: Op::Kill { c: fr.kg_label } }, 10240u32),
        (St::O { op: Op::Kill { c: fr.deg2p } }, 10241u32),
        (St::O { op: Op::Kill { c: fr.deg2p_exact } }, 10242u32),
        (St::O { op: Op::Kill { c: fr.gmode } }, 10244u32),
        (St::O { op: Op::Kill { c: fr.algo_g } }, 10249u32)
    ]
}

pub open spec fn eg_nkg(fr: Fr, nkg: bool) -> Seq<(St, u32)> {
    if nkg {
        seq![(St::DropNkg { ni: fr.nkg_ni, ver: fr.nkg_ver, inval: fr.nkg_inval, root: fr.nkg }, 11041u32)]
    } else {
        Seq::empty()
    }
}

pub open spec fn eg_bump(fr: Fr) -> Seq<(St, u32)> {
    seq![
        (St::O { op: Op::Incr { c: fr.kg_ver } }, 50301u32),
        (St::O { op: Op::Incr { c: fr.nkg_ver } }, 50302u32),
        (St::O { op: Op::Kill { c: fr.algo_all } }, 11052u32)
    ]
}

pub open spec fn eg_s3d(fr: Fr, nkg: bool) -> Seq<(St, u32)> { eg_ti(fr) + eg_er(fr) + eg_nkg(fr, nkg) + eg_bump(fr) }

pub open spec fn eg_s3(fr: Fr, nkg: bool) -> Seq<(St, u32)> { eg_s3a(fr) + eg_s3b(fr) + eg_s3c(fr) + eg_s3d(fr, nkg) }

/// S4: EraseLedgerFor (Eraser.cls:256), inside the transaction.
pub open spec fn eg_s4(m: Mut, fr: Fr, g: i64) -> Seq<(St, u32)> {
    if m == Mut::DropLedger || m == Mut::LedgerFirst || m == Mut::AfterCommit { Seq::empty() } else { lf_seg(fr, g) }
}

/// S5: reviewed, `Lock -^IVG.Ledger("head")` (deferred to the transaction's end, as Ledger.cls:404); TCOMMIT
/// (Eraser.cls:258).
pub open spec fn eg_s5(head: bool, fr: Fr) -> Seq<(St, u32)> {
    if head {
        seq![(St::O { op: Op::Unlock { c: fr.head, mode: Mode::E, immediate: false } }, 90002u32), (St::O { op: Op::TCommit }, 10258u32)]
    } else {
        seq![(St::O { op: Op::TCommit }, 10258u32)]
    }
}

/// S6: nothing after TCOMMIT in the program (the DDL of 282-299 is X-DDL, open; mutant AfterCommit: EraseLedgerFor).
pub open spec fn eg_s6(m: Mut, fr: Fr, g: i64) -> Seq<(St, u32)> {
    if m == Mut::AfterCommit { lf_seg(fr, g) } else { Seq::empty() }
}

/// The program of EraseGraph(g) with mutant m; `head`: the reviewed design's head lock.
pub open spec fn eg_prog_m(m: Mut, head: bool, fr: Fr, g: i64, nkg: bool) -> Seq<(St, u32)> {
    eg_s1(head, fr) + eg_s0(m, fr, g) + eg_s2(m, fr, g) + eg_s3(fr, nkg) + eg_s4(m, fr, g) + eg_s5(head, fr) + eg_s6(m, fr, g)
}

/// The program this build verifies (Mut::None in the baseline).
pub open spec fn eg_prog(head: bool, fr: Fr, g: i64, nkg: bool) -> Seq<(St, u32)> { eg_prog_m(active_mut(), head, fr, g, nkg) }

} // verus!
