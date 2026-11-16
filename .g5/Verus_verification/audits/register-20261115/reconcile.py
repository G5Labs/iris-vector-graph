"""Apply the reviewed audit plan; preserve stable IDs and the sealed starting records."""
from pathlib import Path as _AuditPath
if (_AuditPath(__file__).resolve().parent / "APPLIED.json").exists():
    raise SystemExit("This audit has been applied. Preserve its reviewed registers; replay regressions.py, components.py or verify.py instead of rebuilding history.")

from pathlib import Path
import collections,hashlib,json,os,re,sys,urllib.parse
H=Path(__file__).resolve().parent;R=H.parents[3];V=R/'.g5/Verus_verification'
I=json.loads((H/'starting-inventory.json').read_text());S=json.loads((H/'source-review.json').read_text());O=json.loads((H/'ontology-start.json').read_text())
reg=json.loads((H/'regressions.json').read_text());comp=json.loads((H/'components.json').read_text());simp=json.loads((H/'simplification-review.json').read_text());questions=json.loads((H/'question-review.json').read_text())
by=collections.defaultdict(list)
for row in reg:
 if row['verdict']=='REPRODUCED_WITH_PASSING_NEIGHBOR':
  for ident in row['ids']:by[ident].append(row['name'])
partial={i:x for x in comp for i in x['ids']}
security_explicit=set('bug-001 bug-002 bug-003 bug-004 bug-led-001 bug-led-005 bug-led-006 bug-led-007 bug-led-008 bug-led-009 bug-led-010 bug-plt-005 bug-plt-006 bug-plt-007 bug-plt-009 bug-plt-013 bug-plt-022 bug-plt-023 bug-plt-025 bug-str-005 bug-str-014 bug-cyp-001 bug-cyp-002 bug-cyp-005 bug-cyp-006 bug-cyp-007 bug-cyp-008 bug-srch-006 bug-srch-008 bug-srch-012 bug-srch-013 bug-srch-017 F-0705 F-0707 F-0711 F-0801 F-0802 F-0814 F-0815 F-0816 F-0818 F-0820 F-0901 F-0902 F-0908 F-1001 F-1002 F-1006 F-1008 F-1009 F-1013 F-1101 F-1108 F-1114 F-1201 F-1302 F-1305 F-1306 F-1401 F-1402 F-1502 F-1503 F-1507 F-1603 F-1604 F-1614 F-1701 F-1709 F-1801 F-1806 F-C0150 F-C0151 F-C0340 F-C0341 F-C0901 F-C1150 F-C1202 F-C1250 F-C1302 F-C1303 F-C1304 F-C1305 F-C1306 F-C1307 F-C1309 F-C1350 F-C1351 F-C1547 F-C1603 F-C1741 F-C1743 F-C1803 F-C1850 F-CS01'.split())
security_pattern=re.compile(r'redact|tenant|privileg|superuser|auth(?:orization|entication|enticated)|read-only|across graphs|every graph|all.graphs|another graph|mix(?:es|ing)? graphs|ignore(?:s)? graphs|erasure leaves.*index|erased.*(?:text|content|vector)|raw text|forg(?:e|ed)|pastes.*(?:text|values|SQL)|32.bit checksum|CRC.32',re.I)
source={x['id']:x for x in S['bugs_issues']}
manual={
'F-0825':('unreachable in checked inputs','The six preserved ordinary parser/translator shape checks did not reach the NULL fall-through; accepted AST reachability remains unestablished. This is bounded caller-unreachability evidence, not a universal proof.'),
'F-0904':('refuted stronger effect on checked build','The preserved Community 2026.1 sync-build failure still allowed three new SQL prepares and the reader answer. The stronger process-poisoning premise was not reproduced; compilation latency and the 2026.3 provider remain separate unresolved questions.'),
'F-C0403':('refuted tested failure consequence','The preserved failed rebuild left all 400 source entries and verify_graph ok. This refutes that tested partial-index loss, while concurrent refill visibility and other failures remain inconclusive.'),
'F-1612':('refuted premise; e2e environment-blocked','The preserved real 50,000-character reads refute the 32,000-default-read premise on the tested CSP streams/build. The deployed REST/web-application gate was not exercised; no global end-to-end refutation is claimed.'),
'bug-str-003':('inconclusive concurrency schedule','The actual preserved degree ABA probe completed 3,129 rounds without a stale answer. That negative run does not establish the required interleaving or prove cache correctness.'),
'F-C1501':('inconclusive provider failure boundary','Ordinary task ownership/persistence observations exist, but atomicity failure is still a conditional save/delete-versus-SQL provider contract; no actual cross-provider failure regression reproduced it.'),
'bug-srch-006':('environment-blocked','The preserved queue probe lacked an embedding configuration with the required width. Queue/model output and final stored vector were never established by that test.'),
'F-1613':('environment-blocked','Community lacks the %AI tool classes used by the public MCP caller. The source binding does not execute that application/provider gate.'),
'bug-plt-020':('environment-blocked','The public %AI MCP tool and real embedding provider are absent. Binding natural-language text as an ID is source evidence, not an observed successful application result.'),
'F-C0606':('inconclusive performance envelope','The old finite latency panel is retained. No repeated comparable native performance experiment on this audit host establishes the declared 1.1x budget across the required envelope.'),
'F-C1102':('inconclusive durability contract','No instance-crash experiment is run. The recorded SynchCommit setting is a source/environment fact; promised acknowledged durability and failure recovery need an owner contract and relevant provider evidence.'),
}
rows=[]
for x in I['bugs_issues']:
 ident=x['id'];s=source[ident];old=s.get('inherited_evidence');e=old['entry']if old else {};obs=json.dumps(e.get('observed',''),ensure_ascii=False)
 if ident in by:level='e2e reproduced';status='active reproduced';reason='Actual supported caller, ordinary inputs, real relevant SQL/native providers and material external-reader contrast, with a passing neighbor.'
 elif ident in partial:level='partial reproduced';status='active partial';reason=partial[ident]['remaining_gate']
 elif ident.startswith('F-C') and ident in ['F-C0811','F-C1711','F-C0111','F-C0511','F-C0512','F-C0513','F-C1011']:
  level='outside review scope';status='stopped candidate unassessed';reason='This starting inventory item was never filed; it points to a stopped investigation. Its drafts/inputs were not opened, assessed or executed.'
 elif ident in security_explicit or security_pattern.search(x['title']):
  level='outside active reproduction scope';status='security defensive review only';reason='Security/privacy/boundary-related claim: only the sealed source and existing evidence were reviewed. No vulnerability reproduction or new offensive investigation was constructed or run. Graph scoping is distinguished from the documented namespace authorization boundary.'
 elif ident in manual:status,reason=manual[ident];level='not reproduced in this audit'
 else:
  level='not reproduced in this audit'
  if re.search(r'Arno|arno.callout|%AI|FHIR repository|repository class|licen[cs]e|Enterprise',x['body']+' '+obs,re.I):
   status='environment-blocked';reason='The cited provider/platform premise is absent from the audit runtime or not established by the saved test. A source/model result cannot substitute for that caller/provider gate.'
  elif 'Decision: Open' not in x['severity']:
   status='historical observation outside active bugs';reason='This starting item was already an observation, duplicate, documentation note or unfiled candidate. Its preserved record is not promoted into an active functional defect without a discriminating regression.'
  else:
   status='inconclusive regression gap';reason='The sealed source/evidence and referenced tests were checked, but no reusable discriminating caller-to-reader regression with an established passing neighbor was identified/executed for this exact trigger in this audit. Historical native reports, component tests and model controls remain evidence; this is not a refutation or a claim of correctness.'
 rows.append(dict(id=ident,title=x['title'],status=status,repro_level=level,reason=reason,tests=by.get(ident,[]),component=partial.get(ident),source_files=s['source_files'],test_files=s['test_files'],existing_evidence_disposition=e.get('disposition'),existing_evidence_source=old['source']if old else None,old_reproduction=x['reproduced'],owners=s['owners'],protected=s['protected_human_status']))
