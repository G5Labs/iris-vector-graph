"""Independent complete-map interpreter of the Verus ordinary/default fragment.
No SQL/product classes, expected graph/delta or snapshot-truth inputs.
"""
import copy,json,re

def canonical_value(v):
 if v is None or not isinstance(v,(str,bool,int,float)):raise ValueError('unsupported/null value')
 return ('true' if v else 'false') if isinstance(v,bool) else str(v)
def normalized_ops(raw):
 out=copy.deepcopy(raw)
 for o in out:
  for field in ['props','quals']:
   if field in o:
    if field=='props' and any(str(k) in ('id','__graph') for k in o[field]):raise ValueError('reserved_property')
    o[field]={str(k):canonical_value(v) for k,v in o[field].items()}
  if o['op'] in ('set_prop','remove_prop') and o['key'] in ('id','__graph'):raise ValueError('reserved_property')
  if o['op'] in ('set_prop','set_qual'):o['value']=canonical_value(o['value'])
  if o['op'] in ('set_qual','remove_qual') and not o['key']:raise ValueError('qualifier key required')
 return json.loads(json.dumps(out,sort_keys=True))
def normalized_state(s):
 return dict(nodes={k:dict(labels=sorted(v['labels']),props=dict(v['props'])) for k,v in s['nodes'].items()},rels={str(k):dict(v) for k,v in s['rels'].items()})
