"""(Second run records IVGResult.error; the first runs, kept under failed-runs/, read only the rows and so
showed an error as an empty answer.) W59 follow-up after the source read: a WHERE inside OPTIONAL MATCH over several condition shapes, on a node whose only
optional matches all fail the condition (a2 -> a3, a3 has no v) beside one that has a passing match (a1 -> a2).
Prediction (openCypher, owner query.optional, stated before running): every shape keeps one row per a; a2's row has b
null. The source shows a fallback (translate_where_clause) that puts `(b IS NULL OR cond)` in the WHERE when the
condition holds a property-value subquery; this probe checks which shapes reach it. Fresh tag; USER."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i54w_{TAG}_"; A = f"I54W{TAG}"; K = f"KW{TAG}"
CONDS = {"eq_int": "b.v = 2", "gt_int": "b.v > 1", "eq_str": "b.name = 'a2'", "starts": "b.name STARTS WITH 'a2'",
         "in_list": "b.v IN [2]", "fn_upper": "toUpper(b.name) = 'A2'", "arith": "b.v + 0 = 2", "size": "size(b.name) = 2 AND b.v = 2",
         "not_null": "b.v IS NOT NULL", "param": "b.v = $v", "mixed": "b.v = a.v + 1", "rel_prop": "r.w = 1"}
def main():
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "product": runtime.PRODUCT}
    e.create_node(P + "a1", labels=[A], properties={"name": "a1", "v": 1})
    e.create_node(P + "a2", labels=[A], properties={"name": "a2", "v": 2})
    e.create_node(P + "a3", labels=[A], properties={"name": "a3"})
    e.create_edge(P + "a1", K, P + "a2", qualifiers={"w": 1}); e.create_edge(P + "a2", K, P + "a3", qualifiers={"w": 5})
    for k, cond in CONDS.items():
        q = f"MATCH (a:{A}) OPTIONAL MATCH (a)-[r:{K}]->(b) WHERE {cond} RETURN a.name, b.name ORDER BY a.name"
        try:
            r = e.execute_cypher(q, {"v": 2}); out[k] = {"q": q, "rows": [list(x) for x in r.rows], "error": (str(r.error)[:300] if getattr(r, "error", None) else None)}
        except Exception as x:
            out[k] = {"q": q, "error": f"{type(x).__name__}: {x}"[:300]}
    c.close()
    p = HERE / f"optional-where-observed-{RUN}.json"; p.write_text(json.dumps(out, indent=1) + "\n"); print(p)
if __name__ == "__main__":
    main()
