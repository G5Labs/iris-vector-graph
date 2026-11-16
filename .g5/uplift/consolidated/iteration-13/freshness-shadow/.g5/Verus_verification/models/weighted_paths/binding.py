"""Actual pinned Python argument/observation boundary over a source-shaped native port.
The port executes DijkstraJson's mutable raw queue and backtrack, not ObjectScript.
Independent functional model trace and finite-walk oracle receive no supplied answer.
"""
from __future__ import annotations
import copy,hashlib,importlib.util,inspect,itertools,json,random,socket,sys,textwrap,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
NETWORK=patch.object(socket.socket,'connect',side_effect=AssertionError('weighted binding forbids network'))
CONNECT=NETWORK.start()
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
spec=importlib.util.spec_from_file_location('weighted_binding_common',HERE.parents[1]/'tools/binding_common.py')
bc=importlib.util.module_from_spec(spec);spec.loader.exec_module(bc);PIN=bc.import_pin()
from iris_vector_graph import engine as em
from iris_vector_graph.cypher.ast import Literal

def eff(w):return w if w is not None and w>0 else 1

def raw_graph(rows):
    # Completed ordinary mirrored scalar leaves. Extra graph coordinates coexist.
    raw={}
    for g,u,p,v,w in rows:
        raw[(0,g,u,p,v)]=w;raw[(1,g,v,p,u)]=w
    return raw

def selected(a,g,d,ps):return a[1]==g and (d=='both' or a[0]==(0 if d=='out' else 1)) and (not ps or a[3] in ps)

def snapshot(q,dist,parent,seen):
    return (frozenset(q),tuple(sorted(dist.items())),tuple(sorted(parent.items())),tuple(sorted(seen.items())))

class SourcePort:
    """Line-oriented mutable transcription of TraversalPaths256..346,450..491.
    Instrumentation snapshots do not decide the search. No distance-stale guard.
    """
    def __init__(self,raw,mutant=None):self.raw=raw;self.mutant=mutant;self.calls=[];self.trace=[];self.stale=0
    def call(self,conn,cls,method,src,dst,prop,cap,H,d,wire,g):
        assert (cls,method)==('Graph.KG.Traversal','DijkstraJson');assert prop=='weight'
        self.calls.append((src,dst,prop,cap,H,d,wire,g));ps=set(json.loads(wire))
        if not src or not dst:return '{}'
        if src==dst:return json.dumps({'nodes':[src],'rels':[],'costs':[],'length':0,'totalCost':0.0})
        q={(0,src,0)};dist={(src,0):0};parent={};seen={}
        while q:
            self.trace.append(snapshot(q,dist,parent,seen))
            c,u,h=min(q);q.remove((c,u,h))
            if (u,h) in dist and dist[(u,h)]<c:self.stale+=1
            if u in seen and (self.mutant=='node-only' or seen[u]<=h):continue
            seen[u]=h
            if u==dst:
                nodes=[dst];rels=[];costs=[];v=dst;hh=h
                while v!=src:
                    if (v,hh) not in parent:break
                    v,hh,p,w=parent[(v,hh)];nodes.insert(0,v);rels.insert(0,p);costs.insert(0,float(w))
                return json.dumps({'nodes':nodes,'rels':rels,'costs':costs,'length':len(nodes)-1,'totalCost':float(c)})
            if c>=cap or (H>0 and h>=H):continue
            nh=h+1 if H>0 else 0
            for a in sorted(self.raw):
                if not selected(a,g,d,ps) or a[2]!=u:continue
                v=a[4]
                if v in seen and (self.mutant=='node-only' or seen[v]<=nh):continue
                w=eff(self.raw[a]);nc=c+w
                if nc>cap or (self.mutant=='exclusive-cap' and nc==cap):continue
                if (v,nh) not in dist or nc<dist[(v,nh)]:
                    dist[(v,nh)]=nc;q.add((nc,v,nh));parent[(v,nh)]=(u,h,a[3],w)
        self.trace.append(snapshot(q,dist,parent,seen));return '{}'

