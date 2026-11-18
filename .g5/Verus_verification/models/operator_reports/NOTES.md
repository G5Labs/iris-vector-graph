# operator_reports — operator reports (W58, iteration 52; extended in iteration 53)

Product pin `3eaa79cf`. Root [operator_reports.rs](operator_reports.rs), controls in [model.json](model.json), native
binding [binding.py](binding.py). Frozen predictions: [reports-PAIRS.md](../../../uplift/consolidated/iteration-52/reports-PAIRS.md)
(committed before the deciding source was read). Raw probe: [reports_probe.py](../../../uplift/consolidated/iteration-52/reports_probe.py)
in namespace `I52`. Owners: [install.status](../../../ontology/operations/status-and-repair.g5.md#install.status) and its children
`.readiness`, `.sync`, `.verify_sync`, `.capabilities`, `.readers`, `.ledger` (iteration 53), `.diagram`, and
[install.snapshot.info](../../../ontology/operations/snapshots-and-bulk-load.g5.md#install.snapshot.info).

## Results (final candidate, iteration 53)

| Run | Result | Receipt |
|---|---|---|
| prove | PASS 48 verified, 0 errors | `results/operator_reports/20261117T045706Z-prove` |
| controls | 24 of 24 EXPECTED_FAIL, each in its named functions | `results/operator_reports/20261117T0457*-control-*` |
| binding | AGREES, 535 cases in namespace `I53B`, all 24 mutations detected, both tampered observations detected | `results/operator_reports/20261117T045659Z-binding` |

Iteration 52's final candidate (34 verified, 17 controls, binding AGREES 414 in `I52B`: `20261117T042319Z-prove`,
`20261117T0423*-control-*`, `20261117T042408Z-binding`) is kept; its receipts are of the earlier model.

Iteration 53 kept runs (not final):
- `20261117T045341Z-prove` (PASS 48) was made with a reformatted `model.json` (indent 1); the content was rewritten in
  the repository's indent before any other run.
- `20261117T045354Z-prove` and `20261117T0453*`/`T0454*` controls ran before the `edge-registry-keeps-case` attribution
  was corrected; `20261117T045439Z-control-edge-registry-keeps-case` is **FAIL_ELSEWHERE**: the change breaks
  `lemma_erouted_sum_zero`, on which the two named theorems rely, so they verify alone. The control now names the lemma
  (`20261117T045630Z` EXPECTED_FAIL), and the full suite was re-run on the final `model.json`.

Kept failures:
- `20261117T042222Z-binding` **DISAGREES** (4 mismatches), against the model as first written:
  - The model said a `bulk_load_session` in a caller transaction leaves `^NKG` alone. In fact each row goes through
    the declared adjacency index (`Adjacency.RowPut` → `Put`), which interns it when the `^NKG` skeleton exists.
    `bulk_ns` is now a fold of `create_edge`.
  - The model said setup run again from the engine that ran `sync()` skips the bootstrap, because that engine caches
    `kg_built` True. In fact setup first replaces the engine's capabilities with the deploy's fresh detection
    (`_engine/schema.py` 2583), so any engine's setup sets the markers once edges exist. The `setup_by` function, its
    theorem and its control `setup-ignores-engine-cache` were withdrawn. `theorem_setup_again_sets_markers` and the
    control `setup-skips-bootstrap` replace them.
- The first prove/control receipts (`20261117T041918Z`…`T041943Z`, 31 verified, 16 controls) are of that first model.

## Iteration 53: failed probes, edge vectors, the ledger line (independent review round 2: M2, M3, m7, m10)

Probe first: [failed_probe.py](../../../uplift/consolidated/iteration-53/reports/failed_probe.py) in the fresh namespace
`I53` ([raw](../../../uplift/consolidated/iteration-53/reports/failed-probe-20261117T044921Z.json)). A failed probe is
made honestly: IRIS users with the namespace's database and, for three of them, the Native API resources
(`%Native_GlobalAccess`, `%Native_ClassExecution`) through a role, holding SELECT on all, some or none of the IVG tables.

Added to the state: `label_rows`, `prop_rows` (count inputs), `edge_legacy`, `edge_routes`, `led` (the ledger's Meta and
counters). Added inputs: `Probes` (which probes the caller's privileges let succeed). `status(ns, eng)` is now
`status_p(ns, eng, all_ok())`, so every iteration-52 claim holds unchanged for a caller whose probes all succeed.

| Spec function | Source | Role |
|---|---|---|
| `status_p`, `unknown_of` | `_engine/admin.py` 449-476 (`_count`'s 0 and its part, `_failed`), 480-583 (native probes) | reader: a failed SQL count answers 0; only nodes/edges name a part (`graph`), the node-vector count names `vector_index`; labels, props and edge vectors name none |
| `ledger_line` | `_engine/ledger.py` 39-67; `ledger/client.py` 542-575 | reader: Meta failure → unknown; a failed `ledger_stats` SELECT is caught inside `stats()`, which answers zeros |
| `ledger_enable`, `ledger_commit`, `ledger_reject` | `GraphLedger.enable`, `commit` (observed counters) | writers: genesis is commit 1; a refused commit adds a rejection |
| `is_eroute`, `ecounted`, `erouted_sum` | `security.py` (`is_routed_edge_embedding_table`), `_engine/admin.py` 305-376 with `kind='edge'` | decision: the same case-sensitive test on the DISTINCT text (bug-plt-115) |
| `store_edge_routed`, `store_edge_legacy`, `annotate` | `store_edge_embeddings` (`_engine/embeddings.py` 1207-1290) | writers |
| `server`, `metrics`, `graph_line`, `ready_for_edge_search` | `cypher_api.py` 498-554; `status.py` 192-214, 216-232 | readers: `/server` keeps errors but not `unknown`; `/metrics` neither |

New claims (general unless shown):
- `theorem_failed_census_unknown_only_in_report`: a failed nodes/edges count → `unknown` names graph and the report says
  unknown, but `/metrics` and `/server` answer 0 and `ready_for_bfs` is False while `kg_populated` holds; with every
  probe succeeding the same namespace is ready (bug-plt-119).
- `theorem_failed_vector_count_reads_zero`; `theorem_failed_side_counts_silent` (labels, props, edge vectors name no
  part, and `ready_for_edge_search` reads False); neighbor `theorem_all_probes_ok_counts`.
- `lemma_upper_never_eroute`, `lemma_erouted_sum_zero`, `theorem_routed_edges_never_counted`,
  `theorem_routed_edges_only_not_ready_but_searchable`; neighbor `theorem_legacy_edge_vectors_ready` (bug-plt-115's
  edge trigger, review m7).
- `theorem_ledger_stats_failure_reads_zero` (bug-plt-120); neighbors `theorem_ledger_meta_failure_unknown` (the
  documented unknown path) and `theorem_ledger_counters_follow_commits`; witness of the binding's flow
  `theorem_enable_two_commits_one_reject`.

New controls (7): `metrics-marks-unknown` and `readiness-unknown-not-false` (repair directions of bug-plt-119),
`failed-count-not-zero` (guard: `_count`'s 0), `side-count-marks-unknown` (effect), `edge-registry-keeps-case` (repair
direction, edge trigger of bug-plt-115), `ledger-read-reported` (repair direction of bug-plt-120), `meta-failure-silent`
(guard). `registry-keeps-case` now also names `lemma_upper_never_eroute` (the same provider premise).

Premise added: the probe failures are inputs (`Probes`) chosen by the caller's privileges; which SQL statement a
privilege covers is observed, not modeled. `kg_predicates_consistent` (a conjunct of `ready_for_multihop_bfs`, review
m10) is not modeled: the model's adjacency is consistent by premise, and the owner now names the conjunct.

## What is modeled

State `Ns` holds the namespace facts every reader consults:
- the edge rows (unique on graph, s, p, o) and the node rows' graphs;
- the `^NKG` skeleton, dictionary, interned triples and `edgeCount`;
- the two `Graph.KG.Meta` markers;
- the legacy vector rows and the routed tables (registry name, graph, rows);
- the HNSW flag and the BM25 index names.

`Eng` holds one engine's memory: its pending-sync flag and its cached capabilities. Every report is computed from
`Ns` and `Eng`, and `Ns` comes only from the modeled writers. No decision is supplied as an input.

| Spec function | Source | Role |
|---|---|---|
| `setup`, `fresh_setup` | `schema.py` 3309-3358 `bootstrap_kg_global`; observed: no `^NKG` skeleton on an empty namespace | writer: markers only with edge rows |
| `create_edge` | row insert + declared index; `Adjacency.cls` 80-108 `Put` | writer: interns only with the skeleton; `edgeCount` +1 only for a new merged triple |
| `sync_ns`, `sync_eng` | `_engine/schema.py` 2859-2911; `TraversalBuild.cls` 288-373 | writer: `^NKG` from every graph merged on (s, p, o), `edgeCount` = distinct triples (`ndistinct`); the engine's flag cleared, its `kg_built` set |
| `delete_ns` | `nodes_edges.py` 2227-2267 (Eraser), 1518-1520 | writer: rows go, `^NKG` dropped, flag cleared |
| `bulk_ns`, `bulk_eng` | `nodes_edges.py` 370 `bulk_load_session`; `Adjacency.RowPut` 477-488 | writer: rows through the index; the loading engine's flag set |
| `store_routed`, `store_legacy`, `bm25_build`, `bm25_drop` | `store_embeddings`, `bm25_build`, `bm25_drop` | writers |
| `registry_text` | provider P-COLLATE | `SELECT DISTINCT table_name` answers the upper-cased name |
| `is_route`, `counted`, `routed_sum` | `security.py` 47, 58-69; `_engine/admin.py` 305-376 | decision: a case-sensitive name test on the DISTINCT text |
| `status` and `ready_for_*`, `vector_state`, `sync_line` | `_engine/admin.py` 439-703; `status.py` 159-222 | readers |
| `verify`, `verify_heal` | `_engine/admin.py` 756-848 | reader: rows > `edgeCount` or flag → drift; heal stamps in sync |
| `detect`, `caps_of` | `engine.py` 1742-1814; `schema.py` 2782-2850 | reader: markers, detected once per engine |
| `server`, `metrics_nkg`, `stats_nodes`, `count_in` | `cypher_api.py` 498-568; `_engine/schema.py` 454-497 | readers |
| `label_id` | `_engine/schema.py` 2772-2856 | reader: an unlabeled end gets 0 |
| `info_of`, `restore` | `_engine/snapshot.py` 835-1074 | reader and replacing restore (rows and nodes) |

## Claims

General over every state, row list, registry, label list or action history unless a premise is shown:
- `theorem_shared_triple_never_in_sync`: two rows share (s, p, o) → after `sync()` verify_sync reports drift on every
  engine (`lemma_ndistinct_lt`). Neighbor `theorem_unique_triples_in_sync_after_sync`.
- `theorem_heal_claims_in_sync_then_drift`: on a synced namespace with a shared triple, heal answers `in_sync` and
  `healed`, and the next check, on any engine, answers drift.
- `theorem_fresh_namespace_edges_skip_nkg`: after setup on an empty namespace and one edge, the report shows ready for
  BFS and multi-hop BFS, "in sync" and `^NKG` not built, while verify_sync reports drift. Neighbor
  `theorem_put_after_sync_counted`.
- `theorem_delete_status_vs_verify`: after a delete that leaves rows, both engines' reports say "in sync" and `^NKG`
  not built, and both verify_syncs say drift.
- `theorem_bulk_pending_is_engine_local`: only the loading engine reports pending sync.
- `lemma_upper_never_route`, `theorem_routed_never_counted`: for every name, the DISTINCT text never passes the name
  test, so `node_embeddings` equals the legacy rows whatever the registry holds.
- `theorem_routed_only_not_ready_but_searchable`: routed vectors only → not ready, `absent`, `/server` embeddings 0,
  while the route's reader has rows. Neighbor `theorem_legacy_vectors_ready` (ready, `empty`).
- `theorem_ready_for_bfs_iff_rows`; `theorem_full_text_follows_index`.
- `theorem_markers_never_set_after_empty_setup`: after any history of writes, syncs, deletes, loads, vectors and BM25
  builds from an empty setup, a detecting engine reads `kg_built` and `nkg_built` False; the syncing engine holds
  `kg_built` True in its own cache and `nkg_built` False. Neighbors: `theorem_setup_again_sets_markers` and
  `theorem_setup_with_edges_sets_markers`.
- `theorem_stats_default_vs_server_every_graph`, `theorem_server_and_metrics_project_status`.
- `theorem_unlabeled_endpoint_is_first_label`; `theorem_snapshot_info_matches_restore`.

## Controls (17)

Each control changes one guard, effect or decision; see `model.json`. Repair directions are checked in the model only,
not on the product:
- `registry-keeps-case` (bug-plt-115);
- `verify-counts-distinct-rows`, `nkg-per-graph` and `heal-rereads` (bug-plt-116);
- `sync-sets-markers` (bug-plt-117);
- `viz-none-distinct` (bug-plt-118).

Documented alternative readings:
- `multihop-needs-nkg` (ADMIN_GUIDE "the algorithms need it");
- `status-pending-reads-nkg`;
- `stats-every-graph` (pre-4.6.0).

The rest remove an effect or guard:
- `setup-inits-skeleton` and `put-always-interns`;
- `setup-marks-empty` and `setup-skips-bootstrap`;
- `engine-cache-unchanged` and `bulk-leaves-flag`;
- `delete-keeps-nkg` and `drop-keeps-index`.

## Binding

Iteration 53: `binding.py` now drops and re-creates namespace `I53B` (prefix `i53b_`); `I52B` is left as iteration 52
left it. After the iteration-52 history it adds three steps and compares 535 values:
- `s17`: routed edge vectors in a named graph (0 counted, not ready, the edge search answers), then a legacy edge
  vector (ready);
- `s18`: `ledger.enable()`, two commits and a commit refused for a stale head (`StaleHeadError`): head seq 3, 3 commits,
  1 rejection on every reader;
- `s19`: the same moment read by four users created in `%SYS` for the run and dropped after it (role `i53_brole`;
  users `i53_bmon`, `i53_bnative`, `i53_bpart`, `i53_bnoledger`): status counts, modeled `unknown` parts, ledger line,
  readiness flags, `/server` and `/metrics`. Expected answers come from `status_p` with each user's `Probes`.
Producer inputs added: the routed edge table's name and the `rdf_labels`/`rdf_props` row counts as `_SYSTEM` reads them.
A second tampered observation (the no-ledger user's line set to unknown) is detected. Recorded but not compared:
`ivg status` exits 0 for every user, with 15, 5, 3 and 1 probe errors.

Iteration 52's binding dropped and re-created namespace `I52B` from `%SYS`, in `ivg-cont-20261117-iris` only. It runs one history
through the public API on the pin, and the same history through a Python port of this model's writers and readers. Then
it compares 414 values after 17 steps:
- status fields and flags, and the report's sync line;
- verify_sync, with and without heal;
- a fresh engine's and the calling engine's capabilities;
- `/server`, `/metrics` and `/stats`, through FastAPI `TestClient`;
- the schema diagram's label ids;
- snapshot info and status after a replacing restore.

Producer values taken from the product: the routed table's registry name (the writer's hash) and the diagram's sorted
label list. The provider premise P-COLLATE is observed in the same run: the registry holds `kg_emb_b758…`, and
`SELECT DISTINCT` answers `KG_EMB_B758…`. The tampered observation (verify after heal set to in sync) is detected.

## Premises and trust

- No `assume`, `admit` or `external_body`; vstd only.
- P-COLLATE: IRIS 2026.1 `SELECT DISTINCT` over a default-collation VARCHAR answers the SQLUPPER form. Observed, not
  proved; another collation or provider would change bug-plt-115's trigger.
- The adjacency index is declared (structure.adjacency.declared), so `^KG` holds exactly the rows. `KGEdgeCount` is
  below its 10000 cap.
- No concurrent writer during `sync()`: `RewritePass` counts Puts racing the sweep twice, which errs high.
- Classes deployed and no Arno library. The acceleration label, the Arno fields, `report(internals=True)`, the ledger
  status and `/indexes` are observed by the probe only.

## Not modeled

- `acceleration_state` and `acceleration_label`.
- The store's `capabilities()` catalogue (observed: every algorithm True, no Arno keys).
- `LedgerStatus`'s `strict`, `replays_idem` and verify fields; the per-kind rejection columns are summed.
- `kg_predicates_consistent` and the Arno branch of `ready_for_multihop_bfs` (premises: consistent, no Arno).
- `ivg status`'s exit code (0 with probe errors, observed) and `/indexes` states (an empty BM25 index is `ONLINE`,
  observed); `/indexes` failing whole on one `List()` error, `snapshot_info`'s raw errors and a heal after an
  indeterminate count are source readings only (review m8).
- The multigraph parallel-edge variant of bug-plt-116, which the source predicts but was not run.
