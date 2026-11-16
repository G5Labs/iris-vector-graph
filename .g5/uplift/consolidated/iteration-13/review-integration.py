"""Independent, read-only final ordinary13 integration audit; no Git/native/network."""
from pathlib import Path
import ast, collections, csv, datetime, hashlib, importlib.util, io, json, re, tarfile, time

R = Path(__file__).resolve().parents[4]
H = Path(__file__).resolve().parent
start = time.monotonic()
checks, inputs = [], {}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read(rel):
    p = R / rel
    b = p.read_bytes()
    inputs[str(rel)] = sha(b)
    return b

def js(rel):
    return json.loads(read(rel))

def rows(data):
    return list(csv.DictReader(io.StringIO(data.decode()), delimiter='\t'))

def ck(name, truth):
    checks.append(dict(name=name, passed=bool(truth)))
    assert truth, name

def owner_bodies(text):
    return {m[1]: m[2] for m in re.finditer(r'^<a id="([^"]+)"></a>\n\[[IDQ] · [^\]]+\]\n(.*?)(?=^<a id=|^## |\Z)', text.split('## Metadata')[0], re.M | re.S)}

def entry_bodies(text):
    return {m[1]: m[0] for m in re.finditer(r'^<a id="([^"]+)"></a>\n.*?(?=^<a id=|^## |\Z)', text, re.M | re.S)}

meta = js(H.relative_to(R)/'inputs.json')
archive = Path(meta['before_archive'])
archive_sha = sha(archive.read_bytes())
ck('fixed sealed12 before archive SHA unchanged', archive_sha == meta['before_archive_sha256'] == '772cdc28ad309dee5abbb9c0e1e8e7f82c854be5e44a89967c06ce19ca3f80d0')
old = {}
selected = {
    '.g5/Verus_verification/crosswalk/decision-links.tsv', '.g5/Verus_verification/families.tsv',
    '.g5/Verus_verification/bugs_issues.md', '.g5/Verus_verification/design_simplification.md',
    '.g5/Verus_verification/open_questions.md', '.g5/Verus_verification/crosswalk/findings.tsv',
    '.g5/Verus_verification/crosswalk/statements.tsv',
    '.g5/uplift/consolidated/iteration-12/after-reach/bindings.json',
    '.g5/uplift/consolidated/iteration-12/after-reach/census.json',
    '.g5/uplift/consolidated/iteration-12/builder-scores.json',
}
with tarfile.open(archive, 'r:gz') as t:
    for member in t.getmembers():
        rel = member.name.removeprefix('./')
        if member.isfile() and (rel in selected or (rel.startswith('.g5/ontology/') and rel.endswith('.md'))):
            old[rel] = t.extractfile(member).read()
ck('all selected completed-seal files present', selected <= old.keys())
before_dir = H/'review-integration-before'
before_dir.mkdir(exist_ok=True)
for rel, data in old.items():
    q = before_dir/rel
    q.parent.mkdir(parents=True, exist_ok=True)
    if q.exists():
        assert q.read_bytes() == data
    else:
        q.write_bytes(data)

o, n = {}, {}
for rel, data in old.items():
    if rel.startswith('.g5/ontology/'):
        o.update(owner_bodies(data.decode()))
        n.update(owner_bodies(read(rel).decode()))
ck('403 inherited owner bodies exact, only two ordinary owners added', len(o) == 403 and len(n) == 405 and set(n)-set(o) == {'install.status','query.aggregation'} and all(n[k] == v for k,v in o.items()))
status_text = read('.g5/ontology/concepts/install.g5.md').decode()
aggregate_text = read('.g5/ontology/features/cypher.g5.md').decode()
ck('status owner distinguishes all graphs, legacy routes, partial counts and unknown', all(s in n['install.status'] for s in ['every graph','ordinary count methods','distinct legacy or registered table','without a registry','completed counts','unknown']))
ck('status correspondence explicitly requires stable registry outcome across two scans', 'stable registry view and refusal outcome across the two kind scans' in status_text and 'transient per-read registry changes' in status_text)
ck('status metadata excludes ancillary/provider/snapshot truth and separates per-field unknown', all(s in status_text for s in ['native/index/schema truth','cross-read snapshots','Label/property/edge-vector errors do not by themselves make graph size unknown']))
ck('aggregate owner keeps intended SUM zero identity and typed WITH/collection/page', all(s in n['query.aggregation'] for s in ['SUM leaves out null and returns 0','WITH','collection','ordering, skipping and limiting','declared return columns']))
ck('aggregate metadata explicitly qualifies inspected native roles and partial OPTIONAL', all(s in aggregate_text for s in ['inspected typed count transcriptions only','SQL native panels do not execute those bodies','OPTIONAL synthetic fallback remains observed and partial','newer all-null SUM regression','older [R298 helper test]']))

