"""Static source index of the product at the pin, shared by inventory.py and footprints.py (breadth lane A).

Reads only files of the repository (stdlib only, no IRIS). Two parsers:

- Python: `ast` over iris_vector_graph/**.py (and the few other loaders named below). Every function and method with
  its line range, the calls it makes (resolved where the target is a literal: self.<engine method>, self._store.<m>,
  module functions, imported names, Native API classMethodValue/Void/Object, _call_classmethod, host.call,
  _arno_call), the SQL text it holds (string constants and f-strings rendered with placeholders, module-level SQL
  constants it names, local aliases such as `props = self._t("rdf_props")`) and its transaction/lock markers.
- ObjectScript: a line scanner over iris_src/src/**.cls. Every ClassMethod/Method/Query with its keywords (SqlProc,
  SqlName, Language), line range, global references classified as read or write by command context (Set left of
  '=', Kill/ZKill, $Increment, Merge target, `Kill @` over a $Name), embedded and dynamic SQL text, LOCK commands,
  TSTART/TCOMMIT/TROLLBACK/$TLevel, and calls (##class(C).M, ..M, $classmethod).

This is a heuristic extraction, not a parser of either language's full grammar. footprints.py marks its output
`confidence: "extracted"` unless a hand review overrides it.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parents[5]
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"

# --------------------------------------------------------------------------------------------------------------------
# SQL text analysis
# --------------------------------------------------------------------------------------------------------------------
SQL_START = re.compile(r"^\s*(\(?\s*SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|WITH|CALL|GRANT|REVOKE|"
                       r"MERGE|SET\s+OPTION|START\s+TRANSACTION|COMMIT|ROLLBACK|LOCK\s+TABLE|UNLOCK)\b")
SQL_ANY = re.compile(r"\b(SELECT\b[\s\S]*\bFROM|INSERT\s+(OR\s+UPDATE\s+)?(%\w+\s+)*INTO|UPDATE\s+\S+\s+SET|"
                     r"DELETE\s+(%\w+\s+)*FROM|CREATE\s+(OR\s+REPLACE\s+)?(TABLE|INDEX|UNIQUE|VIEW|PROCEDURE|FUNCTION)|"
                     r"DROP\s+(TABLE|INDEX|VIEW|PROCEDURE|FUNCTION)|ALTER\s+TABLE|TRUNCATE\s+TABLE)\b")
_NAME = r'((?:"[^"]+"|[\w%{}<>?.$]+)(?:\s*\.\s*(?:"[^"]+"|[\w%{}<>?$]+))?)'
SQL_WRITE_PATTERNS = [
    ("insert", re.compile(r"\bINSERT(?:\{[^}]*\})?\s+(?:OR\s+UPDATE\s+)?(?:%\w+(?:\s+%\w+)*\s+)?INTO\s+" + _NAME, re.I)),
    ("update", re.compile(r"\bUPDATE\s+(?:%\w+(?:\s+%\w+)*\s+)?" + _NAME + r"\s+SET\b", re.I)),
    ("delete", re.compile(r"\bDELETE\s+(?:%\w+(?:\s+%\w+)*\s+)?FROM\s+" + _NAME, re.I)),
    ("truncate", re.compile(r"\bTRUNCATE\s+TABLE\s+(?:%\w+\s+)*" + _NAME, re.I)),
    ("ddl-drop", re.compile(r"\bDROP\s+(?:TABLE|VIEW|PROCEDURE|FUNCTION)\s+(?:IF\s+EXISTS\s+)?" + _NAME, re.I)),
    ("ddl-drop-index", re.compile(r"\bDROP\s+INDEX\s+(?:IF\s+EXISTS\s+)?" + _NAME + r"(?:\s+ON\s+(?:TABLE\s+)?" + _NAME + ")?", re.I)),
    ("ddl-create", re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|PROCEDURE|FUNCTION)\s+(?:IF\s+NOT\s+EXISTS\s+)?" + _NAME, re.I)),
    ("ddl-index", re.compile(r"\bCREATE\s+(?:UNIQUE\s+|BITMAP\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?\S+\s+ON\s+(?:TABLE\s+)?" + _NAME, re.I)),
    ("ddl-alter", re.compile(r"\bALTER\s+TABLE\s+" + _NAME, re.I)),
    ("grant", re.compile(r"\b(?:GRANT|REVOKE)\b[^;]*?\bON\s+(?:SCHEMA\s+|TABLE\s+|PROCEDURE\s+|FUNCTION\s+)?" + _NAME, re.I)),
]
SQL_READ_PATTERNS = [
    ("from", re.compile(r"\bFROM\s+(?:%\w+(?:\s+(?:\{[^}]*\}|[\w\"]+)\.[\w\"]+\.[\w\"]+)?\s+)*" + _NAME, re.I)),
    ("join", re.compile(r"\bJOIN\s+(?:%\w+(?:\s+(?:\{[^}]*\}|[\w\"]+)\.[\w\"]+\.[\w\"]+)?\s+)*" + _NAME, re.I)),
]
SQL_HINTS = {
    "%NOLOCK": re.compile(r"%NOLOCK", re.I),
    "%NOINDEX": re.compile(r"%NOINDEX", re.I),
    "%NOCHECK": re.compile(r"%NOCHECK", re.I),
    "%NOTRIGGER": re.compile(r"%NOTRIGGER", re.I),
    "%NOJOURN": re.compile(r"%NOJOURN", re.I),
    "FOR UPDATE": re.compile(r"\bFOR\s+UPDATE\b", re.I),
    "LOCK TABLE": re.compile(r"\bLOCK\s+TABLE\b", re.I),
    "%PROFILE": re.compile(r"%PROFILE", re.I),
}
SQL_TXN = {
    "START TRANSACTION": re.compile(r"\bSTART\s+TRANSACTION\b", re.I),
    "COMMIT": re.compile(r"^\s*COMMIT\b", re.I),
    "ROLLBACK": re.compile(r"^\s*ROLLBACK\b", re.I),
    "SET TRANSACTION": re.compile(r"\bSET\s+TRANSACTION\b", re.I),
}
SQL_ROUTINE_CALL = re.compile(r"\b(Graph_KG|\{[^}]*\})\s*\.\s*(kg_\w+|CY_\w+|JSON_\w+|[A-Za-z]\w*)\s*\(", re.I)
CLASS_IN_TEXT = re.compile(r"##class\(\s*([%\w.]+)\s*\)\s*\.\s*(%?\w+)")

SQL_KEYWORDS = {"SELECT", "WHERE", "AS", "ON", "SET", "VALUES", "TABLE", "(", "THE", "A", "AN", "TOP", "DISTINCT",
                "LATERAL", "UNNEST", "DUAL"}


def norm_table(raw: str) -> Optional[str]:
    """Normalize a table reference to 'Graph_KG.<table>' / 'catalog:<x>' / 'unqualified:<x>'; None for noise."""
    t = raw.strip().strip("(),;").replace('"', "").replace(" ", "")
    if not t or t.upper() in SQL_KEYWORDS or t.startswith("?") or t.startswith("("):
        return None
    if "." in t:
        schema, _, table = t.rpartition(".")
        su = schema.upper()
        if su.startswith("%DICTIONARY") or su == "%DICTIONARY" or su in ("INFORMATION_SCHEMA", "%SYS", "%SYSTEM"):
            return "catalog:" + t
        if su.startswith("%") or su.startswith("%IFIND"):
            return "catalog:" + t
        if su in ("SQLUSER",):
            return "SQLUser." + table
        if not table:
            return None
        # placeholders and the default IVG schema all normalize to Graph_KG (ADR-0016: one schema per namespace)
        if su in ("GRAPH_KG",) or "{" in schema or "<" in schema or schema in ("?",):
            return "Graph_KG." + table
        return schema + "." + table
    if t.upper() in ("DUAL",):
        return None
    if "{" in t or "<" in t:
        return "Graph_KG.<dynamic:" + t.strip("{}<>") + ">"
    if re.fullmatch(r"[A-Za-z_]\w*", t):
        if t.upper() in SQL_KEYWORDS:
            return None
        return "unqualified:" + t
    return None


def looks_like_sql(text: str) -> bool:
    if SQL_START.search(text):
        return True
    return bool(SQL_ANY.search(text)) and text.upper() != text.lower()


def sql_effects(text: str) -> Dict[str, List[Tuple[str, str]]]:
    """{'writes': [(op, table)], 'reads': [(op, table)], 'hints': [...], 'txn': [...], 'routines': [...],
    'classcalls': [(cls, m)]} for one SQL text (with placeholders)."""
    out: Dict[str, list] = {"writes": [], "reads": [], "hints": [], "txn": [], "routines": [], "classcalls": []}
    if not looks_like_sql(text):
        return out
    write_spans = []
    for op, rx in SQL_WRITE_PATTERNS:
        for m in rx.finditer(text):
            groups = [g for g in m.groups() if g]
            tgt = groups[-1] if op == "ddl-drop-index" and len(groups) > 1 else groups[0]
            if op == "ddl-drop-index" and len(groups) == 1:
                # DROP INDEX name with no ON: the index name alone (resolved in the default schema, P-0112)
                out["writes"].append((op, "index:" + groups[0].replace('"', "")))
                write_spans.append(m.span())
                continue
            nt = norm_table(tgt)
            if nt:
                kind = op
                if op in ("ddl-drop", "ddl-create") and re.search(r"\b(PROCEDURE|FUNCTION)\b", m.group(0), re.I):
                    nt = "routine:" + nt.split(":", 1)[-1]
                    kind = op + "-routine"
                elif op in ("ddl-drop", "ddl-create") and re.search(r"\bVIEW\b", m.group(0), re.I):
                    nt = "view:" + nt.split(":", 1)[-1]
                out["writes"].append((kind, nt))
                if op == "delete":
                    write_spans.append((m.start(), m.end()))
    for op, rx in SQL_READ_PATTERNS:
        for m in rx.finditer(text):
            if any(a <= m.start() < b for a, b in write_spans):
                continue
            nt = norm_table(m.group(1))
            if nt and not nt.startswith("unqualified:") or (nt and re.search(r"\bSELECT\b", text, re.I)):
                out["reads"].append((op, nt))
    for name, rx in SQL_HINTS.items():
        if rx.search(text):
            out["hints"].append(name)
    if re.search(r"\bINSERT\{[^}]*hint[^}]*\}", text, re.I):
        out["hints"].append("%NOINDEX? (runtime hint placeholder)")
    for name, rx in SQL_TXN.items():
        if rx.search(text):
            out["txn"].append(name)
    for m in SQL_ROUTINE_CALL.finditer(text):
        name = m.group(2)
        if name.upper() in ("VALUES", "IN", "EXISTS", "COUNT", "MAX", "MIN", "SUM", "AVG", "COALESCE"):
            continue
        out["routines"].append("Graph_KG." + name)
    for m in CLASS_IN_TEXT.finditer(text):
        out["classcalls"].append((m.group(1), m.group(2)))
    return out


# --------------------------------------------------------------------------------------------------------------------
# Python
# --------------------------------------------------------------------------------------------------------------------
NATIVE_CALLS = {"classMethodValue", "classMethodVoid", "classMethodObject", "classMethodString", "classMethodInteger",
                "classMethodBoolean", "classMethodBytes"}
HOST_CALLS = {"_call_classmethod", "_call_classmethod_large", "_arno_call", "call_large", "_classmethod"}
TXN_NAMES = {"WriteTxn", "write_txn", "_write_txn", "ReadTxn", "caller_transaction_open", "_caller_txn_open",
             "refuse_caller_transaction", "begin", "tstart", "tcommit", "trollback", "_tstart", "_tcommit",
             "_trollback", "txn_level", "native"}


@dataclass
class PyFunc:
    file: str
    qual: str
    name: str
    cls: Optional[str]
    start: int
    end: int
    decorators: List[str]
    calls: List[Tuple[str, ...]] = field(default_factory=list)       # (kind, *target, line)
    sql: List[Tuple[int, str]] = field(default_factory=list)          # (line, rendered text)
    txn: List[Tuple[int, str]] = field(default_factory=list)
    locks: List[Tuple[int, str]] = field(default_factory=list)
    native_globals: List[Tuple[int, str, str]] = field(default_factory=list)  # (line, op, global)
    is_property: bool = False
    nested: bool = False

    @property
    def public(self) -> bool:
        return not self.name.startswith("_")

    @property
    def src(self) -> str:
        return f"{self.file}:{self.start}-{self.end}"


def _render(node: ast.AST, aliases: Dict[str, str], consts: Dict[str, str]) -> Optional[str]:
    """A string expression rendered with {placeholders}; None if it is not string-like."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value))
            elif isinstance(v, ast.FormattedValue):
                parts.append(_render_fv(v.value, aliases, consts))
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        a = _render(node.left, aliases, consts)
        b = _render(node.right, aliases, consts) if isinstance(node.op, ast.Add) else ""
        if a is None and b is None:
            return None
        return (a if a is not None else "{?}") + (b if b is not None else "{?}")
    if isinstance(node, ast.Name) and node.id in consts:
        return consts[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return _render(node.func.value, aliases, consts)
    return None


def _render_fv(v: ast.AST, aliases: Dict[str, str], consts: Dict[str, str]) -> str:
    # self._t("nodes") / _table("nodes") / self._table("x") -> Graph_KG.nodes
    if isinstance(v, ast.Call):
        fn = v.func
        fname = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
        if fname in ("_t", "_table", "table", "qualify", "_q", "guard_from", "_tbl", "tbl", "_qualified") and v.args:
            inner = _render(v.args[0], aliases, consts)
            if inner is None and isinstance(v.args[0], ast.Call):
                inner = _render_fv(v.args[0], aliases, consts)
            if inner is not None:
                return inner if "." in inner else "Graph_KG." + inner
        return "{?}"
    if isinstance(v, ast.Name):
        if v.id in aliases:
            return aliases[v.id]
        if v.id in ("schema", "s", "sch", "table_schema", "ivg_schema", "_schema", "target_schema"):
            return "Graph_KG"
        return "{" + v.id + "}"
    if isinstance(v, ast.Attribute):
        if v.attr in ("_ivg_schema", "schema", "_schema", "ivg_schema", "_schema_name", "schema_name"):
            return "Graph_KG"
        return "{" + v.attr + "}"
    return "{?}"


def _attr_chain(node: ast.AST) -> List[str]:
    out = []
    while isinstance(node, ast.Attribute):
        out.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        out.append(node.id)
    elif isinstance(node, ast.Call):
        out.append("()")
        out.extend(_attr_chain(node.func)[::-1][::-1] if False else [])
    return out[::-1]


class PyIndex:
    def __init__(self, files: List[str]):
        self.funcs: Dict[str, PyFunc] = {}            # key "file::qual"
        self.by_file: Dict[str, List[PyFunc]] = {}
        self.classes: Dict[str, Dict] = {}             # class name -> {file, bases, methods{name: key}}
        self.module_consts: Dict[str, Dict[str, str]] = {}
        self.imports: Dict[str, Dict[str, Tuple[str, str]]] = {}  # file -> alias -> (module path, name|"")
        for f in files:
            self._index_file(f)

    # ------------------------------------------------------------------
    def _index_file(self, rel: str) -> None:
        path = REPO / rel
        try:
            tree = ast.parse(path.read_text(), filename=rel)
        except (SyntaxError, UnicodeDecodeError):
            return
        consts: Dict[str, str] = {}
        imps: Dict[str, Tuple[str, str]] = {}
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                val = node.value
                if val is None:
                    continue
                txt = _render(val, {}, consts)
                if txt is not None:
                    for t in targets:
                        if isinstance(t, ast.Name):
                            consts[t.id] = txt
                elif isinstance(val, (ast.Tuple, ast.List)):
                    parts = [_render(e, {}, consts) for e in val.elts]
                    joined = "\n;\n".join(p for p in parts if p)
                    if joined:
                        for t in targets:
                            if isinstance(t, ast.Name):
                                consts[t.id] = joined
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                base = node.module
                if node.level:
                    pkg = Path(rel).parent
                    for _ in range(node.level - 1):
                        pkg = pkg.parent
                    base = ".".join(pkg.parts) + ("." + node.module if node.module else "")
                for a in node.names:
                    imps[a.asname or a.name] = (base, a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    imps[a.asname or a.name] = (a.name, "")
        self.module_consts[rel] = consts
        self.imports[rel] = imps
        self.by_file[rel] = []

        def visit(body, cls: Optional[str], prefix: str, nested: bool):
            for node in body:
                if isinstance(node, ast.ClassDef):
                    bases = [b.id if isinstance(b, ast.Name) else (b.attr if isinstance(b, ast.Attribute) else "")
                             for b in node.bases]
                    self.classes.setdefault(node.name, {"file": rel, "bases": bases, "methods": {},
                                                        "start": node.lineno, "end": node.end_lineno})
                    visit(node.body, node.name, prefix + node.name + ".", nested)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    decos = []
                    for d in node.decorator_list:
                        try:
                            decos.append(ast.unparse(d))
                        except Exception:
                            decos.append("?")
                    fn = PyFunc(rel, prefix + node.name, node.name, cls, node.lineno, node.end_lineno or node.lineno,
                                decos, nested=nested)
                    fn.is_property = any(d in ("property",) or d.endswith(".setter") for d in decos)
                    self._scan_function(fn, node, consts)
                    key = f"{rel}::{fn.qual}"
                    self.funcs[key] = fn
                    self.by_file[rel].append(fn)
                    if cls and not nested:
                        self.classes[cls]["methods"].setdefault(node.name, key)
                    # nested functions: indexed (their effects are folded into the parent too)
                    visit(node.body, None, prefix + node.name + ".<locals>.", True)
                elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)) and not nested:
                    # definitions under a module-level `if _HAS_CLICK:` / `try:` are still module members
                    for blk in ("body", "orelse", "finalbody"):
                        visit(getattr(node, blk, []) or [], cls, prefix, nested)
                    for h in getattr(node, "handlers", []) or []:
                        visit(h.body, cls, prefix, nested)
        visit(tree.body, None, "", False)

    # ------------------------------------------------------------------
    def _scan_function(self, fn: PyFunc, node: ast.AST, consts: Dict[str, str]) -> None:
        aliases: Dict[str, str] = {}
        doc_ids: Set[int] = set()
        body = getattr(node, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
            doc_ids.add(id(body[0].value))
        skip_ids: Set[int] = set(doc_ids)
        # strings inside log/raise/warn calls are messages, not SQL
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                f = sub.func
                name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
                chain = _attr_chain(f)
                if name in ("debug", "info", "warning", "warn", "error", "exception", "critical", "log") and (
                        len(chain) >= 2 and chain[0] in ("logger", "log", "logging", "_log", "LOG", "_logger", "warnings")):
                    for a in ast.walk(sub):
                        skip_ids.add(id(a))
            if isinstance(sub, ast.Raise) and sub.exc is not None:
                for a in ast.walk(sub.exc):
                    skip_ids.add(id(a))
        # aliases: x = self._t("nodes") / x = f"{schema}.rdf_props"
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
                v = sub.value
                if isinstance(v, ast.Call):
                    r = _render_fv(v, aliases, consts)
                    if r != "{?}":
                        aliases[sub.targets[0].id] = r
                elif isinstance(v, (ast.JoinedStr, ast.Constant, ast.BinOp)):
                    r = _render(v, aliases, consts)
                    if r is not None and re.fullmatch(r"[\w{}.<>?]+", r or "") and "." in r:
                        aliases[sub.targets[0].id] = r
        seen_str: Set[int] = set()
        for sub in ast.walk(node):
            if id(sub) in skip_ids:
                continue
            line = getattr(sub, "lineno", fn.start)
            # SQL text
            if isinstance(sub, (ast.JoinedStr, ast.Constant, ast.BinOp, ast.Name)) and id(sub) not in seen_str:
                if isinstance(sub, ast.Constant) and not isinstance(sub.value, str):
                    continue
                if isinstance(sub, ast.Name) and sub.id not in consts:
                    continue
                txt = _render(sub, aliases, consts)
                if txt and looks_like_sql(txt):
                    fn.sql.append((line, txt))
                    for inner in ast.walk(sub):
                        seen_str.add(id(inner))
            if not isinstance(sub, ast.Call):
                continue
            f = sub.func
            chain = _attr_chain(f)
            name = chain[-1] if chain else ""
            lit = [a.value if isinstance(a, ast.Constant) and isinstance(a.value, str) else None for a in sub.args]
            if name in NATIVE_CALLS:
                cls = lit[0] if lit else None
                meth = lit[1] if len(lit) > 1 else None
                if cls:
                    fn.calls.append(("cls", cls, meth or "?", line))
                continue
            if name in HOST_CALLS or (name == "call" and len(lit) >= 2 and (lit[0] or "").startswith(("Graph.", "IVG.", "%"))):
                # _call_classmethod(conn, cls, meth) / host.call(cls, meth) / _arno_call(cls, meth)
                strs = [x for x in lit if x]
                if name in ("_call_classmethod", "_call_classmethod_large") and len(lit) >= 3:
                    cls, meth = lit[1], lit[2]
                else:
                    cls = strs[0] if strs else None
                    meth = strs[1] if len(strs) > 1 else None
                if cls:
                    fn.calls.append(("cls", cls, meth or "?", line))
                continue
            if name in ("execute", "executemany") and sub.args:
                txt = _render(sub.args[0], aliases, consts)
                if txt and looks_like_sql(txt) and not any(t == txt for _, t in fn.sql):
                    fn.sql.append((line, txt))
            # Native API global access
            if name in ("set", "kill", "get", "isDefined", "nextSubscript", "increment", "lock", "unlock",
                        "iterator") and lit and (lit[-1] or "").startswith("^") is False:
                pass
            if name in ("set", "kill", "increment", "get", "isDefined", "nextSubscript", "iterator", "getValue",
                        "getString", "getInteger", "getBytes", "lock", "unlock"):
                # Native API: iris.set(value, "^KG", "out", ...), iris.get("^KG", "out", ...), lock("E", 0, "^X", ...)
                gl = None
                for idx_a, a in enumerate(sub.args):
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) and re.fullmatch(r"\^\|?\|?[%A-Za-z][\w.]*", a.value):
                        gl = a.value
                        nxt = sub.args[idx_a + 1] if idx_a + 1 < len(sub.args) else None
                        if isinstance(nxt, ast.Constant) and isinstance(nxt.value, str):
                            gl = f'{gl}("{nxt.value}")'
                        break
                if gl:
                    if name in ("lock", "unlock"):
                        fn.locks.append((line, f"native {name} {gl} args={lit}"))
                    else:
                        op = "write" if name in ("set", "kill", "increment") else "read"
                        fn.native_globals.append((line, op, gl))
                    continue
            if name in TXN_NAMES or name in ("commit", "rollback", "setAutoCommit", "autocommit"):
                if name == "native" and not (len(chain) >= 2 and chain[-2] in ("txn", "tx", "t", "wt")):
                    pass
                else:
                    fn.txn.append((line, ".".join(chain) + "()"))
            # calls to resolve later
            if isinstance(f, ast.Attribute):
                if len(chain) >= 2 and chain[0] == "self" and len(chain) == 2:
                    fn.calls.append(("self", name, line))
                elif len(chain) >= 3 and chain[0] == "self" and chain[1] in ("_store", "store"):
                    fn.calls.append(("store", name, line))
                elif len(chain) >= 3 and chain[0] == "self" and chain[1] in ("_e", "_engine", "engine", "e"):
                    fn.calls.append(("self", name, line))
                elif len(chain) == 2 and chain[0] in ("engine", "eng", "e", "_e", "self_engine", "graph_engine"):
                    fn.calls.append(("engine", name, line))
                elif len(chain) == 2:
                    fn.calls.append(("attr", chain[0], name, line))
                elif len(chain) >= 3 and chain[0] == "self":
                    fn.calls.append(("selfattr", chain[1], name, line))
            elif isinstance(f, ast.Name):
                fn.calls.append(("name", f.id, line))


