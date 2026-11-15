"""Selected existing source/mock units only; omit live and authentication scenarios."""
import json,os,socket,sys,time
from pathlib import Path
from unittest.mock import patch
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN));os.chdir(PIN)
os.environ['BOLT_ENABLED']='0';os.environ.pop('IVG_API_KEY',None);os.environ.pop('IVG_READ_ONLY',None)
paths=['tests/unit/test_weighted_shortest_path_parameters.py','tests/unit/test_460_weighted_path_graph.py','tests/unit/test_weighted_shortest_path_types.py','tests/unit/test_weighted_cost_route.py','tests/unit/test_460_weighted_path_raises.py','tests/unit/test_460_weighted_path_later_clauses.py','tests/unit/test_460_r183_gds_dijkstra.py',
 'tests/unit/test_bolt_server.py::TestPackStreamPack','tests/unit/test_bolt_server.py::TestPackStreamRoundTrip','tests/unit/test_bolt_server.py::TestChunking','tests/unit/test_bolt_server.py::TestHandshake','tests/unit/test_bolt_server.py::TestGraphEncoding']
start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('remaining survey forbids network')) as guard:
 import pytest
 result=pytest.main(['-q','-p','no:cacheprovider','-p','no:randomly',*paths])
 count=guard.call_count
out={'paths':paths,'exit_code':result,'socket_connect_calls':count,'wall_s':time.monotonic()-start,'excluded':'misnamed weighted_shortest_path unit file requires actual IRIS; authentication/session-key unit scenarios omitted'}
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out));raise SystemExit(result or int(count>0))
