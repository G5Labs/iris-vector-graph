#!/usr/bin/env python3
"""Probe (temporal model, Q3): does a rolled-back temporal write leave its $Increment counters? (F3)

Each case commits or rolls back a temporal write through a public entry point, then compares the temporal
statistics with the raw edges read back through the public readers:

  R1  ledger changeset [create_temporal_edge, create_relationship(to an unknown node)] -> refused
      (LedgerApply.ApplyAll returns failed_op, Ledger.Commit TROLLBACK 1); then the temporal edge alone is
      committed (the retry).
  R2  START TRANSACTION; ledger.commit([create_temporal_edge]); ROLLBACK (the caller's rollback, 4.7.0 nesting).
  R3  START TRANSACTION; create_edge_temporal(...); ROLLBACK (a direct temporal write inside the caller's
      transaction: the store's native object is created on the same connection).
  R4  ledger changeset [create_temporal_edge to an over-long target id]: the structural step throws inside
      the commit; Ledger.Commit's Catch rolls back ("inconsistent"). The error must name AssertTemporalRow.
  R5  (review R1-9) delete_edge_temporal of a source's only edge in its bucket inside the caller's transaction,
      then ROLLBACK: RemoveTemporalRow's $Increment(bucket,-1) is not undone, its Kill at 0 is (restored as 0),
      RebuildBucketAggregate's Sets/Kill are (model witness_rolled_back_delete_undercounts).
  R5b one of two edges deleted and rolled back (no Kill: the decrement stays).
  R6  delete_node of the target inside the caller's transaction (EraseNodes -> RemoveTemporalRow), then ROLLBACK.
Discrimination (review R1-12): R1 requires the refusal to name op 1 (so op 0, the temporal op, ran); R2/R3 require
the edge visible inside the transaction; R4 requires the failure to name AssertTemporalRow; R5/R5b/R6 require the
delete to have removed the edge inside the transaction and the raw edges to come back with the rollback, and the
statistics to have been exact before. A case that cannot show its precondition is INCONCLUSIVE, not a defect.

Expected (model L1, computed from the raw window, not from the counters):
  L1-ATOMIC (spec 224, Changeset.create_temporal_edge docstring: "written inside the ledger's TSTART/TCOMMIT
  transaction, atomically with all structural ops"; USER_GUIDE "your rollback removes both"): a rolled-back
  write leaves no trace in any temporal store — whole-bucket count 0, sum 0, velocity 0.
  L1-AGG after the retry: count 1, sum = the weight, velocity 1.
Premise under test: P-INCR (ADR-0010 Context; USER_GUIDE "Writes inside your transaction"): IRIS does not undo
$Increment on TROLLBACK. Model: witness_refused_changeset_leaves_counts, witness_blocked_changeset_leaves_counts,
witness_throw_in_changeset_leaves_bucket, witness_caller_rollback_leaves_counts.
BlocksCommit (a redaction in progress) takes the same TROLLBACK 1 path; it is not driven here.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import connect, engine, ensure_schema, reset, record  # noqa: E402

BUCKET = 300
P = "PROBE_RB"
A, Bn = "probe:rb:a", "probe:rb:b"
GHOST = "probe:rb:ghost-not-a-node"
LONG = "probe:rb:long:" + "x" * 300


def window_bounds(ts):
    b = ts // BUCKET
    return b, b * BUCKET, b * BUCKET + BUCKET - 1


def kg(native, *subs):
    try:
        if native.isDefined("^KG", *subs) % 10:
            return native.get("^KG", *subs)
    except Exception as e:  # noqa: BLE001
        return f"<read error {e}>"
    return None


def agg(eng, s, m, lo, hi):
    """The product's aggregate reader; a reader error is recorded as the observation, not raised."""
    try:
        return eng.get_temporal_aggregate(s, P, m, lo, hi)
    except Exception as ex:  # noqa: BLE001
        return f"<reader error {type(ex).__name__}: {ex}>"


def stats(eng, native, s, ts):
    b, lo, hi = window_bounds(ts)
    window = [e for e in eng.get_edges_in_window(s, P, lo, hi)]
    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    raw_ws = [e.get("w", e.get("weight")) for e in window]
    ws = [num(x) for x in raw_ws if num(x) is not None]
    return {
        "window_edges": window,
        # an edge whose weight is not a number (e.g. the text 'None') is recorded, not parsed: it is itself evidence
        "unparsable_weights": [x for x in raw_ws if num(x) is None],
        "expected_l1": {"count": len(ws), "sum": float(sum(ws)), "velocity": len(ws)},
        "agg_whole_bucket": {m: agg(eng, s, m, lo, hi) for m in ("count", "sum", "min", "max")},
        "velocity_bucket": eng.get_edge_velocity(s, window_seconds=BUCKET, now_ts=hi),
        "raw": {
            "bucket": kg(native, "bucket", 0, b, s),
            "tagg_count": kg(native, "tagg", 0, b, s, P, "count"),
            "tagg_sum": kg(native, "tagg", 0, b, s, P, "sum"),
            "tagg_min": kg(native, "tagg", 0, b, s, P, "min"),
            "tagg_hll": kg(native, "tagg", 0, b, s, P, "hll") is not None,
        },
    }


