"""Actual pinned RDF producer/SQLite/serialize/parse against an independent raw-row oracle."""
import contextlib,hashlib,importlib.util,inspect,itertools,json,logging,os,re,socket,sqlite3,sys,textwrap,time,warnings
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];PIN=Path(os.environ.get('IVG_PIN_DIR','/Users/ziniuw/runs/ivg-consolidated-20261114/pin'));sys.path.insert(0,str(PIN));sys.dont_write_bytecode=True
SOCKETS=[]
def denied(*a,**kw):SOCKETS.append('connect');raise AssertionError('RDF binding forbids sockets')
socket.socket.connect=denied;socket.create_connection=denied;warnings.filterwarnings('ignore',category=DeprecationWarning);logging.disable(logging.CRITICAL)
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph._engine import _rdf_utils as utils,rdf_export as public
from rdflib import Graph,ConjunctiveGraph,URIRef,BNode,Literal
from rdflib.namespace import RDF,XSD
from rdflib.compare import isomorphic
sp=importlib.util.spec_from_file_location('rdf_raw_port',HERE/'port.py');port=importlib.util.module_from_spec(sp);sp.loader.exec_module(port)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
SOURCES=['iris_vector_graph/_engine/_rdf_utils.py','iris_vector_graph/_engine/rdf_export.py','iris_vector_graph/engine.py']
IDENTITY={s:{'pin':sha(PIN/s),'current':sha(REPO/s)} for s in SOURCES};assert all(x['pin']==x['current'] for x in IDENTITY.values())
class Provider:
 def __init__(self,L,V,E):
  self.queries=[];self.db=sqlite3.connect(':memory:');self.db.execute("ATTACH DATABASE ':memory:' AS Graph_KG")
  self.db.execute('CREATE TABLE Graph_KG.rdf_labels(s TEXT,label TEXT,graph_id TEXT)');self.db.execute('CREATE TABLE Graph_KG.rdf_props(s TEXT,"key" TEXT,val TEXT,graph_id TEXT)');self.db.execute('CREATE TABLE Graph_KG.rdf_edges(s TEXT,p TEXT,o_id TEXT,qualifiers TEXT,graph_id TEXT)');self.db.execute('CREATE TABLE Graph_KG.rdf_namespaces(prefix TEXT,uri TEXT)')
  self.db.executemany('INSERT INTO Graph_KG.rdf_labels VALUES(?,?,?)',L);self.db.executemany('INSERT INTO Graph_KG.rdf_props VALUES(?,?,?,?)',V);self.db.executemany('INSERT INTO Graph_KG.rdf_edges VALUES(?,?,?,?,?)',E)
 def cursor(self):
  parent=self
  class C:
   def __init__(self):self.c=parent.db.cursor()
   def execute(self,sql,args=None):parent.queries.append((sql,list(args or [])));self.c.execute(sql,args or []);return self
   def fetchmany(self,n):return self.c.fetchmany(n)
   def fetchall(self):return self.c.fetchall()
   def close(self):self.c.close()
  return C()
def iri(raw,base):return URIRef(raw if raw.startswith(('http://','https://','urn:','ftp://')) else base+raw)
def pred(raw):return URIRef(raw if raw.startswith(('http://','https://','urn:')) else 'urn:ivg:prop/'+raw)
def independent_literal(s):
 if re.fullmatch(r'(0|[1-9][0-9]*|-[1-9][0-9]*)',s):return Literal(int(s),datatype=XSD.integer)
 # The declared decimal grammar is exact-dyadic; Decimal avoids the source float implementation in this oracle.
 if s=='007':return Literal(Decimal('7.0'),datatype=XSD.decimal)
 if re.fullmatch(r'-?(0|[1-9][0-9]*)\.(0|5|25|75)',s):return Literal(Decimal(s),datatype=XSD.decimal)
 if s.lower() in ('true','false'):return Literal(s.lower()=='true',datatype=XSD.boolean)
 return Literal(s)
