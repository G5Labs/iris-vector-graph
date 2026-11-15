"""Read-only validation of exact independent vector proof/control/binding replay."""
import datetime,hashlib,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];S=HERE/'review-vector-scratch';PY='/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
start=json.loads((HERE/'review-vector-start.json').read_text());rows=[];logs=[]
for p in sorted((S/'.g5/Verus_verification/results/vector_admission').glob('*/receipt.json')):
 r=json.loads(p.read_text());kind=r['kind'];raw=[]
 for rel,h in r['inputs'].items():assert sha(S/rel)==sha(ROOT/rel)==h,(rel,h)
 for rel,h in r.get('raw_log_copies',{}).items():q=S/rel;assert sha(q)==h;raw.append(q)
 row=dict(path=str(p.relative_to(ROOT)),sha256=sha(p),kind=kind,verdict=r['verdict'],input_count=len(r['inputs']))
 if kind=='proof':assert r['verdict']=='PASS' and r['observed']['verified']==77 and r['observed']['errors']==0
 elif kind=='control':
  o=r['observed'];assert r['verdict']=='EXPECTED_FAIL' and o['errors']>0 and o['exit_code']!=0 and not o['has_resource_limit'] and not o['timed_out']
  assert set(o['per_function'])==set(r['control']['expect_fail_in'])
  assert all(x['errors']>0 and not x['timed_out'] for x in o['per_function'].values())
  assert len(raw)==1+len(o['per_function'])
  for q in raw:
   t=q.read_text();assert re.search(r'(assertion failed|postcondition not satisfied)',t),q
   assert not re.search(r'(resource limit exceeded|timed out)',t,re.I),q
  row.update(name=r['control']['name'],ordinary_whole_and_isolated_failure=True,named_claims=list(o['per_function']))
 elif kind=='binding':
  assert r['verdict']=='AGREES' and r['comparisons']==735 and r['search_comparisons']==466 and r['parser_comparisons']==254 and r['mismatch_count']==0 and not r['mismatches'] and not r['parser_misses'] and r['failure'] is None
  assert len(r['cache'])==3 and len(r['ivf'])==12 and all(x['agrees'] for x in r['cache']+r['ivf']) and all(r['checks'].values()) and len(r['checks'])==6
  assert all(r['sensitivity'].values()) and len(r['sensitivity'])==9 and sum(k.startswith('actual_') for k in r['sensitivity'])==7
  assert all(r['current_equals_exported_pin'].values()) and r['socket_connect_calls']==0 and r['native_calls']==0
  row.update(comparisons=735,search=466,json=254,cache=3,ivf=12,sensitivity=dict(actual_python=7,port=1,altered_observation=1),socket_connect_calls=0,native_calls=0,contrasts={k:dict(got=v['got'],effects=v['effects'],agrees=v['agrees']) for k,v in r['contrasts'].items()})
 else:raise AssertionError(kind)
 cmd=[PY,'.g5/Verus_verification/run_verus.py','fresh',str(p.relative_to(S))];v=subprocess.run(cmd,cwd=S,capture_output=True,text=True);logs.append(' '.join(cmd)+'\n'+v.stdout+v.stderr);assert v.returncode==0;row['fresh_exit']=0;rows.append(row)
assert len(rows)==10 and sum(x['kind']=='control' for x in rows)==8
assert all(sha(ROOT/rel)==sha(S/rel)==h for rel,h in start['package_inputs'].items())
counts=start['counts'];assert sum(len(x['proof_declarations']) for x in counts.values())==51 and sum(sum(n.startswith('theorem_') for n in x['proof_declarations']) for x in counts.values())==45 and sum(len(x['recursive_specs']) for x in counts.values())==26 and sum(x['nonlinear_subqueries'] for x in counts.values())==0
up=json.loads((S/'.g5/uplift/consolidated/iteration-11/vector-upstream-units.json').read_text());assert up['verdict']=='PASS' and up['count']==23 and up['socket_connect_calls']==0 and all(x['status']=='PASS' for x in up['tests'])
pin=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
for p,h in up['source_inputs'].items():assert sha(S/Path(p).relative_to(pin))==h
fresh=json.loads((HERE/'review-vector-fresh-audit.json').read_text());seed=json.loads((HERE/'review-seed-audit.json').read_text());native=json.loads((HERE/'review-native-audit.json').read_text())
assert fresh['source_cases']==21 and fresh['all_input_dependent_checks'] and fresh['socket_calls']==0 and fresh['native_runtime_calls']==0 and not fresh['candidate_inspection']
assert seed['local_source_cases']==6 and seed['native_records_audited']==5 and all(x['agrees'] for x in seed['root_native_case_checks']) and seed['sockets']==0 and seed['native_executed_by_reviewer']==0
assert native['vector']['count']==13 and all(x['agrees'] for x in native['vector']['cases']) and native['native_executed_by_reviewer']==0
for rel,h in native['artifacts'].items():assert sha(ROOT/rel)==h
for rel,h in seed['inputs'].items():assert sha(ROOT/rel)==h
recovery=json.loads((HERE/'root-vector-attempt1-provenance.json').read_text());assert sha(ROOT/recovery['recovered_prediction'])==recovery['original_prediction_sha256'] and sha(ROOT/recovery['archived_script'])==recovery['original_script_sha256']
runs=json.loads((HERE/'review-vector-runs.json').read_text())['runs'];assert all(x['exit']==0 for x in runs)
out=dict(verdict='ACCEPT_BOUNDED_FRAGMENT',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),total_verified=77,new_units=dict(proof_declarations=51,named_theorems=45,proof_helpers=6,recursive_spec_checks=26,nonlinear_arithmetic_subqueries=0),imported_units=0,receipts=rows,all10fresh=True,all_package_current_equals_scratch=True,package_inputs=start['package_inputs'],runs=runs,subprocess_elapsed_s=sum(x['seconds'] for x in runs),upstream=up,pre_candidate_source_cases=21,pre_candidate_seed_cases=6,root_native_records_read_only_audited=dict(vector=13,controlled_seed_fault=5),historical_attempt1_prediction_recovery_hash_verified=True,reviewer_native_executions=0,scope='Builder-visible source-first purposive review; ordinary typed/lexical/provider fragment, not arbitrary stdlib grammar/native numeric/catalog truth/identifier/writer transaction/wholebody proof')
(HERE/'review-vector-receipt-freshness.log').write_text('\n'.join(logs))
(HERE/'review-vector-validation.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(verdict=out['verdict'],verified=77,controls=8,binding=735,upstream=23,receipts=10,seconds=out['subprocess_elapsed_s'])))