link_rel = '.g5/Verus_verification/crosswalk/decision-links.tsv'
link_bytes = read(link_rel)
old_links, all_links = rows(old[link_rel]), rows(link_bytes)
added = all_links[len(old_links):]
ck('355 inherited source rows retained as exact byte prefix, 35 appended', len(old_links) == 355 and link_bytes.startswith(old[link_rel]) and len(all_links) == 390 and len(added) == 35)
families = rows(read('.g5/Verus_verification/families.tsv'))
old_families = rows(old['.g5/Verus_verification/families.tsv'])
ck('only two new active families appended, inherited family bytes preserved', read('.g5/Verus_verification/families.tsv').startswith(old['.g5/Verus_verification/families.tsv']) and [x['family_id'] for x in families[len(old_families):]] == ['C-routine_reporting','C-aggregate_results'])
ck('21 active and 14 observation links in correct two families', collections.Counter(x['relation'] for x in added) == {'models':21,'observes':14} and collections.Counter(x['family'] for x in added) == {'C-routine_reporting':15,'C-aggregate_results':20})

hr = H.relative_to(R)
outcomes = js(hr/'member-outcomes.json')
roles = outcomes['roles']
active = [r for r in roles if r['relation'] == 'models']
obs = [r for r in roles if r['relation'] == 'observes']
rr = js(hr/'reporting-integrated-roles.json')['active_roles']
ar = js(hr/'aggregate-integrated-roles.json')['roles']
ck('role ledgers compose all35 outcome rows', len(roles) == 35 and len(active) == 21 and len(obs) == 14 and {r['member'] for r in roles} == {r['member'] for r in rr+ar})
ck('direct-body and whole-member claims remain zero/false', outcomes['direct_body_verified'] == 0 and all(not r['direct_executable_body_verified'] and not r['whole_member_claim'] for r in roles))
ck('new active evidence tiers exactly18Python and3inspected native', collections.Counter(r['evidence_tier'] for r in active) == {'actual-python-executing-local-sql-provider':18,'inspected-typed-transcription-no-native-execution':3})
native = [r for r in active if r['member'].endswith(('::Group','::GroupOf','::EmitGroups'))]
ck('only the three inspected native helpers get new native transcription roles', len(native) == 3 and all(r['evidence_tier'] == 'inspected-typed-transcription-no-native-execution' for r in native))
ck('reporting Registry frame appears in integrated scopes', all('same raw registry view/refusal outcome for both kind scans' in r['scope'] for r in rr if 'admin.py::' in r['member']))
ck('observations remain explicitly uncredited', all(r['outcome'] == 'observation-only-no-new-credit' and r['evidence_tier'] == 'observation-only' and 'Uncredited observation/dependency only:' in r['scope'] for r in obs))

before = js(hr/'before-reach/bindings.json')
after = js(hr/'after-reach/bindings.json')
census = js(hr/'before-reach/census.json')
ck('before maps exact completed12 after maps, same4130 census', before == json.loads(old['.g5/uplift/consolidated/iteration-12/after-reach/bindings.json']) and census == json.loads(old['.g5/uplift/consolidated/iteration-12/after-reach/census.json']) and census == js(hr/'after-reach/census.json') and len(census) == 4130)
ck('231 to249 actual distinct member delta, no losses', len(before) == 231 and len(after) == 249 and not set(before)-set(after) and len(set(after)-set(before)) == 18)
ck('all inherited member bindings retained, no evidence recategorization', all(after[k][:len(v)] == v for k,v in before.items()))
new = set(after)-set(before)
strengthened = {r['member'] for r in active if r['member'] in before}
ck('18new and3strengthened exactly equal active-role reach delta', new == {r['member'] for r in active if r['member'] not in before} and len(strengthened) == 3)
maps = js(hr/'before-after-member-maps.json')
ck('before-after ledger records exact maps and sets', maps['before'] == before and maps['after'] == after and set(maps['new_members']) == new and set(maps['strengthened_members']) == strengthened and maps['lost_members'] == [])
ck('member JSON aggregate counters independently agree', [outcomes[k] for k in ['before','after','denominator','new','strengthened','lost','active_roles','observation_roles']] == [231,249,4130,18,3,0,21,14])
tsv = rows(read(hr/'member-outcomes.tsv'))
ck('member TSV same35 outcomes/scopes/tiers as JSON', len(tsv) == 35 and all(all(t[k] == str(r[k]) for k in t) for t,r in zip(tsv,roles)))

