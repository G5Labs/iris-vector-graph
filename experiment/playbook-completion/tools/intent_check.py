#!/usr/bin/env python3
"""Gate 3.1-intent: every open human decision has independently recovered intent (playbook §3.1).

    python tools/intent_check.py              # check intent/HD-*.md against the 61-decision inventory
    python tools/intent_check.py --self-test  # seeded defects must each be caught

For every decision id of the starting inventory (matrix/obligations.json "decisions", from the original submission)
there must be exactly one intent/HD-NNNN.md with these sections, each non-empty:
  Sources, Contradictions, As built, Intended (or "Intended contract"), Working assumption, Alternatives,
  Discriminating check.
A section may say "None found." Sources must cite at least one location (path:line, a spec/ADR path, or a URL). As
built must cite a pin location
(path:line) or a registered run. A Discriminating check that names an intent-probe id (ia-/ib-/intent-a-/intent-b-)
must name an existing record in evidence/runs/; one that names no registered run must say why (the words "no probe", "not run", "inspection", "inspected" or "none").
Each decision must also appear in intent/lane-a.json or intent/lane-b.json. The check is structural: it shows the
recovery was done for every decision with sources and alternatives, not that the recovered intent is right.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = [("Sources",), ("Contradictions",), ("As built",), ("Intended",), ("Working assumption",),
            ("Alternatives",), ("Discriminating check",)]
LOC = re.compile(r"[\w./-]+\.(?:py|cls|md|json|toml|sql|mac|inc|yaml|yml|txt|sh|rs)(?::\d+)?|https?://\S+")
PIN_LOC = re.compile(r"[\w./-]+\.(?:py|cls|mac|inc|sql|md|toml|json|ya?ml)[:#]L?\d+")
TOKEN = re.compile(r"[A-Za-z][\w.-]*[\w]")
PROBE_ID = re.compile(r"^(?:(?:ia|ib)-HD\d{4}|intent-[ab]-hd\d{4})[\w.-]*$")
NO_RUN = re.compile(r"no probe|not run|not rerun|inspection|inspected|none|no run|not needed|source reading", re.I)


def sections(text: str) -> dict:
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def find(secs: dict, name: str):
    for k, v in secs.items():
        if k.lower().startswith(name.lower()):
            return v
    return None


def check(root: Path) -> list:
    problems = []
    inv = json.loads((root / "matrix" / "obligations.json").read_text())["decisions"]
    ids = sorted(d["id"] for d in inv)
    runs = {p.stem for p in (root / "evidence" / "runs").glob("*.json")}
    lanes = ""
    for f in ("lane-a.json", "lane-b.json"):
        p = root / "intent" / f
        lanes += p.read_text() if p.exists() else ""
    files = {p.stem: p for p in (root / "intent").glob("HD-*.md")}
    for extra in sorted(set(files) - set(ids)):
        problems.append(f"{extra}: intent file for no inventoried decision")
    for i in ids:
        p = files.get(i)
        if p is None:
            problems.append(f"{i}: no intent/{i}.md")
            continue
        secs = sections(p.read_text())
        for (name,) in REQUIRED:
            body = find(secs, name)
            if body is None:
                problems.append(f"{i}: section '{name}' missing")
            elif len(body) < 4:
                problems.append(f"{i}: section '{name}' is empty")
        src = find(secs, "Sources") or ""
        if src and not LOC.search(src):
            problems.append(f"{i}: Sources cites no location")
        ab = find(secs, "As built") or ""
        dc_runs = {x.rstrip(".,;:)") for x in TOKEN.findall(find(secs, "Discriminating check") or "")} & runs
        if ab and not PIN_LOC.search(ab) and not ({x.rstrip(".,;:)") for x in TOKEN.findall(ab)} & runs) and not dc_runs:
            problems.append(f"{i}: As built cites neither a pin location (path:line) nor a registered run "
                            f"(in As built or the Discriminating check)")
        dc = find(secs, "Discriminating check") or ""
        toks = {x.rstrip(".,;:)") for x in TOKEN.findall(dc)}
        real = sorted(toks & runs)
        dangling = sorted(x for x in toks if PROBE_ID.match(x) and x not in runs)
        for r in dangling:
            problems.append(f"{i}: Discriminating check names unregistered run {r}")
        if dc and not real and not dangling and not NO_RUN.search(dc):
            problems.append(f"{i}: Discriminating check names no registered run and gives no reason")
        if i not in lanes:
            problems.append(f"{i}: not listed in intent/lane-a.json or lane-b.json")
    return problems


def self_test() -> int:
    base = check(ROOT)
    if base:
        print("self-test needs a clean baseline; baseline problems:", len(base))
        return 1
    seeded = {
        "missing file": lambda r: (r / "intent" / "HD-0101.md").unlink(),
        "missing section": lambda r: _edit(r / "intent" / "HD-0702.md", "## Alternatives", "## Removed heading"),
        "empty sources": lambda r: _blank(r / "intent" / "HD-1201.md", "Sources"),
        "dangling run": lambda r: _append(r / "intent" / "HD-1401.md", "Discriminating check",
                                          "registry `ib-HD9999-does-not-exist`"),
        "unlisted decision": lambda r: _edit(r / "intent" / "lane-a.json", "HD-0001", "HD-X001"),
        "extra file": lambda r: (r / "intent" / "HD-9999.md").write_text("# HD-9999\n"),
    }
    failed = 0
    for name, mutate in seeded.items():
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp) / "c"
            r.mkdir()
            for sub in ("intent", "matrix", "evidence"):
                shutil.copytree(ROOT / sub, r / sub)
            mutate(r)
            got = check(r)
            ok = bool(got)
            failed += not ok
            print(f"{'caught' if ok else 'MISSED'}: {name} ({len(got)} problem(s))")
    print("self-test", "pass" if not failed else "FAIL")
    return 1 if failed else 0


def _edit(p: Path, a: str, b: str):
    t = p.read_text()
    assert a in t, (p, a)
    p.write_text(t.replace(a, b))


def _blank(p: Path, sec: str):
    lines, out, skip = p.read_text().splitlines(), [], False
    for line in lines:
        if line.startswith("## "):
            skip = line[3:].strip().startswith(sec)
            out.append(line)
            continue
        if not skip:
            out.append(line)
    p.write_text("\n".join(out) + "\n")


def _append(p: Path, sec: str, text: str):
    lines, out, done = p.read_text().splitlines(), [], False
    for line in lines:
        out.append(line)
        if line.startswith("## ") and line[3:].strip().startswith(sec) and not done:
            out.append(text)
            done = True
    p.write_text("\n".join(out) + "\n")


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    problems = check(ROOT)
    n = len(json.loads((ROOT / "matrix" / "obligations.json").read_text())["decisions"])
    for p in problems:
        print("  ", p)
    print(f"intent check: {n} decisions, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
