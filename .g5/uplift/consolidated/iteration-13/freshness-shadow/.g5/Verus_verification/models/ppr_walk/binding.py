"""Actual pinned Python PPR over SQLite; separate ObjectScript source-shaped port.
No native IRIS, socket, cache correctness, arbitrary numeric or collation proof.
"""
from __future__ import annotations
import copy,hashlib,importlib.util,inspect,itertools,json,re,socket,sqlite3,subprocess,sys,textwrap,time
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path
from types import MethodType,SimpleNamespace
from unittest.mock import patch
sys.dont_write_bytecode=True
GUARD=patch.object(socket.socket,'connect',side_effect=AssertionError('ppr binding forbids network'));CONNECT=GUARD.start()
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('ppr_binding_common',HERE.parents[1]/'tools/binding_common.py');bc=importlib.util.module_from_spec(sp);sp.loader.exec_module(bc);PIN=bc.import_pin()
from iris_vector_graph._engine import algorithms as am
from iris_vector_graph._collation import rank_key
from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
from iris_vector_graph.result import IVGResult
FALLBACK_SRC=textwrap.dedent(inspect.getsource(am.AlgorithmsMixin._kg_PERSONALIZED_PAGERANK_python_fallback)).splitlines()
CHECK_OFFSET=next(i for i,line in enumerate(FALLBACK_SRC) if line.strip()=="if change < held * tolerance:")
def trace_equal(observed,want):
    return len(observed)==len(want) and all(a["held"]==b["held"] and abs(a["change"]-float(F(b["change"])))<2e-11 and abs(a["mass"]-float(F(b["mass"])))<2e-11 for a,b in zip(observed,want))
CANON=re.compile(r'(?:0|-?(?:[1-9][0-9]*(?:\.[0-9]*[1-9])?|\.[0-9]*[1-9]))\Z')
def idkey(s):return (0,Decimal(s),'') if CANON.fullmatch(str(s)) else (1,Decimal(0),str(s))
def q12(x):
    z=F(x)*10**12;n,r=divmod(z.numerator,z.denominator)
    return n+int(2*r>z.denominator or (2*r==z.denominator and n%2))
def k(row):return (-q12(row[1]),idkey(row[0]))
def excluded(es,s,p):
    for e in es or []:
        if '.' not in e and e==p:return True
        if '.' in e:
            typ,pred=e.split('.')
            if pred==p and s.startswith(typ+'/'):return True
    return False

def physical(edges,g,ex):
    return [(s,p,d) for gg,s,p,d,n in edges if gg==g and not excluded(ex,s,p) for _ in range(1 if n is None else n)]

def exact(nodes,edges,seeds,g,a,it,tol,rev=False,w=1,ex=None):
    """Independent gather recurrence on physical relational rows, exact fractions.
    Rebuilds degrees each iteration; no source sparse map, cached divisor or matrix.
    """
    ns=[n for gg,n in nodes if gg==g];ss=set(seeds)&set(ns)
    if not ss:return {},[]
    arcs=[(u,v,F(1)) for u,p,v in physical(edges,g,ex)]
    if rev and F(w)>0:arcs +=[(v,u,F(w)) for u,p,v in physical(edges,g,ex)]
    r={n:F(int(n in ss),len(ss)) for n in ns};trace=[];a=F(a);tol=F(tol)
    for _ in range(it):
        degree={u:sum(s==u for s,t,weight in arcs) for u in ns}
        dangling=sum((r[n] for n in ns if not degree[n]),F())
        nr={t:((1-a+a*dangling)/len(ss) if t in ss else F())+sum((a*weight*r[s]/degree[s] for s,v,weight in arcs if v==t and degree.get(s,0)),F()) for t in ns}
        change=sum((abs(nr[n]-r[n]) for n in ns),F());held=sum(bool(v) for v in nr.values());trace.append({'change':str(change),'held':held,'mass':str(sum(nr.values()))});r=nr
        if change<held*tol:break
    return r,trace

