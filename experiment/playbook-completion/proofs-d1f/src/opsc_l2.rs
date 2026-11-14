//! Module 17, L2: the status report, the capability paths and the package's dependency metadata at pin 3eaa79cf;
//! refinement of `opsc_l1` for every step, the invariant, and the controls F-1713 and F-C1706.
//!
//! Parts of the status report (codes): 0..7 the eight names of STATUS_PARTS (graph, acceleration, sync, vector_index,
//! fulltext_index, ivf_index, plaid_index, ledger; status.py:11), 8 "adjacency" (admin.py:551), 9 "routines"
//! (admin.py:752-753). The report marks unknown each part whose probe failed or did not run (status.py:155-157).
//!
//! **Reviewed design**:
//! - R17-6 (F-1713 remedy): STATUS_PARTS names all ten. As built it lacks adjacency and routines: control F-1713
//!   (c17-offline).
//! - R17-7 (F-C1706 remedy): the package asks for a driver floor the product works with (at least 5.4.0, the version
//!   CI tests) and the lock resolves to one. As built pyproject.toml:42 asks intersystems-iris>=1.0.0 and uv.lock
//!   (:1358-1371) installs intersystems-irispython 5.3.2, under which a duplicate INSERT surfaces as '<LIST ERROR>',
//!   which is_duplicate (_write_txn.py:46-49) does not recognise, so write_nodes raises and writes nothing: control
//!   F-C1706 (val-driver532-1 against val-driver540-1).
//! As built and kept (HD-1703 working answer (b)): store.capabilities() is the static catalogue _FULL_CAPABILITIES
//! (iris_sql_store.py:2991-2992); engine.capabilities probes the namespace; routing reads the catalogue and falls back
//! to the same class on a store error, so a call needing an undeployed class raises.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::opsc_l1::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

pub struct O2 { pub deployed: Set<nat>, pub drv: Option<nat>, pub rows: nat }

pub enum OL2 {
    Deploy { cap: nat },
    /// status(): `failed` the parts whose probe failed or did not run
    Report { failed: Set<nat>, unknown: Set<nat>, parts: Set<nat> },
    Claim { cap: nat, avail: bool },
    Catalogue { cap: nat, supported: bool },
    /// the engine routes by the catalogue (`via_store`) and falls back to the same class on a store error
    Route { cap: nat, via_store: bool, ok: bool },
    /// `locked`: uv sync installs the lock's version; else a fresh resolution installs any admitted version
    Install { v: nat, locked: bool },
    WriteNodes { dup: bool, ok: bool },
}

pub open spec fn f1713() -> bool { cfg!(feature = "control_f1713_status_parts_short") }
pub open spec fn fc1706() -> bool { cfg!(feature = "control_fc1706_driver_floor") }

pub open spec fn all_parts() -> Set<nat> { Set::<nat>::range(0, 10) }
pub open spec fn status_parts() -> Set<nat> { if f1713() { Set::<nat>::range(0, 8) } else { Set::<nat>::range(0, 10) } }
pub open spec fn floor() -> nat { if fc1706() { 100 } else { 540 } }
pub open spec fn lock_v() -> nat { if fc1706() { 532 } else { 540 } }
/// Premise P-D1 (as drv_ok): is_duplicate recognises the driver's duplicate-row error from 5.4.0 on.
pub open spec fn recognised(v: nat) -> bool { v >= 540 }

pub open spec fn init2(s: O2) -> bool { s.drv is None && s.rows == 0 }

pub open spec fn step2(s: O2, l: OL2, t: O2) -> bool {
    match l {
        OL2::Deploy { cap } => t == O2 { deployed: s.deployed.insert(cap), ..s },
        OL2::Report { failed, unknown, parts } =>
            failed.subset_of(all_parts()) && unknown == failed && parts == status_parts() && t == s,
        OL2::Claim { cap, avail } => avail == s.deployed.contains(cap) && t == s,
        OL2::Catalogue { cap, supported } => supported == (cap < ncaps()) && t == s,
        OL2::Route { cap, via_store, ok } => via_store == (cap < ncaps()) && ok == s.deployed.contains(cap) && t == s,
        OL2::Install { v, locked } => (if locked { v == lock_v() } else { v >= floor() }) && t == O2 { drv: Some(v), ..s },
        OL2::WriteNodes { dup, ok } =>
            s.drv is Some && if dup { ok == recognised(s.drv->Some_0) && t == s } else { ok && t == O2 { rows: s.rows + 1, ..s } },
    }
}

