#!/usr/bin/env python3
"""Add completion evidence to the repaired ontology (review R-05) and mark model-level evidence.

    python3 experiment/playbook-completion/ontology/tools/add_evidence.py                  # update the modules
    python3 experiment/playbook-completion/ontology/tools/add_evidence.py --ontology DIR   # update a copy instead
    python3 experiment/playbook-completion/ontology/tools/add_evidence.py --plan           # print, write nothing

Inputs: the findings audits (experiment/playbook-completion/findings/audit/*.json), the run registry
(experiment/playbook-completion/evidence/runs/*.json) and the original modules (to know which finding a statement
already cited). Idempotent: running it again changes nothing. Steps:

1. finding:<id> on the statements a reproduced finding contradicts (FINDING_TAGS). Candidates are generated from each
   finding's `intended` text (the statement ids it names as the violated contract); every candidate is reviewed into
   FINDING_TAGS or FINDING_REJECT, and the tool stops on an unreviewed one. Criterion: the observed behaviour
   contradicts the statement's text in some reachable execution. Findings that name no statement stay untagged.
2. live:C-/mc:C-/trace:C- on the statements a passing completion run plainly concerns (RUN_TAGS): its `observes`
   text names the statement id (abbreviated lists such as "RED-I1/I2" are expanded). Every named id is reviewed into
   RUN_TAGS or RUN_REJECT. No proved:C- tag: no completion proof record names a statement.
3. [model-only] on every proved:/mc: item of a statement that cites a finding whose audit disposition is
   reproduced-live, reproduced-test or confirmed-source.
4. Restatements get their primary definition's evidence again (the checker requires equal evidence).
Writes ontology/evidence-additions.json (what was added, qualified, rejected and left untagged, with reasons).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ontology_check as oc  # noqa: E402

ONT = oc.COMPLETION / "ontology"
RUNS = oc.COMPLETION / "evidence" / "runs"
REPRODUCED = {"reproduced-live", "reproduced-test", "reproduced-model", "confirmed-source"}
UNDECIDED = {"intent-undecided", "blocked-access"}
MODS = "SYS|INS|GID|WRT|ADJ|TMP|VEC|TXT|CYP|NAT|ALG|LED|ERS|RED|RPL|INT|API|OPS|SNP"
TOKEN = r"[A-Z]*\d+(?:\.\d+)*[a-z]?"
SID = re.compile(rf"(?<![A-Za-z0-9-])((?:{MODS})-{TOKEN})(?![A-Za-z0-9])")
SID_LIST = re.compile(rf"(?<![A-Za-z0-9-])({MODS})-({TOKEN})((?:\s*[/,]\s*{TOKEN}(?![A-Za-z0-9-]))*)")

C = "contradicted"
# finding -> {statement: why the observed behaviour contradicts the statement's text}
FINDING_TAGS: Dict[str, Dict[str, str]] = {
    "F-0106": {"SYS-I2": f"{C}: a label's property keys answer with keys of another graph's nodes"},
    "F-C0401": {"ADJ-I5.9": f"{C} (model): a stopped writer lets a reader store a count that saw the undone edge"},
    "F-0615": {"SYS-I3": f"{C}: a refused embedding batch leaves a new route and registry row"},
    "F-0704": {"SYS-I3": f"{C}: a refused index-handle build has already destroyed the old index"},
    "F-C0701": {"TXT-D1": f"{C}: index-structure words become stopwords of every index"},
    "F-C0702": {"SYS-I3": f"{C}: a failed Insert/Delete rolls back the caller's whole transaction"},
    "F-0801": {"CYP-X7.2": f"{C}: strict mode fails open, so a Cypher write is not refused"},
    "F-C0901": {"NAT-I3": f"{C}: one shape's entry runs another shape's class until a deploy"},
    "F-1002": {"SYS-I2": f"{C}: random_walk steps across graphs"},
    "F-1005": {"SYS-I8": f"{C} (source, non-indexed configuration): the interned snapshot lacks edges and says nothing"},
    "F-1006": {"ALG-I3": f"{C}: a default-graph call reads subgraph vectors of a named graph by node id"},
    "F-1009": {"ALG-I3": f"{C}: a default-graph khop answers a start node that only a named graph holds"},
    "F-C1001": {"ALG-I6": f"{C}: triangle_count, a read, creates SQL functions and rewrites the deploy record"},
    "F-1114": {"SYS-I1": f"{C}: erasure writes the ledger's statement maps, which the ledger owns"},
    "F-C1101": {"LED-B13.2": f"{C}: a commit its caller rolled back stays counted",
                "LED-B13.4": f"{C}: the stats row over-counts outcomes"},
    "F-C1201": {"RED-B1.1": f"{C}: a run completes against an erasure that then rolls back, so tombstoned content "
                            "is live again"},
    "F-C1303": {"RED-B8": f"{C}: repeated bounded calls rescan from the start and never finish",
                "RED-B8.1": f"{C} (manual, not in intended; review R-05): 60 calls with no commit in between never "
                            "finished"},
    "F-C1301": {"RED-B1.1": f"{C} (model): the liveness check reads another writer's uncommitted delete"},
    "F-1304": {"RPL-B1.1": f"{C} (manual, not in intended; review R-05): redact(None) tombstones another tenant's "
                           "node records, so replay loses that tenant's nodes too"},
    "F-1502": {"SYS-D26": f"{C}: erasing the edge's graph leaves its reifier node and properties",
               "SYS-I2": f"{C}: the reifier node of a named graph's edge answers in the default graph"},
    "F-1506": {"SYS-I9": f"{C}: the refusal names a missing rdflib when rdflib is present"},
    "F-1507": {"SYS-I2": f"{C}: the anchor lookup answers a node of that id from any graph"},
    "F-1511": {"SYS-I3": f"{C} (model): a register that fails after its upsert keeps the new settings"},
    "F-C1501": {"SYS-I4": f"{C} (source): the task and the task id change in separate untransacted steps",
                "INT-F9": f"{C} (source): a failure between the steps leaves an orphan sync task"},
    "F-C1502": {"SYS-I4": f"{C}: the node and its reifiers go in two transactions",
                "INT-E1.9": f"{C}: a stop between the two transactions leaves the reifier nodes"},
    "F-1603": {"SYS-I2": f"{C}: the generated GraphQL server mixes graphs in one answer"},
    "F-1609": {"SYS-I4": f"{C}: the FHIR event route's writes are not all-or-nothing"},
    "F-C1602": {"SYS-I9": f"{C} (source): server and connection failures are reported as client syntax errors"},
    "F-C1603": {"API-T9.1": f"{C}: Bolt listens on every interface unless started by ivg server start"},
    "F-1701": {"SYS-I2": f"{C}: the SQL adapter's unscoped node and label reads merge graphs"},
    "F-C1702": {"OPS-B1.12": f"{C}: with --workers above 1 the command exits without serving"},
    "F-1801": {"SYS-I5": f"{C}: a replacing restore lays the archive's ledger over the live one"},
    "F-C1802": {"SNP-X2.14": f"{C}: a global line that cannot be written is dropped without an error"},
    "F-C1804": {"SNP-I1": f"{C}: routed edge vector tables are neither copied nor listed as left out",
                "SNP-B1.18": f"{C}: a restore loses routed edge vectors"},
}
FINDING_REJECT: Dict[Tuple[str, str], str] = {
    ("F-0503", "RPL-B3"): "the cited paraphrase (replay equals the store when every write goes through the ledger) "
                          "is not RPL-B3's text, which is about verify after erasure and redaction",
    ("F-0703", "SYS-I8"): "outcome intent-undecided (is a BM25 index a rebuilt store?)",
    ("F-C0801", "SYS-I8"): "outcome intent-undecided",
    ("F-C0801", "CYP-I6.4"): "outcome intent-undecided",
    ("F-0805", "CYP-B6.7.6"): "the finding says the matched-endpoint path, which this statement is about, is guarded",
    ("F-0814", "CYP-I9.4"): "the statement is about names in a Cypher query reaching SQL; the finding is AQL values "
                            "pasted into Cypher text",
    ("F-0814", "CYP-I8.6"): "the statement is about reads; the finding is AQL writes that ignore read-only mode",
    ("F-0901", "NAT-T5.16"): "the statement holds as written (the class named for its own checksum runs); the "
                             "checksum collision breaks NAT-I3, which already cites the finding",
    ("F-0905", "NAT-T5.22"): "the drop happens as stated; the race with running builds breaks NAT-I5, which "
                             "already cites the finding",
    ("F-0909", "NAT-T4.7"): "the spec's reason is wrong; the statement describes what the code does",
    ("F-C0901", "NAT-T5.16"): "the cited paraphrase (the class written for its own shape) differs from the "
                              "statement's text (the class named for its own checksum), which holds",
    ("F-1008", "ALG-I2"): "every-graph mode names no graph; ALG-I2 is about a call that names one (ALG-B11.2 "
                          "carries the finding)",
    ("F-1013", "ALG-I2"): "the reproduced branch is a table outside the IVG schema, not a graph mix",
    ("F-1013", "ALG-I3"): "the reproduced branch is a table outside the IVG schema, not a graph mix",
    ("F-1107", "LED-B4.9.1"): "cited for context (the size limit); the defect is the revision kind (LED-B4.9.2)",
    ("F-C1202", "ERS-B1.1"): "the statement says erasure removes the graph's index entries; the finding is "
                             "over-removal of a concurrent edge's entries, which the statement does not deny",
    ("F-1503", "SYS-I2"): "SYS-I2 is about answers; the finding is a delete across graphs",
    ("F-C1601", "API-T8.3"): "the statement (each session opens its own connection) holds; the defect is release",
    ("F-C1801", "SNP-Q1.17"): "a question makes no claim that a finding could contradict",
}

# run -> {statement: condition to add to Notes, or ""}. Each id is named in the run's observes text.
SEQ = ("Completion: mc:C-core-m1-as-built-isolation-stmt-a/b/c check the as-built model sequentially (no "
       "concurrent erasure or commit), profiles a-c, exhaustive within bounds.")
REFUSALS = ""
RUN_TAGS: Dict[str, Dict[str, str]] = {
    "b-08-live-footprints": {"CYP-I6.3": "", "CYP-I6.4": "", "CYP-X6.5": ""},
    "b-10-live-nkg-f1005": {"ALG-B12.7": "Completion: live:C-b-10-live-nkg-f1005 is the indexed (default) "
                                         "configuration; F-1005 stands, by source, where the adjacency index is "
                                         "not declared."},
    "b-10-live-refusals": {k: REFUSALS for k in (
        "ALG-B1.5", "ALG-B2.2", "ALG-B2.8", "ALG-B2.9", "ALG-B2.10", "ALG-B2.13", "ALG-B5.3", "ALG-B5.10",
        "ALG-B5.17", "ALG-B5.22", "ALG-B6.7", "ALG-B8.10", "ALG-B10.6")},
    "c15-live-refusals": {k: REFUSALS for k in (
        "INT-F1.13", "INT-F3.5", "INT-F3.6", "INT-F8.2", "INT-F8.4", "INT-C1.2", "INT-C1.7", "INT-C3.4", "INT-C4.3",
        "INT-C5.1", "INT-M1.2", "INT-M1.3", "INT-M1.6", "INT-M1.8", "INT-M1.12", "INT-R1.18", "INT-S1.4", "INT-S1.6",
        "INT-S1.11", "INT-V1.10", "INT-C4.5", "INT-V1.4")},
    "c15-live-register": {"INT-F3.2": "", "INT-F8.1": "", "INT-F10.5": ""},
    "c18-live-refusals": {"SNP-X2.1": "", "SNP-X2.2": ""},
    "c18-live-restore-footprint": {"SNP-T3.1": ""},
    "c18-live-save-footprint": {"SNP-I2": "", "SNP-T1.11": ""},
    "cmc-restore-reviewed": {"SNP-I3.6": "Completion: mc:C-cmc-restore-reviewed checks the reviewed restore design "
                                         "(refuse divergent histories, keep marks), not the pin."},
    "core-m1-as-built-isolation-stmt-a": {"RED-I1": SEQ, "RED-I2": SEQ, "ERS-I2": SEQ, "ERS-I3": SEQ},
    "core-m1-as-built-isolation-stmt-b": {"RED-I1": SEQ, "RED-I2": SEQ, "ERS-I2": SEQ, "ERS-I3": SEQ},
    "core-m1-as-built-isolation-stmt-c": {"RED-I1": SEQ, "RED-I2": SEQ, "ERS-I2": SEQ, "ERS-I3": SEQ},
    "live-erase-vs-commit-fk": {"ERS-I1": ""},
}
RUN_REJECT: Dict[Tuple[str, str], str] = {
    ("b-08-live-footprints", "CYP-I8.6"): "named only as 'I8.6-read'; the run does not say its reads ran in "
                                          "read-only mode, which is what the statement is about",
    ("cmc-register-as-built-links", "SYS-I3"): "a universal axiom; one command's model does not establish it (a "
                                               "finding can refute it, a confirming model cannot prove it)",
    ("cmc-register-reviewed", "SYS-I3"): "a universal axiom; one command's reviewed model does not establish it",
    ("cmc-restore-reviewed", "SNP-B3.7"): "the statement describes as-built behaviour (a restore puts redacted "
                                          "content back) that the reviewed model forbids",
    ("cmc-snap-reviewed", "SNP-Q1.17"): "a question makes no claim; the run checks one reviewed answer",
    ("cmc-snap-reviewed", "SYS-P2"): "a premise the model assumes, not a property it checks",
    ("live-erase-vs-commit-emptygraph", "ERS-I3"): "the run says the F-1201 window was not reached",
    ("live-erase-vs-commit-fk", "ERS-I3"): "the run says the F-1201 window was not reached",
}


def row_cells(line: str) -> List[str]:
    return oc.split_row(line)


def replace_cells(line: str, new: Dict[int, str]) -> str:
    """Replace cells (0-based) of a table row; every other byte of the line stays as it was."""
    bounds = [i for i, ch in enumerate(line) if ch == "|" and (i == 0 or line[i - 1] != "\\")]
    out, last = [], 0
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        if k in new:
            out.append(line[last:a + 1] + " " + new[k].replace("|", "\\|") + " ")
            last = b
    out.append(line[last:])
    result = "".join(out)
    check = row_cells(result)
    if any(check[k] != v for k, v in new.items()) or len(check) != len(row_cells(line)):
        raise SystemExit(f"cell replacement failed for: {line[:60]}")
    return result


def load_rows(ont: Path) -> Dict[str, Tuple[Path, int, List[str]]]:
    out = {}
    for p in sorted(ont.glob("[0-9][0-9]-*.md")):
        lines = p.read_text(encoding="utf-8").split("\n")
        s0, s1 = table_rows(lines)
        for i in range(s0, s1):
            c = row_cells(lines[i])
            out[c[0]] = (p, i, c)
    return out


def table_rows(lines: List[str]) -> Tuple[int, int]:
    i = next(k for k, l in enumerate(lines) if l.strip() == "## Statements")
    while not lines[i].startswith("|"):
        i += 1
    j = i + 2
    k = j
    while k < len(lines) and lines[k].startswith("|"):
        k += 1
    return j, k


def expand_ids(text: str) -> List[str]:
    out = []
    for m in SID_LIST.finditer(text):
        mod, first, rest = m.group(1), m.group(2), m.group(3)
        out.append(f"{mod}-{first}")
        out += [f"{mod}-{t}" for t in re.findall(TOKEN, rest)]
    return list(dict.fromkeys(out))


def items_of(ev: str) -> List[str]:
    return [x.strip() for x in ev.split(";") if x.strip()]


def bare(item: str) -> str:
    return re.sub(r"\s*\[[a-z-]+\]$", "", item)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ontology", type=Path, default=ONT)
    ap.add_argument("--plan", action="store_true")
    a = ap.parse_args()
    ont = a.ontology.resolve()
    audit = oc.load_audit(oc.COMPLETION)
    runs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(RUNS.glob("*.json"))}
    rows = load_rows(ont)
    orig = load_rows(oc.ORIGINAL / "ontology")
    restated = {}
    for p in sorted(ont.glob("[0-9][0-9]-*.md")):
        errs: List[str] = []
        m = oc.parse_module(p, errs, 0)
        for g in m.glossary:
            for r in g.restated:
                restated[r] = g.primary
    problems: List[str] = []

    # 1. findings: every candidate reviewed, every tag valid
    orig_cites: Dict[str, Set[str]] = {}
    for sid, (_, _, c) in orig.items():
        for f in re.findall(r"finding:(F-[A-Z0-9]+)", c[4]):
            orig_cites.setdefault(f, set()).add(sid)
    for fid, f in sorted(audit.items()):
        if f.get("disposition") not in REPRODUCED:
            continue
        for sid in dict.fromkeys(SID.findall(str(f.get("intended", "")))):
            if sid in rows and sid not in orig_cites.get(fid, set()) and sid not in restated:
                if sid not in FINDING_TAGS.get(fid, {}) and (fid, sid) not in FINDING_REJECT:
                    problems.append(f"unreviewed finding candidate {fid} -> {sid}")
    for fid, tags in FINDING_TAGS.items():
        f = audit.get(fid)
        if f is None or f.get("disposition") not in REPRODUCED or f.get("outcome") in UNDECIDED:
            problems.append(f"{fid}: not a reproduced finding in the audit")
        for sid in tags:
            if sid not in rows or sid in restated:
                problems.append(f"{fid}: statement {sid} missing or a restatement")
    for (fid, sid) in FINDING_REJECT:
        if fid not in audit or sid not in rows:
            problems.append(f"rejected pair {fid}/{sid} does not resolve")
    # 2. runs: every id a passing run names is reviewed, every tag is named and passing
    for rid, r in runs.items():
        if r.get("result") != "pass" or r.get("kind") not in ("live", "mc", "trace"):
            continue
        for sid in expand_ids(r.get("observes", "")):
            if sid in rows and sid not in RUN_TAGS.get(rid, {}) and (rid, sid) not in RUN_REJECT:
                problems.append(f"unreviewed run candidate {rid} -> {sid}")
    for rid, tags in RUN_TAGS.items():
        r = runs.get(rid)
        if r is None or r.get("result") != "pass" or r.get("kind") not in ("live", "mc", "trace") \
                or r.get("product_pin") != oc.PIN:
            problems.append(f"run {rid}: missing or not a passing live/mc/trace run at the pin")
            continue
        named = set(expand_ids(r.get("observes", "")))
        for sid in tags:
            if sid not in named:
                problems.append(f"run {rid} does not name {sid} in its observes text")
            if sid not in rows or sid in restated:
                problems.append(f"run {rid}: statement {sid} missing or a restatement")
    if problems:
        print("\n".join(problems))
        return 1

    # apply
    log = {"findings": {}, "runs": {}, "model_only": {}, "notes": {}, "restatements_updated": []}
    new_ev: Dict[str, List[str]] = {sid: items_of(c[4]) for sid, (_, _, c) in rows.items()}
    new_notes: Dict[str, str] = {sid: c[6] for sid, (_, _, c) in rows.items()}
    for fid, tags in FINDING_TAGS.items():
        for sid, why in tags.items():
            item = f"finding:{fid}"
            if item not in map(bare, new_ev[sid]):
                new_ev[sid].append(item)
            log["findings"].setdefault(sid, {})[fid] = {"disposition": audit[fid]["disposition"], "why": why}
    for rid, tags in RUN_TAGS.items():
        kind = runs[rid]["kind"]
        for sid, note in tags.items():
            item = f"{kind}:C-{rid}"
            if item not in map(bare, new_ev[sid]):
                new_ev[sid].append(item)
            log["runs"].setdefault(sid, []).append(item)
            if note and note not in new_notes[sid]:
                new_notes[sid] = (new_notes[sid].rstrip() + " " + note).strip()
    for sid, items in new_ev.items():
        if sid in restated:
            continue
        prod = [bare(x)[8:] for x in items if bare(x).startswith("finding:")
                and audit.get(bare(x)[8:], {}).get("disposition") in oc.PRODUCT_DISPOSITIONS]
        if not prod:
            continue
        for k, x in enumerate(items):
            if bare(x).split(":")[0] in oc.MODEL_KINDS and not x.endswith("[model-only]"):
                items[k] = f"{x} [model-only]"
                log["model_only"].setdefault(sid, {"findings": prod, "items": []})["items"].append(bare(x))
            elif bare(x).split(":")[0] in oc.MODEL_KINDS:
                log["model_only"].setdefault(sid, {"findings": prod, "items": []})["items"].append(bare(x))
    # logged against the original submission, so a rerun writes the same log
    for r, p in sorted(restated.items()):
        new_ev[r] = list(new_ev[p])
        if p in orig and "; ".join(new_ev[r]) != orig[p][2][4]:
            log["restatements_updated"].append(r)
    for sid in sorted(rows):
        if sid in orig and new_notes[sid] != orig[sid][2][6]:
            log["notes"][sid] = {"old": orig[sid][2][6], "new": new_notes[sid]}
    # findings that no statement cites
    cited = {bare(x)[8:] for items in new_ev.values() for x in items if bare(x).startswith("finding:")}
    log["untagged_reproduced_findings"] = {
        fid: ("its intended text names no statement" if not SID.findall(str(f.get("intended", "")))
              else "every statement it names was rejected (FINDING_REJECT)")
        for fid, f in sorted(audit.items()) if f.get("disposition") in REPRODUCED and fid not in cited}
    log["rejected_findings"] = {f"{k[0]} {k[1]}": v for k, v in sorted(FINDING_REJECT.items())}
    log["rejected_runs"] = {f"{k[0]} {k[1]}": v for k, v in sorted(RUN_REJECT.items())}
    counts = {"finding_tags": sum(len(v) for v in log["findings"].values()),
              "run_tags_by_kind": {}, "statements_model_only": len(log["model_only"]),
              "items_model_only": sum(len(v["items"]) for v in log["model_only"].values()),
              "notes_changed": len(log["notes"]), "restatements_updated": len(log["restatements_updated"]),
              "untagged_reproduced_findings": len(log["untagged_reproduced_findings"])}
    for items in log["runs"].values():
        for x in items:
            k = x.split(":")[0]
            counts["run_tags_by_kind"][k] = counts["run_tags_by_kind"].get(k, 0) + 1
    log = {"counts": counts, **log}
    print(json.dumps(counts, sort_keys=True))
    if a.plan:
        return 0
    changed = 0
    by_file: Dict[Path, List[str]] = {}
    for sid, (p, i, c) in rows.items():
        lines = by_file.setdefault(p, p.read_text(encoding="utf-8").split("\n"))
        ev = "; ".join(new_ev[sid])
        if ev == c[4] and new_notes[sid] == c[6]:
            continue
        cells = {}
        if ev != c[4]:
            cells[4] = ev
        if new_notes[sid] != c[6]:
            cells[6] = new_notes[sid]
        lines[i] = replace_cells(lines[i], cells)
        changed += 1
    for p, lines in by_file.items():
        text = "\n".join(lines)
        if text != p.read_text(encoding="utf-8"):
            p.write_text(text, encoding="utf-8")
    (ont / "evidence-additions.json").write_text(json.dumps(log, indent=1, sort_keys=True, ensure_ascii=False)
                                                  + "\n", encoding="utf-8")
    print(f"rewrote {changed} statement rows; wrote {ont / 'evidence-additions.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
