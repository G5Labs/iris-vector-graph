#!/usr/bin/env python3
"""Mechanical enumeration of the IRIS features each module's code uses (gate 3.2-coverage), classified against the
IRIS environment contract.

    python enumerate.py [--check] [--selftest] [--out coverage.json]

Sources. The pin's files, read from the worktree (`check-product-scope.sh` proves them equal to pin 3eaa79cf).
Module ownership: models/breadth-c/inventory.json. A file owned by one module belongs to it whole; in a file with
several owners, an inventoried entry's line range [line, end] belongs to the entry's owners and every line outside
all entries (class headers, parameters, index and storage definitions, module-level code) to every owner of the
file. Only files with `code: true` are read.

Lexing (no feature is taken from a comment or a docstring):
  ObjectScript (.cls): `//`, `///`, `;`, `#;` and `/* */` comments and string literals removed before code tokens
    are taken; string literals that hold SQL are lexed as SQL; `&sql( ... )` bodies (across lines) are lexed as
    embedded SQL; `Storage` and `XData` blocks are skipped; a method with `Language = python` is lexed as Python.
  Python (.py): `tokenize` comments removed; docstrings (ast) removed; string literals that hold SQL lexed as SQL.
  SQL (.sql): `--` comments removed, lexed as SQL.
  Configuration (.cpf, .conf, Dockerfile, .yml, .sh, .toml): IRIS settings, `iris` CLI verbs and ObjectScript
    tokens in them.
Token classes (every member of a class is a feature; nothing is filtered by a list of "interesting" names):
  ObjectScript intrinsic functions and special variables ($NAME, abbreviations normalised), `$$$` macros, system
  class references (##class(%..), $SYSTEM.X.Y, Extends / As of %-classes), `%`-methods called on objects, commands
  with environment semantics (TSTART, TCOMMIT, TROLLBACK, LOCK forms, JOB, MERGE, KILL, ZKILL, HANG, HALT, XECUTE,
  OPEN/USE/CLOSE, VIEW, ZNSPACE, READ/WRITE), global reference kinds (process-private, IRISTEMP, system, product,
  extended), name indirection, class member kinds (Index types, ForeignKey, Trigger, SqlProc, CodeMode, Language);
  embedded SQL statements by verb; SQL verbs, DDL forms, `%` hints and operators, functions, clauses, catalog views,
  constraints, column types and index types; Python IRIS client calls (Native API and DB-API methods, `iris.*`
  attributes, classMethod* targets, DB-API error classes); SQLCODE literals in either language.

Classification (CLASSIFY below, first match wins): `inside` (a validated clause of iris-contract r6, cited),
`validated` (a clause validated by this lane's registered rounds, contract-2/VALIDATED.json; a clause whose round
is not registered falls back to its `outside` entry), or `outside` with its premise and consequence. A feature no
rule matches is `unclassified`: the module's cell cannot close and `--check` fails.
"""
from __future__ import annotations

import ast
import io
import json
import re
import sys
import tokenize
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PC = HERE.parent
REPO = PC.parents[1]
INVENTORY = PC / "models" / "breadth-c" / "inventory.json"
VALIDATED = HERE / "VALIDATED.json"
OPEN_MODULES = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "15", "16", "17", "18"]
ALL_MODULES = ["00"] + OPEN_MODULES[:11] + ["12", "13", "14"] + OPEN_MODULES[11:]

# ------------------------------------------------------------------------------------------------ normalisation
ABBR = {"$A": "$ASCII", "$C": "$CHAR", "$D": "$DATA", "$E": "$EXTRACT", "$F": "$FIND", "$FN": "$FNUMBER",
        "$G": "$GET", "$H": "$HOROLOG", "$I": "$INCREMENT", "$IO": "$IO", "$J": "$JUSTIFY", "$L": "$LENGTH",
        "$LB": "$LISTBUILD", "$LD": "$LISTDATA", "$LF": "$LISTFIND", "$LFS": "$LISTFROMSTRING", "$LG": "$LISTGET",
        "$LI": "$LIST", "$LL": "$LISTLENGTH", "$LS": "$LISTSAME", "$LTS": "$LISTTOSTRING", "$LU": "$LISTUPDATE",
        "$LV": "$LISTVALID", "$N": "$NEXT", "$NA": "$NAME", "$NUM": "$NUMBER", "$O": "$ORDER", "$P": "$PIECE",
        "$Q": "$QUERY", "$QL": "$QLENGTH", "$QS": "$QSUBSCRIPT", "$R": "$RANDOM", "$RE": "$REVERSE", "$S": "$SELECT",
        "$SEQ": "$SEQUENCE", "$ST": "$STACK", "$T": "$TEXT", "$TL": "$TLEVEL", "$TR": "$TRANSLATE", "$V": "$VIEW",
        "$X": "$X", "$Y": "$Y", "$ZCVT": "$ZCONVERT", "$ZDT": "$ZDATETIME", "$ZDTH": "$ZDATETIMEH", "$ZD": "$ZDATE",
        "$ZDH": "$ZDATEH", "$ZH": "$ZHOROLOG", "$ZTS": "$ZTIMESTAMP", "$ZT": "$ZTIME", "$ZTH": "$ZTIMEH",
        "$ZSTRIP": "$ZSTRIP", "$ZSTR": "$ZSTRIP", "$ZE": "$ZERROR", "$ZU": "$ZUTIL", "$ZV": "$ZVERSION",
        "$ZN": "$ZNAME", "$ZNSPACE": "$NAMESPACE", "$ZPI": "$ZPI", "$ZLN": "$ZLN", "$ZLOG": "$ZLOG",
        "$CLASSNAME": "$CLASSNAME", "$ISOBJ": "$ISOBJECT", "$VE": "$VECTOR"}
# a bare $T (no parenthesis) is $TEST, a bare $J is $JOB, a bare $H is $HOROLOG, a bare $D? not special
BARE = {"$T": "$TEST", "$J": "$JOB", "$H": "$HOROLOG", "$ZH": "$ZHOROLOG", "$ZTS": "$ZTIMESTAMP", "$TL": "$TLEVEL",
        "$ZE": "$ZERROR", "$IO": "$IO", "$ZV": "$ZVERSION", "$NS": "$NAMESPACE"}

SQL_VERBS = r"SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|CALL|BUILD\s+INDEX|START\s+TRANSACTION|COMMIT|ROLLBACK|" \
            r"TRUNCATE|GRANT|REVOKE|SAVEPOINT|SET\s+TRANSACTION|SET\s+OPTION|LOCK\s+TABLE|UNLOCK\s+TABLE|PURGE\s+INDEX"
SQLISH = re.compile(r"(?<![A-Za-z_$%])(?:SELECT\s+.+?\bFROM\b|SELECT\s+(?:\$|TOP|1\b|COUNT|%|\w+\()|INSERT\s+(?:%\w+\s+)*"
                    r"(?:OR\s+UPDATE\s+)?INTO\b|UPDATE\s+[\w.\"{}%]+\s+SET\b|DELETE\s+FROM\b|CREATE\s+(?:OR\s+REPLACE\s+)?"
                    r"(?:UNIQUE\s+|BITMAP\s+)?(?:TABLE|INDEX|VIEW|FUNCTION|PROCEDURE|TRIGGER|SCHEMA|QUERY)\b|DROP\s+(?:TABLE|"
                    r"INDEX|VIEW|FUNCTION|PROCEDURE|TRIGGER|SCHEMA|QUERY)\b|ALTER\s+TABLE\b|CALL\s+[\w.]+|BUILD\s+INDEX\b|"
                    r"START\s+TRANSACTION|^\s*(?:COMMIT|ROLLBACK)\s*(?:WORK)?\s*$|TRUNCATE\s+TABLE|GRANT\s+\w+|REVOKE\s+\w+|"
                    r"SAVEPOINT\s|SET\s+TRANSACTION|SET\s+OPTION|INFORMATION_SCHEMA\.)", re.S)
# IRIS-specific SQL tokens: a string literal holding one is lexed as SQL even when it is a fragment of a statement
# built in pieces (e.g. "AS HNSW(M=16, ...)" concatenated to a CREATE INDEX elsewhere)
IRIS_SQL_TOKENS = re.compile(r"\bHNSW\b|%iFind|search_index\(|\bEMBEDDING\(|\bTO_VECTOR\(|\bVECTOR_(?:COSINE|DOT_PRODUCT|L2)\b|"
                             r"%NOINDEX|%NOCHECK|%IGNOREINDEX|%STARTSWITH|%INLIST|%FIND\b|%EXACT|%SQLUPPER|"
                             r"INFORMATION_SCHEMA|HS_FHIRServer|\bFETCH\s+(?:FIRST|NEXT)\b|\bTOP\s+[\d{?%]|\bLIMIT\s+[\d{?%]|"
                             r"\bINSERT\s+OR\s+UPDATE\b|\bBUILD\s+INDEX\b|%NOLOCK|%NOJOURN|%PARALLEL|\bON\s+DELETE\b|"
                             r"\bREFERENCES\s+[\w.]+\s*\(")


SQL_KEYWORD_PARENS = {"IN", "VALUES", "EXISTS", "KEY", "REFERENCES", "ON", "INTO", "AND", "OR", "NOT", "AS", "FROM",
                      "WHERE", "SELECT", "OVER", "USING", "WITH", "THEN", "ELSE", "WHEN", "BY", "UNIQUE", "CHECK",
                      "TABLE", "INDEX", "SET", "JOIN", "UNION", "CASE", "END", "IS", "LIKE", "ALL", "ANY", "SOME",
                      "DEFAULT", "RETURNS", "FUNCTION", "PROCEDURE", "PARTITION", "LIMIT", "TOP", "OFFSET", "HAVING",
                      "GROUP", "ORDER", "DISTINCT", "BETWEEN", "ESCAPE", "PRIMARY", "FOREIGN", "CONSTRAINT", "VIEW",
                      "INSERT", "UPDATE", "DELETE", "CALL", "LANGUAGE", "OBJECTSCRIPT", "SQL", "PYTHON", "FOR", "LEFT",
                      "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "NULL", "TRUE", "FALSE", "DESC", "ASC", "AFTER",
                      "BEFORE", "EACH", "ROW", "BEGIN", "DECLARE", "CURSOR", "FETCH", "OPEN", "CLOSE", "IF", "ADD",
                      "COLUMN", "MODIFY", "RENAME", "TO", "OF", "NO", "ACTION", "CASCADE", "RESTRICT", "BUILD",
                      "PURGE", "EXEC", "EXECUTE", "RETURN", "INOUT", "OUT", "IDENTITY", "WITHIN", "NEXT", "FIRST",
                      "ROWS", "ONLY", "INCLUDE", "DATA", "PRESERVE", "TEMPORARY", "GLOBAL", "LOCAL", "TRIGGER",
                      "REFERENCING", "NEW", "OLD", "COLLATE", "MATCHES", "PATTERN", "STARTSWITH", "INLIST", "FIND",
                      "EXACT", "SQLUPPER", "SQLSTRING", "UPPER_", "PROCEDURES", "RESULT", "SETS", "DYNAMIC", "STATIC"}
SQL_TYPES = {"VARCHAR", "CHAR", "NVARCHAR", "NCHAR", "NUMERIC", "DECIMAL", "INTEGER", "INT", "BIGINT", "SMALLINT",
             "TINYINT", "DOUBLE", "FLOAT", "REAL", "BIT", "TIMESTAMP", "DATE", "TIME", "DATETIME", "POSIXTIME",
             "LONGVARCHAR", "LONGVARBINARY", "VARBINARY", "BINARY", "VECTOR", "BOOLEAN", "TEXT", "CLOB", "BLOB",
             "SERIAL", "STREAM", "ROWVERSION", "MONEY", "CHARACTER", "VARYING"}

NATIVE_UNIQUE = {"classMethodValue", "classMethodVoid", "classMethodString", "classMethodInteger", "classMethodBoolean",
                 "classMethodBytes", "classMethodFloat", "classMethodObject", "classMethodIRISList", "classMethodDecimal",
                 "isDefined", "nextSubscript", "getTLevel", "tStart", "tCommit", "tRollback", "tRollbackOne",
                 "releaseAllLocks", "getServerVersion", "getIRISList", "getString", "getInteger", "getBytes",
                 "getFloat", "getBoolean", "getDecimal", "getObject", "createIRIS", "procedure", "functionInt",
                 "functionString", "functionBytes", "functionIRISList", "iterator", "getAPIVersion", "setAutoCommit",
                 "executemany", "fetchone", "fetchall", "fetchmany", "callproc", "lastrowid", "createConnection",
                 "IRISList", "IRISReference", "invoke", "invokeVoid", "increment"}
NATIVE_AMBIG = {"set", "get", "kill", "lock", "unlock"}
NATIVE_RECEIVER = re.compile(r"(?i)(iris|native|_n\b|irisobj|_irispy|nat\b|db_native|_db\b|irisn|handle)")
DBAPI_COMMON = {"execute", "cursor", "commit", "rollback", "autocommit"}
DBAPI_ERRORS = {"IntegrityError", "DataError", "OperationalError", "ProgrammingError", "DatabaseError",
                "InterfaceError", "InternalError", "NotSupportedError"}


# ------------------------------------------------------------------------------------------------ lexers
class Found:
    def __init__(self):
        self.f = defaultdict(list)  # feature -> [site]

    def add(self, feat: str, site: str):
        if len(self.f[feat]) < 400:
            self.f[feat].append(site)


