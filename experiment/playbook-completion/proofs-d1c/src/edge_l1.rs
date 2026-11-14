//! Modules 03 and 05 (with module 12's prefix erase), L1: the structural-versus-temporal edge contract.
//!
//! One namespace with the adjacency index declared (spec 252). State:
//! - `edges`: the structural edges, per triple in a graph `K { g, s, p, o }`, each with its provenance: `Explicit`
//!   (asserted by a direct write: create_edge, store_edge) or `Derived` (implied by the triple's temporal edges, ADR-0009:
//!   "a temporal edge implies a structural edge for the same triple in the same graph", CONTEXT.md:66-73);
//! - `tev`: the temporal edges, a triple at a timestamp (`Ev { k, ts }`);
//! - `nodes`: the node rows `(graph, id)`;
//! - `reg`: the (graph, predicate) pairs registered temporal-only (ADR-0015); configuration, no step changes it.
//!
//! Business rules (transition rules; `inv1` is their consequence, proved inductive):
//! - **a temporal edge of a structural predicate implies its structural edge** (ADR-0009; HD-0302 working answer:
//!   "a triple with surviving timestamps keeps a structural row"): `inv_impl`;
//! - **a derived edge exists only while its triple has a timestamp** (ADR-0009 amendment, TMP-B9.13) and only for a
//!   structural predicate (ADR-0015: a temporal-only predicate writes "nothing else"): `inv_derived`;
//! - **the temporal side never removes or changes an explicit edge** (ADR-0009; HD-0302; F-0304, F-0505): a temporal
//!   write, delete or purge drops only derived edges left without a timestamp (`keep_supported`);
//! - **an explicit write owns the edge** (create_edge docstring and ADR-0009: an explicit create over a marked row adopts
//!   it; F-0304, F-C0301): after `Create` or `Store` the edge is explicit; `Create` answers whether it was new or adopted;
//! - **a direct delete removes the explicit assertion only** (HD-0302 working answer): while the triple keeps a timestamp
//!   of a structural predicate the edge stays, derived;
//! - **a refused temporal write writes nothing** (create_edge_temporal docstring, temporal.py:259-261; F-C0501);
//! - **a prefix erase removes every node of the prefix in the graph and everything that hangs off them, temporal-only
//!   edges included** (delete_nodes_by_prefix docstring, nodes_edges.py:1529-1545; ADR-0015:59-60; F-C1203);
//! - an edge's endpoints are node rows of its graph (the composite FKs fk_edges_source/fk_edges_dest): `inv_fk`.
//!
//! Not modelled here: weights and attributes (the bucket aggregates are `tagg_l1`), the ledger (`stmt_l1`), keyed
//! multi-edges (ekey), registry changes (TemporalPolicy.Set, DropRows, BackfillRows), node retirement by purges
//! (pRetireNodes), EraseGraph and EraseAll, the non-indexed and temporal_structural_rows paths.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

/// A triple in a graph: graph key, source, predicate, target.
pub struct K { pub g: int, pub s: int, pub p: int, pub o: int }
/// A temporal edge: a triple at a timestamp.
pub struct Ev { pub k: K, pub ts: int }
/// A node row: graph key, node id.
pub struct NK { pub g: int, pub n: int }
/// A (graph key, predicate) pair.
pub struct GP { pub g: int, pub p: int }

pub enum Prov { Explicit, Derived }

pub struct ES1 {
    pub edges: Map<K, Prov>,
    pub tev: Set<Ev>,
    pub nodes: Set<NK>,
    pub reg: Set<GP>,
}

