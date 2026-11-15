"""Read-only audit of the refuted source forecast and exposed finite follow-ups."""
import datetime,hashlib,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
t=time.perf_counter();bad=json.loads((HERE/'root-ledger-qualkeys-native.json').read_text());good=json.loads((HERE/'root-ledger-qualkeys-followup.json').read_text())
assert bad['verdict']=='DISAGREES_OR_INCOMPLETE' and bad['completed_cases']==0 and bad['cases']==[]
assert bad['failure']['type']=='LedgerInconsistencyError' and '<SUBSCRIPT>' in bad['failure']['message'] and 'QualsJson+4' in bad['failure']['message']
assert len(bad['revisions'])==1 and all(x['op']=='create_node' for x in bad['revisions'][0]['records'])
assert good['verdict']=='AGREES' and good['completed_cases']==6 and good['failure'] is None and good['post_refutation']
assert all(x['actual']==x['expected'] and x['prediction_agrees'] and x['post_refutation'] for x in good['cases'])
for r in [bad,good]:
 assert r['identity_checked'] and r['new_issue_claims']==0 and r['after_meta']['state']=='disabled'
 for p,h in r['inputs'].items():assert sha(ROOT/p)==h
 for p,h in r['source_inputs'].items():assert sha(ROOT/p)==sha(PIN/p)==h
cases={x['label']:x['actual'] for x in good['cases']}
new=cases['new empty-key batch refuses before relationship/revision'];old=cases['existing empty-key batch refuses without changing old qualifier']
assert new['error']==old['error']==dict(type='LedgerInconsistencyError',subscript=True,stage=True)
assert new['unchanged_head'] and new['physical'] is None and old['unchanged_head'] and old['physical']=={'q':'x'}
assert cases['valid nonempty new batch neighbor']==dict(physical={'q':'x'},replay={'q':'x'},records=[['set_qual','q',None,'x']])
assert cases['valid nonempty existing upsert neighbor']==dict(physical={'q':'y'},replay={'q':'y'},records=[['set_qual','q','x','y']])
assert cases['direct empty qualifier retains Python refusal']==['ValueError',True]
assert cases['node empty-property batch rolls back earlier create']==dict(error=dict(type='ChangesetOperationError',empty_property=True),unchanged_head=True,absent_node=True)
prior=json.loads((HERE/'review-ledger-native-audit.json').read_text())
for p,h in prior['inputs'].items():assert sha(ROOT/p)==h
names=['root-ledger-qualkeys-native.py','root-ledger-qualkeys-native.json','root-ledger-qualkeys-native.log','root-ledger-qualkeys-predictions.md','root-ledger-qualkeys-followup.py','root-ledger-qualkeys-followup.json','root-ledger-qualkeys-followup.log','root-ledger-qualkeys-followup-predictions.md']
out=dict(verdict='READ_ONLY_REFUTATION_AND_FOLLOWUP_AUDIT_AGREES',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),original_forecast='Empty batch qualifier key would be skipped after local key collection',forecast_status='REFUTED; reviewer overlooked invalid empty native local-array subscript before enumeration',original_completed_comparisons=0,original_failure=bad['failure'],followup_exposure='All6 explicitly post-refutation, not blind predictions',followup_cases=good['cases'],original_native22_artifacts_unchanged=True,inputs={str((HERE/n).relative_to(ROOT)):sha(HERE/n) for n in names},native_executed_by_reviewer=0,network_calls=0,new_product_issues=0,scope='Finite root-owned carrier observations. Preserve direct Python setter validation versus native local-array failure and node property rollback. No skip-empty theorem, universal native subscript/body/coercion/transaction proof or policy change.',elapsed_s=time.perf_counter()-t)
(HERE/'review-ledger-qualkeys-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['verdict','forecast_status','original_completed_comparisons','native_executed_by_reviewer','elapsed_s']}))
