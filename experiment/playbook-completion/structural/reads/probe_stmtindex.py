"""Feasibility probe 1: does the IRIS SQL statement index (INFORMATION_SCHEMA.STATEMENTS / STATEMENT_RELATIONS /
STATEMENT_LOCATIONS) observe which tables a statement read, per execution, immediately after it runs?
Runs: (a) one harness dynamic statement with a unique alias; (b) a product reader with embedded SQL
(Graph.KG.Eraser.EraseAll's routes cursor, Graph.KG.Ledger reads) and a product Python reader (engine.get_node).
Reads StatCount before/after per statement hash. Observation only."""
import json, sys, time, uuid
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'live'))
import lib

def stats(c, like=None, loc=None):
    if loc:
        q = ("SELECT s.Hash, s.StatCount, s.Statement, l.Location FROM INFORMATION_SCHEMA.STATEMENTS s "
             "JOIN INFORMATION_SCHEMA.STATEMENT_LOCATIONS l ON l.Statement = s.Hash WHERE l.Location %STARTSWITH ?")
        rows = c.sql(q, loc)
    else:
        rows = c.sql("SELECT Hash, StatCount, Statement, NULL FROM INFORMATION_SCHEMA.STATEMENTS WHERE Statement LIKE ?", like.upper())
    return {str(h): {"count": cnt, "sql": str(s)[:160], "loc": str(l) if l else None} for h, cnt, s, l in rows}

def rel(c, h):
    return [str(r[0]) for r in c.sql("SELECT Relation FROM INFORMATION_SCHEMA.STATEMENT_RELATIONS WHERE Statement = ?", h)]

out = {}
c = lib.conn()
lib.reset(c)
e = lib.engine(c)
e.create_node("rd:a", labels=["L"], properties={"k": "v"})
c.conn.commit()
tag = "ivgauditdrd" + uuid.uuid4().hex[:8]
q = f"SELECT COUNT(*) AS {tag} FROM Graph_KG.nodes WHERE node_id = ?"
c.sql(q, "rd:a")
time.sleep(1)
s1 = stats(c, like=f"%{tag}%")
c.sql(q, "rd:a"); c.sql(q, "rd:b")
time.sleep(1)
s2 = stats(c, like=f"%{tag}%")
out["dynamic_harness"] = {"first": s1, "after_two_more": s2, "relations": {h: rel(c, h) for h in s2}}
# embedded SQL of a product class: Graph.KG.Eraser
before = stats(c, loc="Graph.KG.Eraser")
c.call("Graph.KG.Eraser", "EraseAll"); c.conn.commit()
time.sleep(1)
after = stats(c, loc="Graph.KG.Eraser")
changed = {h: [before.get(h, {}).get("count"), v["count"], v["sql"][:100]] for h, v in after.items()
           if before.get(h, {}).get("count") != v["count"]}
out["embedded_eraser"] = {"statements_located_in_class": len(after), "stat_changed_after_EraseAll": changed,
                          "sample": list(after.values())[:3]}
# product Python reader: engine.get_node
e.create_node("rd:a", labels=["L"], properties={"k": "v"}); c.conn.commit()
pyb = stats(c, like="%rdf_props%")
e.get_node("rd:a")
time.sleep(1)
pya = stats(c, like="%rdf_props%")
out["python_get_node"] = {h: [pyb.get(h, {}).get("count"), v["count"], v["sql"]] for h, v in pya.items()
                          if pyb.get(h, {}).get("count") != v["count"]}
out["new_python_statements"] = [v["sql"] for h, v in pya.items() if h not in pyb]
lib.reset(c)
c.close()
p = lib.OUT / "reads" / "probe-stmtindex.json"
lib.dump(p, out)
print(json.dumps(out, indent=1, default=str)[:6000])
