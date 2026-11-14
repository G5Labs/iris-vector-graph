<!-- markdownlint-disable MD013 -->

# 3.5-style round 2, group G1: modules 01 (install and schema), 02 (graph identity), 03 (direct writes)

Module 01: 31 deviations of 6 conventions (primary sources: 31 of 6; secondary BRIEF.md: 0)
Module 02: 3 deviations of 3 conventions (primary sources: 3 of 3; secondary BRIEF.md: 0)
Module 03: 11 deviations of 5 conventions (primary sources: 10 of 4; secondary BRIEF.md: 1)

- **Pin**: product tree at `3eaa79cf`. The checkout's HEAD is `14678055`, and `git diff --stat 3eaa79cf HEAD -- . ':(exclude)experiment'` is empty. Paths are relative to ROOT. Observation only: nothing was run, compiled or connected to.
- **Method**: this follows BRIEF.txt and judges as round 1 did (`product-gates/STYLE.md`). Scopes come from the "Scope:" and "Also owns" lines of `ontology/01-install-schema.md`, `02-graph-identity.md` and `03-writes.md`. One reviewer did module 02 and the merge. Four review agents with the same brief and calibration did module 01 (two agents) and module 03 (two agents). Every in-scope file got the convention searches of BRIEF.txt step 2, and each hit was read in context. Files of 3,000 lines or fewer were read in full on their in-scope ranges, unless the row says sweep. Every cited line was checked with `sed -n` or `grep -n` at ROOT. The merger re-checked 25 deviation and candidate citations.
- **Calibration** (round 1's rulings, applied the same way to all three modules):
  - **C-17 (Python), deviation**: a broad catch (`except Exception`, bare `except`) on a path that changes data, whose handler neither raises nor hands the failure to the caller (`pass`, `continue`, `return False/None/0`, or a DEBUG/INFO line only). A probe that gates a write and fails silently also counts, as round-1 D-17 did. A comment that documents the swallow does not make it conform.
  - **C-17 (Python), borderline**: the handler does say what was not done, through a WARNING or ERROR naming the step, a result or status field, or a non-zero exit (round-1 B-3).
  - **C-17 (ObjectScript)**: the ObjectScript form of a swallow is B-2, not counted.
  - **C-18**: a message that sends the operator to a writing call without saying it writes is a deviation; the product test `tests/unit/test_upgrade_dry_run_read_only.py:21-25` checks for `\bwrites?\b`. If the caller is already doing that write, it is a note (round-1 R-9).
  - **C-35**: a `Graph_KG` literal in a deployed class is B-5, not a deviation. A Python literal is a deviation only when the SQL runs outside `SchemaCursor`/`in_schema`/`runs_in_ivg_schema`/`rewrite_schema_text`/`_t()`/`_ivg_schema`, where the schema can be non-default (schema_name.py:1-7, 404-540).
  - **C-8 (Python)**: a native `^KG` set or kill is a deviation; a read is borderline (B-1).
- **Conventions**: C-1..C-26 as in STYLE.md. C-1 is not counted (the tool run covers it); C-3 and C-20 are not judged; C-21..C-26 are secondary, counted separately. C-27..C-35 are as stated in BRIEF.txt; their ADR Decisions were read at `docs/adr/0005:7-19`, `0006:8-14`, `0007:3-12` (the decision is the paragraph at :5), `0009:8-14`, `0010:10-14`, `0012:10-16`, `0014:10-21`, `0015:10-29` and `0016:10-12`.
- **Added**: **C-40G1**, from `.specify/memory/constitution.md:262-263`: "Use the existing RDF schema (`nodes`, `rdf_labels`, `rdf_props`, `rdf_edges`, `kg_NodeEmbeddings`) unless a schema change is explicitly approved and documented."
  - Applies to: module 01's DDL and module 03's loaders.
  - Result: conforms on the part that can be judged. Every lasting table in the setup DDL (`schema.py`, `_engine/schema.py:143-300`) is described in `docs/architecture/ACTUAL_SCHEMA.md`. The one table the DDL creates and that document does not list, `nodes_new` (`schema.py:1594-1611`), is a transient staging table renamed to `nodes`. Approval cannot be judged from source.
  - No other production-code rule was found in the allowed sources.

## Module 01: install, schema and upgrades

### Files

| File | Lines | Coverage | Conventions applicable |
| --- | --- | --- | --- |
| iris_vector_graph/_engine/schema.py | 3,397 | sweep of 1-325, 421-833, 2097-2858 (setup_tables 234-240, the eight schema reads 440-534, setup helpers, initialize_schema chain, get_schema_visualization); 326-420, 834-2096 (VEC), 2859-3397 (ADJ and others) out of scope | C-2, 4-10, 13/34, 15-19, 27-35, 40G1 |
| iris_vector_graph/schema.py | 3,360 | sweep of 1-736, 904-1639, 1843-1949, 2030-2062, 2782-3360 (DDL, graph_id/ekey upgrade steps, deploy entry, 3.2.0 rescue); 2144-2781 (`get_procedures_sql_list` bodies) by grep and scripted pattern checks only | C-2, 4-10, 15, 17-19, 23-26 (embedded OS), 27-29, 31-33, 35, 40G1 |
| schema_name.py 540, _engine/class_deploy.py 367, routine_record.py 95, legacy_bodies.py 290, legacy_text.py 87, _engine/legacy.py 727 (all under iris_vector_graph/) | 2,106 | full read (legacy_bodies: code lines; the rest are hashes) | C-2, 15-19, 33, 35 |
| iris_vector_graph/legacy_manifest.py | 703 | sweep (code 1-18, 703; the entries are generated data, checked by structure) | C-2, 15, 16 |
| iris_vector_graph/migrations/{`__init__`, _commit, statements, upgrade}.py | 902 | full read | C-2, 16-18, 27, 35, 40G1 |
| iris_src/src/Graph/KG/SqlPrivilege.cls, SqlProcs.cls | 86, 227 | full read | C-8, 14, 21-26, 29, 35 (B-5) |
| scripts/deploy_production.py 112, deploy_objectscript.py 266, deploy_graph_tvfs.py 242, setup_iris.py 66, migrations/migrate_to_nodepk.py 851 | 1,537 | full read | C-17, 18, 19, 21-26 (OS text), 33, 35 |
| sql/** (14 files) | 1,540 | full read of 9 (graph_walk_tvf, operators_fixed, schema, fhir_bridges, rdf_reifications, migrations/001_add_nodepk_table, 002_add_fk_constraints, 001_rollback_nodepk, procedures/kg_PageRank); sweep of 5 (operators, globals_schema, graph_path_globals, migrations/000_base_schema_iris, fraud_sample_data) | C-5, 8, 10, 15, 24, 27, 31, 35 |

Of the sql/ files, only schema.sql, operators_fixed.sql (deploy_production.py:65), graph_walk_tvf.sql (deploy_graph_tvfs.py:182), and 001/002 nodepk (migrate_to_nodepk.py:646, 662) are used by anything in scope. The rest are reviewer notes only.

### Deviations (counted)

| ID | Conv. | Where | What deviates |
| --- | --- | --- | --- |
| D-01-01 | C-17 | iris_vector_graph/_engine/schema.py:592-602 | `_try_registry_ddl`: a broad catch on the registry ALTER/CREATE INDEX logs at DEBUG and returns False, which the only caller drops (566); the docstring (571-576) says the failure is "reported" |
| D-01-02 | C-17 | iris_vector_graph/_engine/schema.py:2700-2703 | `commit()` after TUNE TABLE inside `except Exception: pass` |
| D-01-03 | C-17 | iris_vector_graph/schema.py:663-704 | `ensure_indexes`: CREATE INDEX failures that are not tolerated become `status[name]=False` with a DEBUG line (690, 693-697, 700) or none (702-703); setup discards the status (_engine/schema.py:2514) |
| D-01-04 | C-17 | iris_vector_graph/schema.py:714-717 | A `tighten_graph_id_column` exception goes to DEBUG and into that discarded status |
| D-01-05 | C-17 | iris_vector_graph/schema.py:1077-1079 | `_at_234` probe failure: DEBUG and `return False`, which makes the caller add the triple-only `u_spo_graph` (1099-1102). A gating probe that fails toward the DDL |
| D-01-06 | C-17 | iris_vector_graph/schema.py:1160-1177 | `update_spo_unique_constraint`: `pass` on both DROP CONSTRAINTs (1163-1164, 1167-1168) and a silent `return False` on the ADD (1174-1177) |
| D-01-07 | C-17 | iris_vector_graph/schema.py:1180-1187 | `add_graph_id_index`: a CREATE INDEX failure becomes a silent `return False` |
| D-01-08 | C-17 | iris_vector_graph/schema.py:1190-1200 | `add_graph_oid_index`: same pattern |
| D-01-09 | C-17 | iris_vector_graph/schema.py:1217-1228 | `add_graph_id_column`: an ALTER failure becomes a silent `return False` |
| D-01-10 | C-17 | iris_vector_graph/schema.py:1289-1340 | `tighten_graph_id_column`: UPDATE/ALTER failures at DEBUG only (1291-1294, 1298-1302, 1323-1327, 1335-1336), in a result setup discards |
| D-01-11 | C-17 | iris_vector_graph/schema.py:1588-1589, 1627-1628, 1635-1636 | `add_graph_id_to_nodes` (recreate_pk path): `pass` on the pk probe that gates DROP TABLE nodes, on the commit and on the rollback |
| D-01-12 | C-17 | iris_vector_graph/schema.py:1882-1886 | `upgrade_val_column`: an ALTER failure other than "already"/"same" becomes a silent `return False` |
| D-01-13 | C-17 | iris_vector_graph/schema.py:2931-2934 | Deploy: `pass` around `%SYSTEM.OBJ.Delete(<stale edge class>, "ef-d")` |
| D-01-14 | C-17 | iris_vector_graph/schema.py:2937-2941 | Deploy: a `Gen.DropAll` failure is logged at DEBUG only (ADR-0014:19 says a deploy deletes every compiled class and entry) |
| D-01-15 | C-17 | iris_vector_graph/schema.py:3333-3334, 3342-3343 | `bootstrap_kg_global`: `except Exception: return False` twice, on the probes before BuildKG (the literal pattern the rule names) |
| D-01-16 | C-17 | iris_vector_graph/_engine/legacy.py:689-698 with 670-672 | `_drop`: a broad catch around DROP VIEW/FUNCTION logs at INFO and returns False; for a view the caller still sets `removed = True` |
| D-01-17 | C-17 | scripts/deploy_production.py:69-82 | A broad catch per DDL statement logs a WARNING naming only the file (the statement goes to DEBUG) and continues; the run ends "SQL files applied." with exit 0 |
| D-01-18 | C-17 | scripts/migrations/migrate_to_nodepk.py:157-160 | Bare `except: pass` around `SET SCHEMA Graph_KG`; the unqualified writes that follow then go to the connection's default schema |
| D-01-19 | C-17 | scripts/migrations/migrate_to_nodepk.py:317-320 | Bare except around the final commit rolls back with no log and no raise; the inserted count is still reported (323-333) |
| D-01-20 | C-35 | iris_vector_graph/_engine/schema.py:2689 with schema.py:196, 221-222 | `repair_ifind_helpers(cursor, conn=self.conn)` is called without `schema=`; the default "Graph_KG" is a bound parameter, which `SchemaCursor` does not rewrite (schema_name.py:415-416); the sibling calls pass it (_engine/schema.py:2697-2699) |
| D-01-21 | C-35 | iris_vector_graph/schema.py:656-657 | `DROP INDEX idx_props_key_val` names no schema, so the rewrite cannot qualify it |
| D-01-22 | C-35 | scripts/deploy_production.py:63-65, 97 | The SQL files run under `SET SCHEMA {--schema}` (default IRIS_SCHEMA or "User"), so operators_fixed.sql's procedures land outside the IVG Schema; schema.sql hard-codes Graph_KG; no record read, no rewrite |
| D-01-23 | C-35 | scripts/deploy_objectscript.py:72-101, 117-139, 148-154 | Creates `kg_PPR` unqualified; loads class sources with no `rewrite_schema_text` and no `refuse_other_record` (CONTEXT.md:23-24; CONTRIBUTING.md:65-66) |
| D-01-24 | C-35 | scripts/deploy_graph_tvfs.py:182, 203-212 with sql/graph_walk_tvf.sql:8-10, 18, 72, 96-97 | Unqualified DROP/CREATE PROCEDURE Graph_Walk and Graph_Neighborhood_Expansion, in the default schema |
| D-01-25 | C-35 | scripts/migrations/migrate_to_nodepk.py:155-160 | Hard-coded `SET SCHEMA Graph_KG` with no schema input; all its SQL is unqualified (e.g. 196-204, 294) |
| D-01-26 | C-33 | scripts/deploy_production.py:22-40 | Installs classes through `class_deploy.deploy_packaged_classes` and never runs `Gen.DropAll` (ADR-0014:19-20); the engine's entry does (schema.py:2935-2941) |
| D-01-27 | C-33 | scripts/deploy_objectscript.py:72-101 | Loads and compiles classes (LoadStream "ck", 93) and never drops IVGC classes or `^IVG.CypherCompiled` |
| D-01-28 | C-14 | iris_src/src/Graph/KG/SqlProcs.cls:1-3 | The header says each method forwards "under the SQL name callers have used since 4.5"; Txn_Begin/End/Undo (166-181, 4.6.4) and Prop_Set (183-190, 4.7.0) are later names |
| D-01-29 | C-16 | iris_vector_graph/_engine/schema.py:500-511 | `get_property_keys` says "of nodes with it ... Not graph-scoped", but joins `rl.s = rp.s` across graphs, against the glossary's node and all-graphs read (CONTEXT.md:38-42) |
| D-01-30 | C-16 | iris_vector_graph/_engine/schema.py:2776-2778 against 2790-2802, 2832-2841 | `get_schema_visualization` says "keys of one node" and "one edge's endpoints", but reads keys and labels by node ID across graphs |
| D-01-31 | C-18 | iris_vector_graph/_engine/schema.py:2434-2437 | The ValueError says "call store_embedding() first", a writing call, without saying it writes |

By convention: C-17 19, C-35 6, C-33 2, C-16 2, C-14 1, C-18 1. None from C-21..C-26.

### Borderline (not counted)

- **C-17, where a WARNING or the reply names the failure** (B-3 form):
  - _engine/schema.py:555-565, 621-628, 642-652, 764-795, 2468-2511, 2562-2563, 2591-2594, 2665-2671, 2676-2681. The base-DDL and bootstrap ones are F-0102 evidence.
  - schema.py:221-224, 246-259, 722-724, 727-729, 1150-1154, 1540-1547, 1565-1566, 1613-1621, 1629-1630, 1874-1876, 2904-2908 (see N-01-2), 2918-2922, 3084-3088, 3348-3357.
  - deploy_objectscript.py:153-159 and 166-168 (ERROR, then exit 1 at 251-253); deploy_graph_tvfs.py:105-117 (ERROR, then exit 1 at 228-230).
- **C-17, other**:
  - schema.py:1120-1123: a failed catalog read returns a false `{"status": "already at 234"}`. The failing statement is a read.
  - schema.py:3159-3160, 3172-3173, 3178-3180, 3224-3226: DDL swallowed inside the rescue restore; the next statement raises if it mattered, and that is wrapped at 3101-3109.
- **C-18**:
  - _engine/schema.py:2750-2753 ("Call engine.rebuild_kg()"): the effect is implied only by "not built".
  - schema_name.py:92-94 ("run initialize_schema() again" to upgrade): round 1 accepted effect verbs; the product regex would not.
- **C-24** (secondary, ObjectScript-only rule, B-4): `SELECT TOP ... ORDER BY` in generated LANGUAGE SQL (schema.py:2469/2481, 2513/2522, 2545/2578) and in sql/operators_fixed.sql:13-18, 20-27, 39-48, 63-69.
- **C-27**: sql/operators_fixed.sql:15, 22 use one-argument `TO_VECTOR(:queryVector)`. This is not the banned three-argument form; ADR-0005 is written for the generated procedures.
- **C-35**:
  - upgrade.py:57-58, 140, 149-152 and class_deploy.py:230, 327, 342 default to Graph_KG but take `schema=`; class_deploy refuses a mismatch at 357.
  - schema_name.py:26, 154-155 accept mixed case where ADR-0016:12 says `[A-Z][A-Z0-9_]*`; F-0110 records that the ADR lags.
  - SqlProcs.cls:200 is B-5.
- **C-16**: _engine/legacy.py:725-727 and CONTEXT.md:286-290 ("SQL that calls them keeps working") against `revoke_legacy_arno` (legacy.py:533-587), which setup runs (_engine/schema.py:2298) and which docs/migration/v4.6.0.md:143-145 documents. The documents disagree.

### Candidate findings

| # | Existing or new | Title | Evidence | Severity / confidence |
| --- | --- | --- | --- | --- |
| 1 | F-0101 | Legacy removal reports objects removed that may still be there (D-01-16) | _engine/legacy.py:670-672, 689-698 | existing |
| 2 | F-0105 | The sql/ files put objects outside the IVG Schema (D-01-22) | deploy_production.py:63-65, 97 | existing |
| 3 | F-0102 (extends it) | Setup discards ensure_indexes' status, so the upgrade-step failures of D-01-03..D-01-10 and D-01-12 never reach the reply | _engine/schema.py:2514 | existing |
| 4 | F-0107 | Unqualified DROP INDEX (D-01-21) | schema.py:656-657 | existing |
| 5 | F-0106 | get_property_keys mixes graphs (D-01-29) | _engine/schema.py:500-511 | existing |
| 6 | related to F-C0948 | A swallowed `Gen.DropAll` on deploy (D-01-14) | schema.py:2937-2941 | not new |
| N-01-1 | new | On a non-default IVG Schema, setup's iFind repair looks in Graph_KG, so the schema's helpers are not repaired and the reply's `ifind` is `{}` with no warning (D-01-20) | _engine/schema.py:2683-2689; schema.py:196, 221-222; schema_name.py:415-416 | S3 / low (does not establish that a deploy deletes the helpers there) |
| N-01-2 | new | If the 3.2.0 rescue staging fails, setup logs one WARNING and the deploy still deletes the class-owned rdf_edges with its extent; a partial staging passes the restore count check | schema.py:2904-2908, 2929-2932, 2960-2964, 3080-3091 | S2 / medium (the effect of "ef-d" was not observed) |
| N-01-3 | new | A registry route column (incl. `kind`, read at _engine/embeddings.py:400-407 and admin.py:337) can fail to be added with only a DEBUG line, and setup reports success (D-01-01) | _engine/schema.py:566, 592-602 | S4 / low |
| N-01-4 | new | The schema diagram lists keys and endpoint labels from another graph's node with the same ID (D-01-30; same pattern as F-0106) | _engine/schema.py:2776-2802, 2832-2841 | S4 / medium |
| N-01-5 | new (related to F-0105) | deploy_production splits each file on ';' and cuts every operators_fixed.sql procedure at its first inner ';'; failures go to WARNING and the run reports "SQL files applied." with exit 0 (D-01-17) | deploy_production.py:69, 72-82; sql/operators_fixed.sql:18, 27-29 | S4 / medium |
| N-01-6 | new (related to F-1013, F-0105) | deploy_objectscript's default class directory `iris/src` does not exist at the pin, so a default run loads no class; it creates kg_PPR outside the IVG Schema and is unchecked against the schema record, then logs "Deployment complete!" (D-01-23, D-01-27) | deploy_objectscript.py:49, 56-59, 72-101, 117-139, 148-154, 259 | S4 / high |
| N-01-7 | new | migrate_to_nodepk swallows a failed `SET SCHEMA` and a failed final commit (D-01-18, D-01-19, D-01-25) | migrate_to_nodepk.py:157-160, 317-320 | S4 / medium |

### Reviewer notes (not counted)

Stale text: _engine/schema.py:740-743 says the width parameter "is ignored/deprecated"; it was removed (schema.py:2144-2151), and ADR-0005:15-17 lags the same way. schema.py:70-76 and 3076-3078 say "logged at DEBUG"; since R299 that goes into the reply's warnings. schema.py:1254-1260 says IRIS auto-generates a SQLUser view. schema.py:569, 596, 654: `RETURNING INTEGER` truncates a fractional confidence. schema.py:1225 treats any error containing "unique" as success. Re-run hints given while initialize_schema() is already running do not say it writes (R-9 reading): schema.py:3105-3108, 3198-3200, 3253-3254; _engine/schema.py:2724-2729. Unused sql files that would break the `^KG` conventions if run: globals_schema.sql:33 (`KILL ^KG`), 45-87 (flat layout with no graph key), 54-55 (`deg`/`degp` counters). graph_path_globals.sql:295, 302. operators.sql:20 (`TO_VECTOR(queryInput)`). Stale hints in scripts: deploy_objectscript.py:261 names a method that does not exist. deploy_graph_tvfs.py:224 names a module that does not exist. The graph_walk_tvf.sql stubs return made-up rows (60-62, 90) and are granted to PUBLIC. migrate_to_nodepk.py:306-309 and 294: possible data defects outside the style scope (see the fork note). setup_iris.py:52-61 prints "Schema ready." without reading the returned status. SqlPrivilege.cls uses tabs and SqlProcs.cls four spaces (the R-1 family). Scripts log emoji (deploy_objectscript.py:95, 99, 213, 259). The schema fallback is spelled two ways: `getattr(self, "_schema_prefix", "Graph_KG")` and `_ivg_schema`.

### Conforming citations

C-2: no `type: ignore` in any module 01 file. C-4: schema.py's `$Char(1)` hits (2236-2238) are type marks, not keys. C-5..C-10: `^KG` is built only through BuildKG (schema.py:3347), and the markers are read through Graph.KG.Meta (schema.py:2845, 3330). C-14: SqlPrivilege.cls:1-10 holds; RequireSelect at SqlProcs.cls:133, 141, 147; RequireWrite at SqlProcs.cls:196 and PropWrite.cls:40. SqlProcs.cls:5-9 holds against 13 and 125-128. C-15: schema.py:25-28, 3178; _engine/schema.py:2107, 2113, 2575; schema_name.py:148, 157; legacy.py:29, 725. C-16: schema_name.py:1-7 matches CONTEXT.md:19-25; legacy.py:1-8. C-17: _engine/schema.py:2586-2590 re-raises; schema.py:2916-2917, 3100-3109; _commit.py:28-35; class_deploy.py:177-183 fails closed. C-18: schema_name.py:30-36 ("which writes"); _engine/schema.py:753-759, 2457-2462, 2668-2669; upgrade.py:352-358. C-19: schema.py:146-173 (`_iris_true` is documented). C-21/C-22/C-25/C-26: SqlPrivilege.cls:20/29, 39/53, 62/66; compound conditions at 63-64; postconditionals at 22, 26, 48, 73. C-23: SqlProcs.cls:141. C-27: schema.py:2469 `TO_VECTOR(:queryInput, DOUBLE)`; the signature at 2144-2146 takes no width; _engine/schema.py:744-745. C-28: `embedding_registry` (_engine/schema.py:143-158) is created at 2530, before adoption (2543) and any column alter (2561). C-29: SqlProcs.cls:131-135 forwards a read only. C-33: schema.py:2939. C-35: _engine/schema.py:443, 450, 2272, 2282-2285, 2699; schema.py:2775, 3338; class_deploy.py:318, 357; routine_record.py:38-40; statements.py:269-296. C-30, C-31, C-32, C-34: no hits in executed code.

## Module 02: graph identity

### Files

| File | Lines | Coverage | Conventions applicable |
| --- | --- | --- | --- |
| iris_src/src/Graph/KG/GraphKey.cls | 87 | full read | C-4, 5, 14, 16, 19, 21-26, 35 |
| iris_src/src/Graph/KG/GraphMode.cls | 77 | full read | C-4, 5, 14, 16, 17 (B-2 form), 18, 19, 21-26, 35 (B-5) |
| iris_vector_graph/_validate.py | 312 | full read | C-2, 4, 16, 17, 19 |
| iris_vector_graph/engine.py, graph-scoping parts 157-173, 442-486, 612-639, 988-1314 | 1,944 | full read of those ranges | C-2, 4, 15-19, 35 |
| iris_vector_graph/_engine/admin.py, set_multigraph / is_multigraph / _graph_mode_forget 893-936 | 1,041 | full read of that range | C-2, 4, 16-19 |

Not applicable (no hit in scope): C-6..C-10 and C-13/C-34 (no `^KG`/`^NKG` set or kill, no `^IVG.TemporalStructural`), and C-27..C-33.

### Deviations (counted)

| ID | Conv. | Where | What deviates |
| --- | --- | --- | --- |
| D-02-01 | C-4 | iris_vector_graph/_validate.py:52-71 | `graph_index_key` derives the `^KG` key in Python (`0 if canonical == "" else canonical`), outside `Graph.KG.GraphKey`, which ADR-0003:17-18 and :68 make the only source ("nothing else does"). Its docstring (55-58) says it is "the one place Python is allowed to"; no convention source grants that. Used at nodes_edges.py:1197, 1411; stores/lazy_kg.py:128; _engine/schema.py:3028, 3236 |
| D-02-02 | C-14 | iris_src/src/Graph/KG/GraphKey.cls:6 (repeated at :50) | The header says `ForIndex()` derives the subscript for "^KG / ^NKG". `^NKG` has no graph dimension (ARCHITECTURE.md:113-114; CONTEXT.md:97-101), and no `^NKG` node in iris_src is keyed by a graph key (grep) |
| D-02-03 | C-17 | iris_vector_graph/engine.py:464-465 | `_probe_column`: `except Exception: return False`. initialize_schema sets `_nodes_has_graph_id`/`_children_have_graph_id` from it (_engine/schema.py:2522-2526), and those flags decide whether create_node and the bulk writers name `graph_id` (nodes_edges.py:1023-1027, 1037). A failed catalog read silently turns graph-scoped writes into default-graph writes. The docstring (451-453) documents the choice; round 1 counted D-17 the same way |

### Borderline (not counted)

- GraphKey.cls:1 and 6-7 describe "both" derivations; the body has a third, `ForName` (58-69, "The third derivation"). ADR-0003:10-20 names two and CHANGELOG.md:4612-4614 says three. The header follows the ADR, so the documents disagree.
- GraphMode.cls:51: a `Graph_KG` literal in a deployed class (B-5).

### Candidate findings

- D-02-01: **existing F-0203** (02.json, reproduced live). The Python name check behind `graph_index_key` refuses fewer control characters than `GraphKey.Validate` (_validate.py:43 against GraphKey.cls:44): the drift a second home of the derivation allows.
- D-02-03: **new candidate N-02-1, "A failed graph_id probe during setup makes later named-graph node writes land in the default graph".**
  - Evidence: engine.py:446-465; _engine/schema.py:2522-2526; nodes_edges.py:1023-1027; schema.py:1809 (the unscoped INSERT names no `graph_id`, so the row takes `DEFAULT ''`, schema.py:397).
  - Consequence (source reading): on a post-214 namespace, if the catalog read raises once during `initialize_schema()`, the engine keeps `_nodes_has_graph_id = False` for its lifetime. `create_node(..., graph="g")` then writes the node into the default graph and returns True; the unscoped NOT EXISTS guard also matches the ID in any graph. Nothing is logged.
  - Severity S3. Confidence: medium on the code path, low on how often it occurs.
  - No finding in findings/audit/*.json mentions `_probe_column`, `_nodes_has_graph_id` or this probe.

### Reviewer notes (not counted)

engine.py:443, 447, 468, 613: docstrings say `Graph_KG.<table>` where the code reads the engine's schema (460, 624-634). admin.py:918-926: `is_multigraph` caches per engine (documented), so another engine's mode change is not seen. GraphMode.cls:35-40 checks and then kills without a lock: F-0207. admin.py:914-915: the RuntimeError names `GraphMode.Apply`, a writing call, as the call that failed, not as a remedy (C-18 read as met, R-9).

### Conforming citations

C-4: GraphMode.cls:18, 30, 50. admin.py:905-909 and 921-924, and engine.py:1275 and 1285, pass the name and let the server derive. C-5: GraphKey.cls:55, 76. C-14: GraphMode.cls:1-11 holds: ForIndex at 18 and 30; absent means off at 19; the Eraser kills the node at Eraser.cls:244. GraphKey.cls:23-37 matches 40-47. C-16: engine.py:1010-1012 and 1203-1204 against CONTEXT.md:38-42; admin.py:896-899 against CONTEXT.md:83-86; _validate.py:27 against CONTEXT.md:29-30. C-17: _validate.py:76-79 and 304-312 (specific, re-raised); admin.py:911-915; GraphMode.cls:41-43, 55-57. C-19: GraphMode.cls:59, 72; admin.py:925; engine.py:1288. C-21: GraphKey.cls:40, 47; GraphMode.cls:28, 44. C-22: GraphKey.cls:43, 53; GraphMode.cls:37, 69. C-23: GraphMode.cls:19. C-25 and C-26: no compound condition and no postconditional in either class. C-35: engine.py:460, 624, 630, 634. C-2 and C-15: no hits in scope.

## Module 03: direct writes

### Files

| File | Lines | Coverage | Conventions applicable |
| --- | --- | --- | --- |
| iris_vector_graph/_engine/nodes_edges.py | 2,625 | full read of 1-1472, 1565-1587 (erase_all, WRT-B93), 1597-2625; 1473-1564 and 1588-1596 are module 12 | C-2, 4, 6-8, 10, 11, 13/34, 15-19, 30-32, 35 |
| iris_vector_graph/engine.py, write facade 155-175, 248-276, 517-557, 1894-1944 | 1,944 | full read of those ranges | C-2, 15-18, 35 |
| iris_vector_graph/_write_txn.py | 277 | full read | C-2, 15, 17, 18, 35 |
| iris_src/src/Graph/KG/PropWrite.cls, Txn.cls, LabelIndex.cls | 102, 60, 45 | full read | C-4-8, 14, 15, 19, 21-26, 35 (B-5) |
| bulk_loader.py 714, prop_values.py 279, _dictionary.py 64, _collation.py 32, _batch_check.py 80 (iris_vector_graph/) | 1,169 | full read | C-2, 15-19, 30, 35, 40G1 |
| iris_vector_graph/_engine/snapshot.py, import half 1-15, 381-384, 439-796, 1694-1904 | 1,904 | full read of those ranges; the rest is module 18 | C-2, 5-10, 13/34, 15-19, 27-30, 35 |
| scripts/ingest/networkx_loader.py 578, scripts/load_drkg.py 112, scripts/load_demo_data.py 150 | 840 | full read | C-17, 18, 24, 28, 29, 35 |

### Deviations (counted)

| ID | Conv. | Where | What deviates |
| --- | --- | --- | --- |
| D-03-01 | C-17 | iris_vector_graph/_engine/nodes_edges.py:487-490 | bulk_load_session wraps `Graph.KG.Traversal.Build2HopStats` (it rebuilds `^KG("deg2p")`) in `except Exception: pass`; there is no log and no stats entry |
| D-03-02 | C-17 | iris_vector_graph/_engine/nodes_edges.py:1262-1272 | `_ekey_guard`: a failed INFORMATION_SCHEMA probe is logged at DEBUG and caches `""` for the engine's lifetime, so create_edge (1217) and bulk_ingest_edges (2099) guard on the triple alone. A probe that shapes the write it gates |
| D-03-03 | C-18 | iris_vector_graph/_engine/nodes_edges.py:49-50 | The GraphWriteError text says "run initialize_schema() again" and does not say that call writes |
| D-03-04 | C-18 | iris_vector_graph/_write_txn.py:197-201 | The WARNING ends "Run initialize_schema()." and does not say it writes |
| D-03-05 | C-30 | iris_vector_graph/_engine/nodes_edges.py:2567-2581 | store_edge swallows the duplicate when the triple's row is temporal-marked and never adopts it, so the marker stays (ADR-0009:13; CONTEXT.md:70-72) |
| D-03-06 | C-30 | iris_vector_graph/_engine/nodes_edges.py:2047-2076, 2092-2103 | bulk_ingest_edges never adopts a marked row on either the server path (EdgeScan.cls:296-300 skips an existing row) or the SQL path (`continue` at 2103); only create_edge (1251) and bulk_create_edges (2001) adopt |
| D-03-07 | C-21 (secondary) | iris_src/src/Graph/KG/LabelIndex.cls:16-23 | `UpdateIndex` calls RemoveLabel, checks it and carries on, without `Set tSC = $$$OK` first or `Quit tSC` last. Form only: both statuses reach the caller |
| D-03-08 | C-35 | iris_vector_graph/bulk_loader.py:41, 59, 80-81, 697 | BulkLoader defaults its schema to the literal Graph_KG and never resolves the argument, `IVG_SCHEMA_PREFIX` or the record (schema_name.py:3-5, 167-173); the CLI has no schema option |
| D-03-09 | C-35 | iris_vector_graph/bulk_loader.py:495 | `rebuild_all_indices` names the `Graph.KG.rdfedges/rdflabels/rdfprops/nodes` classes whatever `self.schema` is |
| D-03-10 | C-35 | scripts/ingest/networkx_loader.py:252-254, 281-283, 294, 315, 338, 380, 386, 411, 415 | Every statement names Graph_KG literally on a raw connection |
| D-03-11 | C-35 | scripts/load_demo_data.py:128-136 | The summary reads name Graph_KG on the raw connection, while the engine at 58 resolves the schema from `IVG_SCHEMA_PREFIX` |

By convention: C-35 4, C-17 2, C-18 2, C-30 2 (primary), and C-21 1 (secondary).

### Borderline (not counted)

- **C-17, B-3 form** (the handler names the step or the result carries the failure):
  - nodes_edges.py: 420-424, 427-434, 455-463, 470-474, 483-486, 496-499 (bulk_load_session, WARNING per step); 524-530 (backfill_2hop_exact, WARNING and documented 0); 1755-1757 and 2069-2071 (server-loader failure, WARNING, then the SQL path; related to F-C0330); 2293-2298 (`DeleteResult.failed`).
  - _write_txn.py:251-253 (ERROR while the caller raises).
  - engine.py:1940-1941 (a silent fallback to the caller's connection; not itself a data write).
  - bulk_loader.py:165-169, 240-249, 359-364.
  - snapshot.py:663-667, 694-698, 710-714 (skipped rows at WARNING, documented at 573-574) and 778-781 (failed BuildKG at WARNING; see N-03-6).
  - networkx_loader.py:358-364 and 447-449.
- **C-18**: _write_txn.py:190-194 ("Run initialize_schema() to bring the classes up to date") describes a change but does not say "writes".
- **C-4**: nodes_edges.py:1432 recovers the SQL `graph_id` from the `^KG` key inline (`"" if graph_key == 0 else graph_key`) while the name is in hand. ADR-0003:22-25 forbids converting between the two keys, and the SQL spelling is neither of them.
- **C-16**:
  - nodes_edges.py:494, 504-515 apply "drift" to `^NKG`, a Rebuilt store whose glossary state is "stale" (CONTEXT.md:109-115).
  - bulk_loader.py:4, 8-13: `%NOINDEX` bypasses the index, against CONTEXT.md:91-93 ("bulk load" changes it in the same transaction). Related: F-C1250, F-C1351.
- **C-30**: bulk_loader.py:453-454 stores a caller's `{"temporal": true}` qualifier as a marked row: F-C0351.
- **C-24** (B-4): load_demo_data.py:136 sends TOP with ORDER BY from Python.
- **B-5**: PropWrite.cls:27 and LabelIndex.cls:1-3.

### Candidate findings

| # | Existing or new | Title | Evidence | Severity / confidence |
| --- | --- | --- | --- | --- |
| 1 | F-0304 | Storing an edge over a marked edge does not take the edge over (D-03-05) | nodes_edges.py:2567-2581 | existing (S1, live) |
| 2 | F-0309 | rebuild_all_indices names Graph_KG's classes (D-03-09) | bulk_loader.py:495 | existing |
| N-03-1 | new | bulk_ingest_edges does not take over a temporal-marked row, so a later temporal delete can remove an explicitly written edge (D-03-06; F-0304's mechanism) | nodes_edges.py:2047-2076, 2092-2103; EdgeScan.cls:296-300 | S1 by analogy with F-0304 (S2 if inspected-only candidates are capped) / medium |
| N-03-2 | new | A failed ekey probe narrows create_edge's duplicate guard for the engine's lifetime: on a multigraph triple holding only keyed rows, a plain create_edge answers False and writes nothing (D-03-02) | nodes_edges.py:1217, 1262-1272, 2099 | S4 / low |
| N-03-3 | new | BulkLoader writes Graph_KG unless given `schema=`, ignoring `IVG_SCHEMA_PREFIX` and the record (D-03-08) | bulk_loader.py:41, 59, 80-81, 697 | S4 (S3 where both schemas' tables exist) / high |
| N-03-4 | new (related to F-C0340, F-C1701) | networkx_loader and load_demo_data address Graph_KG whatever the IVG Schema (D-03-10, D-03-11) | networkx_loader.py:252-415; load_demo_data.py:128-136 | S4 / high |
| N-03-5 | new | `_rebuild_indices` tests `if not status`; a failed %Status is non-empty text and reads as success, so load_networkx returns while the %NOINDEX rows stay invisible to SQL | bulk_loader.py:240-249 (contrast 533) | S3 / medium (the failed-status form was not observed) |
| N-03-6 | new | import_rdf answers normal counts after BuildKG fails; without a declared index the imported edges stay out of `^KG` | snapshot.py:776-782 | S4 / medium |
| N-03-7 | new | `load_drkg --embeddings` passes `{"id": ...}` but store_embeddings reads `item["node_id"]`: a KeyError after the graph is loaded | scripts/load_drkg.py:87; _engine/embeddings.py:1078 | S4 / high |

D-03-01 is not proposed as a defect: Build2HopStats stamps the version it was built at (TraversalBuild.cls:946-949), so staleness is detectable. D-03-03, D-03-04 and D-03-07 are wording or form only.

### Reviewer notes (not counted)

Stale text: nodes_edges.py:1568-1571 says rdf_labels/rdf_props are "keyed by node id alone". nodes_edges.py:1774 mentions "%NOINDEX" templates that have none. PropWrite.cls:19-21 calls val "the fifth column" beside `VALSLOT = 4`. LabelIndex.cls:6 cites ADR-0011 for a label rule that is ADR-0008:12-21. create_edge adopts only after its commit (1236, 1250-1252): F-C0301. Its JSON-`true` marker test (1297) differs from bulk_create_edges' prefix test (2001): F-C0450/F-C0351, round-1 R-7. `_swallow_duplicate` (138) and `is_duplicate` (_write_txn.py:46-49) accept any "unique" message: F-C1110. `_deleted_count` (96-100) turns an unreadable result into 0. bulk_delete_adjacency (2301-2339) has no `_ledger_check`: F-1108. get_json_field_values (921-923) pastes `field` into SQL: F-C0341. bulk_create_edges' `finally` (2013-2017) can replace the load's error with a sync error. bulk_loader.py:270 and 399 promise an "errors" key the stats do not return; bulk_loader.py:674 makes `--noindex` a no-op. export_graph_ndjson filters `graph_id = ''` (snapshot.py:1874, 1892) and misses NULL default-graph rows. `skip_existing` is unused (snapshot.py:468-469). bulk_loader.py:594-597 names %BuildIndices without saying it writes (R-9 reading).

### Conforming citations

C-2: none in scope. C-4: LabelIndex.cls:12, 18, 22, 27 pass the name, and Adjacency derives (Adjacency.cls:773, 784). C-5/C-6: nodes_edges.py:1226-1234, 1366-1368, 1445, 2113-2115 go through EdgeScan to Adjacency.Put/Remove (EdgeScan.cls:154-171). C-7: LabelIndex.cls:12-32 goes through Adjacency.PutLabel/RemoveLabel/RemoveAllLabels. C-8: no Python `^KG` set or kill. Erasure goes through the Eraser (nodes_edges.py:1582, 2335); `^KG` is built through Traversal classmethods (bulk_loader.py:531-536; snapshot.py:779). C-11: erase_all raises on failure (1581-1586). C-14: PropWrite.cls:1-15, Txn.cls:1-11 and LabelIndex.cls:1-6 hold against their bodies. C-15: _write_txn.py:20; Txn.cls:3; prop_values.py:147. C-16: nodes_edges.py:1390, 2363, 2378, 2550-2553; snapshot.py:455. C-17: nodes_edges.py:553-558, 1097-1104, 1237-1249; _write_txn.py:168-171; bulk_loader.py:118-127; _dictionary.py:51-56. C-18: nodes_edges.py:60, 76, 1248, 2309-2312; snapshot.py:629-632. C-19: PropWrite.cls:35-39 (documented at 3-7); _collation.py:1-6; prop_values.py:3-7, 171-186. C-22: LabelIndex.cls:19, 37, 42. C-25/C-26: PropWrite.cls:36, 51, 81 / 36, 37, 39, 69, 91. C-28: load_drkg.py:89 and load_demo_data.py:111 go through store_embeddings. C-29: load_demo_data.py:123. C-30: create_edge adopts at 1251 and 1275-1302; bulk_create_edges at 1992-2001; snapshot.py:1844, 1852. C-31/C-32: no `deg`/`degp`; writers reach Adjacency.Put (Adjacency.cls:86-89). C-35: nodes_edges.py:544, 1045, 1215, 2097 (`_t`/`_ivg_schema`) and 368, 2001 (rewrite); snapshot.py:657-658, 677, 685, 705.

## Conventions with no documented rule (not judged; a gap, not a pass)

Accuracy of Python docstrings and comments: C-14 covers Graph.KG class headers only. Which log level a failure gets. The style of generated SQL and DDL. Whether ObjectScript inside CREATE FUNCTION bodies follows anything beyond C-23..C-26. ObjectScript indentation, and `Quit` versus `Return` (round-1 L-2). Python naming (L-3). Operator-script conventions: argument defaults, default credentials and ports (constitution.md:97-98 covers test code only), emoji in logs. Which schema a standalone .sql file targets. Retiring unused sql/ files. Ownership of `^IVF` (SqlProcs.cls:141). Writing a table's storage global past the filer (PropWrite.cls:55). Detecting duplicates by message substring. %Status checks in Python. The NULL versus '' spelling of the default graph (spec 230 only).

## Limitations

- **L-1, not reviewed**:
  - Never reviewed:
    - scripts/setup_security.sql, which deploy_production.py:65 runs.
    - scripts/setup/__init__.py, which runs fraud_sample_data.sql.
    - schema.py:1640-1842 (bulk index disable/rebuild and the bulk insert SQL templates): module 01's scope does not name them, and module 03 uses them.
  - Out of scope, left to their modules:
    - Module 01: _engine/schema.py:326-420, 834-2096 and 2859-3397; schema.py:737-903, 1950-2029 and 2063-2143. These are the VEC, ADJ and ledger helpers that setup calls; their call sites in initialize_schema were judged.
    - Module 01: the four migration step modules other modules own.
    - Module 03: snapshot.py outside the import half.
  - Swept rather than read line by line:
    - The `get_procedures_sql_list` bodies (schema.py:2144-2781).
    - legacy_manifest.py's entries and legacy_bodies.py's hashes.
    - Five sql files.
- **L-2, server behaviour not observed**: everything here is inspected-grade. These candidates depend on server behaviour that was not seen:
  - N-01-1: what a package compile deletes.
  - N-01-2: what "ef-d" deletes.
  - N-01-5: whether IRIS accepts comment-only fragments.
  - N-03-5: the failed-%Status form.
  - N-02-1 and N-03-2: how often a catalog probe fails.
- **L-3, judged by readings that could differ**:
  - D-03-08 rests on reading schema_name.py:3-5 as binding on every Python writer. BulkLoader does take `schema=`, so a reader could put it among the borderline.
  - D-02-01 reads ADR-0003's "nothing else does" as covering Python.
  - The C-30 rows rest on CONTEXT.md:70-72 and ADR-0009; ADR-0009:13 names only create_edge.
- **L-4, not judged**: C-3 (compile) and C-20 (justified indirection).
- **L-5, an ontology citation that does not resolve**: `ontology/02-graph-identity.md` (GID-T3.9) cites `docs/adr/0003-two-graph-key-derivations.md:119-121`, but that ADR has 74 lines. This is an audit artifact, not the product.
