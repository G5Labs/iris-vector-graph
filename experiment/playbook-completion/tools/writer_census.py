#!/usr/bin/env python3
"""§3.3a writer census: every source site that writes a store the ledger/redaction invariants read.

    python writer_census.py [--json OUT] [--self-test]

The original write-set manifest (experiment/playbook-uplift/semantics/writesets.json) declares 15 plans by hand, so
it cannot discover an omitted writer (baseline audit, §3.3a). This census derives writers from the source text:
- ObjectScript (iris_src/src/**/*.cls): SET/KILL/MERGE of ^IVG.Ledger(<sub>...) and SQL INSERT/UPDATE/DELETE/TRUNCATE
  on the content tables and Graph_KG.ledger_revisions (embedded &sql and %ExecDirect text);
- Python (iris_vector_graph/**/*.py): SQL text literals writing those tables, and Native API set/kill/increment of
  ^IVG.Ledger.
Each site is mapped to its enclosing method/function and compared with the manifest's plans (by file and line
range). A site no plan covers is an omitted writer: every (invariant, writer) pair whose read set meets its store
becomes an obligation the matrix must discharge (proof, model check, live check, guard, or finding).
The self-test plants one covered and one uncovered writer and requires exactly the uncovered one to be reported.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "experiment/playbook-uplift/semantics/writesets.json"
LEDGER_SUBS = {"rec": "rec", "idem": "idem", "idemRedacted": "idemRedacted", "redactedRev": "redactedRev",
               "redacting": "marker", "stmt": "stmt", "tuple": "stmt", "stmtNext": "stmt"}
CONTENT = ("nodes", "rdf_labels", "rdf_props", "rdf_edges")
SQLW = re.compile(r"\b(INSERT\s+(?:OR\s+UPDATE\s+)?INTO|UPDATE|DELETE\s+FROM|TRUNCATE\s+TABLE)\s+([A-Za-z_%.{}\"]+)", re.I)
GLW = re.compile(r"\b(?:Set|Kill|Merge|S|K|M)\s+\^IVG\.Ledger\(\s*\"(\w+)\"", re.I)
GLW_BARE = re.compile(r"\b(?:Kill|K)\s+\^IVG\.Ledger\b(?!\()", re.I)


def table_store(name: str):
    n = name.strip('"').split(".")[-1].lower().replace("{", "").replace("}", "")
    for t in CONTENT:
        if n.endswith(t.lower()) or n == t:
            return "content"
    if "ledger_revisions" in n:
        return "meta"
    return None


def cls_sites(path: Path, text: str):
    method = "?"
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"\s*(?:Class)?Method\s+(\w+)", line)
        if m:
            method = m.group(1)
            continue
        s = line.split("//")[0]
        if s.lstrip().startswith("///"):
            continue
        for g in GLW.finditer(s):
            store = LEDGER_SUBS.get(g.group(1))
            if store:
                yield i, method, store, s.strip()[:140]
        if GLW_BARE.search(s):
            yield i, method, "ledger-all", s.strip()[:140]
        for w in SQLW.finditer(s):
            store = table_store(w.group(2))
            if store:
                yield i, method, store, s.strip()[:140]


def py_sites(path: Path, text: str):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    funcs = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append((node.lineno, getattr(node, "end_lineno", node.lineno), node.name))

    def owner(line):
        best = "?"
        for a, b, n in funcs:
            if a <= line <= b:
                best = n
        return best
    for node in ast.walk(tree):
        s = None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
        elif isinstance(node, ast.JoinedStr):
            s = "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{X}." for v in node.values)
        if s:
            for w in SQLW.finditer(s):
                store = table_store(w.group(2))
                if store:
                    yield node.lineno, owner(node.lineno), store, " ".join(s.split())[:140]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("set", "kill", "increment"):
            if any(isinstance(a, ast.Constant) and a.value == "^IVG.Ledger" for a in node.args):
                subs = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                store = next((LEDGER_SUBS[x] for x in subs if x in LEDGER_SUBS), "ledger-all")
                yield node.lineno, owner(node.lineno), store, ast.unparse(node)[:140]


def plans():
    d = json.loads(MANIFEST.read_text())
    out = []
    for name, p in d["plans"].items():
        m = re.match(r"(.+):(\d+)-(\d+)", p["code"])
        if m:
            out.append((name, m.group(1), int(m.group(2)), int(m.group(3)), set(p["writes"])))
    return out, d


CALL_CLS = re.compile(r"(?:##class\(([\w.]+)\)|\.\.)\.?(\w+)\(")


def call_graph(files):
    """ObjectScript methods per class with their line ranges and callees; Python functions with callees by name."""
    meth = {}      # (file, name) -> (start, end, callees set of names, class)
    for path, text in files:
        rel = str(path.relative_to(REPO)) if path.is_absolute() else str(path)
        if path.suffix == ".cls":
            cls = rel.split("iris_src/src/")[-1][:-4].replace("/", ".")
            cur, start, body = None, 0, []
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                m = re.match(r"\s*(?:Class)?Method\s+(\w+)", line)
                if m:
                    if cur:
                        meth[(rel, cur)] = (start, i - 1, {c[1] for c in CALL_CLS.findall("\n".join(body))}, cls)
                    cur, start, body = m.group(1), i, []
                elif cur:
                    body.append(line)
            if cur:
                meth[(rel, cur)] = (start, len(lines), {c[1] for c in CALL_CLS.findall("\n".join(body))}, cls)
        else:
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                             for n in ast.walk(node) if isinstance(n, ast.Call)}
                    meth[(rel, node.name)] = (node.lineno, getattr(node, "end_lineno", node.lineno), calls, rel)
    return meth


def reachable_from_plans(meth, ps):
    """Plan name -> set of (file, method) reachable from the plan's code range (by callee name, transitively)."""
    by_name = {}
    for (f, n), v in meth.items():
        by_name.setdefault(n, []).append((f, n))
    out = {}
    for name, f, a, b, _w in ps:
        seeds = [(ff, n) for (ff, n), (s0, e0, _c, _k) in meth.items() if ff == f and s0 <= b and e0 >= a]
        seen, todo = set(seeds), list(seeds)
        while todo:
            k = todo.pop()
            for callee in meth.get(k, (0, 0, set(), ""))[2]:
                for t in by_name.get(callee, []):
                    if t not in seen and (t[0].endswith(".cls") == k[0].endswith(".cls")):
                        seen.add(t)
                        todo.append(t)
        out[name] = seen
    return out


