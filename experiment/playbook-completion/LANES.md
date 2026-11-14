# Lane checkpoint (orchestrator; read by the hourly monitor)

Updated: 2026-11-14, steer 9 (writesets done; proofs-mech, refusals, structural, style and 09 replay running). First written ~14:50 UTC, after the account switch (session resumed on the new account; no subagent of the
previous account is live: `ListAgents` empty, no audit process running, IRIS and heavy locks free, container healthy,
product scope check passes). Last checkpoint commit before the switch: `1564a673`.

## State of every lane

| Lane | Queue | State | Artifacts | Next |
|---|---|---|---|---|
| proofs-mech (D-14, mechanism laws over a trait in Verus) | Q18b | **interrupted** (quota) during fork integration | `proofs-mech/src` (m01/m02/m05/m11/m12/m13 traits, i*/ctl*/cx* instances and controls), forks in `$RUN_DIR/proofs-mech/fork-a..e`; no runner, no registered run | resume from the artifacts: assemble, add the gate runner, run baseline/controls/recheck |
| refusals (5c-refusals, 3.5-decoders 07/10/18) | Q18c | **interrupted** (quota) mid live probes | `refusals/` extraction (`x-statements.json`), `rx_audit.py`, `live_*.py` per module, decoder checks; no registered run | resume: run the per-module probes under the IRIS lock (AUDITE), register, write REFUSALS.md |
| writesets breadth-a pairs | Q18d | **done** (728e18a1) | 561 of 566 pairs discharged, 5 open; F-C0350, F-C0351; ws-check-r3, selftest 45/45 | — |
| structural frame2 / reads2 (DDL frame oracle; declared reads) | Q18c-d | **done** (a6892eb4) | 3.6-frame 13 more closed (07, 09, 15 open); 3.4-declared-reads 6 more closed (04, 10 open); no new findings | — |
| reflection | Q18e | waiting for the lanes above | — | classify every new finding; premise map by glob; TEST-REFLECTION refresh |
| product-gates: style for all modules | — | **running** (steer 9) | `product-gates/STYLE.md` | 3.5-style for 00-10, 15-18 |
| trace-replay: module 09 | — | **done** (eb492c1c) | 3.7-trace-replay/09 and 3.7-lock-log/09 closed; F-0903 reproduced; 7 generated classes recorded and dropped | — |
| orchestrator: O-1 | — | **done** (this checkpoint) | `incidents/O-1-FIXTURES.md`, run `o1-fixture-inventory`, CONVENTIONS updated, F-C1306 attribution | give the clarification to the next reviewer |
| orchestrator: exclusive-container worlds | Q18f | todo | `traces/crash_world_repeat.py` (not run) | repeated crash trials, SynchCommit=1, licence refusal S6, when no lane uses IRIS |
| orchestrator: account, clean verify, review 5 | Q18g | todo | — | STATUS/TRUST/PROOF-DEBT refresh; `verify.sh --live --clean` on a committed candidate; fifth independent review |

## Blockers

- Operator-dependent: O-2 (product-code mutation testing, `3.7-mutation`; the binding rule says model mutations only).
  O-1 is resolved by the operator's clarification.
- Genuinely unavailable (attempts in `versions/AVAILABILITY.md`): IRIS 2026.3, Enterprise / IRIS for Health and its
  licence (more than 8 units), `%AI`, `HS.FHIRServer`, multi-node, x86_64 `libarno_callout.so`.
- No verifier for ObjectScript/Python (D-2, D-3): statement and handler proof cells stay open.

## Provenance note (operator check after the switch)

The operator checked 1,237 primary log records: 1,231 current digests match; the 6 proof logs overwritten earlier
(`incidents/superseded-logs.json`) have explicitly superseding reruns whose digests match. Those 6 stay superseded,
never relabelled as original matches (TRUST.md, "Log provenance").
