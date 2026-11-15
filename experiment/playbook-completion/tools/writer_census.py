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

Review follow-up (R-02) extension: writes whose table or global name is built at run time.
- Python: f-strings, ``+`` concatenation, ``%`` and ``str.format`` are rendered into one text with each run-time part
  as a placeholder; a call with an IVG table name as a string argument (``self._t('nodes')``, ``_table('rdf_edges')``)
  renders as that table. A placeholder table (``{table}``) is resolved inside its function and module (constant
  assignment, ``for table in (<constants>)`` or a module tuple, defaults, one level of callers) and otherwise kept as
  ``unresolved``. Native API ``set/kill/increment`` with a non-literal global name is resolved the same way;
  ``RESOLVE_HINTS`` names the one allow-list a resolution relies on (restore_snapshot's).
- ObjectScript: string concatenation (``"INSERT INTO " _ pSchema _ ".nodes"``, ``"DELETE FROM " _ tStore``) rendered
  across continuation lines and resolved from the method's ``Set``/``For`` assignments and class parameters;
  indirection writes (``Set @ref``, ``Kill @ref``, ``Merge @ref``); file global loaders (``$System.OBJ.Load``);
  ``^IVG.Ledger("meta")`` (ledger state: Enable/Disable/SetStrict) as store ``state``. iris_src defines no ``$$$``
  macro of its own (no ``.inc``/``#define``); the ``$$$`` macros used are IRIS's status macros, none of which writes.
- Surfaces: a SQL write path that needs no product code because no trigger refuses it (ledger_revisions has
  UPDATE and DELETE triggers only) is listed as an external writer.
Docstrings and bare string statements are skipped, and sites are de-duplicated by (file, line, store, verb, table)
(the original walk counted an f-string's literal part and the f-string itself twice).
The self-test keeps the original two planted writers and adds planted dynamic writers (a Python f-string table, an
ObjectScript concatenated table, a Native API write with a variable global name) that must all be found.
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
               "redacting": "marker", "stmt": "stmt", "tuple": "stmt", "stmtNext": "stmt", "meta": "state"}
LEDGER_ALL = {"rec", "marker", "stmt", "idem", "idemRedacted", "redactedRev", "state"}
ANY = LEDGER_ALL | {"content", "meta"}
CONTENT = ("nodes", "rdf_labels", "rdf_props", "rdf_edges")
KNOWN_TABLES = CONTENT + ("ledger_revisions", "ledger_stats")
SQLW = re.compile(r"\b(INSERT\s+(?:OR\s+UPDATE\s+)?INTO|UPDATE|DELETE\s+FROM|TRUNCATE\s+TABLE)\s+([A-Za-z_%.{}\"]+)", re.I)
# rendered text: placeholders are {v:<name>} (a variable), {c:<name>} (a call), {?} (anything else)
SQLW_DYN = re.compile(r"\b(INSERT\s+(?:OR\s+UPDATE\s+)?INTO|UPDATE|DELETE\s+FROM|TRUNCATE\s+TABLE)\s+"
                      r"((?:[A-Za-z_%\"][\w%\"]*|\{[^{}]*\})(?:\.(?:[A-Za-z_%\"][\w%\"]*|\{[^{}]*\}))*)"
                      r"(?=\s*(?:\(|SET\b|WHERE\b|VALUES\b|SELECT\b|%|\{|$))")
GLW = re.compile(r"\b(?:Set|Kill|Merge|S|K|M)\s+\^IVG\.Ledger\(\s*\"(\w+)\"", re.I)
GLW_BARE = re.compile(r"\b(?:Kill|K)\s+\^IVG\.Ledger\b(?!\()", re.I)
GLW_IND = re.compile(r"\b(?:Set|Kill|Merge|S|K|M)\s+@(\.\.\w+|[\w.]+)", re.I)
GL_LOAD = re.compile(r"\$System\.OBJ\.Load\(", re.I)
GLOBAL_STORE = {"IVG.Ledger": "ledger-all", "Graph.KG.LedgerRevisionD": "meta", "Graph.KG.LedgerRevisionI": "meta"}
# The one resolution that needs knowledge outside the function: restore_snapshot passes f"^{gname}" for each archive
# member that restorable_globals() admits; the candidates are parsed from snapshot_globals() and
# ledger_storage_globals() in the same file (snapshot.py:360-422).
RESOLVE_HINTS = {("iris_vector_graph/_engine/snapshot.py", "_import_global_from_ndjson", "global_name"): "snapshot_allow_list"}


def expand(stores):
    out = set()
    for s in stores:
        out |= LEDGER_ALL if s == "ledger-all" else ANY if s == "any" else {s}
    return out


def table_store(name: str):
    n = name.strip('"').split(".")[-1].lower().replace("{", "").replace("}", "")
    for t in CONTENT:
        if n.endswith(t.lower()) or n == t:
            return "content"
    if "ledger_revisions" in n:
        return "meta"
    return None


def literal_table_store(name: str):
    """Store of a literal table token; None for a placeholder."""
    last = name.split(".")[-1].strip('"')
    if "{" in last:
        return None
    return table_store(last)


def global_store(name: str):
    n = name.lstrip("^")
    if n.startswith("||") or not n:
        return None
    if n in GLOBAL_STORE:
        return GLOBAL_STORE[n]
    if n.endswith(".LedgerRevisionD") or n.endswith(".LedgerRevisionI"):
        return "meta"
    return None


# ------------------------------------------------------------------------------------------------ ObjectScript

def _code(line: str) -> str:
    """The code part of an ObjectScript line: no // comment outside string literals, no /// doc line."""
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


LIT = re.compile(r'"(?:[^"]|"")*"')


def os_chains(stmt: str):
    """Rendered string-concatenation chains of one ObjectScript statement (literals joined with `_`)."""
    parts, last = [], 0
    for m in LIT.finditer(stmt):
        parts.append(("x", stmt[last:m.start()]))
        parts.append(("s", m.group(0)[1:-1].replace('""', '"')))
        last = m.end()
    parts.append(("x", stmt[last:]))
    chains, cur = [], None
    for i, (k, v) in enumerate(parts):
        if k == "s":
            cur = (cur or "") + v
            continue
        if cur is None:
            continue
        m_mid = re.fullmatch(r"\s*_\s*(.+?)\s*_\s*", v)
        nxt_is_lit = i + 1 < len(parts) and parts[i + 1][0] == "s"
        if re.fullmatch(r"\s*_\s*", v) and nxt_is_lit:
            continue
        if m_mid and nxt_is_lit:
            cur += "{v:" + m_mid.group(1).strip() + "}"
            continue
        m_tail = re.match(r"\s*_\s*([\w.#%]+(?:\([^()]*\))?)", v)
        if m_tail:
            cur += "{v:" + m_tail.group(1) + "}"
        chains.append(cur)
        cur = None
    if cur:
        chains.append(cur)
    return chains


def os_statements(text: str):
    """(first line, statement text) with continuation lines joined (a line ending in `_` or followed by `_ ...`)."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        start, s = i + 1, _code(lines[i])
        while i + 1 < len(lines):
            nxt = _code(lines[i + 1]).strip()
            if s.rstrip().endswith(" _") or s.rstrip().endswith("\t_") or nxt.startswith("_ "):
                s = s.rstrip() + " " + nxt
                i += 1
            else:
                break
        yield start, s
        i += 1


def os_methods(text: str):
    """[(name, start, end, body)] and class parameters {name: value}."""
    lines = text.splitlines()
    out, cur, start = [], None, 0
    params = {}
    for i, line in enumerate(lines, 1):
        p = re.match(r"\s*Parameter\s+(\w+)(?:\s+As\s+[\w%.]+)?\s*=\s*\"?([^\";]*)\"?\s*;", line)
        if p:
            params[p.group(1)] = p.group(2)
        m = re.match(r"\s*(?:Class)?Method\s+(\w+)", line)
        if m:
            if cur:
                out.append((cur, start, i - 1, "\n".join(lines[start - 1:i - 1])))
            cur, start = m.group(1), i
    if cur:
        out.append((cur, start, len(lines), "\n".join(lines[start - 1:])))
    return out, params


def os_resolve(var: str, body: str, params: dict, depth: int = 0):
    """Candidate table/global names a variable can hold, from the method's Set/For lines and class parameters.
    Returns (candidates, how)."""
    if var.startswith("..#"):
        v = params.get(var[3:])
        return ([v], "class parameter") if v else ([], "unresolved")
    cands = []
    for m in re.finditer(r"\bFor\s+" + re.escape(var) + r"\s*=\s*((?:\"[^\"]*\"\s*,?\s*)+)", body):
        cands += re.findall(r'"([^"]*)"', m.group(1))
    for m in re.finditer(r"\bSet\s+(?:[\w.]+\s*=[^,\n]*,\s*)*" + re.escape(var) + r"\s*=\s*([^\n]+)", body):
        rhs = m.group(1)
        lits = [c for c in os_chains(rhs) if c]
        for c in lits:
            cands.append(c)
        for pm in re.findall(r"\.\.#(\w+)", rhs):
            if pm in params:
                cands.append(params[pm])
        if not lits and depth < 2:
            ref = re.match(r"\s*([\w.#]+)\s*$", rhs)
            if ref and ref.group(1) != var:
                sub, _ = os_resolve(ref.group(1), body, params, depth + 1)
                cands += sub
    if not cands:
        # a $ListBuild of literals the variable is drawn from ($List(tStores, i)), or any table-like literal
        lits = re.findall(r'"((?:Graph_KG|\^)[\w.]+)"', body)
        cands = lits
        return (cands, "method literals") if cands else ([], "unresolved")
    return cands, "method Set/For"


def cls_sites(path: Path, text: str):
    methods, params = os_methods(text)

    def owner_of(line):
        best = ("?", "")
        for name, a, b, body in methods:
            if a <= line <= b:
                best = (name, body)
        return best
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
                yield i, method, store, s.strip()[:140], {"mechanism": "literal", "verb": "set/kill", "table": "^IVG.Ledger(" + g.group(1) + ")"}
        if GLW_BARE.search(s):
            yield i, method, "ledger-all", s.strip()[:140], {"mechanism": "literal", "verb": "kill", "table": "^IVG.Ledger"}
        for w in SQLW.finditer(s):
            store = table_store(w.group(2))
            if store:
                yield i, method, store, s.strip()[:140], {"mechanism": "literal", "verb": w.group(1).upper(), "table": w.group(2)}
    # run-time names
    for ln, stmt in os_statements(text):
        meth, body = owner_of(ln)
        for chain in os_chains(stmt):
            for w in SQLW_DYN.finditer(chain):
                tok = w.group(2)
                if "{" not in tok:
                    continue  # a literal table: the line rule above
                last = tok.split(".")[-1]
                if "{" not in last:
                    store = literal_table_store(last)
                    if store:
                        yield ln, meth, store, " ".join(chain.split())[:140], {"mechanism": "os-concat", "verb": w.group(1).upper(), "table": tok, "resolved": [last], "how": "literal table, run-time schema"}
                    continue
                var = last[3:-1] if last.startswith("{v:") else last
                cands, how = os_resolve(var, body, params)
                stores = sorted({st for c in cands for st in [table_store(c.split(".")[-1])] if st})
                if cands and not stores:
                    continue  # resolved to tables no invariant reads
                for st in stores or ["unresolved"]:
                    yield ln, meth, st, " ".join(chain.split())[:140], {"mechanism": "os-concat", "verb": w.group(1).upper(), "table": tok, "resolved": cands[:12], "how": how}
        for g in GLW_IND.finditer(stmt):
            var = g.group(1)
            cands, how = os_resolve(var, body, params)
            tables = [c for c in cands if not c.startswith("^")]
            globs = [c for c in cands if c.startswith("^")]
            stores = {table_store(t.split(".")[-1]) for t in tables} | {global_store(gn) for gn in globs}
            stores.discard(None)
            if not cands:
                # the reference comes from the caller: Native-API callable, any global (e.g. Snapshot.SetNodeJSON)
                derived = re.search(r"\bSet\s+" + re.escape(var) + r"\s*=\s*\.\.(\w+)\((p\w+)", body)
                if derived:
                    yield ln, meth, "any", stmt.strip()[:140], {"mechanism": "os-indirection", "verb": "set/kill/merge @", "table": var, "resolved": [], "how": f"name from parameter {derived.group(2)} via {derived.group(1)}"}
                continue
            for st in sorted(stores):
                yield ln, meth, st, stmt.strip()[:140], {"mechanism": "os-indirection", "verb": "set/kill/merge @", "table": var, "resolved": cands[:12], "how": how}
        if GL_LOAD.search(stmt):
            yield ln, meth, "any", stmt.strip()[:140], {"mechanism": "global-loader", "verb": "$System.OBJ.Load", "table": "*.gof", "resolved": [], "how": "loads any global the file names"}


# ------------------------------------------------------------------------------------------------ Python

def _is_tableish_call(node):
    """A call with an IVG table name as a string argument renders as that table (self._t('nodes'))."""
    if not isinstance(node, ast.Call):
        return None
    for a in node.args:
        if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.strip('"') in KNOWN_TABLES:
            return a.value.strip('"')
    return None


TABLE_WRAPPERS = {"_t", "_table", "_qualified", "qualify", "_q", "_tbl", "_qt"}
NON_INVARIANT_CALLS = ("registry", "quarantine", "staging", "route")


def _ph(expr) -> str:
    t = _is_tableish_call(expr)
    if t:
        return "{S}." + t
    if isinstance(expr, ast.Call) and expr.args:
        fname = expr.func.attr if isinstance(expr.func, ast.Attribute) else getattr(expr.func, "id", "")
        a0 = expr.args[0]
        if fname in TABLE_WRAPPERS and isinstance(a0, ast.Constant) and isinstance(a0.value, str):
            return "{S}." + a0.value
        if fname in TABLE_WRAPPERS and isinstance(a0, ast.Name):
            return "{v:" + a0.id + "}"
        if fname in TABLE_WRAPPERS and isinstance(a0, ast.Attribute):
            return "{v:" + a0.attr + "}"
    if isinstance(expr, ast.Name):
        return "{v:" + expr.id + "}"
    if isinstance(expr, ast.Attribute):
        return "{v:" + expr.attr + "}"
    if isinstance(expr, ast.Call):
        f = expr.func
        return "{c:" + (f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "?")) + "}"
    return "{?}"


def render(node):
    """Text of a string-building expression with run-time parts as placeholders; None when it is not one."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                out.append(v.value)
            elif isinstance(v, ast.FormattedValue):
                out.append(_ph(v.value))
        return "".join(out)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = render(node.left), render(node.right)
        if a is None and b is None:
            return None
        return (a if a is not None else _ph(node.left)) + (b if b is not None else _ph(node.right))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        a = render(node.left)
        if a is None:
            return None
        return re.sub(r"%(?:\(\w+\))?[sdr]", "{?}", a)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format"
            and isinstance(node.func.value, ast.Constant) and isinstance(node.func.value.value, str)):
        a = node.func.value.value
        kw = {k.arg: _ph(k.value) for k in node.keywords if k.arg}
        pos = [_ph(x) for x in node.args]

        def sub(m):
            key = m.group(1)
            if key == "":
                return pos.pop(0) if pos else "{?}"
            if key.isdigit():
                return pos[int(key)] if int(key) < len(pos) else "{?}"
            return kw.get(key, "{v:" + key + "}")
        return re.sub(r"\{(\w*)\}", sub, a)
    return None


NON_CONTENT_COLS = re.compile(r"\b(emb|metadata|mechanism|index_state|index_error|recall_measured|dimension|"
                              r"reifier_id|fhir_code|code_system_uri|wm_rsrc|source_table|model_key|declared_config)\b")


def non_content_shape(text: str, start: int) -> bool:
    """The statement after the table names a column that nodes/rdf_*/ledger_revisions do not have."""
    return bool(NON_CONTENT_COLS.search(text[start:start + 400]))


class PyModule:
    def __init__(self, rel: str, text: str):
        self.rel = rel
        self.tree = ast.parse(text)
        self.parent = {}
        for n in ast.walk(self.tree):
            for ch in ast.iter_child_nodes(n):
                self.parent[ch] = n
        self.funcs = [n for n in ast.walk(self.tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.module_consts = {}
        for st in self.tree.body:
            if isinstance(st, ast.Assign):
                for t in st.targets:
                    if isinstance(t, ast.Name):
                        self.module_consts[t.id] = st.value
            elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.value is not None:
                self.module_consts[st.target.id] = st.value

    def owner(self, line):
        """The outermost function holding the line: a nested helper is part of the function that defines it."""
        best = None
        for f in self.funcs:
            if f.lineno <= line <= getattr(f, "end_lineno", f.lineno):
                if best is None or f.lineno < best.lineno:
                    best = f
        return best

    def const_strings(self, node, depth=0):
        """String constants an expression (or a module name) stands for."""
        if node is None or depth > 3:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            out = []
            for e in node.elts:
                r = self.const_strings(e, depth + 1)
                if r is None:
                    return None
                out += r
            return out
        if isinstance(node, ast.Name) and node.id in self.module_consts:
            return self.const_strings(self.module_consts[node.id], depth + 1)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("frozenset", "tuple", "list", "set") and node.args:
            return self.const_strings(node.args[0], depth + 1)
        t = _is_tableish_call(node)
        if t:
            return [t]
        r = render(node) if not isinstance(node, ast.Name) else None
        if r is not None:
            return [r]
        return None

    def resolve(self, var: str, func, depth=0):
        """(candidates, how) for a variable inside a function (then the module)."""
        if depth > 2:
            return [], "unresolved"
        cands, how = [], None
        scope = func if func is not None else self.tree
        for n in ast.walk(scope):
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == var for t in n.targets):
                r = self.const_strings(n.value)
                if r:
                    cands += r
                    how = "assignment"
            if (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Tuple)
                    and isinstance(n.value, ast.Tuple) and len(n.value.elts) == len(n.targets[0].elts)):
                for t, v in zip(n.targets[0].elts, n.value.elts):
                    if isinstance(t, ast.Name) and t.id == var:
                        r = self.const_strings(v)
                        if r:
                            cands += r
                            how = "tuple assignment"
            if (isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.target, ast.Tuple)
                    and isinstance(n.iter, (ast.Tuple, ast.List))):
                names = [e.id if isinstance(e, ast.Name) else None for e in n.target.elts]
                if var in names:
                    i = names.index(var)
                    for row in n.iter.elts:
                        if isinstance(row, ast.Tuple) and len(row.elts) > i:
                            r = self.const_strings(row.elts[i])
                            if r:
                                cands += r
                                how = "loop over constant tuples"
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Tuple):
                names = [e.id if isinstance(e, ast.Name) else None for e in n.targets[0].elts]
                if var in names and isinstance(n.value, ast.Subscript) and isinstance(n.value.value, ast.Name):
                    dct = self.module_consts.get(n.value.value.id)
                    if isinstance(dct, ast.Dict):
                        i = names.index(var)
                        for v in dct.values:
                            if isinstance(v, ast.Tuple) and len(v.elts) > i:
                                r = self.const_strings(v.elts[i])
                                if r:
                                    cands += r
                                    how = "tuple unpacked from a module dict"
            if isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.target, ast.Name) and n.target.id == var:
                r = self.const_strings(n.iter)
                if r:
                    cands += r
                    how = "loop over constants"
        if cands:
            return cands, how
        if func is not None:
            args = func.args
            names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
            if var in names:
                pos = names.index(var)
                found = []
                for call in ast.walk(self.tree):
                    if isinstance(call, ast.Call):
                        fn = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
                        if fn != func.name:
                            continue
                        k = pos - (1 if names and names[0] in ("self", "cls") and isinstance(call.func, ast.Attribute) else 0)
                        arg = next((kw.value for kw in call.keywords if kw.arg == var), None)
                        if arg is None and 0 <= k < len(call.args):
                            arg = call.args[k]
                        r = self.const_strings(arg) if arg is not None else None
                        if r:
                            found += r
                return (found, "callers' constant arguments") if found else ([], "parameter")
        if var in self.module_consts:
            r = self.const_strings(self.module_consts[var])
            if r:
                return r, "module constant"
        return [], "unresolved"

    def is_docstring(self, node):
        p = self.parent.get(node)
        return isinstance(p, ast.Expr)

    def maximal(self, node):
        """True when node is a string expression not inside a larger one (no double counting)."""
        p = self.parent.get(node)
        if isinstance(p, ast.JoinedStr):
            return False
        if isinstance(p, ast.FormattedValue):
            return True
        if isinstance(p, ast.BinOp) and isinstance(p.op, (ast.Add, ast.Mod)) and render(p) is not None:
            return False
        if isinstance(p, ast.Attribute) and p.attr == "format":
            return False
        return True


