"""Read-only ordinary handler/ASGI health survey over exported pin. No live target."""
from __future__ import annotations
import hashlib,importlib,json,os,socket,sqlite3,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

NETWORK_GUARD=patch.object(socket.socket,'connect',side_effect=AssertionError('survey prohibits network connections'))
NETWORK_CONNECT=NETWORK_GUARD.start()
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
sys.path.insert(0,str(PIN))
os.environ['BOLT_ENABLED']='0'
os.environ.pop('IVG_API_KEY',None)
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph.result import IVGResult
from iris_vector_graph.cypher.parser import parse_query
from iris_vector_graph._engine import query as qm

def query_probe():
    c=sqlite3.connect(':memory:');c.execute("ATTACH DATABASE ':memory:' AS Graph_KG")
    c.execute('CREATE TABLE Graph_KG.rdf_labels(graph_id TEXT,s TEXT,label TEXT)')
    c.executemany('INSERT INTO Graph_KG.rdf_labels VALUES(?,?,?)',[('','a','A'),('','b','B'),('','c','A')])
    e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=c;e._schema_prefix='Graph_KG'
    e._last_probe_ok=time.monotonic()  # represent a recently checked connection; do not request IRIS reconnect.
    cases=[
        ('P1-A',"CALL db.labels() YIELD label AS l WHERE l = $wanted RETURN l",{'wanted':'A'}),
        ('P1-C',"CALL db.labels() YIELD label AS l WHERE l = $wanted RETURN l",{'wanted':'C'}),
        ('P1-unfiltered',"CALL db.labels() YIELD label RETURN label",{}),
        ('P2-with',"CALL db.labels() YIELD label WITH label WHERE label = 'B' RETURN label",{}),
        ('P2-refuse-match',"CALL db.labels() YIELD label MATCH (n:X) RETURN label",{}),
        ('P2-refuse-starts',"CALL db.labels() YIELD label WHERE label STARTS WITH 'A' RETURN label",{}),
        ('P2-null',"CALL db.labels() YIELD label WHERE label = null RETURN label",{}),
        ('alias-standalone-discovery',"CALL db.labels() YIELD label AS l WHERE l = 'A'",{}),
        ('alias-standalone-return-neighbor',"CALL db.labels() YIELD label AS l WHERE l = 'A' RETURN l",{}),
        ('alias-standalone-order-discovery',"CALL db.labels() YIELD label AS l ORDER BY l",{}),
    ]
    observations=[]
    for name,text,params in cases:
        try:
            r=e._execute_parsed(parse_query(text),params)
            observations.append({'name':name,'query':text,'params':params,'columns':r.columns,'rows':r.rows,'error':r.error})
        except Exception as exc:observations.append({'name':name,'query':text,'params':params,'raised':type(exc).__name__,'message':str(exc)})
    # Deciding-consumer control: remove WHERE application while the real label producer still runs.
    with patch.object(qm,'where_rows',lambda result,*a,**k:result):
        r=e._execute_parsed(parse_query(cases[0][1]),cases[0][2])
    observations.append({'name':'where-consumer-control','columns':r.columns,'rows':r.rows,'detected':r.rows!=[['A']]})
    for index in [0,7,8,9]:
        name,text,params=cases[index]
        try:
            r=e.execute_cypher(text,params,raise_on_error=True)
            observations.append({'name':'public-entry-'+name,'columns':r.columns,'rows':r.rows,'error':r.error})
        except Exception as exc:observations.append({'name':'public-entry-'+name,'raised':type(exc).__name__,'message':str(exc)})
    c.close();return observations

class HealthCursor:
    def __init__(self,row=(1,),error=None):self.row=row;self.error=error;self.sql=[]
    def execute(self,sql,params=None):
        self.sql.append(sql)
        if self.error:raise self.error
    def fetchone(self):return self.row
    def close(self):pass

class HealthEngine:
    _schema_prefix='Graph_KG'
    def __init__(self,row=(1,),error=None):self.cursor=HealthCursor(row,error);self.conn=SimpleNamespace(cursor=lambda:self.cursor)
    def _iris_obj(self):return object()  # read_record is an explicit substitute, never native.

