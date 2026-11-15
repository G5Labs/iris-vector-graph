//! Module 09, L2 part 1: the compiled-plan cache at pin 3eaa79cf (iris_src/src/Graph/KG/Cypher/Gen.cls), its build jobs
//! and its readers; refinement of `planc_l1` for every step, the invariant, and the controls F-0901 and F-C0901.
//!
//! Layout: `ent` (^IVG.CypherCompiled(h) = $LB(class, shape, stamp, status, began), :13-16; here shape, status and
//! class), `src` (^IVG.CypherCompiled(h, "src"): the shape whose lines are stored), `cls` (the generated classes: which
//! shape's lines each was compiled from), `locks` (Lock +^IVG.CypherCompiled(h), :166), `jobs` (build jobs, :96, with the
//! digest of the lines their reader wrote, :91), `rd` (readers: Exec.RunA asks Gen.For once per run, Exec.cls:158, and
//! calls the class's Walk1 once per anchor, Exec.cls:199, 258; two anchors here), `hash` (h = $ZCRC(shape, 7), :69: any
//! assignment, collisions included: a CRC-32 collision is constructible on demand, b-09-f0901-collision).
//!
//! Steps: `For` (:61-105, one atomic step, job mode; `restart`: a pending entry whose job died or is older than 120 s is
//! rewritten, :75-76), `Walk` (one Walk1 call; a missing class raises in Run, Exec.cls:198-199, and the engine answers by
//! SQL, query.py:2146-2152, as the interpreter does), `BLeave` (lock busy or nothing pending: :166-167, :171-173),
//! `BRefuse` (the R311 digest check, :175-182), `BCompile` (:183-205, the lock held), `BFail` (:208-214), `BMark` (:207).
//!
//! **Reviewed design** (F-0901 remedy, its "or a counter" option, and F-C0901 remedy): each build compiles a class of a
//! fresh name (`next_cls`), so a class a reader runs is never recompiled; Build marks the entry "ok" only if, under its
//! lock, the entry still holds the shape it compiled. Entries stay keyed by the 32-bit hash (two colliding shapes
//! share one entry and take turns: a progress cost, not a safety one). **As built**: the class is IVGC.P<h>
//! (`control_f0901_shared_class_name`: the class every shape of hash h runs, recompiled in place); Build sets element 1
//! and "ok" on whatever entry h holds (`control_fc0901_mark_any_entry`).
//!
//! Premises: P-P1 job mode, one namespace stamp (no deploy, no DropAll: F-0905 is not modelled here); P-P2 For is one
//! step (it holds no lock; atomicity can hide interleavings, not add them); P-P3 compiling the lines of shape s gives
//! code that answers interp(s, db) (the generator's correctness is not modelled); P-P4 an orphaned class (compiled,
//! never marked) is left in place (the remedy deletes it; harmless either way here).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::planc_l1::*;

