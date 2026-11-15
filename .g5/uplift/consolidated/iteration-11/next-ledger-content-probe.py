"""Next-draw source-only named full content; providers are explicit, no IRIS."""
import dataclasses,hashlib,json,runpy,socket,tempfile,time
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/history_diff/binding.py'));R=h['R'];hf=h['hf'];rec=h['rec']
def normalize(state):
 return dict(nodes={k:dict(labels=sorted(v.labels),props=dict(v.props)) for k,v in state.nodes.items()},rels={k:dict(s=v.s,p=v.p,o=v.o,graph=v.graph,quals=dict(v.quals)) for k,v in state.statements.items()})
def main():
 start=time.monotonic();calls=[];tup=json.dumps(dict(s='a',p='R',o='b',graph=None));rs=[rec(1,'create_node',id='a'),rec(1,'add_label',id='a',attr='L',new='',ordinal=2),rec(1,'set_prop',id='a',attr='k',new='1',ordinal=3),rec(1,'create_node',id='b',ordinal=4),rec(2,'create_rel',id='7',kind='rel',new=tup),rec(2,'set_qual',id='7',kind='rel',attr='w',new='1.25',ordinal=2),rec(3,'set_prop',id='a',attr='k',prior='1',new='2'),rec(3,'add_label',id='a',attr='M',new='',ordinal=2),rec(3,'set_qual',id='7',kind='rel',attr='w',prior='1.25',new='2.5',ordinal=3),rec(4,'remove_label',id='a',attr='M',prior='',ordinal=1),rec(4,'set_prop',id='a',attr='k',prior='2',new='1',ordinal=2),rec(4,'set_qual',id='7',kind='rel',attr='w',prior='2.5',new='1.25',ordinal=3)]
 expected={1:dict(nodes={'a':dict(labels=['L'],props={'k':'1'}),'b':dict(labels=[],props={})},rels={}),2:dict(nodes={'a':dict(labels=['L'],props={'k':'1'}),'b':dict(labels=[],props={})},rels={'7':dict(s='a',p='R',o='b',graph=None,quals={'w':'1.25'})}),3:dict(nodes={'a':dict(labels=['L','M'],props={'k':'2'}),'b':dict(labels=[],props={})},rels={'7':dict(s='a',p='R',o='b',graph=None,quals={'w':'2.5'})})};expected[4]=expected[2]
 g=hf.ledger(rs,100);results=[]
 with patch.object(socket.socket,'connect',side_effect=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('network forbidden'))) as guard:
  for seq in range(1,5):
   state=g.reconstruct(str(seq));got=normalize(state);assert got==expected[seq],(seq,got,expected[seq]);stream=list(g.reconstruct(str(seq),stream=True));assert len(stream)==len(expected[seq]['nodes'])+len(expected[seq]['rels'])
   path=Path(tempfile.mkdtemp(prefix='ivg-content-survey-'))/'out.ndjson';summary=g.export_reconstruction(str(seq),str(path));lines=[json.loads(s) for s in path.read_text().splitlines()]
   nodes={x['id']:dict(labels=x['labels'],props=x['props']) for x in lines if x['type']=='node'};rels={x['stmt_id']:dict(s=x['s'],p=x['p'],o=x['o'],graph=x['graph'],quals=x['quals']) for x in lines if x['type']=='rel'};assert dict(nodes=nodes,rels=rels)==expected[seq]
   results.append(dict(case='named full maps/stream/export',through=seq,observed=got,stream_entities=len(stream),export=lines,agrees=True))
  for a in range(1,5):
   for b in range(1,5):
    f=g.diff(str(a),str(b)).to_list();r=g.diff(str(b),str(a)).to_list();assert g.diff(str(a),str(b)).inverse().to_list()==r;assert a!=b or not f
    results.append(dict(case='named reverse/equal',a=a,b=b,entries=f,agrees=True))
  assert not g.diff('2','4').to_list();results.append(dict(case='same-life full label/property/qualifier restore net empty',entries=[],agrees=True))
  # Known deletion-time snapshot issue, now retain rich multi-attribute content.
  snapshot=json.dumps(dict(labels=['L','M'],props={'k':'2'}),sort_keys=True);life=rs[:4]+rs[6:8]+[rec(4,'delete_node',id='a',prior=snapshot),rec(5,'create_node',id='a'),rec(5,'set_prop',id='a',attr='k',new='3',ordinal=2)]
  lg=hf.ledger(life,100);before=normalize(lg.reconstruct('1'));after=normalize(lg.reconstruct('5'));reverse=lg.diff('5','1').to_list();delete_snapshot=next(json.loads(x['after']) for x in reverse if x['entity_id']=='a' and x['attr']=='' and x['after'] is not None)
  assert before['nodes']['a']['props']['k']=='1' and delete_snapshot['props']['k']=='2' and before['nodes']['a']['labels']==['L'] and delete_snapshot['labels']==['L','M']
  results.append(dict(case='known range-prior loss across rich lifecycle',before=before,after=after,reverse=reverse,deletion_snapshot=delete_snapshot,agrees=True,new_bug=False,policy='q-con-002 unresolved; not applied as script'))
  # Native rows retain actual null flag vs empty text; source fixture only.
  def row(null,new):return (1,1,'set_prop','node','a','k','',1,new,null,'','')
  nulls=[R.MutationRecord.from_row(row(1,'')),R.MutationRecord.from_row(row(0,'')),R.MutationRecord.from_row(row(0,'null'))];assert [x.new for x in nulls]==[None,'','null'];results.append(dict(case='raw row nullflag empty and JSON-null text distinct',new_values=[x.new for x in nulls],agrees=True))
  assert guard.call_count==0
 result=dict(verdict='AGREES',cases=results,case_count=len(results),source_inputs={rel:hashlib.sha256((h['PIN']/rel).read_bytes()).hexdigest() for rel in ['iris_vector_graph/ledger/replay.py','iris_vector_graph/ledger/client.py','iris_vector_graph/ledger/export.py']},inputs={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'next-ledger-content-PAIRS.md',REPO/'.g5/Verus_verification/tools/history_fixture.py']},elapsed=time.monotonic()-start,socket_calls=0,new_model_or_formal_credit=0,new_issues=0,scope='Next workflow preparation only; actual named Python decoder/pager/fold/diff/stream/export over explicit SQL/meta/revision/redaction-guard fixture. Explicit expected full maps independent of the GraphState implementation. Histories are semantic admitted shapes, not native-writer reachability proof. Existing lifecycle finding strengthened, no policy decision/full endpoint script claim.')
 Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');print(json.dumps({k:result[k] for k in ['verdict','case_count','elapsed','socket_calls']}))
if __name__=='__main__':main()
