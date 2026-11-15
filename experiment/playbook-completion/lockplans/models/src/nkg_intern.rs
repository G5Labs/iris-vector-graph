//! Family nkg_intern (module 10; gate 3.5-lockplans): ^NKG interning under rollback, and EnsureNKG's double check.
//!
//! `Intern` (LP-10-6). Graph.KG.GraphIndex.InternLabel (GraphIndex.cls:77-100; InternNode :43-75 is the same shape):
//! a lock-free fast path `$Get(^NKG("$LI", label))`, else `Lock +^NKG("$LI", label):0` (then :5), re-check, allocate
//! k = $Increment(labelCount) - 1 and Set the dictionary ($LI, $LS). Called by Adjacency.Put (Adjacency.cls:95-105)
//! inside the writer's transaction; globals are read uncommitted (SYS-P2) and a rollback undoes the Sets but not the
//! $Increment. Writer A allocates inside a transaction that may roll back; writer B interns the same label and commits.
//! Property ALG-B12.7 (CONTEXT.md:109-114): at quiescence every committed ^NKG row's label index is named by the
//! committed dictionary (or the snapshot is marked out of date).
//! Designs: `AsBuilt` (fast path trusts any visible entry); `Reviewed` (the fast path trusts only a committed entry;
//! otherwise it takes the label lock, which an allocating writer holds to its transaction end, as IRIS defers an
//! unlock inside a transaction, corr-lockplan deferred-nested-*); `Control` (the reviewed design with the
//! allocator's lock released at the end of the statement instead of the transaction, and the re-check under the lock
//! trusting any visible entry: the mutant the explorer must catch).
//!
//! `Ensure` (LP-10-2). TraversalBuild.EnsureNKG (:399-424): unlocked pre-check, `Lock +^IVG.NKGBuild:900`, re-check,
//! rewrite, unlock. Two readers after one invalidation. Property: at most one rewrite per invalidation.
//! Designs: `AsBuilt` (re-check under the lock) expected to pass; `Reviewed` = as built; `Control` without the re-check.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, Control }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum W { Start, Interned(u8), Wrote(u8), Committed, Aborted }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct SI {
    /// the dictionary entry: (index, committed?, allocated by)
    pub dict: Option<(u8, bool, u8)>,
    pub counter: u8,
    /// each writer's ^NKG row: (index, committed?)
    pub rows: [Option<(u8, bool)>; 2],
    pub w: [W; 2],
    pub lock: Option<u8>,
}

#[derive(Clone, Debug)]
pub enum AI { Intern(u8), Write(u8), Commit(u8), Abort }

pub struct Intern { pub design: Design }

pub const DICT: &str = "ALG-B12.7: every committed ^NKG row's label index is named by the committed dictionary";

fn fin(w: W) -> bool { matches!(w, W::Committed | W::Aborted) }

