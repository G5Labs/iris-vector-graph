//! M-03 Exclusive section: lock and marker (axioms AX-11, AX-12). Generic machine over `ExclObject`: an
//! interpreter of the step programs the object's processes run, interleaved in every order.
//!
//! State: each process's program counter (or finished / refused); the lock (exclusive holder bitmask, shared
//! holders bitmask); the marker (target, owner) or none; per target (0 = tenant A, 1 = tenant B): live content?,
//! history tombstoned?; the no-lock mark (Adjacency.cls:55-75: a writer that waited 5 s writes without the lock and
//! marks the graph).
//! Steps: `LockX`, `LockS` (block until available), `LockSOrMark` (take shared or, if an exclusive holder exists,
//! set the no-lock mark and go on), `Unlock`, `CheckNotLive(t)` / `CheckNoMarker(t)` / `CheckNoMarkerAny` (refuse
//! and stop the process, releasing its lock), `SetMarker(t)` (only if none), `ClearAny` (whatever marker exists),
//! `ClearOwn`, and guarded effects `MakeLive(t)` (a commit into t), `Erase(t)`, `Tomb(t)`, `Write` (any guarded
//! write of the object's store). `LockXBad` is the control's broken lock (ignores holders).
//!
//! Laws: M03-L1 (invariant) at most one exclusive holder and none with shared holders; M03-L2 (action) every guarded
//! effect is made by a process holding the lock (or, for `LockSOrMark` writers, with the no-lock mark set);
//! M03-L3 (invariant) while t is marked, t is not live; M03-L4 (action) only the marker's owner clears it; M03-L5
//! (action) no history of live content is tombstoned.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Step {
    LockX, LockXBad, LockS, LockSOrMark, Unlock,
    CheckNotLive(u8), CheckNoMarker(u8), CheckNoMarkerAny,
    SetMarker(u8), ClearAny, ClearOwn,
    MakeLive(u8), Erase(u8), Tomb(u8), Write,
}

impl Step {
    fn guarded(&self) -> bool { matches!(self, Step::MakeLive(_) | Step::Erase(_) | Step::Tomb(_) | Step::Write) }
}

pub type Progs = Vec<Vec<Step>>;

pub trait ExclObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    /// initial liveness of targets 0 and 1
    fn init_live(&self) -> [bool; 2];
    fn as_built(&self) -> Progs;
    fn reviewed(&self) -> Progs;
    fn departs(&self) -> (&'static str, &'static [&'static str]);
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Pc { At(u8), Done, Refused }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub pc: Vec<Pc>,
    pub excl: u8,
    pub shared: u8,
    pub marker: Option<(u8, u8)>,
    pub live: [bool; 2],
    pub tomb: [bool; 2],
    pub nolock: bool,
}

#[derive(Clone, Debug)]
pub struct A(pub u8, pub Step);

pub struct Machine<'a, O: ExclObject> { pub o: &'a O, pub progs: Progs }

pub const L1: &str = "M03-L1 mutual exclusion";
pub const L2: &str = "M03-L2 guarded effects hold the lock";
pub const L3: &str = "M03-L3 a marked target is not live";
pub const L4: &str = "M03-L4 only the owner clears the marker";
pub const L5: &str = "M03-L5 no history of live content is tombstoned";

impl<'a, O: ExclObject> Machine<'a, O> {
    fn holds(s: &S, i: u8) -> bool { (s.excl | s.shared) & (1 << i) != 0 }
    fn release(u: &mut S, i: u8) { u.excl &= !(1 << i); u.shared &= !(1 << i); }
}

