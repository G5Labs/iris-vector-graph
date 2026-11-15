"""Real engine token producer -> store/cache -> score rows; IRIS is substituted."""
import inspect,itertools,json,logging,os,sys,textwrap
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN=bc.import_pin()
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph.stores.iris_sql_store import IRISGraphStore

class Server:
    def __init__(self):
        self.nodes={'a':1,'b':2};self.adj=1;self.cache={};self.census=0;self.computes=0;self.fail=False;self.native=0;self.loops=set()
    def cursor(self):return self
    def execute(self,sql):
        assert 'COUNT(*)' in sql and 'MAX(%ID)' in sql
        if self.fail:raise RuntimeError('injected token failure')
    def fetchone(self):return len(self.nodes),max(self.nodes.values(),default=None)
    def loners(self):self.census+=1;return {n:False for n in self.nodes if n not in ('a','b')}
    def call(self,cls,method,*args):
        assert cls in ('Graph.KG.AlgoCache','Graph.KG.PageRank')
        if method=='Token':return self.adj
        if method=='Lookup':
            e=self.cache.get(args);return f'H{e[0]}|{e[1]}' if e and e[0]==self.adj else f'M{self.adj}'
        if method=='Put':
            g,a,h,t,p=args;self.cache[(g,a,h)]=(int(t),p);return 1
        if method=='PageRankGlobalJson':
            self.computes+=1
            ids=['a','b']+sorted(self.loops)+(json.loads(args[2]) if len(args)>2 else [])
            # Provider fixture, not an ObjectScript execution/numerics oracle.
            return json.dumps([{'id':n,'score':1/len(ids)} for n in sorted(ids)])
        raise AssertionError((cls,method))
    def native_answer(self,*args):self.native+=1;return None

def setup(method=None):
    s=Server();store=IRISGraphStore.__new__(IRISGraphStore)
    store._call_classmethod=s.call;store._native_answer=s.native_answer
    if method:store.execute_pagerank=method.__get__(store)
    e=IRISGraphEngine.__new__(IRISGraphEngine);e.conn=s;e._t=lambda n:'Graph_KG.'+n
    e._store=store;e._store_capabilities={};e._loners=s.loners
    return e,s

def compare(method=None,change=False):
    mism=[];n=0
    for fail,extra,adj_change in itertools.product([False,True],range(4),[False,True]):
        e,s=setup(method);s.fail=fail
        first=e.kg_PAGERANK();c1=s.census
        second=e.kg_PAGERANK();c2=s.census
        want_second=2 if fail else 1
        if c2!=want_second or second!=first:mism.append(['repeat',fail,extra,adj_change,c2,want_second])
        for i in range(extra):s.nodes['c'+str(i)]=3+i
        if adj_change:s.adj+=1
        third=e.kg_PAGERANK();ids=[r[0] for r in third]
        if change and n==0:ids=[]
        if ids!=sorted(s.nodes) or abs(sum(r[1] for r in third)-1)>1e-12:mism.append(['rows',fail,extra,adj_change,ids])
        expected=c2+int(fail or extra>0 or adj_change)
        if s.census!=expected:mism.append(['census',s.census,expected])
        n+=1
    return n,mism

def main():
    logging.getLogger('iris_vector_graph._engine.algorithms').setLevel(logging.ERROR)
    os.environ.pop('IVG_DISABLE_ALGO_CACHE',None)
    n,mism=compare()
    src=textwrap.dedent(inspect.getsource(IRISGraphStore.execute_pagerank));scope=dict(vars(sys.modules[IRISGraphStore.__module__]))
    exec(src.replace('params["nodes"] = node_token','params["nodes"] = "constant"'),scope)
    _,mut=compare(scope['execute_pagerank']);_,changed=compare(change=True)
    # Native eligibility is observed with the actual store, on a cold miss.
    e,s=setup();s.nodes['c']=3;rows=e.kg_PAGERANK();assert s.native==0 and len(rows)==3
    e,s=setup();s.nodes['c']=3;s.loops={'c'};e._loners=lambda:{'c':True}
    loop_rows=e.kg_PAGERANK();assert s.native==1 and len(loop_rows)==3
    e,s=setup();s.nodes={};assert e._node_set_token()=='0:0'
    detection={'constant_node_key_mutant':bool(mut),'changed_rows':bool(changed)}
    out=bc.write_receipt('pagerank_admission',Path(__file__),{'verdict':'AGREES' if not mism and all(detection.values()) else 'DISAGREES',
        'comparisons':n,'mismatch_count':len(mism),'mismatches':mism[:5],'detection':detection,'pin':bc.pin_identity(PIN),
        'domain':'token success/failure x 0..3 added isolates x adjacency unchanged/changed; three actual engine calls per case plus cold-loner Owner eligibility, self-loop-only Native eligibility and empty COUNT:MAX',
        'substituted':'node census SQL result, loner server reader, shared cache and PageRank Owner JSON; actual token producer, engine, parameter hash, cache protocol, store, decoder and consumer execute',
        'numerics':'fixture rows sum to one and are forwarded; actual ObjectScript numerical normalization, float accuracy, 10000 cap and concurrency NOT observed or proved'})
    d=json.loads(out.read_text())
    for f in ['iris_vector_graph/_engine/algorithms.py','iris_vector_graph/stores/iris_sql_store.py','iris_vector_graph/algo_cache.py','iris_vector_graph/_edgeless.py']:
        d['inputs'][f]=bc.sha(PIN/f)
    out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(f"pagerank_admission: {d['verdict']}; {n} journeys; {out}")
    return int(d['verdict']!='AGREES')
if __name__=='__main__':raise SystemExit(main())
