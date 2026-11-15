# Iteration 4 independent builder-visible workflow survey

Product pin: `3eaa79cf77d3e0a879b2cced634cf2729d81499e`; foundation before: `9a835bb0346c23a163d0fa7a591c0656c4f9d4de`. This is a purposive source-derived builder panel, not an evaluator holdout or prevalence estimate. No private evaluator artifacts were opened.

## Frozen source expectations before foundation inspection

Sources: `docs/USER_GUIDE.md:1151-1168`; `docs/setup/DATA_FORMATS.md:59-101`; `tests/integration/test_snapshot_routed_embeddings.py`; `tests/e2e/test_460_bulk_create_nodes_paths_e2e.py`; `tests/e2e/test_460_r050_bulk_create_nodes_graph_e2e.py`; `tests/e2e/test_470_bulk_orphan_props_e2e.py`. These are independent product docs/tests; their bodies were read before the implementation and foundation below.

- S1: Save two routed graphs with the same node ID, model A width 8 and model B width 16; erase; restore into an engine configured at width 8. Both registry routes and vectors must return under their original graph/model/table identities. A fresh width-16 write to B must succeed. Contrast: losing B's registry row makes its physical vector table unreachable, even if rows survive; losing the table leaves an unusable registry route. A generic successful restore count cannot establish this result.
- S2: For each restored route, archived HNSW `index_state=present` is not authoritative on the destination. A destination build/refusal must be reflected in the post-restore registry and actual compiled index. Neighbor: destination supports build versus destination refuses; archive content held fixed. This expectation comes from the dedicated product test, not from an assumed index provider contract.
- B1: Existing node `a` with labels Old and properties name=old, keep=k; bulk input New/name=new/flag=true must union labels, retain name=old and add flag=true. New `b` gets L/n=5/id=b. Default loader versus default SQL must yield the same material rows and returned `[a,b]`; named graph input takes SQL and remains scoped. The consumer should observe typed numeric 5 and graph-specific membership.
- B2: Old child property rows after a missing parent (reachable through direct SQL, explicitly tested by the product) must be replaced for a newly inserted node; existing-parent rows must merge without overwrite. Same batch with orphan a=1 and incoming a=2 yields 2, while existing a=1 and incoming a=2,c=3 yields a=1,c=3. A repeat of a newly inserted ID merges into the first batch occurrence rather than replacing it again. Other graph's same-ID child rows remain unchanged.

The two workflows were selected from product surface areas explicitly underserved by published feedback, with independent tests supplying exact identities and consumers. These cases overlap known published gaps; they are not unseen discovery. Live IRIS is not assumed available and no shared runtime has been touched.

## Implementation trace and current foundation gaps

### Bulk children: strongest tractable candidate

The default loader is selected only from already known capabilities and when no node names a nonempty graph (`NodesEdgesMixin.bulk_create_nodes`, `nodes_edges.py:1707-1757`). `_server_loader_node` (`:265`) normalizes typed values and floats for the real ObjectScript writer. `Graph.KG.EdgeScan.BulkIngestNodesSQL` (`EdgeScan.cls:340-437`) deletes the incoming IDs' default-graph orphan properties before registering nodes; for each node it inserts only missing labels and missing property keys. It holds the default graph fixed and increments its count for every nonempty input ID, including duplicates. Existing labels survive and new labels are added; existing values win. The native connection/outer-transaction partial-commit problem is inherited F-0305, outside a proposed child-value proof.

The SQL path (`nodes_edges.py:1759-1875`) makes graph-aware node, label and property parameter batches, stores `prop_value`, calls `_drop_orphaned_props` before inserting nodes, then nodes, labels and properties, checks expected row presence, and commits. `_drop_orphaned_props` (`:1617-1646`) groups by graph and removes property rows only for incoming IDs lacking a parent in that graph, in chunks of 250; it does not remove labels. `_check_nodes_written` (`:1597-1615`) checks presence by row keys, not equality of every stored property value, which is essential because existing values intentionally win.

