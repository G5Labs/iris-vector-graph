"""Real Python edge writers, SQL guards, duplicate handler and edge_count on SQLite.

Txn SQL functions, IRIS dialect, callbacks, ledger and catalog probes are adapted;
this is finite transcription agreement, not an IRIS or concurrent execution proof.
"""
import inspect,itertools,json,logging,sqlite3,sys,textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN_DIR=bc.import_pin()
from iris_vector_graph._engine import nodes_edges as ne

class Cursor:
    def __init__(self,conn): self.conn=conn;self.cur=conn.db.cursor();self.rows=None
    def execute(self,sql,params=()):
        self.rows=None
        if '.Txn_Begin(' in sql:
            self.conn.db.execute('SAVEPOINT ivg');self.rows=[(1,)];return self
        if '.Txn_End(' in sql:
            self.conn.db.execute('RELEASE ivg');self.rows=[(0,)];return self
        if '.Txn_Undo(' in sql:
            self.conn.db.execute('ROLLBACK TO ivg');self.conn.db.execute('RELEASE ivg');self.rows=[(0,)];return self
        # Engine table names are supplied without a schema; only the row-id spelling differs.
        self.cur.execute(sql.replace('%ID','id'),params);return self
    @property
    def rowcount(self):return self.cur.rowcount
    def fetchone(self):return self.rows.pop(0) if self.rows else self.cur.fetchone()
    def fetchall(self):return list(self.rows) if self.rows is not None else self.cur.fetchall()
    def close(self):self.cur.close()

class Connection:
    autocommit=True
    def __init__(self):
        self.db=sqlite3.connect(':memory:',isolation_level=None)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('CREATE TABLE nodes(node_id TEXT,graph_id TEXT,PRIMARY KEY(graph_id,node_id))')
        self.db.execute('CREATE TABLE rdf_edges(id INTEGER PRIMARY KEY,s TEXT,p TEXT,o_id TEXT,qualifiers TEXT,graph_id TEXT,ekey INTEGER DEFAULT 0,UNIQUE(s,p,o_id,graph_id,ekey),FOREIGN KEY(graph_id,s) REFERENCES nodes(graph_id,node_id),FOREIGN KEY(graph_id,o_id) REFERENCES nodes(graph_id,node_id),CHECK(p != "REFUSE"))')
    def cursor(self):return Cursor(self)

def observe(api,graph,indexed,initial,refused=False,mutant=None,incoming_marker=False):
    c=Connection(); e=ne.NodesEdgesMixin.__new__(ne.NodesEdgesMixin)
    e.conn=c;e._ivg_schema='Graph_KG';e._t=lambda name:name
    e._nodes_has_graph_id=True;e._adjacency_indexed=indexed;e._ekey_guard_cached=' AND ekey = 0'
    e._bulk_sql=lambda kind:'INSERT INTO nodes(node_id,graph_id) SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM nodes WHERE node_id=? AND graph_id=?)'
    adjacency=[];e._iris_obj=lambda:SimpleNamespace(classMethodVoid=lambda *args:adjacency.append(args))
    gid=graph or ''
    if initial:
        c.db.executemany('INSERT INTO nodes VALUES(?,?)',[('a',gid),('b',gid)])
        q={'v':1};q.update({'temporal':True} if initial=='temporal' else {})
        c.db.execute('INSERT INTO rdf_edges(s,p,o_id,qualifiers,graph_id) VALUES(?,?,?,?,?)',('a','R','b',json.dumps(q),gid))
    fn=mutant or getattr(ne.NodesEdgesMixin,api)
    answers=[]
    with patch.object(ne,'_ledger_check',lambda *a:None):
        for value in [2,3]:
            try:answers.append(fn(e,'a','REFUSE' if refused else 'R','b',qualifiers={'v':value,**({'temporal':True} if incoming_marker else {})},graph=graph))
            except ne.GraphWriteError:answers.append('error')
    result={'answers':answers,'count':e.edge_count(graph=graph),'other_count':e.edge_count(graph='other'),
        'nodes':list(c.db.execute('SELECT node_id,graph_id FROM nodes ORDER BY node_id')),
        'values':[json.loads(q) for q, in c.db.execute('SELECT qualifiers FROM rdf_edges')],
        'manual_adjacency':len(adjacency)}
    c.db.close();return result

def expected(api,graph,indexed,initial,refused=False,incoming_marker=False):
    gid=graph or '';create=api=='create_edge'
    if refused:
        return {'answers':['error','error'],'count':0,'other_count':0,'nodes':[],'values':[],'manual_adjacency':0}
    old=bool(initial);adopt=initial=='temporal' and create
    retained=create and incoming_marker and (not old or adopt)
    q={'v':3 if retained else (2 if not old or adopt else 1)}
    if (incoming_marker and (not old or adopt)) or (initial=='temporal' and not adopt):q['temporal']=True
    return {'answers':[True if not old or adopt or not create else False,True if retained or not create else False],
        'count':1,'other_count':0,'nodes':[('a',gid),('b',gid)],'values':[q],
        'manual_adjacency':int(create and not old and not indexed)}

def main():
    cases=list(itertools.product(['create_edge','store_edge'],[None,'g'],[False,True],[None,'ordinary','temporal']))
    mism=[];observations=[]
    for args in cases:
        got=observe(*args);want=expected(*args)
        if got!=want:mism.append({'case':args,'got':got,'want':want})
        observations.append({'case':args,'result':got})
    for args in cases:
        got=observe(*args,incoming_marker=True);want=expected(*args,incoming_marker=True)
        if got!=want:mism.append({'case':args,'marker':True,'got':got,'want':want})
        observations.append({'case':args,'marker':True,'result':got})
    for api,graph,indexed in itertools.product(['create_edge','store_edge'],[None,'g'],[False,True]):
        args=(api,graph,indexed,None,True);got=observe(*args);want=expected(*args)
        if got!=want:mism.append({'case':args,'got':got,'want':want})
    source=textwrap.dedent(inspect.getsource(ne.NodesEdgesMixin.store_edge));scope=dict(vars(ne))
    assert source.count('return True')==1
    exec(source.replace('return True','return False'),scope)
    got=observe('store_edge','g',True,'ordinary',mutant=scope['store_edge'])
    sample=observe('create_edge',None,True,None);sample['count']=2
    detection={'same_duplicate_return':got!=expected('store_edge','g',True,'ordinary'),
        'changed_final_count':sample!=expected('create_edge',None,True,None)}
    out=bc.write_receipt('edge_acceptance',Path(__file__),{'verdict':'AGREES' if not mism and all(detection.values()) else 'DISAGREES',
        'comparisons':2*len(cases)+8,'mismatch_count':len(mism),'mismatches':mism,'detection':detection,
        'pin':bc.pin_identity(PIN_DIR),'observations':observations,
        'observed':'real create_edge/store_edge, _ensure_edge_endpoints, _swallow_duplicate, WriteTxn orchestration, temporal adoption and edge_count',
        'substituted':'SQLite atomic savepoints/uniqueness/FKs; IRIS catalog, ledger admission, native adjacency callback and row-id dialect. No cross-process writer race or IRIS observation.',
        'formal_relation':'expected transcribes edge_acceptance::run/count for a single triple; qualifiers represented by v and temporal; SQLite callbacks counted separately'})
    print(out);print(json.dumps({'mismatches':mism,'detection':detection}));return int(bool(mism) or not all(detection.values()))
if __name__=='__main__':raise SystemExit(main())
