// product 3eaa79cf: which nodes embed_nodes embeds (iris_vector_graph/_engine/embeddings.py embed_nodes,
//   iris_vector_graph/embed_selector.py build_node_where, _glob_to_sql_like). A node of the requested graph is selected
//   when its ID has the label in rdf_labels (in any graph: the subquery has no graph condition), is listed when node_ids
//   is given, and does not match exclude_pattern; then it is embedded unless it already has a vector on the route and
//   neither force nor missing_only is set (missing_only selects only nodes without a vector).
//   Provider premise (observed on IRIS 2026.1): LIKE has no default escape character, so the backslash the glob
//   translation puts before `_` and `%` is a literal character: a pattern with either never matches an ID without a
//   backslash.
use vstd::prelude::*;
verus! {

pub struct Node { pub label_here: bool, pub label_elsewhere: bool, pub listed: bool, pub matches_glob: bool, pub has_vector: bool }

/// Whether the exclusion takes effect: only for a pattern with no `_` or `%` (they are escaped without ESCAPE).
pub open spec fn excluded(n: Node, pattern_has_special: bool) -> bool { n.matches_glob && !pattern_has_special }

/// As built: the label may come from another graph's row of the same ID.
pub open spec fn label_ok_built(n: Node) -> bool { n.label_here || n.label_elsewhere }
/// Rule (graph scope): a node's labels are those of its own graph.
pub open spec fn label_ok_rule(n: Node) -> bool { n.label_here }

pub open spec fn selected(n: Node, pattern_has_special: bool) -> bool { label_ok_built(n) && n.listed && !excluded(n, pattern_has_special) }

pub open spec fn embedded(n: Node, pattern_has_special: bool, force: bool, missing_only: bool) -> bool {
    selected(n, pattern_has_special) && (force || !n.has_vector)
}

/// E2/E3: without force an existing vector is kept; with force it is replaced; missing_only behaves like the default.
pub proof fn theorem_existing_vectors(n: Node)
    requires selected(n, false), n.has_vector,
    ensures !embedded(n, false, false, false), !embedded(n, false, false, true), embedded(n, false, true, false),
{}

/// E5: a pattern without `_` or `%` excludes the IDs it matches.
pub proof fn theorem_plain_pattern_excludes(n: Node)
    requires n.matches_glob,
    ensures !selected(n, false),
{}

/// E1 (bug-srch-105): a pattern containing `_` or `%` excludes nothing.
pub proof fn theorem_special_pattern_excludes_nothing(n: Node)
    requires n.matches_glob, n.label_here, n.listed, !n.has_vector,
    ensures selected(n, true), embedded(n, true, false, false),
{}

/// E8 (bug-srch-106): a node whose label is only on its twin in another graph is selected, against graph scope.
pub proof fn theorem_label_from_other_graph(n: Node)
    requires !n.label_here, n.label_elsewhere, n.listed, !n.matches_glob,
    ensures selected(n, false), !label_ok_rule(n),
{}

}
