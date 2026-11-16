"""Actual pinned parser -> SQL translator/caller -> executing provider/store -> final result reader.
No sockets, native calls, supplied aggregate rows, Git or quarantined inputs.
"""
from pathlib import Path
import ast,copy,hashlib,itertools,json,logging,os,socket,sys,time,types,traceback
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];OUT=ROOT/'.g5/uplift/consolidated/iteration-13'
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
# Guard installed before any product imports. Native APIs are never called.
sockets=[]
def no_socket(*a,**k):sockets.append(dict(args=str(a),kwargs=str(k),stack=traceback.format_stack()));raise AssertionError('network prohibited')
class GuardedSocket(socket.socket):
 def __new__(cls,*a,**k):return no_socket(*a,**k)
socket.socket=GuardedSocket;socket.create_connection=no_socket
# Disable urllib3 import-time IPv6 capability socket; this is an environment capability, not a provider reply.
socket.has_ipv6=False
PIN=bc.import_pin()
from iris_vector_graph.cypher.parser import parse_query
from iris_vector_graph.cypher.translator import translate_to_sql
from iris_vector_graph._engine import query as qm
from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
from iris_vector_graph.result import IVGResult
import provider as pr
import functional_model as fm
class Caller(qm.QueryMixin):
 _fetch_first_unsafe=True
 _store_capabilities={'native_sql':True}
 def __init__(self,p):self._store=object.__new__(IRISGraphStore);self._store.conn=p
 def get_table_mapping(self,*a,**k):return None
 def get_rel_mapping(self,*a,**k):return None

def execute(records,text,params=None,edges=(),module=qm):
 p=pr.Provider();p.load(records,edges);parsed=parse_query(text);c=Caller(p)
 r=module.QueryMixin._execute_parsed_sql(c,parsed,params or {})
 module._fill_empty_columns(r,parsed)
 assert not r.error,dict(error=r.error,trace=p.trace,query=text)
 return r,p.trace

def tagged(v):
 if isinstance(v,list):return [tagged(x) for x in v]
 if isinstance(v,tuple):return [tagged(x) for x in v]
 if isinstance(v,dict):return {str(k):tagged(x) for k,x in v.items()}
 return [type(v).__name__,v]

def raw_oracle(records,graph,grouped,distinct):
 # Independent batch relational definition; no accumulator/model output supplied to provider.
 chosen=[r for r in records if graph is None or r[0]==graph]
 ks=list(dict.fromkeys(r[2] for r in chosen)) if grouped else [None]
 out={}
 for k in ks:
  rs=[r for r in chosen if not grouped or r[2]==k];vs=[r[3] for r in rs if r[3] is not None]
  if distinct:vs=list(dict.fromkeys(vs)) # admitted numbers/null only; scalar SQL equality boundary.
  total=sum(vs);floating=any(type(r[3])is float for r in rs)
  out[k]=dict(star=len(rs),count=len(vs),total=float(total) if floating else int(total),mean=float(total/len(vs)) if vs else None,items=vs)
 return out

def source_module(path,name,find,replace):
 src=(PIN/path).read_text();assert src.count(find)==1,(find,src.count(find));m=types.ModuleType(name);m.__package__='iris_vector_graph._engine' if path.endswith('/query.py') else 'iris_vector_graph.cypher';sys.modules[name]=m;exec(compile(src.replace(find,replace),str(PIN/path), 'exec'),m.__dict__);return m

