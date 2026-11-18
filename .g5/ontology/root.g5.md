# iris-vector-graph

iris-vector-graph (IVG) stores and queries graph data in an InterSystems IRIS namespace. It supports openCypher, timestamped edges, vector and text search, and an optional revision ledger. This ontology describes IVG 4.7.0 at `3eaa79cf`.

<a id="top-level-topics"></a>
## How the pages are organized

Choose a page by the question you want answered.

| Category | What belongs here | Example for a graph query |
|---|---|---|
| Concept | Shared terms, policies and invariants that several workflows rely on. | What does omitting `USE GRAPH` mean? A read combines the answers from each graph. The write rules depend on the clause. [Graph scope](concepts/graph-scope.g5.md#graph.all_graphs_read) |
| Architecture | Which component owns the work, how it carries it out and when it takes another path. | How does IVG decide between SQL and the native executor? [Query routing](architecture/query-execution.g5.md#query.native.route) |
| Operation | How to install, configure, inspect or repair IVG and its namespace. | What does this namespace report as ready before I serve queries? [Readiness checks](operations/status-and-repair.g5.md#install.status.readiness) |
| Feature | An action a caller can take on graph data and the result, refusal or failure they can observe. | How can I label results by graph? Run the query once per graph with `USE GRAPH`. [Graph identity in result rows](features/cypher.g5.md#query.graph-scope.row-graph) |

<a id="definitions"></a>
The [graph scope page](concepts/graph-scope.g5.md#definitions) defines namespaces, graphs and the default graph. The [ledger glossary](features/ledger.g5.md#definitions) defines revisions and changesets.

<a id="how-the-major-capabilities-fit-together"></a>
## Work with graph data

- [Write nodes and relationships](features/graph-structure.g5.md) or [record timestamped events](features/temporal.g5.md). With the ledger enabled, see [which changes commit together](features/ledger.g5.md#ledger.commit) and [which properties are written afterward](features/ledger.g5.md#ledger.commit.post-commit).
- [Run Cypher](features/cypher.g5.md), [search vectors and text](features/search.g5.md), or [run a graph algorithm](features/algorithms.g5.md). See [client interfaces](features/client-interfaces.g5.md) and [access policies](concepts/access.g5.md) for connection and permission rules.
- [Import, validate or export graph data](features/data-interchange.g5.md), or [project a FHIR repository into a graph](features/fhir.g5.md).
- [Erase live graph data](features/erasure.g5.md), then [redact retained ledger content](features/redaction.g5.md) when required. See [how to resume an interrupted redaction](features/redaction.g5.md#redaction.batches.resume).

## Maintain a namespace

[Set up or upgrade IVG](operations/setup-and-upgrade.g5.md) · [Check status or repair an index](operations/status-and-repair.g5.md) · [Restore a snapshot or load data in bulk](operations/snapshots-and-bulk-load.g5.md) · [Manage search indexes](operations/search-indexes.g5.md) · [Administer and verify the ledger](operations/ledger.g5.md)

## Follow the implementation

[Cypher execution](architecture/query-execution.g5.md) · [Adjacency and derived data](architecture/adjacency-and-derived-data.g5.md) · [Algorithm execution](architecture/algorithm-execution.g5.md) · [Search storage and indexes](architecture/search-storage-and-indexes.g5.md) · [IRIS adapters](architecture/adapters.g5.md)

<a id="where-the-detailed-statements-are"></a>
## Sources and verification

**I** marks intent. **D** marks a design decision. Metadata links each statement to its sources and any applicable findings, questions and models. A working assumption is provisional. The coverage map gives the scope and premises of each model result and identifies the product behavior observed on IRIS. [Coverage map](../Verus_verification/coverage.md) · [Findings](../Verus_verification/findings.md) · [Open questions](../Verus_verification/open_questions.md) · [Playbook module map](../Verus_verification/runbook.md#playbook-module-map) · [Statement crosswalk](../Verus_verification/crosswalk/statements.tsv)

<a id="not-covered"></a>
The [AQL statement](features/cypher.g5.md#query.aql) covers depth and null translation and the handoff to Cypher. AQL traversal execution remains unproved. For read APIs such as `count_nodes`, `list_graphs` and `get_nodes_by_label`, use the shared graph-scope rules and consult the playbook for API detail. The module map also points to further detail on GraphQL and openCypher translation.
