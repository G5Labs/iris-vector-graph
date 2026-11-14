#!/usr/bin/env python3
"""Map every module's `env_features` (modules/NN.json) to the IRIS environment contract.

    python iris-contract/coverage.py [--check]      writes iris-contract/COVERAGE.json

Each feature gets one status:
  in-contract        the semantics the module relies on is a validated clause (ids below, CONTRACT.md table);
  availability-only  the contract decides only that the feature exists / does not exist on this engine;
  outside-subset     not modelled (reason given); the module's 3.2-coverage gate stays open for it.
The first matching rule wins; `--check` fails if a feature matches no rule.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULES = HERE.parent / "modules"

# Clause ids (CONTRACT.md "Clauses"). E-*: rounds r1/r2; X-*: extension, round r3+.
CLAUSES = {
    "E-GLOBALS": "Globals: SET / KILL subtree / $GET / $DATA, restored by rollback",
    "E-NEST": "Nesting (TSTART / TCOMMIT / TROLLBACK, $TLEVEL)",
    "E-PARTIAL": "Partial rollback (TROLLBACK 1), globals and SQL rows alike",
    "E-INCR": "$INCREMENT not undone by rollback",
    "E-PPG": "Process-private globals: not rolled back, private",
    "E-VIS": "Visibility: no isolation for globals, READ UNCOMMITTED for SQL",
    "E-ROLLBACK-OTHER": "Rollback does not overwrite another process's later write",
    "E-SQL-START": "SQL START TRANSACTION",
    "E-SQL-END": "SQL COMMIT / ROLLBACK end one level",
    "E-DRV": "Driver commit() one level / rollback() every level",
    "E-AUTOCOMMIT": "Autocommit default on; off: first DML opens a level; turning it on commits one open level",
    "E-LOCK-DEFER": "Locks: deferred release inside a transaction",
    "E-LOCK-LIFE": "Locks: survive commit",
    "E-LOCK-NAMES": "Locks: hierarchical names",
    "E-LOCK-MODES": "Locks: shared / exclusive",
    "E-LOCK-COUNT": "Locks: incremental counts",
    "E-LOCK-NONINC": "Non-incremental LOCK",
    "E-LOCK-WAIT": "Lock wait / timeout 0 ($TEST)",
    "E-ROWLOCK": "Row locks",
    "E-UNIQUE": "Unique keys (-119 at once)",
    "E-STOP": "Process stop: rollback, locks released",
    "E-CALLER": "SQL and Native API of one connection share a server process",
    "X-FX": "Functional index entries in the row's statement and transaction",
    "X-NOINDEX": "%NOINDEX / %NOCHECK / BUILD INDEX / %IGNOREINDEX * scan",
    "X-DDL": "DDL: catalog effects, in a transaction rolled back with it",
    "X-NULL": "NULL and '' encodings on the two client paths; COALESCE guard",
    "X-STMT": "Statement-level atomicity; a failed statement still opens the autocommit-off transaction",
    "X-ORDER": "$ORDER / nextSubscript collation",
    "X-STAR": "SELECT * column order; ALTER TABLE ADD COLUMN appends",
    "X-TLEVEL-SQL": "SELECT $TLEVEL; a query does not open a transaction",
    "X-VEC": "Vector SQL functions availability; $VECTOR in a global",
    "X-ZSTRIP": "$ZSTRIP classes C and W and actions * < > =",
}

IN, AV, OUT = "in-contract", "availability-only", "outside-subset"

# (pattern on the lower-cased feature text, status, clause ids or reason, note)
RULES = [
    # ---- outside first where a feature names a construct the subset refuses
    (r"hnsw", OUT, "HNSW vector index maintenance is outside the subset", ""),
    (r"%ifind\.utils|tokenizer", OUT, "iFind tokenizer / analysis not modelled", ""),
    (r"ifind", OUT, "iFind search semantics (tokenizer, word dictionary written outside the transaction, ranking) "
                    "not modelled; only the per-row index entries' transaction behaviour is (X-FX)", ""),
    (r"embedding\(\)|%embedding", OUT, "EMBEDDING() / %Embedding configuration not modelled", ""),
    (r"%sys\.task|task manager", OUT, "Task Manager not modelled", ""),
    (r"fhir", OUT, "InterSystems FHIR server storage: absent on Community 2026.1", ""),
    (r"%ai\.", OUT, "%AI classes: absent on Community 2026.1", ""),
    (r"embedded python|language = python|\[language = python\]|iris\.sql|iris\.gref|iris\.cls|irispython|wsgi",
     OUT, "embedded Python is not driven by the contract (needs irispython in the container)", ""),
    (r"%csp\.rest|%request|security\.applications|grant|revoke|privilege",
     OUT, "web dispatch, roles and SQL privileges not modelled", ""),
    (r"compil|\$system\.obj|%dictionary|\^odd|timechanged|objectgenerator|class dictionary|\$classmethod",
     OUT, "class dictionary and run-time compilation not modelled (compiling is out of the audit's scope)", ""),
    (r"iris\.temp|iristemp", OUT, "IRISTEMP database (not journaled, shared) not modelled", ""),
    (r"\bjob\b|workmgr|work queues|parallel jobs|worker processes", OUT, "JOB / WorkMgr processes not modelled", ""),
    (r"&sql|embedded sql|embedded/dynamic", OUT, "embedded SQL (&sql) compiled into classes: assumed equal to dynamic "
     "SQL (premise E-1), untested; %SQL.Statement %ExecDirect is in the contract (E-PARTIAL, X-FX, X-STMT, X-NULL)", ""),
    (r"top / limit|top n|fetch first", OUT, "result-prefix queries not modelled", ""),
    (r"current_statements|information_schema\.routines|table_constraints|%sys\.namespace|namespace switch|"
     r"default schema|unqualified sql table", OUT, "catalog views other than TABLES / COLUMNS, default-schema "
                                                    "resolution and namespaces not modelled", ""),
    (r"\$zf|callout", OUT, "$ZF callouts not modelled", ""),
    (r"long[- ]string|maxstring|string limit|3,641,144|3\.6 mb|subscript length|bound parameters|zfheap",
     OUT, "engine limits (string, subscript, parameter count) not modelled", ""),
    (r"%stream", OUT, "streams not modelled", ""),
    (r"dynamicobject|dynamicarray|json", OUT, "%DynamicObject / JSON functions not modelled", ""),
    (r"\$list|listbuild", OUT, "$LIST semantics not modelled", ""),
    (r"\$zcrc|shahash|sha-256|encryption|base64|guid|\$random|time functions|\$horolog|\$ztimestamp|\$zdatetime|datediff",
     OUT, "pure functions and clocks not modelled", ""),
    (r"%regex", OUT, "%Regex not modelled", ""),
    (r"trigger|%onbeforesave|%ondelete|%killextent|%openid|%save|foreign key|constraints|idkey",
     OUT, "object filing, triggers and foreign keys not modelled", ""),
    (r"insert or update", OUT, "INSERT OR UPDATE not modelled", ""),
    (r"top / limit|top n|fetch first", OUT, "result-prefix queries not modelled", ""),
    (r"%exact|%sqlupper|cast, coalesce in generated", OUT, "SQL collation functions / generated SQL not modelled", ""),
    (r"bitmap extent", OUT, "the bitmap extent and index-driven full-table DML are not modelled (env/explore-4 A11: "
                            "DELETE without WHERE misses %NOINDEX rows; the cases scan with %IGNOREINDEX *)", ""),
    (r"-- comments|multi-statement|literal escaping", OUT, "SQL text parsing not modelled", ""),
    (r"processquery|killprocess|%system\.version|writetoconsolelog|%sys\.system", OUT,
     "management APIs not modelled (process stop is, via %SYSTEM.Process.Terminate: E-STOP)", ""),
    (r"current_statements|information_schema\.routines|table_constraints|%sys\.namespace|namespace switch|"
     r"default schema|unqualified sql table", OUT, "catalog views other than TABLES / COLUMNS and namespaces "
                                                    "not modelled", ""),
    (r"iris\.temp|iristemp", OUT, "IRISTEMP database (not journaled, shared) not modelled", ""),
    (r"rowids never reused|max\(%id\)", OUT, "row-id allocation not modelled", ""),
    (r"%library\.file|export/load|\.gof|fileset", OUT, "files not modelled", ""),
    (r"journal \(|footprint oracle|journaling of", OUT, "the journal is the audit's oracle, not a contract clause", ""),
    (r"failed compile|unable to prepare", OUT, "compile failures not modelled", ""),
    (r"%status|<throw>|<protect>", OUT, "error reporting through the Native API not modelled", ""),
    (r"sql procedures|create or replace function|create or replace procedure|create function|\[sqlproc\]|sql udf",
     OUT, "SQL routines (compiled) not modelled", ""),
    (r"null subscript", OUT, "Native API subscript validation not modelled", ""),
    (r"licen|connection cap|core limit|number of cpus|connection/core", AV,
     [], "infrastructure fact (CONVENTIONS connection cap), not a contract clause"),
    # ---- in contract / availability
    (r"vector_l2|vector_cosine|vector_dot|vector sql|to_vector|vector\(|vector columns", AV, ["X-VEC"],
     "VECTOR_COSINE / VECTOR_DOT_PRODUCT exist, VECTOR_L2 does not (-359); TO_VECTOR(text, DOUBLE)"),
    (r"\$vector|\$isvector|\$vectorop|\$vectordefined", IN, ["X-VEC"],
     "$VECTOR element set/get and rollback; the Native API cannot read a $VECTOR value (<LIST ERROR>); "
     "$VECTOROP functions not modelled"),
    (r"\$zstrip|\$zconvert", IN, ["X-ZSTRIP"], "$ZCONVERT not modelled"),
    (r"select \*", IN, ["X-STAR"], ""),
    (r"select \$tlevel", IN, ["X-TLEVEL-SQL", "E-NEST"], ""),
    (r"statement-level atomicity|failed sql statement", IN, ["X-STMT"], ""),
    (r"unique index violation|-119 writes no row", IN, ["E-UNIQUE", "X-STMT"], ""),
    (r"where not exists", IN, ["E-UNIQUE", "E-VIS", "X-STMT"], "the guard takes no lock; the unique key is the "
                                                               "backstop (E-UNIQUE)"),
    (r"%noindex|%nocheck|%ignoreindex", IN, ["X-NOINDEX"], "%IGNOREINDEX: the `*` form (full scan) is exercised; "
                                                         "named-index forms are not"),
    (r"functional|%buildindices|build index|adjacency index|row hooks|index maintenance", IN, ["X-FX", "X-NOINDEX"],
     "carrier: %iFind.Index.Basic (a %Library.FunctionalIndex shipped with IRIS); the product's own callbacks are "
     "not compiled here"),
    (r"ddl|create table|drop table|alter", IN, ["X-DDL"], "DDL in a transaction is rolled back with it (catalog); "
                                                        "use of a table after its CREATE was rolled back is outside"),
    (r"catalog|information_schema|tableexists", IN, ["X-DDL"], "TABLES and COLUMNS only"),
    (r"empty string|\$char\(0\)|bound as null|'' bound|empty parameter", IN, ["X-NULL"],
     "the embedded-Python path (P-1709) is outside"),
    (r"collation|\$order|\$query|nextsubscript|sorts-after|canonical numeric", IN, ["X-ORDER"],
     "$QUERY and the ]] operator rely on the same collation but are not exercised"),
    (r"\$increment|id counters|non-transactional|version token|version stamps", IN, ["E-INCR"], ""),
    (r"process-private|\^\|\|", IN, ["E-PPG"], ""),
    (r"start transaction/commit/rollback end every level|commit/rollback end every level", IN, ["E-SQL-END", "E-SQL-START"],
     "the contract refutes the premise on 2026.1: SQL COMMIT / ROLLBACK end one level"),
    (r"driver start transaction|commit\(\) / rollback\(\)|sql start transaction|sql transaction control|"
     r"commit/rollback/autocommit|autocommit", IN, ["E-SQL-START", "E-SQL-END", "E-DRV", "E-AUTOCOMMIT"], ""),
    (r"process death|process stop|process ends|process exit|owning process ends|closing a connection", IN,
     ["E-STOP"], "closing a connection is assumed equal to a process stop"),
    (r"lock freed inside|unlock inside|release inside a transaction|deferred unlock|held to (its|transaction) end",
     IN, ["E-LOCK-DEFER"], ""),
    (r"uncommitted|read uncommitted|dirty|visibility|lock-free global reads|isolation", IN, ["E-VIS"], ""),
    (r"shared", IN, ["E-LOCK-MODES", "E-LOCK-WAIT"], "timeouts are modelled as wait / no-wait"),
    (r"lock", IN, ["E-LOCK-WAIT", "E-LOCK-COUNT", "E-LOCK-NAMES"], "timeouts are modelled as wait / no-wait"),
    (r"rollback restores|before-image|undoes set/kill", IN, ["E-ROLLBACK-OTHER", "E-GLOBALS", "E-INCR"], ""),
    (r"uncommitted|read uncommitted|dirty|visibility|lock-free global reads|isolation", IN, ["E-VIS"], ""),
    (r"tstart|tcommit|trollback|nesting|\$tlevel|write transactions", IN, ["E-NEST", "E-PARTIAL"], ""),
    (r"same server process|server process|shared transaction context|classmethodvalue|one iris process per|"
     r"superserver|native api over db-api", IN, ["E-CALLER"], "caller identity is an exploratory observation "
                                                             "(env/explore-2.log test 7)"),
    (r"%sql\.statement|embedded/dynamic sql|dynamic sql|&sql|embedded sql", IN, ["E-PARTIAL", "X-FX", "X-STMT", "X-NULL"],
     "the terminal driver's %ExecDirect path; embedded &sql compiled into classes is assumed equal (premise E-1)"),
    (r"kill of a whole global|global kill|kill of a subtree|work globals|set/\$get/\$data|globals\)|"
     r"direct global access", IN, ["E-GLOBALS"], "MERGE and $LIST slot access are not modelled"),
    (r"native api", IN, ["E-GLOBALS", "E-CALLER"], ""),
    (r"sqlcode", OUT, "only -30, -110, -119, -201, -359 and -400 are contract observations; the other codes "
                      "the module maps are not modelled", ""),
]


# Features whose first matching rule is not the whole story (keyed by the start of the feature text).
OVERRIDES = {
    "Global Kill of a subtree, Set/$Get/$Data/$Order": (IN, ["E-GLOBALS", "X-ORDER", "E-VIS"], ""),
    "TSTART/TCOMMIT/TROLLBACK 1 nesting, reached as SQL functions": (IN, ["E-NEST", "E-PARTIAL", "E-AUTOCOMMIT",
        "E-CALLER"], "the product's SQL functions (Graph_KG.Txn_*) are not callable in AUDITENV; TSTART on the "
                     "cursor's process is E-CALLER"),
    "SQLCODE map": (OUT, "only -30, -110, -119, -201, -359 and -400 are contract observations; -23, -104, -149, "
                         "-428, -99 and <PROTECT> are not modelled", ""),
    "LOCK +^G(sub):0": (IN, ["E-LOCK-WAIT", "E-LOCK-COUNT", "E-STOP"], ""),
    "Catalog: INFORMATION_SCHEMA.TABLES/COLUMNS": (OUT, "default-schema (SQLUser) resolution is not modelled; TABLES, "
                                                       "COLUMNS and TableExists are (X-DDL)", ""),
    "DB-API driver iris.dbapi.connect and Native API": (IN, ["E-GLOBALS", "E-CALLER", "X-ORDER"], ""),
    "DB-API autocommit True by default; SQL START TRANSACTION": (IN, ["E-AUTOCOMMIT", "E-SQL-START", "E-SQL-END",
                                                                     "X-TLEVEL-SQL"], ""),
    "VECTOR_L2 is a distance": (AV, ["X-VEC"], "the premise P-1710 is refuted here: VECTOR_L2 does not exist (-359); "
                                               "the mutant encoding it is killed"),
    "%Dictionary.CompiledMethod": (OUT, "class dictionary reads not modelled", ""),
    "<LIST ERROR> after another connection's %BuildIndices": (OUT, "effects of an index (re)build on another "
        "connection's cached code are not modelled", ""),
    "Native API nextSubscript('' start)": (IN, ["X-ORDER", "E-GLOBALS"], "nextSubscript answers canonical strings in "
        "$ORDER order; note: the Native API cannot read a $VECTOR value (get raises <LIST ERROR>, X-VEC)"),
    "$Vector / $IsVector / $VectorOp": (OUT, "$LISTVALID / $LISTNEXT, $NAME and %DynamicObject are not modelled; "
                                             "$VECTOR set/get/rollback is (X-VEC)", ""),
    "Runtime DDL: CREATE TABLE": (OUT, "HNSW index build is outside; CREATE / DROP TABLE are in X-DDL", ""),
    "TSTART/TCOMMIT/TROLLBACK around Eraser.EraseAll": (IN, ["E-NEST", "E-PARTIAL", "E-AUTOCOMMIT"], ""),
    "%IGNOREINDEX": (OUT, "only the `%IGNOREINDEX *` full scan is exercised (X-NOINDEX); the product's named-index "
                          "forms are not", ""),
    "embedded SQL / %SQL.Statement reads": (OUT, "embedded SQL (&sql): premise E-1; %SQL.Statement reads at the "
                                                 "default isolation are E-VIS", ""),
    "Native API classMethodValue sharing the DBAPI": (IN, ["E-CALLER"], ""),
    "Native API classMethodValue on the DB-API connection's process": (IN, ["E-CALLER"], ""),
    "LOCK +^G#\"S\" shared lock": (IN, ["E-LOCK-MODES", "E-LOCK-DEFER", "E-LOCK-WAIT"], "timeouts are modelled as "
                                                                                    "wait / no-wait"),
}


def classify(text: str):
    for pre, (status, what, note) in OVERRIDES.items():
        if text.startswith(pre):
            if status == OUT:
                return {"status": OUT, "reason": what}
            return {"status": status, "clauses": what, **({"note": note} if note else {})}
    t = text.lower()
    for pat, status, what, note in RULES:
        if re.search(pat, t):
            if status == OUT:
                return {"status": OUT, "reason": what}
            return {"status": status, "clauses": what, **({"note": note} if note else {})}
    return None


def main() -> int:
    out = {"contract": "experiment/playbook-completion/iris-contract/CONTRACT.md",
           "deciding_round": "env-ext-r6 (evidence/runs/env-ext-r6.json; CONTRACT.md Results)",
           "statuses": {IN: "the relied semantics is a validated clause", AV: "the contract decides only existence on "
                        "this engine", OUT: "not modelled; keeps the module's 3.2-coverage gate open"},
           "clauses": CLAUSES, "modules": {}}
    missing = []
    summary = {}
    for f in sorted(MODULES.glob("[0-9][0-9].json")):
        m = json.loads(f.read_text())
        rows = []
        for i, e in enumerate(m.get("env_features") or []):
            text = e.get("feature") if isinstance(e, dict) else str(e)
            c = classify(text)
            if c is None:
                missing.append((f.stem, i, text))
                c = {"status": OUT, "reason": "unclassified"}
            src = e.get("source") or ", ".join(e.get("samples", [])[:2]) if isinstance(e, dict) else ""
            rows.append({"index": i, "feature": text, "source": src, **c})
        counts = {s: sum(1 for r in rows if r["status"] == s) for s in (IN, AV, OUT)}
        # "closable": every feature the module relies on is in the contract or availability-only, so the gate
        # depends only on the contract's round results; "open": features outside the subset keep it open.
        out["modules"][f.stem] = {"features": rows, "counts": counts,
                                  "gate_3.2_coverage": "closable" if counts[OUT] == 0 else "open",
                                  "open_because": sorted({r["reason"] for r in rows if r["status"] == OUT})}
        summary[f.stem] = counts
    out["summary"] = summary
    (HERE / "COVERAGE.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for s in missing:
        print("unclassified:", *s)
    for k, v in summary.items():
        print(k, v)
    return 1 if (missing and "--check" in sys.argv) else 0


if __name__ == "__main__":
    raise SystemExit(main())
