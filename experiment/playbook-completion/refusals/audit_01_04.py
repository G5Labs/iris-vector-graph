#!/usr/bin/env python3
"""Build the refusals-audit fragments for modules 01 (INS) and 04 (ADJ): refusals/audit/01.json and 04.json.

    python experiment/playbook-completion/refusals/audit_01_04.py

Statement texts come from the mechanical extraction (tools/extract_x.py, the ontology itself), live case names from
the registered runs' results.json (rx-live-01, rx-live-04: every case of the statement whose name does not start with
"setup"/"control"/"function:" and is a refusal record), so nothing is retyped. The judgement per statement (outcome,
implementing code read at the pin, upstream-test evidence, dependency) is the table below.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
import extract_x  # noqa: E402

RUN = Path(os.environ["RUN_DIR"])
RUNS = {"01": ("rx-live-01", RUN / "refusals/01/results.json"), "04": ("rx-live-04", RUN / "refusals/04/results.json")}

S = "iris_vector_graph/schema_name.py"
E = "iris_vector_graph/_engine/schema.py"
U3 = "tests/unit/"


def passed(test):
    return f"{test} PASSED"


# id -> (outcome, implementing_code, extra evidence runs, log_contains, dependency, notes)
T = {
    "INS-X1.2": ("holds-live", [f"{E}:2227-2228", f"{E}:2432-2438"], ["val-unit-3-c02"], None, None,
                 "Live in AUDITE: an engine built with embedding_dimension=None (it stayed None) gets ValueError "
                 "naming embedding_dimension from initialize_schema(); the journal window shows 0 records. The upstream "
                 "unit test on fakes passed too (val-unit-3-c02)."),
    "INS-X1.3": ("holds-live", [f"{E}:2150-2157", "iris_vector_graph/_write_txn.py:90-99"], [], None, None,
                 "Live: START TRANSACTION on the engine's connection ($TLEVEL 1), then initialize_schema() and "
                 "initialize_schema(dry_run=True): both CallerTransactionOpenError, 0 journal records, the caller's "
                 "level still 1 afterwards."),
    "INS-X1.5": ("holds-run", [f"{E}:685-704", f"{E}:765", f"{E}:2469", f"{S}:107-121", f"{S}:123-131"],
                 ["val-unit-3-c01"],
                 {"run:val-unit-3-c01": passed(U3 + "test_262_setup_privilege.py::test_setup_stops_at_the_first_"
                                                  "privilege_violation_and_names_it")},
                 None,
                 "Not triggered live: it needs a user without %CREATE_TABLE/%CREATE_FUNCTION running setup. The lane's "
                 "connection is _SYSTEM (%All); the versions lane's least-privilege user IVGAUDIT_RO is disabled and "
                 "scoped to AUDITB (enabling it is the operator's). Evidence: the upstream unit tests on fakes "
                 "(test_setup_stops_at_the_first_privilege_violation_and_names_it, "
                 "test_a_violation_after_objects_were_created_says_so) passed in val-unit-3-c01. The error text "
                 "match rests on premise P-0105 (IRIS's -99 wording)."),
    "INS-X2.3": ("holds-live", [f"{S}:143-158", "iris_vector_graph/engine.py:299"], ["val-unit-3-c06"], None, None,
                 "Live: IRISGraphEngine(schema_prefix=...) with '', '1bad', 'bad-name', '%Bad', 'SQLUser', 'sqluser': "
                 "each ValueError naming its rule, raised in the constructor before the record read; 0 journal "
                 "records."),
    "INS-X2.4": ("holds-live", [f"{S}:24", f"{S}:159-163"], [], None, None,
                 "Live: 'IVG', 'ivgc', 'IVG_Sub', 'Graph_KG_Sub', 'IVGC_x' each refused naming the code package; "
                 "'graph_kg' validates to Graph_KG (allowed)."),
    "INS-X2.6": ("holds-run", [f"{S}:465-498", f"{S}:501-509", f"{E}:2243"], ["val-scratch-1"],
                 {"run:val-scratch-1": passed("tests/integration/test_schema_record.py::test_a_package_holding_"
                                              "someone_elses_class_is_refused_and_ivgs_own_are_not")},
                 None,
                 "Through setup the check is reached only on a namespace whose record names the requested schema or "
                 "has none; AUDITE records Graph_KG, so initialize_schema(dry_run=True) on INFORMATION_SCHEMA meets the "
                 "record check first (live case shown, IVGSchemaError mismatch). The implementing function itself was "
                 "driven live and read-only: refuse_package_clash(conn, 'INFORMATION_SCHEMA') raised, naming "
                 "INFORMATION.SCHEMA.* classes, 0 journal records (case 'function: refuse_package_clash...'). The "
                 "upstream integration test on a real scratch namespace passed in val-scratch-1."),
    "INS-X2.10": ("blocked-access", [f"{S}:84-104", f"{E}:2229-2242"], [], None,
                  "a namespace with no IVG Schema record whose IVG tables are in another schema or in several "
                  "(the pinned fixture tests/e2e/test_262_record.py builds one in a scratch namespace; its tests were "
                  "SKIPPED in val-e2e-1-c03, gate off, and are not in the gated subsets). AUDITE records Graph_KG; per "
                  "the lane brief no scratch namespace is created here: open",
                  "No upstream test outside that e2e file exercises unrecorded_schemas. Inspected: _engine/schema.py:"
                  "2229-2242 computes the held schemas only when nothing is recorded and raises before "
                  "refuse_package_clash and before any write."),
    "INS-X2.12": ("holds-live", [f"{E}:2222-2226", "iris_vector_graph/_engine/class_deploy.py:355-357",
                                 "iris_vector_graph/schema.py:2878-2888", f"{S}:184-192"], ["val-unit-3-c02"], None,
                  None,
                  "Live: an engine on RXOTHER (AUDITE records Graph_KG): initialize_schema() and its preview raise "
                  "IVGSchemaError naming both schemas; deploy_packaged_classes(conn, schema='RXOTHER') and "
                  "GraphSchema.deploy_objectscript_classes(schema='RXOTHER') raise the same before any load; 0 "
                  "journal records each; the record still reads Graph_KG after the run."),
    "INS-X3.2": ("holds-live", [f"{S}:74-82", f"{S}:220-228", f"{S}:322-348", "iris_vector_graph/engine.py:362-366",
                                "iris_vector_graph/engine.py:414-416", "iris_vector_graph/engine.py:1847-1868"], [],
                 None, None,
                 "Mechanical and live: every public function of the engine class not in EXEMPT_METHODS (233, the "
                 "guard's own selection criterion) and every public method of engine.graph/cypher/temporal/"
                 "algorithms plus ledger meta/head/stats/history/enable/disable/redaction_in_progress/verify, each "
                 "called with no arguments on an engine for RXOTHER: every one raised IVGSchemaError naming Graph_KG "
                 "and RXOTHER; construction itself wrote nothing; 0 journal records. Not called: the 4 public "
                 "class-level callables the guard does not wrap (TableNotMappedError, the classmethods from_connect "
                 "and from_wrapper, which build a new engine, and the staticmethod snapshot_info)."),
    "INS-X3.3": ("holds-run", [f"{S}:220-235", f"{S}:249-267"], ["val-unit-3-c05"],
                 {"run:val-unit-3-c05": passed(U3 + "test_first_access.py::test_every_kind_of_first_access_is_"
                                                    "refused[<lambda>0]")},
                 None,
                 "Needs a namespace with no record and no marker routine; AUDITE has a record. Upstream unit tests "
                 "(fakes) passed in val-unit-3-c05; the never-set-up branch also passed on real IRIS (INS-X3.3.1)."),
    "INS-X3.3.1": ("holds-run", [f"{S}:55-61", f"{S}:262-267"], ["val-scratch-1", "val-unit-3-c02"],
                   {"run:val-scratch-1": passed("tests/integration/test_schema_record.py::test_no_record_and_no_46_"
                                                "objects_is_refused_with_the_never_set_up_error"),
                    "run:val-unit-3-c02": passed(U3 + "test_460_r201_never_set_up.py::test_a_namespace_never_set_up_"
                                                      "says_so")},
                   None, "The integration test ran check_first_access on a real untouched scratch namespace."),
    "INS-X3.3.2": ("holds-run", [f"{S}:48-53", f"{S}:256-261"], ["val-unit-3-c02"],
                   {"run:val-unit-3-c02": passed(U3 + "test_460_r201_never_set_up.py::test_a_namespace_with_an_"
                                                      "earlier_releases_objects_is_still_not_upgraded[User.funcCYCMP]")},
                   None,
                   "Needs a namespace with no record holding a legacy object. The O-1 fixture namespace IVG262FC1306 "
                   "holds v4.5.1 objects but records RAG (the pin's setup ran there), so it would not reach this "
                   "branch; not used."),
    "INS-X3.3.3": ("holds-run", [f"{S}:63-71", f"{S}:238-243", f"{S}:262-266"], ["val-unit-3-c02"],
                   {"run:val-unit-3-c02": passed(U3 + "test_460_r201_never_set_up.py::test_ivgs_own_objects_without_"
                                                      "an_earlier_releases_are_an_unfinished_setup[trace0]")},
                   None, "Needs a namespace with no record holding IVG's own parts only; unit tests on fakes."),
    "INS-X4.10": ("holds-run", ["iris_vector_graph/_engine/class_deploy.py:193-210",
                                "iris_vector_graph/_engine/class_deploy.py:245-251"], ["val-unit-3-c05"],
                  {"run:val-unit-3-c05": passed(U3 + "test_class_deploy.py::TestSchemaClasses::test_someone_elses_"
                                                     "class_of_a_schema_class_name_stops_the_deploy")},
                  None,
                  "A live trigger needs a foreign class compiled under a schema class name in a schema's package "
                  "(compiling a class is out of scope)."),
    "INS-X5.6": ("holds-inspected", [f"{E}:766-785", f"{E}:797-803"], [], None, None,
                 "Not triggerable here: it needs the core kg_KNN_VEC procedure DDL to fail with an SQLCODE other "
                 "than -260 (an error the deployed namespace does not produce, and changing the deployed objects is "
                 "out of scope); no upstream test exercises it (searched tests/ for the RuntimeError text). "
                 "Inspected: a non -260 failure of a core routine is appended to procedure_errors (:783-784) and "
                 "raised as RuntimeError after routines.save() (:797-803), so the record of the others is saved first, "
                 "as the statement's note says."),
    "INS-X6.2": ("holds-run", ["iris_vector_graph/_engine/legacy.py:257-259",
                               "iris_vector_graph/_engine/legacy.py:432-434"], ["val-unit-3-c02"],
                 {"run:val-unit-3-c02": passed(U3 + "test_460_r170_read_path_grants.py::test_an_unexpected_grantee_"
                                                    "name_is_refused")},
                 None,
                 "Reached through setup only with 4.5.x grants on legacy objects. The implementing function was "
                 "driven live: legacy.copy_grants with grantee 'rx01 bad;name' raised ValueError before any GRANT, 0 "
                 "journal records (case 'function: legacy.copy_grants...')."),
    "INS-X6.11": ("holds-run", ["iris_vector_graph/_engine/legacy.py:576-587"], ["val-unit-3-c03"],
                  {"run:val-unit-3-c03": passed(U3 + "test_460_r293_legacy_arno_wrappers.py::test_a_revoke_that_"
                                                     "leaves_the_grant_raises")},
                  None, "Needs a REVOKE that IRIS accepts but that leaves the grant; unit test on fakes."),
    "INS-X6.13": ("holds-inspected", ["iris_vector_graph/_engine/legacy.py:633-635"], ["rx-live-01"], None, None,
                  "No upstream test. Reached through setup only on a namespace recorded under a schema other than "
                  "Graph_KG whose ledger table was not created. The implementing function was driven live in AUDITE "
                  "(case 'function: copy_ledger_history...'): with one genesis row in Graph_KG.ledger_revisions, "
                  "copy_ledger_history(conn, 'RXNOSCHEMA', dry_run=False) raised RuntimeError naming the table and "
                  "the 1 row not copied, 0 journal records."),
    "INS-X7.7": ("holds-live", ["iris_vector_graph/_engine/admin.py:388-395"], ["val-unit-3-c06"], None, None,
                 "Live: with a caller transaction open, remove_legacy_objects(dry_run=False) raised "
                 "CallerTransactionOpenError (0 journal records) and the listing (dry_run=True) answered [] in the "
                 "same transaction, not refused."),
    "INS-X8.5": ("holds-run", [f"{E}:2582-2590", "iris_vector_graph/schema.py:3098-3109"], ["val-unit-3-c00"],
                 {"run:val-unit-3-c00": passed(U3 + "test_230_rdf_edges_rescue.py::TestARescueFailureIsNotSwallowed::"
                                                    "test_initialize_schema_reraises_a_rescue_failure")},
                 None, "Needs a v3.2.0 class-owned rdf_edges and a failing restore; unit test on fakes."),
    "INS-X8.7": ("holds-run", ["iris_vector_graph/schema.py:3185-3202"], ["val-unit-3-c06"],
                 {"run:val-unit-3-c06": passed(U3 + "test_ivg400_rescue_resume.py::TestWhatTheReRunLeavesInTheWay::"
                                                    "test_a_leftover_holding_rows_the_rescue_lacks_is_never_dropped")},
                 None, "Needs a rescue table and a leftover rdf_edges holding foreign rows; unit test on fakes."),
    "INS-X9.4.91": ("holds-live", ["iris_vector_graph/schema.py:1446-1451"], [], None, None,
                    "Live call of GraphSchema.get_graph_scope_migration_sql(legacy_node_keys=['bad; DROP']): "
                    "ValueError, no statements returned (pure function, 0 journal records)."),
    "INS-X9.5": ("holds-live", ["iris_vector_graph/migrations/upgrade.py:178", "iris_vector_graph/migrations/"
                                "upgrade.py:226-236"], [], None, None,
                 "Live: steps=['rx01_bogus'] (dry_run=False) and ['rx01_bogus', 'embeddings'] (dry_run=True) both "
                 "ValueError naming the four known steps before any step; 0 journal records."),
    "INS-X9.8": ("holds-live", ["iris_vector_graph/migrations/upgrade.py:176-177",
                                "iris_vector_graph/migrations/_commit.py:18-22"], [], None, None,
                 "Live: with a caller transaction open, upgrade_to_4_0_0(dry_run=False) raised "
                 "CallerTransactionOpenError (0 journal records); the preview (dry_run=True) in the same "
                 "transaction answered an UpgradeReport, not refused."),
    "INS-X9.9": ("holds-run", ["iris_vector_graph/migrations/_commit.py:25-35"], ["val-unit-3-c04"],
                 {"run:val-unit-3-c04": passed(U3 + "test_470_migration_commit.py::test_a_failed_commit_raises_naming_"
                                                    "the_migration_and_rolls_back[docs_and_edge_vectors]")},
                 None, "Needs a commit IRIS refuses mid-upgrade; unit test with a failing connection."),
    "INS-X9.13": ("holds-live", ["iris_vector_graph/migrations/statements.py:55-57"], ["val-unit-3-c06"], None, None,
                  "Live call: Statement(expects='rx01-bogus') raised ValueError (no IRIS contact)."),
    "INS-X9.14": ("holds-live", ["iris_vector_graph/migrations/statements.py:315-320"], ["val-unit-3-c06"], None,
                  None,
                  "Live: run_statement on a cursor-counting wrapper of the lane's real connection with 2 values for 1 "
                  "placeholder raised ValueError; 0 cursors opened, 0 journal records."),
    "INS-X10.7": ("holds-run", ["iris_src/src/Graph/KG/SqlPrivilege.cls:18-31",
                                "iris_src/src/Graph/KG/SqlProcs.cls:133-162"], ["val-gated-rag-1"],
                  {"run:val-gated-rag-1": passed("tests/e2e/test_460_r280_sql_global_readers_privilege_e2e.py::"
                                                 "test_execute_without_select_is_refused_naming_the_table[kg_PPR]")},
                  None,
                  "Real-IRIS e2e (gate on, operator ruling): a fixture user holding EXECUTE but no SELECT calls each "
                  "global-reading SQL function; the test asserts 'SQLCODE=-99' and 'User <u> lacks SELECT on "
                  "<schema.table>' (tests/e2e/test_460_r280_sql_global_readers_privilege_e2e.py:140-144); all 8 "
                  "parametrizations PASSED in val-gated-rag-1 (the run's 2 failures are unrelated rrf-score-string). "
                  "Not probed by this lane: its connection is _SYSTEM (%All passes, SqlPrivilege.cls:21)."),
    "INS-X10.8": ("holds-live", ["iris_src/src/Graph/KG/SqlPrivilege.cls:56-67", "iris_vector_graph/schema.py:2396",
                                 "iris_vector_graph/schema.py:2405", "iris_vector_graph/schema.py:2420"],
                  ["val-gated-rag-1"], None, None,
                  "Live (failed read): SQL functions CY_PROPS_MAP, CY_VLP_OPT and CY_VLP_CHAIN given a missing table "
                  "each raised SQLCODE -149 wrapping -30 '... (reading Graph_KG.rx01_no_such_table)' instead of an "
                  "empty answer; 0 journal records. The refused (-99) read is covered by the real-IRIS e2e "
                  "test_460_r279_dynamic_sql_refusals_e2e.py::test_the_refusal_is_raised_naming_the_table (3 "
                  "parametrizations PASSED in val-gated-rag-1)."),
    "ADJ-X4.7": ("product-defect", ["iris_src/src/Graph/KG/Adjacency.cls:428-434",
                                "iris_src/src/Graph/KG/Adjacency.cls:452-458",
                                "iris_src/src/Graph/KG/Adjacency.cls:814-821",
                                "iris_src/src/Graph/KG/Eraser.cls:234-235", "iris_src/src/Graph/KG/Eraser.cls:788-789",
                                "iris_src/src/Graph/KG/TraversalBuild.cls:37-38"], [], None, None,
                 "Live: a second process holds ^IVG.AdjW exclusively (Native API lock, shown in ^$LOCK). The refusal "
                 "is implemented: erase_graph, erase_all and sync (BuildKG) each raised the writer-lock error and the "
                 "seeded rows and ^KG out entries are all still there; after the lock is released the same erase_graph "
                 "succeeds (control). 'Nothing is written' does not hold: the journal keeps net changes the rollback "
                 "does not undo (^IVG.AdjNoLock(g), ^KG(\"gen\",g,src), ^KG(\"__version\"); BuildKG only the version), "
                 "and the erase refusal comes after 5 s per deleted edge row plus 5 s (15.07 s, 20.07 s): F-C0415 (S4)."),
    "ADJ-X7.10": ("holds-live", ["iris_src/src/Graph/KG/TraversalBuild.cls:249-250",
                                 "iris_src/src/Graph/KG/TraversalBuild.cls:293-296",
                                 "iris_src/src/Graph/KG/TraversalBuild.cls:410-413"], [], None, None,
                  "Live: a second process holds ^IVG.NKGBuild exclusively; engine.rebuild_nkg() (BuildNKG) waited "
                  "and raised 'another ^NKG build held ^IVG.NKGBuild for 900 seconds' (elapsed time in the case "
                  "record). EnsureNKG (:410-413) shares the lock and the wait; not probed separately."),
    "ADJ-X9.4": ("holds-live", ["iris_vector_graph/_engine/admin.py:885-886", "iris_vector_graph/_validate.py:19-49"],
                 ["val-integration-1-c05"], None, None,
                 "Live: verify_graph('0'), verify_graph('rx04\\x01bad') and verify_graph(5) each ValueError before "
                 "GraphVerify runs; 0 journal records. The upstream integration test "
                 "test_a_graph_name_that_cannot_be_represented_is_rejected PASSED in val-integration-1-c05."),
}


FINDINGS = {"ADJ-X4.7": "F-C0415"}


def live_cases(results: Path, sid: str):
    doc = json.loads(results.read_text())
    out, fn = [], []
    for c in doc["cases"]:
        if c.get("statement") != sid or c.get("outcome") == "observation":
            continue
        if c["case"].startswith("function:"):
            fn.append(c["case"])
        else:
            out.append(c["case"])
    return out, fn


def main():
    xs = extract_x.extract(extract_x.ONTOLOGY, ["01", "04"], extract_x.REPO)
    for mod in ("01", "04"):
        rid, results = RUNS[mod]
        entries = []
        for s in xs["statements"]:
            if s["module"] != mod:
                continue
            outcome, code, runs, logc, dep, notes = T[s["id"]]
            e = {"id": s["id"], "text": s["text"], "implementing_code": code, "outcome": outcome, "notes": notes}
            ev = []
            cases, fn = live_cases(results, s["id"]) if results.is_file() else ([], [])
            if outcome in ("holds-live", "product-defect") and cases:
                e["live_cases"] = cases
                ev.append(f"run:{rid}")
                if fn:
                    e["live_function_cases"] = fn
            elif fn or cases:
                ev.append(f"run:{rid}")
                e["live_function_cases"] = fn
                e["live_entry_cases"] = cases
            ev += [f"run:{r}" for r in runs if f"run:{r}" not in ev]
            e["evidence"] = ev
            if logc:
                e["log_contains"] = logc
            if dep:
                e["dependency"] = dep
            if s["id"] in FINDINGS:
                e["finding"] = FINDINGS[s["id"]]
            entries.append(e)
        out = HERE / "audit" / f"{mod}.json"
        out.write_text(json.dumps({"module": mod, "lane": "refusals (fork C)", "statements": entries}, indent=1) + "\n")
        print(f"wrote {out}: {len(entries)} statements")


if __name__ == "__main__":
    main()
