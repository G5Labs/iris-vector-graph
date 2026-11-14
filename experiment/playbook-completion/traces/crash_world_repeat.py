#!/usr/bin/env python3
"""Repeated instance-crash trials under a stated SynchCommit setting (playbook §3.7 integration worlds).

    bash tools/locks.sh iris python traces/crash_world_repeat.py OUT_DIR --trials 3 --expect-synchcommit 0|1

Run only while holding the IRIS lock AND while no other lane uses the container: every trial SIGKILLs the whole
container (traces/crash_world.py crash_and_restart) and restarts it. Reuses crash_world.py's client, observation and
oracle unchanged (same N, same FR-047 / head / stmt-tuple / verify / retry checks); adds only repetition and a
record of the SynchCommit value actually in force (read from iris.cpf and from Config.Journal in %SYS) before every
trial. Refuses to run if the setting differs from --expect-synchcommit, so a result is always attributed to the
setting it ran under.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))
import crash_world as cw  # noqa: E402
from iris_conn import Conn, version  # noqa: E402


def synchcommit() -> dict:
    cpf = subprocess.run(["docker", "exec", cw.CONTAINER, "grep", "-n", "^SynchCommit=", "/usr/irissys/iris.cpf"],
                         capture_output=True, text=True).stdout.strip()
    script = ' set sc=##class(Config.Journal).Get(.p) write "SC=",$get(p("SynchCommit")),! halt\n'
    live = subprocess.run(["docker", "exec", "-i", cw.CONTAINER, "iris", "session", "IRIS", "-U", "%SYS"],
                          input=script, capture_output=True, text=True).stdout
    val = None
    for line in live.splitlines():
        if line.strip().startswith("SC="):
            val = line.strip()[3:]
    return {"cpf": cpf, "config_journal": val}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--expect-synchcommit", required=True, choices=["0", "1"])
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    s0 = synchcommit()
    if s0["config_journal"] != a.expect_synchcommit or not s0["cpf"].endswith("=" + a.expect_synchcommit):
        print("refused: SynchCommit in force", s0, "expected", a.expect_synchcommit)
        return 2
    c = Conn(cw.NS)
    eng_version = version(c)
    from iris_vector_graph.engine import IRISGraphEngine
    c.call("Graph.KG.Eraser", "EraseAll")
    c.call("Graph.KG.Ledger", "PurgeAll")
    IRISGraphEngine(c.conn, namespace=cw.NS, embedding_dimension=4).ledger.enable()
    c.conn.commit()
    c.close()
    results = []
    for i in range(a.trials):
        for name, crash_after, wait_ack in (("in-flight", 2.0, False), ("acknowledged", 0.0, True)):
            before = synchcommit()
            tag = f"r{a.expect_synchcommit}{i}{name[0]}_"
            r = cw.trial(f"{name}-{i + 1}", f"crashrep-{a.expect_synchcommit}-{name}-{i + 1}", tag, crash_after, wait_ack)
            r["synchcommit_before"] = before
            results.append(r)
            (out / "results.json").write_text(json.dumps({"engine": eng_version, "expect_synchcommit": a.expect_synchcommit,
                                                          "n": cw.N, "trials": results}, indent=1))
            print(json.dumps({k: r[k] for k in ("trial", "commit_running_at_crash", "violations_after_crash",
                                                 "violations_after_retry")} | {"synchcommit": before["config_journal"]}),
                  flush=True)
    s1 = synchcommit()
    summary = {"engine": eng_version, "synchcommit_start": s0, "synchcommit_end": s1, "trials": len(results),
               "acknowledged_lost": sum(1 for r in results if any("acknowledged commit lost" in v
                                                                    for v in r["violations_after_crash"])),
               "acknowledged": sum(1 for r in results if r["acknowledged"]),
               "violations_after_retry": sum(len(r["violations_after_retry"]) for r in results),
               "partial_after_crash": sum(1 for r in results if any("FR-047 partial" in v
                                                                    for v in r["violations_after_crash"])),
               "other_violations_after_crash": sorted({v for r in results for v in r["violations_after_crash"]
                                                       if "FR-047 partial" not in v and "acknowledged commit lost" not in v})}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print("SUMMARY", json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
