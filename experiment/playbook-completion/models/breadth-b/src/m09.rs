//! Module 09 (native Cypher executor) models at pin 3eaa79cf.
//!
//! # Machine `planc`: the compiled-plan cache (spec 257, ADR-0014)
//!
//! Abstracted real state (iris_src/src/Graph/KG/Cypher/Gen.cls):
//! - entry `^IVG.CypherCompiled(h) = $LB(class, shape, stamp, status, began)` and its lines `(h, "src", i)`
//!   (:13-16, written by `For` :79-89, by `Build` :207/:210/:215); here `Entry { shape, status, named, src }` where
//!   `shape = None` is an entry whose element 2 is undefined (`Set $List(g, 4)` on a killed node pads elements 2-3,
//!   P-0907) and `named` is element 1 set to the class name; the stamp is constant (no deploy inside the run);
//! - the generated class `IVGC.P<h>` (:186-206): which shape's lines it was compiled from, and the drop epoch the
//!   lines were written in (ghost);
//! - the build lock `Lock +^IVG.CypherCompiled(h):0` (:166, released :172/:180/:220);
//! - build jobs (`Job ##class(Graph.KG.Cypher.Gen).Build(tH, tDigest)` :96) with the digest of the lines their
//!   reader wrote (:91, the R311 digest check :175-182);
//! - readers: two processes, reader r reads plan shape r. `Exec.RunA` asks `Gen.For` once per run (Exec.cls:158) and
//!   calls `$ClassMethod(tGen, "Walk1", ...)` once per anchor (Exec.cls:199, :258); here two anchors per read;
//! - `DropAll` (:225-230): `$System.OBJ.DeletePackage` then `Kill ^IVG.CypherCompiled`, no lock; at most one.
//! The hash: `tH = $ZCRC(tShape, 7)` (:69), a CRC-32 (P-0901). `collide` puts both shapes on one hash (a CRC-32
//! collision, which the live check b-09-f0901-collision constructs); otherwise each shape has its own entry.
//! `For` is one atomic step (it holds no lock; making it atomic can hide interleavings, never add one). Job mode only
//! (the default, :17-19); sync mode builds the same way inside the reader.
//!
//! Designs:
//! - `AsBuilt`: as above. `For`: an entry of this shape that is "ok" and names `IVGC.P<h>` runs it (:71-74); a
//!   "pending" entry with a live job is left (:77); anything else (absent, another shape, a dead job's pending) is
//!   overwritten as pending with this shape's lines and a job is started (:80-98). An entry with an undefined
//!   element 2 makes `$List(tE, 2)` raise (:71): `RunA` catches it and interprets (Exec.cls:157-166), every time.
//!   `Build`: lock or leave (:166-167); leave unless the entry is pending with lines (:170-173); refuse lines whose
//!   digest is not its own (:175-182); compile the class from the lines it merged (:183-206); then set element 1 and
//!   status "ok" on whatever entry the hash holds now (:207), re-creating a killed one.
//! - `Reviewed` (F-0901 remedy: name the class by a wider digest, here one entry per shape; F-0905 remedy: DropAll
//!   takes each entry's lock, Build re-checks under its lock that its entry still exists and holds the shape it
//!   compiled, otherwise deletes the class it made; For reads with $ListGet).
//! - `ControlSharedName`: Reviewed with the shared 32-bit name (the collision back).
//! - `ControlDropNoLock`: Reviewed with an unlocked DropAll.
//!
//! Invariants: NAT-I3 (a read never runs code written for another plan shape; ghost `wrong`), NAT-T5.16 binding (an
//! "ok" entry's class was compiled from that entry's shape), NAT-I5 (after a DropAll no plan written before it is
//! left; ghost epochs) and P-0907 shape (no entry with an undefined element). Progress (AG EF): each read shape can
//! still come to run compiled (ADR-0014: a shape is compiled once and reused).
//!
//! # Machine `mode`: which compile mode a read builds in (F-0903)
//!
//! `Gen.Effective` (:41-44) answers `$Get(^||IVG.CypherGenMode, $Get(^IVG.CypherGen("mode"), "job"))` unchecked;
//! `For` quits for "off" (:64), jobs for "job" (:92-99), builds in the reader for anything else (:101). `Mode`
//! (:28-39) validates the process value. Namespace values: undefined, job, sync, off, and an unknown text ("OFF").
//! Action properties: NAT-X12 (a namespace mode other than job/sync/off is refused: such a read builds nothing,
//! never in the reader), NAT-X11 (set other leaves the process mode unchanged), NAT-B5.2 (process value first).
//!
//! # Machine `used`: the interpreter's used-relationship set (F-0902)
//!
//! Pattern (a)-[:T]->(h)<-[:T]-(c) over two relationships e0 = (x1,T,hub) and e1 = (x2,T,hub): both hops share the
//! type, so a match keeps its relationships' identity. `Exec.Neighbours` keeps the used ones as a string of
//! `$ZCRC($LB(src, p, dst, ekey), 7)` values and skips a neighbour whose hash is in it (Exec.cls:1243-1245); the
//! compiled walk compares endpoints, type and key exactly (Gen.cls:410-433). Initial states: every hash assignment
//! of e0, e1 into two values (collision or not). Invariant NAT-B1.11 (two different relationships in one match are
//! never taken as the same one): a finished walk counts the reference number of matches (2: (x1,h,x2), (x2,h,x1)).
//!
//! # Machine `gate`: the native gate and the label index (F-0906)
//!
//! Facts: `idx_edges_adj` and `idx_labels_adj` functional or absent (schema.py:769-782, :863-899). The engine's
//! label writers write `^KG("label")` themselves only when the edge index is not functional (the engine decides by
//! `_adjacency_indexed`, engine.py:703-724); the label index writes it from the row when it is functional (P-0902).
//! The gate opens on the edge index alone (native_plan.py:528-529). A native read answers labels from ^KG
//! (Exec.cls:206-266, :908-918), the SQL path from the rows. `ensure_adjacency_index` declares the edge index first
//! and the label index second (schema.py:863-899): a failure in between is the state edge-only.
//! Action property NAT-I1 / NAT-B1: a native read's label answer equals the SQL path's.
use breadth_b::*;
use explorer::*;

