#!/usr/bin/env python3
"""Randomized simulator (playbook §5c): long interleaved schedules through the real product on IRIS, AUDITA.

    bash tools/locks.sh iris python sim.py run OUT_DIR --seeds A:B [--minutes M]   # one lock hold, <= M minutes
    python sim.py check OUT_DIR                                                     # re-run the oracle on traces
    python sim.py self-test TRACE                                                   # oracle self-test
    bash tools/locks.sh iris python sim.py ddmin OUT_DIR SEED --invariant I6 [--finding F-CS01] [--tries N]
                                                    # shrink: drop chaos, seed prefix, phases, workers, single ops
    bash tools/locks.sh iris python sim.py plan OUT_DIR PLAN_JSON [--tries N]         # replay a fixed (shrunk) plan

Per schedule (schedule.py): reset AUDITA (Graph.KG.Eraser.EraseAll, Graph.KG.Ledger.PurgeAll, ledger.enable()),
snapshot the ledger, mark the journal, run each phase's workers (2-4 OS processes, one IRIS connection each, plus
an optional lock-holding probe; the driver may terminate one worker's IRIS process mid-operation), then at each
phase end observe the quiescent state directly (globals and SQL) and run the product's verify(); finally read the
journal since the mark and hand everything to the independent oracle (oracle.py). At most 6 connections at once.
"""
from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
sys.path.insert(0, str(HERE.parent / "traces"))
sys.path.insert(0, str(HERE))
import logging  # noqa: E402

logging.disable(logging.CRITICAL)
from iris_conn import Conn, version  # noqa: E402
import journal  # noqa: E402

import oracle  # noqa: E402
import schedule  # noqa: E402

NS = "AUDITA"
DB = "/usr/irissys/mgr/audita/"
PHASE_TIMEOUT = 240


# ------------------------------------------------------------------------------------------------ direct observation

def session(script: str, timeout: int = 300) -> str:
    return journal._session(script, timeout=timeout)


def dump_globals(roots: List[str]) -> Dict[str, List]:
    """Every node of the given globals of AUDITA, read server-side with $Query (one terminal session)."""
    rl = ",".join('"' + r.replace('"', '""') + '"' for r in roots)
    script = (' zn "' + NS + '" set nrec=0 for root=' + rl + ' { set n=root if $data(@n)#2 { set v=@n'
              ' try { set b=$system.Encryption.Base64Encode(v,1) } catch { set b="*" }'
              ' write $c(30),"G|",$zconvert(n,"O","JSON"),"|",b,! }'
              ' for { set n=$query(@n) quit:n=""  set v=@n'
              ' try { set b=$system.Encryption.Base64Encode(v,1) } catch { set b="*" }'
              ' write $c(30),"G|",$zconvert(n,"O","JSON"),"|",b,! set nrec=nrec+1 } }'
              ' write $c(30),"GEND|",nrec,!\n halt\n')
    out = session(script)
    if "\x1eGEND|" not in out:
        raise RuntimeError("global dump did not finish: " + out[-800:])
    res: Dict[str, List] = {r: [] for r in roots}
    for line in out.replace("\r", "").split("\n"):
        if not line.startswith("\x1eG|"):
            continue
        body = line[3:]
        g, b = body.rsplit("|", 1)
        ref = json.loads('"' + g + '"')
        root = journal.global_root(ref)
        res.setdefault(root, []).append([ref, None if b in ("", "*") else b])
    return res


def tables(c: Conn) -> Dict:
    return {
        "nodes": [list(map(_s, r)) for r in c.sql("SELECT %ID, node_id, graph_id FROM Graph_KG.nodes")],
        "edges": [list(map(_s, r)) for r in c.sql("SELECT %ID, graph_id, s, p, o_id, qualifiers FROM Graph_KG.rdf_edges")],
        "labels": [list(map(_s, r)) for r in c.sql("SELECT %ID, graph_id, s, label FROM Graph_KG.rdf_labels")],
        "props": [list(map(_s, r)) for r in c.sql('SELECT %ID, graph_id, s, "key", val FROM Graph_KG.rdf_props')],
        "revisions": [list(map(_s, r)) for r in c.sql(
            "SELECT seq, revision_id, kind, actor, message, source, correlation_id, idempotency_key, op_count "
            "FROM Graph_KG.ledger_revisions")],
        "stats": [list(map(_s, r)) for r in c.sql("SELECT * FROM Graph_KG.ledger_stats")],
    }


