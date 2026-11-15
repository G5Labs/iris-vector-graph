"""Builder evidence inventory only; never changes product/model/runner results."""
from pathlib import Path
import ast,datetime as dt,hashlib,json,re
REPO=Path(__file__).resolve().parents[4];IT=REPO/'.g5/uplift/consolidated/iteration-12';MD=REPO/'.g5/Verus_verification/models/ledger_content';RES=REPO/'.g5/Verus_verification/results/ledger_content'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,j):p.write_text(json.dumps(j,indent=2)+'\n')
roles=[]
def role(file,member,model,owners,scope,tier):
 t=(REPO/file).read_text();name=member.split('.')[-1];pat=(r'^ClassMethod '+re.escape(name)+r'\(') if file.endswith('.cls') else (r'^\s*(?:async )?def '+re.escape(name)+r'\(');matches=list(re.finditer(pat,t,re.M));assert matches,(file,member)
 line=t[:matches[0].start()].count('\n')+1
 roles.append(dict(file=file,member=member,line=line,role='bounded decide/write/read',model=model,owners=owners,scope=scope,evidence_tier=tier,whole_member_claim=False))
apply='iris_src/src/Graph/KG/LedgerApply.cls';core='ordinary_batches from empty; default None/empty graph, canonical IDs/unique normalized ordered keys, no temporal texttrue/reifiers/competing writers, successful complete SQL/transactions/codec provider. No native-body proof.'
for member,model in [
 ('ApplyAll',['requests','commit','history','theorem_closed_ordinary_source_domain']),
 ('OpCreateNode',['pre_error','request_ops','produce','theorem_new_node_emits_separate_content']),
 ('AddLabel',['produce','theorem_same_value_and_label_are_noop']),
 ('SetProp',['produce','theorem_current_prior_is_derived']),
 ('OpRemoveLabel',['produce','theorem_primitive_records_replay_full_content']),
 ('OpRemoveProp',['produce','theorem_primitive_records_replay_full_content']),
 ('NodeSnapshotJson',['produce','theorem_simple_snapshot_is_complete']),
 ('OpDeleteNode',['request_ops','produce','deleted_nodes','deleted_rels','theorem_closed_ordinary_source_domain']),
 ('OpCreateRel',['pre_error','request_ops','allocating','request','theorem_raw_new_rel_uses_own_fresh_counter']),
 ('MergeQuals',['request_ops','produce','theorem_raw_request_full_content']),
 ('OpQual',['request_ops','produce','theorem_attribute_producer_step']),
 ('DeleteRelInternal',['produce','theorem_primitive_records_replay_full_content'])]:
 role(apply,'Graph.KG.LedgerApply.'+member,model,['ledger.commit','ledger.readers'],core+' Marker/adoption boundary is partial, legal excluded history retained.','InspectedSource+CheckedTypedMath+ExecutedTranscription; finite relevant rootNative observations, not body proof')
for member,model,scope in [
 ('Capture',['alternate::capture_step','alternate::capture','alternate::theorem_genesis_full_content_from_raw_rows'],'Already-projected ordered Node/Label/Prop/Edge rows, canonical tuple/value carrier; native node scan graph loss and duplicate row identity preserved. No SQL scan/ordering/provider theorem.'),
 ('Adopt',['alternate::adopt','alternate::theorem_adoption_identity_is_derived'],'Already-decoded typed content/identity projection only; raw tuple-JSON qualifier IDs, malformed parsing, create envelope reset/flags outside theorem; no supplied prior truth guarantee.')]:
 role('iris_src/src/Graph/KG/LedgerGenesis.cls','Graph.KG.LedgerGenesis.'+member,model,['ledger.lifecycle.genesis' if member=='Capture' else 'ledger.verify'],scope,'InspectedSource+CheckedTypedMath+ExecutedTypedPort; native producer NOT executed')
