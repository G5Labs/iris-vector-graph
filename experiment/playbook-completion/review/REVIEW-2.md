# Independent review, second pass (playbook §3.8, §5c)

Reviewer: independent reviewer lane (read-only). Product pin `3eaa79cf` (tree `b098a6f4`, unchanged). Audit state
reviewed: `3d1095e3` plus uncommitted lane work present at 2026-11-14 ~04:40 UTC (registry: 711 records, 336 added
since the first pass). No IRIS connection, no live run, no commit; I wrote only `review/REVIEW-2.md` and
`review/review-2.json`. `PC/` = `experiment/playbook-completion/`. First pass: `review/REVIEW.md` (R-01..R-13).

Not reviewed, per the coordinator's condition: `PC/iris-contract/` (no `VALIDATED_ROUND` exists) and `PC/versions/`
(no `VERSIONS.md` exists); their registry entries (`env-ext-*`, `ver-*`) are not assessed.

## Decision: **no sign-off**

The audit answered the first review seriously. Five of the seven risks I raised are now recorded findings with live
evidence that I could check, one of them S1 (F-C1308, temporal-only edges) and one S1 that needed a release-upgrade
probe (F-C1306). The census sees the writers I listed, the matrix separates verification status from product status,
the findings gate is open, and the proofs state that their premises are false at the pin. What still stops a
sign-off is the account's accuracy, not the work done:

1. The matrix's **product column under-reports failures** in a way a reader will misread (R2-01), and the corrected
   writer census was **never carried into the matrix** (R2-02).
2. The ontology was re-tagged **before** the follow-up and does not cite any of the eight new findings; one of my four
   first-pass cases (RED-B4) is still an uncited `proved:` tag on a contradicted statement (R2-03).
3. Several new artefacts contradict each other or overstate (STATUS §3.1 "closed", `5c-reviewers` closed against its
   own remaining text, the closure scan versus the census) (R2-04), and the trace-refinement check added for
   correspondence is blind, by construction, to the S1 defect F-C1308 and to redaction completeness (R2-05).

Exact remaining conditions are at the end.

## 1. Responses to the first review, checked against the evidence

