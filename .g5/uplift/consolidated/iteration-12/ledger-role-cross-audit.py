"""Independent read-only role/source/formal/evidence cross-audit; no verifier or runtime calls."""
from pathlib import Path
import ast,datetime,hashlib,json,re
R=Path(__file__).resolve().parents[4];O=Path(__file__).parent;P=R/'.g5/Verus_verification/models/ledger_content';PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();j=lambda p:json.loads(p.read_text());candidate={str(p.relative_to(R)):sha(p) for p in P.iterdir() if p.is_file()};proposal=O/'ledger-content-roles.json';candidate[str(proposal.relative_to(R))]=sha(proposal)
roles=j(proposal)['roles'];before=j(O/'before-reach/bindings.json');census=j(O/'before-reach/census.json');summary=j(O/'before-reach/summary.json');ontology=(R/'.g5/ontology/features/ledger.g5.md').read_text()
# One deliberately narrow checked proof and one semantic owner per role.
rec=[
 ('theorem_closed_ordinary_source_domain','ledger.commit','Ordinary admitted batches from empty preserve full typed store/log correspondence; no transaction/provider-body proof.'),
 ('theorem_new_node_emits_separate_content','ledger.commit','New ordinary existing-context-free node with one admitted nonempty label/property emits three separate full-content records.'),
 ('theorem_same_value_and_label_are_noop','ledger.commit','Joint admitted existing-label/same-property witness emits no records; not all standalone AddLabel preconditions.'),
 ('theorem_current_prior_is_derived','ledger.readers.diff','Changed existing-node property records the derived current prior; successful complete SQL projection is external.'),
 ('theorem_primitive_records_replay_full_content','ledger.commit','Typed RemoveLabel primitive record/effect and failure-without-prefix correspondence.'),
 ('theorem_primitive_records_replay_full_content','ledger.commit','Typed RemoveProp primitive record/effect and failure-without-prefix correspondence; not native-observed here.'),
 ('theorem_simple_snapshot_is_complete','ledger.readers.diff','Complete typed deletion snapshot of a node with no default incident relationship; SQL row scan/JSON bytes external.'),
 ('theorem_closed_ordinary_source_domain','ledger.commit','Default ordinary strict/detach request composition within admitted closed history; no named/all-global deletion theorem.'),
 ('theorem_raw_new_rel_uses_own_fresh_counter','ledger.commit','New tuple with empty qualifier set uses its own fresh counter under the stated allocation/endpoint frame.'),
 ('theorem_raw_request_full_content','ledger.commit','Admitted normalized ordered qualifier writes in raw relationship request replay to its typed content effect; physical PersistQuals/SQL is external.'),
 ('theorem_attribute_producer_step','ledger.commit','Typed ordinary qualifier attribute-step record truth; native evidence is set branch only, remove/replace remain port/transcription.'),
 ('theorem_primitive_records_replay_full_content','ledger.commit','Typed DeleteRel effect and full prior snapshot record replay; physical SQL/index closure external.'),
 ('alternate::theorem_genesis_full_content_from_raw_rows','ledger.lifecycle.genesis','Already-projected ordered raw Row stream generates replay-equivalent full typed content; SQL scan completeness/order and raw codec external.'),
 ('alternate::theorem_adoption_identity_is_derived','ledger.lifecycle','Decoded create_rel tuple selects existing identity or own next counter, ignoring supplied ID; not raw parser/verify/adoption-history correctness.'),
 ('theorem_null_text_and_public_value_boundaries','ledger.readers','Nullable prior/new projection for normalized boolean null flag and admitted text/None cells; other row fields/flag decoding external.'),
 ('theorem_primitive_records_replay_full_content','ledger.readers','Complete typed reader effect for admitted producer-emitted primitive records; not arbitrary raw kind/tuple/flag parsing.'),
 ('theorem_duplicate_tuple_views_remain_distinct','ledger.readers','Two distinct statement IDs for one tuple retain statement/export entries while comparable tuple view takes later insertion; no universal Python dict/collation theorem.'),
 ('theorem_named_generated_full_content_endpoints','ledger.readers.diff','Continuous recognized attributes, lo<hi, generated successful ordinary records: exact named full-field endpoints; lifecycle/order/inverse byte policy excluded.'),
 ('theorem_named_bound_result_projects','ledger.readers.bound','Typed full-state run has exactly the inherited structural bound/refusal projection; provider-selected records/byte carriers external.'),
 ('theorem_later_records_cannot_change_full_content','ledger.readers.bound','Named typed fold/result is unchanged by later-sequence records; SQL SeqOf/Meta/permissions providers external.'),
 ('theorem_named_generated_full_content_endpoints','ledger.readers.diff','Shared forward lower-exclusive/upper-inclusive continuous-attribute effect, lo<hi; equal/reverse wrappers only observed in binding.'),
 ('theorem_full_stream_and_export_fold','ledger.readers.bound','Named unbounded export reconstruction equals typed selected fold; filesystem/wire serialization not formalized.'),
 ('theorem_export_preserves_complete_fields','ledger.readers','Every typed entity view includes complete node labels/properties or relationship tuple/qualifiers; no byte ordering/atomicity/FS theorem.'),
 ('theorem_null_text_and_public_value_boundaries','ledger.changeset','Public Null/nested-container refusal and literal-text-vs-null distinctions in typed scalar fragment; arbitrary numeric str/coercion/exception carrier external.'),
]
assert len(rec)==len(roles)==24
class Definitions(ast.NodeVisitor):
 def __init__(self):self.stack=[];self.defs={}
 def visit_ClassDef(self,n):
  self.defs['.'.join(self.stack+[n.name])]=n.lineno;self.stack.append(n.name)
  for x in n.body:self.visit(x)
  self.stack.pop()
 def visit_FunctionDef(self,n):self.defs['.'.join(self.stack+[n.name])]=n.lineno
 visit_AsyncFunctionDef=visit_FunctionDef
