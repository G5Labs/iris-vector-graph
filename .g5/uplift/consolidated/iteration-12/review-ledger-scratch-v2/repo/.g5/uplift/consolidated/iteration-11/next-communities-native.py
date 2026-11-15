"""Preparatory root-only WCC/CDLP ordinary default-graph components and live loners."""
import hashlib,json,runpy,time,traceback,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
def main():
 start=time.monotonic();c=h['connect']();c2=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=4);w=h['IRISGraphEngine'](c2,embedding_dimension=4);e.ledger.disable();w.ledger.disable();n=e._iris_obj();prefix='cc11:'+uuid.uuid4().hex[:8]+':';node=lambda x:prefix+x;rows=[];failure=None
 edges=[('a','R','b'),('c','R','b'),('a','L','a'),('osc:a','R','osc:b'),('osc:a','L','osc:a'),('vote:x','R','vote:z'),('vote:x','S','vote:z'),('vote:x','T','vote:a'),('loop','L','loop')]
 def observe(label,fn,want=None,error=False):
  got=None;ex=None
  try:got=fn()
  except Exception as x:ex=dict(type=type(x).__name__,message=str(x))
  projected={k[len(prefix):]:str(v)[len(prefix):] if str(v).startswith(prefix) else v for k,v in got.items() if k.startswith(prefix)} if isinstance(got,dict) else got
  good=ex is not None if error else ex is None and (all(projected.get(k)==v for k,v in want.items()) if want is not None else True)
  rows.append(dict(label=label,projection=projected,error=ex,expected=want,agrees=good,cache_stats=dict(getattr(e._store,'_algo_cache_stats',{}))));assert good,rows[-1];return projected
 try:
  for s,p,o in edges:assert e.create_edge(node(s),p,node(o))
  assert e.create_node(node('iso'))
  core=lambda meth,*args:json.loads(str(n.classMethodValue('Graph.KG.Algorithms',meth,*args)))
  wccwant={'a':'a','b':'a','c':'a','osc:a':'osc:a','osc:b':'osc:a','vote:x':'vote:a','vote:z':'vote:a','vote:a':'vote:a','loop':'loop'}
  observe('actual WCC core fixed point',lambda:core('WCCJson'),wccwant)
  observe('actual public WCC adds isolate',lambda:e.kg_WCC(),dict(wccwant,iso='iso'))
  observe('actual WCC exhausted round1 refuses',lambda:core('WCCJson',1),error=True)
  observe('actual public WCC exhausted round1 refuses',lambda:e.kg_WCC(max_iterations=1),error=True)
  for k in [1,2,3,4]:
   pair={'osc:a':'osc:b','osc:b':'osc:a'} if k%2 else {'osc:a':'osc:a','osc:b':'osc:b'}
   if k==1:pair.update({'vote:x':'vote:z','loop':'loop'})
   observe('actual CDLP core round'+str(k),lambda k=k:core('CDLPJson',k),pair)
   observe('actual public CDLP round'+str(k),lambda k=k:e.kg_CDLP(k),dict(pair,iso='iso'))
  # Warm the actual shared core cache, then change only live SQL node membership.
  before_token=n.get('^KG','__version');before={alg:observe('warm '+alg,lambda alg=alg:e.kg_WCC() if alg=='wcc' else e.kg_CDLP(1)) for alg in ['wcc','cdlp']}
  assert w.create_node(node('late'))
  after_token=n.get('^KG','__version');assert after_token==before_token,(before_token,after_token)
  for alg in ['wcc','cdlp']:observe('second connection isolate insert '+alg,lambda alg=alg:e.kg_WCC() if alg=='wcc' else e.kg_CDLP(1),dict(before[alg],late='late'))
  assert w.delete_node(node('late'))
  for alg in ['wcc','cdlp']:
   got=observe('second connection isolate delete '+alg,lambda alg=alg:e.kg_WCC() if alg=='wcc' else e.kg_CDLP(1),before[alg]);assert 'late' not in got,got
 except Exception as ex:failure=dict(type=type(ex).__name__,message=str(ex),trace=traceback.format_exc());raise
 finally:
  result=dict(verdict='AGREES' if failure is None and rows and all(x['agrees'] for x in rows) else 'DISAGREES_OR_INCOMPLETE',cases=rows,completed_cases=len(rows),failure=failure,prefix=prefix,edges=edges,cache_token_before_insert=locals().get('before_token'),cache_token_after_insert=locals().get('after_token'),identity_checked=True,container=h['NAME'],source_inputs={rel:hashlib.sha256((h['PIN_DIR']/rel).read_bytes()).hexdigest() for rel in ['iris_src/src/Graph/KG/Algorithms.cls','iris_vector_graph/_engine/algorithms.py','iris_vector_graph/_edgeless.py','iris_vector_graph/stores/iris_sql_store.py','iris_vector_graph/algo_cache.py']},inputs={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'next-communities-PAIRS.md',REPO/'.g5/Verus_verification/models/temporal_restore/binding.py',REPO/'.g5/uplift/consolidated/iteration-5/native-setup.json']},elapsed=time.monotonic()-start,scope='Next-workflow preparation only. Ordinary disjoint task-owned default-graph components coexist with prior task fixtures; assertions concern only the fresh prefix. Two identity-guarded DBAPI connections, root serial native calls. No global erase/DDL/security/native body proof or new formal/issue credit. Shared-core cache plus fresh live loners checked, not transaction/race/ABA/cachewriter correctness. Typed-predicate vote multiplicity, no keyed parallel-mode mutation.')
  Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close();c2.close()
 print(json.dumps({k:result[k] for k in ['verdict','completed_cases','elapsed']}));assert result['verdict']=='AGREES'
if __name__=='__main__':main()
