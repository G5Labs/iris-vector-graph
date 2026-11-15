"""Actual pinned Python Cost caller/final reader over executing native-source port.
Independent immutable model trace and finite-walk oracle; no native/network/Git.
"""
from __future__ import annotations
import copy,hashlib,importlib.util,inspect,itertools,json,random,socket,textwrap,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
NETWORK=patch.object(socket.socket,'connect',side_effect=AssertionError('Cost binding forbids network'))
CONNECT=NETWORK.start()
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
bc=load('cost_binding_common',HERE.parents[1]/'tools/binding_common.py');PIN=bc.import_pin()
from iris_vector_graph import engine as em
from iris_vector_graph.cypher.ast import Literal
p=load('cost_preparation_oracle',REPO/'.g5/uplift/consolidated/iteration-9/weighted-cost-next-probe.py')

def snap(q,dist,hop,done,best,besth):
    return tuple((frozenset(q[i]),tuple(sorted(dist[i].items())),tuple(sorted(hop[i].items())),frozenset(done[i])) for i in [0,1])+(best,besth)

class SourcePort:
    """Mutable direct transcription of actual Cost378..448, recording raw locals.
    The source assumes exact decrease-key; it has no stale/done pop test.
    """
    def __init__(self,raw,mutant=None):self.raw=raw;self.mutant=mutant;self.trace=[];self.fallback=[];self.calls=[]
    def call(self,conn,cls,method,s,t,cap,d,wire,g,H):
        assert (cls,method)==('Graph.KG.TraversalPaths','DijkstraCost');ps=set(json.loads(wire));self.calls.append((s,t,cap,d,wire,g,H))
        if not s or not t:return ''
        if s==t:return '0'
        fwd=1 if d=='in' else 0;back=1-fwd
        dist=[{s:0},{t:0}];hop=[{s:0},{t:0}];q=[{(0,s)},{(0,t)}];done=[set(),set()];best=None;besth=0
        while True:
            self.trace.append(snap(q,dist,hop,done,best,besth))
            if not q[0] or not q[1]:break
            tops=[min(x)[0] for x in q]
            if best is not None and sum(tops)+(2 if self.mutant=='early-frontsum' else 0)>=best:break
            side=0 if tops[0]<=tops[1] else 1;other=1-side;c,u=min(q[side]);q[side].remove((c,u));done[side].add(u)
            if c>=cap:continue
            for k in [0,1]:
                if k==1 and d!='both':continue
                tag=fwd if (side==0)==(k==0) else back
                if self.mutant=='backward-both-forward-first' and side==1 and d=='both':tag=fwd if k==0 else back
                for a,raw in sorted(self.raw.items()):
                    if a[0]!=tag or a[1]!=g or a[2]!=u or (ps and a[3] not in ps):continue
                    v=a[4]
                    if v in done[side]:continue
                    w=raw if raw is not None and raw>0 else 1;new=c+w
                    if new>cap:continue
                    if v not in dist[side] or new<dist[side][v]:
                        if v in dist[side] and self.mutant!='old-queue-kept':q[side].discard((dist[side][v],v))
                        dist[side][v]=new;q[side].add((new,v));hop[side][v]=hop[side][u]+1
                    if v in dist[other]:
                        meet=dist[side][v]+dist[other][v]
                        if best is None or meet<best:best=meet;besth=0 if self.mutant=='zero-best-hop' else hop[side][v]+hop[other][v]
        if best is None or best>cap:return ''
        if H>0 and besth>H and self.mutant!='no-fallback':
            self.fallback.append((s,t,'',cap,H,d,wire,g))
            answer=p.json_search(p.oriented(self.raw,g,d,ps),s,t,cap,H)
            return '' if answer is None else str(answer)
        return str(best)

def selected(a,g,d,ps,b):
    return a[1]==g and (d=='both' or a[0]==((0 if b else 1) if d=='in' else (1 if b else 0))) and (not ps or a[3] in ps)

def model_json(raw,s,t,cap,H,d,ps,g):
    q=frozenset({(0,s,0)});dist={(s,0):0};seen={}
    while q:
        c,u,h=min(q);q=q-{(c,u,h)}
        if u in seen and seen[u]<=h:continue
        seen={**seen,u:h}
        if u==t:return c
        if c>=cap or (H and h>=H):continue
        nh=h+1 if H else 0
        for a,w in sorted(raw.items()):
            if not selected(a,g,d,ps,False) or a[2]!=u:continue
            v=a[4];n=c+(w if w is not None and w>0 else 1);key=(v,nh)
            if n>cap or (v in seen and seen[v]<=nh) or (key in dist and dist[key]<=n):continue
            q=q|{(n,v,nh)};dist={**dist,key:n}
    return None

