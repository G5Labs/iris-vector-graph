"""Read-only validation of exact independent fraction replays and copied inputs."""
import datetime,hashlib,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];S1=HERE/'review-fraction-scratch';S2=HERE/'review-fraction-v2-scratch';PY='/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[];fresh_logs=[]
for scratch in [S1,S2]:
 paths=sorted((scratch/'.g5/Verus_verification/results/weighted_fraction').glob('*/receipt.json'))
 for p in paths:
  r=json.loads(p.read_text());kind=r['kind'];logs=[]
  for rel,h in r['inputs'].items():assert sha(scratch/rel)==h,(p,rel)
  for rel,h in r.get('raw_log_copies',{}).items():
   q=scratch/rel;assert sha(q)==h;logs.append(q)
  row=dict(scratch=scratch.name,path=str(p.relative_to(ROOT)),sha256=sha(p),kind=kind,verdict=r['verdict'])
  if kind=='prove':assert r['verdict']=='PASS' and r['observed']['verified']==181 and r['observed']['errors']==0
  elif kind=='control':
   o=r['observed'];assert r['verdict']=='EXPECTED_FAIL' and o['exit_code']!=0 and o['errors']>0 and not o['has_resource_limit'] and not o['timed_out']
   assert set(o['per_function'])==set(r['control']['expect_fail_in'])
   for name,t in o['per_function'].items():assert t['errors']>0 and not t['timed_out']
   assert len(logs)==1+len(o['per_function'])
   for q in logs:
    txt=q.read_text();assert re.search(r'(postcondition not satisfied|assertion failed)',txt),q
    assert not re.search(r'(resource limit exceeded|timed out)',txt,re.I),q
   row.update(name=r['control']['name'],whole_errors=o['errors'],isolated_claims=list(o['per_function']),ordinary_failures=True)
  elif kind=='binding':
   assert r['verdict']=='AGREES' and r['comparisons']==20522 and r['mismatch_count']==0 and r['socket_connect_calls']==0
   assert r['generic_exact_provider_worlds']==3 and len(r['unreduced_carrier_worlds'])==4 and len(r['typed_neighbors'])==13
   for field in ['samples','generic_samples','typed_neighbors','unreduced_carrier_worlds','raw_tag2_worlds']:assert all(x['agrees'] for x in r[field]),field
   assert len(r['raw_tag2_worlds'])==2 and all(r['sensitivity'].values()) and len(r['sensitivity'])==11
   assert r['counts']==dict(actual_python_controls=3,altered_observation_controls=1,representation_controls=4,source_port_controls=3)
   assert r['native_supplement']['all_input_hashes_current'] and r['native_supplement']['cases']==22 and r['native_supplement']['mirrored_points']==35
   assert all(r['current_export_pin_identities'].values())
   row.update(comparisons=r['comparisons'],typed=len(r['typed_neighbors']),generic=r['generic_exact_provider_worlds'],unreduced=len(r['unreduced_carrier_worlds']),controls=r['counts'],socket_calls=0,native_executed_by_reviewer=0)
  else:raise AssertionError(kind)
  rel=str(p.relative_to(scratch));cmd=[PY,'.g5/Verus_verification/run_verus.py','fresh',rel]
  f=subprocess.run(cmd,cwd=scratch,capture_output=True,text=True);fresh_logs.append(' '.join(cmd)+'\n'+f.stdout+f.stderr);assert f.returncode==0
  row['fresh_exit']=f.returncode;rows.append(row)
assert len(rows)==15 and sum(x['kind']=='control' for x in rows)==13
start=json.loads((HERE/'review-fraction-start.json').read_text());v=json.loads((HERE/'fraction-validation.json').read_text())
core=[p for p in v['package_inputs'] if p.endswith(('.rs','model.json'))]
assert all(sha(ROOT/p)==sha(S1/p)==sha(S2/p)==v['package_inputs'][p] for p in core)
assert all(sha(ROOT/p)==sha(S2/p)==h for p,h in v['package_inputs'].items())
up=json.loads((S2/'.g5/uplift/consolidated/iteration-11/fraction-upstream.json').read_text());assert up['exit_code']==0 and up['socket_calls']==0
assert '83 passed' in (HERE/'review-fraction-v2-upstream.log').read_text()
for rel,h in up['files'].items():assert sha(S2/rel)==h
formal=json.loads((HERE/'review-fraction-formal-runs.json').read_text());other=json.loads((HERE/'review-fraction-v2-runs.json').read_text())['runs']
out=dict(verdict='ACCEPT_BOUNDED_FRAGMENT',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_units=dict(proof_declarations=65,named_theorems=38,proof_helpers=27,recursive_spec_checks=9,nonlinear_arithmetic_subqueries=19,total=93),imported_rechecked_units=88,total_verified=181,receipts=rows,all_15_fresh=True,all_core_hashes_current_equals_v1_equals_v2=True,final_package_hashes=v['package_inputs'],final_package_current_equals_v2=True,scratch_v1_retained=True,review_discovery=dict(kind='correspondence helper miss',case='F13 raw tag2 under Both',v1_counterexample='review-fraction-tag2-probe.json',resolution='V2 rejects tag2; final two actual-handler boundary worlds agree',formal_unchanged=True,new_product_bug=False),upstream=dict(passed=83,socket_calls=0,source_hashes=up['files']),runs=formal+other,subprocess_elapsed_s=sum(x['seconds'] for x in formal+other),reviewer_native_executions=0,scope='Source-first independent builder-visible review; exact rational source abstraction, no arbitrary native numeric/JSON/provider/collation/body theorem')
(HERE/'review-fraction-fresh.log').write_text('\n'.join(fresh_logs))
(HERE/'review-fraction-validation.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(verdict=out['verdict'],fresh=len(rows),verified=181,controls=13,binding=20522,upstream=83,seconds=out['subprocess_elapsed_s'])))