counts=dict(starting={k:len(v)for k,v in I.items()},bugs_by_disposition=dict(collections.Counter(x['status']for x in rows)),bugs_by_repro_level=dict(collections.Counter(x['repro_level']for x in rows)),fresh_native_cases=len(reg),fresh_native_cases_passing=sum(x['verdict']=='REPRODUCED_WITH_PASSING_NEIGHBOR'for x in reg),simplifications=dict(start=55,withdrawn_claims=54,previously_retired=1,active_claims=0),questions=dict(start=146,settled_existing_authority=9,owner_decisions_open=121,historical=2,proof_debt=14),protected_human_determinations=sum(x['protected']for x in rows))
plan=dict(counts=counts,bugs=rows,removed_ids=[x['id']for x in rows if not x['status'].startswith(('active','security'))],kept_ids=[x['id']for x in rows if x['status'].startswith(('active','security'))])
(H/'reconciliation.json').write_text(json.dumps(plan,indent=2)+'\n')
print(json.dumps(counts,indent=2))
if '--apply'not in sys.argv:sys.exit(0)
assert not any(x['protected']for x in rows),'Protected entry requires exact-byte preservation before applying.'

def relink(text,src,dst):
 def one(m):
  url=m[1]
  if '://'in url or url.startswith('#'):return m[0]
  path,mark,frag=url.partition('#');p=(src/urllib.parse.unquote(path)).resolve()
  if not p.is_relative_to(R):return m[0]
  return ']('+os.path.relpath(p,dst).replace(' ','%20')+(mark+frag if mark else '')+')'
 return re.sub(r'\]\(([^)]+)\)',one,text)