# --------------------------------------------------------------------------------------------------------------------
# ObjectScript
# --------------------------------------------------------------------------------------------------------------------
@dataclass
class ClsMethod:
    file: str
    cls: str
    name: str
    kind: str                  # ClassMethod | Method | Query | Trigger
    start: int
    end: int
    keywords: str
    language: str = "objectscript"
    reads: List[Tuple[int, str]] = field(default_factory=list)
    writes: List[Tuple[int, str]] = field(default_factory=list)
    sql: List[Tuple[int, str]] = field(default_factory=list)
    locks: List[Tuple[int, str]] = field(default_factory=list)
    txn: List[Tuple[int, str]] = field(default_factory=list)
    calls: List[Tuple[str, str, int]] = field(default_factory=list)

    @property
    def sqlproc(self) -> bool:
        return bool(re.search(r"\bSqlProc\b", self.keywords))

    @property
    def sqlname(self) -> Optional[str]:
        m = re.search(r"SqlName\s*=\s*([\w%]+)", self.keywords)
        return m.group(1) if m else None

    @property
    def private(self) -> bool:
        return bool(re.search(r"\bPrivate\b", self.keywords)) or bool(re.search(r"\bInternal\b", self.keywords))

    @property
    def src(self) -> str:
        return f"{self.file}:{self.start}-{self.end}"


