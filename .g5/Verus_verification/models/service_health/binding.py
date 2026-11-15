"""Real health/cache/app Python and in-process ASGI over named substituted providers.

No listener, authentication experiment, native target or database is used. A socket
guard is active before product imports; connection constructors are blocked/stubbed.
"""
from __future__ import annotations
import copy,decimal,fractions,hashlib,importlib,inspect,itertools,json,logging,os,socket,subprocess,sys,textwrap,time,types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

NETWORK=patch.object(socket.socket,'connect',side_effect=AssertionError('service_health forbids network connections'))
CONNECT=NETWORK.start()
logging.disable(logging.CRITICAL)
os.environ['BOLT_ENABLED']='0'
os.environ.pop('IVG_API_KEY',None)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN_DIR=bc.import_pin()
from iris_devtester.utils import dbapi_compat
with patch.object(dbapi_compat,'get_connection',side_effect=RuntimeError('source-only module import')):
    main_api=importlib.import_module('api.main')
cypher_api=importlib.import_module('iris_vector_graph.cypher_api')
from iris_vector_graph.result import IVGResult
from fastapi.testclient import TestClient
import iris,iris.dbapi

SCHEMA='Graph_KG'
REASONS={
    'startup':'the API started without the database',
    'select':'the database did not answer SELECT 1',
    'record_read':'the IVG Schema record could not be read',
    'record_missing':'the namespace has no IVG Schema record: setup has not finished; run initialize_schema()',
    'record_mismatch':'the namespace records another IVG Schema',
}

class Profile:
    def __init__(self,name,*,row=(1,),select_error=None,record=SCHEMA,record_error=None,marked_iris=True,
        query_error=None,result_error=None,count=3,access_error=None,close_error=None,expected=SCHEMA):
        self.name=name;self.row=row;self.select_error=select_error;self.record=record;self.record_error=record_error
        self.marked_iris=marked_iris;self.query_error=query_error;self.result_error=result_error;self.count=count
        self.access_error=access_error;self.close_error=close_error;self.expected=expected
        self.selects=0;self.records=0;self.queries=0;self.closes=0;self.query_locks=[]
        self.sql=[];self.cypher=[]

class Cursor:
    def __init__(self,p):self.p=p
    def execute(self,sql,params=None):
        self.p.sql.append(sql);self.p.selects+=1
        assert sql=='SELECT 1'
        if self.p.select_error:raise self.p.select_error
    def fetchone(self):return self.p.row
    def close(self):pass

class Connection:
    def __init__(self,p):self.p=p
    def cursor(self):return Cursor(self.p)
    def close(self):
        self.p.closes+=1
        if self.p.close_error:raise self.p.close_error

class NativeRecord:
    def __init__(self,p):self.p=p
    def get(self,*args):
        self.p.records+=1
        if self.p.record_error:raise self.p.record_error
        return self.p.record

class Engine:
    def __init__(self,p,connection=None):self.p=p;self._schema_prefix=p.expected;self.connection=connection or Connection(p)
    @property
    def conn(self):
        if self.p.access_error:raise self.p.access_error
        return self.connection
    def _iris_obj(self):return NativeRecord(self.p)
    def execute_cypher(self,text,parameters=None):
        self.p.queries+=1;self.p.cypher.append(text);self.p.query_locks.append(cypher_api._engine_lock._is_owned())
        assert text=='MATCH (n) RETURN count(n) AS c'
        if self.p.query_error:raise self.p.query_error
        return IVGResult(columns=['c'],rows=[[self.p.count]],error=self.p.result_error)

class Factory:
    def __init__(self,*outcomes):self.outcomes=list(outcomes);self.calls=0;self.locks=[]
    def __call__(self):
        self.calls+=1;self.locks.append(cypher_api._engine_lock._is_owned())
        result=self.outcomes.pop(0)
        if isinstance(result,Exception):raise result
        return result

def status_body(response):return {'code':response.status_code,'body':response.json()}

