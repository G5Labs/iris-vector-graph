# Weighted minimum over the actual scalar adjacency graph

Product3eaa79cf, foundation9e120916, iteration9. Known public M12 selected by the
iteration8 source-first survey; this is a known missing numerical proof, not a
blind draw or a newly discovered product defect. The pre-candidate expectations
are retained in [weighted-PAIRS.md](../../../uplift/consolidated/iteration-9/weighted-PAIRS.md)
and the independent review's source-frozen panel. Product and ontology were not
changed by this builder. Final baseline **45 verified units,0 errors**, no imported
model units, bundled vstd only, inherited Verus0.2026.10.04.426d8b0 with explicit
4 threads. These are verifier units including spec recursion checks, not45 separate
product guarantees. No assume/admit/axiom/external-body was added.

## Actual search and achieved theorem

`initial/step/relax/expand` retain the native DijkstraJson ordered raw queue,
(node,hops) dist/parent labels, stale higher-cost queue entries, and seen(node)'s
minimum accepted hop count. Repeated accepted pops at a node require strictly
fewer hops. Unbounded search uses hop0 for every label. No supplied answer, optimal
boolean, independent Bellman solver, invented stale-distance test, or node-only
visited policy decides this search. Arc order is the configured finite raw scan;
queue tie order uses ordered integer atoms. The theorem permits any minimum-cost
path, and does not promise identical tie paths under IRIS string collation.

`base_inv/closure` are derived initially and preserved by every actual Continue.
The coverage invariant says every label has a no-worse queued or accepted witness;
accepted outgoing closure is established after the whole neighbor fold. It yields
both first-target minimum cost and empty-queue absence of every feasible walk.
The theorem is over arbitrary finite feasible walks, not just the finite oracle's
simple paths. Parents are installed from accepted predecessors, stay frozen once
the child state is accepted, and strictly decrease positive integer cost backwards.
`backtrack` preserves the actual stop-by-source and missing-parent break. The proof
shows the missing-parent break is unreachable before source and derives path,
sum and bounded length. Its ghost fuel `cost+1` proves the chain finite; it is not
a product runtime guard or a supplied successful path.

`removed` and `done` are ghost histories with no search decisions. Every raw queue
pop, including a dominated stale entry, inserts a previously unremoved exact
(cost,node,hops) entry into removed. Strict dist improvement prevents reinsertion
of that exact removed entry. A finite universe of admitted nodes (source plus raw
neighbor endpoints), integer costs0..cap and hops0..H supplies a strictly decreasing
rank. With H0 only hop0 exists. `theorem_actual_search_terminates` derives a finite
trace of the deterministic actual Continue relation, bounded by initial rank+1.
`theorem_complete_terminating_search` combines this with a correct terminal result:
Returned gives a feasible minimum-cost actual parent path; Empty means no feasible
walk exists. Thus this is termination and completeness, not only correctness
conditional on an externally supplied finite trace. The rank is deliberately a
finite upper bound, not a practical runtime estimate or a complexity claim.

The admitted source==target special case has a separate empty-path/minimum0 theorem.
Identifiers need no persisted node-table membership: the actual native special0
also accepts ghost->ghost. Empty/missing endpoint refusal, negative public hops,
unsupported direction/weight property and arbitrary parameter coercions are outside
the formal Config domain; root's native/public neighbor observations retain them.

## Fragment and adjacency producer boundary

The proof admits a finite stable raw coordinate graph, exact integer scalar weights
or an absent scalar at an existing coordinate, nonnegative integer maxCost, and
nonnegative H (0 unbounded). Effective absent/nonpositive weight is1. Coordinate
existence is separate from scalar existence, so a children-only coordinate is an
arc with default1. Graph, out/in/both orientation and predicate selection are in
the transition; an empty predicate set means all predicates, matching native `[]`.
Out/in need not be equal-weight mirrors for this one-sided search theorem.

Actual source trace: Python `create_edge(weight=...)` stores a weight property in
row qualifiers; indexed `AdjIndex` routes the row to `Adjacency.RowPut`. RowPut
checks the actual GraphMode flag. Mode off uses plain Put and writes the incoming
scalar to out/in (later write wins). Mode multi uses PutKeyed; completed keyed
updates select the lowest live **ekey**, rather than the smallest weight, through
SetLeafFromLowest. Rebuild/FillTriple's simple legacy duplicate rows select the
last input row; direct scalar reweight is another writer. WeightOf defaults absent,
empty or malformed qualifiers to1 before traversal's nonpositive normalization.
This package proves minimum over the **actual raw scalar graph** regardless of which
writer produced it. It does not prove all writer/index atomicity or infer a
lowest-ekey producer premise merely from a graph's name.

