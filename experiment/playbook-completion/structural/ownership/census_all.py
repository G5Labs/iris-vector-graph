#!/usr/bin/env python3
"""§3.4 ownership, step 1: a source-derived writer census over ALL durable stores of the pin.

    python census_all.py --json OUT

Copied from tools/writer_census.py (registered run followup-writer-census) and generalised: that census keeps only the
stores the ledger/redaction invariants read (content tables, ledger_revisions, ^IVG.Ledger); this one keeps every
durable store a product site writes.

Stores (one name per store, the names traces/journal.py's footprint() gives where they overlap):
- ``sql:Graph_KG.<table>`` for every IVG table, whatever schema the text names (the IVG Schema is a run-time choice:
  ``{schema}.nodes`` and ``RAG.nodes`` are the same store); ``sql:kg_emb_*`` / ``sql:kg_eemb_*`` for the routed vector
  tables (run-time names); other schema-qualified tables as written (``sql:SQLUser.X``); persistent classes by their
  SQL table (Graph.KG.LedgerRevision -> ``sql:Graph_KG.ledger_revisions``, also through their default storage globals
  ^Graph.KG.LedgerRevisionD/I);
- ``global:^Root`` for a global; for the multi-purpose roots ^KG, ^NKG and ^IVG.Ledger the first subscript is a
  sub-store (``global:^KG("out")``), ``global:^KG(?)`` when it is a run-time value the census cannot resolve, and a
  whole-root write (``Kill ^KG``) is ``global:^KG`` with ``whole: true`` (it writes every sub-store); ^BM25Idx keeps
  its one fixed node ``global:^BM25Idx("__stop__")`` apart;
- ``schema:<table|index|routine>`` for DDL (CREATE/ALTER/DROP TABLE, INDEX, VIEW, FUNCTION, PROCEDURE): schema writes,
  counted separately from row/node writes;
- ``system:%SYS.Task`` for Task Manager rows, ``file`` for server files.

Sites:
- ObjectScript (iris_src/src/**/*.cls): Set / Merge targets (multi-target Set, $Piece/$List/$Extract targets), Kill /
  ZKill arguments, $Increment / $I / $Sequence first arguments, indirection (Set/Kill/Merge @ref, $I(@ref)) resolved
  from the method's Set/For lines, %Save / %DeleteId / %KillExtent of persistent classes, SQL write and DDL text
  (embedded &sql, literals, concatenated %ExecDirect/%Prepare text rendered across continuation lines), file loaders
  ($System.OBJ.Load).
- Python (iris_vector_graph/** without browser_static, api/**, src/**): SQL text literals and rendered dynamic text
  (f-strings, +, %, .format, table-name calls, placeholders resolved inside the function/module/callers as the
  original does), Native API set/kill/increment with a literal or resolved global name.
- SQL files (sql/**/*.sql): DML and DDL statements.
Excluded: process-private ^|| globals, IRIS system globals (the journal oracle's SYSTEM_GLOBAL_PREFIXES; ^IRIS.Temp* and
^CacheTemp* are kept, flagged temp: they are instance-wide scratch shared across processes but not journaled), docstrings,
comments, the Native API adapters themselves (host.py / embedded.py set/kill), iris_src/dev (not deployed) and
browser_static (a vendored JS bundle).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SYSTEM_PREFIXES = ("^rINDEXSQL", "^%", "^oddDEF", "^oddDEP", "^oddCOM", "^oddPROC", "^rOBJ", "^ROUTINE", "^rMAP",
                   "^rINDEX", "^ISC.", "^SYS(", "^SYS", "^oddEXT", "^oddMAP", "^oddSQL", "^oddStudio", "^oddPKG",
                   "^SPOOL", "^ERRORS", "^OBJ.DSTIME", "^IRIS.Msg", "^rBACKUP", "^mtemp")
TEMP_PREFIXES = ("^IRIS.Temp", "^CacheTemp")
MULTI = ("^KG", "^NKG", "^IVG.Ledger")
# IVG tables: every CREATE TABLE of the product plus the persistent classes' SQL tables (filled by known_tables()).
IVG_TABLES: dict = {}
SKIPPED_UNKNOWN: list = []
CLASS_TABLES = {"Graph.KG.LedgerRevision": "ledger_revisions", "Graph.KG.LedgerStats": "ledger_stats"}
CLASS_GLOBALS = {}   # ^Graph.KG.LedgerRevisionD -> sql:Graph_KG.ledger_revisions (default storage)
for _c, _t in CLASS_TABLES.items():
    for _suf in ("D", "I", "S"):
        CLASS_GLOBALS["^" + _c + _suf] = "sql:Graph_KG." + _t

VERB = r"(INSERT\s+(?:OR\s+UPDATE\s+)?(?:%\w+\s+)*INTO|UPDATE\s+(?:%\w+\s+)*|DELETE\s+(?:%\w+\s+)*FROM|TRUNCATE\s+TABLE)"
TOK = r"((?:[A-Za-z_%\"][\w%\"]*|\{[^{}]*\})(?:[\w%]*\{[^{}]*\}[\w%]*)*(?:\.(?:[A-Za-z_%\"][\w%\"]*|\{[^{}]*\})(?:[\w%]*\{[^{}]*\}[\w%]*)*)*)"
SQLW = re.compile(r"(?<![\w.])" + VERB + r"\s*" + TOK, re.I)
DDL = re.compile(r"(?<![\w.])(CREATE\s+(?:OR\s+REPLACE\s+)?(?:UNIQUE\s+|BITMAP\s+)?(?:TABLE|INDEX|VIEW|FUNCTION|PROCEDURE|METHOD|QUERY|TRIGGER)"
                 r"(?:\s+IF\s+NOT\s+EXISTS)?|DROP\s+(?:TABLE|INDEX|VIEW|FUNCTION|PROCEDURE|METHOD|QUERY|TRIGGER)(?:\s+IF\s+EXISTS)?|"
                 r"ALTER\s+TABLE)\s+" + TOK, re.I)
BUILD_INDEX = re.compile(r"(?<![\w.])BUILD\s+INDEX\s+(?:[\w%]+\s+)*?(?:FOR|ON)\s+TABLE\s+" + TOK, re.I)
GLOBAL_LOAD = re.compile(r"\$System\.OBJ\.Load\(|\$SYSTEM\.OBJ\.Load\(", re.I)


def known_tables():
    names = set(CLASS_TABLES.values())
    rx = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\"\w.{}]+)", re.I)
    for root in ("iris_vector_graph", "iris_src/src", "sql"):
        for p in (REPO / root).rglob("*"):
            if p.suffix not in (".py", ".cls", ".sql") or "browser_static" in p.parts:
                continue
            for m in rx.finditer(p.read_text(errors="replace")):
                last = m.group(1).split(".")[-1].strip('"')
                if "{" not in last and re.fullmatch(r"[A-Za-z_]\w*", last) and last.lower() not in ("is", "at", "declared", "creates"):
                    names.add(last)
    names |= {"embedding_registry", "embedding_quarantine", "fhir_graphs", "fhir_definitions", "fhir_unresolved",
              "fhir_canonical_refs", "rdf_edges_rescue"}
    for n in names:
        IVG_TABLES[n.lower()] = n


def sql_store(tok: str):
    """Store name of a SQL table token, or None when it still holds a run-time part (needs resolution)."""
    tok = tok.strip().rstrip(",;()")
    parts = [x.strip('"') for x in tok.split(".")]
    last = parts[-1]
    low = last.lower()
    if low.startswith("kg_emb_") and ("{" in last or re.fullmatch(r"kg_emb_[0-9a-f]+", low)):
        return "sql:kg_emb_*"
    if low.startswith("kg_eemb_") and ("{" in last or re.fullmatch(r"kg_eemb_[0-9a-f]+", low)):
        return "sql:kg_eemb_*"
    if "{" in last:
        # a fixed table with a run-time suffix: kg_EdgeEmbeddings{suffix}, docs{suffix}
        base = re.sub(r"\{[^{}]*\}", "", last)
        if base.lower() in IVG_TABLES and base:
            return "sql:Graph_KG." + IVG_TABLES[base.lower()] + "{suffix}"
        return None
    if not re.fullmatch(r"[A-Za-z_%][\w%]*", last):
        return None
    if low in IVG_TABLES:
        return "sql:Graph_KG." + IVG_TABLES[low]
    if len(parts) >= 2:
        schema = parts[-2]
        if "{" in schema:
            return "sql:Graph_KG." + last   # a run-time IVG Schema with an unknown table: keep the table name
        return f"sql:{schema}.{last}"
    return "unknown-table:" + last


def is_system_global(root: str) -> bool:
    return root.startswith(SYSTEM_PREFIXES) or root.startswith("^||") or root.startswith("^$")


def global_store(root: str, sub: str | None, whole: bool):
    """Store of a global write: root, first subscript ('lit:<v>', 'var:<name>', None)."""
    root = root.rstrip(".")
    if is_system_global(root):
        return None
    if root in CLASS_GLOBALS:
        return CLASS_GLOBALS[root]
    if root in MULTI:
        if whole or sub is None:
            return f"global:{root}"
        if sub.startswith("lit:"):
            return f'global:{root}("{sub[4:]}")'
        return f"global:{root}(?)"
    if root == "^BM25Idx" and sub == "lit:__stop__":
        return 'global:^BM25Idx("__stop__")'
    return f"global:{root}"


# ------------------------------------------------------------------------------------------------ ObjectScript

def _code(line: str) -> str:
    if line.lstrip().startswith("///"):
        return ""
    out, inq, i = [], False, 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            inq = not inq
        elif not inq and (line.startswith("//", i) or line.startswith(" ;", i) and False):
            break
        out.append(ch)
        i += 1
    return "".join(out)


LIT = re.compile(r'"(?:[^"]|"")*"')


def mask(s: str) -> str:
    return LIT.sub(lambda m: '"' + "x" * (len(m.group(0)) - 2) + '"', s)


def os_chains(stmt: str):
    """Rendered string-concatenation chains of one statement (literals joined with `_`); copied from the census."""
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


def os_statements(lines):
    """(first line, statement code) with continuation lines joined and comments removed (block comments too)."""
    i = 0
    in_block = False
    clean = []
    for raw in lines:
        s = raw
        if in_block:
            if "*/" in s:
                s = " " * (s.index("*/") + 2) + s[s.index("*/") + 2:]
                in_block = False
            else:
                clean.append("")
                continue
        while "/*" in mask(s):
            a = mask(s).index("/*")
            b = mask(s).find("*/", a + 2)
            if b < 0:
                s = s[:a]
                in_block = True
                break
            s = s[:a] + " " * (b + 2 - a) + s[b + 2:]
        clean.append(_code(s))
    while i < len(clean):
        start, s = i + 1, clean[i]
        while i + 1 < len(clean):
            nxt = clean[i + 1].strip()
            if s.rstrip().endswith(" _") or s.rstrip().endswith("\t_") or nxt.startswith("_ "):
                s = s.rstrip() + " " + nxt
                i += 1
            else:
                break
        yield start, s
        i += 1


def os_methods(text: str):
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


WRITE_CMD = re.compile(r"(?i)(?<![\w$%.^#@\"])(set|s|kill|k|merge|m|zkill|zk)(?=[\s:]|$)")
ANY_CMD = re.compile(r"(?i)(set|s|kill|k|merge|m|zkill|zk|do|d|quit|q|if|i|else|e|elseif|for|f|while|write|w|return|ret|"
                     r"lock|l|halt|hang|h|job|j|throw|tstart|ts|tcommit|tc|trollback|tro|continue|read|r|new|n|xecute|x|"
                     r"goto|g|open|o|close|c|use|u|zwrite|zw|catch|try)(?=[\s:{]|$)")
GREF = re.compile(r"\^(?!\|\|)(?!\$)([%A-Za-z][\w.]*)")
INCR = re.compile(r"(?i)\$(?:increment|i|sequence|seq)\(\s*")
PIECEFN = re.compile(r"(?i)\$(?:piece|p|extract|e|list|li|bit|lb)\(\s*$")


def _args_end(ms: str, k: int) -> int:
    """End of a command's argument list starting at k in masked text."""
    depth = 0
    j = k
    while j < len(ms):
        ch = ms[j]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
            if depth < 0:
                return j
        elif depth == 0 and ch in "{}":
            return j
        elif depth == 0 and ch in " \t":
            rest = ms[j:].lstrip()
            if not rest:
                return j
            if ANY_CMD.match(rest) and not rest.startswith(("=", "_", "+", "-", "*", "/", "'", "&", "!", "#", ",")):
                # a command word after whitespace ends the arguments, unless it is an operand after an operator
                prev = ms[:j].rstrip()[-1:] if ms[:j].rstrip() else ""
                if prev not in ("=", "_", "+", "-", "*", "/", "'", "&", "!", "#", ",", "(", "<", ">", "["):
                    return j
        j += 1
    return j


