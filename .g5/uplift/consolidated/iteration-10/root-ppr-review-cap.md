# Independent PPR producer-cap / fabricated-zero review

The four retained native cases support a second, distinct PPR defect: a requested
positive top_k above the native sparse producer's1000-row cap can cause the final
reader to invent zero scores for valid scored nodes. This is stronger than row
omission and independent of the tiny-positive tie policy. I recommend retaining
one new finding for limit propagation plus completeness inference. I did not open
or edit an issue/model, call native, or change shared files.

## Intended neighbor and actual source chain

USER_GUIDE593 and the public method's return contract distinguish explicit
`return_top_k` from the native route's default1000 cap **without** a requested
limit. Every route promises the same PPR answer; only nodes the walk never
reaches have0. A caller requesting1002 on a1002-node graph whose every node is a
valid seed is inside the documented argument domain. With all nodes dangling,
alpha1/2 and one iteration, each score is exactly1/1002 mathematically. Float
rounding cannot explain a literal zero replacing this positive value.

The public wrapper `_engine/algorithms.py291-301` puts `limit=return_top_k or0`
into `graph_kw` only when exclusions are explicitly supplied. With `exclude=None`
it calls store.execute_ppr without the requested limit. The store's
`_execute_ppr2295-2304` uses RunJson's1000 default if no limit is supplied; a
custom tolerance still sends pLimit1000 explicitly. Root used tolerance0, so this
is not restricted to an omitted/default tolerance. The class fast path's
`_runjson_tail134-146` has the analogous default1000 choice with exclude=None.

RunJson sorts then cuts sparse scored rows at pLimit. The final
`_ppr_every_node393-424` nevertheless uses the caller's larger positive top_k;
because1000 scored rows do not fill1002, it reads node IDs absent from the
truncated map and appends them with score0. The reader has no completeness flag
or continuation and confuses "not returned because producer truncated" with
"never scored". Explicit `exclude=[]` sends limit1002 to the producer and avoids
this loss. A limit1000 fits the sparse cap and returns1000 positive rows legally.
The actual full Python fallback computes all1002 ranks before its cut.

## Native evidence and scope

| Same1002 persisted isolated seeds | Rows | Positive | False zeros |
| --- | --- | --- | --- |
| Public store, exclusionsNone, requested1002 | 1002 | 1000 | cap10:1000,cap10:1001 |
| Public store, exclusions[], requested1002 | 1002 | 1002 | none |
| Public store, exclusionsNone, requested1000 | 1000 | 1000 | none |
| Actual Python fallback, requested1002 | 1002 | 1002 | none |

All positive scores observed are approximately0.000998003992015968. The first
answer's mass is approximately0.998004 because two scored nodes were assigned0;
the full[]/fallback answers sum approximately1. A legitimate1000-row cut also
sums below1 and is **not** itself an error or an obligation to renormalize. The
defect is claiming1002 scores while replacing two existing positive values.

I inspected [source-frozen predictions](root-ppr-cap-predictions.md), the
[native script](root-ppr-cap-native.py) and [four-case receipt](root-ppr-cap-native.json).
The script uses ordinary successful bulk node creation with indexes enabled;
the returned1002 IDs, complete[] answer and fallback answer corroborate the valid
node/seed fixture. It calls the actual private fallback implementation over the
same real DB, rather than forcing public unavailable-provider dispatch. The
counterexample is actual public normal/store behavior; its class-fast-path
analogue is source-only here. No generic float, compiled-body, unlimited graph or
Arno proof is inferred. No runtime call was performed for this review.

[Freshness audit](root-ppr-review-cap-audit.json) confirms all three original
script/prediction/helper stamps and four current source hashes match. Root's
later [exact source provenance](root-ppr-cap-provenance.json) records the four
pin/export/current blob identities, stamps the unchanged four-case script/JSON/
raw log and explicitly reuses setup5 deployment. It adds no new run or compiled
binary/body export. Root subsequently integrated this as bug-plt-104 (Medium),
separate from bug-plt-103 (Low) and ordering-policy q-iter-008; this review is the
independent evidence/disposition recommendation, not that register mutation.

## Dedup and recommendation

Inherited F-1003 is global `PageRankGlobalJson`'s10000-row omission, not personalized
RunJson1000 truncation followed by false zero completion. Its ordinary method,
threshold, deciding producer and final effect differ. F-1004/bug-plt-017 concerns
node-only cache invalidation after a missing seed is created; this fixture's
valid seeds already exist for its first computed answer. The tiny-positive
finding instead has matching true scores and differing final tie/cut order on
three nodes. No matching fabricated-zero/limit-propagation root was found in the
current register. Preserve all those inherited roots without recounting them.

Recommended wording: "When PPR's public caller requests more than1000 rows with
no explicit exclusion list, its requested limit is omitted from the sparse
producer call. The final every-node reader fills to the larger caller limit and
assigns0 to omitted positive-score nodes. With1002 valid isolated seeds, request1002
returns1000 positive scores and two false zeros; explicit[] or the Python fallback
returns all1002 positive scores." Intended repair selection and severity belong
to root; this review does not prescribe code changes or claim they were made.

The eventual formal package must retain producer limit/completeness and actual
reader input, not accept a preclassified "unscored" set. General recurrence mass
preservation alone does not prove that returned rows preserve the computed score.