def census(files):
    files = list(files)
    ps, d = plans()
    meth = call_graph(files)
    reach = reachable_from_plans(meth, ps)
    sites = []
    for path, text in files:
        rel = str(path.relative_to(REPO)) if path.is_absolute() else str(path)
        gen = cls_sites(path, text) if path.suffix == ".cls" else py_sites(path, text)
        for line, owner, store, src in gen:
            cover = [n for n, f, a, b, w in ps if f == rel and a <= line <= b]
            via = sorted(n for n, r in reach.items() if (rel, owner) in r and n not in cover)
            sites.append({"file": rel, "line": line, "owner": owner, "store": store, "src": src, "plans": cover,
                          "via_call": via})
    invs = d["invariants"]
    uncovered = [s for s in sites if not s["plans"] and not s["via_call"]]
    owners = {}
    for s in uncovered:
        owners.setdefault((s["file"], s["owner"]), set()).add(s["store"])
    obligations = []
    for (f, o), stores in sorted(owners.items()):
        for inv, v in invs.items():
            hit = set(v["reads"]) & (stores | ({"rec", "marker", "stmt", "idem", "idemRedacted", "redactedRev"}
                                               if "ledger-all" in stores else set()))
            if hit:
                obligations.append({"invariant": inv, "writer": f"{f}::{o}", "stores": sorted(hit)})
    return {"sites": len(sites), "covered_sites": len(sites) - len(uncovered), "uncovered_sites": len(uncovered),
            "covered_via_call": sum(1 for s in sites if not s["plans"] and s["via_call"]),
            "uncovered_writers": sorted(f"{f}::{o}" for f, o in owners), "new_obligations": obligations,
            "detail": sites}


def product_files():
    for p in sorted((REPO / "iris_src" / "src").rglob("*.cls")):
        yield p, p.read_text(errors="replace")
    for p in sorted((REPO / "iris_vector_graph").rglob("*.py")):
        yield p, p.read_text(errors="replace")


def main() -> int:
    if "--self-test" in sys.argv:
        covered = (REPO / "iris_src/src/Graph/KG/Ledger.cls", "\n" * 399 + '    Set ^IVG.Ledger("rec", 1, 1) = 1\n')
        stray = (REPO / "iris_src/src/Graph/KG/Stray.cls", 'ClassMethod X()\n{\n    Kill ^IVG.Ledger("stmt", 5)\n}\n')
        r = census([covered, stray])
        ok = r["uncovered_writers"] == ["iris_src/src/Graph/KG/Stray.cls::X"] and r["covered_sites"] == 1
        print("self-test", "PASS" if ok else "FAIL", r["uncovered_writers"], r["covered_sites"])
        return 0 if ok else 1
    r = census(product_files())
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(r, indent=1))
    print(f"{r['sites']} writer sites; {r['covered_sites']} inside a declared plan; {r['uncovered_sites']} outside")
    print(f"{len(r['uncovered_writers'])} writers no plan declares; {len(r['new_obligations'])} new (invariant, writer) obligations")
    for w in r["uncovered_writers"]:
        print("  ", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
