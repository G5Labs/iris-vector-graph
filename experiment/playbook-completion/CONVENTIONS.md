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
  | `AUDITIA` / `AUDITIB` | intent lanes A / B | discriminating probes for decisions |

  Reassigned after their lanes finished (steer 7): `AUDITB` to the writesets lane, `AUDITIA` to the product-gates
  lane, `AUDITIB` to the semantics lane, `AUDITC` to the models-2 lane. `AUDITA` stays with the simulator's evidence
  (read only). New (steer 7, `incidents/NAMESPACES.md`): `AUDITD` structural lane, `AUDITE` trace-replay lane; `AUDITCORE` lent to the contract-2 lane for E-1 (the orchestrator does not use it meanwhile).

  Use only your namespace. Do not restart, stop or reconfigure the container; ask the orchestrator.
- **Scratch namespaces for pinned upstream fixtures (in scope, coordinated).** Some upstream test files under
  `tests/` (including some under `tests/unit`) create their own scratch namespace (`scripts/dev/make_scratch_namespace.py`)
  and compile the pin's unmodified classes into it. Running them is within the verification scope: it is the product's
  own fixture, not a product change. Run such a file only under `tools/locks.sh iris`, record the namespace in
  `incidents/NAMESPACES.md` (name, database directory, creating command, lane, UTC time) and leave it intact for
  attribution (do not drop it). A fixture setup that fails (for example `%AI` classes absent on Community) is recorded
  as a visible result (`incomplete` or `blocked` with the exact dependency), never discarded.
- Compiling anything other than the pin's own classes through the pin's own deploy path remains out of scope, with
  one operator-authorized exception (O-1, 2026-11-14, `incidents/O-1-FIXTURES.md`): the existing pinned upstream
  fixture's unchanged 4.5.1 release in its isolated migration-test namespace (`IVG262FC1306`) and the repository's
  unchanged `IVGDev` test helpers in `%SYS` are authorized verification setup. Record versions, namespaces, classes and
  effects for any such use; it authorizes test setup only, never repairs or weakened oracles.
- **Connection cap.** IRIS Community allows 8 connections in total for the whole container, shared by every lane
  (exceeding it fails with "Unable to allocate a license"; the identity probe then reports a mismatch). Therefore
  EVERY command that connects to IRIS runs under `bash experiment/playbook-completion/tools/locks.sh iris <cmd>`,
  holds the lock only for that command, and opens at most 6 connections at once. Long suites run in chunks (one
  directory or file set per lock hold) so other lanes can interleave. A license failure is infrastructure, not a
  product result: rerun under the lock, never record it as a pass or a product failure.
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
- A proved or model-checked **reviewed design** is a statement about a model. Report it as such ("the reviewed model
  satisfies ...") until a correspondence to the original code is discharged; the product's obligation stays as the
  as-built evidence says (failed/open). Never describe the product as satisfying a property only its reviewed model has.
- Decisive failure logs are retained: a rerun gets a new id; the original record and log stay.
- Journal oracle notes: the journal switches files (e.g. at midnight, compressed `*.z`); `records_since` follows the
  chain. Vector (`$vector`) values are recorded with `opaque: true` and no value.
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

New finding ids per lane (steer 7, to avoid collisions): `F-C<module><nn>` with nn 50-69 writesets, 70-79 semantics,
80-84 proofs-d9b, 85-89 models-2, 90-99 product-gates, 40-49 structural, 30-39 trace-replay, 20-29 contract-2, 15-19 refusals (steer 8). Root causes: `RC-NN` (reflection lane only).

JSON object: `id` (keep original `F-NNNN` ids; new ones `F-C<module><nn>`), `module`, `title`, `intended`
(with source citations), `observed` (with evidence refs), `disposition` (from the taxonomy above or
`reproduced-live` / `reproduced-model` / `reproduced-test` / `confirmed-source` / `not-reproduced` / `refuted`),
`evidence` (list of `{kind, ref}`; `ref` is a registry id or `path:lines`), `gates` (playbook gates affected),
`severity` (S1 data loss/isolation, S2 integrity/false result, S3 docs/conflict, S4 minor), `confidence`
(high/medium/low), `remedy` (prose only), `notes`.
