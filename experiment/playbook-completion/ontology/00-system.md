# 00 System root

Module: SYS
Root: SYS-0
Scope: The whole product at pin 3eaa79cf: the Python package iris_vector_graph, the IRIS classes under
iris_src/src, the HTTP and GraphQL API under api, and the SQL under sql. This file holds the terms every module
uses and the universal rules (playbook §3.3a step 1) that every module's statements trace to.

## Glossary

| Term | Defined by | Restated by |
|---|---|---|
| namespace | SYS-D1 | |
| schema | SYS-D2 | |
| graph | SYS-D3 | |
| default graph | SYS-D4 | |
| named graph | SYS-D5 | |
| node | SYS-D6 | |
| edge | SYS-D7 | |
| label | SYS-D8 | |
| property | SYS-D9 | |
| qualifier | SYS-D10 | |
| content | SYS-D11 | |
| store | SYS-D12 | |
| live | SYS-D13 | |
| tenant | SYS-D14 | |
| engine | SYS-D15 | |
| server code | SYS-D16 | |
| process | SYS-D17 | |
| transaction | SYS-D18 | |
| lock | SYS-D19 | |
| operator | SYS-D20 | |
| ledger | SYS-D21 | |
| changeset | SYS-D22 | |
| revision | SYS-D23 | |
| record | SYS-D24 | |
| retry key | SYS-D25 | |
| erasure | SYS-D26 | |
| redaction | SYS-D27 | |
| tombstone | SYS-D28 | |
| vector | SYS-D29 | |
| width | SYS-D30 | |
| vector table | SYS-D31 | |
| replay | SYS-D32 | |

## Statements

