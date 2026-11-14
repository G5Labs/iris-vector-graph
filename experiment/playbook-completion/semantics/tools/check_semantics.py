#!/usr/bin/env python3
"""Check the system semantics of the completion audit (playbook 3.3a gate):

  every object declares its lifecycle, mechanisms and axioms (or carries an explicit reason); every requirement
  traces to an axiom, a contract clause or a named exception, or is listed open; no dangling reference to an axiom,
  mechanism, law, exception, contract clause or finding; every mechanism law has a negative control that its model
  caught; every hand-rolled variant that departs from a law names a finding or an exception and has an as-built check
  that shows the departure.

    python3 check_semantics.py            # check the committed files; exit 1 on any violation
    python3 check_semantics.py --self-test  # the base passes with 0 violations and every seeded mutation is caught

Every message carries a rule tag. Inputs: semantics/{axioms,mechanisms,objects,lifecycles,trace}.json,
semantics/src/finding_classes.json, models/semantics/RESULTS.json, findings/audit/*.json, iris-contract/CONTRACT.md,
ontology/[0-9]*.md (parsed independently of the build and trace tools), and the product tree at the pin (sources).
"""
import copy
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEM = HERE.parent
ROOT = SEM.parent                 # experiment/playbook-completion
REPO = ROOT.parent.parent         # repository root (the product at the pin)
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
REQ_KINDS = {"B", "T", "I", "X", "P"}
SAME_MEANING_IDS = {"absent", "read", "restore", "erase", "live", "upgrade", "redact"}


def load_json(p):
    return json.loads(Path(p).read_text())


def parse_ontology():
    """Entities and requirement statements, parsed here (not taken from the tools under test)."""
    ents, reqs = [], []
    ent_re = re.compile(r"^Entity (.+?): states (.+?); commands (.+)$")
    for f in sorted(glob.glob(str(ROOT / "ontology" / "[0-9][0-9]-*.md"))):
        mod = Path(f).name[:2]
        in_st = False
        for line in Path(f).read_text().splitlines():
            m = ent_re.match(line.strip())
            if m:
                ents.append({"id": f"{mod}/{m.group(1).strip().lower().replace(' ', '-')}",
                             "states": [s.strip() for s in m.group(2).split(",")],
                             "commands": [c.strip() for c in m.group(3).split(",")]})
            if line.startswith("## "):
                in_st = line.strip() == "## Statements"
                continue
            if in_st and line.startswith("| ") and not line.startswith("| Id ") and not line.startswith("|---"):
                cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
                if len(cells) >= 3 and cells[2] in REQ_KINDS:
                    reqs.append(cells[0])
    return ents, reqs


def contract_ids():
    ids = set()
    for line in (ROOT / "iris-contract" / "CONTRACT.md").read_text().splitlines():
        m = re.match(r"^\| \**([EX]-[A-Z0-9-]+)\** \|", line)
        if m:
            ids.add(m.group(1))
    return ids


def finding_ids():
    ids = set()
    for p in sorted(glob.glob(str(ROOT / "findings" / "audit" / "*.json"))):
        d = load_json(p)
        lists = [d] if isinstance(d, list) else [v for v in d.values() if isinstance(v, list)]
        for lst in lists:
            for f in lst:
                if isinstance(f, dict) and "id" in f:
                    ids.add(f["id"])
    return ids


def load_all():
    ents, reqs = parse_ontology()
    return {
        "axioms": load_json(SEM / "axioms.json"),
        "mechanisms": load_json(SEM / "mechanisms.json"),
        "objects": load_json(SEM / "objects.json"),
        "lifecycles": load_json(SEM / "lifecycles.json"),
        "trace": load_json(SEM / "trace.json"),
        "classes": load_json(SEM / "src" / "finding_classes.json")["classes"],
        "results": load_json(ROOT / "models" / "semantics" / "RESULTS.json"),
        "findings": finding_ids(),
        "contract": contract_ids(),
        "entities": ents,
        "requirements": reqs,
    }


def source_ok(ref):
    """path[:a-b[, c-d]] at the pin; a bare file name is allowed only as a path that exists."""
    ref = ref.split(" ")[0]
    path, _, lines = ref.partition(":")
    p = REPO / path
    if not p.exists():
        return False
    if lines and p.is_file():
        n = len(p.read_text(errors="replace").splitlines())
        for part in re.findall(r"(\d+)(?:-(\d+))?", lines):
            hi = int(part[1] or part[0])
            if hi > n:
                return False
    return True


