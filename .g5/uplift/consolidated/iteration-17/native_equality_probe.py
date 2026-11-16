"""W17: the W16 equality cells on the native executor vs the SQL path, same data and queries (run-isolated fixture only).

For each query: native = engine._try_native(parsed, {}) (None when the query does not route natively), sql =
engine._execute_parsed_sql(parsed, {}, None). Both are the product's own entry points used by execute_cypher.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402

RUN = os.environ.get("W17_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
VALUES = [0, 1, 2, -1, 12, True, False, "1", "0", "True", "False", "true", "false", "12", "01", "x", "1.0", "12.0", 1.0, 0.0, 0.95, 12.0]
LITERALS = ["true", "false", "0", "1", "2", "12", "-1"]


def rows_of(r):
    if r is None:
        return None
    err = getattr(r, "error", None)
    return {"rows": [list(x) for x in r.rows], "error": str(err) if err else None}


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.cypher import native_plan
    from iris_vector_graph.cypher.parser import parse_query
    c = runtime.connect()
    e = IRISGraphEngine(c, embedding_dimension=768)  # native executor on (default)
    out = {"run": RUN, "fixture": runtime.NAME, "gate": native_plan.native_gate(e), "worlds": []}
    for i, v in enumerate(VALUES):
        for kind in ("node", "rel"):
            a, b = f"w17{RUN}{kind}{i}a", f"w17{RUN}{kind}{i}b"
            if kind == "node":
                e.create_node(a, labels=["W17"], properties={"p": v})
                base = f"MATCH (x:W17) WHERE x.id = '{a}'"
            else:
                e.create_node(a, labels=["W17"])
                e.create_node(b, labels=["W17"])
                e.create_edge(a, "W17R", b, qualifiers={"p": v})
                base = f"MATCH (s)-[x:W17R]->(t) WHERE s.id = '{a}'"
            w = {"kind": kind, "value": [type(v).__name__, v], "cells": {}}
            for lit in LITERALS + ["return"]:
                q = f"{base} RETURN x.p AS p" if lit == "return" else f"{base} AND x.p = {lit} RETURN count(*) AS n"
                parsed = parse_query(q)
                try:
                    nat = e._try_native(parsed, {})
                    native = rows_of(nat[1]) if nat is not None else None
                except Exception as x:
                    native = {"exception": f"{type(x).__name__}: {x}"}
                sql = rows_of(e._execute_parsed_sql(parse_query(q), {}, None))
                w["cells"][lit] = {"native": native, "sql": sql,
                                   "routed_native": native is not None,
                                   "equal": native is None or (native.get("rows") == sql["rows"])}
            out["worlds"].append(w)
    c.close()
    path = HERE / f"native-equality-observed-{RUN}.json"
    path.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(path, "gate", out["gate"])
    routed = sum(1 for w in out["worlds"] for x in w["cells"].values() if x["routed_native"])
    total = sum(len(w["cells"]) for w in out["worlds"])
    diffs = [(w["kind"], w["value"], k, x["native"], x["sql"]) for w in out["worlds"] for k, x in w["cells"].items() if not x["equal"]]
    print("routed natively", routed, "of", total, "differences", len(diffs))
    for d in diffs[:30]:
        print("DIFF", d)


if __name__ == "__main__":
    main()
