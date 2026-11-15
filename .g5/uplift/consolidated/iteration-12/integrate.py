"""Integrate frozen, independently accepted iteration12 fragments; root only."""
import csv, hashlib, json, re
from pathlib import Path

R = Path.cwd()
V = R / '.g5/Verus_verification'
O = R / '.g5/uplift/consolidated/iteration-12'
C = '.g5/Verus_verification/models/communities/communities.rs'
L = '.g5/Verus_verification/models/ledger_content/ledger_content.rs'
A = '.g5/Verus_verification/models/ledger_content/alternate.rs'
census = json.loads((O / 'before-reach/census.json').read_text())
before = json.loads((O / 'before-reach/bindings.json').read_text())


def metadata(path, block, text, replace=None):
    p = R / path
    s = p.read_text()
    m = re.search(r'^### ' + re.escape(block) + r'\n.*?(?=^### |\Z)', s, re.M | re.S)
    assert m, block
    b = m.group(0)
    if replace:
        assert replace in b, (block, replace)
        b = b.replace(replace, text)
    else:
        lines = b.splitlines()
        i = next((i for i, x in enumerate(lines) if x.startswith('- Expands:') or x == '- agent'), 2)
        lines.insert(i, text)
        b = '\n'.join(lines) + '\n\n'
    p.write_text(s[:m.start()] + b + s[m.end():])


def resolve(path, name):
    if path.endswith('.cls'):
        name = name.rsplit('.', 1)[-1]
    keys = [k for k, v in census.items() if v['path'] == path and (v['symbol'] == name or v['symbol'].endswith('.' + name))]
    assert len(keys) == 1, (path, name, keys)
    k = keys[0]
    assert len(census[k]['lines']) == 1, k
    return k, census[k]['symbol'], census[k]['lines'][0]


rows = []


def role(family, block, label, path, name, formal_path, fn, active, scope, tier):
    k, symbol, line = resolve(path, name)
    assert len(re.findall(r'\bfn\s+' + re.escape(fn) + r'\b', (R / formal_path).read_text())) == 1, (formal_path, fn)
    rows.append(dict(block=block, role=label, path=path, symbol=symbol, line=line, family=family,
                     formal_item=formal_path + '::' + fn, relation='models' if active else 'observes',
                     scope=scope, evidence_tier=tier, before_bound=k in before, whole_member_claim=False,
                     direct_executable_body_verified=False, checked=True))


# Each selected source member has one principal bounded role. All adjacent laws
# and wider source qualifications remain linked in the frozen package NOTES.
cm = {
    'WCCJson': ('algorithms.op.wcc', 'raw synchronous WCC and confirmation', 'theorem_actual_wcc_terminates_with_confirmation'),
    'CDLPJson': ('algorithms.op.cdlp', 'raw synchronous vote decision', 'theorem_cdlp_most_votes_then_least_label'),
    'Scan': ('algorithms.cache.token', 'raw census and cursor producer', 'theorem_native_pages_derive_full_result_or_fail'),
    'HasOther': ('algorithms.cache.token', 'raw nonself incidence', 'theorem_raw_sql_incidence_agree'),
    'loners': ('algorithms.cache.token', 'cursor-value accumulation and failure', 'theorem_native_pages_derive_full_result_or_fail'),
    'loners_sql': ('algorithms.cache.token', 'raw SQL census projection', 'theorem_native_sql_live_loners_require_projection'),
    'complete_labels': ('algorithms.cache.token', 'preserve core and add missing labels', 'theorem_complete_preserves_core_and_adds_only_absent'),
    '_loners': ('algorithms.cache.token', 'whole-census failover and empty distinction', 'theorem_census_success_empty_and_failure_are_distinct'),
    'kg_WCC': ('algorithms.op.wcc', 'public WCC core/live composition', 'theorem_warm_wcc_core_plus_live_census_is_complete'),
    'kg_CDLP': ('algorithms.op.cdlp', 'public CDLP core/live composition', 'theorem_warm_cdlp_plus_live_census_is_complete'),
    '_cached_algorithm': ('algorithms.cache', 'selected-key token and payload history', 'theorem_same_raw_core_reuses_derived_computation'),
}
for item in json.loads((O / 'communities-source-roles.json').read_text())['roles']:
    active = item['role'] == 'bounded-active'
    block, label, fn = cm.get(item['name'], ('algorithms.cache.token', item['name'] + ' qualified context', 'theorem_census_success_empty_and_failure_are_distinct'))
    role('C-communities', block, label, item['path'], item['name'], C, fn, active,
         item['claim'] + ' ' + item['qualifier'], 'finite-native-correspondence' if active else 'observation-only')

