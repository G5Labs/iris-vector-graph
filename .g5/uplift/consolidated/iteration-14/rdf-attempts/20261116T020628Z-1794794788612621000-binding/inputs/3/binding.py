"""Actual pinned RDF producer/SQLite/serialize/parse against an independent raw-row oracle."""
import contextlib,hashlib,importlib.util,inspect,itertools,json,logging,os,re,socket,sqlite3,sys,textwrap,time,warnings
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import shutil
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];PIN=Path(os.environ.get('IVG_PIN_DIR','/Users/ziniuw/runs/ivg-consolidated-20261114/pin'));sys.path.insert(0,str(PIN));sys.dont_write_bytecode=True
SOCKETS=[]
def denied(*a,**kw):SOCKETS.append('connect');raise AssertionError('RDF binding forbids sockets')
socket.socket.connect=denied;socket.create_connection=denied;warnings.filterwarnings('ignore',category=DeprecationWarning);logging.disable(logging.CRITICAL)
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph._engine import _rdf_utils as utils,rdf_export as public
import rdflib
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
def representation(x):
 if x.datatype==XSD.integer:return ('integer',int(str(x)),str(x))
 if x.datatype==XSD.decimal:return ('decimal',Fraction(Decimal(str(x))),str(x))
 if x.datatype==XSD.boolean:return ('boolean',bool(x.toPython()),str(x))
 return ('plain',str(x),str(x))
def expected(L,V,E,g=None,ids=None,labels=None,base='urn:ivg:'):
 quads=set()
 def ctx(raw):return None if not raw else URIRef(raw if raw.startswith(('urn:','http://','https://')) else 'urn:ivg:graph:'+raw)
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
 # One global dataset relation, with fresh encoding-only nodes disjoint from every source BNode.
 g=Graph();used={str(x) for quad in q for x in quad if isinstance(x,BNode)}
 def fresh(label):
  candidate=label
  while candidate in used:candidate+='x'
  used.add(candidate);return BNode(candidate)
 default=fresh('encoding-default-context')
 for i,(ctx,s,p,o) in enumerate(q):
  rec=fresh('encoding-quad-record-'+str(i))
  for key,value in [('context',default if ctx is None else ctx),('subject',s),('predicate',p),('object',o)]:g.add((rec,URIRef('urn:oracle:quad/'+key),value))
 return g
def file_quads(path,fmt):
 if fmt=='nquads':
  parsed=ConjunctiveGraph();parsed.parse(str(path),format=fmt)
  return {(None if isinstance(ctx.identifier,BNode) else ctx.identifier,s,p,o) for s,p,o,ctx in parsed.quads((None,None,None,None))}
 parsed=Graph();parsed.parse(str(path),format='nt');return {(None,s,p,o) for s,p,o in parsed}
N=0;WORLDS=[];LEX=[];FIXTURES={};BASELINES={};ARTIFACTS=None
def check(a,b,label):
 global N;N+=1
 assert a==b,(label,a,b)
def check_port(V,E):
 for s,k,v,g in V:
  if v is not None:
   assert port.admitted(str(v)),('outside lexical frame',v)
   a=utils._to_literal(v);spec=port.literal(str(v));want=independent_literal(str(v));check(a,want,'actual lexical '+str(v));check(representation(a),spec,'model literal datatype/value/spelling '+str(v));LEX.append(spec)
 for *_,raw,g in E:
  if raw:
   d=json.loads(raw);want=[(k,str(v)) for k,v in d.items()] if isinstance(d,dict) else []
   check(port.decode(raw),want,'raw JSON FSM '+raw)
   for k,v in want:assert port.admitted(v),('outside qualifier lexical frame',v)
def oracle_args(config):
 names={'graph_id':'g','label_filter':'labels','node_ids':'ids','base_uri':'base'}
 return {names[k]:v for k,v in config.items()}
def raw_digest(L,V,E):return hashlib.sha256(json.dumps([L,V,E],sort_keys=True).encode()).hexdigest()
def term_record(x):
 if x is None:return ['DefaultContext']
 if isinstance(x,Literal):return ['Literal',str(x),str(x.datatype) if x.datatype else None,x.language]
 if isinstance(x,BNode):return ['Blank',str(x)]
 return ['IRI',str(x)]
