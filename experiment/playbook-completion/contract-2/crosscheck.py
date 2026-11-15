#!/usr/bin/env python3
"""Cross-check: every outside-subset reason the r6 COVERAGE.json (iris-contract/coverage.py over the breadth lanes'
hand-curated env_features) gives a module must be found by enumerate.py's mechanical scan of that module, as a
feature of the matching family or clause. A miss means the mechanical scan lost something the lanes saw.

    python crosscheck.py coverage.json   -> prints misses; exit 1 if any"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = json.loads((HERE.parent / "iris-contract" / "COVERAGE.json").read_text())
NEW = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "coverage.json").read_text())
# old reason (prefix) -> predicate over a new feature row
def fam(*names):
    return lambda r: r.get("family") in names or (r.get("residual") or {}).get("family") in names
def clause(*cs):
    return lambda r: any(c in r.get("clauses", []) for c in cs)
def feat(*prefixes):
    return lambda r: r["feature"].startswith(prefixes)
MAP = [
    ("%DynamicObject / JSON", lambda r: fam("json")(r) or clause("X2-JSON")(r)),
    ("HNSW", fam("hnsw")), ("SQL routines", lambda r: fam("sqlroutine")(r) or clause("S-1")(r)),
    ("class dictionary", fam("dict")), ("embedded SQL (&sql)", lambda r: clause("E-1")(r) or fam("esql-other")(r)),
    ("iFind search semantics", fam("ifind")), ("iFind tokenizer", fam("ifind")),
    ("only -30, -110", lambda r: r["feature"].startswith(("sqlcode.", "py.dbapi.error-class"))),
    ("result-prefix queries", lambda r: clause("X2-TOP")(r) or fam("top", "fetchfirst")(r)),
    ("JOB / WorkMgr", fam("job", "buildindices")), ("only the `%IGNOREINDEX *`", lambda r: r["feature"].startswith("sql.pct.%IGNOREINDEX")),
    ("pure functions and clocks", fam("pure", "clock", "random", "hash")),
    ("EMBEDDING()", fam("embedding")), ("INSERT OR UPDATE", lambda r: clause("X2-IOU")(r) or fam("iou")(r)),
    ("Task Manager", fam("task")), ("embedded Python", fam("epy")), ("engine limits", None),
    ("the journal is the audit's oracle", None),
    ("$LIST semantics", lambda r: clause("X2-LIST")(r) or fam("list")(r)), ("%Regex", lambda r: "Regex" in r["feature"]),
    ("SQL collation functions", lambda r: r["feature"] in ("sql.pct.%EXACT", "sql.pct.%SQLUPPER") or "UPPER" in r["feature"]),
    ("SQL text parsing", None),
    ("IRISTEMP", fam("temp")), ("$ZF callouts", fam("zf")), ("catalog views other than", fam("catalog", "ns")),
    ("object filing", fam("persistent", "trigger", "fk")), ("streams", fam("stream")),
    ("InterSystems FHIR", fam("absent")), ("%AI classes", fam("absent")),
    ("default-schema (SQLUser)", fam("catalog")), ("class dictionary reads", fam("dict")),
    ("effects of an index (re)build", lambda r: r["feature"] in ("sql.verb.BUILD INDEX",) or "BuildIndices" in r["feature"]
     or fam("buildindices")(r)),
    ("management APIs", fam("mgmt")), ("web dispatch", fam("web", "security")),
    ("$LISTVALID / $LISTNEXT, $NAME and %DynamicObject", lambda r: fam("list", "query", "json")(r) or clause("X2-LIST", "X2-JSON")(r)),
    ("HNSW index build", fam("hnsw")), ("Native API subscript validation", None),
    ("the bitmap extent", None), ("row-id allocation", fam("rowid")), ("files not modelled", fam("file")),
    ("compile failures", fam("dict")), ("error reporting through the Native API", fam("status")),
]
SITES = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 else None
import re as _re


def old_sites(src):
    out = []
    for part in _re.split(r"[;,]\s*(?=[\w./-]+\.\w+:)", src or ""):
        m = _re.match(r"\s*([\w./-]+\.\w+):(.*)", part)
        if not m:
            continue
        path = m.group(1)
        for rng in _re.findall(r"(\d+)(?:-(\d+))?", m.group(2)):
            a = int(rng[0]); b = int(rng[1] or rng[0])
            out.append((path, a, b))
    return out


def covered_elsewhere(m, reason, pred):
    """Old sample sites of this reason, looked up in every module's features that satisfy pred."""
    feats = [f for f in OLD["modules"][m]["features"] if f.get("reason") == reason]
    found, prose = [], []
    for f in feats:
        for path, a, b in old_sites(f.get("source", "")):
            hit = None
            for mm, rows in NEW["modules"].items():
                for r in rows["features"]:
                    if not pred(r):
                        continue
                    for site in (SITES[mm].get(r["feature"], []) if SITES else r["sites"]):
                        sp, sl = site.rsplit(":", 1)
                        if sp == path and a - 3 <= int(sl) <= b + 3:
                            hit = (mm, r["feature"], site)
                            break
                    if hit:
                        break
                if hit:
                    break
            (found if hit else prose).append(hit or (path, a, b))
    return found, prose


