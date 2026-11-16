"""Finalize links, readable canonical questions and inventory-preserving indexes."""
from pathlib import Path as _AuditPath
if (_AuditPath(__file__).resolve().parent / "APPLIED.json").exists():
    raise SystemExit("This audit has been applied. Preserve its reviewed registers; replay regressions.py, components.py or verify.py instead of rebuilding history.")

from pathlib import Path
import collections,csv,json,os,re
H=Path(__file__).resolve().parent;R=H.parents[3];V=R/'.g5/Verus_verification'
P=json.loads((H/'reconciliation.json').read_text());Q=json.loads((H/'question-review.json').read_text());N=json.loads((H/'new-canonical-owners.json').read_text())
short={
'0101':'Supported deployments can read the schema record; callers that cannot read it need an explicit refusal or compatibility policy.',
'0103':'Keep the class deployment path canonical and classify each legacy SQL consumer explicitly before declaring the shipped SQL unsupported.',
'0201':'Omission selects the default graph for graph-aware Python reads; all-graphs reads require an explicit interface.',
'0401':'Retiring a generation must never make an in-flight old count look current; counter reuse needs a separate safety argument.',
'0402':'Allow one publishing rebuild per adjacency structure; a second caller should wait or be refused.',
'0501':'Treat temporal-created endpoint nodes as derived only when their provenance can distinguish them from unrecorded user nodes.',
'0502':'Keep temporal operations in audit history while treating exact temporal replay and full verification coverage as separate unresolved promises.',
'0601':'Name retained search-index contents in removal reports until an owner chooses a purge or complete-erasure policy.',
'0602':'Prefer readers seeing a complete published index or an explicit unavailable result; staging and crash recovery add obligations.',
'0603':'Prefer the best k of the scored candidate set; changing candidate admission and ranking still needs a specified domain.',
'0604':'The documented design has one consumer; enforcement versus an operator-only rule is still undecided.',
'0701':'Serialize builds and mutations per index and publish a complete result; lock ordering and interrupted-build recovery still need a policy.',
'0704':'Reserve __stop__ for stopwords; refusing that index name and moving the list to another global are alternative mechanisms.',
'0802':'Treat mapped labels as namespace-global today; a graph-specific mapping needs an explicit registration and migration policy.',
'0803':'Treat the class path as canonical; support for shipped sql/operators.sql remains a separate owner decision.',
'0804':'Keep the source-decided DDL no-op; whether to add a warning or public documentation remains open.',
'0901':'Require current privilege and index evidence before relying on cached native admission; revocation and database session caching need explicit limits.',
'0903':'Model present read visibility as provider-dependent; no committed-only snapshot promise is inferred from either transport.',
'0904':'Prefer setting a failed compiled entry aside after fallback; its reset, retry and concurrent-reader policy remains undecided.',
'1001':'Prefer an ObjectScript walk of the default graph without requiring Arno; result fields and probability semantics still need a contract.',
'1101':'Keep current namespace-wide bare node identity visible and distinguish an absent default row from a node held only in a named graph.',
'1102':'Prefer refusing settings changes inside an open caller transaction until their nesting behavior is specified.',
'1103':'Treat the cached client guard as current behavior; server enforcement and the exact exemption set still need owner choice.',
'1104':'Prefer keeping maximum operation and reconstruction bounds fixed at genesis, with strict-mode changes treated separately.',
'1304':'Require explicit tenant ID prefixes for the current redaction recipe; graph-only removal of bare node history needs a different identity contract.',
'1502':'Keep ordinary erase as a transient clear; durable removal also needs an explicit feed stop or deregistration policy.',
'1504':'Keep the documented failed-batch retry without advancing the watermark; operator repair versus resource quarantine remains open.',
'1602':'Keep the documented single key and database privileges as the current boundary; a separate admin credential would be a policy change.',
'1604':'Treat /metaPath as default-graph-only today; a supplied graph must eventually be honored or clearly refused.',
'1605':'Treat the generated app as a supported surface while leaving the exact safety-limit parity with the sample app to the owner.',
'1703':'Distinguish implemented adapter methods from current namespace availability; route admission needs the latter evidence.',
'1802':'Rely on a consistent archive only with quiescent writers until a point-in-time capture protocol is specified.',
}
# Use concise statements; detailed recovery history belongs in metadata/evidence.
for p in (R/'.g5/ontology').rglob('*.md'):
 s=p.read_text()
 for a in Q:
  for owner in a['owners']:
   if owner not in N or N[owner]['path']!=str(p.relative_to(R)):continue
   working=short.get(a['id'][3:],a['working'])if a['id'].startswith('HD-')else a['working']
   body=working if a['kind']=='D'else a['title'].rstrip('?')+'?\n\n- Working assumption (agent, unratified): '+working
   pattern=r'(<a id="'+re.escape(owner)+r'"></a>\n\[[DQ] · '+re.escape(owner)+r'\]\n\n)(.*?)(?=^<a id=|^## |\Z)'
   s,count=re.subn(pattern,lambda m:m[1]+body+'\n\n',s,count=1,flags=re.M|re.S);assert count==1,owner
 # Restore exact metadata/body ordering while retaining every old metadata byte within its block.
 before,sep,meta=s.partition('## Metadata');ids=re.findall(r'\[[IDQ] · ([^\]]+)\]',before)
 ms=list(re.finditer(r'^### ([^\n]+)\n',meta,re.M));chunks={m[1]:meta[m.start():ms[i+1].start()if i+1<len(ms)else len(meta)] for i,m in enumerate(ms)}
 assert len(chunks)==len(ids)and set(chunks)==set(ids),str(p)
 s=before+sep+'\n\n'+''.join(chunks[k].rstrip()+'\n\n'for k in ids)
 p.write_text(s)
