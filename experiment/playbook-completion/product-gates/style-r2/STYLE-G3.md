Module 08: 2 deviations of 1 convention (primary sources: 0 of 0; secondary BRIEF.md: 2)
Module 09: 2 deviations of 2 conventions (primary sources: 2 of 2; secondary BRIEF.md: 0)
Module 10: 25 deviations of 9 conventions (primary sources: 20 of 8; secondary BRIEF.md: 5)

<!-- markdownlint-disable MD013 -->

# 3.5-style round 2, group G3: modules 08, 09 and 10 against IVG's own documented conventions

"X deviations of Y conventions" means what it meant in round 1: the X counted deviations break Y different conventions. Secondary (C-21..C-26, `docs/dev/notes/research/alt-impl/BRIEF.md:38-42`, "Status: speculative", :5) is counted apart. Borderline items and reviewer notes are not counted.

- **Pin**: the product tree is `3eaa79cf77d3e0a879b2cced634cf2729d81499e`. `git diff --stat 3eaa79cf HEAD -- . ':(exclude)experiment'` is empty, so every `path:line` here is at the pin. Paths are relative to the audit root. Short forms: `.cls` names are under `iris_src/src/Graph/KG/` (`Cypher/` for 09) unless written `IVG/...` (`iris_src/src/IVG/`); `.py` names are under `iris_vector_graph/`.
- **Conventions**: C-1..C-26 as in `product-gates/STYLE.md` (C-1 not counted, C-3 and C-20 not judged); C-27..C-35 as defined in `style-r2/BRIEF.txt` from ADR-0005, 0006, 0007, 0009, 0010 with ARCHITECTURE.md:107, 0012, 0014, 0015 and 0016. I read each ADR's Decision (0001, 0002, 0003, 0005-0007, 0009-0012, 0014-0016), `CONTEXT.md` in full, `docs/architecture/ARCHITECTURE.md` in full, `TESTING_POLICY.md:285-297`, `constitution.md:105-180, 255-270`, `CONTRIBUTING.md:30-110`. No further production-code rule applying to these modules was found, so no C-4x was added (constitution VII governs tests of the translator, not its code).
- **Method**: each module's production files were taken from the "Scope:" line of `ontology/08-cypher-sql.md`, `09-native-executor.md` and `10-algorithms.md` (none has an "Also owns" line). For every file and every applicable convention I ran the convention's search over the whole file and read each hit in context (`type: ignore`; inline keys `= 0`, `$Char(1)`, `$ZStrip`; Set/Kill/Merge/`$Increment` of `^KG`; the temporal store names, `@`, `$Name`; `Kill ^NKG`; `^IVG.TemporalStructural`; "schema prefix"/"SQLUser"; every `except`; remedy messages; `TO_VECTOR`; `embedding_registry`; `^BM25Idx`; `deg`/`degp`/`degc`/`gen`/`degw`; `CypherCompiled`/`IVGC`/`DropAll`/`$System.OBJ.Delete`; `Graph_KG`; `SELECT TOP`; `$System.Status.Is*`; `$Get(` on properties; compound conditions; postconditional spacing). C-14: the header of every in-scope class was read and each factual claim checked against the class body. Files under ~3,000 lines were also read line by line (by the lead and four review forks of this reviewer, each given the same written judgement rules); every cited line was re-checked by the lead with `sed -n`/`grep -n` (one wrong fork citation, `paths.py:131/156`, was corrected to 22/47). `cypher/translator.py` (31,908 lines), `_engine/query.py` (4,545) and `stores/iris_sql_store.py` (4,279) are covered by the convention-driven sweep only, not line by line.
- **Judgement, as round 1**: a write of a `^KG` node outside its owners is C-8; a plain read is borderline (round-1 B-1: ADR-0011:12 limits single ownership to set and kill; CONTEXT.md:224-227 and :266-267 describe readers walking the index). A temporal-store read or write outside TemporalIndex is C-9. C-17 is applied to Python (embedded Python in a `.cls` included) on paths that change data, caches, counters and logs included; a broad catch that says what was not done is borderline (B-3); an ObjectScript `Catch` that drops a failure is borderline (B-2). A `Graph_KG` literal in a `.cls` is not a deviation (B-5). A class with no header is borderline (ARCHITECTURE.md:203 presumes a header; it does not require one). Writing the default graph's `^KG` key as the literal `0` is C-4 (ADR-0003:68; round 1 searched `Key = 0` as an inline derivation; `stores/iris_sql_store.py:2030-2034` itself says "Passing 0 from here would be a second implementation"); recognising `0` in a key read back from `^KG` is borderline (ADR-0003 names no key-to-name rule, GraphKey has no such method).
- **Counting unit**: one deviation per convention per site group: per method for C-8, C-17 and C-32; per class header for C-14; per file for a pattern repeated through a file (C-4 literal key, C-25, C-31, C-35). Every site is listed.

## Module 08: Cypher on the SQL path

