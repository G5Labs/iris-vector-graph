"""Actual caller/store/catch/paged readers over executing prefix-fault Native port.
The port is a specified integer/insert/window adapter, not live IRIS or TCP failure.
"""
from __future__ import annotations
import copy,importlib.util,inspect,itertools,json,logging,socket,sys,textwrap,time
from pathlib import Path
from unittest.mock import patch
NETWORK=patch.object(socket.socket,'connect',side_effect=AssertionError('retry binding forbids network'))
CONNECT=NETWORK.start()
HERE=Path(__file__).resolve().parent
HELPER=HERE.parent/'temporal_clock'/'binding.py'
spec=importlib.util.spec_from_file_location('retry_clock_adapter',HELPER)
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
bc=a.bc;tm=a.tm;IRISGraphStore=a.IRISGraphStore
logging.disable(logging.CRITICAL)

class Native(a.Native):
    def __init__(self,cutoff,graph,seed,reverse):
        super().__init__(clock=(300,),state=seed,rev=seed)
        self.cutoff=cutoff;self.processed=0;self.actual_counts=None
    def classMethodValue(self,cls,method,*args):
        if method!='BulkInsertCounts':return super().classMethodValue(cls,method,*args)
        self.calls.append({'class':cls,'method':method,'args':args})
        graph,wire,upsert,mode=args;assert upsert=='0' and mode==''
        rows=json.loads(wire);written=collisions=0
        k=len(rows) if self.cutoff is None else min(self.cutoff,len(rows))
        for i,row in enumerate(rows[:k]):
            ts=int(row['ts']);ts=200+i if ts==0 else ts
            code=self.put(graph,row['s'],row['p'],row['o'],ts,row['w'],not bool(row.get('sri',0)))
            written+=code==1;collisions+=code==-1;self.processed+=1
        self.actual_counts=[written,collisions,0]
        if self.cutoff is not None:raise RuntimeError('controlled error after completed native-port prefix')
        return f'{written}:{collisions}:0'

PATTERNS=[[],[0],[100],['0'],[0,100],[100,0],[0,0],[100,100]]

def edges(pattern,same=False):
    return [{'s':'a' if same or i==0 else 'c','p':'R','o':'b','ts':v,'w':7} for i,v in enumerate(pattern)]

def oracle(es,cutoff,graph,reverse,seed):
    """Independent twin of counts/run: derive prefix effects, then ALL fallback."""
    state=dict(seed);rev=dict(seed)
    normalized=[]
    try:
        for e in es:
            short=e.get('ts',a.MISSING);long=e.get('timestamp',a.MISSING)
            n=a.payload(False,short,long,shape='unknown' not in e)
            normalized.append((e['s'],e['p'],e['o'],n,e.get('w',1)))
    except (ValueError,TypeError,KeyError):return {'kind':'error'},state,rev
    if not normalized:return {'kind':'count','count':0,'collisions':0,'skipped':0},state,rev
    def put(row,normal,index):
        s,p,o,n,w=row;ts=(200+index if n==0 else n) if normal else n
        k=(graph,ts,s,p,o);exists=k in state
        if not exists:
            state[k]=w
            if reverse:rev[k]=w
        return exists
    k=len(normalized) if cutoff is None else min(cutoff,len(normalized));written=collisions=0
    for i,row in enumerate(normalized[:k]):
        existed=put(row,True,i);written+=not existed;collisions+=existed
    if cutoff is None:return {'kind':'count','count':written,'collisions':collisions,'skipped':0},state,rev
    for i,row in enumerate(normalized):put(row,False,i)
    return {'kind':'count','count':len(normalized),'collisions':0,'skipped':0},state,rev

def invoke(e,es,graph,reverse):
    try:
        with patch.object(tm,'_ledger_strict',lambda *_:False):r=e.bulk_create_edges_temporal(es,graph=graph,suppress_reverse_index=not reverse)
        return {'kind':'count','count':int(r),'collisions':r.collisions,'skipped':r.skipped}
    except (ValueError,TypeError) as ex:return {'kind':'error','exception':type(ex).__name__}

def case(es,cutoff,graph='',reverse=True,seed_time=None,change=False):
    seed={} if seed_time is None else {(graph,seed_time,'a','R','b'):9}
    want,state,rev=oracle(es,cutoff,graph,reverse,seed)
    native=Native(cutoff,graph,seed,reverse);e,_=a.fixture(native)
    got=invoke(e,es,graph,reverse);views=a.read(e,graph);expected=a.expected_views(state,rev,graph)
    if change:
        for rows in views:
            if rows:rows[0]['timestamp']=999;break
    agrees={k:v for k,v in got.items() if k!='exception'}==want and native.state==state and native.rev==rev and views==expected
    # Refused/empty calls must not consult the supplied faulting Counts provider.
    if want.get('kind')=='error' or not es:agrees=agrees and not [x for x in native.calls if x['class']=='Graph.KG.TemporalIndex']
    return {'input':es,'cutoff':cutoff,'graph':graph,'reverse':reverse,'seed_time':seed_time,'actual':got,'expected':want,
        'actual_state':[[list(k),v] for k,v in sorted(native.state.items())],'expected_state':[[list(k),v] for k,v in sorted(state.items())],
        'processed_prefix':native.processed,'port_counts_before_error':native.actual_counts,'port':native.calls,'windows':views,'agrees':agrees}