def functional(raw,src,dst,cap,H,d,ps,g):
    """Transcription of initial/step/expand/backtrack; immutable state updates."""
    if src==dst:return {'nodes':[src],'rels':[],'costs':[],'length':0,'totalCost':0.0},[],0
    state=({(0,src,0)},{(src,0):0},{},{})
    arcs=sorted(raw);trace=[];removed=set();pops=0
    while True:
        q,dist,parent,seen=state;trace.append(snapshot(q,dist,parent,seen))
        if not q:return {},trace,pops
        e=min(q);c,u,h=e
        assert e not in removed;removed.add(e);pops+=1
        state=(q-{e},dist,parent,seen)
        if u in seen and seen[u]<=h:continue
        state=(q-{e},dist,parent,{**seen,u:h})
        if u==dst:
            def back(k):
                if k[0]==src or k not in parent:return []
                prev,ph,p,w=parent[k];return back((prev,ph))+[(prev,p,k[0],w)]
            path=back((u,h));return {'nodes':[src]+[a[2] for a in path],'rels':[a[1] for a in path],
                'costs':[float(a[3]) for a in path],'length':len(path),'totalCost':float(c)},trace,pops
        if c>=cap or (H>0 and h>=H):continue
        for a in arcs:
            if not selected(a,g,d,ps) or a[2]!=u:continue
            q1,ds,pa,se=state;nh=h+1 if H>0 else 0;n=c+eff(raw[a]);k=(a[4],nh)
            if n>cap or (a[4] in se and se[a[4]]<=nh) or (k in ds and ds[k]<=n):continue
            state=(q1|{(n,a[4],nh)},{**ds,k:n},{**pa,k:(u,h,a[3],eff(raw[a]))},se)

def oracle(raw,s,t,cap,H,d,ps,g):
    # Independent exhaustive simple-walk optimum; positive weights remove cycles.
    if s==t:return 0
    answers=[]
    def visit(u,c,visited,h):
        if u==t:answers.append(c);return
        if H and h>=H:return
        for a,w in raw.items():
            if selected(a,g,d,ps) and a[2]==u and a[4] not in visited and c+eff(w)<=cap:
                visit(a[4],c+eff(w),visited|{a[4]},h+1)
    visit(s,0,{s},0);return min(answers) if answers else None

def valid(path,raw,s,t,cap,H,d,ps,g,want):
    if want is None:return path=={}
    if path.get('nodes',[])[:1]!=[s] or path['nodes'][-1]!=t:return False
    ns=path['nodes'];pss=path['rels'];ws=path['costs']
    return len(ns)==len(pss)+1==len(ws)+1 and path['length']==len(pss) and (not H or len(pss)<=H) and path['totalCost']==sum(ws)==want and all(type(w) is float for w in ws) and type(path['totalCost']) is float and all(any(selected(a,g,d,ps) and (a[2],a[3],a[4],eff(w))==(u,p,v,c) for a,w in raw.items()) for u,p,v,c in zip(ns,pss,ns[1:],ws))

def case(raw,s,t,cap,H,d,ps,g,mutant=None,alter=False):
    port=SourcePort(raw,mutant);args=[s,t,'weight',cap,H,d,ps]
    proc=SimpleNamespace(procedure_name='ivg.shortestPath.weighted',options={},arguments=[Literal(v) for v in args],yield_items=['path','totalCost'])
    self=SimpleNamespace(conn=object())
    target=em.IRISGraphEngine._proc_ivg_shortestpath_weighted
    with patch.dict(target.__globals__,{'_call_classmethod':port.call}):r=target(self,proc,graph=g)
    path=r.rows[0][0] if r.rows else {};path=copy.deepcopy(path)
    if alter and path:path['totalCost']+=1
    want,trace,pops=functional(raw,s,t,cap,H,d,set(ps),g);minimum=oracle(raw,s,t,cap,H,d,set(ps),g)
    good=path==want and port.trace==trace and valid(path,raw,s,t,cap,H,d,set(ps),g,minimum)
    # The actual final Python consumer must preserve float(totalCost) separately.
    good=good and (r.rows==[] if minimum is None else len(r.rows)==1 and r.rows[0][1]==minimum)
    universe=(cap+1)*(H+1)*len({s}|{a[4] for a in raw})
    return {'agrees':good,'input':[s,t,cap,H,d,ps,g],'path':path,'want':minimum,'pops':pops,'rank_bound':universe,'stale_pops':port.stale,'calls':port.calls}

def source_variant(find,replace):
    src=textwrap.dedent(inspect.getsource(em.IRISGraphEngine._proc_ivg_shortestpath_weighted));assert src.count(find)==1
    ns=dict(vars(em));exec(src.replace(find,replace),ns);return ns['_proc_ivg_shortestpath_weighted']

