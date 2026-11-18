# Temporal-origin mark: one triple's row from its writers to the NDJSON, RDF and Cypher readers

Product `3eaa79cf`, unchanged. Iteration 15 of the consolidated uplift (cloud continuation). Predictions were frozen
before any native observation in [temporal-marker-PAIRS.md](../../../uplift/consolidated/iteration-15/temporal-marker-PAIRS.md),
with the exposure noted there. Owners: [temporal.structural.mark](../../../ontology/architecture/adjacency-and-derived-data.g5.md#temporal.structural.mark)
and its new reader statement and question; the export owners in `install.g5.md` keep their own rules.

## What the model decides

The input is one default-graph triple's history of writes. Nothing is supplied as a result: the row text, whether it
is marked, and each reader's answer are derived.

- **Producer.** `temporal_write` transcribes `Graph.KG.Adjacency.AssertTemporalRow`: it inserts a row only when the
  triple has none, with the characters `{"temporal":true}` plus `,"weight":<w>` when the weight is not 1. A later
  temporal write never changes an existing row. `explicit_write` transcribes `create_edge` with
  `_adopt_temporal_row`: insert when absent; on a duplicate, replace the qualifiers with the call's own only when the
  row decodes to an object whose `temporal` is true. `bulk_write` transcribes `bulk_create_edges` with
  `_ADOPT_TEMPORAL_ROW_SQL`: insert when absent; set qualifiers NULL when the text starts `{"temporal"`.
- **Decoding.** `theorem_marker_decodes` runs the accepted RDF model's character-level JSON recognizer over the marker
  for any admitted weight spelling: one entry `temporal=True`, plus `weight=w` when `w` is not `1`. The same text is
  marked for both marker tests (`theorem_marker_is_marked_for_both_readers`): the SQL prefix used by NDJSON export and
  bulk adoption, and the decoded object used by `create_edge` adoption.
- **Readers.** NDJSON export writes a line unless the row is marked. Cypher `properties(r)` keeps every decoded key.
  RDF export is the accepted `rdf_reporting` generator, imported unchanged except that its two internal modules are
  now `pub` so this model can name the decoder and literal types.

## Theorems (23 new obligations; 58 unchanged imports: rdf_reporting 50, NDJSON qualifier module 8; total 81)

| Theorem | Distinction |
|---|---|
| `theorem_temporal_on_absent_marks`, `theorem_temporal_never_rewrites_a_row`, `theorem_first_temporal_weight_wins` | first temporal write decides the row; later weights do not reach it |
| `theorem_explicit_first_stays_unmarked`, `theorem_explicit_duplicate_keeps_unmarked` | an explicit edge written first is never marked; a duplicate explicit write leaves an unmarked row alone |
| `theorem_explicit_adopts_marked_with_own`, `theorem_bulk_adopts_marked_to_null` | both adoption paths clear the mark; single takes its own qualifiers, bulk none |
| `theorem_ndjson_omits_marked_includes_adopted` | same triple: marked row has no NDJSON line; adopted row has one |
| `theorem_cypher_reports_marker_key` | marked row's relationship map contains `temporal`; adopted row's does not |
| `theorem_rdf_marked_row_is_reified` | marked row: SPO + 4 envelope quads + boolean `temporal` qualifier (+ weight); adopted row: the SPO quad alone |
| `theorem_rdf_report_counts` | final report for the one-edge world: marked (unit weight) 6 triples / 3 nodes / 4 edges; plain 1 / 1 / 1 |

Premises: the weight's JSON spelling is a canonical integer or dyadic decimal starting with a digit or `-` (the
ObjectScript `+pWeight` then `%ToJSON` spelling is a provider); the predicate's minted IRI is not `rdf:type`; one row
per triple (multigraph edge keys, named graphs, purge and concurrency are outside). No `assume`, `admit` or
`external_body`.

## Controls

Six controls each change one producer or reader rule and must fail their named theorems in both the full run and an
isolated run. The first run of `unit-weight-written` was FAIL_ELSEWHERE: verified alone, `theorem_rdf_report_counts`
passed because it called `theorem_marker_decodes`, whose postcondition is trusted in an isolated run. The report
theorem now derives the stored text from `marker`'s definition and uses only text-level lemmas, so it fails on its own;
the earlier receipt is retained. Final controls: `temporal-overwrites-row`, `unit-weight-written`, `adoption-ignores-marker`, `bulk-keeps-marker`,
`ndjson-writes-marked`, `cypher-hides-marker`. The last is the alternative representation in the open question: the
model distinguishes it from as-built.

## Source roles and evidence tier

| Member | Role | Evidence |
|---|---|---|
| `iris_src/src/Graph/KG/Adjacency.cls::AssertTemporalRow` | marker producer | transcription with native agreement (binding panel on the fixture) |
| `iris_vector_graph/_engine/temporal.py::TemporalMixin.create_edge_temporal` | caller of the producer | native agreement |
| `iris_vector_graph/_engine/nodes_edges.py::NodesEdgesMixin._adopt_temporal_row` | single adoption | native agreement (strengthens `edge_acceptance`, which takes the mark as a boolean) |
| `iris_vector_graph/_engine/nodes_edges.py::NodesEdgesMixin.bulk_create_edges` | bulk adoption | native agreement |
| `iris_vector_graph/cypher/translator.py::_edge_props_sql` | Cypher relationship-map reader | transcription with native agreement; `CY_RETYPE_MAP` itself is a provider |
| `export_graph_ndjson`, `_build_rdflib_graph`, `export_rdf` | readers | already bound by iteration 14; this model composes their rules with the producer |

The binding runs every write history of length 1–3 over {temporal 1.5, temporal 1.0, create_edge,
create_edge(weight=5.0), bulk_create_edges} plus single temporal writes at further weights, each on its own triple, and
compares the raw row, the NDJSON line, the parsed RDF content and the Cypher keys with a Python port of these rules.
The explicit writer's own qualifier text is observed on a separate fresh triple. Six port mutations mirroring the
controls must each disagree with at least one observation. No executable product body is verified.

## Results

- Proof: 81 verified (`results/temporal_marker/*-prove`), no `assume`, `admit` or `external_body`.
- Controls: 6/6 EXPECTED_FAIL in full and isolated runs; no raw log mentions a resource limit.
- Binding: [receipt](../../results/temporal_marker/20261116T164055Z-binding/receipt.json), 160 worlds, 640 comparisons,
  AGREES; port mutations detected by 62, 7, 33, 14, 19 and 19 worlds. Sub-unit weights are written with a leading
  zero (`0.5`), whole weights without a point (`2`). The first attempt's receipt write failed on a serialization error;
  its observations are kept in `20261116T163955Z-binding-attempt1-harness-error`.
- The RDF model's two internal modules became `pub` for this import; its proof (50), 17 controls and binding (2,229
  comparisons) were re-run on the changed bytes and still pass.

Replay, from the repository root with the run environment in the runbook and the fixture running:

```sh
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/temporal_marker
CONTROL=cypher-hides-marker python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/temporal_marker
$RUN_DIR/venv/bin/python -B .g5/Verus_verification/models/temporal_marker/binding.py
```

