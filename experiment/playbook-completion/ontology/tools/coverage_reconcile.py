#!/usr/bin/env python3
"""Mechanical reconciliation of every module's source inventory with the ontology (playbook §3.1, gate 3.1-coverage:
"statements cover the module's actual public entry points, storage owners, background jobs, native paths and
lifecycle operations (reconciled against a source inventory)").

    python3 experiment/playbook-completion/ontology/tools/coverage_reconcile.py               # counts per module
    python3 experiment/playbook-completion/ontology/tools/coverage_reconcile.py --list NN     # uncovered of NN
    python3 experiment/playbook-completion/ontology/tools/coverage_reconcile.py --json OUT    # per-entry result
    python3 experiment/playbook-completion/ontology/tools/coverage_reconcile.py --self-test

Inputs (all committed, read only):

- Source inventories. Modules 01-06: models/breadth-a/inventory/NN.json (`entry_points`, `omissions`,
  `not_counted_as_omissions`). Modules 07-11: models/breadth-b/inventory/NN.json (`entry_points`, `omissions`).
  Modules 12-18 and the unowned surface (module 00): models/breadth-c/inventory.json (`entries` with `owners`; for
  15-18 the lexical `reconciliation`; `unowned_entry_points` and `unowned_files` are module 00's inventory: every
  part of the tree no Scope line owns needs an owner or a reason).
- The ontology modules ontology/NN-*.md (statements: Evidence, Source and Notes columns).
- ontology/reconcile-records.json: one reviewed record per entry point that no statement covers mechanically.
- The storage inventory (pseudo-module "stores", for the gate's "storage owners"): every global the product writes
  or names and every SQL table it declares, derived here from the pinned tree (inv_stores); a store is covered
  when a statement of any module names it.

An entry point counts as covered when, in this order:

1. its inventory already counts it covered (a statement of the original module names it or cites overlapping lines;
   breadth-a also counts code it executes within three call hops) and every statement the inventory names still
   exists in the module here; or the inventory gives a reason it is not counted (another module owns its semantics);
2. a statement of its module cites its file with a line range overlapping its definition (Evidence, Source or Notes),
   or names it (qualified Class.member; for a name of five or more characters that is not a common word, a call
   "name(" or a quoted `name`; or a distinctive identifier of eight or more characters with "_" or camel case);
3. a record in reconcile-records.json says why: `statement` (named statements of this module state it under another
   name), `helper` (private or delegating code of the named covered entry point or statement), `other-module` (the
   named statements of another module state it), `owner` (module 00: the named module owns it and its statements
   state it), `not-entry-point` (an inventory false positive), `tooling` (repository tooling outside the product:
   not shipped and not deployed; the reason must say why), `not-deployed`.

Every record is validated: its entry point is in the inventory, the statements it names exist in the module it
names, a helper's target is covered (no chains through uncovered entries, no cycles), and `why` is not empty. An
invalid record does not count. Rule records (`rules`) match module 00 entries and files by a path glob.
Exit 0 when no record is invalid; the per-module uncovered counts are the result. --require-zero fails on any
uncovered entry point.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
HERE = Path(__file__).resolve().parent
ONT = HERE.parent
COMP = ONT.parent
REPO = COMP.parent.parent
MODULES = [f"{i:02d}" for i in range(0, 19)]
RECORD_KINDS = {"statement", "helper", "other-module", "owner", "not-entry-point", "tooling", "not-deployed"}
COMMON = {"status", "index", "run", "apply", "get", "set", "put", "remove", "insert", "delete", "build", "search",
          "info", "drop", "count", "event", "latest", "call", "close", "first", "begin", "commit", "rollback", "native",
          "written", "level", "fail", "wrapper", "registered", "clear", "create", "purge", "open", "load", "save",
          "list", "query", "main", "health", "reset", "verify", "diff", "redact", "tuple", "equal", "inverse",
          "to_wire", "from_wire", "to_dict", "from_row", "to_list", "__init__", "__call__", "__main__", "root", "q"}
CITE = re.compile(r"((?:[\w.-]+/)*[\w.-]+\.(?:py|cls|sql|toml|yml|yaml|sh|cpf|conf|json|txt|cfg|ini|md))"
                  r":(\d+)(?:-(\d+))?((?:\s*,\s*\d+(?:-\d+)?(?![\w/.]))*)")


# --------------------------------------------------------------------------- pinned tree

class PinTree:
    def __init__(self, repo: Path = REPO, pin: str = PIN):
        self.repo, self.pin = repo, pin
        out = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", pin], capture_output=True,
                             text=True, check=True).stdout
        self.files = set(out.split())
        self.by_base: Dict[str, List[str]] = defaultdict(list)
        for f in self.files:
            self.by_base[f.rsplit("/", 1)[-1]].append(f)
        self._text: Dict[str, Optional[str]] = {}

    def text(self, path: str) -> Optional[str]:
        if path not in self._text:
            if path not in self.files:
                self._text[path] = None
            else:
                self._text[path] = subprocess.run(["git", "-C", str(self.repo), "show", f"{self.pin}:{path}"],
                                                  capture_output=True, text=True, check=True).stdout
        return self._text[path]

    def resolve(self, path: str) -> Optional[str]:
        if path in self.files:
            return path
        for pre in ("iris_vector_graph/", "iris_src/src/Graph/KG/", "iris_vector_graph/_engine/", "iris_src/src/"):
            if pre + path in self.files:
                return pre + path
        cands = self.by_base.get(path.rsplit("/", 1)[-1], [])
        cands = [c for c in cands if c.endswith(path)]
        if len(cands) == 1:
            return cands[0]
        pref = [c for c in cands if c.startswith(("iris_vector_graph/", "iris_src/src/"))]
        return pref[0] if len(pref) == 1 else None

    def cls_span(self, path: str, line: int) -> Tuple[int, int]:
        """A class member's span: its declaration line to the first line that is a lone '}' after its body opens."""
        text = self.text(path)
        if text is None:
            return line, line
        lines = text.split("\n")
        opened = False
        for i in range(line - 1, len(lines)):
            s = lines[i].rstrip()
            if s.startswith("{"):
                opened = True
            if opened and s == "}":
                return line, i + 1
            if i > line - 1 and re.match(r"^(ClassMethod|Method|Query|Property|Parameter|Index|XData|Storage)\b", s):
                return line, i
        return line, line


