#!/usr/bin/env python3
"""Module 15 (integrations: FHIR graph, SQL table mapping, RDF/SHACL/PROV, reification, CLI): live probes of every
stated refusal (INT kind X) reachable in namespace AUDITE, which has no FHIR repository (IRIS Community: no
HS.FHIRServer classes).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 \
        python experiment/playbook-completion/refusals/live_15.py [case ...]

Each case triggers the refused condition through the product's entry point (engine methods, the FHIR graph server
class methods the engine calls, the in-process Cypher HTTP app, the `ivg` CLI as a subprocess) inside a journal
window (rxlib): it holds when the product refuses as stated and the journal shows no net change outside a counter
the case names. Scratch: ids/graphs rx15*, SQL tables IVGAudit.RX15* (dropped). Results: $RUN_DIR/refusals/15/.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rxlib import Lane, raises, returns, either, run_cases, REPO  # noqa: E402
from rx1516 import Listener, hidden_modules, fake_rdflib8, Spy  # noqa: E402

G = "fhir:rx15:none"           # a FHIR graph name that is not registered
STATS = r"ledger_stats|LedgerStats"


def fhir_tables(L):
    return [r[0] for r in L.c.sql("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='Graph_KG' "
                                  "AND TABLE_NAME %STARTSWITH 'fhir_g'")]


def spied(L, fn):
    """Run fn under a Spy; return (result, spy report) via a holder so refusal() still sees the exception."""
    holder = {}

    def run():
        with Spy(L.eng) as s:
            try:
                return fn()
            finally:
                holder.update(s.report())
    return run, holder


# ------------------------------------------------------------------------------------------------ FHIR graph
def c_env(L):
    L.note("INT-F3.2", "environment: FHIR server classes and repository table in AUDITE",
           hs_fhirserver_classes=L.c.sql("SELECT COUNT(*) FROM %Dictionary.CompiledClass WHERE Name %STARTSWITH "
                                         "'HS.FHIRServer'")[0][0],
           hs_repo_table=L.c.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='HS_FHIRServer' "
                                 "AND TABLE_NAME='Repo'")[0][0],
           fhir_graph_tables=fhir_tables(L))


def c_f1_13(L):
    e = L.eng
    cases = {
        "wrong form": ["not a link"],
        "listed twice": ["Library.relatedArtifact", "Library.relatedArtifact"],
        "clashes on its edge name": ["Measure.library", "extension:http://example.org/fhir/library"],
    }
    for k, links in cases.items():
        L.refusal("INT-F1.13", f"engine register json_links {k}", lambda: e.fhir_graph_register(json_links=links),
                  raises("ValueError", match=r"json link"), entry="engine.fhir_graph_register (fhir_links.py)")
    for k, links in cases.items():
        L.refusal("INT-F1.13", f"server ParseJsonLinks {k}",
                  lambda: json.loads(str(L.c.call("Graph.KG.FHIRGraph", "ParseJsonLinks", json.dumps(links)))),
                  returns(lambda r: r.get("status") == "error" and "json link" in r.get("error", ""),
                          "{'status':'error','error':'json link ...'}"),
                  entry="Graph.KG.FHIRGraph.ParseJsonLinks (Native API)")


def c_f3_2(L):
    before = fhir_tables(L)
    L.refusal("INT-F3.2", "engine register without a FHIR repository",
              lambda: L.eng.fhir_graph_register(),
              raises("FHIRGraphError", match=r"no FHIR repository"),
              after=lambda: {"fhir_graph_tables_before": before, "fhir_graph_tables_after": fhir_tables(L)},
              entry="engine.fhir_graph_register -> Graph.KG.FHIRGraph.Register")
    L.refusal("INT-F3.2", "server Register without a FHIR repository",
              lambda: json.loads(str(L.c.call("Graph.KG.FHIRGraph", "Register", "", "[]", 60, ""))),
              returns(lambda r: r.get("status") == "error" and "no FHIR repository" in r.get("error", ""),
                      "{'status':'error'} naming the missing repository"),
              after=lambda: {"fhir_graph_tables_after": fhir_tables(L)},
              entry="Graph.KG.FHIRGraph.Register (Native API)")


def c_f3_3_partial(L):
    """INT-F3.3 cannot be reached without HS_FHIRServer: the repository check answers first. Recorded as such."""
    r = json.loads(str(L.c.call("Graph.KG.FHIRGraph", "Register", "/csp/healthshare/rx15/fhir/r4", "[]", 60, "")))
    L.note("INT-F3.3", "named endpoint in a namespace without a repository: the F3.2 refusal answers first",
           reply=r)


def c_f3_5(L):
    e = L.eng
    L.refusal("INT-F3.5", "engine register interval 30", lambda: e.fhir_graph_register(interval_s=30),
              raises("ValueError", match=r"at least 60"), entry="engine.fhir_graph_register")
    L.refusal("INT-F3.5", "engine register interval 59", lambda: e.fhir_graph_register(interval_s=59),
              raises("ValueError", match=r"at least 60"), entry="engine.fhir_graph_register")
    L.refusal("INT-F3.5", "engine schedule interval 30", lambda: e.fhir_graph_schedule(G, interval_s=30),
              raises("ValueError", match=r"at least 60"), entry="engine.fhir_graph_schedule")


def c_f3_6(L):
    for bad in ("badentry", "Patient.", "Pat ient.x"):
        L.refusal("INT-F3.6", f"engine register denylist {bad!r}",
                  lambda: L.eng.fhir_graph_register(denylist=["Observation.subject", bad]),
                  raises("ValueError", match=r"denylist entry '" + bad.replace(".", r"\.") + "'"),
                  entry="engine.fhir_graph_register")


def c_f8_1(L):
    e = L.eng
    ops = {
        "status": lambda: e.fhir_graph_status(G),
        "rebuild": lambda: e.fhir_graph_rebuild(G),
        "sync": lambda: e.fhir_graph_sync(G),
        "reinterpret": lambda: e.fhir_reinterpret(G),
        "schedule": lambda: e.fhir_graph_schedule(G),
        "unschedule": lambda: e.fhir_graph_unschedule(G),
        "link report": lambda: e.fhir_link_report(G),
        "resolve concepts": lambda: e.fhir_resolve_concepts(G, "rx15cg", ["rx15:c"]),
        "coverage report": lambda: e.fhir_coverage_report(G),
        "concept gaps": lambda: e.fhir_concept_gaps(G),
        "concept ppr (hops 0)": lambda: e.fhir_concept_ppr(G, "rx15cg", ["rx15:c"], hops=0),
        "patient anchors graph=": lambda: e.fhir_patient_anchors("p1", graph=G),
    }
    for k, fn in ops.items():
        L.refusal("INT-F8.1", f"{k} of an unregistered graph", fn,
                  raises("FHIRGraphError", match=r"not registered"), entry=f"engine FHIR graph call ({k})")


def c_f8_2(L):
    e = L.eng
    calls = {
        "status": lambda g: e.fhir_graph_status(g),
        "sync": lambda g: e.fhir_graph_sync(g),
        "rebuild": lambda g: e.fhir_graph_rebuild(g),
        "link report": lambda g: e.fhir_link_report(g),
        "coverage report": lambda g: e.fhir_coverage_report(g),
    }
    for gname, g in (("None", None), ("''", ""), ("'0'", "0"), ("control char", "bad\x01name")):
        for k, fn in calls.items():
            run, spy = spied(L, lambda: fn(g))
            L.refusal("INT-F8.2", f"{k} graph {gname}", run,
                      raises("ValueError", match=r"FHIR graph id is required|reserved|control character"),
                      after=lambda: dict(spy), entry=f"engine FHIR graph call ({k})")
            c = L.cases[-1]
            if c["observations"].get("native_api_requests") or c["observations"].get("fhir_server_calls"):
                c["outcome"] = "not-refused-as-stated"
                c["why"] += " | reached IRIS before refusing"


def c_f8_4(L):
    for bad in ("notakey", "Patient/", "Patient/1/x", "Pat ient/1"):
        run, spy = spied(L, lambda: L.eng.fhir_link_report(G, bad))
        L.refusal("INT-F8.4", f"link report source {bad!r}", run, raises("ValueError", match=r"Type/id"),
                  after=lambda: dict(spy), entry="engine.fhir_link_report")


def c_c1_2(L):
    e = L.eng
    for k, fn in {"hops 11": lambda: e.fhir_expand_concepts("rx15cg", ["rx15:x"], hops=11),
                  "hops -1": lambda: e.fhir_expand_concepts("rx15cg", ["rx15:x"], hops=-1),
                  "hops True": lambda: e.fhir_expand_concepts("rx15cg", ["rx15:x"], hops=True),
                  "direction sideways": lambda: e.fhir_expand_concepts("rx15cg", ["rx15:x"], direction="sideways")
                  }.items():
        run, spy = spied(L, fn)
        L.refusal("INT-C1.2", f"expand {k}", run, raises("ValueError", match=r"hops|direction"),
                  after=lambda: dict(spy), entry="engine.fhir_expand_concepts")
        c = L.cases[-1]
        if c["observations"].get("fhir_server_calls"):
            c["outcome"], c["why"] = "not-refused-as-stated", c["why"] + " | called IRIS"


def c_c1_7(L):
    e = L.eng
    L.refusal("INT-C1.7", "resolve unknown relation", lambda: e.fhir_resolve_concepts(G, "rx15cg", ["rx15:x"],
                                                                                    relations=["nope"]),
              raises("ValueError", match=r"relation 'nope'"), entry="engine.fhir_resolve_concepts")
    L.refusal("INT-C1.7", "resolve param not plain", lambda: e.fhir_resolve_concepts(G, "rx15cg", ["rx15:x"],
                                                                                   params=["code; DROP"]),
              raises("ValueError", match=r"not a search param name"), entry="engine.fhir_resolve_concepts")
    L.refusal("INT-C1.7", "resolve params a bare string", lambda: e.fhir_resolve_concepts(G, "rx15cg", ["rx15:x"],
                                                                                        params="code"),
              raises("ValueError", match=r"params must be"), entry="engine.fhir_resolve_concepts")


def c_c2_6(L):
    e = L.eng
    cases = {
        "via without group_by": dict(via=["subject"]),
        "explain_top without group_by": dict(explain_top=3),
        "bad group name": dict(group_by="encounter"),
        "bad via list": dict(group_by="patient", via=["Bad Param"]),
        "via a string": dict(group_by="patient", via="subject"),
        "bad count": dict(group_by="patient", explain_top=-1),
    }
    for k, kw in cases.items():
        run, spy = spied(L, lambda: e.fhir_concept_ppr(G, "rx15cg", ["rx15:x"], **kw))
        L.refusal("INT-C2.6", f"ppr {k}", run, raises("ValueError", match=r"group_by|via|explain_top"),
                  after=lambda: dict(spy), entry="engine.fhir_concept_ppr")
        c = L.cases[-1]
        if c["observations"].get("native_api_requests") or c["observations"].get("fhir_server_calls"):
            c["outcome"], c["why"] = "not-refused-as-stated", c["why"] + " | reached IRIS before refusing"


def c_c3_4(L):
    e = L.eng
    for k, fn in {"coverage prefix with a space": lambda: e.fhir_coverage_report(G, id_prefix="bad prefix!"),
                  "coverage prefix of 65": lambda: e.fhir_coverage_report(G, id_prefix="a" * 65),
                  "coverage prefix empty": lambda: e.fhir_coverage_report(G, id_prefix=""),
                  "gaps prefix with a space": lambda: e.fhir_concept_gaps(G, id_prefix="bad prefix!"),
                  "gaps top 0": lambda: e.fhir_concept_gaps(G, top=0),
                  "gaps top True": lambda: e.fhir_concept_gaps(G, top=True)}.items():
        run, spy = spied(L, fn)
        L.refusal("INT-C3.4", k, run, raises("ValueError", match=r"id_prefix|top must"),
                  after=lambda: dict(spy), entry="engine.fhir_coverage_report / fhir_concept_gaps")
        c = L.cases[-1]
        if c["observations"].get("fhir_server_calls"):
            c["outcome"], c["why"] = "not-refused-as-stated", c["why"] + " | called IRIS"


def c_c4_3(L):
    for bad in ("bad id!", "a" * 65, "", "p/1"):
        L.refusal("INT-C4.3", f"anchors patient id {bad[:12]!r}", lambda: L.eng.fhir_patient_anchors(bad),
                  raises("ValueError", match=r"patient_id must be a FHIR id"), entry="engine.fhir_patient_anchors")


def c_c4_5(L):
    """The Cypher HTTP app (in process, no lifespan: no Bolt listener), its engine the lane's own."""
    os.environ.pop("IVG_API_KEY", None)
    os.environ.pop("IVG_READ_ONLY", None)
    os.environ.pop("FHIR_BASE_URL", None)
    from starlette.testclient import TestClient
    from iris_vector_graph import cypher_api
    cypher_api._engine_cache = L.eng
    tc = TestClient(cypher_api.app)
    try:
        with Listener("record") as lis:
            for k, allowed in (("no allow-list", None), ("a prefix of the listed base", lis.url + "/fhir"),
                               ("another listed base", "http://127.0.0.1:9/fhir")):
                if allowed is None:
                    os.environ.pop("IVG_FHIR_ALLOWED_BASES", None)
                else:
                    os.environ["IVG_FHIR_ALLOWED_BASES"] = allowed
                target = lis.url + ("/fhir-other" if allowed and allowed.startswith(lis.url) else "/fhir")
                n0 = len(lis.connections)
                L.refusal("INT-C4.5", f"POST /api/cypher fhir_base_url unlisted ({k})",
                          lambda: (lambda r: {"status": r.status_code, "body": r.text[:600]})(
                              tc.post("/api/cypher", json={"query": "RETURN 1 AS n", "fhir_patient_id": "p1",
                                                           "fhir_base_url": target})),
                          returns(lambda r: r["status"] == 400 and "IVG_FHIR_ALLOWED_BASES" in r["body"],
                                  "HTTP 400 naming IVG_FHIR_ALLOWED_BASES"),
                          after=lambda: {"fetches_seen_by_target": len(lis.connections) - n0},
                          entry="cypher_api POST /api/cypher (in-process ASGI)")
                c = L.cases[-1]
                if c["observations"].get("fetches_seen_by_target"):
                    c["outcome"], c["why"] = "not-refused-as-stated", c["why"] + " | the target was fetched"
            # control: the listed base is fetched (so the listener would have seen an unlisted fetch)
            os.environ["IVG_FHIR_ALLOWED_BASES"] = lis.url + "/fhir"
            n0 = len(lis.connections)
            r = tc.post("/api/cypher", json={"query": "RETURN 1 AS n", "fhir_patient_id": "p1",
                                             "fhir_base_url": lis.url + "/fhir/"})
            L.note("INT-C4.5", "control: a listed base (trailing slash) is fetched", status=r.status_code,
                   fetches_seen_by_target=len(lis.connections) - n0)
    finally:
        os.environ.pop("IVG_FHIR_ALLOWED_BASES", None)
        cypher_api._engine_cache = None