def check(d, skip_sources=False):
    err = []
    E = lambda tag, msg: err.append(f"[{tag}] {msg}")
    ax = {a["id"]: a for a in d["axioms"]["axioms"]}
    exc = {e["id"] for e in d["axioms"]["exceptions"]}
    dom = {c["id"] for c in d["axioms"]["contract_clauses"]["domain"]}
    mech = {m["id"]: m for m in d["mechanisms"]["mechanisms"]}
    laws = {m["id"]: {l["id"] for l in m["laws"]} for m in mech.values()}
    lcs = {l["id"]: l for l in d["lifecycles"]["lifecycles"]}
    checks = {c["id"]: c for c in d["results"]["checks"]}
    findings = d["findings"]

    # axioms
    if not 10 <= len(ax) <= 16:
        E("axiom-count", f"{len(ax)} axioms (about 12 expected)")
    for a in ax.values():
        for k in ("rule", "sources"):
            if not a.get(k):
                E("axiom", f"{a['id']} has no {k}")
        for m in a.get("mechanisms", []):
            if m not in mech:
                E("mechanism-ref", f"axiom {a['id']} names mechanism {m}")
        for x in a.get("exceptions", []):
            if x not in exc:
                E("exception-ref", f"axiom {a['id']} names exception {x}")
        for f in a.get("violating_findings", []):
            if f not in findings:
                E("finding-ref", f"axiom {a['id']} cites finding {f}")
        if not skip_sources:
            for s in a.get("sources", []):
                if not source_ok(s):
                    E("source", f"axiom {a['id']} source {s} not at the pin")
    for e in d["axioms"]["exceptions"]:
        if e["axiom"] not in ax:
            E("axiom-ref", f"exception {e['id']} names axiom {e['axiom']}")

    # finding classes: exactly the findings, and only known classes
    cls = d["classes"]
    for f in sorted(findings - set(cls)):
        E("finding-class", f"finding {f} has no class")
    for f, v in cls.items():
        if f not in findings:
            E("finding-ref", f"finding_classes names {f}")
        for c in v:
            if c not in ax and c not in {"FUNC", "DOC", "ENV", "TEST", "PERF", "NONE"}:
                E("axiom-ref", f"finding {f} class {c}")

    # mechanisms
    for m in mech.values():
        for a in m["implements"]:
            if a not in ax:
                E("axiom-ref", f"mechanism {m['id']} implements {a}")
        if not m["laws"]:
            E("law", f"mechanism {m['id']} has no law")
        for l in m["laws"]:
            ok = [c for c in l.get("controls", []) if c in checks and checks[c]["result"] == "met" and checks[c]["design"] == "control"]
            if not ok:
                E("control", f"law {l['id']} has no met negative control")
        for i in m["instances"]:
            if i["object"] not in {o["id"] for o in d["objects"]["objects"]}:
                E("object-ref", f"mechanism {m['id']} instance {i['object']}")
            for law in i.get("departs", []):
                if law not in laws[m["id"]]:
                    E("law-ref", f"{m['id']} {i['object']} departs from unknown law {law}")
            for f in i.get("findings", []):
                if f not in findings:
                    E("finding-ref", f"{m['id']} {i['object']} cites finding {f}")
            if i.get("exception") and i["exception"] not in exc:
                E("exception-ref", f"{m['id']} {i['object']} exception {i['exception']}")
            if i.get("departs") and not (i.get("findings") or i.get("exception")):
                E("departure", f"{m['id']} {i['object']} departs from {i['departs']} with no finding or exception")
            if i["use"] == "canonical" and i.get("departs"):
                E("departure", f"{m['id']} {i['object']} is canonical but departs")
            if i["use"] not in ("canonical", "hand-rolled"):
                E("departure", f"{m['id']} {i['object']} use {i['use']}")
            if i.get("model"):
                mc = i.get("model_checks", [])
                if not mc:
                    E("model", f"{m['id']} {i['object']} model {i['model']} has no check")
                for c in mc:
                    if c not in checks or checks[c]["result"] != "met" or checks[c]["scope"] != "exhaustive":
                        E("model", f"{m['id']} {i['object']} check {c} missing, not met or truncated")
                if i.get("departs"):
                    shown = [c for c in mc if checks.get(c, {}).get("design") in ("as-built", "exception")
                             and checks[c]["expectation"].startswith("violation") and any(checks[c]["law"].startswith(x) for x in i["departs"])]
                    if not shown:
                        E("model", f"{m['id']} {i['object']} departs from {i['departs']} but no as-built check shows it")
            elif not i.get("note"):
                E("model", f"{m['id']} {i['object']} has neither a model nor a reason")

    # objects
    ent_ids = [e["id"] for e in d["entities"]]
    obj = d["objects"]["objects"]
    if [o["id"] for o in obj] != ent_ids:
        E("objects-derived", "objects.json does not list exactly the ontology Entity lines in order")
    ents = {e["id"]: e for e in d["entities"]}
    for o in obj:
        oid = o["id"]
        lc = o.get("lifecycle")
        ref_lc = lc or o.get("closest_lifecycle")
        if not lc and not o.get("reason"):
            E("lifecycle", f"{oid} declares no lifecycle and no reason")
        if lc and lc not in lcs:
            E("lifecycle", f"{oid} lifecycle {lc} unknown")
        if ref_lc in lcs:
            st = {s["id"] for s in lcs[ref_lc]["states"]}
            cm = {c["id"] for c in lcs[ref_lc]["commands"]}
            e = ents.get(oid, {"states": [], "commands": []})
            if lc or o.get("state_map"):
                if set(o.get("state_map", {})) != set(e["states"]):
                    E("lifecycle", f"{oid} state map does not cover exactly its states")
            for k, v in o.get("state_map", {}).items():
                s = v if isinstance(v, str) else v.get("state")
                if s not in st:
                    E("lifecycle", f"{oid} state {k} -> {s} not a state of {ref_lc}")
            if set(o.get("command_map", {})) != set(e["commands"]):
                E("lifecycle", f"{oid} command map does not cover exactly its commands")
            for k, v in o.get("command_map", {}).items():
                if v not in cm:
                    E("lifecycle", f"{oid} command {k} -> {v} not a command of {ref_lc}")
        if not o.get("mechanisms") and not o.get("reason"):
            E("object-mechanism", f"{oid} uses no mechanism and carries no reason")
        for u in o.get("mechanisms", []):
            if u["mechanism"] not in mech:
                E("mechanism-ref", f"{oid} uses mechanism {u['mechanism']}")
        if not o.get("axioms") and not o.get("reason"):
            E("object-axiom", f"{oid} relies on no axiom and carries no reason")
        for a in o.get("axioms", []):
            if a not in ax:
                E("axiom-ref", f"{oid} relies on axiom {a}")
        for f in o.get("findings", []):
            if f not in findings:
                E("finding-ref", f"{oid} cites finding {f}")

    # lifecycle vocabulary: one name, one meaning
    meaning = {}
    for l in lcs.values():
        for kind in ("states", "commands"):
            for s in l[kind]:
                meaning.setdefault((kind, s["id"]), set()).add(s["meaning"])
    for (kind, sid), ms in meaning.items():
        if len(ms) > 1 and sid not in SAME_MEANING_IDS:
            E("vocabulary", f"{kind[:-1]} id '{sid}' has {len(ms)} meanings across lifecycles")

    # trace
    t = d["trace"]
    known = set(ax) | d["contract"] | dom | exc
    seen = {}
    for r in t["requirements"]:
        seen[r["id"]] = seen.get(r["id"], 0) + 1
        for tg in r.get("targets", []):
            if tg not in known:
                E("clause-ref", f"requirement {r['id']} targets unknown {tg}")
        for b in r.get("bases", []):
            if b.startswith("finding:") and b[8:] not in findings:
                E("finding-ref", f"requirement {r['id']} basis {b}")
        if r["status"] == "traced" and not r.get("targets"):
            E("trace", f"requirement {r['id']} traced with no target")
        if r["status"] not in ("traced", "open"):
            E("trace", f"requirement {r['id']} status {r['status']}")
    for rid in d["requirements"]:
        if seen.get(rid, 0) != 1:
            E("trace", f"requirement {rid} appears {seen.get(rid, 0)} times in trace.json")
    for rid in set(seen) - set(d["requirements"]):
        E("trace", f"trace.json lists {rid}, which is not a requirement")
    opened = sorted(r["id"] for r in t["requirements"] if r["status"] == "open")
    if opened != sorted(t.get("open", [])):
        E("trace", "the open list differs from the requirements with status open")
    if t.get("counts", {}).get("requirements") != len(t["requirements"]):
        E("trace", "counts.requirements differs from the number of requirements")

    # results
    if d["results"].get("pin") != PIN:
        E("results", "RESULTS.json pin differs")
    for c in d["results"]["checks"]:
        if c["result"] != "met":
            E("results", f"check {c['id']} not met")
    return err


