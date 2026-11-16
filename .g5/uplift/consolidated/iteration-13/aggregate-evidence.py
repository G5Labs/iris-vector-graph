"""Read-only final hash/verdict/log audit and exact attempted-command cost ledger."""
from pathlib import Path
import datetime,hashlib,json,re
R=Path(__file__).resolve().parents[4];O=Path(__file__).resolve().parent;M=R/'.g5/Verus_verification/models/aggregate_results';RESULT=R/'.g5/Verus_verification/results/aggregate_results'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fresh(d):return all((R/p).is_file() and sha(R/p)==h for p,h in d['inputs'].items())
manifest=json.loads((M/'model.json').read_text());records=[(p,json.loads(p.read_text())) for p in sorted(RESULT.glob('*/receipt.json'))]
chosen=[]
for kind,name in [('proof',None),('binding',None)]+[('control',c['name']) for c in manifest['controls']]:
 options=[(p,d) for p,d in records if d['kind']==kind and (kind!='control' or d['control']['name']==name)]
 p,d=options[-1];assert fresh(d),('stale',p)
 assert d['verdict']=={'proof':'PASS','binding':'AGREES','control':'EXPECTED_FAIL'}[kind],(p,d['verdict'])
 audit=dict(receipt=str(p.relative_to(R)),sha256=sha(p),kind=kind,control=name,inputs_current=True,verdict=d['verdict'])
 if kind=='proof':assert d['observed']['verified']==75 and d['observed']['errors']==0
 if kind=='binding':assert d['comparisons']==669 and d['socket_attempts']==0 and d['native_calls']==0 and all(x['detected'] for x in d['sensitivities']);audit.update(comparisons=669,sensitivities=len(d['sensitivities']))
 if kind=='control':
  observations=[('full',d['observed'])]+list(d['observed']['per_function'].items());checks=[]
  for label,x in observations:
   assert x['errors']>0 and not x['timed_out'] and not x.get('has_resource_limit',False),(name,label,x)
   # Repository raw log copy is byte-identical to its retained command log.
   log=Path(x['raw_log']);text=log.read_text();assert not re.search(r'rlimit|resource limit|timed? out',text,re.I),(name,label,'resource or timeout text');assert 'error: assertion failed' in text or 'error: postcondition not satisfied' in text,(name,label,text)
   matches=[R/z for z,h in d['raw_log_copies'].items() if h==sha(log)];assert matches
   checks.append(dict(label=label,ordinary_assertion_or_post=True,resource_limit=False,timeout=False,raw_log_sha256=sha(log)))
  audit['checks']=checks
 chosen.append(audit)
 attempts=[]
for p in sorted((O/'aggregate-attempts').glob('*/result.json')):
 d=json.loads(p.read_text());snap=json.loads((p.parent/'snapshot.json').read_text());assert all((R/e['preserved']).is_file() and sha(R/e['preserved'])==e['sha256'] for e in snap['inputs'])
 text=(p.parent/'raw.log').read_text();attempts.append(dict(path=str(p.parent.relative_to(R)),kind=d['kind'],exit_code=d['exit_code'],elapsed_s=d['elapsed_s'],input_count=len(d['inputs']),originals_unchanged=d['originals_unchanged'],raw_log_sha256=sha(p.parent/'raw.log'),receipt_copies=d.get('receipt_copies',[]),diagnostic_excerpt=text[-1000:]))
start_source=json.loads((O/'aggregate-start.json').read_text())['time']; audit_now=datetime.datetime.now(datetime.timezone.utc)
ledger=dict(source_first_utc=start_source,audit_utc=audit_now.isoformat(),elapsed_source_first_to_audit_s=(audit_now-datetime.datetime.fromisoformat(start_source)).total_seconds(),attempts=attempts,count=len(attempts),command_wall_seconds=sum(x['elapsed_s'] for x in attempts),by_kind={kind:dict(count=sum(x['kind']==kind for x in attempts),wall_seconds=sum(x['elapsed_s'] for x in attempts if x['kind']==kind),nonzero_exits=sum(x['kind']==kind and x['exit_code']!=0 for x in attempts)) for kind in sorted({x['kind'] for x in attempts})},failures_preserved=True,scope='Actual subprocess wall time, not solver CPU or a deadline. Early build/trigger/type and invariant failures; count-only UNEXPECTED receipts; binding startup/schema/syntax/insufficient-carrier attempts retained byteexact. No old-lane inputs or new tests are consumed by this audit.')
(O/'aggregate-costs.json').write_text(json.dumps(ledger,indent=2)+'\n')
inputs={str(p.relative_to(R)):sha(p) for p in sorted(M.iterdir()) if p.is_file()};inputs['.g5/Verus_verification/models/node_read/node_read.rs']=sha(R/'.g5/Verus_verification/models/node_read/node_read.rs')
body=dict(version='V3-actual-observation-comparator',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='FROZEN_FOR_INDEPENDENT_REPLAY',model='aggregate_results',package_inputs=inputs,flat_binding_inputs=json.loads((M/'binding_inputs.json').read_text()),final_receipts=chosen,fresh_receipts=len(chosen),proof=dict(total=75,new=62,imports=13),binding=dict(comparisons=669,fixtures=160,actual_source_sensitivities=7,provider_sensitivities=1,observation_sensitivities=1,sockets=0,native_calls=0),upstream=json.loads((O/'aggregate-upstream.json').read_text())['passed'],cost_ledger=str((O/'aggregate-costs.json').relative_to(R)),source_roles=str((O/'aggregate-source-roles.json').relative_to(R)),direct_executable_body_verified=0,scope='Frozen bounded ordinary aggregation; OPTIONAL bug-agg-001 retained as partial source/native observation; all provider/codec/numeric/collation/native-body limits in NOTES. No shared integration performed.')
(O/'aggregate-freeze.json').write_text(json.dumps(body,indent=2)+'\n');(O/'aggregate-final-freshness.json').write_text(json.dumps(dict(utc=body['utc'],receipts=chosen,all_fresh=True),indent=2)+'\n');print(json.dumps(dict(status=body['status'],receipts=len(chosen),attempts=len(attempts),command_wall_seconds=ledger['command_wall_seconds'],proof=75,comparisons=669,upstream=body['upstream'])))
