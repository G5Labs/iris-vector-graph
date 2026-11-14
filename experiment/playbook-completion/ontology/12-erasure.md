# 12 Graph erasure

Module: ERS
Root: ERS-0
Scope: Graph.KG.Eraser (iris_src/src/Graph/KG/Eraser.cls), the store inventory Graph.KG.GraphStores
(iris_src/src/Graph/KG/GraphStores.cls), and the engine entry points erase_graph and delete_nodes_by_prefix
(iris_vector_graph/_engine/nodes_edges.py:1473-1560). First stage of the worked example: erasure, then redaction (module RED),
then replay (module RPL). Erasure interleaved with ledger commits is model-checked in model/src/erasure.rs.

## Glossary

| Term | Defined by | Restated by |
|---|---|---|
| graph erasure | ERS-D1 | ERS-D1a |
| node erasure | ERS-D2 | |
| statement entry | ERS-D3 | ERS-D3a, ERS-D3b |
| commit | ERS-D4 | ERS-D4a, ERS-D4b |
| ledger lock | ERS-D5 | ERS-D5a |

## Statements

| Id | Parent | Kind | Statement | Evidence | Source | Notes |
|---|---|---|---|---|---|---|
| ERS-0 | SYS-0 | R | Erasure takes content out of every store. It keeps the ledger's records. | inspected:iris_src/src/Graph/KG/Eraser.cls:1-35 | docs/adr/0004-erasure-removes-content-not-history.md; CONTEXT.md:198-208 | Owns the delete path of every content store; Graph.KG.GraphStores lists the stores it must reach. |
| ERS-D1 | ERS-0 | D | A graph erasure removes all of one graph's content. | inspected:iris_src/src/Graph/KG/Eraser.cls:37-47; inspected:iris_vector_graph/_engine/nodes_edges.py:1473-1527 | docs/adr/0004-erasure-removes-content-not-history.md | EraseGraph(graph); engine.erase_graph. |
| ERS-D2 | ERS-0 | D | A node erasure removes the nodes of one graph whose ids start with a given text. | inspected:iris_src/src/Graph/KG/Eraser.cls:307-352; inspected:iris_vector_graph/_engine/nodes_edges.py:1529-1560 | docs/adr/0004-erasure-removes-content-not-history.md | EraseNodes(graph, prefix); engine.delete_nodes_by_prefix. |
| ERS-D3 | ERS-0 | D | A statement entry is the ledger's note that one edge is live. | inspected:iris_src/src/Graph/KG/Ledger.cls:8-9 | docs/adr/0004-erasure-removes-content-not-history.md | ^IVG.Ledger("stmt", id) and its ^IVG.Ledger("tuple", s, p, o, key). |
| ERS-D4 | ERS-0 | D | A commit is the command that saves a changeset as the next revision. | inspected:iris_src/src/Graph/KG/Ledger.cls:397-415 | specs/213-graph-revision-ledger | Same meaning as LED-D4. |
| ERS-D5 | ERS-0 | D | The ledger lock is the lock a process holds while it adds a revision. | inspected:iris_src/src/Graph/KG/Ledger.cls:440-444 | specs/213-graph-revision-ledger | Same meaning as LED-D3. |
| ERS-B1 | ERS-D1 | B | A graph erasure removes the graph's rows from every table that holds them. | inspected:iris_src/src/Graph/KG/Eraser.cls:113-205; tested:tests/integration/test_erase_graph.py::test_erase_removes_the_sql_rows; live:native-mixed_tenant_flow | docs/adr/0004-erasure-removes-content-not-history.md | Labels, props, docs, vectors, routed tables, FHIR rows, reifications, edge vectors, edges, nodes; both spellings of the default graph (COALESCE). |
| ERS-B1.1 | ERS-B1 | B | It also removes the graph's entries from the native indexes. | inspected:iris_src/src/Graph/KG/Eraser.cls:218-255; tested:tests/integration/test_erase_graph.py::test_erase_removes_the_structural_adjacency; tested:tests/integration/test_erase_graph.py::test_erase_removes_the_temporal_index | docs/adr/0004-erasure-removes-content-not-history.md | ^KG out/in/gen/degc through Adjacency.RemoveGraph, the temporal index, prop/label/deg2p subtrees, graph mode, algorithm cache. |
| ERS-D3a | ERS-B1 | D | A statement entry is the ledger's note that one edge is live. | inspected:iris_src/src/Graph/KG/Ledger.cls:8-9 | docs/adr/0004-erasure-removes-content-not-history.md | Same meaning as ERS-D3. Local restatement for the literal term-scope rule (HD-0001). |
| ERS-B1.2 | ERS-B1 | B | It removes every statement entry of the graph, live or closed. | inspected:iris_src/src/Graph/KG/Eraser.cls:1117-1144; tested:tests/integration/test_edgescan_ledger_erase.py::test_erasing_a_graph_removes_its_ledger_statements_and_leaves_other_graphs | docs/adr/0004-erasure-removes-content-not-history.md | EraseLedgerFor: one pass over ("stmt"), tuple keys derived from each entry. |
| ERS-B1.3 | ERS-B1 | B | It keeps every ledger record. | inspected:iris_src/src/Graph/KG/Eraser.cls:26-33; live:native-mixed_tenant_flow | docs/adr/0004-erasure-removes-content-not-history.md | One revision's records can belong to several graphs. Live: records byte-identical before and after the erasure. |
| ERS-B1.4 | ERS-B1 | B | It returns how many rows of nodes and edges it removed. Zero means nothing matched. | inspected:iris_src/src/Graph/KG/Eraser.cls:37-44; tested:tests/integration/test_erase_graph.py::test_erasing_a_graph_with_no_content_returns_zero | docs/adr/0004-erasure-removes-content-not-history.md | |
| ERS-B1.5 | ERS-B1 | B | Erasing one graph leaves every other graph as it was. | tested:tests/integration/test_erase_graph.py::test_erasing_one_graph_leaves_another_untouched; live:native-mixed_tenant_flow | CONTEXT.md:33-37 | Live: tenant B's content unchanged after tenant A's erasure. |
| ERS-X1 | ERS-B1 | X | A graph whose name cannot be stored is refused before anything changes. | inspected:iris_src/src/Graph/KG/Eraser.cls:49-51; tested:tests/integration/test_erase_graph.py::test_a_rejected_graph_name_raises_before_anything_is_deleted | docs/adr/0003-two-graph-key-derivations.md | GraphKey.ForIndex and ForName before TSTART. |
| ERS-I1 | ERS-B1 | I | A graph erasure finishes in full or changes nothing. | inspected:iris_src/src/Graph/KG/Eraser.cls:56-261; tested:tests/integration/test_eraser_failures.py::test_a_refused_delete_erases_nothing; assumed:P-0001; live:C-live-erase-vs-commit-fk | docs/adr/0004-erasure-removes-content-not-history.md | One TSTART/TCOMMIT; any failure rolls back and throws. |
| ERS-D4a | ERS-I1 | D | A commit is the command that saves a changeset as the next revision. | inspected:iris_src/src/Graph/KG/Ledger.cls:397-415 | specs/213-graph-revision-ledger | Same meaning as ERS-D4. Local restatement for the literal term-scope rule (HD-0001). |
| ERS-T1 | ERS-I1 | T | Tables that hold only one graph's vectors are dropped after the erasure commits. | inspected:iris_src/src/Graph/KG/Eraser.cls:263-305 | docs/adr/0004-erasure-removes-content-not-history.md | The one named exception to ERS-I1: DDL is outside the transaction. A failed drop leaves an empty route. |
| ERS-B2 | ERS-D2 | B | A node erasure removes the matching nodes and every edge that touches them in that graph. | inspected:iris_src/src/Graph/KG/Eraser.cls:353-389; live:native-mixed_tenant_flow | docs/adr/0004-erasure-removes-content-not-history.md | The match is exact and case-sensitive. |
| ERS-D3b | ERS-B2 | D | A statement entry is the ledger's note that one edge is live. | inspected:iris_src/src/Graph/KG/Ledger.cls:8-9 | docs/adr/0004-erasure-removes-content-not-history.md | Same meaning as ERS-D3. Local restatement for the literal term-scope rule (HD-0001). |
| ERS-B2.1 | ERS-B2 | B | It removes the statement entry of each edge it removes. | inspected:iris_src/src/Graph/KG/Eraser.cls:665-678 | docs/adr/0004-erasure-removes-content-not-history.md | EraseEdgeRow kills ("tuple") and its live ("stmt"). Closed entries of the node's old edges stay. |
| ERS-X2 | ERS-B2 | X | A node erasure with an empty prefix is refused. | inspected:iris_src/src/Graph/KG/Eraser.cls:322-326; inspected:iris_vector_graph/_engine/nodes_edges.py:1553-1558 | docs/adr/0004-erasure-removes-content-not-history.md | Use a graph erasure instead. |
| ERS-I2 | ERS-D3 | I | After an erasure, no statement entry claims an edge that has no row. | inspected:iris_src/src/Graph/KG/Eraser.cls:1117-1144; live:native-mixed_tenant_flow; live:native-killed_at_random; mc:erasure-reviewed; mc:C-core-m1-as-built-isolation-stmt-a; mc:C-core-m1-as-built-isolation-stmt-b; mc:C-core-m1-as-built-isolation-stmt-c | docs/adr/0004-erasure-removes-content-not-history.md | ADR-0004's invariant. Checked live after every step of every scenario (L2 check "live statement without its row"). Completion: mc:C-core-m1-as-built-isolation-stmt-a/b/c check the as-built model sequentially (no concurrent erasure or commit), profiles a-c, exhaustive within bounds. |
| ERS-I3 | ERS-I2 | I | After an erasure, each live edge the ledger saved still has its statement entry. | finding:F-1201; mc:erasure-as-built [model-only]; mc:erasure-reviewed [model-only]; mc:C-core-m1-as-built-isolation-stmt-a [model-only]; mc:C-core-m1-as-built-isolation-stmt-b [model-only]; mc:C-core-m1-as-built-isolation-stmt-c [model-only] | docs/adr/0004-erasure-removes-content-not-history.md | The converse of ERS-I2. Fails when a commit into the graph lands between the erasure's row delete and its ledger cleanup: the cleanup kills the new edge's entry and the edge stays live. Completion: mc:C-core-m1-as-built-isolation-stmt-a/b/c check the as-built model sequentially (no concurrent erasure or commit), profiles a-c, exhaustive within bounds. |
| ERS-D1a | ERS-I3 | D | A graph erasure removes all of one graph's content. | inspected:iris_src/src/Graph/KG/Eraser.cls:37-47; inspected:iris_vector_graph/_engine/nodes_edges.py:1473-1527 | docs/adr/0004-erasure-removes-content-not-history.md | Same meaning as ERS-D1. Local restatement for the literal term-scope rule (HD-0001). |
| ERS-D4b | ERS-I3 | D | A commit is the command that saves a changeset as the next revision. | inspected:iris_src/src/Graph/KG/Ledger.cls:397-415 | specs/213-graph-revision-ledger | Same meaning as ERS-D4. Local restatement for the literal term-scope rule (HD-0001). |
| ERS-D5a | ERS-I3 | D | The ledger lock is the lock a process holds while it adds a revision. | inspected:iris_src/src/Graph/KG/Ledger.cls:440-444 | specs/213-graph-revision-ledger | Same meaning as ERS-D5. Local restatement for the literal term-scope rule (HD-0001). |
| ERS-T2 | ERS-I3 | T | A graph erasure takes no ledger lock, so commits into the same graph do not wait for it. | inspected:iris_src/src/Graph/KG/Eraser.cls:47-261; finding:F-1201 | docs/adr/0004-erasure-removes-content-not-history.md | Its adjacency lock is shared (Adjacency.cls:428-447), so writers do not wait either. |
| ERS-P1 | ERS-I3 | P | A delete that meets a row another transaction holds waits for that transaction. | assumed:P-1201 | iris_src/src/Graph/KG/Eraser.cls | IRIS SQL row locks. The erasure model relies on it: an erasure cannot remove a row a commit has not finished. |
| ERS-Q1 | ERS-I3 | Q | Should a graph erasure hold the ledger lock so commits into the graph wait? | open:HD-1201; mc:erasure-reviewed | model/src/erasure.rs | The reviewed design (erasure holds the ledger lock) passes the model exhaustively. |
| ERS-B3 | ERS-0 | B | After an erasure alone, a replay of the ledger still holds what was erased. | proved:theorem_erasure_alone_diverges; tested:tests/integration/test_256_ledger_redaction_e2e.py::test_verify_diverges_after_the_erase_alone_and_is_equal_after_the_redaction; live:native-mixed_tenant_flow | specs/256-ledger-tenant-redaction/plan.md | So verify reports a divergence until the target is redacted (module RED). |
| ERS-B4 | ERS-B3 | B | Erasure alone is not a privacy step: the ledger still names the erased ids. | live:native-mixed_tenant_flow; tested:tests/integration/test_256_ledger_redaction_e2e.py::test_the_scan_sees_tenant_a_after_the_erase_alone | docs/adr/0004-erasure-removes-content-not-history.md | ADR-0004 Consequences. |
| ERS-B5 | ERS-0 | B | Ledger node records name no graph, so a node erasure in the default graph is how a tenant's nodes leave. | inspected:iris_src/src/Graph/KG/LedgerApply.cls:215-251; live:native-mixed_tenant_flow | docs/adr/0013-redaction-removes-content-from-history.md | The full erasure of a tenant whose edges live in its own graph is erase_graph(graph) plus delete_nodes_by_prefix(prefix). |
| ERS-B6 | ERS-0 | B | A ledger delete of a node removes it from the default graph only. | inspected:iris_src/src/Graph/KG/LedgerApply.cls:374-418; live:native-mixed_tenant_flow; finding:F-1401 | iris_src/src/Graph/KG/LedgerApply.cls | 4.6.0 R290: the node's rows and edges in a named graph stay. Live: tenantA\|n3's row and edge in gTenantA outlived its detach delete, and verify diverged before any erasure. |

