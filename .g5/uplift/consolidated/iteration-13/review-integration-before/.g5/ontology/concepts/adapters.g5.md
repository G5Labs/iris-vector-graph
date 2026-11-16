# Adapters and connections

How IVG's Python code reaches IRIS. A client process uses the InterSystems DB-API driver; code running inside IRIS uses the embedded cursor below, which gives `iris.sql` the shape of a DB-API cursor so the engine's code is the same in both places. Which writes the ledger governs, and the network entry points, are in [access](access.g5.md).

## Definitions

- **Embedded cursor**: the DB-API-shaped cursor IVG builds over IRIS's in-process `iris.sql` module.
- **No-row statement**: an `UPDATE`, `DELETE` or `INSERT ... SELECT` that matches no row. IRIS reports it with SQLCODE 100.
- **Row count**: the cursor's `rowcount`. The value -1 means "not known".

## The embedded cursor

<a id="adapters.embedded"></a>
[D · adapters.embedded]

Inside IRIS, IVG runs SQL through the embedded cursor, so a statement gives the same answer and the same errors as it would through the client driver.
- Transaction words (`START TRANSACTION`, `BEGIN`, `COMMIT`, `ROLLBACK`) are passed over: they run nothing and leave no result.
- A statement with more than 100 parameters, or with an empty-text parameter, is sent with its values written in. A bound empty text would reach IRIS as NULL, and many bound values overflow the call stack.
- When IRIS refuses the prepared path as unsupported, the cursor tries the written-in path and then `%SQL.Statement`. If all three fail, one error names all three failures.

<a id="adapters.embedded.no_data"></a>
[I · adapters.embedded.no_data]

A no-row statement is an empty result with row count 0, not an error. Every other error still raises.
- The rule keys on SQLCODE 100, on the error itself or on the error that caused it, whichever of the three paths ran.
- When the written-in path meets SQLCODE 100 it returns no result, and for `UPDATE`, `DELETE` and `INSERT` the cursor reports row count 0 for that too.
- After a statement that did change rows, the row count is -1, not the number changed. Only a no-row statement reports 0.
- A batch call runs the statement once for each row and reports how many rows it ran, no-row statements included. Any other error stops the batch and raises.

## Metadata

### adapters.embedded
- Sources: [USER_GUIDE, embedded use](../../../docs/USER_GUIDE.md#L62-L66); [`iris_vector_graph/embedded.py::EmbeddedCursor.execute`](../../../iris_vector_graph/embedded.py#L312-L385) (transaction words `:314-321`; written-in choice `:328-336`; three paths `:337-359`), [`::_exec_inline`](../../../iris_vector_graph/embedded.py#L265-L277), [`::_is_ddtab_error`](../../../iris_vector_graph/embedded.py#L209-L211), [`::_sql_statement_execute`](../../../iris_vector_graph/embedded.py#L214-L224), [`::MAX_BOUND_PARAMS`](../../../iris_vector_graph/embedded.py#L188-L190); unit tests [test_embedded_no_data_and_native.py](../../../tests/unit/test_embedded_no_data_and_native.py)
- Playbook: the operations module's embedded-connection statements under [OPS-B4.6](../../../experiment/playbook-completion/ontology/17-operations.md#L196) (see [the statement crosswalk](../../Verus_verification/crosswalk/statements.tsv))
- Verus: see [embedded_no_data](../../Verus_verification/models/embedded_no_data/NOTES.md) for the result rule; the path choice itself is not modeled.
- Children: [no-row statements](#adapters.embedded.no_data)
- agent
- architecture-decision, operations
- test-coverage

New owner in the consolidated uplift: the guidance arm's ontology had no statement for `embedded.py`; the playbook arm had these rules in its operations module.

### adapters.embedded.no_data
- Sources: [`iris_vector_graph/embedded.py::_is_no_data`](../../../iris_vector_graph/embedded.py#L193-L196), [`::_no_data_ok`](../../../iris_vector_graph/embedded.py#L199-L206), [`::_exec_inline`](../../../iris_vector_graph/embedded.py#L265-L277), [`::EmbeddedCursor.execute`](../../../iris_vector_graph/embedded.py#L312-L385) (fold `:360-366`; row count `:373`), [`::EmbeddedCursor.executemany`](../../../iris_vector_graph/embedded.py#L387-L413); unit tests [`test_a_statement_that_matches_no_row_is_an_empty_result`, `every_other_error`](../../../tests/unit/test_embedded_no_data_and_native.py)
- Playbook: [OPS-T4.6.5](../../../experiment/playbook-completion/ontology/17-operations.md#L202), [OPS-B4.6.90](../../../experiment/playbook-completion/ontology/17-operations.md#L208)
- Verus: see [embedded_no_data](../../Verus_verification/models/embedded_no_data/NOTES.md) (`theorem_no_data_is_empty`, `theorem_other_error_raises`, `theorem_success_rowcount_unknown`, `theorem_batch_counts_rows`; as-built; controls `fold-every-error`, `ignore-cause`, `inline-none-not-folded`)
- Expands: [embedded cursor](#adapters.embedded)
- agent
- user-facing-behavior, data-integrity
- test-coverage

Public case M17. The baseline scored the playbook arm's ontology 0 here although `OPS-T4.6.5` states the first outcome: the rule sat in the operations module with no adapters owner. The "other errors raise" half is from `_is_no_data` and the re-raise at `embedded.py:204-205`, `:361-362`. Suspected divergence (code reading and a scripted run, see the model notes): when IRIS refuses the prepared batch path as unsupported after some rows already ran, the fallback runs every row of the batch again from the first (`embedded.py:399-410`).

Findings: [A batch fallback in the embedded cursor reruns the rows that already ran](../../Verus_verification/bugs_issues.md#bug-adp-001)