def snapshot_allow_list(mod: PyModule):
    """Global names restore_snapshot admits: snapshot_globals() string constants plus ledger storage globals."""
    out = []
    for f in mod.funcs:
        if f.name == "snapshot_globals":
            for n in ast.walk(f):
                if isinstance(n, ast.Tuple) and n.elts and isinstance(n.elts[0], ast.Constant) and isinstance(n.elts[0].value, str):
                    out.append("^" + n.elts[0].value)
        if f.name == "ledger_storage_globals":
            out += ["^Graph.KG.LedgerRevisionD", "^Graph.KG.LedgerRevisionI", "^Graph.KG.LedgerStatsD"]
    return out


def py_sites(path: Path, text: str, rel: str = None):
    rel = rel or str(path)
    try:
        mod = PyModule(rel, text)
    except SyntaxError:
        return

    const_users = {}
    for st in mod.tree.body:
        if isinstance(st, (ast.Assign, ast.AnnAssign)):
            tgt = st.targets[0] if isinstance(st, ast.Assign) else st.target
            if isinstance(tgt, ast.Name):
                users = sorted({f.name for f in mod.funcs
                                if any(isinstance(n, ast.Name) and n.id == tgt.id for n in ast.walk(f))})
                for ln_ in range(st.lineno, getattr(st, "end_lineno", st.lineno) + 1):
                    const_users[ln_] = (tgt.id, users)

    def owner_name(line):
        f = mod.owner(line)
        if f:
            return f.name
        if line in const_users:
            name, users = const_users[line]
            return users[0] if len(users) == 1 else f"{name} (used by {', '.join(users) or 'nothing'})"
        return "?"
    # (function, placeholder) pairs whose statements write a non-content column somewhere in the function
    noncontent = set()
    for node in ast.walk(mod.tree):
        t = render(node) if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call)) else None
        if not t:
            continue
        f = mod.owner(getattr(node, "lineno", 0))
        for w in SQLW_DYN.finditer(t):
            last = w.group(2).split(".")[-1]
            if last.startswith("{v:") and non_content_shape(t, w.end()) and f is not None:
                noncontent.add((f.name, last[3:-1]))
    for node in ast.walk(mod.tree):
        s = render(node) if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call)) else None
        if s and not mod.is_docstring(node) and mod.maximal(node):
            ln = node.lineno
            for w in SQLW.finditer(s):
                tok = w.group(2)
                if "{" in tok.split(".")[-1]:
                    continue
                store = table_store(tok)
                if store:
                    mech = "py-table-call" if "{S}" in tok else "literal"
                    yield ln, owner_name(ln), store, " ".join(s.split())[:140], {"mechanism": mech, "verb": w.group(1).upper(), "table": tok}
            for w in SQLW_DYN.finditer(s):
                tok = w.group(2)
                last = tok.split(".")[-1]
                if "{" not in tok:
                    continue
                if "{" not in last:
                    store = literal_table_store(last)
                    if store and SQLW.search(s[w.start():w.end()]) and table_store(tok) == store and "{" not in tok.replace("{S}.", ""):
                        # rendered table call ({S}.nodes): a run-time schema with a fixed table
                        yield ln, owner_name(ln), store, " ".join(s.split())[:140], {"mechanism": "py-table-call", "verb": w.group(1).upper(), "table": tok, "resolved": [last], "how": "table-name argument"}
                    elif store:
                        yield ln, owner_name(ln), store, " ".join(s.split())[:140], {"mechanism": "py-format", "verb": w.group(1).upper(), "table": tok, "resolved": [last], "how": "literal table, run-time schema"}
                    continue
                if not (last.startswith("{v:") or last.startswith("{c:")):
                    continue
                var = last[3:-1]
                func = mod.owner(ln)
                if (func is not None and (func.name, var) in noncontent) or non_content_shape(s, w.end()):
                    continue  # an embedding/registry/reification table by its columns
                if last.startswith("{c:"):
                    cands, how = ([], "unresolved call")
                    if any(x in var.lower() for x in NON_INVARIANT_CALLS):
                        continue  # a named non-invariant table (registry, quarantine, staging, route)
                else:
                    cands, how = mod.resolve(var, func)
                stores = sorted({st for c in cands for st in [table_store(c.split(".")[-1])] if st})
                if cands and not stores:
                    continue
                for st in stores or ["unresolved"]:
                    yield ln, owner_name(ln), st, " ".join(s.split())[:140], {"mechanism": "py-dynamic-table", "verb": w.group(1).upper(), "table": tok, "resolved": cands[:12], "how": how}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("set", "kill", "increment"):
            gi = 0 if node.func.attr == "kill" else 1
            if len(node.args) <= gi:
                continue
            g = node.args[gi]
            if isinstance(g, ast.Constant):
                if g.value == "^IVG.Ledger":
                    subs = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                    store = next((LEDGER_SUBS[x] for x in subs if x in LEDGER_SUBS), "ledger-all")
                    yield node.lineno, owner_name(node.lineno), store, ast.unparse(node)[:140], {"mechanism": "literal", "verb": "native " + node.func.attr, "table": "^IVG.Ledger"}
                continue
            # a run-time global name
            func = mod.owner(node.lineno)
            fname = func.name if func else "?"
            if isinstance(g, ast.Starred):
                cands = mod.const_strings(g.value) or []
                how = "starred module constant"
                cands = cands[:1]
            elif isinstance(g, ast.Name):
                cands, how = mod.resolve(g.id, func)
                if any("{" in c for c in cands):  # a name built from another run-time part: not a constant
                    cands, how = [c for c in cands if "{" not in c], how + " (run-time part)"
                hint = RESOLVE_HINTS.get((rel, fname, g.id))
                if not cands and hint == "snapshot_allow_list":
                    cands, how = snapshot_allow_list(mod), "allow-list (RESOLVE_HINTS: restorable_globals)"
            else:
                cands, how = [], "unresolved expression"
            if fname in ("set", "kill", "increment") and fname == node.func.attr:
                continue  # the Native API adapter itself (host.py, embedded.py): its callers are the writers
            stores = {global_store(c) for c in cands}
            stores.discard(None)
            sub = node.args[gi + 1] if len(node.args) > gi + 1 else None
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and stores:
                # a fixed first subscript: ^IVG.Ledger only for its own subscripts, never a revision row
                stores = {LEDGER_SUBS[sub.value]} if ("ledger-all" in stores and sub.value in LEDGER_SUBS) else set()
                if not stores:
                    continue
            if cands and not stores:
                continue
            for st in sorted(stores) or ["unresolved"]:
                yield node.lineno, fname, st, ast.unparse(node)[:140], {"mechanism": "py-dynamic-global", "verb": "native " + node.func.attr, "table": ast.unparse(g)[:60], "resolved": cands[:16], "how": how}


