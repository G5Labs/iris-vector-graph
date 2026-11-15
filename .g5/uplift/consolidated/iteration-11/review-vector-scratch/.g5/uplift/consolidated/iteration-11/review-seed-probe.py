"""Independent actual public seed call -> actual optimized readers; local providers only."""
import hashlib,importlib.util,json,logging,math,re,socket,sys,time,traceback
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
GUARD=patch.object(socket.socket,'connect',side_effect=AssertionError('seed source probe forbids socket'));CONNECT=GUARD.start()
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN))
p=ROOT/'.g5/uplift/consolidated/iteration-10/next-vector-survey-probe.py';s=importlib.util.spec_from_file_location('frozen_seed_providers',p);old=importlib.util.module_from_spec(s);s.loader.exec_module(old)
import iris_vector_graph.embedded as embedded
logging.disable(logging.CRITICAL)
DATA=[('g','seed',[1.,0.,0.,0.]),('g','peer',[.5,.5,0.,0.]),('other','foreign',[1.,0.,0.,0.])]
TABLE='kg_emb_0000000000000001'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rank(query,graph,exclude,k):
 norm=math.sqrt(sum(x*x for x in query));out=[]
 for g,n,v in DATA:
  if (graph is not None and g!=graph) or n==exclude:continue
  out.append((n,sum(a*b for a,b in zip(query,v))/(norm*math.sqrt(sum(x*x for x in v)))))
 return sorted(out,key=lambda x:(-x[1],x[0]))[:k]
def evaluate(sql,args):
 assert TABLE in sql
 bound='TOP ?' in sql
 if bound:k,q,graph=args[0],args[1],args[2]
 else:
  match=re.search(r'\bTOP\s+(\d+)',sql);assert match;k=int(match[1]);q,graph=args[0],args[1]
 assert 'graph_id' in sql
 exclude=args[-1] if 'n.node_id != ?' in sql else None
 return rank(json.loads(q),graph,exclude,k)
class Registry(old.Registry):
 def __init__(self):super().__init__(rows=[old.row()]);self.fail_first=False;self.scores_seen=0;self.seed_reads=0
 def cursor(self):self.opens+=1;return Cursor(self)
class Cursor(old.Cursor):
 def execute(self,sql,params=None):
  flat=' '.join(sql.split());args=list(params or []);r=self.registry
  if flat.startswith('SELECT emb FROM'):
   r.statements.append((flat,args));r.seed_reads+=1;assert TABLE in flat and 'graph_id' in flat
   v=next((v for g,n,v in DATA if n==args[0] and g==args[1]),None);self._rows=[] if v is None else [(','.join(str(x) for x in v),)];return self
  if 'VECTOR_COSINE' in flat:
   r.statements.append((flat,args));r.scores_seen+=1
   if r.fail_first and r.scores_seen==1:raise RuntimeError('named generic primary score provider failure')
   self._rows=evaluate(flat,args);return self
  return super().execute(sql,params)