pub enum EL1 {
    /// create_node: a node row.
    Node { nk: NK },
    /// create_edge: the edge becomes explicit; `ans` is True when it was new or a derived edge was adopted.
    Create { k: K, ans: bool },
    /// store_edge: the edge becomes explicit (it answers True in every case).
    Store { k: K },
    /// delete_edge: the explicit assertion goes.
    Retract { k: K },
    /// create_edge_temporal: a temporal edge; `ok` false is a write IRIS refuses.
    TWrite { k: K, ts: int, ok: bool },
    /// delete_edge_temporal: one temporal edge goes.
    TDelete { k: K, ts: int },
    /// purge_raw_before(graph, end): the graph's temporal edges before `end` go.
    PurgeBefore { g: int, end: int },
    /// TemporalIndex.Purge: every temporal edge goes.
    Purge,
    /// delete_nodes_by_prefix(prefix, graph): `sel` is the set of ids the prefix selects.
    EraseNodes { g: int, sel: Set<int> },
}

pub open spec fn structural(reg: Set<GP>, k: K) -> bool { !reg.contains(GP { g: k.g, p: k.p }) }
pub open spec fn has_ts(tev: Set<Ev>, k: K) -> bool { exists|t: int| #[trigger] tev.contains(Ev { k, ts: t }) }
pub open spec fn supported(s: ES1, k: K) -> bool { has_ts(s.tev, k) && structural(s.reg, k) }
pub open spec fn explicit(s: ES1, k: K) -> bool { s.edges.contains_key(k) && s.edges[k] is Explicit }
pub open spec fn add_ends(nodes: Set<NK>, k: K) -> Set<NK> {
    nodes.insert(NK { g: k.g, n: k.s }).insert(NK { g: k.g, n: k.o })
}
/// After a temporal deletion: every explicit edge stays; a derived edge stays while its triple has a timestamp.
pub open spec fn keep_supported(edges: Map<K, Prov>, tev: Set<Ev>) -> Map<K, Prov> {
    Map::new(edges.dom().filter(|k: K| !(edges[k] is Derived && !has_ts(tev, k))), |k: K| edges[k])
}
pub open spec fn purge_ts(tev: Set<Ev>, g: int, end: int) -> Set<Ev> { tev.filter(|e: Ev| !(e.k.g == g && e.ts < end)) }
pub open spec fn hit(g: int, sel: Set<int>, k: K) -> bool { k.g == g && (sel.contains(k.s) || sel.contains(k.o)) }
pub open spec fn erase_nodes(nodes: Set<NK>, g: int, sel: Set<int>) -> Set<NK> {
    nodes.filter(|nk: NK| !(nk.g == g && sel.contains(nk.n)))
}
pub open spec fn erase_edges(edges: Map<K, Prov>, g: int, sel: Set<int>) -> Map<K, Prov> {
    Map::new(edges.dom().filter(|k: K| !hit(g, sel, k)), |k: K| edges[k])
}
pub open spec fn erase_ts(tev: Set<Ev>, g: int, sel: Set<int>) -> Set<Ev> { tev.filter(|e: Ev| !hit(g, sel, e.k)) }

pub struct EdgeL1;

impl Contract for EdgeL1 {
    type S = ES1;
    type L = EL1;

    open spec fn init(s: ES1) -> bool {
        s.edges == Map::<K, Prov>::empty() && s.tev == Set::<Ev>::empty() && s.nodes == Set::<NK>::empty()
    }

    open spec fn next(s: ES1, l: EL1, t: ES1) -> bool {
        match l {
            EL1::Node { nk } => t == ES1 { nodes: s.nodes.insert(nk), ..s },
            EL1::Create { k, ans } =>
                ans == !explicit(s, k) && t == ES1 { edges: s.edges.insert(k, Prov::Explicit), nodes: add_ends(s.nodes, k), ..s },
            EL1::Store { k } => t == ES1 { edges: s.edges.insert(k, Prov::Explicit), nodes: add_ends(s.nodes, k), ..s },
            EL1::Retract { k } =>
                t == ES1 { edges: if supported(s, k) { s.edges.insert(k, Prov::Derived) } else { s.edges.remove(k) }, ..s },
            EL1::TWrite { k, ts, ok } =>
                if !ok || s.tev.contains(Ev { k, ts }) {
                    t == s
                } else if structural(s.reg, k) && !s.edges.contains_key(k) {
                    t == ES1 { edges: s.edges.insert(k, Prov::Derived), tev: s.tev.insert(Ev { k, ts }),
                               nodes: add_ends(s.nodes, k), ..s }
                } else {
                    t == ES1 { tev: s.tev.insert(Ev { k, ts }), ..s }
                },
            EL1::TDelete { k, ts } =>
                s.tev.contains(Ev { k, ts })
                    && t == ES1 { tev: s.tev.remove(Ev { k, ts }), edges: keep_supported(s.edges, s.tev.remove(Ev { k, ts })), ..s },
            EL1::PurgeBefore { g, end } =>
                t == ES1 { tev: purge_ts(s.tev, g, end), edges: keep_supported(s.edges, purge_ts(s.tev, g, end)), ..s },
            EL1::Purge => t == ES1 { tev: Set::empty(), edges: keep_supported(s.edges, Set::empty()), ..s },
            EL1::EraseNodes { g, sel } =>
                t == ES1 { nodes: erase_nodes(s.nodes, g, sel), edges: erase_edges(s.edges, g, sel),
                           tev: erase_ts(s.tev, g, sel), ..s },
        }
    }
}

// ------------------------------------------------------------------------------------------------ invariant

/// ADR-0009 / HD-0302: a temporal edge of a structural predicate implies its structural edge.
pub open spec fn inv_impl(s: ES1) -> bool {
    forall|e: Ev| #[trigger] s.tev.contains(e) && structural(s.reg, e.k) ==> s.edges.contains_key(e.k)
}
/// TMP-B9.13 / ADR-0015: a derived edge has a timestamp and a structural predicate.
pub open spec fn inv_derived(s: ES1) -> bool {
    forall|k: K| #[trigger] s.edges.contains_key(k) && s.edges[k] is Derived ==> supported(s, k)
}
/// An edge's endpoints are node rows of its graph.
pub open spec fn inv_fk(s: ES1) -> bool {
    forall|k: K| #[trigger] s.edges.contains_key(k) ==> s.nodes.contains(NK { g: k.g, n: k.s }) && s.nodes.contains(NK { g: k.g, n: k.o })
}
pub open spec fn inv1(s: ES1) -> bool { inv_impl(s) && inv_derived(s) && inv_fk(s) }

// ------------------------------------------------------------------------------------------------ helper lemmas

pub proof fn lemma_has_of(tev: Set<Ev>, e: Ev)
    requires tev.contains(e),
    ensures has_ts(tev, e.k),
{
    assert(tev.contains(Ev { k: e.k, ts: e.ts }));
}

pub proof fn lemma_has_sub(a: Set<Ev>, b: Set<Ev>, k: K)
    requires has_ts(a, k), forall|e: Ev| #[trigger] a.contains(e) && e.k == k ==> b.contains(e),
    ensures has_ts(b, k),
{
    let w = choose|t: int| a.contains(Ev { k, ts: t });
    assert(a.contains(Ev { k, ts: w }));
    assert(b.contains(Ev { k, ts: w }));
}

/// A temporal deletion that keeps the supported edges keeps the invariant (TDelete, PurgeBefore, Purge).
proof fn lemma_keep_safe(s: ES1, t: ES1)
    requires inv1(s), t.edges == keep_supported(s.edges, t.tev), t.nodes == s.nodes, t.reg == s.reg,
             forall|e: Ev| #[trigger] t.tev.contains(e) ==> s.tev.contains(e),
    ensures inv1(t),
{
    let d = s.edges.dom().filter(|k: K| !(s.edges[k] is Derived && !has_ts(t.tev, k)));
    assert forall|e: Ev| #[trigger] t.tev.contains(e) && structural(t.reg, e.k) implies t.edges.contains_key(e.k) by {
        lemma_has_of(t.tev, e);
        assert(s.edges.contains_key(e.k));
        assert(d.contains(e.k));
    }
    assert forall|k: K| #[trigger] t.edges.contains_key(k) && t.edges[k] is Derived implies supported(t, k) by {
        assert(d.contains(k));
    }
    assert forall|k: K| #[trigger] t.edges.contains_key(k) implies
        t.nodes.contains(NK { g: k.g, n: k.s }) && t.nodes.contains(NK { g: k.g, n: k.o }) by {
        assert(d.contains(k));
        assert(s.edges.contains_key(k));
    }
}

