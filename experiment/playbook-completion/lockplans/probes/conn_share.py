#!/usr/bin/env python3
"""Module 16 lock plan: who uses one IRIS DB-API connection, from which threads, and at once? (AUDITD, live, 127.0.0.1)

    locks.sh iris python conn_share.py OUT_DIR [--seconds S]          # parent: setup, then one child per part
    python conn_share.py OUT_DIR --part raw|http|sample --seconds S    # a child (own process: a driver crash stays here)

Premise P-1605 (experiment/playbook-uplift/trust/16.md:31-35): the driver declares `iris.dbapi.threadsafety = 1`, and
two threads using one connection at once can lose a statement handle (CHANGELOG.md:304-310, 4.6.5, observed on IRIS
2026.3.0AI.154 with driver 5.4.1). PEP 249 defines threadsafety 1 as "threads may share the module, but not
connections", where sharing means use "without wrapping it using a mutex semaphore". So the lock-plan obligation of a
server that keeps one connection for all requests is: every use of that connection is inside one mutex, and no
cursor outlives it.

Instrumentation (test process only; product code is not changed): the driver's own Python classes are wrapped so
each call that goes to the server on a connection (IRISConnection.cursor / commit / rollback, Cursor.execute /
executemany / fetchone / fetchmany / fetchall / close, and the Native API IRIS object's class-method, global and
transaction calls) records the connection, the calling thread, and how many calls are in flight on that connection
at that moment. An overlap is a call that starts while another thread's call on the same connection is in flight.

Parts:
- raw: one identity-checked connection, two threads, no mutex, S seconds (each thread checks its answers); then the
  same with a threading.Lock around each statement (control: no overlap). Tests whether P-1605's failure appears on
  this build and driver, and that the detector sees overlaps when they happen.
- http: iris_vector_graph.cypher_api.app (the Cypher HTTP server, _engine_lock RLock, cypher_api.py:146-153, 220-224,
  239-250) served by uvicorn on 127.0.0.1 inside this process, its cached engine pre-set on an identity-checked
  connection (cypher_api._engine_cache, as live/breadth-c/16/s6_status_maps.py does); no IRIS_HOST, so the product
  opens no unchecked connection; BOLT_ENABLED=0. Client threads hit /health, POST /api/cypher (read and write),
  /stats, /schema and POST /admin/load (async route that waits in the thread pool) for S seconds.
- sample: api.main.create_app(engine) (the sample API, no lock: api/main.py:100-113, api/routers/cypher.py:89-97)
  served the same way; client threads hit /health (sync def: thread pool) and POST /api/cypher (async def: the event
  loop thread) for S seconds.
Oracle: http: no overlap on the server's connection (max in flight 1), every answer 200 and right. sample: an
overlap is the lock-plan violation itself (API-B4.5); errors and wrong answers are counted separately (F-1608's
symptom).
"""
from __future__ import annotations

import collections
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lpcommon as L  # noqa: E402

N_SEED = 20
# The product's own connection factories (cypher_api._make_engine, api.main.get_engine) must never reach an IRIS: they
# get a closed local port (as live/breadth-c/16/s6_status_maps.py's NOIRIS); every connection here is iris_conn.Conn's.
NOIRIS = {"IRIS_HOST": "127.0.0.1", "IRIS_PORT": "1", "IRIS_NAMESPACE": "AUDITD", "IRIS_USERNAME": "_SYSTEM",
          "IRIS_USER": "_SYSTEM", "IRIS_PASSWORD": "SYS"}


# ------------------------------------------------------------------------------------------- instrumentation
class Meter:
    def __init__(self):
        self.lk = threading.Lock()
        self.owner = {}          # id(cursor or IRIS object) -> id(connection)
        self.keep = []           # keep wrapped objects alive so ids are not reused
        self.inflight = collections.Counter()
        self.holder = collections.defaultdict(collections.Counter)
        self.max_inflight = collections.Counter()
        self.calls = collections.Counter()
        self.overlaps = collections.Counter()
        self.threads = collections.defaultdict(set)
        self.examples = collections.defaultdict(list)

    def enter(self, cid, what):
        t = threading.get_ident()
        with self.lk:
            self.calls[cid] += 1
            self.threads[cid].add(t)
            others = [x for x, n in self.holder[cid].items() if n and x != t]
            if others:
                self.overlaps[cid] += 1
                if len(self.examples[cid]) < 5:
                    self.examples[cid].append({"call": what, "thread": t, "other_threads_in_flight": others,
                                               "t": time.time()})
            self.holder[cid][t] += 1
            self.inflight[cid] += 1
            self.max_inflight[cid] = max(self.max_inflight[cid], len([x for x, n in self.holder[cid].items() if n]))

    def leave(self, cid):
        t = threading.get_ident()
        with self.lk:
            self.holder[cid][t] -= 1
            self.inflight[cid] -= 1

    def report(self, cid):
        return {"calls": self.calls[cid], "threads": len(self.threads[cid]), "overlaps": self.overlaps[cid],
                "max_threads_in_flight": self.max_inflight[cid], "examples": self.examples[cid]}


