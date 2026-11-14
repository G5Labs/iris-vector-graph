# platform model: notes (worker B-platform, initial Verus uplift; revised for review round 1, 2026-11-14)

Product baseline `3eaa79cf`. The product was not modified.

Round 1 review (`.g5/uplift/ivg-verus-initial/review/round1-platform.md`) repaired here:
- **R1-3:** forged CRC-32 collisions. The persistent case and the mid-run swap are now separated, and the
  unique-name repair is proved.
- **R1-4:** the concurrent setup is a suspected defect against FR-005/FR-006. CAS alone versus the lock.
- **R1-5:** the waiver over a mismatch is an observed defect. Only the no-record case stays open.
- **R1-11:** per-path strict classification with formal weight; `_class_present`; migrations; the var-length item
  is closed.
- **Native results** are recorded below.

| Item | Location |
|---|---|
| Model | `.g5/Verus_verification/models/platform/platform.rs` (Part 1 O-SCHEMA, Part 2 O-WRITE-SURFACE, Part 3 cypher O2) |
| Controls | `model.json`: 30 controls, `expected_verified` 51 |
| Proof receipt | `.g5/Verus_verification/results/platform/20261114T002651Z-prove/receipt.json`: PASS, 51 verified, 0 errors |
| Control receipts | `.g5/Verus_verification/results/platform/20261114T*-control-*/receipt.json`, taken after the 002651Z prove (status in the Controls section). The 0013-0026 control receipts belong to an earlier file revision and are superseded. |
| Round-0 receipts (superseded, 35 verified, 21/21) | `.g5/Verus_verification/receipts/platform/20261113T23*` |
| Raw logs | `$RUN_DIR/verus/platform/` |
| Failed attempts, equivalent-mutant checks | `$RUN_DIR/agents/B-platform/failed-attempts.log`, `$RUN_DIR/agents/B-platform/scratch/` |
| Native observations | `.g5/Verus_verification/receipts/native/platform_*.json` |

To re-run: `source experiment/g5-verus/environment.sh; VERUS_RUN_THREADS=4 python3 .g5/Verus_verification/run_verus.py prove|controls .g5/Verus_verification/models/platform`.

Authority tags:
- **H**: human requirement.
- **D**: accepted decision.
- **O**: observed implementation only.
- **I**: intent decided by those sources.

---

## Part 1. O-SCHEMA: one IVG Schema per namespace

### Governing sources

- ADR-0016:11, 17 (**D**).
- Spec 262 FR-005 ("the first `initialize_schema()` … MUST record"), FR-006 and SC-006 (refused before any write, 0
  rows or globals changed), FR-009 (inference; an explicit name records it while other schemas' tables are
  reported) (**D**). US3 (**H**, second-hand).
- KNOWN_ISSUES:787-807 (**D/O**: the interrupted-setup window).

### L1 (I)

- (a) Once `^IVG.Deploy("schema")` names R, it names R.
- (b) After the record names R, nothing for T ≠ R writes. No engine, setup, deploy or migration on T creates objects
  or writes rows or globals.
- (c) A refusal changes nothing.

Model: `record_stable`, `post_writes_ok`, and the refusal clauses. Concurrency changes the implementation, not the
required outcome (R1-4). FR-009's explicit path is consistent with this L1.

### L2 and its L3 bindings (checked by the reviewer, unchanged)

| Model action | Product operation |
|---|---|
| `NewEngine` | `engine.py:366`, `1847-1872` → `check_first_access` (`schema_name.py:220-235`); pending `FirstAccessCheck` (`286-353`; `engine.py:385-390, 414-416`). `native_ok=false`: the check is skipped (`engine.py:1862-1866`). |
| `Access` | `guarded_connection` re-runs a pending check (`schema_name.py:356-373`). |
| `Write` | Any public write by an accepted engine. |
| `Waive` | `_waive_schema_check` → `_schema_check_passed` (`engine.py:1875-1890`); `graph_scoped_embeddings.py:288`, `temporal_structural_rows.py:89`. |
| `SetupRead` | `_engine/schema.py:2222` (read), 2224-2226 (mismatch), 2230-2242 (`held`/`how`). |
| `SetupDdl` | `_initialize_schema` DDL and routines (called at 2284), committed at 2572. |
| `SetupDeploy` | `refuse_other_record` (`schema.py:2888`; `class_deploy.py:357`). Its `IVGSchemaError` is swallowed at `_engine/schema.py:2591-2594`. |
| `SetupRecord` | `write_record` iff the read at 2222 saw nothing (2311-2312: an unconditional `native.set`, `schema_name.py:194-198`), `conn.commit()` (2313), then `_schema_check_passed` (2159-2160). Variants: `cas` (write only if no record exists at write time) and `cas_raises` (a lost CAS raises before the release). |

