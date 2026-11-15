"""Exposed post-refutation native neighbors; the original failed forecast stays intact."""
import hashlib, json, runpy, time, traceback, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
base = runpy.run_path(str(HERE / 'root-ledger-native.py'))
h, Changeset, norm = base['h'], base['Changeset'], base['norm']


def main():
    start = time.monotonic()
    c = h['connect']()
    e = h['IRISGraphEngine'](c, embedding_dimension=4)
    lg = e.ledger
    prefix = 'qualfollow12:' + uuid.uuid4().hex[:8] + ':'
    a, b, invalid = [prefix + x for x in ['a', 'b', 'invalid']]
    cases, revisions = [], []
    before = lg.meta()
    failure = None

    def cs():
        return Changeset(actor='uplift12-qualfollow', actor_type='system')

    def commit(change):
        r = lg.commit(change)
        records = lg.get_revision(r.revision.revision_id).records
        revisions.append(dict(revision=norm(r.revision), ops=change.ops, records=[x.to_wire() for x in records], stmt_ids=r.stmt_ids))
        return r, records

    def check(label, actual, expected):
        actual, expected = norm(actual), norm(expected)
        cases.append(dict(label=label, actual=actual, expected=expected, prediction_agrees=actual == expected, post_refutation=True))
        assert actual == expected, cases[-1]

    def physical():
        cur = c.cursor()
        try:
            cur.execute('SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s=? AND p=? AND o_id=?', [a, 'QUALKEY', b])
            row = cur.fetchone()
            return json.loads(tuple(row)[0]) if row is not None else None
        finally:
            cur.close()

    try:
        lg.enable()
        commit(cs().create_node(a).create_node(b))
        head = lg.head().revision_id
        bad = cs()
        bad.create_relationship(a, 'QUALKEY', b, qualifiers={'': 'ignored', 'q': 'x'})
        error = None
        try:
            commit(bad)
        except Exception as ex:
            error = dict(type=type(ex).__name__, subscript='<SUBSCRIPT>' in str(ex), stage='QualsJson' in str(ex))
        check('new empty-key batch refuses before relationship/revision',
              dict(error=error, unchanged_head=lg.head().revision_id == head, physical=physical()),
              dict(error=dict(type='LedgerInconsistencyError', subscript=True, stage=True), unchanged_head=True, physical=None))
        valid = cs()
        ref = valid.create_relationship(a, 'QUALKEY', b, qualifiers={'q': 'x'})
        r1, records = commit(valid)
        sid = r1.stmt_ids[ref.index]
        check('valid nonempty new batch neighbor',
              dict(physical=physical(), replay=lg.reconstruct(r1.revision.revision_id).statements[sid].quals,
                   records=[(x.op, x.attr, x.prior, x.new) for x in records if x.op != 'create_rel']),
              dict(physical={'q': 'x'}, replay={'q': 'x'}, records=[('set_qual', 'q', None, 'x')]))
        head = lg.head().revision_id
        bad = cs()
        bad.upsert_relationship(a, 'QUALKEY', b, qualifiers={'': 'ignored-again', 'q': 'y'})
        error = None
        try:
            commit(bad)
        except Exception as ex:
            error = dict(type=type(ex).__name__, subscript='<SUBSCRIPT>' in str(ex), stage='MergeQuals' in str(ex))
        check('existing empty-key batch refuses without changing old qualifier',
              dict(error=error, unchanged_head=lg.head().revision_id == head, physical=physical()),
              dict(error=dict(type='LedgerInconsistencyError', subscript=True, stage=True), unchanged_head=True, physical={'q': 'x'}))
        valid = cs()
        valid.upsert_relationship(a, 'QUALKEY', b, qualifiers={'q': 'y'})
        r2, records = commit(valid)
        check('valid nonempty existing upsert neighbor',
              dict(physical=physical(), replay=lg.reconstruct(r2.revision.revision_id).statements[sid].quals,
                   records=[(x.op, x.attr, x.prior, x.new) for x in records]),
              dict(physical={'q': 'y'}, replay={'q': 'y'}, records=[('set_qual', 'q', 'x', 'y')]))
        head = lg.head().revision_id
        error = None
        try:
            cs().set_qualifier(stmt_id=sid, key='', value='x')
        except Exception as ex:
            error = type(ex).__name__
        check('direct empty qualifier retains Python refusal', (error, lg.head().revision_id == head), ('ValueError', True))
        error = None
        try:
            commit(cs().create_node(invalid, properties={'': 'x', 'k': 'y'}))
        except Exception as ex:
            error = dict(type=type(ex).__name__, empty_property='property key is required' in str(ex))
        check('node empty-property batch rolls back earlier create',
              dict(error=error, unchanged_head=lg.head().revision_id == head, absent_node=e.get_node(invalid) is None),
              dict(error=dict(type='ChangesetOperationError', empty_property=True), unchanged_head=True, absent_node=True))
    except Exception as ex:
        failure = dict(type=type(ex).__name__, message=str(ex), trace=traceback.format_exc())
    finally:
        lg.disable()
        after = lg.meta()
        c.close()
        inputs = [Path(__file__), HERE / 'root-ledger-qualkeys-followup-predictions.md', HERE / 'root-ledger-native.py',
                  HERE / 'root-ledger-qualkeys-native.json', REPO / '.g5/Verus_verification/models/temporal_restore/binding.py',
                  REPO / '.g5/uplift/consolidated/iteration-5/native-setup.json']
        sources = ['iris_src/src/Graph/KG/LedgerApply.cls', 'iris_vector_graph/ledger/changeset.py', 'iris_vector_graph/ledger/replay.py', 'iris_vector_graph/ledger/client.py']
        result = dict(verdict='AGREES' if failure is None and len(cases) == 6 and all(x['prediction_agrees'] for x in cases) else 'DISAGREES_OR_INCOMPLETE',
                      completed_cases=len(cases), cases=cases, revisions=revisions, failure=failure, prefix=prefix,
                      before_meta=before, after_meta=after, elapsed=time.monotonic()-start,
                      inputs={str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                      source_inputs={rel: hashlib.sha256((h['PIN_DIR'] / rel).read_bytes()).hexdigest() for rel in sources},
                      identity_checked=True, container=h['NAME'], new_issue_claims=0, post_refutation=True,
                      scope='Six post-refutation source-informed finite native neighbors, not blind predictions. Original skip-empty forecast and0-comparison failed native attempt preserved. Actual empty-key local-map failures for new/existing qualifiers contrast valid records/physical JSON/replay, Python direct refusal and own node-prefix rollback. No new issue/owner decision/product fix/native body or universal provider proof.')
        Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['verdict', 'completed_cases', 'elapsed', 'failure']}))
    assert result['verdict'] == 'AGREES'


if __name__ == '__main__':
    main()
