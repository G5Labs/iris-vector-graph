//! Family gid_mode (module 02; findings F-0201, F-0207, F-0208; statement GID-I4.10; spec 234 FR-002).
//!
//! One triple (s, p, o) of one graph g. State: the edge keys of its rows (unique key (s, p, o_id, graph_id, ekey),
//! iris_vector_graph/schema.py:44), the live mode ^IVG.GraphMode(g) (GraphMode.cls:1-12), and each of two engines'
//! cached mode (admin.py:917-926: `is_multigraph` caches per engine with no expiry; only that engine's
//! `set_multigraph`/erase forget it, admin.py:928-936).
//!
//! Operations (each SQL statement is one step; a Cypher statement asks the mode once, then inserts):
//! - `SetOn(e)`: GraphMode.Set(g, 1) sets the mode (GraphMode.cls:30-33); engine e forgets its cache.
//! - `SetOffCount` / `SetOffKill` (engine 0, the admin): GraphMode.Set(g, 0) runs ParallelCount (one SQL,
//!   GraphMode.cls:35-40, 48-61), refuses if > 0, else kills the mode — two steps, no lock (F-0207).
//! - `CyMode(e)` then `CyInsert(e)`: a Cypher CREATE of the relationship. `_multigraph` asks the engine's
//!   `is_multigraph` once per statement (translator.py:441-457); on, it inserts at COALESCE(MAX(ekey)+1, 0)
//!   (translator.py:10368-10388); off, it is the plain insert at the column default ekey 0, which the unique key
//!   refuses only when ekey 0 exists.
//! - `CreateEdge(e)`: create_edge's guarded insert `... WHERE NOT EXISTS (... AND ekey = 0)` (nodes_edges.py:
//!   1205-1219 with `_ekey_guard`, 1257-1273): a lone row at ekey 1 does not stop it (F-0201).
//! - `StoreEdge(e)`: store_edge's plain insert at ekey 0, duplicate swallowed (nodes_edges.py:2560-2581).
//! - `CyDelete(k)`: a Cypher per-edge DELETE of the row with edge key k (spec 234; keys are never renumbered,
//!   GID-B5.3).
//!
//! Design flags (as built = all three flaws):
//! - `ekey0_guard` (F-0201): the single-edge writers guard only edge key 0; fixed: they refuse when the triple has
//!   any row.
//! - `set_unlocked` (F-0207): Set(g, 0) counts and kills in two unlocked steps, and writers take no lock; fixed:
//!   Set holds an exclusive lock across count and kill, and each Cypher writer holds it shared from its mode read to
//!   its insert (the finding's "a lock the multigraph writers also take").
//! - `cache_forever` (F-0208): each engine keeps the first mode it read; fixed: the mode is read per statement.
//!
//! Invariant `GID-I4.10`: a graph whose mode is off never holds parallel edges, whatever engine or path writes it.
//! Bounds: at most 6 operations, edge keys below 4.
use explorer::*;
use std::collections::BTreeSet;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Flaws { pub ekey0_guard: bool, pub set_unlocked: bool, pub cache_forever: bool, pub writer_lock: bool }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub rows: BTreeSet<u8>,
    pub mode: bool,
    pub cache: [Option<bool>; 2],
    pub set_counted: bool,
    /// Cypher statement in flight per engine: the mode it read
    pub cy: [Option<bool>; 2],
    /// exclusive (Set) / shared (writers) lock holders
    pub excl: bool,
    pub shared: u8,
    pub ops: u8,
}

#[derive(Clone, Debug)]
#[allow(dead_code)] // the engine of CreateEdge/StoreEdge is shown in traces only
pub enum A { SetOn(u8), SetOffCount, SetOffKill, CyMode(u8), CyInsert(u8), CreateEdge(u8), StoreEdge(u8), CyDelete(u8) }

pub struct M { pub flaws: Flaws, pub engines: u8 }

pub const INV: &str = "GID-I4.10: a graph whose mode is off holds no parallel edges";