# Read by hand (the cited lines and their callees, at the pin): why a remaining old reason is not a feature of the
# module's own code. Each entry names where the feature is classified instead.
EXPLAINED = {
    ("08", "iFind search semantics"): "schema.py:165-179 is module 01's catalog read of iFind helper classes "
        "(_IFIND_HELPER_SQL): classified in module 01 as sql.catalog.%DICTIONARY.* (P2-CATALOG); module 08 does not own it",
    ("09", "web dispatch, roles and SQL privileges"): "engine.py:559-586 (_native_privileges, owned by module 02) is a "
        "docstring and a call of schema_name.missing_privilege; the -99 refusal is classified where that code is owned "
        "(sqlcode.-99, P2-SQLCODE)",
    ("15", "web dispatch, roles and SQL privileges"): "FHIRGraph.cls:3039-3095 is dynamic SQL (%SQL.Statement, inside: "
        "E-VIS, E-ROWLOCK, X-STMT, X-NULL); the old classification matched the word 'privilege' in its text",
    ("18", "HNSW index build"): "snapshot.py:1372-1500 calls GraphSchema._create_routed_table / _attempt_route_index "
        "(iris_vector_graph/_engine/schema.py:884-960, owned by modules 01/04/06/15), whose HNSW DDL is classified there "
        "(sql.indextype.HNSW, P2-HNSW); a module's cell covers the code it owns, its callees' cells the rest",
}
misses, noted, elsewhere = [], [], []
for m, d in OLD["modules"].items():
    if m not in NEW["modules"]:
        continue
    rows = NEW["modules"][m]["features"]
    for reason in d.get("open_because", []):
        hit = next(((k, f) for k, f in MAP if reason.startswith(k)), None)
        if hit is None:
            misses.append((m, reason, "no mapping"))
            continue
        k, f = hit
        if f is None:
            noted.append((m, reason, "a semantic limit or oracle, not a source token; carried as a premise in COVERAGE-2.md"))
            continue
        if not any(f(r) for r in rows):
            found, rest = covered_elsewhere(m, reason, f)
            # a cited site with no IRIS token at all (any feature, any module) is prose: a comment or docstring the
            # breadth lanes' text regex matched
            tok = []
            for path, a, b in rest:
                hits = sorted({(mm, ft) for mm, fs in (SITES or {}).items() for ft, ss in fs.items()
                               for st in ss if st.rsplit(":", 1)[0] == path and a - 1 <= int(st.rsplit(":", 1)[1]) <= b + 1})
                tok.append(((path, a, b), hits[:6]))
            prose = [x for x, h in tok if not h]
            other = [(x, h) for x, h in tok if h]
            exp = next((v for (mm, pre), v in EXPLAINED.items() if mm == m and reason.startswith(pre)), None)
            if other and exp:
                elsewhere.append((m, reason[:60], "explained", {"why": exp}))
                continue
            if not other:
                elsewhere.append((m, reason[:60], "covered where the code is owned" if found else "old site is prose",
                                  {"found_at": found[:3], "prose": prose[:4]}))
            else:
                misses.append((m, reason, "token at the cited lines classified differently",
                               {"found_at": found[:3], "prose": prose[:3], "other_tokens": other[:3]}))
print(json.dumps({"misses": misses, "covered_in_owner_module": elsewhere, "not_token_features": noted}, indent=1))
sys.exit(1 if misses else 0)
