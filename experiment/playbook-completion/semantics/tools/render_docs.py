#!/usr/bin/env python3
"""Render semantics/AXIOMS.md and semantics/MECHANISMS.md from axioms.json, mechanisms.json and the sources.

    python3 render_docs.py [--check]

Run after build_semantics.py. --check fails if either file differs from what this script writes.
"""
import json
import sys
from pathlib import Path

SEM = Path(__file__).resolve().parent.parent


def load(n):
    return json.loads((SEM / n).read_text())


def axioms_md():
    a = load("axioms.json")
    fc = load("src/finding_classes.json")["classes"]
    summ = a["finding_classes_summary"]
    new = {"AX-10", "AX-11", "AX-12", "AX-13", "AX-14"}
    old = {f"AX-0{i}" for i in range(1, 10)}
    n_new = [f for f, v in fc.items() if set(v) & new]
    only_new = [f for f in n_new if not set(fc[f]) & old]
    L = ["# Universal axioms of IVG (playbook 3.3a step 1)\n",
         "Product pin `3eaa79cf`. Semantics lane. Machine-readable: `axioms.json` (built by `tools/build_semantics.py` from",
         "`src/axioms_src.json`; violating findings from the hand classification `src/finding_classes.json`; reliance from",
         "`objects.json`; module-00 checks from `models/semantics/RESULTS.json`). Rendered by `tools/render_docs.py`. Checked by",
         "`tools/check_semantics.py` (`sem-check-r2`, self-test `sem-check-selftest-r2`).\n",
         "The original slice-only semantics (`experiment/playbook-uplift/semantics/SEMANTICS.md`) used the ten system statements",
         "SYS-I1..SYS-I10 of `ontology/00-system.md`. Here they are repaired and extended to fourteen axioms for the whole product:",
         "SYS-I3 and SYS-I9 merge into one (the playbook's \"explicit, recorded refusals\"); SYS-I1, I2, I4..I8 and I10 are kept with",
         "the repairs stated per axiom; five are new (AX-10..AX-14: removal reach, serialization, truthful outcomes, capability,",
         f"progress), because {len(n_new)} of the {a['findings_total']} findings in `findings/audit/` break one of them and {len(only_new)} of those break",
         "no rule a SYS statement stated. The ontology's SYS-I statements are not edited (ontology lane); the repair is proposed here.\n",
         f"Each finding was classified by hand against the axioms (`src/finding_classes.json`, {a['findings_total']} findings, every one exactly",
         "once; the checker fails when a new finding appears unclassified). Classes outside the axioms: FUNC (a module's own",
         f"functional contract; {summ.get('FUNC', 0)}), DOC (document against code; {summ.get('DOC', 0)}), ENV ({summ.get('ENV', 0)}), TEST ({summ.get('TEST', 0)}), "
         f"PERF (performance or capacity; {summ.get('PERF', 0)}), NONE (refuted or not reproduced; {summ.get('NONE', 0)}).",
         f"{a['findings_violating_an_axiom']} of {a['findings_total']} findings break at least one axiom.\n",
         "## The axioms\n",
         "| Id | Axiom | Rule | Repairs | Mechanisms | Objects (modules) relying | Findings breaking it (S1/S2/S3/S4) | Exceptions |",
         "|---|---|---|---|---|---|---|---|"]
    for x in a["axioms"]:
        s = x["violating_findings_by_severity"]
        sev = "/".join(str(len(s.get(k, []))) for k in ("S1", "S2", "S3", "S4"))
        L.append(f"| {x['id']} | {x['name']} | {x['rule']} | {', '.join(x['repairs']) or 'new'} | {', '.join(x['mechanisms'])} | "
                 f"{len(x['relied_on_by']['objects'])} ({len(x['relied_on_by']['modules'])}) | {len(x['violating_findings'])} ({sev}) | {', '.join(x['exceptions']) or '-'} |")
    L.append("\n## Repairs, sources and the findings that break each axiom\n")
    for x in a["axioms"]:
        L.append(f"### {x['id']} {x['name']}\n")
        L.append(f"- Rule: {x['rule']}")
        L.append(f"- Formal reading: `{x['formal']}`")
        L.append(f"- Repair: {x['repair_note']}")
        L.append(f"- Sources at the pin: {'; '.join('`' + s + '`' for s in x['sources'])}")
        L.append(f"- Implemented by: {', '.join(x['mechanisms'])}; relied on by {len(x['relied_on_by']['objects'])} objects in modules {', '.join(x['relied_on_by']['modules'])}")
        if x["module00_checks"]:
            L.append(f"- Module-00 model checks (composed mechanisms, `models/semantics/src/sys00.rs`): {', '.join('`' + c + '`' for c in x['module00_checks'])}")
        else:
            L.append(f"- Not in the module-00 composition; its laws are checked by the generic machines of {', '.join(x['mechanisms'])}")
        for k in ("S1", "S2", "S3", "S4"):
            v = x["violating_findings_by_severity"].get(k)
            if v:
                L.append(f"- As-built findings breaking it, {k}: {', '.join(v)}")
        L.append("")
    L += ["## Named exceptions\n", "| Id | Axiom | Exception | Source |", "|---|---|---|---|"]
    for e in a["exceptions"]:
        L.append(f"| {e['id']} | {e['axiom']} | {e['name']}: {e['rule']} | {'; '.join('`' + s + '`' for s in e['sources'])} |")
    L += ["\n## Contract clauses a requirement may trace to\n",
          "Besides an axiom or a named exception, a requirement (`trace.json`) may trace to a clause of the IRIS environment contract",
          "(`iris-contract/CONTRACT.md`, ids E-* and X-*), to the domain contract DC-REPLAY (replay of the ledger equals the governed",
          "store; the 3.3a-domain-contract cell) or to a module's functional contract DC-FUNC-NN (what that module's commands compute,",
          "formalised by its L1 model in the D-1 crate named in `axioms.json`). A DC-FUNC trace is the weakest kind: it says the",
          "statement is a functional rule of its module, which no universal axiom governs; nothing checks that the L1 model encodes",
          "each such statement."]
    return "\n".join(L) + "\n"


