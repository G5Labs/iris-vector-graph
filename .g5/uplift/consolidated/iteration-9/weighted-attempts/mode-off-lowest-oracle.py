"""Actual weighted writers/search/readers against an independent finite-walk oracle.
Only the identity-checked task-owned IRIS; integer small weights/stable fixtures.
"""
import hashlib,itertools,json,random,runpy,time,traceback
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
from iris_vector_graph import engine as em
N=lambda x:'wp9:'+x
FIXTURES=[('wp9:a',[('s','R','a',4),('s','R','b',1),('b','R','a',1),('a','R','t',1)]),
 ('wp9:other',[('s','R','a',8),('s','R','b',2),('b','R','a',2),('a','R','t',4)]),
 ('wp9:norm',[('s','R','a',0),('a','S','t',-3),('s','R','t',4),('t','R','t',0),('a','X','b',None)]),
 ('wp9:multi',[('s','R','t',10),('s','R','a',2),('a','R','t',2)]),
 ('',[('s','R','t',2),('s','S','a',1),('a','R','t',2)])]

def effective(raw):return raw if raw is not None and raw>0 else 1

def oracle(edges,source,target,hops,cap,direction,preds):
    # Any admitted ID has the source==target empty path, regardless of node table.
    if source==target:return 0
    arcs=[]
    for s,p,o,w in edges:
        if preds and p not in preds:continue
        if direction in ['out','both']:arcs.append((s,p,o,effective(w)))
        if direction in ['in','both']:arcs.append((o,p,s,effective(w)))
    vertices={source,target}|{s for s,p,o,w in arcs}|{o for s,p,o,w in arcs}
    limit=min(hops,len(vertices)-1) if hops else len(vertices)-1
    best=None;stack=[(source,0,0,{source})]
    while stack:
        node,cost,depth,seen=stack.pop()
        if node==target:
            if cost<=cap:best=cost if best is None else min(best,cost)
            continue
        if depth>=limit:continue
        for s,p,o,w in arcs:
            if s==node and o not in seen and cost+w<=cap and (best is None or cost+w<best):stack.append((o,cost+w,depth+1,seen|{o}))
    return best

def valid_path(path,edges,source,target,hops,cap,direction,preds,want):
    if want is None:return path=={}
    if not path or path.get('nodes',[None])[0]!=source or path['nodes'][-1]!=target:return False
    nodes=path['nodes'];rels=path['rels'];costs=path['costs']
    if len(nodes)!=len(rels)+1 or len(rels)!=len(costs) or path['length']!=len(rels):return False
    if hops and len(rels)>hops:return False
    if sum(costs)!=want or path['totalCost']!=want or want>cap:return False
    for a,p,b,w in zip(nodes,rels,nodes[1:],costs):
        if preds and p not in preds:return False
        good=any(pp==p and effective(ww)==w and ((direction in ['out','both'] and (s,o)==(a,b)) or (direction in ['in','both'] and (s,o)==(b,a))) for s,pp,o,ww in edges)
        if not good:return False
    return True

