"""Bounded independent actual pinned-source probes; no new candidate/native import."""
import hashlib,importlib.util,json,logging,math,os,re,socket,sys,time,traceback
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
GUARD=patch.object(socket.socket,'connect',side_effect=AssertionError('independent vector fresh probe prohibits sockets'));CONNECT=GUARD.start()
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN))
p=ROOT/'.g5/uplift/consolidated/iteration-10/next-vector-survey-probe.py';sp=importlib.util.spec_from_file_location('inherited_frozen_vector_fakes',p);old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old)
from iris_vector_graph._engine import embeddings as emb
import iris_vector_graph.embedded as embedded
logging.disable(logging.CRITICAL)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fresh(raw=None):
 r=old.Registry(rows=[old.row()]);e=old.f.engine_with(r,embedding_dimension=4);r.statements.clear();r.opens=0;e.invalidate_route_cache()
 if raw is not None:r.raw_rows=raw
 return r,e
def effects(r):
 return {'registry_reads':len(old.registry_reads(r)),'sql_score_attempts':len(old.scores(r)),'metadata_reads':len(old.metadata_reads(r)),'client_vector_reads':sum(s.startswith('SELECT n.node_id, n.emb FROM') for s,a in r.statements),'cursor_opens':r.opens,'sql':r.statements}
def result(fn):
 try:return {'kind':'value','value':fn()}
 except Exception as ex:return {'kind':'error','type':type(ex).__name__,'message':str(ex)}
def record(out,name,input,observation,agrees):out.append({'name':name,'input':input,'observation':observation,'agrees':bool(agrees)});assert agrees,name
class Fault(RuntimeError):
 def __init__(self,message,sqlcode):super().__init__(message);self.sqlcode=sqlcode
class BuildPort:
 def __init__(self,malformed):self.calls=[];self.malformed=malformed
 def classMethodValue(self,cls,method,*args):
  self.calls.append({'class':cls,'method':method,'args':list(args)})
  return ('not-json' if self.malformed else json.dumps({'nlist':1,'dim':4,'metric':'cosine','indexed':1})) if method=='Info' else 1

