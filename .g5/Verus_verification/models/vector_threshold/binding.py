"""Real node/edge SQL builders and readers against an adapted SQLite provider.
Only TOP and TO_VECTOR type/width syntax are adapted. This is not IRIS evidence.
"""
import inspect,itertools,json,math,re,sqlite3,sys,textwrap
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN=bc.import_pin()
from iris_vector_graph.engine import IRISGraphEngine

def cosine(a,b):
    a=json.loads(a);b=json.loads(b)
    return sum(x*y for x,y in zip(a,b))/math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))

class Cursor:
    def __init__(self,db,seen):self.cur=db.cursor();self.seen=seen
    def execute(self,sql,params):
        self.seen.append((sql,params))
        assert 'HAVING' not in sql and sql.rstrip().endswith('ORDER BY score DESC')
        assert sql.count('?')==len(params)
        top=re.search(r'SELECT TOP (\d+) ',sql).group(1)
        q=re.sub(r'SELECT TOP \d+ ','SELECT ',sql)
        q=re.sub(r'TO_VECTOR\(\?, DOUBLE, \d+\)','TO_VECTOR(?)',q)+' LIMIT '+top
        self.cur.execute(q,params);self.description=self.cur.description
    def fetchall(self):return self.cur.fetchall()
    def close(self):self.cur.close()

def compare(method=None,change=False):
    mism=[];n=0
    for edge,t,k in itertools.product([False,True],[None,0.,0.5,1.],range(1,5)):
        db=sqlite3.connect(':memory:');seen=[]
        db.create_function('TO_VECTOR',1,lambda x:x);db.create_function('VECTOR_COSINE',2,cosine)
        db.execute('CREATE TABLE vectors(id TEXT, s TEXT,p TEXT,o_id TEXT,emb TEXT,graph_id TEXT)')
        for id,v in [('a',[1.,0.]),('b',[0.5,math.sqrt(0.75)]),('c',[0.,1.])]:
            db.execute('INSERT INTO vectors VALUES(?,?,?,?,?,?)',(id,id,'R','z',json.dumps(v),''))
        e=IRISGraphEngine.__new__(IRISGraphEngine);e.vector_dtype='DOUBLE';e.conn=type('Conn',(),{'cursor':lambda self:Cursor(db,seen)})()
        e._t=lambda x:x;e._route_for_read=lambda *a,**kw:('vectors',None)
        if edge:
            rows=e.edge_vector_search([1.,0.],top_k=k,score_threshold=t);ids=[r['s'] for r in rows]
        else:
            fn=method.__get__(e) if method else e.vector_search
            rows=fn('vectors','emb',[1.,0.],top_k=k,score_threshold=t,graph='');ids=[r['id'] for r in rows]
        want=[id for id,score in [('a',1.),('b',0.5),('c',0.)] if t is None or score>=t][:k]
        if change and n==0:ids=[]
        if ids!=want:mism.append([edge,t,k,ids,want])
        sql,params=seen[-1]
        if t is not None and ('>= ?' not in sql or params[-1]!=t):mism.append(['binding',sql,params])
        db.close();n+=1
    return n,mism

def main():
    n,mism=compare();scope=dict(vars(sys.modules[IRISGraphEngine.vector_search.__module__]))
    src=textwrap.dedent(inspect.getsource(IRISGraphEngine.vector_search));exec(src.replace('>= ?', '> ?'),scope)
    _,mut=compare(scope['vector_search']);_,changed=compare(change=True)
    detection={'equality_dropped_mutant':bool(mut),'changed_result':bool(changed)}
    out=bc.write_receipt('vector_threshold',Path(__file__),{'verdict':'AGREES' if not mism and all(detection.values()) else 'DISAGREES',
        'comparisons':n,'mismatch_count':len(mism),'mismatches':mism[:5],'detection':detection,'pin':bc.pin_identity(PIN),
        'domain':'node/edge x omitted/0/0.5/1 threshold x k1..4; three actual cosine rows, equality/below/above',
        'substituted':'route provider fixed to one local table; SQLite executes SQL after TOP-to-LIMIT and TO_VECTOR syntax adaptation, cosine is a Python function; no live IRIS preparation, width validation or cross-graph claim'})
    d=json.loads(out.read_text());d['inputs']['iris_vector_graph/_engine/vector.py']=bc.sha(PIN/'iris_vector_graph/_engine/vector.py')
    out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(f"vector_threshold: {d['verdict']}; {n} SQL/result cases; {out}")
    return int(d['verdict']!='AGREES')
if __name__=='__main__':raise SystemExit(main())
