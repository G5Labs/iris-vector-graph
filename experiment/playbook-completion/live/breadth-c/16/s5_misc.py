"""Module 16 checks that need no Graph_KG writes.

    locks.sh iris timeout 600 python s5_misc.py

  F-1615  the fraud server's embedding lookup statement, run as written in AUDITC (and schema-qualified)
  P-1607  what %Stream Read() with no length returns for a body over 32,000 characters (Native API, temp streams only)
  F-1614  the demo server (src/iris_demo_server) with IVG_API_KEY set: are its routes reached without the key?
Connections: one Conn (Native API on the same process); the demo server opens none for the routes used.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jsrv  # noqa: E402
from jcheck import Conn, run_dir  # noqa: E402

import httpx  # noqa: E402

OUT = run_dir("16")
R: dict = {"checks": {}}
DEMO_PORT = 18640
KEY = "c16-secret-key"


def rec(name, **kv):
    R["checks"][name] = kv
    print(name, json.dumps(kv, default=str)[:600])


def main():
    c = Conn("AUDITC")
    try:
        for label, q in (("as_written", "SELECT embedding FROM kg_NodeEmbeddings WHERE node_id = ?"),
                         ("schema_qualified", "SELECT embedding FROM Graph_KG.kg_NodeEmbeddings WHERE node_id = ?"),
                         ("intended", "SELECT TOP 1 emb FROM Graph_KG.kg_NodeEmbeddings WHERE node_id = ? "
                                      "AND COALESCE(graph_id, '') = ''")):
            try:
                rec(f"F1615.{label}", ok=True, rows=c.sql(q, "c16:none"))
            except Exception as e:
                rec(f"F1615.{label}", ok=False, error=str(e)[:400])

        for cls in ("%Stream.TmpCharacter", "%CSP.CharacterStream", "%CSP.BinaryStream"):
            try:
                s = c.o.classMethodObject(cls, "%New")
                s.invoke("Write", "x" * 50000)
                s.invoke("Rewind")
                first = s.invoke("Read")
                size = s.invoke("SizeGet") if hasattr(s, "invoke") else None
                rec(f"P1607.{cls}", written=50000, size=size, first_read_len=len(first or ""),
                    holds=len(first or "") < 50000)
            except Exception as e:
                rec(f"P1607.{cls}", error=str(e)[:300])
        R["superclasses"] = c.sql("SELECT Name, Super FROM %Dictionary.CompiledClass WHERE Name IN "
                                  "('%CSP.CharacterStream','%CSP.BinaryStream','%CSP.Request')")
    finally:
        c.close()

    env = {"IVG_API_KEY": KEY, "PYTHONPATH": os.environ.get("PYTHONPATH", "") + os.pathsep +
           str(jsrv.REPO / "src")}
    p = None
    try:
        p = jsrv.start("demo-server", ["-m", "uvicorn", "iris_demo_server.app:app", "--host", "127.0.0.1",
                                       "--port", str(DEMO_PORT)], env, DEMO_PORT, OUT / "s5_demo_server.log", cwd=OUT,
                       wait_path="/api/status/none")
        u = f"http://127.0.0.1:{DEMO_PORT}"
        r1 = httpx.get(u + "/api/status/none", timeout=30)
        r2 = httpx.post(u + "/api/fhir/live/add", json={"patient": "not-a-patient", "code": "x"}, timeout=30)
        r3 = httpx.post(u + "/api/fhir/live/add", json={"patient": "not-a-patient", "code": "x"},
                        headers={"X-Api-Key": KEY}, timeout=30)
        rec("F1614.demo_without_key", status_status_route=r1.status_code, status_live_add=r2.status_code,
            body_live_add=r2.text[:200], status_live_add_with_key=r3.status_code,
            reproduced=(r1.status_code != 401 and r2.status_code != 401))
    except Exception as e:
        rec("F1614.error", error=f"{type(e).__name__}: {e}"[:500])
    finally:
        jsrv.stop(p)
        jsrv.dump(OUT / "s5_misc.json", R)


if __name__ == "__main__":
    main()
