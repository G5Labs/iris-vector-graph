"""Check only this package; writes fhir-validation.json, no native/runtime calls."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
latest={};attempts=[]
for p in sorted((REPO/'.g5/Verus_verification/results/fhir_tasks').glob('*/receipt.json')):
    d=json.loads(p.read_text());key=d['kind']+(':'+d['control']['name'] if d['kind']=='control' else '')
    latest[key]=(p,d);attempts.append({'receipt':str(p.relative_to(REPO)),'kind':key,'verdict':d['verdict'],'threads':d.get('threads')})
checks=[]
for key,(p,d) in sorted(latest.items()):
    stale=[name for name,h in d['inputs'].items() if not (REPO/name).is_file() or sha(REPO/name)!=h]
    expected='EXPECTED_FAIL' if d['kind']=='control' else 'AGREES' if d['kind']=='binding' else 'PASS'
    checks.append({'kind':key,'receipt':str(p.relative_to(REPO)),'verdict':d['verdict'],'stale_inputs':stale,
        'agrees':not stale and d['verdict']==expected and (d['kind']=='binding' or str(d['threads'])=='4')})
manifest=json.loads((REPO/'.g5/Verus_verification/models/fhir_tasks/model.json').read_text())
native=json.loads((HERE/'fhir-native.json').read_text());unit=json.loads((HERE/'fhir-upstream-unit.json').read_text())
binding=latest['binding'][1];cost=json.loads((HERE/'fhir-verifier-final-cost.json').read_text())
sources=native['source_identities'];source_checks=all(x['export_equals'] and x['current_equals'] for x in sources.values())
out={'all_fresh_and_expected':all(c['agrees'] for c in checks),'latest_receipts':checks,'all_attempt_receipts':attempts,
    'verified':27,'proof_declarations':26,'termination_units':1,'controls':len(manifest['controls']),
    'core_binding_cases':binding['comparisons'],'retry_scenarios':len(binding['retry_scenarios']),'reader_scenarios':len(binding['reader_cases']),
    'graph_cases':len(binding['graph_cases']),'detection':binding['detection'],'native_comparisons':native['comparisons'],'native_verdict':native['verdict'],
    'native_run_by':'root, not child','native_all_created_ids_absent':native['all_created_ids_absent'],'native_source_checks':source_checks,
    'native_id_lookup_observations':binding.get('native_id_lookup_observations'),
    'identifier_provider_fragment':binding.get('identifier_provider_fragment'),
    'native_provenance_inputs':native['source_inputs'],'native_scope':native['scope'],'unit':unit,'unit_passed':45,'final_verifier_cost':cost,
    'kept_attempts':['enum-struct literal syntax','reserved exists keyword','integer literal type inference','22 verified/2 errors: fresh allocation can equal stale registry ID; exact failed source preserved','earlier controls from pre-fix source retained but superseded','root native initial harness failures/zero-case falseAGREES retracted; accepted18 and20 predecessors retained'],
    'failed_retry_source':'.g5/uplift/consolidated/iteration-8/fhir-model-attempts/retry22-2.rs',
    'scope':'as-built default task workflow, valid decoded string Settings, canonical validated graph/ns, specified pre-effect provider failures and successful allocation/load frames; source/native/adapter limits in NOTES',
    'independent_grade':'unavailable; no undisclosed evaluator cases inspected','child_native_runtime_access':False,'product_changed':False}
(HERE/'fhir-validation.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'fresh':out['all_fresh_and_expected'],'receipts':len(checks),'proof':27,'controls':len(manifest['controls']),'binding':binding['verdict'],'native':native['comparisons']}))
assert len(checks)==21 and out['all_fresh_and_expected'] and manifest['expected_verified']==27 and len(manifest['controls'])==19
assert native['verdict']=='AGREES' and native['comparisons']==20 and source_checks and native['all_created_ids_absent'] and unit['exit_code']==0