def main():
    started=time.monotonic();rng=random.Random(219);cases=[];graphs=[]
    fixture=[('g','s','R','a',4),('g','s','R','b',1),('g','b','R','a',1),('g','a','R','t',1)]
    graphs.append(raw_graph(fixture+[('other','s','R','t',1)]))
    graphs.append({(0,'g','s','R','a'):10,(0,'g','a','R','t'):10,(1,'g','t','R','a'):1,(1,'g','a','R','s'):10})
    graphs.append({(0,'g','s','R','t'):None})
    # Includes missing scalar at an existing raw coordinate, zero and negative.
    for _ in range(18):
        rows=[('g',u,p,v,rng.choice([None,-2,0,1,2,5])) for u,v,p in itertools.product('sab','abt',['R','S']) if rng.randrange(5)==0]
        graphs.append(raw_graph(rows))
    for raw in graphs:
        for (s,t),cap,H,d,ps,g in itertools.product([('s','t'),('s','s'),('s','ghost')],[0,3,5,20],[0,2,3],['out','in','both'],[[],['R']],['g','other']):
            cases.append(case(raw,s,t,cap,H,d,ps,g))
    # Stale raw higher entries really survive a strict distance improvement.
    stale=raw_graph([('g','s','R','a',9),('g','s','R','b',1),('g','b','R','a',1)])
    cases.append(case(stale,'s','ghost',20,0,'out',[],'g'))
    witness=case(graphs[0],'s','t',20,2,'out',[],'g')
    sensitivity={'changed_final_cost_rejected':witness['agrees'] and not case(graphs[0],'s','t',20,2,'out',[],'g',alter=True)['agrees'],
        'node_only_source_port_rejected':not case(graphs[0],'s','t',20,2,'out',[],'g',mutant='node-only')['agrees'],
        'exclusive_cap_source_port_rejected':not case(graphs[0],'s','t',5,2,'out',[],'g',mutant='exclusive-cap')['agrees']}
    observations={'stale_pop_observed':cases[-1]['agrees'] and cases[-1]['stale_pops']>0}
    fn=source_variant('max_hops = _int_argument(name, "maxHops", _arg_raw(args[4], parameters), 0) if len(args) > 4 else 10','max_hops = 0')
    with patch.object(em.IRISGraphEngine,'_proc_ivg_shortestpath_weighted',fn):sensitivity['actual_hop_producer_removed']=not case(graphs[0],'s','t',20,2,'out',[],'g')['agrees']
    fn=source_variant('float(path_obj.get("totalCost", 0))','0.0')
    with patch.object(em.IRISGraphEngine,'_proc_ivg_shortestpath_weighted',fn):sensitivity['actual_cost_consumer_changed']=not case(graphs[0],'s','t',20,2,'out',[],'g')['agrees']
    inputs={};identities={}
    for rel in ['iris_vector_graph/engine.py','iris_vector_graph/cypher/ast.py','iris_vector_graph/cypher/translator.py','iris_src/src/Graph/KG/Traversal.cls','iris_src/src/Graph/KG/TraversalPaths.cls','iris_src/src/Graph/KG/Adjacency.cls','iris_src/src/Graph/KG/AdjIndex.cls','iris_src/src/Graph/KG/GraphMode.cls','iris_vector_graph/_engine/nodes_edges.py']:
        inputs[rel]=bc.sha(PIN/rel);identities[rel]=bc.sha(REPO/rel)==inputs[rel]
    for rel in ['.g5/uplift/consolidated/iteration-9/weighted-native.py','.g5/uplift/consolidated/iteration-9/weighted-native.json','.g5/uplift/consolidated/iteration-9/weighted-native-neighbors.py','.g5/uplift/consolidated/iteration-9/weighted-native-neighbors.json','.g5/uplift/consolidated/iteration-9/weighted-mirror-native.py','.g5/uplift/consolidated/iteration-9/weighted-mirror-native.json']:
        inputs[rel]=bc.sha(REPO/rel)
    for q in [Path(__file__),HERE/'weighted_paths.rs',HERE/'model.json',HERE.parents[1]/'tools/binding_common.py']:
        inputs[str(q.relative_to(REPO))]=bc.sha(q)
    mism=[c for c in cases if not c['agrees'] or c['pops']>c['rank_bound']]
    verdict='AGREES' if not mism and all(sensitivity.values()) and all(observations.values()) and all(identities.values()) and CONNECT.call_count==0 else 'DISAGREES'
    out=bc.write_receipt('weighted_paths',Path(__file__),{'verdict':verdict,'comparisons':len(cases),'mismatch_count':len(mism),'mismatches':mism[:8],'samples':[witness,cases[-1]],'sensitivity':sensitivity,'domain_observations':observations,'socket_connect_calls':CONNECT.call_count,'elapsed':time.monotonic()-started,'source_inputs':inputs,'inputs':inputs,'current_equals_exported_pin':identities,'pin_dir':str(PIN),
        'scope':'Actual pinned Python handler argument producer and final float consumer over executing mutable source-port; functional initial/step/expand trace and independent finite-walk optimum. Port is not native execution. Main proof integer exact stable raw scalar graph; DijkstraCost/native roundoff/serialization correspondence not formally proved. Root-owned native receipts are separately stamped observations, not rerun.'})
    print(json.dumps({'verdict':verdict,'comparisons':len(cases),'mismatches':len(mism),'sensitivity':sensitivity,'domain_observations':observations,'receipt':str(out),'elapsed':time.monotonic()-started}));assert verdict=='AGREES'
if __name__=='__main__':main()