// ------------------------------------------------------------------------------------------------ planc

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum PDesign { AsBuilt, Reviewed, ControlSharedName, ControlDropNoLock }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum St { Pending, Ok, Refused }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Entry {
    /// element 2; None = undefined element (P-0907)
    pub shape: Option<u8>,
    pub status: St,
    /// element 1 names IVGC.P<h>
    pub named: bool,
    /// whose lines ("src") the entry holds, and the drop epoch they were written in
    pub src: Option<(u8, u8)>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum JobPc { Start, Compiling { lines: u8, epoch: u8 }, Written { lines: u8, epoch: u8 } }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Job { pub slot: u8, pub digest: u8, pub pc: JobPc }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum RPc { Idle, Walking { gen: Option<u8>, left: u8 } }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct PS {
    pub entry: [Option<Entry>; 2],
    /// class IVGC.P<slot>: (shape its lines were, epoch they were written in)
    pub class: [Option<(u8, u8)>; 2],
    /// lock holder: job index
    pub lock: [Option<u8>; 2],
    pub jobs: [Option<Job>; 2],
    pub reader: [RPc; 2],
    /// ghost: reader r ran a walk compiled for another shape
    pub wrong: [bool; 2],
    /// ghost: reader r's For raised on a broken entry (interpreted)
    pub raised: [bool; 2],
    /// drop epoch (completed DropAll count) and DropAll progress: 0 idle, 1 classes deleted (as-built), 2 done
    pub epoch: u8,
    pub drop_pc: u8,
}

#[derive(Clone, Copy, Debug)]
pub enum PA {
    For(u8),
    Walk(u8),
    JobLock(u8),
    JobCompile(u8),
    JobWrite(u8),
    DropDelete,
    DropKill,
    DropLocked,
}

pub struct Planc {
    pub design: PDesign,
    pub shapes: u8,
    pub collide: bool,
    pub drops: u8,
}

impl Planc {
    fn slot(&self, r: u8) -> usize {
        let shared = match self.design {
            PDesign::AsBuilt | PDesign::ControlSharedName => self.collide,
            PDesign::Reviewed | PDesign::ControlDropNoLock => false,
        };
        if shared { 0 } else { r as usize }
    }
    fn reviewed_build(&self) -> bool { matches!(self.design, PDesign::Reviewed | PDesign::ControlSharedName | PDesign::ControlDropNoLock) }
    fn locked_drop(&self) -> bool { matches!(self.design, PDesign::Reviewed | PDesign::ControlSharedName) }
    fn listget(&self) -> bool { self.reviewed_build() }
}

pub const P_I3: &str = "NAT-I3: a read never runs code written for another plan shape";
pub const P_BIND: &str = "NAT-T5.16: an ok entry runs the class compiled from its own shape";
pub const P_I5: &str = "NAT-I5: after a DropAll no plan written before it is left";
pub const P_SHAPE: &str = "P-0907: no entry has an undefined element";
pub const P_PROGRESS: &str = "AG EF: each read shape can still come to run compiled";
pub const W_OK: &str = "never: an ok entry whose class holds its own shape";
pub const W_COMPILED_READ: &str = "never: a read walks its anchors compiled";
pub const W_DROP: &str = "never: a DropAll completes";

fn ok_compiled(s: &PS, slot: usize, r: u8) -> bool {
    matches!(s.entry[slot], Some(Entry { shape: Some(x), status: St::Ok, named: true, .. }) if x == r)
        && matches!(s.class[slot], Some((c, _)) if c == r)
}

impl Model for Planc {
    type State = PS;
    type Action = PA;
    fn init_states(&self) -> Vec<PS> {
        vec![PS { entry: [None; 2], class: [None; 2], lock: [None; 2], jobs: [None; 2], reader: [RPc::Idle; 2],
                  wrong: [false; 2], raised: [false; 2], epoch: 0, drop_pc: 0 }]
    }
    fn actions(&self, _: &PS) -> Vec<PA> {
        let mut v = vec![];
        for r in 0..self.shapes { v.push(PA::For(r)); v.push(PA::Walk(r)); }
        for j in 0..2 { v.push(PA::JobLock(j)); v.push(PA::JobCompile(j)); v.push(PA::JobWrite(j)); }
        if self.drops > 0 { v.push(PA::DropDelete); v.push(PA::DropKill); v.push(PA::DropLocked); }
        v
    }
    fn next(&self, s: &PS, a: &PA) -> Option<PS> {
        let mut t = s.clone();
        match *a {
            PA::For(r) => {
                let ri = r as usize;
                if s.reader[ri] != RPc::Idle { return None; }
                let slot = self.slot(r);
                let mut gen = None;
                let e = s.entry[slot];
                let job_alive = s.jobs.iter().any(|j| matches!(j, Some(j) if j.slot as usize == slot));
                let mut write = true;
                if let Some(e) = e {
                    match e.shape {
                        None if !self.listget() => {
                            // $List(tE, 2) on an undefined element raises; RunA interprets (Exec.cls:157-166)
                            t.raised[ri] = true;
                            write = false;
                        }
                        Some(x) if x == r => {
                            match e.status {
                                St::Ok => { if e.named { gen = Some(slot as u8); } write = false; }
                                St::Refused => { write = false; }
                                St::Pending => { if job_alive { write = false; } }
                            }
                        }
                        _ => {}
                    }
                }
                if write {
                    t.entry[slot] = Some(Entry { shape: Some(r), status: St::Pending, named: false, src: Some((r, s.epoch)) });
                    // one attempt to start a job; none free leaves the entry pending (reclaimed when no job lives)
                    if let Some(j) = t.jobs.iter().position(|j| j.is_none()) {
                        t.jobs[j] = Some(Job { slot: slot as u8, digest: r, pc: JobPc::Start });
                    }
                }
                t.reader[ri] = RPc::Walking { gen, left: 2 };
            }
            PA::Walk(r) => {
                let ri = r as usize;
                let RPc::Walking { gen, left } = s.reader[ri] else { return None };
                if let Some(slot) = gen {
                    match s.class[slot as usize] {
                        Some((c, _)) => { if c != r { t.wrong[ri] = true; } }
                        // the class was deleted under a running read: the native run fails, SQL answers (NAT-T5.26)
                        None => { t.reader[ri] = RPc::Idle; return Some(t); }
                    }
                }
                t.reader[ri] = if left > 1 { RPc::Walking { gen, left: left - 1 } } else { RPc::Idle };
            }
            PA::JobLock(j) => {
                let ji = j as usize;
                let Some(job) = s.jobs[ji] else { return None };
                if job.pc != JobPc::Start { return None; }
                let slot = job.slot as usize;
                if s.lock[slot].is_some() { t.jobs[ji] = None; return Some(t); } // Lock +..:0 failed: leave
                // a locked DropAll in progress cannot be overtaken (it holds every entry's lock)
                if self.locked_drop() && s.drop_pc == 1 { return None; }
                match s.entry[slot] {
                    Some(Entry { status: St::Pending, src: Some((lines, ep)), .. }) => {
                        if lines != job.digest {
                            // the R311 digest check: lines that are not the ones written for it
                            if let Some(e) = t.entry[slot].as_mut() { e.status = St::Refused; }
                            t.jobs[ji] = None;
                        } else {
                            t.lock[slot] = Some(j);
                            t.jobs[ji] = Some(Job { pc: JobPc::Compiling { lines, epoch: ep }, ..job });
                        }
                    }
                    _ => { t.jobs[ji] = None; }
                }
            }
            PA::JobCompile(j) => {
                let ji = j as usize;
                let Some(job) = s.jobs[ji] else { return None };
                let JobPc::Compiling { lines, epoch } = job.pc else { return None };
                t.class[job.slot as usize] = Some((lines, epoch));
                t.jobs[ji] = Some(Job { pc: JobPc::Written { lines, epoch }, ..job });
            }
            PA::JobWrite(j) => {
                let ji = j as usize;
                let Some(job) = s.jobs[ji] else { return None };
                let JobPc::Written { lines, .. } = job.pc else { return None };
                let slot = job.slot as usize;
                if self.reviewed_build() {
                    // re-check under the lock: the entry still exists and holds the shape these lines were for
                    match t.entry[slot].as_mut() {
                        Some(e) if e.shape == Some(lines) && e.status == St::Pending => { e.named = true; e.status = St::Ok; }
                        _ => { t.class[slot] = None; } // delete the class it made
                    }
                } else {
                    match t.entry[slot].as_mut() {
                        Some(e) => { e.named = true; e.status = St::Ok; }
                        // Set $List(^IVG.CypherCompiled(pH), 1/4) on a killed node: $LB(class, , , "ok")
                        None => { t.entry[slot] = Some(Entry { shape: None, status: St::Ok, named: true, src: None }); }
                    }
                }
                t.lock[slot] = None;
                t.jobs[ji] = None;
            }
            PA::DropDelete => {
                if self.locked_drop() || s.drop_pc != 0 || s.epoch >= self.drops { return None; }
                t.class = [None; 2];
                t.drop_pc = 1;
            }
            PA::DropKill => {
                if self.locked_drop() || s.drop_pc != 1 { return None; }
                t.entry = [None; 2];
                t.drop_pc = 0;
                t.epoch += 1;
            }
            PA::DropLocked => {
                // reviewed: take every entry's lock (wait for builds holding one), delete classes and entries
                if !self.locked_drop() || s.epoch >= self.drops { return None; }
                if s.lock.iter().any(|l| l.is_some()) { return None; }
                t.class = [None; 2];
                t.entry = [None; 2];
                t.epoch += 1;
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<PS>> {
        vec![
            invariant(P_I3, |s: &PS| !s.wrong[0] && !s.wrong[1]),
            invariant(P_BIND, |s: &PS| (0..2).all(|k| match (s.entry[k], s.class[k]) {
                (Some(Entry { shape: Some(x), status: St::Ok, named: true, .. }), Some((c, _))) => c == x,
                _ => true,
            })),
            invariant(P_I5, |s: &PS| s.drop_pc != 0 || s.epoch == 0 || (0..2).all(|k| match s.class[k] {
                Some((_, ep)) => ep == s.epoch,
                None => true,
            })),
            invariant(P_SHAPE, |s: &PS| s.entry.iter().all(|e| !matches!(e, Some(Entry { shape: None, .. })))),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<PS>> {
        let shapes = self.shapes;
        let slots: Vec<usize> = (0..shapes).map(|r| self.slot(r)).collect();
        vec![invariant(P_PROGRESS, move |s: &PS| (0..shapes).all(|r| ok_compiled(s, slots[r as usize], r)))]
    }
}

fn w_ok(s: &PS) -> bool { (0..2).any(|k| ok_compiled(s, k, k as u8)) }
fn w_compiled_read(s: &PS) -> bool {
    s.reader.iter().enumerate().any(|(r, p)| matches!(p, RPc::Walking { gen: Some(_), left: 1 }) && !s.wrong[r])
}
fn w_drop(s: &PS) -> bool { s.epoch >= 1 && s.drop_pc == 0 }

pub fn show_planc(c: &Counterexample<PS, PA>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<16} entry={:?} class={:?} lock={:?} jobs={:?} readers={:?} wrong={:?} raised={:?} epoch={} drop_pc={}\n",
            i + 1, format!("{:?}", a), s.entry, s.class, s.lock, s.jobs, s.reader, s.wrong, s.raised, s.epoch, s.drop_pc);
    }
    out
}

// ------------------------------------------------------------------------------------------------ mode

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum MDesign { AsBuilt, Reviewed, ControlUnknownJob }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum MV { Undef, Job, Sync, Off, Unknown }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Built { Nothing, Background, InReader }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct MS { pub ns: MV, pub proc_: MV, pub last: Option<(MV, Built)> }

#[derive(Clone, Copy, Debug)]
pub enum MA { SetNs(MV), SetProc(MV), ClearProc, Read }

pub struct ModeM { pub design: MDesign }

pub const M_X12: &str = "NAT-X12: a read under an unknown namespace mode builds nothing";
pub const M_X11: &str = "NAT-X11: set other leaves the process mode unchanged";
pub const M_B52: &str = "NAT-B5.2: the process mode wins over the namespace mode";
pub const W_SYNC: &str = "never: a read builds in the reader's process";

const MVS: [MV; 5] = [MV::Undef, MV::Job, MV::Sync, MV::Off, MV::Unknown];

impl Model for ModeM {
    type State = MS;
    type Action = MA;
    fn init_states(&self) -> Vec<MS> { vec![MS { ns: MV::Undef, proc_: MV::Undef, last: None }] }
    fn actions(&self, _: &MS) -> Vec<MA> {
        let mut v = vec![MA::Read, MA::ClearProc];
        for m in MVS { v.push(MA::SetNs(m)); if m != MV::Undef { v.push(MA::SetProc(m)); } }
        v
    }
    fn next(&self, s: &MS, a: &MA) -> Option<MS> {
        let mut t = s.clone();
        t.last = None;
        match *a {
            // a plain global Set (docs/ADMIN_GUIDE.md:774-779): any text
            MA::SetNs(m) => t.ns = m,
            // Gen.Mode validates (:28-39): another value throws, nothing changes
            MA::SetProc(m) => { if m != MV::Unknown { t.proc_ = m; } }
            MA::ClearProc => t.proc_ = MV::Undef,
            MA::Read => {
                let eff = if s.proc_ != MV::Undef { s.proc_ } else if s.ns != MV::Undef { s.ns } else { MV::Job };
                let built = match (self.design, eff) {
                    (_, MV::Off) => Built::Nothing,
                    (_, MV::Job) => Built::Background,
                    (_, MV::Sync) => Built::InReader,
                    (MDesign::AsBuilt, _) => Built::InReader,      // :101 builds for every other value
                    (MDesign::Reviewed, _) => Built::Nothing,       // unknown: off, logged once
                    (MDesign::ControlUnknownJob, _) => Built::Background,
                };
                t.last = Some((eff, built));
            }
        }
        Some(t)
    }
    fn action_properties(&self) -> Vec<ActionProperty<MS, MA>> {
        vec![
            action_property(M_X12, |_: &MS, a: &MA, t: &MS| !matches!(a, MA::Read) || !matches!(t.last, Some((MV::Unknown, b)) if b != Built::Nothing)),
            action_property(M_X11, |s: &MS, a: &MA, t: &MS| !matches!(a, MA::SetProc(MV::Unknown)) || s.proc_ == t.proc_),
            action_property(M_B52, |s: &MS, a: &MA, t: &MS| !matches!(a, MA::Read) || s.proc_ == MV::Undef || matches!(t.last, Some((e, _)) if e == s.proc_)),
        ]
    }
}

// ------------------------------------------------------------------------------------------------ used

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum UDesign { AsBuilt, Reviewed, ControlTypeOnly }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct US {
    /// hash of e0 and e1 ($ZCRC of $LB(src, p, dst, ekey)); equal = a CRC-32 collision
    pub h: [u8; 2],
    /// anchor index (0: x1, 1: x2, 2: done)
    pub a: u8,
    /// stage: 0 first hop, 1 second hop over candidate `c`
    pub stage: u8,
    pub c: u8,
    pub matches: u8,
    pub done: bool,
}

#[derive(Clone, Copy, Debug)]
pub enum UA { Step }

pub struct Used { pub design: UDesign }

pub const U_B111: &str = "NAT-B1.11: two different relationships in one match are never taken as the same one";
pub const W_DONE: &str = "never: the walk finishes";

impl Model for Used {
    type State = US;
    type Action = UA;
    fn init_states(&self) -> Vec<US> {
        let mut v = vec![];
        for h0 in 0..2u8 { for h1 in 0..2u8 { v.push(US { h: [h0, h1], a: 0, stage: 0, c: 0, matches: 0, done: false }); } }
        v
    }
    fn actions(&self, _: &US) -> Vec<UA> { vec![UA::Step] }
    fn next(&self, s: &US, _: &UA) -> Option<US> {
        if s.done { return None; }
        let mut t = s.clone();
        if s.a >= 2 { t.done = true; return Some(t); }
        // anchor a (x1 or x2): first hop takes edge e_a (a -> hub); second hop walks hub's in-edges e_c, c in {0, 1}
        if s.stage == 0 { t.stage = 1; t.c = 0; return Some(t); }
        let first = s.a as usize;
        let second = s.c as usize;
        let same = match self.design {
            UDesign::AsBuilt => s.h[first] == s.h[second],           // pUsed[(","_tEdge_",")
            UDesign::Reviewed => first == second,                   // exact identity (the compiled walk's rule)
            UDesign::ControlTypeOnly => true,                       // mutant: identity by type only
        };
        if !same { t.matches += 1; }
        if s.c == 1 { t.a += 1; t.stage = 0; t.c = 0; } else { t.c = 1; }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<US>> {
        vec![invariant(U_B111, |s: &US| !s.done || s.matches == 2)]
    }
}

// ------------------------------------------------------------------------------------------------ gate

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum GDesign { AsBuilt, Reviewed, ControlAlwaysOpen }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct GS {
    pub edge_idx: bool,
    pub label_idx: bool,
    /// node n's label: in the rdf_labels row, in ^KG("label")
    pub row: bool,
    pub kg: bool,
    pub writes: u8,
    /// last native read: (gate open, native answer, SQL answer)
    pub last: Option<(bool, bool, bool)>,
}

#[derive(Clone, Copy, Debug)]
pub enum GAc { EnsurePartial, EnsureFull, AddLabel, RemoveLabel, Read }

pub struct Gate { pub design: GDesign }

pub const G_I1: &str = "NAT-I1: a native read answers labels as the SQL path does";
pub const W_GATE_READ: &str = "never: a native read runs with the gate open after a label write";

impl Model for Gate {
    type State = GS;
    type Action = GAc;
    fn init_states(&self) -> Vec<GS> {
        vec![GS { edge_idx: false, label_idx: false, row: false, kg: false, writes: 0, last: None }]
    }
    fn actions(&self, _: &GS) -> Vec<GAc> { vec![GAc::EnsurePartial, GAc::EnsureFull, GAc::AddLabel, GAc::RemoveLabel, GAc::Read] }
    fn within_bounds(&self, s: &GS) -> bool { s.writes <= 3 }
    fn next(&self, s: &GS, a: &GAc) -> Option<GS> {
        let mut t = s.clone();
        t.last = None;
        match a {
            // ensure_adjacency_index stopped after the edge index (schema.py:863-899)
            GAc::EnsurePartial => { if s.edge_idx { return None; } t.edge_idx = true; }
            // both declared; declaring the label index builds ^KG("label") from the rows
            GAc::EnsureFull => { if s.edge_idx && s.label_idx { return None; } t.edge_idx = true; t.label_idx = true; t.kg = s.row; }
            GAc::AddLabel | GAc::RemoveLabel => {
                let v = matches!(a, GAc::AddLabel);
                if s.row == v { return None; }
                t.row = v;
                t.writes += 1;
                // the row's own index keeps ^KG where declared; the engine writes ^KG itself only without the edge index
                if s.label_idx || !s.edge_idx { t.kg = v; }
            }
            GAc::Read => {
                let open = match self.design {
                    GDesign::AsBuilt => s.edge_idx,
                    GDesign::Reviewed => s.edge_idx && s.label_idx,
                    GDesign::ControlAlwaysOpen => true,
                };
                let native = if open { s.kg } else { s.row };
                t.last = Some((open, native, s.row));
            }
        }
        Some(t)
    }
    fn action_properties(&self) -> Vec<ActionProperty<GS, GAc>> {
        vec![action_property(G_I1, |_: &GS, _: &GAc, t: &GS| !matches!(t.last, Some((_, n, q)) if n != q))]
    }
}

fn w_gate_read(s: &GS) -> bool { matches!(s.last, Some((true, n, q)) if n == q) && s.writes > 0 }

// ------------------------------------------------------------------------------------------------ checks

pub fn checks() -> Vec<(&'static str, Box<dyn Fn() -> Outcome>)> {
    let pc = |design, shapes, collide, drops| Planc { design, shapes, collide, drops };
    vec![
        // planc: F-0901 (two colliding shapes)
        check("m09-planc-as-built-collide-I3", move || judge("m09-planc-as-built-collide-I3", "09", "planc", "as-built",
            Expect::Violation(P_I3), "F-0901; NAT-I3, ADR-0014: a read mid-walk runs the other shape's rebuilt class",
            explore(&Only::new(pc(PDesign::AsBuilt, 2, true, 0), &[P_I3]), limits()), show_planc)),
        check("m09-planc-as-built-collide-binding", move || judge("m09-planc-as-built-collide-binding", "09", "planc", "as-built",
            Expect::Violation(P_BIND), "F-0901, F-C0901: Build marks the entry the hash holds now ok for the class it compiled from the other shape",
            explore(&Only::new(pc(PDesign::AsBuilt, 2, true, 0), &[P_BIND]), limits()), show_planc)),
        check("m09-planc-as-built-collide-progress", move || judge("m09-planc-as-built-collide-progress", "09", "planc", "as-built",
            Expect::Violation(P_PROGRESS), "F-0901: two colliding shapes can never both run compiled (each read overwrites the other's entry)",
            explore(&Only::new(pc(PDesign::AsBuilt, 2, true, 0), &[P_PROGRESS]), limits()), show_planc)),
        // planc: F-0905 (DropAll during a build), one shape
        check("m09-planc-as-built-drop-shape", move || judge("m09-planc-as-built-drop-shape", "09", "planc", "as-built",
            Expect::Violation(P_SHAPE), "F-0905; P-0907: a build finishing after DropAll re-creates $LB(class,,,\"ok\")",
            explore(&Only::new(pc(PDesign::AsBuilt, 1, false, 1), &[P_SHAPE]), limits()), show_planc)),
        check("m09-planc-as-built-drop-I5", move || judge("m09-planc-as-built-drop-I5", "09", "planc", "as-built",
            Expect::Violation(P_I5), "F-0905; NAT-I5, NAT-T5.22: a class compiled from lines written before the drop survives it",
            explore(&Only::new(pc(PDesign::AsBuilt, 1, false, 1), &[P_I5]), limits()), show_planc)),
        check("m09-planc-as-built-drop-progress", move || judge("m09-planc-as-built-drop-progress", "09", "planc", "as-built",
            Expect::Violation(P_PROGRESS), "F-0905: the broken entry keeps its shape interpreted until the next DropAll",
            explore(&Only::new(pc(PDesign::AsBuilt, 1, false, 1), &[P_PROGRESS]), limits()), show_planc)),
        // planc: reviewed and controls
        check("m09-planc-reviewed", move || judge("m09-planc-reviewed", "09", "planc", "reviewed", Expect::Pass,
            "F-0901/F-0905 remedies: per-shape class name, locked DropAll, Build re-check, $ListGet; NAT-I3, T5.16, I5, P-0907, AG EF",
            explore(&pc(PDesign::Reviewed, 2, true, 1), limits()), show_planc)),
        check("m09-planc-control-shared-name", move || judge("m09-planc-control-shared-name", "09", "planc", "control",
            Expect::Violation(P_I3), "mutant: reviewed with the 32-bit shared class name",
            explore(&Only::new(pc(PDesign::ControlSharedName, 2, true, 1), &[P_I3]), limits()), show_planc)),
        check("m09-planc-control-drop-nolock", move || judge("m09-planc-control-drop-nolock", "09", "planc", "control",
            Expect::Violation(P_I5), "mutant: reviewed with an unlocked DropAll",
            explore(&Only::new(pc(PDesign::ControlDropNoLock, 2, true, 1), &[P_I5]), limits()), show_planc)),
        check("m09-planc-positive-ok", move || judge("m09-planc-positive-ok", "09", "planc", "positive", Expect::Violation(W_OK),
            "sharpness: an ok entry whose class holds its own shape is reachable (reviewed)",
            explore(&Only::new(pc(PDesign::Reviewed, 2, true, 1), &[]).witness(W_OK, w_ok), limits()), show_planc)),
        check("m09-planc-positive-compiled-read", move || judge("m09-planc-positive-compiled-read", "09", "planc", "positive",
            Expect::Violation(W_COMPILED_READ), "sharpness: a read walks compiled (reviewed)",
            explore(&Only::new(pc(PDesign::Reviewed, 2, true, 1), &[]).witness(W_COMPILED_READ, w_compiled_read), limits()), show_planc)),
        check("m09-planc-positive-drop", move || judge("m09-planc-positive-drop", "09", "planc", "positive", Expect::Violation(W_DROP),
            "sharpness: a DropAll completes (reviewed, it waits for builds)",
            explore(&Only::new(pc(PDesign::Reviewed, 2, true, 1), &[]).witness(W_DROP, w_drop), limits()), show_planc)),
        check("m09-planc-as-built-single-pass", move || judge("m09-planc-as-built-single-pass", "09", "planc", "as-built", Expect::Pass,
            "as built without collision or drop: NAT-I3, T5.16, I5, P-0907 and progress hold for one shape (the defects need a collision or a drop)",
            explore(&pc(PDesign::AsBuilt, 1, false, 0), limits()), show_planc)),
        // mode: F-0903
        check("m09-mode-as-built", || judge("m09-mode-as-built", "09", "mode", "as-built", Expect::Violation(M_X12),
            "F-0903; NAT-X12: an unknown namespace mode builds in the reader (sync)",
            explore(&Only::new(ModeM { design: MDesign::AsBuilt }, &[M_X12]), limits()), show_debug)),
        check("m09-mode-reviewed", || judge("m09-mode-reviewed", "09", "mode", "reviewed", Expect::Pass,
            "F-0903 remedy: unknown namespace mode taken as off; NAT-X12, X11, B5.2",
            explore(&ModeM { design: MDesign::Reviewed }, limits()), show_debug)),
        check("m09-mode-as-built-X11-B52", || judge("m09-mode-as-built-X11-B52", "09", "mode", "as-built", Expect::Pass,
            "NAT-X11 and NAT-B5.2 hold as built (Mode validates the process value)",
            explore(&Only::new(ModeM { design: MDesign::AsBuilt }, &[M_X11, M_B52]), limits()), show_debug)),
        check("m09-mode-control-unknown-job", || judge("m09-mode-control-unknown-job", "09", "mode", "control", Expect::Violation(M_X12),
            "mutant: unknown namespace mode taken as job",
            explore(&ModeM { design: MDesign::ControlUnknownJob }, limits()), show_debug)),
        check("m09-mode-positive-sync", || judge("m09-mode-positive-sync", "09", "mode", "positive", Expect::Violation("never: a read builds in the reader's process"),
            "sharpness: a valid sync mode builds in the reader (reviewed)",
            explore(&ModeWitness, limits()), show_debug)),
        // used: F-0902
        check("m09-used-as-built", || judge("m09-used-as-built", "09", "used", "as-built", Expect::Violation(U_B111),
            "F-0902; NAT-B1.11: a CRC-32 collision of two relationships drops valid matches",
            explore(&Used { design: UDesign::AsBuilt }, limits()), show_debug)),
        check("m09-used-reviewed", || judge("m09-used-reviewed", "09", "used", "reviewed", Expect::Pass,
            "F-0902 remedy: exact relationship identity (as the compiled walk, Gen.cls:410-433)",
            explore(&Used { design: UDesign::Reviewed }, limits()), show_debug)),
        check("m09-used-control-type-only", || judge("m09-used-control-type-only", "09", "used", "control", Expect::Violation(U_B111),
            "mutant: relationships told apart by type only", explore(&Used { design: UDesign::ControlTypeOnly }, limits()), show_debug)),
        check("m09-used-positive-done", || judge("m09-used-positive-done", "09", "used", "positive", Expect::Violation(W_DONE),
            "sharpness: the walk finishes", explore(&Only::new(Used { design: UDesign::Reviewed }, &[]).witness(W_DONE, |s: &US| s.done), limits()), show_debug)),
        // gate: F-0906
        check("m09-gate-as-built", || judge("m09-gate-as-built", "09", "gate", "as-built", Expect::Violation(G_I1),
            "F-0906; NAT-I1: gate open on the edge index alone, labels read from a ^KG no writer keeps",
            explore(&Gate { design: GDesign::AsBuilt }, limits()), show_debug)),
        check("m09-gate-reviewed", || judge("m09-gate-reviewed", "09", "gate", "reviewed", Expect::Pass,
            "F-0906 remedy: the gate also requires the label index", explore(&Gate { design: GDesign::Reviewed }, limits()), show_debug)),
        check("m09-gate-control-always-open", || judge("m09-gate-control-always-open", "09", "gate", "control", Expect::Violation(G_I1),
            "mutant: gate always open", explore(&Gate { design: GDesign::ControlAlwaysOpen }, limits()), show_debug)),
        check("m09-gate-positive-read", || judge("m09-gate-positive-read", "09", "gate", "positive", Expect::Violation(W_GATE_READ),
            "sharpness: a native read with the gate open after a label write (reviewed)",
            explore(&Only::new(Gate { design: GDesign::Reviewed }, &[]).witness(W_GATE_READ, w_gate_read), limits()), show_debug)),
    ]
}

/// The mode machine (reviewed) with the witness "never builds in the reader" as an action property.
struct ModeWitness;
impl Model for ModeWitness {
    type State = MS;
    type Action = MA;
    fn init_states(&self) -> Vec<MS> { ModeM { design: MDesign::Reviewed }.init_states() }
    fn actions(&self, s: &MS) -> Vec<MA> { ModeM { design: MDesign::Reviewed }.actions(s) }
    fn next(&self, s: &MS, a: &MA) -> Option<MS> { ModeM { design: MDesign::Reviewed }.next(s, a) }
    fn action_properties(&self) -> Vec<ActionProperty<MS, MA>> {
        vec![action_property(W_SYNC, |_: &MS, _: &MA, t: &MS| !matches!(t.last, Some((_, Built::InReader))))]
    }
}