DECL = re.compile(r"^(ClassMethod|Method|Query|Trigger)\s+(%?\w+)\s*(\(.*)?$")
GLOBAL_REF = re.compile(r'(\$Name\(\s*|\$Na\(\s*)?(\^\|\|?[%\w.]+|\^[%A-Za-z][\w.]*)(\(\s*("(?:[^"]|"")*"|[^,)]*))?')
CMD = re.compile(r"(?:(?<=^)|(?<=[\s{}]))(Set|S|Kill|K|ZKill|ZK|Merge|M|If|ElseIf|Else|While|For|F|Quit|Q|Return|"
                 r"Do|D|Write|W|Lock|L|Throw|TStart|TS|TCommit|TC|TRollback|TRO|Try|Catch|Job|J|Hang|H|New|N)"
                 r"(?=[\s:]|$)", re.I)
STR_LIT = re.compile(r'"((?:[^"]|"")*)"')
LOCK_CMD = re.compile(r'(?:(?<=^)|(?<=[\s{}]))(?:Lock|L)(?::\S+)?\s+(?P<args>[^\s{}]*)', re.I)
LOCK_ARG = re.compile(r'(?P<sign>[+-]?)(?P<ref>\^[%\w.|]+(?:\((?:[^()]|\([^()]*\))*\))?)(?:#"(?P<mode>\w+)")?(?::(?P<to>[\w.]+))?')
TXN_RX = re.compile(r'(?:(?<=^)|(?<=[\s{}]))(TStart|TS|TCommit|TC|TRollback|TRO)\b(?P<arg>\s+\d+)?|\$TLevel|\$TL\b', re.I)
CALL_RX = [
    re.compile(r"##class\(\s*([%\w.]+)\s*\)\s*\.\s*(%?\w+)"),
    re.compile(r"\$classmethod\(\s*\"([%\w.]+)\"\s*,\s*\"(%?\w+)\"", re.I),
]
SELFCALL_RX = re.compile(r"(?<![\w#])\.\.(%?[A-Za-z]\w*)\s*(\(|$|\s)")


