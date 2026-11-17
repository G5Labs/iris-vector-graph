# Iteration 50: retrieval and IVF repairs (review 47-49 item 1, item 4 for `retrieval_compose`, m8, m9)

Worker output for the builder. Product `3eaa79cf` unchanged; nothing committed. Files changed by this worker:
`models/retrieval_compose/{retrieval_compose.rs, model.json, manifest.json, NOTES.md, BINDINGS.md, binding.py}`,
`models/ivf_entries/{ivf_entries.rs, model.json, manifest.json, NOTES.md, BINDINGS.md, binding.py}`,
`ontology/features/algorithms.g5.md` (`algorithms.op.subgraph.guided` body and metadata; `algorithms.op.subgraph`
metadata), `ontology/features/search.g5.md` (`search.ivf.metric` body and metadata), and new receipts under
`results/retrieval_compose/20261117T03*` and `results/ivf_entries/20261117T03*`. Fixture: `ivg-cont-20261117-iris` only,
prefixes `i50r_…` (scratch probe) and the bindings' own `i49b…`/`ie…` prefixes with fresh tags.

## (a) Register text for the builder to apply

### Replacement for the whole `bug-plt-113` entry (anchor kept; heading refined; the two ontology link texts in `algorithms.g5.md` already use the new heading)

