"""Finite source-shaped proof-architecture sanity check; not product execution.

Exact Fraction arithmetic, stable finite leaves and symmetric out/in projection.
The independent finite oracle enumerates simple paths (strictly positive effective
weights make cycles unnecessary). Neither search receives an answer as input.
No native, product import, runtime or network operation is performed.
"""
import hashlib,itertools,json,random,time
from fractions import Fraction as F
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
def eff(w):return F(1) if w is None or w<=0 else F(w)
def arcs(edges,direction,preds=None,broken_reverse=False):
    out={}
    for a,p,b,w in edges:
        if preds is not None and p not in preds:continue
        w=eff(w)
        if direction in ['out','both']:out[(a,p,b)]=w
        if direction in ['in','both'] and not broken_reverse:out[(b,p,a)]=w
    return sorted((a,p,b,w) for (a,p,b),w in out.items())
def json_search(edges,s,t,cap,hops,direction='out',preds=None,node_only=False):
    if not s or not t:return None
    if s==t:return {'nodes':[s],'rels':[],'costs':[],'cost':F(0)}
    a=arcs(edges,direction,preds);q={(F(0),s,0)};dist={(s,0):F(0)};seen={};parent={};steps=0
    while q:
        c,u,h=min(q);q.remove((c,u,h));steps+=1;assert steps<10000
        if u in seen and (node_only or seen[u]<=h):continue
        seen[u]=h
        if u==t:
            nodes=[t];rels=[];costs=[];v=t;hh=h
            while v!=s:
                if (v,hh) not in parent:break
                v,hh,p,w=parent[(v,hh)];nodes.insert(0,v);rels.insert(0,p);costs.insert(0,w)
            return {'nodes':nodes,'rels':rels,'costs':costs,'cost':c}
        if c>=cap or (hops>0 and h>=hops):continue
        nh=h+1 if hops>0 else 0
        for src,p,v,w in a:
            if src!=u:continue
            if v in seen and (node_only or seen[v]<=nh):continue
            nc=c+w
            if nc>cap:continue
            if (v,nh) not in dist or nc<dist[(v,nh)]:
                dist[(v,nh)]=nc;q.add((nc,v,nh));parent[(v,nh)]=(u,h,p,w)
    return None
def cost_search(edges,s,t,cap,hops,direction='out',preds=None,broken_reverse=False):
    if not s or not t:return None,False
    if s==t:return F(0),False
    f=arcs(edges,direction,preds);b=[] if broken_reverse else [(v,p,u,w) for u,p,v,w in f]
    adj=[f,b];dist=[{s:F(0)},{t:F(0)}];hop=[{s:0},{t:0}];q=[{s:F(0)},{t:F(0)}];done=[set(),set()];best=None;besth=0
    while q[0] and q[1]:
        tops=[min(x.values()) for x in q]
        if best is not None and sum(tops)>=best:break
        side=0 if tops[0]<=tops[1] else 1;other=1-side
        u=min(q[side],key=lambda n:(q[side][n],n));c=q[side].pop(u);done[side].add(u)
        if c>=cap:continue
        for src,p,v,w in adj[side]:
            if src!=u or v in done[side]:continue
            nc=c+w
            if nc>cap:continue
            if v not in dist[side] or nc<dist[side][v]:
                dist[side][v]=nc;q[side][v]=nc;hop[side][v]=hop[side][u]+1
            if v in dist[other]:
                meet=dist[side][v]+dist[other][v]
                if best is None or meet<best:best=meet;besth=hop[side][v]+hop[other][v]
    if best is None or best>cap:return None,False
    if hops>0 and besth>hops:
        p=json_search(edges,s,t,cap,hops,direction,preds);return (None if p is None else p['cost']),True
    return best,False
def oracle(edges,s,t,cap,hops,direction,preds):
    if not s or not t:return None
    if s==t:return F(0) # Source early return precedes cap; retain negative-cap quirk.
    a=arcs(edges,direction,preds);answers=[]
    def visit(u,visited,c,h):
        if u==t:answers.append(c);return
        if hops>0 and h>=hops:return
        for src,p,v,w in a:
            if src==u and v not in visited and c+w<=cap:visit(v,visited|{v},c+w,h+1)
    visit(s,{s},F(0),0);return min(answers) if answers else None
