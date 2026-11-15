//! Module 10 (algorithms), L1 part 2: result contracts of shortest paths, variable-length walks and label
//! propagation, as a business contract.
//!
//! **Result-contract abstraction (not the numerics).** A shortest-path answer is `Len(n)`, `NoPath` or `Refused`
//! (the paths themselves and their predicates are not modelled); a variable-length expansion answers the set of end
//! nodes reached within [lo, hi] hops; label propagation answers a label per node. What is modelled is each answer's
//! contract: the length is the least walk length in the direction asked; an unsupported direction is refused; a
//! walk's edges belong to one graph; every node of the default graph gets a label that is a node of the default graph.
//! Which label wins a round (the most frequent, ties by collation) and convergence are numerics and are not modelled
//! (HD-1002 working answer: a non-converged answer is documented, no flag).
//!
//! State: the default graph's nodes `nodes0` and every graph's edges `edges` (graph, source, target; one predicate).
//! Business rules:
//!
//! - **a shortest path is the least walk length in the direction asked; "in" is the reverse of "out"** ("an incoming
//!   path from a to b is an outgoing one from b to a, read backwards", iris_vector_graph/stores/iris_sql_store.py:
//!   2197-2199), and **a direction outside {out, in, both} is refused** (HD-1003 working answer, supported: maintainer
//!   commit 99b00ce9; TraversalPaths.CheckDirection, TraversalPaths.cls:348-355);
//! - **a walk's edges all belong to one graph** (CONTEXT.md:38-43; ALG-I2): an every-graph expansion is the union of
//!   each graph's own expansion;
//! - **label propagation labels every node of the default graph with a node of the default graph** (kg_CDLP's
//!   docstring, _engine/algorithms.py:829-840: one row per node, an edgeless node keeps its own label).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct E { pub g: int, pub a: int, pub b: int }
pub enum Dir { Out, In, Both, Other }
pub enum Sp { Refused, NoPath, Len { n: nat } }

pub struct TS1 { pub nodes0: Set<int>, pub edges: Set<E> }

pub enum TL1 {
    AddNode { n: int },
    AddEdge { g: int, a: int, b: int },
    DelEdge { g: int, a: int, b: int },
    Path { a: int, b: int, maxh: nat, dir: Dir, ans: Sp },
    VarLen { start: int, lo: nat, hi: nat, all: bool, ends: Set<int> },
    Cdlp { labels: Map<int, int> },
}

/// A walk of exactly n steps from a to b along the step relation st.
pub open spec fn walk(st: spec_fn(int, int) -> bool, a: int, b: int, n: nat) -> bool
    decreases n,
{
    if n == 0 { a == b } else { exists|c: int| #[trigger] st(a, c) && walk(st, c, b, (n - 1) as nat) }
}

pub open spec fn st_out(es: Set<E>, g: int) -> spec_fn(int, int) -> bool { |x: int, y: int| es.contains(E { g, a: x, b: y }) }
pub open spec fn st_both(es: Set<E>, g: int) -> spec_fn(int, int) -> bool {
    |x: int, y: int| es.contains(E { g, a: x, b: y }) || es.contains(E { g, a: y, b: x })
}

pub open spec fn shortest(st: spec_fn(int, int) -> bool, a: int, b: int, maxh: nat, ans: Sp) -> bool {
    match ans {
        Sp::Len { n } => n <= maxh && walk(st, a, b, n) && forall|m: nat| m < n ==> !#[trigger] walk(st, a, b, m),
        Sp::NoPath => forall|m: nat| m <= maxh ==> !#[trigger] walk(st, a, b, m),
        Sp::Refused => false,
    }
}

pub open spec fn path1(es: Set<E>, a: int, b: int, maxh: nat, dir: Dir, ans: Sp) -> bool {
    match dir {
        Dir::Out => shortest(st_out(es, 0), a, b, maxh, ans),
        Dir::In => shortest(st_out(es, 0), b, a, maxh, ans),
        Dir::Both => shortest(st_both(es, 0), a, b, maxh, ans),
        Dir::Other => ans is Refused,
    }
}

pub open spec fn reach1(es: Set<E>, start: int, lo: nat, hi: nat, all: bool, t: int) -> bool {
    exists|l: nat, g: int| lo <= l <= hi && (all || g == 0) && #[trigger] walk(st_out(es, g), start, t, l)
}

pub open spec fn varlen1(es: Set<E>, start: int, lo: nat, hi: nat, all: bool, ends: Set<int>) -> bool {
    forall|x: int| #[trigger] ends.contains(x) <==> reach1(es, start, lo, hi, all, x)
}

pub open spec fn cdlp1(s: TS1, labels: Map<int, int>) -> bool {
    labels.dom() == s.nodes0 && forall|n: int| #[trigger] labels.contains_key(n) ==> s.nodes0.contains(labels[n])
}

pub open spec fn next1(s: TS1, l: TL1, t: TS1) -> bool {
    match l {
        TL1::AddNode { n } => t == (TS1 { nodes0: s.nodes0.insert(n), ..s }),
        TL1::AddEdge { g, a, b } => (g == 0 ==> s.nodes0.contains(a) && s.nodes0.contains(b))
            && t == (TS1 { edges: s.edges.insert(E { g, a, b }), ..s }),
        TL1::DelEdge { g, a, b } => s.edges.contains(E { g, a, b }) && t == (TS1 { edges: s.edges.remove(E { g, a, b }), ..s }),
        TL1::Path { a, b, maxh, dir, ans } => path1(s.edges, a, b, maxh, dir, ans) && t == s,
        TL1::VarLen { start, lo, hi, all, ends } => varlen1(s.edges, start, lo, hi, all, ends) && t == s,
        TL1::Cdlp { labels } => cdlp1(s, labels) && t == s,
    }
}

pub struct TravL1;

impl Contract for TravL1 {
    type S = TS1;
    type L = TL1;
    open spec fn init(s: TS1) -> bool { s.edges == Set::<E>::empty() }
    open spec fn next(s: TS1, l: TL1, t: TS1) -> bool { next1(s, l, t) }
}

/// The default graph's edges join its nodes.
pub open spec fn inv1(s: TS1) -> bool {
    forall|e: E| #[trigger] s.edges.contains(e) && e.g == 0 ==> s.nodes0.contains(e.a) && s.nodes0.contains(e.b)
}

pub proof fn lemma_l1_safe(s: TS1, l: TL1, t: TS1)
    requires inv1(s), next1(s, l, t),
    ensures inv1(t),
{
    match l {
        TL1::DelEdge { g, a, b } => {
            assert forall|e: E| #[trigger] t.edges.contains(e) && e.g == 0 implies t.nodes0.contains(e.a) && t.nodes0.contains(e.b) by {
                assert(s.edges.contains(e));
            }
        }
        _ => {}
    }
}