M = Meter()


def install():
    import iris
    import iris.dbapi

    def wrap(cls, name, cid_of):
        orig = getattr(cls, name, None)
        if orig is None:
            return

        def w(self, *a, **k):
            cid = cid_of(self)
            if cid is None:
                return orig(self, *a, **k)
            M.enter(cid, f"{cls.__name__}.{name}")
            try:
                return orig(self, *a, **k)
            finally:
                M.leave(cid)
        setattr(cls, name, w)

    conn_cls = iris.IRISConnection
    orig_cursor = conn_cls.cursor

    def cursor(self, *a, **k):
        cid = id(self)
        M.enter(cid, "IRISConnection.cursor")
        try:
            cur = orig_cursor(self, *a, **k)
        finally:
            M.leave(cid)
        with M.lk:
            M.owner[id(cur)] = cid
            M.keep.append(cur)
        return cur
    conn_cls.cursor = cursor
    for n in ("commit", "rollback"):
        wrap(conn_cls, n, lambda self: id(self))
    for n in ("execute", "executemany", "fetchone", "fetchmany", "fetchall", "close", "callproc"):
        wrap(iris.dbapi.Cursor, n, lambda self: M.owner.get(id(self)))
    orig_create = iris.createIRIS

    def createIRIS(conn, *a, **k):
        obj = orig_create(conn, *a, **k)
        with M.lk:
            M.owner[id(obj)] = id(conn)
            M.keep.append(obj)
        return obj
    iris.createIRIS = createIRIS
    for n in ("classMethodValue", "classMethodVoid", "classMethodString", "classMethodInteger", "classMethodBoolean",
              "classMethodObject", "get", "getString", "set", "kill", "isDefined", "increment", "lock", "unlock",
              "releaseAllLocks", "getTLevel", "tStart", "tCommit", "tRollback", "tRollbackOne", "procedure",
              "function"):
        wrap(iris.IRIS, n, lambda self: M.owner.get(id(self)))


# ------------------------------------------------------------------------------------------- parts
def part_raw(seconds):
    install()
    c = L.conn()
    cid = id(c.conn)
    out = {}
    for mode in ("no-lock", "with-lock"):
        lk = threading.Lock() if mode == "with-lock" else None
        st = {"t1": collections.Counter(), "t2": collections.Counter()}
        errs = []
        stop = time.time() + seconds

        def run(tag, sql, args, check):
            while time.time() < stop:
                try:
                    if lk:
                        lk.acquire()
                    try:
                        cur = c.conn.cursor()
                        cur.execute(sql, args) if args else cur.execute(sql)
                        row = cur.fetchone()
                        cur.close()
                    finally:
                        if lk:
                            lk.release()
                    st[tag]["n"] += 1
                    if not check(row):
                        st[tag]["wrong"] += 1
                        if len(errs) < 10:
                            errs.append({"thread": tag, "wrong_answer": str(row)[:200]})
                except Exception as ex:  # noqa: BLE001
                    st[tag]["error"] += 1
                    if len(errs) < 10:
                        errs.append({"thread": tag, "error": f"{type(ex).__name__}: {str(ex)[:300]}"})
        before = dict(M.report(cid))
        th = [threading.Thread(target=run, args=("t1", "SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH ?",
                                                  ["cs:"], lambda r: r is not None and int(r[0]) == N_SEED)),
              threading.Thread(target=run, args=("t2", "SELECT node_id FROM Graph_KG.nodes WHERE node_id = ?", ["cs:7"],
                                                  lambda r: r is not None and str(r[0]) == "cs:7"))]
        for t in th:
            t.start()
        for t in th:
            t.join(seconds + 120)
        after = M.report(cid)
        out[mode] = {"threads": {k: dict(v) for k, v in st.items()}, "errors": errs,
                     "meter": {"calls": after["calls"] - before["calls"],
                               "overlaps": after["overlaps"] - before["overlaps"],
                               "max_threads_in_flight": after["max_threads_in_flight"],
                               "examples": after["examples"][:3]}}
        M.max_inflight[cid] = 0
    c.close()
    return out


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def serve(app, seconds, load):
    import httpx
    import uvicorn
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    t0 = time.time()
    while not server.started and time.time() - t0 < 30:
        time.sleep(0.05)
    url = f"http://127.0.0.1:{port}"
    stats = collections.defaultdict(collections.Counter)
    samples = collections.defaultdict(list)
    stop = time.time() + seconds

    def client(tag, fn):
        with httpx.Client(timeout=60) as cl:
            i = 0
            while time.time() < stop:
                i += 1
                try:
                    ok, detail = fn(cl, url, i)
                    stats[tag]["n"] += 1
                    if not ok:
                        stats[tag]["bad"] += 1
                        if len(samples[tag]) < 5:
                            samples[tag].append(detail)
                except Exception as ex:  # noqa: BLE001
                    stats[tag]["exc"] += 1
                    if len(samples[tag]) < 5:
                        samples[tag].append(f"{type(ex).__name__}: {str(ex)[:200]}")
    ths = [threading.Thread(target=client, args=(tag, fn)) for tag, fn in load]
    for t in ths:
        t.start()
    for t in ths:
        t.join(seconds + 120)
    server.should_exit = True
    th.join(15)
    return {"port": port, "stats": {k: dict(v) for k, v in stats.items()}, "samples": dict(samples)}