def model(raw,s,t,cap,H,d,ps,g):
    if s==t:return 0,[],[]
    # Side = immutable queue, dist, hop, done. Ghost walks do not decide source.
    state=((frozenset({(0,s)}),{s:0},{s:0},frozenset()),(frozenset({(0,t)}),{t:0},{t:0},frozenset()),None,0)
    trace=[]
    while True:
        f,r,best,besth=state;trace.append(snap([f[0],r[0]],[f[1],r[1]],[f[2],r[2]],[f[3],r[3]],best,besth))
        if not f[0] or not r[0] or (best is not None and min(f[0])[0]+min(r[0])[0]>=best):break
        side=int(min(r[0])[0]<min(f[0])[0]);z=state[side];c,u=min(z[0]);z=(z[0]-{(c,u)},z[1],z[2],z[3]|{u})
        state=(z,state[1],best,besth) if side==0 else (state[0],z,best,besth)
        if c>=cap:continue
        # Source order: forward first tag under this requested direction, then reverse under both.
        arcs=sorted(raw,key=lambda a:((a[0]!=(1 if d=='in' else 0)) if side==0 else (a[0]==(1 if d=='in' else 0)),a[3],a[4],a[1],a[2]))
        for a in arcs:
            z=state[side];other=state[1-side];best,besth=state[2:];v=a[4];w=raw[a];new=c+(w if w is not None and w>0 else 1)
            if not selected(a,g,d,ps,bool(side)) or a[2]!=u or v in z[3] or new>cap:continue
            if v not in z[1] or new<z[1][v]:
                q=z[0]-({(z[1][v],v)} if v in z[1] else set());z=(q|{(new,v)},{**z[1],v:new},{**z[2],v:z[2][u]+1},z[3])
            if v in other[1]:
                meet=z[1][v]+other[1][v]
                if best is None or meet<best:best,besth=meet,z[2][v]+other[2][v]
            state=(z,other,best,besth) if side==0 else (other,z,best,besth)
    best,besth=state[2:]
    if best is None or best>cap:return None,trace,[]
    if H>0 and besth>H:return model_json(raw,s,t,cap,H,d,ps,g),trace,[(s,t,'',float(cap),H,d,json.dumps(sorted(ps)),g)]
    return best,trace,[]

def case(raw,s,t,cap,H,d,ps,g,mutant=None,alter=False):
    port=SourcePort(raw,mutant);proc=SimpleNamespace(procedure_name='ivg.shortestPath.weighted',options={},arguments=[Literal(v) for v in [s,t,'weight',cap,H,d,ps]],yield_items=['totalCost'])
    fn=em.IRISGraphEngine._proc_ivg_shortestpath_weighted
    with patch.dict(fn.__globals__,{'_call_classmethod':port.call}):r=fn(SimpleNamespace(conn=object()),proc,graph=g)
    got=copy.deepcopy(r.rows)
    if alter and got:got[0][1]+=1
    expected,trace,fallback=model(raw,s,t,cap,H,d,set(ps),g);optimum=p.walks(p.oriented(raw,g,d,ps),s,t,cap,H)[0]
    want=[] if optimum is None else [['',float(optimum)]]
    return {'agrees':expected==optimum and got==want and port.trace==trace and port.fallback==fallback and all(type(row[1]) is float for row in got),'input':[s,t,cap,H,d,ps,g],'rows':got,'expected':want,'port_fallback':port.fallback,'model_fallback':fallback,'trace_steps':len(trace),'port_terminal_best':port.trace[-1][-2:] if port.trace else None,'model_terminal_best':trace[-1][-2:] if trace else None,'calls':port.calls}

def variant(find,replace):
    src=textwrap.dedent(inspect.getsource(em.IRISGraphEngine._proc_ivg_shortestpath_weighted));assert src.count(find)==1
    ns=dict(vars(em));exec(src.replace(find,replace),ns);return ns['_proc_ivg_shortestpath_weighted']