## Cells

Entity graph content: states live, being erased, erased; commands erase the graph, erase nodes by prefix, commit into the graph, write outside the ledger, redact

| Entity | State | Command | Outcome | Statements | Decision |
|---|---|---|---|---|---|
| graph content | live | erase the graph | ok | ERS-B1 | |
| graph content | live | erase nodes by prefix | ok | ERS-B2 | |
| graph content | live | commit into the graph | ok | ERS-B5 | |
| graph content | live | write outside the ledger | ok | ERS-B1 | |
| graph content | live | redact | refused | RED-X1 | |
| graph content | being erased | erase the graph | ok | ERS-P1 | |
| graph content | being erased | erase nodes by prefix | ok | ERS-P1 | |
| graph content | being erased | commit into the graph | open | | HD-1201 |
| graph content | being erased | write outside the ledger | open | | HD-1201 |
| graph content | being erased | redact | open | | HD-1201 |
| graph content | erased | erase the graph | no-op | ERS-B1.4 | |
| graph content | erased | erase nodes by prefix | no-op | ERS-B1.4 | |
| graph content | erased | commit into the graph | ok | RED-B1.1 | |
| graph content | erased | write outside the ledger | ok | RED-B5.2 | |
| graph content | erased | redact | ok | RED-B2 | |
