"""Preserve exact package/helper inputs BEFORE every aggregate_results proof/control/binding command."""
from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,sys,time
ROOT=Path('/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph');MODEL=ROOT/'.g5/Verus_verification/models/aggregate_results';OUT=ROOT/'.g5/uplift/consolidated/iteration-13';PY=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python');VERUS='/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus'
kind=sys.argv[1];stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');dest=OUT/'aggregate-attempts'/(stamp+'-'+kind);dest.mkdir(parents=True)
files=[p for p in MODEL.iterdir() if p.is_file()];files += [(MODEL/p).resolve() for p in json.loads((MODEL/'model.json').read_text()).get('additional_inputs',[])];files += [ROOT/'.g5/Verus_verification/run_verus.py',ROOT/'.g5/Verus_verification/tools/binding_common.py',Path(__file__).resolve()]
if (MODEL/'binding_inputs.json').exists():files += [ROOT/p for p in json.loads((MODEL/'binding_inputs.json').read_text())]
if kind=='upstream':files.append(OUT/'aggregate-upstream.py')
entries=[]
for p in files:
 rel=p.relative_to(ROOT);q=dest/'inputs'/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);h=hashlib.sha256(p.read_bytes()).hexdigest();assert hashlib.sha256(q.read_bytes()).hexdigest()==h;entries.append(dict(path=str(rel),sha256=h,preserved=str(q.relative_to(ROOT))))
command=[str(PY),str(OUT/'aggregate-upstream.py')] if kind=='upstream' else [str(PY),str(MODEL/'probe.py')] if kind=='probe' else [str(PY),'.g5/Verus_verification/models/aggregate_results/binding.py'] if kind=='binding' else [str(PY),'.g5/Verus_verification/run_verus.py',kind,'.g5/Verus_verification/models/aggregate_results']
env={**os.environ,'RUN_DIR':'/Users/ziniuw/runs/ivg-iteration13-aggregate-20261116','VERUS_BIN':VERUS,'VERUS_RUN_THREADS':'4','PYTHONDONTWRITEBYTECODE':'1','IVG_PIN_DIR':'/Users/ziniuw/runs/ivg-consolidated-20261114/pin'}
# Base+patch are already preserved before any control verifier command. Materialize
# exact derived mutants here as well, before the shared runner generates its work copies.
if kind=='controls':
 manifest=json.loads((MODEL/'model.json').read_text());source=(MODEL/manifest['root']).read_text()
 for c in manifest['controls']:
  assert source.count(c['find'])==1
  q=dest/'pre-command-mutants'/c['name']/manifest['root'];q.parent.mkdir(parents=True,exist_ok=True);q.write_text(source.replace(c['find'],c['replace']))
meta=dict(kind=kind,utc_before_command=datetime.datetime.now(datetime.timezone.utc).isoformat(),inputs=entries,command=command,environment={k:env[k] for k in ['RUN_DIR','VERUS_BIN','VERUS_RUN_THREADS','IVG_PIN_DIR','PYTHONDONTWRITEBYTECODE']});(dest/'snapshot.json').write_text(json.dumps(meta,indent=2)+'\n');start=time.monotonic()
before=set((ROOT/'.g5/Verus_verification/results/aggregate_results').glob('*/receipt.json'))
with (dest/'raw.log').open('w') as f:result=subprocess.run(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
receipts=[]
for rp in sorted(set((ROOT/'.g5/Verus_verification/results/aggregate_results').glob('*/receipt.json'))-before):
 q=dest/'receipts'/rp.parent.name;shutil.copytree(rp.parent,q);receipts.append(str(q.relative_to(ROOT)))
meta.update(receipt_copies=receipts,exit_code=result.returncode,elapsed_s=time.monotonic()-start,utc_after_command=datetime.datetime.now(datetime.timezone.utc).isoformat(),originals_unchanged=all(hashlib.sha256((ROOT/e['path']).read_bytes()).hexdigest()==e['sha256'] for e in entries));(dest/'result.json').write_text(json.dumps(meta,indent=2)+'\n');print((dest/'raw.log').read_text());print('EXACT_ATTEMPT',dest.relative_to(ROOT),'seconds',meta['elapsed_s']);sys.exit(result.returncode)
