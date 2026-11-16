# W15-A: a temporal-origin edge through its readers — predictions frozen before native observation

Frozen 2026-11-16, before any native call on this workflow. Exposure: while integrating iteration 14 I read
`export_graph_ndjson`, `export_rdf`, `_build_rdflib_graph` (edge loop), `TEMPORAL_MARKED_ROW`, ADR-0009 and the
4.x changelog entry "A temporal edge is visible structurally". I have not read the temporal writer's row-insert
code, the Cypher relationship-property reader or the edge-count reader for this case.

Changing input: one default-graph triple `(a, KNOWS, b)` with labels on both ends, written either by
`create_edge` (unmarked row) or by `create_edge_temporal` (ADR-0009 marked row `{"temporal": true}`). Third
neighbor: `create_edge_temporal` followed by `create_edge` on the same triple (adoption clears the marker).
Named-graph neighbor: the same temporal write with `graph="g1"`.

| Reader | Unmarked (create_edge) | Marked (create_edge_temporal) | Adopted (temporal, then create_edge) | Source of prediction |
|---|---|---|---|---|
| `export_graph_ndjson` edge lines / `edges` | 1 / 1 | 0 / 0 | 1 / 1, no `qualifiers` key | ontology install.export.ndjson (iteration 14 rewrite) + Verus ndjson_export `witness_marked_edge_not_written` |
| `export_rdf` SPO triple present | yes | yes | yes | changelog "exports now see it"; Verus rdf_reporting generation |
| `export_rdf` reification envelope + `urn:ivg:qualifier/temporal` | none | 4 envelope triples + 1 qualifier triple, value `true`^^xsd:boolean | none | Verus rdf_reporting `theorem_original_object_decides_envelope` on raw text `{"temporal": true}`; ontology install.export.rdf.content (only `inferred` hidden) |
| `export_rdf` report `edges` (edge triples only, labels excluded) | 1 | 4 (SPO + 3 IRI-valued envelope triples) | 1 | Verus `theorem_non_type_uri_count_rule`; ontology install.export.rdf.report |
| `export_rdf` report `nodes` | subjects a (+ b only if b is a subject) | + 2 blank subjects | as unmarked | Verus `theorem_summary_counts_subjects_not_objects` |
| Cypher `MATCH (a)-[r:KNOWS]->(b) RETURN count(r)` | 1 | 1 | 1 | ADR-0009 "visible to Cypher MATCH" |
| Cypher `properties(r)` | `{}` | unknown: `{temporal: true}` if qualifiers are read raw, `{}` if the marker is hidden | `{}` | no owner states it; no Verus model reads qualifiers for this case |

Expected material contrast: the RDF reader turns an internal ADR-0009 marker into a public reified qualifier and
inflates the report (edges 1 → 4, nodes +2) for the same user-visible triple, while the NDJSON reader omits the
edge entirely. Neither the owners nor the models state which export representation is intended for a marked row.

Missing roles: the marked-row producer (temporal writer → `rdf_edges` row text) is not modeled; the RDF model
takes qualifier text as raw input. The Cypher property reader for marked rows is unowned.

## Addendum A (after the first native run, before the producer neighbors were observed)

First run `temporal-marker-observed-20261116T161323Z.json`: all frozen RDF/NDJSON/Cypher-count predictions held. The
unknown `properties(r)` cell resolved to `{temporal: True, weight: 1.5}`. The probe's named-graph Cypher call used an
unsupported `graph=` argument (harness error, retained); its export cells held.

Source read after that run: `Graph.KG.Adjacency.AssertTemporalRow` (insert only when the triple has no row; qualifiers
`{"temporal":true}` plus `"weight"` when the weight is not 1), `NodesEdgesMixin._adopt_temporal_row` (qualifiers become
the explicit call's own), `_ADOPT_TEMPORAL_ROW_SQL` used by `bulk_create_edges` (qualifiers NULL), translator
`_edge_props_sql` (`CY_RETYPE_MAP(qualifiers)`, no key filter).

Withdrawn candidate before observation: "bulk adoption drops the bulk call's weight". `bulk_create_edges` refuses
`weight`/`qualifiers` keys, so both writers adopt with the call's own (possibly empty) qualifiers. No divergence.

| World | Prediction (row qualifiers; Cypher r.weight; NDJSON edge lines; RDF edges) |
|---|---|
| temporal weight 1.0 | `{"temporal":true}`; None; 0; 3+1=4 (no weight qualifier) |
| temporal 1.5 then temporal 3.0 | unchanged `{"temporal":true,"weight":1.5}`; 1.5; 0; 4 |
| temporal 1.5 then create_edge(weight=5.0) | `{"weight": 5.0}` (Python json spelling); 5.0; 1; 4 (weight-qualified, unmarked) |
| temporal 1.5 then bulk_create_edges | NULL; None; 1; 1 |
| create_edge(weight=5.0) then temporal 1.5 | unchanged `{"weight": 5.0}`; 5.0; 1; 4 |

## Addendum B (second run observed; before the binding panel)

Second run `temporal-marker-observed-20261116T161532Z.json`: every addendum-A prediction held except the explicit
weight's spelling. `create_edge(weight=5.0)` stores `{"weight": "5.0"}` (text value), not `{"weight": 5.0}`; Cypher,
NDJSON and RDF still read it as 5.0. Recorded as a prediction miss, not a defect.

New prediction, frozen before observation: a temporal weight below 1 such as 0.5. ObjectScript's canonical number is
`.5`; whether `%ToJSON` writes `.5` or `0.5` is unknown. If it writes `.5`, the row text is not JSON: RDF export's
`json.loads` raises, is swallowed, and the edge gets no envelope (edges 1, not 4); `_adopt_temporal_row` returns False,
so a later `create_edge` reports a duplicate and the row stays marked (NDJSON 0 lines, Cypher count 1); Cypher
`properties(r)` depends on `CY_RETYPE_MAP`'s own parser. If it writes `0.5`, the 1.5 pattern holds.

## Addendum C (binding panel outcome)

[Binding receipt](../../../Verus_verification/results/temporal_marker/20261116T164055Z-binding/receipt.json): 160 worlds
(every history of length 1–3 over five writers, plus single temporal writes at 2.0, 0.5, 3.25, 10.0, 0.75), 640
comparisons, AGREES. The first attempt ran the same panel but failed while writing its receipt (a harness
serialization error); its observations are kept in `20261116T163955Z-binding-attempt1-harness-error`.

- Bounded refutation of the addendum-B risk: `%ToJSON` writes `{"temporal":true,"weight":0.5}` and `0.75` with a
  leading zero, so sub-unit weights decode, adopt and export like 1.5. Whole weights are written without a decimal
  point (`2`, `10`). Only these five weights were tested.
- Each of the six rule mutations in the port disagrees with 7–62 actual worlds, so the panel distinguishes every
  modeled rule.
