<!-- markdownlint-disable MD013 -->

# 3.7-integration-worlds: the disconnect world (and the process-stop and lock-timeout worlds)

Lane product-gates. Harness `product-gates/disconnect_world.py` with `product-gates/wireproxy.py`; raw evidence in
`$RUN_DIR/product-gates/disconnect-r1/` (per group `results-<group>.json` and `run-<group>.log`; per trial the raw
journal records `journal-<point>-<trial>.jsonl.gz` and every framed wire message `proxy-<point>-<trial>.jsonl.gz`).
Pin `3eaa79cf` deployed in AUDITIA by its own `initialize_schema` (`$RUN_DIR/setup/deploy-AUDITIA.json`, no redeploy);
IRIS 2026.1 Community (Build 234U); driver 5.3.2 (the pin's `uv.lock`); SynchCommit=0. No instance crash here, so
nothing below is a durability statement (that is the crash world, `live-crash-world-r2`, F-C1102).

## Method

- A client OS process runs one product operation through the product's real entry point (`IRISGraphEngine` on a DBAPI
  connection: `ledger.commit`, `ledger.redact`, `erase_graph`), connected to a TCP proxy instead of the superserver.
  The proxy frames the IRIS wire protocol (14-byte header: length, message id, statement id, 2-character type), so the
  disconnect lands at an exact message: a Native API class-method call is type `K\xc2` naming the class and method as
  `$LIST` strings; the driver's `commit()` is type `TC`; a reply carries its request's message id (sniffed first, then
  used as the trigger). Modes: **drop** the request (the server never sees it), **hold** the reply (the server finished
  the call; the client never reads it: the ambiguous acknowledgement), **cut** (the request is forwarded, the client is
  killed while the server executes it). Then SIGKILL of the client and both sockets closed.
- Two further worlds use the same oracle: **stop** (the client's IRIS process terminated by its recorded pid with
  `%SYSTEM.Process.Terminate` while it executes the call) and **lockheld** (a second live connection holds
  `^IVG.Ledger("head")` for the whole call, longer than LOCKTIMEOUT 30 s, `Ledger.cls:21`).
- After the event the harness waits until the server process has exited (`%SYS.ProcessQuery`), reconnects directly and
  applies the checker (`check()`), a pure function of the recorded observation:
  - O1 full step or nothing (SQL row counts; ledger records, live tuple entries and the redaction marker counted
    server-side in one terminal session, nothing compiled), against the point's expectation where the protocol
    determines it (a dropped COMMIT must leave nothing, a held reply must leave the full step);
  - O2 journal oracle (`traces/journal.py`): every transaction span of the dead process is committed or undone, none is
    open, and no non-counter write lies outside a span. IRIS journals the rollback of a dying process as compensating
    records inside the span before its final CommitTrans (with InTransaction=0 when the process halted on its lost
    client, InTransaction=1 when it was terminated), so a span's outcome is its net effect over all its records; only
    the documented non-transactional counters may survive an undo (`^KG("gen")`, `^KG("__version")`,
    docs/USER_GUIDE.md:252-258, Adjacency.cls:28; `^NKG` counters; SQL row-id counters); a span that changes only
    `^Graph.KG.LedgerStatsD` is a rejection counter (LedgerStats.cls:1-3);
  - O3 the head lock can be taken at once by another process, after the kill and after the retry;
  - O4 retry: the same call on a fresh connection. A commit with the same idempotency key must return the first answer
    when the first committed (`replayed=True`, same seq and revision id; spec 213 `contracts/ledger-api.md:26`
    "original outcome with replayed=True"), the revision the state holds when no answer ever left the server (cut), and
    a fresh single commit when nothing committed; a redaction run again completes; an erasure again removes the rest;
  - O5 the product's own `ledger.verify()` is `equal` after the retry (for an erasure after the documented
    erase-then-redact flow); O6 exactly once (one revision for the key, rows once, one redaction revision);
    O7 (lockheld) the call is refused with the documented `LedgerLockTimeoutError`.
- Controls: `--self-test-oracle` seeds one defect at a time into one recorded observation per point (164 seeded
  observations over 17 points); four defects are seeded live through the product's API at the end of the commit,
  redaction and erasure groups. `--reevaluate` re-judges every trial with the final checker from the kept raw journals.

## Results (52 trials: 49 at a failure point, 3 baselines; 0 violations)

