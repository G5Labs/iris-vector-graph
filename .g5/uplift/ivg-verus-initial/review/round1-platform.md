# Round 1 review: platform, access, Cypher, search, FHIR, algorithms (R3-platform)

Reviewer R3-platform, stage C round 1, 2026-11-13. Product baseline `3eaa79cf` (worktree `0e441f1c`). Product and
`.g5/` artifacts were read only. Scratch and raw logs: `$RUN_DIR/agents/R3-platform/`
(`$RUN_DIR` = `/home/ziniu_wu_g5labs_ai/runs/iris-vector-graph-g5-verus-20261113`).

## Independent expectations

I wrote these before opening any `.g5/` artifact, from CONTEXT.md, ADR-0004/0005/0006/0007/0013/0014/0016, specs 044,
213 (contracts), 235, 236 (contracts), 253, 257 and 262, USER_GUIDE, ADMIN_GUIDE, KNOWN_ISSUES and the code entry
points. The snapshot taken then is `$RUN_DIR/agents/R3-platform/expectations.md`.

**Install and schema**
- I1. A name is validated before any database call. Names that differ only in case are one schema.
- I2. An engine whose schema differs from the record is refused on first access, before any write, and nothing changes
  (FR-006, SC-006).
- I3. With no record, FR-009 decides: tables in the engine's schema are inferred; one other schema is refused; several
  schemas stop setup unless one is named explicitly.
- I4. A dry run writes nothing. An interrupted setup resumes to the same end state.
- I5. Competing first setups. `_record_and_initialize` reads the record at `_engine/schema.py:2222` and writes it
  unconditionally at 2311-2312 if that read saw none. Nothing locks the interval, which ADMIN_GUIDE puts at 44-62 s.
  FR-005, FR-006 and ADR-0016 ("instead of sharing globals silently") still decide the outcome: the second schema must
  not be recorded and must not write.
- I6. Legacy objects are listed and removed only from the manifest, never by pattern. Grants are copied. The Arno
  revoke is the single exception to "in place and working". A deploy drops compiled plans (FR-014).
- I7. FR-006 makes no exception for migrations. `_waive_schema_check` releases a mismatch refusal as well as the
  no-record refusal.

**Access**
- A1. With a key set, every route except the exact public paths needs it. With no key, the server binds
  `0.0.0.0:8200`.
- A2. `IVG_READ_ONLY` refuses `/admin/` write methods by path, Cypher writes by the parser (failing closed), GraphQL
  mutations in their resolvers, and FHIR events. This is an application gate; the database resource is the real
  boundary.
- A3. Strict mode refuses the methods the 213 contract lists. Documented exemptions: BulkLoader, raw SQL, and the
  temporal mirror. In code, the guard fails open when its probe fails, caches its answer per engine for 5 s, and caches
  `_class_present` for the engine's lifetime.
- A4. Writers with no guard: `bulk_delete_adjacency` (deletes edge rows in every graph), FHIR sync, the sample API's
  Cypher and GraphQL paths, MCP, and the `Prop_Set` and `Txn_*` procedures.
- A5. Ruled out: a Cypher write reaching `_route_var_length` before `_ledger_check`. A transactional `SQLQuery` never
  carries `var_length_paths` (`translator.py:6043-6049`).

**Cypher**
- C1. Native execution runs only for read-only, fully supported queries, only where the index is declared, never
  inside `bulk_load_session`, and only for a caller with SELECT on the four tables (FR-011). Native equals SQL, and any
  native error falls back to SQL.
- C2. `USE GRAPH g` reads and writes g. With no `USE GRAPH`, a read is the union of each graph's own answer. `SET`,
  `REMOVE` and `DELETE` act in the bound node's own graph; `CREATE` and `MERGE` write the default graph.
- C3. A compiled plan answers as the interpreter does. A stale entry never runs. Mode `off`, and a process that cannot
  write, interpret.
- C4. Shapes are keyed by CRC-32 (`$ZCRC(shape,7)`). The lookup compares the full shape, but colliding shapes share
  the class name `IVGC.P<crc>`. Any caller who can choose labels or property names can forge a CRC-32 collision.