| File | Lines | Coverage | Conventions applicable |
| --- | --- | --- | --- |
| cypher/`__init__`.py | 4 | full read | C-2, 35 |
| cypher/lexer.py | 534 | full read | C-2, 16, 17, 18 |
| cypher/parser.py | 1941 | full read | C-2, 16, 17, 18 |
| cypher/ast.py | 550 | full read | C-2, 16, 17 |
| cypher/translator.py | 31908 | convention sweep (not line by line) | C-2, 4, 8, 10, 15, 16, 17, 18, 19, 24, 27, 28, 30, 35 |
| cypher/merge_rows.py | 704 | full read | C-2, 17, 18, 19 |
| cypher/row_where.py | 276 | full read | C-2, 16, 17, 18, 19 |
| cypher/count_create.py | 125 | full read | C-2, 17 |
| cypher/read_only.py | 104 | full read | C-2, 16, 17, 18 |
| cypher/procedure_signatures.py | 109 | full read | C-2, 16 |
| cypher/algorithms/`__init__`.py, paths.py | 0, 204 | full read | C-2, 17, 35 |
| cypher/aql/`__init__`, ast, lexer, parser, translator .py | 34, 148, 190, 387, 270 | full read | C-2, 16, 17, 18 |
| _engine/query.py (all but the native lines 2063-2249, module 09) | 4545 | convention sweep | C-2, 4, 8, 16, 17, 18, 24, 35 |
| stores/iris_sql_store.py `execute_transaction` 1580-1819 only | 4279 | that method read in full | C-17, 18, 35 |
| operators.py | 146 | full read | C-2, 16, 17, 27, 28, 35 |
| sql/operators.sql | 154 | full read | C-15, 27, 35 |
| CypherFn.cls | 268 | full read | C-14, 15, 19, 21-26 |
| IVG/Percentile.cls | 55 | full read | C-14, 19, 21-26 |

Not applicable (searched, no hit in any module 08 file): C-5..C-7, C-9, C-11..C-13, C-29, C-31..C-34.

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-08-01 | C-25 (secondary) | CypherFn.cls:162 (IVGLISTGET) | `If firstChar = "[" \|\| (firstChar = "{")`: first operand of a compound condition not parenthesised (strict left-to-right evaluation happens to give the intended result) |
| D-08-02 | C-25 (secondary) | IVG/Percentile.cls:45 (SortArray) | `While j >= 0 && (arr.%Get(j) + 0 > key)`: first operand not parenthesised |

Conforming evidence: C-2 none in any file but `_engine/query.py:705`, justified by its comment at 704. C-14 `CypherFn.cls:1-8` (all 17 methods at 13-266 carry the IVG prefix; forwarders `SqlProcs.cls:87-92` and the rest of 17-97 use `CypherFn_IVG<Name>`; `$Char(0)` mapped at 16-17, 87, 217-219, 244-245), `Percentile.cls:1`. C-15 `translator.py:37`, 361 name the setting; 68, 349, 392 name SQLUser only as where an unqualified name resolves. C-16 `translator.py:257-262`, 291-295 (All-graphs read is the union, CONTEXT.md:38-42; `^NKG` has no graph dimension, :97-101). C-17 `_engine/query.py:1946-1967` (rollback and re-raise), `iris_sql_store.py:1811-1819` (rollback, `GraphWriteError` with the cause), `read_only.py:60-65` (fails closed), `_engine/query.py:247-249`. C-18 `translator.py:3056-3058` ("Run initialize_schema() to bring the functions and classes up to date"); `iris_sql_store.py:57-59` ("Use DETACH DELETE.", met as in round-1 R-9). C-19 `translator.py:18933-18940` (two stored properties compared by Cypher orderability, documented), 17857-17861 (stored boolean spellings), `merge_rows.py:629-637`, `Percentile.cls:43-45` with `translator.py:6145-6148` (`CAST(... AS DOUBLE)` first). C-21..C-24 have no instance (no `%Status` method, no `$Get` on a property, no SQL in either class); C-25 `CypherFn.cls:15`, 117; C-26 `CypherFn.cls:16-17`, 87, 217-219. C-27 every query vector is the two-argument form: `translator.py:2800`, 3235, 3295-3296, 28896, 28941. C-28 `operators.py:18-28` forwards `model_key` only. C-30 `translator.py:10338-10349` adopts a temporal edge's marked row before a per-row CREATE/MERGE insert. C-35 `translator.py:64-71` (`_current_prefix`: the engine's schema, else the module default, else `DEFAULT_SCHEMA`), 360-380 (`_table`), 386-397 (`_fn`); `iris_sql_store.py:1582` (`write_txn(..., self._ivg_schema, ...)`), 1613 (schema-agnostic DELETE detection); `cypher/algorithms/paths.py:22`, 47.

Borderline (not counted):

- B-08-1, C-17: `translator.py:9611-9622` and 9651-9657, inside `_create_resolve_prop_value` (the values a CREATE stores), catch `Exception` and fall through (the list item is kept and JSON-encoded at 9628; the scalar falls to `return v`). It is a translation fallback while building a write, not a failed change reported as success; the rule's text does not cover it. The other broad catches (454, 793, 8090, 10021, 11156, 21675, 24621, 25469-25484, 25536, 27868, 27902) are translation-time and change no data; 4339 and 7918 re-raise.
- B-08-2, C-35: `_engine/query.py:2618`, 3693, 4085 skip bound parameters that start with `"Graph_KG"` when guessing a var-length walk's source or target. Under another IVG Schema the filter keys on the wrong name; I found no bound parameter that carries a schema name, so whether it ever misclassifies is not shown, and the rule's wording (where objects live) does not cover a heuristic.
- B-08-3, C-4: `_engine/query.py:2408-2420` (`_edge_graphs`) maps a `^KG("out")` key back to a name inline (`"" if str(key) == "0"`). Key-to-name is not named by ADR-0003.
- B-08-4, C-8 (round-1 B-1): `_engine/query.py:2414` reads the top level of `^KG("out")` through the Native API.
- B-08-5, C-24 (round-1 B-4): Python-issued `SELECT TOP ... ORDER BY` at `translator.py:2919-2926`, 3327-3343, 4430, documented there as what IRIS requires for an ordered CTE.
- B-08-6, C-30: the literal-endpoint CREATE at `translator.py:10229-10247` has no marked-row adoption (a duplicate triple fails the query, F-0805), and 10342 documents two cases the adoption does not reach (multigraph MERGE; an undirected MERGE matching the reverse row). ADR-0009:13 names `create_edge`; a MERGE that matches is not a create.
- B-08-7, C-35: `sql/operators.sql:6`, 32, 51, 86, 106, 134 create routines with unqualified names. Setup does not load the file (F-0105 covers it), and ADR-0016:12 governs objects IVG creates.
- B-08-8, C-27: `sql/operators.sql:15`, 20 convert the query vector with one-argument `TO_VECTOR(queryInput)` into a `VECTOR(1000)` variable. ADR-0005:16 forbids only the three-argument form, for generated procedures; this file is neither generated nor loaded.
- B-08-9, B-2 (ObjectScript C-17): `CypherFn.cls:220-238` (IVGJSONSET) and 246-251 (IVGJSONREMOVE) `Catch { Return json }` inside the Cypher `SET r.k`/`REMOVE r.k` UPDATE of `rdf_edges.qualifiers` (`translator.py:12184-12192`, 12348-12356).

