#!/usr/bin/env python3
"""O1 bindings: graph-name refusal, NUL stripping, the default graph's two keys, and the Python mirror (Q4, Q5).

L1 (ADR-0003, CONTEXT.md:27-58; model graph_structure.rs §1): a name a store cannot represent ("0", any control
character) is refused before any write; $Char(0) is stripped, so "g" + NUL is the graph "g"; the default graph is
^KG key 0 and ledger key $Char(1), and a scoped write lands only under its own graph's key in each store.

Cases (each judged from L1, not from the code):
  K1 create_edge(graph="0")        refused, nothing written                     (theorem_refusals)
  K2 create_edge(graph="\\x01")     refused, nothing written                     (theorem_refusals)
  K3 create_edge(graph="\\x85")     refused, nothing written, IF IRIS's $ZStrip "C" class holds 0x85 (premise P-CTRL,
                                   observed here through GraphKey.ForName); the Python mirror admits 0x85
                                   (witness_python_mirror_admits_c1_control)
  K4 create_edge(graph="g5k") then create_edge(graph="g5k\\x00") then delete_edge(graph="g5k"): one graph, so the
     second create is a duplicate, and after the delete no row and no ^KG entry remain
     (witness_raw_sql_name_splits_one_index_graph predicts two rows, one ^KG entry, then a row with no entry)
  K5 ledger create_rel in the default graph: ^KG("out", 0, ...) and ^IVG.Ledger("tuple", ..., $Char(1)) are set, and
     neither store holds the edge under the other store's default key (theorem_default_keys_never_cross)
Public entry points: engine.create_edge / delete_edge, engine.ledger.commit, GraphKey.ForName over the Native API (a
pure function, used to observe P-CTRL). Globals and SQL rows are read to observe.
"""
from __future__ import annotations

from graph_structure_common import connect, defined, engine, ensure_schema, err, finish, reset, sql_all

NAME = "graph_structure_keys"
S, P, O = "g5k:a", "G5K_T", "g5k:b"


def edge_rows(conn, s=S, p=P, o=O):
    return sql_all(conn, "SELECT graph_id, ekey FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ?", [s, p, o])


def node_rows(conn, graph):
    return sql_all(conn, "SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id IN (?, ?) AND graph_id = ?", [S, O, graph])


def safe_reset(eng, native, notes: list):
    try:
        reset(eng, native)
    except Exception as e:  # noqa: BLE001
        notes.append(err(e))


def canon(g):
    return ("" if g is None else str(g)).replace("\x00", "")


def try_create(eng, graph):
    try:
        return {"returned": eng.create_edge(S, P, O, graph=graph)}
    except Exception as e:  # noqa: BLE001
        return {"raised": err(e)}


def ctrl_premise(native) -> dict:
    """P-CTRL as observed: which code points GraphKey.Validate refuses (ForName throws on a refusal)."""
    out = {}
    for cp in (0x01, 0x1F, 0x7F, 0x80, 0x85, 0x9F, 0xA0):
        try:
            native.classMethodValue("Graph.KG.GraphKey", "ForName", "x" + chr(cp))
            out[hex(cp)] = "accepted"
        except Exception as e:  # noqa: BLE001
            out[hex(cp)] = "refused: " + str(e)[:120]
    return out


def judge_refusal(res: dict, rows_before: list, rows_after: list, kg_before: int, kg_after: int) -> tuple[str, str]:
    refused = "raised" in res or res.get("returned") is False
    unchanged = rows_before == rows_after and kg_before == kg_after
    if refused and unchanged:
        return "OBSERVED_AS_EXPECTED", "refused, nothing written"
    if not unchanged:
        return "OBSERVED_DEFECT", f"a write landed: rows {rows_before} -> {rows_after}, ^KG $Data {kg_before} -> {kg_after}"
    return "OBSERVED_DEFECT", f"not refused (returned {res.get('returned')}) though nothing visible changed"


def judge_k4(after_two: list, after_delete: list, kg_after_delete: int) -> tuple[str, str]:
    same_graph_rows = [r for r in after_two if canon(r[0]) == "g5k"]
    if len(same_graph_rows) == 1 and not after_delete and kg_after_delete == 0:
        return "OBSERVED_AS_EXPECTED", "one graph: duplicate refused, delete leaves nothing"
    if len(same_graph_rows) >= 2 or (after_delete and kg_after_delete == 0):
        return "OBSERVED_DEFECT", (f"graph 'g5k' and 'g5k'+NUL got {len(same_graph_rows)} rows; after delete_edge(graph='g5k') "
                                   f"rows {after_delete} remain with ^KG $Data {kg_after_delete}")
    return "INCONCLUSIVE", f"rows after two creates {after_two}, after delete {after_delete}, ^KG {kg_after_delete}"


