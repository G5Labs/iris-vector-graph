# Decisions for the human

Each decision the uplift could not take itself. Module files cite them as `open:HD-NNkk`; an `open` cell names one.
Ids are `HD-NNkk` (`NN` the module number). Breadth-module decisions live in `decisions/NN.md`.
An entry needs an `Owner:` line; only `Owner: human` satisfies the gate.

### HD-0001 How to read "defined by its ancestors or an earlier same-level statement"
- Owner: human
- Question: the playbook's definitions-first rule, read literally, forbids a child from using a term its parent's
  earlier sibling defined. The uplift reads it as lexical scope (ancestors, and earlier siblings of the statement or of
  any ancestor). Accept this reading, or require literal ancestry?
- Default applied until decided: lexical scope (`tools/ontology_index.py`, `in_scope`).

## Decisions from the worked example (modules ERS, RED, RPL)

### HD-1201 Should a graph erasure take the ledger head lock?
- Owner: human
- Question: EraseGraph/EraseNodes take no head lock (F-1201). Take it for the whole erasure transaction, or document that erasure
  needs a quiet graph? Also: may a redaction run start while an erasure of its target is open (its liveness check reads the
  erasure's uncommitted deletes)?
- Evidence: model `erasure-as-built` (violation) and `erasure-reviewed` (passes with the lock).
- Default at the pin: no lock.

### HD-1301 Should the redaction's opening check and its marker be one locked step?
- Owner: human
- Question: adopt the reviewed design proved in `proofs/src/l2.rs` (Start checks liveness and the marker under the head lock and sets
  the marker in its own transaction), closing F-1302 and F-1303? A no-op redaction would then write its marker and remove it; the
  audit revision should still be written only when something was redacted.
- Evidence: proof (53 obligations; 6 controls rejected, including the pin's behaviour), model checks and refinement audit (pass),
  live reproductions of both defects.
- Default at the pin: unlocked check, marker at the first tombstone.

### HD-1302 Which rule clears a revision's free text: any tombstone or every record?
- Owner: human
- Question: F-1301. The code and ADR-0013 follow Decision 2 (any). Amend spec 256 FR-004?
- Default at the pin: any.

### HD-1303 Can an unfinished redaction be abandoned, and what may a default-graph target touch?
- Owner: human
- Question: (a) a run stuck on a live target (RED-B8.2) blocks every ledger write into it until the target is erased again; should
  an operator be able to abandon a run? (b) should a default-graph target with no prefix count node rows of every graph, or be
  refused (F-1304)?
- Default at the pin: no abandon call; no-prefix default-graph target accepted.

### HD-1304 How is a tenant's node history redacted when nodes live in the tenant's own graph?
- Owner: human
- Question: F-1305. Record the node's graph in ledger node records (a layout change), or require tenant id prefixes and say so in
  the redaction docs?
- Default at the pin: only id prefixes reach node records.

### HD-1305 Should a replayed commit apply its post-commit properties?
- Owner: human
- Question: F-1306 / F-1101. A replay currently re-applies them, which can revive erased content between erasure and redaction.
- Default at the pin: applied on every replay.

### HD-1401 Verification and record readers: node identity and redaction checks
- Owner: human
- Question: (a) verification compares nodes by id across graphs while a ledger delete removes only the default graph's node
  (F-1401): which should change? (b) should record readers check for a redaction again after reading (F-1402)?
- Default at the pin: graph-blind node comparison; one check before reading.
