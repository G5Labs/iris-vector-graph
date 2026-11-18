# Iteration 64 handoff — census integrity: strict regrade, missed models behind absent, evidence housekeeping

Builder: Opus 5.5 (high). Assignment: [ASSIGNMENT.txt](ASSIGNMENT.txt). Start commit `3f18ba52` (iteration 63's
integration); product pin `3eaa79cf`, no product file touched. No governing ontology text was changed: the census's
block hashes are unchanged for all 406 blocks, so no block is STALE. Only metadata tags, links and evidence annotations
changed (§5). No Verus, binding or IRIS run was made. The STOP file was checked throughout and never present.

## 1. Result

| | start (`3f18ba52`) | end |
|---|---:|---:|
| obligations | 2097 | 2097 |
| full / partial / absent / unassessed | 966 / 403 / 728 / 0 | **744 / 686 / 667 / 0** |
| full/total as recorded | 46.1% | **35.5%** |
| proved over the full stated scope | 322 | 196 |
| proved incl. narrowed / bounded / refuted / unchecked | 1083 / 0 / 129 / 0 | 1105 / 1 / 145 / 0 |
| strict-grade lint (new) | 759 problems on 661 rows (450 LINT-1, 245 LINT-2a, 39 LINT-2b, 24 LINT-3) | **PASS** |

**Honest whole-foundation figure: 35.5% recorded, about 32% estimated, 95% range about 26–36%.**
- The independent reviewer (§4) agreed with 27 of 30 sampled rows that stay full. That is 90%, with a Wilson 95%
  interval of 74–97%.
- Applied to the 744 full rows, that gives about 670 that hold (32%), with a range of 553–718 (26–34%).
- The reviewer also judged 1 of 10 downgrades wrong, so up to about 23 of the 229 downgrades may be too strict
  (+1 point).
- 35.5% is therefore close to an upper bound. 32% is the central estimate, and it agrees with iteration 63's
  estimate of about 30%.
- The sample is small (30 full rows), so the interval is wide.

## 2. Census output, before and after

Commands (repository root, `PYTHONDONTWRITEBYTECODE=1`): `python3 .g5/Verus_verification/tools/census.py` → exit 0,
PASS including the lint, deterministic (two runs compared). Raw: [gates/census.before.txt](gates/census.before.txt),
[gates/census.txt](gates/census.txt), [summary.md](../../../Verus_verification/census/summary.md). Whole-foundation
line: *full 744, partial 686, absent 667, unassessed 0 of 2097; full/total 35.5%; proved, full scope 196; proved 1105,
bounded 1, refuted 145, unchecked 0; N/A blocks 2.*

Per page (`pr-full` = proved over the full stated scope):