def _s(v):
    if v is None:
        return None
    if isinstance(v, (int, float, str)):
        return v
    try:
        return v.read() if hasattr(v, "read") else str(v)
    except Exception:  # noqa: BLE001
        return str(v)


def adjacency_missing(c: Conn, edges: List) -> List:
    out = []
    for _rid, g, s, p, o, quals in edges:
        gk = 0 if g in (None, "", "\x00") else g
        if not int(c.o.isDefined("^KG", "out", gk, s, p, o)):
            out.append([g, s, p, o])
    return out


def observe(c: Conn, run_verify: bool) -> Dict:
    from iris_vector_graph.engine import IRISGraphEngine
    g = dump_globals(["^IVG.Ledger", "^Graph.KG.LedgerRevisionD"])
    t = tables(c)
    obs = {"L": g.get("^IVG.Ledger", []), "R": g.get("^Graph.KG.LedgerRevisionD", []), "tables": t,
           "adj_missing": adjacency_missing(c, t["edges"]), "wall": time.time()}
    if run_verify:
        try:
            rep = IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4).ledger.verify()
            obs["verify"] = {"result": rep.result, "seq": rep.verified_seq,
                             "diff": [str(d)[:200] for d in rep.differences[:12]], "n_diff": len(rep.differences)}
        except Exception as ex:  # noqa: BLE001
            obs["verify"] = {"error": f"{type(ex).__name__}: {str(ex)[:300]}"}
        c.conn.commit()
        g2 = dump_globals(["^IVG.Ledger"])
        obs["stable_during_verify"] = g2.get("^IVG.Ledger", []) == obs["L"]
    return obs


def reset(c: Conn) -> None:
    from iris_vector_graph.engine import IRISGraphEngine
    c.call("Graph.KG.Eraser", "EraseAll")
    c.call("Graph.KG.Ledger", "PurgeAll")
    c.o.kill("^IVGAuditSim")
    c.conn.commit()
    IRISGraphEngine(c.conn, namespace=NS, embedding_dimension=4).ledger.enable()
    c.conn.commit()


# ------------------------------------------------------------------------------------------------ phases

def run_phase(ctl: Conn, phase: Dict, plan_path: Path, log: List[Dict]) -> Dict:
    plan_path.write_text(json.dumps({"workers": phase["workers"]}))
    procs = {}
    state = {w: {"pid": None, "cur": None} for w in phase["workers"]}
    lock = threading.Lock()

    def reader(w: str, p: subprocess.Popen):
        for line in p.stdout:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            with lock:
                log.append(ev)
                if ev["ev"] in ("hello", "reconnect"):
                    state[w]["pid"] = ev["pid"]
                elif ev["ev"] == "begin":
                    state[w]["cur"] = ev
                elif ev["ev"] == "op":
                    state[w]["cur"] = None

    threads = []
    t0 = time.time()
    for w in phase["workers"]:
        p = subprocess.Popen([sys.executable, str(HERE / "worker.py"), str(plan_path), w], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env={**os.environ, "PYTHONWARNINGS": "ignore"})
        procs[w] = p
        th = threading.Thread(target=reader, args=(w, p), daemon=True)
        th.start()
        threads.append(th)
    kills = []
    for at in phase.get("kills", []):
        while time.time() - t0 < at and any(p.poll() is None for p in procs.values()):
            time.sleep(0.05)
        deadline = time.time() + 4
        victim = None
        while time.time() < deadline and victim is None:
            with lock:
                cands = [(w, s["cur"]) for w, s in state.items() if s["cur"] and s["cur"]["kind"] in
                         ("commit", "redact", "erase") and not phase["workers"][w].get("probe")]
            if cands:
                pri = {"redact": 0, "erase": 1, "commit": 2}
                victim = sorted(cands, key=lambda c: pri[c[1]["kind"]])[0]
            else:
                time.sleep(0.002)
        if victim:
            w, cur = victim
            time.sleep([0.0, 0.002, 0.008, 0.02][int(at * 100) % 4])
            try:
                rc = ctl.call("%SYSTEM.Process", "Terminate", cur["pid"])
            except Exception as ex:  # noqa: BLE001
                rc = f"error {ex}"
            kills.append({"at": round(time.time() - t0, 3), "w": w, "i": cur["i"], "attempt": cur["attempt"],
                          "kind": cur["kind"], "pid": cur["pid"], "rc": str(rc)})
        else:
            kills.append({"at": round(time.time() - t0, 3), "victim": None})
    timed_out = []
    for w, p in procs.items():
        try:
            p.wait(timeout=max(1, PHASE_TIMEOUT - (time.time() - t0)))
        except subprocess.TimeoutExpired:
            timed_out.append(w)
            p.kill()
            p.wait(10)
            pid = state[w]["pid"]
            if pid:
                try:
                    ctl.call("%SYSTEM.Process", "Terminate", pid)
                except Exception:  # noqa: BLE001
                    pass
    for th in threads:
        th.join(5)
    errs = {w: p.stderr.read()[-1500:] for w, p in procs.items() if p.returncode not in (0, None)}
    # wait until every worker server process has gone (license slots, and its rollback is journaled)
    pids = {e["pid"] for e in log if e.get("ev") in ("hello", "reconnect")}
    end = time.time() + 30
    while time.time() < end and any(int(ctl.call("%SYS.ProcessQuery", "%ExistsId", p) or 0) for p in pids):
        time.sleep(0.2)
    return {"seconds": round(time.time() - t0, 2), "kills": kills, "timed_out": timed_out, "stderr": errs}


