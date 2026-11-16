"""Actual pinned hydration -> executing SQL -> real NDJSON files -> actual import callback arguments.
No Native/network/Git, supplied rows/results, generic codec/inverse/persistence or whole-body proof.
"""
from pathlib import Path
import copy,datetime,hashlib,inspect,itertools,json,logging,os,socket,sys,textwrap,time,types
logging.disable(logging.CRITICAL);socket.has_ipv6=False
sockets=[]
class Guard(socket.socket):
 def __new__(cls,*a,**k):sockets.append(str(a));raise AssertionError('socket prohibited')
socket.socket=Guard
socket.create_connection=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network prohibited'))
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];OUT=ROOT/'.g5/uplift/consolidated/iteration-14'
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN=bc.import_pin()
from iris_vector_graph._engine.nodes_edges import NodesEdgesMixin
from iris_vector_graph._engine.snapshot import SnapshotMixin
import provider,port,oracle
class Engine(NodesEdgesMixin,SnapshotMixin):
 _ivg_schema='Graph_KG'
 def __init__(self,w):self.conn=w
 def _t(self,name):return 'Graph_KG.'+name
class Sink(SnapshotMixin):
 def __init__(self):self.calls=[]
 def create_node(self,id,labels=None,properties=None,graph=None):self.calls.append(dict(kind='node',id=id,labels=copy.deepcopy(labels),properties=copy.deepcopy(properties),graph=graph));return False
 def create_edge(self,s,p,o,**kwargs):self.calls.append(dict(kind='edge',source=s,predicate=p,target=o,kwargs=copy.deepcopy(kwargs)));return False

def typed(v):
 if isinstance(v,dict):return {k:typed(v[k]) for k in sorted(v)}
 if isinstance(v,(list,tuple)):return [typed(x) for x in v]
 return [type(v).__name__,v]

def fixture(v=29,alias_order=0,q='{"q":0}',reverse=False):
 ps=[('','a','name','Ann'),('','a','score',v),('','a','labels','user-label'),('','b','name','Bob'),('named','a','name','Named'),('named','a','score',99)]
 pair=[('','a','id','application-id'),('','a','p_id','stored-p')]
 if alias_order==0:ps+=pair[:1]
 elif alias_order==1:ps+=pair
 else:ps+=list(reversed(pair))
 es=[('',11,'a','R','b',None),('',10,'a','R','b',None),('',12,'a','Q','c',q),('named',13,'a','R','a',None),('',14,'a','Marked','b','{"temporal":true}')]
 ns=[('','c'),('named','a'),('','b'),('','a')]
 if reverse:ns=list(reversed(ns));es=list(reversed(es))
 return dict(nodes=ns,labels=[('','a','Person'),('','a','Member'),('','b','City'),('named','a','Other')],props=ps,edges=es)

def observe(raw,directory,name,variants=None,extra_reads=False):
 w=provider.World(raw);e=Engine(w)
 for method,fn in (variants or {}).items():setattr(e,method,types.MethodType(fn,e))
 reads={}
 if extra_reads:
  requests=['c','a','a','missing','b'];reads=dict(requests=requests,default=e.get_nodes(requests),named=e.get_node('a',graph='named'),empty=e.get_nodes([]))
 path=directory/(name+'.ndjson');counts=e.export_graph_ndjson(str(path));text=path.read_text();records=[json.loads(line) for line in text.splitlines()]
 assert len(text.splitlines())==counts['nodes']+counts['edges'],('file/count relation',name,counts)
 imports={}
 for graph in [None,'restored','']:
  sink=Sink();answer=sink.import_graph_ndjson(str(path),graph=graph);imports[repr(graph)]=dict(calls=sink.calls,counts=answer)
 return dict(records=records,counts=counts,imports=imports,reads=reads,file=str(path.relative_to(ROOT)),file_sha256=bc.sha(path),trace=w.trace)

def wanted(raw):
 a=oracle.export(raw);a['imports']={repr(g):oracle.callbacks(a['records'],g) for g in [None,'restored','']};return a

def compare(got,want):return typed({k:got[k] for k in ['records','counts','imports']})==typed(want)

