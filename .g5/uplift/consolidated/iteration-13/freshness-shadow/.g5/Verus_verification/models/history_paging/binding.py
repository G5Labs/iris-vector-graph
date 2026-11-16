"""Actual GraphLedger.history -> SQL -> _rev_from_row -> RevisionInfo/HistoryPage.

SQLite executes the generated predicates/order/limit. TOP is adapted to LIMIT,
and the validated IRIS comparison fragment (ASCII case and trailing space/tab)
is installed as a SQLite collation. Negative TOP refuses by the separately
observed native IRIS contract, never SQLite's unlimited-negative-LIMIT rule.
"""
import inspect,itertools,json,logging,re,sqlite3,sys,time,textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN_DIR=bc.import_pin()
from iris_vector_graph.ledger import client as cl
from iris_vector_graph.ledger import replay as rp

def fold(s):
    return ''.join(chr(ord(c)-32) if 'a'<=c<='z' else c for c in s).rstrip(' \t')

ROWS=[]
for seq in range(1,7):
    planner=seq in [2,4]
    ROWS.append({'seq':seq,'revision_id':f'r{seq}','parent_id':None if seq==1 else f'r{seq-1}',
        'kind':'genesis' if seq==1 else 'changeset','actor':'Planner' if planner else 'Human',
        'actor_type':'agent' if planner else 'human','conn_user':'test','committed_ms':seq*100,
        'message':None if seq==1 else f'm{seq}',
        'source':None if seq==1 else ('{"tag":"X"}' if planner else '{"tag":"Y"}'),
        'correlation_id':None if seq==1 else ('TenantX' if seq%2==0 else 'TenantY'),
        'idempotency_key':None,'op_count':None if seq==1 else seq})
COLS=[c.strip() for c in rp._REV_COLS.split(',')]

class ProviderError(RuntimeError):pass
class Cursor:
    def __init__(self,conn):self.conn=conn;self.cur=conn.db.cursor()
    def execute(self,sql,params):
        self.conn.sql.append((sql,list(params)))
        if self.conn.fail=='execute':raise ProviderError('injected query execute refusal')
        m=re.fullmatch(r'SELECT TOP (-?\d+) (.*)',sql);assert m,sql
        n=int(m[1])
        if n<0:raise ProviderError('IRIS native TOP negative syntax refusal (adapter contract)')
        self.cur.execute('SELECT '+m[2]+' LIMIT '+str(n),params)
    def fetchall(self):
        if self.conn.fail=='fetch':raise ProviderError('injected fetch refusal')
        rows=self.cur.fetchall()
        if self.conn.fail=='decode' and rows:
            rows[0]=('not-an-integer',*rows[0][1:])
        return rows
    def close(self):self.conn.closed+=1;self.cur.close()
class Connection:
    def __init__(self,rows=ROWS,fail=None):
        self.db=sqlite3.connect(':memory:');self.fail=fail;self.closed=0;self.opened=0;self.sql=[]
        self.db.create_collation('IVG_UPPER',lambda a,b:(fold(a)>fold(b))-(fold(a)<fold(b)))
        columns=[]
        for col in COLS:
            columns.append(col+(' INTEGER PRIMARY KEY' if col=='seq' else ' INTEGER' if col in ['committed_ms','op_count'] else ' TEXT COLLATE IVG_UPPER'))
        self.db.execute('CREATE TABLE ledger_revisions('+','.join(columns)+')')
        # Deliberately non-monotone write order; the emitted ORDER BY, not fixture
        # order, owns the caller's ordering.
        for row in sorted(rows,key=lambda r:(r['seq']*5)%7):
            self.db.execute('INSERT INTO ledger_revisions VALUES('+','.join('?' for _ in COLS)+')',[row.get(k) for k in COLS])
    def cursor(self):
        if self.fail=='open':raise ProviderError('injected cursor-open refusal')
        self.opened+=1;return Cursor(self)
    def stop(self):self.db.close()

FILTERS=[{}, {'actor':'Planner'}, {'actor':'planner'}, {'actor':'PLANNER \t'}, {'actor':' Planner'},
    {'actor_type':'HUMAN'}, {'actor_type':'humanx'}, {'since_ms':200,'until_ms':500},
    {'since_ms':500,'until_ms':200}, {'correlation_id':'tenantx'}, {'correlation_id':'TenantX  '},
    {'source':'{"tag":"X"}'}, {'source':'{"TAG":"x"}\t'}, {'source':'{"tag": "X"}'}, {'source':'{"tag":"Z"}'},
    {'source':''}, {'correlation_id':''}, {'actor':'Planner','actor_type':'agent','since_ms':200,'until_ms':400,'correlation_id':'tenantx','source':'{"TAG":"x"}'},
    {'actor':'missing'}]

