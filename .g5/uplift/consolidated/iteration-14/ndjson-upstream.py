"""Relevant pinned healthy read/type/import tests; no conftest/native/Git/network or test cache."""
from pathlib import Path
import json,os,hashlib,socket,sys,time
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1';socket.has_ipv6=False
attempts=[]
class Guard(socket.socket):
 def __new__(cls,*a,**k):attempts.append(str(a));raise AssertionError('socket prohibited')
socket.socket=Guard;socket.create_connection=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network prohibited'))
PIN=Path(os.environ['IVG_PIN_DIR']);sys.path.insert(0,str(PIN))
import pytest
names=['test_get_nodes.py','test_230_get_nodes_graph_scope.py','test_460_r218_typed_node_reads.py::TestGetNode','test_460_r218_typed_node_reads.py::TestDecode','test_edgeprop_ndjson.py::TestNdjsonUnit::test_import_upserts_duplicate_nodes','test_edgeprop_ndjson.py::TestNdjsonUnit::test_import_skips_unknown_kind']
class Reports:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.rows.append(dict(nodeid=report.nodeid,outcome=report.outcome,phase=report.when))
r=Reports();start=time.monotonic();args=[str(PIN/'tests/unit'/name.split('::')[0])+('::'+'::'.join(name.split('::')[1:]) if '::' in name else '') for name in names];code=pytest.main(['-q','--noconftest','-p','no:cacheprovider',*args],plugins=[r]);body=dict(passed=sum(x['outcome']=='passed' for x in r.rows),cases=r.rows,exit=code,socket_attempts=attempts,native_calls=0,Git_calls=0,elapsed_s=time.monotonic()-start,inputs={str(Path('tests/unit')/name.split('::')[0]):hashlib.sha256((PIN/'tests/unit'/name.split('::')[0]).read_bytes()).hexdigest() for name in names},scope='Selected existing healthy mock/read/type/import unit regressions. Broader scalar decoding observations retain old provider qualifications; no Native/E2E/conftest/fault/security/prohibited-boundary work.')
Path(__file__).with_suffix('.json').write_text(json.dumps(body,indent=2)+'\n');assert code==0 and not attempts;print(json.dumps({k:body[k] for k in ['passed','elapsed_s','socket_attempts','native_calls','Git_calls']}))