def _strip_comment(line: str) -> str:
    # remove // and ; comments outside string literals
    out, in_str, i = [], False, 0
    while i < len(line):
        c = line[i]
        if c == '"':
            in_str = not in_str
        if not in_str and (line.startswith("//", i) or (c == ";" and (i == 0 or line[i - 1].isspace()))):
            break
        if not in_str and line.startswith("#;", i):
            break
        out.append(c)
        i += 1
    return "".join(out)


def _split_top(s: str, sep: str) -> List[str]:
    parts, depth, cur, in_str = [], 0, [], False
    for c in s:
        if c == '"':
            in_str = not in_str
        if not in_str:
            if c in "([":
                depth += 1
            elif c in ")]":
                depth -= 1
            elif c == sep and depth == 0:
                parts.append("".join(cur))
                cur = []
                continue
        cur.append(c)
    parts.append("".join(cur))
    return parts


def _gname(m: re.Match) -> str:
    g = m.group(2)
    sub = m.group(4)
    if sub and sub.startswith('"'):
        return f'{g}({sub})'
    return g


class ClsIndex:
    def __init__(self, files: List[str]):
        self.methods: Dict[str, ClsMethod] = {}     # "Class.Method"
        self.classes: Dict[str, Dict] = {}          # Class -> {file, extends, methods: [names]}
        self.sqlnames: Dict[str, str] = {}          # SqlName -> Class.Method
        for f in files:
            self._index(f)

    def _index(self, rel: str) -> None:
        """UDL layout (checked over all 73 classes at the pin): a member declaration, then a line that is exactly
        '{', the body, and a line that is exactly '}' at column 0."""
        lines = (REPO / rel).read_text(errors="replace").split("\n")
        cls_name = None
        i = 0
        while i < len(lines):
            raw = lines[i]
            ln = i + 1
            if cls_name is None:
                m = re.match(r"^Class\s+([%\w.]+)(?:\s+Extends\s+(\(?[^\[{]+\)?))?", raw)
                if m:
                    cls_name = m.group(1)
                    extends = [x.strip() for x in (m.group(2) or "").strip("() \t").split(",") if x.strip()]
                    self.classes[cls_name] = {"file": rel, "extends": extends, "methods": [], "start": ln}
                i += 1
                continue
            m = DECL.match(raw)
            if not m:
                i += 1
                continue
            j = i
            decl = raw
            while j + 1 < len(lines) and lines[j + 1] != "{":
                j += 1
                decl += " " + lines[j]
            kw = ""
            km = re.search(r"\[([^\]]*)\]\s*$", decl.strip())
            if km:
                kw = km.group(1)
            lang = "objectscript"
            lm = re.search(r"Language\s*=\s*(\w+)", kw)
            if lm:
                lang = lm.group(1).lower()
            cur = ClsMethod(rel, cls_name, m.group(2), m.group(1), ln, ln, kw, lang)
            k = j + 2   # first body line (0-based index), after the '{' line
            while k < len(lines) and lines[k] != "}":
                text, start = lines[k], k
                # an embedded &sql( ... ) block or a statement continued over lines: join until the parens balance
                if lang != "python":
                    bal = _paren_balance(_strip_comment(text))
                    while bal > 0 and k + 1 < len(lines) and lines[k + 1] != "}" and k - start < 40:
                        k += 1
                        text += " " + lines[k].strip()
                        bal = _paren_balance(_strip_comment(text))
                self._scan_line(cur, text, start + 1)
                k += 1
            cur.end = k + 1
            key = f"{cls_name}.{cur.name}"
            self.methods[key] = cur
            self.classes[cls_name]["methods"].append(cur.name)
            if cur.sqlproc:
                self.sqlnames[(cur.sqlname or (cls_name.replace(".", "_") + "_" + cur.name)).lower()] = key
            i = k + 1

    @staticmethod
    def _brace_delta(text: str) -> int:
        d, in_str = 0, False
        t = _strip_comment(text)
        for c in t:
            if c == '"':
                in_str = not in_str
            elif not in_str:
                if c == "{":
                    d += 1
                elif c == "}":
                    d -= 1
        return d

    def _scan_line(self, m: ClsMethod, text: str, ln: int) -> None:
        if m.language == "python":
            for g in re.finditer(r"gref\(\s*['\"](\^?[%\w.]+)['\"]", text):
                name = g.group(1) if g.group(1).startswith("^") else "^" + g.group(1)
                m.reads.append((ln, name + " (python gref)"))
            for s in re.finditer(r"['\"]((?:SELECT|INSERT|UPDATE|DELETE)[^'\"]*)['\"]", text, re.I):
                m.sql.append((ln, s.group(1)))
            for c in re.finditer(r"iris\.cls\(\s*['\"]([%\w.]+)['\"]\s*\)\s*\.\s*(%?\w+)", text):
                m.calls.append((c.group(1), c.group(2), ln))
            return
        line = _strip_comment(text)
        if not line.strip():
            return
        # SQL: embedded &sql(...) and string literals that look like SQL (concatenated literals joined with {?})
        lits = STR_LIT.findall(line)
        if "&sql(" in line.lower() or "&sql(" in line:
            m.sql.append((ln, line[line.lower().index("&sql(") + 5:]))
        if lits:
            joined = "{?}".join(x.replace('""', '"') for x in lits)
            if looks_like_sql(joined):
                m.sql.append((ln, joined))
        # calls
        for rx in CALL_RX:
            for c in rx.finditer(line):
                m.calls.append((c.group(1), c.group(2), ln))
        for c in SELFCALL_RX.finditer(line):
            m.calls.append((m.cls, c.group(1), ln))
        # txn
        for t in TXN_RX.finditer(line):
            tok = t.group(0).strip()
            m.txn.append((ln, tok))
        # locks
        for lc in LOCK_CMD.finditer(line):
            args = lc.group("args")
            if not args:
                m.locks.append((ln, "LOCK (release all)"))
                continue
            for la in LOCK_ARG.finditer(args):
                sign = la.group("sign") or "="
                mode = la.group("mode") or "X"
                to = la.group("to")
                m.locks.append((ln, f"{'acquire' if sign == '+' else ('release' if sign == '-' else 'exclusive-replace-all')} "
                                    f"{_lock_name(la.group('ref'))} mode={mode}{' timeout=' + to if to else ' timeout=none'}"))
        # global reads / writes by command context; a string literal holding a caret is text, not a reference
        line = re.sub(r'"(?:[^"]|"")*"', lambda mm: ('"' + "x" * (len(mm.group(0)) - 2) + '"') if "^" in mm.group(0)
                      else mm.group(0), line)
        segs = self._commands(line)
        named_writes = "kill @" in line.lower().replace("  ", " ") or re.search(r"\bKill\s+@", line, re.I) or re.search(r"\bSet\s+@", line, re.I)
        for cmd, arg in segs:
            c = cmd.lower()
            if c in ("set", "s"):
                for a in _split_top(arg, ","):
                    lhs, eq, rhs = a.partition("=")
                    if not eq:
                        rhs, lhs = lhs, ""
                    # Set (a, ^b) = ... / Set $List(^x, 2) = ...
                    for g in GLOBAL_REF.finditer(lhs):
                        if g.group(1):
                            continue
                        m.writes.append((ln, _gname(g)))
                    self._reads_in(m, rhs, ln, named_writes)
            elif c in ("kill", "k", "zkill", "zk"):
                for g in GLOBAL_REF.finditer(arg):
                    m.writes.append((ln, _gname(g)))
            elif c in ("merge", "m"):
                lhs, _, rhs = arg.partition("=")
                for g in GLOBAL_REF.finditer(lhs):
                    m.writes.append((ln, _gname(g)))
                self._reads_in(m, rhs, ln, named_writes)
            elif c in ("lock", "l"):
                continue
            else:
                self._reads_in(m, arg, ln, named_writes)

    @staticmethod
    def _reads_in(m: ClsMethod, text: str, ln: int, named_writes) -> None:
        for g in GLOBAL_REF.finditer(text):
            name = _gname(g)
            prefix = text[max(0, g.start() - 12):g.start()].lower()
            if re.search(r"\$i(ncrement)?\(\s*$", prefix):
                m.writes.append((ln, name))
            elif g.group(1):
                (m.writes if named_writes else m.reads).append((ln, name + (" ($Name, killed by indirection)" if named_writes else " ($Name)")))
            else:
                m.reads.append((ln, name))

    @staticmethod
    def _commands(line: str) -> List[Tuple[str, str]]:
        """Split a line into (command, argument) pairs; text before the first command is ignored."""
        out = []
        # mask string literals so that command words inside strings are not matched
        masked = re.sub(r'"(?:[^"]|"")*"', lambda mm: '"' + "x" * (len(mm.group(0)) - 2) + '"', line)
        pos = [(mm.start(), mm.group(1)) for mm in CMD.finditer(masked)]
        for idx, (p, cmd) in enumerate(pos):
            end = pos[idx + 1][0] if idx + 1 < len(pos) else len(line)
            arg = line[p + len(cmd):end]
            arg = re.sub(r"^:[^\s]*", "", arg)  # postconditional
            out.append((cmd, arg.strip().rstrip("{}").strip()))
        return out


