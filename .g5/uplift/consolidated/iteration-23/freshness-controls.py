"""Root-only disposable14 freshness audit. Run after final integration/capture; no model execution."""
import hashlib,importlib.util,json,shutil,time,traceback
from pathlib import Path
R=Path.cwd();A=R/'.g5/uplift/consolidated/iteration-23';V=R/'.g5/Verus_verification';start=time.monotonic()
spec=importlib.util.spec_from_file_location('cloud23_correspondence',V/'tools/correspondence_gate.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
base=json.loads((A/'correspondence-inputs.json').read_text());assert gate.inputs(R)==base
models=['typed_equality'];receipts={}
for m in models:
 paths=sorted((V/'results'/m).glob('*-binding/receipt.json'));assert paths,m
 receipts[m]=json.loads(paths[-1].read_text());assert receipts[m]['verdict']=='AGREES',m
S=A/'freshness-shadow';S.mkdir(exist_ok=False)
names=set(base['product'])|{x for x in base['formal'] if not x.startswith('external:')}
for receipt in receipts.values():names.update(receipt['inputs'])
for rel in sorted(names):
 assert not Path(rel).is_absolute(),rel
 p=R/rel;assert p.is_file(),rel;q=S/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def flat(root,d):return sorted(p for p,h in d['inputs'].items() if not (root/p).is_file() or sha(root/p)!=h)
assert gate.inputs(S)==base and all(not flat(S,d) for d in receipts.values())
jobs=[('decision-source','iris_vector_graph/cypher/translator.py','append'),('spelling-source','iris_vector_graph/prop_values.py','append'),('renamed-source','iris_vector_graph/_engine/query.py','rename'),('removed-source','iris_vector_graph/_engine/nodes_edges.py','remove'),('new-product-filename','iris_vector_graph/cloud23_disposable_writer.py','new-product'),('new-formal-filename','.g5/Verus_verification/models/cloud23_disposable/extra.rs','new-formal'),('equality-proof','.g5/Verus_verification/models/typed_equality/typed_equality.rs','append'),('imported-node-proof','.g5/Verus_verification/models/node_read/node_read.rs','append'),('equality-manifest','.g5/Verus_verification/models/typed_equality/model.json','append'),('family-map','.g5/Verus_verification/families.tsv','append'),('source-role-map','.g5/Verus_verification/crosswalk/decision-links.tsv','append'),('audit-implementation','.g5/Verus_verification/tools/correspondence_gate.py','append')]
for m in models:
 jobs.append((m+'-binding',f'.g5/Verus_verification/models/{m}/binding.py','append'))
 # This checks freshness of declared non-global dependencies; independent review audits completeness separately.
 for rel in sorted(receipts[m]['inputs']):
  if rel not in base['product'] and rel not in base['formal']:
   jobs.append((m+'-flat-'+str(len(jobs)),rel,'append'))
cases=[];failure=None
try:
 for name,rel,op in jobs:
  p=S/rel;raw=p.read_bytes() if p.exists() else None;moved=p.with_name(p.name+'.cloud23-renamed');D=A/'freshness-attempts'/name;D.mkdir(parents=True)
  if raw is not None:(D/'before.bin').write_bytes(raw)
  expected=[op=='new-product' or rel in base['product'],op=='new-formal' or rel in base['formal']]+[rel in receipts[m]['inputs'] for m in models]
  (D/'command.json').write_text(json.dumps(dict(path=rel,operation=op,expected=expected,active_mutation=False,proof_or_binding_execution=False),indent=2)+'\n')
  try:
   if op=='append':p.write_bytes(raw+b'\n ')
   elif op.startswith('new-'):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'// disposable name-inventory fixture\n')
   elif op=='rename':p.rename(moved)
   elif op=='remove':p.unlink()
   now=gate.inputs(S);pc=gate.changes(base['product'],now['product']);fc=gate.changes(base['formal'],now['formal']);stale={m:flat(S,receipts[m]) for m in models};got=[bool(pc),bool(fc)]+[bool(stale[m]) for m in models]
   result=dict(name=name,path=rel,operation=op,expected=expected,observed=got,changed_product=pc,changed_formal=fc,stale_binding_inputs=stale,passed=got==expected,active_inputs_mutated=False)
   (D/'observed.json').write_text(json.dumps(result,indent=2)+'\n');cases.append(result);assert result['passed'],result
  finally:
   if op=='rename' and moved.exists():moved.rename(p)
   elif raw is None:
    if p.exists():p.unlink()
   else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
  assert gate.inputs(S)==base and all(not flat(S,d) for d in receipts.values())
except Exception as e:failure=dict(type=type(e).__name__,message=str(e),trace=traceback.format_exc())
unchanged=gate.inputs(R)==base and all(not flat(R,d) for d in receipts.values())
out=dict(verdict='PASS_GLOBAL_AND_FLAT_CLOUD23_FRESHNESS' if failure is None and unchanged else 'FAILED_OR_INCOMPLETE',models=models,controls=cases,control_count=len(cases),all_expected=failure is None and all(x['passed'] for x in cases),active_inputs_mutated=not unchanged,failure=failure,elapsed_s=time.monotonic()-start,scope='Disposable file/hash freshness only. No proof/binding/product/native/network execution; no private/interrupted inputs. Input-inventory completeness is independently reviewed, not inferred from this declared-dependency stale check.')
(A/'freshness-controls.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['verdict','control_count','all_expected','active_inputs_mutated','failure','elapsed_s']}));raise SystemExit(0 if out['verdict'].startswith('PASS') else 1)
