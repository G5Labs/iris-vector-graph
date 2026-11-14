<!-- markdownlint-disable MD013 -->

# 3.5-style: style review of modules 11-14 against IVG's own documented conventions

Lane: product-gates. Observation only: nothing in the product was changed, compiled, run or connected to.
Registered as `pg-style-review` (kind review). Written by a review agent of the lane from the brief in the lane report;
the lane spot-checked 9 of its citations against the pin (ARCHITECTURE.md:203, TESTING_POLICY.md:291-293,
ADR-0008:12-21, ADR-0011:12-17, Eraser.cls:238-242, guard.py:43-56, LedgerStats.cls:1-3/48/53, Ledger.cls:242-248,
changeset.py:334-335 with CONTEXT.md:173-177): all as cited.

- **Pin**: product tree at `3eaa79cf77d3e0a879b2cced634cf2729d81499e`. The checkout's HEAD is `533cd0a1`, and `git diff --stat 3eaa79cf HEAD -- . ':(exclude)experiment'` is empty, so every `path:line` below is at the pin. Paths are relative to the audit root.
- **Scope**: production files of modules 11 ledger, 12 erasure, 13 redaction and 14 replay, as `ontology/11-ledger.md`..`14-replay.md` scope them. ObjectScript (`iris_src/src/Graph/KG/`): `Ledger.cls`, `LedgerApply.cls`, `LedgerGenesis.cls`, `LedgerStats.cls`, `LedgerRevision.cls`, `Eraser.cls`, `GraphStores.cls`, `LedgerRedact.cls`. Python: `iris_vector_graph/ledger/{changeset,client,guard,errors,__init__,replay,export}.py`, `iris_vector_graph/_engine/ledger.py`, and `iris_vector_graph/_engine/nodes_edges.py:1473-1560` only.
- **Method**: I read every in-scope line by eye, and checked each line number with `sed -n`/`grep -n`. Only documented conventions count. Each one is listed below with its source. Code may cite its own design docs (specs, ADR text, class headers) as evidence, but those do not become rules unless a convention source makes them one (C-14). Anything a configured tool checks (ruff, black, isort, mypy) is left to the lane's tool run and is not counted again here. All evidence is inspected-grade: I read source. I ran nothing.
- **Sources read**: `CONTRIBUTING.md` (in full); `.specify/memory/constitution.md` (in full); `CONTEXT.md` (in full); `docs/dev/TESTING_POLICY.md` (only its rules for production code); `docs/adr/0001`-`0016` (0003, 0004, 0011, 0013 and 0016 in full, the others as far as they touch these files); `PRE_RELEASE_CHECKLIST.md` §5, §6 and §8c; `pyproject.toml:201-253`; `docs/architecture/ARCHITECTURE.md:90-209`. I also ran `grep -ri` for style, naming, convention, docstring and comment under `docs/dev` and `.specify`. That search found `docs/dev/notes/research/alt-impl/BRIEF.md:38-42`, which gives ObjectScript conventions. The rest was test, TCK or template text, or not about style.
- **AGENTS.md / CLAUDE.md**: neither is in the repository at the pin, and neither is `.claude/` (checked with `git ls-tree -r` at `3eaa79cf`). `BRIEF.md:38` says its rules come "from the repo's CLAUDE.md", which does not exist at the pin. I therefore use BRIEF.md's rules as BRIEF.md writes them, at secondary authority: `BRIEF.md:5` reads "Status: speculative. Nothing here is adopted."

## Verdict

**3.5-style: fail (23 deviations of 7 conventions)**

"Of 7 conventions" means the 23 deviations break 7 different conventions. In all, 26 conventions are listed, and 23 of them apply and were judged. Counts by convention: C-7 3, C-8 6, C-9 1, C-14 5, C-16 1, C-17 6, C-21 1. If the secondary-authority BRIEF.md rules (C-21..C-26) are left out, the count is 22 deviations of 6 conventions. Not counted: the borderline items B-1..B-5, where the documents disagree with each other or the rule's text does not cover the case, and the reviewer notes. Some aspects are not judged at all, because the product documents no convention for them (see Limitations). That is a gap in the documentation, not a pass.

## Conventions