# --------------------------------------------------------------------------- ontology

@dataclass
class Stmt:
    id: str
    module: str
    text: str            # the whole row, for name matches
    cites: List[Tuple[str, int, int]]


def split_row(line: str) -> List[str]:
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]


def table(lines: List[str], heading: str) -> List[List[str]]:
    try:
        i = next(k for k, l in enumerate(lines) if l.strip() == f"## {heading}")
    except StopIteration:
        return []
    while i < len(lines) and not lines[i].startswith("|"):
        i += 1
    i += 2
    out = []
    while i < len(lines) and lines[i].startswith("|"):
        out.append(split_row(lines[i]))
        i += 1
    return out


def cites_of(text: str, tree: PinTree) -> List[Tuple[str, int, int]]:
    out = []
    for m in CITE.finditer(text):
        path = tree.resolve(m.group(1))
        if not path:
            continue
        a = int(m.group(2))
        out.append((path, a, int(m.group(3) or a)))
        for x, y in re.findall(r"(\d+)(?:-(\d+))?", m.group(4) or ""):
            out.append((path, int(x), int(y or x)))
    return out


def load_ontology(ont: Path, tree: PinTree) -> Dict[str, Dict[str, Stmt]]:
    mods: Dict[str, Dict[str, Stmt]] = {}
    for f in sorted(ont.glob("[0-9][0-9]-*.md")):
        mod = f.name[:2]
        lines = f.read_text(encoding="utf-8").split("\n")
        mods[mod] = {}
        for r in table(lines, "Statements"):
            if len(r) < 7:
                continue
            row = " | ".join(r)
            mods[mod][r[0]] = Stmt(r[0], mod, row, cites_of(" ; ".join(r[4:7]), tree))
    return mods