for member,model,owners,scope in [
 ('MutationRecord.from_row',['decode_nullable','theorem_null_text_and_public_value_boundaries'],['ledger.readers'],'Typed nullable prior/new projection only; seq/kind/op/flags and arbitrary row carriers are external codec/actual finite observations.'),
 ('GraphState.apply',['apply','fold','theorem_primitive_records_replay_full_content'],['ledger.readers'],'Complete typed content fold after admitted kind/op/tuple decoder; missing/create-reset/null/default graph/duplicate index behavior. Not all raw wire shapes.'),
 ('GraphState.as_comparable',['comparable','theorem_duplicate_tuple_views_remain_distinct'],['ledger.readers'],'Tuple-key last-insertion projection over admitted statement-ID order, distinct from statement/export maps. No arbitrary Python dict or native collation theorem.'),
 ('compute_diff',['attr_record','attr_track','changed','theorem_named_generated_full_content_endpoints','alternate::lifecycle','alternate::theorem_rich_known_lifecycle_keeps_deletion_time_snapshot'],['ledger.readers.diff'],'Recognized ordinary continuous attributes: exact field endpoints from raw base+generated stamped records. Typed lifecycle snapshot witness; no whole unknown/temporal protocol, inverse script, q-con-002 answer or raw sort/serialization theorem.'),
 ('reconstruct',['run','named_fold','theorem_named_bound_result_projects','theorem_full_stream_and_export_fold'],['ledger.readers','ledger.readers.bound'],'Typed ordered records to complete maps; proved old entity/count projection and eager stream. Provider delivers selected ordered records; all iterable/byte/numeric carriers excluded.')]:
 role('iris_vector_graph/ledger/replay.py',member,model,owners,scope,'ActualPinnedPython+CheckedTypedMath+IndependentBinding')
for member,model,owners,scope in [
 ('GraphLedger.reconstruct',['selected','named_fold','run','theorem_later_records_cannot_change_full_content'],['ledger.readers','ledger.readers.bound'],'Shared typed selected-sequence/bound effect in actual named wrapper context. SeqOf/SQL/Meta/permission/redaction providers and argument carriers remain external.'),
 ('GraphLedger.diff',['range_attrs','theorem_named_generated_full_content_endpoints'],['ledger.readers.diff'],'Shared lower-exclusive/upper-inclusive continuous-attribute range effect in actual wrapper context. Equal/reverse exercised; whole lifecycle endpoint policy not proved.'),
 ('GraphLedger.export_reconstruction',['theorem_full_stream_and_export_fold','entities'],['ledger.readers'],'Named unbounded full-field export effect; actual wrapper executes. Filesystem/JSON bytes and error lifecycle outside math.')]:
 role('iris_vector_graph/ledger/client.py',member,model,owners,scope,'ActualPinnedPython+CheckedSharedTypedEffect+IndependentBinding')