def expected(nodes,r,g,top,cap=1000,producer_cap=1000,mode='fast'):
    if mode=='fallback':ranked=sorted(r.items(),key=k)
    else:
        ranked=sorted(((n,v) for n,v in r.items() if v),key=k)
        if producer_cap>0:ranked=ranked[:producer_cap]
        if not ranked:return []
        have={n for n,v in ranked};ranked += [(n,F()) for n in sorted((n for gg,n in nodes if gg==g and n not in have),key=idkey)]
    limit=(top if top is not None and top>0 else cap) if mode=='fast' else (top if top is not None and top>0 else 0)
    return ranked[:limit] if limit else ranked

def equal(actual,want):
    got=list(actual.items()) if isinstance(actual,dict) else list(actual)
    return [n for n,v in got]==[n for n,v in want] and all(type(v) is float and abs(v-float(w))<2e-11 for (_,v),(_,w) in zip(got,want))

class Cursor:
    def __init__(self,db,owner):self.cur=db.cursor();self.owner=owner
    def execute(self,sql,args=None):
        self.owner.reads.append((sql,list(args or [])))
        if self.owner.fault and self.owner.fault in sql:raise RuntimeError('named SQLite read failure')
        top=re.match(r'(SELECT) TOP (\d+) (.*)',sql,re.I|re.S)
        if top:sql='SELECT '+top.group(3)+' LIMIT '+top.group(2)
        if 'ORDER BY node_id' in sql:sql=sql.replace('ORDER BY node_id','ORDER BY node_id COLLATE IRIS_ID')
        self.cur.execute(sql,list(args or []));return self
    def fetchall(self):return self.cur.fetchall()
    def fetchone(self):return self.cur.fetchone()
    def close(self):self.cur.close();self.owner.closed+=1
class Relational:
    """SQLite executes all fallback/node-reader SELECTs; TOP and collation adapter explicit."""
    def __init__(self,nodes,edges):
        self.db=sqlite3.connect(':memory:');self.reads=[];self.closed=0;self.fault=None
        self.db.create_collation('IRIS_ID',lambda a,b:(idkey(a)>idkey(b))-(idkey(a)<idkey(b)))
        self.db.execute('CREATE TABLE nodes(graph_id TEXT NOT NULL,node_id TEXT NOT NULL,PRIMARY KEY(graph_id,node_id))')
        self.db.execute('CREATE TABLE rdf_edges(graph_id TEXT,s TEXT,p TEXT,o_id TEXT,ekey INTEGER)')
        self.db.executemany('INSERT INTO nodes VALUES(?,?)',nodes)
        self.db.executemany('INSERT INTO rdf_edges VALUES(?,?,?,?,?)',[(g,s,p,d,j) for g,s,p,d,n in edges for j in range(1 if n is None else n)])
    def cursor(self):return Cursor(self.db,self)
    def close(self):self.db.close()