| Item | Response | What I checked | Verdict |
|---|---|---|---|
| R-01(a) snapshot copies | F-C1304, S2, `fu-r01a-snapshot-copies` | registry record; log via the evidence audit (table §4) | **addressed** |
| R-01(b) embedding_quarantine | F-C1305, S3, confirmed-source (by design; no live row: only the 4.0.0 migration writes one) | `followup/findings.json`, `Eraser.cls:300-302, 756-758` | **addressed** |
| R-01(c) legacy `Graph_KG.ledger_revisions` | F-C1306, S1, `fc1306-legacy-ledger-rows` (live) | `fc1306/RESULT.md`; registry; evidence audit | **addressed**; scope deviation, see R2-07 |
| R-02 writer census | `tools/writer_census.py` extended; `$RUN_DIR/followup/writer-census.json`: 269 sites, 46 undeclared writers, 162 obligations, 20 conditional, 3 write-set gaps | `detail` by file and mechanism (below) | **tool addressed; matrix not updated** (R2-02) |
| R-03 marker held open | F-C1307, S2, `fu-r03-marker-held-open` | registry; evidence audit | **addressed**; P-C02 now named as a progress premise in `PROOFS.md` and `PROOF-DEBT.md` D-8 (not in `TRUST.md`'s premise table) |
| R-04 temporal-only edges | F-C1308 S1, F-C1203 S1, `fu-r04-temporal-only-live-b` | I read `$RUN_DIR/followup/r04.json` myself: `G_content_rows_in_graph` all 0; `G_redact_unerased.complete = True`, `records_tombstoned = 1`; `G_window_after` still returns the edge (w 7.5); `P_window_after_redact` still returns fq5's edge; `G_verify_after = equal` | **addressed**, confirmed |
| R-05 model results as product status | matrix now has status / product obligation / level; findings gate open (18); `PROOFS.md:152` corrected; 11 ontology statements `[model-only]` | `build_matrix.py:90-180`, `MATRIX.md`, `obligations.json`, ontology rows | **partly addressed** (R2-01, R2-03, R2-04) |
| R-06 proof premises | `PROOFS.md` "Premises the pin violates"; `premises_refuted_at_pin` on 9 proof-level cells; progress premises "none derived or tested" | `PROOFS.md:240-254`, cells | **addressed for the account**; the D-2 progress control is still absent and not listed as debt; breadth proofs omit one violated premise (R2-06) |
| R-07 closed-cell guard | closed needs a decisive registered run, or is graded `inspected`; 145 closed = 106 registered-run + 39 inspected | builder logic, cell list | **addressed**; 17 of the 39 `inspected` closures cite only a findings file and 3 more only a findings file plus footprints (circular but labelled) |
| R-08 misstated descriptions | `erratum` fields on `trace-conformance-ledger` (17 transactions) and `writer-census` (31 + 25 + 48) | `git diff` of both records against their first commit; the logs | **addressed**; the records were edited in place and `registered_utc` overwritten (R2-09) |
| R-09 trace conformance blind spots | correspondence lane: α contract-step check, line coverage, lock probes | `correspondence/CORRESPONDENCE.md`, `tools/abstraction.py:440-505` | **partly addressed** (R2-05) |
| R-10 target digest | F-C1309, S3, `fu-r10-target-digest`; maintainer question | registry; evidence audit | **addressed** |
| R-11 assumed intent as defect | no change (F-0401, F-0503, F-1201 unchanged); F-C1102 repeats the pattern | `findings/audit/04.json`, `05.json`, `12.json`, `11-orchestrator.json` | **not addressed** (R2-08) |
| R-12 narrow model domains | unchanged; disclosed | `MODELS.md`, `PROOF-DEBT.md` D-9, D-10 | accepted as disclosed debt |
| R-13 incident reruns | `b-08-*-rerun` (19 + 4), `val-integration-1-c00-rerun` (identical outcomes, 342 cases) | registry, `SUITES.md` "Incidents" | **addressed** |

**R-02 detail.** The corrected census sees every writer I listed except two benign or marginal ones: restore
(`snapshot.py:1679`, mechanism `py-dynamic-global`, stores `ledger-all` and `meta`), `Snapshot.ImportGlobals` and
`SetNodeJSON`, `Disable`/`SetStrict` (`state`), the SQL INSERT surface on `ledger_revisions`, `copy_ledger_history`,
`LedgerApply`'s concatenated SQL (20 `os-concat` sites), the Cypher translator (86 sites via `cypher.write`),
nodes_edges, temporal, bulk_loader. Still unseen: `PropWrite.SetVal` (`PropWrite.cls:55`, `Set @tRef = tRow`; it
re-types an unchanged value, so harmless for these invariants) and the migration statement lists built as strings
and executed later (`schema.py:1461-1495`), plus the 3.2.0 rescue tables (`rdf_edges__ivg400rescue` /
`__ivg400unplaced`, `schema.py:50-54, 2976-3013`), which are copies of edge content rather than writers of the eight
stores. 15 sites remain unresolved (listed in the census).

## 2. New findings of this pass

### R2-01 (S2, angle 4) — The product column under-reports failures

`MATRIX.md` totals: product `fails` 173, `holds-in-model-only` 13, `unknown` 337. Three mechanisms lose failures:
- **Level string mismatch.** The builder sets `holds-in-model-only` only when `level == "model"`
  (`build_matrix.py:174-175`), but the orchestrator's cells say `"reviewed model"` and the correspondence cells say
  `"as-built (pin 3eaa79cf), AUDITC traces"`. The 12 reviewed-model cells therefore show `unknown`, including
  3.3a-domain-contract, whose own `remaining` says "as-built fails (F-1304/F-1305/F-1306)".
- **Product-scope cells never receive findings.** Findings attach by module number (`build_matrix.py:121-124,
  150-151`); a cell with module `product` gets none. 3.3-progress-controls shows `unknown` although F-C1303
  (reproduced live) lists that gate.
- **A cell's own text contradicts its label.** 08 / 3.3-model-check is `holds-in-model-only` while its `reason` says
  "as-built reproduces F-0805, F-0806, F-0802, F-0815, F-0816, F-0818, F-0819, F-0820" (it cites only the reviewed
  checks, and the m08 ids do not match the registered `b-mc-m08-*` ids). 15 / 3.3-model-check is the same pattern.
  Modules 04 and 11 (3.3-L1/L2/refinement/controls) are `holds-in-model-only` while their controls reproduce the
  pin's behaviour and F-0801, F-1108, F-C1101 are reproduced live.

Recommendation: normalise `level` to the three values; attach findings to product-scope cells through their gates;
derive `fails` when a cell's as-built evidence is an expected violation; re-wire the m07-m11 refs to `b-mc-*`.

### R2-02 (S2, angle 2) — The corrected census is not in the matrix

`followup-writer-census` is cited nowhere in `obligations.json` or `orchestrator_status.json`. The 3.3a-writesets
cells of 12-14 still cite `writer-census` with "100 new (invariant, writer) obligations"; `writer_obligations` is
still 83; module 18's cell does not show the three write-set gaps of `restore_snapshot` (marker, idemRedacted,
redactedRev). `FOLLOWUP.md` "For the orchestrator" asked for exactly this. `STATUS.md` quotes the corrected numbers,
so STATUS and the matrix disagree.

