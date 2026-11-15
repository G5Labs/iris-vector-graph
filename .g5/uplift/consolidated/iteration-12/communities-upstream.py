"""Selected unchanged exported-pin unit functions, no database/native/network."""
from pathlib import Path
import hashlib,importlib.util,inspect,json,os,socket,sys,time,traceback
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];PIN=Path(os.environ.get('IVG_PIN_DIR','/Users/ziniuw/runs/ivg-consolidated-20261114/pin'));sys.path.insert(0,str(PIN));sys.dont_write_bytecode=True
selected={
 'tests/unit/test_460_r306_edgeless.py':None,
 'tests/unit/test_algorithms_extended_unit.py':['TestKgWccCdlp'],
 'tests/unit/test_store_algorithm_dispatch.py':['test_wcc_arno_path_calls_arnoaccel','test_cdlp_arno_path_calls_arnoaccel'],
 'tests/unit/test_460_algorithms_forwarders.py':['test_execute_wcc_returns_the_engine_s_wcc'],
}
results=[];start=time.perf_counter();inputs={}
with patch.object(socket.socket,'connect',side_effect=AssertionError('unit network prohibited')) as connect:
 for i,(rel,names) in enumerate(selected.items()):
  path=PIN/rel;inputs[rel]=hashlib.sha256(path.read_bytes()).hexdigest();spec=importlib.util.spec_from_file_location('community_upstream_'+str(i),path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  for name in (names or [n for n,v in vars(m).items() if n.startswith('test_') and inspect.isfunction(v)]):
   item=getattr(m,name);calls=[(name+'.'+n,getattr(item(),n)) for n,v in vars(item).items() if n.startswith('test_')] if inspect.isclass(item) else [(name,item)]
   for label,fn in calls:
    t=time.perf_counter()
    try:fn();result='PASS';error=None
    except Exception as ex:result='FAIL';error=traceback.format_exc()
    results.append(dict(test=rel+'::'+label,verdict=result,elapsed_s=time.perf_counter()-t,error=error))
 body=dict(inputs=inputs,results=results,passed=sum(x['verdict']=='PASS' for x in results),failed=sum(x['verdict']!='PASS' for x in results),socket_connect_calls=connect.call_count,native_calls=0,elapsed_s=time.perf_counter()-start,scope='19 unchanged selected unit functions: raw labels/edgeless helpers, WCC/CDLP dispatch/fallback/argument forwarding; ordinary mock providers, no IRIS/native execution. Other centrality helpers remain upstream regression checks, not new formal credit.')
Path(__file__).with_suffix('.json').write_text(json.dumps(body,indent=2)+'\n');print(json.dumps(body));assert not body['failed'] and not connect.call_count
