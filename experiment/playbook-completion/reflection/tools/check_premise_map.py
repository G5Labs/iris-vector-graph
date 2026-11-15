#!/usr/bin/env python3
"""Check reflection/premise_tests.json (gate 3.8-test-reflection, TEST-REFLECTION.md sections C-E).

    python check_premise_map.py              # exit 1 on any problem
    python check_premise_map.py --self-test  # the unmutated map passes; every seeded mutation is caught
    python check_premise_map.py --detection  # print the computed product-suite detection section (JSON)

Premise sources (read at check time, so a premise added to any of them fails the check until it is mapped):
  TRUST.md                 rows of its three tables (trusted items; premises whose status changed; new premises),
                           keyed TRUST:<table>:<first cell>
  proofs*/PROOFS.md        every row of each `| Id | Premise |` table, keyed <crate>:<id>; `PF-a..PF-b` rows are
                           expanded; every PF-n named anywhere in the file is a premise of that crate
  models/core/MODELS.md    every original premise id P-NNNN it names (models-core:P-NNNN), and the stated
                           assumptions listed in MODELS_ASSUMPTIONS below, each located by an anchor that must occur
                           verbatim in the file
  iris-contract/CONTRACT.md  every clause id of the validated clause table (iris-contract:<id>), premise E-1, the
                           unsharpened Freedom, and every row of the "Outside the semantic subset" table
                           (iris-contract:OUT:<feature>)
  PROOF-DEBT.md            every debt row D-n (section proof_debt)

Rules (problem tags): [missing] a source premise or debt row has no entry; [stale] an entry names no source premise;
[run] a cited run is not registered; [model-as-test] a run cited as a test of a premise about IRIS or the product is a model/proof/control run (for
premises of class "tool", the audit's own verifier, explorer and oracles, a control or proof run is the test); [upstream]
a cited upstream test file is not in the product tree at the pin; [verdict] an unknown verdict, a tested-* verdict
with no run or upstream test, a tested-holds/-violated verdict resting only on upstream tests that did not run here,
or an untested/partial verdict without should_exist; [anchor] a MODELS.md anchor is
not in the file; [debt] a debt row without tests or without should_exist; [detection] the detection section differs
from the one computed from the findings corpus and validation/results.json; [rule] a product-defect triage rule of
the validation lane is not mapped to a finding, or maps to an unknown finding; [cited-test] a finding cites an
upstream test file but has no relation entry, or a relation names a file the finding does not cite; [md] (main run
only) TEST-REFLECTION.md is not the current rendering (build_test_reflection.py).
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
ROOT = LANE.parent
REPO = ROOT.parent.parent
MAP = LANE / "premise_tests.json"
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
sys.path.insert(0, str(HERE))
from check_root_causes import load_corpus  # noqa: E402

VERDICTS = ("tested-holds", "tested-violated", "tested-partial", "untested")
MODEL_KINDS = ("mc", "proof", "control")
REPRODUCED = ("reproduced-live", "reproduced-test", "reproduced-model", "confirmed-source")
# every proof crate is read by glob (proofs*/PROOFS.md); none is listed by hand (review R4-09)


def proof_crates() -> list:
    return sorted(p.parent.name for p in ROOT.glob("proofs*/PROOFS.md"))


def model_dirs() -> list:
    return sorted(p.parent.name for p in (ROOT / "models").glob("*/MODELS.md"))

# Stated assumptions of each models/<dir>/MODELS.md (prose, no ids there): dir -> {id -> anchor (verbatim substring)}.
# A MODELS.md with no entry here fails the check ([missing]): its assumptions must be named before it is mapped.
MODELS_ASSUMPTIONS = {"core": {
    "MA-1": "writers become quiet (the path adds no commit or bypass write)",
    "MA-2": "the operator resumes stopped or paused runs (calls are\nunbounded)",
    "MA-3": "no process is stopped forever (the path contains no stop)",
    "MA-4": "the operator may erase a target again when a\nwrite made it live",
    "MA-5": "IRIS semantics come from the validated contract",
    "MA-6": "the delete case of dirty reads is the\n  general Visibility clause",
    "MA-7": "what matters about a writer is only (1)",
    "MA-8": "the census writers write content tables only",
    "MA-9": "batches of one record",
    "MA-10": "lock timeouts modelled as waits",
}, "core-partition": {
    "MP-1": "three ids, two graphs, three edges, no temporal edges",
    "MP-2": "at most 2 pre-enable writes, at most 2 ledger commits, at most 1 ledger-bypassing write",
    "MP-3": "the explorer is executable and unproved",
}}

# Proof crates whose premises are stated in prose instead of a `| Id | Premise |` table: crate -> {id -> anchor}.
# A crate with neither a premise table nor an entry here fails the check ([missing]).
PF_REFERENCES_ONLY = {"proofs-env"}
PROSE_PREMISES = {"proofs-mech": {
    "PM-1": "the worker is weakly fair",
    "PM-2": "the premise is that the run is resumed that many more times",
    "PM-3": "Kept as in the explorer (not generalised)",
}}
RANGE = re.compile(r"^(.*?)(\d+)\.\.(.*?)(\d+)$")


def expand_ids(cell: str) -> list:
    """'P-L1..P-L3, P-L5' -> [P-L1, P-L2, P-L3, P-L5]; 'P-D9-1..P-D9-5' -> [P-D9-1 .. P-D9-5]."""
    out = []
    for tok in [re.sub(r"\s*\(.*\)$", "", t.strip()) for t in cell.split(",") if t.strip()]:
        m = RANGE.match(tok)
        if m and m.group(1) == m.group(3) and int(m.group(2)) <= int(m.group(4)):
            out += [f"{m.group(1)}{n}" for n in range(int(m.group(2)), int(m.group(4)) + 1)]
        else:
            out.append(tok)
    return out

# Validation-lane triage rules that are product defects (validation/results.json `rules`), and the audit finding each
# rule reproduces. Test-stale / test-isolation rules are the suite's own staleness, not product findings.
RULE_TO_FINDING = {
    "decimal-score": "F-C1706", "duplicate-listerror": "F-C1706", "list-param-count": "F-C1706",
    "rrf-score-string": "F-C1706", "temporal-structural-cursor": "F-C0502", "leiden-karate-ari": "F-C1002",
    "sc010-latency": "F-C0606",
}

# How each upstream test a finding cites relates to the defect (from the finding's own record):
#   detects    the test is red at the pin because of the defect (validation triage)
#   enshrines  the test passes and asserts the as-built behaviour the finding says is wrong
#   misses     the test covers the area and passes without checking the defective case
#   is-defect  the test or fixture is itself what the finding is about
#   context    cited for intent or setup only
TEST_RELATIONS = {
    "F-0108": {"tests/conftest.py": "is-defect"},
    "F-0302": {"tests/unit/test_ledger_guard.py": "enshrines"},
    "F-0407": {"tests/e2e/test_degree_cache_live.py": "enshrines"},
    "F-0617": {"tests/integration/test_embedding_identity_refusal_e2e.py": "enshrines"},
    "F-0708": {"tests/unit/test_bm25_index.py": "enshrines"},
    "F-0711": {"tests/unit/test_ifind_and_fusion_sql.py": "misses"},
    "F-0803": {"tests/unit/test_lexer_parser_coverage.py": "misses"},
    "F-0810": {"tests/e2e/test_470_set_null_e2e.py": "misses"},
    "F-0815": {"tests/unit/test_cypher_posos_bugs.py": "enshrines"},
    "F-0904": {"tests/e2e/test_257_compiled_plans_e2e.py": "context"},
    "F-1012": {"tests/unit/test_236_reader_gate.py": "enshrines"},
    "F-1101": {"tests/integration/test_ledger_us04_idempotency.py": "misses"},
    "F-1108": {"tests/integration/test_ledger_us05_compat.py": "misses"},
    "F-1110": {"tests/unit/test_ledger_changeset.py": "misses"},
    "F-1112": {"tests/e2e/test_460_r281_ledger_post_commit_graph_e2e.py": "is-defect",
               "tests/e2e/test_460_r290_ledger_node_ops_graph_e2e.py": "is-defect"},
    "F-1509": {"tests/unit/test_231_fhir_bridge_fixes.py": "misses"},
    "F-C1802": {"tests/unit/test_460_r271_snapshot_raises.py": "misses"},
    "F-C1305": {"tests/unit/test_227_erase_plan.py": "enshrines"},
    "F-C1306": {"tests/e2e/test_460_upgrade_ledger_history_e2e.py": "misses"},
    "F-C1706": {"tests/e2e/test_460_proc_yield_alias_e2e.py": "detects",
                "tests/e2e/test_460_r284_retrieve_rrf_score_e2e.py": "detects"},
    "F-C0502": {"tests/e2e/test_temporal_structural_row_live.py": "detects"},
    "F-C1002": {"tests/e2e/test_communities_e2e.py": "detects", "tests/perf/test_leiden_four_way.py": "context"},
    "F-C0606": {"tests/perf/test_227_single_graph_latency.py": "detects"},
    "F-C0090": {"tests/unit/test_coverage_boost.py": "is-defect", "tests/unit/test_engine_deep.py": "is-defect"},
    "F-C0715": {"tests/e2e/test_463_search_id_escaping_e2e.py": "misses"},
    "F-C1641": {"tests/e2e/test_gql_node_queries.py": "misses"},
}
TEST_PATH = re.compile(r"\btests/[\w/.-]+\.py\b")


# ---------------------------------------------------------------------------------------------- sources
def _cells(line: str) -> list:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("`", "").replace("**", "")).strip()


def table_rows(text: str, header_prefix: str) -> list:
    """First cells of every data row of each table whose header row starts with header_prefix."""
    out, lines = [], text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith(header_prefix) and i + 1 < len(lines) and re.match(r"^\|[-| ]+\|$", lines[i + 1].strip()):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                out.append(_cells(lines[j])[0])
                j += 1
    return out


def section(text: str, title_start: str) -> str:
    m = re.search(rf"^## {re.escape(title_start)}.*?(?=^## |\Z)", text, re.S | re.M)
    return m.group(0) if m else ""


def source_premises() -> dict:
    """key -> source path (relative to the repository)."""
    out = {}
    trust = (ROOT / "TRUST.md").read_text()
    for tag, title, hdr in (("trusted", "Trusted items", "| Item |"),
                            ("changed", "Premises whose status changed", "| Premise |"),
                            ("new", "New premises introduced", "| Premise |")):
        for c in table_rows(section(trust, title), hdr):
            out[f"TRUST:{tag}:{_clean(c)}"] = "experiment/playbook-completion/TRUST.md"
    for crate in proof_crates():
        text = (ROOT / crate / "PROOFS.md").read_text()
        rel = f"experiment/playbook-completion/{crate}/PROOFS.md"
        rows = table_rows(text, "| Id | Premise |")
        for c in rows:
            for cid in expand_ids(_clean(c)):
                out[f"{crate}:{cid}"] = rel
        # PF-n named in prose are the crate's premises, except in crates that only cite other crates' PF-n without
        # assuming them (review A-03: proofs-env's ENV-4 says the contract does not imply them)
        if crate not in PF_REFERENCES_ONLY:
            for a, b in re.findall(r"\bPF-(\d+)\.\.PF-(\d+)\b", text):
                for n in range(int(a), int(b) + 1):
                    out[f"{crate}:PF-{n}"] = rel
            for n in set(re.findall(r"\bPF-(\d+)\b", text)):
                out[f"{crate}:PF-{n}"] = rel
        for pid in PROSE_PREMISES.get(crate, {}):
            out[f"{crate}:{pid}"] = rel
        if not rows and crate not in PROSE_PREMISES:
            out[f"{crate}:(no premise table and no named prose premises)"] = rel
    for d in model_dirs():
        models = (ROOT / "models" / d / "MODELS.md").read_text()
        rel = f"experiment/playbook-completion/models/{d}/MODELS.md"
        for pid in sorted(set(re.findall(r"\bP-\d{4}\b", models))):
            out[f"models-{d}:{pid}"] = rel
        for mid in MODELS_ASSUMPTIONS.get(d, {"(no named assumptions)": None}):
            out[f"models-{d}:{mid}"] = rel
    contract = (ROOT / "iris-contract" / "CONTRACT.md").read_text()
    rel = "experiment/playbook-completion/iris-contract/CONTRACT.md"
    for c in table_rows(section(contract, "Clauses (validated)"), "| Id | Clause |"):
        out[f"iris-contract:{_clean(c)}"] = rel
    if "premise E-1" in contract:
        out["iris-contract:E-1"] = rel
    if "**Freedom" in contract:
        out["iris-contract:Freedom"] = rel
    for c in table_rows(section(contract, "Outside the semantic subset"), "| Outside the subset |"):
        out[f"iris-contract:OUT:{_clean(c)[:60]}"] = rel
    return out


def debt_rows() -> list:
    text = (ROOT / "PROOF-DEBT.md").read_text()
    return [_clean(c) for c in table_rows(text, "| # | Obligation |")]


def anchor_for(key: str):
    """The named anchor for a prose premise key, else None."""
    head, _, pid = key.partition(":")
    if head.startswith("models-"):
        return MODELS_ASSUMPTIONS.get(head[len("models-"):], {}).get(pid)
    return PROSE_PREMISES.get(head, {}).get(pid)


def registry() -> dict:
    out = {}
    for p in (ROOT / "evidence" / "runs").glob("*.json"):
        d = json.loads(p.read_text())
        out[d.get("id", p.stem)] = d.get("kind")
    return out


def product_paths() -> set:
    r = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", PIN, "tests"],
                       capture_output=True, text=True, check=True)
    return set(r.stdout.split())


# ---------------------------------------------------------------------------------------------- detection
def detection(corpus: dict) -> dict:
    """Which reproduced findings does the product's own suite detect (a test red at the pin because of it)?"""
    recs = corpus["records"]
    results = json.loads((ROOT / "validation" / "results.json").read_text())
    reg = registry()
    rule_cat = {r["id"]: r["category"] for r in results["rules"]}
    runs_of, nodes_of = {}, {}
    for s in results["functional"] + results.get("perf", []):
        for run in s.get("decisive", []) + s.get("runs", []):
            for rule, v in (run.get("triage") or {}).items():
                rid = f"val-{run['id']}"
                runs_of.setdefault(rule, [])
                if rid in reg and rid not in runs_of[rule]:
                    runs_of[rule].append(rid)
                nodes_of.setdefault(rule, [])
                for n in (v.get("nodes") or [])[:2]:
                    if n not in nodes_of[rule] and len(nodes_of[rule]) < 3:
                        nodes_of[rule].append(n)
    defect_rules = sorted(r for r, c in rule_cat.items() if c.startswith("product-defect") and "test-" not in c)
    detected = {}
    for rule in defect_rules:
        f = RULE_TO_FINDING.get(rule)
        if f is None:
            continue
        d = detected.setdefault(f, {"rules": [], "runs": [], "tests": []})
        d["rules"].append(rule)
        d["runs"] = sorted(set(d["runs"]) | set(runs_of.get(rule, [])))
        d["tests"] += [n for n in nodes_of.get(rule, []) if n not in d["tests"]]
    rows = {}
    for f in sorted(recs):
        r = recs[f]
        cited = sorted(set(TEST_PATH.findall(json.dumps(r))))
        rel = TEST_RELATIONS.get(f, {})
        row = {"disposition": r.get("disposition"), "severity": r.get("severity"),
               "detected_by_product_suite": f in detected,
               "cited_upstream_tests": {t: rel.get(t, "unclassified") for t in cited}}
        if f in detected:
            row["detection"] = detected[f]
        rows[f] = row
    rep = [f for f in rows if rows[f]["disposition"] in REPRODUCED]
    und = [f for f in rep if not rows[f]["detected_by_product_suite"]]
    rel_count = Counter(v for f in rows for v in rows[f]["cited_upstream_tests"].values())
    return {
        "reproduced_dispositions": list(REPRODUCED),
        "product_defect_rules": defect_rules,
        "rule_to_finding": {r: RULE_TO_FINDING.get(r) for r in defect_rules},
        "counts": {"findings": len(rows), "reproduced": len(rep), "detected": len(rep) - len(und),
                   "not_detected": len(und),
                   "not_detected_by_severity": dict(sorted(Counter(rows[f]["severity"] for f in und).items())),
                   "not_detected_by_disposition": dict(sorted(Counter(rows[f]["disposition"] for f in und).items())),
                   "intent_undecided_or_blocked": sum(1 for f in rows if rows[f]["disposition"] in
                                                      ("intent-undecided", "blocked-access")),
                   "cited_test_relations": dict(sorted(rel_count.items()))},
        "detected": sorted(f for f in rep if rows[f]["detected_by_product_suite"]),
        "not_detected_s1": sorted(f for f in und if rows[f]["severity"] == "S1"),
        "findings": rows,
    }


