"""Ordinary dyadic writers -> native JSON/Cost/public reader versus exact walk oracle."""
import hashlib,json,runpy,subprocess,time,traceback,uuid
from fractions import Fraction as F
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
FIXTURES={
 'default':[('s','R','t',None),('s','R','a','1/4'),('a','R','t','1/2')],
 'zero':[('s','R','t','0'),('s','R','a','1/4'),('a','R','t','1/2')],
 'negative':[('s','R','t','-2'),('s','R','a','1/4'),('a','R','t','1/2')],
 'direct':[('s','R','t','5/2'),('s','R','a','5/4'),('a','R','t','3/2')],
 'cap':[('s','R','a','1/2'),('a','S','t','3/4')],
 'hop':[('s','R','t','3/2'),('s','R','a','1/4'),('a','R','b','1/4'),('b','R','t','1/4')],
 'tie':[('s','R','a','1/2'),('a','R','b','1/2'),('b','R','c','1/2'),('c','R','t','1/2'),('s','R','x','3/4'),('x','R','y','1/2'),('y','R','t','3/4')],
 'bothorder':[('s','R','a','1/2'),('a','R','v','1/2'),('v','R','u','1/2'),('u','R','t','1/2'),('u','R','w','3/4'),('s','R','w','3/4')],
 'first':[('s','R','a','1/4'),('a','R','t','9/4'),('s','R','b','1'),('b','R','t','1')]}
CASES=[('default',0,'4','out',[],False),('zero',0,'4','out',[],False),('negative',0,'4','out',[],False),('direct',0,'4','out',[],False),
 ('cap',0,'5/4','out',[],False),('cap',0,'1','out',[],False),('cap',0,'5/4','out',['R'],False),
 ('hop',0,'4','out',[],False),('hop',2,'4','out',[],False),('hop',3,'4','out',[],False),('hop',2,'1','out',[],False),
 ('tie',0,'4','out',[],False),('tie',2,'4','out',[],False),('tie',3,'2','out',[],False),('tie',4,'2','out',[],False),('tie',3,'7/4','out',[],False),
 ('bothorder',3,'4','both',[],False),('bothorder',4,'4','both',[],False),('first',0,'7/4','out',[],False),('first',0,'2','out',[],False),
 ('default',0,'4','in',[],True),('cap',0,'5/4','both',[],True)]
def weight(w):return F(w) if w is not None and F(w)>0 else F(1)
def arcs(edges,direction,preds):
 a=[]
 for s,p,t,w in edges:
  if preds and p not in preds:continue
  if direction in ['out','both']:a.append((s,p,t,weight(w)))
  if direction in ['in','both']:a.append((t,p,s,weight(w)))
 return a
def oracle(edges,src,dst,H,cap,direction,preds):
 a=arcs(edges,direction,preds);vs={src,dst}|{s for s,p,t,w in a}|{t for s,p,t,w in a};lim=min(H,len(vs)-1) if H else len(vs)-1;todo=[(src,F(0),0,{src})];best=None
 while todo:
  v,c,k,seen=todo.pop()
  if v==dst:
   if c<=cap:best=c if best is None else min(best,c)
   continue
  if k==lim:continue
  for u,p,t,w in a:
   if u==v and t not in seen and c+w<=cap:todo.append((t,c+w,k+1,seen|{t}))
 return best