def sql_features(text: str, site: str, out: Found, embedded: bool = False) -> None:
    t = re.sub(r"--[^\n]*", " ", text)
    t = re.sub(r"'(?:[^']|'')*'", "''", t)  # SQL string literals
    T = " " + re.sub(r"\s+", " ", t) + " "
    U = T.upper()
    pre = "esql" if embedded else "sql"
    verbs = [("INSERT OR UPDATE", r"\bINSERT\s+(?:%\w+\s+)*OR\s+UPDATE\b"),
             ("INSERT ... SELECT", r"\bINSERT\s+(?:%\w+\s+)*INTO\s+[\w.\"]+\s*(?:\([^)]*\))?\s*SELECT\b"),
             ("INSERT", r"\bINSERT\s+(?:%\w+\s+)*INTO\b"),
             ("UPDATE", r"\bUPDATE\s+(?:%\w+\s+)*[\w.\"{}]+\s+SET\b"),
             ("DELETE", r"\bDELETE\s+(?:%\w+\s+)*FROM\b"),
             ("SELECT", r"\bSELECT\b"),
             ("SELECT ... INTO :host", r"\bSELECT\b[^;]*?\bINTO\s*:"),
             ("DECLARE CURSOR", r"\bDECLARE\s+\w+\s+CURSOR\b"), ("FETCH", r"^\s*FETCH\b"),
             ("CALL", r"\bCALL\s+[\w.]+"), ("BUILD INDEX", r"\bBUILD\s+INDEX\b"),
             ("PURGE INDEX", r"\bPURGE\s+INDEX\b"),
             ("START TRANSACTION", r"\bSTART\s+TRANSACTION\b"), ("COMMIT", r"^\s*COMMIT\b"),
             ("ROLLBACK", r"^\s*ROLLBACK\b"), ("SAVEPOINT", r"\bSAVEPOINT\b"),
             ("SET TRANSACTION", r"\bSET\s+TRANSACTION\b"), ("SET OPTION", r"\bSET\s+OPTION\b"),
             ("TRUNCATE TABLE", r"\bTRUNCATE\s+TABLE\b"), ("GRANT", r"^\s*GRANT\b"), ("REVOKE", r"^\s*REVOKE\b"),
             ("LOCK TABLE", r"\bLOCK\s+TABLE\b"), ("UNLOCK TABLE", r"\bUNLOCK\s+TABLE\b")]
    for name, pat in verbs:
        if re.search(pat, U):
            out.add(f"{pre}.verb.{name}", site)
    for m in re.finditer(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(UNIQUE\s+|BITMAP\s+|GLOBAL\s+TEMPORARY\s+)?(TABLE|INDEX|VIEW|"
                         r"FUNCTION|PROCEDURE|TRIGGER|SCHEMA|QUERY|METHOD)\b", U):
        out.add(f"sql.ddl.CREATE {(m.group(1) or '').strip() + ' ' if m.group(1) else ''}{m.group(2)}", site)
    for m in re.finditer(r"\bDROP\s+(TABLE|INDEX|VIEW|FUNCTION|PROCEDURE|TRIGGER|SCHEMA|QUERY|METHOD)\b", U):
        out.add(f"sql.ddl.DROP {m.group(1)}", site)
    for m in re.finditer(r"\bALTER\s+TABLE\s+[\w.\"]+\s+(ADD\s+COLUMN|ADD\s+CONSTRAINT|ADD|DROP\s+COLUMN|DROP\s+CONSTRAINT|"
                         r"DROP|ALTER\s+COLUMN|MODIFY|RENAME)", U):
        a = re.sub(r"\s+", " ", m.group(1))
        out.add("sql.ddl.ALTER TABLE " + ("ADD COLUMN" if a == "ADD" else a), site)
    for m in re.finditer(r"%([A-Za-z][A-Za-z_]+)\b", T):
        if m.group(1) == m.group(1).upper():  # SQL spells its % keywords in capitals; %FromJSON is ObjectScript
            out.add(f"sql.pct.%{m.group(1)}", site)
    if re.search(r"%IGNOREINDEX\s+\*", U):
        out.add("sql.pct.%IGNOREINDEX *", site)
    elif "%IGNOREINDEX" in U:
        out.add("sql.pct.%IGNOREINDEX named", site)
    for m in re.finditer(r"\b([A-Z][A-Z0-9_]*)\s*\(", U):
        w = m.group(1)
        if w in SQL_KEYWORD_PARENS:
            continue
        if w in SQL_TYPES:
            out.add(f"sql.type.{w}", site)
            continue
        # a lower-case identifier in the original text is a name (table, column), not a function
        orig = T[m.start(1):m.end(1)]
        if orig != orig.upper():
            continue
        out.add(f"sql.fn.{w}", site)
    for m in re.finditer(r"\b(VARCHAR|CHAR|INTEGER|INT|BIGINT|SMALLINT|DOUBLE|FLOAT|NUMERIC|DECIMAL|TIMESTAMP|DATE|BIT|"
                         r"LONGVARCHAR|VARBINARY|VECTOR|BOOLEAN|POSIXTIME)\b", U):
        if re.search(r"\bCREATE\s+TABLE|\bALTER\s+TABLE|\bCAST\s*\(|\bCONVERT\s*\(|\bRETURNS\b|\bFUNCTION\b", U):
            out.add(f"sql.type.{m.group(1)}", site)
    clauses = {"TOP": r"\bTOP\s+(?:\d+|\?|:|\(|\{|%)", "LIMIT": r"\bLIMIT\s+(?:\d+|\?|:|\{|%)",
               "OFFSET": r"\bOFFSET\s+(?:\d+|\?|:|\{|%)",
               "FETCH FIRST": r"\bFETCH\s+(?:FIRST|NEXT)\b", "ORDER BY": r"\bORDER\s+BY\b", "GROUP BY": r"\bGROUP\s+BY\b",
               "HAVING": r"\bHAVING\b", "DISTINCT": r"\bDISTINCT\b", "UNION": r"\bUNION\b", "JOIN": r"\bJOIN\b",
               "NOT EXISTS": r"\bNOT\s+EXISTS\b", "EXISTS": r"(?<!NOT )\bEXISTS\s*\(", "IN (subquery)": r"\bIN\s*\(\s*SELECT\b",
               "LIKE": r"\bLIKE\b", "BETWEEN": r"\bBETWEEN\b", "CASE": r"\bCASE\b", "CTE (WITH)": r"^\s*WITH\s+\w+\s+AS\s*\(",
               "window (OVER)": r"\bOVER\s*\(", "IS NULL": r"\bIS\s+(?:NOT\s+)?NULL\b", "FOR UPDATE": r"\bFOR\s+UPDATE\b",
               "WHERE CURRENT OF": r"\bWHERE\s+CURRENT\s+OF\b", "string concatenation ||": r"\|\|",
               "host variable": r":[A-Za-z%]\w*" if embedded else r"(?!)", "parameter ?": r"\?",
               "ESCAPE": r"\bESCAPE\b", "subquery": r"\(\s*SELECT\b"}
    for name, pat in clauses.items():
        if re.search(pat, U):
            out.add(f"sql.clause.{name}", site)
    for name, pat in {"PRIMARY KEY": r"\bPRIMARY\s+KEY\b", "UNIQUE": r"\bUNIQUE\b", "FOREIGN KEY": r"\bFOREIGN\s+KEY\b|\bREFERENCES\b",
                      "NOT NULL": r"\bNOT\s+NULL\b", "DEFAULT": r"\bDEFAULT\b", "IDENTITY": r"\bIDENTITY\b|\bSERIAL\b",
                      "CHECK": r"\bCHECK\s*\(", "ON DELETE/UPDATE action": r"\bON\s+(?:DELETE|UPDATE)\s+(?:CASCADE|SET|RESTRICT|NO)",
                      "WITH %CLASSPARAMETER": r"%CLASSPARAMETER"}.items():
        if re.search(pat, U) and re.search(r"\bCREATE\b|\bALTER\b", U):
            out.add(f"sql.constraint.{name}", site)
    for m in re.finditer(r"\bAS\s+(%?[A-Za-z][\w.]*Index[\w.]*|HNSW|%iFind[\w.]*|BITMAP|BITSLICE)\b", T, re.I):
        v = m.group(1)
        if re.match(r"(?i)hnsw", v):
            out.add("sql.indextype.HNSW", site)
        elif v.lower().startswith("%ifind"):
            out.add(f"sql.indextype.{v}", site)
        elif v.upper() in ("BITMAP", "BITSLICE"):
            out.add(f"sql.indextype.{v.upper()}", site)
        else:
            out.add("sql.indextype.functional:" + v, site)
    if re.search(r"\bHNSW\b", U):
        out.add("sql.indextype.HNSW", site)
    for m in re.finditer(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+(HS_\w+|%SYS|SYS|Security|Ens\w*|Config)\.(\w+)", T, re.I):
        out.add(f"sql.table.{m.group(1).split('_')[0] + '_*' if m.group(1).upper().startswith('HS_') else m.group(1)}", site)
    for m in re.finditer(r"\b(INFORMATION_SCHEMA)\.(\w+)", U):
        out.add(f"sql.catalog.INFORMATION_SCHEMA.{m.group(2)}", site)
    for m in re.finditer(r"%(DICTIONARY|SYS|SQL_DIAG|SQL)\.(\w+)", U):
        out.add(f"sql.catalog.%{m.group(1)}.{m.group(2)}", site)
    if re.search(r"\$TLEVEL", U):
        out.add("sql.fn.$TLEVEL", site)
    for m in re.finditer(r"\$(LIST\w*|PIECE|EXTRACT|LENGTH|ZSTRIP|ZCONVERT|HOROLOG|JOB|NAMESPACE|USERNAME|SYSTEM|TLEVEL)\b", U):
        out.add(f"sql.fn.${m.group(1)}", site)
    if re.search(r"\bISOLATION\s+LEVEL\b|%COMMITMODE", U):
        out.add("sql.clause.isolation/commit mode", site)
    for m in re.finditer(r"\bLANGUAGE\s+(OBJECTSCRIPT|SQL|PYTHON)\b", U):
        out.add(f"sql.routine.LANGUAGE {m.group(1)}", site)


def sqlcode_literals(text: str, site: str, out: Found) -> None:
    if re.search(r"(?i)sqlcode|sql error|%sqlcode", text):
        for m in re.finditer(r"(?<![\w.])(-\d{1,4})(?![\w.])", text):
            v = int(m.group(1))
            if -500 <= v <= -1:
                out.add(f"sqlcode.{v}", site)
        if re.search(r"SQLCODE\s*[=<>!']+\s*100\b|\(SQLCODE\s*=\s*100\)|SQLCODE '= 0|SQLCODE = 0", text):
            out.add("sqlcode.0/100", site)


def strip_os(line: str):
    """Return (code without strings and comments, [string literals])."""
    code, strs, i, n = [], [], 0, len(line)
    while i < n:
        ch = line[i]
        if ch == '"':
            j, buf = i + 1, []
            while j < n:
                if line[j] == '"':
                    if j + 1 < n and line[j + 1] == '"':
                        buf.append('"'); j += 2; continue
                    break
                buf.append(line[j]); j += 1
            strs.append("".join(buf))
            code.append('""')
            i = j + 1
            continue
        if line.startswith("//", i) or ch == ";" or line.startswith("#;", i) or line.startswith("##;", i):
            break
        if line.startswith("/*", i):
            j = line.find("*/", i + 2)
            if j < 0:
                return "".join(code), strs, True
            i = j + 2
            continue
        code.append(ch)
        i += 1
    return "".join(code), strs, False


def os_code_features(code: str, site: str, out: Found) -> None:
    for m in re.finditer(r"\$\$\$(\w+)", code):
        out.add(f"os.macro.$$${m.group(1)}", site)
    c2 = re.sub(r"\$\$\$\w+", " ", code)
    c2 = re.sub(r"\$\$\w+", " ", c2)  # extrinsic calls of the class's own labels
    for m in re.finditer(r"(?<![\w$])(\$[A-Za-z]+)(\s*\()?", c2):
        name, paren = m.group(1).upper(), m.group(2)
        if name == "$SYSTEM":
            continue
        if not paren and name in BARE:
            name = BARE[name]
        else:
            name = ABBR.get(name, name)
        out.add(f"os.fn.{name}", site)
    for m in re.finditer(r"(?i)\$SYSTEM\.(\w+)(?:\.(\w+))?(?:\.(\w+))?", c2):
        parts = [p for p in m.groups() if p]
        out.add("os.class.%SYSTEM." + ".".join(parts[:-1] if len(parts) > 1 else parts) + (f":{parts[-1]}" if len(parts) > 1 else ""), site)
    for m in re.finditer(r"##class\(\s*(%?[\w.]+)\s*\)(?:\.(%?\w+))?", c2, re.I):
        cls, meth = m.group(1), m.group(2)
        if cls.startswith(("Graph.", "IVG.")):
            continue
        out.add(f"os.class.{cls}" + (f":{meth}" if meth else ""), site)
    for m in re.finditer(r"\.(%[A-Za-z]\w*)\s*\(", c2):
        if len(m.group(1)) > 2:  # "%s(" is a Python format placeholder in a string, not a method
            out.add(f"os.pctmethod.{m.group(1)}", site)
    for m in re.finditer(r"\.(%[A-Za-z]\w*)\b(?!\s*\()", c2):
        if m.group(1) in ("%SQLCODE", "%ROWCOUNT", "%Message", "%ROWID", "%msg"):
            out.add(f"os.pctprop.{m.group(1)}", site)
    if re.search(r'\{\s*""\s*:|=\s*\{\s*\}|=\s*\[\s*\]|\(\s*\{\s*""|\[\s*\{|=\s*\[\s*""', c2):
        out.add("os.json.literal", site)
    cmd = r"(?i)(?:^|[\s{}])"
    for name, pat in {"TSTART": r"tstart\b|ts\b(?=\s|$)", "TCOMMIT": r"tcommit\b|tc\b(?=\s|$)",
                      "TROLLBACK 1": r"trollback\s+1\b|tro\s+1\b", "TROLLBACK": r"trollback\b(?!\s+1)|tro\b(?!\s+1)",
                      "JOB": r"job\s+[^\s]", "MERGE": r"merge\s", "ZKILL": r"zkill\s|zk\s", "HANG": r"hang\s",
                      "HALT": r"halt\b", "XECUTE": r"xecute\s", "OPEN": r"open\s+[^\s(]", "USE": r"use\s+[^\s(]",
                      "CLOSE": r"close\s+[^\s(]", "VIEW": r"view\s", "ZNSPACE": r"znspace\s|zn\s+\"", "READ": r"read\s+[^\s(]",
                      "WRITE": r"write\s|w\s+[\"!$]", "ZWRITE": r"zwrite\s|zw\s", "KILL global": r"kill\s+[^:\s]*\^",
                      "SET global": r"set\s+[^=]*\^", "NEW $NAMESPACE": r"new\s+\$namespace", "ZTRAP": r"ztrap\b",
                      "BREAK": r"break\b"}.items():
        if re.search(cmd + "(?:" + pat + ")", c2):
            out.add(f"os.cmd.{name}", site)
    for m in re.finditer(r"(?i)(?:^|[\s{}])lock\b([^\n]*)", c2):
        arg = m.group(1).strip()
        if not arg or arg.startswith("}") or arg.startswith("//"):
            out.add("os.lock.release-all", site)
            continue
        if arg.startswith("+"):
            out.add("os.lock.incremental", site)
        elif arg.startswith("-"):
            out.add("os.lock.unlock", site)
        else:
            out.add("os.lock.non-incremental", site)
        if arg.lstrip("+-").startswith("("):
            out.add("os.lock.multi-name", site)
        for t in re.findall(r'#\s*""', arg):
            pass
        # lock types survive string stripping as #"" : read them from the raw code instead
        if re.search(r":\s*[\w.$()+-]+", arg):
            out.add("os.lock.timeout", site)
        if "^" not in arg.split(":")[0]:
            out.add("os.lock.local-name", site)
        if "@" in arg:
            out.add("os.lock.indirect-name", site)
    for m in re.finditer(r"\^(\|\|)?(\$?[%A-Za-z][\w.]*)|\^\|([^|]*)\||\^\[([^\]]*)\]", c2):
        if m.group(3) is not None or m.group(4) is not None:
            out.add("os.global.extended-reference", site)
            continue
        ppg, name = m.group(1), m.group(2)
        if ppg:
            out.add("os.global.process-private", site)
        elif name.startswith(("IRIS.Temp", "CacheTemp", "mtemp", "IRISTEMP")):
            out.add("os.global.IRISTEMP", site)
        elif name.startswith(("$LOCK", "$GLOBAL", "$ROUTINE", "$JOB", "$SYSTEM")):
            out.add(f"os.global.ssvn:^{name.split('(')[0]}", site)
        elif name.startswith(("%", "odd", "ROUTINE", "rINDEX", "rOBJ", "SYS", "ISC", "IRIS.", "rMAP", "SPOOL", "ERRORS")):
            out.add(f"os.global.system:^{name}", site)
        else:
            out.add("os.global.product", site)
    if re.search(r"@\s*[\w(\"]", c2):
        out.add("os.indirection", site)
    if re.search(r"(?<![\w%.])SQLCODE\b", c2):
        out.add("os.SQLCODE-variable", site)  # the status variable of embedded SQL
    if re.search(r"(?<![\w.])%msg\b", c2, re.I):
        out.add("os.%msg-variable", site)


def os_raw_features(raw: str, site: str, out: Found) -> None:
    """Features read from the raw line (lock types are strings: #"S")."""
    for m in re.finditer(r'(?i)(?:^|[\s{}])lock\b[^\n]*?#\s*"(\w+)"', raw):
        out.add(f'os.lock.type #"{m.group(1).upper()}"', site)


CLS_MEMBER = re.compile(r"^(ClassMethod|Method|Query|Trigger|ClientMethod|Index|ForeignKey|Property|Relationship|"
                        r"Parameter|Projection|XData|Storage|Class)\b(.*)$")


def lex_cls(path: Path, lines: list, keep, out: Found) -> None:
    in_storage = in_xdata = in_block = False
    depth_skip = 0
    in_py = False
    py_buf: list = []
    py_start = 0
    sql_buf = None
    sql_depth = 0
    sql_site = ""
    for i, raw in enumerate(lines, 1):
        site = f"{path}:{i}"
        mine = keep(i)
        s = raw.rstrip("\n")
        st = s.strip()
        if in_storage or in_xdata:
            if s.startswith("}"):
                in_storage = in_xdata = False
            continue
        if in_py:
            if s.startswith("}"):
                in_py = False
                if py_buf:
                    lex_py_text(path, "\n".join(py_buf), py_start, keep, out, embedded=True)
                py_buf = []
            else:
                py_buf.append(s)
            continue
        m = CLS_MEMBER.match(s)
        if m:
            kind, rest = m.group(1), m.group(2)
            if kind == "Storage":
                in_storage = True
                continue
            if kind == "XData":
                in_xdata = True
                if mine:
                    out.add("cls.member.XData", site)
                continue
            if mine:
                if kind == "Class":
                    for sup in re.findall(r"(%[\w.]+|Ens\.[\w.]+|HS\.[\w.]+|EnsLib\.[\w.]+)", rest):
                        out.add(f"cls.extends.{sup}", site)
                    if re.search(r"(?i)\bExtends\b", rest) and "%Persistent" in rest:
                        out.add("cls.persistent", site)
                elif kind == "Index":
                    t = re.search(r"\[(.*)\]", rest)
                    kw = t.group(1) if t else ""
                    ty = re.search(r"Type\s*=\s*(\w+)", kw)
                    out.add("cls.index" + (f".Type={ty.group(1)}" if ty else ""), site)
                    if re.search(r"\bUnique\b|\bIdKey\b|\bPrimaryKey\b", kw):
                        out.add("cls.index.unique/idkey", site)
                    fx = re.search(r"\bAs\s+([%\w.]+)", rest)
                    if fx:
                        out.add("cls.index.As:" + ("functional(product)" if fx.group(1).startswith("Graph.") else fx.group(1)), site)
                elif kind in ("ForeignKey", "Trigger", "Relationship", "Projection"):
                    out.add(f"cls.member.{kind}", site)
                elif kind == "Property":
                    for ty in re.findall(r"\bAs\s+(%[\w.]+)", rest):
                        if re.search(r"Stream|Dynamic|Vector|List|Array|Relationship", ty):
                            out.add(f"cls.property.As {ty}", site)
                elif kind in ("ClassMethod", "Method", "Query", "ClientMethod"):
                    kw = rest[rest.rfind("["):] if "[" in rest else ""
                    if re.search(r"Language\s*=\s*python", kw, re.I):
                        out.add("cls.method.Language=python", site)
                        in_py = True
                        py_start = i + 2
                        py_buf = []
                    if re.search(r"\bSqlProc\b", kw):
                        out.add("cls.method.SqlProc", site)
                    if re.search(r"CodeMode\s*=\s*(objectgenerator|generator)", kw, re.I):
                        out.add("cls.method.CodeMode=objectgenerator", site)
                    if re.search(r"Language\s*=\s*(tsql|ispl|mvbasic|basic)", kw, re.I):
                        out.add("cls.method.Language=other", site)
                    if kind == "Query":
                        out.add("cls.member.Query", site)
                    for ty in re.findall(r"\bAs\s+(%[\w.]+)", rest):
                        if re.search(r"Stream|Dynamic|Vector|SQL\.|ResultSet|Status", ty):
                            out.add(f"cls.signature.As {ty}", site)
            if in_py:
                # the next line is "{"
                continue
        if in_block:
            j = s.find("*/")
            if j < 0:
                continue
            s = s[j + 2:]
            in_block = False
        if st.startswith("///") or st.startswith("//") or st.startswith(";") or st.startswith("#;"):
            continue
        # embedded SQL spanning lines
        if sql_buf is not None:
            seg, sql_depth, done = scan_sql_paren(s, sql_depth)
            sql_buf.append(seg)
            if done:
                if keep_site(sql_site, keep):
                    sql_features("\n".join(sql_buf), sql_site, out, embedded=True)
                    esql_verb("\n".join(sql_buf), sql_site, out)
                    sqlcode_literals("\n".join(sql_buf), sql_site, out)
                sql_buf = None
                s = s[len(seg) + 1:] if len(seg) + 1 <= len(s) else ""
            else:
                continue
        while "&sql(" in s or "&SQL(" in s:
            k = s.lower().find("&sql(")
            before, after = s[:k], s[k + 5:]
            if mine:
                code, strs, blk = strip_os(before)
                os_code_features(code, site, out)
                os_raw_features(before, site, out)
                sqlcode_literals(before, site, out)
            seg, depth, done = scan_sql_paren(after, 1)
            if done:
                if mine:
                    sql_features(seg, site, out, embedded=True)
                    esql_verb(seg, site, out)
                s = after[len(seg) + 1:]
            else:
                sql_buf, sql_depth, sql_site = [seg], depth, site
                s = ""
                break
        if not s or not mine:
            if s and not mine:
                code, strs, blk = strip_os(s)
                in_block = blk
            continue
        code, strs, blk = strip_os(s)
        in_block = blk
        if CLS_MEMBER.match(s):
            continue
        os_code_features(code, site, out)
        os_raw_features(s, site, out)
        sqlcode_literals(s, site, out)
        for lit in strs:
            if SQLISH.search(lit.upper()) or IRIS_SQL_TOKENS.search(lit):
                sql_features(lit, site, out)
                out.add("os.dynamic-sql-text", site)
            if re.fullmatch(r"%[A-Za-z]\w+", lit):
                # a %-method named in a string: $ClassMethod(cls, "%BuildIndices", ...), $Method(o, "%Save")
                out.add(f"os.pctstring.{lit}", site)
        if re.search(r"&(js|html|javascript)<", code, re.I):
            out.add("os.embedded-web", site)


def keep_site(site: str, keep) -> bool:
    return keep(int(site.rsplit(":", 1)[1]))


def scan_sql_paren(s: str, depth: int):
    """Consume SQL text until the parenthesis closing `&sql(` (depth 1). Returns (consumed, depth, done)."""
    i, inq = 0, False
    while i < len(s):
        ch = s[i]
        if inq:
            if ch == "'":
                inq = False
        elif ch == "'":
            inq = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return s[:i], 0, True
        i += 1
    return s, depth, False


def esql_verb(sql: str, site: str, out: Found) -> None:
    v = sql.strip().split(None, 1)[0].upper() if sql.strip() else "?"
    out.add(f"os.embedded-sql.{v}", site)


def py_docstring_lines(src: str):
    lines = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return lines
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                for ln in range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1):
                    lines.add(ln)
    return lines


def lex_py_text(path, src: str, first_line: int, keep, out: Found, embedded: bool = False) -> None:
    import textwrap
    src = textwrap.dedent(src)
    doc = py_docstring_lines(src)
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        toks = []
    prev = []
    for tok in toks:
        ln = tok.start[0] + first_line - 1
        site = f"{path}:{ln}"
        if tok.type == tokenize.COMMENT or tok.start[0] in doc:
            continue
        if not keep(ln):
            prev = (prev + [tok])[-4:]
            continue
        if tok.type == tokenize.STRING:
            body = tok.string
            body = re.sub(r"^[rRbBuUfF]{0,2}('''|\"\"\"|'|\")", "", body)
            body = re.sub(r"('''|\"\"\"|'|\")$", "", body)
            if SQLISH.search(body.upper()) or IRIS_SQL_TOKENS.search(body):
                sql_features(body, site, out)
                out.add("py.sql-text", site)
            if re.search(r"##class\(|\$\$\$\w|\b(?:Set|Quit|Do|Kill|Lock|TSTART)\s+[\w^$%(+-]|\.%\w+\(|\$[A-Z]{2,}\(", body):
                # ObjectScript text the product writes or runs (class bodies, Native API snippets)
                code, _strs, _blk = strip_os(body.replace("\\n", "\n"))
                os_code_features(code, site, out)
                os_raw_features(body, site, out)
                out.add("py.objectscript-text", site)
            sqlcode_literals(body, site, out)
            mm = re.fullmatch(r"\s*<?(-\d{1,3})>?\s*", body)
            if mm:
                out.add(f"sqlcode.{int(mm.group(1))}", site)  # e.g. `"-119" in text`
            for en in re.findall(r"<(LIST ERROR|UNDEFINED|PROTECT|COMMAND|TIMEOUT|CLASS DOES NOT EXIST|METHOD DOES NOT EXIST|"
                                 r"PROPERTY DOES NOT EXIST|SYNTAX|PARAMETER ERROR|ARGUMENT ERROR|NULL VALUE|MAXSTRING|SUBSCRIPT|"
                                 r"FRAMESTACK|STORE|WIDE CHAR|INVALID OREF|OBJECT DISPATCH|LOCKED|ZSOAP|THROW)>", body, re.I):
                out.add(f"py.iris-error-name.<{en.upper()}>", site)
            m = re.match(r"\s*(%[\w.]+|Graph\.KG\.\w+|IVG\.\w+)\s*$", body)
            if m and len(prev) >= 2 and prev[-1].string == "(" and prev[-2].string.startswith("classMethod"):
                if m.group(1).startswith("%"):
                    out.add(f"py.native.classmethod:{m.group(1)}", site)
        elif tok.type == tokenize.NAME:
            name = tok.string
            if prev and prev[-1].string == "." and len(prev) >= 2:
                recv = prev[-2].string
                if name in NATIVE_UNIQUE:
                    out.add(f"py.client.{name}", site)
                elif name in NATIVE_AMBIG and NATIVE_RECEIVER.search(recv):
                    out.add(f"py.client.native.{name}", site)
                elif name in DBAPI_COMMON:
                    out.add(f"py.client.dbapi.{name}", site)
                if recv == "iris" and name not in NATIVE_UNIQUE:
                    out.add(f"py.iris.{name}", site)
                if recv == "dbapi" or (name in DBAPI_ERRORS):
                    if name in DBAPI_ERRORS:
                        out.add("py.dbapi.error-class", site)
            elif name in DBAPI_ERRORS:
                out.add("py.dbapi.error-class", site)
            elif name == "iris" and prev and prev[-1].string in ("import",):
                out.add("py.import.iris" + (" (embedded)" if embedded else ""), site)
            elif name in ("intersystems_iris", "irisnative", "iris_dbapi", "irispython", "sqlalchemy_iris"):
                out.add(f"py.import.{name}", site)
        if tok.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            prev = (prev + [tok])[-4:]
    if embedded:
        for m in re.finditer(r"\biris\.(cls|sql|gref|lock|unlock|tstart|tcommit|trollback|system|execute|ref)\b", src):
            out.add(f"py.embedded.iris.{m.group(1)}", f"{path}:{first_line}")


def lex_py(path: Path, text: str, keep, out: Found) -> None:
    lex_py_text(path, text, 1, keep, out)
    # SQLCODE literals in code (not strings): e.g. `code == -119`, constants named *SQLCODE*
    doc = py_docstring_lines(text)
    for i, line in enumerate(text.splitlines(), 1):
        if i in doc or not keep(i) or line.lstrip().startswith("#"):
            continue
        if re.search(r"(?i)sqlcode", line.split("#")[0]):
            sqlcode_literals(line.split("#")[0], f"{path}:{i}", out)


def lex_sql(path: Path, text: str, keep, out: Found) -> None:
    stmt, start = [], 1
    for i, line in enumerate(text.splitlines(), 1):
        if not stmt:
            start = i
        stmt.append(line)
        if line.rstrip().endswith(";") or line.strip().upper() in ("GO", "/"):
            if keep(start):
                sql_features("\n".join(stmt), f"{path}:{start}", out)
            stmt = []
    if stmt and keep(start):
        sql_features("\n".join(stmt), f"{path}:{start}", out)


def lex_config(path: Path, text: str, keep, out: Found) -> None:
    sect = ""
    for i, line in enumerate(text.splitlines(), 1):
        if not keep(i):
            continue
        site = f"{path}:{i}"
        s = line.strip()
        if path.suffix in (".cpf", ".conf") or path.name.endswith(".cpf"):
            m = re.match(r"\[(.+)\]", s)
            if m:
                sect = m.group(1)
                continue
            m = re.match(r"([A-Za-z]\w*)\s*=", s)
            if m and sect:
                out.add(f"cfg.cpf.[{sect}].{m.group(1)}", site)
            m = re.match(r"(?i)(ModifyService|ModifyUser|CreateApplication|ModifyNamespace|CreateDatabase|"
                         r"CreateNamespace|ModifyDatabase|CreateResource|ModifyApplication|CreateUser)\b", s)
            if m:
                out.add(f"cfg.cpf.action.{m.group(1)}", site)
            continue
        if s.startswith("#"):
            continue
        for m in re.finditer(r"\biris\s+(session|start|stop|merge|restart|terminal|list|qlist|force|load)\b", s):
            out.add(f"cfg.cli.iris {m.group(1)}", site)
        if re.search(r"\biris-main\b|\biris_main\b|ISC_CPF_MERGE_FILE|--check-caps", s):
            out.add("cfg.container.iris-main/merge", site)
        for m in re.finditer(r"(intersystems[\w/-]*/iris[\w-]*|containers\.intersystems\.com/[\w/.:-]+|iris-community[\w:.-]*)", s):
            out.add("cfg.image", site)
        if re.search(r"##class\(|\$SYSTEM\.|do \^|zn \"", s, re.I):
            code, strs, _ = strip_os(s)
            os_code_features(s, site, out)
            for lit in re.findall(r"'([^']*)'", s) + strs:
                if SQLISH.search(lit.upper()):
                    sql_features(lit, site, out)
        if re.search(r"\b(SELECT|INSERT|CREATE TABLE|GRANT)\b", s):
            sql_features(s, site, out)


# ------------------------------------------------------------------------------------------------ module regions
def regions():
    inv = json.loads(INVENTORY.read_text())
    files = {f["file"]: f for f in inv["files"]}
    by_file = defaultdict(list)
    for e in inv["entries"]:
        by_file[e["file"]].append(e)
    out = {}
    for path, f in files.items():
        if not f.get("code") or not f["owners"]:
            continue
        owners = f["owners"]
        ents = by_file.get(path, [])
        def keep_for(m, ents=ents, owners=owners):
            if len(owners) == 1:
                return lambda i: True
            spans = [(e["line"], e.get("end") or e["line"], set(e.get("owners") or [])) for e in ents]
            def keep(i):
                inside = [o for a, b, o in spans if a <= i <= b]
                if not inside:
                    return True
                return any(m in o for o in inside)
            return keep
        out[path] = {m: keep_for(m) for m in owners}
    return out


def lex_file(path: str, keep, out: Found, inject: str = "") -> None:
    p = REPO / path
    try:
        text = p.read_text(errors="replace")
    except (FileNotFoundError, IsADirectoryError):
        return
    if inject:
        text = text + "\n" + inject
    rel = Path(path)
    if path.endswith(".cls"):
        lex_cls(rel, text.splitlines(), keep, out)
    elif path.endswith(".py"):
        lex_py(rel, text, keep, out)
    elif path.endswith(".sql"):
        lex_sql(rel, text, keep, out)
    else:
        lex_config(rel, text, keep, out)


# ------------------------------------------------------------------------------------------------ classification
def load_validated():
    if VALIDATED.exists():
        return json.loads(VALIDATED.read_text())
    return {"clauses": {}}


IN = "inside"
VA = "validated"
OUT = "outside"

# Families of outside features: the premise left assumed and what depends on it (consequence).
FAM = {
    "pure": ("P2-PURE: ObjectScript and SQL value built-ins compute their documented value inside the calling process "
             "and touch no shared state",
             "no transaction, lock, visibility, durability or concurrency result depends on them; value-level statements "
             "(key and name encodings, parsing, numeric canonical forms, string building) rest on the documented "
             "semantics and on the module's own live and run evidence on this engine, not on the contract"),
    "sqlexpr": ("P2-SQLEXPR: SQL scalar and aggregate functions, predicates, joins, grouping, ordering and subqueries "
                "compute their documented answer over the rows the statement reads (which rows it reads, and what it "
                "locks, is the contract's: E-VIS, E-ROWLOCK, X-NOINDEX)",
                "query answers of readers and the filters of writers (e.g. COALESCE graph guards are X-NULL; %EXACT and "
                "%SQLUPPER collation of string comparisons, %STARTSWITH, %INLIST, LIKE are not) rest on the documented "
                "semantics; no contract result changes, but a reader result that depends on collation or on a "
                "function's edge case is evidenced only by the module's live/run tests"),
    "plan": ("P2-PLAN: plan hints (named %IGNOREINDEX, %PARALLEL, %FIRSTTABLE, %NOFLATTEN, %PROFILE, ...) change the "
             "plan only, not the rows a statement reads or writes (the documented exception, %NOINDEX rows, is X-NOINDEX)",
             "readers that force a plan (EdgeScan's %IGNOREINDEX on labels/props, eraser scans) are assumed to read the "
             "same rows as without the hint; X-NOINDEX shows a by-key statement on a key with a %NOINDEX duplicate may "
             "reach different rows by plan, so that combination stays outside"),
    "clock": ("P2-CLOCK: clocks advance and are not used to order events between processes",
              "time windows (lock timeouts in seconds, HANG, minimum-age purges, cache windows such as the strict-mode "
              "5 s window HD-0801, timestamps in receipts) are untimed in every model and in the contract (wait/no-wait "
              "only); a result that depends on elapsed time holds only as observed on this container"),
    "random": ("P2-RANDOM: $RANDOM and generated GUIDs are arbitrary values",
               "values drawn from them are treated as arbitrary; no result depends on their distribution or uniqueness "
               "beyond what the product checks itself"),
    "hash": ("P2-HASH: $SYSTEM.Encryption digests, encodings and $ZCRC compute their documented functions",
             "receipts' and digests' equality checks compare outputs of the same function; their value as a "
             "commitment is assumed"),
    "status": ("P2-STATUS: an error inside a method reaches its caller as a %Status or exception whose text carries "
               "the cause (SQLCODE, error name); %Status handling is ObjectScript language semantics",
               "how product errors surface in Python and are classified (by text or SQLCODE) is evidenced by the modules' "
               "live tests and by E-1 (env2-e1-r1: a %Status from AssertTemporalRow carried SQLCODE -108 to the Native "
               "API caller), not by a clause; the r6 note that a DB-API error carries the connection's last ObjectScript "
               "error (env/explore-8) applies"),
    "dict": ("P2-DICT: the pin's classes are compiled as the pin's own deploy path leaves them, and run-time dispatch "
             "by name ($CLASSMETHOD, $PROPERTY, %Dictionary reads) reaches them",
             "deploy, upgrade and introspection results (modules 01, 17, 18) rest on the compiled state observed in the "
             "audit's namespaces; run-time compilation ($SYSTEM.OBJ, objectgenerator code) is out of the audit's scope "
             "and is evidenced only by the product's own suites (validation lane)"),
    "sqlroutine": ("P2-SQLROUTINE: a compiled SQL routine ([SqlProc], CREATE FUNCTION/PROCEDURE, CALL) runs its "
                   "ObjectScript in the calling connection's server process and transaction",
                   "SQL-callable entry points other than Txn_Begin/End/Undo (validated as S-1 when env2-e1-r2 passes) "
                   "are assumed to behave as their ObjectScript body called from that process"),
    "epy": ("P2-EPY: embedded Python methods run in the calling IRIS process, sharing its transaction and locks",
            "embedded Python is not driven by the contract (it needs irispython in the container); results of modules "
            "whose writers run as embedded Python rest on the premise"),
    "job": ("P2-JOB: a JOB or WorkMgr worker is a separate server process with its own transactions and locks, "
            "started outside the caller's transaction",
            "parallel builds and algorithms (modules 04, 09, 10) are modelled, where at all, as independent writers; "
            "WorkMgr queueing, worker reuse, error propagation and the caller's waiting are not modelled; a caller's "
            "rollback does not undo a worker's writes (assumed)"),
    "temp": ("P2-TEMP: IRISTEMP globals (^IRIS.Temp*, ^CacheTemp*, ^mtemp) are not journaled, not undone by a rollback, "
             "lost at restart and shared by every process of the instance",
             "scratch state kept there is treated as non-durable and non-transactional; any reasoning that a rollback "
             "or a crash restores it would be wrong; not testable within the audit's scratch-global rule (^IVGAudit*)"),
    "sysglobal": ("P2-SYSGLOBAL: system globals and structured system variables (^$LOCK, ^$GLOBAL, ^%..., ^ROUTINE, "
                  "^rINDEX) report the engine's current state",
                  "introspection results (lock-table reads, routine and index inventories) are observations of this "
                  "engine only"),
    "ns": ("P2-NS: namespaces have the default mappings: ^KG, ^NKG, ^IVG.* and the IVG schema's tables live in the "
           "namespace's own database; switching namespace changes only the default database",
           "every result is per namespace; a site with package or global mappings (e.g. ^KG mapped to a shared "
           "database) is not covered"),
    "security": ("P2-SEC: the caller has the privileges the product needs (the audit runs as _SYSTEM)",
                 "results do not cover least-privilege callers except where the validation lane ran one; web "
                 "dispatch (%CSP.REST), roles and SQL privileges are not modelled"),
    "mgmt": ("P2-MGMT: management APIs (%SYS.ProcessQuery, %SYSTEM.Process other than Terminate, %SYSTEM.Version, "
             "console log, %SYSTEM.Util) report the engine's state and act as documented",
             "process enumeration, version checks and logging by the product are observed live only; process stop is "
             "E-STOP"),
    "task": ("P2-TASK: Task Manager tasks run in their own process at their schedule", "scheduled work (modules 06, 15) "
             "is not modelled; its writes are those of an independent writer"),
    "stream": ("P2-STREAM: stream data is stored in globals written in the caller's transaction like any global",
               "stream columns and properties (docs, snapshots, ledger payloads if any) are assumed to roll back with "
               "the transaction; not validated"),
    "file": ("P2-FILE: files and devices are outside transactions and journaling: a rollback does not undo a file "
             "write, and file I/O is not observed by the journal oracle",
             "snapshot files (module 18, F-C1803) and any export/load through files are covered only by the module's "
             "live tests; no rollback or crash result covers file contents"),
    "device": ("P2-DEVICE: output to the principal device in a method called through the Native API is not part of "
               "the call's result", "diagnostic WRITEs do not affect any result"),
    "zf": ("P2-ZF: $ZF callouts run native code in the calling process", "results that depend on the Arno callout "
           "(module 10, F-1001) are outside the contract; the x86_64 library is unavailable here"),
    "vecop": ("P2-VECOP: $VECTOROP computes its documented element-wise and aggregate operations",
              "vector math in ObjectScript (similarity, normalisation) rests on the documentation; $VECTOR set/get and "
              "rollback is X-VEC"),
    "hnsw": ("P2-HNSW: an HNSW index is maintained by the row's statement and answers approximate nearest neighbours",
             "vector-search answers (modules 06, 17, 18) and their recall are observations only; HNSW maintenance in "
             "transactions and build effects are not modelled"),
    "ifind": ("P2-IFIND: iFind tokenisation, the word dictionary and ranking behave as documented (only the per-row "
              "entries' transaction behaviour is X-FX)",
              "full-text search answers (modules 01, 03, 06, 07, 08) rest on the tokenizer and ranking; the word "
              "dictionary is written outside the transaction (a rolled-back word stays in the dictionary but finds no row)"),
    "embedding": ("P2-EMBEDDING: EMBEDDING() and %Embedding configurations compute vectors as configured",
                  "embedding generation (module 06) is not modelled; vectors are opaque values"),
    "absent": ("absent on IRIS 2026.1 Community (%AI classes, InterSystems FHIR server storage)",
               "every result that depends on these classes is blocked-access (versions/AVAILABILITY.md)"),
    "fk": ("P2-FK: foreign keys refuse a child row without its parent (-121) and a parent delete with children (-124); "
           "under concurrency the check's visibility and locking are as documented (the parent row is checked with a "
           "shared lock unless %NOLOCK)",
           "the product's FK-based guards (rdf_edges -> nodes, labels/props/embeddings -> nodes; AssertTemporalRow's "
           "-121 retry) rest on the premise; E-1 observed -121 only as a code the product maps, not its concurrency"),
    "trigger": ("P2-TRIGGER: triggers and object callbacks run in the row's statement and transaction",
                "trigger-maintained state (system %OBJJRN*/%OBJGUID triggers on DDL tables; any product trigger) is "
                "assumed to roll back with the row"),
    "persistent": ("P2-OBJ: object filing (%Save, %OpenId, %DeleteId, %ExistsId, %KillExtent, %BuildIndices) writes "
                   "the same rows, indexes and locks as the equivalent SQL",
                   "results about persistent classes (ledger revision classes in module 11, FHIR/registry classes in 15, "
                   "snapshot bookkeeping in 18) rest on this; object concurrency modes are not modelled"),
    "iou": ('P2-IOU (residual after X2-IOU): INSERT OR UPDATE of a key whose row another open transaction deleted, and upserts on keys with several rows, behave as documented',
             'X2-IOU (env2-x2-r1) shows an upsert waits for a row another transaction holds and fails with SQLCODE -109 when that transaction rolls back an insert of the key; upserts in modules 06, 15, 18 can therefore surface -109 under a concurrent rolled-back writer; the deleted-key case is outside'),
    "top": ('P2-TOP (residual after X2-TOP): TOP / LIMIT over keys equal under SQLUPPER (case variants), over %NOINDEX duplicates, or ordered by expressions other than a column, behave as documented',
             "X2-TOP (env2-x2-r1) decides TOP n / LIMIT n [OFFSET m] over ORDER BY a VARCHAR column (SQLUPPER string order: 1, 10, 2, ...; not numeric), DESC and %EXACT; paged and 'first row' readers rest on the residual only for the forms listed"),
    "ddl-other": ("P2-DDL: DDL forms other than CREATE/DROP TABLE and ALTER TABLE ADD COLUMN (CREATE/DROP INDEX, "
                  "CREATE VIEW, other ALTER TABLE forms, TRUNCATE) take effect at once and are undone by a rollback that "
                  "covers them, as X-DDL is", "schema-migration results (modules 01, 17) for those forms rest on the "
                  "analogy with X-DDL"),
    "catalog": ("P2-CATALOG: catalog views other than INFORMATION_SCHEMA.TABLES / COLUMNS, %Dictionary through SQL and "
                "default-schema resolution answer the current definitions",
                "introspection (schema detection, route discovery, version probes) is observed only"),
    "isolation": ("P2-ISO: SQL isolation-level / commit-mode settings other than the default are not used at run time",
                  "if a caller sets READ COMMITTED or %COMMITMODE, the contract's E-VIS and E-AUTOCOMMIT do not apply"),
    "lock-esc": ("P2-ESC: lock escalation: a process holding more than the threshold (default 1,000) row locks on one "
                 "table in one transaction takes a table lock; #\"E\" names the escalating lock type",
                 "bulk transactions over one table (EraseGraph / EraseAll deletes, bulk loads in a caller's transaction) "
                 "can block every other writer of that table, of every graph; the structural lane observes it live "
                 "(structural/capkeys/cap_batch.py case 03); the contract treats #\"E\" as exclusive and models no "
                 "escalation"),
    "lock-local": ("P2-LOCKNAME: lock names without a caret and indirect lock names are lock-table entries with the "
                   "same semantics as global names (E-LOCK-*)", "lock plans that use them are read as E-LOCK-* "
                   "plans; not exercised by the contract's cases"),
    "query": ('P2-QUERY (residual after X2-QUERY): $NAME and $QUERY over references with quoted or very long subscripts behave as documented',
             'walkers that build names with $NAME (eraser roots, snapshot export) rest on the residual'),
    "merge": ('P2-MERGE (residual after X2-MERGE): MERGE between overlapping subtrees and MERGE with local variables behave as documented',
             'X2-MERGE (env2-x2-r1) decides MERGE copy / onto existing / rollback and ZKILL value-only / rollback'),
    "seq": ('P2-SEQ: $SEQUENCE allocates values unique across processes, increasing per process, in ranges, not undone by a rollback (observed in env2-x2-explore, not validated)',
             "id allocation with $SEQUENCE is assumed unique; the global's stored value can run ahead of the values returned, so readers of the global must not treat it as a count"),
    "list": ('P2-LIST (residual after X2-LIST): $LISTVALID, $LISTUPDATE, SET $LIST(...), non-canonical numeric literals ($LB(1.0) is encoded as 10E-1), exponents and non-ASCII string elements behave as documented',
             "list-encoded keys, payloads and snapshot records rest on the residual for those forms; X2-LIST (env2-x2-r1) decides the read functions and the driver's IRISList decode"),
    "buildindices": ("P2-BUILDIDX: %BuildIndices / %PurgeIndices (also with parallel jobs, whose workers are WorkMgr "
                     "processes) rebuild the named indexes from the rows outside the caller's transaction, as BUILD "
                     "INDEX does (X-NOINDEX), and leave other connections' cached code consistent",
                     "BuildKG's parallel adjacency rebuild (TraversalBuild.cls:129-133), schema rebuilds and the P-1715 "
                     "<LIST ERROR> after another connection's %BuildIndices (utils.py:114-130) rest on it; X-NOINDEX "
                     "shows BUILD INDEX is outside the caller's transaction and needs the extent lock"),
    "limits": ("P2-LIMITS: engine limits (long strings up to 3,641,144 characters, subscript length, bound-parameter "
               "count, $ZF heap) are not reached by the module's inputs",
               "inputs near a limit (large property values, long ids, wide IN lists, big snapshot lines) fail with "
               "<MAXSTRING>, <SUBSCRIPT> or a parameter-count error; the module's live tests cover only the sizes they "
               "used; capacity lanes (structural/capkeys) observe some limits live"),
    "oracle": ("P2-JOURNAL: the IRIS journal records every global write of a journaled database with its process and "
               "transaction markers (the audit's oracle, traces/journal.py; not a contract clause)",
               "journal-oracled results (footprints, trace conformance, env2-e1-r1-journal) rest on the journal's "
               "completeness; non-journaled writes (IRISTEMP, %NOJOURN) are invisible to it"),
    "sqlparse": ("P2-SQLTEXT: the SQL text the module builds (comments, multi-statement text, literal escaping, "
                 "identifier quoting) is parsed by IRIS as the module intends",
                 "generated SQL (Cypher translation, module 08) is evidenced by the product's suites and TCK runs, not "
                 "by the contract"),
    "bitmap": ("P2-EXTENT: the bitmap extent and index-driven full-table DML reach every row the statement names "
               "(env/explore-4 A11: DELETE without WHERE misses %NOINDEX rows)",
               "full-table deletes over tables loaded with %NOINDEX (bulk loads before their rebuild) can leave rows"),
    "subscript": ("P2-NATIVESUB: the Native API validates subscripts as ObjectScript does (null subscripts refused)",
                  "Native API walks and writes with empty-string subscripts (snapshot import/export, module 18) rest on it"),
    "fetchfirst": ("P2-FETCH: FETCH FIRST / OFFSET ... FETCH NEXT is not used against this engine",
                   "on IRIS 2026.1 Community with the locked driver 5.3.2 every FETCH FIRST form probed (with and without "
                   "ORDER BY, FETCH FIRST 0, OFFSET ... FETCH NEXT) killed the Python client process with SIGSEGV while "
                   "TOP and LIMIT answered (env2-fetchfirst-probe); the product runs its FETCH FIRST probe in a subprocess "
                   "and falls back to TOP on a crash (engine.py:726-840), so query results use TOP; any FETCH FIRST path "
                   "that bypasses the probe would crash the client"),
    "json": ("P2-JSON: the %DynamicObject / %DynamicArray members and forms not exercised by env2-x2-r1 (%GetIterator, "
             "%Size, %Push, JSON literal constructors with content, a %Library.DynamicObject-typed column, SQL JSON "
             "functions) behave as documented",
             "JSON payloads (ledger changesets, qualifiers, reports) rest on the documentation; the product's prefix "
             "test on serialised qualifiers ('{\"temporal\":true', Adjacency.cls:661) depends on %ToJSON's output form"),
    "indirection": ("P2-INDIR: name indirection (@) and XECUTE resolve to the same references as the literal text",
                    "writers through indirection (RetractTemporalRows' @pRoot@, eraser roots, generic loaders) are "
                    "attributed by the writer census's resolution, not by the contract"),
    "rowid": ("P2-ROWID: row ids (%ID, IDENTITY, IDKEY) are unique, stable while the row exists, and allocated outside "
              "the transaction (the journal shows the id counter SET outside the transaction, env2-e1-r1-journal)",
              "lookups and deletes by %ID (RetractTemporalRow) and id-based paging rest on it; ids are not reused "
              "after a rollback (gaps)"),
    "batch": ('P2-BATCH (residual after X2-BATCH): executemany over keys another process holds behaves per row as execute does',
             "X2-BATCH (env2-x2-r1) confirms the product's premise (_batch_check.py:1-4): a refused row of several is skipped without an error and rowcount counts the written rows; one refused row raises"),
    "irislist": ("P2-IRISLIST (residual after X2-LIST): the driver's getIRISList / classMethodIRISList paths decode as IRISList(bytes) does",
             'X2-LIST (env2-x2-r1) decides IRISList over bytes read by getBytes; other driver entry points are assumed equal'),
    "sqlcode": ("P2-SQLCODE: SQLCODEs other than the contract's observed ones (-30, -104, -108, -110, -119, -201, -359, "
                "-400) are reported for the documented conditions",
                "the product's error mapping for these codes (e.g. -121 FK, -124, -114/-110 lock timeouts, -1/-12 "
                "syntax, -29/-30 names, -99 privilege, -149 function errors, -428/-461 etc.) is evidenced only by "
                "their own tests; a misclassification would change an error surface, not stored data"),
    "config": ("P2-CFG: the deployment configuration (cpf merge files, compose files, install scripts) yields an "
               "instance equivalent to the audit container", "results hold for the audit container's configuration "
               "(IRIS 2026.1 Community defaults, SynchCommit=0); settings the deploy files change (licences, services, "
               "memory, journal settings) are not covered"),
    "esql-other": ("P2-ESQL: embedded SQL forms not exercised by E-1 (cursor FETCH loops over many rows, embedded UPDATE, "
                   "embedded statements with %INLIST / %STARTSWITH / named %IGNOREINDEX) behave as their dynamic forms",
                   "E-1 (env2-e1-r1) validated embedded SELECT INTO, a DECLARE/OPEN/FETCH cursor read, INSERT, "
                   "INSERT ... SELECT WHERE NOT EXISTS and DELETE against the contract; other embedded forms rest on "
                   "the same premise by analogy"),
    "web": ("P2-WEB: web dispatch (%CSP.REST, &js/&html) serves requests in a CSP server process", "REST and web "
            "surfaces (modules 07, 09, 16) are observed through their HTTP behaviour only"),
    "language": ("P2-LANG: ObjectScript language features (dynamic dispatch on objects, %New, object references, "
                 "Try/Catch) behave as documented", "no environment result depends on them"),
}


def V(clause, fallback, note=""):
    return ("V", clause, fallback, note)


RULES = [
    # --------------------------------------------------- embedded SQL (premise E-1)
    (r"^os\.embedded-sql\.(SELECT|INSERT|DELETE|DECLARE|OPEN|FETCH|CLOSE)$", V(["E-1"], "esql-other",
        "embedded statement validated by E-1 (env2-e1-r1): same permitted outcomes as dynamic SQL for E-NEST, "
        "E-PARTIAL, E-SQL-END, E-DRV, E-AUTOCOMMIT, E-VIS, E-ROWLOCK, E-UNIQUE, E-STOP, X-STMT, X-NULL")),
    (r"^os\.embedded-sql\.", ("O", "esql-other")),
    (r"^esql\.verb\.(SELECT|INSERT|DELETE|INSERT \.\.\. SELECT|SELECT \.\.\. INTO :host|DECLARE CURSOR|FETCH)$",
     V(["E-1"], "esql-other")),
    (r"^esql\.verb\.", ("O", "esql-other")),
    (r"^py\.objectscript-text$", ("O", "dict")),
    (r"^sql\.clause\.host variable$", V(["E-1"], "esql-other", "X-NULL for host variables: \"\" binds as NULL, $Char(0) "
                                         "as '' (env2-e1-r1 e1-null-*)")),
    # --------------------------------------------------- transactions
    (r"^os\.cmd\.(TSTART|TCOMMIT|TROLLBACK 1|TROLLBACK)$", ("I", ["E-NEST", "E-PARTIAL", "E-STOP"])),
    (r"^os\.fn\.\$TLEVEL$|^sql\.fn\.\$TLEVEL$", ("I", ["E-NEST", "X-TLEVEL-SQL"])),
    (r"^sql\.verb\.(START TRANSACTION|COMMIT|ROLLBACK)$", ("I", ["E-SQL-START", "E-SQL-END"])),
    (r"^sql\.verb\.SAVEPOINT$|^sql\.verb\.SET TRANSACTION$|^sql\.clause\.isolation", ("O", "isolation")),
    (r"^py\.client\.(tStart|tCommit|tRollback|tRollbackOne|getTLevel)$", ("I", ["E-NEST", "E-PARTIAL"])),
    (r"^py\.client\.(setAutoCommit)$|^py\.client\.dbapi\.(commit|rollback|autocommit)$",
     ("I", ["E-DRV", "E-AUTOCOMMIT"])),
    # --------------------------------------------------- locks
    (r"^os\.lock\.(incremental|unlock)$", ("I", ["E-LOCK-COUNT", "E-LOCK-NAMES", "E-LOCK-DEFER", "E-LOCK-LIFE"])),
    (r"^os\.lock\.non-incremental$", ("I", ["E-LOCK-NONINC"])),
    (r"^os\.lock\.release-all$", ("I", ["E-LOCK-DEFER"])),
    (r"^os\.lock\.timeout$|^os\.fn\.\$TEST$", ("I", ["E-LOCK-WAIT"])),
    (r'^os\.lock\.type #"S"$', ("I", ["E-LOCK-MODES"])),
    (r'^os\.lock\.type #"(I|SI|IS|EI|IE)"$', ("I", ["E-LOCK-DEFER"])),
    (r'^os\.lock\.type #"(E|SE|ES)"$', ("O", "lock-esc")),
    (r'^os\.lock\.type #"D"$', ("I", ["E-LOCK-DEFER"])),
    (r"^os\.lock\.multi-name$", ("I", ["E-LOCK-COUNT", "E-LOCK-NAMES"])),
    (r"^os\.lock\.(local-name|indirect-name)$", ("O", "lock-local")),
    (r"^py\.client\.(releaseAllLocks)$|^py\.client\.native\.(lock|unlock)$", ("I", ["E-LOCK-COUNT", "E-LOCK-DEFER", "E-LOCK-WAIT"])),
    (r"^sql\.verb\.(LOCK TABLE|UNLOCK TABLE)$", ("O", "lock-esc")),
    # --------------------------------------------------- globals
    (r"^os\.global\.product$|^os\.cmd\.(SET global|KILL global)$|^os\.fn\.\$(DATA|GET)$", ("I", ["E-GLOBALS", "E-VIS"])),
    (r"^os\.fn\.\$ORDER$|^py\.client\.nextSubscript$|^py\.client\.iterator$", ("I", ["X-ORDER"])),
    (r"^os\.fn\.\$INCREMENT$|^py\.client\.increment$", ("I", ["E-INCR"])),
    (r"^os\.fn\.\$SEQUENCE$", V(["X2-SEQ"], "seq")),
    (r"^os\.global\.process-private$", ("I", ["E-PPG"])),
    (r"^os\.global\.IRISTEMP$", ("O", "temp")),
    (r"^os\.global\.(system|ssvn)", ("O", "sysglobal")),
    (r"^os\.global\.extended-reference$", ("O", "ns")),
    (r"^os\.cmd\.(MERGE|ZKILL)$", V(["X2-MERGE"], "merge")),
    (r"^os\.fn\.\$(QUERY|QSUBSCRIPT|QLENGTH)$", V(["X2-QUERY"], "query")),
    (r"^os\.fn\.\$NAME$", ("O", "query")),
    (r"^os\.indirection$|^os\.cmd\.XECUTE$|^os\.fn\.\$XECUTE$", ("O", "indirection")),
    (r"^py\.client\.(isDefined|getString|getInteger|getFloat|getBoolean|getDecimal|getObject)$|"
     r"^py\.client\.native\.(set|get|kill)$", ("I", ["E-GLOBALS", "E-VIS"])),
    (r"^py\.client\.(IRISList|getBytes)$|^py\.iris\.IRISList$", V(["X2-LIST"], "irislist")),
    (r"^py\.client\.(getIRISList|classMethodIRISList|functionIRISList)$", ("O", "irislist")),
    # --------------------------------------------------- process identity
    (r"^os\.fn\.\$JOB$", ("I", ["E-CALLER"])),
    (r"^py\.client\.(classMethodValue|classMethodVoid|classMethodString|classMethodInteger|classMethodBoolean|"
     r"classMethodBytes|classMethodFloat|classMethodObject|classMethodDecimal|createIRIS|procedure|functionInt|"
     r"functionString|functionBytes|invoke|invokeVoid|createConnection|getServerVersion|getAPIVersion)$|"
     r"^py\.iris\.(createIRIS|connect|IRIS|dbapi|createConnection)$", ("I", ["E-CALLER", "E-GLOBALS"])),
    (r"^py\.client\.dbapi\.(execute|cursor)$|^py\.client\.(fetchone|fetchall|fetchmany|lastrowid|callproc)$|"
     r"^py\.sql-text$|^os\.dynamic-sql-text$", ("I", ["E-VIS", "E-ROWLOCK", "E-UNIQUE", "X-STMT", "X-NULL"])),
    (r"^py\.client\.executemany$", V(["X2-BATCH"], "batch")),
    (r"^py\.import\.(iris|intersystems_iris|iris_dbapi|irisnative)$", ("I", ["E-CALLER"])),
    (r"^py\.import\.(iris \(embedded\)|irispython)$|^py\.embedded\.|^cls\.method\.Language=python$|^py\.iris\.(cls|sql|gref|system|execute|ref|lock|unlock|tstart|tcommit|trollback)$",
     ("O", "epy")),
    (r"^py\.import\.sqlalchemy_iris$", ("I", ["E-CALLER", "E-DRV", "E-AUTOCOMMIT"])),
    (r"^py\.dbapi\.error-class$", ("O", "sqlcode")),
    # --------------------------------------------------- SQL statements
    (r"^sql\.verb\.(SELECT)$", ("I", ["E-VIS", "X-STAR", "X-TLEVEL-SQL"])),
    (r"^sql\.verb\.(INSERT|UPDATE|DELETE)$", ("I", ["E-ROWLOCK", "E-UNIQUE", "E-VIS", "X-STMT"])),
    (r"^sql\.verb\.INSERT \.\.\. SELECT$", ("I", ["X-STMT", "E-UNIQUE"])),
    (r"^sql\.verb\.SELECT \.\.\. INTO :host$|^sql\.verb\.(DECLARE CURSOR|FETCH)$", V(["E-1"], "esql-other")),
    (r"^sql\.verb\.INSERT OR UPDATE$", V(["X2-IOU"], "iou")),
    (r"^sql\.verb\.BUILD INDEX$", ("I", ["X-NOINDEX"])),
    (r"^sql\.verb\.(PURGE INDEX|TRUNCATE TABLE)$", ("O", "ddl-other")),
    (r"^sql\.verb\.CALL$|^cls\.method\.SqlProc$|^sql\.ddl\.(CREATE|DROP) (FUNCTION|PROCEDURE|QUERY|METHOD)$|^sql\.routine\.",
     V(["S-1"], "sqlroutine", "S-1 covers the pin's Txn_Begin/End/Undo [SqlProc] (env2-e1-r2); other routines rest on "
                              "the same premise")),
    (r"^sql\.verb\.(GRANT|REVOKE)$", ("O", "security")),
    (r"^sql\.verb\.SET OPTION$", ("O", "isolation")),
    (r"^sql\.ddl\.(CREATE TABLE|DROP TABLE|ALTER TABLE ADD COLUMN)$", ("I", ["X-DDL", "X-STAR"])),
    (r"^sql\.ddl\.CREATE GLOBAL TEMPORARY TABLE$", ("O", "temp")),
    (r"^sql\.ddl\.(CREATE (UNIQUE |BITMAP )?INDEX|DROP INDEX|CREATE VIEW|DROP VIEW|ALTER TABLE .*|CREATE SCHEMA|DROP SCHEMA|"
     r"CREATE TRIGGER|DROP TRIGGER)$", ("O", "ddl-other")),
    (r"^sql\.pct\.%(NOINDEX|NOCHECK)$|^sql\.pct\.%IGNOREINDEX \*$", ("I", ["X-NOINDEX"])),
    (r"^sql\.pct\.%IGNOREINDEX( named)?$", ("O", "plan")),
    (r"^sql\.pct\.%(NOLOCK|NOJOURN|NOTRIGGER|KEEPLOCK)$", ("O", "isolation")),
    (r"^sql\.pct\.%(PARALLEL|NOPARALLEL|PROFILE|PROFILE_ALL|FIRSTTABLE|INORDER|NOFLATTEN|NOMERGE|NOREDUCE|NOSVSO|"
     r"NOTOPOPT|NOUNIONOROPT|ALLINDEX|NOFPLAN|STARTTABLE|FULL|IGNOREINDICES)$", ("O", "plan")),
    (r"^sql\.pct\.%(FIND)$|^sql\.fn\.SEARCH_INDEX$", ("I", ["X-FX"])),
    (r"^sql\.pct\.%(ID|VID|TABLENAME|CLASSNAME|ROWID)$|^sql\.constraint\.IDENTITY$", ("O", "rowid")),
    (r"^sql\.pct\.%(EXACT|SQLUPPER|SQLSTRING|UPPER|ALPHAUP|STRING|TRUNCATE|MVR|PLUS|MINUS|LIST|INTERNAL|EXTERNAL|ODBCIN|ODBCOUT)$",
     ("O", "sqlexpr")),
    (r"^sql\.pct\.%(STARTSWITH|INLIST|MATCHES|PATTERN|CONTAINS|CONTAINSTERM|SIMILARITY|INSUB|OBJECT|OID|KEY|VALUE)$",
     ("O", "sqlexpr")),
    (r"^sql\.pct\.%(CLASSPARAMETER|PUBLICROWID|EXTENTSIZE|DESCRIPTION|FILE|ROUTINE|NUMROWS)$", ("O", "ddl-other")),
    (r"^sql\.pct\.%(COMMITMODE)$", ("O", "isolation")),
    (r"^sql\.pct\.%(DYNAMICOBJECT|LIBRARY|DYNAMICARRAY)$", ("O", "json")),
    (r"^sql\.pct\.%(IFIND)$", ("O", "ifind")),
    (r"^sql\.pct\.%(EMBEDDING)$", ("O", "embedding")),
    (r"^sql\.pct\.%(SQLCODE|ROWCOUNT|MSG|ROWID)$", ("I", ["E-VIS", "X-STMT"])),
    (r"^sql\.pct\.%(CREATE_\w+|DROP_\w+|ALTER_\w+|DB_\w+|ADMIN_\w+|USE_\w+|NOCHECK_PRIV|NOTRIGGER_PRIV)$", ("O", "security")),
    (r"^sql\.pct\.%(NORUNTIME|RUNTIME|NOCSE|NOJOIN|PARALLEL)$", ("O", "plan")),
    (r"^sql\.pct\.%(VECTOR)$", ("I", ["X-VEC"])),
    (r"^sql\.pct\.%(DICTIONARY|SYS|SQL_DIAG|SQL|SYSTEM)$", ("O", "catalog")),
    (r"^sql\.pct\.%(STREAM|GLOBALCHARACTERSTREAM|GLOBALBINARYSTREAM)$", ("O", "stream")),
    (r"^sql\.fn\.COALESCE$", ("I", ["X-NULL"])),
    (r"^sql\.fn\.(TO_VECTOR|VECTOR_COSINE|VECTOR_DOT_PRODUCT|VECTOR_L2)$|^sql\.type\.VECTOR$", ("I", ["X-VEC"])),
    (r"^sql\.fn\.EMBEDDING$", ("O", "embedding")),
    (r"^sql\.fn\.(JSON_OBJECT|JSON_ARRAY|JSON_TABLE|JSON_VALUE|JSON_QUERY|JSON_ARRAYAGG|JSON_OBJECTAGG|JSON_EXISTS)$",
     V(["X2-JSON"], "json")),
    (r"^sql\.fn\.(CURRENT_TIMESTAMP|GETDATE|NOW|GETUTCDATE|CURDATE|CURTIME|DATEDIFF|DATEADD|DATEPART|TIMESTAMPADD|"
     r"TIMESTAMPDIFF|SYSDATE|CURRENT_DATE|UNIX_TIMESTAMP|TO_TIMESTAMP|TO_DATE|TO_CHAR|DATENAME|YEAR|MONTH|DAY|HOUR|"
     r"MINUTE|SECOND|LAST_DAY|DAYOFWEEK|WEEK)$", ("O", "clock")),
    (r"^sql\.fn\.\$(HOROLOG)$", ("O", "clock")),
    (r"^sql\.fn\.\$(LIST\w*)$", V(["X2-LIST"], "list")),
    (r"^sql\.fn\.\$(JOB|NAMESPACE|USERNAME|SYSTEM)$", ("O", "mgmt")),
    (r"^sql\.fn\.\$(PIECE|EXTRACT|LENGTH|ZSTRIP|ZCONVERT)$", ("O", "pure")),
    (r"^sql\.fn\.(HASH|SHA1|SHA256|MD5|CRC32)$", ("O", "hash")),
    (r"^sql\.fn\.(RAND|RANDOM|NEWID|UUID)$", ("O", "random")),
    (r"^sql\.fn\.", ("O", "sqlexpr")),
    (r"^sql\.type\.", ("O", "sqlexpr")),
    (r"^sql\.clause\.(TOP|LIMIT|OFFSET)$", V(["X2-TOP"], "top")),
    (r"^sql\.clause\.FETCH FIRST$", ("O", "fetchfirst")),
    (r"^sql\.clause\.(NOT EXISTS)$", ("I", ["E-VIS", "E-UNIQUE", "X-STMT"])),
    (r"^sql\.clause\.(parameter \?)$", ("I", ["X-NULL"])),
    (r"^sql\.clause\.(WHERE CURRENT OF|FOR UPDATE)$", ("O", "esql-other")),
    (r"^sql\.clause\.", ("O", "sqlexpr")),
    (r"^sql\.constraint\.(PRIMARY KEY|UNIQUE)$", ("I", ["E-UNIQUE"])),
    (r"^sql\.constraint\.NOT NULL$", V(["E-1"], "sqlcode", "NOT NULL violations report -108 on the embedded path "
                                                         "(env2-e1-r1 e1-null-empty-host)")),
    (r"^sql\.constraint\.(FOREIGN KEY|ON DELETE/UPDATE action)$", ("O", "fk")),
    (r"^sql\.constraint\.(DEFAULT|CHECK|WITH %CLASSPARAMETER)$", ("O", "ddl-other")),
    (r"^sql\.indextype\.HNSW$", ("O", "hnsw")),
    (r"^sql\.indextype\.%iFind", ("IR", ["X-FX"], "ifind")),
    (r"^sql\.indextype\.functional:", ("I", ["X-FX"])),
    (r"^sql\.indextype\.(BITMAP|BITSLICE)$", ("O", "ddl-other")),
    (r"^sql\.catalog\.INFORMATION_SCHEMA\.(TABLES|COLUMNS)$", ("I", ["X-DDL"])),
    (r"^sql\.catalog\.", ("O", "catalog")),
    # --------------------------------------------------- class members
    (r"^cls\.index\.As:%iFind", ("O", "ifind")),
    (r"^cls\.index\.As:functional\(product\)$|^cls\.extends\.%Library\.FunctionalIndex$|^cls\.extends\.%FunctionalIndex$",
     ("I", ["X-FX"])),
    (r"^os\.pct(method|string)\.%(BuildIndices|PurgeIndices|BuildIndicesAsync|SortBegin|SortEnd)$", ("O", "buildindices")),
    (r"^os\.pctstring\.%SYS$", ("O", "ns")),
    (r"^os\.pctstring\.%(All|Developer|Manager|Operator|SQL|DB_\w+|Admin_\w+|Development|Service_\w+)$", ("O", "security")),
    (r"^os\.pctstring\.%(Library\.)?(DynamicArray|DynamicObject|DynamicAbstractObject)$", ("O", "json")),
    (r"^os\.pctstring\.%(Save|OpenId|DeleteId|ExistsId|KillExtent|New)$", ("O", "persistent")),
    (r"^sql\.table\.HS_\*$", ("O", "absent")),
    (r"^sql\.table\.(Security|%SYS|SYS|Config)$", ("O", "security")),
    (r"^sql\.table\.Ens", ("O", "absent")),
    (r"^cls\.persistent$|^cls\.extends\.%(Library\.)?Persistent$|^cls\.index|^cls\.member\.(Relationship|ForeignKey)$|"
     r"^os\.pctmethod\.%(Save|OpenId|Open|DeleteId|Delete|ExistsId|Exists|KillExtent|"
     r"LockId|UnlockId|LockExtent|UnlockExtent|SaveDirect|Reload|Id|Oid|ObjectId|SortBegin|SortEnd|ValidateObject|"
     r"OnBeforeSave|OnAfterSave|OnDelete|ComposeOid)$", ("O", "persistent")),
    (r"^cls\.member\.Trigger$", ("O", "trigger")),
    (r"^cls\.member\.(Query|Projection|XData)$|^cls\.method\.CodeMode=objectgenerator$|^cls\.method\.Language=other$",
     ("O", "dict")),
    (r"^cls\.property\.As %(Stream|Library\.Global|Library\.File|Library\.Stream)|^cls\.signature\.As %Stream",
     ("O", "stream")),
    (r"^cls\.property\.As %(Library\.)?Dynamic|^cls\.signature\.As %(Library\.)?Dynamic", V(["X2-JSON"], "json")),
    (r"^cls\.property\.As %(Library\.)?(List|Array|ListOf|ArrayOf)", V(["X2-LIST"], "list")),
    (r"^cls\.property\.As %(Library\.)?Vector|^cls\.signature\.As %(Library\.)?Vector", ("I", ["X-VEC"])),
    (r"^cls\.signature\.As %(SQL\.|Library\.ResultSet|ResultSet)", ("I", ["E-VIS", "X-STMT"])),
    (r"^cls\.signature\.As %(Library\.)?Status$", ("O", "status")),
    (r"^cls\.property\.", ("O", "language")),
    (r"^cls\.extends\.%(CSP\.|ZEN\.)", ("O", "web")),
    (r"^cls\.extends\.%(SYS\.Task)", ("O", "task")),
    (r"^cls\.extends\.%(SYSTEM\.WorkMgr|SYS\.WorkQueue)", ("O", "job")),
    (r"^cls\.extends\.(HS\.|%AI)", ("O", "absent")),
    (r"^cls\.extends\.%(Library\.)?(RegisteredObject|SerialObject|SystemBase|Exception\.\w+|DataType|String|Integer|"
     r"Projection\.\w+|XML\.Adaptor|JSON\.Adaptor|SQLQuery|Query)", ("O", "language")),
    (r"^cls\.extends\.%(Library\.)?(DynamicAbstractObject|DynamicObject|DynamicArray)", ("O", "json")),
    (r"^cls\.extends\.%(Library\.)?(GlobalCharacterStream|Stream)", ("O", "stream")),
    (r"^cls\.extends\.%(Net|Library\.File|File)", ("O", "file")),
    # --------------------------------------------------- ObjectScript functions
    (r"^os\.fn\.\$(PIECE|EXTRACT|LENGTH|SELECT|CASE|CHAR|ASCII|FIND|TRANSLATE|REPLACE|REVERSE|JUSTIFY|FNUMBER|NUMBER|"
     r"NORMALIZE|DOUBLE|DECIMAL|ISVALIDNUM|ZABS|ZSQR|ZLN|ZLOG|ZEXP|ZPOWER|ZHEX|ISOBJECT|MATCH|LOCATE|ZCONVERT|BIT|"
     r"BITCOUNT|BITFIND|BITLOGIC|FACTOR|ZBOOLEAN|ZWASCII|ZWCHAR|ZLASCII|ZLCHAR|ZQASCII|ZQCHAR|ZSIN|ZCOS|ZTAN|ZARCSIN|"
     r"ZARCCOS|ZARCTAN|ZPI|ZWPACK|ZWUNPACK|ZWBPACK|ZWBUNPACK|ZPOSITION|ZWIDTH|INUMBER|IEXTRACT|ZDASCII|ZDCHAR|"
     r"ZCYC|ZSEEK|ZNAME|ZSTRIP_|TEXT|NEXT|ZDATE_|ZPREVIOUS|ZORDER|ZSEARCH|ZBITAND|ZBITOR|ZBITNOT|ZBITGET|ZBITSET|"
     r"ZBITLEN|ZBITSTR|ZBITCOUNT|ZBITFIND|ZBITXOR|STORAGE|ZSTORAGE|QUIT|STACK|ESTACK|X|Y|IO|PRINCIPAL|THIS|ZREFERENCE|"
     r"ZEOF|ZA|ZB|ZMODE|ZCHILD_)$", ("O", "pure")),
    (r"^os\.fn\.\$ZSTRIP$", ("I", ["X-ZSTRIP"])),
    (r"^os\.fn\.\$(ZCRC)$", ("O", "hash")),
    (r"^os\.fn\.\$(HOROLOG|ZHOROLOG|ZTIMESTAMP|NOW|ZDATETIME|ZDATETIMEH|ZDATE|ZDATEH|ZTIME|ZTIMEH|ZTIMEZONE|ZUTIL)$",
     ("O", "clock")),
    (r"^os\.fn\.\$RANDOM$", ("O", "random")),
    (r"^os\.fn\.\$(LIST|LISTBUILD|LISTGET|LISTLENGTH|LISTNEXT|LISTFIND|LISTFROMSTRING|LISTTOSTRING|LISTSAME|"
     r"LISTDATA)$", V(["X2-LIST"], "list")),
    (r"^os\.fn\.\$(LISTVALID|LISTUPDATE)$", ("O", "list")),
    (r"^os\.fn\.\$(VECTOR|ISVECTOR|VECTORDEFINED)$", ("I", ["X-VEC"])),
    (r"^os\.fn\.\$(VECTOROP|VECTORS)$", ("O", "vecop")),
    (r"^os\.fn\.\$(CLASSMETHOD|CLASSNAME|METHOD|PARAMETER|PROPERTY)$", ("O", "dict")),
    (r"^os\.fn\.\$(NAMESPACE|ZNSPACE)$|^os\.cmd\.(ZNSPACE|NEW \$NAMESPACE)$", ("O", "ns")),
    (r"^os\.fn\.\$(USERNAME|ROLES)$", ("O", "security")),
    (r"^os\.fn\.\$(ZERROR|ECODE|ETRAP|ZTRAP)$|^os\.cmd\.(ZTRAP|BREAK)$", ("O", "status")),
    (r"^os\.fn\.\$ZF$", ("O", "zf")),
    (r"^os\.fn\.\$(ZVERSION|ZPARENT|ZCHILD|ZJOB|SYSTEM|ZHOROLOG_)$", ("O", "mgmt")),
    (r"^os\.fn\.\$(INCREMENT)$", ("I", ["E-INCR"])),
    (r"^os\.fn\.\$VIEW$|^os\.cmd\.VIEW$", ("O", "sysglobal")),
    # --------------------------------------------------- commands
    (r"^os\.cmd\.JOB$", ("O", "job")),
    (r"^os\.cmd\.HANG$", ("O", "clock")),
    (r"^os\.cmd\.HALT$", ("I", ["E-STOP"])),
    (r"^os\.cmd\.(OPEN|USE|CLOSE|READ)$", ("O", "file")),
    (r"^os\.cmd\.(WRITE|ZWRITE)$", ("O", "device")),
    (r"^os\.embedded-web$", ("O", "web")),
    # --------------------------------------------------- macros and %-methods
    (r"^os\.macro\.\$\$\$(OK|ERROR|ISERR|ISOK|ThrowStatus|ThrowOnError|GeneralError|ThrowSQLIfError|ThrowSQLCODE|"
     r"AppError|ERRORCODE|GETERRORCODE|FormatText|FormatTextJS|Text|TextJS|TextHTML|quote|NULLOREF|QuitOnError|"
     r"ISNULLOREF|EncodeErrorText|ThrowIfInterrupted)$", ("O", "status")),
    (r"^os\.macro\.\$\$\$(comClassKeyGet|comMemberKeyGet|comClassDefined|defClassKeyGet|defMemberKeyGet|"
     r"cCLASSsqlschemaname|cCLASSsqltablename|comMemberDefined|defClassDefined|cPROPtype|cCLASSclasstype|"
     r"cPROPcollection|comMemberArrayGet|comClassArrayGet)$", ("O", "dict")),
    (r"^os\.macro\.\$\$\$(LISTERROR|ListValid)", V(["X2-LIST"], "list")),
    (r"^os\.macro\.\$\$\$IF\w+", ("O", "ifind")),
    (r"^os\.pctmethod\.%(Set|Get|ToJSON|FromJSON|IsDefined|Remove|GetTypeOf)$", V(["X2-JSON"], "json")),
    (r"^os\.pctmethod\.%(GetIterator|GetNext|Size|Push|Pop|Clear|Next_|SetAt|GetAt|FromJSONFile|ToJSONFile|Count|"
     r"IsEmpty)$", ("O", "json")),
    (r"^os\.pctmethod\.%(Prepare|Execute|ExecDirect|Next|GetData|Close|DisplayFormatted|GetRows|SQLCODE|PrepareClassQuery|"
     r"ExecDirectNoPriv|GetMetadata|CurrentResult|NextResult|MoreResults|Display|Print)$|^os\.pctprop\.",
     ("I", ["E-VIS", "E-ROWLOCK", "X-STMT", "X-NULL"])),
    (r"^os\.pctmethod\.%(New|IsA|ClassName|Extends|ConstructClone|PackageName|Close|AddToSaveSet|IsModified|"
     r"SetModified|Normalize|IsValid|LogicalToDisplay|DisplayToLogical|LogicalToOdbc|OdbcToLogical|LogicalToStorage|"
     r"StorageToLogical|XSDToLogical|LogicalToXSD|AsStatus|ThrowIfError|DisplayString|OnNew|DispatchMethod|"
     r"DispatchClassMethod|DispatchGetProperty|DispatchSetProperty|GetParameter|SerializeObject|ClassIsLatestVersion|"
     r"Log|AddCode|OutputToStr|Add|GetProperty|SetProperty|CopyFrom|Rewind|Read|Write|WriteLine|ReadLine|MoveToEnd|"
     r"Size_|AtEnd|SizeGet|Length|Exists_|Find|Matcher|Locate|ReplaceAll|ReplaceFirst|Match|Group|Start|End|"
     r"GetSwizzleObject|ToString|Instance|CreateFromSQLCODE|CreateFromStatus|DisplayError|Code|Name)$",
     ("O", "language")),
    (r"^os\.json\.literal$", ("O", "json")),
    # --------------------------------------------------- system classes
    (r"^os\.class\.%(Library\.)?(DynamicObject|DynamicArray|DynamicAbstractObject):%FromJSON\b", V(["X2-JSON"], "json")),
    (r"^os\.class\.%(Library\.)?(DynamicObject|DynamicArray|DynamicAbstractObject)\b", ("O", "json")),
    (r"^os\.class\.%SQL\.(Statement|StatementResult)\b|^os\.class\.%(Library\.)?ResultSet\b|^os\.class\.%SQL\.",
     ("I", ["E-VIS", "E-ROWLOCK", "X-STMT", "X-NULL"])),
    (r"^os\.class\.%SYSTEM\.SQL(\.Schema)?:(TableExists)$", ("I", ["X-DDL"])),
    (r"^os\.class\.%SYSTEM\.SQL", ("O", "catalog")),
    (r"^os\.class\.%SYSTEM\.Process:(Terminate)$", ("I", ["E-STOP"])),
    (r"^os\.class\.%SYSTEM\.(Process|Util|Version|Config|License|Event|Semaphore|Monitor|Python|INetInfo|SYS)|"
     r"^os\.class\.%SYS\.(ProcessQuery|System|Namespace|Journal|Lock|LockQuery|License|ICMP|Global)|"
     r"^os\.class\.%(Library\.)?(Device|SYS\.Python|SYS\.ClassObj)|^os\.class\.Config\.|^os\.class\.%Monitor",
     ("O", "mgmt")),
    (r"^os\.class\.%SYSTEM\.(Encryption)|^os\.class\.%(Library\.)?(Hash|Base64)|^os\.class\.%SYSTEM\.Util:CreateGUID",
     ("O", "hash")),
    (r"^os\.class\.%SYSTEM\.(OBJ|Dictionary)|^os\.class\.%Dictionary\.|^os\.class\.%(Library\.)?(ClassDefinition|"
     r"CompiledClass|Routine|RoutineMgr)|^os\.class\.%Studio", ("O", "dict")),
    (r"^os\.class\.%SYSTEM\.(WorkMgr)|^os\.class\.%SYS\.WorkQueue", ("O", "job")),
    (r"^os\.class\.%SYS\.Task", ("O", "task")),
    (r"^os\.class\.%(Stream\.|Library\.(GlobalCharacterStream|GlobalBinaryStream|FileCharacterStream|"
     r"FileBinaryStream|Stream))", ("O", "stream")),
    (r"^os\.class\.%(Library\.)?File\b|^os\.class\.%(Stream\.File|Net\.|SYS\.Journal\.File)", ("O", "file")),
    (r"^os\.class\.%iFind", ("O", "ifind")),
    (r"^os\.class\.%Embedding|^os\.class\.%(SQL\.)?Embedding", ("O", "embedding")),
    (r"^os\.class\.(%AI|HS\.|%HS)", ("O", "absent")),
    (r"^os\.class\.%(CSP|ZEN|REST|Net\.HttpRequest)", ("O", "web")),
    (r"^os\.class\.(Security\.|%SYS\.Security|%SYSTEM\.Security)", ("O", "security")),
    (r"^os\.class\.%Regex", ("O", "pure")),
    (r"^os\.class\.%xsd\.", ("O", "pure")),
    (r"^os\.class\.(SYS|Config)\.", ("O", "mgmt")),
    (r"^os\.class\.%(Exception\.|SYSTEM\.Status|Library\.Status|Status)", ("O", "status")),
    (r"^os\.class\.%(Library\.)?(PosixTime|TimeStamp|Date|Time|UTC)", ("O", "clock")),
    (r"^os\.class\.%(Library\.)?(List|ListOfDataTypes|ArrayOfDataTypes|ListOfObjects|ArrayOfObjects)", V(["X2-LIST"], "list")),
    (r"^os\.class\.%(Library\.)?(Vector)", ("I", ["X-VEC"])),
    (r"^os\.class\.%(Library\.)?(Persistent)|^os\.class\.%ExtentMgr", ("O", "persistent")),
    (r"^os\.class\.%(Library\.)?(RegisteredObject|String|Integer|Numeric|Boolean|Double|Decimal|Binary|Utility|"
     r"Function|SerialObject|Collation|XML\.|JSON\.Formatter|JSON\.Adaptor|MessageDictionary|Text|ZEN\.Auxiliary)",
     ("O", "language")),
    (r"^os\.class\.%(Library\.)?(FunctionalIndex)", ("I", ["X-FX"])),
    (r"^os\.class\.(Ens|EnsLib)", ("O", "absent")),
    (r"^py\.native\.classmethod:%SYSTEM\.Process", ("O", "mgmt")),
    (r"^py\.native\.classmethod:%SYSTEM\.SYS$", ("I", ["E-CALLER"])),
    (r"^py\.native\.classmethod:%(Compiler\.|Routine|Library\.Routine)", ("O", "dict")),
    (r"^py\.native\.classmethod:%Stream\.File", ("O", "file")),
    (r"^py\.native\.classmethod:%Stream\.", ("O", "stream")),
    (r"^py\.native\.classmethod:%SYS\.", ("O", "mgmt")),
    (r"^py\.native\.classmethod:%SYSTEM\.Version|^py\.native\.classmethod:%SYSTEM\.(Util|License|Config)", ("O", "mgmt")),
    (r"^py\.native\.classmethod:%SYSTEM\.(OBJ|Dictionary)|^py\.native\.classmethod:%Dictionary", ("O", "dict")),
    (r"^py\.native\.classmethod:%SYSTEM\.SQL", ("O", "catalog")),
    (r"^py\.native\.classmethod:%SYSTEM\.Encryption", ("O", "hash")),
    (r"^py\.native\.classmethod:%(Library\.)?(File)", ("O", "file")),
    (r"^py\.native\.classmethod:%SYSTEM\.(Status)", ("O", "status")),
    (r"^py\.native\.classmethod:%(Library\.)?(DynamicObject|DynamicArray)", V(["X2-JSON"], "json")),
    (r"^py\.native\.classmethod:%SQL", ("I", ["E-VIS", "X-STMT"])),
    (r"^py\.native\.classmethod:%iFind", ("O", "ifind")),
    (r"^py\.native\.classmethod:%(SYS\.Task)", ("O", "task")),
    # --------------------------------------------------- SQLCODEs
    (r"^sqlcode\.(0/100)$", ("I", ["E-ROWLOCK", "X-STMT"])),
    (r"^os\.SQLCODE-variable$", V(["E-1"], "esql-other", "embedded SQL's SQLCODE: 0, 100, -104, -108, -119 observed "
                                                        "as the dynamic path reports them (env2-e1-r1)")),
    (r"^os\.%msg-variable$", ("O", "status")),
    (r"^py\.iris-error-name\.<LIST ERROR>$", ("IR", ["X-NOINDEX"], "buildindices")),
    (r"^py\.iris-error-name\.", ("O", "status")),
    (r"^sqlcode\.(-30|-110|-201|-400)$", ("I", ["X-DDL", "X-NOINDEX"])),
    (r"^sqlcode\.-119$", ("I", ["E-UNIQUE", "X-STMT"])),
    (r"^sqlcode\.-359$", ("I", ["X-VEC"])),
    (r"^sqlcode\.(-104|-108)$", V(["E-1"], "sqlcode", "-104 (MAXLEN) and -108 (NOT NULL) observed alike on the embedded "
                                                     "and dynamic paths (env2-e1-r1 e1-sqlcode-104, e1-null-empty-host)")),
    (r"^sqlcode\.", ("O", "sqlcode")),
    # --------------------------------------------------- configuration
    (r"^cfg\.", ("O", "config")),
]


def classify(feat: str, validated: dict, rules=None):
    for pat, how in (rules or RULES):
        if re.search(pat, feat):
            if how[0] == "I":
                return {"status": IN, "clauses": how[1]}
            if how[0] == "IR":  # inside for the clause; a residual premise for what the clause does not decide
                prem, cons = FAM[how[2]]
                return {"status": IN, "clauses": how[1], "residual": {"family": how[2], "premise": prem}}
            if how[0] == "O":
                prem, cons = FAM[how[1]]
                return {"status": OUT, "family": how[1], "premise": prem, "consequence": cons}
            _, clauses, fb, note = how
            runs = [validated["clauses"].get(c) for c in clauses]
            if all(r and r.get("result") == "pass" for r in runs):
                d = {"status": VA, "clauses": clauses, "runs": sorted({x for r in runs for x in r["runs"]})}
                if note:
                    d["note"] = note
                prem, cons = FAM[fb]
                d["residual"] = {"family": fb, "premise": prem}
                return d
            prem, cons = FAM[fb]
            return {"status": OUT, "family": fb, "premise": prem, "consequence": cons,
                    "pending_validation": clauses}
    return None


# ------------------------------------------------------------------------------------------------ main
SITES: dict = {}


def enumerate_modules(inject=None, rules=None):
    """inject: {module: (file, text)} appended to that file (self-test)."""
    regs = regions()
    found = {m: Found() for m in ALL_MODULES}
    for path, by_mod in sorted(regs.items()):
        for m, keep in by_mod.items():
            if m not in found:
                continue
            extra = ""
            if inject and m in inject and inject[m][0] == path:
                extra = inject[m][1]
                n0 = len((REPO / path).read_text(errors="replace").splitlines()) + 1
                base_keep = keep
                keep = (lambda i, b=base_keep, n0=n0: True if i >= n0 else b(i))
            lex_file(path, keep, found[m], extra)
    validated = load_validated()
    SITES.clear()
    SITES.update({m: dict(found[m].f) for m in ALL_MODULES})
    result = {}
    for m in ALL_MODULES:
        feats = []
        for feat, sites in sorted(found[m].f.items()):
            c = classify(feat, validated, rules)
            row = {"feature": feat, "occurrences": len(sites), "sites": sites[:5]}
            row.update(c if c else {"status": "unclassified"})
            feats.append(row)
        counts = {s: sum(1 for r in feats if r["status"] == s) for s in (IN, VA, OUT, "unclassified")}
        result[m] = {"features": feats, "counts": counts,
                     "cell": "closed" if counts["unclassified"] == 0 else "open",
                     "outside_premises": sorted({r["premise"].split(":")[0] for r in feats if r["status"] == OUT}),
                     "validated_clauses": sorted({c for r in feats if r["status"] == VA for c in r["clauses"]})}
    return result


# Old reasons (iris-contract/COVERAGE.json, the breadth lanes' env_features) that name a semantic limit or an oracle
# rather than a source token: carried into the module's features as `sem.*` outside features (crosscheck.py lists
# them as not_token_features).
SEMANTIC = [("engine limits", "sem.engine-limits", "limits"), ("the journal is the audit's oracle", "sem.journal-oracle", "oracle"),
            ("SQL text parsing", "sem.sql-text-parsing", "sqlparse"), ("the bitmap extent", "sem.bitmap-extent", "bitmap"),
            ("Native API subscript validation", "sem.native-subscripts", "subscript")]


def add_semantic(result):
    old = json.loads((PC / "iris-contract" / "COVERAGE.json").read_text())["modules"]
    for m, d in old.items():
        if m not in result:
            continue
        for f in d["features"]:
            if f.get("status") != "outside-subset":
                continue
            for pre, fid, fam in SEMANTIC:
                if f["reason"].startswith(pre):
                    prem, cons = FAM[fam]
                    rows = result[m]["features"]
                    if not any(r["feature"] == fid for r in rows):
                        rows.append({"feature": fid, "occurrences": 1, "sites": [f.get("source", "")],
                                     "status": OUT, "family": fam, "premise": prem, "consequence": cons,
                                     "source_of_feature": "iris-contract/COVERAGE.json (breadth lanes' env_features)"})
                        result[m]["counts"][OUT] += 1
                        result[m]["outside_premises"] = sorted(set(result[m]["outside_premises"]) | {prem.split(":")[0]})


def selftest() -> int:
    ok = True
    # (a) a seeded unclassified feature in module 02 is reported and keeps the cell open
    f02 = "iris_src/src/Graph/KG/GraphKey.cls"
    seed = ('ClassMethod ZZSeed() As %Integer\n{\n\tSet x = $ZZSEEDED(1)\n\tSet y = ##class(%ZZSeed.Thing).Run()\n'
            '\tSet rs = ##class(%SQL.Statement).%ExecDirect(, "SELECT ZZSEEDFN(k) FROM t")\n'
            '\t// LOCK +^ZZCommentOnly  (a comment: must not be reported)\n\tQuit 1\n}\n')
    res = enumerate_modules(inject={"02": (f02, seed)})
    feats = {r["feature"]: r for r in res["02"]["features"]}
    a1 = feats.get("os.fn.$ZZSEEDED", {}).get("status") == "unclassified"
    a2 = res["02"]["cell"] == "open"
    a3 = "os.lock.incremental" not in feats or all("ZZ" not in s for s in feats["os.lock.incremental"]["sites"])
    a4 = any(f.startswith("os.class.%ZZSeed") for f in feats) and any(f == "sql.fn.ZZSEEDFN" for f in feats)
    # (b) a known feature seeded into module 05 appears, classified
    f05 = None
    inv = json.loads(INVENTORY.read_text())
    for f in inv["files"]:
        if f["owners"] == ["05"] and f["file"].endswith(".cls"):
            f05 = f["file"]; break
    seed5 = 'ClassMethod ZZSeed5()\n{\n\tTSTART\n\tSet x = $SEQUENCE(^IVGAuditZZ)\n\tTCOMMIT\n}\n'
    res5 = enumerate_modules(inject={"05": (f05, seed5)})
    f5 = {r["feature"]: r for r in res5["05"]["features"]}
    b1 = f5.get("os.fn.$SEQUENCE", {}).get("status") in (IN, VA, OUT)
    b2 = any(f05 + ":" in s for s in f5.get("os.fn.$SEQUENCE", {}).get("sites", []))
    # (c) removing every rule that classifies into JSON (family json, or clause X2-JSON) leaves module 11's JSON
    # features unclassified (none is silently picked up by another rule)
    def is_json(how):
        return (how[0] == "O" and how[1] == "json") or (how[0] == "V" and (how[2] == "json" or "X2-JSON" in how[1]))
    base = enumerate_modules()
    json_feats = {r["feature"] for r in base["11"]["features"]
                  if r.get("family") == "json" or "X2-JSON" in r.get("clauses", [])
                  or (r.get("residual") or {}).get("family") == "json"}
    res3 = enumerate_modules(rules=[(p, h) for p, h in RULES if not is_json(h)])
    after = {r["feature"]: r["status"] for r in res3["11"]["features"]}
    c1 = bool(json_feats) and all(after.get(f) == "unclassified" for f in json_feats)
    ok = a1 and a2 and a3 and a4 and b1 and b2 and c1
    report = {"a_seeded_unclassified_reported": a1, "a_cell_open": a2, "a_comment_not_reported": a3,
              "a_seeded_class_and_sql_function_found": a4, "b_known_feature_found_and_classified": b1,
              "b_site_attributed": b2, "c_removed_rule_leaves_unclassified": c1,
              "c_json_features_of_module_11": sorted(json_feats), "pass": ok}
    print(json.dumps(report, indent=1))
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE / "coverage.json"
    res = enumerate_modules()
    add_semantic(res)
    for m in res.values():  # premise and consequence live once per family (doc["families"])
        for r in m["features"]:
            r.pop("premise", None)
            r.pop("consequence", None)
            if isinstance(r.get("residual"), dict):
                r["residual"].pop("premise", None)
    doc = {"pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e", "method": __doc__.strip().split("\n\n")[0],
           "inventory": str(INVENTORY.relative_to(REPO)), "validated": str(VALIDATED.relative_to(REPO)),
           "families": {k: {"premise": v[0], "consequence": v[1]} for k, v in FAM.items()}, "modules": res}
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    if "--sites" in sys.argv:  # every site of every feature (raw, for crosscheck.py)
        Path(sys.argv[sys.argv.index("--sites") + 1]).write_text(json.dumps(
            {m: {f: s for f, s in SITES[m].items()} for m in SITES}))
    unc = 0
    for m in ALL_MODULES:
        c = res[m]["counts"]
        unc += c["unclassified"]
        print(m, c, res[m]["cell"])
        for r in res[m]["features"]:
            if r["status"] == "unclassified":
                print("   unclassified:", r["feature"], r["sites"][:2])
    return 1 if (unc and "--check" in sys.argv) else 0


if __name__ == "__main__":
    raise SystemExit(main())
