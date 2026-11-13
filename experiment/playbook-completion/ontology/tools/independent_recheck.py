#!/usr/bin/env python3
"""Independent recheck of the repaired ontology. Shares no code with ontology_check.py or repair.py.

    python3 experiment/playbook-completion/ontology/tools/independent_recheck.py

1. The literal term-scope rule on the raw markdown of experiment/playbook-completion/ontology: for every module
   glossary row (Defined by plus Restated by), every statement whose text matches the term must have a definer that
   is the statement, an ancestor, or an earlier row with the same parent, and must not come before the primary.
   Run with the pattern of check-literal-scope.py and with a y/ies + hyphen/space superset. Expect 0 and 0.
2. Each restatement: kind D, same module, text equal to the primary's, Notes "Same meaning as <primary>", after it.
3. Preservation: every row of experiment/playbook-uplift/ontology is present with the same id, kind, evidence,
   source and notes, in the same relative order; parent and text differ only where repairs.json says so; the file
   text outside the Glossary and Statements tables (cells included) is unchanged.
Exit 0 only if all three hold.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
NEW = ROOT / "experiment" / "playbook-completion" / "ontology"
OLD = ROOT / "experiment" / "playbook-uplift" / "ontology"


def cells(line):
    return [x.strip().replace("\\|", "|") for x in re.split(r"(?<!\\)\|", line)[1:-1]]


def table(lines, heading):
    i = next(k for k, l in enumerate(lines) if l.strip() == heading)
    while not lines[i].startswith("|"):
        i += 1
    i += 2
    out = []
    while i < len(lines) and lines[i].startswith("|"):
        out.append(cells(lines[i]))
        i += 1
    return out


def literal(t):
    return re.compile(r"(?<![A-Za-z0-9-])" + re.escape(t).replace(r"\ ", r"[\s-]+") + r"(?:s|es)?(?![A-Za-z0-9-])",
                      re.I)


def superset(t):
    w = re.split(r"[\s-]+", t)
    last = w[-1]
    tail = (re.escape(last[:-1]) + r"(?:y(?:s|es)?|ies)") if re.search(r"[^aeiou]y$", last) else \
        re.escape(last) + r"(?:s|es)?"
    return re.compile(r"(?<![A-Za-z0-9-])" + r"[\s-]+".join([re.escape(x) for x in w[:-1]] + [tail])
                      + r"(?![A-Za-z0-9-])", re.I)


def main():
    mods, every = [], {}
    for f in sorted(NEW.glob("[0-9][0-9]-*.md")):
        lines = f.read_text(encoding="utf-8").split("\n")
        g, st = table(lines, "## Glossary"), table(lines, "## Statements")
        mods.append((f.name, g, st))
        for k, r in enumerate(st):
            every[r[0]] = (f.name, k, r)
    out_of_scope = {"literal": set(), "superset": set()}
    problems = []
    for name, g, st in mods:
        pos = {r[0]: k for k, r in enumerate(st)}
        for row in g:
            term, prim = row[0].lower(), row[1]
            rest = [x for x in re.split(r"[ ,]+", row[2]) if x] if len(row) > 2 else []
            if prim not in pos:
                problems.append(f"{name}: '{term}' primary {prim} not in this module")
                continue
            p = every[prim][2]
            for x in rest:
                if x not in pos:
                    problems.append(f"{name}: restatement {x} not in this module")
                    continue
                r = every[x][2]
                if r[2] != "D" or r[3] != p[3] or f"Same meaning as {prim}" not in r[6] or pos[x] <= pos[prim]:
                    problems.append(f"{name}: restatement {x} of {prim} is malformed")
            defs = {prim, *rest}
            for mode, make in (("literal", literal), ("superset", superset)):
                pat = make(term)
                for k, r in enumerate(st):
                    if not pat.search(r[3]):
                        continue
                    scope = {r[0]} | {s[0] for s in st[:k] if s[1] == r[1]}
                    n, seen = r, set()
                    while n[1] in every and n[1] not in seen:
                        seen.add(n[1])
                        n = every[n[1]][2]
                        scope.add(n[0])
                    if not defs & scope or pos[prim] > k:
                        out_of_scope[mode].add((r[0], term))
    print(f"literal rule on the repaired modules: {len(out_of_scope['literal'])} pairs out of scope with the "
          f"check-literal-scope.py pattern, {len(out_of_scope['superset'])} with the superset pattern; "
          f"{len(problems)} restatement problem(s); {len(every)} statements")
    for p in problems[:20]:
        print("  ", p)
    rep = json.loads((NEW / "repairs.json").read_text(encoding="utf-8"))["statements"]
    moved = {k for k, v in rep.items() if "reparent" in v["change"]}
    reworded = {k for k, v in rep.items() if "reword" in v["change"]}
    added = {k for k, v in rep.items() if v["change"].startswith("added")}
    n, bad = 0, []
    for f in sorted(OLD.glob("[0-9][0-9]-*.md")):
        a = {r[0]: r for r in table(f.read_text(encoding="utf-8").split("\n"), "## Statements")}
        new_lines = (NEW / f.name).read_text(encoding="utf-8").split("\n")
        bst = table(new_lines, "## Statements")
        b = {r[0]: r for r in bst}
        for k, r in a.items():
            n += 1
            d = b.get(k)
            if d is None:
                bad.append(f"{k} missing")
                continue
            if [r[0], r[2], r[4], r[5], r[6]] != [d[0], d[2], d[4], d[5], d[6]]:
                bad.append(f"{k}: id/kind/evidence/source/notes changed")
            if (r[1] != d[1]) != (k in moved) or (r[1] != d[1] and rep[k]["old_parent"] != r[1]):
                bad.append(f"{k}: parent change not as recorded")
            if (r[3] != d[3]) != (k in reworded) or (r[3] != d[3] and rep[k]["old_text"] != r[3]):
                bad.append(f"{k}: text change not as recorded")
        if [r[0] for r in bst if r[0] in a] != list(a):
            bad.append(f"{f.name}: original rows reordered")
        extra = {r[0] for r in bst} - set(a)
        if not extra <= added:
            bad.append(f"{f.name}: unrecorded new rows {sorted(extra - added)[:5]}")
        keep = lambda t: [l for l in t.split("\n") if not l.startswith("|")]
        cell_part = lambda t: t.split("## Cells")[1] if "## Cells" in t else ""
        old_text, new_text = f.read_text(encoding="utf-8"), "\n".join(new_lines)
        if keep(old_text) != keep(new_text) or cell_part(old_text) != cell_part(new_text):
            bad.append(f"{f.name}: text outside the glossary and statements tables changed")
    print(f"preservation: {n} original statements checked; {len(bad)} problem(s); recorded changes: "
          f"{len(moved)} reparented, {len(reworded)} reworded, {len(added)} added")
    for p in bad[:20]:
        print("  ", p)
    if len(mods) != 19 or n != 3015 or not every:
        bad.append(f"vacuous input: {len(mods)} modules, {n} original statements")
    ok = not out_of_scope["literal"] and not out_of_scope["superset"] and not problems and not bad
    print("independent recheck:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