class SourcePort:
    """PageRank.Run/RunJson sparse-map transcription, never an IRIS execution.
    raw_edges are (graph,source,predicate,target,optional stored # multiplicity).
    degree_provider normal mode names Adj.Degree==raw-multiplicity provider premise;
    exclusion counts directly, as source. Complete mirrored in/out lists assumed.
    """
    def __init__(self,nodes,edges,mutant=None,degree_provider=None):
        self.nodes=nodes;self.edges=edges;self.mutant=mutant;self.degree_provider=degree_provider;self.calls=[];self.traces=[];self.last_sparse=[]
    def classMethodValue(self,cls,method,*args):
        self.calls.append((cls,method,list(args)))
        if self.mutant=='missing':raise RuntimeError('<METHOD DOES NOT EXIST> *RunJson,Graph.KG.PageRank')
        if self.mutant=='internal':raise RuntimeError('<PARAMETER>RunJson^Graph.KG.PageRank')
        assert (cls,method)==('Graph.KG.PageRank','RunJson')
        seed,a,steps,bidir,w,g,*tail=args;a=float(a);steps=int(steps);bidir=int(bidir);w=float(w)
        ex=json.loads(tail[0]) if tail and tail[0] else [];cap=int(tail[1]) if len(tail)>1 else 1000;tol=float(tail[2]) if len(tail)>2 else 1e-6
        members={n for gg,n in self.nodes if gg==g};ss=set(json.loads(seed))&members
        if not ss:return '[]'
        r={s:1./len(ss) for s in sorted(ss,key=idkey)};want_rev=bidir and w>0;degree={};trace=[]
        kept=[e for e in self.edges if e[0]==g and not excluded(ex,e[1],e[2])]
        for iteration in range(steps):
            nr={};dangling=0.
            for node in sorted(r,key=idkey):
                rank=r[node]
                forward=[e for e in kept if e[1]==node];back=[e for e in kept if e[3]==node] if want_rev else []
                if node not in degree:
                    count=lambda e:1 if e[4] is None else e[4]
                    fd=sum(count(e) for e in forward)
                    if self.degree_provider and not ex:fd=self.degree_provider(g,node,fd)
                    degree[node]=fd+sum(count(e) for e in back)
                    if self.mutant=='weighted-divisor':degree[node]=fd+w*sum(count(e) for e in back)
                deg=degree[node]
                if not deg:
                    dangling += rank
                    continue
                share=a*rank/deg
                for gg,s,p,d,n in forward:nr[d]=nr.get(d,0.)+share*(1 if n is None or self.mutant=='drop-multiplicity' else n)
                for gg,s,p,d,n in back:nr[s]=nr.get(s,0.)+a*w*rank/deg*(1 if n is None else n)
            restart=((1-a)+(0 if self.mutant=='drop-dangling' else a*dangling))/len(ss)
            for s in sorted(ss,key=idkey):nr[s]=nr.get(s,0.)+restart
            change=sum(abs(v-r.get(n,0.)) for n,v in nr.items())+sum(abs(v) for n,v in r.items() if n not in nr)
            held=sum(v!=0 for v in nr.values());trace.append({'change':change,'held':held,'mass':sum(nr.values())});r=nr
            if change<held*tol:break
        ranked=sorted(r.items(),key=lambda x:rank_key(*x));self.last_sparse=ranked;self.traces.append(trace)
        if cap>0:ranked=ranked[:cap]
        return json.dumps([{'id':n,'score':v} for n,v in ranked])

class StoreProvider:
    """Actual _execute_ppr body; cache admission and Native Reader deliberately ports."""
    def __init__(self,port):self.port=port;self.native_calls=[]
    def _native_answer(self,*args):self.native_calls.append(args[0]);return None
    def _call_classmethod(self,*args):return self.port.classMethodValue(*args)
    execute_ppr=IRISGraphStore._execute_ppr

def engine(rel,port,route):
    o=SimpleNamespace(conn=rel,_t=lambda t:t,_store_capabilities={'ppr':route=='store'},capabilities=SimpleNamespace(objectscript_deployed=route!='fallback',kg_built=True),_iris_obj=lambda:port)
    o._store=StoreProvider(port)
    for n in ['_ppr_every_node','_kg_PERSONALIZED_PAGERANK_python_fallback','kg_PERSONALIZED_PAGERANK','ppr']:setattr(o,n,MethodType(getattr(am.AlgorithmsMixin,n),o))
    return o

def run(nodes,edges,seeds,g='',a=F(1,2),steps=1,tol=0,rev=False,w=1,ex=None,top=None,route='fallback',port_mutant=None,method=None,degree_provider=None):
    rel=Relational(nodes,edges);port=SourcePort(nodes,edges,port_mutant,degree_provider);o=engine(rel,port,route)
    if method:setattr(o,method[0],MethodType(method[1],o))
    observed=[];target=o._kg_PERSONALIZED_PAGERANK_python_fallback.__func__.__code__;oldtrace=sys.gettrace()
    def tracer(frame,event,arg):
        if frame.f_code is target and event=='line' and frame.f_lineno==target.co_firstlineno+CHECK_OFFSET:
            local=frame.f_locals;observed.append({'change':local['change'],'held':local['held'],'mass':sum(local['ranks'].values())})
        return tracer
    try:
        sys.settrace(tracer)
        got=o.kg_PERSONALIZED_PAGERANK(seeds,damping_factor=float(a),max_iterations=steps,tolerance=float(tol),return_top_k=top,bidirectional=rev,reverse_edge_weight=float(w),graph=g,exclude_predicates=ex)
        sys.settrace(oldtrace)
        r,trace=exact(nodes,edges,seeds,g,F(a),steps,F(tol),rev,F(w),ex)
        used='fallback' if route=='fallback' or port_mutant=='missing' else 'fast'
        pcap=(top or 0) if ex is not None else 1000
        want=expected(nodes,r,g,top,None if ex is not None else 1000,pcap,used)
        observed=observed if used=='fallback' else (port.traces[0] if port.traces else [])
        return {'agrees':equal(got,want) and trace_equal(observed,trace),'observed_iteration_trace':observed,'got':list(got.items()),'expected':[(n,str(v)) for n,v in want],'source_trace':port.traces,'exact_trace':trace,'provider_calls':port.calls,'reads':rel.reads,'closed_cursors':rel.closed,'mode':used}
    finally:sys.settrace(oldtrace);rel.close()

