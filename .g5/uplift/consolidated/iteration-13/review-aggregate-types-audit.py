"""Read-only audit of fresh ordinary typed native facts; no provider execution."""
from pathlib import Path
from fractions import Fraction
import json,hashlib,time,datetime
R=Path(__file__).resolve().parents[4];H=Path(__file__).resolve().parent;P=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');start=time.monotonic();checks=[];inputs={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):inputs[str(p.relative_to(R))]=sha(p);return p.read_text()
def ck(n,v):checks.append({'name':n,'passed':bool(v)});assert v,n
j=json.loads(read(H/'root-aggregate-types-native.json'));ck('four complete typed agreements',j['verdict']=='AGREES' and j['completed_cases']==4 and len(j['cases'])==4 and j['failure'] is None and j['identity_checked'])
for rel,h in j['inputs'].items():ck('flat input '+rel,sha(R/rel)==h);read(R/rel)
for rel,h in j['source_inputs'].items():ck('source current/export '+rel,sha(R/rel)==sha(P/rel)==h);read(R/rel)
for n in ['root-aggregate-types-native.log','root-aggregate-types-PAIRS.md','review-aggregate-expectations.md']:read(H/n)
f=j['fixture'];gs=list(dict.fromkeys(x['graph'] for x in f));ck('four unique fresh nodes/two scoped graphs',len(f)==4 and len(gs)==2 and len({(x['graph'],x['id']) for x in f})==4 and all(x['graph'].startswith('ordinary13types_') and x['id'].startswith('ordinary13types:') for x in f))
values=[[x['x'] for x in f if x['graph']==g] for g in gs];ck('raw kinds match actual typed inputs',all(type(v) is int for v in values[0]) and all(type(v) is float for v in values[1]))
sums=[sum(Fraction(str(x)) for x in vs) for vs in values];wants=[(int(sums[0]),'int'),(float(sums[1]),'float'),(float(sums[1]),'float'),(float(sums[1]/len(values[1])),'float')]
for i,(case,(v,t)) in enumerate(zip(j['cases'],wants)):
 ck(str(i)+' exact raw half-unit arithmetic and Python type',case['actual']==[[v]] and type(case['actual'][0][0]).__name__==t and case['actual_type']==t and case['expected']==[[v]] and case['expected_type']==t and case['agrees'])
q=j['queries'];ck('six successful actual queries',len(q)==6 and all(x.get('error') is None and 'raised' not in x for x in q))
for i,g in enumerate(gs):
 expected=[[x['id'],x['x']] for x in f if x['graph']==g];ck(str(i)+' independent typed fixture readback',q[i]['rows']==expected and all(type(row[1]) is type(want[1]) for row,want in zip(q[i]['rows'],expected)))
for i,x in enumerate(q):ck(str(i)+' scoped only to new fixture graphs',any(x['query'].startswith("USE GRAPH '"+g+"' MATCH (n:OrdAggType13") for g in gs))
ck('WITH sum exercises actual staged path','WITH sum(n.x) AS s RETURN s' in q[4]['query'] and q[4]['columns']==['s'])
out={'verdict':'PASS_FRESH_ORDINARY_TYPED_NATIVE_AUDIT','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'inputs':inputs,'elapsed_s':time.monotonic()-start,'native_fact_cases':4,'native_fact_agreements':4,'reviewer_native_calls':0,'reviewer_network_calls':0,'git_calls':0,'interrupted_inputs_opened_or_reused':False,'new_issue_credit':0,'formal_credit':0,'qualification':'Exact Fraction expectations from raw dyadic fixture values, actual Python result types and staged WITH readback. Current/export source/helper/setup bytes match; root owns native identity/execution. No general numeric/codec/driver/collation/body proof.'};(H/'review-aggregate-types-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'verdict':out['verdict'],'checks':len(checks),'elapsed_s':out['elapsed_s']}))
