//! Module 08, L2 part 2: the rows Graph_KG.nodes, rdf_labels and rdf_edges (graph_id columns) at pin 3eaa79cf and the
//! three read routes as the translator and engine compute them; refinement of `cys_l1`, and the controls F-0802,
//! F-0816 and F-0818.
//!
//! Routes: the count shortcut (query.py:1843-1856, matched on the text: `SELECT COUNT(*) FROM nodes` and `FROM
//! rdf_edges`, no graph predicate), db.labels (engine.py:1313-1318: `SELECT DISTINCT label FROM rdf_labels`, no graph
//! predicate), the variable-length walk (translator.py:15404-15431: `gall = 1` for a read with no USE GRAPH whose
//! source is not a correlated `n.node_id`, so CY_VLP_* walks every graph's relationships). **Reviewed design**
//! (remedies): the shortcut and the schema procedures honour USE GRAPH (F-0802, F-0816 remedies); the walk is scoped
//! to its source's graph (F-0818 remedy, FR-009). Writes are the stored rows' INSERTs (one step each).
//!
//! The L2 state is the stored rows themselves (the abstraction is the identity): what differs between designs is the
//! read routes, where the findings are. Premise P-S1: the route is chosen as modelled (the shortcut's text match, the
//! uncorrelated WITH-carried start).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::cys_l1::*;

verus! {

pub open spec fn f0802() -> bool { cfg!(feature = "control_f0802_shortcut_unscoped") }
pub open spec fn f0816() -> bool { cfg!(feature = "control_f0816_dblabels_unscoped") }
pub open spec fn f0818() -> bool { cfg!(feature = "control_f0818_vlp_crosses_graphs") }

pub open spec fn labels2(s: CS1, g: int) -> Set<(int, int, int)> { if f0816() { s.lab } else { labels_of(s, g) } }
pub open spec fn counts2(s: CS1, g: int) -> (Set<(int, int)>, Set<(int, int, int)>) { if f0802() { (s.nodes, s.edg) } else { counts_of(s, g) } }
/// CY_VLP_* with gall = 1: each hop reads any graph's relationship from the current node id.
pub open spec fn walk_all(s: CS1) -> ISet<(int, int, int)> {
    ISet::new(|x: (int, int, int)| s.nodes.contains((x.0, x.1))
        && ((exists|g1: int| #[trigger] s.edg.contains((g1, x.1, x.2)))
            || exists|y: int, g1: int, g2: int| #[trigger] s.edg.contains((g1, x.1, y)) && #[trigger] s.edg.contains((g2, y, x.2))))
}
pub open spec fn walk2(s: CS1) -> ISet<(int, int, int)> { if f0818() { walk_all(s) } else { walk_of(s) } }

pub open spec fn step2(s: CS1, l: CSL1, t: CS1) -> bool {
    match l {
        CSL1::Labels { g, ans } => t == s && ans == labels2(s, g),
        CSL1::Counts { g, ans } => t == s && ans == counts2(s, g),
        CSL1::Walk { ans } => t == s && ans == walk2(s),
        _ => CsL1::next(s, l, t),
    }
}

pub struct CsL2;
impl Contract for CsL2 {
    type S = CS1;
    type L = CSL1;
    open spec fn init(s: CS1) -> bool { CsL1::init(s) }
    open spec fn next(s: CS1, l: CSL1, t: CS1) -> bool { inv1(s) && step2(s, l, t) }
}
pub struct CsRaw;
impl Contract for CsRaw {
    type S = CS1;
    type L = CSL1;
    open spec fn init(s: CS1) -> bool { CsL1::init(s) }
    open spec fn next(s: CS1, l: CSL1, t: CS1) -> bool { step2(s, l, t) }
}

proof fn lemma_step(s: CS1, l: CSL1, t: CS1)
    requires inv1(s), step2(s, l, t),
    ensures inv1(t), step_or_stutter::<CsL1>(s, Some(l), t),
{
    match l {
        // db.labels() under USE GRAPH lists g's labels only (control F-0816 fails here)
        CSL1::Labels { g, ans } => { assert(labels2(s, g) == labels_of(s, g)); }
        // the count shortcut counts g's rows only (control F-0802 fails here)
        CSL1::Counts { g, ans } => { assert(counts2(s, g) == counts_of(s, g)); }
        // the walk stays in its source's graph (control F-0818 fails here)
        CSL1::Walk { ans } => { assert(walk2(s) == walk_of(s)); }
        _ => {}
    }
}

impl Refines<CsL1> for CsL2 {
    open spec fn abs(s: CS1) -> CS1 { s }
    open spec fn lab(l: CSL1) -> Option<CSL1> { Some(l) }
    proof fn init_refines(s: CS1) {}
    proof fn step_refines(s: CS1, l: CSL1, t: CS1) { lemma_step(s, l, t); }
}

impl SafeContract for CsL2 {
    open spec fn inv(s: CS1) -> bool { inv1(s) }
    proof fn init_safe(s: CS1) {}
    proof fn step_safe(s: CS1, l: CSL1, t: CS1) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<CS1>, labels: Seq<CSL1>, k: int)
    requires execution::<CsRaw>(states, labels), 0 <= k < states.len(),
    ensures inv1(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the invariant and is an L1 execution.
pub proof fn theorem_raw_executions_refine(states: Seq<CS1>, labels: Seq<CSL1>)
    requires execution::<CsRaw>(states, labels),
    ensures
        execution::<CsL2>(states, labels),
        abstract_execution::<CsL1>(states, Seq::new(labels.len(), |i: int| Some(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv1(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv1(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<CsL2>(states, labels));
    trace_refines::<CsL2, CsL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| <CsL2 as Refines<CsL1>>::abs(states[i])) =~= states);
    assert(Seq::new(labels.len(), |i: int| Some(labels[i])) =~= Seq::new(labels.len(), |i: int| <CsL2 as Refines<CsL1>>::lab(labels[i])));
}

} // verus!
