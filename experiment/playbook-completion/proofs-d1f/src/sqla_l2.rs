//! Module 17, L2: IRISGraphStore at pin 3eaa79cf over Graph_KG.nodes and Graph_KG.rdf_labels (s, label, graph_id);
//! refinement of `sqla_l1` for every step, the invariant, and the controls HD-1701 (two) and F-1701.
//!
//! **Reviewed design**:
//! - R17-3 (HD-1701 working answer (a)): execute_sql refuses a non-SELECT statement before it runs when read_only is
//!   true. As built nothing reads the flag (iris_sql_store.py:1522-1531): control `control_hd1701_read_only_ignored`
//!   (live: ib-HD1701-readonly-flag, an INSERT into Graph_KG.nodes and a CREATE TABLE ran under read_only=True).
//! - R17-4: a statement that ran and returned no result set is answered without an error. As built `fetchall()` on it
//!   raises "<USAGE ERROR> ... did not return a result set" and the answer carries that error (iris_sql_store.py:1531,
//!   1537-1553): control `control_hd1701_write_reported_failed` (the same live probe; filed by no finding: the intent
//!   record HD-1701 names it a candidate S3).
//! - R17-5 (F-1701 remedy; OPS-B5.3): a read that names no graph answers each graph's node apart (its rows carry
//!   graph_id). As built get_nodes with graph=None selects (s, label) over every graph and folds the labels by id
//!   (iris_sql_store.py:1116-1150); the row for id n names no graph, so it is a claim about every node of id n (premise
//!   P-Q1): control F-1701 (live: c17-live-engine).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::sqla_l1::*;

verus! {

pub struct Q2 { pub nodes: Set<NK>, pub labels: Set<LK>, pub writes: nat }

pub enum QL2 {
    AddNode { k: NK },
    AddLabel { lk: LK },
    Exec { write: bool, ro: bool, ok: bool },
    GetNodes { ids: Set<int>, graph: Option<int>, ans: Set<LK> },
}

pub open spec fn hd1701_ro() -> bool { cfg!(feature = "control_hd1701_read_only_ignored") }
pub open spec fn hd1701_err() -> bool { cfg!(feature = "control_hd1701_write_reported_failed") }
pub open spec fn f1701() -> bool { cfg!(feature = "control_f1701_unscoped_merge") }

/// The statement reaches cursor.execute.
pub open spec fn runs(write: bool, ro: bool) -> bool { !(write && ro) || hd1701_ro() }

/// The rows of `SELECT s, label FROM rdf_labels WHERE s IN (...){scope}`, with the reviewed graph_id column.
pub open spec fn scoped(s: Q2, ids: Set<int>, graph: Option<int>, lk: LK) -> bool {
    s.labels.contains(lk) && ids.contains(lk.n) && (graph is Some ==> lk.g == graph->Some_0)
}

/// As built with graph None: the labels of id n from any graph, answered in one row for n, read as every node of id n.
pub open spec fn folded(s: Q2, ids: Set<int>, lk: LK) -> bool {
    s.nodes.contains(NK { g: lk.g, n: lk.n }) && ids.contains(lk.n)
        && exists|g2: int| #[trigger] s.labels.contains(LK { g: g2, n: lk.n, l: lk.l })
}

pub open spec fn answered(s: Q2, ids: Set<int>, graph: Option<int>, lk: LK) -> bool {
    if graph is None && f1701() { folded(s, ids, lk) } else { scoped(s, ids, graph, lk) }
}

/// `ans` holds exactly the label facts the adapter answers.
pub open spec fn answers2(ans: Set<LK>, s: Q2, ids: Set<int>, graph: Option<int>) -> bool {
    forall|lk: LK| #![trigger ans.contains(lk)] ans.contains(lk) == answered(s, ids, graph, lk)
}

pub open spec fn init2(s: Q2) -> bool { s.nodes == Set::<NK>::empty() && s.labels == Set::<LK>::empty() && s.writes == 0 }

pub open spec fn step2(s: Q2, l: QL2, t: Q2) -> bool {
    match l {
        QL2::AddNode { k } => t == Q2 { nodes: s.nodes.insert(k), ..s },
        QL2::AddLabel { lk } => s.nodes.contains(NK { g: lk.g, n: lk.n }) && t == Q2 { labels: s.labels.insert(lk), ..s },
        QL2::Exec { write, ro, ok } =>
            if runs(write, ro) {
                ok == !(write && hd1701_err()) && t == (if write { Q2 { writes: s.writes + 1, ..s } } else { s })
            } else {
                !ok && t == s
            },
        QL2::GetNodes { ids, graph, ans } => answers2(ans, s, ids, graph) && t == s,
    }
}

pub open spec fn absq(s: Q2) -> Q1 { Q1 { nodes: s.nodes, labels: s.labels, writes: s.writes } }

pub open spec fn labq(l: QL2) -> Option<QL1> {
    match l {
        QL2::AddNode { k } => Some(QL1::AddNode { k }),
        QL2::AddLabel { lk } => Some(QL1::AddLabel { lk }),
        QL2::Exec { write, ro, ok } => Some(QL1::Exec { write, ro, ok }),
        QL2::GetNodes { ids, graph, ans } => Some(QL1::GetNodes { ids, graph, ans }),
    }
}

pub open spec fn inv17q(s: Q2) -> bool { inv1(absq(s)) }

pub struct SqlaL2;

impl Contract for SqlaL2 {
    type S = Q2;
    type L = QL2;
    open spec fn init(s: Q2) -> bool { init2(s) }
    open spec fn next(s: Q2, l: QL2, t: Q2) -> bool { inv17q(s) && step2(s, l, t) }
}

pub struct SqlaRaw;

impl Contract for SqlaRaw {
    type S = Q2;
    type L = QL2;
    open spec fn init(s: Q2) -> bool { init2(s) }
    open spec fn next(s: Q2, l: QL2, t: Q2) -> bool { step2(s, l, t) }
}

proof fn lemma_exec(s: Q2, write: bool, ro: bool, ok: bool, t: Q2)
    requires inv17q(s), step2(s, QL2::Exec { write, ro, ok }, t),
    ensures inv17q(t), SqlaL1::next(absq(s), QL1::Exec { write, ro, ok }, absq(t)),
{
    // R17-3: a read-only pass-through of a non-SELECT statement runs nothing (control HD-1701 read_only fails here)
    assert(write && ro ==> t == s);
    // R17-4: an answer that carries an error ran nothing (control HD-1701 misreported write fails here)
    assert(!ok ==> t == s);
    assert(t.labels == s.labels && t.nodes == s.nodes);
    assert forall|lk: LK| #[trigger] absq(t).labels.contains(lk) implies absq(t).nodes.contains(NK { g: lk.g, n: lk.n }) by {
        assert(absq(s).labels.contains(lk));
    }
}