impl M {
    fn guard_blocks(&self, s: &S) -> bool {
        if self.flaws.ekey0_guard { s.rows.contains(&0) } else { !s.rows.is_empty() }
    }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { rows: BTreeSet::new(), mode: false, cache: [None, None], set_counted: false, cy: [None, None],
                 excl: false, shared: 0, ops: 0 }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![A::SetOffCount, A::SetOffKill];
        for e in 0..self.engines {
            v.extend([A::SetOn(e), A::CyMode(e), A::CyInsert(e), A::CreateEdge(e), A::StoreEdge(e)]);
        }
        v.extend((0..4).map(A::CyDelete));
        v
    }
    fn within_bounds(&self, s: &S) -> bool { s.ops < 6 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let locked_sets = !self.flaws.set_unlocked;
        match *a {
            A::SetOn(e) => { u.mode = true; u.cache[e as usize] = None; u.ops += 1; }
            A::SetOffCount => {
                if s.set_counted || !s.mode { return None; }
                if locked_sets { if s.excl || s.shared > 0 { return None; } u.excl = true; }
                if s.rows.len() > 1 {
                    u.excl = false; // refused: parallel_edges_present
                } else {
                    u.set_counted = true;
                    if locked_sets { // count and kill as one locked unit
                        u.mode = false; u.cache[0] = None; u.set_counted = false; u.excl = false;
                    }
                }
                u.ops += 1;
            }
            A::SetOffKill => {
                if !s.set_counted { return None; }
                u.mode = false; u.cache[0] = None; u.set_counted = false;
            }
            A::CyMode(e) => {
                let i = e as usize;
                if s.cy[i].is_some() { return None; }
                if self.flaws.writer_lock && locked_sets { if s.excl { return None; } u.shared += 1; }
                let m = if self.flaws.cache_forever {
                    match s.cache[i] { Some(c) => c, None => { u.cache[i] = Some(s.mode); s.mode } }
                } else { s.mode };
                u.cy[i] = Some(m);
                u.ops += 1;
            }
            A::CyInsert(e) => {
                let i = e as usize;
                let m = s.cy[i]?;
                if m {
                    let k = s.rows.iter().max().map_or(0, |x| x + 1);
                    if k < 4 { u.rows.insert(k); }
                } else if !self.guard_blocks(s) {
                    u.rows.insert(0);
                }
                u.cy[i] = None;
                if self.flaws.writer_lock && locked_sets { u.shared -= 1; }
            }
            A::CreateEdge(_) | A::StoreEdge(_) => {
                if !self.guard_blocks(s) { u.rows.insert(0); }
                u.ops += 1;
            }
            A::CyDelete(k) => { if !s.rows.contains(&k) { return None; } u.rows.remove(&k); u.ops += 1; }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(INV, |s: &S| s.mode || s.rows.len() <= 1)]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("no statement in flight and no lock held", |s: &S| s.cy == [None, None] && !s.excl && s.shared == 0 && !s.set_counted)]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("02", "gid_mode");
    let none = Flaws { ekey0_guard: false, set_unlocked: false, cache_forever: false, writer_lock: true };
    let ab = M { flaws: Flaws { ekey0_guard: true, set_unlocked: true, cache_forever: true, writer_lock: false }, engines: 2 };
    let f0201 = M { flaws: Flaws { ekey0_guard: true, ..none }, engines: 1 };
    let f0207 = M { flaws: Flaws { set_unlocked: true, writer_lock: false, ..none }, engines: 2 };
    let f0208 = M { flaws: Flaws { cache_forever: true, ..none }, engines: 2 };
    let rv = M { flaws: none, engines: 2 };
    let ctl = M { flaws: Flaws { writer_lock: false, ..none }, engines: 2 };
    vec![
        check("gid_mode-as-built", md, fam, "as-built", "safety", Expect::Violation(INV), &Keep::safety(&ab)),
        check("gid_mode-as-built-F0201", md, fam, "as-built", "safety", Expect::Violation(INV), &Keep::safety(&f0201)),
        check("gid_mode-as-built-F0207", md, fam, "as-built", "safety", Expect::Violation(INV), &Keep::safety(&f0207)),
        check("gid_mode-as-built-F0208", md, fam, "as-built", "safety", Expect::Violation(INV), &Keep::safety(&f0208)),
        check("gid_mode-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &Keep::safety(&rv)),
        check("gid_mode-control-writers-unlocked", md, fam, "control", "safety", Expect::Violation(INV), &Keep::safety(&ctl)),
        check("gid_mode-reviewed-progress", md, fam, "reviewed", "progress", Expect::Pass, &Keep::progress(&rv)),
        reach("gid_mode-reviewed-reach-parallel-then-off", md, fam, "reviewed", &rv,
              "never: a multigraph holds two edges of the triple, then (after a delete) is set back to off",
              |s: &S| !s.mode && s.rows.len() == 1 && s.rows.contains(&1)),
        reach("gid_mode-reviewed-reach-parallel", md, fam, "reviewed", &rv,
              "never: a multigraph holds parallel edges", |s: &S| s.mode && s.rows.len() >= 2),
    ]
}