### R2-03 (S3, angle 4) — The ontology does not carry the follow-up findings

The re-tag (`f3fe3917`) precedes the follow-up (`78e7a5e8`). None of F-C1304, F-C1305, F-C1306, F-C1307, F-C1308,
F-C1309, F-C1203, F-C1102 appears in any `ontology/*.md`. Statements they contradict keep their tags uncited:
RED-B7 "holds no content of the target" (F-C1309), RED-B12 "no ledger record, row or reader shows its ids or values"
(F-C1306), RED-B1.1 "never makes a tombstone of the record of live content" (F-C1308). RED-B4 "A retry key of a
redacted revision can never be used again" still carries `proved:theorem_retry_refused` with no `[model-only]` and no
F-1801 (`ontology/13-redaction.md:79`; `core-m3-as-built-F1801-keys`). The `[model-only]` rule
(`ontology/METHOD.md:40`) fires only on cited findings, so it cannot catch a missing citation.

### R2-04 (S3, angles 4 and 5) — Account artefacts that contradict the matrix or themselves

- `STATUS.md` marks §3.1 **closed**; the matrix has 3.1-cells 10 open, 3.1-coverage 19 open, 3.1-intent 18 open.
- `5c-reviewers` is `closed` while its `remaining` says "a randomized simulator through the real product with global
  invariants after every commit was not run" - the third reviewer §5c names.
- `corr-closure-scan` (§4.7 of `CORRESPONDENCE.md`): "44 product write sites of the ledger state: all but one belong
  to a modelled action" (restore). The corrected census lists four more ledger writers outside the ledger classes
  (`ImportGlobals`, `SetNodeJSON`, `copy_ledger_history`, the SQL INSERT surface).
