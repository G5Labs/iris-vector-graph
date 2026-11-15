"""Actual node writers -> SQL metadata producer -> parser -> public CALL consumer.
SQLite's SQL/transaction adapter is explicitly inherited, not IRIS/native evidence.
"""
from __future__ import annotations
import copy,importlib.util,inspect,itertools,json,logging,socket,sys,textwrap,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN=bc.import_pin()
# Reuse only the explicit SQLite dialect/transaction adapter. Stamp its entire
# source; invoking either package's main is forbidden by the import guard.
HELPER=HERE.parent/'bulk_children'/'binding.py'
spec=importlib.util.spec_from_file_location('procedure_sql_adapter',HELPER)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph._engine import query as qm
from iris_vector_graph.cypher import row_where as rw

logging.disable(logging.CRITICAL)

WORLDS=[[],[('', 'a',['A'])],[('', 'a',['B'])],
    [('', 'a',['A']),('', 'b',['B']),('other','c',['A'])],
    [('other','a',['C']),('', 'b',['A']),('', 'c',['A'])]]
FILTERS={'all':'','eqA':"{a} = 'A'",'eqC':"{a} = 'C'",'eqNull':'{a} = null',
    'neNull':'{a} <> null','neBool':'{a} <> true','isNull':'{a} IS NULL',
    'unsupported':"{a} STARTS WITH 'A'",'missing':'{a} = $wanted'}

def expect(labels,alias,kind,ret,order,skip,limit,*,source='label',clause=False):
    """Twin of provider/consume/cut over A/B/C text codes; no product helper called."""
    rows=sorted(set(labels))
    if clause:return {'refused':True}
    if rows and kind!='all' and (source!='label' or kind in ('unsupported','missing')):return {'refused':True}
    def keep(x):
        if kind in ('all','neBool'):return True
        if kind=='eqA':return x=='A'
        if kind=='eqC':return x=='C'
        return False
    rows=[x for x in rows if keep(x)]
    if ret and alias!='label' and source!='label' and rows:return {'refused':True}
    column=alias if ret else 'label'
    if order and order!=column:return {'refused':True}
    rows=rows[skip:] if limit is None else rows[skip:skip+limit]
    return {'columns':[column],'rows':[[x] for x in rows],'error':None}

def observe(e,text):
    try:
        r=e.execute_cypher(text,{},raise_on_error=True)
        return {'columns':r.columns,'rows':r.rows,'error':r.error}
    except ValueError as ex:return {'refused':True,'message':str(ex)}

def equal(got,want):return all(got.get(k)==v for k,v in want.items())

def make(world,writer):
    c=adapter.Connection();e=IRISGraphEngine.__new__(IRISGraphEngine)
    e.conn=c;e._schema_prefix='Graph_KG';e._nodes_has_graph_id=e._children_have_graph_id=True
    e._capabilities=SimpleNamespace(objectscript_deployed=False);e._last_probe_ok=time.monotonic()
    if writer=='single':
        for g,n,labels in world:assert e.create_node(n,labels=labels,graph=g)
    else:
        nodes=[{'id':n,'graph':g,'labels':labels} for g,n,labels in world]
        if nodes:e.bulk_create_nodes(nodes)
    actual=[r[0] for r in c.db.execute('SELECT label FROM Graph_KG.rdf_labels')]
    assert sorted(actual)==sorted(l for g,n,ls in world for l in ls)
    return c,e,actual