def expected_main(p=None,absent=False):
    # Independent inspected twin of main_request/problem, preserving the first returned scalar.
    reason=None
    if absent:reason='startup'
    elif p.access_error or p.select_error or not p.row or p.row[0]!=1:reason='select'
    elif p.marked_iris:
        if p.record_error:reason='record_read'
        elif p.record is None or str(p.record)=='':reason='record_missing'
        elif str(p.record).upper()!=p.expected.upper():reason='record_mismatch'
    if reason:
        return {'code':503,'body':{'status':'unhealthy','database':'unavailable','graphql':'available','reason':REASONS[reason]}}
    return {'code':200,'body':{'status':'healthy','database':'connected','graphql':'available'}}

def expected_cypher(p=None,construction_error=False):
    okay=not construction_error and p is not None and not p.query_error and not p.result_error
    return {'code':200 if okay else 503,'body':{'status':'ok' if okay else 'unavailable'}}

def main_app(p=None,factory=None):
    if factory is None:return main_api.create_app(engine=Engine(p))
    with patch.object(main_api,'get_engine',factory):return main_api.create_app()

def request_main(app):
    with patch.object(main_api,'is_iris_connection',lambda conn:conn.p.marked_iris):
        return status_body(TestClient(app).get('/health'))

def clear_cache():
    # Fixture isolation, not a product transition. Reset transitions are exercised explicitly below.
    with cypher_api._engine_lock:cypher_api._engine_cache=None

def request_cypher(factory):
    with patch.object(cypher_api,'_make_engine',factory):return status_body(TestClient(cypher_api.app).get('/health'))

def request_other_query(factory):
    with patch.object(cypher_api,'_make_engine',factory):
        response=TestClient(cypher_api.app).post('/api/cypher',json={'query':'MATCH (n) RETURN count(n) AS c'})
    body=response.json()
    return {'code':response.status_code,'row_count':body.get('rowCount') if response.status_code==200 else None}