"Applies" means the convention constrains the production code of these modules. Excluded because they govern tests, process or releases rather than production code: constitution I-IV and VI-VIII, Development Workflow and Governance; CONTRIBUTING's sections on tests, containers, CI parity, TCK, coverage and releases; TESTING_POLICY's rules on fixtures, markers, gates and environment; PRE_RELEASE_CHECKLIST §1-4 and §7-9; ADR-0005, 0007, 0010, 0012 and 0014, which nothing in these files touches.

| ID | Convention (quote or faithful paraphrase) | Source | Applies | Result |
| --- | --- | --- | --- | --- |
| C-1 | Lint before committing: `ruff check . && black . && isort .`. Black and isort use line length 100; mypy runs with `disallow_untyped_defs` and related settings; ruff must show zero errors | CONTRIBUTING.md:36-40; pyproject.toml:201-243; PRE_RELEASE_CHECKLIST.md:139-145 | yes (Python) | left to the tool run, not counted |
| C-2 | "No new `type: ignore` comments added without justification" | PRE_RELEASE_CHECKLIST.md:146 | yes (Python) | conforms: none in scope |
| C-3 | Every `.cls` compiles cleanly, with no errors or warnings in `Graph.KG.*` | PRE_RELEASE_CHECKLIST.md:150-154 | yes (OS) | not judgeable without IRIS |
| C-4 | Only `Graph.KG.GraphKey` derives a graph key: `ForIndex` for `^KG`, `ForLedger` for `^IVG.Ledger`, always from the name, never converted from the other key and never inline | ADR-0003:17-27, :68; CONTEXT.md:50-58; BRIEF.md:41-42 | yes (OS) | conforms |
| C-5 | In every `^KG` global the graph key is the first subscript after the store name; the default graph's key is `0` | ADR-0001:9-24; BRIEF.md:41 | yes (OS) | conforms |
| C-6 | `Graph.KG.Adjacency` is the only class that sets or kills `^KG("out")` and `^KG("in")` | ADR-0011:12-17 | yes (OS) | conforms |
| C-7 | One module owns every change to the Adjacency Index (`out`, `in`, `label`), and the Eraser and LedgerApply go through it | ADR-0008:12-21, :34; ARCHITECTURE.md:105-107 | yes (OS) | **3 deviations** |
| C-8 | No direct access to a `^KG` global outside its owners: TemporalIndex, plus Adjacency for the adjacency stores and EdgeScan for the rest | ADR-0001:48-49, as amended by ADR-0011:7, :29 | yes (OS) | **6 deviations** (writes); reads go to B-1 |
| C-9 | Only `Graph.KG.TemporalIndex` may "read or write" `^KG("tout"/"tin"/"bucket"/"tagg"/"edgeprop")`; any admin operation across graphs must be one of its classmethods, "not ... ad-hoc global scans" | ADR-0002:9-13, :34-36 | yes (OS) | **1 deviation** |
| C-10 | "Never `Kill ^NKG`": `GraphIndex.DropNKG` removes it | ARCHITECTURE.md:128 | yes (OS) | conforms |
| C-11 | Erasure owns its transaction and raises rather than returning a count on failure; a returned 0 means nothing matched; `rec` is never touched; `stmt` and `tuple` entries are removed in one pass over `("stmt")` | ADR-0004:10-23, :40-44; CONTEXT.md:198-208 | yes | conforms |
| C-12 | Redaction rules: the tombstone's form, the single trigger exemption, `idemRedacted`, a content-free `redaction` revision, refusal while the target is live, the marker, and the record readers raising | ADR-0013:12-29; CONTEXT.md:209-218 | yes | conforms |
| C-13 | `^IVG.TemporalStructural` is configuration: `EraseGraph` keeps it and `EraseAll` kills it | ADR-0015:12-13, :29 | yes (OS) | conforms |
| C-14 | "The class header comments are the reference for each" `Graph.KG` class, so a header must describe its class as it is | ARCHITECTURE.md:203 | yes (OS) | **5 deviations** |
| C-15 | Do not call the IVG Schema "schema prefix" (that is the setting that names it) or "SQLUser" | CONTEXT.md:25 | yes | conforms |
| C-16 | A glossary term used in code text keeps its glossary meaning | CONTEXT.md (each term's definition; here Collision at :173-177) | yes | **1 deviation** |
| C-17 | "No `except Exception: return False` on a path that changes data ... Let it raise, or catch the specific error and say what was not done." | TESTING_POLICY.md:291-293 | yes (Python as written; ObjectScript cases go to B-2) | **6 deviations** |
| C-18 | "Every message that names a call which writes says it writes." | TESTING_POLICY.md:294-297 | yes | conforms (see R-9) |
| C-19 | "Numeric comparisons MUST be deterministic and documented when values are stored as strings." | constitution.md:264 | yes | conforms |
| C-20 | "Every layer of indirection MUST be justified by a concrete requirement." | constitution.md:115-116 | yes | not judged (it needs design judgement) |
| C-21 | "`Set tSC = $$$OK` first and `Quit tSC` last in methods that return a status". I apply it to `%Status` methods that call code returning a status and then carry on | BRIEF.md:38-39 (secondary) | yes (OS) | **1 deviation** |
| C-22 | Use `$$$OK`/`$$$ISERR()`/`$$$ERROR()` | BRIEF.md:39 (secondary) | yes (OS) | conforms |
| C-23 | "never `$GET` on an object property" | BRIEF.md:39 (secondary) | yes (OS) | conforms |
| C-24 | "no `ORDER BY` with `SELECT TOP`" | BRIEF.md:39-40 (secondary) | yes (OS) | conforms; Python-issued SQL goes to B-4 |
| C-25 | "parenthesise every compound condition" | BRIEF.md:40-41 (secondary) | yes (OS) | conforms |
| C-26 | "Postconditionals take no spaces". I read this as no space outside parentheses | BRIEF.md:42 (secondary) | yes (OS) | conforms |

Conforming evidence, a few sites per convention:

- C-4: `Ledger.cls:45-50`; `LedgerApply.cls:505`, `561`, `688` use `ForIndex` for `^KG`, and `165`, `391`, `680` use `GKey`→`ForLedger`; `LedgerGenesis.cls:101`, `122`; `Eraser.cls:50-51`, `672`, `1139`; `LedgerRedact.cls:463`. Grepping for `$Char(1)` or `Key = 0` finds no inline derivation, only comments.
- C-5: every `^KG` kill in the Eraser is keyed `(store, key, ...)`, for example `Eraser.cls:239-242` and `579-584`.
- C-6: every `out`/`in` change goes through Adjacency: `LedgerApply.cls:508-514`, `563`, `689`; `Eraser.cls:234`, `450`, `547`, `668`, `788`, `1326`. No in-scope file has a `Set` or `Kill` of either store.
- C-9: the Eraser and LedgerApply delegate to TemporalIndex at `Eraser.cls:237`, `605`, `791` and `LedgerApply.cls:635`.
- C-10: `Eraser.cls:1042`.
- C-11: `Eraser.cls:54-62`, `259-262`, `810-812`, `1117-1144`; `nodes_edges.py:1497-1507`.
- C-12: `LedgerRedact.cls:337`, `353-378`, `206-210`, `420-441`; `LedgerRevision.cls:87-101`; `Ledger.cls:466-473`, `514-518`; `client.py:687-693`; `replay.py:812-822`.
- C-13: `Eraser.cls:245-247`, `808`.
- C-14: these headers are accurate: `Ledger.cls:1-17`, `LedgerGenesis.cls:1-10`, `LedgerRedact.cls:1-29`.
- C-15: `client.py:237` names the setting `_schema_prefix`, which the glossary allows.
- C-16: the code's own definitions match the glossary for tombstone (`LedgerRedact.cls:1-13`), erasure (`Eraser.cls:18-33`) and redaction (`client.py:643-664`).
- C-17: these paths conform. `client.py:258-259` re-raises with `from`. At `client.py:352-357` a transport failure becomes an error result, and `commit` then raises at `416`. `_engine/ledger.py:45-50` and `66-68` are status reads that report failures to `errors`.
- C-18: each remedy names its call with a writing verb: `Eraser.cls:325` and `nodes_edges.py:1555-1557` ("erase"), `LedgerRedact.cls:209` ("erase it before redacting"), `Ledger.cls:449` ("re-enable before committing"), `client.py:276-279`.
- C-19: values are strings and are compared exactly, as documented at `changeset.py:3-5` and `LedgerApply.cls:265` and `274`. A weight is checked with `$IsValidNum` at `LedgerApply.cls:445-448`.
- C-21: `Ledger.cls:192-210`, `LedgerStats.cls:65-88`, `LedgerRevision.cls:65-75`.
- C-22: `Ledger.cls:204`, `555`; `LedgerApply.cls:636`; `Eraser.cls:325`, `1358`; `LedgerRevision.cls:69`, `114`. No `$System.Status.IsError` or `IsOK` anywhere in scope.
- C-23: grepping `$Get(` in scope finds only locals and `%msg`.
- C-24: the only `SELECT TOP`, at `GraphStores.cls:308-309`, has no `ORDER BY`.
- C-25: `Ledger.cls:57`, `425`, `627`; `LedgerApply.cls:108`, `457`, `469`; `Eraser.cls:132`, `421`; `GraphStores.cls:254`; `LedgerRedact.cls:339`. The only operands left unparenthesised are single calls or negated calls, such as `LedgerApply.cls:458`, `463` and `Eraser.cls:378`, `532`.
- C-26: `Ledger.cls:432`; `Eraser.cls:94`, `286`, `421`; `GraphStores.cls:310`. Spaces appear only inside argument lists or parentheses (`Eraser.cls:345`, `GraphStores.cls:254`).

## Per-file results

| File | Conventions checked | Deviations | Borderline / notes |
| --- | --- | --- | --- |
| Ledger.cls | C-3(nj), 4, 12, 14, 15, 18, 19, 21-26 | C-21: 1 | B-2 (559-565); B-5 (224, 252, 423) |
| LedgerApply.cls | C-4, 5, 6, 7, 8, 9, 14, 18, 19, 22, 25, 26 | C-14: 1 | B-1 (510, 689); B-2 (82, 137-139, 152, 340-345, 361-362, 657-664); R-4, R-7, R-9 |
| LedgerGenesis.cls | C-4, 14, 19, 22, 25, 26 | none | R-7 |
| LedgerStats.cls | C-14, 21, 22 | C-14: 1 | B-2 (57) |
| LedgerRevision.cls | C-12, 14, 21, 22, 25 | C-14: 1 | R-1 |
| LedgerRedact.cls | C-4, 12, 14, 18, 22, 25, 26 | none | B-5 (185); R-5 |
| Eraser.cls | C-4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 18, 22, 25, 26 | C-7: 3, C-8: 6, C-14: 1 | B-1 (439, 544, 874-885, 1278); B-2 (294-298, 838-841) |
| GraphStores.cls | C-9, 14, 24, 25 | C-9: 1, C-14: 1 | |
| changeset.py | C-2, 16, 19 | C-16: 1 | R-6 |
| client.py | C-2, 12, 15, 17, 18 | none | B-3 (483-487); R-10 |
| guard.py | C-2, 17 | C-17: 2 | R-8 |
| errors.py | C-2, 12, 18 | none | |
| `__init__.py` | C-2 | none | |
| `_engine/ledger.py` | C-2, 17 | C-17: 2 | |
| replay.py | C-2, 12, 17, 19 | C-17: 2 | B-4 (342-345); R-6, R-7 |
| export.py | C-2, 16, 17 | none | |
| nodes_edges.py:1473-1560 | C-11, 17, 18 | none | |

## Deviations (counted)

| # | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-01 | C-7 | Eraser.cls:240 | `Kill ^KG("label", tKey)` in EraseGraph is written directly, not through the module that owns the label store |
| D-02 | C-7 | Eraser.cls:580-585 | The node-by-node walk and `Kill` of `^KG("label", pKey, tL, tId)` skips `Adjacency.RemoveLabel` (Adjacency.cls:778-787) |
| D-03 | C-7 | Eraser.cls:793 | `Kill ^KG("label")` in EraseAll skips `Adjacency.RemoveAllLabels` (Adjacency.cls:789-795) |
| D-04 | C-8 | Eraser.cls:239, 241-242 | EraseGraph kills `^KG("prop"/"deg2p"/"deg2p_exact", tKey)` directly |
| D-05 | C-8 | Eraser.cls:453-454 | EraseEdges kills `^KG("deg2p"/"deg2p_exact", tKey)` directly |
| D-06 | C-8 | Eraser.cls:579 | EraseIdSet kills `^KG("prop", pKey, tId)` directly |
| D-07 | C-8 | Eraser.cls:612-613 | EraseIdSet kills `^KG("deg2p"/"deg2p_exact", pKey)` directly |
| D-08 | C-8 | Eraser.cls:794-795, 801-803 | EraseAll kills `^KG("prop")`, `("labelset")`, `("deg2p")`, `("deg2p_exact")` and `("deg2p_exact_merged")` directly |
| D-09 | C-8 | Eraser.cls:1327 | ForgetNodes kills `^KG("prop", pKey, tId)` directly |
| D-10 | C-9 | GraphStores.cls:195-204, 216-239 | Digest walks every scoped global through indirection (`$Name(@tStore@(tKey))`, `$Query`), including the temporal stores listed at 87-91: an ad-hoc read outside TemporalIndex |
| D-11 | C-14 | LedgerApply.cls:4-5 | The header says the class "maintains adjacency via Graph.KG.EdgeScan"; the code uses `Graph.KG.Adjacency` or the functional index (508-514, 561-563, 688-689) |
| D-12 | C-14 | Eraser.cls:14-16 | The header says the class "derives the list from [GraphStores] rather than restating it". The class never calls GraphStores; it restates the tables inline (130-224, 551-589, 759-781), and a source-text test compares the two lists (tests/unit/test_eraser_inventory_coverage.py:1-12) |
| D-13 | C-14 | GraphStores.cls:10-12 | The header says "Two consumers read it: ... GraphVerify ... and the Eraser" and "No consumer may keep its own list". The Eraser does not read it and keeps its own list (D-12), and Digest calls itself "the third consumer" (173-175) |
| D-14 | C-14 | LedgerStats.cls:2 | The header says "Exactly one row (ID = 1)"; the IdKey is LedgerName (48), and the row is opened as `"default"` (53) |
| D-15 | C-14 | LedgerRevision.cls:2 | The header says rows are "Written only by Graph.KG.Ledger.Commit"; the genesis row is written by Enable (Ledger.cls:304→538-554), and the redaction revision by LedgerRedact (LedgerRedact.cls:437) |
| D-16 | C-16 | changeset.py:334-335 | The docstring says `"insert" (fail if key exists)`. In the glossary, an insert at coordinates already in use "changes nothing ... and is counted" (CONTEXT.md:173-177; TemporalIndex.cls:62-75) |
| D-17 | C-17 | guard.py:43-56 | `except Exception: meta = _ABSENT`: a failed probe turns into "never-enabled", so the strict check that gates structural writes says nothing and lets them through. The module docstring (5-6) documents this fail-open as intended |
| D-18 | C-17 | guard.py:82-86 | `except Exception: pass` around the counter write `Count(rej_strict_block)` |
| D-19 | C-17 | _engine/ledger.py:72-77 | `except Exception: return` skips the strict-mode check on write paths (e.g. nodes_edges.py:1513, 1553) |
| D-20 | C-17 | _engine/ledger.py:82-86 | `except Exception: return False`, exactly the pattern the rule forbids, used on temporal write paths (_engine/temporal.py:304-306, 384) |
| D-21 | C-17 | replay.py:816-819 | `except Exception: pass` around `RecordVerify`, which writes ledger_stats (Ledger.cls:192-210) |
| D-22 | C-17 | replay.py:839-842 | The same, on the main verify path |
| D-23 | C-21 | Ledger.cls:242-248 | PurgeAll throws away the `%Status` of both `%KillExtent` calls and returns `$$$OK`; it never sets `tSC` |

## Candidate findings (inspected-grade, not runtime evidence)

Lane triage against the audit's findings (`findings/audit/*.json`): candidate 1 is F-0801 (its fail-open half; the
probe-failure path is upstream-tested as intended, `intent-a-hd0801-unit-ledger-guard`), candidate 2 is F-0511, and
reviewer note R-7 is in the family of F-C0450 (temporal marker spellings). Candidates 3-7 match no recorded finding;
they stay candidates (source reading only, S4 at most as read) and are not filed: each needs a live check before it
can be a finding.

