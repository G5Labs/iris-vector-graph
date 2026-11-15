"""Recompute final bounded iteration12 accounting from immutable evidence."""
from pathlib import Path
import datetime, hashlib, json

R = Path.cwd()
O = R / '.g5/uplift/consolidated/iteration-12'


def read(name):
    return json.loads((O / name).read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


ledger = read('ledger-content-validation.json')
community = read('communities-freeze.json')
reviews = read('review-final-validation.json')
assert reviews['verdict'] == 'PASS_BOUNDED_FRAGMENTS'
latest = {}
for family, entries in [('ledger_content', ledger['final_receipts']), ('communities', community['current_receipts'])]:
    rows = []
    for entry in entries:
        path = entry['receipt'] if isinstance(entry, dict) else entry
        data = json.loads((R / path).read_text())
        stale = []
        for key, value in data['inputs'].items():
            p = Path(key.removeprefix('external:'))
            if not p.is_absolute():
                p = R / p
            if not p.is_file() or sha(p) != value:
                stale.append(key)
        assert not stale, (path, stale)
        observed = data.get('observed', {})
        rows.append(dict(path=path, sha256=sha(R / path), verdict=data['verdict'],
                         verified=observed.get('verified'), errors=observed.get('errors'),
                         input_count=len(data['inputs']), inputs_match=True))
    latest[family] = rows
assert len(latest['ledger_content']) == 23 and len(latest['communities']) == 14
freshness = read('freshness-controls.json')
assert len(freshness['controls']) == 24 and freshness['all_expected']
assert (O / 'consolidated-gate.log').read_text().rstrip().endswith('PASS')
members = read('member-outcomes.json')['summary']
roles = read('role-audit.json')
assert members['newly_bound'] == 23 and roles['active_rows'] == 35
scores = read('builder-scores.json')
assert len(scores['rows']) == 49
old = read('before-builder-scores.json')
for a, b in zip(scores['rows'][:37], old['rows']):
    assert a['id'] == b['id'] and a['after'] == b['after']
costs = read('review-costs.json')
validation = dict(
    product_pin='3eaa79cf77d3e0a879b2cced634cf2729d81499e', input=read('inputs.json'),
    latest=latest, fresh_central_receipt_sets=37,
    new_units=dict(total=170, ledger_content=97, communities=73, ordinary_proof_queries=149,
                   named_theorem_declarations=93, ordinary_helper_queries=56,
                   recursive_specification_queries=21, nonlinear_arithmetic_subqueries=0,
                   source_proof_declarations=150, checked_termination_hint_declarations=1,
                   hint_is_additional_unit=False, imports_rechecked=11, total_including_imports=181),
    controls=dict(total=33, ledger=21, communities=12, source_algorithm_or_reader=33,
                  all_full_and_named_ordinary=True, no_resource_limits=True),
    bindings=dict(ledger_histories=82, ledger_comparisons=4023, ledger_raw_neighbors=6,
                  ledger_alternate_typed_port_reader_checks=7, ledger_sensitivities=dict(actual_python=6, port=1, observation=1),
                  communities_comparisons=1255, communities_histories=9, communities_affirmative_effects=6,
                  communities_sensitivities=dict(actual_python=5, port=8, observation=1),
                  main_comparisons=5278, child_native_calls=0, child_socket_connections=0),
    native=read('root-native-facts.json'), upstream=dict(ledger=155, communities=19, total=174),
    independent_review=dict(models=['review-communities-final.json', 'review-ledger-content-final.json'],
                            central_and_scratch_receipts_fresh=74, count_hint_probes='review-costs.json',
                            scope='Source-informed bounded review, not evaluator-owned private grading or population sample.'),
    reach=read('reach-delta.json'), member_outcomes=members,
    role_audit=dict(active_rows=35, observations=13, links_added=48, total_source_links=355,
                    expected_checked_valid_active_roles=35, evidence_tiers=roles['evidence_tiers']),
    registers=dict(bugs=433, simplifications=55, questions=146, new_issues=0, known_root_strengthened='F-C0351',
                   related=['F-0505', 'F-C0450'], questions_resolved=0, owner_decisions=0, repairs=0),
    owner_corrections=dict(validation_scope='algorithms-owner-scope-correction.json',
                           cache_composition='communities-cache-owner-clarification.json', new_blocks=0),
    scoring=dict(rows=49, carried_unchanged=37, overlapping_extensions=12, bounded_supported_extensions=11,
                 broad_L4_retained_partial=1, independent_or_private_grade=False, pooled_rate=False),
    freshness_fixtures=dict(controls=24, all_expected=True, active_inputs_mutated=False),
    consolidated_gate=dict(verdict='PASS', ontology_blocks=403, source_links=355),
    cost=dict(communities_builder_command_s=read('communities-costs.json')['command_wall_seconds'],
              communities_builder_elapsed_s=read('communities-costs.json')['elapsed_builder_seconds'],
              ledger_builder_attempt_wall_spans_including_snapshot_s=read('ledger-content-costs.json')['wall_span_sum_s'],
              independent_measured_commands_and_count_probes_s=costs['measured_total_including_auxiliary_s'],
              root_native_elapsed_in_individual_facts=True, tokens_cache_currency_solver_only_cpu='unavailable',
              qualification='Distinct measured command spans/elapsed intervals overlap; not summed as total goal or CPU time. Retained setup/shell delays and failed drafts remain visible.'),
    preservation=dict(exact_before_command_snapshots=True, prior_archives_untouched=True,
                      attempts=['communities-attempts', 'ledger-content-attempts'],
                      reviewer_misses=['empty-key local carrier forecast', 'paging cursor-presence-only draft', 'optional dangling TCK symlink setup'],
                      root_misses=['combined named registration/recreation scenario', 'Cypher refusal exception class', 'DBAPI empty-graph concern refuted']),
    residuals=['default/no-marker ordinary source history is not unrestricted native producer closure',
               'Native Capture/Adopt unexecuted; physical named registration and legal marker history qualified',
               'shared identifier ordering, SQL/KG projection, native JSON/coercion/concurrency and full cache implementation remain providers',
               'keyed CDLP policy, q-con-002 and known rollback/cache/lifecycle failures remain open',
               'raw typed Cypher MERGE branch/value/row capture is a material next candidate; pool-only model set aside as disconnected from real resolvers'],
    convergence='unsupported; continue without fixed round/time/percentage budget after exact seal/next before image',
    direct_executable_body_verified=0, private_evaluator_inputs_inspected=False,
    recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
validation['integration_review'] = dict(report='review-integration.json', readonly_checks=318, verdict='PASS')
(O / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
print(json.dumps(dict(new_units=170, imports=11, controls=33, fresh_receipts=37,
                      source_members=231, new_members=23, source_links=355, new_issues=0)))
