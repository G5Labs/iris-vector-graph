"""Read-only actual pinned FHIR Python wrapper/reader survey, no native/network.

Server replies are supplied observations, not execution of ownership or sync.
The probe explicitly records this boundary instead of claiming Task Manager proof.
"""
import inspect,itertools,json,logging,sys,textwrap,time,hashlib
from pathlib import Path
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN))
from iris_vector_graph._engine import fhir_graph as fg

class Native:
    def __init__(self,reply):self.reply=reply;self.calls=[]
    def classMethodValue(self,*args):self.calls.append(args);return self.reply
def fixture(reply):
    native=Native(reply);engine=fg.FhirGraphMixin.__new__(fg.FhirGraphMixin);engine._iris_obj=lambda:native
    return engine,native
def observe(method,graph,reply,interval=None):
    engine,native=fixture(reply)
    try:
        result=getattr(engine,method)(graph,**({'interval_s':interval} if method=='fhir_graph_schedule' else {}));out={'kind':'value','value':result}
    except Exception as ex:out={'kind':'error','type':type(ex).__name__,'message':str(ex)}
    return {'method':method,'graph':graph,'interval':interval,'reply':reply,'outcome':out,'port':native.calls}
def main():
    t=time.monotonic();cases=[];mismatches=[]
    replies=[{'status':'scheduled','task_id':'7'},{'status':'busy'},{'status':'error','error':'ordinary restored task does not belong to graph'},{}]
    graphs=['fhir:NS:X0001','ordinary-named-graph',None,'','0','a\x01b']
    intervals=[None,0,1,59,60,61,120,-1,'60',60.5]
    for graph,interval,reply in itertools.product(graphs,intervals,replies):
        row=observe('fhir_graph_schedule',graph,json.dumps(reply),interval)
        invalid=graph in [None,'','0','a\x01b'] or (interval is not None and (not isinstance(interval,int) or interval<60))
        expected='validation' if invalid else 'server-error' if reply.get('status')=='error' else 'value'
        good=(not row['port'] and row['outcome']['kind']=='error') if invalid else (
            len(row['port'])==1 and row['port'][0]==('Graph.KG.FHIRGraph','Schedule',graph,interval or 0) and
            ((row['outcome']['kind']=='error' and row['outcome']['type']=='FHIRGraphError') if expected=='server-error' else row['outcome']=={'kind':'value','value':reply}))
        row['expected']=expected;row['agrees']=good;cases.append(row)
        if not good:mismatches.append(row)
    for method,graph,reply in itertools.product(['fhir_graph_sync','fhir_graph_unschedule'],graphs,replies):
        row=observe(method,graph,json.dumps(reply));valid=graph not in [None,'','0','a\x01b']
        good=not row['port'] if not valid else len(row['port'])==1 and ((row['outcome']['kind']=='error' and row['outcome']['type']=='FHIRGraphError') if reply.get('status')=='error' else row['outcome']=={'kind':'value','value':reply})
        row['agrees']=good;cases.append(row)
        if not good:mismatches.append(row)
    versions=[]
    for version in [None,'',0,1,'1',2,'2',3]:
        row=observe('fhir_graph_status','fhir:NS:X0001',json.dumps({'status':'ok','interpretation_version':version,'interpretation_current':2,'task_id':'7'}))
        good=row['outcome']['type']=='RuntimeError' if isinstance(version,int) and version>2 else (row['outcome']['kind']=='value' and row['outcome']['value']['interpretation_version']==(None if version in (None,'') else int(version)) and row['outcome']['value']['interpretation_stale']==(version in (None,'') or int(version)<2))
        row['agrees']=good;versions.append(row)
        if not good:mismatches.append(row)
    # Actual wrapper changed-rule controls only: they say nothing about whether
    # the supplied error was correctly produced from a native task row.
    src=textwrap.dedent(inspect.getsource(fg.FhirGraphMixin._fhir_call));find='if reply.get("status") == "error":';assert src.count(find)==1
    scope=dict(vars(fg));exec(src.replace(find,'if False:'),scope)
    engine,native=fixture(json.dumps({'status':'error','error':'not own task'}));engine._fhir_call=scope['_fhir_call'].__get__(engine)
    changed=engine.fhir_graph_unschedule('fhir:NS:X0001');detection={'error-becomes-success':changed['status']=='error'}
    src=textwrap.dedent(inspect.getsource(fg.FhirGraphMixin.fhir_graph_schedule));find='interval_s < 60';assert src.count(find)==1
    scope=dict(vars(fg));exec(src.replace(find,'interval_s < 61'),scope);engine,native=fixture('{"status":"scheduled"}')
    try:scope['fhir_graph_schedule'](engine,'fhir:NS:X0001',60);detection['valid-60-refused']=False
    except ValueError:detection['valid-60-refused']=not native.calls
    source=['iris_vector_graph/_engine/fhir_graph.py','iris_src/src/Graph/KG/FHIRGraph.cls','iris_src/src/Graph/KG/FHIRGraphSyncTask.cls',
        'docs/FHIR_GRAPH.md','tests/e2e/test_470_fhir_task_ownership_e2e.py']
    out={'verdict':'AGREES' if not mismatches and all(detection.values()) else 'DISAGREES','cases':cases,'status_versions':versions,'mismatches':mismatches,'detection':detection,'elapsed':time.monotonic()-t,
        'observed':'Actual pinned Python wrappers validate interval/graph, forward args, propagate busy and raise FHIRGraphError; actual status version typing/staleness/future-version refusal.',
        'unobserved':['ObjectScript CheckOwnTask/Schedule/Unschedule execution','Task Manager object storage/Settings list and mutations','two-feed SQL selection, transactions/locks and current-resource resync','native FHIR repository and final graph contents'],
        'provider_substitute':'Recording Native API endpoint supplies JSON replies; no task row or native operation is executed.',
        'source_sha256':{p:hashlib.sha256((PIN/p).read_bytes()).hexdigest() for p in source}}
    HERE.joinpath('next-survey-fhir-probe.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'verdict':out['verdict'],'wrapper_cases':len(cases),'version_cases':len(versions),'mismatches':len(mismatches),'detections':detection,'elapsed':out['elapsed']}));assert out['verdict']=='AGREES'
if __name__=='__main__':main()
