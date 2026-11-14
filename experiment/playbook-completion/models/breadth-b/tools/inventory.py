#!/usr/bin/env python3
"""Mechanical entry-point inventory for breadth lane B (modules 07..11), playbook §3.1 reconciliation.

    python experiment/playbook-completion/models/breadth-b/tools/inventory.py 07 [08 ...]

Reads the module's scope file `tools/scope/NN.json` (which product files/classes/methods the module owns, chosen from
the ontology's Scope line) and derives every entry point from the product source at the pin, without hand listing:

- `cls:`   every public ClassMethod/Method of an owned ObjectScript class (not [Private]/[Internal]); flags SqlProc,
           SqlName, and %SYS.Task.Definition subclasses (`task:`);
- `py:`    every public function and public method of a public class in an owned Python file;
- `eng:`   every public IRISGraphEngine method (engine.py and its _engine mixins) whose file/name match the scope;
- `route:` every REST <Route> whose Call target is in scope;
- `cypher:` every registered Cypher procedure (engine._SYSTEM_PROCEDURES and translator `ivg.*` names) in scope;
- `cli:`   every click command in iris_vector_graph/cli.py in scope;
- `sqlfn:` every generated SQL procedure/function in iris_vector_graph/schema.py in scope.

For each entry point it records the source span, a static footprint hint (globals/tables read and written, TSTART/
TCOMMIT/TROLLBACK, LOCK, %NOLOCK, $Increment; transitive over ObjectScript `##class(..).M(` and `..M(` calls and
Python `self.m(` / classMethodValue("Cls","M") calls), and the ontology statements that cover it: a statement covers an
entry point when its Evidence/Source/Notes cite the entry point's file with a line range overlapping its span, or name
it (qualified name, or method name together with its class/file). Cells are mapped to entry points through the scope
file's `cell_map`; the output lists entry points no statement covers (omissions) and cells with no entry point.

Output: experiment/playbook-completion/models/breadth-b/inventory/NN.json. Static hints are evidence of kind
`inspected` at best; footprints/NN.json records the reviewed footprint.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
OUT = HERE.parent / "inventory"
ONTO = REPO / "experiment" / "playbook-uplift" / "ontology"
CLS_ROOT = REPO / "iris_src" / "src"

# ---------------------------------------------------------------- ObjectScript parsing
SIG = re.compile(r"^(ClassMethod|Method|Query)\s+(%?\w+)\s*\(")
CLASS = re.compile(r"^Class\s+([\w.%]+)(?:\s+Extends\s+(\(?[\w.%, ]+\)?))?")


def parse_cls(path: Path):
    lines = path.read_text(errors="replace").splitlines()
    cname, extends = None, ""
    methods = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = CLASS.match(ln)
        if m and cname is None:
            cname, extends = m.group(1), (m.group(2) or "")
        m = SIG.match(ln)
        if m:
            kind, name = m.group(1), m.group(2)
            sig = ln
            j = i
            while "{" not in lines[j] and not lines[j].rstrip().endswith("]") and j + 1 < len(lines) and j - i < 6:
                j += 1
                sig += " " + lines[j]
            kw = ""
            km = re.search(r"\[([^\]]*)\]\s*$", sig.strip())
            if km:
                kw = km.group(1)
            # body: until a line that is exactly "}"
            k = j + 1
            while k < len(lines) and lines[k].rstrip() != "}":
                k += 1
            methods.append({"kind": kind, "name": name, "start": i + 1, "end": k + 1, "keywords": kw,
                            "body": "\n".join(lines[i:k + 1])})
            i = k
        i += 1
    return cname, extends, methods


def is_public_cls(m):
    kw = m["keywords"]
    return not re.search(r"\b(Private|Internal)\b", kw)


# ---------------------------------------------------------------- footprint hints
GLOBAL_TOKEN = re.compile(r"(\^\|\|?[\w.%]*\|?)?(\^\|\|[\w.%]+|\^[\w.%]+)\s*(\()?")


def gname(tok: str) -> str:
    return tok


def cls_hints(body: str):
    w, r, k, lk = set(), set(), set(), set()
    flags = set()
    for raw in body.splitlines():
        ln = raw.split("//")[0]
        s = ln.strip()
        if not s or s.startswith("///"):
            continue
        low = s.lower()
        if re.search(r"\btstart\b", low):
            flags.add("TSTART")
        if re.search(r"\btcommit\b", low):
            flags.add("TCOMMIT")
        if re.search(r"\btrollback\b", low):
            flags.add("TROLLBACK")
        if "%nolock" in low:
            flags.add("%NOLOCK")
        if "%nocheck" in low:
            flags.add("%NOCHECK")
        if "$increment" in low or "$i(" in low:
            flags.add("$INCREMENT")
        if "$tlevel" in low:
            flags.add("$TLEVEL")
        if re.search(r"\$zcrc\b", low):
            flags.add("$ZCRC")
        if "$system.obj.compile" in low or "%system.obj" in low:
            flags.add("COMPILE")
        if re.search(r"\bjob\b", low):
            flags.add("JOB")
        if "isolationmode" in low or "setisolationmode" in low:
            flags.add("ISOLATION")
        # LOCK
        for lm in re.finditer(r"\b(?:lock|l)\s+([+-]?)\s*\(?\s*(\^[\w.%|]+)", s, re.I):
            lk.add(("+" if lm.group(1) != "-" else "-") + lm.group(2))
            if lm.group(1) == "":
                flags.add("LOCK-NO-SIGN")
        if re.search(r"\block\b[^\n]*:\s*[\w.$()]+", s, re.I):
            flags.add("LOCK-TIMEOUT")
        for gm in re.finditer(r"(\^\|\|[\w.%]+|\^[A-Za-z%][\w.%]*)", s):
            g = gm.group(1)
            before = s[:gm.start()].lower()
            if re.search(r"\b(?:kill|k|zkill|zk)\b[^;]*$", before) and not re.search(r"\$\w*\($", before):
                k.add(g)
            elif re.search(r"\$i(?:ncrement)?\($", before):
                w.add(g)
            elif re.search(r"\b(?:lock|l)\b", before):
                pass
            elif re.search(r"\b(?:set|s)\b", before) and re.match(r"\s*(\([^=]*\))?\s*=", s[gm.end():] + " ") is not None:
                w.add(g)
            elif re.search(r"\b(?:set|s)\b[^=]*$", before) and "=" in s[gm.end():] and not re.search(r"\$\w+\($", before):
                # Set ^G(sub) = v  (subscript may contain parentheses)
                rest = s[gm.end():]
                depth, idx = 0, 0
                for idx, ch in enumerate(rest):
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                    elif ch == "=" and depth == 0:
                        break
                    elif ch == "," and depth == 0:
                        break
                if idx < len(rest) and rest[idx] == "=":
                    w.add(g)
                else:
                    r.add(g)
            elif re.search(r"\bmerge\b[^=]*$", before):
                w.add(g)
            else:
                r.add(g)
    sqlw, sqlr = sql_hints(body)
    return {"globals_written": sorted(w), "globals_killed": sorted(k), "globals_read": sorted(r - w - k),
            "locks": sorted(lk), "tables_written": sorted(sqlw), "tables_read": sorted(sqlr), "flags": sorted(flags)}


SQL_W = re.compile(r"\b(?:INSERT\s+(?:OR\s+UPDATE\s+)?INTO|UPDATE|DELETE\s+FROM|DELETE|TRUNCATE\s+TABLE)\s+(%?[\w.\"{}]+)", re.I)
SQL_R = re.compile(r"\b(?:FROM|JOIN)\s+(%?[\w.\"{}]+)", re.I)
SQL_SKIP = {"select", "where", "the", "a", "an", "each", "this", "it", "set", "and", "or", "of", "to", "with", "one",
            "every", "its", "their", "any", "in", "on", "is", "be", "that", "which", "those", "there", "here", "",
            "values", "table", "rows", "row", "(", "?", "%table", "user", "s", "sql", "python", "iris", "json",
            "objectscript", "graph", "native", "caller", "process", "now", "then", "now,", "dual"}


KNOWN_TABLES = {"code_crosswalk", "docs", "embedding_quarantine", "embedding_registry", "fhir_bridges",
                "kg_EdgeEmbeddings", "kg_NodeEmbeddings", "kg_NodeEmbeddings_optimized", "ledger_revisions",
                "ledger_stats", "nodes", "rdf_edges", "rdf_labels", "rdf_namespaces", "rdf_props",
                "rdf_reifications", "relationship_mappings", "table_mappings", "LedgerRevision", "LedgerStats",
                "kg_TXT", "kg_RRF_FUSE", "kg_KNN_VEC", "kg_BM25"}
KNOWN_LOWER = {t.lower(): t for t in KNOWN_TABLES}


def norm_table(t: str) -> str:
    t = t.strip('"').replace('"', "")
    t = re.sub(r"\{[^}]*\}\.?", "", t)
    if "." in t:
        t = t.split(".")[-1]
    return t


def sql_hints(body: str):
    w, r = set(), set()
    for m in SQL_W.finditer(body):
        t = norm_table(m.group(1))
        if t.lower() in KNOWN_LOWER:
            t = KNOWN_LOWER[t.lower()]
            if re.match(r"(?i)update", m.group(0)) and not re.search(r"(?i)\bSET\b", body[m.end():m.end() + 400]):
                continue
            w.add(t)
    for m in SQL_R.finditer(body):
        t = norm_table(m.group(1))
        if t.lower() in KNOWN_LOWER:
            r.add(KNOWN_LOWER[t.lower()])
    return w, r - w


def py_hints(body: str):
    sqlw, sqlr = sql_hints(body)
    flags = set()
    if re.search(r"write_txn|_write_txn|begin_txn", body):
        flags.add("write_txn")
    if re.search(r"\.commit\(\)", body):
        flags.add("commit()")
    if re.search(r"\.rollback\(\)", body):
        flags.add("rollback()")
    if "%NOLOCK" in body.upper():
        flags.add("%NOLOCK")
    if re.search(r"TSTART|START TRANSACTION", body, re.I):
        flags.add("TSTART")
    globals_ = set(re.findall(r"\"(\^[\w.%]+)\"", body)) | set(re.findall(r"gref\(\s*[\"'](\^?[\w.%]+)", body))
    calls = set()
    for m in re.finditer(r"[\"']((?:Graph\.KG|IVG|%SYSTEM|%SYS)[\w.%]*)[\"']\s*,\s*[\"'](%?\w+)[\"']", body):
        calls.add(m.group(1) + "." + m.group(2))
    return {"tables_written": sorted(sqlw), "tables_read": sorted(sqlr), "globals_named": sorted(globals_),
            "classmethod_calls": sorted(calls), "flags": sorted(flags)}


# ---------------------------------------------------------------- whole-tree indexes
def all_classes():
    idx = {}
    for p in sorted(CLS_ROOT.rglob("*.cls")):
        cname, ext, methods = parse_cls(p)
        if cname:
            idx[cname] = {"path": str(p.relative_to(REPO)), "extends": ext, "methods": {m["name"]: m for m in methods}}
    return idx


def cls_callees(cname, m, classes):
    out = set()
    for cm in re.finditer(r"##class\(([\w.%]+)\)\.(%?\w+)\(", m["body"]):
        out.add((cm.group(1), cm.group(2)))
    for cm in re.finditer(r"(?<![\w.])\.\.(%?\w+)\(", m["body"]):
        out.add((cname, cm.group(1)))
    for cm in re.finditer(r"\$ClassMethod\(\s*\"([\w.%]+)\"\s*,\s*\"(%?\w+)\"", m["body"]):
        out.add((cm.group(1), cm.group(2)))
    return {(c, n) for c, n in out if c in classes and n in classes[c]["methods"]}


def cls_closure(cname, mname, classes, limit=400):
    seen = set()
    stack = [(cname, mname)]
    while stack and len(seen) < limit:
        c, n = stack.pop()
        if (c, n) in seen:
            continue
        seen.add((c, n))
        stack.extend(cls_callees(c, classes[c]["methods"][n], classes) - seen)
    return seen


def merge_hints(hs):
    out = {}
    for h in hs:
        for k, v in h.items():
            out.setdefault(k, set()).update(v)
    return {k: sorted(v) for k, v in out.items()}


def py_defs(path: Path):
    src = path.read_text(errors="replace")
    tree = ast.parse(src)
    lines = src.splitlines()
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            out.append({"cls": None, "name": node.name, "start": node.lineno, "end": node.end_lineno,
                        "body": "\n".join(lines[node.lineno - 1:node.end_lineno])})
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append({"cls": node.name, "name": sub.name, "start": sub.lineno, "end": sub.end_lineno,
                                "body": "\n".join(lines[sub.lineno - 1:sub.end_lineno]),
                                "decorators": [ast.unparse(d) for d in sub.decorator_list]})
    return out


def engine_methods():
    files = [REPO / "iris_vector_graph" / "engine.py"] + sorted((REPO / "iris_vector_graph" / "_engine").glob("*.py"))
    out = {}
    for f in files:
        for d in py_defs(f):
            if d["cls"] and (d["cls"] == "IRISGraphEngine" or d["cls"].endswith("Mixin")):
                d["path"] = str(f.relative_to(REPO))
                out.setdefault(d["name"], d)
    return out


def py_closure(name, emethods, limit=200):
    seen = set()
    stack = [name]
    while stack and len(seen) < limit:
        n = stack.pop()
        if n in seen or n not in emethods:
            continue
        seen.add(n)
        for cm in re.finditer(r"self\.(\w+)\(", emethods[n]["body"]):
            if cm.group(1) not in seen:
                stack.append(cm.group(1))
    return seen


# ---------------------------------------------------------------- ontology
def parse_ontology(path: Path):
    stmts, cells, entities = [], [], {}
    section = None
    for ln in path.read_text().splitlines():
        if ln.startswith("## "):
            section = ln[3:].strip()
            continue
        if section == "Cells" and ln.startswith("Entity "):
            m = re.match(r"Entity (.+?): states (.+?); commands (.+)$", ln)
            if m:
                entities[m.group(1)] = {"states": [s.strip() for s in m.group(2).split(",")],
                                        "commands": [c.strip() for c in m.group(3).split(",")]}
        if not ln.startswith("| ") or ln.startswith("|---") or ln.startswith("| Id ") or ln.startswith("| Entity |"):
            continue
        cols = [c.strip() for c in re.split(r"(?<!\\)\|", ln)[1:-1]]
        if section == "Statements" and len(cols) >= 7:
            stmts.append(dict(zip(["id", "parent", "kind", "statement", "evidence", "source", "notes"], cols[:7])))
        if section == "Cells" and len(cols) >= 6:
            cells.append(dict(zip(["entity", "state", "command", "outcome", "statements", "decision"], cols[:6])))
    return stmts, cells, entities


CITE = re.compile(r"((?:iris_src|iris_vector_graph|api|scripts|sql|src)/[\w./-]+?\.(?:cls|py|sql|mac|inc)):(\d+)(?:-(\d+))?")


def covering(stmts, ep):
    path, start, end = ep["path"], ep["start"], ep["end"]
    names = ep["names"]
    hits = []
    for s in stmts:
        text = " ".join([s["evidence"], s["source"], s["notes"], s["statement"]])
        hit = False
        for m in CITE.finditer(text):
            if m.group(1) == path:
                a = int(m.group(2))
                b = int(m.group(3) or a)
                if a <= end and b >= start:
                    hit = True
                    break
        if not hit:
            for n in names:
                if re.search(r"(?<![\w.])" + re.escape(n) + r"(?!\w)", text):
                    hit = True
                    break
        if hit:
            hits.append(s["id"])
    return hits


# ---------------------------------------------------------------- main
def inventory(mod: str):
    scope = json.loads((HERE / "scope" / f"{mod}.json").read_text())
    onto = next(ONTO.glob(f"{mod}-*.md"))
    stmts, cells, entities = parse_ontology(onto)
    classes = all_classes()
    emeth = engine_methods()
    eps = []

    def add(ep):
        eps.append(ep)

    # ObjectScript classes: all public methods, or those matching a regex
    for cname, rx in scope.get("cls", {}).items():
        c = classes[cname]
        is_task = "%SYS.Task.Definition" in c["extends"]
        for m in c["methods"].values():
            if not is_public_cls(m) or not re.search(rx, m["name"]):
                continue
            clos = cls_closure(cname, m["name"], classes)
            h = merge_hints([cls_hints(classes[cc]["methods"][nn]["body"]) for cc, nn in clos])
            kind = "task" if (is_task and m["name"] in ("OnTask",)) else "cls"
            sqlname = re.search(r"SqlName\s*=\s*(\w+)", m["keywords"])
            add({"id": f"{kind}:{cname}.{m['name']}", "kind": kind, "path": c["path"], "start": m["start"],
                 "end": m["end"], "sqlproc": "SqlProc" in m["keywords"],
                 "sqlname": sqlname.group(1) if sqlname else None,
                 "names": [f"{cname}.{m['name']}", f"{cname.split('.')[-1]}.{m['name']}", f"{cname.split('.')[-1]}::{m['name']}"]
                 + ([sqlname.group(1)] if sqlname else []),
                 "callees": sorted(f"{a}.{b}" for a, b in clos if (a, b) != (cname, m["name"])), "hint": h})
    # Python files
    for rel, rx in scope.get("py", {}).items():
        p = REPO / rel
        for d in py_defs(p):
            if d["cls"] and d["cls"].startswith("_"):
                continue
            if d["name"].startswith("_") and d["name"] not in ("__init__", "__call__", "__enter__", "__exit__"):
                continue
            q = f"{d['cls']}.{d['name']}" if d["cls"] else d["name"]
            if not re.search(rx, q):
                continue
            h = py_hints(d["body"])
            add({"id": f"py:{rel}:{q}", "kind": "py", "path": rel, "start": d["start"], "end": d["end"],
                 "names": [q, d["name"]] if d["name"] not in ("__init__", "search", "run", "fuse") else [q], "hint": h})
    # engine methods
    for rel, rx in scope.get("engine", {}).items():
        for name, d in sorted(emeth.items()):
            if d["path"] != rel or name.startswith("_") or not re.search(rx, name):
                continue
            clos = py_closure(name, emeth)
            hs = [py_hints(emeth[n]["body"]) for n in clos]
            h = merge_hints(hs)
            # follow classmethod calls into ObjectScript
            cl = []
            for cm in h.get("classmethod_calls", []):
                c, _, n = cm.rpartition(".")
                if c in classes and n in classes[c]["methods"]:
                    for cc, nn in cls_closure(c, n, classes):
                        cl.append(cls_hints(classes[cc]["methods"][nn]["body"]))
            if cl:
                h = merge_hints([h] + cl)
            add({"id": f"eng:IRISGraphEngine.{name}", "kind": "engine", "path": rel, "start": d["start"],
                 "end": d["end"], "names": [f"engine.{name}", name, f"IRISGraphEngine.{name}"],
                 "self_calls": sorted(clos - {name}), "hint": h})
    # REST routes
    rrx = scope.get("routes")
    if rrx:
        for p in sorted(CLS_ROOT.rglob("*.cls")):
            txt = p.read_text(errors="replace")
            for i, ln in enumerate(txt.splitlines(), 1):
                m = re.search(r'<Route Url="([^"]+)" Method="(\w+)" Call="([\w.:]+)"', ln)
                if m and re.search(rrx, m.group(1) + " " + m.group(3)):
                    add({"id": f"route:{m.group(2)} {m.group(1)}", "kind": "route", "path": str(p.relative_to(REPO)),
                         "start": i, "end": i, "names": [m.group(1), m.group(3)], "hint": {}})
    # Cypher procedures
    crx = scope.get("cypher")
    if crx:
        eng = (REPO / "iris_vector_graph" / "engine.py").read_text().splitlines()
        tr = (REPO / "iris_vector_graph" / "cypher" / "translator.py").read_text().splitlines()
        seen = set()
        for src, rel in ((eng, "iris_vector_graph/engine.py"), (tr, "iris_vector_graph/cypher/translator.py")):
            for i, ln in enumerate(src, 1):
                for m in re.finditer(r"[\"']((?:ivg|db|dbms|apoc|gds)\.[A-Za-z][\w.]*)[\"']", ln):
                    nm = m.group(1).lower()
                    if nm in seen or not re.search(crx, nm) or nm.endswith("."):
                        continue
                    seen.add(nm)
                    add({"id": f"cypher:{nm}", "kind": "cypher-proc", "path": rel, "start": i, "end": i,
                         "names": [m.group(1), nm], "hint": {}})
    # CLI
    clirx = scope.get("cli")
    if clirx:
        lines = (REPO / "iris_vector_graph" / "cli.py").read_text().splitlines()
        for i, ln in enumerate(lines, 1):
            m = re.search(r"@(\w+)\.command\(\s*(?:\"([\w-]+)\")?", ln)
            if m:
                fn = re.search(r"def (\w+)", lines[i] if i < len(lines) else "")
                j = i
                while not fn and j < len(lines) - 1 and j - i < 40:
                    j += 1
                    fn = re.search(r"^\s*def (\w+)", lines[j])
                name = (m.group(2) or (fn.group(1) if fn else "?"))
                full = f"{m.group(1)} {name}" if m.group(1) != "cli" else name
                if re.search(clirx, full):
                    add({"id": f"cli:ivg {full}", "kind": "cli", "path": "iris_vector_graph/cli.py", "start": i,
                         "end": i, "names": [f"ivg {full}"], "hint": {}})
    # generated SQL procedures/functions
    srx = scope.get("sqlfn")
    if srx:
        lines = (REPO / "iris_vector_graph" / "schema.py").read_text().splitlines()
        for i, ln in enumerate(lines, 1):
            m = re.search(r"CREATE (?:OR REPLACE )?(PROCEDURE|FUNCTION)\s+(?:\{?[\w]*\}?\.)?(\w+)", ln)
            if m and re.search(srx, m.group(2)):
                add({"id": f"sqlfn:{m.group(2)}", "kind": "sql-" + m.group(1).lower(), "path": "iris_vector_graph/schema.py",
                     "start": i, "end": i, "names": [m.group(2)], "hint": sql_hints(ln) and {}})
    # extra hand-named entry points (other surfaces, each with a citation)
    for x in scope.get("extra", []):
        add({**x, "hint": x.get("hint", {})})

    # coverage
    for ep in eps:
        ep["covered_by"] = covering(stmts, ep)
    omissions = [ep["id"] for ep in eps if not ep["covered_by"]]
    cmap = scope.get("cell_map", {})
    cell_rows = []
    for c in cells:
        key = f"{c['entity']}|{c['command']}"
        mapped = cmap.get(key, cmap.get(c["command"], []))
        unknown = [m for m in mapped if m not in {e["id"] for e in eps}]
        cell_rows.append({**c, "entry_points": mapped, "unknown_entry_points": unknown})
    cells_without = sorted({f"{c['entity']}|{c['command']}" for c in cell_rows if not c["entry_points"]})
    # entry points that no cell names (informational)
    in_cells = {e for c in cell_rows for e in c["entry_points"]}
    out = {
        "module": mod, "ontology": str(onto.relative_to(REPO)), "scope_file": str((HERE / "scope" / f"{mod}.json").relative_to(REPO)),
        "generated_by": "experiment/playbook-completion/models/breadth-b/tools/inventory.py",
        "counts": {"entry_points": len(eps), "by_kind": {k: sum(1 for e in eps if e["kind"] == k) for k in sorted({e["kind"] for e in eps})},
                   "statements": len(stmts), "cells": len(cells), "omissions": len(omissions),
                   "cells_without_entry_point": len(cells_without)},
        "entities": entities,
        "omissions": omissions,
        "cells_without_entry_point": cells_without,
        "entry_points_in_no_cell": sorted(e["id"] for e in eps if e["id"] not in in_cells),
        "entry_points": [{k: v for k, v in ep.items() if k != "names"} for ep in eps],
        "cells": cell_rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{mod}.json").write_text(json.dumps(out, indent=1, sort_keys=False) + "\n")
    print(f"{mod}: {len(eps)} entry points {out['counts']['by_kind']}, {len(omissions)} uncovered, "
          f"{len(cells)} cells, {len(cells_without)} cell commands without entry point")


if __name__ == "__main__":
    for m in sys.argv[1:]:
        inventory(m)
