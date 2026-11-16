"""Root-only integration of the independently accepted ordinary reporting package."""
import csv,hashlib,io,json,re
from pathlib import Path
R=Path.cwd();V=R/'.g5/Verus_verification';H=R/'.g5/uplift/consolidated/iteration-13'
review=json.loads((H/'review-reporting-final-validation.json').read_text())
assert review['verdict']=='ACCEPT_BOUNDED_ORDINARY_REPORTING_FRAGMENT'
MD=V/'models/routine_reporting';FP='.g5/Verus_verification/models/routine_reporting/routine_reporting.rs'
for name,sha in review['package'].items():assert hashlib.sha256((MD/name).read_bytes()).hexdigest()==sha,name
census=json.loads((H/'before-reach/census.json').read_text());before=json.loads((H/'before-reach/bindings.json').read_text())
def read_rows(p):return list(csv.DictReader(io.StringIO(p.read_text()),delimiter='\t'))
def append(p,rows):
 old=p.read_text();fields=list(read_rows(p)[0]);out=io.StringIO();w=csv.DictWriter(out,fields,delimiter='\t',lineterminator='\n');w.writerows(rows);p.write_text(old+out.getvalue())
def metadata(rel,block,line):
 p=R/rel;s=p.read_text();m=re.search(r'^### '+re.escape(block)+r'\n.*?(?=^### |\Z)',s,re.M|re.S);assert m,block;b=m.group(0)
 assert 'routine_reporting.rs' not in b,block
 lines=b.splitlines();i=next((i for i,x in enumerate(lines) if x=='- agent'),1);lines.insert(i,line);b='\n'.join(lines)+'\n\n';p.write_text(s[:m.start()]+b+s[m.end():])
link=V/'crosswalk/decision-links.tsv';old=read_rows(link);assert not any(r['family']=='C-routine_reporting' for r in old)
rows=[];details=[]
items=json.loads((H/'reporting-roles.json').read_text())['active_recommendations']
for x in items:
 matches=[(k,v) for k,v in census.items() if v['path']==x['path'] and (v['symbol']==x['member'] or v['symbol'].endswith('.'+x['member']))];assert len(matches)==1,x
 key,source=matches[0];assert len(source['lines'])==1,key;line=source['lines'][0]
 fn=x['theorem'];assert len(re.findall(r'\bfn\s+'+re.escape(fn)+r'\b',(R/FP).read_text()))==1,fn
 block='install.status'
 if x['member'] in ['_count_in_graph','node_count','count_nodes','get_node_count','get_edge_count','get_label_distribution']:block='graph.default'
 if x['member']=='edge_count':block='structure.multigraph.count'
 rows.append({'block':block,'role':x['role'],'path':source['path'],'symbol':source['symbol'],'pin lines':str(line),'family':'C-routine_reporting','formal item':FP+'::'+fn,'relation':'models','design':'as-built bounded transcription','grade':'Observed (actual Python and executing local SQL; provider frame)'})
 details.append(dict(member=key,block=block,role=x['role'],formal_item=FP+'::'+fn,actual_ast_start=line,recommended_start=x['start_line'],line_corrected=line!=x['start_line'],before_bound=key in before,relation='models',evidence_tier='actual-python-executing-local-sql-provider',scope=x['scope']+'; canonical graph/filter equality; ancillary/native/schema/driver/collation/concurrent snapshot truth excluded',direct_executable_body_verified=False))
assert len(rows)==15 and len({d['member'] for d in details})==15
append(link,rows)
families=V/'families.tsv';f=read_rows(families);assert not any(r['family_id']=='C-routine_reporting' for r in f)
append(families,[{'family_id':'C-routine_reporting','arm':'consolidated','path':'.g5/Verus_verification/models/routine_reporting','kind':'verus','design':'as-built bounded transcription','scope':'raw row/registry kind+grammar+distinct census; scoped physical counts; partial errors/unknown and final graph/node-vector report projection; provider limits explicit','status':'active','recorded result and where':'new here:35 queries=30 ordinary proof+5 recursive;15 full/named ordinary controls; no imports/NLA/hints','local rerun':'results/routine_reporting/20261116T003809Z-prove/receipt.json PASS35;15 EXPECTED_FAIL full+named; V2binding11204checks8actualsource sensitivities; independent exact scratch accepted','premises file':'.g5/Verus_verification/models/routine_reporting/NOTES.md'}])
metadata('.g5/ontology/concepts/install.g5.md','install.status','- Verus: [routine_reporting.rs](../../Verus_verification/models/routine_reporting/routine_reporting.rs) `theorem_raw_catalog_to_final_report`, `theorem_route_tables_never_double_count`, `theorem_registry_kind_and_shape_both_required`, `theorem_failed_table_keeps_other_counts` and `theorem_failure_is_unknown_not_empty`; [scope](../../Verus_verification/models/routine_reporting/NOTES.md). Raw rows and registry/error fields derive partial census and graph/node-vector report knowledge. Actual Python executes local SQL and the final reader; native/index/schema truth, general IRIS comparison/driver semantics, other report fields and cross-read snapshots remain conditional. Label/property/edge-vector errors do not by themselves make graph size unknown.')
for block in ['graph.default','graph.key.two_forms']:
 metadata('.g5/ontology/concepts/graph-scope.g5.md',block,'- Verus: [routine_reporting.rs](../../Verus_verification/models/routine_reporting/routine_reporting.rs) `theorem_scalar_is_raw_scoped_cardinality`, `theorem_default_null_empty_named`, `theorem_empty_filter_is_unfiltered` and `theorem_scoped_failure_propagates`; [scope](../../Verus_verification/models/routine_reporting/NOTES.md). Canonical graph/filter tokens and a faithful SQL comparison frame bind physical row counts, including legacy NULL/default equivalence; all-graph status remains its documented exception. Grouped label cardinality is modeled, while arbitrary tie ordering, validation and native/collation internals remain outside this claim.')
metadata('.g5/ontology/features/graph-structure.g5.md','structure.multigraph.count','- Verus: [routine_reporting.rs](../../Verus_verification/models/routine_reporting/routine_reporting.rs) `theorem_appending_row_counts_physical_multiplicity` and `theorem_scalar_is_raw_scoped_cardinality`; [scope](../../Verus_verification/models/routine_reporting/NOTES.md). SQL/report census counts matching physical rows. This source relation does not establish ordinary writer uniqueness, adjacency callback maintenance or cache correctness.')
(H/'reporting-integrated-roles.json').write_text(json.dumps(dict(family='C-routine_reporting',active_roles=details,newly_bound=sum(not d['before_bound'] for d in details),strengthened=sum(d['before_bound'] for d in details),observation_context='Source/schema acceptance, ancillary/native/index/driver truth and dataclass formatting remain explicit uncredited provider/exclusion context in NOTES. No invented to_dict or forwarding-only member credit.',direct_body_verified=0),indent=2)+'\n')
print(json.dumps(dict(active_roles=15,newly_bound=sum(not d['before_bound'] for d in details),strengthened=sum(d['before_bound'] for d in details),corrected_ast_lines=sum(d['line_corrected'] for d in details))))