MUTATIONS = [
    ("object without a lifecycle", "lifecycle", lambda d: [o.update(lifecycle=None) or o.pop("reason", None) for o in d["objects"]["objects"][:1]]),
    ("untraced requirement (dropped from the trace)", "trace", lambda d: d["trace"]["requirements"].pop(0)),
    ("requirement traced with no target", "trace", lambda d: next(r for r in d["trace"]["requirements"] if r["status"] == "traced").update(targets=[])),
    ("dangling axiom reference", "axiom-ref", lambda d: d["objects"]["objects"][0]["axioms"].append("AX-99")),
    ("dangling mechanism reference", "mechanism-ref", lambda d: d["objects"]["objects"][0]["mechanisms"].append({"mechanism": "M-99"})),
    ("dangling contract clause", "clause-ref", lambda d: d["trace"]["requirements"][0]["targets"].append("E-NOPE")),
    ("dangling law reference", "law-ref", lambda d: next(i for i in d["mechanisms"]["mechanisms"][0]["instances"] if i.get("departs"))["departs"].append("M01-L9")),
    ("finding id that does not exist", "finding-ref", lambda d: d["mechanisms"]["mechanisms"][0]["instances"][1]["findings"].append("F-9999")),
    ("finding id in the trace that does not exist", "finding-ref", lambda d: d["trace"]["requirements"][0]["bases"].append("finding:F-C9999")),
    ("dangling exception", "exception-ref", lambda d: d["axioms"]["axioms"][0]["exceptions"].append("EXC-99")),
    ("law without a control", "control", lambda d: d["mechanisms"]["mechanisms"][0]["laws"][0].update(controls=[])),
    ("departure with no finding", "departure", lambda d: (lambda i: i.update(findings=[]) or i.pop("exception", None))(next(i for i in d["mechanisms"]["mechanisms"][0]["instances"] if i.get("departs")))),
    ("state not mapped", "lifecycle", lambda d: d["objects"]["objects"][0]["state_map"].popitem()),
    ("object with no mechanism", "object-mechanism", lambda d: d["objects"]["objects"][0].update(mechanisms=[])),
    ("object missing from the derived list", "objects-derived", lambda d: d["objects"]["objects"].pop()),
    ("one id, two meanings", "vocabulary", lambda d: d["lifecycles"]["lifecycles"][2]["states"].append({"id": "stale", "meaning": "something else"})),
    ("finding without a class", "finding-class", lambda d: d["classes"].pop(next(iter(d["classes"])))),
    ("model check not met", "results", lambda d: d["results"]["checks"][0].update(result="not-met")),
]