# --------------------------------------------------------------------------- inventories

@dataclass
class Entry:
    id: str
    module: str
    kind: str
    name: str            # member name
    container: str       # class (short or full) or ''
    file: str
    start: int
    end: int
    source: str          # which inventory
    base: str            # inventory-covered | inventory-not-counted | candidate
    base_ref: List[str] = field(default_factory=list)
    status: str = ""
    how: str = ""


def c_id(e: dict) -> str:
    return f"{e['kind']}:{e['file']}:{e['line']}:{e['name']}"


def inv_breadth_a(mod: str) -> List[Entry]:
    d = json.loads((COMP / "models/breadth-a/inventory" / f"{mod}.json").read_text())
    omis = {o["id"] for o in d["omissions"]}
    notc = d.get("not_counted_as_omissions", {})
    out = []
    for e in d["entry_points"]:
        cov = [c["statement"] for c in e.get("covered_by", [])]
        if cov:
            base, ref = "inventory-covered", cov
        elif e["id"] in notc:
            base, ref = "inventory-not-counted", [notc[e["id"]]]
        elif e["id"] in omis:
            base, ref = "candidate", []
        else:
            base, ref = "inventory-not-counted", ["not public and not native, task or internal (breadth-a rule)"]
        qual = e.get("qual") or ""
        cont = e.get("class") or (qual.rsplit(".", 1)[0] if "." in qual else "")
        out.append(Entry(e["id"], mod, e["kind"], e["name"], cont, e.get("file") or "", e.get("start") or 0,
                         e.get("end") or 0, f"models/breadth-a/inventory/{mod}.json", base, ref))
    return out


def inv_breadth_b(mod: str) -> List[Entry]:
    d = json.loads((COMP / "models/breadth-b/inventory" / f"{mod}.json").read_text())
    omis = set(d["omissions"])
    out = []
    for e in d["entry_points"]:
        eid = e["id"]
        tail = eid.split(":")[-1].split("[")[0]
        if eid.startswith("cls:"):
            cont, name = tail.rsplit(".", 1)
        elif "." in tail:
            cont, name = tail.rsplit(".", 1)
        else:
            cont, name = "", tail
        cov = list(e.get("covered_by") or [])
        base = "candidate" if eid in omis else ("inventory-covered" if cov else "candidate")
        out.append(Entry(eid, mod, e["kind"], name, cont, e.get("path") or "", e.get("start") or 0,
                         e.get("end") or 0, f"models/breadth-b/inventory/{mod}.json", base, cov))
    return out


def inv_breadth_c(mod: str, tree: PinTree, inv: dict) -> List[Entry]:
    recon = inv["reconciliation"].get(mod)
    unc = {(u["kind"], u["file"], u["line"], u["name"]) for u in recon["uncovered"]} if recon else None
    out = []
    for e in inv["entries"]:
        if mod not in e["owners"]:
            continue
        start, end = e["line"], e.get("end") or e["line"]
        if e["kind"] == "os-method":
            start, end = tree.cls_span(e["file"], e["line"])
        name = e.get("method") or e["name"].rsplit(".", 1)[-1] if e["kind"] == "os-method" else e["name"]
        cont = e.get("container") or ""
        key = (e["kind"], e["file"], e["line"], e["name"])
        if unc is None:
            base = "candidate"          # 12-14: no inventory reconciliation; this tool is the reconciliation
        else:
            base = "candidate" if key in unc else "inventory-covered"
        out.append(Entry(c_id(e), mod, e["kind"], name, cont, e["file"], start, end,
                         "models/breadth-c/inventory.json", base,
                         ["lexical (breadth-c rule: the name is a token of the module file)"] if base != "candidate"
                         else []))
    return out