def compare(*,mutant=False,changed=False):
    mism=[];samples=[];count=0
    for wi,world in enumerate(WORLDS):
        for writer in ('single','bulk'):
            c,e,labels=make(world,writer)
            try:
                for alias,kind,ret,order,skip,limit in itertools.product(('label','l'),FILTERS,(False,True),(None,'label','l'),(0,1),(None,0,1)):
                    q='CALL db.labels() YIELD label'+(' AS l' if alias=='l' else '')
                    if FILTERS[kind]:q+=' WHERE '+FILTERS[kind].format(a=alias)
                    if ret:q+=' RETURN '+alias
                    if order:q+=' ORDER BY '+order
                    if skip:q+=' SKIP '+str(skip)
                    if limit is not None:q+=' LIMIT '+str(limit)
                    want=expect(labels,alias,kind,ret,order,skip,limit)
                    if mutant:
                        with patch.object(qm,'where_rows',lambda result,*a,**k:result):got=observe(e,q)
                    else:got=observe(e,q)
                    if changed and wi==1 and kind=='all' and ret and order is None and skip==0 and limit is None:got={**got,'columns':['wrong']}
                    count+=1
                    if not equal(got,want):mism.append({'world':wi,'writer':writer,'query':q,'want':want,'got':got})
                    if writer=='single' and alias=='l' and kind in ('all','unsupported','missing') and skip==0 and limit is None and order in (None,'l'):
                        samples.append({'world':wi,'query':q,'observation':got,'expected':want})
                for tail in (" WITH l WHERE l = 'B' RETURN l", " WITH l AS changed RETURN changed"):
                    q='CALL db.labels() YIELD label AS l'+tail
                    want=({'refused':True} if ' AS changed' in tail else {'columns':['l'],'rows':[['B']] if 'B' in labels else [],'error':None})
                    got=observe(e,q);count+=1
                    if not equal(got,want):mism.append({'query':q,'world':wi,'got':got,'want':want})
                for src,wrong_alias,clause in itertools.product(('label','absent'),('label','l'),(False,True)):
                    q=f'CALL db.labels() YIELD {src} AS {wrong_alias}'+(' MATCH (n:X)' if clause else '')+' RETURN '+wrong_alias
                    want=expect(labels,wrong_alias,'all',True,None,0,None,source=src,clause=clause)
                    got=observe(e,q);count+=1
                    if not equal(got,want):mism.append({'query':q,'world':wi,'got':got,'want':want})
            finally:c.db.close()
    return count,mism,samples

def main():
    start=time.monotonic()
    # Prohibit incidental connection attempts, even via import-time helpers.
    with patch.object(socket.socket,'connect',side_effect=AssertionError('binding forbids network')) as guard:
        n,mism,samples=compare();_,mut,_=compare(mutant=True);_,changed,_=compare(changed=True)
        # Actual method-copy producer mutation: DISTINCT must be meaningful.
        scope=dict(vars(sys.modules[IRISGraphEngine.__module__]));source=textwrap.dedent(inspect.getsource(IRISGraphEngine._proc_db_labels))
        assert source.count('SELECT DISTINCT label')==1
        exec(source.replace('SELECT DISTINCT label','SELECT label'),scope)
        c,e,labels=make(WORLDS[3],'single')
        try:
            with patch.object(IRISGraphEngine,'_proc_db_labels',scope['_proc_db_labels']):got=observe(e,'CALL db.labels() YIELD label RETURN label')
            producer=not equal(got,expect(labels,'label','all',True,None,0,None))
        finally:c.db.close()
    detection={'actual_where_consumer_removed':bool(mut),'actual_distinct_producer_removed':producer,'changed_column_oracle_rejected':bool(changed)}
    files=['iris_vector_graph/_engine/query.py','iris_vector_graph/engine.py','iris_vector_graph/cypher/parser.py','iris_vector_graph/cypher/row_where.py','iris_vector_graph/_engine/nodes_edges.py','iris_vector_graph/result.py']
    body={'verdict':'AGREES' if not mism and all(detection.values()) else 'DISAGREES','comparisons':n,'mismatch_count':len(mism),'mismatches':mism[:10],'detection':detection,'samples':samples,
        'pin':bc.pin_identity(PIN),'source_inputs':{f:bc.sha(PIN/f) for f in files},'blocked_network_calls':guard.call_count,'wall_s':time.monotonic()-start,
        'scope':'A/B/C labels via real single/bulk Python writers, real SQLite DISTINCT producer/parser/dispatch/where/projection/tail/public reader. Explicit transaction and SQL dialect adapters; no native IRIS, network, arbitrary collation, multi-column or general expression proof.'}
    out=bc.write_receipt('procedure_results',Path(__file__),body);d=json.loads(out.read_text());d['inputs'][str(HELPER.relative_to(bc.REPO))]=bc.sha(HELPER)
    for f in files:d['inputs'][f]=bc.sha(PIN/f)
    out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(f"procedure_results: {d['verdict']}; {n} comparisons; {out}")
    if mism:print(json.dumps(mism[:4],indent=2))
    return int(d['verdict']!='AGREES')
if __name__=='__main__':raise SystemExit(main())
