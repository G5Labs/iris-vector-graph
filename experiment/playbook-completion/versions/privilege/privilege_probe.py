#!/usr/bin/env python3
"""Least-privilege live checks in AUDITB as the disposable reader IVGAUDIT_RO (role IVGAUDIT_RO_ROLE).

    python privilege_probe.py <results.json> [--revoke-as GRANTOR[,GRANTOR...]]

--revoke-as: the REVOKE is issued once per grantor with `AS "<grantor>"` (IRIS: without AS a REVOKE removes only the
current user's own grants and answers SQLCODE 100 with no error; the pin says so at _engine/legacy.py:539-540). Round
r1 ran without it, after grant.os had granted as the terminal user irisowner, so its revoke removed nothing (kept as
evidence, not a product result). Whether the right is really gone is checked independently with
$SYSTEM.SQL.Security.CheckPrivilege (as _SYSTEM, for the user and for the role) and with the reader's own SQL.

Run under tools/locks.sh iris, on the audit container (IVG_TEST_CONTAINER / IVG_PORT), after create.os and grant.os.
At most four connections at once (owner, two reader connections, the identity probe's transient one).

Discriminating checks:
- HD-0901 / F-0908: a running engine built as the reader (its native-privilege answer cached) keeps answering a native
  Cypher read after `REVOKE SELECT ON SCHEMA Graph_KG` from the reader's role, while the same server process's SQL is
  refused; a fresh engine closes its native gate and goes to SQL; and the executor class itself
  (Graph.KG.Cypher.Exec.Run) answers the revoked user over the Native API, with no SQL privilege at all.
- F-C1803: the Snapshot file helpers reached by the documented reading role (Native API, %Native_ClassExecution).
- control: the reader's writes are refused (it is a reading role).

Data: the owner (_SYSTEM) erases AUDITB's graph content and writes a -> b -> c -> d (KNOWS, label P) with the pin's
API only (IRISGraphEngine.erase_all / create_node / create_edge / sync), and erases it again at the end. The census
before is recorded. The password is read from $RUN_DIR/versions/secrets/ivgaudit_ro.pw and never printed.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import subprocess
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
import iris  # noqa: E402
import iris.dbapi  # noqa: E402

from tests import conftest as fx  # noqa: E402

NS = "AUDITB"
USER, ROLE = "IVGAUDIT_RO", "IVGAUDIT_RO_ROLE"
DIM = 4  # tools/deploy_namespace.py deployed AUDITB with embedding_dimension=4
CONTAINER = os.environ["IVG_TEST_CONTAINER"]
PORT = int(os.environ["IVG_PORT"])
ONE_HOP = "MATCH (a {node_id: 'a'})-[:KNOWS]->(b) RETURN b.node_id"
# r3: the executor's anchors (iris_src/src/Graph/KG/Cypher/Exec.cls:847-903): an id anchor with no label is a SQL
# lookup in Graph_KG.nodes (:858-866), an id anchor with a label (:868-874) and a label scan (GraphKeys, :832-845)
# read ^KG only. Asked in this order after the revoke, the ^KG-only shapes first.
LABELLED_ID = "MATCH (a:P {node_id: 'a'})-[:KNOWS]->(b) RETURN b.node_id"
LABEL_SCAN = "MATCH (a:P)-[:KNOWS]->(b) RETURN a.node_id, b.node_id"
NATIVE_QUERIES = [("label scan", LABEL_SCAN), ("labelled id anchor", LABELLED_ID), ("unlabelled id anchor", ONE_HOP)]
VARLEN = "MATCH (a {node_id: 'a'})-[:KNOWS*1..3]->(x) RETURN x.node_id ORDER BY x.node_id"
STAMP = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
SCRATCH_DIR = f"/tmp/ivgaudit-versions-{STAMP}/"

OUT: dict = {"started_utc": STAMP, "namespace": NS, "user": USER, "role": ROLE, "steps": []}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def step(name: str, **kw) -> dict:
    rec = {"step": name, "utc": now(), **kw}
    OUT["steps"].append(rec)
    print(json.dumps(rec, default=str), flush=True)
    return rec


def err(e: BaseException) -> str:
    return f"{type(e).__name__}: {str(e)[:400]}"


def connect(user: str, password: str):
    c = iris.dbapi.connect(hostname="127.0.0.1", port=PORT, namespace=NS, username=user, password=password)
    actual = fx.probe_instance_hostname(c)
    if not fx.container_hostname_matches(actual, fx.docker_container_hostname(CONTAINER),
                                         fx.docker_container_id(CONTAINER)):
        c.close()
        raise RuntimeError(f"database identity does not match {CONTAINER}")
    return c


def sql(conn, q: str):
    cur = conn.cursor()
    try:
        cur.execute(q)
        return {"ok": True, "rows": [list(r) for r in cur.fetchall()] if cur.description else cur.rowcount}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": err(e)}
    finally:
        cur.close()


def cypher(engine, q: str) -> dict:
    before = getattr(engine, "_native_answers", 0)
    try:
        r = engine.execute_cypher(q)
        rows, error = [list(x) for x in r.rows], r.error
    except Exception as e:  # noqa: BLE001
        rows, error = None, err(e)
    return {"query": q, "rows": rows, "error": error,
            "native_answers_delta": getattr(engine, "_native_answers", 0) - before}


def check_priv(nat, table: str = "Graph_KG.rdf_edges") -> dict:
    """$SYSTEM.SQL.Security.CheckPrivilege(name, 1 = table, table, "s"), asked by _SYSTEM, for the user and the role."""
    out = {}
    for name in (USER, ROLE):
        try:
            out[name] = int(nat.classMethodValue("%SYSTEM.SQL.Security", "CheckPrivilege", name, 1, table, "s"))
        except Exception as e:  # noqa: BLE001
            out[name] = err(e)
    return out


def census(conn) -> dict:
    t = sql(conn, "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'Graph_KG' ORDER BY TABLE_NAME")
    counts = {}
    for (name,) in t.get("rows") or []:
        r = sql(conn, f"SELECT COUNT(*) FROM Graph_KG.{name}")
        counts[name] = r["rows"][0][0] if r["ok"] else r["error"]
    nat = iris.createIRIS(conn)
    return {"tables": counts, "^KG_defined": int(nat.isDefined("^KG") or 0),
            "^NKG_defined": int(nat.isDefined("^NKG") or 0)}


def main() -> int:
    out_path = Path(sys.argv[1])
    revoke_as = (sys.argv[sys.argv.index("--revoke-as") + 1].split(",") if "--revoke-as" in sys.argv else [None])
    OUT["revoke_as"] = revoke_as
    skip_files = "--skip-files" in sys.argv
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    password = (Path(os.environ["RUN_DIR"]) / "versions" / "secrets" / "ivgaudit_ro.pw").read_text().strip()
    from iris_vector_graph import IRISGraphEngine
    from iris_vector_graph.cypher import native_plan

    conns = []
    try:
        sysconn = connect("_SYSTEM", "SYS")
        conns.append(sysconn)
        nat_sys = iris.createIRIS(sysconn)
        step("engine", version=str(nat_sys.classMethodValue("%SYSTEM.Version", "GetVersion")),
             driver=__import__("importlib.metadata").metadata.version("intersystems-irispython"))
        step("census-before", **census(sysconn))

        owner = IRISGraphEngine(sysconn, embedding_dimension=DIM)
        removed = owner.erase_all()
        made = [owner.create_node(n, labels=["P"], properties={"name": n.upper()}) for n in "abcd"]
        edges = [owner.create_edge(s, "KNOWS", o) for s, o in (("a", "b"), ("b", "c"), ("c", "d"))]
        synced = owner.sync()
        step("seed (owner, pin API)", erase_all_removed=removed, nodes_created=made, edges_created=edges, sync=synced,
             census=census(sysconn), owner_one_hop=cypher(owner, ONE_HOP))

        # --- the reader, granted the documented reading row
        r1conn = connect(USER, password)
        conns.append(r1conn)
        r1 = IRISGraphEngine(r1conn, embedding_dimension=DIM)
        captured = []
        current = {"q": None}
        orig = r1._run_native_plan

        def capture(plan, params):  # observe the plan the engine hands the executor (no behaviour change)
            captured.append((current["q"], plan, params))
            return orig(plan, params)

        def ask_all(engine, label):
            for name, q in NATIVE_QUERIES:
                current["q"] = name
                step(f"{label}: {name}", **cypher(engine, q))
            current["q"] = None

        r1._run_native_plan = capture
        nat_r1 = iris.createIRIS(r1conn)
        perms = {}
        for res in ("%DB_%DEFAULT", "%DB_USER", "%DB_IRISSYS", "%Native_ClassExecution", "%Native_GlobalAccess", "%All"):
            try:
                perms[res] = str(nat_r1.classMethodValue("%SYSTEM.Security", "Check", res))
            except Exception as e:  # noqa: BLE001
                perms[res] = err(e)
        try:
            nat_r1.set("x", "^IVGAuditPriv")
            gwrite = "accepted"
            nat_sys.kill("^IVGAuditPriv")
        except Exception as e:  # noqa: BLE001
            gwrite = "refused: " + err(e)
        step("reader R1 built", whoami=sql(r1conn, "SELECT $USERNAME"), resource_permissions=perms,
             native_global_write_control=gwrite, check_privilege_rdf_edges=check_priv(nat_sys),
             native_privileges=r1._native_privileges(), native_gate=native_plan.native_gate(r1),
             adjacency_indexed=r1._adjacency_indexed)
        ask_all(r1, "R1 before revoke")
        step("R1 before revoke: SQL-path var-length", **cypher(r1, VARLEN))
        step("R1 before revoke: SQL on its connection", result=sql(r1conn, "SELECT COUNT(*) FROM Graph_KG.rdf_edges"))
        try:
            w = r1.create_node("ivgaudit_x", labels=["P"])
            step("control: R1 write (create_node)", answered=w)
        except Exception as e:  # noqa: BLE001
            step("control: R1 write (create_node)", refused=err(e))
        step("control: R1 SQL INSERT", result=sql(r1conn, "INSERT INTO Graph_KG.nodes (node_id) VALUES ('ivgaudit_y')"))

        # --- F-C1803: the Snapshot file helpers as the reading role (Native API)
        if skip_files:
            step("F-C1803 skipped", why="--skip-files (shown in r1 and r2)")

        def snap(method, *args):
            try:
                return {"ok": True, "value": nat_r1.classMethodValue("Graph.KG.Snapshot", method, *args)}
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "error": err(e)}

        def snap_void(method, *args):
            try:
                nat_r1.classMethodVoid("Graph.KG.Snapshot", method, *args)
                return {"ok": True}
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "error": err(e)}

        f = SCRATCH_DIR + "written-by-reader.txt"
        step("F-C1803 as reader", skipped=skip_files) if skip_files else step("F-C1803 as reader", scratch_dir=SCRATCH_DIR,
             file_exists_etc_hostname=snap("FileExists", "/etc/hostname"),
             get_file_size_etc_hostname=snap("GetFileSize", "/etc/hostname"),
             read_file_chunk_etc_hostname=snap("ReadFileChunk", "/etc/hostname", 0, 200),
             read_file_chunk_iris_cpf_head=snap("ReadFileChunk", "/usr/irissys/iris.cpf", 0, 120),
             export_globals_KG=snap("ExportGlobals", SCRATCH_DIR, json.dumps([{"name": "^KG"}])),
             write_file_chunk=snap_void("WriteFileChunk", f, "written by IVGAUDIT_RO through Graph.KG.Snapshot", 0),
             read_back=snap("ReadFileChunk", f, 0, 200))
        if not skip_files:
            ls = subprocess.run(["docker", "exec", CONTAINER, "ls", "-ln", SCRATCH_DIR], capture_output=True, text=True)
            step("F-C1803 server files (docker exec ls -ln, outside IRIS)", stdout=ls.stdout, stderr=ls.stderr.strip())
            step("F-C1803 DeleteDir as reader", delete_dir=snap("DeleteDir", SCRATCH_DIR),
                 exists_after=snap("FileExists", SCRATCH_DIR))
            ls = subprocess.run(["docker", "exec", CONTAINER, "ls", "-ln", SCRATCH_DIR], capture_output=True, text=True)
            step("F-C1803 after DeleteDir (docker exec ls)", rc=ls.returncode, stderr=ls.stderr.strip())

        # --- HD-0901 / F-0908: revoke the SQL right while R1 runs
        revokes = []
        for g in revoke_as:
            q = f"REVOKE SELECT ON SCHEMA Graph_KG FROM {ROLE}" + (f' AS "{g}"' if g else "")
            revokes.append({"statement": q, **sql(sysconn, q)})
        sysconn.commit()
        step("REVOKE SELECT ON SCHEMA Graph_KG FROM IVGAUDIT_RO_ROLE (owner)", revokes=revokes,
             check_privilege_rdf_edges=check_priv(nat_sys))
        step("R1 after revoke: cached answer", native_privileges_cached=r1._native_privileges_cached,
             native_gate=native_plan.native_gate(r1))
        ask_all(r1, "R1 after revoke")
        step("R1 after revoke: SQL-path var-length", **cypher(r1, VARLEN))
        step("R1 after revoke: SQL on its connection", result=sql(r1conn, "SELECT COUNT(*) FROM Graph_KG.rdf_edges"))

        r2conn = connect(USER, password)
        conns.append(r2conn)
        r2 = IRISGraphEngine(r2conn, embedding_dimension=DIM)
        step("fresh engine R2 after revoke", native_privileges=r2._native_privileges(),
             native_gate=native_plan.native_gate(r2))
        ask_all(r2, "R2 (fresh engine) after revoke")
        step("R2: SQL on its connection", result=sql(r2conn, "SELECT COUNT(*) FROM Graph_KG.rdf_edges"))

        nat_r2 = iris.createIRIS(r2conn)
        seen = set()
        for qname, plan, params in captured:
            if qname in seen:
                continue
            seen.add(qname)
            try:
                head = json.loads(str(nat_r2.classMethodValue("Graph.KG.Cypher.Exec", "Run", json.dumps(plan),
                                                              json.dumps(params, default=str))))
                step(f"Exec.Run called directly by the revoked user (R2's connection): {qname}", plan=plan, head=head)
            except Exception as e:  # noqa: BLE001
                step(f"Exec.Run called directly by the revoked user (R2's connection): {qname}", plan=plan,
                     error=err(e))
        if not captured:
            step("Exec.Run direct call skipped", why="no native plan was captured from R1")
        subs, s = [], ""
        try:
            while len(subs) < 20:
                s = nat_r2.nextSubscript(False, "^KG", s)
                if s is None or s == "":
                    break
                subs.append(str(s))
            step("revoked user reads ^KG over the Native API", isDefined=int(nat_r2.isDefined("^KG") or 0),
                 first_level_subscripts=subs)
        except Exception as e:  # noqa: BLE001
            step("revoked user reads ^KG over the Native API", error=err(e))

        # --- restore the role to the documented reading row
        cur = sysconn.cursor()
        cur.execute(f"GRANT SELECT ON SCHEMA Graph_KG TO {ROLE}")
        cur.close()
        sysconn.commit()
        step("GRANT SELECT ON SCHEMA Graph_KG TO IVGAUDIT_RO_ROLE (restored)",
             check_privilege_rdf_edges=check_priv(nat_sys),
             r2_sql_after_regrant=sql(r2conn, "SELECT COUNT(*) FROM Graph_KG.rdf_edges"),
             r2_cached_native_privileges=r2._native_privileges_cached,
             r2_one_hop_after_regrant=cypher(r2, ONE_HOP))

        removed = owner.erase_all()
        step("reset (owner, pin API erase_all)", removed=removed, census=census(sysconn))
    except Exception as e:  # noqa: BLE001
        step("aborted", error=err(e), trace=traceback.format_exc()[-2000:])
        out_path.write_text(json.dumps(OUT, indent=1, default=str))
        return 1
    finally:
        for c in reversed(conns):
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
    OUT["finished_utc"] = now()
    out_path.write_text(json.dumps(OUT, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