def run_schedule(plan: Dict, out: Path, tag: str) -> Dict:
    ctl = Conn(NS)
    try:
        reset(ctl)
        init = observe(ctl, run_verify=False)
        m = journal.mark()
        log: List[Dict] = []
        phases = []
        quiescent = []
        for k, ph in enumerate(plan["phases"]):
            info = run_phase(ctl, ph, out / f"{tag}.phase{k}.plan.json", log)
            phases.append(info)
            quiescent.append(observe(ctl, run_verify=True))
        recs = journal.records_since(m, dbs={DB})
        smap = journal.storage_map(ctl)
        ctl.o.kill("^IVGAuditSim")
    finally:
        ctl.close()
    keep = oracle.relevant_roots()
    recs = [r for r in recs if (not r["g"]) or journal.global_root(r["g"]) in keep]
    trace = {"plan": plan, "init": init, "journal": recs, "events": log, "phases": phases, "quiescent": quiescent,
             "smap_tables": {k: v for k, v in smap.items() if "Graph_KG" in v}}
    with gzip.open(out / f"{tag}.trace.json.gz", "wt") as f:
        json.dump(trace, f, default=str)
    for k in range(len(plan["phases"])):
        (out / f"{tag}.phase{k}.plan.json").unlink(missing_ok=True)
    return trace


def summarize(rep: Dict) -> Dict:
    return {k: rep[k] for k in ("seed", "ops", "committed_units", "violations_by_invariant", "violations_by_finding",
                                "observations", "replay_matches_engine") if k in rep}


def cmd_run(out: Path, seeds: range, minutes: float) -> int:
    out.mkdir(parents=True, exist_ok=True)
    c = Conn(NS)
    print("engine:", version(c), flush=True)
    c.close()
    t_start = time.time()
    n = 0
    for seed in seeds:
        if time.time() - t_start > minutes * 60:
            break
        plan = schedule.generate(seed)
        t0 = time.time()
        try:
            trace = run_schedule(plan, out, f"s{seed}")
        except Exception as ex:  # noqa: BLE001 - infrastructure: recorded, not a product result
            (out / f"s{seed}.infra-error.txt").write_text(f"{type(ex).__name__}: {ex}")
            print(json.dumps({"seed": seed, "infra_error": str(ex)[:300]}), flush=True)
            time.sleep(3)
            continue
        rep = oracle.check(trace)
        rep["seed"] = seed
        rep["wall_seconds"] = round(time.time() - t0, 2)
        (out / f"s{seed}.report.json").write_text(json.dumps(rep, indent=1, default=str))
        print(json.dumps({**summarize(rep), "s": rep["wall_seconds"]}, default=str), flush=True)
        n += 1
    print(f"schedules run in this hold: {n}; minutes {round((time.time() - t_start) / 60, 1)}", flush=True)
    return 0


def cmd_check(out: Path) -> int:
    for f in sorted(out.glob("s*.trace.json.gz"), key=lambda p: int(p.name[1:].split(".")[0])):
        with gzip.open(f, "rt") as fh:
            trace = json.load(fh)
        rep = oracle.check(trace)
        rep["seed"] = trace["plan"]["seed"]
        (out / f.name.replace(".trace.json.gz", ".report.json")).write_text(json.dumps(rep, indent=1, default=str))
        print(json.dumps(summarize(rep), default=str), flush=True)
    return 0