def inv_unowned(tree: PinTree, inv: dict) -> List[Entry]:
    out = []
    for e in inv["unowned_entry_points"]:
        start, end = e["line"], e["line"]
        if e["kind"] == "os-method":
            start, end = tree.cls_span(e["file"], e["line"])
        name = e["name"].rsplit(".", 1)[-1] if e["kind"] == "os-method" else e["name"]
        out.append(Entry(c_id(e), "00", e["kind"], name, e.get("container") or "", e["file"], start, end,
                         "models/breadth-c/inventory.json#unowned_entry_points", "candidate"))
    for f in inv["unowned_files"]:
        out.append(Entry(f"file:{f}", "00", "file", f.rsplit("/", 1)[-1], "", f, 0, 0,
                         "models/breadth-c/inventory.json#unowned_files", "candidate"))
    return out


SYSTEM_GLOBALS = {"oddDEF", "r", "P", "rOBJ", "ROUTINE", "SYS", "rINDEX", "rMAC", "rINC"}


def inv_stores(tree: PinTree) -> List[Entry]:
    """The storage inventory (pseudo-module "stores"): every global the product writes or names and every SQL table
    it declares, derived from the pinned tree. Globals: a Set/Kill/Merge/$Increment of ^Name in server code
    (iris_src/src) and a "^Name" string literal in the Python package. Tables: Graph_KG.<name> after CREATE TABLE, a
    {schema}.<name> table template, and a persistent class's SqlTableName. A store is covered when a statement of any
    module names it (^Name; Graph_KG.name, or the bare name when it holds an underscore)."""
    found: Dict[str, List[str]] = defaultdict(list)
    for f in sorted(tree.files):
        if f.startswith("iris_src/src/") and f.endswith(".cls"):
            kind = "cls"
        elif f.startswith("iris_vector_graph/") and f.endswith(".py"):
            kind = "py"
        elif f.startswith("sql/") and f.endswith(".sql"):
            kind = "sql"
        else:
            continue
        text = tree.text(f) or ""
        for i, l in enumerate(text.split("\n"), 1):
            names = []
            if kind == "cls":
                names += ["^" + m.group(1) for m in re.finditer(
                    r"(?i)\b(?:set|s|kill|k|merge|m)\s+(?:[^\s,]*,)*\^([A-Za-z][\w.]*)", l)]
                names += ["^" + m.group(1) for m in re.finditer(r"(?i)\$i(?:ncrement)?\(\^([A-Za-z][\w.]*)", l)]
                m = re.search(r"Extends\s+\(?%Persistent.*SqlTableName\s*=\s*(\w+)", l)
                if m:
                    names.append("Graph_KG." + m.group(1))
            if kind == "py":
                names += ["^" + m.group(1) for m in re.finditer(r"[\"']\^([A-Za-z][\w.]*)[\"']", l)]
            names += ["Graph_KG." + m.group(1) for m in re.finditer(
                r"(?i)CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:Graph_KG|\{schema\})\.(\w+)", l)]
            for n in names:
                if n.startswith("^") and (n[1:] in SYSTEM_GLOBALS or n[1:].startswith("IRIS.")):
                    continue
                found[n].append(f"{f}:{i}")
    out = []
    for n in sorted(found):
        first = found[n][0]
        path, line = first.rsplit(":", 1)
        out.append(Entry(f"store:{n}", "stores", "global" if n.startswith("^") else "table", n, "", path,
                         int(line), int(line), "pinned tree (inv_stores)", "candidate",
                         [f"{len(found[n])} site(s), first {first}"]))
    return out


def store_cover(e: Entry, onto: Dict[str, Dict[str, Stmt]]) -> Optional[str]:
    n = e.name
    if n.startswith("^"):
        pats = [re.compile(re.escape(n) + r"(?![\w.])")]
    else:
        short = n.split(".", 1)[1]
        pats = [re.compile(r"(?<![\w.])" + re.escape(n) + r"(?![\w])")]
        if "_" in short:
            pats.append(re.compile(r"(?<![\w.])" + re.escape(short) + r"(?![\w])"))
    for m in sorted(onto):
        for s in onto[m].values():
            if any(p.search(s.text) for p in pats):
                return f"{s.id} (module {m}) names {n}"
    return None


