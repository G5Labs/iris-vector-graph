"""Module 16 live helpers: journal a server-side operation by scratch marker, start/stop servers by PID.

A server under test runs its own IRIS process, so its pid is not known in advance. `journal_by_marker` takes the
journal window around the call, finds every process that wrote a global node containing the scratch marker (a
c16-prefixed id), and classifies all records of those processes in the window exactly as
experiment/playbook-completion/live/breadth-c/jcheck.py does (txn / nontransactional increment / outside any txn).
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import jcheck  # noqa: E402
from jcheck import journal, DB  # noqa: E402

REPO = HERE.parents[4]  # the repository root (…/experiment/playbook-completion/live/breadth-c/16)
PY = sys.executable


def classify(recs, smap):
    open_ = {}
    cls = {"txn": set(), "increment": set(), "autocommit": set()}
    commits = {}
    for r in recs:
        t = r["t"]
        if t == "BeginTrans":
            open_[r["p"]] = True
            continue
        if t == "CommitTrans" or t.startswith("RollBack") or t == "Rollback":
            if t == "CommitTrans":
                commits[r["p"]] = commits.get(r["p"], 0) + 1
            open_.pop(r["p"], None)
            continue
        if not r["g"]:
            continue
        st = journal.store_of(r["g"], smap)
        if open_.get(r["p"]):
            cls["txn" if r["x"] else "increment"].add(st)
        else:
            cls["autocommit"].add(st)
    return {"stores_written": sorted(cls["txn"] | cls["increment"] | cls["autocommit"]),
            "stores_written_in_txn": sorted(cls["txn"]),
            "stores_with_nontransactional_increments": sorted(cls["increment"]),
            "stores_written_outside_any_txn": sorted(cls["autocommit"]),
            "outermost_commits_by_pid": commits}


def journal_by_marker(label, fn, markers, smap, own_pids=()):
    m = journal.mark()
    t0 = time.time()
    err = None
    try:
        res = fn()
    except Exception as e:
        res, err = None, f"{type(e).__name__}: {e}"[:1500]
    dt = time.time() - t0
    recs = journal.records_since(m, dbs={DB})
    pids = {r["p"] for r in recs if r["g"] and any(mk in r["g"] for mk in markers)} | set(map(str, own_pids))
    mine = [r for r in recs if r["p"] in pids]
    out = {"label": label, "seconds": round(dt, 3), "error": err, "result": res, "pids": sorted(pids),
           "records": len(mine), "other_pids_in_window": sorted({r["p"] for r in recs} - pids)}
    out.update(classify(mine, smap))
    out["raw_sample"] = [{"p": r["p"], "t": r["t"], "x": r["x"], "g": (r["g"] or "")[:160]} for r in mine[:300]]
    return out


def free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def start(name, args, env_extra, port, log: Path, cwd=REPO, wait_path="/health", timeout=90, http=True):
    if not free(port):
        raise RuntimeError(f"port {port} busy")
    env = dict(os.environ)
    for k in ("IVG_API_KEY", "IVG_READ_ONLY", "IRIS_HOST", "IRIS_PORT", "IRIS_NAMESPACE"):
        env.pop(k, None)
    env.update(env_extra)
    lf = open(log, "w")
    p = subprocess.Popen([PY, *args], cwd=str(cwd), env=env, stdout=lf, stderr=subprocess.STDOUT,
                         start_new_session=True)
    deadline = time.time() + timeout
    import httpx
    while time.time() < deadline:
        if p.poll() is not None:
            raise RuntimeError(f"{name} exited {p.returncode}; see {log}")
        if not free(port):
            if not http:
                return p
            try:
                httpx.get(f"http://127.0.0.1:{port}{wait_path}", timeout=5)
                return p
            except Exception:
                pass
        time.sleep(0.5)
    stop(p)
    raise RuntimeError(f"{name} did not listen on {port} within {timeout}s")


def stop(p):
    if p is None or p.poll() is not None:
        return
    os.killpg(p.pid, signal.SIGTERM)  # its own session: the uvicorn process (and only it)
    try:
        p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait(timeout=10)


def iris_env():
    return {"IRIS_HOST": "127.0.0.1", "IRIS_PORT": os.environ["IVG_PORT"], "IRIS_NAMESPACE": "AUDITC",
            "IRIS_USERNAME": "_SYSTEM", "IRIS_USER": "_SYSTEM", "IRIS_PASSWORD": "SYS"}


def dump(path, obj):
    jcheck.dump(Path(path), obj)
