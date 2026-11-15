"""Actual native-capped sparse producer into actual every-node Python reader."""
import hashlib,json,runpy,time,traceback,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
def main():
    start=time.monotonic();c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);e.ledger.disable();rows=[];failure=None;graph='pp10:cap:'+uuid.uuid4().hex[:8]
    ids=['cap10:'+str(i).zfill(4) for i in range(1002)]
    try:
        added=e.bulk_create_nodes([{'id':x} for x in ids],disable_indexes=False,graph=graph);assert added==ids
        for exclude,limit,label in [(None,1002,'capped producer with larger reader limit'),([],1002,'explicit exclusion list forwards limit'),(None,1000,'limit fits native cap')]:
            got=e.kg_PERSONALIZED_PAGERANK(ids,damping_factor=.5,max_iterations=1,tolerance=0,return_top_k=limit,graph=graph,exclude_predicates=exclude)
            zeros=[k for k,v in got.items() if v==0.0];positive=[v for v in got.values() if v>0]
            want_zero=2 if exclude is None and limit==1002 else 0
            ok=len(got)==limit and len(zeros)==want_zero and all(abs(v-1/1002)<1e-12 for v in positive)
            rows.append(dict(label=label,exclude=exclude,top_k=limit,row_count=len(got),zero_ids=zeros,positive_count=len(positive),mass=sum(got.values()),samples=list(got.items())[:2]+list(got.items())[-3:],source_prediction_agrees=ok))
        got=e._kg_PERSONALIZED_PAGERANK_python_fallback(ids,.5,1,0,1002,False,1,graph=graph)
        rows.append(dict(label='actual Python fallback',row_count=len(got),zero_ids=[k for k,v in got.items() if v==0],positive_count=sum(v>0 for v in got.values()),mass=sum(got.values()),source_prediction_agrees=len(got)==1002 and all(abs(v-1/1002)<1e-12 for v in got.values())))
    except Exception as ex:failure=dict(type=type(ex).__name__,message=str(ex),trace=traceback.format_exc());raise
    finally:
        result=dict(cases=rows,completed_cases=len(rows),scheduled_cases=4,failure=failure,graph=graph,persisted_node_count=len(added) if 'added' in locals() else None,all_nodes_are_valid_seeds=True,identity_checked=True,container=h['NAME'],elapsed=time.monotonic()-start,
            verdict='AGREES_SOURCE_PREDICTION' if failure is None and len(rows)==4 and all(r['source_prediction_agrees'] for r in rows) else 'DISAGREES_OR_INCOMPLETE',
            inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'root-ppr-cap-predictions.md',REPO/'.g5/Verus_verification/models/temporal_restore/binding.py']},
            source_inputs={rel:hashlib.sha256((h['PIN_DIR']/rel).read_bytes()).hexdigest() for rel in ['iris_src/src/Graph/KG/PageRank.cls','iris_vector_graph/_engine/algorithms.py','iris_vector_graph/stores/iris_sql_store.py','iris_vector_graph/_engine/nodes_edges.py']},
            scope='Actual successful bulk node writes without index disable/rebuild, actual public native/store PPR and actual private Python fallback using real owned DB; distinct source-derived producer-cap/final-reader neighbors. No generic recurrence/numeric/native-body proof or provider-unavailability dispatch claim. Correct all-node one-step score mathematically1/1002, comparisons tolerate native/Python arithmetic rounding1e-12.')
        Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
    print(json.dumps({'verdict':result['verdict'],'cases':len(rows),'node_count':len(ids),'zero_counts':[len(r['zero_ids']) for r in rows],'elapsed':result['elapsed']}));assert result['verdict']=='AGREES_SOURCE_PREDICTION'
if __name__=='__main__':main()