Candidate findings (inspected-grade, source reading only):

1. New candidate, from B-08-9 (not counted): **a relationship `SET`/`REMOVE` of a property changes nothing and reports success when the edge's qualifiers are not JSON** (`CypherFn.cls:220-238`, 246-251; `translator.py:12184-12192`, 12348-12356). The Catch returns the old text, so the UPDATE writes it back and no error is raised; F-C0849 shows a CREATE can store qualifiers that are not JSON, which makes the state reachable. S4, confidence medium on the code path, low on reachability. Grep (IVGJSONSET, JSONREMOVE, CY_JSON_SET, "not JSON") finds only F-C0849, the cause, not this symptom.

Reviewer notes (not counted): R-08-1 `translator.py:3272`, 28936 and 396 add `or "Graph_KG"` after `_current_prefix()`, which never returns "" (71): dead fallbacks. R-08-2 `_engine/query.py:117` returns the literal `"Graph_KG"` rather than `schema_name.DEFAULT_SCHEMA`. R-08-3 read-path catches that log at DEBUG and drop a filter or a lookup (`_engine/query.py:318`, 3311-3312, 3322-3323, 3475-3476; `_edge_graphs` returns [] at 2418-2419 and also stops at 10,000 graphs, 2413) change answers silently; C-17 covers only paths that change data. R-08-4, possible defect outside the style scope, unfiled: an identifier spelled like an internal token name is lexed as that token (`lexer.py:482`, `TokenType[upper_value]`), and `eat` does not advance past EOF (530-534), so `RETURN 1 AS eof, 2 AS b` may parse as `RETURN 1 AS eof` and drop the rest (traced in source only; grep TokenType/upper_value: no finding). R-08-5 `aql/translator.py:20` maps AQL `POW` to Cypher `sqrt`; `aql/parser.py:321` parses an index and discards it. R-08-6 `parser.py:1074`, 1096 comments say the default upper bound is 10, the code sets 100 at 1054. R-08-7 `cypher/algorithms/paths.py` has no production caller and its SQL has no graph predicate. R-08-8 `_engine/query.py:675-705` is annotated `Optional[IVGResult]` and documented to return an IVGResult, but returns a tuple sentinel. R-08-9 C-18 is met at `translator.py:3058` by "bring ... up to date", without the word "writes" that `schema_name.py:31-35` uses.

Limitations: L-08-1 translator.py, query.py and iris_sql_store.py are swept by convention, so a deviation of a convention that has no searchable form (C-16 wording, C-19 in an unmarked comparison) can be missed there. L-08-2 the translator's generated SQL was judged from its text, not run.

## Module 09: native executor

| File | Lines | Coverage | Conventions applicable |
| --- | --- | --- | --- |
| Cypher/Exec.cls | 1918 | full read | C-4, 5, 6, 7, 8, 9, 10, 14, 16, 18, 19, 21-26, 31, 32, 33, 35 |
| Cypher/Gen.cls | 642 | full read | C-5, 8, 9, 14, 16, 18, 19, 21-26, 31, 32, 33, 35 |
| Cypher/Props.cls | 120 | full read | C-14, 19, 22-26, 35 |
| Cypher/SortKey.cls | 153 | full read | C-14, 19, 25, 26 |
| IVG/CypherEngine.cls (ObjectScript and embedded Python) | 248 | full read | C-14, 17, 18, 23, 25, 35 |
| cypher/native_plan.py | 536 | full read | C-2, 16, 17, 18, 19, 35 |
| cypher/native_route.py | 123 | full read | C-2, 17 |
| cypher/native_shadow.py | 69 | full read | C-2, 16, 17 |
| _engine/query.py:2063-2249 (native branch of `_execute_parsed`, `_routed_sql`, `_cypher_shadow`, `_try_native`, `_names_mapped_label`, `_native_translation`, `_native_key`, `_run_native_plan`, `_shadow_compare`) | 4545 | those lines read in full | C-2, 16, 17, 35 |

