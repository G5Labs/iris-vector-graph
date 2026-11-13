# Findings

Places where the code, a test or a document disagrees with a stated requirement. Module files cite them as
`finding:F-NNkk`. Breadth-module findings live in `findings/NN.md`; worked-example findings live here.
Each finding names its evidence and what would close it; none is closed by this uplift unless it says so.

Evidence kinds below: **live** = observed on IRIS Community 2026.1 in `$IVG_TEST_CONTAINER` by `native/scenarios.py` (trace in
`$RUN_DIR/native/traces/<scenario>.json`); **model** = a counterexample from `model/` (bounded, executable twin, not the code);
**proof** = rejected as a control by the Verus proof in `proofs/`; **inspected** = read in the code at the pin.

### F-1201 Graph erasure is not serialized with ledger commits into the same graph
- Evidence: inspected `Eraser.cls:47-261` (no `Lock +^IVG.Ledger("head")`; `Adjacency.RemoveGraph` takes a shared lock,
  `Adjacency.cls:428-447`); model `erasure-as-built`: E deletes G's rows, P commits a new edge of G, E's ledger cleanup
  (`EraseLedgerFor`, `Eraser.cls:1117-1144`) kills the new edge's statement entry, both commit: a live edge with no statement.
  The reviewed design (erasure holds the head lock) passes exhaustively. Not reproduced live (the window sits between two
  statements of one ObjectScript method). Same root cause as F-1114 (module LED).
- Impact: the next ledger delete of that edge finds no statement; ADR-0004's converse breaks. A redaction run started while the
  erasure is open reads its uncommitted deletes as "not live" (HD-1201).
- Close: take the head lock in `EraseGraph`/`EraseIdSet`/`EraseEdges` (or decide that erasure requires a quiet graph and say so).

### F-1301 Spec 256 FR-004 and Decision 2 disagree about which revisions lose their free text
- Evidence: `specs/256-ledger-tenant-redaction/spec.md` FR-004 says "for a revision whose every record is redacted"; Decision 2
  (same file), ADR-0013 and `LedgerRedact.cls:345-346` clear it on any tombstone. Commit `42907b21` recorded Decision 2 without
  updating FR-004. Proof control `control_meta_every` (the FR-004 wording) is rejected by the L1 Decision-2 invariant.
- Impact: documentation only; a reader of FR-004 expects tenant B's message on a spanning revision to survive.
- Close: amend FR-004 (HD-1302).

