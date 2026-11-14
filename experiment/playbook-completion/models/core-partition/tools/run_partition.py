#!/usr/bin/env python3
"""Lane models-2, proof debt D-10: run every check of models/core-partition and write RESULTS.json.

    source experiment/playbook-completion/environment.sh
    python experiment/playbook-completion/models/core-partition/tools/run_partition.py [--register] [--skip-full]

Do NOT wrap this script in tools/locks.sh heavy: it takes the heavy lock itself, once for the six (2, 2) family runs
(run in parallel, about 1 GB each) and once for each unpartitioned (2, 2) run (about 15-20 GB each), so other lanes can
interleave between them. The small checks (coverage, union on the smaller profiles, fidelity of the copy) each take
under 5 minutes and under 2 GB and run without the lock. Logs: $RUN_DIR/models-2/final-<UTC>/ (never overwritten).
A truncated run, a timeout or a missing summary line is a failure, never a pass.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
COMPLETION = HERE.parent.parent
REPO = COMPLETION.parent.parent
LOCKS = COMPLETION / "tools" / "locks.sh"
REGISTER = COMPLETION / "tools" / "register_run.py"
LANE = "models-2"
RUN_DIR = Path(os.environ["RUN_DIR"])
TARGET = RUN_DIR / "target" / "core-partition"
BIN = TARGET / "release" / "ivg-core-partition"
FAMILIES = ["reviewed", "as-built-isolation-stmt", "as-built-F1304", "as-built-F1305", "control-liveness-collapsed",
            "control-dropstatements-all-graphs"]
# registered unpartitioned counts of the original crate (evidence/runs/core-m1-*.json): the copy must reproduce them
REGISTERED = {"fidelity-m1-reviewed-a": 2849806, "fidelity-m1-reviewed-b": 1469036, "fidelity-m1-reviewed-c": 1369721,
              "fidelity-m1-as-built-isolation-stmt-a": 3257790, "fidelity-m1-as-built-isolation-stmt-b": 1720016,
              "fidelity-m1-as-built-isolation-stmt-c": 1398785}


def sources_sha256() -> str:
    h = hashlib.sha256()
    for p in sorted((HERE / "src").glob("*.rs")) + [HERE / "Cargo.toml", HERE / "Cargo.lock", Path(__file__)]:
        h.update(str(p.relative_to(HERE)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def rss(text: str):
    m = re.findall(r"Maximum resident set size \(kbytes\): (\d+)", text)
    return int(m[-1]) if m else None


def wall(text: str):
    m = re.findall(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([\d:.]+)", text)
    if not m:
        return None
    parts = [float(x) for x in m[-1].split(":")]
    return round(sum(p * 60 ** i for i, p in enumerate(reversed(parts))), 2)


def run(out: Path, tag: str, args: list[str], heavy: bool = False, timeout: int = 3000) -> dict:
    log = out / f"{tag}.log"
    cmd = ["/usr/bin/time", "-v", "timeout", str(timeout), str(BIN)] + args
    if heavy:
        cmd = ["bash", str(LOCKS), "heavy"] + cmd
    with open(log, "w") as f:
        rc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=dict(os.environ, CARGO_TARGET_DIR=str(TARGET))).returncode
    text = log.read_text(errors="replace")
    shown = " ".join((["locks.sh heavy"] if heavy else []) + ["timeout", str(timeout), "ivg-core-partition"] + args)
    return {"tag": tag, "rc": rc, "log": str(log), "command": shown, "max_rss_kb": rss(text), "wall_seconds": wall(text),
            "text": text}


def families(out: Path) -> dict:
    """The six (2, 2) family runs, in parallel, under one hold of the heavy lock."""
    script = ["set -u", f'B="{BIN}"', 'pids=""']
    for fam in FAMILIES:
        script.append(f'/usr/bin/time -v timeout 3000 "$B" --family {fam} 2 2 --out "{out}/family-{fam}.json" > "{out}/family-{fam}.log" 2>&1 & pids="$pids $!"')
    script += ["rc=0", "for p in $pids; do wait $p || rc=1; done", "exit $rc"]
    sh = out / "families.sh"
    sh.write_text("\n".join(script) + "\n")
    rc = subprocess.run(["bash", str(LOCKS), "heavy", "timeout", "3600", "bash", str(sh)]).returncode
    res = {}
    for fam in FAMILIES:
        log = out / f"family-{fam}.log"
        text = log.read_text(errors="replace") if log.exists() else ""
        js = out / f"family-{fam}.json"
        d = json.loads(js.read_text()) if js.exists() else None
        summ = [l for l in text.splitlines() if l.startswith("family ")]
        res[fam] = {"tag": f"family-{fam}", "log": str(log), "json": str(js), "summary": summ[-1] if summ else None,
                    "max_rss_kb": rss(text), "wall_seconds": wall(text), "data": d,
                    "command": f"locks.sh heavy timeout 3600 (parallel) ivg-core-partition --family {fam} 2 2 --out family-{fam}.json",
                    "ok": bool(d and d.get("met")) and "EVERY EXPECTATION MET" in (summ[-1] if summ else "")}
    res["_rc"] = rc
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--skip-full", action="store_true", help="skip the two unpartitioned (2, 2) runs")
    a = ap.parse_args()
    b = subprocess.run(["cargo", "build", "--release", "--offline"], cwd=HERE, capture_output=True, text=True,
                       env=dict(os.environ, CARGO_TARGET_DIR=str(TARGET)))
    if b.returncode != 0:
        print(b.stderr)
        return 1
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RUN_DIR / LANE / f"final-{stamp}"
    out.mkdir(parents=True)
    sha = sources_sha256()
    R: dict = {"crate": "experiment/playbook-completion/models/core-partition (ivg-core-partition)",
               "copied_from": "experiment/playbook-completion/models/core/src/m1.rs (sha256 5490e14e9b23a629fed054685a344709f1500f1cfc8f9a2b82679c70075428a2), util.rs (9ec651ccc610b168...)",
               "explorer_rev": "c03f9fa9be961610f2b274ffbb6a2c88d7d4d877", "product_pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e",
               "generated_utc": stamp, "sources_sha256": sha, "out_dir": "$RUN_DIR/" + str(out.relative_to(RUN_DIR)),
               "statement": "Every result is about the M1 model (bounded, explorer); none is a property of the product at pin 3eaa79cf.",
               "checks": {}}
    C = R["checks"]

    def small(tag, args, want_rc, want_text):
        r = run(out, tag, args)
        r["ok"] = r["rc"] == want_rc and all(w in r["text"] for w in want_text)
        lines = [l for l in r["text"].splitlines() if l.startswith(("coverage", "union", "profile"))]
        r["summary"] = lines
        r.pop("text")
        C[tag] = r
        print(f"{tag}: {'OK' if r['ok'] else 'FAILED'} rc={r['rc']} {lines[-1] if lines else ''}")

    small("coverage-keys", ["--coverage", "2", "2"], 0, ["coverage: PASS", "43 pre-enable worlds by search", "43 by the independent enumeration", "structural errors: 0"])
    small("coverage-keys-control", ["--coverage", "2", "2", "--broken-key"], 1, ["coverage (control: one piece key dropped): FAIL", "MISSING from the pieces"])
    for tag, args in [("union-a-reviewed", ["1", "2", "reviewed"]), ("union-b-reviewed", ["2", "1", "reviewed"]),
                      ("union-b-as-built", ["2", "1", "as-built"]), ("union-c-reviewed", ["0", "3", "reviewed"])]:
        small(tag, ["--union"] + args, 0, [": PASS"])
    small("union-control", ["--union", "2", "1", "reviewed", "--broken-key"], 1, ["(control: one piece dropped)", ": FAIL"])

    r = run(out, "fidelity", ["--only"] + list(REGISTERED))
    got = {m.group(1): int(m.group(2)) for m in re.finditer(r"^(fidelity-\S+)\s+\S+\s+MET \| (\d+) states", r["text"], re.M)}
    r["states"] = got
    r["registered_states"] = REGISTERED
    r["ok"] = r["rc"] == 0 and got == REGISTERED and "TRUNCATED" not in r["text"]
    r.pop("text")
    C["fidelity"] = r
    print(f"fidelity: {'OK' if r['ok'] else 'FAILED'} {got}")

    F = families(out)
    rc_f = F.pop("_rc")
    for fam, v in F.items():
        C[f"family-{fam}"] = v
        print(f"family-{fam}: {'OK' if v['ok'] else 'FAILED'} {v['summary']}")
    R["families_rc"] = rc_f

    if not a.skip_full:
        for tag, cid, fam in [("full-reviewed-22", "full-m1-reviewed-22", "reviewed"),
                              ("full-as-built-isolation-stmt-22", "full-m1-as-built-isolation-stmt-22", "as-built-isolation-stmt")]:
            free = subprocess.run(["free", "-g"], capture_output=True, text=True).stdout
            r = run(out, tag, ["--only", cid], heavy=True, timeout=3600)
            m = re.search(r"MET \| (\d+) states, (\d+) transitions, depth (\d+), exhaustive within bounds", r["text"])
            fam_states = (F.get(fam, {}).get("data") or {}).get("states_total")
            r["states"] = int(m.group(1)) if m else None
            r["transitions"] = int(m.group(2)) if m else None
            r["partition_states_total"] = fam_states
            r["free_before"] = free
            r["ok"] = r["rc"] == 0 and m is not None and r["states"] == fam_states
            r.pop("text")
            C[tag] = r
            print(f"{tag}: {'OK' if r['ok'] else 'FAILED'} states {r['states']} vs partition sum {fam_states}, rss {r['max_rss_kb']} kB")

    R["all_ok"] = all(v.get("ok") for v in C.values())
    for v in C.values():
        if v.get("data"):
            v["data"] = {k: v["data"][k] for k in v["data"] if k != "pieces"}  # per-piece rows stay in the family JSON
    (HERE / "RESULTS.json").write_text(json.dumps(R, indent=2) + "\n")
    print(f"models-2 core-partition: {'EVERY CHECK OK' if R['all_ok'] else 'SOME CHECK FAILED'} ({out})")

    if a.register:
        def reg(rid, kind, res, log, command, observes):
            subprocess.run([sys.executable, str(REGISTER), rid, kind, res, log, "--lane", LANE, "--command", command,
                            "--observes", observes, "--extra", f"sources_sha256={sha}"], cwd=REPO, check=True)
        for tag, v in C.items():
            if tag.startswith("family-"):
                fam = tag[len("family-"):]
                d = v["data"] or {}
                n, nv, npass = d.get("pieces_total"), d.get("with_violation"), d.get("without_violation")
                exhaust = f"{npass} pieces exhaustive-within-bounds with no violation" if npass else "no piece without a violation"
                obs = (f"M1 (2 pre-enable writes, 2 commits) partitioned by pre-enable world, family {fam}: {n} pieces, every "
                       f"piece met its stated expectation: {nv} with the expected violation, {exhaust}; {d.get('truncated')} truncated; "
                       f"states {d.get('states_total')} (largest piece {d.get('largest_piece_states')}), transitions {d.get('transitions_total')}, "
                       f"{d.get('seconds_total')} s, peak RSS {v['max_rss_kb']} kB; PARTITION invariant kept in every piece")
                if fam == "reviewed" or fam == "as-built-isolation-stmt":
                    res, kind = ("pass" if v["ok"] else "fail"), "mc"
                elif fam.startswith("control"):
                    res, kind = ("expected-violation" if v["ok"] else "fail"), "control"
                else:
                    res, kind = ("expected-violation" if v["ok"] else "fail"), "mc"
                reg(f"m2p-{fam}-22", kind, res, v["log"], v["command"], obs)
            elif tag.startswith("full-"):
                obs = (f"M1 unpartitioned (2 pre-enable writes, 2 commits), {tag}: {v['states']} states, {v['transitions']} transitions, "
                       f"exhaustive-within-bounds, no violation; equal to the partition's sum {v['partition_states_total']}; peak RSS "
                       f"{v['max_rss_kb']} kB, wall {v['wall_seconds']} s")
                reg(f"m2p-{tag}", "mc", "pass" if v["ok"] else "fail", v["log"], v["command"], obs)
            elif tag == "fidelity":
                reg("m2p-fidelity", "mc", "pass" if v["ok"] else "fail", v["log"], v["command"],
                    f"the copied M1 (piece mode off) reproduces the registered core-m1-reviewed-a/b/c and core-m1-as-built-isolation-stmt-a/b/c "
                    f"state counts exactly ({v['states']}), each exhaustive and met")
            else:
                kind = "control" if tag.endswith("control") else "check"
                res = ("expected-violation" if v["ok"] else "fail") if kind == "control" else ("pass" if v["ok"] else "fail")
                reg(f"m2p-{tag}", kind, res, v["log"], v["command"], " / ".join(v["summary"])[:1500])
    return 0 if R["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