def cmd_shrink(out: Path, seed: int, invariant: str, tries: int) -> int:
    """Shortest schedule prefix (operations per worker, probe and kills kept) that still shows `invariant`."""
    out.mkdir(parents=True, exist_ok=True)
    full = schedule.generate(seed)
    total = sum(len(w["ops"]) for ph in full["phases"] for w in ph["workers"].values())
    results = []

    def reproduces(plan, label) -> bool:
        for t in range(tries):
            trace = run_schedule(plan, out, f"shrink-s{seed}-{label}-t{t}")
            rep = oracle.check(trace)
            hit = rep["violations_by_invariant"].get(invariant, 0) > 0
            results.append({"label": label, "try": t, "hit": hit,
                            "ops": sum(len(w["ops"]) for ph in plan["phases"] for w in ph["workers"].values()),
                            "violations": rep["violations_by_invariant"]})
            print(json.dumps(results[-1]), flush=True)
            if hit:
                return True
        return False

    lo, hi = 1, total
    best = None
    if reproduces(full, "full"):
        best = full
        while lo < hi:
            mid = (lo + hi) // 2
            cand = schedule.truncate(full, mid)
            if reproduces(cand, f"k{mid}"):
                hi, best = mid, cand
            else:
                lo = mid + 1
    (out / f"shrink-s{seed}.json").write_text(json.dumps({"seed": seed, "invariant": invariant, "attempts": results,
                                                          "minimal": best}, indent=1, default=str))
    return 0


def cmd_ddmin(out: Path, seed: int, invariant: str, finding: str, tries: int, minutes: float) -> int:
    """Shrink seed's schedule to a minimal one that still shows (invariant, finding): drop the kills and the probe,
    then whole workers and phases, then single operations (last first), then think times; each candidate is run up
    to `tries` times through the real product (the schedule is concurrent, so one run may not reproduce)."""
    import copy
    out.mkdir(parents=True, exist_ok=True)
    t_end = time.time() + minutes * 60
    attempts = []

    def size(p):
        return sum(len(w["ops"]) for ph in p["phases"] for w in ph["workers"].values())

    def hit(p, label) -> bool:
        for t in range(tries):
            trace = run_schedule(p, out, f"dd-s{seed}-{len(attempts)}")
            rep = oracle.check(trace)
            ok = any(v["invariant"] == invariant and (not finding or v["finding"] == finding) for v in rep["violations"])
            attempts.append({"label": label, "try": t, "ops": size(p), "hit": ok,
                             "violations": rep["violations_by_finding"]})
            print(json.dumps(attempts[-1]), flush=True)
            for f in out.glob(f"dd-s{seed}-*.trace.json.gz"):
                f.unlink()
            if ok:
                return True
        return False

    best = schedule.generate(seed)
    if not hit(best, "full"):
        (out / f"ddmin-s{seed}.json").write_text(json.dumps({"seed": seed, "reproduced": False, "attempts": attempts}))
        return 1

    def try_variant(mut, label):
        nonlocal best
        if time.time() > t_end:
            return False
        cand = copy.deepcopy(best)
        if not mut(cand):
            return False
        cand["phases"] = [ph for ph in cand["phases"] if ph["workers"]]
        for ph in cand["phases"]:
            ph["workers"] = {w: v for w, v in ph["workers"].items() if v["ops"]}
        cand["phases"] = [ph for ph in cand["phases"] if ph["workers"]]
        if not cand["phases"]:
            return False
        if hit(cand, label):
            best = cand
            return True
        return False

    def no_chaos(p):
        changed = False
        for ph in p["phases"]:
            if ph.get("kills"):
                ph["kills"], changed = [], True
            for w in [w for w, v in ph["workers"].items() if v.get("probe")]:
                del ph["workers"][w]
                changed = True
        return changed
    try_variant(no_chaos, "no-kills-no-probe")
    # seed prefix first: the shortest prefix (first k operations of every worker, phases in order) that reproduces
    lo, hi = 1, size(best)
    while lo < hi and time.time() < t_end:
        mid = (lo + hi) // 2
        base = copy.deepcopy(best)
        cand = schedule.truncate(base, mid)
        if cand["phases"] and hit(cand, f"prefix-k{mid}"):
            hi = mid
            best_prefix = cand
        else:
            lo = mid + 1
    if hi < size(best) and "best_prefix" in locals():
        best = best_prefix
    for k in range(len(best["phases"]) - 1, -1, -1):
        try_variant(lambda p, k=k: (p["phases"].pop(k), True)[1] if k < len(p["phases"]) else False, f"drop-phase{k}")
    for k in range(len(best["phases"])):
        for w in sorted(best["phases"][k]["workers"]):
            try_variant(lambda p, k=k, w=w: (p["phases"][k]["workers"].pop(w, None) is not None)
                        if k < len(p["phases"]) else False, f"drop-worker{w}")
    progress = True
    while progress and time.time() < t_end:
        progress = False
        for k in range(len(best["phases"])):
            for w in sorted(best["phases"][k]["workers"]):
                n = len(best["phases"][k]["workers"][w]["ops"])
                for i in range(n - 1, -1, -1):
                    def drop(p, k=k, w=w, i=i):
                        if k >= len(p["phases"]) or w not in p["phases"][k]["workers"]:
                            return False
                        ops = p["phases"][k]["workers"][w]["ops"]
                        if i >= len(ops):
                            return False
                        ops.pop(i)
                        return True
                    if try_variant(drop, f"drop-op p{k} w{w} i{i}"):
                        progress = True

    def no_think(p):
        for ph in p["phases"]:
            for v in ph["workers"].values():
                for o in v["ops"]:
                    o["think"] = 0.0
        return True
    try_variant(no_think, "no-think")
    (out / f"ddmin-s{seed}.json").write_text(json.dumps({"seed": seed, "invariant": invariant, "finding": finding,
                                                         "reproduced": True, "minimal_ops": size(best),
                                                         "minimal": best, "attempts": attempts}, indent=1, default=str))
    print(f"minimal schedule: {size(best)} operation(s)", flush=True)
    return 0


