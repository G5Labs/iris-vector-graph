"""Actual committed metadata -> history's SQL text equality on the isolated runtime."""
import importlib.util,json
from pathlib import Path
g5=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('snapshot_binding',g5/'Verus_verification/models/snapshot_routes/binding.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
from iris_vector_graph.ledger.changeset import Changeset
c=b.connect();e=b.IRISGraphEngine(c,embedding_dimension=8);e.erase_all();e.ledger.enable()
cs=Changeset(actor='CaseActor',actor_type='human',correlation_id='CaseCorr',source={'name':'CaseSource'}).create_node('history:case')
commit=e.ledger.commit(cs);cur=c.cursor();cur.execute('SELECT actor, actor_type, correlation_id, source FROM Graph_KG.ledger_revisions WHERE seq=?',[commit.revision.seq]);raw=list(cur.fetchone());cur.close()
cases=[]
for name,value in [('actor',raw[0]),('actor_type',raw[1]),('correlation_id',raw[2]),('source',raw[3])]:
    for altered in [str(value),str(value).lower(),str(value).upper(),str(value)+'x']:
        try:page=e.ledger.history(**{name:altered});result={'seqs':[x.seq for x in page.revisions]}
        except Exception as ex:result={'error':str(ex),'type':type(ex).__name__}
        cases.append({'filter':name,'value':altered,'result':result})
e.ledger.disable();c.close()
out={'native_container':b.NAME,'port':b.PORT,'identity_checked':True,'raw_row':raw,'revision_seq':commit.revision.seq,'cases':cases,'scope':'one actual committed Changeset; SQL provider collation and raw source JSON equality; no SQLite collation assumption'}
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
