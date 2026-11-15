//! Module 02, L2 part 1: graph names on the writers and the graph-scoped readers over the SQL tables at pin 3eaa79cf;
//! refinement of `gid_l1` for every step, the invariant, and controls F-0202, F-0206 and F-0106.
//!
//! Layout: Graph_KG.nodes (graph_id, node_id), rdf_labels (s, label, graph_id), rdf_props (s, key, val, graph_id),
//! the graph_id column holding the name as given ('' the default graph, '0' the reserved name). Steps, each one
//! atomic (a reader's statements see one state):
//!
//! - `CreateNode` create_node (_engine/nodes_edges.py:968-1105): the node, label and property rows in one
//!   transaction, guarded by NOT EXISTS on (graph_id, node_id); `ok` false when the node is there or IRIS refuses.
//!   Reviewed: validate_graph_name refuses an invalid name first (F-0202 remedy, as count_nodes, erase_graph,
//!   delete_nodes_by_prefix and bulk_create_nodes do: nodes_edges.py:747, 1514, 1559, 1698). As built, create_node and store_node call no name check.
//! - `EraseGraph` erase_graph: validates the name (GraphKey.ForName), then removes every row of the graph.
//! - `NodesByLabel` get_nodes_by_label = get_node_ids_by_label (`SELECT s FROM rdf_labels WHERE label = ?`, every
//!   graph, nodes_edges.py:760-777) then get_nodes(ids) (graph_id = '' for each id's labels and properties; an id
//!   with neither is kept only when its default-graph node row exists, nodes_edges.py:621-695). Reviewed: the ids come
//!   from the graph read (graph_id = ''), so each id is hydrated from its own graph (HD-0201).
//! - `IdsByLabel` get_node_ids_by_label: every graph (documented; HD-0201 keeps it as a discovery helper).
//! - `PropertyKeys` get_property_keys(label) (_engine/schema.py:500-515): `rdf_props rp JOIN rdf_labels rl ON
//!   rl.s = rp.s WHERE rl.label = ?`. Reviewed: the join is on (graph_id, s) (F-0106 remedy).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::gid_l1::*;

