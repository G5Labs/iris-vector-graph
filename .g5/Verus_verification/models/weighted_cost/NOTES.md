# Two-frontier weighted cost and actual JSON fallback

Product3eaa79cf; foundatione56c8592 (sealed iteration9); iteration10 before archive
recorded in cost-start.json. Known publicM12 continuation from the source-first
iteration9 cost plan and31,104-case sanity panel, not a blind draw or new product
bug. Initial expectations and input hashes precede this candidate in
[cost-PAIRS.md](../../../uplift/consolidated/iteration-10/cost-PAIRS.md).

Final baseline **88 verified units =43 new +45 imported/rechecked** from unchanged
weighted_paths.rs. New43 comprise40 proof functions and3 recursive spec checks;
helper units are not separate product guarantees. Bundled vstd, inherited pinned
Verus0.2026.10.04.426d8b0, explicit4threads. No new assume/admit/external body/axiom,
solver flag or increased resource limit. This is mathematical transcription and
source correspondence, not verification of compiled ObjectScript/Python bodies.

## Actual deciding algorithm and achieved contract

Side retains the actual ordered (cost,node) queue, dist, hop and Done. A strict
distance decrease removes the old queue entry before adding its replacement;
there is exactly one current queued label per unsettled node on that side.
Unlike JSON, old entries are not retained and there is no stale/done pop guard.
The cheaper frontier is selected, forward on equal tops. Either empty frontier
halts; otherwise frontsum>=Best halts. Inclusive cap and the cost>=cap expansion
stop are retained. Each side scans its actual direction-dependent primary tag
then the opposite tag under Both. Predicate empty means all predicates.

Relaxation first skips same-side Done and over-cap neighbors, conditionally
improves the local dist/hop, then checks the opposite label even if this arrival
did not improve local dist. Only a strictly cheaper meeting replaces Best and
BestHop. Ghost per-label walks are derived from accepted predecessor witnesses;
the actual Cost method has no parent array. A new best snapshots a concatenated
forward/backward ghost walk and its hop length. The witness is historical and
immutable, rather than an assumption that mutable labels stay fixed or that
BestHop minimizes hops among all cheapest paths.

The initially derived invariant and every actual Continue preserve exact queues,
derived cost/hop witnesses, settled minima, outgoing closure and the historical
best witness. The key theorem follows any arbitrary feasible s->t walk through its
forward-Done prefix. At its first unsettled vertex x, the forward queue has a
label no more expensive than that prefix. If x is backward-Done, backward settled
minimality on the reversed suffix makes a current dual sum no greater than the
whole walk, contradicting an absent/more expensive Best. Otherwise backward
closure gives a queued suffix witness. Thus a cheaper feasible walk requires both
queues and their minimum costs sum no more than that walk. This is derived from
actual state, not an input optimum, Bellman oracle or assumed crossing property.

It proves both frontsum termination minimum and empty-frontier completeness:
within cap, an admitted Best is a feasible global minimum; no Best or over-cap
Best means no feasible unbounded walk. Every Continue marks a previously unmarked
(side,node) Done. The finite node universe includes request endpoints plus raw arc
endpoints, so the rank of unaccepted side/node pairs decreases. A finite actual
terminal trace is constructed with at most2N pops (trace length<=2N+1). No finite
trace, runtimeBudget, eventual fairness or practical resource limit is assumed.

When recorded BestHop fits positive H, its historical walk is a bounded feasible
witness at that minimum. Otherwise the model invokes the actual imported JSON
transition relation with unchanged Config. `actual_json_trace` chooses **only**
`json::terminal_trace`, with no invariant/correctness/optimality prefilter. Per-index
Continue induction then derives its final invariant/no-target and invokes the
imported terminal theorem. `actual_json_cost` projects the returned entry's cost,
or None for actual Empty. Cost's own chosen terminal trace is justified likewise.
`theorem_actual_dijkstra_cost_complete` derives Some(feasible minimum) versus
None(no bounded feasible walk), including admitted source==target zero. Initial
core search excludes equal endpoints; self0 is the actual separate early branch.
No persisted node-table membership premise is imposed, including ghost self.

