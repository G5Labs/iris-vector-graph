# RDF export from a Cypher query

Product `3eaa79cf`, unchanged. Iteration 45 (continuation). Predictions frozen from SEMANTIC_LAYER.md:
[cyphexport-PAIRS.md](../../../uplift/consolidated/iteration-45/cyphexport-PAIRS.md). Owner (new):
[install.export.rdf.cypher](../../../ontology/features/data-interchange.g5.md#install.export.rdf.cypher).

## What the model decides

`written` (whether a row becomes a triple, by column naming and whether a value is null or Python-falsy) and
`export_answer` (distinct triples; 0 for a failed query, whose error is not read).

## Theorems (3 verified; no imports)

`theorem_ordinary_and_null_rows` (agrees), `theorem_falsy_value_depends_on_names`
([bug-plt-112](../../bugs_issues.md#bug-plt-112)), `theorem_failed_query_looks_empty`
([bug-plt-111](../../bugs_issues.md#bug-plt-111)).

## Controls

Four, all EXPECTED_FAIL: `positional-checks-null`, `error-raised`, `named-drops-falsy`, `null-written`.

## Binding

[binding.py](binding.py): six answers through the actual `export_rdf_from_cypher`: **AGREES**; each mutation detected.

## Limits

Prefix registration and declaration (W51 C7-C9) are observed and stated in the owner, not modeled.
