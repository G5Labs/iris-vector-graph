"""W22 native probe: null/missing properties in WHERE, node vs relationship (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W22_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
PRED = {"= 5": "x.p = 5", "<> 5": "x.p <> 5", "NOT = 5": "NOT x.p = 5", "IN [5,6]": "x.p IN [5, 6]",
        "NOT IN [5]": "NOT x.p IN [5]", "IS NULL": "x.p IS NULL", "IS NOT NULL": "x.p IS NOT NULL"}
def main():
    c = runtime.connect(); e = runtime.engine(c)
    worlds = {"node missing": ("node", None, False), "node 5": ("node", 5, True),
              "rel absent": ("rel", None, False), "rel {}": ("rel", {}, False), "rel {p: null}": ("rel", {"p": None}, False),
              "rel {p: 5}": ("rel", {"p": 5}, False)}
    out = {"run": RUN, "fixture": runtime.NAME, "worlds": {}}
    for i, (name, (kind, v, _)) in enumerate(worlds.items()):
        a, b = f"nl{RUN}{i}a", f"nl{RUN}{i}b"
        if kind == "node":
            e.create_node(a, labels=["NL"], properties={} if v is None else {"p": v})
            base = f"MATCH (x:NL) WHERE x.id = '{a}'"
        else:
            e.create_node(a, labels=["NL"]); e.create_node(b, labels=["NL"])
            e.create_edge(a, "NLR", b, qualifiers=v)
            base = f"MATCH (s)-[x:NLR]->(t) WHERE s.id = '{a}'"
        cur = c.cursor()
        cur.execute("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ?" if kind == "rel" else "SELECT \"key\", val FROM Graph_KG.rdf_props WHERE s = ?", [a])
        raw = [list(r) for r in cur.fetchall()]; cur.close()
        w = {"raw": raw, "return": e.execute_cypher(f"{base} RETURN x.p AS p")["rows"]}
        for k, p in PRED.items():
            r = e.execute_cypher(f"{base} AND ({p}) RETURN count(*) AS n")
            w[k] = r["rows"][0][0] if r["rows"] else f"ERROR {getattr(r, 'error', None)}"
        out["worlds"][name] = w
    c.close()
    path = HERE / f"null-semantics-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for name, w in out["worlds"].items():
        print(f"{name:14s} raw={w['raw']} return={w['return']}", " ".join(f"[{k}]={w[k]}" for k in PRED))
if __name__ == "__main__":
    main()
