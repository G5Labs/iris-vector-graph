#!/usr/bin/env python3
"""Line coverage of the traced runs: INT-line counts of the IRIS line monitor mapped to .cls lines (§3.5).

    python coverage.py INT_DIR RUN_DIR... --json OUT [--checked NAME,...]

INT_DIR holds the INT text of each class routine (<Class>.<n>.int, from ^ROUTINE at the pin's deployed AUDITC).
Each RUN_DIR holds monitor.json (counts per INT line) from one scenario. Mapping: see map_class (alignment of a
method's non-blank .cls lines with its INT segment; unmapped lines are reported). A .cls line counts as exercised when its INT
line has a count > 0 in any of the given runs. Executable lines are cls_lines.executable(). The report lists, per
handler (method), the executable lines no run exercised: the unchecked lines.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cls_lines  # noqa: E402

LABEL = re.compile(r"^([%\w]+)\(")


def norm(s: str) -> str:
    t = s.strip()
    if t.startswith(";---"):   # the INT keeps an embedded SQL statement as a ";---" comment copy of its source lines
        t = t[4:].strip()
    t = re.sub(r"\s+", " ", t)
    if t.endswith(" }") and t != "}":
        t = t[:-2].rstrip()        # the INT folds a method's closing brace into its last line
    return t


def int_methods(int_lines):
    """{method: (label_index, next_label_index)} (0-based)."""
    idx = [(i, m.group(1)) for i, ln in enumerate(int_lines) for m in [LABEL.match(ln)] if m]
    out = {}
    for k, (i, name) in enumerate(idx):
        nxt = idx[k + 1][0] if k + 1 < len(idx) else len(int_lines)
        out.setdefault(name, (i, nxt))
    return out


def map_class(cls: str, int_dir: Path):
    """{cls_line: (routine, int_line_1based)} and alignment notes.

    Per method: the .cls body lines that are not blank (the INT drops blank lines and keeps comments) are aligned
    with the INT lines between the method's label and the next label: difflib matching blocks on whitespace-
    normalized text, then every gap between two anchors with as many .cls lines as INT lines is mapped line by line
    (macro expansion and embedded SQL change a line's text, not the line count). Lines left over are reported."""
    cls_text = cls_lines.class_file(cls).read_text().split("\n")
    mapping, notes = {}, []
    ints = {f.name[:-4]: f.read_text().split("\n") for f in sorted(int_dir.glob(f"{cls}.*.int"))}
    labels = {rtn: int_methods(lines) for rtn, lines in ints.items()}
    for m in cls_lines.methods(cls):
        name = m["method"]
        where = [(rtn, labels[rtn][nm]) for nm in (name, f"z{name}Execute") for rtn in ints if nm in labels[rtn]]
        if not where:
            notes.append({"method": name, "note": "no INT label in the class routine"})
            continue
        rtn, (li, nxt) = where[0]
        lines = ints[rtn]
        body = [n for n in range(m["open"] + 1, m["close"]) if cls_text[n - 1].strip()]
        seg, after_sql = [], False                # 0-based INT indexes of the lines that come from the .cls text
        for j in range(li + 1, nxt):
            t = lines[j].strip()
            if not t or t.startswith(";--- **"):
                continue
            if t.startswith(";---"):
                after_sql = True
                seg.append(j)
                continue
            if after_sql:                          # the code generated for the embedded SQL statement above
                after_sql = False
                continue
            seg.append(j)
        if seg and lines[seg[-1]].strip() == "}":   # the method's closing brace on a line of its own
            seg.pop()
        a = [norm(cls_text[n - 1]) for n in body]
        b = [norm(lines[j]) for j in seg]
        sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
        blocks = sm.get_matching_blocks()
        pa = pb = 0
        exact = gap = 0
        for (ai, bi, size) in blocks:
            if ai - pa == bi - pb:
                for t in range(ai - pa):
                    mapping[body[pa + t]] = (rtn, seg[pb + t] + 1)
                    gap += 1
            for t in range(size):
                mapping[body[ai + t]] = (rtn, seg[bi + t] + 1)
                exact += 1
            pa, pb = ai + size, bi + size
        # an embedded SQL statement's code is the first INT line after its ";---" comment block
        for n in m["executable"]:
            if "&sql(" in cls_text[n - 1] and n in mapping:
                j = mapping[n][1] - 1           # 0-based index of the comment copy's first line
                k = j + 1
                while k < nxt and (lines[k].strip().startswith(";---") or not lines[k].strip()):
                    k += 1
                if k < nxt and lines[k].strip().startswith(";---") is False:
                    mapping[n] = (rtn, k + 1)
        unmapped = [n for n in m["executable"] if n not in mapping]
        if unmapped or gap:
            notes.append({"method": name, "routine": rtn, "exact": exact, "gap_mapped": gap,
                          "unmapped_executable": unmapped})
    return mapping, notes


def main() -> int:
    int_dir = Path(sys.argv[1])
    runs = [Path(a) for a in sys.argv[2:] if not a.startswith("--") and a != sys.argv[sys.argv.index("--json") + 1]]
    out = Path(sys.argv[sys.argv.index("--json") + 1])
    counts = {}
    for r in runs:
        counts[r.name] = json.loads((r / "monitor.json").read_text())
    classes = sorted({f.name.rsplit(".", 2)[0] for f in int_dir.glob("*.int")})
    report = {"runs": [r.name for r in runs], "classes": {}}
    for cls in classes:
        try:
            ms = cls_lines.methods(cls)
        except FileNotFoundError:
            continue
        mapping, notes = map_class(cls, int_dir)
        per = []
        for m in ms:
            ex = m["executable"]
            hit_by = {}
            unmapped = []
            for n in ex:
                if n not in mapping:
                    unmapped.append(n)
                    continue
                rtn, il = mapping[n]
                hit_by[n] = [rn for rn, c in counts.items() if il - 1 < len(c.get(rtn, [])) and c[rtn][il - 1] > 0]
            unexercised = [n for n in ex if n in hit_by and not hit_by[n]]
            per.append({"method": m["method"], "lines": f"{m['open']}-{m['close']}", "executable": len(ex),
                        "exercised": sum(1 for n in ex if hit_by.get(n)), "unexercised": unexercised,
                        "unmapped": unmapped, "by_run": {rn: sum(1 for n in ex if rn in hit_by.get(n, [])) for rn in counts}})
        report["classes"][cls] = {"methods": per, "alignment_notes": notes,
                                  "executable": sum(p["executable"] for p in per),
                                  "exercised": sum(p["exercised"] for p in per)}
    out.write_text(json.dumps(report, indent=1))
    for cls, v in report["classes"].items():
        print(f"{cls}: {v['exercised']}/{v['executable']} executable lines exercised")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