def c_c5_1(L):
    e = L.eng
    for k, fn in {"empty system": lambda: e.code_crosswalk_add("", "RX15C", "rx15:x"),
                  "empty code": lambda: e.code_crosswalk_add("urn:rx15", "", "rx15:x"),
                  "empty target": lambda: e.code_crosswalk_add("urn:rx15", "RX15C", ""),
                  "bad relation": lambda: e.code_crosswalk_add("urn:rx15", "RX15C", "rx15:x", relation="nope")
                  }.items():
        L.refusal("INT-C5.1", f"crosswalk {k}", fn, raises("ValueError", match=r"required|relation"),
                  entry="engine.code_crosswalk_add")


def _mk_tables(L):
    for t in ("IVGAudit.RX15Pat", "IVGAudit.RX15Vis"):
        try:
            L.c.sql(f"DROP TABLE {t}")
        except Exception:  # noqa: BLE001
            pass
    L.c.sql("CREATE TABLE IVGAudit.RX15Pat (pid VARCHAR(32) PRIMARY KEY, name VARCHAR(64))")
    L.c.sql("CREATE TABLE IVGAudit.RX15Vis (vid VARCHAR(32) PRIMARY KEY, pid VARCHAR(32))")
    L.c.conn.commit()


def _drop_tables(L):
    for lbl in ("RX15Pat", "RX15Vis"):
        try:
            L.eng.remove_table_mapping(lbl)
        except Exception:  # noqa: BLE001
            pass
    for t in ("IVGAudit.RX15Pat", "IVGAudit.RX15Vis"):
        try:
            L.c.sql(f"DROP TABLE {t}")
        except Exception:  # noqa: BLE001
            pass
    L.c.conn.commit()