verus! {

pub enum St { Pending, Ok, Bad }
pub struct Ent { pub shape: int, pub st: St, pub cls: Option<int> }
pub enum Ph { Started, Compiled { c: int, from: int } }
pub struct Job { pub h: int, pub dig: int, pub ph: Ph }
pub struct Rd { pub s: int, pub run: Option<int>, pub left: nat }
pub struct PC2 {
    pub db: int,
    pub hash: Map<int, int>,
    pub ent: Map<int, Ent>,
    pub src: Map<int, int>,
    pub cls: Map<int, int>,
    pub locks: Set<int>,
    pub jobs: Map<int, Job>,
    pub rd: Map<int, Rd>,
    pub next_cls: int,
}

pub enum PCL2 {
    Write { db: int },
    For { r: int, shape: int, j: int, restart: bool },
    Walk { r: int, shape: int, a: (int, int) },
    BLeave { j: int },
    BRefuse { j: int },
    BCompile { j: int },
    BFail { j: int },
    BMark { j: int },
}

pub open spec fn f0901() -> bool { cfg!(feature = "control_f0901_shared_class_name") }
pub open spec fn fc0901() -> bool { cfg!(feature = "control_fc0901_mark_any_entry") }

pub open spec fn hof(s: PC2, x: int) -> int { if s.hash.contains_key(x) { s.hash[x] } else { x } }
pub open spec fn hit(s: PC2, shape: int) -> bool { s.ent.contains_key(hof(s, shape)) && s.ent[hof(s, shape)].shape == shape }
pub open spec fn for2(s: PC2, r: int, shape: int, j: int, restart: bool) -> PC2 {
    let h = hof(s, shape);
    if hit(s, shape) && s.ent[h].st is Ok && s.ent[h].cls is Some {
        PC2 { rd: s.rd.insert(r, Rd { s: shape, run: s.ent[h].cls, left: 2 }), ..s }
    } else if hit(s, shape) && (s.ent[h].st is Bad || (s.ent[h].st is Pending && !restart)) {
        PC2 { rd: s.rd.insert(r, Rd { s: shape, run: None, left: 2 }), ..s }
    } else {
        PC2 { ent: s.ent.insert(h, Ent { shape, st: St::Pending, cls: None }), src: s.src.insert(h, shape),
              jobs: s.jobs.insert(j, Job { h, dig: shape, ph: Ph::Started }),
              rd: s.rd.insert(r, Rd { s: shape, run: None, left: 2 }), ..s }
    }
}
/// What a Walk1 call answers.
pub open spec fn answer(s: PC2, rr: Rd) -> (int, int) {
    match rr.run {
        Some(c) => if s.cls.contains_key(c) { interp(s.cls[c], s.db) } else { interp(rr.s, s.db) },
        None => interp(rr.s, s.db),
    }
}
pub open spec fn walk2(s: PC2, r: int) -> PC2 {
    let rr = s.rd[r];
    PC2 { rd: if rr.left <= 1 { s.rd.remove(r) } else { s.rd.insert(r, Rd { left: (rr.left - 1) as nat, ..rr }) }, ..s }
}
pub open spec fn started(s: PC2, j: int) -> bool { s.jobs.contains_key(j) && s.jobs[j].ph is Started }
pub open spec fn can_build(s: PC2, j: int) -> bool {
    let h = s.jobs[j].h;
    started(s, j) && !s.locks.contains(h) && s.ent.contains_key(h) && s.ent[h].st is Pending && s.src.contains_key(h)
}
/// The class a build compiles into: reviewed, a fresh name; as built, IVGC.P<h>.
pub open spec fn cid(s: PC2, h: int) -> int { if f0901() { h } else { s.next_cls } }
pub open spec fn compile2(s: PC2, j: int) -> PC2 {
    let job = s.jobs[j];
    let c = cid(s, job.h);
    PC2 { cls: s.cls.insert(c, s.src[job.h]), locks: s.locks.insert(job.h),
          jobs: s.jobs.insert(j, Job { ph: Ph::Compiled { c, from: s.src[job.h] }, ..job }), next_cls: s.next_cls + 1, ..s }
}
pub open spec fn bad2(s: PC2, j: int) -> PC2 {
    let h = s.jobs[j].h;
    PC2 { ent: s.ent.insert(h, Ent { st: St::Bad, ..s.ent[h] }), jobs: s.jobs.remove(j), ..s }
}
pub open spec fn fail2(s: PC2, j: int) -> PC2 {
    let h = s.jobs[j].h;
    PC2 { ent: s.ent.insert(h, Ent { st: St::Bad, ..s.ent[h] }), cls: if f0901() { s.cls.remove(h) } else { s.cls },
          jobs: s.jobs.remove(j), ..s }
}
/// Build's last write, under its lock: reviewed, only on the entry that still holds the shape it compiled.
pub open spec fn marks(s: PC2, j: int) -> bool {
    let job = s.jobs[j];
    s.ent.contains_key(job.h) && (fc0901() || (s.ent[job.h].shape == job.ph->from && s.ent[job.h].st is Pending))
}
pub open spec fn mark2(s: PC2, j: int) -> PC2 {
    let job = s.jobs[j];
    PC2 { ent: if marks(s, j) { s.ent.insert(job.h, Ent { st: St::Ok, cls: Some(job.ph->c), ..s.ent[job.h] }) } else { s.ent },
          locks: s.locks.remove(job.h), jobs: s.jobs.remove(j), ..s }
}

pub open spec fn init2(s: PC2) -> bool {
    s.ent == Map::<int, Ent>::empty() && s.src == Map::<int, int>::empty() && s.cls == Map::<int, int>::empty()
        && s.locks == Set::<int>::empty() && s.jobs == Map::<int, Job>::empty() && s.rd == Map::<int, Rd>::empty() && s.next_cls == 0
}

pub open spec fn step2(s: PC2, l: PCL2, t: PC2) -> bool {
    match l {
        PCL2::Write { db } => t == (PC2 { db, ..s }),
        PCL2::For { r, shape, j, restart } =>
            !s.rd.contains_key(r) && !s.jobs.contains_key(j) && t == for2(s, r, shape, j, restart),
        PCL2::Walk { r, shape, a } =>
            s.rd.contains_key(r) && s.rd[r].left > 0 && shape == s.rd[r].s && a == answer(s, s.rd[r]) && t == walk2(s, r),
        PCL2::BLeave { j } => started(s, j) && !can_build(s, j) && t == (PC2 { jobs: s.jobs.remove(j), ..s }),
        PCL2::BRefuse { j } => can_build(s, j) && s.src[s.jobs[j].h] != s.jobs[j].dig && t == bad2(s, j),
        PCL2::BCompile { j } => can_build(s, j) && s.src[s.jobs[j].h] == s.jobs[j].dig && t == compile2(s, j),
        PCL2::BFail { j } => can_build(s, j) && s.src[s.jobs[j].h] == s.jobs[j].dig && t == fail2(s, j),
        PCL2::BMark { j } => s.jobs.contains_key(j) && s.jobs[j].ph is Compiled && t == mark2(s, j),
    }
}

pub open spec fn absp(s: PC2) -> PC1 { PC1 { db: s.db } }
pub open spec fn labp(l: PCL2) -> Option<PCL1> {
    match l {
        PCL2::Write { db } => Some(PCL1::Write { db }),
        PCL2::Walk { r, shape, a } => Some(PCL1::Answer { s: shape, a }),
        _ => None,
    }
}

/// Class `c` is named below the counter, and if it exists it was compiled from shape `sh`.
pub open spec fn cok(s: PC2, c: int, sh: int) -> bool { c < s.next_cls && (s.cls.contains_key(c) ==> s.cls[c] == sh) }
/// NAT-T5.16 (an ok entry's class is its shape's), NAT-I3 for readers in flight, and the builds' classes.
pub open spec fn inv09p(s: PC2) -> bool {
    &&& forall|h: int| #[trigger] s.ent.contains_key(h) && s.ent[h].st is Ok ==>
            s.ent[h].cls is Some && cok(s, s.ent[h].cls->Some_0, s.ent[h].shape)
    &&& forall|r: int| #[trigger] s.rd.contains_key(r) && s.rd[r].run is Some ==> cok(s, s.rd[r].run->Some_0, s.rd[r].s)
    &&& forall|j: int| #[trigger] s.jobs.contains_key(j) && s.jobs[j].ph is Compiled ==> cok(s, s.jobs[j].ph->c, s.jobs[j].ph->from)
    &&& forall|c: int| #[trigger] s.cls.contains_key(c) ==> c < s.next_cls
}

pub struct PcL2;
impl Contract for PcL2 {
    type S = PC2;
    type L = PCL2;
    open spec fn init(s: PC2) -> bool { init2(s) }
    open spec fn next(s: PC2, l: PCL2, t: PC2) -> bool { inv09p(s) && step2(s, l, t) }
}
pub struct PcRaw;
impl Contract for PcRaw {
    type S = PC2;
    type L = PCL2;
    open spec fn init(s: PC2) -> bool { init2(s) }
    open spec fn next(s: PC2, l: PCL2, t: PC2) -> bool { step2(s, l, t) }
}

proof fn lemma_for(s: PC2, r: int, shape: int, j: int, restart: bool, t: PC2)
    requires inv09p(s), step2(s, PCL2::For { r, shape, j, restart }, t),
    ensures inv09p(t),
{
    let h = hof(s, shape);
    assert forall|h2: int| #[trigger] t.ent.contains_key(h2) && t.ent[h2].st is Ok implies
        t.ent[h2].cls is Some && cok(t, t.ent[h2].cls->Some_0, t.ent[h2].shape) by { assert(s.ent.contains_key(h2)); }
    assert forall|r2: int| #[trigger] t.rd.contains_key(r2) && t.rd[r2].run is Some implies cok(t, t.rd[r2].run->Some_0, t.rd[r2].s) by {
        if r2 != r { assert(s.rd.contains_key(r2)); }
        else { assert(s.ent.contains_key(h) && s.ent[h].st is Ok); }
    }
    assert forall|j2: int| #[trigger] t.jobs.contains_key(j2) && t.jobs[j2].ph is Compiled implies
        cok(t, t.jobs[j2].ph->c, t.jobs[j2].ph->from) by { assert(s.jobs.contains_key(j2)); }
}

