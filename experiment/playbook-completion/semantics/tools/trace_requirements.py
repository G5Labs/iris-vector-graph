#!/usr/bin/env python3
"""Requirement trace for playbook 3.3a ("every requirement traces to an axiom, a contract clause or a named exception").

    python3 experiment/playbook-completion/semantics/tools/trace_requirements.py [--check]

A requirement is every statement of kind B (business rule), T (technical rule), I (invariant), X (refusal) or P
(premise) in the Statements tables of experiment/playbook-completion/ontology/[0-9]*.md, all 19 modules (00-18).
Kinds R (module roots), D (definitions and their restatements) and Q (open questions, which name a human decision
instead of a rule) are not requirements.

Targets: an axiom (semantics/src/axioms_src.json), an IRIS environment contract clause (first column of the Clauses
tables of iris-contract/CONTRACT.md), a domain or functional contract clause (DC-REPLAY, DC-FUNC-NN in
axioms_src.json contract_clauses) or a named exception (EXC-NN in axioms_src.json). Bases, applied in this order and
all recorded:
  repairs          SYS-I1..SYS-I10 -> the axiom whose "repairs" lists it
  finding:<id>     the statement's Evidence cites a finding classed with AX-* in src/finding_classes.json
  kind             every X statement -> AX-03
  rule:<id>        a regex rule of src/trace_rules.json matches the statement (or its Notes, where the rule says so)
  explicit         src/trace_explicit.json places the statement by hand
  fallback:functional   a B or T statement (modules 01-18) with no target from the bases above -> DC-FUNC-<module>
I, X and P statements get no fallback: without a target they are open. Writes semantics/trace.json; --check
compares instead of writing and exits 1 on a difference.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEM = HERE.parent
COMP = SEM.parent
ONTO = COMP / "ontology"
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
REQ_KINDS = ("B", "T", "I", "X", "P")


def die(msg):
    raise SystemExit("trace_requirements: " + msg)


def split_row(line):
    cells = re.split(r"(?<!\\)\|", line.strip())[1:-1]
    return [c.strip().replace("\\|", "|") for c in cells]


def statements():
    out = []
    for f in sorted(ONTO.glob("[0-9][0-9]-*.md")):
        mod = f.name[:2]
        sec = None
        for line in f.read_text().splitlines():
            if line.startswith("## "):
                sec = line.strip()
                continue
            if sec != "## Statements" or not line.startswith("| ") or line.startswith("| Id ") or line.startswith("|---"):
                continue
            c = split_row(line)
            if len(c) != 7:
                die(f"{f.name}: statement row with {len(c)} cells: {line[:80]}")
            out.append({"id": c[0], "parent": c[1], "kind": c[2], "statement": c[3], "evidence": c[4],
                        "source": c[5], "notes": c[6], "module": mod})
    ids = [s["id"] for s in out]
    dup = [i for i, n in Counter(ids).items() if n > 1]
    if dup:
        die(f"duplicate statement ids {dup}")
    return out


def contract_clauses():
    ids = []
    sec = None
    for line in (COMP / "iris-contract" / "CONTRACT.md").read_text().splitlines():
        if line.startswith("## "):
            sec = line.strip()
            continue
        if sec and sec.startswith("## Clauses") and line.startswith("| "):
            first = split_row(line)[0].replace("*", "").strip()
            if re.fullmatch(r"[EX]-[A-Z0-9-]+", first):
                ids.append(first)
    if not ids:
        die("no contract clauses parsed from CONTRACT.md")
    v2 = COMP / "contract-2" / "VALIDATED.json"
    if v2.exists():
        ids += [k for k, c in json.loads(v2.read_text())["clauses"].items() if c.get("result") == "pass" and k not in ids]
    return ids


def outside_premises():
    """Named premises the contract-2 lane holds outside the contract (assumed): P2-* ids from coverage.json families,
    and P2-ABSENT for its 'absent' family (features absent on IRIS 2026.1 Community)."""
    cov = COMP / "contract-2" / "coverage.json"
    if not cov.exists():
        return set()
    out = set()
    for key, fam in json.loads(cov.read_text())["families"].items():
        m = re.match(r"(P2-[A-Z0-9]+)", fam["premise"])
        out.add(m.group(1) if m else "P2-" + key.upper())
    return out


def main():
    check = "--check" in sys.argv
    ax_src = json.loads((SEM / "src" / "axioms_src.json").read_text())
    axioms = [a["id"] for a in ax_src["axioms"]]
    repairs = {r: a["id"] for a in ax_src["axioms"] for r in a.get("repairs", [])}
    exceptions = [e["id"] for e in ax_src["exceptions"]]
    domain = [d["id"] for d in ax_src["contract_clauses"]["domain"]]
    clauses = contract_clauses()
    premises = outside_premises()
    known = set(axioms) | set(exceptions) | set(domain) | set(clauses)
    classes = json.loads((SEM / "src" / "finding_classes.json").read_text())["classes"]
    rules = json.loads((SEM / "src" / "trace_rules.json").read_text())["rules"]
    explicit_src = json.loads((SEM / "src" / "trace_explicit.json").read_text())
    explicit = explicit_src["statements"]
    open_reasons = explicit_src.get("open_reasons", {})

    rule_ids = [r["id"] for r in rules]
    if len(set(rule_ids)) != len(rule_ids):
        die("duplicate rule ids")
    compiled = []
    for r in rules:
        for t in r["targets"]:
            if t not in known:
                die(f"rule {r['id']}: unknown target {t}")
        compiled.append((r, re.compile(r["pattern"], re.IGNORECASE)))

    stmts = statements()
    by_id = {s["id"]: s for s in stmts}
    for sid in open_reasons:
        if sid not in by_id:
            die(f"open_reasons: {sid} is not an ontology statement")
    for sid, e in explicit.items():
        if sid not in by_id:
            die(f"trace_explicit: {sid} is not an ontology statement")
        if by_id[sid]["kind"] not in REQ_KINDS:
            die(f"trace_explicit: {sid} is kind {by_id[sid]['kind']}, not a requirement")
        for t in e["targets"]:
            if t not in known:
                die(f"trace_explicit {sid}: unknown target {t}")

    reqs = []
    for s in stmts:
        if s["kind"] not in REQ_KINDS:
            continue
        detail = {}

        def add(basis, targets):
            ts = [t for t in targets if t]
            for t in ts:
                if t not in known:
                    die(f"{s['id']}: basis {basis} gives unknown target {t}")
            if ts:
                detail.setdefault(basis, [])
                for t in ts:
                    if t not in detail[basis]:
                        detail[basis].append(t)

        if s["id"] in repairs:
            add("repairs", [repairs[s["id"]]])
        for fid in re.findall(r"finding:(F-[A-Z0-9]+)", s["evidence"]):
            if fid not in classes:
                die(f"{s['id']}: cites {fid}, which src/finding_classes.json does not class")
            add("finding:" + fid, [c for c in classes[fid] if c.startswith("AX-")])
        if s["kind"] == "X":
            add("kind", ["AX-03"])
        for r, rx in compiled:
            if "kinds" in r and s["kind"] not in r["kinds"]:
                continue
            if "modules" in r and s["module"] not in r["modules"]:
                continue
            if "not_modules" in r and s["module"] in r["not_modules"]:
                continue
            text = " ".join(s[f] for f in r.get("fields", ["statement"]))
            if rx.search(text):
                add("rule:" + r["id"], r["targets"])
        if s["id"] in explicit:
            add("explicit", explicit[s["id"]]["targets"])
        if not detail and s["kind"] in ("B", "T") and s["module"] != "00":
            add("fallback:functional", ["DC-FUNC-" + s["module"]])
        targets = []
        for ts in detail.values():
            for t in ts:
                if t not in targets:
                    targets.append(t)
        entry = {"id": s["id"], "module": s["module"], "kind": s["kind"], "targets": targets,
                 "bases": list(detail), "detail": detail, "status": "traced" if targets else "open"}
        if s["id"] in open_reasons:
            if targets:
                die(f"open_reasons names {s['id']}, which is traced ({targets})")
            r = open_reasons[s["id"]]
            if isinstance(r, dict):
                entry["open_reason"] = r["reason"]
                if r.get("premise"):
                    if r["premise"] not in premises:
                        die(f"open_reasons {s['id']}: unknown outside premise {r['premise']}")
                    entry["outside_premise"] = r["premise"]
            else:
                entry["open_reason"] = r
        reqs.append(entry)

    def cat(t):
        if t in axioms:
            return "axiom"
        if t in clauses:
            return "contract"
        if t in exceptions:
            return "exception"
        return "domain"

    counts = {
        "requirements": len(reqs),
        "by_kind": dict(sorted(Counter(r["kind"] for r in reqs).items())),
        "traced": sum(r["status"] == "traced" for r in reqs),
        "open": sum(r["status"] == "open" for r in reqs),
        "by_basis": dict(sorted(Counter(b.split(":")[0] for r in reqs for b in r["bases"]).items())),
        "by_basis_exact": dict(sorted(Counter(b for r in reqs for b in r["bases"]).items())),
        "axiom_traced": sum(any(cat(t) == "axiom" for t in r["targets"]) for r in reqs),
        "functional_only": sum(r["bases"] == ["fallback:functional"] for r in reqs),
        "contract_traced": sum(any(cat(t) == "contract" for t in r["targets"]) for r in reqs),
        "exception_traced": sum(any(cat(t) == "exception" for t in r["targets"]) for r in reqs),
        "domain_replay_traced": sum("DC-REPLAY" in r["targets"] for r in reqs),
        "by_target": dict(sorted(Counter(t for r in reqs for t in r["targets"]).items())),
        "open_by_kind": dict(sorted(Counter(r["kind"] for r in reqs if r["status"] == "open").items())),
        "open_by_module": dict(sorted(Counter(r["module"] for r in reqs if r["status"] == "open").items())),
        "open_with_reason": sum(r["status"] == "open" and "open_reason" in r for r in reqs),
        "open_with_outside_premise": sum(r["status"] == "open" and "outside_premise" in r for r in reqs),
        "open_by_outside_premise": dict(sorted(Counter(r.get("outside_premise", "none") for r in reqs if r["status"] == "open").items())),
    }
    bm = defaultdict(lambda: Counter())
    for r in reqs:
        c = bm[r["module"]]
        c["requirements"] += 1
        c[r["status"]] += 1
        c["axiom_traced"] += any(cat(t) == "axiom" for t in r["targets"])
        c["functional_only"] += r["bases"] == ["fallback:functional"]
        c["contract_traced"] += any(cat(t) == "contract" for t in r["targets"])
        c["exception_traced"] += any(cat(t) == "exception" for t in r["targets"])
    counts["by_module"] = {m: dict(bm[m]) for m in sorted(bm)}

    out = {
        "_doc": "Generated by experiment/playbook-completion/semantics/tools/trace_requirements.py from the ontology "
                "statements, src/trace_rules.json, src/trace_explicit.json, src/finding_classes.json and "
                "src/axioms_src.json. Do not edit; rerun the script. Each requirement lists its targets, the bases "
                "that gave them (detail maps basis -> targets) and its status; open requirements are also listed "
                "in 'open'. Rule-based traces are a mechanical classification; their measured precision is in "
                "data/trace_sample_review.json.",
        "pin": PIN,
        "generated_by": "experiment/playbook-completion/semantics/tools/trace_requirements.py",
        "definition": "A requirement is every ontology statement (experiment/playbook-completion/ontology/NN-*.md, "
                      "Statements tables, all 19 modules 00-18) of kind B (business rule: what a user, tenant or "
                      "operator can rely on), T (technical rule: how the product does it), I (invariant), X "
                      "(refusal) or P (premise about IRIS, the driver or the operator). R (module roots), D "
                      "(definitions, including local restatements) and Q (open questions, which name a human "
                      "decision rather than state a rule) are not requirements. The ontology is the audit's one "
                      "source-cited statement of intent for every module (literal 3.1 rule, 3,877 statements); the "
                      "specs' FR-/SC- ids cover only some modules (no spec for vectors, interfaces or operations), "
                      "and the ontology already cites the FR ids it restates in Source/Notes.",
        "targets_known": {"axioms": axioms, "contract_clauses": clauses, "domain": domain, "exceptions": exceptions},
        "outside_premises_known": sorted(premises),
        "contract_sources": ["experiment/playbook-completion/iris-contract/CONTRACT.md (round r6)",
                             "experiment/playbook-completion/contract-2/VALIDATED.json (contract-2 lane, result pass)"],
        "counts": counts,
        "requirements": reqs,
        "open": [r["id"] for r in reqs if r["status"] == "open"],
    }
    text = json.dumps(out, indent=1) + "\n"
    dest = SEM / "trace.json"
    if check:
        if not dest.exists() or dest.read_text() != text:
            print("trace.json is stale")
            sys.exit(1)
        print("trace.json is current")
        return
    dest.write_text(text)
    c = counts
    print(f"requirements {c['requirements']} {c['by_kind']}; traced {c['traced']}, open {c['open']} {c['open_by_kind']}; "
          f"axiom {c['axiom_traced']}, functional-only {c['functional_only']}, contract {c['contract_traced']}, "
          f"exception {c['exception_traced']}; bases {c['by_basis']}")


if __name__ == "__main__":
    main()