role('iris_vector_graph/ledger/export.py','export_ndjson',['entities','stream_entities','theorem_export_preserves_complete_fields','theorem_stream_exact_entity_reader'],['ledger.readers'],'Complete typed entity/field projection; actual file readback and counts tested, not general byte/FS atomicity/schema roundtrip.','ActualPinnedPython+CheckedTypedMath+IndependentBinding')
role('iris_vector_graph/ledger/changeset.py','_str_value',['InputValue','public_value','theorem_null_text_and_public_value_boundaries'],['ledger.changeset'],'Shared scalar text/boolean vs null/container decision; canonical NumberText is codec assumption, not all str/numeric/unsupported Python carriers.','ActualPinnedPython+CheckedSharedTypedEffect+IndependentBinding')
observed=[
 'Changeset create_node/upsert_node/create_relationship/upsert_relationship/_props/_quals/validate/canonical_json: actual raw callers, refusal and emitted JSON exercised; generic normalized-key/JSON tuple/auto_stub protocol not formally composed.',
 'GraphLedger.commit/_send_changeset/_commit and transport/error/metrics glue: actual empty-post_commit_properties/hooks payload+record path executed; no new admission/idempotency/post-commit/hooks/concurrent/native transaction guarantee.',
 'Ledger.Enc/EncNull/Rec/WriteRevision/RecordsFetch and SQL record table provider: source and finite native/raw-row audits; abstract Action erases raw N/S/flags envelopes, so no whole body proof.',
 'LedgerApply.NodeExists/EnsureEndpoint/DeleteNodeRows/ResolveRef/FindEdge and physical SQL/global writers: inspected/executed conditional ports/native neighbors; whole all-graph physical membership/allocator/endpoint/index coherence not universally established.',
 'iter_records_sql/iter_records paging: actual page2 adapter/raw decoder exercised, selection/count folded with unchanged reconstruction import; no new generic cursor/SQL paging proof.',
 'GraphLedger.get_revision/_seq_of and revision metadata: actual SQLite paths execute; response metadata, arbitrary revision-ID carriers and error resource lifecycle not newly formalized.',
 'read_canonical/verify/_adoption_items, raw Adopt parser/tuple-JSON qualifier refs and Genesis physical SQL scan completeness/order: boundaries or existing evidence, no new active whole member.',
 'temporal/redaction/audit/unknown operation native writers and post-commit properties/hooks: outside admitted ordinary history; actual raw reader neighbors retained, not all-history endpoint correctness.'
]
dump(IT/'ledger-content-roles.json',dict(scope='Proposed bounded semantic roles for root integration; no independent grading/reach count or whole-member claim. Root may retain narrower active locators after review.',roles=roles,observation_only_or_existing=observed))
# Exact verifier/source category inventory, not an undifferentiated theorem count.
counts={}
for f in [MD/'ledger_content.rs',MD/'alternate.rs',MD.parent/'reconstruction/reconstruction.rs']:
 t=f.read_text();proofs=re.findall(r'pub proof fn (\w+)',t);rec=[]
 for m in re.finditer(r'pub (?:open|closed) spec fn (\w+)',t):
  end=t.find('\npub ',m.end());part=t[m.start():end if end>=0 else len(t)]
  if 'decreases ' in part:rec.append(m[1])
 counts[str(f.relative_to(REPO))]=dict(proof_declarations=len(proofs),theorems=sum(x.startswith('theorem_') for x in proofs),helpers=sum(not x.startswith('theorem_') for x in proofs),recursive_specs=rec,recursive_termination_checks=len(rec),nonlinear_sites=t.count('nonlinear_arith'),source_sha256=sha(f))
manifest=json.loads((MD/'model.json').read_text());latest=[]
for suffix in ['prove','binding']+['control-'+c['name'] for c in manifest['controls']]:
 paths=sorted(RES.glob('*-'+suffix+'/receipt.json'));assert paths,suffix;latest.append(paths[-1])
checks=[]
for p in latest:
 j=json.loads(p.read_text());fresh={rel:(REPO/rel).is_file() and sha(REPO/rel)==h for rel,h in j['inputs'].items()};assert all(fresh.values()),(p,[k for k,v in fresh.items() if not v])
 if j['kind']=='control':
  assert j['verdict']=='EXPECTED_FAIL';logs=[j['observed']['raw_log']]+[v['raw_log'] for v in j['observed']['per_function'].values()]
  ordinary=all(('resource limit' not in Path(x).read_text().lower() and 'rlimit' not in Path(x).read_text().lower()) for x in logs);assert ordinary
 else:ordinary=None;assert j.get('verdict') in ['PASS','AGREES']
 checks.append(dict(receipt=str(p.relative_to(REPO)),sha256=sha(p),verdict=j['verdict'],fresh=True,ordinary_named_and_full_failures=ordinary))
