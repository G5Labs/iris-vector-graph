"""Pinned actual Changeset/GraphLedger/decoder/fold/diff/export over executing SQL.
LedgerApply is an explicit source-transcribed SQLite port, not native code. An
independent complete-map model derives records/endpoints from raw ordinary ops.
"""
from __future__ import annotations
import copy,hashlib,importlib.util,inspect,itertools,json,logging,random,socket,sys,textwrap,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
NETWORK=patch.object(socket.socket,'connect',side_effect=AssertionError('ledger binding forbids network'));CONNECT=NETWORK.start()
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
bc=load('ledger_content_binding_common',HERE.parents[1]/'tools/binding_common.py');PIN=bc.import_pin()
S=load('ledger_content_sql_provider',HERE/'sql_provider.py');M=load('ledger_content_functional',HERE/'functional_model.py')
from iris_vector_graph.ledger import replay as R,changeset as C,export as E
from iris_vector_graph.ledger.client import GraphLedger
from iris_vector_graph.ledger.errors import ReconstructionTooLargeError
logging.getLogger('iris_vector_graph.ledger').setLevel(logging.WARNING)
EXPORTS=HERE.parents[1]/'results/ledger_content'/('binding-exports-'+str(time.time_ns()));EXPORTS.mkdir(parents=True)

def build(raw):
 cs=C.Changeset(actor='binding',actor_type='system')
 def ref(o):
  r=o['ref']
  if 'stmt_id' in r:return dict(stmt_id=str(r['stmt_id']))
  if 'op_ref' in r:return dict(ref=C.OpRef(r['op_ref']))
  t=r['tuple'];return dict(ref=(t['s'],t['p'],t['o'],t.get('graph')))
 for o in raw:
  k=o['op'];n=o.get('id')
  if k in ('create_node','upsert_node'):getattr(cs,k)(n,labels=o.get('labels'),properties=o.get('props'))
  elif k=='delete_node':cs.delete_node(n,o.get('mode','strict'))
  elif k in ('add_label','remove_label'):getattr(cs,k)(n,o['label'])
  elif k=='set_prop':cs.set_property(n,o['key'],o['value'])
  elif k=='remove_prop':cs.remove_property(n,o['key'])
  elif k in ('create_rel','upsert_rel'):
   t=o['tuple'];getattr(cs,'create_relationship' if k=='create_rel' else 'upsert_relationship')(t['s'],t['p'],t['o'],qualifiers=o.get('quals'),graph=t.get('graph'))
  elif k=='delete_rel':cs.delete_relationship(**ref(o))
  elif k=='set_qual':cs.set_qualifier(**ref(o),key=o['key'],value=o['value'])
  elif k=='remove_qual':cs.remove_qualifier(**ref(o),key=o['key'])
  elif k=='replace_quals':cs.replace_qualifiers(**ref(o),qualifiers=o.get('quals'))
  else:raise AssertionError(k)
 return cs

def ledger(p):return GraphLedger(SimpleNamespace(conn=p.conn,_schema_prefix='Graph_KG',_iris_obj=lambda:p))
def norm(st):
 return dict(nodes={k:dict(labels=sorted(v.labels),props=dict(v.props)) for k,v in st.nodes.items()},rels={str(k):dict(s=v.s,p=v.p,o=v.o,graph=v.graph,quals=dict(v.quals)) for k,v in st.statements.items()})
def projected_stream(items):
 nodes={};rels={}
 for k,id,e in items:
  if k=='node':nodes[id]=dict(labels=sorted(e.labels),props=dict(e.props))
  else:rels[str(id)]=dict(s=e.s,p=e.p,o=e.o,graph=e.graph,quals=dict(e.quals))
 return dict(nodes=nodes,rels=rels)
def rows_norm(records):
 out=[]
 for r in records:
  v=r.to_wire() if hasattr(r,'to_wire') else r
  d={k:v[k] for k in ['seq','ordinal','op','entity_kind','entity_id','attr','prior','new','graph']}
  if d['op']=='create_rel' and d['new'] is not None:d['new']=json.loads(d['new'])
  if d['op'] in ('delete_node','delete_rel') and d['prior'] is not None:d['prior']=json.loads(d['prior'])
  out.append(d)
 return out

def exported(g,seq,token):
 path=EXPORTS/(token+'-'+str(seq)+'.ndjson');summary=g.export_reconstruction(str(seq),str(path));lines=[json.loads(x) for x in path.read_text().splitlines()]
 got=dict(nodes={x['id']:dict(labels=x['labels'],props=x['props']) for x in lines if x['type']=='node'},rels={x['stmt_id']:{k:x[k] for k in ['s','p','o','graph','quals']} for x in lines if x['type']=='rel'})
 assert summary.nodes==len(got['nodes']) and summary.rels==len(got['rels']) and summary.path==str(path)
 return got