Root's first mode-off keyed fixture disagreed with a lowest-ekey oracle: that miss
is archived, not deleted. Correct explicit mode multi has key0weight10,key5weight1,
scalar10 and projected shortest cost4, whereas minimum over all keyed rows is1.
The canonical parallel-edge policy question **q-iter-007** is open. This mathematical
scalar-graph theorem does not resolve the intended all-relationship policy or
create a new weighted bug. Known mode-off keyed/multiplicity roots remain intact.

No rational/common-denominator proof is claimed. A rational extension must scale
native default1 to the positive unit D, not to numerator1 indiscriminately.
Arbitrary floating coercion/roundoff, nonfinite/negative caps, collation fidelity,
concurrent/failed writers, native storage and JSON formatting remain explicit
provider/correspondence boundaries. The mathematical rank does not prove a finite
rational interval finite. DijkstraCost's bidirectional minQ lower-bound termination,
meeting witness, hop fallback and equal-weight transpose premise are **not formally
proved here**; separate actual observations do not transfer this theorem to Cost.

## Bindings and source-role recommendations

[binding.py](binding.py) executes the pinned actual Python weighted handler's raw
argument producer and final float(totalCost) consumer over an executing mutable
line-oriented DijkstraJson/backtrack port. A separate functional `initial/step/
expand/backtrack` transcription compares the entire queue/dist/parent/seen trace;
an independent finite simple-walk oracle checks optimum and witness. Neither
search receives an answer. **9073 comparisons,0 mismatches,0 socket connects**;
fixtures include graph/type/direction filters, missing/zero/negative scalar,
source-self/ghost/no-path, bound2/3/0, exact caps, stale entries, unequal mirrors
and children-only raw coordinates. Five genuine sensitivity checks reject changed
observed cost, node-only port dominance, exclusive-cap port admission, a copied
actual Python hop-producer removal and an actual Python final-cost consumer change.
An actually observed stale pop is affirmative domain coverage, not a mutant.
The port is Python source transcription, not actual ObjectScript execution.

Root's separately stamped native receipts retain9000 paired actual Json/Cost
searches (18000 native calls),14 public queries,18 public/native boundary neighbors,
and4 explicit mirror states. Ordinary stable fixtures agree with the independent
finite-walk oracle; asymmetric mirror observations distinguish Cost from Json.
These are finite correspondence observations, not a general native-body proof or
formal Cost credit. This child did not connect to native or the network.

| Source declaration | Recommended role and limit |
|---|---|
| TraversalPaths.DijkstraJson | active pure state transition/search contract within Config fragment |
| TraversalPaths.DijkstraBacktrack | active parent-chain/walk/cost fragment; actual serialization remains observation |
| Traversal.DijkstraJson | thin delegate may share that exact search relation, subject to root's role policy |
| engine._proc_ivg_shortestpath_weighted | observed real argument producer/final consumer; no formal raw-to-Config/refusal theorem |
| Adjacency.RowPut/Put/PutKeyed/SetLeafFromLowest, AdjIndex, create_edge | observed competing producer routes; no new formal writer guarantees |
| CheckDirection/CheckWeightProp/PathJson | observation/provider only; formal invalid/refusal/float bytes not represented |
| TraversalPaths.DijkstraCost | observation only; mathematical search proof remains unassessed |

## Controls, unsuccessful attempts and costs

Seven behavior-rule controls reject reversed cost order, node-only dominance,
exclusive cap, self-parent instead of accepted predecessor, default effective0,
target-at-cap loss and backtrack stopping on hop0. The eighth control removes the
**ghost** popped-entry history: it tests the termination proof's dependency, not an
actual product regression. Final eight controls fail their named isolated claim,
without resource-limit errors. Initial self-parent control only hit rlimit and was
not credited; moving the already-used concrete predecessor assertion before heavy
invariant revelation produced an ordinary named assertion failure. Initial ghost
control attribution expected two isolated failures, while only its underlying
lemma failed; the corrected one-claim manifest is retained alongside that miss.

All intermediate proof receipts/raw logs remain under results/weighted_paths:
reserved-name syntax failure; failed quantifier/sequence obligations; rlimit attempts
resolved by opaque invariant boundaries and explicit witness/trigger lemmas; 45/0
with stale expected46 metadata; earlier partial passes5,15,21,30,41; final45/0.
No increased rlimit, extra solver flag or assumption bypass was used.
Three binding setup errors are separately archived with exact script snapshots:
missing procedure_name/options carrier fields; then copied mutant globals bypassed
a module patch, so the host tried to construct an SDK wrapper from a fake object
and rejected it before any connection. Final invocation patches the invoked method's
globals. No runtime or network operation succeeded; socket connect count remains0.
The builder validation ledger records receipt hashes, timestamp-resolution verifier
cost estimates, observed binding durations and total elapsed scope. Parent owns
independent review, native runtime costs and final central coverage accounting.