### Proved

- `lemma_s_init` and `lemma_s_step_preserves_inv` for `s_proved()`:
  - the lock (P-SERIAL);
  - P-NO-EXPLICIT-OVER-MARKER;
  - P-NATIVE-READABLE;
  - P-WAIVE-HARMLESS.
- `theorem_schema_one_per_namespace`.
- `theorem_refusal_changes_nothing` (as built).

Premise owners:

| Premise | Who establishes it |
|---|---|
| P-SERIAL | Operator today; proposed lock |
| P-NO-EXPLICIT-OVER-MARKER | Human decision (F-S3) |
| P-NATIVE-READABLE | Deployment (ADMIN_GUIDE:515-518) |
| P-WAIVE-HARMLESS | Product code. Violated today: B2 |

### Witnesses (proved traces)

- **W-S1** `witness_concurrent_first_setups_overwrite_the_record`: both setups read "no record"; the record changes
  Graph_KG → IVGALT; the loser's engine writes under the winner's record.
- **W-S1b** `witness_deploy_refusal_is_swallowed`: the deploy's refusal is kept as a warning; setup overwrites the
  record after creating IVGALT objects in a namespace recorded Graph_KG.
- Partial repairs:
  - `witness_reraise_alone_is_not_enough`: re-raising the deploy refusal does not stop W-S1.
  - **R1-4** `witness_cas_alone_still_releases_the_second_engine`: a CAS record write keeps Graph_KG recorded. But
    setup 2 still reaches `_schema_check_passed`, and its released engine writes, so `!post_writes_ok`. This is the
    reviewer's Adv-1, now in the model.
  - **R1-4** `witness_cas_with_raise_still_admits_late_ddl`: CAS plus a raise that does not release the engine
    closes the release. But in W-S1b's order setup 2's DDL lands after the record, so IVGALT objects exist in a
    Graph_KG namespace and (b) is broken.
- `witness_lock_refuses_the_second_setup` plus the serial theorem: only the lock refuses the second setup before it
  writes.
- **W-S2** `witness_waiver_releases_a_mismatch`.
- **W-S3** `witness_interrupted_setup_then_explicit_schema`.
- **W-S4** `witness_unreadable_record_skips_the_check`.
- Valid outcome: `witness_serial_first_setup_and_refusal`. The reviewer's Adv-4 also shows the interrupted-setup
  resume survives the repairs (`$RUN_DIR/agents/R3-platform/adv/adv4_platform_resume.log`).

### Native observations

| Probe | Verdict |
|---|---|
| `platform_schema_refusal` | **OBSERVED_AS_EXPECTED**. An engine on `IVGPROBE` is refused, naming Graph_KG and IVGPROBE, on `node_count`, `list_graphs` and `initialize_schema(dry_run=True)`. Nothing changed. |
| `platform_schema_waiver` | **OBSERVED_DEFECT**. The control engine on IVGPROBE is refused (`IVGSchemaError`). `migrate_to_graph_scoped_embeddings(dry_run=True)` returned a report. `backfill_structural_rows(dry_run=True)` reached SQL on `IVGPROBE.RDF_EDGES` (SQLCODE -30). Snapshot unchanged. |

W-S1 is not probed: it needs two concurrent setups and a throwaway namespace (a second schema).

### Not represented

- Case-variant spelling (F-S6). Dry runs. Legacy removal.
- Other best-effort deploy failures (F-S5). `/health`. Non-IRIS connections.
- Time.

