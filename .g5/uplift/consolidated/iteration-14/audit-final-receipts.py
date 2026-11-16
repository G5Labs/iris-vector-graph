"""Root-only current14 final receipts and complete copied raw-log audit; no execution/reverification."""
from pathlib import Path
import hashlib,json,re,time
R=Path.cwd();V=R/'.g5/Verus_verification';A=R/'.g5/uplift/consolidated/iteration-14';start=time.monotonic();failures=[];records=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,message):
 if not ok:failures.append(message)
resource=re.compile(r'resource\s+limit|rlimit[^\n]*exceeded|timed\s+out|timeout|internal\s+error',re.I)
def audit(path,verdict,model):
 d=json.loads(path.read_text());label=str(path.relative_to(R));require(d.get('verdict')==verdict,label+': wrong verdict')
 for rel,h in d.get('inputs',{}).items():require((R/rel).is_file() and sha(R/rel)==h,label+': stale input '+rel)
 observed=d.get('observed',{});require(not observed.get('timed_out'),label+': timed out');require(not observed.get('has_resource_limit'),label+': resource flag')
 logs={}
 for rel,h in d.get('raw_log_copies',{}).items():
  p=R/rel;require(p.is_file() and sha(p)==h,label+': copied log missing/hash mismatch '+rel)
  if p.is_file():
   text=p.read_text(errors='replace');hits=resource.findall(text);require(not hits,label+': raw log resource/internal failure '+rel);logs[p.name]=dict(path=rel,sha256=sha(p),resource_hits=hits)
 if verdict in ['PASS','EXPECTED_FAIL']:require(Path(observed.get('raw_log','missing')).name in logs,label+': missing full raw copy')
 if verdict=='PASS':require(observed.get('verified')==model['expected_verified'] and observed.get('errors')==0,label+': wrong prove count/errors')
 if verdict=='EXPECTED_FAIL':
  require(isinstance(observed.get('errors'),int) and observed['errors']>0 and observed.get('exit_code')==1,label+': not ordinary full failure');require(bool(logs),label+': no raw copies')
  targets=d.get('control',{}).get('expect_fail_in',[]);require(bool(targets),label+': no named target')
  for fn in targets:
   x=observed.get('per_function',{}).get(fn,{});require(isinstance(x.get('errors'),int) and x['errors']>0 and x.get('verified') is not None and not x.get('timed_out'),label+': named target not ordinary '+fn)
   name=Path(x.get('raw_log','missing')).name;require(name in logs,label+': missing named raw copy '+fn)
 records.append(dict(receipt=label,sha256=sha(path),verdict=d.get('verdict'),kind=d.get('kind'),controls=d.get('control',{}).get('name'),inputs=len(d.get('inputs',{})),raw_logs=list(logs.values())))
for name in ['rdf_reporting','ndjson_export']:
 spec=json.loads((V/'models'/name/'model.json').read_text());P=V/'results'/name
 proves=sorted(P.glob('*-prove/receipt.json'));require(bool(proves),name+': no prove')
 if proves:audit(proves[-1],'PASS',spec)
 latest={}
 for p in sorted(P.glob('*-control-*/receipt.json')):
  d=json.loads(p.read_text());latest[d['control']['name']]=p
 for c in spec['controls']:
  require(c['name'] in latest,name+': missing control '+c['name'])
  if c['name'] in latest:audit(latest[c['name']],'EXPECTED_FAIL',spec)
 binds=sorted(P.glob('*-binding/receipt.json'));require(bool(binds),name+': no binding')
 if binds:audit(binds[-1],'AGREES',spec)
out=dict(verdict='PASS_FRESH_CURRENT14_FULL_AND_NAMED_RAW_LOG_AUDIT' if not failures else 'FAILED_OR_INCOMPLETE',receipts=records,count=len(records),failures=failures,elapsed_s=time.monotonic()-start,scope='Only final selected ordinary14 packages. Every declared receipt input and every copied full/named raw log checked; resource NOTE lines included. No solver/binding/product/native/network execution, older/incomplete controls reused, or interrupted input assessment. Independent review audits input completeness and source semantics separately.')
(A/'root-final-receipt-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(verdict=out['verdict'],receipts=len(records),failures=failures,elapsed_s=out['elapsed_s'])));raise SystemExit(0 if not failures else 1)
