"""Question reconciliation plan. No inference of human approval from implementation."""
from pathlib import Path as _AuditPath
if (_AuditPath(__file__).resolve().parent / "APPLIED.json").exists():
    raise SystemExit("This audit has been applied. Preserve its reviewed registers; replay regressions.py, components.py or verify.py instead of rebuilding history.")

from pathlib import Path
import re,json
H=Path(__file__).resolve().parent;R=H.parents[3]
I=json.loads((H/'starting-inventory.json').read_text())['open_questions'];S=json.loads((H/'source-review.json').read_text())['open_questions'];O=json.loads((H/'ontology-start.json').read_text())
# A chosen policy for audit reasoning, explicitly agent-provisional unless sourced below.
WORK={
'q-004':'Require committed erasure before redaction; treat caller transaction membership as unresolved rather than permitting dirty liveness reads.',
'q-001':'Preserve refusal of the whole shared revision key and loss of its correlation lookup until the maintainer specifies a tenant-specific retry result.',
'q-003':'Document the present strict-off erasure sequence as an operational precondition; do not infer that disabling strict mode is the desired product interface.',
'q-008':'Keep generic erase as literal starts-with and use the separator explicitly in the tenant recipe; changing the generic API needs compatibility authority.',
'q-009':'Treat temporal entries as live content for the intended safety rule; the existing row-only check remains a documented behavior discrepancy pending scope confirmation.',
'q-010':'Treat post-commit properties as unrecorded writes today and keep verify divergence visible; skip-on-replay is a separate already documented idempotency obligation.',
'q-str-001':'Preserve refusal of invalid new names and the promised legacy report; require an operator-visible migration plan before claiming old invalid names are supported.',
'q-tmp-001':'Keep first-write-wins and exactness as requirements; concurrent provider behavior is unestablished, not an approved one-writer exemption.',
'q-srch-001':'Keep quarantined data and explicitly report retention until an owner chooses a purge API and its unknown-graph semantics.',
'q-plt-001':'Record immediate enforcement in the calling engine and a five-second cache elsewhere; the time promised to other engines still needs a decision.',
'q-plt-002':'Prefer refusing a conflicting unfinished setup; accepting it needs an explicit plan for the old globals and rebuild markers.',
'q-plt-003':'Treat the documented open bind and credentials as current behavior only; safer defaults need a maintainer policy decision.',
'q-plt-004':'Prefer refusal while a live ledger exists until replace/merge history semantics are specified; do not count the current overlay as a decided contract.',
'q-plt-005':'Keep documented loader exemptions and chunking; preserve other graphs and multigraph data unless a narrower supported envelope is expressly adopted.',
'q-plt-006':'Record each transport-dependent transaction boundary; prefer an explicit consistent join-or-refuse contract before changing it.',
'q-plt-007':'Require a proven graph-specific reader before relying on native default-graph results; an unavailable Arno provider does not settle its behavior.',
'q-plt-008':'Preserve explicit BulkLoader/raw-SQL/vector exemptions and list undecided FHIR/server paths individually; do not infer exemption from a missing guard.',
'q-cyp-001':'Prefer the bound endpoints graph, with ambiguity refused; the actual default-write rule remains a behavior fact pending intent confirmation.',
'q-led-005':'Treat kind as caller data today while reserving system meaning in analysis; any restricted vocabulary needs an explicit compatibility decision.',
'q-plt-019':'Keep ambiguous write outcomes distinct from known pre-write failure; automatic resend of non-idempotent writes is not presumed safe.',
'q-iter-006':'Keep current failure visibility after startup outage; retry/rebuild needs a lifecycle policy with bounded attempts and readiness semantics.',
'q-iter-004':'Prefer declared YIELD aliases at the public reader, while documenting current handled-call names until the owner decides.',
'q-iter-005':'Prefer validating a requested WHERE independent of row count; current empty-provider acceptance does not settle intent.',
'q-iter-003':'Preserve current database comparison for compatibility and expose the difference from binary Python identity; a portable text rule needs owner choice.',
'q-plt-018':'Treat mapped SQL labels as namespace-global today; assigning every row to a graph needs mapping metadata and migration policy.',
'q-srch-006':'Preserve each current text corpus and rank rule until one common corpus is chosen; common fusion arithmetic alone cannot settle text ranking.',
'q-002':'Keep the explicit redaction guards and list unguarded readers; do not infer that partial-redaction answers are acceptable.',
'q-005':'Record the unsalted digest as built and keep its privacy adequacy open; no guessing or confirmability experiment is in scope.',
'q-006':'Assume completion by rerun after fixing liveness; abandonment needs an owner-approved recovery meaning for partial tombstones.',
'q-007':'Treat the present count as a sum of store effects rather than a count of distinct entities; any stronger public count needs a defined unit.',
'q-str-002':'Prefer the server GraphKey rule for all new names; control-character normalization versus refusal must be documented consistently.',
'q-str-003':'Keep direct create as deduplicating at this pin; the specification planned keyed parallel creation, whose public ID-returning interface is unfinished.',
'q-str-004':'Keep the spec requirement to refuse ambiguous ledger references; do not accept first-row selection as intended parallel-edge semantics.',
'q-tmp-002':'Keep retained aggregate history distinct from surviving raw edges; recomputation after partial raw purge needs an explicit history-retention rule.',
'q-tmp-003':'Treat a paged read as multiple observations today; a point-in-time promise needs an explicit snapshot/version protocol.',
'q-tmp-004':'Keep insert collision as an effect-free accepted temporal call today; ledger record/no-op policy still needs owner choice.',
'q-tmp-005':'Keep temporal-only structural row retention at the opt-out boundary and require drop before opt-in; define last-delete behavior separately.',
'q-tmp-006':'Preserve the temporal implication requirement and record the direct-delete exception; the maintainer must decide whether to refuse or repair it.',
'q-srch-002':'Keep width-compatible undeclared writes to the claimed default table as current compatibility; separate-route enforcement needs an explicit decision.',
'q-srch-003':'Assume no cross-call consistency guarantee until a read/write protocol is chosen; partial-index results remain visible risk, not approved isolation.',
'q-srch-004':'Keep explicit BM25 selection distinct from plain text search; a default-index fallback requires a supported API/corpus decision.',
'q-srch-005':'Preserve token order in reporting skipped terms unless a different order is specified; membership is the existing scoring-relevant fact.',
'q-plt-009':'Keep failures visible in analysis and prefer fail-closed admission; the current fail-open compatibility behavior is not owner ratification.',
'q-plt-010':'Prefer no ready schema record after failed deployment; a partial-ready record would need explicit per-capability admission rules.',
'q-plt-011':'Require an explicit schema choice before a migration with no namespace record; arbitrary fallback schemas are not an inferred supported policy.',
'q-plt-012':'Keep engine read-only guarantees and explicitly list interfaces that ignore access hints; protocol hints and server enforcement need separate decisions.',
'q-plt-013':'Bind proof evidence to exact library/platform builds until source or owner authority permits broader reuse.',
'q-plt-014':'Do not infer proof coverage for accelerated algorithms absent from the gate; extending its inventory needs provider-specific evidence.',
'q-plt-015':'Keep non-USER Owner routing as current availability; cross-namespace native support requires a provider deployment/proof contract.',
'q-plt-016':'Prefer idempotent repeated FHIR events, while preserving current event behavior as observation; event identity and replay retention need owner choice.',
'q-plt-017':'Preserve the documented single-sync restriction and keep competing non-sync writers unestablished; choose serialization or conflict detection explicitly.',
'q-cyp-002':'Keep SQL fallback as the current shadow behavior; fail-fast diagnostic mode remains an unratified alternative.',
'q-cyp-003':'Prefer closing native admission during index-bypassing load; a cache/probe that misses that interval cannot justify current-index reliance.',
'q-cyp-004':'Prefer a consistent structured path value; driver/path-dependent text is current behavior requiring a compatibility decision.',
'q-cyp-005':'Prefer a clear unknown-procedure refusal; preserve present empty results as observed compatibility until the owner decides.',
'q-led-001':'Treat auditor-held original canonical records as required to recompute digests; the product does not promise a retained recoverable preimage.',
'q-led-002':'List snapshots and legacy ledger copies as outside redaction reach; archive-retention/removal policy remains an owner decision.',
'q-led-003':'Prefer refusal of disable during unfinished redaction; resumption and blocked readers require a deliberate lifecycle rule.',
'q-led-004':'Keep namespace-wide bare node IDs in current genesis behavior; graph-specific ledger identity would require a record/migration decision.',
'q-led-006':'Treat verify as requiring quiescent inputs for reliance until a consistent-view protocol is specified; unlocked multi-scan behavior is not a snapshot proof.',
'q-iter-001':'Preserve both accepted property values and structural identity; reserve aliases or introduce a property map only after a compatibility choice.',
'q-con-001':'Keep delivery streaming separate from bounded-memory guarantees; full materialization is current behavior and a memory promise needs a separate bound.',
'q-iter-002':'Prefer an explicit peak reconstruction bound; current per-intermediate graph checks do not settle a final-graph-only policy.',
'q-con-002':'Treat lifecycle diff as an unordered net-change result until a stable script order is specified; consumers must not infer dependency order.',
'q-iter-007':'Keep the current lowest-key representative route distinct from all-parallel-edge shortest path; the optimization domain needs owner choice.',
'q-iter-008':'Preserve the rounded-score tie rule today; giving every positive raw score priority over true zero would change top-k admission.',
}
# Existing canonical owner or a new child under the named owner; a trailing + means add a Q child.
HD={
'0001':None,'0101':'install.schema.refusal.first-use-policy+','0102':'install.setup.failed_deploy','0103':'install.legacy.support-policy+',
'0201':'graph.default.python-read-policy+','0202':'structure.edge.delete','0301':'install.bulk_load.ledger','0302':'temporal.structural.explicit-delete',
'0401':'structure.degree.cache.retirement-policy+','0402':'structure.adjacency.rebuild-concurrency+',
'0501':'temporal.structural.ledger-nodes.policy+','0502':'temporal.ledger.scope-policy+',
'0601':'search.erasure.indexes.coverage-policy+','0602':'search.scope.indexes.publication-policy+','0603':'search.fusion.vector-graph-policy+','0604':'search.embedding.queue.processing.consumers+',
'0701':'search.bm25.write_lock.build-policy+','0702':'search.fusion.absent','0703':'search.bm25.default_index','0704':'search.bm25.name-policy+','0705':'search.fusion.python.support',
'0801':'ledger.strict','0802':'query.graph-scope.read.mapped-label-policy+','0803':'install.legacy.sql-operators-policy+','0804':'query.browser-metadata.ddl-notice-policy+',
'0901':'query.native.privileges.recheck-policy+','0902':'query.shadow.native-failure','0903':'structure.write.reader-isolation-policy+','0904':'query.compiled.fallback.failure-policy+',
'1001':'algorithms.op.walks.result-policy+','1002':'algorithms.op.cdlp','1003':'algorithms.op.paths.direction','1004':'algorithms.op.pagerank',
'1101':'ledger.node-scope.missing-default-policy+','1102':'ledger.lifecycle.settings-transaction-policy+','1103':'ledger.strict.server-policy+','1104':'ledger.lifecycle.settings-policy+','1105':'ledger.commit.post-commit.recorded',
'1201':'erasure.concurrency','1302':'redaction.metadata','1303':'redaction.batches.abort','1304':'redaction.tenant.node-history-policy+','1305':'ledger.idempotency','1401':'ledger.lifecycle.genesis.shared-ids',
'1501':'fhir.ledger','1502':'fhir.erase.durable-removal-policy+','1503':'fhir.sync.other_writers','1504':'fhir.sync.recovery-policy+',
'1601':'access.graph_id','1602':'access.api_key.admin-policy+','1603':'access.retries','1604':'access.surfaces.rest-meta-policy+','1605':'access.webapp.generated-limits-policy+',
'1701':'access.read_only.scope','1702':'access.retries','1703':'algorithms.routing.capability-policy+','1704':'search.embedding.width.raw-helpers+','1705':'access.defaults.exposure','1802':'install.snapshot.consistency-policy+',
}
SETTLED={
'HD-0001':('Method definitions use the literal parent-chain/earlier-same-parent rule. This is a workflow question, not a product contract.','experiment/playbook-uplift/verification-playbook.txt','bfb6f097'),
'HD-0202':('Without an edge ID, direct delete_edge removes the whole triple. A per-edge ID argument is planned, absent at the pin.','specs/234-multigraph-parallel-edges/plan.md','128007c0'),
'HD-0301':('The standalone BulkLoader and raw SQL are expressly outside the client strict-mode guard. That exception does not exempt other engine writers.','specs/213-graph-revision-ledger/contracts/ledger-api.md','04bf1c67'),
'HD-1002':('CDLP returns its last fixed iteration without an in-band settledness flag; the documented diagnostic compares k with k+1.','docs/COMMUNITIES.md','af2bc84e'),
'HD-1004':('Global PageRank promises every default-graph node on every supported route; the hidden Owner output cap violates that documented contract.','iris_vector_graph/_engine/algorithms.py','f3451567'),
'HD-1302':('Decision 2 clears the free text when any record in the revision is tombstoned. The older every-record wording is stale.','docs/adr/0013-redaction-removes-content-from-history.md','42907b21'),
'HD-1305':('A keyed replay returns the original outcome and applies no new effects. How to complete or skip post-commit work is an implementation question; recording those properties remains separately open.','specs/213-graph-revision-ledger/contracts/ledger-api.md',None),
'HD-1601':('The namespace is the authorization boundary; graph IDs scope data operations and do not confer access rights.','docs/USER_GUIDE.md','cc546a29'),
'HD-1704':('The low-level raw DB-API helper pads/truncates and coerces non-finite values as documented. Registry-aware engine writes keep their separate strict contract.','iris_vector_graph/dbapi_utils.py','edd3563b'),
}
def section(s,patterns):
 for pattern in patterns:
  m=re.search(r'^## '+pattern+r'[^\n]*\n(.*?)(?=^## |\Z)',s,re.S|re.M)
  if m:return re.sub(r'\s+',' ',m[1]).strip()
 return ''
