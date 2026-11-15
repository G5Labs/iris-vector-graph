"""Selected pinned unit tests only, guarded against every socket connect."""
import json,os,socket,sys,time
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
pin=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(pin));os.chdir(pin)
start=time.monotonic()
files=['tests/unit/test_460_r270_ppr_networkx.py','tests/unit/test_460_r276_ppr_fast_path_errors.py','tests/unit/test_460_r050_ppr_seed_list.py','tests/unit/test_231_ppr_graph.py','tests/unit/test_235_ppr_exclude.py','tests/unit/test_ppr_bidirectional_passthrough.py']
with patch.object(socket.socket,'connect',side_effect=AssertionError('ppr selected units prohibit network')) as connect:
 import pytest
 code=pytest.main(['-q','-p','no:cacheprovider',*files])
 print(json.dumps({'exit_code':code,'elapsed':time.monotonic()-start,'blocked_socket_calls':connect.call_count,'files':files}))
 assert connect.call_count==0
raise SystemExit(code)
