//! Family adj_token (module 04; finding F-0402; statements ADJ-I7.3, ADJ-I11.2).
//!
//! The graph-version token ^KG("__version") stamps every rebuilt store and cached answer. Modeled here with the
//! shared result cache, the representative of all four token-stamped builds the finding lists (AlgoCache, the
//! two-hop counts TraversalBuild.cls:948-992, the interned snapshot TraversalBuild.cls:333-371, the Arno snapshot
//! ArnoAccel.cls:305-316 — each reads the token, then the adjacency without a lock, then stores under the token).
//!
//! Builder B = `IRISSQLStore._cached_algorithm` (iris_vector_graph/stores/iris_sql_store.py:966-982) over
//! `Graph.KG.AlgoCache` (AlgoCache.cls:27-52): `BToken` Lookup reads the token (a miss), `BCompute` the algorithm
//! reads ^KG("out") (uncommitted entries included, P-0002), `BStore` AlgoCache.Put stores $LB(token, payload).
//! At most two builds.
//!
//! Writer W = one adjacency write in its own transaction (Adjacency.Put of edge 1 or Remove of edge 0,
//! Adjacency.cls:76-160): `WLock` shared ^IVG.AdjW(g) held to the transaction's end (P-0003), `WOut` the out
//! entry, `WBump` $Increment(^KG("__version")) — not undone by rollback (P-0401; journal-confirmed live),
//! `WEnd` commit or roll back. A rollback may happen at any point (`midfail: true`), including between the out
//! write and the token step; `midfail: false` removes only that point, to attribute a counterexample to the
//! F-0402 sequence (a write whose token step has run, read by a build, then rolled back). At most two writes.
//!
//! Designs:
//! - `AsBuilt`: no lock probe.
//! - `Probe`: the finding's proposed fix, ADR-0012's degree rule applied to stamped builds (the contract
//!   AlgoCache.cls:5-7 states: "a write that lands during the computation leaves the entry stale and never wrongly
//!   fresh"): after reading the token, probe the parent writer lock exclusively with no wait; store only when the
//!   probe was granted and the token has not moved.
//! - `Reviewed`: Probe plus the writer steps the token before its out write as well as after it, so a write rolled
//!   back before its token step has still moved the token (the same window as adj_degree's writer window).
//! - `ProbeLate` (negative control): the reviewed design with the probe taken after the computation instead of
//!   before it (the order is part of Adj.Degree's soundness argument, Adj.cls:34-39).
//!
//! Invariant `ADJ-I11.2` (and ADJ-I7.3 for the rebuilt stores): whenever no writer transaction is open, an entry
//! whose stamp equals the current token holds exactly the committed edges.
use explorer::*;
use std::collections::BTreeSet;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Probe, Reviewed, ProbeLate }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum WK { Put, Remove }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum WPc { Idle, Locked(WK), Pre(WK), Wrote(WK), Bumped(WK) }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum BPc { Idle, Token, Probed, Computed, ProbedLate }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub out: BTreeSet<u8>,
    pub committed: BTreeSet<u8>,
    pub token: u8,
    pub cache: Option<(u8, BTreeSet<u8>)>,
    pub w: WPc,
    pub w_undo: Option<(u8, bool)>,
    pub w_runs: u8,
    pub b: BPc,
    pub b_token: u8,
    pub b_got: bool,
    pub b_payload: BTreeSet<u8>,
    pub b_runs: u8,
}

#[derive(Clone, Debug)]
pub enum A { WLock(WK), WPre, WOut, WBump, WCommit, WRollback, BToken, BProbe, BCompute, BProbeLate, BStore }

pub struct M { pub design: Design, pub midfail: bool }

