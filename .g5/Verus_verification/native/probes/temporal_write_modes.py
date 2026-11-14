#!/usr/bin/env python3
"""Probe (temporal model, Q1): write modes and statistics — F1 (update double count), F2 (partial write
that a retry cannot repair) and F2b (the bulk fallback reports success).

Drives only public entry points: IRISGraphEngine.create_edge_temporal / bulk_create_edges_temporal /
delete_edge_temporal / get_edges_in_window / get_temporal_aggregate / get_edge_velocity, plus SQL reads of
Graph_KG.rdf_edges and raw reads of ^KG for the record. Expected outcomes come from the model's L1 rules,
computed from the raw window the probe reads back (never from the implementation's counters):

  L1-AGG (spec 254 US2/FR-003; RebuildBucketAggregate's "the aggregate describes the surviving edges"):
      whole-bucket tagg count/sum and the per-source bucket count equal the raw edges of the bucket.
  L1-W   (FR-003): an "insert" at occupied coordinates changes no store.
  DOC    (create_edge_temporal docstring): "A write IRIS refuses raises GraphWriteError and writes nothing";
         "upsert=True ... Aggregate counters (count/sum/min/max) remain based on the original value".

Model: .g5/Verus_verification/models/temporal/temporal.rs — witness_update_double_counts,
witness_partial_write_is_not_repaired_by_retry, witness_bulk_fallback_reports_success.

Trigger for the structural step's failure: a target id longer than Graph_KG.nodes.node_id (VARCHAR(256)), so
Adjacency.AssertTemporalRow's node INSERT fails after WriteStores has Set tout/tin/tlast and $Increment'ed
bucket. The temporal globals accept the id (subscripts are not length-checked at 300 characters).
Do not run against anything but this arm's instance (harness guard).
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import connect, engine, ensure_schema, reset, record  # noqa: E402

BUCKET = 300
T = 1_700_000_100            # bucket 5666667 (window [1_700_000_100, 1_700_000_399])
B = T // BUCKET
LO, HI = B * BUCKET, B * BUCKET + BUCKET - 1
P = "PROBE_TW"
LONG = "probe:long:" + "x" * 300   # > VARCHAR(256)



def _agg(eng, s, m, lo, hi):
    """The product's aggregate reader; a reader error (e.g. ValueError on float('None')) is the observation."""
    try:
        return eng.get_temporal_aggregate(s, P, m, lo, hi)
    except Exception as ex:  # noqa: BLE001
        return f"<reader error {type(ex).__name__}: {ex}>"

def kg(native, *subs):
    try:
        if native.isDefined("^KG", *subs) % 10:
            return native.get("^KG", *subs)
    except Exception as e:  # noqa: BLE001
        return f"<read error {e}>"
    return None


def raw_view(eng, native, s, o):
    """Everything the stores hold for (s, P, o) at T, through public readers and raw reads."""
    window = [e for e in eng.get_edges_in_window(s, P, LO, HI) if e.get("ts") == T]
    agg = {m: _agg(eng, s, m, LO, HI) for m in ("count", "sum", "min", "max")}
    cut = {m: _agg(eng, s, m, T, T) for m in ("count", "sum")}
    vel = eng.get_edge_velocity(s, window_seconds=BUCKET, now_ts=HI)
    cur = eng.conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ?", [s, P, o])
        rows = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", [o])
        node_rows = int(cur.fetchone()[0])
    except Exception as e:  # noqa: BLE001  (an id over the column length may itself be refused by the read)
        rows, node_rows = f"<sql error {e}>", f"<sql error {e}>"
    finally:
        cur.close()
    return {
        "window_edges": window,
        "agg_whole_bucket": agg,
        "agg_cut_window_T_T": cut,
        "velocity_bucket": vel,
        "rdf_edges_rows": rows,
        "node_rows_for_target": node_rows,
        "raw": {
            "tout": kg(native, "tout", 0, T, s, P, o),
            "bucket": kg(native, "bucket", 0, B, s),
            "tagg_count": kg(native, "tagg", 0, B, s, P, "count"),
            "tagg_sum": kg(native, "tagg", 0, B, s, P, "sum"),
            "tagg_min": kg(native, "tagg", 0, B, s, P, "min"),
            "tagg_max": kg(native, "tagg", 0, B, s, P, "max"),
        },
    }