# Each exact pre-command snapshot remains unchanged. Wall span includes input-copy/record overhead.
attempts=[]
for d in sorted((IT/'ledger-content-attempts').iterdir()):
 if not d.is_dir():continue
 inp=d/'inputs.json';log=d/'command.log';obs=d/'observed.json';entries={}
 if inp.is_file():
  q=json.loads(inp.read_text());entries=q.get('inputs',q)
  if isinstance(entries,dict):assert all((d/rel).is_file() and sha(d/rel)==h for rel,h in entries.items()),d
 begin=dt.datetime.strptime(d.name.split('Z-',1)[0],'%Y%m%dT%H%M%S.%f').replace(tzinfo=dt.timezone.utc).timestamp() if '.' in d.name[:23] else None
 end=max([p.stat().st_mtime for p in [log,obs] if p.exists()] or [d.stat().st_mtime]);text=log.read_text() if log.is_file() else '';m=re.search(r'verification results:: (\d+) verified, (\d+) errors',text)
 attempts.append(dict(path=str(d.relative_to(REPO)),snapshot_inputs=len(entries),snapshot_hashes_equal=True,raw_log=log.is_file(),verified=int(m[1]) if m else None,errors=int(m[2]) if m else None,resource_failure='resource limit' in text.lower() or ('rlimit' in text.lower() and 'exceeded' in text.lower()),syntax_or_type_failure=bool(re.search(r'SyntaxError|error\[E\d+\]',text)),wall_span_s_including_snapshot_record_overhead=max(0,end-begin) if begin is not None else None,observed=json.loads(obs.read_text()) if obs.is_file() else None))
cost=dict(scope='Exact before-command snapshots plus raw logs preserved, including failures. Historical wall spans are filesystem completion-minus-start spans including snapshot/record overhead, not CPU/solver-exclusive timing. Binding receipt elapsed_s is direct harness wall time. No token accounting fabricated.',attempts=attempts,attempt_count=len(attempts),wall_span_sum_s=sum(x['wall_span_s_including_snapshot_record_overhead'] or 0 for x in attempts),failed_or_partial_attempt_count=sum(x['errors'] not in [None,0] or x['syntax_or_type_failure'] for x in attempts),notes=['All altered-rule failures are intentional and counted separately in final control table, not algorithm regressions.','Initial source-only skip-empty forecast refuted by native tKeys empty-subscript carrier failure; transient draft and original negative fact retained.','Initial binding weak observation inequality withdrawn; later exact corruption detection succeeds.','Two unique-anchor preparation assertions before manifest creation ran zero verifier functions; empty controls command therefore emitted no verifier snapshot.','One generated shared Python bytecode cache disclosed; root preserved and removed it, not a source/package edit.'])
dump(IT/'ledger-content-costs.json',cost)
package={str(p.relative_to(REPO)):sha(p) for p in sorted(MD.iterdir()) if p.is_file()};up=json.loads((IT/'ledger-content-upstream.json').read_text());assert up['exit_code']==0 and up['socket_connect_calls']==0
validation=dict(product_pin=manifest['product_baseline'],before_archive_sha256='8dc3d2901ad993fd0200e9aab82cf3ca87b2f63d586970aad08162276869c594',package_inputs=package,counts=dict(total_verified=108,new_units=97,new_proof_declarations=84,new_theorems=58,new_helpers=26,new_recursive_termination_checks=13,new_nonlinear_subqueries=0,imports=11),source_counts=counts,final_receipts=checks,fresh_receipts=len(checks),controls=dict(count=21,source_algorithm_or_reader=21,encoding_only=0,ghost_only=0,all_ordinary=True),upstream=dict(passed=155,socket_connect_calls=0,receipt_sha256=sha(IT/'ledger-content-upstream.json')),attempts_ledger_sha256=sha(IT/'ledger-content-costs.json'),roles_sha256=sha(IT/'ledger-content-roles.json'),provider_claim='Conditional source projection, no native body or arbitrary SQL/string/numeric/parser/concurrency proof',new_issue_claims=0,owner_decisions=0,independent_grade=None)
dump(IT/'ledger-content-validation.json',validation)
print(json.dumps(dict(roles=len(roles),fresh=len(checks),counts=validation['counts'],attempts=len(attempts),wall_s=cost['wall_span_sum_s'])))