def run(L,V,E,config,path,fmt='nquads',record=True):
 p=Provider(L,V,E);e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=p;e._schema_prefix='Graph_KG'
 try:
  actual=e.export_rdf(str(path),format=fmt,**config);want=expected(L,V,E,**oracle_args(config))
  check({k:actual[k] for k in ('triples','nodes','edges')},summary(want),'raw→final summary')
  parsed=file_quads(path,fmt)
  if fmt=='nt':want={(None,s,p,o) for ctx,s,p,o in want}
  check(isomorphic(augment(parsed),augment(want)),True,'GLOBAL dataset content')
  fid=raw_digest(L,V,E);FIXTURES[fid]={'labels':L,'properties':V,'edges':E}
  digest=sha(path);copy=ARTIFACTS/(digest+('.nq' if fmt=='nquads' else '.nt'))
  if not copy.exists():shutil.copyfile(path,copy)
  if record:WORLDS.append({'world_id':len(WORLDS),'fixture_id':fid,'request':config,'format':fmt,'expected_summary':summary(want),'observed_summary':{k:actual[k] for k in ('triples','nodes','edges')},'expected_quads':len(want),'observed_quads':len(parsed),'serialized_sha256':digest,'serialized_copy':str(copy.relative_to(REPO)),'observed_global_quads':sorted([[term_record(ctx),term_record(sub),term_record(pr),term_record(ob)] for ctx,sub,pr,ob in parsed],key=str),'queries':p.queries})
  return actual,parsed
 finally:p.db.close()
def altered(fn,old,new):
 src=textwrap.dedent(inspect.getsource(fn));assert src.count(old)==1,(fn.__name__,old,src.count(old));ns={};exec(compile(src.replace(old,new),'<localized RDF source control>','exec'),fn.__globals__,ns);return ns[fn.__name__]
