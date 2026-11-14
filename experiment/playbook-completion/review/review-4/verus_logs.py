#!/usr/bin/env python3
"""Review 4: compare each in-scope Verus run record (kind proof/control) with its log and JSON log.

For each record: error diagnostics in the log (an `error:` line other than `could not compile`, and the first
`--> file:line` after it), the "due to N previous errors" count, whether the log itself carries a verified count,
the JSON log's verification-results (verified, errors), and what the record's observes text claims.
"""
import hashlib, json, os, re, sys
from pathlib import Path
run_dir = Path(os.environ["RUN_DIR"])
repo = Path(sys.argv[1]); lst = Path(sys.argv[2])
rows = []
for rel in lst.read_text().split():
    rec = json.loads((repo / rel).read_text())
    if rec["kind"] not in ("proof", "control"):
        continue
    log = Path(rec["log"].replace("$RUN_DIR", str(run_dir)))
    text = log.read_text(errors="replace")
    lines = text.splitlines()
    errs = []
    for i, l in enumerate(lines):
        if l.startswith("error") and "could not compile" not in l:
            loc = None
            for j in range(i + 1, min(i + 6, len(lines))):
                m = re.match(r"\s*--> (\S+):(\d+):\d+", lines[j])
                if m:
                    loc = f"{m.group(1)}:{m.group(2)}"; break
            errs.append((l.strip()[:60], loc))
    m = re.search(r"due to (\d+) previous errors?", text)
    prev = int(m.group(1)) if m else 0
    m2 = re.search(r"verification results:: (\d+) verified, (\d+) errors", text)
    summ = re.search(r"(\d+) verified, (\d+) errors?", text)
    row = {"id": rec["id"], "result": rec["result"], "rec_verified": rec.get("verified"), "rec_errors": rec.get("errors"),
           "rec_locs": rec.get("error_locations", ""), "log_err_diags": len(errs), "log_prev": prev,
           "log_locs": sorted({e[1] for e in errs if e[1]}), "log_has_count": bool(m2 or summ),
           "log_tail": lines[-1] if lines else "", "observes": rec["observes"]}
    if "json_log" in rec:
        jp = Path(rec["json_log"].replace("$RUN_DIR", str(run_dir)))
        if jp.exists():
            try:
                jd = json.loads(jp.read_text())
                vr = jd.get("verification-results", {})
                row["json_verified"], row["json_errors"] = vr.get("verified"), vr.get("errors")
            except Exception as e:
                row["json_verified"] = f"unparsable {e}"
            jh = hashlib.sha256(jp.read_bytes()).hexdigest()
            row["json_sha_match"] = (rec.get("json_sha256") == jh) if rec.get("json_sha256") else "no json_sha256 in record"
            row["json_pinned_in_log"] = jh in text
        else:
            row["json_verified"] = "MISSING"
    # claims in observes
    o = rec["observes"]
    mv = re.search(r"(\d+) verified, (\d+) errors", o)
    if mv: row["obs_verified"], row["obs_errors"] = int(mv.group(1)), int(mv.group(2))
    me = re.search(r"(\d+) errors?, all in (\S+?)[:;,]? ", o)
    if me: row["obs_errors"], row["obs_file"] = int(me.group(1)), me.group(2).rstrip(':')
    row["obs_locs"] = sorted(set(re.findall(r"(src/[\w/]+\.rs:\d+)", o)))
    rows.append(row)
json.dump(rows, sys.stdout, indent=1)