def case(name,query,k,fault=False,embedded_unavailable=False):
 r=Registry();e=old.f.engine_with(r,embedding_dimension=4);e.invalidate_route_cache();r.statements.clear();r.scores_seen=0;r.seed_reads=0;r.fail_first=fault;events=[]
 def embedded_port(sql,params):
  events.append({'sql':sql,'params':list(params),'provider':'named embedded SQL over raw vectors'})
  if embedded_unavailable:raise RuntimeError('named embedded provider unavailable')
  return evaluate(sql,list(params))
 error=None;out=None
 with patch.object(embedded,'_sql_statement_execute',side_effect=embedded_port):
  try:out=e.kg_KNN_VEC(query,k=k,graph='g',model_key='m')
  except Exception as ex:error={'type':type(ex).__name__,'message':str(ex)}
 is_seed=query=='seed';intended=rank([1.,0.,0.,0.],'g','seed' if is_seed else None,k)
 expected=rank([1.,0.,0.,0.],'g',None if fault or not is_seed else 'seed',k)
 scores=[(sql,args) for sql,args in r.statements if 'VECTOR_COSINE' in sql]
 agree=error is None and out==expected and all(type(v) is float for n,v in out) and r.seed_reads==(1 if is_seed else 0)
 if fault:
  agree=agree and len(events)==1 and len(scores)==(2 if embedded_unavailable else 1) and 'n.node_id != ?' not in events[0]['sql']
  assert events[0]['params'][0].startswith('['),events
 else:agree=agree and len(events)==0 and len(scores)==1
 if is_seed:agree=agree and 'n.node_id != ?' in scores[0][0]
 return {'name':name,'raw_request':{'query':query,'k':k,'graph':'g','model':'m'},'fault_profile':{'generic_first_primary':fault,'embedded_unavailable':embedded_unavailable,'organic_outage_claim':False},'result':out,'error':error,'expected_asbuilt_from_raw_vectors':expected,'intended_seed_excluded_from_raw_request':intended,'agrees_source_prediction':agree,'intent_satisfied':out==intended,'seed_reads':r.seed_reads,'dbapi_score_attempts':len(scores),'embedded_score_attempts':events,'raw_sql':r.statements,'provider_scope':'actual public/optimized functions, raw-vector semantic SQL provider and actual float reader; no native/DB runtime or modified product method'}
def main():
 start=time.perf_counter();cases=[];failure=None
 try:
  for k in [1,2]:cases.append(case('seed-primary-success-k'+str(k),'seed',k))
  for k in [1,2]:cases.append(case('seed-primary-generic-fault-embedded-k'+str(k),'seed',k,True))
  cases.append(case('seed-primary-generic-fault-DBAPI-k2','seed',2,True,True))
  cases.append(case('literal-same-generic-fault-legal-self','[1,0,0,0]',1,True))
  assert all(c['agrees_source_prediction'] for c in cases)
  assert [c['intent_satisfied'] for c in cases]==[True,True,False,False,False,True]
  assert CONNECT.call_count==old.CONNECT.call_count==0
 except Exception as ex:failure={'type':type(ex).__name__,'message':str(ex),'trace':traceback.format_exc()}
 finally:
  good=failure is None and len(cases)==6 and all(c['agrees_source_prediction'] for c in cases) and CONNECT.call_count+old.CONNECT.call_count==0
  sources=['iris_vector_graph/_engine/vector.py','iris_vector_graph/_engine/embeddings.py','tests/unit/route_fakes_227.py']
  source={f:{'sha256':sha(PIN/f),'current_equal':sha(ROOT/f)==sha(PIN/f)} for f in sources};good=good and all(v['current_equal'] for v in source.values())
  out={'verdict':'SOURCE_CONTRAST_OBSERVED' if good else 'FAILED_OR_INCOMPLETE','cases':cases,'case_count':len(cases),'raw_vectors':DATA,'elapsed_s':time.perf_counter()-start,'socket_calls':CONNECT.call_count+old.CONNECT.call_count,'native_calls':0,'failure':failure,'candidate_inspected':False,'source_inputs':source,'inputs':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),HERE/'review-seed-predictions.md',ROOT/'.g5/uplift/consolidated/iteration-10/next-vector-survey-probe.py']},'scope':'Provider-conditioned seed exclusion loss; actual Python methods execute without product mutation. Local SQL providers derive cosine/predicates from raw data, do not supply result oracle rows. Not organic outage/native proof/new issue adjudication.'}
  Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'verdict':out['verdict'],'cases':len(cases),'elapsed':out['elapsed_s'],'sockets':out['socket_calls'],'native':0,'failure':failure}))
 return 0 if out['verdict']=='SOURCE_CONTRAST_OBSERVED' else 1
if __name__=='__main__':raise SystemExit(main())
