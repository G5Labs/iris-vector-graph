"""Executable transcription of aggregate_results.rs (exact half-unit numerical fragment)."""
def tok(v):
 if type(v) in (int,float):return ('N',int(v*2))
 return (type(v).__name__,v)
def fold(records,graph=None,grouped=False,distinct=False):
 groups={} if grouped else {None:dict(rows=0,seen=set(),items=[],total=0,nums=0,float=False)}
 for g,id,k,v in records:
  if graph is not None and g!=graph:continue
  key=k if grouped else None
  a=groups.setdefault(key,dict(rows=0,seen=set(),items=[],total=0,nums=0,float=False));a['rows']+=1
  a['float'] |= type(v)is float
  if v is None:continue
  t=tok(v);yes=not distinct or t not in a['seen'];a['seen'].add(t)
  if yes:
   a['items'].append(v)
   if type(v) in (int,float):a['total']+=int(v*2);a['nums']+=1
 return {k:dict(star=a['rows'],count=len(a['items']),total=a['total']/2 if a['float'] else a['total']//2,mean=a['total']/(2*a['nums']) if a['nums'] else None,items=a['items']) for k,a in groups.items()}
