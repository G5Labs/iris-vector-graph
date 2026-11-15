"""Binding-only independent replay for an exact trailing-newline cleanup."""
import ast,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];OLD=HERE/'review-fraction-v2-scratch';NEW=HERE/'review-fraction-formatting-scratch';REL='.g5/Verus_verification/models/weighted_fraction/source_ports.py'
PY='/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=(OLD/REL).read_bytes();after=(ROOT/REL).read_bytes()
assert before==after+b'\n\n' and after.endswith(b'\n') and not after.endswith(b'\n\n')
assert ast.dump(ast.parse(before),include_attributes=False)==ast.dump(ast.parse(after),include_attributes=False)
assert sha(ROOT/REL)=='cd3e29117fd5433d75e7f725064cd37c52a69e45ba67ee7169f23c6045abf0e2'
assert not NEW.exists(),'Preserve exact prior formatting replay'
shutil.copytree(OLD,NEW,ignore=shutil.ignore_patterns('run','results','__pycache__'))
shutil.copy2(ROOT/REL,NEW/REL)
v=json.loads((HERE/'review-fraction-validation.json').read_text());package=v['final_package_hashes'];final={}
for p,h in package.items():
 final[p]=sha(ROOT/p)
 assert sha(NEW/p)==final[p]
 if p!=REL:assert final[p]==h
env=os.environ.copy();env.pop('CONTROL',None);env.update(RUN_DIR=str(NEW/'run'),IVG_PIN_DIR='/Users/ziniuw/runs/ivg-consolidated-20261114/pin',GIT_DIR=str(ROOT/'.git'),VERUS_RUN_THREADS='4',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
cmd=[PY,'.g5/Verus_verification/models/weighted_fraction/binding.py'];t=time.perf_counter();p=subprocess.run(cmd,cwd=NEW,env=env,capture_output=True,text=True,timeout=1200);seconds=time.perf_counter()-t
(HERE/'review-fraction-formatting-binding.log').write_text(p.stdout+p.stderr);assert p.returncode==0
receipts=list((NEW/'.g5/Verus_verification/results/weighted_fraction').glob('*/receipt.json'));assert len(receipts)==1;rp=receipts[0];r=json.loads(rp.read_text())
assert r['verdict']=='AGREES' and r['comparisons']==20522 and r['mismatch_count']==0 and r['socket_connect_calls']==0 and all(r['sensitivity'].values()) and len(r['sensitivity'])==11
assert len(r['typed_neighbors'])==13 and r['generic_exact_provider_worlds']==3 and len(r['unreduced_carrier_worlds'])==4
assert all(sha(ROOT/p)==sha(NEW/p)==h for p,h in final.items())
freshcmd=[PY,'.g5/Verus_verification/run_verus.py','fresh',str(rp.relative_to(NEW))];f=subprocess.run(freshcmd,cwd=NEW,capture_output=True,text=True);(HERE/'review-fraction-formatting-freshness.log').write_text(f.stdout+f.stderr);assert f.returncode==0
controls=[]
for row in v['receipts']:
 if row['kind'] in ('proof','control'):
  q=ROOT/row['path'];z=json.loads(q.read_text());assert all(sha(ROOT/k)==h for k,h in z['inputs'].items());controls.append(dict(path=row['path'],verdict=z['verdict'],inputs_current=True))
assert len(controls)==14 and sum(x['verdict']=='EXPECTED_FAIL' for x in controls)==13
out=dict(verdict='ACCEPT_FORMATTING_ONLY_FINAL_BYTES',command=cmd,elapsed_s=seconds,before_helper_sha256=hashlib.sha256(before).hexdigest(),final_helper_sha256=hashlib.sha256(after).hexdigest(),exact_change='Remove two trailing LF bytes; final file ends with one LF',ast_dump_include_attributes_false_equal=True,v2_scratch_unchanged=True,final_scratch=str(NEW),final_package_hashes=final,only_changed_package_input=REL,receipt=str(rp.relative_to(ROOT)),receipt_sha256=sha(rp),binding=dict(comparisons=20522,typed=13,ideal_nondyadic=3,unreduced=4,sensitivities=11,sockets=0,mismatches=0),fresh_command=freshcmd,fresh_exit=0,unchanged_formal_receipts=controls,proof_control_reruns=0,native_executions=0,scope='Independent formatting/current-hash supplement; no semantic/proof/control/product or coverage gain')
(HERE/'review-fraction-formatting.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(verdict=out['verdict'],seconds=seconds,receipt=out['receipt'])))
