"""Read-only independent audit of frozen root native files; never imports them."""
import ast,datetime,hashlib,json,math,re
from fractions import Fraction
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inputs(d,alias=None,strict=True):
 out={}
 for raw,want in d['inputs'].items():
  p=Path(raw) if Path(raw).is_absolute() else ROOT/raw
  if alias and raw in alias:p=alias[raw]
  out[raw]={'observed_file':str(p),'equal':sha(p)==want,'expected_sha256':want,'current_sha256':sha(p)}
  if strict:assert out[raw]['equal'],(raw,p)
 return out

def source(d):
 out={}
 for raw,want in d['source_inputs'].items():
  eq=sha(ROOT/raw)==sha(PIN/raw)==want;identity=d['source_identities'][raw]
  assert eq and identity['export_equals'] and identity['current_equals']
  out[raw]={'pin_export_current_sha_equal':eq,'recorded_pin_blob':identity['pin_blob']}
 return out

v=json.loads((HERE/'root-vector-native.json').read_text());assert v['verdict']=='AGREES' and v['failure'] is None and v['completed_cases']==len(v['cases'])==13 and v['identity_checked']
vs=source(v);vi=inputs(v);vector=[]
for c in v['cases']:
 sql=c['sql'];score=[x for x in sql if 'VECTOR_COSINE' in x['sql'].upper()]
 reads=[x for x in sql if 'SELECT' in x['sql'].upper() and re.search(r'\bEMB\b',x['sql'].upper()) and not any(k in x['sql'].upper() for k in ['DICTIONARY','INFORMATION_SCHEMA'])]
 catalogs=[x for x in sql if any(k in x['sql'].upper() for k in ['DICTIONARY','INFORMATION_SCHEMA'])]
 assert (len(score),len(reads),len(catalogs))==(c['score_calls'],c['vector_read_calls'],c['catalog_calls'])
 label=c['label'];guard='wrong-width' in label or 'absent named pair' in label or label in ['empty literal width0','IVF no route']
 if guard:assert not score and not reads and not catalogs and not c['native']
 if 'wrong-width' in label:assert c['error']['type']=='ValueError' and '3 dimensions' in c['error']['message'] and '4-dimensional' in c['error']['message']
 if 'absent named pair' in label or label=='seed excludes only stored self':assert c['result']==[] and c['error'] is None
 if label.startswith('primary admitted '):assert c['result']==[[v['node'],1.0]]
 if label=='seed includes distinct peer':assert len(c['result'])==1 and c['result'][0][0]!=v['node'] and abs(c['result'][0][1]-1/math.sqrt(2))<1e-12
 if label=='after other engine ordinary create':assert len(c['result'])==1 and c['result'][0][1]==1
 vector.append({'label':label,'score_calls':len(score),'vector_read_calls':len(reads),'catalog_calls':len(catalogs),'guard_before_scoring':guard,'agrees':True})
assert v['catalog_width']==4 and any('LEN,4,' in str(row) for e in v['catalog_trace'] for row in e['rows'])
old=json.loads((HERE/'root-vector-attempt1.json').read_text());assert old['verdict']=='DISAGREES_OR_INCOMPLETE' and old['failure'] is not None
attempt_alias={str((HERE/'root-vector-native.py').relative_to(ROOT)):HERE/'root-vector-attempt1.py'}
oi=inputs(old,attempt_alias,strict=False);assert oi[str((HERE/'root-vector-native.py').relative_to(ROOT))]['equal'];seed=next(c for c in old['cases'] if c['label'].startswith('primary admitted vec11:seed:'));assert seed['result']==[]
observer_misses=[]
for c in old['cases']:
 old_counter=[e for e in c['sql'] if 'SELECT' in e['sql'].upper() and 'EMB' in e['sql'].upper()]
 fields=[e for e in c['sql'] if 'SELECT' in e['sql'].upper() and re.search(r'\bEMB\b',e['sql'].upper()) and not any(k in e['sql'].upper() for k in ['DICTIONARY','INFORMATION_SCHEMA'])]
 if len(old_counter)!=len(fields):observer_misses.append({'label':c['label'],'substring_count':len(old_counter),'field_count':len(fields)})
assert observer_misses

