"""rebuild_reads binding: traversal readers while another connection runs engine.sync() (fixture ivg-cont-20261117-iris).

Writes s-R->a, a-Q->b, s-R->c (default graph, fresh prefix i57r_<tag>_), reads khop(s, 2) and
shortest_path_length(s, b) quietly, then in a loop while a child process (own connection) runs sync() several times.
Port of rebuild_reads.rs: a reader sees `visible(old, rows, k)`; as built (purge, then refill in an unspecified
order) that is any subset of the rows, so the permitted khop answers are {s} plus the walk over any subset, and
`theorem_reader_sees_seed_alone` requires the seed-alone answer to be reachable. khop and the length are two reads
at two moments, so each is judged against its own visible index (the first run paired them; receipt kept). Checks: quiet answers equal the
walk over all rows; every answer during sync lies in the permitted set; the seed-alone answer is observed.
Mutations: `swap` (permitted = the full answer only) must be detected by the observed departures; the tamper
(a node not in the rows put into one observed answer) must be detected."""
import hashlib, itertools, json, os, subprocess, sys, time
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

ROWS = [("s", "R", "a"), ("a", "Q", "b"), ("s", "R", "c")]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def walk(edges, seed, hops):
    seen, front = {seed}, {seed}
    for _ in range(hops):
        front = {o for s, _p, o in edges if s in front} - seen
        seen |= front
    return sorted(seen)


def length(edges, a, b, cap=5):
    if a == b:
        return 0
    seen, front = {a}, {a}
    for d in range(1, cap + 1):
        front = {o for s, _p, o in edges if s in front} - seen
        if b in front:
            return d
        seen |= front
    return -1


def permitted(mut):
    subsets = [ROWS] if mut.get("swap") else [list(c) for n in range(len(ROWS) + 1) for c in itertools.combinations(ROWS, n)]
    # khop and the path length are two reads at two moments of the rebuild: each sees its own visible index.
    return ({json.dumps(walk(es, "s", 2)) for es in subsets}, {length(es, "s", "b") for es in subsets})


def child(n):
    c = runtime.connect(); e = runtime.engine(c)
    for _ in range(n):
        e.sync()
    c.close()


def main():
    t0 = time.time(); tag = time.strftime("%H%M%S", time.gmtime()); P = f"i57r_{tag}_"
    c = runtime.connect(); e = runtime.engine(c); st = e._store
    for a, t, b in ROWS:
        e.create_edge(P + a, t, P + b)

    def read():
        out = {}
        try:
            out["khop"] = sorted(n[len(P):] for n in e.khop(P + "s", hops=2)["nodes"])
        except Exception as ex:
            out["khop"] = "ERR " + str(ex)[:60]
        try:
            out["spl"] = st.shortest_path_length(P + "s", P + "b", [], 5, "out")
        except Exception as ex:
            out["spl"] = "ERR " + str(ex)[:60]
        return json.dumps(out, sort_keys=True)

    quiet = Counter(read() for _ in range(int(os.environ.get("RR_QUIET", "40"))))
    proc = subprocess.Popen([sys.executable, "-B", __file__, "--child", os.environ.get("RR_SYNCS", "4")], env=os.environ)
    busy = Counter()
    while proc.poll() is None:
        busy[read()] += 1
    c.close()
    full = json.dumps({"khop": walk(ROWS, "s", 2), "spl": length(ROWS, "s", "b")}, sort_keys=True)
    seed_alone = json.dumps({"khop": ["s"], "spl": -1}, sort_keys=True)

    def judge(q, b, mut):
        ak, asp = permitted(mut)
        bad_quiet = [k for k in q if k != full]
        outside = [k for k in b if json.dumps(json.loads(k)["khop"]) not in ak or json.loads(k)["spl"] not in asp]
        witness = (seed_alone in b) if not mut.get("swap") else True
        return {"quiet_ok": not bad_quiet, "outside_permitted": outside, "seed_alone_witnessed": witness,
                "agrees": not bad_quiet and not outside and witness}

    base = judge(quiet, busy, {})
    sens = {"swap": not judge(quiet, busy, {"swap": True})["agrees"]}
    tampered = Counter(busy); k0 = next(iter(busy)); tampered[json.dumps({"khop": ["s", "zz"], "spl": 2}, sort_keys=True)] += 1
    tamper_detected = not judge(quiet, tampered, {})["agrees"]
    body = {"kind": "binding", "model": "rebuild_reads", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": tag, "prefix": P, "verdict": "AGREES" if base["agrees"] else "DISAGREES",
            "judgement": base, "quiet": dict(quiet), "during_sync": dict(busy),
            "reads_during_sync": sum(busy.values()), "departures_during_sync": sum(v for k, v in busy.items() if k != full),
            "seed_alone_reads": busy.get(seed_alone, 0), "sensitivities_detected": sens,
            "all_sensitivities_detected": all(sens.values()), "tamper_detected": tamper_detected,
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "rebuild_reads.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/_engine/schema.py", "iris_vector_graph/_engine/algorithms.py",
                                                                    "iris_vector_graph/stores/iris_sql_store.py", "iris_src/src/Graph/KG/TraversalBuild.cls",
                                                                    "iris_src/src/Graph/KG/Adjacency.cls", "iris_src/src/Graph/KG/TraversalBFS.cls",
                                                                    "iris_src/src/Graph/KG/TraversalPaths.cls"]}},
            "scope": "Actual engine.khop and IRISGraphStore.shortest_path_length on IRIS 2026.1 (pin 3eaa79cf), USER default graph, declared "
                     "(functional) adjacency index, while a second process on its own connection runs engine.sync() repeatedly. Only the "
                     "probe's three edges are interpreted; the rest of USER is rebuilt too. Arno absent."}
    d = REPO / ".g5/Verus_verification/results/rebuild_reads" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "reads_during_sync", "departures_during_sync", "seed_alone_reads",
                                            "sensitivities_detected", "tamper_detected", "elapsed_s")}))


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--child":
        child(int(sys.argv[2]))
    else:
        main()