def c_mapping(L):
    e = L.eng
    _mk_tables(L)
    try:
        # M1.2
        for k, fn in {"table": lambda: e.map_sql_table("IVGAudit.RX15Pat; DROP", "pid", "RX15L"),
                      "column": lambda: e.map_sql_table("IVGAudit.RX15Pat", "pid)--", "RX15L"),
                      "label": lambda: e.map_sql_table("IVGAudit.RX15Pat", "pid", "RX15 L")}.items():
            L.refusal("INT-M1.2", f"map_sql_table {k} not a plain name", fn,
                      raises("ValueError", match=r"Invalid characters"), entry="engine.map_sql_table")
        # M1.3
        L.refusal("INT-M1.3", "map_sql_table table missing",
                  lambda: e.map_sql_table("IVGAudit.RX15NoSuch", "pid", "RX15L"),
                  raises("ValueError", match=r"not found"), entry="engine.map_sql_table")
        L.refusal("INT-M1.3", "map_sql_table id column missing",
                  lambda: e.map_sql_table("IVGAudit.RX15Pat", "nosuchcol", "RX15L"),
                  raises("ValueError", match=r"not found"), entry="engine.map_sql_table")
        # M1.6
        L.refusal("INT-M1.6", "map_sql_relationship without fk or join table",
                  lambda: e.map_sql_relationship("RX15Vis", "RX15_OF", "RX15Pat"),
                  raises("ValueError", match=r"target_fk or via_table"), entry="engine.map_sql_relationship")
        L.refusal("INT-M1.6", "map_sql_relationship source label not mapped",
                  lambda: e.map_sql_relationship("RX15Vis", "RX15_OF", "RX15Pat", target_fk="pid"),
                  raises("ValueError", match=r"Source label"), entry="engine.map_sql_relationship")
        e.map_sql_table("IVGAudit.RX15Vis", "vid", "RX15Vis")
        L.c.conn.commit()
        L.refusal("INT-M1.6", "map_sql_relationship target label not mapped",
                  lambda: e.map_sql_relationship("RX15Vis", "RX15_OF", "RX15Pat", target_fk="pid"),
                  raises("ValueError", match=r"Target label"), entry="engine.map_sql_relationship")
        # M1.8
        L.refusal("INT-M1.8", "remove_table_mapping of a label never mapped",
                  lambda: e.remove_table_mapping("RX15NeverMapped"),
                  raises("ValueError", match=r"not found in table_mappings"), entry="engine.remove_table_mapping")
        # M1.12
        L.refusal("INT-M1.12", "attach_embeddings_to_table of an unmapped label",
                  lambda: e.attach_embeddings_to_table("RX15NeverMapped", ["name"]),
                  raises("TableNotMappedError", match=r"not registered"),
                  entry="engine.attach_embeddings_to_table")
    finally:
        _drop_tables(L)


