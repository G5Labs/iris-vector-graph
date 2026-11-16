"""Real temporal writer -> snapshot ZIP/global import -> one-call and paged readers.

Only this task's hostname-checked disposable IRIS is writable. Integer weights and
small typed attrs avoid an unclaimed floating/JSON-codec equivalence proof.
"""
import hashlib,importlib.util,inspect,json,logging,os,sys,textwrap,time,types,zipfile
from pathlib import Path
from unittest.mock import patch
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN_DIR=bc.import_pin()
import iris,iris.dbapi
from tests import conftest as fx
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph._engine import snapshot as snap
NAME='ivg-uplift-next-20261115';PORT=35975
EVENTS=[('',0,'zero','R','b',1,{'n':1,'label':'default'},False),
 ('tw_a',0,'zero','R','b',2,{'n':2,'label':'named'},False),
 ('tw_a',20,'c','S','d',3,{'n':3,'label':'last'},True),
 ('tw_b',10,'other','R','end',4,{'n':4},False)]
def connect():
    if os.environ.get('IVG_TEMPORAL_NATIVE')!='1':raise SystemExit('set IVG_TEMPORAL_NATIVE=1 only for this task runtime')
    c=iris.dbapi.connect(hostname='127.0.0.1',port=PORT,namespace='USER',username='_SYSTEM',password='SYS')
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c),fx.docker_container_hostname(NAME),fx.docker_container_id(NAME)):
        c.close();raise RuntimeError('wrong IRIS instance')
    return c
def project(rows,attrs=False):
    return sorted([{'s':r['s'],'p':r['p'],'o':r['o'],'ts':r['ts'],'w':r['w'],**({'attrs':r['attrs']} if attrs else {})} for r in rows],key=lambda r:(r['ts'],r['s'],r['p'],r['o']))
def expected(graph,direction,with_attrs,restored=False):
    return sorted([{'s':s,'p':p,'o':o,'ts':ts,'w':w,**({'attrs':{k:(str(v) if restored and isinstance(v,(int,float)) else v) for k,v in a.items()}} if with_attrs else {})}
        for g,ts,s,p,o,w,a,suppress in EVENTS if g==graph and not(direction=='in' and suppress)],key=lambda r:(r['ts'],r['s'],r['p'],r['o']))
def observe(e):
    allrows={}
    for graph in ['', 'tw_a','tw_b']:
        row={}
        for direction in ['out','in']:
            once=e.get_edges_in_window(start=0,end=20,direction=direction,graph=graph)
            with e.iter_edges_in_window(0,20,direction=direction,attrs=True,page_size=1,graph=graph) as cur:
                paged=list(cur);trips=cur.round_trips
            row[direction]={'one':project(once),'paged':project(paged,True),'trips':trips}
        row['empty_sources']=list(e.iter_edges_in_window(0,20,sources=[],graph=graph))
        allrows[graph]=row
    return allrows
def agreement(got,restored=False):
    return all(got[g][direction]['one']==expected(g,direction,False,restored) and got[g][direction]['paged']==expected(g,direction,True,restored)
        and got[g]['empty_sources']==[] for g in ['', 'tw_a','tw_b'] for direction in ['out','in'])
def rewrite(original,out,kind):
    with zipfile.ZipFile(original) as z:files={n:z.read(n) for n in z.namelist()}
    bad=None
    if kind=='layout':
        meta=json.loads(files['metadata.json']);meta['layout']='different-layout';files['metadata.json']=json.dumps(meta).encode()
    if kind=='bad_line':
        name='globals/KG.ndjson';lines=files[name].decode().splitlines()
        for i,line in enumerate(lines):
            x=json.loads(line);k=x.get('k',[])
            if len(k)==6 and k[0]=='tout' and str(k[1])=='0' and str(k[2])=='0':
                k[-1]='';bad=x;lines[i]=json.dumps(x);break
        assert bad is not None
        files[name]=('\n'.join(lines)+'\n').encode()
    with zipfile.ZipFile(out,'w') as z:
        for n,b in files.items():z.writestr(n,b)
    return bad