def http_probe():
    # api.main constructs a module-level app. Block its dependency before import so no connection is attempted.
    from iris_devtester.utils import dbapi_compat
    with patch.object(dbapi_compat,'get_connection',side_effect=RuntimeError('survey has no live connection')):
        main=importlib.import_module('api.main')
    ca=importlib.import_module('iris_vector_graph.cypher_api')
    from fastapi.testclient import TestClient
    out=[]
    for name,engine,record,isiris in [
        ('H2-select1',HealthEngine(),None,False),
        ('H2-wrong-select1',HealthEngine(row=(0,)),None,False),
        ('H2-failed-select1',HealthEngine(error=RuntimeError('unavailable')),None,False),
        ('H2-matching-record',HealthEngine(),'GRAPH_KG',True),
        ('H2-other-record',HealthEngine(),'OtherKG',True),
        ('H2-missing-record',HealthEngine(),None,True),
    ]:
        with patch.object(main,'is_iris_connection',return_value=isiris),patch.object(main,'read_record',return_value=record):
            r=TestClient(main.create_app(engine)).get('/health')
        out.append({'name':name,'status_code':r.status_code,'body':r.json(),'sql':engine.cursor.sql})
    for name,answer in [('H1-ok',IVGResult(columns=['c'],rows=[[2]])),('H1-folded-error',IVGResult(columns=[],rows=[],error='unavailable'))]:
        fake=SimpleNamespace(execute_cypher=lambda text,r=answer:r)
        with patch.object(ca,'_get_engine',return_value=fake):r=TestClient(ca.app).get('/health')
        out.append({'name':name,'status_code':r.status_code,'body':r.json()})
    with patch.object(ca,'_get_engine',side_effect=RuntimeError('unavailable')):
        r=TestClient(ca.app).get('/health')
    out.append({'name':'H1-no-engine','status_code':r.status_code,'body':r.json()})
    # Additional state-history contrast discovered from the source after the original freeze.
    recovered=HealthEngine()
    with patch.object(main,'get_engine',side_effect=[RuntimeError('unavailable'),recovered]) as maker:
        app=main.create_app();client=TestClient(app)
        a=client.get('/health');b=client.get('/health')
        out.append({'name':'startup-recovery-discovery-api-main','statuses':[a.status_code,b.status_code],'engine_factory_calls':maker.call_count})
    fake=SimpleNamespace(execute_cypher=lambda text:IVGResult(columns=['c'],rows=[[0]]))
    saved=ca._engine_cache;ca._engine_cache=None
    try:
        with patch.object(ca,'_make_engine',side_effect=[RuntimeError('unavailable'),fake]) as maker:
            client=TestClient(ca.app);a=client.get('/health');b=client.get('/health')
            out.append({'name':'startup-recovery-discovery-cypher-api','statuses':[a.status_code,b.status_code],'engine_factory_calls':maker.call_count})
    finally:ca._engine_cache=saved
    return out

def main():
    start=time.monotonic();p=Path(__file__).with_name('breadth-probe.json')
    repo=Path(__file__).resolve().parents[4]
    files=['iris_vector_graph/engine.py','iris_vector_graph/_engine/query.py','iris_vector_graph/cypher/row_where.py',
        'iris_vector_graph/cypher/parser.py','iris_vector_graph/cypher/translator.py','iris_vector_graph/cypher_api.py',
        'iris_vector_graph/schema_name.py','api/main.py']
    identities={}
    for path in files:
        blob=subprocess.check_output(['git','-C',str(repo),'rev-parse',f'3eaa79cf:{path}'],text=True).strip()
        exported=subprocess.check_output(['git','hash-object',str(PIN/path)],text=True).strip()
        current=subprocess.check_output(['git','hash-object',str(repo/path)],text=True).strip()
        identities[path]={'pin_blob':blob,'export_equal_pin':exported==blob,'current_equal_pin':current==blob,
            'sha256':hashlib.sha256((PIN/path).read_bytes()).hexdigest()}
    assert all(d['export_equal_pin'] and d['current_equal_pin'] for d in identities.values())
    result={'pin':'3eaa79cf77d3e0a879b2cced634cf2729d81499e','query':query_probe(),'http':http_probe(),
        'scope':'actual parser, SQLite-backed metadata producer, _execute_parsed handler consumer and ASGI routes; IRIS schema record and query-result provider are substituted; no security behavior tested, live connection, listener or container used',
        'source_identities':identities,'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'blocked_network_calls':NETWORK_CONNECT.call_count,'wall_s':round(time.monotonic()-start,3)}
    p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