# ------------------------------------------------------------------------------------------------ surfaces

def surfaces():
    """SQL write paths that need no product code: a table whose triggers do not refuse an event."""
    out = []
    p = REPO / "iris_src/src/Graph/KG/LedgerRevision.cls"
    text = p.read_text()
    events = {}
    for i, line in enumerate(text.splitlines(), 1):
        m = re.search(r"Trigger\s+(\w+)\s*\[\s*Event\s*=\s*([\w/]+)", line)
        if m:
            for ev in m.group(2).split("/"):
                events[ev.upper()] = f"{m.group(1)} (LedgerRevision.cls:{i})"
    if "INSERT" not in events:
        out.append({"file": "<any SQL client>", "line": 0, "owner": "INSERT INTO Graph_KG.ledger_revisions",
                    "store": "meta", "src": "no INSERT trigger; triggers: " + "; ".join(f"{k} {v}" for k, v in sorted(events.items())),
                    "plans": [], "via_call": [], "mechanism": "surface", "verb": "INSERT", "table": "Graph_KG.ledger_revisions"})
    return out


# ------------------------------------------------------------------------------------------------ plans / census

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


#: Callee names that are DB-API, container or protocol methods: following them by name would reach every package
#: function of that name (a plan's cursor.execute() reaching an unrelated execute(), a .run() reaching the 4.0.0
#: migration). Measured on the pin: only the 4.0.0 migration's three helpers were "reached" through one of these.
GENERIC_CALLEES = {"__enter__", "__exit__", "__init__", "call", "close", "commit", "cursor", "execute", "executemany",
                   "fetchall", "fetchone", "get", "items", "rollback", "run", "set", "tuple"}