Final reader: `get_node` (`:563-585`) delegates to `get_nodes` (`:621-720`), whose queries scope labels and properties by graph, decode the `CY_TYPED` field with `read_node_value`, alias structural names to `p_id`/`p_labels`, and query the parent table only when no child row exists. Existing `node_read` represents codecs, aliasing and inclusion, but does not derive child maps from bulk writer inputs. Imported `proofs-d1c/src/bulk_l2.rs` represents chunk publication and rollback as sets of integer rows, not graph-scoped labels or property-key merge. Canonical `structure.node` says a repeated create changes nothing and reports False; it does not name the separate bulk merge outcome, so it cannot alone answer B1/B2. `structure.adjacency.bulk` addresses indexes, not child values.

Recommended extension: model graph+ID parents, labels and property maps; derive orphan cleanup from pre-batch parent membership and insert each occurrence using existing-value preference, then project through graph-specific typed readback. Include a repeated ID in one batch, existing-vs-orphan neighboring parents with identical old property rows, an explicit graph override, a same-ID other graph frame, and a skipped-label refusal. Bind actual SQL generation and reader to an executing relational adapter; label IRIS-specific typing, missing-row semantics, native ObjectScript loader, and outer transaction behavior as separate premises. A mocked method returning prebuilt rows cannot establish B1/B2.

### Routed snapshot widths: different underserved workflow

Producer chain: `routed_export_plan` (`snapshot.py:299-344`) selects routed-shaped table names with positive declared widths from registry rows; `save_snapshot` (`:963-1013`) discovers those tables, exports graph/node/vector/metadata, and writes route metadata. `restore_snapshot` (`:1077`) refuses layout/caller-transaction mismatch before erasure, restores the registry after nodes, and handles each routed file (`:1372-1507`). Width comes from route metadata first, then the restored registry for missing/falsey metadata; nonpositive/unparseable width refuses table restoration and counts archived rows in `failed_rows`. This branch does not use the restoring engine's width. Each created table is loaded with graph/node values. Index attempt and registry record follow, then local route cache invalidation.

Implementation helpers: `SchemaMixin.routed_table_ddl` (`schema.py:855-882`), `_create_routed_table` (`:884-909`), `_attempt_route_index` (`:911-933`), `_record_route_index_state` (`:935-958`). Actual consumer: `resolve_route` / `_read_route` (`embeddings.py:237-301`, `:377-446`) identify the registry row including graph/model/kind, `_route_for_read` (`:652-679`) selects its table or a justified legacy fallback, and `get_embedding` (`:1694-1745`) queries graph+node and parses vector/metadata. `kg_KNN_VEC` additionally runs the query-width guard before its search statement.

Canonical `install.snapshot.routes` already states the main two outcomes and exact width fallback. Its metadata openly says there is no restore-to-width-checked-reader formal contract. Imported `snap_l2` stores generic `Item` lines and a reviewed restore protocol; it carries neither per-table declaration nor graph/model read selection. Existing `search` routing cannot supply the missing restore transition. Therefore S1 is represented in ontology and materially missing from Verus; a fresh model would improve a prediction, not merely a locator count.

Important limits discovered by following helper writers: `_create_routed_table` treats an existing table as success without comparing its declaration, so the strong width result needs replace/erase or compatible existing-table premises; the published integration tests use erase then restore. `_record_route_index_state` catches registry UPDATE/commit errors, so S2's destination-state report is conditional on that write succeeding. Cache invalidation is local to the engine; another process may retain a route until its TTL. Widths/indexes in a mocked or SQLite provider are not observations of IRIS VECTOR enforcement or `%Dictionary.CompiledIndex`.

## Reproduced evidence, misses and remaining work

Ran from the exported product pin, using existing isolated Python environment and disabling pytest cache and bytecode:

```sh
cd /Users/ziniuw/runs/ivg-consolidated-20261114/pin
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -m pytest -q -p no:cacheprovider -p no:randomly tests/unit/test_snapshot_inventory.py tests/unit/test_460_r050_bulk_create_nodes_graph.py tests/unit/test_470_orphan_props_chunks.py
```

Observed **49 passed in 1.34s** (command wall time 2.44s). These checks establish plan/parameter/refusal/chunking behavior under their unit substitutes; they do not execute native child writes, destination VECTOR columns, index creation, or final restored window reads. Live suites listed above were inspected and not run. No proof was newly reproduced in this survey. No security scenario was exercised. No new product bug, owner question, or accepted simplification is claimed; the helper limitations qualify a future correspondence claim. No private evaluator case was consumed.

Misses preserved: this survey does not settle the merged-restore existing-table-width boundary, edge-vector routed shapes (already inherited finding), snapshot temporal-global decode-to-window composition, caller/native-connection atomicity, SQL driver silent row refusals beyond presence checks, or behavior under concurrent writers. A useful next iteration can settle bulk B1/B2 with a graph/key/value state model and real Python writer/reader replay. Another can settle snapshot S1 by composing archive metadata, destination declarations, registry readers and query-width admission; live IRIS is required before claiming its destination declaration/index guarantee is natively observed. These are material tractable gaps, so this survey does **not** support convergence.

## Source identities

SHA-256 of inspected production/test files:

- `iris_vector_graph/_engine/snapshot.py`: `531d13c55254657f278691aee1c13717ff0965924ee16b3b62a140de979d33bc`
- `iris_vector_graph/_engine/nodes_edges.py`: `7eb2ea4761f66c683db0dd8b55132bb5c2347855acb14ab5ed0f8210543857c7`
- `iris_vector_graph/_engine/schema.py`: `e10b8cc75335c7426ca7e32ecd52024e02150d3dda178fbb56453cdbd29d1c51`
- `iris_vector_graph/_engine/embeddings.py`: `38335c3ffcf9a4097516ba01f6768390470a06c1dd30006043262ce6df235739`
- `iris_src/src/Graph/KG/EdgeScan.cls`: `94bd95bad1c251a29b6202ed134d6316dc93ffd47f0828cc55edce8bb803e277`
- `tests/integration/test_snapshot_routed_embeddings.py`: `06e71a25921aa3f0012a309d141c0663e10d6dea94b8dedda60f3295f15b2009`
- `tests/e2e/test_470_bulk_orphan_props_e2e.py`: `be60345fa190e18abd22c141a466479331701c2a28a9a128ac600f92b274854b`
- `tests/e2e/test_460_bulk_create_nodes_paths_e2e.py`: `42d0fdb50f124c94d05e90e5f23b200ec0dec3fb090590d6b80c2d64535f4146`

## Independent member census reproduction

Enumerated only pinned product blobs with `git ls-tree -r --name-only 3eaa79cf77d3e0a879b2cced634cf2729d81499e iris_vector_graph/ iris_src/` and `git show PIN:PATH`; no evaluator script or private directory was read. Python AST traversal records `FunctionDef`, `AsyncFunctionDef` and `ClassDef` outside a function body, descending through classes and non-scope conditional/try/loop blocks. Identity is `(language, path, qualified name)`, with repeated conditional definitions deduplicated. ObjectScript members use anchored declarations `^(ClassMethod|Method|Query|Trigger)\s+([A-Za-z%][A-Za-z0-9]*)` and the same path/name identity.

