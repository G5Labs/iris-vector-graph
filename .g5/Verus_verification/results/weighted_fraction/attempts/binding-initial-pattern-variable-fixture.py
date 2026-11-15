"""Actual pinned Python raw arguments/final readers over executing exact-rational ports.
Independent immutable integer model decoded through a derived common denominator;
full physical trace comparisons plus an independent simple-walk output oracle.
No ObjectScript, native DB, network or arbitrary Double refinement claim.
"""
from __future__ import annotations
import copy,hashlib,importlib.util,inspect,itertools,json,math,random,socket,subprocess,textwrap,time
from fractions import Fraction as F
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
NETWORK=patch.object(socket.socket,'connect',side_effect=AssertionError('fraction binding forbids sockets'))
CONNECT=NETWORK.start()
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
bc=load('fraction_binding_common',HERE.parents[1]/'tools/binding_common.py');PIN=bc.import_pin()
sp=load('fraction_source_ports',HERE/'source_ports.py');km=load('fraction_integer_model',HERE/'kernel_model.py')
from iris_vector_graph import engine as em
from iris_vector_graph.cypher.ast import Literal,Variable

def raw(rows):
    r={}
    for g,s,p,t,x in rows:
        x=None if x is None else F(x);r[0,g,s,p,t]=x;r[1,g,t,p,s]=x
    return r

