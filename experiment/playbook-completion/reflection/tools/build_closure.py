#!/usr/bin/env python3
"""Build reflection/closure.json and reflection/CLOSURE.md (gate 3.6-closure, the SQL_CLOSURE.md counterpart).

    python build_closure.py

The exact list of conditions the audit's proofs and models rely on about the environment (IRIS, the driver, the
host and the operator), each mapped to the registered run that validates it, or marked assumed (or shown false) with
its consequence. Four groups, each derived mechanically from its source:

  contract-r6    every clause of iris-contract/CONTRACT.md's validated clause table
  contract-2     every clause of contract-2/VALIDATED.json (E-1, S-1, X2-*)
  outside        every premise family of contract-2/coverage.json (P2-*: what stays outside the contract)
  proof-premise  every premise of reflection/premise_tests.json of class engine or progress taken from TRUST.md,
                 a proofs*/PROOFS.md table or a models/*/MODELS.md (status from its verdict there)

check_closure.py re-derives the expected set and checks each mapping. Nothing here is new evidence: every run cited
was registered by the lane that made it.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
ROOT = LANE.parent
OUT_JSON = LANE / "closure.json"
OUT_MD = LANE / "CLOSURE.md"
CONTRACT = ROOT / "iris-contract" / "CONTRACT.md"
VALIDATED = ROOT / "contract-2" / "VALIDATED.json"
COVERAGE = ROOT / "contract-2" / "coverage.json"
PREMISES = LANE / "premise_tests.json"
STATUSES = ("validated", "validated-in-part", "shown-false", "assumed")
VERDICT_STATUS = {"tested-holds": "validated", "tested-partial": "validated-in-part",
                  "tested-violated": "shown-false", "untested": "assumed"}
R6_E = ["env-contract-r2", "env-ext-r6", "env-contract-r6-recheck", "env2-regress"]
R6_X = ["env-ext-r6", "env-contract-r6-recheck", "env2-regress"]

# Clauses of the r6 table not decided by the differential rounds (CONTRACT.md "Decided by" names no registered case).
R6_PARTIAL = {
    "E-CALLER": (["env2-e1-r2"], "decided by an unregistered exploratory probe (env/explore-2.log test 7); S-1 "
                 "(env2-e1-r2) shows the pin's compiled SQL functions run on the calling connection's process, and "
                 "b-09-f0909-txn-visibility shows a from_connect engine runs SQL and Native API calls in two processes, "
                 "so results that rely on one process per connection hold for connection-object engines only"),
}

# Outside-premise families whose consequence was observed at the pin, or which a run exercises (lane runs, as
# registered; a failing run here is evidence that the consequence occurred, not a validation).
OBSERVED = {
    "fetchfirst": ["env2-fetchfirst-probe", "env2-fc1720-query-nodes"],
    "lock-esc": ["st-live-cap-batch"],
    "limits": ["corr-capacity", "st-live-cap-bm25", "st-live-cap-batch-r2"],
    "buildindices": ["env-ext-explore-10", "ws-live-noindex"],
    "bitmap": ["ws-live-noindex-erase"],
    "hnsw": ["rx-live-06"],
    "mgmt": ["rx-live-17"],
    "absent": ["tr-replay-15", "val-scratch-236-1"],
    "zf": ["ver-arno-callout"],
    "security": ["ver-priv-r3"],
    "config": ["env-synchcommit-setting", "live-crash-world-r2"],
    "oracle": ["trace-conformance-controls", "sim-oracle-selftest", "env2-e1-r1-journal"],
}
# The one family whose premise the pin itself breaks (the product sends FETCH FIRST: F-C1743).
SHOWN_FALSE = {"fetchfirst": "the product does send FETCH FIRST (IRISGraphStore.query_nodes, F-C1743): on driver 5.3.2 "
                             "the client process ends with SIGSEGV"}
VALIDATED_IN_PART = {"oracle": "self-tested oracles (controls caught) and journal equality for E-1; the journal's "
                               "completeness itself is not a contract clause"}


def _cells(line: str) -> list:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def r6_clauses() -> list:
    text = CONTRACT.read_text()
    sec = re.search(r"^## Clauses \(validated\).*?(?=^## )", text, re.S | re.M).group(0)
    rows, lines = [], sec.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("| Id | Clause |"):
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                c = _cells(row)
                rows.append({"id": c[0].replace("**", ""), "clause": c[1].replace("**", ""),
                             "contract": c[2].replace("**", ""), "reliance": c[5] if len(c) > 5 else ""})
    return rows


def family_premise_id(fam: dict) -> str:
    return fam["premise"].split(":")[0].split(" (")[0].strip()


def family_modules(cov: dict, fid: str) -> list:
    """Modules with a feature classified into this family (outside it, or validated with it as the residual)."""
    out = []
    for nn, m in sorted(cov["modules"].items()):
        if any((f.get("family") or (f.get("residual") or {}).get("family")) == fid for f in m.get("features", [])):
            out.append(nn)
    return out


def env_premises(pm: dict) -> list:
    return [e for e in pm["premises"] if e.get("class") in ("engine", "progress")
            and not e["key"].startswith("iris-contract:")]


def build() -> dict:
    conds = []
    for c in r6_clauses():
        runs = list(R6_E if c["id"].startswith("E-") else R6_X)
        status, cons = "validated", ""
        if c["id"] in R6_PARTIAL:
            runs, cons = R6_PARTIAL[c["id"]]
            status = "validated-in-part"
        conds.append({"id": f"contract-r6:{c['id']}", "group": "contract-r6", "ref": c["id"],
                      "condition": f"{c['clause']}: {c['contract']}"[:400], "status": status, "runs": runs,
                      "observed": [], "consequence": cons, "relied_on_by": c["reliance"][:200],
                      "missing_test": ("a named differential case for the clause in the next contract round"
                                       if status != "validated" else ""),
                      "source": "experiment/playbook-completion/iris-contract/CONTRACT.md"})
    val = json.loads(VALIDATED.read_text())["clauses"]
    for cid, v in val.items():
        conds.append({"id": f"contract-2:{cid}", "group": "contract-2", "ref": cid, "condition": v["what"][:400],
                      "status": "validated" if v["result"] == "pass" else "assumed", "runs": list(v["runs"]),
                      "observed": [], "consequence": "", "relied_on_by": "", "missing_test": "",
                      "source": "experiment/playbook-completion/contract-2/VALIDATED.json"})
    cov = json.loads(COVERAGE.read_text())
    for fid, fam in cov["families"].items():
        status = "shown-false" if fid in SHOWN_FALSE else "validated-in-part" if fid in VALIDATED_IN_PART else "assumed"
        cons = fam["consequence"]
        if fid in SHOWN_FALSE:
            cons = SHOWN_FALSE[fid] + ". " + cons
        if fid in VALIDATED_IN_PART:
            cons = VALIDATED_IN_PART[fid] + ". " + cons
        conds.append({"id": f"outside:{fid}", "group": "outside", "ref": fid, "condition": fam["premise"],
                      "status": status, "runs": list(OBSERVED.get(fid, [])) if status != "assumed" else [],
                      "observed": list(OBSERVED.get(fid, [])) if status == "assumed" else [],
                      "consequence": cons, "relied_on_by": ("modules " + ", ".join(family_modules(cov, fid))
                                                            if family_modules(cov, fid) else "no module feature (defined, unused)"),
                      "missing_test": f"a contract clause for family '{fid}' (named cases, mutants, a differential round "
                                      f"on a fresh seed, as contract-2 did for X2-*)",
                      "source": "experiment/playbook-completion/contract-2/coverage.json"})
    pm = json.loads(PREMISES.read_text())
    for e in env_premises(pm):
        status = VERDICT_STATUS[e["verdict"]]
        runs = [t["ref"] for t in e["tests"] if t["kind"] in ("run", "upstream")]
        if status == "validated":
            cons = ""
        elif status == "shown-false":
            cons = (f"false at the pin: results of {e['source'].split('/')[-2]} that rest on it do not transfer to the "
                    f"product (see its 'Premises the pin violates')")
        else:
            cons = (f"results of {e['source'].split('/')[-2]} that rest on it hold only where it holds; missing test: "
                    f"{e.get('should_exist') or '-'}")
        conds.append({"id": f"proof-premise:{e['key']}", "group": "proof-premise", "ref": e["key"],
                      "condition": f"{e['premise']} [{e['class']}]", "status": status,
                      "runs": runs if status != "assumed" else [], "observed": runs if status == "assumed" else [],
                      "consequence": cons, "relied_on_by": e["source"].replace("experiment/playbook-completion/", ""),
                      "missing_test": e.get("should_exist") or ("" if status in ("validated", "shown-false") else "-"),
                      "source": "experiment/playbook-completion/reflection/premise_tests.json"})
    by_group = {g: dict(Counter(c["status"] for c in conds if c["group"] == g))
                for g in ("contract-r6", "contract-2", "outside", "proof-premise")}
    return {"lane": "reflection", "gate": "3.6-closure", "level": "method",
            "pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e",
            "generated_by": "experiment/playbook-completion/reflection/tools/build_closure.py",
            "checked_by": "experiment/playbook-completion/reflection/tools/check_closure.py",
            "statuses": {"validated": "a registered passing run decides the condition on the audit's engine",
                         "validated-in-part": "a registered run decides part of it; the rest is named in consequence",
                         "shown-false": "a registered run shows it false at the pin; consequence names what does not transfer",
                         "assumed": "no run validates it; consequence names what rests on it"},
            "conditions": conds,
            "summary": {"conditions": len(conds), "by_group": by_group,
                        "by_status": dict(Counter(c["status"] for c in conds))}}


def render(m: dict) -> str:
    L = []
    w = L.append
    s = m["summary"]
    w("# Closure conditions: what the proofs and models assume about the environment (gate 3.6-closure)\n")
    w("Lane reflection, product pin `3eaa79cf`. Level: **method**. The playbook's `SQL_CLOSURE.md` counterpart for "
      "IVG on IRIS: the exact list of environment conditions (IRIS 2026.1 Community, the driver, the host and the "
      "operator) that the audit's proofs, models and contract rely on, each mapped to the registered run that "
      "validates it, or marked assumed or shown false with its consequence. Machine-readable twin `closure.json`, "
      "generated by `tools/build_closure.py` from `iris-contract/CONTRACT.md`, `contract-2/VALIDATED.json`, "
      "`contract-2/coverage.json` and `reflection/premise_tests.json`; checked by `tools/check_closure.py` "
      "(`rf-closure-check-r3`, self-test `rf-closure-selftest-r3`). It restates no result: every run named was "
      "registered by the lane that made it.\n")
    w("| Group | Source | Conditions | " + " | ".join(STATUSES) + " |")
    w("|---|---|---|" + "---|" * len(STATUSES))
    src = {"contract-r6": "IRIS contract r6 clauses", "contract-2": "contract-2 validated clauses",
           "outside": "outside-premise families (contract-2 coverage)",
           "proof-premise": "proofs' and models' environment premises (engine, progress)"}
    for g, label in src.items():
        c = s["by_group"].get(g, {})
        w(f"| {g} | {label} | {sum(c.values())} | " + " | ".join(str(c.get(k, 0)) for k in STATUSES) + " |")
    w(f"| **total** | | **{s['conditions']}** | " + " | ".join(f"**{s['by_status'].get(k, 0)}**" for k in STATUSES) + " |")
    w("")
    w("Reading the statuses: *validated* means a passing differential or probe run on this engine decides the "
      "condition (within the contract's semantic subset); *assumed* means nothing here validates it and the "
      "consequence column says which results rest on it; *shown-false* means the pin breaks it, so results relying on "
      "it do not transfer. The engine is IRIS 2026.1 Community with driver 5.3.2 (2026.2 and driver 5.4.0 only where "
      "a run says so); 2026.3, Enterprise and multi-node are blocked-access.\n")
    for g, label in src.items():
        w(f"## {label} ({g})\n")
        w("| Condition | Status | Runs (validating, or observed) | Consequence | Test that should exist | Relied on by |")
        w("|---|---|---|---|---|---|")
        for c in m["conditions"]:
            if c["group"] != g:
                continue
            runs = ", ".join(f"`{r}`" for r in c["runs"]) or ("observed: " + ", ".join(f"`{r}`" for r in c["observed"])
                                                             if c["observed"] else "-")
            cond = c["condition"].replace("|", "/")
            w(f"| `{c['id']}`: {cond} | {c['status']} | {runs} | {(c['consequence'] or '-').replace('|', '/')} | "
              f"{(c['missing_test'] or '-').replace('|', '/')} | {(c['relied_on_by'] or '-').replace('|', '/')} |")
        w("")
    w("## Limits\n")
    w("- The contract's clauses hold inside its semantic subset (CONTRACT.md 'Outside the semantic subset'); "
      "everything outside is a family above, assumed unless a run says otherwise.")
    w("- A family's 'observed' runs are lane runs in which its consequence occurred (often a product finding); they do "
      "not validate the premise.")
    w("- Proof premises keep the verdict of `premise_tests.json`; this file adds no judgement to them.")
    return "\n".join(L) + "\n"


def main() -> int:
    m = build()
    OUT_JSON.write_text(json.dumps(m, indent=1) + "\n")
    OUT_MD.write_text(render(m))
    s = m["summary"]
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}: {s['conditions']} conditions, "
          f"by group {s['by_group']}, by status {s['by_status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
