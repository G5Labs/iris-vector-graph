# IRIS findings audit — sealed iteration 13

Audit base: Git `eceb147d37720658e34b07f279cc267870fd393c`; unchanged product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`. The three live registers were byte-identical to the seal at the start. The pre-existing unfinished iteration 14 work was preserved. This is a register audit, not another uplift iteration, a product repair or a new verification campaign. No benchmark HTML, frozen seal/archive, production source or existing model/proof receipt was changed.

## Reconciliation against every starting ID

| Inventory | Start | Result |
|---|---:|---|
| Bugs/issues | 434 | 42 starting IDs e2e reproduced; 4 partial reproduced; 107 security-related entries outside active reproduction scope; 281 moved to the review record |
| Simplifications | 55 | 54 unsupported reduction claims withdrawn; 1 previously retired counterproposal stays retired; no active net-reduction claim |
| Questions/debt/history | 146 | 9 settled by existing attributable authority; 121 policy questions open; 2 historical reports and 14 qualified proof-debt entries retained |

The live bug file has 153 finding entries: 46 ordinary entries with executable evidence and 107 explicitly scoped defensive-review entries. Archived-ID navigation in that file preserves old links without retaining the removed claims as active findings. All 434 starting IDs resolve to a live entry or the [review record](bugs-review.md); the crosswalks keep their source IDs and now include `canonical_path` and audit disposition. The complete per-ID counts, sources, test mappings and remaining gates are in [reconciliation.json](reconciliation.json).

There were **zero protected `Need fix`, `Defer` or `Irrelevant` determinations** in the sealed or live starting registers. Nine settled questions use existing sources; none is a new human approval. Other agent assumptions remain explicitly provisional. Thirty-six missing canonical owners were added as narrow questions or the documented raw-helper contract; every pre-existing commitment retains its kind and meaning. Two existing body links were repointed to archived findings.

## Actual product regressions

The final [regression program](regressions.py) completed **41/41 caller contrasts**, covering 42 starting IDs, with passing neighbors. PASS means the recorded defect and neighbor reproduced; it does not mean the product is repaired. The tests use actual pinned Python, supported engine or SQL-store entries, and real IRIS SQL/ObjectScript providers. Test-runtime location and cleanup are isolated; relevant result rows, errors, writes, transactions and readers are not substituted. Selected existing scenario functions are reused rather than copied into new product implementations.

Examples, with full values in [regressions.json](regressions.json):

- A leading grouped unmatched OPTIONAL returns SUM null; ordinary empty global SUM returns zero.
- Accepted `id`/`p_id` properties both persist, but the flat node reader loses one. A distinct ordinary key survives.
- Real relationship text `12\n` and `1٢` is read as integer 12; `12x` remains text. This closes the former persistence/JSON_VALUE gate for those inputs.
- Temporal update, partial-write/retry, bulk fallback and seven rollback scenarios disagree with the raw window at the final public statistics/velocity reader; committed neighbors agree.
- A ledger delete leaves a parallel survivor's SQL row but loses its adjacency, while a single-edge neighbor verifies clean. Healthy parallel rows also cause a false verification report.
- PageRank's actual public engine/Owner lists 10,000 of 10,002 nodes with score sum below one; a one-node graph passes. Arno cross-route equivalence remains untested.
- Real merge restore skips one of two archived parents in one graph, while preserving an existing live graph. An earlier one-parent-per-graph attempt succeeded and is retained as a refuted subcase.
- The public SQL store's membership decoder fails for node ID `components`; the engine successfully falls back. No engine-WCC failure is claimed.

The four [component witnesses](components.py) are **partial reproduced**: embedded batch replay with scripted `iris.sql`; fusion absent-rank arithmetic with supplied legs; and two actual Bolt session traces with local transports and a one-row engine adapter. [components.json](components.json) names every remaining native trigger, listener, database/provider and caller gate. The embedded panel makes 1,250 execute and 62,750 batch comparisons with zero mismatches and explicit detection controls. The two pinned upstream unit files supporting helper/DDL authority passed **60/60**; [log](upstream-authority-tests.log).

The dedicated audit runtime is `ivg-register-audit-20261115`, hostname `ivg-register-audit`, `127.0.0.1:35976`, namespace USER, Community 2026.1.0.234.1. It was created independently; no stopped builder was restarted and the iteration 14 runtime was not used. The initializer compiled the pin's classes, with no failures; three `%AI` MCP classes were unavailable. No Arno library was installed. Drivers: `intersystems-irispython 5.3.2`, `intersystems-iris 5.3.3`, wrapper `0.5.20`; rdflib `7.6.0`. [Runtime identities/source hashes](runtime.json), [setup log](runtime.log). Only this isolated instance is reset by the regression helper. It was stopped after validation; restart this dedicated test container, not a builder, to replay native tests.

From the product checkout, with the dedicated container running and the pin exported as recorded in runtime.py:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/audits/register-20261115/regressions.py
PYTHONDONTWRITEBYTECODE=1 /Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python -B -I .g5/Verus_verification/audits/register-20261115/components.py
python3 .g5/Verus_verification/audits/register-20261115/verify.py
```

