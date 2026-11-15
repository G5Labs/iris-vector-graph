"""Run original health unit suites with import-time connection blocked, no listener."""
import os,socket,sys
from unittest.mock import patch
from pathlib import Path
pin=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
sys.path.insert(0,str(pin));os.chdir(pin)
os.environ['BOLT_ENABLED']='0'
with patch.object(socket.socket,'connect',side_effect=AssertionError('no network in health unit replay')) as sockets:
    from iris_devtester.utils import dbapi_compat
    with patch.object(dbapi_compat,'get_connection',side_effect=RuntimeError('source-only import')):
        import api.main
    import pytest
    code=pytest.main(['-q','-p','no:cacheprovider','-p','no:randomly',
        'tests/unit/test_463_api_health_check.py','tests/unit/test_r108_health_status_only.py'])
    print('socket_connect_calls',sockets.call_count)
raise SystemExit(code or int(bool(sockets.call_count)))
