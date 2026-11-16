# Iteration 25: retest entry, reconciliation and the standalone BulkLoader

Retest of the consolidated uplift under the revised iteration and scoring guidance (hashes in
[retest-run.json](retest-run.json): `uplift-iteration.md` `a7521d0e…`, `uplift-scoring.md` `7e250023…`; both changed
since iteration 24). Start: immutable tag `cloud-iris-retest-start-20261116` = `ce5b2f7d`. Product `3eaa79cf` unchanged.
Native evidence only from the dedicated fixture `ivg-retest-20261116-iris` ([runtime.py](runtime.py),
[deployment](runtime.json)); the earlier cloud fixture and the neighboring experiments' containers were not touched.

## Reconciling the start

- Iteration 24's stop judgment is **reopened**. Its basis was "the five most recent workflows outside the vein agreed";
  the revised step 1 asks to start from members without an active behavioral binding and to investigate a large,
  little-linked subsystem even when the known panel is saturated. At the start 3,851 of 4,130 members (93%) had no
  active binding, including whole consequential modules with public outcomes (`bulk_loader.py` 18/18,
  `_write_txn.py` 20/20, `VecIndex.cls` 32/32, `TraversalBuild.cls` 38/38, `SqlProcs.cls` 36/36).
- The later commits are preserved as they are: viewer manifests/BINDINGS (`9448b6f4`, `61fe8112`), the refreshed
  question cards and scoped model bindings (`9c649ed9`) and the `design-verified` tags (`ce5b2f7d`).
- The gate failed at the start because two derived crosswalks did not reflect the question-card refresh: 75
  `statements.tsv` rows named question blocks that moved into `open_questions.md`, and 110 new question anchors had no
  `questions.tsv` row. Regenerated with `make_statements.py` (tested first in a disposable worktree: it only drops the
  75 moved IDs and adds `search.embedding.width.raw-helpers`) and [reconcile_question_cards.py](reconcile_question_cards.py)
  (appends 95 card-identity rows and 15 "moved from ontology child Q" rows; removes nothing). `make_crosswalk.py` was
  **not** run because it rewrites the registers and would overwrite the newer cards.

## Batch 1: W30, the standalone BulkLoader through its readers

Selected from the step-1 inventory (18/18 unbound; public case M23; both inherited findings "inconclusive regression
gap"; outside the recent comparison-operator family). Predictions frozen first in
[bulk-loader-PAIRS.md](bulk-loader-PAIRS.md), with the exposure that the loader source (not the readers) was read
during selection. All ten predictions held; none missed.

- **bug-plt-011 E2E reproduced** (Medium, restored to the live register from the audit archive): an interrupted
  `load_nodes` leaves its nodes without labels and properties, and the same call again reports zeros and adds nothing,
  also after a rebuild. Passing neighbor: a completed load re-run is idempotent.
- **bug-plt-106** (Medium, new entry for a previously recorded owner divergence from spec 252 FR-008): with the default
  `use_noindex=True`, `get_node`, Cypher and counts see nothing until `rebuild_all_indices`. Neighbors: indexed load,
  rebuilt load, `load_networkx`.
- Owner: [install.bulk_load.loader](../../../ontology/concepts/install.g5.md#install.bulk_load.loader) now states the
  phase order, re-run, visibility and graph-scope outcomes; [install.bulk_load.rebuild](../../../ontology/concepts/install.g5.md#install.bulk_load.rebuild)
  links the rebuild theorem. The superseded "Suspected divergence" sentence was replaced by the observed bullet.
- Formal: new [models/bulk_load](../../../Verus_verification/models/bulk_load/NOTES.md), 8 verified, 6 controls
  EXPECTED_FAIL (full and isolated; two first runs FAIL_ELSEWHERE kept, see NOTES), native binding AGREES 360
  comparisons over 72 histories with all six mutations detected.
- Not checked: bug-plt-012 (schema handling), `load_edges` endpoint registration and dedupe, the duplicate-or-refusal
  decision by error text.

## Recount

Active behavioral bindings 279 → **287** of 4,130 ([member-delta.json](member-delta.json)): 8 newly reached and bound
loader members (`load_nodes`, `_known_nodes_sql`, `_graph_predicate`, `_executemany_batched`, `_rollback`, `__init__`,
`rebuild_all_indices`, `_rebuild_indices`); 2 existing members gain a claim (`get_node`, `get_nodes` as the reader);
overlap 0; distinct additions 10; lost 0. Direct executable-body verification remains 0 (transcription with native
agreement).

## Next

Second candidate from the same inventory: writes inside a caller's transaction (`_write_txn.py` 20/20 unbound;
`structure.write`, open question `structure.write.engine-connection`), then a large unfamiliar ObjectScript module
(`VecIndex.cls` or `TraversalBuild.cls`).

## Correction after the seal (recorded in iteration 26)

bug-plt-106 duplicated the inherited entry bug-plt-027 ("BulkLoader's node and edge loads write without indexes and
return before rebuilding them", review round 3 R3-reader M6), which `structure.adjacency.bulk` already linked. The
evidence above now sits on bug-plt-027 (live, E2E reproduced, Medium); `bug-plt-106` remains as an alias anchor and a
crosswalk row marked duplicate. The A1 result is therefore a **repair of a known suspicion**, not a new discovery.
