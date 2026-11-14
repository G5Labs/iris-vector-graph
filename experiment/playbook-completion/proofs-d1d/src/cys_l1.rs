//! Module 08, L1 part 2: graph scope of Cypher reads on the SQL path.
//!
//! Sources: CONTEXT.md:27-43 (every node, edge and label belongs to exactly one graph; graphs are isolation units);
//! docs/USER_GUIDE.md:401-404 (`USE GRAPH` scopes a query to one graph); SYS-I2 / CYP-I5.5 / CYP-I5.6 (an answer about
//! graph g holds only g's data); spec 253 FR-009 as cited at translator.py:15423-15424 (an all-graphs read walks each
//! source in its own graph and ends at that graph's nodes).
//!
//! Abstraction (explicit): the stored rows only: nodes (graph, id), labels (graph, node, label), relationships of one
//! type (graph, source, target); node ids are shared across graphs. Three reads: `Labels` (CALL db.labels() under USE
//! GRAPH g: the label rows behind the names it lists), `Counts` (`MATCH (n) RETURN count(*) AS c UNION ALL MATCH
//! ()-[r]->() RETURN count(*) AS c` under USE GRAPH g: the rows it counts), `Walk` (an all-graphs `MATCH (a) WITH a
//! MATCH (a)-[*1..2]->(b)`: (a's graph, a, b)). Counting and label names are functions of those rows.
//!
//! Business rule: **a read answers from its graph's rows only**, and **a walk stays in its source's graph**.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct CS1 { pub nodes: Set<(int, int)>, pub lab: Set<(int, int, int)>, pub edg: Set<(int, int, int)> }

pub enum CSL1 {
    WNode { g: int, n: int },
    WLab { g: int, n: int, l: int },
    WEdge { g: int, a: int, b: int },
    Labels { g: int, ans: Set<(int, int, int)> },
    Counts { g: int, ans: (Set<(int, int)>, Set<(int, int, int)>) },
    Walk { ans: ISet<(int, int, int)> },
}

pub open spec fn labels_of(s: CS1, g: int) -> Set<(int, int, int)> { s.lab.filter(|x: (int, int, int)| x.0 == g) }
pub open spec fn counts_of(s: CS1, g: int) -> (Set<(int, int)>, Set<(int, int, int)>) {
    (s.nodes.filter(|x: (int, int)| x.0 == g), s.edg.filter(|x: (int, int, int)| x.0 == g))
}
/// (g, a, b): a is a node of g and b is one or two of g's relationships from a.
pub open spec fn walk_of(s: CS1) -> ISet<(int, int, int)> {
    ISet::new(|x: (int, int, int)| s.nodes.contains((x.0, x.1))
        && (s.edg.contains(x) || exists|y: int| #[trigger] s.edg.contains((x.0, x.1, y)) && s.edg.contains((x.0, y, x.2))))
}

pub struct CsL1;

impl Contract for CsL1 {
    type S = CS1;
    type L = CSL1;

    open spec fn init(s: CS1) -> bool {
        s.nodes == Set::<(int, int)>::empty() && s.lab == Set::<(int, int, int)>::empty() && s.edg == Set::<(int, int, int)>::empty()
    }

    open spec fn next(s: CS1, l: CSL1, t: CS1) -> bool {
        match l {
            CSL1::WNode { g, n } => t == (CS1 { nodes: s.nodes.insert((g, n)), ..s }),
            CSL1::WLab { g, n, l } => s.nodes.contains((g, n)) && t == (CS1 { lab: s.lab.insert((g, n, l)), ..s }),
            CSL1::WEdge { g, a, b } => s.nodes.contains((g, a)) && s.nodes.contains((g, b)) && t == (CS1 { edg: s.edg.insert((g, a, b)), ..s }),
            CSL1::Labels { g, ans } => t == s && ans == labels_of(s, g),
            CSL1::Counts { g, ans } => t == s && ans == counts_of(s, g),
            CSL1::Walk { ans } => t == s && ans == walk_of(s),
        }
    }
}

/// Foreign keys: a label row and a relationship's endpoints are node rows of their graph (fk_labels, fk_edges_*).
pub open spec fn inv1(s: CS1) -> bool {
    &&& forall|x: (int, int, int)| #[trigger] s.lab.contains(x) ==> s.nodes.contains((x.0, x.1))
    &&& forall|x: (int, int, int)| #[trigger] s.edg.contains(x) ==> s.nodes.contains((x.0, x.1)) && s.nodes.contains((x.0, x.2))
}

impl SafeContract for CsL1 {
    open spec fn inv(s: CS1) -> bool { inv1(s) }
    proof fn init_safe(s: CS1) {}
    proof fn step_safe(s: CS1, l: CSL1, t: CS1) {}
}

/// SYS-I2: every row a scoped read answers from is its graph's.
pub proof fn theorem_scoped_reads_answer_their_graph(s: CS1, g: int, a: Set<(int, int, int)>, c: (Set<(int, int)>, Set<(int, int, int)>), t: CS1)
    requires CsL1::next(s, CSL1::Labels { g, ans: a }, t), CsL1::next(s, CSL1::Counts { g, ans: c }, t),
    ensures
        forall|x: (int, int, int)| #[trigger] a.contains(x) ==> x.0 == g,
        forall|x: (int, int)| #[trigger] c.0.contains(x) ==> x.0 == g,
        forall|x: (int, int, int)| #[trigger] c.1.contains(x) ==> x.0 == g,
{
}

/// FR-009: a walk's two hops are relationships of its source's graph.
pub proof fn theorem_walk_stays_in_its_graph(s: CS1, w: ISet<(int, int, int)>, t: CS1, x: (int, int, int))
    requires CsL1::next(s, CSL1::Walk { ans: w }, t), w.contains(x), !s.edg.contains(x),
    ensures exists|y: int| #[trigger] s.edg.contains((x.0, x.1, y)) && s.edg.contains((x.0, y, x.2)),
{
}

} // verus!