Not applicable (searched, no hit): C-11..C-13, C-15, C-27..C-30, C-34. `engine.py` holds gate facts the module cites, not owns; not reviewed.

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-09-01 | C-14 | Cypher/Gen.cls:11-15 | The header gives `^IVG.CypherCompiled(hash)`'s fifth element as "built at"; `For` writes the time it set the entry pending (80), reads it as pending-since (76), and `Build` never sets it. It says a failed shape's error "was written to messages.log once"; the generator failure (84-87, "not written: ...") and `Build`'s `Catch` (216-218) record the status without logging (only 179 and 213 log) |
| D-09-02 | C-17 | IVG/CypherEngine.cls:102-106 | `except Exception: pass` drops a params JSON that does not parse; `QueryJson` then runs `execute_cypher` (108), writes included, with no parameters and does not say what was not done |

Conforming evidence: C-4 `Exec.cls:836`, 869, 902 (`GraphKey.ForIndex`). C-5 `Exec.cls:235`, 1082; `Gen.cls:308`. C-6/C-7/C-8: no Set, Kill, Merge or `$Increment` of any `^KG` node in Exec (27 references) or Gen (6); Exec writes only `^||IVG.*` and `^IRIS.Temp.IVG.Cypher`. C-9: the only indirect store subscripts are `"out"`/`"in"` (`Exec.cls:417-418`, 1071-1072; `Gen.cls:336`). C-10: no `^NKG` in scope. C-14 holds for `Exec.cls:1-9` (rows in `^||IVG.CypherOut` 59, 64, 1886; ReadPage 1902; Drop 1913; the "A" tag carries families A and B, `native_plan.py:78`, `Exec.cls:88`), `Props.cls:1-8` (checks 29-39, SQL fallback 64-71), `SortKey.cls:1-4` (`tests/unit/test_257_sort_key_class.py` exists), `IVG/CypherEngine.cls:1-13` (Local 27-33, Remote 35-53, Query 135-138). C-16 `Gen.cls:11` with Shape 114-131 (Plan shape, CONTEXT.md:238-241); `native_shadow.py:41-69`, `_engine/query.py:2226-2249` raise on a difference (Shadow mode, :234-236). C-18 `Exec.cls:40` ("redeploy the classes"); `native_plan.py:535`. C-19 `Exec.cls:924-925` and 989-994 (equality as strings, ranges by `]]`, as SQL compares `rdf_props.val`, documented), `SortKey.cls:81-97`. C-21 `Gen.cls:163-221` (Build), `Exec.cls:540-553`. C-22 `Gen.cls:205-206`; no `$System.Status.IsError/IsOK`. C-23 none. C-24 `Exec.cls:1101` (`SELECT TOP` without ORDER BY). C-25 `Exec.cls:123`, 1049; `Gen.cls:71`, 171. C-26 `Gen.cls:73-76`. C-31/C-32 `Exec.cls:1052`, 1055 and generated `Gen.cls:316`, 320 read degree through `Adj.Cached`, which validates the generation (`Adj.cls:93-106`). C-33 `Gen.cls:70-76` runs an entry only when shape, stamp and class match, otherwise rebuilds (80-104); the stamp is rdf_props' compile time and the Exec and Gen build times (136-139, ADR-0014:21); `DropAll` 225-230; repo grep for CypherCompiled/IVGC/DropAll/`OBJ.Delete`/DeletePackage: only deploys call DropAll (`iris_vector_graph/schema.py:2939`, `scripts/enterprise-container.sh:348`). C-35 the `Graph_KG` literals in the classes (`Exec.cls:858`, 886, 1101; `Props.cls:66`) are deploy-rewritten (B-5). C-2 none.

Borderline (not counted):

- B-09-1, C-8 (round-1 B-1): all 27 `^KG` references in Exec (e.g. 235, 817, 1082, 1177-1179) and 6 in Gen (e.g. 308, 336) are reads; CONTEXT.md:224-227 describes this executor walking the index directly.
- B-09-2, C-31: `Exec.cls:411-438` (Fanout) and 759-810 (LabelStats) count out- and in-entries inline as cost estimates that also return sample neighbours; not a degree answer, and Adj has no in-direction helper.
- B-09-3, C-31: when `Adj.Cached` misses, a tallied hop counts out entries inline as the child keys other than `"#"` (`Exec.cls:1206-1218`, generated `Gen.cls:384-389`); this equals the out-degree only for an unchecked far node, and the read-only `Adj.Count` exists.
- B-09-4, C-4: `Exec.cls:226`, 740, 878 `$Select(g = 0: "", 1: g)` recover a graph name from a key read back (recognition, not derivation; exact today because `GraphKey.Validate` refuses `"0"`).
- B-09-5, C-14: `Exec.cls:5-6` says "Any error is thrown to the caller", while a `Gen.For` failure is interpreted (157-166) and NamedEnds' SQL error falls back to the walk (1110); ADR-0014:19-20 makes interpreting a failed compile the rule, so the wording is over-broad rather than false.
- B-09-6, C-33: `Gen.cls:214` deletes the class of a shape that failed to compile; ADR-0014:23 names only a deploy and DropAll, but the class never compiled and Gen is the owner (:16).
- B-09-7, B-2: `Gen.cls:95-98` empty `Catch` around `Job` (comment 93-94: retried after 120 s); `Gen.cls:214` `Delete`'s status unchecked.
- B-09-8, B-3: `IVG/CypherEngine.cls:107-111` catches broadly but returns the error in the documented `{columns, rows, error}` result (:12, :110).
- B-09-9, C-18: `IVG/CypherEngine.cls:237` SmokeTest prints "running InitSchema()..." without saying it writes; it announces a call, not a remedy.
- B-09-10, C-35: `native_plan.py:533` names "a Graph_KG table" in a gate reason while the check reads the engine's schema; text only.

Candidate findings:

