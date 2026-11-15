#!/usr/bin/env python3
"""Module 17 (operations) live checks in namespace AUDITC, journal-validated.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 python live/breadth-c/17/ops_live.py [part ...]

parts: engine (in-process engine and SQL adapter checks, journal footprints), server (a Cypher HTTP server started
here on 127.0.0.1:18750 with an API key, a delaying proxy on :18751, the HTTP client against both; stopped by PID).
Scratch data: graphs and ids starting c17, scratch table IVGAudit.C17V; all removed at the end. At most 3 IRIS
connections at once (this process, the server's engine). Results: $RUN_DIR/breadth-c/17/<check>.json and
live/breadth-c/17/results.json.
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from jcheck import Lane, run_dir, dump, NS  # noqa: E402

OUT = run_dir("17")
RESULTS = HERE / "results.json"


def _strip(r):
    return {k: v for k, v in r.items() if k != "raw"}


# ------------------------------------------------------------------------------------------------ engine part
def f1701(L):
    e = L.eng
    e.create_node("c17:x", labels=["C17A"], graph="c17g1")
    e.create_node("c17:x", graph="c17g2")
    e.create_node("c17:y", graph="c17g2")
    e.create_node("c17:p", graph="c17g2")
    e.create_edge("c17:x", "R", "c17:y", graph="c17g2")
    e.create_edge("c17:p", "R", "c17:x", graph="c17g2")
    out = {"observes": "F-1701: unscoped adapter reads merge graphs; Cypher label start/target filters"}
    st = e._store
    out["store_get_nodes_no_graph"] = [list(map(str, r)) for r in st.get_nodes(["c17:x"]).rows]
    out["store_get_node_labels"] = [list(map(str, r)) for r in st.get_node_labels(["c17:x"]).rows]
    qs = {
        "start_label": "USE GRAPH 'c17g2' MATCH (s:C17A)-[*1..2]->(t) RETURN t.id",
        "target_label": "USE GRAPH 'c17g2' MATCH (s {id: 'c17:p'})-[*1..2]->(t:C17A) RETURN t.id",
        "fixed_start_label": "USE GRAPH 'c17g2' MATCH (s:C17A)-[:R]->(t) RETURN t.id",
        "labels_in_g2": "USE GRAPH 'c17g2' MATCH (n:C17A) RETURN n.id",
    }
    for k, q in qs.items():
        try:
            r = e.execute_cypher(q)
            md = getattr(r, "metadata", None)
            out[k] = {"rows": [list(map(str, x)) for x in r.rows], "error": r.error,
                      "metadata": repr(md)[:400], "sql": (getattr(r, "sql", None) or "")[:400]}
        except Exception as ex:
            out[k] = {"exception": f"{type(ex).__name__}: {ex}"[:400]}
    out["leak_observed"] = any(out.get(k, {}).get("rows") for k in ("start_label", "target_label", "fixed_start_label"))
    return out


def f1705_and_dbapi(L):
    from iris_vector_graph import dbapi_utils as du
    c = L.c
    for stmt in ("DROP TABLE IVGAudit.C17V",):
        try:
            c.sql(stmt)
        except Exception:
            pass
    c.sql("CREATE TABLE IVGAudit.C17V (id INTEGER PRIMARY KEY, emb VECTOR(DOUBLE, 2))")
    cur = c.conn.cursor()
    out = {"observes": "F-1705 (L2 order), F-1706 (HNSW DDL issued), dbapi_utils.insert_vector footprint"}
    # Not journaled: traces/journal.py's server-side reader stops with <VECTOR> on a journaled $vector value
    # (Base64Encode of a vector NewValue), seen in the first run of this script; a tool limitation reported to the orchestrator.
    for i, v in ((1, [0.0, 0.0]), (2, [1.0, 0.0]), (3, [5.0, 0.0])):
        du.insert_vector(cur, "IVGAudit.C17V", "emb", v, 2, {"id": i}, dtype="DOUBLE")
    out["insert_vector_journal"] = "not journaled: journal.py fails with <VECTOR> on $vector values"
    def attempt(fn):
        try:
            return fn()
        except Exception as ex:
            return f"{type(ex).__name__}: {ex}"[:300]
    out["l2_top1_for_origin"] = attempt(lambda: du.vector_similarity_search(cur, "IVGAudit.C17V", "emb", [0.0, 0.0],
                                                                             top_k=1, metric="L2"))
    out["l2_all"] = attempt(lambda: du.vector_similarity_search(cur, "IVGAudit.C17V", "emb", [0.0, 0.0], top_k=3,
                                                                metric="L2"))
    out["cosine_top1_for_x"] = attempt(lambda: du.vector_similarity_search(cur, "IVGAudit.C17V", "emb", [1.0, 0.0],
                                                                            top_k=3, metric="COSINE"))
    out["raw_l2"] = attempt(lambda: c.sql("SELECT id, VECTOR_L2(emb, TO_VECTOR('[0,0]', DOUBLE, 2)) FROM IVGAudit.C17V"))
    out["raw_cosine"] = attempt(lambda: c.sql("SELECT id, VECTOR_COSINE(emb, TO_VECTOR('[1,0]', DOUBLE, 2)) FROM IVGAudit.C17V"))
    out["iris_version"] = attempt(lambda: str(c.call("%SYSTEM.Version", "GetVersion")))

    class Spy:
        def __init__(self, cur):
            self.cur, self.sql = cur, []

        def execute(self, sql, *a):
            self.sql.append(sql)
            return self.cur.execute(sql, *a)

        def __getattr__(self, k):
            return getattr(self.cur, k)
    spy = Spy(c.conn.cursor())
    try:
        out["create_hnsw_index_returned"] = du.create_hnsw_index(spy, "IVGAudit.C17V", "emb", 2, metric="L2",
                                                                 index_name="C17VHNSW")
    except Exception as ex:
        out["create_hnsw_index_returned"] = f"{type(ex).__name__}: {ex}"[:300]
    out["create_hnsw_index_sql"] = spy.sql
    top = out["l2_top1_for_origin"]
    out["l2_farthest_first"] = isinstance(top, list) and bool(top) and str(top[0].get("id")) == "3"
    out["l2_unsupported"] = isinstance(top, str) and "VECTOR_L2" in top
    c.sql("DROP TABLE IVGAudit.C17V")
    return out


def f1707(L):
    e = L.eng
    out = {"observes": "F-1707: SHOW CONSTRAINTS / indexes vs the dictionary"}
    for q in ("SHOW CONSTRAINTS", "SHOW INDEXES"):
        try:
            r = e.execute_cypher(q)
            out[q] = {"columns": r.columns, "rows": [list(map(str, x))[:6] for x in r.rows][:20], "error": r.error}
        except Exception as ex:
            out[q] = f"{type(ex).__name__}: {ex}"[:300]
    out["store_list_indexes"] = [list(map(str, x)) for x in e._store.list_indexes().rows][:20]
    out["dictionary_constraints"] = L.c.sql(
        "SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS "
        "WHERE TABLE_SCHEMA = 'Graph_KG' AND TABLE_NAME IN ('nodes', 'rdf_edges') ORDER BY TABLE_NAME, CONSTRAINT_NAME")
    names = {str(r[1]) for r in out["dictionary_constraints"]}
    out["reported_names_absent_from_dictionary"] = sorted(
        {n for n in ("pk_nodes", "pk_rdf_edges", "node_id_unique", "edge_spo_unique")} - names)
    return out


def f1712(L):
    from iris_vector_graph.stores.lazy_kg import LazyKG
    e = L.eng
    g = "c17mg"
    e.set_multigraph(g, True)
    for n in ("c17:a", "c17:b", "c17:c"):
        e.create_node(n, graph=g)
    q = "USE GRAPH 'c17mg' MATCH (x {id: $s}), (y {id: $o}) CREATE (x)-[:R]->(y)"
    for src in ("c17:a", "c17:a", "c17:c"):  # two parallel a-R->b (multigraph: openCypher CREATE) and c-R->b
        e.execute_cypher(q, {"s": src, "o": "c17:b"})
    edges = L.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ? AND o_id = 'c17:b'", g)[0][0]
    lk = LazyKG(L.c.conn, graph=g)
    out = {"observes": "F-1712", "rows_into_b": edges, "out_degree_a": lk.degree("c17:a"),
           "in_degree_b": lk.in_degree("c17:b"), "in_degree_for_predicate_b": lk.in_degree_for_predicate("c17:b", "R")}
    out["in_degree_undercounts"] = out["in_degree_b"] != edges
    e.erase_graph(g)
    try:
        e.set_multigraph(g, False)
    except Exception as ex:
        out["multigraph_off"] = str(ex)[:200]
    return out


def f1713(L):
    from iris_vector_graph.status import STATUS_PARTS
    s = L.journaled("status()", lambda: L.eng.status())
    st = L.eng.status()
    d = st.to_dict() if hasattr(st, "to_dict") else {}
    return {"observes": "F-1713; status() is a reader (journal)", "STATUS_PARTS": list(STATUS_PARTS),
            "unknown": list(getattr(st, "unknown", []) or []), "report_keys": sorted(d)[:40],
            "parts_not_in_STATUS_PARTS": sorted({"adjacency", "routines"} - set(STATUS_PARTS)),
            "status_journal": _strip(s)}


def f1703(L):
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    out = {"observes": "F-1703: IVG_STRICT_NAMESPACE=1 with a mismatched namespace="}
    os.environ["IVG_STRICT_NAMESPACE"] = "1"
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                st = IRISGraphStore(L.c.conn, namespace="USER")
                # the probe runs on the store's first class-method call (iris_sql_store.py:1085-1086, :816-838)
                ns = st._call_classmethod("%SYSTEM.SYS", "NameSpace")
                out["outcome"] = "returned"
                out["connection_namespace"] = str(ns)
            except Exception as ex:
                out["outcome"] = f"raised {type(ex).__name__}: {ex}"[:300]
            out["warnings"] = [f"{x.category.__name__}: {x.message}"[:300] for x in w]
    finally:
        os.environ.pop("IVG_STRICT_NAMESPACE", None)
    return out


def footprints(L):
    """Journal footprints of the SQL adapter's writers and of readers that must write nothing."""
    e, st = L.eng, L.eng._store
    out = {"observes": "declared write footprints of module 17 entry points"}
    out["store.write_nodes"] = _strip(L.journaled("store.write_nodes", lambda: st.write_nodes(
        [{"id": "c17:w1", "labels": ["C17W"], "properties": {"k": "v"}}, {"id": "c17:w2"}])))
    out["store.write_edges"] = _strip(L.journaled("store.write_edges", lambda: st.write_edges(
        [{"source": "c17:w1", "predicate": "R", "target": "c17:w2"}])))
    out["store.delete_edges"] = _strip(L.journaled("store.delete_edges", lambda: st.delete_edges(
        [("c17:w1", "R", "c17:w2")])))
    out["store.delete_nodes"] = _strip(L.journaled("store.delete_nodes", lambda: st.delete_nodes(["c17:w1", "c17:w2"])))
    out["store.write_temporal_edge"] = _strip(L.journaled("store.write_temporal_edge", lambda: str(
        st.write_temporal_edge("c17:t1", "T", "c17:t2", 1_700_000_000, graph="c17tg"))[:300]))
    L.c.sql("CREATE TABLE IVGAudit.C17RO (id INTEGER PRIMARY KEY)")
    out["store.execute_sql(read_only=True) INSERT"] = _strip(L.journaled(
        "execute_sql read_only", lambda: st.execute_sql("INSERT INTO IVGAudit.C17RO (id) VALUES (?)", [1],
                                                        read_only=True).error))
    out["read_only_insert_landed"] = L.c.sql("SELECT COUNT(*) FROM IVGAudit.C17RO")[0][0]
    L.c.sql("DROP TABLE IVGAudit.C17RO")
    out["verify_sync()"] = _strip(L.journaled("verify_sync()", lambda: str(e.verify_sync())[:500]))
    out["Graph.KG.Meta.Set"] = _strip(L.journaled("Meta.Set", lambda: L.c.call("Graph.KG.Meta", "Set", "c17probe", "1")))
    L.c.call("Graph.KG.Meta", "Delete", "c17probe")
    try:
        e.erase_graph("c17tg")
    except Exception:
        pass
    return out


