"""Independent immutable transcription of imported integer-kernel spec operations.
Only graph/cap/H determine search. No optimum, valid trace or result is supplied.
"""

def frozen(v):
    if isinstance(v,dict):return tuple(sorted((k,frozen(x)) for k,x in v.items()))
    if isinstance(v,(set,frozenset)):return tuple(sorted(v))
    if isinstance(v,(list,tuple)):return tuple(frozen(x) for x in v)
    return v

def selected(a,g,d,ps,back=False):
    tag=(1 if d=='in' else 0)^int(back)
    return a[1]==g and ((0<=a[0]<=1) if d=='both' else a[0]==tag) and (not ps or a[3] in ps)

def ordered(raw,g,d,ps,u,back=False):
    # This is the named primary-tag/filter concatenation in weighted_cost.rs.
    p=(1 if d=='in' else 0)^int(back)
    tags=(p,1-p) if d=='both' else (p,)
    return tuple(a for t in tags for a in sorted(raw) if a[0]==t and a[2]==u and selected(a,g,d,ps,back))

def json_search(raw,s,t,cap,H,d,ps,g):
    if s==t:return dict(answer=0,path=[],trace=[],stop='self')
    state=(frozenset({(0,s,0)}),{(s,0):0},{},{}) # q, dist, seen, parent
    history=[]
    while state[0]:
        history.append(frozen(state));q,dist,seen,parent=state;c,u,h=min(q)
        q=q-{(c,u,h)}
        if u in seen and seen[u]<=h:
            state=(q,dist,seen,parent);continue
        seen={**seen,u:h}
        if u==t:
            k=(u,h);p=[]
            while k[0]!=s and k in parent:
                v,hh,a,w=parent[k];p=[(a,w)]+p;k=v,hh
            assert k[0]==s
            return dict(answer=c,path=p,trace=history,stop='target')
        state=(q,dist,seen,parent)
        if c>=cap or (H>0 and h>=H):continue
        nh=h+1 if H>0 else 0
        # JSON always scans out then in, independent of Cost side order.
        for a in sorted(raw):
            if a[2]!=u or not selected(a,g,d,ps):continue
            q,dist,seen,parent=state;n=c+raw[a];v=a[4];k=v,nh
            if (v in seen and seen[v]<=nh) or n>cap or (k in dist and dist[k]<=n):continue
            state=(q|{(n,v,nh)},{**dist,k:n},seen,{**parent,k:(u,h,a,raw[a])})
    history.append(frozen(state))
    return dict(answer=None,path=[],trace=history,stop='empty')

def cost_search(raw,s,t,cap,H,d,ps,g):
    if s==t:return dict(answer=0,trace=[],fallback=False,best_hops=0,stop='self')
    z=lambda r:(frozenset({(0,r)}),{r:0},{r:0},frozenset())
    state=(z(s),z(t),None,0);history=[]
    while True:
        f,b,best,bh=state
        history.append(frozen(([f[0],b[0]],[f[1],b[1]],[f[2],b[2]],[f[3],b[3]],best,bh)))
        if not f[0] or not b[0]:stop='empty';break
        if best is not None and min(f[0])[0]+min(b[0])[0]>=best:stop='frontsum';break
        side=int(min(b[0])[0]<min(f[0])[0]);z=state[side];c,u=min(z[0])
        z=(z[0]-{(c,u)},z[1],z[2],z[3]|{u})
        state=(z,state[1],best,bh) if side==0 else (state[0],z,best,bh)
        if c>=cap:continue
        for a in ordered(raw,g,d,ps,u,bool(side)):
            z=state[side];other=state[1-side];best,bh=state[2:];v=a[4];n=c+raw[a]
            if v in z[3] or n>cap:continue
            if v not in z[1] or n<z[1][v]:
                q=z[0]-({(z[1][v],v)} if v in z[1] else set())
                z=(q|{(n,v)},{**z[1],v:n},{**z[2],v:z[2][u]+1},z[3])
            if v in other[1]:
                total=z[1][v]+other[1][v]
                if best is None or total<best:best,bh=total,z[2][v]+other[2][v]
            state=(z,other,best,bh) if side==0 else (other,z,best,bh)
    fallback=best is not None and best<=cap and H>0 and bh>H
    jr=json_search(raw,s,t,cap,H,d,ps,g) if fallback else None
    answer=None if best is None or best>cap else (jr['answer'] if fallback else best)
    return dict(answer=answer,trace=history,fallback=fallback,best_hops=bh,stop=stop,fallback_json=jr)
