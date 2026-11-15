"""Read-only source/receipt audit and local artifact inventory; does not invoke verification."""
from pathlib import Path
import datetime,hashlib,json,re,shlex,shutil
R=Path(__file__).resolve().parents[4];M=R/'.g5/Verus_verification/models/communities';O=Path(__file__).parent;A=O/'communities-attempts';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();write=lambda p,x:p.write_text(json.dumps(x,indent=2)+'\n')
s=(M/'communities.rs').read_text();proofs=[dict(name=m.group(1),line=s[:m.start()].count('\n')+1) for m in re.finditer(r'^pub (?:broadcast )?proof fn (\w+)',s,re.M)];specs=[]
for m in re.finditer(r'^pub (?:open|closed) spec fn (\w+)',s,re.M):
 chunk=s[m.end():];header=chunk[:chunk.index('{')]
 if re.search(r'\bdecreases\b',header):specs.append(dict(name=m.group(1),line=s[:m.start()].count('\n')+1))
count=dict(source_sha256=sha(M/'communities.rs'),source_proof_declarations=len(proofs),source_proofs=proofs,theorem_declarations=sum(x['name'].startswith('theorem_') for x in proofs),lemma_helper_declarations=sum(x['name'].startswith('lemma_') for x in proofs),termination_hint_declarations=['native_pages_termination'],recursive_spec_checks=len(specs),recursive_specs=specs,ordinary_proof_queries=len(proofs)-1,termination_hint_attribution='native_pages_termination is checked via native_pages recursive-spec termination query, not an additional separate verified declaration',extra_nonlinear_arithmetic_subqueries=0,imports=0,total=(len(proofs)-1)+len(specs),no_cheating_token_audit={x:x in s for x in ['assume(','admit(','external_body','by(nonlinear_arith)','rlimit']})
assert count['total']==73 and len(proofs)==66 and len(specs)==8;write(O/'communities-counts.json',count)
roles=[]
def role(path,line,name,kind,claim,qualifier):roles.append(dict(path=path,line_start=line,name=name,role=kind,claim=claim,qualifier=qualifier))
role('iris_src/src/Graph/KG/Algorithms.cls',10,'WCCJson','bounded-active','Raw default-graph owner initialization, synchronous min propagation, changed confirmation, explicit budget refusal and finite termination/minimum correctness.','Mathematical source transcription over finite closed coordinates; weak interpretation requires mirror; native/JSON body execution and broad collation/provider states remain correspondence.')
role('iris_src/src/Graph/KG/Algorithms.cls',93,'CDLPJson','bounded-active','Actual raw-coordinate counts/self exclusion, ordered maximum/tie, synchronous old labels, bounded rounds and parity.','No convergence/quality or all-keyed-row vote promise; normal unique-coordinate projection.')
for line,name,claim in [(43,'Scan','Derived live census with raw HasOther, selected-last-key pagination and value-consuming progress.'),(71,'HasOther','Nonself raw out/in incidence predicate.')]:role('iris_src/src/Graph/KG/Edgeless.cls',line,name,'bounded-active',claim,'Default stable SQL-node/KG edge projection and common admitted order; SQL scan-row counts, cursor lifetime, serialization and malformed global shapes are outside proof.')
for line,name in [(15,'Loners'),(25,'LonersJson')]:role('iris_src/src/Graph/KG/Edgeless.cls',line,name,'observation-only','Native transport/serialization/delegate finite correspondence.','Raw census/pagination logic is represented at Scan; no native serializer proof.')
for line,name,claim in [(21,'loners','Page accumulation, returned cursor value consumption, partial failure discards whole result.'),(36,'loners_sql','Raw default node/edge anti-incidence and self-loop flag.'),(109,'complete_labels','Preserve existing labels, add missing live loners, order final keys.')]:role('iris_vector_graph/_edgeless.py',line,name,'bounded-active',claim,'Typed ordinary maps/IDs and stable framed census; JSON/DBAPI providers, full Python carrier semantics and arbitrary collations qualified.')
role('iris_vector_graph/_engine/algorithms.py',195,'_loners','bounded-active','Native-first whole-result failure then one full SQL census; successful empty distinct.','Outcome/effect relation only; provider exception types/transport body are not proved.')
for line,name in [(805,'kg_WCC'),(829,'kg_CDLP')]:role('iris_vector_graph/_engine/algorithms.py',line,name,'bounded-active','Compose derived core cache result with a separately fresh raw live census and final completion.','Default graph and typed budget/success maps; actual fallback retry details live in binding, not universal formal wire behavior.')
for line,name in [(816,'_kg_WCC'),(842,'_kg_CDLP')]:role('iris_vector_graph/_engine/algorithms.py',line,name,'observation-only','Actual store/direct-Owner dispatch, error retry and final map reader executed in binding.','Formal Failure is an outcome abstraction, not exact retry count/type/message proof.')
role('iris_vector_graph/stores/iris_sql_store.py',921,'_cached_algorithm','bounded-active','Selected admitted small shared-cache key/token/history relation; success-only publication and cached-core/live-census composition.','Param hashing, front cache, cache failure/disabled/large-result branches and concurrent publication are wider than this formal fragment; prior acache_l2 hit retained.')
for line,name in [(662,'_membership_rows'),(2419,'execute_wcc'),(2425,'_execute_wcc'),(2462,'execute_cdlp'),(2471,'_execute_cdlp')]:role('iris_vector_graph/stores/iris_sql_store.py',line,name,'observation-only','Actual pinned strict reader/native fallback/parameter producer/caller executed over raw source ports.','No formal JSON shape parser, native admission body, parameter hash/coercion or exact exception wire theorem.')
write(O/'communities-source-roles.json',dict(owning_ids=['algorithms.op.wcc','algorithms.op.cdlp','algorithms.cache','algorithms.cache.token'],new_census_member_claim='Recommendations only; root owns central membership integration, and existing active members need not count as new.',roles=roles,universal_exclusions=['native acceleration and Owner body correspondence','IRIS/SQL/Python universal collation equivalence','physical keyed-edge policy resolution','arbitrary malformed globals/JSON/coercion','concurrent SQL/KG frames','full cache transport/normalization/front paths']))
# Preserve exact actual generated mutant source along with already-preserved pre-command base+patch.
for attempt in sorted(A.iterdir()):
 if not attempt.is_dir():continue
 copies=[]
 for receipt in attempt.glob('receipts/*/receipt.json'):
  d=json.loads(receipt.read_text())
  if d.get('kind')!='control':continue
  command=d['observed'].get('command','');args=shlex.split(command)
  if len(args)<2:continue
  original=Path(args[1]);dest=attempt/'actual-control-inputs'/d['control']['name']/'communities.rs'
  if original.exists():
   dest.parent.mkdir(parents=True,exist_ok=True)
   if not dest.exists():shutil.copyfile(original,dest)
   assert sha(dest)==sha(original);copies.append(dict(original=str(original),preserved=str(dest.relative_to(R)),sha256=sha(dest),status='exact actual generated input; base source+patch already in pre-command snapshot'))
 if copies:write(attempt/'control-input-copies.json',copies)