def mutate(name,find,replace):
    source=textwrap.dedent(inspect.getsource(getattr(am.AlgorithmsMixin,name)));assert source.count(find)==1,(name,find)
    ns=dict(vars(am));exec(source.replace(find,replace),ns);return name,ns[name]

def panels():
    base=[('',n) for n in ['s','t','0','9','10','07','Type/a']]+[('other',n) for n in ['s','t','extra']]
    edges=[('','s','R','t',None),('','s','S','t',2),('','t','R','Type/a',None),('other','s','R','extra',3)]
    profiles=[{},dict(tol=F(-1,100),steps=3),dict(seeds=['s','s']),dict(seeds=['s','missing']),dict(seeds=['missing']),dict(seeds=['s','t']),dict(seeds=['t']),dict(steps=20,tol=F(1,10**6)),dict(steps=20,tol=10),dict(steps=5,tol=F(2,5)),dict(a=F(17,20),steps=5),dict(rev=True,w=0),dict(rev=True,w=F(1,2)),dict(rev=True,w=1),dict(rev=True,w=2),dict(ex=[]),dict(ex=['R']),dict(ex=['Type.R']),dict(top=1),dict(top=2),dict(top=0),dict(top=-1),dict(top=5),dict(g='other'),dict(g='absent')]
    for route,prof in itertools.product(['fallback','fast','store'],profiles):
        kw=dict(seeds=['s'],g='',a=F(1,2),steps=2,tol=0,route=route);kw.update(prof)
        yield 'ordinary-'+route+'-'+str(prof),base,edges,kw
    for ab,ba,seeds,rev,w,route in itertools.product([0,1,2],[0,1,2],[['a'],['b'],['a','a','b'],['missing']], [False,True],[1,2],['fallback','fast','store']):
        if not rev and w==2:continue
        ns=[('',n) for n in ['a','b','unreached']]+[('other','a'),('other','b')]
        es=([('','a','R','b',ab)] if ab else [])+([('','b','R','a',ba)] if ba else [])+[('other','a','R','b',9)]
        yield 'small-'+str((ab,ba,seeds,rev,w,route)),ns,es,dict(seeds=seeds,a=F(3,4),steps=3,tol=0,rev=rev,w=w,route=route)
    for a,zero,top,route in itertools.product([F(1,10**13),F(1,10**11)],['0','z'],[None,1,2],['fallback','fast','store']):
        yield 'tie-'+str((a,zero,top,route)),[('',n) for n in ['seed','tiny',zero]],[('','seed','R','tiny',None)],dict(seeds=['seed'],a=a,steps=1,tol=0,top=top,route=route)
    for prof in [dict(seeds=['s']),dict(seeds=['s'],a=F(1,10**13),steps=1,top=2),dict(seeds=['missing'])]:
        yield 'public-class-missing-'+str(prof),base,edges,dict(route='fast',port_mutant='missing',**prof)
    seeds=[f'n{i:04d}' for i in range(1002)];ns=[('',n) for n in seeds]
    for ex,top,route in itertools.product([None,[]],[1000,1002],['fallback','fast','store']):
        yield 'cap-'+str((ex,top,route)),ns,[],dict(seeds=seeds,a=F(1,2),steps=1,tol=0,top=top,route=route,ex=ex)

def summary(r):
    return {**{k:v for k,v in r.items() if k not in ['got','expected','reads','provider_calls']},'rows':len(r['got']),'got_head':r['got'][:5],'got_tail':r['got'][-3:],'zeros':sum(v==0 for n,v in r['got']),'read_count':len(r['reads']),'provider_count':len(r['provider_calls']),'provider_arg_shapes':[[c,m,len(args)] for c,m,args in r['provider_calls']]}