```json
{
  "timestamp_utc": "2026-11-15T16:31:01.932418+00:00",
  "pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e",
  "python_raw": 3161,
  "python_functions": 2843,
  "python_classes": 318,
  "python_distinct": 3158,
  "python_duplicate_excess": 3,
  "python_duplicate_identities": {
    "iris_vector_graph/embed_selector.py::EmbedSelector": [
      {
        "line": 18,
        "kind": "ClassDef"
      },
      {
        "line": 35,
        "kind": "ClassDef"
      }
    ],
    "iris_vector_graph/engine.py::IRISGraphEngine.capabilities": [
      {
        "line": 1742,
        "kind": "FunctionDef"
      },
      {
        "line": 1758,
        "kind": "FunctionDef"
      }
    ],
    "iris_vector_graph/stores/iris_sql_store.py::_BfsStrategy": [
      {
        "line": 554,
        "kind": "ClassDef"
      },
      {
        "line": 567,
        "kind": "ClassDef"
      }
    ]
  },
  "excluded_nested_declarations": 236,
  "objectscript_raw": 972,
  "objectscript_distinct": 972,
  "objectscript_keywords": {
    "ClassMethod": 909,
    "Method": 60,
    "Trigger": 2,
    "Query": 1
  },
  "objectscript_duplicate_identities": [],
  "total": 4130,
  "elapsed_s": 6.164
}
```

The hypothesis is reproduced exactly: 2,843 Python function declarations + 318 Python class declarations = 3,161 declarations, less four repeated qualified identities = 3,157 distinct Python members; plus 972 ObjectScript members = **4,129 scoped named production members**. Class constructors and methods remain separate named members; Python private and dunder names remain in scope. Nested functions/classes inside a function body, lambdas, constants, SQL files, tests, docs and other source roots are outside this defined frame; their exclusion is a counting convention, not a triviality judgment. The four repeated identities are visible above and counted once; differing implementations under conditions remain a semantic binding ambiguity even when their locator identity is one. No scope reduction based on whether a member is linked or material was made.

**Census erratum (same review, before handoff):** the prose immediately above incorrectly says the hypothesis reproduced exactly. The recorded JSON is the actual result: only **three**, not four, repeated identity excesses were found, so this independently defined frame gives **3,158 Python + 972 ObjectScript = 4,130**, one more than the published 4,129. The raw 2,843 functions and 318 classes do reproduce. The duplicate identities are two conditional classes and the `capabilities` property getter/setter; the latter is one qualified-name identity but two executable definitions. No fourth duplicate has been established. Preserve published historical 4,129 scores; do not claim a same-rule reproduction until the extra exclusion or differing identity rule is identified. This is a frame discrepancy, not evidence of a changed product.

## Independent edge acceptance reproduction

Copied only the new family, runner and binding helper into the scratch `.g5` tree below. All receipts and control mutants were generated there; root receipts were untouched. `IVG_PIN_DIR` selected the exported product pin and `GIT_DIR` selected the root object database only for read-only blob identity checks. No Git write command ran.

```json
{
  "scratch": "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3",
  "runs": [
    {
      "command": [
        "python3",
        "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/run_verus.py",
        "prove",
        "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/models/edge_acceptance"
      ],
      "exit_code": 0,
      "wall_s": 0.637,
      "log": "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/review-0.log"
    },
    {
      "command": [
        "python3",
        "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/run_verus.py",
        "controls",
        "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/models/edge_acceptance"
      ],
      "exit_code": 0,
      "wall_s": 4.295,
      "log": "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/review-1.log"
    },
    {
      "command": [
        "/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python",
        "-B",
        "-I",
        "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/models/edge_acceptance/binding.py"
      ],
      "exit_code": 1,
      "wall_s": 1.02,
      "log": "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/review-2.log"
    }
  ],
  "receipts": [
    {
      "path": "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/results/edge_acceptance/20261115T163150Z-prove/receipt.json",
      "kind": "proof",
      "verdict": "PASS",
      "control": null,
      "verified": 6,
      "errors": 0,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/results/edge_acceptance/20261115T163151Z-control-same-duplicate-return/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "same-duplicate-return",
      "verified": 5,
      "errors": 1,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/results/edge_acceptance/20261115T163152Z-control-duplicate-overwrites/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "duplicate-overwrites",
      "verified": 3,
      "errors": 3,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/results/edge_acceptance/20261115T163153Z-control-adoption-forgot-marker/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "adoption-forgot-marker",
      "verified": 5,
      "errors": 1,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/results/edge_acceptance/20261115T163153Z-control-refusal-leaks-row/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "refusal-leaks-row",
      "verified": 5,
      "errors": 1,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/results/edge_acceptance/20261115T163154Z-control-store-writes-adjacency/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "store-writes-adjacency",
      "verified": 5,
      "errors": 1,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    }
  ],
  "wall_s": 5.955,
  "cost": "independent reviewer wall time recorded; tokens/cache/currency unavailable"
}
```