proof fn lemma_assert_safe(s: ES1, k: K, t: ES1)
    requires inv1(s), t == (ES1 { edges: s.edges.insert(k, Prov::Explicit), nodes: add_ends(s.nodes, k), ..s }),
    ensures inv1(t),
{
    assert forall|x: K| #[trigger] t.edges.contains_key(x) && t.edges[x] is Derived implies supported(t, x) by {
        assert(x != k);
        assert(s.edges.contains_key(x));
    }
    assert forall|x: K| #[trigger] t.edges.contains_key(x) implies
        t.nodes.contains(NK { g: x.g, n: x.s }) && t.nodes.contains(NK { g: x.g, n: x.o }) by {
        if x != k { assert(s.edges.contains_key(x)); }
    }
}

proof fn lemma_retract_safe(s: ES1, k: K, t: ES1)
    requires inv1(s), EdgeL1::next(s, EL1::Retract { k }, t),
    ensures inv1(t),
{
    if supported(s, k) {
        let w = choose|x: int| s.tev.contains(Ev { k, ts: x });
        assert(s.tev.contains(Ev { k, ts: w }));
        assert(s.edges.contains_key(k));
        assert forall|x: K| #[trigger] t.edges.contains_key(x) && t.edges[x] is Derived implies supported(t, x) by {
            if x != k { assert(s.edges.contains_key(x)); }
        }
        assert forall|x: K| #[trigger] t.edges.contains_key(x) implies
            t.nodes.contains(NK { g: x.g, n: x.s }) && t.nodes.contains(NK { g: x.g, n: x.o }) by {
            assert(s.edges.contains_key(x));
        }
    } else {
        assert forall|e: Ev| #[trigger] t.tev.contains(e) && structural(t.reg, e.k) implies t.edges.contains_key(e.k) by {
            lemma_has_of(s.tev, e);
            assert(s.edges.contains_key(e.k));
        }
        assert forall|x: K| #[trigger] t.edges.contains_key(x) && t.edges[x] is Derived implies supported(t, x) by {
            assert(s.edges.contains_key(x));
        }
        assert forall|x: K| #[trigger] t.edges.contains_key(x) implies
            t.nodes.contains(NK { g: x.g, n: x.s }) && t.nodes.contains(NK { g: x.g, n: x.o }) by {
            assert(s.edges.contains_key(x));
        }
    }
}