pub open spec fn abso(s: O2) -> O1 { O1 { deployed: s.deployed, drv: s.drv, rows: s.rows } }

pub open spec fn labo(l: OL2) -> Option<OL1> {
    match l {
        OL2::Deploy { cap } => Some(OL1::Deploy { cap }),
        OL2::Report { failed, unknown, parts } => Some(OL1::Report { unknown, parts }),
        OL2::Claim { cap, avail } => Some(OL1::Claim { cap, avail }),
        OL2::Catalogue { cap, supported } => Some(OL1::Catalogue { cap, supported }),
        OL2::Route { cap, via_store, ok } => Some(OL1::Call { cap, ok }),
        OL2::Install { v, locked } => Some(OL1::Install { v }),
        OL2::WriteNodes { dup, ok } => Some(OL1::WriteNodes { dup, ok }),
    }
}

pub open spec fn inv17o(s: O2) -> bool { inv1(abso(s)) }

pub struct OpscL2;

impl Contract for OpscL2 {
    type S = O2;
    type L = OL2;
    open spec fn init(s: O2) -> bool { init2(s) }
    open spec fn next(s: O2, l: OL2, t: O2) -> bool { inv17o(s) && step2(s, l, t) }
}

pub struct OpscRaw;

impl Contract for OpscRaw {
    type S = O2;
    type L = OL2;
    open spec fn init(s: O2) -> bool { init2(s) }
    open spec fn next(s: O2, l: OL2, t: O2) -> bool { step2(s, l, t) }
}

proof fn lemma_report(s: O2, failed: Set<nat>, unknown: Set<nat>, parts: Set<nat>, t: O2)
    requires inv17o(s), step2(s, OL2::Report { failed, unknown, parts }, t),
    ensures inv17o(t), step_or_stutter::<OpscL1>(abso(s), labo(OL2::Report { failed, unknown, parts }), abso(t)),
{
    // R17-6: STATUS_PARTS names every part the report can mark unknown (control F-1713 fails here)
    assert(all_parts().subset_of(status_parts()));
}

proof fn lemma_install(s: O2, v: nat, locked: bool, t: O2)
    requires inv17o(s), step2(s, OL2::Install { v, locked }, t),
    ensures inv17o(t), step_or_stutter::<OpscL1>(abso(s), labo(OL2::Install { v, locked }), abso(t)),
{
    // R17-7: every version the metadata admits, and the lock's, is one the product works with (control F-C1706 fails here)
    assert(drv_ok(v));
}

pub proof fn lemma_step(s: O2, l: OL2, t: O2)
    requires inv17o(s), step2(s, l, t),
    ensures inv17o(t), step_or_stutter::<OpscL1>(abso(s), labo(l), abso(t)),
{
    match l {
        OL2::Report { failed, unknown, parts } => lemma_report(s, failed, unknown, parts, t),
        OL2::Install { v, locked } => lemma_install(s, v, locked, t),
        _ => {}
    }
}

impl Refines<OpscL1> for OpscL2 {
    open spec fn abs(s: O2) -> O1 { abso(s) }
    open spec fn lab(l: OL2) -> Option<OL1> { labo(l) }
    proof fn init_refines(s: O2) {}
    proof fn step_refines(s: O2, l: OL2, t: O2) { lemma_step(s, l, t); }
}

impl SafeContract for OpscL2 {
    open spec fn inv(s: O2) -> bool { inv17o(s) }
    proof fn init_safe(s: O2) {}
    proof fn step_safe(s: O2, l: OL2, t: O2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<O2>, labels: Seq<OL2>, k: int)
    requires execution::<OpscRaw>(states, labels), 0 <= k < states.len(),
    ensures inv17o(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution: reports name only listed parts, claims are facts, admitted installs work.
pub proof fn theorem_raw_executions_refine(states: Seq<O2>, labels: Seq<OL2>)
    requires execution::<OpscRaw>(states, labels),
    ensures
        execution::<OpscL2>(states, labels),
        abstract_execution::<OpscL1>(Seq::new(states.len(), |i: int| abso(states[i])),
                                     Seq::new(labels.len(), |i: int| labo(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv17o(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv17o(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<OpscL2>(states, labels));
    trace_refines::<OpscL2, OpscL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| abso(states[i])) =~= Seq::new(states.len(), |i: int| <OpscL2 as Refines<OpscL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labo(labels[i])) =~= Seq::new(labels.len(), |i: int| <OpscL2 as Refines<OpscL1>>::lab(labels[i])));
}

} // verus!