def main():
    started=time.monotonic();rng=random.Random(21010);graphs=[]
    A=p.raw([('g','s','R','a',4),('g','s','R','b',1),('g','b','R','a',1),('g','a','R','t',1)])
    tie=p.raw([('g','s','R','a',2),('g','a','R','b',2),('g','b','R','c',2),('g','c','R','t',2),('g','s','R','x',3),('g','x','R','y',2),('g','y','R','t',3)])
    early=p.raw([('g','s','R','a',1),('g','a','R','b',1),('g','b','R','t',1),('g','s','R','x',2),('g','x','R','t',2)])
    order_rows=[('g','s','R','a',2),('g','a','R','v',2),('g','v','R','u',2),('g','u','R','t',2),('g','u','R','w',3),('g','s','R','w',3)]
    order=p.raw(order_rows)
    graphs=[A,tie,early,order]
    for _ in range(45):graphs.append(p.raw([('g',u,typ,v,rng.choice([None,-2,0,1,2,4,7])) for u,v,typ in itertools.product('sabt','sabt',['R','S']) if rng.randrange(7)==0]))
    cases=[]
    for raw in graphs:
        for (s,t),cap,H,d,ps,g in itertools.product([('s','t'),('s','ghost'),('s','s')],[0,3,5,20],[0,2,3],['out','in','both'],[[],['R']],['g','other']):cases.append(case(raw,s,t,cap,H,d,ps,g))
    good=case(A,'s','t',20,2,'out',[],'g');sensitivity={'changed_observed_cost_rejected':good['agrees'] and not case(A,'s','t',20,2,'out',[],'g',alter=True)['agrees']}
    for m,raw,H in [('no-fallback',A,2),('zero-best-hop',A,2),('early-frontsum',early,0)]:sensitivity['source_port_'+m]=not case(raw,'s','t',20,H,'out',[],'g',m)['agrees']
    queue_found=False
    for raw in graphs:
        if not case(raw,'s','ghost',20,0,'out',[],'g','old-queue-kept')['agrees']:queue_found=True;break
    sensitivity['source_port_old_queue_trace_changed']=queue_found
    original_order=case(order,'s','t',20,3,'both',[],'g');changed_order=case(order,'s','t',20,3,'both',[],'g','backward-both-forward-first')
    sensitivity['backward_both_order_trace_rejected']=original_order['agrees'] and not changed_order['agrees'] and original_order['rows']==changed_order['rows']
    order_contrast={'rows':order_rows,'source_order':original_order,'altered_order':changed_order,'meaning':'Same cost8; source BestHop4 calls Json, wrong backward tag order BestHop3 skips fallback. Trace/branch comparison detects what cost oracle alone misses.'}
    fn=variant('max_hops = _int_argument(name, "maxHops", _arg_raw(args[4], parameters), 0) if len(args) > 4 else 10','max_hops = 0')
    with patch.object(em.IRISGraphEngine,'_proc_ivg_shortestpath_weighted',fn):sensitivity['actual_hop_producer_removed']=not case(A,'s','t',20,2,'out',[],'g')['agrees']
    fn=variant('rows.append(["", float(cost)])','rows.append(["", 0.0])')
    with patch.object(em.IRISGraphEngine,'_proc_ivg_shortestpath_weighted',fn):sensitivity['actual_cost_reader_zeroed']=not case(A,'s','t',20,2,'out',[],'g')['agrees']
    fn=variant('if cost is not None and str(cost) != "":','if cost is not None and str(cost) not in ("", "0"):')
    with patch.object(em.IRISGraphEngine,'_proc_ivg_shortestpath_weighted',fn):sensitivity['actual_zero_reader_drops_self']=not case(A,'ghost','ghost',0,2,'out',[],'g')['agrees']
    flat={};identities={}
    for rel in ['iris_vector_graph/engine.py','iris_vector_graph/cypher/ast.py','iris_vector_graph/cypher/translator.py','iris_src/src/Graph/KG/Traversal.cls','iris_src/src/Graph/KG/TraversalPaths.cls','iris_src/src/Graph/KG/Adjacency.cls','iris_src/src/Graph/KG/AdjIndex.cls','iris_src/src/Graph/KG/GraphMode.cls','iris_vector_graph/_engine/nodes_edges.py']:
        flat[rel]=bc.sha(PIN/rel);identities[rel]=bc.sha(REPO/rel)==flat[rel]
    for rel in ['.g5/Verus_verification/models/weighted_cost/binding.py','.g5/Verus_verification/models/weighted_cost/weighted_cost.rs','.g5/Verus_verification/models/weighted_cost/model.json','.g5/Verus_verification/models/weighted_paths/weighted_paths.rs','.g5/Verus_verification/tools/binding_common.py','.g5/uplift/consolidated/iteration-9/weighted-cost-next-probe.py','.g5/uplift/consolidated/iteration-9/weighted-native.py','.g5/uplift/consolidated/iteration-9/weighted-native.json','.g5/uplift/consolidated/iteration-9/weighted-mirror-native.py','.g5/uplift/consolidated/iteration-9/weighted-mirror-native.json','.g5/uplift/consolidated/iteration-10/root-cost-native.py','.g5/uplift/consolidated/iteration-10/root-cost-native.json','.g5/uplift/consolidated/iteration-10/root-cost-native.log']:flat[rel]=bc.sha(REPO/rel)
    mism=[x for x in cases if not x['agrees']];sockets=CONNECT.call_count+p.CONNECT.call_count
    verdict='AGREES' if not mism and all(sensitivity.values()) and all(identities.values()) and sockets==0 else 'DISAGREES'
    out=bc.write_receipt('weighted_cost',Path(__file__),{'inputs':flat,'verdict':verdict,'comparisons':len(cases),'mismatch_count':len(mism),'mismatches':mism[:8],'samples':[good,case(tie,'s','t',20,3,'out',[],'g'),case(early,'s','t',20,0,'out',[],'g')],'sensitivity':sensitivity,'both_scan_order_contrast':order_contrast,'socket_connect_calls':sockets,'current_equals_exported_pin':identities,'pin_dir':str(PIN),'elapsed':time.monotonic()-started,'scope':'Actual pinned Python Cost argument producer and float/zero/no-path reader over mutable source-shaped Cost/Json port. Separate immutable model trace and independent simple-walk oracle. No ObjectScript/native execution. Root native15 and inherited native9000/mirror4 are flat-hashed finite observations; no internal native branch claim.'})
    print(json.dumps({'verdict':verdict,'comparisons':len(cases),'mismatches':len(mism),'sensitivity':sensitivity,'elapsed':time.monotonic()-started,'receipt':str(out)}));assert verdict=='AGREES'
if __name__=='__main__':main()
