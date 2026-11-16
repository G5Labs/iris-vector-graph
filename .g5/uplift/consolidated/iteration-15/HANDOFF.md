# Iteration 15: the temporal-origin mark through every edge reader

Before image: seal 14 `3b28796d`. Product `3eaa79cf` unchanged. Guidance as recorded in
[iteration 14's cloud-run.json](../iteration-14/cloud-run.json). Native evidence comes only from the run-isolated
fixture `ivg-cloud-20261116-iris` ([runtime.py](runtime.py), [deployment](runtime.json): pin classes compiled, only
the three `%AI` MCP classes skipped, as in the 2026-11-15 audit runtime).

## Why this workflow

It is a released, already-linked path read by a different final reader. Iteration 14 bound the NDJSON and RDF
exporters, and the NDJSON exporter visibly drops ADR-0009 marked rows while the RDF edge query has no such filter.
The producer of those rows (`Graph.KG.Adjacency.AssertTemporalRow`) and the Cypher relationship-map reader were
unbound. This was a discovery from this session's source reading, not a previously known repair.

## Predictions and outcomes

All were frozen before the observation they concern ([PAIRS](temporal-marker-PAIRS.md)).

| Prediction | Outcome |
|---|---|
| Same triple, unmarked vs marked: NDJSON 1 vs 0 lines; RDF edges 1 vs 4, nodes +2; Cypher count 1 both | held |
| Cypher `properties(r)` on a marked row: unknown | resolved: `{temporal: True, weight: 1.5}` |
| Adoption by `create_edge` or `bulk_create_edges` restores the plain reading | held |
| First temporal weight stays; explicit-first edge never marked; weight 1 omitted | held |
| `create_edge(weight=5.0)` stores `{"weight": 5.0}` | **miss**: stores `{"weight": "5.0"}` (text); every reader still reads 5.0 |
| Bulk adoption drops the bulk call's own weight | withdrawn before observation: `bulk_create_edges` refuses `weight` |
| A sub-unit weight may be written `.5`, breaking JSON readers | **refuted** for 0.5 and 0.75: written `0.5`, `0.75` |

## Owners, formal claims and finding

- New statement [temporal.structural.mark.readers](../../../ontology/features/temporal.g5.md#temporal.structural.mark.readers)
  states how each reader treats a marked edge and its adoption. New child question
  [temporal.structural.mark.visibility](../../../ontology/features/temporal.g5.md#temporal.structural.mark.visibility)
  carries the competing intended outcomes; the working assumption (hide the mark, keep the edge and weight) is the
  agent's, unratified. No existing statement changed except metadata links.
- New Low/Open [bug-tmp-101](../../../Verus_verification/bugs_issues.md#bug-tmp-101), e2e reproduced with plain and
  adopted neighbors. Registers: 154 live bug entries (was 153), 55 simplifications, 146 questions in
  `open_questions.md`; the new question lives in its ontology owner.
- New model [temporal_marker](../../../Verus_verification/models/temporal_marker/NOTES.md): 81 verified = 23 new + 58
  unchanged imports (the accepted RDF generator and NDJSON qualifier module). It derives the stored text from the
  writer history and decodes it through the RDF model's character-level recognizer for any admitted weight spelling,
  then proves the NDJSON, Cypher and RDF readings, including the final report counts (6/3/4 vs 1/1/1).
- Six controls, all EXPECTED_FAIL in full and isolated runs. The first run of `unit-weight-written` was
  FAIL_ELSEWHERE because the report theorem leaned on a lemma contract; it was made self-contained and the original
  receipt is kept.
- Native binding: 160 worlds, 640 comparisons, AGREES; each of six port mutations is caught by 7–62 worlds. The
  first attempt's receipt write failed on a serialization error; its observations are kept.
- The RDF model's internal modules became `pub` (visibility only); its proof, 17 controls and binding were re-run.

## Source binding delta

`member_reach.py`: **254 → 257 of 4,130** ([delta](member-delta.json)). New: `Adjacency.cls::AssertTemporalRow`,
`NodesEdgesMixin.bulk_create_edges`, `translator.py::_edge_props_sql`. Strengthened: `_adopt_temporal_row` (now
from raw text rather than a boolean marker input), `TemporalMixin.create_edge_temporal`. Lost: none. Tier: transcription
with native agreement for all five; `CY_RETYPE_MAP` and ObjectScript number spelling remain providers. Direct
executable-body verification: 0.

## Gates and receipts

`check_consolidated.py` PASS; `check_ontology.py` 447 blocks, 0 issues, 2 inherited warnings; `check_findings.py`
(with the pre-edit snapshot in `previous-findings/`) no problems; [18 freshness cases](freshness-controls.json) pass
(the first run's mislabeled verdict string is kept in `freshness-attempts-run1-label`); correspondence stamp
[correspondence-inputs.json](correspondence-inputs.json).

## Builder diagnostic for this workflow

| Decision | Owner states both cases | Verus distinguishes at the reader |
|---|---|---|
| Marked vs explicit edge in NDJSON | yes (`install.export.ndjson`, `mark.readers`) | yes, now from the producer's text |
| Marked vs explicit edge in RDF content and report | yes (new) | yes, final report counts |
| Marked vs explicit edge in Cypher `properties(r)` | yes (new) | yes (map keys; `CY_RETYPE_MAP` value typing is a provider) |
| Adopted (single or bulk) vs still marked, at all readers | yes | yes |
| First temporal weight vs later weight | already owned (`temporal.write.repeatable`) | yes, now at the row |

Not covered: named-graph and multigraph-key rows, purge and delete interplay, concurrent writers, and
`CY_RETYPE_MAP` internals.

## Cost

About 16:05–16:45 UTC, overlapping the iteration-14 control replay. Native fixture work: probe runs 2 × ~5 s,
binding panel 52 s. Verus: proof ~5 s, six controls ~1 min. Tokens and currency unavailable.

## Next

Not converged. Next workflow (W16): typed equality in Cypher `WHERE` on node versus relationship properties. Since
4.7.0 a node property must hold a stored number to equal a number literal, while relationship qualifiers are still
compared by text spelling. The translator, the largest underserved subsystem (4 of 717 members bound after this iteration), owns that
decision.
