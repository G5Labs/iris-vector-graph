#!/usr/bin/env python3
"""§3.4 storage-order scan, extended (structural lane). A copy of tools/storage_order_check.py (unchanged there) with
four more rules, a module assignment and a disposition gate.

    python storage_order_scan.py --json OUT [--dispositions D.json] [--modules 01,03,...]   # scan (+ gate)
    python storage_order_scan.py --self-test                                                 # seeded violations

Rules (each site: file, line, rule, enclosing function, statement text):
  prefix-literal  the original rule: one string literal (Python) or a .cls line window takes a result prefix
                  (SELECT TOP n / LIMIT / FETCH FIRST) and has no ORDER BY.
  prefix-split    Python: a statement passed to execute() is assembled from several literals (f-string placeholders
                  resolved from the function's own assignments, `+=` and `+` concatenation) and the assembled text
                  takes a prefix with no ORDER BY, while no single literal of it does (nodes_edges.py:820 style).
  first-row       Python: a fetchone() (or fetchall()[0]) reads the first row of an executed SELECT that has no ORDER
                  BY, no TOP 1 1 existence form and is not a single-row aggregate.
  os-first-row    ObjectScript: an embedded &sql(SELECT ... INTO ...) outside a cursor, or a dynamic statement
                  (%ExecDirect / %Prepare text) read with `If rs.%Next()` (one row), with no ORDER BY.
  os-cutoff       ObjectScript: a loop over a SQL cursor (FETCH / %Next) or $Order that stops at a count
                  (Quit:<counter> >= ..., or a For loop bounded by a count) - a truncating scan.
Each site gets an automatic class where the text decides it (existence-only, single-row-aggregate, unique-key with
the key named, collation-ordered for $Order loops); every other site is a candidate that needs a disposition.

Gate (--dispositions): every site of the selected modules must carry a disposition whose `cite` lines exist at the
pin and whose `anchor` text occurs on the cited line (so a stale disposition fails), and the disposition's class
must be one of: false-positive (ORDER BY present / not SQL), existence-only, single-row-aggregate, unique-key,
collation-ordered, documented-sample, set-valued, order-irrelevant, finding:<id>. Exit 1 if any site lacks one.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INVENTORY = REPO / "experiment/playbook-completion/models/breadth-c/inventory.json"
PREFIX = re.compile(r"\bSELECT\s+(?:DISTINCT\s+)?TOP\s+\??\d*|\bLIMIT\s+[\d?]|\bFETCH\s+FIRST\b", re.I)
PREFIX_ANY = re.compile(r"\bSELECT\s+(?:DISTINCT\s+)?(?:\{[^{}]*\}\s*)*TOP\b|\bLIMIT\s+(?:[\d?]|\{)|\bFETCH\s+FIRST\b", re.I)
TOP_FRAG = re.compile(r"(?:^|\s)TOP\s+(?:\{|\d|\?)|\bLIMIT\s+(?:\{|\d|\?)|\bFETCH\s+FIRST\b", re.I)
ORDER = re.compile(r"\bORDER\s+BY\b", re.I)
EXISTS = re.compile(r"\bSELECT\s+TOP\s+1\s+1\b", re.I)
SELECT = re.compile(r"^\W*\(?\s*(?:WITH\b.*?\)\s*)?SELECT\b", re.I | re.S)
AGG_ONLY = re.compile(r"^\s*SELECT\s+(?:(?:COUNT|MAX|MIN|SUM|AVG|LIST)\s*\(|1\s+FROM|%EXACT|1\b)", re.I)
GROUP = re.compile(r"\bGROUP\s+BY\b", re.I)
# Declared unique keys of the namespace's tables (iris_vector_graph/schema.py:35-544, ledger classes).
UNIQUE_KEYS = {
    "nodes": [{"node_id", "graph_id"}],
    "rdf_labels": [{"graph_id", "s", "label"}],
    "rdf_props": [{"graph_id", "s", "key"}],
    "rdf_edges": [{"edge_id"}, {"s", "p", "o_id", "graph_id", "ekey"}],
    "embedding_registry": [{"table_name", "graph_id"}],
    "docs": [{"graph_id", "id"}],
    "fhir_graphs": [{"graph_id"}],
    "fhir_definitions": [{"graph_id", "rsrc_key"}],
    "rdf_reifications": [{"reifier_id"}],
    "table_mappings": [{"label"}],
    "relationship_mappings": [{"source_label", "predicate", "target_label"}],
    "rdf_namespaces": [{"prefix"}],
    "ledger_revisions": [{"seq"}, {"revision_id"}],
    "ledger_stats": [{"id"}],
    "kg_nodeembeddings": [{"graph_id", "node_id"}],
    "kg_nodeembeddings_optimized": [{"graph_id", "node_id"}],
    "kg_edgeembeddings": [{"graph_id", "s", "p", "o_id"}],
}
EXEC_NAMES = {"execute", "_execute", "_exec", "exec_sql", "execute_sql", "_run_sql", "_sql", "_query", "query_one",
              "_fetchone", "_fetch_one", "fetch_one"}


def norm(s: str) -> str:
    return " ".join(s.split())


# --------------------------------------------------------------------------------------------- Python rendering

class Fn:
    def __init__(self, node, qual):
        self.node, self.qual = node, qual
        self.assign = {}      # name -> [(line, op, expr)]
        for n in ast.walk(node):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                self.assign.setdefault(n.targets[0].id, []).append((n.lineno, "=", n.value))
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and isinstance(n.op, ast.Add):
                self.assign.setdefault(n.target.id, []).append((n.lineno, "+=", n.value))
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
                self.assign.setdefault(n.target.id, []).append((n.lineno, "=", n.value))

    def render_name(self, name, before, depth):
        hist = sorted(x for x in self.assign.get(name, []) if x[0] <= before)
        if not hist or depth > 3:
            return None
        # the last plain assignment before `before` and every += after it; alternative plain assignments in
        # branches are joined with ' | ' so a prefix or ORDER BY in any branch is seen
        plain = [x for x in hist if x[1] == "="]
        if not plain:
            return None
        last = plain[-1][0]
        alts = [self.render(x[2], x[0], depth + 1) for x in plain if x[0] >= plain[0][0]]
        base = " | ".join(a for a in alts if a) if len(plain) > 1 else self.render(plain[-1][2], last, depth + 1)
        tail = "".join(self.render(x[2], x[0], depth + 1) or "{}" for x in hist if x[1] == "+=" and x[0] > last)
        return (base or "{}") + tail

    def render(self, e, line, depth=0):
        if isinstance(e, ast.Constant) and isinstance(e.value, str):
            return e.value
        if isinstance(e, ast.JoinedStr):
            out = []
            for v in e.values:
                if isinstance(v, ast.Constant):
                    out.append(str(v.value))
                elif isinstance(v, ast.FormattedValue):
                    r = None
                    if isinstance(v.value, ast.Name):
                        r = self.render_name(v.value.id, line, depth + 1)
                    elif isinstance(v.value, ast.IfExp):
                        a = self.render(v.value.body, line, depth + 1)
                        b = self.render(v.value.orelse, line, depth + 1)
                        r = " ".join(x for x in (a, b) if x)
                    out.append(r if r is not None else "{}")
            return "".join(out)
        if isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Add, ast.Mod)):
            a = self.render(e.left, line, depth + 1)
            b = self.render(e.right, line, depth + 1) if isinstance(e.op, ast.Add) else ""
            return (a or "{}") + (b or "")
        if isinstance(e, ast.IfExp):
            a = self.render(e.body, line, depth + 1)
            b = self.render(e.orelse, line, depth + 1)
            return " ".join(x for x in (a, b) if x) or None
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr == "format":
            return self.render(e.func.value, line, depth + 1)
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr == "join" and e.args:
            a = e.args[0]
            parts = []
            if isinstance(a, (ast.List, ast.Tuple)):
                parts = [self.render(x, line, depth + 1) or "{}" for x in a.elts]
            elif isinstance(a, ast.Name):
                r = self.render_name(a.id, line, depth + 1)
                parts = [r or "{}"]
            return " ".join(parts)
        if isinstance(e, (ast.List, ast.Tuple)):
            return " ".join(self.render(x, line, depth + 1) or "" for x in e.elts)
        if isinstance(e, ast.Name):
            return self.render_name(e.id, line, depth + 1)
        return None


def py_functions(tree):
    out = []

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = f"{prefix}.{ch.name}" if prefix else ch.name
                out.append((ch, q))
                walk(ch, q)
            elif isinstance(ch, ast.ClassDef):
                walk(ch, f"{prefix}.{ch.name}" if prefix else ch.name)
            else:
                walk(ch, prefix)
    walk(tree, "")
    return out


def innermost(funcs, line):
    best = None
    for node, q in funcs:
        if node.lineno <= line <= (node.end_lineno or node.lineno):
            if best is None or node.lineno >= best[0].lineno:
                best = (node, q)
    return best


def docstring_nodes(tree):
    ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body:
            b = n.body[0]
            if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and isinstance(b.value.value, str):
                ids.add(id(b.value))
    return ids


def is_existence_use(src_line: str) -> bool:
    return bool(re.search(r"fetchone\(\)\s+is\s+(?:not\s+)?None|bool\([^)]*fetchone\(\)|\bnot\s+\w+\.fetchone\(\)|"
                          r"if\s+\w+\.fetchone\(\)\s*(?:else|:)|return\s+\w+\.fetchone\(\)\s+is", src_line))


def key_class(sql: str):
    """'unique-key:<table>(<cols>)' when the WHERE pins every column of a declared unique key by equality."""
    s = norm(sql)
    m = re.search(r"\bFROM\s+(?:[\w{}\"%]+\.)?\"?([\w{}]+)\"?(?:\s+(?:AS\s+)?(\w+))?", s, re.I)
    if not m:
        return None
    table = m.group(1).strip("{}").lower()
    w = re.search(r"\bWHERE\b(.*)", s, re.I | re.S)
    if not w or re.search(r"\bJOIN\b", s, re.I):
        return None
    where = w.group(1)
    if re.search(r"\bOR\b", where, re.I):
        return None
    eq = {c.lower().strip('"').split(".")[-1] for c in re.findall(r"([\w.\"]+)\s*=\s*(?:\?|:\w+|'[^']*'|\{[^{}]*\}|\d+)", where)}
    for k in UNIQUE_KEYS.get(table, []):
        if k <= eq:
            return f"unique-key:{table}({','.join(sorted(k))})"
    return None


def classify(sql: str, use_line: str = "") -> str:
    s = norm(sql)
    if ORDER.search(s):
        return "false-positive:order-by"
    if EXISTS.search(s) or (use_line and is_existence_use(use_line)) or re.search(r"\bWHERE\s+1\s*=\s*0\b|\bTOP\s+0\b", s, re.I):
        return "existence-only"
    if AGG_ONLY.search(s) and not GROUP.search(s) and re.search(r"^\s*SELECT\s+(?:COUNT|MAX|MIN|SUM|AVG|LIST)\s*\(", s, re.I):
        return "single-row-aggregate"
    k = key_class(s)
    if k:
        return k
    return "candidate"


def py_sites(rel: str, text: str):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    lines = text.splitlines()
    docs = docstring_nodes(tree)
    funcs = py_functions(tree)
    fobj = {}
    seen = set()
    # constants that are parts of an f-string whose whole text orders its rows
    ordered_parts = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            whole = "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}" for v in node.values)
            if ORDER.search(whole):
                ordered_parts |= {id(v) for v in node.values}
    literal_sites = []
    # rule prefix-literal (the original rule, docstrings kept so the original sites map 1:1)
    for node in ast.walk(tree):
        s = None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
        elif isinstance(node, ast.JoinedStr):
            s = "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}" for v in node.values)
        if s and PREFIX.search(s) and re.search(r"\bSELECT\b", s, re.I) and not ORDER.search(s):
            fq = innermost(funcs, node.lineno)
            key = (node.lineno, "prefix-literal")
            if key in seen:
                continue
            seen.add(key)
            auto = "false-positive:docstring" if id(node) in docs else (
                "false-positive:order-by-in-f-string" if id(node) in ordered_parts else (
                    "existence-only" if EXISTS.search(s) else classify(s)))
            literal_sites.append({"file": rel, "line": node.lineno, "rule": "prefix-literal",
                                  "function": fq[1] if fq else None, "sql": norm(s)[:220], "auto": auto,
                                  "_text": norm(s)})
    rendered = []   # (function, rendered statement) of every execute call
    # rules prefix-split and first-row, per execute call
    for fnode, q in funcs:
        f = fobj.setdefault(q, Fn(fnode, q))
        calls = []
        for n in ast.walk(fnode):
            if isinstance(n, ast.Call) and n.args:
                nm = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                if nm in EXEC_NAMES:
                    calls.append(n)
        calls.sort(key=lambda n: n.lineno)
        fetches = []
        for n in ast.walk(fnode):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "fetchone":
                fetches.append(n.lineno)
            if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) \
                    and n.value.func.attr == "fetchall" and isinstance(n.slice, ast.Constant) and n.slice.value == 0:
                fetches.append(n.lineno)
        for i, c in enumerate(calls):
            if innermost(funcs, c.lineno)[1] != q:
                continue  # owned by a nested function
            sql = f.render(c.args[0], c.lineno) or ""
            rendered.append((q, norm(sql)))
            if not re.search(r"\bSELECT\b", sql, re.I):
                continue
            nxt = calls[i + 1].lineno if i + 1 < len(calls) else (fnode.end_lineno or c.lineno) + 1
            literal_prefix = False
            for sub in ast.walk(c.args[0]):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and PREFIX.search(sub.value) and re.search(r"\bSELECT\b", sub.value, re.I):
                    literal_prefix = True
            if isinstance(c.args[0], ast.Name):
                for ln, op, e in f.assign.get(c.args[0].id, []):
                    for sub in ast.walk(e):
                        if isinstance(sub, (ast.Constant, ast.JoinedStr)):
                            st = sub.value if isinstance(sub, ast.Constant) else "".join(
                                v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}" for v in sub.values)
                            if isinstance(st, str) and PREFIX.search(st) and re.search(r"\bSELECT\b", st, re.I):
                                literal_prefix = True
            if PREFIX_ANY.search(sql) and not ORDER.search(sql) and not literal_prefix:
                key = (c.lineno, "prefix-split")
                if key not in seen:
                    seen.add(key)
                    yield {"file": rel, "line": c.lineno, "rule": "prefix-split", "function": q, "sql": norm(sql)[:220],
                           "auto": classify(sql)}
            for fl in fetches:
                if c.lineno <= fl < nxt:
                    use = lines[fl - 1] if fl - 1 < len(lines) else ""
                    if ORDER.search(sql):
                        break
                    auto = classify(sql, use)
                    key = (fl, "first-row")
                    if key not in seen:
                        seen.add(key)
                        yield {"file": rel, "line": fl, "rule": "first-row", "function": q, "execute_line": c.lineno,
                               "sql": norm(sql)[:220], "auto": auto}
                    break
        # py-slice-cut: a list read from an unordered SELECT (or a set) is cut by a slice with a bound
        for n in ast.walk(fnode):
            if not (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice) and n.slice.upper is not None
                    and isinstance(n.value, ast.Name)):
                continue
            if innermost(funcs, n.lineno)[1] != q:
                continue
            src = [x for x in f.assign.get(n.value.id, []) if x[0] <= n.lineno]
            if not src:
                continue
            seg = ast.unparse(src[-1][2]) if hasattr(ast, "unparse") else ""
            from_set = bool(re.search(r"\b(?:list\()?set\(", seg)) and not re.match(r"\s*sorted\(", seg)
            from_rows = "fetchall()" in seg
            if not (from_set or from_rows):
                continue
            prior = [c for c in calls if c.lineno <= src[-1][0]]
            sql = norm(f.render(prior[-1].args[0], prior[-1].lineno) or "") if prior else ""
            if from_rows and (not sql or ORDER.search(sql)):
                continue
            key = (n.lineno, "py-slice-cut")
            if key in seen:
                continue
            seen.add(key)
            yield {"file": rel, "line": n.lineno, "rule": "py-slice-cut", "function": q,
                   "sql": (sql or seg)[:220], "auto": "candidate", "source": "set" if from_set else "rows"}
    yield from _fix_literals(literal_sites, rendered)


def _fix_literals(literal_sites, rendered):
    for ls in literal_sites:
        t = ls.pop("_text")
        if ls["auto"] == "candidate":
            frag = t.replace("{}", "").strip()[:40]
            for q, sql in rendered:
                if q == ls["function"] and frag and frag in sql.replace("{}", "") and ORDER.search(sql):
                    ls["auto"] = "false-positive:order-by-in-assembled-statement"
                    break
        yield ls


# --------------------------------------------------------------------------------------------- ObjectScript

def _code(line: str) -> str:
    if line.lstrip().startswith("///"):
        return ""
    out, inq, i = [], False, 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            inq = not inq
        elif not inq and line.startswith("//", i):
            break
        out.append(ch)
        i += 1
    return "".join(out)


def cls_methods(lines):
    out, cur, start = [], None, 0
    for i, line in enumerate(lines, 1):
        m = re.match(r"\s*(?:Class)?Method\s+(\w+)|\s*Query\s+(\w+)", line)
        if m:
            if cur:
                out.append((cur, start, i - 1))
            cur, start = m.group(1) or m.group(2), i
    if cur:
        out.append((cur, start, len(lines)))
    return out


def method_of(methods, line):
    for n, a, b in methods:
        if a <= line <= b:
            return n
    return None


def _stmt_before(body_lines):
    """The SQL text of the last statement-building line before a loop: every literal on that Set line and on the
    lines that append to the same variable (`Set tSQL = tSQL_"..."`) up to the loop, joined."""
    idx = None
    for k in range(len(body_lines) - 1, -1, -1):
        if re.search(r'"[^"]*\bSELECT\b', body_lines[k], re.I):
            idx = k
            break
    if idx is None:
        return ""
    var = re.search(r"\bSet\s+(\w+)\s*=", body_lines[idx])
    parts = [body_lines[idx]]
    for bl in body_lines[idx + 1:]:
        if var and re.search(r"\b" + re.escape(var.group(1)) + r"\s*=\s*" + re.escape(var.group(1)) + r"\s*_", bl):
            parts.append(bl)
    lits = [m.group(1) for p in parts for m in re.finditer(r'"((?:[^"]|"")*)"', p)]
    sql = norm(" ".join(lits).replace('""', '"'))
    i = sql.upper().find("SELECT")
    return sql[i:] if i >= 0 else ""


def cls_sites(rel: str, text: str):
    lines = text.splitlines()
    methods = cls_methods(lines)
    cls = rel.replace("iris_src/src/", "").replace("/", ".").removesuffix(".cls")
    # prefix-literal (original rule)
    for i, line in enumerate(lines, 1):
        if PREFIX.search(line) and re.search(r"\bSELECT\b", line, re.I):
            window = " ".join(lines[i - 1:i + 4])
            if not ORDER.search(window):
                auto = "false-positive:doc-comment" if line.lstrip().startswith("///") else (
                    "existence-only" if EXISTS.search(line) else classify(norm(line[line.upper().find("SELECT"):])))
                yield {"file": rel, "line": i, "rule": "prefix-literal", "function": f"{cls}.{method_of(methods, i)}",
                       "sql": norm(line)[:220], "auto": auto}
    # os-first-row: embedded single-row SELECT INTO outside a cursor
    i = 0
    while True:
        i = text.find("&sql(", i)
        if i < 0:
            break
        depth, j, inq = 0, i + 4, False
        while j < len(text):
            ch = text[j]
            if ch == "'":
                inq = not inq
            elif not inq:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        body = text[i + 5:j]
        ln = text[:i].count("\n") + 1
        if re.match(r"\s*SELECT\b", body, re.I) and re.search(r"\bINTO\s*:", body, re.I):
            s = norm(body)
            # the INTO list is not part of the key test; drop it for classification
            s_cls = re.sub(r"\bINTO\s+(?::\w+\s*,?\s*)+", " ", s, flags=re.I)
            auto = classify(s_cls)
            if re.match(r"\s*SELECT\s+1\s+INTO\b", s, re.I):
                auto = "existence-only"
            yield {"file": rel, "line": ln, "rule": "os-first-row", "function": f"{cls}.{method_of(methods, ln)}",
                   "sql": s[:220], "auto": auto}
        i = j
    # os-first-row: dynamic statement read with one `If rs.%Next()`
    for n, a, b in methods:
        body_lines = lines[a - 1:b]
        body = "\n".join(_code(x) for x in body_lines)
        for m in re.finditer(r"\bIf\s+'?\(?\s*(\w+)\.%Next\(", body):
            var = m.group(1)
            ln = a + body[:m.start()].count("\n")
            # the statement text: the closest preceding %ExecDirect/%Prepare/%New query text in the method
            sql = _stmt_before(body[:m.start()].split("\n"))
            if not sql:
                continue
            if ORDER.search(sql):
                continue
            yield {"file": rel, "line": ln, "rule": "os-first-row", "function": f"{cls}.{n}", "sql": sql[:220],
                   "auto": classify(sql)}
    # os-cursor-alloc: a result-set loop without ORDER BY whose body allocates identities in iteration order
    for n, a, b in methods:
        body_lines = [_code(x) for x in lines[a - 1:b]]
        for k, bl in enumerate(body_lines):
            m = re.search(r"\bWhile\s+(\w+)\.%Next\(", bl)
            if not m:
                continue
            sql = _stmt_before(body_lines[:k])
            if not sql:
                continue
            loop = "\n".join(body_lines[k:k + 25])
            if not ORDER.search(sql) and re.search(r"\$I(?:ncrement)?\(|\bAlloc\w*\(", loop):
                ln = a + k
                yield {"file": rel, "line": ln, "rule": "os-cursor-alloc", "function": f"{cls}.{n}", "sql": sql[:220],
                       "auto": "candidate"}
    # os-cutoff: a loop that stops at a count
    for i, line in enumerate(lines, 1):
        c = _code(line)
        if_cut = re.search(r"\bIf\s*\(?\s*\(?\s*\+?\w+\s*>=\s*\+?[A-Za-z_.%#]+[^=]*\)?\s*(?:Quit|\{|\|\|)", c)
        if if_cut and not c.lstrip().startswith("///"):
            ctx = "\n".join(_code(x) for x in lines[max(0, i - 15):i])
            kind = "cursor" if re.search(r"FETCH|%Next\(", ctx, re.I) else ("$order" if re.search(r"\$O(?:rder)?\(", ctx, re.I) else "other")
            yield {"file": rel, "line": i, "rule": "os-cutoff", "function": f"{cls}.{method_of(methods, i)}",
                   "sql": norm(c)[:220], "loop": kind, "auto": "collation-ordered" if kind == "$order" else "candidate"}
            continue
        if re.search(r"\b(?:Quit|Q)\s*:\s*\(?\s*\w+\s*(?:>=|>|'<)\s*[\w.$()]+", c, re.I) and \
                re.search(r"(?:Count|count|cnt|Cnt|tN\b|tNum|tSeen|tRows|tOut|tCount|n\b|tI\b|tK\b|tTaken|tFound|processed)", c):
            ctx = "\n".join(_code(x) for x in lines[max(0, i - 15):i])
            kind = "cursor" if re.search(r"FETCH|%Next\(", ctx, re.I) else ("$order" if re.search(r"\$O(?:rder)?\(", ctx, re.I) else "other")
            auto = "collation-ordered" if kind == "$order" else ("candidate" if kind == "cursor" else "candidate")
            yield {"file": rel, "line": i, "rule": "os-cutoff", "function": f"{cls}.{method_of(methods, i)}",
                   "sql": norm(c)[:220], "loop": kind, "auto": auto}


# --------------------------------------------------------------------------------------------- modules

class Modules:
    def __init__(self):
        inv = json.loads(INVENTORY.read_text())
        self.files = {f["file"]: f.get("owners", []) for f in inv["files"]}
        self.entries = {}
        for e in inv["entries"]:
            self.entries.setdefault(e["file"], []).append(e)

    def of(self, rel, line, function):
        best = None
        for e in self.entries.get(rel, []):
            if e.get("line") and e.get("end") and e["line"] <= line <= e["end"] and e.get("owners"):
                if best is None or (e["end"] - e["line"]) < (best["end"] - best["line"]):
                    best = e
        if best:
            return sorted(best["owners"]), f"inventory entry {best['name']} ({rel}:{best['line']}-{best['end']})"
        if function:
            short = function.split(".")[-1]
            for e in self.entries.get(rel, []):
                if e.get("name", "").split(".")[-1] == short and e.get("owners"):
                    return sorted(e["owners"]), f"inventory entry {e['name']} (by name)"
        return sorted(self.files.get(rel, [])), "file owners (inventory files)"


def product_files():
    for root in ("iris_vector_graph", "api", "src"):
        for p in sorted((REPO / root).rglob("*.py")):
            yield p, p.read_text(errors="replace")
    for root in ("iris_src/src", "src"):
        for p in sorted((REPO / root).rglob("*.cls")):
            yield p, p.read_text(errors="replace")


def scan(files, modules=None):
    out = []
    for p, text in files:
        rel = str(p.relative_to(REPO)) if p.is_absolute() else str(p)
        gen = py_sites(rel, text) if rel.endswith(".py") else cls_sites(rel, text)
        for s in gen:
            if modules:
                s["modules"], s["module_basis"] = modules.of(rel, s["line"], s.get("function"))
            out.append(s)
    out.sort(key=lambda s: (s["file"], s["line"], s["rule"]))
    return out


ALLOWED = ("false-positive", "existence-only", "single-row-aggregate", "unique-key", "collation-ordered",
           "documented-sample", "set-valued", "order-irrelevant", "finding:")


def site_key(s):
    return f"{s['file']}:{s['line']}:{s['rule']}"


def gate(sites, disp, wanted, repo=REPO):
    """Every site of a wanted module needs an auto class that decides it or a disposition; dispositions must cite
    existing lines whose text contains the anchor."""
    problems, decided = [], []
    cache = {}

    def line_text(f, n):
        if f not in cache:
            p = repo / f
            cache[f] = p.read_text(errors="replace").splitlines() if p.exists() else []
        L = cache[f]
        return L[n - 1] if 0 < n <= len(L) else None
    for s in sites:
        mods = s.get("modules") or []
        primary = s.get("module")
        if not (set(mods) & wanted) and primary not in wanted:
            continue
        d = disp.get(site_key(s))
        if d is None:
            if s["auto"] == "candidate":
                problems.append({"site": site_key(s), "problem": "no disposition", "sql": s["sql"][:120]})
            else:
                decided.append({**s, "disposition": s["auto"], "basis": "automatic (statement text)"})
            continue
        cls = d.get("class", "")
        if not cls.startswith(ALLOWED):
            problems.append({"site": site_key(s), "problem": f"class {cls!r} not allowed"})
            continue
        bad = []
        for c in d.get("cite", []):
            m = re.match(r"(.+?):(\d+)(?:-(\d+))?$", c)
            if not m:
                bad.append(c)
                continue
            f, a = m.group(1), int(m.group(2))
            if line_text(f, a) is None:
                bad.append(c)
        anchor = d.get("anchor")
        if anchor:
            lt = line_text(s["file"], s["line"]) or ""
            near = " ".join(line_text(s["file"], n) or "" for n in range(max(1, s["line"] - 3), s["line"] + 4))
            if anchor not in lt and anchor not in near:
                bad.append(f"anchor {anchor!r} not at {s['file']}:{s['line']}")
        if bad:
            problems.append({"site": site_key(s), "problem": "stale citation", "bad": bad})
            continue
        decided.append({**s, "disposition": cls, "basis": d.get("reason", ""), "cite": d.get("cite", []),
                        "module": d.get("module", primary)})
    return problems, decided


def self_test() -> int:
    seeded = [
        (Path("t_lit.py"), 'a = "SELECT TOP 1 id FROM t WHERE g = ?"\nb = "SELECT TOP 1 id FROM t ORDER BY id"\n'),
        (Path("t_split.py"),
         "def f(cur, limit, key):\n"
         "    top = f'TOP {int(limit)} ' if limit else ''\n"
         "    sql = f'SELECT {top}s FROM {T} WHERE k = ?'\n"
         "    cur.execute(sql, [key])\n"
         "    return cur.fetchall()\n"
         "def g(cur, limit):\n"
         "    top = f'TOP {int(limit)} ' if limit else ''\n"
         "    sql = f'SELECT {top}s FROM {T} WHERE k = ? ORDER BY s'\n"
         "    cur.execute(sql)\n"
         "    return cur.fetchall()\n"),
        (Path("t_first.py"),
         "def h(cur, label):\n"
         "    cur.execute('SELECT s FROM Graph_KG.rdf_labels WHERE label = ?', [label])\n"
         "    return cur.fetchone()[0]\n"
         "def k(cur, n, g):\n"
         "    cur.execute('SELECT val FROM Graph_KG.nodes WHERE node_id = ? AND graph_id = ?', [n, g])\n"
         "    return cur.fetchone()\n"
         "def e(cur):\n"
         "    cur.execute('SELECT s FROM Graph_KG.rdf_labels WHERE label = ?', ['x'])\n"
         "    return cur.fetchone() is not None\n"),
        (Path("t_slice.py"),
         "def p(cur, off, lim):\n"
         "    cur.execute('SELECT s FROM Graph_KG.rdf_labels WHERE label = ?', ['Q'])\n"
         "    ids = [r[0] for r in cur.fetchall()]\n"
         "    return ids[off:off + lim]\n"
         "def q(cur, xs, k):\n"
         "    ids = sorted(set(xs))\n"
         "    return ids[:k]\n"),
        (Path("iris_src/src/T/D.cls"),
         "Class T.D\n{\nClassMethod A(pId) As %String\n{\n"
         " Set tRS = ##class(%SQL.Statement).%ExecDirect(, \"SELECT s FROM Graph_KG.rdf_edges WHERE o_id = ?\", pId)\n"
         " While tRS.%Next() { Set tN = $Increment(^X(\"n\")) }\n"
         " Quit 1\n}\n"
         "ClassMethod B(pId) As %String\n{\n"
         " Set tRS = ##class(%SQL.Statement).%ExecDirect(, \"SELECT s FROM Graph_KG.rdf_edges WHERE o_id = ? ORDER BY s\", pId)\n"
         " While tRS.%Next() { Set tN = $Increment(^X(\"n\")) }\n"
         " Quit 1\n}\n"
         "ClassMethod C(pB) As %String\n{\n"
         " Set tRS = ##class(%SQL.Statement).%ExecDirect(, \"SELECT s FROM Graph_KG.rdf_edges\")\n"
         " Set tN = 0\n"
         " While tRS.%Next() {\n"
         "  Set tN = tN + 1\n"
         "  If (tN >= pB) Quit\n"
         " }\n"
         " Quit 1\n}\n}\n"),
        (Path("iris_src/src/T/C.cls"),
         "Class T.C\n{\nClassMethod A(pG) As %String\n{\n"
         " &sql(SELECT table_name INTO :t FROM Graph_KG.embedding_registry WHERE graph_id = :pG)\n"
         " Quit t\n}\n"
         "ClassMethod B(pG) As %String\n{\n"
         " &sql(SELECT table_name INTO :t FROM Graph_KG.embedding_registry WHERE graph_id = :pG AND table_name = 'x')\n"
         " Quit t\n}\n}\n"),
    ]
    r = scan(seeded)
    got = {(Path(s["file"]).name, s["line"], s["rule"], s["auto"]) for s in r}
    expect_flag = {("t_lit.py", 1, "prefix-literal"), ("t_split.py", 4, "prefix-split"), ("t_first.py", 3, "first-row"),
                   ("C.cls", 5, "os-first-row"), ("t_slice.py", 4, "py-slice-cut"), ("D.cls", 6, "os-cursor-alloc"),
                   ("D.cls", 21, "os-cutoff")}
    flagged = {(a, b, c) for a, b, c, d in got if d == "candidate"}
    ok_flag = expect_flag <= flagged
    # not flagged as candidates: the ordered literal (line 2), the ordered split statement (g), the unique-key
    # read (k), the existence read (e), and the unique-key embedded select (B)
    not_flag = {("t_lit.py", 2), ("t_split.py", 9), ("t_first.py", 6), ("t_first.py", 9), ("C.cls", 10),
                ("t_slice.py", 7), ("D.cls", 12)}
    ok_not = not ({(a, b) for a, b, c in flagged} & not_flag)
    # gate: one undisposed candidate fails, a disposed one passes, a stale disposition fails
    sites = [dict(s, modules=["99"]) for s in r if s["auto"] == "candidate"]
    probs, _ = gate(sites, {}, {"99"}, repo=Path("/nonexistent"))
    ok_gate_undisposed = len(probs) == len(sites) > 0
    disp = {site_key(s): {"class": "order-irrelevant", "cite": [], "reason": "seeded"} for s in sites}
    probs2, _ = gate(sites, disp, {"99"}, repo=Path("/nonexistent"))
    ok_gate_disposed = not probs2
    stale = dict(disp)
    k0 = next(iter(stale))
    stale[k0] = {"class": "order-irrelevant", "cite": ["iris_vector_graph/engine.py:999999"], "reason": "stale"}
    probs3, _ = gate(sites, stale, {"99"})
    ok_gate_stale = len(probs3) == 1 and probs3[0]["problem"] == "stale citation"
    bad_cls = dict(disp)
    bad_cls[k0] = {"class": "looks-fine", "cite": [], "reason": "x"}
    probs4, _ = gate(sites, bad_cls, {"99"}, repo=Path("/nonexistent"))
    ok_gate_cls = len(probs4) == 1
    res = {"flagged_expected": ok_flag, "not_flagged_expected": ok_not, "gate_undisposed_fails": ok_gate_undisposed,
           "gate_disposed_passes": ok_gate_disposed, "gate_stale_citation_fails": ok_gate_stale,
           "gate_unknown_class_fails": ok_gate_cls, "sites": sorted(got)}
    ok = all(v for k, v in res.items() if k != "sites")
    print("self-test", "PASS" if ok else "FAIL", json.dumps(res, indent=1, default=str))
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    mods = Modules()
    sites = scan(product_files(), mods)
    out = {"pin_repo": str(REPO), "sites": sites}
    by = {}
    for s in sites:
        by.setdefault(s["rule"], {}).setdefault(s["auto"].split(":")[0], 0)
        by[s["rule"]][s["auto"].split(":")[0]] += 1
    out["by_rule"] = by
    rc = 0
    if "--dispositions" in sys.argv:
        dp = json.loads(Path(sys.argv[sys.argv.index("--dispositions") + 1]).read_text())
        wanted = set(sys.argv[sys.argv.index("--modules") + 1].split(","))
        disp = dp["dispositions"]
        for s in sites:
            d = disp.get(site_key(s))
            if d and d.get("module"):
                s["module"] = d["module"]
        problems, decided = gate(sites, disp, wanted)
        out.update({"modules_gated": sorted(wanted), "problems": problems, "decided": decided})
        per = {}
        for d in decided:
            m = d.get("module") or ",".join(d.get("modules") or [])
            per.setdefault(m, {}).setdefault(d["disposition"].split(":")[0] if not d["disposition"].startswith("finding") else d["disposition"], 0)
            per[m][d["disposition"].split(":")[0] if not d["disposition"].startswith("finding") else d["disposition"]] += 1
        out["per_module"] = per
        unused = sorted(set(disp) - {site_key(s) for s in sites})
        out["unused_dispositions"] = unused
        if problems or unused:
            rc = 1
        print(f"gate: {len(decided)} decided, {len(problems)} problems, {len(unused)} unused dispositions")
        for p in problems[:80]:
            print("  PROBLEM", json.dumps(p)[:260])
    print(f"{len(sites)} sites by rule/auto: {json.dumps(by)}")
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, indent=1))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
