# Independent weighted proof architecture and source review

Product3eaa79cf; foundation input9e1209165d5076039d2ee315cc5cf67e4aa00856.
Frozen [neighbor panel](weighted-proof-review-PAIRS.md) predates the new source/
candidate inspection. Docs/test sources include USER_GUIDE631-668, the canonical
weighted owner, live weighted/cost/graph E2E tests and public parameter tests. The
misnamed unit weighted-shortest-path file requires IRIS and was **not** executed.
No private evaluator input, model/shared/Git edit, native/runtime/network access
or security scenario occurred in this review. Parent owns native evidence.

**Architecture verdict:** the actual queue/relaxation algorithm can be proved on
a stable finite positive-effective-weight fragment with a local frontier invariant.
There is no mathematical blocker and no need to replace it with a dynamic-programming
oracle, supplied answer or a contract accepting whichever result was returned.
The following is a source review and actionable proof plan, not a claim that the
builder's unfinished proof or the executable ObjectScript is verified.

## Source decisions the model must preserve

`TraversalPaths.DijkstraJson` :256-346 validates weight property/direction, derives
the graph key, treats positive maxHops as bounded, returns empty for empty endpoints
and returns zero-length self before the search. Bounded states are (node,hops);
unbounded states use hops0. The priority queue is keyed cost,node,hops, with global
minimum cost chosen before node/hop tie ordering. Relaxation updates dist and parent
on strict improvement but **does not remove the older queue entry**. The actual
stale-entry argument must therefore be proved, rather than modeling decrease-key.

`seen(node)` is a hop count, not a boolean visited set and not the whole settled
state set. A pop is skipped when an earlier accepted arrival has no more hops.
Otherwise seen is overwritten with the strictly smaller hop count, potentially
at a larger cost. The algorithm's cost-ordered pops justify the cost half of this
dominance test. A ghost history must retain **all** accepted (node,hops,cost) states;
the current seen value alone loses earlier cheap/high-hop witnesses.

The target test occurs after seen is written and before cap/hop expansion checks.
Neighbors are filtered by direction, graph and type, then by seen dominance. Raw
leaf weight is read with default1, converted numerically, and values<=0 become1.
Candidate costs greater than cap are rejected; equality is allowed. Expansion at
cost>=cap is skipped, safely for a non-target because every effective edge is
strictly positive. A state at the positive hop limit is likewise not expanded.

`DijkstraBacktrack` :450-478 follows parent(node,hops), prepending predecessor,
predicate and edge cost. It terminates on **node==source**, not merely hops0. If
the parent is missing it breaks and still emits PathJson. Thus correctness must
prove that missing-parent/truncated reconstruction is unreachable for an accepted
target in the represented fragment; the reader does not refuse a broken chain.
`PathJson/JsonFloat` :481-514 produces edge-cost and total decimal numbers; full
JSON/native numeric formatting is an observed/provider boundary, not graph math.

## Minimal DijkstraJson invariant

Let K be (v,h), with h=actual length when bounded and h=0 otherwise. Keep actual
Q/dist/seen/parent and ghost Done records with accepted cost and acceptance index.
No optimum answer is an input. Define Covered(v,h,c) as existence of either a Q
entry or a Done record at v with no greater hops and no greater cost. Ties need
not select one particular node for an optimality theorem.

At complete-loop boundaries maintain:

1. Every discovered label and Done record has a real source walk, correct cost,
   graph/type/direction, and a valid hop count. Costs are nonnegative; arc costs>0.
2. Q's selected cost is the actual minimum of its finite keys. Popped costs never
   decrease. Every seen(n) has a Done witness with that hop count and cost no more
   than any current Q cost; seen is the least accepted hop count at that node.
3. Each dist(n,h) is no more than each surviving Q entry for that exact state, and
   its current label has a Q entry **or** seen(n)<=h. This derives, rather than
   assumes, that a nondominated popped entry equals its current dist: any cheaper
   same-state entry either remains (contradicts minQ) or was popped earlier (would
   already dominate this state). It handles retained stale queue entries.
4. Every Done record's eligible outgoing relaxation is Covered(v,next,c+w).
   Eligibility means next within a positive bound and c+w<=cap. This is local
   relaxation closure, not an assumed global minimum. Existing better labels give
   coverage; a seen skip gives a Done witness with cost<=current pop<=candidate.
5. Dist/parent for an accepted state never changes afterward. Future relaxations
   to that same h are skipped because seen never rises above h. Each parent was
   installed from an already accepted predecessor with smaller cost and earlier
   acceptance index. No accepted target existed before the current target branch.

Newly popped current work does not yet have full outgoing closure. Either make a
step pop+complete-neighbor-fold, prove the fold, and reestablish the invariant, or
carry current/remaining-arcs as a phase. Do not assert closure immediately after
adding the current Done record. Target optimality uses the **pre-pop** no-earlier-
target invariant, because the source writes seen before testing target.