| Point | Fault | Trials | Outcome after the fault | Journal of the dead process | Retry | Run |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | caller transaction: `ledger.commit` applied at a nested level, driver COMMIT dropped | 3 | nothing | 1 span undone (10,511 writes, 10,511 compensations) | fresh commit once | `pg-disconnect-commit` |
| A2 | staged commit (7,000 relationships): 2 StageChunk requests reached the server, Commit dropped | 3 | nothing | nothing journaled | fresh commit once | `pg-disconnect-commit` |
| A3 | Commit of 6,000 relationships cut 0.30 s after forwarding | 3 | full (server ran on 5.4-6.4 s, then exited) | 1 span committed (18,000 records) | replayed the revision held | `pg-disconnect-commit` |
| B1 | Commit executed, reply held | 3 | full | 1 span committed (900 records) | replayed, same seq and id as the held reply | `pg-disconnect-commit` |
| B2 | caller transaction: COMMIT executed, reply held | 3 | full | 1 span committed | replayed the first answer | `pg-disconnect-commit` |
| C1 | redaction (600 records, batch 50) executed, reply held | 3 | complete | 13 spans committed | re-run receipt zeros | `pg-disconnect-redact` |
| C2 | redaction (3,000 records, batch 1) cut 0.02 s after forwarding | 3 | complete (server ran every batch, exited 0.12-0.21 s later) | 3,001 spans committed | re-run receipt zeros | `pg-disconnect-redact` |
| C3 | bounded run (max_batches 1 per call), third call dropped | 3 | in progress, 100 tombstones, marker held | 2 batch spans committed | unbounded re-run completes | `pg-disconnect-redact` |
| D1 | EraseGraph (300 edges) executed, reply held | 3 | full | 1 span committed | removed 0 | `pg-disconnect-erase` |
| D2 | caller transaction: `erase_graph` applied, COMMIT dropped | 3 | nothing | 1 span undone (6,900 writes, 6,900 compensations) | removed 900 rows | `pg-disconnect-erase` |
| D3 | EraseGraph (6,000 edges) cut 0.05 s after forwarding | 3 | full (exited 0.61-1.05 s later) | 1 span committed | removed 0 | `pg-disconnect-erase` |
| T1 | server process terminated 0.3 s into a 6,000-relationship Commit | 3 | nothing | 1 span undone (15,632-19,648 journaled writes, net zero) | fresh commit once | `pg-disconnect-stop` |
| T2 | terminated 0.02 s into a redaction (still in its read-only pre-pass) | 3 | nothing yet (no marker) | nothing journaled | completes | `pg-disconnect-stop` |
| T2b | terminated 0.01 s after the redaction's marker appeared | 3 | in progress: 679, 592, 553 tombstones, marker held | as many committed batch spans as tombstones; none open or half undone | completes | `pg-disconnect-stop-midbatch` |
| T3 | terminated 0.05 s into EraseGraph of 6,000 edges | 3 | nothing | 1 span undone (1,924-7,540 journaled writes, net zero) | removed 18,000 rows | `pg-disconnect-stop` |
| L1 | head lock held by another process during a commit | 2 | nothing; LedgerLockTimeoutError after 31.0 s | only the rejection counter (stats span) | fresh commit once | `pg-disconnect-locktimeout` |
| L2 | head lock held during a redaction | 2 | nothing, no marker; LedgerLockTimeoutError after 31.0 s | nothing journaled | completes | `pg-disconnect-locktimeout` |

The head lock was free after every kill and every retry (49/49), verify was equal after every retry (49/49 and the
3 baselines). Re-judged uniformly: `pg-disconnect-reevaluate` (52 trials, 0 violating). Controls:
`pg-disconnect-selftest` (164/164 seeded observations flagged; every source observation passes) and
`pg-disconnect-live-controls` (4/4 caught: a second connection holding the head lock with the tag's content committed
again under another key; a same-key retry with a different changeset; a bounded redaction left open; nodes and an edge
written into an erased graph outside the ledger).

## What the world shows (live, on the pin, SynchCommit=0)

1. **A client disconnect never interrupts a running server call.** The server process runs the call to its end (a
   commit, every batch of a redaction, an erase including its DDL) and exits when it next reads the closed socket
   (A3, C2, D3). So the outcome of a disconnect is decided by which message got through: a request that never arrived
   (A2) or a caller COMMIT that never arrived (A1, D2) leaves nothing, because IRIS rolls back the open transaction of
   the dead process (P-0001 holds, journal-checked); anything else leaves the whole call.
2. **Only a stopped server process interrupts an operation** (T1, T2b, T3): the open transaction is undone, every
   committed redaction batch is whole, and the re-run finishes. No partial step was observed in 49 trials.
3. **Same-key retries return the first answer** whenever the first commit committed (B1, B2: same seq and revision id
   as the reply the client never read; A3: the revision the state holds), and commit exactly once otherwise.
4. **A revision answered inside the caller's own transaction is provisional** (A1): the client was told a seq and a
   revision id; after its COMMIT was lost the retry committed the same content as the same seq with a new revision id.
   This follows the documented contract (docs/USER_GUIDE.md:260-265: after the caller's rollback the revision is
   gone); it is not recorded as a finding, but such a client holds an id that no revision has.
5. **Lock timeouts refuse cleanly** (L1, L2): nothing applied, the documented error, only the rejection counter written.

Not covered: SynchCommit=1; a crash inside these points (crash world); the HTTP API path (F-C1703, F-C1604 are its
retry worlds); multi-node; disconnect of the non-ledger writers (`create_node`, `bulk_create_nodes`; see
`breadth-a-live-03-bulk-killed-client`). The bounded-resume rescan of F-C1303 was met while building C3 (a bounded
call on a longer ledger tombstoned nothing and left no marker, exploration only), which is why C3 uses a fresh ledger.
