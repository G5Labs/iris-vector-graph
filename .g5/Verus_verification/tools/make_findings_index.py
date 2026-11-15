#!/usr/bin/env python3
"""Regenerate .g5/Verus_verification/findings.md from the three register files. Standard library only."""
import re
from pathlib import Path

D = Path(__file__).resolve().parents[1]
DOMAINS = {"led": "ledger/erasure/redaction", "str": "graph structure", "tmp": "temporal", "srch": "search",
           "plt": "platform/access/install", "cyp": "Cypher", "con": "consolidated uplift", "adp": "adapters", "doc": "documentation", "test": "test suite"}


def parse(name):
    out = []
    for b in re.split(r'(?=^<a id=")', (D / name).read_text(), flags=re.M):
        m = re.match(r'<a id="([^"]+)"></a>\s*\n###\s+(.*)\n', b)
        if not m:
            continue
        st = re.search(r'^Severity:\s*(\w+)(?:\s*·\s*Decision:\s*(.+))?$', b, re.M)
        rep = re.search(r'^Reproduced by:\s*(.*)$', b, re.M)
        out.append(dict(id=m.group(1), title=m.group(2).strip(), sev=st.group(1) if st else "Unranked",
                        open=bool(st and st.group(2)), native=bool(rep and not rep.group(1).lower().startswith("none"))))
    return out


MODULES = {"00": "system", "01": "install", "02": "graph identity", "03": "writes", "04": "adjacency", "05": "temporal",
           "06": "vectors", "07": "text search", "08": "Cypher", "09": "native executor", "10": "algorithms", "11": "ledger",
           "12": "erasure", "13": "redaction", "14": "replay", "15": "integrations", "16": "interfaces", "17": "operations",
           "18": "snapshot"}


def dom(i):
    # consolidated uplift: playbook IDs (F-NNNN, F-CNNNN, HD-NNNN by module; RC- root causes) and new families
    m = re.match(r"^(?:F-C?|HD-)(\d{2})", i)
    if m:
        return "playbook: " + MODULES.get(m.group(1), m.group(1))
    if i.startswith("RC-"):
        return "playbook: root cause"
    if i.startswith(("bug-adp", "q-adp")):
        return "adapters"
    parts = i.split("-")
    return DOMAINS.get(parts[1], DOMAINS["led"]) if len(parts) >= 3 else DOMAINS["led"]


def main():
    B, S, Q = parse("bugs_issues.md"), parse("design_simplification.md"), parse("open_questions.md")
    cnt = lambda es, sev: sum(1 for e in es if e["sev"] == sev and e["open"])
    L = ["# Findings register — IVG Verus uplift, consolidated (2026-11-14)", "",
         "Product baseline `3eaa79cf`. The register covers every bug, design simplification and unresolved question found during "
         "intent recovery, modeling, native observation and the independent review rounds. Proposed repairs are not implemented: "
         "the product was read-only for this uplift. The consolidated uplift (2026-11-14) imported every playbook-arm "
         "finding, root cause and decision; each source ID maps to one entry in the [crosswalk](crosswalk/). The [final report](../uplift/ivg-verus-initial/final-report.md) summarises them; "
         "statuses of the claims they affect are in the [coverage map](coverage.md).", "",
         "| File | Entries | High | Medium | Low | Observations / drift | Natively reproduced |",
         "|---|---:|---:|---:|---:|---:|---:|",
         f"| [Bugs and issues](bugs_issues.md) | {len(B)} | {cnt(B,'High')} | {cnt(B,'Medium')} | {cnt(B,'Low')} | "
         f"{sum(1 for e in B if not e['open'])} | {sum(1 for e in B if e['open'] and e['native'])} of {sum(1 for e in B if e['open'])} |",
         f"| [Design simplifications](design_simplification.md) | {len(S)} | {cnt(S,'High')} | {cnt(S,'Medium')} | {cnt(S,'Low')} | "
         f"{sum(1 for e in S if not e['open'])} | n/a |",
         f"| [Open questions](open_questions.md) | {len(Q)} | {cnt(Q,'High')} | {cnt(Q,'Medium')} | {cnt(Q,'Low')} | "
         f"{sum(1 for e in Q if not e['open'])} | n/a |", "",
         "How to read an entry: a bug cites the governing source of the expected behavior (**Expected**), what the baseline does "
         "(**Observed**) and the evidence (**Found by** — model witness, source review or reviewer — and **Reproduced by** — native "
         "probe receipt under `receipts/native/` or an upstream test). An entry whose product reachability was not shown natively "
         "says **Suspected** and its severity is one level lower than its consequence. A simplification states the proposal, why it "
         "helps, the behavior to preserve and a distinguishing case. A question states the evidence, the plausible interpretations "
         "and the decision needed.", "",
         "## High-severity bugs", "", "| ID | Domain | Finding | Native reproduction |", "|---|---|---|---|"]
    L += [f"| [{e['id']}](bugs_issues.md#{e['id']}) | {dom(e['id'])} | {e['title']} | {'yes' if e['native'] else 'no — suspected'} |"
          for e in B if e["open"] and e["sev"] == "High"]
    L += ["", "## Simplifications ranked High or Medium", "", "| ID | Proposal |", "|---|---|"]
    L += [f"| [{e['id']}](design_simplification.md#{e['id']}) | {e['title']} |" for e in S if e["open"] and e["sev"] in ("High", "Medium")]
    L += ["", "## Decisions needed (High and Medium questions)", "", "| ID | Question |", "|---|---|"]
    L += [f"| [{e['id']}](open_questions.md#{e['id']}) | {e['title']} |" for e in Q if e["open"] and e["sev"] in ("High", "Medium")]
    L += ["", "## Sources of the findings", "",
          "- Stage A intent notes: [`intent/`](../uplift/ivg-verus-initial/intent/) and the fresh-reader [reconstruction check](../uplift/ivg-verus-initial/reconstruction-check.md).",
          "- Models and their NOTES: [`models/`](models/) (ledger_redaction, graph_structure, temporal, search, platform).",
          "- Native observations: [`receipts/native/`](receipts/native/) ([sources](receipts/native/SOURCES.txt)).",
          "- Independent review rounds: [`review/`](../uplift/ivg-verus-initial/review/); adjudications in the [uplift plan](../uplift/ivg-verus-initial/uplift-plan.md).", ""]
    (D / "findings.md").write_text("\n".join(L))
    print(f"findings.md: {len(B)} bugs/issues, {len(S)} simplifications, {len(Q)} questions")


if __name__ == "__main__":
    main()
