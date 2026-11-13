#!/usr/bin/env python3
"""Rebuild the completion modules from the original submission so the literal term-scope rule holds.

    python3 experiment/playbook-completion/ontology/tools/repair.py            # write NN-*.md and repairs.json
    python3 experiment/playbook-completion/ontology/tools/repair.py --plan     # print the plan, write nothing
    python3 experiment/playbook-completion/ontology/tools/repair.py --out DIR  # write elsewhere (verify with diff)

Input: experiment/playbook-uplift/ontology/NN-*.md (read-only). Output: experiment/playbook-completion/ontology/NN-*.md
and ontology/repairs.json. Deterministic: the same input gives byte-identical output. Original rows are copied
verbatim except for the Parent cell of a reparented row and the text of an explicitly reworded row. Steps:

1. Explicit repairs (REWORDS, NEW_DEFINITIONS): a definer whose text lacks its term, and terms of another module's
   glossary used without a local definition.
2. Reparenting under a definition: a non-definition statement S whose only module glossary terms are the terms of
   an earlier sibling definition D (same parent) becomes a child of D, when S's subtree uses D's term out of scope.
   S is a rule about the thing D defines, so D is its semantic parent; S keeps everything it needs in scope and its
   descendants gain D. Statements that open with a pronoun (they refer to their parent) are never moved.
3. Local restatements: for every remaining (parent P, term T) with a use out of scope, one definition statement
   with the primary definer's exact text is placed under P immediately before P's first child that uses T. Its
   Notes say "Same meaning as <primary>"; the glossary lists it under "Restated by". Repeated until nothing fails.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ontology_check as oc  # noqa: E402

ORIG_ONT = oc.ORIGINAL / "ontology"
OUT_ONT = oc.COMPLETION / "ontology"
PRONOUN_START = re.compile(r"^(It|Its|They|Their|Them|This|These|That|Those|Then|Both|Also|Such)\b")
RESTATE_NOTE = "Same meaning as {p}. Local restatement for the literal term-scope rule (HD-0001)."

# id -> (old text, new text, reason). The meaning is unchanged in each case.
REWORDS: Dict[str, Tuple[str, str, str]] = {
    "CYP-D13": ("A multigraph is a graph set to let two nodes hold more than one edge of one type.",
                "A multigraph is a graph set to let two nodes hold more than one edge of one type. "
                "That setting is called multigraph mode.",
                "The glossary names CYP-D13 as the definer of 'multigraph mode', but its text did not contain the "
                "term. The added sentence names the setting the first sentence already describes; the original "
                "Notes cite engine.set_multigraph(graph, True)."),
}

# Reparenting candidates found by step 2, reviewed by hand. ACCEPT: the statement is a rule about the thing the
# definition defines (its topic), so the definition is its semantic parent. REJECT: the term is incidental (a
# mechanism or an object inside a rule about something else); the statement keeps its parent and its subtree gets
# local restatements instead. The tool fails if a candidate is in neither set or a listed id is not a candidate.
ACCEPT = {
    "ADJ-B1": "ADJ-D1", "ADJ-B10": "ADJ-D22", "ADJ-B5": "ADJ-D6", "ALG-B15": "ALG-D5", "API-B10": "API-D4",
    "API-T1": "API-D10", "API-T3": "API-D12", "ERS-B1": "ERS-D1", "ERS-B2": "ERS-D2", "ERS-I2": "ERS-D3",
    "GID-B1": "GID-D1", "INS-B4": "INS-D4", "INS-B7": "INS-D7", "INT-B1": "INT-D16", "INT-C5": "INT-D13",
    "INT-E1": "INT-D19", "LED-B4": "LED-D4", "LED-B9": "LED-D4", "NAT-T3": "NAT-D4", "NAT-T6": "NAT-D3",
    "NAT-T8": "NAT-D13", "OPS-B11": "OPS-D17", "OPS-B2": "OPS-D7", "OPS-B4": "OPS-D2", "RED-B7": "RED-D10",
    "RPL-B7": "RPL-D2", "RPL-T1": "RPL-D2", "SNP-B1": "SNP-D1", "TMP-B12": "TMP-D2", "VEC-B1": "VEC-D7",
    "VEC-B11": "VEC-D13", "VEC-B2": "VEC-D8", "VEC-B9": "VEC-D19", "WRT-B1": "WRT-D1", "WRT-B2": "WRT-D1",
}
REJECT = {
    "CYP-B11": "about how Cypher functions become SQL; helper functions are a means",
    "INS-B2": "about each namespace having one schema; the schema record is where the name is kept",
    "INT-C1": "about the three-step path from a concept; FHIR resources are only its output",
    "INT-F8": "about the status command; the FHIR graph is only its argument",
    "LED-B14": "about how refusals reach Python; the error code only names the error type",
    "OPS-B3": "about the admin helpers; drift is one thing they check",
    "RED-B2": "the central redaction rule (records become tombstones); the target is only its scope",
    "SNP-B2": "about the restore command; the archive is only its input",
    "TMP-B1": "about the temporal write command; the temporal edge is what it writes",
    "TMP-B10": "about erasure of temporal stores; the temporal index class is the means",
    "TXT-B12": "about the docs table search command; the table is what it reads",
    "TXT-B14": "about the SQL fused search; the docs table list is one input",
    "VEC-B4": "about reading a node's vector; the route is where it reads",
    "VEC-B5": "about nearest search; the route is where it reads",
    "VEC-B6": "about embedding a graph's nodes; the selector is one input",
    "VEC-B7": "about queueing work for later; the worker is who does it",
}

# New primary definitions for terms of another module's glossary that a statement uses (rule foreign-term). Each
# copies the other module's definition text and cites it; it is placed immediately before its user, same parent.
NEW_DEFINITIONS = [
    {"id": "NAT-D22", "module": "NAT", "term": "chained query", "copy_of": "CYP-D21", "before": "NAT-X1"},
    {"id": "RED-D14", "module": "RED", "term": "statement entry", "copy_of": "ERS-D3", "before": "RED-B9"},
]


@dataclass
class Row:
    id: str
    parent: str
    kind: str
    text: str
    evidence: str
    source: str
    notes: str
    raw: Optional[str]            # the original line (None for a new row)
    orig_parent: Optional[str]
    orig_text: Optional[str]
    primary: Optional[str] = None  # set for a local restatement


@dataclass
class Gl:
    raw_term: str
    term: str
    primary: str
    restated: List[str] = field(default_factory=list)


@dataclass
class Plan:
    code: str
    path: Path
    lines: List[str]
    gl_span: Tuple[int, int]       # [header line, end) of the glossary table
    st_span: Tuple[int, int]       # [first row, end) of the statements table rows
    rows: List[Row]
    glossary: List[Gl]
    log: Dict[str, dict] = field(default_factory=dict)

    def by_id(self) -> Dict[str, Row]:
        return {r.id: r for r in self.rows}

    def terms_of(self, rid: str) -> Set[str]:
        return {g.term for g in self.glossary if g.primary == rid}


def table_span(lines: List[str], heading: str) -> Tuple[int, int]:
    start = next(i for i, l in enumerate(lines) if l.strip() == f"## {heading}")
    i = start + 1
    while not lines[i].lstrip().startswith("|"):
        i += 1
    j = i
    while j < len(lines) and lines[j].lstrip().startswith("|"):
        j += 1
    return i, j


def load(path: Path) -> Plan:
    lines = path.read_text(encoding="utf-8").split("\n")
    code = next(re.match(r"^Module:\s*(\S+)", l).group(1) for l in lines if l.startswith("Module:"))
    g0, g1 = table_span(lines, "Glossary")
    glossary = []
    for l in lines[g0 + 2:g1]:
        c = oc.split_row(l)
        glossary.append(Gl(c[0].strip(), c[0].strip().lower(), c[1].strip()))
    s0, s1 = table_span(lines, "Statements")
    rows = []
    for l in lines[s0 + 2:s1]:
        c = oc.split_row(l)
        rows.append(Row(c[0], c[1], c[2], c[3], c[4], c[5], c[6], l, c[1], c[3]))
    return Plan(code, path, lines, (g0, g1), (s0 + 2, s1), rows, glossary)


PATTERNS: Dict[str, "re.Pattern[str]"] = {}


def pat(term: str):
    if term not in PATTERNS:
        PATTERNS[term] = oc.strong_pattern(term)
    return PATTERNS[term]


_USES: Dict[Tuple[int, int, str], Set[str]] = {}


def uses(text: str, glossary: List[Gl]) -> Set[str]:
    key = (id(glossary), len(glossary), text)
    if key not in _USES:
        _USES[key] = {g.term for g in glossary if pat(g.term).search(text)}
    return _USES[key]


def failing(plan: Plan) -> List[Tuple[int, str]]:
    """(row index, term) pairs out of literal scope, in document order."""
    idx = {r.id: i for i, r in enumerate(plan.rows)}
    byid = plan.by_id()
    out = []
    for i, r in enumerate(plan.rows):
        used = uses(r.text, plan.glossary)
        if not used:
            continue
        anc: Set[str] = set()
        node = r
        while node.parent in byid and node.parent not in anc:
            anc.add(node.parent)
            node = byid[node.parent]
        for g in plan.glossary:
            if g.term not in used:
                continue
            ok = False
            for d in [g.primary] + g.restated:
                if d == r.id or d in anc or (d in byid and byid[d].parent == r.parent and idx[d] < i):
                    ok = True
                    break
            if not ok:
                out.append((i, g.term))
    return out


def subtree(plan: Plan, rid: str) -> Set[str]:
    kids = defaultdict(list)
    for r in plan.rows:
        kids[r.parent].append(r.id)
    out, todo = set(), [rid]
    while todo:
        x = todo.pop()
        for k in kids.get(x, []):
            if k not in out:
                out.add(k)
                todo.append(k)
    return out


def esc(cell: str) -> str:
    return cell.replace("|", "\\|")


def row_line(r: Row) -> str:
    if r.raw is not None and r.parent == r.orig_parent and r.text == r.orig_text:
        return r.raw
    if r.raw is not None:
        c = oc.split_row(r.raw)
        old = "| " + " | ".join(esc(x) for x in c) + " |"
        if old == r.raw:  # canonical layout: rebuild with the new cells
            return "| " + " | ".join(esc(x) for x in [r.id, r.parent, r.kind, r.text, r.evidence, r.source, r.notes]) + " |"
        # non-canonical spacing: patch only the cells that changed
        line = r.raw
        if r.parent != r.orig_parent:
            line = re.sub(rf"^\|\s*{re.escape(r.id)}\s*\|\s*{re.escape(r.orig_parent)}\s*\|",
                          f"| {r.id} | {r.parent} |", line, count=1)
        if r.text != r.orig_text:
            line = line.replace(esc(r.orig_text), esc(r.text), 1)
        return line
    return "| " + " | ".join(esc(x) for x in [r.id, r.parent, r.kind, r.text, r.evidence, r.source, r.notes]) + " |"


# --------------------------------------------------------------------------- steps

def explicit(plans: Dict[str, Plan], every: Dict[str, Row]) -> None:
    for rid, (old, new, why) in REWORDS.items():
        plan = plans[rid.split("-")[0]]
        r = plan.by_id()[rid]
        assert r.text == old, (rid, r.text)
        r.text = new
        plan.log[rid] = {"change": "reworded", "old_parent": r.orig_parent, "new_parent": r.parent,
                         "old_text": old, "new_text": new, "reason": why}
    for nd in NEW_DEFINITIONS:
        plan = plans[nd["module"]]
        src = every[nd["copy_of"]]
        users = plan.by_id()
        before = users[nd["before"]]
        assert nd["id"] not in users and not any(g.term == nd["term"] for g in plan.glossary)
        assert pat(nd["term"]).search(src.text) and pat(nd["term"]).search(before.text)
        row = Row(nd["id"], before.parent, "D", src.text, src.evidence, src.source,
                  f"Same meaning as {nd['copy_of']} (module {src.id.split('-')[0]}). Added because "
                  f"{nd['before']} uses the term.", None, None, None)
        plan.rows.insert(plan.rows.index(before), row)
        plan.glossary.append(Gl(nd["term"], nd["term"], nd["id"]))
        plan.log[nd["id"]] = {"change": "added-definition", "old_parent": None, "new_parent": row.parent,
                              "old_text": None, "new_text": row.text, "copy_of": nd["copy_of"], "term": nd["term"],
                              "reason": f"{nd['before']} uses '{nd['term']}', a term of module "
                                        f"{src.id.split('-')[0]}'s glossary that module {plan.code} did not define."}


CANDIDATES: Dict[str, str] = {}


def reparent(plan: Plan) -> None:
    primaries = {g.primary for g in plan.glossary}
    for pos in range(len(plan.rows)):
        s = plan.rows[pos]
        if s.kind in ("D", "R") or PRONOUN_START.match(s.text):
            continue
        used = uses(s.text, plan.glossary)
        if not used:
            continue
        idx = {r.id: i for i, r in enumerate(plan.rows)}
        fails = failing(plan)
        sub = subtree(plan, s.id)
        best, best_gain = None, 0
        for d in plan.rows[:pos]:
            if d.kind != "D" or d.parent != s.parent or d.id not in primaries or d.primary:
                continue
            dterms = plan.terms_of(d.id)
            if not used <= dterms:
                continue
            gain = sum(1 for i, t in fails if plan.rows[i].id in sub and t in dterms)
            if gain > best_gain:
                best, best_gain = d, gain
        if best is not None:
            CANDIDATES[s.id] = best.id
            if s.id in REJECT:
                continue
            if ACCEPT.get(s.id) != best.id:
                raise SystemExit(f"unreviewed reparenting candidate {s.id} -> {best.id}: add it to ACCEPT or REJECT")
            plan.log[s.id] = {"change": "reparented", "old_parent": s.parent, "new_parent": best.id,
                              "old_text": s.text, "new_text": s.text,
                              "reason": "Reviewed: a rule about the thing the new parent defines. "
                                        f"Its only module terms ({', '.join(sorted(used))}) are defined by "
                                        f"{best.id}, an earlier sibling; as a rule about that thing it moves under "
                                        f"the definition, which brings the term into scope for its "
                                        f"{len(sub)} descendant(s) ({best_gain} use(s))."}
            s.parent = best.id


def restate(plan: Plan) -> int:
    gl = {g.term: g for g in plan.glossary}
    # A restatement repeats a primary definition, so it restates every term that primary defines (one list per
    # primary, shared by its terms). Restating one term at a time would loop when a primary defines two terms.
    shared: Dict[str, List[str]] = {}
    for g in plan.glossary:
        g.restated = shared.setdefault(g.primary, g.restated)
    rounds = 0
    while True:
        fails = failing(plan)
        if not fails:
            return rounds
        rounds += 1
        if rounds > 200:
            raise SystemExit(f"{plan.code}: restatement did not converge")
        first: Dict[Tuple[str, str], Tuple[int, str]] = {}
        for i, t in fails:
            key = (plan.rows[i].parent, t)
            first.setdefault(key, (i, plan.rows[i].id))
        byid = plan.by_id()
        order = {r.id: i for i, r in enumerate(plan.rows)}
        # insert in the order of the primary definitions, so a definition's own terms come first
        todo = sorted(first.items(), key=lambda kv: (kv[1][0], order[gl[kv[0][1]].primary]))
        done: Set[Tuple[str, str]] = set()
        for (parent, term), (_, user) in todo:
            g = gl[term]
            if (parent, g.primary) in done:
                continue
            done.add((parent, g.primary))
            have = [x for x in g.restated if byid[x].parent == parent]
            pos = next(k for k, r in enumerate(plan.rows) if r.id == user)
            if have:
                r = byid[have[0]]
                old = next(k for k, x in enumerate(plan.rows) if x.id == r.id)
                if old > pos:
                    plan.rows.pop(old)
                    plan.rows.insert(pos, r)
                continue
            p = byid[g.primary]
            tmp = f"{g.primary}~{len(g.restated)}"
            r = Row(tmp, parent, "D", p.text, p.evidence, p.source, RESTATE_NOTE.format(p=g.primary), None, None,
                    None, primary=g.primary)
            plan.rows.insert(pos, r)
            g.restated.append(tmp)
            byid[tmp] = r


def suffix(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, k = divmod(n - 1, 26)
        s = chr(97 + k) + s
    return s


def assign_ids(plan: Plan, taken: Set[str]) -> None:
    rename: Dict[str, str] = {}
    count: Dict[str, int] = defaultdict(int)
    for r in plan.rows:
        if r.primary:
            while True:
                new = f"{r.primary}{suffix(count[r.primary])}"
                count[r.primary] += 1
                if new not in taken:
                    break
            rename[r.id] = new
            taken.add(new)
    for r in plan.rows:
        if r.id in rename:
            r.id = rename[r.id]
        if r.parent in rename:
            r.parent = rename[r.parent]
    order = {r.id: i for i, r in enumerate(plan.rows)}
    for g in plan.glossary:
        g.restated = sorted((rename.get(x, x) for x in g.restated), key=lambda x: order[x])
    for r in plan.rows:
        if r.primary:
            plan.log[r.id] = {"change": "added-restatement", "old_parent": None, "new_parent": r.parent,
                              "old_text": None, "new_text": r.text, "primary": r.primary,
                              "terms": sorted(g.term for g in plan.glossary if r.id in g.restated)}


def render(plan: Plan) -> str:
    lines = list(plan.lines)
    s0, s1 = plan.st_span
    body = [row_line(r) for r in plan.rows]
    g0, g1 = plan.gl_span
    gl = ["| Term | Defined by | Restated by |", "|---|---|---|"]
    gl += [f"| {g.raw_term} | {g.primary} | {', '.join(g.restated)} |".replace("|  |", "| |") for g in plan.glossary]
    out = lines[:g0] + gl + lines[g1:s0] + body + lines[s1:]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="print the plan and write nothing")
    ap.add_argument("--out", type=Path, default=OUT_ONT,
                    help="output directory (default: the completion ontology; use a scratch dir to verify)")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    plans: Dict[str, Plan] = {}
    files = sorted(ORIG_ONT.glob("[0-9][0-9]-*.md"))
    for f in files:
        p = load(f)
        plans[p.code] = p
    every = {r.id: r for p in plans.values() for r in p.rows}
    before = {c: len(failing(p)) for c, p in plans.items()}
    explicit(plans, every)
    for p in plans.values():
        reparent(p)
    after_reparent = {c: len(failing(p)) for c, p in plans.items()}
    stale = (set(ACCEPT) | set(REJECT)) - set(CANDIDATES)
    if stale or set(ACCEPT) & set(REJECT):
        raise SystemExit(f"reviewed ids that are not candidates (or in both sets): {sorted(stale)}")
    taken = {r.id for p in plans.values() for r in p.rows}
    for p in plans.values():
        restate(p)
        assign_ids(p, taken)
    log: Dict[str, dict] = {}
    for p in plans.values():
        log.update(p.log)
    kinds = defaultdict(int)
    for v in log.values():
        kinds[v["change"]] += 1
    for c, p in plans.items():
        print(f"{c}: out-of-scope pairs {before[c]} -> {after_reparent[c]} after reparenting -> {len(failing(p))}; "
              f"reparented {sum(1 for v in p.log.values() if v['change'] == 'reparented')}, restated "
              f"{sum(1 for v in p.log.values() if v['change'] == 'added-restatement')}")
    print(f"total: pairs {sum(before.values())} -> {sum(after_reparent.values())} -> "
          f"{sum(len(failing(p)) for p in plans.values())}; " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    if a.plan:
        for k, v in sorted(log.items()):
            if v["change"] == "reparented":
                print(f"REPARENT {k}: {v['old_parent']} -> {v['new_parent']}: {v['old_text']}")
        return 0
    for f in files:
        p = next(x for x in plans.values() if x.path == f)
        (a.out / f.name).write_text(render(p), encoding="utf-8")
    order = {r.id: (i, j) for i, p in enumerate(plans.values()) for j, r in enumerate(p.rows)}
    out = {k: log[k] for k in sorted(log, key=lambda x: order[x])}
    summary = {"input": "experiment/playbook-uplift/ontology (submission 9c3719c1)",
               "reparenting_candidates_rejected": dict(sorted(REJECT.items())),
               "tool": "experiment/playbook-completion/ontology/tools/repair.py",
               "counts": dict(sorted(kinds.items())),
               "pairs_out_of_scope": {"before": sum(before.values()), "after_reparenting": sum(after_reparent.values()),
                                      "after": sum(len(failing(p)) for p in plans.values())}}
    (a.out / "repairs.json").write_text(json.dumps({"summary": summary, "statements": out}, indent=1,
                                                     ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(files)} modules and repairs.json ({len(out)} statement entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
