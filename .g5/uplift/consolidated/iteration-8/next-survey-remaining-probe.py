"""Guarded in-process ordinary weighted wrapper and Bolt result/session survey."""
from __future__ import annotations
import asyncio,copy,hashlib,heapq,inspect,itertools,json,os,socket,subprocess,sys,textwrap,time
from pathlib import Path
from unittest.mock import patch,MagicMock,AsyncMock
from types import SimpleNamespace
GUARD=patch.object(socket.socket,'connect',side_effect=AssertionError('remaining survey prohibits network'))
CONNECT=GUARD.start();os.environ['BOLT_ENABLED']='0';os.environ.pop('IVG_API_KEY',None);os.environ.pop('IVG_READ_ONLY',None)
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN))
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph import engine as em
from iris_vector_graph.result import IVGResult
from iris_vector_graph import bolt_server as bs

class Engine:
    def __init__(self,rows,error=None):
        self.rows=rows;self.error=error;self.calls=[];self.connection_calls=[]
        self.conn=SimpleNamespace(commit=lambda:self.connection_calls.append('commit'),rollback=lambda:self.connection_calls.append('rollback'),cursor=lambda:self.connection_calls.append('cursor'))
    def execute_cypher(self,q,parameters=None):
        self.calls.append((q,parameters));return IVGResult(columns=['v'],rows=copy.deepcopy(self.rows),error=self.error)

def decode(ws):
    out=[]
    for call in ws.send_bytes.call_args_list:
        for m in bs.decode_messages(call.args[0]):
            out.append({'tag':m[1],'fields':bs.PackStream.unpack(m,2)[0] if len(m)>2 else None})
    return out
async def session_trace(rows,operations,error=None):
    engine=Engine(rows,error);ws=AsyncMock();s=bs.BoltSession(ws,lambda:engine);s.state=bs.BoltState.READY;steps=[]
    for tag,fields in operations:
        before=len(ws.send_bytes.call_args_list);await s._dispatch(bs.bolt_message_bytes(tag,*fields))
        steps.append({'input':{'tag':tag,'fields':fields},'output':decode(ws)[before:],'state':str(s.state),'pending':copy.deepcopy(s._pending_result)})
    return {'steps':steps,'engine_calls':engine.calls,'transaction_port_calls':engine.connection_calls,'all_messages':decode(ws)}
def records(trace):return [m['fields'] for m in trace['all_messages'] if m['tag']==bs.TAG_RECORD]

def bolt_probe():
    traces=[]
    for n in [-1,0,1,2,3,4]:
        ops=[(bs.TAG_RUN,('RETURN v',{},{})),(bs.TAG_PULL,({'n':n},)),(bs.TAG_PULL,({'n':1},))]
        t=asyncio.run(session_trace([[1],[2],[3]],ops));want=[[1],[2],[3]][:n] if n>0 else [[1],[2],[3]]
        assert records(t)==want and all('has_more' not in m['fields'] for m in t['all_messages'] if m['tag']==bs.TAG_SUCCESS)
        traces.append({'case':'pull-followup','n':n,**t})
    for command in [bs.TAG_DISCARD,bs.TAG_ROLLBACK,bs.TAG_RESET,bs.TAG_COMMIT]:
        t=asyncio.run(session_trace([[1],[2],[3]],[(bs.TAG_RUN,('RETURN v',{},{})),(command,({'n':1},) if command==bs.TAG_DISCARD else ()),(bs.TAG_PULL,({'n':-1},))]))
        want=[[1],[2],[3]] if command==bs.TAG_COMMIT else []
        assert records(t)==want;traces.append({'case':'pending-competing-writer','command':command,**t})
    t=asyncio.run(session_trace([],[(bs.TAG_RUN,('RETURN v',{},{})),(bs.TAG_PULL,({'n':-1},)),(bs.TAG_ROLLBACK,()),(bs.TAG_RESET,())],error='provider unavailable'))
    assert [m['tag'] for m in t['all_messages']]==[bs.TAG_FAILURE,bs.TAG_IGNORED,bs.TAG_IGNORED,bs.TAG_SUCCESS]
    traces.append({'case':'folded-error-failed-gate-reset','trace':t})
    values=[None,True,3,1.5,'[1]','1e5',{'a':1},[1,2]]
    for v in values:
        t=asyncio.run(session_trace([[v]],[(bs.TAG_RUN,('RETURN v',{},{})),(bs.TAG_PULL,({'n':-1},))]));assert records(t)==[[v]]
        traces.append({'case':'typed-value','input':v,**t})
    for end in [bs.TAG_ROLLBACK,bs.TAG_COMMIT]:
        t=asyncio.run(session_trace([[1]],[(bs.TAG_BEGIN,({},)),(bs.TAG_RUN,('CREATE (n:X)',{},{})),(end,())]))
        assert not t['transaction_port_calls'];traces.append({'case':'explicit-transaction-forwarding','end':end,**t})
    # Mutate the actual record consumer's bounded-slice rule; evaluate the source-derived as-built oracle.
    original=bs.BoltSession._handle_pull;source=textwrap.dedent(inspect.getsource(original));assert source.count('if n > 0:')==1
    ns=dict(vars(bs));exec(source.replace('if n > 0:','if False:'),ns)
    with patch.object(bs.BoltSession,'_handle_pull',ns['_handle_pull']):
        altered=asyncio.run(session_trace([[1],[2],[3]],[(bs.TAG_RUN,('RETURN v',{},{})),(bs.TAG_PULL,({'n':1},))]))
    original_trace=asyncio.run(session_trace([[1],[2],[3]],[(bs.TAG_RUN,('RETURN v',{},{})),(bs.TAG_PULL,({'n':1},))]))
    detection=records(original_trace)==[[1]] and records(altered)!=[[1]]
    assert detection
    return {'traces':traces,'comparisons':len(traces),'actual_pull_consumer_mutation_detected':detection,'protocol_violation':'Known F-1602: PULL n>0 drops suffix and omits has_more; not a new defect','txn_limit':'actual Bolt makes no transaction calls to named spy port; no live DB rollback/commit executed'}

