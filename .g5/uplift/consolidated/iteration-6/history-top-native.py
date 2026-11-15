"""Read-only TOP0/negative provider observation on this task's isolated IRIS."""
import importlib.util,json
from pathlib import Path
g5=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('snapshot_binding',g5/'Verus_verification/models/snapshot_routes/binding.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
c=b.connect();e=b.IRISGraphEngine(c,embedding_dimension=8);out=[]
def top_nodes(limit):
    cur=c.cursor()
    try:cur.execute(f'SELECT TOP {limit} node_id FROM Graph_KG.nodes');return [str(r[0]) for r in cur.fetchall()]
    finally:cur.close()
for limit in [0,-1,-5,1]:
    row={'limit':limit}
    for key,fn in [('history',lambda:e.ledger.history(limit=limit)),('nodes_top',lambda:top_nodes(limit))]:
        try:r=fn();row[key]={'kind':'value','repr':repr(r)}
        except Exception as ex:row[key]={'kind':'error','type':type(ex).__name__,'error':str(ex)}
    out.append(row)
c.close();Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
