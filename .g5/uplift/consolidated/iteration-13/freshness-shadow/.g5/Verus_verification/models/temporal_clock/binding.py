"""Pinned real caller/store/window Python over an executing specified native port.

The adapter executes timestamp resolution, insert-only globals and window paging;
it is not IRIS or a substitute for root's independent native observations. Raw
Python parsing and payload construction are actual product bodies, not adapters.
"""
import inspect,itertools,json,logging,sys,textwrap,time
from pathlib import Path
from unittest.mock import MagicMock,patch
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN_DIR=bc.import_pin()
from iris_vector_graph._engine import temporal as tm
from iris_vector_graph.stores.iris_sql_store import IRISGraphStore

MISSING=object()
VALUES=[MISSING,None,'',0,'0',100,'100',-1,'-1',True,False,0.5,'bad']
def show(v):return {'missing':True} if v is MISSING else {'type':type(v).__name__,'value':v}

# Independent transcription of temporal_clock::single_payload/bulk_payload.
def payload(single,short,long=MISSING,shape=True):
    if single:
        if short is MISSING or short is None:return 0
        n=int(short)
        if n<0:raise ValueError('single nonnegative boundary')
        return n
    supplied=lambda v:v is not MISSING and v is not None and v!=''
    if not shape or not (supplied(short) or supplied(long)):raise ValueError('bulk shape')
    chosen=short if short is not MISSING and bool(short) else (long if long is not MISSING else 0)
    return int(chosen)

def model(single,short,long,available,ok,graph,reverse,duplicate,shape=True,now=200):
    try:n=payload(single,short,long,shape)
    except (ValueError,TypeError,OverflowError):n=None
    ts=None if n is None else (now if not single and available and n==0 else n)
    state={};rev={}
    if duplicate:
        k=(graph,ts if ts is not None else -2,'a','R','b');state[k]=9;rev[k]=9
    initial=dict(state);initial_rev=dict(rev)
    if n is None or not ok:return {'kind':'error'},initial,initial_rev
    k=(graph,ts,'a','R','b');exists=k in state
    if not exists:
        state[k]=7
        if reverse:rev[k]=7
    result={'kind':'single','value':True} if single else {'kind':'count','count':0 if available and exists else 1,
        'collisions':1 if available and exists else 0,'skipped':0}
    return result,state,rev

class Native:
    """Port contract: integer fragment, default insert, pre-effect refusal only."""
    def __init__(self,available=True,ok=True,clock=(200,),state=None,rev=None):
        self.available=available;self.ok=ok;self.clock_values=list(clock);self.clock_index=0
        self.state=dict(state or {});self.rev=dict(rev or {});self.calls=[];self.handles={};self.next_handle=0
    def now(self):
        value=self.clock_values[min(self.clock_index,len(self.clock_values)-1)];self.clock_index+=1;return value
    def put(self,graph,s,p,o,ts,w,reverse):
        key=(graph,ts,s,p,o)
        if key in self.state:return -1
        self.state[key]=float(w)
        if reverse:self.rev[key]=float(w)
        return 1
    def page(self,h,n):
        rows=self.handles[h];out=rows[:n];self.handles[h]=rows[n:]
        # The server stops on a full page before testing exhaustion.
        done=len(out)<n
        if done:del self.handles[h]
        return json.dumps({'h':h,'rows':out,'done':int(done)})
    def classMethodValue(self,cls,method,*args):
        self.calls.append({'class':cls,'method':method,'args':args})
        if cls=='Graph.KG.TemporalWindow':
            if method=='Open':
                graph,spec=args;spec=json.loads(spec);rows=[]
                for (g,t,s,p,o),w in (self.rev if spec['dir']=='in' else self.state).items():
                    src=o if spec['dir']=='in' else s
                    if g!=graph or not spec['start']<=t<=spec['end']:continue
                    if 'source' in spec and src!=spec['source']:continue
                    if 'sources' in spec and src not in spec['sources']:continue
                    if 'prefix' in spec and not src.startswith(spec['prefix']):continue
                    if 'predicates' in spec and p not in spec['predicates']:continue
                    rows.append({'s':s,'p':p,'o':o,'ts':t,'w':w})
                rows.sort(key=lambda r:(r['ts'],r['o'] if spec['dir']=='in' else r['s'],r['p'],r['s'] if spec['dir']=='in' else r['o']))
                self.next_handle+=1;h=self.next_handle;self.handles[h]=rows;return self.page(h,spec['page'])
            if method=='Next':return self.page(*args)
            raise AssertionError(method)
        assert cls=='Graph.KG.TemporalIndex',cls
        if method=='BulkInsertCounts':
            if not self.available:raise RuntimeError('injected unavailable Counts before any effects')
            if not self.ok:raise RuntimeError('injected provider refusal before any effects')
            graph,wire,upsert,mode=args;assert upsert=='0' and mode==''
            written=collisions=0
            for row in json.loads(wire):
                ts=int(row['ts']);ts=self.now() if ts==0 else ts
                code=self.put(graph,row['s'],row['p'],row['o'],ts,row['w'],not bool(row.get('sri',0)))
                written+=code==1;collisions+=code==-1
            return f'{written}:{collisions}:0'
        if method=='InsertEdge':
            if not self.ok:raise RuntimeError('injected provider refusal before any effects')
            graph,s,p,o,wire,w,attrs,upsert,suppress,mode=args;assert upsert=='0' and mode=='' and attrs==''
            # This is the documented/probed provider fragment, not proof of its
            # Integer marshaling or ObjectScript empty-string equality rules.
            ts=self.now() if wire=='' else int(wire)
            self.put(graph,s,p,o,ts,w,suppress=='0');return 1
        raise AssertionError(method)
    def classMethodVoid(self,cls,method,*args):
        assert cls=='Graph.KG.TemporalWindow' and method=='Close'
        self.handles.pop(args[0],None)

