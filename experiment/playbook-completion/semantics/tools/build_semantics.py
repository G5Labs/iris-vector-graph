#!/usr/bin/env python3
"""Build semantics/axioms.json, mechanisms.json and objects.json from the hand-written sources.

    python3 build_semantics.py [--check]

Inputs (paths relative to experiment/playbook-completion/):
  semantics/src/axioms_src.json, src/mechanisms_src.json, src/objects_map.json, src/finding_classes.json,
  semantics/lifecycles.json, models/semantics/RESULTS.json, ontology/[0-9]*.md (Entity lines: the object list is
  derived mechanically from them), findings/audit/*.json.
Derived fields: each object's mechanisms (from the mechanism instance lists), axioms (union of its mechanisms'
`implements`), findings and hand-rolled variants; each mechanism instance's model checks (RESULTS.json checks of its
family and instance that list the object); each law's controls and as-built checks; each axiom's violating findings
(from finding_classes.json), the objects and modules relying on it, and its module-00 model checks.
--check: fail if the outputs are not what this script would write.
"""
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEM = HERE.parent
ROOT = SEM.parent  # experiment/playbook-completion
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
ENTITY = re.compile(r"^Entity (.+?): states (.+?); commands (.+)$")


def load(p):
    return json.loads(Path(p).read_text())


def ontology_objects():
    out = []
    for f in sorted(glob.glob(str(ROOT / "ontology" / "[0-9][0-9]-*.md"))):
        mod = Path(f).name[:2]
        for n, line in enumerate(Path(f).read_text().splitlines(), 1):
            m = ENTITY.match(line.strip())
            if m:
                name = m.group(1).strip()
                out.append({
                    "id": f"{mod}/{name.lower().replace(' ', '-')}", "module": mod, "entity": name,
                    "ontology": f"experiment/playbook-completion/ontology/{Path(f).name}:{n}",
                    "states": [s.strip() for s in m.group(2).split(",")],
                    "commands": [c.strip() for c in m.group(3).split(",")],
                })
    return out


def all_findings():
    ids = {}
    for p in sorted(glob.glob(str(ROOT / "findings" / "audit" / "*.json"))):
        d = load(p)
        lists = [d] if isinstance(d, list) else [v for v in d.values() if isinstance(v, list)]
        for lst in lists:
            for f in lst:
                if isinstance(f, dict) and "id" in f:
                    ids.setdefault(f["id"], f)
    return ids


