"""Selected pinned offline weighted caller/translation unit suites, no native/network."""
import hashlib,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');HERE=Path(__file__).resolve().parent
FILES=['test_weighted_shortest_path_parameters.py','test_weighted_shortest_path_types.py','test_weighted_cost_route.py','test_460_weighted_path_graph.py','test_460_weighted_path_raises.py','test_460_weighted_path_later_clauses.py','test_460_direction_argument.py','test_460_r183_gds_dijkstra.py']
start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('fraction upstream forbids sockets')) as guard:
    sys.path.insert(0,str(PIN));import pytest
    args=['-q','-p','no:cacheprovider','--confcutdir='+str(PIN/'tests/unit')]+[str(PIN/'tests/unit'/x) for x in FILES]
    code=pytest.main(args)
    j=dict(exit_code=int(code),socket_calls=guard.call_count,files={str(p.relative_to(PIN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [PIN/'tests/unit'/x for x in FILES]},script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),elapsed_s=time.monotonic()-start,scope='Pinned existing unit tests, no repository tests/conftest or DB fixture; no native body proof.')
    Path(__file__).with_suffix('.json').write_text(json.dumps(j,indent=2)+'\n')
    assert code==0 and guard.call_count==0
