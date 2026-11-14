# iris-vector-graph

iris-vector-graph (IVG) is a graph database that runs inside InterSystems IRIS. It stores nodes and typed relationships in SQL tables and native indexes, adds timestamped events, vectors and text search, answers openCypher queries, and can keep an append-only history of every recorded change. Python is the main interface; ObjectScript classes own most transactions that span SQL and IRIS globals. This ontology recovers the product's governing contract at release 4.7.0 (commit `3eaa79cf`).

## Definitions

- **Namespace**: the IRIS namespace IVG is installed in. It is the isolation unit: one namespace holds one install.
- **Graph**: a named partition of the data. The **default graph** is the one with the empty name.
- **Ledger**: the optional, append-only revision history. A **revision** records one committed **changeset**.
- **Erasure**: removing live content from every store that holds it.
- **Redaction**: removing an erased target's content from the ledger's history while keeping its shape.

## Top-level topics

Each topic owns the statements with its prefix.

| Prefix | What it covers | Page |
|---|---|---|
| `graph.` | Graphs, graph keys and what a read or write that names no graph means | [Graph scope](concepts/graph-scope.g5.md) |
| `structure.` | Nodes, relationships, parallel edges, the adjacency index, degree and rebuilt stores | [Graph structure](features/graph-structure.g5.md) |
| `ledger.` | Revisions, commits, retries, strict mode, verification and the history readers | [Revision ledger](features/ledger.g5.md) |
| `erasure.` | Removing a graph's, a prefix's or some nodes' content from every store | [Erasure](features/erasure.g5.md) |
| `redaction.` | Removing an erased tenant's content from the ledger's history | [Redaction](features/redaction.g5.md) |
| `temporal.` | Timestamped edges, their statistics and their structural rows | [Temporal edges](features/temporal.g5.md) |
| `search.` | Embeddings, vector routes, BM25 text search and result fusion | [Search](features/search.g5.md) |
| `query.` | openCypher execution: the SQL path, the native executor and compiled plans | [Cypher](features/cypher.g5.md) |
| `install.` | The IVG schema per namespace, setup, upgrades, legacy objects, snapshots and bulk loads | [Install and upgrade](concepts/install.g5.md) |
| `access.` | Network entry points, authentication and which write paths the ledger governs | [Access](concepts/access.g5.md) |
| `fhir.` | Projecting a FHIR repository into a graph | [FHIR](features/fhir.g5.md) |
| `algorithms.` | Graph algorithms, accelerated native readers and cached answers | [Algorithms](features/algorithms.g5.md) |

## How the major capabilities fit together

- A caller writes nodes, relationships and events into a graph, either directly or as a ledger changeset. With the ledger enabled, a changeset becomes one revision and its writes commit together; only its [post-commit properties](features/ledger.g5.md#ledger.commit.post-commit) are written after the revision.
- Readers traverse the adjacency index, run Cypher, search vectors and text, read time windows and run algorithms. Derived stores serve a cached answer only while it is still current.
- Removing a tenant takes two steps. Erasure removes live content, and redaction then removes that content from the ledger's history. The redaction page describes the order, refusals and recovery.
- Verification evidence and the coverage of each statement are in the [Verus verification foundation](../Verus_verification/runbook.md) and its [coverage map](../Verus_verification/coverage.md). Product bugs, proposed simplifications and open questions found during the uplift are indexed in the [findings register](../Verus_verification/findings.md).

## Not covered

The engine's read API outside Cypher (`get_node`, `get_nodes`, `count_nodes`, `list_graphs` and `get_nodes_by_label`) and the exports (`export_graph_ndjson`, `export_rdf`, `prov_export`) have no owning statement. Their graph scope follows [graph scope](concepts/graph-scope.g5.md); nothing else about them was recovered. Imports and inference are owned by [install.import](concepts/install.g5.md#install.import).
