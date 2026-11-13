//! Family adj_degree (module 04; finding F-0401; statements ADJ-I5.9, ADJ-I5.9.1; decision HD-0401, assumption).
//!
//! One graph, one source S. Its out entries are edge ids {0, 1}; S starts with edge 0 committed.
//!
//! Reader R = `Graph.KG.Adj.Degree(g, S)` (iris_src/src/Graph/KG/Adj.cls:51-91), one step per separately executed
//! read or write, in the documented order (Adj.cls:34-39):
//!   `RGen`   read ^KG("gen", g, S) (absent reads 0, Adj.cls:61);
//!   `RHit`   read ^KG("degc", g, S, all); a value whose generation equals the one read is the answer (Adj.cls:62-65);
//!   `RProbe` Lock +^IVG.AdjW(g)#"E":0 then release (Adj.cls:66-70): granted iff no other process holds the
//!            writer lock (shared holders block an exclusive request);
//!   `RCount` Adj.Count over ^KG("out", g, S) (Adj.cls:71, 102-130) — reads uncommitted entries (P-0002);
//!   `RStore` if granted and the generation is unchanged, Set degc = $LB(gen, count) (Adj.cls:73-75);
//!   `RRecheck` re-read the generation and Kill the entry if it moved (Adj.cls:76-78).
//! The reader runs at most two Degree calls.
//!
//! Writer W = one adjacency write in its own transaction (the row hook's Adjacency.Put of edge 1, or Remove of
//! edge 0; Adjacency.cls:76-105, 136-160): `WLock` shared ^IVG.AdjW(g) (held to the end of the transaction:
//! an unlock inside a transaction is deferred, P-0003), `WOut` set/kill the out entry (transactional),
//! `WGen` $Increment(^KG("gen", g, S)) — not undone by a rollback (P-0401; the journal shows $Increment records
//! outside the transaction), `WEnd` commit or roll back. At most two writes.
//!
//! Eraser E = Graph.KG.Eraser.EraseGraph(g) in its transaction on a namespace without the row hook, so the row
//! deletes leave ^KG alone and Adjacency.RemoveGraph (Adjacency.cls:420-441) does: `ELock` shared ^IVG.AdjW(g),
//! `EKillOut` Kill ^KG("out", g), `EKillGen` Kill ^KG("gen", g), `EKillDegc` Kill ^KG("degc", g), then commit or
//! roll back (in the reviewed design the generation step comes first, then the out kill). A rollback restores only
//! what this transaction changed (P-0408): a generation that did not exist is
//! not "restored", and the reader's own Set of degc is not this transaction's to undo. One erase.
//!
//! Modeling restriction (documented, not an environment subset of this module): W and E do not overlap. The
//! eraser's row DELETE waits on rows a writer holds and the writer's row is locked until it commits; overlap of an
//! erase with a concurrent edge write belongs to the erasure module's model (F-1201 family).
//!
//! Initial states: S has edge 0 and no cache entry; its generation is either absent (after any rebuild without the
//! row hook: FillEdge does not step it, Adjacency.cls:824-830; or after a snapshot restore, snapshot.py:1685-1691)
//! or 1.
//!
//! The writer's transaction may roll back at any point (an error or a stopped process between two of its
//! statements: Put does not catch, Adjacency.cls:43-45; a stopped process is rolled back, P-0001), including between
//! its out write and its generation step; the eraser likewise between its out kill and its generation kill.
//! `midfail: false` removes only those rollback points (a rollback is then possible only before a transaction's
//! first write or after its last step), to attribute a counterexample to the F-0401 sequence.
//!
//! Designs:
//! - `AsBuilt`: EKillGen kills the generation (Adjacency.cls:437).
//! - `Hd0401`: HD-0401 ("invalidation can never make an old degree-cache value valid again; model a fresh graph
//!   epoch or monotonically increasing generation, including erase/rebuild"): the eraser steps the generation with
//!   $Increment instead of killing it. Nothing else changes.
//! - `Reviewed`: Hd0401 plus every adjacency writer steps the generation before it changes out: the writer adds one
//!   $Increment before `WOut` (and keeps the one after), and the eraser steps the generation before its out kill.
//!   A transaction rolled back between its write and its later steps has then still moved the generation. This is the mechanism the Adjacency.cls:27-30 comment relies on ("a rolled-back write over-bumps,
//!   which only makes an entry look stale"), which as built holds only once the $Increment has run.
//! - `NoProbe` (negative control): the reviewed design with the reader's lock probe removed.
//!
//! Invariant `ADJ-I5.9` (with ADJ-I5.9.1 as its mechanism): whenever no writer transaction is open and the reader
//! is not between its store and its re-check, a cache entry whose generation equals the source's current
//! generation holds the committed out-degree.
use explorer::refinement::Binding;
use explorer::*;
use std::collections::BTreeSet;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Hd0401, Reviewed, NoProbe }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum WKind { Put, Remove }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum WPc { Idle, Locked(WKind), PreBumped(WKind), Wrote(WKind), Bumped(WKind) }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum EPc { Idle, Locked, Step1, Step2, DegcKilled, Done }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum RPc { Idle, GenRead, Hit, Probed, Counted, Stored }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Undo { Out(u8, bool), Gen(Option<u8>), Degc(Option<(u8, u8)>) }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub out: BTreeSet<u8>,
    pub gen: Option<u8>,
    pub degc: Option<(u8, u8)>,
    /// ghost: the committed out entries
    pub committed: BTreeSet<u8>,
    pub w: WPc,
    pub w_had: bool,
    pub w_undo: Vec<Undo>,
    pub w_runs: u8,
    pub e: EPc,
    pub e_undo: Vec<Undo>,
    pub r: RPc,
    pub r_gen: u8,
    pub r_got: bool,
    pub r_count: u8,
    pub r_calls: u8,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum A { WLock(WKind), WPre, WOut, WGen, WCommit, WRollback, ELock, E1, E2, EKillDegc, ECommit, ERollback,
             RGen, RHit, RProbe, RCount, RStore, RRecheck }

