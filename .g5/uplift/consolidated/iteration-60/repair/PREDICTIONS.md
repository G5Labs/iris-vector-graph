# Iteration 60 repair: predictions frozen before any native run

Written 2026-11-17 by the repair builder, before any probe or binding of this repair ran and before the repaired
models existed. Committed on its own as a checkpoint so its digest precedes every observation.

**Exposure (disclosed).** These are not independent predictions. They are informed by (a) the published review
`$G5_RUN_STATE/review-60/REVIEW.md` and its observations (FE-1 to FE-6, BC-1, C4, CG-3, CG-4), which I read first; and
(b) my own reading of the deciding source at the pin: `replay.py` `read_canonical` / `_drop_temporal_marked` / `compare`
/ `verify`, `changeset.py` `_str_value`, `LedgerApply.cls` `QualsJson` / node operations, `Ledger.cls` `Commit` /
`CommitInTxn` / `WriteRevision` / `Count`, `LedgerStats.cls` `Ensure` / `Bump`, `LedgerRevision.cls` MAXLEN values,
`errors.py`, `client.py` readers. They are graded as repair confirmations, not discovery. Rows marked **new** are
not in the review (they follow from the same source reading).

Fixture: local `ivg-uplift-next-20261115`. Namespaces are this repair's own, created additively: `I60RA` (client,
counters, limits, readers), `I60RC` (max_ops 2), `I60RE` (never enabled), `I60RV` (verify, general), `I60RT` (verify,
temporal text marker). IDs start with `i60r`.

| ID | Case (changing input) | Reader | Predicted outcome |
|---|---|---|---|
| R1.a | `Changeset.create_relationship(a, R, b, qualifiers={"temporal": "yes"})` committed (neighbour) | `verify()` | `equal`, no entry for the tuple |
| R1.b | same with `{"temporal": "true"}` | `rdf_edges.qualifiers`; `verify()`; `verify(adopt=True)`; `verify()` | row stores the text `{"temporal":"true"}`; `diverges` / `unrecorded_writes` with the tuple's existence entry and `qual:temporal` = `"true"`; adopt writes one adoption revision (records create_rel + set_qual); the next verify still `diverges` with the same two entries |
| R1.c | same with the Python boolean `{"temporal": True}` | same | identical to R1.b (`_str_value` stores `"true"`) |
| R1.d (**new**) | engine `create_edge(a, R, b, qualifiers={"temporal": "true"})` (unrecorded, text) | `verify()`, adopt, `verify()` | `diverges` with existence + qualifier entries; adoption records them; the next verify still diverges |
| R1.e (**new**) | engine `create_edge(a, R, b, qualifiers={"temporal": True})` (unrecorded, JSON boolean) | `verify()` | no entry for the tuple: the tables leave a JSON-true row out (F-C0351's behaviour, consistent with the scope rule) |
| R2 | post-commit property `{orphan: {"k": "v"}}` on an ID with no node row | `verify()` | entries for the orphan: node existence (created) and `prop:k` = `"v"` |
| R3.a | caller A commits inside its open transaction; process B commits | B's exception, wall time; `rej_lock_timeout` from a third connection | `LedgerLockTimeoutError` after about 40 s (30 s head lock + ~10 s stalled counter row); `rej_lock_timeout` +0 while A is open and after A ends; B gets the next seq after A's rollback |
| R3.b (**new** neighbour) | the head lock held by another process with a plain `LOCK` (no transaction); B commits | same | `LedgerLockTimeoutError` after about 30 s; `rej_lock_timeout` +1 |
| R3.c (**new**) | while A's transaction is open, a third process calls `Graph.KG.Ledger.Count("rej_strict_block")` (the strict guard's counter call); then again after A ends | `rej_strict_block` | first call stalls about 10 s and is lost (+0); after A ends +1 |
| R4 | a commit whose records touch the target of an unfinished redaction (my own prefix) | exception, hook events, counters, head | `RedactionInProgressError`; exactly one hook event `redaction_in_progress`; every counter unchanged; head unchanged |
| R5 | during that unfinished redaction: `get_revision`, `diff`, `reconstruct`, `export_reconstruction` with an unknown revision ID; after the redaction finishes, the same calls | exception class | `RedactionInProgressError` while unfinished; `UnknownRevisionError` after |
| R6.a | message of 4,000 characters | commit | commits; `commits_ok` +1 |
| R6.b | message 5,000 / idempotency key 300 / correlation ID 300 / actor 300 / object source whose JSON exceeds 4,000 | exception, event, counters, head, node rows | `LedgerInconsistencyError` naming the revision row save failure; one hook event `inconsistent`; every counter unchanged; head unchanged; 0 node rows written |
| R6.c (**new**) | a keyed changeset commits; the same key, actor and operations again with a 5,000-character message | result, counters | replays (`replayed=True`, same seq, `replays_idem` +1): the key check precedes the revision row write |
| R7.a | missing relationship endpoint caught with `except iris_vector_graph.NodeNotFoundError` | which handler catches | not caught; escapes as `iris_vector_graph.ledger.errors.NodeNotFoundError` with `op_index` 1 |
| R7.b | the same caught with `except iris_vector_graph.ledger.NodeNotFoundError`, and with `except iris_vector_graph.errors.IVGError` | which handler catches | both catch it |
| R7.c | `set_property`, `add_label` on an ID that is no node | exception class and message | ledger `NodeNotFoundError` (`op_index` of that op, `missing_node` set) whose message says "create_relationship failed" |
| R8 | `ledger_verify` repaired model | Verus | the old `theorem_temporal_marked_rows_left_out` / `theorem_adoption_closes_the_difference` cannot both stand unchanged once the two marker rules are separate inputs; a text-"true" temporal qualifier in the tables makes every verify diverge, whatever the history |
| R9 | `ledger_client` repaired model | Verus | `theorem_caller_transaction_holds_the_head` holds only with lock count +0 once the caller's transaction holds the counter row |

## Addendum (still before any native run)

R3.b needs an ObjectScript process holding the head lock without a transaction. The product's own lock test does this
through `scripts/dev/tcp_setup.py`, which loads helper classes into `%SYS` of the shared fixture; I will not do that.
A Native API `lock` is, per that test's note, not seen by ObjectScript's `Lock`; I will try it once and report R3.b as
"not observed" if it does not block. Added neighbour that needs no helper:

| ID | Case (changing input) | Reader | Predicted outcome |
|---|---|---|---|
| R3.d (**new**) | caller A, inside its open transaction, commits a changeset with a 5,000-character message (refused `inconsistent`, uncounted: the revision row save fails before the counter row is touched); process B then commits | B's exception and wall time; `rej_lock_timeout` from a third connection | A holds the head (the unlock inside its transaction is deferred) but not the counter row: B gets `LedgerLockTimeoutError` after about 30 s (not 40) and `rej_lock_timeout` +1 |
