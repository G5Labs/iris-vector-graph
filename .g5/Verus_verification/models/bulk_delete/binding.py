"""Real batch wrapper + _delete_in_scope + DeleteResult; storage and ledger guard substituted.
Cleanup failure is raised AFTER the fake primary delete. This is a unit-level
observation of the real caller's partial-effect/error handling, not an IRIS erase.
"""
import inspect,itertools,json,logging,sys,textwrap
from pathlib import Path
from types import SimpleNamespace
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN_DIR=bc.import_pin()
from iris_vector_graph._engine import nodes_edges as NE


def observe(raw,size,reject,cleanup,fn=None):
    live={'a','b'};e=NE.NodesEdgesMixin.__new__(NE.NodesEdgesMixin)
    e._reifiers_of=lambda ids,g:['r'] if set(ids)&cleanup else []
    e._graphs_holding=lambda ids:{'':ids}
    def delete(ids,graph=None):
        if ids==['r']:raise RuntimeError('cleanup failed')
        if set(ids)&reject:raise RuntimeError('primary refused')
        count=len(live&set(ids));live.difference_update(ids)
        return SimpleNamespace(rows=[[count]],error=None)
    e._store=SimpleNamespace(delete_nodes=delete)
    previous=NE._ledger_check;NE._ledger_check=lambda *a:None
    try:r=(fn or NE.NodesEdgesMixin.bulk_delete_nodes)(e,raw,batch_size=size,graph=None)
    finally:NE._ledger_check=previous
    return sorted(live),[r.deleted,r.failed,int(r),bool(r)]


def expected(raw,size,reject,cleanup):
    ids=[]
    for x in raw:
        if x is None or str(x)=='':continue
        if str(x) not in ids:ids.append(str(x))
    live={'a','b'};deleted=failed=0
    for i in range(0,len(ids),size):
        xs=set(ids[i:i+size])
        if xs&reject:failed+=len(xs);continue
        count=len(xs&live);live-=xs
        if xs&cleanup:failed+=len(xs)
        else:deleted+=count
    return sorted(live),[deleted,failed,deleted,deleted>0]


def compare(fn=None,change=False):
    mism=[];n=0
    for length in range(4):
        for raw in itertools.product([None,'','a','b','missing'],repeat=length):
            for size,reject,cleanup in itertools.product([1,2,3],[set(),{'a'}],[set(),{'a'}]):
                got=observe(raw,size,reject,cleanup,fn);want=expected(raw,size,reject,cleanup)
                if change and n==0:got=([],[0,0,0,False])
                if got!=want:mism.append({'raw':raw,'size':size,'reject':sorted(reject),'cleanup':sorted(cleanup),'got':got,'want':want})
                n+=1
    return n,mism


def main():
    n,mism=compare();_,changed=compare(change=True)
    src=textwrap.dedent(inspect.getsource(NE.NodesEdgesMixin.bulk_delete_nodes));scope=dict(vars(NE))
    assert src.count('failed += len(batch)')==1
    exec(src.replace('failed += len(batch)','failed += 0'),scope);_,mut=compare(scope['bulk_delete_nodes'])
    partial=observe(['a','b'],2,set(),{'a'})
    continued=observe(['a','b'],1,{'a'},set())
    assert partial==([],[0,2,0,False]) and continued==(['a'],[1,1,1,True])
    detection={'hidden_failed_count_mutant':bool(mut),'changed_live_content':bool(changed)}
    out=bc.write_receipt('bulk_delete',Path(__file__),{'verdict':'AGREES' if not mism and all(detection.values()) else 'DISAGREES',
        'comparisons':n,'mismatch_count':len(mism),'mismatches':mism[:5],'detection':detection,'pin':bc.pin_identity(PIN_DIR),
        'substituted':'store.delete_nodes with scripted pre-delete or post-delete cleanup failure; reifier/scope census and ledger guard; no IRIS or erasure service executes',
        'observed':'real ID normalization, batching, _delete_in_scope primary/cleanup order, exception wrapping, catch-and-continue, DeleteResult int/bool',
        'pairs':{'cleanup_failure':partial,'continue_after_primary_failure':continued},
        'domain':'raw sequences length 0..3 from None/empty/a/b/missing, size 1/2/3, primary reject a or none, cleanup failure a or none; one explicit default graph'})
    d=json.loads(out.read_text());print(f"bulk_delete: {d['verdict']}; {n} cases; {len(mism)} mismatches; {detection}; {out}")
    return int(d['verdict']!='AGREES')
if __name__=='__main__':raise SystemExit(main())
