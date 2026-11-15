# Randomized simulator through the real product (playbook §5c, gate 5c-reviewers)

Observation only. The product (pin `3eaa79cf`, tree `b098a6f4`) is unchanged and nothing is compiled into IRIS: the
pin's classes in namespace `AUDITA` came from its own `initialize_schema()`. The simulator drives the pin's public Python
API from separate OS processes and judges the outcome with an oracle that never calls the product. Product defects
are recorded (`findings.json`), never fixed. Every IRIS use ran under `tools/locks.sh iris`, in holds of at most
nine minutes with a 30 s pause between holds, with at most six connections open at once.

## Result

**304 schedules, 16,051 operations, 13,282 committed transactions checked, 52.9 minutes of simulated work** (summed
phase time; nine lock holds, the longest 9.3 minutes). Every invariant was checked after every committed transaction
of every schedule, and the replayed state equalled the engine's final state in 304 of 304 schedules. The product
violates five known findings and one new one, **F-CS01**. The oracle rejected all 13 injected violations.

| Run (registry id) | What | Result |
|---|---|---|
| `sim-main-20261114` | 204 general random schedules, seeds 1000-1203 | fail (product violations, below) |
| `sim-race-20261114` | 100 race-template schedules, seeds 2000-2099 | fail (product violations, below) |
| `sim-oracle-selftest` | 13 injected violations in recorded real traces, 40 unmutated baselines | pass (13/13 rejected) |
| `sim-fcs01-ddmin-s1033` | seed 1033 shrunk through the product (41 candidate runs) | 7 operations, one worker |
| `sim-fcs01-minimal` | hand-reduced 6-operation schedule (`fcs01-minimal-plan.json`), 3 runs | reproduced 3/3 |

Coverage: 2,345 erasures (`delete_nodes_by_prefix`, `erase_graph`), 2,456 redaction calls (473 bounded calls
completed, 262 bounded calls left the run open), 7,729 commits (5,484 accepted, 374 of them same-key replays; 99 refused because a redaction of their target was in progress), 1,200
ledger-bypassing writes, 1,008 `verify()`, 777 `reconstruct()`, 536 probe holds of `^IVG.Ledger("head")` or
`^IVG.AdjW(graph)`, 82 terminations of a worker's IRIS process (56 mid-operation; 26 landed between operations),
2-4 workers per schedule (77 / 189 / 38), all tenant mixes, both tenant shapes.

**Violations by invariant and finding** (counted once each, at the transaction that introduced it; `results.json`
has per-schedule examples):

| Invariant | Finding | Violations | Schedules | What the oracle saw |
|---|---|---|---|---|
| I8 IDEM (replay writes content) | F-1101 | 46 | 40 (with F-1306) | a same-key retry answered `replayed=True` and its transaction rewrote the post-commit property rows |
| I8 IDEM (replay revives erased content) | F-1306 | 44 | | the same, onto a node the tenant's erasure had removed: an orphan property row is live again |
| I3 RED-B1.1 | F-1302 | 10 | 4 | a commit re-created a tenant node after the redaction's unlocked liveness check and before its first batch set the marker; the batch tombstoned that node's history while it was live (e.g. seed 1077: commit at journal 336881980, tombstones at 336884208) |
| I4 MARKER / I5 AUDIT | F-1303 | 4 + 1 | 1 | seed 1226: beta's batches tombstoned under gamma_g's marker; gamma_g's Final wrote counts {2:4, 3:2, 4:6, 6:4, 8:2, 10:2, 13:2} against its own tombstones {3:2, 10:2, 13:2} |
| I2b STMT-ROW | F-0303 | 6 (2 transient) | 6 | a direct `delete_edge` of a recorded edge left its statement live |
| I2b STMT-ROW, transient | F-1114 | 2 | 2 | two concurrent erasures (seed 1006), and a commit's `delete_relationship` racing an erasure (seed 2051), each read the other's uncommitted kill of `^IVG.Ledger("stmt")`: in commit order a statement was live without its row until the eraser committed |
| I6 SC-001 | **F-CS01 (new)** | 9 | 9 | after erase and complete redaction, a zero-record revision of the tenant keeps its message, source, correlation id, idempotency key and `^IVG.Ledger("idem")` binding |

