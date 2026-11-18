# G08-algorithms fork report (saved verbatim by the integrator)

G08-algorithms regrade is finished. `rows.tsv` (153 rows, one per id) and its generator `make_rows.py` are in `scratch/iteration-64/forks/G08-algorithms/`. I edited no repository file and committed nothing. The overlay passes (exit 0).

**1. Counts**
- **Full rows (64):** 44 held, 20 went full→partial, none went full→absent. One held row moved from proved to refuted: `algorithms.op.walks#o03`.
- **Absent rows (89):** 87 held, 2 went absent→partial, none went absent→full.
- **check_scope:** 2 went full→narrowed. 1 went narrowed→n/a, because `khop#o06` no longer cites a proof.
- **Statements fixed:** 2.
- **Overlay summary:** rows reviewed: 153; problems naming them: 0; errors: 0 (absent->absent 87, absent->partial 2, full->full 44, full->partial 20, scope full->narrowed 2, scope narrowed->n/a 1, statement changed 2)

**2. Changed rows** (the full text is in each row's `reason` column)

| id | old → new | letters | reason |
|---|---|---|---|
| algorithms.cache#o03 | full refuted, scope full → narrowed | e, g | Single witness plus the d1e control f1004. Gap tagged `owner-contradicted` (bug-str-002, F-1004). |
| algorithms.cache.token#o01 | full refuted, scope full → narrowed | e, g | One counterexample (control f1004); `theorem_hit_is_fresh` has `requires`. Gap tagged `owner-contradicted` (F-1004). |
| algorithms.graph_scope#o01 | full → partial | b, e | The theorem requires every coordinate to be foreign; the mixed default + named case rests on the `selected` definition. |
| algorithms.op#o07 | full → partial | b | gamma/tol and "before reading data" are not modelled. Statement fixed: restored "with ValueError". `owner-contradicted`: the method raises TypeError. |
| algorithms.op#o08 | full → partial | a, b | Boundary point checks only. `owner-contradicted`: sampleSize is capped at 1,000,000 (`_validate.py:249`). |
| algorithms.op.pagerank#o06 | full → partial | b | Only the 10,000-row cut is shown; the sum below 1 and the cached repeat are not reached. |
| algorithms.op.ppr#o01 | full → partial | a | The only proof is mass conservation; the even split over seeds and out-edges is just the `next`/`scatter` definitions. |
| algorithms.op.cdlp#o04 | full → partial | b, e | "No warning" is not modelled; parity is proved for the two-node pair only. |
| algorithms.op.subgraph#o07, #o08 | full → partial | b | One reader of two: the Arno `SubgraphNativeJson` reader answers first when loaded (`iris_sql_store.py:2526-2541`) and is not modelled. |
| algorithms.op.subgraph#o10 | full → partial | a, e, b | The theorem's `requires` excludes edgeless seeds, which is the case at issue; it rests on the `admit` definition; Arno reader also missing. |
| algorithms.op.khop#o01 | full → partial | b | Reach order and the max_nodes cut are only observed. |
| algorithms.op.khop#o03 | full → partial | a, d, b | Seed inclusion is a definition over the input `seed_is_node`; no edge output is modelled. |
| algorithms.op.khop#o06 | full → partial (none, n/a) | a | Spec fn only (would fail LINT-3). |
| algorithms.op.walks#o03 | full proved → full refuted (narrowed) | e, g | The proof requires distinct keys; `theorem_same_hop_target_collapses` is a counterexample (locator added). |
| algorithms.op.neighbors#o02 | full → partial | d | `seen_before` is an input to `appended`. |
| algorithms.op.neighbors#o04, #o05 | full → partial | a, c | Label-level model (`neighbors_reads == true`, `expansion_reads`); no list is modelled. |
| algorithms.op.neighbors#o06 | full → partial | c | A per-edge keep predicate; the returned list is not modelled. |
| algorithms.op.paths#o04 | full → partial | b | Holds for ShortestPathJson only. `owner-contradicted`: ShortestLength walks non-both directions outbound (`TraversalPaths.cls:121`). |
| algorithms.op.paths.weighted#o03 | full → partial | b | The proof is for the SQL entry; the procedure's own check is only observed. |
| algorithms.op.paths.weighted#o13 | full → partial | a, c | `PathAns::Search` is a delegation token; JSON text and `{}` are not modelled. |
| algorithms.op.paths.weighted#o15 | full → partial | b | "Exactly as the procedure" compares against an unmodelled side. |
| algorithms.op.paths#o02 | absent → partial | — | proofs-d1e `atrav_l1::shortest` (reviewed design) gives length 0 for equal endpoints; empty endpoints are not modelled; definition only. |
| algorithms.op.subgraph.guided#o06 | absent → partial | — | `retrieval_compose::admit` dedupes and needs an edge; this entry's PPR seed handling is not modelled. |
| algorithms.op.walks#o05 | held full | — | Statement fixed: removed the imported "(leaving its staged rows)". |

Several held rows changed cells without a grade change:
- **Gap retagged `outside-statement:`:** cache.token#o02, cache.pagerank#o01 and #o06, op.pagerank#o01, ppr#o03, #o04, #o05, #o07, and wcc#o03.
- **Locators added:** cache.pagerank#o05 `theorem_count_max_producer`; ppr#o04 `theorem_zero_tolerance_does_not_stop_on_zero_change`; ppr#o05 `lemma_missing_rows`; ppr#o07 `theorem_multiplicity_divisor_not_distinct_neighbors`; completion#o02 `lemma_missing_rows`, `lemma_missing_has`; weighted#o07 `theorem_raw_signed_rational_json`; weighted#o14 `theorem_readers_check_rdf_edges`.
- **Provider limits moved from gap to premises:** cache.pagerank#o01 (SHA256 injectivity), wcc#o01 and weighted#o01.
- **Bug ids moved from gap to grade_source:** completion#o01, subgraph#o02, guided#o03 and #o04, khop#o07, walks#o04 and #o05, paths#o06 and weighted#o17.

**3. Owner contradictions, duplicates, housekeeping**
- Owner contradictions, tagged in gap: algorithms.cache#o03 (bug-str-002, F-1004); algorithms.cache.token#o01 (F-1004); algorithms.op#o07 (TypeError for an unknown keyword); algorithms.op#o08 (sampleSize cap); algorithms.op.paths#o04 (ShortestLength); algorithms.owner#o01 (random_walk has no Owner, `algorithms.py:658-678`); algorithms.op.walks#o07 (random_walk needs Arno); algorithms.graph_scope#o02 (the refusal message does not name the method, `NKGAccel.cls:213-223`).
- Possible owner gap (not tagged): traversal_strategy models an Arno route for BFS (`theorem_arno_only_default_outbound`), but algorithms.routing#o01 lists only PageRank, PPR, WCC, CDLP and subgraph as Native Reader users. Either the block omits BFS or BFS routing belongs to another owner.
- Duplicates or missing obligations: none seen.
- Housekeeping (report only): coverage.md:506 says "graph algorithm numerics … weighted shortest path's optimality" have no formal link; that is stale for weighted_paths. The crosswalk links kg_MENTIONS to the label `neighbors_reads`, which does not decide neighbors#o03.

**4. Rows I was unsure about** (good reviewer targets)
- cache.pagerank#o01: held because "miss on key difference" follows in one step from `call`'s key-equality test. Partial is arguable.
- ppr#o02 and ppr#o06: held on point witnesses at the hop-list level, relying on the hops→score composition documented in NOTES. They could be judged the same way as ppr#o01, which I downgraded.
- weighted#o02, #o04, #o05, #o09, #o18: each rests on the `weight`/`selected`/`feasible` definitions inside the optimality theorem's conclusion.
- walks#o03: proved → refuted.
- subgraph#o07/#o08/#o10 vs guided#o07/#o08: I applied the Arno-reader downgrade only where the block does not limit its "Today" text to the ObjectScript reader.
- neighbors#o06: a keep predicate rather than a list.
- paths#o02 and guided#o06: these upgrades rest on definitions only (one from a reviewed-design crate).
