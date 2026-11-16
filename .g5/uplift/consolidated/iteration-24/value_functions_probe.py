"""W29: value functions over Python-written values, node vs relationship (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W29_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
EXPR = ["toString(x.p)", "toInteger(x.p)", "x.p + 1", "coalesce(x.p, 'z')"]
def main():
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "cells": {}}
    for i, v in enumerate(["7", 7, 7.5, True]):
        for kind in ("node", "rel"):
            a, b = f"vf{RUN}{kind}{i}a", f"vf{RUN}{kind}{i}b"
            if kind == "node":
                e.create_node(a, labels=["VF"], properties={"p": v}); base = f"MATCH (x:VF) WHERE x.id = '{a}'"
            else:
                e.create_node(a, labels=["VF"]); e.create_node(b, labels=["VF"]); e.create_edge(a, "VFR", b, qualifiers={"p": v})
                base = f"MATCH (s)-[x:VFR]->(t) WHERE s.id = '{a}'"
            cell = {}
            for ex in EXPR:
                r = e.execute_cypher(f"{base} RETURN {ex} AS r")
                cell[ex] = [type(r["rows"][0][0]).__name__, r["rows"][0][0]] if r["rows"] else f"ERROR {getattr(r, 'error', None)}"[:120]
            out["cells"][f"{kind} {v!r}"] = cell
    c.close()
    path = HERE / f"value-functions-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, v in out["cells"].items(): print(f"{k:10s}", v)
if __name__ == "__main__":
    main()
