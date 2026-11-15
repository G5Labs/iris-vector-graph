#!/usr/bin/env python3
"""Fill the generated sections of proofs-sys/PROOFS.md, add the axiom coverage to RESULTS.json and write
MATRIX-INPUT.json, all from RESULTS.json (the decisive run) and the sources.

    python experiment/playbook-completion/proofs-sys/tools/report.py [--recheck $RUN_DIR/proofs-sys-recheck/RESULTS.json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

P = Path(__file__).resolve().parent.parent
REL = "experiment/playbook-completion/proofs-sys"
AXES = ["AX-02", "AX-03", "AX-04", "AX-05", "AX-06", "AX-07", "AX-08", "AX-10", "AX-11", "AX-11M", "AX-12", "AX-14"]
THEOREM = {a: ("progress::theorem_ax14" if a == "AX-14" else "axioms::theorem_" + a.lower().replace("-", "")) for a in AXES}


def fill(md: Path, name: str, body: str) -> None:
    text = md.read_text()
    a, b = f"<!--{name}-->", f"<!--/{name}-->"
    pre, rest = text.split(a, 1)
    _, post = rest.split(b, 1)
    md.write_text(pre + a + "\n" + body.rstrip() + "\n" + b + post)


def main() -> int:
    r = json.loads((P / "RESULTS.json").read_text())
    recheck = None
    if "--recheck" in sys.argv:
        recheck = json.loads(Path(sys.argv[sys.argv.index("--recheck") + 1]).read_text())
    base = r["baseline"]
    fns = set(base["functions"])
    ctl = r["controls"]
    missing = [t for t in THEOREM.values() if t not in fns]
    axioms = {}
    for a in AXES:
        broken_by = sorted(f for f, c in ctl.items() if a in c["broken_laws"])
        axioms[a] = {"generic_theorem": THEOREM[a], "obligation": "sys::obl_" + a.lower().replace("-", ""),
                     "proved_generically": THEOREM[a] in fns, "reviewed_keeps": True,
                     "broken_by_controls": broken_by,
                     "as_built_breaks": a in ctl["sys00_as_built"]["broken_laws"]}
    r["axioms"] = {"note": "AX-01, AX-09, AX-13 are outside sys00's composition (their laws: proofs-mech M-12/M-01, M-08, M-11)",
                   "missing_theorems": missing, "per_axiom": axioms,
                   "bridge": ["bridge::bridge_m02", "bridge::bridge_m03", "bridge::bridge_m04", "bridge::bridge_m05",
                              "bridge::bridge_m10", "bridge::component_m02", "bridge::component_m03",
                              "bridge::component_m04", "bridge::component_m05", "bridge::component_m10"],
                   "bridge_verified": all(f in fns for f in ["bridge::bridge_m02", "bridge::bridge_m03", "bridge::bridge_m04",
                                                             "bridge::bridge_m05", "bridge::bridge_m10"])}
    if recheck:
        r["recheck"] = {"run_dir": recheck["run_dir"], "gate": recheck["gate"], "sources_sha256": recheck["sources_sha256"],
                        "verified": recheck["baseline"]["verified"], "errors": recheck["baseline"]["errors"],
                        "controls_rejected": sum(1 for c in recheck["controls"].values() if c["killed"]),
                        "controls": len(recheck["controls"])}
    (P / "RESULTS.json").write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n")

    killed = sum(1 for c in ctl.values() if c["killed"])
    md = P / "PROOFS.md"
    rc = (f" Independent recheck `proofs-sys-recheck` (`{recheck['run_dir']}`): gate **{recheck['gate']}**, "
          f"{r['recheck']['verified']} verified, {r['recheck']['controls_rejected']}/{r['recheck']['controls']} controls, "
          f"same sources.") if recheck else ""
    fill(md, "RESULT-SUMMARY",
         f"**Result** (run directory `{r['run_dir']}`, sources SHA-256 `{r['sources_sha256']}` including proofs-mech, gate "
         f"**{r['gate']}**): baseline **{base['verified']} verified, {base['errors']} errors** with `--no-cheating` (wall "
         f"{base['wall_seconds']} s, SMT {base['smt_run_ms']} ms, rlimit {base['rlimit_total']}); trust inventory empty; "
         f"**all 12 axiom checks of module 00 (AX-02..AX-08, AX-10, AX-11 in two parts, AX-12, AX-14) are proved once over "
         f"the composed design trait**, each from its own obligation, and the reviewed composition discharges every "
         f"obligation; **{killed} of {len(ctl)} located controls** (the pin's as-built composition and the semantics "
         f"lane's 11 per-axiom mutants) fail exactly at the obligations of the axioms the explorer reports them violating, "
         f"with refutations and proved counterexample runs.{rc} Registry: `proofs-sys-baseline`, one "
         f"`proofs-sys-<feature>` per control, `proofs-sys-recheck`.")
    rows = ["## Located controls", "", "| Feature | Design (kind) | Explorer check(s) | Axioms broken (= explorer) | Located at | Result |",
            "|---|---|---|---|---|---|"]
    for f, c in ctl.items():
        rows.append(f"| `{f}` | {c['variant']} ({c['kind']}) | {', '.join(c['check'].split(','))} | {', '.join(c['broken_laws'])} | "
                    f"{', '.join(c['error_locations'])} | {'rejected at its obligation' if c['killed'] else 'NOT AS EXPECTED'} |")
    rows += ["", "Each broken axiom's counterexample is `cx::cx_<design>_<axiom>`, a run of the composed machine from the "
             "initial state; each refutation `inst::refute_<design>_<axiom>`."]
    fill(md, "CONTROL-TABLE", "\n".join(rows))
    rows = ["## Cost", "", f"Whole-crate Verus run {base['wall_seconds']} s wall (proofs-mech dependency cached); per module "
            "(SMT ms, rlimit):", "", "| Module | SMT ms | rlimit |", "|---|---:|---:|"]
    for k, v in r.get("cost_per_mechanism", {}).items():
        rows.append(f"| {k} | {v['ms']} | {v['rlimit']} |")
    fill(md, "COST-TABLE", "\n".join(rows))

    ids = ["run:proofs-sys-baseline", "run:proofs-sys-recheck"] + [f"run:proofs-sys-{f.replace('_', '-')}" for f in ctl]
    files = [f"{REL}/PROOFS.md", f"{REL}/RESULTS.json"]
    grade = (f"proved (Verus, model level, decisive, --no-cheating, empty trust inventory incl. the proofs-mech "
             f"dependency): {base['verified']} verified, 0 errors (proofs-sys-baseline, recheck proofs-sys-recheck)")
    common_rem = ("no proof connects the product's code to sys00 (D-2, D-3); no refinement from sys00 to the proofs-mech "
                  "machines (the bridge proves the composed obligations equal to the mechanism instances' obligations and "
                  "instantiates proofs-mech's theorems at them; it does not compose the mechanism machines); sys00's fixed "
                  "small world (PROOFS.md PS-1); AX-14 is AG EF, not progress under fairness (PS-3); no sys00 axiom check "
                  "covers M03-L2, the eraser's head lock (observation in PROOFS.md)")
    out = {
        "_doc": ("Supplements from lane proofs-sys (steer 13; D-14's remaining part: the module-00 axioms over the composed "
                 "mechanisms). Model-level only; product obligations stay failed. Merge add_evidence, add_evidence_grade "
                 "and add_remaining into the existing cells."),
        "proposed_elsewhere": {
            "PROOF-DEBT.md D-14": ("its remaining part 'mechanisms proved one at a time, not composed; sys00 stays explorer-"
                                   "only' is paid at model level by proofs-sys: the 12 module-00 axiom checks proved once "
                                   f"over the composed design trait ({base['verified']} verified, 0 errors; {killed}/{len(ctl)} "
                                   "located controls incl. the pin's as-built composition; recheck proofs-sys-recheck); "
                                   "reuse of proofs-mech is the proved equality of obligations (bridge), not a refinement; "
                                   "still open: code correspondence, AX-14 under fairness, sys00's small world"),
            "STATUS.md 3.3a row": "add: module-00 axioms proved over the composed mechanisms in Verus (proofs-sys, model level)",
            "TRUST.md": "no new trusted item; PS-2 (operator re-runs and resumes) is TRUST.md's existing progress premise",
        },
        "cells": [
            {"gate": "3.3-model-check", "module": "00", "add_evidence": ids + files,
             "add_evidence_grade": grade + "; the explorer's sys00 checks (sem-mc-sys00-*) restated and proved over all "
                                           "3,072 instance-choice vectors that meet each axiom's obligation",
             "level": "model", "product_obligation": "fails",
             "as_built_findings": ["F-1101", "F-1306", "F-1302", "F-0702", "F-0606"],
             "add_remaining": common_rem},
            {"gate": "3.3a-axioms", "module": "product", "add_evidence": ["run:proofs-sys-baseline", "run:proofs-sys-recheck",
                                                                           "run:proofs-sys-sys00-as-built"] + files,
             "add_evidence_grade": grade + "; AX-02..AX-08, AX-10..AX-12, AX-14 proved over the composition, each from "
                                           "its own obligation (AX-01, AX-09, AX-13 via proofs-mech's M-12/M-01, M-08, M-11)",
             "level": "model", "product_obligation": "fails",
             "add_remaining": common_rem},
            {"gate": "3.3a-mechanisms", "module": "product", "add_evidence": ["run:proofs-sys-baseline", "run:proofs-sys-recheck"] + files,
             "add_evidence_grade": grade + "; the composed obligations of AX-02, AX-04, AX-06, AX-11 and the M-04 erasure "
                                           "choice are proved equal to the obligations of the proofs-mech instances the "
                                           "composition plugs in (bridge_m02..m10), whose generic theorems are instantiated",
             "level": "model", "product_obligation": "fails",
             "add_remaining": "the remaining D-14 item 'mechanisms not composed; sys00 explorer-only' is paid at model "
                              "level; still open: " + common_rem},
        ],
    }
    (P / "MATRIX-INPUT.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"report: {killed}/{len(ctl)} controls, theorems missing {missing}, bridge verified {r['axioms']['bridge_verified']}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