def scenario(batches,token,mutant=None,corrupt=False):
 p=S.Provider(mutant=mutant);g=ledger(p);m=M.Model();checks=0;fails=[];seqs=[1]
 for raw in batches:
  try:expected_ops=M.normalized_ops(raw);expected_build=True
  except ValueError:expected_ops=None;expected_build=False
  try:cs=build(raw);got_build=True
  except (ValueError,TypeError,C.ChangesetOperationError):got_build=False
  if got_build!=expected_build:fails.append(['client admission',raw,got_build,expected_build]);continue
  if not got_build:checks+=1;continue
  if json.loads(cs.canonical_json())['ops']!=expected_ops:fails.append(['actual caller expansion',raw]);continue
  expected=m.commit(expected_ops)
  try:reply=g.commit(cs);success=True
  except Exception as e:success=False;error=type(e).__name__
  checks+=1
  if success!=expected['ok']:fails.append(['commit status',raw,success,expected]);continue
  if not success:
   if p.seq!=m.seq:fails.append(['failed revision prefix leaked',raw,p.seq,m.seq])
   if norm(g.reconstruct(str(m.seq)))!=M.normalized_state(m.state):fails.append(['failed content prefix leaked',raw])
   continue
  seq=reply.revision.seq;seqs.append(seq);rs=g.get_revision(str(seq)).records;checks+=1
  if rows_norm(rs)!=rows_norm(expected['records']):fails.append(['raw records',raw,rows_norm(rs),rows_norm(expected['records'])])
  want=M.normalized_state(m.state)
  observations=[norm(g.reconstruct(str(seq))),projected_stream(g.reconstruct(str(seq),stream=True)),exported(g,seq,token)]
  if corrupt and observations[0]['nodes']:
   key=next(iter(observations[0]['nodes']));observations[0]['nodes'][key]['props']['corrupted-observation']='changed'
  for got in observations:
   checks+=1
   if got!=want:fails.append(['complete content reader',raw,got,want])
 # Named reader selections must be independent of all later emitted content.
 for seq in seqs:
  checks+=1
  if norm(g.reconstruct(str(seq)))!=M.normalized_state(m.states[seq]):fails.append(['later leaked into named',seq])
 for a,b in itertools.product(seqs,repeat=2):
  f=g.diff(str(a),str(b));rev=g.diff(str(b),str(a));checks+=1
  if f.inverse().to_list()!=rev.to_list() or (a==b and f.to_list()):fails.append(['inverse/equal',a,b])
  lo,hi=sorted((a,b));span=[r for r in m.logs if lo<r['seq']<=hi]
  if not any(r['op'] in ['create_node','delete_node','create_rel','delete_rel'] for r in span):
   want=M.endpoint_diff(m.states[a],m.states[b]);checks+=1
   if f.to_list()!=want:fails.append(['full continuous endpoint diff',a,b,f.to_list(),want])
 return dict(agrees=not fails,checks=checks,failures=fails[:4],revisions=len(seqs),records=len(m.logs),source_sql_reads=len(p.reads),last=norm(g.reconstruct(str(m.seq))))

def node(id='a',**kw):return dict(op='create_node',id=id,**kw)
def relation(**kw):return dict(op='create_rel',tuple=dict(s='a',p='R',o='b',graph=None),**kw)
def field(op,key,value=None,id='a'):
 d=dict(op=op,id=id,key=key)
 if op=='set_prop':d['value']=value
 return d