def fixture(native):
    conn=MagicMock();store=IRISGraphStore(conn);store._namespace_checked=True;store._iris_obj=lambda:native
    engine=tm.TemporalMixin.__new__(tm.TemporalMixin);engine._store=store;engine.conn=conn;engine._iris_obj=lambda:native
    engine._adjacency_indexed=True;engine._temporal_structural_rows=False
    return engine,store

def invoke(engine,single,short,long,graph,reverse,shape=True,fn=None):
    try:
        with patch.object(tm,'_ledger_strict',lambda *_:False):
            if single:
                kw={} if short is MISSING else {'timestamp':short}
                result=(fn or tm.TemporalMixin.create_edge_temporal)(engine,'a','R','b',weight=7,suppress_reverse_index=not reverse,graph=graph,**kw)
                return {'kind':'single','value':result}
            edge={'s':'a','p':'R','o':'b','w':7}
            if short is not MISSING:edge['ts']=short
            if long is not MISSING:edge['timestamp']=long
            if not shape:edge['unknown']=1
            result=(fn or tm.TemporalMixin.bulk_create_edges_temporal)(engine,[edge],graph=graph,suppress_reverse_index=not reverse)
            return {'kind':'count','count':int(result),'collisions':result.collisions,'skipped':result.skipped}
    except Exception as exc:return {'kind':'error','exception':type(exc).__name__}

QUERIES=[(-2,201,'same','out',None),(0,0,'same','out',None),(200,200,'same','out',None),
    (100,100,'same','out',None),(-1,-1,'same','out',None),(-2,201,'other','out',None),
    (-2,201,'same','in',None),(-2,201,'same','out',[])]
def read(engine,graph):
    result=[]
    for lo,hi,g,direction,sources in QUERIES:
        with engine.iter_edges_in_window(lo,hi,graph=graph if g=='same' else 'other',direction=direction,sources=sources,page_size=1) as cursor:
            result.append(list(cursor))
    return result
def expected_views(state,rev,graph):
    out=[]
    for lo,hi,g,direction,sources in QUERIES:
        rows=[]
        for (gg,t,s,p,o),w in (rev if direction=='in' else state).items():
            if gg!=(graph if g=='same' else 'other') or not lo<=t<=hi or sources==[]:continue
            rows.append({'s':s,'p':p,'o':o,'ts':t,'w':w,'source':s,'predicate':p,'target':o,'timestamp':t,'weight':w,'attrs':{}})
        rows.sort(key=lambda r:(r['ts'],r['o'] if direction=='in' else r['s'],r['p'],r['s'] if direction=='in' else r['o']))
        out.append(rows)
    return out

