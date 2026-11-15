#!/usr/bin/env python3
"""Census cells WS-OBL-147/-148/-150 (iris_sql_store._delete_nodes_sql) and WS-OBL-154 (IRISGraphStore.delete_edges'
SQL DELETE): is the SQL fallback reachable at the pin, and what does it leave? Live, AUDITB, as the operator-authorised
disposable principal IVGAUDIT_RO / IVGAUDIT_RO_ROLE (versions/PRIVILEGE.md).

    bash experiment/playbook-completion/writesets/live/run_sql_fallback.sh      # password by env var name, IRIS lock

The fallback runs when IRISGraphStore._has_eraser_method answers False (iris_sql_store.py:1307-1318). That method
caches ANY exception of the probe as "absent". The probe asks %Dictionary.CompiledMethod in SQL; a role without the
dictionary privilege is refused (-99) and then asked over the Native API (IDKEYExists, _dictionary.py:46-55, 4.6.0
R206), which needs %Native_ClassExecution. Two variants of the same seeded state, through the pin's public API
(IRISGraphEngine.delete_node -> store.delete_nodes; IRISGraphStore.delete_edges, exported by iris_vector_graph):

  doc     ADMIN_GUIDE section 3's writing row: %DB_%DEFAULT:RW, %Native_ClassExecution:U, %Native_GlobalAccess:U,
          SELECT/EXECUTE (already held in AUDITB) plus INSERT, UPDATE, DELETE ON SCHEMA Graph_KG.   (control)
  noexec  the same without %Native_ClassExecution:U.

Seed (as _SYSTEM, each variant): Eraser.EraseAll + Ledger.PurgeAll; ledger enabled (not strict); one changeset with
nodes sfp|a..sfp|d and edges sfp|a -R-> sfp|b, sfp|c -R-> sfp|d. Oracles (as _SYSTEM, before and after): the rows, the
ledger statement of each edge (^IVG.Ledger tuple/stmt, as ws_probes' stmt cases read it: INV-stmt is "the live
statements are exactly the live recorded edges"), ^KG("out", g, s, p, o) for each edge, verify(); as the user: the
probe's cached answers (the store's _eraser_methods dict, read, not changed) and every log record of the product.

Role changes are made in %SYS and restored in `finally` to the recorded value; grants are made by _SYSTEM and revoked
AS "_SYSTEM"; the user is enabled only inside each variant and disabled in `finally`; the final principal must equal
the initial one (checked and recorded). The password arrives only as IVGAUDIT_PW and is never written (each record is
scanned for it). Nothing is compiled; no product file is touched.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ws_probes as W  # noqa: E402  (helpers: Conn, eng, reset, live_rows, _stmt_of, verify, err; NS = AUDITB)

import iris.dbapi  # noqa: E402
from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402
from iris_vector_graph.stores import IRISGraphStore  # noqa: E402
from tests import conftest as fx  # noqa: E402

NS = W.NS
USER, ROLE = "IVGAUDIT_RO", "IVGAUDIT_RO_ROLE"
CONTAINER = os.environ["IVG_TEST_CONTAINER"]
PW = os.environ.get("IVGAUDIT_PW", "")
OUT = Path(os.environ["RUN_DIR"]) / "writesets" / "sql-fallback"
TAG = os.environ.get("SFP_TAG", "r1")
EVENTS: list = []
GRANTED: list = []
EDGES = (("sfp|a", "R", "sfp|b"), ("sfp|c", "R", "sfp|d"))
VARIANTS = (
    ("doc", "%DB_%DEFAULT:RW,%Native_ClassExecution:U,%Native_GlobalAccess:U"),
    ("noexec", "%DB_%DEFAULT:RW,%Native_GlobalAccess:U"),
)


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
    d = {}
    for tag in ("USER", "ROLE", "PRIVCOUNT"):
        if f"<<{tag}:" in out:
            d[tag.lower()] = out.split(f"<<{tag}:")[1].split(f":{tag}>>")[0]
    d["grants"] = sorted(l for l in out.split("\n") if l.startswith("PRIV "))
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


def sql(conn, q):
    cur = conn.cursor()
    try:
        cur.execute(q)
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}
    finally:
        cur.close()


def grant(c, priv, obj):
    r = sql(c.conn, f"GRANT {priv} ON {obj} TO {ROLE}")
    GRANTED.append((priv, obj))
    event("grant", statement=f"GRANT {priv} ON {obj} TO {ROLE}", result=r)


def revoke(c, priv, obj):
    r = sql(c.conn, f'REVOKE {priv} ON {obj} FROM {ROLE} AS "_SYSTEM"')
    if not r["ok"]:
        r = {"as_form": r, "plain": sql(c.conn, f"REVOKE {priv} ON {obj} FROM {ROLE}")}
    if (priv, obj) in GRANTED:
        GRANTED.remove((priv, obj))
    event("revoke", statement=f'REVOKE {priv} ON {obj} FROM {ROLE} AS "_SYSTEM"', result=r)


def user_conn():
    c = iris.dbapi.connect(hostname="127.0.0.1", port=int(os.environ["IVG_PORT"]), namespace=NS, username=USER,
                           password=PW)
    actual = fx.probe_instance_hostname(c)
    if not fx.container_hostname_matches(actual, fx.docker_container_hostname(CONTAINER),
                                         fx.docker_container_id(CONTAINER)):
        c.close()
        raise RuntimeError("database identity does not match the audit container")
    return c


def kg_out(c) -> dict:
    """^KG("out", g, s, p, o) for each seeded edge, in every graph key present."""
    graphs = [str(g) for g, _ in c.o.iterator("^KG", "out").items()]
    return {"->".join(e): sorted(g.encode("unicode_escape").decode() for g in graphs
                                 if c.o.isDefined("^KG", "out", g, *e)) for e in EDGES}


def state(c) -> dict:
    e = W.eng(c)
    return {"rows": W.live_rows(c, "sfp"),
            "edge_rows": [list(r) for r in c.sql("SELECT %EXACT(s), %EXACT(p), %EXACT(o_id) FROM Graph_KG.rdf_edges "
                                                 "WHERE %EXACT(s) %STARTSWITH 'sfp|' ORDER BY s")],
            "stmts": {"->".join(t): W._stmt_of(c, *t) for t in EDGES},
            "kg_out": kg_out(c),
            "verify": W.verify(e)}


def seed(c) -> dict:
    W.reset(c)
    e = W.eng(c)
    e.ledger.enable()
    cs = Changeset(actor="audit:writesets", actor_type="ingest", message="sql-fallback seed")
    for n in "abcd":
        cs.create_node(f"sfp|{n}")
    for s, p, o in EDGES:
        cs.create_relationship(s, p, o)
    seq = W.err(lambda: e.ledger.commit(cs).revision.seq)
    c.conn.commit()
    return {"commit": seq, "ledger_state": W.err(lambda: e.ledger.state() if hasattr(e.ledger, "state") else None)}


class Grab(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, r):
        self.records.append(f"{r.levelname} {r.name}: {r.getMessage()[:300]}")


def as_user(variant: str) -> dict:
    out = {}
    grab = Grab()
    root = logging.getLogger()
    root.addHandler(grab)
    old = root.level
    root.setLevel(logging.DEBUG)
    uc = user_conn()
    try:
        out["whoami"] = [list(r) for r in (lambda cur: (cur.execute("SELECT $USERNAME"), cur.fetchall())[1])(uc.cursor())]
        ue = W.err(lambda: IRISGraphEngine(uc, namespace=NS, embedding_dimension=4))
        out["engine"] = {k: v for k, v in ue.items() if k != "value"}
        if ue["ok"]:
            e = ue["value"]
            out["delete_node_sfp|a"] = W.err(lambda: e.delete_node("sfp|a", graph=None))
            store = getattr(e, "_store", None) or getattr(getattr(e, "_e", None), "_store", None)
            out["engine_store_probe_cache"] = dict(getattr(store, "__dict__", {}).get("_eraser_methods", {})) if store else "no store"
        st = IRISGraphStore(uc, namespace=NS)
        out["store_delete_edges_sfp|c"] = W.err(lambda: str(st.delete_edges([EDGES[1]], graph=None).rows))
        out["store_probe_cache"] = dict(st.__dict__.get("_eraser_methods", {}))
        try:
            uc.commit()
        except Exception as ex:  # noqa: BLE001
            out["final_commit"] = f"{type(ex).__name__}: {str(ex)[:200]}"
    finally:
        try:
            uc.close()
        except Exception:  # noqa: BLE001
            pass
        root.removeHandler(grab)
        root.setLevel(old)
    out["log_records"] = [r for r in grab.records if "iris_vector_graph" in r or "Eraser" in r][:40]
    out["log_warning_or_above"] = [r for r in grab.records if not r.startswith(("DEBUG", "INFO"))][:20]
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res_path = OUT / f"results-{TAG}.json"
    if res_path.exists():
        print(f"{res_path} exists: use a new SFP_TAG")
        return 2
    if not PW:
        print("IVGAUDIT_PW is not set")
        return 2
    res = {"tag": TAG, "namespace": NS, "started": now()}
    p0 = principal()
    event("principal-initial", **p0)
    role0 = p0.get("role")
    if not role0 or "enabled=0" not in (p0.get("user") or ""):
        event("refused", reason="principal not in the recorded state (role missing or user enabled)")
        return 2
    res["variants"] = {}
    with W.Conn(NS) as c:
        res["engine_version"] = W.version(c)
        try:
            for name, resources in VARIANTS:
                v = {"resources": resources, "seed": seed(c)}
                v["before"] = state(c)
                try:
                    event(f"{name}:role", out=set_role_resources(resources))
                    for priv in ("INSERT", "UPDATE", "DELETE"):
                        grant(c, priv, "SCHEMA Graph_KG")
                    event(f"{name}:enable", out=set_enabled(1))
                    t0 = time.time()
                    v["as_user"] = as_user(name)
                    v["user_seconds"] = round(time.time() - t0, 2)
                finally:
                    event(f"{name}:disable", out=set_enabled(0))
                    for priv, obj in list(GRANTED):
                        revoke(c, priv, obj)
                    event(f"{name}:role-restore", out=set_role_resources(role0))
                v["after"] = state(c)
                res["variants"][name] = clean(v)
        finally:
            for priv, obj in list(GRANTED):
                revoke(c, priv, obj)
            set_enabled(0)
            set_role_resources(role0)
            W.reset(c)
            c.conn.commit()
    p1 = principal()
    event("principal-final", **p1)
    res["principal_restored"] = {k: p0.get(k) == p1.get(k) for k in ("user", "role", "privcount", "grants")}
    res["events"] = EVENTS

    def verdict(v):
        a, b = v["before"], v["after"]
        u = v.get("as_user", {})
        return {
            "fallback_taken_engine": u.get("engine_store_probe_cache", {}).get("EraseNodeIds") is False,
            "fallback_taken_store": u.get("store_probe_cache", {}).get("EraseEdges") is False,
            "node_rows_after": b["rows"],
            "edge_rows_after": b["edge_rows"],
            "kg_out_after": b["kg_out"],
            "stmt_live_without_row": {k: (b["stmts"][k][0] is not None and list(k.split("->")) not in b["edge_rows"])
                                      for k in b["stmts"]},
            "verify_after": (b["verify"].get("value") or {}).get("result"),
            "warnings": u.get("log_warning_or_above"),
        }
    res["verdict"] = {n: verdict(v) for n, v in res["variants"].items()}
    res["finished"] = now()
    res_path.write_text(json.dumps(clean(res), indent=1, default=str))
    print(json.dumps(res["verdict"], indent=1, default=str))
    print(json.dumps(res["principal_restored"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