lm = {
    'ApplyAll': ('ledger.commit', 'closed default producer history', 'theorem_closed_ordinary_source_domain'),
    'OpCreateNode': ('ledger.commit', 'new/upsert full node record producer', 'theorem_new_node_emits_separate_content'),
    'AddLabel': ('ledger.commit', 'label/noop record producer', 'theorem_same_value_and_label_are_noop'),
    'SetProp': ('ledger.commit', 'full property/current-prior producer', 'theorem_current_prior_is_derived'),
    'OpRemoveLabel': ('ledger.commit', 'label removal/full-content effect', 'theorem_primitive_records_replay_full_content'),
    'OpRemoveProp': ('ledger.commit', 'property removal/full-content effect', 'theorem_primitive_records_replay_full_content'),
    'NodeSnapshotJson': ('ledger.readers.diff', 'complete successful snapshot projection', 'theorem_simple_snapshot_is_complete'),
    'OpDeleteNode': ('ledger.commit', 'default deletion/context producer', 'theorem_closed_ordinary_source_domain'),
    'OpCreateRel': ('ledger.commit', 'fresh tuple/qualifier producer', 'theorem_raw_new_rel_uses_own_fresh_counter'),
    'MergeQuals': ('ledger.commit', 'qualifier upsert/current-prior producer', 'theorem_raw_request_full_content'),
    'OpQual': ('ledger.commit', 'qualifier attribute producer', 'theorem_attribute_producer_step'),
    'DeleteRelInternal': ('ledger.commit', 'relationship snapshot/delete projection', 'theorem_primitive_records_replay_full_content'),
    'Capture': ('ledger.lifecycle.genesis', 'typed scan-row content projection', 'theorem_genesis_full_content_from_raw_rows'),
    'Adopt': ('ledger.lifecycle', 'typed adoption identity/content projection', 'theorem_adoption_identity_is_derived'),
    'MutationRecord.from_row': ('ledger.readers', 'typed nullable record fields', 'theorem_null_text_and_public_value_boundaries'),
    'GraphState.apply': ('ledger.readers', 'complete typed field fold', 'apply'),
    'GraphState.as_comparable': ('ledger.readers', 'tuple projection versus statement identities', 'theorem_duplicate_tuple_views_remain_distinct'),
    'compute_diff': ('ledger.readers.diff', 'named continuous full-field endpoints', 'theorem_named_generated_full_content_endpoints'),
    'reconstruct': ('ledger.readers.bound', 'full-content/count bound projection', 'theorem_named_bound_result_projects'),
    'GraphLedger.reconstruct': ('ledger.readers.bound', 'named full-content wrapper', 'theorem_later_records_cannot_change_full_content'),
    'GraphLedger.diff': ('ledger.readers.diff', 'named continuous-field range wrapper', 'theorem_named_generated_full_content_endpoints'),
    'GraphLedger.export_reconstruction': ('ledger.readers', 'named unbounded entity export wrapper', 'theorem_full_stream_and_export_fold'),
    'export_ndjson': ('ledger.readers', 'complete typed entity/field export', 'theorem_export_preserves_complete_fields'),
    '_str_value': ('ledger.changeset', 'typed scalar/null input boundary', 'theorem_null_text_and_public_value_boundaries'),
}
for item in json.loads((O / 'ledger-content-roles.json').read_text())['roles']:
    name = item['member'].rsplit('.', 1)[-1] if item['file'].endswith('.cls') else item['member']
    block, label, fn = lm[name]
    fp = A if name in ('Capture', 'Adopt') else L
    tier = ('inspected-executed-transcription' if name in ('Capture', 'Adopt', 'OpRemoveProp')
            else 'actual-python-unit' if name in ('GraphState.as_comparable', '_str_value')
            else 'finite-native-correspondence')
    scope = item['scope']
    if name == 'OpQual':
        scope += ' Native observations cover set/noop only; remove/replace remain typed transcription/unit correspondence. Native cross-key replacement/removal ordering and exact ordinals are not proved by Set.to_seq; only typed field/state effects are claimed.'
    role('C-ledger_content', block, label, item['file'], item['member'], fp, fn, True, scope, tier)

for path, name, label, fn in [
    ('iris_vector_graph/ledger/client.py', 'GraphLedger.commit', 'empty-hooks/post-properties wrapper context', 'theorem_committed_revision_full_content'),
    ('iris_src/src/Graph/KG/LedgerApply.cls', 'NodeExists', 'all-graph physical admission boundary', 'theorem_named_registration_refuses_create_after_default_delete'),
    ('iris_src/src/Graph/KG/LedgerApply.cls', 'EnsureEndpoint', 'named physical registration context', 'theorem_named_registration_refuses_create_after_default_delete'),
    ('iris_vector_graph/ledger/replay.py', '_parse_tuple', 'raw decoder/tuple grammar boundary', 'theorem_raw_graph_tuple_normalization'),
]:
    role('C-ledger_content', 'ledger.commit' if path.endswith('.cls') or name == 'GraphLedger.commit' else 'ledger.readers', label,
         path, name, L, fn, False, 'Qualified necessary context only; wider protocol/physical effects or raw grammar not established by this typed fragment.', 'observation-only')

