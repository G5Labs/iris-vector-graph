# Namespaces in the dedicated audit container

Container `ivg-playbook-20261113-audit-iris` (IRIS 2026.1 Community, Build 234U). Every namespace below holds only the
pin's own classes compiled by the pin's own deploy path, or no product classes, or (where the row says so) an older
release built by a pinned upstream fixture. None is dropped: they stay for attribution.

| Namespace | Database | Created by | Lane | UTC | Purpose |
|---|---|---|---|---|---|
| USER | /usr/irissys/mgr/user/ | container image; product deployed by the validation fixtures | validation | before 2026-11-13 22:18 | product suites |
| AUDITENV, AUDITCORE, AUDITA, AUDITB, AUDITC | /usr/irissys/mgr/<lower>/ | orchestrator, `$RUN_DIR/setup/create-namespaces.script` | orchestrator | 2026-11-13 ~22:35 | per-lane isolation |
| AUDITIA, AUDITIB | /usr/irissys/mgr/<lower>/ | orchestrator, `$RUN_DIR/setup/create-namespaces-2.script` | orchestrator | 2026-11-13 ~22:43 | intent probes |
| IVG460SNAP | /usr/irissys/mgr/ivg460snap/ | upstream fixture `tests/unit/test_snapshot.py::snapshot_conn` -> `scripts/dev/make_scratch_namespace.py make('IVG460SNAP')`, then `tests.conftest._deploy_objectscript` (pin classes; 3 MCP classes failed: `%AI` absent) | breadth-c | 2026-11-13 23:02:53 | module 18 unit tests; see IVG460SNAP.md |
| IVG262FC1306 | /usr/irissys/mgr/ivg262fc1306/ | `locks.sh iris timeout 3000 python experiment/playbook-completion/fc1306/probe.py` -> pinned fixture `scripts/fixtures/build_release_namespace.build('v4.5.1','IVG262FC1306',schema_prefix='RAG')` (`make_scratch_namespace.recreate`: absent beforehand, so no drop; v4.5.1's own `initialize_schema` compiled v4.5.1's classes, sources staged by the fixture in container `/tmp/ivg262_src_v4_5_1`), `run_ledger_commits`, then the pin's `initialize_schema(schema_prefix='RAG')` (66 pin classes; 3 MCP skipped: `%AI` absent). Not pin-only: v4.5.1's `Graph.KG.LedgerRevision`/`LedgerStats` and `SQLUser` objects remain | fc1306 | 2026-11-14 01:51:59 (namespace map activated 01:52:00, messages.log 1149-1151) | F-C1306 upgrade probe, run `fc1306-legacy-ledger-rows` |
