//! Module 15, L2: a FHIR graph's stored state at pin 3eaa79cf and the processes that change it; refinement of
//! `fhir_l1` for every step, the invariant, and the controls HD-1503, F-C1501 and F-1511.
//!
//! Layout (production names; one graph, one feed):
//! - `n`        MAX(ID) of the repository's Rsrc table; `bad` the keys whose body the sync cannot read (FHIRGraph.cls:
//!              2380-2397, 2976-2988: not JSON, deeper than 64, more than 10,000 json-link matches; HD-1504)
//! - `graph`    the keys projected into the FHIR graph (nodes, labels, edges of each key; FHIRGraph.cls:2039-2280)
//! - `wm`       Graph_KG.fhir_graphs.wm_rsrc; `stale` its interp_version IS NULL or old (FHIRGraph.cls:1417-1433)
//! - `tasks`    the %SYS.Task rows whose TaskClass is Graph.KG.FHIRGraphSyncTask and GraphId this graph;
//!              `task_id` fhir_graphs.task_id; `next_task` the %SYS.Task ID counter
//! - `sp`       the running SyncOnce, which holds Lock +^IVG.FHIRGraph(g):0 (FHIRGraph.cls:550-555): its phase, its
//!              in-memory position (tCtx.WmRsrc; the re-derivation pass's batch) and the MAX(ID) it read once (:558)
//! - `rcur`     the re-derivation pass's durable cursor (reviewed design R15-P, this lane's proposal; the pin has none)
//! - `removed`  ghost: an operator made a durable removal; `settings` the registered settings (one version number)
//!
//! **Reviewed design** (decisions.md HD-1502, HD-1503; F-C1501 and F-1511 remedies):
//! - R15-1 (HD-1503 alternative (a)): EraseGraph of a FHIR graph takes ^IVG.FHIRGraph(g), so it waits (or answers
//!   busy) while a sync holds it; a durable removal's erase does the same. As built Eraser.cls takes no lock at all and
//!   RunBatch writes an absolute watermark (FHIRGraph.cls:1967-1969): control HD-1503.
//! - R15-2 (F-C1501 remedy): Schedule saves the task and records its id in one transaction (IRIS transactions span
//!   IRISSYS and the namespace's database). As built %Save (:701) and the UPDATE (:703) are separate: control F-C1501.
//! - R15-3 (F-1511 remedy): Register validates and loads its metadata before writing, so a refusal writes nothing. As
//!   built the upsert (:235-245) commits before Open/LoadColumns (:247-249) can throw: control F-1511.
//! - R15-P (progress only; this lane's proposal): a re-derivation pass resumes from a durable cursor. As built an
//!   interrupted pass leaves interp_version unset and the next sync starts it again from the first key (:573-581,
//!   1451-1473; INT-F5.7, spec 235 FR-024): control `control_progress_rederive_restart` (fails only fhir_progress.rs).
//! As built and kept: one sync at a time (the lock, zero timeout: busy, INT-F6.1), a batch and its watermark in one
//! transaction (RunBatch TSTART..TCOMMIT, :1923-1977), a failed batch moves neither and ends the sync (:620-624),
//! EraseGraph zeroes the watermarks and nulls interp_version and keeps the registration (Eraser.cls:1146-1180),
//! Unschedule deletes the task task_id names and clears task_id (FHIRGraph.cls:715-741).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::fhir_l1::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

pub enum Phase { Rederive, Feed }
pub struct Run { pub phase: Phase, pub pos: nat, pub max: nat }

pub struct F2 {
    pub n: nat, pub bad: Set<nat>, pub graph: Set<nat>, pub wm: nat,
    pub tasks: Set<nat>, pub task_id: Option<nat>, pub next_task: nat,
    pub sp: Option<Run>, pub removed: bool, pub settings: nat, pub stale: bool, pub rcur: nat,
}

