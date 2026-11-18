# G12-qexec-clients-adapters fork report (saved verbatim by the integrator)

G12 (query-execution, client-interfaces, adapters): I regraded all 104 assigned rows (81 full, 23 absent) and wrote `scratch/iteration-64/forks/G12-qexec-clients-adapters/rows.tsv` (17 columns plus `reason`, one row per id). No repository files were edited.

overlay.py exits 1, but none of my rows fail. Its summary lines:
```
- FAIL: LINT-1 query.aggregation.keys#o04: full with an untagged gap: 'parity owner is query.native.equal-answers#o04 (bug-cyp-136)'
rows reviewed: 104; problems naming them: 1; errors: 0
  absent->absent: 21   absent->partial: 2   full->full: 68   full->partial: 13
  scope full->narrowed: 39   scope n/a->narrowed: 1
```
The one FAIL is a G02 row. Overlay's substring filter matched it because its gap text contains my id `query.native.equal-answers#o04`. [Integrator: overlay filter fixed; the re-run names 0 problems for G12.]

**1. Counts**
- Full: 68 held, 13 → partial, 0 → absent.
- Absent: 21 held, 2 → partial, 0 → full.
- `check_scope` full → narrowed: 39 (26 rows that stay full, 13 of them the new partials). The `n/a` → narrowed change is the query.paths#o01 upgrade.
- Statements fixed: 0.

**2. Grade changes (letters are the checklist items that failed)**

| id | change | why |
|---|---|---|
| adapters.embedded#o02 | full → partial, narrowed (d) | Which texts count as transaction words is supplied as `Verb::Txn`; the theorem only shows a Txn verb is skipped. |
| adapters.embedded#o05 | full → partial, narrowed (a) | The fallback order exists only in the spec fn `chain`; the theorem proves only that other errors raise. |
| adapters.embedded.no_data#o08 | full → partial, narrowed (b, e) | `theorem_batch_other_error_raises` requires the error at row 0; the case the row names (row 1 fails) is unproved. |
| query.paths#o01 | absent → partial, proved narrowed | `theorem_closed_gate_answers_sql`, `theorem_no_write_runs_natively` and `theorem_per_engine_switch` (native_admission) route these reads to `sql_out`. But the SQL answer is a model input, so "same as native off" is assumed. |
| query.native.reads-only#o05 | full → partial, narrowed (b, c) | Gap carries `owner-contradicted:` (below). Same-transaction visibility is proved only in the reviewed-design crate proofs-d1d and observed live. |
| query.native.equal-answers#o05 | full → partial; refuted → proved, narrowed (a, c, d) | The theorems decide the shadow comparator, not the native answer (native rows are an input). F-0907 is a comparator defect, not a violation of this obligation. |
| query.native.route#o14 | absent → partial, none/n/a | `new_engine` starts with an empty route set (definition only). Route eviction is not modelled. |
| query.shadow#o04 | full → partial, narrowed (a) | `theorem_shadow_switches` restates the definition of `shadow_on`; nothing distinguishes one engine from every engine. |
| access.bolt.transactions#o06, #o07 | full → partial, narrowed (d) | The commit itself is premise P-AUTOCOMMIT, not derived in the model. |
| access.http_transactions#o02 | full → partial, narrowed (d) | Same: the commit is P-AUTOCOMMIT; only the 200 status is derived. |
| access.bolt.versions#o01 | full → partial, narrowed (a, b) | The theorem says only "0 or a supported version"; first-proposal order exists only in `negotiate`. |
| access.bolt.versions#o04 | full → partial, narrowed (a) | Skipping exists only in the definition plus one point check; the "manifest alone" case is unchecked. |
| access.bolt.errors#o01 | full → partial, narrowed (b) | `Answer::Failure` carries no status code and no failure text. |
| access.bolt.errors#o04 | full → partial (b) | The undefined-parameter case the statement names is only in `bolt_code`'s definition. |

Stay full, `check_scope` full → narrowed (requires that narrow the domain, or a single-instance refutation): query.native #o01–#o03; gates#o01, #o03, #o04, #o05; privileges#o01; reads-only#o02, #o03, #o04; fallback#o01, #o02; route#o03, #o10. query.shadow#o02, #o05. adapters.embedded.no_data#o03, #o04. access.surfaces#o03. access.bolt: framing#o02; results#o07; transactions#o01–#o05; errors#o05. access.http_transactions#o01.

Rows that stay full, cells only: added `requires-reviewed:` notes to `premises` and tagged gaps `outside-statement:`; moved refutation descriptions from `gap` to `grade_source` (`refutes: …`) and reachability caveats to `premises`; added proof locators (`theorem_success_rowcount_unknown`, `theorem_no_data_is_empty` (embedded_no_data); `theorem_closed_gate_answers_sql`, `theorem_native_failure_answered_by_sql` (native_admission); `theorem_answer_is_prefix` (http_rows); `theorem_pull_reads_input_rows_then_clears` (bolt_stream); `theorem_rollback_keeps_writes` (bolt_tx)). Every changed row has `iteration` 64 and `; it64 regrade: …` appended to `grade_source`.

**3. Owner contradictions, duplicates, housekeeping**
- Owner contradiction: query.native.reads-only bullet 1. Its example (the MATCH before a per-row MERGE) never runs natively: `theorem_write_read_steps` shows merge_prefix and count_step fail the width check. Only a read statement chained after a write runs natively.
- Possible owner contradiction, not tagged: query.native.privileges' lead vs its own working assumption that a REVOKE does not reach running engines. I left it as a refutation.
- Housekeeping: query.native.gates metadata cites `F-0906` with "the engine caches the index answer until setup … not modeled". native_admission now models `idx_cache`, so that remark is stale.
- Duplicates or missing obligations: none noticed.

**4. Rows I was unsure of (for the reviewer)**
- The P-AUTOCOMMIT downgrades (transactions#o06, #o07, http_transactions#o02). The refutations #o01–#o04 still lean on the same premise; I accepted it there because it is observed live as bug-plt-127.
- Definition-backed grades: query.shadow#o04 is downgraded, but query.native#o01 and access.bolt.errors#o02, #o03 stay full on near-definitional theorems.
- equal-answers#o05: is F-0907 a refutation of this obligation or only of the comparator?
- equal-answers#o03: is the sort-rank theorem the stated observation (row order) or a proxy?
- route#o14: a definition-only partial.
- no_data#o05, errors#o05, surfaces#o03: kept full and narrowed although a named sub-case (fallback-path success, negative overflow, the untruncated count) follows only from the definition.

## Recheck after the show.py stub fix (42 ids, features/client-interfaces)
No change: the rows were graded against the page text read directly. Two statements leave out a qualifier that does not change the grade (access.bolt.framing#o02 "through 65,535 bytes"; framing#o05/#o06 "in the supported Bolt 4.4 protocol"). Overlay exit 0 with 0 problems.
