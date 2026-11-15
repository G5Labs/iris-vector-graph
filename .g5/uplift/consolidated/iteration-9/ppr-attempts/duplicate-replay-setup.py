"""Source-derived PPR reverse-weight challenge on task-owned ordinary fixtures.
Two shipped implementations, real row reads and native Owner, no native-library route.
"""
import hashlib,json,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
def main():
    c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);e.ledger.disable();n=e._iris_obj();graph='pp9:reverse';a='pp9:a';b='pp9:b';out=[]
    assert e.create_edge(a,'R',b,graph=graph)
    # Source-derived prediction before calls: with seed b, one reverse edge,
    # alpha1/2 and one iteration, actual unweighted divisor gives a=w/2,b=1/2
    # for positive reverse multiplier w. At w0 there is no reverse walk: b=1.
    # This is an as-built prediction, not an endorsement of non-unit mass.
    for bidir,w in [(False,2),(True,0),(True,.5),(True,1),(True,2)]:
        raw=n.classMethodValue('Graph.KG.PageRank','RunJson',json.dumps([b]),.5,1,1 if bidir else 0,w,graph,'[]',0,0)
        sparse=json.loads(str(raw));filled=n.classMethodValue('Graph.KG.PageRank','WithUnscored',str(raw),'Graph_KG',graph,0)
        parsed=json.loads(str(filled));native={str(row['id']):float(row['score']) for row in parsed}
        py=e._kg_PERSONALIZED_PAGERANK_python_fallback([b],.5,1,0,None,bidir,w,graph=graph,exclude_predicates=[])
        want={a:w/2,b:.5} if bidir and w>0 else {a:0.0,b:1.0}
        out.append(dict(bidirectional=bidir,reverse_weight=w,native_sparse=sparse,native=native,python=py,source_prediction=want,native_mass=sum(native.values()),python_mass=sum(py.values()),agrees=native==want and py==want))
    result=dict(cases=out,identity_checked=True,container=h['NAME'],graph=graph,agrees=all(r['agrees'] for r in out),
        source_inputs={rel:hashlib.sha256((h['PIN_DIR']/rel).read_bytes()).hexdigest() for rel in ['iris_src/src/Graph/KG/PageRank.cls','iris_vector_graph/_engine/algorithms.py']},
        inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'next-survey-ppr-PAIRS.md',REPO/'.g5/Verus_verification/models/temporal_restore/binding.py']},
        scope='Five source-derived finite one-step traces, actual ObjectScript Owner/WithUnscored and actual Python fallback using persisted graph/node/edge reads. Named graph avoids default native-reader routing. No generic recurrence, arbitrary numerical equivalence, cache proof or new adjudicated issue is claimed. Mass for nonunit reverse multiplier is a next-round intent/model challenge.')
    Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
    print(json.dumps({'cases':len(out),'agrees':result['agrees'],'masses':[(r['bidirectional'],r['reverse_weight'],r['native_mass']) for r in out]}));assert result['agrees']
if __name__=='__main__':main()