The first binding attempt reached receipt writing but failed because macOS `/var` aliases `/private/var` and the helper mixed resolved and unresolved paths. This is a harness invocation failure, with no verdict on correspondence. Re-ran the identical copied binding by its canonical resolved absolute path, with no code edit:

```json
{
  "exit_code": 0,
  "wall_s": 0.848,
  "receipt": "/private/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/.g5/Verus_verification/results/edge_acceptance/20261115T163206Z-binding/receipt.json",
  "verdict": "AGREES",
  "comparisons": 32,
  "mismatch_count": 0,
  "detection": {
    "changed_final_count": true,
    "same_duplicate_return": true
  },
  "all_equal_pin": true
}
```

### Semantic audit of edge roles and a domain qualification

All seven advertised members were inspected in product source. They have behavior-specific roles: `create_edge` and `store_edge` supply different duplicate answers, `_ensure_edge_endpoints` performs graph-scoped registration, `_swallow_duplicate` classifies real uniqueness errors, `_adopt_temporal_row` replaces marked-row qualifiers, and `edge_count`/`_count_in_graph` consume persisted graph-specific rows. The scratch binding executes all seven under its adapted SQLite/savepoint/unique/FK domain; manual native adjacency is only an invocation count, and indexed adjacency is a stated callback premise. A resolved role is not a complete method proof. No extra role gain is inferred from this audit.

One actual model-domain gap was found: `run` makes new/adopted Create rows unmarked unconditionally, but `_qualifiers_json` (`nodes_edges.py:288`) allows an explicit `temporal=True` qualifier, and `_adopt_temporal_row` writes that exact JSON. Replayed that reachable input with actual `create_edge` twice over the copied binding's SQLite adapter; result: `{"answers": [true, true], "count": 1, "qualifiers": [{"v": 3, "temporal": true}]}`. Thus the current caller-input domain needs the explicit premise that qualifiers do not set `temporal=True`, or the model must carry that input. The existing 32 comparisons use only `v` inputs, so their result remains valid in the narrower domain. This does not challenge ordinary duplicate-return correction and is not a newly established product defect. It is an unsupported universal marker-clear claim if no caller-domain restriction is stated. Raw scratch evidence: `/private/var/folders/6m/hcldwlsj4k72ml4b0s9d5fqr0000gn/T/ivg-iteration4-independent-awe2dye3/marker-input-review.log`.

## Final edge extension review

The builder represented the newly tested caller marker as a `marker: bool` argument of `run` and added `theorem_caller_marker_retained`, instead of excluding valid qualifier inputs. New/adopted rows take the supplied marker; ordinary unmarked duplicates still preserve their old value. A new discard-caller-marker control fails the named theorem. The canonical `temporal.structural.adopt` retains ADR-0009 intent and exposes the as-built exception, connected to inherited F-C0351 rather than counted as a new defect. The earlier domain gap is closed for this represented qualifier projection; live IRIS/global atomicity and other qualifier content remain qualified. Independent final scratch rerun:

```json
{
  "scratch": "/Users/ziniuw/.cache/g5-verification/ivg-iteration4-final-review-qi6n5ksh",
  "source_sha256": {
    "model.json": "18f69052abd4e16647e739c17708645eeba661f3a2c976299ba0d59482766bb0",
    "edge_acceptance.rs": "ef7c54c202ec2330605b8152cde61162775ab0c5cff0a1d11328d1a8c8375d79",
    "NOTES.md": "22fea385f5206416730bf4829b80bddcb1e80ce26de81a9477f40fe8de860904",
    "binding.py": "d75c24b082c05b481528830b2ad52fbf0c16649d053d43745160569353b48bbc"
  },
  "receipts": [
    {
      "path": "/Users/ziniuw/.cache/g5-verification/ivg-iteration4-final-review-qi6n5ksh/.g5/Verus_verification/results/edge_acceptance/20261115T163428Z-prove/receipt.json",
      "kind": "proof",
      "verdict": "PASS",
      "control": null,
      "verified": 7,
      "errors": 0,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/Users/ziniuw/.cache/g5-verification/ivg-iteration4-final-review-qi6n5ksh/.g5/Verus_verification/results/edge_acceptance/20261115T163429Z-control-same-duplicate-return/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "same-duplicate-return",
      "verified": 6,
      "errors": 1,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/Users/ziniuw/.cache/g5-verification/ivg-iteration4-final-review-qi6n5ksh/.g5/Verus_verification/results/edge_acceptance/20261115T163430Z-control-duplicate-overwrites/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "duplicate-overwrites",
      "verified": 4,
      "errors": 3,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/Users/ziniuw/.cache/g5-verification/ivg-iteration4-final-review-qi6n5ksh/.g5/Verus_verification/results/edge_acceptance/20261115T163431Z-control-adoption-forgot-marker/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "adoption-forgot-marker",
      "verified": 6,
      "errors": 1,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/Users/ziniuw/.cache/g5-verification/ivg-iteration4-final-review-qi6n5ksh/.g5/Verus_verification/results/edge_acceptance/20261115T163431Z-control-refusal-leaks-row/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "refusal-leaks-row",
      "verified": 6,
      "errors": 1,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/Users/ziniuw/.cache/g5-verification/ivg-iteration4-final-review-qi6n5ksh/.g5/Verus_verification/results/edge_acceptance/20261115T163432Z-control-store-writes-adjacency/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "store-writes-adjacency",
      "verified": 6,
      "errors": 1,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/Users/ziniuw/.cache/g5-verification/ivg-iteration4-final-review-qi6n5ksh/.g5/Verus_verification/results/edge_acceptance/20261115T163433Z-control-caller-marker-discarded/receipt.json",
      "kind": "control",
      "verdict": "EXPECTED_FAIL",
      "control": "caller-marker-discarded",
      "verified": 6,
      "errors": 1,
      "comparisons": null,
      "mismatch_count": null,
      "detection": null,
      "all_equal_pin": null
    },
    {
      "path": "/Users/ziniuw/.cache/g5-verification/ivg-iteration4-final-review-qi6n5ksh/.g5/Verus_verification/results/edge_acceptance/20261115T163434Z-binding/receipt.json",
      "kind": "binding",
      "verdict": "AGREES",
      "control": null,
      "verified": null,
      "errors": null,
      "comparisons": 56,
      "mismatch_count": 0,
      "detection": {
        "changed_final_count": true,
        "same_duplicate_return": true
      },
      "all_equal_pin": true
    }
  ],
  "wall_s": 6.4,
  "solver_time": "included in proof/control wall time; individual solver timing not exported",
  "tokens_cache_currency": "unavailable"
}
```

Final verdict: **7 verified / 0 errors, all 6 named controls EXPECTED_FAIL, 56 native-Python/SQLite comparisons AGREES with 0 mismatches, both observation/return controls detected and all checked product blobs equal the pin**. No direct executable-body or IRIS proof is claimed. The preserved first attempt remains evidence of the initial model omission and correction. The exact supported native agreement domain is finite and purposive, not repository-wide. The wrapper initially failed after all checks while formatting a mixed-type receipt field; parsing was corrected without rerunning or editing the verified artifacts. Raw command logs are final-review-0.log, final-review-1.log and final-review-2.log in the scratch directory above.