def raw_readers():
 cases=[]
 def rr(op,kind='node',id='a',attr='',prior=None,new=None,seq=1,ordinal=1,graph=None):return R.MutationRecord(seq,ordinal,op,kind,id,attr,prior,new,graph)
 t=json.dumps(dict(s='a',p='R',o='b',graph='\0'));raw=[rr('create_node'),rr('add_label',attr='L',new=''),rr('set_prop',attr='k',new=None),rr('create_rel','rel','1',new=t),rr('set_qual','rel','1','q',new='null')]
 st=R.reconstruct(raw,None);expect,_=M.reader([r.to_wire() for r in raw]);cases.append(norm(st)==M.normalized_state(expect))
 raw2=raw+[rr('create_rel','rel','2',new=t),rr('delete_rel','rel','1',prior=t)]
 st=R.reconstruct(raw2,None);expect,by=M.reader([r.to_wire() for r in raw2]);cases.append(norm(st)==M.normalized_state(expect) and st.stmt_for_tuple(('a','R','b',None)) is None and len(st.as_comparable()['rels'])==1)
 row=lambda flag,v:(1,1,'set_prop','node','a','k','',1,v,flag,'','')
 values=[R.MutationRecord.from_row(row(flag,v)).new for flag,v in [(1,''),(0,''),(0,'null')]];cases.append(values==[None,'','null'])
 red=rr('redacted',id='',prior=None,new=None);audit=rr('set_prop','revision',attr='k',new='x');temp=rr('create_temporal_edge','temporal_edge','t',new=t)
 st=R.reconstruct(raw+[red,audit,temp],None);cases.append(norm(st)==norm(R.reconstruct(raw,None)) and R.compute_diff([red]).redacted==[(1,1)] and R.compute_diff([temp]).to_list()[0]['attr']=='qual:')
 reset=raw+[rr('create_node',new=json.dumps(dict(labels=['ignored'],props={'ignored':'x'})))];cases.append(R.reconstruct(reset,None).nodes['a'].labels==set() and R.reconstruct(reset,None).nodes['a'].props=={})
 # Reader no cascade, while the ordinary producer emits relationship deletions.
 named=[rr('create_node'),rr('create_rel','rel','7',new=json.dumps(dict(s='a',p='R',o='b',graph='named'))),rr('delete_node',prior='{}')]
 cases.append('a' not in R.reconstruct(named,None).nodes and '7' in R.reconstruct(named,None).statements)
 return cases

def bounds():
 p=S.Provider(bound=1);g=ledger(p);g.commit(build([node('a'),node('b')]));g.commit(build([dict(op='delete_node',id='b')]))
 refused=False
 try:g.reconstruct('3')
 except ReconstructionTooLargeError:refused=True
 stream=projected_stream(g.reconstruct('3',stream=True));exp=exported(g,3,'bound')
 p.bound=0;zero=norm(g.reconstruct('3'))
 return refused and stream==exp==zero==dict(nodes={'a':dict(labels=[],props={})},rels={})

def lifecycle():
 p=S.Provider();g=ledger(p)
 g.commit(build([node(labels=['L'],props={'k':'1'})]));g.commit(build([field('set_prop','k','2'),dict(op='add_label',id='a',label='M')]))
 g.commit(build([dict(op='delete_node',id='a')]));g.commit(build([node(props={'k':'3'})]))
 before=norm(g.reconstruct('2'));reverse=g.diff('5','2').to_list();snapshot=next(json.loads(e['after']) for e in reverse if e['attr']=='' and e['after'] is not None)
 return dict(agrees=before['nodes']['a']==dict(labels=['L'],props={'k':'1'}) and snapshot==dict(labels=['L','M'],props={'k':'2'}),before=before,reverse=reverse,policy='Known bug-led-101; q-con-002 unresolved; not executed as inverse script.')

def variant(fn,find,repl):
 src=textwrap.dedent(inspect.getsource(fn));assert src.count(find)==1,(fn,find,src.count(find));ns=dict(fn.__globals__);exec(src.replace(find,repl),ns);return ns[fn.__name__]

