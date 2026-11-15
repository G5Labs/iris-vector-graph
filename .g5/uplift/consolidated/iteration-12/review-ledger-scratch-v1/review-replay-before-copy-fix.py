"""Independent exact scratch replay; never writes active model/shared/product paths.
Usage: review-replay.py prepare MODEL SCRATCH | run SCRATCH prove|controls|binding|upstream [pytest args...]
Copies are review evidence; verifier/comparator flags remain the shared runner's.
"""
from pathlib import Path
import datetime,hashlib,importlib.util,json,os,shutil,subprocess,sys,time
REPO=Path('/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph')
OUT=REPO/'.g5/uplift/consolidated/iteration-12'
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
PY='/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python'
VERUS='/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy_file(p,q):
 q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);assert sha(p)==sha(q)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def inventory(p):return {str(x.relative_to(p)):sha(x) for x in sorted(p.rglob('*')) if x.is_file() and '__pycache__' not in x.parts}
kind=sys.argv[1]
if kind=='prepare':
 model,label=sys.argv[2:4];assert label.startswith('review-') and '/' not in label
 dest=OUT/label;dest.mkdir();root=dest/'repo';m=REPO/'.g5/Verus_verification/models'/model
 spec=json.loads((m/'model.json').read_text());inputs={}
 for p in m.iterdir():
  if p.is_file():copy_file(p,root/p.relative_to(REPO));inputs[str(p.relative_to(REPO))]=sha(p)
 for rel in spec.get('additional_inputs',[]):
  p=(m/rel).resolve();copy_file(p,root/p.relative_to(REPO));inputs[str(p.relative_to(REPO))]=sha(p)
 for rel in ['.g5/Verus_verification/run_verus.py','.g5/Verus_verification/tools/binding_common.py']:
  p=REPO/rel;copy_file(p,root/rel);inputs[rel]=sha(p)
 # Copy all exact fresh central receipt inputs, including binding-only fact helpers.
 # This is data copying: native scripts/helpers are never imported or executed.
 central=[]
 for rp in sorted((REPO/'.g5/Verus_verification/results'/model).glob('*/receipt.json')):
  body=json.loads(rp.read_text());flat=body.get('inputs',{})
  if not flat or not all((REPO/rel).is_file() and sha(REPO/rel)==h for rel,h in flat.items()):continue
  central.append(str(rp.relative_to(REPO)));shutil.copytree(rp.parent,dest/'central-receipts'/rp.parent.name)
  for rel,h in flat.items():
   pp=Path(rel)
   if pp.is_absolute():
    if not pp.is_relative_to(REPO):raise ValueError('outside-repo absolute receipt input requires explicit audit: '+rel)
    rel=str(pp.relative_to(REPO))
   p=REPO/rel;copy_file(p,root/rel);inputs[rel]=sha(p)
 # Exact public product sources/tests and checked-in native/provider source, no bytecode.
 for name in ['iris_vector_graph','iris_src','tests']:
  source=PIN/name
  shutil.copytree(source,root/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 for p in PIN.iterdir():
  if p.is_file() and (p.suffix in ('.toml','.ini','.cfg') or p.name in ('README.md','setup.py')):copy_file(p,root/p.name)
 # Source-only native fact artifacts are copied but never imported/executed.
 for iteration,prefixes in [('iteration-12',('root-',)),('iteration-11',('next-communities-',))]:
  source=REPO/'.g5/uplift/consolidated'/iteration
  for p in source.iterdir():
   if p.is_file() and p.name.startswith(prefixes):copy_file(p,root/p.relative_to(REPO))
 (root/'review_socket_guard.py').write_text("import socket,sys,pytest\nfrom unittest.mock import patch\nwith patch.object(socket.socket,'connect',side_effect=AssertionError('independent upstream forbids network')) as guard:\n code=pytest.main(sys.argv[1:])\n print('REVIEW_SOCKET_CONNECT_CALLS',guard.call_count)\n if guard.call_count: code=1\n raise SystemExit(code)\n")
 assert all(sha(root/r)==h for r,h in inputs.items()),'scratch flat inputs changed during copy'
 meta=dict(model=model,created_utc=now(),status='exact frozen scratch input before independent execution',source_inputs=inputs,central_receipts=central,product_pin='3eaa79cf77d3e0a879b2cced634cf2729d81499e',scratch_tree_sha256=inventory(root))
 (dest/'inputs.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(dict(scratch=str(dest),files=len(meta['scratch_tree_sha256']),package_inputs=inputs),indent=2));raise SystemExit(0)
assert kind=='run'
label,op=sys.argv[2:4];assert label.startswith('review-') and '/' not in label and op in ('prove','controls','binding','upstream')
dest=OUT/label;meta=json.loads((dest/'inputs.json').read_text());root=dest/'repo';model=meta['model'];m=root/'.g5/Verus_verification/models'/model
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');attempt=dest/'runs'/(stamp+'-'+op);attempt.mkdir(parents=True)
env={**os.environ,'RUN_DIR':str(dest/'run-dir'),'VERUS_BIN':VERUS,'VERUS_RUN_THREADS':'4','IVG_PIN_DIR':str(root),'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(root),'IVG_LEDGER_IDENTITY_REPO':str(REPO)}
env.pop('CONTROL',None)
command=[PY,'-B',str(root/'.g5/Verus_verification/run_verus.py'),op,str(m)] if op in ('prove','controls') else [PY,'-B',str(m/'binding.py')] if op=='binding' else [PY,'-B',str(root/'review_socket_guard.py'),*sys.argv[4:]]
record=dict(command=command,cwd=str(root),environment={k:env[k] for k in ['RUN_DIR','VERUS_BIN','VERUS_RUN_THREADS','IVG_PIN_DIR','PYTHONDONTWRITEBYTECODE','PYTHONPATH','IVG_LEDGER_IDENTITY_REPO']},utc_before=now(),inputs={r:sha(root/r) for r in meta['source_inputs']})
(attempt/'command.json').write_text(json.dumps(record,indent=2)+'\n');start=time.monotonic()
with (attempt/'raw.log').open('w') as log:result=subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
record.update(exit_code=result.returncode,elapsed_s=time.monotonic()-start,utc_after=now(),inputs_unchanged=all(sha(root/r)==h for r,h in record['inputs'].items()))
record['active_source_still_equal']={r:sha(REPO/r)==h for r,h in meta['source_inputs'].items() if (REPO/r).is_file()}
(attempt/'result.json').write_text(json.dumps(record,indent=2)+'\n');print((attempt/'raw.log').read_text());print(json.dumps(dict(attempt=str(attempt),**{k:record[k] for k in ['exit_code','elapsed_s','inputs_unchanged']})));raise SystemExit(result.returncode)
