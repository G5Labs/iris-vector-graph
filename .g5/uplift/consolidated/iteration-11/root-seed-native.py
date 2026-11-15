"""Controlled first primary provider failure, actual fallback and native cosine rows."""
import hashlib,json,runpy,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'));p=runpy.run_path(str(HERE/'root-vector-native.py'));Cursor=p['Cursor'];Conn=p['Conn']
class FaultCursor(Cursor):
 def __init__(self,base,events,control):super().__init__(base,events);self.control=control
 def execute(self,sql,params=None):
  if self.control['remaining'] and 'VECTOR_COSINE' in sql.upper():
   self.control['remaining']-=1;self.events.append(dict(sql=sql,params=list(params or []),rows=[],injected_error='controlled generic first score provider fault'))
   raise RuntimeError('controlled generic first score provider fault')
  return super().execute(sql,params)
class FaultConn(Conn):
 def __init__(self,base,events,control):super().__init__(base,events);self.control=control
 def cursor(self,*a,**k):return FaultCursor(self.base.cursor(*a,**k),self.events,self.control)
def main():
 start=time.monotonic();c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=4);e.ledger.disable();fixture=json.loads((HERE/'root-vector-native.json').read_text());g=fixture['graph'];model=fixture['model_key'];seed=fixture['node'];peer=next(x['result'][0][0] for x in fixture['cases'] if x['label']=='seed includes distinct peer');events=[];control={'remaining':0};rows=[];failure=None
 try:
  route=e.resolve_route(g,model);assert route is not None and route.dimension==4
  e.conn=FaultConn(c,events,control)
  for inject,query,k,label,want in [(False,seed,1,'primary seed k1',[peer]),(False,seed,2,'primary seed k2',[peer]),(True,seed,1,'generic fault seed k1',[seed]),(True,seed,2,'generic fault seed k2',[seed,peer]),(True,'[1,0,0,0]',1,'generic fault literal k1',[seed])]:
   events.clear();control['remaining']=int(inject);got=e.kg_KNN_VEC(query,k=k,graph=g,model_key=model);good=[x[0] for x in got]==want and control['remaining']==0;rows.append(dict(label=label,query=query,k=k,injected_generic_fault=inject,result=got,expected_ids=want,source_prediction_agrees=good,violates_seed_exclusion=query==seed and any(x[0]==seed for x in got),sql=list(events)));assert good,rows[-1]
 except Exception as ex:failure=dict(type=type(ex).__name__,message=str(ex),trace=traceback.format_exc());raise
 finally:
  result=dict(verdict='AGREES_SOURCE_PREDICTION' if failure is None and len(rows)==5 and all(x['source_prediction_agrees'] for x in rows) else 'DISAGREES_OR_INCOMPLETE',cases=rows,completed_cases=len(rows),failure=failure,identity_checked=True,container=h['NAME'],fixture_graph=g,model_key=model,seed=seed,peer=peer,inputs={str(q.relative_to(REPO)):hashlib.sha256(q.read_bytes()).hexdigest() for q in [Path(__file__),HERE/'root-seed-predictions.md',HERE/'root-vector-native.py',HERE/'root-vector-native.json',REPO/'.g5/Verus_verification/models/temporal_restore/binding.py',REPO/'.g5/uplift/consolidated/iteration-5/native-setup.json']},source_inputs={rel:hashlib.sha256((h['PIN_DIR']/rel).read_bytes()).hexdigest() for rel in ['iris_vector_graph/_engine/vector.py','iris_vector_graph/_engine/embeddings.py']},elapsed=time.monotonic()-start,scope='Actual Python primary/optimized fallback and native same-route/vector scoring. Exactly one generic first-score exception is injected by in-process DBAPI adapter at request start, supplying no answer/row. No organic outage or native-body proof; no data/metadata changed. Original rootvector13 facts unchanged. Seed rule is existing canonical search.knn, literal request is a lawful passing neighbor.')
  Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
 print(json.dumps({k:result[k] for k in ['verdict','completed_cases','elapsed']}));assert result['verdict']=='AGREES_SOURCE_PREDICTION'
if __name__=='__main__':main()