native={n:j(O/n) for n in ['root-ledger-native.json','root-ledger-marker-native.json','root-ledger-qualkeys-native.json']}
main=native['root-ledger-native.json'];marker=native['root-ledger-marker-native.json']
mainlabels=[x['label'] for x in main['cases']];markerlabels=[x['label'] for x in marker['cases']]
anchors={
 0:['new node separate record expansion','changed setter actual priors'],1:['new node separate record expansion'],2:['existing upsert emits no create node','identical writes emit no records'],3:['changed setter actual priors'],4:['changed setter actual priors'],6:['simple delete complete snapshot','changed-before-delete complete deletion snapshot'],7:['simple delete complete snapshot','default deletion leaves named relationship'],8:['relationship create plus separate qualifier records','tuple-only create new'],9:['relationship create plus separate qualifier records','identical writes emit no records'],10:['changed setter actual priors'],11:['changed-before-delete complete deletion snapshot'],14:['new node separate record expansion'],15:['initial complete node content','earlier named cutoff retains complete content'],17:['continuous-life restored net diff empty'],18:['earlier named cutoff retains complete content','earlier cutoff eager stream complete content'],19:['earlier named cutoff retains complete content'],20:['continuous-life restored net diff empty'],21:['earlier cutoff NDJSON full entities'],22:['earlier cutoff NDJSON full entities'],23:['ordinary null setter refuses before commit']}
