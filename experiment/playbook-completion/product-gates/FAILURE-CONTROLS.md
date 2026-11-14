<!-- markdownlint-disable MD013 -->

# 3.7-failure-controls: every failure scenario of the audit, its negative control and its registered run

Lane product-gates (steer 7, Q17e). Gate text: "failure scenarios each with a negative control" (playbook §3.7,
`experiment/playbook-uplift/verification-playbook.txt:351`; §4.3 :422 "liveness and recovery need real-environment
tests (crash, restore, failover) with negative controls"). Pin `3eaa79cf`, IRIS 2026.1 Community (Build 234U),
SynchCommit=0 (`env-synchcommit-setting`): every durability statement below holds for SynchCommit=0 only.

A **failure scenario** here is a fault injected into a real product operation on the dedicated container (a crash, a
lost reply, a disconnect, a stopped process, a held lock, a refused write, a retry after an unknown outcome, an
interrupted run). A **negative control** is a run in which the scenario's own oracle is given a seeded defect (in a
recorded observation, a mutated trace, a model mutant or a live state seeded through the product's API) and must
flag it. A scenario's result and its control are separate registered runs unless noted. Inventory method: a keyword
search of the 1,015 records in `evidence/runs/` at the time of writing (crash, kill, lost, disconnect, stop, timeout,
licence, rollback, refusal, retry, resume, interrupt, abort, journal), then each hit read; model-only results are
listed only where they are the control of a live scenario.

## Summary

| Count | |
| --- | --- |
| rows (failure scenarios) | 20 (S1-S18 and the sub-rows S4b, S5b) |
| a registered negative control existed before this lane | 8 (S2 trace-level, S7, S9, S10 model-level, S11, S12, S14 model-level, S18) |
| control added by this lane | 10 (S1 and S2: oracle self-tests registered; S3, S4, S5: new worlds with seeded and live controls; follow-up: S5b, S13, S15, S16, S17, each a live control with a precondition-absent arm that passes and a precondition-present arm that is flagged) |
| covered by another row's controlled oracle | 2 (S4b by S4; S8 by S3/S4) |
| still without a negative control | 0 |
| not runnable here | 1 (S6, licence refusal at product level: blocked-access) |

Verdict for the gate: **open** only for S6: every other scenario has a registered negative control (17) or is
covered by another row's controlled oracle (2); S6 (licence refusal at product level) cannot run on the shared
container and stays blocked until the orchestrator has the container exclusively.

Follow-up controls (S5b, S13, S15, S16, S17): `product-gates/fc_controls.py`, one live run per scenario in AUDITIA from
an empty state, each keeping its original run's oracle and applying it to an arm where the defect's precondition is
absent (the oracle must pass) and an arm where it is present (the oracle must flag); for S17, where the refusal is the
property, the oracle must pass over the limit and flag at the limit. Inventory recheck: `pg-failure-controls-r2`.

## Scenarios

| # | Scenario (fault, operation) | Oracle | Registered run (result) | Negative control (registered) | Status |
| --- | --- | --- | --- | --- | --- |
| S1 | Instance crash: container SIGKILL + restart during and right after a 36,000-operation ledger commit (`traces/crash_world.py`) | FR-047 all-or-nothing, head = revision rows, stmt/tuple bijection, verify equal, retry once, acknowledged commit survives | `live-crash-world-r2` (fail: the acknowledged commit is lost with SynchCommit=0, F-C1102 intent-undecided; consistency and exactly-once retry held); `live-crash-world-r1-invalid` (incomplete, harness error, `live-maxops-60000-refused`) | **`pg-fc-crash-oracle-selftest`** (added: 3 seeded observations rejected, unmutated accepted) | control present; one trial per world; SynchCommit=1 untested |
| S2 | Lost acknowledgement: client OS process SIGKILLed at 0.05-8 s into a ledger commit with an idempotency key (`traces/lost_ack.py`) | exactly one revision with the content, rows once, verify equal | `live-lost-ack-commit` (pass, 6/6); `corr-trace-lostack` (trace pass) | **`pg-fc-lost-ack-oracle-selftest`** (added: double-applied and missing-content observations rejected); trace check: `trace-conformance-controls`, `corr-abstraction-selftest-r3` | control present |
| S3 | Client disconnect at an exact wire message (`product-gates/disconnect_world.py`, TCP proxy framing the IRIS protocol): commit in a caller transaction with its COMMIT dropped (A1), staged commit with Commit dropped (A2), Commit cut in flight (A3), Commit reply held (B1), caller COMMIT reply held (B2), redaction reply held (C1), redaction cut in flight (C2), bounded redaction with the third call dropped (C3), EraseGraph reply held (D1), erasure in a caller transaction with COMMIT dropped (D2), EraseGraph cut in flight (D3) | O1 full step or nothing; O2 journal: every transaction of the dead server process committed or fully undone; O3 head lock free; O4 same-key retry returns the first answer (spec 213, `contracts/ledger-api.md:26`) or commits once; O5 verify equal; O6 exactly once | `pg-disconnect-commit` (15 trials), `pg-disconnect-redact` (9), `pg-disconnect-erase` (9), 3 baselines; all pass, 0 violations (`pg-disconnect-reevaluate`; DISCONNECT.md) | **`pg-disconnect-selftest`** (164/164 seeded observations flagged over 17 points) and **`pg-disconnect-live-controls`** (4/4 defects seeded through the product's API caught) | control present (new world) |
| S4 | Server process stop mid-operation: the client's IRIS process terminated by pid (`%SYSTEM.Process.Terminate`) inside a commit (T1), during a redaction's read-only pre-pass (T2), between a redaction's batch transactions (T2b), inside an erase (T3) | as S3 | `pg-disconnect-stop` (9 trials: T1 and T3 undone, T2 nothing written yet), `pg-disconnect-stop-midbatch` (3 trials: 553-679 whole batches committed, marker held, re-run completes); all pass | `pg-disconnect-selftest` (T points), `pg-disconnect-live-controls` | control present (new) |
| S4b | The original submission's server-side stops: `killed_mid_batch`, `killed_at_random`, `paused_and_resumed`, `disabled_mid_run` (`experiment/playbook-uplift/native/scenarios.py:421-540, 789`) | the submission's 177 checks | `live-native-rerun-1314` (pass) | none rerun: the original controls (`native/mutants.py`) compile mutated classes, out of scope (CONVENTIONS "Scope control"); the same failure is covered with controls by S4 | covered by S4 |
| S5 | Lock timeout: another live process holds `^IVG.Ledger("head")` longer than LOCKTIMEOUT (30 s, `Ledger.cls:21`) during a commit (L1) and a redaction batch (L2) | as S3 plus O7: refused with the documented lock-timeout error (`contracts/ledger-api.md:26` lists `LedgerLockTimeoutError`) | `pg-disconnect-locktimeout` (4 trials: refused after 31.0 s with `LedgerLockTimeoutError`, nothing applied, only the rejection counter written; retries complete); pass | `pg-disconnect-selftest` (L points, incl. "refusal missing") | control present (new) |
| S5b | Stats row lock held 20 s by a caller transaction (F-1102) | the rejection counter is written (moves by exactly one) | `b-11-live-f1102-locktimeout` (fail) | **`pg-fc-s5b-control`** (added, follow-up): stats row free, the counter moves 0 -> 1 (passes); row held 15 s by a caller transaction's nested commit, the bump waits 10.0 s, returns a lock error and moves the counter by 0 (flagged) | control present |
| S6 | Licence refusal (the Community licence's 8 units exhausted) | infrastructure rule: a refusal is rerun, never a product result; `tools/iris_conn.py` identity probe turns a refused connection into an error | none at product level | the identity probe (not a registered control) | **blocked-access**: a product-level run (a connection refused in the middle of an operation) needs exclusive use of the container's 8 licence units, which all lanes share; exhausting them on purpose fails other lanes' runs (operator) |
| S7 | A failing write inside a caller transaction (nested rollback): BM25 insert (F-C0702); ledger admin calls in a caller transaction (HD-1102) | the caller's earlier work survives | `b-07-fc0702-nested-rollback` (fail), `ib-HD1102-txn-rollback` (expected-violation) | in-run control in `b-07-fc0702-nested-rollback` (a valid insert keeps the caller's row); model: `proofs-d1d-fc0702-bare-trollback`, `b-mc-m08-txn-control-rollback-all` | control present |
| S8 | A refused delete during an erasure (FK -124 from a concurrent commit) rolls the whole erase back | ERS-I1 all or nothing | `live-erase-vs-commit-fk` (pass 8/8) | none for that run; the all-or-nothing oracle for erasure is controlled in S3/S4 (D2, T3 seeded "partial-after-kill") | covered by S3/S4 |
| S9 | Erasure racing a ledger commit (F-1201) | journal order; statement entry of the committed edge | `live-f1201-reproduced` (fail 8/8), `corr-trace-f1201` (trace fail) | `trace-conformance-controls`; model and proof controls `core-m2-as-built-F1201-stmt`, `core-proofs-f1201-erase-unlocked`, `proofs-d9-f1201-erase-unlocked` | control present |
| S10 | Erasure rolled back after a redaction completed against it (F-C1201) | content live and history tombstoned | `ib-HD1201-open-erasure` (fail) | model: `core-m2-as-built-P1311-erase-rollback`, `core-m2-sharp-erase-rollback` | control present (model-level) |
| S11 | Interrupted bounded redaction resumed (F-C1303) | the run finishes | `live-fc1303-bounded-resume` (fail) | in-run control (the same world with max_batches 0 completes); model `core-m2-as-built-paced-resume`; here C3 (resume unbounded completes) | control present |
| S12 | Retry after an unknown outcome over HTTP: client resend (F-C1703), server re-run (F-C1604) | at most once | `c17-live-server` (fail), `c16-s4-server-retry` (fail), `ib-HD1603-server-retry`, `ib-HD1702-client-retry` | `cmc-retry-ctl-client`, `cmc-retry-ctl-server`, `proofs-d1f-fc1703-client-resends-write`; in-run control in `c16-s4-server-retry` (no fault: applied once) | control present |
| S13 | A writer keeps a redaction open (F-C1307) | after an interrupted bounded run, the documented recovery (run again) releases the marker; other tenants' readers work; verify equal | `fu-r03-marker-held-open` (fail) | **`pg-fc-s13-control`** (added, follow-up): no writer on the target, the re-run completes and releases the marker (passes); a bypass `create_node` into the target, the re-run is refused `RedactionTargetLiveError`, the marker stays, another tenant's revision is refused, verify `redaction_in_progress` (flagged) | control present |
| S14 | Strict-mode guard: stale cache or failing probe lets a write through (F-0801) | no unrecorded write under strict mode | `b-08-live-f0801`, `b-08-live-f0801-rerun`, `intent-a-hd0801-strict-cypher-window` (fail); `intent-a-hd0801-unit-ledger-guard` (run pass: `test_probe_failure_fails_open`) | `proofs-breadth-f0801-fail-open`, `proofs-breadth-f0801-ttl-cache`, `proofs-d1d-f0801-*` (model) | control present (model-level) |
| S15 | A rolled-back Cypher edge write leaves `^NKG` counters raised (F-C0801) | `^NKG(-3,src)` and edgeCount move with the edge rows, or `^NKG` is marked stale | `b-08-live-fc0801-rollback-nkg`, `-rerun` (fail) | **`pg-fc-s15-control`** (added, follow-up): the write query commits, counters and rows both +1 (passes); the query rolls back (its second statement failed; here with the driver's `<PARAMETER ERROR>`, F-C1706), rows unchanged, counters +1, no stale mark (flagged) | control present |
| S16 | Client killed inside a bulk-load chunk (F-0305) | one `bulk_create_nodes` call is all or nothing | `breadth-a-live-03-bulk-killed-client` (fail: chunk 1 stayed committed) | **`pg-fc-s16-control`** (added, follow-up): server-loader path not killed, 2,000 nodes / 2,000 props / 1,000 labels (passes); batch-SQL path killed while waiting, nothing left (passes); server-loader path killed while chunk 2 waits on a table lock, chunk 1 stays (1,000 / 1,000 / 0, flagged) | control present |
| S17 | Oversized changeset refused before applying anything (max_ops) | refused with `ChangesetTooLargeError`, nothing applied, head unchanged | `live-maxops-60000-refused` (probe pass) | **`pg-fc-s17-control`** (added, follow-up): 50,001 operations refused in 0.14 s with nothing applied (passes); 50,000 operations, the limit itself, committed (flagged): the oracle is not vacuous and the boundary is exactly 50,000 | control present |
| S18 | Randomized schedules through the real product with invariants after every commit (simulator) | 13 invariants | `sim-main-20261114`, `sim-race-20261114` | `sim-oracle-selftest` (13/13 injected violations caught) | control present |

## What this lane observed about failures (from S3-S5; counts in DISCONNECT.md)

- A client disconnect never interrupts a server call that is running: the server process runs the call to its end
  (commit, every redaction batch, the erase and its DDL) and exits when it next reads or writes the closed socket.
  So a disconnect leaves either the whole call or, when the call never arrived (A2) or the caller's COMMIT never
  arrived (A1, D2), nothing: IRIS rolls back the dead process's open transaction (P-0001). The rollback is journaled
  as compensating records inside the transaction's span, and nothing but the documented non-transactional counters
  survives it.
- Only a stopped server process interrupts an operation (S4): its open transaction is undone and every committed
  redaction batch is whole; the re-run finishes.
- A revision a client sees inside its own transaction (A1: `ledger.commit` answered a seq and an id before the COMMIT
  was lost) is provisional: after the rollback a retry commits the same content as a new revision with the same seq
  and a different revision id. This follows the documented caller-transaction contract, not a defect, but a client that logged the provisional id holds an id no revision has (docs/USER_GUIDE.md:260-265 says a
rollback removes the revision; it does not say the seq is reused).