# Preserve prior rows byte-for-byte; append only reviewed new declarations.
p = V / 'crosswalk/decision-links.tsv'
old = list(csv.reader(p.open(), delimiter='\t'))
assert not any(x[5] in ('C-communities', 'C-ledger_content') for x in old[1:])
with p.open('a', newline='') as f:
    writer = csv.writer(f, delimiter='\t', lineterminator='\n')
    for r in rows:
        grade = {'finite-native-correspondence': 'Observed (finite native/actual Python); bounded fragment',
                 'actual-python-unit': 'Observed (actual Python unit); bounded fragment',
                 'inspected-executed-transcription': 'Inspected (checked math/typed transcription); native body unexecuted',
                 'observation-only': 'Observed/inspected (qualified context)'}[r['evidence_tier']]
        writer.writerow([r['block'], r['role'], r['path'], r['symbol'], str(r['line']), r['family'], r['formal_item'], r['relation'], 'as-built declared typed fragment' if r['relation'] == 'models' else 'qualified wider context', grade])

p = V / 'families.tsv'
with p.open('a', newline='') as f:
    writer = csv.writer(f, delimiter='\t', lineterminator='\n')
    writer.writerow(['C-communities', 'C', '.g5/Verus_verification/models/communities', 'verus', 'as-built typed raw workflow',
                     'raw default WCC/CDLP dynamics, live raw census/cursor and selected cached-core composition', 'active',
                     '73 units =65 ordinary proof queries+8 recursive checks; one checked termination hint not separately counted;0 imports/NLA',
                     '12 full/named ordinary controls;1255 binding comparisons+9 histories/6 effects/14 sensitivities;19 upstream;18 old native reused+8 new census facts',
                     '.g5/Verus_verification/models/communities/NOTES.md'])
    writer.writerow(['C-ledger_content', 'C', '.g5/Verus_verification/models/ledger_content', 'verus', 'as-built typed full content; bounded source profile',
                     'full typed field fold, closed default/no-marker producer history, named bounds/endpoints/export and typed alternate projections', 'active',
                     '108 units =97 new(84 proof queries+13 recursive)+11 unchanged reconstruction imports;0 NLA',
                     '21 full/named ordinary controls;82 histories/4023 comparisons+6 raw/7 alternate/8 sensitivities;155 upstream;34 finite native ledger facts;Capture/Adopt unexecuted',
                     '.g5/Verus_verification/models/ledger_content/NOTES.md'])

alg = '.g5/ontology/features/algorithms.g5.md'
metadata(alg, 'algorithms.op.wcc', '- Verus: [communities](../../Verus_verification/models/communities/NOTES.md) derives raw coordinate membership, synchronous minima, reachable-radius propagation and actual first-stop termination within N rounds including confirmation. Explicit insufficient budgets refuse even after labels happen to be final; empty succeeds before the guard. Weak-component interpretation requires mirrored, closed projected edges and an admitted order relation; native bodies, arbitrary identifiers/serialization, provider truth and concurrency remain unproved.')
metadata(alg, 'algorithms.op.cdlp', '- Verus: [communities](../../Verus_verification/models/communities/NOTES.md) derives raw coordinate frequencies, self-loop exclusion, greatest-vote/least-label decisions, old-map synchrony, finite budget and arbitrary-round two-node parity. It does not promise convergence or resolve physical keyed-edge vote policy; repeated physical keys collapse in the source coordinate projection. Typed integer and shared admitted ordering/provider conditions remain explicit.')
metadata(alg, 'algorithms.cache', '- Verus (new bounded composition): [communities](../../Verus_verification/models/communities/NOTES.md) derives immutable core payloads from raw origins and composes selected-key/token reuse with a fresh raw live census. It proves same-core isolate visibility and retains stale same-token/different-origin counterexamples. Front/shared implementation, hashing, capacity/large results, disabled/failing cache paths, concurrent publication and actual token-writer correctness are wider than this relation; prior reviewed-design and rollback findings remain.')
metadata(alg, 'algorithms.cache.token', '- Verus (WCC/CDLP extension): [communities](../../Verus_verification/models/communities/NOTES.md) derives SQL-node/edge versus KG incidence, value-consuming page cursors with final empty confirmation, whole-result failure discard and SQL fallback. Raw stable SQL/KG projection and a common order-preserving admitted identifier carrier are required. New census8 and reused native18 corroborate finite ordinary cases; no all-driver/collation or rollback repair is implied.')

