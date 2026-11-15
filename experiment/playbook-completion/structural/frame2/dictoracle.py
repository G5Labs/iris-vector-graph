"""DDL / dictionary frame oracle of the structural lane (frame2), read-only.

Three independent views of what an action did to the schema, none compiled, none written by the oracle:
  1. catalog snapshot before/after (SQL): INFORMATION_SCHEMA TABLES, COLUMNS, INDEXES, TABLE_CONSTRAINTS, ROUTINES
     (with LAST_ALTERED), VIEWS; %Dictionary.CompiledClass (Name, TimeChanged) and CompiledStorage locations; the
     namespace's global directory (^$GLOBAL, non-% names) read in an `iris session` terminal.
  2. the IRIS journal with keep_system=True: catalog-global records (^oddDEF/^oddCOM/^oddEXT/^oddMAP/^oddSQL/
     ^oddTSQL/^oddPROC/^ROUTINE/^rOBJ/^rMAP/^rINDEX/^rINDEXSQL), classified to the schema object they belong to
     (class, SQL table, routine; cached queries %sqlcq.* and the statement index ^rINDEXSQL are IRIS's own
     maintenance at prepare time and reported apart).
  3. the SQL text the product's Python code executed (iris.dbapi.Cursor.execute wrapped in this process), DDL verbs
     only.
check(frame, diff, catalog_recs) answers the objects outside the action's declared frame.
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "live"))
import lib  # noqa: E402
from lib import J  # noqa: E402

import iris.dbapi  # noqa: E402

CATALOG = ("^oddDEF", "^oddCOM", "^oddEXT", "^oddEXTR", "^oddMAP", "^oddSQL", "^oddTSQL", "^oddPROC", "^oddDEP", "^oddPKG",
           "^ROUTINE", "^rOBJ", "^rMAP", "^rINDEX", "^rINDEXSQL", "^rINDEXCLASS", "^rINDEXEXT", "^oddStudio", "^rBACKUP",
           "^oddXML", "^ISC.Src.Jrn")
DDL_RX = re.compile(r"^\s*(CREATE|DROP|ALTER|TRUNCATE|BUILD\s+INDEX|GRANT|REVOKE)\b", re.I)

# ------------------------------------------------------------------------------------------------ SQL capture
_CAP = {"on": False, "sql": []}
_oe, _om = iris.dbapi.Cursor.execute, iris.dbapi.Cursor.executemany


def _exec(self, op, *a, **k):
    if _CAP["on"]:
        _CAP["sql"].append(str(op))
    return _oe(self, op, *a, **k)


def _many(self, op, *a, **k):
    if _CAP["on"]:
        _CAP["sql"].append(str(op))
    return _om(self, op, *a, **k)


iris.dbapi.Cursor.execute = _exec
iris.dbapi.Cursor.executemany = _many


def hsql(c, q, *p):
    was = _CAP["on"]
    _CAP["on"] = False
    try:
        return c.sql(q, *p)
    finally:
        _CAP["on"] = was


# ------------------------------------------------------------------------------------------------ snapshot
def S(v):
    return "" if v is None else str(v)


def snapshot(c) -> dict:
    nsys = "NOT (TABLE_SCHEMA %STARTSWITH '%') AND TABLE_SCHEMA <> 'INFORMATION_SCHEMA'"
    snap = {}
    snap["tables"] = {f"{S(a)}.{S(b)}": S(t) for a, b, t in hsql(c, f"SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES WHERE {nsys}")}
    snap["columns"] = {f"{S(a)}.{S(b)}.{S(n)}": f"{S(t)}({S(l)}) null={S(u)}" for a, b, n, t, l, u in hsql(
        c, f"SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE {nsys}")}
    snap["indexes"] = {f"{S(a)}.{S(b)}.{S(n)}.{S(o)}": f"{S(col)} nonunique={S(nu)} pk={S(pk)}" for a, b, n, o, col, nu, pk in hsql(
        c, f"SELECT TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, ORDINAL_POSITION, COLUMN_NAME, NON_UNIQUE, PRIMARY_KEY FROM INFORMATION_SCHEMA.INDEXES WHERE {nsys}")}
    snap["constraints"] = {f"{S(a)}.{S(b)}.{S(n)}": S(t) for a, b, n, t in hsql(
        c, f"SELECT TABLE_SCHEMA, TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS WHERE {nsys}")}
    snap["routines"] = {f"{S(a)}.{S(b)}": f"{S(t)} altered={S(la)}" for a, b, t, la in hsql(
        c, "SELECT ROUTINE_SCHEMA, ROUTINE_NAME, ROUTINE_TYPE, LAST_ALTERED FROM INFORMATION_SCHEMA.ROUTINES "
           "WHERE NOT (ROUTINE_SCHEMA %STARTSWITH '%') AND ROUTINE_SCHEMA <> 'INFORMATION_SCHEMA'")}
    snap["classes"] = {S(n): S(t) for n, t in hsql(c, "SELECT Name, TimeChanged FROM %Dictionary.CompiledClass WHERE NOT (Name %STARTSWITH '%')")}
    snap["storage"] = {f"{S(p)}": f"{S(d)}|{S(i)}" for p, d, i in hsql(
        c, "SELECT parent, DataLocation, IndexLocation FROM %Dictionary.CompiledStorage WHERE NOT (parent %STARTSWITH '%')")}
    out = lib.session(' set n="" for  { set n=$order(^$GLOBAL(n)) quit:n=""  if $extract(n,2)\'="%" { write $c(30),"G|",n,! } } write $c(30),"GEND|",! halt\n')
    if not lib.marked(out, "GEND"):
        raise RuntimeError("global directory read did not finish: " + out[-300:])
    snap["globals"] = sorted(lib.marked(out, "G"))
    snap["globals"] = {g.split("|", 1)[1]: "" for g in snap["globals"]}
    out = lib.session(' set n="" for  { set n=$order(^oddTSQL(n)) quit:n=""  set v=$get(^oddTSQL(n)) '
                      'if $listvalid(v),$listlength(v)>1 { write $c(30),"T|",n,"|",$listget(v,1),".",$listget(v,2),! } } '
                      'write $c(30),"TEND|",! halt\n')
    snap["_tsql_ids"] = {x.split("|")[1]: x.split("|")[2] for x in lib.marked(out, "T")}
    return snap


def diff(a: dict, b: dict) -> dict:
    out = {}
    for k in a:
        if k.startswith("_"):
            continue
        x, y = a[k], b[k]
        added = sorted(set(y) - set(x))
        removed = sorted(set(x) - set(y))
        changed = sorted(k2 for k2 in set(x) & set(y) if x[k2] != y[k2])
        if added or removed or changed:
            out[k] = {"added": added, "removed": removed, "changed": changed}
    return out


# ------------------------------------------------------------------------------------------------ journal (catalog)
def lb_strings(raw: bytes, n: int = 2):
    """The first n string elements of an IRIS $ListBuild value (types 1: 8-bit, 2: UTF-16LE)."""
    out, i = [], 0
    while raw and i < len(raw) and len(out) < n:
        ln = raw[i]
        hdr = 1
        if ln == 0:
            ln = int.from_bytes(raw[i + 1:i + 3], "little")
            hdr = 3
            if ln == 0:
                ln = int.from_bytes(raw[i + 3:i + 7], "little")
                hdr = 7
        if ln < hdr + 1 or i + ln > len(raw):
            break
        typ = raw[i + hdr]
        data = raw[i + hdr + 1:i + ln]
        if typ == 1:
            out.append(data.decode("latin-1"))
        elif typ == 2:
            out.append(data.decode("utf-16-le", "replace"))
        else:
            out.append(None)
        i += ln
    return out


def _subs(node: str):
    if node.startswith('^["'):
        node = "^" + node[node.index("]") + 1:]
    m = re.match(r'^\^[^(]+\((.*)\)$', node)
    if not m:
        return []
    return [s[0] if s[0] or not s[1] else s[1] for s in re.findall(r'"((?:[^"]|"")*)"|(-?\d+(?:\.\d+)?)', m.group(1))]


def _catalog_object(node: str, value: bytes = None):
    """(kind, name) of a catalog-global node: class, sqltable, sqlproc, routine, cachedquery, stmtindex, counter."""
    root = J.global_root(node)
    subs = _subs(node)
    first = subs[0] if subs else ""
    if not subs:
        return ("counter", root)
    if root == "^rINDEXSQL":
        return ("stmtindex", first)
    if root == "^oddSQL" and len(subs) >= 2:
        return ("sqltable", f"{subs[0]}.{subs[1]}")
    if root == "^oddTSQL":
        st = lb_strings(value or b"")
        if len(st) >= 2 and st[0] and st[1]:
            return ("sqltable", f"{st[0]}.{st[1]}")
        return ("sqltable-id", first)
    if root == "^oddPROC" and len(subs) >= 2:
        return ("sqlproc", f"{subs[0]}.{subs[1]}")
    if root in ("^ROUTINE", "^rOBJ", "^rMAP", "^rINDEX"):
        name = subs[1] if root == "^rINDEX" and len(subs) > 1 and first in ("ROUTINE", "Routine") else first
        if name.startswith("%sqlcq."):
            return ("cachedquery", name)
        return ("routine", re.sub(r"\.\d+$", "", name))
    if root == "^rINDEXEXT" and len(subs) >= 2:
        return ("class", subs[1])
    if root == "^oddDEP":
        # ^oddDEP(class, type, dependsOn, hash) or ^oddDEP(0, dependsOn, type, class, kind)
        if first == "0" and len(subs) >= 4:
            return ("class", subs[3])
        return ("class", first)
    if root == "^ISC.Src.Jrn":
        return ("class", subs[-1])
    if first.startswith("%sqlcq."):
        return ("cachedquery", first)
    if first.startswith("^"):
        return ("global", first)
    # IRIS's own dictionary bookkeeping under a non-name first subscript: a number, a $Horolog pair, an internal hash
    # with control characters, or a reserved word such as "datatype"; not attributable to one schema object
    if (re.fullmatch(r"-?\d+(\.\d+)?", first) or re.fullmatch(r"\d+,\d+", first) or any(ord(ch) < 32 for ch in first)
            or first in ("datatype",)):
        return ("bookkeeping", root)
    return ("class", first)


def catalog_object(node: str, value: bytes = None):
    """_catalog_object, with any object name that is a number, a $Horolog pair, an internal hash (control characters)
    or a reserved word re-read as IRIS bookkeeping, and a name that is a global reference read as a global."""
    kind, name = _catalog_object(node, value)
    if kind in ("class", "routine") and isinstance(name, str):
        if name.startswith("^"):
            return ("global", name)
        if (re.fullmatch(r"-?\d+(\.\d+)?", name) or re.fullmatch(r"\d+,\d+", name) or any(ord(ch) < 32 for ch in name)
                or name in ("datatype",)):
            return ("bookkeeping", J.global_root(node))
    return (kind, name)


def catalog_records(recs, idmap=None):
    idmap = dict(idmap or {})
    for r in recs:
        g = r.get("g") or ""
        if g.startswith("^oddTSQL("):
            k = catalog_object(g, J.decode(r.get("n")) or J.decode(r.get("o")))
            subs = _subs(g)
            if k[0] == "sqltable" and subs:
                idmap.setdefault(subs[0], k[1])
    objs = {}
    for r in recs:
        g = r.get("g") or ""
        if g and J.global_root(g) in CATALOG:
            kind, name = catalog_object(g, J.decode(r.get("n")) or J.decode(r.get("o")))
            if kind == "sqltable-id" and name in idmap:
                kind, name = "sqltable", idmap[name]
            objs.setdefault((kind, name), 0)
            objs[(kind, name)] += 1
    return objs


def data_records(recs):
    return [r for r in recs if r.get("g") and J.global_root(r["g"]) not in CATALOG]


# ------------------------------------------------------------------------------------------------ capture + check
def run(c, fn, pids=None):
    """Snapshot, journal mark, SQL capture on, fn(), capture off, journal read (keep_system), snapshot."""
    before = snapshot(c)
    m = J.mark()
    _CAP["sql"] = []
    _CAP["on"] = True
    err, res = None, None
    try:
        res = fn()
    except Exception as ex:  # noqa: BLE001
        err = f"{type(ex).__name__}: {str(ex)[:400]}"
    finally:
        _CAP["on"] = False
    try:
        c.conn.commit()
    except Exception:  # noqa: BLE001
        pass
    recs = J.records_since(m, dbs={lib.DB}, pids=pids, keep_system=True)
    after = snapshot(c)
    sqls = list(_CAP["sql"])
    idmap = {**before.get("_tsql_ids", {}), **after.get("_tsql_ids", {})}
    return {"result": res, "error": err, "diff": diff(before, after), "catalog": catalog_records(recs, idmap),
            "storage_before": before["storage"], "storage_after": after["storage"],
            "data_recs": data_records(recs), "ddl_sql": [s for s in sqls if DDL_RX.match(s)], "sql_count": len(sqls),
            "pids": sorted({r["p"] for r in recs})}


def _match(name, patterns):
    n = name.lower()
    return any(fnmatch.fnmatch(n, p.lower()) for p in patterns)


def check(frame: dict, obs: dict) -> list:
    """frame: {'tables': [patterns of schema.table], 'classes': [patterns], 'routines': [patterns],
    'globals': [patterns of ^names]} — the objects the action may create, change or drop. Derived: a table pattern
    also admits its class-name form (schema dots and underscores folded, as IRIS names a DDL table's class and its
    _Extent procedure), a catalog entry named by the schema of a frame table (package level), and the data/index
    globals of the frame's classes (their storage locations in either snapshot).
    Returns the excursions: catalog-diff items and journaled catalog objects outside the frame."""
    exc = []
    tbl, cls, rtn, glb = (list(frame.get(k, [])) for k in ("tables", "classes", "routines", "globals"))
    for p in list(tbl):
        sch, _, name = p.partition(".")
        folded = sch.replace("_", ".") + "." + name.replace("_", "")
        cls.append(folded)
        cls.append(folded + "*")
        tbl.append(f"{sch}.{name.replace('_', '')}*")
        rtn.append(f"{sch}.{name.replace('_', '')}*")
        rtn.append(f"{sch}.{name}*")
    schemas = {p.partition(".")[0].lower() for p in frame.get("tables", [])}
    schemas |= {s.replace("_", ".") for s in schemas}
    for st in (obs.get("storage_before", {}), obs.get("storage_after", {})):
        for c_, loc in st.items():
            if _match(c_, cls):
                for l in loc.split("|"):
                    if l.startswith("^"):
                        glb.append(l.rsplit(".", 1)[0] + ".*" if l.count(".") >= 2 else l + "*")
    for cat, d in obs["diff"].items():
        for kind in ("added", "removed", "changed"):
            for item in d[kind]:
                if cat in ("tables", "columns", "indexes", "constraints"):
                    t_ = ".".join(item.split(".")[:2])
                    ok = _match(t_, tbl)
                elif cat == "routines":
                    ok = _match(item, rtn)
                elif cat in ("classes", "storage"):
                    ok = _match(item, cls)
                elif cat == "globals":
                    ok = _match(item, glb)
                else:
                    ok = False
                if not ok:
                    exc.append(f"catalog {cat} {kind}: {item}")
    for (kind, name), n in obs["catalog"].items():
        if kind in ("stmtindex", "cachedquery", "counter", "bookkeeping", "sqltable-id"):
            continue
        if kind == "global" and _match(name, glb):
            continue
        if kind == "class" and (_match(name, cls) or name.lower() in schemas):
            continue
        if kind == "routine" and (_match(name, cls) or _match(name, rtn)):
            continue
        if kind == "sqltable" and _match(name, tbl):
            continue
        if kind == "sqlproc" and (_match(name, rtn) or _match(name.rsplit("_", 1)[0], tbl)):
            continue
        exc.append(f"journal catalog {kind}: {name} ({n} records)")
    return exc