# ---------------------------------------------------------------------------------------------- check
def md_render() -> str:
    from build_test_reflection import render  # noqa: E402  (rendering of the committed JSON files)
    return render()


def check(m: dict, sources: dict, debts: list, reg: dict, paths: set, models_text: str, det: dict,
          corpus: dict, md: str | None = None) -> list:
    probs = []
    entries = m.get("premises", [])
    keys = Counter(e.get("key") for e in entries)
    for k, n in keys.items():
        if n > 1:
            probs.append(f"[stale] premise key {k} appears {n} times")
    for k in sources:
        if k not in keys:
            probs.append(f"[missing] premise {k} ({sources[k]}) has no entry")
    for e in entries:
        k = e.get("key")
        if k not in sources:
            probs.append(f"[stale] entry {k} names no premise in the sources")
        elif e.get("source") != sources[k]:
            probs.append(f"[stale] entry {k} source {e.get('source')} != {sources[k]}")
        v = e.get("verdict")
        tests = e.get("tests", [])
        counted = [t for t in tests if t.get("kind") in ("run", "upstream")]
        decisive = [t for t in tests if t.get("kind") == "run" or (t.get("kind") == "upstream" and t.get("ran_here"))]
        if v not in VERDICTS:
            probs.append(f"[verdict] {k}: unknown verdict {v}")
        if v in ("tested-holds", "tested-violated", "tested-partial") and not counted:
            probs.append(f"[verdict] {k}: {v} with no run or upstream test")
        if v in ("tested-holds", "tested-violated") and not decisive:
            probs.append(f"[verdict] {k}: {v} rests on no registered run and no upstream test that ran here")
        if v in ("untested", "tested-partial") and not str(e.get("should_exist") or "").strip():
            probs.append(f"[verdict] {k}: {v} without should_exist")
        for t in tests:
            kind, ref = t.get("kind"), t.get("ref")
            if kind in ("run", "model"):
                if ref not in reg:
                    probs.append(f"[run] {k}: run {ref} is not registered")
                elif kind == "run" and reg[ref] in MODEL_KINDS and e.get("class") != "tool":
                    probs.append(f"[model-as-test] {k}: {ref} is a {reg[ref]} run cited as a test")
            elif kind == "upstream":
                if str(ref).split("::")[0] not in paths:
                    probs.append(f"[upstream] {k}: {ref} is not a test file at the pin")
            else:
                probs.append(f"[verdict] {k}: unknown test kind {kind}")
        want = anchor_for(k)
        if want is not None:
            anchor = e.get("anchor") or ""
            if anchor != want or anchor not in (REPO / e.get("source", "")).read_text():
                probs.append(f"[anchor] {k}: anchor not found in its source or not the named one")
    dmap = {d.get("id"): d for d in m.get("proof_debt", [])}
    for d in debts:
        e = dmap.get(d)
        if e is None:
            probs.append(f"[missing] debt row {d} has no entry")
            continue
        if not [t for t in e.get("tests", []) if t.get("kind") in ("run", "upstream")]:
            probs.append(f"[debt] {d}: no run or upstream test named")
        if not str(e.get("not_covered") or "").strip():
            probs.append(f"[debt] {d}: says nothing of what testing does not cover")
        for t in e.get("tests", []):
            if t.get("kind") in ("run", "model") and t.get("ref") not in reg:
                probs.append(f"[run] {d}: run {t.get('ref')} is not registered")
            if t.get("kind") == "run" and reg.get(t.get("ref")) in MODEL_KINDS:
                probs.append(f"[model-as-test] {d}: {t.get('ref')} is a model run cited as a test")
    for d in dmap:
        if d not in debts:
            probs.append(f"[stale] debt entry {d} is not a row of PROOF-DEBT.md")
    # validation rules
    results = json.loads((ROOT / "validation" / "results.json").read_text())
    for r in results["rules"]:
        c = r["category"]
        if c.startswith("product-defect") and "test-" not in c:
            f = RULE_TO_FINDING.get(r["id"])
            if f is None:
                probs.append(f"[rule] product-defect rule {r['id']} maps to no finding")
            elif f not in corpus["records"]:
                probs.append(f"[rule] rule {r['id']} maps to unknown finding {f}")
    for f, rel in TEST_RELATIONS.items():
        cited = set(TEST_PATH.findall(json.dumps(corpus["records"].get(f, {}))))
        for t in rel:
            if t not in cited:
                probs.append(f"[cited-test] {f}: relation for {t}, which the finding does not cite")
    for f, row in det["findings"].items():
        for t, v in row["cited_upstream_tests"].items():
            if v == "unclassified":
                probs.append(f"[cited-test] {f} cites {t} with no relation entry")
    if md is not None and md != md_render():
        probs.append("[md] TEST-REFLECTION.md is not the rendering of premise_tests.json, root_causes.json and closure.json")
    if m.get("detection") != det:
        a, b = m.get("detection") or {}, det
        diff = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
        probs.append(f"[detection] committed detection section differs from the computed one in {sorted(diff)}")
    return probs


