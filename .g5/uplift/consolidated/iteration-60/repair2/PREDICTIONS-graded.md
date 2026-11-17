# Iteration 60 repair 2: predictions graded

Predictions: [PREDICTIONS.md](PREDICTIONS.md), committed at `9b7a66fa2` (table) and `d87a22595` (addendum), both before
the first native run (`observed-20261117T220625Z-setup.json`, 22:06:25Z). Exposure as stated there: S1 and S2 restate
the validator's published V3 observation (reproduction, not discovery); S3 to S6n and the model rows are this repair's
own questions, though the addendum was written after reading the deciding source.

Observations (local fixture `ivg-uplift-next-20261115`, identity `1a97b1515453` on every connection, 483 product files
byte-equal to `3eaa79cf`; namespace `I60SA`):
[s1 s2](probes/observed-20261117T220645Z-s1-s2.json), [s3 s3z s4 s6 s6n](probes/observed-20261117T220811Z-s3-s3z-s4-s6-s6n.json),
[s5](probes/observed-20261117T220854Z-s5.json), [s5r](probes/observed-20261117T220914Z-s5r.json). The binding repeated
S1, S2, S3, S3z, S6 and S6n as B21, B21n, B22, B22z, B23 and B23z in `I60SB`
([receipt](../../../../Verus_verification/results/ledger_client/20261117T225756Z-binding/receipt.json)) with the same outcomes.

| ID | Predicted | Observed | Grade |
|---|---|---|---|
| S1.a | A: `LedgerLockTimeoutError` ~30 s, `$TLEVEL` 1, `rej_lock_timeout` +0 | 30.1 s, `$TLEVEL` 1, +0 (hook `lock_timeout`) | held (reproduction) |
| S1.b | B: `LedgerInconsistencyError` "stats save failed / #5803 / LedgerStats" ~10 s; head unchanged; 0 rows; one `inconsistent` event; no counter | 10.2 s, exact message, head 1 → 1, 0 rows, `["inconsistent"]`, deltas {} | held (reproduction) |
| S1.c | after A's rollback B's retry: seq head+1, parent prior head, `commits_ok` +1, lock +0 | seq 2, parent = prior head, {commits_ok: 1} | held |
| S2 | no caller transaction: A 30 s and +1; B at once, seq head+1, `commits_ok` +1 | A 30.0 s, `$TLEVEL` 0, {rej_lock_timeout: 1}; B 0.0 s, seq 3, `["success"]` | held |
| S3 | strict, earlier write: A `LedgerStrictModeError`; strict +1 while open; B `inconsistent` ~10 s, nothing written; after rollback strict +0, B's retry commits | `$TLEVEL` 1 before and after; {rej_strict_block: 1} while open; B 10.1 s, 0 rows; after rollback {}; retry seq 4 | held (the open question "does the count run in the caller's process" answered yes, for an engine built on the caller's connection) |
| S3z | no earlier write: strict +1 kept; B commits at once | `$TLEVEL` 0; +1 kept after rollback; B 0.0 s, seq 5 | held |
| S4 | autocommit on: strict +1 kept; B at once | +1 kept; B 0.0 s, seq 6 | held |
| S6 | verify after an earlier write: B `inconsistent` ~10 s, nothing written; after rollback B commits | verify `equal`; B 10.1 s, 0 rows; retry seq 7. Also: A's rollback took back `last_verify_result` (`equal` → None) | held (+ one unpredicted side effect) |
| S6n | verify with nothing written: B at once | `$TLEVEL` 0; B 0.0 s, seq 8; `last_verify_result` kept | held |
| S5 | each `disable()`/`enable()` adopts (head +1) re-recording the `temporal` "true" qualifier; next verify still diverges with the same entries; a second cycle adds another adoption | cycle 1: adoption seq 10, cycle 2: seq 11 (head +1 each); records `create_rel` + `set_qual temporal "true"`; `diverges` / `unrecorded_writes`, same 2 entries after each; the `"yes"` neighbour gives no entry | held |
| M1 | the `!stats_free` refusal provable as is | `theorem_held_counter_row_refuses_a_valid_commit` verified with no proof hints | held |
| M2 | removing the `!stats_free` branch fails the new theorem | control `held-row-not-checked` EXPECTED_FAIL (4 theorems) | held |
| M3 | `txn_commit` counted a nested lock-timeout refusal; fix by deciding the row before the undo | `nested-refusal-counted` (the pre-fix definition) fails `theorem_nested_refusal_is_never_counted` and `theorem_nested_lock_timeout_keeps_the_counter_row` | held |

Score: 13 of 13 rows held. One observation was outside the predictions: verify's recorded result is part of the caller's
transaction and is taken back by its rollback (S6). It is recorded in bug-led-017's evidence, not registered separately.
