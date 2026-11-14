#!/usr/bin/env python3
"""Probe (temporal model, Q4): do temporal writes create endpoint node rows without ledger records, and what
does ledger.verify() then report? (F4)

Expected (model L1-GOV): the decision recorded in commit 43efd473 (2026-10-19, "decided with Tom"): "temporal writes
still create no revisions (spec 213 US11), and a temporal mirror is no longer an unrecorded write" — after a
temporal write, verify() stays "equal" and the head does not move. The model proves this for endpoints the ledger
already knows (any graph: read_canonical keys nodes by id) and for temporal-only predicates
(lemma_temporal_write_keeps_verify), and exhibits the violation for a new endpoint id
(witness_direct_temporal_write_makes_verify_diverge, witness_ledger_temporal_op_makes_verify_diverge,
witness_changeset_op_order_decides).

Cases (each on a freshly reset, seeded ledger: create_node a, create_node b):
  C0 control  create_edge_temporal(a, P, b, graph="probe_g")       known ids, named graph  -> equal expected
  C1 control  set_temporal_structural(Q, False); create_edge_temporal(a, Q, new)  opted out -> equal expected
  V1          create_edge_temporal(a, P, new)                       new endpoint id
  V2          ledger changeset [create_temporal_edge(a, P, new)]
  V3          ledger changeset [create_temporal_edge(a, P, new), upsert_node(new)]
  V4          ledger changeset [create_temporal_edge(a, P, new), create_node(new)]   vs   [create_node(new2), create_temporal_edge(a, P, new2)]
  V5          ledger strict mode on; create_edge_temporal(a, P, new)  (create_edge_temporal is not strict-guarded)
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import connect, engine, ensure_schema, reset, record, ledger_records  # noqa: E402

TS = 1_700_000_100
P, Q = "PROBE_EP", "PROBE_EP_ONLY"
A, Bn = "probe:ep:a", "probe:ep:b"


def seed(eng):
    from iris_vector_graph.ledger.changeset import Changeset

    eng.ledger.enable()
    cs = Changeset(actor="probe", actor_type="system", message="endpoint probe seed")
    cs.create_node(A)
    cs.create_node(Bn)
    eng.ledger.commit(cs)


def nodes_named(eng, nid):
    cur = eng.conn.cursor()
    try:
        cur.execute("SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id = ?", [nid])
        return [list(r) for r in cur.fetchall()]
    finally:
        cur.close()


def rev_count(eng):
    cur = eng.conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM Graph_KG.ledger_revisions")
        return int(cur.fetchone()[0])
    finally:
        cur.close()


def verify(eng):
    rep = eng.ledger.verify()
    return {
        "result": rep.result,
        "classification": rep.classification,
        "differences": [
            {"kind": d.entity_kind, "id": d.entity_id, "attr": d.attr, "before": d.before, "after": d.after}
            for d in rep.differences
        ],
    }


def ops_of_head(native):
    recs = ledger_records(native)
    if not recs:
        return []
    last = max(seq for seq, _ in recs)
    return [recs[k][:3] for k in sorted(recs) if k[0] == last]


def judge(name, before, after, expect_equal=True, new_id=None, node_rows=None):
    """Review R1-12: a divergence counts as F4 only when every difference is the new endpoint's node and its node
    row exists; a divergence about anything else is INCONCLUSIVE."""
    if before["result"] != "equal":
        return f"INCONCLUSIVE: {name}: verify was not equal before the write ({before['result']})"
    if after["result"] == "equal":
        return f"OBSERVED_AS_EXPECTED: {name}: verify stays equal"
    ids = sorted({d["id"] for d in after["differences"]})
    kinds = sorted({d["kind"] for d in after["differences"]})
    if new_id is None:
        return f"OBSERVED_DEFECT: {name}: verify {after['result']} ({after['classification']}) on {ids}"
    if ids != [new_id] or kinds != ["node"]:
        return f"INCONCLUSIVE: {name}: verify diverges on {ids} ({kinds}), not only on the new endpoint's node"
    if node_rows is not None and not node_rows:
        return f"INCONCLUSIVE: {name}: verify names {new_id} but no Graph_KG.nodes row for it was found"
    return (f"OBSERVED_DEFECT: {name}: verify {after['result']} ({after['classification']}) only on the new endpoint "
            f"node {new_id}, whose row the temporal write created")


def case_c0(eng, native):
    before = verify(eng)
    n = rev_count(eng)
    eng.create_edge_temporal(A, P, Bn, timestamp=TS, graph="probe_g")
    after = verify(eng)
    return {"before": before, "after": after, "revisions_added": rev_count(eng) - n,
            "node_rows_b": nodes_named(eng, Bn), "verdict": judge("C0 known endpoints, named graph", before, after)}


def case_c1(eng, native):
    new = "probe:ep:new:optout"
    eng.set_temporal_structural(Q, False)
    before = verify(eng)
    eng.create_edge_temporal(A, Q, new, timestamp=TS)
    after = verify(eng)
    rows = nodes_named(eng, new)
    v = judge("C1 temporal-only predicate", before, after, new_id=new, node_rows=rows)
    if rows:
        v = f"OBSERVED_DEFECT: C1 the temporal-only write created node rows {rows} (ADR-0015)"
    return {"before": before, "after": after, "node_rows": rows, "verdict": v}


def case_v1(eng, native):
    new = "probe:ep:new:1"
    before = verify(eng)
    n = rev_count(eng)
    eng.create_edge_temporal(A, P, new, timestamp=TS)
    after = verify(eng)
    rows = nodes_named(eng, new)
    added = rev_count(eng) - n
    v = judge("V1 direct write, new endpoint", before, after, new_id=new, node_rows=rows)
    if added != 0:
        v = f"INCONCLUSIVE: V1: the direct temporal write added {added} revision(s)"
    return {"before": before, "after": after, "revisions_added": added, "node_rows": rows, "verdict": v}


def case_v2(eng, native):
    from iris_vector_graph.ledger.changeset import Changeset

    new = "probe:ep:new:2"
    before = verify(eng)
    cs = Changeset(actor="probe", actor_type="system", message="temporal op to a new endpoint")
    cs.create_temporal_edge(A, P, new, ts=TS, weight=1.0)
    eng.ledger.commit(cs)
    after = verify(eng)
    rows = nodes_named(eng, new)
    recs = ops_of_head(native)
    v = judge("V2 ledger temporal op, new endpoint", before, after, new_id=new, node_rows=rows)
    if any(r[0] == "create_node" for r in recs):
        v = "INCONCLUSIVE: V2: the revision records a create_node"
    return {"before": before, "after": after, "head_records": recs, "node_rows": rows, "verdict": v}


def case_v3(eng, native):
    from iris_vector_graph.ledger.changeset import Changeset

    new = "probe:ep:new:3"
    before = verify(eng)
    cs = Changeset(actor="probe", actor_type="system", message="temporal op then upsert of its endpoint")
    cs.create_temporal_edge(A, P, new, ts=TS, weight=1.0)
    cs.upsert_node(new)
    eng.ledger.commit(cs)
    after = verify(eng)
    recs = ops_of_head(native)
    rows = nodes_named(eng, new)
    recorded = any(r[0] == "create_node" and r[2] == new for r in recs)
    v = judge("V3 temporal op then upsert_node in one changeset", before, after, new_id=new, node_rows=rows)
    if recorded:
        v = "INCONCLUSIVE: V3: the upsert recorded a create_node for the endpoint"
    return {"before": before, "after": after, "head_records": recs, "node_rows": rows,
            "create_node_recorded": recorded, "verdict": v}


def case_v4(eng, native):
    from iris_vector_graph.ledger.changeset import Changeset

    new, new2 = "probe:ep:new:4", "probe:ep:new:5"
    out = {}
    cs = Changeset(actor="probe", actor_type="system", message="temporal op then create_node of its endpoint")
    cs.create_temporal_edge(A, P, new, ts=TS, weight=1.0)
    cs.create_node(new)
    refused_at, reason = None, ""
    try:
        eng.ledger.commit(cs)
        out["temporal_then_create"] = "committed"
    except Exception as e:  # noqa: BLE001
        out["temporal_then_create"] = f"{type(e).__name__}: {e}"
        refused_at, reason = getattr(e, "op_index", None), str(getattr(e, "reason", "") or e)
    out["refused_op_index"] = refused_at
    cs2 = Changeset(actor="probe", actor_type="system", message="create_node then the temporal op")
    cs2.create_node(new2)
    cs2.create_temporal_edge(A, P, new2, ts=TS + 1, weight=1.0)
    try:
        eng.ledger.commit(cs2)
        out["create_then_temporal"] = "committed"
    except Exception as e:  # noqa: BLE001
        out["create_then_temporal"] = f"{type(e).__name__}: {e}"
    out["after"] = verify(eng)
    differs = out["temporal_then_create"] != out["create_then_temporal"]
    if not differs:
        out["verdict"] = f"OBSERVED_AS_EXPECTED: V4 both orders -> {out['create_then_temporal']}"
    elif out["create_then_temporal"] != "committed" or refused_at != 1 or "node_exists" not in reason:
        # review R1-12: the defect is the create_node (op 1) refused as node_exists because op 0 wrote the node
        out["verdict"] = (f"INCONCLUSIVE: V4 the orders differ, but not as op 1 refused node_exists after op 0: "
                          f"{out['temporal_then_create'][:120]} / {out['create_then_temporal'][:80]}")
    else:
        out["verdict"] = (f"OBSERVED_DEFECT: V4 op order decides: [temporal, create_node] -> op 1 refused node_exists; "
                          f"[create_node, temporal] -> committed")
    return out


def case_v5(eng, native):
    new = "probe:ep:new:strict"
    before = verify(eng)
    eng.ledger.set_strict(True)
    try:
        try:
            eng.create_edge_temporal(A, P, new, timestamp=TS)
            wrote = "returned"
        except Exception as e:  # noqa: BLE001
            wrote = f"{type(e).__name__}: {e}"
        after = verify(eng)
    finally:
        eng.ledger.set_strict(False)
    rows = nodes_named(eng, new)
    v = judge("V5 strict mode, new endpoint", before, after, new_id=new, node_rows=rows)
    if wrote != "returned":
        v = f"OBSERVED_AS_EXPECTED: V5 strict mode refused the temporal write ({wrote[:120]})" if not rows else \
            f"INCONCLUSIVE: V5 the write raised ({wrote[:120]}) but a node row exists"
    return {"before": before, "write": wrote, "after": after, "node_rows": rows, "verdict": v}


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    obs = {"model": "temporal", "probe": "temporal_endpoint_nodes_verify"}
    try:
        obs["schema"] = ensure_schema(eng)
        obs["adjacency_indexed"] = str(native.classMethodValue("Graph.KG.Adjacency", "Indexed"))
        cases = {}
        for name, fn in (("C0_known_endpoints_named_graph", case_c0), ("C1_optout", case_c1),
                         ("V1_direct_new_endpoint", case_v1), ("V2_ledger_new_endpoint", case_v2),
                         ("V3_upsert_after_temporal", case_v3), ("V4_op_order", case_v4),
                         ("V5_strict_mode", case_v5)):
            reset(eng, native)
            try:
                seed(eng)
                cases[name] = fn(eng, native)
            except Exception as e:  # noqa: BLE001
                cases[name] = {"verdict": f"INCONCLUSIVE: {type(e).__name__}: {e}", "trace": traceback.format_exc()}
        obs["cases"] = cases
        controls_ok = all(cases[k]["verdict"].startswith("OBSERVED_AS_EXPECTED")
                          for k in ("C0_known_endpoints_named_graph", "C1_optout"))
        defects = [f"{k}: {c['verdict']}" for k, c in cases.items() if c["verdict"].startswith("OBSERVED_DEFECT")]
        if obs["adjacency_indexed"] != "1":
            obs["verdict"] = "INCONCLUSIVE: the adjacency functional index is not declared (no AssertTemporalRow)"
        elif not controls_ok:
            obs["verdict"] = "INCONCLUSIVE: a control case did not stay equal: " + "; ".join(
                cases[k]["verdict"] for k in ("C0_known_endpoints_named_graph", "C1_optout"))
        elif defects:
            obs["verdict"] = "OBSERVED_DEFECT: " + "; ".join(defects)
        else:
            obs["verdict"] = "OBSERVED_AS_EXPECTED: verify stayed equal in every case"
    finally:
        try:
            reset(eng, native)
        except Exception:  # noqa: BLE001
            pass
        path = record("temporal_endpoint_nodes_verify", obs)
    print(f"{obs.get('verdict', 'INCONCLUSIVE: probe did not finish')} [{path}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