The final caller run is [regressions-final.log](regressions-final.log). Attempts 1–7 retain failed harness assumptions, narrowed triggers, negative neighbors and corrections; none was converted silently into evidence. The tested source is hash-checked against the product Git object. See [commands.json](commands.json) for setup, exact run commands, source searches and checks. Re-running the tests updates their result files; preserve existing run outputs if making a new audit. The one-time reconciliation helpers deliberately refuse regeneration after this audit is applied, so historical imports cannot resurrect removed claims or reinterpret every non-`none` reproduction line as native evidence.

## Good-faith checks and incomplete reproduction

Every starting ID was triaged from its sealed entry, direct existing evidence, available source/test/doc references, canonical owners and relevant product history. The machine-readable [source inventory](source-review.json), [353-file catalog with product commits](source-catalog.json), and [literal searches of the actual tests](test-search.json) record those checks. A matching test filename, source branch, model witness or historical `live` label was not promoted automatically into a new e2e reproduction. Four cited source names are absent: two abbreviated ADR placeholders, retired `docs/README_VERBOSE.md`, and absent spec 019. Their absence is recorded, not filled with invented evidence.

The removed set includes 238 inconclusive regression gaps, one unestablished concurrency schedule, one performance-envelope gap, one durability gap, one conditional cross-provider failure, six environment blocks, 22 source/historical observations, three bounded refutations, one caller-unreachability check and seven stopped unfiled candidates. These sum to 281. The bounded refutations are F-0904's stronger process-poisoning effect, F-C0403's tested failed-rebuild loss, and F-1612's default 32,000-character stream premise; the last still lacks a deployed REST end-to-end check. F-0825's fall-through was not reached by the six recorded ordinary parser shapes, which does not prove global unreachability. **No failure to reproduce is taken as proof of correctness.**

The incomplete per-ID list is explicit in `incompletely_reproduced_ordinary_ids`, each record's reason, and the [review record](bugs-review.md). In particular, the remaining partial witnesses still need their named real-provider/caller gates. The 107 security/privacy/boundary-related entries received defensive source and existing-evidence review only. No vulnerability reproduction, offensive workflow or previously interrupted investigation was constructed or executed.

Seven already unfiled/stopped candidates remain unassessed: F-C0811, F-C1711, F-C0111, F-C0511, F-C0512, F-C0513 and F-C1011. Their IDs were retained; their drafts were not opened. The external `interrupted-unassessed` directory and its inputs were not opened or used.

## Simplifications and questions

Every proposed simplification has a [per-ID preservation/cost review](simplification-review.md), source metrics and original configurations in [simplification-review.json](simplification-review.json). Twenty-four entries have a recorded limited comparison: same-schema redaction variants or whole-crate control/repair query counts. Those are measured declarations or recorded verification queries, including unrelated modules where qualified, not explored states, independent state counts or net whole-product reductions. The rest lack a complete comparable after-model. Centralizing an obligation, adding a codec, reference semantics, token state, owner API or inventory does not remove that obligation. One historical search proof receipt has two stale inputs (model.json and search.rs); its counts are historical and do not establish the current model. [Freshness details](reused-proof-bindings.json). The 54 unsupported reduction claims are therefore withdrawn without rejecting their possible repair value. No proposed product redesign was implemented and no new Verus proof campaign ran.

The [146-entry question review](question-review.md) follows each canonical owner, distinguishes current behavior from authority, and gives alternatives, implications, a provisional working assumption and settling evidence. Existing-authority resolutions: HD-0001, HD-0202, HD-0301, HD-1002, HD-1004, HD-1302, HD-1305, HD-1601 and HD-1704. Residual mechanisms, compatibility and future policy choices stay open. Code/comments and tests were checked alongside docs and available product commits; prior intent records' broader searches are reused with their limits rather than described as fresh branch-wide searches.

Read-only [public upstream queries](upstream.json) found Discussions disabled. Issues #12 and #13 remain open; fixed-at-pin describes pinned changelog/regression evidence, not issue closure. No maintainer approval or contrary policy was inferred from absence of public discussion.

## Preservation and validation

[verify.json](verify.json) records ID conservation, evidence counts, canonical links, all active ordinary owner backlinks, unchanged production/model/receipt inputs, frozen hashes and preservation of unfinished iteration work. Standard G5 ontology and findings checks pass. The ontology checker reports two inherited writing warnings; the pre-existing commitments were not rewritten to remove them. `git diff --check` passes.

`start/` contains exact pre-edit register/ontology/crosswalk bytes. Those snapshots retain original relative links; use the reconciled canonical links for current navigation. [frozen-hashes.json](frozen-hashes.json) records only hashes of the seal and before/after foundation archives. No frozen receipt, seal or archive content was modified.
