"""Run unchanged shared runner with pre-execution exact package/mutant snapshots.
Only records inputs; does not alter verifier flags, result, comparator or model.
"""
import datetime as dt,hashlib,importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];MODEL=REPO/'.g5/Verus_verification/models/ledger_content';ATT=HERE/'ledger-content-attempts'
os.environ['VERUS_BIN']='/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus';os.environ['VERUS_RUN_THREADS']='4';os.environ['RUN_DIR']='/Users/ziniuw/runs/ivg-iteration12-ledger-content-20261115';os.environ['IVG_PIN_DIR']='/Users/ziniuw/runs/ivg-consolidated-20261114/pin'
def snapshot(root=None,function=None,phase='binding'):
 stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');dest=ATT/(stamp+'-'+phase);dest.mkdir(parents=True)
 for label,base in [('package',MODEL),('executed',root.parent if root else MODEL)]:
  shutil.copytree(base,dest/label)
 for source in [Path(__file__).resolve(),REPO/'.g5/Verus_verification/run_verus.py']:
  out=dest/'harness'/source.name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,out)
 manifest=json.loads((MODEL/'model.json').read_text())
 for dep in manifest.get('additional_inputs',[]):
  p=(MODEL/dep).resolve();out=dest/'dependencies'/p.relative_to(REPO);out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)
 if phase=='binding':
  pin=Path(os.environ['IVG_PIN_DIR'])
  for src in (pin/'iris_vector_graph').rglob('*.py'):
   out=dest/'product-pin'/src.relative_to(pin);out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,out)
  src=REPO/'.g5/Verus_verification/tools/binding_common.py';shutil.copyfile(src,dest/'harness'/src.name)
  evidence=set()
  for name in ['root-ledger-native','root-ledger-qualkeys-native','root-ledger-qualkeys-followup','root-ledger-marker-native']:
   q=HERE/(name+'.json');j=json.loads(q.read_text())
   evidence.update(HERE/(name+'.'+ext) for ext in ['py','json','log'])
   for section in ['inputs','source_inputs']:
    evidence.update(Path(rel) if Path(rel).is_absolute() else REPO/rel for rel in j.get(section,{}))
  for src in evidence:
   out=dest/'native-inputs'/src.relative_to(REPO);out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,out)
 j=dict(phase=phase,root=str(root) if root else None,function=function,created_before_execute=True,inputs={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()})
 (dest/'inputs.json').write_text(json.dumps(j,indent=2)+'\n');return dest
if sys.argv[1]=='binding':
 dest=snapshot();p=subprocess.run(['/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python','-B','-I',str(MODEL/'binding.py')],cwd=REPO,capture_output=True,text=True);(dest/'command.log').write_text(p.stdout+p.stderr);print(p.stdout);
 if p.returncode:print('\n'.join(p.stderr.splitlines()[-30:]))
 raise SystemExit(p.returncode)
spec=importlib.util.spec_from_file_location('ledger_content_shared_runner',REPO/'.g5/Verus_verification/run_verus.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);original=r.run_verus
def wrapped(root,log,function=None):
 dest=snapshot(root,function,'verify-'+(function or 'full'));result=original(root,log,function);(dest/'observed.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copyfile(log,dest/'command.log');return result
r.run_verus=wrapped
raise SystemExit(r.prove(MODEL) if sys.argv[1]=='prove' else r.controls(MODEL))
