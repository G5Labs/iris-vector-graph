import sys
sys.path.insert(0, sys.argv[1])
from iris_vector_graph.cypher.parser import parse_query
from iris_vector_graph.cypher import native_plan
from iris_vector_graph.cypher.native_shadow import compare, NativeMismatch
qs = {
 "agg_order_by_count_limit": "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name AS n, count(*) AS c ORDER BY c DESC LIMIT 1",
 "agg_order_by_count": "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name AS n, count(*) AS c ORDER BY c DESC",
 "agg_order_by_key_limit": "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name AS n, count(*) AS c ORDER BY n LIMIT 1",
 "nonagg_order_ties_limit": "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name AS n, b.name AS m ORDER BY n LIMIT 1",
}
for k, q in qs.items():
    p = native_plan.plan_query(parse_query(q), {})
    print(k, "planned" if p else "declined", p and {"ordered": p["ordered"], "limited": p["limited"]})
# SQL top-1 by count is Alice(3); native returns Bob(1): wrong top-k
sql_rows=[["Alice",3]]; full=[["Alice",3],["Bob",1]]
for nat, lab in (([["Bob",1]], "wrong top-1"),):
    try:
        compare("q", {}, ["n","c"], sql_rows, ["n","c"], nat, ordered=False, limited=True, sql_unlimited_rows=full); print(lab, "-> PASS (accepted)")
    except NativeMismatch as e: print(lab, "-> RAISE", e)
# unlimited, order violated by native
try:
    compare("q", {}, ["n","c"], [["Alice",3],["Bob",1]], ["n","c"], [["Bob",1],["Alice",3]], ordered=False, limited=False); print("reversed count order, no limit -> PASS (accepted)")
except NativeMismatch as e: print("reversed -> RAISE", e)
