"""Selected existing pinned offline unit tests; no database/network fixtures."""
import datetime,hashlib,json,os,shutil,socket,sys,time
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
FILES=['test_ledger_changeset.py','test_ledger_replay.py','test_ledger_client.py','test_ledger_errors.py','test_ledger_error_contract.py','test_ledger_commit_seam.py','test_ledger_guard.py','test_460_ledger_replay_temporal_marked.py','test_217_ledger_missing_node.py']
paths=[PIN/'tests/unit'/x for x in FILES];stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');dest=HERE/'ledger-content-attempts'/(stamp+'-upstream');dest.mkdir()
for src in [Path(__file__),*paths,*list((PIN/'iris_vector_graph/ledger').glob('*.py'))]:
 out=dest/('script' if src==Path(__file__) else 'pin')/src.name;out.parent.mkdir(exist_ok=True);shutil.copyfile(src,out)
inputs={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()};(dest/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1';os.environ['SKIP_IRIS_TESTS']='true';sys.path.insert(0,str(PIN));start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('upstream network forbidden')) as guard:
 import pytest
 rc=pytest.main(['-q','-c','/dev/null','--confcutdir='+str(PIN/'tests/unit'),'-p','no:cacheprovider',*map(str,paths)])
 calls=guard.call_count
body=dict(exit_code=rc,socket_connect_calls=calls,files=FILES,inputs=inputs,scope='Selected unchanged tests from exported product pin; no native runtime.',elapsed_s=time.monotonic()-start,snapshot=str(dest))
(HERE/'ledger-content-upstream.json').write_text(json.dumps(body,indent=2)+'\n');print(json.dumps(body));assert rc==0 and calls==0