def run_case(single,short,long=MISSING,available=True,ok=True,graph='',reverse=True,duplicate=False,shape=True,fn=None):
    expected,state,rev=model(single,short,long,available,ok,graph,reverse,duplicate,shape)
    # Seed only preexisting rows, independently of the actual port's writes.
    _,initial,initial_rev=model(single,short,long,available,False,graph,reverse,duplicate,shape)
    native=Native(available,ok,state=initial,rev=initial_rev);engine,_=fixture(native)
    got=invoke(engine,single,short,long,graph,reverse,shape,fn);calls=list(native.calls);views=read(engine,graph)
    agrees={k:v for k,v in got.items() if k!='exception'}==expected and native.state==state and native.rev==rev and views==expected_views(state,rev,graph)
    return {'single':single,'short':show(short),'long':show(long),'available':available,'provider_ok':ok,'graph':graph,'reverse':reverse,
        'duplicate':duplicate,'shape_ok':shape,'actual':got,'expected':expected,'port':calls,'windows':views,'agrees':agrees}

def mutant(owner,name,find,replace):
    source=textwrap.dedent(inspect.getsource(getattr(owner,name)));assert source.count(find)==1,(name,find)
    scope=dict(vars(tm if owner is tm.TemporalMixin else sys.modules[IRISGraphStore.__module__]));exec(source.replace(find,replace),scope);return scope[name]

def special_cases():
    out=[]
    # One actual multi-item batch with distinct clock readings: timestamp is
    # resolved inside the server loop, independently for each item.
    native=Native(clock=(200,201));engine,_=fixture(native)
    with patch.object(tm,'_ledger_strict',lambda *_:False):
        count=engine.bulk_create_edges_temporal([{'s':'a','p':'R','o':'b','ts':0},{'s':'a','p':'R','o':'c','ts':0}])
    rows=list(engine.iter_edges_in_window(0,300,page_size=1));out.append({'case':'per-item-clock','rows':rows,'count':int(count),'agrees':[r['ts'] for r in rows]==[200,201] and int(count)==2})
    native=Native(clock=(200,));native.classMethodValue('Graph.KG.TemporalIndex','InsertEdge','','a','R','b','','7','','0','0','')
    engine,_=fixture(native);rows=list(engine.iter_edges_in_window(200,200));out.append({'case':'direct-native-empty','rows':rows,'agrees':len(rows)==1 and rows[0]['ts']==200})
    native=Native();engine,_=fixture(native)
    with patch.object(tm,'_ledger_strict',lambda *_:False):count=engine.bulk_create_edges_temporal([])
    out.append({'case':'empty-batch','count':int(count),'port':native.calls,'agrees':int(count)==0 and native.calls==[]})
    for bad in [{'s':'a','p':'R','o':'c'},{'s':'a','p':'R','o':'c','ts':'bad'}]:
        native=Native();engine,_=fixture(native)
        try:
            with patch.object(tm,'_ledger_strict',lambda *_:False):engine.bulk_create_edges_temporal([{'s':'a','p':'R','o':'b','ts':100},bad])
            refused=False
        except (ValueError,TypeError):refused=True
        out.append({'case':'late-invalid-validation-barrier','bad':bad,'refused':refused,'port':native.calls,'agrees':refused and not native.calls and not native.state})
    return out

