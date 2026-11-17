# Iteration 60 repair 2: predictions frozen before any native run

Written 2026-11-17 about 22:00Z by the repair-2 builder, before any probe of this repair ran, before the model, owner
or register changed, and before I read `guard.py`, `client.py` (`commit`, `enable`, `write_txn`) or `Ledger.cls` /
`LedgerStats.cls` at the pin. Committed on its own as a checkpoint so its digest precedes every observation.

**Exposure (disclosed).** Not independent. I read first: the validation `$G5_RUN_STATE/review-60v/VALIDATION.md`, its
predictions, its probe `v60_probe.py` and its V3 observation `observed-20261117T215306Z-v3.json` (published round-1
feedback, exposed); the repair's `DISPOSITIONS.md`; and the `ledger_client` model (`server`, `refuse`, `txn_commit`,
`txn_rollback`, `count_strict`), which transcribes the deciding source. Rows S1 and S2 restate the validator's
observation and are graded as reproduction, not discovery. S3/S4 (strict mode) and S5 (re-enable) are this repair's
own questions; their predictions come from the model and the validator's inference, not from reading the code.

Fixture: local `ivg-uplift-next-20261115` (127.0.0.1:35975). This repair's own namespace `I60SA`, created additively
from `%SYS` with `CREATE DATABASE`, deployed with `initialize_schema()`, ledger enabled with defaults. IDs start with
`i60s_`. Nothing written to USER, `I60L*`, `I60R*`, `R60*` or `V60L`.

Connections: A = the caller (its transaction is the subject), B = another writer (autocommit), X = a Native API
connection holding `^IVG.Ledger("head")` with a plain lock, R = a fresh third connection reading `Graph_KG.ledger_stats`
for every counter value.

| ID | Case (changing input or history) | Reader | Predicted outcome |
|---|---|---|---|
| S1.a | X locks the head; A (autocommit off) commits a fresh node | A's exception, wall time, `$TLEVEL`; R's counters | `LedgerLockTimeoutError` after about 30 s; A's `$TLEVEL` 1; `rej_lock_timeout` **+0** (A's own refusal is not counted: the client's transaction wrapper undoes the level that holds the Bump) |
| S1.b | X unlocks; B commits a fresh node while A's transaction is still open | B's exception and wall time; head; B's node rows; B's hook events; R's counters | `LedgerInconsistencyError` whose message names `stats save failed` / `#5803` / `LedgerStats` after about 10 s; head unchanged; 0 node rows; one hook event `inconsistent`; no counter moves |
| S1.c | A rolls back; B retries the same changeset | B's result; R's counters | commits with seq = head + 1, parent = the prior head; `commits_ok` +1; `rej_lock_timeout` still +0 against the start |
| S2 (valid neighbour) | the same, except A runs with autocommit on (no caller transaction): X locks, A commits and times out, X unlocks, B commits | A's exception and count; B's result and wall time | A: `LedgerLockTimeoutError` after about 30 s and `rej_lock_timeout` +1 (the row is free and A holds nothing afterwards); B commits at once (well under 10 s) with seq = head + 1 and `commits_ok` +1 |
| S3 (reachability) | strict mode on; A (autocommit off) attempts a direct, non-ledger write that the strict guard refuses; B then commits while A's transaction is open | A's exception; R's `rej_strict_block`; B's result and wall time | A is refused by the strict guard; **if** the guard's count runs on A's connection inside A's transaction (the validator's open question): `rej_strict_block` +1 visible to R while A is open, B gets `LedgerInconsistencyError` (`stats save failed`) after about 10 s, and after A's rollback `rej_strict_block` is back to its start (+0). If the count runs elsewhere (own connection or autocommit), B commits at once and the count stays +1. I lean to the first (count on the engine's own connection), confidence low |
| S4 (S3's neighbour) | strict mode on; A with autocommit on attempts the same refused direct write; B commits | same | A refused; `rej_strict_block` +1 and it stays; B commits at once |
| S5 (bug-led-013 re-enable clause) | a relationship committed with qualifier `temporal="true"` exists; `disable()` then `enable()` | `enable()`'s return; head; the adoption revision's records; the next `verify()` | `enable()` after `disable()` adopts: head +1 with an adoption revision that records the relationship's `temporal` "true" qualifier again; the next `verify()` still `diverges` with the same entries for that relationship; a second `disable()`/`enable()` cycle adds another adoption revision |

Model-side predictions (before the edit):

| ID | Claim | Predicted |
|---|---|---|
| M1 | `server` with `!stats_free(s, q)`, everything else admitting | `Inconsistent`, `same_ledger`, `cnt` unchanged, one `Refused(Inconsistent)` event: provable as is (the branch exists; no theorem names it yet) |
| M2 | a control that deletes the `!stats_free` branch (the write goes ahead) | the new theorem fails |
| M3 | current `txn_commit` on a nested lock-timeout refusal with the counter row free | `took_row` is true (the model counts the refusal and holds the row with the count); after the repair the count is undone (`cnt` back) while the row stays held, so `took_row` must be decided by "a counted outcome or a nested refusal whose Bump ran", not by the counter value |
