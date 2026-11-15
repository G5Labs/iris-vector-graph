"""Root serial corroboration of independent batch-enumeration challenge."""
import hashlib, json, runpy, time, traceback, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
base = runpy.run_path(str(HERE / 'root-ledger-native.py'))
h, Changeset, norm = base['h'], base['Changeset'], base['norm']


def main():
    started = time.monotonic()
    c = h['connect']()
    e = h['IRISGraphEngine'](c, embedding_dimension=4)
    lg = e.ledger
    prefix = 'qualkeys12:' + uuid.uuid4().hex[:8] + ':'
    a, b, invalid = [prefix + x for x in ['a', 'b', 'invalid']]
    cases, revisions = [], []
    failure = None
    before = lg.meta()

    def cs():
        return Changeset(actor='uplift12-qualkeys', actor_type='system')

    def commit(change):
        r = lg.commit(change)
        records = lg.get_revision(r.revision.revision_id).records
        revisions.append(dict(revision=norm(r.revision), ops=change.ops, records=[x.to_wire() for x in records], stmt_ids=r.stmt_ids))
        return r, records

    def check(label, actual, expected):
        actual, expected = norm(actual), norm(expected)
        cases.append(dict(label=label, actual=actual, expected=expected, prediction_agrees=actual == expected))
        assert actual == expected, cases[-1]

    def physical_quals():
        cur = c.cursor()
        try:
            cur.execute('SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s=? AND p=? AND o_id=?', [a, 'QUALKEY', b])
            return json.loads(tuple(cur.fetchone())[0])
        finally:
            cur.close()

    try:
        lg.enable()
        commit(cs().create_node(a).create_node(b))
        change = cs()
        ref = change.create_relationship(a, 'QUALKEY', b, qualifiers={'': 'ignored', 'q': 'x'})
        r1, records = commit(change)
        sid = r1.stmt_ids[ref.index]
        check('new batch qualifier skips empty key',
              dict(physical=physical_quals(), replay=lg.reconstruct(r1.revision.revision_id).statements[sid].quals,
                   records=[(x.op, x.attr, x.prior, x.new) for x in records if x.op != 'create_rel']),
              dict(physical={'q': 'x'}, replay={'q': 'x'}, records=[('set_qual', 'q', None, 'x')]))
        change = cs()
        change.upsert_relationship(a, 'QUALKEY', b, qualifiers={'': 'ignored-again', 'q': 'y'})
        r2, records = commit(change)
        check('existing upsert batch qualifier skips empty key',
              dict(physical=physical_quals(), replay=lg.reconstruct(r2.revision.revision_id).statements[sid].quals,
                   records=[(x.op, x.attr, x.prior, x.new) for x in records]),
              dict(physical={'q': 'y'}, replay={'q': 'y'}, records=[('set_qual', 'q', 'x', 'y')]))
        head = lg.head().revision_id
        error = None
        try:
            cs().set_qualifier(stmt_id=sid, key='', value='x')
        except Exception as ex:
            error = type(ex).__name__
        check('direct empty qualifier refuses without revision', (error, lg.head().revision_id == head), ('ValueError', True))
        error = None
        try:
            commit(cs().create_node(invalid, properties={'': 'x', 'k': 'y'}))
        except Exception as ex:
            error = dict(type=type(ex).__name__, empty_property='property key is required' in str(ex))
        check('node batch empty property refuses and rolls back create',
              dict(error=error, unchanged_head=lg.head().revision_id == head, absent_node=e.get_node(invalid) is None),
              dict(error=dict(type='ChangesetOperationError', empty_property=True), unchanged_head=True, absent_node=True))
    except Exception as ex:
        failure = dict(type=type(ex).__name__, message=str(ex), trace=traceback.format_exc())
    finally:
        lg.disable()
        after = lg.meta()
        c.close()
        inputs = [Path(__file__), HERE / 'root-ledger-qualkeys-predictions.md', HERE / 'root-ledger-native.py',
                  REPO / '.g5/Verus_verification/models/temporal_restore/binding.py', REPO / '.g5/uplift/consolidated/iteration-5/native-setup.json']
        source_files = ['iris_src/src/Graph/KG/LedgerApply.cls', 'iris_vector_graph/ledger/changeset.py', 'iris_vector_graph/ledger/replay.py', 'iris_vector_graph/ledger/client.py']
        result = dict(verdict='AGREES' if failure is None and len(cases) == 4 and all(x['prediction_agrees'] for x in cases) else 'DISAGREES_OR_INCOMPLETE',
                      completed_cases=len(cases), cases=cases, revisions=revisions, failure=failure, prefix=prefix,
                      before_meta=before, after_meta=after, elapsed=time.monotonic()-started,
                      inputs={str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                      source_inputs={rel: hashlib.sha256((h['PIN_DIR'] / rel).read_bytes()).hexdigest() for rel in source_files},
                      identity_checked=True, container=h['NAME'], new_issue_claims=0,
                      scope='Post-review source-informed batch-key challenge on actual ordinary native Changesets, SQL qualifier JSON, emitted records and named replay. New/existing batch qualifier enumeration differs from direct setter and node property batch. Finite owned-prefix evidence, existing task data retained, no source patch/native-body or universal coercion/SQL/atomicity proof; exact scripted node failure checks its own rollback only.')
        Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['verdict', 'completed_cases', 'elapsed', 'failure']}))
    assert result['verdict'] == 'AGREES'


if __name__ == '__main__':
    main()
