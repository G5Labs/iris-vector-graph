"""Selected pinned codec/chunk/handshake units under a network guard."""
import os,sys,socket,time,json
from pathlib import Path
from unittest.mock import patch
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN));os.environ['BOLT_ENABLED']='0'
import pytest
start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('upstream units forbid network')) as guard:
    path=str(PIN/'tests/unit/test_bolt_server.py')
    names=['TestPackStreamPack','TestPackStreamRoundTrip','TestChunking','TestHandshake','TestGraphEncoding']
    result=pytest.main(['-q',*[path+'::'+n for n in names]])
    print(json.dumps({'pytest_exit':result,'socket_connect_calls':guard.call_count,'wall_s':time.monotonic()-start}))
    assert guard.call_count==0
raise SystemExit(result)
