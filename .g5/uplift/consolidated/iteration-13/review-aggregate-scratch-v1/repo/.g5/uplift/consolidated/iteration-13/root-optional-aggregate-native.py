"""Fresh ordinary caller contrast: zero rows versus synthetic optional-null row."""
import hashlib,json,runpy,time,traceback,uuid
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[3]
h=runpy.run_path(str(R/'.g5/Verus_verification/models/temporal_restore/binding.py'))
def main():
 start=time.monotonic();c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=4,native_cypher=False);assert e.ledger.meta()['state']=='disabled'
 suffix=uuid.uuid4().hex[:8];graph='ordinary13optional_'+suffix;anchor='OrdOptAnchor'+suffix;missing='OrdOptMissing'+suffix;node='ordinary13optional:'+suffix
 cases=[];queries=[];failure=None
 def q(tail):
  text=f"USE GRAPH '{graph}' "+tail;item=dict(query=text);queries.append(item)
  try:
   out=e.execute_cypher(text,raise_on_error=True);rows=[list(x) for x in out.rows];item.update(rows=rows,columns=out.columns,types=[[type(x).__name__ for x in row] for row in rows],error=out.error);assert not out.error,out.error;return rows
  except Exception as ex:item['raised']=dict(type=type(ex).__name__,text=str(ex));raise
 try:
  assert e.create_node(node,labels=[anchor],properties={'kind':'anchor'},graph=graph)
  assert q(f'MATCH (a:{anchor}) RETURN a.id,a.kind')==[[node,'anchor']]
  returns='count(*) AS rows,count(n) AS nodes,sum(n.x) AS total,avg(n.x) AS mean,collect(n.x) AS xs'
  tests=[('ordinary empty global',f'MATCH (n:{missing}) RETURN '+returns,[[0,0,0,None,[]]],[[0,0,0,None,[]]]),
   ('leading optional global',f'OPTIONAL MATCH (n:{missing}) RETURN '+returns,[[1,0,0,None,[]]],[[1,0,0,None,[]]]),
   ('leading optional grouped',f'OPTIONAL MATCH (n:{missing}) RETURN n.kind AS k,'+returns,[[None,1,0,None,None,[]]],[[None,1,0,0,None,[]]]),
   ('anchored optional global',f'MATCH (a:{anchor}) OPTIONAL MATCH (a)-[:OrdinaryMissingEdge]->(n:{missing}) RETURN '+returns,[[1,0,0,None,[]]],[[1,0,0,None,[]]])]
  for name,query,forecast,reference in tests:
   actual=q(query);cases.append(dict(name=name,actual=actual,source_forecast=forecast,r308_zero_sum_reference=reference,agrees_with_source_forecast=actual==forecast,agrees_with_zero_sum_reference=actual==reference))
 except Exception as ex:failure=dict(type=type(ex).__name__,text=str(ex),trace=traceback.format_exc())
 finally:
  c.close();sources=['iris_vector_graph/cypher/parser.py','iris_vector_graph/cypher/translator.py','iris_vector_graph/_engine/query.py','tests/unit/test_460_r298_fixes46_leftovers.py','tests/unit/test_460_r308_guards.py'];inputs=[Path(__file__),H/'root-optional-aggregate-PAIRS.md',H/'inputs.json',R/'.g5/Verus_verification/models/temporal_restore/binding.py',R/'.g5/uplift/consolidated/iteration-5/native-setup.json']
  out=dict(verdict='INCOMPLETE' if failure else 'SOURCE_FORECAST_AGREES' if len(cases)==4 and all(x['agrees_with_source_forecast'] for x in cases) else 'SOURCE_FORECAST_DIFFERS',completed_cases=len(cases),cases=cases,queries=queries,failure=failure,elapsed=time.monotonic()-start,graph=graph,anchor_id=node,container=h['NAME'],identity_checked=True,source_inputs={p:hashlib.sha256((h['PIN_DIR']/p).read_bytes()).hexdigest() for p in sources},inputs={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},scope='Fresh ordinary13 scoped healthy empty/optional caller observations only. Source forecast and newer zero-sum reference separated prospectively. No interrupted inputs/data or namespacecensus, sourcepatch/providerfault/security/globalerase/nativebody/generalSQL/JSON/IEEE or intent-adjudication claim. setup5compiledsourceauditreused.')
  Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:out[k] for k in ['verdict','completed_cases','elapsed','failure']}))
if __name__=='__main__':main()
