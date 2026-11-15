# Exact rational weighted searches

Source pin `3eaa79cf77d3e0a879b2cced634cf2729d81499e`; iteration10 foundation
`cb02a64d9f7eb1de4571b10534b3e8262f4c3b6c`. Iteration11 began after its before
archive, SHA `67817502934f5292e110ee38f2d5cecc972be3da1ee7dc1790e1c80286d19888`.
This extends the known integer-only weighted-path gap, using the already frozen
[fraction neighbor panel](../../../uplift/consolidated/iteration-10/next-weighted-fraction-PAIRS.md)
and [plan](../../../uplift/consolidated/iteration-10/next-weighted-fraction-plan.md).
It is builder-visible work, not an independent blind discovery or a new bug.

Final baseline **181 verified units, zero errors**: **88 imported/rechecked**, plus
**65 new proof declarations (38 theorems,27 helpers),9 recursive spec termination
checks,19 nonlinear arithmetic subqueries**. These categories are different;
93 new verifier units are not93 new theorems. Imported weighted_cost88 includes
weighted_paths45 once. Both imported files remain unchanged. Inherited Verus
0.2026.10.04.426d8b0,4threads, standard resource flags; no assume/admit/external
body, extra axiom, unchecked helper or increased resource limit.

## Raw producer, common grid and actual control flow

`Scalar{num:int,den:nat}` represents an arbitrary signed rational with positive
denominator, including unreduced representations. `Config` contains finite raw
coordinate order and a separate `Map<Arc,Option<Scalar>>`: an existing coordinate
may lack its scalar. The graph/type/direction selectors read the raw coordinate.
`weight` reads the raw ratio and implements the actual absent/nonpositive rule:
effective weight1. Native numeric text coercion is not hidden in this function.

The denominator is **derived**, as the product of all raw scalar denominators
(absent contributes1) and the raw cap denominator. `omitted` proves divisibility
without assuming a supplied certificate. A positive scalar n/d encodes as
n*(D/d); absent/nonpositive encodes as **Some(D)**. It cannot be left None or set
Some(1), because the integer kernel would then apply its unscaled unit default.
The nonnegative cap encodes with its own factor. Ratio cancellation, checked
nat-to-real multiplication, positivity, zero, addition, strict/non-strict order
and injection are proved. The grid need not be the least common denominator.

Source-facing state functions operate directly on raw ratios/reals. They do not
read the encoded graph or a decoded kernel answer. JSON keeps the real ordered
(cost,node,hops) queue, real dist and raw parent `(previousKey,Arc,effectiveWeight)`.
Strict improvement **retains stale queue entries**. Seen is a node's minimum
accepted hops; bounded revisits, cap equality, early target acceptance and raw
per-arc parent costs are retained. Cost keeps both real (cost,node) queues,
dist/hop/Done and real historical Best/BestHop. A strict decrease **removes** the
old queue entry. Relaxation checks a dual meeting even when the local label did
not improve; only a strictly cheaper meeting replaces Best and its immutable
walk/hop witness. Each side's Both scan is primary-tag then secondary-tag,
including backward in-first for ordinary Both. No minimum-hop tie policy is
invented. Empty frontier precedes frontsum; equal tops choose forward.

The coupling proves minimum selection with the full lexicographic order, queue
insert/remove, initial/pop/accept, every raw relaxation, complete neighbor folds,
scan order and the complete transition for **arbitrary coupled states**, not just
one output fixture. Cost's per-label/best walks are derived ghosts and never
choose a runtime branch. Representation is proved before path feasibility and
minimum results are transferred.

Actual rational traces choose **only** the deterministic raw transition relation
from the actual initial state through an actual terminal state. Neither their
definition nor the choice predicate mentions invariant, correctness or optimum.
Existence and finite bounds are derived from the imported integer termination
proof through complete-step commutation; deterministic trace uniqueness links
the independent choice back to that execution. JSON carries the inherited finite
queue-entry bound; Cost carries the inherited <=2N pops/trace-length<=2N+1 bound.
No finite trace, runtime budget, eventual fairness or answer is assumed.

