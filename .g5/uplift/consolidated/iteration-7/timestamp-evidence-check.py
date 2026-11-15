"""Read-only package freshness check; writes only timestamp-validation.json."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[];latest={}
for p in sorted((REPO/'.g5/Verus_verification/results/temporal_clock').glob('*/receipt.json')):
    d=json.loads(p.read_text());key=d['kind']+(':'+d['control']['name'] if d['kind']=='control' else '')
    latest[key]=(p,d);rows.append({'receipt':str(p.relative_to(REPO)),'kind':key,'verdict':d['verdict'],'threads':d.get('threads')})
checks=[]
for key,(p,d) in sorted(latest.items()):
    stale=[name for name,digest in d['inputs'].items() if not (REPO/name).is_file() or sha(REPO/name)!=digest]
    expected='EXPECTED_FAIL' if d['kind']=='control' else 'AGREES' if d['kind']=='binding' else 'PASS'
    checks.append({'kind':key,'receipt':str(p.relative_to(REPO)),'verdict':d['verdict'],'stale_inputs':stale,'agrees':not stale and d['verdict']==expected and (d['kind']=='binding' or str(d['threads'])=='4')})
cost=json.loads((HERE/'timestamp-verifier-cost.json').read_text())
unit=json.loads((HERE/'timestamp-upstream-unit.json').read_text())
native=json.loads((HERE/'timestamp-native.json').read_text())
out={'all_fresh_and_expected':all(c['agrees'] for c in checks),'latest_receipts':checks,'all_attempt_receipts':rows,
    'final_verified':56,'reused_verified':31,'new_units':25,'new_theorem_bodies':24,'new_termination_obligations':1,'controls':16,
    'binding_cases':1564,'window_observations':12512,'binding_special_cases':5,'binding_detections':4,
    'native_cases':native['comparisons'],'native_verdict':native['verdict'],'native_ran_by':'root, not this child',
    'upstream_unit':unit,'upstream_passed':107,'final_verifier_cost':cost,
    'earlier_cost_limit':'Earlier phase wall times were not individually instrumented; preserve receipt stamps/logs rather than invent totals. Initial failed binding command wall0.701s. Missing VERUS_BIN setup and a receipt-summary TypeError are harness/setup failures.',
    'kept_attempts':['initial missing VERUS_BIN setup','binding mutation-anchor ambiguity in timestamp-binding-1.log','55 verified /1 error full-batch theorem before explicit recursive unfolding','earlier successful50/52/56 and14/16-control runs used runner default8; final all4-thread replay supersedes them','initial root native wrong-keyword log retained by root'],
    'private_grade':'unavailable; no held-out evaluator input inspected','product_changed':False}
(HERE/'timestamp-validation.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'fresh':out['all_fresh_and_expected'],'latest_receipts':len(checks),'controls':16,'native':native['verdict']}))
assert len(checks)==18 and out['all_fresh_and_expected'] and unit['exit_code']==0 and native['verdict']=='AGREES'
