//! Module 09, L2 part 2: a native read at pin 3eaa79cf over the stored layout (the relationship rows into the hub, the
//! label rows, ^KG("label"), the two functional indexes' declarations, the SQL grants) and the read paths: the
//! executor's Run (iris_src/src/Graph/KG/Cypher/Exec.cls:32-72), its used-relationship set (Exec.cls:1236-1250), the
//! engine's gate (iris_vector_graph/cypher/native_plan.py:524-539) and shadow mode (query.py:2063-2077, 2146-2152,
//! 2226-2249); refinement of `nread_l1` for every step, the invariant, and the controls F-0902, F-0908, HD-0902, F-0906.
//!
//! Layout and steps: `rels` (rdf_edges rows into the hub; `snap`: the image a writer's open transaction would roll back
//! to, in another process), `labs` (rdf_labels rows), `kg` (^KG("label")), `idx_e`/`idx_l` (idx_edges_adj and
//! idx_labels_adj functional; any combination at the start: ensure_adjacency_index declares the edge index first and
//! the label index second, schema.py:863-899, so a failure between them leaves edge-only), `held` (users holding SELECT
//! on the four tables), `chk` (the executor's per-process check cache, reviewed design only), `crc` ($ZCRC($LB(src, p,
//! dst, key), 7) of each relationship: any assignment, collisions included; b-09-f0902-collision constructs one).
//! `LWrite`: the label row, and ^KG("label") from the label index when it is functional, or by the engine itself when
//! the edge index is not (engine.py:703-724). `Run`/`RunLabels`: the executor answers a plan; `Decline`: the native
//! path declines (the engine answers by SQL); `ShadowRun`: native (`nres`: its answer, or None when it raised) then
//! SQL, compared; `SqlRead`; the writer's TBegin/TAdd/TCommit/TRollback; Grant/Revoke.
//!
//! **Reviewed design**: the interpreter keeps used relationships by exact identity (F-0902 remedy; the compiled walk
//! does, Gen.cls:410-433); Run checks SELECT for (process, user), cached (FR-011 literal, HD-0901 alternative (c));
//! shadow mode raises when the native path raises (HD-0902 working answer); the gate requires both functional indexes
//! (F-0906 remedy). **As built**: checksums (`control_f0902_crc_identity`), no check in Run
//! (`control_f0908_run_unchecked`; the engine's check, engine.py:559-586, guards only the engine's own calls), a native
//! exception yields None and the SQL rows are returned uncompared (`control_hd0902_shadow_swallows_native_error`), the
//! gate opens on the edge index alone (`control_f0906_gate_edge_index_only`).
//!
//! HD-0903 (no control): both paths read the current rows, uncommitted ones included (IRIS reads uncommitted by
//! default, P-0002; the native read runs in another process than the writer's, F-0909): the pin satisfies the working
//! answer at model level (`theorem_native_read_sees_the_open_transaction`). Premises: P-R1 each read is one step (a
//! walk reads the stores at moments spread over it, HD-0903; part of one transaction may be seen, which the working
//! answer allows); P-R2 an out-of-band index drop under running engines is a premise violation (HD-0901 working
//! answer (2)), not a step; P-R3 caller identity per process is what the Native API session's user is.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::nread_l1::*;

