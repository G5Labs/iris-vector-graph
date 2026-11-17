# W1 register snippet (for bugs_issues.md; parent integrates)

Placement: the **High** section of `.g5/Verus_verification/bugs_issues.md` (beside bug-tmp-003, which is High for the
same class of defect: a rollback that leaves effects behind). Then replace the line
`<span id="F-1601"></span> [F-1601: review record](audits/register-20261115/bugs-review.md#F-1601)` near line 5893 with
`<span id="F-1601"></span> [F-1601: promoted to bug-plt-127 in iteration 56](#bug-plt-127); [review record](audits/register-20261115/bugs-review.md#F-1601)`
so the old anchor still resolves. IDs reserved and unused: bug-plt-128, bug-plt-129.

If the parent prefers Medium (the original audit's S2), change only the severity line and the last sentence of
Consequence; the reasoning for High is below.

---

<a id="bug-plt-127"></a>
### A Bolt rollback keeps the transaction's writes: BEGIN, COMMIT and ROLLBACK do nothing and every statement commits at once

Severity: High · Decision: Open

Run: Uplift 2026-11-17 (continuation, iteration 56; promoted from F-1601, playbook audit 2026-11-13/14)

Found by: playbook arm, F-1601 ([review record](audits/register-20261115/bugs-review.md#F-1601); live `c16-s1-cypher-http`), then "inconclusive, not reproduced" in the 2026-11-15 register audit; reopened by independent review 53-55 item F1 ([review](../uplift/consolidated/iteration-56/REVIEW-53-55.md), probe `rv55b … bolt_tx`, [observation](../uplift/consolidated/iteration-56/review-probes/rv55b-observed-20261117T064330Z.json)). Model: [bolt_tx](models/bolt_tx/NOTES.md) `theorem_rollback_keeps_writes`, `theorem_rollback_departs_iff_writes`, `theorem_failed_tx_keeps_earlier_writes`, `theorem_reset_or_close_keeps_writes`; neighbors `theorem_commit_agrees`, `theorem_autocommit_agrees`; controls `atomic-tx`, `begin-refused` (the two repairs), `rollback-answers-failure`, `failure-not-sticky`.

Reproduced by: **E2E reproduced** on the run-isolated IRIS 2026.1 continuation fixture with the unchanged pin, the product's own TCP Bolt listener (`start_tcp_bolt_server`, real engine) read by an independent raw Bolt 4.4 client and by the neo4j Python driver 6.4.1 ([binding](results/bolt_tx/20261117T065936Z-binding/receipt.json), AGREES 17; [cells](../uplift/consolidated/iteration-56/bolt/tx-observed-20261117T065936Z.json), prefix `i56b_065931_`). Raw client: `BEGIN, RUN CREATE, PULL, ROLLBACK` answers SUCCESS to all four and a second connection counts 1 node (2 for two CREATEs); after a failing statement, PULL and ROLLBACK are IGNORED and RESET succeeds, and the earlier CREATE stays; RESET or a closed connection inside a transaction keeps it too. Driver: `tx.rollback()`, a failure then `tx.rollback()` (the driver raises only the statement's `CypherSyntaxError`), an aborted `execute_write` (only the application's `RuntimeError`) and a session closed with an open transaction all leave the node. Passing neighbors: `tx.commit()`, a successful `execute_write` and auto-commit `session.run` keep one node, as they should; an empty transaction rolled back leaves none; a failing statement writes nothing.

Expected: [access.bolt.transactions](../ontology/concepts/access.g5.md#access.bolt.transactions): an explicit transaction keeps its writes only if it commits; ROLLBACK, a failed statement, RESET or a closed connection must leave none of them, or the server must refuse BEGIN so the client knows each statement commits on its own (Bolt message specification: BEGIN/COMMIT/ROLLBACK; README: "a neo4j-driver compatible server"; the engine's own contract, USER_GUIDE: a caller's rollback removes IVG's writes). Which of the two repairs IVG adopts is the open question [access.transactions](open_questions.md#access.transactions); both make this outcome impossible.

Observed: `BoltSession._dispatch` answers BEGIN and COMMIT with SUCCESS and ROLLBACK with SUCCESS after clearing only the pending rows (`bolt_server.py:500-510`); `_handle_run` runs each statement through `engine.execute_cypher` on a connection with no open transaction, so each write commits when the statement finishes (`:567-622`); RESET clears pending rows only (`:662-667`).

Consequence: a Neo4j application that relies on a transaction to undo its work keeps partial or unwanted writes, and every signal it gets says the rollback succeeded: a unit of work that fails halfway leaves its first half, and a retry of that unit (the driver's own `execute_write` pattern, or the application's) writes it again. The damage is silent, persisted and on the driver's standard API. High: the same class as [bug-tmp-003](#bug-tmp-003) (a rolled-back write leaves effects), here for every write a Bolt transaction makes.

Repair proposal (not implemented, checked in the model only): either hold a transaction's statements in one engine transaction on the session's connection and end it on COMMIT, ROLLBACK, RESET, failure or disconnect (control `atomic-tx`), or answer BEGIN with a FAILURE saying explicit transactions are not supported (control `begin-refused`, design `Refuse`, `theorem_refusal_matches_rule`). Preserve: auto-commit statements (`theorem_autocommit_agrees`) and committed transactions (`theorem_commit_agrees`). Writers affected: `_dispatch`, `_handle_run`, `_handle_reset`, the TCP and WebSocket run loops (connection close). Distinguishing case: the binding's `R_rollback` (count 1 today, 0 after either repair) beside `R_commit` (1 on both). The read-only gate inside a transaction and isolation from other sessions are not checked.

Governing statement: [access.bolt.transactions](../ontology/concepts/access.g5.md#access.bolt.transactions).