proof fn lemma_twrite_safe(s: ES1, k: K, ts: int, ok: bool, t: ES1)
    requires inv1(s), EdgeL1::next(s, EL1::TWrite { k, ts, ok }, t),
    ensures inv1(t),
{
    let e = Ev { k, ts };
    if !ok || s.tev.contains(e) {
    } else {
        assert(t.tev == s.tev.insert(e));
        assert(t.tev.contains(e));
        assert forall|x: K| #[trigger] t.edges.contains_key(x) && t.edges[x] is Derived implies supported(t, x) by {
            if x == k && !s.edges.contains_key(k) {
                assert(t.tev.contains(Ev { k, ts }));
            } else {
                assert(s.edges.contains_key(x));
                lemma_has_sub(s.tev, t.tev, x);
            }
        }
        assert forall|x: K| #[trigger] t.edges.contains_key(x) implies
            t.nodes.contains(NK { g: x.g, n: x.s }) && t.nodes.contains(NK { g: x.g, n: x.o }) by {
            if !(x == k && !s.edges.contains_key(k)) { assert(s.edges.contains_key(x)); }
        }
        assert forall|e2: Ev| #[trigger] t.tev.contains(e2) && structural(t.reg, e2.k) implies t.edges.contains_key(e2.k) by {
            if e2 != e { assert(s.tev.contains(e2)); }
        }
    }
}

