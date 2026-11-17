"""W48: kg_NEIGHBORS, kg_MENTIONS and kg_NEIGHBORHOOD_EXPANSION on frozen shapes (run-isolated continuation fixture)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W48_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def main():
    c = runtime.connect(); e = runtime.engine(c)
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    p = f"nb{TAG}_"; R, Q = f"R{TAG}", f"Q{TAG}"
    N = lambda x: p + x  # noqa: E731
    S = lambda xs: sorted(x[len(p):] for x in xs)  # noqa: E731

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    for x in ["a", "b", "c", "d", "e", "a2", "m"]:
        e.create_node(N(x))
    e.create_edge(N("a"), R, N("b")); e.create_edge(N("a"), R, N("c")); e.create_edge(N("b"), R, N("d"))
    e.create_edge(N("a"), Q, N("e")); e.create_edge(N("a2"), R, N("b")); e.create_edge(N("a"), "MENTIONS", N("m"))
    case("N1_out", lambda: S(e.kg_NEIGHBORS([N("a")], predicate=R)))
    case("N1b_out_any_type", lambda: S(e.kg_NEIGHBORS([N("a")])))
    case("N2_in", lambda: S(e.kg_NEIGHBORS([N("b")], direction="in")))
    case("N3_both", lambda: S(e.kg_NEIGHBORS([N("b")], direction="both")))
    case("N4_predicate", lambda: S(e.kg_NEIGHBORS([N("a")], predicate=R)))
    case("N5_distinct_true", lambda: S(e.kg_NEIGHBORS([N("a"), N("a2")], predicate=R)))
    case("N5_distinct_false", lambda: S(e.kg_NEIGHBORS([N("a"), N("a2")], predicate=R, distinct=False)))
    def n6():
        t = N("t"); e.create_node(t)
        srcs = [N(f"s{i:04d}") for i in range(1200)]
        e.bulk_ingest_edges([(s, t, f"T{TAG}") for s in srcs], predicate=f"T{TAG}")
        r = e.kg_NEIGHBORS(srcs, predicate=f"T{TAG}")
        return {"len": len(r), "distinct": len(set(r))}
    case("N6_chunked_distinct", n6)
    G = f"nbg{TAG}"
    for x in ["ga", "gb"]:
        e.create_node(N(x), graph=G)
    e.create_edge(N("ga"), R, N("gb"), graph=G)
    case("N7_named_graph_only", lambda: S(e.kg_NEIGHBORS([N("ga")])))
    e.create_node(N("a"), graph=G); e.create_node(N("z"), graph=G); e.create_edge(N("a"), R, N("z"), graph=G)
    case("N7b_same_id_two_graphs", lambda: S(e.kg_NEIGHBORS([N("a")], predicate=R)))
    case("N8_mentions", lambda: S(e.kg_MENTIONS([N("a")])))
    for x in ["h", "h1", "h2", "h3", "h4"]:
        e.create_node(N(x))
    e.create_edge(N("h"), R, N("h1"), qualifiers={"confidence": 900}); e.create_edge(N("h"), R, N("h2"), qualifiers={"confidence": 500})
    e.create_edge(N("h"), R, N("h3"), qualifiers={"confidence": 100}); e.create_edge(N("h"), R, N("h4"))
    case("N9_expansion", lambda: [(d["target"][len(p):], d["confidence"]) for d in e.kg_NEIGHBORHOOD_EXPANSION([N("h")], confidence_threshold=500)])

    dest = HERE / f"neighbors-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
