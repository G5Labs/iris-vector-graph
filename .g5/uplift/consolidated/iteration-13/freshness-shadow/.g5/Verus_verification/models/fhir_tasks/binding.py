"""Actual pinned FHIR Python over an executing Task/SQLite provider adapter.

TaskManager/ObjectScript bodies are transcribed ports, never called native here.
The reference functions independently transcribe fhir_tasks; controls rerun the
same journey after a named deciding-rule change, never edit an observed answer.
"""
import copy,inspect,itertools,json,logging,sqlite3,sys,textwrap,time
from pathlib import Path
from unittest.mock import patch
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN_DIR=bc.import_pin()
from iris_vector_graph._engine import fhir_graph as fg

CLS='Graph.KG.FHIRGraphSyncTask';NS='USER';G='fhir:NS:X1';OTHER='fhir:NS:other'
def setting(xs):
    # Independent model graph_setting: complete valid decoded list, including odd.
    matches=[xs[i+1] if i+1<len(xs) else '' for i in range(0,len(xs),2) if xs[i]=='GraphId']
    return matches[-1] if matches else ''
def own(t,g,ns=NS):
    return 'Class' if t['class']!=CLS else 'Namespace' if t['namespace']!=ns else 'Graph' if setting(t['settings'])!=g else None
def task(settings=None,cls=CLS,ns=NS,minutes=9):
    return {'class':cls,'namespace':ns,'settings':['GraphId',G] if settings is None else settings,'minutes':minutes,
        'name':'unrelated diagnostic name','suspended':True,'period':5}
def initial(kind='own',graph=G):
    rows={graph:{'task_id':'old','interval':3600,'version':2},OTHER:{'task_id':'unrelated','interval':120,'version':None}}
    tasks={'unrelated':task(['GraphId',OTHER])}
    if kind=='unregistered':rows.pop(graph)
    elif kind=='none':rows[graph]['task_id']=''
    elif kind=='stale':rows[graph]['task_id']='gone'
    elif kind=='stale-equals-fresh':rows[graph]['task_id']='fresh1'
    else:
        settings={'own':['GraphId',graph],'class':['GraphId',graph],'namespace':['GraphId',graph],
            'graph':['GraphId',OTHER],'missing':[],'key-case':['graphid',graph],
            'duplicate-other-last':['GraphId',graph,'GraphId',OTHER],
            'duplicate-mine-last':['GraphId',OTHER,'GraphId',graph],
            'odd-GraphId':['GraphId',graph,'GraphId'],'odd-other':['GraphId',graph,'noise'],
            'key-in-value':['Noise','GraphId','GraphId',graph],
            'registered59':['GraphId',graph],'future-version':['GraphId',graph]}[kind]
        tasks['old']=task(settings,cls='Other.Task' if kind=='class' else CLS,ns='OTHER' if kind=='namespace' else NS)
        if kind=='registered59':rows[graph]['interval']=59
        if kind=='future-version':rows[graph]['version']=3
    return {'rows':rows,'tasks':tasks}