f=json.loads((HERE/'root-fraction-native.json').read_text());assert f['verdict']=='AGREES' and f['failure'] is None and f['completed_cases']==f['scheduled_cases']==len(f['cases'])==22 and f['identity_checked']
fs=source(f);fi=inputs(f)
tree=ast.parse((HERE/'root-fraction-native.py').read_text());fixtures=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FIXTURES' for t in n.targets)))
def eff(raw):return Fraction(raw) if raw is not None and Fraction(raw)>0 else Fraction(1)
def edge_set(rows,direction,preds):
 out=[]
 for u,p,v,w in rows:
  if preds and p not in preds:continue
  if direction in ['out','both']:out.append((u,p,v,eff(w)))
  if direction in ['in','both']:out.append((v,p,u,eff(w)))
 return out
def minimum(raw,s,t,h,cap,direction,preds):
 es=edge_set(raw,direction,preds);nodes={s,t}|{u for u,p,v,w in es}|{v for u,p,v,w in es};bound=min(h,len(nodes)-1) if h else len(nodes)-1
 current={s:Fraction(0)};best=Fraction(0) if s==t else None
 for step in range(bound):
  nxt={}
  for u,p,v,w in es:
   if u in current and current[u]+w<=cap:
    candidate=current[u]+w;nxt[v]=candidate if v not in nxt else min(nxt[v],candidate)
  if t in nxt:best=nxt[t] if best is None else min(best,nxt[t])
  current=nxt
 return best
fraction=[]
for c in f['cases']:
 fixture=c['fixture'];es=fixtures[fixture];want=minimum(es,c['source'],c['target'],c['hops'],Fraction(c['cap']),c['direction'],c['predicates']);wantfloat=None if want is None else float(want)
 assert c['expected_exact']==(None if want is None else str(want)) and c['cost_only']==wantfloat
 assert c['public_rows']==([] if want is None else [[wantfloat]])
 path=c['path']
 if want is None:assert path=={}
 else:
  ns,ps,cs=path['nodes'],path['rels'],path['costs'];prefix='frac11:'+fixture+':'
  assert ns[0]==prefix+c['source'] and ns[-1]==prefix+c['target'] and len(ns)-1==len(ps)==len(cs)==path['length']
  assert not c['hops'] or path['length']<=c['hops'];assert sum(cs)==path['totalCost']==wantfloat
  assert isinstance(path['totalCost'],float) and all(isinstance(x,float) for x in cs)
  chosen=edge_set(es,c['direction'],c['predicates'])
  assert all(any((prefix+u,p,prefix+v,float(w))==(a,pred,b,wc) for u,p,v,w in chosen) for a,pred,b,wc in zip(ns,ps,ns[1:],cs))
 fraction.append({'fixture':fixture,'hops':c['hops'],'cap':c['cap'],'direction':c['direction'],'predicates':c['predicates'],'independent_dp_minimum':str(want) if want is not None else None,'agrees':True})
for p in f['points']:
 want=eff(p['raw_weight']);assert eff(str(p['out']))==eff(str(p['reverse']))==want and p['agrees']
result={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'READ_ONLY_AUDIT_AGREES','native_executed_by_reviewer':0,'candidate_inspection':False,'vector':{'count':13,'cases':vector,'source':vs,'inputs':vi,'retained_attempt':{'verdict':old['verdict'],'seed_self_empty_refuted_expectation':True,'observer_substring_misses':observer_misses,'inputs_with_original_source_alias':oi,'retained_old_prediction_bytes_available':all(x['equal'] for x in oi.values())},'scope':'Finite ordinary route/vector writers and actual SQL final readers; effect observer correct for recorded SQL fields. Client kernel/embedded scoring generic effects not measured by these native traces; source guards, not observer alone, establish their absence in these cases. No metadata fault/TTL/outage/provider generalization.'},'fraction':{'count':22,'points':len(f['points']),'cases':fraction,'source':fs,'inputs':fi,'scope':'Independent exact dynamic programming/path validity audit of frozen native records. Ordinary omitted input weight writes actual1.0 scalar here; absent scalar on present coordinate not directly sampled. All dyadic arithmetic, no arbitrary Double proof, no native internal BestHop instrumentation. Connections closed; task-owned fresh fixture graphs remain root-owned, no cleanup/erase is claimed.'},'artifacts':{str(p.relative_to(ROOT)):sha(p) for stem in ['root-vector-native','root-vector-attempt1','root-fraction-native'] for ext in ['.py','.json','.log'] if (p:=HERE/(stem+ext)).is_file()}}
(HERE/'review-native-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'verdict':result['verdict'],'vector':13,'fraction':22,'points':len(f['points']),'retained_observer_misses':len(observer_misses),'native_executed':0}))
