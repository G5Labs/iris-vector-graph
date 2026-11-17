# Iteration 53: repairs from independent review round 2, then the remaining SQL procedure surface

Before image `8d8d9ae4` (seal 52 `fdcceada` plus the master's inventory commit). Product `3eaa79cf` unchanged:
nothing outside `.g5/` changed (`git diff 8d8d9ae4 -- . ':!.g5'` empty; `check_consolidated.py` confinement PASS).
Commits:
- `99e90a08`: Part A checkpoint;
- `ff7d3528` and `5f4d435f`: the Part B freezes, each committing only its PAIRS file before any deciding body was read;
- the seal.

Guidance: `$G5_HARNESS/AGENTS.md`, `uplift-review.md`, `Verus/{uplift, uplift-iteration, uplift-scoring,
setup_foundation, verification}.md`, `ontology-format.md` and `setup_foundation.md`, read at the start.
`open_questions.md` is unchanged in this iteration: no card, anchor or saved answer touched.

Quarantine respected: no iteration-13 Cypher `MERGE` material and no evaluator-private ledger was opened.

Native evidence comes only from `ivg-cont-20261117-iris`:
- USER with fresh prefixes `i53t_` and `i53s_`;
- fresh namespaces created from `%SYS`: `I53` (probe) and `I53B` (binding) for operator reports, `I53P` (probe) and
  `I53Q` (binding) for SQL procedures.

`I52` and `I52B` were not touched. Every IRIS user and role created (`i53_*`, `i53_b*`, `i53p_*`, `i53q_*`) was
dropped, and the drops were confirmed.

Work split: four workers with disjoint files (temporal; operator reports; graph SQL procedures; BM25 and percentiles)
plus the builder (the Cypher rows, integration, checks, registers, handoff). Each worker's receipts were re-read by
the builder before integration. Two workers each made one whole-file write to `bugs_issues.md` to satisfy
`check_findings` ordering. The registers were audited afterwards: every iteration-53 entry is present once in
`bugs_issues.md` and once in `findings.tsv`, and the file has only insertions since the checkpoint.

## Part A: review 50-52 (round 2 of this run)

Review: [REVIEW-50-52.md](REVIEW-50-52.md), copied verbatim with a header naming session `d548b72a` and commit
`8d8d9ae4`; its probes are in [review-probes/](review-probes/). Every item has a row in
[DISPOSITIONS.md](DISPOSITIONS.md).

**Summary:**
- M1, M2 and M3 were accepted and reproduced, each with a new finding: bug-tmp-105 (Medium), bug-plt-119 (Medium),
  bug-plt-120 (Low).
- m1 was accepted with a new finding, bug-tmp-106 (Low).
- m7 is bug-plt-115's edge trigger, reproduced; it has no new ID.
- m2 is owned as built and not registered: no document promises an empty-key wildcard.
- m3, m4, m5, m6, m9 and m10 were accepted.
- m8 is partly done: two cheap cases are probed and owned; the rest are residuals with first steps.

The three sign-off conditions:
- M1 is recorded at the owner, the register and the binding;
- M2 and M3 are owned with probes, and both are also modeled and bound;
- m4 is relabeled.

## Part B: remaining SQL procedure surface

### Predictions: 44 frozen rows; 35 held, 6 partial, 3 missed, 0 not run

| Workflow (PAIRS) | Held | Partial | Missed |
|---|---|---|---|
| [SQL procedures](sqlprocs-PAIRS.md): `MatchEdges`/`MatchEdgesAllGraphs` (ME), `DijkstraPath` (DJ), `backfill_temporal_rows` (BF), `rebuild_edge_indices` (RB) | ME1-ME3, DJ1-DJ5, DJ7-DJ10, BF3-BF5, RB1-RB4 (19) | ME4 (same targets, but `r.weight` reads null on the scan plan: **bug-cyp-133**); BF1 (row recreated and marked, but the answer is triples walked, not rows written: **bug-tmp-107**); BF2 (writes nothing on a re-run but answers 3 again) | ME5 (`shard` is never read: shards 1 and 7 answer every edge); DJ6 (the SQL entry also refuses a bad direction or weight property: the checks sit in `DijkstraJson`, not only in Python) |
| [BM25 and percentiles](bm25-percentile-PAIRS.md) | B1a-B1i, B2a, B3a, P1a, P1c-P1f (16) | B2b (agreement held; the probe's history differed from the frozen numbers, and the port for the actual history agrees); B3b (`kg_BM25` score is a `Decimal`); P1g (Disc over integers answers 2.0 in Cypher, 2 from SQL) | P1b (`percentileDisc` takes floor((n−1)·p), not the nearest rank: p 0.6 gives 20 and p 0.9 gives 30 over 10..40; **bug-cyp-134**) |

Counts are taken from the rows in the two PAIRS files (24 and 20); the BM25 worker's own report said 26 rows with 21
held and 4 partial, which does not match its file and is not used.

Found after the freeze, not predicted:
- `DijkstraPath('', '')` answers a zero-length path through `$Char(0)` (**bug-str-112**);
- p = 1/3 over four values answers 10 (the double's value times 3 is just below 1);
- `UNWIND $xs` with a list parameter fails (inherited bug-cyp-125);
- `bm25_search` rewrites `c:.5x` as `c:0.5x` while the Cypher procedure keeps the id (inherited F-C0715, now formal).

### Models

| Model | Verified | Controls | Binding |
|---|---|---|---|
| `sql_procs` (new) | 16 | 12/12 EXPECTED_FAIL | AGREES 224 in re-created `I53Q`; 12/12 mutations and tamper detected |
| `bm25_scoring` (new) | 32 | 9/9 | AGREES 46, relative tolerance 1e-12; all mutations and tamper detected |
| `percentile` (new) | 26 | 4/4 | AGREES 156, tolerance 1e-9; all mutations and tamper detected |

`sql_procs` covers the SQL entries in front of the existing search models:
- `MatchEdges` and `MatchEdgesAllGraphs`: the graph/all-graphs scan, the predicate and source filters, the unused
  shard, and the privilege check (`SqlPrivilege.RequireSelect`/`RequireWrite`);
- `DijkstraPath` → `Traversal.DijkstraProc` (a justified delegate) → `TraversalPaths.DijkstraJson`. The search itself
  stays `weighted_paths`' claim; this model adds the entry checks and the NUL path.
- the backfill (`BackfillStructuralRows`/`BackfillWalk`: what it writes, skips, and counts);
- the rebuild (`Ledger.RebuildEdgeIndices`).

`bm25_scoring` gives the owner formula over the stored counts (the counts are proved in `bm25_counts`), with:
- tokenizer and stopwords;
- query term repeats;
- query-time IDF;
- the df cutoff and its fallback;
- tie order;
- `kg_BM25` against `bm25_search`.

Its controls include `unknown-terms-scored`. That control first SURVIVED (its theorems were vacuous under the change);
it was rephrased on df and the receipt is kept.

`percentile` gives the floor-index Disc and the interpolating Cont over integer lists, with exact rationals and the
double p.

## Findings (new vs inherited)

| ID | Severity | Trigger → observable | Found by / reproduced by |
|---|---|---|---|
| [bug-tmp-105](../../../Verus_verification/bugs_issues.md#bug-tmp-105) | Medium | nested label-set value → new hash and entry per call; different nested values share a hash | review M1 / iteration-53 probe and binding |
| [bug-plt-119](../../../Verus_verification/bugs_issues.md#bug-plt-119) | Medium | failed status count → `/metrics` and `/server` 0, readiness False; only the text report says unknown | review M2 (source) / probe in `I53`, binding s19 |
| [bug-cyp-134](../../../Verus_verification/bugs_issues.md#bug-cyp-134) | Medium | `percentileDisc` at p between ranks → the lower value (p95 over 1..10 answers 9) | frozen prediction P1b missed / probe and binding |
| [bug-tmp-106](../../../Verus_verification/bugs_issues.md#bug-tmp-106) | Low | ms-class edge → counted by the seconds whole-bucket readers | review m1 / probe and binding |
| [bug-plt-120](../../../Verus_verification/bugs_issues.md#bug-plt-120) | Low | failed `ledger_stats` read → "0 commits · 0 rejections", no error | review M3 (source) / probe and binding |
| [bug-cyp-133](../../../Verus_verification/bugs_issues.md#bug-cyp-133) | Low | `IVG_EDGESCAN=1` → every relationship property reads null on the scan plan | prediction ME4 partial / probe and binding |
| [bug-tmp-107](../../../Verus_verification/bugs_issues.md#bug-tmp-107) | Low | `backfill_temporal_rows()` → answers triples walked, not rows written | BF1/BF2 partial / probe and binding |
| [bug-str-112](../../../Verus_verification/bugs_issues.md#bug-str-112) | Low | SQL `DijkstraPath('', '')` → a zero-length path through `$Char(0)` | after the source read / probe and binding |

- **Found by the review (5):** bug-tmp-105, bug-plt-119, bug-tmp-106, bug-plt-120, and the m7 trigger of bug-plt-115.
- **Found by Part B (4):** bug-cyp-133, bug-cyp-134, bug-tmp-107, bug-str-112.
- **Strengthened:**
  - bug-plt-115: edge trigger reproduced, doc conflict stated (m3);
  - F-C0715: now formal.
- **Reproduced again:** bug-cyp-125.
- Simplifications and questions: none opened, tested or resolved.

## Owners changed

- `temporal.g5.md`:
  - `temporal.labelset`: opening sentence corrected; nested-value and non-JSON bullets;
  - `temporal.stats.window`: empty keys; ms edge;
  - `.distinct`: empty predicate;
  - `.velocity`: ms window unit;
  - `temporal.structural.upgrade`: the SQL entry and privilege check, existing rows left alone, bug-tmp-107.
- `install.g5.md`:
  - `install.status`: bug-plt-119 bullet;
  - `.readiness`: failed probe reads False; `ready_for_edge_search`; the `kg_predicates_consistent` conjunct and
    premises; the FR-006 vs ADMIN_GUIDE conflict;
  - `.readers`: "unchanged" replaced per reader; empty BM25 index `ONLINE`; `ivg status` exit 0;
  - new block `install.status.ledger`.
- `cypher.g5.md`:
  - `query.functions.list_index`: null row index vs null parameter index (m6);
  - `query.functions.percentile`: floor rounding and float answers as "Today" bullets. The iteration-47 note
    "rounding follows Neo4j" is corrected: the median and quartiles it was checked on agree under both rules.
- `graph-structure.g5.md`: new block `structure.adjacency.scan`; `structure.rebuild` bullets.
- `algorithms.g5.md`: `algorithms.op.paths.weighted` SQL-entry and bug-str-112 bullets.
- `search.g5.md`: `search.bm25.scoring` tie order, and Formal links on `.scoring`, `.query_time_idf` and `.cutoff`.

IDs and anchors are preserved. `check_ontology.py`: 391 blocks, 0 issues, 17 writing warnings (unchanged count).
Expected results come from docs, docstrings, spec 230 FR-006, ADMIN_GUIDE R050 and the owner text. None comes from
a repair the builder prefers.

## Models touched in Part A

| Model | Verified | Controls | Binding |
|---|---|---|---|
| `temporal_stats` | 51 → 58 ([prove](../../../Verus_verification/results/temporal_stats/20261117T044949Z-prove/receipt.json)) | 16 → 18 | 139 → 148 ([receipt](../../../Verus_verification/results/temporal_stats/20261117T045124Z-binding/receipt.json)) |
| `operator_reports` | 34 → 48 ([prove](../../../Verus_verification/results/operator_reports/20261117T045706Z-prove/receipt.json)) | 17 → 24 | 414 → 535, namespace `I53B` ([receipt](../../../Verus_verification/results/operator_reports/20261117T045659Z-binding/receipt.json)) |
| `cypher_exprs` | 22 (re-run, file unchanged) | 22 (re-run) | 233 → 236 (lexer tokens; [receipt](../../../Verus_verification/results/cypher_exprs/20261117T044717Z-binding/receipt.json)) |

Trust: no `assume`, `admit` or `external_body` in any touched or new model; vstd only.

New named premises:
- P-SHA1 (SHA-1 injective on the canonical texts);
- P-INDEX and P-SEEN (`sql_procs`);
- P-LN, the IRIS analyzer as a plain punctuation splitter on the corpus used, and 12-decimal ranking keys
  (`bm25_scoring`).

The existing operator premises are now named in the owner (m10).

Kept failed or superseded runs:
- `operator_reports` control `20261117T045439Z-control-edge-registry-keeps-case` FAIL_ELSEWHERE: the failure was in
  `lemma_erouted_sum_zero`; the control now names it.
- `bm25_scoring` control `051339Z` SURVIVED, `051402Z` FAIL_ELSEWHERE, prove `051422Z` failed. All are earlier
  phrasings.
- `percentile` binding `051656Z` DISAGREES on four p = 1/3 cases: the port used the exact 1/3, the product a double.
- `temporal_stats` binding `045049Z` (146 cases) was superseded before the m9 cases were added.
- The temporal probe's first run is under `temporal/failed-runs/`.

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings **563 → 603**; union reach (master rule: active plus baseline historical locators) **799 → 833**.
- **Additions:** 40 newly bound members.
  - Part A: 6 (`GraphLedger.stats`, `.commit`, `.enable`, `_ledger_status`, `EngineStatus.ready_for_edge_search`,
    `store_edge_embeddings`).
  - Part B: 34. In `SqlProcs.cls`: `MatchEdges`, `MatchEdgesAllGraphs`, `DijkstraPath`, `backfilltemporalrows`,
    `rebuildedgeindices`, `kgBM25`, `PercentilePDISC`, `PercentilePCONT`. Elsewhere: 3 in `EdgeScan`, 8 in
    `BM25Index`, 3 in `IVG.Percentile`, `Traversal.DijkstraProc`, 2 in `SqlPrivilege`, 2 backfill members,
    `Ledger.RebuildEdgeIndices`, 2 in `vector.py`, 4 in the translator.
  - Overlap with earlier locators: 6 (4 `BM25Index` members, `GraphLedger.commit`, `.enable`). So 34 were newly
    reached and 40 distinct members were added.
- **Strengthened:** 14 already-bound members gained a claim; the member delta lists each with its reason.
- **Relabeled:** `_create_resolve_prop_value` is now a delegate (m4). It is still active, with a narrower role.
- **Lost:** 0.

**Material predictions:**
- **Gained:**
  - nested label sets hash per call;
  - a failed status count reads as 0 or False on the HTTP readers and flags;
  - the ledger line hides a failed read;
  - routed edge vectors read not ready;
  - ms edges sit in seconds buckets;
  - the scan plan loses relationship properties;
  - backfill counts walked triples;
  - `DijkstraPath('', '')` answers;
  - `percentileDisc` rounds down;
  - `MatchEdges` ignores `shard`;
  - the SQL Dijkstra entry refuses bad direction and weight;
  - BM25 scores, tie order and the cutoff fallback match the owner formula on the product.
- **Withdrawn:** the iteration-47 owner note that `percentileDisc` "follows Neo4j's rounding" (true only at the
  median and quartiles checked).

## Correspondence

The [delta from 52](correspondence-delta-from-52.json) is STALE_ALL for proof and for correspondence. The changed
inputs are model, binding, crosswalk and families files only; no product file changed. The fresh
[stamp](correspondence-inputs.json) checks as REUSABLE_INPUTS.

## Checks (final candidate)

| Check | Result |
|---|---|
| `check_ontology.py` | 0 issues, 17 warnings (unchanged) |
| `check_findings.py` (`verification_root=.g5/Verus_verification`, `--previous 8d8d9ae4`) | No problems found |
| `check_evidence.py` | FRESH |
| `check_consolidated.py` (G5_GUIDE set) | PASS (898 links resolve; statements 391 rows) |
| Product diff vs pin | none outside `.g5/` |
| `link_verification.py` | not applicable (no TLA models) |

Every touched or new model was proved, ran its full control suite and was bound on the final files, as listed above.

## Limitations

- **Review:** these repairs and the Part B models have not been independently reviewed. This was round 2's repair;
  a round-3 review should start from the new models.
- **Unmodeled:** m2 (empty keys), non-JSON intern input, the ms class's own readers over seconds edges, `ivg status`
  exit codes, `SHOW INDEXES` states.
- **Premises:** `KGEdgeCount`'s cap, `kg_predicates_consistent`, Arno (absent), the backfill seen limit (P-SEEN), the
  IRIS analyzer beyond the corpus used.
- **Numerics:** BM25 scores are bound natively with a stated tolerance; Verus proves structure and ordering over
  integers/rationals, and ln is a premise.
- **Repair proposals:** none was run on the product. Controls check the model's direction only.
- **Fixture state:** `I53`, `I53B`, `I53P` and `I53Q` remain in the dedicated container.

## Residual list (first missing step for each)

- **m2:** add a `""` key branch to `get_aggregate`/`distinct` in `temporal_stats`, plus binding cases.
- **m8:**
  - a user without `%Native_ClassExecution` calls `GET /indexes` (the source predicts a 500);
  - `SHOW INDEXES` during a BM25 build;
  - `snapshot_info` on a damaged archive;
  - `verify_sync(heal=True)` after an indeterminate count;
  - a heal whose `sync()` fails partway (`schema.py:2893`).
- **m10:** a namespace with an inconsistent predicate entry, then read `ready_for_multihop_bfs`.
- **SQL procedures:**
  - a keyed multigraph through the scan;
  - `rebuild_edge_indices` over a `^KG` entry with no row behind it;
  - a graph past the 100,000 seen limit;
  - setup's own `temporal_rows_backfilled` with temporal rows and the index dropped.
- **BM25:**
  - analyzer edge cases (`don't`, `3.14`);
  - a schema-1 search with stored IDF, then `bm25_upgrade`;
  - the skipped-term order (q-srch-005);
  - the `kg_BM25` privilege refusal.
- **Percentiles:** non-numeric values; list-parameter percentiles (blocked by bug-cyp-125 until driver 5.4.x is
  checked).
- **Also carried:** the iteration-52 residual list (multigraph bug-plt-116, the refused-namespace path with F-1713,
  `/indexes` in Verus) and the consolidated queue.

## Cost

About 41 minutes of builder wall clock (04:44 to 05:25 UTC, the seal); the four workers ran in two parallel pairs. Worker tokens: about 1.37 million in total for the
four workers (254k temporal, 323k operator reports, 402k SQL procedures, 388k BM25 and percentiles). The builder's
own tokens and the currency cost are not available to the builder.
