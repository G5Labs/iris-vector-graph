# Conventions for the completion audit

Product pin `3eaa79cf77d3e0a879b2cced634cf2729d81499e` (tree `b098a6f4`). Original submission `9c3719c1` under
`experiment/playbook-uplift/` stays byte-for-byte as submitted: read it, cite it, never edit it.

## Scope control (binding)

- Write only under `experiment/playbook-completion/` (artifacts) and `$RUN_DIR` (raw logs, build targets, traces).
- The product (everything outside `experiment/`) is read-only: no patches, no patch files elsewhere, no modified
  classes compiled into IRIS. The deploy path for product classes is the pin's own `IRISGraphEngine.initialize_schema()`.
- Test-only helpers are allowed only if they create and remove their own scratch globals (`^IVGAudit*`) or scratch
  SQL tables (`IVGAudit.*`). Never compile a class into IRIS. Use the Native API and SQL from Python instead.
- Never make a failing check pass by changing its target or weakening its oracle. A product defect is recorded as a
  finding and its obligation stays failed/open.
- `bash experiment/playbook-completion/check-product-scope.sh` must pass before a result is registered
  (`tools/register_run.py` enforces it).
- Agents do not commit; the orchestrator commits by lane.

## Shared resources

- IRIS: only the dedicated container `$IVG_TEST_CONTAINER` on `$IVG_PORT`, through `tools/iris_conn.Conn(namespace)`
  (identity checked). The pin is deployed (by its own `initialize_schema`, `tools/deploy_namespace.py`) into separate
  namespaces so lanes cannot reset each other's data:

  | Namespace | Owner | Use |
  |---|---|---|
  | `USER` | validation lane | product test suites (`IVG_NAMESPACE=USER`) |
  | `AUDITCORE` | orchestrator | erase/redact/replay traces |
  | `AUDITENV` | orchestrator | IRIS environment contract (no product classes) |
  | `AUDITA` / `AUDITB` / `AUDITC` | breadth lanes A / B / C | targeted live checks of their modules |

  Use only your namespace. Do not restart, stop or reconfigure the container or create namespaces; ask the
  orchestrator. Wrap timing-sensitive work (performance, lock-wait timing) in
  `bash experiment/playbook-completion/tools/locks.sh iris <cmd>` so it runs alone.
- Journal oracle: `traces/journal.py` reads the IRIS journal server-side (nothing compiled): `mark()`,
  `records_since(mark, dbs={"/usr/irissys/mgr/<namespace lower>/"})`, `transactions()`, `storage_map(conn)`,
  `footprint()`. Use it to validate a declared write footprint independently of the source reading.
- Heavy jobs (> 4 GB or > 5 min: big explorer runs, Verus): `tools/locks.sh heavy <cmd>`, each with `timeout`.
- Cargo: `CARGO_TARGET_DIR=$RUN_DIR/target/<crate>`. Explorer and actors come from the local checkout
  `$IVG_EXPERIMENT/playbook-reference-actors` at `c03f9fa9be961610f2b274ffbb6a2c88d7d4d877` (see the original
  `experiment/playbook-uplift/model/Cargo.toml` for the dependency line).
- Stop only processes you started, by PID. Every wait loop has a timeout. Disk floor 60 GB free.

## Evidence

- Raw logs: `$RUN_DIR/<lane>/...`. Register each decisive run with
  `python experiment/playbook-completion/tools/register_run.py <id> <kind> <result> <log> --lane <lane> --command ... --observes ...`.
  One JSON file per run in `evidence/runs/`.
- Evidence grades (keep distinct, never upgrade one into another): `proved` (Verus, decisive, no trusted items),
  `mc` (explorer, bounded; say exhaustive-within-bounds or truncated), `trace` (real execution trace replayed through
  a machine), `live` (observed on the dedicated IRIS), `run` (an existing product test set passed here), `tested`
  (an upstream test exists, not run here), `inspected` (read in source at the pin, cite path:lines), `assumed`
  (named premise), `open` (human decision).

## Outcome taxonomy (four distinct non-pass outcomes)

| Outcome | Meaning |
|---|---|
| `blocked-access` | A dependency or credential is unavailable. Blocks only dependent tasks. Name the exact dependency. |
| `unrepresentable` | The operation lies outside a model's or tool's semantic subset. Name the operation and the subset. |
| `product-defect` | The as-built product violates an accepted contract (or its own docs). Record a finding; obligation stays failed. |
| `intent-undecided` | No authoritative source settles the intended behavior. Record the working assumption and alternatives. |

Pass outcomes: `holds-proved`, `holds-mc`, `holds-live`, `holds-run`, `holds-inspected` (weakest), `not-applicable`
(only with a cited source reason).

## Finding record (new or audited)

JSON object: `id` (keep original `F-NNNN` ids; new ones `F-C<module><nn>`), `module`, `title`, `intended`
(with source citations), `observed` (with evidence refs), `disposition` (from the taxonomy above or
`reproduced-live` / `reproduced-model` / `reproduced-test` / `confirmed-source` / `not-reproduced` / `refuted`),
`evidence` (list of `{kind, ref}`; `ref` is a registry id or `path:lines`), `gates` (playbook gates affected),
`severity` (S1 data loss/isolation, S2 integrity/false result, S3 docs/conflict, S4 minor), `confidence`
(high/medium/low), `remedy` (prose only), `notes`.
