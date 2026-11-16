"""Complete this concrete audit after the final native panel; not a register generator."""
from pathlib import Path as _AuditPath
if (_AuditPath(__file__).resolve().parent / "APPLIED.json").exists():
    raise SystemExit("This audit has been applied. Preserve its reviewed registers; replay regressions.py, components.py or verify.py instead of rebuilding history.")

from pathlib import Path
import collections,csv,hashlib,json,os,re,subprocess
H=Path(__file__).resolve().parent;R=H.parents[3];V=R/'.g5/Verus_verification';P=json.loads((H/'reconciliation.json').read_text());I=json.loads((H/'starting-inventory.json').read_text());orig={x['id']:x for x in I['bugs_issues']};reg=json.loads((H/'regressions.json').read_text())
assert len(reg)==41 and all(x['verdict']=='REPRODUCED_WITH_PASSING_NEIGHBOR'for x in reg), 'final native panel incomplete'
by={x['id']:x for x in P['bugs']};a=by['F-1003'];a.update(status='active reproduced',repro_level='e2e reproduced',tests=['pagerank_owner_cap'],owners=['algorithms.op.pagerank','algorithms.cache.pagerank'],reason='Actual public engine and ObjectScript Owner list 10000 of 10002 ordinary nodes with score sum below one; a one-node public caller passes. No Arno reader is available, so cross-route equivalence remains untested.')
# A word such as Arno in the historical narrative does not itself establish an environment block.
for ident in ['bug-plt-002','F-C1601','bug-plt-018','F-C1001','F-C1002']:
 by[ident].update(status='inconclusive regression gap',reason='Source and recorded observations were checked. The exact listener lifetime, route/capability, DDL-effect or algorithm-quality assertion has no completed fresh discriminating regression here; mentioning Arno does not make the ordinary fallback unavailable. Historical evidence remains intact; correctness is not inferred.')
for ident in ['F-0108','F-0821','F-1011','F-C1040','bug-test-002','bug-test-003','F-C1240']:
 by[ident].update(status='source observation outside active bugs',reason='This is deployment/documentation/provenance/ownership or harness-scope evidence rather than a reproduced ordinary functional defect. The source observation is retained here; a material supported-caller failure needs its own executable regression.')
P['removed_ids']=[x['id']for x in P['bugs']if not x['status'].startswith(('active','security'))];P['kept_ids']=[x['id']for x in P['bugs']if x['status'].startswith(('active','security'))]
P['counts']['bugs_by_disposition']=dict(collections.Counter(x['status']for x in P['bugs']));P['counts']['bugs_by_repro_level']=dict(collections.Counter(x['repro_level']for x in P['bugs']));P['counts']['fresh_native_cases']=len(reg);P['counts']['fresh_native_cases_passing']=len(reg)
P['incompletely_reproduced_ordinary_ids']=[x['id']for x in P['bugs']if x['id']in P['removed_ids']and x['status']!='stopped candidate unassessed'];P['stopped_unassessed_ids']=[x['id']for x in P['bugs']if x['status']=='stopped candidate unassessed']
(H/'reconciliation.json').write_text(json.dumps(P,indent=2)+'\n')
# Record a literal search of the actual product tests for each claim's named API, plus its linked test evidence.
search=[]
for x in I['bugs_issues']:
 names=[]
 for token in re.findall(r'`([^`]+)`',x['body']):
  m=re.match(r'([A-Za-z_][A-Za-z_0-9.]{4,80})(?:\(|$)',token)
  if m:
   v=m[1]
   if ('_'in v or'.'in v)and not v.startswith(('witness_','theorem_','lemma_','control_','Variant'))and v not in names:names.append(v)
 names=names[:4];cmd=['rg','-l','-F']+[a for n in names for a in ['-e',n]]+['tests']
 if names:
  p=subprocess.run(cmd,cwd=R,capture_output=True,text=True);found=p.stdout.splitlines();code=p.returncode
 else:found=[];code=None
 search.append(dict(id=x['id'],literal_api_terms=names,command=cmd if names else None,exit_code=code,matching_test_files=found,qualification='Literal discovery only. Matches are candidate tests, not assertions or reproductions. Linked tests and source/evidence dispositions are indexed separately.'))
(H/'test-search.json').write_text(json.dumps(search,indent=2)+'\n')
# Move the newly completed Owner-cap case back into the active register.
b=orig['F-1003']['body'];b=re.split(r'\n## ',b)[0].strip();old=re.search(r'^Reproduced by: ([^\n]+)',b,re.M)[1]
line='Reproduced by: **e2e reproduced** — [actual public PageRank regression](audits/register-20261115/regressions.py), `pagerank_owner_cap`; [41-case final results and passing neighbors](audits/register-20261115/regressions.json). Actual IRIS Owner; no Arno route-equivalence claim.'
b=re.sub(r'^Reproduced by: [^\n]+',lambda m:line+'\n\nHistorical reproduction record: '+old,b,count=1,flags=re.M)
b+='\n\nAudit: '+a['reason']+' Canonical owners: [algorithms.op.pagerank](../ontology/features/algorithms.g5.md#algorithms.op.pagerank), [algorithms.cache.pagerank](../ontology/features/algorithms.g5.md#algorithms.cache.pagerank).\n\n'
p=V/'bugs_issues.md';text=p.read_text();blocks=re.findall(r'^<a id="[^"]+"></a>\n### [^\n]+\n.*?(?=^<a id=|\Z)',text,re.M|re.S);blocks.append(b);rank={'Critical':0,'High':1,'Medium':2,'Low':3,'Unranked':4};blocks.sort(key=lambda b:(0 if 'Decision: Open'in b else 1,rank[re.search(r'^Severity: (\w+)',b,re.M)[1]]));p.write_text(text.split('## Findings by severity')[0].replace('45 ordinary','46 ordinary').replace('41 e2e reproduced','42 e2e reproduced').replace('282 removed','281 removed')+'## Findings by severity and evidence scope\n\n'+''.join(x.strip()+'\n\n'for x in blocks))
p=H/'bugs-review.md';text=p.read_text();pat=r'^<a id="F-1003"></a>\n.*?(?=^<a id=|\Z)';text=re.sub(pat,'',text,flags=re.M|re.S)
for a in P['bugs']:
 if a['id']not in P['removed_ids']:continue
 pat=r'(^<a id="'+re.escape(a['id'])+r'"></a>\n### [^\n]+\n\n)Disposition: .*?\n\n.*?\n\n'
 replacement=lambda m:m[1]+'Disposition: **'+a['status']+'**. Reproduction level: '+a['repro_level']+'.\n\n'+a['reason']+'\n\n'
 text=re.sub(pat,replacement,text,count=1,flags=re.M|re.S)