proof fn lemma_erase_safe(s: ES1, g: int, sel: Set<int>, t: ES1)
    requires inv1(s), EdgeL1::next(s, EL1::EraseNodes { g, sel }, t),
    ensures inv1(t),
{
    let d = s.edges.dom().filter(|k: K| !hit(g, sel, k));
    assert forall|e: Ev| #[trigger] t.tev.contains(e) && structural(t.reg, e.k) implies t.edges.contains_key(e.k) by {
        assert(s.tev.contains(e));
        assert(d.contains(e.k));
    }
    assert forall|x: K| #[trigger] t.edges.contains_key(x) && t.edges[x] is Derived implies supported(t, x) by {
        assert(d.contains(x));
        assert(s.edges.contains_key(x));
        lemma_has_sub(s.tev, t.tev, x);
    }
    assert forall|x: K| #[trigger] t.edges.contains_key(x) implies
        t.nodes.contains(NK { g: x.g, n: x.s }) && t.nodes.contains(NK { g: x.g, n: x.o }) by {
        assert(d.contains(x));
        assert(s.edges.contains_key(x));
    }
}

/// Every L1 step keeps `inv1` (used by the L2 refinement: the L2 invariant includes `inv1` of the abstraction).
pub proof fn lemma_l1_safe(s: ES1, l: EL1, t: ES1)
    requires inv1(s), EdgeL1::next(s, l, t),
    ensures inv1(t),
{
    match l {
        EL1::Node { nk } => {
            assert forall|x: K| #[trigger] t.edges.contains_key(x) implies
                t.nodes.contains(NK { g: x.g, n: x.s }) && t.nodes.contains(NK { g: x.g, n: x.o }) by {
                assert(s.edges.contains_key(x));
            }
        }
        EL1::Create { k, ans } => lemma_assert_safe(s, k, t),
        EL1::Store { k } => lemma_assert_safe(s, k, t),
        EL1::Retract { k } => lemma_retract_safe(s, k, t),
        EL1::TWrite { k, ts, ok } => lemma_twrite_safe(s, k, ts, ok, t),
        EL1::TDelete { k, ts } => lemma_keep_safe(s, t),
        EL1::PurgeBefore { g, end } => lemma_keep_safe(s, t),
        EL1::Purge => lemma_keep_safe(s, t),
        EL1::EraseNodes { g, sel } => lemma_erase_safe(s, g, sel, t),
    }
}

impl SafeContract for EdgeL1 {
    open spec fn inv(s: ES1) -> bool { inv1(s) }
    proof fn init_safe(s: ES1) {}
    proof fn step_safe(s: ES1, l: EL1, t: ES1) { lemma_l1_safe(s, l, t); }
}

// ------------------------------------------------------------------------------------------------ business theorems

/// ADR-0009 (and HD-0302's working answer): every temporal edge of a structural predicate has its structural edge, so
/// adjacency readers (MATCH, BFS, centrality) see every edge the temporal index holds.
pub proof fn theorem_temporal_implies_structural(s: ES1, e: Ev)
    requires inv1(s), s.tev.contains(e), structural(s.reg, e.k),
    ensures s.edges.contains_key(e.k),
{
}

/// ADR-0009 amendment, TMP-B9.13, ADR-0015: a derived edge exists only while its triple has a timestamp, and only for
/// a structural predicate (F-0507's surviving marked rows are excluded).
pub proof fn theorem_derived_edge_needs_time(s: ES1, k: K)
    requires inv1(s), s.edges.contains_key(k), s.edges[k] is Derived,
    ensures has_ts(s.tev, k), structural(s.reg, k),
{
}

