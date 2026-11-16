"""W27b: node IN [number] over string values (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W27B_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
def main():
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "cells": {}}
    for i, v in enumerate(["01", "1.0", "abc", "", "x1"]):
        a = f"ni{RUN}{i}"; e.create_node(a, labels=["NI"], properties={"p": v})
        base = f"MATCH (x:NI) WHERE x.id = '{a}'"
        out["cells"][repr(v)] = {q: e.execute_cypher(f"{base} AND {q} RETURN count(*) AS n")["rows"][0][0]
                                 for q in ["x.p IN [1]", "x.p IN [0]", "x.p = 1", "x.p = 0"]}
    c.close()
    path = HERE / f"node-in-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1) + "\n"); print(path)
    for k, v in out["cells"].items(): print(f"{k:7s}", v)
if __name__ == "__main__":
    main()