```markdown
<a id="bug-plt-113"></a>
### kg_PPR_GUIDED_SUBGRAPH lists almost none of the edges among its answered nodes and can answer more nodes than its cap

Severity: High · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 49)

Found by: W56 prediction P1 ([predictions](../uplift/consolidated/iteration-49/retrieval-PAIRS.md), missed), traced through `kg_PPR_GUIDED_SUBGRAPH` and `Graph.KG.Subgraph.SubgraphJson`; corrected after [review 47-49](../uplift/consolidated/iteration-50/REVIEW-47-49.md) item 1, which found that the iteration-49 entry treated the documented cap as the defect and proposed the wrong repair, and found the seeds-over-the-cap case. [retrieval_compose](models/retrieval_compose/NOTES.md) `theorem_filled_cap_expands_only_first_node` and `theorem_admitted_seeds_ignore_cap` (every input), witnesses `theorem_guided_subgraph_drops_edges_among_top_nodes` and `theorem_guided_seeds_exceed_cap`, neighbor `theorem_guided_uncapped_lists_all_edges`; controls `edges-among-answered`, `seeds-capped`, `expand-whole-frontier-at-cap`, `guided-cap-top-k-only` ([prove](results/retrieval_compose/20261117T032018Z-prove/receipt.json), 15 of 15 controls EXPECTED_FAIL). The iteration-49 control `guided-cap-max-nodes` encoded the wrong repair and is withdrawn (its receipts are kept).

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, ObjectScript `SubgraphJson` path (no Arno reader on the fixture): iteration-50 [fixture reproduction](../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json) and [binding](results/retrieval_compose/20261117T032153Z-binding/receipt.json) `guided[*]`, `guided_more[*]` (AGREES 45 cases); earlier [observation](../uplift/consolidated/iteration-49/retrieval-observed3-20261117T024208Z.json) `PG_star_top3`, `PG_star_top7`, `PG_star_top50`. Default graph, star s → a1..a6 plus a1 → a2. `kg_PPR_GUIDED_SUBGRAPH([s], ppr_top_k=7)` answers all seven nodes with the single edge a1 → a2; `ppr_top_k=3` answers s, a1, a2 with only a1 → a2. Seeds s, a3, a4 with `ppr_top_k=1` answer three nodes (the cap is 1) and no edge, although s → a3 and s → a4 join them; [s] with `ppr_top_k=50` and `max_nodes=3` answers seven nodes and only a1 → a2. Passing neighbor: [s] with `ppr_top_k=50` and the default `max_nodes` answers all seven edges.

Expected: the docstring (`algorithms.py:956-957`): the subgraph of the seeds and the top nodes within `k_hops`, "capped at `min(max_nodes, ppr_top_k)` nodes"; the [design note](../../docs/dev/notes/enhancements/001-ppr-guided-subgraph.md) (`top_k` a "hard node cap"; acceptance "`len(result.nodes) <= top_k` always"); [algorithms.op.subgraph](../ontology/features/algorithms.g5.md#algorithms.op.subgraph): the edges among the answered nodes. The cap itself is intended.

Observed: `kg_PPR_GUIDED_SUBGRAPH` calls `kg_SUBGRAPH(seeds + top_ids, k_hops, max_nodes=min(max_nodes, ppr_top_k))` (`algorithms.py:971-973`). `SubgraphJson` admits every seed that has an edge with no cap test (`Subgraph.cls:36-48`), so the seeds alone can exceed the cap; once the count has reached the cap it expands only the first frontier node in ID order, recording that node's out-edges, and stops (`Subgraph.cls:51-99`). With Arno loaded and no `edge_types`, `IRISGraphStore.execute_subgraph` asks `ArnoAccel.SubgraphNativeJson` first (`iris_sql_store.py:2526-2541`); that path was not checked.

Consequence: whenever the walk reaches at least `ppr_top_k` nodes (with the default 50, any ordinary graph), the answer is the top nodes with only the out-edges of the alphabetically first one, which may also point outside the answer; with more seeds than the cap the answer is larger than the documented cap. A retrieval caller gets a node list with its relationships missing and no sign of it. High is kept: the method's main output is wrong under its defaults, silently; the cap being intended does not change the edge loss. The over-cap node count alone would be Medium.

Repair proposal (not implemented): keep the cap; admit seeds and top nodes only up to the cap (best PPR score first), then list every edge whose two ends are answered (the same repair as bug-plt-114's). Preserve: the cap `min(max_nodes, ppr_top_k)`, the PPR ranking and `ppr_top_k`, argument checks before any read, `k_hops`, and the uncapped answer (all seven edges when the cap exceeds the reachable nodes). Writers and readers: `SubgraphJson` (seed loop, frontier loop, edge list), `kg_SUBGRAPH` and `kg_PPR_GUIDED_SUBGRAPH` (reshape), `IRISGraphOperators.kg_PPR_GUIDED_SUBGRAPH`; the Arno reader must give the same answer. Distinguishing cases: [s] with `ppr_top_k=3` lists s → a1 and s → a2; seeds s, a3, a4 with `ppr_top_k=1` answer one node. Checked in the model only (controls `edges-among-answered` and `seeds-capped` make the departures fail while the uncapped neighbor verifies); not run on the product. Governing statement: [algorithms.op.subgraph.guided](../ontology/features/algorithms.g5.md#algorithms.op.subgraph.guided).
```

### Additions to other entries (append; wording proposed)

- `bug-plt-114`, end of `Found by:` — "Iteration 50: `theorem_capped_subgraph_lists_edge_to_unlisted_node` now holds for every node, adjacency and state at the cap (review 47-49 m9); the repair is checked in the model by the control `edges-among-answered`, which also repairs bug-plt-113's edge loss."
- `bug-srch-107`, end of `Reproduced by:` — "Iteration 50 (review 47-49 m8): the cross-cell case needs no change of vector. Under metric "cosine" or "dot", re-inserting a node with the vector the build stored can choose another cell, because the build clusters by Euclidean k-means and `Insert` picks the cell with the largest dot product ([binding](results/ivf_entries/20261117T032444Z-binding/receipt.json) `cell_cosine`, `cell_dot`: built in cell 0, inserted in cell 1, now in both, `indexed` + 1; neighbor `cell_l2` keeps cell 0). [ivf_entries](models/ivf_entries/NOTES.md) `theorem_cosine_reinsert_changes_cell`, neighbor `theorem_l2_insert_matches_build`, control `insert-by-distance`."
- `bug-srch-109`, `Observed:` replace the last sentence with — "`ivf_build` clusters the raw vectors with Euclidean k-means whatever the metric and stores them in those cells (`vector.py:1985-2017`, `AddBatch`); nothing divides by a length. So under "cosine" the build's cells follow distance while `Search` and `Insert` follow the dot product (review 47-49 m8; see bug-srch-107)." In `Found by:` the neighbor `theorem_equal_lengths_agree` now holds for every equal-length pair (m9) and `cosine-takes-l2-branch` also names `theorem_cosine_metric_misranks`.

