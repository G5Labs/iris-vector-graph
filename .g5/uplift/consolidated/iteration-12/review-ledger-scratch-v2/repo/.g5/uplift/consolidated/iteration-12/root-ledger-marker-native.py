"""Root-only ordinary true/false qualifier neighbor, actual native adoption."""
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
    prefix = 'marker12:' + uuid.uuid4().hex[:8] + ':'
    a, b = prefix + 'a', prefix + 'b'
    cases, revisions = [], []
    before = lg.meta()
    failure = None

    def cs():
        return Changeset(actor='uplift12-marker', actor_type='system')

    def commit(change):
        r = lg.commit(change)
        records = lg.get_revision(r.revision.revision_id).records
        revisions.append(dict(revision=norm(r.revision), ops=change.ops, records=[x.to_wire() for x in records], stmt_ids=r.stmt_ids))
        return r, records

    def check(label, actual, expected):
        actual, expected = norm(actual), norm(expected)
        cases.append(dict(label=label, actual=actual, expected=expected, agrees=actual == expected))
        assert actual == expected, cases[-1]

    def create(p, quals):
        change = cs()
        ref = change.create_relationship(a, p, b, qualifiers=quals)
        result, records = commit(change)
        return result, records, result.stmt_ids[ref.index]

    try:
        lg.enable()
        commit(cs().create_node(a).create_node(b))
        control, _, control_sid = create('MARK_FALSE', {'temporal': 'false', 'q': 'old'})
        head = lg.head().revision_id
        error = None
        try:
            create('MARK_FALSE', {'q': 'new'})
        except Exception as ex:
            error = dict(type=type(ex).__name__, existing='relationship_exists' in str(ex))
        check('false qualifier existing create refuses without revision',
              dict(error=error, unchanged_head=lg.head().revision_id == head),
              dict(error=dict(type='ChangesetOperationError', existing=True), unchanged_head=True))
        first, _, old_sid = create('MARK_TRUE', {'temporal': 'true', 'q': 'old'})
        second, records, new_sid = create('MARK_TRUE', {'q': 'new'})
        check('true qualifier selects adoption and allocates new identity',
              dict(different_id=old_sid != new_sid, records=[(r.op, r.attr, r.prior, r.new) for r in records if r.op != 'create_rel'], creates=sum(r.op == 'create_rel' for r in records), deletes=sum(r.op == 'delete_rel' for r in records)),
              dict(different_id=True, records=[('set_qual', 'q', None, 'new')], creates=1, deletes=0))
        state = lg.reconstruct(second.revision.revision_id)
        relevant = {sid: norm(st) for sid, st in state.statements.items() if st.s == a and st.p == 'MARK_TRUE'}
        check('named replay retains both statement identities', relevant,
              {old_sid: dict(s=a, p='MARK_TRUE', o=b, graph=None, quals={'q': 'old', 'temporal': 'true'}),
               new_sid: dict(s=a, p='MARK_TRUE', o=b, graph=None, quals={'q': 'new'})})
        check('tuple lookup selects the new identity', state.stmt_for_tuple((a, 'MARK_TRUE', b, None)), new_sid)
        cur = c.cursor()
        try:
            cur.execute('SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s=? AND p=? AND o_id=?', [a, 'MARK_TRUE', b])
            physical = [json.loads(tuple(r)[0]) for r in cur.fetchall()]
        finally:
            cur.close()
        check('physical tuple remains one rewritten row', physical, [{'q': 'new'}])
        path = HERE / ('root-ledger-marker-' + prefix.split(':')[1] + '.ndjson')
        lg.export_reconstruction(second.revision.revision_id, str(path))
        entities = [json.loads(line) for line in path.read_text().splitlines()]
        selected = [row for row in entities if row.get('type') == 'rel' and row.get('s') == a and row.get('p') == 'MARK_TRUE']
        check('NDJSON preserves both IDs unlike the one physical tuple', sorted(row['stmt_id'] for row in selected), sorted([old_sid, new_sid]))
    except Exception as ex:
        failure = dict(type=type(ex).__name__, message=str(ex), trace=traceback.format_exc())
    finally:
        lg.disable()
        after = lg.meta()
        c.close()
        sources = ['iris_src/src/Graph/KG/LedgerApply.cls', 'iris_vector_graph/ledger/changeset.py', 'iris_vector_graph/ledger/client.py', 'iris_vector_graph/ledger/replay.py', 'iris_vector_graph/ledger/export.py']
        inputs = [Path(__file__), HERE / 'root-ledger-marker-predictions.md', HERE / 'root-ledger-native.py', REPO / '.g5/Verus_verification/models/temporal_restore/binding.py', REPO / '.g5/uplift/consolidated/iteration-5/native-setup.json']
        result = dict(verdict='AGREES_SOURCE_FORECAST' if failure is None and len(cases) == 6 and all(x['agrees'] for x in cases) else 'DISAGREES_OR_INCOMPLETE',
                      completed_cases=len(cases), cases=cases, revisions=revisions, failure=failure,
                      before_meta=before, after_meta=after, prefix=prefix, elapsed=time.monotonic()-start,
                      source_inputs={rel: hashlib.sha256((h['PIN_DIR'] / rel).read_bytes()).hexdigest() for rel in sources},
                      inputs={str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                      identity_checked=True, container=h['NAME'], new_issue_claims=0,
                      scope='Source-informed ordinary public Changeset true/false qualifier neighbor through actual native commit, SQL record decoder/named replay/tuple lookup/export. No temporal writer, parallel-mode change, malformed input, security scenario, injected provider failure or source patch. Intent/dedup disposition separate; finite ordinary reachability, not native-body/general provider proof. setup5 export/class audit reused.')
        Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['verdict', 'completed_cases', 'elapsed', 'failure']}))


if __name__ == '__main__':
    main()
