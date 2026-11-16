"""Independent raw-row relational oracle; no provider/port/product imports."""
import json

def read(v):
 if v=='true':return True
 if v=='false':return False
 if isinstance(v,str) and v[:1] in ('[','{'):
  x=json.loads(v)
  if isinstance(x,(list,dict)):return x
 return v

def full_records(raw,requests,g=''):
 out=[]
 for id in requests:
  labels=[l for rg,n,l in raw['labels'] if rg==g and n==id]
  relevant=[(i,k,v) for i,(rg,n,k,v) in enumerate(raw['props']) if rg==g and n==id]
  if not labels and not relevant and (g,id) not in raw['nodes']:continue
  r={'id':id,'labels':labels}
  aliases={('p_'+k if k in ('id','labels') else k) for i,k,v in relevant}
  for key in sorted(aliases):
   i,k,v=max((row for row in relevant if ('p_'+row[1] if row[1] in ('id','labels') else row[1])==key),key=lambda row:row[0])
   r[key]=read(v)
  out.append(r)
 return out

def export(raw):
 ids=sorted(n for g,n in raw['nodes'] if g=='')
 hydrated=full_records(raw,ids)
 nodes=[dict(kind='node',id=n['id'],labels=n['labels'],properties={k:v for k,v in n.items() if k not in ('id','labels')}) for n in hydrated]
 edges=[]
 selected=[row for row in raw['edges'] if row[0]=='' and not (row[5] or '').startswith('{"temporal"')]
 for rg,serial,s,p,o,q in sorted(selected,key=lambda row:row[1]):
  e=dict(kind='edge',source=s,predicate=p,target=o)
  value=json.loads(q) if q else None
  if value:e['qualifiers']=value
  edges.append(e)
 return dict(records=nodes+edges,counts=dict(nodes=len(nodes),edges=len(edges)))

def callbacks(records,graph=None):
 calls=[]
 for e in records:
  if e['kind']=='node':calls.append(dict(kind='node',id=e['id'],labels=e['labels'],properties=e['properties'],graph=graph))
  else:
   kwargs={}
   if graph is not None or bool(e.get('qualifiers')):kwargs={'qualifiers':e.get('qualifiers') or None,'graph':graph}
   calls.append(dict(kind='edge',source=e['source'],predicate=e['predicate'],target=e['target'],kwargs=kwargs))
 return dict(calls=calls,counts=dict(nodes=sum(e['kind']=='node' for e in records),edges=sum(e['kind']=='edge' for e in records),temporal_edges=0,skipped=0))
