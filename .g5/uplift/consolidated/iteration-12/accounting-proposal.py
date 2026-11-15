"""Conservative draft accounting, read-only toward all packages and evidence.
No solver/tests/Git/native invocation. Outputs only iteration12 accounting/drafts.
"""
import copy,hashlib,json,re,tarfile
from collections import Counter
from pathlib import Path
IT=Path(__file__).resolve().parent;REPO=IT.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,x):(IT/name).write_text(json.dumps(x,indent=2)+'\n')
baseline=IT/'before-builder-scores.json';assert sha(baseline)=='86060ead20b1516e84d3cab944ef1a6e7ead4f67a7adfafea83717833087bb25';base=json.loads(baseline.read_text());assert len(base['rows'])==37
inputs=json.loads((IT/'inputs.json').read_text());audit=[]
oldfiles=['.g5/Verus_verification/models/graph_structure/graph_structure.rs','.g5/Verus_verification/models/history_diff/history_diff.rs','.g5/Verus_verification/models/reconstruction/reconstruction.rs','experiment/playbook-completion/proofs-d1e/src/acache_l1.rs','experiment/playbook-completion/proofs-d1e/src/acache_l2.rs']
with tarfile.open(inputs['before_archive']) as t:
 names=set(t.getnames())
 for rel in oldfiles:
  cur=REPO/rel;row=dict(path=rel,current_sha256=sha(cur),before_basis='Root identifies these old families as unchanged sealed11 bodies; this audit reads current exact bytes.')
  if rel in names:
   b=t.extractfile(rel).read();row.update(before_archive_member_sha256=hashlib.sha256(b).hexdigest(),current_equal_before_archive=b==cur.read_bytes());assert row['current_equal_before_archive']
  else:row.update(current_equal_before_archive=None,before_archive_member_absent=True)
  audit.append(row)
 oldowner={}
 for rel in ['.g5/ontology/features/algorithms.g5.md','.g5/ontology/features/ledger.g5.md']:
  b=t.extractfile(rel).read();oldowner[rel]=dict(before_archive_sha256=hashlib.sha256(b).hexdigest(),scope='Exact sealed11 before12 owner body read from archive, not current root edits.')
counts=json.loads((IT/'communities-counts.json').read_text());freeze=json.loads((IT/'communities-freeze.json').read_text());csrc=REPO/'.g5/Verus_verification/models/communities/communities.rs';ct=csrc.read_text()
assert sha(csrc)==counts['source_sha256']==freeze['package'][str(csrc.relative_to(REPO))]
assert len(re.findall(r'\bproof fn\b',ct))==66 and len(re.findall(r'#\[verifier::decreases_by\]',ct))==1
assert counts['ordinary_proof_queries']==65 and counts['recursive_spec_checks']==8 and counts['total']==73 and counts['extra_nonlinear_arithmetic_subqueries']==counts['imports']==0
count_audit=dict(status='READ_ONLY_SOURCE_METADATA_AUDIT_NO_NEW_VERIFIER_COMMAND',source_sha256=sha(csrc),source_proof_declarations=66,ordinary_proof_queries=65,theorem_declarations=35,ordinary_helper_declarations=30,checked_decreases_by_hint_declarations=1,hint='native_pages_termination checked within native_pages recursive termination query; not an extra ordinary proof unit',recursive_termination_checks=8,nonlinear_subqueries=0,imports=0,total_verified_units=73,metadata_matches_source=True,reported_receipt=freeze['current_receipts'][-2],no_new_prover_or_tests=True)
write('accounting-before-model-audit.json',dict(baseline_sha256=sha(baseline),archive_identity_from_inputs=inputs['before_archive_sha256'],old_model_bodies=audit,old_owner_bodies=oldowner,findings=['P acache_l1 has rows/over result contracts and P acache_l2 reviewed node-version cache state, not WCC/CDLP labels or raw rounds. It is substantive partial result/cache evidence, not absence of prior work and not raw kernel closure.','G graph_structure has raw graph/storage/degree/multigraph roles and concrete rollback/token poison/refusal; its algorithm answer is the content edge set, not WCC/CDLP output or fresh live completion.','reconstruction already proves named structural/entity count, peak prefixes, at-bound/zero and stream/export fold with opaque int payloads; it does not preserve all nested content.','history_diff already derives actual first prior/last new from raw scalar writes, net zero and named reverse/equal, complete scalar simple snapshot and stronger set-before-delete range-prior loss. It is genuine endpoint/lifecycle evidence, but not complete multi-entity maps/record expansion.','The prior raw-kernel provider foundations do not answer WCC reach/minimum or CDLP votes/parity. Before grades retain partial foundation hits and explicitly identify the missing deciding kernel; they do not claim an old theorem answered those decisions.']))
write('accounting-communities-count-audit.json',count_audit)
def g(x):return dict(grade=x,complete=x=='supported')
def pair(ont,model):return dict(ontology=g(ont),model=g(model))
rows=[]
for old in base['rows']:
 r=copy.deepcopy(old);r['before']=copy.deepcopy(old['after']);r['after']=copy.deepcopy(old['after']);r['prior_cohort']=old['cohort'];r['cohort']='carried37';r['panel_origin']='Exact iteration11 decision carried; iteration11 after is iteration12 before and remains iteration12 after. No new sampling or regrade.';r['iteration12_changes_exact_grade']=False;r['baseline_row_sha256']=hashlib.sha256(json.dumps(old,sort_keys=True,separators=(',',':')).encode()).hexdigest();rows.append(r)
