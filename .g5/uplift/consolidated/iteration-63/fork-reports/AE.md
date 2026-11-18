# AE report — architecture/algorithm-execution (13) and operations/status-and-repair (13)

Saved by the builder from the fork's final message. Fragment: 26 blocks complete, 137 obligations, 26 exclusions,
owner-updates `graph.default#x03 → install.status#o01`; merged check PASS.

## 1. Per block (f/p/a, excl, note)
algorithms.owner 0/0/2 (0; #o01 contradicted by source: random_walk has no Owner); algorithms.routing (parent) 0/0/7 (4);
routing.revision 0/0/3; routing.fallback 0/0/3; routing.reload 0/0/1 (bug-plt-010 suspected); routing.excluded 0/0/1 (1);
algorithms.proof (parent) 0/0/3 (4); proof.gate 0/0/4; algorithms.cache (parent) 1/2/1 (#o03 refuted, bug-str-002,
F-1004); cache.token 2/0/2 (3; #o01 refuted for PPR, F-1004, bug-plt-017); cache.pagerank 6/0/0 (2; pagerank_admission);
cache.erasure 0/0/1; cache.concurrency 0/1/1 (1); access.health 4/0/0 (2; service_health); access.health.lifecycle
9/0/0 (1); install.status 7/0/0 (1; #o03 refuted on IRIS, bug-plt-115); status.readiness 10/2/2 (2; #o02 refuted);
status.sync 5/1/1; status.verify_sync 6/0/0 (1; #o03 refuted, bug-plt-116); status.capabilities 5/0/2 (1; #o01 refuted,
bug-plt-117); status.readers 4/2/6 (1); status.ledger 6/0/0 (#o02 refuted, bug-plt-120); status.diagram 1/0/2;
structure.drift 1/2/0 (adjacency_maint); structure.rebuild 5/5/4 (2; adjacency_maint, rebuild_reads, sql_procs,
operator_reports); structure.verify 0/0/4 (no model; bug-str-004 observed). No structural zero.

## 2. Totals
algorithm-execution 9/3/29 of 41 (22.0%), proved 10, refuted 2; status-and-repair 63/12/21 of 96 (65.6%), proved 63,
refuted 5; both 72/15/50 of 137 (52.6%), proved 73, refuted 7. Proved over full stated scope: 0 (premises: declared
index, KGEdgeCount below cap, no Arno library, P-COLLATE observed not proved, stable reads, sequential requests).
The 7 refutations are full / refuted / scope full: algorithms.cache#o03, cache.token#o01, install.status#o03,
readiness#o02, verify_sync#o03, capabilities#o01, ledger#o02. Full by definition with no check: access.health#o01,
verify_sync#o06. Exclusions 26: restatement 13, undecided-alternative 8, rationale 3, cross-reference 1,
evidence-annotation 1.

## 3. Grades: reused 84, changed 4, new 49
Reused: operator_reports NOTES (it. 52–53; install.status children); routine_reporting NOTES (install.status lead);
service_health NOTES (it. 7; access.health*); pagerank_admission NOTES + coverage.md line 549 (cache.pagerank);
communities NOTES (cache.token bullet 2); adjacency_maint, rebuild_reads, sql_procs NOTES (structure.drift, rebuild);
coverage.md line 103 (structure.verify absent).
Changed:
- algorithms.cache#o03: "Violated" (coverage.md 101) / "reviewed design only" (481) → full, refuted (graph_structure `witness_rolled_back_write_poisons_algo_cache`, proofs-d1e `control_f1004_create_moves_no_token`; native graph_structure_algo_cache_rollback.json OBSERVED_DEFECT).
- algorithms.cache.token#o01: "Proved (given the bump)" (coverage.md 102) → full, refuted for PPR (F-1004, bug-plt-017).
- algorithms.cache.concurrency#o01 → partial: coverage.md 101 grades this block against wording that is not its current text; soundness proved only for the repaired design that bumps the token after a rollback.
- install.status#o03: "design-verified" (routine_reporting, proved on local SQL) → full, refuted on IRIS (operator_reports `theorem_routed_never_counted`, bug-plt-115).
New: all routing, proof and gate obligations (absent); status reader bullets no model covers; rebuild failure and
concurrent-write bullets; structure.verify degree-cache and `ok` obligations.

## 4. Parents
algorithms.routing: no entailment; residual #o01–#o07 (revision, fallback, reload, excluded can all hold while a
non-listed algorithm, a named-graph call or a non-USER call is routed to a native reader). algorithms.cache: no
entailment; #o03 residual: token admission and cache.pagerank#o02 hold while the token does not move on a rollback
(bug-str-002) or on node creation for PPR (F-1004) — refuted as built; #o01 residual: no child states that PPR answers
are cached and reused across connections. algorithms.proof, access.health, install.status: own obligations only.
Metadata quirk: install.status's Children line is not a `- Children:` bullet, so the census lists no children for it.

## 5. Restatements
owner-updates: graph.default#x03 → install.status#o01. Cross-fork: algorithms.cache.token#x01 "A cached answer is valid
only while the graph-version token it was computed under is still current" → structure.rebuilt.valid (A);
cache.token#x02 "The token moves on changes to the adjacency index, not on node rows or properties" →
structure.rebuilt.token (A); cache.pagerank#x02 "The Owner's 10,000-row cap can break the requirement to list every node
and return scores summing to one" → algorithms.op.pagerank (AL). Same/enumerated owners: routing#x01 →
cache.pagerank#o06; routing#x04 → install.status.capabilities#o07; proof#x02 → routing#o02; cache.concurrency#x01 →
access.read_only.caches#o02; access.health#x01 → access.api_key.every_route#o01; install.status#x01 →
install.status.readers#o03; readiness#x01 → install.status#o03; structure.rebuild#x01 → structure.drift#o01.
Overlap kept: algorithms.cache.erasure#o01 (every erase path) vs erasure.scope#o05 (graph erase only, absent there too).

## 6. Grade-source errors
1. coverage.md line 101 maps algorithms.cache.concurrency to "never computed over rolled-back content"; current text is about two concurrent computations where the last store wins, large answers not stored, and the read-only login.
2. coverage.md line 102 "Proved (given the bump)" omits the as-built PPR refutation (control f1004).
3. design-verified tags on algorithms.cache, algorithms.cache.token, install.status sit alongside as-built refutations.
4. algorithms.owner "Every algorithm has an Owner … complete answers without Arno" contradicted by _engine/algorithms.py:658-678 (random_walk returns [] without Arno; own metadata calls it an observed divergence).
5. Stale NOTES links: operator_reports/NOTES.md → ontology/concepts/install.g5.md#install.status; rebuild_reads/NOTES.md → features/graph-structure.g5.md#structure.rebuild (resolve only through redirects).
6. structure.rebuild "the interned snapshot still does [need a rebuild] after bulk loads": operator_reports NOTES found bulk_load_session rows are interned through the declared index when the ^NKG skeleton exists; may hold only for erasure and BulkLoader (not traced).

## 7. Ranked uncovered
1. Native-reader routing (18 absent, no model): routing#o01–#o07, revision#o01–#o03, reload#o01, excluded#o01, proof#o01–#o03. Which reader answers for an unlisted algorithm / revision below minimum / named graph / non-USER namespace / multigraph / failed report / replaced library / invalid record. Bind arno_readers.py::route, ::load_proof, ::validate_proof, ::parse_report, ::read_reader_report; stores/iris_sql_store.py::_arno_route; ArnoAccel.cls (ReaderRevisions, multigraph refusal 242-262).
2. Native failure fallback (routing.fallback#o01–#o03): iris_sql_store.py::_native_answer and per-algorithm decoders (F-C1018).
3. Algorithm-cache freshness as built: cache#o03, token#o01 refuted; absent token#o04 (namespace-wide token), cache#o04, cache.erasure#o01, cache.concurrency#o02. Bind algo_cache.py (CACHEABLE), iris_sql_store.py::_cached_algorithm, AlgoCache.cls::Lookup/Put/InvalidateGraph, Eraser.cls (Kill ^IVG.AlgoCache at 249, 809), Txn.cls::Undo.
4. verify_graph (structure.verify#o01–#o04): reports healthy parallel edges as missing (bug-str-004, F-0204, F-0403). GraphVerify.cls (65-128), _engine/admin.py::verify_graph.
5. Rebuild failure and concurrent writes (structure.rebuild#o09, #o10, #o12, #o13; bug-str-009, bug-str-115). TraversalBuild.cls::BuildKG, ::BeginRebuild, Adjacency.cls::RowPut; readers BFSFast, Exec.cls variable-length path.
6. Evidence gate (proof.gate#o01–#o04): scripts/arno_reader_gate.py.
7. Status readers: readers#o05, #o06, #o07–#o09, #o11; diagram#o01–#o02; readiness#o07, #o12; sync#o06; capabilities#o05, #o07 (cypher_api.py 469-568, _engine/admin.py SHOW INDEXES 195-264, cli.py, _engine/schema.py::get_schema_visualization, capabilities() iris_sql_store.py 29-52, _engine/algorithms.py 341-343).
8. structure.drift#o01: writers outside adjacency_maint (BulkLoader, ledger OpCreateRel, temporal PutShadow, undeclared EdgeScan writers).

## 8. Iteration-60 residual mapping
store/iris_sql_store: routing#o04–#o05 (_arno_route), routing.fallback#o01–#o03 (_native_answer), cache#o01–#o03
(_cached_algorithm), capabilities#o07. SDK/CLI/HTTP admin: install.status.readers#o01–#o12 (/server, /metrics, /stats,
/schema, /indexes, ivg commands); access.health covered by service_health. Install residue:
install.status.capabilities#o01–#o07, structure.drift#o02. Operator residue: install.status.*, structure.rebuild,
structure.verify. None: GQL/GraphQL, translator, load_networkx/load_obo, migrations, temporal/retrieval.
Source-discovered omissions: random_walk returns [] with a warning without Arno (owned by algorithms.op.walks);
ObjectScript list makes status/capability fields claim PPR and WCC run natively (bug-plt-018, ArnoAccel.cls; metadata
only); a failed availability probe is kept for the life of the store (routing.reload metadata only); PPR's own conditions
for using the Owner (bidirectional calls or excluded nodes) only in routing metadata.

## 9. Limitations
Every proof marked narrowed (a reviewer could argue full scope where the bullet states the declared-index premise);
refutation convention per rule 3 (proofs-d1e control in reviewed-design crate); split granularity (health.lifecycle
bullet 4 → 3, /indexes → 3, ledger lead → 2, readiness bullet 1 → 2); HNSW "ready" state full by model definition only;
source reading limited to random_walk, the two health handlers, the Eraser AlgoCache kill and the arno_readers list.
