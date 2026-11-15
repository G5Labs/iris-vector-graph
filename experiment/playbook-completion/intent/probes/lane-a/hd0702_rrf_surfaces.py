"""HD-0702 probe: do the reciprocal-rank-fusion surfaces rank the same two legs the same way?

Rules as written at the pin (each surface's own source/test, no common contract):
- engine kg_RRF_FUSE (iris_vector_graph/_engine/vector.py:1438-1446; pinned by
  tests/e2e/test_460_rrf_fuse_ivf_e2e.py:7-13): an item missing from a leg sits at rank len(leg) + c.
- SQL Graph_KG.kg_RRF_FUSE (iris_vector_graph/schema.py:2548-2550; read as a table, as PyOps.cls:388 does) and /hybridSearch (PyOps.FuseRanks): missing rank
  10^9 (about 0); its text leg is kg_TXT over the docs table, not a BM25 index.
- RRFFusion.fuse_results (iris_vector_graph/fusion.py:27-60) and CALL ivg.retrieve (translator.py:3342-3353): a missing
  item adds 0.
Discriminating construction (c = 60, the documented default): the vector leg holds 10 nodes (W rank 1, X rank 2, ...),
the text leg holds only Z (rank 1), which has no vector. Standard RRF: Z = 1/61 > X = 1/62. Engine rule:
X = 1/62 + 1/(60+1+60) = 0.024393 > Z = 1/(60+10+60) + 1/61 = 0.024085. So the order of X and Z tells the rules apart.
Oracle: per-surface reading (the working answer) holds when each surface matches its own formula; a single common rule
holds only if all surfaces order X and Z the same. Verdict: pass = each surface matches its own written rule (the
divergence is then a recorded fact for HD-0702, not a defect); fail = a surface deviates from its own rule.
Data: default graph (kg_KNN_VEC and the SQL procedure read only the default graph's kg_NodeEmbeddings; a named graph's
vectors would need a routed table, i.e. DDL), ids `ia0702:*`, docs rows with those ids, BM25 index `ia0702bm25`.
Precondition checked: kg_NodeEmbeddings holds no other rows and no other BM25 index exists, else `blocked`.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

CC = 60
IDS = ["ia0702:w", "ia0702:x"] + [f"ia0702:v{i}" for i in range(3, 11)]
Z = "ia0702:z"
BM = "ia0702bm25"


def vec(i):
    t = math.radians(8 * i)
    return [math.cos(t), math.sin(t), 0.0, 0.0]


def order(rows, a, b):
    ids = [r[0] for r in rows]
    if a not in ids or b not in ids:
        return None
    return a if ids.index(a) < ids.index(b) else b


def rule_missing(vec_leg, txt_leg, missing_v, missing_t):
    vr = {n: i + 1 for i, (n, _) in enumerate(vec_leg)}
    tr = {n: i + 1 for i, (n, _) in enumerate(txt_leg)}
    rows = []
    for n in set(vr) | set(tr):
        rows.append((n, 1 / (CC + vr.get(n, missing_v)) + 1 / (CC + tr.get(n, missing_t))))
    return sorted(rows, key=lambda r: -r[1])


def main() -> int:
    from iris_vector_graph.fusion import RRFFusion

    c = C.conn()
    e = C.engine(c)
    others = c.sql("SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings WHERE NOT (node_id %STARTSWITH 'ia0702:')")[0][0]
    bm_list = str(c.call("Graph.KG.BM25Index", "List") or "")
    if others or (bm_list and bm_list != "None"):
        C.verdict("blocked", f"shared default-graph state present: {others} other vectors, BM25 indexes {bm_list!r}")
        c.close()
        return 0
    reg_before = c.sql("SELECT * FROM Graph_KG.embedding_registry")
    failures = []
    try:
        for i, nid in enumerate(IDS):
            e.create_node(nid, labels=["IA0702"], properties={"name": f"alpha {i}"})
            e.store_embedding(nid, vec(i))
            c.sql("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES ('', ?, ?)", nid, f"alpha {i}")
        e.create_node(Z, labels=["IA0702"], properties={"name": "zebra"})
        c.sql("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES ('', ?, ?)", Z, "zebra")
        e.bm25_build(BM, ["name"])
        q = vec(0)
        vec_leg = e.kg_KNN_VEC(json.dumps(q), k=10)
        txt_leg = e.bm25_search(BM, "zebra", k=5)
        C.obs(step="legs", vector=vec_leg, text=txt_leg, leg_index=e._fusion_leg_index(("ivf", "hnsw"), ""))

        eng = e.kg_RRF_FUSE(k=11, k1=10, k2=5, c=CC, query_vector=json.dumps(q), query_text="zebra")
        eng_expected = rule_missing(vec_leg, txt_leg, len(vec_leg) + CC, len(txt_leg) + CC)
        C.obs(step="engine_kg_RRF_FUSE", rows=[(r[0], round(r[1], 9)) for r in eng],
              x_vs_z=order(eng, "ia0702:x", Z))
        if [r[0] for r in eng][:3] != [r[0] for r in eng_expected][:3] or any(
                abs(a[1] - b[1]) > 1e-9 for a, b in zip(sorted(eng), sorted(eng_expected))):
            failures.append("engine kg_RRF_FUSE deviates from its own len+c rule")

        rrf = RRFFusion.fuse_results([vec_leg, txt_leg], c=CC)
        std = rule_missing(vec_leg, txt_leg, math.inf, math.inf)
        C.obs(step="RRFFusion", rows=[(n, round(s, 9)) for n, s in rrf], x_vs_z=order(rrf, "ia0702:x", Z))
        if any(abs(dict(rrf)[n] - s) > 1e-12 for n, s in std):
            failures.append("RRFFusion deviates from standard RRF")

        try:
            sql_rows = c.sql("SELECT id, rrf, vs, ts FROM Graph_KG.kg_RRF_FUSE(?, ?, ?, ?, ?, ?, ?)", 11, 10, 5, CC, json.dumps(q), "zebra", "")
            sql_rows = [(str(r[0]), float(r[1])) + tuple(r[2:]) for r in sql_rows]
            C.obs(step="SQL_kg_RRF_FUSE", rows=[(r[0], round(r[1], 9)) for r in sql_rows],
                  x_vs_z=order(sql_rows, "ia0702:x", Z))
        except Exception as ex:  # noqa: BLE001
            sql_rows = None
            C.obs(step="SQL_kg_RRF_FUSE", error=str(ex)[:300])
        computed_sql = rule_missing(vec_leg, txt_leg, 10**9, 10**9)
        C.obs(step="SQL_rule_on_same_legs_computed_not_live", x_vs_z=order(computed_sql, "ia0702:x", Z))
        orders = {"engine": order(eng, "ia0702:x", Z), "RRFFusion": order(rrf, "ia0702:x", Z),
                  "SQL": order(sql_rows, "ia0702:x", Z) if sql_rows else None}
        C.obs(step="summary", x_before_z_by_surface=orders,
              surfaces_agree=len({v for v in orders.values() if v}) == 1)
    finally:
        try:
            e.bm25_drop(BM)
        except Exception as ex:  # noqa: BLE001
            C.obs(cleanup_error=str(ex)[:200])
        c.sql("DELETE FROM Graph_KG.docs WHERE id %STARTSWITH 'ia0702:'")
        c.sql("DELETE FROM Graph_KG.kg_NodeEmbeddings WHERE node_id %STARTSWITH 'ia0702:'")
        for nid in IDS + [Z]:
            try:
                e.delete_node(nid)
            except Exception as ex:  # noqa: BLE001
                C.obs(cleanup_error=f"{nid}: {str(ex)[:200]}")
        reg_after = c.sql("SELECT * FROM Graph_KG.embedding_registry")
        C.obs(step="cleanup", registry_unchanged=reg_before == reg_after,
              nodes_left=c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'ia0702:'"),
              vectors_left=c.sql("SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings WHERE node_id %STARTSWITH 'ia0702:'"),
              docs_left=c.sql("SELECT COUNT(*) FROM Graph_KG.docs WHERE id %STARTSWITH 'ia0702:'"),
              bm25_defined=c.o.isDefined("^BM25Idx", BM))
        c.close()
    if failures:
        C.verdict("fail", "; ".join(failures))
    else:
        C.verdict("pass", "each surface follows its own written rule; the engine orders X before Z, the standard rule "
                  "Z before X (see summary)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
