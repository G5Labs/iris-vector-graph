"""Explicit zero-fixture product unit functions under a socket guard; no pytest discovery."""
import hashlib,importlib.util,inspect,json,socket,sys,time,traceback
from pathlib import Path
from unittest.mock import patch
GUARD=patch.object(socket.socket,'connect',side_effect=AssertionError('vector unit survey forbids network'));CONNECT=GUARD.start()
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN));HERE=Path(__file__).resolve().parent
began=time.monotonic();results=[];inputs={}
for name in ['test_227_query_width.py','test_227_ivf_route.py','test_227_route_cache.py']:
 p=PIN/'tests/unit'/name;inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();spec=importlib.util.spec_from_file_location('vector_survey_'+p.stem,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 for key,fn in vars(m).items():
  if not key.startswith('test_') or not callable(fn):continue
  if inspect.signature(fn).parameters:results.append({'test':name+'::'+key,'status':'SKIPPED_FIXTURE'});continue
  try:fn();results.append({'test':name+'::'+key,'status':'PASS'})
  except Exception as ex:results.append({'test':name+'::'+key,'status':'FAIL','type':type(ex).__name__,'error':str(ex),'trace':traceback.format_exc()})
body={'verdict':'PASS' if all(x['status']=='PASS' for x in results) and CONNECT.call_count==0 else 'FAIL_OR_SKIP','tests':results,'count':len(results),'socket_connect_calls':CONNECT.call_count,'source_inputs':inputs,'elapsed':time.monotonic()-began,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Explicit existing non-security unit functions; raw SQL/metadata are mocked. No native DB or server tests; no private/evaluator file read.'};Path(__file__).with_suffix('.json').write_text(json.dumps(body,indent=2)+'\n');print(json.dumps({'verdict':body['verdict'],'count':len(results),'failed':[x['test'] for x in results if x['status']!='PASS'],'sockets':CONNECT.call_count,'elapsed':body['elapsed']}));assert body['verdict']=='PASS'
