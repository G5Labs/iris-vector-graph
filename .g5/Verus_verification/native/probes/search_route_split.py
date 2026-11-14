#!/usr/bin/env python3
"""O3 / F9 — claiming kg_NodeEmbeddings after a model already has its own default-graph route.

Model: search.rs witness_claim_after_route_splits_pair (W-O3c); theorem_store_routes_and_refuses (one
route per pair is kept by store_embedding itself). L1 (4.0.0 routing, CHANGELOG "routed tables, one
per (graph_id, model_key)"; FR-011 "one graph's vectors split across both" is the failure it exists to
prevent): every vector stored for a (graph, model) pair is read back by that pair, and one registry
row answers the pair.

Sequence (public entry points only): initialize_schema by an engine with no embedding_config (the
kg_NodeEmbeddings row is adopted, model unknown); an engine configured for model A stores a default-
graph vector (A has no row, so a kg_emb_ route is created for ('', A)); set_embedding_identity claims
kg_NodeEmbeddings for A (what initialize_schema does for an A-configured engine); A reads the vector
back with get_embedding. The registry is read with SELECT for the observation only.
"""
from search_common import connect, engine, ensure_schema, reset, say

MODEL = "g5probe-model-a"
NODE = "g5p:route:1"
# Probe-run premises (review R1-12): the vector width is the one recorded for kg_NodeEmbeddings at the start
# (768 on this arm; the first run's hard-coded width 4 was refused before the case under test), and the run
# needs one DB-API connection plus the native handle on it (Community Edition's connection limit).


def registry_rows(conn) -> list:
    cur = conn.cursor()
    try:
        cur.execute("SELECT table_name, graph_id, model_key, mechanism, dimension FROM Graph_KG.embedding_registry")
        return [tuple(r) for r in cur.fetchall()]
    finally:
        cur.close()


def main() -> int:
    from iris_vector_graph.embedding_identity import identity_from_config, normalize_model_key

    conn, native = connect()
    eng0 = engine(conn)
    data = {"schema": ensure_schema(eng0)}
    reset(eng0, native)
    data["schema_after_reset"] = ensure_schema(eng0)
    key = normalize_model_key(MODEL)
    rows0 = registry_rows(conn)
    legacy0 = [r for r in rows0 if r[0] == "kg_NodeEmbeddings" and (r[1] or "") == ""]
    data["registry_initial"] = rows0
    if not legacy0 or legacy0[0][2] not in (None, ""):
        say("search_route_split", "INCONCLUSIVE", f"kg_NodeEmbeddings is not adopted-unknown at start: {legacy0}", data)
        return 0
    if legacy0[0][4] in (None, ""):
        say("search_route_split", "INCONCLUSIVE", f"kg_NodeEmbeddings has no recorded width: {legacy0}", data)
        return 0
    width = int(legacy0[0][4])
    vec = [round(0.11 + 0.001 * i, 6) for i in range(width)]
    data["width"] = width
    eng0.create_node(NODE, labels=["Doc"])
    try:
        eng_a = engine(conn, embedding_config=MODEL, embedding_dimension=width)
        data["stored"] = eng_a.store_embedding(NODE, vec)
    except Exception as e:
        say("search_route_split", "INCONCLUSIVE", f"engine with embedding_config or store_embedding refused: {e!r}"[:300], data)
        return 0
    rows1 = registry_rows(conn)
    data["registry_after_store"] = rows1
    routes_a = [r for r in rows1 if (r[1] or "") == "" and r[2] == key]
    if not any(str(r[0]).startswith("kg_emb_") for r in routes_a):
        say("search_route_split", "INCONCLUSIVE", f"no kg_emb_ route was created for ('', {key!r}): {routes_a}", data)
        return 0
    data["read_before_claim"] = eng_a.get_embedding(NODE) is not None
    try:
        data["claimed"] = str(eng_a.set_embedding_identity(identity_from_config(MODEL, dimension=width), "kg_NodeEmbeddings"))
    except Exception as e:
        say("search_route_split", "INCONCLUSIVE", f"set_embedding_identity refused: {e!r}"[:300], data)
        return 0
    eng_a.invalidate_route_cache()
    rows2 = registry_rows(conn)
    data["registry_after_claim"] = rows2
    answering = [r for r in rows2 if (r[1] or "") == "" and r[2] == key]
    got = eng_a.get_embedding(NODE)
    data["read_after_claim"] = None if got is None else got.get("embedding")
    data["rows_answering_pair"] = answering
    reset(eng0, native)

    # expected from L1: the stored vector is read back by its pair, and one row answers the pair
    ok_read = got is not None and [round(x, 4) for x in got.get("embedding", [])] == [round(x, 4) for x in vec]
    if ok_read and len(answering) == 1:
        say("search_route_split", "OBSERVED_AS_EXPECTED", "the pair still reads its vector and one row answers it", data)
    else:
        say("search_route_split", "OBSERVED_DEFECT",
            f"after claiming kg_NodeEmbeddings for {key!r}, {len(answering)} registry rows answer ('', {key!r}) and "
            f"get_embedding({NODE!r}) returns {'nothing' if got is None else 'another vector'} although the vector stored "
            f"for that pair is still in its kg_emb_ route", data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
