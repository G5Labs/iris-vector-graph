# G01-cypher-a fork report (saved verbatim by the integrator)

G01-cypher-a is regraded: all 134 rows (66 full, 68 absent) are in `scratch/iteration-64/forks/G01-cypher-a/rows.tsv`. I edited no repository file.

**1. Counts**
- Full rows: 51 held, 15 full→partial, 0 full→absent.
- Absent rows: 64 held, 4 absent→partial, 0 absent→full.
- check_scope full→narrowed: 7 (varlength#o05, #o07; aql#o05, #o06, #o07; computed_values#o04; retype#o03).
- Statements fixed: 1 (retype#o03).
- Overlay result: exit 0. "rows reviewed: 134; problems naming them: 0; errors: 0" (absent→absent 64, absent→partial 4, full→full 51, full→partial 15, scope full→narrowed 7, scope n/a→narrowed 4, statement changed 1).

**2. Changed rows**

| id | old → new | letters | reason |
|---|---|---|---|
| query.paths.varlength#o03 | full → partial | b d | The (depth, id) order is assumed: `ordered(rows)` is a premise over an input sequence, by depth only. The id tiebreak is not modelled. |
| query.paths.varlength#o05 | scope full → narrowed | — | The ObjectScript half follows only by composing with `theorem_os_rows_eq_sql_rows`, which carries the ^KG = edge-rows premise. That locator was added. |
| query.paths.varlength#o07 | full → partial, scope → narrowed | b e | `theorem_fixture_path` requires `!env.arno` and no raise. The raise case and an Arno-capable env that does not choose Arno rest only on definitions. |
| query.paths.varlength#o08 | full → partial | a b | Only three single-fixture point checks plus the `trail` definition support the general no-reuse claim. |
| query.aql#o05, #o06, #o07 | scope full → narrowed | — | Point checks (LINT-2b). In #o07, `Lt` stands for every other operator. |
| query.writes.computed_values#o04 | scope full → narrowed | — | Point check over the enum. |
| query.writes.computed_values#o06 | full → partial | a | The computed-value refusal and the literal case between matched nodes hold only by `create_rel_matched_value`'s definition. |
| query.writes.retype#o03 | full → partial, scope → narrowed | f b d | Statement fixed (below). The model has no failed-write outcome, and the per-engine cache is a parameter. |
| query.system-procedures.results#o01, #o02, #o03, #o06, #o07, #o08 | full → partial | b | The rules apply to every handled metadata call; only the single-column db.labels branch is modelled. |
| query.aggregation.keys#o01 | full → partial | b e | Equal floats and equal maps are one-kind cases the statement covers, and they are not modelled. |
| query.aggregation.arithmetic#o02 | full → partial | b | Rounding is proved for two property sums only. The aggregate-with-integer-literal shape has only its column type proved. |
| query.optional#o01 | full → partial | c b | Rows are seen only through aggregate counts over one anchor, a proxy for the row stream. |
| query.paging#o04 | full → partial | c | The count value is proved; the rows it cuts are not modelled. |
| query.writes.delete#o05 | absent → partial | — | adjacency_maint models Cypher `DELETE r` as one `DelRow`, and `theorem_delete_one_parallel_keeps_other` shows the parallel edge survives. Endpoints staying is not modelled. |
| query.writes.atomic#o05 | absent → partial | d | proofs-d1d `cyw_l1::theorem_refused_query_writes_nothing` (baseline receipt) treats a query as one atomic step; per-row steps are not modelled. |
| query.browser-metadata#o02 | absent → partial, refuted narrowed | — | proofs-d1d `cx_f0802::counterexample_f0802` with `cys_l2::counts2` (control f0802 + baseline receipts): a count query under USE GRAPH gets the namespace-wide fixed answer. The text match is premise P-S1. |
| query.graph-scope.read#o02 | absent → partial, refuted narrowed | — | proofs-d1d `cx_f0818::counterexample_f0818` with `cys_l2::walk2` (control f0818 + baseline receipts): an all-graphs variable-length walk from a WITH-carried start crosses graphs. A one-hop MATCH after WITH is not modelled. |

The retype#o03 statement now restores the block's consequence: "…; an unreadable dictionary is taken as deployed, so where the function is missing the write fails instead of keeping the old type".

Rows held as full had their gaps cleared, moved to premises, or tagged `outside-statement:`; the rest are listed in `rows.tsv`. Seven full-scope rows carry `requires-reviewed:` notes: varlength#o06, aggregation#o02, #o03, #o05, #o06, #o10 and optional#o09.

**3. Owner contradictions, missed models and housekeeping**
- Census defect. proofs-d1d's `cys_l2`, `cx_f0802`, `cx_f0816` and `cx_f0818` (fresh control receipts) are cited nowhere in the census. Two rows outside my group should also cite them: F-0802 and F-0816 → query.graph-scope#o01 (currently partial); F-0818 → query.graph-scope.read#o03 (currently partial).
- Lint parser bug (census.py `proof_fns`). When the body `{` begins an indented line, as in the one-line style of aggregate_results.rs, the header runs into the next fn. Its `requires` then gets attributed to this proof: 19 of the 46 proof fns in aggregate_results.rs are affected. Example: `theorem_collection_contains_no_nulls` (lines 195–198) has no `requires`, but the lint reports one. I worked around it with a `requires-reviewed:` note on aggregation#o10. [Integrator: fixed in census.py before the merge.]
- No new owner contradictions. Already-known ones: query.with's metadata says C5 is modelled in clause_combos; clause_combos NOTES.md:85 says it is not (§6.1 #31). query.graph-scope.names (bug-cyp-006, §6.1 #1). query.browser-metadata (bug-cyp-003, §6.1 #2).
- No duplicate or missing obligations noticed.

**4. Rows I was unsure about (for the reviewer)**
- query.optional#o12 (held): I tagged the "only `=` is modelled" gap as `outside-statement`. A stricter reading of "a WHERE" makes it partial.
- query.paths.varlength#o06 (held, full scope): `theorem_arno_reachable` requires `kg_readable`, which the statement does not name.
- query.writes.delete#o01 (held): the edge counts per graph are inputs. The "whichever writer" condition holds only because the model is shape-only.
- query.system-procedures.results#o04, #o05 (held): I read bullet 2 as db.labels-specific.
- query.writes.atomic#o05, query.writes.delete#o05 (upgraded): both are partial upgrades that rest mostly on how a step is defined.
- query.aggregation.arithmetic#o02, query.paging#o04 (downgraded): strict calls a reviewer may contest.