1. New candidate (D-09-02): **`IVG.CypherEngine.QueryJson` runs a query without its parameters when the params JSON does not parse** (`IVG/CypherEngine.cls:102-108`). The caller's parameters are dropped with nothing reported and the query, a write included, runs as if none were given; the class's own error contract (:12, :110) is not used. S4, confidence medium (what the translator does with an absent `$param` was not traced). Grep CypherEngine/QueryJson/params: only F-C0940, which is about `Scalar`.
2. D-09-01 is documentation only. Gen behaviours already filed (F-0901..F-0905, F-C0901, F-C0948) are not duplicated here.

Reviewer notes (not counted): R-09-1 `Exec.cls:31-32` documents Run's `pParams`, which the body never reads; `_engine/query.py:2207` sends it. R-09-2 `Gen.cls:1` says "routines of their own"; line 5 and ADR-0014:12 say classes. R-09-3 parallel-edge multiplicity is coded twice: child keys other than `"#"` (`Exec.cls:1208-1214`, `Gen.cls:384-389`) against the `"#"` value (`Adj.cls:118-119`). R-09-4 `IVG/CypherEngine.cls:225-229` IsReady answers 0 on any exception, after which SmokeTest runs InitSchema, which writes. R-09-5 the `execute_cypher` docstring (`_engine/query.py:1752-1754`) says a supported read "runs over ^KG"; the speed route can answer it on SQL.

Limitations: L-09-1 the generated `IVGC.P<n>` code was judged from the generator's text, not from a compiled class. L-09-2 in `_engine/query.py` only 2063-2249 is this module's.

## Module 10: algorithms

| File | Lines | Coverage | Conventions applicable |
| --- | --- | --- | --- |
| Algorithms.cls | 188 | full read | C-4, 5, 6, 8, 14, 19, 22, 25, 26, 31 |
| PageRank.cls | 532 | full read | C-4, 5, 8, 14, 19, 22, 24, 25, 26, 31 |
| PageRankEmbedded.cls (embedded Python) | 171 | full read | C-14, 17, 35 |
| Centrality.cls | 175 | full read | C-4, 5, 8, 14, 16, 25, 26, 31, 32 |
| Communities.cls | 705 | full read | C-10, 14, 25, 26 |
| Subgraph.cls | 414 | full read | C-4, 5, 8, 14, 22, 25, 26, 31 |
| Traversal.cls | 185 | full read | C-14, 21 |
| TraversalBFS.cls | 695 | full read | C-4, 5, 8, 14, 25, 26 |
| TraversalKHop.cls | 244 | full read | C-4, 5, 8, 14, 25, 26, 31, 32 |
| TraversalPaths.cls | 506 | full read | C-4, 5, 6, 8, 9, 10, 14, 19, 21-26, 31, 35 |
| VarLength.cls | 567 | full read | C-4, 5, 6, 8, 9, 14, 21-26, 31, 35 |
| NKGAccel.cls | 241 | full read | C-4, 5, 8, 10, 14, 18, 22, 25, 26 |
| NKGAccelAdjacency.cls | 255 | full read | C-5, 8, 10, 14, 25, 26, 31 |
| NKGAccelCentrality.cls | 757 | full read | C-10, 14, 18, 21, 22, 25, 26, 31 |
| NKGAccelLoader.cls | 140 | full read | C-8, 10, 14, 18, 25, 26 |
| NKGAccelTraversal.cls | 632 | full read | C-4, 5, 6, 8, 9, 10, 14, 21-26, 31 |
| ArnoAccel.cls | 442 | full read | C-4, 5, 8, 10, 14, 16, 21, 22, 25, 26, 31 |
| AlgoCache.cls (shared with 04) | 68 | full read | C-4, 14 |
| _engine/algorithms.py | 1821 | full read | C-2, 4, 8, 9, 10, 15, 16, 17, 18, 24, 31, 35 |
| stores/arno_bridge.py | 931 | full read | C-2, 4, 5, 8, 15, 16, 17, 18, 21-26 (embedded ObjectScript), 35 |
| arno_readers.py | 280 | full read | C-2, 16, 17, 18 |
| _arno_gate.py | 196 | full read | C-2, 16, 17 |
| algo_cache.py (shared with 04) | 64 | full read | C-2, 4, 16 |
| stores/iris_sql_store.py, the algorithm routing and cache parts (read in context: 1-110, 540-600, 765-1110, 1846-1860, 2021-2090, 2231-2567, 3103-3200, 3370-3580, 3737-3880; grep-swept: the rest) | 4279 | convention sweep | C-2, 4, 8, 9, 10, 16, 17, 18, 31, 32, 35 |

Not applicable (searched, no hit): C-9 (no temporal store named, directly or through `@`/`$Name`/`$Query`), C-11..C-13, C-27..C-30, C-33, C-34. TraversalBuild and GraphIndex (the `^NKG` builder and helpers) are module 04's (`ontology/04-adjacency.md:5-14`).

