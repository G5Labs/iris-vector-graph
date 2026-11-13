"""IRIS engine features each of modules 01-06 relies on, found mechanically in the source ranges of the module's entry
points (models/breadth-a/inventory/NN.json), for the orchestrator's IRIS environment contract (gate 3.2-coverage).

    python experiment/playbook-completion/models/breadth-a/tools/env_features.py

Writes models/breadth-a/inventory/env-features-NN.json: per feature, the number of matching lines inside the module's
entry-point ranges and up to 5 sample path:line citations. A regex over source text: it over-approximates (a mention
in a comment counts) and only sees direct text, not callees in other modules.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BA = HERE.parent
REPO = BA.parents[3]

FEATURES = [
    ("LOCK with timeout", r"\bLock\s*\+?\^[^\s]*?:\s*\d+|\bLock\s*\+\^[^\n]*:\s*\w+"),
    ("LOCK shared mode (#\"S\")", r'#"S"'),
    ("LOCK exclusive probe with 0 timeout (#\"E\":0)", r'#"E"\s*:\s*0'),
    ("LOCK release inside a transaction (deferred unlock, P-0003)", r"\bLock\s*:?[^\n]*\s-\^"),
    ("$Increment (not undone by rollback, P-0401)", r"\$Increment\(|\$I\("),
    ("TSTART / TCOMMIT nesting", r"\bTSTART\b|\bTStart\b|\bTCOMMIT\b|\bTCommit\b"),
    ("TROLLBACK with no argument (ends every level, P-0409)", r"\bTROLLBACK\b(?!\s+1)|\bTRollback\b(?!\s+1)"),
    ("TROLLBACK 1 (one level)", r"\bTROLLBACK\s+1\b|\bTRollback\s+1\b"),
    ("$TLevel", r"\$TLevel|getTLevel"),
    ("SQL transaction control from Python (commit/rollback/autocommit)", r"\.commit\(\)|\.rollback\(\)|setAutoCommit|START TRANSACTION|autocommit"),
    ("%NOLOCK", r"%NOLOCK"),
    ("%NOINDEX / %NOCHECK", r"%NOINDEX|%NOCHECK"),
    ("%IGNOREINDEX", r"%IGNOREINDEX"),
    ("LOCK TABLE / FOR UPDATE", r"LOCK TABLE|FOR UPDATE"),
    ("SQL isolation level", r"ISOLATION LEVEL|READ UNCOMMITTED|READ COMMITTED"),
    ("DDL (CREATE/ALTER/DROP TABLE, INDEX, VIEW)", r"\b(CREATE|ALTER|DROP)\s+(TABLE|INDEX|VIEW)\b"),
    ("CREATE OR REPLACE FUNCTION/PROCEDURE (LANGUAGE OBJECTSCRIPT)", r"CREATE\s+(OR\s+REPLACE\s+)?(FUNCTION|PROCEDURE)"),
    ("GRANT / REVOKE / SQL privileges", r"\bGRANT\b|\bREVOKE\b|%CHECKPRIV|CheckPrivilege"),
    ("Vector SQL (VECTOR type, TO_VECTOR, VECTOR_COSINE/DOT)", r"TO_VECTOR|VECTOR_COSINE|VECTOR_DOT_PRODUCT|\bVECTOR\s*\("),
    ("HNSW vector index", r"\bHNSW\b|AS HNSW"),
    ("$vectorop / $vector (ObjectScript vectors)", r"\$vectorop|\$vector\b|\$VECTOR"),
    ("IRIS EMBEDDING() SQL function / %Embedding config", r"EMBEDDING\(|%Embedding"),
    ("iFind full-text index", r"iFind|%iFind"),
    ("Process-private globals (^||)", r"\^\|\|"),
    ("Functional index callbacks / %BuildIndices / BUILD INDEX", r"FunctionalIndex|%BuildIndices|%PurgeIndices|BUILD INDEX"),
    ("Parallel jobs (JOB, WorkMgr, %BuildIndices jobs)", r"\bJob\b|%SYSTEM\.WorkMgr|NumberOfCPUs"),
    ("Native API from Python (classMethod*, globals)", r"classMethodValue|classMethodVoid|createIRIS|nextSubscript|isDefined\("),
    ("Embedded/dynamic SQL in ObjectScript (&sql, %SQL.Statement)", r"&sql\(|%SQL\.Statement|%ExecDirect"),
    ("%DynamicObject / JSON functions", r"%DynamicObject|%DynamicArray|%FromJSON|%ToJSON|\{\}\.%FromJSON|JSON_VALUE|JSON_TABLE"),
    ("$ZStrip / $ZConvert character classes", r"\$ZStrip|\$ZConvert|\$ZCVT"),
    ("Global collation order ($Order/$Query)", r"\$Order\(|\$O\(|\$Query\(|nextSubscript"),
    ("Global KILL of a subtree / Merge", r"\bKill\s+\^|\bMerge\s+\^"),
    ("Class dictionary reads (^oddDEF, %Dictionary)", r"\^oddDEF|%Dictionary"),
    ("Class compile/delete at run time ($System.OBJ)", r"%SYSTEM\.OBJ|\$System\.OBJ|\$SYSTEM\.OBJ"),
    ("Task Manager (%SYS.Task)", r"%SYS\.Task"),
    ("Time functions (DATEDIFF, $ZTimeStamp, $Horolog)", r"DATEDIFF|\$ZTimeStamp|\$ZTS\b|\$Horolog|\$H\b"),
    ("SQL empty string as $Char(0)", r"\$Char\(0\)|\$C\(0\)|\\x00"),
    ("SQLCODE-specific handling", r"SQLCODE|-119|-121|-104|-30\b"),
    ("INSERT OR UPDATE", r"INSERT OR UPDATE"),
    ("TOP / LIMIT / FETCH FIRST result prefix", r"\bTOP\s+[\d:?{]|\bLIMIT\b|FETCH FIRST"),
    ("%Stream", r"%Stream"),
]


def ranges(inv):
    out = {}
    for e in inv["entry_points"]:
        src = e.get("source") or ""
        m = re.match(r"(.+?):(\d+)-(\d+)$", src)
        if not m:
            continue
        out.setdefault(m.group(1), []).append((int(m.group(2)), int(m.group(3))))
    return out


def main():
    for mod in ("01", "02", "03", "04", "05", "06"):
        inv = json.loads((BA / "inventory" / f"{mod}.json").read_text())
        rng = ranges(inv)
        feats = []
        for name, pat in FEATURES:
            rx = re.compile(pat)
            hits = []
            for path, spans in sorted(rng.items()):
                p = REPO / path
                if not p.exists():
                    continue
                lines = p.read_text(errors="replace").splitlines()
                seen = set()
                for a, b in spans:
                    for i in range(max(a, 1), min(b, len(lines)) + 1):
                        if i in seen:
                            continue
                        seen.add(i)
                        if rx.search(lines[i - 1]):
                            hits.append(f"{path}:{i}")
            if hits:
                feats.append({"feature": name, "occurrences": len(hits), "samples": hits[:5]})
        out = {"module": mod, "generated_by": "experiment/playbook-completion/models/breadth-a/tools/env_features.py",
               "method": "regex over the source ranges of the module's inventoried entry points; over-approximates",
               "env_features": feats}
        (BA / "inventory" / f"env-features-{mod}.json").write_text(json.dumps(out, indent=1) + "\n")
        print(mod, len(feats), "features")


if __name__ == "__main__":
    main()