def readable(st):
    """count and sum read as numbers and every raw weight parsed. min/max reader errors (review R1-5: the product's
    get_temporal_aggregate raises for an empty or half-rolled-back bucket) are recorded but do not decide a verdict."""
    a = st["agg_whole_bucket"]
    return not st.get("unparsable_weights") and not any(
        isinstance(a[m], str) and a[m].startswith("<reader error") for m in ("count", "sum"))


def exact(st):
    """L1-AGG on count, sum and the per-source bucket count."""
    e, a = st["expected_l1"], st["agg_whole_bucket"]
    if not readable(st):
        return False
    try:
        return int(a["count"]) == e["count"] and abs(float(a["sum"] or 0.0) - e["sum"]) < 1e-9 \
            and int(st["velocity_bucket"]) == e["velocity"]
    except (TypeError, ValueError):
        return False


def seed(eng):
    from iris_vector_graph.ledger.changeset import Changeset

    eng.ledger.enable()
    cs = Changeset(actor="probe", actor_type="system", message="temporal rollback probe seed")
    cs.create_node(A)
    cs.create_node(Bn)
    eng.ledger.commit(cs)


def head_seq(eng):
    try:
        return eng.ledger.head().seq
    except Exception as e:  # noqa: BLE001
        return f"<{e}>"


def verdict_for(name, rolled_back_stats, extra=""):
    st = rolled_back_stats
    if not readable(st):
        return f"INCONCLUSIVE: {name}: count/sum or a raw weight could not be read{extra}"
    if st["window_edges"]:
        return f"INCONCLUSIVE: {name}: the raw edge survived the rollback (the write did not join the transaction){extra}"
    if exact(st):
        return f"OBSERVED_AS_EXPECTED: {name}: nothing left after the rollback{extra}"
    a = st["agg_whole_bucket"]
    return (f"OBSERVED_DEFECT: {name}: no raw edge after the rollback, but whole-bucket count={a['count']} sum={a['sum']} "
            f"velocity={st['velocity_bucket']}{extra}")


def case_r1(eng, native, out):
    from iris_vector_graph.ledger.changeset import Changeset

    ts = 1_700_000_100
    out.update({"ts": ts, "head_before": head_seq(eng)})
    cs = Changeset(actor="probe", actor_type="system", message="temporal op then a refused op")
    cs.create_temporal_edge(A, P, Bn, ts=ts, weight=2.0, mode="insert")
    cs.create_relationship(A, "PROBE_REL", GHOST)
    op_index = None
    try:
        eng.ledger.commit(cs)
        out["commit"] = "committed (unexpected)"
    except Exception as e:  # noqa: BLE001
        out["commit"] = f"{type(e).__name__}: {e}"
        op_index = getattr(e, "op_index", None)
    # ApplyAll applies ops in order and returns at the first refusal: op 1 refused means op 0 (the temporal op) ran
    out["refused_op_index"] = op_index
    out["head_after_refusal"] = head_seq(eng)
    out["after_refusal"] = stats(eng, native, A, ts)
    retry = Changeset(actor="probe", actor_type="system", message="the retry")
    retry.create_temporal_edge(A, P, Bn, ts=ts, weight=2.0, mode="insert")
    eng.ledger.commit(retry)
    out["after_retry"] = stats(eng, native, A, ts)
    if out["commit"].startswith("committed"):
        out["verdict"] = "INCONCLUSIVE: R1: the changeset with an unknown endpoint committed"
        return out
    if op_index != 1:
        out["verdict"] = f"INCONCLUSIVE: R1: the refusal names op {op_index}, not op 1 (the temporal op may not have run)"
        return out
    v = verdict_for("R1 refused changeset (op 1 refused, op 0 ran)", out["after_refusal"])
    r = out["after_retry"]
    if not exact(r):
        a = r["agg_whole_bucket"]
        v += (f"; after the retry {len(r['window_edges'])} raw edge(s) but count={a['count']} sum={a['sum']} "
              f"velocity={r['velocity_bucket']}")
        if v.startswith("OBSERVED_AS_EXPECTED"):
            v = "OBSERVED_DEFECT: " + v.split(": ", 1)[1]
    out["verdict"] = v
    return out


