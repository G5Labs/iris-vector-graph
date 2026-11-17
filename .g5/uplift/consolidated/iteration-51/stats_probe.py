"""W57 probe (iteration 51): temporal statistics readers on the run-isolated fixture ivg-cont-20261117-iris.

Each case writes a fresh history into its own graph (prefix i51_<tag>) through public entry points and records the
readers' answers (Python return values, or the class method's return for ObjectScript-only members). Expected values
are in stats-PAIRS.md (frozen before the deciding source was read); this script only observes.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-51/stats_probe.py)
"""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i51_{TAG}_"
T = 1_900_000_200
B = T // 300
assert T % 300 == 0


def g(x):
    return f"i51{TAG}{x}"


def n(x):
    return P + x


def obs(f):
    try:
        return f()
    except Exception as ex:  # record, not raise: the error is an observation
        return {"error": type(ex).__name__, "msg": str(ex)[:300]}


def aggs(e, s, lo, hi, graph, p="P", metrics=("count", "sum", "min", "max", "avg")):
    return {m: obs(lambda m=m: e.get_temporal_aggregate(n(s), p, m, T + lo, T + hi, graph=graph)) for m in metrics}


def short(rows):
    if isinstance(rows, list):
        return [{k: (v[len(P):] if isinstance(v, str) and v.startswith(P) else v) for k, v in r.items()} if isinstance(r, dict)
                else (r[len(P):] if isinstance(r, str) and r.startswith(P) else r) for r in rows]
    return rows


