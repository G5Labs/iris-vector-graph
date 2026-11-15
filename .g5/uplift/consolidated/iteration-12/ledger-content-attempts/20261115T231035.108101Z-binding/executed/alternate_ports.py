"""Typed Capture/Adopt content projection only. Not native/Python producers.
Ordered projected rows, decoded qualifier values, canonical IDs/tuple codec;
raw SQL scan, tuple-JSON qualifier refs and malformed envelopes are outside.
"""
import copy,json

def rec(op,kind,id,attr='',prior=None,new=None,graph=None):
 return dict(seq=2,ordinal=0,op=op,entity_kind=kind,entity_id=str(id),attr=attr,prior=prior,new=new,graph=graph,flags=[])
def capture(rows):
 state=dict(nodes={},rels={});records=[];next_id=1;by={}
 for row in rows:
  k=row[0]
  if k=='node':
   id=row[1];state['nodes'][id]=dict(labels=[],props={});records.append(rec('create_node','node',id))
  elif k=='label':
   _,id,key=row
   if id in state['nodes']:state['nodes'][id]['labels']=sorted(set(state['nodes'][id]['labels'])|{key})
   records.append(rec('add_label','node',id,key,new=''))
  elif k=='prop':
   _,id,key,val=row
   if key in ('id','__graph'):continue
   val='' if val is None else val
   if id in state['nodes']:state['nodes'][id]['props'][key]=val
   records.append(rec('set_prop','node',id,key,new=val))
  else:
   _,s,p,o,g,raw=row
   if raw.get('temporal') is True:continue
   q={key:('true' if v is True else 'false' if v is False else json.dumps(v,separators=(',',':'),sort_keys=True) if isinstance(v,(dict,list)) else str(v)) for key,v in raw.items() if v is not None}
   if '' in q:return dict(error='KeyCarrier',state=dict(nodes={},rels={}),records=[])
   id=str(next_id);next_id+=1;g=None if g in (None,'','\0') else g;t=dict(s=s,p=p,o=o,graph=g)
   state['rels'][id]=dict(**t,quals=q);by[(s,p,o,g)]=id;records.append(rec('create_rel','rel',id,new=json.dumps(t,separators=(',',':'),sort_keys=True),graph=g))
   records.extend(rec('set_qual','rel',id,key,new=val,graph=g) for key,val in sorted(q.items()))
 for i,r in enumerate(records,1):r['ordinal']=i
 return dict(error=None,state=state,records=records,by_tuple=by,next=next_id)

def adopt(ids,record):
 ids=copy.deepcopy(ids);r=copy.deepcopy(record)
 if r['op']=='create_rel':
  t=json.loads(r['new']);key=(t['s'],t['p'],t['o'],None if t.get('graph') in (None,'','\0') else t['graph'])
  id=ids['tuples'].get(key)
  if id is None:
   id=str(ids['next']);ids['next']+=1;ids['tuples'][key]=id;ids['statements'][id]=key
  r.update(entity_id=id,entity_kind='rel',attr='',prior=None,graph=t.get('graph'),flags=['adoption'])
 elif r['op']=='delete_rel':
  t=ids['statements'].get(r['entity_id'])
  if t is not None:ids['tuples'].pop(t,None)
  r.update(attr='',new=None,flags=['adoption'])
 else:r['flags']=['adoption']
 return ids,r
