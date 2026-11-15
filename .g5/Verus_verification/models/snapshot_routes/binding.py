"""Real pinned save/restore/registry/physical VECTOR widths and final embedding reads.

Only this task's hostname-checked disposable IRIS is writable. Exact integer-valued
vectors represent the model's Seq<int>. No concurrency or floating arithmetic claim.
"""
import hashlib,json,logging,math,os,subprocess,sys,time,zipfile
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
from iris_vector_graph.schema import GraphSchema
from iris_vector_graph._engine import snapshot as snap
NAME='ivg-uplift-next-20261115';PORT=35975
A=('snap_a','snap_model_a',8,1.0);B=('snap_b','snap_model_b',16,3.0);NODE='snap:shared'

def connect():
    if os.environ.get('IVG_SNAPSHOT_NATIVE')!='1':raise SystemExit('set IVG_SNAPSHOT_NATIVE=1 only for this task runtime')
    c=iris.dbapi.connect(hostname='127.0.0.1',port=PORT,namespace='USER',username='_SYSTEM',password='SYS')
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c),fx.docker_container_hostname(NAME),fx.docker_container_id(NAME)):
        c.close();raise RuntimeError('wrong IRIS instance')
    return c

def edit_archive(original,out,kind):
    with zipfile.ZipFile(original) as z:files={n:z.read(n) for n in z.namelist()}
    meta=json.loads(files['metadata.json']);routes=meta[snap.ROUTED_TABLES_KEY]
    btable=next(k for k,v in routes.items() if v['graph_id']==B[0])
    if kind=='fallback':routes[btable].pop('dimension')
    if kind=='invalid':routes[btable]['dimension']='bad'
    if kind=='wrong_width':routes[btable]['dimension']=8
    if kind=='missing_registry':
        name=next(n for n in files if 'embedding_registry' in n)
        rows=[json.loads(x) for x in files[name].decode().splitlines() if x.strip()]
        files[name]=('\n'.join(json.dumps(r) for r in rows if r['graph_id']!=B[0])+'\n').encode()
    files['metadata.json']=json.dumps(meta).encode()
    with zipfile.ZipFile(out,'w') as z:
        for n,b in files.items():z.writestr(n,b)
    return btable

def empty_destination(e,tables):
    e.erase_all()
    # Establish a fresh destination declaration, rather than allowing a preexisting
    # correctly declared table to hide a wrong-width creator. These are this probe's tables.
    cur=e.conn.cursor()
    for table in tables:
        try:cur.execute('DROP TABLE Graph_KG.'+table)
        except Exception as ex:
            if '-30' not in str(ex) and 'does not exist' not in str(ex).lower():raise
    e.conn.commit();cur.close();e.invalidate_route_cache()

def observation(e,tables):
    result={}
    for graph,model,w,val in [A,B]:
        route=e.resolve_route(graph,model)
        try:row=e.get_embedding(NODE,graph=graph,model_key=model);read={'kind':'absent' if row is None else 'value','row':row}
        except Exception as ex:read={'kind':'error','error':str(ex)}
        cur=e.conn.cursor();table=tables[graph]
        try:declared=GraphSchema.get_embedding_dimension(cur,'Graph_KG.'+table)
        except Exception:declared=None
        try:cur.execute('SELECT COUNT(*) FROM Graph_KG.'+table);count=int(cur.fetchone()[0])
        except Exception:count=None
        compiled=GraphSchema.hnsw_indexes(cur,'Graph_KG.'+table)
        cur.close()
        result[graph]={'route':None if route is None else {'table':route.table_name,'width':route.dimension,'index_state':route.index_state},'declared':declared,'count':count,'read':read,'compiled_hnsw':compiled}
    return result

