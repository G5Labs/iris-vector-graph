**Current pointer (continuation, 2026-11-17).** RUNNING. Latest seal: iteration 46 (W52, IVF index). The retest's convergence below is reopened product-wide under `uplift-iteration.md` `d31f5890`. Next candidate: chosen from the product-wide inventory in [the continuation section](#continuation-2026-11-17).

<a id="continuation-2026-11-17"></a>
## Continuation (2026-11-17, from `cloud-iris-continuation-start-20261117`)

Guidance: run copy `$G5_HARNESS`; `Verus/uplift-iteration.md` sha256 `d31f5890bbcae14699c6a37cef392ace2aeb0c0a74f2be5e2129f1ff1fecfa16` (changed from `a7521d0e`: steps 4-5 now return every finished family to the product-wide inventory, require a formal claim that rejects a probe-confirmed wrong outcome, and require a representative public workflow in each area that could still hold a consequential decision before convergence), `Verus/uplift-scoring.md` `7e250023ffaa55fc6c891f137ac54b8cecbc424f69add756a3e5e9d91736e233` ([continuation-run.json](iteration-36/continuation-run.json)). Product `3eaa79cf` unchanged; run-isolated fixture `ivg-cont-20261117-iris`.

| Iteration | Workflow (predictions frozen first) | Material outcome |
|---|---|---|
| [36](iteration-36/HANDOFF.md) | W42 embedding queue: both workers, default and named graph, provider vector/empty/failure | Medium bug-srch-103 (inherited source-only divergence, now reproduced), Medium bug-srch-104 (new); model `embed_queue`; 375 → 392 |
| [37](iteration-37/HANDOFF.md) | W43 k-hop and graph walk readers; client retry source binding | Low bug-str-103, Low bug-str-104 (new), question `algorithms.op.walks.rows`; model `walk_reader`; 392 → 407 |
| [38](iteration-38/HANDOFF.md) | W44 RDFS inference: materialize, create, retract | Medium bug-str-105, Low bug-str-106 (new), question `install.inference.assert_after`, owner `install.inference`; model `inference_rows`; 407 → 409 |
| [39](iteration-39/HANDOFF.md) | W45 SHACL validation | Medium bug-str-107, Low bug-str-108 (new), owner `install.shacl`; model `shacl_data`; 409 → 412 |
| [40](iteration-40/HANDOFF.md) | W46 SQL table mappings | Low bug-cyp-108, -109, -110 (new), question `fhir.sql_mapping.cache`, owner corrected; model `sql_mapping`; 412 → 423 |
| [41](iteration-41/HANDOFF.md) | W47 RDF import | Medium bug-str-109, -110, -111 (new), owner `install.import.rdf`; model `rdf_import`; 423 → 426 |
| [42](iteration-42/HANDOFF.md) | W48 one-hop retrieval operators | no finding (10 of 11); question `algorithms.op.neighbors.scope`, owner `algorithms.op.neighbors`; model `retrieval_scope`; 426 → 428 |
| [43](iteration-43/HANDOFF.md) | W49 bulk embedding (`embed_nodes`) | Low bug-srch-105, -106 (new), owner `search.embedding.bulk`; model `embed_selection`; 428 → 433 |
| [44](iteration-44/HANDOFF.md) | W50 PROV-O export | Medium bug-plt-110, Low bug-plt-109 (new), owner `install.export.prov`; model `prov_window`; 433 → 439 |
| [45](iteration-45/HANDOFF.md) | W51 RDF export from Cypher, namespace prefixes | Medium bug-plt-111, Low bug-plt-112 (new), owner `install.export.rdf.cypher`; model `cypher_export`; 439 → 441 |
| [46](iteration-46/HANDOFF.md) | W52 IVF index after its build | Medium bug-srch-107, Low bug-srch-108 (new), owner `search.ivf`; model `ivf_entries`; 441 → 448 |


### Residual queue and interim judgment (kept current)

Not converged. Every iteration of this continuation opened an area the earlier stops had not assessed, and nine of
eleven produced new findings (21 new, plus one inherited divergence registered; iteration 42 was the only clean one).
The frozen predictions taken from the docs mostly held; most findings came from reading the source after the freeze.
The diminishing-returns claim of the retest therefore held only for the families it examined.

Next candidates, ranked by consequence and tractability (each still unowned or unbound at the pin):

1. SQL procedures in `Graph.KG.SqlProcs` (36 members, 0 bound): `MatchEdges`, `DijkstraPath`, `kg_BM25`, `kg_IVF`,
   `Txn_Begin/End/Undo`, `Prop_Set` (SQL-callable surface; ledger records excluded).