def l1_expected(view):
    """L1-AGG from the raw window alone."""
    ws = [float(e.get("w", e.get("weight"))) for e in view["window_edges"]]
    return {"count": len(ws), "sum": float(sum(ws)), "velocity": len(ws)}


def agg_matches(view, exp):
    """count, sum and the per-source bucket count; a reader error on count/sum is not a match (and the caller
    reports it). min/max reader errors (review R1-5) are recorded only."""
    a = view["agg_whole_bucket"]
    try:
        return int(a["count"]) == exp["count"] and abs(float(a["sum"] or 0.0) - exp["sum"]) < 1e-9 \
            and int(view["velocity_bucket"]) == exp["velocity"]
    except (TypeError, ValueError):
        return False


def readable(view):
    a = view["agg_whole_bucket"]
    return not any(isinstance(a[m], str) and a[m].startswith("<reader error") for m in ("count", "sum"))


def case_update(eng, native, out):
    s, o = "probe:upd:s", "probe:upd:o"
    eng.create_edge_temporal(s, P, o, timestamp=T, weight=2.0)
    out["after_insert"] = raw_view(eng, native, s, o)
    if not (readable(out["after_insert"]) and agg_matches(out["after_insert"], {"count": 1, "sum": 2.0, "velocity": 1})):
        out["verdict"] = "INCONCLUSIVE: the first insert did not leave exact statistics (precondition)"
        return out
    eng.create_edge_temporal(s, P, o, timestamp=T, weight=9.0, mode="update")
    v = raw_view(eng, native, s, o)
    out["after_update"] = v
    exp = l1_expected(v)
    out["expected_l1"] = exp
    out["expected_doc_original_value"] = {"count": 1, "sum": 2.0}
    deleted = eng.delete_edge_temporal(s, P, o, T)
    vd = raw_view(eng, native, s, o)
    out["delete_returned"] = deleted
    out["after_delete"] = vd
    out["expected_l1_after_delete"] = l1_expected(vd)
    a = v["agg_whole_bucket"]
    if not (readable(v) and readable(vd)):
        out["verdict"] = "INCONCLUSIVE: count/sum could not be read after the update or the delete"
        return out
    def tagg_is(cnt, sm):
        return int(a["count"]) == cnt and abs(float(a["sum"] or 0.0) - sm) < 1e-9

    l1_ok = agg_matches(v, exp)
    tagg_l1 = tagg_is(1, 9.0)       # the raw store's statistics (L1-AGG)
    tagg_doc = tagg_is(1, 2.0)      # the docstrings' "original value" (tagg only; they say nothing of the bucket count)
    vel_ok = int(v["velocity_bucket"]) == 1
    del_ok = agg_matches(vd, l1_expected(vd))
    out["l1_holds_after_update"] = l1_ok
    out["doc_holds_after_update"] = tagg_doc
    out["l1_holds_after_delete"] = del_ok
    if not (len(v["window_edges"]) == 1 and abs(float(v["window_edges"][0].get("w", 0)) - 9.0) < 1e-9):
        out["verdict"] = "INCONCLUSIVE: the update did not leave one raw edge of weight 9"
    elif not tagg_l1 and not tagg_doc:
        out["verdict"] = (f"OBSERVED_DEFECT: one raw edge (w=9) but whole-bucket count={a['count']} sum={a['sum']} "
                          f"velocity={v['velocity_bucket']} (L1 expects 1/9.0/1, the docstring 1/2.0)")
    elif not vel_ok:
        out["verdict"] = (f"OBSERVED_DEFECT: tagg reads {'raw-exact' if tagg_l1 else 'original-value'}, but the per-source "
                          f"bucket count is {v['velocity_bucket']} over one raw edge")
    elif not del_ok:
        out["verdict"] = f"OBSERVED_DEFECT: after deleting the only edge, velocity={vd['velocity_bucket']} (expected 0)"
    else:
        out["verdict"] = "OBSERVED_AS_EXPECTED: " + ("raw-exact" if l1_ok else "original-value") + " aggregates"
    return out


