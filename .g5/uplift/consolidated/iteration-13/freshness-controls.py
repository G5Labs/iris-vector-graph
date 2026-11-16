"""Disposable ordinary13 global-name and flat binding freshness controls; no execution."""
import hashlib,importlib.util,json,shutil,time,traceback
from pathlib import Path
R=Path.cwd();H=R/'.g5/uplift/consolidated/iteration-13';start=time.monotonic()
spec=importlib.util.spec_from_file_location('ordinary13_correspondence_gate',R/'.g5/Verus_verification/tools/correspondence_gate.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
base=json.loads((H/'correspondence-inputs.json').read_text());assert gate.inputs(R)==base
receipts={
 'reporting':json.loads((R/'.g5/Verus_verification/results/routine_reporting/20261116T004115Z-binding/receipt.json').read_text()),
 'aggregate':json.loads((R/'.g5/Verus_verification/results/aggregate_results/20261116T010011Z-binding/receipt.json').read_text())}
S=H/'freshness-shadow';S.mkdir(exist_ok=False)
names=set(base['product'])|{p for p in base['formal'] if not p.startswith('external:')}
for receipt in receipts.values():names.update(receipt['inputs'])
for rel in names:
 assert not Path(rel).is_absolute(),rel
 p=R/rel;q=S/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
assert gate.inputs(S)==base
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def flat(root,receipt):return sorted(k for k,v in receipt['inputs'].items() if not (root/k).is_file() or sha(root/k)!=v)
assert all(not flat(S,x) for x in receipts.values())
cases=[];failure=None
jobs=[
 ('core-source','.g5/placeholder','iris_vector_graph/_engine/admin.py','append',True,False,True,False),
 ('aggregate-source','', 'iris_vector_graph/cypher/translator.py','append',True,False,False,True),
 ('new-writer-name','', 'iris_vector_graph/ordinary13_disposable_writer.py','new',True,False,False,False),
 ('renamed-source','', 'iris_vector_graph/_engine/admin.py','rename',True,False,True,False),
 ('removed-source','', 'iris_vector_graph/_engine/admin.py','remove',True,False,True,False),
 ('reporting-proof','', '.g5/Verus_verification/models/routine_reporting/routine_reporting.rs','append',False,True,True,False),
 ('aggregate-manifest','', '.g5/Verus_verification/models/aggregate_results/model.json','append',False,True,False,True),
 ('reporting-binding','', '.g5/Verus_verification/models/routine_reporting/binding.py','append',True,False,True,False),
 ('family-map','', '.g5/Verus_verification/families.tsv','append',True,False,False,False),
 ('source-role-map','', '.g5/Verus_verification/crosswalk/decision-links.tsv','append',True,False,False,False),
 ('new-formal-name','', '.g5/Verus_verification/models/ordinary13_disposable/extra.rs','new',False,True,False,False),
 ('audit-implementation','', '.g5/Verus_verification/tools/correspondence_gate.py','append',True,False,False,False),
 ('reporting-notes-flat','', '.g5/Verus_verification/models/routine_reporting/NOTES.md','append',False,False,True,False),
 ('aggregate-functional-flat','', '.g5/Verus_verification/models/aggregate_results/functional_model.py','append',False,False,False,True),
 ('aggregate-provider-flat','', '.g5/Verus_verification/models/aggregate_results/provider.py','append',False,False,False,True),
 ('aggregate-probe-flat','', '.g5/Verus_verification/models/aggregate_results/probe.py','append',False,False,False,True),
 ('aggregate-helper-inventory-flat','', '.g5/Verus_verification/models/aggregate_results/binding_inputs.json','append',False,False,False,True),
 ('native-fact-flat','', '.g5/uplift/consolidated/iteration-13/root-aggregate-native.json','append',False,False,False,True),
 ('native-prediction-flat','', '.g5/uplift/consolidated/iteration-13/root-aggregate-native-PAIRS.md','append',False,False,False,True),
 ('native-connection-helper-flat','', '.g5/Verus_verification/models/temporal_restore/binding.py','append',True,False,False,True),
 ('native-R308-authority-flat','', 'tests/unit/test_460_r308_guards.py','append',False,False,False,True),
 ('native-count-authority-flat','', 'tests/e2e/test_470_issue13_count_distinct_limit_e2e.py','append',False,False,False,True),
 ('reporting-selector-source','', 'iris_vector_graph/security.py','append',True,False,True,False),
]
try:
 for name,unused,rel,op,ep,ef,er,ea in jobs:
  p=S/rel;original=p.read_bytes() if p.exists() else None;moved=p.with_name(p.name+'.ordinary13-renamed');d=H/'freshness-attempts'/name;d.mkdir(parents=True)
  if original is not None:(d/'before.bin').write_bytes(original)
  try:
   if op=='append':p.write_bytes(original+b'\n ')
   elif op=='new':p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'// disposable file-name inventory fixture\n')
   elif op=='rename':p.rename(moved)
   elif op=='remove':p.unlink()
   now=gate.inputs(S);pc=gate.changes(base['product'],now['product']);fc=gate.changes(base['formal'],now['formal']);rs=flat(S,receipts['reporting']);ag=flat(S,receipts['aggregate'])
   got=[bool(pc),bool(fc),bool(rs),bool(ag)];expected=[ep,ef,er,ea]
   result=dict(name=name,operation=op,path=rel,expected=expected,observed=got,changed_product=pc,changed_formal=fc,stale_reporting_flat=rs,stale_aggregate_flat=ag,passed=got==expected,active_inputs_mutated=False)
   (d/'observed.json').write_text(json.dumps(result,indent=2)+'\n');cases.append(result);assert result['passed'],result
  finally:
   if op=='rename' and moved.exists():moved.rename(p)
   elif original is None:
    if p.exists():p.unlink()
   else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(original)
  assert gate.inputs(S)==base and all(not flat(S,r) for r in receipts.values())
except Exception as ex:failure=dict(type=type(ex).__name__,text=str(ex),trace=traceback.format_exc())
active_unchanged=gate.inputs(R)==base and all(not flat(R,r) for r in receipts.values())
out=dict(verdict='PASS_GLOBAL_AND_FLAT_ORDINARY_FRESHNESS' if failure is None and active_unchanged else 'FAILED_OR_INCOMPLETE',controls=cases,all_expected=failure is None and all(x['passed'] for x in cases),active_inputs_mutated=not active_unchanged,failure=failure,elapsed_s=time.monotonic()-start,scope='Disposable hashes/name inventory only; no proof/binding/product/native execution. Full scoped product/formal inventory and declared flat helpers/native authority are distinct. No private or interrupted input opened/reused. Active files byte-unchanged.')
(H/'freshness-controls.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(verdict=out['verdict'],controls=len(cases),failure=failure,active_inputs_mutated=not active_unchanged)))
raise SystemExit(0 if out['verdict'].startswith('PASS') else 1)