def clean(body):
 # Register section prose is not part of the preceding entry.
 return re.split(r'\n## ',body)[0].strip()+'\n\n'

# Every original removed ID remains a stable anchor in the review record and starting snapshot.
archive='# Bug review record — fresh findings audit\n\nThis file is outside the active bug register. All removed starting IDs and historical qualifications remain addressable here. Lack of reproduction is not proof of correctness. The exact sealed starting text is in [start/bugs_issues.md](start/bugs_issues.md); full source/evidence inventories are [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json). Seven stopped, never-filed candidates remain unassessed. No protected human status existed in the starting registers.\n\n'
keep=[];secu=[]
for orig,row in zip(I['bugs_issues'],rows):
 ident=row['id'];b=clean(orig['body'])
 if row['status'].startswith(('active','security')):
  historical=re.search(r'^Reproduced by: ([^\n]*)',b,re.M)
  if row['repro_level']=='e2e reproduced':
   line='Reproduced by: **e2e reproduced** — [fresh pinned-product regressions](audits/register-20261115/regressions.py), cases `'+', '.join(row['tests'])+'`; [actual results and passing neighbors](audits/register-20261115/regressions.json). No provider substitution in these cases.'
   b=re.sub(r'\n\*\*Suspected.*?(?=\n\n)', '', b, count=1, flags=re.S)
  elif row['repro_level']=='partial reproduced':
   line='Reproduced by: **partial reproduced** — [executable component cases](audits/register-20261115/components.py) and [results](audits/register-20261115/components.json). Remaining gate: '+row['reason']
  else:
   line='Reproduced by: **outside active reproduction scope** — defensive source and existing-evidence review only. No new security reproduction was constructed or executed. Historical runtime claims below are not fresh e2e observations.'
  if historical:b=re.sub(r'^Reproduced by: [^\n]*',lambda _:line+'\n\nHistorical reproduction record: '+historical[1],b,count=1,flags=re.M)
  else:
   run=re.search(r'^Run: [^\n]*',b,re.M)
   if run:b=b[:run.end()]+'\n\n'+line+b[run.end():]
   else:b+='\n'+line+'\n'
  b+='\nAudit: [per-ID disposition and sources](audits/register-20261115/reconciliation.json). '+row['reason']+'\n\n'
  (secu if row['status'].startswith('security')else keep).append(b)
 else:
  archive+=f'<a id="{ident}"></a>\n### {row["title"]}\n\nDisposition: **{row["status"]}**. Reproduction level: {row["repro_level"]}.\n\n'+row['reason']+'\n\n'
  if row['existing_evidence_source']:archive+='Existing source disposition: `'+str(row['existing_evidence_disposition'])+'`; ['+row['existing_evidence_source']+']('+os.path.relpath(R/row['existing_evidence_source'],H)+').\n\n'
  archive+='Previous reproduction record: '+relink(orig['reproduced']or 'none recorded',V,H)+'\n\n'
  if row['source_files']:archive+='Source/test check: '+', '.join('['+p+']('+os.path.relpath(R/p,H)+')'for p in row['source_files'][:8])+'. Full indexed file/commit identities are in source-review.json and source-catalog.json.\n\n'
  archive+='[Exact starting entry](start/bugs_issues.md#'+ident+'). Reopen with the exact trigger, supported caller, relevant real providers, final external-reader assertion and a passing neighbor; retain the current governing intent.\n\n'