def expected(L,V,E,g=None,ids=None,labels=None,base='urn:ivg:'):
 quads=set()
 def ctx(raw):return URIRef('urn:oracle:default') if not raw else URIRef(raw if raw.startswith(('urn:','http://','https://')) else 'urn:ivg:graph:'+raw)
 def add(graph,s,p,o):quads.add((ctx(graph),s,p,o))
 def within(raw):return g is None or (raw or '')==g
 def wanted(s,graph):return (not ids or s in ids) and (not labels or any(ls==s and (lg or '')==(graph or '') and ll in labels for ls,ll,lg in L))
 for s,l,graph in L:
  if within(graph) and (not ids or s in ids) and (not labels or l in labels):add(graph,iri(s,base),RDF.type,iri(l,base))
 for s,k,v,graph in V:
  if within(graph) and wanted(s,graph) and v is not None:add(graph,iri(s,base),pred(k),independent_literal(str(v)))
 for pos,(s,p,o,raw,graph) in enumerate(E):
  if within(graph) and wanted(s,graph):
   sub,pr,obj=iri(s,base),iri(p,base),iri(o,base);add(graph,sub,pr,obj)
   # Independent ordinary codec result; model port parsing is checked against it separately.
   quals=json.loads(raw) if raw else {}
   if isinstance(quals,dict) and quals:
    st=BNode('oracle-edge-'+str(pos)+'-statement');rf=BNode('oracle-edge-'+str(pos)+'-reifier')
    add(graph,st,RDF.subject,sub);add(graph,st,RDF.predicate,pr);add(graph,st,RDF.object,obj);add(graph,rf,URIRef(str(RDF)+'reifies'),st)
    for key,value in quals.items():
     if key!='inferred':
      text=str(value);x=independent_literal(text)
      if (x.datatype==XSD.boolean and str(x)=='false') or (x.datatype in (XSD.integer,XSD.decimal) and Decimal(str(x))==0) or str(x)=='':x=Literal(text)
      add(graph,rf,URIRef('urn:ivg:qualifier/'+key),x)
 return quads
def summary(q):
 ts={(s,p,o) for ctx,s,p,o in q};return {'triples':len(ts),'nodes':len({s for s,p,o in ts}),'edges':sum(isinstance(o,URIRef) and p!=RDF.type for s,p,o in ts)}
def augment(q):
 # ONE graph isomorphism for the full dataset. Shared original BNodes retain identity across all contexts.
 g=Graph()
 for i,(ctx,s,p,o) in enumerate(q):
  rec=BNode('quad-record-'+str(i))
  for key,value in [('context',ctx),('subject',s),('predicate',p),('object',o)]:g.add((rec,URIRef('urn:oracle:quad/'+key),value))
 return g
def file_quads(path,fmt):
 if fmt=='nquads':
  parsed=ConjunctiveGraph();parsed.parse(str(path),format=fmt)
  return {(URIRef('urn:oracle:default') if isinstance(ctx.identifier,BNode) else ctx.identifier,s,p,o) for s,p,o,ctx in parsed.quads((None,None,None,None))}
 parsed=Graph();parsed.parse(str(path),format='nt');return {(URIRef('urn:oracle:default'),s,p,o) for s,p,o in parsed}
N=0;WORLDS=[];LEX=[]
def check(a,b,label):
 global N;N+=1
 assert a==b,(label,a,b)
def check_port(V,E):
 for s,k,v,g in V:
  if v is not None:
   assert port.admitted(str(v)),('outside lexical frame',v)
   a=utils._to_literal(v);spec=port.literal(str(v));want=independent_literal(str(v));check(a,want,'actual lexical '+str(v));LEX.append(spec)
 for *_,raw,g in E:
  if raw:
   d=json.loads(raw);want=[(k,str(v)) for k,v in d.items()] if isinstance(d,dict) else []
   check(port.decode(raw),want,'raw JSON FSM '+raw)
   for k,v in want:assert port.admitted(v),('outside qualifier lexical frame',v)