def _split_top(ms: str, a: int, b: int, ch: str = ","):
    out, depth, start = [], 0, a
    for j in range(a, b):
        c = ms[j]
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == ch and depth == 0:
            out.append((start, j))
            start = j + 1
    out.append((start, b))
    return out


def _first_sub(s: str, ms: str, pos: int):
    """First subscript of the global reference whose name ends at pos ('lit:<v>' / 'var:<expr>' / None)."""
    if pos >= len(s) or s[pos] != "(":
        return None
    depth, j = 0, pos
    while j < len(ms):
        c = ms[j]
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
            if depth == 0:
                break
        elif c == "," and depth == 1:
            break
        j += 1
    sub = s[pos + 1:j].strip()
    m = re.fullmatch(r'"((?:[^"]|"")*)"', sub)
    if m:
        return "lit:" + m.group(1).replace('""', '"')
    if re.fullmatch(r"-?\d+(\.\d+)?", sub):
        return "lit:" + sub
    return "var:" + sub


CLASS_CTX = {}   # set by cls_sites: methods, params and text of the class being scanned


def _method_body(name):
    for n, a, b, body in CLASS_CTX.get("methods", []):
        if n == name:
            return body
    return ""


def _resolve_os(var: str, body: str, params: dict, depth: int = 0):
    """Candidate global or table names a variable can hold in this method (Set/For lines, class parameters, a
    method's returned $Name, the arguments same-class callers pass for a parameter)."""
    if var.startswith(".."):
        mname = re.match(r"\.\.(\w+)", var)
        if mname and not var.startswith("..#"):
            mb = _method_body(mname.group(1))
            c2 = []
            for g in re.finditer(r"\$(?:Name|NA)\(\s*(\^\|\|[%\w.]+|\^[%\w.]+)(\(\s*\"([^\"]*)\")?", mb, re.I):
                c2.append(g.group(1) + (f'("{g.group(3)}")' if g.group(3) is not None else ""))
            return (sorted(set(c2)), "returned by " + var) if c2 else ([], "unresolved")
    if var.startswith("..#"):
        v = params.get(var[3:])
        return ([v], "class parameter") if v else ([], "unresolved")
    cands = []
    for m in re.finditer(r"(?i)\bFor\s+" + re.escape(var) + r"\s*=\s*((?:\"[^\"]*\"\s*,?\s*)+)", body):
        cands += re.findall(r'"([^"]*)"', m.group(1))
    for m in re.finditer(r"(?i)\b(?:Set|S)\s+(?:[^\n]*?,\s*)?" + re.escape(var) + r"\s*=\s*([^\n]+)", body):
        rhs = m.group(1)
        for g in re.finditer(r"\$(?:Name|NA)\(\s*(\^\|\|[%\w.]+|\^[%\w.]+)(\(\s*(\"([^\"]*)\"|[^,()]+))?", rhs, re.I):
            if g.group(3) is None:
                cands.append(g.group(1))
            elif g.group(4) is not None:
                cands.append(g.group(1) + f'("{g.group(4)}")')
            else:
                subvar = g.group(3).strip()
                sub = []
                if re.fullmatch(r"\w+", subvar) and subvar != var and depth < 2:
                    sub, _h = _resolve_os(subvar, body, params, depth + 1)
                    sub = [x for x in sub if not x.startswith("^") and "(" not in x]
                cands += [g.group(1) + f'("{x}")' for x in sub] or [g.group(1) + "(?)"]
        for g in re.finditer(r"\$(?:Name|NA)\(\s*@(\w+)", rhs, re.I):
            if g.group(1) != var and depth < 2:
                sub, _h = _resolve_os(g.group(1), body, params, depth + 1)
                cands += sub
        for lit in re.findall(r'"(\^[%\w.]+)"', rhs):
            cands.append(lit)
        for c in os_chains(rhs):
            if c.startswith("^") or re.match(r"[\w%]+\.[\w%{}]+$", c):
                cands.append(c)
        for pm in re.findall(r"\.\.#(\w+)", rhs):
            if pm in params:
                cands.append(params[pm])
    cands = [c for c in cands if c]
    if not cands and re.search(r"(?i)\b(?:Set|S)\s+" + re.escape(var) + r"\s*=\s*\$Order\(\s*(?:\w*Route\w*|\.\.Routes)\(", body):
        # a route name: $Order over the route array read from embedding_registry (Eraser.cls IsRouteName, FHIRGraph
        # LoadRoutes): a routed vector table
        return ["kg_emb_{h}", "kg_eemb_{h}"], "route names ($Order over the registry's route array)"
    if not cands:
        lits = re.findall(r'"((?:Graph_KG\.)[\w]+)"', body)
        if lits and re.search(r"(?i)\b(?:Set|S)\s+" + re.escape(var) + r"\s*=\s*\$List", body):
            return sorted(set(lits)), "method literals (a $List of table names)"
    if not cands and depth < 2:
        # a formal parameter: what this class's callers pass in its position
        sig = re.match(r"\s*(?:Class)?Method\s+(\w+)\(([^)]*)\)", body)
        if sig:
            names = [re.sub(r"^(ByRef|Output)\s+", "", a.strip()).split()[0].split("=")[0].lstrip(".")
                     for a in sig.group(2).split(",") if a.strip()]
            if var in names:
                pos = names.index(var)
                for n, a, b, cbody in CLASS_CTX.get("methods", []):
                    for call in re.finditer(r"\.\." + re.escape(sig.group(1)) + r"\(", cbody):
                        args, d, cur, j = [], 0, "", call.end()
                        while j < len(cbody):
                            ch = cbody[j]
                            if ch == "(":
                                d += 1
                            elif ch == ")":
                                if d == 0:
                                    break
                                d -= 1
                            if ch == "," and d == 0:
                                args.append(cur)
                                cur = ""
                            else:
                                cur += ch
                            j += 1
                        args.append(cur)
                        if pos < len(args):
                            arg = args[pos].strip().lstrip(".")
                            mm = re.match(r"\$(?:Name|NA)\(\s*(\^\|\|[%\w.]+|\^[%\w.]+)", arg, re.I)
                            if mm:
                                cands.append(mm.group(1))
                            elif re.fullmatch(r"\w+", arg) and n != sig.group(1):
                                sub, _h = _resolve_os(arg, cbody, params, depth + 1)
                                cands += sub
                            elif re.fullmatch(r'"[^"]*"', arg):
                                cands.append(arg.strip('"'))
                if cands:
                    return sorted(set(cands)), "same-class callers' arguments"
    return (sorted(set(cands)), "method Set/For") if cands else ([], "unresolved")


