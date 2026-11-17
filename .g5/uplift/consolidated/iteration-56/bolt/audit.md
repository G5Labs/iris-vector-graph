# W1 binding-integrity audit (rows in decision-links.tsv of this folder)

Question for each row with relation models/proves/witnesses: would swapping or weakening that member's actual decision
break a theorem or the binding? Evidence: bolt_tx controls (7/7 EXPECTED_FAIL) and the binding's port mutations
(6/6 detected; counts of cases that change).

| Member | Formal item (relation) | Member's own decision | Swap / weaken | Breaks? | Verdict |
|---|---|---|---|---|---|
| `BoltSession._dispatch` 500-510 | `theorem_rollback_keeps_writes` (proves) | what BEGIN/COMMIT/ROLLBACK answer and change | refuse BEGIN (`begin-refused`: 14 cases change); open a held transaction (`atomic-tx`: 10 cases); ROLLBACK answers FAILURE (`rollback-answers-failure`: 3 cases) | yes: theorem and binding | active (decision derived from the message kind) |
| `BoltSession._dispatch` 465-472 | `theorem_failed_tx_keeps_earlier_writes` (proves) | FAILED ignores all but RESET | remove the guard (`failure-not-sticky`: 2 cases; `lemma_plain_failed` fails) | yes | active |
| `BoltSession._handle_run` 567-622 | `step` (models) | runs the statement with no session transaction, so it commits at once; a failure writes nothing and fails the session | not committing (`run-not-committed`: 16 cases); a failing statement keeps its write (`failed-run-writes`: 3 cases) | yes | active (strengthens existing bolt_stream/bolt_answers rows on the same member) |
| `BoltSession._handle_reset` 662-667 | `theorem_reset_or_close_keeps_writes` (proves) | RESET clears rows and the failure, not the writes | discarding a held transaction (`atomic-tx`, `R_reset_in_tx` changes); not clearing the failure (the binding's `R_fail_autocommit` CREATE after RESET would be IGNORED: count 0, a mismatch; no named port mutation for this one) | yes (binding; theorem via `atomic-tx`) | active |
| `TcpBoltSession` (class) | `step` (cites) | none: inherits `_dispatch` | n/a | n/a | locator only, not counted |

Not added: `start_tcp_bolt_server` and `TcpBoltSession.run` (entries without a decision of their own here); the
engine's `execute_cypher` (the P-AUTOCOMMIT producer, a shared premise named in NOTES, not bound by this model).
New active members from this folder: 0 (all four active members were already bound by bolt_stream / bolt_answers;
these rows strengthen them with a transaction claim).