---

## Part 2. O-WRITE-SURFACE: strict ledger mode

### Governing sources

- Spec 213 `contracts/ledger-api.md:82-92` (**D**): the guarded list; "`BulkLoader` and raw SQL are not guarded
  (documented)".
- USER_GUIDE:1107-1120 (**D**: "the other methods"); USER_GUIDE:1085-1090 (**D**: the temporal derived row is outside
  the ledger).
- ADR-0006:34 (**D**): "Embedding writes sit entirely outside it".
- ADMIN_GUIDE:631-636 (**D**): MCP `RunSQL` runs any SQL by design.
- ADR-0004:79-82 (**D**): `bulk_delete_adjacency` "is removed rather than deprecated". It is still present: doc drift.
- ADR-0013 (**D**): erase, then redact.
- `ledger/guard.py:1-7` (**O**): TTL and fail-open.

### L1 (I)

With the ledger enabled and strict, a structural write outside the ledger on a path the contract covers is refused
and changes nothing. A call that begins after `set_strict(True)` returned must be refused. An overlapping call may
commit.

Two readings:
- `strict_ok`: the contract as written. It covers the guarded paths and the undocumented bypasses.
- `strict_ok_all`: strict also governs the undecided paths.

### Per-path classification (R1-11)

`class_of` in the model; each class is pinned by a witness and a control.

