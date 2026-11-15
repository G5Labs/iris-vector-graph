# Independent Cost review: frozen neighboring expectations

Product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`, foundation
`e56c8592b040abb08eafefed65ae17e2f56bd673`, iteration10. This is builder-visible
review of known public M12, not a private evaluation. At this freeze I have read
the inherited iteration9 Cost plan/panel, canonical owner, user guide, public
handler and native Cost body; I have **not read the new weighted_cost candidate**.
No model, product, ontology, runtime or Git mutation is part of this review.

## Authority and predictions

The owner `algorithms.op.paths.weighted` and USER_GUIDE631 require the cheapest
admitted weighted path, including a dearer fewer-hop answer when a positive hop
bound excludes the globally cheapest walk. `YIELD totalCost` selects Cost; the
path-producing form selects JSON. Public tests cover minimum, cap, no path and
self, but do not by themselves establish bidirectional equivalence. Inherited
weighted_paths proves actual JSON state search and termination only. Its NOTES
explicitly leave Cost's frontsum, meetings and fallback unproved.

The following are material neighboring outcomes the new contract must distinguish:

| Neighbor | Expected observable result / necessary distinction |
| --- | --- |
| A1: s-a4,s-b1,b-a1,a-t1 | H0/3 returns3; H2 returns5 through actual JSON fallback; cap4/H2 returns none, cap5 returns5. |
| First meeting versus final meeting: s-a1,a-t9,s-b4,b-t4 | First10 is provisional; final8. |
| Frontsum: s-a1,a-b1,b-t1,s-x2,x-t2 | Roots may find4 while frontsum2; continue to3. |
| Equal-cost long/short paths (frozen plan tie fixture) | Historical Best8/hops4 may persist although an equal-cost3-hop meeting later exists; H3 still invokes fallback and returns8. BestHops is not minimum hops at optimum. |
| Strict improvement versus unchanged arrival | Remove old queue entry only on strict decrease; check opposite-label meeting after either branch. Cost has no stale queue entries. |
| Empty queue versus frontsum >= Best | Either ends the actual loop. A best has a constructed feasible historical witness; no best/over-cap cannot conceal an admitted path. |
| Cap below versus exactly optimum | Above-cap relaxations refused; exact cap accepted and may meet although its pop does not expand. |
| Ghost self versus distinct unreachable endpoints | Nonempty self returns0 before node/cap checks; distinct unreachable returns empty. Direct empty native endpoints return empty; public refuses them. |
| Complete versus missing/unequal reverse leaf | Inherited mirror4: JSON20/Cost20, then20/none, then20/11, restored20/20. A named graph or stable graph alone does not imply equal-effective-weight transpose. |

Scalar representative optimization remains as-built, with parallel-edge policy
q-iter-007 unresolved. Neither this review nor the Cost theorem can choose that
policy by proving a scalar-graph minimum. No new product defect is predicted here.

## Independent acceptance obligations

Trace actual queues/dist/hops/done and direction/type/graph selection; no assumed
answer, optimal boolean, independent DP search or supplied terminal trace may
decide execution. Per-side exact queue and settled closure must be established
from initialization and every actual transition. Dist witnesses come from raw
relaxation; historical Best retains the exact pair of walks and hops from its
strict update, rather than reading mutable labels later.

The key proof is crossing/frontsum: for any admitted hypothetical walk cheaper
than Best (or any walk if Best absent), first forward-unsettled and last
backward-unsettled vertices cannot cross. A shared settled vertex or the edge
across adjoining settled regions must produce a dual-label sum no greater than
that walk. Otherwise the two frontier minima sum no higher than its cost. Empty
frontier and frontsum terminal rules then rule out a cheaper walk. This must be
derived, not a premise named invariant without preservation.

Finite two-side done-set growth supplies termination (at most twice the finite
node universe), with finite raw neighbor folds. Positive H plus historical
BestHops>H must run the imported actual JSON search on unchanged config and derive
its terminating result. A fitting historical Best witness proves bounded
feasibility; lack of an admitted unbounded path proves bounded absence. Check
source ghost/self, fallback source special case and distinct endpoints explicitly.

Exact integer stable graph, numeric/coercion, native collation/JSON and mirrored
provider boundaries must remain visible. Inspect imported dependencies and their
stamps, isolated named control failures, executing Python handler/port and final
float consumer. Finite 31,104 preparation comparisons and native neighbors are
correspondence evidence, not substitutes for these proofs.

Sources: [frozen prior panel](../iteration-9/weighted-cost-next-PAIRS.md),
[proof plan and cases](../iteration-9/weighted-cost-next-plan.md),
[preparation receipt](../iteration-9/weighted-cost-next-validation.json),
[mirror4](../iteration-9/weighted-mirror-native.json),
[weighted owner](../../../ontology/features/algorithms.g5.md#algorithms.op.paths.weighted),
[prior JSON scope](../../../Verus_verification/models/weighted_paths/NOTES.md),
[Cost body](../../../../iris_src/src/Graph/KG/TraversalPaths.cls#L378),
[public route](../../../../iris_vector_graph/engine.py#L1201),
[user guide](../../../../docs/USER_GUIDE.md#L631).