verus! {

pub struct NR2 {
    pub rels: Set<int>,
    pub snap: Option<Set<int>>,
    pub held: Set<int>,
    pub chk: Set<(int, int)>,
    pub labs: Set<(int, int)>,
    pub kg: Set<(int, int)>,
    pub idx_e: bool,
    pub idx_l: bool,
    pub crc: Map<int, int>,
}

pub enum NRL2 {
    TBegin,
    TAdd { e: int },
    TCommit,
    TRollback,
    Grant { u: int },
    Revoke { u: int },
    LWrite { n: int, l: int },
    Run { p: int, u: int, ans: ISet<(int, int)> },
    RunLabels { p: int, u: int, ans: Set<(int, int)> },
    Decline { p: int, u: int },
    ShadowRun { p: int, u: int, nres: Option<ISet<(int, int)>>, ans: Option<ISet<(int, int)>>, compared: bool },
    SqlRead { u: int, ans: Option<ISet<(int, int)>> },
}

pub open spec fn f0902() -> bool { cfg!(feature = "control_f0902_crc_identity") }
pub open spec fn f0908() -> bool { cfg!(feature = "control_f0908_run_unchecked") }
pub open spec fn hd0902() -> bool { cfg!(feature = "control_hd0902_shadow_swallows_native_error") }
pub open spec fn f0906() -> bool { cfg!(feature = "control_f0906_gate_edge_index_only") }

pub open spec fn crcof(s: NR2, e: int) -> int { if s.crc.contains_key(e) { s.crc[e] } else { e } }
pub open spec fn absr(s: NR2) -> NR1 { NR1 { rels: s.rels, snap: s.snap, held: s.held, chk: s.chk, labs: s.labs } }
/// The interpreter's answer: as built, a neighbour is skipped when its checksum is in the used string.
pub open spec fn interp2(s: NR2) -> ISet<(int, int)> {
    if f0902() { ISet::new(|x: (int, int)| s.rels.contains(x.0) && s.rels.contains(x.1) && crcof(s, x.0) != crcof(s, x.1)) }
    else { pairs(s.rels) }
}
/// Run's own check (reviewed: SELECT for (p, u), cached; as built: none).
pub open spec fn run_ok(s: NR2, p: int, u: int) -> bool { f0908() || authorized(absr(s), p, u) }
pub open spec fn after_run(s: NR2, p: int, u: int) -> NR2 { if f0908() { s } else { NR2 { chk: s.chk.insert((p, u)), ..s } } }
/// The engine's gate on the indexes (FR-003, NAT-I1).
pub open spec fn gate(s: NR2) -> bool { s.idx_e && (f0906() || s.idx_l) }
/// Shadow mode's outcome for a native result `nres` (None: native raised) and the SQL path's answer.
pub open spec fn shadow_ok(s: NR2, u: int, nres: Option<ISet<(int, int)>>, ans: Option<ISet<(int, int)>>, compared: bool) -> bool {
    let sql = pairs(s.rels);
    if nres is None && hd0902() {
        !compared && ans == (if s.held.contains(u) { Some(sql) } else { None })
    } else {
        compared == (nres is Some) && ans == (if nres == Some(sql) && s.held.contains(u) { Some(sql) } else { None })
    }
}

pub open spec fn init2(s: NR2) -> bool {
    s.rels == Set::<int>::empty() && s.snap is None && s.chk == Set::<(int, int)>::empty() && s.labs == Set::<(int, int)>::empty()
        && s.kg == Set::<(int, int)>::empty()
}

pub open spec fn step2(s: NR2, l: NRL2, t: NR2) -> bool {
    match l {
        NRL2::TBegin => s.snap is None && t == (NR2 { snap: Some(s.rels), ..s }),
        NRL2::TAdd { e } => s.snap is Some && t == (NR2 { rels: s.rels.insert(e), ..s }),
        NRL2::TCommit => s.snap is Some && t == (NR2 { snap: None, ..s }),
        NRL2::TRollback => s.snap is Some && t == (NR2 { rels: s.snap->Some_0, snap: None, ..s }),
        NRL2::Grant { u } => t == (NR2 { held: s.held.insert(u), ..s }),
        NRL2::Revoke { u } => t == (NR2 { held: s.held.remove(u), ..s }),
        NRL2::LWrite { n, l } =>
            t == (NR2 { labs: s.labs.insert((n, l)), kg: if s.idx_l || !s.idx_e { s.kg.insert((n, l)) } else { s.kg }, ..s }),
        NRL2::Run { p, u, ans } => run_ok(s, p, u) && ans == interp2(s) && t == after_run(s, p, u),
        NRL2::RunLabels { p, u, ans } => gate(s) && run_ok(s, p, u) && ans == s.kg && t == after_run(s, p, u),
        NRL2::Decline { p, u } => t == s,
        NRL2::ShadowRun { p, u, nres, ans, compared } =>
            (nres is None || nres == Some(interp2(s))) && shadow_ok(s, u, nres, ans, compared) && t == s,
        NRL2::SqlRead { u, ans } => t == s && ans == (if s.held.contains(u) { Some(pairs(s.rels)) } else { None }),
    }
}

pub open spec fn labr(l: NRL2) -> Option<NRL1> {
    match l {
        NRL2::TBegin => Some(NRL1::TBegin),
        NRL2::TAdd { e } => Some(NRL1::TAdd { e }),
        NRL2::TCommit => Some(NRL1::TCommit),
        NRL2::TRollback => Some(NRL1::TRollback),
        NRL2::Grant { u } => Some(NRL1::Grant { u }),
        NRL2::Revoke { u } => Some(NRL1::Revoke { u }),
        NRL2::LWrite { n, l } => Some(NRL1::LWrite { n, l }),
        NRL2::Run { p, u, ans } => Some(NRL1::NRead { p, u, ans }),
        NRL2::RunLabels { p, u, ans } => Some(NRL1::NLabels { p, u, ans }),
        NRL2::Decline { p, u } => Some(NRL1::NRefuse { p, u }),
        NRL2::ShadowRun { p, u, nres, ans, compared } => Some(NRL1::Shadow { p, u, ans, compared }),
        NRL2::SqlRead { u, ans } => Some(NRL1::SqlRead { u, ans }),
    }
}

/// ^KG("label") holds exactly the label rows wherever a label write keeps it (the label index is functional, or the
/// engine writes it because the edge index is not).
pub open spec fn inv09r(s: NR2) -> bool { (s.idx_l || !s.idx_e) ==> s.kg == s.labs }

pub struct NrL2;
impl Contract for NrL2 {
    type S = NR2;
    type L = NRL2;
    open spec fn init(s: NR2) -> bool { init2(s) }
    open spec fn next(s: NR2, l: NRL2, t: NR2) -> bool { inv09r(s) && step2(s, l, t) }
}
pub struct NrRaw;
impl Contract for NrRaw {
    type S = NR2;
    type L = NRL2;
    open spec fn init(s: NR2) -> bool { init2(s) }
    open spec fn next(s: NR2, l: NRL2, t: NR2) -> bool { step2(s, l, t) }
}

proof fn lemma_run(s: NR2, p: int, u: int, ans: ISet<(int, int)>, t: NR2)
    requires inv09r(s), step2(s, NRL2::Run { p, u, ans }, t),
    ensures inv09r(t), step_or_stutter::<NrL1>(absr(s), labr(NRL2::Run { p, u, ans }), absr(t)),
{
    // Run checks SELECT for (process, user), cached (FR-011) (control F-0908 fails here)
    assert(authorized(absr(s), p, u));
    // two different relationships are never taken as one (NAT-B1.11) (control F-0902 fails here)
    assert(ans == pairs(s.rels));
}

proof fn lemma_runlabels(s: NR2, p: int, u: int, ans: Set<(int, int)>, t: NR2)
    requires inv09r(s), step2(s, NRL2::RunLabels { p, u, ans }, t),
    ensures inv09r(t), step_or_stutter::<NrL1>(absr(s), labr(NRL2::RunLabels { p, u, ans }), absr(t)),
{
    // (control F-0908 fails here too)
    assert(authorized(absr(s), p, u));
    // the gate opened only where ^KG("label") is kept: the native labels are the rows (control F-0906 fails here)
    assert(ans == s.labs);
}

proof fn lemma_shadow(s: NR2, p: int, u: int, nres: Option<ISet<(int, int)>>, ans: Option<ISet<(int, int)>>, compared: bool, t: NR2)
    requires inv09r(s), step2(s, NRL2::ShadowRun { p, u, nres, ans, compared }, t),
    ensures inv09r(t), step_or_stutter::<NrL1>(absr(s), labr(NRL2::ShadowRun { p, u, nres, ans, compared }), absr(t)),
{
    // a shadow answer is returned only after native answered and agreed (control HD-0902 fails here)
    assert(ans is Some ==> compared);
}

proof fn lemma_step(s: NR2, l: NRL2, t: NR2)
    requires inv09r(s), step2(s, l, t),
    ensures inv09r(t), step_or_stutter::<NrL1>(absr(s), labr(l), absr(t)),
{
    match l {
        NRL2::Run { p, u, ans } => lemma_run(s, p, u, ans, t),
        NRL2::RunLabels { p, u, ans } => lemma_runlabels(s, p, u, ans, t),
        NRL2::ShadowRun { p, u, nres, ans, compared } => lemma_shadow(s, p, u, nres, ans, compared, t),
        _ => {}
    }
}

impl Refines<NrL1> for NrL2 {
    open spec fn abs(s: NR2) -> NR1 { absr(s) }
    open spec fn lab(l: NRL2) -> Option<NRL1> { labr(l) }
    proof fn init_refines(s: NR2) {}
    proof fn step_refines(s: NR2, l: NRL2, t: NR2) { lemma_step(s, l, t); }
}

impl SafeContract for NrL2 {
    open spec fn inv(s: NR2) -> bool { inv09r(s) }
    proof fn init_safe(s: NR2) {}
    proof fn step_safe(s: NR2, l: NRL2, t: NR2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<NR2>, labels: Seq<NRL2>, k: int)
    requires execution::<NrRaw>(states, labels), 0 <= k < states.len(),
    ensures inv09r(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state (any grants, any index declarations, any
/// checksums) keeps the L2 invariant, and its abstraction is an L1 execution.
pub proof fn theorem_raw_executions_refine(states: Seq<NR2>, labels: Seq<NRL2>)
    requires execution::<NrRaw>(states, labels),
    ensures
        execution::<NrL2>(states, labels),
        abstract_execution::<NrL1>(Seq::new(states.len(), |i: int| absr(states[i])),
                                   Seq::new(labels.len(), |i: int| labr(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv09r(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv09r(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<NrL2>(states, labels));
    trace_refines::<NrL2, NrL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absr(states[i])) =~= Seq::new(states.len(), |i: int| <NrL2 as Refines<NrL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labr(labels[i])) =~= Seq::new(labels.len(), |i: int| <NrL2 as Refines<NrL1>>::lab(labels[i])));
}

/// HD-0903 at model level (the pin's behaviour, every design): while a writer's transaction is open, a native read and
/// a SQL-path read from the same state answer the same rows, the uncommitted ones included.
pub proof fn theorem_native_read_sees_the_open_transaction(s: NR2, p: int, u: int, x: ISet<(int, int)>, t: NR2,
                                                           y: ISet<(int, int)>)
    requires inv09r(s), s.snap is Some, step2(s, NRL2::Run { p, u, ans: x }, t), step2(s, NRL2::SqlRead { u, ans: Some(y) }, s),
    ensures x == y, x == pairs(s.rels),
{
    lemma_run(s, p, u, x, t);
}

} // verus!
