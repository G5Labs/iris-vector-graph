#!/usr/bin/env python3
"""Write refusals/audit/10.json (module 10, ALG) from the extracted X statements and the registered live logs.

    python experiment/playbook-completion/refusals/make_audit_10.py

Texts come verbatim from x-statements.json (extract_x.py); live case names come from the registered results logs
(every case of the statement in the log is cited, so a case that did not hold would fail rx_audit.py). Citations were
read at the pin.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path(os.environ["RUN_DIR"]) / "refusals" / "10"
xs = {s["id"]: s for s in json.loads((HERE / "x-statements.json").read_text())["statements"] if s["module"] == "10"}


def cases(log, sid):
    p = RUN / log
    if not p.is_file():
        return []
    return [c["case"] for c in json.loads(p.read_text())["cases"]
            if c.get("statement") == sid and c.get("outcome") != "observation"]


MAIN, WAIT = "results.json", "results-rebuild-wait.json"
LIVE, WAITRUN, UNIT = "run:rx-live-10", "run:rx-live-10-rebuild-wait", "run:b-10-run-unit"
AL = "iris_vector_graph/_engine/algorithms.py"
TP = "iris_src/src/Graph/KG/TraversalPaths.cls"
TR = "iris_vector_graph/cypher/translator.py"
CALLER = ("Made with RX10CallerStore, a delegating caller-supplied store of the harness passed through the engine's "
          "documented store= argument (engine.py:286, 375-379; store_protocol.py:7); the product ships no store "
          "of that shape (IRISGraphStore only). The refusal observed is the engine's.")

E = {
    "ALG-B1.5": dict(code=[f"{AL}:66-77", f"{AL}:768", "iris_src/src/Graph/KG/PageRank.cls:77-85",
                           "iris_src/src/Graph/KG/PageRank.cls:406-409"],
                     notes="ValueError naming damping / max_iterations from kg_PAGERANK; PageRankGlobalJson throws "
                           "IVG 5001 (CheckArgs). Journal: 0 records in every case."),
    "ALG-B1.13": dict(out="holds-run", code=[f"{AL}:773-779", f"{AL}:15-18"], ev=[UNIT],
                      log={UNIT: "tests/unit/test_463_refused_pagerank_delete_node.py"},
                      notes="Upstream unit test test_kg_pagerank_wraps_a_driver_refusal passed here (b-10-run-unit: "
                            "349 passed, 0 failed; mocked driver). Not triggered live: a database refusal of "
                            "kg_PAGERANK's read needs a login without SELECT on Graph_KG (the disabled IVGAUDIT_RO, "
                            "grants in AUDITB only; versions/PRIVILEGE.md), an operator action."),
    "ALG-B2.2": dict(code=["iris_vector_graph/_validate.py:19-48", f"{AL}:289", f"{AL}:1094"],
                     notes='"0" and a control character refused by validate_graph_name before any call.'),
    "ALG-B2.8": dict(code=[f"{AL}:66-77", f"{AL}:281", f"{AL}:644", f"{AL}:961", f"{AL}:1035",
                           "iris_src/src/Graph/KG/PageRank.cls:77-85", "iris_src/src/Graph/KG/PageRank.cls:170-173",
                           f"{TR}:3082-3088", "iris_vector_graph/schema.py:2582-2598"],
                     notes="Every PPR entry point probed: kg_PERSONALIZED_PAGERANK, ppr, kg_PPR, SQL kg_PPR "
                           "(SQLCODE -149 wrapping the IVG 5001 text), PageRank.RunJson, CALL ivg.ppr."),
    "ALG-B2.9": dict(code=[f"{AL}:282-285"]),
    "ALG-B2.10": dict(code=[f"{AL}:52-63", f"{AL}:286"],
                      notes="ValueError for no seed; TypeError for a string, a non-string and a nested list."),
    "ALG-B2.13": dict(code=[f"{AL}:21-49", f"{AL}:290", "iris_src/src/Graph/KG/PageRank.cls:351-380"],
                      notes="Python refusals and the server's ParseExclude (PPRExclude 5001) both probed."),
    "ALG-B3.4": dict(code=["iris_src/src/Graph/KG/Algorithms.cls:33-36", f"{AL}:805-828"],
                     notes="kg_WCC(max_iterations=1) on a 4-node chain raises 'WCC did not converge in 1 rounds'; "
                           "control: max_iterations=10 answers one component."),
    "ALG-B5.3": dict(code=["iris_vector_graph/_validate.py:243-246", f"{AL}:1089-1093",
                           "iris_src/src/Graph/KG/Centrality.cls:46", f"{TP}:350-355", f"{TR}:3468-3473"]),
    "ALG-B5.5": dict(code=[f"{AL}:1116-1127", "iris_vector_graph/store_protocol.py:106-109"],
                     notes="TypeError for graph='rx10g' from a store whose execute_degree_centrality takes no graph; "
                           "controls: the same store answers the default graph, the product's store answers the "
                           "named graph's own degrees. " + CALLER),
    "ALG-B5.10": dict(code=["iris_vector_graph/_validate.py:249-254", f"{AL}:1205-1211"],
                      notes="sample_size -1, direction, max_hops -1 and 1001, mem_budget_mb 8."),
    "ALG-B5.17": dict(code=["iris_vector_graph/_validate.py:257-261", f"{AL}:1392"]),
    "ALG-B5.21": dict(code=[f"{AL}:1213-1217", f"{AL}:1399-1403"],
                      notes="NotImplementedError 'Centrality.betweenness not supported by store RX10CallerStore' (and "
                            "closeness). The text says 'not supported', which the statement words as 'not built'. "
                            + CALLER),
    "ALG-B5.22": dict(code=[f"{AL}:1323-1331"]),
    "ALG-B5.94": dict(code=["iris_src/src/Graph/KG/NKGAccelCentrality.cls:4-7",
                            "iris_src/src/Graph/KG/NKGAccelCentrality.cls:351-354",
                            "iris_src/src/Graph/KG/NKGAccelCentrality.cls:608-611",
                            "iris_vector_graph/schema.py:2648-2649", "iris_vector_graph/schema.py:2669-2670"],
                      notes="Server methods answer the ERROR: texts; the SQL functions raise (SQLCODE -149 wrapping "
                            "-400 with the ERROR: text; the IVG 5001 code itself is not in the driver's message)."),
    "ALG-B6.7": dict(code=["iris_vector_graph/_validate.py:270-276", f"{AL}:1587"]),
    "ALG-B6.8": dict(code=[f"{AL}:84-88", f"{AL}:1617", f"{AL}:1699", f"{AL}:1757", f"{AL}:1815"],
                     ev_extra=[UNIT],
                     notes="RuntimeError '<method> failed: ...' for leiden, triangle_count, SCC and k_core when the "
                           "store's path reports an error. " + CALLER + " Upstream "
                           "tests/unit/test_460_centrality_failed_path_raises.py also passed (b-10-run-unit)."),
    "ALG-B6.95": dict(out="blocked-access", code=["iris_vector_graph/stores/arno_bridge.py:432-517"],
                      dependency="an x86_64 libarno_callout.so 1.2.1 loadable by the audit IRIS (F-1001; "
                                 "versions/AVAILABILITY.md, run ver-arno-callout)",
                      notes="Only the library-missing branch is reachable here and holds live (rx-live-10: arno_call "
                            "raises ArnoError 'libarno_callout not available', for a known and an unknown kernel name; "
                            "the unknown-name, arity, NULL/ERROR-answer and chunked-fetch branches run only after "
                            "arno_available() is True). The first call wrote ^IVG.Deploy(\"routines\") once (the "
                            "wrappers' routine record, arno_bridge.py:360-376), allowed for that case."),
    "ALG-B7": dict(code=[f"{TR}:256-275", f"{TR}:226-241", f"{TR}:31703-31868", f"{AL}:171-177"],
                   notes="All seven procedures refused with a named graph's edge present, each naming its engine "
                         "method (engine.betweenness_centrality() ... engine.k_core())."),
    "ALG-B7.1": dict(code=[f"{TR}:226-241"], notes="USE GRAPH '' and USE GRAPH 'rx10g'."),
    "ALG-B7.2": dict(code=["iris_src/src/Graph/KG/NKGAccel.cls:208-222", "iris_vector_graph/schema.py:2645",
                           "iris_vector_graph/schema.py:2665", "iris_vector_graph/schema.py:2686",
                           "iris_vector_graph/schema.py:2706", "iris_vector_graph/schema.py:2725",
                           "iris_vector_graph/schema.py:2744", "iris_vector_graph/schema.py:2763"],
                     notes="All seven kg_* SQL functions and RefuseMergedGraphs itself."),
    "ALG-B7.4": dict(code=["iris_src/src/Graph/KG/Communities.cls:56-58", "iris_src/src/Graph/KG/Communities.cls:111-113",
                           "iris_src/src/Graph/KG/Communities.cls:186-188", "iris_vector_graph/schema.py:2730",
                           "iris_vector_graph/_engine/query.py:1746-1774"],
                     notes="On an empty namespace (^NKG not built) CALL ivg.triangleCount/scc/kcore answer in-band "
                           "(no rows, IVGResult.error naming '^NKG not built', as execute_cypher documents for a failed "
                           "read) and raise with raise_on_error=True; SQL kg_TriangleCount raises (-149)."),
    "ALG-B7.91": dict(code=[f"{TR}:123-135", f"{TR}:160-180", f"{TR}:326-338", "iris_vector_graph/_validate.py:291-312"],
                      notes="Unknown keys (bogus, weighted, depth) and model-refused values (formula 'classic', "
                            "maxHops -1, maxIter 0, gamma 0, topK -1) across betweenness, closeness, eigenvector, "
                            "leiden, triangleCount, scc, kcore."),
    "ALG-B8.10": dict(code=[f"{AL}:961"]),
    "ALG-B9.3": dict(out="blocked-access", code=[f"{AL}:100-131", f"{AL}:719-724"],
                     dependency="a login that may not write AUDITE's globals database (<PROTECT> on ^ArnoKG): the "
                                "disposable least-privilege user IVGAUDIT_RO exists but is disabled, with SQL grants "
                                "in AUDITB only (versions/PRIVILEGE.md); enabling it and granting in AUDITE is a "
                                "security change for the operator",
                     notes="Not triggered; no upstream test of _refused_work_area was run here."),
    "ALG-B10.6": dict(code=[f"{TP}:256-263", f"{TP}:350-355", f"{TP}:359-365", f"{TP}:378-380", f"{TR}:3449-3460",
                            f"{TR}:3468-3473"],
                      notes="Server DijkstraJson/DijkstraCost and CALL ivg.shortestPath.weighted."),
    "ALG-B12.3": dict(code=["iris_src/src/Graph/KG/TraversalBuild.cls:250", "iris_src/src/Graph/KG/TraversalBuild.cls:288-296",
                            "iris_src/src/Graph/KG/TraversalBuild.cls:410-413"], wait=True,
                      notes="Another process holds ^IVG.NKGBuild; Graph.KG.Traversal.BuildNKG (third process) waits "
                            "NKGBUILDWAIT (900 s) and throws naming the lock; while it waits a 20 s check shows both "
                            "rebuilds still blocked. Its own process wrote nothing."),
    "ALG-B12.8": dict(code=["iris_vector_graph/_engine/schema.py:2859-2875", "iris_vector_graph/_engine/schema.py:2878-2884",
                            "iris_vector_graph/_engine/schema.py:2898-2910"], wait=True,
                      notes="engine.sync() during the same held lock raised after 900 s: RuntimeError "
                            "'Graph.KG.Traversal.BuildKG failed: ERROR #5001: BuildKG rebuilt ^KG but not ^NKG: ... "
                            "BuildNKG: another ^NKG build held ^IVG.NKGBuild for 900 seconds' (_raise_unless_ok names "
                            "the server method). Its process changed only ^KG nodes (BuildKG's rewrite, allowed for "
                            "this case)."),
    "ALG-B13.3": dict(code=["iris_src/src/Graph/KG/ArnoAccel.cls:51-71", "iris_vector_graph/stores/arno_bridge.py:143-160"],
                      notes="ivg_arno_zf_probe and ivg_arno_zf_call_2s refuse another library path and an unused "
                            "function name (SQLCODE -99 inside -149) before any $ZF; the wrappers exist in AUDITE "
                            "(created by the product's own arno_available, arno_bridge.py:360-376)."),
    "ALG-B13.93": dict(code=["iris_src/src/Graph/KG/NKGAccelLoader.cls:128-135", "iris_src/src/Graph/KG/NKGAccel.cls:144-147"]),
    "ALG-B15.2": dict(out="holds-run", code=["iris_vector_graph/arno_readers.py:58-62", "iris_vector_graph/arno_readers.py:80-172"],
                      ev=[UNIT, LIVE], log={UNIT: "tests/unit/test_236_proof_file.py"},
                      notes="Upstream test_validate_proof_agrees_with_the_committed_schema passed here (b-10-run-unit, "
                            "349 passed). Corroborated in the rx-live-10 harness (pure Python, no IRIS): "
                            "Proof.from_dict refuses min_revision 0, four fixtures, four repeats, a bad version form "
                            "and a bad sha256."),
    "ALG-B15.3": dict(out="holds-run", code=["iris_vector_graph/arno_readers.py:28", "iris_vector_graph/arno_readers.py:133-135"],
                      ev=[UNIT, LIVE], log={UNIT: "tests/unit/test_236_reader_routing.py"},
                      notes="Upstream test_betweenness_is_never_native_however_the_report_and_proof_read passed here "
                            "(b-10-run-unit). Corroborated in rx-live-10: Proof.from_dict refuses a record naming "
                            "betweenness ('not a routed algorithm')."),
    "ALG-B15.10": dict(out="holds-run", code=["iris_vector_graph/_arno_gate.py:179-187", "scripts/arno_reader_gate.py:255-261"],
                       ev=[UNIT, LIVE], log={UNIT: "tests/unit/test_236_reader_gate.py"},
                       notes="Upstream test_check_fails_when_the_proof_claims_a_revision_above_the_report passed here "
                             "(b-10-run-unit). Corroborated in rx-live-10 with AUDITE's real reader report ({}: no "
                             "library) against the committed docs/dev/arno-reader-proof.json (pagerank min_revision "
                             "2): one problem reported. The gate script itself was not run: it connects only to USER "
                             "(another lane's namespace) and erases it per fixture."),
    "ALG-B15.11": dict(out="holds-run", code=["iris_vector_graph/_arno_gate.py:190-196", "scripts/arno_reader_gate.py:240-252"],
                       ev=[UNIT, LIVE], log={UNIT: "tests/unit/test_236_reader_gate.py"},
                       notes="Upstream test_a_missing_library_fails_under_the_require_switch_and_skips_otherwise passed "
                             "here (b-10-run-unit). Corroborated in rx-live-10: missing_library_action answers 'fail' "
                             "with IVG_REQUIRE_ARNO=1 and 'skip' without, and store._detect_arno() is False on AUDITE. "
                             "The gate script was not run (USER only)."),
}

out = []
for sid, s in xs.items():
    e = E[sid]
    o = e.get("out", "holds-live")
    rec = {"id": sid, "text": s["text"], "implementing_code": e["code"], "outcome": o}
    if o == "holds-live":
        log, run = (WAIT, WAITRUN) if e.get("wait") else (MAIN, LIVE)
        rec["evidence"] = [run] + e.get("ev_extra", [])
        rec["live_cases"] = cases(log, sid)
    elif o == "holds-run":
        rec["evidence"] = e["ev"]
        rec["log_contains"] = e["log"]
    elif o == "blocked-access":
        rec["dependency"] = e["dependency"]
        rec["evidence"] = [LIVE] if cases(MAIN, sid) else []
        if cases(MAIN, sid):
            rec["live_cases"] = cases(MAIN, sid)
    if e.get("notes"):
        rec["notes"] = e["notes"]
    out.append(rec)
missing = set(xs) - set(E)
assert not missing, missing
(HERE / "audit").mkdir(exist_ok=True)
(HERE / "audit" / "10.json").write_text(json.dumps({"module": "10", "code": "ALG", "statements": out}, indent=1) + "\n")
from collections import Counter
print(len(out), Counter(r["outcome"] for r in out))