**Search**
- S1. The registry refuses a conflicting declared model, width or dtype on a route. An undeclared writer is checked
  on width only. Under 4.0.0, a `model_key` routes to its own table, with no fallback to a namespace-wide scan.
- S2. The quarantine is never searched. Placement refuses rather than creating a route. A query vector of the wrong
  width raises.
- S3. BM25 Insert and Delete run under the index lock in a transaction. Build and Drop take no lock. Upgrade
  re-checks nothing under the lock. Insert's Catch runs `If $TLevel > 0 TRollback`, which unwinds every level of a
  caller's transaction.
- S4. The common-term cutoff keeps the rarest term. Fusion swallows a failed leg (KNOWN_ISSUES).

**FHIR and algorithms**
- F1. FHIR compartment edges are owned by their source resource. A full sync equals the incremental syncs. An
  interrupted re-derive leaves the marker unset.
- G1. `route()` sends a call native only for an in-scope algorithm on the default graph, with a proof entry and a
  reader revision at or above it. The Owner is the fallback. The cache token is read before compute.

**Cross-domain erasure**
- X1. The Eraser covers rows, `^KG`, the temporal index, `^NKG`, `docs`, the embedding tables and routes,
  `AlgoCache`, and the ledger's `stmt` and `tuple`. It keeps `rec` and the quarantine.
