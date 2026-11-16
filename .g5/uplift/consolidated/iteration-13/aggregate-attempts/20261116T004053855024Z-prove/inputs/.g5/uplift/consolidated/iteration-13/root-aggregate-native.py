"""Fresh ordinary iteration13 aggregate panel over only new isolated graphs."""
import hashlib,json,runpy,time,traceback,uuid
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[3]
h=runpy.run_path(str(R/'.g5/Verus_verification/models/temporal_restore/binding.py'))
def main():
 start=time.monotonic();c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=4,native_cypher=False)
 assert e.ledger.meta()['state']=='disabled'
 suffix=uuid.uuid4().hex[:8];graph='ordinary13agg_'+suffix;other=graph+'_other';label='OrdAgg13'+suffix;empty=label+'Empty'
 cases=[];queries=[];fixture=[];failure=None
 def q(text):
  item=dict(query=text);queries.append(item)
  try:
   out=e.execute_cypher(text,raise_on_error=True);rows=[list(x) for x in out.rows];item.update(rows=rows,columns=out.columns,error=out.error);assert not out.error,out.error;return rows
  except Exception as ex:item['raised']=dict(type=type(ex).__name__,text=str(ex));raise
 def check(name,tail,want,g=graph):
  got=q(f"USE GRAPH '{g}' "+tail);cases.append(dict(name=name,actual=got,expected=want,agrees=got==want));assert got==want,cases[-1]
 try:
  for i,(cat,value) in enumerate([('A',2),('A',2),('A',4),('B',7),('B',None)]):
   node='ordinary13agg:'+suffix+':'+str(i);props={'cat':cat}
   if value is not None:props['v']=value
   assert e.create_node(node,labels=[label],properties=props,graph=graph);fixture.append(dict(graph=graph,id=node,properties=props))
  node='ordinary13agg:'+suffix+':other';assert e.create_node(node,labels=[label],properties={'cat':'A','v':99},graph=other);fixture.append(dict(graph=other,id=node,properties={'cat':'A','v':99}))
  readback=q(f"USE GRAPH '{graph}' MATCH (n:{label}) RETURN n.id,n.cat,n.v ORDER BY n.id")
  assert readback==[[x['id'],x['properties']['cat'],x['properties'].get('v')] for x in fixture if x['graph']==graph],readback
  check('empty global count',f'MATCH (n:{empty}) RETURN count(*),count(n.v),count(DISTINCT n.v)',[[0,0,0]])
  check('empty grouped count',f'MATCH (n:{empty}) RETURN n.cat,count(*) ORDER BY n.cat',[])
  check('global bag null and distinct counts',f'MATCH (n:{label}) RETURN count(*),count(n.v),count(DISTINCT n.v)',[[5,4,3]])
  check('grouped bag null and distinct counts',f'MATCH (n:{label}) RETURN n.cat,count(*),count(n.v),count(DISTINCT n.v) ORDER BY n.cat',[['A',3,3,2],['B',2,1,1]])
  grouped=f'MATCH (n:{label}) RETURN n.cat AS cat,count(*) AS c ORDER BY c DESC,cat'
  check('aggregate ordering then limit',grouped+' LIMIT 1',[['A',3]])
  check('aggregate ordering then skip limit',grouped+' SKIP 1 LIMIT 1',[['B',2]])
  check('global distinct count order limit',f'MATCH (n:{label}) RETURN count(DISTINCT n.v) AS c ORDER BY c DESC LIMIT 5',[[3]])
  check('other fresh graph remains separate',f'MATCH (n:{label}) RETURN count(*),count(n.v),count(DISTINCT n.v)',[[1,1,1]],g=other)
 except Exception as ex:failure=dict(type=type(ex).__name__,text=str(ex),trace=traceback.format_exc())
 finally:
  c.close();sources=['iris_vector_graph/cypher/parser.py','iris_vector_graph/cypher/translator.py','iris_vector_graph/_engine/query.py','iris_vector_graph/_engine/nodes_edges.py','tests/unit/test_order_limit_aggregate_scope.py','tests/e2e/test_470_issue13_count_distinct_limit_e2e.py'];inputs=[Path(__file__),H/'root-aggregate-native-PAIRS.md',H/'inputs.json',R/'.g5/Verus_verification/models/temporal_restore/binding.py',R/'.g5/uplift/consolidated/iteration-5/native-setup.json']
  out=dict(verdict='AGREES' if failure is None and len(cases)==8 and all(x['agrees'] for x in cases) else 'DISAGREES_OR_INCOMPLETE',completed_cases=len(cases),cases=cases,queries=queries,fixture=fixture,failure=failure,elapsed=time.monotonic()-start,container=h['NAME'],identity_checked=True,source_inputs={p:hashlib.sha256((h['PIN_DIR']/p).read_bytes()).hexdigest() for p in sources},inputs={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},scope='Fresh ordinary13 only: eight actual scoped aggregate cases over new graphs, no namespace census or interrupted repro inputs/outcomes; actual pinned Python/nativeSQL with setup5 compiled audit reused. No supplied rows/faultadapter/sourcepatch/security/globalerase/nativebody proof or universal aggregate/numeric/collation/JSON/concurrency claim.')
  Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:out[k] for k in ['verdict','completed_cases','elapsed','failure']}))
if __name__=='__main__':main()