def main():
 start=time.perf_counter();cases=[];failure=None
 try:
  literals=[('nested-object','[{"k":[1,2]},[3,4]]',2),('escaped-strings',r'["comma,] and quote\"", "[,]"]',2),('nonnumeric','[true,false,null,"x"]',4),('python-extensions','[NaN,Infinity,-Infinity]',3),('numeric-exponents',' \n[1,-2.5e+2,3E-4]\t',3),('empty','[]',0)]
  for name,q,width in literals:
   assert len(json.loads(q.strip()))==width
   for dim in ([4] if width==0 else [width,width+1]):
    r,e=fresh();r.rows[0]['dimension']=dim;z=result(lambda:e.kg_KNN_VEC(q,k=2,graph='g',model_key='m'));eff=effects(r)
    if dim==width:
     okay=z=={'kind':'value','value':[('n',.75)]} and eff['sql_score_attempts']==1 and old.scores(r)[0][1][1]==q
    else:
     okay=z['kind']=='error' and z['type']=='ValueError' and f'{width} dimensions' in z['message'] and f'{dim}-dimensional' in z['message'] and eff['sql_score_attempts']==eff['client_vector_reads']==0
    record(cases,'V5-'+name+'-route'+str(dim),{'raw_query':q,'hand_expected_outer_count':width,'raw_recorded_dimension':dim,'native_numeric_element_acceptance':'unassessed'}, {'result':z,**eff},okay)
  for label,raw in [('attribute-30',Fault('absent by numeric attribute',-30)),('message-30',RuntimeError('[SQLCODE: <-30>:<Table or view not found>]')),('other-error',RuntimeError('registry provider unavailable')),('nearby-text-not-classified',RuntimeError('unrelated raw -30 text'))]:
   r,e=fresh();r.registry_error=raw;z=result(lambda:e._route_for_read('g','m'));eff=effects(r)
   absent=label in ['attribute-30','message-30'];okay=(z['kind']=='value' and z['value']==('kg_NodeEmbeddings',None)) if absent else z['kind']=='error' and z['type']==type(raw).__name__
   okay=okay and eff['registry_reads']==1 and eff['sql_score_attempts']==0 and not getattr(e,'_route_cache_store',{})
   record(cases,'V8-'+label,{'exception_type':type(raw).__name__,'sqlcode':getattr(raw,'sqlcode',None),'message':str(raw)}, {'result':z,**eff},okay)
  now=[0.0]
  with patch.object(emb.time,'monotonic',side_effect=lambda:now[0]):
   r,e=fresh();timeline=[]
   for clock in [0.0,30.0,30.001]:
    now[0]=clock
    if clock:r.registry_error=RuntimeError('current backend non-30 failure')
    z=result(lambda:e._read_route('g','m'));timeline.append({'time':clock,'result':repr(z),'registry_reads':len(old.registry_reads(r)),'cache':repr(getattr(e,'_route_cache_store',{}))})
   okay=[x['registry_reads'] for x in timeline]==[1,1,2] and 'current backend non-30 failure' not in timeline[1]['result'] and "'kind': 'error'" in timeline[2]['result'] and not e._route_cache_store
   record(cases,'V11-unexpired-hit-hides-backend-error-until-expiry',{'clock':[0,30,30.001],'backend_after_initial_read':'non-30 exception'},timeline,okay)
   now[0]=0;r,e=fresh([(None,4,'DOUBLE',None,None)]);first=result(lambda:e._read_route('g','m'));r.registry_error=RuntimeError('backend hidden by decoded-row hit');now[0]=30
   z=result(lambda:e.kg_KNN_VEC('[1,2,3]',graph='g',model_key='m'));eff=effects(r)
   okay=first['kind']=='value' and first['value'][0] is True and first['value'][1].table_name is None and z=={'kind':'value','value':[]} and eff['registry_reads']==1 and eff['sql_score_attempts']==eff['metadata_reads']==0 and bool(e._route_cache_store)
   record(cases,'V8-V11-decoded-tableNone-is-cached-row-not-negative-cache',{'raw_row':[None,4,'DOUBLE',None,None],'clock_after_read':30,'backend':'non-30 error'}, {'first':repr(first),'search':z,'cache':repr(e._route_cache_store),**eff},okay)
  for mode in ['embedded-success','embedded-unavailable-DBAPI-success']:
   r,e=fresh();rows=[(None,'0.5'),('keep','0.75')];r.scores=rows;events=[]
   def embedded_port(sql,params):
    events.append({'sql':sql,'params':list(params),'provider':mode})
    if mode!='embedded-success':raise RuntimeError('named embedded unavailable')
    return rows
   with patch.object(embedded,'_sql_statement_execute',side_effect=embedded_port):z=result(lambda:e._kg_KNN_VEC_python_optimized('[1,2,3,4]',k=2,graph='g',model_key='m'))
   eff=effects(r);want=[('keep',.75)] if mode=='embedded-success' else [(None,.5),('keep',.75)]
   okay=z=={'kind':'value','value':want} and len(events)==1 and eff['sql_score_attempts']==(0 if mode=='embedded-success' else 1) and eff['client_vector_reads']==0
   record(cases,'V13-'+mode,{'provider_rows':rows,'query':'[1,2,3,4]'}, {'result':z,'embedded_attempts':events,**eff},okay)
  for malformed in [False,True]:
   r,e=fresh();r.ivf_rows=[('n','1,0,0,0')];port=BuildPort(malformed);e._iris_obj=lambda:port;name='review_fresh_bad' if malformed else 'review_fresh_good';before=(dict(e._index_registry),dict(e._index_graph_scopes))
   z=result(lambda:e.ivf_build(name,nlist=1,graph='g',model_key='m'));after=(dict(e._index_registry),dict(e._index_graph_scopes));methods=[x['method'] for x in port.calls]
   okay=methods==['Build','AddBatch','FinalizeIndex','Info'] and len([x for x in r.statements if x[0].startswith('SELECT node_id, emb FROM')])==1
   if malformed:okay=okay and z['kind']=='error' and z['type']=='JSONDecodeError' and after==before
   else:okay=okay and z=={'kind':'value','value':{'nlist':1,'dim':4,'metric':'cosine','indexed':1}} and e._index_registry[name]=='ivf' and e._index_graph_scopes[name]=='g'
   record(cases,'V18-IVF-'+('malformed-Info-after-effects' if malformed else 'successful-Info-local-writes'),{'ivf_rows':r.ivf_rows,'malformed_info':malformed}, {'result':z,'local_before':before,'local_after':after,'class_method_port_events':port.calls,**effects(r)},okay)
 except Exception as ex:failure={'type':type(ex).__name__,'message':str(ex),'trace':traceback.format_exc()}
 finally:
  names={x['name'] for x in cases};required={'V11-unexpired-hit-hides-backend-error-until-expiry','V8-V11-decoded-tableNone-is-cached-row-not-negative-cache','V13-embedded-success','V13-embedded-unavailable-DBAPI-success','V18-IVF-malformed-Info-after-effects'}
  good=failure is None and len(cases)>=20 and required<=names and all(c['agrees'] for c in cases) and CONNECT.call_count==old.CONNECT.call_count==0
  sources=['iris_vector_graph/_engine/vector.py','iris_vector_graph/_engine/embeddings.py','iris_vector_graph/schema.py','iris_vector_graph/_validate.py','tests/unit/route_fakes_227.py']
  source_inputs={s:{'sha256':sha(PIN/s),'current_equal':sha(ROOT/s)==sha(PIN/s)} for s in sources};good=good and all(x['current_equal'] for x in source_inputs.values())
  out={'verdict':'OBSERVED_SOURCE_AGREES' if good else 'FAILED_OR_INCOMPLETE','cases':cases,'completed_cases':len(cases),'failure':failure,'elapsed_s':time.perf_counter()-start,'socket_connect_calls':CONNECT.call_count+old.CONNECT.call_count,'native_calls':0,'candidate_files_inspected':[],'source_inputs':source_inputs,'inputs':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'.g5/uplift/consolidated/iteration-10/next-vector-survey-probe.py',HERE/'review-vector-expectations.md']},'helper_substitutions':['inherited FakeRegistry/FakeCursor+capability constructor fixtures; request statistics reset after construction','time.monotonic controlled input for actual cache methods','embedded._sql_statement_execute named external SQL provider returning raw rows or raising, actual optimized reader unchanged','_iris_obj named local Build/AddBatch/Finalize/Info port, actual one-vector sklearn clustering; no native method executed'],'scope':'Actual source admission, cache writers/readers, embedded-vs-DBAPI typed final readers and IVF post-Build Info conversion over named local fakes. Numeric element/native binder/cosine/clustering/native index/transactional rollback correctness not inferred. No formal or new issue/coverage claim.'}
  Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps({'verdict':out['verdict'],'cases':len(cases),'sockets':out['socket_connect_calls'],'native':0,'elapsed':out['elapsed_s'],'failure':failure}))
 return 0 if out['verdict']=='OBSERVED_SOURCE_AGREES' else 1
if __name__=='__main__':raise SystemExit(main())