def reference(state,operation,raw=None,fault='none',fresh='fresh1',g=G):
    s=copy.deepcopy(state);ops=[]
    def err(reason):return {'kind':'error','reason':reason},s,ops
    if operation=='Schedule' and raw is not None and (not isinstance(raw,int) or raw<60):return err('Caller')
    if g not in s['rows']:return err('Unregistered')
    row=s['rows'][g];old=row['task_id'];exists=bool(old) and old in s['tasks']
    n=(raw if raw is not None else 0) if operation=='Schedule' else 0
    effective=n if n>0 else row['interval']
    if operation=='Schedule' and effective<60:return err('Interval')
    reason=own(s['tasks'][old],g) if exists else None
    if reason:return err(reason)
    if operation=='Schedule':
        ops.append('Assign')
        if fault=='assign':return err('Assign')
        ops.append('Save')
        if fault=='save':return err('Save')
        target=old if exists else fresh
        t=copy.deepcopy(s['tasks'][old]) if exists else task([],minutes=0)
        t.update({'class':CLS,'namespace':NS,'settings':['GraphId',g],'minutes':(effective+59)//60,
            'name':('IVG FHIR sync '+g)[:50],'period':0})
        s['tasks'][target]=t;ops.append('Sql')
        if fault=='sql':return err('Sql')
        row.update({'task_id':target,'interval':effective})
        return {'kind':'value','value':{'status':'scheduled','graph_id':g,'task_id':target,'interval_s':effective,'minutes':(effective+59)//60}},s,ops
    if exists:
        ops.append('Delete')
        if fault=='delete':return err('Delete')
        del s['tasks'][old]
    ops.append('Sql')
    if fault=='sql':return err('Sql')
    row['task_id']=''
    return {'kind':'value','value':{'status':'unscheduled','graph_id':g,'task_id':old,'removed':exists}},s,ops

class ProviderError(RuntimeError):pass
class Provider:
    def __init__(self,state,fault='none',fresh='fresh1',rule=None):
        self.db=sqlite3.connect(':memory:');self.tasks=copy.deepcopy(state['tasks']);self.fault=fault;self.fresh=fresh;self.rule=rule
        self.ops=[];self.calls=[];self.sql=[];self.sync_reply='{"status":"busy"}';self.read_ok=True
        self.db.execute('CREATE TABLE fhir_graphs(graph_id TEXT PRIMARY KEY,task_id TEXT,interval_s INTEGER,interp_version INTEGER)')
        self.db.executemany('INSERT INTO fhir_graphs VALUES (?,?,?,?)',[(g,r['task_id'] or None,r['interval'],r['version']) for g,r in state['rows'].items()])
    def open(self,g):
        r=self.db.execute('SELECT task_id,interval_s,interp_version FROM fhir_graphs WHERE graph_id=?',(g,)).fetchone()
        if r is None:raise ProviderError('Unregistered')
        return {'task_id':r[0] or '','interval':r[1],'version':r[2]}
    def check(self,t,g):
        if t['class']!=CLS and self.rule!='ignore-class':raise ProviderError('Class')
        if t['namespace']!=NS and self.rule!='ignore-namespace':raise ProviderError('Namespace')
        # Source-style left-to-right alternating list scan, independent of the
        # reference's selected-match comprehension above.
        decoded='';xs=t['settings']
        for i in range(0,len(xs),2):
            if xs[i]=='GraphId':
                decoded=xs[i+1] if i+1<len(xs) else ''
                if self.rule=='first-GraphId':break
        if decoded!=g:raise ProviderError('Graph')
    def boundary(self,name):
        self.ops.append(name)
        if self.fault==name.lower():raise ProviderError(name)
    def update(self,sql,args):
        self.boundary('Sql');self.sql.append((sql,args));self.db.execute(sql,args)
    def schedule(self,g,sent):
        row=self.open(g);seconds=sent if sent>0 else row['interval']
        if seconds<60:raise ProviderError('Interval')
        mins=seconds//60+(seconds%60>0);old=row['task_id'];has=bool(old) and old in self.tasks
        if has:self.check(self.tasks[old],g)
        target=old if has else self.fresh
        pending=copy.deepcopy(self.tasks[old]) if has else task([],minutes=0)
        pending.update({'name':('IVG FHIR sync '+g)[:50],'namespace':NS,'class':CLS,'period':0,'minutes':int(mins)})
        self.boundary('Assign');pending['settings']=['GraphId',g]
        self.boundary('Save');before=copy.deepcopy(self.tasks);self.tasks[target]=pending
        try:self.update('UPDATE fhir_graphs SET task_id=?,interval_s=? WHERE graph_id=?',(target,seconds,g))
        except Exception:
            if self.rule=='rollback-save':self.tasks=before
            raise
        return {'status':'scheduled','graph_id':g,'task_id':target,'interval_s':seconds,'minutes':int(mins)}
    def unschedule(self,g):
        row=self.open(g);old=row['task_id'];has=bool(old) and old in self.tasks
        if has:
            self.check(self.tasks[old],g);self.boundary('Delete');del self.tasks[old]
        self.update('UPDATE fhir_graphs SET task_id=NULL WHERE graph_id=?',(g,))
        return {'status':'unscheduled','graph_id':g,'task_id':old,'removed':has}
    def snapshot(self):
        return {'tasks':copy.deepcopy(self.tasks),'rows':{g:{'task_id':i or '','interval':n,'version':v} for g,i,n,v in self.db.execute('SELECT graph_id,task_id,interval_s,interp_version FROM fhir_graphs')}}
    def classMethodValue(self,cls,method,*args):
        self.calls.append((cls,method,*args));assert cls=='Graph.KG.FHIRGraph'
        if method=='SyncOnce':
            if self.sync_reply is None:raise ProviderError('injected SyncOnce exception')
            return self.sync_reply
        try:
            if method=='Schedule':out=self.schedule(*args)
            elif method=='Unschedule':out=self.unschedule(*args)
            elif method=='Status':
                if not self.read_ok:raise ProviderError('later resource metadata read failed')
                row=self.open(args[0]);out={'status':'ok','graph_id':args[0],'task_id':row['task_id'],'interval_s':row['interval'],
                    'interpretation_version':row['version'],'interpretation_current':2}
            else:raise AssertionError(method)
            return json.dumps(out)
        except ProviderError as ex:return json.dumps({'status':'error','error':str(ex)})
    def on_task(self,id,reply):
        if id not in self.tasks or self.tasks[id]['class']!=CLS:return None
        t=self.tasks[id];g=setting(t['settings']);self.sync_reply=reply
        try:
            wire=self.classMethodValue('Graph.KG.FHIRGraph','SyncOnce',g);success=json.loads(wire).get('status','')!='error'
        except Exception:success=False
        return {'namespace':t['namespace'],'graph':g,'success':success}
    def close(self):self.db.close()

def fixture(provider):
    engine=fg.FhirGraphMixin.__new__(fg.FhirGraphMixin);engine._iris_obj=lambda:provider;return engine
def invoke(engine,operation,g,raw):
    try:
        value=engine.fhir_graph_schedule(g,raw) if operation=='Schedule' else engine.fhir_graph_unschedule(g)
        return {'kind':'value','value':value}
    except Exception as ex:return {'kind':'error','type':type(ex).__name__,'message':str(ex)}
def status(engine,g):
    try:
        r=engine.fhir_graph_status(g)
        return {'kind':'value','task_id':r['task_id'],'interval':r['interval_s'],'version':r['interpretation_version'],'stale':r['interpretation_stale']}
    except Exception as ex:return {'kind':'error','type':type(ex).__name__}
def expected_status(s,g):
    r=s['rows'].get(g)
    if r is None or (r['version'] is not None and r['version']>2):return {'kind':'error'}
    return {'kind':'value','task_id':r['task_id'],'interval':r['interval'],'version':r['version'],'stale':r['version'] is None or r['version']<2}
def run_case(kind,operation,raw=None,fault='none',rule=None):
    state=initial(kind);expected,after,ops=reference(state,operation,raw,fault)
    p=Provider(state,fault,rule=rule);engine=fixture(p);got=invoke(engine,operation,G,raw);view=status(engine,G)
    normalized={'kind':'error','reason':'Caller' if got.get('type')=='ValueError' else 'Server'} if got['kind']=='error' else got
    exp={'kind':'error','reason':'Caller' if expected.get('reason')=='Caller' else 'Server'} if expected['kind']=='error' else expected
    actual_state=p.snapshot();wanted_view=expected_status(after,G)
    comparable_view={k:v for k,v in view.items() if k!='type'}
    agrees=normalized==exp and actual_state==after and p.ops==ops and comparable_view==wanted_view
    out={'state_kind':kind,'operation':operation,'raw_interval':raw,'fault':fault,'actual':got,'expected':expected,'ops':p.ops,'expected_ops':ops,'status':view,
        'state':actual_state,'native_calls':p.calls,'sql':p.sql,'agrees':agrees}
    p.close();return out

KINDS=['unregistered','none','stale','stale-equals-fresh','own','class','namespace','graph','missing','key-case',
    'duplicate-other-last','duplicate-mine-last','odd-GraphId','odd-other','key-in-value','registered59','future-version']
def matrix(rule=None):
    cases=[]
    for kind,raw,fault in itertools.product(KINDS,[None,0,59,60,61,120,-1,'60',60.5,True],['none','assign','save','sql']):
        cases.append(run_case(kind,'Schedule',raw,fault,rule))
    for kind,fault in itertools.product(KINDS,['none','delete','sql']):cases.append(run_case(kind,'Unschedule',fault=fault,rule=rule))
    return cases

def retries():
    rows=[]
    for kind,operation in itertools.product(['none','stale','stale-equals-fresh','own'],['Schedule','Unschedule']):
        state=initial(kind);p=Provider(state,'sql');engine=fixture(p);expected,after,_=reference(state,operation,60,'sql')
        first=invoke(engine,operation,G,60);firststate=p.snapshot();p.fault='none';p.fresh='fresh2';p.ops=[]
        want,final,ops=reference(after,operation,60,'none','fresh2');second=invoke(engine,operation,G,60);view=status(engine,G)
        good=first['kind']=='error' and firststate==after and second==want and p.snapshot()==final and p.ops==ops
        rows.append({'case':kind+'-'+operation,'first':first,'second':second,'first_state':firststate,'final_state':p.snapshot(),'status':view,'agrees':good});p.close()
    # SQL-failed newly saved orphan survives successful registry-based unschedule.
    p=Provider(initial('none'),'sql');engine=fixture(p);invoke(engine,'Schedule',G,60);p.fault='none';second=invoke(engine,'Unschedule',G,None)
    ticks=[]
    for wire in ['{"status":"busy"}','{"status":"ok"}','{"status":"error","error":"failed"}','{}','bad-json',None]:
        actual=p.on_task('fresh1',wire);expected_success=wire not in ['{"status":"error","error":"failed"}','bad-json',None]
        ticks.append({'wire':wire,'invocation':actual,'agrees':actual=={'namespace':NS,'graph':G,'success':expected_success}})
    rows.append({'case':'orphan-unschedule-tick','second':second,'tasks':list(p.tasks),'ticks':ticks,'agrees':'fresh1' in p.tasks and all(t['agrees'] for t in ticks)});p.close();return rows

def reader_cases():
    rows=[]
    for version in [None,'',0,1,'1',2,'2',3]:
        p=Provider(initial());engine=fixture(p)
        wire=json.dumps({'status':'ok','task_id':'old','interval_s':60,'interpretation_version':version,'interpretation_current':2})
        with patch.object(p,'classMethodValue',lambda *_:wire):got=status(engine,G)
        expected={'kind':'error'} if version==3 else {'kind':'value','task_id':'old','interval':60,'version':None if version in [None,''] else int(version),'stale':version in [None,''] or int(version)<2}
        rows.append({'version':version,'actual':got,'agrees':{k:v for k,v in got.items() if k!='type'}==expected});p.close()
    p=Provider(initial());engine=fixture(p);written=invoke(engine,'Schedule',G,60);p.read_ok=False;view=status(engine,G)
    rows.append({'case':'task-success-does-not-imply-status-provider-success','command':written,'status':view,
        'agrees':written['kind']=='value' and p.snapshot()['rows'][G]['task_id']=='old' and view['kind']=='error'});p.close()
    return rows

def graph_cases():
    rows=[]
    for raw in [G,G+'\x00','1','ordinary graph',None,'','0','a\x01b']:
        canonical=raw.replace('\x00','') if isinstance(raw,str) else ''
        valid=bool(canonical) and canonical!='0' and all(ord(c)>=32 and ord(c)!=127 for c in canonical)
        state=initial('own',canonical if valid else G);p=Provider(state);engine=fixture(p)
        got=invoke(engine,'Schedule',raw,60)
        if valid:
            expected,after,ops=reference(state,'Schedule',60,g=canonical)
            good=got==expected and p.snapshot()==after and p.ops==ops and p.calls[0][2]==canonical
        else:good=got['kind']=='error' and got['type']=='ValueError' and not p.calls and p.snapshot()==state
        rows.append({'raw_graph':raw,'canonical':canonical,'actual':got,'port':p.calls,'agrees':good});p.close()
    return rows

def main():
    t=time.monotonic();cases=matrix();extra=retries();readers=reader_cases();graphs=graph_cases();detection={}
    # Actual product function mutations; every check executes the public wrapper
    # and uses the same reference/state/reader assertions, with no edited answer.
    src=textwrap.dedent(inspect.getsource(fg.FhirGraphMixin.fhir_graph_schedule));assert src.count('interval_s < 60')==1
    scope=dict(vars(fg));exec(src.replace('interval_s < 60','interval_s < 61'),scope)
    with patch.object(fg.FhirGraphMixin,'fhir_graph_schedule',scope['fhir_graph_schedule']):detection['product-valid60-refused']=not run_case('none','Schedule',60)['agrees']
    src=textwrap.dedent(inspect.getsource(fg.FhirGraphMixin._fhir_call));find='if reply.get("status") == "error":';assert src.count(find)==1
    scope=dict(vars(fg));exec(src.replace(find,'if False:'),scope)
    with patch.object(fg.FhirGraphMixin,'_fhir_call',scope['_fhir_call']):detection['product-error-folded-as-value']=not run_case('class','Schedule',60)['agrees']
    src=textwrap.dedent(inspect.getsource(fg._interp_stale));find='if int(version) > int(current):';assert src.count(find)==1
    scope=dict(vars(fg));exec(src.replace(find,'if False:'),scope)
    with patch.object(fg,'_interp_stale',scope['_interp_stale']):detection['product-future-version-accepted']=any(not r['agrees'] for r in reader_cases())
    # Adapter controls are labeled as such; native bodies are not mutated here.
    for rule,kind,operation,fault in [('ignore-class','class','Schedule','none'),('ignore-namespace','namespace','Unschedule','none'),
        ('first-GraphId','duplicate-other-last','Schedule','none'),('rollback-save','none','Schedule','sql')]:
        detection['adapter-'+rule]=not run_case(kind,operation,60,fault,rule)['agrees']
    bad=[r for r in cases if not r['agrees']];verdict='AGREES' if not bad and all(x['agrees'] for x in extra+readers+graphs) and all(detection.values()) else 'DISAGREES'
    receipt=bc.write_receipt('fhir_tasks',Path(__file__),{'verdict':verdict,'comparisons':len(cases),'mismatch_count':len(bad),'mismatches':bad[:10],
        'cases':cases,'retry_scenarios':extra,'reader_cases':readers,'graph_cases':graphs,'detection':detection,'elapsed':time.monotonic()-t,'pin':bc.pin_identity(PIN_DIR),
        'actual_product':'FhirGraphMixin.fhir_graph_schedule/unschedule/status/_fhir_call/_interp_stale; actual Python validation, payload and final reader types/errors',
        'provider_adapter':'Executing Python transcription of FHIRGraph Open/CheckOwnTask/Schedule/Unschedule/OnTask plus real SQLite registry SQL; no ObjectScript/TaskManager/IRIS/native driver executed by child. Allocation uses unused named IDs; failures are pre-effect at indicated port, later SQL failure retains earlier task effect.',
        'formal_relation':'fhir_tasks::graph_setting/ownership/caller_interval/effective/minutes/schedule/public_schedule/unschedule/status/tick/on_task',
        'qualified_scope':'valid decoded native Settings string lists; TaskManager canonical AssignSettings load; projected class/namespace/settings/minutes; final registry/status task ID+interval/version projection; no whole FHIR count/resource query or background task execution proof'})
    data=json.loads(receipt.read_text());data['inputs'][str((HERE/'model.json').relative_to(bc.REPO))]=bc.sha(HERE/'model.json')
    data['product_sources']={p:bc.sha(PIN_DIR/p) for p in ['iris_vector_graph/_engine/fhir_graph.py','iris_vector_graph/_validate.py','iris_src/src/Graph/KG/FHIRGraph.cls','iris_src/src/Graph/KG/FHIRGraphSyncTask.cls']}
    native=[]
    for p in sorted((bc.REPO/'.g5/uplift/consolidated/iteration-8').glob('fhir-native.*')):
        if p.suffix in ['.py','.json']:data['inputs'][str(p.relative_to(bc.REPO))]=bc.sha(p);native.append(str(p.relative_to(bc.REPO)))
    data['native_evidence_from_root']=native
    if native:
        obj=json.loads((bc.REPO/'.g5/uplift/consolidated/iteration-8/fhir-native.json').read_text());assert obj['verdict']=='AGREES'
        data['native_comparisons']=obj['comparisons'];data['native_scope']=obj['scope']
        assert obj['comparisons']==20 and obj['identity_checked'] and obj['all_created_ids_absent']
        native_script=bc.REPO/'.g5/uplift/consolidated/iteration-8/fhir-native.py'
        assert bc.sha(native_script)==obj['script_sha256']
        helper=bc.REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'
        data['inputs'][str(helper.relative_to(bc.REPO))]=bc.sha(helper)
        for name,digest in obj.get('source_inputs',{}).items():
            p=bc.REPO/name;assert bc.sha(p)==digest;data['inputs'][name]=digest
    lookup=bc.REPO/'.g5/uplift/consolidated/iteration-8/fhir-id-native.json'
    if lookup.is_file():
        observation=json.loads(lookup.read_text());canonical=observation['canonical_id']
        assert observation['identity_checked'] and observation['harness_failure'] is None and observation['cleanup']['delete_ok'] and not observation['cleanup']['exists_after']
        assert len(observation['observations'])==9
        for row in observation['observations']:
            accepted=str(row['raw'])==canonical
            assert row.get('exists')==accepted and row.get('opened_id')==(canonical if accepted else None) and 'exception' not in row
        for name,digest in observation['inputs'].items():
            p=bc.REPO/name;assert bc.sha(p)==digest;data['inputs'][name]=digest
        for suffix in ['.py','.json','.log']:
            p=lookup.with_suffix(suffix);data['inputs'][str(p.relative_to(bc.REPO))]=bc.sha(p)
        data['native_id_lookup_observations']=9
        data['identifier_provider_fragment']='exact canonical stored string lookup and opened object %Id identity. Root sampled one owned object with9 carriers; no alias accepted. Untested ID/coercion forms remain unassessed; this is not a universal normalization proof.'
    names=bc.REPO/'.g5/uplift/consolidated/iteration-8/fhir-name-native.json'
    if names.is_file():
        observation=json.loads(names.read_text())
        assert observation['identity_checked'] and observation['failure'] is None and len(observation['saves'])==2
        assert all(x['saved'] for x in observation['saves']) and observation['saves'][0]['task_id']!=observation['saves'][1]['task_id']
        assert all(not x['remaining'] for x in observation['cleanup'])
        for name,digest in observation['inputs'].items():
            p=bc.REPO/name;assert bc.sha(p)==digest;data['inputs'][name]=digest
        for suffix in ['.py','.json','.log']:
            p=names.with_suffix(suffix);data['inputs'][str(p.relative_to(bc.REPO))]=bc.sha(p)
        data['native_same_name_saves']=2
        data['name_provider_fragment']='Two actual valid same-name daily tasks accepted; finite support for successful second save, no registry SQL fault or universal name/allocation proof.'
    receipt.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n');print(receipt);print(json.dumps({'verdict':verdict,'cases':len(cases),'mismatches':len(bad),'detections':detection,'elapsed':time.monotonic()-t}));return int(verdict!='AGREES')
if __name__=='__main__':raise SystemExit(main())
