"""Read-only exact-integer DijkstraCost source-shaped preparation, not a model proof.
No product import/runtime/native/network/Git. Socket guard is active before work.
"""
import hashlib,itertools,json,random,socket,time
from pathlib import Path
from unittest.mock import patch
GUARD=patch.object(socket.socket,'connect',side_effect=AssertionError('cost preparation forbids network'))
CONNECT=GUARD.start()
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
def effective(w):return w if w is not None and w>0 else 1

def raw(rows):
    d={}
    for g,u,p,v,w in rows:d[(0,g,u,p,v)]=w;d[(1,g,v,p,u)]=w
    return d

def oriented(d,g,direction,preds,side=0):
    first=1 if direction=='in' else 0;second=1-first
    tags=[first,second] if direction=='both' else [first]
    if side:tags=[1-t for t in tags]
    return [(u,p,v,effective(d[(tag,gg,u,p,v)])) for tag in tags for tt,gg,u,p,v in sorted(d) if tt==tag and gg==g and (not preds or p in preds)]

def walks(arcs,s,t,cap,H=0):
    # Independent exhaustive simple-path oracle; no search algorithm consumes it.
    answers=[]
    def rec(u,c,h,seen,path):
        if u==t:answers.append((c,h,path));return
        if H and h>=H:return
        for a,p,v,w in arcs:
            if a==u and v not in seen and c+w<=cap:rec(v,c+w,h+1,seen|{v},path+[(a,p,v,w)])
    rec(s,0,0,{s},[])
    if not answers:return None,None,None
    c=min(x[0] for x in answers);best=[x for x in answers if x[0]==c];answer=min(best,key=lambda x:x[1]);return answer

def path_valid(p,arcs,s,t):
    return (p[0][0] if p else t)==s and (p[-1][2] if p else s)==t and all(a in arcs for a in p) and all(p[i][2]==p[i+1][0] for i in range(len(p)-1))

def json_search(arcs,s,t,cap,H):
    if not s or not t:return None
    if s==t:return 0
    q={(0,s,0)};dist={(s,0):0};seen={};parent={}
    while q:
        c,u,h=min(q);q.remove((c,u,h))
        if u in seen and seen[u]<=h:continue
        seen[u]=h
        if u==t:
            v=t;hh=h;path=[]
            while v!=s:
                if (v,hh) not in parent:break
                before,ph,p,w=parent[(v,hh)];path.insert(0,(before,p,v,w));v,hh=before,ph
            assert path_valid(path,arcs,s,t) and sum(a[3] for a in path)==c and (not H or len(path)<=H)
            return c
        if c>=cap or (H and h>=H):continue
        nh=h+1 if H else 0
        for a,p,v,w in arcs:
            if a!=u or (v in seen and seen[v]<=nh):continue
            nc=c+w
            if nc>cap:continue
            if (v,nh) not in dist or nc<dist[(v,nh)]:dist[(v,nh)]=nc;q.add((nc,v,nh));parent[(v,nh)]=(u,h,p,w)
    return None

