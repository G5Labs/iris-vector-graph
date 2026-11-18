# Bolt explicit transactions (bolt_tx)

Product `3eaa79cf`, unchanged. Iteration 56, repair of independent review 53-55 item F1 (inherited F-1601, now
[bug-plt-127](../../bugs_issues.md#bug-plt-127)). Owner:
[access.bolt.transactions](../../../ontology/features/client-interfaces.g5.md#access.bolt.transactions) (new), with the
consistency edits in [access.bolt](../../../ontology/features/client-interfaces.g5.md#access.bolt) and
[access.bolt.results](../../../ontology/features/client-interfaces.g5.md#access.bolt.results). Open question:
[access.transactions](../../open_questions.md#access.transactions) (real transactions or a refused BEGIN). An
as-built Verus transcription with native agreement; **not** executable-body verification. Bundled vstd only; no
`assume`, `admit` or `external_body`.

No frozen prediction: this is a review repair. The inherited audit (F-1601, playbook arm, `c16-s1-cypher-http`) and
the review's probe (`rv55b … bolt_tx`, neo4j 6.4.1) had already observed the outcome; the source was then read.

## What the model derives, from which input

| Part | Deciding input | Derived decision | Reader |
|---|---|---|---|
| `step` (as built, `Design::AsBuilt`) | the message kind and whether the session is FAILED | BEGIN, COMMIT, ROLLBACK, RESET, PULL: SUCCESS, no store effect; RUN: its writes are added to the store at once (P-AUTOCOMMIT) or, if it fails, FAILURE, nothing written (P-STMT-ATOMIC) and the session FAILED; while FAILED only RESET is handled, everything else IGNORED | the summary answers a client reads; a second connection's node count |
| `neo` (the rule) | the same messages | Bolt's client ledger: BEGIN opens a transaction, its writes are held until COMMIT; ROLLBACK, a failure, RESET or a closed connection discard them; auto-commit statements commit at once | the count the client may expect |
| `Design::Refuse` (checked alternative repair) | the same messages | BEGIN answers FAILURE and fails the session, so the client's statements are IGNORED until RESET | answers and count |

`S.tx` exists so a repair (control `atomic-tx`) can hold a transaction's writes; as built nothing sets it.

## Theorems (20 verified units)

General over any state that is not FAILED and any `inner` sequence of successful statements and PULLs (`plain`),
with `total(inner)` their writes:
- `theorem_rollback_keeps_writes`: `[BEGIN] + inner + [ROLLBACK]` answers SUCCESS to every message and the store grows
  by `total(inner)`; the rule leaves it unchanged.
- `theorem_rollback_departs_iff_writes`: as built and the rule differ exactly when `total(inner) > 0` (a write-free
  transaction agrees).
- `theorem_failed_tx_keeps_earlier_writes` (any failing statement size `v`): answers `SUCCESS…, FAILURE, IGNORED (PULL),
  IGNORED (ROLLBACK), SUCCESS (RESET)`; the earlier writes stay; the rule discards them.
- `theorem_reset_or_close_keeps_writes`: RESET or a closed connection in a transaction keeps its writes.
- Neighbors: `theorem_commit_agrees` (a committed transaction keeps its writes on both, COMMIT answered SUCCESS),
  `theorem_autocommit_agrees` (statements outside a transaction).
- Alternative repair: `theorem_refusal_matches_rule` (BEGIN answered FAILURE, store unchanged, equal to the rule).
- Witness: `theorem_witness_one_create_rolled_back` (one CREATE, store 1 as built, 0 by the rule).
- Lemmas: `lemma_exec_append`, `lemma_neo_append`, `lemma_one`, `lemma_neo_one`, `lemma_plain_as_built`,
  `lemma_plain_failed`, `lemma_plain_neo`, `lemma_shape`.

## Controls (7, all EXPECTED_FAIL)

| Control | Change | Fails in |
|---|---|---|
| `atomic-tx` | repair: BEGIN opens a transaction; RUN holds writes; COMMIT applies; ROLLBACK/RESET/close discard | `theorem_rollback_keeps_writes`, `theorem_failed_tx_keeps_earlier_writes`, `theorem_reset_or_close_keeps_writes` |
| `begin-refused` | repair: BEGIN answers FAILURE | the three above and `theorem_commit_agrees` |
| `rollback-answers-failure` | ROLLBACK answers FAILURE | `theorem_rollback_keeps_writes` |
| `run-not-committed` | a successful RUN's write is not committed (P-AUTOCOMMIT removed) | `lemma_plain_as_built` (every theorem uses it) |
| `failed-run-writes` | a failing statement keeps its writes (P-STMT-ATOMIC flipped) | `theorem_failed_tx_keeps_earlier_writes` |
| `failure-not-sticky` | the FAILED guard removed | `lemma_plain_failed`, `theorem_failed_tx_keeps_earlier_writes` |
| `rule-rollback-keeps` | the rule weakened: ROLLBACK keeps the writes | `theorem_rollback_keeps_writes`, `theorem_refusal_matches_rule` |

## Binding

`binding.py`, run from the pin tree on `ivg-cont-20261117-iris` (USER, prefix `i56b_<tag>_`, one label per case). The
product's own TCP listener (`start_tcp_bolt_server`) runs in-process over a real engine on its own connection.
- **R cases (9)**: an independent raw Bolt 4.4 client sends one message at a time and records each summary answer;
  then a second engine connection counts the case's nodes. Shapes: rollback (one and two CREATEs), failure then
  ROLLBACK then RESET, RESET in a transaction, a closed connection in a transaction, commit, auto-commit, an empty
  transaction rolled back, a failure in auto-commit followed by RESET and a CREATE.
- **D cases (8)**: the neo4j Python driver 6.4.1: `tx.rollback()` (one and two CREATEs), a failing statement then
  `tx.rollback()`, an aborted `execute_write`, a session closed with an open transaction, `tx.commit()`, a successful
  `execute_write`, auto-commit `session.run`. Observed: the count and the exceptions the driver raised.
- The failing statement is `CREATE (…) RETURN 1 AS a UNION RETURN 2 AS b`: it would write one node and fails in
  translation, so P-STMT-ATOMIC is observed (the count stays), not assumed.
- Port mutations mirror six controls (all detected); `rule-rollback-keeps` changes only the rule and has no product
  observation. One tampered count (`R_rollback` → 0) is detected. The rule's count is recorded beside each case: 10 of
  17 cases depart from it, exactly the ones that end a transaction without COMMIT.

Receipt: [AGREES 17](../../results/bolt_tx/20261117T065936Z-binding/receipt.json). A first run of the harness wrote
no receipt (the listener's `close()` was called from the wrong thread after all cases ran; fixed by scheduling it on
the loop); its nodes stay in USER under an earlier `I56B<tag>` label.

## Exact source roles (pin `3eaa79cf`)

| Member | Lines | Role |
|---|---|---|
| `iris_vector_graph/bolt_server.py::BoltSession._dispatch` | 459-519 (BEGIN 500-501, COMMIT 502-504, ROLLBACK 505-510, FAILED gate 465-472) | decision: BEGIN/COMMIT/ROLLBACK answer SUCCESS and change no store; FAILED ignores all but RESET/GOODBYE |
| `iris_vector_graph/bolt_server.py::BoltSession._handle_run` | 567-622 | effect: `engine.execute_cypher` with no session transaction, so a write commits at once; failure → FAILURE, FAILED |
| `iris_vector_graph/bolt_server.py::BoltSession._handle_reset` | 662-667 | effect: clears pending rows only; READY |
| `iris_vector_graph/bolt_server.py::TcpBoltSession` | 922- | entry: inherits `_dispatch`; the class every case connects to |

Shared, not bound here: `QueryMixin.execute_cypher` (the P-AUTOCOMMIT producer; its per-call transaction nesting is
the engine's documented contract, USER_GUIDE "Transactions").

## Premises and limits

- **P-AUTOCOMMIT**: the session's engine connection has no caller transaction, so each `execute_cypher` write commits
  when the call returns (USER_GUIDE; observed by the count after every case). If a caller transaction were open on
  that connection the outcome would differ; the listener opens none.
- **P-STMT-ATOMIC**: a statement that fails writes nothing (observed for a translation failure only; a statement that
  fails at run time after writing part of its effect was not tried).
- Not covered: WebSocket Bolt (`BoltSession` itself; same `_dispatch`), other drivers (Java, JavaScript, Go), the
  read-only gate inside a transaction, the HTTP `/db/{db}/query/v2` route (one statement), concurrent sessions and
  isolation (what another session reads mid-transaction).
- The rule is the Bolt message specification's; which repair IVG adopts is the open question. Both checked repairs
  (`atomic-tx`, `begin-refused`) satisfy it.

## HTTP `/db/neo4j/tx/commit` batch (iteration 59, independent review 56-58 item G1)

Owner: [access.http_transactions](../../../ontology/features/client-interfaces.g5.md#access.http_transactions) (new); finding
[bug-plt-136](../../bugs_issues.md#bug-plt-136) (Medium); open question [access.transactions](../../open_questions.md#access.transactions)
(working assumption revised, review m1). No frozen prediction: a review repair; the reviewer's probe had observed the
outcome before the source was read. 35 verified (20 + 15: 9 proofs, 6 recursive-spec termination checks).

| Part | Deciding input | Derived decision | Reader |
|---|---|---|---|
| `http_batch` (as built, `neo4j_tx_commit` 379-404) | read-only mode, each statement's writes `w`, whether it fails, whether its text names a write | refused (403, nothing runs) when read-only and **any** statement names a write; otherwise `run_all`: every statement runs, a failure adds an error and the loop goes on (P-STMT-ATOMIC: a failing statement writes nothing), status 400 iff an error | status, result and error counts; a second connection's node count |
| `rule_batch` (the rule) | the same | refused, or failed whole (store unchanged), or committed whole | the count the client may expect |
| `theorem_http_rule_is_bolt_rule` | — | `rule_batch(false, s, b)` equals Bolt's `neo` on BEGIN, one RUN per statement, COMMIT, close: the HTTP rule is not a second rule | — |

Theorems: general `theorem_http_batch_keeps_writes_around_failure` (outside the refusal, every statement runs, the
successful statements' writes stay, errors = failing statements, 400 iff a failure, and the rule keeps nothing when a
statement failed), `theorem_http_batch_departs_iff` (departure exactly when a statement failed and another wrote);
neighbors `theorem_http_all_succeed_agrees`, `theorem_http_read_only_runs_none`; witness
`theorem_http_witness_failing_middle` (CREATE, failing, CREATE: store 2, 3 statements ran, 400; rule 0).

Controls (7 new, 14 total, all EXPECTED_FAIL): `http-batch-atomic` (the repair), `http-stop-at-failure` (Neo4j's
order: stop at the failure), `http-failure-writes` (P-STMT-ATOMIC flipped), `http-status-ok-on-error`,
`http-read-only-runs-reads`, `read-only-first-only` (`_cypher_writes_under_read_only` checks only the first statement),
`rule-http-keeps-earlier` (the rule weakened; breaks the shared-rule theorem).

Binding section H (9 requests, FastAPI `TestClient` over `cypher_api.app` in-process, real engine on USER, counted by a
second connection; receipt [AGREES 26](../../results/bolt_tx/20261117T090118Z-binding/receipt.json)): `H_fail_middle`
(2 nodes, 400, 2 results, 1 error), `H_fail_first`, `H_fail_last`, `H_two_failures`, `H_all_ok` (200), `H_reads_around_failure`
(no write), `H_read_only_write` and `H_read_only_write_last` (403, nothing ran), `H_read_only_reads` (200). Six port
mutations mirror the HTTP controls and are each detected; a second tamper (`H_fail_middle` count 0) is detected. Four
H cases depart from the rule (the four with a failure among writes). Every error code is
`Neo.ClientError.Statement.SyntaxError` (observation only).

| Member | Lines | Role |
|---|---|---|
| `iris_vector_graph/cypher_api.py::neo4j_tx_commit` | 379-404 | decision: the read-only all-or-nothing gate; every statement runs and the loop continues after a failure; status |
| `iris_vector_graph/cypher_api.py::_cypher_writes_under_read_only` | 230-236 | decision: "any statement writes" over every statement before one runs |
| `iris_vector_graph/cypher_api.py::_run_cypher` | 239-265 | effect (cited): one statement through `execute_cypher` (P-AUTOCOMMIT), one retry (HD-1603), then raise |

Limits: `/db/{db}/query/v2` (one statement per request), a statement that fails at run time after writing part of its
effect, concurrent requests (the engine lock serializes them), the 1,000-row cap (owned by `http_rows`). Neo4j's HTTP
API page could not be fetched (permission denied), so the rule rests on the product's documents and its Bolt rule.