def cls_sites(rel: str, text: str):
    methods, params = os_methods(text)
    lines = text.splitlines()
    cls = rel.split("iris_src/src/")[-1][:-4].replace("/", ".")
    CLASS_CTX.clear()
    CLASS_CTX.update({"methods": methods, "params": params})

    def owner_of(line):
        for name, a, b, body in methods:
            if a <= line <= b:
                return name, body
        return "?", ""

    for ln, s in os_statements(lines):
        if not s.strip():
            continue
        meth, body = owner_of(ln)
        ms = mask(s)
        base = {"file": rel, "line": ln, "method": f"{cls}.{meth}", "src": " ".join(s.split())[:160]}

        def emit_ref(pos_caret, verb, how="literal"):
            m = GREF.match(ms, pos_caret)
            if not m:
                return
            root = "^" + m.group(1).rstrip(".")
            sub = _first_sub(s, ms, m.end())
            whole = sub is None and verb in ("kill", "zkill")
            subs_c = [sub]
            how2 = how
            if sub and sub.startswith("var:") and root in MULTI:
                cands, h = _resolve_os(sub[4:], body, params)
                lits = [c for c in cands if not c.startswith("^") and "{" not in c]
                if lits:
                    subs_c, how2 = ["lit:" + c for c in lits], "subscript variable resolved (" + h + ")"
            for sb in subs_c:
                st = global_store(root, sb, whole)
                if st:
                    yield dict(base, store=st, verb=verb, kind="global", mechanism=how2, root=root, whole=whole,
                               temp=root.startswith(TEMP_PREFIXES))

        def emit_indirection(var, verb):
            if (rel, meth, var) == ("iris_src/src/Graph/KG/PropWrite.cls", "SetVal", "tRef"):
                yield dict(base, store="sql:Graph_KG.rdf_props", verb=verb + " @", kind="global", mechanism="os-indirection",
                           resolved=["data global of Graph_KG.rdf_props"],
                           how="hint: PropWrite.cls:25-44 (tRef = $Name(@<data global of ..#TABLE>@(pId)), TABLE = Graph_KG.rdf_props)")
                return
            cands, how = _resolve_os(var, body, params)
            globs = [c for c in cands if c.startswith("^")]
            tabs = [c for c in cands if not c.startswith("^")]
            if not cands:
                yield dict(base, store="any", verb=verb + " @", kind="global", mechanism="os-indirection",
                           resolved=[], how="name from a parameter or expression (any global)")
                return
            for g in globs:
                if g.startswith("^||"):
                    continue                  # process-private: not a durable store
                mm = re.match(r"(\^[%\w.]+)(?:\((\?|\"([^\"]*)\"))?", g)
                if mm.group(2) == "?":
                    subv = "var:?"
                elif mm.group(3) is not None:
                    subv = "lit:" + mm.group(3)
                else:
                    subv = None
                st = global_store(mm.group(1), subv, verb.startswith("kill") and subv is None)
                if st:
                    yield dict(base, store=st, verb=verb + " @", kind="global", mechanism="os-indirection",
                               resolved=cands[:12], how=how)
            for t in tabs:
                st = sql_store(t)
                if st:
                    yield dict(base, store=st, verb=verb + " @", kind="global", mechanism="os-indirection",
                               resolved=cands[:12], how=how)

        # Set / Kill / Merge / ZKill commands
        for cm in WRITE_CMD.finditer(ms):
            verb = {"s": "set", "set": "set", "k": "kill", "kill": "kill", "m": "merge", "merge": "merge",
                    "zkill": "zkill", "zk": "zkill"}[cm.group(1).lower()]
            k = cm.end()
            if k < len(ms) and ms[k] == ":":     # postconditional
                depth, k = 0, k + 1
                while k < len(ms) and not (ms[k] in " \t" and depth == 0):
                    depth += ms[k] in "(["
                    depth -= ms[k] in ")]"
                    k += 1
            while k < len(ms) and ms[k] in " \t":
                k += 1
            end = _args_end(ms, k)
            for a, b in _split_top(ms, k, end):
                arg = ms[a:b]
                lead = len(arg) - len(arg.lstrip())
                a2 = a + lead
                if verb in ("kill", "zkill"):
                    if ms[a2:a2 + 1] == "^":
                        yield from emit_ref(a2, verb)
                    elif ms[a2:a2 + 1] == "@":
                        mv = re.match(r"@\(?\s*([\w.]+|\.\.#\w+)", ms[a2:])
                        if mv:
                            yield from emit_indirection(mv.group(1), verb)
                    continue
                # Set / Merge: targets are left of the first top-level '='
                eqs = [j for j in range(a2, b) if ms[j] == "=" and ms[j - 1:j] not in ("'", "<", ">", "]")
                       and _depth(ms, a2, j) == 0]
                if not eqs:
                    continue
                lhs_a, lhs_b = a2, eqs[0]
                lhs = ms[lhs_a:lhs_b]
                ta, tb = lhs_a, lhs_b
                if lhs.lstrip().startswith("("):        # Set (a,b)=v
                    ta = lhs_a + lhs.index("(") + 1
                    tb = lhs_a + lhs.rindex(")") if ")" in lhs else lhs_b
                for x, y in _split_top(ms, ta, tb):
                    t = ms[x:y]
                    off = len(t) - len(t.lstrip())
                    p0 = x + off
                    if ms[p0:p0 + 1] == "^":
                        yield from emit_ref(p0, verb)
                    elif ms[p0:p0 + 1] == "@":
                        mv = re.match(r"@\(?\s*([\w.]+|\.\.#\w+)", ms[p0:])
                        if mv:
                            yield from emit_indirection(mv.group(1), verb)
                    elif re.match(r"(?i)\$(?:piece|p|extract|e|list|li|bit)\(", ms[p0:]):
                        q = ms.index("(", p0) + 1
                        while q < len(ms) and ms[q] == " ":
                            q += 1
                        if ms[q:q + 1] == "^":
                            yield from emit_ref(q, verb + " piece")
        # $Increment / $Sequence
        for im in INCR.finditer(ms):
            q = im.end()
            if ms[q:q + 1] == "^":
                yield from emit_ref(q, "$increment")
            elif ms[q:q + 1] == "@":
                mv = re.match(r"@\(?\s*([\w.]+)", ms[q:])
                if mv:
                    yield from emit_indirection(mv.group(1), "$increment")
        # object persistence
        for om in re.finditer(r"##class\(([%\w.]+)\)\.(%KillExtent|%DeleteId|%DeleteExtent|%Delete)\(", s):
            c = om.group(1)
            st = ("sql:Graph_KG." + CLASS_TABLES[c]) if c in CLASS_TABLES else ("system:" + c if c.startswith("%SYS") else "object:" + c)
            yield dict(base, store=st, verb=om.group(2), kind="object", mechanism="object")
        for om in re.finditer(r"(\w+)\.%Save\(\)", s):
            var = om.group(1)
            mm = re.search(r"(?i)\b(?:Set|S)\s+" + re.escape(var) + r"\s*=\s*##class\(([%\w.]+)\)\.(%?\w+)\(", body)
            if not mm:
                mm2 = re.search(r"(?i)\b(?:Set|S)\s+" + re.escape(var) + r"\s*=\s*\.\.(%?\w+)\(", body)
                c = cls if mm2 else None
                if c not in CLASS_TABLES:
                    yield dict(base, store="object:?" + var, verb="%Save", kind="object", mechanism="object",
                               how="object class not resolved in the method")
                    continue
            else:
                c = mm.group(1)
            if c in CLASS_TABLES:
                st = "sql:Graph_KG." + CLASS_TABLES[c]
            elif c.startswith("%SYS.Task"):
                st = "system:%SYS.Task"
            elif "Stream" in c or c.startswith("%File"):
                st = "file" if "File" in c else None
            else:
                st = "object:" + c
            if st:
                yield dict(base, store=st, verb="%Save", kind="object", mechanism="object", resolved=[c])
        if GLOBAL_LOAD.search(s):
            yield dict(base, store="any", verb="$System.OBJ.Load", kind="global", mechanism="global-loader",
                       how="loads any global the file names")
        # SQL: literal text on the statement and rendered concatenation chains
        texts = [(" ".join(mask_free_sql(s)), "literal")] + [(c, "os-concat") for c in os_chains(s)]
        for t, mech in texts:
            yield from sql_text_sites(t, base, mech, lambda v: _resolve_os(v, body, params))


