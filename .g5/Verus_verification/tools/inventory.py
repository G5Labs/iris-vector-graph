#!/usr/bin/env python3
"""Pinned source inventory and link coverage numbers (reviewed plan section 8). Read-only.

    python3 .g5/Verus_verification/tools/inventory.py            # prints the numbers, writes coverage/inventory.json

Inventory at the product pin 3eaa79cf, read with `git show` (never the working tree):
- Python: every function, method and class-level def under iris_vector_graph/, by AST qualified name; public = no
  leading underscore in its own name.
- ObjectScript: every ClassMethod, Method, Query and Trigger member under iris_src/, by member keyword, per class.
- SQL files under sql/. Listed outside the denominator: api/, src/, scripts/ (Python files and definitions).
Links: crosswalk/decision-links.tsv. A symbol counts as **directly linked** when a row with relation models, proves or
witnesses names it with a formal item of an active family; **indirectly** when it appears only with relation observes
or with no formal item. Numbers are reported per language and never added across strata. Standard library only.
"""
from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
V = REPO / ".g5/Verus_verification"
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"


def git(*a):
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True).stdout


def files(prefix, suffix):
    return [p for p in git("ls-tree", "-r", "--name-only", PIN, prefix).splitlines() if p.endswith(suffix)]


def py_defs(src):
    out = []

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append(prefix + ch.name)
                walk(ch, prefix + ch.name + ".")
            elif isinstance(ch, ast.ClassDef):
                walk(ch, prefix + ch.name + ".")
            else:
                # if/try/with/loop blocks do not introduce a Python name scope.
                walk(ch, prefix)
    try:
        walk(ast.parse(src), "")
    except SyntaxError:
        pass
    return out


def main():
    inv = {"pin": PIN}
    py = {}
    for f in files("iris_vector_graph/", ".py"):
        py[f] = py_defs(git("show", f"{PIN}:{f}"))
    n_py = sum(len(v) for v in py.values())
    n_pub = sum(1 for v in py.values() for q in v if not q.split(".")[-1].startswith("_"))
    inv["python"] = {"files": len(py), "definitions": n_py, "public": n_pub}
    os_kw = Counter()
    os_members = {}
    classes = files("iris_src/", ".cls")
    for f in classes:
        src = git("show", f"{PIN}:{f}")
        ms = re.findall(r"^(ClassMethod|Method|Query|Trigger)\s+([A-Za-z%][A-Za-z0-9]*)", src, re.M)
        os_kw.update(k for k, _ in ms)
        os_members[f] = [m for _, m in ms]
    inv["objectscript"] = {"classes": len(classes), **dict(os_kw), "members": sum(os_kw.values())}
    inv["sql_files"] = len(files("sql/", ".sql"))
    inv["outside_denominator"] = {d: {"python_files": len(files(d, ".py")),
                                      "definitions": sum(len(py_defs(git("show", f"{PIN}:{f}"))) for f in files(d, ".py"))}
                                  for d in ("api/", "src/", "scripts/")}
    links = list(csv.DictReader(open(V / "crosswalk/decision-links.tsv"), delimiter="\t"))
    fams = {r["family_id"]: r["status"] for r in csv.DictReader(open(V / "families.tsv"), delimiter="\t")}

    def active(fam):
        f = fam.replace("P-proofs-", "playbook-proofs-")
        return fams.get(f, "").startswith("active")
    direct, indirect = set(), set()
    support_inputs, unresolved = set(), set()
    blocks_roles = {}
    for r in links:
        key = (r["path"], r["symbol"])
        path, symbol = key
        definitions = py.get(path, []) if path.endswith(".py") else os_members.get(path, [])
        if definitions.count(symbol) != 1:
            # Constants are valid supporting inputs, but are not function/method definitions in this denominator.
            src = git("show", f"{PIN}:{path}")
            assignments = {n.id for top in ast.parse(src).body if isinstance(top, (ast.Assign, ast.AnnAssign))
                           for target in (top.targets if isinstance(top, ast.Assign) else [top.target])
                           for n in ast.walk(target) if isinstance(n, ast.Name)} if path.endswith(".py") else set()
            (support_inputs if symbol in assignments else unresolved).add(key)
            continue
        item = r["formal item"]
        if item not in ("", "-"):
            formal_path, _, fn = item.partition("::")
            f = REPO / formal_path
            if not f.is_file() or len(re.findall(rf"\bfn\s+{re.escape(fn)}\b", f.read_text())) != 1:
                unresolved.add(key)
                continue
        is_direct = r["relation"] in ("models", "proves", "witnesses") and r["formal item"] not in ("", "-") and active(r["family"])
        (direct if is_direct else indirect).add(key)
        blocks_roles.setdefault(r["block"], set()).add(r["role"])
    indirect -= direct
    lang = lambda keys, ext: sum(1 for p, _ in keys if p.endswith(ext))
    inv["links"] = {
        "decision_links_rows": len(links),
        "direct": {"python": lang(direct, ".py"), "objectscript": lang(direct, ".cls")},
        "indirect_only": {"python": lang(indirect, ".py"), "objectscript": lang(indirect, ".cls")},
        "support_inputs_excluded_from_definition_counts": [f"{p}::{s}" for p,s in sorted(support_inputs)],
        "unresolved_excluded_from_definition_counts": [f"{p}::{s}" for p,s in sorted(unresolved)],
        "blocks_linked": len(blocks_roles),
        "blocks_with_writer_or_producer_and_reader_or_consumer": sorted(
            b for b, roles in blocks_roles.items() if roles & {"writer", "producer"} and roles & {"reader", "consumer"}),
        "blocks_with_one_side_only": sorted(
            b for b, roles in blocks_roles.items() if not (roles & {"writer", "producer"} and roles & {"reader", "consumer"})),
    }
    # tested upstream: test files at the pin, by kind (not a per-symbol mapping)
    tests = files("tests/", ".py")
    inv["tested_upstream"] = {"test_files": len([t for t in tests if Path(t).name.startswith("test_")]),
                              "by_directory": dict(Counter(t.split("/")[1] for t in tests if Path(t).name.startswith("test_"))),
                              "note": "test files at the pin; no per-symbol mapping is claimed"}
    inv["implementation_verified"] = 0
    out = V / "coverage"
    out.mkdir(exist_ok=True)
    (out / "inventory.json").write_text(json.dumps(inv, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: inv[k] for k in ("python", "objectscript", "sql_files", "outside_denominator")}, indent=1))
    L = inv["links"]
    print(f"direct links: Python {L['direct']['python']} of {inv['python']['definitions']} definitions; "
          f"ObjectScript {L['direct']['objectscript']} of {inv['objectscript']['members']} members")
    print(f"indirect only: Python {L['indirect_only']['python']}; ObjectScript {L['indirect_only']['objectscript']}")
    print(f"blocks linked: {L['blocks_linked']}; writer and reader both linked: {len(L['blocks_with_writer_or_producer_and_reader_or_consumer'])}")
    print("implementation-verified: 0")
    print(f"support inputs outside definition denominator: {len(support_inputs)}; unresolved: {len(unresolved)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