## Transpose, arithmetic and public boundaries

The fragment is a finite stable raw coordinate graph, exact integer scalar weights
or absent scalar on an existing coordinate, nonnegative integer cap and nonnegative
H (0 unbounded). Imported effective absent/nonpositive weight is1. Existing raw
coordinate and scalar existence are distinct. Graph/type/direction selection is in
the transition. Selected tags are exactly0/1 under Out/In and <=1 under Both;
raw tag2 is rejected, not folded into a backward out arc.

`frame` explicitly requires selected forward/backward coordinates to be equal-
effective-weight transposes via reverse(tag,g,u,p,v)=(1-tag,g,v,p,u), both ways.
This is a named provider premise, not inferred from SQL rows, a graph's name or
current mode. Raw0 and absent scalar may both have effective1. Root's inherited
mirror4 gives Json20/Cost20 for ordinary mirrors, Json20/CostNone after a missing
reverse, Json20/Cost11 with reverse1 instead of10, then restored20/20. No new
ordinary-write failure or concurrency claim follows from those explicit adverse
provider states.

The theorem is over actual scalar adjacency, not minimum over all keyed rows.
Mode-dependent RowPut/Put versus PutKeyed/lowest-ekey production and competing
reweight/rebuild writers remain qualified inherited correspondence. Open
q-iter-007 still separates as-built representative projection from intended
all-parallel weighted policy; no new weighted defect or owner answer is inferred.

Exact arithmetic/order is mathematical. Native coercion, float roundoff/nonfinite
or negative caps, arbitrary collation/identifier encodings, failed/concurrent graph
changes, graph-key normalization, general producer atomicity and public raw
validation are not newly proved. No rational scaling fragment is claimed. Public
negative hops refuse while native nonpositive hops are unbounded; empty/missing
endpoints, unsupported direction/weight property and unspecified-graph enumeration
remain explicit inherited observations outside this normalized Config theorem.

Actual fallback serialization is a correspondence boundary: native DijkstraJson
returns PathJson, Cost parses `%FromJSON(...).%Get("totalCost")`, then the Python
consumer converts float. The formal fallback projects the imported mathematical
returned entry, not JSON bytes. PathJson float spelling, parser behavior and broad
error/cancellation protocols are not formal claims here. Queue ties are ordered
atoms; minimum correctness does not promise an identical native tie path.

## Actual bindings and native observations

[binding.py](binding.py) executes the pinned actual Python cost-only handler
argument producer and float/zero/no-path reader over an executing mutable Cost/
JSON source port. A separate immutable initial/step/decrease/relax/fallback
transcription compares every queue/dist/hop/Done/Best/BestHop loop-boundary state
and actual fallback carrier; independent finite simple-walk enumeration checks
minimum output. Neither deciding algorithm receives an oracle answer.

**21,168 comparisons,0 mismatches,0 socket connects** across49 graphs, cap0/3/5/20,
H0/2/3, Out/In/Both, graph/type filters, absent/negative/zero/positive scalar,
self/no-path/ghost and both hop fixtures. Nine sensitivities are classified:
three copied **actual Python method mutants** (hop producer removed, positive-cost
reader zeroed, zero reader drops self); five **source-port mutants** (no fallback,
zero BestHop, early frontsum, old queue retained, wrong backward Both scan order);
and one deliberately corrupted observation rejected against input-derived oracle.
Old queue retention may preserve returned cost but violates exact trace correspondence.
These are not nine actual native/product regression executions.

The explicit Both contrast uses s-a2,a-v2,v-u2,u-t2,u-w3,s-w3 with H3. Correct
backward in-first records Best8/Hops4 and calls JSON; wrong out-first records8/3
and skips fallback. Both return8. Full trace/carrier comparison detects the
correspondence error that a cost-only oracle misses. Equal-cost paths also show
BestHop need not be minimum hops: a too-long recorded best may conservatively
fall back even when an equally cheap fitting path exists. The actual branch is
derived by formal/source-port work, not inferred from native cost output alone.

