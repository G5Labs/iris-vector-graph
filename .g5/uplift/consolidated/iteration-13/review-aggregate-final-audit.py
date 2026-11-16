"""Read-only independent ordinary aggregate V3/current-input replay audit."""
from pathlib import Path
import json, hashlib, re, datetime, time, copy

R = Path(__file__).resolve().parents[4]
H = Path(__file__).resolve().parent
D = H / 'review-aggregate-scratch-v2'
S = D / 'repo'
M = Path('.g5/Verus_verification/models/aggregate_results')
started = time.monotonic()

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def audit_receipt(p, root):
    j = json.loads(p.read_text())
    assert all((root/k).is_file() and sha(root/k) == v for k, v in j['inputs'].items()), p
    logs = []
    for rel, digest in j.get('raw_log_copies', {}).items():
        q = root / rel
        assert sha(q) == digest
        text = q.read_text()
        ordinary = bool(re.search(r'assertion failed|postcondition not satisfied|precondition not satisfied', text))
        limited = bool(re.search(r'rlimit.{0,100}exceeded|resource limit|timed out|internal error', text, re.I))
        logs.append(dict(path=str(q.relative_to(root)), sha256=digest, ordinary=ordinary, resource_or_timeout=limited))
    if j['kind'] == 'control':
        o = j['observed']
        assert j['verdict'] == 'EXPECTED_FAIL' and o['errors'] > 0
        assert not o['timed_out'] and not o['has_resource_limit']
        assert all(x['errors'] > 0 and not x['timed_out'] for x in o['per_function'].values())
        assert len(logs) == 1 + len(o['per_function'])
        assert all(x['ordinary'] and not x['resource_or_timeout'] for x in logs)
    if j['kind'] == 'binding':
        assert j['verdict'] == 'AGREES' and j['comparisons'] == 669 and j['fixtures'] == 160
        assert not j['mismatches'] and j['socket_attempts'] == j['native_calls'] == 0
        assert len(j['sensitivities']) == 9 and all(x['detected'] for x in j['sensitivities'])
    return dict(path=str(p.relative_to(root)), sha256=sha(p), kind=j['kind'], verdict=j['verdict'], flat_inputs=len(j['inputs']), logs=logs), j

freeze = json.loads((H/'aggregate-freeze.json').read_text())
assert freeze['version'] == 'V3-actual-observation-comparator'
assert all(sha(R/k) == sha(S/k) == v for k, v in freeze['package_inputs'].items())
assert all(sha(R/k) == sha(S/k) == v for k, v in freeze['flat_binding_inputs'].items())
meta = json.loads((D/'inputs.json').read_text())
assert all(sha(S/k) == sha(R/k) == v for k, v in meta['source_inputs'].items())
scratch, bodies = [], []
for p in sorted((S/'.g5/Verus_verification/results/aggregate_results').glob('*/receipt.json')):
    a, j = audit_receipt(p, S)
    scratch.append(a)
    bodies.append(j)
assert len(scratch) == 14 and sum(x['kind'] == 'control' for x in scratch) == 12
proof = next(x for x in bodies if x['kind'] == 'proof')
binding = next(x for x in bodies if x['kind'] == 'binding')
assert proof['verdict'] == 'PASS' and proof['observed']['verified'] == 75 and proof['observed']['errors'] == 0
assert len(binding['inputs']) == 45
for stem in ['root-aggregate-native', 'root-aggregate-types-native', 'root-optional-aggregate-native']:
    fact = json.loads((H/(stem+'.json')).read_text())
    for field in ['inputs', 'source_inputs']:
        for rel, digest in fact[field].items():
            assert binding['inputs'][rel] == digest and sha(R/rel) == digest

manifest = json.loads((S/M/'model.json').read_text())
source = (S/M/'aggregate_results.rs').read_text()
mutants = []
for c in manifest['controls']:
    fs = list((D/'run-dir/verus/aggregate_results/controls'/c['name']).glob('*/models/aggregate_results/aggregate_results.rs'))
    assert len(fs) == 1 and source.count(c['find']) == 1
    assert fs[0].read_text() == source.replace(c['find'], c['replace'])
    mutants.append(dict(name=c['name'], path=str(fs[0].relative_to(H)), sha256=sha(fs[0])))
empty_controls = [c for c in manifest['controls'] if c['name'] in ['global-empty-row-omitted','grouped-empty-row-fabricated']]
assert len(empty_controls) == 2
assert all('seq!' in c['find'] for c in empty_controls)
assert 'if !q.grouped{seq![Key::Global]}' in empty_controls[0]['find']
assert 'key_order' in empty_controls[1]['find']

obs = [x for x in binding['cases'] if x.get('kind') == 'actual-observation sensitivity']
assert len(obs) == 1
obs = obs[0]
raw = obs['raw']
assert raw == [['g','x','A',2],['g','y','A',2],['g','z','B',None]]
selected = [r for r in raw if r[0] == 'g']
vals = {r[3] for r in selected if r[3] is not None}
wanted = [[len(selected), len(vals)]]
assert obs['wanted'] == obs['produced'] == wanted
changed = copy.deepcopy(obs['produced'])
changed[0][0] += 1
assert obs['corrupted'] == changed and changed != wanted
assert obs['baseline_agrees'] and obs['corrupted_rejected'] and obs['trace']
assert 'COUNT(*)' in obs['trace'][0]['source'] and 'COUNT(DISTINCT' in obs['trace'][0]['source']
binding_text = (S/M/'binding.py').read_text()
assert 'assert comparator(produced.rows)' in binding_text
assert 'not comparator(corrupted)' in binding_text

central = []
for row in freeze['final_receipts']:
    p = R/row['receipt']
    assert sha(p) == row['sha256']
    central.append(audit_receipt(p, R)[0])
