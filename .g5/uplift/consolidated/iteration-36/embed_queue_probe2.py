"""W42 second observation: the IRIS worker through its real task (start_background_embedding), default graph versus a
named graph, provider success versus failure (run-isolated continuation fixture only; same fixture provider)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime  # noqa: E402

RUN = os.environ.get("W42_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def main():
    from iris_vector_graph.schema import _call_classmethod
    c = runtime.connect(); e = runtime.engine(c)
    o = runtime.connect(); O = runtime.engine(o)
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    G = f"w42g{TAG}"
    dflt = [f"w42d{TAG}:ok", f"w42d{TAG}:POISON", f"w42d{TAG}:EMPTY"]
    named = [f"w42n{TAG}:ok", f"w42n{TAG}:POISON", f"w42n{TAG}:EMPTY"]
    for n in dflt:
        e.create_node(n, labels=["W42"], properties={"k": n})
    for n in named:
        e.create_node(n, labels=["W42"], properties={"k": n}, graph=G)

    def entry(req):
        return json.loads(str(_call_classmethod(o, "Graph.KG.EmbedQueue", "GetEntry", req)))

    def width(node, graph=None):
        g = O.get_embedding(node, graph=graph, model_key=("w42-fixture" if graph else None))
        return None if g is None else len(g.get("embedding") or [])

    try:
        out["cases"]["enqueue"] = {
            "default": e.enqueue_for_embedding(node_ids=dflt, embedding_config="w42-fixture"),
            "named": e.enqueue_for_embedding(node_ids=named, embedding_config="w42-fixture", graph=G),
            "named_route": str(O.resolve_route(graph=G, model_key="w42-fixture")),
            "pending": O.embed_queue_pending()}
        task = e.start_background_embedding(batch_size=100)
        t0 = time.time(); pend = None
        while time.time() - t0 < 120:
            pend = O.embed_queue_pending()
            if pend == 0:
                break
            time.sleep(1)
        out["cases"]["task"] = {"task_id": task, "pending_after": pend, "seconds": round(time.time() - t0, 1)}
        out["cases"]["default_graph"] = {n: {"entry": entry(n), "vector_width": width(n)} for n in dflt}
        out["cases"]["named_graph"] = {n: {"entry": entry(n), "vector_width": width(n, G)} for n in named}
    except Exception:
        out["cases"]["raised"] = traceback.format_exc().strip().splitlines()[-1][:400]

    dest = HERE / f"embed-queue-observed2-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
