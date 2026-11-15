"""Explicit provider-state variations, not a claim that an ordinary writer corrupts mirrors."""
import hashlib,json,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
def main():
    c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);e.ledger.disable();n=e._iris_obj();g='wp9:mirror';s='wm9:s';a='wm9:a';t='wm9:t';out=[]
    for x,y in [(s,a),(a,t)]:assert e.create_edge(x,'R',y,weight=10,graph=g)
    key=n.classMethodValue('Graph.KG.GraphKey','ForIndex',g);point=('in',key,t,'R',a);original=n.get('^KG',*point)
    def observe(label):
        raw=n.classMethodValue('Graph.KG.Traversal','DijkstraJson',s,t,'weight',99,0,'out','[]',g);p=json.loads(str(raw) or '{}')
        raw=n.classMethodValue('Graph.KG.TraversalPaths','DijkstraCost',s,t,99,'out','[]',g,0);cost=None if raw is None or str(raw)=='' else float(raw)
        out.append(dict(label=label,path=p,cost_only=cost,out=n.get('^KG','out',key,a,'R',t),reverse=n.get('^KG',*point)))
    failure=None
    try:
        observe('complete ordinary producer mirrors')
        n.kill('^KG',*point);observe('explicit missing reverse coordinate')
        n.set(1,'^KG',*point);observe('explicit unequal reverse scalar')
    except Exception as ex:failure={'type':type(ex).__name__,'message':str(ex)};raise
    finally:
        n.set(original,'^KG',*point);observe('restored original point')
        result=dict(cases=out,failure=failure,identity_checked=True,container=h['NAME'],original_point_restored=n.get('^KG',*point)==original,
            inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'weighted-native.json',REPO/'.g5/Verus_verification/models/temporal_restore/binding.py']},
            scope='Actual native searches with deliberately varied task-owned raw adjacency provider state. Correct mirrors from ordinary writers first; one missing reverse entry then unequal reverse weight, restored in finally. Not a new ordinary-write defect, concurrency observation or arbitrary malformed-state guarantee. Demonstrates cost-only equivalence needs transpose/equal-effective-weight premise; primary JSON search is over actual selected out arcs.')
        Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
    assert [r['path']['totalCost'] for r in out]==[20.0]*4
    assert [r['cost_only'] for r in out]==[20.0,None,11.0,20.0]
    assert result['original_point_restored'];print(json.dumps({'cases':len(out),'path_costs':[r['path']['totalCost'] for r in out],'cost_only':[r['cost_only'] for r in out],'restored':True}))
if __name__=='__main__':main()
