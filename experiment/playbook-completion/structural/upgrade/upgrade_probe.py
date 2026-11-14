#!/usr/bin/env python3
"""3.6-capacity/01: the pin's initialize_schema() upgrading a populated v4.5.1 namespace (operator ruling O-1).

    locks.sh iris timeout 1800 python upgrade_probe.py build    # fixture build of a NEW namespace (refuses if it exists)
    locks.sh iris timeout 3000 python upgrade_probe.py load     # content through v4.5.1's own API (load451_child.py)
    locks.sh iris timeout 3000 python upgrade_probe.py upgrade  # dry run, a killed run, the completing run, checks

Namespace NS (default IVG262CAP; the fixture builds only IVG262*/IVG460FX*/IVG463*/IVG470* names) is created by the
pinned fixture scripts/fixtures/build_release_namespace.build("v4.5.1", NS) (imported unmodified: v4.5.1's own
initialize_schema compiles v4.5.1's classes into NS and seeds it) and is never dropped. Content is written by
load451_child.py under v4.5.1's own code. The upgrade is the pin's IRISGraphEngine(..., embedding_dimension=8)
.initialize_schema(): first dry_run=True, then a run in a child process killed after KILL_AFTER seconds (a failure
mid-upgrade), then the completing run in this process. Observed per run: wall time, client peak allocation
(tracemalloc), the server process's MemoryPeak (%SYS.ProcessQuery), journal bytes (journal address delta), the lock
table sampled every second (^$LOCK entries naming NS's globals, mode, and whether a table-level lock appeared), and the
returned status. Checks: content digests (rows of nodes, rdf_edges, rdf_labels, rdf_props, sorted, SHA-256) and the key
and FK oracles (structural/capkeys keys.keys_check, fk.fk_check) before, after the killed run, and after the completing
run; verify_graph of the default graph and of capg after the completing run.
Output: $RUN_DIR/structural/upgrade/<phase>.json
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent
PC = HERE.parents[1]
REPO = PC.parents[1]
sys.path.insert(0, str(PC / "tools"))
sys.path.insert(0, str(PC / "traces"))
sys.path.insert(0, str(HERE.parent / "capkeys"))
sys.path.append(str(REPO / "scripts" / "fixtures"))
from iris_conn import Conn, version  # noqa: E402
import journal as J  # noqa: E402
import build_release_namespace as brn  # noqa: E402  (the pinned fixture, unmodified)

NS = os.environ.get("CAP_NS", "IVG262CAP")
TAG = "v4.5.1"
DIM = brn.EMBEDDING_DIM
OUT = Path(os.environ["RUN_DIR"]) / "structural" / "upgrade"
OUT.mkdir(parents=True, exist_ok=True)
SIZES = dict(nodes=100_000, edges=200_000, named=10_000, temporal=20_000, vectors=2_000, commits=50)
KILL_AFTER = float(os.environ.get("CAP_KILL_AFTER", "8"))


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def session(script, ns="%SYS", timeout=600):
    r = subprocess.run(["docker", "exec", "-i", os.environ["IVG_TEST_CONTAINER"], "iris", "session", "IRIS", "-U", ns],
                       input=script, capture_output=True, text=True, errors="replace", timeout=timeout)
    return r.stdout.replace("\r", "")


def marked(out, tag):
    return [ln[1:] for ln in out.split("\n") if ln.startswith("\x1e" + tag + "|")]


def ns_exists(ns):
    out = session(f' write $c(30),"NS|",##class(Config.Namespaces).Exists("{ns}"),! halt\n')
    v = marked(out, "NS")
    if not v:
        raise RuntimeError("namespace probe failed: " + out[-300:])
    return v[0].split("|")[1].strip() == "1"


def ns_database(ns):
    out = session(f' set sc=##class(Config.Namespaces).Get("{ns}",.p) write $c(30),"DB|",$get(p("Globals")),! halt\n')
    v = marked(out, "DB")
    db = v[0].split("|")[1].strip() if v else ""
    out = session(f' set sc=##class(Config.Databases).Get("{db}",.p) write $c(30),"DIR|",$get(p("Directory")),! halt\n')
    d = marked(out, "DIR")
    return db, (d[0].split("|")[1].strip() if d else "")


def dump(name, obj):
    p = OUT / f"{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=str))
    return p


# ------------------------------------------------------------------------------------------------ build / load
def phase_build():
    rec = {"phase": "build", "namespace": NS, "tag": TAG, "started_utc": now()}
    if ns_exists(NS):
        rec["refused"] = f"{NS} exists: this probe builds a NEW namespace and never lets the fixture drop one"
        dump("build", rec)
        print(json.dumps(rec))
        return 1
    t = time.time()
    rec["fixture_call"] = f'scripts/fixtures/build_release_namespace.build("{TAG}", "{NS}")'
    rec["inventory"] = brn.build(TAG, NS)
    rec["seconds"] = round(time.time() - t, 1)
    rec["database"] = ns_database(NS)
    c = Conn(NS)
    try:
        rec["classes"] = sorted(r[0] for r in c.sql("SELECT Name FROM %Dictionary.CompiledClass WHERE NOT (Name %STARTSWITH '%')"))
        rec["engine"] = version(c)
    finally:
        c.close()
    rec["finished_utc"] = now()
    dump("build", rec)
    print(json.dumps({k: (v if k != "classes" else len(v)) for k, v in rec.items() if k != "inventory"}, default=str))
    return 0


def phase_load():
    tree = brn.release_worktree(TAG)
    env = dict(os.environ, PYTHONPATH=str(tree), IVG_AUDIT_REPO=str(REPO))
    args = [sys.executable, str(HERE / "load451_child.py"), NS] + [str(SIZES[k]) for k in
                                                                     ("nodes", "edges", "named", "temporal", "vectors", "commits")]
    t = time.time()
    out = subprocess.run(args, env=env, capture_output=True, text=True, timeout=2700, cwd=str(tree))
    rec = {"phase": "load", "namespace": NS, "sizes": SIZES, "returncode": out.returncode, "seconds": round(time.time() - t, 1),
           "stderr_tail": out.stderr[-3000:], "finished_utc": now()}
    if out.returncode == 0:
        rec["result"] = brn.parse_result(out.stdout)
    c = Conn(NS)
    try:
        rec["counts"] = counts(c)
    finally:
        c.close()
    dump("load", rec)
    print(json.dumps({k: v for k, v in rec.items() if k != "stderr_tail"}, default=str)[:3000])
    return 0 if out.returncode == 0 else 1


# ------------------------------------------------------------------------------------------------ checks
def counts(c):
    out = {}
    for t in ("nodes", "rdf_edges", "rdf_labels", "rdf_props", "kg_NodeEmbeddings", "ledger_revisions"):
        try:
            out[t] = c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t}")[0][0]
        except Exception as ex:  # noqa: BLE001
            out[t] = f"<{type(ex).__name__}>"
    return out


def digests(c):
    out = {}
    for t, cols in (("nodes", "node_id, COALESCE(graph_id,'')"), ("rdf_edges", "s, p, o_id, COALESCE(graph_id,''), ekey"),
                    ("rdf_labels", "s, label, COALESCE(graph_id,'')"), ("rdf_props", "s, \"key\", val, COALESCE(graph_id,'')")):
        h = hashlib.sha256()
        rows = sorted(tuple("" if v is None else str(v) for v in r) for r in c.sql(f"SELECT {cols} FROM %IGNOREINDEX * Graph_KG.{t}"))
        for r in rows:
            h.update(("\x1f".join(r) + "\x1e").encode("utf-8", "surrogatepass"))
        out[t] = {"rows": len(rows), "sha256": h.hexdigest()[:16]}
    return out


def oracles(c):
    import keys
    import fk
    out = {}
    try:
        k = keys.keys_check(c)
        out.update(key_violations=k["violations"][:6], row_counts=k.get("row_counts"))
    except Exception as ex:  # noqa: BLE001
        out["key_oracle_error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
    try:
        f = fk.fk_check(c)
        out["fk_violations"] = f["violations"][:6]
    except Exception as ex:  # noqa: BLE001
        out["fk_oracle_error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
    return out


def state(c, label):
    t = time.time()
    s = {"label": label, "counts": counts(c), "digests": digests(c), "oracles": oracles(c),
         "kg_out_graphs": {str(G): sum(1 for _ in c.o.iterator("^KG", "out", G).items()) for G, _ in c.o.iterator("^KG", "out").items()}
         if int(c.o.isDefined("^KG", "out")) else {},
         "classes_pin_named": c.sql("SELECT COUNT(*) FROM %Dictionary.CompiledClass WHERE Name %STARTSWITH 'Graph.KG.' OR Name %STARTSWITH 'IVG.'")[0][0],
         "schema_record": str(c.o.get("^IVG.Deploy", "schema") or "")}
    s["secs"] = round(time.time() - t, 1)
    return s


class LockSampler(threading.Thread):
    """Samples the lock table every second: entries whose global lives in NS's database, their mode, and table-level
    (subscript-free) locks on SQL storage globals."""

    def __init__(self, dbdir):
        super().__init__(daemon=True)
        self.dbdir, self.stop, self.samples = dbdir, threading.Event(), []

    def run(self):
        while not self.stop.is_set():
            out = session(' set n="",c=0,t=0,x="" for  { set n=$order(^$LOCK(n)) quit:n=""  set c=c+1 '
                          'if n\'["(" { set t=t+1,x=x_n_";" } } '
                          'write $c(30),"LS|",c,"|",t,"|",$extract(x,1,400),! halt\n', ns=NS, timeout=60)
            v = marked(out, "LS")
            if v:
                _, cnt, tbl, names = v[0].split("|", 3)
                self.samples.append({"t": round(time.time(), 1), "locks": int(cnt or 0), "table_level": int(tbl or 0), "names": names})
            self.stop.wait(1.0)


def mem_peak(pid):
    c = Conn(NS)
    try:
        r = c.sql("SELECT MemoryPeak, MemoryUsed FROM %SYS.ProcessQuery WHERE Pid = ?", int(pid))
        return [str(x) for x in r[0]] if r else None
    except Exception as ex:  # noqa: BLE001
        return f"<{type(ex).__name__}: {str(ex)[:120]}>"
    finally:
        c.close()


def journal_bytes(m0, m1):
    return (m1.address - m0.address) if m0.file == m1.file else f"switched files {m0.file} -> {m1.file}"


KILL_CHILD = r'''
import sys, os, time
sys.path.insert(0, os.environ["CAP_TOOLS"])
from iris_conn import Conn
from iris_vector_graph.engine import IRISGraphEngine
c = Conn(os.environ["CAP_NS"])
print("PID", c.pid, flush=True)
IRISGraphEngine(c.conn, namespace=os.environ["CAP_NS"], embedding_dimension=int(os.environ["CAP_DIM"])).initialize_schema()
print("DONE", flush=True)
'''


def phase_upgrade():
    from iris_vector_graph.engine import IRISGraphEngine
    rec = {"phase": "upgrade", "namespace": NS, "started_utc": now(), "kill_after_s": KILL_AFTER}
    db, dbdir = ns_database(NS)
    rec["database"] = [db, dbdir]
    c = Conn(NS)
    try:
        rec["before"] = state(c, "before (v4.5.1 with content)")
        t = time.time()
        rec["dry_run"] = {"status": {k: v for k, v in IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=DIM)
                                     .initialize_schema(dry_run=True).items() if k in ("schema", "schema_recorded", "legacy_objects",
                                     "ledger_history_copied", "embedding_dimension", "other_schemas", "grants_copied", "read_path_grants",
                                     "arno_wrappers_replaced")}, "secs": round(time.time() - t, 1)}
        c.conn.commit()
    finally:
        c.close()
    # --- a run killed mid-way
    env = dict(os.environ, CAP_TOOLS=str(PC / "tools"), CAP_NS=NS, CAP_DIM=str(DIM))
    p = subprocess.Popen([sys.executable, "-c", KILL_CHILD], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = p.stdout.readline()
    kpid = line.split()[1] if line.startswith("PID") else None
    time.sleep(KILL_AFTER)
    finished_before_kill = p.poll() is not None
    if not finished_before_kill:
        os.kill(p.pid, signal.SIGKILL)
    p.wait(timeout=60)
    err_tail = p.stderr.read()[-1500:] if p.stderr else ""
    gone = None
    for _ in range(60):
        c2 = Conn(NS)
        try:
            gone = not c2.sql("SELECT COUNT(*) FROM %SYS.ProcessQuery WHERE Pid = ?", int(kpid or 0))[0][0]
        finally:
            c2.close()
        if gone:
            break
        time.sleep(2)
    rec["killed_run"] = {"client_killed_after_s": KILL_AFTER, "finished_before_kill": finished_before_kill,
                         "server_pid": kpid, "server_process_gone": gone, "stderr_tail": err_tail}
    c = Conn(NS)
    try:
        rec["after_kill"] = state(c, "after the killed run")
    finally:
        c.close()
    # --- the completing run, measured
    c = Conn(NS)
    sampler = LockSampler(dbdir)
    try:
        m0 = J.mark()
        sampler.start()
        tracemalloc.start()
        t = time.time()
        err = None
        try:
            st = IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=DIM).initialize_schema()
        except Exception as ex:  # noqa: BLE001
            st, err = {}, f"{type(ex).__name__}: {str(ex)[:600]}"
        secs = round(time.time() - t, 1)
        _cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        c.conn.commit()
        sampler.stop.set()
        sampler.join(timeout=30)
        m1 = J.mark()
        rec["completing_run"] = {
            "secs": secs, "error": err, "client_peak_MB": round(peak / 1e6, 1), "server_pid": c.pid,
            "server_memory_peak_used": mem_peak(c.pid), "journal_bytes": journal_bytes(m0, m1),
            "lock_samples": len(sampler.samples), "max_locks": max((s["locks"] for s in sampler.samples), default=0),
            "table_level_lock_seen": any(s["table_level"] for s in sampler.samples),
            "table_level_examples": sorted({s["names"] for s in sampler.samples if s["table_level"]})[:5],
            "status": {k: st.get(k) for k in ("schema", "tables_created", "objectscript_compiled", "objectscript_failed", "warnings",
                                            "kg_built", "adjacency_index", "ledger_index", "tuned", "routines", "ledger_history_copied",
                                            "needs_manual_migration", "embedding_dimension", "legacy_objects")}}
        rec["after"] = state(c, "after the completing run")
        e = IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=DIM)
        rec["verify_default"] = {k: v for k, v in e.verify_graph().items() if k in ("ok", "counts", "drift")}
        rec["verify_capg"] = {k: v for k, v in e.verify_graph(graph="capg").items() if k in ("ok", "counts", "drift")}
        try:
            rec["ledger_verify"] = str(e.ledger.verify().result)
        except Exception as ex:  # noqa: BLE001
            rec["ledger_verify"] = f"<{type(ex).__name__}: {str(ex)[:200]}>"
    finally:
        sampler.stop.set()
        c.close()
    b, k, a = rec["before"], rec["after_kill"], rec["after"]
    rec["content_unchanged_by_killed_run"] = b["digests"] == k["digests"]
    rec["content_unchanged_by_upgrade"] = b["digests"] == a["digests"]
    rec["finished_utc"] = now()
    dump("upgrade", rec)
    print(json.dumps({x: rec[x] for x in ("killed_run", "content_unchanged_by_killed_run", "content_unchanged_by_upgrade",
                                          "verify_default", "verify_capg", "ledger_verify")}, default=str)[:3000])
    print(json.dumps(rec["completing_run"], default=str)[:3000])
    print(json.dumps({x: {"counts": rec[x]["counts"], "oracles": rec[x]["oracles"], "classes": rec[x]["classes_pin_named"]}
                      for x in ("before", "after_kill", "after")}, default=str)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit({"build": phase_build, "load": phase_load, "upgrade": phase_upgrade}[sys.argv[1]]())