# Add exact canonical ownership and runtime links for every active ordinary reproduction.
extra={
'F-0304':['temporal.structural.adopt'],'F-0204':['structure.verify'],'F-0403':['structure.verify'],
'F-0208':['structure.multigraph.switch'],'F-0502':['temporal.edge.clock'],'F-0607':['search.scope.indexes.ivf'],'F-0610':['search.knn'],
'F-0803':['query.conformance'],'F-0810':['query.values'],'F-0823':['query.aggregation'],'F-1802':['install.snapshot.routes'],
'F-C0101':['query.conformance'],'F-C0501':['temporal.write.partial-failure'],'F-C0602':['search.knn'],'F-C0715':['search.bm25'],
'F-C0848':['query.writes'],'F-0508':['temporal.stats'],'F-0509':['temporal.edge'],'F-0808':['query.conformance'],
'F-0817':['query.system-procedures.unknown'],'F-0822':['query.writes'],'F-0824':['query.aql'],'F-C0841':['query.conformance'],
'F-C0849':['query.writes'],'F-C1018':['algorithms.op.wcc','algorithms.routing.fallback'],
}
ownerpaths={}
for p in (R/'.g5/ontology').rglob('*.md'):
 for ident in re.findall(r'\[[IDQ] · ([^\]]+)\]',p.read_text().split('## Metadata')[0]):ownerpaths[ident]=p
bugtext=(V/'bugs_issues.md').read_text()
for a in P['bugs']:
 if not a['status'].startswith('active'):continue
 a['owners']=list(dict.fromkeys(a['owners']+extra.get(a['id'],[])));assert a['owners'],a['id']
 owners=[]
 for owner in a['owners']:
  p=ownerpaths[owner];s=p.read_text();note='Audit reproduction: ['+a['id']+']('+os.path.relpath(V/'bugs_issues.md',p.parent)+'#'+a['id']+') is '+a['repro_level']+'; [actual cases, result, neighbor and provider qualifications]('+os.path.relpath(H/('regressions.json'if a['tests']else'components.json'),p.parent)+'). This is product observation, not executable-body verification.'
  pat=r'(^### '+re.escape(owner)+r'\n)(.*?)(?=^### |\Z)'
  def add(m):
   text=m[2].rstrip()+'\n\n'+note+'\n\n';link=os.path.relpath(V/'bugs_issues.md',p.parent)+'#'+a['id']
   if not re.search(r'Findings: [^\n]*'+re.escape('#'+a['id']),text):text+='Findings: ['+a['title']+']('+link+').\n\n'
   return m[1]+text
  s,n=re.subn(pat,add,s,count=1,flags=re.M|re.S);assert n==1;p.write_text(s)
  owners.append('['+owner+']('+os.path.relpath(p,V)+'#'+owner+')')
 pat=r'(<a id="'+re.escape(a['id'])+r'"></a>\n.*?)(?=^<a id=|\Z)'
 bugtext=re.sub(pat,lambda m:m[1].rstrip()+'\n\nCanonical owner and evidence: '+', '.join(owners)+'.\n\n',bugtext,count=1,flags=re.S|re.M)