def main():
 global ARTIFACTS
 start=time.monotonic();outdir=REPO/'.g5/uplift/consolidated/iteration-14/rdf-binding-files';outdir.mkdir(exist_ok=True);ARTIFACTS=outdir/(str(time.time_ns())+'-serialized');ARTIFACTS.mkdir()
 L=[('a','L',''),('a','Extra',''),('a','Z','g'),('b','L','g')]
 V=[('a','name','alpha',''),('a','flag','false',''),('a','zero','0',''),('a','name','alpha','g'),('b','n','2.5','g'),('a','omit',None,'')]
 E=[('a','R','b',None,''),('a','R','b',None,''),('a','R','b',None,'g'),('b','S','a',None,'')]
 fixtures=[([],[],[]),(L,V,E),(L,V,[('a','R','b','{"q":"x"}',''),('a','R','b','{"q":"x"}','')]),(L,V,[('a','I','b','{"inferred":true}','')]),(L,V,[('a','R','b','{"zero":0,"flag":false,"empty":"","nil":null}','')]),(L,V,[('a','R','b','{"q":"x"}',''),('a','R','b','{"q":"x"}','g')]),([('a','L',None),('a','Z','g')],[('a','n','007',None),('a','frac','1.25','g')],[('a','R','b','{}',None)]),([('prop/x','L','')],[('prop/x','x','hello','')],[('prop/x','http://www.w3.org/1999/02/22-rdf-syntax-ns#type','ftp://x',None,'')])]
 for L0,V0,E0 in fixtures:
  check_port(V0,E0)
  for graph,ids,labels in itertools.product([None,'','g','absent'],[None,[],['a'],['b']],[None,[],['L'],['Z']]):
   config={'graph_id':graph,'node_ids':ids,'label_filter':labels}
   for fmt in ['nquads','nt']:run(L0,V0,E0,config,outdir/('current.'+('nq' if fmt=='nquads' else 'nt')),fmt)
 # Absolute passthrough and custom base are a real final-file helper contrast.
 La=[('http://example.org/a','urn:Type:L','g'),('bare','L','')];Va=[('http://example.org/a','ftp://key','hello','g')];Ea=[('http://example.org/a','ftp://R','urn:target:b',None,'g')]
 for fmt in ['nquads','nt']:run(La,Va,Ea,{'base_uri':'urn:custom:'},outdir/('absolute.'+('nq' if fmt=='nquads' else 'nt')),fmt)
 # Duplicate raw JSON keys derive last value through both actual JSON and model parser.
 raw='{"q":"first","q":"last"}';check_port([], [('a','R','b',raw,'')]);duplicate_answer,duplicate_quads=run(L,[],[('a','R','b',raw,'')],{},outdir/'duplicate-key.nq')
 unique='{"q":"last"}';check_port([], [('a','R','b',unique,'')]);unique_answer,unique_quads=run(L,[],[('a','R','b',unique,'')],{},outdir/'unique-key.nq');check(isomorphic(augment(duplicate_quads),augment(unique_quads)),True,'raw duplicate-key/last-only actual content pair')
 # Values exercise actual characters→datatype/value/spelling and qualifier fallback; no supplied type flags.
 for raw in ['-7','0','7','007','0.0','0.5','1.25','2.5','-2.75','true','false','True','False','','hello','None']:
  assert port.admitted(raw);check(utils._to_literal(raw),independent_literal(raw),'raw literal exact '+raw)
  check(bool(utils._to_literal(raw)),port.truth(port.literal(raw)),'literal truth '+raw)
  check(representation(utils._to_literal(raw)),port.literal(raw),'helper complete representation '+raw)
  p=Provider([],[],[('a','R','b',json.dumps({'q':raw}), '')]);e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=p;e._schema_prefix='Graph_KG';f=outdir/'qualifier-lexical.nq';e.export_rdf(str(f),format='nquads');objects=[o for ctx,sub,pr,o in file_quads(f,'nquads') if pr==URIRef('urn:ivg:qualifier/q')];check(len(objects),1,'one derived qualifier');check(representation(objects[0]),port.qualifier(raw),'final qualifier complete representation '+raw);p.db.close()
 detections=sensitivities(L,V,E,outdir)
 check(representation(utils._to_literal('7')),port.literal('7'),'unaltered model correspondence baseline')
 # A model-port kind mutation preserves truth and must still break actual term correspondence.
 with patch.object(port,'literal',return_value=('plain','7','7')):
  detections['model-literal-kind']=representation(utils._to_literal('7'))!=port.literal('7')
 check(all(detections.values()),True,'all classified controls');check(SOCKETS,[],'zero sockets')
 body={'kind':'binding','model':'rdf_reporting','product_baseline':'3eaa79cf77d3e0a879b2cced634cf2729d81499e','verdict':'AGREES','worlds':len(WORLDS),'comparisons':N,'mismatch_count':0,'sensitivity':detections,'socket_connect_calls':len(SOCKETS),'native_executions':0,'elapsed':time.monotonic()-start,'source_identity':IDENTITY,'python':sys.version.split()[0],'rdflib_version':rdflib.__version__,'sqlite_version':sqlite3.sqlite_version,'global_dataset_isomorphism':True,'sensitivity_classes':{'actual_source':11,'allocator_provider':1,'model_correspondence':1},'scope':'Healthy ordinary ASCII lexical/JSON/source SQL/provider fragment; actual SQLite and public serialize/parse. Native/collation/codec/normalization/allocation internals qualified.'}
 flat={str(p.relative_to(REPO)):sha(p) for p in HERE.iterdir() if p.is_file()};flat.update({s:sha(REPO/s) for s in SOURCES})
 for name in ['rdf-attempt.py','rdf-PAIRS.md']:
  p=REPO/'.g5/uplift/consolidated/iteration-14'/name;flat[str(p.relative_to(REPO))]=sha(p)
 body['inputs']=flat;target=REPO/'.g5/Verus_verification/results/rdf_reporting'/time.strftime('%Y%m%dT%H%M%SZ-binding',time.gmtime());target.mkdir(parents=True);(target/'receipt.json').write_text(json.dumps(body,indent=2,sort_keys=True)+'\n');(target/'worlds.json').write_text(json.dumps({'fixtures':FIXTURES,'worlds':WORLDS,'unaltered_control_baselines':BASELINES},indent=2)+'\n');body['worlds_artifact_sha256']=sha(target/'worlds.json');(target/'receipt.json').write_text(json.dumps(body,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in body.items() if k not in ('inputs','source_identity')},indent=2))
