"""Input invalidation tests in disposable copies only; active files never mutated."""
import hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];TOOL=REPO/'.g5/Verus_verification/tools/correspondence_gate.py';STAMP=HERE/'correspondence-inputs.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def main():
 old=json.loads(STAMP.read_text());scratch=Path(tempfile.mkdtemp(prefix='ivg-iter11-freshness-'));packages={}
 def relkey(k):
  p=Path(k);return str(p.relative_to(REPO)) if p.is_absolute() else k
 for fam in ['weighted_fraction','vector_admission']:
  receipt=sorted((REPO/'.g5/Verus_verification/results'/fam).glob('*-binding/receipt.json'))[-1];packages[fam]=json.loads(receipt.read_text())['inputs']
 for key in set(old['product'])|set(old['formal'])|set().union(*[set(p) for p in packages.values()]):
  if key.startswith('external:'):continue
  rel=relkey(key);assert not Path(rel).is_absolute();p=scratch/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/rel,p)
 results=[]
 def run(label,rel=None,formal=False,package_only=False,added=False):
  p=scratch/rel if rel else None;saved=p.read_bytes() if p and p.exists() else None
  if p:
   p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((saved or b'')+(b'\ndef competing_vector_writer(conn):\n    return conn.execute("UPDATE embedding_registry SET dimension=3")\n' if added else b'\n'))
  r=subprocess.run([sys.executable,str(TOOL),'check',str(STAMP),'--root',str(scratch)],cwd=REPO,text=True,capture_output=True);v=json.loads(r.stdout)
  expected=('STALE_ALL' if formal else 'REUSABLE_INPUTS','STALE_ALL' if rel and not package_only else 'REUSABLE_INPUTS');assert (v['proof'],v['correspondence'])==expected,(label,v,expected)
  stale={fam:sorted(k for k,h in package.items() if sha(scratch/relkey(k))!=h) for fam,package in packages.items()}
  for fam,package in packages.items():assert stale[fam]==sorted(k for k in package if relkey(k)==rel),(label,fam,stale)
  if rel is None:assert all(not x for x in stale.values())
  results.append(dict(label=label,exit=r.returncode,**v,package_stale_inputs=stale))
  if p:
   if saved is None:p.unlink()
   else:p.write_bytes(saved)
 run('fresh')
 run('fraction-formal','.g5/Verus_verification/models/weighted_fraction/weighted_fraction.rs',formal=True)
 run('vector-formal','.g5/Verus_verification/models/vector_admission/vector_admission.rs',formal=True)
 for name in ['json_width.rs','catalog.rs','numbers.rs','parser.rs']:
  run('vector-companion-'+name,'.g5/Verus_verification/models/vector_admission/'+name,formal=True)
 run('vector-manifest','.g5/Verus_verification/models/vector_admission/model.json',formal=True)
 for fam in ['weighted_cost','weighted_paths']:
  run('fraction-import-'+fam,'.g5/Verus_verification/models/'+fam+'/'+fam+'.rs',formal=True)
 run('fraction-comparison-helper','.g5/Verus_verification/models/weighted_fraction/kernel_model.py',package_only=True)
 run('vector-comparison-port','.g5/Verus_verification/models/vector_admission/port.py',package_only=True)
 run('binding-wrapper','.g5/Verus_verification/models/vector_admission/binding.py')
 run('weighted-source','iris_src/src/Graph/KG/TraversalPaths.cls')
 run('vector-source','iris_vector_graph/_engine/vector.py')
 run('role-links','.g5/Verus_verification/crosswalk/decision-links.tsv')
 run('new-writer','iris_vector_graph/new_vector_writer.py',added=True)
 for name in ['root-fraction-native.json','root-vector-native.json','root-seed-native.json']:
  run('native-fact-'+name,'.g5/uplift/consolidated/iteration-11/'+name,package_only=True)
 result=dict(scratch=str(scratch),controls=results,all_expected=True,active_inputs_mutated=False,scope='Global proof/source/name/link manifest is distinct from per-package flat comparator/native evidence hashes. Helper or native-fact changes may leave global proof/source reusable but invalidate the relevant package binding; the consolidated gate requires both. No live provider freshness follows.')
 (HERE/'freshness-controls.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(controls=len(results),all_expected=True,scratch=str(scratch))))
if __name__=='__main__':main()
