# embedded_no_data — notes

Consolidated uplift, 2026-11-14. Product baseline `3eaa79cf`. Root [embedded_no_data.rs](embedded_no_data.rs); controls in [model.json](model.json); binding [binding.py](binding.py). Public case M17. Owner blocks: [adapters.embedded](../../../ontology/architecture/adapters.g5.md#adapters.embedded), [adapters.embedded.no_data](../../../ontology/architecture/adapters.g5.md#adapters.embedded.no_data). Neither prior arm modeled the embedded cursor.

## Obligations and theorems (Proved, as-built transcription)

| Obligation | Theorem |
|---|---|
| a DML statement ending in SQLCODE 100 (error or cause, any path) is an empty result with row count 0 | `theorem_no_data_is_empty`, `theorem_no_data_on_every_path` (prepared, written in, second and third path) |
| any other error raises | `theorem_other_error_raises` |
| a successful statement reports row count -1 (not known) | `theorem_success_rowcount_unknown` |
| transaction words run nothing | `theorem_txn_skipped` |
| a batch with no first-pass error runs each row once, in order, and counts every row (no-row rows included) | `theorem_batch_counts_rows`, `witness_batch_no_data_row_counts` |
| a batch's first-pass error that is neither no-row nor unsupported-path raises | `theorem_batch_other_error_raises` |
| as built: an inlined non-DML statement meeting SQLCODE 100 reports -1, the prepared path 0 (both empty) | `witness_inline_select_no_data_rowcount` (recorded, not a requirement) |
| **suspected defect** (bug-adp-001): an unsupported-path error at row k > 0 makes the fallback rerun rows 0..k-1 | `witness_ddtab_mid_batch_reruns_rows` |

Expected: 13 verified, 0 errors; 6 controls EXPECTED_FAIL: `fold-every-error`, `ignore-cause`, `inline-none-not-folded`, `no-data-rowcount-unknown`, `batch-raises-on-no-data`, and `repair-fallback-resumes` (the repaired variant: the fallback resumes at the failed row, and the as-built rerun witness then fails).

## Bindings

| Model | Product (pin) | Grade |
|---|---|---|
| `is_no_data` | `iris_vector_graph/embedded.py::_is_no_data` :193-196 | Observed (binding) |
| `exec_inline` | `::_exec_inline` :265-277 | Observed |
| `chain`, `execute` | `::EmbeddedCursor.execute` :312-385 | Observed |
| `first_pass_row`, `pass1`, `fallback`, `executemany` | `::EmbeddedCursor.executemany` :387-413, `::_no_data_ok` :199-206 | Observed |
| `Err.ddtab` | `::_is_ddtab_error` :209-211 | Observed |

Binding: the pin's real cursor with a scripted `iris.sql` and a stub `iris` module: 1,250 `execute` cases (5 verbs x 2 parameter forms x 5 x 5 x 5 path outcomes) and 62,750 `executemany` batches (one or two rows; each row's form and its three path outcomes), 0 mismatches against a transcription of the spec functions. Detected: a changed row count, a fold-everything mutant, a resume-at-failed-row mutant. The rerun was observed on the real cursor: rows `[0, 0, 1]` completed, row count 2, no error. The first binding run (`…T042838Z-binding`, DISAGREES) is kept: its harness passed one parameter to a two-marker statement, so `_inline_params` raised; it says nothing about the product.

## Premises, trust and limits

- Substituted: IRIS's `iris.sql` and `%SQL.Statement`. Whether IRIS raises an unsupported-path (`<UNIMPLEMENTED>` / `ddtab`) error at a row's execution after a successful prepare is **not shown**; bug-adp-001 is therefore Suspected.
- `iris.sql.exec` is assumed to return a result object for a successful statement (so `rs is None` arises only from the SQLCODE 100 fold); if it returned None for a successful DML, the cursor would report row count 0 for rows changed. Not observed here.
- Descriptions and fetch behavior are not modeled. Trust inventory: none; bundled `vstd` only.