def expected(rows,after_seq=0,limit=100,descending=False,**filters):
    if limit<0:return {'kind':'error'}
    chosen=[]
    for row in rows:
        seq=row['seq']
        if not ((not after_seq or seq<after_seq) if descending else seq>after_seq):continue
        good=True
        for key,value in filters.items():
            if key=='since_ms':good &= row['committed_ms'] is not None and row['committed_ms']>=value
            elif key=='until_ms':good &= row['committed_ms'] is not None and row['committed_ms']<=value
            else:good &= row[key] is not None and fold(row[key])==fold(value)
        if good:chosen.append(row)
    chosen=sorted(chosen,key=lambda r:r['seq'],reverse=descending)[:limit]
    return {'kind':'page','seqs':[r['seq'] for r in chosen],
        'next':chosen[-1]['seq'] if chosen and len(chosen)==limit else None}

def observe(conn,**params):
    ledger=cl.GraphLedger(SimpleNamespace(conn=conn,_schema_prefix='main'))
    before=conn.closed
    try:
        page=ledger.history(**params)
        out={'kind':'page','seqs':[r.seq for r in page.revisions],'next':page.next_after_seq}
        # Final actual RevisionInfo projection, not a prebuilt list of answers.
        projection=[{'seq_type':type(r.seq).__name__,'ms_type':type(r.committed_ms).__name__,
            'count_type':type(r.op_count).__name__,'seq':r.seq,'ms':r.committed_ms,'count':r.op_count,
            'parent':r.parent_id,'source':r.source,'actor':r.actor,'kind':r.kind,'message':r.message,
            'correlation_id':r.correlation_id,'idempotency_key':r.idempotency_key} for r in page.revisions]
    except Exception as ex:out={'kind':'error'};projection=[type(ex).__name__]
    return out,conn.closed-before,projection

def matrix(fn=None):
    mism=[];n=0;projection_ok=True;closed_ok=True
    with patch.object(rp,'fetch_history',fn or rp.fetch_history):
        for rows in [ROWS,[]]:
            conn=Connection(rows)
            try:
                for desc,limit,after,flt in itertools.product([False,True],[-5,-1,0,1,2,3,4,7],[-1,0,1,2,3,4,5,6,7,8],FILTERS):
                    params=dict(after_seq=after,limit=limit,descending=desc,**flt)
                    got,closed,projection=observe(conn,**params);want=expected(rows,**params)
                    if got!=want:mism.append({'params':params,'empty':not rows,'got':got,'want':want})
                    closed_ok &= closed==1
                    if got['kind']=='page':
                        for value in projection:
                            original=next(r for r in rows if r['seq']==value['seq'])
                            source=None if value['seq']==1 else {'tag':'X' if value['seq'] in [2,4] else 'Y'}
                            projection_ok &= (value['seq_type']==value['ms_type']==value['count_type']=='int'
                                and value['ms']==original['committed_ms'] and value['count']==(original['op_count'] or 0)
                                and value['parent']==original['parent_id'] and value['source']==source
                                and value['actor']==original['actor'] and value['kind']==original['kind'] and value['message']==original['message']
                                and value['correlation_id']==original['correlation_id'] and value['idempotency_key'] is None)
                    n+=1
            finally:conn.stop()
    return n,mism,projection_ok,closed_ok

def decoder_cases():
    # Expectations are explicit wire examples, including JSON values whose type
    # differs from the source annotation. This is observed, not a general JSON proof.
    sources=[(None,None),('',None),('{}',None),('[]',None),('false',None),('0',None),
        ('{"x":1}',{'x':1}),('[1,2]',[1,2]),('"text"','text'),('true',True),('1',1),('not json',{'raw':'not json'})]
    observations=[];mism=[]
    for raw,want in sources:
        values={'seq':'7','revision_id':None,'parent_id':'','kind':None,'actor':None,'actor_type':None,'conn_user':None,
            'committed_ms':None,'message':'','source':raw,'correlation_id':'','idempotency_key':'','op_count':None}
        got=rp._rev_from_row([values[k] for k in COLS])
        ok=(type(got.seq) is int and got.seq==7 and got.revision_id=='None' and got.kind==got.actor==got.actor_type==got.conn_user=='None'
            and got.parent_id is None and got.committed_ms==0 and got.message is None and got.correlation_id is None and got.idempotency_key is None and got.op_count==0
            and type(got.source) is type(want) and got.source==want)
        observations.append({'source_wire':raw,'source_type':type(got.source).__name__,'source_value':got.source,'agrees':ok})
        if not ok:mism.append(observations[-1])
    return observations,mism

