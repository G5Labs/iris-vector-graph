"""W27 native probe: IN lists and min/max over Python-written mixed values, node vs relationship (fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W27_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
def main():
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "in": {}, "minmax": {}}
    for i, v in enumerate(["1", 1, True]):
        for kind in ("node", "rel"):
            a, b = f"ro{RUN}{kind}{i}a", f"ro{RUN}{kind}{i}b"
            if kind == "node":
                e.create_node(a, labels=["RO"], properties={"p": v}); base = f"MATCH (x:RO) WHERE x.id = '{a}'"
            else:
                e.create_node(a, labels=["RO"]); e.create_node(b, labels=["RO"]); e.create_edge(a, "ROR", b, qualifiers={"p": v})
                base = f"MATCH (s)-[x:ROR]->(t) WHERE s.id = '{a}'"
            out["in"][f"{kind} {v!r}"] = {lst: e.execute_cypher(f"{base} AND x.p IN {lst} RETURN count(*) AS n")["rows"][0][0] for lst in ["[1]", "[true]", "['1']"]}
    lab, R, A = f"ROM{RUN}", f"ROMR{RUN}", f"rom{RUN}A"
    e.create_node(A, labels=[lab + "A"])
    for i, v in enumerate(["9", 5]):
        e.create_node(f"rom{RUN}n{i}", labels=[lab], properties={"p": v})
        e.create_node(f"rom{RUN}t{i}", labels=[lab + "T"]); e.create_edge(A, R, f"rom{RUN}t{i}", qualifiers={"p": v})
    out["minmax"]["node"] = e.execute_cypher(f"MATCH (x:{lab}) RETURN min(x.p), max(x.p)")["rows"]
    out["minmax"]["rel"] = e.execute_cypher(f"MATCH (a:{lab}A)-[x:{R}]->(t) RETURN min(x.p), max(x.p)")["rows"]
    c.close()
    path = HERE / f"remaining-operators-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, v in out["in"].items(): print("IN", f"{k:10s}", v)
    print("minmax", out["minmax"])
if __name__ == "__main__":
    main()
