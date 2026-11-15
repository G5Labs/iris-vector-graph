#!/usr/bin/env python3
"""Module 15 (INT) live checks in AUDITC, journal-validated (breadth lane C).

    flock -s $RUN_DIR/breadth-c/auditc.lock timeout 900 python live15.py <part> [<part> ...]

Parts: register (F-1511 refusal path, INT-F3.2, INT-F8.1 cells), reify (F-1502, INT-E1), delreif (F-1503),
bridge (F-1507, fhir_bridge_add, code_crosswalk_add footprints), tablemap (F-1504, INT-M1 footprints),
anchors (F-1508 via the Cypher HTTP handler in-process), rdf (export/SHACL/PROV readers, F-1501), memory (F-1510).
All scratch data uses the c15 prefix and is removed at the end of each part. Results go to
$RUN_DIR/breadth-c/15/<part>.json; the console gets a summary.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from jcheck import Lane, dump, run_dir  # noqa: E402

warnings.simplefilter("ignore", DeprecationWarning)
OUT = run_dir("15")

# `iris session` (the journal reader) occasionally exits 133 when several lanes open sessions at once; retry it a few
# times in this process only (the oracle itself is unchanged).
import journal as _journal  # noqa: E402

_orig_session = _journal._session


def _session_retry(script, timeout=600):
    last = None
    for i in range(6):
        try:
            return _orig_session(script, timeout)
        except RuntimeError as ex:  # noqa: PERF203
            last = ex
            time.sleep(2 + 3 * i)
    raise last


_journal._session = _session_retry


def slim(r):
    return {k: v for k, v in r.items() if k not in ("raw", "traceback")}


def gkey(L, g):
    return str(L.c.call("Graph.KG.GraphKey", "ForIndex", g))


def kg_defined(L, *subs):
    try:
        return int(L.c.o.isDefined("^KG", *subs))
    except Exception as e:  # noqa: BLE001
        return f"error {e}"


# ------------------------------------------------------------------------------------------------ register
def part_register(L):
    res = {}
    c = L.c
    res["hs_fhirserver_classes"] = c.sql("SELECT COUNT(*) FROM %Dictionary.CompiledClass WHERE Name %STARTSWITH 'HS.FHIRServer'")[0][0]
    res["hs_repo_table"] = c.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'HS_FHIRServer'")[0][0]
    res["fhir_graphs_before"] = c.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='Graph_KG' AND TABLE_NAME LIKE 'fhir_%'")[0][0]
    # 1. the engine's register (Python validation, lazy table creation, then the server's Register)
    r = L.journaled("engine.fhir_graph_register()", lambda: L.eng.fhir_graph_register())
    res["engine_register"] = slim(r)
    # 2. the server method directly, with a json-link list (so ParseLinks runs first)
    r = L.journaled("Graph.KG.FHIRGraph.Register direct",
                    lambda: c.call("Graph.KG.FHIRGraph", "Register", "", "[]", 60, ""))
    res["server_register"] = slim(r)
    res["fhir_graphs_after"] = c.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='Graph_KG' AND TABLE_NAME LIKE 'fhir_%'")[0][0]
    # 3. every other graph call on an unregistered graph (cells "no tables" x commands)
    g = "fhir:c15:none"
    ops = {
        "status": lambda: L.eng.fhir_graph_status(g),
        "rebuild": lambda: L.eng.fhir_graph_rebuild(g),
        "sync": lambda: L.eng.fhir_graph_sync(g),
        "reinterpret": lambda: L.eng.fhir_reinterpret(g),
        "schedule": lambda: L.eng.fhir_graph_schedule(g),
        "unschedule": lambda: L.eng.fhir_graph_unschedule(g),
        "link_report": lambda: L.eng.fhir_link_report(g, "Patient/p1"),
        "patient_anchors_no_graph_arg": lambda: L.eng.fhir_patient_anchors("p1"),
    }
    res["calls"] = {k: slim(L.journaled(k, f)) for k, f in ops.items()}
    # 4. task manager: no IVG FHIR sync task exists in this namespace
    res["sync_tasks"] = c.sql("SELECT COUNT(*) FROM %SYS.Task WHERE TaskClass = 'Graph.KG.FHIRGraphSyncTask'") \
        if False else "not read (Task table lives in %SYS; read-only check skipped)"
    # 5. the lock global is not left behind
    res["lock_global_defined"] = int(c.o.isDefined("^IVG.FHIRGraph", g))
    # 6. erase of a graph in a namespace with no FHIR tables (INT-F10.5)
    L.eng.create_node("c15:fx", graph="c15fhir")
    r = L.journaled("erase_graph(c15fhir) without FHIR tables", lambda: L.eng.erase_graph("c15fhir"))
    res["erase_without_fhir_tables"] = slim(r)
    return res


# ------------------------------------------------------------------------------------------------ reify
def edge_id(L, s, o, g):
    rows = L.c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s = ? AND o_id = ? AND graph_id = ?", s, o, g)
    return int(rows[0][0]) if rows else None


def part_reify(L):
    res = {}
    e = L.eng
    c = L.c
    g = "c15g1"
    e.create_node("c15:a", labels=["C15A"], graph=g)
    e.create_node("c15:b", labels=["C15B"], graph=g)
    e.create_edge("c15:a", "c15rel", "c15:b", graph=g)
    eid = edge_id(L, "c15:a", "c15:b", g)
    res["edge_id"] = eid
    r = L.journaled("reify_edge", lambda: e.reify_edge(eid, reifier_id="c15:reif1",
                                                       props={"source": "tenant-c15g1-secret", "confidence": 0.9}))
    res["reify_edge"] = slim(r)
    res["reifier_rows"] = {
        "nodes": c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = 'c15:reif1'"),
        "labels": c.sql("SELECT graph_id, label FROM Graph_KG.rdf_labels WHERE s = 'c15:reif1'"),
        "props": c.sql("SELECT graph_id, \"key\", val FROM Graph_KG.rdf_props WHERE s = 'c15:reif1'"),
        "link": c.sql("SELECT reifier_id, edge_id FROM Graph_KG.rdf_reifications WHERE reifier_id = 'c15:reif1'"),
    }
    res["edge_graph"] = c.sql("SELECT graph_id FROM Graph_KG.rdf_edges WHERE edge_id = ?", eid)
    r = L.journaled("get_reifications", lambda: e.get_reifications(eid))
    res["get_reifications"] = slim(r)
    res["default_graph_read_of_reifier"] = e.get_nodes(["c15:reif1"])
    res["named_graph_read_of_reifier"] = e.get_nodes(["c15:reif1"], graph=g)
    # a duplicate reifier id is refused (INT-E1.4)
    r = L.journaled("reify_edge duplicate id", lambda: e.reify_edge(eid, reifier_id="c15:reif1"))
    res["reify_duplicate"] = slim(r)
    # missing edge: None, nothing written (INT-E1.2)
    r = L.journaled("reify_edge missing edge", lambda: e.reify_edge(-424242, reifier_id="c15:reifX"))
    res["reify_missing_edge"] = slim(r)
    # F-1502: erase the edge's graph
    r = L.journaled("erase_graph(c15g1)", lambda: e.erase_graph(g))
    res["erase_graph"] = slim(r)
    res["after_erase"] = {
        "edge": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE edge_id = ?", eid)[0][0],
        "link": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_reifications WHERE reifier_id = 'c15:reif1'")[0][0],
        "reifier_node": c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = 'c15:reif1'"),
        "reifier_props": c.sql("SELECT graph_id, \"key\", val FROM Graph_KG.rdf_props WHERE s = 'c15:reif1'"),
        "reifier_labels": c.sql("SELECT graph_id, label FROM Graph_KG.rdf_labels WHERE s = 'c15:reif1'"),
        "default_graph_get_node": e.get_node("c15:reif1"),
        "cypher_default_graph": repr(e.execute_cypher(
            "MATCH (n:Reification) WHERE n.id = 'c15:reif1' RETURN n.id, n.source").rows),
    }
    # parity: delete_node removes the reifier of the node's edge (INT-E1.9)
    g2 = "c15g1b"
    e.create_node("c15:a2", graph=g2)
    e.create_node("c15:b2", graph=g2)
    e.create_edge("c15:a2", "c15rel", "c15:b2", graph=g2)
    eid2 = edge_id(L, "c15:a2", "c15:b2", g2)
    e.reify_edge(eid2, reifier_id="c15:reif2", props={"source": "x"})
    r = L.journaled("delete_node(c15:a2, graph=c15g1b)", lambda: e.delete_node("c15:a2", graph=g2))
    res["delete_node_parity"] = slim(r)
    res["after_delete_node"] = {
        "reifier2_node": c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = 'c15:reif2'"),
        "reifier2_props": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE s = 'c15:reif2'")[0][0],
    }
    # cleanup
    for nid in ("c15:reif1", "c15:reif2"):
        try:
            e.delete_node(nid, graph="")
        except Exception:  # noqa: BLE001
            pass
    for gg in (g, g2):
        e.erase_graph(gg)
    res["cleanup_left"] = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'c15:'")[0][0]
    return res


# ------------------------------------------------------------------------------------------------ delete_reification
def part_delreif(L):
    res = {}
    e, c = L.eng, L.c
    g = "c15g2"
    e.create_node("c15:x", labels=["C15L"], properties={"p": "named-graph-value"}, graph=g)
    e.create_node("c15:y", graph=g)
    e.create_edge("c15:x", "c15r", "c15:y", graph=g)
    e.create_node("c15:x", labels=["C15D"], properties={"p": "default-graph-value"})  # same id, default graph
    k = gkey(L, g)
    res["gkey"] = k
    before = {
        "nodes": c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = 'c15:x' ORDER BY graph_id"),
        "labels": c.sql("SELECT graph_id, label FROM Graph_KG.rdf_labels WHERE s = 'c15:x' ORDER BY graph_id"),
        "props": c.sql("SELECT graph_id, \"key\" FROM Graph_KG.rdf_props WHERE s = 'c15:x' ORDER BY graph_id"),
        "edges": c.sql("SELECT graph_id, p, o_id FROM Graph_KG.rdf_edges WHERE s = 'c15:x'"),
        "kg_out": kg_defined(L, "out", k, "c15:x"),
        "kg_label_named": kg_defined(L, "label", k, "C15L", "c15:x"),
        "kg_label_default": kg_defined(L, "label", 0, "C15D", "c15:x"),
        "is_reifier": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_reifications WHERE reifier_id = 'c15:x'")[0][0],
    }
    res["before"] = before
    r = L.journaled("delete_reification(c15:x) on a non-reifier", lambda: e.delete_reification("c15:x"))
    res["delete_reification"] = slim(r)
    res["after"] = {
        "nodes": c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = 'c15:x' ORDER BY graph_id"),
        "labels": c.sql("SELECT graph_id, label FROM Graph_KG.rdf_labels WHERE s = 'c15:x' ORDER BY graph_id"),
        "props": c.sql("SELECT graph_id, \"key\" FROM Graph_KG.rdf_props WHERE s = 'c15:x' ORDER BY graph_id"),
        "edges": c.sql("SELECT graph_id, p, o_id FROM Graph_KG.rdf_edges WHERE s = 'c15:x'"),
        "kg_out": kg_defined(L, "out", k, "c15:x"),
        "kg_label_named": kg_defined(L, "label", k, "C15L", "c15:x"),
        "kg_label_default": kg_defined(L, "label", 0, "C15D", "c15:x"),
        "cypher_named": repr(e.execute_cypher("USE GRAPH 'c15g2' MATCH (a)-[r]->(b) WHERE b.id = 'c15:y' RETURN a.id, type(r)").rows),
        "cypher_named_err": getattr(e.execute_cypher("USE GRAPH 'c15g2' MATCH (a)-[r]->(b) WHERE b.id = 'c15:y' RETURN a.id, type(r)"), "error", None),
    }
    try:
        res["verify_graph"] = e.verify_graph(g) if hasattr(e, "verify_graph") else None
    except Exception as ex:  # noqa: BLE001
        res["verify_graph"] = f"{type(ex).__name__}: {ex}"
    # cleanup
    e.erase_graph(g)
    try:
        e.delete_node("c15:x", graph="")
    except Exception:  # noqa: BLE001
        pass
    res["cleanup_left"] = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'c15:'")[0][0]
    res["cleanup_left_kg_label_default"] = kg_defined(L, "label", 0, "C15D", "c15:x")
    return res


def part_delreif2(L):
    """delete_reification on a non-reifier id that has NO edges, present in a named graph and the default graph."""
    res = {}
    e, c = L.eng, L.c
    g = "c15g2b"
    e.create_node("c15:z", labels=["C15ZN"], properties={"p": "tenant-value"}, graph=g)
    e.create_node("c15:z", labels=["C15ZD"], properties={"p": "default-value"})
    k = gkey(L, g)

    def state():
        return {
            "nodes": c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = 'c15:z' ORDER BY graph_id"),
            "labels": c.sql("SELECT graph_id, label FROM Graph_KG.rdf_labels WHERE s = 'c15:z' ORDER BY graph_id"),
            "props": c.sql("SELECT graph_id, \"key\", val FROM Graph_KG.rdf_props WHERE s = 'c15:z' ORDER BY graph_id"),
            "kg_label_named": kg_defined(L, "label", k, "C15ZN", "c15:z"),
            "kg_label_default": kg_defined(L, "label", 0, "C15ZD", "c15:z"),
            "kg_prop_named": kg_defined(L, "prop", k, "c15:z"),
            "is_reifier": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_reifications WHERE reifier_id = 'c15:z'")[0][0],
        }
    res["before"] = state()
    r = L.journaled("delete_reification(c15:z) on an edge-less non-reifier", lambda: e.delete_reification("c15:z"))
    res["delete_reification"] = slim(r)
    res["after"] = state()
    res["get_node_named_after"] = e.get_node("c15:z", graph=g)
    for gg in (g, ""):
        try:
            e.delete_node("c15:z", graph=gg)
        except Exception:  # noqa: BLE001
            pass
    e.erase_graph(g)
    res["cleanup_left"] = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'c15:'")[0][0]
    res["cleanup_left_kg"] = [kg_defined(L, "label", k, "C15ZN", "c15:z"), kg_defined(L, "label", 0, "C15ZD", "c15:z")]
    return res


# ------------------------------------------------------------------------------------------------ bridge / crosswalk
def part_bridge(L):
    res = {}
    e, c = L.eng, L.c
    others = c.sql("SELECT COUNT(*) FROM Graph_KG.fhir_bridges WHERE fhir_code NOT LIKE 'C15%'")[0][0]
    res["foreign_bridge_rows"] = others
    e.create_node("c15:anchor", labels=["C15Concept"], graph="c15g3")  # only in a named graph
    r = L.journaled("fhir_bridge_add", lambda: e.fhir_bridge_add("C15CODE1", "c15:anchor", bridge_type="c15bt"))
    res["fhir_bridge_add"] = slim(r)
    res["rows"] = {
        "bridges": c.sql("SELECT fhir_code, kg_node_id, bridge_type FROM Graph_KG.fhir_bridges WHERE fhir_code LIKE 'C15%'"),
        "crosswalk": c.sql("SELECT code_system_uri, code, target_graph, target_node_id, relation FROM Graph_KG.code_crosswalk WHERE code LIKE 'C15%'"),
        "anchor_graphs": c.sql("SELECT graph_id FROM Graph_KG.nodes WHERE node_id = 'c15:anchor'"),
    }
    r = L.journaled("get_kg_anchors", lambda: e.get_kg_anchors(["C15CODE1"], bridge_type="c15bt"))
    res["get_kg_anchors"] = slim(r)
    r = L.journaled("code_crosswalk_add", lambda: e.code_crosswalk_add("urn:c15:sys", "C15CODE2", "c15:anchor",
                                                                       target_graph="c15g3", relation="exact"))
    res["code_crosswalk_add"] = slim(r)
    r = L.journaled("code_crosswalk_add bad relation", lambda: e.code_crosswalk_add("urn:c15:sys", "C15CODE3",
                                                                                   "c15:anchor", relation="nope"))
    res["code_crosswalk_refused"] = slim(r)
    if others == 0:
        r = L.journaled("migrate_fhir_bridges_to_crosswalk", lambda: e.migrate_fhir_bridges_to_crosswalk())
        res["migrate"] = slim(r)
    else:
        res["migrate"] = "skipped: other lanes' bridge rows present (namespace-wide upsert)"
    # cleanup (own rows only)
    c.sql("DELETE FROM Graph_KG.fhir_bridges WHERE fhir_code LIKE 'C15%'")
    c.sql("DELETE FROM Graph_KG.code_crosswalk WHERE code LIKE 'C15%'")
    e.erase_graph("c15g3")
    res["cleanup_left"] = [c.sql("SELECT COUNT(*) FROM Graph_KG.fhir_bridges WHERE fhir_code LIKE 'C15%'")[0][0],
                           c.sql("SELECT COUNT(*) FROM Graph_KG.code_crosswalk WHERE code LIKE 'C15%'")[0][0]]
    return res


# ------------------------------------------------------------------------------------------------ table mappings
def part_tablemap(L):
    res = {}
    e, c = L.eng, L.c
    for t in ("IVGAudit.C15Patients", "IVGAudit.C15Visits"):
        try:
            c.sql(f"DROP TABLE {t}")
        except Exception:  # noqa: BLE001
            pass
    c.sql("CREATE TABLE IVGAudit.C15Patients (pid VARCHAR(32) PRIMARY KEY, name VARCHAR(64))")
    c.sql("CREATE TABLE IVGAudit.C15Visits (vid VARCHAR(32) PRIMARY KEY, pid VARCHAR(32))")
    c.sql("INSERT INTO IVGAudit.C15Patients (pid, name) VALUES ('p1', 'Ann')")
    c.sql("INSERT INTO IVGAudit.C15Visits (vid, pid) VALUES ('v1', 'p1')")
    res["default_schema"] = str(c.call("%SYSTEM.SQL.Schema", "Default")) if True else None
    res["schema_USER_tables"] = c.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'USER'")[0][0]
    res["sqluser_tables"] = [r[0] for r in c.sql("SELECT TOP 5 TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'SQLUser'")]
    # the qualified mapping is accepted
    r = L.journaled("map_sql_table qualified", lambda: e.map_sql_table("IVGAudit.C15Patients", "pid", "C15Patient",
                                                                       property_columns=["name"]))
    res["map_qualified"] = slim(r)
    # F-1504: the lookup an unqualified name gets. A table in SQLUser, if one exists, is mapped both ways (read-only
    # use of somebody else's table: only a mapping row of ours is written and then removed).
    if res["sqluser_tables"]:
        t = res["sqluser_tables"][0]
        col = c.sql("SELECT TOP 1 COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='SQLUser' AND TABLE_NAME=?", t)[0][0]
        r = L.journaled("map_sql_table unqualified SQLUser table", lambda: e.map_sql_table(t, col, "C15UnqualU"))
        res["map_unqualified_existing"] = slim(r)
        r = L.journaled("map_sql_table SQLUser-qualified", lambda: e.map_sql_table(f"SQLUser.{t}", col, "C15UnqualQ"))
        res["map_sqluser_qualified"] = slim(r)
        res["unqualified_table_resolves_in_sql"] = c.sql(f"SELECT COUNT(*) FROM {t}")[0][0]
        for lbl in ("C15UnqualU", "C15UnqualQ"):
            try:
                e.remove_table_mapping(lbl)
            except Exception:  # noqa: BLE001
                pass
    else:
        r = L.journaled("map_sql_table unqualified (no SQLUser table exists)",
                        lambda: e.map_sql_table("C15Patients", "pid", "C15UnqualU"))
        res["map_unqualified_nonexistent"] = slim(r)
    # the exact catalog query the code runs for an unqualified name, against the qualified table's real schema
    res["lookup_with_USER"] = c.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? AND COLUMN_NAME = ?",
                                    "USER", "C15Patients", "pid")[0][0]
    res["lookup_with_IVGAudit"] = c.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? AND COLUMN_NAME = ?",
                                        "IVGAudit", "C15Patients", "pid")[0][0]
    r = L.journaled("map_sql_table second label", lambda: e.map_sql_table("IVGAudit.C15Visits", "vid", "C15Visit"))
    res["map_second"] = slim(r)
    r = L.journaled("map_sql_relationship", lambda: e.map_sql_relationship("C15Visit", "C15_OF", "C15Patient",
                                                                           target_fk="pid"))
    res["map_rel"] = slim(r)
    r = L.journaled("map_sql_relationship unmapped label", lambda: e.map_sql_relationship("C15Nope", "X", "C15Patient",
                                                                                         target_fk="pid"))
    res["map_rel_refused"] = slim(r)
    r = L.journaled("list_table_mappings", lambda: e.list_table_mappings())
    res["list"] = {k: v for k, v in slim(r).items() if k != "result"}
    res["cypher_over_mapping"] = repr(e.execute_cypher("MATCH (p:C15Patient) RETURN p.name").rows)
    r = L.journaled("remove_table_mapping C15Patient", lambda: e.remove_table_mapping("C15Patient"))
    res["remove"] = slim(r)
    res["rel_rows_after_remove"] = c.sql("SELECT COUNT(*) FROM Graph_KG.relationship_mappings WHERE source_label LIKE 'C15%' OR target_label LIKE 'C15%'")[0][0]
    r = L.journaled("remove_table_mapping unmapped", lambda: e.remove_table_mapping("C15Patient"))
    res["remove_refused"] = slim(r)
    # cleanup
    for lbl in ("C15Visit",):
        try:
            e.remove_table_mapping(lbl)
        except Exception:  # noqa: BLE001
            pass
    for t in ("IVGAudit.C15Patients", "IVGAudit.C15Visits"):
        c.sql(f"DROP TABLE {t}")
    res["cleanup_left"] = c.sql("SELECT COUNT(*) FROM Graph_KG.table_mappings WHERE label LIKE 'C15%'")[0][0]
    return res


# ------------------------------------------------------------------------------------------------ F-1508
def part_anchors(L):
    res = {}
    os.environ.pop("FHIR_BASE_URL", None)
    from iris_vector_graph import cypher_api
    cypher_api._engine_cache = L.eng  # the identity-checked engine on AUDITC; no server is started
    cases = {
        "unregistered_fhir_graph": dict(fhir_patient_id="p1", fhir_graph="fhir:c15:none"),
        "invalid_patient_id": dict(fhir_patient_id="bad id!"),
        "no_fhir_tables_no_graph_arg": dict(fhir_patient_id="p1"),
    }
    for name, kw in cases.items():
        req = cypher_api.CypherRequest(query="RETURN size($patient_anchors) AS n", **kw)
        direct = None
        try:
            direct = L.eng.fhir_patient_anchors(kw["fhir_patient_id"], graph=kw.get("fhir_graph"))
        except Exception as ex:  # noqa: BLE001
            direct = f"raised {type(ex).__name__}: {ex}"
        try:
            out = cypher_api.cypher_query(req)
            res[name] = {"engine_call": direct, "http_handler": out}
        except Exception as ex:  # noqa: BLE001
            res[name] = {"engine_call": direct, "http_handler": f"raised {type(ex).__name__}: {getattr(ex, 'detail', ex)}"}
    cypher_api._engine_cache = None
    return res


# ------------------------------------------------------------------------------------------------ rdf / shacl / prov
def part_rdf(L):
    res = {}
    e, c = L.eng, L.c
    g = "c15g4"
    e.create_node("c15:r1", labels=["C15Thing"], properties={"name": "one", "n": 7}, graph=g)
    e.create_node("c15:r2", labels=["C15Thing"], properties={"name": "two"}, graph=g)
    e.create_edge("c15:r1", "c15link", "c15:r2", qualifiers={"w": 1}, graph=g)
    out = OUT / "c15g4.nq"
    r = L.journaled("export_rdf nquads", lambda: e.export_rdf(str(out), format="nquads", graph_id=g))
    res["export_rdf"] = slim(r)
    res["export_lines"] = out.read_text().count("\n") if out.exists() else None
    shapes = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <urn:ivg:> .
ex:S a sh:NodeShape ; sh:targetClass <urn:ivg:C15Thing> ;
  sh:property [ sh:path <urn:ivg:prop/name> ; sh:minCount 1 ] ;
  sh:property [ sh:path <urn:ivg:prop/n> ; sh:minCount 1 ] .
"""
    r = L.journaled("validate_shacl", lambda: (lambda rep: {"conforms": rep.conforms, "violations": len(rep.violations)})(
        e.validate_shacl(shapes, node_ids=["c15:r1", "c15:r2"])))
    res["validate_shacl"] = slim(r)
    r = L.journaled("register_namespace", lambda: e.register_namespace("c15ex", "http://c15.example/"))
    res["register_namespace"] = slim(r)
    c.sql("DELETE FROM Graph_KG.rdf_namespaces WHERE prefix = 'c15ex'")
    # F-1501: a failed window read. A second engine whose connection is closed: the read fails at IRIS.
    with Lane("c15", engine=True) as L2:
        eng2 = L2.eng
        L2.c.conn.close()
        p = OUT / "prov-failed-window.ttl"
        if p.exists():
            p.unlink()
        try:
            eng2.prov_export(str(p))
            res["prov_failed_window"] = {"raised": None, "file_exists": p.exists(),
                                         "file_bytes": p.stat().st_size if p.exists() else None}
        except Exception as ex:  # noqa: BLE001
            res["prov_failed_window"] = {"raised": f"{type(ex).__name__}: {str(ex)[:300]}", "file_exists": p.exists()}
    # PROV export on a healthy engine (default graph only; no temporal edges of ours there): reads only
    p2 = OUT / "prov-ok.ttl"
    r = L.journaled("prov_export healthy", lambda: e.prov_export(str(p2), ts_start=0, ts_end=1))
    res["prov_export_ok"] = slim(r)
    e.erase_graph(g)
    return res