Backtracking follows the actual stored parent key and appends the raw recorded
weight. The proof-only fuel bounds a while-loop derivation; the accepted-state
parent invariant proves that fuel cannot exhaust or a missing parent break occur
before reaching src. `jread` returns those arcs/costs and the accepted real total.
Its feasible path, sum of recorded costs, hop bound and minimum are derived.
This is a structured reader contract, rather than defining result as integer/D.

`cfinish` reads the actual historical Best/BestHop and, when the positive hop bound
is exceeded, calls **the rational `janswer(c)` with unchanged raw Config**. The
actual imported JSON trace used to justify this branch is itself the unfiltered
actual transition trace. Fallback and output equality are proved after both full
transition and reader relations. Historical Best has a derived raw feasible
unbounded walk and its recorded hop length. No supplied optimum or alternate DP
algorithm decides either search.

For nonnegative cap, `theorem_actual_rational_json_complete` and
`theorem_actual_rational_cost_complete` derive Some(feasible minimum) versus
None(no bounded feasible walk). The latter requires selected equal-effective
forward/backward transposes. `theorem_raw_signed_rational_json/cost` additionally
cover **negative caps through their actual source branches**, outside Nat
coupling: distinct endpoints give a derived two-state empty trace, while self
returns zero before cap checks. Self includes a ghost node with no node-table
membership premise. The signed-cap theorems do not impose mirror assumptions on
self or negative-cap branches. Raw scalar denominators remain positive throughout;
zero denominators and malformed numeric carriers are outside the representation.

## Source roles and remaining providers

| Product declaration | Bounded role and formal relation |
|---|---|
| `TraversalPaths.DijkstraJson` (256) | active raw ratio/default and cap readers; queue/dist/seen/parent writers; `jrelax/jexpand/jstep`, complete commutation and actual JSON minimum/termination |
| `TraversalPaths.DijkstraBacktrack` (450) | active stored raw parent-cost reader; `jbacktrack/jread`, derived source reach, raw cost sequence, feasible minimum path |
| `TraversalPaths.DijkstraCost` (378) | active raw ratio/cap, decrease-key, historical Best/Hop, scan/stop, unchanged-config actual JSON fallback and final result; `cdecrease/crelax/cstep/cfinish/canswer` |
| `engine._proc_ivg_shortestpath_weighted` (1201) | observation: actual Python typed caller, graph/type/H/limit forwarding and final path/cost float readers are executed in binding; no formal arbitrary raw-to-Config or YIELD/JSON carrier theorem |
| `Traversal.DijkstraJson` (151) | thin-delegate observation/inherited role; no new forwarding tuple theorem |
| `TraversalPaths.PathJson/JsonFloat` (486/497), `%FromJSON` | observation/provider: mathematical structured path/returned cost only; arbitrary JSON byte spelling/parser/native rounding not formalized |
| `Adjacency.SetLeafFromLowest` (874), mode-dependent Put/PutKeyed/RowPut, AdjIndex and reweight/rebuild writers | inherited raw adjacency provider roles; no new writer/transaction/trigger/global projection theorem in this package |
| GraphKey, CheckWeightProp, CheckDirection and translator validators | admitted graph/type/direction/ordered-atom context; typed refusal/carrier observations, not whole-body formal claims |

The source coordinate sequence is finite and stable, with no repeated raw Arc;
Map membership exactly matches it. Cost's transpose/effective-weight equality is
an explicit provider frame, not inferred from a graph's name, SQL rows or mode.
The theorem computes the minimum over the scalar adjacency actually read. The
intended all-keyed parallel-edge policy remains unresolved in q-iter-007; rational
arithmetic does not settle it. Nonempty node/predicate identifiers are ordered
atoms; arbitrary native subscript collation and tie-path byte identity are not
proved. H is a nonnegative integer,0 unbounded. Public negative H refuses while
native nonpositive H is unbounded; actual typed neighbors retain that boundary.