Root's newly recorded native15 cases execute actual Cost, JSON and public cost-only
queries on20 ordinary mirrored triples, including hop fallback effects, exact cap,
tie, first-intersection and frontier-threshold fixtures. Seven product pin/export/
current identities match. The inherited native9000 pairs/14 public plus mirror4
remain separately stamped. New native15 does not instrument private BestHop or
prove compiled-body/arithmetic behavior generally. Script/json/log and all relied
product/import/helper files are in binding receipt's **flat inputs**, so freshness
checks validate them. This builder did not connect to native or mutate runtime.

## Located controls

Final eight full and isolated control runs have ordinary assertion/postcondition
failures, no timeouts and no resource-limit errors. Attribution is explicit:

| Mutation | Isolated failed claim |
|---|---|
| retain old queue entry | lemma_decrease_base |
| omit backward half of BestHop | lemma_relax_best |
| prefer more expensive best meeting | lemma_relax_best |
| stop frontsum two units early | theorem_terminal_minimum |
| require both frontiers empty before stopping | lemma_continue_has_frontiers |
| remove positive-hop fallback | theorem_finish_correct |
| project fallback returned cost as zero | theorem_actual_json_fallback_correct |
| lose admitted self0 | theorem_actual_dijkstra_cost_complete |

These are formal source-rule mutations, not execution of altered compiled native
code. Empty-frontier attribution uses a small checked primitive guard lemma;
full transition preservation remains proved separately. No control is credited
merely because some unrelated claim exhausted solver resources.

## Source roles and retained misses

| Declaration | Recommended scope |
|---|---|
| TraversalPaths.DijkstraCost | active pure transition/minimum/termination/hop-fallback fragment under stated Config+transpose premises |
| TraversalPaths.DijkstraJson and DijkstraBacktrack | imported45 rechecked, no new coverage credit; actual transition/returned-cost relation used by fallback |
| Traversal.DijkstraJson | inherited thin delegate/correspondence; no new body claim |
| engine._proc_ivg_shortestpath_weighted | observed real raw producer and final cost reader; no formal raw-to-Config/refusal mapping |
| Adjacency/AdjIndex/GraphMode/GraphKey and ordinary/keyed writers | inherited observed provider routes, no new writer/atomicity guarantee |
| CheckDirection, CheckWeightProp, PathJson and JSON parser | observation/provider only; invalid/refusal/format/parse branches outside formal normalized fragment |

The initial81-unit candidate used one shared Arc scan order for both sides. Its
mathematical arbitrary-order minimum theorem was valid, but a single order cannot
encode native Both forward out/in and backward in/out simultaneously. Source/
BestHop correspondence credit was withdrawn. Exact model/manifest/binding snapshots
and explanation are preserved in results/weighted_cost/*-unordered-scan-attempt.
The corrected primary-tag concatenation and explicit same-cost branch contrast
supersede that attempt, rather than relabel it as successful source correspondence.

Earlier receipts retain trigger inference failure; missing root/domain/sequence
obligations; rlimit attempts resolved by scoped invariant revelation and two small
checked optimal/dual extraction lemmas; first complete81 passes; and correction
runs80/1 and intermediate83, then membership/closure proof decomposition before
final88. Five added proof-engineering helpers after83 change no numerical contract. Early full-mutant empty-frontier and self-zero runs had
unrelated rlimits while their isolated named claims failed ordinarily; these are
retained separately and not described as resource-free runs. At intermediate83,
the isolated empty-frontier Continue theorem also had both an ordinary assertion
failure and a resource-limit error; control credit was withheld until the small
primitive guard extraction gave clean attribution. Final88 full and isolated
controls are all free of resource-limit errors. No solver-limit bypass,
extra assumption or removal of a difficult theorem was used. The validation ledger
records all receipts, final freshness, measured binding durations and timestamp-
resolution aggregate verifier cost. Parent owns independent review, native costs,
central role/coverage integration and sealing.
