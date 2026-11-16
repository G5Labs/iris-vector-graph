"""W23 native probe: STARTS WITH / CONTAINS / ENDS WITH on numeric vs string properties (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W23_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
PRED = {"STARTS WITH '1'": "x.p STARTS WITH '1'", "CONTAINS '2'": "x.p CONTAINS '2'", "ENDS WITH 'c'": "x.p ENDS WITH 'c'"}
def main():
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "worlds": {}}
    for i, v in enumerate([12, "12", "abc", 1.5]):
        for kind in ("node", "rel"):
            a, b = f"sp{RUN}{kind}{i}a", f"sp{RUN}{kind}{i}b"
            if kind == "node":
                e.create_node(a, labels=["SP"], properties={"p": v}); base = f"MATCH (x:SP) WHERE x.id = '{a}'"
            else:
                e.create_node(a, labels=["SP"]); e.create_node(b, labels=["SP"]); e.create_edge(a, "SPR", b, qualifiers={"p": v})
                base = f"MATCH (s)-[x:SPR]->(t) WHERE s.id = '{a}'"
            w = {"value": repr(v), "return": e.execute_cypher(f"{base} RETURN x.p AS p")["rows"]}
            for k, p in PRED.items():
                r = e.execute_cypher(f"{base} AND {p} RETURN count(*) AS n"); w[k] = r["rows"][0][0] if r["rows"] else f"ERROR {getattr(r, 'error', None)}"
            out["worlds"][f"{kind} {v!r}"] = w
    c.close()
    path = HERE / f"string-predicate-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for name, w in out["worlds"].items():
        print(f"{name:12s} return={w['return']}", " ".join(f"[{k}]={w[k]}" for k in PRED))
if __name__ == "__main__":
    main()