# ------------------------------------------------------------------------------------------------ RDF / SHACL / PROV
SHAPES = "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"


def c_rdf(L):
    e = L.eng
    out = L.out
    with hidden_modules("rdflib"):
        L.refusal("INT-R1.18", "export_rdf without rdflib", lambda: e.export_rdf(str(out / "never1.ttl")),
                  raises("ImportError", match=r"iris-vector-graph\[rdf\]"),
                  after=lambda: {"file_written": (out / "never1.ttl").exists()}, entry="engine.export_rdf")
        L.refusal("INT-R1.18", "export_rdf_from_cypher without rdflib",
                  lambda: e.export_rdf_from_cypher("RETURN 1 AS s", str(out / "never2.ttl")),
                  raises("ImportError", match=r"iris-vector-graph\[rdf\]"),
                  after=lambda: {"file_written": (out / "never2.ttl").exists()}, entry="engine.export_rdf_from_cypher")
        L.refusal("INT-S1.11", "validate_shacl without rdflib", lambda: e.validate_shacl(SHAPES),
                  raises("ImportError", match=r"iris-vector-graph\[rdf\]"), entry="engine.validate_shacl")
        L.refusal("INT-V1.10", "prov_export without rdflib", lambda: e.prov_export(str(out / "never3.ttl")),
                  raises("ImportError", match=r"rdflib is required for PROV-O"),
                  after=lambda: {"file_written": (out / "never3.ttl").exists()}, entry="engine.prov_export")
    with hidden_modules("pyshacl"):
        L.refusal("INT-S1.11", "validate_shacl without pySHACL", lambda: e.validate_shacl(SHAPES),
                  raises("ImportError", match=r"pyshacl is required.*iris-vector-graph\[rdf\]"),
                  entry="engine.validate_shacl")
    # INT-R1.19: rdflib 8 (no ConjunctiveGraph): the refusal should name the version
    for k, fn in {"export_rdf": lambda: e.export_rdf(str(out / "never4.ttl")),
                  "validate_shacl": lambda: e.validate_shacl(SHAPES)}.items():
        with fake_rdflib8():
            L.refusal("INT-R1.19", f"{k} with rdflib 8.0.0 lacking ConjunctiveGraph", fn,
                      raises("ImportError", match=r"8\.0|version"), entry=f"engine.{k}")
    # INT-V1.10 second half: one activity's lookup works without rdflib
    e.create_edge_temporal("rx15:t1", "rx15saw", "rx15:t2", timestamp=1_700_000_000)
    L.c.conn.commit()
    window = e._get_temporal_edges_window(None, None)
    eid = next((x.get("edge_id") for x in window if x.get("source") == "rx15:t1"), None)
    with hidden_modules("rdflib"):
        try:
            got = e.prov_as_dict(eid)
            res = {"answered": True, "keys": sorted(got) if isinstance(got, dict) else repr(got)[:200]}
        except Exception as ex:  # noqa: BLE001
            res = {"answered": False, "error": f"{type(ex).__name__}: {ex}"[:300]}
    L.note("INT-V1.10", "prov_as_dict without rdflib (the lookup that still works)", edge_id=eid, **res)
    # INT-V1.4: a named graph's temporal edge never reaches PROV export
    e.create_edge_temporal("rx15:n1", "rx15named", "rx15:n2", timestamp=1_700_000_100, graph="rx15gt")
    L.c.conn.commit()
    p = out / "prov-named.ttl"

    def prov_named():
        rep = e.prov_export(str(p), ts_start=1_700_000_099, ts_end=1_700_000_101)
        text = p.read_text() if p.exists() else ""
        return {"report": rep, "mentions_named_edge": ("rx15named" in text) or ("rx15:n1" in text)}
    L.refusal("INT-V1.4", "prov_export over a window holding only a named graph's temporal edge", prov_named,
              returns(lambda r: not r["mentions_named_edge"] and (r["report"] or {}).get("activities", 0) == 0,
                      "no activity for the named graph's edge"), entry="engine.prov_export")
    # control: a default-graph edge in that window is exported
    e.create_edge_temporal("rx15:d1", "rx15default", "rx15:d2", timestamp=1_700_000_100)
    L.c.conn.commit()
    rep = e.prov_export(str(p), ts_start=1_700_000_099, ts_end=1_700_000_101)
    L.note("INT-V1.4", "control: a default-graph temporal edge in the window is exported",
           report=rep, mentions_default=("rx15default" in p.read_text()) if p.exists() else None)


