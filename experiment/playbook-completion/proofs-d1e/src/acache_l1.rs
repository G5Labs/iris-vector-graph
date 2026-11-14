//! Module 10 (algorithms), L1 part 1: cached answers of graph-wide algorithms, PageRank's completeness and a read's
//! footprint, as a business contract.
//!
//! **Result-contract abstraction (not the numerics).** An answer is modelled by the rows it lists and the edges its
//! scores are computed over (`Ans { rows, over }`): the scores themselves are a deterministic function of the graph and
//! the parameters (networkx's pagerank, iris_vector_graph/stores/iris_sql_store.py:2243-2246; algorithms.py:741-760)
//! and are not modelled. Personalized PageRank from a seed lists every node of the graph when the seed is a node (an
//! edgeless seed scores 1.0, live b-10-live-cache) and none otherwise; global PageRank lists every node of the
//! default graph (its docstring, _engine/algorithms.py:741-760; HD-1004 working answer: every node on every route).
//!
//! State: the default graph's nodes and edges (one graph: the cache key holds the graph key, AlgoCache.cls:1-13, so
//! graphs do not share entries), the namespace's SQL function classes `dict` and the routine record `rrec`
//! (^IVG.Deploy("routines"), iris_vector_graph/routine_record.py:1-21). Business rules:
//!
//! - **an answer equals a fresh computation on the current graph**, cached or not (ALG-I4, ALG-B2.19, ALG-B16.11);
//! - **global PageRank lists every node of the default graph and no other** (HD-1004; ALG-B1.11);
//! - **a read changes no content**: it may write only its own work areas and caches, which are not content (ALG-I6,
//!   docs/ADMIN_GUIDE.md:521-525); only setup creates SQL functions and writes the routine record.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct Ed { pub a: int, pub b: int }
pub struct Ans { pub rows: Set<int>, pub over: Set<Ed> }
pub enum Q { Ppr { seed: int }, PageRank }

pub struct AS1 { pub nodes: Set<int>, pub edges: Set<Ed>, pub dict: Set<int>, pub rrec: Set<int> }

pub enum AL1 {
    CreateNode { n: int },
    DeleteNode { n: int },
    AddEdge { a: int, b: int },
    DelEdge { a: int, b: int },
    Read { q: Q, ans: Ans },
    Triangles,
    Install { names: Set<int> },
}

pub open spec fn fresh(s: AS1, q: Q) -> Ans {
    match q {
        Q::Ppr { seed } => Ans { rows: if s.nodes.contains(seed) { s.nodes } else { Set::empty() }, over: s.edges },
        Q::PageRank => Ans { rows: s.nodes, over: s.edges },
    }
}

pub open spec fn next1(s: AS1, l: AL1, t: AS1) -> bool {
    match l {
        AL1::CreateNode { n } => !s.nodes.contains(n) && t == (AS1 { nodes: s.nodes.insert(n), ..s }),
        AL1::DeleteNode { n } => s.nodes.contains(n)
            && t == (AS1 { nodes: s.nodes.remove(n), edges: s.edges.filter(|e: Ed| e.a != n && e.b != n), ..s }),
        AL1::AddEdge { a, b } => s.nodes.contains(a) && s.nodes.contains(b)
            && t == (AS1 { edges: s.edges.insert(Ed { a, b }), ..s }),
        AL1::DelEdge { a, b } => s.edges.contains(Ed { a, b }) && t == (AS1 { edges: s.edges.remove(Ed { a, b }), ..s }),
        AL1::Read { q, ans } => ans == fresh(s, q) && t == s,
        AL1::Triangles => t == s,
        AL1::Install { names } => t == (AS1 { dict: s.dict.union(names), rrec: s.rrec.union(names), ..s }),
    }
}

pub struct CacheL1;

impl Contract for CacheL1 {
    type S = AS1;
    type L = AL1;
    open spec fn init(s: AS1) -> bool { forall|e: Ed| #[trigger] s.edges.contains(e) ==> s.nodes.contains(e.a) && s.nodes.contains(e.b) }
    open spec fn next(s: AS1, l: AL1, t: AS1) -> bool { next1(s, l, t) }
}

/// Every edge joins two nodes of the graph.
pub open spec fn inv1(s: AS1) -> bool {
    forall|e: Ed| #[trigger] s.edges.contains(e) ==> s.nodes.contains(e.a) && s.nodes.contains(e.b)
}

pub proof fn lemma_l1_safe(s: AS1, l: AL1, t: AS1)
    requires inv1(s), next1(s, l, t),
    ensures inv1(t),
{
    match l {
        AL1::DeleteNode { n } => {
            assert forall|e: Ed| #[trigger] t.edges.contains(e) implies t.nodes.contains(e.a) && t.nodes.contains(e.b) by {
                assert(s.edges.contains(e));
            }
        }
        AL1::DelEdge { a, b } => {
            assert forall|e: Ed| #[trigger] t.edges.contains(e) implies t.nodes.contains(e.a) && t.nodes.contains(e.b) by {
                assert(s.edges.contains(e));
            }
        }
        _ => {}
    }
}

impl SafeContract for CacheL1 {
    open spec fn inv(s: AS1) -> bool { inv1(s) }
    proof fn init_safe(s: AS1) {}
    proof fn step_safe(s: AS1, l: AL1, t: AS1) { lemma_l1_safe(s, l, t); }
}

/// ALG-I4 / ALG-B16.11: whatever answers a read, its answer is the fresh computation on the current graph.
pub proof fn theorem_answer_is_fresh(s: AS1, q: Q, ans: Ans, t: AS1)
    requires next1(s, AL1::Read { q, ans }, t),
    ensures ans == fresh(s, q), t == s,
{
}

/// ALG-B2.19: a start node written without an edge is in the next personalized PageRank answer.
pub proof fn theorem_edgeless_seed_is_answered(s: AS1, n: int, t: AS1, ans: Ans, u: AS1)
    requires next1(s, AL1::CreateNode { n }, t), next1(t, AL1::Read { q: Q::Ppr { seed: n }, ans }, u),
    ensures ans.rows.contains(n),
{
}

/// HD-1004: global PageRank lists every node of the default graph, and only those.
pub proof fn theorem_pagerank_lists_every_node(s: AS1, ans: Ans, t: AS1)
    requires next1(s, AL1::Read { q: Q::PageRank, ans }, t),
    ensures forall|n: int| ans.rows.contains(n) <==> s.nodes.contains(n),
{
}

/// ALG-I6: a read changes no content (nodes, edges, SQL functions, the routine record).
pub proof fn theorem_reads_change_no_content(s: AS1, l: AL1, t: AS1)
    requires next1(s, l, t), l is Read || l is Triangles,
    ensures t == s,
{
}

} // verus!
