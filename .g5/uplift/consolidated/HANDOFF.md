**Current pointer (cloud continuation, 2026-11-16).** Iteration: 21 sealed, 22 in progress (BM25 text search). Latest seal: the clean tip with subject `Seal iteration 21: variable-length multiplicity and adjacency rebuild` — [iteration 21 handoff](iteration-21/HANDOFF.md): both workflows agree with openCypher/owners; reach 273 of 4,130. This session: 14–20 sealed with five new findings (bug-tmp-101, bug-cyp-102…105) and reach 249 → 273. Cost: builder wall clock only (tokens/currency unavailable). Next missing role: BM25 index writers and scoring reader (owners detailed, no model or binding). Convergence: not established.

Older pointer, superseded: [iteration 11](iteration-11/HANDOFF.md), continuing into iteration 12.

# IVG consolidated uplift — handoff

**Historical continuation: iteration 3 (2026-11-15)** — [sealed handoff](iteration-3/HANDOFF.md), [retained sample and challenges](iteration-3/PAIRS.md), [coverage](../../Verus_verification/coverage.md#improvement-iteration-3-2026-11-15). Input `0af2a61d`; implementation checkpoint `6f32b507`; final seal is the clean tip with subject `Seal iteration 3 with corrected snapshot evidence and handoff`. Four new as-built families: **33 obligations / 19 named controls**, **164 upstream tests passed**, consolidated gate PASS. Corrects the inherited empty-deletion-prior inference while retaining a stronger range-prior witness. Named diff, global PageRank admission/self-loop producer, AQL frontend and vector threshold/results gain scoped contracts; full lifecycle/content and live IRIS correspondence remain open. This supersedes conflicting scope/count claims below without removing historical evidence.

**Prior continuation: iteration 2 (2026-11-15)** — [sealed handoff](iteration-2/HANDOFF.md), [controlled predictions and retained sample](iteration-2/PAIRS.md), [coverage](../../Verus_verification/coverage.md#improvement-iteration-2-2026-11-15). Input `d087503`; implementation checkpoint `c64c6dda`; final seal is the clean tip with subject `Seal iteration 2 with controlled predictions and review handoff`. Four new as-built families: **41 obligations / 22 named controls**, Python unit bindings with explicit provider limits, **314 upstream tests passed**, consolidated gate PASS. The new application model addresses M03's selected producer/failure boundary; full history/diff/restore and live ObjectScript correspondence remain open. This current handoff supersedes older scope/count claims below; all historical evidence is retained.

**Prior continuation: iteration 1 (2026-11-15)** — [sealed iteration handoff](iteration-1/HANDOFF.md), [controlled pairs](iteration-1/PAIRS.md), [current coverage](../../Verus_verification/coverage.md#improvement-iteration-1-2026-11-15). The clean `consolidated_uplift` tip with subject `Seal iteration 1 with scalar reader evidence and handoff` is the next-round input. New contracts: 35 obligations / 17 controls; final product suites: 383 passed / 4 skipped. Published M03/M21/J04 formal corrections remain partial. The sections below preserve checkpoint 0's original account and predictions; the current handoff and public feedback supersede conflicting scope/count claims (including the old 26-Python-definition figure).

Branch `consolidated_uplift`, product pin `3eaa79cf` (v4.7.0), from the guidance arm `24c6b0c0` with the playbook arm `2d59e578` imported verbatim. Assignment: `reviewed-plan.md` (2026-11-14). Nothing outside `.g5/` and the imported `experiment/playbook-*` trees changed; the product, `.agents/` and `experiment/g5-verus/` are byte-identical to their sources (gate check 1). Nothing was pushed or posted. No statement is `implementation-verified`: no product body is verified here.

## 1. Commits, environment, gate

| Commit | Content |
|---|---|
| `abfce8dd` | the playbook arm imported verbatim from `2d59e578`: `experiment/playbook-uplift` tree `becf53a4`, `experiment/playbook-completion` tree `a8fe7129` (3,335 files) |
| `36ed59dc` | tooling: `run_verus.py` copies each raw Verus log beside its receipt (additive); `tools/run_playbook_crate.py`; a scoped `.gitignore` re-including `results/` and `*.log` |
| `0bd0a68e` | WP0: [families.tsv](../../Verus_verification/families.tsv), [check_consolidated.py](../../Verus_verification/tools/check_consolidated.py), reruns of both arms (receipts with logs) |
| `3a44b8c0` | WP1 Tier 1 ontology lifts, the mechanical register crosswalk, contract A (window reader) |
| `bf33cd3d` | WP2 contracts B1 (freshness), B2 (embedded no-row), B3 (relationship text), D (index declaration); findings bug-adp-001, bug-cyp-101 |
| `41e33024` | statement crosswalk, sweep log, code links, leads L1/L2 settled (bug-led-101, q-con-001, q-con-002), upstream #12/#13 |
| final | coverage numbers, coverage map rows, reader self-check, runbook section, this handoff. The final commit is the tip of `consolidated_uplift` (`git log -1`) |

Environment (this Mac, arm64; no IRIS used): Verus `0.2026.10.04.426d8b0` at `~/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus`; `actors` from `~/.cache/g5-verification/ivg-actors-c03f9fa`; the pin exported to `$RUN_DIR/pin` with `uv sync --frozen --all-extras` (CPython 3.11.8); `RUN_DIR=$HOME/runs/ivg-consolidated-20261114`. Provenance: [SOURCE-consolidated.json](../../Verus_verification/SOURCE-consolidated.json). Copyable commands: [runbook, "On this machine"](../../Verus_verification/runbook.md#on-this-machine-consolidated-uplift-2026-11-14).

Gate: `python3 .g5/Verus_verification/tools/check_consolidated.py` → **PASS** at the final commit: product paths equal the pin (HEAD and working tree); `.agents` and `experiment/g5-verus` equal `24c6b0c0`; both imported trees hash as imported; no untracked file outside `.g5/`; the five inherited model roots, `model.json` files and `twin.rs` byte-identical; `check_evidence.py` FRESH (10 models incl. bindings, 40 native observations, 105 playbook rerun pairs); `check_ontology.py` 14 files, 0 issues, 0 warnings; `check_findings.py` no problems; all 113 + 19 + 56 guidance-arm register IDs still anchors; the four crosswalks complete; 52 code links each resolved to one definition at the pin and one `fn`.

## 2. Inherited results

| Arm | Re-run here and matched | Not re-run (why) |
|---|---|---|
| Guidance | 5 of 5 proofs at the recorded counts (ledger_redaction 41, graph_structure 67, temporal 113, search 56, platform 51) and **128 of 128 controls EXPECTED_FAIL** (`results/<model>/20261115T*`), about 15 minutes | twin build (its probe needs the VM's IRIS); 40 native observations (no IVG IRIS here; rule 3 also forbids repeating the security-relevant probes) |
| Playbook | 15 crate baselines at their recorded counts: proofs 88, breadth 94, pa3 108, d1b 92, d1c 111, d1d 118, d1e 115, d1f 115, d9 115, d9b 158, d9c 158, env 305, env2 433, mech 1,149, sys 256; uplift/proofs 53 (no RESULTS.json; count from MODELS.md). Controls of breadth (7), pa3 (9), d1b (11), d1c (10), d1d (21), d1e (15), d9c (16): **89 of 89 EXPECTED_FAIL at exactly the recorded error locations**. `actors` 121 verified each time | explorer crates (core and core-partition above 8 GB; the others inherited with registry records), simulator and contract lanes (need the VM's IRIS), proofs-mech's 120 and proofs-sys's 12 controls (time), proofs-stmt and lockplans (partial) |

Retained failures: two repeated playbook baselines that cargo took as up to date (no verdict; `playbook-proofs-pa3/20261115T040739Z-baseline`, `playbook-proofs-d9c/20261115T040807Z-baseline`; the tool now cleans the package); the first `index_declaration` control run where `skip-ekey-check` **survived** (a weak theorem, fixed); the first `embedded_no_data` binding (harness error, DISAGREES). Every family's status, design attribute and rerun: [families.tsv](../../Verus_verification/families.tsv) (40 families: 7 guidance, 28 playbook, 5 new).

## 3. Governing ontology

- **Tier 1 (all 13 rows)**: `ledger.commit` (M03), `temporal.window.sources` (M06, new), `temporal.window.paging` + new `.release` (M07, M08 incl. the empty middle page), new `structure.rebuilt.stamp` (M09), `structure.multigraph.count` (M11), new `algorithms.op.paths` / `.weighted` / `.direction` (M12), `search.embedding.width` + `search.routes.no_fallback` (M14), `install.bulk_load.loader` (M23), new `install.snapshot.routes` (J01) and `.temporal` (J02), new `structure.adjacency.declare` (M16, J07), a new [adapters page](../../ontology/concepts/adapters.g5.md) with `adapters.embedded` and `.no_data` (M17), new `query.values` / `.relationship_text` (M18). Each with `path::symbol` sources at pin lines, `Playbook:` statement IDs and a `Verus:` line.
- Model-supported rows reconciled: the owning blocks of M01, M02, M03, M10, M13, M21, J04, J05, J08 name the active family and its design (as-built or **reviewed**, with the control that reintroduces the pin's behavior).
- Root: an `adapters.` topic, a "Where the detailed statements are" map from every playbook module to pages, and a narrower "Not covered" (the engine read API outside Cypher and the exports still have no owning block).
- Tier 2: [ontology-sweep.tsv](../../Verus_verification/crosswalk/ontology-sweep.tsv). Swept row by row: the window reader (`TMP-B6.*`, 16 rows: 9 lifted incl. the reversed window, page bound and handle-per-connection; 5 already present; 2 deferred). **Not swept: 1,335 refusal or contrast rows** in the other modules (7 modules not touched at all). Statement crosswalk: [statements.tsv](../../Verus_verification/crosswalk/statements.tsv) (371 blocks; 27 extended from the playbook arm; 344 `g-only`, meaning not yet compared).
- Contradictions: none found between the arms' statements on the Tier 1 rows. Severity disagreements are kept in the merged register entries (bug-003 Medium vs S1; bug-tmp-002 High vs S2; bug-str-002 High vs S2).
- Removed text: none dropped. Rewordings: `temporal.window.paging`'s bullet "A reader is closed when the iteration ends or is abandoned" moved into its main sentence; the root's "Not covered" sentence "nothing else about them was recovered" replaced by a pointer to the playbook modules that state their behavior.
- Self-check from `.g5/ontology` alone: [reader-check.md](reader-check.md) (17 differing public cases answered).

## 4. New contracts (all under `.g5/Verus_verification/models/`)

| Model | Obligation (cases) | Theorems | Controls | Binding (Observed at unit level; server or database substituted) | Premises, trust |
|---|---|---|---|---|---|
| [temporal_window_reader](../../Verus_verification/models/temporal_window_reader/NOTES.md) | M06, M07, M08 | `theorem_spec_sources_omitted_vs_empty`, `theorem_server_filter_sources`, `theorem_yield_is_concat_to_done`, `theorem_exhaustion_frees_without_close`, `theorem_close_mid_read_once`, `theorem_failed_page_closes_once`, `theorem_server_full_page_nonempty` (16 verified) | 8 of 8 | real `window_spec` + `TemporalWindowCursor`, 640 + 45 cases, AGREES, 3/3 detection | the window ends; server half Inspected |
| [freshness_stamp](../../Verus_verification/models/freshness_stamp/NOTES.md) | M09 | `theorem_unstamped_stale_at_zero`, `theorem_stamped_zero_current`, `theorem_python_agrees_with_objectscript`, `theorem_stale_stores_exact` (7) | 4 of 4 | real `Freshness`, 1,795 cases, AGREES | canonical integer stamps; `TraversalKHop.Fresh` Inspected |
| [embedded_no_data](../../Verus_verification/models/embedded_no_data/NOTES.md) | M17 | `theorem_no_data_is_empty`, `theorem_no_data_on_every_path`, `theorem_other_error_raises`, `theorem_success_rowcount_unknown`, `theorem_batch_counts_rows`; witness `witness_ddtab_mid_batch_reruns_rows` (13) | 6 of 6 | real `EmbeddedCursor`, 64,000 cases, AGREES; rerun observed `[0, 0, 1]` | `iris.sql` substituted |
| [rel_prop_text](../../Verus_verification/models/rel_prop_text/NOTES.md) | M18 | `theorem_decode_classes`, `theorem_noncanonical_stays_text` (**reviewed** rule), `theorem_as_built_agrees_on_plain_ascii`; as-built witnesses (10) | 5 of 5 | real `parse_rel_prop_text` + `_decode_rel_prop_text_columns`, 1,139 texts, AGREES with as-built; 38 departures from the rule | `JSON_VALUE` round trip not observed |
| [index_declaration](../../Verus_verification/models/index_declaration/NOTES.md) | M16, J07 | `theorem_no_prereq_no_ddl`, `theorem_prereqs_declare_both`, `theorem_declared_left_alone`, `theorem_backfill_before_edge_index`, `theorem_plain_replaced`, `theorem_second_run_is_noop` (7) | 4 of 4 incl. the 4.7.0 plain-index defect | real `ensure_adjacency_index`, 216 states x 2 runs, AGREES | DDL effect inside IRIS not modeled |

Trust inventory of every new model: empty (no `assume`, `admit`, `external_body`); bundled `vstd` only; the harnesses' spec transcriptions are unverified Python. **Attempted and not built** (plan C, E, F): the history fold (compute_diff against reconstruct), restore-to-reader (J01, J02), writer paths into the id reader (#12) and the row-limit selector (#13); their blocks and coverage rows say "no formal contract" with what is missing.

## 5. Registers

Every guidance-arm entry kept (113 / 19 / 56). Crosswalk rows (one per source ID; [crosswalk/](../../Verus_verification/crosswalk/)): findings 442 = guidance 113 + playbook 313 audit records (298 own entries, 9 merged into guidance entries, 6 withdrawn: 2 refuted, 3 not reproduced, 1 duplicate) + 3 renumbered + 3 sub-case labels + 7 unfiled candidates + 3 new here; simplifications 56 = 19 + 36 root causes + HD-1301 merged into simp-001; questions 139 = 56 + 60 decisions (HD-1801 merged into q-plt-004) + REACH-1..5 + D-1..D-14 (inherited proof debt) + 4 new here; 104 errata in `evidence-errata.tsv`. Merges confirmed by trigger and effect: bug-001/F-1303, bug-002/F-C1201+F-C1301, bug-003/F-1304, bug-led-007/F-C1203+F-C1308, bug-srch-002/F-C0702, bug-tmp-002/F-0501, bug-str-002/F-0402, simp-001/HD-1301, q-plt-004/HD-1801. **Not yet compared** with the other arm: every other playbook entry (marked in its text).

New findings (discovered here, each Suspected end to end): **bug-adp-001** (Low) the embedded batch fallback reruns rows that already ran; **bug-cyp-101** (Low) relationship property text with a final line break or non-ASCII digits reads back as a number; **bug-led-101** (Low) the reverse diff of a delete-and-recreate range reports the earlier property as absent. New questions: q-con-001 (L1), q-con-002 (L2); historical: hist-012, hist-013. Findings index regenerated: [findings.md](../../Verus_verification/findings.md).

## 6. Coverage (command: `python3 .g5/Verus_verification/tools/inventory.py`)

Python definitions in `iris_vector_graph/` (3,004; 119 files; 1,172 public): 26 directly linked from active formal items, 8 indirectly only. ObjectScript members in `iris_src/` (972 in 73 classes: 909 ClassMethod, 60 Method, 1 Query, 2 Trigger): 10 direct, 0 indirect only. SQL files: 14, none linked. Outside the denominator: `api/` 84, `src/` 141, `scripts/` 866 definitions. Tested upstream: 1,788 test files (no per-symbol mapping claimed). Implementation-verified: **0**. Of 15 linked blocks, 6 link both writer or producer and reader or consumer. Unmapped strata and the per-clause map: [coverage.md, consolidated section](../../Verus_verification/coverage.md#consolidated-uplift-2026-11-14-new-contracts-and-the-playbook-arms-active-families).

## 7. Paired predictions for the 32 public cases

Predictions for the graders to check, not grades. "Before" is the better arm per axis from `public-baselines.tsv`. No prediction is made about any private case.

| Case | Before: best ontology (G/P) | After: ontology | Ontology block | Before: best model (G/P) | After: model | Formal item |
|---|---:|---:|---|---:|---:|---|
| M01 | 2 (2S/2S) | 2 | ledger.commit.admission, ledger.idempotency | 2 (2S/2S) | 2 | G ledger_redaction theorem_retry_replays_first (as-built); P pa3 ledger_l1 (reviewed) |
| M02 | 2 (2S/2S) | 2 | ledger.idempotency | 2 (1P/2S) | 2 | P proofs-pa3 ledger_l2 commit_glob/lay_idem (reviewed) |
| M03 | 2 (1P/2S) | 2 | ledger.commit (Tier 1) | 2 (1P/2S) | 2 | P proofs-pa3 ledger_l2 (reviewed) |
| M04 | 2 (2S/2S) | 2 | ledger.readers | 1 (1P/1P) | 1 | unchanged: no named-revision reconstruction contract |
| M05 | 2 (2S/2S) | 2 | ledger.readers | 0 (0U/0U) | 0 | unchanged: no compute_diff-vs-reconstruct contract (C not built); bug-led-101 recorded |
| M06 | 2 (2S/2S) | 2 | temporal.window.sources (new) | 0 (0U/0U) | 2 | temporal_window_reader theorem_spec_sources_omitted_vs_empty + theorem_server_filter_sources (as-built; server Inspected) |
| M07 | 2 (1P/2S) | 2 | temporal.window.paging.release (new) | 0 (0U/0U) | 2 | temporal_window_reader theorem_yield_is_concat_to_done, theorem_close_mid_read_once |
| M08 | 1 (1P/1P) | 2 | temporal.window.paging, .release | 0 (0U/0U) | 2 | temporal_window_reader theorem_yield_is_concat_to_done (empty middle page), theorem_failed_page_closes_once |
| M09 | 2 (1P/2S) | 2 | structure.rebuilt.stamp (new) | 1 (1P/1P) | 2 | freshness_stamp theorem_unstamped_stale_at_zero, theorem_stamped_zero_current |
| M10 | 2 (2S/2S) | 2 | structure.degree.cache.uncommitted | 2 (2S/2S) | 2 | G graph_structure theorem_as_built_cache_sound + witness |
| M11 | 2 (1P/2S) | 2 | structure.multigraph.count (Tier 1) | 1 (1P/1P) | 1 | unchanged: no one-hop projection contract |
| M12 | 2 (0U/2S) | 2 | algorithms.op.paths.weighted (new) | 0 (0U/0U) | 0 | none: no optimality proof of the ObjectScript Dijkstra |
| M13 | 2 (2S/2S) | 2 | search.embedding.other_model | 2 (2S/1P) | 2 | G search theorem_store_routes_and_refuses |
| M14 | 2 (1P/2S) | 2 | search.embedding.width, search.routes.no_fallback (Tier 1) | 1 (1P/1P) | 1 | unchanged: route absence modeled, query-width preflight not |
| M15 | 2 (2S/2S) | 2 | search.routes.orphan, search.embedding.width | 1 (1P/1P) | 1 | unchanged |
| M16 | 1 (1P/1P) | 2 | structure.adjacency.declare (new) | 1 (0U/1P) | 2 | index_declaration theorem_no_prereq_no_ddl, theorem_prereqs_declare_both, theorem_declared_left_alone |
| M17 | 0 (0U/0U) | 2 | adapters.embedded.no_data (new page) | 0 (0U/0U) | 2 | embedded_no_data theorem_no_data_is_empty, theorem_other_error_raises |
| M18 | 0 (0U/0U) | 2 | query.values.relationship_text (new) | 0 (0U/0U) | 2 | rel_prop_text theorem_decode_classes, theorem_noncanonical_stays_text (reviewed rule) + as-built witnesses |
| M19 | 2 (2S/2S) | 2 | query.compiled.fallback | 1 (1P/1P) | 1 | unchanged |
| M20 | 2 (2S/2S) | 2 | query.compiled.fallback | 1 (1P/1P) | 1 | unchanged (P planc_l2 reviewed; restart supplied) |
| M21 | 2 (2S/2S) | 2 | algorithms.cache | 2 (1P/2S) | 2 | P proofs-d1e acache_l2 (reviewed; pin = control_f1004) |
| M22 | 2 (2S/2S) | 2 | temporal.ledger | 1 (1P/1P) | 1 | unchanged |
| M23 | 2 (1P/2S) | 2 | install.bulk_load.loader (Tier 1) | 1 (0U/1P) | 1 | unchanged: P bulk_l2 checkpoints only |
| M24 | 2 (2S/2S) | 2 | ledger.verify | 1 (1P/1P) | 1 | unchanged |
| J01 | 2 (1P/2S) | 2 | install.snapshot.routes (new) | 1 (0U/1P) | 1 | unchanged: P snap_l2 abstract contents |
| J02 | 2 (1P/2S) | 2 | install.snapshot.temporal (new) | 1 (0U/1P) | 1 | unchanged: P snap_l2; the window model is not connected to restore |
| J03 | 2 (2S/2S) | 2 | ledger.readers | 0 (0U/0U) | 0 | unchanged; q-con-001 recorded |
| J04 | 2 (2S/2S) | 2 | algorithms.cache.token | 2 (1P/2S) | 2 | P proofs-d1e acache_l2 (reviewed) |
| J05 | 2 (2S/2S) | 2 | ledger.commit.serial, ledger.idempotency | 2 (1P/2S) | 2 | P proofs-pa3 ledger_l2 (reviewed) |
| J06 | 2 (2S/2S) | 2 | temporal.ledger | 1 (1P/1P) | 1 | unchanged |
| J07 | 1 (1P/1P) | 2 | structure.adjacency.declare (new) | 1 (0U/1P) | 2 | index_declaration theorem_backfill_before_edge_index, theorem_no_prereq_no_ddl |
| J08 | 2 (2S/2S) | 2 | query.compiled.modes, .fallback | 2 (1P/2S) | 2 | P proofs-d1d planc_l2 (reviewed) |
| **Total** | **57** | **64** | | **33** | **46** | |

## 8. Outstanding questions, by consequence

1. **Serialization of erase, commits and redaction start** (bug-001, bug-002, simp-001/HD-1301, HD-1201): working answer, one lock across all three; alternative, refuse while transactions are open.
2. **Completeness of tenant removal** (HD-1304, HD-1303, REACH-1..5, F-1304): working answer, require tenant prefixes or report an explicit incomplete result naming every store not reached; alternative, record each node record's graph and migrate history.
3. **Restore against a live ledger** (q-plt-004 = HD-1801, F-1801): working answer, refuse when the heads diverge; alternative, explicit wholesale replacement.
4. **Reverse diffs and the streaming bound** (bug-led-101, q-con-002, q-con-001): working answer, a diff is a set of net changes and must report the earlier revision's values correctly; the bound covers delivery only. Alternative: a diff is a script (reverse tied entries), and the bound caps memory (fold incrementally).
5. **Reachability of bug-adp-001 and bug-cyp-101 on IRIS**: whether an unsupported-path error can follow a successful prepare, and whether `JSON_VALUE` returns a stored line break; a native observation decides each.

## 9. Costs (wall clock, this session, 2026-11-14/15 UTC)

WP0 import, registry, gate: about 50 minutes, with the reruns in the background (guidance controls 03:52-04:07, about 14.5 minutes of machine time; playbook reruns 03:54-04:03 and 04:07-04:11, about 13 minutes). Tier 1 ontology: about 60 minutes. Register crosswalk: about 30 minutes. Contracts A, B1, B2, B3, D: about 75 minutes in total; each proof under 1 s and each control suite under 15 s; bindings under 2 s each. Leads, sweep, links, coverage, handoff: about 70 minutes. No IRIS container was started (plan 3.5 was optional; nothing in priorities A-D needed it).

## 10. Independent review: pending

No independent review was possible in this session (no other session may be started). Package for the reviewer:

- Reproduce one new contract: the runbook's "One new contract end to end" (proof, `CONTROL=stop-on-empty-page`, `binding.py`), and one playbook crate (`run_playbook_crate.py proofs-d1e baseline control_f1004_create_moves_no_token`).
- Read [reader-check.md](reader-check.md) without this file, then answer the 17 cases from `.g5/ontology` alone.
- Attack first: (1) do the binding harnesses' hand transcriptions match the Verus spec functions they claim to (they are unverified Python), and do the enumerated domains cover the decisive inputs? (2) are the "reviewed design" labels and the claim "no pin-departure control for idempotency" in `proofs-pa3` right, i.e. is any active reviewed family being read as a product property? (3) are bug-adp-001, bug-cyp-101 and bug-led-101 real on IRIS, and are the 1,335 unswept refusal and contrast rows hiding Tier 1-like losses?

## 11. Method notes (mechanism principles)

| Concrete failure here | Smallest action that changes a capable agent's decision | Good behavior to preserve | Why it transfers | Cost |
|---|---|---|---|---|
| A repeated crate run from a `git archive` copy verified nothing (cargo up to date from archive mtimes) and printed no result line | the rerun tool cleans the package and treats "no result line" as ERROR, never a pass | rerunning from a pristine copy of the imported tree | any receipt-producing runner over immutable copies | one `cargo clean -p` per run |
| A safety theorem stated over the guarded predicate let a control that weakens that predicate survive | state "nothing happens unless" theorems over the raw inputs, not over the helper being controlled | controls as the test of a contract's strength | any controlled contract with a named precondition helper | none |
| A playbook statement existed but sat under a module with no owner page (M17 scored 0) | the root's module-to-page map plus an owner page for every module | detailed evidence tables as a source, not a second ontology | any consolidation of a detailed ledger into a governing ontology | one table |
| Hand transcriptions of spec functions in the bindings are unverified | a verified exec twin per binding (as `ledger_redaction/twin.rs`) | enumerated comparison plus mutation detection | every unit-level binding | about an hour per model |
