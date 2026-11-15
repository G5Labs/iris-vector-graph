#!/usr/bin/env python3
"""Independent recheck of the repaired ontology. Shares no code with ontology_check.py or repair.py.

    python3 experiment/playbook-completion/ontology/tools/independent_recheck.py

1. The literal term-scope rule on the raw markdown of experiment/playbook-completion/ontology: for every module
   glossary row (Defined by plus Restated by), every statement whose text matches the term must have a definer that
   is the statement, an ancestor, or an earlier row with the same parent, and must not come before the primary.
   Run with the pattern of check-literal-scope.py and with a y/ies + hyphen/space superset. Expect 0 and 0.
2. Each restatement: kind D, same module, text equal to the primary's, Notes "Same meaning as <primary>", after it.
3. Preservation: every row of experiment/playbook-uplift/ontology is present with the same id, kind and source, in
   the same relative order; parent and text differ only where repairs.json says so; evidence is the original
   evidence plus exactly the items evidence-additions.json lists, with [model-only] only where it lists it; notes
   are unchanged or as evidence-additions.json lists; the file text outside the Glossary and Statements tables
   (cells included) is unchanged. The only other rows, entity lines and cells are the coverage additions that
   evidence-additions.json lists under `coverage_additions` (ontology-2 lane, applied by add_coverage.py): each
   listed statement row is present exactly as recorded, and removing the listed scope addenda, entity lines and
   cell rows gives back the original text outside the tables and the original Cells section.
4. Evidence (review R-05), re-derived from the raw audit and registry files: a statement citing a finding whose
   audit disposition is reproduced-live, reproduced-test or confirmed-source, or intent-undecided with live, run or
   trace evidence (review R2-08), has [model-only] on every proved:/mc: item; every restatement's evidence equals
   its primary's; every finding id and C- run reference resolves (a C- reference needs a record of the same kind with
   result pass); no statement that a reproduced finding's `intended` text names carries proved: without citing that
   finding (review R2-03).
Exit 0 only if all four hold.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
COMP = ROOT / "experiment" / "playbook-completion"
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


def audit_findings(full=False):
    out = {}
    for p in sorted((COMP / "findings" / "audit").glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("findings", []) + data.get("new_findings", [])
        for f in items:
            out[f["id"]] = f if full else f.get("disposition")
    return out


def about_product(f):
    """Written apart from ontology_check.observed_on_product: product dispositions, or intent-undecided with a live,
    run or trace evidence item."""
    if f is None:
        return False
    d = f.get("disposition")
    if d in ("reproduced-live", "reproduced-test", "confirmed-source"):
        return True
    kinds = [e.get("kind") for e in (f.get("evidence") or []) if isinstance(e, dict)]
    return d == "intent-undecided" and bool({"live", "run", "trace"} & set(kinds))


def evidence_checks(mods, every):
    disp = audit_findings()
    full = audit_findings(full=True)
    original = set()
    old = ROOT / "experiment" / "playbook-uplift"
    for p in [old / "FINDINGS.md", *sorted((old / "findings").glob("*.md"))]:
        if p.exists():
            original |= set(re.findall(r"^#{2,4}\s+(F-\d+[a-z]?)\b", p.read_text(encoding="utf-8"), re.M))
    runs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (COMP / "evidence" / "runs").glob("*.json")}
    want = {"mc": "mc", "live": "live", "trace": "trace", "run": "run", "proved": "proof"}
    out = []
    for name, g, st in mods:
        for row in g:
            for x in [y for y in re.split(r"[ ,]+", row[2]) if y] if len(row) > 2 else []:
                if every[x][2][4] != every[row[1]][2][4]:
                    out.append(f"{x}: restatement evidence differs from {row[1]}")
        for r in st:
            items = [x.strip() for x in r[4].split(";") if x.strip()]
            fids = [x[8:] for x in items if x.startswith("finding:")]
            for f in fids:
                if f not in disp and f not in original:
                    out.append(f"{r[0]}: finding {f} resolves nowhere")
            product = [f for f in fids if about_product(full.get(f))]
            for x in items:
                kind = x.split(":")[0]
                if product and kind in ("proved", "mc") and not x.endswith(" [model-only]"):
                    out.append(f"{r[0]}: {x} beside {product} lacks [model-only]")
                m = re.match(r"^(mc|live|trace|run|proved):C-([^ ]+)", x)
                if m and m.group(1) != "proved":
                    rec = runs.get(m.group(2))
                    if not rec or rec.get("kind") != want[m.group(1)] or rec.get("result") != "pass":
                        out.append(f"{r[0]}: {x} has no passing {want[m.group(1)]} record")
    # review R2-03: a reproduced finding's intended text names a statement with proved: that does not cite it
    rows = {r[0]: r for _, _, st in mods for r in st}
    for fid, f in sorted(full.items()):
        if f.get("disposition") not in ("reproduced-live", "reproduced-test", "reproduced-model", "confirmed-source"):
            continue
        for sid in re.findall(r"\b([A-Z]{2,4}-[A-Z]*[0-9]+(?:\.[0-9]+)*[a-z]?)(?![A-Za-z0-9])", str(f.get("intended", ""))):
            r = rows.get(sid)
            if r is None:
                continue
            items = [x.strip() for x in r[4].split(";") if x.strip()]
            if any(x.startswith("proved:") for x in items) and f"finding:{fid}" not in [
                    re.sub(r" \[model-only\]$", "", x) for x in items]:
                out.append(f"{sid}: proved: item, named by {fid}'s intended text, without finding:{fid}")
    return out


def main():
    global NEW
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ontology", type=Path, help="check a scratch copy of the modules instead (read only)")
    ap.add_argument("--coverage-spec", type=Path,
                    help="add this file's statements/cells/scope_addenda to the recorded coverage additions")
    a = ap.parse_args()
    ont_dir = NEW
    if a.ontology:
        NEW = a.ontology.resolve()
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
    ev_problems = evidence_checks(mods, every)
    print(f"evidence: {len(ev_problems)} problem(s) (model-only rule, restatement evidence, finding and C- run "
          f"references)")
    for p in ev_problems[:20]:
        print("  ", p)
    problems += ev_problems
    adds = json.loads((ont_dir / "evidence-additions.json").read_text(encoding="utf-8"))
    rep = json.loads((ont_dir / "repairs.json").read_text(encoding="utf-8"))["statements"]
    if a.coverage_spec:
        extra = json.loads(a.coverage_spec.read_text(encoding="utf-8"))
        extra = extra.get("coverage_additions", extra)
        cov0 = adds.setdefault("coverage_additions", {})
        for k in ("statements", "cells", "scope_addenda"):
            cov0[k] = cov0.get(k, []) + extra.get(k, [])
    moved = {k for k, v in rep.items() if "reparent" in v["change"]}
    reworded = {k for k, v in rep.items() if "reword" in v["change"]}
    added = {k for k, v in rep.items() if v["change"].startswith("added")}
    cov = adds.get("coverage_additions", {})
    cov_rows, cov_lines = {}, {}
    for x in cov.get("statements", []):
        cov_rows.setdefault(x["file"], {})[x["row"][0]] = [c.strip() for c in x["row"]]
    for x in cov.get("scope_addenda", []):
        cov_lines.setdefault(x["file"], {"entity": [], "rows": []})["entity"].append(x["line"])
    for x in cov.get("cells", []):
        lst = cov_lines.setdefault(x["file"], {"entity": [], "rows": []})
        if x.get("entity_line"):
            lst["entity"].append(x["entity_line"])
        lst["rows"] += [[c.strip() for c in r] for r in x.get("rows", [])]

    def drop_recorded(text, name):
        """The file text with the recorded entity lines and cell rows removed (each once)."""
        rec = cov_lines.get(name, {"entity": [], "rows": []})
        ent, rows, out = list(rec["entity"]), [list(r) for r in rec["rows"]], []
        for l in text.split("\n"):
            if l in ent:
                ent.remove(l)
                continue
            if l.startswith("|") and cells(l) in rows:
                rows.remove(cells(l))
                continue
            out.append(l)
        return "\n".join(out), ent + rows

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
            if [r[0], r[2], r[5]] != [d[0], d[2], d[5]]:
                bad.append(f"{k}: id/kind/source changed")
            old_items = [x.strip() for x in r[4].split(";") if x.strip()]
            new_items = [x.strip() for x in d[4].split(";") if x.strip()]
            qualified = set(adds["model_only"].get(k, {}).get("items", []))
            base = [re.sub(r" \[model-only\]$", "", x) for x in new_items[:len(old_items)]]
            appended = new_items[len(old_items):]
            listed = [f"finding:{f}" for f in adds["findings"].get(k, {})] + adds["runs"].get(k, [])
            if base != old_items:
                bad.append(f"{k}: original evidence items changed")
            if sorted(re.sub(r" \[model-only\]$", "", x) for x in appended) != sorted(
                    x for x in listed if x not in old_items):
                bad.append(f"{k}: added evidence differs from evidence-additions.json")
            for x in new_items:
                if x.endswith("[model-only]") and re.sub(r" \[model-only\]$", "", x) not in qualified:
                    bad.append(f"{k}: unrecorded [model-only] on {x}")
            if r[6] != d[6] and adds["notes"].get(k, {}).get("new") != d[6]:
                bad.append(f"{k}: notes changed without a record")
            if (r[1] != d[1]) != (k in moved) or (r[1] != d[1] and rep[k]["old_parent"] != r[1]):
                bad.append(f"{k}: parent change not as recorded")
            if (r[3] != d[3]) != (k in reworded) or (r[3] != d[3] and rep[k]["old_text"] != r[3]):
                bad.append(f"{k}: text change not as recorded")
        if [r[0] for r in bst if r[0] in a] != list(a):
            bad.append(f"{f.name}: original rows reordered")
        extra = {r[0] for r in bst} - set(a)
        mine = cov_rows.get(f.name, {})
        if not extra <= added | set(mine):
            bad.append(f"{f.name}: unrecorded new rows {sorted(extra - added - set(mine))[:5]}")
        for rid, row in mine.items():
            if b.get(rid) != row:
                bad.append(f"{f.name}: coverage addition {rid} missing or not as recorded")
        keep = lambda t: [l for l in t.split("\n") if not l.startswith("|")]
        cell_part = lambda t: t.split("## Cells")[1] if "## Cells" in t else ""
        old_text = f.read_text(encoding="utf-8")
        new_text, unmatched = drop_recorded("\n".join(new_lines), f.name)
        if unmatched:
            bad.append(f"{f.name}: recorded entity lines or cells not present: {unmatched[:3]}")
        if keep(old_text) != keep(new_text) or cell_part(old_text) != cell_part(new_text):
            bad.append(f"{f.name}: text outside the glossary and statements tables changed")
    print(f"preservation: {n} original statements checked; {len(bad)} problem(s); recorded changes: "
          f"{len(moved)} reparented, {len(reworded)} reworded, {len(added)} added; coverage additions: "
          f"{sum(len(v) for v in cov_rows.values())} statements, "
          f"{sum(len(v['entity']) for v in cov_lines.values())} entity lines, "
          f"{sum(len(v['rows']) for v in cov_lines.values())} cells")
    for p in bad[:20]:
        print("  ", p)
    if len(mods) != 19 or n != 3015 or not every:
        bad.append(f"vacuous input: {len(mods)} modules, {n} original statements")
    ok = not out_of_scope["literal"] and not out_of_scope["superset"] and not problems and not bad
    print("independent recheck:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
