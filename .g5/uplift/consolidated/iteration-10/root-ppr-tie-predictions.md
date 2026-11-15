# PPR tiny-positive and zero before native observation

Product3eaa79cf, foundatione56c8592. The iteration9 pre-body PPR panel already
scheduled12-decimal ties/final zero-fill. This refinement is source-derived,
not blind grading. No native tiny-positive observation has run yet.

One ordinary edge s:seed -> t:tiny, one disconnected0:zero, alpha1e-13,
one iteration/tolerance0: score seed=1-alpha,tiny=alpha,zero=0. The unchanged
rank_key rounds tiny/zero to the same12-decimal key, then IDs put0:zero first.
Python fallback sorts the full node map, predicting seed,zero,tiny. RunJson sorts
the scored subset and WithUnscored appends zeros; the public native/store path
also short-circuits when scored rows already fill top_k. Source predicts seed,
tiny,zero and a different second node at top_k2.

Keep passing neighbors: alpha1e-11 (outside the zero tie), top_k1, and a zero ID
z:zero that collates after t:tiny. Current docs have tension: USER_GUIDE550 says
all ranked answers use12-decimal ties, while593 says zero nodes come after the
others; the class header/method implements the latter, and the Python full
fallback appears to implement the former. A differing selected set is observable
regardless of which policy eventually wins. Do not silently decide the policy
or register a bug before actual route/evidence and existing-root review.

Probe only on the task-owned hostname-guarded native instance, fresh named
fixtures, ordinary graph writes/query methods, no Arno/network/security scenario.
