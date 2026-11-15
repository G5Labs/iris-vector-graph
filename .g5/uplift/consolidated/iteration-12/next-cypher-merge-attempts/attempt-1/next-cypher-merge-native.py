"""Next-draw preparation: actual SQL-path MERGE effects and independent readers."""
import hashlib, json, runpy, subprocess, time, traceback, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
h = runpy.run_path(str(REPO / '.g5/Verus_verification/models/temporal_restore/binding.py'))


def typed(rows):
    return [[[v, type(v).__name__] for v in row] for row in rows]


def main():
    start = time.monotonic()
    c = h['connect']()
    e = h['IRISGraphEngine'](c, embedding_dimension=4, native_cypher=False)
    assert e.ledger.meta()['state'] == 'disabled'
    prefix = 'merge12:' + uuid.uuid4().hex[:8] + ':'
    label = 'Merge12' + uuid.uuid4().hex[:8]
    rows, queries = [], []
    failure = None
    source_files = ['iris_vector_graph/cypher/parser.py', 'iris_vector_graph/cypher/translator.py',
                    'iris_vector_graph/_engine/query.py', 'iris_vector_graph/_engine/nodes_edges.py',
                    'iris_vector_graph/stores/iris_sql_store.py', 'iris_vector_graph/prop_values.py']
    identities = {}
    for rel in source_files:
        blob = subprocess.check_output(['git', 'rev-parse', '3eaa79cf:' + rel], cwd=REPO, text=True).strip()
        identities[rel] = dict(pin_blob=blob, export_equals=subprocess.check_output(['git', 'hash-object', str(h['PIN_DIR'] / rel)], text=True).strip() == blob,
                               current_equals=subprocess.check_output(['git', 'hash-object', str(REPO / rel)], text=True).strip() == blob)
    assert all(x['export_equals'] and x['current_equals'] for x in identities.values())

    def q(text, params=None):
        item = dict(query=text, parameters=params)
        queries.append(item)
        try:
            result = e.execute_cypher(text, params, raise_on_error=True)
            item.update(columns=result.columns, rows=[list(r) for r in result.rows], error=result.error,
                        metadata=getattr(result, 'metadata', None))
            assert not result.error, result.error
            return [list(r) for r in result.rows]
        except Exception as ex:
            item['raised'] = dict(type=type(ex).__name__, message=str(ex))
            raise

    def case(name, actual, expected):
        ok = actual == expected
        rows.append(dict(label=name, actual=actual, expected=expected, prediction_agrees=ok))
        assert ok, (name, actual, expected)

    def read(nid, expr):
        return typed(q(f'MATCH (n:{label} {{id: $id}}) RETURN ' + expr, {'id': nid}))

    def prop(nid, keys):
        node = e.get_node(nid)
        assert node is not None
        return typed([[node.get(k) for k in keys]])

    try:
        a, b, src, target, new = [prefix + x for x in ['a', 'b', 'src', 'target', 'new']]
        got = q(f'MERGE (n:{label} {{id: $id}}) ON CREATE SET n.c = 1 + 1, n.f = 1.5 + 1, n.s = \'a\' + \'b\', n.b = 1 < 2 ON MATCH SET n.m = 6 RETURN n.c, n.f, n.s, n.b, n.m', {'id': a})
        values = [[[2, 'int'], [2.5, 'float'], ['ab', 'str'], [True, 'bool'], [None, 'NoneType']]]
        case('new branch typed computed RETURN', typed(got), values)
        case('new branch fresh MATCH reader', read(a, 'n.c, n.f, n.s, n.b, n.m'), values)
        case('new branch independent get_node reader', prop(a, ['c', 'f', 's', 'b', 'm']), values)
        q(f'MERGE (n:{label} {{id: $id}}) ON CREATE SET n.c = 99 ON MATCH SET n.m = 2 * 3', {'id': a})
        case('existing branch keeps create and applies match', read(a, 'n.c, n.m'), [[[2, 'int'], [6, 'int']]])
        q(f'MERGE (n:{label} {{id: $id}}) ON MATCH SET n.m = 6', {'id': new})
        case('match action absent on new identity', read(new, 'n.m'), [[[None, 'NoneType']]])
        q(f'MERGE (n:{label} {{id: $id}}) ON MATCH SET n.c = n.c + 1', {'id': a})
        case('own node computed property read', read(a, 'n.c, n.c > 2'), [[[3, 'int'], [True, 'bool']]])
        q(f'CREATE (n:{label} {{id: $id, c: 500, extra: 7}})', {'id': a})
        case('CREATE existing keeps old value and adds absent property', prop(a, ['c', 'extra']), [[[3, 'int'], [7, 'int']]])

        q(f'CREATE (n:{label} {{id: $id, count: 4, f: 1.5, name: \'src\'}})', {'id': src})
        q(f'MATCH (m:{label} {{id: $src}}) MERGE (n:{label} {{id: $id}}) ON CREATE SET n.v = m.count + 1, n.f = m.f + 1, n.s = m.name + \'-y\', n.b = m.count > 1', {'src': src, 'id': target})
        expected = [[[5, 'int'], [2.5, 'float'], ['src-y', 'str'], [True, 'bool']]]
        case('other bound node typed computed MATCH reader', read(target, 'n.v, n.f, n.s, n.b'), expected)
        case('other bound node get_node reader', prop(target, ['v', 'f', 's', 'b']), expected)
        q(f'MATCH (m:{label} {{id: $src}}) MERGE (n:{label} {{id: $id}}) ON MATCH SET n.v = m.count * 2', {'src': src, 'id': target})
        case('other bound node on match', read(target, 'n.v'), [[[8, 'int']]])
        for key, value, tag in [('numeric', 2, 'int'), ('textual', '2', 'str')]:
            nid = prefix + key
            q(f'MERGE (n:{label} {{id: $id}}) ON CREATE SET n.v = $v', {'id': nid, 'v': value})
            case('parameter stored type ' + key, prop(nid, ['v']), [[[value, tag]]])
            case('parameter equality filter ' + key, typed(q(f'MATCH (n:{label} {{id: $id}}) WHERE n.v = $v RETURN n.v', {'id': nid, 'v': value})), [[[value, tag]]])

        q(f'CREATE (n:{label} {{id: $id}})', {'id': b})
        rel_base = f'MATCH (a:{label} {{id: $a}}), (b:{label} {{id: $b}}) MERGE (a)-[r:MERGE12]->(b) '
        rel_params = {'a': a, 'b': b}
        q(rel_base + 'ON CREATE SET r.w = $p + 1', dict(rel_params, p=1))
        rel_read = f'MATCH (:{label} {{id: $id}})-[r:MERGE12]->() RETURN r.w, r.w > 1'
        case('relationship parameter computation final reader', typed(q(rel_read, {'id': a})), [[[2, 'int'], [True, 'bool']]])
        q(rel_base + 'ON MATCH SET r.w = r.w + 1', rel_params)
        case('relationship own value final reader', typed(q(rel_read, {'id': a})), [[[3, 'int'], [True, 'bool']]])
        refused = None
        try:
            q(rel_base + 'ON MATCH SET r.w = a.c', rel_params)
        except Exception as ex:
            refused = dict(type=type(ex).__name__, explicit='not supported' in str(ex))
        case('relationship other-variable expression explicitly refuses', refused, dict(type='GraphWriteError', explicit=True))
        case('relationship refused write leaves prior value', typed(q(rel_read, {'id': a})), [[[3, 'int'], [True, 'bool']]])
    except Exception as ex:
        failure = dict(type=type(ex).__name__, message=str(ex), trace=traceback.format_exc())
    finally:
        c.close()
        result = dict(verdict='AGREES' if failure is None and rows and all(r['prediction_agrees'] for r in rows) else 'DISAGREES_OR_INCOMPLETE',
                      completed_cases=len(rows), cases=rows, queries=queries, failure=failure, prefix=prefix, label=label,
                      source_identities=identities, source_inputs={rel: hashlib.sha256((h['PIN_DIR'] / rel).read_bytes()).hexdigest() for rel in source_files},
                      inputs={str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), HERE / 'next-cypher-merge-PAIRS.md', REPO / '.g5/Verus_verification/models/temporal_restore/binding.py', REPO / '.g5/uplift/consolidated/iteration-5/native-setup.json']},
                      elapsed=time.monotonic() - start, identity_checked=True, container=h['NAME'],
                      scope='Next-draw preparation only. Actual pinned parser/translator/SQL write transaction and independent SQL-path MATCH/get_node readers on fresh task-prefix identities, no erase or fault injection. Recent known repairs/regressions, not new discoveries. No new model, native executable-body proof, arbitrary expression/provider/type codec or all-route claim. Multirow capture and caller rollback are source survey obligations, unexecuted by this small panel.')
        Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({k: result[k] for k in ['verdict', 'completed_cases', 'elapsed', 'failure']}))
    assert result['verdict'] == 'AGREES'


if __name__ == '__main__':
    main()
