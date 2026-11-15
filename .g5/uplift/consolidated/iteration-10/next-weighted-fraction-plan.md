# Next numerical extension: raw rational search coupled to integer kernels

## Recommendation and present gap

Extend the proved JSON/Cost kernels through an explicit rational-state simulation.
Use raw signed rational scalars and a ghost common-denominator grid; keep the
source-shaped rational queue, distances, comparisons, additions and final reader
visible. This is substantially stronger than defining an integer answer divided
byD. It reuses the existing optimality/termination invariants without silently
claiming that every native Double operation is exact.

USER_GUIDE631 explicitly permits ordinary2.5 weights. Iteration9 weighted_paths45
and iteration10 weighted_cost88 (including those45) prove only integer arithmetic.
That is a material disclosed gap even after finite native fraction observations.
This survey adds no model or formal credit, changes no product/shared/Git/native
state, and does not select an answer to parallel-edge policy q007. Expectations
are frozen in [PAIRS](next-weighted-fraction-PAIRS.md).

## Raw carrier and derived grid

The source-facing mathematical input should contain raw coordinate presence and
an optional scalar `num/den`, with signed integer num and positive integer den.
The rational search reads that ratio, not the encoded numerator map. Its weight
is the actual rule: absent scalar or ratio<=0 gives1; otherwise use the ratio.
Keep coordinate absence separate from scalar absence on an existing coordinate.
Graph/type/direction and normalized nonnegative hop bound stay unchanged.

For nonnegative rational cap p/q, derive a ghost positive common D that is a
multiple of every raw scalar denominator and q. A finite product is enough;
LCM/gcd minimization is unnecessary for soundness. A preliminary module may
accept a checked grid certificate, but must name that premise rather than claim
all finite rational inputs until the finite-product construction is proved.
The preferred final contract derives D from the finite raw input denominator
list. D is proof representation, not a new product API argument.

Let `factor_i=D/den_i`, `C=p*(D/q)`, and derive the kernel raw scalar:

```
present positive num_i/den_i -> Some(num_i * factor_i)
present zero/negative ratio -> Some(D)
absent scalar at present coordinate -> Some(D)
absent coordinate -> absent coordinate
```

All resulting kernel scalar values are positive integers; hence its existing
effective-weight normalizer returns them unchanged. **Do not retain None or a
nonpositive kernel scalar:** its fallback integer1 would decode to1/D. Default
one must be numeratorD. This derivation is a raw normalization operation, not a
supplied transition matrix or resolved optimum.

The derived kernel cap is C and decoded cap is C/D. Including the cap denominator
avoids an extra floor-cap proof. A later real-cap extension could use
floor(D*cap), since path costs lie on the grid, but that is not needed to cover
ordinary rational caps. Negative/nonfinite caps and raw argument carriers remain
separate source/provider boundaries as in the existing packages; self0 retains
its actual early branch.

## Elementary laws and their proofs

These are mathematical derivations, not new Verus receipts. The next package
must mechanize them before claiming transfer.

Define `decode(k)=k/D`, D>0. Finite-product induction proves D>0 and each raw
denominator dividesD. Thus factor_i is integral and
`decode(num_i*factor_i)=num_i/den_i`. Sign is unchanged by a positive factor.
Default normalization gives `decode(D)=1`. Every effective numerator is>=1.

For any nonnegative integers a,b:

- `decode(0)=0` and `decode(a+b)=(a+b)/D=a/D+b/D` by distributivity.
- Multiplication by positiveD preserves and reflects `<`, `<=`, and `=`. Hence
  decoded distance improvements, cap tests, minimum-cost ties and frontsum tests
  are exactly the integer tests. Injectivity also preserves queue-set identity.
- Induction over a path gives `sum(raw_effective_weights)=kernel_sum/D`, using
  the weight law at each arc and the addition law. Hop length and edge identity
  are unchanged. A kernel minimum therefore decodes to a rational minimum over
  the same selected walks, once the actual transition/reader simulation is shown.