def self_check() -> dict:
    a, _ = judge_k4([["g5k", 0], ["g5k\x00", 0]], [["g5k\x00", 0]], 0)
    b, _ = judge_k4([["g5k", 0]], [], 0)
    c, _ = judge_refusal({"returned": True}, [], [["0", 0]], 0, 1)
    d, _ = judge_refusal({"raised": {}}, [], [], 0, 0)
    return {"k4_defect": a, "k4_ok": b, "refusal_defect": c, "refusal_ok": d,
            "discriminates": a == "OBSERVED_DEFECT" and b == "OBSERVED_AS_EXPECTED" and c == "OBSERVED_DEFECT" and d == "OBSERVED_AS_EXPECTED"}


def main() -> None:
    obs = {"probe": NAME}
    conn, native = connect()
    eng = engine(conn)
    obs["schema"] = ensure_schema(eng)
    reset(eng, native)
    obs["p_ctrl"] = ctrl_premise(native)
    results = {}

    for label, graph, key in (("K1", "0", 0), ("K2", "\x01", "\x01"), ("K3", "\x85", "\x85")):
        rb = edge_rows(conn) + node_rows(conn, graph)
        kb = defined(native, "^KG", "out", key, S, P, O)
        res = try_create(eng, graph)
        ra = edge_rows(conn) + node_rows(conn, graph)
        ka = defined(native, "^KG", "out", key, S, P, O)
        v, why = judge_refusal(res, rb, ra, kb, ka)
        results[label] = {"graph": repr(graph), "result": res, "rows_before": rb, "rows_after": ra,
                          "kg_before": kb, "kg_after": ka, "verdict": v, "reason": why}
        safe_reset(eng, native, obs.setdefault("reset_errors", []))

    # K4: the NUL-padded name
    k4 = {"first": try_create(eng, "g5k"), "second": try_create(eng, "g5k\x00")}
    k4["rows_after_two"] = edge_rows(conn)
    k4["kg_after_two"] = defined(native, "^KG", "out", "g5k", S, P, O)
    try:
        k4["delete"] = {"returned": eng.delete_edge(S, P, O, graph="g5k")}
    except Exception as e:  # noqa: BLE001
        k4["delete"] = {"raised": err(e)}
    k4["rows_after_delete"] = edge_rows(conn)
    k4["kg_after_delete"] = defined(native, "^KG", "out", "g5k", S, P, O)
    try:
        k4["verify_g5k"] = eng.verify_graph("g5k")
    except Exception as e:  # noqa: BLE001
        k4["verify_g5k"] = err(e)
    k4["verdict"], k4["reason"] = judge_k4(k4["rows_after_two"], k4["rows_after_delete"], k4["kg_after_delete"])
    results["K4"] = k4
    safe_reset(eng, native, obs.setdefault("reset_errors", []))

    # K5: the default graph's keys in the two stores
    k5 = {}
    try:
        from iris_vector_graph.ledger import Changeset

        eng.ledger.enable()
        cs = Changeset(actor="g5-probe", actor_type="system", message="graph_structure K5")
        cs.create_node(S)
        cs.create_node(O)
        cs.create_relationship(S, P, O)
        eng.ledger.commit(cs)
        k5["kg_index_key"] = defined(native, "^KG", "out", 0, S, P, O)
        k5["kg_ledger_key"] = defined(native, "^KG", "out", "\x01", S, P, O)
        k5["ledger_ledger_key"] = defined(native, "^IVG.Ledger", "tuple", S, P, O, "\x01")
        k5["ledger_index_key"] = defined(native, "^IVG.Ledger", "tuple", S, P, O, 0)
        ok = k5["kg_index_key"] > 0 and k5["ledger_ledger_key"] > 0 and k5["kg_ledger_key"] == 0 and k5["ledger_index_key"] == 0
        k5["verdict"] = "OBSERVED_AS_EXPECTED" if ok else "OBSERVED_DEFECT"
        k5["reason"] = "each store holds the edge under its own default key only" if ok else f"keys observed {k5}"
    except Exception as e:  # noqa: BLE001
        k5["error"] = err(e)
        k5["verdict"], k5["reason"] = "INCONCLUSIVE", "ledger commit failed"
    results["K5"] = k5

    obs["cases"] = results
    sc = self_check()
    verdicts = {k: v["verdict"] for k, v in results.items()}
    defects = [k for k, v in verdicts.items() if v == "OBSERVED_DEFECT"]
    if defects:
        verdict, why = "OBSERVED_DEFECT", "; ".join(f"{k}: {results[k]['reason']}" for k in defects)
    elif all(v == "OBSERVED_AS_EXPECTED" for v in verdicts.values()):
        verdict, why = "OBSERVED_AS_EXPECTED", "refusals, NUL stripping and default-graph keys as L1 requires"
    else:
        verdict, why = "INCONCLUSIVE", str(verdicts)
    if not sc["discriminates"]:
        verdict, why = "INCONCLUSIVE", f"verdict self-check failed: {sc}"
    finish(NAME, verdict, why, obs, sc)


if __name__ == "__main__":
    main()