def _depth(ms, a, j):
    d = 0
    for c in ms[a:j]:
        d += c in "(["
        d -= c in ")]"
    return d


def mask_free_sql(s: str):
    """The statement with string-literal quotes removed, so embedded &sql(...) and literal SQL both read as text."""
    return [s.replace('""', '"')]


def sql_text_sites(t: str, base: dict, mech: str, resolver):
    for w in SQLW.finditer(t):
        pre = t[max(0, w.start() - 6):w.start()].upper()
        if re.search(r"(ON|FOR)\s*$", pre):
            continue                      # ON UPDATE / FOR UPDATE
        verb = re.sub(r"\s+", " ", w.group(1).upper()).split(" %")[0].strip()
        verb = re.sub(r" %\w+", "", verb)
        yield from _table_sites(w.group(2), verb, "dml", base, mech, resolver)
    for w in DDL.finditer(t):
        words = w.group(1).upper().split()
        kind_word = next((x for x in words if x in ("TABLE", "INDEX", "VIEW", "FUNCTION", "PROCEDURE", "METHOD",
                                                     "QUERY", "TRIGGER")), "TABLE")
        verb = words[0] + " " + kind_word
        yield from _table_sites(w.group(2), verb, "ddl", base, mech, resolver)
    for w in BUILD_INDEX.finditer(t):
        yield from _table_sites(w.group(1), "BUILD INDEX", "ddl", base, mech, resolver)


