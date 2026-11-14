//! M3: a FHIR graph's incremental sync against erasure, scheduling and an unreadable resource
//! (HD-1502, HD-1503, HD-1504; module 15).
//!
//! Abstract state: a repository feed of K keys (ids 1..K, one feed; the two real feeds Rsrc/RsrcVer behave alike),
//! the projected graph (which keys have nodes/edges), the registry row's watermark `wm` and interpretation marker,
//! whether the %SYS.Task is scheduled, and one sync process.
//!
//! As built at 3eaa79cf:
//! - `SyncOnce` takes `Lock +^IVG.FHIRGraph(g):0` (busy otherwise), reads the watermark into its context (`Open`) and
//!   the feed's MAX(ID) once, then runs batches; each `RunBatch` resyncs its keys and writes the watermark in one
//!   TSTART..TCOMMIT and only then sets the in-memory watermark (iris_src/src/Graph/KG/FHIRGraph.cls:543-626,
//!   1923-1979). An unreadable body throws "resource <key>: body is not JSON" (:2380-2395): the batch rolls back, the
//!   watermark stays, and `RecordError` writes `last_error` outside the transaction (:3101-3109).
//! - `Graph.KG.Eraser.EraseGraph` takes no lock at all (Eraser.cls has no LOCK), deletes the graph's content and resets
//!   `wm_rsrc = 0, wm_ver = 0, interp_version = NULL` in one transaction (Eraser.cls:1151-1180); the registration and
//!   the task survive.
//! - The task (FHIRGraphSyncTask) runs SyncOnce on its schedule; `Unschedule` suspends it but does not stop a sync
//!   that is running.
//! Reviewed (decisions.md): HD-1503 erase serializes with sync publication (here: erase takes the same lock, so it
//! waits for a running sync); HD-1502 durable removal = unschedule, then erase under that lock, and the feed stays
//! paused; HD-1504 failure without advancing the watermark is the baseline (progress needs the operator's repair);
//! the quarantine design is the alternative that progresses without repair.
//!
//! Properties:
//! - `watermark soundness`: with no sync batch in flight, every readable key at or below the watermark is projected
//!   (a key past the watermark may be missing; one at or below it may not, or no later sync brings it back);
//! - `durable removal holds`: after an operator's durable removal, the graph stays empty;
//! - always possibly: every key is projected (or quarantined) and the watermark reaches the feed's end.
use explorer::*;

pub const K: u8 = 3;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, ReviewedQuarantine, ControlEraseIgnoresLock }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Sync { Idle, Running { next: u8, max: u8 } }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    /// bit k-1: key k projected
    pub graph: u8,
    pub wm: u8,
    /// bit k-1: key k is unreadable in the repository (fixed unless repaired)
    pub poison: u8,
    /// bit k-1: key k set aside by the quarantine design
    pub quarantined: u8,
    pub scheduled: bool,
    pub sync: Sync,
    /// ghost: an operator performed a durable removal
    pub removed: bool,
    pub erases: u8,
    /// ghost (witness only): the graph was erased and then fully projected again
    pub refilled: bool,
}

#[derive(Clone, Debug)]
pub enum A {
    /// the task (or a caller) starts SyncOnce; refused as busy while one runs
    StartSync,
    /// one RunBatch of the running sync: `size` keys from `next`
    Batch { size: u8 },
    /// Eraser.EraseGraph (ordinary, transient erase)
    Erase,
    /// the operator's durable removal: unschedule the task, then erase. As built the erase does not wait for a
    /// sync that is already running (Unschedule suspends future runs only); reviewed it takes the sync lock.
    DurableRemoval,
    /// the operator repairs the offending resource (HD-1504 recovery)
    Repair,
}

pub struct M { pub design: Design, pub repair: bool, pub poison: u8, pub erase: bool }

impl M {
    fn erase_waits_for_sync(&self) -> bool { matches!(self.design, Design::Reviewed | Design::ReviewedQuarantine) }
    fn quarantines(&self) -> bool { self.design == Design::ReviewedQuarantine }
}

fn bit(k: u8) -> u8 { 1 << (k - 1) }

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { graph: 0, wm: 0, poison: self.poison, quarantined: 0, scheduled: true, sync: Sync::Idle,
                 removed: false, erases: 0, refilled: false }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![A::StartSync, A::Batch { size: 1 }, A::Batch { size: 2 }, A::Repair];
        if self.erase { v.push(A::Erase); v.push(A::DurableRemoval); }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut t = s.clone();
        match a {
            A::StartSync => {
                if s.sync != Sync::Idle || !s.scheduled { return None; }
                // Open() reads wm; MAX(ID) is read once. A graph erased since its last sync is re-derived over the
                // keys <= wm first (none after an erase: wm is 0) and then fed from wm.
                if s.wm >= K { return None; } // nothing past the watermark: the sync is a no-op
                t.sync = Sync::Running { next: s.wm + 1, max: K };
            }
            A::Batch { size } => {
                let Sync::Running { next, max } = s.sync else { return None };
                let end = (next + size - 1).min(max);
                if *size == 2 && end == next { return None; }
                let keys: Vec<u8> = (next..=end).collect();
                let bad: Vec<u8> = keys.iter().copied().filter(|k| s.poison & bit(*k) != 0).collect();
                if !bad.is_empty() && !self.quarantines() {
                    // the batch and its watermark roll back; the error is recorded; SyncOnce ends
                    t.sync = Sync::Idle;
                    return Some(t);
                }
                for k in &keys {
                    if bad.contains(k) { t.quarantined |= bit(*k); } else { t.graph |= bit(*k); }
                }
                t.wm = end; // UPDATE fhir_graphs SET wm = end, in the batch's transaction
                if s.erases > 0 && t.graph == (1 << K) - 1 { t.refilled = true; }
                t.sync = if end >= max { Sync::Idle } else { Sync::Running { next: end + 1, max } };
            }
            A::Erase | A::DurableRemoval => {
                if s.erases >= 2 { return None; }
                if self.erase_waits_for_sync() && s.sync != Sync::Idle { return None; }
                t.erases += 1;
                t.graph = 0;
                t.quarantined = 0;
                t.wm = 0;
                if matches!(a, A::DurableRemoval) {
                    t.removed = true;
                    t.scheduled = false;
                }
            }
            A::Repair => { if !self.repair || s.poison == 0 { return None; } t.poison = 0; }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant("watermark soundness", |s: &S| {
                if s.sync != Sync::Idle { return true; }
                (1..=s.wm).all(|k| (s.graph | s.quarantined) & bit(k) != 0)
            }),
            invariant("durable removal holds", |s: &S| !(s.removed && s.graph != 0)),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("every key is projected and the watermark reaches the end", |s: &S| {
            s.removed
                || (s.wm == K && (1..=K).all(|k| s.graph & bit(k) != 0 || s.quarantined & bit(k) != 0))
        })]
    }
}

pub struct Witness { pub m: M }
impl Model for Witness {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { self.m.init_states() }
    fn actions(&self, s: &S) -> Vec<A> { self.m.actions(s) }
    fn next(&self, s: &S, a: &A) -> Option<S> { self.m.next(s, a) }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant("an erased graph is fully projected again by later syncs", |s: &S| !s.refilled)]
    }
}

pub fn show(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps (keys 1..{K}, poison mask {:03b}):\n",
                          c.property, c.kind, c.steps.len(), c.init.poison);
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<18} graph={:03b} wm={} quarantined={:03b} sync={:?} scheduled={} removed={}\n",
                        i + 1, format!("{:?}", a), s.graph, s.wm, s.quarantined, s.sync, s.scheduled, s.removed);
    }
    out
}