def reachable_from_plans(meth, ps):
    """Plan name -> set of (file, method) reachable from the plan's code range (by callee name, transitively;
    Python callee names in GENERIC_CALLEES are not followed)."""
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
                if callee in GENERIC_CALLEES and not k[0].endswith(".cls"):
                    continue
                targets = by_name.get(callee, [])
                if not k[0].endswith(".cls"):
                    # a Python name defined in the caller's own file is that definition (restore_snapshot's nested
                    # _register_endpoints is not BulkLoader._register_endpoints)
                    local = [t for t in targets if t[0] == k[0]]
                    targets = local or targets
                for t in targets:
                    if t not in seen and (t[0].endswith(".cls") == k[0].endswith(".cls")):
                        seen.add(t)
                        todo.append(t)
        out[name] = seen
    return out


def census(files, with_surfaces=True):
    files = list(files)
    ps, d = plans()
    meth = call_graph(files)
    reach = reachable_from_plans(meth, ps)
    sites, seen = [], set()
    for path, text in files:
        rel = str(path.relative_to(REPO)) if path.is_absolute() else str(path)
        gen = cls_sites(path, text) if path.suffix == ".cls" else py_sites(path, text, rel)
        for line, owner, store, src, info in gen:
            key = (rel, line, store, info.get("verb"), re.sub(r"\{[^}]*\}", "{}", str(info.get("table"))))
            if key in seen:
                continue
            seen.add(key)
            cover = [n for n, f, a, b, w in ps if f == rel and a <= line <= b]
            via = sorted(n for n, r in reach.items() if (rel, owner) in r and n not in cover)
            sites.append({"file": rel, "line": line, "owner": owner, "store": store, "src": src, "plans": cover,
                          "via_call": via, **info})
    if with_surfaces:
        sites += surfaces()
    invs = d["invariants"]
    uncovered = [s for s in sites if not s["plans"] and not s["via_call"]]
    owners = {}
    for s in uncovered:
        owners.setdefault((s["file"], s["owner"]), set()).add(s["store"])
    obligations, conditional = [], []
    for (f, o), stores in sorted(owners.items()):
        definite = expand(stores - {"unresolved"})
        for inv, v in invs.items():
            hit = set(v["reads"]) & definite
            if hit:
                obligations.append({"invariant": inv, "writer": f"{f}::{o}", "stores": sorted(hit)})
            elif "unresolved" in stores and set(v["reads"]) & {"content", "meta"}:
                conditional.append({"invariant": inv, "writer": f"{f}::{o}",
                                    "stores": ["unresolved (if the run-time name is a content or ledger table)"]})
    # write-set gaps: a covered site writes a store its plan does not declare (restore_snapshot writing the marker)
    plan_writes = {n: w for n, _f, _a, _b, w in ps}
    gaps = {}
    for s in sites:
        if s["store"] == "unresolved":
            continue
        reaching = s["plans"] + s["via_call"]
        declared = set().union(*(plan_writes[n] for n in reaching)) if reaching else set()
        for st in sorted(expand({s["store"]}) - declared - {"state"}):
            # no plan that reaches this site declares the store it writes
            for n in reaching:
                gaps.setdefault((n, st), []).append(f"{s['file']}:{s['line']} {s['owner']}")
    gap_obligations = []
    for (n, st), where in sorted(gaps.items()):
        for inv, v in invs.items():
            if st in v["reads"]:
                gap_obligations.append({"invariant": inv, "plan": n, "undeclared_store": st,
                                        "pair_in_manifest_coverage": f"{inv}|{n}" in d["coverage"],
                                        "sites": sorted(set(where))[:6], "site_count": len(set(where))})
    mech = {}
    for s in sites:
        m = s.get("mechanism", "literal")
        e = mech.setdefault(m, {"sites": 0, "in_plan": 0, "via_call": 0, "outside": 0})
        e["sites"] += 1
        e["in_plan" if s["plans"] else "via_call" if s["via_call"] else "outside"] += 1
    ledger_outside = sorted({f"{s['file']}::{s['owner']}" for s in sites
                             if expand({s["store"]}) & (LEDGER_ALL | {"meta"}) and s["store"] != "unresolved"
                             and not any(s["file"].endswith(x) for x in ("Ledger.cls", "LedgerRedact.cls", "LedgerApply.cls",
                                                                         "LedgerGenesis.cls", "LedgerRevision.cls",
                                                                         "ledger/client.py", "ledger/replay.py"))})
    return {"sites": len(sites), "site_lines": len({(s["file"], s["line"]) for s in sites}), "covered_sites": len(sites) - len(uncovered), "uncovered_sites": len(uncovered),
            "inside_plan_ranges": sum(1 for s in sites if s["plans"]),
            "covered_via_call": sum(1 for s in sites if not s["plans"] and s["via_call"]),
            "uncovered_writers": sorted(f"{f}::{o}" for f, o in owners), "new_obligations": obligations,
            "conditional_obligations": conditional, "by_mechanism": mech,
            "plan_write_gaps": [{"plan": n, "undeclared_store": st, "site_count": len(set(w))} for (n, st), w in sorted(gaps.items())],
            "gap_obligations": gap_obligations,
            "ledger_writers_outside_ledger_classes": ledger_outside,
            "unresolved_sites": [f"{s['file']}:{s['line']} {s['owner']}" for s in sites if s["store"] == "unresolved"],
            "macros_checked": "iris_src defines no $$$ macro (no .inc, no #define); the $$$ macros used are IRIS status macros",
            "detail": sites}