def cmd_plan(out: Path, plan_file: Path, tries: int) -> int:
    """Run a fixed plan (e.g. a shrunk schedule) `tries` times and report each run's violations."""
    out.mkdir(parents=True, exist_ok=True)
    plan = json.loads(plan_file.read_text())
    plan = plan.get("minimal", plan)
    for t in range(tries):
        trace = run_schedule(plan, out, f"plan-{plan_file.stem}-t{t}")
        rep = oracle.check(trace)
        rep["seed"] = plan.get("seed")
        (out / f"plan-{plan_file.stem}-t{t}.report.json").write_text(json.dumps(rep, indent=1, default=str))
        print(json.dumps({"try": t, **summarize(rep),
                          "violations": [v["detail"][:300] for v in rep["violations"]]}, default=str), flush=True)
    return 0


def main() -> int:
    cmd = sys.argv[1]
    if cmd == "self-test":
        return oracle.self_test(Path(sys.argv[2]))
    out = Path(sys.argv[2])
    if cmd == "check":
        return cmd_check(out)
    if cmd == "ddmin":
        seed = int(sys.argv[3])
        inv = sys.argv[sys.argv.index("--invariant") + 1]
        fid = sys.argv[sys.argv.index("--finding") + 1] if "--finding" in sys.argv else ""
        tries = int(sys.argv[sys.argv.index("--tries") + 1]) if "--tries" in sys.argv else 2
        minutes = float(sys.argv[sys.argv.index("--minutes") + 1]) if "--minutes" in sys.argv else 9.0
        return cmd_ddmin(out, seed, inv, fid, tries, minutes)
    if cmd == "plan":
        tries = int(sys.argv[sys.argv.index("--tries") + 1]) if "--tries" in sys.argv else 3
        return cmd_plan(out, Path(sys.argv[3]), tries)
    if cmd == "shrink":
        seed = int(sys.argv[3])
        inv = sys.argv[sys.argv.index("--invariant") + 1]
        tries = int(sys.argv[sys.argv.index("--tries") + 1]) if "--tries" in sys.argv else 3
        return cmd_shrink(out, seed, inv, tries)
    a, b = sys.argv[sys.argv.index("--seeds") + 1].split(":")
    minutes = float(sys.argv[sys.argv.index("--minutes") + 1]) if "--minutes" in sys.argv else 9.0
    return cmd_run(out, range(int(a), int(b)), minutes)


if __name__ == "__main__":
    raise SystemExit(main())