def main():
    started=time.monotonic();observations=[];mismatches=[];checks=0
    def compare(name,got,want,detail=None):
        nonlocal checks
        checks+=1;row={'name':name,'got':got,'expected':want}
        if detail is not None:row['detail']=detail
        observations.append(row)
        if got!=want:mismatches.append(row)

    profiles=[
        Profile('one'),Profile('standin-no-record',marked_iris=False,record=None),
        Profile('standin-record-unreadable',marked_iris=False,record_error=PermissionError('record unavailable')),
        Profile('wrong-zero',row=(0,)),Profile('no-row',row=None),Profile('empty-row',row=()),
        Profile('text-one',row=('1',)),Profile('null-first',row=(None,)),Profile('boolean-one',row=(True,)),
        Profile('boolean-zero',row=(False,)),Profile('float-one',row=(1.0,)),Profile('float-half',row=(0.5,)),
        Profile('decimal-one',row=(decimal.Decimal('1.0'),)),Profile('fraction-one',row=(fractions.Fraction(2,2),)),
        Profile('nonfinite-nan',row=(float('nan'),)),Profile('nonfinite-inf',row=(float('inf'),)),
        Profile('select-connection',select_error=ConnectionError('probe unavailable')),
        Profile('select-permission',select_error=PermissionError('probe unavailable')),
        Profile('record-missing',record=None),Profile('record-empty',record=''),Profile('record-other',record='OtherKG'),
        Profile('record-case',record='gRAPH_kg'),Profile('record-number',record=7),
        Profile('record-permission',record_error=PermissionError('record unavailable')),
        Profile('record-connection',record_error=ConnectionError('record unavailable')),
    ]
    for p in profiles:
        app=main_app(p);got=request_main(app)
        compare('main-'+p.name,got,expected_main(p),{'selects':p.selects,'records':p.records,'sql':p.sql})
        want_record=int(not p.access_error and not p.select_error and bool(p.row) and p.row[0]==1 and p.marked_iris)
        compare('main-provider-order-'+p.name,{'selects':p.selects,'records':p.records},{'selects':1,'records':want_record})

    # Startup exception/first-access error are captured only on the automatic branch.
    for error in [ConnectionError('factory unavailable'),PermissionError('factory unavailable')]:
        good=Engine(Profile('later-good'));f=Factory(error,good);app=main_app(factory=f)
        got=[request_main(app),request_main(app)]
        compare('sticky-'+type(error).__name__,{'replies':got,'calls':f.calls},
            {'replies':[expected_main(absent=True)]*2,'calls':1})
    access=Profile('first-access-error',access_error=PermissionError('first access unavailable'))
    f=Factory(Engine(access));app=main_app(factory=f)
    compare('automatic-first-access-caught',{'reply':request_main(app),'calls':f.calls},{'reply':expected_main(absent=True),'calls':1})
    raised=None
    try:main_app(access)
    except Exception as exc:raised=type(exc).__name__
    compare('injected-first-access-not-caught',raised,'PermissionError')
    p=Profile('sample-recovery',select_error=ConnectionError('temporarily unavailable'));app=main_app(p)
    bad=request_main(app);want_bad=expected_main(p);p.select_error=None;good=request_main(app)
    compare('bound-main-recovery',[bad,good],[want_bad,expected_main(p)])

    # Lazy construction retry and cached query errors are different histories.
    clear_cache();p=Profile('lazy-recovery');f=Factory(ConnectionError('factory unavailable'),Engine(p))
    replies=[request_cypher(f),request_cypher(f)]
    compare('lazy-factory-recovery',{'replies':replies,'calls':f.calls,'cached':cypher_api._engine_cache.p.name},
        {'replies':[expected_cypher(construction_error=True),expected_cypher(p)],'calls':2,'cached':p.name})
    compare('lazy-factory-lock',f.locks,[True,True])
    for kind,error in [('raised-connection',ConnectionError('query unavailable')),('raised-permission',PermissionError('query unavailable')),
        ('folded','query unavailable'),('empty-folded',''),('clean',None)]:
        clear_cache();p=Profile(kind,query_error=error if isinstance(error,Exception) else None,
            result_error=None if isinstance(error,Exception) else error,count=0)
        e=Engine(p);f=Factory(e);got=request_cypher(f)
        compare('cypher-'+kind,got,expected_cypher(p))
        compare('cached-'+kind,{'same_engine':cypher_api._engine_cache is e,'calls':f.calls,'queries':p.queries},
            {'same_engine':True,'calls':1,'queries':1})
        compare('query-lock-'+kind,p.query_locks,[True])
    clear_cache();p=Profile('cached-recovers',query_error=ConnectionError('temporarily unavailable'));e=Engine(p);f=Factory(e)
    a=request_cypher(f);want_a=expected_cypher(p);p.query_error=None;b=request_cypher(f)
    compare('cached-query-recovers',{'replies':[a,b],'calls':f.calls,'same_engine':cypher_api._engine_cache is e},
        {'replies':[want_a,expected_cypher(p)],'calls':1,'same_engine':True})
    for fails in [False,True]:
        clear_cache();old=Profile('old',query_error=ConnectionError('old query unavailable'),
            close_error=ConnectionError('close unavailable') if fails else None)
        new=Profile('replacement');f=Factory(Engine(old),Engine(new));a=request_cypher(f)
        with cypher_api._engine_lock:cypher_api._reset_engine()
        cleared=cypher_api._engine_cache is None;b=request_cypher(f)
        compare('reset-'+str(fails),{'replies':[a,b],'calls':f.calls,'close_attempts':old.closes,'cleared':cleared},
            {'replies':[expected_cypher(old),expected_cypher(new)],'calls':2,'close_attempts':1,'cleared':True})
    clear_cache()
    with cypher_api._engine_lock:cypher_api._reset_engine()
    compare('reset-empty-cache',cypher_api._engine_cache,None)

    # The actual competing writer/caller, not only a direct reset fixture.
    for error in [ConnectionError('query unavailable'),PermissionError('query unavailable')]:
        clear_cache();old=Profile('other-query-old',query_error=error,close_error=ConnectionError('close unavailable'))
        new=Profile('other-query-new');f=Factory(Engine(old),Engine(new));request_cypher(f)
        query_result=request_other_query(f);next_health=request_cypher(f)
        compare('other-query-replaces-'+type(error).__name__,
            {'query':query_result,'health':next_health,'calls':f.calls,'closed':old.closes,'cached':cypher_api._engine_cache.p.name},
            {'query':{'code':200,'row_count':1},'health':expected_cypher(new),'calls':2,'closed':1,'cached':new.name})
    clear_cache();old=Profile('folded-other-query',result_error='query unavailable');new=Profile('unused-new')
    f=Factory(Engine(old),Engine(new));request_cypher(f);query_result=request_other_query(f);next_health=request_cypher(f)
    compare('folded-other-query-does-not-reset',
        {'query':query_result,'health':next_health,'calls':f.calls,'closed':old.closes,'cached':cypher_api._engine_cache.p.name},
        {'query':{'code':400,'row_count':None},'health':expected_cypher(old),'calls':1,'closed':0,'cached':old.name})
    clear_cache();old=Profile('first-exception',query_error=ConnectionError('first unavailable'))
    new=Profile('second-exception',query_error=ConnectionError('second unavailable'));f=Factory(Engine(old),Engine(new))
    request_cypher(f);query_result=request_other_query(f);next_health=request_cypher(f)
    compare('second-other-query-exception-stops',
        {'query':query_result,'health':next_health,'calls':f.calls,'closed':old.closes,'new_queries':new.queries},
        {'query':{'code':400,'row_count':None},'health':expected_cypher(new),'calls':2,'closed':1,'new_queries':2})

    # Execute actual connection-factory bodies over a named connector and constructor port.
    factory_ports=[]
    profile=Profile('factory-body',marked_iris=False);conn=Connection(profile)
    def connector(*a,**kw):factory_ports.append('connector');return conn
    def constructor(c):factory_ports.append('engine-constructor');return Engine(profile,c)
    with patch.dict(os.environ,{'IRIS_HOST':'source-only.invalid','IRIS_PORT':'9','IRIS_NAMESPACE':'FIXTURE',
        'IRIS_USER':'fixture','IRIS_USERNAME':'fixture','IRIS_PASSWORD':'fixture'}):
        with patch.object(main_api,'iris_connect',connector),patch.object(main_api,'IRISGraphEngine',constructor):
            made=main_api.get_engine()
        compare('main-factory-body',made.connection is conn,True)
        with patch.object(iris.dbapi,'connect',connector),patch.object(cypher_api,'IRISGraphEngine',constructor):
            made=cypher_api._make_engine()
        compare('cypher-factory-host-body',made.connection is conn,True)
    compare('factory-port-order',factory_ports,['connector','engine-constructor']*2)

    # Mutants run valid actual Python bodies through the same ASGI request path.
    p=Profile('case-neighbor',record='gRAPH_kg');app=main_app(p)
    with patch.object(main_api,'same_schema',lambda a,b:a==b):bad=request_main(app)
    detection={'schema-case-mutation':bad!=expected_main(p)}
    p=Profile('mismatch-neighbor',record='OtherKG');src=textwrap.dedent(inspect.getsource(main_api.database_problem));scope=dict(vars(main_api))
    assert src.count('if not same_schema(recorded, schema):')==1
    exec(src.replace('if not same_schema(recorded, schema):','if False:'),scope)
    app=main_app(p)
    with patch.object(main_api,'database_problem',scope['database_problem']):bad=request_main(app)
    detection['record-mismatch-mutation']=bad!=expected_main(p)
    clear_cache();p=Profile('folded-mutant',result_error='query unavailable');f=Factory(Engine(p))
    src=textwrap.dedent(inspect.getsource(cypher_api.health));src=src[src.index('def health'):];scope=dict(vars(cypher_api))
    assert src.count('if error:')==1;exec(src.replace('if error:','if False:'),scope)
    route=next(r for r in cypher_api.app.routes if getattr(r,'path',None)=='/health')
    with patch.object(route.dependant,'call',scope['health']):bad=request_cypher(f)
    detection['folded-error-mutation']=bad!=expected_cypher(p)
    clear_cache();old=Profile('bad-old',query_error=ConnectionError('old query unavailable'),close_error=ConnectionError('close unavailable'))
    new=Profile('good-new');f=Factory(Engine(old),Engine(new));request_cypher(f)
    src=textwrap.dedent(inspect.getsource(cypher_api._reset_engine));scope=dict(vars(cypher_api))
    assert src.count('_engine_cache = None')==1;exec(src.replace('_engine_cache = None','_engine_cache = _engine_cache'),scope)
    # The writer must operate on the actual module's cache so the NEXT request sees its effect.
    mutant_reset=types.FunctionType(scope['_reset_engine'].__code__,vars(cypher_api),'_reset_engine')
    with patch.object(cypher_api,'_reset_engine',mutant_reset):
        with cypher_api._engine_lock:cypher_api._reset_engine()
    bad=request_cypher(f)
    detection['reset-cache-mutation']=bad!=expected_cypher(new) and f.calls==1
    clear_cache();old=Profile('other-mutant-old',query_error=ConnectionError('unavailable'));new=Profile('other-mutant-new')
    f=Factory(Engine(old),Engine(new));request_cypher(f)
    src=textwrap.dedent(inspect.getsource(cypher_api._run_cypher));scope=dict(vars(cypher_api))
    assert src.count('if attempt == 0:')==1;exec(src.replace('if attempt == 0:','if False:'),scope)
    with patch.object(cypher_api,'_run_cypher',scope['_run_cypher']):bad=request_other_query(f)
    detection['actual-other-query-retry-removed']=bad!={'code':200,'row_count':1} and request_cypher(f)!=expected_cypher(new)
    clear_cache();p=Profile('observation-control');f=Factory(Engine(p));good=request_cypher(f)
    changed=copy.deepcopy(good);changed['code']=503
    detection['changed-http-status']=good==expected_cypher(p) and changed!=expected_cypher(p)
    clear_cache()
    compare('no-network-connects',CONNECT.call_count,0)

    ident=bc.pin_identity(PIN_DIR);extra=['api/main.py','iris_vector_graph/cypher_api.py','iris_vector_graph/schema_name.py','iris_vector_graph/result.py']
    for path in extra:
        blob=subprocess.check_output(['git','-C',str(bc.REPO),'rev-parse',f'{bc.PIN}:{path}'],text=True).strip()
        have=subprocess.check_output(['git','hash-object',str(PIN_DIR/path)],text=True).strip()
        ident['files_equal_pin_blobs'][path]=blob==have;ident['all_equal'] &= blob==have
    verdict='AGREES' if not mismatches and all(detection.values()) and ident['all_equal'] else 'DISAGREES'
    out=bc.write_receipt('service_health',Path(__file__),{'verdict':verdict,'comparisons':checks,'mismatch_count':len(mismatches),
        'mismatches':mismatches,'observations':observations,'detection':detection,'pin':ident,'wall_s':round(time.monotonic()-started,3),
        'network_connect_calls':CONNECT.call_count,
        'real':'api.main.create_app/get_engine/database_problem, schema_name.read_record/same_schema, cypher_api._make_engine host branch/_get_engine/_engine/_reset_engine/health, actual ASGI request routing and response JSON',
        'substituted':'named connector and engine-constructor ports; returned SELECT1 scalar/exception; NativeAPI record get; execute_cypher result/exception; connection.close. No SQL engine, live IRIS, network listener, authentication/deployment/concurrency proof.',
        'formal_relation':'raw provider responses -> problem/main_boot/main_request and cache_request/reset; expected Python twin inspected against service_health spec; scalar SELECT1 equality varied, validated ASCII schema casing; no executable-body proof or general Unicode casing proof',
        'scope':'main app capture/sticky absence versus lazy cache retry, actual query/record decision to status/body, folded/empty error, reset including close failure; api/main.py lies outside historical production-member census and is reported separately'})
    d=json.loads(out.read_text())
    for path in extra:d['inputs'][path]=hashlib.sha256((PIN_DIR/path).read_bytes()).hexdigest()
    out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(f'service_health: {verdict}; {checks} comparisons; {len(mismatches)} mismatches -> {out}')
    print(json.dumps({'detection':detection,'first_mismatches':mismatches[:3],'network_calls':CONNECT.call_count}))
    return int(verdict!='AGREES')
if __name__=='__main__':raise SystemExit(main())
