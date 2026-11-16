"""W16 native probe: typed WHERE equality on node vs relationship properties (run-isolated fixture only)."""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402

RUN = os.environ.get("W16_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
VALUES = {"int1": 1, "boolT": True, "str1": "1", "f095": 0.95, "str095": "0.95", "int0": 0, "boolF": False}
LITERALS = ["true", "false", "1", "0", "0.95"]


def run(e, q):
    try:
        return e.execute_cypher(q)["rows"]
    except Exception as x:
        return f"ERROR {type(x).__name__}: {x}"


def main():
    c = runtime.connect()
    e = runtime.engine(c)
    out = {"run": RUN, "fixture": runtime.NAME, "worlds": {}}
    for name, v in VALUES.items():
        for kind in ("node", "rel"):
            a, b = f"w16{RUN}{kind}{name}a", f"w16{RUN}{kind}{name}b"
            if kind == "node":
                e.create_node(a, labels=["W16"], properties={"p": v})
                base = f"MATCH (x:W16) WHERE x.id = '{a}'"
                raw = None
                cur = c.cursor()
                cur.execute("SELECT val FROM Graph_KG.rdf_props WHERE s = ? AND \"key\" = 'p'", [a])
                raw = [list(r) for r in cur.fetchall()]
                cur.close()
            else:
                e.create_node(a, labels=["W16"])
                e.create_node(b, labels=["W16"])
                e.create_edge(a, "W16R", b, qualifiers={"p": v})
                base = f"MATCH (s)-[x:W16R]->(t) WHERE s.id = '{a}'"
                cur = c.cursor()
                cur.execute("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ?", [a])
                raw = [list(r) for r in cur.fetchall()]
                cur.close()
            w = {"value": repr(v), "raw": raw, "return": run(e, f"{base} RETURN x.p AS p")}
            for lit in LITERALS:
                w["eq " + lit] = run(e, f"{base} AND x.p = {lit} RETURN count(*) AS n")
                w["ne " + lit] = run(e, f"{base} AND x.p <> {lit} RETURN count(*) AS n")
            out["worlds"][f"{kind}:{name}"] = w
    c.close()
    path = HERE / f"typed-equality-observed-{RUN}.json"
    path.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(path)
    for k, w in out["worlds"].items():
        cells = " ".join(f"{lit}={w['eq ' + lit][0][0] if isinstance(w['eq ' + lit], list) else 'E'}" for lit in LITERALS)
        print(f"{k:12s} raw={w['raw']} return={w['return']} {cells}")


if __name__ == "__main__":
    main()
