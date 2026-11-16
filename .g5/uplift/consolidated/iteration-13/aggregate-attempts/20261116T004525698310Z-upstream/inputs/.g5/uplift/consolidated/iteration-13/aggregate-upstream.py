"""Selected ordinary aggregate source tests, pinned export, no conftest/native/network/Git."""
from pathlib import Path
import hashlib,json,os,socket,sys,time
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1';socket.has_ipv6=False
attempts=[]
class Guard(socket.socket):
 def __new__(cls,*a,**k):attempts.append(str(a));raise AssertionError('socket prohibited')
socket.socket=Guard
socket.create_connection=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network prohibited'))
pin=Path(os.environ['IVG_PIN_DIR']);sys.path.insert(0,str(pin))
import pytest
files=['test_sum_column_typing.py','test_460_r308_collect_typed.py','test_empty_result_columns.py','test_253_native_plan_groups.py','test_order_limit_aggregate_scope.py','test_460_r298_fixes46_leftovers.py']
class Reports:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.rows.append(dict(nodeid=report.nodeid,outcome=report.outcome,phase=report.when))
r=Reports();start=time.monotonic();code=pytest.main(['-q','-p','no:cacheprovider','--noconftest',*[str(pin/'tests/unit'/f) for f in files]],plugins=[r]);out=Path(__file__).with_suffix('.json')
body=dict(exit=code,cases=r.rows,passed=sum(x['outcome']=='passed' for x in r.rows),socket_attempts=attempts,native_calls=0,elapsed_s=time.monotonic()-start,inputs={str(Path('tests/unit')/f):hashlib.sha256((pin/'tests/unit'/f).read_bytes()).hexdigest() for f in files},scope='Relevant selected source tests only, no conftest/cache/native/network; source shape/read-helper tests do not prove SQL/native bodies.')
out.write_text(json.dumps(body,indent=2)+'\n');assert code==0 and not attempts;print(json.dumps({k:body[k] for k in ['passed','elapsed_s','native_calls','socket_attempts']}))