proof fn lemma_walk(s: PC2, r: int, shape: int, a: (int, int), t: PC2)
    requires inv09p(s), step2(s, PCL2::Walk { r, shape, a }, t),
    ensures inv09p(t), step_or_stutter::<PcL1>(absp(s), labp(PCL2::Walk { r, shape, a }), absp(t)),
{
    // the class a reader runs was compiled from its own shape (NAT-I3)
    assert(a == interp(shape, s.db));
    assert forall|r2: int| #[trigger] t.rd.contains_key(r2) && t.rd[r2].run is Some implies cok(t, t.rd[r2].run->Some_0, t.rd[r2].s) by {
        assert(s.rd.contains_key(r2));
    }
}

proof fn lemma_bcompile(s: PC2, j: int, t: PC2)
    requires inv09p(s), step2(s, PCL2::BCompile { j }, t),
    ensures inv09p(t),
{
    // a build compiles into a class no reader, entry or other build names (control F-0901 fails here)
    let job = s.jobs[j];
    let c = cid(s, job.h);
    assert(c == s.next_cls && !s.cls.contains_key(c));
    assert forall|h2: int| #[trigger] t.ent.contains_key(h2) && t.ent[h2].st is Ok implies
        t.ent[h2].cls is Some && cok(t, t.ent[h2].cls->Some_0, t.ent[h2].shape) by { assert(s.ent.contains_key(h2)); }
    assert forall|r2: int| #[trigger] t.rd.contains_key(r2) && t.rd[r2].run is Some implies cok(t, t.rd[r2].run->Some_0, t.rd[r2].s) by {
        assert(s.rd.contains_key(r2));
    }
    assert forall|j2: int| #[trigger] t.jobs.contains_key(j2) && t.jobs[j2].ph is Compiled implies
        cok(t, t.jobs[j2].ph->c, t.jobs[j2].ph->from) by {
        if j2 != j { assert(s.jobs.contains_key(j2)); }
    }
    assert forall|c2: int| #[trigger] t.cls.contains_key(c2) implies c2 < t.next_cls by {
        if c2 != c { assert(s.cls.contains_key(c2)); }
    }
}

