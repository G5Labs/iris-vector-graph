"""Read-only independent audit of frozen root native facts; no native imports/calls."""
import copy,datetime,hashlib,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def graph(g):return None if g in (None,'','\x00') else str(g)
def snap(n):return dict(labels=sorted(n['labels']),props=dict(n['props']))
def norm(s):return dict(nodes={k:snap(v) for k,v in s['nodes'].items()},rels=copy.deepcopy(s['rels']))
def js(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
start=time.perf_counter();path=HERE/'root-ledger-native.json';r=json.loads(path.read_text())
assert r['verdict']=='AGREES' and r['completed_cases']==22 and r['failure'] is None
assert r['identity_checked'] and not r['genesis_native_executed'] and r['enable']['kind']=='adoption' and r['after_meta']['state']=='disabled'
assert all(x['prediction_agrees'] and x['actual']==x['expected'] for x in r['cases'])
sources={}
for rel,h in r['source_inputs'].items():
 data=(ROOT/rel).read_bytes();assert sha(ROOT/rel)==sha(PIN/rel)==h
 blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();assert blob==r['source_identities'][rel]['pin_blob']
 sources[rel]=dict(sha256=h,pin_export_current_equal=True,git_blob_calculated_without_git=blob)
for rel,h in r['inputs'].items():assert sha(ROOT/rel)==h
state=dict(nodes={},rels={});physical=set();bytuple={};seenids=set();states={};opchecks=[];allrecords=[]
def emit(op,kind,eid,attr='',prior=None,new=None,g=None):return dict(op=op,entity_kind=kind,entity_id=eid,attr=attr,prior=prior,new=new,graph=g,flags=[])
def label(nid,value,add):
 n=state['nodes'][nid];exists=value in n['labels']
 if add:
  if exists:return []
  n['labels'].add(value);return [emit('add_label','node',nid,value,new='')]
 assert exists;n['labels'].remove(value);return [emit('remove_label','node',nid,value,prior='')]
def prop(nid,key,value):
 assert value is not None and key not in ['id','__graph']
 n=state['nodes'][nid];prior=n['props'].get(key)
 if prior==value and key in n['props']:return []
 n['props'][key]=value;return [emit('set_prop','node',nid,key,prior,value)]
def qual(sid,key,value):
 assert value is not None;s=state['rels'][sid];prior=s['quals'].get(key)
 if prior==value and key in s['quals']:return []
 s['quals'][key]=value;return [emit('set_qual','rel',sid,key,prior,value,s['graph'])]
for revision in r['revisions']:
 seq=revision['revision']['seq'];want=[]
 for i,op in enumerate(revision['ops']):
  tag=op['op']
  if tag in ['create_node','upsert_node']:
   nid=op['id'];exists=any(x==nid for x,g in physical)
   if tag=='create_node':assert not exists
   if not exists:state['nodes'][nid]=dict(labels=set(),props={});physical.add((nid,None));want.append(emit('create_node','node',nid,new=''))
   assert nid in state['nodes'],'Ordinary-prefix audit needs live default content; named-only upsert outside this finite panel'
   for x in op.get('labels',[]):want+=label(nid,x,True)
   for k,v in sorted(op.get('props',{}).items()):want+=prop(nid,k,v)
  elif tag in ['set_prop','add_label','remove_label']:
   nid=op['id'];assert nid in state['nodes']
   if tag=='set_prop':want+=prop(nid,op['key'],op['value'])
   else:want+=label(nid,op['label'],tag=='add_label')
  elif tag in ['create_rel','upsert_rel']:
   t={**op['tuple'],'graph':graph(op['tuple'].get('graph'))};key=(t['s'],t['p'],t['o'],t['graph']);sid=bytuple.get(key)
   assert all(any(n==nid for n,g in physical) for nid in [t['s'],t['o']])
   if sid is None:
    sid=revision['stmt_ids'][str(i)];assert sid not in seenids;seenids.add(sid);bytuple[key]=sid
    state['rels'][sid]=dict(**t,quals={});physical.add((t['s'],t['graph']));physical.add((t['o'],t['graph']))
    want.append(emit('create_rel','rel',sid,new=js(t),g=t['graph']))
   else:assert tag=='upsert_rel'
   for k,v in sorted(op.get('quals',{}).items()):want+=qual(sid,k,v)
  elif tag=='set_qual':want+=qual(op['ref']['stmt_id'],op['key'],op['value'])
  elif tag=='delete_rel':
   sid=op['ref']['stmt_id'];s=state['rels'].pop(sid);bytuple.pop((s['s'],s['p'],s['o'],s['graph']),None)
   want.append(emit('delete_rel','rel',sid,prior=js(s),g=s['graph']))
  elif tag=='delete_node':
   nid=op['id'];assert op['mode']=='strict' and not any(s['graph'] is None and nid in [s['s'],s['o']] for s in state['rels'].values())
   n=state['nodes'].pop(nid);physical.discard((nid,None));want.append(emit('delete_node','node',nid,prior=js(snap(n))))
  else:raise AssertionError('Unassessed native fixture operation '+tag)
 actual=revision['records'];assert revision['revision']['op_count']==len(actual)==len(want)
 for ordinal,(a,b) in enumerate(zip(actual,want),1):
  assert a['seq']==seq and a['ordinal']==ordinal
  got={k:a[k] for k in b}
  for k in ['prior','new']:
   if b['op']=='create_rel' and k=='new' or b['op'] in ['delete_rel','delete_node'] and k=='prior':got[k]=json.loads(got[k]);b[k]=json.loads(b[k])
  assert got==b,(seq,ordinal,got,b)
 opchecks.append(dict(seq=seq,operations=len(revision['ops']),records=len(actual),derived_expansion_priors_snapshots_agree=True));states[seq]=norm(state);allrecords+=actual
cases={c['label']:c['actual'] for c in r['cases']};seqs=sorted(states)
assert states[seqs[1]]==cases['existing upsert preserves unspecified full content']==cases['continuous-life restored complete content']==cases['earlier named cutoff retains complete content']==cases['earlier cutoff eager stream complete content']
prefix=r['prefix'];a=prefix+'a';named=prefix+'named-source';last=states[seqs[-1]]
assert named not in last['nodes'] and any(s['s']==named and s['graph']==r['named_graph'] for s in last['rels'].values()) and (named,r['named_graph']) in physical
assert cases['surviving named registration refuses ordinary create']==dict(type='ChangesetOperationError',node_exists=True)
startnode=states[seqs[1]]['nodes'][a];deletion=[x for x in allrecords if x['op']=='delete_node' and x['entity_id']==a][0];deletionsnapshot=json.loads(deletion['prior'])
assert deletionsnapshot==cases['known rich lifecycle reverse uses deletion-time snapshot'] and deletionsnapshot!=startnode
# Continuous life: first prior and final new across r2->r4 are raw emitted values.
continuous=[x for x in allrecords if seqs[1]<x['seq']<=seqs[4]];attrs={}
for x in continuous:
 if x['op'] in ['set_prop','set_qual','add_label','remove_label']:
  k=(x['entity_kind'],x['entity_id'],x['attr']);before,after=attrs.get(k,(x['prior'],x['prior']));attrs[k]=(before,x['new'])
assert attrs and all(b==a for b,a in attrs.values()) and cases['continuous-life restored net diff empty']==[]
export=Path(r['export_summary']['path']);assert export.is_file();rows=[json.loads(x) for x in export.read_text().splitlines()];selected=[x for x in rows if str(x.get('id',x.get('s',''))).startswith(prefix)]
assert sorted(selected,key=js)==sorted(cases['earlier cutoff NDJSON full entities'],key=js)
old=HERE/'root-ledger-attempts/attempt-1';attempt=json.loads((old/'root-ledger-native.json').read_text());assert attempt['verdict']=='DISAGREES_OR_INCOMPLETE' and attempt['completed_cases']==16 and attempt['failure']
alias={'.g5/uplift/consolidated/iteration-12/root-ledger-native.py':old/'root-ledger-native.py','.g5/uplift/consolidated/iteration-12/root-ledger-predictions.md':old/'root-ledger-predictions.md'}
for rel,h in attempt['inputs'].items():assert sha(alias.get(rel,ROOT/rel))==h
out=dict(verdict='READ_ONLY_NATIVE_FACT_AUDIT_AGREES',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),native_executed=0,network_calls=0,candidate_inspection='No ledger_content candidate inspected',native_records=22,revision_expansion_checks=opchecks,raw_mutation_records=len(allrecords),sources=sources,inputs={str(p.relative_to(ROOT)):sha(p) for p in [path,HERE/'root-ledger-native.py',HERE/'root-ledger-native.log',HERE/'root-ledger-predictions.md',export,Path(__file__)]},known_lifecycle=dict(start=startnode,deletion=deletionsnapshot,distinct=True,root='bug-led-101',policy='q-con-002 remains open'),named_identity=dict(replay_absent=True,derived_physical_registration_present=True,actual_create_refusal=True,duplicate_root='Existing F-1105/HD1101, not a new issue'),retained_attempt1=dict(completed=16,failed=True,archival_input_hashes_verified=True,scope='Final extra named-create refusal is as-built discovery after original scenario miss, not22 new blind forecasts'),scope='Finite prefix-only semantic operation expansion/current-prior/snapshot/full-content audit over actual root native decoded records. Statement allocation IDs are observed nominal provider IDs, not a universal allocation proof. Raw SQL null rows/JSON bytes, native bodies, arbitrary coercion/transaction/fullgraph correctness, Genesis and unrestricted Admit histories unproved. Ledger disabled afterward; task-owned data retained, no cleanup/erase claim.',elapsed_s=time.perf_counter()-start)
HERE.joinpath('review-ledger-native-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['verdict','native_records','raw_mutation_records','native_executed','elapsed_s']}))