def _paren_balance(text: str) -> int:
    d, in_str = 0, False
    for c in text:
        if c == '"':
            in_str = not in_str
        elif not in_str:
            if c == "(":
                d += 1
            elif c == ")":
                d -= 1
    return d


def _lock_name(ref: str) -> str:
    m = re.match(r"(\^[%\w.|]+)(\((.*)\))?", ref)
    if not m:
        return ref
    return m.group(1) + ("(" + m.group(3) + ")" if m.group(3) else "")


# --------------------------------------------------------------------------------------------------------------------
# Repository file lists
# --------------------------------------------------------------------------------------------------------------------
def python_files() -> List[str]:
    files = sorted(str(p.relative_to(REPO)) for p in (REPO / "iris_vector_graph").rglob("*.py"))
    extra = ["scripts/deploy_production.py", "scripts/deploy_graph_tvfs.py", "api/main.py", "api/routers/cypher.py"]
    return files + [e for e in extra if (REPO / e).exists()]


def cls_files() -> List[str]:
    return sorted(str(p.relative_to(REPO)) for p in (REPO / "iris_src" / "src").rglob("*.cls"))


_CACHE: Dict[str, object] = {}


def load() -> Tuple[PyIndex, ClsIndex]:
    if "py" not in _CACHE:
        _CACHE["py"] = PyIndex(python_files())
        _CACHE["cls"] = ClsIndex(cls_files())
    return _CACHE["py"], _CACHE["cls"]  # type: ignore[return-value]


