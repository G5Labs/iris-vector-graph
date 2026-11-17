# RDF import

Product `3eaa79cf`, unchanged. Iteration 41 (continuation). Predictions frozen from SEMANTIC_LAYER.md and the API
reference: [rdfimport-PAIRS.md](../../../uplift/consolidated/iteration-41/rdfimport-PAIRS.md). Owner (new):
[install.import.rdf](../../../ontology/concepts/install.g5.md#install.import.rdf).

## What the model decides

Per parsed statement of `import_rdf`: `effective_graph` (a named quad context wins, else the argument); `stored` and
`stored_has_datatype` (a literal's text only); `after_import`/`counted` (a property row is inserted only when the key is
unset, and only then counted); `key_of` (the predicate's local name); `infer_graph` (the argument). These are decision
tables over the inputs that choose each outcome.

## Theorems (5 verified; no imports)

`theorem_context_wins` (agrees), `theorem_local_name_collision` (as documented),
`theorem_datatype_dropped` ([bug-str-109](../../bugs_issues.md#bug-str-109)), `theorem_reimport_keeps_old_value`
([bug-str-110](../../bugs_issues.md#bug-str-110)), `theorem_infer_ignores_contexts`
([bug-str-111](../../bugs_issues.md#bug-str-111)). No `assume`, `admit` or `external_body`.

## Controls

Five, all EXPECTED_FAIL: `context-ignored`, `keep-datatype`, `upsert-property`, `full-iri-key`, `infer-on-contexts`.

## Binding

[binding.py](binding.py): fresh N-Quads and Turtle files through the actual `import_rdf`, read back through
`node_exists`, `get_node`, Cypher and `rdf_edges`: **AGREES** on 7 outcome classes; each of five mutations is detected.

## Premises and limits

- Readers return a property stored as text `2011` as the string `"2011"` (observed for `get_node` and Cypher).
- Which of two colliding literals survives follows rdflib's iteration order; not compared.
- Not exercised: TriG, JSON-LD, language tags, blank nodes across files, batch boundaries, a caller's transaction.
