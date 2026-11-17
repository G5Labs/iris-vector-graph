# Iteration 56 Part B: install lifecycle — frozen neighboring predictions

Frozen before reading any deciding source (`iris_vector_graph/schema_name.py`, `schema.py`, `_engine/schema.py`,
`_engine/class_deploy.py`). Sources used: owners `install.schema*`, `install.setup*`, `install.deploy*`,
`install.upgrade*`, `search.embedding*`, `search.quarantine*`; `docs/ADMIN_GUIDE.md` §2 (setup, "One IVG Schema per
namespace", "Running setup again", "What setup replies"), §9 "Embedding tables, the registry and the quarantine", §11
troubleshooting; `CHANGELOG.md` (4.6.0 schema entries, 4.0.0 quarantine, 4.2.1, 4.7.0 rewidth). Each row: the input or
history that changes, the reader, and the expected difference. Fixture: fresh namespaces `I56S*` in
`ivg-cont-20261117-iris`.

| # | Workflow | Changing input / history | Reader | Prediction A | Prediction B (neighbor) | Source |
|---|---|---|---|---|---|---|
| A1 | setup: fresh vs existing | namespace never set up vs set up once | `initialize_schema()["schema_recorded"]`, `^IVG.Deploy("schema")` | fresh: `new`, record written = engine's schema, `tables_created` 18 | second run: `existing`, `tables_created` `[]`, record unchanged | ADMIN_GUIDE "What setup replies", install.setup |
| A2 | setup: mismatched schema | record `Graph_KG`, second engine `schema_prefix="I56ALT"` | engine first call; `initialize_schema()` by that engine | engine's first public call raises `IVGSchemaError` naming both schemas, nothing written | same namespace, engine with the recorded name: call answers | install.schema.refusal |
| A3 | setup: tables in another schema, no record | IVG tables present only in schema X (record removed), engine for Y | setup | refuses, names X, records nothing (even with Y explicit) | engine for X: `schema_recorded` = `inferred`, record X | install.schema.existing |
| A4 | setup: dry run | `dry_run=True` on a fresh namespace vs a real run | `^IVG.Deploy`, catalog tables, reply | dry run: nothing written (no record, no tables); reply lists 18 tables, 58 routines, `schema_recorded` `new` | real run creates those 18 tables and writes the record | install.setup.dry_run, ADMIN_GUIDE |
| A5 | setup: resume | record killed after a complete setup (objects present, no record) | engine first call; next setup | engine refused "setup has not finished here"; status reports `schema` None | next setup records (`inferred`), engine then answers; state equals one uninterrupted run | install.setup.resume, install.schema.not_ready |
| A6 | schema name validation | name `1abc` / `SQLUser` / `%X` / `Graph_KG` package clash vs `I56_OK` | `IRISGraphEngine(..., schema_prefix=)` | invalid: `ValueError` naming the rule before any DB call | valid name accepted; names differing only in case are the same schema | install.schema.name |
| B1 | first access on a non-set-up namespace | empty namespace (no IVG objects) vs namespace with only 4.5.x `SQLUser` objects | engine first public call message | "never been set up for IVG" | "set up by an earlier IVG release and has not been upgraded" | install.schema.not_ready, ADMIN_GUIDE errors |
| B2 | first access: exempt calls | refused namespace | `status()`, `initialize_schema` | `status()` answers with `schema` None and the reason | an ordinary call (`count_nodes` / `execute_cypher`) raises `IVGSchemaError` | CHANGELOG 4.6.0 |
| C1 | class deploy: unchanged sources | second setup with the same package | `objectscript_compiled` | `[]` (skipped), `objectscript_deployed` True | `IVG_FORCE_CLASS_DEPLOY=1`: recompiles every class | ADMIN_GUIDE "Running setup again" |
| C2 | class deploy: fingerprint change | `^IVG.Deploy("fingerprint")` altered (as after an upgrade) or a class deleted | `objectscript_compiled` | differing fingerprint: recompiles all classes | same fingerprint but a class not compiled: redeploys (skip only when every class compiled) | install.deploy, ADMIN_GUIDE |
| D1 | embedding width: empty table | configured 8 vs recorded 768, `kg_NodeEmbeddings` empty | setup | plain setup raises `EmbeddingIdentityConflict`, width unchanged | `rewidth=True`: column re-declared at 8, registry width 8 | ADMIN_GUIDE §11 (4.7.0) |
| D2 | embedding width: populated table | configured 8 vs a table holding 768-wide vectors | setup reply, dry run | plain setup: table named in `needs_manual_migration` + warning, no alter, vectors kept | `rewidth=True` raises; dry run lists it under `needs_manual_migration` | ADMIN_GUIDE §11, search.embedding.width |
| D3 | embedding write vs recorded identity | write of width 8 into a table recorded 768 vs width 768 | `store_embedding` | width 8: refused before writing (dimension mismatch / `EmbeddingIdentityConflict`) | width 768: written | search.embedding.check_on_write |
| E1 | adopt identities on legacy rows | setup on a namespace whose legacy table has no registry row | `embedding_registry` | row with the declared width, `set_by` `adopted`, model unknown | engine declaring a model: `set_by` `claimed`, model recorded; later different model refused unless `force=True` (`forced`) | ADMIN_GUIDE §9, search.embedding.claim |
| F1 | place quarantined vector | route exists with same width and node in graph vs node absent from graph | `place_quarantined`, `list_quarantine` | succeeds: row copied into route, removed from quarantine | node absent (or route width differs / no route): raises, row stays in quarantine; never creates a route | search.quarantine.placement, CHANGELOG 4.0.0 |
| F2 | place quarantined: route already holds node | route already has a vector for that node | `place_quarantined` | route refuses the copy; vector stays in quarantine | — | search.quarantine.placement |

Committed alone, before the deciding source was opened.

---

## Result (written after the freeze commit `4f1c5d25`; not part of the freeze)

Observations: binding receipt
[20261117T071614Z](../../../Verus_verification/results/install_lifecycle/20261117T071614Z-binding/receipt.json)
(AGREES 138 against the model; the raw observations are in the receipt), first probe runs
[observed-20261117T065715Z.json](install/observed-20261117T065715Z.json) and
[observed-20261117T065950Z.json](install/observed-20261117T065950Z.json), and the case probe
[case-observed-20261117T070557Z.json](install/case-observed-20261117T070557Z.json). Fresh namespaces I56SA-I56SD.

| # | A | B (neighbor) | Verdict | What was observed |
|---|---|---|---|---|
| A1 | held | held | **held** | fresh: `new`, 18 tables, record `Graph_KG`; re-run: `existing`, no table, nothing compiled, record unchanged |
| A2 | held | held | **held** | `I56ALT` engine: first call, setup, dry run and `deploy_packaged_classes` all refused naming both; `status()` answers `Graph_KG`; the recorded name in lower case is accepted |
| A3 | partly | held | **partial (miss)** | no name: refused naming `I56X`, nothing recorded (held); named `I56Y` (argument or environment): the dry run plans `explicit` and setup records `I56Y`, then `I56X`'s engine is refused (missed: the owner/FR-009 reading; bug-plt-026 reproduced) |
| A4 | held | held | **held** | dry run: no record, no table, no fingerprint, engine still refused; reply 18 tables, 58 routines, `new`; the real run created those 18 |
| A5 | missed | held | **miss** | record removed after a complete setup: the next engine is **admitted** (this release's marker function is there; KNOWN_ISSUES; bug-plt-133); next setup `inferred` and the record back (held). With the marker function also dropped the engine is refused "setup has not finished" |
| A6 | held | held | **held** | `1abc`, `SQLUser`, `sqluser`, `%X`, `""`, `a-b`, `Graph_KG_x`, `IVG_A`, `IVGC` → `ValueError`; `I56_OK` accepted; `graph_kg`/`GRAPH_KG` → `Graph_KG`; argument over environment; `IRIS_SCHEMA_PREFIX` ignored. Not frozen: a setup by the other-case engine misbehaves (bug-plt-015) |
| B1 | held | held | **held** | empty namespace "never been set up"; an earlier-release class "set up by an earlier IVG release"; (also) only an IVG global "setup has not finished" |
| B2 | held | held | **held** | `status().schema` None on a refused namespace; the ordinary call raises |
| C1 | held | not run | **held (A only)** | re-run: `objectscript_compiled` empty, `plan_packaged_classes(...).unchanged` True; `IVG_FORCE_CLASS_DEPLOY=1` not tried |
| C2 | held | held | **held** | fingerprint altered: plan not unchanged, setup compiles every class and writes the fingerprint back; `IVG.Percentile` deleted: plan not unchanged, setup recompiles, class back |
| D1 | held | held | **held** | width 8 → engine 16, tables empty: setup raises `EmbeddingIdentityConflict`, column stays 8; `rewidth=True` re-declares all three at 16, registry 16 (`adopted` kept) |
| D2 | missed | held | **partial (miss)** | a populated table at 16 beside empty ones: plain setup at 8 **raises** (the empty ones need rewidth), no `needs_manual_migration` reply (bug-plt-134); `rewidth=True` raises (held); dry run lists the populated table under `needs_manual_migration` (held) |
| D3 | held | held | **held** | 8-wide write to a 16-wide table refused (dimension mismatch); 16-wide written |
| E1 | held | held | **held** | setup adopts (width from the column, model unknown, `adopted`); a declared model claims it (`claimed`); the same key in other case/spaces is kept; another model refused; `force=True` → `forced`; a deleted legacy edge row re-adopted as an edge route; a second adoption changes nothing |
| F1 | missed | held (row stays) | **miss** | every placement of an existing row fails "Cursor closed" (bug-srch-116); the row stays. With the row read repaired (harness substitution): placed (−1/+1) and every documented refusal, row kept |
| F2 | not reached | — | **held under the repair only** | the second vector for the node is refused by the route's key (SQLCODE -119); the row stays |

Totals: 16 frozen workflows, 32 predictions; 10 workflows held in full, 1 held in A only (C1, B not run), 2 partial,
2 missed, 1 held only under the repair. Material predictions gained: the record decision with an explicit name, the
admission of an unrecorded namespace with this release's objects, the width refusal across sibling tables, the
case-variant width bypass, and that placement is unusable over the DB-API driver. Withdrawn: none.