(H/'bugs-review.md').write_text(archive)
(V/'bugs_issues.md').write_text('# Bugs and issues — iteration 13 findings audit\n\nPinned Git `eceb147d37720658e34b07f279cc267870fd393c`, product `3eaa79cf`. Fresh audit; no uplift iteration or product repair. [Reconciliation and counts](audits/register-20261115/README.md). Removed IDs, refuted bounded triggers, unreachable checked callers, environment blocks and unresolved regression gaps live in the [review record](audits/register-20261115/bugs-review.md). The sealed starting text and historical evidence are preserved.\n\n## Ordinary functional findings with executable reproduction\n\n'+''.join(keep)+'\n## Security-related findings — outside active reproduction scope\n\nThese candidates received defensive source and existing-evidence review only. Their presence does not assert a newly reproduced vulnerability, a new authorization contract or a human approval. The namespace remains the documented authorization boundary.\n\n'+''.join(secu))

# Withdraw complexity claims, preserving every candidate, stable anchor and original run.
simptext='# Design simplifications — audited proposals\n\nThe 54 active claims are withdrawn as unsubstantiated simplifications; the one previously retired counterproposal remains retired. Repair desirability and simpler prose do not establish a smaller Verus model. No product redesign was undertaken. [Per-ID behavior, boundary costs and actual model metrics](audits/register-20261115/simplification-review.md). All original proposal/evidence text remains below for review; it is historical, not an active net-reduction claim.\n\n## Withdrawn claims and retained engineering candidates\n\n'
for x,a in zip(I['design_simplification'],simp):
 b=clean(x['body']);b=re.sub(r' · Decision: Open','',b)
 b=re.sub(r'^Comparison: [^\n]*', 'Comparison: none — no complete comparable proposed model establishes net simplification. Original Verus repair/control configurations and measured counts are retained in the [per-ID comparison](audits/register-20261115/simplification-review.md#'+x['id']+').',b,flags=re.M)
 b+='\nAudit disposition: '+a['disposition']+'. Preserve: '+a['behavior_to_preserve']+' Decision/cost: '+a['boundary_cost']+' [Actual Verus comparison](audits/register-20261115/simplification-review.md#'+x['id']+').\n\n'
 simptext+=b
(V/'design_simplification.md').write_text(simptext)

# Keep settled questions separate from real open decisions, with attribution and canonical owners.
openparts=[];settled=[];historical=[]
for x,a in zip(I['open_questions'],questions):
 b=clean(x['body'])
 if a['status']=='settled existing authority':
  b=re.sub(r' · Decision: Open','',b)
  b+='\nAudit resolution: **settled by existing authority at the pin**, not new maintainer approval. '+a['working']+' [Sources and history](audits/register-20261115/question-review.md#'+a['id']+').\n\n'
  settled.append(b)
 else:
  b+='\nAudit: '+('Working assumption (agent, unratified): '+a['working']+' Options/implications and settling evidence remain explicit in the [per-ID review](audits/register-20261115/question-review.md#'+a['id']+').'if a['status']=='open owner decision'else 'Historical/qualified record retained; see the [per-ID review](audits/register-20261115/question-review.md#'+a['id']+').')+'\n\n'
  (openparts if a['status']=='open owner decision'else historical).append(b)
 if a['owners']:
  ownerlinks=[]
  for owner in a['owners']:
   path=O[owner]['path']if owner in O else O[owner.rsplit('.',1)[0]]['path']
   ownerlinks.append('['+owner+']('+os.path.relpath(R/path,V)+'#'+owner+')')
  # Use an explicit link in the entry, even when the imported record had none.
  target=settled if a['status']=='settled existing authority'else openparts if a['status']=='open owner decision'else historical
  target[-1]+='Canonical owner: '+', '.join(ownerlinks)+'.\n\n'
