#!/usr/bin/env python3
"""O3 / F8 — where the IRIS queue worker puts a default-graph vector for a declared model.

Model: search.rs witness_queue_default_graph_misroutes (W-O3a) and witness_queue_writes_into_claimed_table
(W-O3b). L1 (4.0.0 routing; EmbedQueue.ClaimPendingBatch's own rationale "otherwise the queue would be
the one write path that escapes the embedding identity registry"): a vector computed for (graph '',
model B) is stored where readers of ('', B) read it — the same place store_embedding(model_key=B)
puts it — and never in a table recorded for another model.

Needs an IRIS %Embedding.Config whose VectorLength equals kg_NodeEmbeddings' declared width (768 on this
arm); without one the probe is INCONCLUSIVE (the worker computes the vector with SELECT EMBEDDING(text,
config), so no stand-in can replace a real model). Community Edition ships the %Embedding.Config table
empty. A config can only be provided where the IRIS container's embedded Python has sentence-transformers
and the model files (or network access to fetch them); this arm was not provisioned with them (review
R1-12). Opt-in setup, for an arm that is: G5_EMBED_MODEL=<huggingface model id of that width> (e.g.
sentence-transformers/all-mpnet-base-v2 for 768) and optionally G5_EMBED_CACHE=<hfCachePath inside the
container>; the probe then inserts a %Embedding.Config row named g5probe-st and deletes it at the end.
G5_EMBED_CONFIG=<name> uses an existing config instead.
Drives: create_node, enqueue_for_embedding, start_background_embedding, embed_queue_pending,
get_embedding. Reads ^EmbedQueue(node) and the tables with SELECT for the observation only.
"""
import os
import time

from search_common import connect, engine, ensure_schema, reset, say

NODE = "g5p:queue:1"


def one(conn, sql, params=()):
    cur = conn.cursor()
    try:
        cur.execute(sql, list(params))
        return cur.fetchall()
    finally:
        cur.close()


def main() -> int:
    from iris_vector_graph.embedding_identity import normalize_model_key

    conn, native = connect()
    eng = engine(conn)
    data = {"schema": ensure_schema(eng)}
    reset(eng, native)
    ensure_schema(eng)
    width_rows = one(conn, "SELECT dimension, model_key FROM Graph_KG.embedding_registry WHERE table_name = 'kg_NodeEmbeddings' AND COALESCE(graph_id, '') = ''")
    created_cfg = None
    if os.environ.get("G5_EMBED_MODEL") and width_rows and width_rows[0][0] not in (None, ""):
        import json as _json

        cfg_json = _json.dumps({"modelName": os.environ["G5_EMBED_MODEL"],
                                "hfCachePath": os.environ.get("G5_EMBED_CACHE", "/tmp/g5probe-hf-cache"),
                                "maxTokens": 256, "checkTokenCount": True})
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM %Embedding.Config WHERE Name = 'g5probe-st'")
            cur.execute("INSERT INTO %Embedding.Config (Name, Configuration, EmbeddingClass, VectorLength, Description) "
                        "VALUES ('g5probe-st', ?, '%Embedding.SentenceTransformers', ?, 'B-search probe fixture')",
                        [cfg_json, int(width_rows[0][0])])
            conn.commit()
            created_cfg = "g5probe-st"
        except Exception as e:
            data["config_setup_error"] = repr(e)[:300]
        finally:
            cur.close()
    try:
        try:
            configs = one(conn, "SELECT Name, VectorLength FROM %Embedding.Config")
        except Exception as e:
            say("search_queue_default_graph", "INCONCLUSIVE", f"cannot read %Embedding.Config: {e!r}"[:300], data)
            return 0
        if os.environ.get("G5_EMBED_CONFIG"):
            configs = [r for r in configs if r[0] == os.environ["G5_EMBED_CONFIG"]]
        data["configs"] = [tuple(r) for r in configs]
        data["legacy_row"] = [tuple(r) for r in width_rows]
        width = int(width_rows[0][0]) if width_rows and width_rows[0][0] not in (None, "") else None
        usable = [r[0] for r in configs if r[1] not in (None, "") and width is not None and int(r[1]) == width]
        if not usable:
            say("search_queue_default_graph", "INCONCLUSIVE",
                f"no %Embedding.Config with VectorLength = kg_NodeEmbeddings width {width}: {data['configs']} "
                f"(Community ships none; set G5_EMBED_MODEL on an arm whose IRIS Python can load a model of that width)", data)
            return 0
        if width_rows[0][1] not in (None, ""):
            say("search_queue_default_graph", "INCONCLUSIVE", f"kg_NodeEmbeddings is already claimed: {data['legacy_row']}", data)
            return 0
        cfg = usable[0]
        key = normalize_model_key(cfg)
        eng.create_node(NODE, labels=["Doc"], properties={"name": "queued text"})
        try:
            data["enqueued"] = eng.enqueue_for_embedding([NODE], embedding_config=cfg)
        except Exception as e:
            say("search_queue_default_graph", "INCONCLUSIVE", f"enqueue refused: {e!r}"[:300], data)
            return 0
        data["task"] = eng.start_background_embedding(10)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline and eng.embed_queue_pending() > 0:
            time.sleep(1.0)
        data["entry_status"] = str(native.get("^EmbedQueue", NODE, "status"))
        data["entry_error"] = str(native.get("^EmbedQueue", NODE, "error"))
        data["in_kg_NodeEmbeddings"] = int(one(conn, "SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings WHERE node_id = ?", [NODE])[0][0])
        got_b = eng.get_embedding(NODE, model_key=cfg)
        got_undeclared = eng.get_embedding(NODE)
        data["read_by_pair_B"] = got_b is not None
        data["read_by_undeclared_default_pair"] = got_undeclared is not None
        data["registry_after"] = [tuple(r) for r in one(conn, "SELECT table_name, graph_id, model_key FROM Graph_KG.embedding_registry")]
        reset(eng, native)
        if data["entry_status"] != "DONE":
            say("search_queue_default_graph", "INCONCLUSIVE", f"the worker did not finish the entry: {data['entry_status']} {data['entry_error'][:200]}", data)
        elif got_b is not None and data["in_kg_NodeEmbeddings"] == 0:
            say("search_queue_default_graph", "OBSERVED_AS_EXPECTED", f"the ('', {key!r}) vector is read by its own pair", data)
        else:
            say("search_queue_default_graph", "OBSERVED_DEFECT",
                f"the IRIS worker wrote the ('', {key!r}) vector into kg_NodeEmbeddings ({data['in_kg_NodeEmbeddings']} row); "
                f"get_embedding(model_key={cfg!r}) {'finds' if got_b else 'misses'} it and the undeclared default pair "
                f"{'reads' if got_undeclared else 'does not read'} it", data)
    finally:
        if created_cfg:
            cur = conn.cursor()
            try:
                cur.execute("DELETE FROM %Embedding.Config WHERE Name = ?", [created_cfg])
                conn.commit()
            finally:
                cur.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