def case_r2(eng, native, out):
    from iris_vector_graph.ledger.changeset import Changeset

    ts = 1_700_000_700
    out.update({"ts": ts, "head_before": head_seq(eng)})
    cur = eng.conn.cursor()
    try:
        cur.execute("START TRANSACTION")
        cs = Changeset(actor="probe", actor_type="system", message="inside the caller's transaction")
        cs.create_temporal_edge(A, P, Bn, ts=ts, weight=3.0, mode="insert")
        try:
            eng.ledger.commit(cs)
            out["commit"] = "committed inside the caller's transaction"
        except Exception as e:  # noqa: BLE001
            out["commit"] = f"{type(e).__name__}: {e}"
        out["inside"] = stats(eng, native, A, ts)
        cur.execute("ROLLBACK")
    finally:
        cur.close()
    out["head_after_rollback"] = head_seq(eng)
    out["after_rollback"] = stats(eng, native, A, ts)
    if not out["commit"].startswith("committed"):
        out["verdict"] = f"INCONCLUSIVE: R2: the commit inside the caller's transaction failed ({out['commit']})"
    elif not out["inside"]["window_edges"]:
        out["verdict"] = "INCONCLUSIVE: R2: the committed temporal edge was not visible inside the transaction"
    else:
        out["verdict"] = verdict_for("R2 caller rollback of a ledger commit", out["after_rollback"])
    return out


def case_r3(eng, native, out):
    ts = 1_700_001_300
    out["ts"] = ts
    cur = eng.conn.cursor()
    try:
        cur.execute("START TRANSACTION")
        eng.create_edge_temporal(A, P, Bn, timestamp=ts, weight=4.0)
        out["inside"] = stats(eng, native, A, ts)
        cur.execute("ROLLBACK")
    finally:
        cur.close()
    out["after_rollback"] = stats(eng, native, A, ts)
    if not out["inside"]["window_edges"]:
        out["verdict"] = "INCONCLUSIVE: R3: the temporal edge was not visible inside the transaction"
    else:
        out["verdict"] = verdict_for("R3 caller rollback of create_edge_temporal", out["after_rollback"])
    return out


def case_r4(eng, native, out):
    from iris_vector_graph.ledger.changeset import Changeset

    ts = 1_700_001_900
    out.update({"ts": ts, "head_before": head_seq(eng)})
    cs = Changeset(actor="probe", actor_type="system", message="temporal op whose structural step throws")
    cs.create_temporal_edge(A, P, LONG, ts=ts, weight=5.0, mode="update")
    try:
        eng.ledger.commit(cs)
        out["commit"] = "committed (unexpected)"
    except Exception as e:  # noqa: BLE001
        out["commit"] = f"{type(e).__name__}: {e}"
    out["head_after"] = head_seq(eng)
    out["after"] = stats(eng, native, A, ts)
    if out["commit"].startswith("committed"):
        out["verdict"] = "INCONCLUSIVE: R4: the over-long endpoint did not make the commit fail"
    elif "AssertTemporalRow" not in out["commit"]:
        # the failure must be the structural step inside WriteStores, after its $Increment(bucket)
        out["verdict"] = f"INCONCLUSIVE: R4: the commit failed elsewhere than AssertTemporalRow ({out['commit'][:160]})"
    else:
        out["verdict"] = verdict_for("R4 throw inside a changeset (AssertTemporalRow)", out["after"])
    return out


def restored_verdict(name, before, inside, after):
    """R1-9: a rolled-back delete must give back exactly the statistics it took (L1-ATOMIC + L1-AGG)."""
    if len(inside["window_edges"]) >= len(before["window_edges"]):
        return f"INCONCLUSIVE: {name}: the delete removed nothing inside the transaction"
    if len(after["window_edges"]) != len(before["window_edges"]):
        return f"INCONCLUSIVE: {name}: the raw edges did not come back with the rollback (the delete did not join it)"
    if not (readable(before) and readable(after)):
        return f"INCONCLUSIVE: {name}: count/sum or a raw weight could not be read"
    if not exact(before):
        return f"INCONCLUSIVE: {name}: the statistics were not exact before the delete"
    if exact(after):
        return f"OBSERVED_AS_EXPECTED: {name}: the rollback gave back the raw edges and their statistics"
    a, e = after["agg_whole_bucket"], after["expected_l1"]
    return (f"OBSERVED_DEFECT: {name}: {e['count']} raw edge(s) back after the rollback, but whole-bucket count={a['count']} "
            f"sum={a['sum']} velocity={after['velocity_bucket']} (raw bucket={after['raw']['bucket']!r}; "
            f"expected {e['count']}/{e['sum']}/{e['velocity']})")


