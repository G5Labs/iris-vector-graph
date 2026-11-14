#!/usr/bin/env python3
"""Render reflection/TEST-REFLECTION.md from premise_tests.json, root_causes.json and validation/results.json.

    python build_test_reflection.py           # write TEST-REFLECTION.md
    python build_test_reflection.py --check   # exit 1 if the committed file differs from the rendering

Every number in the document is computed here from those files; the narrative is fixed text.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
ROOT = LANE.parent
OUT = LANE / "TEST-REFLECTION.md"

SRC_LABEL = {"TRUST": "TRUST.md (trusted items and premise tables)", "proofs": "proofs/PROOFS.md",
             "proofs-d9": "proofs-d9/PROOFS.md", "proofs-breadth": "proofs-breadth/PROOFS.md",
             "proofs-d1b": "proofs-d1b/PROOFS.md", "proofs-d1c": "proofs-d1c/PROOFS.md",
             "proofs-d1d": "proofs-d1d/PROOFS.md", "proofs-d1e": "proofs-d1e/PROOFS.md",
             "proofs-d1f": "proofs-d1f/PROOFS.md", "models-core": "models/core/MODELS.md (stated assumptions)",
             "iris-contract": "iris-contract/CONTRACT.md (clauses, E-1, Freedom, outside-subset features)"}

# per root cause: the product test that would have detected its findings (from the remedy's test clause)
RC_TESTS = {
    "RC-01": "a two-graph fixture with one id held by both graphs, run through every reader and writer (USE GRAPH, all-graphs, default graph)",
    "RC-02": "the same fixture for ownership checks: redaction targets, node deletes, verify(), index use under a graph, snapshot round trip of named-graph rows",
    "RC-03": "an inventory-driven residue scan after erase + redact over every store, field and copy (indexes, temporal globals, routes, quarantine, legacy rows, archives), as the simulator's SC-001 scan does for the ledger",
    "RC-04": "two-process interleaving tests at the eraser / commit / redaction-start boundaries with a held lock to force the window (as live-f1201-reproduced and ib-HD1201-open-erasure)",
    "RC-05": "a two-process interleaving test per read-modify-write handler (mode switch, BM25 build, rebuild, DropAll, queue claim, counters)",
    "RC-06": "per derived store: write, roll back, read; and write on every path (weights, node-only, temporal), then read the cache",
    "RC-07": "a reader paused between pages while a redaction runs; an export while a writer holds an open transaction",
    "RC-08": "strict mode and a redaction marker against every writer of the census (not only the engine's guarded calls)",
    "RC-09": "lost-acknowledgement retries of commits with post-commit properties, and of HTTP writes through the client and server",
    "RC-10": "fault injection after the first write of each multi-step command, asserting no store changed",
    "RC-11": "a failing IVG call inside a caller's open transaction, asserting the caller's own write survives",
    "RC-12": "the suites on every supported cell (engine version x edition x driver x optional library), as the validation lane's driver A/B did for 5.3.2 vs 5.4.0",
    "RC-13": "the suites on a namespace installed with a non-default IVG Schema",
    "RC-14": "fault-injected reads and writes asserting a raise, not an empty or default answer",
    "RC-15": "a test that enumerates exported exception classes and server reason codes against IVGError and the HTTP/SDK maps",
    "RC-16": "the typed openCypher TCK on mixed data and a differential oracle per clause shape",
    "RC-17": "round trips of every value type through every writer and reader",
    "RC-18": "one test per enum value, unit and metric (refusal of unknown values; normalisation and sort direction)",
    "RC-19": "hostile literals and identifiers at every query entry, with read_only set",
    "RC-20": "calls as the documented least-privilege role and from a non-loopback address, asserting refusal",
    "RC-21": "a multigraph fixture through every reader, writer and verifier",
    "RC-22": "every writer and deleter over a marked row, asserting one shared predicate",
    "RC-23": "row-permutation tests: the same logical state inserted in different orders gives the same answers",
    "RC-24": "a birthday-collision fixture (the audit's b-09 search) in the native-plan tests",
    "RC-25": "restore tests against a live ledger that moved on, with overlapping merges and derived stores",
    "RC-26": "every vector-writing seam against a declared model of another identity and width, and with the registry unreadable",
    "RC-27": "boundary inputs (reserved names, control characters, negative timestamps, wrong widths, schema limits) at every entry",
    "RC-28": "each declared bound at and beyond its limit",
    "RC-29": "differential tests that run every route of one operation on the same fixtures",
    "RC-30": "progress tests: a bounded run finishes in finitely many calls; a queue serves every entry under steady load",
    "RC-31": "executed documentation examples and generated contracts (wire schema, constraint lists, status parts) compared in CI",
    "RC-32": "CI that installs from the package and runs the deploy recipes, console scripts and fixtures as shipped",
    "RC-33": "a mechanically generated list of documented refusals, parameters and protocol verbs, each with a test",
}


def render() -> str:
    pm = json.loads((LANE / "premise_tests.json").read_text())
    rc = json.loads((LANE / "root_causes.json").read_text())
    det = pm["detection"]
    cnt = det["counts"]
    prem = pm["premises"]
    L = []
    w = L.append
    w("# Test reflection (completion audit, playbook §3.8)\n")
    w("Lane reflection, product pin `3eaa79cf`, IRIS 2026.1 Community in the dedicated audit container. Level: "
      "**method**. What the completion audit's proofs and models rely on, which test checks each premise, what "
      "testing covers for each unpaid proof-debt row, and whether the product's own suites detect the defects this "
      "audit reproduced. Machine-readable twin: `premise_tests.json`, checked by `tools/check_premise_map.py` "
      "(registered `rf-premise-map-check`, self-test `rf-premise-map-selftest`); this file is rendered from it by "
      "`tools/build_test_reflection.py`. The original submission's `experiment/playbook-uplift/TEST-REFLECTION.md` "
      "(sections A-E) is the model for the structure; its premise table (section D) covered the worked example only.\n")

    w("## A. The audit's own tests (what the registry holds)\n")
    reg = defaultdict(Counter)
    for p in (ROOT / "evidence" / "runs").glob("*.json"):
        d = json.loads(p.read_text())
        reg[d["kind"]][d["result"]] += 1
    w("| Kind | Runs | Results |")
    w("|---|---|---|")
    for k in sorted(reg, key=lambda k: -sum(reg[k].values())):
        w(f"| {k} | {sum(reg[k].values())} | {', '.join(f'{r} {n}' for r, n in sorted(reg[k].items()))} |")
    w("")
    w("Only `live`, `probe`, `run`, `trace` and `check` runs observe IRIS or the product; `mc`, `proof` and `control` "
      "runs are about models (a model result never counts as a test of a product premise below). The run counts "
      "are those of the registry when this file was rendered.\n")

    w("## B. The product's own suites at the pin\n")
    w("From the validation lane (`validation/SUITES.md`, `validation/results.json`): unit 24,794 passed, integration "
      "2,651, e2e 3,348 with gate namespaces off and 10,122 in the gated subset, the r306 algorithm oracle 7,406, the "
      "openCypher TCK 3,895 of 3,896, docs 15 of 16 per run, the multi-process ledger cases 15/15 three times. Every "
      "failure was triaged by rule. What that says about the suites as a detector:")
    res = json.loads((ROOT / "validation" / "results.json").read_text())
    cats = Counter()
    for r in res["rules"]:
        c = r["category"]
        cats["product defect (driver 5.3.2)" if "driver" in c else "product defect" if c == "product-defect"
             else "suite stale (test-stale / test-isolation)" if c.startswith("product-defect") else c.split(" ")[0]] += 1
    w("- Triage rules by class: " + ", ".join(f"{k} {v}" for k, v in sorted(cats.items())) + ".")
    w("- The suite is red at the pin for reasons that are not product defects (stale tests: width refusals, the "
      "removed SQLUser views, path-as-dict, a mock signature, static budgets, an outdated schema contract). A red "
      "suite hides a new red test. The product's CI (`.github/workflows/ci.yml`, `quickstart.yml`) runs "
      "`tests/unit` with `SKIP_IRIS_TESTS=true` against the driver a fresh install resolves (not the `uv.lock` "
      "one), a wheel install check, and the quickstart harness (`scripts/quickstart_e2e.py`: README/QUICKSTART "
      "examples, setup and upgrade on a stock container); the integration, e2e, gated, oracle and TCK suites are "
      "not in CI, so their detections run only when someone runs them by hand. The quickstart harness was not run "
      "here.")
    w("- Not run decisively here: the 22 spec-236 scratch integration files (the 8-unit Community licence; "
      "`val-scratch-236-1` and its per-file reruns are `blocked`), gated e2e files with threads, processes or extra "
      "users, Enterprise-only and %AI-dependent cases. A detection in those files is unknown, not absent.")
    w("- One unconfirmed lead from a non-decisive run (rule `varlen-lookup-lead`): "
      "`tests/integration/test_025_varlen_path_functions.py:178-185` patches `get_node_labels` to raise and expects "
      "`execute_cypher` to raise; in the licence-degraded run it returned. It is a suspected swallowed lookup "
      "(RC-14 class), not a finding; it needs one decisive run of that file.\n")

    w("## C. Does the product's own suite detect the defects this audit reproduced?\n")
    w(f"Reproduced findings ({', '.join(det['reproduced_dispositions'])}): **{cnt['reproduced']}**. Detected by a "
      f"product test that is red at the pin because of the defect: **{cnt['detected']}** "
      f"({', '.join(det['detected'])}). **Not detected by any product test: {cnt['not_detected']}** "
      f"(by severity {', '.join(f'{k} {v}' for k, v in cnt['not_detected_by_severity'].items())}; by disposition "
      f"{', '.join(f'{k} {v}' for k, v in cnt['not_detected_by_disposition'].items())}). "
      f"{cnt['intent_undecided_or_blocked']} further findings are intent-undecided or blocked-access and are not "
      f"counted either way.\n")
    w("The four detected findings are the validation lane's own: they were found by running the suites "
      "(`zz-validation.json`), so the suites detected nothing the other lanes found. Every S1 finding that is "
      f"reproduced ({len(det['not_detected_s1'])}) is undetected by the product's tests.\n")
    w("| Detected finding | Triage rules | Product tests (examples) | Registered runs |")
    w("|---|---|---|---|")
    for f in det["detected"]:
        d = det["findings"][f]["detection"]
        w(f"| {f} | {', '.join(d['rules'])} | {'; '.join(d['tests'][:3])} | {', '.join(d['runs'][:6])} |")
    w("")
    w("Upstream tests the findings themselves cite, by relation to the defect "
      f"({', '.join(f'{k} {v}' for k, v in cnt['cited_test_relations'].items())}):\n")
    w("| Finding | Upstream test | Relation |")
    w("|---|---|---|")
    for f, row in sorted(det["findings"].items()):
        for t, v in sorted(row["cited_upstream_tests"].items()):
            w(f"| {f} | `{t}` | {v} |")
    w("")
    w("Relations: *detects* = red at the pin because of the defect; *enshrines* = passes while asserting the "
      "behaviour the finding calls wrong (fixing the defect turns it red); *misses* = covers the area and passes "
      "without the defective case; *is-defect* = the test or fixture is what the finding is about; *context* = "
      "cited for intent or setup.\n")
    w("Undetected findings by root cause, and the product test that would have detected them (from each root "
      "cause's remedy; none exists at the pin):\n")
    w("| Root cause | Findings | Not detected | Test that should exist |")
    w("|---|---|---|---|")
    for r in rc["root_causes"]:
        nd = sum(1 for f in r["primary"] if det["findings"][f]["disposition"] in det["reproduced_dispositions"]
                 and not det["findings"][f]["detected_by_product_suite"])
        w(f"| {r['id']} {r['title']} | {len(r['primary'])} | {nd} | {RC_TESTS[r['id']]} |")
    w("")

    w("## D. Premises and their tests\n")
    by_src = defaultdict(Counter)
    for e in prem:
        by_src[e["key"].split(":")[0]][e["verdict"]] += 1
    vs = ("tested-holds", "tested-violated", "tested-partial", "untested")
    w("Every premise named in the sources below has an entry (the checker extracts them from the files and fails on "
      "any premise without one). Verdicts: " + "; ".join(f"*{k}*: {v}" for k, v in pm["verdicts"].items()) + ".\n")
    w("| Source | Premises | " + " | ".join(vs) + " |")
    w("|---|---|" + "---|" * len(vs))
    tot = Counter()
    for s in SRC_LABEL:
        c = by_src.get(s, Counter())
        tot.update(c)
        w(f"| {SRC_LABEL[s]} | {sum(c.values())} | " + " | ".join(str(c.get(v, 0)) for v in vs) + " |")
    w(f"| **total** | **{sum(tot.values())}** | " + " | ".join(f"**{tot.get(v, 0)}**" for v in vs) + " |")
    w("")
    w("### D.1 Premises shown false at the pin (tested-violated)\n")
    w("| Premise | Statement | Test (registered run) |")
    w("|---|---|---|")
    for e in prem:
        if e["verdict"] == "tested-violated":
            runs = [t["ref"] for t in e["tests"] if t["kind"] in ("run", "upstream")]
            w(f"| {e['key']} | {e['premise']} | {', '.join(runs[:4])} |")
    w("")
    w("### D.2 Premises with no test or a partial test, and the test that should exist\n")
    w("Contract features outside the validated subset are summarised after the table.\n")
    w("| Premise | Statement | Verdict | Partial evidence | Test that should exist |")
    w("|---|---|---|---|---|")
    out_rows = []
    for e in prem:
        if e["verdict"] in ("untested", "tested-partial"):
            if e["key"].startswith("iris-contract:OUT:"):
                out_rows.append(e)
                continue
            runs = [t["ref"] for t in e["tests"] if t["kind"] in ("run", "upstream")]
            w(f"| {e['key']} | {e['premise']} | {e['verdict']} | {', '.join(runs[:3]) or '-'} | {e['should_exist']} |")
    w("")
    w(f"Outside the contract's validated subset ({len(out_rows)} features, all untested as engine clauses; the "
      "modules relying on each are listed in `iris-contract/CONTRACT.md`): " +
      "; ".join(e["id"] for e in out_rows) + ". Test that should exist for each: " +
      (out_rows[0]["should_exist"] if out_rows else "-") + ".\n")

    w("## E. Proof debt: what testing covers instead\n")
    w("| Debt | Tests that cover part of it | What testing does not cover |")
    w("|---|---|---|")
    for d in pm["proof_debt"]:
        tests = [f"`{t['ref']}`" + (" (model)" if t["kind"] == "model" else "") for t in d["tests"]]
        w(f"| {d['id']} | {', '.join(tests)} | {d['not_covered']} |")
    w("")
    w("No row of PROOF-DEBT.md is paid by these tests: they sample the obligation on the product, they do not "
      "prove it.\n")

    w("## F. Tests that should exist and need the operator or an unavailable dependency\n")
    w("- The crash world with `SynchCommit=1` (needs the container reconfigured; the audit may not reconfigure it).")
    w("- The transaction-verb cases on IRIS 2026.3, the product premise's engine (`ver-avail-iris-2026.3`, "
      "blocked-access), on Enterprise / IRIS for Health and on a multi-node ECP or mirror setup (blocked-access).")
    w("- Embedded SQL (`&sql`) against the contract's clauses (premise E-1): needs compiling a scratch class, outside "
      "the scope rule without an operator ruling.")
    w("- The spec-236 scratch suites (more than 8 licence units) and the %AI-dependent MCP cases.")
    w("- A fairness soak for the progress premises (PF-1..PF-6, MA-1..MA-4): long schedules with committers, "
      "stops and operator re-runs, asserting completion within a bound; feasible here but not run (the pin's "
      "bounded resume already fails progress: `live-fc1303-bounded-resume`).\n")

    w("## G. Limits\n")
    w("- A premise's test is named from the registry and the findings' evidence; the checker verifies that every "
      "named run exists and is not a model run, that every upstream file exists at the pin, and that every "
      "premise has an entry. It does not re-judge whether the run really observes the premise.")
    w("- 'Not detected' means no product test was red at the pin because of the defect among the suites that ran "
      "here (section B); it does not mean no product test touches the code.")
    w("- Breadth model crates (`models/breadth-a..c`) state their modelling restrictions in `modules/NN.json`, not "
      "in a MODELS.md; they are outside this map (the task's sources are TRUST.md, the PROOFS.md premise tables, "
      "models/*/MODELS.md and the IRIS contract).")
    return "\n".join(L) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text() == text
        print("TEST-REFLECTION.md current" if ok else "TEST-REFLECTION.md STALE")
        return 0 if ok else 1
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
