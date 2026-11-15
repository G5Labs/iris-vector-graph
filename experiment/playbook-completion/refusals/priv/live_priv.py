#!/usr/bin/env python3
"""Least-privilege refusals, live in AUDITE as the operator-authorised user IVGAUDIT_RO (versions/PRIVILEGE.md).

    bash experiment/playbook-completion/refusals/priv/run_priv.sh      # wrapper: password by env var name, IRIS lock

Statements: INS-X10.7, ALG-B9.3, INS-X1.5, SNP-X1.3, OPS-X4.84, VEC-X1.16. One lock hold. Sequence:
  as _SYSTEM: reset AUDITE (EraseAll/PurgeAll), oracle control, seed scratch data (rxp*);
  %SYS: record the principal (user, role resources, SQL privileges); enable the user;
  per scenario: GRANT exactly what it needs as SQL in AUDITE (grantor _SYSTEM), confirm with CheckPrivilege, run the
  refused calls through the product as IVGAUDIT_RO inside journal windows (rxlib: AUDITE's database, all processes),
  then REVOKE ... AS "_SYSTEM" and confirm CheckPrivilege 0; role resource changes (OPS-X4.84: without
  %DB_%DEFAULT; VEC-X1.16: %DB_%DEFAULT:RW) are made in %SYS and restored to the recorded value at once;
  finally (always, in `finally`): revoke everything granted, restore the role, disable the user, check the login is
  refused, list privileges and CheckPrivilege for every AUDITE Graph_KG table -> final-state.json; reset AUDITE.
The password arrives only as the environment variable IVGAUDIT_PW and is never printed or logged; every log line is
scanned for it before it is written (a hit aborts the write).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from rxlib import Lane, raises, returns, run_dir, NS  # noqa: E402

import iris  # noqa: E402
import iris.dbapi  # noqa: E402
from tests import conftest as fx  # noqa: E402

USER, ROLE = "IVGAUDIT_RO", "IVGAUDIT_RO_ROLE"
CONTAINER = os.environ["IVG_TEST_CONTAINER"]
PW = os.environ.get("IVGAUDIT_PW", "")
OUT = run_dir("priv")
TAG = os.environ.get("RX_PRIV_TAG", "r1")
EVENTS: list = []
GRANTED: list = []          # (privilege, object) currently granted by this run, for the finally block
ROLE_ORIG = {"resources": None}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def clean(obj):
    s = json.dumps(obj, default=str)
    if PW and PW in s:
        raise RuntimeError("refusing to record text that contains the password")
    return obj


def event(name, **kw):
    rec = clean({"utc": now(), "event": name, **kw})
    EVENTS.append(rec)
    print(json.dumps(rec, default=str)[:400], flush=True)
    return rec


def sys_session(script: str) -> str:
    """Run ObjectScript lines in %SYS through `iris session` (no password involved)."""
    r = subprocess.run(["docker", "exec", "-i", CONTAINER, "iris", "session", "IRIS", "-U", "%SYS"],
                       input=script + "\n halt\n", capture_output=True, text=True, timeout=300)
    return "\n".join(l for l in r.stdout.replace("\r", "").split("\n") if "<<" in l or l.startswith("PRIV "))


PRINCIPAL = r'''
 kill u do ##class(Security.Users).Get("IVGAUDIT_RO",.u) write "<<USER:roles=",$get(u("Roles"))," ns=",$get(u("NameSpace"))," enabled=",$get(u("Enabled")),":USER>>",!
 kill r do ##class(Security.Roles).Get("IVGAUDIT_RO_ROLE",.r) write "<<ROLE:",$get(r("Resources")),":ROLE>>",!
 set rs=##class(%SQL.Statement).%ExecDirect(,"SELECT Namespace, Grantee, Grantor, Privilege, SQLObject FROM Security.SQLPrivileges WHERE Grantee IN ('IVGAUDIT_RO','IVGAUDIT_RO_ROLE')")
 set k=0 while rs.%Next() { set k=k+1 write "PRIV ns=",rs.Namespace," grantee=",rs.Grantee," grantor=",rs.Grantor," priv=",rs.Privilege," obj=",rs.SQLObject,! }
 write "<<PRIVCOUNT:",k,":PRIVCOUNT>>",!'''


def principal() -> dict:
    out = sys_session(PRINCIPAL)
    d = {"raw": out.split("\n")}
    for tag in ("USER", "ROLE", "PRIVCOUNT"):
        if f"<<{tag}:" in out:
            d[tag.lower()] = out.split(f"<<{tag}:")[1].split(f":{tag}>>")[0]
    d["auditE_grants"] = [l for l in out.split("\n") if l.startswith("PRIV ns=AUDITE")]
    return d


def set_enabled(flag: int) -> str:
    return sys_session(f''' kill u set sc=##class(Security.Users).Get("{USER}",.u) set u("Enabled")={flag} set sc=##class(Security.Users).Modify("{USER}",.u)
 write "<<SET:",$system.Status.GetErrorText(sc),":SET>>",!
 kill u do ##class(Security.Users).Get("{USER}",.u) write "<<ENABLED:",$get(u("Enabled")),":ENABLED>>",!''')


def set_role_resources(res: str) -> str:
    assert all(c not in res for c in '"\n'), res
    return sys_session(f''' kill r set sc=##class(Security.Roles).Get("{ROLE}",.r) set r("Resources")="{res}" set sc=##class(Security.Roles).Modify("{ROLE}",.r)
 write "<<SET:",$system.Status.GetErrorText(sc),":SET>>",!
 kill r do ##class(Security.Roles).Get("{ROLE}",.r) write "<<ROLE:",$get(r("Resources")),":ROLE>>",!''')


def sql(conn, q, *params):
    cur = conn.cursor()
    try:
        cur.execute(q, params) if params else cur.execute(q)
        return {"ok": True, "rows": [list(r) for r in cur.fetchall()] if cur.description else cur.rowcount}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:400]}"}
    finally:
        cur.close()


def grant(L, priv: str, obj: str):
    r = sql(L.c.conn, f"GRANT {priv} ON {obj} TO {ROLE}")
    GRANTED.append((priv, obj))
    event("grant", statement=f"GRANT {priv} ON {obj} TO {ROLE}", result=r)


def revoke(L, priv: str, obj: str):
    r = sql(L.c.conn, f'REVOKE {priv} ON {obj} FROM {ROLE} AS "_SYSTEM"')
    if not r["ok"]:  # the grantor is this connection's user (_SYSTEM): a plain REVOKE removes its grants
        r = {"as_form": r, "plain": sql(L.c.conn, f"REVOKE {priv} ON {obj} FROM {ROLE}")}
    if (priv, obj) in GRANTED:
        GRANTED.remove((priv, obj))
    event("revoke", statement=f'REVOKE {priv} ON {obj} FROM {ROLE} AS "_SYSTEM"', result=r)


def tables(L):
    return [r[0] for r in L.c.sql("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'Graph_KG' "
                                  "AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")]


def checkpriv(L, names, action="s"):
    out = {}
    for t in names:
        for who in (USER, ROLE):
            try:
                out[f"{who}:{t}:{action}"] = int(L.c.call("%SYSTEM.SQL.Security", "CheckPrivilege", who, 1,
                                                          f"Graph_KG.{t}", action))
            except Exception as e:  # noqa: BLE001
                out[f"{who}:{t}:{action}"] = f"{type(e).__name__}: {str(e)[:120]}"
    return out


def reader():
    """An identity-checked connection to AUDITE as IVGAUDIT_RO (one IRIS process)."""
    c = iris.dbapi.connect(hostname="127.0.0.1", port=int(os.environ["IVG_PORT"]), namespace=NS, username=USER,
                           password=PW)
    actual = fx.probe_instance_hostname(c)
    if not fx.container_hostname_matches(actual, fx.docker_container_hostname(CONTAINER),
                                         fx.docker_container_id(CONTAINER)):
        c.close()
        raise RuntimeError("database identity does not match the audit container")
    return c


def reader_engine(c):
    from iris_vector_graph.engine import IRISGraphEngine
    return IRISGraphEngine(c, namespace=NS, embedding_dimension=4)


def whoami(c):
    return sql(c, "SELECT $USERNAME")


def count(L, table, where="1=1", *params):
    return int(L.c.sql(f"SELECT COUNT(*) FROM Graph_KG.{table} WHERE {where}", *params)[0][0])


# ------------------------------------------------------------------------------------------------ scenarios
FUNCS = {
    "CY_VLP_ENDS": ("SELECT Graph_KG.CY_VLP_ENDS('rxp:a', '[\"knows\"]', 'out', 1, 2, 1, '', 'Graph_KG.rdf_edges')", "rdf_edges"),
    "kg_PPR": ("SELECT Graph_KG.kg_PPR('[\"rxp:a\"]', 0.85, 100, 0, 1.0, '')", "rdf_edges"),
    "kg_DegreeCentrality": ("SELECT Graph_KG.kg_DegreeCentrality('out', '', 10000, '')", "rdf_edges"),
    "kg_SCC": ("SELECT Graph_KG.kg_SCC(10000)", "rdf_edges"),
    "MatchEdges": ("SELECT Graph_KG.MatchEdges('rxp:a', 'knows', 0, 0)", "rdf_edges"),
    "MatchEdgesAllGraphs": ("SELECT Graph_KG.MatchEdgesAllGraphs('rxp:a', 'knows', 0)", "rdf_edges"),
    "DijkstraPath": ("SELECT Graph_KG.DijkstraPath('rxp:a', 'rxp:c', '', 99, 5, 'out', '', '')", "rdf_edges"),
    "kg_BM25": ("SELECT Graph_KG.kg_BM25('rxpbm25', 'lovelace', 5)", "rdf_props"),
}


def s_ins_x10_7(L):
    """INS-X10.7: EXECUTE on the schema, no SELECT: each global-reading SQL function is refused naming the table."""
    grant(L, "EXECUTE", "SCHEMA Graph_KG")
    event("checkprivilege", **checkpriv(L, ["rdf_edges", "rdf_props"]))
    c = reader()
    try:
        event("reader login", whoami=whoami(c))
        for fn, (q, table) in FUNCS.items():
            L.refusal("INS-X10.7", f"as IVGAUDIT_RO (EXECUTE only): {fn} -> -99 naming Graph_KG.{table}",
                      lambda q=q: sql_raise(c, q),
                      raises("Exception", match=rf"SQLCODE.?=?.?-99.*User {USER} lacks SELECT on Graph_KG\.{table}"),
                      entry=f"SQL Graph_KG.{fn} as IVGAUDIT_RO")
    finally:
        c.close()
    revoke(L, "EXECUTE", "SCHEMA Graph_KG")


def sql_raise(c, q):
    cur = c.cursor()
    try:
        cur.execute(q)
        return [list(r) for r in cur.fetchall()]
    finally:
        cur.close()


def s_alg_b9_3_ins_x1_5(L):
    """ALG-B9.3 (walk work area refused at database R) and INS-X1.5 (setup without create rights), the documented
    reading row: SELECT and EXECUTE on the schema, the database at R."""
    grant(L, "SELECT", "SCHEMA Graph_KG")
    grant(L, "EXECUTE", "SCHEMA Graph_KG")
    event("checkprivilege", **checkpriv(L, ["nodes", "rdf_edges"]))
    c = reader()
    try:
        e = reader_engine(c)
        event("reader engine", whoami=whoami(c))
        L.refusal("ALG-B9.3", "as IVGAUDIT_RO (database R): kg_GRAPH_WALK -> refused naming ^ArnoKG(\"bfs_r\") and RW",
                  lambda: e.kg_GRAPH_WALK("rxp:a", max_depth=2),
                  raises("RuntimeError", match=r'\^ArnoKG\("bfs_r"\).*RW'),
                  entry="engine.kg_GRAPH_WALK as IVGAUDIT_RO")
        L.refusal("INS-X1.5", "as IVGAUDIT_RO (no %CREATE_* rights): initialize_schema -> IVGSchemaError naming user, "
                              "schema and the right",
                  lambda: e.initialize_schema(),
                  raises("IVGSchemaError", match=rf"(?=.*schema Graph_KG)(?=.*user {USER} does not hold the SQL "
                                                 r"privilege %CREATE_[A-Z_]+)"),
                  entry="engine.initialize_schema as IVGAUDIT_RO")
    finally:
        c.close()
    revoke(L, "SELECT", "SCHEMA Graph_KG")
    revoke(L, "EXECUTE", "SCHEMA Graph_KG")


def s_snp_x1_3(L):
    """SNP-X1.3: SELECT on every Graph_KG table but rdf_props: save_snapshot raises naming it, no file written."""
    all_t = tables(L)
    for t in all_t:
        if t != "rdf_props":
            grant(L, "SELECT", f"Graph_KG.{t}")
    grant(L, "EXECUTE", "SCHEMA Graph_KG")
    event("checkprivilege", **checkpriv(L, ["nodes", "rdf_props"]))
    c = reader()
    try:
        e = reader_engine(c)
        with tempfile.TemporaryDirectory(dir=str(OUT)) as td:
            path = Path(td) / "rxp-snapshot.zip"
            L.refusal("SNP-X1.3", "as IVGAUDIT_RO without SELECT on Graph_KG.rdf_props: save_snapshot -> "
                                  "SnapshotReadError naming it, no file",
                      lambda: e.save_snapshot(str(path)),
                      raises("SnapshotReadError", match=r"rdf_props"),
                      after=lambda: {"file_written": path.exists(), "dir_listing": sorted(os.listdir(td))},
                      entry="engine.save_snapshot as IVGAUDIT_RO")
            if path.exists() or os.listdir(td):
                L.cases[-1]["outcome"] = "refused-but-changed"
                L.cases[-1]["unchanged"] = False
    finally:
        c.close()
    for t in all_t:
        if t != "rdf_props":
            revoke(L, "SELECT", f"Graph_KG.{t}")
    revoke(L, "EXECUTE", "SCHEMA Graph_KG")


def s_ops_x4_84(L):
    """OPS-X4.84: a login refused read of the class list (no R on the database holding AUDITE's routines)."""
    grant(L, "SELECT", "SCHEMA Graph_KG")
    grant(L, "EXECUTE", "SCHEMA Graph_KG")
    orig = ROLE_ORIG["resources"]
    without_db = ",".join(p for p in orig.split(",") if not p.startswith("%DB_%DEFAULT:"))
    event("role resources (no database resource)", result=set_role_resources(without_db))
    try:
        try:
            c = reader()
        except Exception as exc:  # noqa: BLE001
            event("OPS-X4.84 login without the database resource", refused=f"{type(exc).__name__}: {str(exc)[:300]}")
            L.note("OPS-X4.84", "login to AUDITE without R on its database (which holds globals and routines)",
                   refused=f"{type(exc).__name__}: {str(exc)[:300]}")
            c = None
        if c is not None:
            try:
                def build_and_detect():
                    e = reader_engine(c)
                    return {"capabilities": repr(e._detect_capabilities())[:300]}
                L.refusal("OPS-X4.84", "as IVGAUDIT_RO without R on the routines database: capability detection -> "
                                       "ClassesUnreadable (not 'no classes')",
                          build_and_detect, raises("ClassesUnreadable"), entry="IRISGraphEngine + _detect_capabilities")
                def khop():
                    e = reader_engine(c)
                    return e.khop("rxp:a", 2) if hasattr(e, "khop") else "no khop"
                L.refusal("OPS-X4.84", "as IVGAUDIT_RO without R on the routines database: khop -> raises, not []",
                          khop, raises("ClassesUnreadable", "Exception"), entry="engine.khop")
            finally:
                c.close()
    finally:
        event("role resources restored", result=set_role_resources(orig))
    revoke(L, "SELECT", "SCHEMA Graph_KG")
    revoke(L, "EXECUTE", "SCHEMA Graph_KG")


def s_vec_x1_16(L):
    """VEC-X1.16: a writer that may not read the embedding registry (registry present): the write should be refused."""
    all_t = tables(L)
    for t in all_t:
        if t != "embedding_registry":
            grant(L, "SELECT", f"Graph_KG.{t}")
    grant(L, "INSERT,UPDATE,DELETE", "Graph_KG.kg_NodeEmbeddings")
    grant(L, "EXECUTE", "SCHEMA Graph_KG")
    event("checkprivilege", **checkpriv(L, ["embedding_registry", "kg_NodeEmbeddings", "nodes"]),
          **checkpriv(L, ["kg_NodeEmbeddings"], "i"))
    orig = ROLE_ORIG["resources"]
    rw = ",".join(("%DB_%DEFAULT:RW" if p.startswith("%DB_%DEFAULT:") else p) for p in orig.split(","))
    event("role resources (database RW for the write)", result=set_role_resources(rw))
    try:
        c = reader()
        try:
            e = reader_engine(c)
            before = count(L, "kg_NodeEmbeddings", "node_id = ?", "rxp:v2")
            L.refusal("VEC-X1.16", "as IVGAUDIT_RO (no SELECT on the registry, which holds kg_NodeEmbeddings' identity): "
                                   "store_embedding with another model -> refused (stated)",
                      lambda: e.store_embedding("rxp:v2", [0.1, 0.2, 0.3, 0.4], model_key="rxp-other-model"),
                      raises("EmbeddingIdentityConflict", "Exception"),
                      after=lambda: {"rows_before": before,
                                     "rows_after": count(L, "kg_NodeEmbeddings", "node_id = ?", "rxp:v2")},
                      entry="engine.store_embedding as IVGAUDIT_RO")
            L.refusal("VEC-X1.16", "as IVGAUDIT_RO: store_embedding, same model -> refused (stated)",
                      lambda: e.store_embedding("rxp:v3", [0.1, 0.2, 0.3, 0.5]),
                      raises("Exception"),
                      after=lambda: {"rows_after": count(L, "kg_NodeEmbeddings", "node_id = ?", "rxp:v3")},
                      entry="engine.store_embedding as IVGAUDIT_RO")
        finally:
            c.close()
    finally:
        event("role resources restored", result=set_role_resources(orig))
    for t in all_t:
        if t != "embedding_registry":
            revoke(L, "SELECT", f"Graph_KG.{t}")
    revoke(L, "INSERT,UPDATE,DELETE", "Graph_KG.kg_NodeEmbeddings")
    revoke(L, "EXECUTE", "SCHEMA Graph_KG")


def frames_of(fn, holder: dict):
    """Run fn; on an exception record the product frames it passed (file:line function), then re-raise."""
    import traceback as _tb

    def run():
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            holder["frames"] = [f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in _tb.extract_tb(exc.__traceback__)
                                if "iris_vector_graph" in f.filename][-8:]
            raise
    return run


def s_vec_x1_16_r2(L):
    """VEC-X1.16, round r2: which code refuses, and whether a write is refused when the route is already cached.
    (a) routed model rxp-m1 (registry row made as _SYSTEM), fresh engine, no SELECT on the registry;
    (b) the default pair (no model), fresh engine, no SELECT on the registry;
    (c) SELECT on the registry granted, one write of rxp-m1 (caches the route for 30 s), SELECT on the registry revoked
        (CheckPrivilege 0), a second write of rxp-m1 on the same engine."""
    reg = L.c.sql("SELECT table_name FROM Graph_KG.embedding_registry WHERE model_key = 'rxp-m1'")
    routed = str(reg[0][0])
    all_t = tables(L)
    for t in all_t:
        if t != "embedding_registry":
            grant(L, "SELECT", f"Graph_KG.{t}")
    for t in ("kg_NodeEmbeddings", routed):
        grant(L, "INSERT,UPDATE,DELETE", f"Graph_KG.{t}")
    grant(L, "EXECUTE", "SCHEMA Graph_KG")
    event("checkprivilege", **checkpriv(L, ["embedding_registry", routed]), **checkpriv(L, [routed], "i"))
    orig = ROLE_ORIG["resources"]
    rw = ",".join(("%DB_%DEFAULT:RW" if p.startswith("%DB_%DEFAULT:") else p) for p in orig.split(","))
    event("role resources (database RW for the write)", result=set_role_resources(rw))
    try:
        c = reader()
        try:
            e = reader_engine(c)
            h = {}
            L.refusal("VEC-X1.16", "r2 (a) fresh engine, routed model rxp-m1, no SELECT on the registry -> refused",
                      frames_of(lambda: e.store_embedding("rxp:v2", [0.1, 0.2, 0.3, 0.4], model_key="rxp-m1"), h),
                      raises("Exception", match=r"-99"),
                      after=lambda: {"frames": h.get("frames"),
                                     "rows_v2": count(L, routed, "node_id = ?", "rxp:v2")},
                      entry="engine.store_embedding as IVGAUDIT_RO")
            h2 = {}
            L.refusal("VEC-X1.16", "r2 (b) fresh engine, default pair, no SELECT on the registry -> refused",
                      frames_of(lambda: e.store_embedding("rxp:v3", [0.1, 0.2, 0.3, 0.5]), h2),
                      raises("Exception", match=r"-99"),
                      after=lambda: {"frames": h2.get("frames"),
                                     "rows_v3": count(L, "kg_NodeEmbeddings", "node_id = ?", "rxp:v3")},
                      entry="engine.store_embedding as IVGAUDIT_RO")
            # (c) the route cached while the registry was readable
            grant(L, "SELECT", "Graph_KG.embedding_registry")
            event("checkprivilege", **checkpriv(L, ["embedding_registry"]))
            e2 = reader_engine(c)
            first = e2.store_embedding("rxp:v4", [0.1, 0.2, 0.3, 0.6], model_key="rxp-m1")
            c.commit()
            event("(c) first write with the registry readable", result=first,
                  cached_routes=len(getattr(e2, "_route_cache_store", {}) or {}))
            revoke(L, "SELECT", "Graph_KG.embedding_registry")
            event("checkprivilege after revoke", **checkpriv(L, ["embedding_registry"]),
                  reader_sql=sql(c, "SELECT COUNT(*) FROM Graph_KG.embedding_registry"))
            h3 = {}
            L.refusal("VEC-X1.16", "r2 (c) route cached, then SELECT on the registry revoked: second write -> refused "
                                   "(stated)",
                      frames_of(lambda: (e2.store_embedding("rxp:v5", [0.1, 0.2, 0.3, 0.7], model_key="rxp-m1"),
                                         c.commit())[0], h3),
                      raises("Exception"),
                      after=lambda: {"frames": h3.get("frames"),
                                     "rows_v5": count(L, routed, "node_id = ?", "rxp:v5"),
                                     "reader_registry_read": sql(c, "SELECT COUNT(*) FROM Graph_KG.embedding_registry")},
                      entry="engine.store_embedding as IVGAUDIT_RO (route cached)")
        finally:
            c.close()
    finally:
        event("role resources restored", result=set_role_resources(orig))
    for priv, obj in list(GRANTED):
        revoke(L, priv, obj)


def seed(L):
    e = L.eng
    for nid, name in (("rxp:a", "Ada Lovelace"), ("rxp:b", "Bes"), ("rxp:c", "Cyd"), ("rxp:v1", "v1"),
                      ("rxp:v2", "v2"), ("rxp:v3", "v3"), ("rxp:v4", "v4"), ("rxp:v5", "v5")):
        e.create_node(nid, labels=["RXP"], properties={"name": name})
    e.create_edge("rxp:a", "knows", "rxp:b")
    e.create_edge("rxp:b", "knows", "rxp:c")
    e.sync()
    e.bm25_build("rxpbm25", ["name"])
    e.store_embedding("rxp:v1", [0.1, 0.2, 0.3, 0.4])          # the default pair (kg_NodeEmbeddings)
    e.store_embedding("rxp:v1", [0.1, 0.2, 0.3, 0.4], model_key="rxp-m1")   # a routed model: a registry row
    L.c.conn.commit()
    # control: as _SYSTEM (registry readable) the identity check refuses another model
    try:
        e.store_embedding("rxp:v2", [0.1, 0.2, 0.3, 0.4], model_key="rxp-other-model")
        ctl = "accepted"
    except Exception as exc:  # noqa: BLE001
        ctl = f"{type(exc).__name__}: {str(exc)[:200]}"
    L.c.conn.commit()
    reg = L.c.sql("SELECT table_name, graph_id, model_key, dimension FROM Graph_KG.embedding_registry")
    L.note("VEC-X1.16", "as _SYSTEM: a write with another model (rxp-other-model) makes its own route, no conflict",
           result=ctl,
           registry=[list(r) for r in reg], rows_v2=count(L, "kg_NodeEmbeddings", "node_id = ?", "rxp:v2"))


def final_state(L) -> dict:
    p = principal()
    login = None
    try:
        c = reader()
        login = {"accepted": True, "whoami": whoami(c)}
        c.close()
    except Exception as exc:  # noqa: BLE001
        login = {"accepted": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    all_t = tables(L)
    cp = {}
    for a in ("s", "i", "u", "d"):
        cp.update(checkpriv(L, all_t, a))
    nonzero = {k: v for k, v in cp.items() if v != 0}
    st = {"utc": now(), "user": p.get("user"), "role_resources": p.get("role"),
          "role_resources_as_recorded_before": p.get("role") == ROLE_ORIG["resources"],
          "sql_privileges_in_AUDITE": p["auditE_grants"], "privilege_rows_all_namespaces": p.get("privcount"),
          "login_after_disable": login, "checkprivilege_checked": len(cp), "checkprivilege_nonzero": nonzero,
          "raw": p["raw"]}
    st["ok"] = ("enabled=0" in (p.get("user") or "") and st["role_resources_as_recorded_before"]
                and not p["auditE_grants"] and not login["accepted"] and not nonzero)
    return clean(st)


def main():
    if not PW:
        raise SystemExit("IVGAUDIT_PW is not set (run through run_priv.sh)")
    with Lane("priv") as L:
        L.reset()
        L.control()
        seed(L)
        before = principal()
        ROLE_ORIG["resources"] = before.get("role")
        event("principal before", user=before.get("user"), role=before.get("role"),
              auditE_grants=before["auditE_grants"], privcount=before.get("privcount"))
        if before["auditE_grants"] or "enabled=0" not in (before.get("user") or ""):
            raise SystemExit("unexpected starting state: grants in AUDITE or user enabled")
        final = None
        try:
            event("enable user", result=set_enabled(1))
            all_s = (("INS-X10.7", s_ins_x10_7), ("ALG-B9.3/INS-X1.5", s_alg_b9_3_ins_x1_5),
                     ("SNP-X1.3", s_snp_x1_3), ("OPS-X4.84", s_ops_x4_84), ("VEC-X1.16", s_vec_x1_16),
                     ("VEC-X1.16-r2", s_vec_x1_16_r2))
            want = os.environ.get("RX_PRIV_SCENARIOS", "INS-X10.7,ALG-B9.3/INS-X1.5,SNP-X1.3,OPS-X4.84,VEC-X1.16").split(",")
            for name, fn in [x for x in all_s if x[0] in want]:
                event(f"scenario {name} start")
                try:
                    fn(L)
                except Exception as exc:  # noqa: BLE001
                    event(f"scenario {name} harness error", error=f"{type(exc).__name__}: {str(exc)[:400]}")
                event(f"scenario {name} end")
        finally:
            for priv, obj in list(GRANTED):
                revoke(L, priv, obj)
            if ROLE_ORIG["resources"]:
                event("role resources (final restore)", result=set_role_resources(ROLE_ORIG["resources"]))
            event("disable user", result=set_enabled(0))
            final = final_state(L)
            (OUT / f"final-state-{TAG}.json").write_text(json.dumps(final, indent=1, default=str) + "\n")
            event("final state", ok=final["ok"], nonzero=final["checkprivilege_nonzero"],
                  login=final["login_after_disable"])
        L.cases.append(clean({"statement": None, "case": "events", "outcome": "log", "events": EVENTS}))
        L.reset()
        L.save(f"results-{TAG}.json")


if __name__ == "__main__":
    main()