/// ADR-0009 / HD-0302: no temporal write, delete or purge removes or changes an explicit edge (F-0304, F-0505).
pub proof fn theorem_temporal_side_keeps_explicit_edges(s: ES1, l: EL1, t: ES1, x: K)
    requires EdgeL1::next(s, l, t), explicit(s, x),
             l is TWrite || l is TDelete || l is PurgeBefore || l is Purge,
    ensures explicit(t, x),
{
    match l {
        EL1::TDelete { k, ts } => { assert(s.edges.dom().filter(|k: K| !(s.edges[k] is Derived && !has_ts(t.tev, k))).contains(x)); }
        EL1::PurgeBefore { g, end } => { assert(s.edges.dom().filter(|k: K| !(s.edges[k] is Derived && !has_ts(t.tev, k))).contains(x)); }
        EL1::Purge => { assert(s.edges.dom().filter(|k: K| !(s.edges[k] is Derived && !has_ts(t.tev, k))).contains(x)); }
        _ => {}
    }
}

/// create_edge docstring, ADR-0009, F-0304, F-C0301: an explicit write leaves the edge explicit; create_edge answers
/// True exactly when the edge was not explicit before (new, or a derived edge adopted).
pub proof fn theorem_explicit_write_owns_its_edge(s: ES1, l: EL1, t: ES1, x: K)
    requires EdgeL1::next(s, l, t), l == (EL1::Store { k: x }) || l == (EL1::Create { k: x, ans: true }) || l == (EL1::Create { k: x, ans: false }),
    ensures explicit(t, x), l == (EL1::Create { k: x, ans: true }) ==> !explicit(s, x),
            l == (EL1::Create { k: x, ans: false }) ==> explicit(s, x),
{
}

/// F-C0501: a temporal write IRIS refuses writes nothing.
pub proof fn theorem_refused_temporal_write_writes_nothing(s: ES1, k: K, ts: int, t: ES1)
    requires EdgeL1::next(s, EL1::TWrite { k, ts, ok: false }, t),
    ensures t == s,
{
}

/// HD-0302 working answer: a direct delete keeps the edge (derived) while its triple has a timestamp of a structural
/// predicate, and removes it otherwise.
pub proof fn theorem_direct_delete_keeps_supported_edge(s: ES1, k: K, t: ES1)
    requires EdgeL1::next(s, EL1::Retract { k }, t),
    ensures supported(s, k) ==> t.edges.contains_key(k) && t.edges[k] is Derived,
            !supported(s, k) ==> !t.edges.contains_key(k),
{
}

/// ADR-0015: a temporal write of a temporal-only predicate writes no structural edge and no node.
pub proof fn theorem_temporal_only_writes_nothing_structural(s: ES1, k: K, ts: int, ok: bool, t: ES1)
    requires EdgeL1::next(s, EL1::TWrite { k, ts, ok }, t), !structural(s.reg, k),
    ensures t.edges == s.edges, t.nodes == s.nodes,
{
}

/// F-C1203 (ADR-0015:59-60; delete_nodes_by_prefix docstring): after a prefix erase no node, structural edge or temporal
/// edge of the graph touches an id of the prefix.
pub proof fn theorem_prefix_erase_leaves_nothing_of_the_prefix(s: ES1, g: int, sel: Set<int>, t: ES1, n: int)
    requires EdgeL1::next(s, EL1::EraseNodes { g, sel }, t), sel.contains(n),
    ensures !t.nodes.contains(NK { g, n }),
            forall|k: K| #[trigger] t.edges.contains_key(k) ==> !(k.g == g && (k.s == n || k.o == n)),
            forall|e: Ev| #[trigger] t.tev.contains(e) ==> !(e.k.g == g && (e.k.s == n || e.k.o == n)),
{
    assert forall|k: K| #[trigger] t.edges.contains_key(k) implies !(k.g == g && (k.s == n || k.o == n)) by {
        assert(s.edges.dom().filter(|k: K| !hit(g, sel, k)).contains(k));
    }
}

} // verus!
