# DijkstraCost: next formal implementation plan

Product3eaa79cf, known publicM12. This is source-first preparation during iteration9
sealing. No Cost model or theorem was added; current JSON proof remains45 units.
The next archive must precede the Cost candidate. Source-frozen expectations and
inherited A6/mirror4 are in weighted-cost-next-PAIRS.md/start.json. The actual Cost
body is TraversalPaths.cls378-448, with Python cost-only route engine.py1291-1300.

## Source decisions that the next state machine must retain

Represent each side's queue as a set of (cost,node), not JSON's stale-entry queue.
Strictly smaller dist removes the exact old queue entry then inserts the new one;
otherwise dist/hop remain unchanged. Done skips same-side neighbors, and popped
nodes never reenter that side. Dist/hop persist after a pop. There are two roots0
and the side with smaller top is chosen (forward on equal tops). Source checks
empty frontier before frontsum>=Best. Either can terminate with no best, best over
cap, or a valid admitted best, with the corresponding returned behavior.

The outgoing fold scans actual selected raw adjacency. Effective absent/nonpositive
weight is1; newCost==cap is admitted; a popped cost>=cap has no admissible outgoing
edge because weights are positive. Each relaxation checks opposite dist after the
conditional local improvement, even when this particular arrival did not improve
local dist. Best and BestHops change only on a strictly smaller meeting sum.

The bounded wrapper does not run a hop-aware bidirectional search. If its recorded
best witness fits H, that witness establishes bounded feasibility at the global
unbounded minimum. Otherwise it delegates to actual DijkstraJson with unchanged
graph/cap/H/direction/predicate arguments. The next model should expose this actual
fallback event/config and import JSON's derived terminal-trace theorem, then project
its returned total cost. It must not replace fallback by an oracle/optimal boolean
or an arbitrary supplied result. No best within cap implies no unbounded path,
hence no bounded path and no fallback is necessary.

## Stable graph/provider relation

Reuse the existing raw Config/Arc/effective selection semantics where practical.
Define reverse_arc(tag,g,u,p,v)=(1-tag,g,v,p,u). Require each selected forward raw
arc's reverse exists in the backward selection with equal **effective** weight,
and conversely. This is a per-coordinate transpose condition, not an assumption
that graph names or SQL rows imply correct mirrors. Tag flips matter for out/in;
both includes each selected orientation. Raw0 versus absent scalar can both be
1 effectively. Strict raw equality is stronger than needed. IDs include admitted
request endpoints and raw arc endpoints; no persisted node-table premise.

The stable exact-integer fragment keeps nonnegative cap and nonnegative H, with
H0 unbounded. Mathematical tie order is any fixed total ordered-atom order;
minimum-cost correctness must not promise an identical native tie path. Scalar
projection versus all keyed rows remains q-iter-007, not resolved here. Arbitrary
float/coercion/roundoff, negative/nonfinite cap, concurrent/failed producer states,
empty/public parameter validation and general native-body fidelity remain qualified.

Root's inherited mirror4 observations are decisive provider neighbors: ordinary
20/20; missing reverse Json20/CostNone; unequal reverse Json20/Cost11; restored20/20.
The finite source port reproduces those three distinct shapes. No new ordinary
writer bug or concurrency event is inferred, and the next Cost theorem must not
silently assume transpose without naming it.

## Sufficient invariants and proof order

1. Per-side exact queue and derived witnesses. Queue entries are exactly current
   dist labels whose node is not Done, one per node. Every dist label has a ghost
   path from that side's root with cost=dist and length=hop, derived at each strict
   relaxation from the accepted predecessor's path. Ghost witnesses do not decide
   execution and need no actual Cost parent array (there is none). Accepted labels
   are frozen. A full neighbor fold establishes closure for all accepted nodes;
   keep the freshly accepted node separate until its fold is complete.
2. Per-side frontier/settled minimum. Derive initially and preserve all Continue
   transitions. For an arbitrary feasible root-to-node walk whose endpoint is not
   Done, its first unsettled vertex is queued at no more than prefix cost. Thus a
   minimum pop cannot be more expensive than a hypothetical cheaper route to it;
   every Done label is minimum against all feasible walks in that oriented graph.
   This is a proof of the actual queue, not an alternative Dijkstra oracle.
3. Meeting invariant. At loop boundaries Best is absent iff there are no dual
   labels; otherwise it is the minimum current sum distF(v)+distB(v) over dual
   vertices. Keep an immutable best path-pair/hop snapshot derived when that best
   is installed, and prove its concatenation a forward walk using transpose.
   This snapshot safely handles later label changes and avoids assuming the best
   path is a live mutable parent chain. It may cost more than cap during search.
4. Global two-frontier lemma, without a supplied optimum. Take any feasible s->t
   walk P of cost D with Best absent or D<Best. Let i be its first forward-unsettled
   vertex and j its last backward-unsettled vertex. All-forward-Done or
   all-backward-Done would dual-label the opposite root and force Best<=D.
   If i>j+1, an intervening vertex is Done on both sides and the settled minima
   force Best<=D. If i=j+1, forward closure across that crossing edge labels the
   backward-Done vertex at no more than prefix cost, again making a dual sum<=D.
   Thus i<=j; the two queued prefix/suffix witnesses give TopF+TopB<=D. This is the
   core hard lemma to implement, not leave as an assumption or finite test.
