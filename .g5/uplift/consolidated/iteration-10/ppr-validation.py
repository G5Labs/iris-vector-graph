"""Read-only final receipt/freshness/name-local failure audit, no verifier replay."""
import datetime,hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];V=ROOT/'.g5/Verus_verification';MODEL=V/'models/ppr_walk';manifest=json.loads((MODEL/'model.json').read_text());pool=[]
for p in sorted((V/'results/ppr_walk').glob('*/receipt.json')):pool.append((p,json.loads(p.read_text())))
def latest(kind,name=None):
 pairs=[(p,d) for p,d in pool if d.get('kind')==kind and (name is None or d.get('control',{}).get('name')==name)]
 assert pairs,(kind,name)
 return pairs[-1]
chosen=[latest('proof')]+[latest('control',c['name']) for c in manifest['controls']]+[latest('binding')];rows=[]
for p,d in chosen:
 f=subprocess.run([sys.executable,str(V/'run_verus.py'),'fresh',str(p)],capture_output=True,text=True,cwd=ROOT)
 row={'receipt':str(p.relative_to(ROOT)),'kind':d['kind'],'verdict':d['verdict'],'fresh':f.returncode==0,'fresh_stdout':f.stdout.strip()}
 assert row['fresh'],row
 if d['kind']=='proof':assert d['verdict']=='PASS' and d['observed']['verified']==manifest['expected_verified'] and d['observed']['errors']==0
 if d['kind']=='control':
  assert d['verdict']=='EXPECTED_FAIL',(p,d['verdict']);row['control']=d['control']['name'];row['whole_mutant_resource_limit']=d['observed'].get('has_resource_limit',False);row['named']={}
  for name,obs in d['observed']['per_function'].items():
   text=Path(obs['raw_log']).read_text();clean=obs['errors']>0 and not obs['timed_out'] and 'Resource limit' not in text and 'rlimit' not in text.lower() and bool(re.search(r'(assertion failed|postcondition not satisfied)',text))
   row['named'][name]={'errors':obs['errors'],'clean_deciding_failure':clean,'log':obs['raw_log']};assert clean,(p,name,text)
 if d['kind']=='binding':
  assert d['verdict']=='AGREES' and d['cases']==450 and not d['mismatch_count'] and d['blocked_socket_calls']==0 and all(d['detection'].values())
  assert len(d['error_neighbors'])==6 and len(d['refused_neighbors'])==13 and len(d['wrapper_reader_cases'])==9
  assert {k:v['count'] for k,v in d['root_native_supplements'].items()}=={'tie':6,'cap':4,'reverse5':5}
 rows.append(row)
# Raw copied logs are immutable receipt artifacts as well.
for p,d in chosen:
 for rel,digest in d.get('raw_log_copies',{}).items():assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest
result={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_fresh_expected':True,'selected_receipts':len(rows),'verifier_units':manifest['expected_verified'],'declared_controls':len(manifest['controls']),'receipts':rows,'scope':'Latest exact final input hashes; named controls have ordinary post/assert failures, no resource/parse/type-only credit. Native facts read/hash-audited in binding, never run here.'}
q=Path(__file__).with_suffix('.json');q.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='receipts'}))
