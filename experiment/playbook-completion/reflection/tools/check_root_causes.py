#!/usr/bin/env python3
"""Check reflection/root_causes.json (gate 5c-root-causes) against the findings corpus.

    python check_root_causes.py              # check the committed file; exit 1 on any problem
    python check_root_causes.py --self-test  # the unmutated map passes; every seeded mutation is caught

Corpus (read-only): the original submission's finding ids (experiment/playbook-uplift/FINDINGS.md and findings/*.md,
headings `### F-NNNN`, as matrix/build_matrix.py reads them) and every audit record in
experiment/playbook-completion/findings/audit/*.json (dict files: `findings` + `new_findings`; list files: the list).
A finding id recorded in several audit files takes the record of the last file in sorted order (the rule
build_matrix.py applies). The corpus is read at check time, so a finding added by any lane after the map was built
fails the check until it is assigned (a ratchet).

Rules (each problem carries a tag; the self-test asserts the tag):
  [missing]        a corpus id appears neither as a primary member nor as excluded
  [twice]          an id appears more than once across primary lists and the excluded list
  [unknown-id]     an id named anywhere (primary, secondary, excluded, assignments) is not in the corpus
  [orig-unaudited] an original F-NNNN id has no audit record
  [excluded]       an excluded id is not refuted/not-reproduced/duplicate in the corpus, or such an id is primary
  [xref]           a root cause names an AX-NN / M-NN id absent from semantics/axioms.json / mechanisms.json
  [severity]       highest_severity or severity_counts of a root cause differ from its primary members' severities
  [secondary]      a root cause lists as secondary a finding whose primary is that same root cause
  [assignment]     the per-finding assignments disagree with the root-cause lists
  [conditional]    the conditional list differs from the members that are intent-undecided or blocked-access
  [rc-id]          root-cause ids are not unique RC-NN in order
  [fields]         a root cause lacks a statement, remedy, title or a primary member
  [axiom]          an axiom id is not one of SYS-I1..SYS-I10 as defined in the original ontology (00-system.md)
  [corpus]         the recorded corpus counts differ from the corpus
  [summary]        the summary (counts, top-10 order) differs from what the lists give
  [md]             ROOT-CAUSES.md does not show every root cause with its primary count
"""
from __future__ import annotations

import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
ROOT = LANE.parent                      # experiment/playbook-completion
UPLIFT = ROOT.parent / "playbook-uplift"
MAP = LANE / "root_causes.json"
MD = LANE / "ROOT-CAUSES.md"
SEV_ORDER = {"S1": 1, "S2": 2, "S3": 3, "S4": 4}
EXCLUDED_DISPOSITIONS = ("refuted", "not-reproduced", "duplicate")
CONDITIONAL_DISPOSITIONS = ("intent-undecided", "blocked-access")


def original_ids() -> list:
    ids = []
    files = sorted((UPLIFT / "findings").glob("*.md")) + [UPLIFT / "FINDINGS.md"]
    for f in files:
        for i in re.findall(r"^#+\s*(F-\d{4})\b", f.read_text(), re.M):
            if i not in ids:
                ids.append(i)
    return ids


def load_corpus() -> dict:
    """{'records': {id: record}, 'files': {id: [stems]}, 'original': [ids]}."""
    records, files = {}, {}
    for p in sorted((ROOT / "findings" / "audit").glob("*.json")):
        data = json.loads(p.read_text())
        recs = data if isinstance(data, list) else data.get("findings", []) + data.get("new_findings", [])
        for r in recs:
            records[r["id"]] = r                     # last file in sorted order wins
            files.setdefault(r["id"], []).append(p.stem)
    return {"records": records, "files": files, "original": original_ids()}


def axiom_ids() -> set:
    text = (UPLIFT / "ontology" / "00-system.md").read_text()
    return set(re.findall(r"^\|\s*(SYS-I\d+)\s*\|", text, re.M))


def semantics_ids() -> tuple:
    """(axiom ids, mechanism ids) of the semantics lane's final files; None when a file is absent."""
    sem = ROOT / "semantics"
    out = []
    for fname, key in (("axioms.json", "axioms"), ("mechanisms.json", "mechanisms")):
        p = sem / fname
        out.append({x["id"] for x in json.loads(p.read_text())[key]} if p.exists() else None)
    return tuple(out)


def top10(rcs: list) -> list:
    def key(rc):
        sev = Counter(rc["severity_counts"])
        return (-len(rc["primary"]), -sev.get("S1", 0), -sev.get("S2", 0), rc["id"])
    return [rc["id"] for rc in sorted(rcs, key=key)[:10]]


