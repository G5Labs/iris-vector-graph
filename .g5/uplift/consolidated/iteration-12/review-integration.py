"""Read-only final integration audit. No test/prover/native/source/Git mutation."""
from pathlib import Path
import ast,collections,csv,datetime,hashlib,io,json,os,re,subprocess,time
REPO=Path('/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph');H=Path(__file__).resolve().parent;BEFORE='9de67a2841e6250d322f73bdd951bbe121867340'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def dump(j):return json.dumps(j,sort_keys=True,separators=(',',':')).encode()
start=time.monotonic();checks=[];inputs={}
def check(name,ok):checks.append(dict(check=name,passed=bool(ok)));assert ok,name
def read(rel):
 p=REPO/rel;inputs[rel]=sha(p);return p.read_text()
# Exact published foundation bytes only, restricted read-only Git object reads.
old={}
for rel in ['.g5/Verus_verification/crosswalk/decision-links.tsv','.g5/Verus_verification/families.tsv','.g5/ontology/features/algorithms.g5.md','.g5/ontology/features/ledger.g5.md','.g5/uplift/consolidated/iteration-11/builder-scores.json']:
 b=subprocess.run(['git','-C',str(REPO),'show',BEFORE+':'+rel],check=True,capture_output=True).stdout;old[rel]=b;dest=H/'review-integration-before'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
linksrel='.g5/Verus_verification/crosswalk/decision-links.tsv';text=read(linksrel);rows=list(csv.DictReader(io.StringIO(text),delimiter='\t'));oldrows=list(csv.DictReader(io.StringIO(old[linksrel].decode()),delimiter='\t'))
check('exact307 old link bytes retained as prefix',text.encode().startswith(old[linksrel]) and len(oldrows)==307)
new=rows[len(oldrows):];active=[r for r in new if r['relation'] in ('models','proves','witnesses')];obs=[r for r in new if r['relation']=='observes'];check('355links with48append35active13observations',len(rows)==355 and len(new)==48 and len(active)==35 and len(obs)==13)
famrel='.g5/Verus_verification/families.tsv';ft=read(famrel);families={r['family_id']:r for r in csv.DictReader(io.StringIO(ft),delimiter='\t')};of={r['family_id']:r for r in csv.DictReader(io.StringIO(old[famrel].decode()),delimiter='\t')};check('exact two families added',set(families)-set(of)=={'C-communities','C-ledger_content'});check('prior family rows unchanged',all(families[k]==v for k,v in of.items()))
before=load(H/'before-reach/bindings.json');after=load(H/'after-reach/bindings.json');census=load(H/'after-reach/census.json');check('same4130census',census==load(H/'before-reach/census.json') and len(census)==4130)
check('208to231 with23new lost0',len(before)==208 and len(after)==231 and not set(before)-set(after) and len(set(after)-set(before))==23)
check('35active12strengthened23new',len({r['path']+'::'+r['symbol'] for r in active})==35 and sum(r['path']+'::'+r['symbol'] in before for r in active)==12)
anchors=set();blocks=[]
for p in (REPO/'.g5/ontology').rglob('*.md'):
 s=p.read_text();ids=re.findall(r'<a id="([^"]+)">',s);anchors.update(ids);blocks.extend(re.findall(r'^\[[A-Z] · ([^\]]+)\]',s,re.M))
check('403owning blocks no addedblocks',len(blocks)==403 and len(set(blocks))==403)
lookup={};details=[]
for r in new:
 key=r['path']+'::'+r['symbol'];check('source locator '+key,key in census and census[key]['lines']==[int(r['pin lines'])])
 check('existing owner '+r['block'],r['block'] in anchors)
 fp,sep,fn=r['formal item'].partition('::');s=read(fp);check('formal locator '+r['formal item'],bool(sep) and len(re.findall(r'\bfn\s+'+re.escape(fn)+r'\b',s))==1)
 check('family active '+r['family'],families[r['family']]['status'].startswith('active'))
 details.append(dict(member=key,relation=r['relation'],owner=r['block'],line=int(r['pin lines']),formal=r['formal item'],grade=r['grade'],newly_bound=key not in before if r in active else False))
