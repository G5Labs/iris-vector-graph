"""W42: the embedding queue from enqueue to the vector reader (run-isolated continuation fixture only).

Needs the fixture-only provider `fixture/W42.FixtureEmbedding.cls` and the `%Embedding.Config` row `w42-fixture`
(VectorLength 768) on ivg-cont-20261117-iris; see embed-queue-PAIRS.md. Python worker: a callable embedder that fails
on POISON and answers 5 numbers on WIDE. IRIS worker: Graph.KG.EmbedQueue.ProcessBatch, the method the queue task calls.
"""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime  # noqa: E402

RUN = os.environ.get("W42_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def fixture_embedder(text):
    if "POISON" in text:
        raise RuntimeError("W42 python fixture embedder refused the text")
    if "WIDE" in text:
        return [0.5] * 5
    return [(i + len(text)) / 1000 for i in range(1, 769)]


def main():
    from iris_vector_graph.schema import _call_classmethod
    c = runtime.connect(); e = runtime.engine(c); e.embedder = fixture_embedder
    o = runtime.connect(); O = runtime.engine(o)            # an observer engine for every reader
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}

    def entry(req):
        return json.loads(str(_call_classmethod(o, "Graph.KG.EmbedQueue", "GetEntry", req)))

    def raw(req, sub):
        cur = o.cursor(); cur.execute("SELECT 1"); cur.close()
        import iris
        return iris.createIRIS(o).get("^EmbedQueue", req, sub)

    def vec(node):
        g = O.get_embedding(node)
        return None if g is None else len(g.get("embedding") or [])

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    p = f"w42{TAG}"
    py_nodes = [f"{p}:a", f"{p}:b", f"{p}:POISON", f"{p}:WIDE"]
    ir_nodes = [f"{p}:r1", f"{p}:rPOISON", f"{p}:rEMPTY"]
    ir_nocfg = [f"{p}:rnocfg"]
    for n in py_nodes + ir_nodes + ir_nocfg + [f"{p}:other"]:
        e.create_node(n, labels=["W42"], properties={"k": n})

    out["cases"]["start_pending"] = O.embed_queue_pending()

    # Q1: node-keyed enqueue with the worker's own model (empty config)
    case("Q1_enqueue_python", lambda: {"returned": e.enqueue_for_embedding(node_ids=py_nodes),
                                       "pending": O.embed_queue_pending()})
    # Q4 setup: an entry that asks for another model
    case("Q4_enqueue_other_model", lambda: {"returned": e.enqueue_for_embedding(node_ids=[f"{p}:other"], embedding_config="w42-fixture"),
                                            "pending": O.embed_queue_pending()})
    # Q3-Q5: the Python worker
    def py_worker():
        res = e.process_embed_queue(batch_size=100)
        return {"returned": res, "pending": O.embed_queue_pending(),
                "entries": {n: entry(n) for n in py_nodes + [f"{p}:other"]},
                "vector_width": {n: vec(n) for n in py_nodes + [f"{p}:other"]}}
    case("Q3_Q5_python_worker", py_worker)

    # IRIS worker: entries asking for the IRIS provider, and one asking for nothing
    case("R_enqueue_iris", lambda: {"returned_cfg": e.enqueue_for_embedding(node_ids=ir_nodes, embedding_config="w42-fixture"),
                                    "returned_nocfg": e.enqueue_for_embedding(node_ids=ir_nocfg),
                                    "pending": O.embed_queue_pending()})
    def iris_worker():
        res = json.loads(str(_call_classmethod(c, "Graph.KG.EmbedQueue", "ProcessBatch", 100)))
        return {"returned": res, "pending": O.embed_queue_pending(),
                "entries": {n: entry(n) for n in ir_nodes + ir_nocfg},
                "result_len": {n: len(str(raw(n, "result") or "")) for n in ir_nodes + ir_nocfg},
                "vector_width": {n: vec(n) for n in ir_nodes + ir_nocfg}}
    case("R_iris_worker", iris_worker)

    dest = HERE / f"embed-queue-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