def mechanisms_md():
    m = load("mechanisms.json")
    a = {x["id"]: x for x in load("axioms.json")["axioms"]}
    fc = load("src/finding_classes.json")["classes"]
    r = m["results"]
    L = ["# Shared mechanisms of IVG (playbook 3.3a step 2)\n",
         "Product pin `3eaa79cf`. Semantics lane. Machine-readable: `mechanisms.json` (built by `tools/build_semantics.py` from",
         "`src/mechanisms_src.json` and `models/semantics/RESULTS.json`); rendered by `tools/render_docs.py`. Models:",
         "`models/semantics/` (explorer and actors at `c03f9fa`), one file per mechanism.\n",
         "**How the models are generic.** Each mechanism is one machine generic over a trait (`LedgerObject`, `RetryObject`,",
         "`ExclObject`, `DerivedObject`, ...). Each object (or group of objects with the same variant) that uses the mechanism is",
         "one trait instance that declares its as-built variant (the policies, programs or paths the pin implements, each with",
         "the source lines in the file's comments) and the reviewed variant (the mechanism's canonical policies). The laws are",
         "written once per machine; an instance adds no law. Per instance: as-built checks attributed with `Keep::only` to the law",
         "each variant departs from (the shortest counterexample violates that law), or a pass where the pin keeps every law, and a",
         "reviewed check expected to pass. Per mechanism: at least one negative control per law (a generic mutant of a canonical",
         "instance) and sharpness witnesses. Every check is exhaustive within its declared bounds; none was truncated. All of it is",
         "model-level: a twin abstracts the cited code, it is not the code; these are explorer checks, not Verus lemmas over the",
         "trait (PROOF-DEBT D-14).\n",
         "**Attribution and the complement (review 4, R4-08).** `Keep::only` keeps only the attributed law, so a counterexample is",
         "a violation *of that law*, not proof that no other law is violated. Since the rerun every Keep check also runs the",
         "complement: each safety law of the underlying model explored alone, recorded in `RESULTS.json` (`violates`,",
         f"`also_violates`). Of the {r['violation_checks_with_complement']} violation checks, {r['of_which_also_violate_another_law']} also violate another law; they are listed per",
         "law below (`also violated by`). For every instance, the laws its as-built model violates equal its declared departures,",
         "each with a finding or a named exception (`check_semantics.py`, rules `departure-undeclared` and `departure-unshown`);",
         "a departure that is a consequence of the same defect in the model says so in its `why`.\n",
         f"Results: {r['checks']} checks, {r['met']} met their expectation, {r['truncated']} truncated (`sem-mc-all-r2`; per family",
         "`sem-mc-<family>-as-built-r2` expected-violation, `sem-mc-<family>-reviewed-r2` pass, `sem-control-<family>-r2`",
         "expected-violation).\n",
         "## Summary\n",
         "| Id | Mechanism | Implements | Laws | Objects using it (canonical / hand-rolled) | Declared departures (law, object) | Checks |",
         "|---|---|---|---:|---|---:|---:|"]
    for x in m["mechanisms"]:
        ins = x["instances"]
        hr = [i for i in ins if i["use"] == "hand-rolled"]
        nd = sum(len(i.get("departures", [])) for i in ins)
        L.append(f"| {x['id']} | {x['name']} | {', '.join(x['implements'])} | {len(x['laws'])} | {len(ins)} ({len(ins) - len(hr)} / {len(hr)}) | {nd} | {x['model']['checks']} |")
    for x in m["mechanisms"]:
        L.append(f"\n## {x['id']} {x['name']}\n")
        L.append(f"- Implements: {', '.join(i + ' ' + a[i]['name'] for i in x['implements'])}")
        L.append(f"- State: {x['state']}")
        L.append(f"- Operations: {'; '.join(x['operations'])}")
        L.append(f"- Effect kinds: {', '.join(x['effect_kinds'])}; events: {', '.join(x['events'])}")
        L.append(f"- Model: `models/semantics/src/{x['family']}.rs` ({x['model']['checks']} checks, {x['model']['checks_met']} met, {', '.join(x['model']['scope'])})\n")
        L.append("| Law | Kind | Statement | Negative control(s) | As-built checks attributed to it | Also violated by (complement) |")
        L.append("|---|---|---|---|---|---|")
        for law in x["laws"]:
            L.append(f"| {law['id']} | {law['kind']} | {law['text']} | {', '.join('`' + c + '`' for c in law['controls'])} | "
                     f"{', '.join('`' + c + '`' for c in law['as_built_violations']) or '-'} | {', '.join('`' + c + '`' for c in law['also_violated_by']) or '-'} |")
        L.append("\n| Object | Use | Departures (law: findings or exception; why) | Where (pin) | Model checks |")
        L.append("|---|---|---|---|---|")
        for i in x["instances"]:
            deps = []
            for d in i.get("departures", []):
                fe = ", ".join(d.get("findings", [])) + (("; " if d.get("findings") else "") + d["exception"] if d.get("exception") else "")
                deps.append(f"{d['law']}: {fe}" + (f" ({d['why']})" if d.get("why") else ""))
            if i.get("exception_note"):
                deps.append(f"exception {i['exception_note']}")
            mc = ", ".join("`" + c + "`" for c in i.get("model_checks", [])) or ("not modelled: " + i.get("note", ""))
            L.append(f"| {i['object']} | {i['use']} | {'<br>'.join(deps) or '-'} | `{i['where']}` | {mc} |")
        notes = [i for i in x["instances"] if i.get("note") and i.get("model_checks")]
        if notes:
            L.append("")
            for i in notes:
                L.append(f"- {i['object']}: {i['note']}")
    att = {f for x in m["mechanisms"] for i in x["instances"] for f in i.get("findings", [])}
    un = sorted(f for f, v in fc.items() if any(c.startswith("AX-") for c in v) and f not in att)
    L += ["\n## Axiom-breaking findings not attached to a mechanism instance\n",
          f"{len(un)} findings break an axiom (`axioms.json`) but are not attached to a mechanism instance above, because the",
          "mechanism instances model one representative variant per object and these findings are further variants, or because",
          "the departure lies outside every machine's subset (network exposure, resource release, error-class mapping, cost):",
          ", ".join(un) + ".",
          "They stay counted against their axioms; attaching them (one more trait instance each) is an open part of 3.3a-mechanisms."]
    return "\n".join(L) + "\n"


def main():
    out = {"AXIOMS.md": axioms_md(), "MECHANISMS.md": mechanisms_md()}
    if "--check" in sys.argv:
        bad = [n for n, t in out.items() if (SEM / n).read_text() != t]
        if bad:
            raise SystemExit(f"stale: {bad}")
        print("ok")
        return
    for n, t in out.items():
        (SEM / n).write_text(t)
    print("written: " + ", ".join(out))


if __name__ == "__main__":
    main()