def error_cases():
    ns=[('','a'),('','b')];es=[('','a','R','b',None)];out=[]
    for route,mut,expected_error in [('fast','missing',None),('fast','internal','RuntimeError'),('store','internal','RuntimeError'),('store','missing','RuntimeError')]:
        rel=Relational(ns,es);port=SourcePort(ns,es,mut);o=engine(rel,port,route)
        try:
            got=o.kg_PERSONALIZED_PAGERANK(['a'],damping_factor=.5,max_iterations=2,tolerance=0)
            r,_=exact(ns,es,['a'],'',F(1,2),2,0);good=expected_error is None and equal(got,expected(ns,r,'',None,mode='fallback'))
            name='value'
        except Exception as exc:good=type(exc).__name__==expected_error;name=type(exc).__name__
        out.append({'route':route,'provider':mut,'outcome':name,'agrees':good,'sql_reads':len(rel.reads),'provider_calls':len(port.calls)})
        rel.close()
    for fault in ['FROM nodes','FROM rdf_edges']:
        rel=Relational(ns,es);rel.fault=fault;o=engine(rel,SourcePort(ns,es),'fallback')
        try:o.kg_PERSONALIZED_PAGERANK(['a']);good=False
        except RuntimeError as exc:good=str(exc)=='named SQLite read failure' and rel.closed==1
        out.append({'read_fault':fault,'agrees':good,'closed':rel.closed});rel.close()
    return out

def refusal_cases():
    ns=[('','a')];rel=Relational(ns,[]);o=engine(rel,SourcePort(ns,[]),'fallback');out=[]
    checks=[({'seed_entities':[]},'ValueError'),({'seed_entities':'a'},'TypeError'),({'seed_entities':[3]},'TypeError'),({'damping_factor':0},'ValueError'),({'damping_factor':1},'ValueError'),({'damping_factor':True},'ValueError'),({'damping_factor':float('nan')},'ValueError'),({'damping_factor':'0.5'},'ValueError'),({'max_iterations':0},'ValueError'),({'max_iterations':1.5},'ValueError'),({'max_iterations':True},'ValueError'),({'reverse_edge_weight':-1},'ValueError'),({'exclude_predicates':['a.b.c']},'ValueError')]
    for kw,kind in checks:
        args={'seed_entities':['a'],**kw};before=len(rel.reads)
        try:o.kg_PERSONALIZED_PAGERANK(**args);good=False;got='value'
        except Exception as exc:got=type(exc).__name__;good=got==kind and len(rel.reads)==before
        out.append({'input':repr(kw),'outcome':got,'agrees':good})
    rel.close();return out

def detections():
    ns=[('',n) for n in ['a','b','0']];es=[('','a','R','b',2)];out={}
    variants=[('duplicate-seeds','_kg_PERSONALIZED_PAGERANK_python_fallback','seed_set = set(valid_seeds)','seed_set = valid_seeds',dict(seeds=['a','a','b'])),
      ('dangling-mass-lost','_kg_PERSONALIZED_PAGERANK_python_fallback','+ damping_factor * dangling','+ 0.0 * dangling',dict(seeds=['b'])),
      ('multiplicity-divisor-doubled','_kg_PERSONALIZED_PAGERANK_python_fallback','out_degree[src] = out_degree.get(src, 0) + 1','out_degree[src] = out_degree.get(src, 0) + 2',dict(seeds=['a'])),
      ('held-count-total-nodes','_kg_PERSONALIZED_PAGERANK_python_fallback','held += rank != 0.0','held += 1',dict(seeds=['a'],steps=5,tol=F(2,5))),
      ('tiny-sort-zeros-with-scored','_ppr_every_node','return dict(ranked + [(v, 0.0) for v in unscored])','return dict(sorted(ranked + [(v, 0.0) for v in unscored], key=lambda x: rank_key(x[0], x[1])))',dict(seeds=['a'],a=F(1,10**13),route='fast',top=3)),
      ('zero-completion-removed','_ppr_every_node','return dict(ranked + [(v, 0.0) for v in unscored])','return dict(ranked)',dict(seeds=['a'],route='fast',top=3))]
    for name,owner,find,repl,kw in variants:
        profile=dict(seeds=['a'],steps=1,tol=0,route='fallback');profile.update(kw)
        baseline=run(ns,es,**profile);changed=run(ns,es,**profile,method=mutate(owner,find,repl));out['actual-Python-'+name]=baseline['agrees'] and not changed['agrees']
    for name,kw in [('drop-dangling',dict(seeds=['b'])),('weighted-divisor',dict(seeds=['b'],rev=True,w=2)),('drop-multiplicity',dict(seeds=['a']))]:
        base=run(ns,es,route='fast',**kw);bad=run(ns,es,route='fast',port_mutant=name,**kw);out['source-port-'+name]=base['agrees'] and not bad['agrees']
    sample=run(ns,es,seeds=['a'],route='fast');observed=copy.deepcopy(sample['got']);observed[0]=(observed[0][0],observed[0][1]+.125)
    want=[(n,F(v)) for n,v in sample['expected']]
    out['altered-final-score-rejected']=sample['agrees'] and not equal(observed,want)
    # Adverse Degree state, explicitly a provider-state variation rather than a writer trigger or new defect.
    base=run(ns,es,seeds=['a'],route='fast');stale=run(ns,es,seeds=['a'],route='fast',degree_provider=lambda g,n,degree:degree+1 if n=='a' else degree)
    boundary={'correct_provider_agrees':base['agrees'],'stale_provider_agrees':stale['agrees'],'stale_output':stale['got'],'expected':stale['expected'],'claim':'premise sensitivity only; no native Degree/cache execution or ordinary-trigger claim'}
    assert boundary['correct_provider_agrees'] and not boundary['stale_provider_agrees']
    return out,boundary

