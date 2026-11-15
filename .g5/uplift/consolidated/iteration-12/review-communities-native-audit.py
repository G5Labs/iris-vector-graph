"""Read-only audit of root census8 and disclosed/reused communities18 facts."""
import collections,datetime,hashlib,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
t=time.perf_counter();r=json.loads((HERE/'root-communities-census-native.json').read_text());oldpath=ROOT/'.g5/uplift/consolidated/iteration-11/next-communities-native.json';old=json.loads(oldpath.read_text())
assert r['verdict']=='AGREES' and r['completed_cases']==8 and r['failure'] is None and r['identity_checked']
# Derive expected prefix observations from the raw source-frozen fixture structure.
nodes={'a','b','iso','loop'};edges=[('a','R','b'),('loop','L','loop')]
loners={v:any(a==v for a,p,b in edges) for v in nodes if not any(a!=b and v in (a,b) for a,p,b in edges)}
labels={v:v for v in nodes}
while True:
 nxt={v:min([labels[v]]+[labels[b if a==v else a] for a,p,b in edges if v in (a,b)]) for v in nodes}
 if nxt==labels:break
 labels=nxt
cdlp={}
for v in nodes:
 bag=collections.Counter(b if a==v else a for a,p,b in edges if a!=b and v in (a,b))
 cdlp[v]=min(bag,key=lambda x:(-bag[x],x)) if bag else v
for i,case in enumerate(r['cases']):
 want=loners if i<6 else labels if i==6 else cdlp
 assert case['result']==case['expected']==want and case['agrees'] and case['error'] is None
 assert case['injected_census_failures']==(0 if i<4 else 1)
assert r['total_injected_census_failures']==4
for data in [r,old]:
 assert data['verdict']=='AGREES' and data['failure'] is None and data['identity_checked']
 for p,h in data['inputs'].items():assert sha(ROOT/p)==h
 for p,h in data['source_inputs'].items():assert sha(ROOT/p)==sha(PIN/p)==h
assert old['completed_cases']==18 and all(x['agrees'] for x in old['cases']) and old['cache_token_before_insert']==old['cache_token_after_insert']
names=['root-communities-census-predictions.md','root-communities-census-native.py','root-communities-census-native.json','root-communities-census-native.log']
out=dict(verdict='READ_ONLY_CENSUS_AND_REUSED_FACT_AUDIT_AGREES',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_native_records=8,reused_exposed_native_records=18,independently_derived_prefix=dict(loners=loners,wcc=labels,cdlp_one_round=cdlp),controlled_failures=4,driver_concern='Default DBAPI SQL census did not lose the isolate; native host-variable empty-to-NULL comments do not establish DBAPI parameter behavior. Concern refuted on this finite provider.',cache_fact='Reused18 isolate insertion leaves adjacency token equal while public completion remains current; not all-history cache freshness.',inputs={**{str((HERE/n).relative_to(ROOT)):sha(HERE/n) for n in names},str(oldpath.relative_to(ROOT)):sha(oldpath)},native_executed_by_reviewer=0,network_calls=0,new_issues=0,scope='Actual root-owned native/default+named SQL census and public reader observations, prefix-only. Fault adapter intercepts only LonersJson, delegates other calls and supplies no rows. No organic outage/native body/universal binding/collation/SQL-KG faithfulness/cleanup or cache writer proof. Existing data retained. Native18 is disclosed old evidence, not8+18 new runs.',elapsed_s=time.perf_counter()-t)
(HERE/'review-communities-native-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['verdict','new_native_records','reused_exposed_native_records','native_executed_by_reviewer','elapsed_s']}))