def load_inventories(tree: PinTree) -> Dict[str, List[Entry]]:
    inv = json.loads((COMP / "models/breadth-c/inventory.json").read_text())
    out: Dict[str, List[Entry]] = {"00": inv_unowned(tree, inv), "stores": inv_stores(tree)}
    for m in ["01", "02", "03", "04", "05", "06"]:
        out[m] = inv_breadth_a(m)
    for m in ["07", "08", "09", "10", "11"]:
        out[m] = inv_breadth_b(m)
    for m in ["12", "13", "14", "15", "16", "17", "18"]:
        out[m] = inv_breadth_c(m, tree, inv)
    return out


# --------------------------------------------------------------------------- matching

def name_patterns(e: Entry) -> List[re.Pattern]:
    n = e.name
    pats = []
    if not n:
        return pats
    if e.kind == "file":
        return [re.compile(r"(?<![\w/.-])" + re.escape(e.file) + r"(?![\w/])")]
    if e.container:
        short = e.container.rsplit(".", 1)[-1]
        pats.append(re.compile(r"(?<![\w])" + re.escape(f"{short}.{n}") + r"(?![\w])"))
        if short != e.container:
            pats.append(re.compile(r"(?<![\w])" + re.escape(f"{e.container}.{n}") + r"(?![\w])"))
    if n.lower() in COMMON or n.startswith("__") or len(n) < 5:
        return pats
    pats.append(re.compile(r"(?<![\w.])" + re.escape(n) + r"\s*\("))
    pats.append(re.compile(r"`" + re.escape(n) + r"[`(]"))
    distinctive = len(n) >= 8 and ("_" in n.strip("_") or re.search(r"[a-z][A-Z]", n))
    if distinctive:
        pats.append(re.compile(r"(?<![\w])" + re.escape(n) + r"(?![\w])"))
    return pats


def statement_cover(e: Entry, stmts: Dict[str, Stmt]) -> Optional[str]:
    if e.file and e.start:
        for s in stmts.values():
            for path, a, b in s.cites:
                if path == e.file and a <= e.end and b >= e.start:
                    return f"{s.id} cites {path}:{a}-{b}"
    pats = name_patterns(e)
    for s in stmts.values():
        for p in pats:
            if p.search(s.text):
                return f"{s.id} names {e.container + '.' if e.container else ''}{e.name}"
    return None


# --------------------------------------------------------------------------- records

def load_records(path: Path) -> dict:
    if not path.exists():
        return {"modules": {}, "rules": []}
    return json.loads(path.read_text(encoding="utf-8"))


