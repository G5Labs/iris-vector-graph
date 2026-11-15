"""Exact frozen fraction scratch preparation/replay, never runs native scripts."""
import datetime,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];S=HERE/'review-fraction-scratch';PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');PY=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python');VERUS=Path('/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
validation=json.loads((HERE/'fraction-validation.json').read_text());assert validation['verdict']=='PASS';files={};origin=[]
def copy(rel,want=None):
 src=ROOT/rel;dst=S/rel
 if not src.is_file():src=PIN/rel
 assert src.is_file(),(rel,src)
 if want is not None:assert sha(src)==want,(rel,want,sha(src))
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);assert sha(dst)==sha(src);files[rel]=sha(dst)
for rel,want in validation['package_inputs'].items():copy(rel,want)
for entry in validation['final_receipts']:
 src=ROOT/entry['path'];assert sha(src)==entry['sha256'];d=json.loads(src.read_text());origin.append((entry['path'],d))
 out=S/'original-receipts'/entry['path'];out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out)
 for rel,want in d['inputs'].items():copy(rel,want)
 for rel,want in d.get('raw_log_copies',{}).items():
  p=S/'original-receipts'/rel;p.parent.mkdir(parents=True,exist_ok=True);assert sha(ROOT/rel)==want;shutil.copy2(ROOT/rel,p)
for rel in ['.g5/Verus_verification/run_verus.py','.g5/Verus_verification/tools/binding_common.py','.g5/uplift/consolidated/iteration-11/fraction-upstream.py','.g5/uplift/consolidated/iteration-11/fraction-upstream.json','.g5/uplift/consolidated/iteration-11/fraction-upstream.log']:copy(rel)
up=json.loads((HERE/'fraction-upstream.json').read_text())
for rel,want in up['files'].items():copy(rel,want)
model=S/'.g5/Verus_verification/models/weighted_fraction';src=(model/'weighted_fraction.rs').read_text();decl=list(re.finditer(r'\b(proof|spec)\s+fn\s+([A-Za-z_]\w*)',re.sub(r'//[^\n]*','',src)));specs=[]
clean=re.sub(r'//[^\n]*','',src)
for i,m in enumerate(decl):
 seg=clean[m.start():decl[i+1].start() if i+1<len(decl) else len(clean)];header=seg.split('{',1)[0]
 if m.group(1)=='spec' and re.search(r'\bdecreases\b',header):specs.append(m.group(2))
counts={'new_proof_declarations':sum(x.group(1)=='proof' for x in decl),'named_theorems':sum(x.group(1)=='proof' and x.group(2).startswith('theorem_') for x in decl),'recursive_spec_names':specs,'nonlinear_subqueries':len(re.findall(r'\bby\s*\(\s*nonlinear_arith\s*\)',clean))}
assert counts['new_proof_declarations']==65 and counts['named_theorems']==38 and len(specs)==9 and counts['nonlinear_subqueries']==19
start={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'EXACT_FROZEN_INPUT_COPY','root_package_inputs':validation['package_inputs'],'all_copied_inputs':files,'counts':counts,'source_model_changed':False,'native_executed':0,'original_receipts':len(origin),'scratch':str(S)}
(HERE/'review-fraction-start.json').write_text(json.dumps(start,indent=2)+'\n')
if '--prepare-only' in sys.argv:print(json.dumps({'prepared':len(files),'counts':counts}));raise SystemExit(0)
env=os.environ.copy();env.pop('CONTROL',None);env.update(RUN_DIR=str(S/'run'),IVG_PIN_DIR=str(PIN),GIT_DIR=str(ROOT/'.git'),VERUS_BIN=str(VERUS),VERUS_RUN_THREADS='4',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
commands=[('prove',[str(PY),'.g5/Verus_verification/run_verus.py','prove','.g5/Verus_verification/models/weighted_fraction']),('controls',[str(PY),'.g5/Verus_verification/run_verus.py','controls','.g5/Verus_verification/models/weighted_fraction']),('binding',[str(PY),'.g5/Verus_verification/models/weighted_fraction/binding.py']),('upstream',[str(PY),'.g5/uplift/consolidated/iteration-11/fraction-upstream.py'])];runs=[]
for label,cmd in commands:
 log=HERE/('review-fraction-'+label+'.log');t=time.perf_counter();p=subprocess.run(cmd,cwd=S,env=env,capture_output=True,text=True,timeout=1200);elapsed=time.perf_counter()-t;log.write_text(p.stdout+p.stderr);row={'label':label,'command':cmd,'exit_code':p.returncode,'elapsed_s':elapsed,'log':str(log.relative_to(ROOT))};runs.append(row)
 (HERE/'review-fraction-runs.json').write_text(json.dumps({'runs':runs,'all_core_hashes_still_equal':all(sha(ROOT/p)==sha(S/p)==h for p,h in validation['package_inputs'].items())},indent=2)+'\n');print(json.dumps(row),flush=True)
 if p.returncode:raise SystemExit(p.returncode)
assert all(sha(ROOT/p)==sha(S/p)==h for p,h in validation['package_inputs'].items())