| page | total | full before | full after | partial after | absent after | before | after | pr-full before | after | refuted after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| architecture/adapters | 14 | 10 | 7 | 6 | 1 | 71.4% | 50.0% | 8 | 3 | 1 |
| architecture/adjacency-and-derived-data | 131 | 82 | 68 | 38 | 25 | 62.6% | 51.9% | 18 | 14 | 9 |
| architecture/algorithm-execution | 41 | 9 | 9 | 3 | 29 | 22.0% | 22.0% | 0 | 0 | 2 |
| architecture/query-execution | 70 | 37 | 34 | 24 | 12 | 52.9% | 48.6% | 21 | 7 | 14 |
| architecture/search-storage-and-indexes | 87 | 29 | 21 | 35 | 31 | 33.3% | 24.1% | 16 | 10 | 5 |
| concepts/access | 44 | 12 | 8 | 22 | 14 | 27.3% | 18.2% | 0 | 0 | 6 |
| concepts/graph-scope | 39 | 8 | 9 | 12 | 18 | 20.5% | 23.1% | 2 | 2 | 3 |
| features/algorithms | 137 | 55 | 35 | 44 | 58 | 40.1% | 25.5% | 0 | 0 | 7 |
| features/client-interfaces | 51 | 34 | 27 | 16 | 8 | 66.7% | 52.9% | 20 | 11 | 13 |
| features/cypher | 322 | 135 | 107 | 92 | 123 | 41.9% | 33.2% | 38 | 24 | 29 |
| features/data-interchange | 89 | 59 | 41 | 26 | 22 | 66.3% | 46.1% | 17 | 4 | 4 |
| features/erasure | 47 | 6 | 2 | 19 | 26 | 12.8% | 4.3% | 0 | 0 | 3 |
| features/fhir | 81 | 22 | 18 | 22 | 41 | 27.2% | 22.2% | 13 | 7 | 1 |
| features/graph-structure | 99 | 42 | 29 | 30 | 40 | 42.4% | 29.3% | 8 | 5 | 0 |
| features/ledger | 123 | 73 | 61 | 46 | 16 | 59.3% | 49.6% | 31 | 18 | 3 |
| features/redaction | 111 | 44 | 27 | 39 | 45 | 39.6% | 24.3% | 21 | 14 | 2 |
| features/search | 132 | 72 | 56 | 57 | 19 | 54.5% | 42.4% | 29 | 22 | 13 |
| features/temporal | 169 | 92 | 68 | 59 | 42 | 54.4% | 40.2% | 48 | 30 | 6 |
| operations/ledger | 36 | 22 | 19 | 13 | 4 | 61.1% | 52.8% | 13 | 10 | 2 |
| operations/search-indexes | 16 | 12 | 8 | 7 | 1 | 75.0% | 50.0% | 2 | 1 | 4 |
| operations/setup-and-upgrade | 106 | 26 | 24 | 27 | 55 | 24.5% | 22.6% | 17 | 14 | 9 |
| operations/snapshots-and-bulk-load | 56 | 23 | 16 | 21 | 19 | 41.1% | 28.6% | 0 | 0 | 4 |
| operations/status-and-repair | 96 | 62 | 50 | 28 | 18 | 64.6% | 52.1% | 0 | 0 | 5 |
| **whole foundation** | **2097** | **966** | **744** | **686** | **667** | **46.1%** | **35.5%** | **322** | **196** | **145** |

**Change in scope versus change on retained obligations.** Scope is unchanged: 406 blocks and 2097 obligations, with
no obligation added, withdrawn or renumbered. Every change in §3 is a regrade of a retained obligation.

## 3. What changed (regrade ledger)

[regrade-ledger.tsv](regrade-ledger.tsv) has one row per changed obligation (857 rows). Columns:
- `id` and `tranche` (1 = iterations 61/62, 2 = iteration 63);
- the old and new grade, design check and check scope;
- `statement_changed`;
- `layer`: which fork, integrator, reviewer or owner-tag step changed it;
- `reason`;
- `changes`: a JSON object of every changed column's new value.

[regrade-tools/replay.py](regrade-tools/replay.py) applies the ledger to the start commit's obligations.tsv and
reproduces the committed census exactly ([gates/replay.txt](gates/replay.txt): REPLAY OK).

| change | tranche 1 | tranche 2 | total |
|---|---:|---:|---:|
| full → partial | 55 | 174 | **229** |
| full → absent | 0 | 0 | **0** |
| absent → partial | 23 | 31 | **54** |
| absent → full | 3 | 4 | **7** |
| check_scope full → narrowed (incl. rows that went partial) | | | **161** (+1 full → n/a) |
| statements fixed (checklist f) | | | **17** |
| design check none → proved / refuted / bounded | | | 34 / 10 / 1 |
| design check proved → refuted / none; refuted → proved | | | 7 / 6; 1 |
| full held, cells only (gap tagged, `requires-reviewed:` note, locator added) | 147 | 385 | 532 |

Full grades held: tranche 1, 191 of 246 (78%); tranche 2, 546 of 720 (76%).

What the downgrades show:
- They follow iteration 63's patterns, and checklist items **a** (a definition or spec fn only) and **b** (one
  entry point or case of several) are the most common. **d** (a decision supplied as an input) and **c** (a proxy
  observation) follow.
- **e** (narrowing `requires`) mostly moved scope rather than grade.

Examples:
- `adapters.embedded#o02`: `Verb::Txn` is an input.
- `install.status.readiness#o13`: `route_rows > 0` is a proxy.
- `algorithms.op.subgraph#o07`: the Arno reader that answers first is not modelled.
- `install.export.rdf.content#o01`: triple shapes exist only in `emit_*` definitions.
- `query.system-procedures.results#o01`–`#o08`: only the db.labels branch is modelled.

