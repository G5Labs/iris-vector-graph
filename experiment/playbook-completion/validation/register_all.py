#!/usr/bin/env python3
"""Register every finished validation run (one evidence/runs/val-<run>.json each) through tools/register_run.py.

    python register_all.py [prefix ...]      (default: every run in results.json; already-registered ids are kept)

result: pass when the run's exit is 0, fail otherwise, blocked for runs listed in BLOCKED (licence exhaustion),
incomplete for attempts that did not finish. --observes carries the counts and the triage rule ids with counts.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from aggregate import runs_of  # noqa: E402
from triage import triage  # noqa: E402

REG = HERE.parent / "tools" / "register_run.py"
EVID = HERE.parent / "evidence" / "runs"
ATTEMPTS = {
    "unit-1": ("fail", "harness attempt: collection error (read-only audit worktree; FastHTML writes .sesskey into the "
                       "cwd); superseded by unit-3 from the clean clone"),
    "unit-2": ("incomplete", "stopped at 42% when the connection-cap rule arrived (not under the iris lock) and the first "
                             "harness version refused unit tests exercising _deploy_objectscript/tcp_setup with fakes; "
                             "superseded by unit-3"),
    "harness-check-1": ("pass", "harness self-check of the refined dispatch on two unit files (21 passed); not a suite result"),
    "perf-smoke-1": ("pass", "smoke of validation/perf at 4,000 records; not a measurement"),
    "docs-1": ("fail", "pre-connection-cap docs run (not under the lock); superseded by docs-2 (same 196 passed / 16 failed)"),
    "regression-1": ("fail", "pre-connection-cap regression run (static, no IRIS); superseded by regression-2 (same result)"),
}


def registered(rid):
    return (EVID / f"val-{rid}.json").exists()


def command_of(log: Path) -> str:
    lines = log.read_text(errors="replace").splitlines()
    return lines[1][len("# cmd: "):][:3000] if len(lines) > 1 and lines[1].startswith("# cmd: ") else "see log"


def reg(rid, result, log, command, observes, extra=()):
    if registered(rid):
        return
    subprocess.run([sys.executable, str(REG), f"val-{rid}", "run", result, str(log), "--lane", "validation",
                    "--command", command, "--observes", observes, "--extra", *extra], check=True)


def register_pytest(prefix, suite, note=""):
    a, rules, _ = triage(prefix)
    tri = ", ".join(f"{k}={v['count']} ({v['category']})" for k, v in rules.items()) or "none"
    for c in a["chunks"]:
        log = Path(c["log"])
        if c["exit"] is None:
            continue
        if c["id"] in ATTEMPTS:
            res, why = ATTEMPTS[c["id"]]
            reg(c["id"], res, log, command_of(log), f"{suite}: {json.dumps(c['counts'])}. {why}")
            continue
        res = "pass" if c["exit"] == "0" else "fail"
        reg(c["id"], res, log, command_of(log),
            f"{suite} ({prefix}, chunk {c['id']}): {json.dumps(c['counts'])}. Triage of the whole {prefix} set: {tri}. "
            f"{note}Rules: validation/triage.py; per-case lists in validation/results.json.")


def main():
    res = json.loads((HERE / "results.json").read_text())
    for s in res["functional"]:
        for r in s["decisive"] + s["supporting"]:
            if r.get("status") != "done":
                continue
            rid = r["id"]
            if rid.startswith("tck"):
                log = Path(r["log"])
                failed = r.get("failed_scenarios")
                reg(rid, "fail" if failed else "pass", log,
                    "validation/run_tck.sh / scripts/tck/run_all.sh (behave per area, TCK_LOCK=0, under locks.sh iris)",
                    f"{s['suite']}: {'; '.join(r['summary'][:3])}. Failed: {failed}. Triage: product-defect "
                    "(Unwind1 [3] '<ARGUMENT ERROR> Incorrect number of parameters', reproduced by tck-unwind-rerun-1).")
                continue
            if rid.startswith("scratch-236"):
                continue  # registered by hand as blocked (licence exhaustion): val-scratch-236-1, val-scratch-236-1-rerun-*
            register_pytest(rid, s["suite"])
    for s in res["perf"]:
        for r in s["runs"]:
            if r.get("status") != "done":
                continue
            rid = r["id"]
            if rid.startswith("bench-"):
                reg(rid, "pass" if r["exit"] == "0" else "fail", Path(r["log"]), command_of(Path(r["log"])),
                    f"{s['measurement']}: result file {r.get('result_file')}")
                continue
            note = ""
            if r.get("sc_lines"):
                note = " ".join(r["sc_lines"]) + " "
            if r.get("committer_cycles"):
                note += " ".join(
                    f"[cycle {m['cycle']}: redact {m['redact_s']} s, receipt max_batch_ms {m['receipt']['max_batch_ms']}, "
                    f"longest commit during redaction {m['commit_latency_B_during'].get('max_ms')} ms (n="
                    f"{m['commit_latency_B_during'].get('n')}), before p50 {m['commit_latency_A_before'].get('p50_ms')} ms, "
                    f"verify {m['verify']}, history contiguous {m['history']['contiguous']}]" for m in r["committer_cycles"]) + " "
            register_pytest(rid, s["measurement"], note)


if __name__ == "__main__":
    main()
