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
| `install.` | The IVG schema per namespace, status reports, setup, upgrades, legacy objects, snapshots and bulk loads | [Install and upgrade](concepts/install.g5.md) |
| `access.` | Network entry points, authentication and which write paths the ledger governs | [Access](concepts/access.g5.md) |
| `adapters.` | How Python code reaches IRIS: the embedded cursor inside IRIS and its no-row rule | [Adapters](concepts/adapters.g5.md) |
| `fhir.` | Projecting a FHIR repository into a graph | [FHIR](features/fhir.g5.md) |
| `algorithms.` | Graph algorithms, accelerated native readers and cached answers | [Algorithms](features/algorithms.g5.md) |

## How the major capabilities fit together

- A caller writes nodes, relationships and events into a graph, either directly or as a ledger changeset. With the ledger enabled, a changeset becomes one revision and its writes commit together; only its [post-commit properties](features/ledger.g5.md#ledger.commit.post-commit) are written after the revision.
- Readers traverse the adjacency index, run Cypher, search vectors and text, read time windows and run algorithms. Derived stores serve a cached answer only while it is still current.
- Removing a tenant takes two steps. Erasure removes live content, and redaction then removes that content from the ledger's history. The redaction page describes the order, refusals and recovery.
- Verification evidence and the coverage of each statement are in the [Verus verification foundation](../Verus_verification/runbook.md) and its [coverage map](../Verus_verification/coverage.md). Product bugs, proposed simplifications and open questions found during the uplift are indexed in the [findings register](../Verus_verification/findings.md).

## Where the detailed statements are

This ontology is the governing contract. The playbook uplift kept a more detailed statement table per module, with inspected line ranges and test evidence for each row; it is preserved unchanged under `experiment/playbook-completion/ontology/`. Each of its modules maps to the pages below; the [statement crosswalk](../Verus_verification/crosswalk/statements.tsv) links individual blocks to statement IDs, and the [sweep log](../Verus_verification/crosswalk/ontology-sweep.tsv) shows which modules were compared row by row.

| Playbook module | Prefix | Pages here |
|---|---|---|
| [00 system](../../experiment/playbook-completion/ontology/00-system.md) | `SYS` | this page, [access](concepts/access.g5.md) |
| [01 install and schema](../../experiment/playbook-completion/ontology/01-install-schema.md) | `INS` | [install](concepts/install.g5.md) |
| [02 graph identity](../../experiment/playbook-completion/ontology/02-graph-identity.md) | `GID` | [graph scope](concepts/graph-scope.g5.md), [graph structure](features/graph-structure.g5.md) |
| [03 writes](../../experiment/playbook-completion/ontology/03-writes.md) | `WRT` | [graph structure](features/graph-structure.g5.md), [access](concepts/access.g5.md), [install: bulk loads](concepts/install.g5.md#install.bulk_load) |
| [04 adjacency](../../experiment/playbook-completion/ontology/04-adjacency.md) | `ADJ` | [graph structure](features/graph-structure.g5.md) |
| [05 temporal](../../experiment/playbook-completion/ontology/05-temporal.md) | `TMP` | [temporal](features/temporal.g5.md), [adjacency declaration](features/graph-structure.g5.md#structure.adjacency.declare) |
| [06 vectors](../../experiment/playbook-completion/ontology/06-vectors.md), [07 text search](../../experiment/playbook-completion/ontology/07-text-search.md) | `VEC`, `TXT` | [search](features/search.g5.md) |
| [08 Cypher on SQL](../../experiment/playbook-completion/ontology/08-cypher-sql.md), [09 native executor](../../experiment/playbook-completion/ontology/09-native-executor.md) | `CYP`, `NAT` | [Cypher](features/cypher.g5.md) |
| [10 algorithms](../../experiment/playbook-completion/ontology/10-algorithms.md) | `ALG` | [algorithms](features/algorithms.g5.md) |
| [11 ledger](../../experiment/playbook-completion/ontology/11-ledger.md), [14 replay](../../experiment/playbook-completion/ontology/14-replay.md) | `LED`, `RPL` | [ledger](features/ledger.g5.md) |
| [12 erasure](../../experiment/playbook-completion/ontology/12-erasure.md) | `ERS` | [erasure](features/erasure.g5.md) |
| [13 redaction](../../experiment/playbook-completion/ontology/13-redaction.md) | `RED` | [redaction](features/redaction.g5.md) |
| [15 integrations](../../experiment/playbook-completion/ontology/15-integrations.md) | `INT` | [FHIR](features/fhir.g5.md), [install: imports](concepts/install.g5.md#install.import) |
| [16 interfaces](../../experiment/playbook-completion/ontology/16-interfaces.md) | `API` | [access](concepts/access.g5.md) |
| [17 operations](../../experiment/playbook-completion/ontology/17-operations.md) | `OPS` | [install](concepts/install.g5.md), [access](concepts/access.g5.md), [adapters](concepts/adapters.g5.md) |
| [18 snapshot](../../experiment/playbook-completion/ontology/18-snapshot.md) | `SNP` | [install: snapshots](concepts/install.g5.md#install.snapshot) |

## Not covered

- The engine's `get_node` and `get_nodes` API is owned by [node reads](features/graph-structure.g5.md#structure.node.read). Other read APIs (`count_nodes`, `list_graphs`, `get_nodes_by_label`) and exports (`export_graph_ndjson`, `export_rdf`, `prov_export`) still lack a detailed owning block; their graph scope follows [graph scope](concepts/graph-scope.g5.md). The playbook's [02 graph identity](../../experiment/playbook-completion/ontology/02-graph-identity.md) and [16 interfaces](../../experiment/playbook-completion/ontology/16-interfaces.md) modules retain further detail.
- Imports and inference are owned by [install.import](concepts/install.g5.md#install.import).
- AQL depth/null translation and adapter handoff have a narrow [owner](features/cypher.g5.md#query.aql); its traversal execution remains unproved. The Bolt and HTTP servers, the GraphQL layer and the openCypher translator's semantics beyond the blocks on the [Cypher](features/cypher.g5.md) page have no detailed owner here; the playbook's 08, 09 and 16 modules hold the detail.