def run(L,V,E,config,path,fmt='nquads',record=True):
 p=Provider(L,V,E);e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=p;e._schema_prefix='Graph_KG'
 try:
  actual=e.export_rdf(str(path),format=fmt,**config);want=expected(L,V,E,**{'g' if k=='graph_id' else 'labels' if k=='label_filter' else 'ids' if k=='node_ids' else 'base':v for k,v in config.items()})
  check({k:actual[k] for k in ('triples','nodes','edges')},summary(want),'raw→final summary')
  parsed=file_quads(path,fmt)
  if fmt=='nt':want={(URIRef('urn:oracle:default'),s,p,o) for ctx,s,p,o in want}
  check(isomorphic(augment(parsed),augment(want)),True,'GLOBAL dataset content')
  if record:WORLDS.append({'request':config,'format':fmt,'summary':summary(want),'quads':len(want),'queries':len(p.queries)})
  return actual,parsed
 finally:p.db.close()
def altered(fn,old,new):
 src=textwrap.dedent(inspect.getsource(fn));assert src.count(old)==1,(fn.__name__,old,src.count(old));ns={};exec(compile(src.replace(old,new),'<localized RDF source control>','exec'),fn.__globals__,ns);return ns[fn.__name__]
def main():
 start=time.monotonic();outdir=REPO/'.g5/uplift/consolidated/iteration-14/rdf-binding-files';outdir.mkdir(exist_ok=True)
 L=[('a','L',''),('a','Extra',''),('a','Z','g'),('b','L','g')]
 V=[('a','name','alpha',''),('a','flag','false',''),('a','zero','0',''),('a','name','alpha','g'),('b','n','2.5','g'),('a','omit',None,'')]
 E=[('a','R','b',None,''),('a','R','b',None,''),('a','R','b',None,'g'),('b','S','a',None,'')]
 fixtures=[([],[],[]),(L,V,E),(L,V,[('a','R','b','{"q":"x"}',''),('a','R','b','{"q":"x"}','')]),(L,V,[('a','I','b','{"inferred":true}','')]),(L,V,[('a','R','b','{"zero":0,"flag":false,"empty":""}','')]),(L,V,[('a','R','b','{"q":"x"}',''),('a','R','b','{"q":"x"}','g')]),([('a','L',None),('a','Z','g')],[('a','n','007',None),('a','frac','1.25','g')],[('a','R','b','{}',None)]),([('prop/x','L','')],[('prop/x','x','hello','')],[('prop/x','http://www.w3.org/1999/02/22-rdf-syntax-ns#type','ftp://x',None,'')])]
 for L0,V0,E0 in fixtures:
  check_port(V0,E0)
  for graph,ids,labels in itertools.product([None,'','g','absent'],[None,[],['a'],['b']],[None,[],['L'],['Z']]):
   config={'graph_id':graph,'node_ids':ids,'label_filter':labels}
   for fmt in ['nquads','nt']:run(L0,V0,E0,config,outdir/('current.'+('nq' if fmt=='nquads' else 'nt')),fmt)
 # Values exercise actual characters→datatype/value/spelling and qualifier fallback; no supplied type flags.
 for raw in ['-7','0','7','007','0.0','0.5','1.25','2.5','-2.75','true','false','True','False','','hello','None']:
  assert port.admitted(raw);check(utils._to_literal(raw),independent_literal(raw),'raw literal exact '+raw)
  check(bool(utils._to_literal(raw)),port.truth(port.literal(raw)),'literal truth '+raw)
 detections=sensitivities(L,V,E,outdir)
 check(all(detections.values()),True,'all actual source controls');check(SOCKETS,[],'zero sockets')
 body={'kind':'binding','model':'rdf_reporting','product_baseline':'3eaa79cf77d3e0a879b2cced634cf2729d81499e','verdict':'AGREES','worlds':len(WORLDS),'comparisons':N,'mismatch_count':0,'sensitivity':detections,'socket_connect_calls':len(SOCKETS),'native_executions':0,'elapsed':time.monotonic()-start,'source_identity':IDENTITY,'global_dataset_isomorphism':True,'scope':'Healthy ordinary ASCII lexical/JSON/source SQL/provider fragment; actual SQLite and public serialize/parse. Native/collation/codec/normalization/allocation internals qualified.'}
 flat={str(p.relative_to(REPO)):sha(p) for p in HERE.iterdir() if p.is_file()};flat.update({s:sha(REPO/s) for s in SOURCES})
 for name in ['rdf-attempt.py','rdf-PAIRS.md']:
  p=REPO/'.g5/uplift/consolidated/iteration-14'/name;flat[str(p.relative_to(REPO))]=sha(p)
 body['inputs']=flat;target=REPO/'.g5/Verus_verification/results/rdf_reporting'/time.strftime('%Y%m%dT%H%M%SZ-binding',time.gmtime());target.mkdir(parents=True);(target/'receipt.json').write_text(json.dumps(body,indent=2,sort_keys=True)+'\n');(target/'worlds.json').write_text(json.dumps(WORLDS,indent=2)+'\n');print(json.dumps({k:v for k,v in body.items() if k not in ('inputs','source_identity')},indent=2))
