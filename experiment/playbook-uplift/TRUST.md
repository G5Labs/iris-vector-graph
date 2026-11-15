# Trust inventory and premises

Every premise the uplift relies on, with how it is (or is not) checked. Module files cite them as `assumed:P-NNNN`.
Premise ids are `P-NNkk`: `NN` is the module number of the file that introduced it, `kk` a counter. Premises from the
breadth modules live in `trust/NN.md`; the system and worked-example premises live here.

A premise is not a proof. "Checked live" means a test in this uplift observed the premise on IRIS Community
2026.1 (`$IVG_TEST_CONTAINER`), which is evidence for that build only.

### P-0001 IRIS rolls back a stopped process's open transaction
- Statement: when a process stops (killed, halted or crashed) inside TSTART, IRIS undoes its uncommitted global and SQL writes.
- Used by: every batched or multi-store command (Eraser, Ledger.Commit, LedgerRedact batches).
- Check: live (see `evidence/runs.json`, the kill-mid-batch scenario), else documentation only.

### P-0002 Uncommitted global writes are visible to other processes
- Statement: IRIS globals have no read isolation; another process reads a value set inside an open transaction.
- Used by: the analysis of lock-free readers (verify, record readers, redaction's first liveness check).
- Check: live (dirty-read probe).

### P-0003 A lock released inside a transaction is held until the transaction ends
- Statement: `Lock -name` executed inside TSTART defers the release to TCOMMIT/TROLLBACK.
- Used by: Graph.KG.Ledger.Commit (releases the head lock before TCOMMIT), Graph.KG.Adjacency writers.
- Check: live (lock probe from a second process).

### P-0004 A stopped process's locks are freed
- Statement: IRIS releases every lock of a process when the process ends.
- Used by: resumption after an interrupted redaction or commit.
- Check: live (kill-mid-batch scenario: a later redaction acquires the head lock).

## Premises of the worked example (modules ERS, RED, RPL)

### P-1201 A SQL delete waits for a row another transaction holds
- Statement: IRIS row locks make the Eraser's DELETE wait for a row that an open transaction inserted or deleted.
- Used by: model/src/erasure.rs (an erasure cannot remove a row a commit has not finished).
- Check: documentation only (IRIS SQL locking); not observed in this uplift.

### P-1301 Separability: every record of one replay key is in a redaction target or none is
- Statement: target membership is a property of the node id or statement id a record touches, not of the record.
- Why it holds at the pin: node records carry graph "" and are matched by id prefix; edge records carry their edge's graph and
  fixed ends (`LedgerRedact.cls:89-112`). Exception: a qualifier record whose ends cannot be found is left alone and counted as
  `unattributed_records`; with such records the replay theorem does not apply.
- Used by: every replay theorem (`proofs/src/model.rs`), the model checks.
- Check: live scenarios compare the code's tombstones with an independent oracle of the target rule (`native/scenarios.py
  in_target`); they agreed in every scenario.

### P-1302 SHA-256 identifies a record
- Statement: two different canonical records do not share a digest; the canonical form (`Ledger.CanonicalRecord`) is stable.
- Used by: RED-B2.2 (an auditor holding the original can confirm a tombstone).
- Check: live scenarios recompute every tombstone's digest from the record read before redaction.

### P-1303 sha256(retry key) identifies the key
- Used by: proofs/src/l2.rs models `idemRedacted` as holding the key itself.

### P-1306 Commits pause long enough for a redaction run to reach the last record
- Statement: the batch loop follows the tail of `^IVG.Ledger("rec")`; under a steady stream of commits it finishes only if the scan
  outpaces them. Proved only: an uninterrupted run takes at most `rank0` steps (`proofs/src/progress.rs`).

### P-1307 An operator calls an interrupted redaction again
- Statement: nothing resumes a stopped run on its own; commits into the target stay refused until someone does.

### P-1308 Only LedgerRedact sets the revision-table exemption variable
- Statement: `%IVGLedgerRedaction` is process-public; the exemption guards against mistakes, not against code running in the
  namespace. Check: upstream unit test `test_only_ledger_redact_sets_the_exemption_variable` (source scan), run in the unit run.

### P-1309 Journals, backups and earlier exports are out of reach
- Statement: IRIS journals, backups and `export_reconstruction` files written before a redaction keep the content; the redaction
  marker also holds the target in plain text while a run is unfinished.

### P-1401 Verification runs on a quiet ledger
- Statement: verify() takes no lock and reads the head, records and tables separately; concurrent commits show up as differences.

### P-1310 One scope for erasure, the liveness check and the record match
- Statement: the replay theorems model a redaction target as one predicate, used by the erasure, by the liveness check and by
  the record match. In the code these are three scopes: the Eraser's SQL (graph, or graph and id prefix), `LiveRows` (default
  graph only for a no-prefix default-graph target, every graph for a default-graph prefix target, the target graph only for a
  named-graph target) and `Matches` (record graph field, id prefix,
  edge ends). Where they differ the theorem does not apply: F-1304 and F-1305 are such places.
- Check: live, on the scenario worlds only (the oracle agreed with the code there); not checked in general. Raised by the
  independent review.

### P-1311 No erasure of the target is open when a redaction starts
- Statement: the liveness check reads uncommitted rows (P-0002) and the erasure takes no head lock (F-1201), so a check can pass
  on an erasure that later rolls back. The reviewed design's proof assumes erasure is atomic with respect to the check.
- Check: none (HD-1201). Raised by the independent review.