def variant(cls,method,name,find=None,replace=None,transform=None,directory=None):
 original=textwrap.dedent(inspect.getsource(getattr(cls,method)))
 if transform:changed=transform(original)
 else:
  assert original.count(find)==1,(name,original.count(find),find);changed=original.replace(find,replace)
 assert changed!=original
 path=directory/(name+'.py');path.write_text(changed)
 scope=dict(vars(sys.modules[cls.__module__]));exec(compile(changed,str(path),'exec'),scope)
 return scope[method],dict(method=method,name=name,original_sha256=hashlib.sha256(original.encode()).hexdigest(),mutant_sha256=bc.sha(path),path=str(path.relative_to(ROOT)))

def swap_export_loops(src):
 start=src.index('            cursor.execute(');middle=src.index('            # R088:');end=src.index('    finally:')
 return src[:start]+src[middle:end]+src[start:middle]+src[end:]

def main():
 start=time.monotonic()
 for rel,h in json.loads((HERE/'binding_inputs.json').read_text()).items():assert bc.sha(ROOT/rel)==h,('stale declared dependency',rel)
 directory=OUT/'ndjson-files'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');directory.mkdir(parents=True);mutants=directory/'mutants';mutants.mkdir();print('OUTPUT_DIRECTORY',directory,flush=True)
 cases=[];comparisons=0
 values=[0,29,5.0,-0.5,'29','plain','true','false']
 qs=[None,'','{}','{"q":0}','{"q":1}','{"q":12}']
 fixtures=[fixture(v,alias,q,rev) for v,alias,q,rev in itertools.product(values,[0,1,2],qs,[False,True])]
 fixtures += [dict(nodes=[],labels=[],props=[],edges=[]),dict(nodes=[('','bare')],labels=[],props=[],edges=[])]
 for i,raw in enumerate(fixtures):
  assert len({(g,n,k) for g,n,k,v in raw['props']})==len(raw['props'])
  model=port.export(raw);reference=oracle.export(raw);assert typed(model)==typed(reference)
  got=observe(raw,directory,'case'+str(i),extra_reads=True);expected=wanted(raw);assert compare(got,expected),(i,raw,got,expected)
  req=got['reads']['requests'];assert typed(got['reads']['default'])==typed(port.get_nodes(raw,req))==typed(oracle.full_records(raw,req));named=oracle.full_records(raw,['a'],'named');assert typed(got['reads']['named'])==typed(named[0] if named else None);assert got['reads']['empty']==[]
  for g in [None,'restored','']:assert typed(port.callbacks(model['records'],g))==typed(expected['imports'][repr(g)])
  comparisons+=6
  cases.append(dict(index=i,raw=raw,actual=got,oracle=reference))
 # Every altered source gets the SAME fixture, same configuration and same input-derived comparator affirmed first.
 raw=fixture(5.0,1,'{"q":0}',False);expected=wanted(raw);sens=[]
 changes=[
  (SnapshotMixin,'export_graph_ndjson','actual node census includes named parents',"WHERE graph_id = '' ORDER BY node_id","WHERE 1=1 ORDER BY node_id",None),
  (SnapshotMixin,'export_graph_ndjson','actual export hydrates wrong graph','node_data = self.get_node(node_id)','node_data = self.get_node(node_id, graph="named")',None),
  (NodesEdgesMixin,'get_nodes','actual reserved alias removed','store_key = f"p_{key}" if key in _STRUCTURAL_KEYS else key','store_key = key',None),
  (NodesEdgesMixin,'get_nodes','actual label fold overwritten','node_map[s]["labels"].append(label)','node_map[s]["labels"] = [label]',None),
  (NodesEdgesMixin,'get_nodes','actual scalar decoder omitted','node_map[s][store_key] = read_node_value(val)','node_map[s][store_key] = val',None),
  (SnapshotMixin,'export_graph_ndjson','actual projected aliases omitted','if k not in ("id", "labels")','if k not in ("id", "labels", "p_id", "p_labels")',None),
  (SnapshotMixin,'export_graph_ndjson','actual node line counter doubled','nodes_written += 1','nodes_written += 2',None),
  (SnapshotMixin,'export_graph_ndjson','actual edge rows deduplicated','for s, p, o, quals in cursor.fetchall():','for s, p, o, quals in dict.fromkeys(cursor.fetchall()):',None),
  (SnapshotMixin,'export_graph_ndjson','actual zero qualifier omitted','if quals:','if quals and quals.get("q"):',None),
  (SnapshotMixin,'export_graph_ndjson','actual marker predicate omitted','f"AND (qualifiers IS NULL OR NOT ({TEMPORAL_MARKED_ROW})) ORDER BY edge_id"','"ORDER BY edge_id"',None),
  (SnapshotMixin,'export_graph_ndjson','actual edge lines before node lines',None,None,swap_export_loops),
 ]
 for j,(cls,method,name,find,replace,transform) in enumerate(changes):
  baseline=observe(raw,directory,'baseline'+str(j));assert compare(baseline,expected),(name,'unaltered fixture does not agree',baseline,expected)
  fn,meta=variant(cls,method,'mutant'+str(j),find,replace,transform,mutants)
  altered=observe(raw,directory,'mutant'+str(j),variants={method:fn})
  assert not compare(altered,expected),(name,'mutant survived')
  sens.append(dict(name=name,classification='actual Python source-copy producer mutation',baseline_agrees=True,altered_rejected=True,baseline=baseline,altered=altered,oracle=expected,source=meta))
 baseline=observe(raw,directory,'observation-baseline');assert compare(baseline,expected)
 corrupted=copy.deepcopy(baseline);corrupted['records'][0]['properties']['name']='changed'
 assert not compare(corrupted,expected)
 sens.append(dict(name='actual produced observation corrupted',classification='observation sensitivity, not a source mutation',baseline_agrees=True,altered_rejected=True,baseline=baseline,altered=corrupted,oracle=expected))
 # Actual source-only broader value observations stay outside the admitted nr::Stored/Value scalar theorem.
 supplement=[]
 raw_extra=fixture();raw_extra['props'] += [('','b','list','[1,"a"]'),('','b','map','{"x":1}')]
 got=observe(raw_extra,directory,'container-observation');assert compare(got,wanted(raw_extra));supplement.append(dict(classification='broader JSON-container observation only, not mathematical scalar agreement',raw=raw_extra,actual=got))
 assert not sockets
 sources=['iris_vector_graph/_engine/nodes_edges.py','iris_vector_graph/_engine/snapshot.py','iris_vector_graph/_engine/ledger.py','iris_vector_graph/prop_values.py','iris_vector_graph/constants.py']
 identities={rel:bc.sha(ROOT/rel)==bc.sha(PIN/rel) for rel in sources};assert all(identities.values())
 paths=[p for p in HERE.iterdir() if p.is_file()]+[HERE.parents[1]/'tools/binding_common.py']+[(HERE/p).resolve() for p in json.loads((HERE/'model.json').read_text()).get('additional_inputs',[])]+[ROOT/p for p in json.loads((HERE/'binding_inputs.json').read_text())]
 inputs={str(p.relative_to(ROOT)):bc.sha(p) for p in paths}
 body=dict(verdict='AGREES',inputs=inputs,comparisons=comparisons,fixtures=len(fixtures),cases=cases,sensitivities=sens,source_only_supplement=supplement,mismatches=[],socket_attempts=len(sockets),native_calls=0,Git_calls=0,pin_export_equals_current=identities,elapsed_s=time.monotonic()-start,scope='Actual pinned single-pass small-request hydration, default exporter, executing local SQL/raw tables, real JSON files and actual generated-record import reader with recording callbacks. Independent raw-row oracle and source-shaped port. Scalar/qualifier/order/JSON/write providers and nonempty identifier assumptions explicit; callbacks are not persistence, no inverse/native/body/all-carrier/large-request/failure claim.')
 receipt=bc.write_receipt('ndjson_export',Path(__file__),body);(OUT/'ndjson-binding.json').write_text(json.dumps(body,indent=2)+'\n');print(json.dumps({k:body[k] for k in ['verdict','comparisons','fixtures','socket_attempts','native_calls','Git_calls','elapsed_s']}));print(receipt)
if __name__=='__main__':main()