**Absent → full (7), each a missed model found by behaviour.** Each is listed with its locator:

| id | locator | check |
|---|---|---|
| graph.all_graphs_read#o03 | proofs-d1d `cx_f0818.rs::counterexample_f0818` (control f0818) | refuted, narrowed |
| erasure.live-statements#o01, erasure.entry-points.single-path#o01 | proofs-d1c `cx_f0303.rs::counterexample_f0303` (control f0303) | refuted, narrowed |
| search.bm25.write_lock#o05 | proofs-d1d `bmw_l1`/`bmw_l2` + `cx_fc0702.rs::counterexample_fc0702` (control fc0702); native `search_bm25_caller_txn_rollback` | refuted, narrowed |
| search.erasure#o04 | search.rs `witness_erase_leaves_bm25` | refuted, narrowed |
| temporal.write.repeatable#o03 | temporal_marker.rs `theorem_first_temporal_weight_wins`, `theorem_marker_decodes` | proved, narrowed |
| install.legacy#o04 | proofs-d1e `cx_f0101.rs::counterexample_f0101` (control f0101) | refuted, narrowed |

The 54 absent → partial upgrades are listed with their locators in the ledger and the fork reports. Their main
sources are:
- proofs-d1f `auth_l1`/`auth_l2` (access.*), reviewed design with a baseline receipt only, so partial at most;
- d9b, d1d, d1e and d1b definitions;
- node_read, traversal_strategy, retrieval_compose, vector_admission, install_lifecycle, rebuild_reads, sql_procs,
  ledger_content/alternate.rs, write_routing and adjacency_maint;
- two Rust explorers (lockplans `nkg_intern.rs`, breadth-a `adj_rebuild_txn.rs`).

Each of the 728 start-absent rows has a `held absent: <what was searched>` or upgrade reason in its fork's rows file
([fork-rows/](fork-rows/)).

**Process.**
- Twelve forks of this session regraded every full and absent row under one brief:
  [fork-reports/BRIEF.md](fork-reports/BRIEF.md) restates checklist a–g and the lint.
- Each fork worked in scratch and passed `overlay.py` (the census plus the lint on its rows) before returning. Reports
  are in [fork-reports/](fork-reports/) and rows in [fork-rows/](fork-rows/).
- [regrade-tools/merge.py](regrade-tools/merge.py) applies the layers in order: forks, then the integrator's rows,
  then the reviewer corrections, then the owner-contradicted tags.
- Mid-run, three forks found real defects in the scratch tools and the lint parser. All were fixed before the merge,
  and the five affected forks re-checked checklist f on the affected rows (§8):
  - one-line Rust bodies;
  - `//` inside string literals;
  - `show.py` reading redirect stubs before canonical blocks.

## 4. Independent review sample

- **Reviewer:** a fresh general-purpose agent, not a fork. It had the README rules and the same checklist, but no
  grades, checks, scopes, gaps or reasons. It was told not to open the census TSVs or iteration-63/64 material.
- **Sample:** 50 rows, deterministic and stratified ([review/sample.tsv](review/sample.tsv);
  [regrade-tools/sample.py](regrade-tools/sample.py) ranks each stratum by `sha256("it64-review:"+id)`). The blind
  packet ([review/blind.md](review/blind.md)) interleaves the strata.
- **Verdicts and corrections:** [review/verdicts.tsv](review/verdicts.tsv);
  [review/corrections.tsv](review/corrections.tsv).

| stratum | rows | grade agreement | reviewer disagreement |
|---|---:|---:|---|
| T1-full (tranche 1, full after, empty start gap) | 10 | 8 | redaction.metadata#o01 → partial (c, proxy for the four cleared fields); redaction.call#o05 → partial (a/d) |
| T2-full (tranche 2, same) | 10 | 9 | search.fusion.python#o01 → partial (point check before the fused order) |
| GAP-full (held full, had a gap at start) | 10 | 10 | scope only: temporal.labelset#o02, caller-transaction#o11 → narrowed; aggregation.keys#o04, knn.threshold#o01 → full |
| DOWN (full → partial/absent) | 10 | 9 | query.system-procedures.results#o07 → full (narrowed) |
| UP (absent → partial/full) | 5 | 5 | — |
| ABS (absent held) | 5 | 3 | install.legacy#o03, access.api_key.every_route#o03 → partial (missed reviewed-design models) |
| **total** | **50** | **44 (88%; Wilson 76–94%)** | |

