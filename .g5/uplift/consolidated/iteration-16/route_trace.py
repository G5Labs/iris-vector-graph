"""Translation-only trace (no database): which translator members the W16 queries execute. Run with the pin on sys.path."""
import json, os, sys
sys.path.insert(0, os.environ["IVG_PIN_DIR"])
import iris_vector_graph.cypher.translator as T
from iris_vector_graph.cypher.parser import parse_query
calls = []
for name in ["_stored_bool_in", "_stored_bool_comparison", "_node_number_eq_sql", "_number_eq_sql", "_number_texts", "_stored_number_test", "bool_spellings_sql"]:
    f = getattr(T, name)
    setattr(T, name, lambda *a, _f=f, _n=name, **k: (calls.append(_n), _f(*a, **k))[1])
out = {}
for q in ["MATCH (x:TE) WHERE x.id = 'a' AND x.p = true RETURN count(*) AS n", "MATCH (x:TE) WHERE x.id = 'a' AND x.p = 1 RETURN count(*) AS n",
          "MATCH (s)-[x:TER]->(t) WHERE s.id = 'a' AND x.p = true RETURN count(*) AS n", "MATCH (s)-[x:TER]->(t) WHERE s.id = 'a' AND x.p = 12 RETURN count(*) AS n"]:
    calls.clear()
    r = T.translate_to_sql(parse_query(q))
    sql = getattr(r, "sql", str(r))
    out[q] = {"members": sorted(set(calls)), "legacy_in_list": "IN ('true', '1', 'True')" in sql, "sql": sql}
print(json.dumps(out, indent=1))