proof fn lemma_getnodes(s: Q2, ids: Set<int>, graph: Option<int>, ans: Set<LK>, t: Q2)
    requires inv17q(s), step2(s, QL2::GetNodes { ids, graph, ans }, t),
    ensures inv17q(t), SqlaL1::next(absq(s), QL1::GetNodes { ids, graph, ans }, absq(t)),
{
    // R17-5: a read that names no graph answers each node's own labels (control F-1701 fails here)
    assert(forall|lk: LK| #[trigger] answered(s, ids, graph, lk) == own(absq(s), ids, graph, lk));
    assert forall|lk: LK| #![trigger ans.contains(lk)] ans.contains(lk) == own(absq(s), ids, graph, lk) by {
        assert(ans.contains(lk) == answered(s, ids, graph, lk));
        assert(answered(s, ids, graph, lk) == own(absq(s), ids, graph, lk));
    }
    assert forall|lk: LK| #[trigger] absq(t).labels.contains(lk) implies absq(t).nodes.contains(NK { g: lk.g, n: lk.n }) by {
        assert(absq(s).labels.contains(lk));
    }
}

pub proof fn lemma_step(s: Q2, l: QL2, t: Q2)
    requires inv17q(s), step2(s, l, t),
    ensures inv17q(t), step_or_stutter::<SqlaL1>(absq(s), labq(l), absq(t)),
{
    match l {
        QL2::Exec { write, ro, ok } => lemma_exec(s, write, ro, ok, t),
        QL2::GetNodes { ids, graph, ans } => lemma_getnodes(s, ids, graph, ans, t),
        QL2::AddNode { k } => { SqlaL1::step_safe(absq(s), QL1::AddNode { k }, absq(t)); }
        QL2::AddLabel { lk } => { SqlaL1::step_safe(absq(s), QL1::AddLabel { lk }, absq(t)); }
    }
}

impl Refines<SqlaL1> for SqlaL2 {
    open spec fn abs(s: Q2) -> Q1 { absq(s) }
    open spec fn lab(l: QL2) -> Option<QL1> { labq(l) }
    proof fn init_refines(s: Q2) {}
    proof fn step_refines(s: Q2, l: QL2, t: Q2) { lemma_step(s, l, t); }
}

impl SafeContract for SqlaL2 {
    open spec fn inv(s: Q2) -> bool { inv17q(s) }
    proof fn init_safe(s: Q2) {}
    proof fn step_safe(s: Q2, l: QL2, t: Q2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<Q2>, labels: Seq<QL2>, k: int)
    requires execution::<SqlaRaw>(states, labels), 0 <= k < states.len(),
    ensures inv17q(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution: read-only calls write nothing, error answers ran nothing, node reads keep graphs apart.
pub proof fn theorem_raw_executions_refine(states: Seq<Q2>, labels: Seq<QL2>)
    requires execution::<SqlaRaw>(states, labels),
    ensures
        execution::<SqlaL2>(states, labels),
        abstract_execution::<SqlaL1>(Seq::new(states.len(), |i: int| absq(states[i])),
                                     Seq::new(labels.len(), |i: int| labq(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv17q(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv17q(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<SqlaL2>(states, labels));
    trace_refines::<SqlaL2, SqlaL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absq(states[i])) =~= Seq::new(states.len(), |i: int| <SqlaL2 as Refines<SqlaL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labq(labels[i])) =~= Seq::new(labels.len(), |i: int| <SqlaL2 as Refines<SqlaL1>>::lab(labels[i])));
}

} // verus!
