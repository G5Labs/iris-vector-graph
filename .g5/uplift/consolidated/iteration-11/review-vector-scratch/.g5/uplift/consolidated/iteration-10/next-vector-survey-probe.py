"""Read-only actual pinned vector admission/cache/IVF functions over local fakes.
No native/runtime/network or security tests. No formal model/credit is claimed.
"""
import copy,hashlib,importlib.util,inspect,json,logging,socket,sys,textwrap,time,traceback
from pathlib import Path
from unittest.mock import patch
NETWORK=patch.object(socket.socket,'connect',side_effect=AssertionError('vector survey forbids network'))
CONNECT=NETWORK.start();logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN))
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
f=load('vector_survey_route_fakes',PIN/'tests/unit/route_fakes_227.py')
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph._engine.embeddings import EmbeddingsMixin
from iris_vector_graph._engine.vector import VectorMixin
import iris_vector_graph._engine.embeddings as emb
import iris_vector_graph.embedded as embedded

class Registry(f.FakeRegistry):
 def __init__(self,rows=(),catalog=None,registry_error=None,raw_rows=None,score_error=None,scores=None,client_rows=None,ivf_rows=None):
  super().__init__(rows=list(rows));self.catalog=catalog or {};self.registry_error=registry_error;self.raw_rows=raw_rows;self.score_error=score_error;self.scores=[('n',0.75)] if scores is None else scores;self.client_rows=client_rows or [('n','1,0,0,0')];self.ivf_rows=ivf_rows or [];self.opens=0
 def cursor(self):self.opens+=1;return Cursor(self)

class Cursor(f.FakeCursor):
 def execute(self,sql,params=None):
  flat=' '.join(str(sql).split());args=list(params or []);r=self.registry;special=True;rows=[]
  if 'embedding_registry' in flat and flat.upper().startswith('SELECT') and 'table_name, dimension' in flat:
   if r.registry_error is not None:rows=r.registry_error
   elif r.raw_rows is not None:rows=r.raw_rows
   else:return super().execute(sql,params)
  elif '%Dictionary.CompiledClass' in flat:rows=RuntimeError('catalog class unavailable') if r.catalog.get('error') else [('Graph.KG.VectorSurvey',)]
  elif '%Dictionary.CompiledProperty' in flat:rows=RuntimeError('catalog properties unavailable') if r.catalog.get('error') else [(v,) for v in r.catalog.get('params',[])]
  elif 'INFORMATION_SCHEMA.COLUMNS' in flat and "COLUMN_NAME = 'emb'" in flat:rows=RuntimeError('catalog columns unavailable') if r.catalog.get('error') else r.catalog.get('info',[])
  elif 'VECTOR_COSINE' in flat:
   outcome=r.score_error.pop(0) if isinstance(r.score_error,list) and r.score_error else r.score_error
   rows=outcome if outcome is not None and outcome!=[] else r.scores
  elif flat.startswith('SELECT TOP 1 emb FROM'):rows=[('1,0,0,0',)]
  elif flat.startswith('SELECT emb FROM'):rows=[('1,0,0,0',)]
  elif flat.startswith('SELECT n.node_id, n.emb FROM'):rows=r.client_rows
  elif flat.startswith('SELECT node_id, emb FROM'):rows=r.ivf_rows
  else:special=False
  if not special:return super().execute(sql,params)
  r.statements.append((flat,args))
  if isinstance(rows,BaseException):raise rows
  self._rows=list(rows);return self

def row(g='g',m='m',table='kg_emb_0000000000000001',dimension=4,kind='node',dtype='DOUBLE'):
 return dict(graph_id=g,model_key=m,table_name=table,dimension=dimension,kind=kind,dtype=dtype,index_state='present',index_error=None)

def scores(r):return [x for x in r.statements if 'VECTOR_COSINE' in x[0]]
def registry_reads(r):return [x for x in r.statements if 'embedding_registry' in x[0] and x[0].startswith('SELECT') and 'table_name, dimension' in x[0]]
def metadata_reads(r):return [x for x in r.statements if '%Dictionary' in x[0] or ('INFORMATION_SCHEMA' in x[0] and "'emb'" in x[0])]
def invoke(e,method,q,**kw):
 try:return {'kind':'rows','value':getattr(e,method)(q,k=2,graph='g',model_key='m',**kw)}
 except Exception as ex:return {'kind':'error','type':type(ex).__name__,'message':str(ex)}