pub struct M { pub design: Design, pub midfail: bool, pub props: bool }

pub const INV: &str = "ADJ-I5.9: a current degree-cache entry holds the committed out-degree";
pub const QUIET: &str = "quiescent: no transaction open and no Degree call in flight";

fn g(s: &S) -> u8 { s.gen.unwrap_or(0) }

fn rollback(u: &mut S, undo: &[Undo]) {
    for x in undo.iter().rev() {
        match x {
            Undo::Out(e, present) => { if *present { u.out.insert(*e); } else { u.out.remove(e); } }
            Undo::Gen(v) => u.gen = *v,
            Undo::Degc(v) => u.degc = *v,
        }
    }
}

impl M {
    fn kill_out(&self, s: &S, u: &mut S) {
        for x in &s.out { u.e_undo.push(Undo::Out(*x, true)); }
        u.out.clear();
    }
}

pub fn busy(s: &S) -> u8 { (s.w != WPc::Idle) as u8 + (!matches!(s.e, EPc::Idle | EPc::Done)) as u8 + (s.r == RPc::Stored) as u8 }

/// What Degree(g, S) answers in state s (cached entry if current, else the count).
pub fn answer(s: &S) -> u8 {
    match s.degc { Some((cg, c)) if cg == g(s) => c, _ => s.out.len() as u8 }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        let one: BTreeSet<u8> = [0].into_iter().collect();
        [None, Some(1)].into_iter().map(|gen| S {
            out: one.clone(), gen, degc: None, committed: one.clone(), w: WPc::Idle, w_had: false, w_undo: vec![],
            w_runs: 0, e: EPc::Idle, e_undo: vec![], r: RPc::Idle, r_gen: 0, r_got: false, r_count: 0, r_calls: 0,
        }).collect()
    }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::WLock(WKind::Put), A::WLock(WKind::Remove), A::WPre, A::WOut, A::WGen, A::WCommit, A::WRollback, A::ELock,
             A::E1, A::E2, A::EKillDegc, A::ECommit, A::ERollback, A::RGen, A::RHit, A::RProbe, A::RCount,
             A::RStore, A::RRecheck]
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let e_open = !matches!(s.e, EPc::Idle | EPc::Done);
        match a {
            A::WLock(k) => {
                if s.w != WPc::Idle || s.w_runs >= 2 || e_open { return None; }
                u.w = WPc::Locked(*k);
            }
            A::WPre => {
                let WPc::Locked(k) = s.w else { return None };
                if !matches!(self.design, Design::Reviewed | Design::NoProbe) { return None; }
                u.gen = Some(g(s) + 1);
                u.w = WPc::PreBumped(k);
            }
            A::WOut => {
                let k = match (s.w, self.design) {
                    (WPc::Locked(k), Design::AsBuilt | Design::Hd0401) => k,
                    (WPc::PreBumped(k), Design::Reviewed | Design::NoProbe) => k,
                    _ => return None,
                };
                match k {
                    WKind::Put => { u.w_undo.push(Undo::Out(1, s.out.contains(&1))); u.out.insert(1); }
                    WKind::Remove => { u.w_had = s.out.contains(&0); u.w_undo.push(Undo::Out(0, s.out.contains(&0))); u.out.remove(&0); }
                }
                u.w = WPc::Wrote(k);
            }
            A::WGen => {
                let WPc::Wrote(k) = s.w else { return None };
                // Put always steps; Remove steps only when the entry was there (Adjacency.cls:146-148)
                if k == WKind::Put || s.w_had { u.gen = Some(g(s) + 1); }
                u.w = WPc::Bumped(k);
            }
            A::WCommit => {
                let WPc::Bumped(k) = s.w else { return None };
                match k { WKind::Put => { u.committed.insert(1); } WKind::Remove => { u.committed.remove(&0); } }
                u.w = WPc::Idle; u.w_undo.clear(); u.w_runs += 1; u.w_had = false;
            }
            A::WRollback => {
                if matches!(s.w, WPc::Idle) { return None; }
                if !self.midfail && matches!(s.w, WPc::Wrote(_)) { return None; }
                let undo = s.w_undo.clone();
                rollback(&mut u, &undo);
                u.w = WPc::Idle; u.w_undo.clear(); u.w_runs += 1; u.w_had = false;
            }
            A::ELock => {
                if s.e != EPc::Idle || s.w != WPc::Idle { return None; }
                u.e = EPc::Locked;
            }
            // As built (and Hd0401): E1 kills out, E2 kills (Hd0401: steps) the generation (RemoveGraph order,
            // Adjacency.cls:432-437). Reviewed: E1 steps the generation, E2 kills out.
            A::E1 => {
                if s.e != EPc::Locked { return None; }
                match self.design {
                    Design::AsBuilt | Design::Hd0401 => self.kill_out(s, &mut u),
                    Design::Reviewed | Design::NoProbe => { u.gen = Some(g(s) + 1); }
                }
                u.e = EPc::Step1;
            }
            A::E2 => {
                if s.e != EPc::Step1 { return None; }
                match self.design {
                    Design::AsBuilt => { if s.gen.is_some() { u.e_undo.push(Undo::Gen(s.gen)); } u.gen = None; }
                    // $Increment: not in the transaction's undo (P-0401)
                    Design::Hd0401 => { u.gen = Some(g(s) + 1); }
                    Design::Reviewed | Design::NoProbe => self.kill_out(s, &mut u),
                }
                u.e = EPc::Step2;
            }
            A::EKillDegc => {
                if s.e != EPc::Step2 { return None; }
                if s.degc.is_some() { u.e_undo.push(Undo::Degc(s.degc)); }
                u.degc = None;
                u.e = EPc::DegcKilled;
            }
            A::ECommit => {
                if s.e != EPc::DegcKilled { return None; }
                u.committed.clear(); u.e_undo.clear(); u.e = EPc::Done;
            }
            A::ERollback => {
                if !e_open { return None; }
                if !self.midfail && matches!(s.e, EPc::Step1 | EPc::Step2) { return None; }
                let undo = s.e_undo.clone();
                rollback(&mut u, &undo);
                u.e_undo.clear(); u.e = EPc::Done;
            }
            A::RGen => {
                if s.r != RPc::Idle || s.r_calls >= 2 { return None; }
                u.r_gen = g(s); u.r = RPc::GenRead;
            }
            A::RHit => {
                if s.r != RPc::GenRead { return None; }
                match s.degc {
                    Some((cg, _)) if cg == s.r_gen => { u.r = RPc::Idle; u.r_calls += 1; }
                    _ => { u.r = RPc::Hit; }
                }
            }
            A::RProbe => {
                if s.r != RPc::Hit { return None; }
                let held = s.w != WPc::Idle || e_open;
                u.r_got = match self.design { Design::NoProbe => true, _ => !held };
                u.r = RPc::Probed;
            }
            A::RCount => {
                if s.r != RPc::Probed { return None; }
                u.r_count = s.out.len() as u8; u.r = RPc::Counted;
            }
            A::RStore => {
                if s.r != RPc::Counted { return None; }
                if s.r_got && g(s) == s.r_gen {
                    u.degc = Some((s.r_gen, s.r_count)); u.r = RPc::Stored;
                } else {
                    u.r = RPc::Idle; u.r_calls += 1;
                }
            }
            A::RRecheck => {
                if s.r != RPc::Stored { return None; }
                if g(s) != s.r_gen { u.degc = None; }
                u.r = RPc::Idle; u.r_calls += 1;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        if !self.props { return vec![]; }
        vec![invariant(INV, |s: &S| {
            if busy(s) > 0 { return true; }
            match s.degc { Some((cg, c)) if cg == g(s) => c as usize == s.committed.len(), _ => true }
        })]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        if !self.props { return vec![]; }
        vec![invariant(QUIET, |s: &S| busy(s) == 0 && matches!(s.r, RPc::Idle) && matches!(s.e, EPc::Idle | EPc::Done))]
    }
}

