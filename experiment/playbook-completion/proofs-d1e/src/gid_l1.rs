//! Module 02 (graph identity), L1 part 1: graph names and keys, and graph-scoped reads, as a business contract.
//!
//! A graph name is encoded as an int: 0 the default graph (''), -1 the name "0", below -1 a name with a control
//! character, 1.. other names. `valid(g)`: the names GraphKey.Validate accepts (iris_src/src/Graph/KG/GraphKey.cls:
//! 23-49). `ikey(g)`: the ^KG / ^NKG subscript ForIndex derives after IRIS canonicalizes the subscript "0" to the
//! integer 0 (GraphKey.cls:25-27, 50-56; ADR-0003 docs/adr/0003-two-graph-key-derivations.md:119-121).
//!
//! State: node rows `nodes` (graph, id), label rows `labels` (graph, id, label), property rows `props` (graph, id,
//! key) (the tables are keyed by graph, iris_vector_graph/schema.py:395-400 for the nodes). Business
//! rules:
//!
//! - **every graph that holds content has a valid name**, so the index keys of distinct graphs differ and the
//!   default graph alone has key 0 (ADR-0003; GID-I1), and every graph holding content can be erased by name;
//! - **a read with no graph argument reads the default graph and hydrates each id from it** (USER_GUIDE.md:
//!   462-467; HD-0201 working assumption: never join ids from one scope with records of another);
//! - **an all-graphs read is the union of each graph's own answer** (CONTEXT.md:38-43; SYS-I2): the all-graph id
//!   helper (documented "in all graphs", iris_vector_graph/_engine/nodes_edges.py:760-777) and get_property_keys
//!   (documented "Not graph-scoped", _engine/schema.py:500-504).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct NK { pub g: int, pub n: int }
pub struct LK { pub g: int, pub n: int, pub l: int }
pub struct PK { pub g: int, pub n: int, pub k: int }
/// A hydrated node: its labels and property keys.
pub struct Hyd { pub labels: Set<int>, pub props: Set<int> }

pub open spec fn valid(g: int) -> bool { g >= 0 }
pub open spec fn ikey(g: int) -> int { if g == -1 { 0 } else { g } }

pub struct GS1 { pub nodes: Set<NK>, pub labels: Set<LK>, pub props: Set<PK> }

pub enum GL1 {
    /// create_node / store_node with one label and one property key (`ok` false: refused or already there)
    CreateNode { g: int, n: int, l: int, k: int, ok: bool },
    EraseGraph { g: int },
    NodesByLabel { l: int, ans: Map<int, Hyd> },
    IdsByLabel { l: int, ids: Set<int> },
    PropertyKeys { l: int, keys: Set<int> },
}

