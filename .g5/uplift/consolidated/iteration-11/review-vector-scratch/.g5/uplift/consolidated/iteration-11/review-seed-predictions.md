# Seed identity handoff: source-informed expectations before probe/candidate

Product3eaa79cf; foundationcb02a64d. No new candidate inspected. This is a
builder-reported source boundary independently inspected, not a blind draw.
Root's newly reported native5 outcomes are known; this probe independently runs
the actual Python source over named local providers, no native/outage claim.

Intent is already explicit: API_REFERENCE971, USER_GUIDE926-931 and canonical
search.knn say the node-ID query uses its stored vector and leaves that node out.
VecIndex `vec_expand`1192 deliberately does not exclude its seed and is a different
surface. No new policy assumption/approval or issue creation is needed here.

Actual primary assigns exclude_id from the incoming ID, reads its same-graph
stored vector, reassigns query_vector to a bracket literal, and uses != in primary
SQL. Generic exception calls optimized with that reassigned literal but without
exclude_id. Optimized treats a literal as a vector and its SQL lacks the identity
predicate. A provider fault may therefore change neighbors although graph/table/
vector are unchanged.

Raw graph g has seed=[1,0,0,0], peer=[.5,.5,0,0], plus a differently scoped trap.
For k1/2:

- seed primary success: peer only at1/sqrt2; self exclusion remains reachable;
- generic first primary-score fault after seed read -> actual optimized embedded
  reader: seed1 ranks ahead of peer, k1 displaces peer and k2 includes self;
- embedded unavailable additionally -> actual optimized DBAPI reader: same loss;
- literal [1,0,0,0], including same generic fault: self is a legal hit because no
  identity was requested to exclude. Do not call all cosine1 hits a violation.

The local SQL providers must derive cosine and rows from raw vectors plus actual
SQL graph/exclusion predicates, not supply a wanted result. Fault is installed
at request start and raised at first primary score only; capability construction
must not consume it. Record original request, stored literal, every statement/
argument, row type and final reader. Do not patch kg_KNN_VEC/optimized behavior.
