# Independent tiny-positive / zero PPR review

## Verdict

The retained six-case native evidence supports a real **route-dependent top-k
membership difference**, separately from the unresolved choice of zero/tie
ordering policy. It does not establish a recurrence, mass or convergence error.
No matching inherited issue root was found in the current bugs/questions register.
Root should retain one new route-consistency finding, with the preferred ordering
policy separately explicit rather than silently choosing which route is correct.
This review opens or edits no issue, model or canonical owner.

This is source-first builder-visible discovery from the iteration9 frozen PPR
panel and iteration10 root predictions, not a held-out result. Cost proof review
remains the priority; this secondary read uses no native/runtime/network calls.

## Authority and unresolved policy

USER_GUIDE550 and `algorithms.op` say ranked answers treat scores equal
at12 decimal places as ties and break ties by IRIS node ID. CHANGELOG R306 states
that rule for ranked answers everywhere. The typed `_collation.rank_key` directly
implements it as `(-round(float(score),12),collation_key(id))`.

USER_GUIDE593's more specific PPR prose says unreached zero nodes occur after the
others, within the cut. `PageRank.WithUnscored118-151` and `_ppr_every_node393-424`
explicitly append missing zeros after ranked scored rows. One could read that as
a specialized exception to the general tie rule, but no explicit exception
settles a positive value rounding to zero; the two rules give opposite second
nodes in this fixture. Source behavior alone cannot choose human intent.

The independent commitment survives this ambiguity: USER_GUIDE592,
API_REFERENCE1678 and the public Python method docstring promise the same PPR
answer on every route. Once `top_k` selects different node sets, this is more
than harmless insertion-order variation in a dict or permissible float noise.
The scores themselves agree; only final ordering/cutting differs here.

## Deciding writers and final readers

One iteration, alpha1e-13, source seed `s:seed` with an edge to `t:tiny`, and an
isolated `0:zero` produces seed=1-alpha,tiny=alpha,zero=0. No negative score,
parallel-edge, reverse, cache-staleness or approximate convergence premise is
needed. Alpha is valid in the documented open(0,1) domain.

Native `PageRank.RunJson33-71` ranks the sparse stored walk map by normalized
12-place score/ID and cuts it. `WithUnscored` then appends missing nodes and stops
at the limit. Public `execute_ppr` supplies sparse rows; the engine's
`_ppr_every_node` sorts those rows and returns immediately if they already fill
the positive limit, otherwise appending missing zeros. Both therefore keep
`t:tiny` ahead of `0:zero`.

The real Python `_kg_PERSONALIZED_PAGERANK_python_fallback` builds the full node
rank map, including zeros, sorts **all** items by the same rank_key at566, and
then cuts. Tiny1e-13 and0 share the rounded zero key; `0:zero` collates before
`t:tiny`, so the fallback retains the unreachable node at top2. The deciding
difference is sparse-sort/cut-then-zero-append versus full-sort-then-cut, not the
arithmetic recurrence or ID comparator.

Root's script directly calls the actual fallback implementation over the same
real database, alongside actual public normal/store and ObjectScript readers.
It does not force public capability/class-missing dispatch into fallback in this
native probe. Source shows that dispatch and the builder can exercise it with an
in-process adapter; do not rename this receipt a full native public-fallback
dispatch test. Arno, SQL CALL projection, arbitrary codecs, Unicode IDs and
unbounded floating equivalence are unassessed by these six cases.

## Evidence and neighbors

| Fixture | Native / public store | Actual Python fallback |
| --- | --- | --- |
| alpha1e-13, early zero, full | seed,tiny,zero | seed,zero,tiny |
| alpha1e-13, early zero, top2 | seed,tiny | seed,zero |
| alpha1e-13, early zero, top1 | seed | seed |
| alpha1e-11, early zero, full | seed,tiny,zero | same |
| alpha1e-11, early zero, top2 | seed,tiny | same |
| alpha1e-13, late `z:zero`, top2 | seed,tiny | same |

I inspected the root script and JSON without rerunning native. All three stamped
script/helper/prediction inputs are fresh; all four product source hashes equal
the current checkout and the receipt's pin-export stamps. The helper owns native
hostname/connection provenance. This review does not independently reexport
compiled classes or claim universal decimal-rounding correspondence. The two
contrasts and four agreeing neighbors match the retained pre-observation source
predictions. `AGREES_SOURCE_PREDICTION` is not agreement between routes.

Root's subsequent [provenance audit](root-ppr-tie-provenance.json) adds exact
pin/export/current blob equality for the four sources and hashes the unchanged
six-case script/receipt/raw log/predictions/helper plus setup5 deployment evidence.
It explicitly reuses setup5's successful PageRank deployment rather than claiming
a fresh compiled export. This strengthens source identity without counting any
new native observation or changing the dispatch qualification above.

Dedup check covered current `bugs_issues.md`, `open_questions.md`, PPR canonical
owners and R270/R306 changelog context. F-1004/bug-plt-017 concern node-only cache
invalidation after a missing seed is created; these fixtures use fresh named
graphs with existing valid seeds and disagree on their first computed route
answer. F-1003/global-owner10000 cap is also a different route/root and size.
No inherited tiny-positive/zero final-sort/cut issue was found. Keep those prior
findings and the refuted node-deletion premise intact.

Recommended finding wording: "At the pin, PPR's normal/native route and Python
fallback can return different top-k nodes when a positive score ties with zero
at12 decimal places. Sparse native/store readers append zeros after the scored
cut; the Python fallback ranks zeros with the full map before cutting. The
intended ordering of a rounded-zero positive score is unresolved, but all routes
must apply one policy consistently." Severity and final adjudication remain root
work; no product repair or new native run is requested by this review.

Evidence: [root predictions](root-ppr-tie-predictions.md),
[native source](root-ppr-tie-native.py), [native receipt](root-ppr-tie-native.json),
[frozen PPR panel](../iteration-9/next-survey-ppr-PAIRS.md),
[user guide](../../../../docs/USER_GUIDE.md#L550),
[actual sparse readers](../../../../iris_src/src/Graph/KG/PageRank.cls#L33),
[actual engine/fallback](../../../../iris_vector_graph/_engine/algorithms.py#L393),
[typed comparator](../../../../iris_vector_graph/_collation.py#L37).