**Accepted (8, applied):**
- 3 full → partial: redaction.metadata#o01, redaction.call#o05, search.fusion.python#o01.
- 2 absent → partial: install.legacy#o03 (`proofs-d1e inst_l1.rs::removed1`), access.api_key.every_route#o03
  (`proofs-d1f auth_l1.rs::decide`, public path is an input).
- 3 scope full → narrowed: temporal.labelset#o02, ledger.commit.caller-transaction#o11, temporal.edge.clock#o11.

**Rejected (5):**
- results#o07 → full: the block's rules cover every handled metadata call, and only db.labels is modelled
  (one entry point of several).
- query.aql#o05 → full scope: point checks; LINT-2b.
- search.knn.threshold#o01 and query.aggregation.keys#o04 → full scope: the rows carry a provider or
  inspected-transcription premise.
- algorithms.op#o08 "bounded": a Verus point proof is recorded as proved, narrowed, not bounded.

No statement needed a fix, in the reviewer's reading. Its least-sure rows are listed at the end of its verdict
reasons, for the next sample: query.native.privileges#o01, redaction.after-erasure.default-graph#o02,
query.values.ordering#o03, redaction.metadata.exception#o03.

## 5. Lint and evidence-side housekeeping

**Lint** (`tools/census.py`, function `lint`; documented in
[census/README.md](../../../Verus_verification/census/README.md) "Strict-grade lint").
- It runs by default. `--no-lint` reproduces the pre-iteration-64 output byte for byte.
- Rules:
  - **LINT-1:** a full row with an untagged gap. Allowed segments are `outside-statement:` and
    `owner-contradicted:`.
  - **LINT-2a:** check_scope full over a cited `requires` without a `requires-reviewed:` note.
  - **LINT-2b:** check_scope full on point checks only.
  - **LINT-3:** full without a cited `proof fn`.
- It parses `proof fn` headers in the cited .rs files: comments are stripped, string literals kept, and the body is
  taken as the last depth-0 brace group before the next item.
- Cross-checked over all 5158 proof fns in models and playbook crates: 2754 have requires, and no header spills into
  a body.
- On the start census it reports 759 problems on 661 rows
  ([gates/lint-on-start-census.txt](gates/lint-on-start-census.txt)). At the end it passes, with:
  - 101 full rows carrying `outside-statement:` gaps;
  - 144 rows carrying `requires-reviewed:` notes;
  - 48 rows carrying `owner-contradicted:` segments.

**Housekeeping (iteration-63 §6.2–§6.4; no owner wording changed):**

- **coverage.md** ([regrade-tools/coverage_fix.py](regrade-tools/coverage_fix.py), replayable from the start file).
  - A census-precedence note was added.
  - Three receipt names were corrected where the latest receipt has the same counts: platform `20261116T160814Z`
    (twice), search `20261116T160846Z` and ledger_redaction `20261116T160746Z`.
  - 26 rows carry an inline **Stale (iteration 64):** note naming the census rows that now hold the grade. They cover
    every §6.2 row: search other_model, queue, the gap list and controls; nodes/edges CRUD; cache.concurrency;
    "Proved (given the bump)"; undeclared; degree.cache.erase; temporal.structural/adopt/end; ts=0; the window
    reader; not_ready; existing; query.writes.ledger; the install gaps; query.writes.atomic; "FHIR: no model";
    "Algorithms: not modelled"; weighted Open; the acache reviewed row; M18; and the "no active formal link"
    paragraph.
  - Model rows were added for cypher_fns and cypher_exprs.