assert len(central) == 14
runs, events = [], []
for p in sorted((D/'runs').iterdir()):
    j = json.loads((p/'result.json').read_text())
    assert j['exit_code'] == 0 and j['inputs_unchanged']
    drift = {k for k, v in j['active_source_still_equal'].items() if not v}
    assert not drift or (p.name.endswith('-upstream') and drift == {str(M/'binding.py'), str(M/'NOTES.md')})
    text = (p/'raw.log').read_text()
    assert 'REVIEW_OUTER_SOCKET_CONNECT_CALLS 0' in text
    if p.name.endswith('-upstream'):
        assert '109 passed' in text
    runs.append(dict(path=str(p.relative_to(H)), op=p.name.rsplit('-',1)[1], elapsed_s=j['elapsed_s'], raw_log_sha256=sha(p/'raw.log'), git_reads=j['git_read_count']))
    if (p/'subprocess.jsonl').exists():
        events += [json.loads(s) for s in (p/'subprocess.jsonl').read_text().splitlines()]
assert len(runs) == 4 and sum(x['git_reads'] for x in runs) == 0
all_verus = [x for x in events if Path(x['argv'][0]).name == 'verus']
verus = [x for x in all_verus if any(a.endswith('.rs') for a in x['argv'])]
versions = [x for x in all_verus if x['argv'][1:] == ['--version']]
assert len(verus) == 25 and len(versions) == 13 and len(all_verus) == 38
assert all('--num-threads' in x['argv'] and x['argv'][x['argv'].index('--num-threads')+1] == '4' for x in verus)
counts = json.loads((H/'review-aggregate-results-counts.json').read_text())
assert counts['total_units'] == 75 and counts['new_units'] == 62 and counts['imported_units'] == 13
assert counts['proof_units'] == 58 and counts['recursive_spec_units'] == 17 and counts['nonlinear_subquery_units'] == 0
new, old = counts['files']
assert new['proof_units'] == 46 and new['recursive_spec_units'] == 16
assert old['proof_units'] == 12 and old['recursive_spec_units'] == 1
assert sum(n.startswith('theorem_') for n in new['proof_query_declarations']) == 38
assert sum(n.startswith('lemma_') for n in new['proof_query_declarations']) == 8
assert not any(x['decreases_by_hint_declarations'] for x in counts['files'])
roles = json.loads((H/'aggregate-source-roles.json').read_text())
assert roles['active_count'] == 6 and sum(x['role'] == 'bounded-active' for x in roles['roles']) == 6
native_active = [x['symbol'] for x in roles['roles'] if x['role'] == 'bounded-active' and x['path'].endswith('.cls')]
assert native_active == ['Group','GroupOf','EmitGroups']

out = dict(verdict='ACCEPT_BOUNDED_ORDINARY_AGGREGATE_FRAGMENT', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), package=freeze['package_inputs'], current_scratch_bytes_equal=True, verified=75, new_units=62, new_proof_queries=46, new_recursive_spec_queries=16, imports=dict(units=13, proof_queries=12, recursive_spec_queries=1), NLA=0, extra_hints=0, controls=12, all_full_and_named_ordinary=True, mutant_inputs=mutants, scratch_receipts=scratch, central_fresh_receipts=central, binding=dict(comparisons=669, fixtures=160, sensitivities=dict(actual_python=7, SQL_provider=1, actual_observation=1), all_detected=True, flat_inputs=45, native_fact_maps_flat_and_current=True, observation_raw_oracle_and_actual_output_checked=True, sockets=0, native=0), upstream_passed=109, runs=runs, measured_replay_command_s=sum(x['elapsed_s'] for x in runs), audit_s=time.monotonic()-started, actual_verification_commands=25, verus_version_metadata_queries=13, total_verus_binary_invocations=38, actual_git_reads=0, git_mutations=0, reviewer_native_calls=0, interrupted_inputs_opened_or_reused=False, V1_preservation='review-aggregate-scratch-v1; aggregate-v1-spec-controls (builder)', V2_preservation='review-aggregate-scratch-v2/preserved-v2-before-observation-refresh; aggregate-v2-observation-miss (builder)', V3_qualification='Proof/controls/upstream ran exact V2 rs/manifest/imports, unchanged in V3; binding and NOTES refreshed then binding independently rerun. Only binding/NOTES advanced while V2 upstream ran; neither was used by product upstream tests. All exact scratch inputs remained unchanged.', roles_recommended_active=6, role_tiers=dict(actual_python=3, inspected_typed_transcription=3), observation_roles=14, direct_executable_bodies_verified=0, residuals=['ORDER BY relation is a complete unique permutation/provider premise; the theorem proves aggregation-before-page and projection, not generic SQL ordering/collation.', 'Exact integer/half-unit SUM/AVG fragment and canonical SQL numeric/typed-text carriers; arbitrary binary64, overflow, NaN, general coercion and JSON codecs remain provider boundaries.', 'Native Group/GroupOf/EmitGroups are inspected typed transcriptions at pW=1 with ordinary nonnull identity/key/order frames; fresh native facts execute SQL routes and do not upgrade native-body evidence.', 'OPTIONAL synthetic-null grouped SUM path remains partial/observation and violates newer R308 zero identity in fresh native case; existing new ordinary bug-agg-001 retains as-built null rather than claiming proof.', 'Internal ASCII generated-column projection is proved; arbitrary alias collisions, Unicode name regex, all error/empty-column branches and complete finalizer are not whole-member proofs.'])
(H/'review-aggregate-final-validation.json').write_text(json.dumps(out, indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['verdict','verified','new_units','controls','binding','upstream_passed','measured_replay_command_s','audit_s']}))
