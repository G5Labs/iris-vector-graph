# Graph algorithms

IVG runs graph algorithms: PageRank and personalized PageRank (PPR), centrality, components and communities, triangles, k-core, subgraph extraction and walks. An optional native library can answer some of them faster, and answers are cached while the graph is unchanged.

## Definitions

- **Owner**: IVG's own implementation of an algorithm, running in IRIS. It is the reference answer and the fallback.
- **Arno**: an optional native library loaded into IRIS processes. It holds the Native Readers and some faster graph walks.
- **Native Reader**: an Arno implementation of an algorithm, used only after it has been proven against its Owner.
- **Reader Revision**: a whole number Arno reports for each Native Reader, raised whenever that reader's behavior is fixed. It is unrelated to a ledger revision.
- **Proof record**: the file shipped with IVG that lists, per algorithm, the lowest Reader Revision proven equal to its Owner and the library build it was proven on.
- **Evidence gate**: the test run that compares each Native Reader with its Owner and writes the proof record.
- **Graph-version token**: the namespace-wide counter that every change to the adjacency index raises, defined on the [graph-structure page](graph-structure.g5.md#structure.rebuilt.token).
- **IRIS collation**: the sort order used to break ties: numbers first, by value, then text (`9`, `10`, `07`, `a`).
- **Algorithm cache**: stored algorithm answers, shared by every connection in the namespace.

## Owners and Native Readers

<a id="algorithms.owner"></a>
[D · algorithms.owner]

Every algorithm has an Owner, and IVG gives complete answers without Arno. No Owner is removed when a Native Reader is adopted.

<a id="algorithms.routing"></a>
[I · algorithms.routing]

A call uses a Native Reader only when all of these hold; otherwise the Owner answers.

- The algorithm is one of PageRank, PPR, WCC, CDLP and subgraph.
- The proof record lists the algorithm.
- The loaded library reports a Reader Revision for it at or above the proof record's minimum.
- The call is within the scope the proof covers: today, the default graph only.
- The call runs in the namespace the library reads, today `USER` only; anywhere else the Owner answers, because the library would read another namespace's graph ([open question](#algorithms.routing.namespace)).
- PageRank also uses its Owner when the default graph is in multigraph mode or a node has no edge.

<a id="algorithms.routing.revision"></a>
[D · algorithms.routing.revision]

Routing reads Reader Revisions only from the library's own capability report, and minimum revisions only from the proof record. It never uses the library's version string or a list written into IVG's code. A missing, failing or unreadable report means no Native Readers.

<a id="algorithms.routing.fallback"></a>
[I · algorithms.routing.fallback]

If a Native Reader fails, returns nothing or returns an unreadable answer, the Owner answers instead and the failure is logged. The caller never sees the native failure.

<a id="algorithms.routing.reload"></a>
[I · algorithms.routing.reload]

When the library is replaced, routing reads the new library's report on its next load and never routes on the old library's revisions.

<a id="algorithms.routing.excluded"></a>
[D · algorithms.routing.excluded]

Betweenness always uses its exact directed Owner. The library's own breadth-first computation is not adopted until a separate decision.

<a id="algorithms.routing.named_graphs"></a>
[Q · algorithms.routing.named_graphs]

Can a default-graph call still use a Native Reader once a named graph holds edges? There is no provisional answer.

- The native readers may read an index that merges every graph, and the gate never tests that case.
- Plausible answers: route to the Owner whenever a named graph has edges, or record named-graph coverage in the proof.

<a id="algorithms.routing.namespace"></a>
[Q · algorithms.routing.namespace]

Should Native Readers work in any namespace? There is no provisional answer.

- Today they are used only in the `USER` namespace, because the library reads that namespace's data whatever namespace calls it.
- Every other namespace always gets the Owner, although the namespace is IVG's isolation unit.

## The proof record

<a id="algorithms.proof"></a>
[D · algorithms.proof]

The proof record ships with IVG and only the evidence gate writes it, never a person. An algorithm absent from it answers from its Owner, and a missing or invalid record sends every algorithm to its Owner, with a log entry.

<a id="algorithms.proof.gate"></a>
[D · algorithms.proof.gate]

The gate compares each Native Reader with its Owner, using that algorithm's equivalence rule, on at least four graph shapes and one tie-heavy graph, with five repeated calls each.

- The gate fails when the proof record claims a revision above what the installed library reports.
- Where the library is required, the gate must not skip because the library is absent.
- An algorithm that fails stays on its Owner and does not block the others.

<a id="algorithms.proof.build"></a>
[Q · algorithms.proof.build]

Does a proven Reader Revision hold for every build and platform of the library? There is no provisional answer.

- Routing ignores the build, but the proof record was made on one ARM build only.
- Plausible answers: the revision is the contract across builds, or routing also requires a proven build.

<a id="algorithms.proof.ungated"></a>
[Q · algorithms.proof.ungated]

Must the evidence gate also cover the other algorithms Arno speeds up, such as triangle count, strongly connected components, k-core and Leiden? There is no provisional answer. Today they use Arno without a proof entry and fall back only on a library error.

## Graph scope

<a id="algorithms.graph_scope"></a>
[D · algorithms.graph_scope]

PageRank, WCC, CDLP and subgraph read the default graph only, while PPR and degree centrality can read a named graph. Procedures that read the index without a graph dimension refuse, naming the Python method to use, once a named graph holds an edge. Without that refusal they would answer from every graph merged.

## Operations

<a id="algorithms.op"></a>
[I · algorithms.op]

Every algorithm answer includes every node of the graph, nodes with no edge too, and the n in any formula is the graph's node count. Ranked answers come highest first, and ties go by node ID in IRIS collation; two scores equal to 12 decimal places are a tie.

- A direction is `out` (along edges), `in` (against them) or `both` (the graph read as undirected).
- A damping factor outside (0, 1), an iteration count below 1 or an unknown direction raises `ValueError` before anything is read.
- The exceptions to "every node" are betweenness, which lists only nodes that score above 0, and walks and subgraphs, which list what they reach.

<a id="algorithms.op.pagerank"></a>
[I · algorithms.op.pagerank]

Global PageRank is textbook PageRank over every node of the default graph, returned as (node, score) pairs whose scores sum to 1.

- The damping factor is 0.85 and the run is 20 iterations by default. The count is fixed, not a convergence test, except that with Arno the walk also stops once converged.
- A node with no out-edges spreads its rank over every node.
- Known departure at the pin: the Owner silently returns at most 10,000 rows, so a larger result can omit nodes and sum to less than one. That violates the complete-answer requirement; cache admission does not repair it.
- Rank passes in proportion to edge count, so two edges from one node to another pass twice the rank of one.
- Given seeds, it returns personalized PageRank cut at this method's iteration count. Its `bidirectional` and `reverse_weight` options are accepted and ignored.

<a id="algorithms.op.ppr"></a>
[I · algorithms.op.ppr]

Personalized PageRank ranks every node of one graph by a walk that restarts at the seeds. It equals networkx's `pagerank` with that personalization, on the graph read as a multigraph.

- The walk restarts at the seeds evenly with probability 1 minus the damping factor (default 0.85), and otherwise follows an out-edge chosen evenly.
- Every edge counts: an edge under each relationship type, and each parallel edge of a multigraph.
- A node with no out-edges hands its score back to the seeds, so the scores sum to 1.
- It stops after `max_iterations` (100) or once the total change in one iteration is below N times `tolerance` (1e-6), N being the nodes holding a score.
- A repeated seed counts once, a seed that is not a node scores nothing, and a node the walk never reaches scores 0.0.
- `graph=` picks the graph and `exclude_predicates=` leaves relationship types out.

<a id="algorithms.op.wcc"></a>
[I · algorithms.op.wcc]

Weakly connected components ignore edge direction and label each node with the smallest node ID of its component, in IRIS collation. Labels spread until none changes; an optional round limit raises an error if they are still changing when it is reached.

<a id="algorithms.op.cdlp"></a>
[I · algorithms.op.cdlp]

Label propagation (CDLP) starts each node with its own ID as its label. Each round, every node at once takes the most common label among its neighbors in either direction, each edge one vote and a self-loop no vote; a tie goes to the label first in IRIS collation.

- It stops when no label changes, or after `max_iterations` rounds (10).
- Labels can swap between two states every round; the answer is then whichever round the limit ended on, with no warning.

<a id="algorithms.op.subgraph"></a>
[I · algorithms.op.subgraph]

Subgraph extraction returns the nodes within `k_hops` (2) of the seeds, at most `max_nodes` (10,000), and the edges among them. By default it adds each node's properties and labels, and vectors only on request. An edge-type filter keeps only those types, and empty seeds give an empty answer.

<a id="algorithms.op.degree"></a>
[I · algorithms.op.degree]

Degree centrality gives each node its number of edges in the chosen direction (`out` by default) and a score of degree divided by n − 1. It can count one relationship type only, and it reads the named graph or, by default, the default graph.

<a id="algorithms.op.betweenness"></a>
[I · algorithms.op.betweenness]

Betweenness centrality uses Brandes' algorithm, unnormalized, and lists only the nodes that lie on some shortest path between two others.

- `sample_size=0`, the default, uses every node as a source on a graph of up to 200 nodes and 200 sources above that, an approximation scaled by n over the sample.
- Any sample at or above n is exact: networkx's `betweenness_centrality(G, normalized=False)`.
- The sample is fixed: the node IDs that sort first by the SHA-1 of their UTF-8 bytes.
- `out` and `in` give the directed graph's scores and `both` the undirected graph's. `max_hops=k` counts only pairs at most k hops apart.
- The neighborhood form runs the same on the subgraph a seed reaches by out-edges within `hops` (2).

<a id="algorithms.op.closeness"></a>
[I · algorithms.op.closeness]

Closeness centrality is harmonic by default: the sum of 1/d over the nodes a node reaches, not normalized. The `classical` formula is (n − 1) divided by the sum of distances for a node that reaches every other node, and 0 otherwise; any other formula is refused.

<a id="algorithms.op.eigenvector"></a>
[I · algorithms.op.eigenvector]

Eigenvector centrality equals networkx's `eigenvector_centrality` on the directed graph: a node scores by the nodes pointing to it, each counted once however many edges it has.

- It iterates on the adjacency matrix plus the identity, starting from 1/N and normalizing each round, until the total change is below N times `tol` (1e-6).
- `max_iter` is 1 to 1000 (default 100). If it runs out first, the call raises `PowerIterationFailedConvergence` rather than answer an unconverged round.

<a id="algorithms.op.leiden"></a>
[D · algorithms.op.leiden]

Leiden community detection reads the graph as undirected, simple and unweighted: any number of edges between two nodes, in either direction, is one edge of weight 1.

- With `gamma=1.0` it optimizes modularity; any other `gamma` uses the Constant Potts Model.
- `random_seed` makes a run repeatable. Rows are `{id, community, size}`, community 0 the largest, and `top_k` counts rows, so it can cut through a community.
- The first available implementation answers: `leidenalg` inside IRIS, else Louvain in ObjectScript, then Arno's Leiden, then Python's `leidenalg` or, failing that, networkx's Louvain.
- With `gamma` other than 1.0 the Arno step is skipped, and the Python step needs `leidenalg`.

<a id="algorithms.op.triangles"></a>
[I · algorithms.op.triangles]

Triangle count gives each node the triangles through it, over its neighbors in either direction, and its local clustering coefficient: triangles divided by k(k − 1)/2 for k neighbors. Self-loops and parallel edges count once. Rows sort by triangle count, then by node ID.

<a id="algorithms.op.scc"></a>
[I · algorithms.op.scc]

Strongly connected components group nodes that reach one another along edge direction, found by an iterative Tarjan's algorithm. Rows are `{id, component, size}`, component 0 the largest.

<a id="algorithms.op.kcore"></a>
[I · algorithms.op.kcore]

A node's coreness is the largest k such that it belongs to a subgraph where every node has at least k neighbors, counted in either direction with self-loops removed. Rows sort by coreness, then by node ID, as networkx's `core_number`.

<a id="algorithms.op.khop"></a>
[I · algorithms.op.khop]

A k-hop read walks outbound, breadth first, from a seed for up to `hops` (2) hops. It returns the seed and then each node in the order reached, at most `max_nodes` (500), plus the edges walked among them with the hop that walked each.

- A seed with no out-edge returns itself and no edges; a missing seed returns nothing.
- A walk that fails raises an error rather than answer empty.

<a id="algorithms.op.walks"></a>
[I · algorithms.op.walks]

The walk operations follow outbound edges from one start node.

- A graph walk goes breadth first up to `max_depth` (3) hops and returns at most `max_results` (100) rows of (source, type, target, hop). Its edge-type list is a sequence: hop h follows the h-th type, and the last type repeats.
- A graph path returns the two-hop paths start, first type, middle, second type, end, one row per step.
- A random walk returns `num_walks` (10) walks of up to `length` (20) steps from a seed.

<a id="algorithms.op.paths"></a>
[I · algorithms.op.paths]

Path search finds a shortest path between two nodes inside one graph. A path from a node to itself has length zero, and an empty source or target answers no path.
- The search can follow the edges, go against them, or do both.
- The unweighted path routines answer no path for a direction they do not walk, instead of refusing it ([open question](#algorithms.op.paths.direction)).

<a id="algorithms.op.paths.weighted"></a>
[I · algorithms.op.paths.weighted]

A weighted path search returns a path with the lowest total cost, even when that path has more hops than another, and returns no row when no path joins the two nodes.
- Each edge costs its stored weight. A weight of zero or less, or no weight, costs one.
- Only the stored weight can be used: naming another weight property, or a direction other than out, in or both, is refused.
- For distinct endpoints, a path that costs more than the cost limit, or has more hops than a positive hop limit, is not an answer. Zero means no hop limit in the public procedure; a negative hop limit is refused there. The native search also treats negative hops as unbounded.
- Nonempty equal endpoints return the empty path at cost 0 before the native cost-cap or node-existence check. Public empty or missing endpoint arguments are refused; direct native empty endpoints answer no path.
- With a graph named, it searches that graph. With none, it searches each graph that has edges and gives one row for each graph where it finds a path.
- Costs come back as decimal numbers, so a weight of one reads back as 1.0. A failed search raises instead of answering no row.
- Relationship types omitted or supplied as an empty list mean every type. As built, the search reads each adjacency leaf's representative weight; in a correctly maintained multigraph that is the lowest live edge key, which need not hold the least weight of the parallel rows. Whether the intended minimum must instead consider every stored parallel relationship remains [open](#algorithms.op.paths.weighted.parallel).

<a id="algorithms.op.paths.weighted.parallel"></a>
[Q · algorithms.op.paths.weighted.parallel]

Which relationship set should weighted shortest path optimize in a multigraph: every stored parallel relationship, or the lowest-key representative graph? There is no provisional owner answer.
- The user guide promises the cheapest path by edge weight; the storage specification mandates the lowest-key leaf but does not clearly assign weighted shortest path to that projection.
- As built, parallel keys0/weight10 and5/weight1 plus an alternative route of cost4 return4; the full stored multigraph has a path of cost1. Proving the implemented queue minimizes its derived graph does not settle this policy.

<a id="algorithms.op.paths.direction"></a>
[Q · algorithms.op.paths.direction]

Should the unweighted path routines refuse a direction they do not walk?
- Today `ShortestPathJson` answers no path for any direction but out and both, and `ShortestLength` reads any direction but both as out.
- Provisional answer: refuse it, as the weighted search does.
- Alternative: keep today's behavior and document it.

## Cached answers

<a id="algorithms.cache"></a>
[I · algorithms.cache]

Answers of PageRank, PPR, WCC and CDLP are cached for every connection, separately per graph, and keyed by algorithm and parameters. A cached answer is served only while the graph is unchanged, so nothing stale is ever returned. The cache applies to Owner and Native Reader answers alike and does not depend on the library build.

<a id="algorithms.cache.token"></a>
[D · algorithms.cache.token]

A cached answer is valid only while the graph-version token it was computed under is still current, as the [structure page](graph-structure.g5.md#structure.rebuilt.valid) defines. The token moves on changes to the adjacency index, not on node rows or properties, so the cache admits only answers that depend on adjacency alone.

- PageRank also keys on the set of nodes, because adding a node without edges does not move the token.
- Subgraph extraction reads labels and properties, so its answers are never cached.
- The token is shared by the whole namespace, so a write to one graph also invalidates other graphs' answers.

<a id="algorithms.cache.pagerank"></a>
[D · algorithms.cache.pagerank]

Global PageRank puts the node table's row count and largest row ID in its cache key, alongside damping and iteration count; a cache hit also requires the current adjacency token. On a hit it returns the stored score rows without reading the nodes with no edge; adding an isolated node changes the node key and makes the next call compute again.

- An unreadable node token falls back to reading the edgeless list before lookup and using that list in the key. A missing token is not a known empty node set; an empty table successfully reads as `0:0`.
- The loner reader includes nodes whose only edges are self-loops. PageRank's adapter removes those from the edgeless list; a nonempty remaining list forces the Owner, while a self-loop-only list does not force that fallback.
- These checks assume stable reads and non-reused row IDs. They do not establish a consistent snapshot during concurrent writes, PPR freshness, or numerical correctness. The Owner's 10,000-row cap can break the requirement to list every node and return scores summing to one; that is the existing [F-1003](../../Verus_verification/bugs_issues.md#F-1003).

<a id="algorithms.cache.erasure"></a>
[I · algorithms.cache.erasure]

Erasure removes the cached answers of the graphs it erases, so no answer outlives erased content.

<a id="algorithms.cache.concurrency"></a>
[D · algorithms.cache.concurrency]

When two callers compute the same uncached answer, both answers are correct and the last one stored wins. A very large or uncacheable answer is not stored, and the call still succeeds. A read-only login gets answers without caching.

## Metadata

### algorithms.owner

- Sources: [CONTEXT.md: Owner, Arno](../../../CONTEXT.md); [Spec 236 FR-005](../../../specs/236-arno-callout-adoption/spec.md); [ADMIN_GUIDE §4: Arno](../../../docs/ADMIN_GUIDE.md)
- agent
- architecture-decision

Observed divergence: `random_walk` has no Owner; without Arno it logs a warning and returns an empty list (see [walks](#algorithms.op.walks)).

### algorithms.routing

- Sources: [Spec 236 FR-001, FR-006, FR-014a](../../../specs/236-arno-callout-adoption/spec.md); [CONTEXT.md: Native Reader, Reader Revision](../../../CONTEXT.md); [arno_readers.py route](../../../iris_vector_graph/arno_readers.py); [stores/iris_sql_store.py](../../../iris_vector_graph/stores/iris_sql_store.py)
- Children: [revision](#algorithms.routing.revision), [fallback](#algorithms.routing.fallback), [reload](#algorithms.routing.reload), [excluded](#algorithms.routing.excluded), [named graphs](#algorithms.routing.named_graphs), [namespace](#algorithms.routing.namespace)
- agent
- architecture-decision, data-integrity

Spec 236's status line still says "Draft", although it shipped in 4.2.0. Since 4.6.0 only PageRank is proven, so the other four always use their Owners (ADMIN_GUIDE §4). Some routes add parameter limits beyond the proof, for example PPR uses its Owner when the call is bidirectional or excludes nodes. The routing rules are unit-tested with supplied reports (`tests/unit/test_236_reader_routing.py`). The live gate test skips unless the library is required.


The namespace guard is in [iris_sql_store.py _arno_route](../../../iris_vector_graph/stores/iris_sql_store.py#L882-L890) and [ArnoAccel.cls](../../../iris_src/src/Graph/KG/ArnoAccel.cls#L242-L262), which also refuses native PageRank on a multigraph default graph; the edgeless-node case is at [iris_sql_store.py](../../../iris_vector_graph/stores/iris_sql_store.py#L2390-L2395). Added by review round 3 R3-reader M11.

### algorithms.routing.revision

- Sources: [Spec 236 FR-002, FR-003, FR-004, FR-008](../../../specs/236-arno-callout-adoption/spec.md); [arno_readers.py](../../../iris_vector_graph/arno_readers.py); [ArnoAccel.cls ReaderRevisions](../../../iris_src/src/Graph/KG/ArnoAccel.cls)
- Expands: [Routing](#algorithms.routing)
- agent
- architecture-decision

Observed divergence: the capability and status fields that say PPR and WCC run natively come from a list written into the ObjectScript code, not from routing, so they claim native use that routing never makes.

### algorithms.routing.fallback

- Sources: [Spec 236 Edge Cases](../../../specs/236-arno-callout-adoption/spec.md); [stores/iris_sql_store.py _native_answer](../../../iris_vector_graph/stores/iris_sql_store.py)
- Expands: [Routing](#algorithms.routing)
- agent
- data-integrity

A native answer that parses but is wrong is returned and cached; the evidence gate is the only assurance against that.

Findings: [Make the engine's Owner fallback uniform across algorithms](../../Verus_verification/design_simplification.md#simp-plt-002)

### algorithms.routing.reload

- Sources: [Spec 236 Edge Cases](../../../specs/236-arno-callout-adoption/spec.md); [ArnoAccel.cls](../../../iris_src/src/Graph/KG/ArnoAccel.cls); [Stage A notes F-A2](../../uplift/ivg-verus-initial/intent/platform.md)
- Expands: [Routing](#algorithms.routing)
- agent
- data-integrity

Suspected divergence: the server-side loader reloads a replaced library without telling the Python side, so the engine keeps the old library's report. The unit test resets the report by hand. A failed availability probe is also kept for the life of the store.

Findings: [After the native library is replaced, routing can keep using the old library's proof report](../../Verus_verification/bugs_issues.md#bug-plt-010)

### algorithms.routing.excluded

- Sources: [Spec 236 FR-006, FR-015](../../../specs/236-arno-callout-adoption/spec.md)
- Expands: [Routing](#algorithms.routing)
- agent
- architecture-decision

### algorithms.routing.named_graphs

- Sources: [Spec 236 FR-014a](../../../specs/236-arno-callout-adoption/spec.md); [KNOWN_ISSUES: Named graphs are not accelerated by Arno](../../../docs/KNOWN_ISSUES.md); [ArnoAccel.cls PageRankNativeJson](../../../iris_src/src/Graph/KG/ArnoAccel.cls); [Stage A notes F-A3](../../uplift/ivg-verus-initial/intent/platform.md)
- Expands: [Routing](#algorithms.routing)
- agent
- uncertain
- data-integrity

The sources disagree about what a Native Reader reads. CONTEXT.md says "the Adjacency Index directly", and the ObjectScript wrapper says the merged native export. Other Arno-backed algorithms already refuse that tier once a named graph holds edges.

Findings: [Can a default-graph algorithm call use a native reader once a named graph holds edges?](../../Verus_verification/open_questions.md#q-plt-007)

### algorithms.routing.namespace

- Sources: [Spec 236 research](../../../specs/236-arno-callout-adoption/research.md); [stores/iris_sql_store.py _arno_route](../../../iris_vector_graph/stores/iris_sql_store.py); [ADR-0016](../../../docs/adr/0016-one-ivg-schema-per-namespace.md)
- Expands: [Routing](#algorithms.routing)
- agent
- uncertain
- architecture-decision

Findings: [Should native readers work in namespaces other than USER?](../../Verus_verification/open_questions.md#q-plt-015)

### algorithms.proof

- Sources: [CONTEXT.md: Proof Record](../../../CONTEXT.md); [Spec 236 FR-007, FR-008, Edge Cases](../../../specs/236-arno-callout-adoption/spec.md); [docs/dev/arno-reader-proof.json](../../../docs/dev/arno-reader-proof.json); [arno_readers.py load_proof](../../../iris_vector_graph/arno_readers.py)
- Children: [gate](#algorithms.proof.gate), [build](#algorithms.proof.build), [ungated](#algorithms.proof.ungated)
- agent
- architecture-decision

Observed: one invalid entry, including an out-of-scope algorithm, empties the whole record (it fails safe). FR-007 asks for the build per algorithm, but the record keeps one build for all. Before 4.6.0 (R104) wheels shipped no proof record.

Findings: [Capabilities and status report native algorithms that are not proven or routed](../../Verus_verification/bugs_issues.md#bug-plt-018)

### algorithms.proof.gate

- Sources: [Spec 236 FR-009, FR-010, FR-011](../../../specs/236-arno-callout-adoption/spec.md); [scripts/arno_reader_gate.py](../../../scripts/arno_reader_gate.py)
- Expands: [Proof record](#algorithms.proof)
- agent
- data-integrity

The gate's graphs are single-graph graphs in `USER`, with no multigraph mode and no nodes without edges.

### algorithms.proof.build

- Sources: [Spec 236 open questions](../../../specs/236-arno-callout-adoption/spec.md); [docs/dev/arno-reader-proof.json](../../../docs/dev/arno-reader-proof.json)
- Expands: [Proof record](#algorithms.proof)
- agent
- uncertain
- architecture-decision

Findings: [Does a proven reader revision hold for every build and platform of the library?](../../Verus_verification/open_questions.md#q-plt-013)

### algorithms.proof.ungated

- Sources: [stores/iris_sql_store.py](../../../iris_vector_graph/stores/iris_sql_store.py); [Stage A notes F-A7](../../uplift/ivg-verus-initial/intent/platform.md)
- Expands: [Proof record](#algorithms.proof)
- agent
- uncertain
- data-integrity

Findings: [Must the evidence gate also cover the other algorithms the native library speeds up?](../../Verus_verification/open_questions.md#q-plt-014)

### algorithms.graph_scope

- Sources: [KNOWN_ISSUES: The ^NKG algorithm procedures raise once a named graph has edges](../../../docs/KNOWN_ISSUES.md); [USER_GUIDE algorithms](../../../docs/USER_GUIDE.md); [graph.unscoped_snapshot](../concepts/graph-scope.g5.md#graph.unscoped_snapshot)
- agent
- user-facing-behavior

Changed in 4.6.0. Before that, procedures and methods disagreed: some answered every graph merged and others the default graph.

### algorithms.op

- Sources: [USER_GUIDE §6 Graph algorithms](../../../docs/USER_GUIDE.md); [API_REFERENCE: Graph algorithms](../../../docs/API_REFERENCE.md); [_engine/algorithms.py](../../../iris_vector_graph/_engine/algorithms.py)
- Children: [PageRank](#algorithms.op.pagerank), [PPR](#algorithms.op.ppr), [WCC](#algorithms.op.wcc), [CDLP](#algorithms.op.cdlp), [subgraph](#algorithms.op.subgraph), [degree](#algorithms.op.degree), [betweenness](#algorithms.op.betweenness), [closeness](#algorithms.op.closeness), [eigenvector](#algorithms.op.eigenvector), [Leiden](#algorithms.op.leiden), [triangles](#algorithms.op.triangles), [SCC](#algorithms.op.scc), [k-core](#algorithms.op.kcore), [k-hop](#algorithms.op.khop), [walks](#algorithms.op.walks), [paths](#algorithms.op.paths)
- agent
- user-facing-behavior

Edgeless nodes joined every answer in 4.6.0 (R306), and unreached PPR nodes got a 0.0 row in 4.7.0. Argument checks for damping and iterations came in 4.7.0. The Cypher procedures' graph scope is in [graph scope](#algorithms.graph_scope).

### algorithms.op.pagerank

- Sources: [API_REFERENCE kg_PAGERANK](../../../docs/API_REFERENCE.md); [USER_GUIDE PageRank](../../../docs/USER_GUIDE.md); [CHANGELOG v4.6.0](../../../CHANGELOG.md); [PageRank.cls](../../../iris_src/src/Graph/KG/PageRank.cls)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior
- test-coverage

Textbook PageRank and weighting by edge count came in 4.6.0. Before, a parallel edge counted in its source's degree but passed rank once, and the scores did not sum to 1. Live coverage: `tests/e2e/test_pagerank_textbook_e2e.py`.

Findings: [Owner result cap F-1003](../../Verus_verification/bugs_issues.md#F-1003); the numerical/every-node rule is not established by the new cache-admission contract.

### algorithms.op.ppr

- Sources: [API_REFERENCE kg_PERSONALIZED_PAGERANK, ppr](../../../docs/API_REFERENCE.md); [USER_GUIDE PageRank](../../../docs/USER_GUIDE.md); [CHANGELOG v4.6.0 (R270)](../../../CHANGELOG.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

networkx semantics, dangling handling and weighting of keyed parallel edges by their count came in 4.6.0. A seed that is not a node stopped scoring 1.0 in 4.7.0. The results come back as a node-to-score map; `ppr()` returns a list cut to `top_k` (20).

### algorithms.op.wcc

- Sources: [COMMUNITIES.md: Weakly connected components](../../../docs/COMMUNITIES.md); [API_REFERENCE kg_WCC](../../../docs/API_REFERENCE.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

With a round limit the Owner answers even when Arno is loaded. Before 4.6.0 labels stopped after 100 rounds, so a long component could come back split.

### algorithms.op.cdlp

- Sources: [COMMUNITIES.md: Label propagation](../../../docs/COMMUNITIES.md); [API_REFERENCE kg_CDLP](../../../docs/API_REFERENCE.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

The self-loop rule and the collation tie-break changed in 4.6.0. The oscillation is documented; the documented check is to compare two adjacent round limits.

### algorithms.op.subgraph

- Sources: [API_REFERENCE kg_SUBGRAPH](../../../docs/API_REFERENCE.md); [_engine/algorithms.py kg_SUBGRAPH](../../../iris_vector_graph/_engine/algorithms.py)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

The walk direction is not documented. A code comment still calls the traversal namespace-wide, although its Owner reads the default graph only.

### algorithms.op.degree

- Sources: [API_REFERENCE degree_centrality](../../../docs/API_REFERENCE.md); [USER_GUIDE §6](../../../docs/USER_GUIDE.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

The method's argument note still says n counts only nodes with an edge, which 4.6.0 changed.

### algorithms.op.betweenness

- Sources: [USER_GUIDE §6](../../../docs/USER_GUIDE.md); [API_REFERENCE betweenness_centrality, betweenness_centrality_neighborhood](../../../docs/API_REFERENCE.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

The hash-based sample replaced the first IDs in ID order in 4.6.0. With a read-only login, or once a named graph holds edges, the slower Python walk answers.

### algorithms.op.closeness

- Sources: [API_REFERENCE closeness_centrality](../../../docs/API_REFERENCE.md); [USER_GUIDE §6](../../../docs/USER_GUIDE.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

Once any node has no edge, no node reaches every other, so every classical score is 0.

### algorithms.op.eigenvector

- Sources: [API_REFERENCE eigenvector_centrality](../../../docs/API_REFERENCE.md); [USER_GUIDE §6](../../../docs/USER_GUIDE.md); [CHANGELOG v4.6.0 (R306)](../../../CHANGELOG.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

Counting each pointing node once came in 4.6.0, when two routes disagreed on parallel edges. Before, it iterated on the adjacency matrix alone for 30 rounds and answered the last round silently.

### algorithms.op.leiden

- Sources: [COMMUNITIES.md: Leiden](../../../docs/COMMUNITIES.md); [API_REFERENCE leiden_communities](../../../docs/API_REFERENCE.md); [CHANGELOG v4.6.0 (R231)](../../../CHANGELOG.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

The ObjectScript Louvain does not guarantee connected communities and ignores `random_seed`, so the answer can differ by which implementation is installed. Arno's Leiden is outside the proof gate (see [ungated](#algorithms.proof.ungated)).

### algorithms.op.triangles

- Sources: [COMMUNITIES.md: Triangles](../../../docs/COMMUNITIES.md); [API_REFERENCE triangle_count](../../../docs/API_REFERENCE.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

### algorithms.op.scc

- Sources: [COMMUNITIES.md: Strongly connected components](../../../docs/COMMUNITIES.md); [API_REFERENCE strongly_connected_components](../../../docs/API_REFERENCE.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

### algorithms.op.kcore

- Sources: [COMMUNITIES.md: K-core](../../../docs/COMMUNITIES.md); [API_REFERENCE k_core](../../../docs/API_REFERENCE.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

### algorithms.op.khop

- Sources: [API_REFERENCE khop](../../../docs/API_REFERENCE.md); [_engine/algorithms.py khop](../../../iris_vector_graph/_engine/algorithms.py)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

The Owner answers with or without Arno, so the result has one shape (4.6.0). A failed walk raised instead of answering empty from 4.6.0.

### algorithms.op.walks

- Sources: [API_REFERENCE kg_GRAPH_WALK, kg_GRAPH_PATH, random_walk](../../../docs/API_REFERENCE.md); [_engine/algorithms.py](../../../iris_vector_graph/_engine/algorithms.py); [USER_GUIDE: shortest path](../../../docs/USER_GUIDE.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

Observed divergence: `random_walk` needs Arno, and without it returns an empty list after a warning, against the promise that every algorithm has an Owner. The graph path's `max_hops` argument is not used. Weighted shortest paths are a Cypher procedure and use each edge's `weight` property, 1.0 when absent; [weighted path search](#algorithms.op.paths.weighted) owns that rule.

### algorithms.op.paths
- Sources: [CHANGELOG 4.6.0 paths](../../../CHANGELOG.md#L525-L535); [`iris_src/src/Graph/KG/TraversalPaths.cls::ShortestPathJson`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L5-L116), [`::ShortestLength`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L117-L175)
- Playbook: [ALG-B10](../../../experiment/playbook-completion/ontology/10-algorithms.md#L219), [ALG-B10.2](../../../experiment/playbook-completion/ontology/10-algorithms.md#L221)
- Verus: the playbook's `proofs-d1e` `atrav_l2` (reviewed design) proves the direction contract; its control `control_hd1003_direction_unchecked` reintroduces the pin's behavior (finding HD-1003). No as-built model.
- Expands: [Operations](#algorithms.op)
- Children: [weighted](#algorithms.op.paths.weighted), [direction](#algorithms.op.paths.direction)
- agent
- user-facing-behavior
- test-coverage

### algorithms.op.paths.weighted
- Sources: [`iris_src/src/Graph/KG/TraversalPaths.cls::DijkstraJson`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L256-L346) (cost order and settling `:293-342`; weight of zero or less is one `:329-331`; hop bound `:265`, `:312`; no path `"{}"` `:344-345`), [`::DijkstraCost`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L378-L448), [`::CheckDirection`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L350-L355), [`::CheckWeightProp`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L359-L365); [`iris_vector_graph/engine.py::IRISGraphEngine._proc_ivg_shortestpath_weighted`](../../../iris_vector_graph/engine.py#L1201-L1313) (one search per graph `:1275-1282`); tests [test_weighted_shortest_path.py](../../../tests/unit/test_weighted_shortest_path.py) (they drive a live engine)
- Playbook: [ALG-B10.5](../../../experiment/playbook-completion/ontology/10-algorithms.md#L225), [ALG-B10.6](../../../experiment/playbook-completion/ontology/10-algorithms.md#L226), [ALG-B10.7](../../../experiment/playbook-completion/ontology/10-algorithms.md#L227), [ALG-B10.8](../../../experiment/playbook-completion/ontology/10-algorithms.md#L228), [ALG-B10.90](../../../experiment/playbook-completion/ontology/10-algorithms.md#L229)
- Verus: [weighted_paths.rs](../../Verus_verification/models/weighted_paths/weighted_paths.rs), `theorem_complete_terminating_search`, `theorem_actual_search_terminates`, `theorem_actual_returned_path_is_optimal`, `theorem_empty_queue_is_no_feasible_path`, `theorem_admitted_self_is_zero`; [domain and source roles](../../Verus_verification/models/weighted_paths/NOTES.md). As-built state-transcription proof over a finite stable actual raw scalar graph, exact integer weights/cap and nonnegative hop bound: ordered stale queue, raw seen-hop dominance, dist/parent relaxation, optimal returned chain, no-path and derived termination. The bidirectional `DijkstraCost`, raw public argument/refusal carrier, writer/index maintenance, arbitrary floating/JSON/collation correspondence and concurrent changes remain unproved. No product executable body is verified.
- Children: [Parallel-edge policy](#algorithms.op.paths.weighted.parallel)
- Expands: [Path search](#algorithms.op.paths)
- agent
- user-facing-behavior
- test-coverage

Public case M12 now has a substantive one-sided numerical-search contract, while the cost-only route remains a material formal gap. The queue proof retains stale entries and minimum-hop dominance rather than replacing the algorithm with a supplied shortest answer. [9000 paired native searches,14 public queries](../../uplift/consolidated/iteration-9/weighted-native.json), [18 boundary neighbors](../../uplift/consolidated/iteration-9/weighted-native-neighbors.json) and [four explicit mirror-state variations](../../uplift/consolidated/iteration-9/weighted-mirror-native.json) are finite correspondence evidence, not a native-body or general cost-only proof. The mode-off lowest-key harness miss is retained and withdrawn as an unsupported producer expectation; the valid mode-on4-vs1 policy remains open. The cost-only route requires equal-effective-weight reverse mirrors: in the explicit provider-state fixture JSON keeps cost20, while a missing reverse point makes Cost answer no path and a reverse weight1 replacing10 makes Cost answer11; restoring the point restores20. These deliberately altered provider states are not ordinary-writer defects or a promise about malformed graphs.

### algorithms.op.paths.weighted.parallel
- Sources: [USER_GUIDE631-644](../../../docs/USER_GUIDE.md#L631-L644), [spec234 FR004/FR015](../../../specs/234-multigraph-parallel-edges/spec.md#L225-L243), [DijkstraJson raw leaf read](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L329-L338), [native mode-on fixture](../../uplift/consolidated/iteration-9/weighted-native.json), [independent intent review](../../uplift/consolidated/iteration-9/weighted-projection-review.md)
- Expands: [Weighted path](#algorithms.op.paths.weighted)
- agent
- uncertain
- user-facing-behavior, data-integrity
- test-coverage

The model's raw adjacency minimum and native4-vs1 observation are as-built evidence. No owner has selected the parallel-edge policy, no repair was accepted, and no new weighted product bug is counted. [q-iter-007](../../Verus_verification/open_questions.md#q-iter-007) records the decision. The earlier mode-off fixture miss is separately withdrawn as an unsupported lowest-key oracle, not evidence for this question.

### algorithms.op.paths.direction
- Sources: [`iris_src/src/Graph/KG/TraversalPaths.cls::ShortestPathJson`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L5-L116), [`::ShortestLength`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L117-L175)
- Playbook: [ALG-Q4](../../../experiment/playbook-completion/ontology/10-algorithms.md#L224), decision [HD-1003](../../../experiment/playbook-completion/intent/HD-1003.md)
- Verus: the playbook's `proofs-d1e` `atrav_l2` (reviewed design, control `control_hd1003_direction_unchecked`).
- Expands: [Path search](#algorithms.op.paths)
- agent
- uncertain
- user-facing-behavior

Findings: [HD-1003](../../Verus_verification/open_questions.md#HD-1003)

### algorithms.cache

- Sources: [Spec 236 FR-016, FR-017, FR-022, Story 4](../../../specs/236-arno-callout-adoption/spec.md); [algo_cache.py](../../../iris_vector_graph/algo_cache.py); [AlgoCache.cls](../../../iris_src/src/Graph/KG/AlgoCache.cls)
- Playbook: [ALG-B16](../../../experiment/playbook-completion/ontology/10-algorithms.md#L309), [ALG-B16.3](../../../experiment/playbook-completion/ontology/10-algorithms.md#L312)
- Verus: active for modeled PageRank/PPR keys and repeated calls (partial for public M21): the playbook's `proofs-d1e` [`acache_l1.rs`](../../../experiment/playbook-completion/proofs-d1e/src/acache_l1.rs) `theorem_answer_is_fresh` and `acache_l2.rs` (**reviewed design**: freshness is keyed on a node token `nver` the pin does not have; the pin's behavior is control `control_f1004_create_moves_no_token`, finding F-1004, rerun here). Its theorem supports "the reviewed design returns fresh answers", not "the product does". Overlapping: `G-graph_structure` (as-built) algorithm-cache token model, which omits the parameters from the key; its witness of a rolled-back write is finding bug-str-002. Scope correction in iteration 1: Q contains only PageRank and seeded PPR, not CDLP iteration keys; Ans does not carry CDLP labels or iteration counts. M21 remains partial.
- Children: [global PageRank admission](#algorithms.cache.pagerank), [token](#algorithms.cache.token), [erasure](#algorithms.cache.erasure), [concurrency](#algorithms.cache.concurrency)
- agent
- data-integrity
- test-coverage

Live coverage: `tests/integration/test_236_algo_cache.py`. Each graph's cache is keyed by the adjacency form of its graph key. The cached set is fixed in `algo_cache.py` (`CACHEABLE`).

Findings: [A cached personalized PageRank answer does not notice a node created after it](../../Verus_verification/bugs_issues.md#bug-plt-017)

### algorithms.cache.token

- Sources: [Spec 236 FR-017, FR-018, FR-019, research R2](../../../specs/236-arno-callout-adoption/spec.md); [Spec 236 token audit](../../../specs/236-arno-callout-adoption/research-token-audit.md); [algo_cache.py](../../../iris_vector_graph/algo_cache.py); [Adjacency.cls](../../../iris_src/src/Graph/KG/Adjacency.cls); [structure.rebuilt.token](graph-structure.g5.md#structure.rebuilt.token)
- Playbook: [ALG-B16.6](../../../experiment/playbook-completion/ontology/10-algorithms.md#L315), [ALG-B16.7](../../../experiment/playbook-completion/ontology/10-algorithms.md#L316)
- Verus: active for abstract shared-cache hits and recompute after a write (partial for public J04): the playbook's `proofs-d1e` `acache_l2.rs` (**reviewed design**, see [algorithm cache](#algorithms.cache); control `control_f1004_create_moves_no_token`). As-built evidence: `G-graph_structure` `theorem_as_built_cache_sound` and the rollback witness behind bug-str-002 (not the same defect as F-1004). Scope correction in iteration 1: WCC components and the public second-connection WCC reader are not represented, so J04 remains partial; an abstract shared-cache hit is not that workflow.
- Expands: [Algorithm cache](#algorithms.cache)
- agent
- data-integrity
- test-coverage

Live coverage: `tests/integration/test_236_token_write_paths.py`, one case per audited write path. Where the label index is declared, label writes also move the token, so the stated reason subgraph is not cached is out of date; the decision stands. The case of a write that rolls back after a reader stored an answer is the open question [structure.rebuilt.rollback](graph-structure.g5.md#structure.rebuilt.rollback). Suspected divergence: a cached PPR answer for a seed that is not yet a node survives the node's creation, since PPR is not keyed on the node set.

Findings: [A cached personalized PageRank answer does not notice a node created after it](../../Verus_verification/bugs_issues.md#bug-plt-017), [same creation trigger in F-1004](../../Verus_verification/bugs_issues.md#F-1004)

### algorithms.cache.pagerank

- Sources: [COUNT:MAX producer and engine consumer](../../../iris_vector_graph/_engine/algorithms.py#L179-L194), [global engine](../../../iris_vector_graph/_engine/algorithms.py#L782-L804), [store and cache](../../../iris_vector_graph/stores/iris_sql_store.py#L2362-L2424), [edgeless producer](../../../iris_vector_graph/_edgeless.py#L65-L67), [R313 tests](../../../tests/unit/test_460_r313_pagerank_loners_lazy.py)
- Verus: [pagerank_admission](../../Verus_verification/models/pagerank_admission/NOTES.md), as-built `token`, `key`, `edgeless`, `call` and named neighbor theorems. COUNT:MAX SQL, row-ID monotonicity, snapshot consistency and actual PageRank numerics remain provider obligations.
- Expands: [cache](#algorithms.cache)
- agent
- data-integrity
- test-coverage

Findings: [F-1003](../../Verus_verification/bugs_issues.md#F-1003). Global PageRank's node key is not evidence of [PPR freshness](#algorithms.cache.token). No live IRIS or numerical proof.

### algorithms.cache.erasure

- Sources: [Spec 236 FR-020](../../../specs/236-arno-callout-adoption/spec.md); [ADR-0004](../../../docs/adr/0004-erasure-removes-content-not-history.md)
- Expands: [Algorithm cache](#algorithms.cache)
- agent
- data-integrity
- test-coverage

Live coverage: the erase cases in `tests/integration/test_236_token_write_paths.py`.

### algorithms.cache.concurrency

- Sources: [Spec 236 Edge Cases](../../../specs/236-arno-callout-adoption/spec.md); [ADMIN_GUIDE §3 (reading role)](../../../docs/ADMIN_GUIDE.md)
- Expands: [Algorithm cache](#algorithms.cache)
- agent
- operations

Findings: [A cached algorithm answer computed over a write that later rolls back stays current](../../Verus_verification/bugs_issues.md#bug-str-002)