| ID | Conv. | Location | What deviates |
| --- | --- | --- | --- |
| D-10-01 | C-4 | Algorithms.cls:12, 95 | WCCJson and CDLPJson write the default key inline (`Set pGraph = 0`) |
| D-10-02 | C-4 | PageRank.cls:410 | PageRankGlobalJson: `Set pGraph = 0`; the same class derives the key through ForIndex at 178 |
| D-10-03 | C-4 | Subgraph.cls:8, 180 | `Set pGraph = 0`, two lines above a comment (9-10) that cites ADR-0003's "one derivation" for the SQL name |
| D-10-04 | C-4 | TraversalKHop.cls:15-22, 30, 69, 137, 218, 229 | `^KG("degw", 0)`, `^KG("degc", 0, ...)`, `Adj.Degree(0, ...)` and `Set pGraph = 0` throughout |
| D-10-05 | C-4 | stores/arno_bridge.py:621-638, 712-742 (Native API), 786-833 (generated ObjectScript) | The `^KG` default key is the literal `0` in Python walks and in the ObjectScript it generates |
| D-10-06 | C-5 | NKGAccelTraversal.cls:64, 68, 148, 152, 204 | The Else branches of KHopNeighbors, KHopNeighborsSorted and RandomWalkJson read `^KG("out", node, pred, dst)` with no graph key first (ADR-0001:9, :48); the header (3-8) admits the legacy layout |
| D-10-07 | C-8 | ArnoAccel.cls:299-302 | `BumpVersion` runs `$Increment(^KG("__version"))`, the Graph-Version Token that Adjacency moves (ADR-0008:16-18; ADR-0011:12-17, :29) |
| D-10-08 | C-8 | NKGAccelTraversal.cls:614, 627 | `Build2HopExact` kills and sets `^KG("deg2p_exact_merged")` outside the store's owners (ADR-0001:48-49 as amended by ADR-0011:7, :29) |
| D-10-09 | C-14 | Centrality.cls:4-8, 12, 14, 16-23 | Lists BetweennessJson and ClosenessJson, which exist nowhere in `iris_src` (the class has only DegreeCentralityJson, 40); gives `^KG("in", 0, ...)` where the code reads `pGraph` (62, 96, 110, 128, 136); says sources come from `Adj.NextSource` where 56 walks `^KG("out")`; lists scratch `^\|\|BC.*`, `^\|\|CL.*`, `^\|\|EIG.*` the class never uses, and omits `^\|\|CENTNODES` (53-69); its `^IVG.warnings` log is written by `stores/iris_sql_store.py:3446-3448`, not this class |
| D-10-10 | C-14 | Communities.cls:3, 12 | "Four pure-ObjectScript algorithms ... no embedded Python": ClosenessJsonPy (543) and LeidenJsonPy (615) are `[ Language = python ]` and LeidenJsonAuto (698-703) prefers the Python one (ARCHITECTURE.md:70 lists both); "sorted by descending group size" is false for TriangleCount (88) and KCore (165) |
| D-10-11 | C-14 | NKGAccel.cls:3 | "Full-graph algorithms export adjacency for Rust consumption": its full-graph algorithms (196-238) delegate to NKGAccelCentrality, which runs them in ObjectScript over `^NKG` (NKGAccelCentrality.cls:4-8, 95, 220) |
| D-10-12 | C-14 | ArnoAccel.cls:2-3, 5 | The cache is the namespace-wide `^ArnoKG(gname, "graph_json")` (305-315), not a process-private `^\|\|ArnoKG.JSON...`, and the readers are passed `"^KG"` (265); "All methods fall back to pure ObjectScript on failure", but CallFn throws (170, 172) and KhopSampleJson answers "arno unavailable" (408-414) |
| D-10-13 | C-17 | stores/arno_bridge.py:403-410 | `except Exception:` around `_ensure_zf_call_function` (CREATE OR REPLACE FUNCTION through `_create_routines`, 106-134) caches `available=False`, returns False and logs nothing |
| D-10-14 | C-17 | stores/iris_sql_store.py:1013-1020 | Two adjacent `except Exception: pass` around `ArnoAccel.Load` and `NKGAccel.Load`, which write `^ArnoAccel("lib_path")` (ArnoAccel.cls:117) |
| D-10-15 | C-17 | stores/iris_sql_store.py:1064-1066 | `_detect_arno`'s outer `except Exception:` turns any failure, the loads included, into "Arno unavailable" with no log line |
| D-10-16 | C-17 | stores/iris_sql_store.py:3442-3450 | `except Exception: pass` around the write of the durable warning `^IVG.warnings("centrality", ...)` |
| D-10-17 | C-31 | PageRank.cls:233-248, 414-428 | Run (with exclusions) and PageRankGlobalJson count out-degree inline from `^KG("out")` with Multiplicity instead of `Adj.Degree` (ADR-0010:12-13) |
| D-10-18 | C-32 | Centrality.cls:80, 91, 107, 123, 133 | While `Adj.AllWarm` holds, reads `$ListGet($Get(^KG("degc", g, node, key)), 2, 0)` with no check against `^KG("gen")`, a missing entry counting 0 (ADR-0012:13-14, :17); the `degw` stamp is documented only in a method comment (Adj.cls:197-204) |
| D-10-19 | C-32 | TraversalKHop.cls:13-21 | KHopCount inlines AllWarm ("read inline: no call") and reads `^KG("degc", 0, ...)` unvalidated, while its doc (4-7) calls the count "generation-validated" |
| D-10-20 | C-35 | PageRankEmbedded.cls:15, 23 | Embedded-Python SQL names `nodes` and `rdf_edges` with no schema; the deploy rewrites only `Graph_KG` literals (`schema_name.py:6-7`), so they resolve outside the IVG Schema |
| D-10-21 | C-25 (secondary) | TraversalBFS.cls:177, 185 | `If direction = "out" \|\| (...)`: first operand not parenthesised |
| D-10-22 | C-25 (secondary) | TraversalKHop.cls:40, 57 | `If dstIdx = "" \|\| '##class(...)...`: first operand not parenthesised |
| D-10-23 | C-25 (secondary) | NKGAccelAdjacency.cls:80 | `If predicatesJson '= "[]" && (...)` |
| D-10-24 | C-25 (secondary) | NKGAccelTraversal.cls:477, 500 | `If direction = "out" \|\| (...)`, `If direction = "in" \|\| (...)` |
| D-10-25 | C-25 (secondary) | TraversalPaths.cls:10, 29, 45, 184, 267 | Five compound conditions in ShortestPathJson, DFSPaths and DijkstraJson with the first operand bare |