def wrapper_cases():
    ns=[('',n) for n in ['s','t','0']];es=[('','s','R','t',None)];out=[]
    for route,seed in itertools.product(['fallback','fast','store'],['s',['s'],('s','t')]):
        rel=Relational(ns,es);port=SourcePort(ns,es);o=engine(rel,port,route)
        got=o.ppr(seed,alpha=.5,max_iter=2,top_k=3)['scores'];seeds=[seed] if isinstance(seed,str) else list(seed)
        r,_=exact(ns,es,seeds,'',F(1,2),2,F(1,10**6));want=expected(ns,r,'',3,mode='fallback' if route=='fallback' else 'fast')
        want=sorted(want,key=lambda x:-x[1]);actual=[(x['id'],x['score']) for x in got]
        out.append({'route':route,'seed':repr(seed),'agrees':equal(actual,want),'rows':got});rel.close()
    return out

def supplement(receipt):
    """Read-only hash/shape audit of root-owned native facts, no replay counted."""
    folder=bc.REPO/'.g5/uplift/consolidated/iteration-10';facts={}
    for kind,count in [('tie',6),('cap',4)]:
        stem=folder/('root-ppr-'+kind+'-native');probe=json.loads(stem.with_suffix('.json').read_text());facts[kind]=probe
        assert probe['completed_cases']==probe['scheduled_cases']==count and probe['failure'] is None and probe['identity_checked']
        assert all(x['source_prediction_agrees'] for x in probe['cases'])
        if kind=='tie':
            assert [x['routes_same_selected_order'] for x in probe['cases']]==[False,False,True,True,True,True]
            for case in probe['cases']:
                a=F(str(case['alpha']));zero=case['zero_id'];top=case['top_k'];ns=[('',n) for n in ['s:seed','t:tiny',zero]];r={'s:seed':1-a,'t:tiny':a,zero:F()}
                assert equal(case['native'],expected(ns,r,'',top)) and equal(case['public_store'],expected(ns,r,'',top))
                assert equal(case['python_fallback'],expected(ns,r,'',top,mode='fallback'))
        else:
            assert probe['persisted_node_count']==1002 and probe['all_nodes_are_valid_seeds']
            assert [x['row_count'] for x in probe['cases']]==[1002,1002,1000,1002]
            assert [len(x['zero_ids']) for x in probe['cases']]==[2,0,0,0]
            assert [x['positive_count'] for x in probe['cases']]==[1000,1002,1000,1002]
            for case in probe['cases']:
                assert all(abs(v-(0 if n in case['zero_ids'] else 1/1002))<2e-11 for n,v in case.get('samples',[]))
        prov=folder/('root-ppr-'+kind+'-provenance.json');provenance=json.loads(prov.read_text());assert all(x['all_equal'] for x in provenance['source_identities'].values())
        for raw,digest in provenance['inputs'].items():assert bc.sha(bc.REPO/raw)==digest,(kind,raw)
        for p in [stem.with_suffix('.py'),stem.with_suffix('.json'),stem.with_suffix('.log'),prov,folder/('root-ppr-'+kind+'-predictions.md')]:receipt['inputs'][str(p.relative_to(bc.REPO))]=bc.sha(p)
        for raw,digest in provenance['inputs'].items():receipt['inputs'][raw]=digest
    old=bc.REPO/'.g5/uplift/consolidated/iteration-9/next-survey-ppr-native.json';p5=json.loads(old.read_text());assert p5['identity_checked'] and p5['agrees'] and len(p5['cases'])==5
    for case,mass in zip(p5['cases'],[1,1,.75,1,1.5]):
        assert case['agrees'] and case['native_mass']==case['python_mass']==mass
        assert case['native']==case['python']==case['source_prediction']
    for raw,digest in {**p5['inputs'],**p5['source_inputs']}.items():
        target=Path(raw) if Path(raw).is_absolute() else bc.REPO/raw;assert bc.sha(target)==digest
        receipt['inputs'][str(target.relative_to(bc.REPO))]=digest
    for suffix in ['.py','.json','.log']:
        p=old.with_suffix(suffix);receipt['inputs'][str(p.relative_to(bc.REPO))]=bc.sha(p)
    facts['reverse5']=p5
    return facts

