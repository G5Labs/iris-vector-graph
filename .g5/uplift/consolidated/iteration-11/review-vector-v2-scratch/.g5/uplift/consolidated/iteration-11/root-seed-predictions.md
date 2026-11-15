# Seed exclusion across primary scoring fallback: before native execution

Existing canonical search.knn explicitly leaves a seed node out of its answer.
Source kg_KNN_VEC expands a seed's selected-table vector and sets exclude_id, so
successful primary SQL excludes it. Its generic-error handler forwards only the
expanded literal to _kg_KNN_VEC_python_optimized; that entry resets exclude_id.

On the already-created task-owned root vector13 graph, seed unit vector and distinct
peer cosine1/sqrt2, predict primary seed k1/k2 returns peer only. An in-process
DBAPI wrapper that injects one generic first-score exception at request start
should make the actual fallback read the same native rows but return seed at1,
and seed+peer at2. The same literal-input generic-fault neighbor may lawfully return
the seed: it was never a seed-ID request. This fault adapter supplies no rows,
widths, selected tables or final answers; all successful scoring remains native.

Use only the identity-guarded owned runtime and frozen root-vector-native.json
fixture identifiers; no global erase, data/metadata modification or native outage.
This is a controlled provider-fault composition, not an organic availability event,
native implementation proof, new policy or product repair. Any new finding waits
for independent intent/dedup/source review. Preserve all failed attempts unchanged.
