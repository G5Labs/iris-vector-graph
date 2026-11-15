"""Does a finished Bolt session give back its IRIS connection? (connection/licence accounting, P-1609)

    flock -s $RUN_DIR/breadth-c/auditc.lock timeout 600 python s2_bolt_sessions.py

Starts the Cypher HTTP server (Bolt TCP on 127.0.0.1:18613), opens 3 Bolt sessions one after another (each runs one
read and is closed by the driver, which sends GOODBYE), and after each lists the AUDITC processes that appeared
since the server started (%SYS.ProcessQuery), plus the licence units in use. A session that returns its connection
leaves no new process behind; each leaked one adds one. Waits 20 s at the end for a cyclic GC to run. Also captures
the full Bolt FAILURE a session gets when IRIS refuses its connection, if that happens.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jsrv  # noqa: E402
from jcheck import run_dir  # noqa: E402

import iris  # noqa: E402

OUT = run_dir("16")
HTTP, BOLT = 18612, 18613


def procs(o, cur):
    cur.execute("SELECT Pid FROM %SYS.ProcessQuery WHERE NameSpace = 'AUDITC'")
    return {int(r[0]) for r in cur.fetchall()}


def main():
    from neo4j import GraphDatabase
    n = iris.connect(hostname="127.0.0.1", port=int(os.environ["IVG_PORT"]), namespace="AUDITC",
                     username="_SYSTEM", password="SYS")
    o = iris.createIRIS(n)
    cur = n.cursor()
    out = {"steps": []}
    base = procs(o, cur)
    env = jsrv.iris_env()
    env.update({"BOLT_TCP_HOST": "127.0.0.1", "BOLT_TCP_PORT": str(BOLT)})
    p = jsrv.start("bolt-sessions", ["-m", "uvicorn", "iris_vector_graph.cypher_api:app", "--host", "127.0.0.1",
                                     "--port", str(HTTP)], env, HTTP, OUT / "s2_server.log", wait_path="/openapi")
    try:
        def step(label, err=None):
            now = procs(o, cur)
            out["steps"].append({"label": label, "new_auditc_processes": sorted(now - base),
                                 "lu_consumed": o.classMethodValue("%SYSTEM.License", "LUConsumed"),
                                 "lu_available": o.classMethodValue("%SYSTEM.License", "LUAvailable"),
                                 "error": err})
            print(out["steps"][-1])
        step("server started (no request yet)")
        for i in range(3):
            err = None
            drv = GraphDatabase.driver(f"bolt://127.0.0.1:{BOLT}", auth=("neo4j", "x"))
            try:
                with drv.session() as s:
                    s.run("RETURN 1 AS one").consume()
            except Exception as e:
                err = {"type": type(e).__name__, "code": getattr(e, "code", None), "message": str(e)[:1500]}
            finally:
                drv.close()
            time.sleep(1)
            step(f"after Bolt session {i + 1} closed", err)
        time.sleep(20)
        step("20 s later")
    finally:
        jsrv.stop(p)
        time.sleep(2)
        out["after_server_stopped_new_processes"] = sorted(procs(o, cur) - base)
        n.close()
        jsrv.dump(OUT / "s2_bolt_sessions.json", out)
        print(out["after_server_stopped_new_processes"])


if __name__ == "__main__":
    main()