def case_partial_write(eng, native, out):
    from iris_vector_graph.errors import GraphWriteError

    s, o = "probe:pw:s", LONG
    try:
        eng.create_edge_temporal(s, P, o, timestamp=T, weight=2.0)
        out["first_write"] = "returned (no error)"
    except GraphWriteError as e:
        out["first_write"] = f"GraphWriteError: {e}"
    except Exception as e:  # noqa: BLE001
        out["first_write"] = f"{type(e).__name__}: {e}"
    v1 = raw_view(eng, native, s, o)
    out["after_first"] = v1
    try:
        r = eng.create_edge_temporal(s, P, o, timestamp=T, weight=2.0)
        out["retry_insert"] = f"returned {r!r} (no error)"
        retry_silent = True
    except Exception as e:  # noqa: BLE001
        out["retry_insert"] = f"{type(e).__name__}: {e}"
        retry_silent = False
    v2 = raw_view(eng, native, s, o)
    out["after_retry"] = v2
    if out["first_write"].startswith("returned"):
        out["verdict"] = "INCONCLUSIVE: the over-long endpoint did not make the structural step fail (trigger not reproduced)"
        return out
    if "AssertTemporalRow" not in out["first_write"]:
        # review R1-12: a failure before WriteStores (validation, a reader) writes nothing and is not the F2 case
        out["verdict"] = f"INCONCLUSIVE: the write failed elsewhere than AssertTemporalRow ({out['first_write'][:160]})"
        return out
    wrote_something = bool(v1["window_edges"]) or v1["raw"]["bucket"] is not None
    l1_ok = agg_matches(v1, l1_expected(v1))
    unchanged = v1["raw"] == v2["raw"] and len(v1["window_edges"]) == len(v2["window_edges"])
    out["retry_changed_nothing"] = unchanged
    if wrote_something and retry_silent and not unchanged:
        out["verdict"] = (f"INCONCLUSIVE: the silent retry changed the stores ({v1['raw']} -> {v2['raw']}); "
                          "not the collision the model predicts")
    elif wrote_something and retry_silent:
        out["verdict"] = (f"OBSERVED_DEFECT: the refused write left {len(v1['window_edges'])} raw edge(s), "
                          f"bucket={v1['raw']['bucket']}, tagg count={v1['raw']['tagg_count']} (docstring: writes nothing); "
                          f"the retry returned without error and wrote nothing more (L1-AGG holds: {l1_ok})")
    elif wrote_something:
        out["verdict"] = (f"OBSERVED_DEFECT: the refused write left raw stores (bucket={v1['raw']['bucket']}, "
                          f"tagg count={v1['raw']['tagg_count']}); the retry raised again")
    else:
        out["verdict"] = "OBSERVED_AS_EXPECTED: the refused write left nothing"
    return out