def _table_sites(tok: str, verb: str, kind: str, base: dict, mech: str, resolver):
    if kind == "ddl" and verb.split()[-1] in ("INDEX", "FUNCTION", "PROCEDURE", "METHOD", "QUERY", "VIEW", "TRIGGER"):
        name = tok.strip('"').split(".")[-1]
        yield dict(base, store="schema:" + verb.split()[-1].lower() + ":" + re.sub(r"\{[^{}]*\}", "{}", name),
                   verb=verb, kind="ddl", mechanism=mech, table=tok)
        return
    if tok.strip() in ('"', "") or tok.rstrip().endswith('."') or tok.strip().startswith('"_'):
        return                            # a literal cut by `_` concatenation: the rendered chain carries the table
    st = sql_store(tok)
    if st and st.startswith("unknown-table:"):
        SKIPPED_UNKNOWN.append({"file": base["file"], "line": base["line"], "token": tok, "verb": verb})
        return                            # an unqualified word no CREATE TABLE of the product names (prose, JS)
    if st:
        yield dict(base, store=("schema:" + st if kind == "ddl" else st), verb=verb, kind=kind, mechanism=mech, table=tok)
        return
    last = tok.split(".")[-1]
    m = re.match(r"\{(?:v|c):([^{}]+)\}$", last) or re.match(r"\{([A-Za-z_]\w*)\}$", last)
    if not m:
        yield dict(base, store="unresolved-table", verb=verb, kind=kind, mechanism=mech, table=tok, how="placeholder shape")
        return
    cands, how = resolver(m.group(1))
    # a candidate that still holds a placeholder (qualified = f"{schema}.{table}") is resolved once more
    more = []
    for c in cands:
        mm = re.search(r"\{(?:v|c):([^{}]+)\}$", c.split(".")[-1])
        if mm and mm.group(1) != m.group(1):
            sub, _h = resolver(mm.group(1))
            more += [c[:c.rindex("{")] + x.split(".")[-1] for x in sub]
    cands = [c for c in cands if not re.search(r"\{(?:v|c):[^{}]+\}$", c.split(".")[-1])] + more if more else cands
    stores = sorted({x for c in cands for x in [sql_store(c)] if x and not x.startswith("unknown-table:")})
    if not stores:
        yield dict(base, store="unresolved-table", verb=verb, kind=kind, mechanism=mech, table=tok,
                   resolved=cands[:12], how=how)
        return
    for st in stores:
        yield dict(base, store=("schema:" + st if kind == "ddl" else st), verb=verb, kind=kind, mechanism=mech,
                   table=tok, resolved=cands[:12], how=how)