Why this suffices: suppose a feasible source-target walk costs W less than the
accepted target's minimum queue cost C. Every prefix costs<C. Covered cannot use
a Q witness there (all queue costs>=C), so each prefix has a Done witness. Its
local outgoing closure yields Covered for the next prefix; lower hop counts keep
the extension within the same bound. At the target this contradicts either no
earlier Done target or minimum Q. If Q is empty, the same induction excludes every
feasible path. This gives both optimality and no-path completeness using the actual
frontier, not a separate solver.

Termination is also finite: each repeat accepted at a node strictly lowers seen
hops. At most N*(H+1) accepted states exist for finite N and positive bound H;
unbounded h0 allows at most N. Each complete adjacency scan inserts finitely many
entries, and each loop removes one. Backtracking's bounded h decreases. For the
unbounded case use the earlier predecessor acceptance index / finite Done rank;
positive **integer** cost decrease is another valid rank, but decreasing arbitrary
rational costs alone is not a well-founded argument.

Suggested small proof units: queue-label coverage; seen dominance witness; accepted
pop equals dist; parent freeze/chain witness; fold establishes outgoing closure;
Covered monotonicity across a pop/skip/relax; path-prefix frontier; target optimality;
empty-frontier completeness; finite expansion/queue drain; backtrack projection.
The semantic specification may quantify all valid walks and their costs; it must
not run an unrelated DP implementation as the transcribed producer or take ans
as a transition label as the existing result-contract abstraction does.

## DijkstraCost: source-specific two-sided proof

`DijkstraCost` :378-448 keeps two ordinary node-based searches, dist/hop/PQ/Done
per side. A decrease removes the old queue entry here, unlike DijkstraJson. Side1
walks the requested orientation; side2 its transpose. Source chooses the cheaper
top side. Each side's popped label is its minimum unsettled cost and settles once.
Its tentative label retains a real path/hop witness. All current doubly-labeled
vertices have been considered for Best; Best keeps a valid concatenated path
witness and the hop count **at the moment of that Best update**, even if labels
later change. A ghost retained witness avoids conflating current hop maps with
the historical best pair.

For the stop `top1+top2>=Best`, prove: if a source-target walk of cost D<Best exists,
the first forward-unsettled vertex and last backward-unsettled vertex along a
shortest walk cannot cross. An overlap or crossing edge would already yield a
shared-label meeting cost<=D, contradicting the Best invariant. With frontiers
uncrossed, the two minimum queue costs sum to at most D. Thus the stop condition
excludes a cheaper path. If one queue is empty, its completed relaxation closure
reaches every feasible capped path, including the opposite root's zero label,
so the best meeting is final or no feasible path exists. Keep this argument at
full-iteration boundaries after all meeting updates.

The hop-bound wrapper has a short separate argument: if this globally cheapest
Best witness has hops<=H, it is also cheapest in the bounded subset. If its hops
exceed H, source calls the **actual bounded DijkstraJson**, and returns that path's
total or empty. Equal-cost witnesses with different hops do not invalidate this:
choosing a long equal-cost witness can trigger an unnecessary fallback, which still
answers correctly. Do not optimize away the fallback based on existence of some
unrecorded short equal-cost witness. The cost search itself ignores hop bounds
until this final branch.

Reverse search requires an explicit producer premise: in/out are equal-weight
transposes for the graph read. DijkstraJson over raw directed leaves alone does
not discharge it. A stable but asymmetric out-only a->x->t can have Json cost2
while the cost search's backward queue empties with no meeting. That is a sanity
counterexample to dropping the premise, not a newly reproduced native bug. Complete
ordinary Adjacency writers set both leaves; postfailure/raw restore/concurrent or
stale physical mirrors still need their own correspondence/ownership evidence.

## Raw adjacency producer and numerical boundary

`Adjacency.RowPut` :476-489 selects Put for simple graphs and PutKeyed for multi.
WeightOf :750-766 defaults absent/empty/malformed qualifier weight to1; general
JSON and numeric coercion are not mathematical integer decoding proofs.
PutKeyed :212-260, RowUpdate :506-533, RemoveKeyed and SetLeafFromLowest :874-881
maintain one scalar leaf at the **lowest live ekey's** weight, with children for
the parallel rows. FillTriple :838-857 uses that lowest row in multi mode, but
the last supplied row in nonmulti legacy-duplicate input. Put/PutShadow refresh
the bare leaf and mirror directly. Writer sequencing, rolled-back rows, functional
index declaration and competing raw writers remain explicit conditions.

Both searches read that scalar leaf, not every multigraph child. Therefore a
multi triple with low-ekey weight9 and high-ekey weight1 is costed9, not1, until
the representative changes. Minimum cost over the **derived adjacency graph** is
different from minimum over every stored parallel SQL row. Do not silently replace
lowest ekey with min weight or claim the stronger SQL-multigraph minimum. The
parent's producer function/role binding should state this directly.

