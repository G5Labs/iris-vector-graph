# W1 coverage snippet (for coverage.md; parent integrates)

coverage.md has no bolt_answers row (iteration 55 recorded it only in its handoff) and bolt_stream appears only in the
iteration-9 section text. Proposed rows for an iteration-56 table:

| Family | Established bounded relation | Limits |
|---|---|---|
| [bolt_tx](models/bolt_tx/NOTES.md) (new) | Bolt message sequence (BEGIN, RUN, PULL, COMMIT, ROLLBACK, RESET, close; FAILED state) → summary answers and the committed node count a second connection reads, as built; the rule `neo` (a transaction's writes kept only by COMMIT); general over any sequence of successful statements: rollback, failure, RESET and close keep the writes (bug-plt-127), commit and auto-commit agree; refusing BEGIN proved to satisfy the rule. 20 verified, 7/7 controls, binding AGREES 17 (raw Bolt 4.4 client and neo4j 6.4.1), 6/6 mutations and tamper detected. | Premises P-AUTOCOMMIT (no caller transaction on the session's connection) and P-STMT-ATOMIC (a failing statement writes nothing; observed for a translation failure only). WebSocket Bolt, other drivers, the read-only gate inside a transaction, the HTTP transaction routes and isolation from other sessions unchecked. |
| [bolt_stream](models/bolt_stream/NOTES.md) (scope note) | Unchanged. `theorem_commit_preserves_but_rollback_discards` concerns the **pending result rows** only (PULL after ROLLBACK reads none), not the transaction's writes. | A Bolt rollback's effect on writes is bolt_tx's (bug-plt-127). |
