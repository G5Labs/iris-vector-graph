"""Out-of-formal-fragment whole-float iteration carrier, actual Python only."""
import importlib.util,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[4]
p=root/'.g5/Verus_verification/models/ppr_walk/binding.py'
spec=importlib.util.spec_from_file_location('ppr_carrier_binding',p);b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
rows=[];start=time.monotonic()
for it in [1,1.0,2,2.0]:
 rel=b.Relational([('','seed'),('','zero')],[]);o=b.engine(rel,b.SourcePort([('','seed'),('','zero')],[]),'fallback')
 b.am.check_ppr_args('carrier',.5,it,'alpha','max_iter')
 try:got=o.kg_PERSONALIZED_PAGERANK(['seed'],damping_factor=.5,max_iterations=it,tolerance=0);out={'value':got}
 except Exception as e:out={'error_type':type(e).__name__,'error':str(e)}
 rows.append({'carrier':repr(it),'python_type':type(it).__name__,'public_validation':'accepted','outcome':out,'cursor_closed':rel.closed});rel.close()
assert rows[0]['outcome']['value']==rows[2]['outcome']['value']=={'seed':1.,'zero':0.}
assert rows[1]['outcome']['error_type']==rows[3]['outcome']['error_type']=='TypeError'
assert b.CONNECT.call_count==0
out={'scope':'Actual public method with no store or ObjectScript capability -> actual Python fallback over SQLite. No native/classfast coercion conclusion, no issue or policy decision. Request.iterations in ppr_walk is an integer carrier; this allowed whole-float carrier is explicitly outside that formal fragment. Newly noticed after original predictions.','cases':rows,'blocked_socket_calls':b.CONNECT.call_count,'elapsed':time.monotonic()-start,'inputs':{str(p.relative_to(root)):b.bc.sha(p),'iris_vector_graph/_engine/algorithms.py':b.bc.sha(b.PIN/'iris_vector_graph/_engine/algorithms.py')}}
q=Path(__file__).with_suffix('.json');q.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
