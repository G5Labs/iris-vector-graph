#!/usr/bin/env python3
"""Write contract-2/VALIDATED.json from the run registry: a clause counts as validated only when every run it cites
is registered (evidence/runs/<id>.json) with result pass. enumerate.py reads the file; an unregistered or failed
round leaves its features `outside`."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent / "evidence" / "runs"
CLAUSES = {
    "E-1": (["env2-e1-r1", "env2-e1-r1-journal"], "the pin's compiled embedded SQL (SELECT INTO, cursor, INSERT, "
            "INSERT ... SELECT WHERE NOT EXISTS, DELETE) has the dynamic statement's permitted outcomes for E-NEST, "
            "E-PARTIAL, E-SQL-END, E-DRV, E-AUTOCOMMIT, E-VIS, E-ROWLOCK, E-UNIQUE, E-STOP, X-STMT, X-NULL; -104, -108"),
    "S-1": (["env2-e1-r2"], "the pin's compiled SQL functions Txn_Begin / Txn_End / Txn_Undo act on the calling "
            "connection's process and transaction"),
    "X2-JSON": (["env2-x2-r1"], "%DynamicObject %Set / %Get / %GetTypeOf / %IsDefined / %Remove / %ToJSON / %FromJSON"),
    "X2-LIST": (["env2-x2-r1"], "$LIST / $LISTBUILD / $LISTGET / $LISTDATA / $LISTLENGTH / $LISTNEXT / $LISTFIND / "
                "$LISTSAME / $LISTTOSTRING / $LISTFROMSTRING; IRISList decode"),
    "X2-TOP": (["env2-x2-r1"], "TOP n, LIMIT n [OFFSET m] over ORDER BY (SQLUPPER default, DESC, %EXACT) and unordered"),
    "X2-BATCH": (["env2-x2-r1"], "DB-API executemany: a refused row of several skipped silently; one row raises"),
    "X2-IOU": (["env2-x2-r1"], "INSERT OR UPDATE: inserts / updates; waits for a held row; -109 if it is gone"),
    "X2-QUERY": (["env2-x2-r1"], "$QUERY forward and reverse, $QLENGTH, $QSUBSCRIPT in $ORDER collation"),
    "X2-MERGE": (["env2-x2-r1"], "MERGE (copy, onto existing, rolled back) and ZKILL (value only, rolled back)"),
}
out = {"clauses": {}}
for c, (runs, what) in CLAUSES.items():
    res = []
    for r in runs:
        f = RUNS / f"{r}.json"
        res.append(json.loads(f.read_text())["result"] if f.exists() else "not-registered")
    out["clauses"][c] = {"runs": runs, "run_results": res, "result": "pass" if all(x == "pass" for x in res) else "open",
                         "what": what}
(HERE / "VALIDATED.json").write_text(json.dumps(out, indent=1) + "\n")
for c, v in out["clauses"].items():
    print(c, v["result"], v["run_results"])
