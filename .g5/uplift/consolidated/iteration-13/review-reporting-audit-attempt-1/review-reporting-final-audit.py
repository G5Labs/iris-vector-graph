"""Independent exact ordinary reporting package/control/binding/current-input audit."""
from pathlib import Path
import json,hashlib,re,datetime,time
R=Path(__file__).resolve().parents[4];H=Path(__file__).resolve().parent;D=H/'review-reporting-scratch-v1';S=D/'repo';M=Path('.g5/Verus_verification/models/routine_reporting');start=time.monotonic()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def receipt(p,root):
 j=json.loads(p.read_text());assert all((root/k).is_file() and sha(root/k)==v for k,v in j['inputs'].items()),p
 logs=[]
 for rel,h in j.get('raw_log_copies',{}).items():
  q=root/rel;assert sha(q)==h;s=q.read_text();ordinary=bool(re.search('assertion failed|postcondition not satisfied|precondition not satisfied',s));bad=bool(re.search('rlimit.{0,100}exceeded|resource limit|timed out|internal error',s,re.I));logs.append({'path':str(q.relative_to(root)),'sha256':h,'ordinary':ordinary,'resource_or_timeout':bad})
 if j['kind']=='control':
  o=j['observed'];assert j['verdict']=='EXPECTED_FAIL' and o['errors']>0 and not o['timed_out'] and not o['has_resource_limit'];assert all(x['errors']>0 and not x['timed_out'] for x in o['per_function'].values());assert len(logs)==1+len(o['per_function']) and all(x['ordinary'] and not x['resource_or_timeout'] for x in logs)
 if j['kind']=='binding':assert j['verdict']=='AGREES' and j['comparisons']==11204 and j['worlds']==156 and j['mismatch_count']==0 and j['socket_connect_calls']==j['native_executions']==0 and len(j['sensitivity'])==8 and all(j['sensitivity'].values()) and sha(p.parent/j['detail'])==j['detail_sha256']
 return {'path':str(p.relative_to(root)),'sha256':sha(p),'kind':j['kind'],'verdict':j['verdict'],'flat_inputs':len(j['inputs']),'logs':logs},j
expected={'routine_reporting.rs':'224e16eede8fda124658933601d304ffe1a0a2ce92edfc802e5c612cebfa4a8d','model.json':'476529fece46dfdfebe64114446c9966bf6a4a68c3e07594a5e880e8c7618bac','binding.py':'966e7ee43aba8c602c8b98fc33a95ee57efef2772afdc2b1de04b5d0f750c8fb','NOTES.md':'b6a8476828e94590ae65f32dea16bf50d2816e3b7d32a771324f8e319da85154'}
assert all(sha(R/M/k)==sha(S/M/k)==v for k,v in expected.items());meta=json.loads((D/'inputs.json').read_text());assert all(sha(S/k)==sha(R/k)==v for k,v in meta['source_inputs'].items())
scratch=[];bodies=[]
for p in sorted((S/'.g5/Verus_verification/results/routine_reporting').glob('*/receipt.json')):
 a,j=receipt(p,S);scratch.append(a);bodies.append(j)
assert len(scratch)==17 and sum(x['kind']=='control' for x in scratch)==15
proof=next(x for x in bodies if x['kind']=='proof');bind=next(x for x in bodies if x['kind']=='binding');assert proof['verdict']=='PASS' and proof['observed']['verified']==35 and proof['observed']['errors']==0
manifest=json.loads((S/M/'model.json').read_text());source=(S/M/'routine_reporting.rs').read_text();mutants=[]
for c in manifest['controls']:
 fs=list((D/'run-dir/verus/routine_reporting/controls'/c['name']).glob('*/models/routine_reporting/routine_reporting.rs'));assert len(fs)==1 and source.count(c['find'])==1 and fs[0].read_text()==source.replace(c['find'],c['replace']);mutants.append({'name':c['name'],'path':str(fs[0].relative_to(H)),'sha256':sha(fs[0])})
