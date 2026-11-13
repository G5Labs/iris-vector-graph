#!/usr/bin/env python3
"""Digest the upstream test runs of this uplift into evidence/test-results.json.

    python experiment/playbook-uplift/tools/test_results.py

Reads $RUN_DIR/unit/junit.xml (the whole tests/unit set) and $RUN_DIR/final/upstream-community-redaction.log (the
spec 256 e2e file on IRIS Community). For each test function it records pass, fail, error or skipped (a parametrized
function passes only if every case passed). The ontology index uses it to show which `tested:` citations were run here.
"""
import hashlib, json, os, re, sys
import xml.etree.ElementTree as ET
from pathlib import Path

UPLIFT = Path(__file__).resolve().parent.parent
REPO = UPLIFT.parent.parent
RUN = Path(os.environ["RUN_DIR"])
RANK = {"pass": 0, "skipped": 1, "fail": 2, "error": 3}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def unit():
    j = RUN / "unit" / "junit.xml"
    files, skips = {}, {}
    for tc in ET.parse(j).getroot().iter("testcase"):
        mod = tc.get("classname", "")
        parts = mod.split(".")
        # classname is tests.unit.test_x[.TestClass]
        idx = next(i for i, x in enumerate(parts) if x.startswith("test_"))
        path = "/".join(parts[: idx + 1]) + ".py"
        name = tc.get("name", "").split("[")[0]
        st = "pass"
        for k, v in (("failure", "fail"), ("error", "error"), ("skipped", "skipped")):
            if tc.find(k) is not None:
                st = v
                if v == "skipped":
                    skips[f"{path}::{name}"] = "skipped: " + (tc.find(k).get("message") or "")[:140]
                break
        cur = files.setdefault(path, {}).get(name)
        if cur is None or RANK[st] > RANK[cur]:
            files[path][name] = st
    log = RUN / "unit" / "unit-full.log"
    summary = log.read_text(errors="replace").strip().splitlines()[-2]
    return {"kind": "run", "command": "SKIP_IRIS_TESTS=true python -m pytest tests/unit -q -o addopts= -m 'not perf'",
            "summary": summary, "log": "$RUN_DIR/unit/unit-full.log", "log_sha256": sha(log),
            "junit": "$RUN_DIR/unit/junit.xml", "junit_sha256": sha(j), "files": files,
            "triage": {"tests/unit/test_203_tck_regressions.py": "86 setup errors: the upstream fixture compiles every class "
                       "and the MCP classes need %AI, absent on IRIS Community (environment; P-0101/P-0106)",
                       "tests/unit/test_setup_logging.py::test_no_warning": "fails on 'Class or module gref not found in "
                       "iris_embedded_python' warnings from the client package in this venv (environment)"} | skips}


def community():
    log = RUN / "final" / "upstream-community-redaction.log"
    text = log.read_text(errors="replace")
    m = re.search(r"(\d+) passed", text)
    failed = re.search(r"(\d+) (failed|error)", text)
    path = "tests/integration/test_256_ledger_redaction_e2e.py"
    src = (REPO / path).read_text()
    names = re.findall(r"^\s*def (test_\w+)\(", src, re.MULTILINE)
    ok = bool(m) and not failed and int(m.group(1)) >= len(names)
    return {"kind": "live", "command": 'python "$RUN_DIR/run-community-redaction.py"',
            "summary": (m.group(0) if m else "no result line") + (f", {failed.group(0)}" if failed else ""),
            "log": "$RUN_DIR/final/upstream-community-redaction.log", "log_sha256": sha(log),
            "files": {path: {n: ("pass" if ok else "unknown") for n in names}}}


def main():
    out = {"unit-full": unit()}
    if (RUN / "final" / "upstream-community-redaction.log").exists():
        out["upstream-community-redaction"] = community()
    dest = UPLIFT / "evidence" / "test-results.json"
    dest.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    n = sum(len(v) for r in out.values() for v in r["files"].values())
    print(f"wrote {dest.relative_to(REPO)}: {n} test functions in {len(out)} runs")


if __name__ == "__main__":
    sys.exit(main())