def main():
    c = runtime.connect(); e = runtime.engine(c)
    nat = e._iris_obj()
    out = {"run": RUN, "prefix": P, "T": T, "fixture": runtime.NAME, "product": runtime.PRODUCT}

    def bulk(graph, rows):
        return int(e.bulk_create_edges_temporal([{"s": n(s), "p": p, "o": n(o), "ts": T + dt, "w": w} for s, p, o, dt, w in rows], graph=graph))

    # ------------------------------------------------------------------ A: aggregate reads
    GA, GA2 = g("a"), g("a2")
    out["A_setup"] = bulk(GA, [("ann", "P", "b", 5, 2.0), ("ann", "P", "b", 100, 4.0), ("ann", "P", "c", 299, 9.0),
                               ("ann", "P", "d", 300, 1.0), ("ann", "P", "b", 650, 5.0)])
    out["A_setup2"] = bulk(GA2, [("ann", "P", "z", 50, 100.0)])
    out["A1_cut_100_300"] = aggs(e, "ann", 100, 300, GA)
    out["A1_whole_0_299"] = aggs(e, "ann", 0, 299, GA)
    out["A2_empty_301_649"] = aggs(e, "ann", 301, 649, GA)
    out["A2_unknown_metric"] = obs(lambda: e.get_temporal_aggregate(n("ann"), "P", "median", T, T + 299, graph=GA))
    out["A8_scope_GA2"] = aggs(e, "ann", 0, 299, GA2, metrics=("count", "sum"))
    # A3 update vs collision
    e.create_edge_temporal(n("upd"), "P", n("x"), timestamp=T + 10, weight=2.0, graph=GA)
    e.create_edge_temporal(n("upd"), "P", n("x"), timestamp=T + 10, weight=9.0, graph=GA, mode="update")
    e.create_edge_temporal(n("col"), "P", n("x"), timestamp=T + 10, weight=2.0, graph=GA)
    e.create_edge_temporal(n("col"), "P", n("x"), timestamp=T + 10, weight=9.0, graph=GA)
    for s in ("upd", "col"):
        out[f"A3_{s}_whole"] = aggs(e, s, 0, 299, GA)
        out[f"A3_{s}_cut"] = aggs(e, s, 1, 299, GA, metrics=("count", "sum", "max"))
        out[f"A3_{s}_raw"] = short(obs(lambda s=s: e.get_edges_in_window(n(s), "P", T, T + 299, graph=GA)))
        out[f"V3_{s}_velocity"] = obs(lambda s=s: e.get_edge_velocity(n(s), 300, now_ts=T + 299, graph=GA))
        out[f"D_{s}_distinct"] = obs(lambda s=s: e.get_distinct_count(n(s), "P", T, T + 299, graph=GA))
    out["A3_upd_delete"] = obs(lambda: e.delete_edge_temporal(n("upd"), "P", n("x"), T + 10, graph=GA))
    out["A3_upd_after_delete_whole"] = aggs(e, "upd", 0, 299, GA, metrics=("count", "sum"))
    out["A3_upd_after_delete_velocity"] = obs(lambda: e.get_edge_velocity(n("upd"), 300, now_ts=T + 299, graph=GA))
    # A4 rollback vs commit
    cur = c.cursor()
    try:
        cur.execute("START TRANSACTION")
        e.create_edge_temporal(n("rb"), "P", n("x"), timestamp=T + 20, weight=3.0, graph=GA)
        out["A4_rb_inside_count"] = obs(lambda: e.get_temporal_aggregate(n("rb"), "P", "count", T + 1, T + 299, graph=GA))
        cur.execute("ROLLBACK")
    finally:
        cur.close()
    e.create_edge_temporal(n("rbc"), "P", n("x"), timestamp=T + 20, weight=3.0, graph=GA)
    for s in ("rb", "rbc"):
        out[f"A4_{s}_whole"] = aggs(e, s, 0, 299, GA)
        out[f"A4_{s}_cut"] = aggs(e, s, 1, 299, GA, metrics=("count", "sum"))
        out[f"A4_{s}_velocity"] = obs(lambda s=s: e.get_edge_velocity(n(s), 300, now_ts=T + 299, graph=GA))
        out[f"A4_{s}_distinct"] = obs(lambda s=s: e.get_distinct_count(n(s), "P", T, T + 299, graph=GA))
        out[f"A4_{s}_groups"] = short(obs(lambda s=s: e.get_bucket_groups("P", T, T + 299, source_prefix=n(s), graph=GA)))
        out[f"A4_{s}_latest"] = short(obs(lambda s=s: [(r["s"], r["ts"] - T) for r in e.get_latest_edges([n(s)], graph=GA)]))
    # A7 delete the minimum vs a middle weight
    bulk(GA, [("dm", "P", "x", 10, 1.0), ("dm", "P", "y", 20, 5.0), ("dm", "P", "z", 30, 3.0),
              ("dn", "P", "x", 10, 1.0), ("dn", "P", "y", 20, 5.0), ("dn", "P", "z", 30, 3.0)])
    e.delete_edge_temporal(n("dm"), "P", n("x"), T + 10, graph=GA)
    e.delete_edge_temporal(n("dn"), "P", n("z"), T + 30, graph=GA)
    out["A7_dm"] = aggs(e, "dm", 0, 299, GA, metrics=("count", "min", "max"))
    out["A7_dn"] = aggs(e, "dn", 0, 299, GA, metrics=("count", "min", "max"))

    # ------------------------------------------------------------------ A5/A6: raw purge vs bucket-range purge
    GP, GQ = g("p"), g("q")
    hist = [("ps", "P", "b", 5, 2.0), ("ps", "P", "b", 100, 4.0), ("ps", "P", "c", 299, 9.0), ("ps", "P", "d", 400, 1.0)]
    bulk(GP, hist); bulk(GQ, hist)
    out["A5_purge"] = list(obs(lambda: e.purge_raw_before(T + 300, graph=GP, retire_bare_nodes=False)))
    out["A6_purge_bad_order"] = obs(lambda: e.purge_bucket_range(B + 5, B, graph=GQ))
    out["A6_purge_empty_bucket"] = obs(lambda: e.purge_bucket_range(B + 10, B + 12, graph=GQ))
    out["A6_purge"] = obs(lambda: e.purge_bucket_range(B, B, graph=GQ))
    for tag_, G in (("A5", GP), ("A6", GQ)):
        out[f"{tag_}_whole_0_299"] = aggs(e, "ps", 0, 299, G)
        out[f"{tag_}_cut_100_299"] = aggs(e, "ps", 100, 299, G, metrics=("count", "sum"))
        out[f"{tag_}_whole_plus_cut_0_500"] = aggs(e, "ps", 0, 500, G, metrics=("count", "sum"))
        out[f"{tag_}_groups_whole"] = short(obs(lambda G=G: e.get_bucket_groups("P", T, T + 299, source_prefix=n("ps"), graph=G)))
        out[f"{tag_}_groups_cut"] = short(obs(lambda G=G: e.get_bucket_groups("P", T + 100, T + 299, source_prefix=n("ps"), graph=G)))
        out[f"{tag_}_velocity_b0"] = obs(lambda G=G: e.get_edge_velocity(n("ps"), 0, now_ts=T + 299, graph=G))
        out[f"{tag_}_velocity_b1"] = obs(lambda G=G: e.get_edge_velocity(n("ps"), 0, now_ts=T + 599, graph=G))
        out[f"{tag_}_distinct"] = obs(lambda G=G: e.get_distinct_count(n("ps"), "P", T, T + 299, graph=G))
        out[f"{tag_}_targets"] = short(obs(lambda G=G: e.get_bucket_group_targets(n("ps"), "P", T, T + 299, graph=G)))
        out[f"{tag_}_latest"] = short(obs(lambda G=G: [(r["s"], r["ts"] - T) for r in e.get_latest_edges([n("ps")], graph=G)]))
    # a later delete in the purged bucket (A6b: after bucket-range purge; A5b: after raw purge of another bucket)
    out["A6b_delete"] = obs(lambda: e.delete_edge_temporal(n("ps"), "P", n("b"), T + 5, graph=GQ))
    out["A6b_whole_0_299"] = aggs(e, "ps", 0, 299, GQ, metrics=("count", "sum"))
    out["A6b_velocity_b0"] = obs(lambda: e.get_edge_velocity(n("ps"), 0, now_ts=T + 299, graph=GQ))
    bulk(GP, [("ps", "P", "e", 120, 7.0)])
    out["A5b_whole_after_rewrite"] = aggs(e, "ps", 0, 299, GP, metrics=("count", "sum"))
    out["A5b_delete"] = obs(lambda: e.delete_edge_temporal(n("ps"), "P", n("e"), T + 120, graph=GP))
    out["A5b_whole_after_delete"] = aggs(e, "ps", 0, 299, GP, metrics=("count", "sum"))
    out["A5b_velocity_b0"] = obs(lambda: e.get_edge_velocity(n("ps"), 0, now_ts=T + 299, graph=GP))

    # ------------------------------------------------------------------ G: bucket groups and targets
    GB = g("b")
    bulk(GB, [("ann", "CALLED", "b", 5, 2.0), ("ann", "CALLED", "b", 100, 4.0), ("ann", "CALLED", "c", 299, 9.0),
              ("ann", "CALLED", "d", 300, 1.0), ("ann", "CALLED", "b", 650, 5.0), ("ben", "CALLED", "ann", 10, 7.0),
              ("ann", "OTHER", "q", 50, 10.0), ("tg", "P", "x", 5, 1.0), ("tg", "P", "y", 150, 1.0)])
    for lo, hi in ((100, 300), (0, 1000), (301, 649)):
        out[f"G1_{lo}_{hi}"] = short(obs(lambda lo=lo, hi=hi: e.get_bucket_groups("CALLED", T + lo, T + hi, source_prefix=P, graph=GB)))
    out["G2_all_predicates"] = short(obs(lambda: e.get_bucket_groups("", T, T + 299, source_prefix=n("ann"), graph=GB)))
    out["G2_called_only"] = short(obs(lambda: e.get_bucket_groups("CALLED", T, T + 299, source_prefix=n("ann"), graph=GB)))
    out["G4_targets_100_200"] = short(obs(lambda: e.get_bucket_group_targets(n("tg"), "P", T + 100, T + 200, graph=GB)))
    out["G4_targets_0_299"] = short(obs(lambda: e.get_bucket_group_targets(n("tg"), "P", T, T + 299, graph=GB)))

    # ------------------------------------------------------------------ V/B: velocity and bursts
    GV, GV2 = g("v"), g("v2")
    bulk(GV, [("vs", "P", "a", 299, 1.0), ("vs", "P", "a", 300, 1.0), ("vs", "Q", "a", 600, 1.0),
              ("vf", "P", "a", 590, 1.0), ("vd", "P", "a", 10, 1.0), ("vd", "P", "b", 20, 1.0)])
    bulk(GV2, [("vs", "P", "a", 300 + i, 1.0) for i in range(5)])
    out["V1_now650"] = obs(lambda: e.get_edge_velocity(n("vs"), 300, now_ts=T + 650, graph=GV))
    out["V1_now599"] = obs(lambda: e.get_edge_velocity(n("vs"), 300, now_ts=T + 599, graph=GV))
    out["V1_window_alias"] = obs(lambda: e.get_edge_velocity(n("vs"), window=0, now_ts=T + 650, graph=GV))
    out["V1_future_in_now_bucket"] = obs(lambda: e.get_edge_velocity(n("vf"), 300, now_ts=T + 301, graph=GV))
    out["V5_before_delete"] = obs(lambda: e.get_edge_velocity(n("vd"), 300, now_ts=T + 299, graph=GV))
    e.delete_edge_temporal(n("vd"), "P", n("a"), T + 10, graph=GV)
    out["V5_after_delete"] = obs(lambda: e.get_edge_velocity(n("vd"), 300, now_ts=T + 299, graph=GV))
    out["B1_pred_unused"] = short(obs(lambda: e.find_burst_nodes("NOPE", 300, 2, now_ts=T + 650, graph=GV)))
    out["B1_pred_empty"] = short(obs(lambda: e.find_burst_nodes("", 300, 2, now_ts=T + 650, graph=GV)))
    out["B2_threshold3"] = short(obs(lambda: e.find_burst_nodes("", 300, 3, now_ts=T + 650, graph=GV)))
    out["B2_threshold1"] = short(obs(lambda: e.find_burst_nodes("", 300, 1, now_ts=T + 650, graph=GV)))
    out["B3_GV2"] = short(obs(lambda: e.find_burst_nodes("", 300, 2, now_ts=T + 650, graph=GV2)))
    out["B4_wallclock"] = short(obs(lambda: e.find_burst_nodes("", 300, 1, graph=GV)))

    # ------------------------------------------------------------------ D: distinct-count estimate
    GD = g("d")
    rows = [("d1", "P", "x", 10, 1.0), ("d1", "P", "x", 20, 1.0), ("d1", "P", "x", 30, 1.0),
            ("d3", "P", "x", 10, 1.0), ("d3", "P", "y", 20, 1.0), ("d3", "P", "z", 30, 1.0),
            ("dw", "P", "x", 5, 1.0), ("dw", "P", "y", 400, 1.0),
            ("dd", "P", "x", 10, 1.0), ("dd", "P", "y", 20, 1.0)]
    rows += [("dbig", "P", f"t{i:03d}", 100 + i, 1.0) for i in range(100)]
    bulk(GD, rows)
    for s in ("d1", "d3", "dbig", "dd"):
        out[f"D_{s}"] = obs(lambda s=s: e.get_distinct_count(n(s), "P", T, T + 299, graph=GD))
    out["D_none"] = obs(lambda: e.get_distinct_count(n("nobody"), "P", T, T + 299, graph=GD))
    out["D2_touch_100_200"] = obs(lambda: e.get_distinct_count(n("dw"), "P", T + 100, T + 200, graph=GD))
    out["D2_touch_400_500"] = obs(lambda: e.get_distinct_count(n("dw"), "P", T + 400, T + 500, graph=GD))
    out["D2_none_600_800"] = obs(lambda: e.get_distinct_count(n("dw"), "P", T + 600, T + 800, graph=GD))
    e.delete_edge_temporal(n("dd"), "P", n("y"), T + 20, graph=GD)
    out["D4_dd_after_delete"] = obs(lambda: e.get_distinct_count(n("dd"), "P", T, T + 299, graph=GD))
    out["D5_all_sources"] = obs(lambda: e.get_distinct_count("", "P", T, T + 299, graph=GD))

    # ------------------------------------------------------------------ L: latest reads
    GL, GL2 = g("l"), g("l2")
    bulk(GL, [("ls", "P", "a", 5, 1.0), ("ls", "P", "b", 650, 2.0), ("lp", "P", "a", 5, 1.0), ("lp", "P", "b", 650, 2.0)])
    lat = lambda **kw: short(obs(lambda: [(r["s"], r["p"], r["o"], r["ts"] - T, r.get("w"), r.get("attrs")) for r in e.get_latest_edges(graph=kw.pop("graph", GL), **kw)]))  # noqa: E731
    out["L1_named"] = lat(sources=[n("ls")])
    out["L1_before650"] = lat(sources=[n("ls")], before=T + 650)
    out["L2_lookback100"] = lat(sources=[n("ls")], before=T + 650, lookback=100)
    out["L2_lookback700"] = lat(sources=[n("ls")], before=T + 650, lookback=700)
    out["L5_prefix"] = lat(source_prefix=n("l"))
    out["L5_every"] = lat()
    out["L5_empty_list"] = lat(sources=[])
    out["L6_rebuild"] = obs(lambda: e.rebuild_temporal_latest(graph=GL))
    out["L6_after_rebuild"] = lat()
    e.delete_edge_temporal(n("ls"), "P", n("b"), T + 650, graph=GL)
    out["L3_after_delete"] = lat(sources=[n("ls")])
    out["L4_purge"] = list(obs(lambda: e.purge_raw_before(T + 100, graph=GL, retire_bare_nodes=False)))
    out["L4_after_purge"] = lat(sources=[n("ls"), n("lp")])
    out["L4_after_purge_every"] = lat()
    bulk(GL2, [("lq", "P", "a", 5, 1.0), ("lq", "P", "b", 650, 2.0)])
    e.purge_raw_before(T + 1000, graph=GL2, retire_bare_nodes=False)
    out["L4_purge_all"] = lat(sources=[n("lq")], graph=GL2)
    # L7 update vs collision at the newest coordinate
    e.create_edge_temporal(n("lu"), "P", n("a"), timestamp=T + 700, weight=1.0, attrs={"k": 1}, graph=GL)
    e.create_edge_temporal(n("lu"), "P", n("a"), timestamp=T + 700, weight=7.0, attrs={"k": 2}, graph=GL, mode="update")
    e.create_edge_temporal(n("lc"), "P", n("a"), timestamp=T + 700, weight=1.0, attrs={"k": 1}, graph=GL)
    e.create_edge_temporal(n("lc"), "P", n("a"), timestamp=T + 700, weight=7.0, attrs={"k": 2}, graph=GL)
    out["L7"] = lat(sources=[n("lu"), n("lc")])
    # rollback of a newer write
    e.create_edge_temporal(n("lr"), "P", n("a"), timestamp=T + 5, weight=1.0, graph=GL)
    cur = c.cursor()
    try:
        cur.execute("START TRANSACTION")
        e.create_edge_temporal(n("lr"), "P", n("b"), timestamp=T + 900, weight=1.0, graph=GL)
        cur.execute("ROLLBACK")
    finally:
        cur.close()
    out["L8_rollback"] = lat(sources=[n("lr")])

    # ------------------------------------------------------------------ S: label sets
    d1 = {"port": 1972, "a": True, "n": None, "s": "x"}
    d2 = {"s": "x", "n": None, "a": True, "port": 1972}
    h1 = obs(lambda: e.intern_label_set(d1)); h2 = obs(lambda: e.intern_label_set(d2))
    out["S1"] = {"h1": h1, "h2": h2, "resolve": obs(lambda: e.resolve_label_set(h1)), "unknown": obs(lambda: e.resolve_label_set("f" * 40))}
    q1 = {"a": 'x","b":"y'}; q2 = {"a": "x", "b": "y"}
    hq1 = obs(lambda: e.intern_label_set(q1)); hq2 = obs(lambda: e.intern_label_set(q2))
    out["S3_quote"] = {"h1": hq1, "h2": hq2, "resolve1": obs(lambda: e.resolve_label_set(hq1))}
    hf = obs(lambda: e.intern_label_set({"x": 0.5}))
    out["S4_fraction"] = {"h": hf, "resolve": obs(lambda: e.resolve_label_set(hf)),
                          "json_loads": obs(lambda: json.loads(e.resolve_label_set(hf)))}
    e.purge_raw_before(T + 100000, graph=GA, retire_bare_nodes=False)
    out["S2_after_purge"] = obs(lambda: e.resolve_label_set(h1))

    # ------------------------------------------------------------------ M: millisecond entry point (ObjectScript)
    GM = g("m")
    TM = T * 1000
    out["M_insert"] = obs(lambda: nat.classMethodValue("Graph.KG.TemporalIndexMS", "InsertEdge", GM, n("ms"), "P", n("a"), TM + 5, 1, "", 0, 0, ""))
    out["M_bucketcount"] = obs(lambda: nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetBucketCount", GM, TM // 300000, n("ms")))
    out["M_velocity_explicit"] = obs(lambda: nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetVelocity", GM, n("ms"), 300000, TM + 10))
    out["M_velocity_default_now"] = obs(lambda: nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetVelocity", GM, n("ms"), 300000 * 100000, 0))
    out["M_aggregate"] = obs(lambda: nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetAggregate", GM, n("ms"), "P", "count", TM, TM + 299999))
    c.close()
    dest = HERE / f"stats-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
    print(dest)
    print(json.dumps(out, sort_keys=True, default=str)[:20000])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(); sys.exit(1)
