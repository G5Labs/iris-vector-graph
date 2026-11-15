"""Actual provider save of two task-owned definitions with identical generated name."""
import hashlib,json,runpy,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
helper=REPO/'.g5/Verus_verification/models/temporal_restore/binding.py';h=runpy.run_path(str(helper))
def main():
    c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);native=e._iris_obj();graph='fhir:G5Name8:'+uuid.uuid4().hex[:8];name=('IVG FHIR sync '+graph)[:50];tasks=set();out=[];failure=None
    try:
        for index in [0,1]:
            t=native.classMethodObject('%SYS.Task','%New')
            for key,value in [('Name',name),('Description','G5 task-owned provider check'),('NameSpace','USER'),('TaskClass','Graph.KG.FHIRGraphSyncTask'),('TimePeriod',0),('DailyFrequency',1),('DailyFrequencyTime',0),('DailyIncrement',60),('DailyStartTime',0),('DailyEndTime',86399)]:t.set(key,value)
            definition=native.classMethodObject('Graph.KG.FHIRGraphSyncTask','%New');definition.set('GraphId',graph)
            assigned=t.invoke('AssignSettings',definition);assert int(native.classMethodValue('%SYSTEM.Status','IsOK',assigned))
            sc=t.invoke('%Save');ok=bool(int(native.classMethodValue('%SYSTEM.Status','IsOK',sc)));tid=t.invoke('%Id')
            if tid:tasks.add(str(tid))
            out.append({'index':index,'saved':ok,'task_id':None if not tid else str(tid),'error':None if ok else str(native.classMethodValue('%SYSTEM.Status','GetErrorText',sc))})
    except Exception as ex:failure={'type':type(ex).__name__,'error':str(ex)};raise
    finally:
        cleanup=[]
        for tid in tasks:
            existed=bool(int(native.classMethodValue('%SYS.Task','%ExistsId',tid)))
            if existed:sc=native.classMethodValue('%SYS.Task','%DeleteId',tid)
            cleanup.append({'task_id':tid,'existed':existed,'remaining':bool(int(native.classMethodValue('%SYS.Task','%ExistsId',tid)))})
        result={'kind':'actual TaskManager same-name save provider observation, no registry or async invocation','identity_checked':True,'container':h['NAME'],'graph':graph,'name':name,'saves':out,'failure':failure,'cleanup':cleanup,
            'inputs':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),helper]},'scope':'sampled valid canonical settings and product daily-task fields; no registry SQL failure, lost reply, background timing or general provider proof'}
        Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');c.close()
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