central=[]
for p in sorted((R/'.g5/Verus_verification/results/routine_reporting').glob('*/receipt.json')):
 j=json.loads(p.read_text())
 if all((R/k).is_file() and sha(R/k)==v for k,v in j['inputs'].items()):central.append(receipt(p,R)[0])
assert len(central)==17 and sum(x['kind']=='binding' for x in central)==1
runs=[];events=[]
for p in sorted((D/'runs').iterdir()):
 j=json.loads((p/'result.json').read_text());assert j['exit_code']==0 and j['inputs_unchanged'] and all(j['active_source_still_equal'].values());text=(p/'raw.log').read_text();assert 'REVIEW_OUTER_SOCKET_CONNECT_CALLS 0' in text
 if p.name.endswith('-upstream'):assert '111 passed' in text
 runs.append({'path':str(p.relative_to(H)),'op':p.name.rsplit('-',1)[1],'elapsed_s':j['elapsed_s'],'log_sha256':sha(p/'raw.log'),'git_reads':j['git_read_count']})
 if (p/'subprocess.jsonl').exists():events += [json.loads(s) for s in (p/'subprocess.jsonl').read_text().splitlines()]
assert len(runs)==4 and sum(x['git_reads'] for x in runs)==0
verus=[x for x in events if Path(x['argv'][0]).name=='verus'];assert len(verus)==31 and all('--num-threads' in x['argv'] and x['argv'][x['argv'].index('--num-threads')+1]=='4' for x in verus)
counts=json.loads((H/'review-routine-reporting-counts.json').read_text());assert counts['total_units']==35 and counts['proof_units']==30 and counts['recursive_spec_units']==5 and counts['imported_units']==counts['nonlinear_subquery_units']==0
names=counts['files'][0]['proof_query_declarations'];assert len([n for n in names if n.startswith('theorem_')])==20 and len([n for n in names if n.startswith('lemma_')])==10
out={'verdict':'ACCEPT_BOUNDED_ORDINARY_REPORTING_FRAGMENT','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'package':expected,'current_scratch_bytes_equal':True,'verified':35,'new_ordinary_proof_queries':30,'new_recursive_spec_queries':5,'imports':0,'NLA':0,'extra_hint_declarations':0,'controls':15,'all_full_and_named_ordinary':True,'mutant_inputs':mutants,'scratch_receipts':scratch,'central_fresh_receipts':central,'binding':{'worlds':156,'comparisons':11204,'actual_python_sensitivities':8,'all_detected':True,'sockets':0,'native':0},'upstream_passed':111,'runs':runs,'measured_replay_command_s':sum(x['elapsed_s'] for x in runs),'audit_s':time.monotonic()-start,'actual_verus_commands':31,'actual_git_reads':0,'git_mutations':0,'reviewer_native_calls':0,'interrupted_inputs_opened_or_reused':False,'V1_preservation':'review-reporting-scratch-v1/preserved-v1-before-standard-receipt-refresh','V2_qualification':'Proof/controls/upstream executed V1; exact rs/manifest unchanged in V2. V2 binding/NOTES/flat auxiliary inputs refreshed and binding rerun; no unchanged proof rerun claimed.','roles_recommended_active':15,'direct_executable_bodies_verified':0,'residuals':['Canonical graph/label/predicate equality projection; full raw graph validator grammar not proved.','SQL DISTINCT/COALESCE/COUNT/GROUP BY engine/collation/identifier/driver/concurrency remain provider frames.','Label distribution map proved; descending order and failure behavior finite Python/SQLite only.','First-access schema acceptance/refusal and other native/global/index/routine/ledger/readiness fields are observation/provider only.','Graph/vector report projections and normal raw-diagnostic wrapper identity fragment; no whole report formatting or arbitrary exception __str__ proof.']};(H/'review-reporting-final-validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'verdict':out['verdict'],'verified':35,'controls':15,'binding':out['binding'],'upstream':111,'commands_s':out['measured_replay_command_s'],'audit_s':out['audit_s']}))
