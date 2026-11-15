"""Reviewer sensitivity: omit only fixed phase TTL, retain strengthened contract."""
import hashlib,json,shutil,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];SRC=ROOT/'.g5/Verus_verification/models/vector_admission';OUT=HERE/'review-vector-ttl-challenge-inputs'
assert not OUT.exists(),'Preserve prior reviewer challenge'
OUT.mkdir();inputs={}
for p in SRC.glob('*.rs'):
 q=OUT/p.name;shutil.copy2(p,q);inputs[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
p=OUT/'vector_admission.rs';s=p.read_text();assert s.count('ttl:r.ttl,..z.request')==1;s=s.replace('ttl:r.ttl,..z.request','..z.request');p.write_text(s)
cmd=['/Users/ziniuw/.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus',str(p),'--crate-type=lib','--num-threads','4','--triggers-mode','silent']
t=time.perf_counter();v=subprocess.run(cmd,cwd=OUT,capture_output=True,text=True,timeout=1200);seconds=time.perf_counter()-t;raw=v.stdout+v.stderr
(HERE/'review-vector-ttl-challenge.log').write_text(raw)
good=v.returncode!=0 and '76 verified, 1 errors' in raw and 'postcondition not satisfied' in raw and 'request.ttl==v[0].request.ttl' in raw and 'resource limit exceeded' not in raw and 'timed out' not in raw
out=dict(verdict='EXPECTED_FAIL' if good else 'UNEXPECTED',command=cmd,exit=v.returncode,seconds=seconds,original_inputs=inputs,mutant_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),patch=dict(find='ttl:r.ttl,..z.request',replace='..z.request'),unchanged_claim='workflow::theorem_all_search_phases_keep_original_scope TTL postcondition',scope='Extra independent reviewer sensitivity, not a ninth package control or new product issue')
(HERE/'review-vector-ttl-challenge.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out));assert good