impl SafeContract for TravL1 {
    open spec fn inv(s: TS1) -> bool { inv1(s) }
    proof fn init_safe(s: TS1) {}
    proof fn step_safe(s: TS1, l: TL1, t: TS1) { lemma_l1_safe(s, l, t); }
}

/// A walk of one step is an edge of the step relation.
pub proof fn lemma_walk1(st: spec_fn(int, int) -> bool, a: int, b: int)
    ensures walk(st, a, b, 1) == st(a, b),
{
    reveal_with_fuel(walk, 2);
    if st(a, b) { assert(walk(st, b, b, 0)); }
}

/// A walk of two steps is a pair of steps through some node.
pub proof fn lemma_walk2(st: spec_fn(int, int) -> bool, a: int, b: int)
    ensures walk(st, a, b, 2) == exists|c: int| #[trigger] st(a, c) && st(c, b),
{
    assert(walk(st, a, b, 2) == exists|c: int| #[trigger] st(a, c) && walk(st, c, b, 1));
    assert forall|c: int| #[trigger] walk(st, c, b, 1) == st(c, b) by { lemma_walk1(st, c, b); }
}

/// Walks over pointwise-equal step relations are equal.
pub proof fn lemma_walk_ext(f: spec_fn(int, int) -> bool, h: spec_fn(int, int) -> bool, a: int, b: int, n: nat)
    requires forall|x: int, y: int| #[trigger] f(x, y) == h(x, y),
    ensures walk(f, a, b, n) == walk(h, a, b, n),
    decreases n,
{
    if n > 0 {
        assert forall|c: int| #![trigger f(a, c)] #![trigger h(a, c)]
            (f(a, c) && walk(f, c, b, (n - 1) as nat)) == (h(a, c) && walk(h, c, b, (n - 1) as nat)) by {
            lemma_walk_ext(f, h, c, b, (n - 1) as nat);
        }
        assert(walk(f, a, b, n) == exists|c: int| #[trigger] f(a, c) && walk(f, c, b, (n - 1) as nat));
        assert(walk(h, a, b, n) == exists|c: int| #[trigger] h(a, c) && walk(h, c, b, (n - 1) as nat));
    }
}

pub proof fn lemma_shortest_ext(f: spec_fn(int, int) -> bool, h: spec_fn(int, int) -> bool, a: int, b: int, maxh: nat, ans: Sp)
    requires forall|x: int, y: int| #[trigger] f(x, y) == h(x, y),
    ensures shortest(f, a, b, maxh, ans) == shortest(h, a, b, maxh, ans),
{
    assert forall|m: nat| #![trigger walk(f, a, b, m)] #![trigger walk(h, a, b, m)] walk(f, a, b, m) == walk(h, a, b, m) by {
        lemma_walk_ext(f, h, a, b, m);
    }
}

/// HD-1003: "in" from a to b answers what "out" from b to a answers; another direction is refused.
pub proof fn theorem_direction_contract(s: TS1, a: int, b: int, maxh: nat, dir: Dir, ans: Sp, t: TS1)
    requires next1(s, TL1::Path { a, b, maxh, dir, ans }, t),
    ensures
        dir is Other <==> ans is Refused,
        dir is In ==> shortest(st_out(s.edges, 0), b, a, maxh, ans),
        ans is Len && dir is Out ==> walk(st_out(s.edges, 0), a, b, ans->Len_n),
        ans is Len && dir is In ==> walk(st_out(s.edges, 0), b, a, ans->Len_n),
{
}

/// CONTEXT.md:38-43 / ALG-I2: every end of an expansion is reached by a walk inside one graph.
pub proof fn theorem_walk_in_one_graph(s: TS1, start: int, lo: nat, hi: nat, all: bool, ends: Set<int>, t: TS1, x: int)
    requires next1(s, TL1::VarLen { start, lo, hi, all, ends }, t), ends.contains(x),
    ensures exists|l: nat, g: int| lo <= l <= hi && (all || g == 0) && #[trigger] walk(st_out(s.edges, g), start, x, l),
{
    assert(reach1(s.edges, start, lo, hi, all, x));
}

/// Label propagation labels every node of the default graph, with a node of the default graph.
pub proof fn theorem_labels_are_nodes(s: TS1, labels: Map<int, int>, t: TS1, n: int)
    requires next1(s, TL1::Cdlp { labels }, t), s.nodes0.contains(n),
    ensures labels.contains_key(n), s.nodes0.contains(labels[n]),
{
}

} // verus!
