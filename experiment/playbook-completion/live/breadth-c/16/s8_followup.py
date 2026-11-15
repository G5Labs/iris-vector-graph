"""Follow-ups to s3/s5 on AUDITC.

    locks.sh iris timeout 600 python s8_followup.py

  F-1604 journal   the sample API's updateProtein footprint, found by its new value (an UPDATE of rdf_props.val
                   journals the row and the (key, val) index, neither of which holds the node id)
  F-1614           the demo server with IVG_API_KEY set (s5 could not import it: wrong repository root in jsrv)
  P-1607           a CSP request stream's Read() with no length, run as ObjectScript in a terminal (iris session in
                   AUDITC, temporary streams only), next to the Native API invoke s5 used
Connections: Lane, the sample API, the journal / terminal session: at most 3.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jsrv  # noqa: E402
from jcheck import Lane, run_dir  # noqa: E402

import httpx  # noqa: E402

OUT = run_dir("16")
R: dict = {"checks": {}}
KEY = "c16-secret-key"


def rec(name, **kv):
    R["checks"][name] = kv
    print(name, json.dumps(kv, default=str)[:700])


def props_of(L, nid):
    return L.c.sql("SELECT graph_id, \"key\", val FROM Graph_KG.rdf_props WHERE s = ? ORDER BY graph_id, \"key\"", nid)


def stream_terminal():
    script = (' set out="" for c="%CSP.BinaryStream","%CSP.CharacterStream","%Stream.TmpCharacter" {'
              ' set s=$classmethod(c,"%New") do s.Write($justify("",50000)) do s.Rewind()'
              ' set x=s.Read() set out=out_c_"="_$length(x)_";" }'
              ' write !,$char(30),"STREAM|",out,!\n halt\n')
    r = subprocess.run(["docker", "exec", "-i", os.environ["IVG_TEST_CONTAINER"], "iris", "session", "IRIS", "-U",
                        "AUDITC"], input=script, capture_output=True, text=True, timeout=120)
    line = [ln for ln in r.stdout.replace("\r", "").split("\n") if ln.startswith("\x1eSTREAM|")]
    rec("P1607.terminal_read_no_length", result=line[0][8:] if line else r.stdout[-500:])


def main():
    L = Lane("c16")
    p = q = None
    try:
        L.eng.create_node("c16:p1", ["Protein"], {"name": "p-default"})
        L.eng.create_node("c16:p1", ["Protein"], {"name": "p-g1"}, graph="c16g1")
        p = jsrv.start("sample-api", ["-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "18631"],
                       jsrv.iris_env(), 18631, OUT / "s8_sample_api.log", cwd=OUT)
        before = props_of(L, "c16:p1")
        m = 'mutation { updateProtein(id: "c16:p1", input: {name: "c16-p-updated"}) { id name } }'
        j = jsrv.journal_by_marker("sample API updateProtein", lambda: httpx.post(
            "http://127.0.0.1:18631/graphql", json={"query": m}, timeout=60).json(), ["c16-p-updated"], L.smap)
        after = props_of(L, "c16:p1")
        rec("F1604.updateProtein_journal", before=before, after=after, journal=j,
            reproduced=[v for g, k, v in after if g == "c16g1" and k == "name"] == ["c16-p-updated"])
        jsrv.stop(p)
        p = None

        env = {"IVG_API_KEY": KEY, "PYTHONPATH": os.environ.get("PYTHONPATH", "") + os.pathsep + str(jsrv.REPO / "src")}
        q = jsrv.start("demo-server", ["-m", "uvicorn", "iris_demo_server.app:app", "--host", "127.0.0.1",
                                       "--port", "18640"], env, 18640, OUT / "s8_demo_server.log", cwd=OUT,
                       wait_path="/api/status/none")
        u = "http://127.0.0.1:18640"
        r1 = httpx.get(u + "/api/status/none", timeout=30)
        r2 = httpx.post(u + "/api/fhir/live/add", json={"patient": "not-a-patient", "code": "x"}, timeout=30)
        rec("F1614.demo_without_key", key_configured=True, status_route=r1.status_code, live_add=r2.status_code,
            live_add_body=r2.text[:200],
            reproduced=(r1.status_code != 401 and r2.status_code != 401))
        jsrv.stop(q)
        q = None
        stream_terminal()
    finally:
        jsrv.stop(p)
        jsrv.stop(q)
        try:
            L.eng.erase_graph("c16g1")
            L.eng.delete_node("c16:p1")
        except Exception as e:
            R["cleanup_error"] = str(e)
        R["left"] = L.c.sql("SELECT graph_id, node_id FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'c16'")
        L.close()
        jsrv.dump(OUT / "s8_followup.json", R)


if __name__ == "__main__":
    main()