**No violation** in 304 schedules of: I1 stmt/tuple bijection, I2 ERS-I3, I3b RED-I1 (tombstones outside the target),
I7 `verify()` (708 quiescent points: 568 diverges / 60 equal / 80 redaction_in_progress, all as the oracle's replay
expected), I9 readers (683 `reconstruct()` answers, each equal to a committed point of its interval), I10 (every
refused commit, erasure or direct write committed nothing, including the 18 erasures refused under concurrency
with SQLCODE -124 / -110 and "nothing was erased"), I11, ADJ (no edge row without `^KG("out")`).

**Liveness observations** (expected effects of known findings, not invariant violations): 32 schedules ended with a
redaction marker set: in 29 the last call was bounded and incomplete (F-C1303: 65 bounded calls had tombstoned
nothing yet because each call rescans from the first record), in 3 the last call was refused `target_live` with the
marker held (F-C1307). While markers were set, 191 redaction calls of other targets and 94 `reconstruct()`
calls were refused `RedactionInProgressError` and 80 quiescent `verify()` answered `redaction_in_progress` (F-C1307).

**Known findings in scope that were not hit:** F-1201 (the erase-vs-commit template pre-populates the graph; with an
edge in it the race makes the erasure fail and roll back, as `traces/f1201_native.py` notes; it showed here as the 15
SQLCODE -124 refusals), F-1402 (no torn reader in 683 answers), F-C1202, F-1304/F-1305 (the generator always prefixes
ids; the documented two-target recipe was used for the graph tenant). Not hit means not reached by these
schedules, not that the finding is refuted.

### F-CS01 (new): a revision that recorded nothing survives the tenant's redaction

A changeset whose operations are all no-ops (FR-009c: upsert of an existing node, `add_label` of a present label,
`set_property` with the current value) commits a revision with `op_count` 0 but the full metadata and an idempotency
binding (Ledger.cls:491-492 counts operations, not records; :523-525). Redaction clears metadata and unbinds the key on
a revision's first tombstone only (LedgerRedact.cls:332-347, plan.md:25), and such a revision has no record to
tombstone. Minimal schedule (one worker, `fcs01-minimal-plan.json`): create `acme|n1` with label Person; upsert
`acme|n1` + add label Person (key `acme-k-min-2`, 0 records); `delete_nodes_by_prefix("acme|")`;
`redact(None, prefix="acme")` -> complete, `verify()` equal. Revision 3 still holds `acme commit min-2`,
`{"tenant":"acme"}`, `acme-corr-0`, `acme-k-min-2`; the key is still bound, and a retry with it after the redaction is
replayed (seq 3) instead of refused. Severity S2 (operator metadata, not recorded content; S1-class where metadata
names the tenant), confidence high. Record: `findings.json`.

## What runs

| File | Role |
|---|---|
| `schedule.py` | seeded schedule generator (pure). Seeds below 2000: the general generator; seeds 2000 and up: race templates |
| `worker.py` | one OS process, one IRIS connection (`tools/iris_conn.Conn("AUDITA")`), runs its list of operations |
| `sim.py` | driver: reset, phases, probe, kills, quiescent observation, journal capture, oracle; `run`, `check`, `self-test`, `ddmin`, `plan` |
| `oracle.py` | independent oracle: journal replay, invariants, classification, self-test controls |
| `summarize.py` | aggregates per-schedule reports into `results.json` |
| `run_batches.sh` | lock-fair batching: one `locks.sh iris` hold per batch of seeds, at most 9 minutes each |
| `fcs01-minimal-plan.json` | the hand-reduced six-operation schedule that reproduces F-CS01 |

**Per schedule.** `Graph.KG.Eraser.EraseAll`, `Graph.KG.Ledger.PurgeAll`, `ledger.enable()`; snapshot of
`^IVG.Ledger`, `^Graph.KG.LedgerRevisionD` and the four content tables; `journal.mark()`; then each phase's workers
run concurrently (2-4 workers, plus an optional probe), then the driver observes the quiescent state directly
(globals by a server-side `$Query` dump, tables by SQL, `^KG("out")` per live edge) and runs the product's `verify()`;
at the end the IRIS journal since the mark is read (`traces/journal.py`) and the oracle judges the whole trace. The
trace (journal records of the relevant globals, events, observations) is kept gzip-compressed under
`$RUN_DIR/simulator/<batch>/s<seed>.trace.json.gz`, so every verdict can be recomputed offline (`sim.py check`).