# ------------------------------------------------------------------------------------------------ F-1510
def part_memory(L):
    import tracemalloc
    res = {}
    e = L.eng
    for n in (300, 3000):
        g = f"c15mem{n}"
        e.bulk_create_nodes([{"id": f"c15:m{n}:{i}", "labels": ["C15M"],
                              "properties": {"name": f"node {i}", "k": i}} for i in range(n)], graph=g)
        out = OUT / f"mem{n}.nt"
        tracemalloc.start()
        t0 = time.time()
        rep = e.export_rdf(str(out), format="nt", graph_id=g)
        cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        res[str(n)] = {"triples": rep["triples"], "peak_bytes": peak, "seconds": round(time.time() - t0, 2),
                       "bytes_per_triple": round(peak / max(rep["triples"], 1), 1)}
        e.erase_graph(g)
        out.unlink()
    a, b = res["300"], res["3000"]
    res["peak_ratio"] = round(b["peak_bytes"] / max(a["peak_bytes"], 1), 2)
    res["triple_ratio"] = round(b["triples"] / max(a["triples"], 1), 2)
    return res


# ------------------------------------------------------------------------------------------------ 5c refusals
def part_refusals(L):
    """Each stated refusal (X statement) reachable without a FHIR repository, journaled: it must raise or answer an
    error and write nothing."""
    import builtins
    e = L.eng
    g = "fhir:c15:none"
    cases = {
        "INT-F3.5 register interval<60": lambda: e.fhir_graph_register(interval_s=30),
        "INT-F3.5 schedule interval<60": lambda: e.fhir_graph_schedule(g, interval_s=30),
        "INT-F3.6 denylist entry not Type.param": lambda: e.fhir_graph_register(denylist=["badentry"]),
        "INT-F1.13 json link wrong form": lambda: e.fhir_graph_register(json_links=["not a link"]),
        "INT-F1.13 json link listed twice": lambda: e.fhir_graph_register(json_links=["Library.relatedArtifact", "Library.relatedArtifact"]),
        "INT-F8.2 default graph (None)": lambda: e.fhir_graph_status(None),
        "INT-F8.2 default graph ('')": lambda: e.fhir_graph_sync(""),
        "INT-F8.2 name not allowed": lambda: e.fhir_graph_rebuild("bad\x01name"),
        "INT-F8.4 link report source not Type/id": lambda: e.fhir_link_report(g, "notakey"),
        "INT-C1.2 expand hops 11": lambda: e.fhir_expand_concepts("c15cg", ["c15:x"], hops=11),
        "INT-C1.2 expand unknown direction": lambda: e.fhir_expand_concepts("c15cg", ["c15:x"], direction="sideways"),
        "INT-C1.7 resolve unknown relation": lambda: e.fhir_resolve_concepts(g, "c15cg", ["c15:x"], relations=["nope"]),
        "INT-C1.7 resolve param not plain": lambda: e.fhir_resolve_concepts(g, "c15cg", ["c15:x"], params=["code; DROP"]),
        "INT-C3.4 coverage bad prefix": lambda: e.fhir_coverage_report(g, id_prefix="bad prefix!"),
        "INT-C3.4 gaps top 0": lambda: e.fhir_concept_gaps(g, top=0),
        "INT-C4.3 anchors bad patient id": lambda: e.fhir_patient_anchors("bad id!"),
        "INT-C5.1 crosswalk empty system": lambda: e.code_crosswalk_add("", "C15X", "c15:x"),
        "INT-C5.1 crosswalk bad relation": lambda: e.code_crosswalk_add("urn:c15", "C15X", "c15:x", relation="nope"),
        "INT-M1.2 map table not a plain name": lambda: e.map_sql_table("IVGAudit.C15T; DROP", "id", "C15L"),
        "INT-M1.3 map table missing": lambda: e.map_sql_table("IVGAudit.C15NoSuchTable", "id", "C15L"),
        "INT-M1.6 link without fk/join": lambda: e.map_sql_relationship("C15A", "R", "C15B"),
        "INT-M1.8 remove unmapped": lambda: e.remove_table_mapping("C15NeverMapped"),
        "INT-M1.12 attach vectors unmapped": lambda: e.attach_embeddings_to_table("C15NeverMapped", ["name"]),
        "INT-E1.2 reify missing edge (no-op)": lambda: e.reify_edge(-7, reifier_id="c15:never"),
        "INT-S1.6 shapes of another kind": lambda: e.validate_shacl(12345),
        "INT-S1.4 shapes URL unreachable": lambda: e.validate_shacl("http://127.0.0.1:9/c15-shapes.ttl"),
    }
    res = {}
    for name, fn in cases.items():
        r = slim(L.journaled(name, fn))
        res[name] = {"error": r["error"], "result": r["result"], "records": r["records"],
                     "stores_written": r["stores_written"]}
    # INT-R1.18 / S1.11 / V1.10: rdflib absent (hidden from import in this process only)
    real_import = builtins.__import__

    def no_rdflib(name, *a, **k):
        if name == "rdflib" or name.startswith("rdflib.") or name == "pyshacl" or name.startswith("pyshacl."):
            raise ImportError(f"No module named '{name}' (hidden by the c15 probe)")
        return real_import(name, *a, **k)
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k == "rdflib" or k.startswith("rdflib.")
             or k == "pyshacl" or k.startswith("pyshacl.")}
    builtins.__import__ = no_rdflib
    try:
        for name, fn in {"INT-R1.18 export without rdflib": lambda: e.export_rdf(str(OUT / "never.ttl")),
                         "INT-R1.18 cypher export without rdflib": lambda: e.export_rdf_from_cypher("RETURN 1 AS s", str(OUT / "never2.ttl")),
                         "INT-S1.11 shacl without rdflib": lambda: e.validate_shacl("@prefix sh: <http://www.w3.org/ns/shacl#> ."),
                         "INT-V1.10 prov export without rdflib": lambda: e.prov_export(str(OUT / "never3.ttl"))}.items():
            r = slim(L.journaled(name, fn))
            res[name] = {"error": r["error"], "result": r["result"], "records": r["records"],
                         "stores_written": r["stores_written"]}
    finally:
        builtins.__import__ = real_import
        sys.modules.update(saved)
    # INT-V1.4: a named graph's temporal edge never reaches PROV export
    e.create_edge_temporal("c15:t1", "c15saw", "c15:t2", timestamp=1700000000, graph="c15gt")
    p = OUT / "prov-named.ttl"
    r = slim(L.journaled("INT-V1.4 prov export skips named graph", lambda: e.prov_export(str(p), ts_start=1699999999, ts_end=1700000001)))
    res["INT-V1.4 prov export skips named graph"] = {"error": r["error"], "result": r["result"], "records": r["records"]}
    e.erase_graph("c15gt")
    # INT-C4.5: the Cypher API refuses a caller FHIR base URL that the operator did not list
    from iris_vector_graph import cypher_api
    os.environ.pop("IVG_FHIR_ALLOWED_BASES", None)
    cypher_api._engine_cache = e
    try:
        out = cypher_api.cypher_query(cypher_api.CypherRequest(query="RETURN 1 AS n", fhir_patient_id="p1",
                                                               fhir_base_url="http://169.254.169.254/fhir"))
        res["INT-C4.5 unlisted fhir_base_url"] = {"answered": out}
    except Exception as ex:  # noqa: BLE001
        res["INT-C4.5 unlisted fhir_base_url"] = {"raised": f"{type(ex).__name__}", "detail": getattr(ex, "detail", str(ex))}
    finally:
        cypher_api._engine_cache = None
    res["_refused_with_zero_writes"] = sorted(k for k, v in res.items()
                                              if isinstance(v, dict) and v.get("error") and v.get("records") == 0)
    res["_not_refused"] = sorted(k for k, v in res.items() if isinstance(v, dict) and "error" in v and not v.get("error"))
    res["_cleanup_left"] = L.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'c15'")[0][0]
    return res


PARTS = {"register": part_register, "reify": part_reify, "delreif": part_delreif, "delreif2": part_delreif2, "bridge": part_bridge,
         "tablemap": part_tablemap, "anchors": part_anchors, "rdf": part_rdf, "memory": part_memory,
         "refusals": part_refusals}


def main():
    parts = sys.argv[1:] or list(PARTS)
    summary = {}
    with Lane("c15") as L:
        for p in parts:
            t0 = time.time()
            try:
                res = PARTS[p](L)
                res["_ok"] = True
            except Exception as ex:  # noqa: BLE001
                res = {"_ok": False, "_error": f"{type(ex).__name__}: {ex}", "_traceback": traceback.format_exc()[-4000:]}
            res["_seconds"] = round(time.time() - t0, 2)
            dump(OUT / f"{p}.json", res)
            summary[p] = {"ok": res["_ok"], "seconds": res["_seconds"], "error": res.get("_error")}
            print(p, json.dumps(summary[p]))
    dump(OUT / "summary.json", summary)


if __name__ == "__main__":
    main()
