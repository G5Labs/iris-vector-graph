"""Executing SQLite transcription of inspected LedgerApply/record ports.
No ObjectScript/native execution. SQL/null/tuple/provider limits are explicit.
"""
import json,sqlite3
from types import SimpleNamespace
class OpError(Exception):pass
class CarrierError(Exception):pass

def graph(g):return '' if g in (None,'','\0') else str(g)
def text(v):return '' if v is None else str(v)

class Cursor:
 def __init__(self,p):self.p=p;self.c=p.db.cursor()
 def execute(self,sql,args=()):
  self.p.reads.append((sql,list(args)))
  if '.ledger_records(' in sql:
   seq,end,ordinal,size=args
   sql='SELECT * FROM records WHERE seq>=? AND seq<=? AND (seq>? OR ordinal>=?) ORDER BY seq,ordinal LIMIT ?'
   args=(seq,end,seq,ordinal,min(size,self.p.page))
  else:sql=sql.replace('Graph_KG.ledger_revisions','revisions')
  self.c.execute(sql,args);return self
 def fetchone(self):return self.c.fetchone()
 def fetchall(self):return self.c.fetchall()
 def close(self):self.c.close()

class Connection:
 def __init__(self,p):self.p=p
 def cursor(self):return Cursor(self.p)

class Provider:
 def __init__(self,bound=100,page=2,mutant=None):
  self.db=sqlite3.connect(':memory:');self.db.execute('PRAGMA foreign_keys=ON');self.bound=bound;self.page=page;self.mutant=mutant
  self.next=1;self.seq=1;self.reads=[];self.calls=[]
  self.db.executescript('''CREATE TABLE nodes(id TEXT PRIMARY KEY);CREATE TABLE registrations(g TEXT,id TEXT,PRIMARY KEY(g,id));
 CREATE TABLE labels(s TEXT,label TEXT,PRIMARY KEY(s,label),FOREIGN KEY(s) REFERENCES nodes(id));
 CREATE TABLE props(s TEXT,k TEXT,v TEXT,PRIMARY KEY(s,k),FOREIGN KEY(s) REFERENCES nodes(id));
 CREATE TABLE edges(sid INTEGER PRIMARY KEY,s TEXT,p TEXT,o TEXT,g TEXT,q TEXT);
 CREATE TABLE revisions(seq INTEGER PRIMARY KEY,revision_id TEXT,parent_id TEXT,kind TEXT,actor TEXT,actor_type TEXT,conn_user TEXT,committed_ms INTEGER,message TEXT,source TEXT,correlation_id TEXT,idempotency_key TEXT,op_count INTEGER);
 CREATE TABLE records(seq INTEGER,ordinal INTEGER,op TEXT,entity_kind TEXT,entity_id TEXT,attr TEXT,prior TEXT,prior_null INTEGER,"new" TEXT,new_null INTEGER,graph TEXT,flags TEXT,digest TEXT,redacted_op TEXT);''')
  self.write_revision(1,[],0)
  self.conn=Connection(self)
 def write_revision(self,seq,records,count):
  vals=(seq,str(seq),str(seq-1),'changeset','binding','system','sqlite',seq,None,None,None,None,count)
  self.db.execute('INSERT INTO revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',vals)
  for i,r in enumerate(records,1):
   op,kind,eid,attr,prior,new,g,flags=r
   self.db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(seq,i,op,kind,str(eid),attr,prior,int(prior is None),new,int(new is None),g,flags,None,None))
  return dict(zip(['seq','revision_id','parent_id','kind','actor','actor_type','conn_user','committed_ms','message','source','correlation_id','idempotency_key','op_count'],vals))
 def classMethodValue(self,cls,method,*args):
  self.calls.append((cls,method,args))
  if cls=='Graph.KG.Meta':return '0'
  if method=='InProgress':return json.dumps({'in_progress':False})
  if method=='Meta':return json.dumps({'state':'enabled','head_seq':self.seq,'recon_bound':self.bound})
  if method=='SeqOf':
   r=self.db.execute('SELECT seq FROM revisions WHERE revision_id=?',(str(args[0]),)).fetchone()
   return json.dumps({'ok':bool(r),'seq':r[0] if r else None})
  if method=='Commit':return json.dumps(self.commit(json.loads(args[0]),json.loads(args[1])))
  raise AssertionError((cls,method,args))
 def emit(self,op,kind,eid,attr='',prior=None,new=None,g=None,flags=''):
  self.buffer.append((op,kind,str(eid),attr,prior,new,None if not graph(g) else graph(g),flags))
 def exists(self,n):return self.db.execute('SELECT 1 FROM registrations WHERE id=?',(n,)).fetchone() is not None
 def node_snapshot(self,n):
  labels=[x[0] for x in self.db.execute('SELECT label FROM labels WHERE s=? ORDER BY label',(n,))]
  props=dict(self.db.execute("SELECT k,v FROM props WHERE s=? AND k NOT IN ('id','__graph') ORDER BY k",(n,)))
  return json.dumps(dict(labels=labels,props=props),sort_keys=True,separators=(',',':'))
 def label(self,n,k,remove=False):
  if not self.exists(n):raise OpError('node_not_found')
  if not remove and not k:raise OpError('label is required')
  old=self.db.execute('SELECT 1 FROM labels WHERE s=? AND label=?',(n,k)).fetchone()
  if remove:
   if not old:raise OpError('label_not_present')
   self.db.execute('DELETE FROM labels WHERE s=? AND label=?',(n,k));self.emit('remove_label','node',n,k,'',None)
  elif not old:
   self.db.execute('INSERT INTO labels VALUES (?,?)',(n,k));self.emit('add_label','node',n,k,None,'')
 def prop(self,n,k,v=None,remove=False):
  if k in ('id','__graph'):raise OpError('reserved_property')
  if not self.exists(n):raise OpError('node_not_found')
  if not remove and not k:raise OpError('property key is required')
  old=self.db.execute('SELECT v FROM props WHERE s=? AND k=?',(n,k)).fetchone()
  if remove:
   if not old:raise OpError('property_not_present')
   self.db.execute('DELETE FROM props WHERE s=? AND k=?',(n,k));self.emit('remove_prop','node',n,k,old[0],None)
  elif not old or old[0]!=v:
   self.db.execute('INSERT OR REPLACE INTO props VALUES (?,?,?)',(n,k,v))
   self.emit('set_prop','node',n,k,None if self.mutant=='discard-prior' else (old[0] if old else None),v)
 def edge(self,sid):return self.db.execute('SELECT sid,s,p,o,g,q FROM edges WHERE sid=?',(sid,)).fetchone()
 def resolve(self,ref):
  if 'op_ref' in ref:sid=self.opids[ref['op_ref']]
  elif 'stmt_id' in ref:sid=int(ref['stmt_id'])
  else:
   t=ref['tuple'];row=self.db.execute('SELECT sid FROM edges WHERE s=? AND p=? AND o=? AND g=?',(t['s'],t['p'],t['o'],graph(t.get('graph')))).fetchone()
   if not row:raise OpError('relationship not found')
   sid=row[0]
  if sid in self.dead_rels:raise OpError('statement was deleted earlier')
  row=self.edge(sid)
  if not row:raise OpError('statement unknown')
  return row
 def numeric(self,v):
  import re
  return bool(re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',v))
 def quals(self,row,new,replace=False):
  sid,s,p,o,g,oldjson=row;old=json.loads(oldjson)
  if 'weight' in new and not self.numeric(new['weight']):raise OpError('weight must be numeric')
  if '' in new:raise CarrierError('<SUBSCRIPT> MergeQuals tKeys()')
  if replace:
   for k in sorted(old):
    if k not in new:self.emit('remove_qual','rel',sid,k,old.pop(k),None,g)
  for k,v in sorted(new.items()):
   if k not in old or old[k]!=v:
    self.emit('set_qual','rel',sid,k,old.get(k),v,g);old[k]=v
  self.db.execute('UPDATE edges SET q=? WHERE sid=?',(json.dumps(old,sort_keys=True),sid))
 def delete_rel(self,row):
  sid,s,p,o,g,q=row
  snap=json.dumps(dict(s=s,p=p,o=o,graph=graph(g) or None,quals=json.loads(q)),sort_keys=True,separators=(',',':'))
  self.db.execute('DELETE FROM edges WHERE sid=?',(sid,));self.emit('delete_rel','rel',sid,prior=snap,g=g);self.dead_rels.add(sid)
 def operation(self,op,i):
  kind=op['op'];n=op.get('id');k=op.get('key')
  if n in self.dead_nodes:raise OpError('node was deleted earlier')
  if kind in ('create_node','upsert_node'):
   if not n:raise OpError('node id required')
   existed=self.exists(n)
   if existed and kind=='create_node':raise OpError('node_exists')
   props=op.get('props') or {}
   if any(k in ('id','__graph') for k in props):raise OpError('reserved_property')
   if not existed:
    self.db.execute('INSERT INTO nodes VALUES (?)',(n,));self.db.execute("INSERT INTO registrations VALUES ('',?)",(n,));self.emit('create_node','node',n,new='')
   for label in op.get('labels') or []:self.label(n,label)
   for key,v in props.items():self.prop(n,key,text(v))
  elif kind in ('add_label','remove_label'):self.label(n,op['label'],kind=='remove_label')
  elif kind in ('set_prop','remove_prop'):self.prop(n,k,text(op.get('value')),kind=='remove_prop')
  elif kind in ('create_rel','upsert_rel'):
   t=op['tuple'];s,p,o=t['s'],t['p'],t['o'];g=graph(t.get('graph'));qs=op.get('quals') or {}
   if not s or not p or not o:raise OpError('tuple requires s p o')
   if s in self.dead_nodes or o in self.dead_nodes:raise OpError('endpoint was deleted earlier')
   if not self.exists(s) or not self.exists(o):raise OpError('node_not_found')
   if 'weight' in qs and not self.numeric(text(qs['weight'])):raise OpError('weight must be numeric')
   found=self.db.execute('SELECT sid,s,p,o,g,q FROM edges WHERE s=? AND p=? AND o=? AND g=?',(s,p,o,g)).fetchone()
   if found:
    if kind=='create_rel':raise OpError('relationship_exists')
    self.quals(found,qs);sid=found[0]
   else:
    if '' in qs:raise CarrierError('<SUBSCRIPT> QualsJson tKeys()')
    for endpoint in [s,o]:self.db.execute('INSERT OR IGNORE INTO registrations VALUES (?,?)',(g,endpoint))
    sid=self.next;self.next+=1
    self.db.execute('INSERT INTO edges VALUES (?,?,?,?,?,?)',(sid,s,p,o,g,json.dumps(qs,sort_keys=True)))
    self.emit('create_rel','rel',sid,new=json.dumps(dict(s=s,p=p,o=o,graph=g or None),sort_keys=True,separators=(',',':')),g=g)
    for key,v in sorted(qs.items()):self.emit('set_qual','rel',sid,key,None,v,g)
   self.opids[i]=sid
  elif kind=='delete_rel':self.delete_rel(self.resolve(op['ref']))
  elif kind in ('set_qual','remove_qual','replace_quals'):
   row=self.resolve(op['ref'])
   if kind=='replace_quals':self.quals(row,op.get('quals') or {},True)
   else:
    if not k:raise OpError('qualifier key required')
    if kind=='set_qual':self.quals(row,{k:text(op.get('value'))})
    else:
     q=json.loads(row[5])
     if k not in q:raise OpError('qualifier_not_present')
     old=q.pop(k);self.db.execute('UPDATE edges SET q=? WHERE sid=?',(json.dumps(q),row[0]));self.emit('remove_qual','rel',row[0],k,old,None,row[4])
  elif kind=='delete_node':
   if not self.exists(n):raise OpError('node_not_found')
   incident=self.db.execute("SELECT sid,s,p,o,g,q FROM edges WHERE g='' AND (s=? OR o=?) ORDER BY sid",(n,n)).fetchall()
   if incident and op.get('mode','strict')!='detach':raise OpError('node_has_relationships')
   for row in incident:self.delete_rel(row)
   snapshot=self.node_snapshot(n)
   self.db.execute('DELETE FROM labels WHERE s=?',(n,));self.db.execute('DELETE FROM props WHERE s=?',(n,));self.db.execute('DELETE FROM nodes WHERE id=?',(n,));self.db.execute("DELETE FROM registrations WHERE g='' AND id=?",(n,))
   self.emit('delete_node','node',n,prior=snapshot);self.dead_nodes.add(n)
  else:raise OpError('unknown_operation')
 def commit(self,wire,meta):
  oldnext=self.next;self.buffer=[];self.dead_nodes=set();self.dead_rels=set();self.opids={};self.db.execute('SAVEPOINT ordinary')
  try:
   for i,op in enumerate(wire['ops']):self.operation(op,i)
   seq=self.seq+1;rev=self.write_revision(seq,self.buffer,len(wire['ops']));self.seq=seq;self.db.execute('RELEASE ordinary')
   return dict(ok=True,revision=rev,replayed=False,stmt_ids={str(k):str(v) for k,v in self.opids.items()})
  except Exception as e:
   self.db.execute('ROLLBACK TO ordinary');self.db.execute('RELEASE ordinary');self.next=oldnext
   if isinstance(e,CarrierError):raise
   return dict(ok=False,error='failed_op',reason=str(e),op_index=i)