# ------------------------------------------------------------------------------------------------ server part
PORT, PROXY_PORT = 18750, 18751


def _wait_port(port, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


class DelayProxy:
    """Forwards to the server; holds back the FIRST response for `delay` s (longer than the client timeout)."""

    def __init__(self, delay):
        self.delay, self.count, self.loop, self.server = delay, 0, None, None

    async def handle(self, reader, writer):
        """Pump both directions; for the first request, hold the server's reply for `delay` s."""
        try:
            first = await reader.read(65536)
            if not first:  # a bare connect (the port probe) is not a request
                writer.close()
                return
            self.count += 1
            n = self.count
            ur, uw = await asyncio.open_connection("127.0.0.1", PORT)
            uw.write(first)
            await uw.drain()

            async def up():
                while True:
                    b = await reader.read(65536)
                    if not b:
                        break
                    uw.write(b)
                    await uw.drain()

            async def down():
                held = n == 1
                while True:
                    b = await ur.read(65536)
                    if not b:
                        break
                    if held:
                        await asyncio.sleep(self.delay)  # the server has run the request; its reply is late
                        held = False
                    writer.write(b)
                    await writer.drain()
            await asyncio.wait([asyncio.ensure_future(up()), asyncio.ensure_future(down())],
                               return_when=asyncio.FIRST_COMPLETED, timeout=30)
        except Exception:
            pass
        finally:
            for w in ("writer", "uw"):
                try:
                    locals()[w].close()
                except Exception:
                    pass

    def start(self):
        def run():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.server = self.loop.run_until_complete(asyncio.start_server(self.handle, "127.0.0.1", PROXY_PORT))
            self.loop.run_forever()
        threading.Thread(target=run, daemon=True).start()
        return _wait_port(PROXY_PORT, 10)


def server_part(L):
    from iris_vector_graph.sdk import IVGClient, AsyncIVGClient, IVGClientError, IVGServerError
    env = dict(os.environ, IRIS_HOST="127.0.0.1", IRIS_PORT=os.environ["IVG_PORT"], IRIS_NAMESPACE=NS,
               IRIS_USERNAME="_SYSTEM", IRIS_PASSWORD="SYS", BOLT_ENABLED="0", IVG_API_KEY="c17-key")
    log = open(OUT / "server.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "iris_vector_graph.cypher_api:app", "--host",
                             "127.0.0.1", "--port", str(PORT)], env=env, stdout=log, stderr=subprocess.STDOUT)
    out = {"observes": "F-1714 (401 mapping per SDK call), HD-1702 (client resends a write whose reply was late)",
           "server_pid": proc.pid}
    try:
        if not _wait_port(PORT, 90):
            out["error"] = "server did not start"
            return out
        url = f"http://127.0.0.1:{PORT}"
        nd = OUT / "c17.ndjson"
        nd.write_text(json.dumps({"type": "node", "id": "c17:nd", "labels": ["C17"]}) + "\n")
        calls = {
            "execute_cypher": lambda c: c.execute_cypher("RETURN 1"),
            "load_ndjson": lambda c: c.load_ndjson(str(nd)),
            "explain": lambda c: c.explain("RETURN 1"),
        }
        res = {}
        for name, fn in calls.items():
            c = IVGClient(url, api_key="wrong-key", max_retries=1)
            try:
                fn(c)
                res[name] = "no exception"
            except Exception as ex:
                res[name] = {"class": type(ex).__name__, "module": type(ex).__module__,
                             "is_IVGClientError": isinstance(ex, IVGClientError), "msg": str(ex)[:160]}
            finally:
                c.close()

        async def acall():
            ac = AsyncIVGClient(url, api_key="wrong-key")
            try:
                await ac.execute_cypher("RETURN 1")
                return "no exception"
            except Exception as ex:
                return {"class": type(ex).__name__, "is_IVGClientError": isinstance(ex, IVGClientError)}
            finally:
                await ac.aclose()
        res["AsyncIVGClient.execute_cypher"] = asyncio.run(acall())
        out["wrong_key"] = res

        # HD-1702: a write whose first reply is held back past the client timeout
        proxy = DelayProxy(delay=4.0)
        out["proxy_started"] = proxy.start()
        marker = f"c17dup-{int(time.time())}"
        c = IVGClient(f"http://127.0.0.1:{PROXY_PORT}", api_key="c17-key", timeout=2.0, max_retries=3)
        t0 = time.time()
        try:
            r = c.execute_cypher("CREATE (n:C17Dup {marker: $m}) RETURN n.marker", {"m": marker})
            out["client_answer"] = {"rows": r.rows}
        except Exception as ex:
            out["client_answer"] = {"exception": f"{type(ex).__name__}: {ex}"[:300]}
        finally:
            c.close()
        out["client_seconds"] = round(time.time() - t0, 2)
        out["proxy_requests"] = proxy.count
        time.sleep(1.0)
        cnt = L.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE \"key\" = 'marker' AND val = ?", marker)
        out["nodes_created_for_one_call"] = cnt[0][0]
        out["duplicate_write"] = cnt[0][0] > 1
        try:
            proxy.loop.call_soon_threadsafe(proxy.loop.stop)
        except Exception:
            pass
        return out
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(10)
        out["server_stopped"] = proc.poll() is not None
        log.close()


