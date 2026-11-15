"""Serial actual IRIS clock/writer/window cases on task-owned guarded runtime."""
import json,os,runpy,sys,time,hashlib
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
helper=REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'
h=runpy.run_path(str(helper));IRISGraphEngine=h['IRISGraphEngine']
class Port:
    def __init__(self,native,fail=False):self.native=native;self.fail=fail;self.calls=[]
    def classMethodValue(self,cls,method,*args):
        self.calls.append({'class':cls,'method':method,'args':args})
        if method=='BulkInsertCounts' and self.fail:raise RuntimeError('controlled prewrite BulkInsertCounts unavailable')
        return self.native.classMethodValue(cls,method,*args)
    def __getattr__(self,k):return getattr(self.native,k)
def main():
    c=h['connect']();e=IRISGraphEngine(c,embedding_dimension=8);e.ledger.disable();e.erase_all()
    store=e._store;native=store._iris_obj();cases=[];mism=[]
    def check(name,route,value=None,omitted=False,fail=False,repeat=False,expect_now=False):
        graph='clock7';s='clk:'+name;port=Port(native,fail);start=int(time.time())
        edge={'s':s,'p':'R','o':'end','ts':value}
        with patch.object(store,'_iris_obj',return_value=port):
            if route=='single':ret=e.create_edge_temporal(s,'R','end',graph=graph,**({} if omitted else {'timestamp':value}))
            else:ret=e.bulk_create_edges_temporal([edge],graph=graph)
            second=e.bulk_create_edges_temporal([edge],graph=graph) if repeat else None
        end=int(time.time());rows=e.get_edges_in_window(start=0,end=end+180,source=s,graph=graph)
        timestamps=[r['ts'] for r in rows];coord=(len(timestamps)==1 and start-5<=timestamps[0]<=end+5) if expect_now else timestamps==[0 if omitted or value is None else int(value)]
        one_epoch=e.get_edges_in_window(start=0,end=0,source=s,graph=graph)
        wrong_graph=e.get_edges_in_window(start=0,end=end+180,source=s,graph='other7')
        item={'name':name,'route':route,'input':value,'omitted':omitted,'prewrite_bulk_unavailable':fail,'repeat':repeat,
            'return':{'written':int(ret),'collisions':getattr(ret,'collisions',None),'skipped':getattr(ret,'skipped',None)},
            'second':None if second is None else {'written':int(second),'collisions':second.collisions,'skipped':second.skipped},
            'wall_clock_bounds':[start,end],'window_rows':rows,'epoch_rows':one_epoch,'wrong_graph':wrong_graph,'port_calls':port.calls,'coordinate_agrees':coord}
        if not coord or wrong_graph or (expect_now and one_epoch):mism.append(name)
        cases.append(item)
    for name,value,omitted in [('single-omitted',None,True),('single-none',None,False),('single-zero',0,False),('single-100',100,False)]:check(name,'single',value,omitted)
    check('bulk-zero','bulk',0,expect_now=True)
    check('bulk-100','bulk',100,repeat=True)
    check('fallback-zero','bulk',0,fail=True)
    check('fallback-100','bulk',100,fail=True,repeat=True)
    # Direct actual NativeAPI empty timestamp invokes clock; string0 is epoch.
    start=int(time.time());native.classMethodValue('Graph.KG.TemporalIndex','InsertEdge','clock7','clk:direct-empty','R','end','',1,'',0,0,'')
    end=int(time.time());rows=e.get_edges_in_window(start=0,end=end+180,source='clk:direct-empty',graph='clock7')
    direct={'wall_clock_bounds':[start,end],'window_rows':rows,'agrees':len(rows)==1 and start-5<=rows[0]['ts']<=end+5}
    if not direct['agrees']:mism.append('direct-empty')
    # Input-derived count predicates retain valid collision neighbors.
    normal=next(x for x in cases if x['name']=='bulk-100');fallback=next(x for x in cases if x['name']=='fallback-100')
    counts=normal['second']=={'written':0,'collisions':1,'skipped':0} and fallback['second']=={'written':1,'collisions':0,'skipped':0}
    if not counts:mism.append('collision-counts')
    out={'verdict':'AGREES' if not mism else 'DISAGREES','comparisons':len(cases)+1,'mismatches':mism,'cases':cases,'direct_empty':direct,'collision_count_neighbor':counts,
        'scope':'Actual writer/store/native driver/TemporalIndex/window, graph and inclusive epoch endpoints; controlled BulkInsertCounts unavailability occurs before any native write. Local UTC seconds only bounds observed current time; no shared/monotonic clock or partial-prefix replay proof.',
        'container':h['NAME'],'port':h['PORT'],'identity_checked':True,'source_inputs':{str(helper.relative_to(REPO)):hashlib.sha256(helper.read_bytes()).hexdigest()},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    p=Path(__file__).with_suffix('.json');p.write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps({'verdict':out['verdict'],'comparisons':out['comparisons'],'mismatches':mism,'counts':counts}));c.close();assert not mism
if __name__=='__main__':main()
