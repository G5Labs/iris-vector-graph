"""Source-frozen bulk B1/B2 through actual IRIS writers and typed readers."""
import importlib.util,json,logging,sys,time
from pathlib import Path
from unittest.mock import patch
g5=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('snapshot_binding',g5/'Verus_verification/models/snapshot_routes/binding.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
from iris_vector_graph import schema
from iris_vector_graph.engine import IRISGraphEngine
start=time.monotonic();observations=[];errors=[]
def subset(row,props,labels):
    return row is not None and all(row.get(k)==v for k,v in props.items()) and set(row['labels'])==set(labels)
for mode in ['default_loader','default_sql','named_sql']:
    conn=b.connect();e=IRISGraphEngine(conn,embedding_dimension=8);e.erase_all()
    # initialize_schema/caller detection is explicitly permitted to populate capabilities.
    if mode!='default_sql':caps=e.capabilities
    known=bool(e._known_capabilities.objectscript_deployed)
    graph='bulk_named' if mode=='named_sql' else ''
    for ident,props,labels in [('a',{'name':'old','keep':'k'},['Old']),('o',{'a':1,'old':'old'},[]),('x',{'a':1},[])]:
        e.create_node(ident,properties=props,labels=labels,graph=graph)
    e.create_node('o',properties={'a':9},graph='other')
    cur=conn.cursor();cur.execute("DELETE FROM Graph_KG.nodes WHERE graph_id=? AND node_id=?",[graph,'o']);conn.commit();cur.close()
    payload=[{'id':'a','labels':['New'],'properties':{'name':'new','flag':True}},
        {'id':'b','labels':['L'],'properties':{'n':5}},
        {'id':'o','properties':{'a':2}},{'id':'x','properties':{'a':2,'c':3}},
        {'id':'f','properties':{'a':2}},{'id':'o','properties':{'a':3,'d':4}}]
    if graph:payload=[{**r,'graph':graph} for r in payload]
    calls=[];original=schema._call_classmethod_large
    def traced(*a,**kw):calls.append({'class':a[1],'method':a[2]});return original(*a,**kw)
    with patch.object(schema,'_call_classmethod_large',traced):ids=e.bulk_create_nodes(payload,disable_indexes=False)
    rows={n:e.get_node(n,graph=graph) for n in ['a','b','o','x','f']};other=e.get_node('o',graph='other')
    ok=ids==['a','b','o','x','f','o'] and subset(rows['a'],{'name':'old','keep':'k','flag':True},['Old','New'])
    ok &= subset(rows['b'],{'n':5},['L']) and type(rows['b']['n']) is int
    ok &= rows['o'].get('a')==2 and rows['o'].get('d')==4 and 'old' not in rows['o']
    ok &= rows['x'].get('a')==1 and rows['x'].get('c')==3 and rows['f'].get('a')==2 and other.get('a')==9
    loader_calls=[c for c in calls if c['method']=='BulkIngestNodesSQL']
    ok &= bool(loader_calls)==(mode=='default_loader')
    observations.append({'mode':mode,'known_deployed_before_call':known,'calls':calls,'ids':ids,'rows':rows,'other_graph':other,'agrees':bool(ok)})
    if not ok:errors.append(mode)
    conn.close()
out={'verdict':'AGREES' if not errors else 'DISAGREES','observations':observations,'mismatches':errors,'elapsed':time.monotonic()-start,
    'native':{'container':b.NAME,'port':b.PORT,'identity_checked':True},'source_pin':b.bc.pin_identity(b.PIN_DIR),
    'instrumentation':'_call_classmethod_large wrapper logs calls and invokes unchanged original; public payload, actual SQL/native writes and final reader. Orphan parent deleted by SQL as in product e2e fixture.',
    'scope':'six-node batch, existing/orphan/repeat, labels, typed child values and other-graph frame across actual default-loader/default-SQL/named-SQL paths; no concurrency or full provider proof',
    'probe_sha256':b.bc.sha(Path(__file__))}
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'verdict':out['verdict'],'mismatches':errors,'elapsed':out['elapsed'],'loader_calls':[o['calls'] for o in observations]}));raise SystemExit(bool(errors))