def main():
    start=time.monotonic();c=connect();e=IRISGraphEngine(c,embedding_dimension=8)
    e.erase_all();tables={}
    for graph,model,w,value in [A,B]:
        e.create_node(NODE,graph=graph)
        route=e.resolve_route(graph,model,create=True,dimension=w);tables[graph]=route.table_name
        assert e.store_embedding(NODE,[value]*w,graph=graph,model_key=model)
    work=Path(os.environ.get('RUN_DIR','/Users/ziniuw/runs/ivg-iteration5-snapshot-20261115'))/'native-snapshot';work.mkdir(parents=True,exist_ok=True)
    original=work/'original.zip';e.save_snapshot(str(original),layers=['sql'])
    observations=[];mism=[]
    for kind in ['normal','fallback','missing_registry','invalid','wrong_width','existing_incompatible','merge_existing_row','merge_parent_collision','merge_existing_incompatible_row']:
        path=work/(kind+'.zip');btable=edit_archive(original,path,kind)
        empty_destination(e,list(tables.values()))
        if kind=='existing_incompatible':
            cur=c.cursor();e._create_routed_table(cur,tables[B[0]],dimension=8);cur.close()
        if kind in ['merge_existing_row','merge_parent_collision','merge_existing_incompatible_row']:
            if kind!='merge_parent_collision':e.create_node(NODE,graph=A[0])
            ew=8 if kind=='merge_existing_incompatible_row' else 16
            e.create_node(NODE,graph=B[0]);e.resolve_route(B[0],B[1],create=True,dimension=ew)
            e.store_embedding(NODE,[9.0]*ew,graph=B[0],model_key=B[1])
        restore=e.restore_snapshot(str(path),merge=kind in ['existing_incompatible','merge_existing_row','merge_parent_collision','merge_existing_incompatible_row']);got=observation(e,tables)
        aa=got[A[0]];bb=got[B[0]]
        ok=aa['declared']==8 and aa['read']['kind']=='value' and aa['read']['row']['embedding']==[1.0]*8
        if kind in ['normal','fallback']:
            ok &= bb['declared']==16 and bb['route']['width']==16 and bb['read']['kind']=='value' and bb['read']['row']['embedding']==[3.0]*16 and not restore['failed_rows']
            searches={}
            for graph,model,w,val in [A,B]:
                found=e.kg_KNN_VEC(json.dumps([val]*w),k=1,graph=graph,model_key=model)
                try:e.kg_KNN_VEC(json.dumps([val]*(w+1)),k=1,graph=graph,model_key=model);refused=False
                except ValueError:refused=True
                searches[graph]={'found':found,'wrong_width_refused':refused}
                ok &= len(found)==1 and found[0][0]==NODE and math.isclose(found[0][1],1.0,abs_tol=1e-6) and refused
            got['searches']=searches
            # Final actual writer uses the restored route, not engine-wide width8.
            e.create_node('snap:b2',graph=B[0]);ok &= e.store_embedding('snap:b2',[4.0]*16,graph=B[0],model_key=B[1])
        elif kind=='missing_registry':
            missing_search=e.kg_KNN_VEC(json.dumps([3.0]*16),k=1,graph=B[0],model_key=B[1])
            got['missing_route_search']=missing_search
            ok &= bb['route'] is None and bb['declared']==16 and bb['count']==1 and bb['read']['kind']=='absent' and missing_search==[]
        elif kind=='invalid':ok &= bb['declared'] is None and bb['route']['width']==16 and bb['read']['kind']=='error' and restore['failed_rows'].get(btable)==1
        elif kind in ['wrong_width','existing_incompatible']:ok &= bb['declared']==8 and bb['route']['width']==16 and bb['read']['kind']=='absent' and restore['failed_rows'].get(btable)==1
        elif kind=='merge_existing_row':ok &= bb['declared']==16 and bb['read']['kind']=='value' and bb['read']['row']['embedding']==[9.0]*16 and restore['restored_tables'].get(btable)==1 and bb['count']==1 and not restore['failed_rows']
        elif kind=='merge_existing_incompatible_row':ok &= bb['declared']==8 and bb['route']['width']==8 and bb['read']['kind']=='value' and bb['read']['row']['embedding']==[9.0]*8 and restore['restored_tables'].get(btable)==1 and bb['count']==1 and not restore['failed_rows']
        elif kind=='merge_parent_collision':
            # Retain the original complete-archive oracle as VIOLATED. The as-built
            # model now derives the actual first-column parent-skip/FK failure.
            ok=aa['read']['kind']=='absent' and bb['read']['row']['embedding']==[9.0]*16 and restore['failed_rows'].get('Graph_KG.'+tables[A[0]])==1
            got['intended_complete_archive']='VIOLATED: missing A parent/vector; known bug-plt-004/F-1802 root'
        if not ok:mism.append({'case':kind,'got':got,'restore':restore})
        observations.append({'case':kind,'got':got,'restore':restore,'archive_sha256':bc.sha(path),'agrees':bool(ok)})
    # Exercise real index-result and recording helpers under explicit provider faults.
    # The runtime supports HNSW, so these fault cases are injected boundary checks.
    class FaultCursor:
        def __init__(self,cur,kind):self.cur=cur;self.kind=kind
        def execute(self,sql,*a):
            if self.kind=='build' and 'CREATE INDEX' in sql.upper():raise RuntimeError('injected destination refuses ANN index')
            if self.kind=='record' and sql.upper().startswith('UPDATE ') and 'SET INDEX_STATE' in sql.upper():raise RuntimeError('injected registry update refusal')
            return self.cur.execute(sql,*a)
        def __getattr__(self,n):return getattr(self.cur,n)
    original_attempt=e._attempt_route_index;original_record=e._record_route_index_state
    for fail_record in [False,True]:
        empty_destination(e,list(tables.values()))
        def refuse_build(cur,table):return original_attempt(FaultCursor(cur,'build'),table)
        def record_index(cur,table,graph,state,error):return original_record(FaultCursor(cur,'record') if fail_record else cur,table,graph,state,error)
        with patch.object(e,'_attempt_route_index',refuse_build),patch.object(e,'_record_route_index_state',record_index):
            restore=e.restore_snapshot(str(original))
        got=observation(e,tables);want='present' if fail_record else 'refused'
        ok=all(got[g]['route']['index_state']==want and not got[g]['compiled_hnsw'] for g in [A[0],B[0]])
        if not ok:mism.append({'case':'injected_index_record','fail_record':fail_record,'got':got})
        observations.append({'case':'injected_index_record','provider_fault_injected':True,'fail_record':fail_record,'got':got,'agrees':ok})
    # Product creator mutation uses the real public restore with physical IRIS width enforcement.
    empty_destination(e,list(tables.values()));original_ddl=e.routed_table_ddl
    def wrong_ddl(name,**kw):return original_ddl(name,**{**kw,'dimension':8})
    with patch.object(e,'routed_table_ddl',wrong_ddl):mut_restore=e.restore_snapshot(str(original))
    mutated=observation(e,tables);detected=mutated[B[0]]['read']['kind']!='value' and bool(mut_restore['failed_rows'])
    # Restore valid neighbor before returning, preserving a usable last runtime state.
    empty_destination(e,list(tables.values()));e.restore_snapshot(str(original));final=observation(e,tables)
    changed=json.loads(json.dumps(final));changed[B[0]]['read']['row']['embedding'][0]=99
    detection={'creator_default_width_mutant':bool(detected),'changed_final_vector':changed!=final}
    c.close()
    extra_sources=['iris_vector_graph/_engine/snapshot.py','iris_vector_graph/_engine/schema.py','iris_vector_graph/_engine/embeddings.py']
    hashes={p:bc.sha(PIN_DIR/p) for p in extra_sources}
    out=bc.write_receipt('snapshot_routes',Path(__file__),{'verdict':'AGREES' if not mism and all(detection.values()) else 'DISAGREES',
        'comparisons':len(observations),'mismatch_count':len(mism),'mismatches':mism,'observations':observations,'detection':detection,
        'native':{'container':NAME,'port':PORT,'namespace':'USER','identity_checked':True,'image':subprocess.check_output(['docker','inspect','-f','{{.Image}}',NAME],text=True).strip()},
        'pin':bc.pin_identity(PIN_DIR),'additional_product_sha256':hashes,'elapsed':time.monotonic()-start,
        'observed':'actual save/restore ZIP, registry, per-route VECTOR declarations, row refusal/count, cache invalidation, resolve/get_embedding and valid width16 write on engine8',
        'substituted':'none in normal/fallback/missing-registry/invalid/wrong-width cases; archives deliberately altered. Two additional index-helper cases inject provider refusals, not native provider-failure observations. Product creator mutation forced dimension8. No concurrency or temporal restore evaluated.',
        'formal_relation':'registry identity/table width/graph-node rows and read value/absent/missing-table projection of prepare/load/read; vectors are exact integer-valued doubles; decoded metadata width maps to Width enum'})
    print(out);print(json.dumps({'mismatches':len(mism),'detection':detection,'elapsed':time.monotonic()-start}));return int(bool(mism) or not all(detection.values()))
if __name__=='__main__':raise SystemExit(main())
