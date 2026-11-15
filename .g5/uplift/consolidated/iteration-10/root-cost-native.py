"""New Cost frontier/historical-hop/fallback neighbors on ordinary native fixtures."""
import hashlib,json,runpy,subprocess,time,traceback,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
FIXTURES={
 'a1':[('s','a',4),('s','b',1),('b','a',1),('a','t',1)],
 'tie':[('s','a',2),('a','b',2),('b','c',2),('c','t',2),('s','x',3),('x','y',2),('y','t',3)],
 'frontsum':[('s','a',1),('a','b',1),('b','t',1),('s','x',2),('x','t',2)],
 'first':[('s','a',1),('a','t',9),('s','b',4),('b','t',4)]}
CASES=[('a1',0,20,3),('a1',2,20,5),('a1',3,20,3),('a1',2,4,None),('a1',2,5,5),
 ('tie',0,20,8),('tie',2,20,None),('tie',3,20,8),('tie',4,20,8),('tie',3,7,None),('tie',3,8,8),
 ('frontsum',0,2,None),('frontsum',0,3,3),('first',0,7,None),('first',0,8,8)]
def main():
    started=time.monotonic();sources={};identities={}
    for rel in ['iris_src/src/Graph/KG/Traversal.cls','iris_src/src/Graph/KG/TraversalPaths.cls','iris_src/src/Graph/KG/Adjacency.cls','iris_src/src/Graph/KG/AdjIndex.cls','iris_src/src/Graph/KG/GraphKey.cls','iris_vector_graph/engine.py','iris_vector_graph/_engine/nodes_edges.py']:
        p=h['PIN_DIR']/rel;sources[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
        pin=subprocess.check_output(['git','rev-parse','3eaa79cf:'+rel],cwd=REPO,text=True).strip()
        identities[rel]=dict(pin_blob=pin,export_equals=subprocess.check_output(['git','hash-object',str(p)],text=True).strip()==pin,current_equals=subprocess.check_output(['git','hash-object',str(REPO/rel)],text=True).strip()==pin)
    assert all(x['export_equals'] and x['current_equals'] for x in identities.values())
    c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);e.ledger.disable();n=e._iris_obj();graphs={};points=[];rows=[];failure=None
    def node(f,x):return 'cost10:'+f+':'+x
    try:
        for f,edges in FIXTURES.items():
            g='cost10:'+f+':'+uuid.uuid4().hex[:8];graphs[f]=g
            for a,b,w in edges:
                assert e.create_edge(node(f,a),'R',node(f,b),weight=w,graph=g)
                key=n.classMethodValue('Graph.KG.GraphKey','ForIndex',g);fw=n.get('^KG','out',key,node(f,a),'R',node(f,b));bw=n.get('^KG','in',key,node(f,b),'R',node(f,a))
                points.append(dict(fixture=f,source=a,target=b,weight=w,out=fw,reverse=bw,agrees=float(fw)==w and float(bw)==w))
        for f,H,cap,want in CASES:
            s=node(f,'s');t=node(f,'t');g=graphs[f]
            raw=n.classMethodValue('Graph.KG.TraversalPaths','DijkstraCost',s,t,cap,'out','[]',g,H);cost=None if raw is None or str(raw)=='' else float(raw)
            path=json.loads(str(n.classMethodValue('Graph.KG.Traversal','DijkstraJson',s,t,'weight',cap,H,'out','[]',g)))
            q=f"USE GRAPH '{g}' CALL ivg.shortestPath.weighted('{s}','{t}','weight',{cap},{H},'out',[]) YIELD totalCost RETURN totalCost"
            pub=e.execute_cypher(q,{},raise_on_error=True)
            witness=path=={} if want is None else path['nodes'][0]==s and path['nodes'][-1]==t and path['length']==len(path['nodes'])-1==len(path['rels'])==len(path['costs']) and (not H or path['length']<=H) and path['totalCost']==sum(path['costs'])==want and all(any((node(f,a),node(f,b),float(w))==(u,v,x) for a,b,w in FIXTURES[f]) for u,v,x in zip(path['nodes'],path['nodes'][1:],path['costs']))
            good=cost==want and witness and (pub.rows==[] if want is None else pub.rows==[[float(want)]])
            rows.append(dict(fixture=f,hops=H,cap=cap,want=want,cost_only=cost,path=path,public_query=q,public_rows=pub.rows,agrees=good))
    except Exception as ex:failure=dict(type=type(ex).__name__,message=str(ex),trace=traceback.format_exc());raise
    finally:
        result=dict(cases=rows,points=points,graphs=graphs,completed_cases=len(rows),scheduled_cases=len(CASES),failure=failure,identity_checked=True,container=h['NAME'],
            verdict='AGREES' if failure is None and len(rows)==len(CASES) and all(r['agrees'] for r in rows+points) else 'DISAGREES_OR_INCOMPLETE',
            source_inputs=sources,source_identities=identities,inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),REPO/'.g5/uplift/consolidated/iteration-9/weighted-cost-next-PAIRS.md',REPO/'.g5/uplift/consolidated/iteration-9/weighted-cost-next-plan.md',REPO/'.g5/Verus_verification/models/temporal_restore/binding.py']},elapsed=time.monotonic()-started,
            scope='Actual ordinary successful writers and out/in points, native Cost and JSON plus actual public cost-only parser/handler/reader. Fifteen new finite neighbors from frozen iteration9 Cost panel. No local BestHop/fallback-branch instrumentation; equal-cost shorter-hop tie can be conservative fallback, and actual branch proof stays in formal/source-port layer. No arbitrary numeric or native-body proof; q-iter-007 unchanged.')
        Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
    print(json.dumps({'verdict':result['verdict'],'cases':len(rows),'mirrored_points':len(points),'elapsed':result['elapsed']}));assert result['verdict']=='AGREES'
if __name__=='__main__':main()
