//! Family adj_rebuild_txn (module 04; finding F-0409, statement ADJ-B8.9; decision HD-0402, statement ADJ-Q8.10).
//!
//! Part 1, `Caller` machine — a rebuild inside a caller's transaction. The caller C works on one connection whose
//! server process also runs the rebuild (`engine.sync()` -> `_sync_kg` -> `Graph.KG.Traversal.BuildKG` through
//! `self._iris_obj()`, iris_vector_graph/_engine/schema.py:2859-2895; on a createIRIS(conn) engine that is the
//! cursor's own process, P-0305). Steps: `CBegin` START TRANSACTION ($TLevel 0 -> 1), `CWrite` one row of the
//! caller's own, `SyncStart` BuildKG's TStart (TraversalBuild.cls:40; level +1, the level found is recorded),
//! `SyncOk` its TCommit (TraversalBuild.cls:132, one level), `SyncFail` its Catch (TraversalBuild.cls:154-157),
//! `CCommit` / `CRollback` the caller's own end (only at the caller's level 1). A call without a caller
//! transaction (`SyncStart` at level 0) is also possible.
//!
//! Designs: `AsBuilt` — `If $TLevel > 0 { TRollback }` with no argument ends every level (P-0409); `Reviewed` —
//! `While $TLevel > tTxnLevel { TROLLBACK 1 }` with the level found before TStart (CHANGELOG 4.6.4 lists the
//! classes that "roll back to the level they found"; TraversalBuild is not among them); `LevelAfterTStart`
//! (negative control) — the reviewed loop with the level captured after TStart (off by one), so the rebuild's own
//! level stays open.
//!
//! Action property `ADJ-B8.9` (CHANGELOG.md:410-424: "An IVG write never commits or rolls back a transaction its
//! caller opened"): every rebuild step ends at the level the rebuild found (or deeper while it runs), leaves the
//! caller's pending row in place, and returns at exactly the level found.
//!
//! Part 2, `Concurrent` machine — two rebuilds at once (HD-0402, assumption: "allow at most one publishing rebuild
//! per adjacency structure"). One committed edge row e0. Each rebuild B_i (BuildKG on a namespace without the row
//! hook): `Begin` Adjacency.BeginRebuild (Lock +^IVG.AdjW#"S":5, Adjacency.cls:814-822 — shared, so two rebuilds
//! hold it together) and TStart; `Kill` RemoveAll's Kill ^KG("out") (Adjacency.cls:452-462; transactional,
//! before-image journaled); `Fill` FillEdge(e0) (Adjacency.cls:826-830); `Commit` TCommit + EndRebuild; `Fail`
//! TRollback (restores this transaction's before-images, in reverse order, P-0408) + EndRebuild(0).
//! Designs: `AsBuilt` (shared lock); `Reviewed` (BeginRebuild takes the parent lock exclusively: one rebuild at a
//! time); `EarlyRelease` (negative control: exclusive, but released after the Kill — EndRebuild before the fill).
//! Invariant `ADJ-Q8.10/HD-0402`: with no rebuild open, the adjacency holds exactly the committed rows.
use explorer::*;

// ---------------------------------------------------------------- part 1

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum D1 { AsBuilt, Reviewed, LevelAfterTStart }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Sync { NotYet, Running { found: u8 }, Done }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S1 {
    pub tlevel: u8,
    pub caller_open: bool,
    pub caller_pending: bool,
    pub caller_committed: bool,
    pub sync: Sync,
    pub sync_returned_at: Option<(u8, u8)>, // (level found, level at return)
}

#[derive(Clone, Debug)]
pub enum A1 { CBegin, CWrite, SyncStart, SyncOk, SyncFail, CCommit, CRollback }

pub struct Caller { pub design: D1 }

pub const B89: &str = "ADJ-B8.9: a rebuild never ends or undoes a transaction its caller opened";