- X2. No erase path touches `^BM25Idx`, `^IVF`, `^VecIdx` or `^PLAID`. `erase_all` is no exception, and it starts a
  replacing `restore_snapshot`. Restore imports index globals set-only (`snapshot.py:1654-1692`), so a replace overlays
  archived index nodes on live ones. CONTEXT ("every store that holds it") and ADR-0013 ("Together they cover
  everything IVG can reach") say erasure must reach them.

## Coverage findings

The uplift's coverage in this domain is broad. Stage-A notes, ontology pages, two Verus models with 43 controls and 17
probes cover most of my expectations, including I5, I7, A3, A4, C4, S1, S3 and X2. The gaps:

- **R1-6 (missing intent; suspected product defect).** Neither `install.snapshot` nor `search.erasure` says what a
  replacing restore does to the named search indexes. `erase_all` does not clear them (`Eraser.cls:709-830`), and
  `_import_global_from_ndjson` only sets nodes. After `restore_snapshot(path)`, three things go wrong:
  - a live index the archive lacks still answers for the pre-restore graph;
  - a same-named index mixes live and archived postings, df and token records, which breaks `search.bm25.counts`;
  - `install.snapshot.scope` ("it empties every graph and loads the archive") is not true of these stores.

  This is from code reading only; no probe covers it.
- **R1-11 (missing intent, partly).** The strict-mode bypass inventory is nearly complete, but three items are
  missing:
  - **`LedgerGuard._class_present`** (`guard.py:45-49`) is cached for the engine's lifetime. NOTES Part 2 calls it
    "not modelled", and no ontology statement mentions it.
  - **Migrations** (`upgrade_to_4_0_0`, the temporal backfill) rewrite tables and globals with no strict check, and no
    page says whether strict mode governs them.
  - **One open item can now be closed.** A Cypher write cannot reach the var-length route before `_ledger_check`
    (A5). Platform NOTES Part 2 should record that.
- **R1-3 (coverage part).** The adversarial collision case has no ontology statement and no probe. A caller with only
  Cypher read access, through a server whose IRIS login can write the database, can forge a colliding shape and
  poison another caller's compiled plan. This includes `IVG_READ_ONLY` servers on the default `_SYSTEM` login, since
  reads write compiled plans (`access.read_only.caches`). NOTES premise P-NO-COLLISION says collisions are easy to
  construct, but neither the ontology nor the register states the consequence (see Fidelity).
- **Unmodelled with no stated reason in `coverage.md`** (Low). FHIR (needs IRIS for Health), Arno routing (a pure
  function, unit-tested), fusion, quarantine placement (mocked tests only) and the access surfaces are not modelled.
  The NOTES justify some of this, but `coverage.md` has no row for any of them (see R1-1).

## Fidelity findings

- **R1-4 (incorrect intent).** `install.schema.concurrency` is a Q with a "provisional answer". The sources already
  decide the outcome:
  - FR-005: "the first `initialize_schema()` ... MUST record";
  - FR-006 and SC-006: refused before any write, 0 rows or globals changed;
  - ADR-0016: "instead of sharing globals silently".

  Concurrency changes how the rule is implemented, not which outcome is required. The platform model already takes
  L1 (a)-(c) from those sources and proves `record_stable` and `post_writes_ok` only under P-SERIAL, so the ontology
  and the model disagree on whether this is a requirement. Restate the block as I and link B1 as a suspected product
  defect. Production can reach it: two `initialize_schema()` calls with different prefixes whose 44-62 s windows
  overlap. That is the hipporag2 setup ADR-0016 names (RAG beside Graph_KG), or two deployers at once.

  My adversarial check (Adv-1) shows a compare-and-set record write alone is not a repair. Setup still releases its
  own engine (`_schema_check_passed`, 2159-2160), which then writes under the other schema's record. A repair needs
  the lock, or CAS plus a raise that does not release the engine.
- **R1-5 (incorrect intent / unresolved decision split wrongly).** `install.migration.schema` is one Q, but it covers
  two cases:
  - **Mismatch** (a record names another schema). FR-006 decides this with no exception. `platform_schema_waiver` now
    observes the release: with `Graph_KG` recorded, a migration on `IVGPROBE` is not refused, and the backfill reaches
    SQL on `IVGPROBE.RDF_EDGES`. The waiver's only justification, the code comment at `engine.py:1887-1890`, covers
    only "before any 4.6.0 setup recorded the schema". It is not an authorized exception for a mismatch. This case is
    an observed defect (B2) against an I.
  - **No record yet.** This case is genuinely open: FR-006a's letter against the 4.0.0 upgrade's documented order.

  F-S12 adds that the embeddings and `^KG` steps address the default schema and the real globals
  (`upgrade.py:145-152`). So on an FR-009 two-schema namespace, a default-schema migration can rebuild the shared
  `^KG` from the other schema's rows.
- **R1-7 (incorrect intent).** `search.erasure.indexes` is a Q whose provisional answer the governing texts already
  give:
  - CONTEXT "Erasure": every store that holds the content;
  - ADR-0004: "a write path that touches one store without the others is a bug";
  - ADR-0013: erasure and redaction together "cover everything IVG can reach".

  A BM25 token record is the node's text content, and an IVF, VecIndex or PLAID entry is a copy of its vector.
  `search_bm25_erase` observes the erased text still scoring the node, even after the node is re-created with other
  text. USER_GUIDE's "`bm25_insert`/`bm25_delete` keep an index current" governs ordinary node writes and deletes; the
  caller-upkeep D is right for those. It does not govern erasure, the privacy primitive. Split the block:
  - erasure: I, with F1 as an observed defect;
  - node deletes: keep the caller-upkeep D;
  - treating the indexes as rebuild-only derived stores: a proposal to change the decision, not an equal alternative.
- **R1-3 (incorrect intent; suspected product defect, practical estimate).** `query.compiled.integrity` (D) says "a
  shape's record may name only that shape's own class ... a user who can write the database therefore cannot make
  another user's read run code of their choosing". `query.compiled.never-stale` says "A compiled plan runs only for the
  shape it was written for".
  - **Both hold only under P-NO-COLLISION**, which nobody establishes. With colliding shapes a and b, W-O2b gives
    entry `(shape b, ok)` over a's compiled walk. Every later b run walks a's code until a deploy, a stamp change or
    a new run of a. I checked W-O2b against the code: `Gen.For` 80/81/89, then `Build` 170-207, which verifies only
    the lines' digest. It is a real interleaving; the job for b is refused when it runs second, so a job ordering in
    which a's job wins (about half) is enough.
  - **Accidental collisions** are negligible for typical workloads. By the birthday bound
    P ≈ 1 − exp(−S²/2³³) for S distinct shapes between deploys:

    | Distinct shapes S | P(any collision) |
    | ---: | ---: |
    | 10² | 1.2×10⁻⁶ |
    | 10³ | 1.2×10⁻⁴ |
    | 10⁴ | 1.2% |
    | 6.6×10⁴ | 39% |

    A harmful outcome additionally needs the two shapes' first runs, or a run and a recompile, to interleave within
    milliseconds. The likelier result is recompile thrash, a performance cost. Large S is plausible only for ad hoc
    or LLM-generated Cypher (MCP, GraphRAG).
  - **Adversarially it is practical.**
    - CRC-32 is affine. Four free bytes in a label or property name hit any target CRC.
    - The shape's `$ListBuild` text can be reproduced by running the open-source planner of the same version.
    - The attacker can run both a and b itself, repeating until the W-O2b ordering lands, then confirm by running b.
    - Choosing a's label so that it matches nothing makes the victim's shape silently answer no rows.

    This needs Cypher read access only, through any login that may write `^IVG.CypherCompiled`.

  Ontology: qualify both blocks with the premise and state the consequence. Register: P1, High, security/integrity,
  suspected. Proposed probe: a test hook that fixes `tH`, or a crafted collision.
- **R1-9 (incorrect provenance, Low).** The `search.embedding.other_model` metadata and search NOTES O3 say the
  glossary's "refused rather than mixed in" "predates routing". `git log -S` shows the phrase was added on 2026-11-04
  in commit `267aaff1` (R039, authored as Thomas Dyar). That is after the 4.0.0 routing release of 2026-09-22
  (`e0438914`). It is a later glossary restatement of ADR-0006 that was not reconciled with routing, not an older
  superseded text.

  On challenge 1, which source governs: the 4.0.0 decision (CHANGELOG, migration guide "Routed tables", USER_GUIDE §7
  "Several models") governs writes that name a `model_key`. Refusal still governs a declared different model on one
  table, which USER_GUIDE §7 re-affirms. The ontology's "never mixed" reading is right, but its stated reason is not.
  The correction also strengthens the "refuse" side of `search.embedding.undeclared_default`, because the newer text
  says refuse. Keep it Q; spec 226 FR-010 as quoted in code supports current behavior.
- **R1-8 (model error).** `witness_drop_inside_insert` (W-O1c, `search.rs:813`) is not a trace of `wstep`. It
  composes `remove_postings`, `absent_ix`, `remove_tail` and `add_doc` by hand. In the model's L2, Insert is one
  atomic step (P_lock) and Drop is unconstrained, so the transition system cannot represent a Drop inside an Insert.
  P_lock establishes atomicity only among locked writers, not against Build or Drop. Adv-3 confirms it: with Drop
  disabled entirely, the file still verifies 49/49.

  As a result, `theorem_locked_build_preserves`, described as "Build and Drop serialize with the writers", is silent
  on W-O1c. Its repaired Drop guard checks only a Build in flight. The source-level argument is plausible
  (`BM25Index.cls:416-491`); the problem is the claim that W-O1c is a "proved trace". Either model Insert at its
  `TStart`/`TCommit` boundaries with Drop and Build interleavings, or relabel W-O1c as inspection and narrow the
  repair claim.
- **R1-11 (classification).** `ledger.strict` metadata lists "embedding, vector-index and BM25 writes" among paths
  "observed and not guarded, whether by design or not". They are outside the ledger's scope by decision: ADR-0006
  ("Embedding writes sit entirely outside it") and spec 213 (strict mode governs structural writes). Meanwhile
  `access.ledger_strict.surfaces` lists the MCP SQL tool as open, though ADMIN_GUIDE §3 documents it as raw SQL by
  design, which falls under the contract's raw-SQL exemption. Give the owning block a per-path classification:
  - documented exemption;
  - outside ledger scope;
  - undocumented bypass that contradicts the 213 contract or USER_GUIDE "the other methods": `bulk_delete_adjacency`,
    the sample-API Cypher and GraphQL, the example mutations;
  - undecided: FHIR sync, MCP CypherQuery, `set_multigraph`, `Prop_Set`/`Txn_*`;
  - guard-mechanism gaps: the 5 s TTL, fail-open, `_class_present`.

  Adv-3b shows the model gives this classification no formal weight: reclassifying FHIR sync and MCP Cypher as exempt
  still verifies 35/35.
- **R1-2 (incorrect intent wording; observed product defect).** `search.bm25.write_lock` (D) says "a failed write
  leaves the index as it was". `search_bm25_caller_txn_rollback` observes much more:
  - a failed `bm25_insert` (`<SUBSCRIPT>` on a long document ID) inside the caller's transaction takes `$TLEVEL` from
    1 to 0;
  - the node the caller created earlier in that transaction is gone after the caller's "successful" commit
    (`commit_error: null`).

  This is silent loss of the caller's other writes, against the project rule that a failed IVG write takes back only
  its own changes (`query.writes.atomic`, Eraser's `TROLLBACK 1` loop). It appears only as metadata divergence (F3).
  It needs an owning statement and a High register entry. The same pattern sits in `Delete`'s Catch.
- **Checked and accepted (no finding).**
  - Platform Part 1 bindings: `_engine/schema.py:2222-2312`, `schema_name.py:194-198`, the swallowed deploy refusal
    at 2591-2594.
  - Part 2 guard semantics: `guard.py:38-59`; set_strict refreshes only the calling engine.
  - Part 3 transitions: `Gen.cls:61-222`.
  - Search O1 Build steps, the Upgrade boundaries and the identity 2×2 table (`embedding_identity.py:180-241`).
  - W-S1, W-S1b, W-S2, W-TTL, W-FAILOPEN, the bda bypass, W-O1a, W-O1b, W-O2a (Upgrade), W-O5 and P1's W-O2a/b are
    real product paths; native observations confirm most of them.

## Adversarial checks

Raw logs are under `$RUN_DIR/agents/R3-platform/adv/`. Each run used `$VERUS_BIN <file>.rs --crate-type=lib
--num-threads 4 --triggers-mode silent` (Verus 0.2026.10.04.426d8b0). None timed out or hit a resource limit.

| # | Kind | What I changed (scratch copy) | Verdict | Meaning | Log |
| --- | --- | --- | --- | --- | --- |
| Adv-1 | (b) faulty repair | `platform_cas.rs`: `SetupRecord` writes iff no record exists at write time (CAS, no lock). Added `witness_r3_cas_only_repair_still_admits_second_engine` | 33 verified, 3 errors | Correct detection. The three as-built overwrite witnesses fail at `record == Some(2)`, so the model sees the mutation. My witness verifies: under CAS the record stays Graph_KG, but setup 2 releases its engine, which writes, and `!post_writes_ok`. A CAS-only repair is insufficient. | `adv1_cas.log` |
| Adv-2a | (b) partial repair | `platform_pshape.rs`: `build` also requires the entry's shape and stamp to equal the job's (the uplift's P1 proposal 2) | 34 verified, 1 error | Only `witness_collision_leaves_another_shapes_code_under_an_ok_entry` (W-O2b) fails, so this repair closes the persistent poisoning. `witness_collision_swaps_the_class_mid_run` (W-O2a) still verifies: the shared class name still lets a mid-run swap through. | `adv2_platform_pshape.log` |
| Adv-2b | (b) detection of the residual | Adv-2a plus the P-NO-COLLISION premise dropped | 33 verified, 2 errors (`lemma_p_step_preserves_inv`, W-O2b) | Without the premise, the step lemma fails even with the shape check. Only unique class names (S2, SHA-256) remove the dependency. | `adv2_platform_pshape_nocoll.log` |
| Adv-3a | (a) false premise | `search_nodrop.rs`: `WAct::Drop => None` (Drop never runs) | 49 verified, 0 errors | The model failed to detect this. W-O1c still "verifies" with Drop impossible, so it is not a trace of the model (R1-8). | `adv3_search_nodrop.log` |
| Adv-3b | (a) false classification | `platform_fhirexempt.rs`: FhirSync and McpCypher marked documented-exempt | 35 verified, 0 errors | Nothing catches it, so the bypass classification rests on prose (R1-11). This run also reproduces the receipt's 35/35. | `adv3_platform_fhirexempt.log` |
| Adv-4 | (c) valid outcome | `platform_resume.rs`: `witness_r3_resume_after_interrupt_survives_the_repairs` under `s_proved()` (lock plus refuse-explicit-over-marker). Setup Graph_KG stops after DDL, an explicit IVGALT setup is refused at its read, then Graph_KG's setup resumes, records, and its engine writes with `post_writes_ok` | 36 verified, 0 errors | The proposed repairs keep spec 262's "interrupted upgrade resumes" path. | `adv4_platform_resume.log` |
| Adv-4c | control for Adv-4 | the same with `refuse_explicit_over_marker: false` | 33 verified, 3 errors (my witness's refusal assertion, the step lemma, W-S3's refusal) | The valid-outcome witness is not vacuous: its refusal step depends on the proposed repair. | `adv4_platform_resume_ctl.log` |

## Evidence findings

- **Receipts are fresh.** The platform receipts (prove 35/35 and 21/21 controls EXPECTED_FAIL, each failing in its
  named functions) carry the current `platform.rs` (d7bcef30) and `model.json` (06b6e8ef) hashes. The search receipts
  of 23:30-23:38 (prove 49/49 and 22/22 controls) carry the current `search.rs` (9719f3a2) and `model.json`
  (5425eb23). The 23:21-23:28 search receipts use an older `model.json` and are superseded, not stale citations. No
  timeout, resource limit or zero-test result was found.
- **R1-10 (stale or misread evidence).**
  - **Stale probe revision.** `cypher_subquery_write-20261113T234233Z.json`, copied to
    `receipts/native/cypher_subquery_write.json`, came from an earlier revision of the probe. The probe file changed
    at 23:42:40, the run ended at 23:42:33, and the current revision writes `result_type`, which the observation
    lacks.
  - **Misread verdict.** The observation's verdict reason says the query "returned", yet the recorded result shows
    `error='<SQL ERROR> ... SQLCODE -12'` while `error_in_result` is null. By the probe's own rule ("refused" if an
    error is in the result), this is not the defect its verdict claims.
  - **What the raw output does show.** `CALL { CREATE … }` is not classified as a write, so it fails with a SQL error
    in `result.error`: no raise, no write, no `GraphWriteError` (`query.writes.atomic`), and no strict refusal. The
    suspected "silent drop when RETURN reads only matched variables" remains unobserved.
  - **Stale metadata.** `query.writes.subquery` still says "source reading; not run".
  - **No fingerprint.** Native receipts carry no probe-source hash or product baseline, so the runner cannot detect
    this kind of staleness. Re-run the current probe and add input fingerprints to native receipts.
- **NOTES are stale.** Platform NOTES ("Probes (written, not run)") and search NOTES ("Native probes (not run)") still
  classify B2, W1, W2, W-TTL, F1, F2, F3 and F4 as "SUSPECTED until the probe runs". The probes have run:
  - observed defects: `platform_schema_waiver`, `platform_strict_bulk_delete_adjacency`,
    `platform_strict_api_sample`, `platform_strict_ttl`, `search_bm25_erase`, `search_bm25_build_insert_race` (99
    violations with no Build in flight), `search_bm25_caller_txn_rollback`, `search_bm25_upgrade_concurrent` (18 of 22
    searches empty during the second pass, consistent afterwards);
  - observed as expected: `platform_schema_refusal`, `platform_strict_paths`, `platform_strict_redaction`,
    `search_bm25_cutoff`, `search_bm25_caller_txn_lock`.
- **R1-12 (missing evidence, Low).**
  - `search_route_split` is INCONCLUSIVE for a probe-design reason: it claims a width-4 identity on the 768-wide
    `kg_NodeEmbeddings`.
  - `search_queue_default_graph` is INCONCLUSIVE: no `%Embedding.Config`.
  - F9 and F8 therefore stay unobserved. Use a fresh named graph, or a matching width.
  - The final batch log shows repeated "Unable to allocate a license" warnings from the conftest hostname read. They
    did not decide any verdict above, but the Community connection limit should be named as a premise of the probe
    runs.
- **`coverage.md` covers only the ledger, erasure and redaction** (last modified 22:58). It has no row for O-SCHEMA,
  O-WRITE-SURFACE, compiled plans, BM25, embedding identity, fusion, FHIR, algorithms or access, so none of the
  Proved, Observed or Violated statuses above are recorded against a clause (R1-1).

## Findings-register check

- **The register files** (`bugs_issues.md`, `open_questions.md`, `design_simplification.md`) hold only redaction and
  ledger items. `bugs_issues.md` links `findings.md`, which does not exist. No finding from this scope is registered.
- **Missing bugs**, with the severity I would give:
  - **High:** F3 caller-transaction rollback (observed); F1 BM25/IVF/PLAID/VecIdx content surviving erase (observed);
    P1 CRC-32 compiled-plan poisoning (suspected; adversarially practical).
  - **Medium:** B1 concurrent first setups (proved trace, not probed); B2 waiver releasing a mismatch (observed); W1
    `bulk_delete_adjacency` strict bypass (observed); W2 sample-API strict bypass (observed); F2 Build/Insert race
    (observed); the replacing-restore index overlay (R1-6, suspected).
  - **Low:** F4 concurrent Upgrade (observed, transient); P2, P3; F11; F-S4 (`remove_legacy_objects` misreport);
    F-B1 to F-B6.
- **Missing open questions:** TTL window (Q2); fail-open (Q3); strict versus erase-then-redact, which overlaps the
  existing ledger Q "How should strict mode and the erase-then-redact path fit together?"; FHIR sync and MCP under
  strict (Q5); the undeclared default-graph writer (Q1); the glossary update (Q2); BM25 read isolation; the no-record
  part of the migration waiver.
- **Misclassified:** `install.schema.concurrency` and the mismatch half of `install.migration.schema` are decided by
  sources (R1-4, R1-5). `search.erasure.indexes` is decided for erasure (R1-7).
- **Missing simplifications:** S1 (one server-side strict gate), S2 (SHA-256 class names), S-a to S-f (search) are in
  NOTES only.
- **Unsupported claims:**
  - W-O1c is labelled a "proved trace" (R1-8).
  - "predates routing" (R1-9).
  - The subquery probe's verdict reason (R1-10).

## Answers to the specific challenges

1. **Routing versus "refused rather than mixed in".**
   - The 4.0.0 routing decision governs writes that name a `model_key`.
   - Refusal governs width, dtype and mechanism, and a declared different model on the same route; USER_GUIDE §7
     re-affirms this.
   - The ontology's operative reading ("never mixed") is right, but its provenance claim ("predates routing") is
     false (R1-9).
   - The undeclared-writer case is honestly left open as a Q.
2. **BM25 races: reachable from public entry points? Yes.**
   - `bm25_build`, `bm25_drop`, `bm25_upgrade`, `bm25_insert` and `bm25_delete` are public engine methods
     (`_engine/vector.py:1749-1870`), and `index_protocol` drops too. There is no HTTP route.
   - Build with concurrent Inserts (a rebuild while an application inserts) is realistic, and natively observed with
     persistent corruption.
   - Concurrent Upgrades are observed, with transient empty searches.
   - Drop inside an Insert (W-O1c) is plausible from source but neither probed nor a model trace (R1-8).
   - Crash after the flip (Upgrade W-O2b) is not probed.
3. **The schema-record race and the migration waiver.**
   - The race is reachable whenever two setups with different prefixes overlap their 44-62 s windows. It needs an
     operator or deployment race and has not been reproduced natively. The model's lock repair is right, and a
     CAS-only repair is insufficient (Adv-1).
   - Production reaches the waiver through `upgrade_to_4_0_0(conn)` or `migrate_to_graph_scoped_embeddings(conn)`
     whenever the environment or default schema differs from the record. This is observed.
   - The waiver is not an authorized exception for the mismatch case. FR-006 has no exception, and the code comment
     justifies only the no-record case (R1-5).
4. **Is the strict-mode bypass list complete and correctly classified?** It is nearly complete; `_class_present`
   and the migrations are missing, and the var-length route can be closed as not reachable. It is not correctly
   classified:
   - out-of-scope embedding and index writes are mixed in with bypasses;
   - MCP `RunSQL` is a documented raw-SQL exemption;
   - `bulk_delete_adjacency` and the sample API's paths are undocumented and contradict the contract.

   The model cannot check classification (Adv-3b) (R1-11).
5. **The compiled-plan checksum collision.** Accidental harm is theoretical for typical workloads (≤10⁻⁴ for 10³
   shapes) and becomes about 1% at 10⁴ shapes, mainly as thrash. Adversarially it is practical: a caller with Cypher
   read access can poison another shape persistently through W-O2b (R1-3).
6. **Behavior with neither an ontology block nor a model or probe:**
   - the search-index overlay or survival through a replacing restore (R1-6);
   - adversarial compiled-plan poisoning by readers (R1-3);
   - `_class_present` cached for an engine's lifetime;
   - migrations under strict mode;
   - Search during Build answering `[]`, which is noted in search NOTES but has no ontology statement;
   - two concurrent `bm25_build`s, which the search model excludes as a bound.

## Summary table of material findings

| ID | Severity | Category | Owning artifact | Proposed correction |
| --- | --- | --- | --- | --- |
| R1-1 | High | missing or stale evidence | `.g5/Verus_verification/{bugs_issues,open_questions,design_simplification,coverage}.md`; platform and search `NOTES.md` | Register every platform, search and Cypher finding with severity and native status. Add coverage rows for O-SCHEMA, O-WRITE-SURFACE, compiled plans, BM25, identity, erasure-over-search, and the unmodelled FHIR, algorithms, fusion and access with reasons. Fix the dangling `findings.md` link. Update NOTES with the probe results. |
| R1-2 | High | product defect (observed) and incorrect intent wording | `search.bm25.write_lock`; register | State that a failed index write takes back only its own changes. Register F3 as High: a failed `bm25_insert`/`bm25_delete` silently aborts the caller's transaction. Proposal S-c (`TROLLBACK 1` to entry level). |
| R1-3 | High | incorrect intent and suspected product defect | `query.compiled.integrity`, `query.compiled.never-stale`; P1 in the register | Qualify both blocks with P-NO-COLLISION. State that a read-capable caller can forge a CRC-32 collision and poison another shape (W-O2b) persistently. Register P1 as High, security. Proposals: SHA-256 or sequence class names; the Build shape check alone is insufficient (Adv-2). Add a probe through a hash test hook. |
| R1-4 | Medium | incorrect intent | `install.schema.concurrency`; register | Restate as I from FR-005, FR-006, SC-006 and ADR-0016. Register B1 (suspected). Repair: lock, or CAS plus a raise without release (Adv-1). |
| R1-5 | Medium | incorrect intent / unresolved decision | `install.migration.schema`, `install.schema.refusal` | Split it: mismatch is an I under FR-006 with B2 observed; only the no-record case stays Q. Link F-S12 (`^KG` and embeddings steps on the default schema). |
| R1-6 | Medium | missing intent; suspected product defect | `install.snapshot.scope`, `search.erasure` | State what a replacing restore does to `^BM25Idx`, `^IVF`, `^PLAID` and `^VecIdx` (today: survive and overlay). Add a probe; register the suspected defect. |
| R1-7 | Medium | incorrect intent | `search.erasure.indexes` | Erasure: I (CONTEXT, ADR-0004, ADR-0013) with F1 observed. Node-delete upkeep stays D. The derived-store option is a proposed decision change. |
| R1-8 | Medium | model error | `models/search/search.rs` (W-O1c, `theorem_locked_build_preserves`), search NOTES | Model Insert at its TStart/TCommit boundaries with Drop and Build interleavings, or relabel W-O1c as inspection and narrow the repair theorem's claim; it does not cover Drop inside an Insert (Adv-3a). |
| R1-10 | Medium | missing or stale evidence | `receipts/native/cypher_subquery_write.json`, `query.writes.subquery`, `native/run_probes` | Re-run the current probe. Record the observed outcome (SQL error in result, not raised, not a write, no strict refusal). Add probe-source and baseline hashes to native receipts. |
| R1-11 | Medium | incorrect classification / missing intent | `ledger.strict`, `access.ledger_strict.surfaces`, platform NOTES Part 2 | Per-path classification table. Move embedding and index writes to "outside ledger scope" and MCP `RunSQL` to "documented raw SQL". Add `_class_present` caching and migrations. Close the var-length item (transactional `SQLQuery` has no `var_length_paths`). |
| R1-9 | Low | incorrect provenance | `search.embedding.other_model` metadata, search NOTES O3 | Replace "predates routing" with "added 2026-11-04 (R039) restating ADR-0006, not reconciled with 4.0.0 routing". Keep the routing reading. Note that the newer text favours "refuse" in `search.embedding.undeclared_default`. |
| R1-12 | Low | missing evidence | `search_route_split.py`, `search_queue_default_graph.py` | Fix the probe setup (fresh named graph or matching width, or an embedding config) and re-run. Name the Community license and connection limit as a probe-run premise. |