pub const INV: &str = "ADJ-I11.2: a cached answer stamped with the current token holds only committed edges";

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        let one: BTreeSet<u8> = [0].into_iter().collect();
        vec![S { out: one.clone(), committed: one, token: 0, cache: None, w: WPc::Idle, w_undo: None, w_runs: 0,
                 b: BPc::Idle, b_token: 0, b_got: false, b_payload: BTreeSet::new(), b_runs: 0 }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::WLock(WK::Put), A::WLock(WK::Remove), A::WPre, A::WOut, A::WBump, A::WCommit, A::WRollback, A::BToken,
             A::BProbe, A::BCompute, A::BProbeLate, A::BStore]
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let held = s.w != WPc::Idle;
        match a {
            A::WLock(k) => { if held || s.w_runs >= 2 { return None; } u.w = WPc::Locked(*k); }
            A::WPre => {
                let WPc::Locked(k) = s.w else { return None };
                if !matches!(self.design, Design::Reviewed | Design::ProbeLate) { return None; }
                u.token += 1; u.w = WPc::Pre(k);
            }
            A::WOut => {
                let k = match (s.w, self.design) {
                    (WPc::Locked(k), Design::AsBuilt | Design::Probe) => k,
                    (WPc::Pre(k), Design::Reviewed | Design::ProbeLate) => k,
                    _ => return None,
                };
                let e = if k == WK::Put { 1 } else { 0 };
                u.w_undo = Some((e, s.out.contains(&e)));
                if k == WK::Put { u.out.insert(1); } else { u.out.remove(&0); }
                u.w = WPc::Wrote(k);
            }
            A::WBump => { let WPc::Wrote(k) = s.w else { return None }; u.token += 1; u.w = WPc::Bumped(k); }
            A::WCommit => {
                let WPc::Bumped(k) = s.w else { return None };
                if k == WK::Put { u.committed.insert(1); } else { u.committed.remove(&0); }
                u.w = WPc::Idle; u.w_undo = None; u.w_runs += 1;
            }
            A::WRollback => {
                if !held { return None; }
                if !self.midfail && matches!(s.w, WPc::Wrote(_)) { return None; }
                if let Some((e, present)) = s.w_undo { if present { u.out.insert(e); } else { u.out.remove(&e); } }
                u.w = WPc::Idle; u.w_undo = None; u.w_runs += 1;
            }
            A::BToken => { if s.b != BPc::Idle || s.b_runs >= 2 { return None; } u.b_token = s.token; u.b = BPc::Token; }
            A::BProbe => {
                if s.b != BPc::Token || !matches!(self.design, Design::Probe | Design::Reviewed) { return None; }
                u.b_got = !held; u.b = BPc::Probed;
            }
            A::BCompute => {
                let ok = match self.design { Design::Probe | Design::Reviewed => s.b == BPc::Probed, _ => s.b == BPc::Token };
                if !ok { return None; }
                u.b_payload = s.out.clone(); u.b = BPc::Computed;
            }
            A::BProbeLate => {
                if s.b != BPc::Computed || self.design != Design::ProbeLate { return None; }
                u.b_got = !held; u.b = BPc::ProbedLate;
            }
            A::BStore => {
                let stores = match self.design {
                    Design::AsBuilt => s.b == BPc::Computed,
                    Design::Probe | Design::Reviewed => s.b == BPc::Computed && s.b_got && s.token == s.b_token,
                    Design::ProbeLate => s.b == BPc::ProbedLate && s.b_got && s.token == s.b_token,
                };
                let at = match self.design { Design::ProbeLate => BPc::ProbedLate, _ => BPc::Computed };
                if s.b != at { return None; }
                if stores { u.cache = Some((s.b_token, s.b_payload.clone())); }
                u.b = BPc::Idle; u.b_runs += 1; u.b_got = false; u.b_payload.clear();
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(INV, |s: &S| {
            if s.w != WPc::Idle { return true; }
            match &s.cache { Some((t, p)) if *t == s.token => *p == s.committed, _ => true }
        })]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("quiescent: no write open, no build in flight", |s: &S| s.w == WPc::Idle && s.b == BPc::Idle)]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("04", "adj_token");
    let m = |design, midfail| M { design, midfail };
    let ab = m(Design::AsBuilt, true);
    let ab_nomid = m(Design::AsBuilt, false);
    let pr = m(Design::Probe, true);
    let pr_nomid = m(Design::Probe, false);
    let rv = m(Design::Reviewed, true);
    let pl = m(Design::ProbeLate, true);
    vec![
        check("adj_token-as-built", md, fam, "as-built", "safety", Expect::Violation(INV), &Keep::safety(&ab)),
        check("adj_token-as-built-F0402", md, fam, "as-built", "safety", Expect::Violation(INV), &Keep::safety(&ab_nomid)),
        check("adj_token-probe-closes-F0402", md, fam, "reviewed", "safety", Expect::Pass, &Keep::safety(&pr_nomid)),
        check("adj_token-probe-writer-window", md, fam, "reviewed", "safety", Expect::Violation(INV), &Keep::safety(&pr)),
        check("adj_token-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &Keep::safety(&rv)),
        check("adj_token-control-probe-late", md, fam, "control", "safety", Expect::Violation(INV), &Keep::safety(&pl)),
        check("adj_token-reviewed-progress", md, fam, "reviewed", "progress", Expect::Pass, &Keep::progress(&rv)),
        reach("adj_token-reviewed-reach-current-entry", md, fam, "reviewed", &rv,
              "never: a stored entry is current after a committed write",
              |s: &S| s.w == WPc::Idle && s.committed.len() == 2 && matches!(&s.cache, Some((t, _)) if *t == s.token)),
        reach("adj_token-reviewed-reach-rollback", md, fam, "reviewed", &rv,
              "never: a write is rolled back after moving the token",
              |s: &S| s.w == WPc::Idle && s.token >= 1 && s.committed.len() == 1 && s.w_runs >= 1 && s.out == s.committed),
    ]
}
