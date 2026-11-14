#!/usr/bin/env python3
"""Build validation/results.json from the run directories (machine-readable twin of SUITES.md).

    python finalize.py

Every number comes from the run's own files under $RUN_DIR/validation (pytest summary lines, JUnit XML, harness
meta.json, the TCK summary, the perf JSON lines / result files). Static context (environment, harness, incidents,
blocked lanes) is in results-static.json next to this file. A run that has not finished is reported as pending.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from aggregate import runs_of  # noqa: E402
from triage import RULES, triage  # noqa: E402

V = Path(os.environ["RUN_DIR"]) / "validation"

FUNCTIONAL = [
    # suite, decisive run prefixes, supporting runs (reruns/attempts), how it is meant to run
    ("tests/unit", ["unit-3"], ["unit-1", "unit-2"],
     "CI: pytest tests/unit with SKIP_IRIS_TESTS=true (.github/workflows/ci.yml); here with IRIS, so the live unit tests ran"),
    ("tests/integration", ["integration-1"], ["integration-1-c00-rerun", "rerun-1"],
     "TESTING.md `pytest -m integration` against the test container; not in CI"),
    ("tests/e2e (gate namespaces off)", ["e2e-1"], ["rerun-2", "rerun-3", "perm-rerun-1"],
     "TESTING.md `pytest -m e2e`; scripts/ci-parity.sh gate mode would make ~45 scratch namespaces (tests/e2e/gate.py)"),
    ("tests/e2e r306 algorithm oracle in USER (IVG_ORACLE_USER=1)", ["oracle-1"], [],
     "the runnable use of tests/oracle: test_460_r306_algorithm_oracle_e2e.py + _fixes_e2e.py, documented USER opt-in"),
    ("tests/tck (openCypher TCK, behave)", ["tck-1"], ["tck-unwind-rerun-1"],
     "scripts/tck/run_all.sh (one behave process per area, behave.ini) + scripts/tck/summarize.py"),
    ("tests/contract (default)", ["contract-1"], [], "conftest skips every item unless IVG_RUN_CONTRACT=1"),
    ("tests/contract (IVG_RUN_CONTRACT=1)", ["contract-optin-1"], [], "opt-in collection of the TDD stubs"),
    ("tests/docs", ["docs-2"], ["docs-1"], "ci-parity.sh: test_docs_consistent (static) + test_docs_run (needs IVG460DOC)"),
    ("tests/regression", ["regression-2"], ["regression-1"], "plain pytest, static budgets; not in CI"),
    ("tests/python", ["python-1"], [], "plain pytest against the container (+ REST on :52773)"),
    ("tests/test_schema_contract.py", ["schema-contract-1"], [], "plain pytest against the container"),
    ("tests/perf default selection (spec 227 SC-010 latency gate)", ["perf-default-1", "perf-default-2", "perf-default-3",
     "perf-default-4"], ["perf-default-540-1", "perf-default-540-2"],
     "default addopts -m 'not perf' leaves the 3 test_227 cases (interleaved medians); -540 runs use driver 5.4.0"),
    ("scratch-namespace fixtures (operator ruling 2026-11-14)", ["scratch-1"], [],
     "VALIDATION_SCRATCH_NS=1, IVG_NS_IVG460SNAP=IVG460SNAPVAL: the unit/integration files the guard had refused"),
    ("spec 236 scratch suites (IVG_NS_IVG236=IVG236VAL)", ["scratch-236-1"], ["scratch-236-2a", "scratch-236-2b"],
     "22 integration files using tests/conftest.py::ivg_236_scratch; blocked by the 8-unit licence"),
    ("tests/docs/test_docs_run.py in IVG460DOC (operator ruling)", ["docs-run-1", "docs-run-2"], ["docs-run-540-1"],
     "ci-parity.sh: IVG_NAMESPACE=IVG460DOC pytest tests/docs/test_docs_run.py after make_scratch_namespace.py IVG460DOC"),
    ("IVG262ALT-dependent files (operator ruling)", ["alt-1"], [],
     "IVG_NS_IVG262ALT=IVG262ALT: tests/e2e/test_262_alt_schema_paths.py (its fixture sets IVG262ALT up), "
     "tests/integration/test_grant_copy.py, tests/integration/test_cypher_advanced.py"),
    ("e2e gated subset, gate on (operator ruling)", ["gated-1", "gated-2", "gated-3", "gated-4", "gated-rag-1", "gated-rag-2"], [],
     "run_gated.sh: IVG_GATE_NAMESPACES=1 + scratch mode; the 102 primary-only and 44 rag-only gated files "
     "without threads/processes/extra users, one gate namespace per batch (made and dropped by the gate)"),
    ("driver A/B: 5.3.2 (pin uv.lock) vs 5.4.0, same 8 files, alternating", ["driver532-1", "driver540-1", "driver540-2", "gated-540-1", "gated-532-1", "gated-rag-540-1", "gated-rag-532-1"],
     ["driver540-oracle-1", "driver540-tck-unwind-1"],
     "A = earlier 5.3.2 runs (integration-1, e2e-1, rerun-1..3) and driver532-1; B = driver540-1/-2 with "
     "VALIDATION_DRIVER_SITE=$RUN_DIR/availability/driver-5.4.0-venv site-packages"),
    ("multi-process (existing ledger concurrency cases)", ["mp-existing-1", "mp-existing-2", "mp-existing-3"], [],
     "tests/integration/test_ledger_us03/us04/us09: separate OS processes, own DB-API connections"),
]
PERF = [
    ("spec 256 SC-002/SC-003 upstream (-m perf)", ["perf-sc256-upstream-1", "perf-sc256-upstream-2"]),
    ("spec 256 SC-003 committer-side, 1 committer process", ["perf-committer-n1-1", "perf-committer-n1-2"]),
    ("spec 256 SC-003 committer-side, 3 committer processes (multi-process)", ["perf-committer-n3-1"]),
    ("spec 213 ledger perf (-m perf, soak deselected)", ["perf-ledger-1"]),
    ("nodepk perf/performance", ["perf-nodepk-1"]),
    ("algorithms perf (communities, cypher benchmark, tests/perf -m perf)", ["perf-algos-1"]),
    ("tests/performance (-m performance)", ["perf-performance-1"]),
    ("spec 093 traversal benchmark tests/benchmarks/bench.py --datasets S M", ["bench-1", "bench-2"]),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pytest_run(prefix):
    if not runs_of(prefix):
        return {"id": prefix, "status": "pending" if not (V / prefix).exists() else "incomplete"}
    if prefix == "unit-2":  # stopped by this lane at 42% (connection-cap rule): no exit file by design
        return {"id": prefix, "status": "incomplete (stopped at 42%)", "log": str(V / prefix / "run.log"),
                "log_sha256": sha(V / prefix / "run.log")}
    if any(not (d / "exit").exists() for d in runs_of(prefix)):
        return {"id": prefix, "status": "running"}
    a, rules, unmatched = triage(prefix)
    chunks = [{k: c[k] for k in ("id", "exit", "counts", "log", "log_sha256")} for c in a["chunks"]]
    return {
        "id": prefix, "status": "done", "counts": a["counts"], "chunks": chunks, "license_failure": a["license_failure"],
        "namespaces_unchanged": a["namespaces_unchanged"], "guard_hits": a["guard_hits"],
        "triage": {rid: {"category": v["category"], "count": v["count"], "nodes": v["nodes"][:60],
                         "nodes_total": len(v["nodes"])} for rid, v in rules.items()},
        "untriaged": [[k, n, m[:300]] for k, n, m in unmatched],
        "skip_reasons_top": dict(list(a["skips"].items())[:25]),
    }


def tck_run(prefix):
    d = V / prefix
    if not (d / "summary.txt").exists():
        return {"id": prefix, "status": "pending"}
    drv = d / "driver.log"
    res = d / "results.tsv"
    failed = [ln.split("\t", 1)[1] for ln in res.read_text().splitlines() if ln.startswith("0\t")] if res.exists() else []
    return {"id": prefix, "status": "done", "summary": (d / "summary.txt").read_text().strip().splitlines()[:6],
            "failed_scenarios": failed, "log": str(drv), "log_sha256": sha(drv),
            "summary_sha256": sha(d / "summary.txt"),
            "license_failure": "LICENSE FAILURE" in drv.read_text(errors="replace")}


def tck_rerun(prefix):
    d = V / prefix
    if not (d / "driver.log").exists():
        return {"id": prefix, "status": "pending"}
    drv = d / "driver.log"
    return {"id": prefix, "status": "done", "summary": drv.read_text().strip().splitlines()[-3:], "log": str(drv),
            "log_sha256": sha(drv)}


def perf_run(prefix):
    if prefix.startswith("bench-"):
        d = V / prefix
        if not (d / "exit").exists():
            return {"id": prefix, "status": "pending"}
        results = sorted(d.glob("bench_*.json"))
        data = json.loads(results[-1].read_text()) if results else None
        return {"id": prefix, "status": "done", "exit": (d / "exit").read_text().strip(), "log": str(d / "run.log"),
                "log_sha256": sha(d / "run.log"), "result_file": str(results[-1]) if results else None,
                "result": data}
    r = pytest_run(prefix)
    if r.get("status") != "done":
        return r
    log = (V / prefix / "run.log").read_text(errors="replace")
    r["sc_lines"] = [ln.strip() for ln in log.splitlines() if re.match(r"^SC-00[23]:", ln)]
    jl = V / f"{prefix}.jsonl"
    if jl.exists():
        r["committer_cycles"] = [json.loads(x) for x in jl.read_text().splitlines() if x.strip()]
    extra = sorted((V / prefix).glob("ledger_*.json"))
    if extra:
        r["ledger_results"] = json.loads(extra[-1].read_text())
    return r


def main():
    static = json.loads((HERE / "results-static.json").read_text())
    out = {"lane": "validation", "generated_utc": __import__("datetime").datetime.utcnow().isoformat(timespec="seconds") + "Z",
           **static, "rules": [{"id": r[0], "category": r[1], "reason": r[4]} for r in RULES], "functional": [], "perf": []}
    for name, decisive, support, how in FUNCTIONAL:
        runner = tck_run if name.startswith("tests/tck") else pytest_run
        sup_runner = tck_rerun if name.startswith("tests/tck") else pytest_run
        if name.startswith("driver A/B"):
            out["functional"].append({"suite": name, "meant_to_run": how, "decisive": [pytest_run(p) for p in decisive],
                                      "supporting": [pytest_run(support[0]), tck_rerun(support[1])]})
            continue
        out["functional"].append({"suite": name, "meant_to_run": how, "decisive": [runner(p) for p in decisive],
                                  "supporting": [sup_runner(p) for p in support]})
    for name, prefixes in PERF:
        out["perf"].append({"measurement": name, "runs": [perf_run(p) for p in prefixes]})
    (HERE / "results.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {HERE / 'results.json'}")


if __name__ == "__main__":
    main()
