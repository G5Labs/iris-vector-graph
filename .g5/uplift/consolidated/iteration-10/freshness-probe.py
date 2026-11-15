"""Test input invalidation only in disposable copies; no active files mutated."""
import hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];TOOL=REPO/'.g5/Verus_verification/tools/correspondence_gate.py';STAMP=HERE/'correspondence-inputs.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def main():
 old=json.loads(STAMP.read_text());scratch=Path(tempfile.mkdtemp(prefix='ivg-iter10-freshness-'));packages={}
 for fam in ['weighted_cost','ppr_walk']:
  receipt=sorted((REPO/'.g5/Verus_verification/results'/fam).glob('*-binding/receipt.json'))[-1];packages[fam]=json.loads(receipt.read_text())['inputs']
 for rel in set(old['product'])|set(old['formal'])|set().union(*[set(p) for p in packages.values()]):
  if rel.startswith('external:'):continue
  p=scratch/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/rel,p)
 results=[]
 def run(label,rel=None,formal=False,native=False,add=False):
  p=scratch/rel if rel else None;saved=p.read_bytes() if p and p.exists() else None
  if p:
   p.parent.mkdir(parents=True,exist_ok=True)
   p.write_bytes((saved or b'')+(b'\ndef new_weight_writer(conn):\n    return conn.execute("UPDATE weights SET w=1")\n' if add else b'\n'))
  r=subprocess.run([sys.executable,str(TOOL),'check',str(STAMP),'--root',str(scratch)],cwd=REPO,text=True,capture_output=True);v=json.loads(r.stdout)
  stale={fam:[k for k,h in package.items() if sha(scratch/k)!=h] for fam,package in packages.items()}
  expected=('STALE_ALL' if formal else 'REUSABLE_INPUTS','STALE_ALL' if rel and not native else 'REUSABLE_INPUTS')
  assert (v['proof'],v['correspondence'])==expected,(label,v,expected)
  for fam,package in packages.items():assert stale[fam]==([rel] if rel in package else []),(label,fam,stale)
  results.append(dict(label=label,exit=r.returncode,**v,package_stale_inputs=stale))
  if p:
   if saved is None:p.unlink()
   else:p.write_bytes(saved)
 run('fresh')
 run('cost-source','iris_src/src/Graph/KG/TraversalPaths.cls')
 run('ppr-source','iris_vector_graph/_engine/algorithms.py')
 run('cost-formal','.g5/Verus_verification/models/weighted_cost/weighted_cost.rs',formal=True)
 run('ppr-formal','.g5/Verus_verification/models/ppr_walk/ppr_walk.rs',formal=True)
 run('cost-import','.g5/Verus_verification/models/weighted_paths/weighted_paths.rs',formal=True)
 run('binding-code','.g5/Verus_verification/models/ppr_walk/binding.py')
 run('role-links','.g5/Verus_verification/crosswalk/decision-links.tsv')
 run('new-writer','iris_vector_graph/new_weight_writer.py',add=True)
 run('cost-native-fact','.g5/uplift/consolidated/iteration-10/root-cost-native.json',native=True)
 run('ppr-native-fact','.g5/uplift/consolidated/iteration-10/root-ppr-cap-native.json',native=True)
 result=dict(scratch=str(scratch),controls=results,all_expected=True,active_inputs_mutated=False,scope='Global source/formal/name/link reuse and per-package flat evidence hashes are independent. This tests freshness detection, not algorithm behavior or live provider freshness.')
 (HERE/'freshness-controls.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(controls=len(results),all_expected=True,scratch=str(scratch))))
if __name__=='__main__':main()
