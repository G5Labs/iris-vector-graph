#!/usr/bin/env python3
"""Review 4 (semantics slice): compare each sem-* run record's observes text with its family log.

Parses the check lines of $RUN_DIR/semantics/r1/<family>.log and recomputes, per record kind, the counts, max states,
laws, control->law pairs and passing instance names that the observes text states. Prints one line per record.
"""
import json, os, re, sys
from pathlib import Path
RUN = Path(os.environ["RUN_DIR"]); REPO = Path(sys.argv[1])
LINE = re.compile(r"^(\S+)\s+(as-built|reviewed|control|exception)\s+(safety|progress|liveness|sharpness)\s+expect (exhaustive pass|violation of '(.*?)')\s+-> (MET|NOT MET) \| (\d+) states, (\d+) transitions, depth (\d+), (\w+), [\d.]+s(?: \| found '(.*)')?$")
def parse(log):
    out = []
    for l in log.read_text().splitlines():
        m = LINE.match(l)
        if m:
            out.append(dict(id=m[1], design=m[2], kind=m[3], expect=m[5], met=m[6] == "MET", states=int(m[7]),
                            exh=m[10], found=m[11] or ""))
    return out
res = []
for f in sorted((REPO / "experiment/playbook-completion/evidence/runs").glob("sem-*.json")):
    r = json.loads(f.read_text()); o = r["observes"]; rid = r["id"]
    if rid in ("sem-check", "sem-check-selftest"):
        continue
    log = Path(r["log"].replace("$RUN_DIR", str(RUN))); L = parse(log)
    fam = rid.split("-")[2] if rid != "sem-mc-all" else "all"
    probs = []
    if any(not x["met"] for x in L): probs.append("NOT MET lines")
    if any(x["exh"] != "exhaustive" for x in L): probs.append("non-exhaustive lines")
    if rid.endswith("-as-built"):
        S = [x for x in L if x["design"] in ("as-built", "exception")]
        n = len(S); v = [x for x in S if x["expect"]]; mx = max(x["states"] for x in S)
        m = re.search(r"(\d+) of (\d+) (?:checks )?met", o); 
        if not m or int(m[1]) != n or int(m[2]) != n: probs.append(f"count: log {n}, obs {m[0] if m else None}")
        m = re.search(r"\(max (\d+) states\)", o)
        if not m or int(m[1]) != mx: probs.append(f"max states: log {mx}, obs {m[1] if m else None}")
        m = re.search(r"(\d+) expected violations", o)
        if not m or int(m[1]) != len(v): probs.append(f"violations: log {len(v)}, obs {m[1] if m else None}")
        laws = sorted({x["expect"] for x in v})
        for law in laws:
            if law not in o: probs.append(f"law not named in obs: {law}")
        for law in re.findall(r"((?:M\d\d|AX)-L?\d+[^;)]*)", o):
            pass
        passing = [x["id"] for x in S if not x["expect"]]
        m = re.search(r"(\d+) as-built instance\(s\) pass every law \(([^)]*)\)", o)
        if m and int(m[1]) != len(passing): probs.append(f"passing: log {passing}, obs {m[0]}")
        if m:
            names = [s.strip() for s in m[2].split(",")] if m[2] != "none" else []
            for nm in names:
                if not any(nm in p for p in passing): probs.append(f"pass name {nm} not in log {passing}")
        extra = {"n": n, "viol": len(v), "max": mx, "laws": laws, "passing": passing}
    elif rid.endswith("-reviewed"):
        S = [x for x in L if x["design"] == "reviewed"]
        n = len(S); sh = [x for x in S if x["kind"] == "sharpness"]; mx = max(x["states"] for x in S)
        m = re.search(r"(\d+) of (\d+) (?:checks )?met", o)
        if not m or int(m[1]) != n or int(m[2]) != n: probs.append(f"count: log {n}, obs {m[0] if m else None}")
        m = re.search(r"\(max (\d+) states\)", o)
        if not m or int(m[1]) != mx: probs.append(f"max states: log {mx}, obs {m[1] if m else None}")
        m = re.search(r"(\d+) sharpness witness", o)
        if not m or int(m[1]) != len(sh): probs.append(f"sharpness: log {len(sh)}, obs {m[1] if m else None}")
        nonsh = [x for x in S if x["kind"] != "sharpness"]
        if any(x["expect"] for x in nonsh): probs.append("reviewed non-sharpness expecting violation")
        m = re.search(r"(\d+) reviewed check\(s\) pass", o)
        if not m or int(m[1]) != len(nonsh): probs.append(f"reviewed passing: log {len(nonsh)}, obs {m[1] if m else None}")
        extra = {"n": n, "sharp": len(sh), "max": mx, "nonsharp": len(nonsh)}
    elif rid.startswith("sem-control-"):
        S = [x for x in L if x["design"] == "control"]
        n = len(S)
        m = re.search(r"(\d+) of (\d+) generic mutants caught", o)
        if not m or int(m[1]) != n or int(m[2]) != n: probs.append(f"count: log {n}, obs {m[0] if m else None}")
        pairs = re.findall(r"([\w-]+-control-[\w-]+) -> ((?:M\d\d-L\d+|AX-\d+))", o)
        logmap = {x["id"]: x["found"] for x in S}
        for cid, law in pairs:
            if cid not in logmap: probs.append(f"control {cid} not in log")
            elif not logmap[cid].startswith(law + " "): probs.append(f"{cid}: obs {law}, log found '{logmap[cid]}'")
        if len(pairs) != n: probs.append(f"pairs in obs {len(pairs)} vs log controls {n}")
        extra = {"n": n}
    else:  # sem-mc-all
        d = {}
        for x in L: d[x["design"]] = d.get(x["design"], 0) + 1
        mx = max(x["states"] for x in L)
        extra = {"by_design": d, "total": len(L), "max": mx}
    res.append((rid, "MATCH" if not probs else "CHECK", probs, extra))
for rid, v, p, e in res:
    print(rid, v, "; ".join(p), json.dumps(e))
