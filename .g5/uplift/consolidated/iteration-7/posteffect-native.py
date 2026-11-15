"""Actual writes followed by explicit lost-reply port fault; no network fault claim."""
import json,runpy,time,hashlib
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
class Port:
    def __init__(self,native,after):self.native=native;self.after=after;self.calls=[]
    def classMethodValue(self,cls,method,*args):
        rec={'method':method,'args':args};self.calls.append(rec)
        if method=='BulkInsertCounts':
            if self.after:rec['actual_native_reply']=self.native.classMethodValue(cls,method,*args)
            rec['fault']='controlled lost reply after actual completion' if self.after else 'controlled prewrite unavailable'
            raise RuntimeError(rec['fault'])
        return self.native.classMethodValue(cls,method,*args)
    def __getattr__(self,k):return getattr(self.native,k)
def main():
    c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);e.ledger.disable();e.erase_all();store=e._store;native=store._iris_obj();out=[]
    for name,values,after in [('zero',[0],True),('positive',[100],True),('mixed',[0,100],True),('prewrite',[0,100],False)]:
        graph='ack7_'+name;port=Port(native,after);start=int(time.time())
        edges=[{'s':'ack:'+str(i),'p':'R','o':'end','ts':v} for i,v in enumerate(values)]
        with patch.object(store,'_iris_obj',return_value=port):ret=e.bulk_create_edges_temporal(edges,graph=graph)
        end=int(time.time());rows=e.get_edges_in_window(start=0,end=end+180,graph=graph)
        expected_count=len(values)+(values.count(0) if after else 0)
        epoch=[r for r in rows if r['ts']==0];recent=[r for r in rows if start-5<=r['ts']<=end+5];hundred=[r for r in rows if r['ts']==100]
        agrees=len(rows)==expected_count and len(epoch)==values.count(0) and len(recent)==(values.count(0) if after else 0) and len(hundred)==values.count(100) and int(ret)==len(values) and ret.collisions==0
        out.append({'name':name,'inputs':edges,'fault_after_actual_success':after,'port':port.calls,'rows':rows,'wall_clock_bounds':[start,end],'returned':{'written':int(ret),'collisions':ret.collisions,'skipped':ret.skipped},'agreement':agrees})
    result={'verdict':'AGREES' if all(x['agreement'] for x in out) else 'DISAGREES','comparisons':len(out),'cases':out,'identity_checked':True,'container':h['NAME'],
        'scope':'Actual unchanged native Counts/InsertEdge and public writer/window; injected exception occurs after completed native success, before caller accepts reply. This is not real TCP/partial-prefix fault evidence. Native leaves are real; expected result is source-derived, not yet a proved composed model.',
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'verdict':result['verdict'],'comparisons':len(out),'event_counts':[len(x['rows']) for x in out]}));c.close();assert result['verdict']=='AGREES'
if __name__=='__main__':main()