2. `load_networkx` and `load_obo` imports (a variant of the W47 import rules; expected to repeat bug-str-109's class).
3. Operator reports: `status()`, `capabilities`, `get_schema_visualization`, `snapshot_info` (counts that guide action).
4. Temporal analytics readers (`get_edge_velocity`, `find_burst_nodes`, `get_bucket_groups`, `get_distinct_count`):
   owned (`temporal.stats`) with known divergences; no model.
5. Embedding identity maintenance (`reconcile_recorded_dimensions`, `adopt_embedding_identities`, `list_quarantine`,
   `place_quarantined`, `measure_route_recall`).
6. `kg_PPR_GUIDED_SUBGRAPH`, `kg_RERANK`, `kg_VECTOR_GRAPH_SEARCH`, `multi_vector_search` (retrieval composition).
7. The `ivg` CLI (32 members, 4 bound) and the HTTP admin routes beyond `/api/cypher`.

Still excluded or blocked as before: erasure, redaction and tenant removal (security-related); FHIR (external provider);
Cypher `MERGE` (quarantined subject); Arno/NKG (library absent); embedded in-IRIS execution and `IVG.CypherEngine`
(package not in the container's embedded Python; about one iteration to install offline); the 3.2.0 to 4.0.0
migrations (need a reconstructed 3.2.0 install; about one iteration).

Earlier pointer (superseded): **Current pointer (retest, 2026-11-16).** CONVERGED after iteration 35. Latest seal: the clean tip with subject `Record convergence of the retest` (its parent is the iteration-35 seal). Session: iterations 25-35 (W30-W41), 6 new findings (1 High, 1 Medium, 4 Low), 4 inherited suspicions reproduced, 8 new models, reach 279 → 375 of 4,130 (96 new, 10 strengthened, 0 lost). Cost: builder wall clock about 1 h 20 min (21:15-22:35 UTC; tokens/currency unavailable). Convergence basis: [below](#retest-convergence-2026-11-16).

<a id="retest-2026-11-16"></a>
## Retest (2026-11-16, from `cloud-iris-retest-start-20261116`)

Guidance: run copy `$G5_HARNESS`, `Verus/uplift-iteration.md` sha256 `a7521d0e208c34bdf84e83537c5ffd2acc52b7aeec9d730a2a53ee89013fc563`, `Verus/uplift-scoring.md` `7e250023ffaa55fc6c891f137ac54b8cecbc424f69add756a3e5e9d91736e233` ([retest-run.json](iteration-25/retest-run.json)). The cloud continuation's convergence below is reopened under the revised step 1 and step 5.

| Iteration | Workflow (predictions frozen first) | Material outcome |
|---|---|---|
| [25](iteration-25/HANDOFF.md) | start reconciliation; W30 standalone BulkLoader through `get_node`/Cypher | bug-plt-011 and bug-plt-027 e2e reproduced; model `bulk_load`; 279 → 287 |
| [26](iteration-26/HANDOFF.md) | W31 engine writes inside a caller's transaction, by engine kind and caller mode | High bug-tmp-102 (new), Low bug-plt-107; model `write_routing`; 287 → 305 |
| [27](iteration-27/HANDOFF.md) | W32 VecIndex lifecycle; correction of how owner predictions were read in 25-26 | owner `search.vecindex`; F-0608 VecIndex branch reproduced; Low bug-srch-101, bug-srch-102; model `vec_index`; 305 → 328 |
| [28](iteration-28/HANDOFF.md) | W33 algorithm options, engine method vs Cypher `CALL ivg.*` | all agree (negative result); ranges stated in `algorithms.op`; model `algo_options`; 328 → 349 |
| [29](iteration-29/HANDOFF.md) | W34 embedding inventory, engine report and `ivg embeddings inventory` | all agree (negative result); owner `search.routes.inventory`; model `embedding_inventory`; 349 → 357 |
| [30](iteration-30/HANDOFF.md) | W35 F-0608's PLAID branch | reproduced, scoped difference from IVF; owner `search.plaid`; model `plaid_index`; 357 → 364 |
| [31](iteration-31/HANDOFF.md) | W36 BulkLoader in a non-default IVG Schema; W37 bug-tmp-102's rule on batch and delete | bug-plt-012 reproduced; bug-tmp-102 widened; `bulk_load` and `write_routing` extended; 364 → 368 |
| [32](iteration-32/HANDOFF.md) | W38 one Cypher answer through three HTTP readers | Medium bug-plt-108 (new); model `http_rows`; 368 → 371 |
| [33](iteration-33/HANDOFF.md) | W39 node and edge updates and deletes | all agree (negative result); model `node_edge_update`; 371 → 375 |
| [34](iteration-34/HANDOFF.md) | W40 Python property readers over API-written values | Low bug-str-102 (new); HD-0201 evidence; owner `structure.node.read.properties`; 375 |
| [35](iteration-35/HANDOFF.md) | W41 `bulk_load_session` with and without a caller transaction | all agree (reader corrected); `structure.adjacency.bulk` extended; 375 |


<a id="retest-convergence-2026-11-16"></a>
## Retest convergence (2026-11-16)

Guidance: `$G5_HARNESS` run copy (byte-identical to `$HOME/.agents`): `Verus/uplift-iteration.md` sha256
`a7521d0e208c34bdf84e83537c5ffd2acc52b7aeec9d730a2a53ee89013fc563`, `Verus/uplift-scoring.md`
`7e250023ffaa55fc6c891f137ac54b8cecbc424f69add756a3e5e9d91736e233` (all hashes in
[retest-run.json](iteration-25/retest-run.json)). Start: tag `cloud-iris-retest-start-20261116` (`ce5b2f7d`); iteration
24's stop was reopened under the revised step 1. Product `3eaa79cf` unchanged throughout; nothing outside `.g5/`
changed; nothing was published. No private evaluator input or quarantined iteration-13 material was opened. The later
viewer, question-card and model-binding commits were preserved; two derived crosswalks were reconciled to them.

### Discoveries and repairs (matched by trigger and observable consequence)

| Kind | Entries |
|---|---|
| New, not recorded anywhere before | **High bug-tmp-102** (autocommit-off rollback splits temporal writes, batches and deletes from their structural side), **Medium bug-plt-108** (Neo4j HTTP routes silently cap answers at 1,000 rows), Low bug-plt-107 (guide misnames which `from_connect` calls escape a transaction), Low bug-srch-101 (VecIndex re-create reports count 0), Low bug-srch-102 (VecIndex insert docs), Low bug-str-102 (property readers return a boolean as "true") |
| Inherited suspicions now E2E reproduced | bug-plt-011 (interrupted bulk load), bug-plt-027 (default bulk load invisible until rebuild; bug-plt-106 merged into it), bug-plt-012 (BulkLoader ignores the IVG Schema), F-0608 VecIndex and PLAID branches (PLAID differs from IVF: stale vectors do not answer) |
| Corrections | iterations 25-26 had read owner predictions from metadata only (A1, T5, T8, T10 were in fact predicted by statement bodies); builder wall-clock estimates in pointers 25-33 were overstated; seal 31 carries iteration 32's first receipts |
| Questions | none opened or closed; evidence added to `structure.write.engine-connection` and HD-0201 |
| Simplifications | none proposed, tested or retired (55 unchanged) |

Registers: 170 live bug entries (160 at the start), 55 simplifications, 256 question anchors. Ontology 344 → 348 blocks:
new owners `search.vecindex`, `search.plaid`, `search.routes.inventory`, `structure.node.read.properties`; extended
`install.bulk_load.loader`, `structure.write`, `temporal.write`, `algorithms.op`, `access.surfaces`,
`structure.adjacency.bulk`. New models (each with full and isolated controls and a native or in-process binding):
`bulk_load`, `write_routing`, `vec_index`, `algo_options`, `embedding_inventory`, `plaid_index`, `http_rows`,
`node_edge_update`. Every sampled workflow, its frozen predictions, misses and set-asides are in the iterations' `*-PAIRS.md`.

### Reach ([session-retest-20261116-reach.json](session-retest-20261116-reach.json))

Active behavioral bindings 279 → **375** of 4130: 96 newly reached and bound, 10 existing members with an
added claim, overlap 0, lost 0. Direct executable-body verification remains 0.

| Area | Members | Bound at retest start | Bound now | Unbound |
|---|---:|---:|---:|---:|
| Cypher translator/parser | 996 | 29 | 33 | 963 |
| ObjectScript iris_src | 972 | 69 | 94 | 878 |
| engine mixins | 711 | 100 | 130 | 581 |
| ledger | 151 | 19 | 19 | 132 |
| migrations | 161 | 0 | 0 | 161 |
| other package modules | 955 | 55 | 90 | 865 |
| stores | 184 | 7 | 9 | 175 |

### Why the step-5 check now supports stopping

The last step-5 pair: the strongest remaining candidate (W40, API-written values through the Python property readers,
the counterpart of the vein that yielded seven findings in iterations 16-24) gave one Low type-presentation finding and
an already-open question; the outside-family workflow (W41, the engine's bulk session) agreed fully with its owners, as
did W39 (node and edge updates and deletes). Severity of new discoveries fell from High and Medium (W31, W38, both in a
transaction mode or final reader no iteration had examined) to Low and none. Further modeling in the examined families
(bulk loading, caller transactions, named vector indexes, option validation, reporting, HTTP readers, CRUD, property
readers) would add Low presentation variants that the owners now predict.

### Remaining areas, by reason

- Scope limits: erasure, ledger redaction and tenant removal (security-related), FHIR mapping (external provider),
  Cypher `MERGE` (quarantined iteration-13 subject), the sample API under `api/` and its GraphQL schema (`gql`).
- Blockers: Arno and NKG accelerators (library not installed; 61 ObjectScript members), embedded in-IRIS execution
  (`embedded.py`; needs the package inside the container's embedded Python, about one iteration), IRIS 2026.3 (F-C1705).
- Internals of modeled decisions: `TraversalBuild` sweeps and sketches (rebuilt-store token rule modeled), the Cypher
  translator and parser (TCK-covered for Cypher-written data; the API-writer boundary examined in 16-24), engine and
  store delegates, `store_protocol` (abstract), ledger client and replay delegates (ledger family modeled).
- Low yield for the cost: the 3.2.0 → 4.0.0 migrations (161 members; need a reconstructed 3.2.0 install, about one
  iteration; affect installs two major versions back) — the largest unknown, with that settling cost.

### Stop reasons, labeled

1. **Evidenced diminishing returns** (primary), limited to the families named above.
2. **Scope limits** and **blockers** as listed.
3. **Budget**: not binding.

### Honest limits

No independent reviewer ran. Bindings are transcriptions with native or in-process agreement; provider premises are
named in each model. Probe-only claims, open in Verus: bug-str-102 and W41. One detail is unexplained: a two-edge
temporal batch's window read returned one edge (W37; the binding uses one-edge batches). The run-isolated fixture
`ivg-retest-20261116-iris` (with namespaces `USER` and `W37`) was stopped, not removed: `docker start
ivg-retest-20261116-iris` restores it for every binding.

Earlier pointer (superseded): **Current pointer (cloud continuation, 2026-11-16).** CONVERGED after iteration 24. Latest seal: the clean tip with subject `Record convergence of the cloud continuation` (its parent `0575c5de` is the last iteration seal). Session: iterations 14–24, seven new findings, reach 249 → 279 of 4,130 (30 new, 0 lost). Cost: builder wall clock about 1 h 50 min (tokens/currency unavailable). Convergence basis: [below](#convergence-cloud-continuation-2026-11-16).

<a id="convergence-cloud-continuation-2026-11-16"></a>
## Convergence (cloud continuation, 2026-11-16)

Guidance: `$G5_HARNESS` run copy; `Verus/uplift-iteration.md` sha256
`af3f5f7200a0e8ebd5bb9e014b4f651c259a5bebad2924a37a039ad5b8acc7ed`, `Verus/uplift-scoring.md`
`f67cb9089aa6c8b03a56de79102908b5f3906a0391d74e6557456882da7328ec` (all hashes in
[iteration-14/cloud-run.json](iteration-14/cloud-run.json)). Start: tag `cloud-uplift-start-20261116` (`f32c1c4b`).
Product `3eaa79cf` unchanged throughout; nothing outside `.g5/` changed; nothing was published. No private evaluator
input or quarantined iteration-13 material was opened.

### What this session did

| Iteration | Workflow (predictions frozen first) | Material outcome |
|---|---|---|
| [14](iteration-14/HANDOFF.md) | completed the inherited RDF and NDJSON export packages on Linux; re-proved all 44 models and replayed all 499 controls after the toolchain change | four export owners now state their cases; 249 → 254 |
| [15](iteration-15/HANDOFF.md) | ADR-0009 temporal mark through NDJSON, RDF and Cypher readers | Low bug-tmp-101; new owner and question; model `temporal_marker`; 254 → 257 |
| [16](iteration-16/HANDOFF.md) | `WHERE` equality, node vs relationship | Medium bug-cyp-102 (stored integers equal booleans); model `typed_equality`; 257 → 264 |
| [17](iteration-17/HANDOFF.md) | equality on the native executor; ordering comparisons | native declines typed equality (no divergence); Medium bug-cyp-103 (relationship text orders as 0); 264 → 266 |
| [18](iteration-18/HANDOFF.md) | ORDER BY sort key; empty string under both executors | Medium bug-cyp-104 (executors order an empty string differently); model `sort_key`; 266 → 269 |
| [19](iteration-19/HANDOFF.md) | strongest candidate (16 native shapes) and setup lifecycle on a fresh namespace | both agree with owners; model `setup_record`; 269 → 272 |
| [20](iteration-20/HANDOFF.md) | null semantics; string predicates | nulls agree; Low bug-cyp-105; 272 → 273 |
| [21](iteration-21/HANDOFF.md) | variable-length multiplicity; adjacency rebuild | both agree; 273 |
| [22](iteration-22/HANDOFF.md) | BM25 build, incremental writes, scoring | all agree; model `bm25_counts`; 273 → 278 |
| [23](iteration-23/HANDOFF.md) | IN lists, min/max | Medium bug-cyp-106 (IN disagrees with =); 278 → 279 |
| [24](iteration-24/HANDOFF.md) | inline patterns and parameters; value functions | patterns fully predicted by owners; Low bug-cyp-107 (relationship coalesce returns text); 279 |

Every sampled workflow, its predictions, misses and set-asides are in the iteration's `*-PAIRS.md`. New formal claims:
`temporal_marker` (81), `typed_equality` (43), `sort_key` (52), `setup_record` (7), `bm25_counts` (7), plus the accepted
`rdf_reporting` (50) and `ndjson_export` (144); every model has full and isolated ordinary control failures and a
native or local-SQL binding. Reach by area and the 30 new members: [session-20261116-reach.json](session-20261116-reach.json).
Registers: 160 live bug entries (7 new, all e2e reproduced), 55 simplifications, 146 questions plus one new owner
question (`temporal.structural.mark.visibility`).

### Why the strongest remaining candidate does not justify another batch

The productive vein this session was the boundary where values written by the Python API are read by Cypher, which
the product's 100% openCypher TCK does not exercise (it writes through Cypher). Its comparison operators are now
owned and observed: `=`, `<>`, `<`/`>`, `STARTS WITH`, `IN` (literal and parameter), inline maps, parameters, `ORDER BY`,
`min`/`max`, nulls. In the last two iterations the owners predicted every W28 cell, and W29's one new item follows
from an existing owner clause (only marked relationship columns are decoded). Severity fell from Medium to Low. The
strongest remaining candidate is further value functions and list operators at the same boundary, at about 10–15
minutes per family. Expected yield: Low type-presentation variants that a reader can already predict from
`query.values.relationship_text`, `.equality` and the documented known issue. Further modeling there would not change
a material prediction.

### Why a different underserved workflow does not either

Five different workflows outside that vein were tested against frozen predictions and all agreed with their owners:
native-executor shapes, setup lifecycle (including resume and mismatch refusal), variable-length paths, adjacency
rebuild, and BM25 text search. The largest remaining unbound areas are, by reason:

- Scope limits: Cypher `MERGE` (adjacent to the quarantined iteration-13 investigation; not pursued), FHIR mapping
  (needs an external FHIR provider), ledger redaction and tenant removal (security-related, out of scope), Arno and NKG
  accelerators (the Arno library is not installed on the fixture).
- Low yield for the cost: the 3.2.0 → 4.0.0 migrations (161 members) need a reconstructed 3.2.0 install (about one
  iteration) and affect only installs two major versions back.

Unbound members by area at the end: Cypher translator/parser 967 of 996, ObjectScript 903 of 972, other package
modules 900 of 955, engine mixins 611 of 711, stores 177 of 184, migrations 161 of 161, ledger 132 of 151. Most are
delegates, DDL, validation shells or the excluded areas above. No sampled workflow from this session's survey points
to a consequential, tractable gap that would change a material prediction.

### Stop reasons, labeled

1. **Evidenced diminishing returns** (primary): the five most recent workflows outside the boundary vein agreed with
   owners; inside it, owners now predict new shapes and severity fell to Low.
2. **Scope limits**: quarantined iteration-13 subject, security-related workflows, external providers.
3. **Budget**: not binding.

### Honest limits

Direct executable-body verification remains 0; bindings are transcriptions with native or local-SQL agreement, and
provider premises are named in each model (IRIS SQL comparison, `JSON_VALUE` spelling, text-to-double cast,
`$IsValidNum`, `%ToJSON` spelling, executor transports, tokenization). Four inherited controls hit collateral resource
limits in full runs on the Linux toolchain and rest on their isolated failures ([control replay](iteration-14/control-replay.json)).
No independent reviewer ran in this session. The run-isolated fixture `ivg-cloud-20261116-iris` was stopped, not
removed; `docker start ivg-cloud-20261116-iris` restores it for native replays (namespaces USER and W21).


Older pointer, superseded: [iteration 11](iteration-11/HANDOFF.md), continuing into iteration 12.

# IVG consolidated uplift — handoff

**Historical continuation: iteration 3 (2026-11-15)** — [sealed handoff](iteration-3/HANDOFF.md), [retained sample and challenges](iteration-3/PAIRS.md), [coverage](../../Verus_verification/coverage.md#improvement-iteration-3-2026-11-15). Input `0af2a61d`; implementation checkpoint `6f32b507`; final seal is the clean tip with subject `Seal iteration 3 with corrected snapshot evidence and handoff`. Four new as-built families: **33 obligations / 19 named controls**, **164 upstream tests passed**, consolidated gate PASS. Corrects the inherited empty-deletion-prior inference while retaining a stronger range-prior witness. Named diff, global PageRank admission/self-loop producer, AQL frontend and vector threshold/results gain scoped contracts; full lifecycle/content and live IRIS correspondence remain open. This supersedes conflicting scope/count claims below without removing historical evidence.

**Prior continuation: iteration 2 (2026-11-15)** — [sealed handoff](iteration-2/HANDOFF.md), [controlled predictions and retained sample](iteration-2/PAIRS.md), [coverage](../../Verus_verification/coverage.md#improvement-iteration-2-2026-11-15). Input `d087503`; implementation checkpoint `c64c6dda`; final seal is the clean tip with subject `Seal iteration 2 with controlled predictions and review handoff`. Four new as-built families: **41 obligations / 22 named controls**, Python unit bindings with explicit provider limits, **314 upstream tests passed**, consolidated gate PASS. The new application model addresses M03's selected producer/failure boundary; full history/diff/restore and live ObjectScript correspondence remain open. This current handoff supersedes older scope/count claims below; all historical evidence is retained.

**Prior continuation: iteration 1 (2026-11-15)** — [sealed iteration handoff](iteration-1/HANDOFF.md), [controlled pairs](iteration-1/PAIRS.md), [current coverage](../../Verus_verification/coverage.md#improvement-iteration-1-2026-11-15). The clean `consolidated_uplift` tip with subject `Seal iteration 1 with scalar reader evidence and handoff` is the next-round input. New contracts: 35 obligations / 17 controls; final product suites: 383 passed / 4 skipped. Published M03/M21/J04 formal corrections remain partial. The sections below preserve checkpoint 0's original account and predictions; the current handoff and public feedback supersede conflicting scope/count claims (including the old 26-Python-definition figure).

Branch `consolidated_uplift`, product pin `3eaa79cf` (v4.7.0), from the guidance arm `24c6b0c0` with the playbook arm `2d59e578` imported verbatim. Assignment: `reviewed-plan.md` (2026-11-14). Nothing outside `.g5/` and the imported `experiment/playbook-*` trees changed; the product, `.agents/` and `experiment/g5-verus/` are byte-identical to their sources (gate check 1). Nothing was pushed or posted. No statement is `implementation-verified`: no product body is verified here.

## 1. Commits, environment, gate

| Commit | Content |
|---|---|
| `abfce8dd` | the playbook arm imported verbatim from `2d59e578`: `experiment/playbook-uplift` tree `becf53a4`, `experiment/playbook-completion` tree `a8fe7129` (3,335 files) |
| `36ed59dc` | tooling: `run_verus.py` copies each raw Verus log beside its receipt (additive); `tools/run_playbook_crate.py`; a scoped `.gitignore` re-including `results/` and `*.log` |
| `0bd0a68e` | WP0: [families.tsv](../../Verus_verification/families.tsv), [check_consolidated.py](../../Verus_verification/tools/check_consolidated.py), reruns of both arms (receipts with logs) |
| `3a44b8c0` | WP1 Tier 1 ontology lifts, the mechanical register crosswalk, contract A (window reader) |
| `bf33cd3d` | WP2 contracts B1 (freshness), B2 (embedded no-row), B3 (relationship text), D (index declaration); findings bug-adp-001, bug-cyp-101 |
| `41e33024` | statement crosswalk, sweep log, code links, leads L1/L2 settled (bug-led-101, q-con-001, q-con-002), upstream #12/#13 |
| final | coverage numbers, coverage map rows, reader self-check, runbook section, this handoff. The final commit is the tip of `consolidated_uplift` (`git log -1`) |

Environment (this Mac, arm64; no IRIS used): Verus `0.2026.10.04.426d8b0` at `~/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus`; `actors` from `~/.cache/g5-verification/ivg-actors-c03f9fa`; the pin exported to `$RUN_DIR/pin` with `uv sync --frozen --all-extras` (CPython 3.11.8); `RUN_DIR=$HOME/runs/ivg-consolidated-20261114`. Provenance: [SOURCE-consolidated.json](../../Verus_verification/SOURCE-consolidated.json). Copyable commands: [runbook, "On this machine"](../../Verus_verification/runbook.md#on-this-machine-consolidated-uplift-2026-11-14).

Gate: `python3 .g5/Verus_verification/tools/check_consolidated.py` → **PASS** at the final commit: product paths equal the pin (HEAD and working tree); `.agents` and `experiment/g5-verus` equal `24c6b0c0`; both imported trees hash as imported; no untracked file outside `.g5/`; the five inherited model roots, `model.json` files and `twin.rs` byte-identical; `check_evidence.py` FRESH (10 models incl. bindings, 40 native observations, 105 playbook rerun pairs); `check_ontology.py` 14 files, 0 issues, 0 warnings; `check_findings.py` no problems; all 113 + 19 + 56 guidance-arm register IDs still anchors; the four crosswalks complete; 52 code links each resolved to one definition at the pin and one `fn`.

## 2. Inherited results

| Arm | Re-run here and matched | Not re-run (why) |
|---|---|---|
| Guidance | 5 of 5 proofs at the recorded counts (ledger_redaction 41, graph_structure 67, temporal 113, search 56, platform 51) and **128 of 128 controls EXPECTED_FAIL** (`results/<model>/20261115T*`), about 15 minutes | twin build (its probe needs the VM's IRIS); 40 native observations (no IVG IRIS here; rule 3 also forbids repeating the security-relevant probes) |
| Playbook | 15 crate baselines at their recorded counts: proofs 88, breadth 94, pa3 108, d1b 92, d1c 111, d1d 118, d1e 115, d1f 115, d9 115, d9b 158, d9c 158, env 305, env2 433, mech 1,149, sys 256; uplift/proofs 53 (no RESULTS.json; count from MODELS.md). Controls of breadth (7), pa3 (9), d1b (11), d1c (10), d1d (21), d1e (15), d9c (16): **89 of 89 EXPECTED_FAIL at exactly the recorded error locations**. `actors` 121 verified each time | explorer crates (core and core-partition above 8 GB; the others inherited with registry records), simulator and contract lanes (need the VM's IRIS), proofs-mech's 120 and proofs-sys's 12 controls (time), proofs-stmt and lockplans (partial) |

Retained failures: two repeated playbook baselines that cargo took as up to date (no verdict; `playbook-proofs-pa3/20261115T040739Z-baseline`, `playbook-proofs-d9c/20261115T040807Z-baseline`; the tool now cleans the package); the first `index_declaration` control run where `skip-ekey-check` **survived** (a weak theorem, fixed); the first `embedded_no_data` binding (harness error, DISAGREES). Every family's status, design attribute and rerun: [families.tsv](../../Verus_verification/families.tsv) (40 families: 7 guidance, 28 playbook, 5 new).

## 3. Governing ontology

- **Tier 1 (all 13 rows)**: `ledger.commit` (M03), `temporal.window.sources` (M06, new), `temporal.window.paging` + new `.release` (M07, M08 incl. the empty middle page), new `structure.rebuilt.stamp` (M09), `structure.multigraph.count` (M11), new `algorithms.op.paths` / `.weighted` / `.direction` (M12), `search.embedding.width` + `search.routes.no_fallback` (M14), `install.bulk_load.loader` (M23), new `install.snapshot.routes` (J01) and `.temporal` (J02), new `structure.adjacency.declare` (M16, J07), a new [adapters page](../../ontology/concepts/adapters.g5.md) with `adapters.embedded` and `.no_data` (M17), new `query.values` / `.relationship_text` (M18). Each with `path::symbol` sources at pin lines, `Playbook:` statement IDs and a `Verus:` line.
- Model-supported rows reconciled: the owning blocks of M01, M02, M03, M10, M13, M21, J04, J05, J08 name the active family and its design (as-built or **reviewed**, with the control that reintroduces the pin's behavior).
- Root: an `adapters.` topic, a "Where the detailed statements are" map from every playbook module to pages, and a narrower "Not covered" (the engine read API outside Cypher and the exports still have no owning block).
- Tier 2: [ontology-sweep.tsv](../../Verus_verification/crosswalk/ontology-sweep.tsv). Swept row by row: the window reader (`TMP-B6.*`, 16 rows: 9 lifted incl. the reversed window, page bound and handle-per-connection; 5 already present; 2 deferred). **Not swept: 1,335 refusal or contrast rows** in the other modules (7 modules not touched at all). Statement crosswalk: [statements.tsv](../../Verus_verification/crosswalk/statements.tsv) (371 blocks; 27 extended from the playbook arm; 344 `g-only`, meaning not yet compared).
- Contradictions: none found between the arms' statements on the Tier 1 rows. Severity disagreements are kept in the merged register entries (bug-003 Medium vs S1; bug-tmp-002 High vs S2; bug-str-002 High vs S2).
- Removed text: none dropped. Rewordings: `temporal.window.paging`'s bullet "A reader is closed when the iteration ends or is abandoned" moved into its main sentence; the root's "Not covered" sentence "nothing else about them was recovered" replaced by a pointer to the playbook modules that state their behavior.
- Self-check from `.g5/ontology` alone: [reader-check.md](reader-check.md) (17 differing public cases answered).

## 4. New contracts (all under `.g5/Verus_verification/models/`)

| Model | Obligation (cases) | Theorems | Controls | Binding (Observed at unit level; server or database substituted) | Premises, trust |
|---|---|---|---|---|---|
| [temporal_window_reader](../../Verus_verification/models/temporal_window_reader/NOTES.md) | M06, M07, M08 | `theorem_spec_sources_omitted_vs_empty`, `theorem_server_filter_sources`, `theorem_yield_is_concat_to_done`, `theorem_exhaustion_frees_without_close`, `theorem_close_mid_read_once`, `theorem_failed_page_closes_once`, `theorem_server_full_page_nonempty` (16 verified) | 8 of 8 | real `window_spec` + `TemporalWindowCursor`, 640 + 45 cases, AGREES, 3/3 detection | the window ends; server half Inspected |
| [freshness_stamp](../../Verus_verification/models/freshness_stamp/NOTES.md) | M09 | `theorem_unstamped_stale_at_zero`, `theorem_stamped_zero_current`, `theorem_python_agrees_with_objectscript`, `theorem_stale_stores_exact` (7) | 4 of 4 | real `Freshness`, 1,795 cases, AGREES | canonical integer stamps; `TraversalKHop.Fresh` Inspected |
| [embedded_no_data](../../Verus_verification/models/embedded_no_data/NOTES.md) | M17 | `theorem_no_data_is_empty`, `theorem_no_data_on_every_path`, `theorem_other_error_raises`, `theorem_success_rowcount_unknown`, `theorem_batch_counts_rows`; witness `witness_ddtab_mid_batch_reruns_rows` (13) | 6 of 6 | real `EmbeddedCursor`, 64,000 cases, AGREES; rerun observed `[0, 0, 1]` | `iris.sql` substituted |
| [rel_prop_text](../../Verus_verification/models/rel_prop_text/NOTES.md) | M18 | `theorem_decode_classes`, `theorem_noncanonical_stays_text` (**reviewed** rule), `theorem_as_built_agrees_on_plain_ascii`; as-built witnesses (10) | 5 of 5 | real `parse_rel_prop_text` + `_decode_rel_prop_text_columns`, 1,139 texts, AGREES with as-built; 38 departures from the rule | `JSON_VALUE` round trip not observed |
| [index_declaration](../../Verus_verification/models/index_declaration/NOTES.md) | M16, J07 | `theorem_no_prereq_no_ddl`, `theorem_prereqs_declare_both`, `theorem_declared_left_alone`, `theorem_backfill_before_edge_index`, `theorem_plain_replaced`, `theorem_second_run_is_noop` (7) | 4 of 4 incl. the 4.7.0 plain-index defect | real `ensure_adjacency_index`, 216 states x 2 runs, AGREES | DDL effect inside IRIS not modeled |

Trust inventory of every new model: empty (no `assume`, `admit`, `external_body`); bundled `vstd` only; the harnesses' spec transcriptions are unverified Python. **Attempted and not built** (plan C, E, F): the history fold (compute_diff against reconstruct), restore-to-reader (J01, J02), writer paths into the id reader (#12) and the row-limit selector (#13); their blocks and coverage rows say "no formal contract" with what is missing.

## 5. Registers

Every guidance-arm entry kept (113 / 19 / 56). Crosswalk rows (one per source ID; [crosswalk/](../../Verus_verification/crosswalk/)): findings 442 = guidance 113 + playbook 313 audit records (298 own entries, 9 merged into guidance entries, 6 withdrawn: 2 refuted, 3 not reproduced, 1 duplicate) + 3 renumbered + 3 sub-case labels + 7 unfiled candidates + 3 new here; simplifications 56 = 19 + 36 root causes + HD-1301 merged into simp-001; questions 139 = 56 + 60 decisions (HD-1801 merged into q-plt-004) + REACH-1..5 + D-1..D-14 (inherited proof debt) + 4 new here; 104 errata in `evidence-errata.tsv`. Merges confirmed by trigger and effect: bug-001/F-1303, bug-002/F-C1201+F-C1301, bug-003/F-1304, bug-led-007/F-C1203+F-C1308, bug-srch-002/F-C0702, bug-tmp-002/F-0501, bug-str-002/F-0402, simp-001/HD-1301, q-plt-004/HD-1801. **Not yet compared** with the other arm: every other playbook entry (marked in its text).

New findings (discovered here, each Suspected end to end): **bug-adp-001** (Low) the embedded batch fallback reruns rows that already ran; **bug-cyp-101** (Low) relationship property text with a final line break or non-ASCII digits reads back as a number; **bug-led-101** (Low) the reverse diff of a delete-and-recreate range reports the earlier property as absent. New questions: q-con-001 (L1), q-con-002 (L2); historical: hist-012, hist-013. Findings index regenerated: [findings.md](../../Verus_verification/findings.md).

## 6. Coverage (command: `python3 .g5/Verus_verification/tools/inventory.py`)

Python definitions in `iris_vector_graph/` (3,004; 119 files; 1,172 public): 26 directly linked from active formal items, 8 indirectly only. ObjectScript members in `iris_src/` (972 in 73 classes: 909 ClassMethod, 60 Method, 1 Query, 2 Trigger): 10 direct, 0 indirect only. SQL files: 14, none linked. Outside the denominator: `api/` 84, `src/` 141, `scripts/` 866 definitions. Tested upstream: 1,788 test files (no per-symbol mapping claimed). Implementation-verified: **0**. Of 15 linked blocks, 6 link both writer or producer and reader or consumer. Unmapped strata and the per-clause map: [coverage.md, consolidated section](../../Verus_verification/coverage.md#consolidated-uplift-2026-11-14-new-contracts-and-the-playbook-arms-active-families).

## 7. Paired predictions for the 32 public cases

Predictions for the graders to check, not grades. "Before" is the better arm per axis from `public-baselines.tsv`. No prediction is made about any private case.

| Case | Before: best ontology (G/P) | After: ontology | Ontology block | Before: best model (G/P) | After: model | Formal item |
|---|---:|---:|---|---:|---:|---|
| M01 | 2 (2S/2S) | 2 | ledger.commit.admission, ledger.idempotency | 2 (2S/2S) | 2 | G ledger_redaction theorem_retry_replays_first (as-built); P pa3 ledger_l1 (reviewed) |
| M02 | 2 (2S/2S) | 2 | ledger.idempotency | 2 (1P/2S) | 2 | P proofs-pa3 ledger_l2 commit_glob/lay_idem (reviewed) |
| M03 | 2 (1P/2S) | 2 | ledger.commit (Tier 1) | 2 (1P/2S) | 2 | P proofs-pa3 ledger_l2 (reviewed) |
| M04 | 2 (2S/2S) | 2 | ledger.readers | 1 (1P/1P) | 1 | unchanged: no named-revision reconstruction contract |
| M05 | 2 (2S/2S) | 2 | ledger.readers | 0 (0U/0U) | 0 | unchanged: no compute_diff-vs-reconstruct contract (C not built); bug-led-101 recorded |
| M06 | 2 (2S/2S) | 2 | temporal.window.sources (new) | 0 (0U/0U) | 2 | temporal_window_reader theorem_spec_sources_omitted_vs_empty + theorem_server_filter_sources (as-built; server Inspected) |
| M07 | 2 (1P/2S) | 2 | temporal.window.paging.release (new) | 0 (0U/0U) | 2 | temporal_window_reader theorem_yield_is_concat_to_done, theorem_close_mid_read_once |
| M08 | 1 (1P/1P) | 2 | temporal.window.paging, .release | 0 (0U/0U) | 2 | temporal_window_reader theorem_yield_is_concat_to_done (empty middle page), theorem_failed_page_closes_once |
| M09 | 2 (1P/2S) | 2 | structure.rebuilt.stamp (new) | 1 (1P/1P) | 2 | freshness_stamp theorem_unstamped_stale_at_zero, theorem_stamped_zero_current |
| M10 | 2 (2S/2S) | 2 | structure.degree.cache.uncommitted | 2 (2S/2S) | 2 | G graph_structure theorem_as_built_cache_sound + witness |
| M11 | 2 (1P/2S) | 2 | structure.multigraph.count (Tier 1) | 1 (1P/1P) | 1 | unchanged: no one-hop projection contract |
| M12 | 2 (0U/2S) | 2 | algorithms.op.paths.weighted (new) | 0 (0U/0U) | 0 | none: no optimality proof of the ObjectScript Dijkstra |
| M13 | 2 (2S/2S) | 2 | search.embedding.other_model | 2 (2S/1P) | 2 | G search theorem_store_routes_and_refuses |
| M14 | 2 (1P/2S) | 2 | search.embedding.width, search.routes.no_fallback (Tier 1) | 1 (1P/1P) | 1 | unchanged: route absence modeled, query-width preflight not |
| M15 | 2 (2S/2S) | 2 | search.routes.orphan, search.embedding.width | 1 (1P/1P) | 1 | unchanged |
| M16 | 1 (1P/1P) | 2 | structure.adjacency.declare (new) | 1 (0U/1P) | 2 | index_declaration theorem_no_prereq_no_ddl, theorem_prereqs_declare_both, theorem_declared_left_alone |
| M17 | 0 (0U/0U) | 2 | adapters.embedded.no_data (new page) | 0 (0U/0U) | 2 | embedded_no_data theorem_no_data_is_empty, theorem_other_error_raises |
| M18 | 0 (0U/0U) | 2 | query.values.relationship_text (new) | 0 (0U/0U) | 2 | rel_prop_text theorem_decode_classes, theorem_noncanonical_stays_text (reviewed rule) + as-built witnesses |
| M19 | 2 (2S/2S) | 2 | query.compiled.fallback | 1 (1P/1P) | 1 | unchanged |
| M20 | 2 (2S/2S) | 2 | query.compiled.fallback | 1 (1P/1P) | 1 | unchanged (P planc_l2 reviewed; restart supplied) |
| M21 | 2 (2S/2S) | 2 | algorithms.cache | 2 (1P/2S) | 2 | P proofs-d1e acache_l2 (reviewed; pin = control_f1004) |
| M22 | 2 (2S/2S) | 2 | temporal.ledger | 1 (1P/1P) | 1 | unchanged |
| M23 | 2 (1P/2S) | 2 | install.bulk_load.loader (Tier 1) | 1 (0U/1P) | 1 | unchanged: P bulk_l2 checkpoints only |
| M24 | 2 (2S/2S) | 2 | ledger.verify | 1 (1P/1P) | 1 | unchanged |
| J01 | 2 (1P/2S) | 2 | install.snapshot.routes (new) | 1 (0U/1P) | 1 | unchanged: P snap_l2 abstract contents |
| J02 | 2 (1P/2S) | 2 | install.snapshot.temporal (new) | 1 (0U/1P) | 1 | unchanged: P snap_l2; the window model is not connected to restore |
| J03 | 2 (2S/2S) | 2 | ledger.readers | 0 (0U/0U) | 0 | unchanged; q-con-001 recorded |
| J04 | 2 (2S/2S) | 2 | algorithms.cache.token | 2 (1P/2S) | 2 | P proofs-d1e acache_l2 (reviewed) |
| J05 | 2 (2S/2S) | 2 | ledger.commit.serial, ledger.idempotency | 2 (1P/2S) | 2 | P proofs-pa3 ledger_l2 (reviewed) |
| J06 | 2 (2S/2S) | 2 | temporal.ledger | 1 (1P/1P) | 1 | unchanged |
| J07 | 1 (1P/1P) | 2 | structure.adjacency.declare (new) | 1 (0U/1P) | 2 | index_declaration theorem_backfill_before_edge_index, theorem_no_prereq_no_ddl |
| J08 | 2 (2S/2S) | 2 | query.compiled.modes, .fallback | 2 (1P/2S) | 2 | P proofs-d1d planc_l2 (reviewed) |
| **Total** | **57** | **64** | | **33** | **46** | |

## 8. Outstanding questions, by consequence

1. **Serialization of erase, commits and redaction start** (bug-001, bug-002, simp-001/HD-1301, HD-1201): working answer, one lock across all three; alternative, refuse while transactions are open.
2. **Completeness of tenant removal** (HD-1304, HD-1303, REACH-1..5, F-1304): working answer, require tenant prefixes or report an explicit incomplete result naming every store not reached; alternative, record each node record's graph and migrate history.
3. **Restore against a live ledger** (q-plt-004 = HD-1801, F-1801): working answer, refuse when the heads diverge; alternative, explicit wholesale replacement.
4. **Reverse diffs and the streaming bound** (bug-led-101, q-con-002, q-con-001): working answer, a diff is a set of net changes and must report the earlier revision's values correctly; the bound covers delivery only. Alternative: a diff is a script (reverse tied entries), and the bound caps memory (fold incrementally).
5. **Reachability of bug-adp-001 and bug-cyp-101 on IRIS**: whether an unsupported-path error can follow a successful prepare, and whether `JSON_VALUE` returns a stored line break; a native observation decides each.

## 9. Costs (wall clock, this session, 2026-11-14/15 UTC)

WP0 import, registry, gate: about 50 minutes, with the reruns in the background (guidance controls 03:52-04:07, about 14.5 minutes of machine time; playbook reruns 03:54-04:03 and 04:07-04:11, about 13 minutes). Tier 1 ontology: about 60 minutes. Register crosswalk: about 30 minutes. Contracts A, B1, B2, B3, D: about 75 minutes in total; each proof under 1 s and each control suite under 15 s; bindings under 2 s each. Leads, sweep, links, coverage, handoff: about 70 minutes. No IRIS container was started (plan 3.5 was optional; nothing in priorities A-D needed it).

## 10. Independent review: pending

No independent review was possible in this session (no other session may be started). Package for the reviewer:

- Reproduce one new contract: the runbook's "One new contract end to end" (proof, `CONTROL=stop-on-empty-page`, `binding.py`), and one playbook crate (`run_playbook_crate.py proofs-d1e baseline control_f1004_create_moves_no_token`).
- Read [reader-check.md](reader-check.md) without this file, then answer the 17 cases from `.g5/ontology` alone.
- Attack first: (1) do the binding harnesses' hand transcriptions match the Verus spec functions they claim to (they are unverified Python), and do the enumerated domains cover the decisive inputs? (2) are the "reviewed design" labels and the claim "no pin-departure control for idempotency" in `proofs-pa3` right, i.e. is any active reviewed family being read as a product property? (3) are bug-adp-001, bug-cyp-101 and bug-led-101 real on IRIS, and are the 1,335 unswept refusal and contrast rows hiding Tier 1-like losses?

## 11. Method notes (mechanism principles)

| Concrete failure here | Smallest action that changes a capable agent's decision | Good behavior to preserve | Why it transfers | Cost |
|---|---|---|---|---|
| A repeated crate run from a `git archive` copy verified nothing (cargo up to date from archive mtimes) and printed no result line | the rerun tool cleans the package and treats "no result line" as ERROR, never a pass | rerunning from a pristine copy of the imported tree | any receipt-producing runner over immutable copies | one `cargo clean -p` per run |
| A safety theorem stated over the guarded predicate let a control that weakens that predicate survive | state "nothing happens unless" theorems over the raw inputs, not over the helper being controlled | controls as the test of a contract's strength | any controlled contract with a named precondition helper | none |
| A playbook statement existed but sat under a module with no owner page (M17 scored 0) | the root's module-to-page map plus an owner page for every module | detailed evidence tables as a source, not a second ontology | any consolidation of a detailed ledger into a governing ontology | one table |
| Hand transcriptions of spec functions in the bindings are unverified | a verified exec twin per binding (as `ledger_redaction/twin.rs`) | enumerated comparison plus mutation detection | every unit-level binding | about an hour per model |
