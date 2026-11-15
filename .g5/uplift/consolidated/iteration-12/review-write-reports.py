"""Render independent source-first obligation ledger and bounded acceptance reports."""
from pathlib import Path
import datetime,hashlib,json
H=Path(__file__).resolve().parent
c=[
('C1','supported','Raw default owner/SQL node domains and foreign-graph frame derive from coordinates/rows; actual reader adds current isolates.'),
('C2','partial','Native/SQL census agreement is proved under explicit edge↔coordinate projection and live endpoints; those physical provider/writer facts and universal collation are not proved.'),
('C3','supported','Raw synchronous WCC rounds derive reachable minima; weak-component interpretation adds mirror, rather than assuming a partition.'),
('C4','supported','Every round uses the complete old map; in-place changes are distinguished.'),
('C5','supported','Two-node budget1 refuses despite correct first partition; budget2 confirms no change and succeeds.'),
('C6','supported','Empty core bypasses guard; typed nonpositive WCC refuses when nonempty, CDLP performs zero rounds. No generic pre-read ValueError promise.'),
('C7','supported','Raw reachable-ball growth gives bounded first terminal confirmation and component minimum, with source provenance.'),
('C8','partial','Raw coordinate frequencies/winner are proved; physical keyed repeats collapse to one coordinate. Intended keyed-edge multiplicity policy remains unanswered.'),
('C9','supported','Actual count/best scans derive max frequency, least admitted label, self exclusion and no-vote preservation.'),
('C10','supported','Arbitrary-round two-node CDLP parity proves oscillation; no convergence guarantee is invented.'),
('C11','supported','Stable stop versus finite exhausted budget and installed new map are distinct derived outcomes.'),
('C12','supported','Raw node/edge/coordinate census derives other-neighbor exclusion, outgoing loop flag and missing-only completion.'),
('C13','supported','Correct warm core plus fresh census sees newly inserted isolate without recomputing core; actual two-engine binding/native reuse corroborate.'),
('C14','partial','Same-token/different-origin stale core survives fresh loners. Primitive cache witness is proved; causal transaction/cache-writer implementation remains existing external evidence.'),
('C15','supported','Returned next VALUE decides strict subsequent key filter; ordered unique tail proof, extra empty final page and whole partial-result discard/fallback verified.'),
('C16','partial','Actual Python strict reader/dispatch/completion execute; formal failure/order result is a typed projection, not raw JSON grammar, retry counts/error wire or accelerated body proof.'),
]
l=[
('L1','supported','Raw create/upsert expands empty create plus separate labels/properties; current values/noops and rollback derived on declared ordinary profile.'),
('L2','supported','Tuple lookup/own allocation counter, qualifier merge and inductive coherent/fresh/default/live/key frames are derived across whole admitted history.'),
('L3','partial','Typed nullable flags and actual decoder distinguish None/empty/text-null; full SQL/native row coercion/grammar remains provider.'),
('L4','supported','Complete opaque text maps and scalar Boolean/NumberText decisions survive actual reader; JSON containers/null differ from public scalar admission.'),
('L5','partial','Raw reader derives tuple graph and None/empty/NUL normalization; ordinary native producer correspondence admits None/empty only and excludes general named/NUL histories.'),
('L6','supported','Generic complete reader reset/ignore/idempotence laws are separate from ordinary producer admission.'),
('L7','supported','Typed deleted-context/weight/existing/reserved/key order and transactional rollback are distinguished, including native empty-batch-key carrier fault versus direct setter refusal.'),
('L8','supported','Deletion snapshots/current priors derive from current complete maps; complete successful SQL is an explicit source premise.'),
('L9','partial','Default detach/strict behavior and no implicit reader cascade are retained; native named relationship/registration survival is observed, not full named producer closure.'),
('L10','partial','Physical any-graph registration may refuse create despite bare replay absence; standalone witness/native fact does not prove a general registration history.'),
('L11','supported','Duplicate tuple IDs remain distinct in full statements/export while tuple/comparable selects later; native legal caller-marker history reaches this contrast.'),
('L12','partial','Capture derives typed raw-row content/records incl graph-loss/duplicates; native Genesis/SQL scan completeness/order remain unexecuted/provider.'),
('L13','partial','Typed Adopt content/ID reuse/copy projection only; raw envelopes/parser/tuple-JSON qualifier IDs/native producer are not proved or executed.'),
('L14','supported','Raw base log plus generated recognized continuous attribute operations derive exact named endpoint fields/range diff; no supplied endpoints.'),
('L15','partial','Rich known bug-led-101 deletion-time snapshot/prior loss retained and native-strengthened; q-con-002 inverse/lifecycle policy unanswered.'),
('L16','supported','Full-content run derives old entity/count projection, selected prefix/strict bound/transient oversize; unchanged11 units explicitly imported.'),
('L17','supported','Structured entity sets and all fields reach actual eager stream/NDJSON; byte/FS atomicity and bounded-memory claims excluded.'),
('L18','supported','Actual named reads/diff exercise lower-exclusive upper-inclusive range, equal/reverse, and later records cannot affect earlier selected state.'),
('L19','partial','Recognized ordinary diff frame is explicit; actual temporal/unknown-kind/op/tombstone/audit contrasts retained. Typed Other is unknown operation, not all other entity kinds.'),
('L20','partial','Successful complete SQL/snapshot/codec/transaction premises remain material; quiet native query failures and universal provider/body behavior are unproved.'),
]
configs=[('communities',c,'review-communities-scratch-v1','review-communities-expectations.md'),('ledger-content',l,'review-ledger-scratch-v2','review-ledger-expectations.md')]
for name,rows,scratch,panel in configs:
 validation=json.loads((H/('review-'+name+'-validation.json')).read_text());counts=json.loads((H/('review-'+name+'-counts.json')).read_text());summary={k:sum(st==k for _,st,_ in rows) for k in ['supported','partial','unanswered']}
 body=dict(verdict='ACCEPT_BOUNDED_FRAGMENT',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Builder-visible source-informed purposive review, not external/private grading or a population sample.',panel=dict(path=panel,sha256=hashlib.sha256((H/panel).read_bytes()).hexdigest(),frozen_before_new_candidate_inspection=True,exposure='Root initial named-registration miss was disclosed before ledger panel; later native/refuted forecasts are explicitly exposed supplements, not blind draws.'),rows=[dict(id=i,status=s,evidence=e) for i,s,e in rows],summary=summary,counts=counts,validation='review-'+name+'-validation.json',scratch=scratch,package=validation['package'],command_cost_s=validation['measured_command_elapsed_s'],private_evaluator_inspected=False,reviewer_native_calls=0,reviewer_network_calls=0)
 if name=='communities':
  body['misses_retained']=['Initial moving model used cursor presence/index skip rather than actual next value; corrected to strict after filter with ordered-tail proof and ordinary terminating overadvance control.','Physical keyed multiplicity necessarily changes CDLP forecast and DBAPI default NULL concern were refuted; no defect/policy invented.']
  body['residuals']=['Default graph core only; projected unique native coordinates and SQL/KG live-endpoint relation.','Shared order-preserving admitted identifier carrier across native label/global, SQL paging and Python ordering; no mixed/numeric universal collation claim.','Cache origin is ghost computed-payload provenance at selected key/token; no cache writer/transaction/front/transport/body/read-count proof.','Core/Public Failure is outcome projection; actual wrapper retry/error wire and accelerated/JSON body remain observations.','Keyed-edge intended vote projection unresolved.']
  body['prior_hits']=['G graph_structure','P acache_l2','procedure_results/routing; no imported/new duplicate credit']
 else:
  body['misses_retained']=['Reviewer skip-empty batch-key forecast was refuted by native local-array SUBSCRIPT before enumeration; original0-comparison negative and6 exposed followups retained.','Per-entry NodeExists==bare replay presence was not inductive for named histories; actual named-survivor refusal retained, whole ordinary source profile is closed default-only.','Legal caller temporal:texttrue can reach adoption/reallocation/full-reader duplicate IDs; native6 strengthens inherited F-C0351 with F-0505/F-C0450, no new issue count.','Scratch copy dangling optional TCK symlink, wrong confcutdir and omitted schema test dependency were reviewer setup errors; exact failed attempts retained, no candidate failure inferred.']
  body['residuals']=['Whole ordinary source profile excludes legal texttrue-marker/NUL/named/temporal/reifier/unrecorded/competing writer histories; no API refusal asserted.','Canonical ID and unique normalized ordered key/number/tuple/string/JSON carriers plus complete successful SQL/snapshots/transactions remain explicit providers.','GraphLedger.commit binding has empty post_commit_properties/hooks; no whole wrapper/admission/idempotency/native transaction guarantee.','Capture/Adopt have inspected source+checked typed math+executed transcription only, no actual native/Python producer tier; actual downstream Python readers execute.','Continuous recognized-attribute endpoint theorem does not solve rich lifecycle bug-led-101/q-con-002 or unknown/temporal operation diff behavior.']
  body['prior_hits']=['ledger_apply','reconstruction11 imported/rechecked','history_diff and existing record paging; strengthened full content, not wholly new members']
 (H/('review-'+name+'-final.json')).write_text(json.dumps(body,indent=2)+'\n')
 first='Accepted the stated bounded fragment after independent exact scratch replay. No core semantic change is requested.'
 nums=f"Baseline {validation['expected_verified']}/0; {validation['controls']}/{validation['controls']} full and isolated named controls fail ordinarily without resource/timeout errors. Binding {validation['bindings']['comparisons']} comparisons, {validation['bindings']['histories']} histories and {validation['bindings']['sensitivities']} sensitivities agree; {validation['upstream_passed']} unchanged unit tests pass,0 socket calls. All final package bytes match scratch; {len(validation['central_receipts'])} central and {len(validation['scratch_receipts'])} scratch receipts are fresh."
 text=f'# Independent {name} review\n\n{first}\n\n{nums}\n\nThe [{panel}]({panel}) was source-frozen before candidate inspection; this is a source-informed builder-visible review, not a blind grade or a project-wide success fraction. Statuses below concern only these scoped obligations.\n\n| Case | Status | Observation and boundary |\n|---|---|---|\n'+''.join(f'| {i} | {s} | {e} |\n' for i,s,e in rows)
 text+='\n'+f"Rows: {len(rows)} total; "+', '.join(f'{n} {k}' for k,n in summary.items())+'. Counts derive directly from the JSON rows; unanswered policy/provider limits remain in partial rows.\n\n'
 text+='Retained misses and corrections:\n\n'+''.join('- '+x+'\n' for x in body['misses_retained'])
 text+='\nMaterial limits:\n\n'+''.join('- '+x+'\n' for x in body['residuals'])
 text+=f"\nExact inputs/results/commands/raw logs/mutants are under `{scratch}/`; validation is `review-{name}-validation.json` and enumerated query classification is `review-{name}-counts.json`. Measured wrapper commands, including retained failed upstream attempts, total {body['command_cost_s']:.3f}s. Preparation/shell-start latency, source-review/wait wall time and money are not inferred from that figure. No private evaluator artifact, product/shared source, Git state or native runtime was changed by this reviewer. Root owns canonical integration and issue disposition.\n"
 (H/('review-'+name+'-final.md')).write_text(text)
# Separate command accounting, never pool native or upstream prep into proof counts.
v=json.loads((H/'review-final-validation.json').read_text());q=json.loads((H/'review-communities-count-queries/results.json').read_text());cost=dict(command_elapsed_s={k:x['measured_command_elapsed_s'] for k,x in v['models'].items()},auxiliary_count_query_elapsed_s=sum(x['elapsed_s'] for x in q['results']),query_purposes='native_pages counts1; checked decreases_by hint counts0 independently. No extra theorem/control credit.',source_probe_and_readonly_native_fact_audits='Elapsed fields retained in individual review-*-probe/audit JSON files; no native reruns.',setup_failures=['review-ledger-scratch-v1/prepare-failure.json','review-ledger-upstream-supplement.json'],currency_cost=None,qualification='Only measured child-command durations are reported; shell/process startup latency and interleaved builder wait/review wall time are not assigned as proof cost.')
cost['measured_total_including_auxiliary_s']=sum(cost['command_elapsed_s'].values())+cost['auxiliary_count_query_elapsed_s'];(H/'review-costs.json').write_text(json.dumps(cost,indent=2)+'\n')
print(json.dumps(dict(reports=['review-communities-final.md/json','review-ledger-content-final.md/json'],summaries={x[0]:{k:sum(st==k for _,st,_ in x[1]) for k in ['supported','partial','unanswered']} for x in configs},measured_command_total_s=cost['measured_total_including_auxiliary_s'])))