def c_shacl(L):
    e = L.eng
    with Listener("http500") as lis:
        L.refusal("INT-S1.4", "shapes URL answering HTTP 500", lambda: e.validate_shacl(lis.url + "/shapes.ttl"),
                  raises("OSError", match=r"Could not fetch shapes"), entry="engine.validate_shacl")
    L.refusal("INT-S1.4", "shapes URL refusing the connection", lambda: e.validate_shacl("http://127.0.0.1:9/s.ttl"),
              raises("OSError", match=r"Could not fetch shapes"), entry="engine.validate_shacl")
    with Listener("silent") as lis:
        L.refusal("INT-S1.4", "shapes URL that never answers (30 s timeout)",
                  lambda: e.validate_shacl(lis.url + "/slow.ttl"), raises("OSError"),
                  entry="engine.validate_shacl")
    for k, v in {"int": 12345, "list": ["a"], "bytes": b"x"}.items():
        L.refusal("INT-S1.6", f"shapes of another kind ({k})", lambda: e.validate_shacl(v),
                  raises("ValueError", match=r"shapes_source must be"), entry="engine.validate_shacl")


# ------------------------------------------------------------------------------------------------ reification
def c_reify(L):
    e = L.eng
    e.create_node("rx15:a", labels=["RX15"], graph="rx15g")
    e.create_node("rx15:b", labels=["RX15"], graph="rx15g")
    e.create_edge("rx15:a", "rx15rel", "rx15:b", graph="rx15g")
    L.c.conn.commit()
    eid = int(L.c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s='rx15:a' AND o_id='rx15:b'")[0][0])
    e.reify_edge(eid, reifier_id="rx15:reif", props={"why": "first"})
    L.c.conn.commit()
    e.create_edge("rx15:b", "rx15rel", "rx15:a", graph="rx15g")
    L.c.conn.commit()
    eid2 = int(L.c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s='rx15:b' AND o_id='rx15:a'")[0][0])
    L.refusal("INT-E1.4", "reify another edge with an already linked reifier id",
              lambda: e.reify_edge(eid2, reifier_id="rx15:reif", props={"why": "second"}),
              raises("GraphWriteError"),
              after=lambda: {"links": L.c.sql("SELECT reifier_id, edge_id FROM Graph_KG.rdf_reifications "
                                              "WHERE reifier_id='rx15:reif'"),
                             "props": L.c.sql("SELECT \"key\", val FROM Graph_KG.rdf_props WHERE s='rx15:reif'")},
              entry="engine.reify_edge")
    L.refusal("INT-E1.4", "reify the same edge again with its reifier id",
              lambda: e.reify_edge(eid, reifier_id="rx15:reif", props={"why": "again"}),
              raises("GraphWriteError"),
              after=lambda: {"props": L.c.sql("SELECT \"key\", val FROM Graph_KG.rdf_props WHERE s='rx15:reif'")},
              entry="engine.reify_edge")
    # INT-E1.5: strict ledger mode
    L.eng.ledger.enable(strict=True)
    L.c.conn.commit()
    L.fresh_engine()
    e = L.eng
    try:
        L.refusal("INT-E1.5", "reify_edge in strict ledger mode",
                  lambda: e.reify_edge(eid2, reifier_id="rx15:reif2"),
                  raises("LedgerStrictModeError"), allowed=[STATS], entry="engine.reify_edge")
        L.refusal("INT-E1.5", "delete_reification in strict ledger mode",
                  lambda: e.delete_reification("rx15:reif"),
                  raises("LedgerStrictModeError"), allowed=[STATS], entry="engine.delete_reification")
    finally:
        L.reset()


# ------------------------------------------------------------------------------------------------ inference, CLI
def c_x80_86(L):
    kind = str(L.c.call("Graph.KG.Adjacency", "IndexKind"))
    L.note("INT-X80.86", "AUDITE's adjacency index (the refusal applies only where it is absent)", index_kind=kind,
           engine_adjacency_indexed=bool(L.eng._adjacency_indexed))


def _cli(args, env_extra=None, drop=("IRIS_HOST", "IRIS_PORT", "IRIS_NAMESPACE", "IRIS_USERNAME", "IRIS_PASSWORD")):
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, "-m", "iris_vector_graph.cli", *args], cwd=str(REPO), env=env,
                       capture_output=True, text=True, timeout=120)
    return {"exit": r.returncode, "stderr": r.stderr[-800:], "stdout": r.stdout[-300:]}