impl<'a, O: ExclObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { pc: vec![Pc::At(0); self.progs.len()], excl: 0, shared: 0, marker: None, live: self.o.init_live(), tomb: [false; 2], nolock: false }]
    }
    fn actions(&self, s: &S) -> Vec<A> {
        let mut v = vec![];
        for (i, p) in s.pc.iter().enumerate() {
            if let Pc::At(k) = p { v.push(A(i as u8, self.progs[i][*k as usize])); }
        }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let i = a.0;
        let Pc::At(k) = s.pc[i as usize] else { return None };
        let mut u = s.clone();
        let me = 1u8 << i;
        let mut advance = true;
        match a.1 {
            Step::LockX => { if (s.excl | s.shared) & !me != 0 { return None; } u.excl |= me; }
            Step::LockXBad => { u.excl |= me; }
            Step::LockS => { if s.excl & !me != 0 { return None; } u.shared |= me; }
            Step::LockSOrMark => { if s.excl & !me != 0 { u.nolock = true; } else { u.shared |= me; } }
            Step::Unlock => { Self::release(&mut u, i); }
            Step::CheckNotLive(t) => { if s.live[t as usize] { u.pc[i as usize] = Pc::Refused; Self::release(&mut u, i); advance = false; } }
            Step::CheckNoMarker(t) => { if matches!(s.marker, Some((m, o)) if m == t && o != i) { u.pc[i as usize] = Pc::Refused; Self::release(&mut u, i); advance = false; } }
            Step::CheckNoMarkerAny => { if matches!(s.marker, Some((_, o)) if o != i) { u.pc[i as usize] = Pc::Refused; Self::release(&mut u, i); advance = false; } }
            Step::SetMarker(t) => { if s.marker.is_none() { u.marker = Some((t, i)); } }
            Step::ClearAny => { u.marker = None; }
            Step::ClearOwn => { if matches!(s.marker, Some((_, o)) if o == i) { u.marker = None; } }
            Step::MakeLive(t) => { u.live[t as usize] = true; }
            Step::Erase(t) => { u.live[t as usize] = false; }
            Step::Tomb(t) => { u.tomb[t as usize] = true; }
            Step::Write => {}
        }
        if advance {
            let next = k + 1;
            u.pc[i as usize] = if next as usize >= self.progs[i as usize].len() { Self::release(&mut u, i); Pc::Done } else { Pc::At(next) };
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(L1, |s: &S| s.excl.count_ones() <= 1 && (s.excl == 0 || s.shared == 0)),
            invariant(L3, |s: &S| match s.marker { Some((t, _)) => !s.live[t as usize], None => true }),
        ]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![
            action_property(L2, |o: &S, a: &A, _n: &S| !a.1.guarded() || Self::holds(o, a.0) || o.nolock),
            action_property(L4, |o: &S, a: &A, n: &S| !(o.marker.is_some() && n.marker.is_none()) || matches!(o.marker, Some((_, w)) if w == a.0)),
            action_property(L5, |o: &S, a: &A, _n: &S| match a.1 { Step::Tomb(t) => !o.live[t as usize], _ => true }),
        ]
    }
}

use Step::*;

macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], $live:expr, $ab:expr, $rv:expr, $law:expr, [$($f:expr),*]) => {
        pub struct $t;
        impl ExclObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn init_live(&self) -> [bool; 2] { $live }
            fn as_built(&self) -> Progs { $ab }
            fn reviewed(&self) -> Progs { $rv }
            fn departs(&self) -> (&'static str, &'static [&'static str]) { ($law, &[$($f),*]) }
        }
    };
}

fn commit_into(t: u8) -> Vec<Step> { vec![LockX, CheckNoMarker(t), MakeLive(t), Unlock] }
fn redact_reviewed(t: u8) -> Vec<Step> { vec![LockX, CheckNoMarkerAny, CheckNotLive(t), SetMarker(t), Tomb(t), Unlock, LockX, CheckNotLive(t), ClearOwn, Unlock] }
/// LedgerRedact.Redact as built: unlocked liveness check (:185-211), the marker set in the first batch under the
/// head lock (:302-330), Final clears the one global marker (:384-430).
fn redact_as_built(t: u8) -> Vec<Step> { vec![CheckNoMarkerAny, CheckNotLive(t), LockX, SetMarker(t), Tomb(t), Unlock, LockX, CheckNotLive(t), ClearAny, Unlock] }

