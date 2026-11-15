//! Family vec_ivf (module 06; findings F-0608, F-0606; statements VEC-B11.14, VEC-B11.4; decision HD-0601,
//! assumption).
//!
//! One IVF index ^IVF(name) (iris_src/src/Graph/KG/IVFIndex.cls) over graph g's vectors, two cells, two node ids
//! a, b of g. State: the cells each id is listed in (^IVF(name, "list", cell, id)), the "indexed" counter
//! (^IVF(name, "cfg", "indexed")), the ids with a live vector in g, and two inserting processes.
//!
//! Operations:
//! - `Insert(p, id, cell)`: IVFIndex.Insert (IVFIndex.cls:180-215): Set the list entry in the best cell (no removal
//!   of the id from another cell), then `Set indexed = $Get(indexed) + 1` — a read and a write, so modeled as two
//!   steps (`InsSet` then `InsCount`), and two concurrent inserts can lose one count.
//! - `Delete(id)`: IVFIndex.Delete (IVFIndex.cls:217-232): removes the id from the first cell where it is found
//!   (`Quit` after one) and decrements indexed.
//! - `EraseGraph`: Graph.KG.Eraser.EraseGraph(g) removes g's nodes and vectors; it names no ^IVF (Eraser.cls;
//!   GraphStores.cls:28-133 does not list ^IVF), so the index keeps g's ids (F-0606).
//!
//! Designs:
//! - `AsBuilt`.
//! - `Reviewed`: Insert removes the id from every other cell and counts with $Increment only an id that was not
//!   indexed (one step); Delete removes it from every cell; EraseGraph drops g's ids from the index (HD-0601:
//!   "for graph-owned indexes require invalidation or deletion").
//! - `CountEvery` (negative control): the reviewed design whose Insert counts every insert again.
//!
//! Invariants: `VEC-B11.14` an id is listed in at most one cell (a re-inserted vector replaces the old one);
//! `VEC-B11.14 count` indexed equals the number of distinct ids listed (when no insert is mid-way);
//! `VEC-B11.4/HD-0601` the index lists only ids with a live vector (after an erase, none of g's).
use explorer::*;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, CountEvery }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub lists: BTreeMap<u8, BTreeSet<u8>>,
    pub indexed: i8,
    pub live: BTreeSet<u8>,
    pub p: [Option<i8>; 2],
    pub ops: u8,
}

#[derive(Clone, Debug)]
pub enum A { InsSet(u8, u8, u8), InsCount(u8), Delete(u8), EraseGraph }

pub struct M { pub design: Design }

pub const ONE: &str = "VEC-B11.14: an id is listed in at most one cell";
pub const COUNT: &str = "VEC-B11.14: indexed equals the number of distinct ids listed";
pub const LIVE: &str = "VEC-B11.4/HD-0601: the index lists only ids with a live vector";

fn distinct(s: &S) -> i8 { s.lists.values().filter(|c| !c.is_empty()).count() as i8 }

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { lists: BTreeMap::new(), indexed: 0, live: [0, 1].into_iter().collect(), p: [None, None], ops: 0 }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![A::EraseGraph, A::Delete(0), A::Delete(1), A::InsCount(0), A::InsCount(1)];
        for p in 0..2 { for id in 0..2 { for c in 0..2 { v.push(A::InsSet(p, id, c)); } } }
        v
    }
    fn within_bounds(&self, s: &S) -> bool { s.ops < 4 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        match *a {
            A::InsSet(p, id, c) => {
                if s.p[p as usize].is_some() || !s.live.contains(&id) { return None; }
                u.ops += 1;
                match self.design {
                    Design::AsBuilt => {
                        u.lists.entry(id).or_default().insert(c);
                        u.p[p as usize] = Some(s.indexed); // the read of $Get(indexed)
                    }
                    Design::Reviewed | Design::CountEvery => {
                        let was = s.lists.get(&id).is_some_and(|x| !x.is_empty());
                        u.lists.insert(id, [c].into_iter().collect());
                        if !was || self.design == Design::CountEvery { u.indexed += 1; }
                    }
                }
            }
            A::InsCount(p) => {
                let r = s.p[p as usize]?;
                u.indexed = r + 1; u.p[p as usize] = None;
            }
            A::Delete(id) => {
                let cells = s.lists.get(&id)?.clone();
                let first = *cells.iter().next()?;
                u.ops += 1;
                match self.design {
                    Design::AsBuilt => { u.lists.get_mut(&id).unwrap().remove(&first); }
                    _ => { u.lists.remove(&id); }
                }
                u.indexed -= 1;
                if u.lists.get(&id).is_some_and(|x| x.is_empty()) { u.lists.remove(&id); }
            }
            A::EraseGraph => {
                if s.live.is_empty() { return None; }
                u.ops += 1;
                u.live.clear();
                if self.design != Design::AsBuilt { u.lists.clear(); u.indexed = 0; }
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(ONE, |s: &S| s.lists.values().all(|c| c.len() <= 1)),
            invariant(COUNT, |s: &S| s.p != [None, None] || s.indexed == distinct(s)),
            invariant(LIVE, |s: &S| s.lists.iter().all(|(id, c)| c.is_empty() || s.live.contains(id))),
        ]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("06", "vec_ivf");
    let ab = M { design: Design::AsBuilt };
    let rv = M { design: Design::Reviewed };
    let ct = M { design: Design::CountEvery };
    vec![
        check("vec_ivf-as-built-F0608-one-cell", md, fam, "as-built", "safety", Expect::Violation(ONE), &Keep::invariants(&ab, &[ONE])),
        check("vec_ivf-as-built-F0608-count", md, fam, "as-built", "safety", Expect::Violation(COUNT), &Keep::invariants(&ab, &[COUNT])),
        check("vec_ivf-as-built-F0606-erase", md, fam, "as-built", "safety", Expect::Violation(LIVE), &Keep::invariants(&ab, &[LIVE])),
        check("vec_ivf-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &rv),
        check("vec_ivf-control-count-every", md, fam, "control", "safety", Expect::Violation(COUNT), &ct),
        reach("vec_ivf-reviewed-reach-reinsert", md, fam, "reviewed", &rv,
              "never: an id is re-inserted into another cell", |s: &S| s.lists.get(&0).is_some_and(|c| c.contains(&1)) && s.ops >= 2),
        reach("vec_ivf-reviewed-reach-erased", md, fam, "reviewed", &rv,
              "never: the graph is erased after its ids were indexed", |s: &S| s.live.is_empty() && s.ops >= 2),
    ]
}
