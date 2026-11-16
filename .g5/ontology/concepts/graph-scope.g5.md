# Graph scope

Which graph a piece of content belongs to, how each store names a graph, and what a read or write that names no graph does. The structure kept inside a graph is described in [graph structure](../features/graph-structure.g5.md).

## Definitions

- **Graph**: a named partition of the content of one IVG install. It carries no type constraints.
- **Default graph**: the graph whose name is the empty string. In Python, `graph=None` and `graph=""` both name it.
- **Named graph**: a graph whose name is a non-empty string, such as `"acme-health"`.
- **Store**: one place IVG keeps graph content. There are three: the SQL tables, the native index (adjacency and temporal entries), and the revision ledger.
- **Graph key**: the value that identifies a graph inside one native store. It is derived from the graph's name.
- **Namespace**: the IRIS namespace that holds one IVG install, with its SQL schema and all of its native stores.
- **Interned snapshot**: a rebuilt copy of every graph's edges with each node ID numbered once (see [graph structure](../features/graph-structure.g5.md#definitions)).

## Membership and isolation

<a id="graph.membership"></a>
[I · graph.membership]

Every node, structural edge, temporal edge, aggregate and adjacency entry belongs to exactly one graph. The same node ID in two graphs is two nodes, each with its own labels, properties and edges, and an edge connects only nodes of its own graph.

<a id="graph.default"></a>
[I · graph.default]

A read or write that names no graph uses the default graph. In Python, a `graph=` argument that is omitted or None means the default graph, never every graph. These calls are the exceptions:

- A Cypher query without `USE GRAPH` reads every graph ([all-graphs read](#graph.all_graphs_read)) and writes as [all-graphs write](#graph.all_graphs_write) says.
- [RDF export](install.g5.md#install.export.rdf.scope) uses an omitted or None `graph_id` for every graph; an empty `graph_id` still selects only the default graph.
- The [status report](install.g5.md#install.status) counts core SQL rows across every graph; its census is separate from a graph-scoped node or edge count.
- Deleting nodes with `graph=` omitted, not None, deletes each ID from the one graph that holds it, meaning a graph with a node row or an edge row naming that ID.
- In that case an ID that no graph holds deletes nothing and reports False, and an ID that several graphs hold is refused before anything is deleted.
- Deleting an edge with `all_graphs` set deletes the triple from every graph.
- Deleting a reifier removes its rows in every graph ([reifications](../features/graph-structure.g5.md#structure.reification)).

- Working assumption: For graph-aware Python reads, omission selects the default graph. Keep the all-graph id helpers as separate discovery operations with their scope visible. Never hydrate ids from one scope with another scope's records. Model delete_node's 'holding graph or refuse' rule as its own documented operation.

<a id="graph.named"></a>
[I · graph.named]

Two graphs' content never shares an index entry, so content written to one named graph is never visible through another.

<a id="graph.tenants"></a>
[D · graph.tenants]

A graph keeps two datasets apart, but it is not a security boundary, because any caller can name any graph. Tenants that must not share an adjacency index or a revision ledger need separate namespaces, since those stores belong to the whole namespace.

## Graph keys

<a id="graph.key"></a>
[D · graph.key]

Inside each native store a graph is identified by a graph key derived from its name. The key is the first part of every graph-scoped entry, so reading or clearing one graph never has to visit another graph's entries.

<a id="graph.key.two_forms"></a>
[D · graph.key.two_forms]

The stores spell the default graph differently, and each spelling stays:

- In the native index the default graph's key is the number 0, and a named graph's key is its name.
- In the revision ledger the default graph's key is the control character with code 1, and a named graph's key is its name.
- In the SQL tables the default graph's name is the empty string. Older rows that leave the name missing (NULL) also mean the default graph.

<a id="graph.key.derive"></a>
[I · graph.key.derive]

Code that is about to touch a store derives that store's key from the graph name, and never converts one store's key into another's. A key used on the wrong store reads nothing and writes where no reader looks.

<a id="graph.key.owner"></a>
[D · graph.key.owner]

One module owns every graph-key derivation, including the SQL spelling of a graph's name, and no other code derives a key itself. The Python package keeps a single mirror of the native-index rule so it can reject a bad name before calling IRIS.

<a id="graph.no_fallthrough"></a>
[I · graph.no_fallthrough]

A lookup scoped to one graph never falls through to another graph: a wrong or unknown key reads nothing, never another graph's content.

<a id="graph.unscoped_snapshot"></a>
[D · graph.unscoped_snapshot]

The interned snapshot has no graph dimension, so it gives the default graph's answer only while no named graph holds an edge. Once any named graph holds an edge, a reader of the snapshot either refuses or reads the default graph's scoped index instead.

## Graph names

<a id="graph.names"></a>
[I · graph.names]

A graph name that cannot be stored as a key is refused before anything is written.

- The name `"0"` is reserved, because IRIS stores it as the number 0, which is the default graph's index key.
- NUL characters (code 0) are removed first, rather than refused, because IRIS SQL returns a NUL for an empty name.
- A name that still contains a control character is refused: codes 1 to 31 and 127 to 159, the ones IRIS classes as control characters. This includes code 1, the ledger's default-graph key.

- Working assumption: Preserve refusal of invalid new names and the promised legacy report; require an operator-visible migration plan before claiming old invalid names are supported.
- Working assumption: Prefer the server GraphKey rule for all new names; control-character normalization versus refusal must be documented consistently.

<a id="graph.names.report"></a>
[D · graph.names.report]

Graph verification must report any existing graph whose name is now refused. Today nothing reports them, verification itself refuses the name `"0"`, and a rebuild of the adjacency index fails on such a row.


## Reads and writes that name no graph

<a id="graph.all_graphs_read"></a>
[D · graph.all_graphs_read]

A Cypher query without `USE GRAPH` reads every graph, and its answer is the union of each graph's own answer. A node keeps its own graph's labels and properties, and an edge meets only nodes of its own graph.

<a id="graph.all_graphs_write"></a>
[D · graph.all_graphs_write]

A Cypher write without `USE GRAPH` changes only what its `MATCH` bound, each node and relationship in its own graph.

- `SET`, `REMOVE` and `DELETE` never touch a graph in which the pattern did not match, even when that graph holds a node with the same ID.
- `CREATE` writes the default graph.
- `MERGE` matches and creates in the default graph, so its `ON MATCH` changes only the default graph's node.

## Metadata

### graph.membership

- Sources: [CONTEXT.md, Graph](../../../CONTEXT.md#L27-L31), [USER_GUIDE section 4](../../../docs/USER_GUIDE.md#L384-L388), [rdf_edges foreign keys on (graph_id, node)](../../../iris_vector_graph/schema.py#L34-L45)
- agent
- user-facing-behavior, data-integrity

Findings: [delete_reification deletes the reifier's rows in every graph](../../Verus_verification/bugs_issues.md#bug-str-014)

### graph.default

- uncertain
- Sources: [CONTEXT.md, Graph](../../../CONTEXT.md#L27-L31), [USER_GUIDE section 4](../../../docs/USER_GUIDE.md#L386-L388), [USER_GUIDE on deletes and graph=](../../../docs/USER_GUIDE.md#L431-L465), [the omitted-graph marker](../../../iris_vector_graph/_engine/nodes_edges.py#L82-L83), [holders of an ID](../../../iris_vector_graph/_engine/nodes_edges.py#L2134-L2153), [delete_node scopes](../../../iris_vector_graph/_engine/nodes_edges.py#L2202-L2268), [delete_edge all_graphs](../../../iris_vector_graph/_engine/nodes_edges.py#L1390-L1422), [delete_reification](../../../iris_vector_graph/_engine/schema.py#L3361-L3392)
- Verus: [routine_reporting.rs](../../Verus_verification/models/routine_reporting/routine_reporting.rs) `theorem_scalar_is_raw_scoped_cardinality`, `theorem_default_null_empty_named`, `theorem_empty_filter_is_unfiltered` and `theorem_scoped_failure_propagates`; [scope](../../Verus_verification/models/routine_reporting/NOTES.md). Canonical graph/filter tokens and a faithful SQL comparison frame bind physical row counts, including legacy NULL/default equivalence; all-graph status remains its documented exception. Grouped label cardinality is modeled, while arbitrary tie ordering, validation and native/collation internals remain outside this claim.
- agent
- user-facing-behavior

The refusal of an ID held by several graphs dates from 4.6.0 (#112); before it, a delete without a graph removed the ID from every graph. The holder rule, the False answer for an ID with no holder and the omitted-versus-None distinction were added after the stage-A reconstruction check (gaps G1 and G2) and verified in the code; the same rule applies to `delete_node` and `bulk_delete_nodes`.

Open questions: [HD-0201](../../Verus_verification/open_questions.md#HD-0201)

### graph.named

- Sources: [CONTEXT.md, Named Graph](../../../CONTEXT.md#L33-L36), [ADR-0001](../../../docs/adr/0001-graph-key-as-first-subscript.md)
- agent
- data-integrity
- test-coverage

Live coverage: [USE GRAPH confines every read shape](../../../tests/e2e/test_use_graph_scope_shapes_e2e.py).

### graph.tenants

- Sources: [USER_GUIDE, not a security boundary](../../../docs/USER_GUIDE.md#L467-L468), [CONTEXT.md, Namespace](../../../CONTEXT.md#L14-L18), [ADR-0016 context](../../../docs/adr/0016-one-ivg-schema-per-namespace.md)
- agent
- security, architecture-decision

The namespace as the isolation unit is owned by the platform pages; this block records only what a graph does not promise.

### graph.key

- Sources: [ADR-0001](../../../docs/adr/0001-graph-key-as-first-subscript.md), [CONTEXT.md, Graph Key](../../../CONTEXT.md#L50-L58), [GraphKey](../../../iris_src/src/Graph/KG/GraphKey.cls)
- Children: [two forms](#graph.key.two_forms), [derive per store](#graph.key.derive), [one owner](#graph.key.owner)
- agent
- architecture-decision

ADR-0001 calls the layout a storage contract that only a new major version may change.

### graph.key.two_forms

- Sources: [ADR-0003](../../../docs/adr/0003-two-graph-key-derivations.md), [GraphKey.ForIndex / ForLedger / ForName](../../../iris_src/src/Graph/KG/GraphKey.cls#L50-L77), [delete_edge on the two SQL spellings](../../../iris_vector_graph/_engine/nodes_edges.py#L1424-L1433), [restore translates NULL](../../../iris_vector_graph/_engine/snapshot.py#L1249-L1255)
- Expands: [graph keys](#graph.key)
- Verus: [routine_reporting.rs](../../Verus_verification/models/routine_reporting/routine_reporting.rs) `theorem_scalar_is_raw_scoped_cardinality`, `theorem_default_null_empty_named`, `theorem_empty_filter_is_unfiltered` and `theorem_scoped_failure_propagates`; [scope](../../Verus_verification/models/routine_reporting/NOTES.md). Canonical graph/filter tokens and a faithful SQL comparison frame bind physical row counts, including legacy NULL/default equivalence; all-graph status remains its documented exception. Grouped label cardinality is modeled, while arbitrary tie ordering, validation and native/collation internals remain outside this claim.
- agent
- architecture-decision, data-integrity

In ObjectScript the ledger's default key is `$Char(1)` ([GraphKey.LEDGERDEFAULT](../../../iris_src/src/Graph/KG/GraphKey.cls#L20-L21)). The ledger keeps its own spelling because IRIS stores the subscript `"0"` as the number 0, so a graph named `"0"` would be the default graph under the index convention. ADR-0003 defers unifying the two spellings to a major version, together with a ledger layout stamp. The NULL spelling of the default graph is recorded in code comments and the restore, not in an ADR.

Findings: [ADR-0003 says control characters are stripped from named-graph keys, but the code refuses them](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-doc-006)

### graph.key.derive

- Sources: [ADR-0003](../../../docs/adr/0003-two-graph-key-derivations.md), [CONTEXT.md, Graph Key](../../../CONTEXT.md#L50-L58), [LedgerApply uses the index key for adjacency](../../../iris_src/src/Graph/KG/LedgerApply.cls#L498-L514)
- Expands: [graph keys](#graph.key)
- agent
- data-integrity
- test-coverage

Live coverage: [a ledger commit writes adjacency under the index key](../../../tests/integration/test_ledger_adjacency_graph_key.py). Source: a ledger write once used the ledger key on the native index, so default-graph edges written through the ledger were invisible to traversal. Observed divergence: several modules convert a native-index key back into a graph name themselves ([stage-A notes, C1](../../uplift/ivg-verus-initial/intent/graph-structure.md#c1-graph-scope-and-the-graph-key-derivations)).

Findings: [create_edge stores the raw graph name in SQL, so a name with a NUL becomes a second SQL graph sharing one adjacency entry](../../Verus_verification/bugs_issues.md#bug-str-005)

### graph.key.owner

- Sources: [ADR-0003 consequences](../../../docs/adr/0003-two-graph-key-derivations.md), [GraphKey](../../../iris_src/src/Graph/KG/GraphKey.cls), [Python mirror](../../../iris_vector_graph/_validate.py#L19-L71)
- Expands: [graph keys](#graph.key)
- agent
- architecture-decision
- test-coverage

Coverage is a source scan, not a live check: [GraphKey is the only derivation](../../../tests/unit/test_graph_key_module.py). Observed divergence: readers that serve only the default graph write its key 0 inline, and about ten sites convert a key back to a name outside the owner ([stage-A notes, C1](../../uplift/ivg-verus-initial/intent/graph-structure.md#c1-graph-scope-and-the-graph-key-derivations)).

Findings: [Give the inverse of a graph key one owner in GraphKey](../../Verus_verification/design_simplification.md#simp-str-002)

### graph.no_fallthrough

- Sources: [CONTEXT.md, Graph Key](../../../CONTEXT.md#L50-L58), [ADR-0001 context](../../../docs/adr/0001-graph-key-as-first-subscript.md)
- agent
- data-integrity, security
- test-coverage

Live coverage: [USE GRAPH confines every read shape](../../../tests/e2e/test_use_graph_scope_shapes_e2e.py).

### graph.unscoped_snapshot

- Sources: [CONTEXT.md, Interned snapshot](../../../CONTEXT.md#L97-L101), [NKGAccel.RefuseMergedGraphs](../../../iris_src/src/Graph/KG/NKGAccel.cls#L208-L224), [named_graph_with_edges](../../../iris_vector_graph/stores/lazy_kg.py#L45-L62), [USER_GUIDE, algorithms without USE GRAPH](../../../docs/USER_GUIDE.md#L755-L762)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Live coverage: [default-graph scope of the snapshot readers](../../../tests/e2e/test_460_r184_default_graph_scope_e2e.py). The refusal dates from 4.6.0 (R184, R196); before it, these readers answered every graph merged.

### graph.names

- uncertain
- Sources: [ADR-0003](../../../docs/adr/0003-two-graph-key-derivations.md), [GraphKey.Validate](../../../iris_src/src/Graph/KG/GraphKey.cls#L23-L48), [validate_graph_name](../../../iris_vector_graph/_validate.py#L19-L49)
- Children: [report refused names](#graph.names.report), [legacy names](../../Verus_verification/open_questions.md#q-str-001)
- agent
- data-integrity
- test-coverage

Live coverage: [GraphKey's two refused names](../../../tests/integration/test_graph_key_behaviour.py). ADR-0003's table still says the index form strips control characters; the code refuses them. The check is IRIS's `$ZStrip(name, "*C")`; the range 0 to 31 and 127 to 159 is IRIS's documented control-character class, not checked live in this run. Observed divergence: `create_node` does not check the graph name, `create_edge` and `create_node` store the unstripped name in SQL, and the Python mirror refuses only codes 0 to 31 and 127, so a name with a code from 128 to 159 passes Python and is refused inside IRIS ([stage-A notes, Q4-Q5](../../uplift/ivg-verus-initial/intent/graph-structure.md#open-questions-human-decision-needed)).

Findings: [create_edge stores the raw graph name in SQL, so a name with a NUL becomes a second SQL graph sharing one adjacency entry](../../Verus_verification/bugs_issues.md#bug-str-005); [Which control characters must a graph name refuse, and who owns the rule?](../../Verus_verification/open_questions.md#q-str-002)

Audit (q-str-002): Open owner decision. Working assumption (agent, unratified): Prefer the server GraphKey rule for all new names; control-character normalization versus refusal must be documented consistently. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#q-str-002).

Open questions: [q-str-001](../../Verus_verification/open_questions.md#q-str-001), [q-str-002](../../Verus_verification/open_questions.md#q-str-002)

### graph.names.report

- Sources: [ADR-0003](../../../docs/adr/0003-two-graph-key-derivations.md#L69-L70), [GraphVerify.cls VerifyGraph](../../../iris_src/src/Graph/KG/GraphVerify.cls#L41-L44), [TraversalBuild.cls](../../../iris_src/src/Graph/KG/TraversalBuild.cls#L44-L53)
- Expands: [graph names](#graph.names)
- human-verified
- data-integrity, operations

ADR-0003 (Accepted) says "the validator rejects new ones and `verify_graph` reports existing violations". Observed divergence (code reading): no code reports them, `verify_graph` derives the index key first and so refuses `"0"`, and the rebuild fails inside its transaction on such a row. Moved out of the Q by review round 3 R3-reader M10, which found the accepted decision demoted to a provisional answer.

Findings: [How should an install that already holds a graph named "0", or one with a control character, find and migrate it?](../../Verus_verification/open_questions.md#q-str-001), [Nothing reports an existing graph whose name is now refused, as ADR-0003 promises, and verification itself refuses the name "0"](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-str-017)

### graph.all_graphs_read

- Sources: [CONTEXT.md, All-graphs read (Decided 2026-10-20)](../../../CONTEXT.md#L38-L42), [USER_GUIDE section 4](../../../docs/USER_GUIDE.md#L402-L411), [Known issue: no way to tell a row's graph](../../../docs/KNOWN_ISSUES.md#a-query-over-every-graph-cannot-say-which-graph-a-row-came-from)
- human-verified
- user-facing-behavior

CONTEXT.md defines this as "a read that names no graph (a Cypher query without `USE GRAPH`)"; the statement keeps that limit, so Python reads without a graph still use the default graph ([default graph](#graph.default)). A limitation the known issues record: a query over every graph cannot say which graph a row came from. The Cypher translation and native executor that implement this decision are covered by the Cypher pages.

### graph.all_graphs_write

- Sources: [CONTEXT.md, All-graphs write (Decided 2026-11-06)](../../../CONTEXT.md#L44-L48), [USER_GUIDE section 4](../../../docs/USER_GUIDE.md#L413-L418)
- human-verified
- user-facing-behavior, data-integrity
- test-coverage

Live coverage: [a node DELETE without USE GRAPH removes only what its MATCH bound](../../../tests/e2e/test_delete_graph_scope_e2e.py). The statement names Cypher explicitly, as CONTEXT.md's rule does; Python writes follow [default graph](#graph.default).