# Twelve overlapping, deliberately bounded extensions, never pooled with carried rows.
new=[]
def ext(id,decision,owner,ontbefore,modelbefore,before_reason,model,scope,origins,after='supported'):
 row=dict(id=id,decision=decision,owner=owner,cohort='overlapping_extension12',before=pair(ontbefore,modelbefore),before_reason=before_reason,source_frozen_origins=origins,model_locators=model,scope=scope,after=pair('pending','pending') if after=='supported' else pair('partial','partial'),proposed_after=pair('supported','supported') if after=='supported' else pair('partial','partial'),status='PENDING_INDEPENDENT_REPLAY_AND_ROOT_ADJUDICATION' if after=='supported' else 'RETAINED_PARTIAL_BROAD_CLOSURE_NO_SUPPORTED_PROPOSAL',review_pending=True,proposal_not_final=True)
 new.append(row)
co=['iteration-11/next-communities-PAIRS.md','iteration-11/next-communities-plan.md','iteration-12/review-communities-expectations.md']
lo=['iteration-11/next-ledger-content-PAIRS.md','iteration-11/next-ledger-content-plan.md','iteration-11/next-ledger-content-independent-review.md','iteration-12/ledger-content-PAIRS.md','iteration-12/review-ledger-expectations.md']
ext('CM1','Raw default coordinate owners/weak mirrored paths derive WCC component-minimum labels and finite terminal result','algorithms.op.wcc','supported','partial','Old G graph keys/layout/mirror and P abstract fresh cache are real foundations, but neither computes WCC path-radius/minimum labels; no old raw WCC kernel proof.',['members','ball','labels_at','theorem_every_actual_round_is_raw_reachable_minimum','theorem_actual_wcc_terminates_with_confirmation'],'Finite stable default raw coordinates; weak component meaning needs faithful mirrors/closed endpoints, shared admitted order; no arbitrary native body/coercion/writer theorem.',co)
ext('CM2','WCC already-correct updated pair still needs unchanged confirmation: budget1 refuses, budget2/default succeeds; empty and nonpositive typed limits separate','algorithms.op.wcc','partial','partial','Old owner describes convergence/limit broadly; G/P do not model raw WCC guard/scan/install/change/confirmation or empty-before-budget. Generic cache proofs remain partial context.',['wstep','first_stop','theorem_confirmation_round_by_n','theorem_already_correct_pair_still_needs_confirmation'],'Actual typed integer/default guard order, derives <=N including confirmation; no blanket public carrier/exception-class guarantee.',co)
ext('CM3','CDLP raw coordinate counts derive frequency/majority/least-label tie, no-vote retention and self-loop exclusion, distinct from keyed physical multiplicity policy','algorithms.op.cdlp','partial','partial','Old owner says each edge one vote; physical keyed-coordinate policy is unresolved. G keyed layout is real prior evidence, not CDLP vote accumulation or maximum/tie selection.',['frequency','count_fold','best_fold','theorem_raw_coordinate_counting','theorem_cdlp_most_votes_then_least_label','theorem_self_loop_is_no_vote'],'Counts actual selected distinct direction/predicate/neighbor coordinates in admitted order; keyed SQL projection/collation provider and intended keyed-edge policy remain separate.',co)
ext('CM4','Synchronous CDLP two-node odd/even label oscillation and bounded/fixed stopping are derived from old-map vote rounds','algorithms.op.cdlp','supported','partial','Old ontology already specifies simultaneous rounds/oscillation. Existing P/G result/cache structure does not derive label swaps, parity or actual CDLP finite counter; not a convergence proof.',['cround','crun','theorem_two_node_oscillation_is_limit_parity','theorem_cdlp_finite_budget_and_fixed_stop'],'Finite typed integer limits, recognized core and raw old-label maps; zero-round and fixed-stop distinct; no global convergence/community-quality claim.',co)
ext('CM5','Raw SQL node/edge rows and faithful KG projection derive isolates/self-loop loners and all-current-node completion','algorithms.op.wcc / algorithms.op.cdlp','partial','partial','Old P rows/over and G stored layout contain membership foundations but do not derive actual SQL/KG loner census and its public consumer; abstract node-token guarantee cannot replace it.',['live','sql_loners','native_loners','projection','theorem_native_sql_live_loners_require_projection','theorem_complete_raw_live_census_is_all_live_members'],'Stable default node census, complete SQL-edge/KG coordinate projection, live endpoints/shared key order; graph-parametric census is not named-graph kernel closure.',co)
ext('CM6','Native loner page cursor VALUE is consumed exclusively; exact-full last page needs final empty read, with complete finite result or page failure','algorithms.op.wcc / algorithms.op.cdlp','partial','partial','Old cache/storage/result abstractions do not provide this native page writer-to-cursor-reader chain; retained foundations are partial, not a supplied complete census.',['page','after','native_pages','lemma_cursor_tail_equivalence','theorem_native_pages_derive_full_result_or_fail','theorem_full_final_page_requires_empty_page'],'Ordered unique admitted IDs, stable derived loner set/SQL order, positive page limit; no arbitrary malformed cursor/JSON/driver-lifetime/body theorem.',co)
ext('CM7','Successful empty census versus failure after a partial native page: discard prefix, whole SQL retry, and propagate SQL failure rather than emit public empty','algorithms.op.wcc / algorithms.op.cdlp','partial','partial','Existing cached/result abstractions and current wrapper context are substantive partial hits; no old raw loner page/full fallback outcome composition.',['census','public','theorem_census_success_empty_and_failure_are_distinct','theorem_native_failure_after_page_discards_partial','theorem_failed_census_is_not_public_empty'],'Typed failure abstraction plus actual Python/SQLite correspondence; exception text/counts/organic outage/native transport errors outside math. Four new native unavailability events are controlled.',co)
ext('CM8','Derived cached core plus fresh live loners admits same-token isolate insertion while retaining stale-core/rollback counterexample','algorithms.cache.token','partial','partial','Old G explicitly proves retained rollback/token poison and P reviewed nver/fresh2 abstractions; neither composes actual WCC/CDLP kernel payload with fresh per-call loner completion. No old absence claim or universal node-token defect.',['compute','core_read','public','theorem_inserted_isolate_visible_even_on_same_core_hit','theorem_fresh_loners_do_not_repair_stale_same_token_entry'],'Fixed admitted key/token/cache entry origin actually derived from raw earlier kernel. Correct-cache/equal-origin condition for fresh answers; no all-writer/ABA/concurrent cache theorem or native recomputation/read-count claim.',co)
ext('L1','Raw node/relationship/label/property/qualifier requests derive complete maps, separate records, actual priors/snapshots/noops/refusals and atomic semantic rollback across closed revisions','ledger.commit','supported','partial','Old history_diff derives current scalar priors and lifecycle snapshot; reconstruction proves opaque entity fold. Neither derives full Node/Stmt maps, batch expansion, deletion context or inductive ordinary producer frame.',['produce','request_ops','request','execute','commit','history','theorem_closed_ordinary_source_domain'],'Closed empty-origin default None/empty graph, no temporal texttrue/reifiers/competing/unrecorded/post-commit writes; canonical IDs/unique ordered keys and successful complete provider operations. Legal excluded markers are not API refusals.',lo)
ext('L2','Complete labels/properties/tuple/qualifiers survive named cutoff, prefix bound, eager stream and unbounded export through proved old structural/count projection','ledger.readers / ledger.readers.bound','supported','partial','Old reconstruction already fully proves the structural/count cutoff/peak-bound/stream effect; payload int abstraction does not preserve all nested content or actual full export fields.',['apply','fold','project','theorem_entity_count_projection','named_fold','run','theorem_named_bound_result_projects','theorem_later_records_cannot_change_full_content','entities','stream_entities'],'Typed decoder/ordered records/tuple codec and stable provider premises; full map/field projection, not all JSON bytes/filesystem/all numeric carriers/native bodies.',lo)
ext('L3','Continuous recognized attribute histories derive named before/after full content from base records plus generated/stamped records, with exact changed fields and no restored entries','ledger.readers.diff','supported','partial','Old history_diff already derives actual scalar continuous endpoints, first prior/last new/net-zero and reverse/equal. New decision requires all node labels/properties and relationship qualifiers plus named endpoint folds from input records, not supplied maps.',['attr_record','attr_track','changed','theorem_continuous_full_content_endpoint_diff','theorem_named_generated_full_content_endpoints'],'Recognized continuous label/property/qualifier range without create/delete. Raw-base reader algebra is not Genesis/Adopt native reach; rich known lifecycle prior loss and q-con-002 remain.',lo)
ext('L4','Broad native Genesis/Adopt plus general named/physical-registration/ordinary-marker producer-to-reader closure, beyond the qualified default no-marker history','ledger.lifecycle.genesis / ledger.verify / ledger.commit','partial','partial','Old G/P scope and history/reconstruction are partial; new typed alternate writers/readers and actual named/marker finite observations still do not establish whole native producer closure. Existing shared-ID questions/known marker root remain.',['alternate::capture','alternate::adopt','theorem_named_registration_refuses_create_after_default_delete','theorem_duplicate_tuple_views_remain_distinct','ordinary_batches'],'RETAINS PARTIAL: Genesis/Adopt native producers unexecuted; typed row/ID/content projection excludes raw SQL scan/parser/envelope/tuple-JSON-ref effects. Named registration can survive bare deletion; legal caller marker reaches duplicate replay IDs vs one physical row and is outside ordinary source profile. No API refusal or new bug/policy claim.',lo,after='partial')
rows+=new;assert len(rows)==49
for a,b in zip(rows[:37],base['rows']):assert a['id']==b['id'] and a['decision']==b['decision'] and a['before']==b['after'] and a['after']==b['after']
def summary(rs,side):
 out={}
 for layer in ['ontology','model']:
  c=Counter(r[side][layer]['grade'] for r in rs);out[layer]=dict(scheduled=len(rs),graded=len(rs)-c['pending'],pending=c['pending'],complete=sum(r[side][layer]['complete'] for r in rs),grades=dict(c))
 return out