def main():
    start=time.monotonic();cases=[]
    for short,ok,graph,reverse,duplicate in itertools.product(VALUES,[False,True],['','tenant'],[False,True],[False,True]):
        cases.append(run_case(True,short,ok=ok,graph=graph,reverse=reverse,duplicate=duplicate))
    for short,long,available,reverse,duplicate in itertools.product(VALUES,VALUES,[False,True],[False,True],[False,True]):
        cases.append(run_case(False,short,long,available=available,reverse=reverse,duplicate=duplicate,graph='tenant'))
    # Genuine malformed shape and a provider refusal are retained, not silently
    # filtered out of the comparison domain.
    for available in [False,True]:
        cases.append(run_case(False,0,available=available,shape=False))
        cases.append(run_case(False,0,available=available,ok=False))
    special=special_cases();detection={}
    fn=mutant(tm.TemporalMixin,'create_edge_temporal','timestamp=int(timestamp) if timestamp is not None else 0','timestamp=int(timestamp) if timestamp is not None else ""')
    detection['none-carrier-empty']=not run_case(True,None,fn=fn)['agrees']
    fn=mutant(tm.TemporalMixin,'bulk_create_edges_temporal','int(e.get("ts") or e.get("timestamp", 0))','int(e.get("ts", e.get("timestamp", 0)))')
    detection['alias-presence']=not run_case(False,0,100,fn=fn)['agrees']
    original=IRISGraphStore.bulk_write_temporal_edges
    fn=mutant(IRISGraphStore,'bulk_write_temporal_edges','                edge.get("timestamp", 0),','                "" if edge.get("timestamp", 0)==0 else edge.get("timestamp", 0),')
    with patch.object(IRISGraphStore,'bulk_write_temporal_edges',fn):detection['fallback-zero-empty']=not run_case(False,0,available=False)['agrees']
    assert IRISGraphStore.bulk_write_temporal_edges is original
    base=run_case(False,0);altered=json.loads(json.dumps(base['windows']));altered[2][0]['timestamp']=0
    _,expected_state,expected_rev=model(False,0,MISSING,True,True,'',True,False)
    wanted_views=expected_views(expected_state,expected_rev,'')
    detection['changed-final-coordinate']=base['windows']==wanted_views and altered!=wanted_views
    mismatches=[c for c in cases if not c['agrees']];verdict='AGREES' if not mismatches and all(s['agrees'] for s in special) and all(detection.values()) else 'DISAGREES'
    out=bc.write_receipt('temporal_clock',Path(__file__),{'verdict':verdict,'comparisons':len(cases),'window_comparisons':len(cases)*len(QUERIES),
        'mismatch_count':len(mismatches),'mismatches':mismatches[:10],'cases':cases,'special':special,'detection':detection,'elapsed':time.monotonic()-start,
        'pin':bc.pin_identity(PIN_DIR),'observed':'actual TemporalMixin single/bulk normalization, actual IRISGraphStore port serialization and prewrite fallback, actual public iter_edges_in_window -> window_spec -> TemporalWindowCursor -> event projection',
        'provider_substitution':'executing Python native-port contract for integer clock/global/window fragment, with default insert and pre-effect refusal. No IRIS or driver is executed by this builder. Namespace/ledger guards and structural/SQL mirrors substituted.',
        'formal_relation':'temporal_clock::single_payload/bulk_shape/bulk_selected/bulk_payload/coordinate/write/call_single/call_bulk/observe; imported stores::insert/weight and paging::window_spec/server_admits',
        'residuals':['full ObjectScript numeric/native Integer marshaling','partial-prefix batch errors and errors after raw store effects','millisecond class','strict ledger and structural mirror transaction','JSON parser and arbitrary Python int objects']})
    receipt=json.loads(out.read_text())
    for name in ['model.json','../temporal_restore/temporal_restore.rs','../temporal_window_reader/temporal_window_reader.rs']:
        p=(HERE/name).resolve();receipt['inputs'][str(p.relative_to(bc.REPO))]=bc.sha(p)
    receipt['source_sha256']={p:bc.sha(PIN_DIR/p) for p in ['iris_vector_graph/_engine/temporal.py','iris_vector_graph/_engine/temporal_window.py','iris_vector_graph/stores/iris_sql_store.py','iris_src/src/Graph/KG/TemporalIndex.cls','iris_src/src/Graph/KG/TemporalWindow.cls']}
    # Root's serial native observations, if already available, are stamped
    # rather than replayed here; their absence is an explicit correspondence gap.
    native=[]
    for p in sorted((bc.REPO/'.g5/uplift/consolidated/iteration-7').glob('timestamp-*native.*')):
        if p.suffix in ['.py','.json']:
            receipt['inputs'][str(p.relative_to(bc.REPO))]=bc.sha(p);native.append(str(p.relative_to(bc.REPO)))
    receipt['provider_evidence_from_root']=native
    root_native=bc.REPO/'.g5/uplift/consolidated/iteration-7/timestamp-native.json'
    if root_native.is_file():
        evidence=json.loads(root_native.read_text());assert evidence['verdict']=='AGREES' and evidence['comparisons']==9 and evidence['identity_checked']
        receipt['root_native_comparisons']=evidence['comparisons'];receipt['root_native_scope']=evidence['scope']
        for relative,digest in evidence['source_inputs'].items():
            p=bc.REPO/relative;assert bc.sha(p)==digest;receipt['inputs'][relative]=digest
    out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(out);print(json.dumps({'verdict':verdict,'comparisons':len(cases),'mismatches':len(mismatches),'detection':detection,'elapsed':time.monotonic()-start}));return int(verdict!='AGREES')
if __name__=='__main__':raise SystemExit(main())