**Tenants** (two or three per schedule): `acme` and `beta` in the prefix shape (ids `acme|n<k>` in the default graph),
`gamma` in the graph-per-tenant shape (relationships in graph `gamma_g`, node ids `gamma|n<k>`; its complete
redaction is the documented pair `redact("gamma_g")` + `redact(None, prefix="gamma")`, iris_vector_graph/ledger/client.py:653-655). Ids come
from a pool of seven per tenant shared by all workers, so operations collide on purpose. Every string a tenant's
operations carry (ids, property and qualifier values, messages, sources, correlation ids, idempotency keys, graph
name) contains the tenant's name, which is what the SC-001 scan looks for.

**Operations** (public API only): `ledger.commit` of changesets mixing `create_node` / `upsert_node` with labels and
properties, `create_relationship` / `upsert_relationship` with qualifiers, `set_property`, `set_qualifier`,
`delete_relationship`, `delete_node(detach)`, `add_label`, spanning edges between prefix tenants, post-commit
properties (15%), idempotency keys (60%); same-key retries (idempotent replay) and same-key different-changeset reuses
(conflict); ledger-bypassing `create_node`, `create_edge`, `delete_edge`; `delete_nodes_by_prefix` and `erase_graph`;
`ledger.redact` with batch sizes 1-2000 and `max_batches` 0 (unbounded) or 1-3 (bounded, resumed by calling again);
`verify()`; `head()` + `reconstruct()`. Snapshot save/restore was left out: it writes server files and its residue
paths are already established findings (F-1801, F-C1304).