def reconcile(invs: Dict[str, List[Entry]], onto: Dict[str, Dict[str, Stmt]], records: dict
              ) -> Tuple[Dict[str, List[Entry]], List[str]]:
    errors: List[str] = []
    recs = records.get("modules", {})
    rules = records.get("rules", [])
    all_ids = {m: {e.id for e in es} for m, es in invs.items()}
    for m, rs in recs.items():
        for eid in rs:
            if eid not in all_ids.get(m, set()):
                errors.append(f"[stale-record] {m} {eid}: not in the module's inventory")
    by_id: Dict[Tuple[str, str], Entry] = {}
    # passes 1 and 2
    for m, es in invs.items():
        stmts = onto.get(m, {})
        for e in es:
            by_id[(m, e.id)] = e
            if e.base == "inventory-covered":
                gone = [s for s in e.base_ref if re.match(r"^[A-Z]{2,4}-", s) and s not in stmts]
                if gone:
                    errors.append(f"[inventory] {m} {e.id}: inventory statements no longer here: {gone}")
                e.status, e.how = "inventory", "; ".join(e.base_ref[:4])
                continue
            if e.base == "inventory-not-counted":
                e.status, e.how = "inventory-not-counted", "; ".join(e.base_ref)
                continue
            how = store_cover(e, onto) if m == "stores" else statement_cover(e, stmts)
            if how:
                e.status, e.how = "statement-match", how
    # pass 3: records (helpers resolved after the others, to a fixpoint)

    def rec_for(m: str, e: Entry) -> Optional[dict]:
        r = recs.get(m, {}).get(e.id)
        if r is not None:
            return r
        for rule in rules:
            if rule.get("module") == m and fnmatch.fnmatch(e.file, rule["file_glob"]) \
                    and (not rule.get("kinds") or e.kind in rule["kinds"]):
                return dict(rule, rule=rule["file_glob"])
        return None

    def valid(m: str, e: Entry, r: dict) -> Optional[str]:
        k = r.get("status")
        if k not in RECORD_KINDS:
            return f"unknown record status {k!r}"
        if not str(r.get("why", "")).strip():
            return "record has no 'why'"
        if k in ("statement", "other-module", "owner"):
            tm = m if k == "statement" else r.get("module", "")
            sts = r.get("statements") or []
            if not sts:
                return f"{k} record names no statement"
            missing = [s for s in sts if s not in onto.get(tm, {})]
            if missing:
                return f"statements {missing} not in module {tm}"
        if k == "helper" and not r.get("of"):
            return "helper record names no covered entry point or statement ('of')"
        return None

    pending = []
    for m, es in invs.items():
        for e in es:
            if e.status:
                continue
            r = rec_for(m, e)
            if r is None:
                continue
            bad = valid(m, e, r)
            if bad:
                errors.append(f"[record] {m} {e.id}: {bad}")
                continue
            if r["status"] == "helper":
                pending.append((m, e, r))
                continue
            e.status = "record:" + r["status"]
            e.how = (", ".join(r.get("statements", [])) + (f" (module {r['module']})" if r.get("module") else "")
                     + (f" [rule {r['rule']}]" if r.get("rule") else "") + ": " + r["why"])
    changed = True
    while changed:
        changed = False
        for m, e, r in pending:
            if e.status:
                continue
            targets = r["of"] if isinstance(r["of"], list) else [r["of"]]
            ok = True
            for t in targets:
                if re.match(r"^[A-Z]{2,4}-[A-Za-z0-9.]+$", t):
                    tm = r.get("module", m)
                    if t not in onto.get(tm, {}):
                        ok = False
                else:
                    te = by_id.get((r.get("module", m), t))
                    if te is None or not te.status or te.status == "uncovered":
                        ok = False
            if ok:
                e.status, e.how = "record:helper", f"of {', '.join(targets)}: {r['why']}"
                changed = True
    for m, e, r in pending:
        if not e.status:
            errors.append(f"[helper] {m} {e.id}: target {r['of']} is not covered (or does not exist)")
    for m, es in invs.items():
        for e in es:
            if not e.status:
                e.status = "uncovered"
    return invs, errors


def summarize(invs: Dict[str, List[Entry]]) -> Dict[str, dict]:
    out = {}
    for m in sorted(invs, key=lambda k: (k == "stores", k)):
        c = Counter(e.status for e in invs[m])
        out[m] = {"entries": len(invs[m]), "uncovered": c.get("uncovered", 0), "by_status": dict(sorted(c.items()))}
    return out


def run(ont: Path, records_path: Path, tree: Optional[PinTree] = None):
    tree = tree or PinTree()
    invs = load_inventories(tree)
    onto = load_ontology(ont, tree)
    return reconcile(invs, onto, load_records(records_path))


# --------------------------------------------------------------------------- self-test