# Evidence grades are per-fragment; rows never claim executable body verification.
mo=load(H/'member-outcomes.json');members=mo['members'];am=[m for m in members if m['new_model_or_domain']];tiers=collections.Counter(m['evidence_tier'] for m in am)
check('35bounded member tiers30native2python3transcription',len(am)==35 and tiers=={'finite-native-correspondence':30,'actual-python-unit':2,'inspected-executed-transcription':3})
check('no whole member or executable body claim',all(not m['whole_member_claim'] and not m['direct_executable_body_verified'] for m in members))
by={m['member']:m for m in members};check('unexecuted producer tiers',all(by[k]['evidence_tier']=='inspected-executed-transcription' for k in ['iris_src/src/Graph/KG/LedgerGenesis.cls::Capture','iris_src/src/Graph/KG/LedgerGenesis.cls::Adopt','iris_src/src/Graph/KG/LedgerApply.cls::OpRemoveProp']))
check('python-only tiers',all(by[k]['evidence_tier']=='actual-python-unit' for k in ['iris_vector_graph/ledger/replay.py::GraphState.as_comparable','iris_vector_graph/ledger/changeset.py::_str_value']))
check('OpQual set-only native/removal ordering provider','set/noop only' in by['iris_src/src/Graph/KG/LedgerApply.cls::OpQual']['scope'] and 'ordering' in by['iris_src/src/Graph/KG/LedgerApply.cls::OpQual']['scope'])
check('Adopt lifecycle owner not verify',by['iris_src/src/Graph/KG/LedgerGenesis.cls::Adopt']['block']=='ledger.lifecycle')
check('snapshot diff owner',by['iris_src/src/Graph/KG/LedgerApply.cls::NodeSnapshotJson']['block']=='ledger.readers.diff')
# Scoped builder judgments: same37 decisions/grades; all12 overlapping additions retained.
score=load(H/'builder-scores.json');base=load(H/'before-builder-scores.json');check('baseline bytes equal sealed11', (H/'before-builder-scores.json').read_bytes()==old['.g5/uplift/consolidated/iteration-11/builder-scores.json'])
check('baseline provenance digest',score['baseline_sha256']==sha(H/'before-builder-scores.json'))
bmap={r['id']:r for r in base['rows']};carried=[r for r in score['rows'] if r['cohort']=='carried37'];extensions=[r for r in score['rows'] if r['cohort']!='carried37'];formats=[]
for r in carried:
 b=bmap[r['id']];check('carried decision and grades '+r['id'],r['decision']==b['decision'] and r['owner']==b['owner'] and r['before']==b['after'] and r['after']==b['after'] and not r['iteration12_changes_exact_grade'])
 matches=[fmt for fmt,text in [('sortedcompact',dump(b)),('sorteddefault',json.dumps(b,sort_keys=True).encode())] if hashlib.sha256(text).hexdigest()==r['baseline_row_sha256']];check('baseline row digest '+r['id'],bool(matches));formats.extend(matches)
check('49rows37carried11supported1partial',len(score['rows'])==49 and len(carried)==37 and len(extensions)==12 and sum(r['status']=='SUPPORTED_BOUNDED_EXTENSION' for r in extensions)==11 and next(r for r in extensions if r['id']=='L4')['after']['model']['grade']=='partial')
check('source frozen origins exist',all((H.parent.parent/str(p)).is_file() or (H.parent/str(p)).is_file() for r in extensions for p in r['source_frozen_origins']))
# Primary-authority scope correction and inherited marker consequence, without policy or issue-count changes.
a=load(H/'algorithms-owner-scope-correction.json');pres=REPO/a['before_preserved'];alg=read(a['path']);check('exact old algorithm owner preserved',pres.read_bytes()==old[a['path']] and sha(pres)==a['before_sha256']);check('PRPPR direction scope corrected from authority',a['replacement'] in alg and a['original'] not in alg and a['new_blocks']==a['new_issues']==a['new_owner_decisions']==0)
md=load(H/'marker-disposition.json');register=read('.g5/Verus_verification/bugs_issues.md');entry=register[register.index('<a id="F-C0351">'):];entry=entry[:entry.find('\n<a id=',1)] if '\n<a id=' in entry[1:] else entry
check('marker preserved old/current evidence and unchangedcounts',sha(H/md['original_entry_preserved'])==md['original_entry_sha256'] and sha(H/md['after_entry_preserved'])==md['after_entry_sha256'] and (H/md['after_entry_preserved']).read_text() in register and md['new_issue_ids']==0 and md['counts_unchanged'] and not md['severity_changed'] and md['owner_decisions']==0)
# Independent fresh hashes for the global file/name inventory plus per-package comparator inputs.
stamp=load(H/'correspondence-inputs.json');product={str(p.relative_to(REPO)):sha(p) for n in ['iris_vector_graph','iris_src','api'] for p in (REPO/n).rglob('*') if p.is_file() and p.suffix in ['.py','.cls','.sql']};formal={str(p.relative_to(REPO)):sha(p) for p in (REPO/'.g5/Verus_verification/models').rglob('*') if p.is_file() and (p.suffix=='.rs' or p.name=='model.json')}
for p in (REPO/'.g5/Verus_verification/models').glob('*/binding.py'):product[str(p.relative_to(REPO))]=sha(p)
for rel in ['tools/binding_common.py','tools/correspondence_gate.py','crosswalk/decision-links.tsv','families.tsv']:product['.g5/Verus_verification/'+rel]=sha(REPO/'.g5/Verus_verification'/rel)
for rel in ['run_verus.py','SOURCE.json','SOURCE-consolidated.json']:formal['.g5/Verus_verification/'+rel]=sha(REPO/'.g5/Verus_verification'/rel)
for key in stamp['formal']:
 if key.startswith('external:'):formal[key]=sha(Path(key[len('external:'):]))