def cleanup(L):
    e = L.eng
    for g in ("c17g1", "c17g2", "c17mg", "c17tg"):
        try:
            e.erase_graph(g)
        except Exception:
            pass
    for g in (None,):
        try:
            e.delete_nodes_by_prefix("c17", graph=g)
        except Exception:
            pass
    try:
        for (nid,) in L.c.sql("SELECT s FROM Graph_KG.rdf_props WHERE \"key\" = 'marker' AND val %STARTSWITH 'c17dup-'"):
            e.delete_node(nid)
        L.c.sql("DELETE FROM Graph_KG.rdf_labels WHERE label = 'C17Dup'")
    except Exception as ex:
        print("cleanup C17Dup:", ex)
    for t in ("IVGAudit.C17V", "IVGAudit.C17RO"):
        try:
            L.c.sql(f"DROP TABLE {t}")
        except Exception:
            pass


PARTS = {"engine": [("F-1701", f1701), ("F-1705", f1705_and_dbapi), ("F-1707", f1707), ("F-1712", f1712),
                    ("F-1713", f1713), ("F-1703", f1703), ("footprints", footprints)],
         "server": [("server", server_part)], "vec": [("F-1705", f1705_and_dbapi)], "cleanup": []}


def main():
    want = sys.argv[1:] or list(PARTS)
    summary = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    with Lane("c17", embedding_dimension=4) as L:
        try:
            for part in want:
                for name, fn in PARTS[part]:
                    t0 = time.time()
                    try:
                        res = fn(L)
                    except Exception as ex:
                        res = {"exception": f"{type(ex).__name__}: {ex}", "traceback": traceback.format_exc()[-3000:]}
                    res["seconds"] = round(time.time() - t0, 2)
                    res["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    dump(OUT / f"{name}.json", res)
                    summary[name] = res
                    print(name, json.dumps(res, default=str)[:1200])
        finally:
            cleanup(L)
    RESULTS.write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n")


if __name__ == "__main__":
    main()
