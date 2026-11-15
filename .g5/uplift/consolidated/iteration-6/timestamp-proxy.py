"""Source survey: real Python temporal caller/store up to a recording Native API port.

No native runtime is contacted and no source file is changed. Clock resolution,
ObjectScript comparison/coercion and persisted observations are not reproduced.
"""
import inspect,json,logging,sys,textwrap,time,hashlib
from pathlib import Path
from unittest.mock import MagicMock,patch
logging.disable(logging.CRITICAL)
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN))
from iris_vector_graph._engine import temporal as tm
from iris_vector_graph.stores.iris_sql_store import IRISGraphStore

class Native:
    def __init__(self,fail_bulk=False):self.fail_bulk=fail_bulk;self.calls=[]
    def classMethodValue(self,cls,method,*args):
        self.calls.append({'class':cls,'method':method,'args':args})
        if method=='BulkInsertCounts':
            if self.fail_bulk:raise RuntimeError('injected unavailable BulkInsertCounts before writes')
            return '1:0:0'
        if method=='InsertEdge':return 1
        raise AssertionError((cls,method))

def fixture(fail_bulk=False):
    native=Native(fail_bulk);conn=MagicMock();store=IRISGraphStore(conn);store._namespace_checked=True
    store._iris_obj=lambda:native
    engine=tm.TemporalMixin.__new__(tm.TemporalMixin);engine._store=store;engine.conn=conn
    engine._adjacency_indexed=True;engine._temporal_structural_rows=False
    return engine,store,native

def single(value,omitted=False,fn=None):
    engine,store,native=fixture()
    try:
        with patch.object(tm,'_ledger_strict',lambda *_:False):
            result=(fn or tm.TemporalMixin.create_edge_temporal)(engine,'a','R','b',**({} if omitted else {'timestamp':value}))
        outcome={'kind':'value','result':result}
    except Exception as ex:outcome={'kind':'error','type':type(ex).__name__,'message':str(ex)}
    return {'input':value,'omitted':omitted,'outcome':outcome,'native_port_calls':native.calls}

def bulk(edge,fail=False):
    engine,store,native=fixture(fail)
    try:
        with patch.object(tm,'_ledger_strict',lambda *_:False):result=engine.bulk_create_edges_temporal([edge])
        outcome={'kind':'value','count':int(result),'collisions':result.collisions,'skipped':result.skipped}
    except Exception as ex:outcome={'kind':'error','type':type(ex).__name__,'message':str(ex)}
    return {'edge':edge,'fail_bulk':fail,'outcome':outcome,'native_port_calls':native.calls}

def main():
    start=time.monotonic();singles=[single(None,True)]+[single(v) for v in [None,0,'0',100,'100','',-1]]
    base={'s':'a','p':'R','o':'b'}
    edges=[{**base,'ts':0},{**base,'timestamp':0},{**base,'ts':'0'},{**base,'ts':100},base,
        {**base,'ts':None},{**base,'ts':''},{**base,'ts':0,'timestamp':100},{**base,'ts':100,'timestamp':0}]
    batches=[bulk(e) for e in edges]+[bulk({**base,'ts':v},True) for v in [0,100]]
    for result in singles[:5]:
        assert result['native_port_calls'][0]['args'][4] in ['0','100']
    assert singles[0]['native_port_calls'][0]['args'][4]=='0'
    assert singles[1]['native_port_calls'][0]['args'][4]=='0'
    assert batches[0]['native_port_calls'][0]['method']=='BulkInsertCounts'
    assert json.loads(batches[0]['native_port_calls'][0]['args'][1])[0]['ts']==0
    assert batches[-2]['native_port_calls'][-1]['method']=='InsertEdge' and batches[-2]['native_port_calls'][-1]['args'][4]=='0'
    for row in batches[4:7]:assert row['outcome']['kind']=='error' and not row['native_port_calls']
    # A specific timestamp-carrier mutation is detected at the final Python port.
    source=textwrap.dedent(inspect.getsource(tm.TemporalMixin.create_edge_temporal));find='timestamp=int(timestamp) if timestamp is not None else 0';assert source.count(find)==1
    scope=dict(vars(tm));exec(source.replace(find,'timestamp=int(timestamp) if timestamp is not None else ""'),scope)
    mutant=single(None,fn=scope['create_edge_temporal'])
    detection=mutant['native_port_calls'][0]['args'][4]=='' and mutant['native_port_calls']!=singles[1]['native_port_calls']
    out={'kind':'actual Python port observation only','singles':singles,'batches':batches,'mutation_empty_for_none_detected':detection,
        'not_observed':['ObjectScript clock resolution','native-driver coercion','IRIS persistence/window','partial bulk failure after a prefix'],
        'substituted':'Native API recording endpoint and namespace/ledger/setup guards; no database connection',
        'source_sha256':{p:hashlib.sha256((PIN/p).read_bytes()).hexdigest() for p in ['iris_vector_graph/_engine/temporal.py','iris_vector_graph/stores/iris_sql_store.py','iris_src/src/Graph/KG/TemporalIndex.cls']},'elapsed':time.monotonic()-start}
    Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'single_cases':len(singles),'batch_cases':len(batches),'detection':detection,'elapsed':out['elapsed']}));assert detection
if __name__=='__main__':main()
