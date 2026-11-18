# SHACL data graph

Product `3eaa79cf`, unchanged. Iteration 39 (continuation). Predictions frozen from SEMANTIC_LAYER.md and the API
reference: [shacl-PAIRS.md](../../../uplift/consolidated/iteration-39/shacl-PAIRS.md). Owner (new):
[install.shacl](../../../ontology/features/data-interchange.g5.md#install.shacl); governing rule:
[graph scope](../../../ontology/concepts/graph-scope.g5.md).

## What the model decides

Rows are facts per (graph, node ID): has the shape's property, has the class label, has an edge to another node.
`loaded` is what `_build_rdflib_graph` reads (every row, or with `node_ids` only listed subjects). The rule
(graph-scope) checks a node in its own graph; the as-built checks pySHACL makes see one IRI per node ID with the union of
every graph's loaded triples (`min_ok_built`, `class_ok_built`).

## Theorems (4 verified; no imports)

| Theorem | Claim | Disposition |
|---|---|---|
| `theorem_single_graph_min_agrees` | one graph, every row loaded: minCount agrees with the rule | as-built agrees |
| `theorem_single_graph_class_agrees` | one graph, every row loaded: sh:class agrees with the rule | as-built agrees |
| `theorem_other_graph_masks_missing_property` | another graph's same-ID node with the property makes a node without it pass | [bug-str-107](../../bugs_issues.md#bug-str-107) |
| `theorem_focus_only_breaks_class` | with only the focus listed, a correctly labelled target fails sh:class | [bug-str-108](../../bugs_issues.md#bug-str-108) |

No `assume`, `admit` or `external_body`. Earlier runs kept: two ERROR runs (trigger inference) and one UNEXPECTED
(multi-term trigger), before the predicates were wrapped in spec functions.

## Controls

Four, all EXPECTED_FAIL: `data-graph-keeps-graphs-apart`, `focus-loads-targets` (the S6 repair), `rule-ignores-graph`,
`class-ignores-label`.

## Binding

[binding.py](binding.py): six cases through the actual `validate_shacl` with `node_ids` naming this run's nodes;
`conforms` compared with the port: **AGREES**; each of three mutations is detected.

## Premises and limits

- pySHACL 0.40.2 with rdflib 7.6.0 validates the ConjunctiveGraph's union and follows Core semantics for `sh:minCount`
  and `sh:class` (provider premise, observed only through these shapes).
- The literal typing rule (a stored "2011" is an integer, W45 S3) is stated in the owner and observed, not modeled here.
- Not exercised: other Core constraints, URL shapes, SHACL-AF, `sh:severity` other than Violation.
