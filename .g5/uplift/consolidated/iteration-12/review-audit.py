"""Independent current/scratch receipt, raw control, package and result audit."""
from pathlib import Path
import datetime,hashlib,json,re,shutil,time
REPO=Path('/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph');HERE=Path(__file__).resolve().parent
CONFIG={'ledger_content':('review-ledger-scratch-v2',108,21,4023,82,8,155),'communities':('review-communities-scratch-v1',73,12,1255,9,14,19)}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit_receipt(path,root):
 b=json.loads(path.read_text());fresh=all((root/rel).is_file() and sha(root/rel)==h for rel,h in b['inputs'].items());assert fresh,path
 logs=[]
 for rel,h in b.get('raw_log_copies',{}).items():
  p=root/rel;assert p.is_file() and sha(p)==h,p
  s=p.read_text();ordinary=bool(re.search(r'(?:assertion failed|postcondition not satisfied|precondition not satisfied)',s));bad=bool(re.search(r'rlimit.{0,100}exceeded|resource limit|timed out|internal error',s,re.I));logs.append(dict(path=str(p.relative_to(root)),sha256=h,ordinary_failure=ordinary,resource_or_timeout=bad))
 if b['kind']=='control':
  obs=b['observed'];assert b['verdict']=='EXPECTED_FAIL' and obs['errors']>0 and not obs['timed_out'] and not obs['has_resource_limit'],path
  assert all(v['errors']>0 and not v['timed_out'] for v in obs['per_function'].values()),path
  assert len(logs)==1+len(obs['per_function']) and all(x['ordinary_failure'] and not x['resource_or_timeout'] for x in logs),path
 return dict(path=str(path.relative_to(root)),sha256=sha(path),kind=b['kind'],control=b.get('control',{}).get('name'),verdict=b['verdict'],fresh=fresh,logs=logs),b
all_results={};start=time.monotonic()
for model,(label,total,ncontrols,ncompare,nhistory,nsens,nupstream) in CONFIG.items():
 scratch=HERE/label;root=scratch/'repo';meta=json.loads((scratch/'inputs.json').read_text());d=root/'.g5/Verus_verification/models'/model;manifest=json.loads((d/'model.json').read_text());package={str(p.relative_to(root)):sha(p) for p in d.iterdir() if p.is_file()}
 equal={rel:sha(REPO/rel)==h==meta['source_inputs'][rel] for rel,h in package.items()};assert all(equal.values()),equal
 for rel,h in meta['source_inputs'].items():assert sha(root/rel)==h==sha(REPO/rel),(model,rel)
 receipts=[];bodies=[]
 for rp in sorted((root/'.g5/Verus_verification/results'/model).glob('*/receipt.json')):
  a,b=audit_receipt(rp,root);receipts.append(a);bodies.append(b)
 assert len(receipts)==ncontrols+2 and sum(x['kind']=='control' for x in receipts)==ncontrols
 proof=next(x for x in bodies if x['kind']=='proof');bind=next(x for x in bodies if x['kind']=='binding');assert proof['verdict']=='PASS' and proof['observed']['verified']==total and proof['observed']['errors']==0
 assert bind['verdict']=='AGREES' and bind['comparisons']==ncompare and bind['mismatch_count']==0 and bind['socket_connect_calls']==0 and len(bind['sensitivity'])==nsens and all(bind['sensitivity'].values())
 if model=='ledger_content':
  assert bind['histories']==nhistory and len(bind['raw_reader_neighbors'])==6 and all(bind['raw_reader_neighbors']) and len(bind['alternate_typed_port_readers'])==7 and all(bind['alternate_typed_port_readers']) and bind['bound_neighbor'] and bind['known_lifecycle']['agrees'] and bind['native_audit']['agrees']
  frozen=json.loads((HERE/'ledger-content-validation.json').read_text());central=[x['receipt'] for x in frozen['final_receipts']];assert frozen['fresh_receipts']==23
 else:
  assert len(bind['histories'])==nhistory and all(x['agrees'] for x in bind['histories']) and len(bind['effect_checks'])==6 and all(bind['effect_checks'].values()) and bind['native_executions']==0
  frozen=json.loads((HERE/'communities-freeze.json').read_text());central=frozen['current_receipts']
 central_rows=[audit_receipt(REPO/rel,REPO)[0] for rel in central];assert len(central_rows)==ncontrols+2
 runs=[]
 for run in sorted((scratch/'runs').iterdir()):
  j=json.loads((run/'result.json').read_text());assert j['inputs_unchanged'] and all(j['active_source_still_equal'].values());runs.append(dict(path=str(run.relative_to(HERE)),op=run.name.split('-',1)[1],exit_code=j['exit_code'],elapsed_s=j['elapsed_s'],log_sha256=sha(run/'raw.log')))
 good=[x for x in runs if x['op']=='upstream' and x['exit_code']==0];assert len(good)==1
 text=(HERE/good[0]['path']/'raw.log').read_text();assert f'{nupstream} passed' in text and 'REVIEW_SOCKET_CONNECT_CALLS 0' in text
 result=dict(verdict='PASS_BOUNDED_FRAGMENT',package=package,current_equals_scratch=equal,scratch_receipts=receipts,central_receipts=central_rows,expected_verified=total,controls=ncontrols,controls_full_and_named_ordinary=True,bindings=dict(comparisons=ncompare,histories=nhistory,sensitivities=nsens,socket_calls=0),upstream_passed=nupstream,runs=runs,measured_command_elapsed_s=sum(x['elapsed_s'] for x in runs),limits='Source correspondence/provider/role qualifications remain as in independent review; no body verification or external grade.')
 all_results[model]=result
 preserved=HERE/('review-'+model.replace('_','-')+'-central-freeze.json');preserved.write_text(json.dumps(frozen,indent=2)+'\n')
 (HERE/('review-'+model.replace('_','-')+'-validation.json')).write_text(json.dumps(result,indent=2)+'\n')
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),verdict='PASS_BOUNDED_FRAGMENTS',models=all_results,counts=dict(verified_total=181,new_units=170,imported_unchanged=11,new_ordinary_proof_queries=149,new_recursive_spec_queries=21,new_nonlinear_subqueries=0,extra_checked_decreases_by_hint_declarations=1,formal_controls=33,current_central_fresh_receipts=37,scratch_fresh_receipts=37),audit_elapsed_s=time.monotonic()-start,reviewer_native_calls=0,private_evaluator_inspected=False)
(HERE/'review-final-validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(verdict=out['verdict'],counts=out['counts'],commands_s={k:v['measured_command_elapsed_s'] for k,v in all_results.items()},audit_s=out['audit_elapsed_s'])))