- **NOTES.**
  - 43 old-location owner links in 25 NOTES were repointed to the canonical pages
    ([notes-links-repointed.tsv](notes-links-repointed.tsv)).
  - A "Latest receipts (checked in iteration 64)" section was appended to cypher_exprs, clause_combos,
    cypher_clauses, result_decoders, sort_key, temporal_stats, adjacency_maint and ledger_redaction.
  - aggregate_results/NOTES.md is a recorded input of its receipts. Editing it would stale them, so its stale name
    is documented here and not edited.
  - native_admission/NOTES.md now documents the undeclared receipt `20261118T015505Z-control-read-step-keeps-write`
    as history: its theorem no longer exists. The receipt was not deleted.
  - retrieval_compose's withdrawn `guided-cap-max-nodes` receipts were already documented in its NOTES (lines 39–40).
    The control was not declared in model.json, because model.json is a recorded receipt input.
- **install_lifecycle/manifest.json** was added in the shape of the other 102 manifests: `ontology_ids` from its NOTES
  owner list, and runs from model.json.
- **Crosswalk.** Two rows were changed from `models` to `cites`, with a "Locator only (iteration 64)" note:
  - `remove_table_mapping → theorem_writer_reads_current` (`mapped` is an input);
  - structure.multigraph.count → `theorem_appending_row_counts_physical_multiplicity` (it counts scan rows, not
    degree or one-hop rows).

  decision-links.tsv is a correspondence-gate input. A new stamp,
  [correspondence-inputs.json](correspondence-inputs.json), was captured after checking that it differs from
  iteration 62's only in that file. It checks REUSABLE_INPUTS.