### F-1302 A commit that lands between the redaction's liveness check and its first tombstone is redacted while live
- Evidence: inspected `LedgerRedact.cls:202-216` (marker and liveness read without the head lock) and `322-324` (marker set with
  the first tombstone). Live `commit_in_unmarked_window`: with the head lock held by a second process, `Redact(gTenantA)` passed
  its liveness check; a commit re-creating `tenantA|n9` in gTenantA landed; the run then tombstoned the new revision's records,
  cleared its free text, moved its retry key to `idemRedacted`, and refused at its final step with `target_live`, leaving the
  marker. Reruns are refused (target live); commits into the target are refused; only a second erasure lets the run finish.
  Model `redaction-as-built-live` (3 steps: Start A, Commit into A, Scan). Proof: control `control_unmarked_start` is the pin's
  behaviour (with `control_other_target`) and is rejected; the reviewed design (check and marker in one locked step) is proved
  and model-checked. The design itself prescribes the late marker: `specs/256-ledger-tenant-redaction/plan.md:23` ("The first
  tombstone sets the marker").
- Impact: the history of live content is destroyed (cannot be recovered; only digests remain) and the tenant cannot be written
  through the ledger until erased again. The window lasts from the call until the first matching record's batch commits, which on
  a large ledger with the tenant's records late in it is the whole scan of other tenants' records.
- Close: HD-1301 (set the marker together with the liveness check under the head lock, in its own transaction).

### F-1303 Two redaction runs of different targets that start together both run, and their audits mix
- Evidence: inspected `LedgerRedact.cls:202-205` (the "another redaction?" check is unlocked), `322-324` (a run sets the marker only
  if none exists; a second target's run tombstones under the first's marker), `342-344` and `473-480` (one set of counters),
  `409-441` (a final step removes whichever marker exists). Live `two_targets_at_once`: both runs completed; the audit revisions'
  counts were wrong in every run, and differently each time (10/6, 14/2 and 1/15 against true counts 9/7). Model `redaction-as-built-audit` (7 steps): the second run to finish
  writes an audit that counts the first target's tombstone and removes the first run's marker while it is still running. Proof
  control `control_other_target` is rejected.
- Impact: the audit (Decision 1) misattributes; while one run holds the marker, commits into the other run's target are not
  refused, which reopens F-1302 for the whole of that run.
- Close: as HD-1301 (the marker taken under the lock at start also refuses the second target).

### F-1304 `redact(None)` with no prefix tombstones the node records of nodes that live in named graphs
- Evidence: `LedgerRedact.cls:149-176` checks liveness of a no-prefix default-graph target in the default graph only, while
  `Matches` (`89-112`) takes every node record (all have graph ""). `LedgerGenesis.cls:14-36` records every node graph-blind.
  Live `default_graph_without_prefix`: nodes created in gTenantB before `enable()`; `Redact("", "")` was accepted and
  tombstoned all their genesis node records; `verify()` then diverged on live content.
- Intent violated: `specs/256-ledger-tenant-redaction/plan.md:10` ("the node-liveness check for a default-graph target is
  graph-blind"); the code makes it graph-blind only when a prefix is given.
- Impact: another tenant's live history is destroyed by a call the API documents as "the default graph".
- Close: HD-1303-style decision: count node rows of every graph for a default-graph target (as the prefix case already does), or
  refuse a default-graph target without a prefix.

### F-1305 One graph per tenant with unprefixed node ids cannot be redacted
- Evidence: live `graph_per_tenant_unprefixed`: nodes n1, n2 in gTenantA and m1, m2 in gTenantB, ledger enabled afterwards
  (genesis); `erase_graph("gTenantA")` and `redact("gTenantA")` completed; tenant A's node ids and property values stayed in the
  ledger and `verify()` diverged. Inspected: node records name no graph (`LedgerGenesis.cls:14-36`, `LedgerApply.cls:215-251`).
- Impact: spec 256's context (`spec.md:17`, "tenant erasure is then EraseGraph plus this redaction") holds only when node ids
  carry a tenant prefix; the only other target that reaches the records is F-1304's. ADR-0013 and `plan.md:9` document that
  node records are graph-blind, so this is a documented limitation that contradicts the spec's stated deployment.
- Close: HD-1304 (record a node's graph, or require and document tenant id prefixes).

### F-1306 A replayed retry re-applies post-commit properties and revives an erased tenant's content
- Evidence: inspected `client.py:430-435` (post-commit properties applied with no `replayed` check) and `445-487` (plain SQL, no
  revision; `rdf_props` has no foreign key). Model `retry-as-built` (3 steps: Commit, Erase, Retry). Live
  `retry_between_erase_and_redact`. Same root cause as F-1101 (module LED).
- Also during a run: a retry whose key is still bound (its revision not yet tombstoned) is replayed before the redaction's
  commit check runs (`Ledger.cls:457-462` before `514-518`), so its post-commit properties are re-applied then too.
- Impact: a client retry between erasure and redaction makes part of the erased tenant live again, and the redaction is then
  refused as `target_live`. Live, the revived property row outlived a second `delete_nodes_by_prefix` (its node row was gone, so
  the node erasure did not select it); only a manual SQL delete let the redaction finish. No product call removes it short of
  erasing the whole default graph.
- Close: HD-1305 (apply post-commit properties only to the first, non-replayed commit).

### F-1401 Verification reports a divergence after a ledger detach delete of a node that has edges in a named graph
- Evidence: inspected `LedgerApply.cls:374-418` (4.6.0 R290: the delete is the default graph's; the named graph's node row and
  edges stay) and `replay.py:596-606` (verification compares nodes by id across graphs). Live `mixed_tenant_flow`: on the upstream
  fixture's world, before any erasure, `verify()` reported one difference, node `tenantA|n3` (its gTenantA row and its LINKS edge
  outlived the detach delete).
- Impact: false "unrecorded_writes"; `verify(adopt=True)` would re-record the node. The upstream e2e test's "equal after the
  redaction" partly reflects the erasure removing this leftover (test reflection).
- Close: HD-1401 (verification and R290 must agree on what a node is).

### F-1402 Record readers check for a redaction once, before reading, with no lock
- Evidence: inspected `client.py:687-739` and `replay.py:806-835`: the marker is read, then the records are read in separate
  calls. Model `readers-as-built` (4 steps: reader checks, redaction starts, one tombstone, reader reads a half-done view); a
  second check after the read passes the model (`readers-reviewed`). Live `reader_races_redaction`: with one batch forced
  (in the test process only) between `reconstruct()`'s marker check and its record read, `reconstruct()` answered instead of
  refusing, with tenant A's graph half redacted (2 of 3 statements); called again, it refused.
- Impact: `reconstruct`, `diff`, `export_reconstruction` and `verify` can return a view with part of a tenant redacted, which spec
  256 Decision 3 exists to prevent.
- Close: HD-1401.