No new finding IDs are proposed: the seeds-over-cap case belongs to bug-plt-113 (same call, same reader, same repair site); the cell inconsistency is reported as a new trigger of bug-srch-107 and a cause in bug-srch-109.

## (b) `crosswalk/decision-links.tsv` rows

Renamed or removed formal names: `truncate_first` (removed; **no row referenced it**), `seeded` kept, `lemma_admit_counts_all` (never registered; removed). All 31 existing rows that reference `retrieval_compose.rs` or `ivf_entries.rs` still resolve to exactly one declaration (checked by script). Theorem signatures that changed but kept their names: `theorem_capped_subgraph_lists_edge_to_unlisted_node`, `theorem_guided_cap_is_ppr_top_k`, `theorem_hybrid_c_zero_becomes_60`, `theorem_equal_lengths_agree`.

Grade for new and changed rows: `Observed (actual product on run-isolated IRIS 2026.1 continuation fixture; native binding 45 cases, iteration 50; inspected transcription)` for retrieval_compose, `Observed (actual product on run-isolated IRIS 2026.1 continuation fixture; native binding 9 cases, iteration 50; inspected transcription)` for ivf_entries. Design column: `as-built bounded transcription`.

Change (text only, same formal item and relation):

| Line | Change | Reason |
|---|---|---|
| 711 (`kg_PPR_GUIDED_SUBGRAPH` 971) | role → `decision: hands kg_SUBGRAPH the documented cap min(max_nodes, ppr_top_k) and the seeds plus the PPR top ids, which can exceed it (bug-plt-113)` | the cap is intent, not the defect (item 1) |
| 642 (`IVFIndex.cls::Build` 6) | formal item → `.g5/Verus_verification/models/ivf_entries/ivf_entries.rs::theorem_cosine_reinsert_changes_cell`; role → `effect: stores the k-means centroids unnormalized and cfg metric, which Insert's and Search's metric branches read; assigns no cell itself (AddBatch stores the k-means labels)` | m8: the model now has the cell choice that reads Build's centroids, so Build's row constrains a modeled reader instead of naming `entry_score`; keeps `models` |

Add (tab-separated, in this column order: block, role, path, symbol, pin lines, family, formal item, relation, design, grade):

