"""W28: inline map patterns and parameters vs WHERE =, node vs relationship (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W28_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
def main():
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "cells": {}}
    for i, v in enumerate(["1", 1, 1.0, True]):
        for kind in ("node", "rel"):
            a, b = f"pp{RUN}{kind}{i}a", f"pp{RUN}{kind}{i}b"
            if kind == "node":
                e.create_node(a, labels=["PP"], properties={"p": v})
                q = {"= 1": (f"MATCH (x:PP) WHERE x.id = '{a}' AND x.p = 1", {}),
                     "{p: 1}": (f"MATCH (x:PP {{p: 1}}) WHERE x.id = '{a}'", {}),
                     "= $v": (f"MATCH (x:PP) WHERE x.id = '{a}' AND x.p = $v", {"v": 1}),
                     "IN $list": (f"MATCH (x:PP) WHERE x.id = '{a}' AND x.p IN $list", {"list": [1]}),
                     "{p: true}": (f"MATCH (x:PP {{p: true}}) WHERE x.id = '{a}'", {})}
            else:
                e.create_node(a, labels=["PP"]); e.create_node(b, labels=["PP"]); e.create_edge(a, "PPR", b, qualifiers={"p": v})
                q = {"= 1": (f"MATCH (s)-[x:PPR]->(t) WHERE s.id = '{a}' AND x.p = 1", {}),
                     "{p: 1}": (f"MATCH (s)-[x:PPR {{p: 1}}]->(t) WHERE s.id = '{a}'", {}),
                     "= $v": (f"MATCH (s)-[x:PPR]->(t) WHERE s.id = '{a}' AND x.p = $v", {"v": 1}),
                     "IN $list": (f"MATCH (s)-[x:PPR]->(t) WHERE s.id = '{a}' AND x.p IN $list", {"list": [1]}),
                     "{p: true}": (f"MATCH (s)-[x:PPR {{p: true}}]->(t) WHERE s.id = '{a}'", {})}
            cell = {}
            for k, (text, params) in q.items():
                r = e.execute_cypher(text + " RETURN count(*) AS n", params)
                cell[k] = r["rows"][0][0] if r["rows"] else f"ERROR {getattr(r, 'error', None)}"
            out["cells"][f"{kind} {v!r}"] = cell
    c.close()
    path = HERE / f"patterns-params-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, v in out["cells"].items(): print(f"{k:10s}", v)
if __name__ == "__main__":
    main()