- **Ontology metadata** (not governing text):
  - query.optional now cites `theorem_null_row_counts`; the non-existent `_count_zero` name is gone (§6.1 #32).
  - query.with's C5 claim was corrected to "observed only, not modeled" (#31).
  - query.values.equality's "Parameters … were not checked" was annotated as superseded (#33).
  - query.writes' Children line no longer picks up structure.node.delete through a nested link (#34).
  - install.status's `Children:` became a `- Children:` bullet, so the census sees its 7 children (#35). blocks.tsv
    `children` was updated for both blocks.
- **`design-verified` tags** ([design-verified-tags.tsv](design-verified-tags.tsv),
  [regrade-tools/tags.py](regrade-tools/tags.py)).
  - Rule applied: a block keeps the tag only when the census grades every obligation full and none is an as-built
    refutation. This follows ontology-format.md: "a model association … does not by itself establish complete
    verification".
  - 7 blocks keep it: algorithms.cache.pagerank, algorithms.op.wcc, install.export.ndjson,
    fhir.graph.lifecycle.tasks, temporal.edge.clock, temporal.write.retry and access.health.lifecycle.
  - 103 lose it. No other verification tag replaces it, and their Verus / State machines links stay.
  - **This is a judgement the master may reverse.** The harness's TLC `link_verification.py` assigns the tag on any
    linked model with a recorded run. The TSV lists every block, so restoring is mechanical.
- **Census.** query.native.sql-first#x02 now names query.values#o01 as the SQL-side owner.
- **Erasure alignment (§6.4).**
  - erasure.kept#o03 and #o05 went absent → partial on the same basis as fhir.erase#o01 (`proofs-d1f
    fhir_l2.rs::erased`, definition only).
  - erasure.atomic#o01 now cites `temporal.rs::witness_rolled_back_delete_undercounts` and native
    `temporal_rollback_counters.json` R6. It stays partial, with check refuted, narrowed, for the temporal-counter
    part.
  - erasure.atomic#o04 (G10: partial via d9b `witness_erasure_rollback`) carries the same refutation note.
  - erasure.entry-points.single-path#o01 is full, refuted (§3).
- **Owner contradictions (§6.1 items 1–29).** The 34 obligation rows in [owner-contradicted.tsv](owner-contradicted.tsv)
  carry an `owner-contradicted: <evidence> (iteration-63 §6.1 item N)` gap segment. Forks added 14 more from their own
  reading, 48 in all.
  - Item 30 (access.defaults) was **not** tagged: the statements are scoped to `ivg server start` and Bolt, and the
    evidence confirms them there. The sample `api/main.py` is outside them.
  - Items 31–35 were metadata and are fixed above.
  - No owner statement was reworded.

## 6. Gates (raw in [gates/](gates/); `*.before.txt` at the start commit)

| gate | start | end |
|---|---|---|
| `tools/census.py` (incl. lint) | exit 0 without lint; lint would report 759 | **exit 0, PASS, lint PASS**, deterministic |
| `tools/census.py --no-lint` | — | exit 0, PASS |
| `tools/check_evidence.py` | FRESH | **FRESH** |
| `tools/check_consolidated.py` (`G5_GUIDE=$G5_HARNESS/guidance`) | PASS | **PASS** (correspondence gate REUSABLE_INPUTS against the iteration-64 stamp) |
| `guidance/scripts/check_ontology.py .g5/ontology` | 0 issues, 17 warnings, 406 blocks | 0 issues, 17 warnings, 406 blocks |
| `guidance/scripts/check_findings.py` | No problems found | No problems found |
| `regrade-tools/replay.py` | — | REPLAY OK |

## 7. Limitations and remaining uncertainty

- **The grades are still one session's judgement.** Twelve forks of this builder regraded under one brief, and one
  independent reviewer checked 50 rows. Fork strictness varied: some downgraded definition-only halves that others
  held, and each fork lists these in its §4. The interval in §1 comes from 30 sampled full rows.
- **The lint checks form, not truth.** It forces each `outside-statement:` or `requires-reviewed:` claim to be
  stated, but cannot check it. 101 and 144 such notes rest on fork judgement; the reviewer sampled 10 GAP-full rows,
  all of which held.
- **Absent searches** were by behaviour across models, NOTES, manifests, coverage.md, the crosswalk and the playbook
  crates. The reviewer still found 2 of 5 sampled absent rows to be partial, through reviewed-design crates, so about
  30–40% of the 667 absent rows may have a partial-level model somewhere. That would lift partial, not full.
- **Reviewed-design crate convention** (unchanged from iteration 63): a d1c, d1d or d1e counterexample counts as a
  refutation only with a fresh control receipt. Several new full refutations rest on it, and none is reproduced live
  except where a native receipt is cited.
- **The tag rule (§5) is strict and reversible.**
- **Statements:** 17 were fixed. Five forks first read redirect stubs for 207 rows and rechecked them after the tool
  fix: G04 and G12 had no change, G05 had 2 statements restored (both now partial), G07 5 and G09 2.

## 8. Remaining work (master's call)

- **Next review sample:** a larger independent re-grade of held-full rows to narrow the 26–36% interval, stratified
  by page (algorithms, cypher, data-interchange and temporal hold the most full rows). Include the reviewer's
  least-sure rows (§4).
- **Owner repairs:** area batches should separate the 48 `owner-contradicted:` rows into intended policy, as-built
  defect or wrong statement.
- **Uncited models the forks found:**
  - proofs-d1d `cx_f0802`/`cx_f0816` → query.graph-scope#o01 (partial); `cx_f0818` → query.graph-scope.read#o03;
  - `witness_ledger_delete_rel_drops_survivors_non_indexed`;
  - ledger_content `alternate.rs` is not linked from the genesis metadata.
- **Model notes:**
  - ivf_entries `search_answers` is constant `true`, so `theorem_other_width_answered` is vacuous.
  - ledger_client `enable` ignores `redacting`.
  - search NOTES still cite the W-O3a/b queue witnesses that embed_queue's binding contradicts.
  - cypher_fns NOTES "Limits" lists percentiles as observed only.
  - query.native.gates metadata says `idx_cache` is unmodelled.
  - algorithms.routing may omit BFS's Arno route.
- **Possible owner issues** noted but not tagged: redaction.batches#o02 (bug-led-006), query.native.privileges' lead
  versus its working assumption, and query.native.reads-only bullet 1's example.
- **Modelling targets** are unchanged from iteration 63 §8: erasure across stores (now 4.3%), security surfaces,
  native-reader routing and migrations.

Files changed:
- census: obligations.tsv, blocks.tsv (2 children cells), excluded.tsv (1 reason), summary.md, README.md;
- `tools/census.py` (the lint);
- coverage.md, decision-links.tsv (2 rows), 33 model NOTES and install_lifecycle/manifest.json;
- 22 ontology pages, metadata only (tags, links and annotations);
- this directory.
