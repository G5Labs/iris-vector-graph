# Iteration 52: operator reports (W58)

Before image: `6c0dd694` (seal 51 `c20a8892` plus the master's inventory commit). Product `3eaa79cf` is unchanged:
nothing outside `.g5/` changed in this iteration (`git diff 6c0dd694 -- . ':!.g5'` is empty; `check_consolidated.py`
confinement PASS).

Native evidence comes only from `ivg-cont-20261117-iris`. Status counts every graph of a namespace, so the work ran in
two fresh namespaces created from `%SYS` for this iteration:
- `I52` for the probe, prefix `i52_`;
- `I52B` for the binding, which drops and re-creates it on each run, prefix `i52b_`.

No other namespace was written. Guidance: `Verus/uplift-iteration.md` `7c5f718a…` (unchanged). The question cards in
`open_questions.md` are unchanged; one evidence paragraph was added above the HD-1703 card. No quarantined material
(iteration-13 Cypher `MERGE`) and no evaluator-private input was read.

Predictions were frozen first ([reports-PAIRS.md](reports-PAIRS.md), commit `a9e96d5b`). They were taken from:
- ADMIN_GUIDE, ADMIN_API, the API reference, USER_GUIDE, README and CHANGELOG;
- docstrings extracted without bodies;
- the owners and HD-1703.

No test body was read. Only after that commit were the deciding bodies read: `status.py`, `AdminMixin.status`,
`_status_probes`, `verify_sync`, the capabilities code, the HTTP and CLI reporters, `snapshot_info`,
`get_schema_visualization`, `TraversalBuild`, `Adjacency.Put` and the bootstrap.

## Result

The operator reports now have a model whose every report comes from the modeled writer history: `operator_reports`,
with 34 verified and 17 controls, each failing in its named functions. A native binding in a re-created namespace
AGREES on 414 values, with all 17 mutations and the tampered observation detected. It found four new defects:

- **bug-plt-115 (Medium):** `status()` never counts a routed vector table on IRIS. A namespace whose vectors are all
  routed reads `node_embeddings` 0, `Vector index: absent` and not ready, and `/server` and `/metrics` say 0
  embeddings, while a search on that graph answers. The cause: the registry read's `SELECT DISTINCT` answers
  `KG_EMB_…` and the route test expects `kg_emb_…`. Proved for every name and registry. The iteration-13
  `routine_reporting` replay used local SQL, which keeps the case, so its routed-table correspondence is withdrawn at
  the IRIS reader.
- **bug-plt-116 (Medium):** once two graphs hold the same (s, p, o), `verify_sync()` reports drift after every `sync()`.
  `heal=True` answers healed and in sync, and the next check answers drift again. `^NKG` counts the shared triple once.
  Proved for every row list with a shared triple; the neighbor (unique triples, then in sync) is proved too.
- **bug-plt-117 (Low):** on a namespace set up while empty, `engine.capabilities.kg_built` and `.nkg_built` stay False
  in every new engine whatever is built. Only setup writes the markers, and only when edges exist. `sync()` sets
  `kg_built` in its own engine only. Personalized PageRank skips its ObjectScript path meanwhile. Re-running setup
  clears it.
- **bug-plt-118 (Low):** the schema diagram draws a relationship whose end has no label from or to the first label:
  "none" and label 0 share an id.

As built and owned, not registered as findings:
- The report's "Sync state" shows only this engine's flag. On a fresh namespace's first edges, and after a delete, it
  says "in sync" while `^NKG` is not built.
- `ready_for_multihop_bfs` does not need `^NKG`. Variable-length matches and PageRank answered without it.
- `/stats` counts the default graph while `/server` and `/metrics` count every graph.
- `snapshot_info`'s `version` is the archive format, "1.1".

## Predictions (33 frozen rows): 23 held, 6 partial, 2 missed, 2 not run

| Rows | Outcome |
|---|---|
| R1, R2, R5, R6, R7, R9, R10, R12, S3, S4, S5, S7, C3, C4, N2, N3, H1-H7 | held. S7 held in substance: `enable()` itself writes revision 1. C4: `lib_path` is "" rather than None. |
| R3 | partial: `nkg_populated` False before the first sync held; "multi-hop readiness follows `^NKG`" missed (True without it). |
| R4 | partial: k-hop and variable-length answers held; "PageRank answers empty before sync" missed (it scored). |
| R8 | partial: the flag is False as predicted, but because the count is 0, not because only the legacy table counts by design. **bug-plt-115.** |
| S1 | partial: in sync after sync held; "a second edge without sync drifts" missed (`Put` interns it once `^NKG` exists). |
| C2 | partial: every algorithm True held; the `*_arno` keys are absent rather than False. |
| N1 | partial: tables, layout and globals held; "`version` is the IVG version" missed ("1.1"). |
| S2 | missed: the deleting engine does not set its flag, and a second engine also reports drift (the Eraser drops `^NKG`, so the count is 0). The docstring's list of flagging paths is out of date. |
| C1 | missed: a fresh engine is as stale as the first one. **bug-plt-117.** |
| R11, S6 | not run. R11: the probe's edge-vector write used a wrong item key (`o` for `o_id`). S6: no node had two labels. |

Cases added after the source read (not frozen; kept as such):
- the shared triple and heal (bug-plt-116);
- the unlabeled endpoint (bug-plt-118);
- setup again from the syncing engine and from a fresh engine;
- bulk rows interned by `Put`;
- `IVG_DISABLE_ARNO=1`;
- `internals=True`.

Set aside:
- a failed count probe (readiness reads False, not unknown; `/metrics` would print 0);
- the refused-namespace path;
- HNSW on a routed table;
- Arno loaded (blocked: no library).

## Findings

| ID | Severity | Trigger → observable | Formal claim | Status |
|---|---|---|---|---|
| [bug-plt-115](../../../Verus_verification/bugs_issues.md#bug-plt-115) | Medium | routed vectors only → status 0, `absent`, not ready; search answers | `lemma_upper_never_route`, `theorem_routed_never_counted`, `theorem_routed_only_not_ready_but_searchable` | new, E2E |
| [bug-plt-116](../../../Verus_verification/bugs_issues.md#bug-plt-116) | Medium | a triple shared by two graphs → drift after every sync; heal says healed | `theorem_shared_triple_never_in_sync`, `theorem_heal_claims_in_sync_then_drift` | new, E2E |
| [bug-plt-117](../../../Verus_verification/bugs_issues.md#bug-plt-117) | Low | empty setup, load, sync → new engines read not built | `theorem_markers_never_set_after_empty_setup` | new, E2E |
| [bug-plt-118](../../../Verus_verification/bugs_issues.md#bug-plt-118) | Low | unlabeled endpoint → drawn at label 0 | `theorem_unlabeled_endpoint_is_first_label` | new, E2E |
| HD-1703 (question) | — | store capabilities a static catalogue | — | evidence added (additive); assumption unchanged |
| bug-plt-018, F-1713 (inherited) | — | — | — | unchanged: Arno absent here; STATUS_PARTS omission confirmed by source read only |

Simplifications: none proposed, tested or retired. Questions: none opened or resolved.

## Owners changed (`.g5/ontology/concepts/install.g5.md`)

- **New children of `install.status`:**
  - `.readiness`: what each flag reads, and that it should say whether the operation would answer;
  - `.sync`: the engine-local flag, `^NKG` before the first sync and after a delete;
  - `.verify_sync`: the documented use, the heal, the shared triple;
  - `.capabilities`: the markers, re-running setup, the store catalogue as a provisional assumption linked to HD-1703
    (`uncertain`);
  - `.readers`: `/server` and `/metrics` vs `/stats` and `/schema`, `/indexes`, the CLI;
  - `.diagram`.
- **New child of `install.snapshot`:** `.info`.
- **`install.status`:** one "Today" bullet (bug-plt-115) and a metadata note withdrawing the routed-table
  correspondence at the IRIS reader. The intent sentence is kept.
- **Definitions:** integer adjacency copy, pending-sync flag, routed vector table, readiness flag.

IDs are preserved. `check_ontology.py`: 389 blocks, 0 issues, 17 writing warnings (unchanged count).

Expected results come from the docs:
- the ADMIN_GUIDE field table;
- spec 230 FR-006 and the `_embedding_row_count` docstring;
- the `verify_sync` docstring's documented use;
- the API reference for capabilities;
- the diagram docstring.

None comes from a repair the builder prefers. Where the docs only describe as-built behavior (the sync line, `/stats`
scope), the owner states it as built.

## Model

| Model | Verified | Controls | Binding |
|---|---|---|---|
| `operator_reports` (new) | 34 ([receipt](../../../Verus_verification/results/operator_reports/20261117T042319Z-prove/receipt.json)) | 17 of 17 EXPECTED_FAIL | AGREES 414; 17/17 mutations and tamper detected ([receipt](../../../Verus_verification/results/operator_reports/20261117T042408Z-binding/receipt.json)) |

Every report is a function of the namespace state and the engine's own memory, and the state is built only by the
modeled writers. No decision is a constant premise. The theorems are general over every state, row list, registry
name, label list or action history:
- `theorem_markers_never_set_after_empty_setup` covers every history of eight action kinds.
- The routed-count claim covers every name.

Witness-style statements instantiate only the step order of a documented flow (fresh setup, then one edge), never
the answer.

Trust: no `assume`, `admit` or `external_body`; vstd only. Premises:
- P-COLLATE: IRIS `DISTINCT` answers the SQLUPPER form; observed in the same binding run.
- The adjacency index is declared.
- `KGEdgeCount` is below its cap.
- No writer races `sync()`.

Kept failures:
- `20261117T042222Z-binding` DISAGREES on 4 values. The first model said a bulk load in a caller transaction leaves
  `^NKG` alone, and that setup from the syncing engine skips the bootstrap. The source shows `RowPut` → `Put`, and that
  setup replaces the cached capabilities first. The model was corrected, the `setup-ignores-engine-cache` control
  withdrawn and `setup-skips-bootstrap` added.
- The first prove/control receipts (31 verified, 16 controls) are of that model.

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings **537 → 563**: 26 newly reached and bound, 10 strengthened, overlap 0, lost 0 (36 distinct
additions). No newly reached member had a locator before.

**Newly reached and bound:**
- `status.py`: `EngineStatus.ready_for_bfs`, `.ready_for_multihop_bfs`, `.ready_for_vector_search`,
  `.ready_for_full_text`, `.vector_index_state` and `SyncReport.__bool__`.
- `_engine/admin.py`: `AdminMixin.verify_sync`.
- `_engine/schema.py`: `sync`, `_sync_kg`, `_sync_nkg` and `get_schema_visualization`.
- `_engine/snapshot.py`: `snapshot_info`.
- `_engine/nodes_edges.py`: `bulk_load_session`.
- `engine.py`: `_detect_capabilities`.
- `schema.py`: `check_objectscript_classes` and `bootstrap_kg_global`.
- `cypher_api.py`: `get_server_info`, `get_metrics` and `get_stats`.
- `Adjacency.cls`: `Put` and `RowPut`.
- `TraversalBuild.cls`: `BuildNKG`, `RewritePass`, `NKGEdgeCount`, `NKGPopulated` and `KGEdgeCount`.

**Strengthened:**
- `AdminMixin.status`, `_status_probes`, `_embedding_tables` and `_embedding_row_count` (the IRIS reader now modeled);
- `EngineStatus.report` (the sync line);
- `security.is_routed_embedding_table`;
- `delete_node`, `get_node_count`, `initialize_schema` and `save_snapshot`.

**Delegates (justified in `decision-links.tsv`):** `cli.py::status` and `::schema_status`, which print the HTTP answer
unchanged, and `EngineStatus.fulltext_index_state`, the same predicate as `ready_for_full_text`.

**Excluded or unassessed:**
- Trivial: the dataclass containers, `to_dict` and `__str__`.
- Not registered: `IRISGraphEngine.capabilities`, ambiguous at the pin (property and setter);
  `_detect_capabilities` carries the binding.
- Probe only: `acceleration_state` and `acceleration_label`, `_ledger_status`, `IRISGraphStore.capabilities`,
  `_show_indexes`, `get_indexes`, `get_schema` and `cli indexes_list`.
- Unassessed: `ready_for_edge_search` and `_status_schema` (the refused path).

`status.py` is now 7 of 22 bound, up from 1.

**Material predictions changed:**
- Gained:
  - routed vectors read absent and not ready;
  - verify_sync never clears a shared triple, and heal contradicts the next check;
  - capabilities stay "not built" after an empty setup;
  - multi-hop readiness and PageRank do not need `^NKG`;
  - `Put` keeps `^NKG` current after the first sync;
  - a delete drops `^NKG` and clears the flag;
  - re-running setup sets the markers from any engine;
  - snapshot `version` is "1.1".
- Withdrawn: the iteration-13 routed-count correspondence at the IRIS reader (`routine_reporting` remains valid on
  its local-SQL frame).

## Correspondence

The [delta from 51](correspondence-delta-from-51.json) is STALE_ALL for proof and for correspondence. The changed
files are the new model, its binding, the crosswalk and the families. No product file changed. A fresh
[stamp](correspondence-inputs.json) checks as REUSABLE_INPUTS.

## Checks

- `check_ontology.py`: 0 issues, 17 warnings (unchanged).
- `check_findings.py` (`verification_root=.g5/Verus_verification`, previous = `6c0dd694`'s pair): no problems.
- `check_evidence.py`: FRESH, including `operator_reports` with 34 verified and 17 controls.
- `check_consolidated.py` (G5_GUIDE set): PASS. The first run failed because the ambiguous
  `IRISGraphEngine.capabilities` row did not resolve; the row was removed.
- Product diff vs pin: no change outside `.g5/` in this iteration. `git diff --check` is clean.
- `link_verification.py`: not applicable (no TLA models).

## Limitations

- **Edge routes and HNSW:** routed edge tables (`kg_eemb_`) and HNSW on a routed table are predicted by the same source
  line but not observed.
- **Multigraph:** the parallel-edge variant of bug-plt-116 was not run.
- **Failed probes:** readiness after a failed probe (a refused count reads 0, so the flags read False, not unknown;
  `/metrics` would print 0 as a number) is a source reading only.
- **Arno:** absent, so the acceleration label and `ready_for_multihop_bfs`'s Arno branch, bug-plt-018 and the store's
  `*_arno` keys cannot be checked here.
- **Repair proposals:** none was run on the product; the controls check the model's direction only.
- **Concurrency:** `sync()` racing writers is a premise, not modeled.
- **Review:** this iteration was not independently reviewed.
- **Fixture state:** the namespaces `I52` and `I52B` remain in the fixture (dedicated container).

## Residual list (first missing step for each)

- **Routed edge vectors:** `store_edge_embeddings([{"s","p","o_id","embedding"}], graph=g)`, then read
  `status().tables.edge_embeddings` and `ready_for_edge_search`. bug-plt-115 predicts 0 and False.
- **Multigraph:** `set_multigraph(g, True)`, two parallel edges, `sync()`, `verify_sync()`. The source predicts drift.
- **Failed probe:** a role without SELECT on `Graph_KG.nodes` in `I52`. Compare `report()` ("unknown"), the readiness
  flags (False) and `/metrics` (`ivg_nodes_total 0`) with the install.status rule against invented zeros.
- **Refused namespace:** `_status_schema`, plus F-1713 (`STATUS_PARTS` lacks `routines` and `adjacency`). First step: a
  namespace with a 4.5.x leftover, then `status()`.
- **`/indexes` and the CLI `indexes list`:** add `show_indexes` rows (`NOT_BUILT`/`ONLINE` from `NKGPopulated` and
  `KGEdgeCount`, BM25 names) to `operator_reports`. They are observed already.
- **`LedgerStatus` vs `ledger.stats()`:** compare after commits, a rejected commit and `verify()`.

Carried: the iteration-51 residual list and the consolidated queue.

## Cost

About 30 minutes of builder wall clock (04:02 to about 04:33 UTC). Tokens and currency are not available to the
builder.