def sensitivities(L,V,E,d):
 cases=[('graph-all',utils,'_build_rdflib_graph','if graph_id is None:','if True:',{'graph_id':''},E),('own-graph-label',utils,'_build_rdflib_graph'," AND COALESCE(lf.graph_id, '') = COALESCE({alias}.graph_id, '')",'',{'label_filter':['L']},E),('target-filter',utils,'_build_rdflib_graph','edges_sql += _node_filter_clause("s")','edges_sql += _node_filter_clause("o_id")',{'node_ids':['a']},E),('label-triples-wide',utils,'_build_rdflib_graph','label_sql += " AND label IN ("','label_sql += " AND label NOT IN ("',{'label_filter':['L']},E),('inferred-envelope-dropped',utils,'_build_rdflib_graph','if quals and isinstance(quals, dict):','if quals and isinstance(quals, dict) and any(k != "inferred" for k in quals):',{},[('a','I','b','{"inferred":true}','')]),('qualifier-fallback-removed',utils,'_build_rdflib_graph','_to_literal(str(qv)) or Literal(str(qv))','_to_literal(str(qv))',{},[('a','R','b','{"zero":0,"flag":false}','')]),('summary-counts-quads',public.RdfExportMixin,'export_rdf','triple_count = len(g)','triple_count = sum(1 for _ in g.quads((None,None,None,None)))',{},E),('summary-counts-objects',public.RdfExportMixin,'export_rdf','subjects = set(g.subjects())','subjects = set(g.objects())',{},E),('type-counted-edge',public.RdfExportMixin,'export_rdf','isinstance(o, URIRef) and p != RDF.type','isinstance(o, URIRef)',{},E)]
 detected={}
 for name,mod,member,old,new,conf,edges in cases:
  fn=getattr(mod,member);mut=altered(fn,old,new)
  p=Provider(L,V,edges);e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=p;e._schema_prefix='Graph_KG';path=d/(name+'.nq')
  # public module imports build by name, so change both references for this same actual source function.
  with contextlib.ExitStack() as stack:
   stack.enter_context(patch.object(mod,member,mut))
   if member=='_build_rdflib_graph':stack.enter_context(patch.object(public,member,mut))
   try:
    actual=e.export_rdf(str(path),format='nquads',**conf);want=expected(L,V,edges,**{'g' if k=='graph_id' else 'labels' if k=='label_filter' else 'ids':v for k,v in conf.items()});parsed=file_quads(path,'nquads')
    detected[name]=({k:actual[k] for k in ('triples','nodes','edges')}!=summary(want) or not isomorphic(augment(parsed),augment(want)))
   except Exception as exc:raise AssertionError(('control must reach final content/report, not exception',name,exc)) from exc
  p.db.close()
 # Global allocation reuse control uses the actual producer with one shared BNode per role, across contexts.
 real=BNode;made=[]
 def reused(*a,**kw):
  # BNode() invoked only directly by producer; ConjunctiveGraph internal allocator uses its module's original class.
  b=real('reused-'+str(len(made)%2));made.append(b);return b
 p=Provider(L,V,[('a','R','b','{"q":"x"}',''),('a','R','b','{"q":"x"}','g')]);e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=p;e._schema_prefix='Graph_KG';path=d/'global-blank-reuse.nq'
 import rdflib
 with patch.object(rdflib,'BNode',side_effect=reused):actual=e.export_rdf(str(path),format='nquads')
 want=expected(L,V,[('a','R','b','{"q":"x"}',''),('a','R','b','{"q":"x"}','g')]);detected['global-allocation-reuse']=not isomorphic(augment(file_quads(path,'nquads')),augment(want));p.db.close()
 return detected
if __name__=='__main__':main()