led = '.g5/ontology/features/ledger.g5.md'
metadata(led, 'ledger.commit', '- Verus: [ledger_content](../../Verus_verification/models/ledger_content/NOTES.md) independently derives complete maps and separate records, current priors/noops/snapshots, deletion context and fresh coherent identities across whole histories. Native source correspondence is an inductive default/canonical/no-marker profile from empty with complete successful providers and no competing/reifier/post-commit writes. Legal marker/named histories remain explicit partial boundaries; this is not a native transaction/body or whole-wrapper proof.')
metadata(led, 'ledger.changeset', '- Verus (scalar slice): [ledger_content](../../Verus_verification/models/ledger_content/NOTES.md) distinguishes text/boolean values from null/container refusal and typed nullable record fields. Arbitrary numeric stringification, Python carriers, raw wire grammar and all constructor/protocol branches remain external; values are opaque stored strings, not recursively typed JSON.')
metadata(led, 'ledger.readers', '- Verus: [ledger_content](../../Verus_verification/models/ledger_content/NOTES.md) adds complete typed label/property/tuple/qualifier folds, source-derived ordinary records and full entity/export projections. Statement-ID maps and exports retain duplicate tuples while tuple lookup/comparable may collapse them. Native producer breadth, raw codecs, graph-scoped node fidelity, temporal/unknown operation diff and unrestricted lifecycle reconstruction remain qualified.')
metadata(led, 'ledger.readers.bound', '- Verus (full-content extension): [ledger_content](../../Verus_verification/models/ledger_content/NOTES.md) proves an explicit projection from complete typed states to the retained reconstruction entity/count model, composing named cutoff and intermediate bound. Later records cannot change earlier full contents/refusal; stream and export fold eagerly without that bound. This is not a byte/memory bound, generic iterable/SQL snapshot or raw tuple decoder proof.')
metadata(led, 'ledger.readers.diff', '- Verus (continuous full fields): [ledger_content](../../Verus_verification/models/ledger_content/NOTES.md) derives raw-base named endpoint maps and stamped label/property/qualifier records, proving exactly changed field pairs and omission of restored values. The rich deletion-time snapshot witness strengthens known bug-led-101; q-con-002, unrestricted lifecycle semantics and executable inverse scripts remain unresolved.')
metadata(led, 'ledger.lifecycle.genesis', '- Verus (inspected typed projection): [ledger_content alternate](../../Verus_verification/models/ledger_content/NOTES.md) derives Capture records/content from already-projected ordered scan rows, including distinct IDs per physical edge and bare-node graph loss. Source and typed ports are checked, but the native producer, SQL scan completeness/order and arbitrary coercion are unexecuted/unproved; no one-tuple/one-statement invariant is inferred.')
metadata(led, 'ledger.lifecycle', '- Verus (inspected typed adoption slice): [ledger_content alternate](../../Verus_verification/models/ledger_content/NOTES.md) derives adopted identity reuse/allocation and typed contents while retaining permissive payload and duplicate-view boundaries. Raw envelope/parser/tuple-JSON reference handling, canonical SQL changes and truth of supplied priors are not proved. Actual downstream Python readers execute the typed records; bounded native Adopt producer assertions were not run.')

# Update obsolete blanket gap descriptions while retaining the older successes.
p = R / led
s = p.read_text().replace('complete lifecycle/content reconstruction remains open.', 'unrestricted lifecycle/native correspondence remains open; the new full typed-content extension is described below.')
s = s.replace('Labels, complete property/qualifier maps, tuple decoding and diff are not proved.', 'That retained model does not prove complete maps, tuple decoding or diff; the new typed full-content extension below supplies the scoped map layer.')
s = s.replace('No full graph diff/refinement proof.', 'No unrestricted lifecycle/native full-graph refinement proof; the continuous full-field extension below is separate.')
p.write_text(s)

active = [r for r in rows if r['relation'] == 'models']
new = sorted({r['path'] + '::' + r['symbol'] for r in active} - set(before))
report = dict(rows=rows, active_rows=len(active), observations=len(rows)-len(active), new_rows=len(rows),
              expected_bounded_active_roles=len(active), checked_active_roles=len(active), valid_active_roles=len(active),
              newly_bound=new, new_unique_members=len(new), already_bound_strengthened=len(active)-len(new),
              evidence_tiers={tier: sum(r['evidence_tier'] == tier for r in active) for tier in sorted({r['evidence_tier'] for r in active})},
              direct_executable_body_verified=0, scope='All rows are bounded source roles, not whole bodies. Inspected typed native transcriptions are separated from actual Python and finite native observations. Existing208 members are not exhaustively recategorized; raw denominator unchanged.')
(O / 'role-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k not in ('rows', 'newly_bound')}))
