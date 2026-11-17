# W58: operator reports — state → report → operator decision (frozen predictions)

Frozen 2026-11-17T04:10Z, **before** reading the deciding bodies of `iris_vector_graph/status.py` (every property and
`report`), `iris_vector_graph/_engine/admin.py` (`status`, `_status_schema`, `_status_probes`, `verify_sync`,
`_show_indexes`), `iris_vector_graph/_engine/ledger.py` (`_ledger_status`), `iris_vector_graph/engine.py`
(`capabilities`, `_detect_capabilities`), `iris_vector_graph/stores/iris_sql_store.py` (`capabilities`, `list_indexes`,
`server_info`), `iris_vector_graph/capabilities.py`, `iris_vector_graph/_engine/schema.py`
(`get_schema_visualization`, `sync`), `iris_vector_graph/_engine/snapshot.py` (`snapshot_info`), the reporter bodies
in `iris_vector_graph/cypher_api.py` (`get_schema`, `get_indexes`, `get_server_info`, `get_metrics`, `get_stats`) and
the `ivg status` / `ivg schema status` / `ivg indexes list` bodies in `iris_vector_graph/cli.py`.

Sources used: `docs/ADMIN_GUIDE.md` §7 "From Python" status table (L920-L960), §8 backup (L976-L985), §9 adjacency
(L1036-L1060), troubleshooting (L1270-L1280) and Arno (L660-L700); `docs/ADMIN_API.md` `/indexes`, `/server`,
`/metrics`, `/stats`, `/health` and the `ivg` command list (L100-L215, L390-L405); `docs/API_REFERENCE.md` entries
`capabilities`, `get_schema_visualization`, `snapshot_info`, `status`, `verify_sync`; `docs/USER_GUIDE.md` L270-L285
(caller transaction, `pending_sync`), L1160-L1210 (snapshot_info, status counts every graph); `README.md` L115-L125;
`CHANGELOG.md` (R010/R011 `kg_edge_count`, R103/R134/R165 index lists, R160 `hnsw_built`, R199, R207 "no ANN index",
R274 dropped `^NKG`, R284 store capabilities, R050 unknown, 4.6.0 graph-scope note L800-L806, spec 080 v1.63.3,
`verify_sync` v1.x L6145-L6156); method and class **docstrings only**, extracted with `ast.get_docstring` (bodies not
read); the owners [install.status](../../../ontology/concepts/install.g5.md#install.status),
[structure.adjacency.bulk](../../../ontology/features/graph-structure.g5.md#structure.adjacency.bulk),
[access.health](../../../ontology/concepts/access.g5.md#access.health),
[algorithms.routing](../../../ontology/features/algorithms.g5.md#algorithms.routing) and the open question
[HD-1703](../../../Verus_verification/open_questions.md#HD-1703). Test files were located by name and `grep` lines only;
no test body was read.

Prior knowledge carried in (agent findings, not product observation at this iteration): HD-1703 (store capabilities a
static catalogue), the verify_graph docstring's statement that `verify_sync` is one-directional and blind to deletion
drift, F-1713 (STATUS_PARTS omits two unknown parts), bug-plt-018 (capabilities name native algorithms that are not
routed), the design note that `graphoperators_deployed` probes a retired class. Where a document and a suspicion
disagree, the prediction follows the **document** and says so.

Fixture: `ivg-cont-20261117-iris`. Status counts **every graph of the namespace**, so the count and readiness cases run
in a **fresh namespace** `I52` created for this iteration (setup by `initialize_schema()`), never in `USER`, whose
earlier iterations' rows would decide the counts. Prefix `i52_`. Readers: the Python return value of the engine
method, `EngineStatus` fields and properties, `report()` text, the HTTP routes through FastAPI `TestClient` (no port
opened), and the CLI through `click.testing.CliRunner` where it can be pointed at that client.

## Readiness flags (`status()`), and agreement with the operation they announce

| ID | Case (changing input or history) | Neighbor | Predicted (source) |
|---|---|---|---|
| R1 | fresh namespace after setup, no edge | one `create_edge` in the default graph | ADMIN_GUIDE table ("`^KG` holds the adjacency and the graph has edges"): `ready_for_bfs` False → True; `adjacency.kg_edge_count` 0 → 1 = `rdf_edges` rows |
| R2 | the only edges are in a named graph `g` | the same edges in the default graph | status counts every graph (USER_GUIDE L1203): `ready_for_bfs` True in both; `tables.edges` 2 in both while `edge_count()` is 0 vs 2 |
| R3 | after `create_edge` only (no `sync()`) | after `sync()` | ADMIN_GUIDE §9 (`^NKG` is not kept from the rows): `adjacency.nkg_populated` False before sync on a fresh namespace, True after; `ready_for_multihop_bfs` (undocumented) follows `nkg_populated` (low confidence) |
| R4 | `ready_for_bfs` True with `^NKG` not built | the same after `sync()` | the flag announces "traversals work": a 1-hop `khop`/Cypher match answers the edge in both; an `^NKG` reader (`kg_PAGERANK`) answers `[]`-like empty before sync (ADMIN_GUIDE troubleshooting "Algorithms answer [] … ^NKG is not built") and scores after |
| R5 | `bulk_load_session` inside a caller transaction, committed | the same without a caller transaction | USER_GUIDE L280 / owner structure.adjacency.bulk: loading engine `pending_sync` True until `sync()`; a second engine reports False; without the caller transaction False |
| R6 | the R5 caller transaction rolled back | committed | owner: loading engine `pending_sync` stays True after the rollback (documented in the owner) |
| R7 | no embeddings | one vector in the default table `kg_NodeEmbeddings` | ADMIN_GUIDE ("the default embedding table holds vectors"): `ready_for_vector_search` False → True; `vector_index_state` "absent" → "empty" (no HNSW; CHANGELOG R207: report "no ANN index (1 vectors, searched by a scan)") |
| R8 | the only vectors are in a routed table (named graph route) | vectors in the default table | ADMIN_GUIDE literal: `ready_for_vector_search` False for the routed-only namespace although a width-checked search on that graph answers; `tables.node_embeddings` counts the routed rows (owner install.status) — so the count and the flag disagree (medium confidence on the flag) |
| R9 | no BM25 index | `bm25_build("i52", ["name"])` | ADMIN_GUIDE ("a BM25 index exists"): `ready_for_full_text` False → True; `fulltext_index_state` "absent" → "ready"; `indexes.bm25_indexes` lists the name; `bm25_search` answers after the build |
| R10 | the BM25 index dropped (`bm25_drop`) | kept | flag back to False, state "absent" |
| R11 | no edge embeddings | one `store_edge_embeddings` row | CHANGELOG spec 080: `ready_for_edge_search` False → True |
| R12 | `status(internals=True)` | `status(internals=False)` | API (`internals` parameter): readiness flags and counts are the same; only the `internals` field is filled with True |

## Sync report and counts

| ID | Case | Neighbor | Predicted (source) |
|---|---|---|---|
| S1 | `verify_sync()` after `create_edge` and `sync()` | the same after a second `create_edge` without sync | docstring: in sync → `in_sync` True, `bool(report)` True; then SQL (2) > `^NKG` edgeCount (1) → False/False; `to_dict()` holds the seven fields |
| S2 | `verify_sync()` on the same engine after `delete_node` of an edge's endpoint | a **second engine** asked the same | docstring: the deleting engine's `_nkg_dirty` → `in_sync` False, `pending_sync` True; a second engine: one-directional count (sql < global) → `in_sync` True (the documented blind spot) |
| S3 | `verify_sync(heal=True)` when drifted | `heal=False` | docstring: runs `sync()`; `healed` True; the report after heal says in sync (low confidence whether `in_sync` is re-read) |
| S4 | `tables.nodes`/`edges` with 2 nodes in default and 3 in `g` | `node_count()`, `node_count(graph="g")` | USER_GUIDE: tables 5; node_count 2 and 3 |
| S5 | `erase_graph("g")` / delete of a node | before | tables drop to the remaining rows; `adjacency.kg_edge_count` = `rdf_edges` rows (ADMIN_GUIDE table "equals") |
| S6 | `tables.labels` with one node holding two labels | one label | ADMIN_API: counts `rdf_labels` rows (2), not distinct labels |
| S7 | `status().ledger` with the ledger off | enabled and one commit | spec 213 FR-050: counters mirrored; off → state says off/disabled with head_seq None/0; on → `commits_ok` 1, `head_seq` 1 |

## Capabilities: catalogue vs live fact

| ID | Case | Neighbor | Predicted (source) |
|---|---|---|---|
| C1 | `engine.capabilities` read once, then `sync()` builds `^NKG` | a fresh engine after the sync | docstring ("Detected on first use, once"): the first engine keeps `nkg_built` False (stale) until reassigned; the fresh engine reports True |
| C2 | `store.capabilities()` in `I52` (classes deployed, Arno absent) | the same in a namespace without the Graph.KG classes (not created here; source only) | HD-1703: every algorithm True whatever is deployed; `*_arno` False here |
| C3 | `capabilities.graphoperators_deployed` after a full setup | — | design note (retired class): False on a complete install |
| C4 | `status().acceleration_label` with Arno absent | `IVG_DISABLE_ARNO=1` | ADMIN_GUIDE: "ObjectScript (Arno not loaded)" vs "ObjectScript (Arno disabled: IVG_DISABLE_ARNO=1)", `arno.lib_path` None under the switch |

## Snapshot info vs restore

| ID | Case | Neighbor | Predicted (source) |
|---|---|---|---|
| N1 | `snapshot_info(path)` of an archive saved from `I52` (default + named graph) | `status().tables` at save time | docstring: `tables` maps table → rows; its `nodes` and `rdf_edges` equal the namespace-wide counts; `version` is the IVG version, `layout` the storage layout, `globals` names the non-empty globals only (ADMIN_GUIDE §8: "a global that is empty is not written") |
| N2 | `restore_snapshot(path)` (replacing) after more writes | `snapshot_info` read before | status after restore equals what `snapshot_info.tables` said (nodes, edges) |
| N3 | `snapshot_info` on a ZIP without `metadata.json` | a valid archive | docs silent; predicted to raise (KeyError) rather than answer an empty dict (low confidence) |

## HTTP and CLI readers of the same facts

| ID | Case | Neighbor | Predicted (source) |
|---|---|---|---|
| H1 | `GET /stats` with nodes in default (2) and `g` (3) | `GET /server` and `GET /metrics` | CHANGELOG 4.6.0 L805: `/stats` nodeCount 2 (default graph); `/server` `schema.nodes` and `ivg_nodes_total` 5 (from `status()`) — two readers disagree by design |
| H2 | `GET /indexes` before `sync()` | after | ADMIN_API: `nkg_adjacency` NOT_BUILT → ONLINE; `kg_adjacency` ONLINE; after `bm25_build` a `FULLTEXT(BM25)` row by name |
| H3 | `GET /server` `adjacency` | `status().adjacency` | ADMIN_API ("part of engine.status()"): the same `kg_populated`, `nkg_populated`, `bfs_path` |
| H4 | `GET /metrics` `ivg_nkg_populated` | `status().adjacency.nkg_populated` | 0/1 equal to the status field |
| H5 | `ivg status` | `GET /server` | ADMIN_API: prints that answer |
| H6 | `ivg indexes list` | `GET /indexes` | prints those rows |
| H7 | `get_schema_visualization()` with label A on nodes in `g` only | label in default | docstring: across all graphs → A listed in both; properties sampled from one node |

Ranking by consequence: readiness flags vs the operation (R4, R7-R10: an operator skips or runs a rebuild), then
sync reports (S1-S3: `if not verify_sync(): sync()` is the documented usage), then capabilities (C1-C2: routing reads
them), then HTTP/CLI agreement (H1-H4: dashboards), then snapshot info.