Exact real/rational arithmetic is explicit. No universal native Double addition,
comparison, accumulation order, coercion, NaN/infinite behavior, under/overflow or
JSON round-trip refinement follows. Stable positive exact-grid inputs can have
native floating rounding; root's dyadic panel supplies finite corroboration only.
The provider frame also excludes concurrent/failed partial writes and does not
prove mode/trigger/cache/mirror correctness. An absent scalar on a present Arc is
modeled, but root's ordinary omitted-weight writer stores effective1: that native
case is not evidence of a children-only missing scalar leaf.

## Binding, controls and retained attempts

[binding.py](binding.py) executes the unchanged pinned actual Python handler over
[source_ports.py](source_ports.py), a mutable exact Fraction transcription of the
actual JSON/Cost source. [kernel_model.py](kernel_model.py) independently uses
immutable states for the imported integer spec, on the **derived** denominator.
Every physical loop-boundary queue/dist/seen/parent or queue/dist/hop/Done/Best/
BestHop state is compared, including actual fallback trace and raw parent weights.
Independent finite simple-walk enumeration checks output, never feeds a deciding
search.3 additional non-dyadic ideal-provider worlds and4 unreduced numerator/
denominator worlds check the same full traces without Python float cap conversion.
Negative cap is explicitly a separate signed source-branch observation, not an
imported Nat kernel claim.

Final binding: **20,522 public handler comparisons (20,520 original +2 raw-tag2 boundary),13 typed neighbors,3 exact
non-dyadic worlds,4 unreduced-carrier worlds,0 mismatches,0 socket connects**.
Public main-panel caps/weights are dyadic or unit-default examples. Eleven
sensitivities divide into **3 actual Python method mutants** (H producer, final
cost reader, final path reader), **3 source-port rule mutants** (JSON removes old,
Cost keeps old, wrong Both scan), **4 representation mutants** (default/nonpositive
unit unscaled, positive numerator unscaled, cap unscaled), and **1 deliberately
altered observation**. Representation mutants test the coupling, not actual
product behavior. No sensitivity is an altered native execution.

All13 formal controls have ordinary full and named isolated assertion/postcondition
failures, no timeout or resource-limit failure. Four mutate representation
(default, positive scaling, raw-zero default, cap factor). Nine mutate actual
source-facing algorithm/reader rules (JSON stale queue and stored parent weight;
Cost old-entry removal, BestHop, backward Both order, frontsum, actual fallback;
JSON final total and early self zero). No ghost-only controls are counted.
The manifest records each exact patch and deciding failed claim.

Root's [native22 panel](../../../uplift/consolidated/iteration-11/root-fraction-native.json)
observed actual JSON, Cost and public cost-only queries on35 ordinary mirrored
points, including omitted/zero/negative effective defaults,2.5 vs2.75, fractional
cap equality, filters/directions, H2/H3 and tie/frontier fixtures. Six exact product
pin/export/current identities and setup/helper provenance are audited read-only
and flat-stamped in the binding receipt. It does not instrument internal BestHop,
prove native bodies or justify arbitrary Double equivalence. This builder made no
native connection or runtime mutation. Existing83 selected offline pinned weighted
unit tests passed with0 sockets; their source hashes and exact invocation are
retained in iteration11/fraction-upstream.*.

All raw proof/control receipts/logs and useful source snapshots are retained in
results/weighted_fraction. Initial set-image/filter/real-cast and signed-singleton
proof failures are retained; final181 has no resource failure. Count-discovery
runs with zero errors but an outdated expected count are labeled UNEXPECTED and
not counted as final passes. The first binding run failed on a missing harness
`procedure_name`; the next retained run had2 false typed expectations because a
Variable lacked `is_parameter=True`. Both exact drafts/logs and the DISAGREES
receipt remain. Corrected binding did not modify product or formal rules. Independent review then
found that the integer Python helper admitted raw tag2 under Both even though
the formal model and source port reject it. The original20,520 valid-tag worlds
were unaffected. Exact frozen V1 helper/binding/NOTES/ledgers are retained as
`attempts/tag2-before-review.*`; the corrected helper and2 actual-handler
boundary checks now reject that shortcut. Core proof/manifest/controls are unchanged.

Independent review, costs, exact receipt freshness and canonical recommendations
are in the iteration11/fraction-* handoff/validation artifacts. No independent
held-out grade or convergence claim is available.