def c_cli(L):
    for args in (["fhir", "register"], ["fhir", "status", G], ["fhir", "rebuild", G], ["fhir", "sync", "--once", G],
                 ["fhir", "links", G], ["fhir", "schedule", G], ["embeddings", "inventory"]):
        L.refusal("INT-B90.90", "ivg " + " ".join(args[:2]) + " with no IRIS address", lambda: _cli(args),
                  returns(lambda r: r["exit"] == 1 and "IRIS_HOST" in r["stderr"] and "--iris-host" in r["stderr"],
                          "exit 1, stderr naming IRIS_HOST and --iris-host"), entry="ivg CLI (subprocess)")
    with Listener("record") as lis:
        n0 = len(lis.connections)
        L.refusal("INT-B90.91", "ivg fhir sync without --once (IRIS_HOST at a listener)",
                  lambda: _cli(["fhir", "sync", G], {"IRIS_HOST": "127.0.0.1", "IRIS_PORT": str(lis.port)}),
                  returns(lambda r: r["exit"] == 2 and "fhir schedule" in r["stderr"] and "--once" in r["stderr"],
                          "click UsageError (exit 2) pointing to `ivg fhir schedule`"),
                  after=lambda: {"connections_to_iris_address": len(lis.connections) - n0},
                  entry="ivg CLI (subprocess)")
        c = L.cases[-1]
        if c["observations"].get("connections_to_iris_address"):
            c["outcome"], c["why"] = "not-refused-as-stated", c["why"] + " | it connected first"


