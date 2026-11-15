"""Root-only ordinary ledger producers through native records and public readers."""
import dataclasses, hashlib, json, runpy, subprocess, time, traceback, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
h = runpy.run_path(str(REPO / '.g5/Verus_verification/models/temporal_restore/binding.py'))
from iris_vector_graph.ledger.changeset import Changeset


def norm(value):
    if dataclasses.is_dataclass(value):
        return norm(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): norm(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [norm(v) for v in value]
    if isinstance(value, set):
        return sorted(value)
    return value


def main():
    started = time.monotonic()
    sources = ['iris_vector_graph/ledger/client.py', 'iris_vector_graph/ledger/changeset.py',
               'iris_vector_graph/ledger/replay.py', 'iris_vector_graph/ledger/export.py',
               'iris_src/src/Graph/KG/Ledger.cls', 'iris_src/src/Graph/KG/LedgerApply.cls',
               'iris_src/src/Graph/KG/LedgerGenesis.cls']
    identities = {}
    for rel in sources:
        expected = subprocess.check_output(['git', 'rev-parse', '3eaa79cf:' + rel], cwd=REPO, text=True).strip()
        identities[rel] = dict(pin_blob=expected, export_equals=subprocess.check_output(
            ['git', 'hash-object', str(h['PIN_DIR'] / rel)], text=True).strip() == expected,
            current_equals=subprocess.check_output(['git', 'hash-object', str(REPO / rel)], text=True).strip() == expected)
    assert all(v['export_equals'] and v['current_equals'] for v in identities.values())
    c = h['connect']()
    e = h['IRISGraphEngine'](c, embedding_dimension=4)
    lg = e.ledger
    prefix = 'ledger12:' + uuid.uuid4().hex[:8] + ':'
    a, b, simple = [prefix + v for v in ['a', 'b', 'simple']]
    graph = prefix + 'named'
    rows, revisions = [], []
    before = lg.meta()
    failure = None
    enable = None
    after = None

    def case(label, actual, expected):
        actual, expected = norm(actual), norm(expected)
        ok = actual == expected
        rows.append(dict(label=label, actual=actual, expected=expected, prediction_agrees=ok))
        assert ok, (label, actual, expected)

    def cs():
        return Changeset(actor='uplift12-native', actor_type='system')

    def commit(changeset):
        result = lg.commit(changeset)
        records = lg.get_revision(result.revision.revision_id).records
        revisions.append(dict(revision=norm(result.revision), ops=changeset.ops,
                              records=[r.to_wire() for r in records], stmt_ids=result.stmt_ids))
        return result, records

    def project(state):
        return dict(nodes={k: norm(v) for k, v in state.nodes.items() if k.startswith(prefix)},
                    rels={k: norm(v) for k, v in state.statements.items() if v.s.startswith(prefix)})

    def state(revision):
        return project(lg.reconstruct(revision.revision.revision_id))

    def snapshot(node_labels, node_props):
        return dict(labels=sorted(node_labels), props=node_props)

    try:
        enable = norm(lg.enable())
        first = cs().create_node(a, labels=['L'], properties={'k': '1', 'empty': '', 'text': 'null'})
        first.create_node(b).create_node(simple, labels=['Simple'], properties={'x': '0'})
        r1, rec1 = commit(first)
        ar = [r for r in rec1 if r.entity_id == a]
        case('new node separate record expansion', [(r.op, r.attr, r.prior, r.new) for r in ar],
             [('create_node', '', None, ''), ('add_label', 'L', None, ''),
              ('set_prop', 'empty', None, ''), ('set_prop', 'k', None, '1'), ('set_prop', 'text', None, 'null')])
        case('initial complete node content', state(r1)['nodes'][a], snapshot(['L'], {'empty': '', 'k': '1', 'text': 'null'}))

        change = cs().upsert_node(a, labels=['M'], properties={'k': '2'})
        op_ref = change.upsert_relationship(a, 'R', b, qualifiers={'q': 'x', 'weight': '1.25'})
        r2, rec2 = commit(change)
        sid = r2.stmt_ids[op_ref.index]
        expected2 = dict(nodes={a: snapshot(['L', 'M'], {'empty': '', 'k': '2', 'text': 'null'}),
                               b: snapshot([], {}), simple: snapshot(['Simple'], {'x': '0'})},
                         rels={sid: dict(s=a, p='R', o=b, graph=None, quals={'q': 'x', 'weight': '1.25'})})
        case('existing upsert preserves unspecified full content', state(r2), expected2)
        case('existing upsert emits no create node', [r.op for r in rec2 if r.entity_id == a], ['add_label', 'set_prop'])
        relrec = [r for r in rec2 if r.entity_kind == 'rel']
        case('relationship create plus separate qualifier records', [(r.op, r.attr) for r in relrec],
             [('create_rel', ''), ('set_qual', 'q'), ('set_qual', 'weight')])
        case('tuple-only create new', json.loads(relrec[0].new), dict(s=a, p='R', o=b, graph=None))

        noop = cs().set_property(a, 'k', '2').add_label(a, 'M')
        noop.set_qualifier(stmt_id=sid, key='q', value='x')
        _, nrec = commit(noop)
        case('identical writes emit no records', [r.to_wire() for r in nrec], [])
        invalid = None
        try:
            cs().set_property(a, 'k', None)
        except Exception as ex:
            invalid = type(ex).__name__
        case('ordinary null setter refuses before commit', invalid, 'ChangesetOperationError')

        changed = cs().set_property(a, 'k', '3').remove_label(a, 'M')
        changed.set_qualifier(stmt_id=sid, key='q', value='y')
        r3, changed_records = commit(changed)
        case('changed setter actual priors', [(r.op, r.attr, r.prior, r.new) for r in changed_records],
             [('set_prop', 'k', '2', '3'), ('remove_label', 'M', '', None), ('set_qual', 'q', 'x', 'y')])
        restore = cs().set_property(a, 'k', '2').add_label(a, 'M')
        restore.set_qualifier(stmt_id=sid, key='q', value='x')
        r4, _ = commit(restore)
        case('continuous-life restored complete content', state(r4), expected2)
        case('continuous-life restored net diff empty', lg.diff(r2.revision.revision_id, r4.revision.revision_id).to_list(), [])

        deleted_simple, simple_records = commit(cs().delete_node(simple))
        case('simple delete complete snapshot', json.loads(simple_records[0].prior), snapshot(['Simple'], {'x': '0'}))
        later = cs().delete_relationship(stmt_id=sid).set_property(a, 'k', '9').add_label(a, 'R')
        named_ref = later.create_relationship(a, 'NAMED', b, qualifiers={'q': 'named'}, graph=graph)
        r5, _ = commit(later)
        named_sid = r5.stmt_ids[named_ref.index]
        r6, deletion_records = commit(cs().delete_node(a, mode='strict'))
        case('changed-before-delete complete deletion snapshot', json.loads(deletion_records[0].prior),
             snapshot(['L', 'M', 'R'], {'empty': '', 'k': '9', 'text': 'null'}))
        deleted_state = state(r6)
        case('default deletion leaves named relationship', deleted_state['rels'][named_sid],
             dict(s=a, p='NAMED', o=b, graph=graph, quals={'q': 'named'}))
        case('bare endpoint absent while named relationship remains', (a in deleted_state['nodes'], named_sid in deleted_state['rels']), (False, True))
        cur = c.cursor()
        try:
            cur.execute('SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s=? AND p=? AND o_id=? AND graph_id=?', [a, 'NAMED', b, graph])
            edge_count = tuple(cur.fetchone())[0]
        finally:
            cur.close()
        case('native named edge physical row survives', int(edge_count), 1)
        r7, _ = commit(cs().create_node(a, properties={'k': 'fresh'}))
        reverse = lg.diff(r7.revision.revision_id, r2.revision.revision_id).to_list()
        existence = [x for x in reverse if x['entity_id'] == a and x['attr'] == '' and x['after'] is not None]
        case('known rich lifecycle reverse uses deletion-time snapshot', json.loads(existence[0]['after']),
             snapshot(['L', 'M', 'R'], {'empty': '', 'k': '9', 'text': 'null'}))
        case('known reverse snapshot differs from range-start content', json.loads(existence[0]['after']) == expected2['nodes'][a], False)
        case('earlier named cutoff retains complete content', state(r2), expected2)
        streamed = list(lg.reconstruct(r2.revision.revision_id, stream=True))
        stream_projection = dict(nodes={eid: norm(ent) for kind, eid, ent in streamed if kind == 'node' and eid.startswith(prefix)},
                                 rels={eid: norm(ent) for kind, eid, ent in streamed if kind == 'rel' and ent.s.startswith(prefix)})
        case('earlier cutoff eager stream complete content', stream_projection, expected2)
        export_path = HERE / ('root-ledger-native-' + prefix.split(':')[1] + '.ndjson')
        export_summary = norm(lg.export_reconstruction(r2.revision.revision_id, str(export_path)))
        exported = [json.loads(line) for line in export_path.read_text().splitlines()]
        selected = [row for row in exported if str(row.get('id', row.get('s', ''))).startswith(prefix)]
        expected_export = [dict(type='node', id=nid, **ent) for nid, ent in expected2['nodes'].items()]
        expected_export += [dict(type='rel', stmt_id=sid, s=a, p='R', o=b, graph=None, quals={'q': 'x', 'weight': '1.25'})]
        case('earlier cutoff NDJSON full entities', sorted(selected, key=lambda x: json.dumps(x, sort_keys=True)),
             sorted(expected_export, key=lambda x: json.dumps(x, sort_keys=True)))
    except Exception as ex:
        failure = dict(type=type(ex).__name__, message=str(ex), trace=traceback.format_exc())
    finally:
        try:
            lg.disable()
            after = lg.meta()
        finally:
            c.close()
        result = dict(verdict='AGREES' if failure is None and rows and all(x['prediction_agrees'] for x in rows) else 'DISAGREES_OR_INCOMPLETE',
                      completed_cases=len(rows), cases=rows, failure=failure, prefix=prefix, named_graph=graph,
                      before_meta=before, enable=enable, after_meta=after, revisions=revisions,
                      export_summary=locals().get('export_summary'), reverse_diff=locals().get('reverse'),
                      container=h['NAME'], identity_checked=True, source_identities=identities,
                      source_inputs={rel: hashlib.sha256((h['PIN_DIR'] / rel).read_bytes()).hexdigest() for rel in sources},
                      inputs={str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), HERE / 'root-ledger-predictions.md', REPO / '.g5/Verus_verification/models/temporal_restore/binding.py', REPO / '.g5/uplift/consolidated/iteration-5/native-setup.json']},
                      elapsed=time.monotonic() - started,
                      genesis_native_executed=False, new_issue_claims=0,
                      scope='Ordinary finite Changeset/ApplyAll native writers through actual SQL record decoder, named full-content reconstruction/diff/stream/export on a fresh prefix. Earlier task-owned state retained. Enable resumes/adopts disabled history; no reset or Genesis execution. Known bug-led-101 strengthened, q-con-002 unanswered. Native class correspondence reuses setup5 deployment/export audit; no native-body, arbitrary SQL/JSON/string coercion, atomicity or repository-wide proof.')
        Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({k: result[k] for k in ['verdict', 'completed_cases', 'elapsed', 'failure']}))
    assert result['verdict'] == 'AGREES'


if __name__ == '__main__':
    main()
