"""Executable source-shaped transcription of the verified admitted raw-row/event/callback functions."""
def scalar(v):
 if type(v) in (int,float):return v
 if v=='true':return True
 if v=='false':return False
 return v

def get_nodes(raw,requests,graph=None):
 g='' if graph is None else graph
 m={id:{'id':id,'labels':[]} for id in requests}
 for rg,id,label in raw['labels']:
  if rg==g and id in m:m[id]['labels'].append(label)
 for rg,id,key,v in raw['props']:
  if rg==g and id in m:m[id]['p_'+key if key in ('id','labels') else key]=scalar(v)
 out=[]
 for id in requests:
  r=m[id]
  if r['labels'] or len(r)>2 or (g,id) in raw['nodes']:out.append(r)
 return out

def qualifier(text):
 if text is None or text in ('','{}'):return None
 if not (text.startswith('{"q":') and text.endswith('}')):raise ValueError('outside formal qualifier grammar')
 ds=text[5:-1]
 if not ds or len(ds)>1 and ds[0]=='0' or any(not '0'<=c<='9' for c in ds):raise ValueError('outside formal qualifier grammar')
 n=0
 for c in ds:n=n*10+ord(c)-ord('0')
 return {'q':n}

def export(raw):
 records=[];nodes=edges=0
 for id in sorted(id for g,id in raw['nodes'] if g==''):
  out=get_nodes(raw,[id]);r=out[0] if out else None
  if r:
   records.append(dict(kind='node',id=id,labels=r.get('labels',[]),properties={k:v for k,v in r.items() if k not in ('id','labels')}));nodes+=1
 for g,serial,s,p,o,q in sorted(raw['edges'],key=lambda x:x[1]):
  if g!='' or q is not None and q.startswith('{"temporal"'):continue
  e=dict(kind='edge',source=s,predicate=p,target=o);quals=qualifier(q)
  if quals:e['qualifiers']=quals
  records.append(e);edges+=1
 return dict(records=records,counts=dict(nodes=nodes,edges=edges))

def callbacks(records,graph=None):
 calls=[];nodes=edges=0
 for e in records:
  if e['kind']=='node':calls.append(dict(kind='node',id=e['id'],labels=e['labels'],properties=e['properties'],graph=graph));nodes+=1
  else:
   q=e.get('qualifiers');kw=dict(qualifiers=q or None,graph=graph) if graph is not None or q else {}
   calls.append(dict(kind='edge',source=e['source'],predicate=e['predicate'],target=e['target'],kwargs=kw));edges+=1
 return dict(calls=calls,counts=dict(nodes=nodes,edges=edges,temporal_edges=0,skipped=0))