# The viewer orders actionable entries globally by severity, regardless of evidence scope.
entries=re.findall(r'^<a id="([^"]+)"></a>\n### [^\n]+\n.*?(?=^<a id=|\Z)',bugtext,re.M|re.S)
blocks=re.findall(r'^<a id="[^"]+"></a>\n### [^\n]+\n.*?(?=^<a id=|\Z)',bugtext,re.M|re.S)
blocks=[re.split(r'\n## ',b)[0].strip()+'\n\n'for b in blocks]
order={'Critical':0,'High':1,'Medium':2,'Low':3,'Unranked':4}
blocks.sort(key=lambda b:(0 if 'Decision: Open'in b else 1,order[re.search(r'^Severity: (\w+)',b,re.M)[1]]))
(V/'bugs_issues.md').write_text('# Bugs and issues — iteration 13 findings audit\n\nGit `eceb147d37720658e34b07f279cc267870fd393c`; product `3eaa79cf`. This is a fresh audit, with no product repair or uplift iteration. There are 45 ordinary entries with executable evidence: 41 e2e reproduced and 4 partial reproduced. Another 107 security-related entries are explicitly **outside active reproduction scope** and received defensive source/existing-evidence review only. Entries are ordered by severity; each declares its evidence scope.\n\nAll 434 starting IDs are reconciled. The 282 removed entries retain stable IDs and historical evidence in the [review record](audits/register-20261115/bugs-review.md). Lack of reproduction is not proof of correctness. [Counts, commands and limitations](audits/register-20261115/README.md).\n\n## Findings by severity and evidence scope\n\n'+''.join(blocks))
(H/'reconciliation.json').write_text(json.dumps(P,indent=2)+'\n')
# Preserve source columns and IDs; add an explicit canonical destination and audit result.
for name,records,default in [('findings',P['bugs'],'bugs_issues.md'),('questions',Q,'open_questions.md'),('simplifications',json.loads((H/'simplification-review.json').read_text()),'design_simplification.md')]:
 p=V/'crosswalk'/f'{name}.tsv';rows=list(csv.DictReader(p.open(),delimiter='\t'));fields=list(rows[0]);fields+=[k for k in ['canonical_path','audit disposition','audit evidence']if k not in fields];lookup={a['id']:a for a in records}
 for row in rows:
  a=lookup.get(row['canonical_id']);destination=V/default
  if a:
   if name=='findings'and not a['status'].startswith(('active','security')):destination=H/'bugs-review.md'
   row['audit disposition']=a.get('status',a.get('disposition',''))
   row['audit evidence']=str((H/('reconciliation.json'if name=='findings'else'question-review.json'if name=='questions'else'simplification-review.json')).relative_to(R))
   if a.get('owners'):row['owning block']=';'.join(a['owners'])
  row['canonical_path']=str(destination.relative_to(R))
 with p.open('w',newline='')as f:
  w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
# Keep the index accurate without the old generator's any-non-none == native heuristic.
(V/'findings.md').write_text('''# Findings register — fresh iteration 13 audit

Git `eceb147d37720658e34b07f279cc267870fd393c`, product `3eaa79cf`. This audit changes registers and supporting ontology/evidence only. It does not change production behavior or the frozen seal.

| Register | Starting IDs | Reconciliation |
|---|---:|---|
| [Bugs](bugs_issues.md) | 434 | 41 e2e reproduced; 4 partial reproduced; 107 security-related source-only; 282 moved to the review record |
| [Simplifications](design_simplification.md) | 55 | 54 unsupported reduction claims withdrawn; 1 previously retired proposal retained |
| [Questions](open_questions.md) | 146 | 9 settled by existing authority; 121 owner decisions open; 2 historical reports; 14 qualified proof-debt records |

The [audit handoff](audits/register-20261115/README.md) records actual commands, positive neighbors, substituted dependencies, bounded refutations, caller-unreachability checks, environment blocks and incomplete regressions. Every original ID remains in its live register or the [bug review record](audits/register-20261115/bugs-review.md); [crosswalks](crosswalk/) now carry an explicit canonical_path. No human protection status was present at the start. No new human approval was inferred.

A passing audit regression means its recorded defect contrast and passing neighbor reproduced; it does not mean the product was repaired. A Verus repair/control pair is not a measured design simplification. Security entries remain explicitly outside active reproduction scope.
''')
print('Finalized ownership, metadata order, canonical destinations and counts.')
