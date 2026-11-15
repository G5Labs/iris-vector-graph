"""Actual ordinary PPR producer -> native/Python final-reader tie and top-k neighbors."""
import hashlib,json,runpy,traceback,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
from iris_vector_graph._collation import rank_key
def main():
    c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);e.ledger.disable();n=e._iris_obj();rows=[];failure=None
    try:
        for late,alpha,top in [(False,1e-13,None),(False,1e-13,2),(False,1e-13,1),(False,1e-11,None),(False,1e-11,2),(True,1e-13,2)]:
            graph='pp10:tie:'+uuid.uuid4().hex[:8];s='s:seed';t='t:tiny';z='z:zero' if late else '0:zero'
            assert e.create_edge(s,'R',t,graph=graph);e.create_node(z,graph=graph)
            raw=n.classMethodValue('Graph.KG.PageRank','RunJson',json.dumps([s]),alpha,1,0,1,graph,'[]',top or 0,0)
            filled=n.classMethodValue('Graph.KG.PageRank','WithUnscored',str(raw),'Graph_KG',graph,top or 0)
            sparse=json.loads(str(raw));native=json.loads(str(filled));native_pairs=[(str(r['id']),float(r['score'])) for r in native]
            public=e.kg_PERSONALIZED_PAGERANK([s],damping_factor=alpha,max_iterations=1,tolerance=0,return_top_k=top,graph=graph,exclude_predicates=[])
            py=e._kg_PERSONALIZED_PAGERANK_python_fallback([s],alpha,1,0,top,False,1,graph=graph,exclude_predicates=[])
            want={s:1-alpha,t:alpha,z:0.0};full=sorted(want.items(),key=lambda p:rank_key(*p));full=full[:top] if top else full
            append=[(s,1-alpha),(t,alpha),(z,0.0)];append=append[:top] if top else append
            # Two literal source-derived reader predictions, no chosen policy.
            source_ok=native_pairs==append and list(public.items())==append and list(py.items())==full
            rows.append(dict(graph=graph,alpha=alpha,top_k=top,zero_id=z,sparse=sparse,native=native_pairs,public_store=list(public.items()),python_fallback=list(py.items()),full_rounded_order=full,positive_then_zero_order=append,
                rounded_keys={k:str(rank_key(k,v)) for k,v in want.items()},routes_same_selected_order=list(public.items())==list(py.items()),source_prediction_agrees=source_ok))
    except Exception as ex:failure=dict(type=type(ex).__name__,message=str(ex),trace=traceback.format_exc());raise
    finally:
        result=dict(cases=rows,completed_cases=len(rows),scheduled_cases=6,failure=failure,identity_checked=True,container=h['NAME'],
            verdict='AGREES_SOURCE_PREDICTION' if failure is None and len(rows)==6 and all(r['source_prediction_agrees'] for r in rows) else 'DISAGREES_OR_INCOMPLETE',
            inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'root-ppr-tie-predictions.md',REPO/'.g5/Verus_verification/models/temporal_restore/binding.py']},
            source_inputs={rel:hashlib.sha256((h['PIN_DIR']/rel).read_bytes()).hexdigest() for rel in ['iris_src/src/Graph/KG/PageRank.cls','iris_vector_graph/_engine/algorithms.py','iris_vector_graph/_collation.py','iris_vector_graph/stores/iris_sql_store.py']},
            scope='Actual ordinary named-graph row/adjacency writes, ObjectScript RunJson/WithUnscored, public store route and Python fallback using real database reads. Finite source-derived tiny/zero ordering and cut observation; no approved policy, generic numerical/body proof, Arno route, external service or security scenario. Fresh task-owned graph per case.')
        Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
    print(json.dumps({'verdict':result['verdict'],'cases':len(rows),'routes_same':[r['routes_same_selected_order'] for r in rows]}));assert result['verdict']=='AGREES_SOURCE_PREDICTION'
if __name__=='__main__':main()
