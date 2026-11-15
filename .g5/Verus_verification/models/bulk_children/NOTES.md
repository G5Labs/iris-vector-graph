# Bulk children: graph-scoped merge and readback

Product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`; builder starts after iteration 4 seal `a63144b2a00a1489dc249c7f76a533b3a8eb2874`. Bundled vstd with the existing pinned arm64 Verus `0.2026.10.04.426d8b0`, four threads. No new library or toolchain pin, assumption, admission or external body. This is an as-built transcription, not an executable-body proof.

The independent source-first B1/B2 predictions were frozen in the iteration-4 external `independent-survey.md`. B1: an existing node gains labels and missing properties but keeps stored values; a new node stores its supplied typed children in its chosen graph. B2: an incoming ID lacking its parent loses old orphan properties before any batch parent is inserted; repeated occurrences then merge into the first occurrence. The same ID in another graph is unchanged. The source tests `test_460_bulk_create_nodes_paths_e2e.py` and `test_470_bulk_orphan_props_e2e.py` supply exact hand-worked fixtures. They were inspected before modeling; no private evaluator evidence was used.

## Formal contract

`Store` contains real graph+ID parent membership, graph-scoped label sets and property maps. `select_graph` and `prepare` distinguish an absent graph key, explicit null/default graph and an explicit graph overriding the call keyword. `offered` derives non-null property writes and the implicit ID property, retaining the explicit-null exception. `cleanup` uses the **pre-batch** parent census and removes only incoming IDs' orphan properties. `apply`/`fold` model guarded INSERTs: labels union and old property values win, including on repeated IDs. `returned` retains input order and repeats; falsey admitted IDs are inactive.

The no-refusal theorem applies to arbitrary finite input sequences and arbitrary finite maps/sets, not only B1/B2 examples. Generic theorems prove existing values, newly supplied missing values, orphan replacement/removal, label union, repeated-ID first-value preference, other-graph and unrequested-node frames, graph-key precedence and null/ID handling. `Fault` represents skipped attempted parent/label/property INSERTs; the actual presence check derives success or refusal from the produced rows. Missing required rows and provider exceptions restore the original store under the named database rollback contract. The checker deliberately tests **presence**, not equality with incoming values: equality would wrongly refuse a legitimate existing-value merge.

`read` selects only the requested graph+ID, reconstructs labels and folds the actual stored property values through structural-name aliases. The row-order input represents SQL's lack of an `ORDER BY`; `reader_order` requires every stored key exactly once. Complete-reader theorems connect existing/orphan values to a full property read when the target display key has no collision. Inputs with alias collisions remain representable; `witness_alias_row_order_can_change_result` proves the inherited `id`/`p_id` ordering ambiguity. Scalar/type identities are abstract atoms here. Numeric tags, JSON and nonfinite conversions are governed by the existing `node_read` slice and independently exercised by the native-Python binding; this family does not re-prove their codec.

The SQL implementation groups all parent INSERTs, then labels, then properties. The model folds each input's contributions after the same one-time cleanup. Those contributions do not depend on intermediate parent/label writes and have the same final per-key guards. This is an inspected end-state correspondence under one successful SQL transaction and no concurrent observer/writer; intermediate phases are not claimed unobservable on IRIS's default isolation. Failure outcomes use actual WriteTxn rollback orchestration plus the assumed provider rollback contract.

## Product roles

All paths below are relative to the repository. These are proposed semantic bindings for root integration; a locator alone earns no semantic credit.

| Role | Production member | Contract | Evidence in this package |
| --- | --- | --- | --- |
| deciding caller/writer | `iris_vector_graph/_engine/nodes_edges.py::NodesEdgesMixin.bulk_create_nodes` | `prepare`, `offered`, `fold`, `returned`, `run` | actual SQL branch, typed bound inputs, persisted rows and return values |
| deciding orphan writer | same file `NodesEdgesMixin._drop_orphaned_props` | `cleanup` | actual grouped/chunked relational DELETE before INSERTs |
| SQL producer | same file `NodesEdgesMixin._bulk_sql` | `add_props`, `apply` | actual schema rewrite and generated guards |
| guard producer | `iris_vector_graph/schema.py::GraphSchema.get_bulk_insert_sql` | `add_props`, `apply` | actual guarded node/label/property SQL executed after stripping optimizer hints |
| validation caller | nodes/edges file `NodesEdgesMixin._check_nodes_written` | `met`, `complete` | actual expected-key construction and readback |
| validation reader | `iris_vector_graph/_batch_check.py::missing_rows` | `complete` | actual SELECT against persisted rows, including driver-skipped label refusal |
| refusal mapper | same file `raise_if_missing` | `run` | actual GraphWriteError before rollback |
| final reader | nodes/edges file `NodesEdgesMixin.get_nodes` | `read`, `read_props`, `reader_order` | actual graph-scoped queries, typed decoding and aliases |
| delegated reader | same file `NodesEdgesMixin.get_node` | `read` | justified shared role: calls `get_nodes([id], graph)` and selects its first result |

`prop_value`, `read_node_value` and WriteTxn begin/commit/rollback are consumed by the binding, with existing codec/transaction boundaries retained. They are not promoted to executable-body verification. The capability branch and native `Graph.KG.EdgeScan.BulkIngestNodesSQL` were inspected, **not executed by this builder**. The ObjectScript writer uses a default-graph orphan DELETE and guarded missing child INSERTs; its per-chunk transaction ownership remains inherited F-0305. No default-loader versus SQL equivalence claim follows from the Python/SQLite comparison. Root may attach independently obtained native evidence.

## Replay and results

From the repository root:

```sh
export RUN_DIR=/Users/ziniuw/runs/ivg-iteration5-bulk-20261115
export VERUS_BIN=/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus
export VERUS_RUN_THREADS=4 PYTHONDONTWRITEBYTECODE=1
export IVG_PIN_DIR=/Users/ziniuw/runs/ivg-consolidated-20261114/pin
python3 .g5/Verus_verification/run_verus.py prove .g5/Verus_verification/models/bulk_children
python3 .g5/Verus_verification/run_verus.py controls .g5/Verus_verification/models/bulk_children
/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/models/bulk_children/binding.py
```

Expected final results: **30 verified / 0 errors**, all **11** controls `EXPECTED_FAIL`, and binding **AGREES / 140 comparisons / 0 mismatches** with five detections true. Receipts and raw proof/control logs live in `results/bulk_children/`; earlier 27-obligation runs are retained. Final measured commands and input hashes: [bulk-validation.json](../../../uplift/consolidated/iteration-5/bulk-validation.json). Failed type/trigger/sequence-proof attempts and their successful corrections: `bulk-attempts/` in that evidence directory. The initial use of the wrong finite-map constructor and missing trigger/sequence witnesses supplied no defect verdict.

The binding executes real `bulk_create_nodes` with generated SQL, one relational store, `prop_value`, orphan cleanup, missing-row checks, WriteTxn orchestration and the actual `get_node/get_nodes/read_node_value` consumer. It compares full persisted parent/label/property state and public typed reads. B1/B2, default/named/override graphs, old values, repeats, nulls, caller ID, alias collisions, falsey ID 0, integer/text/float/bool/container/tag/nonfinite values and empty input are covered. Four neighbors make a real NOT NULL label failure either raise or be driver-skipped; all restore the original orphan properties and all prior rows. The skip adapter follows the documented IRIS executemany behavior; IRIS itself was not run by this builder. Valid producers and observers also survive the fault-free cases.

Five sensitivity checks detect removed orphan cleanup, removed presence backstop, a graph-losing actual reader, a numeric writer changed to text and a changed final public value. Proof controls independently change cleanup, existing-value preference, labels, graph scope, missing-row admission, null handling, repeated returns and consumer aliases/graph selection. A successful parse or unrelated failure is never counted as a control verdict.

The relational adapter preserves generated predicates and parameters, strips IRIS optimizer hints, substitutes SQLite savepoints for the Txn SQL functions, and supplies the inspected CY_TYPED numeric/tag producer. It forces only the `_batch_check._live` predicate so the real backstop executes against the relational tables. SQLite uniqueness, NOT NULL constraints and label foreign keys are active; properties intentionally have no parent FK, matching the product. This is finite native-Python transcription agreement, not a proof of SQLite/IRIS equivalence or the Python twin. Supplemental typed values do not establish an exhaustive codec theorem.

## Limits and dispositions

No new product defect, simplification or owner-policy question is claimed. This strengthens material prediction and binding gaps exposed by the public feedback. Existing findings and owner decisions remain unchanged. Parent-null legacy graph spellings, large-batch index DDL/rebuild, caller-owned transactions, provider failures during commit/rollback, cross-process interference, the native loader and all other writers remain separate obligations. The model admits label/alias outcomes that can be unproducible under a particular FK/provider configuration; only the actual native comparisons are product observations.

The package is builder-selected and self-evaluated. Its 140 cases are a purposive panel, not independent grading or a repository-wide rate. The 81 relevant pinned unit tests were reproduced with no failures (`bulk-unit.log`); they use their existing substitutes and do not establish live IRIS behavior. Token/cache/currency costs are unavailable. Proof/control/binding wall time is measured separately in `bulk-validation.json`; raw failed runs remain available. This package supplies no convergence claim: routed snapshot widths through final readers and the native-loader/provider boundary remain consequential candidates.

## Root native qualification (iteration 5)

[bulk-native.py](../../../uplift/consolidated/iteration-5/bulk-native.py) and its
JSON/log run B1/B2 on actual hostname-checked IRIS in three paths: default loader,
fresh-engine default SQL and named-graph SQL. All three agree. Instrumentation
wraps _call_classmethod_large and invokes its unchanged original: exactly the
loader case calls Graph.KG.EdgeScan.BulkIngestNodesSQL. Existing/orphan/repeated
values, integer5, union labels, returned repeats and the other-graph value9 survive.
This adds finite native agreement for the default single chunk and SQL paths; it
is not a general ObjectScript proof or a caller/commit/large-index/failure proof.
The wider140-value/refusal panel still uses the SQLite/CY_TYPED substitutes.