def main():
 start=time.monotonic();rng=random.Random(120041)
 base=[node(labels=['L'],props={'k':'1','empty':'','text':'null'}),node('b'),relation(quals={'weight':'1.25','q':'x'})]
 candidates=[field('set_prop','k','2'),field('set_prop','k','1'),field('remove_prop','k'),dict(op='add_label',id='a',label='M'),dict(op='remove_label',id='a',label='L'),dict(op='set_qual',ref={'stmt_id':'1'},key='q',value='y'),dict(op='replace_quals',ref={'stmt_id':'1'},quals={'z':'v'}),dict(op='remove_qual',ref={'stmt_id':'1'},key='q'),dict(op='delete_node',id='a',mode='detach'),dict(op='delete_rel',ref={'stmt_id':'1'}),node('c',props={'fresh':True})]
 histories=[ [base]+[[o] for o in ops] for ops in itertools.product(candidates[:6],repeat=2)]
 for _ in range(35):histories.append([base]+[[rng.choice(candidates)] for _ in range(4)])
 histories += [ [base,[dict(op='upsert_node',id='a',labels=['M'],props={'k':'2'})]], [base,[relation(quals={'q':'z'})]], [base,[dict(op='upsert_rel',tuple=dict(s='a',p='R',o='b',graph=None),quals={'q':'z'})]], [base,[field('set_prop','k','2'),dict(op='delete_node',id='a',mode='detach'),node('a')]], [[node('a'),dict(op='add_label',id='a',label='')]], [base,[dict(op='replace_quals',ref={'stmt_id':'1'},quals={'':'x','q':'y'})]] ]
 results=[scenario(x,str(i)) for i,x in enumerate(histories)]
 raw=raw_readers();bound=bounds();life=lifecycle();sensitivity={}
 fn=variant(R.GraphState.apply,'node.labels.add(r.attr)','node.labels.add("wrong")')
 with patch.object(R.GraphState,'apply',fn):sensitivity['actual-label-writer']=not scenario(histories[0],'mut-label')['agrees']
 fn=variant(R.GraphState.apply,'node.props[r.attr] = r.new if r.new is not None else ""','node.props[r.attr] = "wrong"')
 with patch.object(R.GraphState,'apply',fn):sensitivity['actual-property-writer']=not scenario(histories[0],'mut-prop')['agrees']
 fn=variant(R.GraphState.apply,'st.quals[r.attr] = r.new if r.new is not None else ""','st.quals[r.attr] = "wrong"')
 with patch.object(R.GraphState,'apply',fn):sensitivity['actual-qualifier-writer']=not scenario(histories[0],'mut-qual')['agrees']
 fn=variant(R.compute_diff,'if ak not in lc.attrs_before:','if True:')
 with patch.object(R,'compute_diff',fn):sensitivity['actual-first-prior-reader']=not scenario([base,[field('set_prop','k','2')],[field('set_prop','k','3')]],'mut-diff')['agrees']
 fn=variant(GraphLedger.reconstruct,'iter_records_sql(self._engine.conn, self._schema(), 1, seq)','iter_records_sql(self._engine.conn, self._schema(), 1, 999999)')
 with patch.object(GraphLedger,'reconstruct',fn):sensitivity['actual-named-cutoff']=not scenario(histories[0],'mut-cut')['agrees']
 fn=variant(E.export_ndjson,'"labels": sorted(ns.labels),','"labels": [],')
 with patch.object(E,'export_ndjson',fn):sensitivity['actual-export-label-reader']=not scenario(histories[0],'mut-export')['agrees']
 sensitivity['source-port-prior']=not scenario([base,[field('set_prop','k','2')]],'mut-source','discard-prior')['agrees']
 changed=scenario(histories[0],'observation');sensitivity['altered-observation']=changed['agrees'] and not scenario(histories[0],'observation-corrupt',corrupt=True)['agrees']
 mism=[x for x in results if not x['agrees']];flat={}
 for f in ['binding.py','functional_model.py','sql_provider.py','ledger_content.rs','alternate.rs','model.json']:flat[str((HERE/f).relative_to(REPO))]=bc.sha(HERE/f)
 for rel in ['.g5/Verus_verification/models/reconstruction/reconstruction.rs','.g5/Verus_verification/tools/binding_common.py','iris_vector_graph/ledger/client.py','iris_vector_graph/ledger/changeset.py','iris_vector_graph/ledger/replay.py','iris_vector_graph/ledger/export.py','iris_src/src/Graph/KG/Ledger.cls','iris_src/src/Graph/KG/LedgerApply.cls','iris_src/src/Graph/KG/LedgerGenesis.cls']:
  flat[rel]=bc.sha(REPO/rel)
 out=dict(inputs=flat,verdict='AGREES' if not mism and all(raw) and bound and life['agrees'] and all(sensitivity.values()) and CONNECT.call_count==0 else 'DISAGREES',histories=len(histories),comparisons=sum(x['checks'] for x in results),mismatch_count=len(mism),mismatches=mism[:3],raw_reader_neighbors=raw,bound_neighbor=bound,known_lifecycle=life,sensitivity=sensitivity,socket_connect_calls=CONNECT.call_count,elapsed_s=time.monotonic()-start,scope='Actual pinned Changeset and GraphLedger commit/named read/decoder/pager/full fold/diff/export over explicitly transcribed SQLite LedgerApply port; independent raw-op complete-map model. Closed ordinary default-only/no-marked-row/no-reifier/provider-success fragment. Native bodies, tuple/string/JSON/provider full coercion/SQL atomicity and general named producer closure not proved. Generic raw-reader cases are separate from ordinary native reach. All source mutations are in-process copies, not product edits.')
 receipt=bc.write_receipt('ledger_content',Path(__file__),out);print(json.dumps(dict(verdict=out['verdict'],histories=out['histories'],comparisons=out['comparisons'],mismatches=len(mism),raw=raw,bound=bound,sensitivity=sensitivity,elapsed_s=out['elapsed_s'],receipt=str(receipt))));assert out['verdict']=='AGREES'
if __name__=='__main__':main()