pub enum FL2 {
    /// a new resource row (HS.FHIRServer writes Rsrc)
    Append,
    /// the operator repairs or deletes an unreadable resource (HD-1504 recovery)
    Repair { k: nat },
    /// SyncOnce: the task's tick (`by_task`) or a caller (fhir_graph_sync, `ivg fhir sync --once`) takes the lock,
    /// opens the context (reads wm, interp_version) and reads MAX(ID) once (FHIRGraph.cls:543-558)
    Start { by_task: bool },
    /// one RunBatch of the re-derivation pass (Rederive, :1451-1473; no watermark)
    RBatch,
    /// SetInterpVersion after the pass (:577-580)
    RDone,
    /// one RunBatch of the feed, committed with its watermark e (:585-609, 1967-1969)
    Batch { e: nat },
    /// a batch holding an unreadable key throws: it rolls back with its watermark, RecordError, SyncOnce ends
    BatchFail { e: nat },
    /// the sync's process stops, or its re-derivation batch throws (SYS-P1 rolls the open batch back)
    Interrupt,
    /// the feed is done: last_sync, last_error = NULL, the lock is released (:611)
    End,
    /// Graph.KG.Eraser.EraseGraph (Eraser.cls:47-258, EraseFHIRGraphRows :1151-1180)
    Erase,
    /// the operator's durable removal: Unschedule, then EraseGraph (HD-1502 working answer)
    Remove,
    /// FHIRGraph.Schedule (:667-713)
    Schedule { ok: bool },
    /// FHIRGraph.Unschedule (:715-741)
    Unschedule { ok: bool },
    /// FHIRGraph.Register run again with settings v (:167-280)
    Register { ok: bool, v: nat },
}

pub open spec fn hd1503() -> bool { cfg!(feature = "control_hd1503_erase_ignores_sync_lock") }
pub open spec fn fc1501() -> bool { cfg!(feature = "control_fc1501_schedule_untransacted") }
pub open spec fn f1511() -> bool { cfg!(feature = "control_f1511_upsert_before_load") }
pub open spec fn prog_restart() -> bool { cfg!(feature = "control_progress_rederive_restart") }

pub open spec fn task_set(id: Option<nat>) -> Set<nat> {
    match id { Some(i) => Set::<nat>::empty().insert(i), None => Set::<nat>::empty() }
}

