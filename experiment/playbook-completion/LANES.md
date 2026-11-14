# Lane checkpoint (orchestrator; read by the hourly monitor)

Updated: 2026-11-14 ~20:15 UTC (after the 19:20 quota reset; same account).
previous account is live: `ListAgents` empty, no audit process running, IRIS and heavy locks free, container healthy,
product scope check passes). Last checkpoint commit before the switch: `1564a673`.

## State of every lane (16:35 UTC)

| Lane | State | Output (stable paths) | Next |
|---|---|---|---|
| writesets (census, breadth-a, R4) | done (728e18a1) | `writesets/` | — |
| structural (incl. frame2/reads2, suspected defects) | done (a6892eb4) | `structural/` | — |
| trace-replay (incl. module 09) | done (eb492c1c) | `trace-replay/` | — |
| refusals (incl. least-privilege follow-up) | done (95abaf5f) | `refusals/`, `versions/PRIVILEGE.md` | — |
| product-gates (lint, style all modules, disconnect, failure controls) | done (d7595869) | `product-gates/` | S6 licence-refusal run (orchestrator, exclusive container) |
| semantics r4 | done (956bdcfd) | `semantics/`, `models/semantics/` | — |
| proofs-mech (D-14) | done (e9041b19): 1,149 verified, 120 controls, recheck | `proofs-mech/` | — |
| reflection (Q18e) | **done** (3d75a633) | `reflection/` (ROOT-CAUSES, premise map by glob, TEST-REFLECTION, CLOSURE.md, MATRIX-INPUT.json) | integrate: copy `reflection/MATRIX-INPUT.json` to `matrix-input/reflection.json`, add its errata texts to `evidence/errata.json`, `python3 matrix/build_matrix.py`, commit |
| orchestrator: crash world, SynchCommit=0, 3+3 trials (Q18f) | **done**: `live-crash-repeat-sc0` (fail: 3/3 in-flight all-or-nothing; 3/3 acknowledged commits lost; retries clean) | `$RUN_DIR/crash-repeat/sc0/{run.log,results.json,summary.json}`; pre-state `$RUN_DIR/crash-repeat/pre-sc0.txt`; an earlier refused attempt (wrong config class, nothing ran) kept in `$RUN_DIR/crash-repeat/sc0-refused-wrong-config-class/` | register: `python tools/register_run.py live-crash-repeat-sc0 live <pass if every in-flight trial is all-or-nothing and every retry clean, else fail> $RUN_DIR/crash-repeat/sc0/run.log --lane orchestrator --command '...' --observes '<from summary.json>'` |
| orchestrator: crash world, SynchCommit=1 | **done**: `live-crash-repeat-sc1` (0/3 acknowledged lost; SynchCommit=0 restored, healthy) | `$RUN_DIR/crash-repeat/` | — |
| (old row) crash world, SynchCommit=1 | **running** since ~16:45 UTC: `bash tools/locks.sh iris timeout 7000 bash $RUN_DIR/crash-repeat/sc1-procedure.sh` (log `$RUN_DIR/crash-repeat/sc1-procedure.log`; it restores SynchCommit=0 itself) | `$RUN_DIR/crash-repeat/sc1/` | (1) `docker exec -i $IVG_TEST_CONTAINER iris session IRIS -U %SYS < $RUN_DIR/crash-repeat/set-synchcommit-1.script` under `tools/locks.sh iris`; (2) `docker restart $IVG_TEST_CONTAINER`, wait healthy; (3) `bash tools/locks.sh iris timeout 5400 python traces/crash_world_repeat.py $RUN_DIR/crash-repeat/sc1 --trials 3 --expect-synchcommit 1`; (4) restore with `set-synchcommit-0.script`, restart, confirm `iris.cpf` line `SynchCommit=0` and Docker healthy; record in `incidents/` (alerts from the deliberate crashes are expected; preserve them, do not clear) |
| orchestrator: S6 licence refusal | **done**: `live-licence-world` (F-C1795) | — | design: hold idle connections up to the 8-unit cap, then drive a product operation that needs a new connection; record refusal handling and that nothing partial is written |
| orchestrator: account and closure | STATUS/PROOF-DEBT/TRUST refreshed (1dff8e3c); operator clean gate on a42f10c8 failed 9 proof readers (fixed 6238aaaa, kept as `verify-clean-a42f10c8`); **next**: integrate the structural follow-up, commit a candidate, `bash verify.sh --live --clean` (~80 min), fifth review | — | STATUS rewrite with `python tools/status_numbers.py --write`; TRUST/PROOF-DEBT; `bash verify.sh --live --clean` on a committed tree (expect ~60 min: proofs-mech alone ~36 min); fifth independent review with the O-1 clarification (`incidents/O-1-FIXTURES.md`) |

| structural final follow-up | **running** (resumed ~20:00 UTC): 3.6-capacity/01 via the O-1 4.5.1 fixture, declared reads 04/10, bulk_load_session pair | `structural/MATRIX-INPUT-3.json` | integrate |

## Blockers

- Not operator-dependent (recorded so the monitor does not count it): the least-privilege login; the disposable user `IVGAUDIT_RO` is authorized setup (versions/PRIVILEGE.md).
- Operator-dependent: O-2 (product-code mutation testing, `3.7-mutation`; the binding rule says model mutations only).
  O-1 is resolved by the operator's clarification.
- Genuinely unavailable (attempts in `versions/AVAILABILITY.md`): IRIS 2026.3, Enterprise / IRIS for Health and its
  licence (more than 8 units), `%AI`, `HS.FHIRServer`, multi-node, x86_64 `libarno_callout.so`.
- No verifier for ObjectScript/Python (D-2, D-3): statement and handler proof cells stay open.

## Provenance note (operator check after the switch)

The operator checked 1,237 primary log records: 1,231 current digests match; the 6 proof logs overwritten earlier
(`incidents/superseded-logs.json`) have explicitly superseding reruns whose digests match. Those 6 stay superseded,
never relabelled as original matches (TRUST.md, "Log provenance").