```
algorithms.op.subgraph.guided	decision: the seed loop admits every seed with an edge either way and counts it, with no cap test, so seeds alone can exceed the cap (bug-plt-113)	iris_src/src/Graph/KG/Subgraph.cls	SubgraphJson	36-48	C-retrieval_compose	.g5/Verus_verification/models/retrieval_compose/retrieval_compose.rs::theorem_admitted_seeds_ignore_cap	proves	as-built bounded transcription	Observed (actual product on run-isolated IRIS 2026.1 continuation fixture; native binding 45 cases, iteration 50; inspected transcription)
algorithms.op.subgraph.guided	decision: after each frontier node the count is tested against the cap; once the seeds fill it only the first node in ID order is expanded (bug-plt-113)	iris_src/src/Graph/KG/Subgraph.cls	SubgraphJson	87-99	C-retrieval_compose	.g5/Verus_verification/models/retrieval_compose/retrieval_compose.rs::theorem_filled_cap_expands_only_first_node	proves	as-built bounded transcription	Observed (actual product on run-isolated IRIS 2026.1 continuation fixture; native binding 45 cases, iteration 50; inspected transcription)
algorithms.op.subgraph.guided	witness: seeds s, a3, a4 with ppr_top_k 1 answer three nodes and no edge (bug-plt-113)	iris_vector_graph/_engine/algorithms.py	AlgorithmsMixin.kg_PPR_GUIDED_SUBGRAPH	971-973	C-retrieval_compose	.g5/Verus_verification/models/retrieval_compose/retrieval_compose.rs::theorem_guided_seeds_exceed_cap	witnesses	as-built bounded transcription	Observed (actual product on run-isolated IRIS 2026.1 continuation fixture; native binding 45 cases, iteration 50; inspected transcription)
algorithms.op.subgraph	reader: the answer is the recorded edge list (kg_SUBGRAPH reshapes it, adding none); the documented answer lists every edge between answered nodes	iris_vector_graph/_engine/algorithms.py	AlgorithmsMixin.kg_SUBGRAPH	880-946	C-retrieval_compose	.g5/Verus_verification/models/retrieval_compose/retrieval_compose.rs::lists_edge	models	as-built bounded transcription	Observed (actual product on run-isolated IRIS 2026.1 continuation fixture; native binding 45 cases, iteration 50; inspected transcription)
algorithms.op.subgraph.guided	alternate reader, not modeled: with Arno loaded, routing native and no edge_types, execute_subgraph asks SubgraphNativeJson first; the theorems cover the Owner path only	iris_src/src/Graph/KG/ArnoAccel.cls	SubgraphNativeJson	288	C-retrieval_compose	.g5/Verus_verification/models/retrieval_compose/retrieval_compose.rs::expand_frontier	cites	as-built bounded transcription	Inspected only (no Arno reader on the fixture; iteration 50 scope note)
search.ivf.metric	decision: Insert's own metric branch picks the cell: dot product for "cosine" and "dot", negated squared distance otherwise; first best cell wins (review 47-49 m8)	iris_src/src/Graph/KG/IVFIndex.cls	Insert	195-210	C-ivf_entries	.g5/Verus_verification/models/ivf_entries/ivf_entries.rs::theorem_cosine_reinsert_changes_cell	models	as-built bounded transcription	Observed (actual product on run-isolated IRIS 2026.1 continuation fixture; native binding 9 cases, iteration 50; inspected transcription)
search.ivf.metric	decision (neighbor): under "l2" Insert picks the cell the build picks	iris_src/src/Graph/KG/IVFIndex.cls	Insert	200-205	C-ivf_entries	.g5/Verus_verification/models/ivf_entries/ivf_entries.rs::theorem_l2_insert_matches_build	proves	as-built bounded transcription	Observed (actual product on run-isolated IRIS 2026.1 continuation fixture; native binding 9 cases, iteration 50; inspected transcription)
search.ivf.metric	decision: clusters the raw vectors with Euclidean MiniBatchKMeans whatever the metric and passes the labels to AddBatch (review 47-49 m8)	iris_vector_graph/_engine/vector.py	VectorMixin.ivf_build	1985-2017	C-ivf_entries	.g5/Verus_verification/models/ivf_entries/ivf_entries.rs::build_cell	models	as-built bounded transcription	Observed (actual product on run-isolated IRIS 2026.1 continuation fixture; native binding 9 cases, iteration 50; inspected transcription)
search.ivf.metric	effect: stores each vector in the cell its k-means label names	iris_src/src/Graph/KG/IVFIndex.cls	AddBatch	237	C-ivf_entries	.g5/Verus_verification/models/ivf_entries/ivf_entries.rs::build_cell	models	as-built bounded transcription	Observed (actual product on run-isolated IRIS 2026.1 continuation fixture; native binding 9 cases, iteration 50; inspected transcription)
```