No law follows merely from weights being finite floats. Those laws are exact
rational semantics; a native arithmetic contract must separately justify them
for the reachable values of a sampled/admitted machine fragment.

## Substantive state/step simulation

Use a source-facing rational state with actual ratio/real costs in PQ/dist/Best
and stored parent weights; it executes the raw source arithmetic and comparisons.
Define `decode_state` from the imported integer state by decoding every numeric
cost field. Node/hop keys, seen minima, Done node sets and arc sequences are
unchanged. Ghost Done-cost/removed histories decode too when used for transfer.
The rational machine must not simply call the integer answer function.

Required checked relations, in proof order:

1. Raw selection/domain/neighbor sequence preservation. Encoding changes numeric
   scalars only. JSON retains its out/in scan order; Cost retains its side-specific
   primary tag followed by secondary under Both. Effective reverse transpose
   transfers by positive-D injectivity; None and raw1 can be effective mirrors
   despite different raw carriers.
2. Finite set/map image laws: decoded queue insert/remove/empty and dist lookup/
   update commute with decoding. Equal numerators correspond exactly to equal
   rational costs, so no queue key is accidentally merged or split. Lexicographic
   minima commute because cost order and node/hop tie order both commute.
3. Initial state and **each raw relaxation** commute. Show the rational guard
   `current+raw_effective<=cap` and strict improvement agree with encoded tests;
   then show actual queue/dist/parent writes agree. Do not establish only final
   cost equality. JSON keeps its old higher-cost queue entries; Cost deletes its
   exact old entry. Seen-hop checks and next-hop0/unbounded behavior are unchanged.
4. Finite neighbor-fold and complete step/event commutation follow by induction.
   Accepted/source/target and cap/hop stop branches agree. Cost's meeting sum,
   strictly improving Best and **historical** BestHop/walk snapshot commute;
   equal-cost lower-hop alternatives must still be ignored as source does.
5. JSON backtrack commutes with the actual source-stop/missing-parent behavior.
   A rational parent record stores the raw effective weight read at relaxation;
   relate it to the kernel parent arc's decoded weight under the stable graph.
   Parent domains/keys agree, so chain membership/order and stop location agree.
   Existing kernel parent correctness rules out a premature missing break. Decode
   each recorded cost as well as totalCost, then use path-sum induction. Native
   JSON float spelling/%FromJSON and Python float conversion remain providers.
6. Cost's fitting-hop branch decodes its historical feasible witness. Its fallback
   must invoke the rational JSON transition on the **same raw rational graph,
   cap, H, direction and predicates**; prove that call corresponds to imported
   JSON on the encoded config. Do not substitute a supplied bounded optimum or
   choose a trace filtered by correctness. Terminal-trace choice contains only
   the actual rational transition relation, with invariants derived afterwards.
7. Import the existing kernel terminal-trace/optimality/absence/termination
   theorems and transport them through the above relations. Initial plus step
   simulation derives reachable grid closure; it is not an assumed terminating
   trace. Determinism or reverse simulation shows every actual rational prefix
   follows the decoded kernel prefix. Kernel finite termination then gives actual
   rational termination, and decoded feasible-walk comparison gives minimum/None.

This keeps algorithmic work faithful while avoiding a second proof of the costly
JSON dominance/frontier and Cost crossing argument. Import weighted_cost once and
reuse its nested json module, so imported88 units are rechecked once, separately
from new representation/simulation obligations. Pin both source bytes in manifest
additional_inputs. Do not modify the old kernels merely to reduce a new count.

A lean numerator-backed rational state is a possible implementation optimization
only if it still defines source arithmetic/guards by raw ratio semantics and
proves those commute. Defining its step as the imported integer step and dividing
the answer would leave the intended source relation missing; no credit should be
assigned to that shortcut.

