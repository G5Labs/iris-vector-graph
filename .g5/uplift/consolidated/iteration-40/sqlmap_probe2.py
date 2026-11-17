import json, os, sys, time
sys.path.insert(0, os.environ["IT36"])
import runtime
TAG = time.strftime("%H%M%S", time.gmtime())
c = runtime.connect(); e = runtime.engine(c); cur = c.cursor(); S = f"W46y{TAG}"
cur.execute(f"CREATE TABLE {S}.Drug (id VARCHAR(50) PRIMARY KEY, name VARCHAR(50))")
cur.execute(f"CREATE TABLE {S}.Target (id VARCHAR(50) PRIMARY KEY, drug_id VARCHAR(50))")
cur.execute(f"INSERT INTO {S}.Drug (id, name) VALUES ('d1', 'a')"); cur.execute(f"INSERT INTO {S}.Drug (id, name) VALUES ('d3', 'c')")
cur.execute(f"INSERT INTO {S}.Target (id, drug_id) VALUES ('t1', 'd1')"); cur.execute(f"INSERT INTO {S}.Target (id, drug_id) VALUES ('t2', 'd3')"); c.commit()
L, LT = f"YD{TAG}", f"YT{TAG}"
e.map_sql_table(f"{S}.Drug", "id", L, ["name"]); e.map_sql_table(f"{S}.Target", "id", LT, [])
e.map_sql_relationship(L, "HAS", LT, target_fk="drug_id")       # FK column on the TARGET table pointing at the source
r = e.execute_cypher(f"MATCH (d:{L})-[:HAS]->(t:{LT}) RETURN d.id, t.id")
out = {"reversed_reading_rows": sorted(map(list, r.rows)) if not r.error else "ERROR " + str(r.error)[:200]}
e.create_node("ivgx" + TAG); e.create_edge("d1", "TREATS" + TAG, "ivgx" + TAG)
r2 = e.execute_cypher(f"MATCH (d:{L})-[:TREATS{TAG}]->(x) RETURN d.id, x.id")
out["mapped_to_ivg_edge"] = sorted(map(list, r2.rows)) if not r2.error else "ERROR " + str(r2.error)[:200]
r3 = e.execute_cypher(f"MATCH (d:{L}) WHERE d.id = 'd1' MATCH (d)-[r]->(x) RETURN type(r), x.id")
out["mapped_any_rel"] = sorted(map(list, r3.rows)) if not r3.error else "ERROR " + str(r3.error)[:200]
print(json.dumps(out))