// Ledger.Commit: the head lock around the marker check and the apply (Ledger.cls:440-444, :404).
object!(HeadLockCommit, "head-lock-commit", ["11/ledger", "10/interned-snapshot"], [false, false],
        vec![commit_into(0), commit_into(1)], vec![commit_into(0), commit_into(1)], "", []);
// Redaction of two targets with a writer committing into the first (F-1302, F-1303).
object!(RedactionMarker, "redaction-marker", ["13/redaction-target", "13/redaction-run"], [false, false],
        vec![redact_as_built(0), redact_as_built(1), commit_into(0)],
        vec![redact_reviewed(0), redact_reviewed(1), commit_into(0)], L4, ["F-1302", "F-1303"]);
// EraseGraph changes rows and statement maps a commit also writes, with no head lock (Eraser.cls:665-678, 809-811).
object!(EraserNoHeadLock, "eraser-no-head-lock", ["12/graph-content"], [true, false],
        vec![vec![Erase(0), Write], commit_into(0)],
        vec![vec![LockX, Erase(0), Write, Unlock], commit_into(0)], L2, ["F-1201", "F-1114", "F-C1201"]);
// The adjacency writer lock: writers shared (or marked after 5 s), rebuild exclusive; Reweight takes none (F-0407).
object!(AdjacencyWriterLock, "adjacency-writer-lock", ["04/graph-writer-lock"], [true, false],
        vec![vec![LockSOrMark, Write, Unlock], vec![Write], vec![LockX, Write, Unlock]],
        vec![vec![LockSOrMark, Write, Unlock], vec![LockSOrMark, Write, Unlock], vec![LockX, Write, Unlock]], L2, ["F-0407"]);
// The no-lock mark alone: writers that time out on the shared lock write and set the mark (Adjacency.cls:55-75),
// the rebuild holds the lock exclusively; no lock-free writer (Reweight belongs to the graph writer lock above).
object!(AdjacencyNoLockMark, "adjacency-no-lock-mark", ["04/no-lock-mark"], [true, false],
        vec![vec![LockSOrMark, Write, Unlock], vec![LockSOrMark, Write, Unlock], vec![LockX, Write, Unlock]],
        vec![vec![LockSOrMark, Write, Unlock], vec![LockSOrMark, Write, Unlock], vec![LockX, Write, Unlock]], "", []);
// BM25: Insert takes the index write lock; Build and Drop write without it (BM25Index.cls:97-175, 587-591; F-0701).
object!(Bm25WriteLock, "bm25-write-lock", ["07/bm25-index"], [true, false],
        vec![vec![LockX, Write, Unlock], vec![Write, Write]],
        vec![vec![LockX, Write, Unlock], vec![LockX, Write, Write, Unlock]], L2, ["F-0701"]);
// Compiled plans: a build holds its lock; a deploy's drop does not wait for it (Gen.cls:166, 225-230; F-0905).
object!(PlanBuildLock, "plan-build-lock", ["09/compiled-shape"], [true, false],
        vec![vec![LockX, Write, Unlock], vec![Write]],
        vec![vec![LockX, Write, Unlock], vec![LockX, Write, Unlock]], L2, ["F-0905"]);
// Graph mode: turning the mode off races a write that adds a parallel edge (GraphMode.cls:26-61; F-0207).
object!(ModeSwitch, "mode-switch", ["02/graph-mode"], [true, false],
        vec![vec![Write], vec![Write]],
        vec![vec![LockX, Write, Unlock], vec![LockS, Write, Unlock]], L2, ["F-0207"]);