| Id | Parent | Kind | Statement | Evidence | Source | Notes |
|---|---|---|---|---|---|---|
| SYS-0 | - | R | The product keeps linked data in IRIS and answers questions about it. | inspected:iris_vector_graph/engine.py:1-8 | README.md; CONTEXT.md:1-10 | Root of every module. Module roots name SYS-0 as parent. |
| SYS-D1 | SYS-0 | D | A namespace is one IRIS data space that holds one install of the product. | inspected:iris_vector_graph/schema_name.py:1-8 | CONTEXT.md:14-19; docs/adr/0016-one-ivg-schema-per-namespace.md | The glossary's "isolation unit". Globals outside SQL belong to the namespace. |
| SYS-D2 | SYS-0 | D | The schema is the one SQL schema in a namespace that holds all the product's tables. | inspected:iris_vector_graph/schema_name.py:1-21 | CONTEXT.md:20-26 | Graph_KG unless chosen at install; recorded in ^IVG.Deploy("schema"). |
| SYS-D3 | SYS-0 | D | A graph is a named part of the data. Each piece of data belongs to one graph. | inspected:iris_src/src/Graph/KG/GraphKey.cls:51-77 | CONTEXT.md:27-32 | Graphs are partitions inside the schema, not SQL schemas. |
| SYS-D4 | SYS-0 | D | The default graph is the graph with the empty name. A read or write that names no graph uses it. | inspected:iris_src/src/Graph/KG/GraphKey.cls:51-56 | CONTEXT.md:27-32 | Spelled '' or NULL in SQL, integer 0 in ^KG and $Char(1) in ^IVG.Ledger (ADR-0003). |
| SYS-D5 | SYS-0 | D | A named graph is any graph whose name is not empty. | inspected:iris_src/src/Graph/KG/GraphKey.cls:65-69 | CONTEXT.md:33-37 | Names "0" and control characters are refused (GraphKey.Validate). |
| SYS-D6 | SYS-0 | D | A node is one thing in a graph, known by its id. | inspected:iris_vector_graph/schema.py:395-402 | CONTEXT.md:27-32 | Graph_KG.nodes is unique on (graph_id, node_id) since spec 230, so one id can name a node in two graphs. |
| SYS-D7 | SYS-0 | D | An edge is a typed link from one node to another node in the same graph. | inspected:iris_vector_graph/schema.py:34-45 | CONTEXT.md:60-64 | The glossary's Structural Edge; Graph_KG.rdf_edges (s, p, o_id, graph_id, qualifiers). |
| SYS-D8 | SYS-0 | D | A label is a name that marks a node as a kind of thing. | inspected:iris_vector_graph/schema.py:403-410 | CONTEXT.md:88-96 | Graph_KG.rdf_labels. |
| SYS-D9 | SYS-0 | D | A property is a key and a value kept on a node. | inspected:iris_vector_graph/schema.py:411-420 | CONTEXT.md:88-96 | Graph_KG.rdf_props; keys id and __graph are reserved. |
| SYS-D10 | SYS-0 | D | A qualifier is a key and a value kept on an edge. | inspected:iris_vector_graph/schema.py:34-45 | CONTEXT.md:60-64 | The qualifiers column of rdf_edges (JSON). |
| SYS-D11 | SYS-0 | D | Content is the data a graph holds: its nodes, edges, labels, properties and the like. | inspected:iris_src/src/Graph/KG/Eraser.cls:37-46 | CONTEXT.md:198-208 | Also temporal edges, vectors and text documents (modules TMP, VEC, TXT). |
| SYS-D12 | SYS-0 | D | A store is one place that holds content, such as a table or a native index. | inspected:iris_src/src/Graph/KG/Eraser.cls:13-17 | CONTEXT.md:121-128 | Graph.KG.GraphStores is the inventory of stores. |
| SYS-D13 | SYS-0 | D | Content is live while some store still holds it. | inspected:iris_src/src/Graph/KG/LedgerRedact.cls:143-178 | docs/adr/0013-redaction-removes-content-from-history.md | Redaction's liveness check reads nodes, rdf_labels, rdf_props and rdf_edges. |
| SYS-D14 | SYS-0 | D | A tenant is one customer. Each tenant's content must stay apart from the others. | inspected:tests/integration/test_256_ledger_redaction_e2e.py:1-16 | specs/256-ledger-tenant-redaction/spec.md; docs/dev/notes/for-opsreview/IVG-OPSREVIEW-BRIEF.md | The product has no tenant object. A tenant is a named graph plus a node id prefix in the default graph (spec 256). |
| SYS-D15 | SYS-0 | D | The engine is the Python object a caller uses to reach the product. | inspected:iris_vector_graph/engine.py:17-40 | docs/API_REFERENCE.md | IRISGraphEngine, a facade over the _engine mixins. |
| SYS-D16 | SYS-0 | D | Server code is the product code that runs inside IRIS. | inspected:iris_src/src/Graph/KG/Ledger.cls:1-18 | docs/architecture/ARCHITECTURE.md | ObjectScript classes Graph.KG.*, deployed into the namespace. |
| SYS-D17 | SYS-0 | D | A process is one running job inside IRIS. | inspected:iris_src/src/Graph/KG/Ledger.cls:397-415 | docs/adr/0004-erasure-removes-content-not-history.md | Each DBAPI or Native API connection is served by one IRIS process. |
| SYS-D18 | SYS-0 | D | A transaction is a group of writes that the database keeps all together or not at all. | inspected:iris_src/src/Graph/KG/Ledger.cls:397-415 | docs/adr/0004-erasure-removes-content-not-history.md | TSTART / TCOMMIT / TROLLBACK; SQL and global writes of one process share it. |
| SYS-D19 | SYS-0 | D | A lock is a claim that one process holds so that other processes wait. | inspected:iris_src/src/Graph/KG/Ledger.cls:440-444 | docs/adr/0013-redaction-removes-content-from-history.md | IRIS LOCK; the ledger head lock is Lock +^IVG.Ledger("head") with a 30 s timeout. |
| SYS-D20 | SYS-0 | D | An operator is a person who runs and repairs an install. | inspected:iris_vector_graph/cli.py:1-20 | docs/ADMIN_GUIDE.md | |
| SYS-D21 | SYS-0 | D | The ledger is the saved history of changes to graphs, in order. | inspected:iris_src/src/Graph/KG/Ledger.cls:1-17 | CONTEXT.md:193-197; specs/213-graph-revision-ledger | Optional; enabled per namespace. ^IVG.Ledger and Graph_KG.ledger_revisions. |
| SYS-D22 | SYS-0 | D | A changeset is a list of changes that a caller sends to the ledger to save as one unit. | inspected:iris_vector_graph/ledger/changeset.py:96-108 | CONTEXT.md:188-192 | Python Changeset; ops plus actor, message, source, correlation id, expected head, retry key. |
| SYS-D23 | SYS-0 | D | A revision is one saved changeset. It has a number, an id, and some free text such as a message. | inspected:iris_src/src/Graph/KG/Ledger.cls:532-567 | CONTEXT.md:183-187 | Row of Graph_KG.ledger_revisions keyed by seq; free text is message, source, correlation_id, idempotency_key. |
| SYS-D24 | SYS-0 | D | A record is one change inside a revision. It keeps a fixed place in that revision. | inspected:iris_src/src/Graph/KG/Ledger.cls:7-8 | specs/213-graph-revision-ledger | ^IVG.Ledger("rec", seq, ordinal) = $LB(op, kind, id, attr, prior, new, graph, flags). The graph is per record. |
| SYS-D25 | SYS-0 | D | A retry key is a name a caller gives a changeset, so that sending it twice saves it once. | inspected:iris_src/src/Graph/KG/Ledger.cls:454-473 | specs/213-graph-revision-ledger | The idempotency key; ^IVG.Ledger("idem", key) = $LB(seq, fingerprint). |
| SYS-D26 | SYS-0 | D | Erasure removes a graph's content, or some of its nodes, from every store. | inspected:iris_src/src/Graph/KG/Eraser.cls:1-35; finding:F-1502 | CONTEXT.md:198-208; docs/adr/0004-erasure-removes-content-not-history.md | Module ERS. Erasure keeps the ledger's records. |
| SYS-D27 | SYS-0 | D | Redaction removes erased content from the ledger. It keeps the history in its old shape. | inspected:iris_src/src/Graph/KG/LedgerRedact.cls:1-29 | CONTEXT.md:209-214; docs/adr/0013-redaction-removes-content-from-history.md | Module RED. |
| SYS-D28 | SYS-0 | D | A tombstone is what a record becomes after redaction. It keeps its place and holds no content. | inspected:iris_src/src/Graph/KG/LedgerRedact.cls:332-347 | CONTEXT.md:215-220 | $LB("redacted", sha256 digest, flags, op, entityKind). |
| SYS-D29 | SYS-0 | D | A vector is a list of numbers that stands for the meaning of a node, an edge or a text. | inspected:iris_vector_graph/schema.py:429-437 | CONTEXT.md:154-157 | Promoted from VEC-D1 during consolidation: modules ALG, API, INT, LED and WRT use the term. |
| SYS-D30 | SYS-0 | D | The width of a vector is how many numbers it holds. | inspected:iris_vector_graph/schema.py:2063-2103 | docs/adr/0005-vector-width-is-not-declared-in-to-vector.md | Promoted from VEC-D2. |
| SYS-D31 | SYS-0 | D | A vector table is a table that keeps one vector per row. | inspected:iris_vector_graph/constants.py:27-31 | docs/migration/v4.0.0.md:97-128 | Promoted from VEC-D6. |
| SYS-D32 | SYS-0 | D | Replay rebuilds nodes and edges by applying the ledger's records in order. | inspected:iris_vector_graph/ledger/replay.py:155-210 | specs/256-ledger-tenant-redaction/spec.md | Promoted from RPL-D1: the erasure, redaction and replay modules all use it. |
| SYS-I1 | SYS-0 | I | Each kind of fact has one owner, and only that owner writes it. | inspected:iris_src/src/Graph/KG/Adjacency.cls:1-20; inspected:iris_src/src/Graph/KG/GraphKey.cls:51-77; inspected:iris_src/src/Graph/KG/Eraser.cls:1-17; finding:F-1114 | docs/adr/0011-the-adjacency-index-has-one-writer-module.md; docs/adr/0003-two-graph-key-derivations.md | Universal axiom U1. Each module root names the facts it owns. |
| SYS-I2 | SYS-0 | I | Content of one graph never shows up in an answer about another graph. | inspected:iris_src/src/Graph/KG/GraphKey.cls:51-77; inspected:iris_src/src/Graph/KG/Eraser.cls:113-125; finding:F-0106; finding:F-1002; finding:F-1502; finding:F-1507; finding:F-1603; finding:F-1701 | CONTEXT.md:33-37; CONTEXT.md:50-59; docs/adr/0001-graph-key-as-first-subscript.md | Universal axiom U2. All-graphs reads are the union of each graph's own answer (CONTEXT.md:38-43). |
| SYS-I3 | SYS-0 | I | A refused command leaves every store as it was. | inspected:iris_src/src/Graph/KG/Ledger.cls:397-415; inspected:iris_src/src/Graph/KG/LedgerRedact.cls:185-211; finding:F-0615; finding:F-0704; finding:F-C0702; finding:F-1511 | docs/adr/0004-erasure-removes-content-not-history.md | Universal axiom U3. |
| SYS-I4 | SYS-0 | I | A command that writes to more than one store writes to all of them or to none. | inspected:iris_src/src/Graph/KG/Eraser.cls:47-260; inspected:iris_src/src/Graph/KG/Ledger.cls:397-415; finding:F-C1501; finding:F-C1502; finding:F-1609 | docs/adr/0004-erasure-removes-content-not-history.md | Universal axiom U4. Exceptions are named per module (EraseGraph drops routed tables after its commit). |
| SYS-I5 | SYS-0 | I | The ledger only grows. A saved record changes only when redaction turns it into a tombstone. | inspected:iris_src/src/Graph/KG/LedgerRevision.cls:77-123; inspected:iris_src/src/Graph/KG/LedgerRedact.cls:332-347; finding:F-1801 | docs/adr/0013-redaction-removes-content-from-history.md | Universal axiom U5. PurgeAll is a test and admin reset outside this rule. |
| SYS-I6 | SYS-0 | I | A retry with the same retry key gets the first answer or a clear refusal. It never saves twice. | inspected:iris_src/src/Graph/KG/Ledger.cls:454-473 | specs/213-graph-revision-ledger; docs/adr/0013-redaction-removes-content-from-history.md | Universal axiom U6. |
| SYS-I7 | SYS-0 | I | Each change the ledger governs is saved in the same transaction as its record. | inspected:iris_src/src/Graph/KG/Ledger.cls:387-415 | specs/213-graph-revision-ledger | Universal axiom U7 (spec 213 FR-047). |
| SYS-I8 | SYS-0 | I | A store that is built from other stores either matches them or says it is out of date. | inspected:iris_src/src/Graph/KG/Adjacency.cls:20-35; finding:F-1005 | CONTEXT.md:109-120 | Universal axiom U8 (rebuilt stores, graph-version token). |
| SYS-I9 | SYS-0 | I | Every refusal says why it was refused. | inspected:iris_src/src/Graph/KG/Ledger.cls:61-70; inspected:iris_vector_graph/ledger/errors.py:1-40; finding:F-1506; finding:F-C1602 | docs/dev/TESTING_POLICY.md | Universal axiom U9. |
| SYS-I10 | SYS-0 | I | A namespace holds one install of the product, under one schema. | inspected:iris_vector_graph/schema_name.py:1-8 | docs/adr/0016-one-ivg-schema-per-namespace.md | Universal axiom U10. Two tenants that must not share an index or a ledger use two namespaces. |
| SYS-P1 | SYS-0 | P | When a process stops, IRIS undoes the writes of its open transaction. | assumed:P-0001 | docs/adr/0004-erasure-removes-content-not-history.md | Interruption safety of every batch rests on it. |
| SYS-P2 | SYS-0 | P | Other processes can read a new value before the writer's transaction ends. | assumed:P-0002 | docs/dev/notes | Globals have no read isolation; SQL default isolation in IRIS reads uncommitted data. |
| SYS-P3 | SYS-0 | P | A lock freed inside a transaction stays held until that transaction ends. | assumed:P-0003 | iris_src/src/Graph/KG/Ledger.cls | Commit releases the head lock before TCOMMIT and relies on this (Ledger.cls:390-404). |
| SYS-P4 | SYS-0 | P | When a process stops, IRIS frees every lock it held. | assumed:P-0004 | iris_src/src/Graph/KG/Ledger.cls | |
