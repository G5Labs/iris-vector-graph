#!/usr/bin/env python3
"""Entry-point inventory of modules 01-06, derived mechanically from source at the pin (playbook §3.1 cells, §3.4).

    python experiment/playbook-completion/models/breadth-a/tools/inventory.py [--out DIR]

For each module (file assignment in modules.py, transcribed from the ontology's Scope line):
  - entry points: python-api (public functions/methods; IRISGraphEngine mixin methods as IRISGraphEngine.<m>),
    exported (__all__ names that land in the module's files), classmethod / sqlproc (ObjectScript members, SqlProc),
    sqlproc (SQL routines created by setup's DDL strings), sqlfile-object (objects the shipped sql/ files create),
    rest (FastAPI routes and %CSP.REST UrlMap routes whose handler reaches the module), cli (click commands that reach
    it, through the HTTP route they call or directly), task (%SYS.Task.Definition), native (ObjectScript members
    called from Python over the Native API; functional-index callbacks run by the SQL filer), lifecycle (a tag on
    install/upgrade/migrate/erase/rebuild/sync/backfill/purge/remove entries).
  - reconciliation with the module's ontology: an entry point is covered when a statement or a cell of the module
    names it, or cites its file with a line range overlapping its definition; uncovered public entry points are
    omissions. Each cell lists its statements and the entry points they cover; a cell whose statements cover none is
    listed in cells_without_entry_point.
Output: <out>/NN.json (default models/breadth-a/inventory) and <out>/unassigned.json.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import srcindex as S  # noqa: E402
from modules import MODULE_FILES, NAMES, ONTOLOGY, routine_owner  # noqa: E402

REPO = S.REPO
HERE = Path(__file__).resolve().parent
LIFECYCLE = re.compile(r"^(initialize_schema|setup_tables|upgrade|migrate|run|apply|remove_legacy|erase|rebuild|sync|"
                       r"backfill|purge|drop|deploy|bootstrap|stage_class_owned|restore_rescued|ensure_|tighten|add_graph|"
                       r"update_spo|tune_tables|repair|Purge|Erase|Remove|Build|Rebuild|Backfill|Drop|Migrate|Upgrade|"
                       r"Install|Deploy|BeginRebuild|EndRebuild|Clear|clear_done|reconcile|adopt|place_quarantined|"
                       r"ivf_build|vec_build|plaid_build|ivf_drop|vec_drop|plaid_drop|create_index)", re.I)


# ------------------------------------------------------------------------------------------------------------------
# selection
# ------------------------------------------------------------------------------------------------------------------
def _selected(spec, fn: S.PyFunc) -> Tuple[bool, Optional[str]]:
    qual = fn.qual
    cls_star = (fn.cls + ".*") if fn.cls else None
    if spec == "*":
        return True, None
    inc = spec.get("include")
    exc = spec.get("exclude", {})
    if fn.name in exc or qual in exc:
        return False, exc.get(fn.name) or exc.get(qual)
    if inc is None:
        return True, None
    if "*" in inc or fn.name in inc or qual in inc or (cls_star and cls_star in inc):
        return True, spec.get("reason")
    return False, None


def py_entry_id(fn: S.PyFunc) -> str:
    mod = fn.file[:-3].replace("/", ".")
    if fn.cls and fn.cls.endswith("Mixin"):
        return "py:IRISGraphEngine." + fn.name
    if fn.cls:
        return f"py:{mod}.{fn.cls}.{fn.name}"
    return f"py:{mod}.{fn.name}"


def module_py_entries(py: S.PyIndex, mod: str, exported: Dict[str, str]) -> Tuple[List[dict], List[dict]]:
    out, excluded = [], []
    spec_files = MODULE_FILES[mod]["py"]
    for rel, spec in spec_files.items():
        if rel not in py.by_file:
            continue
        for fn in py.by_file[rel]:
            if fn.nested:
                continue
            ok, reason = _selected(spec, fn)
            if not ok:
                if reason:
                    excluded.append({"name": fn.qual, "source": fn.src, "reason": reason})
                continue
            explicit = spec != "*" and (fn.name in spec.get("include", []) or fn.qual in spec.get("include", []))
            private = fn.name.startswith("_") and not fn.name.startswith("__")
            dunder = fn.name.startswith("__")
            cls_private = bool(fn.cls) and fn.cls.startswith("_") and not explicit and not (
                spec != "*" and (fn.cls + ".*") in spec.get("include", []))
            if dunder and not (fn.name == "__init__" and fn.cls and not fn.cls.startswith("_")
                               and not fn.cls.endswith("Mixin") and fn.cls != "IRISGraphEngine"):
                continue
            if (private or cls_private) and not explicit:
                continue
            kinds = ["python-api"] if not private else ["internal"]
            if dunder:
                kinds = ["python-api(constructor)"]
                private = False
            if fn.is_property:
                kinds = ["python-api(property)"] if not private else ["internal"]
            if LIFECYCLE.match(fn.name):
                kinds.append("lifecycle")
            e = {"id": py_entry_id(fn), "kind": kinds[0], "kinds": kinds, "name": fn.name, "qual": fn.qual,
                 "source": fn.src, "file": fn.file, "start": fn.start, "end": fn.end,
                 "public": not private and not cls_private, "module": mod}
            if spec != "*" and spec.get("reason") and explicit:
                e["assignment_reason"] = spec["reason"]
            out.append(e)
    # exported names landing in the module's files
    for name, rel in exported.items():
        if rel in spec_files:
            spec = spec_files[rel]
            if spec != "*" and name not in spec.get("include", []) and "*" not in spec.get("include", []) and spec.get("include") is not None:
                continue
            if spec != "*" and name in spec.get("exclude", {}):
                continue
            cls = py.classes.get(name)
            fnk = next((k for k, f in py.funcs.items() if f.file == rel and f.qual == name), None)
            if cls and cls["file"] == rel:
                src = f"{rel}:{cls['start']}-{cls['end']}"
                start, end = cls["start"], cls["end"]
            elif fnk:
                f = py.funcs[fnk]
                src, start, end = f.src, f.start, f.end
            else:
                src, start, end = rel, 0, 0
            out.append({"id": "export:" + name, "kind": "exported", "kinds": ["exported"], "name": name, "qual": name,
                        "source": src, "file": rel, "start": start, "end": end, "public": True, "module": mod})
    return out, excluded


def exported_names(py: S.PyIndex) -> Dict[str, str]:
    init = REPO / "iris_vector_graph/__init__.py"
    tree = ast.parse(init.read_text())
    allnames: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            allnames = [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
    src: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            base = node.module
            if node.level:
                base = "iris_vector_graph" + ("." + node.module if node.module else "")
            path = base.replace(".", "/")
            cand = [path + ".py", path + "/__init__.py"]
            rel = next((c for c in cand if (REPO / c).exists()), None)
            for a in node.names:
                if rel:
                    src[a.asname or a.name] = rel
    return {n: src[n] for n in allnames if n in src}


def module_cls_entries(cl: S.ClsIndex, py: S.PyIndex, mod: str, native_sites: Dict[str, List[str]]) -> List[dict]:
    out = []
    for rel in MODULE_FILES[mod].get("cls", []):
        cname = next((c for c, v in cl.classes.items() if v["file"] == rel), None)
        if not cname:
            continue
        ext = cl.classes[cname]["extends"]
        for mname in cl.classes[cname]["methods"]:
            m = cl.methods[f"{cname}.{mname}"]
            kinds = []
            if any("FunctionalIndex" in x for x in ext) and mname.endswith("Index"):
                kinds.append("native(functional-index-callback)")
            elif any("Task.Definition" in x for x in ext) and mname == "OnTask":
                kinds.append("task")
            elif m.sqlproc:
                kinds.append("sqlproc")
            else:
                kinds.append("classmethod" if m.kind == "ClassMethod" else m.kind.lower())
            key = f"{cname}.{mname}"
            if key in native_sites:
                kinds.append("native")
            if LIFECYCLE.match(mname):
                kinds.append("lifecycle")
            e = {"id": "cls:" + key, "kind": kinds[0], "kinds": kinds, "name": mname, "qual": key, "class": cname,
                 "source": m.src, "file": rel, "start": m.start, "end": m.end,
                 "public": not m.private and "ServerOnly" not in m.keywords or kinds[0].startswith("native"),
                 "private": m.private, "module": mod, "keywords": m.keywords, "language": m.language}
            if m.sqlproc:
                e["sqlname"] = m.sqlname or cname.replace(".", "_") + "_" + mname
            if key in native_sites:
                e["native_callers"] = sorted(set(native_sites[key]))[:25]
                e["native_caller_count"] = len(set(native_sites[key]))
            out.append(e)
    # cls classes of another module that this module's Scope cites as called by its commands
    for key in MODULE_FILES[mod].get("cited_cls", []):
        m = cl.methods.get(key)
        if m:
            out.append({"id": "cls:" + key, "kind": "classmethod(cited)", "kinds": ["classmethod(cited)"], "name": m.name,
                        "qual": key, "class": m.cls, "source": m.src, "file": m.file, "start": m.start, "end": m.end,
                        "public": True, "module": mod, "owner_note": "owned by another module; the Scope cites it where this module's commands call it"})
    return out


def native_call_sites(py: S.PyIndex) -> Dict[str, List[str]]:
    sites: Dict[str, List[str]] = defaultdict(list)
    for f in py.funcs.values():
        for c in f.calls:
            if c[0] == "cls":
                sites[f"{c[1]}.{c[2]}"].append(f"{f.file}:{c[3]} ({f.qual})")
    return sites


DDL_ROUTINE = re.compile(r"CREATE\s+OR\s+REPLACE\s+(FUNCTION|PROCEDURE)\s+(?:\{table_schema\}|Graph_KG)\.(\w+)")


def ddl_routines() -> List[dict]:
    rel = "iris_vector_graph/schema.py"
    out = []
    for i, line in enumerate((REPO / rel).read_text().split("\n"), 1):
        for m in DDL_ROUTINE.finditer(line):
            out.append({"name": m.group(2), "type": m.group(1).lower(), "line": i})
    return out


SQL_CREATE = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?(TABLE|PROCEDURE|FUNCTION|VIEW|INDEX|UNIQUE\s+INDEX)\s+"
                        r"(?:IF\s+NOT\s+EXISTS\s+)?([\w.\"]+)", re.I)


def sql_file_objects() -> List[dict]:
    loaders = defaultdict(list)
    for p in list((REPO / "scripts").rglob("*.py")) + list((REPO / "iris_vector_graph").rglob("*.py")):
        try:
            text = p.read_text()
        except UnicodeDecodeError:
            continue
        for m in re.finditer(r"sql/([\w/]+\.sql)", text):
            ln = text[:m.start()].count("\n") + 1
            loaders["sql/" + m.group(1)].append(f"{p.relative_to(REPO)}:{ln}")
    out = []
    for p in sorted((REPO / "sql").rglob("*.sql")):
        rel = str(p.relative_to(REPO))
        lines = p.read_text(errors="replace").split("\n")
        for i, line in enumerate(lines, 1):
            m = SQL_CREATE.search(line)
            if m:
                obj = m.group(2).replace('"', "")
                out.append({"file": rel, "line": i, "type": m.group(1).upper(), "object": obj,
                            "qualified": "." in obj, "loaders": sorted(set(loaders.get(rel, [])))})
    return out


# ------------------------------------------------------------------------------------------------------------------
# REST and CLI
# ------------------------------------------------------------------------------------------------------------------
def rest_routes(py: S.PyIndex, cl: S.ClsIndex) -> List[dict]:
    routes = []
    for rel in ("iris_vector_graph/cypher_api.py", "api/main.py", "api/routers/cypher.py", "api/routers/fhir_event.py"):
        if rel not in py.by_file:
            continue
        funcs = {f.qual: f for f in py.by_file[rel]}
        for f in py.by_file[rel]:
            for d in f.decorators:
                m = re.match(r"(?:app|router)\.(get|post|put|delete|patch|websocket)\((['\"])([^'\"]*)\2", d)
                if not m:
                    continue
                called = set()
                for c in f.calls:
                    if c[0] in ("engine", "attr") and len(c) >= 3:
                        called.add(c[-2])
                    elif c[0] == "name" and c[1] in funcs:
                        for c2 in funcs[c[1]].calls:
                            if c2[0] in ("engine", "attr") and len(c2) >= 3:
                                called.add(c2[-2])
                routes.append({"route": f"{m.group(1).upper()} {m.group(3)}", "handler": f"{rel}:{f.start}-{f.end}",
                               "function": f.qual, "calls": sorted(called)})
    # %CSP.REST UrlMap
    for cname, info in cl.classes.items():
        text = (REPO / info["file"]).read_text(errors="replace")
        if "XData UrlMap" not in text:
            continue
        for m in re.finditer(r'<Route\s+Url="([^"]+)"\s+Method="(\w+)"\s+Call="(\w+)"', text):
            meth = cl.methods.get(f"{cname}.{m.group(3)}")
            # follow ObjectScript calls three hops (Service -> PyOps -> the module's classes)
            calls, frontier = set(), [f"{cname}.{m.group(3)}"]
            for _ in range(3):
                nxt = []
                for k in frontier:
                    mm = cl.methods.get(k)
                    for a2, b2, _l in (mm.calls if mm else []):
                        key2 = f"{a2}.{b2}"
                        if key2 not in calls:
                            calls.add(key2)
                            nxt.append(key2)
                frontier = nxt
            sqltext = " ".join(s for k in calls | {f"{cname}.{m.group(3)}"} for _, s in (cl.methods[k].sql if k in cl.methods else []))
            calls = sorted(calls)
            routes.append({"route": f"{m.group(2)} {m.group(1)}", "handler": meth.src if meth else info["file"],
                           "function": f"{cname}.{m.group(3)}", "calls": calls, "csp": True,
                           "sql_tables": sorted(set(re.findall(r"Graph_KG\.(\w+)", sqltext)))})
    return routes


def cli_commands(py: S.PyIndex) -> List[dict]:
    rel = "iris_vector_graph/cli.py"
    out = []
    text = (REPO / rel).read_text().split("\n")
    sdk_urls: Dict[str, str] = {}
    for f in py.by_file.get("iris_vector_graph/sdk.py", []):
        body = "\n".join((REPO / f.file).read_text().split("\n")[f.start - 1:f.end])
        m = re.search(r"['\"}](/(?:api|admin|db|schema|server|stats|health|indexes)[\w/{}.-]*)['\"]", body)
        if m:
            sdk_urls[f.name] = m.group(1)
    for f in py.by_file.get(rel, []):
        if not any(".command(" in d or d.endswith(".command()") or ".group(" in d for d in f.decorators):
            continue
        cmd = next((re.search(r"command\((['\"])([^'\"]+)\1", d) for d in f.decorators if "command(" in d), None)
        grp = next((d.split(".")[0] for d in f.decorators if ".command(" in d or ".group(" in d), "cli")
        if any(".group(" in d for d in f.decorators):
            continue
        body = "\n".join(text[f.start - 1:f.end])
        urls = sorted(set(re.findall(r"(/(?:api|admin|db|schema|server|stats|health|indexes)[\w/{}.-]*)", body)))
        calls = sorted({c[-2] for c in f.calls if c[0] in ("attr", "engine") and len(c) >= 3})
        for c in calls:
            if c in sdk_urls:
                urls.append(sdk_urls[c])
        cname = cmd.group(2) if cmd else f.name.replace("_", "-")
        out.append({"command": (cname if grp == "cli" else f"{grp} {cname}"), "function": f.qual, "source": f.src,
                    "urls": sorted(set(urls)), "calls": calls})
    return out


# ------------------------------------------------------------------------------------------------------------------
# ontology reconciliation
# ------------------------------------------------------------------------------------------------------------------
CITE = re.compile(r"([\w./-]*[\w-]+\.(?:py|cls|sql)):(\d+)(?:-(\d+))?((?:\s*,\s*\d+(?:-\d+)?(?![\w.]))*)")


def _resolve(path: str, basenames: Dict[str, List[str]]) -> Optional[str]:
    if (REPO / path).exists():
        return path
    for pre in ("iris_vector_graph/", "iris_src/src/Graph/KG/", "iris_vector_graph/_engine/"):
        if (REPO / (pre + path)).exists():
            return pre + path
    cands = basenames.get(Path(path).name, [])
    if len(cands) == 1:
        return cands[0]
    pref = [c for c in cands if c.startswith(("iris_vector_graph/", "iris_src/"))]
    return pref[0] if len(pref) == 1 else None


def parse_ontology(rel: str, basenames) -> Tuple[List[dict], List[dict]]:
    lines = (REPO / rel).read_text().split("\n")
    stmts, cells = [], []
    section = None
    for i, line in enumerate(lines, 1):
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if section and section.startswith("statements") and re.match(r"^[A-Z]{3}-", cols[0]):
            text = " | ".join(cols)
            cites = []
            for m in CITE.finditer(text):
                path = _resolve(m.group(1), basenames)
                if not path:
                    continue
                a = int(m.group(2))
                b = int(m.group(3) or a)
                cites.append((path, a, b))
                for extra in re.findall(r"(\d+)(?:-(\d+))?", m.group(4) or ""):
                    x = int(extra[0])
                    cites.append((path, x, int(extra[1] or x)))
            stmts.append({"id": cols[0], "kind": cols[2] if len(cols) > 2 else "", "line": i, "text": text,
                          "cites": cites})
        elif section and section.startswith("cells") and len(cols) >= 5 and cols[0] not in ("Entity",):
            cells.append({"entity": cols[0], "state": cols[1], "command": cols[2], "outcome": cols[3],
                          "statements": [s.strip() for s in re.split(r"[,;]\s*", cols[4]) if s.strip()],
                          "decision": cols[5] if len(cols) > 5 else "", "line": i})
    return stmts, cells


COMMON = {"status", "index", "run", "apply", "get", "set", "put", "remove", "insert", "delete", "build", "search",
          "info", "drop", "count", "event", "latest", "call", "close", "first", "begin", "commit", "rollback", "native",
          "written", "level", "fail", "wrapper", "registered", "Put", "Remove", "Count", "Build", "Search", "Insert",
          "Delete", "Info", "Drop", "Set", "Get", "Clear", "Create", "Status", "Purge"}


def name_patterns(e: dict) -> List[re.Pattern]:
    n = e["name"]
    pats = []
    if e["id"].startswith("cls:"):
        cname = e["class"]
        short = cname.split(".")[-1]
        pats.append(re.compile(re.escape(f"{short}.{n}") + r"(?![\w])"))
        pats.append(re.compile(re.escape(f"{cname}.{n}") + r"(?![\w])"))
        if n not in COMMON and len(n) >= 6:
            pats.append(re.compile(r"(?<![\w.])" + re.escape(n) + r"(?=\s*\(|`)"))
            pats.append(re.compile(r"`" + re.escape(n) + r"`"))
    else:
        if n in COMMON or len(n) < 4:
            pats.append(re.compile(r"(?:\.|`)" + re.escape(n) + r"(?:\(|`)"))
        else:
            pats.append(re.compile(r"(?<![\w])" + re.escape(n) + r"(?![\w])"))
        if e.get("kind") == "rest":
            pats = [re.compile(re.escape(e["name"]))]
    return pats


def covers(stmt: dict, e: dict, pats) -> Optional[str]:
    for path, a, b in stmt["cites"]:
        if path == e.get("file") and e.get("start") and a <= e["end"] and b >= e["start"]:
            return f"cites {path}:{a}-{b}"
    for p in pats:
        if p.search(stmt["text"]):
            return "names " + e["name"]
    # a statement that cites code the entry point executes (its private helpers, the class methods it calls), within
    # three call hops; helpers with a fan-in above FANIN_CAP (validate_graph_name, _t, ledger_check...) do not count
    for path, a, b in stmt["cites"]:
        for (cpath, cs, ce, ckey) in e.get("_callee_spans", []):
            if cpath == path and a <= ce and b >= cs:
                return f"cites callee {ckey.split('::')[-1]} ({path}:{a}-{b})"
    return None


FANIN_CAP = 12


def line_owner(py: S.PyIndex, cl: S.ClsIndex, path: str, line: int) -> Optional[str]:
    """The innermost function or class method of `path` that contains `line`."""
    best = None
    if path.endswith(".py"):
        for f in py.by_file.get(path, []):
            if f.start <= line <= f.end and (best is None or f.start >= best[1]):
                best = (f"{path}::{f.qual}", f.start)
    elif path.endswith(".cls"):
        for k, m in cl.methods.items():
            if m.file == path and m.start <= line <= m.end:
                best = ("cls:" + k, m.start)
    return best[0] if best else None


def callee_spans(R: S.Resolver, key: str, fanin: Dict[str, int]) -> List[Tuple[str, int, int, str]]:
    out = []
    for k, (d, _via) in R.closure(key, 3).items():
        if d == 0 or fanin.get(k, 0) > FANIN_CAP:
            continue
        try:
            f, s, e = R.span(k)
        except KeyError:
            continue
        out.append((f, s, e, k))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE.parent / "inventory"))
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    py, cl = S.load()
    basenames: Dict[str, List[str]] = defaultdict(list)
    for f in S.python_files() + S.cls_files() + [str(p.relative_to(REPO)) for p in (REPO / "sql").rglob("*.sql")]:
        basenames[Path(f).name].append(f)
    exported = exported_names(py)
    nsites = native_call_sites(py)
    routines = ddl_routines()
    sqlobjs = sql_file_objects()
    routes = rest_routes(py, cl)
    clis = cli_commands(py)

    per_mod: Dict[str, List[dict]] = {}
    excluded_all: Dict[str, List[dict]] = {}
    for mod in sorted(MODULE_FILES):
        eps, excl = module_py_entries(py, mod, exported)
        eps += module_cls_entries(cl, py, mod, nsites)
        # SQL routines created by setup's DDL strings
        for r in routines:
            owner = routine_owner(r["name"])
            if mod == "01" or owner == mod:
                eps.append({"id": f"sqlroutine:Graph_KG.{r['name']}", "kind": "sqlproc", "kinds": ["sqlproc"],
                            "name": r["name"], "qual": r["name"], "source": f"iris_vector_graph/schema.py:{r['line']}",
                            "file": "iris_vector_graph/schema.py", "start": r["line"], "end": r["line"],
                            "public": True, "module": mod, "semantics_owner": owner,
                            "created_by": "GraphSchema.get_procedures_sql_list (setup)"})
        if mod == "01":
            for o in sqlobjs:
                eps.append({"id": f"sqlfile:{o['file']}:{o['object']}", "kind": "sqlfile-object",
                            "kinds": ["sqlfile-object", "lifecycle"], "name": o["object"], "qual": o["object"],
                            "source": f"{o['file']}:{o['line']}", "file": o["file"], "start": o["line"],
                            "end": o["line"], "public": True, "module": mod, "object_type": o["type"],
                            "schema_qualified": o["qualified"], "loaders": o["loaders"]})
        per_mod[mod] = eps
        excluded_all[mod] = excl

    # engine method -> module (for REST/CLI attribution)
    owner_of: Dict[str, str] = {}
    for mod, eps in per_mod.items():
        for e in eps:
            if e["id"].startswith("py:IRISGraphEngine.") or e["id"].startswith("py:iris_vector_graph.engine."):
                owner_of.setdefault(e["name"], mod)
            if e["id"].startswith("cls:"):
                owner_of.setdefault(e["qual"], mod)
    route_mod: Dict[str, List[str]] = {}
    for r in routes:
        mods = {owner_of[c] for c in r["calls"] if c in owner_of}
        # a %CSP.REST route whose SQL reaches the vector procedure or the registry is a VEC entry point
        if set(r.get("sql_tables", [])) & {"kg_KNN_VEC", "kg_NodeEmbeddings", "embedding_registry"}:
            mods.add("06")
        mods = sorted(mods)
        route_mod[r["route"].split(" ", 1)[1]] = mods
        for mod in mods:
            per_mod[mod].append({"id": f"rest:{r['route']}", "kind": "rest", "kinds": ["rest"], "name": r["route"],
                                 "qual": r["function"], "source": r["handler"], "file": r["handler"].split(":")[0],
                                 "start": int(r["handler"].split(":")[1].split("-")[0]) if ":" in r["handler"] else 0,
                                 "end": int(r["handler"].split("-")[-1]) if "-" in r["handler"] else 0,
                                 "public": True, "module": mod,
                                 "reaches": sorted(c for c in r["calls"] if owner_of.get(c) == mod) or r.get("sql_tables", [])})
    for c in clis:
        mods = set()
        for u in c["urls"]:
            mods.update(route_mod.get(u, []))
        for call in c["calls"]:
            if call in owner_of:
                mods.add(owner_of[call])
        for mod in sorted(mods):
            per_mod[mod].append({"id": f"cli:ivg {c['command']}", "kind": "cli", "kinds": ["cli"], "name": c["command"],
                                 "qual": c["function"], "source": c["source"], "file": c["source"].split(":")[0],
                                 "start": int(c["source"].split(":")[1].split("-")[0]),
                                 "end": int(c["source"].split("-")[-1]), "public": True, "module": mod,
                                 "via": c["urls"] or c["calls"]})

    R = S.Resolver(py, cl)
    fanin: Dict[str, int] = Counter()
    for k in list(py.funcs) + ["cls:" + m for m in cl.methods]:
        for c in {c for c, _ in R.callees(k)}:
            fanin[c] += 1
    for mod, eps in per_mod.items():
        for e in eps:
            key = None
            if e["id"].startswith("cls:"):
                key = e["id"]
            elif e["id"].startswith("py:") or e["id"].startswith("export:"):
                key = next((k for k, f in py.funcs.items() if f.file == e["file"] and f.qual == e["qual"]), None)
            if key:
                e["_key"] = key
                e["_callee_spans"] = callee_spans(R, key, fanin)

    all_stmts = {}
    for mod, rel in ONTOLOGY.items():
        all_stmts[mod] = parse_ontology(rel, basenames)

    unassigned = {"generated_by": "models/breadth-a/tools/inventory.py", "pin": S.PIN,
                  "excluded_by_scope": excluded_all,
                  "note": "members of lane-A files that the Scope lines give to another module or to none"}
    summary = {}
    for mod, eps in per_mod.items():
        stmts, cells = all_stmts[mod]
        seen = set()
        uniq = []
        for e in eps:
            if e["id"] in seen:
                continue
            seen.add(e["id"])
            pats = name_patterns(e)
            cov = []
            for s in stmts:
                why = covers(s, e, pats)
                if why:
                    cov.append({"statement": s["id"], "how": why})
            e["covered_by"] = cov[:12]
            e["_covered_ids"] = {c["statement"] for c in cov}
            e["covered_by_count"] = len(cov)
            if not cov:
                # covered by another lane-A module's ontology?
                other = []
                for m2, (st2, _) in all_stmts.items():
                    if m2 == mod:
                        continue
                    for s in st2:
                        why = covers(s, e, pats)
                        if why:
                            other.append(f"{s['id']} ({why})")
                            break
                e["covered_elsewhere"] = other
            uniq.append(e)
        per_mod[mod] = uniq
        omit_reasons = {}
        omissions = []
        for e in uniq:
            if e["covered_by"]:
                continue
            if not e.get("public", True) and not e["kind"].startswith(("native", "task")) and e["kind"] != "internal":
                continue
            if e["kind"] == "sqlproc" and e.get("semantics_owner") not in (None, mod):
                omit_reasons[e["id"]] = f"installed by setup; semantics owned by module {e['semantics_owner']}"
                continue
            omissions.append({"id": e["id"], "kind": e["kind"], "source": e["source"],
                              "covered_elsewhere": e.get("covered_elsewhere", [])})
        # cells
        stmt_by_id = {s["id"]: s for s in stmts}
        cell_rows = []
        no_ep = []
        for c in cells:
            hits = []
            for sid in c["statements"]:
                s = stmt_by_id.get(sid)
                if not s:
                    continue
                for e in uniq:
                    if sid in e["_covered_ids"]:
                        hits.append(e["id"])
            hits = sorted(set(hits))
            row = {"entity": c["entity"], "state": c["state"], "command": c["command"], "outcome": c["outcome"],
                   "statements": c["statements"], "decision": c["decision"], "entry_points": hits[:15],
                   "entry_point_count": len(hits), "ontology_line": c["line"]}
            if not hits:
                # do the statements cite any product code at all (another module's entry point)?
                cited = []
                for sid in c["statements"]:
                    s = stmt_by_id.get(sid)
                    if s:
                        cited += [f"{p}:{a}-{b}" for p, a, b in s["cites"]]
                row["statements_cite"] = sorted(set(cited))[:10]
                impl = set()
                for sid in c["statements"]:
                    s = stmt_by_id.get(sid)
                    for p, a, b in (s["cites"] if s else []):
                        k = line_owner(py, cl, p, a)
                        if k:
                            impl.add(k)
                row["cited_code_outside_module"] = sorted(impl)[:10]
                no_ep.append(row)
            cell_rows.append(row)
        for e in uniq:
            for k in ("_covered_ids", "_callee_spans", "_key"):
                e.pop(k, None)
        counts = Counter(e["kind"] for e in uniq)
        tag_counts = Counter(k for e in uniq for k in e["kinds"])
        doc = {
            "module": mod, "name": NAMES[mod], "pin": S.PIN,
            "generated_by": "experiment/playbook-completion/models/breadth-a/tools/inventory.py",
            "method": ("Mechanical: Python ast over the module's files and a line scanner over its .cls files, with the "
                       "file/function assignment of modules.py transcribed from the ontology Scope line "
                       f"({MODULE_FILES[mod]['scope']}). Coverage: a statement names the entry point or cites its file "
                       "with an overlapping line range. Name matching is textual; a hit is evidence of mention, not "
                       "of a correct statement."),
            "scope_files": {"python": list(MODULE_FILES[mod]["py"].keys()), "cls": MODULE_FILES[mod].get("cls", []),
                            "sql_files": bool(MODULE_FILES[mod].get("sql_files"))},
            "ontology": ONTOLOGY[mod], "statements": len(stmts), "cells": len(cells),
            "counts": {"entry_points": len(uniq), "by_kind": dict(sorted(counts.items())),
                       "by_tag": dict(sorted(tag_counts.items())), "omissions": len(omissions),
                       "cells_without_entry_point": len(no_ep), "covered": sum(1 for e in uniq if e["covered_by"])},
            "entry_points": uniq,
            "omissions": omissions,
            "not_counted_as_omissions": omit_reasons,
            "cells": cell_rows,
            "cells_without_entry_point": no_ep,
            "excluded_by_scope": excluded_all[mod],
        }
        (out_dir / f"{mod}.json").write_text(json.dumps(doc, indent=1) + "\n")
        summary[mod] = doc["counts"]
    unassigned["rest_routes"] = routes
    unassigned["cli_commands"] = clis
    (out_dir / "unassigned.json").write_text(json.dumps(unassigned, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
