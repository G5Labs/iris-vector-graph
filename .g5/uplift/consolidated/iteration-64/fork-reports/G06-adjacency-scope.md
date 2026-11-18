# G06-adjacency-scope fork report (saved by the integrator; verbatim content)

G06-adjacency-scope regrade (135 rows: 90 full, 45 absent). `rows.tsv` is written and `overlay.py` exits 0. Nothing in the repository was edited. Files: `rows.tsv`, `make_rows.py` (every decision with its reason), `show.txt` / `compact.txt` (inspection dumps), `work/`.

## 1. Counts

| | count |
|---|---:|
| full held as full | 76 (3 of them proved → refuted) |
| full → partial | 14 |
| full → absent | 0 |
| absent held | 43 |
| absent → partial | 1 |
| absent → full | 1 |
| check_scope full → narrowed | 4 (one on a row that also went partial) |
| statements fixed | 0 |

Rows changed: 71 in all; 25 are rewrites of gap, premises or locators with no grade change (gaps tagged `outside-statement:`, narrowing/findings/control notes moved out of `gap`, six `requires-reviewed:` notes, three general theorems added).

Overlay: rows reviewed: 135; problems naming them: 0; errors: 0 (absent->absent 43, absent->full 1, absent->partial 1, full->full 76, full->partial 14, scope full->narrowed 4, scope n/a->narrowed 5).

## 2. Rows whose grade, check or scope changed

| id | old → new | letters | reason |
|---|---|---|---|
| graph.all_graphs_read#o03 | absent → full refuted narrowed | missed model | proofs-d1d `cys_l1` with `cx_f0818::counterexample_f0818`: an all-graphs variable-length walk follows graph 2's edge from graph 1's node with the same id. The f0818 control receipt is fresh (EXPECTED_FAIL), and a live check reproduced it. |
| structure.adjacency.declared#o01 | full proved → full refuted narrowed | g | The statement names the ledger writer. `witness_ledger_delete_rel_drops_survivor_indexed` shows ledger delete_rel removes the surviving edge's entry (bug-str-001; native OBSERVED_DEFECT). |
| structure.degree.cache#o01 | full proved → full refuted narrowed | e/g | The proof needs P-QUIET, which no component establishes. Without it, `witness_aba_delete_and_recreate_serves_stale_degree` serves 2 while a recount gives 0. |
| temporal.structural.mark.readers#o07 | full proved → full refuted narrowed | g | edge_acceptance `theorem_caller_marker_retained`: `create_edge` with caller qualifiers `temporal=True` writes a marked explicit row (F-C0351). Gap tagged owner-contradicted. |
| structure.adjacency#o05 | full → partial | d | `held_elsewhere` is a boolean input to `nkg_edge_after_remove`. |
| structure.adjacency.scan#o03 | full → partial (proved narrowed) | a | The named-source contrast exists only in `scan_hit`'s definition. |
| structure.adjacency.scan#o06 | full → partial | a | The weight column is `scan_w`'s definition only. |
| structure.adjacency.scan#o11 | full → partial | a/b | `hop_targets` returns `match_all` for both plans, so "same edges" is assumed, not derived. |
| structure.degree.cache#o02 | full → partial | a | The generation bump is the Write step's definition; no theorem concludes it. |
| structure.degree.cache.uncommitted#o03 | full → partial (proved narrowed) | a/b | The generation test is an equivalent mutant; only the probe half is distinguished. |
| structure.degree.cache.erase#o01 | full → partial | a | Clearing is KillCommitted's definition; only one source is modelled. |
| structure.degree.cache.warm#o03 | full → partial | b/d | One-source theorem; the source sequence is an input. |
| structure.rebuilt.stamp#o05 | full → partial, scope narrowed | b | Soundness and a length bound, not completeness or order for a mixed list. |
| structure.rebuilt.valid#o01 | full → partial | a | The hit rule is `a_served`'s definition; the only soundness theorem is for the repaired variant. |
| temporal.stats.writers#o01 | full → partial | b | Sum, maximum and the sketch after a first insert are not concluded. |
| temporal.stats.writers#o03 | full → partial | b | The extremes after an update are not concluded. |
| temporal.stats.writers#o04 | full → partial | b | Sum, max and sketch rebuild, and the counter's removal at zero, are not concluded. |
| temporal.structural.adopt#o05 | full → partial | a | Ledger create_rel adoption is `apply_op`'s definition only. |
| temporal.structural.upgrade#o03 | absent → partial | missed model | The sql_procs `Bf` state carries the opt-out registry, and `backfill` leaves it unchanged by definition. |
| structure.adjacency.scan#o07, declare#o03, declare#o04 | scope full → narrowed | e | A two-row index; a declared edge index only; the label index already functional. |
| structure.rebuilt.valid#o02 | full, check none → proved narrowed | – | `theorem_repaired_algo_cache_sound` applies by documented composition (`astep` reads the variant only at Rollback). |
| temporal.structural.upgrade#o07 | full, check none → proved narrowed | – | `theorem_backfill_writes_missing_only` is general over the graph key. |

## 3. For the integrator
- Owner contradictions tagged: graph.key.owner#o02 (`_validate.py:47` tests only ord<32 or ==127); structure.multigraph.layout#o06 (no retry, §6.1 item 21); structure.rebuilt#o01 (`^NKG` uses its own flags, §6.1 item 24); temporal.structural.mark.readers#o07 (the caller-marker exception, adopt bullet 5).
- Ownership choices: writer-path defects of the layout rows (ledger delete_rel bug-str-001, ledger reweight bug-str-012) tagged `outside-statement`, owned by structure.adjacency.declared#o01, now refuted; the other reading is to refute layout#o02 and #o03 as well. Concurrency: temporal.stats.writers#o01 leaves concurrent inserts to temporal.stats#o01's residual; structure.adjacency.declared#o03's concurrency is now a premise, so its proof is narrowed.
- Missed models for other groups: proofs-d1d `cx_f0802` (count shortcut under USE GRAPH unscoped) and `cx_f0816` (`db.labels` unscoped) are cited by no census row (query.graph-scope rows). `witness_ledger_delete_rel_drops_survivors_non_indexed` is uncited.
- Housekeeping: `design-verified` is now overstated on temporal.stats.writers and structure.degree.cache.uncommitted. proofs-d1e `gmode_l2` models ekey allocation only as "any fresh key".
- Duplicates or missing obligations: none found.

## 4. Unsure rows (reviewer targets)
- graph.all_graphs_read#o03: whether a reviewed-design counterexample on one query shape should be full refuted or partial.
- structure.degree.cache#o01: refuted or partial (P-QUIET); erase#o02 already carries the same witness.
- structure.rebuilt.valid#o02: full by composition through a repaired-variant theorem.
- temporal.structural.upgrade#o02: domain preservation is by definition; the theorem preserves values.
- temporal.stats.writers downgrades for unconcluded sum and max may be stricter than other groups.
- structure.multigraph.layout#o02 and #o03: the outside-statement ownership choice above.