# ------------------------------------------------------------------------------------------------ partial FHIR
def c_partial(L):
    """Parts of FHIR-repository refusals reachable without a repository: the server's own classifier and json-link
    extractor, driven directly (the sync path that calls them needs HS.FHIRServer)."""
    import iris
    o = L.c.o
    obj = o.classMethodObject("Graph.KG.FHIRGraph", "%New")
    for ref, rel in (("#contained1", "#contained1"), ("urn:uuid:1234", "urn:uuid:1234"), ("Patient", "Patient"),
                     ("Patient/1/x", "Patient/1/x"), ("/1", "/1")):
        t = iris.IRISReference(None)
        L.refusal("INT-F1.5", f"Classify {ref!r} (server method, no repository)",
                  lambda: str(obj.invoke("Classify", ref, rel, t)),
                  returns(lambda r: r == "skip", "'skip'"), entry="Graph.KG.FHIRGraph.Classify (instance, Native API)")
    t = iris.IRISReference(None)
    L.note("INT-F1.5", "control: Classify a plain Type/id", answer=str(obj.invoke("Classify", "Patient/p1",
                                                                                   "Patient/p1", t)))
    ext = json.dumps(["extension:http://example.org/fhir/rx15link"])
    deep = {"resourceType": "Library", "id": "l1"}
    cur = deep
    for _ in range(70):
        cur["extension"] = [{"url": "http://example.org/other", "x": {}}]
        cur = cur["extension"][0]["x"]
    many = {"resourceType": "Library", "id": "l2",
            "extension": [{"url": "http://example.org/fhir/rx15link", "valueCanonical": f"http://c/{i}"}
                          for i in range(10001)]}
    for k, body in (("text not JSON", "{not json"), ("nesting deeper than 64", json.dumps(deep)),
                    ("more than 10000 json link matches", json.dumps(many))):
        L.refusal("INT-F1.14", f"ExtractLinks {k} (server method, no repository)",
                  lambda: json.loads(str(L.c.call("Graph.KG.FHIRGraph", "ExtractLinks", body, ext))),
                  returns(lambda r: r.get("status") == "error", "{'status':'error'}"),
                  entry="Graph.KG.FHIRGraph.ExtractLinks (Native API)")


CASES = [("env", c_env), ("f1_13", c_f1_13), ("f3_2", c_f3_2), ("f3_3", c_f3_3_partial), ("f3_5", c_f3_5),
         ("f3_6", c_f3_6), ("f8_1", c_f8_1), ("f8_2", c_f8_2), ("f8_4", c_f8_4), ("c1_2", c_c1_2), ("c1_7", c_c1_7),
         ("c2_6", c_c2_6), ("c3_4", c_c3_4), ("c4_3", c_c4_3), ("c4_5", c_c4_5), ("c5_1", c_c5_1),
         ("mapping", c_mapping), ("rdf", c_rdf), ("shacl", c_shacl), ("reify", c_reify), ("x80_86", c_x80_86),
         ("cli", c_cli), ("partial", c_partial)]


def main():
    only = sys.argv[1:] or None
    name = os.environ.get("RX_RESULTS", "results.json" if not only else "results-partial.json")
    with Lane("15") as L:
        L.reset()
        L.control()
        run_cases(L, CASES, only)
        L.reset()
        L.save(name)


if __name__ == "__main__":
    main()