pub open spec fn add1(s: GS1, g: int, n: int, l: int, k: int) -> GS1 {
    GS1 { nodes: s.nodes.insert(NK { g, n }), labels: s.labels.insert(LK { g, n, l }), props: s.props.insert(PK { g, n, k }) }
}
pub open spec fn erase1(s: GS1, g: int) -> GS1 {
    GS1 { nodes: s.nodes.filter(|x: NK| x.g != g), labels: s.labels.filter(|x: LK| x.g != g), props: s.props.filter(|x: PK| x.g != g) }
}
pub open spec fn hyd1(s: GS1, n: int, h: Hyd) -> bool {
    (forall|x: int| #[trigger] h.labels.contains(x) <==> s.labels.contains(LK { g: 0, n, l: x }))
    && (forall|k: int| #[trigger] h.props.contains(k) <==> s.props.contains(PK { g: 0, n, k }))
}
pub open spec fn bylabel1(s: GS1, l: int, ans: Map<int, Hyd>) -> bool {
    (forall|n: int| #[trigger] ans.contains_key(n) <==> s.labels.contains(LK { g: 0, n, l }))
    && (forall|n: int| ans.contains_key(n) ==> hyd1(s, n, #[trigger] ans[n]))
}
pub open spec fn ids1(s: GS1, l: int, ids: Set<int>) -> bool {
    forall|n: int| #[trigger] ids.contains(n) <==> (exists|g: int| s.labels.contains(LK { g, n, l }))
}
pub open spec fn keys1(s: GS1, l: int, keys: Set<int>) -> bool {
    forall|k: int| #[trigger] keys.contains(k) <==> (exists|g: int, n: int| s.labels.contains(LK { g, n, l }) && s.props.contains(PK { g, n, k }))
}

pub open spec fn next1(s: GS1, l: GL1, t: GS1) -> bool {
    match l {
        GL1::CreateNode { g, n, l, k, ok } =>
            if ok { valid(g) && !s.nodes.contains(NK { g, n }) && t == add1(s, g, n, l, k) } else { t == s },
        GL1::EraseGraph { g } => valid(g) && t == erase1(s, g),
        GL1::NodesByLabel { l, ans } => bylabel1(s, l, ans) && t == s,
        GL1::IdsByLabel { l, ids } => ids1(s, l, ids) && t == s,
        GL1::PropertyKeys { l, keys } => keys1(s, l, keys) && t == s,
    }
}

pub struct GidL1;

impl Contract for GidL1 {
    type S = GS1;
    type L = GL1;
    open spec fn init(s: GS1) -> bool {
        s.nodes == Set::<NK>::empty() && s.labels == Set::<LK>::empty() && s.props == Set::<PK>::empty()
    }
    open spec fn next(s: GS1, l: GL1, t: GS1) -> bool { next1(s, l, t) }
}

/// Every graph holding content has a valid name; label and property rows belong to node rows of their graph.
pub open spec fn inv1(s: GS1) -> bool {
    &&& forall|x: NK| #[trigger] s.nodes.contains(x) ==> valid(x.g)
    &&& forall|x: LK| #[trigger] s.labels.contains(x) ==> s.nodes.contains(NK { g: x.g, n: x.n })
    &&& forall|x: PK| #[trigger] s.props.contains(x) ==> s.nodes.contains(NK { g: x.g, n: x.n })
}

pub proof fn lemma_l1_safe(s: GS1, l: GL1, t: GS1)
    requires inv1(s), next1(s, l, t),
    ensures inv1(t),
{
    match l {
        GL1::EraseGraph { g } => {
            assert forall|x: LK| #[trigger] t.labels.contains(x) implies t.nodes.contains(NK { g: x.g, n: x.n }) by {
                assert(s.labels.contains(x));
            }
            assert forall|x: PK| #[trigger] t.props.contains(x) implies t.nodes.contains(NK { g: x.g, n: x.n }) by {
                assert(s.props.contains(x));
            }
        }
        _ => {}
    }
}

impl SafeContract for GidL1 {
    open spec fn inv(s: GS1) -> bool { inv1(s) }
    proof fn init_safe(s: GS1) {}
    proof fn step_safe(s: GS1, l: GL1, t: GS1) { lemma_l1_safe(s, l, t); }
}

/// ADR-0003: two graphs holding content have distinct index keys, and key 0 is the default graph's alone.
pub proof fn theorem_index_keys_distinct(s: GS1, a: NK, b: NK)
    requires inv1(s), s.nodes.contains(a), s.nodes.contains(b), a.g != b.g,
    ensures ikey(a.g) != ikey(b.g), ikey(a.g) == 0 ==> a.g == 0,
{
}

/// Every graph holding content can be erased by its name, and the erase leaves nothing of it.
pub proof fn theorem_every_graph_erasable(s: GS1, x: NK)
    requires inv1(s), s.nodes.contains(x),
    ensures next1(s, GL1::EraseGraph { g: x.g }, erase1(s, x.g)), !erase1(s, x.g).nodes.contains(x),
{
}

/// HD-0201 / USER_GUIDE.md:462-467: a default-graph read answers nodes holding the label in the default graph, each
/// with its own default-graph labels.
pub proof fn theorem_default_read_is_scoped(s: GS1, l: int, ans: Map<int, Hyd>, t: GS1, n: int)
    requires next1(s, GL1::NodesByLabel { l, ans }, t), ans.contains_key(n),
    ensures s.labels.contains(LK { g: 0, n, l }), ans[n].labels.contains(l),
{
}

/// CONTEXT.md:38-43 / SYS-I2: every key an all-graphs read answers for a label is held by a node with that label in
/// the node's own graph.
pub proof fn theorem_all_graph_read_is_union(s: GS1, l: int, keys: Set<int>, t: GS1, k: int)
    requires next1(s, GL1::PropertyKeys { l, keys }, t), keys.contains(k),
    ensures exists|g: int, n: int| s.labels.contains(LK { g, n, l }) && s.props.contains(PK { g, n, k }),
{
}

} // verus!
