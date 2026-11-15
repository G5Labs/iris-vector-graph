# Independent seed-exclusion intent, dedup and source review

Existing intent is explicit, so no new policy question is needed to decide what
a node-ID call promises: [API_REFERENCE971](../../../../docs/API_REFERENCE.md#L971),
[USER_GUIDE926-931](../../../../docs/USER_GUIDE.md#L926), and
[search.knn](../../../ontology/features/search.g5.md#search.knn) say that the node
whose stored vector is used is left out of the answer. `vec_expand` on a named
VecIndex explicitly does not exclude its seed (API_REFERENCE1192); that separate
surface does not supply a conflicting answer for `kg_KNN_VEC`.

Production vector.py535-625 establishes the deciding/writing/reader chain:
`exclude_id` is derived from the original seed string, selected-table/same-graph
lookup expands `query_vector` into a literal, and primary SQL excludes that ID.
On generic primary score failure, the except branch passes the reassigned literal
to `_kg_KNN_VEC_python_optimized` without the identity. Optimized literal SQL has
no `node_id !=` predicate; its embedded/DBAPI float readers can return self. Graph
and table remain correct; this is identity loss across a fallback, not cross-graph
widening, query-width refusal, wrong numeric cosine or all cosine1 hits being bad.

[review-seed-probe.json](review-seed-probe.json) independently executes six actual
public-source cases over named local semantic SQL providers. Those providers
derive cosine/graph/exclusion from raw seed/peer/other-graph vectors and actual
SQL/args, supplying no wanted output rows. Primary seed k1/k2 returns only peer;
a single generic first-score exception after seed lookup sends the literal to
actual optimized embedded reader and returns self at k1 /self+peer at k2. A second
embedded-unavailable variation reaches the actual optimized DBAPI reader and has
the same loss. Literal query with the same fault returns self lawfully. Expected
source results and the intended raw-request exclusion oracle are distinct;
identity is checked against the original request, not merely changed!=baseline.
No product method body is altered. All six agree with the inspected source,
with0sockets/0native calls and~0.019s measured probe body. No candidate inspected.

Existing current bug, question and simplification registers were searched for
`seed`, `exclude_id`, `query node`, `self-neighbor`, and exclusion/left-out phrases
on vector/KNN surfaces, including section-level normalized text. No matching
seed-to-literal fallback identity-loss root was located. Nearby F-C0602 is SQL
multi-label duplication, F-C0603 is registry-row preference; neither has this
trigger/decider/final-reader consequence. This is bounded duplicate review of
those current registers, not proof against every historic discussion/private
artifact. No private evaluator path was inspected or opened.

Root's frozen [root-seed-native.json](root-seed-native.json) independently samples
the actual primary/fallback/native cosine on the unchanged ordinary root13
seed/peer route. Exactly one first primary score exception is injected by an
in-process DBAPI adapter which supplies no rows. Five cases reproduce primary
peer-only k1/k2, faulted seed self-first k1/k2, and legal faulted literal self.
This is a controlled provider-failure observation, **not an organic outage or
native-class failure reproduction**. It does not establish all recovery paths,
numeric/binder behavior, or whole native/Python body correctness.

Recommendation for root adjudication: this supports a distinct provider-conditioned
seed-exclusion finding under the existing `search.knn` intent, with Low severity
appropriate to the bounded evidence. No issue/register/owner edit is made by this
reviewer. Preserve both passing neighbors and exact fault condition; do not write
that every normal seeded query returns self or that the fallback crosses graphs.
The moving vector candidate must preserve this as built rather than quietly
propagate an identity that product code actually drops.

The root's earlier native13 seed-self expectation miss and EMB-substring observer
miss remain retained, not product bugs. Root has now recovered the exact old
prediction bytes as root-vector-attempt1-predictions.md with archival provenance;
the prior frozen review-native-audit's initial mismatch stays historical rather
than edited. The follow-up seed audit verifies that archival alias and original
native13 bytes independently; no unrecoverable old-input claim remains.