def search_case(label,q,dimension=4,catalog=None,present=True,method='kg_KNN_VEC',registry_error=None,raw_rows=None,score_error=None,score_rows=None):
 provider_input=[str(x) for x in score_error] if isinstance(score_error,list) else (str(score_error) if score_error is not None else None)
 r=Registry(rows=[row(dimension=dimension)] if present else [],catalog=catalog,registry_error=registry_error,raw_rows=raw_rows,score_error=None,scores=score_rows)
 e=f.engine_with(r,embedding_dimension=4);r.statements.clear();r.opens=0
 r.score_error=list(score_error) if isinstance(score_error,list) else score_error
 with patch.object(embedded,'_sql_statement_execute',side_effect=RuntimeError('embedded route unavailable')):
  out=invoke(e,method,q)
 return {'label':label,'method':method,'query':repr(q),'dimension':repr(dimension),'catalog':catalog or {},'present':present,'provider_error_input':provider_input,'output':out,'score_statements':len(scores(r)),'metadata_statements':len(metadata_reads(r)),'registry_statements':len(registry_reads(r)),'sql':r.statements,'cache_keys':list(getattr(e,'_route_cache_store',{}))}

def variant(owner,name,find,replace):
 src=textwrap.dedent(inspect.getsource(getattr(owner,name)));assert src.count(find)==1,(name,find)
 ns=dict(vars(sys.modules[owner.__module__]));exec(src.replace(find,replace),ns);return ns[name]

class Native:
 def __init__(self):self.calls=[]
 def classMethodValue(self,cls,method,*args):
  self.calls.append((cls,method,args))
  return json.dumps({'nlist':1,'dim':4,'metric':'cosine','indexed':1}) if method=='Info' else 1

def ivf_case(label,present=True,node_ids=None,rows=None):
 r=Registry(rows=[row()] if present else [],ivf_rows=rows);e=f.engine_with(r,embedding_dimension=4);r.statements.clear();r.opens=0;n=Native();e._iris_obj=lambda:n
 try:out={'kind':'result','value':e.ivf_build('survey',nlist=1,node_ids=node_ids,graph='g',model_key='m')}
 except Exception as ex:out={'kind':'error','type':type(ex).__name__,'message':str(ex)}
 table_reads=[x for x in r.statements if x[0].startswith('SELECT node_id, emb')]
 return {'label':label,'present':present,'node_ids':node_ids,'output':out,'table_reads':table_reads,'native_port_calls':n.calls,'registry_reads':len(registry_reads(r)),'cursor_opens':r.opens}

def cache_probes():
 now=[0.0];records=[]
 with patch.object(emb.time,'monotonic',side_effect=lambda:now[0]):
  r=Registry();a=f.engine_with(r,embedding_dimension=4);b=f.engine_with(r,embedding_dimension=4);r.statements.clear()
  first=a._read_route('g','m');before=len(registry_reads(r));created=b.resolve_route('g','m',create=True,dimension=4);aftercreate=len(registry_reads(r));second=a._read_route('g','m')
  records.append({'case':'miss-then-other-engine-real-create','first':repr(first),'created':repr(created),'second':repr(second),'registry_reads_after_miss':before,'after_create':aftercreate,'after_second':len(registry_reads(r)),'miss_cache_empty':before==1 and bool(second[1]),'actual_writer':'resolve_route/_create_route over existing FakeRegistry SQL/DDL; no native DB'})
  r=Registry(rows=[row('g1','m1','kg_emb_000000000000000a'),row('g2','m1','kg_emb_000000000000000b'),row('g1','m2','kg_emb_000000000000000c'),row('g1','m1','kg_emb_000000000000000f',kind='edge')]);e=f.engine_with(r,embedding_dimension=4);r.statements.clear()
  pair_tables=[e._read_route(g,m,kind=k)[1].table_name for g,m,k in [('g1','m1','node'),('g2','m1','node'),('g1','m2','node'),('g1','m1','edge'),('g1','m1','node')]]
  records.append({'case':'per-graph-model-kind-key','tables':pair_tables,'reads':len(registry_reads(r)),'keys':list(e._route_cache_store)})
  r=Registry(rows=[row(table='kg_emb_000000000000000d')]);e=f.engine_with(r,embedding_dimension=4);r.statements.clear();timeline=[]
  for clock in [0.0,30.0,30.001]:
   now[0]=clock
   if clock>0:r.rows[0]['table_name']='kg_emb_000000000000000e';r.rows[0]['dimension']=3
   z=e._read_route('g','m')[1];timeline.append({'time':clock,'table':z.table_name,'dimension':z.dimension,'reads':len(registry_reads(r))})
  records.append({'case':'positive-cache-TTL-boundary','timeline':timeline,'provider_change':'raw registry provider replacement, not a claimed ordinary writer race'})
  e.invalidate_route_cache('g','m');z=e._read_route('g','m')[1];records.append({'case':'explicit-invalidation','table':z.table_name,'reads':len(registry_reads(r))})
 return records

