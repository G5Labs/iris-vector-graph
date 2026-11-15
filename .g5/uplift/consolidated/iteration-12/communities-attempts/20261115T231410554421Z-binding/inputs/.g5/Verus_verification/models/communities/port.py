"""Mutable source-shaped Owner kernels and raw projection/census, no native execution."""
from collections import Counter

def coordinates(edges):
    return sorted({(d,g,s if not d else o,p,o if not d else s) for g,s,p,o,k in edges for d in (False,True)})
def members(raw):return {u for d,g,u,p,v in raw if g==''}
def weak_oracle(edges,key):
    raw=coordinates(edges);nodes=members(raw);adj={u:set() for u in nodes}
    for d,g,u,p,v in raw:
        if g=='':adj.setdefault(u,set()).add(v)
    out={}
    for u in nodes:
        seen={u};todo=[u]
        while todo:
            x=todo.pop()
            for v in adj.get(x,()):
                if v not in seen:seen.add(v);todo.append(v)
        out[u]=min(seen,key=key)
    return out

def model(raw,kind,limit,key):
    nodes=members(raw);labels={u:u for u in nodes};trace=[];rounds=0
    if not nodes:return labels,trace
    while True:
        if kind=='wcc' and limit is not None and rounds>=limit:trace.append(('refuse',rounds,dict(labels)));raise ModelRefusal(trace)
        if kind=='cdlp' and rounds>=max(limit,0):return labels,trace
        old=labels
        if kind=='wcc':new={u:min([old[u]]+[old.get(v,v) for d,g,a,p,v in raw if g=='' and a==u],key=key) for u in nodes}
        else:
            def vote(u):
                c=Counter(old.get(v,v) for d,g,a,p,v in raw if g=='' and a==u and v!=u)
                return min(c,key=lambda x:(-c[x],key(x))) if c else old[u]
            new={u:vote(u) for u in nodes}
        changed=sum(new[u]!=old[u] for u in nodes);rounds+=1;trace.append(('round',rounds,dict(old),dict(new),changed));labels=new
        if not changed:return labels,trace
class ModelRefusal(RuntimeError):
    def __init__(self,trace):self.trace=trace;super().__init__('WCC did not converge')

class SourcePort:
    """Algorithms.cls10..185 loops over source old/new maps and ordered coordinates."""
    def __init__(self,raw,key,mutant=None):self.raw=list(raw);self.key=key;self.mutant=mutant;self.trace=[]
    def neighbors(self,u):
        for d in (False,True):
            if self.mutant=='out-only' and d:continue
            for a in sorted((a for a in self.raw if a[0]==d and a[1]=='' and a[2]==u),key=lambda a:(self.key(a[3]),self.key(a[4]))):yield a[4]
    def run(self,kind,limit):
        labels={u:u for u in sorted(members(self.raw),key=self.key)};self.trace=[];iteration=0
        if not labels:return labels
        while True:
            if kind=='wcc' and limit is not None and iteration>=limit and self.mutant!='guard-after-scan':self.trace.append(('refuse',iteration,dict(labels)));raise RuntimeError('WCC did not converge')
            if kind=='cdlp' and iteration>=max(limit,0):return labels
            old=dict(labels);new={};changed=0
            for u in sorted(labels,key=self.key):
                read=labels if self.mutant=='in-place' else old;mine=read[u]
                if kind=='wcc':
                    best=mine
                    for v in self.neighbors(u):
                        other=read.get(v,v)
                        if self.key(other)<self.key(best):best=other
                else:
                    counts={}
                    for v in self.neighbors(u):
                        if v==u and self.mutant!='count-self':continue
                        x=read.get(v,v);counts[x]=1 if self.mutant=='dedup-label-votes' else counts.get(x,0)+1
                    best=mine;amount=0
                    for x in sorted(counts,key=self.key):
                        n=counts[x]
                        if n>amount or n==amount and (self.key(x)>self.key(best) if self.mutant=='tie-last' else self.key(x)<self.key(best)):best=x;amount=n
                if best!=old[u]:changed+=1
                new[u]=best
                if self.mutant=='in-place':labels[u]=best
            iteration+=1;labels=new;self.trace.append(('round',iteration,old,dict(new),changed))
            if not changed:return labels
            if kind=='wcc' and limit is not None and iteration>limit:self.trace.append(('refuse',iteration,dict(labels)));raise RuntimeError('WCC did not converge')

def loners_sql(nodes,edges):
    return {u:any(g=='' and s==u for g,s,p,o,k in edges) for g,u in nodes if g=='' and not any(eg=='' and ((s==u and o!=u) or (o==u and s!=u)) for eg,s,p,o,k in edges)}
def loners_native(nodes,raw):
    return {u:any(g=='' and not d and a==u for d,g,a,p,v in raw) for g,u in nodes if g=='' and not any(rg=='' and a==u and v!=u for d,rg,a,p,v in raw)}
def native_page(nodes,raw,after,page,key):
    all=loners_native(nodes,raw);ids=sorted((u for u in all if not after or key(u)>key(after)),key=key);chosen=ids[:page] if page>0 else ids
    return {'loners':{u:int(all[u]) for u in chosen},'next':chosen[-1] if page>0 and len(chosen)>=page else ''}
def complete(core,loners,key):
    return {u:core.get(u,u) for u in sorted(set(core)|set(loners),key=key)}