def cost_search(d,s,t,cap,H,direction,preds,g,mutant=None,audit=True):
    arcs=[oriented(d,g,direction,preds,i) for i in [0,1]]
    if not s or not t:return {'cost':None,'stop':'empty_endpoint','pops':0,'events':[],'fallback':False}
    if s==t:return {'cost':0,'stop':'self','pops':0,'events':[],'fallback':False}
    transpose={(v,p,u,w) for u,p,v,w in arcs[0]}==set(arcs[1])
    if mutant=='same-way-back':arcs[1]=arcs[0]
    dist=[{s:0},{t:0}];hop=[{s:0},{t:0}];pq=[{(0,s)},{(0,t)}];done=[set(),set()]
    witness=[{s:[]},{t:[]}];roots=[s,t];best=None;besth=0;bestpath=None;bestvertex=None;events=[];pops=0;label_after_best=0;own_best_label_updates=0;equal_shorter=0;decreases=0
    optimum=walks(arcs[0],s,t,cap)[0] if audit else None
    def check():
        if not audit:return
        for side in [0,1]:
            assert pq[side]=={(c,v) for v,c in dist[side].items() if v not in done[side]},('queue_exact',side,pq,dist,done)
            for v,c in dist[side].items():
                p=witness[side][v];assert path_valid(p,arcs[side],roots[side],v) and len(p)==hop[side][v] and sum(a[3] for a in p)==c
            for v in done[side]:assert walks(arcs[side],roots[side],v,cap)[0]==dist[side][v],('settled_optimal',side,v)
        dual=set(dist[0])&set(dist[1]);minimum=min((dist[0][v]+dist[1][v] for v in dual),default=None)
        assert best==minimum,('best_current_min',best,minimum)
        if best is not None:
            assert dist[0][bestvertex]+dist[1][bestvertex]==best
            assert hop[0][bestvertex]+hop[1][bestvertex]==besth
            assert len(bestpath)==besth and sum(a[3] for a in bestpath)==best
            if transpose:assert path_valid(bestpath,arcs[0],s,t)
    while True:
        check()
        if not pq[0] or not pq[1]:stop='empty_frontier';break
        tops=[min(q)[0] for q in pq]
        if audit and transpose and optimum is not None and (best is None or optimum<best):assert sum(tops)<=optimum,('frontier_bound',tops,optimum,best)
        if best is not None and sum(tops)+(2 if mutant=='early-frontsum' else 0)>=best:stop='frontsum';break
        side=0 if tops[0]<=tops[1] else 1;other=1-side;c,u=min(pq[side]);pq[side].remove((c,u));done[side].add(u);pops+=1
        if c>=cap:continue
        for a,p,v,w in arcs[side]:
            if a!=u or v in done[side]:continue
            new=c+w
            if new>cap:continue
            oldbest=best;oldv=bestvertex
            if v not in dist[side] or new<dist[side][v]:
                if best is not None:label_after_best+=1
                if best is not None and v==bestvertex:own_best_label_updates+=1
                if v in dist[side]:
                    decreases+=1
                    if mutant!='keep-old-queue':pq[side].discard((dist[side][v],v))
                dist[side][v]=new;pq[side].add((new,v));hop[side][v]=hop[side][u]+1;witness[side][v]=witness[side][u]+[(u,p,v,w)]
            if v in dist[other]:
                meet=dist[side][v]+dist[other][v];h=hop[side][v]+hop[other][v]
                if best is not None and meet==best and h<besth:equal_shorter+=1;events.append({'kind':'equal_cheaper_hops_ignored','meeting':v,'cost':meet,'retained_hops':besth,'alternative_hops':h})
                if best is None or meet<best:
                    best=meet;besth=0 if mutant=='zero-best-hop' else h;bestvertex=v
                    bestpath=witness[0][v]+[(y,p,x,w) for x,p,y,w in reversed(witness[1][v])]
                    events.append({'kind':'best','cost':best,'hops':besth,'vertex':v,'path':bestpath})
                    if mutant=='first-meeting':return {'cost':best if best<=cap else None,'stop':'mutant_first_meeting','pops':pops,'events':events,'fallback':False}
            if audit and oldbest is not None and oldv==v and bestvertex==oldv and best==oldbest:
                assert dist[0][oldv]+dist[1][oldv]==oldbest,('recorded_meeting_changed_without_best',oldv)
    if best is None or best>cap:answer=None;fallback=False
    elif H>0 and besth>H and mutant!='no-fallback':answer=json_search(arcs[0],s,t,cap,H);fallback=True
    else:answer=best;fallback=False
    n=len({s,t}|{u for aa in arcs for u,p,v,w in aa}|{v for aa in arcs for u,p,v,w in aa})
    if audit:assert pops<=2*n
    if audit and transpose:assert (best if best is not None and best<=cap else None)==optimum
    return {'cost':answer,'stop':stop,'pops':pops,'finite_pop_bound':2*n,'events':events,'fallback':fallback,'best':best,'best_hops':besth,'label_updates_after_best':label_after_best,'recorded_meeting_label_updates':own_best_label_updates,'equal_shorter_meetings':equal_shorter,'decrease_key_updates':decreases,'transpose':transpose}

