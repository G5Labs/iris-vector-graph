import socket,sys,pytest
from unittest.mock import patch
with patch.object(socket.socket,'connect',side_effect=AssertionError('independent upstream forbids network')) as guard:
 code=pytest.main(sys.argv[1:])
 print('REVIEW_SOCKET_CONNECT_CALLS',guard.call_count)
 if guard.call_count: code=1
 raise SystemExit(code)
