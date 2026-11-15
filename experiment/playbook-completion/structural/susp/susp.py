#!/usr/bin/env python3
"""Follow-up: decide the ontology-2 lane's possible findings live on AUDITD (observation only).

    locks.sh iris python susp.py OUT_DIR [case ...]

Cases (each from an empty namespace inside one lock hold, scratch data only, the product reached through its own
entry points; a harness stand-in replaces only a transport or a connection factory, never product logic):
  loader-clear   scripts/ingest/networkx_loader.py NetworkXIRISLoader.import_graph(G, clear_existing=True)
                 (connection injected: its own factory needs iris_devtester's container); before/after per graph.
  nkg-merged     Graph.KG.NKGAccelCentrality ClosenessGlobal / BetweennessGlobal and Graph.KG.NKGAccel
                 EigenvectorGlobal called directly (Native API) with edges in the default graph and a named graph;
                 the SQL function kg_Closeness and the engine's closeness_centrality as references.
  mcp-load       scripts/mcp/ivg_mcp_server.py call_tool("LoadGraph") with the `mcp` package replaced by a stand-in
                 (Server decorators, Tool, TextContent; the package is not installed here) and the module's
                 connection set to an AUDITD connection; its answer vs the rows the load wrote.
  gql-props      iris_vector_graph.gql.create_app over the engine, queried in-process (starlette TestClient):
                 Node.properties of a node with properties.
  scalar         IVG.CypherEngine.Scalar's input: execute_cypher on a failing read (error, rows); and whether the
                 container's embedded Python can import iris_vector_graph (needed to call Scalar itself).
  range-step     Cypher range() with a step of 0 known only at run time, against a literal 0 and a run-time 1.
  json-field     get_json_field_values(key, field) with crafted field names over two scratch property rows.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import tempfile
import time
import traceback
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "live"))
import lib  # noqa: E402

REPO = lib.REPO


def call(f):
    try:
        return {"ok": True, "answer": f()}
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": f"{type(ex).__name__}: {str(ex)[:400]}"}


def per_graph(c):
    out = {}
    for t in ("nodes", "rdf_edges", "rdf_labels", "rdf_props"):
        rows = c.sql(f"SELECT COALESCE(graph_id, ''), COUNT(*) FROM Graph_KG.{t} GROUP BY COALESCE(graph_id, '')")
        out[t] = {str(g) or "(default)": int(n) for g, n in rows}
    return out


def kg_out_graphs(c):
    if not int(c.o.isDefined("^KG", "out")):
        return {}
    res = {}
    for G, _ in c.o.iterator("^KG", "out").items():
        res[str(G)] = sum(1 for _ in c.o.iterator("^KG", "out", G).items())
    return res


# ---------------------------------------------------------------------------------------------------- cases

def loader_clear(c, e):
    import networkx as nx
    out = {}
    led = e.ledger
    led.enable()
    from iris_vector_graph.ledger import Changeset
    ch = Changeset(actor="audit:structural", actor_type="ingest", message="ledger content")
    ch.create_node("sl|1")
    ch.create_node("sl|2")
    ch.create_relationship("sl|1", "R", "sl|2")
    led.commit(ch)
    for g in (None, "sgB"):
        e.create_node("sx:1", labels=["L"], properties={"p": "1"}, graph=g)
        e.create_node("sx:2", labels=["L"], properties={"p": "2"}, graph=g)
        e.create_edge("sx:1", "R", "sx:2", graph=g)
    e.create_edge_temporal("sx:1", "T", "sx:2", timestamp=1_700_000_000, graph="sgB")
    e.store_embedding("sx:1", [0.1, 0.2, 0.3, 0.4])
    c.conn.commit()
    out["verify_before"] = str(call(lambda: led.verify().result))
    led.set_strict(True)
    c.conn.commit()
    out["strict_before_load"] = str(call(lambda: led.meta()))[:200]
    out["before"] = {"rows": per_graph(c), "kg_out": kg_out_graphs(c),
                     "temporal_sgB": len(e.get_edges_in_window(start=1_699_999_999, end=1_700_000_001, graph="sgB")),
                     "embeddings": c.sql("SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings")[0][0]}
    sys.path.insert(0, str(REPO / "scripts" / "ingest"))
    spec = importlib.util.spec_from_file_location("ivg_networkx_loader", REPO / "scripts/ingest/networkx_loader.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    loader = mod.NetworkXIRISLoader()
    loader.conn = c.conn
    G = nx.DiGraph()
    G.add_edge("nl:1", "nl:2", relation="LINKS")
    out["import_graph_clear_existing"] = call(lambda: loader.import_graph(G, clear_existing=True))
    try:
        c.conn.commit()
    except Exception:  # noqa: BLE001
        pass
    led.set_strict(False)
    c.conn.commit()
    out["after"] = {"rows": per_graph(c), "kg_out": kg_out_graphs(c),
                    "temporal_sgB": len(e.get_edges_in_window(start=1_699_999_999, end=1_700_000_001, graph="sgB")),
                    "embeddings": c.sql("SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings")[0][0],
                    "sgB_nodes_left": c.sql("SELECT node_id FROM Graph_KG.nodes WHERE graph_id = 'sgB'"),
                    "sgB_get_node": str(call(lambda: e.get_node("sx:1", graph="sgB")))[:300]}
    out["verify_after"] = str(call(lambda: led.verify().result))
    return out


def nkg_merged(c, e):
    out = {}
    e.create_node("nd:1")
    e.create_node("nd:2")
    e.create_edge("nd:1", "R", "nd:2")
    for n in ("ng:1", "ng:2", "ng:3", "ng:4"):
        e.create_node(n, graph="sgN")
    for a, b in (("ng:1", "ng:2"), ("ng:2", "ng:3"), ("ng:3", "ng:4")):
        e.create_edge(a, "R", b, graph="sgN")
    c.conn.commit()
    out["kg_out_graphs"] = kg_out_graphs(c)
    out["engine.sync() (builds ^NKG)"] = call(lambda: e.sync())
    c.conn.commit()
    out["nkg_interned_nodes"] = sum(1 for _ in c.o.iterator("^NKG", "$NI").items()) if int(c.o.isDefined("^NKG", "$NI")) else 0

    def ids(s):
        txt = str(s)
        return sorted({x for x in ("nd:1", "nd:2", "ng:1", "ng:2", "ng:3", "ng:4") if x in txt})
    for name, cls, meth, args in (("ClosenessGlobal", "Graph.KG.NKGAccelCentrality", "ClosenessGlobal", ("harmonic", "out", 0, 100)),
                                  ("BetweennessGlobal", "Graph.KG.NKGAccelCentrality", "BetweennessGlobal", (0, 100, 200, "out", 0)),
                                  ("EigenvectorGlobal", "Graph.KG.NKGAccel", "EigenvectorGlobal", (100, 0.000001, 100, "Graph_KG"))):
        r = call(lambda cls=cls, meth=meth, args=args: str(c.call(cls, meth, *args)))
        out[f"direct {cls}.{name}"] = {"result": (r.get("answer") or r.get("error"))[:700], "node_ids_in_answer": ids(r.get("answer", ""))}
    r = call(lambda: c.sql("SELECT Graph_KG.kg_Closeness('harmonic', 'out', 0, 100)"))
    out["SQL kg_Closeness"] = str(r)[:400]
    r = call(lambda: e.closeness_centrality())
    out["engine.closeness_centrality()"] = {"result": str(r)[:500], "node_ids_in_answer": ids(r.get("answer", ""))}
    return out


def mcp_load(c, e):
    out = {}
    # stand-in for the `mcp` package (not installed here): only the transport and type names the module imports
    class Server:
        def __init__(self, name):
            self.name = name

        def list_tools(self):
            return lambda f: f

        def call_tool(self):
            return lambda f: f

    class TextContent:
        def __init__(self, type, text):
            self.type, self.text = type, text

    class Tool:
        def __init__(self, **kw):
            self.__dict__.update(kw)
    m = types.ModuleType("mcp")
    ms = types.ModuleType("mcp.server")
    ms.Server = Server
    mss = types.ModuleType("mcp.server.stdio")
    mss.stdio_server = None
    mt = types.ModuleType("mcp.types")
    mt.Tool, mt.TextContent = Tool, TextContent
    sys.modules.update({"mcp": m, "mcp.server": ms, "mcp.server.stdio": mss, "mcp.types": mt})
    spec = importlib.util.spec_from_file_location("ivg_mcp_server", REPO / "scripts/mcp/ivg_mcp_server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._conn = c.conn
    import networkx as nx
    G = nx.DiGraph()
    for a, b in (("mc:1", "mc:2"), ("mc:2", "mc:3")):
        G.add_edge(a, b)
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "g.graphml")
        nx.write_graphml(G, p)
        res = asyncio.run(mod.call_tool("LoadGraph", {"filePath": p, "format": "graphml"}))
    c.conn.commit()
    out["LoadGraph_answer"] = json.loads(res[0].text)
    out["rows_written"] = {"nodes": c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'mc:'")[0][0],
                           "edges": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'mc:'")[0][0]}
    G2 = nx.DiGraph()
    G2.add_edge("mc2:1", "mc2:2")
    out["engine.load_networkx_return_keys"] = sorted(lib.engine(c).load_networkx(G2).keys())
    return out


def gql_props(c, e):
    from starlette.testclient import TestClient
    from iris_vector_graph.gql import create_app
    e.create_node("gq:1", labels=["Gqx"], properties={"name": "alpha", "colour": "red"})
    c.conn.commit()
    app = create_app(lib.engine(c))
    out = {"stored_props": c.sql("SELECT \"key\", val FROM Graph_KG.rdf_props WHERE s = 'gq:1'")}
    with TestClient(app) as tc:
        q = '{ node(id: "gq:1") { id labels properties { key value } ... on Gqx { name colour } } }'
        r = tc.post("/graphql", json={"query": q})
        out["node_query"] = {"status": r.status_code, "body": r.json()}
        r = tc.post("/graphql", json={"query": '{ nodes(label: "Gqx", limit: 5) { id properties { key value } } }'})
        out["nodes_query"] = {"status": r.status_code, "body": r.json()}
    return out


def scalar(c, e):
    out = {}
    for q in ("MATCH (n) RETURN count(n) AS c", "MATCH (n) RETURN count(n) / 0 AS c"):
        r = e.execute_cypher(q)
        out[q] = {"error": (str(r.error)[:200] if r.error else None), "rows": r.rows}
    sess = lib.session(' try { set m=##class(%SYS.Python).Import("iris_vector_graph") write $c(30),"IVG|ok",! } '
                       'catch ex { write $c(30),"IVG|",ex.DisplayString(),! }\n'
                       ' try { set eng=##class(IVG.CypherEngine).Local(4) write $c(30),"SC|",eng.Scalar("MATCH (n) RETURN count(n) / 0 AS c","0"),! } '
                       'catch ex { write $c(30),"SC|ERR ",ex.DisplayString(),! }\n halt\n')
    out["embedded_import_iris_vector_graph"] = lib.marked(sess, "IVG")
    out["IVG.CypherEngine.Local(4).Scalar(failing count, default '0')"] = lib.marked(sess, "SC")
    return out


def range_step(c, e):
    out = {}
    for q in ("RETURN range(1, 3, 0) AS r", "UNWIND [0] AS s RETURN range(1, 3, s) AS r",
              "UNWIND [1] AS s RETURN range(1, 3, s) AS r", "WITH 0 AS s RETURN range(1, 3, s) AS r"):
        try:
            r = e.execute_cypher(q)
            out[q] = {"error": (str(r.error)[:200] if r.error else None), "rows": r.rows}
        except Exception as ex:  # noqa: BLE001
            out[q] = {"raised": f"{type(ex).__name__}: {str(ex)[:200]}"}
    return out


def json_field(c, e):
    out = {}
    e.create_node("jf:1", properties={"meta": json.dumps({"color": "red"})})
    e.create_node("jf:2", properties={"private": json.dumps({"color": "blue"})})
    c.conn.commit()
    crafted = 'color": "\', 2), \'"\', 1) FROM Graph_KG.rdf_props WHERE "key" <> ? AND (1 = 1 OR val LIKE ?) --'
    for label, field in (("baseline field 'color'", "color"),
                         ("field with LIKE wildcard 'co_or'", "co_or"),
                         ("field with one quote", "col'or"),
                         ("crafted field: key <> ? replaces key = ?", crafted)):
        out[label] = {"field": field, "result": call(lambda field=field: e.get_json_field_values("meta", field))}
    return out


CASES = {"loader-clear": loader_clear, "nkg-merged": nkg_merged, "mcp-load": mcp_load, "gql-props": gql_props,
         "scalar": scalar, "range-step": range_step, "json-field": json_field}


def main() -> int:
    od = Path(sys.argv[1])
    sel = sys.argv[2:] or list(CASES)
    for name in sel:
        c = lib.conn()
        t0 = time.time()
        try:
            lib.reset(c)
            r = {"case": name, "result": CASES[name](c, lib.engine(c))}
        except Exception:  # noqa: BLE001
            r = {"case": name, "harness_error": traceback.format_exc()[-2000:]}
        finally:
            try:
                c.conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            try:
                lib.engine(c).ledger.set_strict(False)
            except Exception:  # noqa: BLE001
                pass
            lib.reset(c)
            c.close()
        r["secs"] = round(time.time() - t0, 2)
        lib.dump(od / f"{name}.json", r)
        print(json.dumps(r, default=str)[:3000], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