def main():
    started=time.monotonic();c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);e.ledger.disable();e.erase_all();native=e._iris_obj()
    comparisons=[];mism=[];projections=[];public=[];failure=None;completed=0
    try:
        for graph,rows in FIXTURES:
            for s,p,o,w in rows:assert e.create_edge(N(s),p,N(o),weight=w,graph=graph)
            if graph=='wp9:multi':
                cur=c.cursor();cur.execute('INSERT INTO Graph_KG.rdf_edges(graph_id,s,p,o_id,ekey,qualifiers) VALUES(?,?,?,?,?,?)',[graph,N('s'),'R',N('t'),5,json.dumps({'weight':1})]);c.commit();cur.close()
        # Read persisted weights and derive lowest-ekey scalar projection; never
        # treat minimum parallel weight as the native graph being searched.
        projected={};all_edges={}
        for graph,rows in FIXTURES:
            cur=c.cursor();cur.execute("SELECT s,p,o_id,ekey,CASE WHEN qualifiers IS NULL THEN NULL ELSE Graph_KG.JSON_VALUE(qualifiers, '$.weight') END FROM Graph_KG.rdf_edges WHERE graph_id=? ORDER BY edge_id",[graph]);raw=[tuple(r) for r in cur.fetchall()];cur.close()
            keyed={};original=[]
            for s,p,o,k,w in raw:
                weight=None if w is None else float(w);original.append((str(s),str(p),str(o),weight))
                key=(str(s),str(p),str(o));old=keyed.get(key)
                if old is None or int(k)<old[0]:keyed[key]=(int(k),weight)
            gkey=native.classMethodValue('Graph.KG.GraphKey','ForIndex',graph);edges=[];leaves=[]
            for (s,p,o),(k,w) in keyed.items():
                out=native.get('^KG','out',gkey,s,p,o);back=native.get('^KG','in',gkey,o,p,s)
                expected=1 if w is None else w
                agrees=out is not None and back is not None and float(out)==expected and float(back)==expected
                if not agrees:mism.append({'kind':'producer_projection','graph':graph,'triple':[s,p,o],'raw':[out,back],'expected':expected})
                leaves.append({'triple':[s,p,o],'lowest_ekey':k,'sql_weight':w,'out':out,'in':back,'agrees':agrees});edges.append((s,p,o,expected))
            projected[graph]=edges;all_edges[graph]=original;projections.append({'graph':graph,'sql_rows':raw,'leaves':leaves})
        ids=[N(x) for x in ['s','a','b','t','ghost']]
        for graph,_ in FIXTURES:
            edges=projected[graph];count=0
            for source,target,direction,preds,hops,cap in itertools.product(ids,ids,['out','in','both'],[[],['R']],[0,2,3],[0,3,5,99]):
                want=oracle(edges,source,target,hops,cap,direction,preds)
                raw=native.classMethodValue('Graph.KG.Traversal','DijkstraJson',source,target,'weight',cap,hops,direction,json.dumps(preds),graph)
                path=json.loads(str(raw) or '{}')
                raw_cost=native.classMethodValue('Graph.KG.TraversalPaths','DijkstraCost',source,target,cap,direction,json.dumps(preds),graph,hops)
                cost=None if raw_cost is None or str(raw_cost)=='' else float(raw_cost)
                good=cost==want and valid_path(path,edges,source,target,hops,cap,direction,preds,want)
                if not good:mism.append({'kind':'search','graph':graph,'source':source,'target':target,'direction':direction,'preds':preds,'hops':hops,'cap':cap,'want':want,'path':path,'cost':cost})
                if len(comparisons)<30 or (graph=='wp9:a' and source==N('s') and target==N('t')):comparisons.append({'graph':graph,'source':source,'target':target,'hops':hops,'cap':cap,'direction':direction,'preds':preds,'want':want,'path':path,'cost':cost,'agrees':good})
                count+=1;completed+=1
            print(json.dumps({'graph':graph,'paired_search_cases':count,'mismatches':len(mism)}),flush=True)
        for graph,hops,cap in [('wp9:a',0,99),('wp9:a',2,4),('wp9:a',2,5),('wp9:other',2,99),('wp9:norm',0,99),('wp9:multi',0,99),('',0,99)]:
            for cost_only in [False,True]:
                tail='YIELD totalCost RETURN totalCost' if cost_only else 'YIELD path, totalCost RETURN path, totalCost'
                q=f"USE GRAPH '{graph}' CALL ivg.shortestPath.weighted('{N('s')}','{N('t')}','weight',{cap},{hops},'out') "+tail
                r=e.execute_cypher(q,{},raise_on_error=True);want=oracle(projected[graph],N('s'),N('t'),hops,cap,'out',[])
                good=(not r.rows if want is None else len(r.rows)==1 and r.rows[0][-1]==want)
                if not cost_only and want is not None:good=good and valid_path(r.rows[0][0],projected[graph],N('s'),N('t'),hops,cap,'out',[],want)
                public.append({'query':q,'columns':r.columns,'rows':r.rows,'want':want,'agrees':good})
                if not good:mism.append({'kind':'public','query':q,'want':want,'rows':r.rows})
        # Real Python hop-producer mutation followed by unchanged native search.
        import inspect,textwrap
        src=textwrap.dedent(inspect.getsource(em.IRISGraphEngine._proc_ivg_shortestpath_weighted));scope=dict(vars(em));find='max_hops = _int_argument(name, "maxHops", _arg_raw(args[4], parameters), 0) if len(args) > 4 else 10';assert src.count(find)==1
        exec(src.replace(find,'max_hops = 0'),scope)
        q=f"USE GRAPH 'wp9:a' CALL ivg.shortestPath.weighted('{N('s')}','{N('t')}','weight',99,2,'out') YIELD path, totalCost RETURN path, totalCost"
        with patch.object(em.IRISGraphEngine,'_proc_ivg_shortestpath_weighted',scope['_proc_ivg_shortestpath_weighted']):changed=e.execute_cypher(q,{},raise_on_error=True)
        detection={'actual_hop_producer_removed':changed.rows[0][-1]!=oracle(projected['wp9:a'],N('s'),N('t'),2,99,'out',[])}
        if not all(detection.values()):mism.append({'kind':'producer-control','result':changed.rows})
        parallel={'projected_cost':oracle(projected['wp9:multi'],N('s'),N('t'),0,99,'out',[]),'all_keyed_edge_cost':oracle(all_edges['wp9:multi'],N('s'),N('t'),0,99,'out',[]),'disposition':'as-built graph projection, no new product defect/policy assumed'}
    except Exception as ex:failure={'type':type(ex).__name__,'error':str(ex),'trace':traceback.format_exc()};raise
    finally:
        result={'verdict':'AGREES' if failure is None and not mism and len(public)==14 else 'DISAGREES','paired_search_cases':completed,'scheduled_search_cases':5*25*3*2*3*4,'mismatch_count':len(mism),'mismatches':mism[:20],'sampled_searches':comparisons,'projections':projections,'public':public,'failure':failure,'identity_checked':True,'container':h['NAME'],
            'scope':'actual Python ordinary+keyed SQL writers, persisted weights->lowest-ekey out/in scalar projection, actual native DijkstraJson/DijkstraCost, public parser/handler/result plus producer mutant. Independent simple-walk oracle with effective positive small integer weights; stable fixtures only. No general floating/concurrency/native-body proof.',
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'elapsed':time.monotonic()-started}
        if failure is None:result.update(detection=detection,parallel_projection=parallel)
        Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n');c.close()
    print(json.dumps({'verdict':result['verdict'],'paired_search_cases':result['paired_search_cases'],'mismatches':len(mism),'parallel':parallel,'elapsed':result['elapsed']}),flush=True);assert not mism
if __name__=='__main__':main()
