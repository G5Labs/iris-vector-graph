# Independent iteration11 preparation and architecture critique

Frozen before either new candidate is read: [vector18 contrasts](review-vector-expectations.md)
and [fraction16 contrasts](review-fraction-expectations.md). Product3eaa79cf;
foundationcb02a64d; before archive hash recorded in both. These are purposive
source-informed panels using the frozen iteration10 surveys and owning docs/
production bodies, not a blind evaluator or product-wide percentage. New model
inspection/replay waits for package freeze. Only review-* files are written.

## Vector critical architecture

1. Derive raw registry classification/row arity/preference/field decode and own
   cache write from source inputs. `_registry_absent` checks numeric sqlcode==-30
   or exact message substring `SQLCODE: <-30>`; arbitrary '-30' or a supplied
   readable flag is not that function. `_is_width_mismatch` instead checks message
   `-257` or the width phrase and does not simply inspect numeric sqlcode. Keep
   these two actual classifiers distinct.
2. Derive raw query outer-array length, not a passed count or mismatch flag.
   Nested arrays/objects/escaped strings/non-numeric elements are valid JSON and
   affect outer count. Malformed text defers width, and Python NaN/Infinity and
   non-string carriers remain census inputs rather than invented refusals.
3. Route truthiness/recorded int conversion precedes raw catalog fallback. A
   parsed catalog number is source behavior, not proof of true column width:
   VARCHAR4000/digit-join examples are heuristic boundaries. Direct primary,
   optimized and client callers each resolve/check themselves. Primary dtype
   chooses route type and uppercases before width; optimized uses engine dtype.
   Do not collapse those into one universal dtype rule or ignore invalid fields.
4. Separate all scoring attempts from final results. Unknown width then generic
   primary failure / optimized-257 / mismatched client rows can yield[] after
   effects, unlike absence-before-score[]. Embedded score reader drops IDNone;
   primary/DBAPI do not. Float conversion can trigger another fallback. SQL cosine
   text alone misses ClientVectorRead/KernelAttempt; EMB substring falsely counts
   embedding_registry. Do not infer cursor-finally behavior where source lacks it.
5. Derive positive **decoded-row** cache and key/schema/graph/model/kind, strict
   elapsed>TTL, disabled lookup atTTL0, local invalidation and read counts.
   Unexpired hit with present backend error does not touch it; after expiry it
   reads/raises. tableNone may still be a decoded cached row. Miss/notrouting
   errors are not cached. Cross-engine positive-row replacement is a provider
   update, not proof of concurrent create/drop atomicity.
6. IVF is a separate admission action: argument validation/dependency imports
   precede route, missing route precedes table cursor/Build. Empty node_ids and
   no rows differ; all-None rows can fail shape later. Pydantic's unused validation
   result does not rewrite source locals. An Info parse error can follow external
   Build/AddBatch/Finalize effects and precede local registry writes. Clustering,
   native storage and transaction rollback are not implied by route admission.

Existing G identity/read_route/read_table and C vector_threshold remain real
partial hits. Stable provider-row tie order and one_row assumptions must not be
exchanged silently. Any inherited imports are rechecked, not all counted new.
Unknown valid carriers must be outside a named theorem while retained in evidence,
not silently marked impossible or returned as a fabricated Unsupported API result.

## Fraction critical architecture

The raw numerator/denominator/default and cap denominators must derive a positive
common grid. Default/nonpositive1 becomes numeratorD, never kernel default1 that
decodes1/D. Coordinate existence is separate. Preserve raw selection, exact
addition/strict order/equality, lexical minimum and queue/map identities.

Require substantive initial/relax/fold/step simulations for both source machines:
JSON keeps stale entries and node/hop/seen dominance; Cost deletes its old label,
uses actual side-specific Both scans and historical BestHop snapshot. Equal-cost
lower-hop meetings do not update Best. Parent weights and ordered backtrack, not
only totalCost, must decode from actual writes. Derive every actual rational
prefix/grid closure and termination; do not assume a finite trace or choose one
filtered by invariants/correctness. Fallback runs rational JSON on unchanged raw
Config and is related to the imported actual JSON transition. A function defined
as integer-answer/D, without raw source guards/writes, does not close the gap.

Integer imports are substantive reuse and separately counted; native serialization,
public raw coercion, Double roundoff/cap boundaries, scalar projection writers,
effective transpose provider and Q007 policy stay explicit. A dyadic observed
value does not justify rational exactness of all machine operations.

## Read-only native audit

[review-native-audit.json](review-native-audit.json) and its script/log audit the
root's frozen files without importing/executing native code. Final vector13 and
fraction22 agree with independently recomputed observations;35 actual scalar/
reverse points agree. Fraction audit uses separate exact bounded dynamic
programming and full returned-path feasibility/type/length/edge-cost checks,
rather than trusting source fixture expected fields. Numeric caps are dyadic;
no private BestHop state or arbitrary Double claim follows.

Final vector SQL counters are recomputed with the EMB word/field criterion and
metadata exclusions, not the misleading embedding_registry substring. The three
entry width/absence guards, empty vector, literal/whitespace results, sole-self
empty, distinct seed peer cosine1/sqrt2, no-route IVF and other-engine create are
supported. The root's initial self-return forecast was refuted, not a product bug;
initial substring observer overcounted three cases. Both original scripts/JSON/logs
remain. The retained attempt's old prediction hash no longer matches the updated
prediction file and no old prediction snapshot was found in the supplied set;
this is a failed-attempt provenance limit, not a failure of final13. The first
review audit strictly checking that old hash failed and is retained as
review-native-audit-attempt1.py/log. Final13/22 inputs/source/export/current hashes
all match; old script bytes match their preserved alias.

Native evidence is finite: actual ordinary route/vector writers, true SQL readers,
inspected compiled LEN4, selected dyadic/native path results. Native metadata
faults/cache TTL/outages/arbitrary parse/carrier cases are not sampled by13, and
its SQL spy does not observe client kernel/embedded effects generically. Source
guards establish their absence in sampled preflight cases. Omitted weight input
in the fraction writer produced an actual1.0 scalar; absent scalar on an existing
coordinate is not directly sampled there. Setup5 compiled deployment is reused,
not exported executable-body identity. Connections close; fresh task-owned graph
fixtures remain root-owned, and no erase/cleanup is falsely claimed.

## Ready for package freeze

After explicit freeze, independently inspect exact source/model/manifest/binding/
NOTES, copy declared inputs/imports/fixtures into separate review-vector and
review-fraction scratch roots, isolated RUN_DIRs, preserve every raw baseline,
control working tree/log/receipt and binding/upstream result. All named controls
must fail ordinary deciding post/assert obligations. Path-only adaptations require
byte-equal copied artifacts and retained failures; no product/oracle/candidate
change is permitted to manufacture agreement. New role reach must name the proved
fragment rather than full parser/catalog/cache/numerical/native member coverage.