p.write_text(text)
# Supersede historical narrower statements only for the actually observed caller/gate.
notes={
'F-C1018':'Fresh audit qualification: public SQL GraphStore execute_wcc returns an error for the accepted node ID components. The public engine kg_WCC succeeds by falling back to the Owner. The fresh regression does not claim that the engine WCC call fails.',
'F-C0849':'Fresh audit qualification: the real stored qualifiers are invalid JSON; on this audit build RETURN r.q raises a CY_REL_PROP SQL error. The earlier null result is historical and is not claimed universal.',
'F-0817':'Intent qualification: empty success is reproduced. Whether an unknown procedure must be refused remains the canonical open policy question; this is not an owner-ratified semantic rule.',
'bug-plt-004':'Fresh audit qualification: two archived parents in the same graph reproduce the first-column merge skip on this schema. The initial one-parent-per-graph/shared-ID attempt succeeded and is preserved as a refuted subcase; it does not refute all merge-loss cases.',
'F-1802':'Fresh audit qualification: the 41-case panel exercises the two-parents-in-one-graph skip and preserves an existing live graph. The historical routed-vector parent case is not rerun under an asserted identical physical column order.',
}
p=V/'bugs_issues.md';text=p.read_text()
for ident,note in notes.items():text=re.sub(r'(^<a id="'+re.escape(ident)+r'"></a>\n.*?)(?=^<a id=|\Z)',lambda m:m[1].rstrip()+'\n\n'+note+'\n\n',text,count=1,flags=re.M|re.S)
p.write_text(text)
p=R/'.g5/ontology/features/algorithms.g5.md';text=p.read_text()
for owner in ['algorithms.op.pagerank','algorithms.cache.pagerank']:
 note='Audit reproduction: [F-1003](../../Verus_verification/bugs_issues.md#F-1003) is e2e reproduced through the actual engine/Owner cap, with a passing small graph; [results](../../Verus_verification/audits/register-20261115/regressions.json). Arno route equivalence is untested.'
 text=re.sub(r'(^### '+re.escape(owner)+r'\n)(.*?)(?=^### |\Z)',lambda m:m[1]+m[2].rstrip()+'\n\n'+note+'\n\nFindings: [Global PageRank output cap](../../Verus_verification/bugs_issues.md#F-1003).\n\n',text,count=1,flags=re.M|re.S)
p.write_text(text)
# Repoint any editable references to the now-reproduced case; old archives remain immutable.
for p in list((R/'.g5/ontology').rglob('*.md'))+[V/n for n in ['bugs_issues.md','open_questions.md','design_simplification.md']]:
 text=p.read_text();text=re.sub(r'\]\([^)]*audits/register-20261115/bugs-review\.md#F-1003\)',']('+os.path.relpath(V/'bugs_issues.md',p.parent)+'#F-1003)',text);p.write_text(text)
for name,lookup,default in [('findings',by,'bugs_issues.md')]:
 p=V/'crosswalk'/f'{name}.tsv';rows=list(csv.DictReader(p.open(),delimiter='\t'));fields=list(rows[0])
 for row in rows:
  x=lookup.get(row['canonical_id'])
  if x:
   row['canonical_path']=str((H/'bugs-review.md'if x['id']in P['removed_ids']else V/default).relative_to(R));row['audit disposition']=x['status']
   if x['owners']:row['owning block']=';'.join(x['owners'])
 with p.open('w',newline='')as f:w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
p=V/'findings.md';p.write_text(p.read_text().replace('41 e2e reproduced','42 e2e reproduced').replace('282 moved','281 moved'))
# Remove the inherited contradictory generic owner wording from already-settled entries.
p=V/'open_questions.md';text=p.read_text()
for x in json.loads((H/'question-review.json').read_text()):
 if x['status']!='settled existing authority':continue
 pat=r'(^<a id="'+re.escape(x['id'])+r'"></a>\n.*?)(?=^<a id=|\Z)'
 def fix(m):
  b=m[1];b=re.sub(r'^- Owner: [^\n]+','- Authority: the attributable source documented in the audit resolution below; no new maintainer approval is claimed.',b,flags=re.M);b=b.replace('not re-checked here','re-checked against the pin in this audit');return b
 text=re.sub(pat,fix,text,count=1,flags=re.M|re.S)
text=text.replace('Two public reports against older releases','Two public reports against older releases')
text+='\nPublic-report qualification: upstream issues #12 and #13 were still open when checked. Fixed-at-pin here refers to the pinned changelog and preserved regression evidence, not a GitHub issue closure or a new maintainer approval. See [public source snapshot](audits/register-20261115/upstream.json).\n';p.write_text(text)
print(json.dumps(P['counts'],indent=2))