/// L1: the out-degree is the committed count; a busy counter tracks open transactions (and a reader between its
/// store and re-check). Its observation is the degree when nothing is busy.
pub struct L1;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Eff { Same, Add, Del, Clear }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum LA { Begin, End(Eff) }

impl Model for L1 {
    type State = (u8, u8);
    type Action = LA;
    fn init_states(&self) -> Vec<(u8, u8)> { vec![(1, 0)] }
    fn actions(&self, _: &(u8, u8)) -> Vec<LA> {
        vec![LA::Begin, LA::End(Eff::Same), LA::End(Eff::Add), LA::End(Eff::Del), LA::End(Eff::Clear)]
    }
    fn next(&self, s: &(u8, u8), a: &LA) -> Option<(u8, u8)> {
        let (d, b) = *s;
        match a {
            LA::Begin => (b < 3).then_some((d, b + 1)),
            LA::End(e) => {
                if b == 0 { return None; }
                let d2 = match e { Eff::Same => d, Eff::Add => d.checked_add(1)?, Eff::Del => d.checked_sub(1)?, Eff::Clear => 0 };
                Some((d2, b - 1))
            }
        }
    }
}

pub struct Bind { pub m: M }

impl Binding for Bind {
    type Concrete = M;
    type Abstract = L1;
    type Observation = Option<u8>;
    fn concrete(&self) -> &M { &self.m }
    fn abstract_model(&self) -> &L1 { &L1 }
    fn abstract_state(&self, s: &S) -> (u8, u8) { (s.committed.len() as u8, busy(s)) }
    fn abstract_action(&self, _: &A) -> Option<LA> { None }
    fn abstract_action_at(&self, s: &S, _: &A, t: &S) -> Option<LA> {
        let (b, a) = (self.abstract_state(s), self.abstract_state(t));
        if a == b { return None; }
        if a.1 == b.1 + 1 { return Some(LA::Begin); }
        if a.1 + 1 == b.1 {
            let e = if a.0 == b.0 { Eff::Same } else if a.0 == b.0 + 1 { Eff::Add } else if a.0 + 1 == b.0 { Eff::Del } else { Eff::Clear };
            return Some(LA::End(e));
        }
        Some(LA::Begin)
    }
    fn observe_concrete(&self, s: &S) -> Option<u8> { (busy(s) == 0).then(|| answer(s)) }
    fn observe_abstract(&self, s: &(u8, u8)) -> Option<u8> { (s.1 == 0).then_some(s.0) }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("04", "adj_degree");
    let m = |design, midfail| M { design, midfail, props: true };
    let ab = m(Design::AsBuilt, true);
    let ab_nomid = m(Design::AsBuilt, false);
    let hd = m(Design::Hd0401, true);
    let hd_nomid = m(Design::Hd0401, false);
    let rv = m(Design::Reviewed, true);
    let np = m(Design::NoProbe, true);
    let mut out = vec![
        check("adj_degree-as-built", md, fam, "as-built", "safety", Expect::Violation(INV), &Keep::safety(&ab)),
        check("adj_degree-as-built-F0401-erase", md, fam, "as-built", "safety", Expect::Violation(INV), &Keep::safety(&ab_nomid)),
        check("adj_degree-hd0401-erase-closed", md, fam, "reviewed", "safety", Expect::Pass, &Keep::safety(&hd_nomid)),
        check("adj_degree-hd0401-writer-window", md, fam, "reviewed", "safety", Expect::Violation(INV), &Keep::safety(&hd)),
        check("adj_degree-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &Keep::safety(&rv)),
        check("adj_degree-control-no-probe", md, fam, "control", "safety", Expect::Violation(INV), &Keep::safety(&np)),
        check("adj_degree-reviewed-progress", md, fam, "reviewed", "progress", Expect::Pass, &Keep::progress(&rv)),
        check("adj_degree-as-built-progress", md, fam, "as-built", "progress", Expect::Pass, &Keep::progress(&ab)),
        reach("adj_degree-reviewed-reach-store", md, fam, "reviewed", &rv,
              "never: a reader's stored entry is current with no transaction open",
              |s: &S| busy(s) == 0 && matches!(s.degc, Some((cg, _)) if cg == g(s))),
        reach("adj_degree-reviewed-reach-erase-rollback", md, fam, "reviewed", &rv,
              "never: an erase rolled back after killing the out entries",
              |s: &S| s.e == EPc::Done && s.out.contains(&0) && s.committed.contains(&0) && s.gen.is_some_and(|x| x >= 1) && s.r_count == 0 && s.r_calls >= 1),
        reach("adj_degree-reviewed-reach-writer-midfail", md, fam, "reviewed", &rv,
              "never: a writer rolled back after its out write and before its last generation step",
              |s: &S| s.w_runs >= 1 && s.r_count == 2 && s.committed.len() == 1 && s.w == WPc::Idle),
    ];
    let r = explorer::refinement::audit(Bind { m: M { design: Design::AsBuilt, midfail: false, props: false } }, limits()).expect("audit");
    out.push(judge("adj_degree-refinement-as-built-F0401", md, fam, "as-built", "refinement",
                   Expect::Violation("refinement observations"), r));
    let r = explorer::refinement::audit(Bind { m: M { design: Design::Reviewed, midfail: true, props: false } }, limits()).expect("audit");
    out.push(judge("adj_degree-refinement-reviewed", md, fam, "reviewed", "refinement", Expect::Pass, r));
    let r = explorer::refinement::audit(Bind { m: M { design: Design::NoProbe, midfail: true, props: false } }, limits()).expect("audit");
    out.push(judge("adj_degree-refinement-control-no-probe", md, fam, "control", "refinement",
                   Expect::Violation("refinement observations"), r));
    out
}
