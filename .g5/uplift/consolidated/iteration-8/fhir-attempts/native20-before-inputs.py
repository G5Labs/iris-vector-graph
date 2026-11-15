"""Task-owned registry/TaskManager fixtures on identity-checked isolated IRIS.
No FHIR repository, background invocation, listener or external service is used.
"""
import hashlib,json,runpy,time,traceback,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
from iris_vector_graph.schema import GraphSchema
from iris_vector_graph.utils import _split_sql_statements
from iris_vector_graph.exceptions import FHIRGraphError
import iris

def main():
    started=time.monotonic();c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8)
    cur=c.cursor()
    for sql in _split_sql_statements(GraphSchema.get_fhir_graph_schema_sql()):
        if not sql.strip():continue
        try:cur.execute(sql)
        except Exception as ex:
            if 'already' not in str(ex).lower():raise
    token=uuid.uuid4().hex[:8];mine='fhir:G5T8:'+token+'a';other='fhir:G5T8:'+token+'b'
    for g in [mine,other]:
        cur.execute("INSERT INTO Graph_KG.fhir_graphs (graph_id,repo_id,rsrc_schema,search_schema,ver_schema,interval_s) VALUES (?,'XG58','HSFHIR_XG58_R','HSFHIR_XG58_S','HSFHIR_XG58_V',3600)",[g])
    c.commit();native=e._iris_obj();tasks=set();observations=[];mism=[];cleanup=[]
    def ok(sc):return bool(int(native.classMethodValue('%SYSTEM.Status','IsOK',sc)))
    def status_text(sc):return str(native.classMethodValue('%SYSTEM.Status','GetErrorText',sc))
    def registry(g):
        q=c.cursor();q.execute('SELECT task_id,interval_s FROM Graph_KG.fhir_graphs WHERE graph_id=?',[g]);r=tuple(q.fetchone());q.close();return {'task_id':None if not r[0] else str(r[0]),'interval':int(r[1])}
    def point(g,tid=None,interval=None):
        if interval is None:cur.execute('UPDATE Graph_KG.fhir_graphs SET task_id=? WHERE graph_id=?',[tid,g])
        else:cur.execute('UPDATE Graph_KG.fhir_graphs SET task_id=?,interval_s=? WHERE graph_id=?',[tid,interval,g])
        c.commit()
    def exists(tid):return bool(int(native.classMethodValue('%SYS.Task','%ExistsId',str(tid))))
    def task(tid):
        if not exists(tid):return None
        o=native.classMethodObject('%SYS.Task','%OpenId',str(tid));li=o.getIRISList('Settings')
        values=[li.get(i) for i in range(1,li.count()+1)] if li is not None else []
        return {'name':o.get('Name'),'class':o.get('TaskClass'),'namespace':o.get('NameSpace'),
            'period':int(o.get('TimePeriod')),'minutes':None if o.get('DailyIncrement') is None else int(o.get('DailyIncrement')),'settings':values}
    def record(name,got,agrees):
        observations.append({'name':name,'got':got,'agrees':bool(agrees)})
        if not agrees:mism.append(name)
    def schedule(g,seconds=None):
        r=e.fhir_graph_schedule(g,**({} if seconds is None else {'interval_s':seconds}))
        if r.get('task_id'):tasks.add(str(r['task_id']))
        return r
    def refused(name,g,call,tid):
        before={'registry':registry(g),'task':task(tid)};err=None
        try:getattr(e,'fhir_graph_'+call)(g,**({'interval_s':60} if call=='schedule' else {}))
        except FHIRGraphError as ex:err=str(ex)
        after={'registry':registry(g),'task':task(tid)}
        record(name,{'before':before,'after':after,'error':err},err is not None and before==after and 'not this graph' in err)
    def new_on_demand(cls='%SYS.Task.PurgeErrorsAndLogs',namespace='%SYS'):
        o=native.classMethodObject('%SYS.Task','%New');o.set('Name','G5 owned fixture '+token);o.set('TaskClass',cls);o.set('NameSpace',namespace);o.set('TimePeriod',5)
        sc=o.invoke('%Save');assert ok(sc),status_text(sc);tid=str(o.invoke('%Id'));tasks.add(tid);return tid
    def settings(tid,values):
        o=native.classMethodObject('%SYS.Task','%OpenId',tid);li=iris.IRISList()
        for x in values:li.add(x)
        o.set('Settings',li.getBuffer());sc=o.invoke('%Save');return {'ok':ok(sc),'error':None if ok(sc) else status_text(sc)}
    try:
        a=schedule(mine,60);tid=str(a['task_id']);t=task(tid);r=registry(mine)
        record('new60',{'reply':a,'task':t,'registry':r},t['class']=='Graph.KG.FHIRGraphSyncTask' and t['namespace']=='USER' and t['minutes']==1 and t['settings']==['GraphId',mine] and r=={'task_id':tid,'interval':60})
        b=schedule(mine,61);record('own-reschedule61',{'reply':b,'task':task(tid),'registry':registry(mine)},str(b['task_id'])==tid and task(tid)['minutes']==2 and registry(mine)['interval']==61)
        gone=e.fhir_graph_unschedule(mine);record('own-unschedule',{'reply':gone,'task':task(tid),'registry':registry(mine)},gone['removed'] is True and task(tid) is None and registry(mine)['task_id'] is None)
        # The exact known-created/deleted ID, not an arbitrary system task ID.
        point(mine,tid);r=e.fhir_graph_unschedule(mine);record('stale-unschedule',{'reply':r,'registry':registry(mine)},r['removed'] is False and registry(mine)['task_id'] is None)
        point(mine,tid);fresh=schedule(mine);own_id=str(fresh['task_id']);record('stale-schedule',{'reply':fresh,'task':task(own_id),'registry':registry(mine)},task(own_id)['settings']==['GraphId',mine] and registry(mine)['task_id']==own_id)
        other_id=str(schedule(other,3600)['task_id']);point(mine,other_id)
        for call in ['schedule','unschedule']:refused('other-graph-'+call,mine,call,other_id)
        alien=new_on_demand();point(mine,alien)
        for call in ['schedule','unschedule']:refused('other-class-'+call,mine,call,alien)
        # Only mutate a task created in this fixture; keep it on-demand while testing raw metadata.
        obj=native.classMethodObject('%SYS.Task','%OpenId',own_id);obj.set('TimePeriod',5);obj.set('NameSpace','%SYS');sc=obj.invoke('%Save')
        if ok(sc):
            point(mine,own_id)
            for call in ['schedule','unschedule']:refused('other-namespace-'+call,mine,call,own_id)
        else:observations.append({'name':'other-namespace-provider-refused-save','save_error':status_text(sc),'assessed_guard':False})
        obj.set('NameSpace','USER');assert ok(obj.invoke('%Save'))
        for label,values,allowed in [('missing',[],False),('odd-trailing-GraphId',['GraphId',mine,'GraphId'],False),('duplicate-last-other',['GraphId',mine,'GraphId',other],False),('duplicate-last-mine',['GraphId',other,'GraphId',mine],True)]:
            saved=settings(own_id,values)
            if not saved['ok']:
                observations.append({'name':label+'-settings-provider-refused-save','save':saved,'assessed_guard':False});continue
            point(mine,own_id)
            if allowed:
                reply=schedule(mine,60);record(label,{'reply':reply,'task':task(own_id),'registry':registry(mine)},str(reply['task_id'])==own_id and task(own_id)['settings']==['GraphId',mine])
            else:
                for call in ['schedule','unschedule']:refused(label+'-'+call,mine,call,own_id)
        # Effective registered interval is checked before touching any task.
        point(mine,None,59);before=registry(mine);err=None
        try:schedule(mine)
        except FHIRGraphError as ex:err=str(ex)
        record('registered59-none',{'error':err,'before':before,'after':registry(mine)},err is not None and before==registry(mine))
        reply=schedule(mine,60);record('registered59-override60',{'reply':reply,'registry':registry(mine)},registry(mine)['interval']==60)
        # Exact public Status cannot pretend a registry-only fixture is a FHIR repository.
        error=None
        try:answer=e.fhir_graph_status(mine)
        except FHIRGraphError as ex:error=str(ex);answer=None
        record('public-status-missing-repository',{'reply':answer,'error':error,'registry_point':registry(mine)},error is not None)
        definition=native.classMethodObject('Graph.KG.FHIRGraphSyncTask','%New');definition.set('GraphId',mine);sc=definition.invoke('OnTask')
        record('direct-ontask-repository-failure',{'ok':ok(sc),'error':status_text(sc),'registry_point':registry(mine)},not ok(sc))
    except Exception as ex:
        mism.append("HARNESS_OR_PROVIDER_EXCEPTION: "+type(ex).__name__+": "+str(ex))
        raise
    finally:
        for tid in sorted(tasks):
            if exists(tid):
                sc=native.classMethodValue('%SYS.Task','%DeleteId',tid);cleanup.append({'task_id':tid,'deleted':ok(sc),'remaining':exists(tid)})
        if not all(x['deleted'] and not x['remaining'] for x in cleanup):mism.append('cleanup-incomplete')
        cur.execute('DELETE FROM Graph_KG.fhir_graphs WHERE graph_id IN (?,?)',[mine,other]);c.commit()
        result={'verdict':'AGREES' if not mism and {'new60','own-reschedule61','own-unschedule','stale-unschedule','stale-schedule','other-graph-schedule','other-graph-unschedule','other-class-schedule','other-class-unschedule','registered59-none','registered59-override60','public-status-missing-repository','direct-ontask-repository-failure'} <= {x['name'] for x in observations if x.get('agrees')} else 'DISAGREES','comparisons':len([x for x in observations if 'agrees' in x]),'mismatches':mism,'observations':observations,
            'identity_checked':True,'container':h['NAME'],'graphs':[mine,other],'created_tasks':sorted(tasks),'cleanup':cleanup,'all_created_ids_absent':all(not exists(t) for t in tasks),
            'scope':'Actual Python wrapper/FHIRGraph Open/CheckOwnTask/Schedule/Unschedule/TaskManager save/read/delete and SQL registry point. Direct OnTask observes missing-repository failure only. No genuine FHIR resource projection, background invocation, network fault, SQL-update fault, race or security behavior is claimed.',
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'elapsed':time.monotonic()-started}
        Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
    print(json.dumps({'verdict':result['verdict'],'comparisons':result['comparisons'],'mismatches':mism,'tasks':len(tasks),'cleanup_ok':all(x['deleted'] and not x['remaining'] for x in cleanup)}));assert not mism
if __name__=='__main__':main()