(V/'open_questions.md').write_text('# Questions — iteration 13 findings audit\n\nEvery starting ID is accounted for in the [146-entry review](audits/register-20261115/question-review.md). 121 policy decisions remain open; nine inherited questions have existing authoritative answers for this pin; two old upstream reports and 14 qualified proof-debt entries are separate. No new human approval was inferred. Current public issue state and disabled Discussions are recorded in [upstream.json](audits/register-20261115/upstream.json).\n\n## Open owner decisions\n\n'+''.join(openparts)+'\n## Settled by existing sources\n\n'+''.join(settled)+'\n## Historical reports and qualified proof debt\n\n'+''.join(historical))

# Add missing canonical questions under existing owners; preserve every preexisting body.
files={p:p.read_text()for p in(R/'.g5/ontology').rglob('*.md')}
newowners={}
for a in questions:
 for owner in a['owners']:
  if owner in O:continue
  parent=owner.rsplit('.',1)[0];assert parent in O,parent
  p=R/O[parent]['path'];s=files[p]
  if owner not in newowners:
   kind=a['kind']or'Q';statement=a['working']if kind=='D'else a['title'].rstrip('?')+'? The working assumption is provisional: '+a['working']
   # Append the child after the parent's complete existing subtree, before its next sibling.
   before,sep,meta=s.partition('## Metadata');matches=list(re.finditer(r'^<a id="([^"]+)"></a>',before,re.M));after=None
   for i,m in enumerate(matches):
    if m[1]==parent:
     j=i+1
     while j<len(matches)and matches[j][1].startswith(parent+'.'):j+=1
     after=matches[j].start()if j<len(matches)else len(before);break
   assert after is not None,parent
   block=f'<a id="{owner}"></a>\n[{kind} · {owner}]\n\n{statement}\n\n'
   before=before[:after]+block+before[after:];s=before+sep+meta
   s+='\n### '+owner+'\n- Expands: [parent](#'+parent+')\n- agent\n'+('- uncertain\n'if kind=='Q'else'')+'- manual-check-review\n\nFindings: ['+a['title']+']('+os.path.relpath(V/'open_questions.md',p.parent)+'#'+a['id']+').\n\nAudit sources, current behavior, options, costs and settling evidence: [question review]('+os.path.relpath(H/'question-review.md',p.parent)+'#'+a['id']+').\n'
   files[p]=s;newowners[owner]=dict(path=str(p.relative_to(R)),kind=kind,parent=parent)
# Metadata records make the canonical source/evidence discoverable for every mapped question.
for a in questions:
 for owner in a['owners']:
  path=O[owner]['path']if owner in O else newowners[owner]['path'];p=R/path;s=files[p]
  note='Audit ('+a['id']+'): '+('Existing authority: '+a['working']if a['status']=='settled existing authority'else 'Open owner decision. Working assumption (agent, unratified): '+a['working'])+' See [current behavior, alternatives and settling sources]('+os.path.relpath(H/'question-review.md',p.parent)+'#'+a['id']+').'
  pat=r'(^### '+re.escape(owner)+r'\n)(.*?)(?=^### |\Z)'
  def add(m):
   body=m[2].rstrip()+'\n\n'+note+'\n\n'
   link=os.path.relpath(V/'open_questions.md',p.parent)+'#'+a['id']
   if link not in body:body+='Findings: ['+a['title']+']('+link+').\n\n'
   return m[1]+body
  s,n=re.subn(pat,add,s,count=1,flags=re.M|re.S);assert n==1,owner;files[p]=s

# Repoint existing editable ontology/register links to removed IDs without losing their anchors.
removed=set(plan['removed_ids'])
def removed_links(text,base):
 def fix(m):
  dest=m[1];p,mark,frag=dest.partition('#')
  if frag in removed and p.endswith('bugs_issues.md'):
   return ']('+os.path.relpath(H/'bugs-review.md',base)+'#'+frag+')'
  return m[0]
 return re.sub(r'\]\(([^)]+)\)',fix,text)
for p,s in files.items():
 s=removed_links(s,p.parent)
 if s!=p.read_text():p.write_text(s)
for p in[V/'bugs_issues.md',V/'design_simplification.md',V/'open_questions.md']:
 p.write_text(removed_links(p.read_text(),p.parent))
(H/'new-canonical-owners.json').write_text(json.dumps(newowners,indent=2)+'\n')
print('Applied reviewed registers and canonical metadata; no production/model/receipt edits.')