def case_bulk_fallback(eng, native, mode, out):
    from iris_vector_graph.errors import GraphWriteError

    s = f"probe:bulk:{mode}:s"
    o0, o1 = f"probe:bulk:{mode}:o0", LONG
    edges = [
        {"s": s, "p": P, "o": o0, "ts": T, "w": 1.0},
        {"s": s, "p": P, "o": o1, "ts": T + 1, "w": 5.0},   # same bucket and (s, p) key as edge 0
    ]
    out["mode"] = mode
    try:
        r = eng.bulk_create_edges_temporal(edges, mode=mode)
        out["returned"] = {"written": int(r), "collisions": r.collisions, "skipped": r.skipped}
        raised = False
    except GraphWriteError as e:
        out["returned"] = f"GraphWriteError: {e}"
        raised = True
    except Exception as e:  # noqa: BLE001
        out["returned"] = f"{type(e).__name__}: {e}"
        raised = True
    window = eng.get_edges_in_window(s, P, LO, HI)
    out["window_all"] = window
    ws = [float(e.get("w", e.get("weight"))) for e in window]
    exp = {"count": len(ws), "sum": float(sum(ws)), "velocity": len(ws)}
    out["expected_l1"] = exp
    agg = {m: _agg(eng, s, m, LO, HI) for m in ("count", "sum")}
    vel = eng.get_edge_velocity(s, window_seconds=BUCKET, now_ts=HI)
    out["agg_whole_bucket"] = agg
    out["velocity_bucket"] = vel
    out["raw"] = {"bucket": kg(native, "bucket", 0, B, s), "tagg_count": kg(native, "tagg", 0, B, s, P, "count"),
                  "tagg_sum": kg(native, "tagg", 0, B, s, P, "sum")}
    cur = eng.conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = ? AND p = ?", [s, P])
        out["rdf_edges_rows_for_source"] = int(cur.fetchone()[0])
    finally:
        cur.close()
    agg_ok = agg_matches({"agg_whole_bucket": agg, "velocity_bucket": vel}, exp)
    out["l1_holds"] = agg_ok
    # review R1-12: the defect is the refused edge's partial write being hidden; show it is there: e1's raw entry
    # exists without its row, and (update mode) the surfaced error names the structural step
    e1_raw = any(e.get("ts") == T + 1 for e in window)
    out["refused_edge_raw_present"] = e1_raw
    if not readable({"agg_whole_bucket": agg}):
        out["verdict"] = f"INCONCLUSIVE: mode={mode} count/sum could not be read"
    elif not e1_raw:
        out["verdict"] = f"INCONCLUSIVE: mode={mode} the refused edge left no raw entry (no partial write to hide)"
    elif raised and "AssertTemporalRow" not in str(out["returned"]):
        out["verdict"] = f"INCONCLUSIVE: mode={mode} the batch failed elsewhere than AssertTemporalRow ({str(out['returned'])[:160]})"
    elif not raised and isinstance(out["returned"], dict) and out["returned"]["written"] == 2 \
            and out["returned"]["collisions"] == 0 and not agg_ok:
        out["verdict"] = (f"OBSERVED_DEFECT: mode={mode} batch with a refused edge returned written=2, collisions=0, no error; "
                          f"raw edges={exp['count']} (sum {exp['sum']}), tagg count={agg['count']} sum={agg['sum']}, "
                          f"velocity={vel}, rows={out['rdf_edges_rows_for_source']}")
    elif not agg_ok:
        out["verdict"] = (f"OBSERVED_DEFECT: mode={mode} after the fallback the whole-bucket count/sum/velocity "
                          f"{agg['count']}/{agg['sum']}/{vel} differ from the raw store {exp['count']}/{exp['sum']}/{exp['velocity']} "
                          f"(call: {out['returned']})")
    elif raised:
        out["verdict"] = f"OBSERVED_AS_EXPECTED: mode={mode} the refused edge raised and the statistics match the raw store"
    else:
        out["verdict"] = f"INCONCLUSIVE: mode={mode} unexpected result {out['returned']}"
    return out


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    obs = {"model": "temporal", "probe": "temporal_write_modes", "T": T, "bucket": B}
    try:
        obs["schema"] = ensure_schema(eng)
        obs["adjacency_indexed"] = str(native.classMethodValue("Graph.KG.Adjacency", "Indexed"))
        cases = {}
        obs["cases"] = cases
        for name, fn in (("update_double_count", lambda o: case_update(eng, native, o)),
                         ("partial_write_retry", lambda o: case_partial_write(eng, native, o)),
                         ("bulk_fallback_insert", lambda o: case_bulk_fallback(eng, native, "insert", o)),
                         ("bulk_fallback_update", lambda o: case_bulk_fallback(eng, native, "update", o))):
            reset(eng, native)
            out = cases.setdefault(name, {})   # filled as the case runs: a crash keeps what was seen (review R1-6)
            try:
                fn(out)
            except Exception as e:  # noqa: BLE001
                out["verdict"] = f"INCONCLUSIVE: {type(e).__name__}: {e}"
                out["trace"] = traceback.format_exc()
        if obs["adjacency_indexed"] != "1":
            verdict = "INCONCLUSIVE: the adjacency functional index is not declared (AssertTemporalRow path not taken)"
        elif any(c["verdict"].startswith("OBSERVED_DEFECT") for c in cases.values()):
            verdict = "OBSERVED_DEFECT: " + "; ".join(f"{k}: {c['verdict']}" for k, c in cases.items()
                                                      if c["verdict"].startswith("OBSERVED_DEFECT"))
        elif all(c["verdict"].startswith("OBSERVED_AS_EXPECTED") for c in cases.values()):
            verdict = "OBSERVED_AS_EXPECTED: every case"
        else:
            verdict = "INCONCLUSIVE: " + "; ".join(f"{k}: {c['verdict']}" for k, c in cases.items())
        obs["verdict"] = verdict
    finally:
        try:
            reset(eng, native)
        except Exception:  # noqa: BLE001
            pass
        path = record("temporal_write_modes", obs)
    print(f"{obs.get('verdict', 'INCONCLUSIVE: probe did not finish')} [{path}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
