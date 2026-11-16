#!/usr/bin/env python3
"""Snapshot exact inputs before each verifier/binding invocation; unchanged shared runner semantics."""
import hashlib, importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path
R=Path(__file__).resolve().parents[4]
M=R/'.g5/Verus_verification/models/routine_reporting'
A=R/'.g5/uplift/consolidated/iteration-13/reporting-attempts'
P=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
V=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/venv/bin/python')
SOURCES=['iris_vector_graph/_engine/admin.py','iris_vector_graph/_engine/schema.py','iris_vector_graph/_engine/nodes_edges.py','iris_vector_graph/_engine/embeddings.py','iris_vector_graph/status.py','iris_vector_graph/security.py','iris_vector_graph/_validate.py']
ENV={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','RUN_DIR':'/Users/ziniuw/runs/ivg-iteration13-reporting-20261115','VERUS_BIN':'/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus','VERUS_RUN_THREADS':'4','IVG_PIN_DIR':str(P)}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(label, extra=None):
 d=A/(time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+str(time.time_ns())+'-'+label);d.mkdir(parents=True)
 files=[p for p in M.rglob('*') if p.is_file()]+[R/'.g5/Verus_verification/run_verus.py',Path(__file__)]
 files += [R/'.g5/uplift/consolidated/iteration-13/reporting-upstream.py'] if (R/'.g5/uplift/consolidated/iteration-13/reporting-upstream.py').exists() else []
 files += [p for p in (P/'tests/unit').glob('test_*status*.py') if p.name in ['test_230_status_counts.py','test_460_r050_status_unknown.py','test_460_r050_status_counts_every_graph.py','test_status_schema.py','test_460_status_probes.py','test_status_acceleration_label.py','test_460_r207_status_labels.py','test_engine_status.py']]
 files += [P/'tests/unit'/f for f in ['test_460_r219_counts_default_graph.py','test_460_r249_counters_default_graph.py','route_fakes_227.py','test_first_access.py']]
 files += [R/s for s in SOURCES if (R/s).exists()]+[P/s for s in SOURCES if (P/s).exists()]
 if extra: files.append(Path(extra))
 h={}
 for i,p in enumerate(files):
  target=d/'inputs'/str(i)/p.name;target.parent.mkdir(parents=True);shutil.copyfile(p,target);h[str(p)]={'sha256':sha(p),'copy':str(target.relative_to(d))}
 (d/'inputs.json').write_text(json.dumps(h,indent=2)+'\n');return d
def record(d,cmd,run):
 (d/'command.json').write_text(json.dumps({'command':cmd,'env':{k:ENV[k] for k in ['PYTHONDONTWRITEBYTECODE','RUN_DIR','VERUS_BIN','VERUS_RUN_THREADS','IVG_PIN_DIR']}},indent=2)+'\n')
 start=time.monotonic(); result=run();elapsed=time.monotonic()-start
 (d/'result.json').write_text(json.dumps({'elapsed_seconds':elapsed,'result':result},indent=2)+'\n');return result
if sys.argv[1] in ('prove','controls'):
 os.environ.update(ENV)
 path=R/'.g5/Verus_verification/run_verus.py';sp=importlib.util.spec_from_file_location('report_runner',path);mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
 original=mod.run_verus
 def wrapped(root,log,function=None):
  d=snapshot(('isolated-'+function) if function else root.stem,root)
  result=record(d,[ENV['VERUS_BIN'],str(root),'--crate-type=lib','--num-threads','4','--triggers-mode','silent']+(['--verify-root','--verify-function',function] if function else []),lambda:original(root,log,function))
  if Path(log).exists():shutil.copyfile(log,d/'raw.log')
  return result
 mod.run_verus=wrapped
 sys.exit(getattr(mod,sys.argv[1])(M))
else:
 label=sys.argv[1];d=snapshot(label)
 cmd=[str(V),'-B','-I',str(M/'binding.py')] if label=='binding' else [str(V),'-B','-I',str(R/'.g5/uplift/consolidated/iteration-13/reporting-upstream.py')]
 def run():
  p=subprocess.run(cmd,cwd=R,env=ENV,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(d/'raw.log').write_text(p.stdout);print(p.stdout);return {'exit_code':p.returncode}
 result=record(d,cmd,run);sys.exit(result['exit_code'])
