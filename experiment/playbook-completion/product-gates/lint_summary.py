#!/usr/bin/env python3
"""Summarize one run of run_lint.sh: counts by tool and by rule, the module 11-14 subset, shadowed tests.

    python -I lint_summary.py OUT_DIR WORK_DIR      (writes OUT_DIR/summary.json, prints a text summary)

A tool passes only with zero findings under the product's own configuration (gate 3.5-lint).
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

OUT, ROOT = Path(sys.argv[1]), sys.argv[2].rstrip("/") + "/"
MODS_11_14 = ("iris_vector_graph/ledger/", "iris_vector_graph/_engine/ledger.py",
              "iris_vector_graph/_engine/nodes_edges.py")


def rd(name: str) -> str:
    p = OUT / name
    return p.read_text(errors="replace") if p.exists() else ""


def rel(p: str) -> str:
    return p.replace(ROOT, "").lstrip("./") if p.startswith((ROOT, "./")) else p


def top(c: collections.Counter, n: int = 40) -> dict:
    return dict(c.most_common(n))


s: dict = {"tools": {}}


def ruff(name: str) -> None:
    findings = json.loads(rd(f"{name}.out") or "[]")
    by_rule = collections.Counter(f["code"] for f in findings)
    files = {rel(f["filename"]) for f in findings}
    sub = collections.Counter(f["code"] for f in findings if rel(f["filename"]).startswith(MODS_11_14))
    shadowed = [{"file": rel(f["filename"]), "line": f["location"]["row"], "message": f["message"]}
                for f in findings if f["code"] == "F811" and re.search(r"`test_\w+`", f["message"])
                and rel(f["filename"]).startswith("tests/")]
    s["tools"][name] = {"rc": int(rd(f"{name}.rc") or -1), "findings": len(findings), "files": len(files),
                        "by_rule": top(by_rule, 200), "modules_11_14": dict(sub),
                        "by_top_dir": dict(collections.Counter(rel(f["filename"]).split("/")[0] for f in findings)),
                        "shadowed_test_functions_F811": shadowed}


ruff("ruff-0.15.14")
ruff("ruff-current")

err = rd("black.err")
reformat = [rel(ln.split("would reformat ", 1)[1].strip()) for ln in err.splitlines() if ln.startswith("would reformat ")]
m = re.search(r"(\d+) files? would be reformatted, (\d+) files? would be left unchanged", err)
s["tools"]["black"] = {"rc": int(rd("black.rc") or -1), "files_would_reformat": len(reformat),
                       "summary_line": m.group(0) if m else err.strip().splitlines()[-1:],
                       "modules_11_14_would_reformat": sorted(f for f in reformat if f.startswith(MODS_11_14))}

isort_err = [rel(ln.split("ERROR: ", 1)[1].split(" Imports are", 1)[0]) for ln in rd("isort.err").splitlines()
             if ln.startswith("ERROR: ")]
s["tools"]["isort"] = {"rc": int(rd("isort.rc") or -1), "files_incorrectly_sorted": len(isort_err),
                       "modules_11_14": sorted(f for f in isort_err if f.startswith(MODS_11_14))}

fl = [ln.split(":", 4) for ln in rd("flake8.out").splitlines() if ln.count(":") >= 4]
fl_rule = collections.Counter(x[3] for x in fl)
s["tools"]["flake8"] = {"rc": int(rd("flake8.rc") or -1), "findings": len(fl),
                        "files": len({rel(x[0]) for x in fl}), "by_rule": top(fl_rule, 200),
                        "modules_11_14": dict(collections.Counter(x[3] for x in fl if rel(x[0]).startswith(MODS_11_14))),
                        "E501_share": round(fl_rule.get("E501", 0) / max(1, len(fl)), 4)}

my = rd("mypy.out").splitlines()
errs = [ln for ln in my if ": error:" in ln]
codes = collections.Counter(ln.rstrip().rsplit("[", 1)[-1].rstrip("]") for ln in errs)
summ = [ln for ln in my if ln.startswith(("Found ", "Success"))]
sub = collections.Counter(ln.rstrip().rsplit("[", 1)[-1].rstrip("]") for ln in errs if ln.startswith(MODS_11_14))
s["tools"]["mypy"] = {"rc": int(rd("mypy.rc") or -1), "errors": len(errs),
                      "notes": sum(1 for ln in my if ": note:" in ln), "summary_line": summ[-1] if summ else None,
                      "by_code": top(codes, 100), "modules_11_14": dict(sub),
                      "modules_11_14_non_annotation": [ln for ln in errs if ln.startswith(MODS_11_14) and not re.search(
                          r"\[(no-untyped-def|no-any-return|var-annotated|attr-defined)\]$", ln)]}

md = [ln for ln in rd("markdownlint.err").splitlines() if re.search(r" MD\d{3}/", ln)]
mdr = collections.Counter(re.search(r" (MD\d{3}/[\w-]+)", ln).group(1) for ln in md)
msum = [ln for ln in rd("markdownlint.out").splitlines() if ln.startswith("Summary:")]
s["tools"]["markdownlint-cli2"] = {"rc": int(rd("markdownlint.rc") or -1), "issues": len(md),
                                   "files": len({ln.split(":", 1)[0] for ln in md}), "by_rule": dict(mdr),
                                   "summary_line": msum[-1] if msum else None,
                                   "files_checked": len(rd("md-files.txt").split())}
pw = [ln[7:].strip() for ln in rd("prettier.err").splitlines()
      if ln.startswith("[warn] ") and not ln.startswith("[warn] Code style")]
s["tools"]["prettier"] = {"rc": int(rd("prettier.rc") or -1), "files_not_formatted": len(pw), "files": pw}

s["versions"] = dict(ln.split(": ", 1) for ln in rd("versions.txt").splitlines() if ": " in ln)
s["zero_warnings"] = {k: (v.get("rc") == 0) for k, v in s["tools"].items()}
(OUT / "summary.json").write_text(json.dumps(s, indent=1))

t = s["tools"]
print("versions:", json.dumps(s["versions"]))
print(f"ruff 0.15.14 (default rules): {t['ruff-0.15.14']['findings']} findings in {t['ruff-0.15.14']['files']} files;"
      f" top {list(t['ruff-0.15.14']['by_rule'].items())[:8]}")
print(f"ruff current ({s['versions'].get('ruff_current')}): {t['ruff-current']['findings']} findings in "
      f"{t['ruff-current']['files']} files")
print(f"black --check: {t['black']['summary_line']}")
print(f"isort --check-only: {t['isort']['files_incorrectly_sorted']} files")
print(f"flake8 (defaults): {t['flake8']['findings']} findings in {t['flake8']['files']} files;"
      f" E501 {t['flake8']['by_rule'].get('E501', 0)}")
print(f"mypy: {t['mypy']['summary_line']}")
print(f"markdownlint-cli2: {t['markdownlint-cli2']['summary_line']}; by rule {t['markdownlint-cli2']['by_rule']}")
print(f"prettier --check: {t['prettier']['files_not_formatted']} files {t['prettier']['files']}")
print("modules 11-14: ruff", t["ruff-0.15.14"]["modules_11_14"], "flake8", t["flake8"]["modules_11_14"],
      "mypy", t["mypy"]["modules_11_14"], "black", len(t["black"]["modules_11_14_would_reformat"]),
      "isort", len(t["isort"]["modules_11_14"]))
print("shadowed test functions (F811):", [(x["file"], x["line"]) for x in t["ruff-0.15.14"]["shadowed_test_functions_F811"]])
print("zero warnings:", s["zero_warnings"])
