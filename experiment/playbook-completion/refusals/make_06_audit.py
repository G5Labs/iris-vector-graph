#!/usr/bin/env python3
"""Build refusals/audit/06.json (module 06, VEC kind X) from the per-statement decisions below, the registered live
run's results (case names are checked against it) and the registered upstream-suite logs (each holds-run citation is
the exact pytest -v PASSED line found in a registered run's log).

    python experiment/playbook-completion/refusals/make_06_audit.py
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPLETION = HERE.parent
RD = Path(os.environ["RUN_DIR"])
LIVE = "rx-live-06"
LOCAL = "rx-probe-06-local"

xs = {s["id"]: s for s in json.loads((HERE / "x-statements.json").read_text())["statements"] if s["module"] == "06"}
live_doc = json.loads((RD / "refusals" / "06" / "results.json").read_text())
cases = {}
for c in live_doc["cases"]:
    if (c.get("statement") or "").startswith("VEC-") and c.get("outcome") != "observation":
        cases.setdefault(c["statement"], []).append(c)

_runs = []
for f in sorted((COMPLETION / "evidence" / "runs").glob("val-*.json")):
    d = json.loads(f.read_text())
    p = Path(d["log"].replace("$RUN_DIR", str(RD)))
    if p.is_file():
        _runs.append((d["id"], p, d["result"]))
# complete suite chunks first; val-unit-2 (result incomplete) only when nothing else shows the test
_runs.sort(key=lambda r: (r[2] == "incomplete", r[0]))
_text = {}


def passed(test: str, avoid=()):
    """(run id, exact log line) of a registered run whose log shows `test` PASSED. test = 'path::name'. Runs in
    `avoid` are tried last (log_contains holds one substring per run)."""
    path, _, name = test.partition("::")
    pat = re.compile(re.escape(path) + r"::(?:[A-Za-z0-9_]+::)?" + re.escape(name) + r"(?:\[[^\]]*\])? PASSED")
    order = [r for r in _runs if r[0] not in avoid] + [r for r in _runs if r[0] in avoid]
    for rid, p, _res in order:
        if rid not in _text:
            _text[rid] = p.read_text(errors="replace")
        m = pat.search(_text[rid])
        if m:
            return rid, m.group(0)
    raise SystemExit(f"no registered run shows {test} PASSED")


def live(sid, outcome, code, notes, finding=None, extra_runs=()):
    names = [c["case"] for c in cases.get(sid, [])]
    if not names:
        raise SystemExit(f"{sid}: no live case in results.json")
    e = {"outcome": outcome, "implementing_code": code, "evidence": [f"run:{LIVE}", *[f"run:{r}" for r in extra_runs]],
         "live_cases": names, "notes": notes}
    if finding:
        e["finding"] = finding
    return e


def run(sid, tests, code, notes, extra_runs=()):
    lc, ev = {}, []
    for t in tests:
        rid, line = passed(t, avoid={k[4:] for k in lc})
        key = f"run:{rid}"
        if key in lc:  # one substring per run: keep the first, list the others in notes
            notes += f" Also PASSED in {rid}: {line}."
            continue
        lc[key] = line
        ev.append(key)
    return {"outcome": "holds-run", "implementing_code": code, "evidence": ev + [f"run:{r}" for r in extra_runs],
            "log_contains": lc, "notes": notes}


E = "iris_vector_graph/_engine/embeddings.py"
S = "iris_vector_graph/_engine/schema.py"
V = "iris_vector_graph/_engine/vector.py"
Q = "iris_src/src/Graph/KG/EmbedQueue.cls"
G = "iris_vector_graph/migrations/graph_scoped_embeddings.py"

A = {
    "VEC-X1.5": live("VEC-X1.5", "holds-live", [f"{S}:1127-1127", "iris_vector_graph/embedding_identity.py:59-72"],
                     "set_embedding_identity normalizes the offered key; normalize_model_key raises ValueError for a "
                     "blank key; 0 journal records. A writer with no model offers the undeclared identity "
                     "(identity_from_config(None): mechanism and model_key None, observation in the log)."),
    "VEC-X1.6": live("VEC-X1.6", "holds-live", [f"{S}:1122-1125", "iris_vector_graph/embedding_identity.py:147-151"],
                     "Both entry points refuse 'word2vec' with ValueError naming the closed set; 0 journal records."),
    "VEC-X1.13": live("VEC-X1.13", "holds-live", [f"{S}:1383-1396", f"{E}:1064-1073", f"{E}:973-987"],
                      "A width clash (batch of 5-wide vectors into a 4-wide route) and a mechanism clash "
                      "(sentence-transformers claim vs an embedding_config writer of the same model name) both raise "
                      "EmbeddingIdentityConflict before any INSERT; the width case names graph 'rx06g13'; 0 journal "
                      "records in both windows."),
    "VEC-X1.16": {"outcome": "product-defect", "implementing_code": [f"{S}:1042-1061", f"{S}:1383-1385"],
                  "evidence": ["run:breadth-a-probe-local-0101-0601", f"run:{LOCAL}"], "finding": "F-0601",
                  "notes": "Not implemented: get_embedding_identity answers None for any read error "
                           "(schema.py:1054-1056), and enforce_embedding_identity then lets the write through "
                           "(1383-1385). Shown on pin code with a stand-in cursor raising SQLCODE -99 (breadth-a "
                           "probe; again in rx-probe-06-local: returned None, write proceeds). Not triggerable live "
                           "here: a present-but-unreadable registry needs a second IRIS user without SELECT on it "
                           "(the versions lane's least-privilege user is disabled and not this lane's to enable)."},
    "VEC-X1.19": live("VEC-X1.19", "holds-live", [f"{S}:1209-1216"],
                      "A row claimed for rx06-m1 refuses rx06-m2 with EmbeddingIdentityConflict; registry row "
                      "unchanged; 0 journal records."),
    "VEC-X1.21": live("VEC-X1.21", "holds-live", [f"{S}:1117-1121"],
                      "Undeclared identity and None both refused with ValueError; 0 journal records."),
    "VEC-X1.22": live("VEC-X1.22", "holds-live", [f"{S}:1109-1113", "iris_vector_graph/security.py:58-68"],
                      "'nodes' and an edge route name kg_eemb_<16 hex> both refused with ValueError; 0 journal "
                      "records."),
    "VEC-X1.29": live("VEC-X1.29", "holds-live", [f"{S}:2276-2281", f"{S}:1564-1599", f"{S}:1517-1537"],
                      "initialize_schema at width 6 over empty width-4 columns (no rewidth) and with rewidth=True "
                      "while kg_NodeEmbeddings holds a vector: both raise EmbeddingIdentityConflict before setup "
                      "writes (0 journal records); column widths stay 4."),
    "VEC-X2.8": live("VEC-X2.8", "holds-live", [f"{E}:493-499"],
                     "Inside a caller transaction (START TRANSACTION + INSERT, $TLEVEL 1) a write needing a new route "
                     "raises CallerTransactionOpenError; 0 journal records; no route after the rollback."),
    "VEC-X2.11": run("VEC-X2.11", ["tests/unit/test_227_route_reuse_width.py::test_orphan_table_at_another_width_refuses_the_route",
                                   "tests/unit/test_227_route_reuse_width.py::test_a_refused_route_records_nothing"],
                     [f"{E}:589-633"],
                     "Upstream unit tests (stand-in cursor) PASSED here. Not probed live: a routed table that outlived "
                     "its registry row arises only from an interrupted writer, a lost race or a direct registry edit; "
                     "this lane does not edit product tables to stage it."),
    "VEC-X2.16": run("VEC-X2.16", ["tests/unit/test_460_r161_read_route_absent_only.py::test_any_other_failure_raises",
                                   "tests/unit/test_460_r161_read_route_absent_only.py::test_a_named_graph_read_does_not_fall_back_to_the_legacy_table"],
                     [f"{E}:423-434"],
                     "Upstream unit tests PASSED here; rx-probe-06-local also shows _read_route raising on a SQLCODE -99 "
                     "registry read (pin code, stand-in cursor). Not live: needs a user who may not read the registry.",
                     extra_runs=(LOCAL,)),
    "VEC-X3.1": live("VEC-X3.1", "holds-live", [f"{E}:967-967", "iris_vector_graph/_engine/nodes_edges.py:532-557"],
                     "A node present only in the default graph, stored for graph rx06g31, and a node in no graph: "
                     "ValueError 'Node does not exist in graph'; 0 journal records."),
    "VEC-X3.2": live("VEC-X3.2", "holds-live", [f"{S}:1383-1396", f"{E}:973-987"],
                     "5-wide vector into graph rx06g32's 4-wide route: EmbeddingIdentityConflict naming graph "
                     "'rx06g32'; route row count unchanged; 0 journal records."),
    "VEC-X3.7": live("VEC-X3.7", "holds-live", [f"{E}:1050-1059"],
                     "Batch with widths [4, 5]: ValueError before any route or row; 0 journal records."),
    "VEC-X3.9": live("VEC-X3.9", "product-defect", [f"{E}:1064-1084"],
                     "Reproduced live: the batch is refused (ValueError for the missing node) after _route_for_write "
                     "made the new route: the journal shows a new embedding_registry row (kg_emb_..., graph rx06g39, "
                     "set_by routed) and the routed table's class storage (^oddTSQL); 90 records. F-0615.",
                     finding="F-0615"),
    "VEC-X3.16": live("VEC-X3.16", "product-defect", ["iris_vector_graph/vector_utils.py:151-280"],
                      "Not implemented: migrate_to_optimized has no identity check (F-0613, source). Live on IRIS 2026.1 "
                      "the tool cannot reach its copy loop: its CREATE INDEX IF NOT EXISTS ... AS HNSW is rejected "
                      "(SQLCODE -1, 'ON expected'), so it returns success False with that SQL error and copies "
                      "nothing - a failure for another reason, not the stated identity refusal (F-C0615).",
                      finding="F-0613"),
    "VEC-X4.5": run("VEC-X4.5", ["tests/unit/test_460_r276_except_audit.py::test_embedding_count_raises_when_it_cannot_count",
                                 "tests/unit/test_embedded_wgproto.py::test_embedding_count_raises_on_another_error"],
                    [f"{E}:2156-2162", f"{E}:904-939"],
                    "embedding_count re-raises any failure but a missing table (2156-2162); get_unembedded_nodes has "
                    "no except at all (917-939), so a failed listing raises. Upstream unit tests PASSED here; "
                    "rx-probe-06-local shows embedding_count raising on SQLCODE -99. A failing count cannot be "
                    "produced live without a restricted user.", extra_runs=(LOCAL,)),
    "VEC-X5.5": live("VEC-X5.5", "holds-live", [f"{V}:455-502"],
                     "kg_KNN_VEC and search_nodes_by_vector with a 5-wide query on a 4-wide route: ValueError naming "
                     "5 and 4 before any search statement; 0 journal records."),
    "VEC-X5.11": {"outcome": "blocked-access", "implementing_code": [f"{V}:779-790"],
                  "evidence": [f"run:{LIVE}"],
                  "dependency": "an IRIS server without native VECTOR_COSINE (before 2024.1); this 2026.1 server has it "
                                "(_probe_native_vec True), so search_nodes_by_vector never reaches its IVF branch",
                  "notes": "Corroboration only (SIMULATED, not counted as live): with the engine's cached native-vector "
                           "probe forced to False on the real engine, search_nodes_by_vector naming a graph or a "
                           "model raised ValueError with 0 journal records (cases 'SIMULATED no-VECTOR_COSINE ...' "
                           "in rx-live-06)."},
    "VEC-X5.15": live("VEC-X5.15", "product-defect", [f"{V}:1209-1220"],
                      "Holds for a node route (kg_emb_: ValueError); not for an edge route: vector_search over "
                      "kg_eemb_ with no graph ran and returned a row ('rx06:s1', score 1) - the name test checks only "
                      "the kg_emb_ prefix (vector.py:1212). Live reproduction of the kg_eemb_ half of F-0612 "
                      "(disposition confirmed-source until now).", finding="F-0612"),
    "VEC-X6.7": live("VEC-X6.7", "product-defect", [f"{E}:1462-1480"],
                     "Reproduced live: embed_nodes over graph rx06g67 with 5-wide vectors into a 4-wide route returned "
                     "{'embedded': 0, 'errors': 2, ...} and logged the EmbeddingIdentityConflict; only "
                     "CallerTransactionOpenError is re-raised (1472-1473). F-0614.", finding="F-0614"),
    "VEC-X7.2": live("VEC-X7.2", "holds-live", [f"{Q}:35-50", f"{Q}:64-78"],
                     "Node pending for rx06qa; enqueue for rx06qb answers 0 and leaves the entry (graph rx06qa, "
                     "PENDING); 0 journal records."),
    "VEC-X7.5": live("VEC-X7.5", "holds-live", [f"{E}:1837-1842"],
                     "kg_NodeEmbeddings claimed for rx06-qm; enqueue with config rx06-other raises "
                     "EmbeddingIdentityConflict; nothing queued (entry absent); 0 journal records."),
    "VEC-X7.10": live("VEC-X7.10", "holds-live", [f"{E}:1928-1942", f"{E}:1987-2016"],
                      "Worker with model rx06-worker: the entry asking rx06-other is marked ERROR with the conflict "
                      "reason, the other entry is DONE and its vector stored ({'processed': 1, 'errors': 1}); no vector "
                      "for the refused node. The statement says the entry is marked, so queue and route writes are "
                      "expected (the case allows them and checks the outcome)."),
    "VEC-X7.16": live("VEC-X7.16", "holds-live", [f"{Q}:270-305"],
                      "Server Graph.KG.EmbedQueue.ProcessBatch: node not in its queued graph -> ERROR 'is not in "
                      "graph'; node in a graph with no route -> ERROR 'no embedding route'; {'processed': 0, "
                      "'errors': 2}; the journal shows writes to ^EmbedQueue only (no vector table, no registry)."),
    "VEC-X8.4": {"outcome": "intent-undecided", "implementing_code": [f"{S}:1743-1745", f"{S}:1819-1827"],
                 "evidence": [f"run:{LOCAL}"], "finding": "F-0601",
                 "notes": "The pin answers [] (rx-probe-06-local: embedding_inventory returned [] for a SQLCODE -99 "
                          "registry read). The statement (uplift ontology, cites ADMIN_GUIDE.md:1131-1145, which does "
                          "not state it) says it raises; the pin's own docstring says 'An unreadable registry yields "
                          "[]... a status command must not raise on one' (schema.py:1738-1739). F-0601's text covers "
                          "the write path only; the inventory half is a documented choice of the code, so the intent "
                          "is undecided. Not triggerable live without a restricted user."},
    "VEC-X9.2": live("VEC-X9.2", "holds-live", [f"{S}:1928-1932"],
                     "list_quarantine(reason='rx06-bogus'): ValueError listing the reasons; 0 journal records."),
    "VEC-X9.5": run("VEC-X9.5", ["tests/unit/test_227_quarantine_api.py::test_an_unrouted_pair_is_refused",
                                 "tests/unit/test_227_quarantine_api.py::test_no_route_is_created_on_the_operators_behalf"],
                    [f"{S}:2001-2007"],
                    "Upstream unit tests PASSED here. Not live: a quarantined row exists only after the 4.0.0 upgrade "
                    "quarantines a legacy vector (pinned 3.2.0/4.5.1 fixture), and EraseAll leaves the quarantine; "
                    "this lane does not insert rows into it."),
    "VEC-X9.6": run("VEC-X9.6", ["tests/unit/test_227_quarantine_api.py::test_a_width_the_route_does_not_declare_is_refused",
                                 "tests/unit/test_227_quarantine_api.py::test_a_dtype_the_route_does_not_declare_is_refused"],
                    [f"{S}:2012-2042"], "Upstream unit tests PASSED here; not live for the reason given at VEC-X9.5."),
    "VEC-X9.7": run("VEC-X9.7", ["tests/unit/test_227_quarantine_api.py::test_a_node_that_is_not_in_that_graph_is_refused"],
                    [f"{S}:2043-2048"], "Upstream unit test PASSED here; not live for the reason given at VEC-X9.5."),
    "VEC-X10.4": run("VEC-X10.4", ["tests/e2e/test_227_migration.py::test_a_resolver_naming_a_graph_that_does_not_hold_the_node_has_declined"],
                     [f"{G}:895-918"],
                     "Upstream e2e test (live IRIS, validation lane) PASSED here. Not probed in AUDITE: an ambiguous "
                     "legacy row needs a 3.2.0-shaped embedding table (the pinned upgrade fixture)."),
    "VEC-X10.9": live("VEC-X10.9", "holds-live",
                      [f"{G}:257-258", "iris_vector_graph/migrations/docs_and_edge_vectors.py:495-498",
                       "iris_vector_graph/migrations/kg_node_stores.py:142-143", "iris_vector_graph/migrations/_commit.py:18-22"],
                      "Each of the three upgrade steps, called inside a caller transaction ($TLEVEL 1), raised "
                      "CallerTransactionOpenError with 0 journal records."),
    "VEC-X10.10": run("VEC-X10.10", ["tests/unit/test_rekey_resume_dedupe_legacy_keys.py::test_props_that_disagree_on_the_value_refuse_the_rekey",
                                     "tests/unit/test_rekey_resume_dedupe_legacy_keys.py::test_a_legacy_key_that_is_the_idkey_refuses_the_rekey",
                                     "tests/unit/test_rekey_resume_dedupe_legacy_keys.py::test_an_unknown_foreign_key_holding_the_legacy_key_refuses_the_rekey"],
                      [f"{G}:199-206", f"{G}:291-321"],
                      "Upstream unit tests PASSED here: a refused re-key reports key_conflicts / node_key_blockers and "
                      "writes nothing. That the pass then moves no vectors is read in source: writing = not dry_run and "
                      "not rekey.refused (299), and with writing False no drain/reshape/redistribute runs and the "
                      "predicted report carries the blockers (308-321). Not live: needs a pre-4.0 node layout."),
    "VEC-X10.17": run("VEC-X10.17", ["tests/unit/test_230_rekey_compile_order.py::test_an_unscoped_source_refuses_before_any_compile",
                                     "tests/unit/test_230_rekey_compile_order.py::test_the_refusal_names_the_class_and_the_method",
                                     "tests/unit/test_230_rekey_compile_order.py::test_an_absent_source_still_says_nothing_was_dropped"],
                      ["iris_vector_graph/migrations/kg_node_stores.py:144-144",
                       "iris_vector_graph/migrations/kg_node_stores.py:195-233",
                       "iris_vector_graph/migrations/kg_node_stores.py:299-317"],
                      "Upstream unit tests PASSED here. Not live: AUDITE's sources declare graph_id and the rebuild "
                      "entry points are compiled, so neither refused condition exists here."),
    "VEC-X10.92": run("VEC-X10.92", ["tests/unit/test_edge_vector_resume_width.py::test_a_wrong_width_table_that_holds_rows_is_refused_not_dropped",
                                     "tests/unit/test_edge_vector_resume_width.py::test_an_empty_table_at_the_wrong_width_is_dropped_so_prepare_rebuilds_it"],
                      ["iris_vector_graph/migrations/docs_and_edge_vectors.py:224-256"],
                      "Upstream unit tests PASSED here. Not live: needs a staging/quarantine table left by a failed "
                      "4.0.0 edge-vector pass at another width."),
    "VEC-X11.1": live("VEC-X11.1", "holds-live", [f"{V}:227-238", "iris_vector_graph/errors.py:37-48"],
                      "engine.index('rx06-nosuch'): IndexNotFoundError with 'Known indexes: [...]'; 0 journal records."),
    "VEC-X11.3": live("VEC-X11.3", "holds-live", [f"{V}:322-328", "iris_vector_graph/index_protocol.py:92-95"],
                      "build raises NotImplementedError; search is refused earlier by Index.search's status check "
                      "with IndexNotBuiltError (not NotImplementedError as the ontology note says; the statement text "
                      "does not name the exception); 0 journal records."),
    "VEC-X11.7": live("VEC-X11.7", "holds-live", [f"{V}:1937-1967"],
                      "No route: ValueError 'no embedding table is routed'; a route with no vectors: ValueError 'no "
                      "vectors found'; 0 journal records."),
    "VEC-X11.13": live("VEC-X11.13", "holds-live", [f"{V}:2040-2050", "iris_src/src/Graph/KG/IVFIndex.cls:180-183"],
                       "IVFIndex.Insert answers -1 before any SET when the index has no nlist; ivf_insert raises "
                       "ValueError; 0 journal records."),
    "VEC-X11.20": live("VEC-X11.20", "holds-live", [f"{V}:1564-1565", "iris_src/src/Graph/KG/VecIndex.cls:26-46"],
                       "Python vec_create_index and the server VecIndex.Create both refuse 'mahalanobis' before any "
                       "^VecIdx SET; 0 journal records."),
    "VEC-X11.25": live("VEC-X11.25", "holds-live", [f"{V}:1664-1674"],
                       "A document with a 5-wide token among 4-wide ones: ValueError before numpy or any write; 0 "
                       "journal records."),
}

missing = sorted(set(xs) - set(A))
extra = sorted(set(A) - set(xs))
if missing or extra:
    raise SystemExit(f"missing {missing} extra {extra}")
out = {"module": "06", "code": "VEC", "live_run": LIVE, "statements": []}
for sid in xs:
    e = {"id": sid, "text": xs[sid]["text"], **A[sid]}
    out["statements"].append(e)
(HERE / "audit").mkdir(exist_ok=True)
(HERE / "audit" / "06.json").write_text(json.dumps(out, indent=1) + "\n")
from collections import Counter
print(Counter(e["outcome"] for e in out["statements"]), len(out["statements"]))