def self_test() -> int:
    """Fixture: one module, a statement, and five entry points. A seeded uncovered entry point must be reported;
    cite overlap, a statement record, a helper of a covered entry, a helper chained to an uncovered entry, a record
    naming a missing statement, a stale record and a helper cycle must each give the expected result. Then on the
    real inputs: deleting one real record raises that module's uncovered count by one, and a seeded entry point with
    no statement and no record is reported uncovered."""
    fails = []
    tree = PinTree()
    with tempfile.TemporaryDirectory() as td:
        ont = Path(td)
        (ont / "05-mod.md").write_text(
            "# 05 Mod\n\n## Statements\n\n| Id | Parent | Kind | Statement | Evidence | Source | Notes |\n"
            "|---|---|---|---|---|---|---|\n"
            "| MOD-0 | SYS-0 | R | Root. | inspected:iris_src/src/Graph/KG/Ledger.cls:27-33 | x | |\n"
            "| MOD-B1 | MOD-0 | B | Text. | inspected:iris_src/src/Graph/KG/Eraser.cls:47-50 | x | |\n",
            encoding="utf-8")
        onto = load_ontology(ont, tree)

        def mk(i, start, end, name="Foo"):
            return Entry(f"e{i}", "05", "cls", name, "Graph.KG.X", f"iris_src/src/Graph/KG/{'Eraser' if i else 'Ledger'}.cls",
                         start, end, "fixture", "candidate")

        def case(entries, recs):
            invs = {"05": entries}
            return reconcile(invs, onto, {"modules": {"05": recs}})

        invs, errs = case([mk(1, 900, 905, "SeededUncovered")], {})
        if invs["05"][0].status != "uncovered" or summarize(invs)["05"]["uncovered"] != 1:
            fails.append("seeded uncovered entry point not reported")
        invs, _ = case([mk(1, 45, 60)], {})
        if invs["05"][0].status != "statement-match":
            fails.append("cite overlap not counted")
        invs, errs = case([mk(1, 900, 905)], {"e1": {"status": "statement", "statements": ["MOD-B1"], "why": "w"}})
        if invs["05"][0].status != "record:statement" or errs:
            fails.append("statement record not counted")
        invs, errs = case([mk(1, 45, 60), mk(2, 900, 905)], {"e2": {"status": "helper", "of": "e1", "why": "w"}})
        if invs["05"][1].status != "record:helper" or errs:
            fails.append("helper of a covered entry not counted")
        invs, errs = case([mk(1, 800, 805), mk(2, 900, 905)], {"e2": {"status": "helper", "of": "e1", "why": "w"}})
        if invs["05"][1].status != "uncovered" or not any("[helper]" in x for x in errs):
            fails.append("helper of an uncovered entry accepted")
        invs, errs = case([mk(1, 900, 905)], {"e1": {"status": "statement", "statements": ["MOD-B9"], "why": "w"}})
        if invs["05"][0].status != "uncovered" or not any("[record]" in x for x in errs):
            fails.append("record naming a missing statement accepted")
        invs, errs = case([mk(1, 900, 905)], {"e9": {"status": "tooling", "why": "w"}})
        if not any("[stale-record]" in x for x in errs):
            fails.append("stale record not reported")
        invs, errs = case([mk(1, 800, 805), mk(2, 900, 905)], {"e1": {"status": "helper", "of": "e2", "why": "w"},
                                                               "e2": {"status": "helper", "of": "e1", "why": "w"}})
        if invs["05"][0].status != "uncovered" or invs["05"][1].status != "uncovered":
            fails.append("helper cycle accepted")
        invs, errs = case([mk(1, 900, 905)], {"e1": {"status": "tooling", "why": ""}})
        if invs["05"][0].status != "uncovered":
            fails.append("record without a reason accepted")
    # real inputs
    real = load_records(ONT / "reconcile-records.json")
    invs, errs = run(ONT, ONT / "reconcile-records.json", tree)
    base = summarize(invs)
    if errs:
        fails.append(f"real inputs have {len(errs)} invalid record(s)")
    # a non-helper record that is what covers its entry (not a redundant one, and no rule would catch the entry)
    status = {(m, e.id): (e.status, e.how) for m, es in invs.items() for e in es}
    picked = next(((m, eid) for m, rs in sorted(real.get("modules", {}).items()) for eid, r in sorted(rs.items())
                   if r.get("status") != "helper" and m != "00"
                   and status.get((m, eid), ("", ""))[0] == "record:" + r.get("status", "")), None)
    if picked:
        m, eid = picked
        cut = json.loads(json.dumps(real))
        del cut["modules"][m][eid]
        dependants = sum(1 for r in cut["modules"][m].values() if r.get("status") == "helper"
                         and eid in (r["of"] if isinstance(r["of"], list) else [r["of"]]))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "r.json"
            p.write_text(json.dumps(cut))
            invs2, _ = run(ONT, p, tree)
        got = summarize(invs2)[m]["uncovered"] - base[m]["uncovered"]
        print(f"real inputs: removed record {m} {eid} ({real['modules'][m][eid]['status']}): uncovered in {m} "
              f"{base[m]['uncovered']} -> {base[m]['uncovered'] + got}")
        if got < 1 or (dependants == 0 and got != 1):
            fails.append(f"removing record {m} {eid} changed uncovered by {got}, want 1 (+ dependants)")
    else:
        fails.append("no real record to remove")
    tree2 = tree
    invs3 = load_inventories(tree2)
    invs3["11"].append(Entry("seed:Graph.KG.Ledger.SeededNoSuchMethod", "11", "cls", "SeededNoSuchMethod",
                             "Graph.KG.Ledger", "iris_src/src/Graph/KG/Ledger.cls", 99999, 99999, "seed", "candidate"))
    invs3, _ = reconcile(invs3, load_ontology(ONT, tree2), real)
    seeded = [e for e in invs3["11"] if e.id.startswith("seed:")]
    print(f"real inputs: seeded entry point {seeded[0].id} -> {seeded[0].status}; uncovered in 11 "
          f"{summarize(invs3)['11']['uncovered']}")
    if not any(e.status == "uncovered" for e in seeded):
        fails.append("seeded entry point in the real inventory not reported")
    n = 9 + 2
    for f in fails:
        print("SELF-TEST FAIL:", f)
    print(f"coverage_reconcile self-test: {n - len(fails)}/{n} cases as expected "
          f"(seeded uncovered entry point reported: {'yes' if 'seeded uncovered entry point not reported' not in fails else 'no'})")
    return 1 if fails else 0