def main():
    began=time.monotonic();rng=random.Random(21910);rows=[];counts={'cases':0,'fallbacks':0,'frontsum':0,'empty_frontier':0,'decrease_key_updates':0,'label_updates_after_best':0,'recorded_meeting_label_updates':0,'equal_shorter_meetings':0};failures=[]
    A=[('g','s','R','a',4),('g','s','R','b',1),('g','b','R','a',1),('g','a','R','t',1)]
    tie=[('g','s','R','a',2),('g','a','R','b',2),('g','b','R','c',2),('g','c','R','t',2),('g','s','R','x',3),('g','x','R','y',2),('g','y','R','t',3)]
    first=[('g','s','R','a',1),('g','a','R','t',9),('g','s','R','b',4),('g','b','R','t',4)]
    early=[('g','s','R','a',1),('g','a','R','b',1),('g','b','R','t',1),('g','s','R','x',2),('g','x','R','t',2)]
    graphs=[raw(A),raw(tie),raw(first),raw(early)]
    for _ in range(140):graphs.append(raw([('g',u,p,v,rng.choice([None,-2,0,1,2,4,7])) for u,v,p in itertools.product('sabt','sabt',['R','S']) if rng.randrange(7)==0]))
    for i,d in enumerate(graphs):
        for (s,t),cap,H,direction,preds in itertools.product([('s','t'),('s','ghost'),('s','s')],[0,3,5,20],[0,2,3],['out','in','both'],[[],['R']]):
            got=cost_search(d,s,t,cap,H,direction,preds,'g');want=walks(oriented(d,'g',direction,preds),s,t,cap,H)[0]
            counts['cases']+=1
            for k in ['decrease_key_updates','label_updates_after_best','recorded_meeting_label_updates','equal_shorter_meetings']:counts[k]+=got.get(k,0)
            counts['fallbacks']+=got['fallback'];counts['frontsum']+=got['stop']=='frontsum';counts['empty_frontier']+=got['stop']=='empty_frontier'
            if got['cost']!=want:failures.append({'graph':i,'input':[s,t,cap,H,direction,preds],'got':got,'want':want})
    decisive={}
    for name,d,H,cap in [('bounded_hop',raw(A),2,20),('equal_cost_shorter_hop',raw(tie),3,20),('first_intersection',raw(first),0,20),('frontsum_neighbor',raw(early),0,20)]:
        got=cost_search(d,'s','t',cap,H,'out',[],'g');decisive[name]={'result':got,'oracle':walks(oriented(d,'g','out',[]),'s','t',cap,H)[:2]}
    sensitivity={}
    for m,d,H in [('no-fallback',raw(A),2),('zero-best-hop',raw(A),2),('first-meeting',raw(first),0),('same-way-back',raw(A),0),('early-frontsum',raw(early),0)]:
        changed=cost_search(d,'s','t',20,H,'out',[],'g',m,False);want=walks(oriented(d,'g','out',[]),'s','t',20,H)[0];sensitivity[m]={'detected':changed['cost']!=want,'changed':changed,'want':want}
    # Queue mutation is a source-correspondence invariant check, not necessarily a cost counterexample.
    queue_error=None
    for d in graphs:
        try:cost_search(d,'s','ghost',20,0,'out',[],'g','keep-old-queue',True)
        except AssertionError as ex:queue_error=str(ex);break
    sensitivity['old-queue-entry-not-killed']={'detected':queue_error is not None,'invariant_error':queue_error,'kind':'queue-correspondence; result need not differ'}
    d=raw([('g','s','R','a',10),('g','a','R','t',10)]);mirror=[]
    for mode in ['complete','missing','unequal']:
        v=dict(d)
        if mode=='missing':v.pop((1,'g','t','R','a'))
        if mode=='unequal':v[(1,'g','t','R','a')]=1
        got=cost_search(v,'s','t',99,0,'out',[],'g',audit=False);mirror.append({'mode':mode,'cost':got['cost'],'json_cost':json_search(oriented(v,'g','out',[]),'s','t',99,0),'transpose':got['transpose']})
    inputs={}
    for rel in ['iris_src/src/Graph/KG/TraversalPaths.cls','.g5/uplift/consolidated/iteration-9/weighted-cost-next-PAIRS.md','.g5/uplift/consolidated/iteration-9/weighted-cost-next-start.json','.g5/uplift/consolidated/iteration-9/weighted-mirror-native.json']:
        inputs[rel]=hashlib.sha256((REPO/rel).read_bytes()).hexdigest()
    result={'verdict':'AGREES' if not failures and all(v['detected'] for v in sensitivity.values()) and CONNECT.call_count==0 else 'DISAGREES','counts':counts,'failures':failures[:10],'decisive':decisive,'sensitivity':sensitivity,'mirror_neighbors':mirror,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'inputs':inputs,'elapsed':time.monotonic()-began,'socket_connect_calls':CONNECT.call_count,'scope':'Pure exact-integer source-shaped finite sanity checks; no actual product/native execution or formal theorem. Oracle used only in assertions/observations; search receives no answer and has no runtimeBudget.'}
    Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'verdict':result['verdict'],'counts':counts,'failures':len(failures),'sensitivities':{k:v['detected'] for k,v in sensitivity.items()},'elapsed':result['elapsed']}));assert result['verdict']=='AGREES'
if __name__=='__main__':main()
