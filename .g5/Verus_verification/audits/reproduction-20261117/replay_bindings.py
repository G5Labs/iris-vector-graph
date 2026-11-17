"""Run the stopped foundation's product witnesses on its isolated IRIS fixture.
Invoked on the cloud VM with python3; never modifies the experimental checkout.
"""
import datetime,io,json,os,pathlib,subprocess,tarfile,time
home=pathlib.Path.home();repo=(home/'experiments/iris-uplift-master-workers-20261117/iris-vector-graph').resolve()
root=home/'experiments/iris-issue-reproduction-20261117';tree=root/'tree';out=root/'evidence';tree.mkdir(parents=True,exist_ok=True);out.mkdir(exist_ok=True)
rev='1a9facfbf0fd67fbfc26047caf89ddc1927fa813'
models=['cypher_fns','cypher_exprs','retrieval_compose','temporal_stats','operator_reports','sql_procs','bm25_scoring','percentile','cypher_clauses','bolt_answers','bolt_tx','traversal_strategy','adjacency_maint','clause_combos','result_decoders','ivf_entries','install_lifecycle','rebuild_reads']
paths=['.g5/Verus_verification/tools','.g5/uplift/consolidated/iteration-36']
paths += ['.g5/Verus_verification/models/'+m for m in models]
paths += ['.g5/uplift/consolidated/iteration-'+str(n) for n in range(47,60)]
data=subprocess.check_output(['git','-C',repo,'archive',rev,*paths])
with tarfile.open(fileobj=io.BytesIO(data)) as t:t.extractall(tree,filter='data')
(tree/'.git').write_text('gitdir: '+str(repo/'.git')+'\n')
fixture=home/'experiments/iris-uplift-continuation-20261117/runs/ivg-cont-20261117'
env=dict(os.environ,RUN_DIR=str(fixture),IVG_REPO=str(tree),IVG_PIN_DIR=str(fixture/'pin'),PYTHONDONTWRITEBYTECODE='1',RR_SYNCS='6')
v541=fixture/'i55/venv541/bin/python'
if v541.exists():env['I55_VENV541']=str(v541)
else:print('DRIVER_541_MISSING',v541,flush=True)
for model in models:
 started=datetime.datetime.now(datetime.timezone.utc).isoformat();t0=time.monotonic()
 print('RUN',model,started,flush=True)
 try:
  p=subprocess.run([fixture/'venv/bin/python','-B',tree/'.g5/Verus_verification/models'/model/'binding.py'],env=env,cwd=fixture/'pin',text=True,capture_output=True,timeout=900)
  (out/(model+'.stdout.log')).write_text(p.stdout);(out/(model+'.stderr.log')).write_text(p.stderr)
  receipts=sorted((tree/'.g5/Verus_verification/results'/model).glob('*/receipt.json'))
  receipt=json.loads(receipts[-1].read_text()) if receipts else None
  row={'model':model,'started':started,'seconds':time.monotonic()-t0,'exit_code':p.returncode,'receipt':receipt,'receipt_source':str(receipts[-1]) if receipts else None}
 except Exception as ex:row={'model':model,'started':started,'seconds':time.monotonic()-t0,'error':repr(ex)}
 (out/(model+'.json')).write_text(json.dumps(row,indent=2,default=str)+'\n')
 q=row.get('receipt')or{};print('DONE',model,row.get('exit_code'),q.get('verdict'),q.get('cases'),round(row['seconds'],1),flush=True)
(root/'complete.json').write_text(json.dumps({'revision':rev,'completed':datetime.datetime.now(datetime.timezone.utc).isoformat(),'models':models},indent=2)+'\n')
