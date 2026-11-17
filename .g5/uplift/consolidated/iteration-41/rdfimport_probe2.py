import json, os, sys, time
sys.path.insert(0, os.environ["IT36"]); import runtime
c = runtime.connect(); e = runtime.engine(c); TAG = time.strftime("%H%M%S", time.gmtime())
x = os.environ["X"]
e.create_node(f"api{TAG}", properties={"yr": 2011})
cur = c.cursor()
cur.execute(f"SELECT s, \"key\", val FROM {e._ivg_schema}.rdf_props WHERE (s = ? AND \"key\" IN ('yrInt','yrStr','flag')) OR (s = ? AND \"key\" = 'yr')", [x + "s", f"api{TAG}"])
stored = sorted([list(r) for r in cur.fetchall()])
r = e.execute_cypher("MATCH (n {node_id: $s}) RETURN n.yrInt, n.yrStr, n.flag", {"s": x + "s"})
r2 = e.execute_cypher("MATCH (n {node_id: $s}) WHERE n.yrInt = 2011 RETURN count(n)", {"s": x + "s"})
r3 = e.execute_cypher("MATCH (n {node_id: $s}) RETURN n.yr", {"s": f"api{TAG}"})
print(json.dumps({"stored": stored, "cypher_values": [list(z) for z in r.rows], "cypher_eq_2011": [list(z) for z in r2.rows],
                  "api_get_node": e.get_node(f"api{TAG}").get("yr"), "api_cypher": [list(z) for z in r3.rows]}))
