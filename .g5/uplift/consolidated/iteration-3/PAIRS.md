# Iteration 3 builder sample

Frozen before tracing the selected implementations, from checkpoint 0af2a61d.
These are builder questions, never independent holdout results. Judgmental selection:
one known consequential history gap and four scarcely examined ordinary correctness
areas, using product tests and the public feedback. No repository-wide estimate.

| ID | Actor, reachable neighbors and reader observation | Initial canonical / formal prediction | Selection source |
|---|---|---|---|
| I3-DIFF | Ledger caller: equal named endpoints versus forward then reverse range; empty versus fieldwise inverse, retaining original priors through delete/recreate | Canonical promises net/inverse; formal absent for diff. Existing bug-led-101 may contradict semantic inversion | integration/test_ledger_us07_diff.py; public M05 |
| I3-PR | PageRank caller: unchanged node COUNT:MAX versus changed token after adding an isolated node; cache hit without census versus recompute with census and normalized scores | Canonical says fresh and complete but omits COUNT:MAX/lazy decision; reviewed cache formal has an abstract token, no producer or normalized rows | unit/test_460_r313_pagerank_loners_lazy.py |
| I3-AQL | AQL caller: equality versus inequality against null, and integer depth 1..2 versus decimal depth; translated null test and typed hop bounds versus refusal | No detailed canonical AQL owner; no active as-built formal contract | unit/test_aql_translator_extra.py; unit/test_aql_parser.py |
| I3-VEC | Vector caller: omitted threshold versus 0.5 with a 0.25 cosine result; row retained versus excluded, equality admitted | Canonical top-k lacks threshold; no active formal threshold selector/consumer | unit/test_vector_score_threshold.py; integration/test_vector_score_threshold_live.py |
| I3-BULK | Bulk writer: same node ID/labels/properties in default versus explicit named graph; downstream reads must observe the chosen graph's labels/properties | Generic scope commitment, no complete bulk producer/reader proof | public H2-02 lead; nodes_edges.bulk_create_nodes |

Outcomes, challenges, source authority, inherited-finding comparison and deferrals
will be appended without replacing these initial predictions. I3-AQL and I3-PR are
independent discovery selections even where they overlap published leads; exposure
means neither is credited as a fresh independent case.

## Observed outcomes and selection after the first batch

| ID | Deciding observation and actual scope | Producer / consumer / assumption challenge | Inherited comparison |
|---|---|---|---|
| I3-DIFF | Equal named endpoints return []; reverse swaps fields. 9481 actual named pairs, 8113 continuous-life endpoint comparisons agree. Generic continuous-life endpoint relation and raw snapshot witnesses prove; complete graph/lifecycle relation remains open | The original empty deletion prior was not produced by DeleteNodeRows. Actual NodeSnapshotJson supplies labels/props, so a simple delete/recreate preserves k=1 in inverse existence.after. A stronger admitted history initial1 -> set2 -> delete(snapshot2) -> recreate -> set3 instead loses range prior1. Snapshot policy and tie application order stay at ledger.readers.diff.order | Repaired known M05 selector/inverse gap; withdraw old simple missing-value inference in bug-led-101, retain corrected range-prior evidence under the same ID. Not a new defect |
| I3-PR | Same COUNT:MAX plus adjacency/params hits with no loner census; adding an isolate moves the key and returns the recomputed score rows including it. Failed token reads loners before each call; empty census is known0:0 | Real _node_set_token query reaches real engine/store/hash/cache consumer. Constant node-key mutant is detected. Formal token derives from count/max and insertion; DB snapshot and ID nonreuse are premises. Fixture score rows sum1; actual numerical normalization is not proved or observed | Distinct from PPR F-1004/bug-plt-017. Global admission now modeled as built, not the inherited reviewed nver repair. F-1003 cap still contradicts complete output |
| I3-AQL | 1..2 produces integer bounds1,2 and *1..2; decimal depths refuse. Literal null equality/inequality becomes IS NULL/IS NOT NULL, string-null remains a value. 100 real frontend/adapter journeys agree | A lexer mutant treating '..' as decimal is rejected; typed range and null consumer mutants fail proofs. Native adapter hands exact text/bindings to a recorder; Cypher query execution remains absent | Public exposed typed/null leads gain a scoped frontend contract. RC-16 gains evidence, no general translator proof or new bug |
| I3-VEC | Omitted threshold returns all eligible cosine rows; .5 excludes .25, includes equality. 32 result cases check actual SQL builders/readers with adapted SQLite; six obligations, three named controls | Changed WHERE comparison loses an equality row and is detected. Provider executes real cosine on three vectors; TOP and TO_VECTOR syntax are adapted. IRIS dialect/preparation, float nonfinites and graph isolation are not established | Historical threshold syntax fix (test_vector_score_threshold.py) is a benign control lead, not a current defect. This helper is separate from other KNN/fusion surfaces |
| I3-BULK | Inspected current bulk_create_nodes: absent graph inherits call graph; explicit child graph selects its node/label/property tuples. SQL labels/props carry the same node_graph, and existing props are guarded/merged. Default-only batches may take BulkIngestNodesSQL | Read actual producer (nodes_edges:1648-1878), SQL templates and _check_nodes_written consumer; no server observation or new Verus bulk-label/property contract. Existing writer_id_reader covers ID projection only | Deferred sampled decision. Do not promote existing ID-only or global scope proofs into per-graph label/property equivalence. No case score change predicted |

The first batch selected DIFF, PR and AQL; VEC was the additional underserved-area
review after those proofs. The sample retains BULK as deferred rather than deleting
it from the denominator. Selection is judgmental and exposed to public feedback;
none of these observations is independent holdout grading.

## Independent additional decision during producer review: I3-PR2

Raw loners contain has_self_loop. Holding the caller's cache-miss state fixed,
{id:false} becomes a nonempty edgeless argument and forces the Owner; {id:true}
becomes an empty edgeless argument and permits a Native Reader eligibility probe.
The same node is in adjacency in the latter case. This distinction was selected
from _edgeless.py, beyond the original COUNT:MAX question, before adding its proof.
Both raw-bit neighbors now have a theorem, an inverted-bit control and real
engine/store observations. Native availability/proof-record gating still decides
whether that candidate is used; no unconditional Native execution is claimed.
This is an additional checked decision, not a new finding; the inherited R306
edgeless behavior and algorithms.routing already explain its motivation.

## Stopping boundary and remaining work

The final batch has deciding controls in both layers and the producer challenges
above. More links or scalar fields would not close the remaining full lifecycle
and snapshot-to-reader claims. Those require a full content/transaction model and
an isolated IRIS correspondence campaign; the unresolved diff application policy
also needs the named maintainer. BULK remains a concrete next modeling slice,
with server/SQL transaction and child-value equivalence explicitly unproved.
No numerical, all-graph, snapshot-consistency or hidden-case result is inferred.
