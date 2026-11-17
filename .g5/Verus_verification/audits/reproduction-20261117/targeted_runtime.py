"""Independent public-entry witnesses for additions without a binding-suite witness.

Run on the isolated continuation fixture with its venv; exports are unchanged.
Every case records the query, runtime answer, expectation and passing neighbor.
No model predictions or mocked product outcomes are used.
"""
import datetime, json, os, pathlib, sys, time

ROOT = pathlib.Path.home() / 'experiments/iris-issue-reproduction-20261117'
TREE = ROOT / 'tree'
sys.path.insert(0, str(TREE / '.g5/uplift/consolidated/iteration-36'))
import runtime
from iris_vector_graph.engine import IRISGraphEngine

c = runtime.connect()
e = IRISGraphEngine(c, embedding_dimension=768, native_cypher=False)
tag = time.strftime('%H%M%S', time.gmtime())
label = 'Audit84' + tag
p = 'audit84_' + tag + '_'
e.create_node(p+'a', labels=[label], properties={'num':5, 'str':'abc', 's':'\t a \n', 'f':0, 'l':[1,2,3], 'k':'gotcha'})
e.create_node(p+'b', labels=[label+'B'], properties={'num':6})
M = f"MATCH (n:{label})"
cases = {}

def q(key, query, params=None):
    cell = {'query':query, 'params':params or {}}
    try:
        r = e.execute_cypher(query, params or {})
        cell.update(rows=[list(row) for row in r.rows], error=str(r.error) if r.error else None)
        cell['types'] = [[type(v).__name__ for v in row] for row in r.rows]
    except Exception as ex:
        cell['exception'] = type(ex).__name__ + ': ' + str(ex)
    cases[key] = cell
    return cell

q('111_bad', M+' UNWIND [-1] AS i RETURN n.l[i]')
q('111_type', M+' UNWIND [0] AS i RETURN n.l[i]')
q('111_control', M+' RETURN n.l[-1]')
q('112_bad', M+' RETURN reverse(n.l)')
q('112_control', 'RETURN reverse([1,2,3])')
q('113_bad', M+" UNWIND ['num'] AS k RETURN n[k]")
q('113_control', M+" RETURN n['num']")
q('114_bad', 'UNWIND [1,2,3,4,5] AS i RETURN randomUUID(), rand()')
q('114_create', f'CREATE (n:{label}Random {{u:randomUUID()}})')
q('114_control', 'RETURN randomUUID(), rand()')
q('126_index_bad', M+' UNWIND [null] AS i RETURN n.l[i]')
q('126_index_control', M+' RETURN n.l[3]')
q('115_bad', "WITH {a:1, b:2.5, c:true, d:[1]} AS m UNWIND ['a','b','c','d'] AS k RETURN k, m[k]")
q('115_control', "WITH {a:1} AS m RETURN m['missing']")
q('116_bad', M+' RETURN head(n.num)')
q('116_control', 'RETURN head([5])')
q('122_bad', 'WITH [1,2,3] AS l, 1 AS a RETURN l[a..3]')
q('122_control', 'WITH [1,2,3] AS l RETURN l[1..3]')
q('124_bad', "RETURN left('hello',0), right('hello',0), substring('hello',2,0)")
q('124_control', "RETURN left('hello',1), right('hello',1), substring('hello',2,1)")
q('128_bad', M+' SET n.l1 = [n.num, 1]')
q('128_read', M+' RETURN n.l1')
q('128_control', M+' SET n.l1 = [5, 1] RETURN n.l1')
q('130_bad', M+' RETURN trim(n.s)')
q('130_control', "RETURN trim('  a  ')")
q('130_create', f"CREATE (n:{label}T {{s:trim('\\t a \\n')}}) RETURN n.s")
q('131_bad', 'UNWIND [1.5] AS s RETURN range(1,3,s)')
q('131_control', 'UNWIND [2] AS s RETURN range(1,5,s)')
q('131_literal', 'RETURN range(1,3,1.5)')
q('relationship_setup', f"MATCH (n:{label}), (b:{label}B) CREATE (n)-[r:AUDIT84{tag} {{age:'30', v:1}}]->(b)")
R = f'MATCH (n:{label})-[r:AUDIT84{tag}]->(b)'
q('132_bad', R+' SET r.age = toInteger(r.age)')
q('132_control', R+' SET r.v = r.v + 1 RETURN r.v')
q('150_bad', R+' WITH * RETURN type(r)')
q('150_control', R+' WITH n, r, b RETURN type(r)')
q('151_bad', M+' WITH *, n.num AS v RETURN v')
q('151_control', M+' WITH n, n.num AS v RETURN v')
q('152_bad', M+' FOREACH (x IN [1,2] | SET n.f = x)')
q('152_read', M+' RETURN n.f')
q('152_control', M+' FOREACH (x IN [1,2] | SET n.f = 5)')
q('152_control_read', M+' RETURN n.f')
q('157_bad', 'UNWIND [1,2] AS i CALL { WITH i RETURN i*2 AS d } RETURN i,d')
q('157_control', 'UNWIND [1,2] AS i CALL { RETURN 5 AS d } RETURN i,d')
q('158_bad', "UNWIND [2,'a',null,1.5,true] AS x RETURN x ORDER BY x")
q('158_control', "UNWIND [2,'a',null,1.5,true] AS x WITH x ORDER BY x RETURN x")

e.create_node(p+'g1', labels=[label+'G'], properties={'v':1})
e.create_node(p+'g2', labels=[label+'G'], properties={'v':'1'})
q('136_sql', f'MATCH (n:{label}G) RETURN n.v, count(*)')
e = IRISGraphEngine(c, embedding_dimension=768, native_cypher=True)
q('136_native', f'MATCH (n:{label}G) RETURN n.v, count(*)')

os.environ.update(IRIS_HOST='127.0.0.1', IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE='USER',
                  IRIS_USERNAME='_SYSTEM', IRIS_PASSWORD='SYS', BOLT_ENABLED='0')
from fastapi.testclient import TestClient
from iris_vector_graph import cypher_api
with TestClient(cypher_api.app) as client:
    for key, text in [('126_bad',M+' RETURN n'), ('126_control',M+' RETURN properties(n)')]:
        r = client.post('/db/neo4j/tx/commit', json={'statements':[{'statement':text,'parameters':{}}]})
        cases[key] = {'query':text, 'status':r.status_code, 'body':r.json()}

result = {'time':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'product':runtime.PRODUCT,
          'fixture':runtime.NAME, 'entry':'execute_cypher; 126 uses real FastAPI route and database in-process',
          'native_cypher':False, 'cases':cases}
dst=ROOT/'evidence/targeted-runtime.json'
dst.write_text(json.dumps(result,indent=2,default=str)+'\n')
print(json.dumps(result,indent=2,default=str))
c.close()