Neighbor presence is also separate from scalar presence: `$Order` finds a child-
only neighbor; `$Get(leaf,1)` supplies effective1. Normal complete producer shapes
have scalar leaves, but dropping child-only coordinates merely because a scalar
map has no value would narrow raw-state scope. Model an arc set plus optional
scalar, or state the incomplete-raw-global restriction explicitly.

Integer proof plus finite mathematical order/addition is already useful. For an
exact rational extension via scale D, default effective1 must become scaled D,
positive weights/caps/sums scale consistently, and readers divide by D. Mapping
native0.25 to model1 while also mapping raw0->effective1 to model1 is incorrect.
Native +coercion, decimal precision, overflow, canonical numeric-key ordering,
cost ties, nonfinite values and differing association in the two-sided sum remain
provider questions. A finite quarter-weight native sample is corroboration, not
a universal floating-point theorem or proof of all rational representability.

## Public boundary and retained existing hits

The real handler :1201-1313 forwards actual source/target parameters, validates
weight property/direction, serializes types, selects graph IDs and chooses Cost
only for exactly YIELD totalCost. Later-clause translation can route differently.
Public negative maxHops is **refused** by `_int_argument(...minimum=0)` even though
native nonpositive maxHops means unbounded. Explicit types=[] means **all**, not
an empty allowed set. maxCost has no nonnegative validation. Native self returns0
before cap/node-existence checks; with no edge-bearing graph the public graph
enumeration falls back to default. These source-derived neighbors are retained
after the original panel, not invented intended policy or newly counted defects.

Existing P `atrav_l1/l2` remains a useful unweighted result contract (direction,
least walk length, graph scope), but its Sp answer is a supplied result consistent
with the contract, not an implementation/numerical Dijkstra proof. Preserve that
hit and qualification. P Unit L1/L2 is a separate Bolt/HTTP transaction contract;
it is not weighted search and must not be recounted as missing/covered numerics.
Existing writer/graph-layout proofs and prior wrapper unit tests remain useful
inputs; new weighted queue proofs add a different material guarantee. No foundation
convergence follows from them or from the finite checks below.

## Bounded sanity evidence and root-native fixture panel

[Probe](weighted-proof-review-probe.py) transcribes queue/relaxation/backtrack and
two-sided cost/fallback with exact Fraction arithmetic, and independently enumerates
finite simple paths for sanity. It does not import/execute ObjectScript or consume
a precomputed answer. On49 small graphs, directions, predicate filters, caps,
hop bounds and endpoints: **10,656** comparisons, zero mismatches, **87** fallback
journeys. The node-only-settlement mutant loses the bounded fixture. An out-only
mirror challenge demonstrates why the cost transpose premise matters. Runtime
0.220s, source hashes and all decisive cases retained in its JSON/log. These are
finite source-shaped checks, neither native evidence nor generic proof units.

Suggested minimal serial root-owned native panel, using ordinary create_edge
writers under isolated graph names and reading actual leaves/rows as well as public
results (clean up only these graph IDs):

1. A->X5,A->B1,B->X1,X->T1: Json and public full path H0/H3 cost3; H2 cost6 and
   Cost-only triggers bounded fallback. H2 cap5 empty, cap6 exact6. Assert actual
   nodes/rels/cost sum/endpoints, not only totalCost.
2. Reverse the query: out absent, in and both traverse the reversed path. Distinct
   graph with same IDs but direct cost8 must remain independent. A missing named
   graph/default fixture gives no cross-graph path.
3. A chain with absent,0,negative weights costs1 per edge; a separate quarter-weight
   chain observes exact simple fractional totals. A type filter excluding the only
   connection is empty, while types=[] retains every type.
4. In a temporary multigraph (`set_multigraph(graph,True)` as current E2E fixture),
   create parallel same-(s,p,o) rows in known ekey order at9 then1. Confirm lowest
   ekey leaf/out-in mirror and weighted result9; deleting that exact low row via
   the indexed row writer changes the representative/result to1. Use the existing
   multigraph E2E fixture API/SQL rather than assuming repeated simple create means
   two rows. Do not equate per-row oracle minimum1 with adjacency minimum9.
5. Optional ordinary base cases: empty endpoints native empty, nonempty missing
   self ID native zero (including negative cap), public negative hop refusal,
   invalid weight property/direction refusal. These qualify raw/native/public
   boundaries and should not inflate the numerical optimum claim.

No native asymmetry/corruption experiment is required merely to illustrate a
premise; the in-process challenge already preserves its mathematical role. Root
can decide whether an existing legitimate producer-failure receipt warrants that
additional native scope later. Math remains tractable; broad provider precision,
concurrency and every raw-writer transaction are unresolved boundaries, not an
excuse to substitute a supplied-answer theorem.