1. **Strict mode lets writes through when its probe fails** (D-17, D-19, D-20; guard.py:43-56, 45-49, 75-80; _engine/ledger.py:72-87). If the `Meta` probe raises, the guard caches "never-enabled" for `TTL_SECONDS` (guard.py:20). `check_structural_write` then allows the write, and nothing is logged. As a result, a ledger in strict mode can take unrecorded writes. One aggravating detail: `_class_present`, once False (45-49), is never re-asked, because `refresh()` (34-36) resets only `_cached`.
2. **The `insert` mode on a ledger temporal edge does not fail as documented** (D-16). The docstring promises a failure; the write changes nothing instead. `InsertEdge` returns 1 whether or not it wrote (TemporalIndex.cls:62-64). `OpCreateTemporalEdge` therefore records `create_temporal_edge` anyway (LedgerApply.cls:635-639), and the commit succeeds. So the ledger can hold a record for a write that changed nothing.
3. **Ledger counters can silently go stale** (D-18, D-21, D-22). When `RecordVerify` or `Count` fails, nothing is reported. `stats()` and `status()` then show an old `last_verify_result`/`last_verify_ms`, or an undercounted `rej_strict_block` (client.py:542-575; _engine/ledger.py:59-65). Low severity.
4. **PurgeAll reports success after a partial reset** (D-23; Ledger.cls:242-248). If a `%KillExtent` fails, `^IVG.Ledger` is still killed, rows are left in the ledger tables, and the method returns `$$$OK`. This is an admin/test path. Low severity.
5. **An erase that removes only stale label entries may leave the Graph-Version Token unchanged** (D-02; Eraser.cls:580-585, 615-627). `Adjacency.RemoveLabel` bumps `^KG("__version")` (Adjacency.cls:784-785). EraseIdSet bumps it only when `(tRemoved > 0) || tHadEdges` holds, so removing label entries that have no row and no edge changes the index without a bump (CONTEXT.md:116-119). I did not check whether any version-cached reader depends on `^KG("label")`.
6. **From B-2, not counted: a ledger `delete_node` can leave vectors behind** (LedgerApply.cls:357-362). The two embedding `DELETE`s are still unchecked, although the comment at 357-360 records that an unchecked status once left a deleted node's vectors behind "with nothing said about it".
7. **From B-2, not counted: the reification cascade can be skipped silently** (LedgerApply.cls:657-664). If the lookup fails, the cascade is skipped (658). Each reification `DELETE` is unchecked (664). The relationship delete goes ahead in both cases.

