"""Builder final receipt/input audit and retained-attempt cost inventory."""
import datetime as dt,hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];MODEL=REPO/'.g5/Verus_verification/models/weighted_fraction';RESULT=REPO/'.g5/Verus_verification/results/weighted_fraction'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def relative(p):return str(p.relative_to(REPO))
def fresh(j):return all((REPO/k).is_file() and sha(REPO/k)==v for k,v in j.get('inputs',{}).items())
def ordinary(s):return ('assertion failed' in s or 'postcondition not satisfied' in s) and not ('rlimit' in s.lower() and 'exceeded' in s.lower())
allrec=[]
for p in sorted(RESULT.glob('*/receipt.json')):
    j=json.loads(p.read_text());o=j.get('observed',{});seconds=None
    if 'raw_log' in o:
        a=Path(o['raw_log']).name[:16];b=p.parent.name[:16]
        try:seconds=(dt.datetime.strptime(b,'%Y%m%dT%H%M%SZ')-dt.datetime.strptime(a,'%Y%m%dT%H%M%SZ')).total_seconds()
        except ValueError:pass
    allrec.append(dict(path=relative(p),sha256=sha(p),kind=j['kind'],verdict=j['verdict'],verified=o.get('verified'),errors=o.get('errors'),has_resource_limit=o.get('has_resource_limit'),input_fresh=fresh(j),approx_pair_wall_s=seconds,body=j))
manifest=json.loads((MODEL/'model.json').read_text());final=[]
proof=[r for r in allrec if r['kind']=='proof'][-1];assert proof['verdict']=='PASS' and proof['verified']==181 and proof['errors']==0;final.append(proof)
controlaudit=[]
for c in manifest['controls']:
    r=[r for r in allrec if '-control-'+c['name']+'/' in r['path']][-1];j=r['body'];o=j['observed'];assert j['verdict']=='EXPECTED_FAIL' and not o['has_resource_limit'] and not o['timed_out']
    logs=[REPO/k for k in j['raw_log_copies']];assert all(sha(p)==j['raw_log_copies'][relative(p)] for p in logs)
    assert all(ordinary(p.read_text()) for p in logs)
    assert all(x['errors'] and not x['timed_out'] for x in o['per_function'].values())
    controlaudit.append(dict(name=c['name'],category='representation' if c['name'] in ['default-unit-not-scaled','positive-numerator-not-scaled','zero-raw-not-defaulted','cap-omits-common-factor'] else 'source-facing algorithm/reader',targets=c['expect_fail_in'],ordinary_full_and_isolated=True,no_resource_limit=True,receipt=r['path']))
    final.append(r)
binding=[r for r in allrec if r['kind']=='binding'][-1];b=binding['body'];assert b['verdict']=='AGREES' and b['comparisons']==20522 and b['mismatch_count']==0 and b['socket_connect_calls']==0 and all(b['sensitivity'].values());assert all(x['agrees'] for x in b['unreduced_carrier_worlds']);final.append(binding)
assert all(r['input_fresh'] for r in final)
package={relative(p):sha(p) for p in sorted(MODEL.iterdir()) if p.is_file()}
up=json.loads((HERE/'fraction-upstream.json').read_text());assert up['exit_code']==0 and up['socket_calls']==0
out=dict(verdict='PASS',package_inputs=package,final_receipts=[{k:v for k,v in r.items() if k!='body'} for r in final],final_fresh_count=len(final),controls=controlaudit,counts=json.loads((HERE/'fraction-counts.json').read_text()),binding=dict(receipt=binding['path'],comparisons=b['comparisons'],typed_neighbors=len(b['typed_neighbors']),generic_exact_provider_worlds=b['generic_exact_provider_worlds'],unreduced_carrier_worlds=len(b['unreduced_carrier_worlds']),negative_cap_source_branch_worlds=b['negative_cap_source_branch_worlds'],sensitivity=b['counts'],sensitivity_total=len(b['sensitivity']),socket_calls=0),review_correction=dict(type='binding helper selected Both tag2',core_unchanged=True,old_valid_tag_worlds_unaffected=20520,added_actual_handler_worlds=2,preserved='results/weighted_fraction/attempts/tag2-before-review.*'),upstream=dict(passed=83,files=up['files'],elapsed_s=up['elapsed_s'],socket_calls=0),native_read_only=b['native_supplement'],scope='Builder audit, not independent or held-out grade. Final named targets all ordinary; imported units are rechecked. Earlier receipt verdicts and stale hashes retained as historical attempt facts.')
(HERE/'fraction-validation.json').write_text(json.dumps(out,indent=2)+'\n')
compact=[{k:v for k,v in r.items() if k!='body'} for r in allrec]
co=dict(receipt_inventory=compact,receipt_count=len(compact),proof_runner_commands=sum(r['kind']=='proof' for r in allrec),formal_control_pairs=sum(r['kind']=='control' for r in allrec),binding_receipts=sum(r['kind']=='binding' for r in allrec),approx_receipt_backed_verifier_wall_s=sum(r['approx_pair_wall_s'] or 0 for r in allrec),binding_elapsed_s=[r['body'].get('elapsed_s') for r in allrec if r['kind']=='binding'],extra_import_baseline_log=relative(HERE/'fraction-import-baseline.log'),source_snapshots={relative(p):sha(p) for p in sorted((RESULT/'attempts').glob('*')) if p.is_file()},unreceipted_binding_failure=dict(log=relative(HERE/'fraction-binding-attempt1.log'),sha256=sha(HERE/'fraction-binding-attempt1.log'),cause='Missing harness procedure_name before typed panel; corrected, exact initial draft retained'),retained_binding_false_expectations=dict(receipt='.g5/Verus_verification/results/weighted_fraction/20261115T212108Z-binding/receipt.json',cause='Variable fixture default is_parameter=False meant pattern variable, not a missing parameter. Explicit is_parameter=True corrected fixture; all20,520 search worlds already agreed.'),cost_scope='Receipt UTC-second differences estimate elapsed runner invocation/control-pair wall time (coarse, not CPU or reasoning time). Import-only baseline additionally retained; initial binding exception has no elapsed receipt. Native22/root and independent review costs are separate, not rerun here. No raised resource flags or fixed budget.')
# Runner controls use kind="control"; keep command count exact even if schema changes.
co['formal_control_pairs']=len([r for r in allrec if '-control-' in r['path']]);co['receipt_backed_verifier_commands']=co['proof_runner_commands']+2*co['formal_control_pairs'];co['extra_import_baseline_commands']=1
(HERE/'fraction-costs.json').write_text(json.dumps(co,indent=2)+'\n')
print(json.dumps(dict(verdict=out['verdict'],final_fresh=len(final),proof181=True,controls=len(controlaudit),binding=out['binding'],verifier_commands=co['receipt_backed_verifier_commands'],all_receipts=len(compact))))