def case_r5(eng, native, out):
    """delete_edge_temporal of a source's only edge in its bucket inside the caller's transaction, then ROLLBACK."""
    ts = 1_700_002_500
    out["ts"] = ts
    eng.create_edge_temporal(A, P, Bn, timestamp=ts, weight=2.0)
    out["before"] = stats(eng, native, A, ts)
    cur = eng.conn.cursor()
    try:
        cur.execute("START TRANSACTION")
        out["delete_returned"] = eng.delete_edge_temporal(A, P, Bn, ts)
        out["inside"] = stats(eng, native, A, ts)
        cur.execute("ROLLBACK")
    finally:
        cur.close()
    out["after_rollback"] = stats(eng, native, A, ts)
    out["verdict"] = restored_verdict("R5 rolled-back delete of the only edge", out["before"], out["inside"], out["after_rollback"])
    return out


def case_r5b(eng, native, out):
    """Two edges of one source in one bucket; one deleted inside the caller's transaction, then ROLLBACK."""
    ts = 1_700_003_100
    out["ts"] = ts
    eng.create_edge_temporal(A, P, Bn, timestamp=ts, weight=2.0)
    eng.create_edge_temporal(A, P, Bn, timestamp=ts + 1, weight=3.0)
    out["before"] = stats(eng, native, A, ts)
    cur = eng.conn.cursor()
    try:
        cur.execute("START TRANSACTION")
        out["delete_returned"] = eng.delete_edge_temporal(A, P, Bn, ts)
        out["inside"] = stats(eng, native, A, ts)
        cur.execute("ROLLBACK")
    finally:
        cur.close()
    out["after_rollback"] = stats(eng, native, A, ts)
    out["verdict"] = restored_verdict("R5b rolled-back delete of one of two edges", out["before"], out["inside"], out["after_rollback"])
    return out


def case_r6(eng, native, out):
    """delete_node of the target inside the caller's transaction (Eraser.EraseNodeIds -> TemporalIndex.EraseNodes ->
    RemoveTemporalRow), then ROLLBACK."""
    ts = 1_700_003_700
    out["ts"] = ts
    eng.create_edge_temporal(A, P, Bn, timestamp=ts, weight=2.0)
    out["before"] = stats(eng, native, A, ts)
    cur = eng.conn.cursor()
    try:
        cur.execute("START TRANSACTION")
        try:
            out["delete_node"] = repr(eng.delete_node(Bn, graph=None))
        except Exception as e:  # noqa: BLE001
            out["delete_node"] = f"{type(e).__name__}: {e}"
        out["inside"] = stats(eng, native, A, ts)
        cur.execute("ROLLBACK")
    finally:
        cur.close()
    out["after_rollback"] = stats(eng, native, A, ts)
    out["verdict"] = restored_verdict("R6 rolled-back node erasure", out["before"], out["inside"], out["after_rollback"])
    return out


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    obs = {"model": "temporal", "probe": "temporal_rollback_counters"}
    try:
        obs["schema"] = ensure_schema(eng)
        obs["adjacency_indexed"] = str(native.classMethodValue("Graph.KG.Adjacency", "Indexed"))
        cases = {}
        obs["cases"] = cases
        for name, fn in (("R1_refused_changeset", case_r1), ("R2_caller_rollback_commit", case_r2),
                         ("R3_caller_rollback_direct", case_r3), ("R4_throw_in_changeset", case_r4),
                         ("R5_rollback_delete_only_edge", case_r5), ("R5b_rollback_delete_one_of_two", case_r5b),
                         ("R6_rollback_node_erasure", case_r6)):
            reset(eng, native)
            out = cases.setdefault(name, {})   # filled as the case runs, so a crash keeps what it saw
            try:
                seed(eng)
                fn(eng, native, out)
            except Exception as e:  # noqa: BLE001
                out["verdict"] = f"INCONCLUSIVE: {type(e).__name__}: {e}"
                out["trace"] = traceback.format_exc()
        defects = [f"{k}: {c['verdict']}" for k, c in cases.items() if c["verdict"].startswith("OBSERVED_DEFECT")]
        if defects:
            obs["verdict"] = "OBSERVED_DEFECT: " + "; ".join(defects)
        elif all(c["verdict"].startswith("OBSERVED_AS_EXPECTED") for c in cases.values()):
            obs["verdict"] = "OBSERVED_AS_EXPECTED: every rollback left nothing"
        else:
            obs["verdict"] = "INCONCLUSIVE: " + "; ".join(f"{k}: {c['verdict']}" for k, c in cases.items())
    finally:
        try:
            reset(eng, native)
        except Exception:  # noqa: BLE001
            pass
        path = record("temporal_rollback_counters", obs)
    print(f"{obs.get('verdict', 'INCONCLUSIVE: probe did not finish')} [{path}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