Conforming evidence: C-2 `stores/iris_sql_store.py:567`, justified at 566; no other. C-4 `PageRank.cls:178`; `Centrality.cls:47`; `TraversalBFS.cls:47`, 112, 382; `TraversalPaths.cls:7`, 119, 264, 383; `VarLength.cls:54`; `ArnoAccel.cls:324`; `AlgoCache.cls:30`, 48, 56; `algo_cache.py` passes the graph name; `iris_sql_store.py:2030-2034`. C-5 every keyed read, e.g. `Centrality.cls:96`, `TraversalKHop.cls:222`. C-6/C-7: no class sets or kills `out`, `in` or `label`. C-10: no `Kill ^NKG`; the centralities call `TraversalBuild.EnsureNKG` (`NKGAccelCentrality.cls:8`, 97, 355); the only Python `.kill(` is the `^ArnoKG` probe (`_engine/algorithms.py:126`). C-14 holds for `Algorithms.cls:1-2`, `Traversal.cls:2-7` (every method is a delegator), `AlgoCache.cls:1-13` (Eraser kills the cache at `Eraser.cls:249`, 809, 1052), `NKGAccelAdjacency.cls:1-5`, `NKGAccelTraversal.cls:3-8`, `VarLength.cls:1-7`. C-16 `arno_readers.py:3-8` (Owner as reference and fallback; the proof "never by hand", CONTEXT.md:256-280) and 215 ("the version string is not read", :274-275). C-17 handled: `stores/arno_bridge.py:480-486` re-raises with `from`; `_engine/algorithms.py:370-378`. C-18 `_engine/algorithms.py:121-124` ("it writes a work area"), 164-166 ("Run initialize_schema() to deploy them"); `iris_sql_store.py:1063`; `NKGAccelLoader.cls:134`. C-19 `PageRank.cls:79-83` (`$IsValidNum`); `TraversalPaths.cls:329-331`. C-21 `Traversal.cls:16-24`; `VarLength.cls:342-396`. C-22 `PageRank.cls:103`; `ArnoAccel.cls:170`, 172. C-23, C-24 none (only `PageRank.cls:138`, ORDER BY without TOP). C-25 `PageRank.cls:79`, `VarLength.cls:249`. C-26 `PageRank.cls:65`, `VarLength.cls:243`. C-31 `PageRank.cls:227`, `Subgraph.cls:208` call `Adj.Degree`; `TraversalKHop.cls:221`, 230, 238-243 check a Rebuilt store's stamp (CONTEXT.md:109-114); `^NKG(-3)` is a documented Rebuilt store (ARCHITECTURE.md:124). C-35 `_engine/algorithms.py:187`, 414, 453 (`self._t()`); `iris_sql_store.py` passes `self._ivg_schema`; `Graph_KG` literals in `TraversalPaths.cls:1`, `VarLength.cls:3` are B-5.

Borderline (not counted):

- B-10-1, C-14: no class header in PageRankEmbedded, TraversalBFS, TraversalKHop, TraversalPaths, NKGAccelCentrality, NKGAccelLoader.
- B-10-2, C-31: sources enumerated inline with `$Order(^KG("out", g, s))` rather than `Adj.NextSource`: `Algorithms.cls:15-20`, 98-103; `Centrality.cls:55-59`; `PageRank.cls:413-415`; `ArnoAccel.cls:328`, 345 (ADR-0010:5 says implementation pending; the shipped helper is NextSource).
- B-10-3, C-31: in-degree counted inline from `^KG("in")` (`Centrality.cls:93-139`; `PageRank.cls:253-275`): ADR-0010 and CONTEXT.md:103-104 define Degree as outgoing, and no in-degree helper exists. `VarLength.cls:513-522` counts one triple's parallel edges, not a node degree.
- B-10-4, C-8 (round-1 B-1): reads of `^KG` in every class but Traversal and AlgoCache (e.g. `TraversalPaths.cls:48`, `VarLength.cls:136-141`, `TraversalKHop.cls:222`, 231, `ArnoAccel.cls:307`) and through the Native API (`stores/arno_bridge.py:621-742`; `iris_sql_store.py:1853-1856`).
- B-10-5, C-5: `^KG("deg2p_exact_merged", s, p)` has no graph key on purpose (`NKGAccelTraversal.cls:622-626`); ADR-0001:9 says every `^KG` global is keyed, but ARCHITECTURE.md:102 documents the unkeyed `^KG("labelset", hash)`.
- B-10-6, C-4: `NKGAccel.cls:219` (`Continue:tKey=0`) and `iris_sql_store.py:1856` (`str(first) == "0"`) recognise the default key in a key read back.
- B-10-7, C-14: `NKGAccelTraversal.cls:1-8` omits its `^KG` write (614, 627); an omission, not a false claim.
- B-10-8, B-2: `ArnoAccel.cls:128-132` (Load returns 0 after recording `lib_path` at 117), 411-412, 424-425, 437-438 (empty Catch around CacheGraphJson, which writes `^ArnoKG`); `NKGAccelTraversal.cls:584-588`, 603-607.
- B-10-9, B-3: `iris_sql_store.py:985-987` (`AlgoCache.Put` failure logged by `_log_cache_store_failure`, 76-86, saying the answer is not cached); `stores/arno_bridge.py:392-396` (WARNING naming what was not loaded).
- B-10-10, B-4: `_engine/algorithms.py:411-415` sends `SELECT TOP ... ORDER BY node_id` from Python.