def weighted_probe():
    out=[];path={'nodes':['s','a','t'],'rels':['R','R'],'costs':[4.0,1.0],'length':2,'totalCost':5.0}
    for graph,hops,cost_only,direction in itertools.product([None,'g'],[0,2,3],[False,True],['out','in','both']):
        calls=[];e=IRISGraphEngine(MagicMock(),native_cypher=False);e._graphs_with_edges=lambda:['g0','g1']
        def port(conn,cls,method,*args):calls.append((cls,method,args));return '5' if method=='DijkstraCost' else json.dumps(path)
        query=(f"USE GRAPH '{graph}' " if graph is not None else '')+f"CALL ivg.shortestPath.weighted($s, $t, 'weight', 20, {hops}, '{direction}') YIELD "+('totalCost RETURN totalCost' if cost_only else 'path, totalCost RETURN path, totalCost')
        with patch.object(em,'_call_classmethod',port):r=e.execute_cypher(query,{'s':'s','t':'t'},raise_on_error=True)
        assert len(calls)==(2 if graph is None else 1)
        for _,method,args in calls:
            assert method==('DijkstraCost' if cost_only else 'DijkstraJson')
            assert args[:2]==('s','t') and (args[-1] if cost_only else args[4])==hops
        assert all(row[-1]==5.0 for row in r.rows)
        out.append({'query':query,'port_calls':calls,'columns':r.columns,'rows':r.rows})
    return {'comparisons':len(out),'cases':out,'scope':'actual parser/handler/route/projection with recorded algorithm response; NOT execution of native numerical search'}

# Separate source-transcription sanity check. This does not execute ObjectScript.
def dijkstra_twin(edges,bound,hop_state=True):
    pq=[(0,'s',0)];seen={};dist={('s',0):0}
    while pq:
        cost,u,h=heapq.heappop(pq)
        if u in seen and (seen[u]<=h if hop_state else True):continue
        seen[u]=h
        if u=='t':return cost
        if bound and h>=bound:continue
        nxt=h+1 if bound else 0
        for a,b,w in edges:
            if a!=u:continue
            if b in seen and (seen[b]<=nxt if hop_state else True):continue
            ncost=cost+(w if w>0 else 1)
            key=(b,nxt if hop_state else 0)
            if key not in dist or ncost<dist[key]:dist[key]=ncost;heapq.heappush(pq,(ncost,b,nxt))
    return None

def main():
    start=time.monotonic();b=bolt_probe();w=weighted_probe()
    edges=[('s','a',4),('s','b',1),('b','a',1),('a','t',1)]
    sanity={'unbounded':dijkstra_twin(edges,0),'bounded2':dijkstra_twin(edges,2),'node_only_mutant':dijkstra_twin(edges,2,False),'scope':'unverified source-shaped Python transcription; not actual algorithm/native/model proof'}
    assert sanity['unbounded']==3 and sanity['bounded2']==5 and sanity['node_only_mutant'] is None
    repo=Path(__file__).resolve().parents[4];files=['iris_vector_graph/bolt_server.py','iris_vector_graph/engine.py','iris_vector_graph/_engine/query.py','iris_src/src/Graph/KG/TraversalPaths.cls','iris_src/src/Graph/KG/Traversal.cls']
    identities={}
    for f in files:
        blob=subprocess.check_output(['git','-C',str(repo),'rev-parse','3eaa79cf:'+f],text=True).strip();have=subprocess.check_output(['git','hash-object',str(PIN/f)],text=True).strip();assert blob==have
        identities[f]={'sha256':hashlib.sha256((PIN/f).read_bytes()).hexdigest(),'equal_pin_blob':True}
    result={'product_pin':'3eaa79cf77d3e0a879b2cced634cf2729d81499e','bolt':b,'weighted_wrapper':w,'weighted_source_sanity':sanity,'source_identities':identities,'network_connect_calls':CONNECT.call_count,'elapsed':time.monotonic()-start,'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    assert CONNECT.call_count==0;Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'bolt_comparisons':b['comparisons'],'weighted_wrapper_comparisons':w['comparisons'],'sanity':sanity,'network':CONNECT.call_count,'elapsed':result['elapsed']}))
if __name__=='__main__':main()