impl Model for Intern {
    type State = SI;
    type Action = AI;
    fn init_states(&self) -> Vec<SI> {
        vec![SI { dict: None, counter: 0, rows: [None; 2], w: [W::Start; 2], lock: None }]
    }
    fn actions(&self, _: &SI) -> Vec<AI> {
        vec![AI::Intern(0), AI::Intern(1), AI::Write(0), AI::Write(1), AI::Commit(0), AI::Commit(1), AI::Abort]
    }
    fn next(&self, s: &SI, a: &AI) -> Option<SI> {
        let mut u = s.clone();
        match *a {
            AI::Intern(i) => {
                let k = i as usize;
                if s.w[k] != W::Start { return None; }
                let fast_ok = match (self.design, s.dict) {
                    (_, None) => None,
                    (Design::AsBuilt, Some((x, _, _))) => Some(x),
                    (_, Some((x, true, _))) => Some(x),
                    (_, Some((x, false, o))) => if o == i { Some(x) } else { None },
                };
                if let Some(x) = fast_ok {
                    u.w[k] = W::Interned(x);
                } else {
                    // slow path: the label lock, re-check, allocate
                    if s.lock.is_some() && s.lock != Some(i) { return None; }
                    if let Some((x, c, o)) = s.dict {
                        if c || o == i || self.design != Design::Reviewed { u.w[k] = W::Interned(x); return Some(u); }
                    }
                    let x = s.counter;
                    u.counter += 1;
                    u.dict = Some((x, false, i));
                    u.w[k] = W::Interned(x);
                    // reviewed: held to the end of the transaction (deferred unlock); control: released now
                    u.lock = if self.design == Design::Reviewed { Some(i) } else { None };
                }
            }
            AI::Write(i) => {
                let k = i as usize;
                let W::Interned(x) = s.w[k] else { return None };
                u.rows[k] = Some((x, false));
                u.w[k] = W::Wrote(x);
            }
            AI::Commit(i) => {
                let k = i as usize;
                let W::Wrote(_) = s.w[k] else { return None };
                if i == 0 { return None; } // writer 0 is A, who ends by Abort; B (1) commits
                if let Some((x, false, o)) = s.dict { if o == i { u.dict = Some((x, true, o)); } }
                if let Some((x, false)) = s.rows[k] { u.rows[k] = Some((x, true)); }
                if s.lock == Some(i) { u.lock = None; }
                u.w[k] = W::Committed;
            }
            AI::Abort => {
                if !matches!(s.w[0], W::Wrote(_)) { return None; }
                if let Some((_, false, 0)) = s.dict { u.dict = None; }
                u.rows[0] = None;
                if s.lock == Some(0) { u.lock = None; }
                u.w[0] = W::Aborted;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<SI>> {
        vec![invariant(DICT, |s: &SI| {
            !(fin(s.w[0]) && fin(s.w[1])) || s.rows.iter().all(|r| match r {
                Some((x, true)) => matches!(s.dict, Some((y, true, _)) if y == *x),
                _ => true,
            })
        })]
    }
}

// ------------------------------------------------------------------------------------------------ Ensure
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum R { Start, SawStale, Locked, Done }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct SE { pub built: bool, pub r: [R; 2], pub lock: Option<u8>, pub rewrites: u8 }

#[derive(Clone, Debug)]
pub enum AE { Pre(u8), Lock(u8), Recheck(u8) }

pub struct Ensure { pub design: Design }

pub const ONCE: &str = "LP-10-2: one rewrite per invalidation";

impl Model for Ensure {
    type State = SE;
    type Action = AE;
    fn init_states(&self) -> Vec<SE> { vec![SE { built: false, r: [R::Start; 2], lock: None, rewrites: 0 }] }
    fn actions(&self, _: &SE) -> Vec<AE> {
        vec![AE::Pre(0), AE::Pre(1), AE::Lock(0), AE::Lock(1), AE::Recheck(0), AE::Recheck(1)]
    }
    fn next(&self, s: &SE, a: &AE) -> Option<SE> {
        let mut u = s.clone();
        match *a {
            AE::Pre(i) => {
                let k = i as usize;
                if s.r[k] != R::Start { return None; }
                u.r[k] = if s.built { R::Done } else { R::SawStale };
            }
            AE::Lock(i) => {
                let k = i as usize;
                if s.r[k] != R::SawStale || s.lock.is_some() { return None; }
                u.lock = Some(i); u.r[k] = R::Locked;
            }
            AE::Recheck(i) => {
                let k = i as usize;
                if s.r[k] != R::Locked { return None; }
                if self.design == Design::Control || !s.built { u.built = true; u.rewrites += 1; }
                u.lock = None; u.r[k] = R::Done;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<SE>> { vec![invariant(ONCE, |s: &SE| s.rewrites <= 1)] }
    fn always_possibly(&self) -> Vec<Invariant<SE>> {
        vec![invariant("both readers can finish with the snapshot built", |s: &SE| s.r == [R::Done; 2] && s.built)]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("10", "nkg_intern");
    let ia = Intern { design: Design::AsBuilt };
    let ir = Intern { design: Design::Reviewed };
    let ic = Intern { design: Design::Control };
    let ea = Ensure { design: Design::AsBuilt };
    let er = Ensure { design: Design::Reviewed };
    let ec = Ensure { design: Design::Control };
    vec![
        check("nkg_intern-intern-as-built", md, fam, "as-built", "safety", Expect::Violation(DICT), &ia),
        check("nkg_intern-intern-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &ir),
        check("nkg_intern-intern-control-early-unlock", md, fam, "control", "safety", Expect::Violation(DICT), &ic),
        reach("nkg_intern-intern-reviewed-reach-B-own-index", md, fam, "reviewed", &ir, "never: B commits under an index it allocated after A's rollback",
              |s: &SI| s.w[0] == W::Aborted && s.w[1] == W::Committed && matches!(s.dict, Some((_, true, 1)))),
        check("nkg_intern-ensure-as-built", md, fam, "as-built", "safety", Expect::Pass, &Keep::safety(&ea)),
        check("nkg_intern-ensure-as-built-progress", md, fam, "as-built", "progress", Expect::Pass, &Keep::progress(&ea)),
        check("nkg_intern-ensure-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &Keep::safety(&er)),
        check("nkg_intern-ensure-control-no-recheck", md, fam, "control", "safety", Expect::Violation(ONCE), &Keep::safety(&ec)),
        reach("nkg_intern-ensure-as-built-reach-one-rewrite", md, fam, "as-built", &ea, "never: both readers done after one rewrite",
              |s: &SE| s.r == [R::Done; 2] && s.rewrites == 1),
    ]
}