## Borderline (not counted)

- **B-1, direct reads of `^KG("out"/"in")` outside Adjacency**: LedgerApply.cls:510, 689; Eraser.cls:439, 544, 874-885, 1278. Read literally, ADR-0001:48-49 forbids them, and ADR-0008:25-26 says "every reader goes through the module". Against that, ADR-0011:12 limits the single-owner rule to set and kill; CONTEXT.md:224-227 describes the native executor "walking the Adjacency Index directly"; 26 `.cls` files under `iris_src/src/Graph/KG/` contain `^KG("out"`; and Adjacency has no reader that tests whether a tuple exists (Adj.cls:241 `HasEdges` covers only a source's out-edges). The documents disagree, so these reads are not counted.
- **B-2, ObjectScript versions of C-17**, where a failure is dropped and not reported: LedgerApply.cls:82, 137-139, 152, 340-345, 361-362, 657-664; Ledger.cls:559-565 (stats skipped when `Ensure` fails); LedgerStats.cls:57 (save status unchecked); Eraser.cls:294-298 and 838-841 (a `DROP` failure after the commit is swallowed; the comments in place call this deliberate). The rule's text names Python syntax, so these are not counted.
- **B-3**: client.py:483-487 catches `Exception` broadly on a write, but it does say what was not done: it logs at ERROR and returns the error in `CommitResult.post_commit_error`, whose contract is at client.py:94-97.
- **B-4**: replay.py:342-345 sends `SELECT TOP ... ORDER BY` from Python. The BRIEF.md rule is stated for ObjectScript.
- **B-5**: ADR-0016:12 and :24 say the classes read the recorded schema instead of naming `Graph_KG`. In fact they name `Graph_KG` (for example Ledger.cls:224, Eraser.cls:130, LedgerRedact.cls:185, 355), and the deploy rewrites them. That later decision is documented at specs/262-ivg-owned-sql-schema/research.md:8-12, CONTRIBUTING.md:65-66 and schema_name.py:6-7. The code follows the later documents; ADR-0016's text is out of date.

## Reviewer notes (taste or undocumented; not counted)

- **R-1**: ObjectScript indentation is mixed: tabs in Eraser.cls, GraphStores.cls and LedgerRevision.cls:65-75; four spaces in Ledger.cls, LedgerApply.cls, LedgerRedact.cls and LedgerRevision.cls:87-101. Concatenation is written both as `_` (GraphStores.cls:203) and ` _ ` (Ledger.cls), and values are returned with both `Quit` (Eraser) and `Return` (Ledger).
- **R-4**: The inline comment at LedgerApply.cls:498-499 names "Graph.KG.GraphIndex" as the functional index. The code checks `Adjacency.Indexed()`, whose index is `Graph.KG.AdjIndex` (Adjacency.cls:536-543); GraphIndex is `^NKG` (ARCHITECTURE.md:193).
- **R-5**: `ClearRevision` writes `Graph_KG.ledger_revisions` as a literal (LedgerRedact.cls:355, 369), while the rest of the class takes `pSchema` (154). It works only because the deploy rewrites the literal.
- **R-6**: `RESERVED_PROPERTIES` is defined twice (changeset.py:31, replay.py:16).
- **R-7, possible defect outside the style scope**: modules disagree on what counts as the temporal marker. LedgerGenesis.cls:62-71 and replay.py:617 accept only a JSON boolean, but LedgerApply.cls:468-469 and replay.py:800 accept the string `"true"`. A governed relationship carrying the qualifier `temporal="true"` would be adopted by `create_rel` instead of refused, and dropped from the replay while `read_canonical` keeps it.
- **R-8**: guard.py:13 puts a first-party import between standard-library imports. That is for isort; the tool run covers it.
- **R-9**: The hint "use mode=detach" (LedgerApply.cls:402) does not say that detach also deletes the node's live relationships. I read C-18 as met, because the caller is already deleting.
- **R-10**: client.py:352-357 maps every transport exception to `inconsistent` (LedgerInconsistencyError).

## Limitations

- **L-1**: AGENTS.md, CLAUDE.md and `.claude/` are all absent at the pin. C-21..C-26 come from a research brief at secondary authority (BRIEF.md:5), which quotes a CLAUDE.md that does not exist at the pin.
- **L-2**: Several aspects of ObjectScript style are not documented: indentation, `Quit` versus `Return`, the `p`/`t` prefixes, comment style, and class or method naming. "Follow ... the style of the neighbouring classes" (BRIEF.md:31-32) is too vague to judge. These aspects are not judged, which is a gap and not a pass.
- **L-3**: Python has no documented convention for docstrings, naming or comments beyond the tools (CONTRIBUTING.md:36-40; pyproject.toml:201-243). pyproject has no `[tool.ruff]` table, so ruff runs with its defaults; flake8 is the declared dev linter (pyproject.toml:115).
- **L-4**: C-3 (compile cleanliness) and C-20 (justified indirection) are not judged. The first needs an IRIS instance; the second needs design judgement.
- **L-5**: The documents disagree with each other in four places, and I do not resolve the conflicts here: B-1 (ADR-0001 and ADR-0008 against ADR-0011 and CONTEXT.md), B-5 (ADR-0016 against spec 262 R1), CONTEXT.md:195-196 ("the ledger owns the transaction boundary of a commit") against the 4.7.0 nesting in a caller's transaction (Ledger.cls:390-396; client.py:384-390), and TESTING_POLICY.md:291's Python-only wording (B-2).
- **L-6**: Several counted rules are invisible to tools. ADR-0002:27's grep lint for `^KG("tout"` cannot see D-10's indirection; the accuracy of headers (C-14) and of glossary meanings (C-16) has no checker; and no ruff rule selection is configured that would flag C-17's broad excepts.