def get_ok(path, check=None):
    def f(cl, url, i):
        r = cl.get(url + path)
        good = r.status_code == 200 and (check is None or check(r.json()))
        return good, f"{r.status_code} {r.text[:200]}"
    return f


def post_cypher(q, check=None, params=None):
    def f(cl, url, i):
        body = {"query": q}
        if params:
            body["parameters"] = params(i)
        r = cl.post(url + "/api/cypher", json=body)
        good = r.status_code == 200 and (check is None or check(r.json()))
        return good, f"{r.status_code} {r.text[:200]}"
    return f


def count_is(n):
    def chk(body):
        rows = body.get("rows") or (body.get("result") or {}).get("rows") or []
        try:
            return int(rows[0][0]) == n
        except Exception:  # noqa: BLE001
            return False
    return chk


def part_http(seconds):
    install()
    os.environ["BOLT_ENABLED"] = "0"
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"):
        os.environ.pop(k, None)
    os.environ.update(NOIRIS)
    import iris_vector_graph.cypher_api as capi
    c = L.conn()
    eng = L.engine(c)
    capi._engine_cache = eng
    cid = id(c.conn)
    ndjson = "\n".join(json.dumps({"kind": "node", "id": f"cs:l{i}", "labels": ["CSL"]}) for i in range(3)) + "\n"

    def admin_load(cl, url, i):
        r = cl.post(url + "/admin/load", content=ndjson.encode())
        return r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    load = [("health-1", get_ok("/health")), ("health-2", get_ok("/health")),
            ("cypher-read", post_cypher("MATCH (n:CS) RETURN count(n) AS c", count_is(N_SEED))),
            ("cypher-write", post_cypher("MATCH (n:CS {id: 'cs:0'}) SET n.v = $v RETURN n.v AS v",
                                         params=lambda i: {"v": i})),
            ("stats", get_ok("/stats")), ("schema", get_ok("/schema")), ("admin-load", admin_load)]
    res = serve(capi.app, seconds, load)
    res["meter"] = M.report(cid)
    res["engine_reset"] = capi._engine_cache is not eng
    res["admin_during_long_query"] = admin_during_long_query(capi)
    res["meter_after_admin_part"] = M.report(cid)
    c.close()
    return res


