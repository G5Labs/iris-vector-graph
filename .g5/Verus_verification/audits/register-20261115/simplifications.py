"""Audit the claimed simplification, not the desirability of a repair."""
from pathlib import Path as _AuditPath
if (_AuditPath(__file__).resolve().parent / "APPLIED.json").exists():
    raise SystemExit("This audit has been applied. Preserve its reviewed registers; replay regressions.py, components.py or verify.py instead of rebuilding history.")

from pathlib import Path
import re,json,hashlib
H=Path(__file__).resolve().parent;R=H.parents[3];V=R/'.g5/Verus_verification'
I=json.loads((H/'starting-inventory.json').read_text())['design_simplification']
# behavior that must survive; where the obligation moves and what it costs
RC={
'01':('Default/named/all-graph results and scoped writes, including optional null rows and parallel edges.','A scoped query layer must represent the current exceptional calls and composite joins; every adapter and SQL escape hatch still needs binding evidence.'),
'02':('Existing node/edge identity, replay, diff, redaction target attribution and old archive readability.','Adding graph keys changes records, hashes and migration/read compatibility; attribution moves into every writer and the migration boundary.'),
'03':('Removal reach and retained configuration, separator-aware targets and truthful receipts.','An inventory generator needs complete writer/store discovery, versioned hooks and tests; completeness is a new central obligation, not an eliminated one.'),
'04':('Nested transactions, concurrent unrelated targets, and required erase/redact refusal.','The shared lock must cover all writers with a lock-order and progress proof; it adds contention and cannot repair dirty-read isolation by naming a lock alone.'),
'05':('Concurrent updates without lost facts and the same public error/rollback contracts.','A shared lock or atomic primitive requires per-key ownership, failure cleanup and competing-writer coverage; serialization costs remain at the storage boundary.'),
'06':('Fresh answers after commit, rollback, process death, erase and independent cache deletion.','A token scheme needs every relevant producer and rollback/death invalidation; the validity proof moves to token ownership and admission.'),
'07':('Consistent multi-call results with bounded readers and existing refusal behavior.','A snapshot/version protocol adds retries or locks and needs starvation, crash and incomplete-read handling; reader consistency has not disappeared.'),
'08':('All documented strict-mode exemptions, ledger writes, refusal errors and transaction nesting.','Server ownership needs a bypass-writer census and capability context; centralized admission adds a trusted boundary and deployment/compatibility work.'),
'09':('The original keyed outcome and no duplicate external effect, including ambiguous replies.','A durable effect/outcome record adds state, recovery and retention rules; an unknown-outcome response changes client interfaces.'),
'10':('Whole-operation rollback where promised and documented chunked-loader semantics.','Validation/transactions need staging, temporary capacity and explicit multi-transaction exceptions; costs move to the shared writer.'),
'11':('Caller-owned transaction levels and only the failed operation being undone.','A shared helper still needs accurate started-level tracking at every ObjectScript caller and process-death behavior; helpers do not remove transaction obligations.'),
'12':('Supported server/driver/platform outcomes and explicit refusal of missing premises.','Environment checks need deploy-time provenance, cache invalidation and runtime rechecks; validation adds failure states.'),
'13':('One schema per namespace, migration to legacy installs and case-compatible naming.','The resolver becomes a central dependency; every raw SQL/native/deploy entry still needs a schema-binding proof.'),
'14':('Distinguishing empty success, partial success and provider failure without hiding completed effects.','Typed result propagation changes error interfaces and callers; recovery and compatibility decisions remain per operation.'),
'15':('Public exception compatibility, useful operation context and distinct refusal causes.','A typed hierarchy moves mapping into boundary adapters; subclass compatibility and callers catching old exceptions need checks.'),
'16':('Supported clause semantics, typed values, graph scope and refusal of unsupported forms.','A reference evaluator adds an independent semantics maintenance burden and coverage domain; it is additional verification, not a smaller product model.'),
'17':('Numbers versus numeric-looking strings, booleans, nulls, legacy values and relationship qualifiers.','A common encoding needs versioned storage/migration and readers; typed node paths already exist, so a whole-product reduction is not shown.'),
'18':('Existing domain codes, metrics and units with explicitly compatible conversions.','Types need conversion and unknown-value policies at all external providers; obligation counts cannot omit the adapters.'),
'19':('Accepted ordinary literals and identifiers, query parameters and requested read-only behavior.','Binding and name validation need separate identifier/value APIs and complete translator coverage; this is a security repair candidate, source review only.'),
'20':('Documented namespace privileges, graph collision-avoidance semantics and existing operator controls.','Authorization moves into server middleware/executors and needs deployment and credential compatibility; source-only security scope, no new reproduction.'),
'21':('Single-edge and multigraph identity, lowest-key representatives and per-edge deletes.','A shared edge identity changes tuple references and migrations; ambiguous legacy references still need a chosen refusal policy.'),
'22':('Explicit edges survive temporal cleanup and inferred/derived provenance stays distinguishable.','A shared marker predicate still needs a reserved-key policy, old-data handling and writers that cannot forge or misclassify marks.'),
'23':('Bag multiplicity, specified tie ordering and graph-specific joins.','Canonicalization/sorting adds CPU and memory and requires a tie contract; an unspecified order cannot be silently made a new promise.'),
'24':('Identity discrimination and stale-entry rejection for ordinary names, plans and relationships.','Collision-safe identity requires full-key comparisons or wider keys plus lifetime/compatibility rules; checks cannot just move into a hash provider.'),
'25':('Archive readability, intended merge/replace behavior, per-store ownership and honest partial failures.','Owner hooks need archive versioning and transaction/refusal interfaces; the proposal transfers import correctness to each store.'),
'26':('Registry identity refusals before writes and declared missing-registry compatibility.','A common admission gate must cover routes, queues, optimizer and raw helper exceptions; the complete writer binding remains.'),
'27':('Ordinary valid inputs, stable validation errors and write-nothing refusals.','Shared validation needs server/Python agreement and exceptions for low-level documented coercion; it adds a common failure interface.'),
'28':('Correct bounded responses and explicit capacity failures with recorded partial work.','Streaming/chunking adds continuation and intermediate-capacity obligations; final size, peak memory and fairness are different bounds.'),
'29':('The same observable contract on each supported native, Owner, SQL and Python route.','A shared implementation must preserve platform/fallback availability; moving code removes neither route admission nor provider correspondence.'),
'30':('Pause/retry recovery, no duplicate effects and honest progress on queued/batched work.','Persisted cursors/claims add lease, recovery and cleanup state and fairness assumptions; progress still depends on scheduling.'),
'31':('Accurate documentation of supported behavior and exceptions.','Generated descriptions need a semantic source and stable annotation/schema APIs; prose/code agreement remains a validation obligation.'),
'32':('Installable packages and the same Community/Enterprise deployment behavior as supported setup.','A shared deploy manifest adds edition-specific predicates and packaging tests; tooling reuse alone does not shrink the product model.'),
'33':('Requested semantic options are honored or clearly refused before effects.','Central admission requires an option-support matrix and compatibility errors for every route; it adds explicit refusal transitions.'),
'34':('All permitted writers, transaction membership and cross-store invariants.','An enforced owner API needs interception of direct SQL/native paths and deployment authority; bypass and transaction proofs move to that API.'),
'35':('Bulk load throughput, declared chunk commits, constraints and rebuilt indexes on every graph.','Index/key maintenance or staging adds load-time checks and rebuild recovery; omitting them is a behavior change, not a simplification.'),
'36':('All accepted text/JSON values, types, delimiters and stable external results.','A codec adds versioning and legacy decode support; producer/consumer agreement and malformed-reply handling remain proof obligations.'),
}
COST={
'simp-001':'The prose token/takeover protocol adds identity and recovery checks. The actual repaired flag only changes admission guards; Run.started remains in the model.',
'simp-cyp-001':'Digest/sequence identity adds class lifetime, collision and stale-layout binding obligations; entry/class matching cannot simply disappear.',
'simp-002':'Endpoint-bearing records add stored fields and old-record branches. Knowledge lookup may shrink only if legacy layouts, record hashes and record-count compatibility are accounted for.',
'simp-003':'One inventory owns completeness and hook coverage. Full liveness adds checked stores and refusal cases rather than eliminating the content-ownership decision.',
'simp-str-001':'The Eraser API must preserve ledger recording, keyed edge selection, caller transactions and returned counts. Each caller still needs a correspondence check.',
'simp-srch-001':'A common fusion API needs leg-failure and absent-rank policy, corpus choice, weights, duplicate/tie semantics and compatibility adapters; no replacement is modeled.',
'simp-plt-001':'A server gate needs a complete exemption/writer list, nested-transaction behavior and Python error mapping; the five-second client cache vanishes only after those obligations are supplied.',
'simp-cyp-002':'Graph-bearing AST bindings add types and per-join null-placement rules; late regex decisions move into translation, with no proposed Verus AST/SQL model.',
'simp-str-002':'GraphKey gains the inverse contract and every SQL/native caller needs the same default/named conversion; migration and old aliases remain.',
'simp-str-003':'Changing warm/token order still requires no reader to admit an unfinished rebuild; one ordering check replaces another, with no alternate state model.',
'simp-tmp-001':'Removing the legacy Python path requires opt-out, dry-run/backfill and non-indexed fallback coverage; dropping a supported fallback narrows the operating envelope.',
'simp-srch-002':'The route-row snapshot must remain valid until the write, including registry changes and missing-registry exceptions; a saved query is not a removed identity obligation.',
'simp-plt-002':'Uniform fallback still needs per-algorithm numerical parameters, refusal/error policy and native admission; an Owner call is not an interchangeable opaque result.',
'simp-plt-003':'Label ownership moves to Adjacency but FHIR transaction, graph key and rollback binding remain; extra helper calls may add cost.',
'simp-plt-004':'Batching rebuilds trades repeated work for index-staleness intervals, failure recovery and concurrent-writer handling; final KG equality alone is insufficient.',
'simp-plt-005':'Retirement needs a caller census and per-engine schema-state equivalent; process-global state cannot be dropped without proving the replacement lifecycle.',
'simp-cyp-003':'Failed-entry state and retry/reset policy are added; one SQL fallback does not establish future builds, concurrent users or error classification.',
'simp-led-001':'GraphKey owns the conversion but digest stability, prefix targeting and legacy empty/default graph encoding still need correspondence.',
'simp-str-005':'The existing counterexample shows an unrelated writer can produce a reused generation value; key ownership is not repaired by changing the counter source.',
}
def metrics(path):
 s=path.read_text();structs={}
 for m in re.finditer(r'pub\s+struct\s+(\w+)[^{]*\{([^}]+)\}',s,re.S):
  fs=re.findall(r'\bpub\s+(\w+)\s*:',m[2]);structs[m[1]]=fs
 return dict(path=str(path.relative_to(R)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),declared_fields=structs,declared_field_total=sum(map(len,structs.values())),proof_function_declarations=len(re.findall(r'\bproof\s+fn\b',s)))
