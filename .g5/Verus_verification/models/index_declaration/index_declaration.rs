// IVG adjacency index declaration at setup: from catalog state to an ordered list of DDL actions.
// Verus model, consolidated uplift (2026-11-14). Product baseline 3eaa79cf. As-built transcription of
//   iris_vector_graph/schema.py  GraphSchema.ensure_adjacency_index :821-898 (prerequisites :831-860, per index
//   :863-897, temporal backfill before the edge index :879-884), GraphSchema.adjacency_index_kind :785-818,
//   GraphSchema.ADJACENCY_INDEXES :769-782 (edge index, then label index); called by ensure_indexes :600-731 (:726).
//
// Run:  $VERUS_BIN index_declaration.rs --crate-type=lib --num-threads 4 --triggers-mode silent
use vstd::prelude::*;

verus! {

pub enum Kind { Functional, Plain, Absent }

pub enum Idx { Edges, Labels }

pub struct Catalog {
    pub callbacks: bool,   // Graph.KG.AdjIndex and Graph.KG.LabelIndex compiled (COUNT = 2)
    pub procs: bool,       // the IVG Schema's SqlProcs class compiled
    pub ekey: bool,        // rdf_edges.ekey exists
    pub graph_cols: bool,  // graph_id on rdf_edges and rdf_labels
    pub edges: Kind,       // adjacency_index_kind(idx_edges_adj)
    pub labels: Kind,      // adjacency_index_kind(idx_labels_adj)
}

pub enum Act { Skip, Drop(Idx), Backfill, Create(Idx) }

pub open spec fn prereqs(c: Catalog) -> bool {
    c.callbacks && c.procs && c.ekey && c.graph_cols
}

/// The per-index part of the loop (:864-897).
pub open spec fn for_index(i: Idx, k: Kind) -> Seq<Act> {
    match k {
        Kind::Functional => Seq::empty(),
        _ => {
            let drop: Seq<Act> = if k is Plain { seq![Act::Drop(i)] } else { Seq::empty() };
            let fill: Seq<Act> = if i is Edges { seq![Act::Backfill] } else { Seq::empty() };
            drop + fill + seq![Act::Create(i)]
        },
    }
}

pub open spec fn plan(c: Catalog) -> Seq<Act> {
    if !prereqs(c) { seq![Act::Skip] } else { for_index(Idx::Edges, c.edges) + for_index(Idx::Labels, c.labels) }
}

pub open spec fn is_ddl(a: Act) -> bool {
    !(a is Skip)
}

/// After the actions: a created index is functional; nothing else changes.
pub open spec fn apply(c: Catalog) -> Catalog {
    if !prereqs(c) { c } else { Catalog { edges: Kind::Functional, labels: Kind::Functional, ..c } }
}

/// Nothing is declared, dropped or backfilled without every prerequisite. Stated over the four catalog facts, not
/// over `prereqs`, so a weakened `prereqs` cannot weaken the theorem (the first version did, and its control survived).
pub proof fn theorem_no_prereq_no_ddl(c: Catalog)
    requires !c.callbacks || !c.procs || !c.ekey || !c.graph_cols,
    ensures forall|j: int| 0 <= j < plan(c).len() ==> !is_ddl(#[trigger] plan(c)[j]),
{
}

/// With every prerequisite and neither index declared, both are declared, the edge index first, after the backfill.
pub proof fn theorem_prereqs_declare_both(c: Catalog)
    requires prereqs(c), c.edges is Absent, c.labels is Absent,
    ensures plan(c) == seq![Act::Backfill, Act::Create(Idx::Edges), Act::Create(Idx::Labels)],
{
    assert(plan(c) =~= seq![Act::Backfill, Act::Create(Idx::Edges), Act::Create(Idx::Labels)]);
}

/// An index already declared as the adjacency index is left alone (and the edge index's backfill is not run again).
pub proof fn theorem_declared_left_alone(c: Catalog)
    requires prereqs(c), c.edges is Functional,
    ensures
        forall|j: int| 0 <= j < plan(c).len() ==>
            !(#[trigger] plan(c)[j] == Act::Create(Idx::Edges)) && plan(c)[j] != Act::Drop(Idx::Edges) && plan(c)[j] != Act::Backfill,
{
    assert(plan(c) =~= for_index(Idx::Labels, c.labels));
}

/// Whenever the edge index is created, the temporal backfill comes earlier in the plan.
pub proof fn theorem_backfill_before_edge_index(c: Catalog, j: int)
    requires 0 <= j < plan(c).len(), plan(c)[j] == Act::Create(Idx::Edges),
    ensures exists|i: int| 0 <= i < j && #[trigger] plan(c)[i] == Act::Backfill,
{
    let e = for_index(Idx::Edges, c.edges);
    assert(prereqs(c));
    assert(!(c.edges is Functional)) by {
        if c.edges is Functional {
            assert(plan(c) =~= for_index(Idx::Labels, c.labels));
            assert(false);
        }
    }
    if j < e.len() {
        let d = if c.edges is Plain { 1int } else { 0int };
        assert(e.len() == d + 2);
        assert(plan(c)[d] == Act::Backfill);
        assert(j == d + 1);
    } else {
        let l = for_index(Idx::Labels, c.labels);
        assert(plan(c)[j] == l[j - e.len()]);
        assert(false);
    }
}

/// A plain index of the same name is dropped, then declared.
pub proof fn theorem_plain_replaced(c: Catalog)
    requires prereqs(c), c.edges is Plain, c.labels is Functional,
    ensures plan(c) == seq![Act::Drop(Idx::Edges), Act::Backfill, Act::Create(Idx::Edges)],
{
    assert(plan(c) =~= seq![Act::Drop(Idx::Edges), Act::Backfill, Act::Create(Idx::Edges)]);
}

/// Setup can run again: after one run both indexes are declared and a second run declares nothing.
pub proof fn theorem_second_run_is_noop(c: Catalog)
    requires prereqs(c),
    ensures plan(apply(c)) == Seq::<Act>::empty(),
{
    assert(plan(apply(c)) =~= Seq::<Act>::empty());
}

/// A namespace from before graph scoping: setup skips; once the upgrade adds the columns, setup declares both.
pub proof fn witness_skip_then_declare()
{
    let before = Catalog { callbacks: true, procs: true, ekey: true, graph_cols: false, edges: Kind::Absent, labels: Kind::Absent };
    let after = Catalog { graph_cols: true, ..before };
    assert(plan(before) == seq![Act::Skip]);
    theorem_prereqs_declare_both(after);
}

} // verus!
