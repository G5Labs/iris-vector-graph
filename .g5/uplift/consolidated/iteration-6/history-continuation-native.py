"""Read existing legitimate revisions through actual limit1 cursor continuations."""
import importlib.util,json,dataclasses
from pathlib import Path
g5=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('snapshot_binding',g5/'Verus_verification/models/snapshot_routes/binding.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
c=b.connect();e=b.IRISGraphEngine(c,embedding_dimension=8);result=[]
for descending in [False,True]:
    cursor=0;pages=[]
    for _ in range(10):
        p=e.ledger.history(after_seq=cursor,limit=1,descending=descending)
        pages.append({'input_after_seq':cursor,'revisions':[dataclasses.asdict(x) for x in p.revisions],'next_after_seq':p.next_after_seq})
        if p.next_after_seq is None:break
        cursor=p.next_after_seq
    assert pages[-1]['next_after_seq'] is None
    result.append({'descending':descending,'pages':pages})
c.close();Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
print(json.dumps([{'descending':r['descending'],'pages':[{'seqs':[x['seq'] for x in p['revisions']],'next':p['next_after_seq']} for p in r['pages']]} for r in result],indent=2))
