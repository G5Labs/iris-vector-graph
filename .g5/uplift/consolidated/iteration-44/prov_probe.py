"""W50: PROV-O export of temporal edges (run-isolated continuation fixture; files under $W50_FILES; ordinary data)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W50_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
FILES = Path(os.environ.get("W50_FILES", "/tmp")) / f"w50-{RUN}"
BIG = int(os.environ.get("W50_BIG", "40000"))


def main():
    import rdflib
    FILES.mkdir(parents=True, exist_ok=True)
    c = runtime.connect(); e = runtime.engine(c)
    out = {"run": RUN, "fixture": runtime.NAME, "files": str(FILES), "cases": {}}
    s, A, B, P = f"pv{TAG}:s", f"pv{TAG}:A", f"pv{TAG}:B", f"MEAS{TAG}"
    base = 1_900_000_000 + int(TAG) * 1000; t1, t2 = base, base + 3600
    lo, hi = base - 10, base + 7200     # windows restricted to this run's edges

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    e.create_edge_temporal(s, P, A, timestamp=t1, weight=1.0)
    e.create_edge_temporal(s, P, B, timestamp=t2, weight=2.0)
    e.create_edge_temporal(s, P, B, timestamp=t2, weight=2.0)          # P7: same (s, p, o, t) again
    def p1():
        f = FILES / "p1.ttl"; r = e.prov_export(str(f), ts_start=lo, ts_end=hi)
        g = rdflib.Graph().parse(str(f)); PROV = rdflib.Namespace("http://www.w3.org/ns/prov#")
        return {"answer": {k: r[k] for k in ("activities", "entities")}, "started": sorted(str(x) for x in g.objects(predicate=PROV.startedAtTime)),
                "ended": len(list(g.objects(predicate=PROV.endedAtTime)))}
    case("P1_P7_export", p1)
    case("P2_ts_start_inclusive", lambda: {k: v for k, v in e.prov_export(str(FILES / "p2.ttl"), ts_start=t2, ts_end=hi).items() if k != "path"})
    case("P3_ts_end_inclusive", lambda: {k: v for k, v in e.prov_export(str(FILES / "p3.ttl"), ts_start=lo, ts_end=t1).items() if k != "path"})
    case("P4_as_dict", lambda: e.prov_as_dict(f"{s}|{P}|{A}|{t1}"))
    case("P4b_as_dict_missing", lambda: e.prov_as_dict(f"{s}|{P}|{A}|{t1 + 1}"))
    G = f"pvg{TAG}"
    e.create_edge_temporal(f"pv{TAG}:gs", P, f"pv{TAG}:gA", timestamp=t1 + 5, weight=1.0, graph=G)
    case("P5_named_graph_excluded", lambda: {k: v for k, v in e.prov_export(str(FILES / "p5.ttl"), ts_start=lo, ts_end=hi).items() if k != "path"})
    case("P6_from_cypher", lambda: {k: v for k, v in e.prov_export_from_cypher("MATCH (n {node_id: $id}) RETURN n.node_id", str(FILES / "p6.ttl"), parameters={"id": B}).items() if k != "path"})
    def big():
        t0 = time.time(); pad = "z" * 40; bs, bt = base + 100000, base + 100000
        rows = [{"s": f"pv{TAG}:bigsrc{pad}", "p": P, "o": f"pv{TAG}:bigdst{i:06d}{pad}", "ts": bt + (i % 300), "w": 1.0} for i in range(BIG)]
        for k in range(0, BIG, 5000):
            e.bulk_create_edges_temporal(rows[k:k + 5000])
        res = {"load_s": round(time.time() - t0, 1)}
        try:
            r = e.prov_export(str(FILES / "p8.ttl"), ts_start=bt, ts_end=bt + 400)
            res["export"] = {k: r[k] for k in ("activities", "entities")}; res["file_bytes"] = (FILES / "p8.ttl").stat().st_size
        except Exception as ex:
            res["export"] = "RAISED " + type(ex).__name__ + ": " + str(ex)[:200]
        try:
            res["as_dict_small_edge_after_big"] = e.prov_as_dict(f"{s}|{P}|{A}|{t1}")["startedAtTime"]
        except Exception as ex:
            res["as_dict_small_edge_after_big"] = "RAISED " + type(ex).__name__ + ": " + str(ex)[:200]
        try:
            r = e.prov_export(str(FILES / "p8small.ttl"), ts_start=lo, ts_end=hi)
            res["small_window_export_after_big"] = r["activities"]
        except Exception as ex:
            res["small_window_export_after_big"] = "RAISED " + type(ex).__name__ + ": " + str(ex)[:200]
        return res
    case("P8_P9_large_window", big)
    dest = HERE / f"prov-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