def self_test():
    base = load_all()
    errs = check(base)
    if errs:
        print("base not clean:", *errs[:20], sep="\n  ")
        return 1
    failed = 0
    for name, tag, mut in MUTATIONS:
        d = copy.deepcopy(base)
        mut(d)
        got = check(d, skip_sources=True)
        hit = any(e.startswith(f"[{tag}]") for e in got)
        print(f"{'caught' if hit else 'MISSED'}: {name} -> [{tag}] ({len(got)} messages)")
        failed += 0 if hit else 1
    print(f"self-test: base 0 violations; {len(MUTATIONS) - failed} of {len(MUTATIONS)} seeded mutations caught")
    return 1 if failed else 0


def derived_fresh():
    """axioms.json, mechanisms.json and objects.json are what build_semantics.py writes from the sources."""
    sys.path.insert(0, str(HERE))
    import build_semantics
    out = []
    for name, data in build_semantics.build().items():
        if (SEM / name).read_text() != json.dumps(data, indent=1, ensure_ascii=False) + "\n":
            out.append(f"[derived-fresh] {name} is stale: rerun semantics/tools/build_semantics.py")
    return out


def main():
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    d = load_all()
    errs = check(d) + derived_fresh()
    for e in errs:
        print(e)
    o = d["objects"]["counts"]
    t = d["trace"]["counts"]
    print(f"semantics: {len(d['axioms']['axioms'])} axioms, {len(d['mechanisms']['mechanisms'])} mechanisms, "
          f"{len(d['lifecycles']['lifecycles'])} lifecycles, {o['objects']} objects ({o['with_lifecycle']} with a lifecycle, "
          f"{o['with_reason']} with a reason), {t['requirements']} requirements ({t['traced']} traced, {t['open']} open), "
          f"{len(d['results']['checks'])} model checks; {len(errs)} violations")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
