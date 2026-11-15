"""Independent final helper/binding replay; preserves the original V1 scratch."""
import datetime,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];S=HERE/'review-fraction-v2-scratch'
PY='/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python'
PIN='/Users/ziniuw/runs/ivg-consolidated-20261114/pin'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
v=json.loads((HERE/'fraction-validation.json').read_text());assert v['verdict']=='PASS'
assert not S.exists(),'Do not overwrite an independent replay'
shutil.copytree(HERE/'review-fraction-scratch',S,ignore=shutil.ignore_patterns('run','results','__pycache__'))
files={}
def copy(rel,h):
 p=ROOT/rel
 if not p.is_file():p=Path(PIN)/rel
 assert sha(p)==h,(rel,h,sha(p))
 q=S/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);assert sha(q)==h;files[rel]=h
for p,h in v['package_inputs'].items():copy(p,h)
original=[]
for row in v['final_receipts']:
 p=ROOT/row['path'];assert sha(p)==row['sha256'];r=json.loads(p.read_text())
 q=S/'final-original-receipts'/row['path'];q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);original.append(row)
 for rel,h in r['inputs'].items():copy(rel,h)
 for rel,h in r.get('raw_log_copies',{}).items():
  p=ROOT/rel;assert sha(p)==h;q=S/'final-original-receipts'/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
start=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='V2 binding/upstream only; exact V1 formal inputs unchanged',inputs=files,original_receipts=original,native_executed=0,scratch=str(S))
(HERE/'review-fraction-v2-start.json').write_text(json.dumps(start,indent=2)+'\n')
env=os.environ.copy();env.pop('CONTROL',None);env.update(RUN_DIR=str(S/'run'),IVG_PIN_DIR=PIN,GIT_DIR=str(ROOT/'.git'),VERUS_RUN_THREADS='4',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
runs=[]
for label,cmd in [('binding',[PY,'.g5/Verus_verification/models/weighted_fraction/binding.py']),('upstream',[PY,'.g5/uplift/consolidated/iteration-11/fraction-upstream.py'])]:
 t=time.perf_counter();p=subprocess.run(cmd,cwd=S,env=env,capture_output=True,text=True,timeout=1200)
 log=HERE/('review-fraction-v2-'+label+'.log');log.write_text(p.stdout+p.stderr)
 row=dict(kind=label,command=cmd,exit=p.returncode,seconds=time.perf_counter()-t,log=str(log.relative_to(ROOT)));runs.append(row)
 stable=all(sha(ROOT/rel)==sha(S/rel)==h for rel,h in v['package_inputs'].items())
 (HERE/'review-fraction-v2-runs.json').write_text(json.dumps(dict(runs=runs,package_current_equals_scratch=stable),indent=2)+'\n');print(json.dumps(row),flush=True)
 assert stable
 if p.returncode:raise SystemExit(p.returncode)