def check(rcmap: dict, corpus: dict, md_text: str | None, axioms: set, sem: tuple = (None, None)) -> list:
    problems = []
    recs = corpus["records"]
    ids = set(recs)
    rcs = rcmap.get("root_causes", [])
    excluded = rcmap.get("excluded", [])

    for o in corpus["original"]:
        if o not in recs:
            problems.append(f"[orig-unaudited] {o} has no audit record")

    # rc ids
    want = [f"RC-{n:02d}" for n in range(1, len(rcs) + 1)]
    if [rc.get("id") for rc in rcs] != want:
        problems.append(f"[rc-id] root-cause ids are {[rc.get('id') for rc in rcs][:5]}..., expected RC-01..RC-{len(rcs):02d}")

    seen = Counter()
    for rc in rcs:
        for k in ("title", "statement", "remedy"):
            if not str(rc.get(k) or "").strip():
                problems.append(f"[fields] {rc.get('id')} has no {k}")
        if not rc.get("primary"):
            problems.append(f"[fields] {rc.get('id')} has no primary member")
        for a in rc.get("violates", {}).get("axioms", []):
            if a not in axioms:
                problems.append(f"[axiom] {rc.get('id')} names {a}, not an axiom of 00-system.md")
        x = rc.get("semantics_xref") or {}
        for kind, known in (("axioms", sem[0]), ("mechanisms", sem[1])):
            for i in x.get(kind, []):
                if known is None or i not in known:
                    problems.append(f"[xref] {rc.get('id')} names {i}, not in semantics/{kind}.json")
        for f in rc.get("primary", []):
            seen[f] += 1
            if f not in ids:
                problems.append(f"[unknown-id] {rc['id']} primary {f} is not in the corpus")
            elif recs[f].get("disposition") in EXCLUDED_DISPOSITIONS:
                problems.append(f"[excluded] {f} is {recs[f]['disposition']} but is a primary member of {rc['id']}")
        for f in rc.get("secondary", []):
            if f not in ids:
                problems.append(f"[unknown-id] {rc['id']} secondary {f} is not in the corpus")
            if f in rc.get("primary", []):
                problems.append(f"[secondary] {rc['id']} lists its own primary member {f} as secondary")
        members = [f for f in rc.get("primary", []) if f in ids]
        sev = Counter(recs[f].get("severity") for f in members)
        if members:
            hi = min((s for s in sev if s in SEV_ORDER), key=lambda s: SEV_ORDER[s])
            if rc.get("highest_severity") != hi:
                problems.append(f"[severity] {rc['id']} highest_severity {rc.get('highest_severity')} but members give {hi}")
        if {k: v for k, v in (rc.get("severity_counts") or {}).items() if v} != dict(sev):
            problems.append(f"[severity] {rc['id']} severity_counts {rc.get('severity_counts')} != {dict(sev)}")
        cond = sorted(f for f in members if recs[f].get("disposition") in CONDITIONAL_DISPOSITIONS)
        if sorted(rc.get("conditional", [])) != cond:
            problems.append(f"[conditional] {rc['id']} conditional {rc.get('conditional')} != {cond}")

    for e in excluded:
        f = e.get("id")
        seen[f] += 1
        if f not in ids:
            problems.append(f"[unknown-id] excluded {f} is not in the corpus")
        elif recs[f].get("disposition") not in EXCLUDED_DISPOSITIONS or e.get("disposition") != recs[f].get("disposition"):
            problems.append(f"[excluded] {f} excluded as {e.get('disposition')} but the corpus says {recs[f].get('disposition')}")
        if not str(e.get("reason") or "").strip():
            problems.append(f"[fields] excluded {f} has no reason")
    for f in ids:
        if seen[f] == 0:
            problems.append(f"[missing] {f} ({recs[f].get('disposition')}) has no primary root cause and is not excluded")
        elif seen[f] > 1:
            problems.append(f"[twice] {f} appears {seen[f]} times")
    for f in ids:
        if recs[f].get("disposition") in EXCLUDED_DISPOSITIONS and f not in {e.get("id") for e in excluded}:
            problems.append(f"[excluded] {f} is {recs[f]['disposition']} and must be listed as excluded")

    # per-finding assignments
    asg = rcmap.get("assignments", {})
    prim_of = {f: rc["id"] for rc in rcs for f in rc.get("primary", [])}
    sec_of = {}
    for rc in rcs:
        for f in rc.get("secondary", []):
            sec_of.setdefault(f, []).append(rc["id"])
    for f in set(asg) | set(prim_of):
        if f not in ids:
            if f in asg:
                problems.append(f"[unknown-id] assignment for {f}, not in the corpus")
            continue
        a = asg.get(f)
        if a is None:
            problems.append(f"[assignment] {f} has a root cause but no assignment entry")
            continue
        if a.get("primary") != prim_of.get(f):
            problems.append(f"[assignment] {f} assignment primary {a.get('primary')} != list {prim_of.get(f)}")
        if sorted(a.get("secondary", [])) != sorted(sec_of.get(f, [])):
            problems.append(f"[assignment] {f} assignment secondary {a.get('secondary')} != lists {sec_of.get(f, [])}")
        if a.get("primary") in a.get("secondary", []):
            problems.append(f"[secondary] {f} has {a.get('primary')} as both primary and secondary")
        if a.get("severity") != recs[f].get("severity") or a.get("disposition") != recs[f].get("disposition"):
            problems.append(f"[assignment] {f} severity/disposition copied wrong")

    # corpus counts
    c = rcmap.get("corpus", {})
    disp = Counter(r.get("disposition") for r in recs.values())
    expect = {"unique_ids": len(ids), "original": len(corpus["original"]),
              "new": len(ids - set(corpus["original"])), "dispositions": dict(sorted(disp.items()))}
    for k, v in expect.items():
        if c.get(k) != v:
            problems.append(f"[corpus] corpus.{k} = {c.get(k)}, the corpus gives {v}")

    # summary
    s = rcmap.get("summary", {})
    assigned = sum(len(rc.get("primary", [])) for rc in rcs)
    exp = {"root_causes": len(rcs), "assigned": assigned, "excluded": len(excluded),
           "conditional": sum(len(rc.get("conditional", [])) for rc in rcs)}
    for k, v in exp.items():
        if s.get(k) != v:
            problems.append(f"[summary] summary.{k} = {s.get(k)}, the lists give {v}")
    if rcs and all("severity_counts" in rc for rc in rcs) and s.get("top10") != top10(rcs):
        problems.append(f"[summary] top10 {s.get('top10')} != {top10(rcs)}")

    if md_text is not None:
        for rc in rcs:
            if not re.search(rf"\|\s*{rc['id']}\s*\|[^\n]*\|\s*{len(rc.get('primary', []))}\s*\|", md_text):
                problems.append(f"[md] ROOT-CAUSES.md has no table row for {rc['id']} with {len(rc.get('primary', []))} findings")
    return problems