def main():
 start=time.monotonic()
 for rel,wanted in json.loads((HERE/'binding_inputs.json').read_text()).items():assert bc.sha(ROOT/rel)==wanted,('stale declared binding input',rel)
 cases=[];trace_examples=[];mismatches=[];comparisons=0
 fixtures=[[]]
 vals=[None,0,1,1.5,2]
 for n in range(1,4):
  for vv in itertools.product(vals,repeat=n):fixtures.append([('g','n'+str(i),'A' if i%2==0 else 'B',v) for i,v in enumerate(vv)])
 fixtures += [[('g','i','A',1),('g','d','A',1.0)],[('g','a','A',-0.5),('g','b','A',0.5)],[('g','n0',None,None),('g','n1',None,None)],[('g','n0','A',1),('other','n0','A',99)]]
 for fno,records in enumerate(fixtures):
  for grouped,distinct in itertools.product([False,True],repeat=2):
   spec=fm.fold(records,'g',grouped,distinct);oracle=raw_oracle(records,'g',grouped,distinct);assert tagged(spec)==tagged(oracle)
   dk='DISTINCT ' if distinct else '';head='n.k AS k, ' if grouped else ''
   text="USE GRAPH 'g' MATCH (n:Report) RETURN "+head+f'count(*) AS star,count({dk}n.v) AS c,sum({dk}n.v) AS s,avg({dk}n.v) AS a'
   result,trace=execute(records,text)
   wanted=[([k] if grouped else [])+[v['star'],v['count'],v['total'],v['mean']] for k,v in oracle.items()]
   got=sorted([tagged(r) for r in result.rows],key=repr);want=sorted([tagged(r) for r in wanted],key=repr)
   comparisons+=1
   if got!=want:mismatches.append(dict(fixture=fno,query=text,got=got,want=want,trace=trace))
   if fno in (0,1,len(fixtures)-1):trace_examples.append(dict(raw=records,query=text,columns=result.columns,rows=result.rows,trace=trace))
 # Actual WITH-stage numeric producer and final reader.
 for values in [[],[None],[1,3],[1.5,2.5],[1,1.5]]:
  records=[('g',str(i),'A',v) for i,v in enumerate(values)];want=raw_oracle(records,'g',False,False)[None]['total']
  r,tr=execute(records,"USE GRAPH 'g' MATCH (n:Report) WITH sum(n.v) AS s RETURN s")
  assert tagged(r.rows)==tagged([[want]]);comparisons+=1;cases.append(dict(kind='WITH sum',raw=records,rows=r.rows,trace=tr))
 # Scalar known-list collection: SQL provider sees raw literals/parameters, reader decodes actual JSON text.
 collection_values=[[],[None],[1,1,None,2.5],['a','b','a',None],[False,True,None],[True,True,False]]
 for values in collection_values:
  literal=json.dumps(values).replace('"',"'");text=f'UNWIND {literal} AS x RETURN collect(x) AS xs,collect(DISTINCT x) AS dx'
  nonnull=[x for x in values if x is not None];unique=list(dict.fromkeys(nonnull));want=[nonnull,unique]
  for query,params in [(text,{}),('UNWIND $values AS x RETURN collect(x) AS xs,collect(DISTINCT x) AS dx',{'values':values})]:
   r,tr=execute([],query,params)
   assert tagged(r.rows)==tagged([want]),dict(q=query,got=r.rows,want=want,trace=tr);comparisons+=1;cases.append(dict(kind='collect literal/parameter',raw=values,params=params,rows=r.rows,trace=tr))
 # Stored-property collection executes the actual text-serialization producer and JSON final reader.
 for values in [[],[None,None],[1,2.5,None,1],['7','text','',None],['true','false']]:
  records=[('g',str(i),'A',v) for i,v in enumerate(values)]
  r,tr=execute(records,"USE GRAPH 'g' MATCH (n:Report) RETURN collect(n.v) AS xs,collect(DISTINCT n.v) AS dx")
  vs=[v for v in values if v is not None];logical=[True if v=='true' else False if v=='false' else v for v in vs]
  wanted=[logical,list(dict.fromkeys(logical))]
  assert tagged(r.rows)==tagged([wanted]),dict(raw=records,rows=r.rows,wanted=wanted,trace=tr)
  comparisons+=1;cases.append(dict(kind='property collect',raw=records,trace=tr,rows=r.rows))
 # Generic SQL graph+identity expression is tested on its actual grouped branch (no fast-path scope claim).
 records=[('g','same','A',2),('other','same','A',9)]
 r,tr=execute(records,'MATCH (n:Report) RETURN n.k AS k,count(DISTINCT n) AS c')
 expected=len({(g,id) for g,id,k,v in records});assert r.rows==[['A',expected]]
 comparisons+=1;cases.append(dict(kind='generic graph+ID distinct',raw=records,trace=tr,rows=r.rows))
 # Leading OPTIONAL pure/global and grouped-null fallbacks are separate reachable source-shaped branches.
 optional_observations=[]
 for grouped,wanted in [(False,[[1,0,0,None,[]]]),(True,[[None,1,0,None,None,[]]])]:
  head='n.k AS k,' if grouped else ''
  text="USE GRAPH 'g' OPTIONAL MATCH (n:Report) RETURN "+head+'count(*) AS star,count(n.v) AS c,sum(n.v) AS s,avg(n.v) AS a,collect(n.v) AS xs'
  r,tr=execute([],text);assert tagged(r.rows)==tagged(wanted)
  comparisons+=1;optional_observations.append(dict(kind='leading OPTIONAL null-row',query=text,raw=[],trace=tr,rows=r.rows,disposition='As-built R298 typed fallback; not equated to ordinary raw-row SUM fold; no new issue inferred.'))
 cases+=optional_observations
 # Actual multikey edge join multiplicity, counted after raw SQL JOIN, not a prepared row stream.
 records=[('g','a','A',2),('g','b','B',4)];edges=[('g','a','R','b','e0'),('g','a','R','b','e1')]
 r,tr=execute(records,"USE GRAPH 'g' MATCH (n:Report)-[r:R]->(m:Report) RETURN count(*) AS c,count(DISTINCT r) AS d",edges=edges)
 assert r.rows==[[2,2]];comparisons+=1;cases.append(dict(kind='edge multiplicity',raw_edges=edges,trace=tr,rows=r.rows))
 # ORDER/page operates after complete groups; store strips __rn, finalizer strips __sort.
 records=[('g','a0','A',2),('g','a1','A',2),('g','b','B',7)]
 for tail,want in [('ORDER BY c DESC LIMIT 1',[['A',2]]),('ORDER BY c DESC SKIP 1 LIMIT 1',[['B',1]]),('ORDER BY c DESC LIMIT 0',[])]:
  r,tr=execute(records,"USE GRAPH 'g' MATCH (n:Report) RETURN n.k AS k,count(*) AS c "+tail)
  assert tagged(r.rows)==tagged(want) and r.columns==['k','c'];comparisons+=1;cases.append(dict(kind='page',trace=tr,rows=r.rows,columns=r.columns))
 # Actual empty-column finalizer is AST-derived and preserves error/existing data.
 for text in ['MATCH (n) RETURN n.v AS value,count(*) AS c LIMIT 0','MATCH (n) RETURN *']:
  parsed=parse_query(text);r=IVGResult(columns=[],rows=[]);qm._fill_empty_columns(r,parsed);cases.append(dict(kind='empty columns',query=text,columns=r.columns));assert r.columns==(['value','c'] if 'value' in text else [])
 r=IVGResult(columns=[],rows=[],error='provider ordinary error');qm._fill_empty_columns(r,parse_query('RETURN 1 AS x'));assert r.columns==[]
 assert not mismatches,mismatches[:1]
 # Located real source-copy alterations; no product files are modified.
 sensitivities=[]
 def detect(name,check):
  detected=check();assert detected,name;sensitivities.append(dict(name=name,detected=True))
 old=pr.sql_adapter
 detect('SQL distinct removed provider contrast',lambda: _adapter_contrast())
 detect('observation corruption rejected',lambda: tagged([[99]])!=tagged([[3]]))
 # Additional source mutants installed only in private module dictionaries.
 tpath='iris_vector_graph/cypher/translator.py';qpath='iris_vector_graph/_engine/query.py'
 original=qm.translate_to_sql
 mutant=source_module(tpath,'iris_vector_graph.cypher.aggregate_mutant_distinct',"result_expr = f\"{fn}({'DISTINCT ' if expr.distinct else ''}{arg})\"","result_expr = f\"{fn}({arg})\"")
 qm.translate_to_sql=mutant.translate_to_sql
 r,_=execute([('g','0','A',2),('g','1','A',2)],"USE GRAPH 'g' MATCH (n:Report) RETURN count(DISTINCT n.v) AS c")
 qm.translate_to_sql=original;detect('actual translator DISTINCT omission',lambda:r.rows!=[[1]])
 mutant=source_module(tpath,'iris_vector_graph.cypher.aggregate_mutant_float',"f\"CASE WHEN MAX({_fn('CY_IS_FLOAT')}({arg})) = 1 \"","f\"CASE WHEN 0 = 1 \"")
 qm.translate_to_sql=mutant.translate_to_sql;r,_=execute([('g','0','A',1.5),('g','1','A',2.5)],"USE GRAPH 'g' MATCH (n:Report) RETURN sum(n.v) AS s");qm.translate_to_sql=original
 detect('actual translator raw-float presence lost',lambda:tagged(r.rows)!=tagged([[4.0]]))
 mutant=source_module(qpath,'iris_vector_graph._engine.aggregate_mutant_drop','    _drop_internal_columns(result)\n','    pass # omitted internal projection\n')
 r,_=execute(records,"USE GRAPH 'g' MATCH (n:Report) RETURN n.k AS k,count(*) AS c ORDER BY c DESC LIMIT 1",module=mutant)
 detect('actual finalizer internal sort retained',lambda:r.columns!=['k','c'])
 mutant=source_module(qpath,'iris_vector_graph._engine.aggregate_mutant_json','                row[i] = decode_json_value(v)\n','                row[i] = v\n')
 r,_=execute([],'UNWIND [1,2] AS x RETURN collect(x) AS xs',module=mutant);detect('actual finalizer JSON decode omitted',lambda:tagged(r.rows)!=tagged([[[1,2]]]))
 mutant=source_module(tpath,'iris_vector_graph.cypher.aggregate_mutant_null_collect',"return _json_text_list_agg(f\"NULLIF({_elem_text}, 'null')\", expr.distinct)","return _json_text_list_agg(_elem_text, expr.distinct)")
 qm.translate_to_sql=mutant.translate_to_sql;r,_=execute([],'UNWIND [true,null] AS x RETURN collect(x) AS xs');qm.translate_to_sql=original
 detect('actual translator collection null admitted',lambda:tagged(r.rows)!=tagged([[[True]]]))
 mutant=source_module(qpath,'iris_vector_graph._engine.aggregate_mutant_avg_type','                row[i] = _float_expr_value(row[i])\n','                row[i] = row[i]\n')
 r,_=execute([('g','0','A',1),('g','1','A',3)],"USE GRAPH 'g' MATCH (n:Report) RETURN avg(n.v) AS a",module=mutant)
 detect('actual finalizer AVG float type omitted',lambda:tagged(r.rows)!=tagged([[2.0]]))
 mutant=source_module(qpath,'iris_vector_graph._engine.aggregate_mutant_typed_sum','    _decode_typed_value_columns(result, sql_query)\n','    pass # omitted typed scalar reader\n')
 r,_=execute([('g','0','A',1.5),('g','1','A',2.5)],"USE GRAPH 'g' MATCH (n:Report) RETURN sum(n.v) AS s",module=mutant)
 detect('actual finalizer SUM tag decode omitted',lambda:tagged(r.rows)!=tagged([[4.0]]))
 assert sockets==[],sockets
 inputs={}
 paths=list(HERE.glob('*'))+[HERE.parents[1]/'tools/binding_common.py',ROOT/'.g5/Verus_verification/models/node_read/node_read.rs',OUT/'aggregate-PAIRS.md',OUT/'aggregate-start.json']
 for stem in ['root-aggregate-native','root-aggregate-types-native']:
  for ext in ['py','json','log']:paths.append(OUT/(stem+'.'+ext))
 paths += [OUT/'root-aggregate-native-PAIRS.md',OUT/'root-aggregate-types-PAIRS.md']
 product=['iris_vector_graph/cypher/parser.py','iris_vector_graph/cypher/ast.py','iris_vector_graph/cypher/translator.py','iris_vector_graph/_engine/query.py','iris_vector_graph/stores/iris_sql_store.py','iris_vector_graph/prop_values.py','iris_vector_graph/schema.py','iris_src/src/Graph/KG/Cypher/Exec.cls']
 identity={f:hashlib.sha256((PIN/f).read_bytes()).hexdigest()==hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in product};assert all(identity.values())
 paths += [ROOT/f for f in product]
 # Native evidence closure is flat-stamped (read only; never executed here).
 for stem in ['root-aggregate-native','root-aggregate-types-native']:
  data=json.loads((OUT/(stem+'.json')).read_text())
  paths += [ROOT/p for p in data.get('inputs',{})]
 paths += [ROOT/p for p in json.loads((HERE/'binding_inputs.json').read_text())]
 for p in paths:
  if p.is_file():inputs[str(p.resolve().relative_to(ROOT))]=bc.sha(p)
 body=dict(verdict='AGREES',comparisons=comparisons,fixtures=len(fixtures),mismatches=mismatches,cases=cases,trace_examples=trace_examples,sensitivities=sensitivities,socket_attempts=len(sockets),native_calls=0,pin_export_equals_current=identity,inputs=inputs,elapsed_s=time.monotonic()-start,scope='Finite correspondence of real parser, translator, QueryMixin._execute_parsed_sql, IRISGraphStore.execute_sql and _finish_sql_result with a local executing SQLite provider. SQL numeric/equality/collation/UDF/JSON substitutes, not native-body/driver/codec theorem. Numeric inputs exact half units; scalar collection cases; actual source mutants separate from provider/observation controls.')
 receipt=bc.write_receipt('aggregate_results',Path(__file__),body);(OUT/'aggregate-binding.json').write_text(json.dumps(body,indent=2,default=str)+'\n');print(json.dumps({k:body[k] for k in ['verdict','comparisons','fixtures','socket_attempts','elapsed_s']}));print(receipt)

def _adapter_contrast():
 old=pr.sql_adapter
 try:
  pr.sql_adapter=lambda x:old(x).replace('COUNT(DISTINCT ','COUNT(')
  r,_=execute([('g','0','A',2),('g','1','A',2)],"USE GRAPH 'g' MATCH (n:Report) RETURN count(DISTINCT n.v) AS c")
  return r.rows!=[[1]]
 finally:pr.sql_adapter=old
if __name__=='__main__':main()
