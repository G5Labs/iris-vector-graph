"""Iteration 53 temporal probe: review round 2 items M1, m1, m2, m9 on the run-isolated fixture ivg-cont-20261117-iris.

M1  nested map/list label-set values: two interns of the same dict, the resolved text; scalar neighbors; invalid JSON.
m1  a TemporalIndexMS edge read by the seconds readers (whole bucket vs cut window vs raw window), and the converse.
m2  empty source / predicate in get_temporal_aggregate, get_distinct_count, get_bucket_groups.
m9  TemporalIndexMS GetVelocity / FindBursts window argument units.

Fresh graphs, prefix i53t_<tag>; USER namespace. Only observes (errors are observations).

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-53/temporal/labelset_probe.py)
"""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[4]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i53t_{TAG}_"
T = 1_900_000_200
B = T // 300
assert T % 300 == 0


def G(x):
    return f"i53t{TAG}{x}"


def N(x):
    return P + x


def obs(f):
    try:
        return f()
    except Exception as ex:
        return {"error": type(ex).__name__, "msg": str(ex)[:300]}


def main():
    c = runtime.connect(); e = runtime.engine(c); nat = e._iris_obj()
    out = {"run": RUN, "prefix": P, "T": T, "fixture": runtime.NAME, "product": runtime.PRODUCT}

    # ---------------------------------------------------------------- M1
    cases = {"nested_map": {N("k"): {"b": 1}}, "list": {N("k"): [1, 2]}, "empty_map": {N("k"): {}},
             "string": {N("k"): "v"}, "number": {N("k"): 7}, "bool": {N("k"): True}, "null": {N("k"): None},
             "mixed": {N("a"): "v", N("z"): [1]}}
    lab = {}
    for k, d in cases.items():
        h1 = obs(lambda d=d: e.intern_label_set(d)); h2 = obs(lambda d=d: e.intern_label_set(d))
        lab[k] = {"h1": h1, "h2": h2, "same": h1 == h2,
                  "r1": obs(lambda h=h1: e.resolve_label_set(h)) if isinstance(h1, str) else None,
                  "r2": obs(lambda h=h2: e.resolve_label_set(h)) if isinstance(h2, str) else None}
    out["M1"] = lab
    out["M1_invalid_json_class"] = obs(lambda: str(nat.classMethodValue("Graph.KG.TemporalIndex", "InternLabelSet", "{not json")))
    out["M1_array_top_class"] = obs(lambda: str(nat.classMethodValue("Graph.KG.TemporalIndex", "InternLabelSet", "[1,2]")))

    # ---------------------------------------------------------------- m1
    g1 = G("ms")
    ms_ts = (T + 50) * 1000
    out["m1_ms_insert"] = obs(lambda: str(nat.classMethodValue("Graph.KG.TemporalIndexMS", "InsertEdge", g1, N("s"), "P", N("o"), ms_ts, 2, "", 0, 0, "")))
    out["m1_ms_bucket_number"] = ms_ts // 300000
    out["m1_seconds_bucket_number"] = (T + 50) // 300
    out["m1_sec_whole_count"] = obs(lambda: e.get_temporal_aggregate(N("s"), "P", "count", T, T + 299, graph=g1))
    out["m1_sec_whole_sum"] = obs(lambda: e.get_temporal_aggregate(N("s"), "P", "sum", T, T + 299, graph=g1))
    out["m1_sec_cut_count"] = obs(lambda: e.get_temporal_aggregate(N("s"), "P", "count", T, T + 298, graph=g1))
    out["m1_sec_groups_whole"] = obs(lambda: e.get_bucket_groups("P", T, T + 299, source_prefix=P, graph=g1))
    out["m1_sec_targets_whole"] = obs(lambda: e.get_bucket_group_targets(N("s"), "P", T, T + 299, graph=g1))
    out["m1_sec_velocity"] = obs(lambda: e.get_edge_velocity(N("s"), 300, now_ts=T + 299, graph=g1))
    out["m1_sec_distinct"] = obs(lambda: e.get_distinct_count(N("s"), "P", T, T + 299, graph=g1))
    out["m1_sec_raw_window"] = obs(lambda: e.get_edges_in_window(N("s"), "P", T, T + 299, graph=g1))
    out["m1_sec_raw_window_ms_range"] = obs(lambda: len(e.get_edges_in_window(N("s"), "P", ms_ts - 1, ms_ts + 1, graph=g1)))
    # converse: a seconds edge read by the ms class's whole-bucket aggregate
    g2 = G("sec")
    e.create_edge_temporal(N("t"), "P", N("o"), timestamp=T + 50, weight=3.0, graph=g2)
    out["m1_ms_whole_count_of_seconds_edge"] = obs(lambda: str(nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetAggregate", g2, N("t"), "P", "count", str(T * 1000), str(T * 1000 + 299999))))
    out["m1_ms_cut_count_of_seconds_edge"] = obs(lambda: str(nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetAggregate", g2, N("t"), "P", "count", str(T * 1000), str(T * 1000 + 299998))))

    # ---------------------------------------------------------------- m2
    g3 = G("emp")
    e.create_edge_temporal(N("u"), "P", N("x"), timestamp=T + 5, graph=g3)
    e.create_edge_temporal(N("u"), "Q", N("y"), timestamp=T + 6, graph=g3)
    e.create_edge_temporal(N("w"), "P", N("z"), timestamp=T + 7, graph=g3)
    out["m2_agg_src_empty_whole"] = obs(lambda: e.get_temporal_aggregate("", "P", "count", T, T + 299, graph=g3))
    out["m2_agg_pred_empty_whole"] = obs(lambda: e.get_temporal_aggregate(N("u"), "", "count", T, T + 299, graph=g3))
    out["m2_agg_src_empty_cut_with_edges"] = obs(lambda: e.get_temporal_aggregate("", "P", "count", T, T + 298, graph=g3))
    out["m2_agg_src_empty_cut_no_edges"] = obs(lambda: e.get_temporal_aggregate("", "P", "count", T + 100, T + 200, graph=g3))
    out["m2_distinct_src_named_pred_empty"] = obs(lambda: e.get_distinct_count(N("u"), "", T, T + 299, graph=g3))
    out["m2_distinct_src_empty_pred_P"] = obs(lambda: e.get_distinct_count("", "P", T, T + 299, graph=g3))
    out["m2_distinct_src_empty_pred_empty"] = obs(lambda: e.get_distinct_count("", "", T, T + 299, graph=g3))
    out["m2_distinct_src_u_pred_P"] = obs(lambda: e.get_distinct_count(N("u"), "P", T, T + 299, graph=g3))
    out["m2_groups_pred_empty"] = obs(lambda: e.get_bucket_groups("", T, T + 299, source_prefix=P, graph=g3))
    out["m2_targets_pred_empty"] = obs(lambda: e.get_bucket_group_targets(N("u"), "", T, T + 299, graph=g3))

    # ---------------------------------------------------------------- m9
    g4 = G("vel")
    b0 = 1_900_000_200_000 // 300000  # ms bucket number
    t0 = b0 * 300000
    nat.classMethodValue("Graph.KG.TemporalIndexMS", "InsertEdge", g4, N("v"), "P", N("a"), t0 + 5, 1, "", 0, 0, "")
    nat.classMethodValue("Graph.KG.TemporalIndexMS", "InsertEdge", g4, N("v"), "P", N("b"), t0 + 300000 + 5, 1, "", 0, 0, "")
    now = t0 + 300000 + 1000  # 1 s into the later bucket: now - 300 stays in it, now - 300000 reaches the earlier one
    out["m9_now_ms"] = now
    out["m9_vel_window_300"] = obs(lambda: int(nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetVelocity", g4, N("v"), 300, now)))
    out["m9_vel_window_300000"] = obs(lambda: int(nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetVelocity", g4, N("v"), 300000, now)))
    out["m9_bursts_window_300_thr2"] = obs(lambda: str(nat.classMethodValue("Graph.KG.TemporalIndexMS", "FindBursts", g4, "P", 300, 2, now)))
    out["m9_bursts_window_300000_thr2"] = obs(lambda: str(nat.classMethodValue("Graph.KG.TemporalIndexMS", "FindBursts", g4, "P", 300000, 2, now)))

    path = HERE / f"temporal-observed-{RUN}.json"
    path.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str)); print("wrote", path)


if __name__ == "__main__":
    main()