rows=[]
for x in I:
 links=re.findall(r'\]\((results/[^)]+receipt.json)\)',x['body']);receipts=[];models=[]
 for l in dict.fromkeys(links):
  p=V/l;j=json.loads(p.read_text());rec=dict(path=str(p.relative_to(R)),verdict=j.get('verdict'),label=j.get('label'),root=j.get('root',j.get('observed')),command=j.get('command',j.get('observed',{}).get('command')));receipts.append(rec)
  if j.get('control_file') and j.get('crate'):models.append(R/j['crate']/j['control_file'])
  for f in j.get('inputs',{}):
   if f.endswith('.rs') and (R/f).is_file():models.append(R/f)
 before_after=None
 if x['id'].startswith('RC-'):
  behavior,cost=RC[x['id'][-2:]]
  if len(receipts)>=2 and receipts[0].get('root') and receipts[1].get('root'):
   def units(r):
    q=r['root'];return q.get('verified',0)+q.get('errors',0) if isinstance(q,dict) and 'verified' in q else None
   a,b=units(receipts[0]),units(receipts[1]);before_after=dict(metric='verification queries in the same whole crate (includes unrelated modules)',as_built=a,reviewed=b,removed=(a-b if a is not None and b is not None else None),qualification='Control feature changes behavior; baseline is a reviewed repair. This is not a model of the full cross-module RC proposal and is not a state count.')
 else:
  b=re.search(r'Behavior to preserve: ([^\n]+)',x['body']);behavior=b[1] if b else 'Sound degree-cache admission under all competing writers and rollback.';cost=COST[x['id']]
 if x['id'] in ['simp-001','simp-003']:
  before_after=dict(metric='declared model schema; shared by both variants',as_built={'St_fields':12,'Run_fields':4,'Action_variants':9},proposed={'St_fields':12,'Run_fields':4,'Action_variants':9},removed=0,qualification='Measured declarations, not independent states. Same Run.started and all nine action alternatives remain. Witnesses change Variant flags; prose run-token/inventory API is not modeled. Sequences/maps/sets have unbounded mathematical domains; no reachable-state count.')
 rows.append(dict(id=x['id'],behavior_to_preserve=behavior,boundary_cost=cost,existing_receipts=receipts,source_metrics=[metrics(p)for p in dict.fromkeys(models)if p.is_file()],comparison=before_after,disposition='retired counterproposal' if x['id']=='simp-str-005' else 'simplification claim withdrawn; engineering candidate retained for review',reason='No comparable complete after-model establishes a net decrease in independent fields, rules or obligations over the same required outcomes and operating envelope. Repair/control success is not a complexity measurement.'))
