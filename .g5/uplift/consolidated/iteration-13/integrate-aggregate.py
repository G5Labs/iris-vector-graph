"""Root-only integration of accepted V3 ordinary aggregate results."""
import csv,hashlib,io,json,re
from pathlib import Path
R=Path.cwd();V=R/'.g5/Verus_verification';H=R/'.g5/uplift/consolidated/iteration-13'
review=json.loads((H/'review-aggregate-final-validation.json').read_text());assert review['verdict']=='ACCEPT_BOUNDED_ORDINARY_AGGREGATE_FRAGMENT'
for rel,sha in review['package'].items():assert hashlib.sha256((R/rel).read_bytes()).hexdigest()==sha,rel
C=json.loads((H/'before-reach/census.json').read_text());B=json.loads((H/'before-reach/bindings.json').read_text())
FP='.g5/Verus_verification/models/aggregate_results/aggregate_results.rs';FAMILY='C-aggregate_results'
def read_rows(p):return list(csv.DictReader(io.StringIO(p.read_text()),delimiter='\t'))
def append(p,rows):
 s=p.read_text();fields=list(read_rows(p)[0]);o=io.StringIO();w=csv.DictWriter(o,fields,delimiter='\t',lineterminator='\n');w.writerows(rows);p.write_text(s+o.getvalue())
rows=[];detail=[];all_roles=json.loads((H/'aggregate-source-roles.json').read_text())['roles']
for r in all_roles:
 key=r['path']+'::'+r['symbol'];assert key in C and len(C[key]['lines'])==1,key;line=C[key]['lines'][0];active=r['role']=='bounded-active'
 formal=r['formal_item'] if active else FP+'::theorem_full_output_before_page'
 path,sep,fn=formal.partition('::');assert sep and len(re.findall(r'\bfn\s+'+re.escape(fn)+r'\b',(R/path).read_text()))==1,formal
 tier='inspected-typed-transcription-no-native-execution' if r['path'].endswith('.cls') else 'actual-python-executing-local-sql-provider'
 scope=r['qualifier']
 if not active:scope='Uncredited observation/dependency only: '+scope
 rows.append({'block':'query.aggregation','role':r['symbol']+(' bounded aggregate role' if active else ' unmodeled aggregate context'),'path':r['path'],'symbol':r['symbol'],'pin lines':str(line),'family':FAMILY,'formal item':formal,'relation':'models' if active else 'observes','design':'as-built bounded transcription','grade':('Inspected (typed source transcription; native body unexecuted)' if r['path'].endswith('.cls') else 'Observed (actual Python/local SQL provider; numeric/codec frame)') if active else 'Observation only; not an active source binding'})
 detail.append(dict(member=key,block='query.aggregation',formal_item=formal,relation='models' if active else 'observes',source_role=r['role'],source_claim=r['claim'],scope=scope,evidence_tier=tier if active else 'observation-only',ast_start=line,recommended_start=r['line_start'],line_corrected=line!=r['line_start'],before_bound=key in B,direct_executable_body_verified=False))
active=[r for r in detail if r['relation']=='models'];obs=[r for r in detail if r['relation']=='observes'];assert len(active)==6 and len(obs)==14
p=V/'crosswalk/decision-links.tsv';assert not any(x['family']==FAMILY for x in read_rows(p));append(p,rows)
p=V/'families.tsv';assert not any(x['family_id']==FAMILY for x in read_rows(p));append(p,[{'family_id':FAMILY,'arm':'consolidated','path':'.g5/Verus_verification/models/aggregate_results','kind':'verus','design':'as-built bounded transcription','scope':'raw selected rows/RETURN AST to unique groups/null/distinct/half-unit SUM/AVG/typed scalar/collection/full output/page/raw-name projection; SQL/codec/IEEE/provider limits; native count slice inspected only; OPTIONAL partial bug-agg-001','status':'active','recorded result and where':'62 new queries=46 ordinary proofs+16 recursive;13 unchanged node_read imports; total75;12 source-producer controls full+named, no NLA/hints','local rerun':'V3 proof75 PASS;12 EXPECTED_FAIL ordinary full+named;binding669 comparisons/160 fixtures and7Python+1provider+1actual-observation sensitivities;109upstream; independent exact scratch accepted','premises file':'.g5/Verus_verification/models/aggregate_results/NOTES.md'}])
p=R/'.g5/ontology/features/cypher.g5.md';s=p.read_text();m=re.search(r'^### query\.aggregation\n.*?(?=^### |\Z)',s,re.M|re.S);assert m;b=m.group(0);assert 'aggregate_results.rs' not in b
line='- Verus: [aggregate_results.rs](../../Verus_verification/models/aggregate_results/aggregate_results.rs) `theorem_raw_group_SUM_reaches_typed_scalar_reader`, `theorem_key_enumeration_complete_unique`, `theorem_full_output_before_page` and `theorem_reader_projection_keeps_exact_public_cells`; [scope](../../Verus_verification/models/aggregate_results/NOTES.md). Raw rows and a RETURN AST fragment derive groups, folds, result kind and full output before paging; exact integer/half-unit arithmetic, SQL equality/aggregate operations, JSON spelling/parsing, raw-name generation and collation remain stated provider frames. Native Group/GroupOf/EmitGroups have inspected typed count transcriptions only, under their nonnull/pW1/equality/order premises; the SQL native panels do not execute those bodies. OPTIONAL synthetic fallback remains observed and partial under bug-agg-001.'
lines=b.splitlines();i=next(i for i,x in enumerate(lines) if x=='- agent');lines.insert(i,line);b='\n'.join(lines)+'\n\n'
b=b.replace('formal correspondence is pending the ordinary package and independent replay.','the selected ordinary fragment has been independently replayed within its stated domain.')
p.write_text(s[:m.start()]+b+s[m.end():])
(H/'aggregate-integrated-roles.json').write_text(json.dumps(dict(family=FAMILY,roles=detail,active=6,observations=14,newly_bound=sum(not r['before_bound'] for r in active),strengthened=sum(r['before_bound'] for r in active),active_tiers={'actual-python-executing-local-sql-provider':3,'inspected-typed-transcription-no-native-execution':3},direct_body_verified=0,scope='Only six bounded roles earn source reach; all other observations and native/SQL/codec/AST/provider boundaries remain visible. No whole method or native-body claim.'),indent=2)+'\n')
print(json.dumps(dict(active=6,observations=14,newly_bound=sum(not r['before_bound'] for r in active),strengthened=sum(r['before_bound'] for r in active),corrected_lines=sum(r['line_corrected'] for r in detail))))