def context():
    corpus = load_corpus()
    return (source_premises(), debt_rows(), registry(), product_paths(),
            (ROOT / "models" / "core" / "MODELS.md").read_text(), detection(corpus), corpus)


def self_test() -> int:
    base = json.loads(MAP.read_text())
    sources, debts, reg, paths, models, det, corpus = context()
    p0 = check(base, sources, debts, reg, paths, models, det, corpus)
    print(f"unmutated: {len(p0)} problems")
    for p in p0[:10]:
        print("  ", p)
    ok = not p0
    idx_tested = next(i for i, e in enumerate(base["premises"]) if e["verdict"] == "tested-holds"
                      and e.get("class") != "tool" and any(t["kind"] == "run" for t in e["tests"]))
    idx_untested = next(i for i, e in enumerate(base["premises"]) if e["verdict"] == "untested")
    idx_ma = next(i for i, e in enumerate(base["premises"]) if e["key"].startswith("models-core:MA-"))
    model_run = next(r for r, k in reg.items() if k == "mc")

    def drop_premise(m, s, c):
        m["premises"].pop(0)

    def new_source_premise(m, s, c):
        s["proofs-d1c:P-Z9"] = "experiment/playbook-completion/proofs-d1c/PROOFS.md"

    def stale_entry(m, s, c):
        e = copy.deepcopy(m["premises"][0])
        e["key"] = "proofs:P-C99"
        m["premises"].append(e)

    def bad_run(m, s, c):
        m["premises"][idx_tested]["tests"].append({"kind": "run", "ref": "rf-no-such-run", "what": "seeded"})

    def model_as_test(m, s, c):
        m["premises"][idx_tested]["tests"].append({"kind": "run", "ref": model_run, "what": "seeded"})

    def bad_upstream(m, s, c):
        m["premises"][idx_tested]["tests"].append({"kind": "upstream", "ref": "tests/no_such_test.py", "what": "x"})

    def tested_without_test(m, s, c):
        e = m["premises"][idx_untested]
        e["verdict"] = "tested-holds"
        e["tests"] = [t for t in e["tests"] if t["kind"] not in ("run", "upstream")]

    def holds_on_unrun_upstream(m, s, c):
        e = m["premises"][idx_untested]
        e["verdict"] = "tested-holds"
        e["tests"] = [{"kind": "upstream", "ref": sorted(paths)[0], "ran_here": False, "what": "seeded"}]

    def untested_without_should(m, s, c):
        m["premises"][idx_untested]["should_exist"] = ""

    def bad_anchor(m, s, c):
        m["premises"][idx_ma]["anchor"] = "this text is not in MODELS.md"

    def drop_debt(m, s, c):
        m["proof_debt"].pop(3)

    def debt_without_test(m, s, c):
        m["proof_debt"][0]["tests"] = []

    def detection_count(m, s, c):
        m["detection"]["counts"]["not_detected"] -= 1

    def detection_flag(m, s, c):
        f = m["detection"]["detected"][0]
        m["detection"]["findings"][f]["detected_by_product_suite"] = False

    def new_cited_test(m, s, c):
        f = next(i for i, r in c["records"].items() if i not in TEST_RELATIONS and r.get("disposition") in REPRODUCED)
        c["records"][f] = dict(c["records"][f], notes=str(c["records"][f].get("notes")) + " tests/unit/test_x.py")

    muts = [("missing", drop_premise), ("missing", new_source_premise), ("stale", stale_entry), ("run", bad_run),
            ("model-as-test", model_as_test), ("upstream", bad_upstream), ("verdict", tested_without_test), ("verdict", holds_on_unrun_upstream),
            ("verdict", untested_without_should), ("anchor", bad_anchor), ("missing", drop_debt),
            ("debt", debt_without_test), ("detection", detection_count), ("detection", detection_flag),
            ("cited-test", new_cited_test)]
    caught = 0
    for tag, fn in muts:
        m, s, c = copy.deepcopy(base), dict(sources), copy.deepcopy(corpus)
        fn(m, s, c)
        d = detection(c) if fn is new_cited_test else det
        probs = check(m, s, debts, reg, paths, models, d, c)
        hit = any(p.startswith(f"[{tag}]") for p in probs)
        caught += hit
        ok &= hit
        print(f"mutation {fn.__name__:24s} expects [{tag}]: {'CAUGHT' if hit else 'MISSED'} ({len(probs)} problems)")
    # extractor ratchets: ranges expand, every proofs*/PROOFS.md and models/*/MODELS.md is read, and a crate or
    # model whose premises are not named fails as [missing]
    ext = [("expand_ids", expand_ids("P-L1..P-L3, P-L5") == ["P-L1", "P-L2", "P-L3", "P-L5"]
            and expand_ids("P-D9-1..P-D9-3") == ["P-D9-1", "P-D9-2", "P-D9-3"] and expand_ids("P-LV (named here)") == ["P-LV"]),
           ("every crate read", {k.split(":")[0] for k in sources if k.startswith("proofs")} == set(proof_crates())),
           ("every model read", {k.split(":")[0][len("models-"):] for k in sources if k.startswith("models-")} == set(model_dirs()))]
    for name, pop in (("unnamed model assumptions", ("models", "core-partition")), ("unnamed prose premises", ("prose", "proofs-mech"))):
        table = MODELS_ASSUMPTIONS if pop[0] == "models" else PROSE_PREMISES
        saved = table.pop(pop[1])
        try:
            s2 = source_premises()
            probs = check(base, s2, debts, reg, paths, models, det, corpus)
            ext.append((name, any(p.startswith("[missing]") and "(no " in p for p in probs)))
        finally:
            table[pop[1]] = saved
    stale = md_render() + "edited by hand\n"
    ext.append(("stale TEST-REFLECTION.md", any(p.startswith("[md]") for p in
                                                check(base, sources, debts, reg, paths, models, det, corpus, stale))))
    for name, hit in ext:
        print(f"extractor {name:28s}: {'CAUGHT/OK' if hit else 'FAILED'}")
        ok &= hit
        caught += hit
    print(f"self-test: {caught}/{len(muts) + len(ext)} seeded mutations and extractor checks passed; unmutated {'clean' if not p0 else 'NOT clean'}")
    print("SELF-TEST PASS" if ok else "SELF-TEST FAIL")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    if "--detection" in sys.argv:
        print(json.dumps(detection(load_corpus()), indent=1))
        return 0
    m = json.loads(MAP.read_text())
    sources, debts, reg, paths, models, det, corpus = context()
    tr = LANE / "TEST-REFLECTION.md"
    probs = check(m, sources, debts, reg, paths, models, det, corpus, tr.read_text() if tr.exists() else "")
    v = Counter(e.get("verdict") for e in m.get("premises", []))
    by_src = Counter(e.get("key").split(":")[0] for e in m.get("premises", []))
    print(f"proof crates read by glob ({len(proof_crates())}): {', '.join(proof_crates())}")
    print(f"models read by glob ({len(model_dirs())}): {', '.join(model_dirs())}")
    print(f"premises in sources: {len(sources)}; entries: {len(m.get('premises', []))}")
    for src_name, n in sorted(by_src.items()):
        vv = Counter(e["verdict"] for e in m["premises"] if e["key"].split(":")[0] == src_name)
        print(f"  {src_name:22s} {n:3d}  " + ", ".join(f"{k} {vv.get(k, 0)}" for k in VERDICTS))
    print("verdicts: " + ", ".join(f"{k} {v.get(k, 0)}" for k in VERDICTS))
    print(f"debt rows ({len(debts)}): {', '.join(debts)}")
    c = det["counts"]
    print(f"findings {c['findings']}; reproduced {c['reproduced']}; detected by a red product test {c['detected']} "
          f"({', '.join(det['detected'])}); not detected {c['not_detected']} (by severity "
          f"{', '.join(f'{k} {n}' for k, n in c['not_detected_by_severity'].items())}); reproduced S1 not detected "
          f"{len(det['not_detected_s1'])}; intent-undecided or blocked {c['intent_undecided_or_blocked']}")
    print(f"product-defect triage rules mapped: {len(det['product_defect_rules'])} "
          f"({', '.join(f'{r}->{f}' for r, f in det['rule_to_finding'].items())}); cited upstream test relations: "
          + ", ".join(f"{k} {n}" for k, n in c["cited_test_relations"].items()))
    for p in probs:
        print("PROBLEM", p)
    print("CHECK PASS" if not probs else f"CHECK FAIL ({len(probs)} problems)")
    return 0 if not probs else 1


if __name__ == "__main__":
    sys.exit(main())
