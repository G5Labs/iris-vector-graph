"""Exact independent vector candidate replay. Never executes native scripts."""
import datetime,hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];S=HERE/'review-vector-v2-scratch';PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
PY='/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python';VERUS='/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not S.exists(),'Do not overwrite an independent replay'
files={};package={};original=[]
def copy(rel,h=None):
 src=ROOT/rel
 if not src.is_file():src=PIN/rel
 assert src.is_file(),rel
 if h is not None:assert sha(src)==h,(rel,h,sha(src))
 q=S/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,q);assert sha(q)==sha(src);files[rel]=sha(q)
model=ROOT/'.g5/Verus_verification/models/vector_admission'
for p in [*sorted(model.glob('*.rs')),model/'model.json',model/'binding.py',model/'port.py',model/'NOTES.md']:
 rel=str(p.relative_to(ROOT));copy(rel);package[rel]=sha(p)
assert package[str((model/'vector_admission.rs').relative_to(ROOT))]=='167d5d385daad2c4644b45324d725b9ec5a2113332a395c759cf91fc8366d130'
assert package[str((model/'model.json').relative_to(ROOT))]=='d66a2896070991db3935a3927a246ce57a52bf495e0a1fa57cdcc4c57fd584d6'
assert package[str((model/'binding.py').relative_to(ROOT))]=='c5126dedb2502f2e1e4573750d1312a57321f6f9411444f7fc0fb3d69d867b66'
v=[]
for receipt in sorted((ROOT/'.g5/Verus_verification/results/vector_admission').glob('*/receipt.json')):
 data=json.loads(receipt.read_text())
 if data.get('inputs',{}).get('.g5/Verus_verification/models/vector_admission/vector_admission.rs')=='167d5d385daad2c4644b45324d725b9ec5a2113332a395c759cf91fc8366d130':v.append(dict(receipt=str(receipt.relative_to(ROOT)),verdict=data['verdict']))
assert len(v)==10 and sum(x['verdict']=='EXPECTED_FAIL' for x in v)==8
for row in v:
 p=ROOT/row['receipt'];r=json.loads(p.read_text());original.append(dict(path=row['receipt'],sha256=sha(p)))
 q=S/'original-receipts'/row['receipt'];q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
 for rel,h in r['inputs'].items():copy(rel,h)
 for rel,h in r.get('raw_log_copies',{}).items():
  p=ROOT/rel;assert sha(p)==h;q=S/'original-receipts'/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
for rel in ['.g5/Verus_verification/run_verus.py','.g5/Verus_verification/tools/binding_common.py','.g5/uplift/consolidated/iteration-11/vector-upstream-units.py','.g5/uplift/consolidated/iteration-11/vector-upstream-units.json','.g5/uplift/consolidated/iteration-11/review-native-audit.py','.g5/uplift/consolidated/iteration-11/review-native-audit.json','.g5/uplift/consolidated/iteration-11/root-vector-attempt1-predictions.md','.g5/uplift/consolidated/iteration-11/root-vector-attempt1-provenance.json']:copy(rel)
up=json.loads((HERE/'vector-upstream-units.json').read_text())
for p,h in up['source_inputs'].items():copy(str(Path(p).relative_to(PIN)),h)
count={};allnames=[]
for p in sorted(model.glob('*.rs')):
 text=re.sub(r'//[^\n]*','',p.read_text());decl=list(re.finditer(r'\b(proof|spec)\s+fn\s+([A-Za-z_]\w*)',text));recursive=[];proof=[]
 for i,m in enumerate(decl):
  if m.group(1)=='proof':proof.append(m.group(2))
  else:
   head=text[m.start():decl[i+1].start() if i+1<len(decl) else len(text)].split('{',1)[0]
   if re.search(r'\bdecreases\b',head):recursive.append(m.group(2))
 count[p.name]=dict(proof_declarations=proof,recursive_specs=recursive,nonlinear_subqueries=len(re.findall(r'\bby\s*\(\s*nonlinear_arith\s*\)',text)));allnames+=proof
assert len(allnames)==51 and sum(x.startswith('theorem_') for x in allnames)==45 and sum(len(x['recursive_specs']) for x in count.values())==26 and sum(x['nonlinear_subqueries'] for x in count.values())==0
(HERE/'review-vector-v2-start.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),package_inputs=package,all_copied_inputs=files,counts=count,original_receipts=original,scratch=str(S),native_executed=0),indent=2)+'\n')
env=os.environ.copy();env.pop('CONTROL',None);env.update(RUN_DIR=str(S/'run'),IVG_PIN_DIR=str(PIN),GIT_DIR=str(ROOT/'.git'),VERUS_BIN=VERUS,VERUS_RUN_THREADS='4',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
runs=[]
for label,cmd in [('proof',[PY,'.g5/Verus_verification/run_verus.py','prove','.g5/Verus_verification/models/vector_admission']),('controls',[PY,'.g5/Verus_verification/run_verus.py','controls','.g5/Verus_verification/models/vector_admission']),('binding',[PY,'.g5/Verus_verification/models/vector_admission/binding.py']),('upstream',[PY,'.g5/uplift/consolidated/iteration-11/vector-upstream-units.py'])]:
 t=time.perf_counter();r=subprocess.run(cmd,cwd=S,env=env,capture_output=True,text=True,timeout=1200);log=HERE/('review-vector-v2-'+label+'.log');log.write_text(r.stdout+r.stderr)
 row=dict(kind=label,command=cmd,exit=r.returncode,seconds=time.perf_counter()-t,log=str(log.relative_to(ROOT)));runs.append(row)
 stable=all(sha(ROOT/p)==sha(S/p)==h for p,h in package.items())
 (HERE/'review-vector-v2-runs.json').write_text(json.dumps(dict(runs=runs,all_package_hashes_current_equals_scratch=stable),indent=2)+'\n');print(json.dumps(row),flush=True);assert stable
 if r.returncode:raise SystemExit(r.returncode)
