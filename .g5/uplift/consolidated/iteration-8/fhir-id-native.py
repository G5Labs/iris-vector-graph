"""Lookup-only alternate-ID spellings for one newly allocated on-demand task."""
import hashlib,json,runpy,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
helper=REPO/'.g5/Verus_verification/models/temporal_restore/binding.py';h=runpy.run_path(str(helper))
def main():
    c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);native=e._iris_obj();task=native.classMethodObject('%SYS.Task','%New');tid=None;out=[];failure=None
    try:
        task.set('Name','G5 own Task ID lookup probe');task.set('NameSpace','%SYS');task.set('TaskClass','%SYS.Task.PurgeErrorsAndLogs');task.set('TimePeriod',5)
        sc=task.invoke('%Save');assert int(native.classMethodValue('%SYSTEM.Status','IsOK',sc));tid=str(task.invoke('%Id'))
        values=[tid,'0'+tid,'00'+tid,'+'+tid,tid+'.0',' '+tid,tid+' ',str(int(tid))+'e0',int(tid)]
        for raw in values:
            try:
                exists=bool(int(native.classMethodValue('%SYS.Task','%ExistsId',raw)))
                obj=native.classMethodObject('%SYS.Task','%OpenId',raw)
                returned=None if obj is None else str(obj.invoke('%Id'))
                out.append({'raw':raw,'type':type(raw).__name__,'exists':exists,'opened_id':returned})
            except Exception as ex:out.append({'raw':raw,'type':type(raw).__name__,'exception':type(ex).__name__,'error':str(ex)})
    except Exception as ex:failure={'type':type(ex).__name__,'error':str(ex)};raise
    finally:
        cleanup=None
        if tid is not None:
            sc=native.classMethodValue('%SYS.Task','%DeleteId',tid);cleanup={'task_id':tid,'delete_ok':bool(int(native.classMethodValue('%SYSTEM.Status','IsOK',sc))),'exists_after':bool(int(native.classMethodValue('%SYS.Task','%ExistsId',tid)))}
        result={'kind':'actual owned on-demand TaskManager ID lookup, no Schedule or background invocation','identity_checked':True,'container':h['NAME'],'canonical_id':tid,'observations':out,'harness_failure':failure,'cleanup':cleanup,
            'inputs':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),helper]},'provider_scope':'sampled native string/int ID carriers, not all canonicalization/coercion forms'}
        Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');c.close()
    print(json.dumps({'canonical_id':tid,'observations':out,'cleanup':cleanup},indent=2))
if __name__=='__main__':main()
