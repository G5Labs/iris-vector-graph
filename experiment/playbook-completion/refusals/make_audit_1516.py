#!/usr/bin/env python3
"""Write refusals/audit/15.json and 16.json (fragments for tools/rx_audit.py) from the curated per-statement table
below and the registered live results ($RUN_DIR/refusals/NN/results.json, run rx-live-NN): the live case names are
read from the results (every case of the statement), never typed by hand; texts come from x-statements.json.

    python make_audit_1516.py 15|16
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path(os.environ["RUN_DIR"]) / "refusals"

FHIR_DEP = ("HS.FHIRServer classes and a JsonAdvSQL FHIR repository in the namespace (InterSystems IRIS for Health; "
            "the audit container is IRIS 2026.1 Community: 0 HS.FHIRServer classes, no HS_FHIRServer.Repo table, "
            "rx-live-15 observation)")

T15 = {
    "INT-F1.5": dict(outcome="blocked-access", dependency=FHIR_DEP,
                     code=["iris_src/src/Graph/KG/FHIRGraph.cls:2620-2650"], partial=True,
                     notes="Partial live: Graph.KG.FHIRGraph.Classify (instance method on a fresh %New(), Native API) "
                           "answers 'skip' for '#contained1', 'urn:uuid:1234', 'Patient', 'Patient/1/x' and '/1' (5 "
                           "cases, 0 journal records); control 'Patient/p1' answers 'local'. That a skipped link never "
                           "becomes an edge is a property of a sync, which needs a FHIR repository."),
    "INT-F1.13": dict(outcome="holds-live",
                      code=["iris_vector_graph/fhir_links.py:44-71", "iris_vector_graph/_engine/fhir_graph.py:247",
                            "iris_src/src/Graph/KG/FHIRGraph.cls:2736-2808",
                            "iris_src/src/Graph/KG/FHIRGraph.cls:171-176"],
                      notes="engine.fhir_graph_register(json_links=...) refuses a wrong form, a duplicate and a "
                            "predicate clash (ValueError naming the entry) before IRIS; the server's ParseJsonLinks "
                            "refuses the same three with {'status':'error'}; 6 cases, 0 journal records."),
    "INT-F1.14": dict(outcome="blocked-access", dependency=FHIR_DEP,
                      code=["iris_src/src/Graph/KG/FHIRGraph.cls:2380-2394",
                            "iris_src/src/Graph/KG/FHIRGraph.cls:2973-2978",
                            "iris_src/src/Graph/KG/FHIRGraph.cls:2983-2988",
                            "iris_src/src/Graph/KG/FHIRGraph.cls:3017-3021"], partial=True,
                      notes="Partial live: the server's ExtractLinks (the json-link extractor a sync uses) refuses a "
                            "body that is not JSON, a 70-level nesting under an extension link (WALKDEPTH 64) and "
                            "10,001 matches (WALKMATCHES 10000) with {'status':'error'}; 3 cases, 0 journal records. "
                            "ReadResource's not-JSON refusal and the failure of the whole batch need a sync over a "
                            "FHIR repository. Note: the depth bound applies only while an extension json link is "
                            "configured (Walk runs only then, FHIRGraph.cls:2973-2975)."),
    "INT-F1.20": dict(outcome="blocked-access", dependency=FHIR_DEP,
                      code=["iris_src/src/Graph/KG/FHIRGraph.cls:2519-2525",
                            "iris_src/src/Graph/KG/FHIRGraph.cls:1832-1849"],
                      notes="Category labels are derived in SyncProps (private, during a sync) against R4Types read "
                            "from the repository's schema; nothing reaches it without a repository."),
    "INT-F2.3": dict(outcome="blocked-access", dependency=FHIR_DEP,
                     code=["iris_src/src/Graph/KG/FHIRGraph.cls:2192-2194"],
                     notes="Compartment edges are derived during a sync only."),
    "INT-F2.4": dict(outcome="blocked-access", dependency=FHIR_DEP,
                     code=["iris_src/src/Graph/KG/FHIRGraph.cls:2194-2205"],
                     notes="Compartment edges are derived during a sync only (only 'Patient/' targets of the "
                           "compartment params, ..Comp)."),
    "INT-F3.2": dict(outcome="holds-live",
                     code=["iris_vector_graph/_engine/fhir_graph.py:190-202",
                           "iris_src/src/Graph/KG/FHIRGraph.cls:178-181"],
                     notes="engine.fhir_graph_register() and the server's Register in AUDITE (no repository): "
                           "FHIRGraphError / {'status':'error'} 'namespace AUDITE has no FHIR repository'; no "
                           "Graph_KG.fhir_g* table before or after; 2 cases, 0 journal records. Upstream e2e "
                           "test_register_without_repository_creates_nothing also PASSED in val-e2e-1-c01."),
    "INT-F3.3": dict(outcome="blocked-access", dependency=FHIR_DEP,
                     code=["iris_src/src/Graph/KG/FHIRGraph.cls:189-212"],
                     notes="In AUDITE a named endpoint is refused by the repository check first (observation: "
                           "Register('/csp/healthshare/rx15/fhir/r4') answers 'no FHIR repository'); the two-repository "
                           "and unknown-endpoint branches need HS_FHIRServer.Repo/RepoInstance. The upstream e2e test "
                           "was SKIPPED in val-e2e-1-c18 for the same reason."),
    "INT-F3.4": dict(outcome="blocked-access", dependency=FHIR_DEP,
                     code=["iris_src/src/Graph/KG/FHIRGraph.cls:214-225"],
                     notes="The storage-strategy check reads HS_FHIRServer.Repo."),
    "INT-F3.5": dict(outcome="holds-live",
                     code=["iris_vector_graph/_engine/fhir_graph.py:243-246",
                           "iris_vector_graph/_engine/fhir_graph.py:296-299",
                           "iris_src/src/Graph/KG/FHIRGraph.cls:183-185",
                           "iris_src/src/Graph/KG/FHIRGraph.cls:671-675"],
                     notes="engine register (interval 30, 59) and schedule (30) refuse with ValueError before IRIS; "
                           "3 cases, 0 journal records. The class's own checks (Register 183-185, Schedule 671-675) "
                           "sit after the repository / registration checks, so in AUDITE they are not reached."),
    "INT-F3.6": dict(outcome="holds-live",
                     code=["iris_vector_graph/_engine/fhir_graph.py:239-242",
                           "iris_src/src/Graph/KG/FHIRGraph.cls:1752-1766"],
                     notes="engine register refuses 'badentry', 'Patient.' and 'Pat ient.x' with the entry named; 3 "
                           "cases, 0 journal records. The class's ParseDenylist runs after the repository check."),
    "INT-F5.8": dict(outcome="holds-run",
                     code=["iris_vector_graph/_engine/fhir_graph.py:64-76",
                           "iris_vector_graph/_engine/fhir_graph.py:270-273",
                           "iris_vector_graph/_engine/fhir_graph.py:510-513"],
                     evidence=["run:val-unit-3-c01"],
                     log_contains={"run:val-unit-3-c01":
                                   "tests/unit/test_235_interp_marker.py::TestInterpStale::test_higher_raises PASSED"},
                     notes="The version is read from a registered graph's Status/CoverageReport, which needs a FHIR "
                           "repository; the decision (_interp_stale raises RuntimeError when newer) is covered by the "
                           "upstream unit test, which passed in val-unit-3-c01."),
    "INT-F8.1": dict(outcome="holds-live",
                     code=["iris_src/src/Graph/KG/FHIRGraph.cls:1713-1724",
                           "iris_vector_graph/_engine/fhir_graph.py:183-188"],
                     notes="status, rebuild, sync, reinterpret, schedule, unschedule, link report, resolve concepts, "
                           "coverage report, concept gaps, concept ppr and patient anchors (graph=) on an unregistered "
                           "graph: each FHIRGraphError '... is not registered; call Register() first'; 12 cases, 0 "
                           "journal records."),
    "INT-F8.2": dict(outcome="holds-live",
                     code=["iris_vector_graph/_engine/fhir_graph.py:56-61", "iris_vector_graph/_validate.py:31-49"],
                     notes="status, sync, rebuild, link report, coverage report with None, '', '0' and a control "
                           "character: ValueError; a spy on the engine's Native API and FHIR server calls counted 0 "
                           "requests in every case (before IRIS); 20 cases, 0 journal records."),
    "INT-F8.4": dict(outcome="holds-live", code=["iris_vector_graph/_engine/fhir_graph.py:283-289"],
                     notes="'notakey', 'Patient/', 'Patient/1/x', 'Pat ient/1': ValueError before IRIS; 4 cases."),
    "INT-F9.2": dict(outcome="blocked-access", dependency=FHIR_DEP,
                     code=["iris_src/src/Graph/KG/FHIRGraph.cls:683", "iris_src/src/Graph/KG/FHIRGraph.cls:725",
                           "iris_src/src/Graph/KG/FHIRGraph.cls:744-775"],
                     notes="CheckOwnTask runs on a registered graph's task_id; registering needs a repository (the "
                           "upstream e2e tests were SKIPPED in val-e2e-1-c14)."),
    "INT-C1.2": dict(outcome="holds-live",
                     code=["iris_vector_graph/_engine/fhir_graph.py:386-389",
                           "iris_vector_graph/_engine/fhir_graph.py:157-159"],
                     notes="hops 11, -1, True and direction 'sideways': ValueError, 0 FHIR server calls (spy); 4 cases."),
    "INT-C1.7": dict(outcome="holds-live",
                     code=["iris_vector_graph/_engine/fhir_graph.py:93-103",
                           "iris_vector_graph/_engine/fhir_graph.py:170-177",
                           "iris_vector_graph/_engine/fhir_graph.py:334-336"],
                     notes="relation 'nope', param 'code; DROP', params a bare string: ValueError; 3 cases."),
    "INT-C2.6": dict(outcome="holds-live", code=["iris_vector_graph/_engine/fhir_graph.py:434-446"],
                     notes="via or explain_top without group_by, group_by 'encounter', via ['Bad Param'], via a "
                           "string, explain_top -1: ValueError with 0 Native API requests and 0 FHIR calls (spy); 6 "
                           "cases."),
    "INT-C3.4": dict(outcome="holds-live",
                     code=["iris_vector_graph/_engine/fhir_graph.py:149-154",
                           "iris_vector_graph/_engine/fhir_graph.py:500",
                           "iris_vector_graph/_engine/fhir_graph.py:533-535"],
                     notes="coverage prefix 'bad prefix!', 65 letters, ''; gaps prefix 'bad prefix!', top 0, top "
                           "True: ValueError, 0 FHIR calls; 6 cases."),
    "INT-C4.3": dict(outcome="holds-live", code=["iris_vector_graph/_engine/fhir_graph.py:571-572"],
                     notes="'bad id!', 65 letters, '', 'p/1': ValueError; 4 cases."),
    "INT-C4.5": dict(outcome="holds-live", code=["iris_vector_graph/cypher_api.py:288-308"],
                     notes="POST /api/cypher (in-process app) with fhir_base_url not listed (no list; a longer path of "
                           "the listed base; another base listed): HTTP 400 naming IVG_FHIR_ALLOWED_BASES and the "
                           "target listener saw 0 connections; control: the listed base with a trailing slash is "
                           "fetched (1 connection); 3 cases."),
    "INT-C5.1": dict(outcome="holds-live", code=["iris_vector_graph/_engine/fhir_graph.py:620-628"],
                     notes="empty system, code, target and relation 'nope': ValueError; 4 cases."),
    "INT-M1.2": dict(outcome="holds-live",
                     code=["iris_vector_graph/_engine/fhir.py:106-110", "iris_vector_graph/security.py:78-99"],
                     notes="table 'IVGAudit.RX15Pat; DROP', column 'pid)--', label 'RX15 L': ValueError; 3 cases."),
    "INT-M1.3": dict(outcome="holds-live", code=["iris_vector_graph/_engine/fhir.py:111-126"],
                     notes="missing qualified table and missing id column of an existing IVGAudit table: ValueError "
                           "'not found'; 2 cases. Related, not a missing refusal: F-1504 (an unqualified name is "
                           "looked up in schema USER, so an existing SQLUser table is refused)."),
    "INT-M1.6": dict(outcome="holds-live", code=["iris_vector_graph/_engine/fhir.py:165-174"],
                     notes="no fk or join table; source label not mapped; target label not mapped: ValueError; 3 "
                           "cases."),
    "INT-M1.8": dict(outcome="holds-live", code=["iris_vector_graph/_engine/fhir.py:242-247"],
                     notes="remove_table_mapping('RX15NeverMapped'): ValueError, no net journal change; 1 case."),
    "INT-M1.12": dict(outcome="holds-live", code=["iris_vector_graph/_engine/fhir.py:296-300"],
                      notes="attach_embeddings_to_table('RX15NeverMapped'): TableNotMappedError; 1 case."),
    "INT-R1.18": dict(outcome="holds-live",
                      code=["iris_vector_graph/_engine/rdf_export.py:39-47",
                            "iris_vector_graph/_engine/rdf_export.py:123",
                            "iris_vector_graph/_engine/rdf_export.py:179"],
                      notes="rdflib hidden from import in the probe process: export_rdf and export_rdf_from_cypher "
                            "raise ImportError naming iris-vector-graph[rdf]; no file written; 2 cases."),
    "INT-R1.19": dict(outcome="product-defect", finding="F-1506",
                      code=["iris_vector_graph/_engine/_rdf_utils.py:125-133"],
                      notes="An rdflib stand-in (the installed 7.6.0 minus ConjunctiveGraph, __version__ 8.0.0) in the "
                            "probe process: export_rdf and validate_shacl raise ImportError 'rdflib is required for RDF "
                            "operations. Install with: pip install iris-vector-graph[rdf]' as if rdflib were missing; "
                            "the version is not named. Reproduces F-1506 (confirmed-source until now) live; 2 cases."),
    "INT-E1.4": dict(outcome="holds-live", code=["iris_vector_graph/_engine/schema.py:3292-3330"],
                     notes="reify_edge of a second edge, and of the same edge, with the already linked reifier id "
                           "'rx15:reif': GraphWriteError (SQLCODE -119), journal net change 0, link and properties "
                           "unchanged; 2 cases."),
    "INT-E1.5": dict(outcome="holds-live",
                     code=["iris_vector_graph/_engine/schema.py:3286", "iris_vector_graph/_engine/schema.py:3372",
                           "iris_vector_graph/_engine/ledger.py:72-79", "iris_vector_graph/ledger/guard.py:75-80"],
                     notes="ledger enabled strict: reify_edge and delete_reification raise LedgerStrictModeError; the "
                           "only journal change is the guard's rej_strict_block counter in Graph_KG.ledger_stats "
                           "(guard.py:77, allowed); 2 cases."),
    "INT-S1.4": dict(outcome="holds-live", code=["iris_vector_graph/_engine/shacl.py:123-132"],
                     notes="HTTP 500 -> IOError 'Could not fetch shapes ... HTTP 500'; refused connection -> IOError "
                           "'... Connection refused'; a listener that accepts and never answers -> TimeoutError "
                           "'timed out' after 30 s (an OSError subclass, so an IO error, but not wrapped in the "
                           "'Could not fetch shapes' message: urlopen times out in the read, outside the caught "
                           "URLError); 3 cases."),
    "INT-S1.6": dict(outcome="holds-live", code=["iris_vector_graph/_engine/shacl.py:115-120"],
                     notes="int, list, bytes: ValueError 'shapes_source must be ...'; 3 cases."),
    "INT-S1.11": dict(outcome="holds-live",
                      code=["iris_vector_graph/_engine/shacl.py:85-104", "iris_vector_graph/_engine/shacl.py:227-228"],
                      notes="rdflib hidden: ImportError 'rdflib is required for SHACL validation ... [rdf]'; pyshacl "
                            "hidden: ImportError 'pyshacl is required ... [rdf]'; 2 cases."),
    "INT-V1.4": dict(outcome="holds-live", code=["iris_vector_graph/_engine/prov.py:181-191"],
                     notes="A named graph's temporal edge alone in the window: prov_export reports 0 activities and "
                           "the file does not mention it; control: a default-graph edge in the same window is exported "
                           "(1 activity); 1 case."),
    "INT-V1.10": dict(outcome="holds-live",
                      code=["iris_vector_graph/_engine/prov.py:48-56", "iris_vector_graph/_engine/prov.py:126",
                            "iris_vector_graph/_engine/prov.py:86-105"],
                      notes="rdflib hidden: prov_export raises ImportError naming PROV-O and [rdf], no file; "
                            "prov_as_dict of the default-graph edge still answers (observation); 1 case."),
    "INT-X80.86": dict(outcome="holds-inspected",
                       code=["iris_vector_graph/_engine/schema.py:3192-3202", "iris_vector_graph/_write_txn.py:90-99"],
                       notes="The refusal applies only where rdf_edges lacks the functional adjacency index. AUDITE, "
                             "deployed by the pin's initialize_schema, has it (observation: Adjacency.IndexKind() = "
                             "functional, engine._adjacency_indexed True), so the branch cannot be entered there; making "
                             "a namespace without it would need a schema change outside the pin's deploy path. No "
                             "dependency is missing; the code is read at the pin (refuse_in_caller_transaction raises "
                             "CallerTransactionOpenError when $TLEVEL > 0, the same helper whose refusals hold live "
                             "elsewhere, e.g. SNP-X2.2)."),
    "INT-B90.90": dict(outcome="holds-live",
                       code=["iris_vector_graph/cli.py:28-44", "iris_vector_graph/cli.py:296-317"],
                       notes="`ivg fhir register|status|rebuild|sync --once|links|schedule` and `ivg embeddings "
                             "inventory` with no IRIS_* variables: exit 1, stderr naming IRIS_HOST and --iris-host; "
                             "7 cases."),
    "INT-B90.91": dict(outcome="holds-live", code=["iris_vector_graph/cli.py:350-361"],
                       notes="`ivg fhir sync G` without --once, IRIS_HOST at a local listener: exit 2 (click "
                             "UsageError) pointing to `ivg fhir schedule`; the listener saw 0 connections; 1 case."),
}


def build(module: str, table: dict) -> dict:
    xs = json.loads((HERE / "x-statements.json").read_text())
    texts = {s["id"]: s["text"] for s in xs["statements"] if s["module"] == module}
    res = json.loads((RUN / module / "results.json").read_text())
    by: dict = {}
    for c in res["cases"]:
        if c.get("statement") and c.get("outcome") not in (None, "observation"):
            by.setdefault(c["statement"], []).append(c["case"])
    missing = sorted(set(texts) - set(table))
    extra = sorted(set(table) - set(texts))
    if missing or extra:
        raise SystemExit(f"table does not match the module's X statements: missing {missing}, extra {extra}")
    out = []
    for sid in texts:
        t = table[sid]
        e = {"id": sid, "text": texts[sid], "outcome": t["outcome"], "implementing_code": t["code"],
             "evidence": t.get("evidence", [f"run:rx-live-{module}"]), "notes": t["notes"]}
        if t["outcome"] in ("holds-live", "product-defect") and t.get("evidence") is None:
            e["live_cases"] = by.get(sid, [])
        if t.get("partial"):
            e["partial_live_cases"] = by.get(sid, [])
            e["evidence"] = [f"run:rx-live-{module}"]
        for k in ("finding", "dependency", "log_contains", "absent"):
            if k in t:
                e[k] = t[k]
        out.append(e)
    return {"module": module, "pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e", "statements": out}


def main():
    m = sys.argv[1]
    table = {"15": T15}.get(m)
    if table is None:
        from make_audit_16 import T16  # noqa: E402
        table = T16
    doc = build(m, table)
    p = HERE / "audit" / f"{m}.json"
    p.write_text(json.dumps(doc, indent=1) + "\n")
    from collections import Counter
    print(p, dict(Counter(s["outcome"] for s in doc["statements"])))


if __name__ == "__main__":
    main()