ast_cache = {}
def declarations(path):
    if path in ast_cache:
        return ast_cache[path]
    text = read(path).decode()
    result = {}
    if path.endswith('.py'):
        def walk(node, scope=''):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result.setdefault(scope+node.name, []).append(node.lineno)
                return
            if isinstance(node, ast.ClassDef):
                result.setdefault(scope+node.name, []).append(node.lineno)
                for child in node.body:
                    walk(child, scope+node.name+'.')
                return
            for child in ast.iter_child_nodes(node):
                walk(child, scope)
        walk(ast.parse(text))
    else:
        for index,line in enumerate(text.splitlines(),1):
            m = re.match(r'^\s*(?:ClassMethod|Method)\s+(\w+)', line)
            if m:
                result.setdefault(m[1], []).append(index)
    ast_cache[path] = result
    return result

for row in added:
    key = row['path']+'::'+row['symbol']
    ck('source/formal locator '+key, key in census and declarations(row['path']).get(row['symbol']) == census[key]['lines'] == [int(row['pin lines'])] and len([r for r in roles if r['member'] == key and r['formal_item'] == row['formal item'] and r['relation'] == row['relation'] and r['block'] == row['block']]) == 1)
    path, sep, fn = row['formal item'].partition('::')
    ck('formal item exists exactly once '+fn, bool(sep) and len(re.findall(r'\bfn\s+'+re.escape(fn)+r'\b', read(path).decode())) == 1)

bug_rel = '.g5/Verus_verification/bugs_issues.md'
old_entries = entry_bodies(old[bug_rel].decode())
new_entries = entry_bodies(read(bug_rel).decode())
ck('433 inherited bug entries byte exact, only ordinary agg001 added', len(old_entries) == 433 and len(new_entries) == 434 and set(new_entries)-set(old_entries) == {'bug-agg-001'} and all(new_entries[k] == v for k,v in old_entries.items()))
ck('new issue remainsLowOpen, controlled fresh ordinary scope, older/newer authority explicit', all(s in new_entries['bug-agg-001'] for s in ['Severity: Low · Decision: Open','source-informed ordinary discovery','fresh graph','R308','R298','synthetic','not private']))
for rel in ['.g5/Verus_verification/design_simplification.md','.g5/Verus_verification/open_questions.md']:
    ck('unchanged '+rel, read(rel) == old[rel])
findings = rows(read('.g5/Verus_verification/crosswalk/findings.tsv'))
old_findings = rows(old['.g5/Verus_verification/crosswalk/findings.tsv'])
ck('findings crosswalk retains old rows plus one ordinary finding', read('.g5/Verus_verification/crosswalk/findings.tsv').startswith(old['.g5/Verus_verification/crosswalk/findings.tsv']) and len(findings) == len(old_findings)+1 and 'bug-agg-001' in str(findings[-1]))
ck('statements crosswalk retains old403 rows plus two owners', read('.g5/Verus_verification/crosswalk/statements.tsv').startswith(old['.g5/Verus_verification/crosswalk/statements.tsv']) and len(rows(read('.g5/Verus_verification/crosswalk/statements.tsv'))) == 405)
register = read('.g5/Verus_verification/findings.md').decode()
ck('findings index consistent434/55/146 and native244of403', '| 434 | 48 | 130 | 225 | 31 | 244 of 403 |' in register and '| 55 | 16 | 25 | 13 | 1 | n/a |' in register and '| 146 | 1 | 23 | 42 | 16 | n/a |' in register and 'bug-agg-001' in register)