- Validation's product-defect results (`SUITES.md`: decimal scores, the `create_edge_temporal(...,
  temporal_structural_rows=True)` cursor failure S2, Leiden ARI, TCK Unwind1 [3], SC-010 latency) are in no
  `findings/audit/*.json`.
- `TRUST.md`'s premise table omits "no write outside the ledger" (P-C02) for progress and the SynchCommit premise
  behind F-C1102, both named in `PROOFS.md` / `STATUS.md`.

### R2-05 (S3, angle 4) — The correspondence check is blind to F-C1308 and to completeness

The correspondence lane's α (`correspondence/CORRESPONDENCE.md` §2) maps `create_temporal_edge` to no content and
excludes temporal-marked rows, as `replay.py` does. Its "tombstone of live content" check
(`tools/abstraction.py:466-472`) folds the record's keys against α's rows, so a live temporal-only edge is never
"live": F-C1308's failure passes the check by construction. The redaction step check verifies soundness, counts,
digests and the marker, but nothing checks completeness at Final (every live record of the target tombstoned;
`theorem_final_effect` in the proofs), so F-1305 / F-C1302-class outcomes also pass. All checked traces are sequential
apart from the F-1201 pair. The lane's honesty about "unchecked lines" (281 ObjectScript, 181 Python) is good; the
exercised lines are checked only against a contract with these two holes.

### R2-06 (S3, angle 3) — Remaining premise gaps

- No progress-only control for D-2 (scan bound fixed at marking), the element behind "commits by other tenants cannot
  prolong a run" (`PROOFS.md:145-147`); it is not in `PROOF-DEBT.md`.
- `proofs-breadth/PROOFS.md` "Premises the pin violates" lists P-L4, P-L6, P-A4 but not P-A3 ("an eraser of g
  overlaps no writer of g", status "explorer restriction; not established for inserts of new rows"). The core models'
  F-C1202 (EraseGraph's adjacency kill drops an edge committed after its row delete) and F-1201 (live) are that
  overlap at the pin.

### R2-07 (S3, process) — F-C1306's probe compiled a non-pin release, outside the written rule

`fc1306/RESULT.md` "Scope notes": the pinned fixture compiled **v4.5.1's** classes into scratch namespace
IVG262FC1306 and possibly loaded the fixture's `IVGDev.Setup` helper into `%SYS`; `SUITES.md` also records
`IVGDev.Setup/Run` compiled into `%SYS`. `CONVENTIONS.md` (unchanged since the first pass) allows scratch fixtures that
"compile the pin's unmodified classes" and says "Compiling anything other than the pin's own classes ... remains out
of scope". The lane disclosed it (`FOLLOWUP.md` even called it out of scope before it ran), and the evidence is
sound, but the rule was not amended and I found no operator ruling for it (the 03:16Z ruling in `SUITES.md` covers
other items). It needs an operator decision on record; an agent's note cannot authorise it.

### R2-08 (S3, angle 1) — Assumed intent still graded as product defect

R-11 is unchanged, and F-C1102 (S2, `live-crash-world-r2`) repeats it: its `intended` says "No IVG document states a
durability premise or the IRIS setting it needs", and its `notes` say "Environment premise rather than a code
defect", yet it is `reproduced-live` S2 and drives `fails` cells. The live observation is solid (one trial per world,
SynchCommit=0 only); the classification should be `intent-undecided` with the premise recorded in `TRUST.md`.

### R2-09 (S4, angle 5) — Errata edited the original records in place

Both erratum records keep their id and log but replace `observes`, `experiment_head` and `registered_utc` (first
registered 2026-11-13T23:23:31 and 23:05:38; now 2026-11-14T01:06:23). The history is recoverable from git, so no
evidence is lost, but the record no longer says when it was first registered. Keep the original time and add an
`erratum_utc`.

### R2-10 (S3, angle 6) — Tenant copies still unrecorded

From my first pass, still in no finding: `^EmbedQueue(reqId, "text" | "node_id" | "result" | "graph")` keeps a
tenant's text and vectors until `ClearDone` (DONE entries only; ERROR and PENDING stay; `EmbedQueue.cls:2-20,
181-195`) and no erase path touches it; `docs_quarantine` and `edge_vector_quarantine`; the stale `^ArnoKG` snapshot
until `EraseAll` (`ArnoAccel.cls:299-303`); the 3.2.0 rescue/unplaced edge tables. Each is inspected only.

## 3. New material

- **`STATUS.md`** is honest in its verdict ("not complete") and its model/product separation, apart from R2-04's §3.1
  line; its S1 table matches the findings files.
- **`TRUST.md`, `PROOF-DEBT.md`**: complete for the proof crates (empty trust inventory, scanned); premise table gaps
  in R2-04; D-1..D-11 are accurate, D-2 control missing (R2-06).
- **`correspondence/`**: the strongest code correspondence in the audit, and candid (no handler proved; unchecked lines
  exact; lock plans observed with `%SYS.LockQuery`, matching source everywhere). Limits in R2-05; closure scan in
  R2-04. 3.6-keys and 3.6-fk are `closed` for 12-14 on sequential traces; read them as "no violation observed", which
  the matrix's `product unknown` correctly says.
- **`proofs-breadth/`** (modules 11, 04): 94 verified, 7 located controls, each with a proved reachable counterexample;
  model-level and labelled so; P-A3 in R2-06.
- **Crash world** (`traces/crash_world.py`, `live-crash-world-r1-invalid`, `live-crash-world-r2`): r1 correctly kept as
  `incomplete` (60,000 operations exceeded `max_ops`, so nothing was in flight). r2: in-flight commit all-or-nothing
  after SIGKILL and journal recovery; acknowledged commit (seq 3, 12,000 rows) absent after restart with SynchCommit=0;
  exactly-once retry held. One trial per world; SynchCommit=1 untested. Classification in R2-08. The deliberate crash
  caused the 01:19-02:18 health alert (`incidents/HEALTH-ALERT-0119.md`); I found no registered run in the crash window
  (01:19:03-01:21:11) other than the crash itself.
- **`traces/lost_ack.py`**: oracle sound; `verify` of `None` is accepted as equal (`lost_ack.py:77`), a small weakening;
  the server-side-rollback branch was not observed (disclosed).
- **`traces/fc1303_resume.py`**: deterministic world (30 zeta revisions = 60 records ahead of acme, batch 1, cap 20), so
  60 calls stand for "never"; the unbounded control completes in 14 batches. Sound.
- **`incidents/`**: USER-REDEPLOY-08 and HEALTH-ALERT-0119 dispositioned with reruns; superseded core-proof logs still
  listed.
- **`validation/`** (interim): SC-002 (10,000 revisions, verify equal) and SC-003 (100,000 records in 1.42 s, longest
  batch 39 ms; committer-side longest overlapping commit 311 ms) now have one decisive run each on Community, repeats
  pending; triage is rule-based with reruns for every product-defect class; intermittent classes are kept as leads.
  Findings not filed (R2-04).

## 4. Evidence audit (second pass, runs added since the first pass)

EVIDENCE_PLACEHOLDER

## 5. Conditions for sign-off (exact)

Sign-off on spec against intent and on the account's accuracy (§3.8 first clause) needs all of these; items 1-4 are
mechanical and small:
1. **Matrix product column (R2-01):** `level` normalised; findings attached to product-scope cells by gate; a cell
   whose as-built evidence is an expected violation or a reproduced finding shows `fails`; the m07-m11 refs wired to
   the registered `b-mc-*` ids. After the fix, no cell's `remaining`/`reason` may say "as-built fails" or "as-built
   reproduces" beside a non-`fails` product label (a check in `build_matrix.py --check`).
2. **Census in the matrix (R2-02):** the 162 obligations, 20 conditional obligations and 3 write-set gaps of
   `followup-writer-census` as open cells; `corr-closure-scan` reconciled with the census's ledger-writer list.
3. **Ontology (R2-03):** every reproduced follow-up finding cited on the statements it contradicts (at least RED-B1.1,
   RED-B7, RED-B12, RED-B4), with `[model-only]` on their `proved:`/`mc:` items; the checker extended to flag a
   `proved:` tag on a statement that a reproduced finding's `intended` field cites but the statement does not.
4. **Account consistency (R2-04, R2-09):** STATUS §3.1 matches the matrix; `5c-reviewers` open until the randomized
   simulator runs or the gate is recorded as not applicable with a reason; validation's product defects filed as
   findings; TRUST's premise table complete (P-C02 for progress, SynchCommit); erratum records keep their first
   `registered_utc`.
5. **Classification (R2-08, R-11):** findings whose intent rests only on an Assumption HD or on no source (F-0401,
   F-0503, F-C1102, and F-1201's ADR-0004 citation) marked `intent-undecided`/conditional, their cells not `fails`.
6. **Scope record (R2-07):** an operator ruling (from the user/operator, not an agent) on compiling a non-pin release
   and the `%SYS` helper, or the F-C1306 evidence re-graded as outside the conventions.
7. **Disclosed gaps stated where read (R2-05, R2-06, R2-10):** the α check's temporal and completeness holes stated on
   the 3.5-handlers / 3.7-trace-replay cells; the D-2 control and P-A3 added to the debt / premise lists; the
   remaining tenant copies recorded (finding or reach obligation).
8. The pending items the audit itself lists: SC-002/SC-003 repeats, the e2e/perf queue, and the contract extension
   and version comparison once `VALIDATED_ROUND` / `VERSIONS.md` exist (to be reviewed then).

The second clause of the §3.8 gate ("every finding becomes a fix or a recorded decision") stays open until a
maintainer answers; an observation-only audit cannot close it, and my sign-off would cover the account, not the
product. Nothing found in this pass is a new unrecorded S1; the open items are about how the evidence is reported.
