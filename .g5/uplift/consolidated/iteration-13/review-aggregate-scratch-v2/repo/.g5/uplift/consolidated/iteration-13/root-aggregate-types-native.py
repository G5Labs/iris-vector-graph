"""Ordinary native typed SUM/WITH/AVG, fresh scoped data only."""
import hashlib,json,runpy,time,traceback,uuid
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[3]
h=runpy.run_path(str(R/'.g5/Verus_verification/models/temporal_restore/binding.py'))
def main():
 start=time.monotonic();c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=4,native_cypher=False);assert e.ledger.meta()['state']=='disabled'
 suffix=uuid.uuid4().hex[:8];label='OrdAggType13'+suffix;graphs=['ordinary13types_'+suffix+'_int','ordinary13types_'+suffix+'_float'];cases=[];queries=[];fixture=[];failure=None
 def q(graph,tail):
  text=f"USE GRAPH '{graph}' "+tail;item=dict(query=text);queries.append(item)
  try:
   out=e.execute_cypher(text,raise_on_error=True);rows=[list(x) for x in out.rows];item.update(rows=rows,types=[[type(x).__name__ for x in row] for row in rows],columns=out.columns,error=out.error);assert not out.error,out.error;return rows
  except Exception as ex:item['raised']=dict(type=type(ex).__name__,text=str(ex));raise
 def check(name,graph,tail,value,kind):
  got=q(graph,tail);ok=got==[[value]] and type(got[0][0]).__name__==kind;cases.append(dict(name=name,actual=got,actual_type=type(got[0][0]).__name__ if got else None,expected=[[value]],expected_type=kind,agrees=ok));assert ok,cases[-1]
 try:
  for graph,values in zip(graphs,[[1,3],[1.5,2.5]]):
   for i,value in enumerate(values):
    node='ordinary13types:'+suffix+':'+graph.rsplit('_',1)[1]+':'+str(i);assert e.create_node(node,labels=[label],properties={'x':value},graph=graph);fixture.append(dict(graph=graph,id=node,x=value,type=type(value).__name__))
   readback=q(graph,f'MATCH (n:{label}) RETURN n.id,n.x ORDER BY n.id')
   expected=[[x['id'],x['x']] for x in fixture if x['graph']==graph];assert readback==expected and all(type(row[1]) is type(want[1]) for row,want in zip(readback,expected)),readback
  check('integer property sum',graphs[0],f'MATCH (n:{label}) RETURN sum(n.x) AS total',4,'int')
  check('float whole property sum',graphs[1],f'MATCH (n:{label}) RETURN sum(n.x) AS total',4.0,'float')
  check('float whole sum through WITH',graphs[1],f'MATCH (n:{label}) WITH sum(n.x) AS s RETURN s',4.0,'float')
  check('float average',graphs[1],f'MATCH (n:{label}) RETURN avg(n.x) AS mean',2.0,'float')
 except Exception as ex:failure=dict(type=type(ex).__name__,text=str(ex),trace=traceback.format_exc())
 finally:
  c.close();sources=['iris_vector_graph/cypher/parser.py','iris_vector_graph/cypher/translator.py','iris_vector_graph/_engine/query.py','iris_vector_graph/_engine/nodes_edges.py','tests/unit/test_sum_column_typing.py'];inputs=[Path(__file__),H/'root-aggregate-types-PAIRS.md',H/'inputs.json',R/'.g5/Verus_verification/models/temporal_restore/binding.py',R/'.g5/uplift/consolidated/iteration-5/native-setup.json']
  out=dict(verdict='AGREES' if failure is None and len(cases)==4 and all(x['agrees'] for x in cases) else 'DISAGREES_OR_INCOMPLETE',completed_cases=len(cases),cases=cases,queries=queries,fixture=fixture,failure=failure,elapsed=time.monotonic()-start,container=h['NAME'],identity_checked=True,source_inputs={p:hashlib.sha256((h['PIN_DIR']/p).read_bytes()).hexdigest() for p in sources},inputs={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},scope='Fresh ordinary13 only: four actual scoped typed SUM/WITH/AVG cases over new graphs and typed fixture readback; no interrupted inputs/data, namespacecensus, suppliedrows/faultadapter/sourcepatch/security/globalerase/nativebody proof or universal numeric/JSON/driver/concurrency claim. setup5compiledsourceauditreused.')
  Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:out[k] for k in ['verdict','completed_cases','elapsed','failure']}))
if __name__=='__main__':main()