# ---------------------------------------------------------------------------------------------- self-test
def self_test() -> int:
    base = json.loads(MAP.read_text())
    corpus = load_corpus()
    md = MD.read_text()
    ax = axiom_ids()
    sem = semantics_ids()
    ok = True
    p0 = check(base, corpus, md, ax, sem)
    print(f"unmutated: {len(p0)} problems")
    if p0:
        ok = False
        print("  " + "\n  ".join(p0[:10]))
    rcs = base["root_causes"]
    big = max(rcs, key=lambda r: len(r["primary"]))
    other = next(r for r in rcs if r is not big)
    s1rc = next(r for r in rcs if r["highest_severity"] == "S1" and len(r["primary"]) > 1)
    a_finding = big["primary"][0]
    excl = base["excluded"][0]["id"]

    def m_missing(m, c):
        f = m["root_causes"][rcs.index(big)]["primary"].pop()
        m["assignments"].pop(f, None)

    def m_twice(m, c):
        m["root_causes"][rcs.index(other)]["primary"].append(a_finding)

    def m_unknown(m, c):
        m["root_causes"][rcs.index(other)]["secondary"].append("F-9999")

    def m_excluded_assigned(m, c):
        e = m["excluded"].pop(0)
        m["root_causes"][0]["primary"].append(e["id"])

    def m_excluded_wrong(m, c):
        r = m["root_causes"][rcs.index(big)]
        f = r["primary"].pop(0)
        m["excluded"].append({"id": f, "disposition": "refuted", "reason": "seeded"})

    def m_severity(m, c):
        r = m["root_causes"][rcs.index(s1rc)]
        r["highest_severity"] = "S2"

    def m_severity_counts(m, c):
        r = m["root_causes"][rcs.index(big)]
        r["severity_counts"]["S4"] = r["severity_counts"].get("S4", 0) + 1

    def m_secondary(m, c):
        r = m["root_causes"][rcs.index(big)]
        r["secondary"].append(r["primary"][0])

    def m_assignment(m, c):
        m["assignments"][a_finding]["primary"] = other["id"]

    def m_rcid(m, c):
        m["root_causes"][1]["id"] = m["root_causes"][0]["id"]

    def m_fields(m, c):
        m["root_causes"][2]["remedy"] = " "

    def m_axiom(m, c):
        m["root_causes"][0]["violates"]["axioms"].append("SYS-I11")

    def m_corpus_new(m, c):            # a finding added to the corpus after the map: must be assigned
        c["records"]["F-C9999"] = {"id": "F-C9999", "severity": "S2", "disposition": "reproduced-live"}

    def m_corpus_disp(m, c):           # the corpus changes an excluded finding's disposition
        c["records"][excl] = dict(c["records"][excl], disposition="reproduced-live")

    def m_conditional(m, c):
        r = next(x for x in m["root_causes"] if x["conditional"])
        r["conditional"] = []

    def m_summary(m, c):
        m["summary"]["top10"] = list(reversed(m["summary"]["top10"]))

    def m_xref(m, c):
        r = next(x for x in m["root_causes"] if x["semantics_xref"]["mechanisms"])
        r["semantics_xref"]["mechanisms"].append("M-99")

    def m_duplicate_assigned(m, c):
        e = next(x for x in m["excluded"] if x["disposition"] == "duplicate")
        m["excluded"].remove(e)
        m["root_causes"][0]["primary"].append(e["id"])

    def m_md(m, c):
        return md.replace(f"| {big['id']} |", f"| {big['id']}x |", 1)

    mutations = [("missing", m_missing), ("twice", m_twice), ("unknown-id", m_unknown),
                 ("excluded", m_excluded_assigned), ("excluded", m_excluded_wrong), ("severity", m_severity),
                 ("severity", m_severity_counts), ("secondary", m_secondary), ("assignment", m_assignment),
                 ("rc-id", m_rcid), ("fields", m_fields), ("axiom", m_axiom), ("missing", m_corpus_new),
                 ("excluded", m_corpus_disp), ("conditional", m_conditional), ("summary", m_summary), ("md", m_md), ("xref", m_xref),
                 ("excluded", m_duplicate_assigned)]
    caught = 0
    for tag, fn in mutations:
        m = copy.deepcopy(base)
        c = copy.deepcopy(corpus)
        md2 = fn(m, c)
        probs = check(m, c, md2 if isinstance(md2, str) else md, ax, sem)
        hit = any(p.startswith(f"[{tag}]") for p in probs)
        caught += hit
        print(f"mutation {fn.__name__:22s} expects [{tag}]: {'CAUGHT' if hit else 'MISSED'} ({len(probs)} problems)")
        ok &= hit
    print(f"self-test: {caught}/{len(mutations)} seeded mutations caught; unmutated {'clean' if not p0 else 'NOT clean'}")
    print("SELF-TEST PASS" if ok else "SELF-TEST FAIL")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    rcmap = json.loads(MAP.read_text())
    corpus = load_corpus()
    sem = semantics_ids()
    probs = check(rcmap, corpus, MD.read_text() if MD.exists() else "", axiom_ids(), sem)
    recs = corpus["records"]
    nfiles = len(list((ROOT / "findings" / "audit").glob("*.json")))
    nrecs = sum(len(v) for v in corpus["files"].values())
    rcs = rcmap["root_causes"]
    disp = Counter(r.get("disposition") for r in recs.values())
    print(f"corpus: {nrecs} audit records in {nfiles} files; {len(recs)} finding ids ({len(corpus['original'])} original, "
          f"{len(set(recs) - set(corpus['original']))} new); ids recorded in several files (last file wins): "
          f"{', '.join(f'{k} ({chr(32).join(v)})' for k, v in sorted(corpus['files'].items()) if len(v) > 1)}")
    print("dispositions: " + ", ".join(f"{k} {v}" for k, v in sorted(disp.items())))
    print(f"root causes: {len(rcs)}; assigned (primary) {sum(len(r['primary']) for r in rcs)}; "
          f"conditional {sum(len(r.get('conditional', [])) for r in rcs)}; excluded {len(rcmap['excluded'])}: "
          + ", ".join(f"{e['id']} {e['disposition']}" for e in rcmap["excluded"]))
    sev = Counter(recs[f]["severity"] for r in rcs for f in r["primary"])
    print("assigned by severity: " + ", ".join(f"{k} {sev[k]}" for k in ("S1", "S2", "S3", "S4")))
    for r in rcs:
        sc = r.get("severity_counts", {})
        print(f"  {r['id']} {len(r['primary']):3d} findings, highest {r.get('highest_severity')}, "
              f"S1..S4 {[sc.get(k, 0) for k in ('S1', 'S2', 'S3', 'S4')]}, conditional {len(r.get('conditional', []))}, "
              f"secondary {len(r.get('secondary', []))}, axioms {r['violates']['axioms'] + r.get('semantics_xref', {}).get('axioms', [])}, "
              f"mechanisms {r.get('semantics_xref', {}).get('mechanisms', [])}")
    print(f"top10: {', '.join(rcmap['summary'].get('top10', []))} (covering {rcmap['summary'].get('top10_cover')})")
    print(f"semantics final ids present: axioms {sem[0] is not None} ({len(sem[0] or [])}), "
          f"mechanisms {sem[1] is not None} ({len(sem[1] or [])})")
    for p in probs:
        print("PROBLEM", p)
    print("CHECK PASS" if not probs else f"CHECK FAIL ({len(probs)} problems)")
    return 0 if not probs else 1


if __name__ == "__main__":
    sys.exit(main())