def main():
    start=time.monotonic();c=connect();e=IRISGraphEngine(c,embedding_dimension=8)
    e.ledger.disable();e.erase_all()
    for g,ts,s,p,o,w,a,suppress in EVENTS:
        assert e.create_edge_temporal(s,p,o,timestamp=ts,weight=w,attrs=a,suppress_reverse_index=suppress,graph=g)
    before=observe(e);assert agreement(before),before
    work=Path(os.environ.get('RUN_DIR','/Users/ziniuw/runs/ivg-iteration6-temporal-20261115'))/'native-temporal';work.mkdir(parents=True,exist_ok=True)
    original=work/'original.zip';e.save_snapshot(str(original))
    e.erase_all();assert all(not x['out']['one'] for x in observe(e).values())
    restored=e.restore_snapshot(str(original));after=observe(e);mism=[]
    if not agreement(after,restored=True):mism.append({'case':'as_built_roundtrip','got':after})
    intended_types_preserved=agreement(after,restored=False)
    # Refuse before erase, including a live SQL sentinel and both temporal readers.
    e.create_node('keep:sentinel');bad_layout=work/'bad-layout.zip';rewrite(original,bad_layout,'layout')
    refused=False
    try:e.restore_snapshot(str(bad_layout))
    except ValueError:refused=True
    same=observe(e)==after and e.get_node('keep:sentinel') is not None
    if not refused or not same:mism.append({'case':'layout','refused':refused,'unchanged':same})
    # Reintroduce the historical exporter sentinel in a copy of the actual method.
    source=textwrap.dedent(inspect.getsource(snap.SnapshotMixin._export_global_to_ndjson));scope=dict(vars(snap));assert source.count('START = ""')==1
    exec(source.replace('START = ""','START = 0'),scope)
    mutant_path=work/'zero-start.zip'
    with patch.object(e,'_export_global_to_ndjson',types.MethodType(scope['_export_global_to_ndjson'],e)):
        e.save_snapshot(str(mutant_path))
    e.erase_all();e.restore_snapshot(str(mutant_path));mutant=observe(e)
    zero_detected=not mutant['']['out']['one'] and not any(r['ts']==0 for r in mutant['tw_a']['out']['one']) and mutant['tw_a']['out']['one']
    # One actual native-invalid subscript line: valid neighbors still restore.
    malformed_path=work/'bad-line.zip';bad=rewrite(original,malformed_path,'bad_line');native_error=None
    try:e._iris_obj().set(bad['v'],'^KG',*bad['k'])
    except Exception as ex:native_error={'type':type(ex).__name__,'error':str(ex)}
    e.erase_all();quiet=e.restore_snapshot(str(malformed_path));quiet_rows=observe(e)
    quiet_ok=native_error is not None and not quiet['failed_rows'] and 'KG' in quiet['restored_globals'] and not quiet_rows['']['out']['one'] and quiet_rows['tw_a']['out']['one']==expected('tw_a','out',False)
    if not quiet_ok:mism.append({'case':'quiet_line','got':quiet_rows,'restore':quiet,'native_error':native_error})
    # Test the existing scalar-preservation proposal in an actual method COPY.
    # Seed fresh typed writer values; an old string-only archive cannot recover lost types.
    e.erase_all()
    for g,ts,s,p,o,w,a,suppress in EVENTS:
        e.create_edge_temporal(s,p,o,timestamp=ts,weight=w,attrs=a,suppress_reverse_index=suppress,graph=g)
    scalar_scope=dict(vars(snap));assert source.count('"v": str(val)')==1
    exec(source.replace('"v": str(val)','"v": val'),scalar_scope)
    typed_path=work/'typed-scalar-variant.zip'
    typed_restore=typed_rows=None;typed_variant_error=None;typed_variant_ok=False
    try:
        with patch.object(e,'_export_global_to_ndjson',types.MethodType(scalar_scope['_export_global_to_ndjson'],e)):
            e.save_snapshot(str(typed_path))
        e.erase_all();typed_restore=e.restore_snapshot(str(typed_path));typed_rows=observe(e)
        typed_variant_ok=agreement(typed_rows,restored=False)
    except Exception as ex:
        # A proposed simplification is allowed to fail. Retain its verdict rather
        # than changing the as-built oracle or calling the proposal implemented.
        typed_variant_error={'type':type(ex).__name__,'error':str(ex)}
    # Leave the runtime at the valid neighbor.
    e.erase_all();e.restore_snapshot(str(original));final=observe(e);changed=json.loads(json.dumps(final));changed['tw_a']['out']['paged'][0]['attrs']['n']=99
    detection={'zero_start_exporter':bool(zero_detected),'changed_final_attr':agreement(final,restored=True) and not agreement(changed,restored=True)}
    c.close()
    out=bc.write_receipt('temporal_restore',Path(__file__),{'verdict':'AGREES' if not mism and all(detection.values()) else 'DISAGREES',
        'comparisons':7,'mismatch_count':len(mism),'mismatches':mism,'before':before,'after':after,'restore':restored,
        'intended_scalar_types':{'preserved':intended_types_preserved,'disposition':'VIOLATED; inherited F-1804; original DISAGREES receipt retained'},
        'scalar_preserving_variant':{'actual_method_copy':True,'agrees':typed_variant_ok,'rows':typed_rows,'restore':typed_restore,'error':typed_variant_error,'disposition':'raw-value-only simplification retired if serialization fails; no product change','scope':'unimplemented candidate; actual native Decimal values can refuse JSON serialization, so merely removing str() is insufficient'},
        'layout':{'refused':refused,'unchanged':same},'zero_start':mutant,
        'quiet_line':{'restore':quiet,'rows':quiet_rows,'native_refusal':native_error,'as_built_agrees':bool(quiet_ok),'intended_failure_reporting':'VIOLATED; inherited F-C1802'},
        'detection':detection,'native':{'container':NAME,'port':PORT,'identity_checked':True},'pin':bc.pin_identity(PIN_DIR),
        'elapsed':time.monotonic()-start,'observed':'actual create_edge_temporal, snapshot ZIP/global walk/import, raw native refusal, one-call QueryWindow/store and paged TemporalWindow/consumer with attrs, default/named graph and epoch0',
        'substituted':'none in normal/layout/bad-subscript worlds; exporter mutant is an altered actual Python method in the disposable runtime. No arbitrary provider fault, concurrent read/write, huge window or general codec proof.',
        'formal_relation':'global key/scalar atoms, exact integer weights and typed attrs; source first-write transition -> serialized keys/values -> import -> per-edge query projection; paging lifecycle reused from stamped imported model'})
    # The binding also depends on the imported formal definitions, beyond the shared helper's root stamp.
    body=json.loads(out.read_text());dep=HERE.parent/'temporal_window_reader/temporal_window_reader.rs';body['inputs'][str(dep.relative_to(bc.REPO))]=bc.sha(dep);out.write_text(json.dumps(body,indent=2,sort_keys=True)+'\n')
    print(out);print(json.dumps({'mismatches':len(mism),'detection':detection,'elapsed':time.monotonic()-start,'native_line_refused':native_error is not None}));return int(bool(mism) or not all(detection.values()))
if __name__=='__main__':raise SystemExit(main())