baseline = js(hr/'before-builder-scores.json')
scores = js(hr/'builder-scores.json')
ck('before diagnostic bytes exact completed12 ledger', read(hr/'before-builder-scores.json') == old['.g5/uplift/consolidated/iteration-12/builder-scores.json'] and len(baseline['rows']) == 49)
ck('full original49rows retained exactly', scores['carried_rows'] == baseline['rows'])
ck('49 prior after grades bridge to both before/after without regrade', len(scores['rows']) == 60 and all(r['id'] == oldr['id'] and r['before'] == r['after'] == oldr['after'] and r['prior_row_sha256'] == sha(json.dumps(oldr,sort_keys=True,separators=(',',':')).encode()) for r,oldr in zip(scores['rows'][:49],baseline['rows'])))
extensions = scores['rows'][49:]
ck('11overlapping extensions derive8supported/3partial models and9/2ontology', len(extensions) == 11 and collections.Counter(r['after']['model']['grade'] for r in extensions) == {'supported':8,'partial':3} and collections.Counter(r['after']['ontology']['grade'] for r in extensions) == {'supported':9,'partial':2})
ck('diagnostic limits remain explicit, not whole-surface/population/private grading', all(r['limits'] and not r['whole_public_surface_claim'] for r in extensions) and 'overlapping' in scores['authority'] and 'no independent/private grading' in scores['authority'] and not scores['private_inputs_read'])
ck('three residuals and bounded ORDER/Registry frames not scoredcomplete', {r['id'] for r in extensions if r['after']['model']['grade'] == 'partial'} == {'A13-5','A13-6','R13-5'} and 'permutation premise' in extensions[3]['limits'] and 'Stable registry' in next(r['limits'] for r in extensions if r['id'] == 'R13-2'))

accepted_r = js(hr/'review-reporting-final-validation.json')
accepted_a = js(hr/'review-aggregate-final-validation.json')
for name, digest in accepted_r['package'].items():
    ck('reporting accepted bytes unchanged '+name, sha(read('.g5/Verus_verification/models/routine_reporting/'+name)) == digest)
for rel,digest in accepted_a['package'].items():
    ck('aggregate accepted bytes unchanged '+rel, sha(read(rel)) == digest)
receipt_count = 0
for accepted in [accepted_r, accepted_a]:
    for row in accepted['central_fresh_receipts']:
        p = row['path']
        receipt = js(p)
        ck('final receipt+flat inputs fresh '+p, sha(read(p)) == row['sha256'] and all(sha(read(k)) == v for k,v in receipt['inputs'].items()))
        receipt_count += 1
ck('31 central final receipts remain fresh', receipt_count == 31)
ck('independent unit classification97new76proof21rec13imports110total', accepted_r['verified'] + accepted_a['verified'] == 110 and accepted_r['new_ordinary_proof_queries'] + accepted_a['new_proof_queries'] == 76 and accepted_r['new_recursive_spec_queries'] + accepted_a['new_recursive_spec_queries'] == 21 and accepted_a['imports']['units'] == 13)

native_final = js(hr/'ordinary-native-facts-final.json')
native_original = js(hr/'ordinary-native-facts.json')
ck('native aggregate distinguishes16forecasts from15references+1difference', [native_final[k] for k in ['cases','source_forecast_agreements','ordinary_or_zero_reference_agreements','reference_differences']] == [16,16,15,1])
ck('original12panel manifest stays12; final adds4 without replacing first facts', sum(x['cases'] for x in native_original['groups']) == 12 and len(native_final['groups']) == 3 and all(native_final['inputs'].get(k) == v for k,v in native_original['inputs'].items()))
ck('all16fact panel bytes/current maps preserved', all(sha(read(k)) == v for k,v in native_final['inputs'].items()))
ck('native scope explicitly excludes body/provider/population claims', all(s in native_final['scope'] for s in ['source-informed','No interrupted','native body proof','unseen/population']))

