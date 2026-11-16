#!/usr/bin/env python3
"""Run only reporting/scoped-count unit suites, with socket calls forbidden."""
import json,os,socket,sys
from pathlib import Path
R=Path(__file__).resolve().parents[4];P=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
sys.path[:0]=[str(P)]
CALLS=[]
def denied(*a,**kw):CALLS.append('socket');raise AssertionError('network disabled in reporting tests')
socket.socket.connect=denied;socket.create_connection=denied
import pytest
files=['test_230_status_counts.py','test_460_r050_status_unknown.py','test_460_r050_status_counts_every_graph.py','test_460_r219_counts_default_graph.py','test_460_r249_counters_default_graph.py','test_status_schema.py','test_460_status_probes.py','test_status_acceleration_label.py','test_460_r207_status_labels.py']
args=[str(P/'tests/unit'/f) for f in files]+[str(P/'tests/unit/test_engine_status.py')+'::TestEngineStatusUnit','-q','--confcutdir='+str(P/'tests/unit')]
result=pytest.main(args);assert CALLS==[],CALLS
out={'exit_code':result,'socket_attempts':len(CALLS),'command':args}
d=R/'.g5/uplift/consolidated/iteration-13';(d/'reporting-upstream.json').write_text(json.dumps(out,indent=2)+'\n');sys.exit(result)
