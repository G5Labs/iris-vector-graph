"""Read-only audit of root-owned native marker facts. Never imports native helpers."""
from pathlib import Path
import datetime,hashlib,json,time
REPO=Path('/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph');HERE=Path(__file__).resolve().parent
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
start=time.monotonic();p=HERE/'root-ledger-marker-native.json';j=json.loads(p.read_text());checks=[]
def check(label,ok):
 checks.append(dict(label=label,passed=bool(ok)));assert ok,label
check('six completed source-forecast cases',j['completed_cases']==6 and len(j['cases'])==6 and j['failure'] is None and j['verdict']=='AGREES_SOURCE_FORECAST' and all(x['agrees'] for x in j['cases']))
for rel,h in j['inputs'].items():check('input current '+rel,sha(REPO/rel)==h)
for rel,h in j['source_inputs'].items():check('source current/pin '+rel,sha(REPO/rel)==sha(PIN/rel)==h)
rs=j['revisions'];check('four recorded successful ordinary revisions',len(rs)==4)
a,b=[o['id'] for o in rs[0]['ops']];check('raw node producer expansion',[(r['op'],r['entity_id'],r['new']) for r in rs[0]['records']]==[('create_node',a,''),('create_node',b,'')])
states={};source_effects=[]
for rv in rs[1:]:
 op=rv['ops'][0];t=op['tuple'];qs=op['quals'];rid=rv['stmt_ids']['0'];records=rv['records'];old=[(i,e) for i,e in states.items() if e['p']==t['p']]
 adopts=bool(old) and old[-1][1]['quals'].get('temporal')=='true'
 check('ordinary create first-or-marker-adopt '+rid,not old or adopts)
 check('new identity not reused '+rid,rid not in states)
 expected=[('create_rel','',None,t)]+[('set_qual',k,None,v) for k,v in sorted(qs.items())]
 observed=[(r['op'],r['attr'],r['prior'],json.loads(r['new']) if r['op']=='create_rel' else r['new']) for r in records]
 check('derived complete record expansion '+rid,observed==expected and all(r['entity_id']==rid for r in records))
 states[rid]={**t,'quals':dict(qs)};source_effects.append(dict(id=rid,adopts=adopts,source_quals=qs,records=len(records)))
false,first,second=source_effects
check('false ordinary create refuses and head stable',j['cases'][0]['actual']==dict(error=dict(type='ChangesetOperationError',existing=True),unchanged_head=True))
check('true caller row selected adoption',not false['adopts'] and not first['adopts'] and second['adopts'])
want={i:e for i,e in states.items() if e['p']=='MARK_TRUE'}
check('named replay keeps both derived full statement contents',j['cases'][2]['actual']==want and len(want)==2)
check('tuple final writer selects new identity',j['cases'][3]['actual']==second['id'])
check('one physical row has replacement not merged quals',j['cases'][4]['actual']==[second['source_quals']])
raw=HERE/('root-ledger-marker-'+j['prefix'].split(':')[1]+'.ndjson');lines=[json.loads(s) for s in raw.read_text().splitlines()]
selected={r['stmt_id']:{k:r[k] for k in ['s','p','o','graph','quals']} for r in lines if r.get('type')=='rel' and r.get('s')==a and r.get('p')=='MARK_TRUE'}
check('raw NDJSON complete fields retain both identities',selected==want and j['cases'][5]['actual']==sorted(want))
check('ledger disabled at end; task data retained',j['before_meta']['state']==j['after_meta']['state']=='disabled' and j['after_meta']['head_seq']==rs[-1]['revision']['seq'])
out=dict(verdict='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_forecast='review-ledger-marker-intent.json',checks=checks,derived_source_effects=source_effects,derived_statement_map=states,inputs={str(x.relative_to(REPO)):sha(x) for x in [Path(__file__),p,HERE/'root-ledger-marker-native.py',HERE/'root-ledger-marker-native.log',HERE/'root-ledger-marker-predictions.md',raw,HERE/'review-ledger-marker-intent.json']},native_completed_cases=6,source_records=sum(len(x['records']) for x in rs),reviewer_native_calls=0,reviewer_network_calls=0,elapsed_s=time.monotonic()-start,disposition='Strengthen inherited caller-marker root F-C0351 and cross-reference inconsistent-marker F-0505/F-C0450; exact effect is newly observed ordinary reachability, no separate new root count recommended.',limits=['Finite root-owned prefix only; current/export source hashes corroborated, no native-body proof.','Setup5 deployment/identity evidence reused rather than rerun.','Boolean caller normalization source-inspected; native panel directly used text true/false.','Named here is a revision cutoff, not a named graph; all probe relationships default graph.','No temporal writer, injected failure, native reviewer execution, cleanup claim or policy/repair assumed.'])
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(verdict=out['verdict'],checks=len(checks),records=out['source_records'],elapsed_s=out['elapsed_s'],native_calls=0)))
