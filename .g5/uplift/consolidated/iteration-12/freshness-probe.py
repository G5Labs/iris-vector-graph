"""Input invalidation tests in disposable copies only; active files never mutated."""
import hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];TOOL=REPO/'.g5/Verus_verification/tools/correspondence_gate.py';STAMP=HERE/'correspondence-inputs.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def main():
 old=json.loads(STAMP.read_text());scratch=Path(tempfile.mkdtemp(prefix='ivg-iter12-freshness-'));packages={}
 def relkey(k):
  p=Path(k);return str(p.relative_to(REPO)) if p.is_absolute() else k
 for fam in ['communities','ledger_content']:
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
 for fam in ['communities','ledger_content']:
  run(fam+'-root','.g5/Verus_verification/models/'+fam+'/'+fam+'.rs',formal=True)
  run(fam+'-manifest','.g5/Verus_verification/models/'+fam+'/model.json',formal=True)
 run('ledger-alternate','.g5/Verus_verification/models/ledger_content/alternate.rs',formal=True)
 run('ledger-reconstruction-import','.g5/Verus_verification/models/reconstruction/reconstruction.rs',formal=True)
 for fam,name in [('communities','port.py'),('ledger_content','functional_model.py'),('ledger_content','sql_provider.py'),('ledger_content','alternate_ports.py')]:
  run(fam+'-'+name,'.g5/Verus_verification/models/'+fam+'/'+name,package_only=True)
 for fam in ['communities','ledger_content']:
  run(fam+'-binding-wrapper','.g5/Verus_verification/models/'+fam+'/binding.py')
 for name in ['iris_src/src/Graph/KG/Algorithms.cls','iris_src/src/Graph/KG/LedgerApply.cls','iris_vector_graph/_edgeless.py','iris_vector_graph/ledger/replay.py']:
  run('product-'+name,name)
 run('role-links','.g5/Verus_verification/crosswalk/decision-links.tsv')
 run('new-writer','iris_vector_graph/new_ledger_content_writer.py',added=True)
 for name in ['root-communities-census-native.json','root-ledger-native.json','root-ledger-qualkeys-native.json','root-ledger-qualkeys-followup.json','root-ledger-marker-native.json']:
  run('native-fact-'+name,'.g5/uplift/consolidated/iteration-12/'+name,package_only=True)
 result=dict(scratch=str(scratch),controls=results,all_expected=True,active_inputs_mutated=False,scope='Global proof/source/name/link manifest is distinct from per-package flat comparator/native evidence hashes. Helper or native-fact changes may leave global proof/source reusable but invalidate the relevant package binding; the consolidated gate requires both. No live provider freshness follows.')
 (HERE/'freshness-controls.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(controls=len(results),all_expected=True,scratch=str(scratch))))
if __name__=='__main__':main()
