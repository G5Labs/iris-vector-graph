// product 3eaa79cf: the data graph validate_shacl hands to pySHACL (iris_vector_graph/_engine/shacl.py,
//   _engine/_rdf_utils.py::_build_rdflib_graph) and the two Core checks W45 used (sh:minCount on a property path,
//   sh:class on an edge path). Rows are (graph, node id) facts; the data graph names a node by its IRI, minted from the
//   node ID alone, and with node_ids it holds only rows whose subject is listed.
//   Provider premises (observed with pySHACL 0.40.2, rdflib 7.6.0): validation of the ConjunctiveGraph sees the union of
//   its contexts; minCount counts values of the focus IRI; sh:class looks for an rdf:type triple of the value IRI.
use vstd::prelude::*;
verus! {

pub type G = int;   // graph
pub type N = int;   // node id (one IRI per id)

pub struct Rows {
    pub has_prop: spec_fn(G, N) -> bool,   // the node of that graph has the shape's property
    pub has_label: spec_fn(G, N) -> bool,  // the node of that graph has the target class label
    pub edge: spec_fn(G, N, N) -> bool,    // an edge of the shape's predicate in that graph
}

pub open spec fn prop(r: Rows, g: G, n: N) -> bool { (r.has_prop)(g, n) }
pub open spec fn lab(r: Rows, g: G, n: N) -> bool { (r.has_label)(g, n) }
pub open spec fn edg(r: Rows, g: G, n: N, m: N) -> bool { (r.edge)(g, n, m) }

/// Which rows the data graph holds: every row, or with node_ids only rows whose subject is listed.
pub open spec fn loaded(focus: Option<Set<N>>, n: N) -> bool { match focus { None => true, Some(s) => s.contains(n) } }

/// L1 (graph-scope): the node (g, n) satisfies minCount 1 exactly when it has the property in its own graph.
pub open spec fn min_ok_rule(r: Rows, g: G, n: N) -> bool { prop(r, g, n) }
/// As built: the IRI n satisfies minCount when any graph's row of n with the property is loaded.
pub open spec fn min_ok_built(r: Rows, focus: Option<Set<N>>, n: N) -> bool { loaded(focus, n) && exists|h: G| #[trigger] prop(r, h, n) }

/// L1 for sh:class on an edge: every target of the node's edges, in its graph, carries the label there.
pub open spec fn class_ok_rule(r: Rows, g: G, n: N) -> bool { forall|m: N| #[trigger] edg(r, g, n, m) ==> lab(r, g, m) }
/// As built: every loaded edge target has a loaded rdf:type triple of the label (in any graph).
pub open spec fn class_ok_built(r: Rows, focus: Option<Set<N>>, n: N) -> bool {
    forall|h: G, m: N| (loaded(focus, n) && #[trigger] edg(r, h, n, m)) ==> (loaded(focus, m) && exists|h2: G| #[trigger] lab(r, h2, m))
}

/// S1/S2: with one graph and the whole namespace loaded, the built answer is the rule's.
pub proof fn theorem_single_graph_min_agrees(r: Rows, g: G, n: N)
    requires forall|h: G| h != g ==> !#[trigger] prop(r, h, n),
    ensures min_ok_built(r, None, n) == min_ok_rule(r, g, n),
{
    if min_ok_built(r, None, n) { let h = choose|h: G| prop(r, h, n); assert(h == g); }
}

/// S4 (bug-str-107): the same id in another graph with the property makes a node without it pass.
pub proof fn theorem_other_graph_masks_missing_property(r: Rows, g: G, h: G, n: N)
    requires g != h, !prop(r, g, n), prop(r, h, n),
    ensures min_ok_built(r, None, n), !min_ok_rule(r, g, n),
{}

/// S6 (bug-str-108): validating only the focus node fails sh:class for a target that carries the label.
pub proof fn theorem_focus_only_breaks_class(r: Rows, g: G, n: N, m: N)
    requires n != m, edg(r, g, n, m), lab(r, g, m), forall|k: N| #[trigger] edg(r, g, n, k) ==> k == m,
        forall|h: G, k: N| h != g ==> !(#[trigger] edg(r, h, n, k)),
    ensures class_ok_rule(r, g, n), !class_ok_built(r, Some(set![n]), n), class_ok_built(r, None, n),
{
    assert(!loaded(Some(set![n]), m));
    assert(loaded(Some(set![n]), n));
    assert forall|h: G, k: N| (loaded(None, n) && #[trigger] edg(r, h, n, k)) implies (loaded(None, k) && exists|h2: G| #[trigger] lab(r, h2, k)) by {
        if h != g { assert(!edg(r, h, n, k)); } else { assert(k == m); assert(lab(r, g, m)); }
    }
}

/// S5: with every row loaded and one graph, sh:class agrees with the rule.
pub proof fn theorem_single_graph_class_agrees(r: Rows, g: G, n: N)
    requires forall|h: G, k: N| h != g ==> !(#[trigger] edg(r, h, n, k)),
        forall|h: G, k: N| h != g ==> !(#[trigger] lab(r, h, k)),
    ensures class_ok_built(r, None, n) == class_ok_rule(r, g, n),
{
    if class_ok_rule(r, g, n) {
        assert forall|h: G, m: N| (loaded(None, n) && #[trigger] edg(r, h, n, m)) implies (loaded(None, m) && exists|h2: G| #[trigger] lab(r, h2, m)) by {
            if h != g { assert(!edg(r, h, n, m)); } else { assert(lab(r, g, m)); }
        }
    }
    if class_ok_built(r, None, n) {
        assert forall|m: N| #[trigger] edg(r, g, n, m) implies lab(r, g, m) by {
            assert(loaded(None, n) && edg(r, g, n, m));
            let h2 = choose|h2: G| lab(r, h2, m);
            if h2 != g { assert(!lab(r, h2, m)); }
        }
    }
}

}