def short(s,n=900):return s if len(s)<=n else s[:n].rsplit(' ',1)[0]+'…'
rows=[]
for x,s in zip(I,S):
 ident=x['id'];owners=s['owners'];new=False;kind=None
 if ident.startswith('HD-'):
  p=R/f'experiment/playbook-completion/intent/{ident}.md';intent=p.read_text();owner=HD[ident[3:]]
  if owner:new=owner.endswith('+');owner=owner.rstrip('+');owners=[owner]
  else:owners=[]
  current=section(intent,['As built']);working=section(intent,['Working assumption']);options=section(intent,['Alternatives']);settle=section(intent,['What would change this','Confidence and what would change it','Residual question'])
  if not working:working='Keep the source-supported current contract while the explicit residual policy question remains open.'
  if ident in SETTLED:status='settled existing authority';working,authority,commit=SETTLED[ident];kind='D'
  else:status='open owner decision';authority=None;commit=None;kind='Q'
  if ident=='HD-1704':new=True
 elif ident.startswith('q-'):
  current=re.search(r'^Evidence: (.*?)(?=\n\n(?:Interpretations|Decision|Scope|Working)|\Z)',x['body'],re.M|re.S)
  current=short(re.sub(r'\s+',' ',current[1])) if current else 'The linked canonical owner and preserved register evidence describe current behavior.'
  working=WORK[ident];options=re.search(r'^(?:Interpretations|Options|Alternatives): (.*?)(?=\n\n|\Z)',x['body'],re.M|re.S);options=options[1] if options else 'Preserve the current compatibility behavior or adopt the stronger intended alternative described in the canonical question; their observable difference must be tested.'
  settle='A maintainer statement choosing the contract and scope, or an existing attributable source that explicitly selects it; implementation behavior alone cannot decide intent.'
  qowners=[a for a in owners if O.get(a,{}).get('kind')=='Q'];owners=qowners[-1:] or owners[-1:];new=False;status='open owner decision';kind='Q';authority=commit=None
 elif ident.startswith('REACH-'):
  status='open owner decision';kind='Q';new=True;authority=commit=None
  owner={'REACH-1':'erasure.scope.embedding-queue-policy','REACH-2':'search.quarantine.retention','REACH-3':'search.quarantine.retention','REACH-4':'erasure.kept.snapshot-retention-policy','REACH-5':'erasure.scope.legacy-backup-policy'}[ident];owners=[owner];new=owner not in O
  current=re.sub(r'\s+',' ',x['body'].split('- Today:')[-1].split('- Classification:')[0]).strip();working='Keep these retained copies visible in removal receipts; do not infer a new purge promise from erasure of the live graph.';options='Retain with a truthful out-of-reach declaration, or add an explicit purge/removal policy with graph attribution and recovery costs.';settle='An owner retention/removal decision naming the store, attribution and audit/backup requirements.'
 else:
  status='historical fixed-at-pin report' if ident.startswith('hist-') else 'inherited qualified proof debt';kind=None;new=False;authority=commit=None
  current=x['body'];working='Keep the existing recorded scope; no new verification or human decision is inferred.';options='Reopen if source or relied-on evidence changes.';settle='A discriminating product regression for the historical reports; missing source/handler/environment proofs for debt, not a higher theorem count.'
 rows.append(dict(id=ident,title=x['title'],status=status,owners=owners,new_owner=new,kind=kind,current=short(current),working=short(working),options=short(options),settles=short(settle),authority=authority,commit=commit,sources=s['source_files'],test_files=s['test_files'],intent=(f'experiment/playbook-completion/intent/{ident}.md'if ident.startswith('HD-')else None)))