def main():
 start=time.monotonic();sources={};identities={}
 for rel in ['iris_src/src/Graph/KG/Traversal.cls','iris_src/src/Graph/KG/TraversalPaths.cls','iris_src/src/Graph/KG/Adjacency.cls','iris_src/src/Graph/KG/AdjIndex.cls','iris_vector_graph/engine.py','iris_vector_graph/_engine/nodes_edges.py']:
  p=h['PIN_DIR']/rel;sources[rel]=hashlib.sha256(p.read_bytes()).hexdigest();blob=subprocess.check_output(['git','rev-parse','3eaa79cf:'+rel],cwd=REPO,text=True).strip();identities[rel]=dict(pin_blob=blob,export_equals=subprocess.check_output(['git','hash-object',str(p)],text=True).strip()==blob,current_equals=subprocess.check_output(['git','hash-object',str(REPO/rel)],text=True).strip()==blob)
 assert all(x['export_equals'] and x['current_equals'] for x in identities.values())
 c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);e.ledger.disable();n=e._iris_obj();suffix=uuid.uuid4().hex[:8];graphs={};points=[];rows=[];failure=None
 def node(f,v):return 'frac11:'+f+':'+v
 try:
  for f,edges in FIXTURES.items():
   g='frac11:'+f+':'+suffix;graphs[f]=g
   for s,p,t,w in edges:
    assert e.create_edge(node(f,s),p,node(f,t),weight=None if w is None else float(F(w)),graph=g)
    key=n.classMethodValue('Graph.KG.GraphKey','ForIndex',g);fw=n.get('^KG','out',key,node(f,s),p,node(f,t));bw=n.get('^KG','in',key,node(f,t),p,node(f,s))
    def effective(v):return F(str(v)) if v is not None and str(v)!='' and F(str(v))>0 else F(1)
    good=effective(fw)==effective(bw)==weight(w);points.append(dict(fixture=f,source=s,predicate=p,target=t,raw_weight=w,out=fw,reverse=bw,effective=str(weight(w)),agrees=good));assert good,points[-1]
  for f,H,cap,direction,preds,reverse in CASES:
   src,dst=('t','s') if reverse else ('s','t');g=graphs[f];s=node(f,src);t=node(f,dst);want=oracle(FIXTURES[f],src,dst,H,F(cap),direction,preds);wantnum=None if want is None else float(want)
   raw=n.classMethodValue('Graph.KG.TraversalPaths','DijkstraCost',s,t,float(F(cap)),direction,json.dumps(preds),g,H);cost=None if raw is None or str(raw)=='' else float(raw)
   path=json.loads(str(n.classMethodValue('Graph.KG.Traversal','DijkstraJson',s,t,'weight',float(F(cap)),H,direction,json.dumps(preds),g)))
   predarg='['+','.join("'"+p+"'" for p in preds)+']';q=f"USE GRAPH '{g}' CALL ivg.shortestPath.weighted('{s}','{t}','weight',{float(F(cap))},{H},'{direction}',{predarg}) YIELD totalCost RETURN totalCost";pub=e.execute_cypher(q,{},raise_on_error=True).rows
   if want is None:witness=path=={}
   else:
    ns=path['nodes'];cs=path['costs'];ps=path['rels'];aa=arcs(FIXTURES[f],direction,preds);witness=ns[0]==s and ns[-1]==t and path['length']==len(ns)-1==len(cs)==len(ps) and (not H or path['length']<=H) and path['totalCost']==sum(cs)==wantnum and all(any((node(f,u),p,node(f,v),float(w))==(a,pred,b,wc) for u,p,v,w in aa) for a,pred,b,wc in zip(ns,ps,ns[1:],cs))
   good=cost==wantnum and witness and (pub==[] if want is None else pub==[[wantnum]])
   rows.append(dict(fixture=f,hops=H,cap=cap,direction=direction,predicates=preds,source=src,target=dst,expected_exact=str(want) if want is not None else None,cost_only=cost,path=path,public_query=q,public_rows=pub,agrees=good));assert good,rows[-1]
 except Exception as ex:failure=dict(type=type(ex).__name__,message=str(ex),trace=traceback.format_exc());raise
 finally:
  result=dict(verdict='AGREES' if failure is None and len(rows)==len(CASES) and all(x['agrees'] for x in rows+points) else 'DISAGREES_OR_INCOMPLETE',cases=rows,points=points,graphs=graphs,completed_cases=len(rows),scheduled_cases=len(CASES),failure=failure,source_inputs=sources,source_identities=identities,inputs={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'root-fraction-predictions.md',REPO/'.g5/Verus_verification/models/temporal_restore/binding.py',REPO/'.g5/uplift/consolidated/iteration-5/native-setup.json']},identity_checked=True,container=h['NAME'],elapsed=time.monotonic()-start,scope='Ordinary dyadic and omitted/nonpositive weights; actual native Json/Cost and public cost-only reader versus independent exact Fraction walk enumeration. Finite source correspondence reuses setup5/export identity, not arbitrary Double refinement/native-body proof, internal BestHop instrumentation or all-keyed policy.')
  Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
 print(json.dumps({k:result[k] for k in ['verdict','completed_cases','elapsed']}));assert result['verdict']=='AGREES'
if __name__=='__main__':main()
