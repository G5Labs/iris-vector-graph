"""Distinguish merge guard from destination-width refusal on this task IRIS."""
import importlib.util,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[3]
p=root/'Verus_verification/models/snapshot_routes/binding.py'
spec=importlib.util.spec_from_file_location('snapshot_binding',p);b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
c=b.connect();e=b.IRISGraphEngine(c,embedding_dimension=8)
tables={g:e.resolve_route(g,m).table_name for g,m,w,v in [b.A,b.B]}
b.empty_destination(e,list(tables.values()))
for graph,model,w,value in [b.A,b.B]:e.create_node(b.NODE,graph=graph)
e.resolve_route(b.B[0],b.B[1],create=True,dimension=8)
e.store_embedding(b.NODE,[9.0]*8,graph=b.B[0],model_key=b.B[1])
path='/Users/ziniuw/runs/ivg-iteration5-snapshot-20261115/native-snapshot/original.zip'
before=b.observation(e,tables);restore=e.restore_snapshot(path,merge=True);after=b.observation(e,tables)
out={'before':before,'restore':restore,'after':after,'meaning':'Both parents present; preexisting same-key width8 row versus incoming width16 row; whether NOT EXISTS skips before width enforcement.'}
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'failed_rows':restore['failed_rows'],'reported':restore['restored_tables'].get('Graph_KG.'+tables[b.B[0]]),'b':after[b.B[0]]},indent=2));c.close()