/// No key of (a, e] is unreadable.
pub open spec fn clean(s: F2, a: nat, e: nat) -> bool { forall|k: nat| #[trigger] upto(a, e).contains(k) ==> !s.bad.contains(k) }

/// Where a re-derivation pass starts: R15-P resumes from the durable cursor; as built it starts again.
pub open spec fn rstart(s: F2) -> nat { if prog_restart() { 0 } else { s.rcur } }

pub open spec fn started(s: F2) -> F2 {
    if s.stale { F2 { sp: Some(Run { phase: Phase::Rederive, pos: rstart(s), max: s.n }), rcur: rstart(s), ..s } }
    else { F2 { sp: Some(Run { phase: Phase::Feed, pos: s.wm, max: s.n }), ..s } }
}
pub open spec fn rbatched(s: F2) -> F2 {
    F2 { sp: Some(Run { pos: s.sp->Some_0.pos + 1, ..s.sp->Some_0 }), rcur: s.sp->Some_0.pos + 1, ..s }
}
pub open spec fn rdone(s: F2) -> F2 { F2 { sp: Some(Run { phase: Phase::Feed, pos: s.wm, ..s.sp->Some_0 }), stale: false, ..s } }
pub open spec fn batched(s: F2, e: nat) -> F2 {
    F2 { graph: s.graph.union(upto(s.sp->Some_0.pos, e)), wm: e, sp: Some(Run { pos: e, ..s.sp->Some_0 }), ..s }
}
pub open spec fn stopped(s: F2) -> F2 { F2 { sp: None, ..s } }
pub open spec fn erased(s: F2) -> F2 { F2 { graph: Set::empty(), wm: 0, stale: true, rcur: 0, ..s } }
pub open spec fn without_task(s: F2) -> Set<nat> { match s.task_id { Some(i) => s.tasks.remove(i), None => s.tasks } }
pub open spec fn unscheduled(s: F2) -> F2 { F2 { tasks: without_task(s), task_id: None, ..s } }
pub open spec fn removed_state(s: F2) -> F2 { F2 { removed: true, ..erased(unscheduled(s)) } }
pub open spec fn new_task(s: F2) -> F2 {
    F2 { tasks: s.tasks.insert(s.next_task), task_id: Some(s.next_task), next_task: s.next_task + 1, ..s }
}
/// Schedule rewrites the graph's own task when task_id names one, else creates one.
pub open spec fn scheduled(s: F2) -> F2 {
    if s.task_id is Some && s.tasks.contains(s.task_id->Some_0) { s } else { new_task(s) }
}
/// As built, a Schedule whose UPDATE fails after %Save: a task the registry does not name.
pub open spec fn orphaned(s: F2) -> F2 { F2 { tasks: s.tasks.insert(s.next_task), next_task: s.next_task + 1, ..s } }

pub open spec fn feed(s: F2) -> bool { s.sp is Some && s.sp->Some_0.phase is Feed }
pub open spec fn rederiving(s: F2) -> bool { s.sp is Some && s.sp->Some_0.phase is Rederive }

pub open spec fn init2(s: F2) -> bool {
    &&& s.graph == Set::<nat>::empty() && s.wm == 0 && s.rcur == 0
    &&& s.tasks == Set::<nat>::empty() && s.task_id is None
    &&& s.sp is None && !s.removed
}

pub open spec fn step2(s: F2, l: FL2, t: F2) -> bool {
    match l {
        FL2::Append => t == F2 { n: s.n + 1, ..s },
        FL2::Repair { k } => t == F2 { bad: s.bad.remove(k), ..s },
        FL2::Start { by_task } =>
            s.sp is None && (if by_task { s.tasks != Set::<nat>::empty() } else { !s.removed }) && t == started(s),
        FL2::RBatch => rederiving(s) && s.sp->Some_0.pos < s.wm && t == rbatched(s),
        FL2::RDone => rederiving(s) && s.sp->Some_0.pos == s.wm && t == rdone(s),
        FL2::Batch { e } =>
            feed(s) && s.sp->Some_0.pos < e && e <= s.sp->Some_0.max && clean(s, s.sp->Some_0.pos, e) && t == batched(s, e),
        FL2::BatchFail { e } =>
            feed(s) && s.sp->Some_0.pos < e && e <= s.sp->Some_0.max && !clean(s, s.sp->Some_0.pos, e) && t == stopped(s),
        FL2::Interrupt => s.sp is Some && t == stopped(s),
        FL2::End => feed(s) && s.sp->Some_0.pos == s.sp->Some_0.max && t == stopped(s),
        FL2::Erase => (hd1503() || s.sp is None) && t == erased(s),
        FL2::Remove => (hd1503() || s.sp is None) && t == removed_state(s),
        FL2::Schedule { ok } =>
            !s.removed && if ok { t == scheduled(s) } else { t == s || (fc1501() && t == orphaned(s)) },
        FL2::Unschedule { ok } => if ok { t == unscheduled(s) } else { t == s },
        FL2::Register { ok, v } => if ok || f1511() { t == F2 { settings: v, ..s } } else { t == s },
    }
}

pub open spec fn absf(s: F2) -> F1 {
    F1 { n: s.n, graph: s.graph, wm: s.wm, sched: s.tasks != Set::<nat>::empty(), removed: s.removed, settings: s.settings }
}

pub open spec fn labf(l: FL2) -> Option<FL1> {
    match l {
        FL2::Append => Some(FL1::Append),
        FL2::Batch { e } => Some(FL1::Batch { e }),
        FL2::Erase => Some(FL1::Erase),
        FL2::Remove => Some(FL1::Remove),
        FL2::Schedule { ok } => Some(FL1::Schedule { ok }),
        FL2::Unschedule { ok } => Some(FL1::Unschedule { ok }),
        FL2::Register { ok, v } => Some(FL1::Register { ok, v }),
        _ => None,
    }
}

/// The running sync's position is the stored watermark (feed) or the durable cursor (re-derivation).
pub open spec fn run_ok(s: F2) -> bool {
    match s.sp {
        None => true,
        Some(r) => !s.removed && r.max <= s.n && s.wm <= r.max && match r.phase {
            Phase::Feed => r.pos == s.wm && !s.stale,
            Phase::Rederive => s.stale && r.pos == s.rcur,
        },
    }
}

/// The graph's sync tasks are exactly the one the registry names (INT-F9).
pub open spec fn tasks_ok(s: F2) -> bool {
    &&& s.tasks == task_set(s.task_id)
    &&& s.task_id is Some ==> s.task_id->Some_0 < s.next_task
}

pub open spec fn inv15(s: F2) -> bool {
    &&& inv1(absf(s))
    &&& run_ok(s)
    &&& s.rcur <= s.wm
    &&& tasks_ok(s)
}

pub struct FhirL2;

impl Contract for FhirL2 {
    type S = F2;
    type L = FL2;
    open spec fn init(s: F2) -> bool { init2(s) }
    open spec fn next(s: F2, l: FL2, t: F2) -> bool { inv15(s) && step2(s, l, t) }
}

pub struct FhirRaw;

impl Contract for FhirRaw {
    type S = F2;
    type L = FL2;
    open spec fn init(s: F2) -> bool { init2(s) }
    open spec fn next(s: F2, l: FL2, t: F2) -> bool { step2(s, l, t) }
}

proof fn lemma_batch(s: F2, e: nat, t: F2)
    requires inv15(s), step2(s, FL2::Batch { e }, t),
    ensures inv15(t), FhirL1::next(absf(s), FL1::Batch { e }, absf(t)),
{
    // the batch starts at the stored watermark: what the reviewed erase (R15-1) keeps true
    assert(s.sp->Some_0.pos == s.wm);
    lemma_l1_safe(absf(s), FL1::Batch { e }, absf(t));
}

proof fn lemma_erase(s: F2, t: F2)
    requires inv15(s), step2(s, FL2::Erase, t),
    ensures inv15(t), FhirL1::next(absf(s), FL1::Erase, absf(t)),
{
    // R15-1: the erase waits for the sync lock, so no sync runs past it with an old position (control HD-1503 fails here)
    assert(run_ok(t));
    lemma_l1_safe(absf(s), FL1::Erase, absf(t));
}

proof fn lemma_remove(s: F2, t: F2)
    requires inv15(s), step2(s, FL2::Remove, t),
    ensures inv15(t), FhirL1::next(absf(s), FL1::Remove, absf(t)),
{
    assert(without_task(s) =~= Set::<nat>::empty());
    // R15-1: the durable removal's erase waits for a running sync, so nothing projects after it (control HD-1503 fails here)
    assert(run_ok(t));
    lemma_l1_safe(absf(s), FL1::Remove, absf(t));
}

proof fn lemma_schedule(s: F2, ok: bool, t: F2)
    requires inv15(s), step2(s, FL2::Schedule { ok }, t),
    ensures inv15(t), FhirL1::next(absf(s), FL1::Schedule { ok }, absf(t)),
{
    if ok {
        if !(s.task_id is Some && s.tasks.contains(s.task_id->Some_0)) {
            assert(s.tasks =~= Set::<nat>::empty());
            assert(t.tasks.contains(s.next_task));
        }
    } else {
        // R15-2: the task and its registry id are written together or not at all (control F-C1501 fails here)
        assert(t == s);
    }
    lemma_l1_safe(absf(s), FL1::Schedule { ok }, absf(t));
}

proof fn lemma_unschedule(s: F2, ok: bool, t: F2)
    requires inv15(s), step2(s, FL2::Unschedule { ok }, t),
    ensures inv15(t), FhirL1::next(absf(s), FL1::Unschedule { ok }, absf(t)),
{
    if ok { assert(without_task(s) =~= Set::<nat>::empty()); }
    lemma_l1_safe(absf(s), FL1::Unschedule { ok }, absf(t));
}

proof fn lemma_register(s: F2, ok: bool, v: nat, t: F2)
    requires inv15(s), step2(s, FL2::Register { ok, v }, t),
    ensures inv15(t), FhirL1::next(absf(s), FL1::Register { ok, v }, absf(t)),
{
    // R15-3: a refused register writes nothing (control F-1511 fails here)
    assert(!ok ==> t == s);
    lemma_l1_safe(absf(s), FL1::Register { ok, v }, absf(t));
}

pub proof fn lemma_step(s: F2, l: FL2, t: F2)
    requires inv15(s), step2(s, l, t),
    ensures inv15(t), step_or_stutter::<FhirL1>(absf(s), labf(l), absf(t)),
{
    match l {
        FL2::Append => { lemma_l1_safe(absf(s), FL1::Append, absf(t)); }
        FL2::Batch { e } => lemma_batch(s, e, t),
        FL2::Erase => lemma_erase(s, t),
        FL2::Remove => lemma_remove(s, t),
        FL2::Schedule { ok } => lemma_schedule(s, ok, t),
        FL2::Unschedule { ok } => lemma_unschedule(s, ok, t),
        FL2::Register { ok, v } => lemma_register(s, ok, v, t),
        FL2::Start { by_task } => {
            if by_task { assert(!s.removed); }
            assert(absf(t) == absf(s));
        }
        _ => { assert(absf(t) == absf(s)); }
    }
}

impl Refines<FhirL1> for FhirL2 {
    open spec fn abs(s: F2) -> F1 { absf(s) }
    open spec fn lab(l: FL2) -> Option<FL1> { labf(l) }
    proof fn init_refines(s: F2) {}
    proof fn step_refines(s: F2, l: FL2, t: F2) { lemma_step(s, l, t); }
}

impl SafeContract for FhirL2 {
    open spec fn inv(s: F2) -> bool { inv15(s) }
    proof fn init_safe(s: F2) { assert(s.tasks =~= task_set(s.task_id)); }
    proof fn step_safe(s: F2, l: FL2, t: F2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<F2>, labels: Seq<FL2>, k: int)
    requires execution::<FhirRaw>(states, labels), 0 <= k < states.len(),
    ensures inv15(states[k]),
    decreases k,
{
    if k == 0 { assert(states[0].tasks =~= task_set(states[0].task_id)); }
    else {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution: the graph changes only by whole batches after the stored watermark, erases and durable removals.
pub proof fn theorem_raw_executions_refine(states: Seq<F2>, labels: Seq<FL2>)
    requires execution::<FhirRaw>(states, labels),
    ensures
        execution::<FhirL2>(states, labels),
        abstract_execution::<FhirL1>(Seq::new(states.len(), |i: int| absf(states[i])),
                                     Seq::new(labels.len(), |i: int| labf(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv15(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv15(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<FhirL2>(states, labels));
    trace_refines::<FhirL2, FhirL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absf(states[i])) =~= Seq::new(states.len(), |i: int| <FhirL2 as Refines<FhirL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labf(labels[i])) =~= Seq::new(labels.len(), |i: int| <FhirL2 as Refines<FhirL1>>::lab(labels[i])));
}

/// HD-1503 on the layout: a running sync's next batch starts at the stored watermark.
pub proof fn theorem_sync_continues_from_the_stored_watermark(s: F2)
    requires inv15(s), feed(s),
    ensures s.sp->Some_0.pos == s.wm, !s.removed,
{
}

/// HD-1502 on the layout: after a durable removal no sync task exists, none runs, and no task tick can start one
/// (a manual sync is excluded by premise P-F2).
pub proof fn theorem_durable_removal_stops_the_feed(s: F2, t: F2)
    requires inv15(s), s.removed,
    ensures s.tasks == Set::<nat>::empty(), s.sp is None, !step2(s, FL2::Start { by_task: true }, t),
{
}

} // verus!