ledger=[]
for p in sorted(A.glob('*/result.json')):
 d=json.loads(p.read_text());ledger.append(dict(attempt=str(p.parent.relative_to(R)),kind=d['kind'],start=d['utc_before_command'],end=d.get('utc_after_command'),elapsed_s=d['elapsed_s'],exit_code=d['exit_code'],originals_unchanged=d['originals_unchanged'],snapshot_sha256=sha(p.parent/'snapshot.json'),result_sha256=sha(p),receipt_copies=d.get('receipt_copies',[])))
start=json.loads((O/'communities-start.json').read_text())['time'];now=datetime.datetime.now(datetime.timezone.utc)
write(O/'communities-costs.json',dict(start=start,as_of=now.isoformat(),elapsed_builder_seconds=(now-datetime.datetime.fromisoformat(start)).total_seconds(),attempt_count=len(ledger),command_wall_seconds=sum(x['elapsed_s'] for x in ledger),attempts=ledger,history='Includes every attempted proof/binding/control/upstream wrapper command, ordinary assertion/type/syntax/resource failures and superseded cursor-presence model. Proof declarations are not solver CPU seconds. Raw per-function controls include full+isolated runs in one recorded controls command; all logs preserved. No fixed budget, new native execution or external outage.'))
package={str(p.relative_to(R)):sha(p) for p in sorted(M.iterdir()) if p.is_file()};receipts=[]
for p in sorted((R/'.g5/Verus_verification/results/communities').glob('*/receipt.json')):
 d=json.loads(p.read_text());current=all((R/k).is_file() and sha(R/k)==v for k,v in d['inputs'].items());receipts.append(dict(path=str(p.relative_to(R)),sha256=sha(p),kind=d['kind'],control=d.get('control',{}).get('name'),verdict=d['verdict'],fresh=current,observed=d.get('observed')))
write(O/'communities-final-freshness.json',dict(package=package,receipts=receipts,current_receipts=[x['path'] for x in receipts if x['fresh']],count=count['total']))
print(json.dumps(dict(count=count['total'],proof_declarations=len(proofs),recursive=len(specs),attempts=len(ledger),command_wall_s=sum(x['elapsed_s'] for x in ledger),current_receipts=len([x for x in receipts if x['fresh']]))))
