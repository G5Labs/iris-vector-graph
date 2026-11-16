"""Exact ordinary scratch replay from sealed shared tooling; no active/shared/product mutations.
prepare MODEL review-LABEL | run review-LABEL prove|controls|binding|upstream [pytest args]
"""
from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,sys,time
REPO=Path('/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph');OUT=Path(__file__).resolve().parent;PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
PY='/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python';VERUS='/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);assert sha(p)==sha(q)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def inventory(p):return {str(x.relative_to(p)):sha(x) for x in sorted(p.rglob('*')) if x.is_file() and not x.is_symlink() and '__pycache__' not in x.parts}
def gitdir():
 p=REPO/'.git'
 if p.is_file():
  s=p.read_text().strip();assert s.startswith('gitdir: ');return (REPO/s[8:]).resolve()
 assert p.is_dir();return p.resolve()
mode=sys.argv[1]
if mode=='prepare':
 model,label=sys.argv[2:4];assert model in ('rdf_reporting','ndjson_export') and label.startswith('review-') and '/' not in label
 dest=OUT/label;dest.mkdir();root=dest/'repo';m=REPO/'.g5/Verus_verification/models'/model;spec=json.loads((m/'model.json').read_text());inputs={};central=[]
 for p in m.iterdir():
  if p.is_file():copy(p,root/p.relative_to(REPO));inputs[str(p.relative_to(REPO))]=sha(p)
 for rel in spec.get('additional_inputs',[]):
  p=(m/rel).resolve();assert p.is_relative_to(REPO);copy(p,root/p.relative_to(REPO));inputs[str(p.relative_to(REPO))]=sha(p)
 for rel in ['.g5/Verus_verification/run_verus.py','.g5/Verus_verification/tools/binding_common.py']:
  p=REPO/rel;copy(p,root/rel);inputs[rel]=sha(p)
 for rp in sorted((REPO/'.g5/Verus_verification/results'/model).glob('*/receipt.json')):
  body=json.loads(rp.read_text());flat=body.get('inputs',{})
  if not flat or not all((REPO/rel).is_file() and sha(REPO/rel)==h for rel,h in flat.items()):continue
  central.append(str(rp.relative_to(REPO)));shutil.copytree(rp.parent,dest/'central-receipts'/rp.parent.name)
  for rel,h in flat.items():
   p=Path(rel) if Path(rel).is_absolute() else REPO/rel;assert p.resolve().is_relative_to(REPO)
   rel=str(p.relative_to(REPO));copy(p,root/rel);inputs[rel]=sha(p)
 for name in ['iris_vector_graph']:
  if (PIN/name).is_dir():shutil.copytree(PIN/name,root/name,dirs_exist_ok=True,symlinks=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 for p in PIN.iterdir():
  if p.is_file() and not p.is_symlink() and (p.suffix in ('.toml','.ini','.cfg','.json') or p.name in ('README.md','setup.py')):copy(p,root/p.name)
 copy(OUT/'review-bootstrap.py',root/'review_bootstrap.py')
 (root/'review_upstream.py').write_text("import pytest,sys\nraise SystemExit(pytest.main(sys.argv[1:]))\n")
 assert all(sha(root/r)==h for r,h in inputs.items())
 meta={'model':model,'created_utc':now(),'status':'exact final frozen source before independent execution','source_inputs':inputs,'central_receipts':central,'product_pin':'3eaa79cf77d3e0a879b2cced634cf2729d81499e','scratch_tree_sha256':inventory(root),'read_only_git_dir':str(gitdir()),'interrupted_inputs_opened_or_reused':False}
 (dest/'inputs.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({'scratch':str(dest),'files':len(meta['scratch_tree_sha256']),'flat_inputs':len(inputs)}));raise SystemExit(0)
assert mode=='run';label,op=sys.argv[2:4];assert label.startswith('review-') and '/' not in label and op in ('prove','controls','binding','upstream')
dest=OUT/label;meta=json.loads((dest/'inputs.json').read_text());root=dest/'repo';model=meta['model'];m=root/'.g5/Verus_verification/models'/model
attempt=dest/'runs'/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-'+op);attempt.mkdir(parents=True)
env={**os.environ,'RUN_DIR':str(dest/'run-dir'),'VERUS_BIN':VERUS,'VERUS_RUN_THREADS':'4','IVG_PIN_DIR':str(root),'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(root),'REVIEW_SUBPROCESS_LOG':str(attempt/'subprocess.jsonl'),'GIT_DIR':meta['read_only_git_dir'],'GIT_WORK_TREE':str(root),'GIT_OPTIONAL_LOCKS':'0'};env.pop('CONTROL',None)
if op=='upstream':env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',SKIP_IRIS_TESTS='true')
target=[str(root/'.g5/Verus_verification/run_verus.py'),op,str(m)] if op in ('prove','controls') else [str(m/'binding.py')] if op=='binding' else [str(root/'review_upstream.py'),*sys.argv[4:]]
command=[PY,'-B',str(root/'review_bootstrap.py'),*target]
for src,name in [(Path(__file__),'review-replay-exact.py'),(root/'review_bootstrap.py','review-bootstrap-exact.py')]:copy(src,attempt/name)
if op=='upstream':copy(root/'review_upstream.py',attempt/'review-upstream-exact.py')
# Retain every declared package/dependency byte before each command, not only hashes.
exact=attempt/'exact-inputs'
for rel in meta['source_inputs']:
 copy(root/rel,exact/rel)
record={'command':command,'cwd':str(root),'environment':{k:env[k] for k in ['RUN_DIR','VERUS_BIN','VERUS_RUN_THREADS','IVG_PIN_DIR','PYTHONDONTWRITEBYTECODE','PYTHONPATH','REVIEW_SUBPROCESS_LOG','GIT_DIR','GIT_WORK_TREE','GIT_OPTIONAL_LOCKS','PYTEST_DISABLE_PLUGIN_AUTOLOAD','SKIP_IRIS_TESTS'] if k in env},'utc_before':now(),'inputs':{r:sha(root/r) for r in meta['source_inputs']},'bootstrap_sha256':sha(root/'review_bootstrap.py'),'wrapper_sha256':sha(Path(__file__))};(attempt/'command.json').write_text(json.dumps(record,indent=2)+'\n');start=time.monotonic()
with (attempt/'raw.log').open('w') as log:result=subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
events=[json.loads(s) for s in (attempt/'subprocess.jsonl').read_text().splitlines()] if (attempt/'subprocess.jsonl').exists() else [];git=[e for e in events if Path(e['argv'][0]).name=='git']
record.update(exit_code=result.returncode,elapsed_s=time.monotonic()-start,utc_after=now(),inputs_unchanged=all(sha(root/r)==h for r,h in record['inputs'].items()),active_source_still_equal={r:sha(REPO/r)==h for r,h in meta['source_inputs'].items()},git_read_commands=git,git_read_count=len(git),git_mutations=0)
(attempt/'result.json').write_text(json.dumps(record,indent=2)+'\n');print((attempt/'raw.log').read_text());print(json.dumps({'attempt':str(attempt),'exit_code':record['exit_code'],'elapsed_s':record['elapsed_s'],'inputs_unchanged':record['inputs_unchanged'],'git_read_count':len(git)}));raise SystemExit(result.returncode)
