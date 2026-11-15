# Independent weighted-path expectations before implementation/candidate

Product3eaa79cf; input foundation9e1209165d5076039d2ee315cc5cf67e4aa00856.
Selected from README, USER_GUIDE631-668, canonical algorithms.op.paths.weighted,
and weighted shortest path, DijkstraCost and graph-scoping tests. The file under
tests/unit/test_weighted_shortest_path.py is a live test and is read, not executed.
No candidate model or implementation body has been inspected for this review yet.

Known public M12 is an existing missing numerical proof, not a newly found defect.
Existing unweighted shortest-path/P Unit contracts do not prove weighted minimum
cost. The canonical owner explicitly says neither previous arm has that contract.
Do not count finite DijkstraJson/DijkstraCost agreement as independent optimality.

| Neighbor | Owning-doc/test expectation to preserve |
|---|---|
| direct expensive edge vs longer cheap route | minimum total effective weight, not minimum hops |
| bounded node/hops vs node-only settlement | a cheaper high-hop arrival must not discard a costlier arrival with more hop budget |
| maxHops2/3/0 | bounded cases differ; nonpositive hops is unbounded |
| exact cap vs one below | equality admitted, greater cost refused |
| unreachable vs source==target | no row vs zero-length cost0; empty endpoints no path |
| stored positive / zero / negative / absent | positive retained; other effective weights1 |
| outgoing / incoming / both | derive traversed orientation; retain graph/type filters |
| graph1 vs graph2 vs default/unspecified | graph-specific answer; unspecified one answer per graph with edges |
| unsupported weight property/direction | explicit refusal, not no path |
| full path vs cost-only route | same minimum where both algorithms apply; returned path endpoints/edges/cost sum must be a real witness |
| equal-cost alternatives / parallel rows | any valid minimum unless tie policy promised; do not assume lowest numerical row weight wins |
| positive fractional weights | rational proof fragment only if native arithmetic/order correspondence explicitly scoped; arbitrary float numerics remains provider work |

Decisive hop-budget fixture (integers): A->X5, A->B1, B->X1, X->T1.
Unlimited or limit3 minimum3; limit2 minimum6; limit2/cap5 absent; limit2/cap6
present6. X must have distinct states (X,1) and (X,2). This is a structural invariant
challenge, not an independent numerical oracle or a precomputed answer input.

Later source review will inspect queue pop, relaxation, settling and predecessor
backtracking; DijkstraCost's two-sided lower-bound termination and fallback; raw
adjacency's representative ekey/effective weight. Stable finite integer/rational
fragment only. No native/runtime/network or product/shared/model/Git edits by this
reviewer. Root owns any native fixture observations.

## Additional source-derived neighbors, retained after inspection

These are not retroactive blind predictions. Native src==dst precedes cap and
node-existence checks, so nonempty self returns0 even for a negative cap. Public
maxCost has no minimum, while public maxHops has minimum0 despite native <=0 being
unbounded. `types=[]` means no filter/all types. With no graph carrying edges,
the public graph enumeration falls back to default. Normal multigraph adjacency
chooses the lowest live ekey's leaf weight, not the minimum row weight. Reverse
cost search needs symmetric equal-weight mirrors; a stable but asymmetric raw
out/in shape does not establish that premise. All are retained scope/outcome
challenges, not newly adjudicated bugs or owner decisions.
