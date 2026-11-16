"""Independent read-only audit of the fresh ordinary aggregate panel; no native helper is imported."""
from pathlib import Path
import json,hashlib,time,datetime
R=Path(__file__).resolve().parents[4];H=Path(__file__).resolve().parent;P=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');start=time.monotonic();checks=[];inputs={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):inputs[str(p.relative_to(R))]=sha(p);return p.read_text()
def ck(n,v):checks.append({'name':n,'passed':bool(v)});assert v,n
j=json.loads(read(H/'root-aggregate-native.json'));ck('eight complete agreements',j['verdict']=='AGREES' and j['completed_cases']==8 and len(j['cases'])==8 and j['failure'] is None and j['identity_checked'])
for rel,h in j['inputs'].items():ck('flat input '+rel,sha(R/rel)==h);read(R/rel)
for rel,h in j['source_inputs'].items():ck('source current/export '+rel,sha(R/rel)==sha(P/rel)==h);read(R/rel)
for name in ['root-aggregate-native.log','root-aggregate-native-PAIRS.md','review-aggregate-expectations.md','inputs.json','REDIRECTION.md']:read(H/name)
fixture=j['fixture'];graphs=list(dict.fromkeys(x['graph'] for x in fixture));ck('only six new fixture nodes in two ordinary graphs',len(fixture)==6 and len(graphs)==2 and len({(x['graph'],x['id']) for x in fixture})==6 and all(x['graph'].startswith('ordinary13agg_') and x['id'].startswith('ordinary13agg:') for x in fixture))
rows=[x for x in fixture if x['graph']==graphs[0]];other=[x for x in fixture if x['graph']==graphs[1]]
def counts(rs):
 vals=[x['properties'].get('v') for x in rs];nonnull=[v for v in vals if v is not None];return [len(rs),len(nonnull),len(set(nonnull))]
groups={}
for x in rows:groups.setdefault(x['properties']['cat'],[]).append(x)
grouped=[[key,*counts(rs)] for key,rs in sorted(groups.items())];order=sorted([[key,len(rs)] for key,rs in groups.items()],key=lambda x:(-x[1],x[0]))
expected=[[[0,0,0]],[],[counts(rows)],grouped,order[:1],order[1:2],[[counts(rows)[2]]],[counts(other)]]
for i,(case,want) in enumerate(zip(j['cases'],expected)):
 ck(str(i)+' raw fixture-derived full result',case['actual']==want and case['expected']==want and case['agrees'])
q=j['queries'];ck('nine actual queries including independent fixture reader',len(q)==9 and all(x.get('error') is None and 'raised' not in x for x in q))
ck('unkeyed fixture readback equals raw creation inputs',q[0]['rows']==[[x['id'],x['properties']['cat'],x['properties'].get('v')] for x in rows])
for i,x in enumerate(q):ck(str(i)+' explicitly scoped to only fresh graphs',any(x['query'].startswith("USE GRAPH '"+g+"' MATCH (n:OrdAgg13") for g in graphs))
ck('empty grouped result preserves RETURN column names',q[2]['rows']==[] and q[2]['columns']==['n.cat','count(*)'])
ck('global empty differs from grouped empty',q[1]['rows']==[[0,0,0]] and q[2]['rows']==[])
ck('order and paging derived after aggregate',q[5]['rows']==order[:1] and q[6]['rows']==order[1:2] and q[5]['columns']==q[6]['columns']==['cat','c'])
out={'verdict':'PASS_FRESH_ORDINARY_NATIVE_FACT_AUDIT','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'inputs':inputs,'elapsed_s':time.monotonic()-start,'native_fact_cases':8,'native_fact_agreements':8,'reviewer_native_calls':0,'reviewer_network_calls':0,'git_calls':0,'interrupted_inputs_opened_or_reused':False,'new_issue_credit':0,'formal_credit':0,'qualification':'Raw fixture-derived count/group/null/distinct/paging expectations, exact current/export source and completed setup/helper hashes; root owns actual native identity/execution. No arbitrary aggregate/numeric/JSON/collation/parser/concurrency or native executable-body claim.'}
(H/'review-aggregate-native-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'verdict':out['verdict'],'checks':len(checks),'elapsed_s':out['elapsed_s']}))
