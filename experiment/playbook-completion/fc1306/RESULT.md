# F-C1306 live probe: legacy `Graph_KG.ledger_revisions` after a 4.5.1 upgrade to a non-default schema

Lane `fc1306`, pin `3eaa79cf`. Run `fc1306-legacy-ledger-rows` (live, **fail**). Raw result `$RUN_DIR/fc1306/probe.json`
(stdout `$RUN_DIR/fc1306/probe.log`). Updated finding record: `fc1306/finding.json` (F-C1306, now `reproduced-live`,
S1, confidence high).

## What ran

`bash tools/locks.sh iris timeout 3000 python experiment/playbook-completion/fc1306/probe.py`, 2026-11-14
01:51:59-01:52:28 UTC. The steps:

1. **4.5.1 namespace.** The probe used the pinned fixture's functions, imported unmodified from
   `scripts/fixtures/build_release_namespace.py`. `tests/e2e/test_460_upgrade_ledger_history_e2e.py::upg` calls the
   same ones.
   - `build('v4.5.1', 'IVG262FC1306', schema_prefix='RAG')` created the new scratch namespace (database
     `/usr/irissys/mgr/ivg262fc1306/`). v4.5.1's own setup compiled v4.5.1's classes.
   - `run_ledger_commits('v4.5.1', ..., 'RAG')` committed the fixture's two r114 changesets.
   - The namespace did not exist beforehand: the probe checked, so `build`'s drop was a no-op. It is left intact and
     recorded in `incidents/NAMESPACES.md`.
2. **Two tenants.** `fc1306/ledger451_child.py` ran the way the fixture runs its own child: the release worktree on
   `PYTHONPATH`, through v4.5.1's public `engine.ledger.commit`.
   - Tenant T (`r114`) got 2 more changesets, tenant O (`o114`) got 2.
   - Each had a message, source, correlation id and idempotency key.
   - Result: 7 revisions in `Graph_KG.ledger_revisions`. T's are seqs 2, 3, 4 and 6; O's are 5 and 7.
3. **Upgrade.** The pin's `initialize_schema(schema_prefix='RAG')` ran, with a dry run first.
   - It reported `ledger_history_copied` = `{ledger_revisions: 7, ledger_stats: 1}`.
   - `verify()` was equal and the head was 7.
   - It deployed 66 classes and skipped the 3 MCP classes (`%AI` is absent; this probe does not need them).
4. **Erase and redact T.** Through the pin's public API:
   - `delete_nodes_by_prefix('r114:')` removed 3 nodes.
   - `ledger.redact(None, prefix='r114', separator=':')` completed. Receipt: revisions [2, 3, 4, 6], 11 records
     tombstoned, `metadata_cleared` 4, 2 idempotency keys removed, redaction seq 8.
   - `verify()` was equal.
5. **Scan.** SC-001-style scans for T's and O's strings covered:
   - every `^IVG.Ledger` node;
   - every row of every `ledger_*` table, in both schemas;
   - those tables' storage globals.

## What it found

| Location | T's strings after redaction |
|---|---|
| `^IVG.Ledger` (103 nodes) | none |
| `RAG.ledger_revisions` (the pin's table, which `ClearRevision` updates) | none (seqs 2, 3, 4, 6: all four fields NULL) |
| `Graph_KG.ledger_revisions` (v4.5.1's `Graph.KG.LedgerRevision`, still projected) | **4 rows** (below) |
| `^Graph.KG.LedgerRevisionD` (that table's data global) | the same 4 rows' values |

What the 4 rows in `Graph_KG.ledger_revisions` keep:
- Seqs 2 and 3 keep their messages ("two nodes and a relationship", "a property").
- Seqs 4 and 6 keep message, source, correlation id and idempotency key verbatim (`fc1306T-msg-3`,
  `{"system":"fc1306T-src-3"}`, `fc1306T-corr-3`, `fc1306T-idem-3`, and the same for `-4`).

Why this is a failure:
- SC-001's bar is "every `Graph_KG.ledger_*` row finds none of the tenant's ids or values", so this run fails it in
  the spec's own literal scope.
- The receipt said `metadata_cleared: 4`, and its `out_of_reach` names only exports, journals and backups.
- Migration step 4 (`DROP TABLE ... %NODELDATA`, docs/migration/v4.6.0.md:240-252) would drop the projection, but
  `^Graph.KG.LedgerRevisionD` would still hold the values above.

Tenant O's rows were unchanged in `RAG.ledger_revisions`, so the redaction stayed within T as intended.

Side observation, not part of the finding: the actor value `r114` (the fixture's actor) stays in both schemas'
`ActorIdx`. FR-004 does not clear `actor`.

## Scope notes

- No product file was changed. `check-product-scope.sh` passed at registration.
- Three things were compiled:
  - v4.5.1's classes, by the fixture's `build`, in the scratch namespace;
  - the pin's classes, by its own `initialize_schema`;
  - possibly the fixture's `IVGDev.Setup` helper in `%SYS`, which `tcp_setup.ensure_helper` loads only when the
    loaded one's hash differs.
- The fixture also staged v4.5.1's sources in container `/tmp/ivg262_src_v4_5_1` (`docker cp`).
- `messages.log` shows "Failed to load dynamic library .../None" three times. That is v4.5.1's optional Arno probe
  and does not affect the result.
- Connections: one from the probe at a time, plus one per fixture child.
- `NAMESPACES.md`'s header says every namespace holds pin-only classes. That is not true of IVG262FC1306; its row says
  so.
