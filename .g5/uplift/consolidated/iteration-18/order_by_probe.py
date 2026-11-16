"""W19 native probe: ORDER BY over mixed property values, node vs relationship (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W19_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
VALUES = [10, 9, 2.5, "10", "9", "abc", "B", True, False, "", None]
def main():
    c = runtime.connect(); e = runtime.engine(c)
    lab, rel, anchor = f"OB{RUN}", f"OBR{RUN}", f"ob{RUN}anchor"
    e.create_node(anchor, labels=[lab + "A"])
    for i, v in enumerate(VALUES):
        props = {} if v is None else {"p": v}
        e.create_node(f"ob{RUN}n{i}", labels=[lab], properties=props)
        e.create_node(f"ob{RUN}t{i}", labels=[lab + "T"])
        e.create_edge(anchor, rel, f"ob{RUN}t{i}", qualifiers=props or None)
    out = {"run": RUN, "fixture": runtime.NAME, "values": [repr(v) for v in VALUES]}
    for d in ("", " DESC"):
        out["node" + d] = e.execute_cypher(f"MATCH (x:{lab}) RETURN x.p AS p ORDER BY x.p{d}")["rows"]
        out["rel" + d] = e.execute_cypher(f"MATCH (a:{lab}A)-[x:{rel}]->(t) RETURN x.p AS p ORDER BY x.p{d}")["rows"]
    c.close()
    path = HERE / f"order-by-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k in ("node", "rel", "node DESC", "rel DESC"):
        print(f"{k:9s}", [r[0] for r in out[k]])
if __name__ == "__main__":
    main()
