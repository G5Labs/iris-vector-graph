#!/usr/bin/env python3
"""3.6-frame, second pass: DDL-issuing and so-far-unobserved write statements under the dictionary oracle
(dictoracle.py: catalog snapshot diff + journaled catalog globals + executed DDL text) and the journal (data rows,
key level), on AUDITD through the product's own entry points.

    locks.sh iris python frame2_live.py OUT_DIR control|run [action ...]

Each action: base state from lib.reset() (product's EraseAll + PurgeAll) plus a bystander set (a scratch SQL table
IVGAudit.Fr2Bystander with an index and a row, and a scratch global ^IVGAuditDFr2Keep, both created by the harness
outside the capture window and removed after), the action's own setup, then dictoracle.run(). Frame of an action:
the schema objects (tables / classes / SQL procedures / routines / globals, as patterns) its statements name, cited
per action, plus the data keys its statements' WHERE or VALUES name. Verdict: catalog excursions (objects changed
outside the frame, bystanders included) and data excursions (journaled rows or nodes of the product's content
stores carrying none of the action's keys and not a cited counter).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dictoracle as D  # noqa: E402
import lib  # noqa: E402
from lib import J  # noqa: E402

TS = 1_700_000_000
SUBCLASS = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
PRODUCT_GLOBALS = ["^kg", "^nkg", "^ivg.*", "^t52s.*", "^graph.kg.*", "^bm25idx", "^ivf", "^vecidx", "^plaid",
                   "^embedqueue", "^arnokg", "^ivgc.*"]
CONTENT = ("sql:Graph_KG.nodes", "sql:Graph_KG.rdf_edges", "sql:Graph_KG.rdf_labels", "sql:Graph_KG.rdf_props",
           "global:^KG")
COUNTERS = ('^KG("__version"', '^KG("gen"', '^NKG("$meta"', '^KG("degc"')


def bystanders(c, make=True):
    if make:
        D.hsql(c, "CREATE TABLE IVGAudit.Fr2Bystander (id VARCHAR(64), v INTEGER)")
        D.hsql(c, "CREATE INDEX idx_fr2_by ON IVGAudit.Fr2Bystander (v)")
        D.hsql(c, "INSERT INTO IVGAudit.Fr2Bystander (id, v) VALUES ('b', 1)")
        c.o.set("keep", "^IVGAuditDFr2Keep", 1)
        c.conn.commit()
    else:
        for q in ("DROP TABLE IVGAudit.Fr2Bystander",):
            try:
                D.hsql(c, q)
            except Exception:  # noqa: BLE001
                pass
        c.o.kill("^IVGAuditDFr2Keep")
        c.conn.commit()


def keyed_rowids(c, keys, smap):
    """Row ids of the content tables' rows that carry one of the action's keys, read by SQL (a deleted row's KILL
    record carries no old value, so the journal alone cannot attribute its index nodes)."""
    cols = {"Graph_KG.nodes": ["node_id"], "Graph_KG.rdf_edges": ["s", "o_id", "p"], "Graph_KG.rdf_labels": ["s"],
            "Graph_KG.rdf_props": ["s"]}
    inv = {v: k for k, v in smap.items() if k.endswith(".")}
    out = {}
    for t, cs in cols.items():
        pre = inv.get(t)
        if not pre or not keys:
            continue
        marks = ",".join("?" * len(keys))
        where = " OR ".join(f"{col} IN ({marks})" for col in cs)
        try:
            rows = D.hsql(c, f"SELECT %ID FROM {t} WHERE {where}", *(list(keys) * len(cs)))
        except Exception:  # noqa: BLE001
            rows = []
        out.setdefault(pre, set()).update(int(r[0]) for r in rows)
    return out


def data_excursions(c, recs, keys, smap, extra_counters=(), keyed_extra=None):
    """Rows/nodes of the content stores that are none of the action's rows. A row is keyed when its data node
    ^T.1(rowid) carries one of the action's keys (new or old value). Other nodes of the same table pass when they
    belong to a keyed row: a long-column node ^T.1(rowid, col), an index node ending in the rowid, a bitmap chunk
    ^T.k(..., chunk) holding a keyed rowid (64,000 ids per chunk), an iFind posting ^T.k("P", rowid, ...); iFind word
    and list nodes ("W", "L") are counted as unattributable index nodes of a table with keyed rows."""
    import re as _re

    def hay(r):
        return (r.get("g") or "") + " " + " ".join((J.decode(x) or b"").decode("latin-1", "replace") for x in (r.get("n"), r.get("o")))

    def prefix(root):
        return root.rsplit(".", 1)[0] + "." if root.count(".") >= 2 else root
    keyed = {}
    for r in recs:
        g = r.get("g") or ""
        m = _re.match(r'^(\^[^(]+)\((\d+)\)$', g)
        if m and m.group(1).endswith(".1") and any(k in hay(r) for k in keys):
            keyed.setdefault(prefix(m.group(1)), set()).add(int(m.group(2)))
    for pre, ids in (keyed_extra or {}).items():
        keyed.setdefault(pre, set()).update(ids)
    bad, unattributable = [], 0
    for r in recs:
        g = r.get("g") or ""
        st = J.store_of(g, smap)
        if st not in CONTENT:
            continue
        if "(" not in g or g.startswith(COUNTERS + tuple(extra_counters)):
            continue
        if any(k in hay(r) for k in keys):
            continue
        root = J.global_root(g)
        rows = keyed.get(prefix(root), set())
        mlong = _re.match(r'^\^[^(]+\((\d+),"[^"]+"\)$', g)
        mlast = _re.search(r'[,(](\d+)\)$', g)
        mpost = _re.match(r'^\^[^(]+\("P",(\d+)', g)
        if mlong and int(mlong.group(1)) in rows:
            continue
        if mpost and int(mpost.group(1)) in rows:
            continue
        if mlast and rows:
            v = int(mlast.group(1))
            if v in rows or (r["t"] in ("BitSET", "ZKILL", "SET", "KILL") and any(x // 64000 + 1 == v for x in rows)):
                continue
        if _re.match(r'^\^[^(]+\("(W|L)"', g) and rows:
            unattributable += 1
            continue
        if mlong:
            try:
                row = D.hsql(c, f"SELECT * FROM {st[4:]} WHERE %ID = ?", int(mlong.group(1)))
            except Exception:  # noqa: BLE001
                row = []
            if row and any(k in " ".join(str(x) for x in row[0]) for k in keys):
                continue
        bad.append({"store": st, "node": g[:160], "t": r["t"]})
    return bad if not unattributable else bad + [{"unattributable_index_nodes": unattributable}]


def stores_written(recs, smap):
    return sorted({J.store_of(r["g"], smap) for r in recs if r.get("g")})


# ------------------------------------------------------------------------------------------------ actions
def act_setup_rerun(c, e):
    """01: initialize_schema() over a set-up namespace, with a node carrying a '__graph' property
    (add_graph_id_to_nodes, iris_vector_graph/schema.py:1514-1566: UPDATE nodes ... DELETE rdf_props key '__graph')."""
    e.create_node("fr2:plain", labels=["L"], properties={"p": "1"})
    w = D.hsql  # noqa: F841
    setup = {"create_node __graph": str(e.create_node("fr2:g", properties={"__graph": "fr2gX"}))}
    c.conn.commit()
    setup["rows_before"] = D.hsql(c, "SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'fr2:'")
    setup["props_before"] = D.hsql(c, "SELECT s, \"key\", graph_id FROM Graph_KG.rdf_props WHERE s %STARTSWITH 'fr2:'")
    frame = {"tables": ["graph_kg.*"], "classes": ["graph.kg.*", "ivg.*", "ivgc.*"], "routines": ["graph_kg.*", "graph.kg.*", "ivg.*"],
             "globals": PRODUCT_GLOBALS,
             "cite": "initialize_schema's DDL names only IVG Schema objects (spec 262 FR-007; iris_vector_graph/_engine/schema.py:2097-2161, schema.py:705-731) and deploys the pin's Graph.KG/IVG classes (class_deploy.py); its data statements name the content tables store-wide (no key)"}
    def fn():
        st = lib.engine(c).initialize_schema()
        c.conn.commit()
        return {"status_warnings": st.get("warnings"),
                "rows_after": D.hsql(c, "SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'fr2:'"),
                "props_after": D.hsql(c, "SELECT s, \"key\", graph_id FROM Graph_KG.rdf_props WHERE s %STARTSWITH 'fr2:'")}
    return frame, fn, None, setup


def act_ff_probe(c, e):
    """02/03/04/05/06/08/10 (engine.py:765-803): the FETCH FIRST probe, run by an engine made with
    IRISGraphEngine.from_connect (the only constructor that keeps connection parameters), on its first Cypher
    translation."""
    from iris_vector_graph.engine import IRISGraphEngine
    import os
    from tests import conftest as fixtures
    eng = IRISGraphEngine.from_connect("127.0.0.1", port=int(os.environ["IVG_PORT"]), namespace=lib.NS,
                                       username="_SYSTEM", password="SYS", embedding_dimension=4)
    actual = fixtures.probe_instance_hostname(eng.conn)
    ok = fixtures.container_hostname_matches(actual, fixtures.docker_container_hostname(os.environ["IVG_TEST_CONTAINER"]),
                                             fixtures.docker_container_id(os.environ["IVG_TEST_CONTAINER"]))
    if not ok:
        raise RuntimeError("from_connect connection is not the audit container")
    frame = {"tables": ["graph_kg.ivg_ff_probe_*"], "classes": ["graph.kg.ivgffprobe*"], "routines": ["graph_kg.ivg_ff_probe_*"],
             "globals": ["^t52s.*"],
             "cite": "engine.py:742-746 (two tables named for the probe in the IVG Schema), :786-805 (CREATE, SELECT, DROP of exactly those); their storage globals carry the IVG Schema's DDL package hash ^t52S.*, created and dropped within the action (the global-directory diff shows none left)"}

    def fn():
        r = eng.execute_cypher("MATCH (n) RETURN n.id AS id ORDER BY id LIMIT 1")
        return {"cypher_error": r.error, "fetch_first_unsafe": eng._fetch_first_unsafe_cached}
    return frame, fn, None, {"from_connect_identity": ok, "_eng": eng}


def act_route(c, e):
    """06 (_engine/schema.py:255-298, embeddings.py:942-1025): the first vector of a new graph creates its routed table."""
    from iris_vector_graph.routing import route_table_name
    e.create_node("fr2:v", graph="fr2gr")
    c.conn.commit()
    route = route_table_name("fr2gr", None)
    short = route.split(".")[-1].lower()
    frame = {"tables": [f"graph_kg.{short}", "graph_kg.embedding_registry"], "classes": [f"graph.kg.{short.replace('_', '')}*", "graph.kg.nodes"],
             "routines": [f"graph_kg.{short}*"], "globals": [], "route": route,
             "cite": "embeddings.py:942-1025 store_embedding -> routed_table_ddl (_engine/schema.py:255-298): CREATE TABLE <route> with its FOREIGN KEY (graph_id, node_id) REFERENCES Graph_KG.nodes (the referenced class records the dependency) and its HNSW index; registry row"}
    return frame, (lambda: e.store_embedding("fr2:v", [0.1, 0.2, 0.3, 0.4], graph="fr2gr")), ["fr2:v", "fr2gr"], {"route": route}


def act_edge_route(c, e):
    """06 (_engine/schema.py:284): the first edge vector of a new graph creates its edge route."""
    from iris_vector_graph.routing import edge_route_table_name
    e.create_node("fr2:s", graph="fr2ge")
    e.create_node("fr2:o", graph="fr2ge")
    e.create_edge("fr2:s", "R", "fr2:o", graph="fr2ge")
    c.conn.commit()
    route = edge_route_table_name("fr2ge", None)
    short = route.split(".")[-1].lower()
    frame = {"tables": [f"graph_kg.{short}", "graph_kg.embedding_registry"], "classes": [f"graph.kg.{short.replace('_', '')}*"],
             "routines": [f"graph_kg.{short}*"], "globals": [],
             "cite": "embeddings.py:1117-1204 store_edge_embedding -> _ROUTED_EDGE_EMBEDDING_DDL (_engine/schema.py:284)"}
    return frame, (lambda: e.store_edge_embedding("fr2:s", "R", "fr2:o", [0.1, 0.2, 0.3, 0.4], graph="fr2ge")), ["fr2:s", "fr2ge"], {"route": route}


def act_rebuild_edge_indices(c, e):
    """11/14 (Ledger.cls:224-240): RebuildEdgeIndices: BUILD INDEX FOR TABLE nodes, rdf_labels, rdf_props, rdf_edges."""
    e.create_node("fr2:a", labels=["L"], properties={"k": "v"})
    e.create_node("fr2:b")
    e.create_edge("fr2:a", "R", "fr2:b")
    c.conn.commit()
    frame = {"tables": ["graph_kg.nodes", "graph_kg.rdf_labels", "graph_kg.rdf_props", "graph_kg.rdf_edges"], "classes": [], "routines": [],
             "globals": [], "data_stores": ["sql:Graph_KG.nodes", "sql:Graph_KG.rdf_labels",
             "sql:Graph_KG.rdf_props", "sql:Graph_KG.rdf_edges", "global:^KG", "global:^IRIS.IF.TransfoB"],
             "cite": "Ledger.cls:212-232: BUILD INDEX FOR TABLE of the four structural tables (their index status in the catalog, their index globals; rdf_props' iFind index idx_props_val_ifind uses IRIS's iFind transformation global ^IRIS.IF.TransfoB); rdf_edges' functional index purges and rebuilds ^KG out/in and the degree cache"}
    return frame, (lambda: int(c.call("Graph.KG.Ledger", "RebuildEdgeIndices", "Graph_KG"))), None, {}


def act_cypher_schema(c, e):
    """08/09 (query.py:1884-1893): Cypher CREATE/DROP INDEX and CONSTRAINT commands."""
    frame = {"tables": [], "classes": [], "routines": [], "globals": [],
             "cite": "query.py:1884-1893 answers an empty IVGResult for these commands: no statement"}

    def fn():
        out = []
        for q in ("CREATE INDEX fr2_idx FOR (n:L) ON (n.p)", "DROP INDEX fr2_idx", "CREATE CONSTRAINT fr2_c FOR (n:L) REQUIRE n.id IS UNIQUE",
                  "DROP CONSTRAINT fr2_c", "CREATE FULLTEXT INDEX fr2_ft FOR (n:L) ON EACH [n.p]"):
            r = e.execute_cypher(q)
            out.append([q, r.error, len(r.rows)])
        return out
    return frame, fn, [], {}


def act_dbapi_utils(c, e):
    """17 (dbapi_utils.py:101-235): create_hnsw_index, create_ivfflat_index and insert_vector (INSERT, then the UPDATE
    of an upsert, :137-163) on a scratch table, and IRISGraphStore.execute_sql(read_only=True) with an INSERT (HD-1701)."""
    D.hsql(c, "CREATE TABLE IVGAudit.Fr2Vec (id VARCHAR(64) NOT NULL PRIMARY KEY, emb VECTOR(DOUBLE, 4), note VARCHAR(32))")
    c.conn.commit()
    frame = {"tables": ["ivgaudit.fr2vec"], "classes": ["ivgaudit.fr2vec*"], "routines": ["ivgaudit.fr2vec*"], "globals": [],
             "data_tables": ["IVGAudit.Fr2Vec"],
             "cite": "dbapi_utils.py:170-204 / 207-235 CREATE INDEX on the table named; :101-167 INSERT / UPDATE of the table named; execute_sql runs the caller's statement"}

    def fn():
        import iris_vector_graph.dbapi_utils as U
        from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
        cur = c.conn.cursor()
        out = {}
        for name, f in (("create_hnsw_index", lambda: U.create_hnsw_index(cur, "IVGAudit.Fr2Vec", "emb", 4)),
                        ("create_ivfflat_index", lambda: U.create_ivfflat_index(cur, "IVGAudit.Fr2Vec", "emb", 4, n_lists=2)),
                        ("insert_vector new", lambda: U.insert_vector(cur, "IVGAudit.Fr2Vec", "emb", [0.1, 0.2, 0.3, 0.4], 4, {"id": "fr2:x"})),
                        ("insert_vector upsert", lambda: U.insert_vector(cur, "IVGAudit.Fr2Vec", "emb", [0.4, 0.3, 0.2, 0.1], 4, {"id": "fr2:x"})),
                        ("execute_sql read_only INSERT", lambda: IRISGraphStore(c.conn, namespace=lib.NS).execute_sql(
                            "INSERT INTO IVGAudit.Fr2Vec (id, note) VALUES (?, ?)", ["fr2:y", "ro"], read_only=True).error)):
            try:
                out[name] = str(f())[:200]
            except Exception as ex:  # noqa: BLE001
                out[name] = f"{type(ex).__name__}: {str(ex)[:200]}"
        cur.close()
        c.conn.commit()
        out["rows"] = D.hsql(c, "SELECT id, note FROM IVGAudit.Fr2Vec")
        return out
    return frame, fn, ["fr2:x", "fr2:y"], {}


def act_post_commit_delete(c, e):
    """13/11/14 (ledger/client.py:455-485): post-commit properties over an existing property: DELETE then INSERT."""
    from iris_vector_graph.ledger import Changeset
    led = e.ledger
    led.enable()
    ch = Changeset(actor="audit:frame2", actor_type="ingest", message="pc 1")
    ch.create_node("fr2|e")
    ch.post_commit_properties = {"fr2|e": {"pc": "1"}}
    led.commit(ch)
    c.conn.commit()
    frame = {"tables": [], "classes": [], "routines": [], "globals": [],
             "cite": "client.py:470-480: DELETE FROM rdf_props WHERE graph AND s = ? AND key = ?; INSERT of the same key; the commit's own ledger writes are checked by st-live-frame-r8"}

    def fn():
        ch2 = Changeset(actor="audit:frame2", actor_type="ingest", message="pc 2")
        ch2.update_node("fr2|e", properties={"q": "1"}) if hasattr(ch2, "update_node") else ch2.create_node("fr2|f")
        ch2.post_commit_properties = {"fr2|e": {"pc": "2"}}
        r = led.commit(ch2)
        return {"seq": r.revision.seq, "pc": D.hsql(c, "SELECT val FROM Graph_KG.rdf_props WHERE s = 'fr2|e' AND \"key\" = 'pc'")}
    return frame, fn, ["fr2|e", "fr2|f"], {}


def act_retract_temporal_rows(c, e):
    """04 (Adjacency.cls:623-690): RetractTemporalRow (DELETE FROM rdf_edges WHERE %ID = ?, :636) and
    RetractTemporalRows over a scratch root global (DELETE ... WHERE s = :tS AND p = :tP AND o_id = :tO, :674)."""
    for n in ("fr2:a", "fr2:b", "fr2:c", "fr2:d", "fr2:y", "fr2:z"):
        e.create_node(n)
    e.create_edge_temporal("fr2:a", "T", "fr2:b", timestamp=TS)
    e.create_edge_temporal("fr2:c", "T", "fr2:d", timestamp=TS)
    e.create_edge_temporal("fr2:y", "T", "fr2:z", timestamp=TS)
    c.conn.commit()
    c.o.set("", "^IVGAuditDFr2R", "fr2:c", "T", "fr2:d")
    frame = {"tables": [], "classes": [], "routines": [], "globals": [],
             "cite": "Adjacency.cls:619-690: the marked rdf_edges rows of the triples named (pSrc/pPred/pDst, or the nodes of @pRoot@) and their ^KG entries"}

    def fn():
        a = c.call("Graph.KG.Adjacency", "RetractTemporalRow", 0, "fr2:a", "T", "fr2:b")
        b = c.call("Graph.KG.Adjacency", "RetractTemporalRows", 0, "^IVGAuditDFr2R")
        rows = D.hsql(c, "SELECT s, o_id FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'fr2:'")
        return {"RetractTemporalRow": str(a), "RetractTemporalRows": str(b), "rows_left": rows}
    return frame, fn, ["fr2:a", "fr2:b", "fr2:c", "fr2:d"], {}


def act_retract_inference(c, e):
    """01/04/06 (_engine/schema.py:3186-3259): retract_inference: DELETE FROM rdf_edges WHERE qualifiers LIKE the
    inferred marker (:3224) after materialize_inference wrote one inferred edge."""
    for n in ("fr2:A", "fr2:B", "fr2:C"):
        e.create_node(n)
    e.create_edge("fr2:A", SUBCLASS, "fr2:B")
    e.create_edge("fr2:B", SUBCLASS, "fr2:C")
    e.create_edge("fr2:A", "R", "fr2:C")
    c.conn.commit()
    mat = e.materialize_inference()
    c.conn.commit()
    inferred = D.hsql(c, "SELECT s, p, o_id FROM Graph_KG.rdf_edges WHERE qualifiers LIKE '%\"inferred\":%'")
    frame = {"tables": [], "classes": [], "routines": [], "globals": [],
             "cite": "_engine/schema.py:3186-3259: deletes the rows whose qualifiers carry the inferred marker (INFERRED_QUALIFIER_LIKE, :61) and their ^KG entries"}
    keys = sorted({k for row in inferred for k in (row[0], row[2])}) or ["fr2:A"]
    return frame, (lambda: e.retract_inference()), ["inferred"] + keys, {"materialize": str(mat)[:200], "inferred_rows": inferred}


def act_adopt_update(c, e):
    """03/04/12 (nodes_edges.py:91-93): create_edge over a temporal structural row of the same triple adopts it with
    UPDATE rdf_edges SET qualifiers = NULL WHERE s, p, o_id (and the marker)."""
    for n in ("fr2:a", "fr2:b", "fr2:y", "fr2:z"):
        e.create_node(n)
    e.create_edge_temporal("fr2:a", "R", "fr2:b", timestamp=TS)
    e.create_edge_temporal("fr2:y", "R", "fr2:z", timestamp=TS)
    c.conn.commit()
    frame = {"tables": [], "classes": [], "routines": [], "globals": [],
             "cite": "nodes_edges.py:86-93 (the adoption UPDATE names the triple), :1251-1253 (create_edge's adoption)"}
    return frame, (lambda: e.create_edge("fr2:a", "R", "fr2:b")), ["fr2:a", "fr2:b"], {}


ACTIONS = {
    "F01-setup-rerun-graph-prop": ("01", act_setup_rerun),
    "F02-fetch-first-probe": ("02,03,04,05,06,08,10", act_ff_probe),
    "F03-route-create": ("06", act_route),
    "F04-edge-route-create": ("06", act_edge_route),
    "F05-rebuild-edge-indices": ("11,14", act_rebuild_edge_indices),
    "F06-cypher-schema-commands": ("08,09", act_cypher_schema),
    "F07-dbapi-utils": ("17", act_dbapi_utils),
    "F08-post-commit-overwrite": ("13,11,14", act_post_commit_delete),
    "F09-retract-temporal-rows": ("04", act_retract_temporal_rows),
    "F10-retract-inference": ("01,04,06", act_retract_inference),
    "F11-adoption-update": ("03,04,12", act_adopt_update),
}


def run_action(name, seed=None):
    mods, mk = ACTIONS[name]
    c = lib.conn()
    rec = {"action": name, "modules": mods}
    t0 = time.time()
    try:
        lib.reset(c)
        bystanders(c, True)
        e = lib.engine(c)
        frame, fn, keys, setup = mk(c, e)
        eng2 = setup.pop("_eng", None)
        rec["setup"] = setup
        rec["frame"] = {k: v for k, v in frame.items()}
        smap = J.storage_map(c)
        kx_before = keyed_rowids(c, keys, smap) if keys else {}
        if seed == "intruder-table":
            inner = fn
            fn = lambda: (inner(), D.hsql(c, "CREATE TABLE IVGAudit.Fr2Intruder (id VARCHAR(8))"))[0]  # noqa: E731
        elif seed == "intruder-global":
            inner = fn
            fn = lambda: (inner(), c.o.set(1, "^IVGAuditDFr2X"))[0]  # noqa: E731
        elif seed == "intruder-row":
            inner = fn
            fn = lambda: (inner(), e.create_edge("fr2:y", "R", "fr2:z"))[0]  # noqa: E731
        obs = D.run(c, fn)
        rec["result"] = obs["result"]
        rec["error"] = obs["error"]
        rec["ddl_sql"] = obs["ddl_sql"]
        rec["catalog_objects"] = {f"{k}:{n}": v for (k, n), v in sorted(obs["catalog"].items())}
        rec["catalog_diff"] = obs["diff"]
        rec["data_stores_written"] = stores_written(obs["data_recs"], smap)
        exc = D.check(frame, obs)
        if frame.get("data_stores") is not None:
            exc += [f"data store outside frame: {s}" for s in rec["data_stores_written"]
                    if s not in frame["data_stores"] and not s.startswith("global:^IVG") and s not in ("global:^ISC.Src.Jrn",)]
        if frame.get("data_tables"):
            allowed = {"sql:" + t for t in frame["data_tables"]}
            exc += [f"data store outside frame: {s}" for s in rec["data_stores_written"]
                    if s.startswith("sql:") and s not in allowed and not s.startswith("sql:%")]
        if keys is not None:
            kx = keyed_rowids(c, keys, smap)
            for pre, ids in kx_before.items():
                kx.setdefault(pre, set()).update(ids)
            dx = data_excursions(c, obs["data_recs"], keys, smap, keyed_extra=kx)
            rec["unattributable_index_nodes"] = sum(x.get("unattributable_index_nodes", 0) for x in dx)
            exc += [f"data key excursion: {x}" for x in dx if "unattributable_index_nodes" not in x][:20]
        rec["excursions"] = exc
        rec["holds"] = not exc and obs["error"] is None
        rec["pids"] = obs["pids"]
        if eng2 is not None:
            try:
                eng2.conn.close()
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        rec["harness_error"] = traceback.format_exc()[-2000:]
    finally:
        for q in ("DROP TABLE IVGAudit.Fr2Intruder", "DROP TABLE IVGAudit.Fr2Vec"):
            try:
                D.hsql(c, q)
            except Exception:  # noqa: BLE001
                pass
        for g in ("^IVGAuditDFr2X", "^IVGAuditDFr2R"):
            try:
                c.o.kill(g)
            except Exception:  # noqa: BLE001
                pass
        bystanders(c, False)
        try:
            lib.reset(c)
        except Exception:  # noqa: BLE001
            pass
        c.close()
    rec["secs"] = round(time.time() - t0, 2)
    return rec


def main() -> int:
    od = Path(sys.argv[1])
    mode = sys.argv[2]
    sel = sys.argv[3:] or list(ACTIONS)
    res = []
    if mode == "control":
        cases = [("conforming F06", "F06-cypher-schema-commands", None, True),
                 ("seeded intruder table", "F06-cypher-schema-commands", "intruder-table", False),
                 ("seeded intruder global", "F06-cypher-schema-commands", "intruder-global", False),
                 ("conforming F11", "F11-adoption-update", None, True),
                 ("seeded second triple", "F11-adoption-update", "intruder-row", False)]
        ok = True
        for label, act, seed, want in cases:
            r = run_action(act, seed)
            got = r.get("holds")
            r["control"] = {"label": label, "expect_holds": want, "got_holds": got, "pass": got is want}
            ok &= got is want
            res.append(r)
            print(json.dumps({"control": label, "pass": got is want, "excursions": r.get("excursions", [])[:4],
                              "harness_error": r.get("harness_error", "")[-300:]}, default=str), flush=True)
        lib.dump(od / "control.json", {"cases": res, "pass": ok})
        print("CONTROL", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    for a in sel:
        r = run_action(a)
        res.append(r)
        print(json.dumps({k: r.get(k) for k in ("action", "modules", "holds", "error", "excursions", "ddl_sql", "data_stores_written", "harness_error")},
                         default=str)[:2500], flush=True)
        lib.dump(od / "run.json", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