proof fn lemma_bmark(s: PC2, j: int, t: PC2)
    requires inv09p(s), step2(s, PCL2::BMark { j }, t),
    ensures inv09p(t),
{
    let job = s.jobs[j];
    // a build marks only the entry that still holds the shape it compiled (control F-C0901 fails here)
    assert(marks(s, j) ==> s.ent[job.h].shape == job.ph->from);
    assert(s.jobs.contains_key(j) && s.jobs[j].ph is Compiled);
    assert forall|h2: int| #[trigger] t.ent.contains_key(h2) && t.ent[h2].st is Ok implies
        t.ent[h2].cls is Some && cok(t, t.ent[h2].cls->Some_0, t.ent[h2].shape) by { assert(s.ent.contains_key(h2)); }
    assert forall|r2: int| #[trigger] t.rd.contains_key(r2) && t.rd[r2].run is Some implies cok(t, t.rd[r2].run->Some_0, t.rd[r2].s) by {
        assert(s.rd.contains_key(r2));
    }
    assert forall|j2: int| #[trigger] t.jobs.contains_key(j2) && t.jobs[j2].ph is Compiled implies
        cok(t, t.jobs[j2].ph->c, t.jobs[j2].ph->from) by { assert(s.jobs.contains_key(j2)); }
}