class Model:
 def __init__(self):self.state=dict(nodes={},rels={});self.next=1;self.seq=1;self.logs=[];self.states={1:copy.deepcopy(self.state)}
 def commit(self,ops):
  g=copy.deepcopy(self.state);ns=g['nodes'];es=g['rels'];nextid=self.next;records=[];deadn=set();deadr=set();opids={}
  def emit(op,kind,eid,attr='',before=None,after=None,graph=None):records.append(dict(op=op,entity_kind=kind,entity_id=str(eid),attr=attr,prior=before,new=after,graph=graph))
  def no(condition,msg='refusal'):
   if condition:raise ValueError(msg)
  def qjson(t):return json.dumps(t,sort_keys=True,separators=(',',':'))
  def ref(r):
   if 'op_ref' in r:rid=opids[r['op_ref']]
   elif 'stmt_id' in r:rid=int(r['stmt_id'])
   else:
    t=r['tuple'];rid=next((i for i,e in es.items() if (e['s'],e['p'],e['o'],e['graph'])==(t['s'],t['p'],t['o'],t.get('graph') or None)),None)
   no(rid is None or rid in deadr or rid not in es);return rid
  def qual(rid,new,replace=False):
   old=es[rid]['quals'];no('weight' in new and not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',new['weight']))
   no('' in new,'carrier')
   if replace:
    for k in sorted(set(old)-set(new)):emit('remove_qual','rel',rid,k,old.pop(k),None,es[rid]['graph'])
   for k,v in sorted(new.items()):
    if old.get(k)!=v:emit('set_qual','rel',rid,k,old.get(k),v,es[rid]['graph']);old[k]=v
  def delete_rel(rid):
   e=es.pop(rid);emit('delete_rel','rel',rid,before=qjson(e),graph=e['graph']);deadr.add(rid)
  try:
   for i,o in enumerate(ops):
    k=o['op'];n=o.get('id');key=o.get('key');no(n in deadn,'deleted')
    if k in ('create_node','upsert_node'):
     no(not n);no(n in ns and k=='create_node');no(any(k in ('id','__graph') for k in o.get('props',{})))
     if n not in ns:ns[n]=dict(labels=set(),props={});emit('create_node','node',n,after='')
     for lab in o.get('labels',[]):
      no(not lab)
      if lab not in ns[n]['labels']:ns[n]['labels'].add(lab);emit('add_label','node',n,lab,None,'')
     for key,v in o.get('props',{}).items():
      no(not key)
      if ns[n]['props'].get(key)!=v:emit('set_prop','node',n,key,ns[n]['props'].get(key),v);ns[n]['props'][key]=v
    elif k in ('add_label','remove_label'):
     no(n not in ns);lab=o['label']
     if k=='add_label':
      no(not lab)
      if lab not in ns[n]['labels']:ns[n]['labels'].add(lab);emit(k,'node',n,lab,None,'')
     else:no(lab not in ns[n]['labels']);ns[n]['labels'].remove(lab);emit(k,'node',n,lab,'',None)
    elif k in ('set_prop','remove_prop'):
     no(key in ('id','__graph'));no(n not in ns);props=ns[n]['props']
     if k=='set_prop':
      no(not key);v=o['value']
      if props.get(key)!=v:emit(k,'node',n,key,props.get(key),v);props[key]=v
     else:no(key not in props);emit(k,'node',n,key,props.pop(key),None)
    elif k in ('create_rel','upsert_rel'):
     t=copy.deepcopy(o['tuple']);t['graph']=t.get('graph') or None;no(not t['p'] or not t['s'] or not t['o']);no(t['s'] in deadn or t['o'] in deadn);no(t['s'] not in ns or t['o'] not in ns)
     qs=o.get('quals',{});no('weight' in qs and not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',qs['weight']))
     rid=next((i for i,e in es.items() if all(e[x]==t[x] for x in ['s','p','o','graph'])),None)
     if rid is not None:no(k=='create_rel');qual(rid,qs)
     else:
      no('' in qs,'carrier');rid=nextid;nextid+=1;es[rid]={**t,'quals':dict(qs)};emit('create_rel','rel',rid,after=qjson(t),graph=t['graph'])
      for key,v in sorted(qs.items()):emit('set_qual','rel',rid,key,None,v,t['graph'])
     opids[i]=rid
    elif k=='delete_rel':delete_rel(ref(o['ref']))
    elif k in ('set_qual','remove_qual','replace_quals'):
     rid=ref(o['ref'])
     if k=='replace_quals':qual(rid,o.get('quals',{}),True)
     else:
      no(not key)
      if k=='set_qual':qual(rid,{key:o['value']})
      else:no(key not in es[rid]['quals']);emit(k,'rel',rid,key,es[rid]['quals'].pop(key),None,es[rid]['graph'])
    elif k=='delete_node':
     no(n not in ns);incident=sorted(i for i,e in es.items() if e['graph'] is None and n in (e['s'],e['o']));no(incident and o.get('mode','strict')!='detach')
     for rid in incident:delete_rel(rid)
     v=ns.pop(n);emit('delete_node','node',n,before=qjson(dict(labels=sorted(v['labels']),props=v['props'])));deadn.add(n)
    else:raise ValueError('unsupported')
  except (ValueError,KeyError):return dict(ok=False,records=[],op_index=i)
  self.state=g;self.next=nextid;self.seq+=1
  for ordinal,r in enumerate(records,1):r.update(seq=self.seq,ordinal=ordinal)
  self.logs.extend(records);self.states[self.seq]=copy.deepcopy(g)
  return dict(ok=True,records=records,stmt_ids={i:str(v) for i,v in opids.items()})

def reader(rs):
 s=dict(nodes={},rels={});by={}
 for r in rs:
  if r.get('op')=='redacted' or r.get('entity_kind')=='revision':continue
  op=r['op'];id=r['entity_id'];a=r.get('attr','');v=r.get('new')
  if r['entity_kind']=='node':
   if op=='create_node':s['nodes'][id]=dict(labels=set(),props={})
   elif op=='delete_node':s['nodes'].pop(id,None)
   elif id in s['nodes']:
    n=s['nodes'][id]
    if op=='add_label':n['labels'].add(a)
    elif op=='remove_label':n['labels'].discard(a)
    elif op=='set_prop':n['props'][a]='' if v is None else v
    elif op=='remove_prop':n['props'].pop(a,None)
  else:
   if op=='create_rel':
    t=json.loads(v or '{}');g=t.get('graph');g=None if g in (None,'','\0') else str(g)
    e={x:str(t.get(x,'')) for x in ['s','p','o']};e.update(graph=g,quals={});s['rels'][id]=e;by[tuple(e[x] for x in ['s','p','o','graph'])]=id
   elif op=='delete_rel':
    e=s['rels'].pop(id,None)
    if e:by.pop(tuple(e[x] for x in ['s','p','o','graph']),None)
   elif id in s['rels']:
    if op=='set_qual':s['rels'][id]['quals'][a]='' if v is None else v
    elif op=='remove_qual':s['rels'][id]['quals'].pop(a,None)
 return s,by

def endpoint_diff(a,b):
 out=[]
 for n in sorted(set(a['nodes'])|set(b['nodes'])):
  x=a['nodes'].get(n);y=b['nodes'].get(n)
  assert x is not None and y is not None
  for label in sorted(x['labels']|y['labels']):
   before='' if label in x['labels'] else None;after='' if label in y['labels'] else None
   if before!=after:out.append(dict(entity_kind='node',entity_id=n,attr='label:'+label,before=before,after=after))
  for key in sorted(set(x['props'])|set(y['props'])):
   before=x['props'].get(key);after=y['props'].get(key)
   if before!=after:out.append(dict(entity_kind='node',entity_id=n,attr='prop:'+key,before=before,after=after))
 for rid in sorted(set(a['rels'])|set(b['rels']),key=str):
  x=a['rels'].get(rid);y=b['rels'].get(rid);assert x is not None and y is not None
  for key in sorted(set(x['quals'])|set(y['quals'])):
   before=x['quals'].get(key);after=y['quals'].get(key)
   if before!=after:out.append(dict(entity_kind='rel',entity_id=str(rid),attr='qual:'+key,before=before,after=after))
 return sorted(out,key=lambda e:(e['entity_kind']!='node',e['entity_id'],e['attr']))
