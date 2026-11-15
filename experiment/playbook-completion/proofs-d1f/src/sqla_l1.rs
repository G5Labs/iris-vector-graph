//! Module 17, L1: the SQL adapter's pass-through and node reads (IRISGraphStore, the GraphStore protocol).
//!
//! State: the nodes (`NK {g, n}`: id n in graph g; the same id in two graphs is two nodes, SYS-D6), their labels
//! (`LK {g, n, l}`), and the pass-through's other writes (`writes`, one counter for any non-SELECT statement).
//! Business rules:
//! - **a read-only pass-through writes nothing** (HD-1701 working answer (a): read_only=True is a requested guarantee;
//!   a non-SELECT statement is refused before it runs);
//! - **a reported failure means nothing ran** (SYS-I3 for the pass-through's answer; OPS-B5.9: a failure comes back in
//!   the result's error);
//! - **a node read keeps each graph's node apart** (OPS-B5.3; CONTEXT.md:38-43 "All-graphs read": the answer is the
//!   union of each graph's own answer, and a node's labels are its own graph's; SYS-I2). An answer is a set of label
//!   facts, each about one node of one graph.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct NK { pub g: int, pub n: int }
pub struct LK { pub g: int, pub n: int, pub l: int }

pub struct Q1 { pub nodes: Set<NK>, pub labels: Set<LK>, pub writes: nat }

pub enum QL1 {
    AddNode { k: NK },
    AddLabel { lk: LK },
    /// execute_sql(sql, params, read_only=ro); `write` a non-SELECT statement; `ok` the answer carries no error
    Exec { write: bool, ro: bool, ok: bool },
    /// get_nodes(ids, graph=graph) (and get_node_labels, which reads it with no graph); `ans` the label facts answered
    GetNodes { ids: Set<int>, graph: Option<int>, ans: Set<LK> },
}

/// The label facts a read of `ids` in `graph` (None: every graph) answers: each node's own labels.
pub open spec fn own(s: Q1, ids: Set<int>, graph: Option<int>, lk: LK) -> bool {
    s.labels.contains(lk) && ids.contains(lk.n) && (graph is Some ==> lk.g == graph->Some_0)
}

/// `ans` holds exactly the label facts `own` names.
pub open spec fn answers(ans: Set<LK>, s: Q1, ids: Set<int>, graph: Option<int>) -> bool {
    forall|lk: LK| #![trigger ans.contains(lk)] ans.contains(lk) == own(s, ids, graph, lk)
}

pub struct SqlaL1;

impl Contract for SqlaL1 {
    type S = Q1;
    type L = QL1;

    open spec fn init(s: Q1) -> bool { s.nodes == Set::<NK>::empty() && s.labels == Set::<LK>::empty() && s.writes == 0 }

    open spec fn next(s: Q1, l: QL1, t: Q1) -> bool {
        match l {
            QL1::AddNode { k } => t == Q1 { nodes: s.nodes.insert(k), ..s },
            QL1::AddLabel { lk } => s.nodes.contains(NK { g: lk.g, n: lk.n }) && t == Q1 { labels: s.labels.insert(lk), ..s },
            QL1::Exec { write, ro, ok } =>
                if write && ro { !ok && t == s } else if write { ok && t == Q1 { writes: s.writes + 1, ..s } } else { ok && t == s },
            QL1::GetNodes { ids, graph, ans } =>
                answers(ans, s, ids, graph) && t == s,
        }
    }
}

pub open spec fn inv1(s: Q1) -> bool { forall|lk: LK| #[trigger] s.labels.contains(lk) ==> s.nodes.contains(NK { g: lk.g, n: lk.n }) }

impl SafeContract for SqlaL1 {
    open spec fn inv(s: Q1) -> bool { inv1(s) }
    proof fn init_safe(s: Q1) {}
    proof fn step_safe(s: Q1, l: QL1, t: Q1) {
        match l {
            QL1::AddNode { k } => {
                assert forall|lk: LK| #[trigger] t.labels.contains(lk) implies t.nodes.contains(NK { g: lk.g, n: lk.n }) by {
                    assert(s.nodes.contains(NK { g: lk.g, n: lk.n }));
                }
            }
            QL1::AddLabel { lk } => {
                assert forall|x: LK| #[trigger] t.labels.contains(x) implies t.nodes.contains(NK { g: x.g, n: x.n }) by {
                    if x != lk { assert(s.labels.contains(x)); }
                }
            }
            _ => {}
        }
    }
}

/// HD-1701 (working answer (a)): execute_sql(read_only=True) of a non-SELECT statement is refused and writes nothing.
pub proof fn theorem_read_only_call_writes_nothing(s: Q1, ok: bool, t: Q1)
    requires SqlaL1::next(s, QL1::Exec { write: true, ro: true, ok }, t),
    ensures t == s, !ok,
{
}

/// OPS-B5.9 with SYS-I3: a pass-through answer that carries an error ran nothing.
pub proof fn theorem_failure_report_means_nothing_ran(s: Q1, write: bool, ro: bool, t: Q1)
    requires SqlaL1::next(s, QL1::Exec { write, ro, ok: false }, t),
    ensures t == s,
{
}

/// OPS-B5.3: every label fact a node read answers is a label of that node in its own graph, and a read naming a graph
/// answers only that graph's facts.
pub proof fn theorem_node_read_keeps_graphs_apart(s: Q1, ids: Set<int>, graph: Option<int>, ans: Set<LK>, lk: LK)
    requires SqlaL1::next(s, QL1::GetNodes { ids, graph, ans }, s), ans.contains(lk),
    ensures s.labels.contains(lk), graph is Some ==> lk.g == graph->Some_0,
{
    assert(own(s, ids, graph, lk));
}

} // verus!
