# System semantics of the worked example (playbook §3.3a)

Scope: graph erasure → ledger redaction → replay, at product pin `3eaa79cf`. The order follows §3.3a: axioms, mechanisms,
lifecycles, the domain contract, then invariants with write-set obligations (generated: `WRITESETS.md`).

## 1. Universal axioms

The ten system-level rules are statements `SYS-I1`…`SYS-I10` in `ontology/00-system.md`. The slice uses them as follows.

| Axiom | Rule | In this slice |
|---|---|---|
| U1 `SYS-I1` | One owner per kind of fact | Records, markers and retry bindings are written by `Graph.KG.Ledger` and `Graph.KG.LedgerRedact` only; content rows by many paths (the ledger, the engine, Cypher, bulk loads, restores), which is why `INV-stmt` and `INV-replay` have many write plans. |
| U2 `SYS-I2` | No graph's content in another graph's answer | Redaction targets are graph-scoped, but ledger node records are graph-blind (F-1304, F-1305). |
| U3 `SYS-I3` | A refusal changes nothing | Every redaction refusal returns before its first write, or rolls back its batch; checked live with whole-store snapshots. |
| U4 `SYS-I4` | Several stores change together or not at all | Erasure: one transaction (DDL after commit is the named exception). Redaction: one transaction per batch; between batches the marker stands for "half done". |
| U5 `SYS-I5` | History only grows; a record changes only into a tombstone | Proved for the reviewed L2 (`shape_ok`); `PurgeAll` and a replacing restore (F-1801) are outside it. |
| U6 `SYS-I6` | A retry gets the first answer or a clear refusal | `idemRedacted` refuses retries of redacted revisions (proved, live); a replayed retry re-applies post-commit properties (F-1306). |
| U7 `SYS-I7` | A governed change and its record share a transaction | Holds for ledger commits; post-commit properties are outside by design. |
| U8 `SYS-I8` | A derived store matches or says it is stale | The redaction marker plays this role for readers; readers check it before reading only (F-1402). |
| U9 `SYS-I9` | Every refusal says why | `target_live`, `redaction_in_progress`, `idempotency_redacted`, `disabled`, `invalid_target`, `transaction_open`. |
| U10 `SYS-I10` | One install per namespace | One ledger per namespace; a tenant that needs its own ledger needs its own namespace (ADR-0016). |

## 2. Shared mechanisms

Each mechanism is one piece of machinery that several commands rely on. "Laws" are the L1 rules it must keep; "proved"
names the Verus statement in `proofs/src`; "deviates" names where the code at the pin does not follow the reviewed design.

| Mechanism | State | Operations | Laws | Proved / checked | Deviates at the pin |
|---|---|---|---|---|---|
| **Head lock** (`^IVG.Ledger("head")`) | holder | Commit, every redaction batch, Final | Steps that change records are serial | Modelled as atomic L2 steps; P-0003 observed live | Erasure and readers do not take it (F-1201, F-1402) |
| **Transaction** | open writes | TSTART/TCOMMIT/TROLLBACK | A stopped process leaves no partial step | P-0001, P-0004 live; `killed_mid_batch`, `killed_at_random` live | — |
| **Retry key** (`idem`, `idemRedacted`) | unused → bound → redacted | Commit, Redact (first tombstone) | At most one save per key; a redacted key never saves or replays | `theorem_retry_refused`, `keys_ok`; live `retries` | Post-commit properties re-applied on replay (F-1306) |
| **Redaction marker** (`redacting`) | none / target t | Start (reviewed) or first tombstone (pin), Final | While t is marked: no live record of t in the abstraction, no commit into t, no other target starts | `marker_ok`, `theorem_l2_satisfies_l1`; mc `redaction-reviewed` | Set late (F-1302); not exclusive between targets (F-1303) |
| **Tombstone** | content → tombstone | Batch | Keeps place and op; digest = sha256(canonical record); never back | `shape_ok`, `tombs_ok`, `theorem_isolation`; live digest recomputation | — |
| **Liveness check** | — | Start, Final | Redaction runs only on an empty target | `theorem_begin_spares_live` (reviewed) | Unlocked at Start (F-1302); default graph without prefix looks in one graph only (F-1304) |
| **Audit revision** | — | Final | One per finished redaction that changed something; counts only its own target | Live `mixed_tenant_flow` | Counters shared between targets (F-1303) |

## 3. Canonical lifecycles

- **Redaction target** (module RED cells): live → erased → redacting → redacted; "redacted" returns to live only through a new
  recorded commit (re-onboarding). A refused Final keeps it in redacting until it is erased again (RED-B8.2).
- **Record**: content → tombstone. No transition back. An audit record is born content-free.
- **Revision free text**: present → cleared (on the revision's first tombstone; Decision 2).
- **Retry key**: unused → bound → redacted. No transition back.
- **Redaction run**: running ↔ stopped (process stop, `max_batches`, disabled ledger) → finished, or stuck on a live target.
  Progress: an uninterrupted run takes at most `rank0` steps (`theorem_run_bounded`); premises P-1306 and P-1307.

## 4. Domain contract: replay equals the store

The central contract of the ledger is that the fold of the committed records (replay) equals the governed content of the
store. Proved in `proofs/src/model.rs` and `l1.rs`, for every history and every separable target (P-1301) whose erasure,
liveness check and record match cover the same entities (P-1310; at the pin they differ in F-1304 and F-1305):

- `theorem_commit_keeps_except` / `theorem_commit_between`: commits outside a target keep agreement outside it;
- `theorem_erasure_alone_diverges`: erasing live content breaks agreement;
- `lemma_replay_tomb`, `theorem_redaction_restores`: tombstoning the target's records restores it;
- `theorem_audit_changes_nothing`: the audit revision changes no replay;
- `theorem_erase_then_redact`: from agreement, erase then redact gives agreement again.

Outside the contract by design: unrecorded writes (classified by verify), the temporal index and vectors (verify does not
compare them, RPL-B2.1), and node identity across graphs (F-1401).

## 5. Invariants and write-set obligations

`writesets.json` declares the stored facts, every write plan found in the code (ledger commit, genesis, adoption, purge,
the three redaction steps, the three erasure entry points, direct engine writes and deletes, Cypher writes, post-commit
properties and a replacing snapshot restore) and the eight invariants with their read sets. `tools/writesets.py`
generates every (invariant, plan) pair whose write set meets the read set and requires a discharge for each; the result
is `WRITESETS.md`. A pair discharged only by a finding is listed as open.