accounting = js(hr/'accounting.json')
expected = dict(new_units=97,new_ordinary_proof_queries=76,new_recursive_spec_queries=21,new_theorems=58,new_helpers=18,new_source_proof_declarations=76,checked_hint_declarations=0,NLA=0,unchanged_import_units=13,total_units=110,controls=27,main_binding_comparisons=11873,actual_python_sensitivities=15,provider_sensitivities=1,actual_observation_sensitivities=1,upstream_tests=220,native_cases=16,native_source_forecasts_agree=16,native_reference_agree=15,native_reference_differences=1,source_before=231,source_after=249,source_denominator=4130,new_members=18,strengthened_members=3,lost_members=0,active_source_roles=21,observation_roles=14,direct_executable_bodies_verified=0,ontology_before=403,ontology_after=405,old_body_changes=0,findings_before=433,findings_after=434,simplifications=55,questions=146,builder_diagnostic_rows=60)
ck('root accounting matches independently derived quantities', all(accounting[k] == v for k,v in expected.items()))
ck('cost ledger agrees with independent measured commands', accounting['cost']['reporting_review_command_s'] == accepted_r['measured_replay_command_s'] and accounting['cost']['aggregate_review_command_s'] == accepted_a['measured_replay_command_s'] and accounting['cost']['reviewer_verification_commands'] == 56 and accounting['cost']['reviewer_version_metadata_queries'] == 29)
ck('no convergence/private grade/token cost invented', accounting['convergence'].startswith('unsupported') and 'unavailable' in accounting['cost']['tokens_cache_currency_solver_only_cpu'] and accounting['policy_or_owner_decisions'] == accounting['product_repairs'] == 0)
fresh = js(hr/'freshness-controls.json')
ck('23disposable freshness cases expected with no active mutation', fresh['verdict'] == 'PASS_GLOBAL_AND_FLAT_ORDINARY_FRESHNESS' and len(fresh['controls']) == 23 and fresh['all_expected'] and not fresh['active_inputs_mutated'] and fresh['failure'] is None and all(c['passed'] and c['expected'] == c['observed'] and not c['active_inputs_mutated'] for c in fresh['controls']))
spec = importlib.util.spec_from_file_location('independent_ordinary13_gate', R/'.g5/Verus_verification/tools/correspondence_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
correspondence = js(hr/'correspondence-inputs.json')
ck('current full file/name formal+product manifest exact', gate.inputs(R) == correspondence)
gate_log = read(hr/'consolidated-gate.log').decode()
ck('root mechanical gate passed405blocks390links and freshness', gate_log.rstrip().endswith('PASS') and '405 block(s): 0 issue(s), 0 writing warning(s)' in gate_log and '390 links; every symbol and formal item resolves uniquely' in gate_log and 'FRESH' in gate_log and '"changed_formal": []' in gate_log)
validation = js(hr/'validation.json')
ck('central validation matches accounting and final counts, audit-pending state honest', all(validation[k] == v for k,v in accounting.items()) and validation['central_final_receipts'] == validation['scratch_final_receipts'] == 31 and validation['private_evaluator_grade'] is None and validation['status'] == 'INTEGRATED_ACCEPTED_PACKAGES_FINAL_CENTRAL_AUDIT_PENDING')
guide = Path(meta['public_scoring_guide'])
ck('same public scoring guide', sha(guide.read_bytes()) == meta['public_scoring_guide_sha256'] == validation['public_scoring_guide_sha256'])
ck('all audited current inputs stable during read-only audit', all(sha((R/k).read_bytes()) == v for k,v in inputs.items()))

out = dict(verdict='PASS_FINAL_ORDINARY13_CENTRAL_INTEGRATION', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), checks=checks, checks_passed=len(checks), inputs=inputs, before_archive_sha256=archive_sha, exact_before_copies=str(before_dir.relative_to(H)), independently_derived=expected, package_receipts_fresh=31, current_package_hashes_equal_accepted=True, source_roles=dict(active=21,observation=14,new_members=18,strengthened=3,lost=0,actual_python=18,native_inspected_typed=3,direct_body=0), diagnostic=dict(rows=60,carried_unchanged=49,extensions=11,model_supported=8,model_partial=3,ontology_supported=9,ontology_partial=2,rate_claim=False), native=dict(cases=16,source_forecasts_agree=16,references_agree=15,difference=1,reviewer_calls=0), elapsed_s=time.monotonic()-start, new_prover_or_test_runs=0, git_reads=0,git_mutations=0,network_calls=0,shared_or_product_writes=0,interrupted_inputs_opened_or_reused=False,private_evaluator_read=False,concrete_misses=[],qualifications=['Stable registry view/refusal outcome across both kind scans; no arbitrary transient cross-read history closure.','ORDER BY is a complete unique permutation/provider relation; page composition does not prove generic SQL sorting/collation.','Native Group/GroupOf/EmitGroups remain inspected typed transcriptions at the admitted pW1/nonnull/key/order frame; root native SQL observations do not execute those bodies.','OPTIONAL grouped SUM remains partial and counted as one intended-reference difference, with fresh ordinary bug-agg-001; source forecast agreement is not conformance.','Original12 manifest is still12 and its8+4panel input map is a subset of final16; historical byte identity of the manifest itself was not independently captured earlier, so that additional root historical assertion is not upgraded here.'])
(H/'review-integration.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['verdict','checks_passed','package_receipts_fresh','source_roles','diagnostic','native','elapsed_s','concrete_misses']}))
