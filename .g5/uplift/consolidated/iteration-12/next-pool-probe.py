"""Unchanged pinned pool source, opaque links only; no sockets or DB operations."""
import asyncio, hashlib, importlib.util, json, runpy, sys, time, types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
h = runpy.run_path(str(REPO / '.g5/Verus_verification/models/temporal_restore/binding.py'))
path = h['PIN_DIR'] / 'iris_vector_graph/gql/pooling.py'
spec = importlib.util.spec_from_file_location('iris_vector_graph.gql.pooling', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


async def main():
    start = time.monotonic()
    rows = []
    link = object()
    engine = types.SimpleNamespace(conn=link)

    def record(name, actual, expected, forecast):
        rows.append(dict(label=name, actual=actual, expected_as_built=expected,
                         source_agrees=actual == expected, prospective_hypothesis=forecast))
        assert actual == expected, (name, actual, expected)

    pool = module.AsyncConnectionPool(engine, max_size=2)
    entered, release = asyncio.Event(), asyncio.Event()
    observed = []

    async def first():
        async with pool.acquire() as c:
            observed.append(c)
            entered.set()
            await release.wait()

    task = asyncio.create_task(first())
    await entered.wait()
    async with pool.acquire() as c:
        observed.append(c)
        record('two logical slots alias one physical link',
               dict(same_link=observed[0] is observed[1], created_count=pool._created_count),
               dict(same_link=True, created_count=2), 'Hypothesis1 distinct-borrower isolation is false for this helper; no actual concurrent DB use tested')
    release.set()
    await task
    record('two returned queue entries alias same physical link',
           dict(queue_size=pool._pool.qsize(), permits=pool._semaphore._value),
           dict(queue_size=2, permits=2), 'Counts are logical slots, not distinct physical links')

    serial = module.AsyncConnectionPool(engine, max_size=1)
    async with serial.acquire():
        waiter = asyncio.create_task(serial.acquire().__aenter__())
        await asyncio.sleep(0)
        record('capacity-one waiter blocked', waiter.done(), False, 'Capacity-one excludes a second admitted borrower')
        waiter.cancel()
        try:
            await waiter
        except asyncio.CancelledError:
            pass
        record('cancel waiting does not manufacture permit', serial._semaphore._value, 0, 'Hypothesis2 waiting cancellation passes')
    record('return after waiting cancellation restores capacity',
           dict(permits=serial._semaphore._value, queue_size=serial._pool.qsize(), created_count=serial._created_count),
           dict(permits=1, queue_size=1, created_count=1), 'Hypothesis2 passes for bounded schedule')
    try:
        async with serial.acquire():
            raise ValueError('owned opaque-body exception')
    except ValueError:
        pass
    record('raised borrower body returns logical link',
           dict(permits=serial._semaphore._value, queue_size=serial._pool.qsize()),
           dict(permits=1, queue_size=1), 'Hypothesis2 body exception passes')

    inside, wait = asyncio.Event(), asyncio.Event()

    async def cancel_body():
        async with serial.acquire():
            inside.set()
            await wait.wait()

    body = asyncio.create_task(cancel_body())
    await inside.wait()
    body.cancel()
    try:
        await body
    except asyncio.CancelledError:
        pass
    record('cancelled acquired body returns logical link',
           dict(permits=serial._semaphore._value, queue_size=serial._pool.qsize()),
           dict(permits=1, queue_size=1), 'Hypothesis2 acquired cancellation passes')
    module._pool_instance = None
    module._pool_lock = asyncio.Lock()
    other = types.SimpleNamespace(conn=object())
    one = await module.get_pool(engine)
    two = await module.get_pool(other)
    record('singleton retains first engine', dict(same_pool=one is two, first_engine=two.engine is engine),
           dict(same_pool=True, first_engine=True), 'Different app engine is not a new pool; actual resolvers bypass it')

    result = dict(verdict='AGREES_AS_BUILT_WITH_FORECAST_MISS', cases=rows, completed_cases=len(rows),
                  elapsed=time.monotonic()-start, socket_calls=0, native_calls=0, db_operations=0,
                  source_inputs={rel: hashlib.sha256((h['PIN_DIR'] / rel).read_bytes()).hexdigest() for rel in ['iris_vector_graph/gql/pooling.py', 'iris_vector_graph/gql/__init__.py', 'iris_vector_graph/gql/resolvers.py']},
                  inputs={str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), HERE / 'next-pool-PAIRS.md']},
                  scope='Builder alternate-workflow survey only. Unmodified pinned pooling module loaded directly with its real engine import, opaque link objects and explicit bounded asyncio schedules. No actual SQL/driver/network/server concurrency, safety/security scenario, product fix, new formal/issue/owner credit. Resolver and startup consumer bypass established by source inspection separately; helper distinct-link forecast refuted.')
    Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['verdict', 'completed_cases', 'elapsed']}))


if __name__ == '__main__':
    asyncio.run(main())