cohorts={}
for name,subset in [('carried_original30',[r for r in rows[:37] if r['prior_cohort']=='carried30']),('carried_previous_overlapping7',[r for r in rows[:37] if r['prior_cohort']=='overlapping_extension7']),('new_overlapping12',new)]:
 cohorts[name]={side:summary(subset,side) for side in ['before','after']}
cohorts['new_overlapping12']['proposed_after_not_accepted']=summary([{**r,'proposal':r['proposed_after']} for r in new],'proposal')
packages={rel:sha(REPO/rel) for rel in ['.g5/uplift/consolidated/iteration-12/communities-counts.json','.g5/uplift/consolidated/iteration-12/communities-freeze.json','.g5/Verus_verification/models/communities/NOTES.md','.g5/uplift/consolidated/iteration-12/ledger-content-validation.json','.g5/Verus_verification/models/ledger_content/NOTES.md','.g5/uplift/consolidated/iteration-12/root-native-facts.json']}
body=dict(status='DRAFT_PENDING_INDEPENDENT_REPLAY_AND_ROOT_FINALIZATION',product_pin=base['product_pin'],before='Sealed iteration11 9de67a2841e6250d322f73bdd951bbe121867340',baseline_path=str(baseline.relative_to(REPO)),baseline_sha256=sha(baseline),authority='Builder-visible purposive source-informed overlapping decisions. Proposal only, no independent grade/private/discovery/population/convergence claim.',accounting_plan='Carry exact37 decisions unchanged; add12 explicitly overlapping extensions, never pool a success rate or infer population coverage. Eleven supported after proposals remain pending; L4 broad closure remains partial.',grade_rules='Supported means sufficient for the stated bounded decision under explicit premises, not whole native or all public input closure. Before partial retains substantive exact old-family hits without pretending old kernels exist. Pending supported proposals are ungraded until root finalizes after review.',rows=rows,cohort_summaries=cohorts,administrative_counts=dict(total_scheduled_rows=49,carried_rows=37,new_overlapping_rows=12,carried_exact_grade_changes=0,new_supported_proposals_pending=11,new_retained_partial=1,pooled_rate=None),count_proposal=dict(communities=dict(total=73,ordinary_proof_queries=65,proof_declarations=66,theorems=35,ordinary_helpers=30,checked_termination_hint_declarations=1,recursive_checks=8,nonlinear_subqueries=0,imports=0),ledger=dict(total=108,imports_rechecked=11,new_units=97,new_proof_declarations=84,new_theorems=58,new_helpers=26,new_recursive_checks=13,nonlinear_subqueries=0),combined_iteration12=dict(new_units=170,new_ordinary_proof_queries=149,new_source_proof_declarations_including_hint=150,new_theorems=93,new_ordinary_helpers=56,termination_hint_declarations=1,new_recursive_checks=21,nonlinear_subqueries=0,imports_rechecked=11,total_units_in_both_full_runs=181,controls=33),counts_are_not_grade_gain=True),finite_evidence=dict(new_main_native=42,new_ledger=34,new_communities=8,new_controlled_census_unavailable_events=4,reused_old_communities=18,separate_next_cypher_native_preparation=18,separate_pool_source_schedules=8,pool_native_calls=0,original_key_forecast_refutation_completed_comparisons=0,failed_native_attempt_counts_not_added_to_final=True),binding_administrative=dict(ledger=dict(histories=82,comparisons=4023,raw_reader_checks=6,typed_alternate_port_reader_checks=7,sensitivities=dict(actual_python=6,source_port=1,altered_observation=1),upstream_passed=155),communities=dict(comparisons=1255,history_records=9,affirmative_effect_checks=6,sensitivities=dict(actual_python=5,source_port=8,altered_observation=1),upstream_functions_passed=19),sockets=0,heterogeneous_case_counts_not_pooled=True),residuals=base['residuals']+[dict(id='L4/native closure',status='partial',limit='Typed Capture/Adopt plus raw reader duplicates/named finite facts do not close native Genesis, all named registrations or caller-marker adoption. Legal excluded history, not refused input.'),dict(id='q-con-002 / bug-led-101',status='unresolved policy / inherited known behavior',limit='No lifecycle inverse script or new issue credit.'),dict(id='CDLP keyed vote policy',status='retained ambiguity',limit='Source coordinate votes do not decide intended each physical keyed edge semantics.')],evidence_inputs=packages,not_measured=['independent grade','discovery success rate','population success rate','convergence','whole native executable-body verification','all-provider/collation/carrier/concurrency correctness'])
write('builder-scores-DRAFT.json',body)
notes='''# Iteration12 conservative accounting draft

This is a root proposal while independent replay is pending, not final acceptance.
The exact37-row baseline SHA86060ead20b1516e84d3cab944ef1a6e7ead4f67a7adfafea83717833087bb25
is verified. Every carried decision keeps its exact grade: prior after becomes
current before and after. No carried grade changes. Original30 and prior overlapping7
remain separate in mechanically derived summaries. Twelve new overlapping rows
are a disclosed source-informed continuation, not a fresh population sample.

CM1–CM8 separate raw WCC minima, budget confirmation, CDLP raw votes, parity,
raw live census, cursor-value paging, failure/empty fallback and derived cached
core plus live completion. L1–L3 separate complete request/record maps, named
cutoff/stream/export and continuous full-field diff. Their11 proposed supported
after judgments remain **pending**. L4 is **partial before and after**, covering
the broader native alternate/named/marker closure that the package does not prove.
Thus actual new after summary has1 graded partial and11 pending; the separate
proposal summary has11 supported/1 partial and is not an accepted score.

Before judgments read actual old bodies, not an imagined blank baseline. G's
raw storage/token rollback witness and P's abstract rows/over plus reviewed node
version are substantive partial predecessors; P has no WCC/CDLP labels/rounds.
Old reconstruction already answers structural cutoff/count/peak/stream behavior,
while opaque payloads leave nested fields open. Old history_diff already derives
scalar first-prior/last-new/net-zero and the known deletion-time snapshot challenge.
Those are partial predecessors of L1–L3, not discarded successes. G/reconstruction/
history_diff bytes equal exact before-archive entries. P's current exact hashes
are recorded under root's unchanged-family premise; its source was not present
in that archive, so no archive byte-equality is fabricated. Exact old owner bodies
were also read from the before archive for ontology-before judgments.

Communities73=65 ordinary proof queries+8 recursive checks,0NLA/import. Its66
source proof declarations include35 theorem/30 ordinary helper declarations and
one checked decreases_by hint, native_pages_termination, attributed to the
native_pages recursive termination query. Do not add that hint as a66th ordinary
query. Ledger108=11 imports+84 new proof declarations(58theorems26helpers)+13rec,
0NLA. Combined new170=149ordinary proof queries+21rec, with150new source proof
declarations including the one hint; total full runs181 includes11 rechecked
imports. Count precision itself earns no coverage/grade gain. Read-only metadata/
source count audit is accounting-communities-count-audit.json; no new prover/test
was run for this accounting task.33 formal controls are administrative evidence,
not33 independent workflow samples.

New main native42=ledger34(22main+6key followups+6marker)+community8. Four community
unavailability events are controlled adapter refusals. Old community18 is reused;
Cypher18 native preparation and pool8 actual-source opaque-link schedules are
separate and gain no formal model credit. Original empty-key forecast0-comparison
refutation and earlier failed-attempt agreements are retained, never added again.
Binding histories/cases and test counts remain separate by package; no mixed rate.

Legal caller temporal:'true' can trigger row adoption/new identity: it is outside
the closed no-marker/default source frame, not an API refusal or hypothetical
provider. Genesis/Adopt typed content ports do not execute their native bodies;
named registration can survive a bare default deletion. Keep L4 partial, inherited
F-C0351/F-0505/F-C0450/F-1105, known bug-led-101 and q-con-002. R1/V1 broad partial,
R2 raw carriers and q-iter-007/q-iter-008 residuals remain exactly carried. No new
issue/severity/policy/repair or independent-grade/convergence claim is proposed.

Artifacts: builder-scores-DRAFT.json, accounting-before-model-audit.json,
accounting-communities-count-audit.json. Root should finalize only after current
independent replay and its own evidence/role adjudication. The frozen model,
results/native/shared/product/Git files were not modified by this accounting task.
'''
(IT/'notes-DRAFT.md').write_text(notes)
print(json.dumps(dict(rows=len(rows),carried=37,changed_carried_grades=0,extensions=12,extension_actual_after=cohorts['new_overlapping12']['after'],extension_proposal=cohorts['new_overlapping12']['proposed_after_not_accepted'],communities_count_total=73)))