# ------------------------------------------------------------------------------------------------ Python

TABLE_WRAPPERS = {"_t", "_table", "_qualified", "qualify", "_q", "_tbl", "_qt", "_qualify", "qualified_table", "_sql_table"}


def _is_tableish_call(node):
    if not isinstance(node, ast.Call):
        return None
    for a in node.args:
        if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.strip('"').lower() in IVG_TABLES:
            return a.value.strip('"')
    return None


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


class PyModule:
    """Copied from tools/writer_census.py (resolution of run-time names inside a function, module and callers)."""

    def __init__(self, rel: str, text: str):
        self.rel = rel
        self.tree = ast.parse(text)
        self.parent = {}
        for n in ast.walk(self.tree):
            for ch in ast.iter_child_nodes(n):
                self.parent[ch] = n
        self.funcs = [n for n in ast.walk(self.tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.classes = [n for n in ast.walk(self.tree) if isinstance(n, ast.ClassDef)]
        self.module_consts = {}
        for st in self.tree.body:
            if isinstance(st, ast.Assign):
                for t in st.targets:
                    if isinstance(t, ast.Name):
                        self.module_consts[t.id] = st.value
            elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.value is not None:
                self.module_consts[st.target.id] = st.value

    def owner(self, line):
        best = None
        for f in self.funcs:
            if f.lineno <= line <= getattr(f, "end_lineno", f.lineno):
                if best is None or f.lineno < best.lineno:
                    best = f
        return best

    def qualname(self, f):
        if f is None:
            return "?"
        for c in self.classes:
            if f in c.body:
                return f"{c.name}.{f.name}"
        return f.name

    def const_strings(self, node, depth=0):
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
        if (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Name)
                and (node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")) in TABLE_WRAPPERS):
            r0 = self.const_strings(node.args[0], depth + 1)
            if r0:
                return r0
        r = render(node) if not isinstance(node, ast.Name) else None
        if r is not None:
            return [r]
        return None

    def resolve(self, var: str, func, depth=0):
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
                # defaults of the parameter itself
                defaults = dict(zip([a.arg for a in args.args][-len(args.defaults):], args.defaults)) if args.defaults else {}
                for a_, d_ in zip(args.kwonlyargs, args.kw_defaults):
                    if d_ is not None:
                        defaults[a_.arg] = d_
                if var in defaults:
                    r = self.const_strings(defaults[var])
                    if r:
                        found += r
                return (found, "callers' constant arguments / default") if found else ([], "parameter")
        if var in self.module_consts:
            r = self.const_strings(self.module_consts[var])
            if r:
                return r, "module constant"
        return [], "unresolved"

    def is_docstring(self, node):
        return isinstance(self.parent.get(node), ast.Expr)

    def maximal(self, node):
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


RESOLVE_HINTS = {("iris_vector_graph/_engine/snapshot.py", "_import_global_from_ndjson", "global_name"): "snapshot_allow_list"}
#: Named resolutions that need knowledge outside the expression, each with the source lines it rests on (the same kind of
#: entry as the original census's RESOLVE_HINTS). Key: (file, function, variable) -> (candidates, citation).
TABLE_HINTS = {
    # the route a vector write lands in: _route_for_write answers a routed table (kg_emb_<hash> / kg_eemb_<hash>) or
    # the legacy table (embeddings.py:755-840)
    ("iris_vector_graph/_engine/embeddings.py", "store_embedding", "table"): (["kg_emb_{h}", "kg_NodeEmbeddings"], "embeddings.py:755-840 _route_for_write"),
    ("iris_vector_graph/_engine/embeddings.py", "store_embeddings", "table"): (["kg_emb_{h}", "kg_NodeEmbeddings"], "embeddings.py:755-840 _route_for_write"),
    ("iris_vector_graph/_engine/embeddings.py", "store_edge_embedding", "table"): (["kg_eemb_{h}", "kg_EdgeEmbeddings"], "embeddings.py:755-840 _route_for_write (edge kind)"),
    ("iris_vector_graph/_engine/embeddings.py", "store_edge_embeddings", "table"): (["kg_eemb_{h}", "kg_EdgeEmbeddings"], "embeddings.py:755-840 _route_for_write (edge kind)"),
    # restore: the archive's files restricted to TABLE_ORDER = RESTORE_TABLE_ORDER (snapshot.py:215-239, 1136, 1234-1238)
    ("iris_vector_graph/_engine/snapshot.py", "restore_snapshot", "table_name"): ("RESTORE_TABLE_ORDER", "snapshot.py:215-239,1136,1234-1238"),
    ("iris_vector_graph/_engine/snapshot.py", "restore_snapshot", "table"): ("RESTORE_TABLE_ORDER", "snapshot.py:1154-1165 _insert_row(table) called with table_name"),
    ("iris_vector_graph/_engine/snapshot.py", "restore_snapshot", "target"): (["kg_emb_{h}"], "snapshot.py:1398-1408 target = self._t(short), is_routed_embedding_table(short)"),
    # the 4.0.0 vector migration's staging / source / target / quarantine tables are the legacy and routed vector
    # tables and the quarantine (graph_scoped_embeddings.py module docstring and _Migrator)
    ("iris_vector_graph/migrations/graph_scoped_embeddings.py", "_drain", "staging"): (["kg_emb_{h}"], "graph_scoped_embeddings.py:940-965 _drain"),
    ("iris_vector_graph/migrations/graph_scoped_embeddings.py", "_drain", "quarantine"): (["embedding_quarantine"], "graph_scoped_embeddings.py:940-965 _drain"),
    ("iris_vector_graph/migrations/graph_scoped_embeddings.py", "_rename", "staging"): (["kg_emb_{h}"], "graph_scoped_embeddings.py:1020-1045 _rename"),
    ("iris_vector_graph/migrations/graph_scoped_embeddings.py", "_rename", "target"): (["kg_emb_{h}"], "graph_scoped_embeddings.py:1020-1045 _rename"),
    ("iris_vector_graph/migrations/graph_scoped_embeddings.py", "_reshape", "source"): (["kg_NodeEmbeddings", "kg_NodeEmbeddings_optimized"], "graph_scoped_embeddings.py:970-980 _reshape"),
    ("iris_vector_graph/migrations/graph_scoped_embeddings.py", "_redistribute", "source"): (["kg_emb_{h}"], "graph_scoped_embeddings.py:1075-1090 _redistribute"),
    ("iris_vector_graph/migrations/graph_scoped_embeddings.py", "_redistribute", "target"): (["kg_emb_{h}"], "graph_scoped_embeddings.py:1075-1090 _redistribute"),
    ("iris_vector_graph/migrations/graph_scoped_embeddings.py", "_dedupe", "q"): (["kg_EdgeEmbeddings", "rdf_labels", "rdf_props"], "graph_scoped_embeddings.py:795-810 _dedupe"),
    ("iris_vector_graph/migrations/graph_scoped_embeddings.py", "_create_embedding_table", "table"): (["kg_emb_{h}"], "graph_scoped_embeddings.py:1400-1410"),
    ("iris_vector_graph/migrations/graph_scoped_embeddings.py", "_backfill_graph_id", "table"): (["kg_NodeEmbeddings", "kg_NodeEmbeddings_optimized", "kg_EdgeEmbeddings", "docs"], "graph_scoped_embeddings.py:740-750"),
    ("iris_vector_graph/_engine/schema.py", "place_quarantined", "table_name"): (["kg_emb_{h}"], "schema.py:2040-2063 place_quarantined into a route"),
    ("iris_vector_graph/_engine/schema.py", "set_embedding_identity", "table"): (["embedding_registry"], "schema.py:1120-1180 set_embedding_identity (registry columns mechanism/model_key)"),
    ("iris_vector_graph/_engine/schema.py", "_migrate_vector_dimensions", "table"): (["kg_NodeEmbeddings", "kg_NodeEmbeddings_optimized", "kg_EdgeEmbeddings", "kg_emb_{h}"], "schema.py:1640-1665"),
    ("iris_vector_graph/_engine/schema.py", "_ensure_registry_route_columns", "table"): (["embedding_registry"], "schema.py:570-585"),
}


LINE_HINTS = {
    ("iris_vector_graph/_engine/schema.py", 143): (["embedding_registry"], "schema.py:137-143 _EMBEDDING_REGISTRY_DDL"),
    ("iris_vector_graph/_engine/schema.py", 212): (["embedding_quarantine"], "schema.py:205-212 _EMBEDDING_QUARANTINE_DDL"),
    ("iris_vector_graph/_engine/schema.py", 255): (["kg_emb_{h}"], "schema.py:250-255 _ROUTED_EMBEDDING_DDL"),
    ("iris_vector_graph/_engine/schema.py", 284): (["kg_eemb_{h}"], "schema.py:280-284 _ROUTED_EDGE_EMBEDDING_DDL"),
    ("iris_vector_graph/engine.py", 765): (["Graph_KG.ivg_ff_probe"], "engine.py:741-747 _fetch_first_probe_tables (the probe's own two tables)"),
    ("iris_vector_graph/engine.py", 784): (["Graph_KG.ivg_ff_probe"], "engine.py:741-747,782 (the probe's own two tables)"),
    ("iris_vector_graph/migrations/statements.py", 195): (["kg_EdgeEmbeddings"], "statements.py:186-196 edge_width_reset_drop (edge vectors: width reset)"),
}


def _hint(mod, func, var, line=None):
    if line is not None and (mod.rel, line) in LINE_HINTS:
        c, cite = LINE_HINTS[(mod.rel, line)]
        return list(c), "hint: " + cite
    if func is None:
        return None
    h = TABLE_HINTS.get((mod.rel, func.name, var))
    if not h:
        return None
    cands, cite = h
    if cands == "RESTORE_TABLE_ORDER":
        lst = mod.const_strings(mod.module_consts.get("RESTORE_TABLE_ORDER")) or []
        cands = [x.replace("Graph_KG_", "Graph_KG.").replace(".ndjson", "") for x in lst]
    return list(cands), "hint: " + cite


def _py_resolver(mod, func, line=None):
    def r(var):
        h = _hint(mod, func, var, line)
        if h:
            return h
        cands, how = mod.resolve(var, func)
        if cands:
            return cands, how
        # a call placeholder {c:name}: the string a same-module function of that name returns
        out = []
        for f in mod.funcs:
            if f.name == var:
                for n in ast.walk(f):
                    if isinstance(n, ast.Return) and n.value is not None:
                        out += mod.const_strings(n.value) or []
        if not out:
            out = FUNC_RETURNS.get(var, [])
            if out:
                return out, "returned by " + var + " (product function of that name)"
        return (out, "returned by " + var) if out else (cands, how)
    return r


FUNC_RETURNS: dict = {}
#: Lines whose matched text is prose, not SQL (checked by reading).
SKIP_LINES = {("iris_vector_graph/_engine/schema.py", 1588): "an error message ('re-declares only an empty column'), schema.py:1585-1592",
              ("src/iris_demo_server/routes/biomedical.py", 682): "JavaScript text of a Script(NotStr(...)) block (biomedical.py:676-700), not SQL"}


def index_returns(files):
    """name -> strings a product Python function of that name returns (for {c:name} placeholders)."""
    for rel, text in files:
        if not rel.endswith(".py"):
            continue
        try:
            mod = PyModule(rel, text)
        except SyntaxError:
            continue
        for f in mod.funcs:
            for n in ast.walk(f):
                if isinstance(n, ast.Return) and n.value is not None:
                    r = mod.const_strings(n.value) or []
                    r = [x for x in r if "{" not in x.split(".")[-1]] if r else []
                    if r:
                        FUNC_RETURNS.setdefault(f.name, [])
                        FUNC_RETURNS[f.name] += [x for x in r if x not in FUNC_RETURNS[f.name]]
ADAPTERS = {"iris_vector_graph/host.py", "iris_vector_graph/embedded.py"}


def snapshot_allow_list(mod: PyModule):
    out = []
    for f in mod.funcs:
        if f.name == "snapshot_globals":
            for n in ast.walk(f):
                if isinstance(n, ast.Tuple) and n.elts and isinstance(n.elts[0], ast.Constant) and isinstance(n.elts[0].value, str):
                    out.append("^" + n.elts[0].value.lstrip("^"))
        if f.name == "ledger_storage_globals":
            out += ["^Graph.KG.LedgerRevisionD", "^Graph.KG.LedgerRevisionI", "^Graph.KG.LedgerStatsD"]
    return out


def py_sites(rel: str, text: str):
    try:
        mod = PyModule(rel, text)
    except SyntaxError:
        return
    for node in ast.walk(mod.tree):
        s = render(node) if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call)) else None
        if s and not mod.is_docstring(node) and mod.maximal(node) and re.search(r"(?i)\b(INSERT|UPDATE|DELETE|TRUNCATE|CREATE|DROP|ALTER|BUILD)\b", s):
            ln = node.lineno
            func = mod.owner(ln)
            base = {"file": rel, "line": ln, "method": mod.qualname(func) if func else "<module>", "src": " ".join(s.split())[:160]}
            mech = "literal" if isinstance(node, ast.Constant) else "py-dynamic"
            yield from sql_text_sites(s, base, mech, _py_resolver(mod, func, ln))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("set", "kill", "increment"):
            if rel in ADAPTERS:
                continue
            gi = 0 if node.func.attr == "kill" else 1
            if len(node.args) <= gi:
                continue
            g = node.args[gi]
            func = mod.owner(node.lineno)
            fname = func.name if func else "?"
            base = {"file": rel, "line": node.lineno, "method": mod.qualname(func) if func else "<module>",
                    "src": ast.unparse(node)[:160]}
            if isinstance(g, ast.Constant) and isinstance(g.value, str):
                if not g.value.startswith("^"):
                    continue
                cands, how = [g.value], "literal"
            elif isinstance(g, ast.Starred):
                cands = (mod.const_strings(g.value) or [])[:1]
                how = "starred module constant"
            elif isinstance(g, ast.Name):
                cands, how = mod.resolve(g.id, func)
                cands = [c for c in cands if "{" not in c]
                hint = RESOLVE_HINTS.get((rel, fname, g.id))
                if not cands and hint == "snapshot_allow_list":
                    cands, how = snapshot_allow_list(mod), "allow-list (RESOLVE_HINTS: restorable_globals)"
            else:
                cands, how = [], "unresolved expression"
            cands = [c for c in cands if c.startswith("^")]
            if not cands:
                # a .set/.kill on something that is not a global name (a Python set, a dict): only report a likely
                # Native API handle
                recv = ast.unparse(node.func.value)
                if re.search(r"(?i)iris|native|host|_obj|irispy|\bio\b", recv):
                    yield dict(base, store="any", verb="native " + node.func.attr, kind="global",
                               mechanism="py-dynamic-global", how=how, resolved=[])
                continue
            sub = node.args[gi + 1] if len(node.args) > gi + 1 else None
            subv = ("lit:" + sub.value) if isinstance(sub, ast.Constant) and isinstance(sub.value, (str, int)) else (None if sub is None else "var:" + ast.unparse(sub))
            if isinstance(sub, ast.Constant):
                subv = "lit:" + str(sub.value)
            subs_list = [subv]
            if isinstance(sub, ast.Name):
                sc, _h = mod.resolve(sub.id, func)
                if sc:
                    subs_list = ["lit:" + x for x in sc]
            if (rel, fname) == ("iris_vector_graph/_engine/snapshot.py", "_import_global_from_ndjson") and isinstance(sub, ast.Constant):
                # snapshot.py:1680-1691: the degree-cache kills run only for graphs collected while is_kg (^KG)
                cands, how = ["^KG"], "hint: snapshot.py:1680-1691 (adjacency_graphs filled only for ^KG)"
            for c in cands:
                for sv in subs_list:
                    st = global_store(c, sv, node.func.attr == "kill" and sub is None)
                    if st:
                        yield dict(base, store=st, verb="native " + node.func.attr, kind="global",
                                   mechanism="literal" if how == "literal" else "py-dynamic-global", resolved=cands[:16],
                                   how=how, root=c)


def sql_file_sites(rel: str, text: str):
    for i, line in enumerate(text.splitlines(), 1):
        code = line.split("--")[0]
        if not code.strip():
            continue
        base = {"file": rel, "line": i, "method": "<sql file>", "src": " ".join(code.split())[:160]}
        yield from sql_text_sites(code, base, "sql-file", lambda v: ([], "unresolved"))


# ------------------------------------------------------------------------------------------------ census

def product_files():
    for p in sorted((REPO / "iris_src" / "src").rglob("*.cls")):
        yield p
    for root in ("iris_vector_graph", "api", "src"):
        for p in sorted((REPO / root).rglob("*.py")):
            if "browser_static" in p.parts:
                continue
            yield p
    for p in sorted((REPO / "sql").rglob("*.sql")):
        yield p
    # served by the sample API (api/gql/schema.py:78-85 imports BiomedicalDomainResolver)
    for p in sorted((REPO / "examples" / "domains" / "biomedical").rglob("*.py")):
        yield p


def census(files):
    """files: iterable of (rel path, text)."""
    if not IVG_TABLES:
        known_tables()
    files = list(files)
    index_returns(files)
    sites, seen = [], set()
    for rel, text in files:
        if rel.endswith(".cls"):
            gen = cls_sites(rel, text)
        elif rel.endswith(".py"):
            gen = py_sites(rel, text)
        else:
            gen = sql_file_sites(rel, text)
        for s in gen:
            if (s["file"], s["line"]) in SKIP_LINES:
                continue
            key = (s["file"], s["line"], s["store"], s["verb"])
            if key in seen:
                continue
            seen.add(key)
            sites.append(s)
    return sites


def main() -> int:
    files = [(str(p.relative_to(REPO)), p.read_text(errors="replace")) for p in product_files()]
    sites = census(files)
    by_store = {}
    for s in sites:
        by_store.setdefault(s["store"], 0)
        by_store[s["store"]] += 1
    out = {"pin_files": len(files), "sites": len(sites), "stores": dict(sorted(by_store.items())),
           "skipped_unknown_tokens": SKIPPED_UNKNOWN,
           "ivg_tables": sorted(IVG_TABLES.values()), "detail": sites}
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, indent=1))
    print(f"{len(files)} files, {len(sites)} write sites, {len(by_store)} stores")
    for k, v in sorted(by_store.items()):
        print(f"  {v:5} {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
