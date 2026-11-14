#!/usr/bin/env python3
"""Module 17 (operations): live probes of the stated refusals (OPS kind X) in namespace AUDITE.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 \
        python experiment/playbook-completion/refusals/live_17.py [--out NAME] [case ...]

Each case triggers the refused condition through the product's real entry point: the `ivg` console script (the pin's
iris_vector_graph.cli via PYTHONPATH), the Cypher HTTP server (uvicorn iris_vector_graph.cypher_api:app on
127.0.0.1, AUDITE) and the SDK client, the engine and IRISGraphStore methods, the host layer, LazyKG, the index API
and Graph.KG.PyOps over the Native API. Every case runs in a journal window (rxlib): it holds when the product refuses
as the statement says and the journal of AUDITE's database shows no net change outside the patterns the case names
(table ID counters, which $Increment advances outside any transaction). "Without the web packages" / "without httpx"
/ "outside IRIS" are produced in a child Python process whose import of that package fails (sys.modules[name] =
None) or which is not irispython; nothing in the product is changed.
Results: $RUN_DIR/refusals/17/<NAME or results.json>.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rxlib import Lane, raises, returns, either, run_cases, open_caller_txn, rollback_all, tlevel, NS, REPO  # noqa: E402

# A table's data-global root node is its ID counter ($Increment, not undone by a rollback); IRIS journals it.
COUNTERS = [r"^\^t52S\.\w+\.1$", r"^\^Graph\.KG\.\w+D$"]
# ^KG("__version"): the cache version a nodes-row write bumps outside the transaction ($Increment), which a rollback
# does not take back (incidents/NAMESPACES.md note on the pin's non-transactional counters)
KGVERSION = [r'^\^KG\("__version"\)$']
IVG = str(Path(sys.executable).parent / "ivg")
PORT_KEY, PORT_RO = 18917, 18918
API_KEY = "rx17-key"


def child_env(**extra):
    env = dict(os.environ)
    for k in ("IRIS_HOST", "IRIS_PORT", "IRIS_NAMESPACE", "IRIS_USERNAME", "IRIS_PASSWORD", "IVG_URL", "IVG_API_KEY"):
        env.pop(k, None)
    env["PYTHONPATH"] = str(REPO)
    env.update(extra)
    return env


def run(cmd, env=None, timeout=120):
    r = subprocess.run(cmd, env=env or child_env(), capture_output=True, text=True, timeout=timeout, cwd=str(REPO))
    return {"rc": r.returncode, "stdout": r.stdout[-1500:], "stderr": r.stderr[-2500:]}


def py(code, env=None, timeout=120):
    return run([sys.executable, "-c", code], env=env, timeout=timeout)


def ivg(*args, env=None, timeout=120):
    return run([IVG, *args], env=env, timeout=timeout)


def port_free(p):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", p)) != 0


def wait_port(p, timeout=90):
    t = time.time()
    while time.time() - t < timeout:
        if not port_free(p):
            return True
        time.sleep(0.5)
    return False


@contextlib.contextmanager
def server(L, port, **envx):
    """The Cypher HTTP server on AUDITE (uvicorn iris_vector_graph.cypher_api:app), stopped with SIGINT."""
    if not port_free(port):
        raise RuntimeError(f"port {port} is in use")
    env = child_env(IRIS_HOST="127.0.0.1", IRIS_PORT=os.environ["IVG_PORT"], IRIS_NAMESPACE=NS,
                    IRIS_USERNAME="_SYSTEM", IRIS_PASSWORD="SYS", BOLT_ENABLED="0", **envx)
    log = open(L.out / f"server-{port}.log", "a")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "iris_vector_graph.cypher_api:app", "--host", "127.0.0.1",
                             "--port", str(port)], env=env, stdout=log, stderr=subprocess.STDOUT, cwd=str(REPO))
    try:
        if not wait_port(port, 90):
            raise RuntimeError("server did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(10)
        log.close()


def vector_width(L):
    rows = L.c.sql("SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='Graph_KG' "
                   "AND TABLE_NAME='kg_NodeEmbeddings' AND COLUMN_NAME='emb'")
    t = str(rows[0][0]) if rows else ""
    m = re.search(r"(\d+)\s*\)?\s*$", t)
    return t, (int(m.group(1)) if m else None)


# ---------------------------------------------------------------------------------------------------- CLI
def c_cli(L):
    which = py("import iris_vector_graph, sys; print(iris_vector_graph.__file__)")
    L.note("OPS-X1.10.2", "setup: the ivg script's package is the pin's worktree", file=which["stdout"].strip(),
           ivg=IVG)
    L.refusal("OPS-X1.10.2", "ivg embeddings inventory with no IRIS_HOST -> exit 1 naming IRIS_HOST/--iris-host",
              lambda: ivg("embeddings", "inventory"),
              returns(lambda r: r["rc"] == 1 and "IRIS_HOST" in r["stderr"] and "--iris-host" in r["stderr"],
                      "exit 1, stderr names IRIS_HOST and --iris-host"), entry="ivg embeddings inventory")
    L.refusal("OPS-X1.10.2", "ivg fhir status with no IRIS_HOST -> exit 1 naming IRIS_HOST/--iris-host",
              lambda: ivg("fhir", "status", "rx17g"),
              returns(lambda r: r["rc"] == 1 and "IRIS_HOST" in r["stderr"] and "--iris-host" in r["stderr"],
                      "exit 1, stderr names IRIS_HOST and --iris-host"), entry="ivg fhir status")
    # an unreachable IRIS address: an engine call would fail with a connection error ("fhir: ...", exit 1)
    unreachable = ("--iris-host", "127.0.0.1", "--iris-port", "9")
    L.refusal("OPS-X1.11.1", "ivg fhir sync without --once -> usage error naming ivg fhir schedule, engine not called",
              lambda: ivg("fhir", "sync", "rx17g", *unreachable),
              returns(lambda r: r["rc"] == 2 and "ivg fhir schedule" in r["stderr"] and "fhir:" not in r["stderr"],
                      "exit 2 (click UsageError) naming `ivg fhir schedule`, no engine error"),
              entry="ivg fhir sync")
    L.refusal("OPS-X1.11.3", "ivg fhir register --no-links --link X -> usage error",
              lambda: ivg("fhir", "register", "--no-links", "--link", "Library.relatedArtifact", *unreachable),
              returns(lambda r: r["rc"] == 2 and "--no-links and --link cannot be combined" in r["stderr"]
                      and "fhir:" not in r["stderr"], "exit 2, '--no-links and --link cannot be combined'"),
              entry="ivg fhir register")
    code = ("import sys; sys.modules['uvicorn'] = None; sys.argv = ['ivg', 'server', 'start', '--host', '127.0.0.1', "
            "'--port', '18919']; from iris_vector_graph.cli import main; main()")
    L.refusal("OPS-X1.12.4", "ivg server start without uvicorn -> install hint, exit 1",
              lambda: py(code),
              returns(lambda r: r["rc"] == 1 and "pip install 'iris-vector-graph[full]'" in (r["stderr"] + r["stdout"]),
                      "exit 1, prints pip install 'iris-vector-graph[full]'"),
              entry="ivg server start (child process whose import of uvicorn fails)")


def c_schema_init(L):
    """OPS-X1.8.1: schema init over the server at another vector width -> 409, CLI exit 1 naming --rewidth."""
    L.reset()
    w = int(str(L.c.call("Graph.KG.PyOps", "getExpectedDimension", "", "")))
    L.note("OPS-X1.8.1", "setup: AUDITE vector width (PyOps.getExpectedDimension) and stored vectors", width=w,
           vectors=L.c.sql("SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings")[0][0])
    other = w + 3
    with server(L, PORT_KEY, IVG_API_KEY=API_KEY) as url:
        L.refusal("OPS-X1.8.1", f"ivg schema init --embedding-dim {other} (tables at {w}) -> 409, exit 1, names --rewidth",
                  lambda: ivg("--url", url, "--api-key", API_KEY, "schema", "init", "--embedding-dim", str(other)),
                  returns(lambda r: r["rc"] == 1 and "409" in r["stderr"] and "--rewidth" in r["stderr"],
                          "exit 1, stderr 'Schema init refused (409)' and '--rewidth'"),
                  allowed=COUNTERS, entry="ivg schema init -> POST /admin/schema/init")
    L.note("OPS-X1.8.1", "after: vector width unchanged",
           width=int(str(L.c.call("Graph.KG.PyOps", "getExpectedDimension", "", ""))))


# ---------------------------------------------------------------------------------------------------- engine/admin
def c_refused_namespace(L):
    """OPS-X2.1.1: an engine whose IVG Schema the namespace does not record: most calls refused; status, dry-run
    legacy removal and close run."""
    from iris_vector_graph.engine import IRISGraphEngine
    L.reset()
    rec = L.c.o.get("IVG.Deploy", "schema") if int(L.c.o.isDefined("IVG.Deploy", "schema")) else None
    L.note("OPS-X2.1.1", "setup: the namespace's recorded IVG Schema", record=str(rec))
    c2 = L.conn()
    holder = {}

    def build():
        holder["e"] = IRISGraphEngine(c2.conn, schema_prefix="RX17ALT", embedding_dimension=4)
        return "built"
    L.refusal("OPS-X2.1.1", "engine on schema RX17ALT: construction answers (the check is pending)", build,
              returns(lambda r: r == "built", "constructed"), entry="IRISGraphEngine(schema_prefix='RX17ALT')")
    e = holder.get("e")
    if e is None:
        return
    for name, fn in (("create_node", lambda: e.create_node("rx17:alt", labels=["RX17"])),
                     ("get_node", lambda: e.get_node("rx17:alt")),
                     ("node_count", lambda: e.node_count()),
                     ("execute_cypher", lambda: e.execute_cypher("MATCH (n) RETURN count(n)"))):
        L.refusal("OPS-X2.1.1", f"refused engine: {name} -> IVGSchemaError", fn, raises("IVGSchemaError"),
                  entry=f"engine.{name}")
    L.refusal("OPS-X2.1.1", "refused engine: status() still runs", lambda: type(e.status()).__name__,
              returns(lambda r: isinstance(r, str), "a status report"), entry="engine.status")
    L.refusal("OPS-X2.1.1", "refused engine: remove_legacy_objects(dry_run=True) still runs",
              lambda: e.remove_legacy_objects(dry_run=True), returns(lambda r: isinstance(r, list), "a list"),
              entry="engine.remove_legacy_objects(dry_run=True)")
    L.note("OPS-X2.1.1", "IRISGraphEngine has a close method", has_close=hasattr(e, "close"),
           store_has_close=hasattr(e._store, "close"))
    L.refusal("OPS-X2.1.1", "refused engine: its store's close() still runs", lambda: (e._store.close(), "closed")[1],
              returns(lambda r: r == "closed", "closed"), entry="engine._store.close (IRISGraphStore.close)")
    L.refusal("OPS-X2.1.1", "refused engine: its store's get_nodes is refused",
              lambda: e._store.get_nodes(["rx17:alt"]), raises("IVGSchemaError"), entry="engine._store.get_nodes")
    L.drop(c2)


def c_admin(L):
    L.reset()
    e = L.eng
    for bad in ("0", "a\x01b", 42):
        L.refusal("OPS-X3.2.1", f"verify_graph({bad!r}) -> ValueError", lambda bad=bad: e.verify_graph(bad),
                  raises("ValueError"), entry="engine.verify_graph")
    # a listing that fails: the engine's connection is closed under it
    from iris_vector_graph.engine import IRISGraphEngine
    c2 = L.conn()
    e2 = IRISGraphEngine(c2.conn, embedding_dimension=4)
    ok = e2.list_active_queries(5)
    L.note("OPS-X3.4.1", "control: list_active_queries answers on an open connection", rows=len(ok))
    c2.conn.close()
    L.refusal("OPS-X3.4.1", "list_active_queries on a connection that fails -> raises, not []",
              lambda: e2.list_active_queries(5), raises("Exception"), entry="engine.list_active_queries")
    L.drop(c2)
    import logging
    msgs = []

    class H(logging.Handler):
        def emit(self, rec):
            msgs.append(rec.getMessage())
    h = H()
    logging.getLogger("iris_vector_graph").addHandler(h)
    try:
        for qid in ("999999999", "not-a-process"):
            n0 = len(msgs)
            L.refusal("OPS-X3.5.1", f"kill_query({qid!r}) -> False with a warning, not raised",
                      lambda qid=qid: e.kill_query(qid),
                      returns(lambda r: r is False, "False"), entry="engine.kill_query",
                      after=lambda n0=n0: {"warnings": [m[:200] for m in msgs[n0:]]})
        c3 = L.conn()
        n0 = len(msgs)
        answered = e.kill_query(c3.pid)
        try:
            alive = int(str(c3.call("%SYSTEM.SYS", "ProcessID"))) == int(c3.pid)
        except Exception as ex:  # noqa: BLE001
            alive = f"dead: {type(ex).__name__}"
        L.note("OPS-X3.5.1", "kill_query on the lane's own scratch process (a killable one)", pid=c3.pid,
               answered=answered, process_alive_after=alive, warnings=[m[:300] for m in msgs[n0:]])
        L.drop(c3)
    finally:
        logging.getLogger("iris_vector_graph").removeHandler(h)


def c_caller_txn(L):
    """OPS-X3.8.1 and OPS-X7.3: remove_legacy_objects(dry_run=False) in a caller transaction that holds a write."""
    L.reset()
    lvl = open_caller_txn(L.c.conn, "INSERT INTO Graph_KG.nodes (node_id) VALUES ('rx17:txn')")
    L.note("OPS-X3.8.1", "setup: caller transaction open", tlevel=lvl)
    rec = L.refusal("OPS-X3.8.1", "remove_legacy_objects(dry_run=False) with a caller write -> CallerTransactionOpenError",
                    lambda: L.eng.remove_legacy_objects(dry_run=False), raises("CallerTransactionOpenError"),
                    keep_txn=True, entry="engine.remove_legacy_objects(dry_run=False)",
                    after=lambda: {"tlevel": tlevel(L.c.conn), "caller_row_pending": L.c.sql(
                        "SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id='rx17:txn'")[0][0]})
    L.refusal("OPS-X3.8.1", "remove_legacy_objects(dry_run=True) in the same transaction is allowed",
              lambda: type(L.eng.remove_legacy_objects(dry_run=True)).__name__,
              returns(lambda r: r == "list", "a list (dry run allowed)"), keep_txn=True,
              entry="engine.remove_legacy_objects(dry_run=True)")
    msg = (rec.get("exception") or {}).get("message", "")
    L.refusal("OPS-X7.3", "the refusal says nothing was done and the transaction is still open; it is",
              lambda: {"message": msg, "tlevel": tlevel(L.c.conn), "caller_row_pending": L.c.sql(
                  "SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id='rx17:txn'")[0][0]},
              returns(lambda r: "Nothing was done" in r["message"] and "still open" in r["message"]
                      and r["tlevel"] == 1 and r["caller_row_pending"] == 1,
                      "message 'Nothing was done' + 'still open'; $TLEVEL 1; the caller's row still pending"),
              keep_txn=True, entry="CallerTransactionOpenError (engine.remove_legacy_objects)")
    open_caller_txn_restore = None  # noqa: F841
    rollback_all(L.c.conn)
    # the same refusal through another 4.7.0 call (initialize_schema), message checked the same way
    open_caller_txn(L.c.conn, "INSERT INTO Graph_KG.nodes (node_id) VALUES ('rx17:txn2')")
    L.refusal("OPS-X7.3", "initialize_schema() with a caller write -> CallerTransactionOpenError, nothing done",
              lambda: L.eng.initialize_schema(), raises("CallerTransactionOpenError", match="Nothing was done"),
              keep_txn=True, entry="engine.initialize_schema",
              after=lambda: {"tlevel": tlevel(L.c.conn)})
    rollback_all(L.c.conn)


def c_host(L):
    from iris_vector_graph.host import host_for
    h = host_for(L.c.conn)
    L.note("OPS-X4.2", "setup: host class", cls=type(h).__name__)
    for name, fn in (("call", lambda: h.call("Graph.KG.Snapshot", "%New")),
                     ("call_large", lambda: h.call_large("Graph.KG.Snapshot", "%New")),
                     ("call %ExistsId", lambda: h.call("Graph.KG.Meta", "%ExistsId", "1"))):
        L.refusal("OPS-X4.2", f"host.{name} of a %-method -> HostError", fn, raises("HostError", match="'%' method"),
                  entry=f"{type(h).__name__}.{name.split()[0]}")


def c_embedded(L):
    code = ("import json\n"
            "out = {}\n"
            "from iris_vector_graph.embedded import EmbeddedConnection\n"
            "for name in ('engine', 'cursor'):\n"
            "    try:\n"
            "        if name == 'engine':\n"
            "            from iris_vector_graph.engine import IRISGraphEngine\n"
            "            IRISGraphEngine(EmbeddedConnection())\n"
            "        else:\n"
            "            EmbeddedConnection().cursor().execute('SELECT 1')\n"
            "        out[name] = 'no exception'\n"
            "    except BaseException as e:\n"
            "        out[name] = {'type': type(e).__name__, 'mro': [k.__name__ for k in type(e).__mro__][:4], 'msg': str(e)[:400]}\n"
            "print('RESULT' + json.dumps(out))\n")

    def go():
        r = py(code)
        line = next((ln for ln in r["stdout"].splitlines() if ln.startswith("RESULT")), None)
        return {"rc": r["rc"], "result": json.loads(line[6:]) if line else None, "stderr": r["stderr"][-600:]}
    L.refusal("OPS-X4.6.1", "EmbeddedConnection outside IRIS: engine and cursor refused naming iris.connect",
              go, returns(lambda r: r["result"] and all(isinstance(v, dict) and "ImportError" in v["mro"]
                                                        and "iris.connect" in v["msg"] for v in r["result"].values()),
                          "both raise an ImportError naming iris.connect"),
              entry="IRISGraphEngine(EmbeddedConnection()) / EmbeddedConnection().cursor() (child, not irispython)")


def c_strict_ns(L):
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    os.environ["IVG_STRICT_NAMESPACE"] = "1"
    caught = []
    try:
        def go():
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                st = IRISGraphStore(L.c.conn, namespace="USER")
                ns = st._call_classmethod("%SYSTEM.SYS", "NameSpace")
                caught.extend(f"{x.category.__name__}: {str(x.message)[:200]}" for x in w)
                return {"returned_namespace": str(ns)}
        L.refusal("OPS-X4.8.2", "IVG_STRICT_NAMESPACE=1, store namespace='USER' on an AUDITE connection -> error",
                  go, raises("Exception", match="mismatch"), entry="IRISGraphStore(namespace='USER') first class call",
                  after=lambda: {"warnings": list(caught)})
    finally:
        os.environ.pop("IVG_STRICT_NAMESPACE", None)


# ---------------------------------------------------------------------------------------------------- store
def c_store(L):
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    from iris_vector_graph.stores.lazy_kg import LazyKG
    L.reset()
    e = L.eng
    e.create_node("rx17:d1", labels=["RX17"])
    e.create_node("rx17:d2", labels=["RX17"])
    e.create_edge("rx17:d1", "R", "rx17:d2")
    L.c.conn.commit()
    st = IRISGraphStore(L.c.conn)
    L.refusal("OPS-X5.4.1", "store.write_nodes: second node id over 256 chars -> GraphWriteError, first undone",
              lambda: st.write_nodes([{"id": "rx17:w1", "labels": ["RX17"]}, {"id": "rx17:" + "x" * 300}]),
              raises("GraphWriteError"), allowed=COUNTERS + KGVERSION, entry="IRISGraphStore.write_nodes",
              after=lambda: {"rx17_w1_rows": L.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id='rx17:w1'")[0][0]})
    for bad in ("0", "g\x01"):
        L.refusal("OPS-X5.6.2", f"store.delete_nodes(graph={bad!r}) -> ValueError before any statement",
                  lambda bad=bad: st.delete_nodes(["rx17:d1"], graph=bad), raises("ValueError"),
                  entry="IRISGraphStore.delete_nodes")
    for p in ("", None):
        L.refusal("OPS-X5.7", f"store.delete_nodes_by_prefix({p!r}) -> ValueError naming erase_graph",
                  lambda p=p: st.delete_nodes_by_prefix(p), raises("ValueError", match="erase_graph"),
                  entry="IRISGraphStore.delete_nodes_by_prefix",
                  after=lambda: {"rx17_nodes": L.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'rx17'")[0][0]})
    L.refusal("OPS-X5.10.1", "store.execute_transaction: second statement fails -> GraphWriteError, first undone",
              lambda: st.execute_transaction(["INSERT INTO Graph_KG.nodes (node_id) VALUES (?)",
                                              "INSERT INTO Graph_KG.rx17_no_such_table (x) VALUES (?)"],
                                             [["rx17:t1"], ["x"]]),
              raises("GraphWriteError"), allowed=COUNTERS, entry="IRISGraphStore.execute_transaction",
              after=lambda: {"rx17_t1_rows": L.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id='rx17:t1'")[0][0]})
    L.refusal("OPS-X5.10.2", "Cypher DELETE of a node with an edge -> refused (ConstraintVerificationFailed)",
              lambda: e.execute_cypher("MATCH (n {node_id: 'rx17:d1'}) DELETE n"),
              raises("GraphWriteError", match="ConstraintVerificationFailed"), allowed=COUNTERS,
              entry="engine.execute_cypher",
              after=lambda: {"rx17_d1_rows": L.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id='rx17:d1'")[0][0],
                             "edges": L.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s='rx17:d1'")[0][0]})
    try:
        r = e.execute_cypher("MATCH (n {node_id: 'rx17:d1'}) DETACH DELETE n")
        L.c.conn.commit()
        L.note("OPS-X5.10.2", "control: DETACH DELETE removes it", error=getattr(r, "error", None),
               rows=L.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id='rx17:d1'")[0][0])
    except Exception as ex:  # noqa: BLE001
        L.note("OPS-X5.10.2", "control: DETACH DELETE", error=f"{type(ex).__name__}: {ex}"[:300])
    for bad in ("0", "g\x02"):
        L.refusal("OPS-X5.19.1", f"LazyKG(conn, graph={bad!r}) -> refused at construction",
                  lambda bad=bad: LazyKG(L.c.conn, graph=bad), raises("ValueError"), entry="LazyKG.__init__")


# ---------------------------------------------------------------------------------------------------- SDK
def c_sdk(L):
    from iris_vector_graph.sdk import IVGClient, IVGClientError
    L.reset()
    nd = L.out / "rx17.ndjson"
    nd.write_text(json.dumps({"type": "node", "id": "rx17:nd", "labels": ["RX17"]}) + "\n")
    with server(L, PORT_KEY, IVG_API_KEY=API_KEY) as url:
        def with_client(fn, key="wrong-key"):
            def go():
                c = IVGClient(url, api_key=key, max_retries=1)
                try:
                    return fn(c)
                finally:
                    c.close()
            return go
        is401 = raises("IVGClientError", attr={"http_code": 401})
        for name, fn in (("execute_cypher (query)", lambda c: c.execute_cypher("RETURN 1")),
                         ("stats (read)", lambda c: c.stats()),
                         ("schema (read)", lambda c: c.schema()),
                         ("explain (query)", lambda c: c.explain("RETURN 1")),
                         ("load_ndjson", lambda c: c.load_ndjson(str(nd)))):
            L.refusal("OPS-X6.2", f"wrong API key: {name} -> IVGClientError 401", with_client(fn), is401,
                      allowed=COUNTERS, entry=f"IVGClient.{name.split()[0]} -> server with IVG_API_KEY")
        L.note("OPS-X6.2", "control: the right key answers",
               rows=with_client(lambda c: c.execute_cypher("RETURN 1").rows, key=API_KEY)())
    with server(L, PORT_RO, IVG_READ_ONLY="true") as url:
        def ro(fn):
            def go():
                c = IVGClient(url, max_retries=1)
                try:
                    return fn(c)
                finally:
                    c.close()
            return go
        L.refusal("OPS-X6.2", "read-only server: CREATE via execute_cypher -> IVGClientError 403",
                  ro(lambda c: c.execute_cypher("CREATE (n:RX17RO {node_id: 'rx17:ro'}) RETURN n")),
                  raises("IVGClientError", attr={"http_code": 403}), allowed=COUNTERS,
                  entry="IVGClient.execute_cypher -> server with IVG_READ_ONLY=true")
        L.refusal("OPS-X6.2", "read-only server: load_ndjson -> IVGClientError 403",
                  ro(lambda c: c.load_ndjson(str(nd))),
                  raises("IVGClientError", attr={"http_code": 403}), allowed=COUNTERS,
                  entry="IVGClient.load_ndjson -> server with IVG_READ_ONLY=true")
    closed = "http://127.0.0.1:9"

    def retries():
        c = IVGClient(closed, max_retries=2, timeout=2.0)
        try:
            return c.execute_cypher("RETURN 1")
        finally:
            c.close()
    L.refusal("OPS-X6.4.1", "every try fails to connect -> IVGClientError naming the 2 tries, http_code None",
              retries, raises("IVGClientError", match=r"after 2 attempts", attr={"http_code": None}),
              entry="IVGClient.execute_cypher (nothing listening)")
    for bad in ("0", "g\x03"):
        def nc(bad=bad):
            c = IVGClient(closed, max_retries=1, timeout=1.0)
            try:
                return c.node_count(bad)
            finally:
                c.close()
        L.refusal("OPS-X6.5.1", f"IVGClient.node_count({bad!r}) -> ValueError before any request", nc,
                  raises("ValueError"), entry="IVGClient.node_count (a request would fail to connect)")
    code = ("import sys; sys.modules['httpx'] = None\n"
            "from iris_vector_graph.sdk import IVGClient, AsyncIVGClient\n"
            "for k in (IVGClient, AsyncIVGClient):\n"
            "    try:\n"
            "        k('http://127.0.0.1:9'); print(k.__name__, 'no exception')\n"
            "    except ImportError as e:\n"
            "        print(k.__name__, 'ImportError', e)\n")
    L.refusal("OPS-X6.7", "IVGClient / AsyncIVGClient without httpx -> ImportError 'pip install httpx'",
              lambda: py(code),
              returns(lambda r: r["stdout"].count("ImportError") == 2 and r["stdout"].count("pip install httpx") == 2,
                      "both raise ImportError naming pip install httpx"),
              entry="IVGClient(...) in a child process whose import of httpx fails")


# ---------------------------------------------------------------------------------------------------- indexes
def c_index(L):
    from iris_vector_graph.index_config import VectorIndexConfig, FulltextIndexConfig
    L.reset()
    e = L.fresh_engine()
    idx = e.create_index(VectorIndexConfig(name="rx17idx", method="ivf", nlist=4))
    L.refusal("OPS-X8.1", "search on an index never built -> IndexNotBuiltError saying to build it",
              lambda: idx.search([0.1, 0.2, 0.3, 0.4], k=3), raises("IndexNotBuiltError", match="build"),
              entry="engine.create_index(...).search")
    for name, kw in (("unknown field", {"name": "rx17c", "bogus": 1}), ("nlist 0", {"name": "rx17c", "nlist": 0}),
                     ("empty name", {"name": ""}), ("bad metric", {"name": "rx17c", "metric": "manhattan"})):
        L.refusal("OPS-X8.2", f"VectorIndexConfig with {name} -> ValidationError",
                  lambda kw=kw: VectorIndexConfig(**kw), raises("ValidationError", "ValueError"),
                  entry="iris_vector_graph.index_config.VectorIndexConfig")
    L.refusal("OPS-X8.2", "FulltextIndexConfig b=2 -> ValidationError",
              lambda: FulltextIndexConfig(name="rx17f", properties=["name"], b=2),
              raises("ValidationError", "ValueError"), entry="FulltextIndexConfig")


# ---------------------------------------------------------------------------------------------------- PyOps
def c_pyops(L):
    L.reset()
    o = L.c.o
    try:
        exp = o.classMethodValue("Graph.KG.PyOps", "getExpectedDimension", "", "")
    except Exception as ex:  # noqa: BLE001
        L.note("OPS-X10.4.1", "setup: embedded Python (PyOps) not callable", error=f"{type(ex).__name__}: {ex}"[:400])
        return
    L.note("OPS-X10.4.1", "setup: PyOps expected width of the default graph", expected=str(exp))
    width = int(str(exp)) if str(exp).isdigit() else 0
    wrong = width + 1 if width else 3
    arr = o.classMethodObject("%DynamicArray", "%FromJSON", json.dumps([0.5] * wrong))
    L.refusal("OPS-X10.4.1", f"VectorSearch with a {wrong}-wide vector (expected {width}) -> ValueError naming both",
              lambda: o.classMethodObject("Graph.KG.PyOps", "VectorSearch", arr, 5, "", ""),
              raises("Exception", match=rf"dimension {wrong} does not match expected {width}"),
              entry="Graph.KG.PyOps.VectorSearch (Native API)")
    # X10.4.2: a registry row whose table name is not the route shape (data any IVG-Schema writer can insert)
    good = o.classMethodObject("%DynamicArray", "%FromJSON", json.dumps([0.5] * width)) if width else None
    rows = [("rx17g", "nodes", "DOUBLE", "nodes"), ("rx17h", "kg_emb_0123456789abcdef", "DOUBLE),(1",
                                                    "element type")]
    try:
        for g, tname, dtype, what in rows:
            L.c.sql("INSERT INTO Graph_KG.embedding_registry (table_name, graph_id, model_key, dimension, dtype) "
                    "VALUES (?, ?, '', ?, ?)", tname, g, width or 4, dtype)
            L.c.conn.commit()
            L.note("OPS-X10.4.2", f"setup: registry row for graph {g} names {tname!r} dtype {dtype!r}")
            L.refusal("OPS-X10.4.2", f"VectorSearch in graph {g}: registry names {tname!r} -> refused ({what})",
                      lambda g=g: o.classMethodObject("Graph.KG.PyOps", "VectorSearch", good, 5, "", g),
                      raises("Exception", match="not a node route|unknown element type"),
                      entry="Graph.KG.PyOps.VectorSearch -> RouteVectorRows (Native API)")
    finally:
        L.c.sql("DELETE FROM Graph_KG.embedding_registry WHERE graph_id IN ('rx17g', 'rx17h')")
        L.c.conn.commit()


CASES = [("cli", c_cli), ("schema_init", c_schema_init), ("refused_namespace", c_refused_namespace),
         ("admin", c_admin), ("caller_txn", c_caller_txn), ("host", c_host), ("embedded", c_embedded),
         ("strict_ns", c_strict_ns), ("store", c_store), ("sdk", c_sdk), ("index", c_index), ("pyops", c_pyops)]


def main():
    args = sys.argv[1:]
    out = "results.json"
    if args[:1] == ["--out"]:
        out, args = args[1], args[2:]
    only = args or None
    with Lane("17") as L:
        L.reset()
        L.control()
        run_cases(L, CASES, only)
        L.reset()
        L.note("-", "final: ledger state and rx17 rows after the last reset",
               ledger=json.loads(str(L.c.call("Graph.KG.Ledger", "Meta"))).get("state"),
               rx17_nodes=L.c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'rx17'")[0][0],
               registry_rx17=L.c.sql("SELECT COUNT(*) FROM Graph_KG.embedding_registry WHERE graph_id %STARTSWITH 'rx17'")[0][0])
        L.save(out if (not only or out != "results.json") else "results-partial.json")


if __name__ == "__main__":
    main()