check('global complete input/name inventory current',stamp==dict(product=product,formal=formal))
fc=load(H/'freshness-controls.json');check('24shadow fixtures expected activeunchanged',len(fc['controls'])==24 and fc['all_expected'] and not fc['active_inputs_mutated'])
for r in fc['controls']:
 if r['label']=='fresh':check('fresh fixture',r['exit']==0 and r['proof']==r['correspondence']=='REUSABLE_INPUTS')
 elif r['label'].startswith(('native-fact','communities-port.py','ledger_content-functional_model.py','ledger_content-sql_provider.py','ledger_content-alternate_ports.py')):check('package-only invalidation '+r['label'],any(r['package_stale_inputs'].values()) and r['proof']==r['correspondence']=='REUSABLE_INPUTS')
 else:check('global invalidation '+r['label'],r['exit']==1 and r['correspondence']=='STALE_ALL')
validation=load(H/'validation.json');check('root integration gate and currentcounts',validation['consolidated_gate']=={'verdict':'PASS','ontology_blocks':403,'source_links':355} and validation['new_units']['total']==170 and validation['controls']['total']==33 if isinstance(validation['controls'],dict) and 'total' in validation['controls'] else validation['new_units']['total']==170)
check('gate raw record passes','\nPASS\n' in read('.g5/uplift/consolidated/iteration-12/consolidated-gate.log'))
# Frozen source/model/NOTES inputs remain equal to independent scratch; no repeated proof/tests.
for name in ['communities','ledger-content']:
 v=load(H/('review-'+name+'-validation.json'));check('frozen package unchanged '+name,all(sha(REPO/p)==h for p,h in v['package'].items()))
for p in ['role-audit.json','member-outcomes.json','reach-delta.json','validation.json','builder-scores.json','freshness-controls.json','correspondence-inputs.json','HANDOFF.md']:
 q=H/p;inputs[str(q.relative_to(REPO))]=sha(q)
out=dict(verdict='PASS_BOUNDED_INTEGRATION',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,new_link_rows=details,counts=dict(links_before=307,links_after=355,appended=48,active=35,observations=13,reach_before=208,reach_after=231,denominator=4130,new_members=23,lost=0,strengthened=12,blocks=403,score_rows=49,carried_decisions_grades=37,bounded_supported_extensions=11,broad_partial_extension=1,finite_native_correspondence_members=30,actual_python_only=2,inspected_typed_transcription=3),source_metadata_sha256=inputs,baseline_row_digest_format=sorted(set(formats)),scope_qualifications=['All35active links are bounded source-side mathematical/observed fragments, not whole members or executable body verification.','Native OpQual tier covers set/noop only; removal/replace and cross-key order remain transcription/provider claims.','Capture/Adopt/OpRemoveProp have no relevant bounded native producer execution; as_comparable/_str_value are Python-only.','No-marker/default ordinary producer profile is partial for lawful marker/named histories; marker6 strengthens existingF-C0351 without newID/severity/policy.','Global stamp and per-package flat helper/native fact hashes are distinct necessary checks; neither proves live provider freshness.','Score extensions are overlapping purposive microdecisions, not an independent grade or pooled project-wide rate.','Prior archive byte preservation is root-audited; this reviewer compares selected sealed11 Git object bytes and current package/source hashes, not whole external tarballs.'],reviewer_native_calls=0,reviewer_tests_or_prover_runs_for_integration=0,git_operations='Five restricted read-only show operations on specified sealed11 metadata files; no Git state change.',private_evaluator_inspected=False,elapsed_s=time.monotonic()-start)
(H/'review-integration.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(verdict=out['verdict'],checks=len(checks),counts=out['counts'],elapsed_s=out['elapsed_s'])))