impl Model for Caller {
    type State = S1;
    type Action = A1;
    fn init_states(&self) -> Vec<S1> {
        vec![S1 { tlevel: 0, caller_open: false, caller_pending: false, caller_committed: false, sync: Sync::NotYet,
                  sync_returned_at: None }]
    }
    fn actions(&self, _: &S1) -> Vec<A1> {
        vec![A1::CBegin, A1::CWrite, A1::SyncStart, A1::SyncOk, A1::SyncFail, A1::CCommit, A1::CRollback]
    }
    fn next(&self, s: &S1, a: &A1) -> Option<S1> {
        let mut u = s.clone();
        match a {
            A1::CBegin => { if s.caller_open || s.tlevel != 0 || s.caller_committed || s.sync != Sync::NotYet { return None; } u.caller_open = true; u.tlevel = 1; }
            A1::CWrite => { if !s.caller_open || s.caller_pending || s.tlevel == 0 { return None; } u.caller_pending = true; }
            A1::SyncStart => { if s.sync != Sync::NotYet { return None; } u.sync = Sync::Running { found: s.tlevel }; u.tlevel += 1; }
            A1::SyncOk => {
                let Sync::Running { found } = s.sync else { return None };
                u.tlevel -= 1; // TCommit: one level
                u.sync = Sync::Done; u.sync_returned_at = Some((found, u.tlevel));
            }
            A1::SyncFail => {
                let Sync::Running { found } = s.sync else { return None };
                match self.design {
                    D1::AsBuilt => { u.tlevel = 0; if s.caller_pending { u.caller_pending = false; } }
                    D1::Reviewed => { u.tlevel = found; }
                    D1::LevelAfterTStart => { let after = found + 1; while u.tlevel > after { u.tlevel -= 1; } }
                }
                u.sync = Sync::Done; u.sync_returned_at = Some((found, u.tlevel));
            }
            A1::CCommit | A1::CRollback => {
                if !s.caller_open || matches!(s.sync, Sync::Running { .. }) { return None; }
                // the caller ends its own transaction; at $TLevel 0 there is nothing left to end (its rows are gone)
                if matches!(a, A1::CCommit) && s.tlevel >= 1 && s.caller_pending { u.caller_committed = true; }
                u.caller_open = false; u.caller_pending = false; u.tlevel = 0;
            }
        }
        Some(u)
    }
    fn action_properties(&self) -> Vec<ActionProperty<S1, A1>> {
        vec![action_property(B89, |s: &S1, a: &A1, t: &S1| match a {
            A1::SyncOk | A1::SyncFail => {
                let Sync::Running { found } = s.sync else { return true };
                t.tlevel == found && t.caller_pending == s.caller_pending
            }
            _ => true,
        })]
    }
}

// ---------------------------------------------------------------- part 2

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum D2 { AsBuilt, Reviewed, EarlyRelease }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum BPc { Idle, Begun, Killed, Filled, Done }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S2 {
    /// ^KG("out", g, e0) present
    pub out: bool,
    pub pc: [BPc; 2],
    pub undo: [Vec<bool>; 2],
    /// the exclusive rebuild lock (reviewed designs): who holds it
    pub excl: Option<u8>,
    /// ghost: rebuilds that failed
    pub fails: u8,
}

#[derive(Clone, Debug)]
pub enum A2 { Begin(u8), Kill(u8), Fill(u8), Commit(u8), Fail(u8) }

pub struct Concurrent { pub design: D2 }

pub const HD0402: &str = "ADJ-Q8.10/HD-0402: with no rebuild open the adjacency holds exactly the committed rows";