# --------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", nargs="*", metavar="NN")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--records", type=Path, default=ONT / "reconcile-records.json")
    ap.add_argument("--ontology", type=Path, default=ONT)
    ap.add_argument("--require-zero", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    invs, errors = run(a.ontology, a.records)
    summ = summarize(invs)
    for e in errors:
        print("INVALID:", e)
    print(f"{'module':<7}{'entries':>8}{'uncovered':>10}  by status")
    tot = Counter()
    for m, s in summ.items():
        tot["entries"] += s["entries"]
        tot["uncovered"] += s["uncovered"]
        print(f"{m:<7}{s['entries']:>8}{s['uncovered']:>10}  " + ", ".join(f"{k}={v}" for k, v in s["by_status"].items()))
    print(f"{'total':<7}{tot['entries']:>8}{tot['uncovered']:>10}; invalid records: {len(errors)}")
    if a.list is not None:
        for m in (a.list or sorted(invs)):
            for e in invs.get(m, []):
                if e.status == "uncovered":
                    print(f"UNCOVERED {m} {e.id} {e.file}:{e.start}-{e.end}")
    if a.json:
        a.json.write_text(json.dumps({"pin": PIN, "summary": summ, "invalid_records": errors,
                                      "entries": {m: [dict(id=e.id, kind=e.kind, file=e.file, start=e.start, end=e.end,
                                                           status=e.status, how=e.how, inventory=e.source)
                                                      for e in es] for m, es in invs.items()}},
                                     indent=1, sort_keys=True) + "\n")
    if errors:
        return 1
    if a.require_zero and tot["uncovered"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