def product_files():
    for p in sorted((REPO / "iris_src" / "src").rglob("*.cls")):
        yield p, p.read_text(errors="replace")
    for p in sorted((REPO / "iris_vector_graph").rglob("*.py")):
        yield p, p.read_text(errors="replace")


PLANTED_PY = '''
def planted_dynamic_writer(self, cursor, node_id, key, value):
    """A writer whose table name is built at run time: the original census could not see it."""
    cursor.execute(f"INSERT INTO {self._t('rdf_props')} (s, \\"key\\", val) VALUES (?, ?, ?)", [node_id, key, value])


def planted_global_writer(iris_obj, value):
    global_name = "^IVG.Ledger"
    iris_obj.set(value, global_name, "redacting")
'''
PLANTED_CLS = '''Class Graph.KG.StrayDyn
{
ClassMethod Y(pSchema As %String, pId As %String)
{
    Set tRS = ##class(%SQL.Statement).%ExecDirect(, "DELETE FROM " _ pSchema _ ".rdf_edges WHERE s = ?", pId)
}
}
'''


def main() -> int:
    if "--self-test" in sys.argv:
        covered = (REPO / "iris_src/src/Graph/KG/Ledger.cls", "\n" * 399 + '    Set ^IVG.Ledger("rec", 1, 1) = 1\n')
        stray = (REPO / "iris_src/src/Graph/KG/Stray.cls", 'ClassMethod X()\n{\n    Kill ^IVG.Ledger("stmt", 5)\n}\n')
        r = census([covered, stray], with_surfaces=False)
        ok = r["uncovered_writers"] == ["iris_src/src/Graph/KG/Stray.cls::X"] and r["covered_sites"] == 1
        print("self-test (original)", "PASS" if ok else "FAIL", r["uncovered_writers"], r["covered_sites"])
        planted_py = (REPO / "iris_vector_graph/_engine/zz_planted.py", PLANTED_PY)
        planted_cls = (REPO / "iris_src/src/Graph/KG/StrayDyn.cls", PLANTED_CLS)
        r2 = census([covered, stray, planted_py, planted_cls], with_surfaces=False)
        want = sorted(["iris_src/src/Graph/KG/Stray.cls::X", "iris_src/src/Graph/KG/StrayDyn.cls::Y",
                       "iris_vector_graph/_engine/zz_planted.py::planted_dynamic_writer",
                       "iris_vector_graph/_engine/zz_planted.py::planted_global_writer"])
        stores = {(s["owner"], s["store"]) for s in r2["detail"]}
        ok2 = (r2["uncovered_writers"] == want and r2["covered_sites"] == 1
               and ("planted_dynamic_writer", "content") in stores and ("Y", "content") in stores
               and ("planted_global_writer", "marker") in stores)
        print("self-test (planted dynamic writers)", "PASS" if ok2 else "FAIL", r2["uncovered_writers"], sorted(stores))
        # the original rules alone miss the planted f-string writer (the reason for the extension)
        return 0 if ok and ok2 else 1
    r = census(product_files())
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(r, indent=1))
    print(f"{r['sites']} writer sites; {r['inside_plan_ranges']} inside a declared plan's range; "
          f"{r['covered_via_call']} reached by call from a plan; {r['uncovered_sites']} outside")
    print(f"{len(r['uncovered_writers'])} writers no plan declares; {len(r['new_obligations'])} new (invariant, writer) "
          f"obligations; {len(r['conditional_obligations'])} conditional (unresolved run-time names)")
    print("by mechanism:", json.dumps(r["by_mechanism"]))
    print(f"{len(r['plan_write_gaps'])} (plan, undeclared store) write-set gaps; {len(r['gap_obligations'])} (invariant, plan) "
          f"obligations from them, {sum(1 for g in r['gap_obligations'] if not g['pair_in_manifest_coverage'])} of them pairs "
          f"the manifest's coverage does not list")
    print("ledger writers outside the ledger classes:", r["ledger_writers_outside_ledger_classes"])
    for w in r["uncovered_writers"]:
        print("  ", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