Reach effect: every member above already has an active row (`SubgraphJson`, `kg_PPR_GUIDED_SUBGRAPH`, `kg_SUBGRAPH`,
`Insert`, `ivf_build`, `AddBatch`, `Build`), so active bindings neither gain nor lose from this worker's rows.
`ArnoAccel.cls::SubgraphNativeJson` becomes a `cites` locator only (counted under `rejected` as citation only). Members
strengthened (new formal distinction at an already-bound member): `SubgraphJson` (seed admission, filled-cap stop),
`kg_PPR_GUIDED_SUBGRAPH` (seeds over cap), `kg_SUBGRAPH` (reader rule), `IVFIndex.Insert` (cell choice),
`ivf_build` and `AddBatch` (the build's cell), `IVFIndex.Build` (now constrains the modeled cell reader).

## (c) Receipts

| Model | Prove | Controls | Binding |
|---|---|---|---|
| `retrieval_compose` | PASS 35 verified, [20261117T032018Z-prove](../../../Verus_verification/results/retrieval_compose/20261117T032018Z-prove/receipt.json) | 15 of 15 EXPECTED_FAIL, `results/retrieval_compose/20261117T032026Z` … `20261117T032116Z-control-*`; whole-file errors = named count for every control | AGREES 45 cases, 15 of 15 mutations detected, tamper detected, [20261117T032153Z-binding](../../../Verus_verification/results/retrieval_compose/20261117T032153Z-binding/receipt.json) |
| `ivf_entries` | PASS 19 verified, [20261117T032405Z-prove](../../../Verus_verification/results/ivf_entries/20261117T032405Z-prove/receipt.json) | 7 of 7 EXPECTED_FAIL, `results/ivf_entries/20261117T032407Z` … `20261117T032417Z-control-*`; whole-file errors = named count | AGREES 9 cases, 7 of 7 mutations detected, tamper detected, [20261117T032444Z-binding](../../../Verus_verification/results/ivf_entries/20261117T032444Z-binding/receipt.json) |

Kept failing or superseded runs:
- `retrieval_compose/20261117T031839Z-prove` UNEXPECTED: 36 verified against the old expected 28.
- `031846Z-prove` PASS 36, a first draft.
- `031851Z`…`031939Z-control-*`: the first suite. `seeds-capped` was FAIL_ELSEWHERE there because the claim sat in a helper lemma; `edges-among-answered` failed 5 against 4 named because `theorem_filled_cap_expands_only_first_node` also fails under the repair, which is honest and is now named.
- `032006Z-prove`: a rerun on an unchanged file after an edit script aborted.
- `ivf_entries/20261117T032300Z` and `032310Z-prove` UNEXPECTED: an incomplete arithmetic proof (one error each).
- `032319Z-prove`: 19 verified against the old expected count.
- `032325Z-prove` and `032327Z`…`032336Z-control-*`: the first suite. `cosine-takes-l2-branch` there had 3 errors for 1 named, as iteration 47's receipt `20261117T014837Z` already had (4 for 1). Both are now named, and the witness states its distances.
- The iteration-49 `guided-cap-max-nodes` receipts are kept as history.

## (d) Dispositions

- **Item 1 (bug-plt-113): accepted.** The cap is now the statement, not a defect; the departures are edges missing and seeds over the cap. Both are modeled from inputs (`admit`, `expand_frontier`, `lists_edge` against `rule_lists_edge` and `rule_within_cap`), reproduced on the fixture and bound (`guided_more`). The wrong control `guided-cap-max-nodes` was withdrawn and replaced by `edges-among-answered`, `seeds-capped` (repairs), `expand-whole-frontier-at-cap` and `guided-cap-top-k-only` (effects). The claim is scoped to the ObjectScript `SubgraphJson` path; the Arno path is a `cites` locator. Severity stays High (reasons in the entry).
- **Item 4, `truncate_first`: accepted, modeled.** The constant is removed; `answered` transcribes `list(set(...))[:k]` and `rule_answered` is the ranked alternative. `sort-before-truncate` now edits the transcription, still EXPECTED_FAIL with 1 error. Row 703 stays active.
- **Item 4, `IVFIndex.Build` metric: accepted, modeled (m8).** The model now has the cell choice that reads Build's centroids and records; row 642 moves from `entry_score` to `theorem_cosine_reinsert_changes_cell` (still `models`). No locator-only downgrade is needed.
- **Item 4, `PyOps.getDefaultDimension`: no change.** Its whole body returns 768, and `pyops_expected` transcribes that constant at the reader that consumes it (`theorem_unrouted_rest_search_refuses_width`). The reviewer classed it "directly constrained (a constant)"; it stays active.
- **m8: accepted.** The ontology now says what each operation does: search and insert pick cells by the metric branch, and the build clusters by distance whatever the metric. Cell assignment is modeled (`build_cell`, `insert_cell`) with a general l2 neighbor, a cosine witness and control `insert-by-distance`, and bound (`cell_cosine`, `cell_dot`, `cell_l2`). The observed consequence is a new trigger of bug-srch-107.
- **m9, IVF/retrieval part: accepted.** Now general (every input):
  - `theorem_equal_lengths_agree`, stated over the dot order so it is independent of the cosine-branch controls; the old example is kept as `theorem_equal_lengths_witness`.
  - `theorem_capped_subgraph_lists_edge_to_unlisted_node`.
  - `theorem_guided_cap_is_ppr_top_k`: min for every input.
  - `theorem_hybrid_c_zero_becomes_60`: every c.
  - New general theorems `theorem_filled_cap_expands_only_first_node` and `theorem_admitted_seeds_ignore_cap`.

  Still single examples, now labeled as witnesses in their doc comments: `theorem_guided_subgraph_drops_edges_among_top_nodes`, `theorem_guided_seeds_exceed_cap`, `theorem_last_hop_edges_missing` and `theorem_guided_uncapped_lists_all_edges`.

## (e) Owner blocks changed

- [algorithms.op.subgraph.guided](../../../ontology/features/algorithms.g5.md#algorithms.op.subgraph.guided):
  - The statement now gives the documented cap and the edges among the answered nodes.
  - The old cap bullet is replaced by two "Today" bullets (seeds over the cap; only the first node expanded) and a scope bullet (ObjectScript reader; Arno not checked).
  - Metadata: Sources (docstring lines, `execute_subgraph`), the Verus line (new names and controls), the provenance note (corrected after review 47-49 with links), and the Findings link text (new heading).
- [algorithms.op.subgraph](../../../ontology/features/algorithms.g5.md#algorithms.op.subgraph): Verus metadata only (new names and controls; Findings link text). The body is unchanged.
- [search.ivf.metric](../../../ontology/features/search.g5.md#search.ivf.metric):
  - The "when it picks cells" bullet is narrowed to search and insert.
  - New bullet: the build clusters by plain distance whatever the metric.
  - New "Today" bullet: a re-insert of an unchanged vector can change cell, linked to bug-srch-107.
  - Metadata: Sources (`ivf_build`'s k-means, `AddBatch`), the Verus line, the provenance note, and a bug-srch-107 Findings link.

`check_ontology.py`: 377 blocks, 0 issues, 17 writing warnings (unchanged). IDs and anchors unchanged.

## (f) Residual

- The Arno reader `SubgraphNativeJson` (and whether it has the same two departures) is unchecked. First missing step: a fixture with Arno loaded and the same star.
- In the model, the guided seed list (`dict.fromkeys(seeds + top_ids)`) is an explicit sequence in the witnesses. It is not derived from PPR scores, which stay provider inputs.
- `kg_SUBGRAPH` with `k_hops > 1` is modeled for one hop only; the binding covers two hops.
- The k-means labels are a provider premise: the Euclidean-nearest final centroid, observed for separated clusters. The binding's port takes centroids as cluster means under the observed labels and does not read the stored centroids.
- Search's choice of cells to probe (`nprobe < nlist`) is still inspected only.