## Altered rules and exact neighboring outcomes

The source-only probe checks complete queue/dist/seen/parent/Best/BestHop/fallback
traces, not just costs. Its eight alterations detect default numerator1, nonpositive
numerator1, scaling a positive numerator twice, an unscaled cap, missing output
decode, JSON deleting stale entries, Cost retaining old entries and wrong backward
Both scan order. In the latter cases a returned cost may remain equal while the
source-state or fallback trace differs. These are preparation sensitivities,
not formal controls or native regressions.

[Thirteen golden neighbors](next-weighted-fraction-neighbors.json) include:

- default/zero/negative direct weight1 versus quarter+half route: minimum3/4;
- stored2.5 exact cap2.5 gives2.5; cap2 gives no path;
- half+three-quarters exact cap5/4 versus cap1;
- scaled A1: H2 gives5/2 by actual fallback, H3 gives3/2 without fallback;
- mixed half/third/quarter inputs represented on D12; raw-different effective
  mirrors; absent coordinate; and exact one-third with cap1/3.

The finite probe has33,696 paired exact trace comparisons,62 fallback executions,
1,350 addition/order checks, zero mismatches and all eight sensitivities detected
in1.91s with zero sockets. It uses the same source control skeleton under two
numeric interpretations and supplies neither an optimum nor a result to a
deciding search. It is scaling sanity, not an independent algorithm proof.

## Alternative: direct real-state proof and cost to settle

A direct real-weight rewrite is mathematically tractable but broader. Cost still
terminates by fresh(side,node) Done, at most2N; its optimum argument uses positive
weights/order/addition rather than integrality. JSON's old cost+1 backtrack fuel
and finite integer cost-universe rank cannot simply be reused for arbitrary reals.
One can instead retain predecessor acceptance indices for backtracking and use
lexicographic termination `(remaining acceptances, queue size)`: an accepted node
must lower its seen-hop minimum (at mostH+1 accepted states per node, or one
unbounded state), while a dominated stale pop reduces queue size. Expansions may
increase queue size only when the first component decreases. Finite neighbor
folds preserve the argument. This is a new termination/parent proof, not a hard
block, but would require reworking more of the existing45-unit JSON kernel.

The grid simulation is the smaller next experiment for ordinary rational weights.
Expected new work is denominator/divisibility arithmetic, decoded map/set/minimum
relations, two relax/step/fold simulations, parent/output and fallback composition.
Its solver cost is unmeasured: no new Verus model was run here, and no fixed time
or round budget is implied. The raw fractional source ports are cheap; difficult
quantifier/image proofs should be decomposed rather than weakening contracts.

Remaining expensive boundary is actual native numeric/provider refinement:
coercion, decimal/binary accumulation and comparisons near the cap, JSON roundtrip,
canonical cost subscripts, collation and concurrent producer states. Exact-grid
mathematics alone does not settle it. q007's scalar projection policy also stays
open. No convergence claim follows from either extension route.

## Minimal future root-native panel (not run)

After the next before archive, root can create fresh ordinary mirrored single-edge
fixtures and call both actual JSON and Cost plus the public cost-only reader.
Observe out/in scalar points, inputs and output types. Use dyadic values above
for2.5/1.25/default1/cap/H/None/zero/negative/Both neighbors so known exact arithmetic
is plausible and directly checked, not assumed from a graph name. Prefer distinct
triples to avoid coupling q007 into the numerical test.
Check ordinary writer admission for zero/negative values and retain any refusal;
the panel must not bypass that writer merely to force a desired fixture.

Add a separately labeled numeric-provider challenge with0.1+0.2 versus cap0.3,
and a near-boundary perturbation. Record actual scalar coercion/addition/cap
outcomes; do not preclassify a mismatch as an algorithm defect or pretend the
Double provider is rationally exact. Raw one-third is mathematical preparation,
not a promised native exact value. No native call or fixture is performed by
this survey.
