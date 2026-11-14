# Validation lane: environment, harness and blocked lanes (reference for SUITES.md)

## Machine and container

- Host: GCP VM, Intel Xeon Platinum 8481C @ 2.70 GHz, 22 vCPUs (10 visible to this session), 86 GB RAM, Linux
  7.0.0-1014-gcp; shared with the other audit lanes and unrelated containers (load average 5-8 during the runs).
- IRIS: container `ivg-playbook-20261113-audit-iris`, image `containers.intersystems.com/intersystems/iris-community:2026.1`
  (sha256:546fe52b9e68), IRIS for UNIX (Ubuntu Server LTS for x86-64 Containers) 2026.1 (Build 234U) Fri Mar 27 2026;
  cpuset 5,6 (2 CPUs), no memory limit, buffers auto-sized (`globals=0`), USER journalled (GlobalJournalState 3).
- Licence (`%SYSTEM.License`, `$RUN_DIR/validation/env-probe/license.log`): "InterSystems IRIS Community license",
  8 licence units for the whole container, shared by all lanes (CONVENTIONS.md "Connection cap"). `%AI.Tool`,
  `%AI.ToolSet`, `%AI.MCP.Service`, `%AI.Policy.ConsoleAudit` do not exist on this server.
- Client: Python 3.11.18, the venv of the original run (`$IVG_BASE_RUN/venv`), intersystems-irispython 5.3.2 (the pin's
  `uv.lock`), pytest 9.0.3, behave from the same venv.

## Clean build

The audit worktree is read-only for this lane, and upstream tests write into the checkout (FastHTML's `.sesskey` in the
cwd; result files), so the first unit attempt failed at collection (`unit-1`). Every suite therefore ran from a clean
clone of the pin: `git clone --shared --no-checkout` of the local repository into `$RUN_DIR/validation/checkout`,
`checkout --detach 3eaa79cf77d3e0a879b2cced634cf2729d81499e` (tree b098a6f48a37, equal to the pin tree), submodule
`vendor/opencypher` at 677cbafa from the local module store (no network). `run.sh` refuses to run unless the clone is
at the pin with no tracked change, and records untracked files before and after. `PYTHONPATH` is the clone, so the
editable install's path (the main checkout) is never imported.

## Harness (validation/run_suite.py) — exactly what it replaces

1. `tests.conftest._deploy_objectscript`: only the session fixture's call (`iris_test_container` ->
   `_deploy_objectscript(<container>)`, container == `$IVG_TEST_CONTAINER`, namespace unset or USER, no Native handle,
   no port) goes to `deploy_community`: database identity checked with the pin's probe, then the pin's own
   `IRISGraphEngine.initialize_schema()` at width 768 (which skips Graph.KG.MCPService/MCPToolSet/MCPTools for the
   missing %AI classes and reports them). Every other call (unit tests that exercise the function with fakes; e2e
   files loading a scratch namespace) goes to the pin's function unchanged (`deploy_delegated` in each meta.json).
   The conftest blob is checked equal to the pin's before patching.
2. Namespace guard (lane rule: never create namespaces): `scripts/dev/tcp_setup.make_namespace` / `drop_namespace`
   given a real IRIS handle, and `tcp_setup.run` on the real server with lines creating a namespace or database,
   raise `AuditNamespacePolicy`. Fakes pass through. Hits are recorded (`guard_hits`).
3. Switch, not a replacement: `IVG_GATE_NAMESPACES=0` (tests/e2e/gate.py's documented switch) so the e2e gate does
   not make its ~45 scratch namespaces; the files that need them skip with the gate's own reason.

Per run: `iris.cpf` [Namespaces] read before and after (`namespaces_unchanged`); every run holds `tools/locks.sh iris`.
`integration-1-c00` recorded `IVG460SNAP` appearing during its hold: messages.log shows it mounted at 23:02:53, and
`$RUN_DIR/breadth-c/18/unit-snapshot-20261113T230248.log` shows breadth lane C running tests/unit/test_snapshot.py
then (its make_scratch_namespace creates IVG460SNAP). Not this lane's doing; reported to the orchestrator here.

## Side effects of the upstream suites on the shared container

- `IVGDev.Setup` and `IVGDev.Run` (scripts/dev/objectscript/IVGDev/*.cls at the pin, unmodified) are compiled into
  %SYS by the suites' own `scripts/dev/tcp_setup.ensure_helper` (first seen after `docs-1`; absent at 22:38 UTC).
- e2e security tests create and delete their own users, roles and web applications (Security.* in their fixtures).