def build():
    ax = load(SEM / "src" / "axioms_src.json")
    mech = load(SEM / "src" / "mechanisms_src.json")
    omap = load(SEM / "src" / "objects_map.json")["objects"]
    fclass = load(SEM / "src" / "finding_classes.json")["classes"]
    res = load(ROOT / "models" / "semantics" / "RESULTS.json")
    checks = res["checks"]
    by_check = {c["id"]: c for c in checks}
    findings = all_findings()

    # objects (mechanical list) with their mechanism uses
    objs = ontology_objects()
    by_id = {o["id"]: o for o in objs}
    implements = {m["id"]: m["implements"] for m in mech["mechanisms"]}
    for o in objs:
        mp = omap.get(o["id"], {})
        o["lifecycle"] = mp.get("lifecycle")
        if "closest" in mp:
            o["closest_lifecycle"] = mp["closest"]
        if mp.get("reason"):
            o["reason"] = mp["reason"]
        o["state_map"] = mp.get("state_map", {})
        o["command_map"] = mp.get("command_map", {})
        if mp.get("notes"):
            o["notes"] = mp["notes"]
        o["mechanisms"] = []
    lawid = lambda name: name.split(" ")[0]
    for m in mech["mechanisms"]:
        fam = m["family"]
        for inst in m["instances"]:
            inst_checks = []
            models = inst.get("model", [])
            models = [models] if isinstance(models, str) else models
            for ref in models:
                f, n = ref.split("/", 1)
                inst_checks += [c["id"] for c in checks if c["family"] == f and c["instance"] == n and inst["object"] in c["objects"]]
            inst["model_checks"] = inst_checks
            # laws the instance's as-built model violates: the complement sets of its Keep checks, plus the attributed
            # law of its as-built progress or liveness violations (not run through Keep)
            ab = [cid_ for cid_ in inst_checks if by_check[cid_]["design"] in ("as-built", "exception")]
            violated = set()
            for cid_ in ab:
                c = by_check[cid_]
                violated |= {lawid(v) for v in (c.get("violates") or [])}
                if c["expectation"].startswith("violation") and c.get("violates") is None:
                    violated.add(lawid(c["law"]))
            inst["violated_laws"] = sorted(violated) if models else None
            inst["departs"] = sorted({d["law"] for d in inst.get("departures", [])})
            inst["findings"] = sorted({f for d in inst.get("departures", []) for f in d.get("findings", [])} | set(inst.get("related_findings", [])))
            use = {k: inst[k] for k in ("use", "where", "departures", "departs", "findings", "exception_note", "model", "note", "violated_laws") if k in inst}
            use["mechanism"] = m["id"]
            use["model_checks"] = inst_checks
            if inst["object"] in by_id:
                by_id[inst["object"]]["mechanisms"].append(use)
        for law in m["laws"]:
            law["controls"] = [c["id"] for c in checks if c["family"] == fam and c["design"] == "control" and c["law"].startswith(law["id"] + " ")]
            law["as_built_violations"] = [c["id"] for c in checks if c["family"] == fam and c["design"] in ("as-built", "exception")
                                          and c["law"].startswith(law["id"] + " ") and c["expectation"].startswith("violation")]
            law["also_violated_by"] = [c["id"] for c in checks if c["family"] == fam and c["design"] in ("as-built", "exception", "control")
                                       and not c["law"].startswith(law["id"] + " ") and any(lawid(v) == law["id"] for v in (c.get("violates") or []))]
            law["sharpness"] = [c["id"] for c in checks if c["family"] == fam and c["kind"] == "sharpness"]
        m["model"] = {"crate": "experiment/playbook-completion/models/semantics", "family": fam,
                      "checks": len([c for c in checks if c["family"] == fam]),
                      "checks_met": len([c for c in checks if c["family"] == fam and c["result"] == "met"]),
                      "scope": sorted({c["scope"] for c in checks if c["family"] == fam})}
    for o in objs:
        o["axioms"] = sorted({a for u in o["mechanisms"] for a in implements.get(u["mechanism"], [])})
        o["hand_rolled"] = sorted({u["mechanism"] for u in o["mechanisms"] if u.get("use") == "hand-rolled"})
        o["findings"] = sorted({f for u in o["mechanisms"] for f in u.get("findings", [])})

    # axioms: violating findings, reliance, module-00 checks
    sys_checks = [c for c in checks if c["family"] == "sys00"]
    for a in ax["axioms"]:
        a["mechanisms"] = [m["id"] for m in mech["mechanisms"] if a["id"] in m["implements"]]
        a["violating_findings"] = sorted(f for f, cl in fclass.items() if a["id"] in cl)
        a["violating_findings_by_severity"] = {}
        for f in a["violating_findings"]:
            sev = findings.get(f, {}).get("severity", "?")
            a["violating_findings_by_severity"].setdefault(sev, []).append(f)
        rel = [o["id"] for o in objs if a["id"] in o["axioms"]]
        a["relied_on_by"] = {"objects": rel, "modules": sorted({r[:2] for r in rel})}
        a["module00_checks"] = [c["id"] for c in sys_checks if c["law"].startswith(a["id"] + " ")]
    ax_out = {
        "_doc": "Universal axioms of IVG (playbook 3.3a step 1), semantics lane, steer 7. Built by semantics/tools/build_semantics.py from src/axioms_src.json; violating_findings from src/finding_classes.json (hand classification of every finding), relied_on_by from objects.json, module00_checks from models/semantics/RESULTS.json (family sys00). Sources are paths at the pin.",
        "pin": PIN,
        "axioms": ax["axioms"], "exceptions": ax["exceptions"], "contract_clauses": ax["contract_clauses"],
        "finding_classes_summary": {k: sum(1 for v in fclass.values() if k in v) for k in sorted({c for v in fclass.values() for c in v})},
        "findings_total": len(fclass),
        "findings_violating_an_axiom": sum(1 for v in fclass.values() if any(c.startswith("AX-") for c in v)),
    }
    mech_out = {
        "_doc": "Shared mechanisms of IVG (playbook 3.3a step 2). Built by semantics/tools/build_semantics.py from src/mechanisms_src.json and models/semantics/RESULTS.json. Each law lists its negative controls and the as-built checks that violate it; each instance lists the model checks run for that object.",
        "pin": PIN, "mechanisms": mech["mechanisms"], "unattached_objects": mech.get("unattached_objects", {}),
        "results": {"checks": len(checks), "met": len([c for c in checks if c["result"] == "met"]),
                    "truncated": len([c for c in checks if c["scope"] != "exhaustive"]),
                    "violation_checks_with_complement": len([c for c in checks if c["expectation"].startswith("violation") and c.get("violates") is not None]),
                    "of_which_also_violate_another_law": len([c for c in checks if c["expectation"].startswith("violation") and c.get("also_violates")])},
    }
    obj_out = {
        "_doc": "Every object (ontology Entity line) of every module, with its canonical lifecycle (lifecycles.json), the state and command mapping (src/objects_map.json), the mechanisms it uses (src/mechanisms_src.json instances) and the axioms those implement. Built by semantics/tools/build_semantics.py; the object list is derived from the ontology, not by hand. Module 00 declares no entity (its statements are the axioms' sources).",
        "pin": PIN, "objects": objs,
        "counts": {"objects": len(objs), "with_lifecycle": len([o for o in objs if o["lifecycle"]]),
                   "with_reason": len([o for o in objs if not o["lifecycle"] and o.get("reason")]),
                   "with_hand_rolled": len([o for o in objs if o["hand_rolled"]])},
    }
    return {"axioms.json": ax_out, "mechanisms.json": mech_out, "objects.json": obj_out}


def main():
    out = build()
    check = "--check" in sys.argv
    bad = []
    for name, data in out.items():
        text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
        p = SEM / name
        if check:
            if not p.exists() or p.read_text() != text:
                bad.append(name)
        else:
            p.write_text(text)
    if check and bad:
        raise SystemExit(f"stale: {bad}")
    print("ok" if check else "written: " + ", ".join(out))


if __name__ == "__main__":
    main()
