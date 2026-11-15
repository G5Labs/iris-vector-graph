"""HD-0803 probe (read-only): which definitions of sql/operators.sql's six routines does a namespace set up by the pin's
own initialize_schema hold?

sql/operators.sql (pin) defines kg_KNN_VEC(queryInput, k, labelFilter, embeddingConfig), kg_TXT, kg_RRF_FUSE,
kg_GRAPH_PATH, kg_RERANK and kg_PPR unqualified (SQLUser at the default) and with no graph argument; nothing in the
pin loads it (grep: no reference outside the file). The live procedures come from iris_vector_graph/schema.py.
Oracle: list INFORMATION_SCHEMA routines named like these six in every schema with their parameter names.
  - a routine whose parameters equal operators.sql's (no graph argument) in any schema -> operators.sql is deployed
  - only Graph_KG routines with schema.py's parameters (graph argument)               -> setup does not deploy it
This settles the as-built deployment fact only; whether the file is product code stays a maintainer decision.
Nothing is written.
"""
from __future__ import annotations

import re
from pathlib import Path

import _common as C

NAMES = ["kg_KNN_VEC", "kg_TXT", "kg_RRF_FUSE", "kg_GRAPH_PATH", "kg_RERANK", "kg_PPR"]
REPO = Path(__file__).resolve().parents[5]


def file_params(path: Path) -> dict:
    text = path.read_text()
    out = {}
    for m in re.finditer(r"CREATE OR REPLACE (?:PROCEDURE|FUNCTION) (\w+)\((.*?)\)\s*(?:RETURNS|LANGUAGE|\n)", text, re.S):
        params = re.findall(r"(?:IN|OUT|INOUT)?\s*(\w+)\s+(?:VARCHAR|INT|INTEGER|DOUBLE|FLOAT|BIGINT|VECTOR|LONGVARCHAR)",
                            re.sub(r"--[^\n]*", "", m.group(2)))
        out[m.group(1)] = params
    return out


def main():
    c = C.conn()
    try:
        ops = file_params(REPO / "sql" / "operators.sql")
        C.obs(source="sql/operators.sql", routines=ops)
        rows = c.sql("SELECT ROUTINE_SCHEMA, ROUTINE_NAME, ROUTINE_TYPE FROM INFORMATION_SCHEMA.ROUTINES "
                     "WHERE UPPER(ROUTINE_NAME) IN (" + ",".join("?" * len(NAMES)) + ")", *[n.upper() for n in NAMES])
        live = {}
        for schema, name, rtype in rows:
            params = c.sql("SELECT PARAMETER_NAME FROM INFORMATION_SCHEMA.PARAMETERS WHERE SPECIFIC_SCHEMA = ? AND "
                           "SPECIFIC_NAME = ? ORDER BY ORDINAL_POSITION", schema, name)
            live[f"{schema}.{name}"] = {"type": rtype, "params": [p[0] for p in params if p[0]]}
        C.obs(live_routines=live)
        sqluser = [k for k in live if not k.startswith("Graph_KG.")]
        same = [k for k, v in live.items()
                if k.split(".")[1] in ops and [p.lower() for p in v["params"]] == [p.lower() for p in ops[k.split(".")[1]]]]
        C.obs(outside_graph_kg=sqluser, matching_operators_sql_signature=same,
              missing_from_namespace=[n for n in NAMES if not any(k.split(".")[1].lower() == n.lower() for k in live)])
        if not sqluser and not same:
            C.verdict("pass", f"no routine with operators.sql's signature in any schema; live: "
                              f"{ {k: v['params'] for k, v in live.items()} }")
        else:
            C.verdict("pass", f"operators.sql-shaped routines present: {sqluser or same}")
    finally:
        c.close()


if __name__ == "__main__":
    main()
