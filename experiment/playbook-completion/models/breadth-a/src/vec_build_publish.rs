//! Family vec_build_publish (module 06; decision HD-0602, assumption; statement VEC-Q11.18).
//!
//! `ivf_build` (iris_vector_graph/_engine/vector.py:1880-2027) rebuilds an IVF index in several server calls on one
//! name: `IVFIndex.Build` (IVFIndex.cls:6-53: `Kill ^IVF(name)` first, then centroids and cfg with
//! indexed = 0; the Python passes no assignments, "[]"), then one `AddBatch` per `build_batch_size` vectors
//! (IVFIndex.cls:237-257; vector.py:2012-2020), then `FinalizeIndex` (IVFIndex.cls:260-276). Nothing makes these
//! calls one unit, and the builder can stop between any two (an error, a stopped process: none rolls back, the
//! calls run outside a transaction). A concurrent `IVFIndex.Search` (IVFIndex.cls:55-158; `ivf_search`) answers
//! "[]" when cfg nlist is absent (57-58) — which ivf_search documents as "the index does not exist" and a caller
//! cannot tell from "no match" — and otherwise from whatever lists are there.
//!
//! Modeled: the index already holds a complete generation over ids {a, b} (batch 1 = a, batch 2 = b); one rebuild
//! of the same data; a reader that searches repeatedly (k large, so an answer is the set of listed ids).
//!
//! Designs:
//! - `AsBuilt`: the steps above, in place.
//! - `Reviewed` (HD-0602: "readers see a complete published index or a clear unavailable result, including
//!   interrupted rebuilds"; atomic publication is one of the named alternatives): build under a staging name, then
//!   publish in one step (a single Set of the published pointer, or Kill+Merge inside one transaction); a stopped
//!   build leaves the previous complete index published.
//! - `EarlyPublish` (negative control): the reviewed design that publishes before the last AddBatch.
//!
//! Invariant `VEC-Q11.18/HD-0602`: every search answers from a complete generation or says "unavailable".
use explorer::*;
use std::collections::BTreeSet;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, EarlyPublish }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum B { Idle, Built, Added1, Added2, Finalized, Published, Stopped }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Answer { None, Unavailable, Ids(u8) }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    /// the store searches read: None = no cfg (nlist absent); Some(ids listed)
    pub live: Option<BTreeSet<u8>>,
    /// the staging store (reviewed designs)
    pub staging: Option<BTreeSet<u8>>,
    pub b: B,
    pub last: Answer,
    pub searches: u8,
}

#[derive(Clone, Debug)]
pub enum A { Build, Add1, Add2, Finalize, Publish, Stop, Search }

pub struct M { pub design: Design }

pub const INV: &str = "VEC-Q11.18/HD-0602: a search answers from a complete index or says unavailable";

fn target(u: &mut S, inplace: bool) -> &mut Option<BTreeSet<u8>> { if inplace { &mut u.live } else { &mut u.staging } }

fn enc(ids: &BTreeSet<u8>) -> u8 { ids.iter().fold(0, |m, i| m | (1 << i)) }

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { live: Some([0, 1].into_iter().collect()), staging: None, b: B::Idle, last: Answer::None, searches: 0 }]
    }
    fn actions(&self, _: &S) -> Vec<A> { vec![A::Build, A::Add1, A::Add2, A::Finalize, A::Publish, A::Stop, A::Search] }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let inplace = self.design == Design::AsBuilt;
        match a {
            A::Build => { if s.b != B::Idle { return None; } *target(&mut u, inplace) = Some(BTreeSet::new()); u.b = B::Built; }
            A::Add1 => { if s.b != B::Built { return None; } target(&mut u, inplace).as_mut()?.insert(0); u.b = B::Added1; }
            A::Add2 => {
                if s.b != B::Added1 { return None; }
                if self.design == Design::EarlyPublish { u.live = u.staging.clone(); }
                target(&mut u, inplace).as_mut()?.insert(1); u.b = B::Added2;
            }
            A::Finalize => { if s.b != B::Added2 { return None; } u.b = B::Finalized; }
            A::Publish => {
                if s.b != B::Finalized { return None; }
                if !inplace { u.live = u.staging.take(); }
                u.b = B::Published;
            }
            A::Stop => { if matches!(s.b, B::Idle | B::Published | B::Stopped) { return None; } u.b = B::Stopped; }
            A::Search => {
                if s.searches >= 3 { return None; }
                u.searches += 1;
                u.last = match &s.live {
                    // as built: "[]" (no cfg) reads as an empty answer; reviewed: an explicit unavailable
                    None => if inplace { Answer::Ids(0) } else { Answer::Unavailable },
                    Some(ids) => Answer::Ids(enc(ids)),
                };
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(INV, |s: &S| matches!(s.last, Answer::None | Answer::Unavailable | Answer::Ids(3)))]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("06", "vec_build_publish");
    let ab = M { design: Design::AsBuilt };
    let rv = M { design: Design::Reviewed };
    let ct = M { design: Design::EarlyPublish };
    vec![
        check("vec_build_publish-as-built-HD0602", md, fam, "as-built", "safety", Expect::Violation(INV), &ab),
        check("vec_build_publish-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &rv),
        check("vec_build_publish-control-early-publish", md, fam, "control", "safety", Expect::Violation(INV), &ct),
        reach("vec_build_publish-reviewed-reach-published", md, fam, "reviewed", &rv,
              "never: a rebuilt index is published and searched", |s: &S| s.b == B::Published && s.last == Answer::Ids(3)),
        reach("vec_build_publish-reviewed-reach-stopped", md, fam, "reviewed", &rv,
              "never: a stopped rebuild leaves the old index answering", |s: &S| s.b == B::Stopped && s.last == Answer::Ids(3) && s.searches >= 1),
        reach("vec_build_publish-as-built-reach-stopped-partial", md, fam, "as-built", &ab,
              "never: a stopped rebuild leaves a partial index answering", |s: &S| s.b == B::Stopped && s.last == Answer::Ids(1)),
    ]
}
