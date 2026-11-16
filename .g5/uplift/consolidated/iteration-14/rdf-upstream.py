import json,os,socket,sys
from pathlib import Path
R=Path(__file__).resolve().parents[4];P=Path(os.environ.get('IVG_PIN_DIR','/Users/ziniuw/runs/ivg-consolidated-20261114/pin'));sys.path.insert(0,str(P));C=[]
def denied(*a,**k):C.append('socket');raise AssertionError('RDF unit replay forbids sockets')
socket.socket.connect=denied;socket.create_connection=denied
import pytest
files=['test_rdf_export.py','test_230_rdf_export_scope.py','test_460_rdf_graph_iri.py']
args=[str(P/'tests/unit'/x) for x in files]+['-q','--confcutdir='+str(P/'tests/unit')];code=pytest.main(args);assert C==[]
(R/'.g5/uplift/consolidated/iteration-14/rdf-upstream.json').write_text(json.dumps({'exit_code':code,'socket_calls':len(C),'args':args},indent=2)+'\n');raise SystemExit(code)
