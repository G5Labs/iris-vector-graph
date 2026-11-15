"""Provision only this iteration's freshly created, hostname-checked IVG runtime."""
import json,sys,os,time,subprocess
from pathlib import Path
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
sys.path.insert(0,str(PIN))
import iris,iris.dbapi
from tests import conftest as fx
from iris_vector_graph.engine import IRISGraphEngine
NAME='ivg-uplift-next-20261115';PORT=35975
def connect():
    conn=iris.dbapi.connect(hostname='127.0.0.1',port=PORT,namespace='USER',username='_SYSTEM',password='SYS')
    actual=fx.probe_instance_hostname(conn)
    if not fx.container_hostname_matches(actual,fx.docker_container_hostname(NAME),fx.docker_container_id(NAME)):
        conn.close();raise RuntimeError('database identity mismatch')
    return conn
def main():
    start=time.monotonic();conn=connect();e=IRISGraphEngine(conn,embedding_dimension=8)
    status=e.initialize_schema()
    result={'container':NAME,'port':PORT,'namespace':'USER','product_pin':'3eaa79cf77d3e0a879b2cced634cf2729d81499e','image':subprocess.check_output(['docker','inspect','-f','{{.Image}}',NAME],text=True).strip(),'identity_checked':True,'status':status,'elapsed':time.monotonic()-start}
    p=Path(__file__).with_name('native-setup.json');p.write_text(json.dumps(result,indent=2,default=str)+'\n')
    print(json.dumps({k:result[k] for k in ['container','port','identity_checked','elapsed']}));print(json.dumps({k:status.get(k) for k in ['schema','objectscript_failed','objectscript_skipped','warnings']},default=str))
    conn.close()
if __name__=='__main__':main()