def main():
 began=time.monotonic();cases=[]
 queries=['[1,2,3]','[1,2,3,4]',' [1,2,3] ','[]','[.1,2,3]','[[1,2],[3,4]]','[true,false,null,"x"]','[NaN,Infinity,-Infinity,0]','node:seed',[1,2,3],(1,2,3),None,5]
 catalogs={'none':{},'comma':{'params':['TYPE,VECTOR,LEN,4']},'control':{'params':['LEN\x01\x034']},'info':{'info':[('VECTOR(DOUBLE,4)',None,None)]},'unsupported_digits':{'info':[('VARCHAR(4000)',None,None)]},'error':{'error':True}}
 for method in ['kg_KNN_VEC','_kg_KNN_VEC_python_optimized','_kg_KNN_VEC_client_side']:
  for q in queries:cases.append(search_case('raw-carrier',q,method=method))
  for name,cat in catalogs.items():cases.append(search_case('catalog-'+name,'[1,2,3]',dimension=None,catalog=cat,method=method))
  for dim in [None,'',0,False,True,'4','bad']:
   cases.append(search_case('typed-route-dimension','[1,2,3,4]',dimension=dim,catalog=catalogs['comma'],method=method))
  cases.append(search_case('absent-wrong-width','[1,2,3]',present=False,method=method))
 for err in [RuntimeError('registry provider unavailable'),RuntimeError('[SQLCODE: <-30>:<Table or view not found>]')]:cases.append(search_case('registry-failure','[1,2,3,4]',registry_error=err))
 for raw in [[('short',)],[(None,4,'DOUBLE',None,None)],[('kg_emb_0000000000000002',4,7,None,None)]]:cases.append(search_case('raw-registry-shape','[1,2,3,4]',raw_rows=raw))
 for method in ['kg_KNN_VEC','_kg_KNN_VEC_python_optimized']:
  cases.append(search_case('provider-width-error-unknown-catalog','[1,2,3]',dimension=None,method=method,score_error=RuntimeError('SQLCODE -257 vectors of different lengths')))
  cases.append(search_case('provider-generic-error','[1,2,3,4]',method=method,score_error=RuntimeError('provider score unavailable')))
 cases.append(search_case('public-immediate-257','[1,2,3]',dimension=None,catalog={'error':True},score_error=RuntimeError('SQLCODE -257 vectors of different lengths')))
 cases.append(search_case('public-generic-then-257','[1,2,3]',dimension=None,catalog={'error':True},score_error=[RuntimeError('primary score provider unavailable'),RuntimeError('SQLCODE -257 vectors of different lengths')]))
 for rr in [[('n',None)],[('n','0.75')],[('n',1)],[('n',True)]]:cases.append(search_case('typed-score-reader','[1,2,3,4]',score_rows=rr))
 ivf=[ivf_case('no-route',False,['n']),ivf_case('empty-node-list',True,[]),ivf_case('routed-empty-table'),ivf_case('routed-one-vector',rows=[('n','1,0,0,0')])]
 cache=cache_probes();sensitivity={}
 base=search_case('control','[1,2,3]')
 fn=variant(VectorMixin,'_assert_query_width','if width == int(dimension):','if True:')
 with patch.object(IRISGraphEngine,'_assert_query_width',fn):changed=search_case('control','[1,2,3]')
 width_control={'original':base,'changed':changed}
 sensitivity['actual_width_guard_removed']=base['output']['kind']=='error' and base['score_statements']==0 and changed['score_statements']>0
 fn=variant(VectorMixin,'_assert_query_width','if not dimension:\n        dimension = self._catalog_width(table)','if True:\n        dimension = self._catalog_width(table)')
 with patch.object(IRISGraphEngine,'_assert_query_width',fn):changed=search_case('control-precedence','[1,2,3]',dimension=4,catalog={'params':['LEN,3']})
 precedence_control=changed
 sensitivity['actual_route_width_precedence_lost']=changed['output']['kind']=='rows' and changed['score_statements']>0
 fn=variant(EmbeddingsMixin,'_route_cache_key','graph_id or ""','""')
 with patch.object(IRISGraphEngine,'_route_cache_key',fn):
  r=Registry(rows=[row('g1','m','kg_emb_000000000000000a'),row('g2','m','kg_emb_000000000000000b')]);e=f.engine_with(r,embedding_dimension=4);z=[e._read_route(g,'m')[1].table_name for g in ['g1','g2']]
 sensitivity['actual_cache_graph_key_removed']=z!=['kg_emb_000000000000000a','kg_emb_000000000000000b']
 inputs={rel:hashlib.sha256((PIN/rel).read_bytes()).hexdigest() for rel in ['iris_vector_graph/_engine/vector.py','iris_vector_graph/_engine/embeddings.py','iris_vector_graph/schema.py','iris_vector_graph/_engine/schema.py','iris_vector_graph/embedding_identity.py','iris_vector_graph/_validate.py','tests/unit/route_fakes_227.py']}
 checks={'three_direct_mismatch_no_score':all(c['output']['kind']=='error' and c['score_statements']==0 for c in cases if c['label']=='raw-carrier' and c['query']==repr('[1,2,3]')),'absent_pair_empty':all(c['output']=={'kind':'rows','value':[]} and c['score_statements']==0 for c in cases if c['label']=='absent-wrong-width'),'other_engine_create_visible':cache[0]['after_second']>cache[0]['after_create'] and 'EmbeddingRoute' in cache[0]['second'],'ivf_no_route_no_table_or_build':ivf[0]['output']['kind']=='error' and not ivf[0]['table_reads'] and not ivf[0]['native_port_calls']}
 mixed=next(c for c in cases if c['label']=='public-generic-then-257');immediate=next(c for c in cases if c['label']=='public-immediate-257')
 checks['public_mixed_failure_boundary_retained']=mixed['output']=={'kind':'rows','value':[]} and mixed['score_statements']==2 and immediate['output']['kind']=='error' and immediate['output']['type']=='ValueError' and immediate['score_statements']==1
 out={'verdict':'OBSERVED' if all(checks.values()) and all(sensitivity.values()) and CONNECT.call_count==0 else 'CHECK_FAILED','cases':cases,'case_count':len(cases),'ivf':ivf,'cache':cache,'checks':checks,'sensitivity':sensitivity,'sensitivity_observations':{'width':width_control,'precedence':precedence_control,'cache_key_tables':z},'source_inputs':inputs,'current_equals_pin':{rel:hashlib.sha256((REPO/rel).read_bytes()).hexdigest()==h for rel,h in inputs.items()},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'socket_connect_calls':CONNECT.call_count,'elapsed':time.monotonic()-began,'scope':'Actual Python routes/raw-width/catalog/fallback/IVF admission/readers over local SQL/metadata/Native-port fakes, actual one-row local clustering; no native server execution. Unsupported literals/types retained as observed carrier branches, no native acceptance or formal proof.'}
 Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps({'verdict':out['verdict'],'cases':len(cases),'checks':checks,'sensitivities':sensitivity,'elapsed':out['elapsed'],'sockets':CONNECT.call_count}));assert out['verdict']=='OBSERVED'
if __name__=='__main__':main()