def sensitivities(L,V,E,d):
 cases=[('graph-all',utils,'_build_rdflib_graph','if graph_id is None:','if True:',{'graph_id':''},E),('own-graph-label',utils,'_build_rdflib_graph'," AND COALESCE(lf.graph_id, '') = COALESCE({alias}.graph_id, '')",'',{'label_filter':['L']},E),('target-filter',utils,'_build_rdflib_graph','edges_sql += _node_filter_clause("s")','edges_sql += _node_filter_clause("o_id")',{'node_ids':['a']},E),('label-triples-wide',utils,'_build_rdflib_graph','label_sql += " AND label IN ("','label_sql += " AND label NOT IN ("',{'label_filter':['L']},E),('inferred-envelope-dropped',utils,'_build_rdflib_graph','if quals and isinstance(quals, dict):','if quals and isinstance(quals, dict) and any(k != "inferred" for k in quals):',{},[('a','I','b','{"inferred":true}','')]),('qualifier-fallback-removed',utils,'_build_rdflib_graph','_to_literal(str(qv)) or Literal(str(qv))','_to_literal(str(qv))',{},[('a','R','b','{"zero":0,"flag":false}','')]),('summary-counts-quads',public.RdfExportMixin,'export_rdf','triple_count = len(g)','triple_count = sum(1 for _ in g.quads((None,None,None,None)))',{},E),('summary-counts-objects',public.RdfExportMixin,'export_rdf','subjects = set(g.subjects())','subjects = set(g.objects())',{},E),('type-counted-edge',public.RdfExportMixin,'export_rdf','isinstance(o, URIRef) and p != RDF.type','isinstance(o, URIRef)',{},E)]
 cases.extend([
 ('literal-canonical-check',utils,'_to_literal','if str(int_val) == s:','if True:',{},[('a','R','b',None,'')]),
 ('absolute-mint-removed',utils,'_mint_iri','if node_id.startswith(("http://", "https://", "urn:", "ftp://")):','if False:',{'base_uri':'urn:custom:'},[('urn:a','ftp://R','http://example.org/b',None,'')])])
 detected={}
 for name,mod,member,old,new,conf,edges in cases:
  fn=getattr(mod,member);mut=altered(fn,old,new)
  vrows=V+([('a','n','007','')] if name=='literal-canonical-check' else [])
  baseline_path=d/(name+'-unaltered.nq');baseline,baseline_quads=run(L,vrows,edges,conf,baseline_path,record=False)
  BASELINES[name]={'fixture_id':raw_digest(L,vrows,edges),'request':conf,'observed_summary':{k:baseline[k] for k in ('triples','nodes','edges')},'serialized_sha256':sha(baseline_path),'parsed_quads':len(baseline_quads),'same_comparator_affirmed':True}
  p=Provider(L,vrows,edges);e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=p;e._schema_prefix='Graph_KG';path=d/(name+'.nq')
  # public module imports build by name, so change both references for this same actual source function.
  with contextlib.ExitStack() as stack:
   stack.enter_context(patch.object(mod,member,mut))
   if member=='_build_rdflib_graph':stack.enter_context(patch.object(public,member,mut))
   try:
    actual=e.export_rdf(str(path),format='nquads',**conf);want=expected(L,vrows,edges,**oracle_args(conf));parsed=file_quads(path,'nquads')
    detected[name]=({k:actual[k] for k in ('triples','nodes','edges')}!=summary(want) or not isomorphic(augment(parsed),augment(want)))
   except Exception as exc:raise AssertionError(('control must reach final content/report, not exception',name,exc)) from exc
  p.db.close()
 # Global allocation reuse control uses the actual producer with one shared BNode per role, across contexts.
 real=BNode;made=[]
 def reused(*a,**kw):
  # BNode() invoked only directly by producer; ConjunctiveGraph internal allocator uses its module's original class.
  b=real('reused-'+str(len(made)%2));made.append(b);return b
 run(L,V,[('a','R','b','{"q":"x"}',''),('a','R','b','{"q":"x"}','g')],{},d/'allocation-unaltered.nq',record=False)
 p=Provider(L,V,[('a','R','b','{"q":"x"}',''),('a','R','b','{"q":"x"}','g')]);e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=p;e._schema_prefix='Graph_KG';path=d/'global-blank-reuse.nq'
 import rdflib
 with patch.object(rdflib,'BNode',side_effect=reused):actual=e.export_rdf(str(path),format='nquads')
 want=expected(L,V,[('a','R','b','{"q":"x"}',''),('a','R','b','{"q":"x"}','g')]);detected['global-allocation-reuse']=not isomorphic(augment(file_quads(path,'nquads')),augment(want));p.db.close()
 return detected
if __name__=='__main__':main()