(H/'simplification-review.json').write_text(json.dumps(rows,indent=2)+'\n')
text='# Simplification comparisons — fresh register audit\n\nAll 55 starting IDs reviewed. No product design was changed. 54 unsubstantiated simplification claims are withdrawn; the already retired counterproposal stays retired. This does not reject a possible repair. Counts below are measured declarations or recorded solver queries, never states or a whole-product complexity estimate.\n\n'
for x in rows:
 text+=f'<a id="{x["id"]}"></a>\n### {x["id"]}\n\nPreserve: {x["behavior_to_preserve"]}\n\nDecision and cost: {x["boundary_cost"]}\n\n'
 if x['comparison']:text+='Actual Verus comparison: `'+json.dumps(x['comparison'],ensure_ascii=False)+'`\n\n'
 else:text+='Actual Verus comparison: no complete proposed model under the same envelope. Eliminated independent fields/rules/obligations: **unestablished**, not zero measured. No state-space percentage is claimed.\n\n'
 text+='Disposition: '+x['disposition']+'. '+x['reason']+' The source declarations, original receipts and exact configurations are indexed in [simplification-review.json](simplification-review.json).\n\n'
(H/'simplification-review.md').write_text(text)
print(json.dumps({'reviewed':len(rows),'withdrawn_claims':54,'already_retired':1,'recorded_comparisons':sum(x['comparison']is not None for x in rows)}))
