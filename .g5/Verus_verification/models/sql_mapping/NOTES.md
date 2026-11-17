# SQL table mappings

Product `3eaa79cf`, unchanged. Iteration 40 (continuation). Predictions frozen from the owner statements and the API
reference: [sqlmap-PAIRS.md](../../../uplift/consolidated/iteration-40/sqlmap-PAIRS.md). Owner:
[fhir.sql_mapping](../../../ontology/features/fhir.g5.md#fhir.sql_mapping) and its children.

## What the model decides

- `label_source`: a reader takes a label from its engine's mapping cache (the table) or else from IVG's nodes.
- `cache_current`: an engine's cache reflects the stored mappings only if it made the last change, reloaded after it,
  or first loaded after it.
- `joined_built` versus `joined_doc`: the translator joins on a key column of the target table holding the source id;
  the documentation says a key column of the source table.
- `pattern_outcome`: a relationship from a mapped node that is not a mapped relationship is an SQL error.
- `accepted`: `map_sql_table` checks an unqualified name under schema `USER`.

These are decision tables over the inputs that choose the outcome, not a model of SQL translation.

## Theorems (5 verified; no imports)

`theorem_writer_reads_current` (agrees), `theorem_stale_engine_reads_own_nodes` (question
[fhir.sql_mapping.cache](../../open_questions.md#fhir.sql_mapping.cache)), `theorem_fk_side_differs`
([bug-cyp-108](../../bugs_issues.md#bug-cyp-108)), `theorem_mapped_with_ivg_relationship_errors`
([bug-cyp-109](../../bugs_issues.md#bug-cyp-109)), `theorem_unqualified_name_refused`
([bug-cyp-110](../../bugs_issues.md#bug-cyp-110)). No `assume`, `admit` or `external_body`.

## Controls

Five, all EXPECTED_FAIL: `join-on-source-fk`, `unmapped-rel-translated`, `unqualified-checks-sqluser`,
`caches-shared`, `mapping-ignored`.

## Binding

[binding.py](binding.py): fixture-only SQL tables, two engines, 11 outcome classes (which source each engine reads
before and after mapping, removal and reload; join rows or SQL error for both key sides; pattern outcomes; accepted or
refused table names): **AGREES**; each of five mutations is detected.

## Limits

Join tables (`via_table`), property mapping details, `attach_embeddings_to_table`, mapped labels in writes and the
graph scope of mapped rows beyond `USE GRAPH` (q-plt-018) are not exercised. With a same-named column on the target
table, a source-side key would join silently on the wrong column (not exercised).
