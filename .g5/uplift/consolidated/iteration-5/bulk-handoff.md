# Iteration 5 bulk-child builder handoff

The bounded package is the new `models/bulk_children/` family and its receipts. Product source, shared tools, imported trees, ontology, crosswalk and Git index were not changed by this builder. Root owns integration and grading. Starting foundation: iteration-4 seal `a63144b2a00a1489dc249c7f76a533b3a8eb2874`; product stays `3eaa79cf77d3e0a879b2cced634cf2729d81499e`.

## Material result and original cases

B1/B2 were frozen from product tests/docs in the prior independent survey, before implementation/model inspection. B1 contrasts an existing parent and new parent: labels union; an existing property retains its old value, a missing property gets the supplied typed value; node graph keys override the keyword. B2 holds old property rows fixed at a=1 and varies parent membership: a missing parent gets incoming a=2 with obsolete properties removed, while an existing parent keeps a=1 and gains c=3. A repeated new ID retains the first a=2 and gains d=4; another graph's same ID remains a=9. All IDs, including repeats, return in order.

Before this package, canonical `structure.node` did not name the bulk merge operation, `node_read` supplied the codec/reader fragments, and imported `bulk_l2` supplied publication/chunk behavior over anonymous row sets. None derived child maps from these inputs through final graph-scoped typed readback. The new family represents that decision and effect, not only member locators. This is a builder-selected known gap, not unseen discovery or independent evaluation.

Formal result: **30 verified / 0 errors; all 11 meaningful controls EXPECTED_FAIL**. Theorems are generic over graph+ID parents, property maps and label sets, with arbitrary finite batches for no-refusal completeness and ordered returns. The complete-reader connection derives values from stored maps and actual permissible SQL property orders, keeping alias collisions representable. Presence checks derive refusal from skipped required rows; provider exceptions and missing parent/label/property rows restore the original state under the explicit database rollback contract.

Native-Python result: **140 comparisons AGREES / 0 mismatches**, with real generated guards, relational writes, pre-batch orphan cleanup, actual missing-row checks, real WriteTxn orchestration, and actual `get_node/get_nodes` typed consumers. Five sensitivity checks detect altered cleanup, missing backstop, lost reader graph, numeric-to-text writer and a changed observed value. The adapter substitutes SQLite relations/savepoints, IRIS optimizer hints, the CY_TYPED producer and documented driver row skipping. No ObjectScript loader, index DDL or IRIS execution is claimed by this builder.

Pinned unit regression result: **81 passed in 1.30s**; `bulk-unit.log` retains the command output. Final proof/control/binding commands, measured wall times, inputs and all receipts are in `bulk-validation.json`; proof/control raw logs are copied beside receipts. Earlier 27-obligation passing runs and failed construction/proof attempts are retained in `bulk-attempts/`. The unsuccessful attempts were constructor, trigger and sequence-witness issues; they supplied no product-defect verdict. Tokens/cache/currency and solver-only time are unavailable.

## Exact canonical text recommendations

These are recommendations for root integration; this file is not a second canonical owner.

1. Scope the first sentence of `structure.node` to its actual single-node API, preserving its intended concurrency/refusal commitments:

> `create_node` changes nothing and reports False when the node already exists in its graph. A write that IRIS refuses raises an error and leaves nothing behind.

2. Add child `structure.node.bulk` after that owner, before node deletion. Suggested canonical body:

> `bulk_create_nodes` returns each nonempty input ID in input order, including repeats and nodes already present in the chosen graph. Each node uses its own `graph` value when supplied; otherwise the call's graph applies, and None names the default graph.
>
> Existing nodes gain labels and property keys they lack and keep every value they already hold. Before inserting the batch's parents, properties left by a missing parent are removed for that ID in that graph; repeated IDs then merge into the first occurrence, and the same ID's other graphs stay unchanged.
>
> A None-valued property is omitted. An absent `id` property defaults to the node ID; an explicit None-valued `id` property is omitted too. [Node reads](#structure.node.read) apply the shared type and alias rules.
>
> The SQL path checks that every expected parent, label and non-null property key exists before it returns. A failed write or missing required row raises and rolls back that SQL operation under the database transaction contract; an existing property's different value is a permitted merge, not a missing row.

Keep the native-loader publication boundary linked to existing F-0305 rather than extending this SQL rollback statement to all loader chunks. A size threshold drops/rebuilds indexes on the SQL path, but this package did not establish that separate DDL contract. `nonempty` is conventional product language; the actual Python branch skips every falsey ID, including numeric 0. Root may prefer `truthy ID` with a short definition if it intends to expose such admitted non-string inputs; the model and binding retain this neighbor.

3. Use the stable formal target in the new block metadata:

`[bulk child contract](../../Verus_verification/models/bulk_children/bulk_children.rs)`

Useful declaration targets are `select_graph`, `prepare`, `cleanup`, `offered`, `fold`, `run`, `read` and the named generic theorems. Model-side role recommendations appear once in `models/bulk_children/NOTES.md`; integrate only the roles actually qualified. Keep the existing `node_read` and transaction-provider boundaries explicit.

## Native fixture recommendation for root's isolated IRIS

No runtime write was performed by this builder. Three paths can be exercised without changing product behavior: (a) an engine after `initialize_schema()` with `_known_capabilities.objectscript_deployed=True` and no nonempty node graph uses the default loader; (b) a fresh second engine with no stored `_capabilities` uses the SQL branch if no one first reads its detecting `capabilities` property; (c) a nonempty named graph forces SQL on either engine. Record these pre-call facts and the payload. A source-inspected guard is path evidence; a direct native `Graph.KG.EdgeScan.BulkIngestNodesSQL` call can independently observe the server body without relying on an unmeasured wrapper dispatch. Do not treat lack of a fallback warning as a complete dispatch measurement.

B1 public API fixture, independently for each path: create `a` with Old/name=old/keep=k; bulk `[a New/name=new/flag=True, b L/n=5]`. Read both nodes and the graph's SQL child rows. Expect a's labels Old+New, name old, keep k, flag True; b's n must be integer 5; implicit ID appears as `p_id` in public readback. Use unique IDs per path and same-ID rows in graph other to check scope.

B2's orphan fixture needs the product's tested raw SQL parent deletion, because public `delete_node` correctly deletes the properties: create orphan candidate with a=1/obsolete=old, remove only its parent row by graph+ID SQL, and confirm the properties remain. Create an existing candidate with a=1. Bulk `[orphan a2, existing a2/c3, fresh a2, orphan a3/d4]`. Expect returned IDs in precisely that order; orphan a2/d4 with obsolete removed, existing a1/c3, fresh a2; other-graph a9 unchanged. The exact source tests are `test_470_bulk_orphan_props_e2e.py` and `test_460_bulk_create_nodes_paths_e2e.py`.

## Misses, findings and next work

This package supplies no new product bug, owner decision or design simplification, and no global coverage/precision percentage. It strengthens a known boundary. Source-predicted native loader equivalence is still inspection only until root's independent execution; F-0305's outer/native connection publication risk is inherited and not repaired. Full IRIS typing/rollback, caller-owned transactions, large-batch index rebuild, legacy NULL graph spellings, concurrent writers/readers and other child writers remain outside the demonstrated native domain. Alias collisions are represented and retained as the existing question, not silently excluded.

Material tractable gaps remain, so this package does **not** establish convergence. A different underserved workflow is snapshot restore at per-route archived widths through registry lookup and the final vector reader. Root is working that independent slice. A later iteration could materially strengthen the bulk guarantee by observing native loader/SQL readback on IRIS and then addressing actual provider and cross-process transaction boundaries; it should preserve the B1/B2 values and refusal neighbors rather than add locator-only credit.
