# Independent review of the IVG completion audit (playbook §3.8, §5c)

Reviewer: independent reviewer lane (read-only). Product pin `3eaa79cf` (tree `b098a6f4`; `git diff 3eaa79cf HEAD`
outside `experiment/` is empty). Audit head reviewed: `44636dd1` plus the untracked registry entries present on
2026-11-14. No IRIS connection, no live run, no commit; every statement below comes from source, artifacts and logs
under `$RUN_DIR` (`~/runs/iris-vector-graph-playbook-uplift-20261113/completion-audit`). Where I relied on a helper's
sweep, I re-checked the decisive items myself (marked "re-checked").

Paths are relative to the worktree unless they start with `$RUN_DIR`. `PC/` = `experiment/playbook-completion/`.

Scope note: other lanes kept working during this review. `PC/TRUST.md` (00:54 UTC), `PC/correspondence/` (from
00:37) and uncommitted edits to `PC/iris-contract/` (to 00:57) appeared after I read those areas; they are **not**
reviewed here, and nothing below depends on them. I changed nothing outside `PC/review/`.

## Decision: **no sign-off**

The audit is careful, mostly honest about model-versus-product, and its central product findings (F-1201, F-1302 to
F-1306, F-C1201, F-C1303, F-1401/1402, F-1801) are well evidenced. I cannot sign off on spec against intent (§3.8 gate)
because:

1. A redacted tenant's data stays in IVG-held copies that neither the redaction receipt nor any finding names
   (R-01), and the writer census that backs the §3.3a write-set obligations misses whole classes of writers,
   including one that writes the ledger itself (R-02).
2. Model-level results are shown as closed gates next to product gates with no level marker, and in places stated as
   product properties (R-05); a closed-cell guard that the queue says exists does not exist for most cells (R-07).
3. The proofs' safety rests on three premises that the audit's own evidence shows false at the pin, and the progress
   result rests on a fairness premise that is neither derived nor tested (R-06).

Conditions that would change the decision are listed at the end.

## Findings, ranked by consequence

Severity uses the audit's scale (S1 data loss/isolation, S2 integrity/false result, S3 docs/conflict, S4 minor).
Machine-readable copy: `review/review.json`.

### R-01 (S1, angles 6 and 1) — Copies of a redacted tenant inside IVG's reach that no receipt or finding names

Spec 256 US1: "no record, revision field or index reachable through IVG holds the tenant's entity ids, attribute values
or messages"; SC-001: "every `Graph_KG.ledger_*` row finds none"; FR-008: the receipt states "what stays out of reach".
The receipt names exactly three things (`iris_src/src/Graph/KG/LedgerRedact.cls:506-508`): export_reconstruction files,
IRIS journals, backups. Not named, and not recorded as findings:

- **Legacy revision rows after an upgrade (re-checked, inspected).** `copy_ledger_history`
  (`iris_vector_graph/_engine/legacy.py:606-646`) copies 4.5.x `Graph_KG.ledger_revisions` rows into a non-default IVG
  Schema and states "The `Graph_KG` rows stay where they are". The deploy rewrites every `Graph_KG` token in class
  sources to the IVG Schema (`iris_vector_graph/_engine/class_deploy.py:109-119`), so `ClearRevision`'s
  `UPDATE Graph_KG.ledger_revisions ...` (`LedgerRedact.cls:355,369`) clears only the schema's copy. The tenant's
  `message`, `source`, `correlation_id` and `idempotency_key` survive in `Graph_KG.ledger_revisions` - the literal
  table SC-001 scans. The ontology knows the rows stay (`PC/ontology/01-install-schema.md` INS-B6.12) but nothing
  connects it to redaction. Confidence medium: needs one live probe (upgrade path, non-default schema).