def effective(x):return x if x is not None and x>0 else F(1)
def derive(r,cap,mutant=None):
    # Model denominator product includes every raw scalar denominator AND cap.
    D=math.prod([x.denominator if x is not None else 1 for a,x in sorted(r.items())]+[cap.denominator])
    enc={a:(x.numerator*(D//x.denominator) if x is not None and x>0 else D) for a,x in r.items()}
    if mutant=='default-unit-one':enc={a:(1 if x is None else enc[a]) for a,x in r.items()}
    if mutant=='nonpositive-unit-one':enc={a:(1 if x is not None and x<=0 else enc[a]) for a,x in r.items()}
    if mutant=='positive-unscaled':enc={a:(x.numerator if x is not None and x>0 else enc[a]) for a,x in r.items()}
    C=cap.numerator*(D//cap.denominator)
    if mutant=='cap-unscaled':C=cap.numerator
    return D,enc,C

def decode_json(z,D):
    def state(t):
        q,dist,seen,parent=t
        return (tuple((F(c,D),u,h) for c,u,h in q),tuple((k,F(v,D)) for k,v in dist),seen,
                tuple((k,(u,h,a,F(w,D))) for k,(u,h,a,w) in parent))
    return {**z,'answer':None if z['answer'] is None else F(z['answer'],D),
            'path':[(a,F(w,D)) for a,w in z['path']],'trace':[state(t) for t in z['trace']]}

def decode_cost(z,D):
    def state(t):
        q,dist,hops,done,best,bh=t
        return (tuple(tuple((F(c,D),u) for c,u in side) for side in q),
                tuple(tuple((k,F(v,D)) for k,v in side) for side in dist),hops,done,
                None if best is None else F(best,D),bh)
    ans={**z,'answer':None if z['answer'] is None else F(z['answer'],D),'trace':[state(t) for t in z['trace']]}
    if z.get('fallback_json') is not None:ans['fallback_json']=decode_json(z['fallback_json'],D)
    return ans

def oracle(r,s,t,cap,H,d,ps,g):
    if s==t:return F(0) # actual early self branch precedes cap
    aa=[a for a in r if km.selected(a,g,d,ps)];nodes={s,t}|{a[2] for a in aa}|{a[4] for a in aa}
    limit=min(H,len(nodes)-1) if H else len(nodes)-1;front=[(s,F(0),frozenset({s}))];answer=None
    while front:
        u,c,seen=front.pop()
        if u==t:
            if c<=cap:answer=c if answer is None else min(answer,c)
            continue
        if len(seen)-1==limit:continue
        for a in aa:
            n=c+effective(r[a]);v=a[4]
            if a[2]==u and v not in seen and n<=cap:front.append((v,n,seen|{v}))
    return answer

def run_pair(r,s,t,cap,H,d,ps,g,mutant=None):
    # Source-side reads raw signed Fraction values; it never sees D or encoded graph.
    sj=sp.json_search(r,effective,s,t,cap,H,d,ps,g,mutant)
    sc=sp.cost_search(r,effective,s,t,cap,H,d,ps,g,mutant)
    D,enc,C=derive(r,cap,mutant)
    ij=decode_json(km.json_search(enc,s,t,C,H,d,ps,g),D)
    ic=decode_cost(km.cost_search(enc,s,t,C,H,d,ps,g),D)
    # Negative cap is a separately proved source branch, never a Nat encoding claim.
    if cap<0:
        expected=F(0) if s==t else None
        assert sj['answer']==sc['answer']==expected
        assert (not sj['trace'] and not sc['trace']) if s==t else (len(sj['trace'])==len(sc['trace'])==2 and sj['stop']==sc['stop']=='empty')
    optimum=oracle(r,s,t,cap,H,d,ps,g)
    return dict(agrees=sj==ij and sc==ic and sj['answer']==sc['answer']==optimum,
                json=sj,cost=sc,scaled_json=ij,scaled_cost=ic,denominator=D,optimum=optimum)

def path_object(z,s):
    if z['answer'] is None:return None
    return dict(nodes=[s]+[a[4] for a,w in z['path']],rels=[a[3] for a,w in z['path']],
                costs=[float(w) for a,w in z['path']],length=len(z['path']),totalCost=float(z['answer']))

class SourcePort:
    def __init__(self,r,mutant=None):self.raw=r;self.mutant=mutant;self.calls=[];self.executions=[]
    def call(self,conn,cls,method,*args):
        self.calls.append((cls,method,args))
        if method=='DijkstraCost':
            s,t,cap,d,preds,g,H=args;assert cls=='Graph.KG.TraversalPaths'
        else:
            assert (cls,method)==('Graph.KG.Traversal','DijkstraJson');s,t,prop,cap,H,d,preds,g=args
            assert prop in ('','weight')
        cap=F(cap);ps=set(json.loads(preds));H=max(0,H)
        z=sp.cost_search(self.raw,effective,s,t,cap,H,d,ps,g,self.mutant) if method=='DijkstraCost' else sp.json_search(self.raw,effective,s,t,cap,H,d,ps,g,self.mutant)
        self.executions.append(z)
        if method=='DijkstraCost':return '' if z['answer'] is None else str(float(z['answer']))
        return json.dumps(path_object(z,s) or {})

def public_case(r,s,t,cap,H,d,ps,g,cost_only=True,fn=None,alter=False):
    port=SourcePort(r);fn=fn or em.IRISGraphEngine._proc_ivg_shortestpath_weighted
    proc=SimpleNamespace(procedure_name='ivg.shortestPath.weighted',options={},arguments=[Literal(x) for x in [s,t,'weight',float(cap),H,d,ps]],yield_items=['totalCost'] if cost_only else ['path','totalCost'])
    with patch.dict(fn.__globals__,{'_call_classmethod':port.call}):result=fn(SimpleNamespace(conn=object()),proc,graph=g)
    # actual _number_argument converts raw numeric carrier to float; interpret exact represented value.
    cap=F(float(cap));z=run_pair(r,s,t,cap,H,d,set(ps),g);source=z['cost'] if cost_only else z['json'];obj=path_object(z['json'],s)
    want=[] if z['optimum'] is None else [['' if cost_only else obj,float(z['optimum'])]]
    got=copy.deepcopy(result.rows)
    if alter and got:got[0][1]+=0.25
    agree=z['agrees'] and port.executions==[source] and got==want and all(type(row[1]) is float for row in got)
    if not cost_only:agree=agree and all(type(v) is float for row in got for v in row[0]['costs'])
    return dict(agrees=agree,args=[s,t,str(cap),H,d,ps,g,cost_only],rows=got,want=want,
                calls=port.calls,denominator=z['denominator'],json_steps=len(z['json']['trace']),cost_steps=len(z['cost']['trace']),
                fallback=z['cost']['fallback'],best_hops=z['cost']['best_hops'],trace_sha256=hashlib.sha256(repr((z['json'],z['cost'])).encode()).hexdigest())

def variant(find,repl):
    src=textwrap.dedent(inspect.getsource(em.IRISGraphEngine._proc_ivg_shortestpath_weighted));assert src.count(find)==1
    ns=dict(vars(em));exec(src.replace(find,repl),ns);return ns['_proc_ivg_shortestpath_weighted']

def typed_panel(r):
    fn=em.IRISGraphEngine._proc_ivg_shortestpath_weighted;out=[]
    base=['s','t','weight',1.25,2,'out',[]]
    for idx,value in [(3,True),(3,None),(3,'bad'),(4,True),(4,2.5),(4,-1),(4,'bad'),(5,'sideways'),(2,'price')]:
        a=base.copy();a[idx]=value;port=SourcePort(r)
        with patch.dict(fn.__globals__,{'_call_classmethod':port.call}):
            try:fn(SimpleNamespace(conn=object()),SimpleNamespace(procedure_name='ivg.shortestPath.weighted',options={},arguments=[Literal(x) for x in a],yield_items=['totalCost']),graph='g');out.append(dict(agrees=False,args=a))
            except ValueError as e:out.append(dict(agrees=not port.calls,args=a,error=str(e)))
    for missing in [0,1]:
        a=[Literal(x) for x in base];a[missing]=Variable('missing')
        port=SourcePort(r)
        with patch.dict(fn.__globals__,{'_call_classmethod':port.call}):
            try:fn(SimpleNamespace(conn=object()),SimpleNamespace(procedure_name='ivg.shortestPath.weighted',options={},arguments=a,yield_items=['totalCost']),graph='g');out.append(dict(agrees=False,missing=missing))
            except ValueError as e:out.append(dict(agrees=not port.calls,missing=missing,error=str(e)))
    # Accepted string and whole-float numeric carriers; these are observations outside raw-rational theorem input.
    for cv,hv in [('1.25','2'),(1.25,2.0)]:
        a=base.copy();a[3]=cv;a[4]=hv;port=SourcePort(r)
        with patch.dict(fn.__globals__,{'_call_classmethod':port.call}):result=fn(SimpleNamespace(conn=object()),SimpleNamespace(procedure_name='ivg.shortestPath.weighted',options={},arguments=[Literal(x) for x in a],yield_items=['totalCost']),graph='g')
        out.append(dict(agrees=port.calls[0][2][2]==1.25 and port.calls[0][2][-1]==2 and result.rows==[['',1.25]],args=a,calls=port.calls))
    return out

def audit_native(flat):
    base='.g5/uplift/consolidated/iteration-11/';j=json.loads((REPO/base/'root-fraction-native.json').read_text())
    assert j['verdict']=='AGREES' and j['completed_cases']==j['scheduled_cases']==22
    assert all(x['agrees'] for x in j['cases']+j['points'])
    for rel,h in {**j['source_inputs'],**j['inputs']}.items():assert bc.sha(REPO/rel)==h;flat[rel]=h
    assert all(x['export_equals'] and x['current_equals'] for x in j['source_identities'].values())
    for leaf in ['root-fraction-predictions.md','root-fraction-native.py','root-fraction-native.json','root-fraction-native.log']:flat[base+leaf]=bc.sha(REPO/base/leaf)
    return dict(cases=22,mirrored_points=len(j['points']),all_input_hashes_current=True,scope=j['scope'])

def main():
    start=time.monotonic();rng=random.Random(211115)
    A=raw([('g','s','R','a',2),('g','s','R','b',F(1,2)),('g','b','R','a',F(1,2)),('g','a','R','t',F(1,2))])
    default=raw([('g','s','R','t',None),('g','s','R','a',F(1,4)),('g','a','R','t',F(1,2))])
    zero=raw([('g','s','R','t',0),('g','s','R','a',F(1,4)),('g','a','R','t',F(1,2))])
    capgraph=raw([('g','s','R','a',F(1,2)),('g','a','S','t',F(3,4))])
    both=raw([('g','s','R','a',F(1,2)),('g','a','R','v',F(1,2)),('g','v','R','u',F(1,2)),('g','u','R','t',F(1,2)),('g','u','R','w',F(3,4)),('g','s','R','w',F(3,4))])
    graphs=[A,default,zero,capgraph,both,{},raw([('g','s','R','t',F(5,2)),('g','s','R','a',F(5,4)),('g','a','R','t',F(3,2))])]
    for _ in range(12):graphs.append(raw([('g',u,p,v,rng.choice([None,F(-3,2),0,F(1,4),F(1,2),F(5,4),F(5,2)])) for u,v,p in itertools.product('sabt','sabt',['R','S']) if rng.randrange(8)==0]))
    checks=[]
    for r,(s,t),cap,H,d,ps,g,co in itertools.product(graphs,[('s','t'),('s','ghost'),('ghost','ghost')],[F(-1,2),F(0),F(1),F(5,4),F(4)],[0,2,3],['out','in','both'],[[],['R']],['g','other'],[False,True]):
        checks.append(public_case(r,s,t,cap,H,d,ps,g,co))
    # Non-dyadic exact provider worlds, without converting cap through Python float.
    generic=[]
    for r,cap,H in [(raw([('g','s','R','a',F(1,3)),('g','a','R','t',F(1,2)),('g','s','R','t',F(7,8))]),F(5,6),0),
                    (raw([('g','s','R','t',None),('g','s','R','a',F(1,3)),('g','a','R','t',F(1,3))]),F(2,3),2),
                    (raw([('g','s','R','t',F(-1,3)),('g','s','R','a',F(1,5)),('g','a','R','t',F(1,7))]),F(12,35),2)]:
        z=run_pair(r,'s','t',cap,H,'out',set(),'g');generic.append(z)
    typed=typed_panel(capgraph)
    sensitivity={}
    for name,r,cap,H,d in [('default-unit-one',default,F(3),0,'out'),('nonpositive-unit-one',zero,F(3),0,'out'),('positive-unscaled',capgraph,F(5,4),0,'out'),('cap-unscaled',capgraph,F(5,4),0,'out'),('json-removes-old',A,F(10),0,'out'),('cost-keeps-old',A,F(10),0,'out'),('cost-wrong-both-order',both,F(10),3,'both')]:
        sensitivity[name]=run_pair(r,'s','t',cap,H,d,set(),'g')['agrees'] and not run_pair(r,'s','t',cap,H,d,set(),'g',name)['agrees']
    sensitivity['altered-observed-cost']=not public_case(A,'s','t',F(10),2,'out',[],'g',alter=True)['agrees']
    fn=variant('max_hops = _int_argument(name, "maxHops", _arg_raw(args[4], parameters), 0) if len(args) > 4 else 10','max_hops = 0')
    sensitivity['actual-Python-hop-producer']=not public_case(A,'s','t',F(10),2,'out',[],'g',fn=fn)['agrees']
    fn=variant('rows.append(["", float(cost)])','rows.append(["", 0.0])')
    sensitivity['actual-Python-cost-reader']=not public_case(A,'s','t',F(10),2,'out',[],'g',fn=fn)['agrees']
    fn=variant('rows.append([path_obj, float(path_obj.get("totalCost", 0))])','rows.append([path_obj, 0.0])')
    sensitivity['actual-Python-path-reader']=not public_case(A,'s','t',F(10),2,'out',[],'g',False,fn=fn)['agrees']
    flat={};identities={}
    for rel in ['iris_vector_graph/engine.py','iris_vector_graph/cypher/ast.py','iris_vector_graph/cypher/translator.py','iris_src/src/Graph/KG/Traversal.cls','iris_src/src/Graph/KG/TraversalPaths.cls','iris_src/src/Graph/KG/Adjacency.cls','iris_src/src/Graph/KG/AdjIndex.cls','iris_src/src/Graph/KG/GraphMode.cls','iris_vector_graph/_engine/nodes_edges.py']:
        h=bc.sha(PIN/rel);flat[rel]=h;identities[rel]=h==bc.sha(REPO/rel)
        blob=subprocess.check_output(['git','-C',str(REPO),'rev-parse',bc.PIN+':'+rel],text=True).strip();identities[rel]=identities[rel] and subprocess.check_output(['git','hash-object',str(PIN/rel)],text=True).strip()==blob
    for rel in ['.g5/Verus_verification/models/weighted_fraction/'+x for x in ['binding.py','source_ports.py','kernel_model.py','weighted_fraction.rs','model.json']]+['.g5/Verus_verification/models/weighted_cost/weighted_cost.rs','.g5/Verus_verification/models/weighted_paths/weighted_paths.rs','.g5/Verus_verification/tools/binding_common.py']:
        flat[rel]=bc.sha(REPO/rel)
    native=audit_native(flat);mism=[x for x in checks+typed if not x['agrees']]
    okay=not mism and all(x['agrees'] for x in generic) and all(sensitivity.values()) and all(identities.values()) and CONNECT.call_count==0
    body=dict(inputs=flat,verdict='AGREES' if okay else 'DISAGREES',comparisons=len(checks),generic_exact_provider_worlds=len(generic),negative_cap_source_branch_worlds=sum(F(x['args'][2])<0 for x in checks),typed_neighbors=typed,
              mismatch_count=len(mism),mismatches=mism[:6],samples=[public_case(A,'s','t',F(10),h,'out',[],'g') for h in [0,2,3]],
              generic_samples=generic,sensitivity=sensitivity,native_supplement=native,current_export_pin_identities=identities,
              socket_connect_calls=CONNECT.call_count,elapsed_s=time.monotonic()-start,
              counts=dict(actual_python_controls=3,source_port_controls=3,representation_controls=4,altered_observation_controls=1),
              all_trace_sha256=hashlib.sha256(repr([x['trace_sha256'] for x in checks]).encode()).hexdigest(),
              scope='Actual pinned Python argument producer and path/cost float readers over explicit exact Fraction source ports; independent immutable integer model on product-derived denominator, all physical loop states for nonnegative-cap coupling; negative-cap integer helper observations are separate signed source-branch checks (outside imported Nat coupling); raw stored parent weights, historical BestHop/fallback and independent walk output oracle. Generic non-dyadic provider cases are source-only. Root native22 finite dyadic observations audited read-only; native Double roundoff, arbitrary JSON/coercion/collation, key projection and mirror correctness remain provider boundaries.')
    out=bc.write_receipt('weighted_fraction',Path(__file__),body)
    print(json.dumps(dict(verdict=body['verdict'],comparisons=len(checks),generic=len(generic),typed=len(typed),mismatches=len(mism),sensitivity=sensitivity,sockets=CONNECT.call_count,elapsed_s=body['elapsed_s'],receipt=str(out))))
    assert okay
if __name__=='__main__':main()