5. Correct terminal result. The lemma rules out every cheaper feasible P when
   frontsum>=Best. Empty-frontier termination contradicts the two required queued
   witnesses for any cheaper P, or any P at all when no Best exists. The derived
   Best walk provides the upper bound; therefore admitted Best is a feasible
   global minimum, and absent/over-cap best means no admitted feasible walk.
6. Actual termination. Let the finite node universe include both roots and raw
   endpoints. Exact queue + Done skip means each Continue accepts a previously
   unaccepted (side,node). Rank=(N-|DoneF|)+(N-|DoneB|) strictly decreases, so at
   most2N accepted pops, with finite neighbor folds. Derive a finite terminal trace
   via this rank, as JSON already does; do not assume a terminating trace or add a
   runtimeBudget. Then combine fitting-hop best witness versus derived actual JSON
   fallback to obtain bounded/unbounded Some/None completeness and minimum cost.

The feasible-path frontier lemma can avoid defining a global minimum as a model
input. Best's own witness plus universal comparisons yields the minimum theorem.
Spec opacity and small witness/sequence lemmas from JSON should limit accidental
quantifier expansion. Importing JSON45 rechecks45 units; new Cost units must be
reported separately. The mathematical proof is tractable; no provider-blocked
label is appropriate merely because the crossing lemma takes work.

## Hop snapshots and concrete counterchecks

The probe instruments full ghost label paths, not just an expected hop number.
It checks exact queue correspondence, path/cost/hop consistency, settled minima,
Best=min current dual sum, recorded meeting cost/hop equality, Best path validity,
and the proposed frontier lower bound at every loop boundary. The oracle appears
only in assertions and output comparisons; no search decision reads its answer.

- A1: s-a4,s-b1,b-a1,a-t1 first records cost5/hops2, then improves the same meeting
  label and Best to3/hops3. H2 must fall back to JSON and return5; H3/unbounded3.
- Equal-cost wrong-hop tie: s-a2,a-b2,b-c2,c-t2 versus s-x3,x-y2,y-t3. Best8/hops4
  is installed at b. Later equal meetings at y and x have hops3 and are ignored.
  H3 still falls back and returns8. Thus BestHops is not minimum hops among all
  cheapest paths, and bestHop>H does not prove every globally cheapest path is too
  long. It only justifies the conservative fallback branch.
- First intersection: s-a1,a-t9 versus s-b4,b-t4. The scan first installs10 then8;
  returning the first meeting instead of completing the search returns10 wrongly.
- Frontsum neighbor: s-a1,a-b1,b-t1 versus s-x2,x-t2. After roots Best4 while
  TopF+TopB=2. Correct source guard continues to3; adding2 to the frontsum guard
  stops wrongly at4. This is a distinct threshold contrast.

Label paths/hops can change while searching: the final probe observes1098 label
updates after a Best exists, including69 updates at a then-recorded meeting vertex.
Those meeting changes reduce a constituent cost, so the same relaxation installs
an improved Best/hop snapshot. No sampled recorded best vertex changed while
Best stayed fixed; the boundary invariant checks its current cost and hop sums.
This is a source-derived candidate invariant supported by finite checks, not a
new universal theorem. The immutable historical snapshot is sufficient even if
that stronger current-meeting invariant is omitted from the proof.

## Finite observations, controls and costs

weighted-cost-next-probe.py/json/log contain31,104 cases over144 finite graphs:
53 actual source-shaped JSON fallback calls;273 decrease-key updates;48 ignored
shorter-hop equal meetings;0 result mismatches against independent finite-walk
enumeration. Six sensitivities pass: no fallback, zeroed BestHop, first meeting,
same-way backward traversal and prematurely loosened frontsum each change a
result; omitted old queue deletion violates exact-queue correspondence (its cost
need not differ). The latter is not advertised as a numerical counterexample.
Stale queue entries are JSON's behavior; Cost must retain decrease-key.

The initial successful30,888-case script/receipt/log are retained as
weighted-cost-next-probe-initial.*. The additional frontier contrast caused the
only rerun; both succeed. No failed attempts or surviving controls are hidden.
Final measured port/oracle run0.80s, zero socket connections. This is preparation
sanity evidence, not product execution, native numerical proof or new coverage.
No Verus Cost run has occurred, so its solver cost is unmeasured. Previous JSON
proof cost is a reference only, not a budget or stopping condition for next round.

## Precise optional next native panel for root

Use a task-owned named graph per fixture, ordinary successful create_edge(weight=)
with distinct triples and explicit raw out/in observations; no keyed projection
premise is needed. Suggested IDs prefix `cost10:` and graphs `cost10:a1`, `:tie`,
`:frontsum`, `:first`. Root alone owns native/runtime setup and execution.

Call orders:
`TraversalPaths.DijkstraCost(src,dst,cap,'out','[]',graph,H)` and
`Traversal.DijkstraJson(src,dst,'weight',cap,H,'out','[]',graph)`.
Public cost route is `USE GRAPH 'g' CALL ivg.shortestPath.weighted('s','t',
'weight',20,H,'out',[]) YIELD totalCost RETURN totalCost`.

Use A1 H0/2/3 (3/5/3), H2 cap4/5 (none/5); tie H0/2/3/4 (8/none/8/8), cap7/8
(none/8); frontier cap2/3 (none/3); first-intersection cap7/8 (none/8). These
numeric public/native observations do not expose local BestHop/fallback branch
internals, so branch credit still requires formal/source-port correspondence.
The existing mirror4 panel already supplies the adverse transpose neighbors;
rerun only when setup/provider changes make it useful. Native graphs must be
interpreted through observed scalar leaves, preserving q-iter-007 qualification.
