"""Real bulk SQL producer -> persisted SQLite rows -> real typed get_node/get_nodes.

The IRIS dialect hints, Txn SQL functions, CY_TYPED producer and driver skip policy
are explicit adapters. No native ObjectScript, IRIS VECTOR or concurrent claim.
"""
from __future__ import annotations
import copy, hashlib, inspect, itertools, json, logging, math, re, sqlite3, sys, textwrap, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN_DIR=bc.import_pin()
from iris_vector_graph._engine import nodes_edges as ne
from iris_vector_graph import _batch_check as check
from iris_vector_graph import prop_values as pv

def typed(v):
    if isinstance(v,dict):return {str(k):typed(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [typed(x) for x in v]
    return [type(v).__name__,v]

def encoded(v):
    """Independent source contract: Python scalar input -> stored SQL value."""
    if isinstance(v,bool):return 'true' if v else 'false'
    if isinstance(v,int):return v if -(2**63)<=v<2**63 else str(v)
    if isinstance(v,float):return v if math.isfinite(v) else str(v)
    if isinstance(v,(dict,list)):return json.dumps(v)
    return str(v)

def decoded(v):
    """Independent stored-value observer; CY_TYPED tags themselves are adapted below."""
    if v=='true':return True
    if v=='false':return False
    if isinstance(v,str) and v.startswith(('[','{')):
        try:return json.loads(v)
        except ValueError:pass
    return v

def cy_typed(v):
    if type(v) is int:return '\x01N'+str(v)
    if type(v) is float:return '\x01D'+repr(v)
    if isinstance(v,str) and v.startswith('\x01'):return '\x01S'+v
    return v

def dialect(sql):
    # Keep the generated guards and bound parameters; strip only IRIS optimizer hints.
    sql=re.sub(r'%IGNOREINDEX\s+Graph_KG\.[A-Za-z_]+\.[A-Za-z_]+(?:,\s*Graph_KG\.[A-Za-z_]+\.[A-Za-z_]+)*\s+','',sql)
    return sql.replace('%NOINDEX ','').replace('Graph_KG.CY_TYPED(','CY_TYPED(')

class Cursor:
    def __init__(self,conn):self.conn=conn;self.cur=conn.db.cursor();self.rows=None;self.batch_count=None
    def execute(self,sql,params=()):
        self.rows=None;self.batch_count=None
        self.conn.calls.append((sql,list(params)))
        if '.Txn_Begin(' in sql:
            self.conn.level+=1;self.conn.db.execute(f'SAVEPOINT ivg_{self.conn.level}')
            self.rows=[(self.conn.level,)];return self
        if '.Txn_End(' in sql:
            self.conn.db.execute(f'RELEASE ivg_{self.conn.level}');self.conn.level-=1
            self.rows=[(self.conn.level,)];return self
        if '.Txn_Undo(' in sql:
            self.conn.db.execute(f'ROLLBACK TO ivg_{self.conn.level}');self.conn.db.execute(f'RELEASE ivg_{self.conn.level}');self.conn.level-=1
            self.rows=[(self.conn.level,)];return self
        self.cur.execute(dialect(sql),params);return self
    def executemany(self,sql,rows):
        count=0
        for row in rows:
            try:self.execute(sql,row);count+=max(self.cur.rowcount,0)
            except sqlite3.IntegrityError:
                if not self.conn.skip_integrity:raise
                self.conn.skipped+=1
        self.batch_count=count;return self
    @property
    def rowcount(self):return self.cur.rowcount if self.batch_count is None else self.batch_count
    def fetchone(self):return self.rows.pop(0) if self.rows else self.cur.fetchone()
    def fetchall(self):return list(self.rows) if self.rows is not None else self.cur.fetchall()
    def close(self):self.cur.close()

class Connection:
    autocommit=True
    def __init__(self,skip_integrity=False):
        self.level=0;self.skip_integrity=skip_integrity;self.skipped=0;self.calls=[]
        self.db=sqlite3.connect(':memory:',isolation_level=None)
        self.db.execute("ATTACH DATABASE ':memory:' AS Graph_KG")
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.create_function('CY_TYPED',1,cy_typed)
        self.db.execute('CREATE TABLE Graph_KG.nodes(node_id TEXT NOT NULL,graph_id TEXT NOT NULL,PRIMARY KEY(graph_id,node_id))')
        self.db.execute('CREATE TABLE Graph_KG.rdf_labels(graph_id TEXT NOT NULL,s TEXT NOT NULL,label TEXT NOT NULL,PRIMARY KEY(graph_id,s,label),FOREIGN KEY(graph_id,s) REFERENCES nodes(graph_id,node_id))')
        # No FK here: modern product rdf_props can outlive a deleted parent.
        self.db.execute('CREATE TABLE Graph_KG.rdf_props(graph_id TEXT NOT NULL,s TEXT NOT NULL,"key" TEXT NOT NULL,val BLOB,PRIMARY KEY(graph_id,s,"key"))')
    def cursor(self):return Cursor(self)
    def commit(self):self.db.commit()

def engine(conn):
    e=ne.NodesEdgesMixin.__new__(ne.NodesEdgesMixin)
    e.conn=conn;e._schema_prefix='Graph_KG';e._ivg_schema='Graph_KG';e._t=lambda name:'Graph_KG.'+name
    e._nodes_has_graph_id=e._children_have_graph_id=True
    e._known_capabilities=SimpleNamespace(objectscript_deployed=False)
    return e

def empty():return {'parents':set(),'labels':set(),'props':{}}

def seed(conn,s):
    conn.db.executemany('INSERT INTO Graph_KG.nodes(graph_id,node_id) VALUES(?,?)',sorted(s['parents']))
    conn.db.executemany('INSERT INTO Graph_KG.rdf_labels VALUES(?,?,?)',sorted(s['labels']))
    conn.db.executemany('INSERT INTO Graph_KG.rdf_props VALUES(?,?,?,?)',[(g,n,k,v) for (g,n,k),v in s['props'].items()])

def persisted(conn):
    return {'parents':set(conn.db.execute('SELECT graph_id,node_id FROM Graph_KG.nodes')),
        'labels':set(conn.db.execute('SELECT graph_id,s,label FROM Graph_KG.rdf_labels')),
        'props':{(g,n,k):v for g,n,k,v in conn.db.execute('SELECT graph_id,s,"key",val FROM Graph_KG.rdf_props')}}

def prepared(nodes,graph):
    return [n if 'graph' in n else {**n,'graph':graph} for n in nodes] if graph else nodes

def expected(before,nodes,graph=None):
    """Inspectable Python twin of bulk_children cleanup/fold, never calls product helpers."""
    out=copy.deepcopy(before);nodes=prepared(nodes,graph)
    targets={(n.get('graph') or '',n['id']) for n in nodes if n.get('id')}
    for key in list(out['props']):
        if key[:2] in targets and key[:2] not in before['parents']:del out['props'][key]
    ids=[]
    for n in nodes:
        if not n.get('id'):continue
        g,nid=n.get('graph') or '',n['id'];ids.append(nid);out['parents'].add((g,nid))
        out['labels'].update((g,nid,l) for l in n.get('labels',[]))
        props=dict(n.get('properties') or {})
        if 'id' not in props:props['id']=nid
        for k,v in props.items():
            if v is not None:out['props'].setdefault((g,nid,k),encoded(v))
    return out,ids

def public_check(got,s,nid,graph):
    """Allow all row orders when alias keys collide; compare exact types/values otherwise."""
    labels={l for g,n,l in s['labels'] if (g,n)==(graph,nid)}
    props={k:v for (g,n,k),v in s['props'].items() if (g,n)==(graph,nid)}
    present=(graph,nid) in s['parents'] or labels or props
    if not present:return got is None
    if got is None or got.get('id')!=nid or set(got.get('labels',[]))!=labels:return False
    possible={}
    for k,v in props.items():possible.setdefault('p_'+k if k in ('id','labels') else k,[]).append(decoded(v))
    if set(got)!=set(possible)|{'id','labels'}:return False
    return all(any(typed(got[k])==typed(v) for v in vs) for k,vs in possible.items())

def observe(before,nodes,graph=None,*,skip=False,mutant=None,reader_mutant=None):
    c=Connection(skip);seed(c,before);e=engine(c);err=None;returned=None
    if mutant=='no_cleanup':e._drop_orphaned_props=lambda *a:None
    if mutant=='no_backstop':e._check_nodes_written=lambda *a:None
    if reader_mutant is not None:e.get_nodes=reader_mutant.__get__(e,ne.NodesEdgesMixin)
    before_args=copy.deepcopy(nodes)
    with patch.object(ne,'_ledger_check',lambda *a:None),patch.object(check,'_live',lambda conn:True):
        try:returned=e.bulk_create_nodes(nodes,disable_indexes=False,graph=graph)
        except Exception as exc:err={'class':type(exc).__name__,'text':str(exc)}
    after=persisted(c);reads={};mism=[]
    all_ids=sorted({n for _,n in before['parents']}|{n['id'] for n in nodes if n.get('id')})
    all_graphs=sorted({g for g,_ in before['parents']}|{g for g,_,_ in before['props']}|{n.get('graph') or '' for n in prepared(nodes,graph)}|{'','other'})
    for g in all_graphs:
        for nid in all_ids:
            got=e.get_node(nid,graph=g);reads[(g,nid)]=got
            if not public_check(got,after,nid,g):mism.append({'graph':g,'id':nid,'got':typed(got)})
        ids=all_ids+all_ids[:1]+['absent']
        many=e.get_nodes(ids,graph=g)
        want=[reads[(g,n)] for n in ids if n in all_ids and reads[(g,n)] is not None]
        if typed(many)!=typed(want):mism.append({'graph':g,'batch_reader':typed(many),'single_readers':typed(want)})
    out={'returned':returned,'error':err,'after':after,'reads':reads,'reader_mismatches':mism,
        'arguments_unchanged':nodes==before_args,'skipped':c.skipped,'txn_level':c.level,
        'executed_sql_statements':len(c.calls)}
    c.db.close();return out

def jsonable(s):
    return {'parents':sorted(s['parents']),'labels':sorted(s['labels'],key=repr),
        'props':[(list(k),typed(v)) for k,v in sorted(s['props'].items(),key=lambda kv:repr(kv[0]))]}

def compare_case(name,before,nodes,graph=None):
    want,ids=expected(before,nodes,graph);got=observe(before,copy.deepcopy(nodes),graph)
    bad=got['error'] is not None or got['returned']!=ids or typed(jsonable(got['after']))!=typed(jsonable(want)) or got['reader_mismatches'] or not got['arguments_unchanged'] or got['txn_level']!=0
    summary={'name':name,'returned':got['returned'],'persisted':jsonable(got['after']),
        'reads':{str(k):typed(v) for k,v in got['reads'].items()},'sql_statements':got['executed_sql_statements']}
    return bad,summary,got

def main():
    started=time.monotonic();mism=[];observations=[];cases=[]
    # Independently frozen B1, in both default and explicit named graph, plus same-ID other graph.
    for graph in ('','g'):
        before=empty();before['parents']={(graph,'a'),('other','a')}
        before['labels']={(graph,'a','Old'),('other','a','Other')}
        before['props']={(graph,'a','name'):'old',(graph,'a','keep'):'k',('other','a','name'):'foreign'}
        nodes=[{'id':'a','labels':['New'],'properties':{'name':'new','flag':True}},
            {'id':'b','labels':['L'],'properties':{'n':5}},
            {'id':'c','graph':'override','labels':['G'],'properties':{'x':'y'}}]
        cases.append((f'B1-{graph or "default"}',before,nodes,graph))
    # B2 mixed batch has orphan/existing/fresh/repeat, with identical deciding old property a=1.
    for graph in ('','g'):
        before=empty();before['parents']={(graph,'existing'),('other','orphan')}
        before['props']={(graph,'orphan','a'):1,(graph,'orphan','obsolete'):'old',
            (graph,'existing','a'):1,('other','orphan','a'):9}
        nodes=[{'id':'orphan','properties':{'a':2}},{'id':'existing','properties':{'a':2,'c':3}},
            {'id':'fresh','properties':{'a':2}},{'id':'orphan','properties':{'a':3,'d':4}}]
        cases.append((f'B2-{graph or "default"}',before,nodes,graph))
    # Input values challenge numeric/text, booleans, containers, null, type marks and nonfinite spelling.
    values=[0,-7,29,2**63-1,2**63,0.5,5.0,True,False,'29','true','false','',
        '\x01N29','[1,2]',{'x':1},[1,'a'],None,float('inf'),float('-inf'),float('nan')]
    for graph,initial,v in itertools.product(('','g'),('fresh','existing','orphan'),values):
        before=empty()
        if initial=='existing':before['parents'].add((graph,'n'))
        if initial!='fresh':before['props'][(graph,'n','v')]=1
        before['parents'].add(('other','n'));before['props'][('other','n','v')]=9
        cases.append((f'value-{graph}-{initial}-{v!r}',before,[{'id':'n','labels':['L'],'properties':{'v':v}}],graph))
    cases.extend([
        ('explicit-null-id',empty(),[{'id':'n','properties':{'id':None,'a':None}}],None),
        ('explicit-caller-id',empty(),[{'id':'n','properties':{'id':'caller','labels':'user','p_id':'collision'}}],None),
        ('falsey-id-skipped',empty(),[{'id':0},{'id':'n'}],None),
        ('graph-null-overrides-keyword',empty(),[{'id':'n','graph':None},{'id':'m'}],'g'),
        ('empty',empty(),[],None),
        ('repeated-values',empty(),[{'id':'n','properties':{'a':1}},{'id':'n','properties':{'a':2,'c':3}}],None),
    ])
    for name,before,nodes,graph in cases:
        bad,summary,_=compare_case(name,before,nodes,graph);observations.append(summary)
        if bad:mism.append(summary)
    failures=[]
    for graph,skip in itertools.product(('','g'),(False,True)):
        before=empty();before['props'][(graph,'orphan','a')]=1
        nodes=[{'id':'orphan','labels':['Good'],'properties':{'a':2}},
            {'id':'bad','labels':[None],'properties':{'v':3}}]
        got=observe(before,nodes,graph,skip=skip)
        okay=got['error'] is not None and typed(jsonable(got['after']))==typed(jsonable(before)) and got['txn_level']==0
        failures.append({'graph':graph,'skip':skip,'error':got['error'],'skipped':got['skipped'],'restored_original':okay})
        if not okay:mism.append(failures[-1])
    # Mutations change deciding work / the final reader and still execute valid product Python/SQL.
    before=empty();before['props'][('g','n','a')]=1
    nodes=[{'id':'n','properties':{'a':2}}]
    bad=observe(before,nodes,'g',mutant='no_cleanup');want,_=expected(before,nodes,'g')
    detection={'orphan_cleanup_removed':typed(jsonable(bad['after']))!=typed(jsonable(want))}
    bad=observe(empty(),[{'id':'a','labels':['Good']},{'id':'b','labels':[None]}],skip=True,mutant='no_backstop')
    detection['missing_row_backstop_removed']=bad['error'] is None and bool(bad['after']['parents'])
    src=textwrap.dedent(inspect.getsource(ne.NodesEdgesMixin.get_nodes));scope=dict(vars(ne))
    assert src.count('graph_id = DEFAULT_GRAPH if graph is None else graph')==1
    exec(src.replace('graph_id = DEFAULT_GRAPH if graph is None else graph','graph_id = DEFAULT_GRAPH'),scope)
    bad=observe(empty(),[{'id':'n','properties':{'a':2}}],'g',reader_mutant=scope['get_nodes'])
    detection['reader_graph_removed']=bool(bad['reader_mismatches'])
    with patch.object(ne,'prop_value',pv.prop_text):
        bad=observe(empty(),[{'id':'n','properties':{'v':29}}])
    detection['numeric_writer_changed']=type(bad['reads'][('','n')]['v']) is str
    good=observe(empty(),[{'id':'n','properties':{'a':2}}]);changed=copy.deepcopy(good['reads'][('','n')]);changed['a']=3
    detection['changed_public_value']=not public_check(changed,good['after'],'n','')
    ident=bc.pin_identity(PIN_DIR)
    extra=['iris_vector_graph/_batch_check.py','iris_vector_graph/_write_txn.py','iris_vector_graph/_widths.py','iris_vector_graph/schema_name.py','iris_vector_graph/schema.py','iris_vector_graph/prop_values.py']
    import subprocess
    for path in extra:
        blob=subprocess.check_output(['git','-C',str(bc.REPO),'rev-parse',f'{bc.PIN}:{path}'],text=True).strip()
        have=subprocess.check_output(['git','hash-object',str(PIN_DIR/path)],text=True).strip()
        ident['files_equal_pin_blobs'][path]=blob==have;ident['all_equal'] &= blob==have
    verdict='AGREES' if not mism and all(detection.values()) and ident['all_equal'] else 'DISAGREES'
    out=bc.write_receipt('bulk_children',Path(__file__),{'verdict':verdict,'comparisons':len(cases)+len(failures),
        'mismatch_count':len(mism),'mismatches':mism,'detection':detection,'pin':ident,'observations':observations,'failures':failures,
        'wall_s':round(time.monotonic()-started,3),
        'real':'bulk_create_nodes SQL branch, _bulk_sql/get_bulk_insert_sql, shape/width guards, orphan DELETE, guarded child INSERTs, _check_nodes_written/missing_rows, WriteTxn orchestration, get_node/get_nodes/read_node_value',
        'substituted':'SQLite relational storage/atomic savepoints and uniqueness/FKs; stripped IRIS optimizer hints; CY_TYPED tag producer; _batch_check live-connection predicate forced true; optional driver skips real NOT NULL failures. No native ObjectScript loader, index DDL or live IRIS.',
        'formal_relation':'expected is inspected transcription of bulk_children::cleanup/offered/fold/returned, with decoded typed atoms; public_check consumes persisted state and admits each alias-collision row order; generic whole-batch no-refusal and complete-reader theorems are proved. The Python twin itself is not proved.'})
    d=json.loads(out.read_text())
    for path in extra:d['inputs'][path]=hashlib.sha256((PIN_DIR/path).read_bytes()).hexdigest()
    out.write_text(json.dumps(d,indent=2,sort_keys=True,default=str)+'\n')
    print(f'bulk_children: {verdict}, {len(cases)+len(failures)} comparisons, {len(mism)} mismatches -> {out}')
    print(json.dumps({'detection':detection,'failures':failures,'first_mismatches':mism[:2]},default=str))
    return int(verdict!='AGREES')
if __name__=='__main__':raise SystemExit(main())
