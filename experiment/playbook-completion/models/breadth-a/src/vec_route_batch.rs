//! Family vec_route_batch (module 06; finding F-0615; statement VEC-X3.9; system statement SYS-I3: a refused write
//! changes no store).
//!
//! `store_embeddings(items, graph=g, model_key=k)` (iris_vector_graph/_engine/embeddings.py:1044-1100):
//! one width per batch (1051-1057), then `_route_for_write(graph, model, dimension=widths[0])` resolves the route
//! with create=True — creating the kg_emb_ table, its index and the registry row, and committing them
//! (embeddings.py:470-558) — and enforces the identity, then checks every item's node (`_assert_node_exists`,
//! 1077-1084), refusing the whole batch for a missing node. `store_embedding` (one vector) checks the node first
//! (967).
//!
//! Modeled: the pair (g, k) with no route; node a exists, node m does not; calls choose a batch from
//! {[a], [m], [a, m]} and a width from {2, 3}; at most three calls. A route records its width; a later batch of
//! another width is refused by the identity check (no change).
//!
//! Designs: `AsBuilt`; `Reviewed` — every item's node is checked before the route is resolved (the finding's
//! fix, as store_embedding orders it); `FirstOnly` (negative control) — the reviewed check applied to the first item
//! only.
//!
//! Action property `VEC-X3.9/SYS-I3`: a call that is refused leaves the registry and the routes as they were.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, FirstOnly }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Out { None, Stored, Refused }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S { pub route: Option<u8>, pub stored: u8, pub last: Out, pub calls: u8 }

/// items: 0 = [a], 1 = [m], 2 = [a, m]
#[derive(Clone, Debug)]
pub enum A { Store(u8, u8) }

pub struct M { pub design: Design }

pub const X39: &str = "VEC-X3.9/SYS-I3: a refused batch leaves no new route behind";

fn missing(items: u8) -> bool { items != 0 }

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { vec![S { route: None, stored: 0, last: Out::None, calls: 0 }] }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![];
        for items in 0..3 { for w in 2..=3 { v.push(A::Store(items, w)); } }
        v
    }
    fn within_bounds(&self, s: &S) -> bool { s.calls < 3 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let A::Store(items, w) = *a;
        u.calls += 1;
        let pre_check = match self.design {
            Design::AsBuilt => false,
            Design::Reviewed => missing(items),
            Design::FirstOnly => items == 1, // [m]: its first item is missing; [a, m]: the first is a
        };
        if pre_check { u.last = Out::Refused; return Some(u); }
        // resolve the route (create=True commits it), then the identity check
        match s.route {
            None => u.route = Some(w),
            Some(rw) if rw != w => { u.last = Out::Refused; return Some(u); }
            Some(_) => {}
        }
        if missing(items) { u.last = Out::Refused; return Some(u); }
        u.stored += 1; u.last = Out::Stored;
        Some(u)
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![action_property(X39, |s: &S, _: &A, t: &S| t.last != Out::Refused || t.route == s.route)]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("06", "vec_route_batch");
    let ab = M { design: Design::AsBuilt };
    let rv = M { design: Design::Reviewed };
    let ct = M { design: Design::FirstOnly };
    vec![
        check("vec_route_batch-as-built-F0615", md, fam, "as-built", "safety", Expect::Violation(X39), &ab),
        check("vec_route_batch-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &rv),
        check("vec_route_batch-control-first-item-only", md, fam, "control", "safety", Expect::Violation(X39), &ct),
        reach("vec_route_batch-reviewed-reach-route-created", md, fam, "reviewed", &rv,
              "never: a stored batch creates its route", |s: &S| s.route.is_some() && s.last == Out::Stored),
        reach("vec_route_batch-reviewed-reach-width-refusal", md, fam, "reviewed", &rv,
              "never: a batch of another width is refused by an existing route", |s: &S| s.route.is_some() && s.last == Out::Refused && s.stored >= 1),
    ]
}
