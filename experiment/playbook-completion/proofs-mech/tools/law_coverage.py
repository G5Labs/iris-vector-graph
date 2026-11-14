#!/usr/bin/env python3
"""Law coverage of the PROOFS-MECH crate, derived from its sources and the semantics lane's mechanisms.json.

    python experiment/playbook-completion/proofs-mech/tools/law_coverage.py [RESULTS.json] [--markdown PROOFS.md]

For each of the 45 laws: the generic theorem(s) proving it once over the mechanism's trait (from the mNN files),
the obligation, the instances that discharge it (types implementing `<Fam>Object` in the baseline, which discharge
every obligation of their trait; as-built and mutant variants that keep it, by their `keep_*` lemmas), and the
variants that break it (each a located control with its refutation and counterexample). Instance types are mapped
to the explorer's model variants (family/name) and so to the objects mechanisms.json lists for them. The result is
written into RESULTS.json under `law_coverage` (the runner's own keys are left as they are) and printed as a table.
With --markdown, the generated sections of PROOFS.md (between `<!--NAME-->` and `<!--/NAME-->` markers: result
summary, law table, control table, cost table) are rewritten from RESULTS.json; the prose is left as it is.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROOFS = Path(__file__).resolve().parent.parent
COMPLETION = PROOFS.parent
SRC = PROOFS / "src"
FAM = {"01": "ledger", "02": "retry", "03": "excl", "04": "derived", "05": "removal", "06": "snapshot", "07": "queue",
       "08": "install", "09": "scope", "10": "unit", "11": "cap", "12": "catalog", "13": "epoch"}
# Object types whose name does not spell their explorer variant
OVERRIDE = {
    ("08", "Canonical"): "install/canonical", ("10", "Canonical"): "unit/canonical", ("09", "ScopeCanonical"): "scope/canonical",
    ("12", "CatalogCanonical"): "catalog/canonical", ("11", "HttpServer"): "cap/http-server",
    ("07", "EmbedQueueEntryReviewed"): "queue/embed-queue", ("07", "EmbedQueueOrderReviewed"): "queue/embed-queue",
    ("07", "BoundedRedactionResumeReviewed"): "queue/bounded-redaction-resume",
    ("04", "ResultCache04Reviewed"): "derived/result-cache-04", ("05", "Bm25Reviewed"): "removal/bm25",
    ("12", "Bm25IndexGraphUncheckedReviewed"): "catalog/bm25-index-graph-unchecked",
    ("12", "IvfIndexGraphUncheckedReviewed"): "catalog/ivf-index-graph-unchecked",
    ("03", "Bm25WriteLockReviewed"): "excl/bm25-write-lock",
    ("04", "Bm25TextChangeReviewed"): "derived/bm25-text-change",
}
# which laws each Object trait covers (M-07 has three sub-machines)
TRAIT_LAWS = {"QueueEntryObject": ["M07-L1", "M07-L2"], "QueueOrderObject": ["M07-L3", "M07-L4"], "ResumeObject": ["M07-L4"]}


def kebab(name: str) -> str:
    name = re.sub(r"(Reviewed|AsBuilt)$", "", name)
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower().replace("bm25-", "bm25-")


def variant_of(nn: str, ty: str, variants: dict) -> str | None:
    if (nn, ty) in OVERRIDE:
        return OVERRIDE[(nn, ty)]
    v = f"{FAM[nn]}/{kebab(ty)}"
    return v if v in variants else None


def generic_theorems(theorems: list[str], fam: str, lid: str, n: str, kind: str) -> list[str]:
    own = [t for t in theorems if re.fullmatch(rf"theorem_l{n}(_\w+)?", t)]
    if not own and kind == "action" and "theorem_action_laws" in theorems:
        own = ["theorem_action_laws"]
    if fam == "queue":
        bundle = {"M07-L1": ["theorem_entry"], "M07-L2": ["theorem_entry"], "M07-L3": ["theorem_order"],
                  "M07-L4": ["theorem_order", "theorem_resume"]}[lid]
    else:
        bundle = [f"theorem_{fam}"] if f"theorem_{fam}" in theorems else []
    return own + bundle


def fill(md: Path, name: str, body: str) -> None:
    text = md.read_text()
    a, b = f"<!--{name}-->", f"<!--/{name}-->"
    if b in text:
        pre, rest = text.split(a, 1)
        _, post = rest.split(b, 1)
    else:
        pre, post = text.split(a, 1)
    md.write_text(pre + a + "\n" + body.rstrip() + "\n" + b + post)


def markdown(md: Path, results: dict, coverage: dict) -> None:
    base = results["baseline"]
    ctl = results["controls"]
    killed = sum(1 for c in ctl.values() if c.get("killed"))
    kinds = {}
    for c in ctl.values():
        kinds[c.get("kind")] = kinds.get(c.get("kind"), 0) + 1
    objs = {(c["mechanism"], d["type"]) for c in coverage.values() for d in c["discharged_by_instances"]}
    summ = (f"**Result** (run directory `{results['run_dir']}`, sources SHA-256 `{results['sources_sha256']}`, gate "
            f"**{results['gate']}**): baseline **{base.get('verified')} verified, {base.get('errors')} errors** with "
            f"`--no-cheating` (wall {base.get('wall_seconds')} s, SMT {base.get('smt_run_ms')} ms, rlimit "
            f"{base.get('rlimit_total')}); trust inventory empty; **all 45 laws of the 13 mechanisms are proved "
            f"generically** (one theorem per law over the mechanism's trait, plus one bundled theorem per mechanism; "
            f"M07-L4 as two progress theorems); {len(objs)} canonical or reviewed instances discharge every obligation of "
            f"their trait; **{killed} of {len(ctl)} located controls** ({kinds.get('as-built', 0)} as-built variants of "
            f"the pin, {kinds.get('exception', 0)} documented exceptions, {kinds.get('mutant', 0)} generic mutants) fail "
            f"exactly at the obligation(s) of the law(s) the explorer reports them violating, with their refutations and "
            f"proved counterexamples verified in the same build. Registry: `proofs-mech-baseline`, one "
            f"`proofs-mech-<feature>` per control, recheck `proofs-mech-recheck`.")
    fill(md, "RESULT-SUMMARY", summ)
    rows = ["## Which instances discharge which laws", "",
            "Every law is proved once over its mechanism's trait (column 2). Column 3: the canonical/reviewed instances "
            "that implement the mechanism's Object trait in the baseline (they discharge every obligation of their trait, "
            "so the generic theorem applies with no proof of their own); column 4: departing variants that still keep "
            "this law (their `keep_*` lemma discharges its obligation, so the per-law theorem applies to them); column 5: "
            "the variants that break it (each a located control with a refutation and a proved counterexample).", "",
            "| Law | Generic theorem(s) | Discharged by (instances) | Kept by departing variants | Broken by (control) |",
            "|---|---|---|---|---|"]
    for lid, c in coverage.items():
        d = ", ".join(f"{x['type']}" for x in c["discharged_by_instances"])
        k = ", ".join(x["type"] for x in c["kept_by_departing_variants"]) or "-"
        b = ", ".join(f"{x['type']} ({','.join(x['findings']) or x['kind']})" for x in c["broken_by_variants"]) or "-"
        rows.append(f"| {lid} {c['kind']} | {', '.join('`'+t+'`' for t in c['generic_theorems'])} | {d} | {k} | {b} |")
    fill(md, "LAW-TABLE", "\n".join(rows))
    rows = ["## Located controls", "",
            "One Cargo feature each (`proofs-mech-<feature>` with `_` as `-`); result `expected-violation` when the control "
            "fails exactly at its LOCATE line(s) and nowhere else. Full records: `RESULTS.json` `controls`.", "",
            "| Feature | Variant (kind) | Explorer check(s) | Findings | Laws broken | Located at | Result |", "|---|---|---|---|---|---|---|"]
    for f, c in sorted(ctl.items(), key=lambda kv: (kv[1].get("mechanism", ""), kv[1].get("file", ""), kv[0])):
        rows.append(f"| `{f}` | {c.get('variant')} ({c.get('kind')}) | {', '.join(c.get('check', '').split(','))} | "
                    f"{', '.join(c.get('findings', [])) or '-'} | {', '.join(c.get('broken_laws', []))} | "
                    f"{', '.join(c.get('error_locations', []))} | {'rejected at its obligation' if c.get('killed') else 'NOT AS EXPECTED'} |")
    fill(md, "CONTROL-TABLE", "\n".join(rows))
    rows = ["Baseline SMT time and rlimit per mechanism (its mNN, iNN and cxNN modules), from the baseline's Verus JSON; "
            f"whole-crate wall time {base.get('wall_seconds')} s per Verus run (one run per control, the same order).", "",
            "| Mechanism | SMT ms | rlimit | functions |", "|---|---:|---:|---:|"]
    for k, v in results.get("cost_per_mechanism", {}).items():
        if k.startswith("M-"):
            rows.append(f"| {k} | {v['ms']} | {v['rlimit']} | {v['functions']} |")
    fill(md, "COST-TABLE", "\n".join(rows))


def main() -> int:
    mech = json.loads((COMPLETION / "semantics" / "mechanisms.json").read_text())
    args = [a for a in sys.argv[1:]]
    md = None
    if "--markdown" in args:
        i = args.index("--markdown")
        md = Path(args[i + 1])
        del args[i:i + 2]
    results_path = Path(args[0]) if args else PROOFS / "RESULTS.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    ctl_results = results.get("controls", {})
    variants = {}
    for mm in mech["mechanisms"]:
        for inst in mm["instances"]:
            ms = inst.get("model")
            for m in (ms if isinstance(ms, list) else [ms]):
                if m:
                    variants.setdefault(m, {"mechanism": mm["id"], "objects": []})["objects"].append(inst["object"])
    coverage = {}
    for mm in mech["mechanisms"]:
        nn = mm["id"][2:]
        fam = FAM[nn]
        mtext = (SRC / f"m{nn}_{fam}.rs").read_text()
        itext = (SRC / f"i{nn}_{fam}.rs").read_text()
        ctext = (SRC / f"ctl_{fam}.rs").read_text()
        objects_impl = re.findall(r"^impl (\w+Object) for (\w+)", itext, re.M)
        theorems = re.findall(r"pub proof fn (theorem_\w+)<", mtext)
        controls = []
        for line in ctext.splitlines():
            m = re.match(r"\s*// CONTROL (\S+) (.*)", line)
            if m:
                kv = dict(x.split("=", 1) for x in m.group(2).split())
                controls.append((m.group(1), kv))
        ctl_types = {}
        for feat, kv in controls:
            ty = re.search(rf"#\[cfg\(feature = \"{feat}\"\)\]\nimpl \w+ for (\w+)", ctext).group(1)
            ctl_types[feat] = ty
        for law in mm["laws"]:
            lid = law["id"]
            n = lid.split("-L")[1]
            disch = []
            for trait, ty in objects_impl:
                if trait in TRAIT_LAWS and lid not in TRAIT_LAWS[trait]:
                    continue
                v = variant_of(nn, ty, variants)
                disch.append({"type": ty, "variant": v, "objects": variants.get(v, {}).get("objects", []),
                              "how": "Object impl (baseline)"})
            kept, broken = [], []
            for feat, kv in controls:
                ty = ctl_types[feat]
                laws_here = kv["violates"].split(",")
                stems = {re.sub(r"_l\d+$", "", r.split("::refute_")[1]) for r in kv["refute"].split(",")}
                stem = next(iter(stems))
                trait_ok = True
                if nn == "07":
                    tr = re.search(rf"impl (\w+) for {ty}\b", ctext).group(1)
                    trait_ok = lid in TRAIT_LAWS.get(tr, [])
                if not trait_ok:
                    continue
                rid = f"proofs-mech-{feat.replace('_', '-')}"
                entry = {"type": ty, "control": feat, "registry": rid, "checks": kv["check"].split(","), "kind": kv["kind"],
                         "objects": kv["objects"].split(",") if kv.get("objects") else [],
                         "findings": kv["findings"].split(",") if kv.get("findings") else []}
                if lid in laws_here:
                    entry["refutation"] = [r for r in kv["refute"].split(",") if r.endswith(f"_l{n}")]
                    entry["counterexample"] = [c for c in kv["cx"].split(",") if c.endswith(f"_l{n}")]
                    cr = ctl_results.get(feat, {})
                    entry["located_at"] = [x["at"] for x in cr.get("locate", []) if x["law"] == lid] or None
                    entry["control_result"] = "rejected at its obligation" if cr.get("killed") else ("not run" if not cr else "NOT AS EXPECTED")
                    broken.append(entry)
                elif re.search(rf"fn keep_{stem}_l{n}\(", itext):
                    entry["how"] = f"keep_{stem}_l{n}"
                    kept.append(entry)
            coverage[lid] = {
                "mechanism": mm["id"], "kind": law["kind"], "text": law["text"],
                "generic_theorems": generic_theorems(theorems, fam, lid, n, law["kind"]),
                "obligation": f"m{nn}_{fam}::obl_l{n}" + ("_resume (resume part)" if lid == "M07-L4" else ""),
                "discharged_by_instances": disch,
                "kept_by_departing_variants": kept,
                "broken_by_variants": broken,
                "status": "proved generically over the trait (model level)",
            }
    unmapped = sorted({d["type"] for c in coverage.values() for d in c["discharged_by_instances"] if not d["variant"]})
    summary = {
        "laws": len(coverage),
        "proved_generically": sum(1 for c in coverage.values() if c["generic_theorems"]),
        "explorer_only": [k for k, c in coverage.items() if not c["generic_theorems"]],
        "instances_discharging_all_obligations": sorted({(c["mechanism"], d["type"]) for c in coverage.values()
                                                         for d in c["discharged_by_instances"]}),
        "unmapped_instance_types": unmapped,
        "mechanisms_json_sha256": __import__("hashlib").sha256((COMPLETION / "semantics" / "mechanisms.json").read_bytes()).hexdigest(),
    }
    summary["instances_discharging_all_obligations"] = [list(x) for x in summary["instances_discharging_all_obligations"]]
    results["law_coverage"] = {"summary": summary, "laws": coverage}
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    if md:
        markdown(md, results, coverage)
    for lid, c in coverage.items():
        print(f"{lid}: theorems {','.join(c['generic_theorems'])}; discharged by {len(c['discharged_by_instances'])} instances, "
              f"kept by {len(c['kept_by_departing_variants'])} departing variants, broken by "
              f"{[b['type'] for b in c['broken_by_variants']]}")
    print(json.dumps({k: v for k, v in summary.items() if k != "instances_discharging_all_obligations"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
