"""Root-only real routes, width preflight and actual result/IVF admission neighbors."""
import hashlib,json,runpy,subprocess,time,traceback,types,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
class Cursor:
 def __init__(self,base,events):self.base=base;self.events=events;self.event=None
 def execute(self,sql,params=None):
  self.event=dict(sql=sql,params=list(params) if params is not None else [],rows=[]);self.events.append(self.event)
  try:return self.base.execute(sql,params) if params is not None else self.base.execute(sql)
  except Exception as ex:self.event['error']=dict(type=type(ex).__name__,message=str(ex));raise
 def fetchone(self):
  row=self.base.fetchone();r=tuple(row) if row is not None else None
  if self.event is not None:self.event['rows'].append(r)
  return r
 def fetchall(self):
  rs=[tuple(x) for x in self.base.fetchall()]
  if self.event is not None:self.event['rows']+=rs
  return rs
 def __iter__(self):return iter(self.fetchall())
 def __getattr__(self,key):return getattr(self.base,key)
class Conn:
 def __init__(self,base,events):self.base=base;self.events=events
 def cursor(self,*a,**k):return Cursor(self.base.cursor(*a,**k),self.events)
 def __getattr__(self,key):return getattr(self.base,key)
class Native:
 def __init__(self,base,events):self.base=base;self.events=events
 def __getattr__(self,key):
  f=getattr(self.base,key)
  if not key.startswith('classMethod'):return f
  def call(*a,**k):self.events.append(dict(method=key,args=list(a)));return f(*a,**k)
  return call

def main():
 started=time.monotonic();inputs={};identities={}
 sources=['iris_vector_graph/_engine/vector.py','iris_vector_graph/_engine/embeddings.py','iris_vector_graph/schema.py','iris_vector_graph/embedding_identity.py','iris_vector_graph/_validate.py','iris_vector_graph/engine.py']
 for rel in sources:
  p=h['PIN_DIR']/rel;inputs[rel]=hashlib.sha256(p.read_bytes()).hexdigest();blob=subprocess.check_output(['git','rev-parse','3eaa79cf:'+rel],cwd=REPO,text=True).strip();identities[rel]=dict(pin_blob=blob,export_equals=subprocess.check_output(['git','hash-object',str(p)],text=True).strip()==blob,current_equals=subprocess.check_output(['git','hash-object',str(REPO/rel)],text=True).strip()==blob)
 assert all(x['export_equals'] and x['current_equals'] for x in identities.values())
 c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=4);e.ledger.disable();suffix=uuid.uuid4().hex[:8];g='vec11:'+suffix;model='vec11:unit:'+suffix;node='vec11:seed:'+suffix;missing='vec11:missing:'+suffix
 rows=[];sql=[];native=[];failure=None;route=None;catalog=None
 def run(label,fn,want_error=False,want_empty=False,no_score=False,no_catalog=False):
  sql.clear();native.clear();error=None;got=None
  try:got=fn()
  except Exception as ex:error=dict(type=type(ex).__name__,message=str(ex))
  score=[x for x in sql if 'VECTOR_COSINE' in x['sql'].upper()];catalogq=[x for x in sql if any(s in x['sql'].upper() for s in ['DICTIONARY','INFORMATION_SCHEMA'])]
  vector_reads=[x for x in sql if 'SELECT' in x['sql'].upper() and 'EMB' in x['sql'].upper() and 'EMBEDDINGMODELS' not in x['sql'].upper() and 'DICTIONARY' not in x['sql'].upper() and 'INFORMATION_SCHEMA' not in x['sql'].upper()]
  good=(error is not None and error['type']=='ValueError') if want_error else error is None and (got==[] if want_empty else bool(got))
  if want_error and 'wrong' in label:good=good and '3 dimensions' in error['message'] and '4-dimensional' in error['message']
  if no_score:good=good and not score and not vector_reads and not native
  if no_catalog:good=good and not catalogq
  rows.append(dict(label=label,result=got,error=error,sql=list(sql),native=list(native),score_calls=len(score),vector_read_calls=len(vector_reads),catalog_calls=len(catalogq),prediction_agrees=good));return got
 try:
  assert e.create_node(node,graph=g);assert e.store_embedding(node,[1.,0.,0.,0.],graph=g,model_key=model)
  route=e.resolve_route(g,model);assert route is not None and route.dimension==4
  n=e._iris_obj();e.conn=Conn(c,sql);spy=Native(n,native);e._iris_obj=types.MethodType(lambda self:spy,e)
  catalog=e._catalog_width(route.table_name);catalog_trace=list(sql);assert catalog==4,(catalog,catalog_trace)
  for method in ['kg_KNN_VEC','_kg_KNN_VEC_python_optimized','_kg_KNN_VEC_client_side']:
   run(method+' wrong-width',lambda method=method:getattr(e,method)('[1,2,3]',k=1,graph=g,model_key=model),want_error=True,no_score=True,no_catalog=True)
   run(method+' absent named pair',lambda method=method:getattr(e,method)('[1,2,3]',k=1,graph=missing,model_key=model),want_empty=True,no_score=True,no_catalog=True)
  run('empty literal width0',lambda:e.kg_KNN_VEC('[]',k=1,graph=g,model_key=model),want_error=True,no_score=True,no_catalog=True)
  for query in ['[1,0,0,0]','  [1, 0, 0, 0]  ',node]:
   got=run('primary admitted '+query,lambda query=query:e.kg_KNN_VEC(query,k=1,graph=g,model_key=model));assert len(got)==1 and got[0][0]==node and abs(float(got[0][1])-1)<1e-12,got
  run('IVF no route',lambda:e.ivf_build('vec11_missing_'+suffix,nlist=1,graph=missing,model_key=model),want_error=True,no_score=True,no_catalog=True)
  # Same e already missed the pair; another initialized ordinary writer creates it.
  e2=h['IRISGraphEngine'](c,embedding_dimension=4);e2.ledger.disable();node2='vec11:after:'+suffix;assert e2.create_node(node2,graph=missing);assert e2.store_embedding(node2,[1.,0.,0.,0.],graph=missing,model_key=model)
  got=run('after other engine ordinary create',lambda:e.kg_KNN_VEC('[1,0,0,0]',k=1,graph=missing,model_key=model));assert len(got)==1 and got[0][0]==node2,got
 except Exception as ex:failure=dict(type=type(ex).__name__,message=str(ex),trace=traceback.format_exc());raise
 finally:
  result=dict(verdict='AGREES' if failure is None and rows and all(r['prediction_agrees'] for r in rows) else 'DISAGREES_OR_INCOMPLETE',cases=rows,completed_cases=len(rows),failure=failure,graph=g,missing_graph=missing,model_key=model,node=node,route=vars(route) if route else None,catalog_width=catalog,catalog_trace=locals().get('catalog_trace'),identity_checked=True,container=h['NAME'],source_inputs=inputs,source_identities=identities,inputs={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'root-vector-predictions.md',REPO/'.g5/Verus_verification/models/temporal_restore/binding.py',REPO/'.g5/uplift/consolidated/iteration-5/native-setup.json']},elapsed=time.monotonic()-started,scope='Actual ordinary route/vector writers; native SQL cosine final reader; actual three entry width/absence guards and IVF no-route admission. DBAPI and classMethod spy delegates unchanged calls to owned runtime. No outage/metadata fault injection, arbitrary numeric/JSON/collation or native executable proof. Other-engine route creation is passing miss-not-cached evidence, not a bug.')
  Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
 print(json.dumps({k:result[k] for k in ['verdict','completed_cases','elapsed']}));assert result['verdict']=='AGREES'
if __name__=='__main__':main()