def valid_witness(path,edges,s,t,hops,direction,preds):
    if path is None:return True
    nodes=path['nodes'];weights=path['costs'];rels=path['rels'];a=arcs(edges,direction,preds)
    return nodes[0]==s and nodes[-1]==t and len(nodes)==len(rels)+1==len(weights)+1 and sum(weights)==path['cost'] and (hops<=0 or len(rels)<=hops) and all((u,p,v,w) in a for u,p,v,w in zip(nodes,rels,nodes[1:],weights))
def main():
    started=time.monotonic();rng=random.Random(209);graphs=[]
    for i in range(48):
        edges=[]
        for a,b in itertools.product('abcd','abcd'):
            for p in ['R','S']:
                if rng.randrange(7)==0:edges.append((a,p,b,rng.choice([None,F(-1),F(0),F(1,4),F(1),F(2),F(5)])))
        graphs.append(edges)
    fixture=[('a','R','x',5),('a','R','b',1),('b','R','x',1),('x','R','t',1)]
    graphs.append(fixture);mismatches=[];count=0;fallbacks=0
    for i,es in enumerate(graphs):
        for s,t in [('a','d'),('a','a'),('a','z')]+([('a','t')] if i==len(graphs)-1 else []):
            for d,preds,cap,h in itertools.product(['out','in','both'],[None,{'R'}],[F(0),F(1),F(3),F(20)],[0,1,2]):
                want=oracle(es,s,t,cap,h,d,preds);got=json_search(es,s,t,cap,h,d,preds);cost,fb=cost_search(es,s,t,cap,h,d,preds);fallbacks+=fb;count+=1
                if (None if got is None else got['cost'])!=want or cost!=want or not valid_witness(got,es,s,t,h,d,preds):
                    mismatches.append({'graph':i,'edges':es,'s':s,'t':t,'direction':d,'preds':preds,'cap':cap,'hops':h,'want':want,'json':got,'cost':cost})
    decisive=[]
    for h,cap in [(0,20),(2,20),(3,20),(2,5),(2,6)]:
        p=json_search(fixture,'a','t',F(cap),h);c,fb=cost_search(fixture,'a','t',F(cap),h)
        decisive.append({'hops':h,'cap':cap,'json':p,'cost':c,'cost_fallback':fb})
    mutant=json_search(fixture,'a','t',F(20),2,node_only=True)
    asym=[('a','R','x',1),('x','R','t',1)]
    asymmetry={'json_out':json_search(asym,'a','t',F(9),0),'cost_missing_reverse':cost_search(asym,'a','t',F(9),0,broken_reverse=True)[0],
        'interpretation':'specified counterexample to dropping reverse-mirror premise, not an executed native/provider failure'}
    scalar=[{'raw_weights_by_ekey':{1:9,2:1},'selected_lowest_ekey_weight':9,'minimum_row_weight':1,
        'interpretation':'source producer prediction: weighted search sees representative9, not cheaper parallel row1'}]
    out={'kind':'source-shaped exact arithmetic architecture sanity, not actual product execution or formal proof','comparisons':count,'mismatches':mismatches,
        'fallbacks':fallbacks,'decisive':decisive,'node_only_mutant':mutant,'node_only_mutant_detected':mutant is None or mutant['cost']!=6,
        'reverse_mirror_challenge':asymmetry,'raw_adjacency_prediction':scalar,'elapsed':time.monotonic()-started,
        'source_sha256':{p:hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in ['iris_src/src/Graph/KG/TraversalPaths.cls','iris_src/src/Graph/KG/Adjacency.cls','iris_vector_graph/engine.py']},
        'limits':['hand transcription not shipped ObjectScript','exact Fraction/order fragment, no native numeric/coercion/collation','quiescent finite raw adjacency; no writer/rollback/concurrency proof','oracle is finite path enumeration for sanity, not model implementation or supplied answer']}
    HERE.joinpath('weighted-proof-review-probe.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps({'comparisons':count,'mismatches':len(mismatches),'fallbacks':fallbacks,'node_only_detected':out['node_only_mutant_detected'],'elapsed':out['elapsed']}));assert not mismatches and out['node_only_mutant_detected']
if __name__=='__main__':main()
