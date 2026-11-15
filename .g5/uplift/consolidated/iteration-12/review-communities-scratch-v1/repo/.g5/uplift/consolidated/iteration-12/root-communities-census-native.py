"""Root-only real node/edge writers, native census and actual SQL fallback."""
import hashlib, json, runpy, time, traceback, types, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
h = runpy.run_path(str(REPO / '.g5/Verus_verification/models/temporal_restore/binding.py'))
from iris_vector_graph import _edgeless


class CensusUnavailable:
    def __init__(self, actual):
        self.actual, self.failures = actual, 0

    def classMethodValue(self, cls, method, *args):
        if cls == 'Graph.KG.Edgeless' and method == 'LonersJson':
            self.failures += 1
            raise RuntimeError('owned controlled census provider unavailable')
        return self.actual.classMethodValue(cls, method, *args)

    def __getattr__(self, name):
        return getattr(self.actual, name)


def main():
    start = time.monotonic()
    c = h['connect']()
    e = h['IRISGraphEngine'](c, embedding_dimension=4)
    assert e.ledger.meta()['state'] == 'disabled'
    prefix = 'census12:' + uuid.uuid4().hex[:8] + ':'
    graph = prefix + 'named'
    rows = []
    failure = None
    native = e._iris_obj()
    fault = CensusUnavailable(native)

    def projection(value):
        return {k[len(prefix):]: v[len(prefix):] if isinstance(v, str) and v.startswith(prefix) else v
                for k, v in value.items() if k.startswith(prefix)}

    def case(label, fn, want):
        before = fault.failures
        got, error = None, None
        try:
            got = projection(fn())
        except Exception as ex:
            error = dict(type=type(ex).__name__, message=str(ex))
        rows.append(dict(label=label, result=got, expected=want, error=error,
                         injected_census_failures=fault.failures-before, agrees=error is None and got == want))

    try:
        for gid in ['', graph]:
            for name in ['iso', 'loop', 'a', 'b']:
                assert e.create_node(prefix + name, graph=gid)
            assert e.create_edge(prefix + 'a', 'R', prefix + 'b', graph=gid)
            assert e.create_edge(prefix + 'loop', 'L', prefix + 'loop', graph=gid)
        want = dict(iso=False, loop=True)
        for gid, name in [('', 'default'), (graph, 'named')]:
            case('native census ' + name, lambda gid=gid: e._loners(gid), want)
            case('actual SQL census ' + name, lambda gid=gid: _edgeless.loners_sql(c, 'Graph_KG.nodes', 'Graph_KG.rdf_edges', gid), want)
        e._iris_obj = types.MethodType(lambda self: fault, e)
        for gid, name in [('', 'default'), (graph, 'named')]:
            case('provider refusal invokes real SQL fallback ' + name, lambda gid=gid: e._loners(gid), want)
        case('public WCC after census provider refusal', lambda: e.kg_WCC(), dict(a='a', b='a', iso='iso', loop='loop'))
        case('public CDLP1 after census provider refusal', lambda: e.kg_CDLP(1), dict(a='b', b='a', iso='iso', loop='loop'))
    except Exception as ex:
        failure = dict(type=type(ex).__name__, message=str(ex), trace=traceback.format_exc())
    finally:
        c.close()
        sources = ['iris_vector_graph/_engine/algorithms.py', 'iris_vector_graph/_edgeless.py', 'iris_src/src/Graph/KG/Edgeless.cls', 'iris_src/src/Graph/KG/Algorithms.cls']
        inputs = [Path(__file__), HERE / 'root-communities-census-predictions.md', REPO / '.g5/Verus_verification/models/temporal_restore/binding.py', REPO / '.g5/uplift/consolidated/iteration-5/native-setup.json']
        result = dict(verdict='AGREES' if failure is None and len(rows) == 8 and all(r['agrees'] for r in rows) else 'DISAGREES_OR_INCOMPLETE',
                      completed_cases=len(rows), cases=rows, failure=failure, prefix=prefix, graph=graph,
                      total_injected_census_failures=fault.failures, elapsed=time.monotonic()-start,
                      source_inputs={rel: hashlib.sha256((h['PIN_DIR'] / rel).read_bytes()).hexdigest() for rel in sources},
                      inputs={str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                      identity_checked=True, container=h['NAME'],
                      scope='Actual fresh default/named node+edge writers and prefix-projected native vs SQL census, followed by public WCC/CDLP. Only LonersJson is made unavailable by an in-process class-call adapter; it supplies no rows/results, and SQL/core/public readers execute unchanged. No organic outage, class removal, global erase/security/source patch/native-body/universal driver or collation proof. Existing setup5 export/class audit reused.')
        Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['verdict', 'completed_cases', 'elapsed', 'failure']}))


if __name__ == '__main__':
    main()