def source_variant(owner,name,find,replace):
    s=textwrap.dedent(inspect.getsource(getattr(owner,name)));assert s.count(find)==1,(name,find,s.count(find))
    ns=dict(vars(sys.modules[owner.__module__]));exec(s.replace(find,replace),ns);return ns[name]

def main():
    start=time.monotonic();cases=[]
    for pattern,same,graph,reverse,seed in itertools.product(PATTERNS,[False,True],['','tenant'],[False,True],[None,0,100,200]):
        es=edges(pattern,same)
        for cutoff in [None,*range(len(es)+1)]:cases.append(case(es,cutoff,graph,reverse,seed))
    for malformed in [{'s':'c','p':'R','o':'b'},{'s':'c','p':'R','o':'b','ts':'bad'}]:
        for cutoff in [None,0,1,2]:cases.append(case([{'s':'a','p':'R','o':'b','ts':0},malformed],cutoff))
    detection={}
    base=case(edges([0]),1)
    detection['changed_final_timestamp_rejected']=base['agrees'] and not case(edges([0]),1,change=True)['agrees']
    fn=source_variant(IRISGraphStore,'bulk_write_temporal_edges','first_error = None\n        for edge in edges:','first_error = None\n        for edge in []:')
    with patch.object(IRISGraphStore,'bulk_write_temporal_edges',fn):
        detection['actual_fallback_loop_removed']=not case(edges([0]),1)['agrees']
        detection['normal_success_neighbor_preserved']=case(edges([100]),None)['agrees']
    fn=source_variant(IRISGraphStore,'write_temporal_edge','str(timestamp),','"" if timestamp==0 else str(timestamp),')
    with patch.object(IRISGraphStore,'write_temporal_edge',fn):detection['actual_fallback_clock_rule_changed']=not case(edges([0]),1)['agrees']
    fn=source_variant(IRISGraphStore,'bulk_write_temporal_edges','inserted += 1','inserted += 0')
    with patch.object(IRISGraphStore,'bulk_write_temporal_edges',fn):detection['actual_fallback_count_changed']=not case(edges([100]),1,seed_time=100)['agrees']
    mism=[x for x in cases if not x['agrees']];verdict='AGREES' if not mism and all(detection.values()) and CONNECT.call_count==0 else 'DISAGREES'
    out=bc.write_receipt('retry_replay',Path(__file__),{'verdict':verdict,'comparisons':len(cases),'window_comparisons':len(cases)*len(a.QUERIES),'mismatch_count':len(mism),'mismatches':mism[:5],
        'samples':[c for c in cases if c['input'] in [edges([0]),edges([100]),edges([0,100])] and c['graph']=='' and c['reverse'] and c['seed_time'] is None],
        'detection':detection,'blocked_network_calls':CONNECT.call_count,'elapsed':time.monotonic()-start,'pin':bc.pin_identity(a.PIN_DIR),
        'scope':'Actual Python caller normalization/store/catch/whole-batch fallback/ported writer calls and public paged reader. Specified Native-port adapter executes completed-prefix/default-insert/time/window; no native/TCP/partial-within-item failure executed by this builder.',
        'provider_contract':'Fault occurs after k COMPLETE item operations or before all; actual fallback calls complete. Mode default insert, no attrs. Clocks at item i are200+i; fallback0 stays0. Prefix post-state derived, never supplied.',
        'residuals':['partial WriteStores raw/structural effects','real TCP loss','fallback item failures','upsert/skip/aggregate/latest effects','general JSON/numeric marshaling','strict ledger/concurrent writers']})
    r=json.loads(out.read_text())
    for rel in ['model.json','../temporal_clock/temporal_clock.rs','../temporal_restore/temporal_restore.rs','../temporal_window_reader/temporal_window_reader.rs','../temporal_clock/binding.py']:
        p=(HERE/rel).resolve();r['inputs'][str(p.relative_to(bc.REPO))]=bc.sha(p)
    for rel in ['iris_vector_graph/_engine/temporal.py','iris_vector_graph/stores/iris_sql_store.py','iris_vector_graph/_engine/temporal_window.py','iris_src/src/Graph/KG/TemporalIndex.cls','iris_src/src/Graph/KG/TemporalWindow.cls']:
        r['inputs'][rel]=bc.sha(a.PIN_DIR/rel)
    for rel in ['.g5/uplift/consolidated/iteration-7/posteffect-native.py','.g5/uplift/consolidated/iteration-7/posteffect-native.json']:
        p=bc.REPO/rel;r['inputs'][rel]=bc.sha(p)
    native=json.loads((bc.REPO/'.g5/uplift/consolidated/iteration-7/posteffect-native.json').read_text())
    assert native['verdict']=='AGREES' and native['comparisons']==4 and native['identity_checked'];r['root_native_comparisons']=4;r['root_native_scope']=native['scope']
    out.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps({'verdict':verdict,'comparisons':len(cases),'mismatches':len(mism),'detection':detection,'elapsed':time.monotonic()-start,'receipt':str(out)}))
    return int(verdict!='AGREES')
if __name__=='__main__':raise SystemExit(main())