- **IVG's own snapshot archives (re-checked, inspected + existing live evidence).** `save_snapshot` archives
  `^IVG.Ledger` and the LedgerRevision storage globals (`iris_vector_graph/_engine/snapshot.py:399-404`).
  `POST /admin/snapshot` lets any API-key holder write one on demand to `IVG_SNAPSHOT_DIR` or the system temp
  directory (`iris_vector_graph/cypher_api.py:668-678`; ZIP written with the process umask, `snapshot.py:1035`).
  A restore writes those globals node by node (`snapshot.py:1679`) and brings redacted content back (F-1801;
  `c18-live-ledger-overlay`: "restore of the pre-redaction archive put back ... secret='c18-sensitive' ... while
  redactedRev(2) remains"). F-1801 records the restore effect; the receipt's reach statement and the
  pre-redaction archives themselves are not recorded.
- **`Graph_KG.embedding_quarantine`** keeps node ids and vectors no erase can attribute, by design
  (`Eraser.cls:300-302`, `756-758`, FR-039/040). That is defensible, but the tenant erasure receipt (opsreview's use
  case) does not say so.

Recommendation: record as a finding against FR-008/SC-001 (S1 for the legacy rows if confirmed live, S2/S3 for the
receipt text); add the three items to the obligation matrix as reach obligations.

### R-02 (S1, angle 2) — The writer census and the "bypass writer" grouping miss writers, including a ledger writer

`$RUN_DIR/checks/writer-census.json` (104 sites, 25 uncovered writer methods, 100 new obligations) backs the failed
3.3a-writesets cells and the claim that M2's writer W "stands for all of them" because "the census writers write
content tables only" (`PC/models/core/MODELS.md:282-297`). The census is lexical (`PC/tools/writer_census.py:28-31`):
`SQLW` needs a literal table name after `INSERT INTO`/`UPDATE`/`DELETE FROM`, and Native-API writes are matched only
with a literal `^IVG.Ledger`. What it cannot see (re-checked by grep unless marked):
- **Formatted table names in Python.** 115 content-table write sites of the form `f"INSERT INTO {self._t('nodes')}"`
  or `{_table('rdf_edges')}` are absent from `detail`: `cypher/translator.py` (78 sites: every Cypher updating
  clause, reached from HTTP, Bolt and MCP), `_engine/nodes_edges.py` (23), `_engine/snapshot.py` (5 plus
  `{table}`-formatted restore inserts at 1163-1295), `_engine/schema.py` (5, reification delete), `_engine/temporal.py`
  (3, the structural mirror), `bulk_loader.py:225` (BulkLoader, unguarded even in strict mode per
  `specs/213-graph-revision-ledger/contracts/ledger-api.md`).
- **Concatenated table names in ObjectScript.** `"INSERT INTO " _ pSchema _ ".nodes"` style: 19 sites in
  `LedgerApply.cls` (the commit's own content writes), 3 in `Eraser.cls`, 1 in `EmbedQueue.cls`.
- **Writers of the ledger itself, outside the ledger classes** (these break the "content only" premise):
  - `restore_snapshot` writes every archived global node by node, including all of `^IVG.Ledger` (rec, idem,
    idemRedacted, redactedRev, redacting, stmt, tuple, head, meta) and the LedgerRevision/LedgerStats storage
    globals, with a variable global name (`_engine/snapshot.py:399-404`, `1654-1692`, `iris_obj.set(entry["v"],
    global_name, *subs)` at 1679). Raw global sets bypass `RejectUpdate` and `%OnBeforeSave`. Observed live:
    `ib-HD1801-merge-restore` log line 24 `restored_globals: ['NKG', 'IVG.Ledger', 'Graph.KG.LedgerRevisionD', ...]`.
    It also restores the redaction marker of an archive taken mid-run (save takes no lock and reads no marker,
    `snapshot.py:1010-1035`). The core models note "restores during a run are not modelled" (`MODELS.md:343-344`).
  - `Graph.KG.Snapshot.ImportGlobals` (`Snapshot.cls:24-35`, `$System.OBJ.Load` of any `*.gof`; F-1806 records the
    allow-list gap, not its role as a ledger writer).
  - `Ledger.Disable` / `SetStrict` write `^IVG.Ledger("meta", ...)` without the head lock (`Ledger.cls:331-385`); a
    disable mid-run stops every batch (`LedgerRedact.cls:304-305`). `"meta"` is not in the census's `LEDGER_SUBS`.
  - A plain SQL `INSERT` into `ledger_revisions` is not refused: the triggers are `Event = UPDATE` and
    `Event = DELETE` only (`LedgerRevision.cls:87`, `104`). Inferred consequence: a row at `head+1` wedges the next
    commit exactly as F-1801's overlay does ("ID key not unique"). Needs a probe.
- **Direct storage-global content writes.** `Graph.KG.PropWrite` sets the `rdf_props` data global directly
  (`PropWrite.cls:55`, `Set @tRef = tRow`), exposed as SQL procedure `Prop_Set` (`SqlProcs.cls:187-190`) and used by
  Cypher `SET`.
- **Migrations during setup** that delete or rewrite content rows (`schema.py:1465-1492`, `1290`, `2991-3009`,
  `migrations/graph_scoped_embeddings.py:679,749,808`).

None of these reads the marker or takes the head lock (only `Ledger.cls`, `LedgerRedact.cls`, `ledger/client.py` and
`ledger/replay.py` mention `redacting`). The grouping argument holds for content-only writers, but the ledger
writers above need their own (invariant, writer) obligations: INV-marker, INV-text, INV-retry and
INV-no-live-tombstone are all writable by `restore_snapshot` during a run.

**Readers** (FR-003 and ADR-0013 "Batches"): the SQL table function `ledger_records` (`SqlProcs.cls:206-224` ->
`Ledger.RecordsExecute/Fetch`, `Ledger.cls:613-646`) never checks the marker; only the Python wrapper does, in a
separate call before paging (`client.py:687-739`, pages are separate statements, `replay.py:252-279`). `history()`
returns `RevisionInfo` with no redacted flag (`client.py:40-70`), although FR-003 names `history` among readers that
"MUST mark it as redacted". `verify(adopt=True)` checks the marker once (`replay.py:811-812`) and commits the adoption
later (`:857`). Inferred: a redaction that completes in between lets an adoption revision write the erased tenant's
values as priors after a "complete" receipt (a variant of F-1103 / F-C1302). `save_snapshot` reads the whole ledger
with no marker check.

Recommendation: make the census see formatted and concatenated SQL and variable-name global writes (or derive
writers from the journal oracle's footprints of every public entry point), add the ledger writers above as writers
with obligations, and add restore-during-a-run to M3 or record it as an open obligation.

### R-03 (S2, angles 6 and 3) — Any writer can hold a redaction open indefinitely, and the open marker blocks everyone

Not recorded as a finding. At the pin and in the reviewed design:
- Non-ledger writers never read the marker: only `Ledger.cls`, `LedgerRedact.cls`, `ledger/client.py`,
  `ledger/replay.py` reference it (grep for `redacting|RedactionInProgress`). Strict mode is client-side
  (HD-1103) and refuses only named Python methods; `POST /admin/load` (`cypher_api.py:628-643`, calls
  `import_graph_ndjson`) and Cypher updating clauses write content into any graph.
- Authentication is one shared key (`iris_vector_graph/_api_key.py`, `api_auth.py`); there is no graph-scoped
  credential, so "a graph-scoped API key" is not a boundary the product offers: the key reaches every tenant.
- A write that makes the marked target live makes `FinalInLock` refuse `target_live` and keep the marker
  (`PC/ontology/13-redaction.md` RED-B8.2; original live `native-commit_in_unmarked_window`). While the marker
  exists every record reader refuses and `verify()` reports `redaction_in_progress` for **all** tenants (ADR-0013
  "Batches"), and a redaction of any other target is refused (`LedgerRedact.cls:202-205`). There is no abandon call
  (HD-1303).
- So one writer (careless or hostile) that keeps re-creating a row in the target keeps every tenant's redaction
  and every ledger reader blocked. The core models record this only as "W does write content into a marked target
  unrefused ... (AG EF still holds: erase again)" (`PC/models/core/MODELS.md:302`), and the AG EF premise "writers
  become quiet" (`MODELS.md:310`) assumes it away.

Recommendation: record as a finding (availability of the erasure obligation); add "no writer makes a marked target
live" as an explicit progress premise (it is P-C02, see R-06) and a maintainer question on abandonment.

### R-04 (S2, angles 1 and 6) — Temporal-only edges escape the liveness refusal (FR-005); left open and never probed

`Matches` treats `create_temporal_edge` records as target records (`LedgerRedact.cls:97-98`); `LiveRows` counts only
`nodes`, `rdf_labels`, `rdf_props`, `rdf_edges` (`LedgerRedact.cls:149-178`); a temporal-only predicate writes no
structural row (ADR-0015 Decision; `LedgerApply.cls:617-639` records the edge after `TemporalIndex.InsertEdge`); and
`verify()` drops temporal statements (`iris_vector_graph/ledger/replay.py:617-619`, `792-800`). Inference: a graph
target whose only live content is temporal-only edges passes the liveness check, its live edges' history is
tombstoned, and `verify()` cannot notice. The core lane lists this as "open, inspected only, no claim"
(`MODELS.md:328-331`). One live probe would settle a potential S1 (FR-005 / RED-X2) cheaply.

### R-05 (S2, angle 4) — Model results presented as product status

- `PC/matrix/MATRIX.md` (the human summary) has no level column: the 12 cells marked `level: "reviewed model"` in
  `obligations.json` (3.3-L1/L2/refinement for 12-14, 3.3-protocol, 3.3-progress-controls, 3.3a-domain-contract) are
  counted in "closed" beside product gates. Other model-only closures carry no level at all: 3.3-controls (12-14),
  3.7-explorers, 3.3-cost, 5-mutants-located.
- **3.3-model-check means different things per lane.** For 12-14 it is `failed` ("as-built violates; reviewed model
  passes"); for 01-05, 09-11 and 15-18 it is `closed` under the same pattern (e.g. 03 and 05 closed while F-0304 and
  F-0505 are S1 as-built violations; 18 closed while F-1801 is S1). 12 closed 3.3-model-check cells are of this kind.
- **3.8-findings-disposed is `closed` for 16 modules** with the reason "every finding recorded with evidence;
  product obligations stay failed" (`orchestrator_status.json`). The playbook gate is "every finding becomes a fix or
  a recorded decision" (§3.8). No finding is fixed and none has a maintainer decision; the gate is open.
- `PC/proofs/PROOFS.md:152`: "So the pin's rescanning resume is safe". The control keeps every other reviewed-design
  guard (locked start, own marker, eraser lock); the pin has none of them (D-3 to D-6, `PROOFS.md` §7) and is unsafe
  (F-1302, F-1303). Correct reading: "within the reviewed design, a rescanning resume does not break safety".
- The completion ontology (the account's requirement list) still carries the original submission's `proved:` tags
  on product statements that the audit's own findings contradict, without citing them, against `ontology/INDEX.md`'s
  own rule ("where the code at the pin differs ... the statement also cites a finding"):
  RED-B8 "Calling the same redaction again finishes a stopped or paused run" (`13-redaction.md:108`, tags
  `proved:theorem_run_can_step`, live passes; F-C1303 shows the opposite and cites RED-B8 as its intent);
  RED-B8.1 "Without new commits, a redaction run takes a bounded number of steps" (`:112`, `proved:theorem_run_bounded`
  only; F-C1303's 60 calls added no commit); RED-B4 "A retry key of a redacted revision can never be used again"
  (F-1801; `core-m3-as-built-F1801-keys`: after a restore the redacted revision's key is bound again); RPL-B1.1 "replay gives what it gave before, less the
  tenant" (F-1304 tombstones another tenant's node records). These `proved:` names resolve to
  `experiment/playbook-uplift/proofs/src/{l1,l2,progress}.rs`, whose premise P-1311 F-C1201 refutes. Q8b
  (re-tagging) is `todo`, so the ontology today reads as a product guarantee.

### R-06 (S2, angles 3 and 1) — Proof premises that are false at the pin; progress premise neither derived nor tested

`PROOFS.md` §8 names its premises honestly; the consequence is not carried into the gate statuses.
- Safety (`theorem_implementations_safe`, `theorem_replay_settled`) assumes **P-C02** (no ledger-bypassing writes),
  **P-C03** (one target predicate) and **P-C04** (no erasure abort). The audit's own evidence refutes all three at the
  pin: the writer census (25 uncovered writer methods; more in R-02), F-1304/F-1305 (three predicates differ), F-C1201
  (an erasure rolled back after the redaction read it). The failure modes these premises remove (F-C1301,
  F-1304/F-1305, F-C1201) are exactly the S1 findings, so the proof cannot be read as covering them even for the
  reviewed design; only M1/M2 (bounded, graph-only targets under concurrency) touch them.
- Progress (`theorem_redaction_completes`) assumes `productive_fairness` (`actors/src/fairness.rs:22-24`: whenever
  rank > 0, a work step eventually occurs). That is close to the conclusion; the substance is `nonincreasing`.
  `theorem_work_available` shows enabledness only when `enabled && !locked`; nothing derives productive fairness from
  PF-1..PF-4. Status of each premise: PF-1 operator re-runs (assumed; F-C1303 shows re-running is not enough at the
  pin); PF-2 ledger stays enabled (assumed); PF-3 erasures end (Process stop / Lock wait clauses tested in
  `env-contract-r2`; an erasure inside a long caller transaction is not, and under *Locks: deferral* the reviewed
  eraser would then hold the head lock until the caller commits); PF-4 scheduling and commit (assumed; lock timeouts
  and waiter fairness are outside the contract subset, `iris-contract/CONTRACT.md` "Outside the semantic subset").
- **Missing progress premise.** `theorem_work_available` says Final is "never refused: nothing of t is live while t is
  marked" - true only under P-C02. PF-1..PF-4 omit it, and R-03 shows it is violated by an ordinary writer.
- **Progress-only control.** `control_progress_rewind` isolates progress well (one error at `progress.rs:165`, every
  other function verifies; re-checked in `$RUN_DIR/core-proofs-recheck/control_progress_rewind.log:73`). It
  demonstrates D-1 only. D-2 (fixed scan bound), which carries the claim "commits by other tenants cannot prolong a
  run", has no control. D-1 and D-2 are this lane's design choices (`PROOFS.md` §7), not intent.
- The model AG EF results encode premises as path choices (writers quiet, operator resumes, no permanent stop,
  re-erase; `MODELS.md:308-313`). They are stated, not tested.

### R-07 (S2, angle 5) — The closed-cell guard is mostly absent; closed cells rest on unregistered or non-passing runs

`PC/QUEUE.md` header: "every `closed` cell cites registered passing runs". Mechanically (script over
`matrix/obligations.json` and `evidence/runs/`):
- 68 of 109 closed cells cite no `run:` evidence; 10 cite nothing at all (12/13/14 3.1-cells, 3.1-intent,
  3.8-findings-disposed; product 5-hygiene, which also has a recorded lapse).
- `build_matrix.py:125-133` checks only `run:`-prefixed strings, so any other ref passes unchecked.
- Closed 3.3-model-check (09, 10, 11) and 3.3-L1 (10, 11) rest on 90 distinct breadth-B model results (129 citations) that are not in
  the registry: `PC/models/breadth-b/results/*.json`, with only `$RUN_DIR/breadth-b/mc/0[7-9]-dev.log`, `10-dev.log`,
  `11-dev.log` behind them (no hash, "dev" runs). Against §5c landing rules ("crate results carry only from
  script-collected full runs with control records").
- 11 / 3.4-storage-order is closed citing `storage-order-scan` (result `incomplete`); 11 / 3.1-intent cites
  `ib-HD1101-namedonly` and `ib-HD1105-replay-reapplies` (result `fail`). The builder would have reopened both had
  they been prefixed `run:`.

### R-08 (S3, angle 5) — Evidence records: 2 mismatches, 6 overwritten decisive logs, inconsistent `result`

See the evidence-audit table. Summary: 377 registered runs, 371 SHA-256 ok, 6 mismatched (all `core-proofs-*`,
disclosed in `incidents/superseded-logs.json`); of 38 runs read against their `observes`, 2 are contradicted by their
logs and 16 are only partly supported by the registered log. Additional defects:
- The six original core-proof logs were overwritten (against CONVENTIONS "the original record and log stay"); the
  superseding record says "~00:40 UTC" but the files' mtimes are 00:31:29-00:31:44 and the recheck copies 00:32:20.
  The recheck logs that close 3.3-protocol etc. contain no verification count; "88 verified, 0 errors" is only in
  the unhashed `baseline.json`.
- `result` means different things: `live-native-rerun-1314` (reproduces F-1303..F-1306, F-1401, F-1402) and
  `live-erase-vs-commit-fk` (erase fails 8/8) are `pass`; `live-f1201-reproduced` and `live-fc1303-bounded-resume`
  are `fail`. The matrix guard keys on `result`.
- No registered log records the pin; pin attribution is registry metadata only. Claimed namespaces (AUDITCORE,
  AUDITENV, AUDITIB) do not appear in their logs.

### R-09 (S3, angle 4) — Trace conformance and the journal oracle cannot see the defects that matter

`trace-conformance-ledger` (closes 3.7-trace-replay for 12-14) is one sequential scenario with one target shape
(`EraseNodes("", "acme|")`, prefix default-graph target; `PC/traces/conformance.py:327-343`). The redaction step rule
(`conformance.py:240-262`) checks soundness only: no tombstone outside the target, op/kind kept, marker ownership. It
does not check completeness (F-1305, F-C1302), liveness at tombstone time (F-1302, F-1304, F-C1201), Decision 2
metadata clearing, `idemRedacted`, or SC-001. The journal records no reads, no locks, no process-private globals
(`^||IVG.RedactStmt`, the PrePass map read outside the lock) and no `^IRIS.Temp`; writes from background jobs carry
another pid than the operation. So the pass shows the happy path conforms; it cannot distinguish the pin from the
reviewed design on any recorded concurrency defect. The cell's "remaining: one two-tenant scenario" understates this.

### R-10 (S3, angle 1) — Target digest and record digest identify the tenant; spec and ADR conflict, unrecorded

The redaction revision and the marker hold `sha256(graph NUL match)` (`LedgerRedact.cls:56-59`, `:420-441`): an
unsalted hash of the tenant's name and prefix. Anyone who can read history can confirm a guessed tenant ("acme|") was
redacted. Spec 256 Decision 1 requires the audit to hold "no ... free text from the target"; ADR-0013 says "Nothing
in it comes from the target" and acknowledges guessability only for record digests. Spec 256 US2 ("nobody can recover
the content from the digest") contradicts ADR-0013 Consequences ("can be confirmed by guessing"). F-1301 records only
the FR-004 conflict. Recommendation: record both as S3 documentation/intent conflicts with a maintainer question.

### R-11 (S3, angle 1) — Intent treated as settled where it is a working assumption

48 of 61 decisions are `Assumption` (`PC/decisions.md`). 23 S1/S2 findings cite an Assumption HD in `intended`, and
the matrix turns them into `failed` (product defect). Most also cite an authoritative source, but some rest on the
assumption: F-0401 (ADJ-I5.9 + HD-0401 only), F-0503 (HD-0501), and F-1201's "ADR-0004: 'no live statement outlives
its content'" cites the converse of the property it needs (ERS-I3 is "the converse of ERS-I2",
`ontology/12-erasure.md:46`; ADR-0004 states only ERS-I2). CONVENTIONS reserves `intent-undecided` for this case.
Recommendation: mark these findings conditional on the named HD and keep their gate `open`, not `failed`.

### R-12 (S3, angle 1) — Over-narrow model domains exactly where the S1 findings live

Disclosed by the audit (`MODELS.md:323-350`, `PROOFS.md` §11) but not reflected in the closures: the reviewed design
is checked under concurrency only for graph-only targets on two named graphs, batch size 1, `EraseGraph` only, lock
timeouts as waits, no ledger disable during a run, no prefix targets (the ADR-0013 two-target tenant procedure), no
`EraseNodes`/`EraseEdges`/`EraseAll` concurrency, no restore or snapshot during a run, verify modelled as one cut
(stronger than the pin), no temporal edges, no multi-node (ECP/mirror; §3.7 N-node e2e). The "reviewed design" for the
full tenant procedure (graph target + prefix target) is therefore not established even at model level.

### R-13 (S4, angle 5) — Smaller record issues

- Breadth-B incident-window reruns (`incidents/IVG460SNAP.md`: "Reruns under the IRIS lock were requested from breadth
  B") are not registered, and the record does not name the AUDITB run (pid 7950) it affects.
- F-1201's evidence list includes `live-erase-vs-commit-emptygraph`, whose record says "F-1201 window not reached".
- F-1302's `reproduced-live` rests on the original submission's run (`native-commit_in_unmarked_window`); I verified
  its log (`~/runs/.../playbook/final/native/traces/commit_in_unmarked_window.json`, SHA-256 `675d4453...` matches
  `experiment/playbook-uplift/evidence/runs.json`), but it is not a completion registry id.
- `live-lost-ack-commit` is a re-evaluation after an oracle field fix (`status` -> `result`, commit `c407918c`). I
  judge the fix legitimate (the raw `run.log` shows `result='equal'` in all 6 worlds); the original 6-of-6 failure is
  kept in `run.log` but not registered.

## Review by angle

### 1. Spec against intent

What holds. For erase/redact/replay, the models' invariants track spec 256 and ADR-0013 closely: RED-X2/FR-005 (no
tombstone of live content), RED-B12/SC-001 (completeness for the own target), RED-I1/I2 and SC-004 (others untouched),
Decision 1 (per-target audit), Decision 2 (any-record clearing; F-1301 correctly records FR-004's stale "every"),
Decision 3 (marker honoured by readers and verify; F-1402), ADR-0013 retry-key movement (INV-retry), ADR-0004's
"no live statement outlives its content" (ERS-I2). The intent records are thorough (sources, contradictions,
alternatives; e.g. `intent/HD-1801.md`). Sample of other modules: module 07's TXT-I5 is sourced to ADR-0007 ("every
write under an index-level lock in a transaction"), which F-0701's journal (`b-07-f0701-race`: Build 30,008 records,
none in a transaction) contradicts directly - well-founded. Module 18's S1 F-1801 rests on HD-1801, an Assumption, but
with FR-043, CONTEXT.md and ADMIN_GUIDE cited; acceptable if labelled conditional (R-11). Module 16: the documented
isolation unit is the namespace (ADR-0016) and the HTTP key is global; the audit's graph-mixing findings (F-1603,
F-1604) are framed against graph scoping of answers, which is right; they do not say that no per-graph credential
exists (R-03).

Over-narrow domains (states, graphs, ids, writers, failure modes the models exclude): R-12 lists them; the most
consequential are prefix targets under concurrency (the ADR-0013 two-target tenant procedure), `EraseNodes`
concurrency, restore/snapshot during a run, temporal-only edges (R-04), ledger-global writers other than the ledger
(R-02), and the proofs' P-C02/P-C03/P-C04 (R-06), which remove exactly the S1 failure modes.

Intent relabelled as settled: R-11 (Assumption HDs driving `failed` product-defect cells; ERS-I3 attributed to
ADR-0004). The reviewed-design elements D-1 (cursor kept with the marker) and D-2 (scan bound fixed at mark time)
are this lane's inventions (`PROOFS.md` §7); D-2 changes the documented behaviour (the pin follows the tail) and is
not in spec 256 or ADR-0013. Not recorded conflicts: spec US2 vs ADR-0013 on digest secrecy, and the target digest
(R-10); the receipt's reach statement versus US1/SC-001 (R-01).

### 2. Omitted writers and readers

R-02. The census misses whole mechanisms (formatted and concatenated SQL, variable-name global writes, direct
storage-global writes, object-free plain INSERT into `ledger_revisions`), and among the missed writers four touch the
ledger itself (`restore_snapshot`, `Snapshot.ImportGlobals`, `Ledger.Disable`/`SetStrict`, SQL INSERT into revisions)
plus `PurgeAll`, which the census lists only as "ledger-all". The "bypass writer" grouping is sound for content-only
writers that take no head lock (I agree with its three criteria and with M2's treatment of autocommit as a special
case), but it does not cover ledger-global writers, which need their own obligations; the restore case is the one
the models explicitly leave out. Readers: the SQL `ledger_records` function and `history()` do not honour the
marker or mark redacted revisions; only the Python wrappers check, once, before paging. Derived stores already
covered by findings: BM25 (F-0702), IVF/tree/PLAID (F-0606); `^EmbedQueue`, `docs_quarantine`,
`edge_vector_quarantine` and `^ArnoKG` (stale until EraseAll, `ArnoAccel.cls:299-303`, `Eraser.cls:806`) are not
(helper sweep, inspected; I did not probe them).

### 3. Fairness and environment premises

| Premise | Where | Status |
|---|---|---|
| `productive_fairness` (work eventually happens while rank > 0) | `proofs/src/progress.rs:190-192`, `actors/src/fairness.rs:22-24` | assumed; not derived from PF-1..PF-4 (R-06) |
| `infinite_execution` | same | modelling convention |
| PF-1 operator re-runs after a stop | `PROOFS.md` §5 | assumed; F-C1303 shows re-running with `max_batches` does not finish at the pin |
| PF-2 ledger re-enabled and stays enabled | same | assumed; `Disable` takes no lock (R-02) |
| PF-3 every erasure ends | same | partly tested (contract *Process stop*, *Lock wait*, `env-contract-r2`); erasure inside a caller transaction not tested |
| PF-4 scheduling and commit | same | assumed; lock timeouts, waiter fairness, lock escalation, lock-table capacity outside the contract subset |
| P-C01 each step one atomic transaction | `PROOFS.md` §8 | tested for nesting/deferral/process stop; instance crash not (Q12b open) |
| P-C02 no ledger-bypassing writes | same | false at the pin (census, R-02); also an unlisted progress premise (R-03, R-06) |
| P-C03 one target predicate | same | false at the pin (F-1304, F-1305) |
| P-C04 no erasure abort | same | false at the pin (F-C1201, live) |
| AG EF path premises: writers quiet, operator resumes, no permanent stop, re-erase allowed | `MODELS.md:308-313` | stated, not tested |
| batch size 1; lock timeouts as waits | `MODELS.md:59-61`, `:335` | stated (a subset of schedules for safety; not for progress or SC-003) |
| E-1 embedded SQL behaves as dynamic SQL | `CONTRACT.md` "Outside" | untested; Eraser and Adjacency use `&sql`, the contract cases use dynamic SQL |
| SQL COMMIT/ROLLBACK level semantics 2026.1 vs 2026.3 | `CONTRACT.md` "Version difference" | blocked-access (no 2026.3 engine / 5.4.0 driver) |
| ECP, mirroring, multi-node; journal restore | `CONTRACT.md` "Outside" | outside; §3.7 N-node e2e open |

Do the progress-only controls isolate progress? The proof control does (one error at `progress.rs:165`, every other
function verifies) and the five model progress mutants each pass safety and fail only AG EF (`MODELS.md:315-321`).
But they demonstrate D-1 only; D-2 has no control, and no control weakens a fairness premise, so nothing shows which
premises the progress result actually needs.

### 4. Relationship to executable code

The audit keeps model and product apart in most prose (CONVENTIONS "Evidence"; `PROOFS.md` §11; `MODELS.md`
opening), and every model-level cell in `orchestrator_status.json` that carries `level` is correct. Where it slips:
R-05 (matrix summary without level; inconsistent 3.3-model-check semantics; 3.8 closed without fixes or decisions;
`PROOFS.md:152`; ontology `proved:` tags on contradicted product statements). The only code correspondence is journal
trace conformance on one sequential scenario (R-09); 3.4-statements, 3.5-handlers, 3.5-lockplans and 3.6 are
correctly open. Journal-oracle blind spots: reads, locks, process-private and `^IRIS.Temp` globals, background-job
writes under another pid, rules that check soundness but not completeness or liveness, and a single target shape.
Additionally the oracle cannot validate the journal itself on a database with journaling off or `%NOJOURN`
statements (outside the contract subset; I found no `%NOJOURN` in the product).

### 5. Evidence audit

See the table below. 377 records hashed; 38 runs read against `observes` (35 by a helper with verbatim
excerpts, re-checked where marked, 3 by me), plus the 6 overwritten originals by hash. Mismatch count: **8** (2 contradicted `observes`, 6 SHA-256 mismatches
of overwritten decisive logs, disclosed). 16 partial. Root causes (ratchet groups): RC-E1 `observes` written from
files other than the registered log (16 partial); RC-E2 decisive logs overwritten by a rerun writing to the same
directory (6); RC-E3 hand-written counts in `observes` (2 mismatches); RC-E4 `result` semantics (R-08); RC-E5 the
matrix guard checks only `run:` refs (R-07); RC-E6 model results never registered (breadth-B: 132 results, 90 cited by closed cells).

### 6. Adversarial

As the tenant to be erased: copies outside the receipt (R-01: legacy revision rows, snapshots, quarantines); history
tombstoned without the node history (F-1305, recorded) or with live temporal-only edges' history gone (R-04); the
tenant's name confirmable from `target_sha256` (R-10); content re-entering history through an adoption that races
the redaction (R-02, inferred) or a restore (F-1801, recorded); `actor` fields that name the tenant are kept by design
(ADR-0013).

As the operator: a paced run never finishes (F-C1303, recorded); one stuck run blocks every other tenant's redaction
and every ledger reader, with no abandon (R-03); `Disable` mid-run stalls the run silently until re-enabled; a
"complete" receipt for a graph-per-tenant target while node history remains (F-1305); a 4.5.x upgrade leaves a
second copy the receipt does not mention (R-01); SC-002/SC-003 (10,000 revisions verify-equal; <1 s commit blocking)
are not yet evidenced on this engine (validation lane in progress).

As an attacker holding the API key (there is no graph-scoped key): read every tenant's content through Cypher and
`/admin/export`; write into a target under redaction (`/admin/load`, Cypher) to keep the marker set indefinitely
(R-03); `POST /admin/snapshot` to keep pre-redaction archives in the server's temp directory (R-01); with SQL INSERT
on `ledger_revisions`, wedge the ledger (R-02, inferred); with Native API access, everything (F-C1803, recorded):
the revision immutability is enforced only by SQL triggers and `%OnBeforeSave`, which raw global writes bypass.

## Claims I could not verify

Not verifiable by me without a live run or a missing artifact; I neither accept nor reject these:
- All live reproductions beyond reading their logs (I did not rerun anything; observation-only).
- F-1302's live reproduction and the original L1/L2 proofs that the ontology's `proved:` tags name: they belong to
  the original submission (`9c3719c1`); I checked one original log's SHA-256 against its registry, nothing more.
- "88 verified, 0 errors" for `core-proofs-baseline` (the registered log was overwritten; only the recheck's
  unhashed `baseline.json` holds the count) and the claim that the recheck used `--no-cheating` and the same sources
  (`862f8bad...` appears in neither registered log).
- The breadth-B model results (132 files in `models/breadth-b/results/`, 90 cited) behind closed cells of modules 09-11: no
  registered decisive run, only dev logs.
- SC-002 and SC-003 of spec 256 (validation lane "in progress"; `validation/SUITES.md`), the instance-crash world
  (Q12b), editions (Enterprise, 2026.3, driver 5.4.0: blocked-access), multi-node behaviour.
- My own inferred items: R-01 legacy rows (needs an upgrade-path probe), R-04 temporal-only edges, the adoption race
  and the revision-insert wedge in R-02. Each is from source reading and needs one live probe.
- Pin and namespace attribution of individual logs: no registered log records the pin; claimed namespaces
  (AUDITCORE, AUDITENV, AUDITIB) do not appear in their logs. I relied on registry metadata and
  `check-product-scope.sh` having run at registration.
- Whether runs active in the 23:02:53-23:03:40 incident window (AUDITB pid 7950) are among those cited; the
  requested breadth-B reruns are not registered.

## Evidence audit (mechanical, with a ratchet)

Method. (a) SHA-256 of every registered log recomputed (script over all 377 records in `PC/evidence/runs/`):
**371 ok, 6 mismatch** (all six `core-proofs-*` originals; overwritten by the orchestrator's recheck at
00:31:29-00:31:44 UTC, disclosed in `incidents/superseded-logs.json`). (b) 38 runs read against their `observes`,
prioritising findings marked reproduced-live and cells marked closed: 35 by a helper that quoted the log verbatim
(I re-checked the two mismatches, `b-07-f0701-race`, `live-fc1303-bounded-resume` and the core-proof logs), 3 by me;
rows 39-44 are the six overwritten originals, checked by hash.
Verdicts: MATCH = every factual claim is in the registered log; PARTIAL = some claims only in another file or absent;
MISMATCH = contradicted, or SHA-256 differs.

| # | Registry id | kind / result | SHA | Verdict | Note |
|---|---|---|---|---|---|
| 1 | live-f1201-reproduced | live / fail | ok | PARTIAL | log holds 8 verdicts; statement 4001 SET/KILL order, 4,000 statements, nodes in G only in `trial-0.json`; build only in `run.log`; "Community", AUDITCORE absent |
| 2 | live-native-rerun-1314 | live / pass | ok | MATCH | 177 checks all PASS (31+10+29+27+21+7+7+14+9+22); `result=pass` although it reproduces F-1303..F-1306, F-1401, F-1402 |
| 3 | live-fc1303-bounded-resume | live / fail | ok | PARTIAL | 60 calls, 0 tombstoned, `complete=false`, 9 left, control 9 in 14 batches: supported; "30 revisions of zeta then 3 of acme" and "scanned the first 20 records" not in the log (mechanism is from source) |
| 4 | trace-conformance-ledger | trace / pass | ok | **MISMATCH** | "18 product transactions" vs `txn_count_per_op` summing to 17 (`traces/conf2/offline-check.log:15-24`; `checked`: commit 4, erase 1, redact 11, verify 1); "53 journal units" only in `conf2/run.log:88` |
| 5 | trace-conformance-controls | control / pass | ok | MATCH | 5 mutated traces rejected, unmutated clean |
| 6 | decoder-map-ledger | check / pass | ok | MATCH | 15/15, unmapped [], dead [], self-test PASS |
| 7 | env-contract-r2 | check / pass | ok | PARTIAL | 283 / 0 outside / 282 singleton / 17 of 17 in `report.json`; engine build only in `driver.log`; case-family split only countable from `cases.json` |
| 8 | ontology-check-final | check / pass | ok | PARTIAL | "3877 statements, 0 violation(s) ... index current"; "19 repaired modules" and the 1406 baseline only in `baseline-original.log` |
| 9 | core-refine-m2-reviewed | mc / pass | ok | MATCH | "2448115 states ... exhaustive within bounds", expect pass, result pass |
| 10 | core-proofs-recheck-baseline | proof / pass | ok | PARTIAL | log = cargo warnings + "Finished `dev` profile" + WALLSECONDS; "88 verified, 0 errors" only in unhashed `baseline.json`; `--no-cheating`, sources SHA absent |
| 11 | core-proofs-recheck-f1302_unlocked_start | control / expected-violation | ok | PARTIAL | errors at `protocol_rl.rs:305/309/323` supported; "same as the lane's run" only provable from the overwritten lane log |
| 12 | live-lost-ack-commit | live / pass | ok | PARTIAL | registered log is a re-evaluation ("0 of 6"); 1,500 figures and `equal` only in `results.json`; "oracle self-test rejects..." absent; raw `run.log` says "6 of 6" before the field fix (`c407918c`, judged legitimate) |
| 13 | breadth-a-mc-all | mc / pass | ok | MATCH | "model checks: 104 of 104 met their expectation", 14 families |
| 14 | writer-census | check / incomplete | ok | **MISMATCH** | "56 inside the original manifest's 15 plans, 23 more reached by call" vs `covered_sites 56` = 31 with a plan + 25 via call (`checks/writer-census.json:2-5`); 9 plans and 9 store labels in `detail`, not 15 and 8 |
| 15 | b-07-f0701-race | live / fail | ok | MATCH | N 3000 / totalLen 12000 vs 3001 / 12003; reader saw [1,2]; Build 30008 records, 0 in a txn; AUDITB (re-checked) |
| 16 | b-08-live-f0802 | live / fail | ok | MATCH | oracle text, "verdict": "reproduced", AUDITB |
| 17 | b-08-live-f0814 | live / fail | ok | MATCH | hostile filter rows, `execute_aql_has_read_only: false` |
| 18 | b-08-live-f0818 | live / fail | ok | MATCH | carried start includes the leak row |
| 19 | b-10-live-nkg | live / fail | ok | MATCH | answer [], first steps, betweenness refusal, footprint pids; log labels F-1005 not-reproduced |
| 20 | b-11-live-findings | live / fail | ok | MATCH | every sub-claim present |
| 21 | breadth-a-live-05-temporal | live / fail | ok | MATCH | all values present |
| 22 | breadth-a-live-04-adjacency | live / fail | ok | MATCH | 5 reproduced=True with stated values |
| 23 | breadth-a-live-06-vectors | live / fail | ok | MATCH | values present; p0614/p0616 judgements are the registrant's |
| 24 | c15-live-reify | live / fail | ok | MATCH | outermost 1, link 0 after erase, secret props stay |
| 25 | c15-live-delreif2 | live / fail | ok | MATCH | rows and label indexes 1 -> 0 in both graphs |
| 26 | c16-s3-graphql-sample-api | live / fail | ok | PARTIAL | the 500 on the Cypher route only in `s3_sample_api.log:33`; "timeout=1" not recorded |
| 27 | c17-live-engine | live / fail | ok | PARTIAL | log truncates entries at ~1,200 chars; shapes, `u_spo_graph_ekey`, 0 journal records only in per-finding JSON |
| 28 | c18-live-ledger-overlay | live / fail | ok | MATCH | head 3 -> 2, `LedgerRevisionD(3)` error, replay of seq 3, verify "equal", secret restored |
| 29 | c18-live-file-helpers | live / fail | ok | PARTIAL | FileExists/ReadFileChunk/ImportGlobals results present; namespace and arguments not recorded |
| 30 | c18-live-edge-vectors | live / fail | ok | PARTIAL | routed `kg_eemb_` table after restore not shown |
| 31 | ib-HD1201-open-erasure | probe / fail | ok | PARTIAL | TLEVEL 1, receipt complete with 2 tombstones, rows back, "RESULT: VIOLATED" present; AUDITIB and setup absent |
| 32 | b-07-f0711 | live / fail | ok | PARTIAL | ids from both graphs, `search_documents []` present; graph names and "SQLCODE -30" absent |
| 33 | cmc-snap-reviewed | mc / pass | ok | MATCH | "MET \| 65 states ... exhaustive within bounds" |
| 34 | ontology-independent-recheck | check / pass | ok | PARTIAL | counts present; "shares no code", "equal repairs.json" absent |
| 35 | live-erase-vs-commit-fk | live / pass | ok | PARTIAL | `pass` while the erase fails 8/8 (claim: ERS-I1/I3 hold); SQLCODE -124 only in `run.log`/trials |
| 36 | ib-HD1801-merge-restore | probe / fail | ok | MATCH | `ib3_hd1801.log:24` restored_globals incl. IVG.Ledger and LedgerRevisionD; `:26` history 1-4; `:28` "ID key not unique"; `:30` verify diverges |
| 37 | core-proofs-recheck-progress_rewind | control / expected-violation | ok | PARTIAL | `progress.rs:165` error present (`:73`); "87 verified" and "fails only" only in the unhashed JSON |
| 38 | native-commit_in_unmarked_window (original registry) | live / pass | ok (`675d4453...`) | MATCH | 15 checks ok incl. "the late commit's relationship record became a tombstone while its content is live" |
| 39 | core-proofs-baseline | proof / pass | **mismatch** | **MISMATCH** | overwritten at 00:31:29; superseded by #10; record says "~00:40" |
| 40 | core-proofs-f1201-erase-unlocked | control / expected-violation | **mismatch** | **MISMATCH** | overwritten 00:31:38; superseded |
| 41 | core-proofs-f1302-unlocked-start | control / expected-violation | **mismatch** | **MISMATCH** | overwritten 00:31:32; superseded by #11; cited by closed 3.3-controls (12-14) and 5-mutants-located |
| 42 | core-proofs-f1303-other-marker | control / expected-violation | **mismatch** | **MISMATCH** | overwritten 00:31:35; superseded |
| 43 | core-proofs-f1306-replay-reapplies | control / expected-violation | **mismatch** | **MISMATCH** | overwritten 00:31:41; superseded |
| 44 | core-proofs-progress-rewind | control / expected-violation | **mismatch** | **MISMATCH** | overwritten 00:31:44; superseded by #37; cited by closed 3.3-progress-controls |

**Mismatch count: 8** (rows 4, 14: `observes` contradicted by the log; rows 39-44: SHA-256 differs, disclosed as
superseded). Partial: 16. Of the 6 SHA mismatches, the orchestrator's recheck reproduces the same error locations
(rows 11, 37), so I treat them as an evidence-hygiene defect, not a false result.

**Ratchet.** These enter the review list and leave it only when fixed, grouped by root cause: RC-E2 (rows 39-44:
restore or re-register with logs that carry their own counts), RC-E3 (rows 4, 14: correct the `observes` text),
RC-E1 (the 16 partial rows: register the file that holds each claim, or narrow the claim), RC-E4 (normalise
`result` to one meaning, e.g. "the run's expectation was met", and record product defects in a separate field),
RC-E5/RC-E6 (R-07). A re-review must re-run the SHA script over the whole registry and re-read every row above.

## Conditions that would change the decision to sign-off

Sign-off on "spec against intent" and on the account's accuracy needs all of:
1. R-01, R-03, R-04 recorded as findings (or refuted by a live probe each), with the receipt's reach statement and
   SC-001 scope treated as obligations in the matrix.
2. R-02: a census that sees formatted/concatenated SQL and variable-name global writes (with a self-test planting
   one of each), the ledger writers listed there given (invariant, writer) obligations, and restore-during-a-run
   either modelled or recorded as an open obligation.
3. R-05: a level column in `MATRIX.md`; one meaning for 3.3-model-check across lanes; 3.8-findings-disposed reopened
   (it closes only with fixes or maintainer decisions); `PROOFS.md:152` corrected; Q8b done so that no product
   statement carries a `proved:` tag the audit's findings contradict without citing them.
4. R-06: P-C02/P-C03/P-C04 shown as refuted at the pin on every proof-level closure; P-C02 added to the progress
   premises; a D-2 control; each PF premise mapped to a test or listed as assumed in the trust/premise inventory.
5. R-07/R-08: the matrix builder validates every evidence reference (any prefix) against the registry and its
   result; breadth-B model results registered from a scripted full run; the 8 mismatches and 16 partials of the
   evidence table fixed or narrowed; `QUEUE.md`'s closed-cell claim made true.
6. The §3.8 artefacts the orchestrator lists as pending (STATUS.md, trust inventory, test reflection) exist, and
   state each guarantee's level as the CONVENTIONS require.

Even with all of these, the second clause of the §3.8 gate ("every finding becomes a fix or a recorded decision")
stays open until a maintainer answers `decisions.md`'s questions: an observation-only audit cannot close it. My
sign-off would then cover the account, not the product.