impl Model for Concurrent {
    type State = S2;
    type Action = A2;
    fn init_states(&self) -> Vec<S2> {
        vec![S2 { out: true, pc: [BPc::Idle; 2], undo: [vec![], vec![]], excl: None, fails: 0 }]
    }
    fn actions(&self, _: &S2) -> Vec<A2> {
        (0..2u8).flat_map(|i| [A2::Begin(i), A2::Kill(i), A2::Fill(i), A2::Commit(i), A2::Fail(i)]).collect()
    }
    fn next(&self, s: &S2, a: &A2) -> Option<S2> {
        let mut u = s.clone();
        let open = |pc: BPc| matches!(pc, BPc::Begun | BPc::Killed | BPc::Filled);
        match *a {
            A2::Begin(i) => {
                if s.pc[i as usize] != BPc::Idle { return None; }
                if self.design != D2::AsBuilt { if s.excl.is_some() { return None; } u.excl = Some(i); }
                u.pc[i as usize] = BPc::Begun;
            }
            A2::Kill(i) => {
                if s.pc[i as usize] != BPc::Begun { return None; }
                u.undo[i as usize].push(s.out); u.out = false; u.pc[i as usize] = BPc::Killed;
                if self.design == D2::EarlyRelease { u.excl = None; }
            }
            A2::Fill(i) => {
                if s.pc[i as usize] != BPc::Killed { return None; }
                u.undo[i as usize].push(s.out); u.out = true; u.pc[i as usize] = BPc::Filled;
            }
            A2::Commit(i) => {
                if s.pc[i as usize] != BPc::Filled { return None; }
                u.undo[i as usize].clear(); u.pc[i as usize] = BPc::Done;
                if s.excl == Some(i) { u.excl = None; }
            }
            A2::Fail(i) => {
                if !open(s.pc[i as usize]) { return None; }
                for before in s.undo[i as usize].iter().rev() { u.out = *before; }
                u.undo[i as usize].clear(); u.pc[i as usize] = BPc::Done; u.fails += 1;
                if s.excl == Some(i) { u.excl = None; }
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S2>> {
        vec![invariant(HD0402, |s: &S2| {
            if s.pc.iter().any(|p| matches!(p, BPc::Begun | BPc::Killed | BPc::Filled)) { return true; }
            s.out
        })]
    }
    fn always_possibly(&self) -> Vec<Invariant<S2>> {
        vec![invariant("both rebuilds can finish and the lock is released", |s: &S2| {
            s.pc.iter().all(|p| *p == BPc::Done) && s.excl.is_none()
        })]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("04", "adj_rebuild_txn");
    let ab = Caller { design: D1::AsBuilt };
    let rv = Caller { design: D1::Reviewed };
    let ct = Caller { design: D1::LevelAfterTStart };
    let cab = Concurrent { design: D2::AsBuilt };
    let crv = Concurrent { design: D2::Reviewed };
    let cct = Concurrent { design: D2::EarlyRelease };
    vec![
        check("adj_rebuild_txn-as-built-F0409", md, fam, "as-built", "safety", Expect::Violation(B89), &ab),
        check("adj_rebuild_txn-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &rv),
        check("adj_rebuild_txn-control-level-after-tstart", md, fam, "control", "safety", Expect::Violation(B89), &ct),
        reach("adj_rebuild_txn-reviewed-reach-caller-commits-after-failed-sync", md, fam, "reviewed", &rv,
              "never: the caller commits its own row after a failed rebuild",
              |s: &S1| s.caller_committed && matches!(s.sync_returned_at, Some((1, 1)))),
        check("adj_rebuild_txn-concurrent-as-built-HD0402", md, fam, "as-built", "safety", Expect::Violation(HD0402), &Keep::safety(&cab)),
        check("adj_rebuild_txn-concurrent-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &Keep::safety(&crv)),
        check("adj_rebuild_txn-concurrent-control-early-release", md, fam, "control", "safety", Expect::Violation(HD0402), &Keep::safety(&cct)),
        check("adj_rebuild_txn-concurrent-reviewed-progress", md, fam, "reviewed", "progress", Expect::Pass, &Keep::progress(&crv)),
        reach("adj_rebuild_txn-concurrent-reviewed-reach-failed-rebuild", md, fam, "reviewed", &crv,
              "never: a rebuild fails and the other then commits",
              |s: &S2| s.pc == [BPc::Done, BPc::Done] && s.out && s.fails == 1),
    ]
}
