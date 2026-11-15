"""Seven bounded reader counterexamples/premise checks; no native/network/model."""
import hashlib,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('ledger source review forbids sockets')) as guard:
 sys.path.insert(0,str(PIN))
 from iris_vector_graph.ledger.replay import GraphState,MutationRecord as R,compute_diff,_parse_tuple
 def rec(op,kind='node',eid='a',attr='',prior=None,new=None,seq=1,ordinal=1):return R(seq,ordinal,op,kind,eid,attr,prior,new,None)
 def fold(rs):
  s=GraphState()
  for r in rs:s.apply(r)
  return s
 cases=[]
 embedded=fold([rec('create_node',new=json.dumps(dict(labels=['L'],props={'k':'v'})))])
 cases.append(dict(case='create does not unpack embedded node content',observed=dict(labels=sorted(embedded.nodes['a'].labels),props=embedded.nodes['a'].props),reader_admitted=True,ordinary_ApplyAll_record=False,source='ApplyAll create_node emits empty new, then add_label/set_prop; do not encode a create payload snapshot as already-applied maps.'))
 nullrec=rec('set_prop',attr='k',new=None)
 nullable=fold([rec('create_node'),nullrec]);delta=compute_diff([nullrec]).to_list()
 assert nullable.nodes['a'].props=={'k':''} and delta==[]
 cases.append(dict(case='raw set None differs from absent property but diff prior/new None cancels',props=nullable.nodes['a'].props,diff=delta,reader_admitted=True,ordinary_ApplyAll_record=False,source='SetProp emits Enc(value), never EncNull as new; null JSON MetaGet becomes empty text. Adoption is a separate permissive record writer.'))
 t=json.dumps(dict(s='a',p='R',o='b',graph=None));rs=[rec('create_rel','rel','1',new=t),rec('set_qual','rel','1','w',new='1'),rec('create_rel','rel','2',new=t),rec('set_qual','rel','2','w',new='2')]
 parallel=fold(rs);before=dict(statements=len(parallel.statements),comparable_tuples=len(parallel.as_comparable()['rels']),tuple_lookup=parallel.stmt_for_tuple(('a','R','b',None)))
 parallel.apply(rec('delete_rel','rel','1'))
 after=dict(statement_ids=sorted(parallel.statements),tuple_lookup=parallel.stmt_for_tuple(('a','R','b',None)))
 assert before==dict(statements=2,comparable_tuples=1,tuple_lookup='2') and after==dict(statement_ids=['2'],tuple_lookup=None)
 cases.append(dict(case='parallel IDs are not a tuple bijection',before=before,after=after,source_conditional_native_reach='Genesis.Capture allocates once per physical non-temporal edge row; Enable has no duplicate/GraphMode guard. Native duplicate-row fixture unexecuted here.',new_issue=False))
 graphs=[_parse_tuple(json.dumps(dict(s='a',p='R',o='b',graph=g)))[3] for g in [None,'','\x00','named']]
 assert graphs==[None,None,None,'named'];cases.append(dict(case='tuple default graph normalization',observed=graphs))
 named=json.dumps(dict(s='a',p='R',o='b',graph='named'))
 namedstate=fold([rec('create_node',eid='a'),rec('create_node',eid='b'),rec('create_rel','rel','3',new=named),rec('delete_node',eid='a')])
 assert 'a' not in namedstate.nodes and '3' in namedstate.statements
 cases.append(dict(case='delete_node has no GraphState relationship cascade',nodes=sorted(namedstate.nodes),statements=sorted(namedstate.statements),source_conditional_native_reach='ApplyAll deletes default-graph incidents only; a named relationship survives its default bare-ID profile deletion. Do not infer global endpoint closure.'))
 full=json.dumps(dict(labels=['L'],props={'k':'v'}));a=fold([rec('create_node'),rec('delete_node',prior=full)]);b=fold([rec('create_node'),rec('delete_node',prior='')])
 assert a.as_comparable()==b.as_comparable()
 cases.append(dict(case='fold cannot validate deletion snapshot truth',folds_equal=True,diff_full=compute_diff([rec('delete_node',prior=full)]).to_list(),diff_empty=compute_diff([rec('delete_node',prior='')]).to_list(),source='DeleteNodeRows derives snapshot before deletion; snapshot correctness must follow actual SQL contents/query contract, not the final empty fold. Simple complete deletion snapshot remains passing; no policy decision.'))
 reserved=fold([rec('create_node'),rec('set_prop',attr='id',new='x'),rec('set_qual','rel','missing','id',new='x')])
 assert reserved.nodes['a'].props=={'id':'x'}
 cases.append(dict(case='GraphState accepts reserved raw record key',props=reserved.nodes['a'].props,reader_admitted=True,ordinary_ApplyAll_record=False,source='Ordinary node-property producer rejects id/__graph; reader does not. Relationship qualifier keys use a different admission rule.'))
 out=dict(verdict='AGREES',cases=cases,case_count=len(cases),socket_calls=guard.call_count,native_calls=0,elapsed_s=time.monotonic()-start,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),product_inputs={p:hashlib.sha256((PIN/p).read_bytes()).hexdigest() for p in ['iris_vector_graph/ledger/replay.py','iris_src/src/Graph/KG/LedgerApply.cls','iris_src/src/Graph/KG/LedgerGenesis.cls','iris_src/src/Graph/KG/Ledger.cls']},scope='Seven bounded exact Python reader observations, source-based native reach assessment only. No new model, issue, source patch, native writer claim or q-con-002 decision.')
 assert guard.call_count==0
 Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['verdict','case_count','socket_calls','native_calls','elapsed_s']}))
