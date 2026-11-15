# Remaining PPR workflow after the frozen draw

The [pre-body panel](next-survey-ppr-PAIRS.md) was frozen from docs, canonical
intent, test names and entry-point names. Later source inspection is explicitly
not blind evidence. PPR remains a material different workflow alongside the
cost-only weighted algorithm; neither is a convergence argument or a blocker.

The source chain is kg_PERSONALIZED_PAGERANK -> store.execute_ppr or native
PageRank.RunJson -> _ppr_every_node, with a distinct actual Python fallback.
The caller preserves store errors and non-missing native failures; signature
fallback and missing RunJson are separate routes. The recurrence reads node
membership, deduplicates valid seeds, derives forward/reverse in-edges and degree,
redistributes dangling mass to seeds, iterates until its bound or held-score
change threshold, sorts and cuts. Native RunJson is sparse; WithUnscored and
_ppr_every_node are actual final zero-fill/cut readers, not supplied answer maps.

Existing P acache_l1/l2 are substantive row-set/cache models: valid seed => graph
node rows, invalid seed => empty, node-token membership/cache concerns. Their
comments explicitly exclude numerical scores. The baseline decision crosswalk
contains no exact active PPR recurrence/zero-fill member binding. These are real
unmodeled producer/reader decisions, not code labeled trivial or a new discovery
of the already-modeled cache abstraction. Source files/members include
_engine/algorithms.py::kg_PERSONALIZED_PAGERANK, _ppr_every_node,
_kg_PERSONALIZED_PAGERANK_python_fallback; stores/iris_sql_store.py::execute_ppr;
PageRank.cls::NodeSeeds/Run/RunJson/WithUnscored and multiplicity/exclusion helpers.

Root executed [five actual native/Python pairs](next-survey-ppr-native.json) on
fresh owned named graph a->b, seed b, alpha1/2, one iteration. Both ordinary
implementations agree after the native final WithUnscored reader. No reverse or
reverse weight0 leaves b1/a0. Reverse weight1 gives a1/2,b1/2. Weight1/2 gives
a1/4,b1/2 (mass3/4); weight2 gives a1,b1/2 (mass3/2). These are source-derived
expectations and finite native observations, not a generic recurrence proof.

The reverse-weight observation is not adjudicated as a new bug: PageRank.cls31
explicitly says reverse weight scales contribution and never the divisor. Thus
a mass1 theorem needs its actual domain (ordinary forward walk or unit reverse
multiplier), rather than a silently assumed weighted-degree normalization. The
public promise of networkx/default PageRank must be kept separate from the
documented reverse enhancement. No owner decision about that extension is made.

The initial probe omitted WithUnscored while expecting a full node map; its
five-case disagreement and a subsequent duplicate-fixture setup refusal are
retained under ppr-attempts, with no credited success. The final script uses a
fresh task-owned graph per replay and retains sparse and final native payloads.
No upstream PPR suite was run in this survey. No new issue, model claim, active
binding or repair is credited by it.

Next distinguishing closure: derive valid distinct seeds, effective multigraph
transition multiplicity and exact rational iteration (restart/dangling/held
change), then feed actual sparse-score completion/top-k order. Pair actual Python
and native Owner fixtures, mutate missing dangling redistribution and duplicate
seed/multiplicity or final zero-fill rules, and preserve nonunit reverse, absent
seed, cap and provider-error neighbors. Float/native order correspondence stays
explicit. This is tractable mathematical/program work; no environmental block
or fixed time/round limit is asserted.