rows=[];inputs={str(proposal.relative_to(R)):sha(proposal)}
for i,(x,(proof,owner,scope)) in enumerate(zip(roles,rec)):
 path=R/x['file'];symbol=x['member'].split('.')[-1] if path.suffix=='.cls' else x['member'];key=x['file']+'::'+symbol;entry=census.get(key);assert entry,key
 if path.suffix=='.py':defs=Definitions();defs.visit(ast.parse(path.read_text()));line=defs.defs[symbol]
 else:
  found=list(re.finditer(r'^ClassMethod\s+'+re.escape(symbol)+r'\s*\(',path.read_text(),re.M));assert len(found)==1;line=path.read_text()[:found[0].start()].count('\n')+1
 assert line in entry['lines'];assert sha(path)==sha(PIN/x['file']);inputs[x['file']]=sha(path)
 source=P/'alternate.rs' if proof.startswith('alternate::') else P/'ledger_content.rs';name=proof.split('::')[-1];match=re.search(r'^pub (?:broadcast )?proof fn '+re.escape(name)+r'\(',source.read_text(),re.M);assert match,proof;proofline=source.read_text()[:match.start()].count('\n')+1
 assert '<a id="'+owner+'">' in ontology,owner
 if i in [12,13]:tier='InspectedSource + CheckedTypedTranscription + ExecutedTypedPort ONLY';execution='No relevant actual Python/ObjectScript/native producer execution. Public enable on empty was explicitly not relevant Capture evidence; ordinary create temporal-row takeover is not LedgerGenesis.Adopt.'
 elif i==5:tier='InspectedSource + CheckedTypedTranscription + ExecutedLocalSourcePort';execution='No OpRemoveProp in main/marker completed native operation panel; actual local Python Changeset/reader path is not native ObjectScript execution.'
 elif i<12:tier='InspectedSource + CheckedTypedTranscription + ExecutedLocalSourcePort + RelevantFiniteNativeWorkflow';execution='Finite root observation only; OpQual set branch only; no body, parser, physical SQL, all-mode, collation or concurrency proof.'
 elif i==16:tier='ActualPinnedPython + CheckedTypedTranscription + IndependentLocalBinding';execution='as_comparable is directly called in local raw_readers binding; no direct root native-backed as_comparable call found.'
 elif i==23:tier='ActualPinnedPython + CheckedSharedTypedEffect + IndependentLocalBinding';execution='Root null refusal is actual Python before native commit; do not call this a native coercion/body proof.'
 else:tier='ActualPinnedPython + CheckedTypedTranscription + IndependentLocalBinding + FiniteNativeBackedReaderObservation';execution='Root reads actual native-generated records with these Python readers/wrappers; provider bytes/SQL and whole function behavior remain bounded.'
 labels=anchors.get(i,[]);assert all(n in mainlabels for n in labels)
 rows.append(dict(proposal_index=i,source_id=key,census_symbol=symbol,proposed_member=x['member'],proposed_line=x['line'],actual_ast_or_classmethod_line=line,line_needs_correction=x['line']!=line,pin_current_sha256=sha(path),pin_identity=True,prior_active=bool(before.get(key)),before_bindings=before.get(key,[]),prospective_new_locator=not bool(before.get(key)),recommendation='retain bounded active role with narrowed locator/claim; no whole-member credit',role='producer' if i<14 or i==23 else 'reader',owner=owner,owner_changed_from_proposal=owner not in x['owners'],formal_item=str(source.relative_to(R))+'::'+name,formal_line=proofline,formal_relation='proves',claim_scope=scope,evidence_tier=tier,execution_limit=execution,native_main_case_anchors=labels,marker_supplement='Native marker6 supports replay statement/export distinction only, not direct as_comparable or Genesis.Adopt' if i in [13,15,16,22] else None,whole_member_claim=False))
for q in [O/'before-reach/bindings.json',O/'before-reach/census.json',O/'before-reach/summary.json',R/'.g5/ontology/features/ledger.g5.md',O/'ledger-content-validation.json',O/'root-ledger-native.py',O/'root-ledger-native.json',O/'root-ledger-marker-native.py',O/'root-ledger-marker-native.json',O/'root-ledger-qualkeys-native.py',O/'root-ledger-qualkeys-native.json',O/'review-ledger-native-audit.json']:
 inputs[str(q.relative_to(R))]=sha(q)
inputs.update(candidate)
assert all(sha(R/k)==v for k,v in candidate.items()),'candidate changed during read-only audit'
assert len(before)==208
out=dict(verdict='BOUNDED_ROLE_RECOMMENDATIONS_WITH_CORRECTIONS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),method='Read-only source-first cross-audit of exact current proposals, actual pinned/current definitions, before208 locator map, formal declarations/contracts and root executed branch evidence. No verifier, test, Git, native, network or private/evaluator access.',inputs=inputs,candidate_bytes_unchanged=True,before_active_locators=len(before),proposal_count=len(rows),prior_active_proposals=sum(x['prior_active'] for x in rows),prospective_new_locators=sum(x['prospective_new_locator'] for x in rows),line_corrections=sum(x['line_needs_correction'] for x in rows),root_main_completed_cases=main['completed_cases'],root_marker_completed_cases=marker['completed_cases'],qualkeys_completed_cases=native['root-ledger-qualkeys-native.json']['completed_cases'],no_automatic_reach_credit='13 unbound locators are proposals only; root must resolve accepted canonical rows after semantic review. Existing11 are semantic strengthening, not new reach.',rows=rows,limits=['Capture/Adopt typed ports are not actual source/native execution','OpRemoveProp no relevant native branch; OpQual native set-only','Python AST def lines, not preceding decorators/comments, used','ObjectScript census uses bare methods, not Graph.KG.Class prefix','One checked proof and one semantic owner per recommendation; broad spec lists not copied','Adopt owner ledger.lifecycle selects its adoption identity role, not unproved verify correctness','Bound/stream/export/parsing/serialization/native bodies remain distinct','Native main22 and marker6 are read-only finite workflow observations; failed qualkeys0 is not successful coverage'])
(O/'ledger-role-cross-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['verdict','proposal_count','prior_active_proposals','prospective_new_locators','line_corrections','candidate_bytes_unchanged']}))
