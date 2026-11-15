"""Read-only source/native-record audit; never imports any root native script."""
import datetime,hashlib,json,math,re
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
local=json.loads((HERE/'review-seed-probe.json').read_text());assert local['verdict']=='SOURCE_CONTRAST_OBSERVED' and local['case_count']==6 and local['socket_calls']==local['native_calls']==0 and local['failure'] is None
for raw,want in local['inputs'].items():assert sha(ROOT/raw)==want
for raw,info in local['source_inputs'].items():assert sha(PIN/raw)==sha(ROOT/raw)==info['sha256']
n=json.loads((HERE/'root-seed-native.json').read_text());assert n['verdict']=='AGREES_SOURCE_PREDICTION' and n['failure'] is None and n['completed_cases']==len(n['cases'])==5 and n['identity_checked']
for raw,want in n['inputs'].items():assert sha(ROOT/raw)==want
for raw,want in n['source_inputs'].items():assert sha(PIN/raw)==sha(ROOT/raw)==want
seed,peer=n['seed'],n['peer'];checks=[]
for c in n['cases']:
 expected=[peer] if not c['injected_generic_fault'] else ([seed,peer][:c['k']] if c['query']==seed else [seed])
 assert [x[0] for x in c['result']]==expected
 for node,score in c['result']:assert isinstance(score,float) and abs(score-(1 if node==seed else 1/math.sqrt(2)))<1e-12
 actual_faults=[e for e in c['sql'] if 'injected_error' in e];assert len(actual_faults)==int(c['injected_generic_fault'])
 score=[e for e in c['sql'] if 'VECTOR_COSINE' in e['sql'].upper()];assert score
 if c['query']==seed:assert 'n.node_id != ?' in score[0]['sql']
 if c['injected_generic_fault']:
  completed=[e for e in score if 'injected_error' not in e];assert completed and 'n.node_id != ?' not in completed[-1]['sql']
  assert completed[-1]['params'][0].startswith('[')
 violated=c['query']==seed and c['injected_generic_fault'];assert c['violates_seed_exclusion']==violated
 checks.append({'label':c['label'],'ids':expected,'intent_violation':violated,'injected_faults':len(actual_faults),'score_attempts':len(score),'agrees':True})
old_audit=json.loads((HERE/'review-native-audit.json').read_text());original13={raw:want for raw,want in old_audit['artifacts'].items() if 'root-vector-native.' in raw}
assert all(sha(ROOT/raw)==want for raw,want in original13.items())
old=json.loads((HERE/'root-vector-attempt1.json').read_text());prediction_key=str((HERE/'root-vector-predictions.md').relative_to(ROOT));recovered=HERE/'root-vector-attempt1-predictions.md';assert sha(recovered)==old['inputs'][prediction_key]
provenance=HERE/'root-vector-attempt1-provenance.json';assert provenance.is_file()
corpora=['bugs_issues.md','open_questions.md','design_simplification.md'];dedup={};terms=[r'query.{0,30}node',r'self[- ]?neigh',r'\bseed\b',r'exclude_id',r'(exclud|left out).{0,40}(node|answer)',r'node.{0,40}(exclud|left out)']
for file in corpora:
 p=ROOT/'.g5/Verus_verification'/file;hits=[]
 for section in re.split(r'(?=\n### )',p.read_text()):
  flat=' '.join(section.split())
  if re.search(r'kg_KNN_VEC|VectorMixin|kg_KNN_VEC_python_optimized',flat) and any(re.search(t,flat,re.I) for t in terms):hits.append(next((l for l in section.splitlines() if l.startswith('### ')),section[:60]))
 dedup[file]={'sha256':sha(p),'same_surface_synonym_section_candidates':hits}
assert not any(x['same_surface_synonym_section_candidates'] for x in dedup.values())
files=[HERE/'review-seed-predictions.md',HERE/'review-seed-probe.py',HERE/'review-seed-probe.json',HERE/'review-seed-probe.log',HERE/'review-seed-intent.md',Path(__file__),recovered,provenance]+[HERE/('root-seed-native'+e) for e in ['.py','.json','.log']]+[HERE/'root-seed-predictions.md']
out={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'READ_ONLY_SEED_AUDIT_AGREES','local_source_cases':6,'native_records_audited':5,'root_native_case_checks':checks,'probe_body_elapsed_s':local['elapsed_s'],'probe_failures':[],'native_executed_by_reviewer':0,'sockets':0,'candidate_files_inspected':[],'dedup':dedup,'intent':'Existing kg_KNN_VEC API/user/canonical seed exclusion; vec_expand differsurface intentionally includesseed','recommendation':'Distinct Low provider-conditioned seed-to-literal fallback identity-loss finding; root adjudicates, no register/model/shared edits by reviewer','historical_prediction_recovery':{'file':str(recovered.relative_to(ROOT)),'matches_old_input_digest':True,'original_native13_files_unchanged':True,'old_audit_left_unchanged':True},'inputs':{str(p.relative_to(ROOT)):sha(p) for p in files},'scope':'Independent finite source execution and static audit of actual root-native records; one controlled generic first-score exception is injected. No organic outage/native-body/refusal-all-carriers/wholemember proof.'}
(HERE/'review-seed-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'source_cases':6,'native_records':5,'duplicate_roots_located':0,'native_executed':0,'prediction_recovered_exactly':True}))
