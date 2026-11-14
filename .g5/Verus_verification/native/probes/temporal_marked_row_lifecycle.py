#!/usr/bin/env python3
"""Probe (temporal model, Q2): the marked structural row (ADR-0009, spec 254 amendment) and the temporal-only
opt-out (ADR-0015), including the toggle back with existing data (F8).

Expected (model L1-ROW, lemmas lemma_marked_row_goes_with_last_timestamp, lemma_temporal_ops_keep_explicit_rows,
lemma_explicit_create_clears_marker, lemma_optout_write_writes_no_row, lemma_purge_leaves_registered_rows):
  K1  a temporal write of a structural predicate asserts a row marked {"temporal": true}; deleting one of two
      timestamps keeps it; deleting the last removes it.
  K2  an explicit create_edge after the temporal write clears the marker; deleting the last timestamp keeps the row.
  K3  a registered (temporal-only) predicate's write creates no row and no node.
  K4  registered after its row exists: purge of every timestamp keeps the row (ADR-0015 decided); delete of the
      last timestamp removes it (DeleteTemporalEdge does not read the registry) — the model calls the asymmetry an
      open question, so both outcomes are recorded and the case passes when it matches the code reading.
  F8  register, purge every timestamp, opt back in: L1-ROW says a marked row of a structural predicate has a
      timestamp. The model (witness_optin_strands_marked_row) predicts a stranded marked row that delete, purge,
      drop (refused for a structural predicate) and backfill all leave.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import connect, engine, ensure_schema, reset, record  # noqa: E402

TS = 1_700_000_100
P, Q = "PROBE_ML", "PROBE_ML_OPT"


def rows(eng, s, p, o):
    cur = eng.conn.cursor()
    try:
        cur.execute("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ?", [s, p, o])
        out = []
        for (q,) in cur.fetchall():
            try:
                d = json.loads(q) if isinstance(q, str) and q else (dict(q) if q else {})
            except Exception:  # noqa: BLE001
                d = {"_raw": str(q)}
            out.append(d)
        return out
    finally:
        cur.close()


def marked(rs):
    return [r for r in rs if r.get("temporal") is True]


def node_count(eng, nid):
    cur = eng.conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", [nid])
        return int(cur.fetchone()[0])
    finally:
        cur.close()


def window(eng, s, p):
    return eng.get_edges_in_window(s, p, 0, 2_000_000_000)


def case_k1(eng):
    s, o = "probe:ml:k1:s", "probe:ml:k1:o"
    out = {}
    eng.create_edge_temporal(s, P, o, timestamp=TS)
    eng.create_edge_temporal(s, P, o, timestamp=TS + 10)
    out["after_two_writes"] = rows(eng, s, P, o)
    eng.delete_edge_temporal(s, P, o, TS)
    out["after_first_delete"] = rows(eng, s, P, o)
    eng.delete_edge_temporal(s, P, o, TS + 10)
    out["after_last_delete"] = rows(eng, s, P, o)
    ok = (len(marked(out["after_two_writes"])) == 1 and len(marked(out["after_first_delete"])) == 1
          and out["after_last_delete"] == [])
    out["verdict"] = ("OBSERVED_AS_EXPECTED: K1 marked row asserted, kept while a timestamp remains, removed with the last"
                      if ok else f"OBSERVED_DEFECT: K1 {out}")
    return out


def case_k2(eng):
    s, o = "probe:ml:k2:s", "probe:ml:k2:o"
    out = {}
    eng.create_edge_temporal(s, P, o, timestamp=TS)
    eng.create_edge(s, P, o)
    out["after_create_edge"] = rows(eng, s, P, o)
    eng.delete_edge_temporal(s, P, o, TS)
    out["after_last_delete"] = rows(eng, s, P, o)
    eng.create_edge_temporal(s, P, o, timestamp=TS + 5)
    eng.purge_raw_before(TS + 6, retire_bare_nodes=False)
    out["after_purge"] = rows(eng, s, P, o)
    ok = (len(out["after_create_edge"]) == 1 and not marked(out["after_create_edge"])
          and len(out["after_last_delete"]) == 1 and len(out["after_purge"]) == 1
          and not marked(out["after_purge"]))
    out["verdict"] = ("OBSERVED_AS_EXPECTED: K2 adoption cleared the marker and the explicit row outlived delete and purge"
                      if ok else f"OBSERVED_DEFECT: K2 {out}")
    return out


def case_k3(eng):
    s, o = "probe:ml:k3:s", "probe:ml:k3:o-new"
    eng.set_temporal_structural(Q, False)
    eng.create_edge_temporal(s, Q, o, timestamp=TS)
    out = {"rows": rows(eng, s, Q, o), "target_node_rows": node_count(eng, o), "window": window(eng, s, Q)}
    ok = out["rows"] == [] and out["target_node_rows"] == 0 and len(out["window"]) == 1
    out["verdict"] = ("OBSERVED_AS_EXPECTED: K3 temporal-only write: no row, no node, temporal edge readable"
                      if ok else f"OBSERVED_DEFECT: K3 {out}")
    return out


def case_k4(eng):
    out = {}
    s, o = "probe:ml:k4d:s", "probe:ml:k4d:o"
    eng.create_edge_temporal(s, P, o, timestamp=TS)
    eng.set_temporal_structural(P, False)
    eng.delete_edge_temporal(s, P, o, TS)
    out["delete_path_rows"] = rows(eng, s, P, o)
    eng.set_temporal_structural(P, True)
    s2, o2 = "probe:ml:k4p:s", "probe:ml:k4p:o"
    eng.create_edge_temporal(s2, P, o2, timestamp=TS)
    eng.set_temporal_structural(P, False)
    eng.purge_raw_before(TS + 1, retire_bare_nodes=False)
    out["purge_path_rows"] = rows(eng, s2, P, o2)
    out["purge_path_window"] = window(eng, s2, P)
    eng.set_temporal_structural(P, True)
    matches_code = out["delete_path_rows"] == [] and len(marked(out["purge_path_rows"])) == 1
    out["verdict"] = ("OBSERVED_AS_EXPECTED: K4 registered predicate: delete retracts the old row, purge keeps it "
                      "(the open delete/purge asymmetry, as the model reads the code)" if matches_code
                      else f"INCONCLUSIVE: K4 differs from the code reading: {out}")
    return out


def case_f8(eng):
    s, o = "probe:ml:f8:s", "probe:ml:f8:o"
    out = {}
    eng.create_edge_temporal(s, P, o, timestamp=TS)
    out["start"] = rows(eng, s, P, o)
    eng.set_temporal_structural(P, False)
    out["purge"] = str(eng.purge_raw_before(TS + 1, retire_bare_nodes=False))
    out["after_purge_while_registered"] = rows(eng, s, P, o)
    eng.set_temporal_structural(P, True)
    out["structural_again"] = eng.get_temporal_structural(P)
    out["window_after_optin"] = window(eng, s, P)
    out["rows_after_optin"] = rows(eng, s, P, o)
    # every temporal maintenance path
    out["delete_returned"] = eng.delete_edge_temporal(s, P, o, TS)
    out["purge_again"] = str(eng.purge_raw_before(2_000_000_000, retire_bare_nodes=False))
    try:
        out["drop"] = str(eng.drop_temporal_structural_rows(P))
    except Exception as e:  # noqa: BLE001
        out["drop"] = f"{type(e).__name__}: {e}"
    try:
        out["backfill"] = eng.backfill_temporal_structural_rows(P)
    except Exception as e:  # noqa: BLE001
        out["backfill"] = f"{type(e).__name__}: {e}"
    out["rows_after_maintenance"] = rows(eng, s, P, o)
    if len(marked(out["start"])) != 1:
        out["verdict"] = "INCONCLUSIVE: F8 no marked row was asserted at the start"
    elif out["window_after_optin"]:
        out["verdict"] = "INCONCLUSIVE: F8 the purge left a timestamp"
    elif not out["purge"].startswith("PurgeResult(deleted=1"):
        out["verdict"] = f"INCONCLUSIVE: F8 the purge did not delete exactly the one timestamp ({out['purge']})"
    elif out["delete_returned"] is not False or "still structural" not in out["drop"]:
        # review R1-12: the stranding is the drop refused because the predicate is structural, and delete finding nothing
        out["verdict"] = (f"INCONCLUSIVE: F8 maintenance did not behave as the model reads it "
                          f"(delete={out['delete_returned']!r}, drop={out['drop'][:100]})")
    elif len(marked(out["rows_after_maintenance"])) == 1:
        out["verdict"] = ("OBSERVED_DEFECT: F8 a marked row of a structural predicate with no timestamp survives delete, purge, "
                          f"drop ({out['drop'][:80]}) and backfill (L1-ROW; decision Q4 open)")
    else:
        out["verdict"] = "OBSERVED_AS_EXPECTED: F8 no stranded marked row"
    return out


def main() -> int:
    conn, native = connect()
    eng = engine(conn)
    obs = {"model": "temporal", "probe": "temporal_marked_row_lifecycle"}
    try:
        obs["schema"] = ensure_schema(eng)
        obs["adjacency_indexed"] = str(native.classMethodValue("Graph.KG.Adjacency", "Indexed"))
        cases = {}
        for name, fn in (("K1_marked_row", case_k1), ("K2_adoption", case_k2), ("K3_optout_write", case_k3),
                         ("K4_delete_vs_purge_registered", case_k4), ("F8_optin_strands", case_f8)):
            reset(eng, native)
            try:
                cases[name] = fn(eng)
            except Exception as e:  # noqa: BLE001
                cases[name] = {"verdict": f"INCONCLUSIVE: {type(e).__name__}: {e}", "trace": traceback.format_exc()}
        obs["cases"] = cases
        defects = [f"{k}: {c['verdict']}" for k, c in cases.items() if c["verdict"].startswith("OBSERVED_DEFECT")]
        if obs["adjacency_indexed"] != "1":
            obs["verdict"] = "INCONCLUSIVE: the adjacency functional index is not declared"
        elif defects:
            obs["verdict"] = "OBSERVED_DEFECT: " + "; ".join(defects)
        elif all(c["verdict"].startswith("OBSERVED_AS_EXPECTED") for c in cases.values()):
            obs["verdict"] = "OBSERVED_AS_EXPECTED: every case"
        else:
            obs["verdict"] = "INCONCLUSIVE: " + "; ".join(f"{k}: {c['verdict']}" for k, c in cases.items())
    finally:
        try:
            reset(eng, native)
        except Exception:  # noqa: BLE001
            pass
        path = record("temporal_marked_row_lifecycle", obs)
    print(f"{obs.get('verdict', 'INCONCLUSIVE: probe did not finish')} [{path}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
