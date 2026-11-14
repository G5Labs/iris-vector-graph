# Namespaces in the dedicated audit container

Container `ivg-playbook-20261113-audit-iris` (IRIS 2026.1 Community, Build 234U). Every namespace below holds only the
pin's own classes, compiled by the pin's own deploy path, or no product classes. None is dropped: they stay for
attribution.

| Namespace | Database | Created by | Lane | UTC | Purpose |
|---|---|---|---|---|---|
| USER | /usr/irissys/mgr/user/ | container image; product deployed by the validation fixtures | validation | before 2026-11-13 22:18 | product suites |
| AUDITENV, AUDITCORE, AUDITA, AUDITB, AUDITC | /usr/irissys/mgr/<lower>/ | orchestrator, `$RUN_DIR/setup/create-namespaces.script` | orchestrator | 2026-11-13 ~22:35 | per-lane isolation |
| AUDITIA, AUDITIB | /usr/irissys/mgr/<lower>/ | orchestrator, `$RUN_DIR/setup/create-namespaces-2.script` | orchestrator | 2026-11-13 ~22:43 | intent probes |
| IVG460SNAP | /usr/irissys/mgr/ivg460snap/ | upstream fixture `tests/unit/test_snapshot.py::snapshot_conn` -> `scripts/dev/make_scratch_namespace.py make('IVG460SNAP')`, then `tests.conftest._deploy_objectscript` (pin classes; 3 MCP classes failed: `%AI` absent) | breadth-c | 2026-11-13 23:02:53 | module 18 unit tests; see IVG460SNAP.md |