Candidate findings:

1. Existing **F-0406** (D-10-18, D-10-19): clearing the degree cache alone gives zeros while the warm stamp holds; ADR-0012:17 calls the clear safe.
2. Existing **F-C1040** (D-10-07): `ArnoAccel.BumpVersion` moves the adjacency module's Graph-Version Token.
3. Existing **F-1013** (D-10-20): PageRankEmbedded is deployed, its unqualified SQL resolves outside the IVG Schema.
4. Existing **F-1007** (from B-10-3): degree centrality counts parallel edges on out-edges but not in-edges.
5. New candidate (D-10-13): **a failed Arno wrapper DDL is reported as "library not available", cached for the connection and logged nowhere** (`stores/arno_bridge.py:403-410`, 106-134). The connection never tries Arno again and the later error names the wrong remedy (library path); answers stay right through the fallback, slower. S4, confidence high on the code path. Related to F-C1001 (the same DDL on a read path), which does not record the masking. Grep: arno_available, `_ensure_zf_call_function`, ivg_arno_zf.
6. New candidate (D-10-14, D-10-15): **`_detect_arno` turns a failed `ArnoAccel.Load`/`NKGAccel.Load` into "Arno off" with no log line** (`stores/iris_sql_store.py:1013-1020`, 1064-1066). An unloadable or unrecordable `IVG_ARNO_LIB` leaves every algorithm on its Owner silently. S4, confidence medium. Grep: `_detect_arno`, ArnoAccel.Load, lib_path (F-1002 names `_detect_arno` for another reason).
7. New candidate (D-10-06): **before `^NKG("$meta")` exists, NKGAccel's k-hop and random walk read the legacy unkeyed layout and answer only the seed** (`NKGAccelTraversal.cls:20-22`, 61-77, 145-153, 189-205; `NKGAccelLoader.cls:8-11`). Reachable only in a namespace never synced or built; nothing reports it. S4, confidence low to medium. Family of F-1002 (random_walk), not covered by it.
8. Not candidates: D-10-16 (the skipped source is still reported in the result's `_meta`), the C-4 group (the methods are documented as default-graph only), the C-14 headers and C-25.

Reviewer notes (not counted): R-10-1 possible defect outside the style scope: `Subgraph.cls:207-226` PPRGuidedJson divides by `Adj.Degree` (which counts parallel edges) but shares rank once per distinct `(p, o)`, and keeps rank at a dangling node; no production caller; no finding (grep PPRGuided). R-10-2 `TraversalBFS.cls:273-277` escapes `"` twice in BFSFastJsonDirect; no finding. R-10-3 read-path catches that widen a walk on malformed filter JSON: `Subgraph.cls:32-33`, 300-301; `TraversalBFS.cls:218-222`; `NKGAccelAdjacency.cls:81`; `NKGAccelTraversal.cls:442-446`. R-10-4 stale method comments (not class headers): `Centrality.cls:50-51`; `Subgraph.cls:131`; `Communities.cls:541-542`; `TraversalKHop.cls:4-7`; `_engine/algorithms.py:244`, 277-278, 1085-1086. R-10-5 `NKGAccel.cls:12-105` holds about 90 lines of `///` text attached to no member, describing removed methods. R-10-6 ARCHITECTURE.md:71 says PageRankEmbedded is "called by nothing else in IVG"; F-1013 records that it is deployed and called. R-10-7 `algo_cache.py:15-16` says a label write changes subgraph's answer without moving the token, against the Graph-Version Token's definition (CONTEXT.md:116-119); harmless because subgraph is never cached. R-10-8 `iris_sql_store.py:565-568`'s "Python < 3.8" fallback is dead under `requires-python >=3.10`. R-10-9 `stores/arno_bridge.py:904` puts `lib_path` into SQL text as a literal where every other call binds it.

Limitations: L-10-1 `iris_sql_store.py` outside the ranges listed is grep-swept only; LazyKG, routine_record and host.py, which these paths call, are other modules' files and were not read. L-10-2 the `degw` stamp's soundness (`Adj.cls:197-217`) is module 04's; only its readers here were judged.

## Shared limitations and aspects with no documented rule

- L-1: AGENTS.md, CLAUDE.md and `.claude/` are absent at the pin; C-21..C-26 come from a research brief at secondary authority (BRIEF.md:5) that quotes a CLAUDE.md the pin does not have.
- L-2: no documented rule, so not judged (a documentation gap, not a pass): ObjectScript indentation (tabs and four spaces both occur in each module), `Quit` versus `Return`, `p`/`t` prefixes, comment style and comments attached to no member, class and method naming (e.g. `TraversalBFS.cls:6`, 15 lower-case `jsonNum`/`jsonEsc`), names of generated locals and work-area globals, embedded-Python style inside `.cls`, Python docstrings, naming and comments beyond the tools (CONTRIBUTING.md:36-40), the style of `sql/*.sql`, the AQL dialect, native-route thresholds.
- L-3: C-1 (left to the tool run), C-3 (needs IRIS) and C-20 (needs design judgement) are not judged. Source reading only: nothing was compiled, run or connected to.
- L-4: the documents disagree at B-1 (reads of `^KG`), B-5 (`Graph_KG` literals), B-10-5 (unkeyed `^KG` stores) and on whether ADR-0010's Sources helper is the shipped `Adj.NextSource` (B-10-2); these are not resolved here.
