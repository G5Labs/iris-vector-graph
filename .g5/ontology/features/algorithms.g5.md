# Graph algorithms

Find the available walks, paths, rankings and other graph algorithms. For reader selection and cache behavior, see [how graph algorithms run](../architecture/algorithm-execution.g5.md).

## Definitions

- **Owner**: IVG's own implementation of an algorithm, running in IRIS. It is the reference answer and the fallback.
- **Arno**: an optional native library loaded into IRIS processes. It holds the Native Readers and some faster graph walks.
- **Native Reader**: an Arno implementation of an algorithm, used only after it has been proven against its Owner.
- **Reader Revision**: a whole number Arno reports for each Native Reader, raised whenever that reader's behavior is fixed. It is unrelated to a ledger revision.
- **Proof record**: the file shipped with IVG that lists, per algorithm, the lowest Reader Revision proven equal to its Owner and the library build it was proven on.
- **Evidence gate**: the test run that compares each Native Reader with its Owner and writes the proof record.
- **Graph-version token**: the namespace-wide counter that every change to the adjacency index raises, defined on the [graph-structure page](../architecture/adjacency-and-derived-data.g5.md#structure.rebuilt.token).
- **IRIS collation**: the sort order used to break ties: numbers first, by value, then text (`9`, `10`, `07`, `a`).
- **Algorithm cache**: stored algorithm answers, shared by every connection in the namespace.

## Graph scope

<a id="algorithms.graph_scope"></a>
[D · algorithms.graph_scope]

PageRank, WCC, CDLP and subgraph read the default graph only, while PPR and degree centrality can read a named graph. Procedures that read the index without a graph dimension refuse, naming the Python method to use, once a named graph holds an edge. Without that refusal they would answer from every graph merged.

## Algorithms and the results they return

<a id="algorithms.op"></a>
[I · algorithms.op]

Every algorithm answer includes every node of the graph, nodes with no edge too, and the n in any formula is the graph's node count. Ranked answers come highest first, and ties go by node ID in IRIS collation; two scores equal to 12 decimal places are a tie.

- A direction is `out` (along edges), `in` (against them) or `both` (the graph read as undirected).
- PageRank and PPR reject a damping factor outside (0, 1) or an iteration count below 1 with `ValueError` before reading data.
- Operations with a direction reject an unknown direction with `ValueError` before reading data.
- The centrality and community methods and their Cypher procedures (`CALL ivg.*`) accept the same option values and refuse the same ones with `ValueError` before reading data: `topK` 0 to 1,000,000 (0 keeps every row), `maxHops` 0 to 1000, `sampleSize` 0 or more, `maxIter` 1 to 1000, `memBudgetMB` 16 to 8192, `gamma` above 0 up to 100, and `formula` and `direction` spelled exactly. A whole-number string or float is taken as that number; a procedure refuses an option it does not list, naming the ones it does.
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

- Working assumption: Preserve the rounded-score tie rule today; giving every positive raw score priority over true zero would change top-k admission.

<a id="algorithms.op.ppr.completion"></a>
[I · algorithms.op.ppr.completion]

Completing a PPR answer with zero-score nodes must distinguish nodes the walk never reached from positive scores omitted by an earlier row limit. A caller's larger result limit must not turn a truncated positive score into zero.

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
- Today it reads the default graph only and lists only the edges leaving the nodes it expanded, so an edge between two nodes of the outermost hop is missing ([finding](../../Verus_verification/bugs_issues.md#bug-plt-114)).
- Today, when the cap is reached, the edge that crossed it is still listed although its far node is not, and expansion stops at once. A seed with no edge at all is left out.

<a id="algorithms.op.subgraph.guided"></a>
[I · algorithms.op.subgraph.guided]

`kg_PPR_GUIDED_SUBGRAPH` runs personalized PageRank from the seeds on the default graph, keeps the `ppr_top_k` (50) best positive scores, and returns the subgraph within `k_hops` (1) of the seeds and those nodes with their scores. The answer has at most `min(max_nodes, ppr_top_k)` nodes and lists the edges among them.
- Damping outside (0, 1) or fewer than 1 iteration raises `ValueError` before any data is read. A repeated seed counts once; seeds that are not nodes add nothing.
- Today every seed and top node with an edge is taken in, however many there are, so the answer can exceed the cap: three seeds with `ppr_top_k` 1 answer three nodes ([finding](../../Verus_verification/bugs_issues.md#bug-plt-113)).
- Today, once those nodes fill the cap, only the first of them in ID order is expanded, so the answer lists only its out-edges and the edges among the others are missing. With the default 50 this happens whenever the walk reaches 50 nodes ([finding](../../Verus_verification/bugs_issues.md#bug-plt-113)).
- Both departures were seen on the ObjectScript subgraph reader. With the Arno accelerator loaded and no edge-type filter, another reader answers first; it was not checked.
- `IRISGraphOperators` takes `top_k` and `max_hops` as other names for `ppr_top_k` and `k_hops`. `kg_PPR` is the same walk's scores as a list, best first, zero scores included.

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
- It has no graph argument and walks the default graph: its nodes after the seed are the breadth-first route's outbound nodes there. Today a seed held only by a named graph answers itself and no edges ([finding](../../Verus_verification/bugs_issues.md#F-1009)).
- Today a read during another session's `sync()` can answer the seed alone instead of raising ([finding](../../Verus_verification/bugs_issues.md#bug-str-115)).

<a id="algorithms.op.walks"></a>
[I · algorithms.op.walks]

The walk operations follow outbound edges from one start node.

- A graph walk goes breadth first up to `max_depth` (3) hops and returns at most `max_results` (100) rows of (source, type, target, hop). Its edge-type list is a sequence: hop h follows the h-th type, and the last type repeats.
  - Its rows are the edges walked from each hop's new nodes, ordered by hop and then target, including an edge back to a node reached earlier. Today two edges that reach the same node at the same hop leave only one row ([open question](../../Verus_verification/open_questions.md#algorithms.op.walks.rows)).
  - A walk whose answer is longer than one IRIS string raises an error; a k-hop read of the same size is answered.
- A graph path returns the two-hop paths start, first type, middle, second type, end, one row per step.
- A random walk returns `num_walks` (10) walks of up to `length` (20) steps from a seed.

- Working assumption: Walk the default graph's adjacency (graph key 0) in ObjectScript, library or not (option (a)). Where only a merged ^NKG route is available and a named graph has edges, refuse visibly rather than answer [] or a merged walk. An explicit graph= argument (option (c)) is a compatible extension.

<a id="algorithms.op.neighbors"></a>
[I · algorithms.op.neighbors]

The one-hop retrieval steps return what is one edge away from a list of seed nodes.
- `kg_NEIGHBORS` follows out-edges, in-edges or both, of one type or any, and lists each neighbor once unless asked to keep repeats, however the seeds are split into chunks. `kg_MENTIONS` is the same along `MENTIONS` edges.
- `kg_NEIGHBORS` reads every graph: a seed's edges in a named graph count, and a seed ID used in two graphs gives the neighbors of both ([open question](../../Verus_verification/open_questions.md#algorithms.op.neighbors.scope)).
- `kg_NEIGHBORHOOD_EXPANSION` reads one graph, the default unless one is named, and keeps an edge only when its `confidence` qualifier is at least the threshold, highest first. An edge without that qualifier is left out.

<a id="algorithms.op.paths"></a>
[I · algorithms.op.paths]

Path search finds a shortest path between two nodes inside one graph. A path from a node to itself has length zero, and an empty source or target answers no path.
- The search can follow the edges, go against them, or do both.
- The unweighted path routines answer no path for a direction they do not walk, instead of refusing it ([open question](../../Verus_verification/open_questions.md#HD-1003)).

- Working assumption: Keep the public 'in' semantics, caller reversal included. Require ShortestPathJson and ShortestLength to refuse any direction outside {out, both}, or to implement 'in' by walking from the far end. Require IRISGraphStore.shortest_path_length to reverse 'in' as execute_shortest_path does. Record the live false positive as a defect against its docstring.
- `shortest_path_length` answers the length of `execute_shortest_path`'s path for `out` and `both`; parallel edges and another graph's edges change neither.
- Today `shortest_path_length` walks `in` as `out`, so it can answer no path where an incoming path exists and a length where none does ([finding](../../Verus_verification/bugs_issues.md#bug-str-113)). Cypher's length-only route uses only `out` and `both`.

<a id="algorithms.op.paths.weighted"></a>
[I · algorithms.op.paths.weighted]

A weighted path search returns a path with the lowest total cost, even when that path has more hops than another, and returns no row when no path joins the two nodes.
- Each edge costs its stored weight. A weight of zero or less, or no weight, costs one.
- Only the stored weight can be used: naming another weight property, or a direction other than out, in or both, is refused.
- For distinct endpoints, a path that costs more than the cost limit, or has more hops than a positive hop limit, is not an answer. Zero means no hop limit in the public procedure; a negative hop limit is refused there. The native search also treats negative hops as unbounded.
- Nonempty equal endpoints return the empty path at cost 0 before the native cost-cap or node-existence check. Public empty or missing endpoint arguments are refused; direct native empty endpoints answer no path.
- With a graph named, it searches that graph. With none, it searches each graph that has edges and gives one row for each graph where it finds a path.
- Costs come back as decimal numbers, so a weight of one reads back as 1.0. A failed search raises instead of answering no row.
- The SQL function `DijkstraPath(from, to, weightProp, maxCost, maxHops, direction, types, graph)` runs the same search and answers the path's JSON text, or `{}` for no path. It refuses a caller without SELECT on `rdf_edges`, and it refuses another weight property or direction as the procedure does. A graph of `''` or NULL is the default graph.
- Today `DijkstraPath('', '')` answers a zero-length path through a node named by the NUL character, where an empty endpoint should give no path ([finding](../../Verus_verification/bugs_issues.md#bug-str-112)).
- Relationship types omitted or supplied as an empty list mean every type. As built, the search reads each adjacency leaf's representative weight; in a correctly maintained multigraph that is the lowest live edge key, which need not hold the least weight of the parallel rows. Whether the intended minimum must instead consider every stored parallel relationship remains [open](../../Verus_verification/open_questions.md#q-iter-007).

- Working assumption: Keep the current lowest-key representative route distinct from all-parallel-edge shortest path; the optimization domain needs owner choice.

## Earlier links

These links take you to the current sections and statements.

<a id="owners-and-native-readers"></a>

[Select the IRIS or native algorithm](../architecture/algorithm-execution.g5.md#select-the-iris-or-native-algorithm)

<a id="the-proof-record"></a>

[Check the evidence for a native reader](../architecture/algorithm-execution.g5.md#check-the-evidence-for-a-native-reader)

<a id="operations"></a>

[Algorithms and the results they return](#algorithms-and-the-results-they-return)

<a id="cached-answers"></a>

[When can IVG reuse an algorithm result?](../architecture/algorithm-execution.g5.md#when-can-ivg-reuse-an-algorithm-result)

<a id="algorithms.owner"></a>

[algorithms.owner](../architecture/algorithm-execution.g5.md#algorithms.owner)

<a id="algorithms.routing"></a>

[algorithms.routing](../architecture/algorithm-execution.g5.md#algorithms.routing)

<a id="algorithms.routing.revision"></a>

[algorithms.routing.revision](../architecture/algorithm-execution.g5.md#algorithms.routing.revision)

<a id="algorithms.routing.fallback"></a>

[algorithms.routing.fallback](../architecture/algorithm-execution.g5.md#algorithms.routing.fallback)

<a id="algorithms.routing.reload"></a>

[algorithms.routing.reload](../architecture/algorithm-execution.g5.md#algorithms.routing.reload)

<a id="algorithms.routing.excluded"></a>

[algorithms.routing.excluded](../architecture/algorithm-execution.g5.md#algorithms.routing.excluded)

<a id="algorithms.proof"></a>

[algorithms.proof](../architecture/algorithm-execution.g5.md#algorithms.proof)

<a id="algorithms.proof.gate"></a>

[algorithms.proof.gate](../architecture/algorithm-execution.g5.md#algorithms.proof.gate)

<a id="algorithms.cache"></a>

[algorithms.cache](../architecture/algorithm-execution.g5.md#algorithms.cache)

<a id="algorithms.cache.token"></a>

[algorithms.cache.token](../architecture/algorithm-execution.g5.md#algorithms.cache.token)

<a id="algorithms.cache.pagerank"></a>

[algorithms.cache.pagerank](../architecture/algorithm-execution.g5.md#algorithms.cache.pagerank)

<a id="algorithms.cache.erasure"></a>

[algorithms.cache.erasure](../architecture/algorithm-execution.g5.md#algorithms.cache.erasure)

<a id="algorithms.cache.concurrency"></a>

[algorithms.cache.concurrency](../architecture/algorithm-execution.g5.md#algorithms.cache.concurrency)

## Metadata

### algorithms.graph_scope

- Sources: [KNOWN_ISSUES: The ^NKG algorithm procedures raise once a named graph has edges](../../../docs/KNOWN_ISSUES.md); [USER_GUIDE algorithms](../../../docs/USER_GUIDE.md); [graph.unscoped_snapshot](../concepts/graph-scope.g5.md#graph.unscoped_snapshot)
- agent
- user-facing-behavior

Changed in 4.6.0. Before that, procedures and methods disagreed: some answered every graph merged and others the default graph.

### algorithms.op

- Sources: [USER_GUIDE §6 Graph algorithms](../../../docs/USER_GUIDE.md); [API_REFERENCE: Graph algorithms](../../../docs/API_REFERENCE.md); [_engine/algorithms.py](../../../iris_vector_graph/_engine/algorithms.py)
- Children: [PageRank](#algorithms.op.pagerank), [PPR](#algorithms.op.ppr), [WCC](#algorithms.op.wcc), [CDLP](#algorithms.op.cdlp), [subgraph](#algorithms.op.subgraph), [degree](#algorithms.op.degree), [betweenness](#algorithms.op.betweenness), [closeness](#algorithms.op.closeness), [eigenvector](#algorithms.op.eigenvector), [Leiden](#algorithms.op.leiden), [triangles](#algorithms.op.triangles), [SCC](#algorithms.op.scc), [k-core](#algorithms.op.kcore), [k-hop](#algorithms.op.khop), [walks](#algorithms.op.walks), [neighbors](#algorithms.op.neighbors), [paths](#algorithms.op.paths)
- Verus: [algo_options](../../Verus_verification/models/algo_options/NOTES.md) `theorem_same_decision`, `theorem_ranges`, `theorem_unlisted_refused`, `theorem_uncoercible_refused`, `theorem_enumerations_exact` (option checks of the centrality and community methods and procedures, as built)
- Evidence: [frozen predictions and native observations](../../uplift/consolidated/iteration-28/algo-options-PAIRS.md)
- agent
- user-facing-behavior

Edgeless nodes joined every answer in 4.6.0 (R306), and unreached PPR nodes got a 0.0 row in 4.7.0. PageRank and PPR argument checks for damping and iterations came in 4.7.0 ([USER_GUIDE](../../../docs/USER_GUIDE.md#L598-L600), [CHANGELOG](../../../CHANGELOG.md#L41)). The Cypher procedures' graph scope is in [graph scope](#algorithms.graph_scope).

State machines: [algo options](../../Verus_verification/models/algo_options/manifest.json)

### algorithms.op.pagerank

- Sources: [API_REFERENCE kg_PAGERANK](../../../docs/API_REFERENCE.md); [USER_GUIDE PageRank](../../../docs/USER_GUIDE.md); [CHANGELOG v4.6.0](../../../CHANGELOG.md); [PageRank.cls](../../../iris_src/src/Graph/KG/PageRank.cls)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior
- test-coverage

Textbook PageRank and weighting by edge count came in 4.6.0. Before, a parallel edge counted in its source's degree but passed rank once, and the scores did not sum to 1. Live coverage: `tests/e2e/test_pagerank_textbook_e2e.py`.

Findings: [Owner result cap F-1003](../../Verus_verification/bugs_issues.md#F-1003); the numerical/every-node rule is not established by the new cache-admission contract.

Audit (HD-1004): Existing authority: Global PageRank promises every default-graph node on every supported route; the hidden Owner output cap violates that documented contract. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#HD-1004).

Findings: [How many nodes should global PageRank list?](../../Verus_verification/open_questions.md#HD-1004).

Audit reproduction: [F-1003](../../Verus_verification/bugs_issues.md#F-1003) is e2e reproduced through the actual engine/Owner cap, with a passing small graph; [results](../../Verus_verification/audits/register-20261115/regressions.json). Arno route equivalence is untested.

Findings: [Global PageRank output cap](../../Verus_verification/bugs_issues.md#F-1003).

### algorithms.op.ppr


- uncertain
- Sources: [API_REFERENCE kg_PERSONALIZED_PAGERANK, ppr](../../../docs/API_REFERENCE.md); [USER_GUIDE PageRank](../../../docs/USER_GUIDE.md); [CHANGELOG v4.6.0 (R270)](../../../CHANGELOG.md)
- Verus: [ppr_walk.rs](../../Verus_verification/models/ppr_walk/ppr_walk.rs), `theorem_raw_walk_mass`, `theorem_strict_held_change_decides`, `theorem_walk_request_stays_within_iteration_budget`; [domain and roles](../../Verus_verification/models/ppr_walk/NOTES.md). The exact finite model derives graph membership, distinct valid seeds, multiplicity/divisors/transfers, dangling restart, held-score stopping and final node projection. Mathematical mass is preserved for forward or unit-reverse traversal on stable closed data; nonunit reverse scales contributions without weighting the divisor. Native numerical/serialization/collation equivalence, correct cached scores, Adj.Degree equality to raw recount, positive grouped counter/key/mirror consistency and concurrent snapshots remain providers. Typed-prefix filtering, arbitrary numeric carriers and generic native zero-map presence are not established; no product executable body is verified.
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

networkx semantics, dangling handling and weighting of keyed parallel edges by their count came in 4.6.0. A seed that is not a node stopped scoring 1.0 in 4.7.0. The results come back as a node-to-score map; `ppr()` returns a list cut to `top_k` (20).

- Children: [Score completion](#algorithms.op.ppr.completion), [Should tiny positive PPR scores share the rounded zero tie or always precede true zeros?](../../Verus_verification/open_questions.md#q-iter-008)

Open questions: [Should tiny positive PPR scores share the rounded zero tie or always precede true zeros?](../../Verus_verification/open_questions.md#q-iter-008)

State machines: [ppr walk](../../Verus_verification/models/ppr_walk/manifest.json)

### algorithms.op.ppr.completion

- Sources: [PPR definition/return contract](../../../iris_vector_graph/_engine/algorithms.py#L216-L278), [native producer limit](../../../iris_src/src/Graph/KG/PageRank.cls#L33-L72), [caller cap and graph arguments](../../../iris_vector_graph/_engine/algorithms.py#L303-L317), [every-node reader](../../../iris_vector_graph/_engine/algorithms.py#L392-L421), [store native default limit](../../../iris_vector_graph/stores/iris_sql_store.py#L2280-L2314), [four native cases](../../uplift/consolidated/iteration-10/root-ppr-cap-native.json), [independent review](../../uplift/consolidated/iteration-10/root-ppr-review-cap.md)
- Verus: [ppr_walk.rs](../../Verus_verification/models/ppr_walk/ppr_walk.rs), `theorem_producer_limit_is_derived`, `theorem_positive_input_cap_gap`, `theorem_public_default_cap_gap_from_raw_seeds`; [limits and receipts](../../Verus_verification/models/ppr_walk/NOTES.md). Any distinct raw list of more than1000 isolated valid seeds produces positive one-step scores, the actual default producer1000 and a missing ID which the larger final reader emits as0. A normalized score map, assumed cap or supplied missing-membership flag does not decide that chain. Native1002 corroboration and actual Python provider-dispatch cases remain finite evidence, not a general float/cache/runtime proof.
- Expands: [PPR](#algorithms.op.ppr)
- agent
- user-facing-behavior, data-integrity

Observed: without an exclusion list the caller omits return_top_k from the producer arguments, leaving the native1000 cap, while _ppr_every_node uses a larger positive caller limit. On1002 isolated valid seeds (one iteration, alpha1/2), public limit1002 then appends two nodes as0 although every seed scores1/1002. Supplying exclude_predicates=[] forwards limit1002 and all scores stay positive; public limit1000 and the actual fallback are passing neighbors. This is false score inference after truncation, not a complaint that an intentional cut has mass below1. [bug-plt-104](../../Verus_verification/audits/register-20261115/bugs-review.md#bug-plt-104). Runtime/provider/arbitrary numeric equivalence and the final public unavailable-provider dispatch remain qualified; no repair is implemented.

State machines: [ppr walk](../../Verus_verification/models/ppr_walk/manifest.json)

### algorithms.op.wcc

- design-verified

- Sources: [COMMUNITIES.md: Weakly connected components](../../../docs/COMMUNITIES.md); [API_REFERENCE kg_WCC](../../../docs/API_REFERENCE.md)
- Verus: [communities](../../Verus_verification/models/communities/NOTES.md) derives raw coordinate membership, synchronous minima, reachable-radius propagation and actual first-stop termination within N rounds including confirmation. Explicit insufficient budgets refuse even after labels happen to be final; empty succeeds before the guard. Weak-component interpretation requires mirrored, closed projected edges and an admitted order relation; native bodies, arbitrary identifiers/serialization, provider truth and concurrency remain unproved.
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

With a round limit the Owner answers even when Arno is loaded. Before 4.6.0 labels stopped after 100 rounds, so a long component could come back split.

Audit reproduction: [F-C1018](../../Verus_verification/bugs_issues.md#F-C1018) is e2e reproduced; [actual cases, result, neighbor and provider qualifications](../../Verus_verification/audits/register-20261115/regressions.json). This is product observation, not executable-body verification.

Findings: [The store's membership decoder refuses the Owner's components and label-propagation answers when a default-graph node is named 'components', 'communities' or 'largest' (read as an accelerated summary…](../../Verus_verification/bugs_issues.md#F-C1018).

State machines: [communities](../../Verus_verification/models/communities/manifest.json)

### algorithms.op.cdlp


- Sources: [COMMUNITIES.md: Label propagation](../../../docs/COMMUNITIES.md); [API_REFERENCE kg_CDLP](../../../docs/API_REFERENCE.md)
- Verus: [communities](../../Verus_verification/models/communities/NOTES.md) derives raw coordinate frequencies, self-loop exclusion, greatest-vote/least-label decisions, old-map synchrony, finite budget and arbitrary-round two-node parity. It does not promise convergence or resolve physical keyed-edge vote policy; repeated physical keys collapse in the source coordinate projection. Typed integer and shared admitted ordering/provider conditions remain explicit.
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

The self-loop rule and the collation tie-break changed in 4.6.0. The oscillation is documented; the documented check is to compare two adjacent round limits.

Audit (HD-1002): Existing authority: CDLP returns its last fixed iteration without an in-band settledness flag; the documented diagnostic compares k with k+1. See [current behavior, alternatives and settling sources](../../Verus_verification/audits/register-20261115/question-review.md#HD-1002).

Findings: [Should label propagation say when its labels did not settle?](../../Verus_verification/open_questions.md#HD-1002).

State machines: [communities](../../Verus_verification/models/communities/manifest.json)

### algorithms.op.subgraph

- Sources: [API_REFERENCE kg_SUBGRAPH](../../../docs/API_REFERENCE.md); [_engine/algorithms.py kg_SUBGRAPH](../../../iris_vector_graph/_engine/algorithms.py); [Subgraph.cls SubgraphJson](../../../iris_src/src/Graph/KG/Subgraph.cls#L6-L100)
- Expands: [Operations](#algorithms.op)
- Children: [PPR-guided subgraph](#algorithms.op.subgraph.guided)
- Verus: active: [retrieval_compose](../../Verus_verification/models/retrieval_compose/NOTES.md) `admit`, `expand_node`, `expand_frontier`, `lists_edge` against `rule_lists_edge`; `theorem_capped_subgraph_lists_edge_to_unlisted_node` (every input since iteration 50), witness `theorem_last_hop_edges_missing` (controls `edge-recorded-after-cap-test`, `edges-among-answered`)
- agent
- user-facing-behavior

The walk direction is not documented. A code comment still calls the traversal namespace-wide, although its Owner reads the default graph only.

State machines: [retrieval compose](../../Verus_verification/models/retrieval_compose/manifest.json)

Findings: [kg_SUBGRAPH misses edges among the outermost nodes and lists an edge to a node it left out when capped](../../Verus_verification/bugs_issues.md#bug-plt-114); [kg_PPR_GUIDED_SUBGRAPH lists almost none of the edges among its answered nodes and can answer more nodes than its cap](../../Verus_verification/bugs_issues.md#bug-plt-113)

### algorithms.op.subgraph.guided

- Sources: [kg_PPR_GUIDED_SUBGRAPH](../../../iris_vector_graph/_engine/algorithms.py#L947-L985) (the cap in its docstring, lines 956-957), [execute_subgraph](../../../iris_vector_graph/stores/iris_sql_store.py#L2500-L2560) (the Arno reader first, lines 2526-2541), [check_ppr_args](../../../iris_vector_graph/_engine/algorithms.py#L66-L76), [kg_PPR](../../../iris_vector_graph/_engine/algorithms.py#L1028-L1042), [IRISGraphOperators.kg_PPR_GUIDED_SUBGRAPH](../../../iris_vector_graph/operators.py#L112-L124), [enhancement note](../../../docs/dev/notes/enhancements/001-ppr-guided-subgraph.md)
- Expands: [Subgraph](#algorithms.op.subgraph)
- Verus: active: [retrieval_compose](../../Verus_verification/models/retrieval_compose/NOTES.md) `guided_cap`, `admit`, `lists_edge` against the rule `rule_lists_edge`, `rule_within_cap`; `theorem_guided_cap_is_ppr_top_k`, `theorem_admitted_seeds_ignore_cap`, `theorem_filled_cap_expands_only_first_node`; witnesses `theorem_guided_subgraph_drops_edges_among_top_nodes`, `theorem_guided_seeds_exceed_cap`, neighbor `theorem_guided_uncapped_lists_all_edges` (controls `edges-among-answered`, `seeds-capped`, `expand-whole-frontier-at-cap`, `guided-cap-top-k-only`)
- agent
- user-facing-behavior

Recovered in iteration 49 ([W56 predictions](../../uplift/consolidated/iteration-49/retrieval-PAIRS.md) P1-P4, R2): P2, P3, P4 and R2 held; P1 missed (the answer is capped at `ppr_top_k` nodes). Corrected in iteration 50 after [review 47-49](../../uplift/consolidated/iteration-50/REVIEW-47-49.md) item 1: the cap `min(max_nodes, ppr_top_k)` is documented intent (the docstring and the [enhancement note](../../../docs/dev/notes/enhancements/001-ppr-guided-subgraph.md)'s `top_k` "hard node cap", "`len(result.nodes) <= top_k` always"), so it is now the statement; the departures are the missing edges and the seeds over the cap ([fixture reproduction](../../uplift/consolidated/iteration-50/review-repro-20261117T031150Z.json)).

State machines: [retrieval compose](../../Verus_verification/models/retrieval_compose/manifest.json)

Findings: [kg_PPR_GUIDED_SUBGRAPH lists almost none of the edges among its answered nodes and can answer more nodes than its cap](../../Verus_verification/bugs_issues.md#bug-plt-113)

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

The ObjectScript Louvain does not guarantee connected communities and ignores `random_seed`, so the answer can differ by which implementation is installed. Arno's Leiden is outside the proof gate (see [Must the evidence gate also cover the other algorithms the native library speeds up?](../../Verus_verification/open_questions.md#q-plt-014)).

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
- Verus: [traversal_strategy](../../Verus_verification/models/traversal_strategy/NOTES.md) `theorem_khop_is_default_out_bfs`, `theorem_khop_ignores_named_graphs` (as built, iteration 57)
- Verus (iteration 57): [rebuild_reads](../../Verus_verification/models/rebuild_reads/NOTES.md) `theorem_reader_sees_seed_alone`; findings: [bug-str-115](../../Verus_verification/bugs_issues.md#bug-str-115), [bug-str-117](../../Verus_verification/bugs_issues.md#bug-str-117)

The Owner answers with or without Arno, so the result has one shape (4.6.0). A failed walk raised instead of answering empty from 4.6.0.

Observed (iteration 37, [W43](../../uplift/consolidated/iteration-37/traversal-PAIRS.md)): every case of this block agreed, including a diamond (each edge listed, the shared node once) and a 40,000-edge answer longer than one IRIS string. Verus: active: [`walk_reader.rs`](../../Verus_verification/models/walk_reader/walk_reader.rs) `theorem_khop_answers_any_size`.

### algorithms.op.walks

- uncertain
- Sources: [API_REFERENCE kg_GRAPH_WALK, kg_GRAPH_PATH, random_walk](../../../docs/API_REFERENCE.md); [_engine/algorithms.py](../../../iris_vector_graph/_engine/algorithms.py); [USER_GUIDE: shortest path](../../../docs/USER_GUIDE.md)
- Expands: [Operations](#algorithms.op)
- agent
- user-facing-behavior

Observed divergence: `random_walk` needs Arno, and without it returns an empty list after a warning, against the promise that every algorithm has an Owner. The graph path's `max_hops` argument is not used. Weighted shortest paths are a Cypher procedure and use each edge's `weight` property, 1.0 when absent; [weighted path search](#algorithms.op.paths.weighted) owns that rule.

Observed (iteration 37, [W43](../../uplift/consolidated/iteration-37/traversal-PAIRS.md)): chains, typed sequences, `max_results`, the named-graph case (nothing) and the graph path agree with this block. The walk keeps one row per hop and target, and an over-long walk raises and leaves its staged rows behind.

Verus: active: [`walk_reader.rs`](../../Verus_verification/models/walk_reader/walk_reader.rs) `theorem_distinct_keys_list_every_edge`, `theorem_same_hop_target_collapses` (as-built), `theorem_walk_overflow_raises_and_leaves_stage` (as-built), `theorem_khop_answers_any_size`.

Findings: [kg_GRAPH_WALK keeps one row per hop and node](../../Verus_verification/bugs_issues.md#bug-str-103); [A graph walk whose answer is longer than an IRIS string raises](../../Verus_verification/bugs_issues.md#bug-str-104)

Open questions: [What should `random_walk` answer, and over which graph?](../../Verus_verification/open_questions.md#HD-1001), [Should a graph walk list every edge it walks, or one row per node reached?](../../Verus_verification/open_questions.md#algorithms.op.walks.rows)

Assumption review evidence: Changed from decisions.md: **yes**. decisions.md asked for a declared scope plus an observable 'unavailable' result. The deployed ObjectScript walk runs without the library (upstream test and live), and ADMIN_GUIDE says every algorithm has an ObjectScript answer. So a real default-graph answer is the better-supported reading. 'Unavailable' remains only for a route that cannot honour the scope.

### algorithms.op.neighbors

- Sources: [API_REFERENCE kg_NEIGHBORS, kg_MENTIONS, kg_NEIGHBORHOOD_EXPANSION](../../../docs/API_REFERENCE.md); [`AlgorithmsMixin.kg_NEIGHBORS`](../../../iris_vector_graph/_engine/algorithms.py#L986-L1023), [`VectorMixin.kg_NEIGHBORHOOD_EXPANSION`](../../../iris_vector_graph/_engine/vector.py#L1055-L1121), [graph scope of Cypher without USE GRAPH](../concepts/graph-scope.g5.md)
- Expands: [Operations](#algorithms.op)
- Verus: active: [`retrieval_scope.rs`](../../Verus_verification/models/retrieval_scope/NOTES.md) `theorem_scopes_differ`, `theorem_confidence_filter`, `theorem_distinct_across_chunks`.
- agent
- user-facing-behavior

Recovered in iteration 42 from the API reference and observation ([W48](../../uplift/consolidated/iteration-42/neighbors-PAIRS.md)): every frozen case held except the assumed default-graph scope of `kg_NEIGHBORS`.

Open questions: [Which graph should the unscoped retrieval operators read?](../../Verus_verification/open_questions.md#algorithms.op.neighbors.scope)

### algorithms.op.paths

- uncertain
- Sources: [CHANGELOG 4.6.0 paths](../../../CHANGELOG.md#L525-L535); [`iris_src/src/Graph/KG/TraversalPaths.cls::ShortestPathJson`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L5-L116), [`::ShortestLength`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L117-L175)
- Playbook: [ALG-B10](../../../experiment/playbook-completion/ontology/10-algorithms.md#L219), [ALG-B10.2](../../../experiment/playbook-completion/ontology/10-algorithms.md#L221)
- Verus: the playbook's `proofs-d1e` `atrav_l2` (reviewed design) proves the direction contract; its control `control_hd1003_direction_unchecked` reintroduces the pin's behavior (finding HD-1003). As built: [traversal_strategy](../../Verus_verification/models/traversal_strategy/NOTES.md) `theorem_lengths_agree_out_both`, `theorem_in_length_differs`, `theorem_parallel_edge_invisible`, `theorem_other_graph_edges_invisible` (iteration 57).
- Expands: [Operations](#algorithms.op)
- Children: [weighted](#algorithms.op.paths.weighted), [Should the shortest-path routines refuse a direction they do not walk?](../../Verus_verification/open_questions.md#HD-1003)
- agent
- user-facing-behavior
- test-coverage
- Findings (iteration 57): [bug-str-113](../../Verus_verification/bugs_issues.md#bug-str-113)

Open questions: [Should the shortest-path routines refuse a direction they do not walk?](../../Verus_verification/open_questions.md#HD-1003)

Assumption review evidence: Changed from decisions.md: **yes**. Status moves from assumption to supported: maintainer commit 99b00ce9 states the refuse-outside-set policy for ObjectScript entry points. New live evidence shows a wrong positive answer, not just a missing one, on a public store method.

### algorithms.op.paths.weighted


- uncertain
- Sources: [`iris_src/src/Graph/KG/TraversalPaths.cls::DijkstraJson`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L256-L346) (cost order and settling `:293-342`; weight of zero or less is one `:329-331`; hop bound `:265`, `:312`; no path `"{}"` `:344-345`), [`::DijkstraCost`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L378-L448), [`::CheckDirection`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L350-L355), [`::CheckWeightProp`](../../../iris_src/src/Graph/KG/TraversalPaths.cls#L359-L365); [`iris_vector_graph/engine.py::IRISGraphEngine._proc_ivg_shortestpath_weighted`](../../../iris_vector_graph/engine.py#L1201-L1313) (one search per graph `:1275-1282`); tests [test_weighted_shortest_path.py](../../../tests/unit/test_weighted_shortest_path.py) (they drive a live engine)
- Playbook: [ALG-B10.5](../../../experiment/playbook-completion/ontology/10-algorithms.md#L225), [ALG-B10.6](../../../experiment/playbook-completion/ontology/10-algorithms.md#L226), [ALG-B10.7](../../../experiment/playbook-completion/ontology/10-algorithms.md#L227), [ALG-B10.8](../../../experiment/playbook-completion/ontology/10-algorithms.md#L228), [ALG-B10.90](../../../experiment/playbook-completion/ontology/10-algorithms.md#L229)
- Verus: [weighted_paths.rs](../../Verus_verification/models/weighted_paths/weighted_paths.rs), `theorem_complete_terminating_search`, `theorem_actual_search_terminates`, `theorem_actual_returned_path_is_optimal`, `theorem_empty_queue_is_no_feasible_path`, `theorem_admitted_self_is_zero`; [domain and source roles](../../Verus_verification/models/weighted_paths/NOTES.md). As-built state-transcription proof over a finite stable actual raw scalar graph, exact integer weights/cap and nonnegative hop bound: ordered stale queue, raw seen-hop dominance, dist/parent relaxation, optimal returned chain, no-path and derived termination. [weighted_cost.rs](../../Verus_verification/models/weighted_cost/weighted_cost.rs) `theorem_actual_dijkstra_cost_complete`, `theorem_initial_search_terminates`, `theorem_finish_correct` and `theorem_actual_json_fallback_correct` additionally derive the actual two-frontier Cost minimum/no-path/termination and hop fallback to the imported JSON transition; [transpose and source limits](../../Verus_verification/models/weighted_cost/NOTES.md). Its graph must have selected equal-effective-weight reverse coordinates. Raw public argument/refusal carrier, writer/index maintenance, arbitrary floating/JSON/collation correspondence and concurrent changes remain unproved. No product executable body is verified.
- Verus (exact rational extension): [weighted_fraction.rs](../../Verus_verification/models/weighted_fraction/weighted_fraction.rs), `theorem_raw_signed_rational_json`, `theorem_raw_signed_rational_cost`, `theorem_backtrack_reaches_source` and `theorem_json_reader_raw_fields`; [domains, controls and source roles](../../Verus_verification/models/weighted_fraction/NOTES.md). Raw signed ratios with positive denominators derive the common grid, default1/cap scaling and independent real-state transitions, parent costs, historical BestHop and unchanged-config actual JSON fallback. Complete-step coupling derives minimum/no-path, structured path sums and finite termination; negative caps and early self0 use separate actual source branches. This extends the mathematical numerical domain of the existing searches, not their raw Python/IRIS text coercion, native rounding/JSON/collation, writer/mirror maintenance or unresolved parallel-edge policy. [22 ordinary dyadic native cases](../../uplift/consolidated/iteration-11/root-fraction-native.json) and20,522 actual Python handler/source-port worlds are finite correspondence evidence, not native executable-body proof. The independent tag2 helper miss is retained and corrected; formal source and imported kernels were unchanged.
- Children: [Should weighted shortest path consider every parallel edge or the lowest-key representative graph?](../../Verus_verification/open_questions.md#q-iter-007)
- Expands: [Path search](#algorithms.op.paths)
- agent
- user-facing-behavior

Public case M12 now has substantive normalized one-sided and cost-only numerical-search contracts within the stated integer/provider fragments; broader public/numeric/serialization correspondence remains qualified. The queue proof retains stale entries and minimum-hop dominance rather than replacing the algorithm with a supplied shortest answer. [9000 paired native searches,14 public queries](../../uplift/consolidated/iteration-9/weighted-native.json), [18 boundary neighbors](../../uplift/consolidated/iteration-9/weighted-native-neighbors.json) and [four explicit mirror-state variations](../../uplift/consolidated/iteration-9/weighted-mirror-native.json) are finite correspondence evidence, not a native-body or general cost-only proof. The mode-off lowest-key harness miss is retained and withdrawn as an unsupported producer expectation; the valid mode-on4-vs1 policy remains open. Iteration10 adds [15 actual Cost/JSON/public neighbors on20 mirrored triples](../../uplift/consolidated/iteration-10/root-cost-native.json); those outputs do not expose internal BestHop or prove the fallback branch. Formal and source-port traces distinguish a Both scan-order case with equal returned8 but historical hops4/fallback versus3/no fallback. The initial shared-order81 candidate and mixed-resource83 controls are retained with their correspondence/control credit withdrawn; final88 and all8 controls independently replay cleanly. The cost-only route requires equal-effective-weight reverse mirrors: in the explicit provider-state fixture JSON keeps cost20, while a missing reverse point makes Cost answer no path and a reverse weight1 replacing10 makes Cost answer11; restoring the point restores20. These deliberately altered provider states are not ordinary-writer defects or a promise about malformed graphs.

Open questions: [Should weighted shortest path consider every parallel edge or the lowest-key representative graph?](../../Verus_verification/open_questions.md#q-iter-007)

Iteration 53, the SQL entry: [SqlProcs.DijkstraPath](../../../iris_src/src/Graph/KG/SqlProcs.cls#L160-L164) checks SELECT on `rdf_edges`, then calls [Traversal.DijkstraProc](../../../iris_src/src/Graph/KG/Traversal.cls#L11-L14), which forwards to `DijkstraJson` unchanged. [sql_procs](../../Verus_verification/models/sql_procs/sql_procs.rs) `dijkstra_path`, `theorem_sql_entry_refuses_bad_arguments`, `theorem_sql_empty_endpoints_zero_path`, `theorem_dijkstra_endpoint_neighbors`, `theorem_entries_gated` model the entry; the search stays `weighted_paths`' claim. The [binding](../../Verus_verification/results/sql_procs/20261117T051429Z-binding/receipt.json) compares 26 SQL argument sets and the CALL with a port of the documented rule. SQL hands `''` to the body as `$Char(0)`, which `DijkstraJson`'s empty test misses. Frozen predictions DJ1-DJ10 in [sqlprocs-PAIRS.md](../../uplift/consolidated/iteration-53/sqlprocs-PAIRS.md); DJ6 missed (the SQL entry refuses too).

Findings: [DijkstraPath with two empty endpoints answers a zero-length path through the NUL character](../../Verus_verification/bugs_issues.md#bug-str-112)

State machines: [weighted cost](../../Verus_verification/models/weighted_cost/manifest.json), [weighted fraction](../../Verus_verification/models/weighted_fraction/manifest.json), [weighted paths](../../Verus_verification/models/weighted_paths/manifest.json)