fn instance_checks<O: ExclObject>(o: &O) -> Vec<Outcome> {
    let (law, f) = o.departs();
    let n = o.name();
    let ab = Machine { o, progs: o.as_built() };
    let rv = Machine { o, progs: o.reviewed() };
    let mut out = vec![];
    if law.is_empty() {
        out.push(check_keep(&format!("excl-{n}-as-built"), meta("M-03", "excl", n, o.objects(), "as-built", "safety", "all", f, ""), Expect::Pass, &Keep::safety(&ab)));
    } else {
        out.push(check_keep(&format!("excl-{n}-as-built"), meta("M-03", "excl", n, o.objects(), "as-built", "safety", law, f, ""), Expect::Violation(law), &Keep::only(&ab, &[law])));
    }
    out.push(check_keep(&format!("excl-{n}-reviewed"), meta("M-03", "excl", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)));
    out
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&HeadLockCommit));
    out.extend(instance_checks(&RedactionMarker));
    // the redaction marker's other two departures, each attributed to its own law and finding
    {
        let o = &RedactionMarker;
        let ab = Machine { o, progs: o.as_built() };
        out.push(check_keep("excl-redaction-marker-as-built-F1302-marker", meta("M-03", "excl", "redaction-marker", o.objects(), "as-built", "safety", L3, &["F-1302"], ""),
                       Expect::Violation(L3), &Keep::only(&ab, &[L3])));
        out.push(check_keep("excl-redaction-marker-as-built-F1302-tomb-live", meta("M-03", "excl", "redaction-marker", o.objects(), "as-built", "safety", L5, &["F-1302"], ""),
                       Expect::Violation(L5), &Keep::only(&ab, &[L5])));
    }
    out.extend(instance_checks(&EraserNoHeadLock));
    out.extend(instance_checks(&AdjacencyWriterLock));
    out.extend(instance_checks(&AdjacencyNoLockMark));
    out.extend(instance_checks(&Bm25WriteLock));
    out.extend(instance_checks(&PlanBuildLock));
    out.extend(instance_checks(&ModeSwitch));
    // generic controls: mutants of the reviewed redaction-marker programs, one per law
    let o = &RedactionMarker;
    let ctl = |id: &str, law: &'static str, progs: Progs| {
        let m = Machine { o, progs };
        check_keep(id, meta("M-03", "excl", "redaction-marker", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    let bad_lock = vec![vec![LockXBad, Write, Unlock], vec![LockX, Write, Unlock]];
    out.push(ctl("excl-control-C1-lock-admits-two", L1, bad_lock));
    out.push(ctl("excl-control-C2-writer-without-lock", L2, vec![redact_reviewed(0), vec![CheckNoMarker(0), MakeLive(0)]]));
    out.push(ctl("excl-control-C3-check-before-lock", L3, vec![
        vec![CheckNotLive(0), LockX, CheckNoMarkerAny, SetMarker(0), Tomb(0), Unlock, LockX, CheckNotLive(0), ClearOwn, Unlock], commit_into(0)]));
    out.push(ctl("excl-control-C4-clear-any", L4, vec![
        vec![LockX, CheckNoMarkerAny, CheckNotLive(0), SetMarker(0), Tomb(0), Unlock, LockX, ClearAny, Unlock],
        vec![LockX, CheckNotLive(1), Tomb(1), Unlock, LockX, ClearAny, Unlock]]));
    out.push(ctl("excl-control-C5-tomb-without-check", L5, vec![vec![LockX, SetMarker(0), Tomb(0), Unlock], vec![LockX, MakeLive(0), Unlock]]));
    let rv = Machine { o, progs: o.reviewed() };
    let sm = || meta("M-03", "excl", "redaction-marker", RedactionMarker.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("excl-sharp-redaction-finishes", sm(), &rv, "never: target 0 tombstoned, not live, unmarked, run done",
                   |s: &S| s.tomb[0] && !s.live[0] && s.marker.is_none() && s.pc[0] == Pc::Done));
    out.push(reach("excl-sharp-commit-refused-by-marker", sm(), &rv, "never: the commit refused by the marker",
                   |s: &S| s.pc[2] == Pc::Refused));
    out.push(reach("excl-sharp-run-refused-live", sm(), &rv, "never: a redaction refused because its target is live",
                   |s: &S| s.pc[0] == Pc::Refused && s.live[0]));
    out
}