verus! {

pub struct GS2 { pub nodes_t: Set<NK>, pub labels_t: Set<LK>, pub props_t: Set<PK> }

pub enum GL2 {
    CreateNode { g: int, n: int, l: int, k: int, ok: bool },
    EraseGraph { g: int },
    NodesByLabel { l: int, ans: Map<int, Hyd> },
    IdsByLabel { l: int, ids: Set<int> },
    PropertyKeys { l: int, keys: Set<int> },
}

pub open spec fn f0202() -> bool { cfg!(feature = "control_f0202_writer_skips_name_check") }
pub open spec fn f0206() -> bool { cfg!(feature = "control_f0206_hydrate_from_default") }
pub open spec fn f0106() -> bool { cfg!(feature = "control_f0106_keys_join_on_id") }

/// The name check the writer runs: none as built (F-0202).
pub open spec fn accepts(g: int) -> bool { if f0202() { true } else { valid(g) } }

pub open spec fn add2(s: GS2, g: int, n: int, l: int, k: int) -> GS2 {
    GS2 { nodes_t: s.nodes_t.insert(NK { g, n }), labels_t: s.labels_t.insert(LK { g, n, l }), props_t: s.props_t.insert(PK { g, n, k }) }
}
pub open spec fn erase2(s: GS2, g: int) -> GS2 {
    GS2 { nodes_t: s.nodes_t.filter(|x: NK| x.g != g), labels_t: s.labels_t.filter(|x: LK| x.g != g),
          props_t: s.props_t.filter(|x: PK| x.g != g) }
}

/// The ids get_nodes_by_label hydrates: every graph's as built, the default graph's reviewed.
pub open spec fn ids_of(s: GS2, l: int, n: int) -> bool {
    if f0206() { exists|g: int| s.labels_t.contains(LK { g, n, l }) } else { s.labels_t.contains(LK { g: 0, n, l }) }
}
/// get_nodes keeps an id with a default-graph label or property, or with no data and a default-graph node row.
pub open spec fn kept(s: GS2, n: int) -> bool {
    (exists|x: int| s.labels_t.contains(LK { g: 0, n, l: x })) || (exists|k: int| s.props_t.contains(PK { g: 0, n, k }))
        || s.nodes_t.contains(NK { g: 0, n })
}
pub open spec fn hyd2(s: GS2, n: int, h: Hyd) -> bool {
    (forall|x: int| #[trigger] h.labels.contains(x) <==> s.labels_t.contains(LK { g: 0, n, l: x }))
    && (forall|k: int| #[trigger] h.props.contains(k) <==> s.props_t.contains(PK { g: 0, n, k }))
}
pub open spec fn bylabel2(s: GS2, l: int, ans: Map<int, Hyd>) -> bool {
    (forall|n: int| #[trigger] ans.contains_key(n) <==> ids_of(s, l, n) && kept(s, n))
    && (forall|n: int| ans.contains_key(n) ==> hyd2(s, n, #[trigger] ans[n]))
}
pub open spec fn ids2(s: GS2, l: int, ids: Set<int>) -> bool {
    forall|n: int| #[trigger] ids.contains(n) <==> (exists|g: int| s.labels_t.contains(LK { g, n, l }))
}
/// get_property_keys(label): the join on s alone as built, on (graph_id, s) reviewed.
pub open spec fn keys2(s: GS2, l: int, keys: Set<int>) -> bool {
    if f0106() {
        forall|k: int| #[trigger] keys.contains(k) <==> (exists|g1: int, g2: int, n: int|
            s.labels_t.contains(LK { g: g1, n, l }) && s.props_t.contains(PK { g: g2, n, k }))
    } else {
        forall|k: int| #[trigger] keys.contains(k) <==> (exists|g: int, n: int| s.labels_t.contains(LK { g, n, l }) && s.props_t.contains(PK { g, n, k }))
    }
}

pub open spec fn step2(s: GS2, l: GL2, t: GS2) -> bool {
    match l {
        GL2::CreateNode { g, n, l, k, ok } =>
            if ok { accepts(g) && !s.nodes_t.contains(NK { g, n }) && t == add2(s, g, n, l, k) } else { t == s },
        GL2::EraseGraph { g } => valid(g) && t == erase2(s, g),
        GL2::NodesByLabel { l, ans } => bylabel2(s, l, ans) && t == s,
        GL2::IdsByLabel { l, ids } => ids2(s, l, ids) && t == s,
        GL2::PropertyKeys { l, keys } => keys2(s, l, keys) && t == s,
    }
}

pub open spec fn init2(s: GS2) -> bool {
    s.nodes_t == Set::<NK>::empty() && s.labels_t == Set::<LK>::empty() && s.props_t == Set::<PK>::empty()
}

pub open spec fn absg(s: GS2) -> GS1 { GS1 { nodes: s.nodes_t, labels: s.labels_t, props: s.props_t } }

pub open spec fn labg(l: GL2) -> Option<GL1> {
    match l {
        GL2::CreateNode { g, n, l, k, ok } => Some(GL1::CreateNode { g, n, l, k, ok }),
        GL2::EraseGraph { g } => Some(GL1::EraseGraph { g }),
        GL2::NodesByLabel { l, ans } => Some(GL1::NodesByLabel { l, ans }),
        GL2::IdsByLabel { l, ids } => Some(GL1::IdsByLabel { l, ids }),
        GL2::PropertyKeys { l, keys } => Some(GL1::PropertyKeys { l, keys }),
    }
}

/// L1's invariant on the tables (`lemma_inv02_is_inv1`): every graph_id holding a row is a valid name; label and
/// property rows have their node row.
pub open spec fn inv02(s: GS2) -> bool {
    &&& forall|x: NK| #[trigger] s.nodes_t.contains(x) ==> valid(x.g)
    &&& forall|x: LK| #[trigger] s.labels_t.contains(x) ==> s.nodes_t.contains(NK { g: x.g, n: x.n })
    &&& forall|x: PK| #[trigger] s.props_t.contains(x) ==> s.nodes_t.contains(NK { g: x.g, n: x.n })
}

pub proof fn lemma_inv02_is_inv1(s: GS2)
    ensures inv02(s) == inv1(absg(s)),
{
    let a = absg(s);
    assert(a.nodes == s.nodes_t && a.labels == s.labels_t && a.props == s.props_t);
}

pub struct GidL2;

impl Contract for GidL2 {
    type S = GS2;
    type L = GL2;
    open spec fn init(s: GS2) -> bool { init2(s) }
    open spec fn next(s: GS2, l: GL2, t: GS2) -> bool { inv02(s) && step2(s, l, t) }
}

pub struct GidRaw;

impl Contract for GidRaw {
    type S = GS2;
    type L = GL2;
    open spec fn init(s: GS2) -> bool { init2(s) }
    open spec fn next(s: GS2, l: GL2, t: GS2) -> bool { step2(s, l, t) }
}

proof fn lemma_createnode(s: GS2, g: int, n: int, l: int, k: int, ok: bool, t: GS2)
    requires inv02(s), step2(s, GL2::CreateNode { g, n, l, k, ok }, t),
    ensures inv02(t), step_or_stutter::<GidL1>(absg(s), labg(GL2::CreateNode { g, n, l, k, ok }), absg(t)),
{
    // a writer that takes a graph name writes only under a valid name (control F-0202 fails here)
    assert(ok ==> valid(g));
    if ok {
        assert(absg(t) == add1(absg(s), g, n, l, k));
        assert forall|x: LK| #[trigger] t.labels_t.contains(x) implies t.nodes_t.contains(NK { g: x.g, n: x.n }) by {
            if x != (LK { g, n, l }) { assert(s.labels_t.contains(x)); }
        }
        assert forall|x: PK| #[trigger] t.props_t.contains(x) implies t.nodes_t.contains(NK { g: x.g, n: x.n }) by {
            if x != (PK { g, n, k }) { assert(s.props_t.contains(x)); }
        }
    }
}

proof fn lemma_bylabel(s: GS2, l: int, ans: Map<int, Hyd>, t: GS2)
    requires inv02(s), step2(s, GL2::NodesByLabel { l, ans }, t),
    ensures inv02(t), step_or_stutter::<GidL1>(absg(s), labg(GL2::NodesByLabel { l, ans }), absg(t)),
{
    // the reader answers the default graph's nodes holding the label (control F-0206 fails here)
    assert forall|n: int| ans.contains_key(n) <==> s.labels_t.contains(LK { g: 0, n, l }) by {
        if s.labels_t.contains(LK { g: 0, n, l }) { assert(kept(s, n)); }
    }
    assert(forall|n: int| ans.contains_key(n) ==> hyd1(absg(s), n, #[trigger] ans[n]));
}

proof fn lemma_propkeys(s: GS2, l: int, keys: Set<int>, t: GS2)
    requires inv02(s), step2(s, GL2::PropertyKeys { l, keys }, t),
    ensures inv02(t), step_or_stutter::<GidL1>(absg(s), labg(GL2::PropertyKeys { l, keys }), absg(t)),
{
    // every key answered is held, in its own graph, by a node with the label (control F-0106 fails here)
    assert(keys1(absg(s), l, keys));
}

proof fn lemma_step(s: GS2, l: GL2, t: GS2)
    requires inv02(s), step2(s, l, t),
    ensures inv02(t), step_or_stutter::<GidL1>(absg(s), labg(l), absg(t)),
{
    match l {
        GL2::CreateNode { g, n, l, k, ok } => lemma_createnode(s, g, n, l, k, ok, t),
        GL2::NodesByLabel { l, ans } => lemma_bylabel(s, l, ans, t),
        GL2::PropertyKeys { l, keys } => lemma_propkeys(s, l, keys, t),
        GL2::EraseGraph { g } => {
            assert(absg(t) == erase1(absg(s), g));
            assert forall|x: LK| #[trigger] t.labels_t.contains(x) implies t.nodes_t.contains(NK { g: x.g, n: x.n }) by {
                assert(s.labels_t.contains(x));
            }
            assert forall|x: PK| #[trigger] t.props_t.contains(x) implies t.nodes_t.contains(NK { g: x.g, n: x.n }) by {
                assert(s.props_t.contains(x));
            }
        }
        GL2::IdsByLabel { l, ids } => {
            assert(absg(s).labels == s.labels_t);
            assert(ids1(absg(s), l, ids));
        }
    }
}

impl Refines<GidL1> for GidL2 {
    open spec fn abs(s: GS2) -> GS1 { absg(s) }
    open spec fn lab(l: GL2) -> Option<GL1> { labg(l) }
    proof fn init_refines(s: GS2) {}
    proof fn step_refines(s: GS2, l: GL2, t: GS2) { lemma_step(s, l, t); }
}

impl SafeContract for GidL2 {
    open spec fn inv(s: GS2) -> bool { inv02(s) }
    proof fn init_safe(s: GS2) {}
    proof fn step_safe(s: GS2, l: GL2, t: GS2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<GS2>, labels: Seq<GL2>, k: int)
    requires execution::<GidRaw>(states, labels), 0 <= k < states.len(),
    ensures inv02(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution.
pub proof fn theorem_raw_executions_refine(states: Seq<GS2>, labels: Seq<GL2>)
    requires execution::<GidRaw>(states, labels),
    ensures
        execution::<GidL2>(states, labels),
        abstract_execution::<GidL1>(Seq::new(states.len(), |i: int| absg(states[i])),
                                    Seq::new(labels.len(), |i: int| labg(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv02(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv02(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<GidL2>(states, labels));
    trace_refines::<GidL2, GidL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absg(states[i])) =~= Seq::new(states.len(), |i: int| <GidL2 as Refines<GidL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labg(labels[i])) =~= Seq::new(labels.len(), |i: int| <GidL2 as Refines<GidL1>>::lab(labels[i])));
}

/// On the tables: no row is stored under a name the index cannot key apart from the default graph.
pub proof fn theorem_no_row_under_reserved_name(s: GS2, x: NK)
    requires inv02(s), s.nodes_t.contains(x),
    ensures x.g != -1, ikey(x.g) == 0 ==> x.g == 0,
{
}

} // verus!
