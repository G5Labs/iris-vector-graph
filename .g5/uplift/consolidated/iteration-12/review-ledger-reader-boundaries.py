"""Actual pinned pure readers on frozen L19 carrier contrasts; no native/SQL calls."""
import hashlib,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
sys.dont_write_bytecode=True;t=time.perf_counter();cases=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('reader probe forbids sockets')) as guard:
 sys.path.insert(0,str(PIN));from iris_vector_graph.ledger.replay import MutationRecord,GraphState,compute_diff
 raw=json.dumps(dict(s='a',p='R',o='b',graph='named'),sort_keys=True,separators=(',',':'))
 def probe(name,op,kind,expected_entities,expected_entries,expected_redacted):
  r=MutationRecord(seq=1,ordinal=1,op=op,entity_kind=kind,entity_id='x',attr='',prior=None,new=raw,graph='named')
  s=GraphState();s.apply(r);d=compute_diff([r]);entry=d.to_list();actual=dict(node_ids=sorted(s.nodes),stmt_ids=sorted(s.statements),entries=entry,redacted=d.redacted)
  assert (len(s.nodes),len(s.statements))==expected_entities and entry==expected_entries and d.redacted==expected_redacted
  cases.append(dict(name=name,input=r.to_wire(),actual=actual,agrees=True))
 probe('temporal record ignored by structural fold but diff treats contributing unknown op as attribute','create_temporal_edge','temporal_edge',(0,0),[dict(entity_kind='temporal_edge',entity_id='x',attr='qual:',before=None,after=raw)],[])
 probe('non-node non-revision kind with create_rel still enters relationship reader','create_rel','other-kind',(0,1),[dict(entity_kind='other-kind',entity_id='x',attr='',before=None,after=raw)],[])
 probe('create_node with rel kind ignored by fold but classified as creation by diff','create_node','rel',(0,0),[dict(entity_kind='rel',entity_id='x',attr='',before=None,after=raw)],[])
 probe('revision audit ignored by both','arbitrary','revision',(0,0),[],[])
 probe('tombstone tracked separately in diff','redacted','node',(0,0),[],[(1,1)])
 assert guard.call_count==0
 src='iris_vector_graph/ledger/replay.py';h=hashlib.sha256((PIN/src).read_bytes()).hexdigest();assert hashlib.sha256((ROOT/src).read_bytes()).hexdigest()==h
 out=dict(verdict='OBSERVED_ACTUAL_SOURCE_BOUNDARIES',cases=cases,socket_connect_calls=guard.call_count,native_calls=0,elapsed_s=time.perf_counter()-t,source_sha256=h,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Five L19 pure-reader contrasts. Nonordinary kind/op and temporal histories limit a general endpoint theorem; no new product issue, native/SQL reachability, policy or formal coverage claim. Actual decoder constructors/readers unchanged, no candidate import.')
 HERE.joinpath('review-ledger-reader-boundaries.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(verdict=out['verdict'],cases=len(cases),sockets=guard.call_count,native=0,seconds=out['elapsed_s'])))
