//! Module 15, L1: a FHIR graph as a projection of its repository's change feed (docs/FHIR_GRAPH.md:245-297), with its
//! sync task (INT-F9) and its registration (INT-F3).
//!
//! State: the feed's highest row id `n` (keys 1..n, one feed: Rsrc and RsrcVer behave alike, INT-F5.1), the projected
//! keys `graph`, the watermark `wm` (fhir_graphs.wm_rsrc), whether a sync task runs the graph (`sched`), whether an
//! operator has made a durable removal (`removed`, HD-1502 working answer: unschedule, then erase, and no manual sync
//! afterwards), and the registered settings (`settings`: endpoints, denylist, interval, as one version number).
//!
//! Business rules (`inv1`, proved inductive by `lemma_l1_safe`):
//! - **watermark soundness** (INT-F5.2, FHIR_GRAPH.md:255-259 "any sequence of syncs converges on the graph a rebuild
//!   would build"): every key at or below the watermark is projected, and a batch applies exactly the keys after the
//!   stored watermark, moving the watermark with them;
//! - **a durable removal stays removed** (HD-1502 working answer, spec 256 tenant erasure): after it the graph is empty
//!   and no task runs it, and nothing projects into it again;
//! - **a refused command changes nothing** (SYS-I3; INT-F3.9 for register, INT-F9 / SYS-I4 for schedule);
//! - re-registering keeps the watermarks (INT-F3.7).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

/// The feed keys in (a, b]: row ids a+1..b.
pub open spec fn upto(a: nat, b: nat) -> Set<nat> { Set::<nat>::range(a + 1, b + 1) }

pub struct F1 { pub n: nat, pub graph: Set<nat>, pub wm: nat, pub sched: bool, pub removed: bool, pub settings: nat }

pub enum FL1 {
    /// a new resource row in the repository (Rsrc.ID = n + 1)
    Append,
    /// one committed sync batch: the keys after the watermark, up to e, with the watermark
    Batch { e: nat },
    /// Graph.KG.Eraser.EraseGraph of the FHIR graph: a transient clear (HD-1502, supported)
    Erase,
    /// the operator's durable removal: the task is unscheduled and the graph erased
    Remove,
    Schedule { ok: bool },
    Unschedule { ok: bool },
    Register { ok: bool, v: nat },
}

pub struct FhirL1;

impl Contract for FhirL1 {
    type S = F1;
    type L = FL1;

    open spec fn init(s: F1) -> bool { s.graph == Set::<nat>::empty() && s.wm == 0 && !s.sched && !s.removed }

    open spec fn next(s: F1, l: FL1, t: F1) -> bool {
        match l {
            FL1::Append => t == F1 { n: s.n + 1, ..s },
            FL1::Batch { e } =>
                !s.removed && s.wm < e && e <= s.n && t == F1 { graph: s.graph.union(upto(s.wm, e)), wm: e, ..s },
            FL1::Erase => t == F1 { graph: Set::empty(), wm: 0, ..s },
            FL1::Remove => t == F1 { graph: Set::empty(), wm: 0, sched: false, removed: true, ..s },
            FL1::Schedule { ok } => if ok { !s.removed && t == F1 { sched: true, ..s } } else { t == s },
            FL1::Unschedule { ok } => if ok { t == F1 { sched: false, ..s } } else { t == s },
            FL1::Register { ok, v } => if ok { t == F1 { settings: v, ..s } } else { t == s },
        }
    }
}

/// Every key at or below the watermark is projected.
pub open spec fn sound(s: F1) -> bool { forall|k: nat| 1 <= k && k <= s.wm ==> #[trigger] s.graph.contains(k) }

pub open spec fn inv1(s: F1) -> bool {
    &&& s.wm <= s.n
    &&& sound(s)
    &&& forall|k: nat| #[trigger] s.graph.contains(k) ==> 1 <= k && k <= s.n
    &&& s.removed ==> s.graph == Set::<nat>::empty() && !s.sched && s.wm == 0
}

pub proof fn lemma_l1_safe(s: F1, l: FL1, t: F1)
    requires inv1(s), FhirL1::next(s, l, t),
    ensures inv1(t),
{
    match l {
        FL1::Batch { e } => {
            assert forall|k: nat| 1 <= k && k <= t.wm implies #[trigger] t.graph.contains(k) by {
                if k <= s.wm { assert(s.graph.contains(k)); } else { assert(upto(s.wm, e).contains(k)); }
            }
            assert forall|k: nat| #[trigger] t.graph.contains(k) implies 1 <= k && k <= t.n by {
                if s.graph.contains(k) {} else { assert(upto(s.wm, e).contains(k)); }
            }
        }
        _ => {}
    }
}

impl SafeContract for FhirL1 {
    open spec fn inv(s: F1) -> bool { inv1(s) }
    proof fn init_safe(s: F1) {}
    proof fn step_safe(s: F1, l: FL1, t: F1) { lemma_l1_safe(s, l, t); }
}

/// FHIR_GRAPH.md:255-259: a graph whose watermark has reached the feed's end holds exactly the repository's keys.
pub proof fn theorem_caught_up_graph_is_the_repository(s: F1)
    requires inv1(s), s.wm == s.n,
    ensures s.graph == upto(0, s.n),
{
    assert forall|k: nat| s.graph.contains(k) <==> #[trigger] upto(0, s.n).contains(k) by {
        if upto(0, s.n).contains(k) { assert(1 <= k && k <= s.wm); }
    }
    assert(s.graph =~= upto(0, s.n));
}

/// INT-F5.2: a batch applies the keys after the stored watermark and moves the watermark with them.
pub proof fn theorem_batch_moves_with_its_watermark(s: F1, e: nat, t: F1)
    requires FhirL1::next(s, FL1::Batch { e }, t),
    ensures t.wm == e, t.graph == s.graph.union(upto(s.wm, e)), s.wm < e,
{
}

/// HD-1502 (working answer): after a durable removal the graph stays empty and no task runs it.
pub proof fn theorem_durable_removal_stays_removed(s: F1, l: FL1, t: F1)
    requires inv1(s), s.removed, FhirL1::next(s, l, t),
    ensures t.removed, t.graph == Set::<nat>::empty(), !t.sched,
{
    lemma_l1_safe(s, l, t);
}

/// SYS-I3 (INT-F3.9 for register; SYS-I4 for schedule, which writes the Task Manager and the registry): a refused
/// schedule, unschedule or register changes nothing.
pub proof fn theorem_refusals_change_nothing(s: F1, l: FL1, t: F1)
    requires FhirL1::next(s, l, t),
        match l { FL1::Schedule { ok } => !ok, FL1::Unschedule { ok } => !ok, FL1::Register { ok, v } => !ok, _ => false },
    ensures t == s,
{
}

/// INT-F3.7: a register run again keeps the watermarks and the projection.
pub proof fn theorem_register_keeps_watermarks(s: F1, v: nat, t: F1)
    requires FhirL1::next(s, FL1::Register { ok: true, v }, t),
    ensures t.wm == s.wm, t.graph == s.graph, t.settings == v,
{
}

/// INT-F9: after a successful unschedule no task runs the graph.
pub proof fn theorem_unschedule_stops_the_task(s: F1, t: F1)
    requires FhirL1::next(s, FL1::Unschedule { ok: true }, t),
    ensures !t.sched,
{
}

} // verus!
