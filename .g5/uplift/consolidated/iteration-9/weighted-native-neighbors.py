"""Source-derived public/native boundary neighbors on the retained weighted fixtures."""
import hashlib,json,runpy,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
def main():
    c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);n=e._iris_obj();rows=[]
    def public(label,args,want=None,error=False,graph='wp9:a'):
        q=(f"USE GRAPH '{graph}' " if graph is not None else '')+'CALL ivg.shortestPath.weighted('+args+') YIELD totalCost RETURN totalCost'
        got=None;ex=None
        try:got=e.execute_cypher(q,{},raise_on_error=True).rows
        except Exception as x:ex={'type':type(x).__name__,'message':str(x)}
        ok=(ex is not None and ex['type']=='ValueError') if error else ex is None and sorted(r[0] for r in got)==sorted(want)
        rows.append(dict(label=label,query=q,rows=got,error=ex,expected_error=error,expected_costs=want,agrees=ok))
    public('negative public hops refused',"'wp9:s','wp9:t','weight',99,-1",error=True)
    public('empty public source refused',"'','wp9:t'",error=True)
    public('empty public target refused',"'wp9:s',''",error=True)
    public('unknown weight refused',"'wp9:s','wp9:t','price'",error=True)
    public('unknown direction refused',"'wp9:s','wp9:t','weight',99,0,'sideways'",error=True)
    public('negative cap self precedes cap and existence',"'wp9:ghost','wp9:ghost','weight',-1,0",[0.0])
    public('negative cap distinct has no path',"'wp9:s','wp9:t','weight',-1,0",[])
    public('zero public hops unbounded',"'wp9:s','wp9:t','weight',99,0",[3.0])
    public('bounded public hops alternative',"'wp9:s','wp9:t','weight',99,2",[5.0])
    for types,want in [('[]',[2.0]),("['R']",[4.0]),("['S']",[]),("'R'",[4.0])]:
        public('public types '+types,"'wp9:s','wp9:t','weight',99,0,'out',"+types,want,graph='wp9:norm')
    public('unspecified graph enumerates each graph',"'wp9:s','wp9:t','weight',99,0",[3.0,8.0,2.0,4.0,2.0],graph=None)
    for src,dst,hops,cap,want in [('wp9:s','wp9:t',-1,99,3.0),('wp9:ghost','wp9:ghost',0,-1,0.0),('','wp9:t',0,99,None),('wp9:s','',0,99,None)]:
        raw=n.classMethodValue('Graph.KG.Traversal','DijkstraJson',src,dst,'weight',cap,hops,'out','[]','wp9:a');p=json.loads(str(raw) or '{}')
        cost=n.classMethodValue('Graph.KG.TraversalPaths','DijkstraCost',src,dst,cap,'out','[]','wp9:a',hops);cost=None if cost is None or str(cost)=='' else float(cost)
        got=p.get('totalCost');rows.append(dict(label='direct native endpoint/hop/cap',source=src,target=dst,hops=hops,cap=cap,path=p,cost=cost,expected=want,agrees=got==want and cost==want))
    result=dict(rows=rows,comparisons=len(rows),identity_checked=True,container=h['NAME'],agrees=all(r['agrees'] for r in rows),
        inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'weighted-native.py',HERE/'weighted-native.json',REPO/'.g5/Verus_verification/models/temporal_restore/binding.py']},
        scope='Source-derived neighboring outcomes, not blind predictions. Reads retained five native fixtures from weighted-native AGREES run; no graph edit, security scenario, native body proof or arbitrary numeric equivalence. Public errors differ from direct native empty endpoint/no-path and negative hop behavior.')
    Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
    print(json.dumps({'comparisons':len(rows),'agrees':result['agrees'],'disagreements':[r for r in rows if not r['agrees']]}));assert result['agrees']
if __name__=='__main__':main()