def main():
    start=time.monotonic();n,mism,typed,closed=matrix()
    pages={}
    for desc in [False,True]:
        conn=Connection();after=0;out=[]
        for _ in range(8):
            got,_,_=observe(conn,after_seq=after,limit=2,descending=desc);out.append(got)
            if got['next'] is None:break
            after=got['next']
        pages[str(desc)]=out;conn.stop()
    # Actual product function mutants, with independent expectations unchanged.
    src=textwrap.dedent(inspect.getsource(rp.fetch_history));mutants={
        'inclusive_cursor':('where.append("seq > ?")','where.append("seq >= ?")'),
        'full_page_cursor_hidden':('len(revs) == int(limit)','len(revs) > int(limit)'),
        'actor_predicate_removed':('if actor is not None:','if False:')}
    detection={}
    for name,(find,replace) in mutants.items():
        assert src.count(find)==1;scope=dict(vars(rp));exec(src.replace(find,replace),scope)
        _,mm,_,_=matrix(scope['fetch_history']);detection[name]=bool(mm)
    sample=expected(ROWS,limit=2);sample['seqs']=[999];detection['changed_final_revision']=sample!=expected(ROWS,limit=2)
    faults=[]
    for fault in ['open','execute','fetch','decode']:
        conn=Connection(fail=fault);got,calls,projection=observe(conn,limit=2)
        ok=got['kind']=='error' and calls==(0 if fault=='open' else 1)
        faults.append({'fault':fault,'result':got,'close_calls':calls,'exception_type':projection,'agrees':ok});conn.stop()
    decoder,dm=decoder_cases()
    # Successful integer-text conversion keeps the original raw truthiness.
    conn=Connection();coercions=[]
    for after in [0,'0']:
        got,calls,_=observe(conn,after_seq=after,limit=2,descending=True);coercions.append({'raw_after':after,'type':type(after).__name__,'result':got,'close_calls':calls})
    conn.stop()
    coercion_ok=coercions[0]['result']=={'kind':'page','seqs':[6,5],'next':5} and coercions[1]['result']=={'kind':'page','seqs':[],'next':None}
    assert src.count('if after_seq:')==1;scope=dict(vars(rp));exec(src.replace('if after_seq:','if int(after_seq):'),scope)
    conn=Connection()
    with patch.object(rp,'fetch_history',scope['fetch_history']):mut,_,_=observe(conn,after_seq='0',limit=2,descending=True)
    conn.stop();detection['converted_cursor_truthiness']=mut!=coercions[1]['result']
    verdict='AGREES' if not mism and not dm and typed and closed and coercion_ok and all(detection.values()) and all(f['agrees'] for f in faults) else 'DISAGREES'
    out=bc.write_receipt('history_paging',Path(__file__),{'verdict':verdict,'comparisons':n,'mismatch_count':len(mism)+len(dm),'mismatches':mism[:8]+dm,
        'typed_projection_agrees':typed,'all_acquired_cursors_closed_once':closed,'detection':detection,'pages':pages,'faults':faults,'decoder_cases':decoder,
        'cursor_coercion_cases':coercions,'cursor_coercions_agree':coercion_ok,'pin':bc.pin_identity(PIN_DIR),'elapsed':time.monotonic()-start,
        'observed':'actual GraphLedger.history forwarding, generated SQL predicates/order, _rev_from_row and RevisionInfo/HistoryPage fields, exact-full final cursor, zero/negative handling and exception/finally paths',
        'provider_substitution':'SQLite TOP->LIMIT, ASCII case/trailing space+tab collation fragment, negative TOP rejection per root native IRIS observations. SQL/driver and JSON parsing are not executable-body proofs; injected faults are boundary tests.',
        'formal_relation':'history_paging::admitted/ordered/prefix/decode/finish/history/attempt. SQL row values map to Table rows by unique seq; view wire source keeps raw comparison identity while actual JSON decode is observed separately.'})
    # Native validation inputs are shared facts supplied by root, not native runs
    # by this builder. Stamping both scripts and observations reopens this receipt
    # if a provider assumption's evidence changes.
    receipt=json.loads(out.read_text());native=[]
    for stem in ['history-top-native','history-collation-native','history-collation-spaces-native','history-collation-interior-native','history-continuation-native']:
        for suffix in ['.py','.json']:
            p=bc.REPO/'.g5/uplift/consolidated/iteration-6'/(stem+suffix)
            if not p.is_file():raise RuntimeError('missing provider evidence '+str(p))
            receipt['inputs'][str(p.relative_to(bc.REPO))]=bc.sha(p);native.append(str(p.relative_to(bc.REPO)))
    receipt['provider_evidence_from_root']=native
    receipt['native_correspondence_scope']='Root observed negative/zero TOP and case/trailing-space/tab filters on actual committed revisions; builder ran only Python/SQLite. General Unicode/full SQLUPPER remains open.'
    out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(out);print(json.dumps({'verdict':verdict,'cases':n,'mismatches':len(mism)+len(dm),'detection':detection,'elapsed':time.monotonic()-start}));return int(verdict!='AGREES')
if __name__=='__main__':raise SystemExit(main())