def admin_during_long_query(capi):
    """GET /admin/queries ("the statements running in the namespace", docs/ADMIN_API.md:327-331) while the same
    server runs a long Cypher read: the route needs _engine_lock, which the long query holds."""
    import httpx
    import uvicorn
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(capi.app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    t0 = time.time()
    while not server.started and time.time() - t0 < 30:
        time.sleep(0.05)
    url = f"http://127.0.0.1:{port}"
    out = {}
    with httpx.Client(timeout=300) as cl:
        q = None
        for k in (3, 4, 5):
            text = "MATCH " + ", ".join(f"(v{j}:CSX)" for j in range(k)) + " RETURN count(*) AS c"
            t = time.time()
            r = cl.post(url + "/api/cypher", json={"query": text})
            d = time.time() - t
            out[f"alone_k{k}"] = {"status": r.status_code, "seconds": round(d, 2), "body": r.text[:120]}
            if r.status_code == 200 and d >= 3.0:
                q = text
                break
        t = time.time()
        r = cl.get(url + "/admin/queries")
        out["admin_queries_idle"] = {"status": r.status_code, "seconds": round(time.time() - t, 3)}
        if q:
            box = {}

            def long():
                t1 = time.time()
                rr = cl2.post(url + "/api/cypher", json={"query": q})
                box["long"] = {"status": rr.status_code, "start": t1, "end": time.time()}
            with httpx.Client(timeout=300) as cl2:
                tl = threading.Thread(target=long)
                tl.start()
                time.sleep(0.7)
                ta = time.time()
                ra = cl.get(url + "/admin/queries")
                tb = time.time()
                tl.join(300)
            lq = box.get("long", {})
            body = ra.json() if ra.status_code == 200 else {}
            listed = [x for x in body.get("queries", []) if "CSX" in str(x.get("command", "")) or "rdf_labels" in str(x.get("command", ""))]
            out["admin_queries_during_long"] = {
                "status": ra.status_code, "asked_at_s": round(ta - lq.get("start", ta), 2),
                "answered_at_s": round(tb - lq.get("start", ta), 2),
                "long_query_ended_at_s": round(lq.get("end", tb) - lq.get("start", ta), 2),
                "answered_after_long_query_ended": tb >= lq.get("end", tb + 1),
                "queries_listed": len(body.get("queries", [])), "long_query_listed": bool(listed),
                "long": {k: v for k, v in lq.items() if k == "status"}}
    server.should_exit = True
    th.join(15)
    return out


def part_sample(seconds):
    install()
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"):
        os.environ.pop(k, None)
    os.environ.update(NOIRIS)   # api.main builds a module-level app at import: it must fail to connect, not reach any IRIS
    from api.main import create_app
    c = L.conn()
    eng = L.engine(c)
    app = create_app(eng)
    cid = id(c.conn)
    load = [("health-1", get_ok("/health")), ("health-2", get_ok("/health")),
            ("cypher-read", post_cypher("MATCH (n:CS) RETURN count(n) AS c", count_is(N_SEED)))]
    res = serve(app, seconds, load)
    res["meter"] = M.report(cid)
    c.close()
    return res


def main() -> int:
    out = Path(sys.argv[1])
    seconds = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 12.0
    if "--part" in sys.argv:
        part = sys.argv[sys.argv.index("--part") + 1]
        fn = {"raw": part_raw, "http": part_http, "sample": part_sample}[part]
        r = fn(seconds)
        L.dump(out / f"part-{part}.json", r)
        print(json.dumps(r, default=str)[:3000], flush=True)
        return 0
    import iris.dbapi
    import importlib.metadata as md
    res = {"driver": {"threadsafety": iris.dbapi.threadsafety, "apilevel": iris.dbapi.apilevel,
                      "intersystems-irispython": md.version("intersystems-irispython")}}
    c = L.conn()
    res["engine"] = L.version(c)
    L.reset(c)
    e = L.engine(c)
    e.bulk_create_nodes([{"id": f"cs:{i}", "labels": ["CS"]} for i in range(N_SEED)])
    e.bulk_create_nodes([{"id": f"csx:{i}", "labels": ["CSX"]} for i in range(60)])
    c.conn.commit()
    c.close()
    for part in ("raw", "http", "sample"):
        p = subprocess.run([sys.executable, __file__, str(out), "--part", part, "--seconds", str(seconds)],
                           capture_output=True, text=True, timeout=seconds * 4 + 300)
        res[part] = {"exit": p.returncode, "stderr_tail": p.stderr[-1500:]}
        f = out / f"part-{part}.json"
        if f.exists():
            res[part]["result"] = json.loads(f.read_text())
        print(part, "exit", p.returncode, flush=True)
    c = L.conn()
    L.reset(c)
    c.close()
    L.dump(out / "conn_share.json", res)
    summ = {"driver": res["driver"]}
    for part in ("raw", "http", "sample"):
        r = res[part].get("result") or {}
        if part == "raw":
            summ[part] = {m: {"meter": {k: v for k, v in r[m]["meter"].items() if k != "examples"},
                              "threads": r[m]["threads"]} for m in r} if r else res[part]
        else:
            summ[part] = {"meter": {k: v for k, v in (r.get("meter") or {}).items() if k != "examples"},
                          "stats": r.get("stats"), "exit": res[part]["exit"]}
    L.dump(out / "summary.json", summ)
    print(json.dumps(summ, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