| Class | Paths (model `Path`) | L3 | Witness / control |
|---|---|---|---|
| Guarded | `CreateNode`, `CypherDml`, `EraseGraph`, `OtherGuarded` (the contract list and store writers; the temporal backfill migration writes through `create_edge`) | `nodes_edges.py:1005, 1513, 1553, 1581`, `query.py:2299-2301`, the call sites listed in round 0 | `theorem_strict_paths`; `g-no-refusal` |
| Documented exemption | `BulkLoader`, `RawSql` (SQL or Native API, **MCP `RunSQL`**), `TemporalDerived` | ledger-api.md:92; ADMIN_GUIDE:631-636; USER_GUIDE:1085-1090 | `witness_exempt_and_out_of_scope_writes_are_permitted` |
| Outside ledger scope | `IndexWrite`: embeddings, IVF/VecIndex/PLAID, BM25 | ADR-0006:34; spec 213 governs structural writes | same witness; `g-index-writes-undecided` |
| Undocumented bypass (contradicts the contract or "the other methods") | `BulkDeleteAdjacency` (`nodes_edges.py:2301-2338`); `ApiSample`: api.main `/api/cypher` and GraphQL `executeCypher` (`api/routers/cypher.py:130-166`, `api/gql/schema.py:174-200`), and the example `updateProtein` mutation (raw `rdf_props` writes, `examples/domains/biomedical/resolver.py:263-275`) | no `ledger_check` | `witness_undocumented_bypasses_break_the_contract`; `g-bda-guarded` |
| Undecided (no source decides) | `FhirSync` (`_engine/fhir_graph.py:255-258`), `McpCypher` (`MCPTools.cls:9-29`), `Migration` (`upgrade_to_4_0_0`, `upgrade.py:130-292`; `rekey_kg_node_stores` kills and rebuilds `^KG`, `kg_node_stores.py:175-180`), `SetMultigraph` (`_engine/admin.py:893`), `PropSetProc` (`Prop_Set`, `SqlProcs.cls:187`; `Txn_*` 168-178, called directly) | no check | `witness_undecided_paths_write_under_strict` (contract silent, all-paths reading broken); `g-fhir-exempt` (the reviewer's Adv-3b, now detected) |

Guard-mechanism gaps:

| Gap | Mechanism | Witness / control |
|---|---|---|
| 5 s TTL | `guard.py:20, 38-59`; `set_strict` refreshes only the caller (`client.py:305-309`) | `witness_ttl_window_admits_a_write_after_set_strict`; `g-ttl-zero`, `g-set-strict-no-refresh` |
| Fail-open probe | `guard.py:55-58` | `witness_failed_probe_admits_a_write`; `g-fail-closed` |
| **`_class_present` cached for the guard's lifetime** | `guard.py:45-49` | `witness_class_absent_cached_for_the_engines_lifetime`; `g-class-present-recomputed` |

On `_class_present`: an engine whose first guarded call ran while `Graph.KG.Ledger` was not compiled never reads
`Meta()` again. That can happen after a failed best-effort deploy, or after setup with
`auto_deploy_objectscript=False`. After the class is deployed and strict is on, that engine's writes are admitted
past every TTL, while a new engine is refused.

Closed (R1-11, the reviewer's A5): a Cypher write cannot reach the var-length route
(`query.py:2290-2297`) before `_ledger_check`. A transactional `SQLQuery` is built without `var_length_paths`
(`translator.py:6043-6049`).

### Proved

- `lemma_g_step_preserves_inv` (any `GVariant`), under:
  - P-PROBE-OK: the Meta probe answers, and the ledger class is compiled at each guard's first probe;
  - P-NO-STALE-CACHE: vacuous at TTL 0 (`lemma_ttl0_needs_no_cache_premise`) or with one engine;
  - P-PATHS: vacuous with `guard_all`.
- `theorem_strict_paths` (as built): a guarded path is refused and changes nothing. An unguarded path is admitted;
  its write breaks `strict_ok` exactly when it is an undocumented bypass, and `strict_ok_all` exactly when it is not
  exempt.
- `lemma_strict_ok_all_implies_strict_ok`.
- `theorem_strict_blocks_named_graph_redaction`.

### Native observations

| Probe | Verdict |
|---|---|
| `platform_strict_paths` | **OBSERVED_AS_EXPECTED**: `create_node`, Cypher CREATE and `erase_graph` raise `LedgerStrictModeError` and change nothing. Side observation: `rej_strict_block` grew by 2, not 3. `count_rejection` swallows its own failure (`guard.py:82-86`); not investigated, and it did not decide the verdict. |
| `platform_strict_bulk_delete_adjacency` | **OBSERVED_DEFECT**: under strict the call returned, the edge was deleted unrecorded, and `verify()` went from `equal` to `diverges`. |
| `platform_strict_api_sample` | **OBSERVED_DEFECT**: the strict-off control wrote. Under strict, the api.main handler committed `CREATE` unrecorded (HTTP 200), while the engine path raised `LedgerStrictModeError`. |
| `platform_strict_ttl` | **OBSERVED_DEFECT**: engine 2 wrote `ttl-bypass` 0.001 s after `set_strict(True)` returned (its cached probe was under 0.1 s old). The engine that set strict was refused at once. After the 5 s TTL engine 2 was refused. |
| `platform_strict_redaction` | **Consequence observed** (verdict OBSERVED_AS_EXPECTED). Under strict, `erase_graph(tenantG)` is refused. Ledger deletes of the relationship and both nodes leave 2 node rows in tenantG. `redact` is refused `target_live` ("nodes 2"). With strict off, erase (2 rows) and redact complete. |

FHIR sync and MCP are not probed: Community has neither IRIS for Health nor %AI. `_class_present` and the migrations
are not probed.

### Not represented

- Row content beyond the tenant graph. Caller-open transactions.
- Ledger commit internals (the ledger_redaction model).
- `IVG_READ_ONLY`.

---

## Part 3. Cypher O2: a compiled class runs only for its own plan

### Governing sources

- ADR-0014:16-23 (**D**). `CONTEXT.md` "Compiled plan" (**D**). Spec 257 (**D**).
- 4.6.0 R311 (**D**): a role with RW may set the entry and the lines.

### L1

Every `Walk1` a run executes is the code written for that run's (shape, stamp) (`execs_ok`). An absent, pending,
failed or unrecordable entry interprets. A deploy discards all plans.

### L2 and its L3 bindings (checked by the reviewer: `Gen.cls:61-222`)

These are as in round 0:
- `ForCheck` binds `Gen.cls:63-77` (line 73: the name check);
- `ForEntry` 80; `ForSrc` 81-91; `ForSpawn` 92-101; `ForInlineBuild`/`ForReadBack` 101-103 (no name or shape
  check);
- `JobBuild` `Gen.Build` 163-222 (checks the lines' digest, not the entry's shape);
- `Walk`: `Exec.cls:199, 258` after one `For` per run (`Exec.cls:158`);
- `Deploy`: `schema.py:2935-2941`.

Class names are now a `CName`:
- `P(h)`: IVGC.P<CRC-32>, as built;
- `D(n)`: named by the lines' SHA-256, the proposed repair;
- `Other`: any other class.

`PVariant` switches the three repair components: `build_checks`, `unique_names`, `readback_checks`.

### Proved (as built)

- `lemma_for_hit_checks`, `lemma_for_interprets_otherwise`, `lemma_deploy_discards`.
- `lemma_p_init`, `lemma_build_preserves`, `lemma_p_step_preserves_inv`: L1 for every interleaving, under:
  - **P-NO-COLLISION**, which nobody establishes (see R1-3);
  - P-QUIESCENT;
  - P-NO-PLANT-ENTRY;
  - P-SHA.
- `lemma_crc_collision_exists` (pigeonhole) and `lemma_colliding_shapes_with_different_code` (P-CODE-VARIETY).

### Forging (R1-3)

- `lemma_forge_collision`, under **P-CRC-AFFINE**. CRC-32 is affine over GF(2); four appended bytes are a bijection
  of its 32-bit state. So for any target shape there is a 4-byte suffix of a chosen label that hits the target's
  CRC-32. Proved with `lemma_map_size` and `lemma_subset_equality`.
- `witness_reader_forges_a_collision_and_poisons_a_shape`:
  - Every action is an ordinary read; nothing is planted.
  - The attacker runs its forged shape and the victim's shape in job mode, and its own job builds first (W-O2b's
    order).
  - Every later run of the victim's shape walks the attacker's code until a deploy, a stamp change, or a new run of
    the forged shape. A label that matches nothing makes the victim's read answer no rows.
  - It needs Cypher read access through a login that can write `^IVG.CypherCompiled`: the default `_SYSTEM`, any RW
    role, and also `IVG_READ_ONLY` servers, since reads write compiled plans.
- The reviewer's estimate for accidental collisions (birthday bound): about 1.2% at 10⁴ distinct shapes between
  deploys, plus a millisecond interleaving. The adversarial case is practical.

### Which repair closes what (R1-3)

| Case | Build shape/stamp check | Read-back checks | Unique names (`D<sha256>`) |
|---|---|---|---|
| Persistent poisoning, W-O2b and the forged attack | **closes it**: `witness_build_check_closes_the_persistent_case` (a's job refuses an entry written for b; b stays interpreted) | — | does not close it alone: `witness_unique_names_alone_leave_the_persistent_case` (the entry names a's `D` class) |
| Mid-run swap, W-O2a | **does not close it**: `witness_build_check_leaves_the_mid_run_swap` (with the read-back checks too) | — | closes it: a class name never changes its code |
| Read-back race | — | needed: `witness_unique_names_need_the_readback_check` (with unique names and the build check, a's read-back after b's build is given b's class; the repaired read-back returns None on that state) | — |
| Straggler with an old layout, W-O2c | — | — | closes it (an old-layout class gets its own name) |

- `lemma_q_build_preserves`, `lemma_q_step_preserves_inv`, `lemma_q_init`: the **full repair** (`p_repaired()`:
  unique names + build check + read-back checks) satisfies L1 for every interleaving. That includes colliding
  shapes, concurrent deploys, `rdf_props` recompiles and planted lines. Only P-SHA and P-NO-PLANT-ENTRY remain;
  P-NO-COLLISION and P-QUIESCENT are no longer needed.
- Controls `r-no-build-check`, `r-no-unique-names` and `r-no-readback-check` each make the repaired system fail.
  - The first two fail in `lemma_q_build_preserves`, which is where the build check and the naming are consumed.
    `r-no-unique-names` also fails in `witness_repair_keeps_both_colliding_plans`.
  - `r-no-readback-check` fails in `lemma_q_step_preserves_inv`.
  - Their semantic counterexamples are the witnesses in the table above.
  `p-as-built-with-build-check` makes W-O2b and the forged attack fail; W-O2a has its own witness under that check.
- Valid outcome under the repair: `witness_repair_keeps_both_colliding_plans`. Two colliding shapes each compile
  their own `D` class, and each run walks its own code. The repair does not stop compiled plans from being used.
- Other witnesses, as in round 0:
  - W-O2a `witness_collision_swaps_the_class_mid_run` (the product claim also needs P-RELINK);
  - W-O2b `witness_collision_leaves_another_shapes_code_under_an_ok_entry`;
  - W-O2c `witness_straggler_recompiles_for_an_old_layout`;
  - W-O2d `witness_readback_trusts_the_entrys_class`;
  - valid outcome `witness_compiled_plan_is_used`.
- Equivalent mutants (round 0, `scratch/eq-*`): without collisions the shape comparison is redundant; without
  planted entries the name check is redundant.

Not probed. The proposed probe is a test hook that fixes `tH`, or a crafted collision through the planner of the same
version.

### Not represented

- Mode `off`, non-direct layout, compile errors, parallel workers, O1 answer equality.
- Liveness: a stale job can mark a fresh entry refused (round-0 note).

---

## Trust inventory

- `uninterp spec fn`:
  - `crc32(Shape) -> u32`;
  - `lines_of(Shape, Stamp) -> int`;
  - `digest(int) -> int`;
  - `forged(int, int) -> Shape`: the shape whose label is a chosen base plus four free bytes.
- Premises are carried as `requires` or predicates, never assumed:
  - the premise tables above;
  - `digest_injective()` (P-SHA);
  - `crc_suffix_bijective` (P-CRC-AFFINE);
  - the witnesses' requires.
- No `assume`, `admit`, `external_body` or `assume_specification`.
- Library: bundled vstd 0.2026.10.04 (`lemma_int_range`, `lemma_map_size`, `lemma_len_subset`,
  `lemma_subset_equality`, `Set::lemma_map_contains`).
- The model is a transcription. The Python and ObjectScript bodies are not verified.

## Controls (`model.json`, 30)

Attribution fix, round 1: in the first control run on the revised file, `r-no-build-check` and `r-no-unique-names`
were FAIL_ELSEWHERE. Each named `lemma_q_step_preserves_inv`, which still verified on its own, because it relies on
`lemma_q_build_preserves`'s contract; the failures were in that build lemma. The expectation now names the build
lemma. This is the same pattern as `p-no-digest-check` → `lemma_build_preserves`. It was not a weak contract: the
build lemma is where those two repair components are used. Logs:
`$RUN_DIR/verus/platform/20261114T0023*-control-r-no-*.log`.

Each control names the functions that must fail; see `model.json` for the exact find/replace.

- **Part 1:**
  - `s-no-mismatch-refusal`, `s-no-first-access-check`;
  - `s-serial-off`, `s-explicit-over-marker-allowed`;
  - `s-deploy-reraise`;
  - `s-waive-checks` (now: waive only with no record, R1-5);
  - `s-setup-does-not-release` (valid outcome);
  - `s-cas-raise-releases` (new).
- **Part 2:**
  - `g-no-refusal`, `g-set-strict-no-refresh`;
  - `g-bda-guarded`;
  - `g-fhir-exempt` (new, Adv-3b), `g-index-writes-undecided` (new), `g-class-present-recomputed` (new);
  - `g-ledger-deletes-named-nodes`;
  - `g-ttl-zero`, `g-fail-closed`.
- **Part 3:**
  - `p-no-class-name-check`, `p-no-stamp-check`, `p-no-shape-check`;
  - `p-no-digest-check` (now also `lemma_q_build_preserves`);
  - `p-no-dropall`;
  - `p-build-never-ok` (valid outcome; also the repair's valid witness);
  - `p-collision-premise-dropped`, `p-quiescence-premise-dropped`;
  - `r-no-build-check`, `r-no-unique-names`, `r-no-readback-check` (new);
  - `p-as-built-with-build-check` (new), `p-forge-needs-affine-crc` (new).

---

## Candidate findings (statuses after the native runs)

### Bugs

**B1. Concurrent first setups overwrite the IVG Schema record and both schemas write.** Medium. Proved model trace;
**SUSPECTED** product defect against I: FR-005, FR-006/SC-006, ADR-0016.
- Mechanism: read at 2222, unconditional write at 2311-2312, no lock. The deploy's re-check is swallowed (2591-2594).
- Reachable in production: two `initialize_schema()` calls with different prefixes whose 44-62 s windows overlap.
  Examples are the hipporag2 RAG-beside-Graph_KG setup ADR-0016 names, or two deployers.
- Repair: `LOCK +^IVG.Deploy("schema")` from read to record. CAS alone, and CAS plus a non-releasing raise, are
  insufficient (both proved).
- Not probed: it would create a second schema.

**B2. The migration waiver releases a mismatch refusal.** Medium. **OBSERVED_DEFECT**
(`receipts/native/platform_schema_waiver.json`) against I (FR-006, no exception for migrations).
- The comment at `engine.py:1887-1890` justifies only "before any 4.6.0 setup recorded the schema".
- Related, F-S12: the embeddings and `^KG` steps use the default schema and the real globals (`upgrade.py:145-152`).
  So on an FR-009 two-schema namespace a default-schema migration can rebuild the shared `^KG` from the other
  schema's rows.
- Repair: waive only when there is no record (control `s-waive-checks`), or build the migration engine on the record.
- Open sub-case (Q): no record yet. FR-006a's letter against the documented 4.0.0 upgrade order.

**W1. `bulk_delete_adjacency` bypasses strict mode.** **OBSERVED_DEFECT**
(`receipts/native/platform_strict_bulk_delete_adjacency.json`). Against spec 213, USER_GUIDE "the other methods", and
ADR-0004:81 (the method should be gone).

**W2. api.main `/api/cypher`, GraphQL `executeCypher` and the example `updateProtein` mutation bypass strict mode.**
**OBSERVED_DEFECT** for `/api/cypher` (`receipts/native/platform_strict_api_sample.json`). GraphQL and the mutation
are from source reading.

**W-TTL. A write is admitted after `set_strict(True)` returned.** **OBSERVED_DEFECT** under the reading "strict from
the moment `set_strict` returns" (`receipts/native/platform_strict_ttl.json`). Under the reading "eventually, within
5 s per engine", it is a documentation gap (Q2 below).

**P1. Compiled-plan poisoning through a CRC-32 collision.** High, security/integrity. Proved model traces including
the forged-collision attack; **SUSPECTED** in the product (not probed).
- A Cypher-read caller can make another caller's shape run its code persistently.
- Repair:
  - name classes by the lines' SHA-256;
  - add Build's shape/stamp check;
  - add the read-back checks.
- The full repair is proved (`lemma_q_step_preserves_inv`). The build check alone closes the persistent case but not
  the mid-run swap.

**P2 / P3.** As in round 0: the old-layout straggler and the read-back name check. Both are low severity, and both
are closed by the proved repair.

### Open questions

- **Q1 (F-S3):** explicit over an interrupted 4.6 setup (W-S3).
- **Q2:** the TTL semantics.
- **Q3:** fail-open probes, and `_class_present` cached for an engine's lifetime.
- **Q4:** strict mode blocks the erase-then-redact order for a named graph. Observed: `platform_strict_redaction`.
  Options:
  - allow erase under strict as a recorded operation;
  - make the ledger's node deletes graph-aware;
  - document the strict-off window.
- **Q5:** do FHIR sync, MCP `CypherQuery`, migrations, `set_multigraph` and direct `Prop_Set`/`Txn_*` fall under
  strict mode? Today they are undecided bypasses.
- **B2 sub-case:** the waiver with no record.

### Simplifications

- **S1:** one server-side strict gate. It removes the TTL window, the fail-open, `_class_present`, and the
  Python-only coverage.
- **S2:** digest-named compiled classes plus Build's and the read-back's checks (proved).

### Doc drift

- ADR-0004:81 says `bulk_delete_adjacency` is removed; it is present (API_REFERENCE:418).