proof fn lemma_bother(s: PC2, l: PCL2, t: PC2)
    requires inv09p(s), step2(s, l, t), l is BLeave || l is BRefuse || l is BFail || l is Write,
    ensures inv09p(t),
{
    assert forall|h2: int| #[trigger] t.ent.contains_key(h2) && t.ent[h2].st is Ok implies
        t.ent[h2].cls is Some && cok(t, t.ent[h2].cls->Some_0, t.ent[h2].shape) by { assert(s.ent.contains_key(h2)); }
    assert forall|r2: int| #[trigger] t.rd.contains_key(r2) && t.rd[r2].run is Some implies cok(t, t.rd[r2].run->Some_0, t.rd[r2].s) by {
        assert(s.rd.contains_key(r2));
    }
    assert forall|j2: int| #[trigger] t.jobs.contains_key(j2) && t.jobs[j2].ph is Compiled implies
        cok(t, t.jobs[j2].ph->c, t.jobs[j2].ph->from) by { assert(s.jobs.contains_key(j2)); }
    assert forall|c2: int| #[trigger] t.cls.contains_key(c2) implies c2 < t.next_cls by { assert(s.cls.contains_key(c2)); }
}

proof fn lemma_step(s: PC2, l: PCL2, t: PC2)
    requires inv09p(s), step2(s, l, t),
    ensures inv09p(t), step_or_stutter::<PcL1>(absp(s), labp(l), absp(t)),
{
    match l {
        PCL2::For { r, shape, j, restart } => lemma_for(s, r, shape, j, restart, t),
        PCL2::Walk { r, shape, a } => lemma_walk(s, r, shape, a, t),
        PCL2::BCompile { j } => lemma_bcompile(s, j, t),
        PCL2::BMark { j } => lemma_bmark(s, j, t),
        _ => lemma_bother(s, l, t),
    }
}

impl Refines<PcL1> for PcL2 {
    open spec fn abs(s: PC2) -> PC1 { absp(s) }
    open spec fn lab(l: PCL2) -> Option<PCL1> { labp(l) }
    proof fn init_refines(s: PC2) {}
    proof fn step_refines(s: PC2, l: PCL2, t: PC2) { lemma_step(s, l, t); }
}

impl SafeContract for PcL2 {
    open spec fn inv(s: PC2) -> bool { inv09p(s) }
    proof fn init_safe(s: PC2) {}
    proof fn step_safe(s: PC2, l: PCL2, t: PC2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<PC2>, labels: Seq<PCL2>, k: int)
    requires execution::<PcRaw>(states, labels), 0 <= k < states.len(),
    ensures inv09p(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state (any hash assignment, collisions included) keeps
/// the L2 invariant, and its abstraction is an L1 execution: every answer is its shape's.
pub proof fn theorem_raw_executions_refine(states: Seq<PC2>, labels: Seq<PCL2>)
    requires execution::<PcRaw>(states, labels),
    ensures
        execution::<PcL2>(states, labels),
        abstract_execution::<PcL1>(Seq::new(states.len(), |i: int| absp(states[i])),
                                   Seq::new(labels.len(), |i: int| labp(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv09p(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv09p(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<PcL2>(states, labels));
    trace_refines::<PcL2, PcL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absp(states[i])) =~= Seq::new(states.len(), |i: int| <PcL2 as Refines<PcL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labp(labels[i])) =~= Seq::new(labels.len(), |i: int| <PcL2 as Refines<PcL1>>::lab(labels[i])));
}

/// NAT-T5.16 on the layout: an "ok" entry's class, if it exists, was compiled from that entry's shape.
pub proof fn theorem_ok_entry_runs_its_shapes_class(s: PC2, h: int)
    requires inv09p(s), s.ent.contains_key(h), s.ent[h].st is Ok, s.cls.contains_key(s.ent[h].cls->Some_0),
    ensures s.cls[s.ent[h].cls->Some_0] == s.ent[h].shape,
{
}

} // verus!