**Interleaving.** Random think times (0-300 ms); a probe process that holds the ledger head lock name
`^IVG.Ledger("head")` (0.3-2.5 s) or an adjacency writer lock name `^IVG.AdjW(graph)` (0.5-6.5 s, beyond the
writers' 5 s timeout) exclusively, as `traces/f1201_native.py` does; and the driver's `%SYSTEM.Process.Terminate` of
a worker's IRIS server process mid-operation (commit, erase or redaction), after which the worker reconnects and
retries the same operation once (the lost-acknowledgement retry with the same idempotency key; the resumed
redaction). A general schedule is two phases: build-up and churn by every worker, then offboarding of one tenant
(erase, redact every target, repeated once if a run did not complete; bounded runs resumed three times) while the
other workers keep writing, 30% of their operations into the tenant being offboarded. Race templates (seeds >= 2000)
time the same vocabulary into the windows the audit's models name: `dual-offboard`, `commit-into-offboard`,
`erase-vs-commit` (an erasure paused on `^IVG.AdjW` while commits land), `reader-vs-redact`, `retry-after-erase`,
`kill-redaction`, `bounded-resume`, `mixed`; each ends with a settling phase that offboards tenants and verifies.

## The oracle (independent of the product)

**Attribution.** Each worker brackets every attempt with two scratch SETs
`^IVGAuditSim(worker, op, attempt, "b"|"e") = pid`, outside any transaction (removed by the driver after each
schedule). IRIS journals them in the worker process's own stream, so every journaled write of that process between
its markers belongs to that attempt. `journal.transactions` groups the records into outermost transactions; a
transaction still open at the end (a terminated process) is not applied.

**Replay.** Starting from the recorded initial state, the oracle replays every committed unit in commit order onto
`^IVG.Ledger`, `^Graph.KG.LedgerRevisionD` (the rows of `Graph_KG.ledger_revisions`) and the data globals of
`Graph_KG.nodes`, `rdf_edges`, `rdf_labels`, `rdf_props` (row `$LB` layouts read from `%Dictionary.CompiledStorage`).
After every committed unit it checks the invariants below on the replayed state; a violation is counted once, at the
unit that introduced it, and is tagged *persistent* if it still holds in the final committed state (otherwise
*transient*: healed by a later commit, e.g. of a concurrent transaction whose uncommitted write the violating one had
read). At the end the replayed state is compared with the final direct observation (replay fidelity).

The target predicate, the target digest, the record replay and the verify comparison are written again from the
specs (spec 213 replay semantics; spec 256 FR-001/FR-002 for membership; `sha256(graph || $c(0) || prefix|)` for the
digest), not imported from the product.

| Id | Invariant | Source of the rule | Checked |
|---|---|---|---|
| I1 | stmt/tuple bijection: every `("tuple",s,p,o,gkey)` names a live `("stmt")` of that tuple, every live statement has its tuple entry | Ledger.cls:6-8 storage contract; CONTEXT.md:198-205 | after every unit |
| I2 | ERS-I3: every live edge row written by a ledger commit has a live statement | original STATUS.md ERS-I3 | after every unit |
| I2b | every live statement has a live edge row (converse; ERS-I2) | Eraser.cls:30-32 ("no live statement outlives its content") | after every unit |
| I3 | RED-B1.1: no tombstone a batch writes is of content live when that batch commits | STATUS.md RED-B1.1; spec 256 FR-005 | each redaction batch |
| I3b | RED-I1: a tombstone belongs to its run's target (FR-001 predicate) | spec 256 FR-001 | each redaction batch |
| I4 | marker owned by one target: a batch tombstones under its own target's marker; a Final removes only its own marker | RED-B6; LedgerRedact.cls:19-28 | each batch and Final |
| I5 | the redaction revision's per-revision counts equal the tombstones its own target's run wrote since its last Final | RED-B7.1; spec 256 FR-008/FR-009 | each Final |
| I6 | SC-001: once every target of a tenant has completed with no later write carrying the tenant, no string of the tenant remains in `^IVG.Ledger` (subscripts and values) or `ledger_revisions` | spec 256 SC-001, US1 (spec.md:40-44, 142-143) | at each completion |
| I7 | `verify()` at a quiescent point equals the oracle's replay-vs-tables comparison (`redaction_in_progress` while a marker exists) | spec 256 FR-007, Decision 3; replay.py contract | each phase end |
| I8 | an idempotency key binds one revision and one fingerprint; a replay returns that revision and writes no content; a redacted key is never bound again | spec 213 FR-019 (Ledger.cls:454-474); RED-B4; LED-B10 | every unit / replay |
| I9 | a `reconstruct()` answer equals the oracle's reconstruction at some committed point of its interval | RPL-I1 | each reader |
| I10 | an operation that reported failure (process not terminated) left no committed write | ERS-I1; spec 213 FR-047 | each refused op |
| I11 | a commit assigns a new statement id (`assigned_stmt`) only to an edge with no live recorded statement | LedgerApply.cls:173-195 (ResolveRef) | each commit |
| ADJ | every live edge row has its `^KG("out")` entry | spec 252 adjacency contract | each phase end |

**Classification.** Each violation is mapped to an existing finding from what caused it (the operation kind that
introduced it, the unit that killed the statement, the writer that made the tombstoned content live, whether a
replayed commit wrote content into an erased tenant, whether a redaction overlapped a reader), or `NEW`. NEW
violations are shrunk (`sim.py ddmin`: drop kills and probe, binary-search the seed prefix, drop phases, workers and
single operations, then think times; every candidate re-run through the product) and given `F-CSnn` ids.

**Self-test.** `sim.py self-test` mutates recorded real traces into ones the product did not produce and requires the
oracle to reject each with the intended invariant: a dropped tuple SET (I1), a statement killed after its commit
(I2), an edge row killed under a live statement (I2b), a node row made live inside a batch before its tombstone (I3),
a foreign marker digest (I4), an inflated audit count (I5), a tenant string left in the ledger at a completion (I6),
a flipped quiescent `verify()` answer (I7), a second binding of a key (I8), a ghost node in a reader's answer (I9), a
committed commit reported as failed (I10), a missing adjacency entry (ADJ). The unmutated traces are the baseline:
the control must raise its invariant's count above it.

## Limits

- Commit-order replay is the oracle's serialization of the journal; it does not model IRIS's dirty reads directly.
  A violation that only exists in the committed-state view and heals when a concurrent transaction commits is
  reported as transient, not counted as persistent.
- `verify()` is judged at quiescent points only; in-flight `verify()` answers (non-atomic by design) are recorded but
  not judged. Readers are judged by linearizability against committed points.
- Coverage is what random schedules reach in the time run: the races of F-1201 (needs the adjacency lock held while a
  commit lands in the erased graph), F-1303 (two runs starting together) and F-1402 depend on narrow timing; their
  counts below are what was hit, not rates.
- Temporal edges, vectors, BM25, snapshots and the non-ledger stores are outside this simulator.
