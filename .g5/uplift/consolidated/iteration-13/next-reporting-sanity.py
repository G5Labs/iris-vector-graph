"""Small healthy ordinary RDF source feasibility panel, not a model or native test."""
import hashlib,json,socket,sqlite3,sys,time,warnings
from pathlib import Path
R=Path(__file__).resolve().parents[4];P=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');D=Path(__file__).parent
sys.path.insert(0,str(P));calls=[]
def deny(*a,**k):calls.append('socket');raise AssertionError('network disabled')
socket.socket.connect=deny;socket.create_connection=deny
warnings.filterwarnings('ignore',category=DeprecationWarning)
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph._engine._rdf_utils import _to_literal
from rdflib import ConjunctiveGraph,URIRef,BNode
from rdflib.namespace import RDF,XSD
S=['iris_vector_graph/_engine/_rdf_utils.py','iris_vector_graph/_engine/rdf_export.py','iris_vector_graph/_engine/snapshot.py','iris_vector_graph/_engine/nodes_edges.py']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
identity={s:{'pin':sha(P/s),'current':sha(R/s)} for s in S};assert all(x['pin']==x['current'] for x in identity.values())
class Provider:
 def __init__(self,L,V,E):
  self.db=sqlite3.connect(':memory:');self.db.execute("ATTACH DATABASE ':memory:' AS Graph_KG")
  self.db.execute('CREATE TABLE Graph_KG.rdf_labels(s TEXT,label TEXT,graph_id TEXT)')
  self.db.execute('CREATE TABLE Graph_KG.rdf_props(s TEXT,"key" TEXT,val TEXT,graph_id TEXT)')
  self.db.execute('CREATE TABLE Graph_KG.rdf_edges(s TEXT,p TEXT,o_id TEXT,qualifiers TEXT,graph_id TEXT)')
  self.db.execute('CREATE TABLE Graph_KG.rdf_namespaces(prefix TEXT,uri TEXT)')
  self.db.executemany('INSERT INTO Graph_KG.rdf_labels VALUES(?,?,?)',L);self.db.executemany('INSERT INTO Graph_KG.rdf_props VALUES(?,?,?,?)',V);self.db.executemany('INSERT INTO Graph_KG.rdf_edges VALUES(?,?,?,?,?)',E)
 def cursor(self):return self.db.cursor()
def selected(g,req):return req is None or (g or '')==req
def oracle(L,V,E,g=None,ids=None,labels=None):
 # Raw-row set projection with fresh per-physical-row reification IDs; no product selector or result counts.
 Q=set()
 def iri(x):return ('IRI',x if x.startswith(('http://','https://','urn:','ftp://')) else 'urn:ivg:'+x)
 def add(ctx,s,p,o):Q.add((ctx or '',s,p,o))
 def subj_ok(s,ctx):return (not ids or s in ids) and (not labels or any(ls==s and (lg or '')==(ctx or '') and ll in labels for ls,ll,lg in L))
 for s,l,ctx in L:
  if selected(ctx,g) and (not ids or s in ids) and (not labels or l in labels):add(ctx,iri(s),('IRI',str(RDF.type)),iri(l))
 for s,k,v,ctx in V:
  if selected(ctx,g) and subj_ok(s,ctx) and v is not None:
   # This panel's property values are healthy ordinary plain text only.
   assert v=='alpha'
   add(ctx,iri(s),('IRI','urn:ivg:prop/'+k),('Lit',v))
 for i,(s,p,o,q,ctx) in enumerate(E):
  if selected(ctx,g) and subj_ok(s,ctx):
   add(ctx,iri(s),iri(p),iri(o));qs=json.loads(q) if q else {}
   if qs:
    st=('Blank',str(i)+'stmt');rf=('Blank',str(i)+'reifier')
    for pred,obj in [(str(RDF.subject),iri(s)),(str(RDF.predicate),iri(p)),(str(RDF.object),iri(o))]:add(ctx,st,('IRI',pred),obj)
    add(ctx,rf,('IRI',str(RDF)+'reifies'),st)
    for key,val in qs.items():
     if key!='inferred':add(ctx,rf,('IRI','urn:ivg:qualifier/'+key),('Lit',str(val)))
 T={(s,p,o) for ctx,s,p,o in Q}
 return {'triples':len(T),'nodes':len({s for s,p,o in T}),'edges':sum(o[0]=='IRI' and p!=('IRI',str(RDF.type)) for s,p,o in T),'quads':len(Q)}
def main():
 start=time.monotonic();files=D/'next-reporting-files';files.mkdir(exist_ok=True)
 L=[('a','L',''),('a','Extra',''),('a','Z','g'),('b','L','g')]
 V=[('a','name','alpha',''),('a','name','alpha','g'),('b','name','alpha','g')]
 E=[('a','R','b',None,''),('a','R','b',None,''),('a','R','b',None,'g'),('b','S','a',None,'')]
 cases=[]
 for name,g,ids,labels,edges in [('all',None,None,None,E),('default','',None,None,E),('named','g',None,None,E),('source-filter',None,['a'],None,E),('empty-filter',None,[],[],E),('label-own-graph',None,None,['L'],E),('qualifier-envelope','',None,None,[('a','R','b','{"source":"x"}',''),('a','I','b','{"inferred":true}','')])]:
  p=Provider(L,V,edges);e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=p;e._schema_prefix='Graph_KG';path=files/(name+'.nq')
  answer=e.export_rdf(str(path),graph_id=g,node_ids=ids,label_filter=labels)
  parsed=ConjunctiveGraph();parsed.parse(str(path),format='nquads');want=oracle(L,V,edges,g,ids,labels)
  actual={k:answer[k] for k in ('triples','nodes','edges')};assert actual=={k:want[k] for k in actual},(name,actual,want)
  count_quads=sum(1 for _ in parsed.quads((None,None,None,None)));assert count_quads==want['quads']
  cases.append({'name':name,'actual_return':actual,'derived_raw_oracle':want,'parsed_quad_count':count_quads,'returned_equals_serialized_quad_count':answer['triples']==count_quads});p.db.close()
 literals=[]
 for raw in ['7','007','1.25','true','false','hello','']:
  x=_to_literal(raw);literals.append({'raw':raw,'lexical':str(x),'datatype':str(x.datatype) if x.datatype else None,'python_truth':bool(x)})
 # Contrast the final qualifier reader against property literal conversion on ordinary false/zero values.
 p=Provider([],[],[('a','R','b','{"zero":"0","flag":"false"}','')]);e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=p;e._schema_prefix='Graph_KG';path=files/'qualifier-false-zero.nq';e.export_rdf(str(path));parsed=ConjunctiveGraph();parsed.parse(str(path),format='nquads')
 quals=[{'predicate':str(pred),'lexical':str(o),'datatype':str(o.datatype) if o.datatype else None} for s,pred,o in parsed if str(pred).startswith('urn:ivg:qualifier/')];p.db.close()
 assert calls==[]
 out={'scope':'source-informed bounded feasibility; no native/formal/new issue credit','cases':cases,'literal_observations':literals,'false_zero_qualifier_observations':quals,'source_inputs':identity,'socket_attempts':len(calls),'seconds':time.monotonic()-start}
 (D/'next-reporting-sanity.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