# --------------------------------------------------------------------------------------------------------------------
# Call resolution (shared by inventory coverage and footprints)
# --------------------------------------------------------------------------------------------------------------------
ENGINE_CLASSES = ("IRISGraphEngine",)
STORE_CLASSES = ("IRISGraphStore",)


class Resolver:
    def __init__(self, py: PyIndex, cl: ClsIndex):
        self.py, self.cl = py, cl
        self.engine: Dict[str, str] = {}
        eng_bases = py.classes.get("IRISGraphEngine", {}).get("bases", [])
        for cname in list(eng_bases) + ["IRISGraphEngine"]:
            for name, key in py.classes.get(cname, {}).get("methods", {}).items():
                self.engine.setdefault(name, key)
        self.store: Dict[str, str] = {}
        for cname in STORE_CLASSES:
            info = py.classes.get(cname, {})
            for name, key in info.get("methods", {}).items():
                self.store.setdefault(name, key)
            for b in info.get("bases", []):
                for name, key in py.classes.get(b, {}).get("methods", {}).items():
                    self.store.setdefault(name, key)
        self.top: Dict[Tuple[str, str], str] = {}
        for key, f in py.funcs.items():
            if f.cls is None and not f.nested:
                self.top[(f.file, f.name)] = key
        self.mod_file: Dict[str, str] = {}
        for rel in py.by_file:
            if rel.endswith("/__init__.py"):
                self.mod_file[rel[:-12].replace("/", ".")] = rel
            self.mod_file[rel[:-3].replace("/", ".")] = rel
        # SQL routine name -> class method (SqlProc) for calls from SQL text
        self.sqlname = dict(cl.sqlnames)

    def cls_key(self, cls: str, meth: str) -> Optional[str]:
        seen = 0
        c = cls
        while c and seen < 6:
            k = f"{c}.{meth}"
            if k in self.cl.methods:
                return k
            ext = self.cl.classes.get(c, {}).get("extends", [])
            c = next((e for e in ext if e.startswith(("Graph.", "IVG."))), None)
            seen += 1
        return None

    def py_call(self, fn: PyFunc, call: Tuple) -> Optional[str]:
        kind = call[0]
        if kind == "cls":
            k = self.cls_key(call[1], call[2])
            return ("cls:" + k) if k else None
        if kind == "self":
            name = call[1]
            if fn.cls:
                own = self.py.classes.get(fn.cls, {}).get("methods", {}).get(name)
                if own:
                    return own
                for b in self.py.classes.get(fn.cls, {}).get("bases", []):
                    k = self.py.classes.get(b, {}).get("methods", {}).get(name)
                    if k:
                        return k
            return self.engine.get(name)
        if kind == "engine":
            return self.engine.get(call[1])
        if kind == "store":
            return self.store.get(call[1])
        if kind == "name":
            name = call[1]
            k = self.top.get((fn.file, name))
            if k:
                return k
            imp = self.py.imports.get(fn.file, {}).get(name)
            if imp:
                modpath, orig = imp
                rel = self.mod_file.get(modpath)
                if rel and orig:
                    k = self.top.get((rel, orig))
                    if k:
                        return k
                    # a class: its __init__ is not interesting; skip
            return None
        if kind == "attr":
            alias, name = call[1], call[2]
            imp = self.py.imports.get(fn.file, {}).get(alias)
            if imp:
                modpath, orig = imp
                target = modpath + ("." + orig if orig else "")
                rel = self.mod_file.get(target) or self.mod_file.get(modpath)
                if rel:
                    k = self.top.get((rel, name))
                    if k:
                        return k
                    # Class.method of an imported class
                    cinfo = self.py.classes.get(orig) if orig else None
                    if cinfo:
                        return cinfo["methods"].get(name)
            return None
        if kind == "selfattr":
            # self.<attr>.<method>: the engine's sub-objects; resolved only for _store-like names
            if call[1] in ("_store", "store"):
                return self.store.get(call[2])
            return None
        return None

    def callees(self, key: str) -> List[Tuple[str, int]]:
        """[(callee key, call line)] for a py func key or 'cls:Class.Method'."""
        out = []
        if key.startswith("cls:"):
            m = self.cl.methods.get(key[4:])
            if not m:
                return out
            for c, meth, ln in m.calls:
                k = self.cls_key(c, meth)
                if k and k != key[4:]:
                    out.append(("cls:" + k, ln))
            for ln, text in m.sql:
                for r in sql_effects(text)["routines"]:
                    k = self.sqlname.get(r.split(".", 1)[1].lower())
                    if k:
                        out.append(("cls:" + k, ln))
            return out
        fn = self.py.funcs.get(key)
        if not fn:
            return out
        for c in fn.calls:
            k = self.py_call(fn, c)
            if k and k != key:
                out.append((k, c[-1]))
        # nested functions defined inside fn
        prefix = fn.qual + ".<locals>."
        for k2, f2 in self.py.funcs.items():
            if f2.file == fn.file and f2.qual.startswith(prefix) and f2.qual.count("<locals>") == fn.qual.count("<locals>") + 1:
                out.append((k2, f2.start))
        for ln, text in fn.sql:
            eff = sql_effects(text)
            for r in eff["routines"]:
                k = self.sqlname.get(r.split(".", 1)[1].lower())
                if k:
                    out.append(("cls:" + k, ln))
            for cc, mm in eff["classcalls"]:
                k = self.cls_key(cc, mm)
                if k:
                    out.append(("cls:" + k, ln))
        return out

    def closure(self, key: str, depth: int = 4) -> Dict[str, Tuple[int, str]]:
        """{reached key: (depth, via)} within `depth` hops."""
        seen: Dict[str, Tuple[int, str]] = {key: (0, "")}
        frontier = [key]
        for d in range(1, depth + 1):
            nxt = []
            for k in frontier:
                for c, ln in self.callees(k):
                    if c not in seen:
                        seen[c] = (d, f"{k}@{ln}")
                        nxt.append(c)
            frontier = nxt
        return seen

    def span(self, key: str) -> Tuple[str, int, int]:
        if key.startswith("cls:"):
            m = self.cl.methods[key[4:]]
            return m.file, m.start, m.end
        f = self.py.funcs[key]
        return f.file, f.start, f.end