assert len(rows)==146 and len(WORK)==66
(H/'question-review.json').write_text(json.dumps(rows,indent=2)+'\n')
text='# Question review — all 146 starting IDs\n\nSource behavior and existing attributable contract evidence are separate from owner approval. Nine inherited questions are settled for the pin by existing sources; residual mechanisms remain open where stated. The other policy questions retain agent-provisional assumptions. The 2 historical reports and 14 proof-debt records are separate. Public issue status is not product behavior or approval; see [upstream](upstream.json). The repository has Discussions disabled. Relevant historical intent searches are retained, not presented as a fresh branch-wide search.\n\n'
for x in rows:
 text+=f'<a id="{x["id"]}"></a>\n### {x["title"]}\n\nStatus: {x["status"]}. Canonical owner: '+(', '.join('`'+a+'`'for a in x['owners'])or 'method/historical evidence; no new product owner')+'.\n\n'
 text+='Now: '+x['current']+'\n\nWorking assumption'+(' (existing authority)'if x['status']=='settled existing authority'else ' (agent, unratified)')+': '+x['working']+'\n\n'
 if x['authority']:text+='Authority: ['+x['authority']+'](../../../../'+x['authority']+'); history '+str(x['commit']or 'contract and existing idempotency tests')+'. No new maintainer approval is claimed.\n\n'
 else:text+='Options and implications: '+x['options']+'\n\nSettling evidence: '+x['settles']+'\n\n'
 text+='The code/comments, tests, docs and last product commits consulted are enumerated for this ID in [source-review.json](source-review.json) and [source-catalog.json](source-catalog.json); the longer intent record is retained when present.\n\n'
(H/'question-review.md').write_text(text)
print(json.dumps({'reviewed':len(rows),'settled':len(SETTLED),'new_canonical_owners':sum(x['new_owner']for x in rows),'policy_open':sum(x['status']=='open owner decision'for x in rows)}))
