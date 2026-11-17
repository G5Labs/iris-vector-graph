"""W43: khop, kg_GRAPH_WALK and kg_GRAPH_PATH on small frozen shapes, and one walk longer than an IRIS string
(run-isolated continuation fixture only; ordinary data)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W43_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
BIG = int(os.environ.get("W43_BIG", "40000"))


def main():
    c = runtime.connect(); e = runtime.engine(c)
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    p = f"t{TAG}"
    N = lambda x: f"{p}{x}"  # noqa: E731

    def edge(s, t, o, graph=None):
        e.create_edge(N(s), t, N(o), graph=graph)

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    for x in ["s", "a", "b", "c", "d", "z", "ds", "da", "db", "dx", "w1", "w2", "w3", "w4", "ws", "wy"]:
        e.create_node(N(x), labels=["T"])
    edge("s", "R", "a"); edge("a", "R", "b"); edge("b", "R", "c"); edge("s", "R", "d")        # chain + branch
    edge("ds", "R", "da"); edge("ds", "R", "db"); edge("da", "R", "dx"); edge("db", "R", "dx")  # diamond
    edge("w1", "T1", "w2"); edge("w2", "T2", "w3"); edge("w3", "T2", "w4"); edge("w2", "T1", "wy")  # typed chain
    edge("ws", "R", "w1"); edge("ws", "Q", "w1")                                               # two types, same target

    def short(r):
        return {"nodes": [n[len(p):] for n in r["nodes"]],
                "edges": sorted((x["s"][len(p):], x["p"], x["o"][len(p):], x["step"]) for x in r["edges"])}

    def rows(r):
        return [(a[len(p):], t, b[len(p):], h) for a, t, b, h in r]

    case("K1_khop_chain", lambda: short(e.khop(N("s"), hops=2)))
    case("K2_khop_no_out_edge", lambda: short(e.khop(N("c"), hops=2)))
    case("K3_khop_missing", lambda: e.khop(N("missing"), hops=2))
    case("K4_khop_max_nodes", lambda: short(e.khop(N("s"), hops=2, max_nodes=2)))
    case("K5_khop_diamond", lambda: short(e.khop(N("ds"), hops=2)))
    case("W1_walk_chain", lambda: rows(e.kg_GRAPH_WALK(N("s"), max_depth=3)))
    case("W2_walk_typed", lambda: rows(e.kg_GRAPH_WALK(N("w1"), max_depth=3, edge_types=["T1", "T2"])))
    case("W3_walk_max_results", lambda: rows(e.kg_GRAPH_WALK(N("s"), max_depth=3, max_results=2)))
    case("W5_walk_diamond", lambda: rows(e.kg_GRAPH_WALK(N("ds"), max_depth=2)))
    case("W6_walk_two_types_same_target", lambda: rows(e.kg_GRAPH_WALK(N("ws"), max_depth=1)))
    case("K6_khop_two_types_same_target", lambda: short(e.khop(N("ws"), hops=1)))
    case("P1_graph_path", lambda: [(r[0], r[1], r[2][len(p):], r[3], r[4][len(p):]) for r in e.kg_GRAPH_PATH(N("w1"), "T1", "T2")])

    # W4: the same chain only in a named graph
    G = f"tg{TAG}"
    for x in ["gs", "ga", "gb"]:
        e.create_node(N(x), labels=["T"], graph=G)
    edge("gs", "R", "ga", graph=G); edge("ga", "R", "gb", graph=G)
    case("W4_walk_named_graph_only", lambda: rows(e.kg_GRAPH_WALK(N("gs"), max_depth=3)))
    case("K7_khop_named_graph_only", lambda: short(e.khop(N("gs"), hops=2)))

    # L1: a star whose walk answer is longer than an IRIS string
    def big():
        hub = N("hub")
        pad = "x" * 40
        t0 = time.time()
        n = e.bulk_ingest_edges([(hub, f"{p}leaf{i:06d}{pad}", "STAR") for i in range(BIG)], predicate="STAR")
        load = round(time.time() - t0, 1)
        res = {"loaded": n, "load_s": load}
        t1 = time.time()
        try:
            r = e.kg_GRAPH_WALK(hub, max_depth=1, max_results=BIG + 10)
            res["walk"] = {"rows": len(r), "distinct_targets": len({x[2] for x in r}), "s": round(time.time() - t1, 1)}
        except Exception as exc:
            res["walk"] = "RAISED " + str(exc)[:300]
        t2 = time.time()
        try:
            k = e.khop(hub, hops=1, max_nodes=BIG + 10)
            res["khop"] = {"nodes": len(k["nodes"]), "edges": len(k["edges"]), "s": round(time.time() - t2, 1)}
        except Exception as exc:
            res["khop"] = "RAISED " + str(exc)[:300]
        import iris
        nat = iris.createIRIS(c)
        res["staged_bfs_r_left"] = [str(x) for x in _children(nat, "^ArnoKG", "bfs_r")][:5]
        return res
    case("L1_walk_longer_than_a_string", big)

    dest = HERE / f"traversal-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))


def _children(nat, glo, *subs):
    out, k = [], ""
    while True:
        k = nat.nextSubscript(False, glo, *subs, k)
        if k is None or k == "":
            return out
        out.append(k)


if __name__ == "__main__":
    main()