def main():
    started=time.monotonic();cases=[];mismatch=[]
    for name,ns,es,kw in panels():
        r=run(ns,es,**kw);cases.append({'name':name,**summary(r)})
        if not r['agrees']:mismatch.append({'name':name,**r})
    errors=error_cases();refusals=refusal_cases();wrappers=wrapper_cases();detection,boundary=detections()
    native_meta={"inputs":{}};native=supplement(native_meta)
    ident=bc.pin_identity(PIN)
    source_names=['iris_vector_graph/_engine/algorithms.py','iris_vector_graph/_collation.py','iris_vector_graph/stores/iris_sql_store.py','iris_src/src/Graph/KG/PageRank.cls','iris_src/src/Graph/KG/Adj.cls','iris_vector_graph/result.py']
    for name in source_names:
        want=subprocess.check_output(['git','-C',str(bc.REPO),'rev-parse',bc.PIN+':'+name],text=True).strip();have=subprocess.check_output(['git','hash-object',str(PIN/name)],text=True).strip();ident['files_equal_pin_blobs'][name]=want==have;ident['all_equal'] &= want==have
    verdict='AGREES' if not mismatch and all(x['agrees'] for x in errors+refusals+wrappers) and all(detection.values()) and ident['all_equal'] and CONNECT.call_count==0 else 'DISAGREES'
    out=bc.write_receipt('ppr_walk',Path(__file__),{'verdict':verdict,'cases':len(cases),'mismatch_count':len(mismatch),'mismatches':mismatch[:3],'observations':cases,'error_neighbors':errors,'refused_neighbors':refusals,'wrapper_reader_cases':wrappers,'detection':detection,'degree_provider_boundary':boundary,'blocked_socket_calls':CONNECT.call_count,'pin':ident,'elapsed':time.monotonic()-started,'scope':'Actual public Python dispatcher, fallback SQL arithmetic, _execute_ppr, every-node/top-k and ppr result reader over executing SQLite plus explicit PageRank source-port/native-answer/cache providers. Finite float correspondence only; native supplements observed by root, no native execution here.'})
    d=json.loads(out.read_text());d['inputs'][str((HERE/'model.json').relative_to(bc.REPO))]=bc.sha(HERE/'model.json')
    for name in source_names:d['inputs'][name]=bc.sha(PIN/name)
    d['inputs'].update(native_meta['inputs']);d['root_native_supplements']={k:{'count':len(v['cases']),'scope':v['scope']} for k,v in native.items()}
    out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps({'verdict':verdict,'cases':len(cases),'mismatches':mismatch[:1],'errors':errors,'detection':detection,'elapsed':time.monotonic()-started,'receipt':str(out)},default=str));return int(verdict!='AGREES')
if __name__=='__main__':raise SystemExit(main())
