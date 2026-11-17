"""W49: embed_nodes with a fixture model and its readers (run-isolated continuation fixture; ordinary data)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W49_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


class FixtureModel:
    """Stands in for a model with a sentence-transformers-like encode: a string gives one numpy vector, a list a 2-D
    array (768 wide). It is not a SentenceTransformer instance, so embed_nodes takes its per-text embed_text path."""
    def __init__(self): self.calls = []
    def encode(self, texts, **kw):
        import numpy as np
        one = isinstance(texts, str)
        batch = [texts] if one else list(texts)
        self.calls.append(batch)
        arr = np.array([[(len(t) + i) / 1000.0 for i in range(768)] for t in batch])
        return arr[0] if one else arr


def main():
    c = runtime.connect(); e = runtime.engine(c)
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    p = f"en{TAG}_"; L, O = f"Gene{TAG}", f"Other{TAG}"; G, K = f"eng{TAG}", f"fixture-model-{TAG}"
    N = lambda x: p + x  # noqa: E731
    M = FixtureModel()

    def has(nid, graph=None, mk=None):
        return e.get_embedding(nid, graph=graph, model_key=mk) is not None

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    for x in ["g1", "g2", "g3"]:
        e.create_node(N(x), labels=[L])
    e.create_node(N("o1"), labels=[O]); e.create_node(N("skip_me"), labels=[L])
    before = e.embedding_count()
    e.create_node(N("xskipx"), labels=[L])
    case("E1_label", lambda: {"answer": e.embed_nodes(model=M, label=L, exclude_pattern=f"{p}skip*"),
                              "vectors": {x: has(N(x)) for x in ["g1", "g2", "g3", "o1", "skip_me", "xskipx"]},
                              "count_delta": e.embedding_count() - before, "texts": M.calls[-1] if M.calls else None})
    case("E5_pattern_without_underscore", lambda: (M.calls.clear(), {"answer": e.embed_nodes(model=M, node_ids=[N("xskipx"), N("skip_me")], exclude_pattern="*skip*", force=True), "texts": M.calls})[1])
    e.create_node(N("g4"), labels=[L])
    case("E2_missing_only", lambda: (M.calls.clear(), {"answer": e.embed_nodes(model=M, label=L, missing_only=True), "texts": M.calls})[1])
    e.create_node(N("g5"), labels=[L])
    case("E3_default_no_force", lambda: (M.calls.clear(), {"answer": e.embed_nodes(model=M, label=L), "texts": M.calls})[1])
    case("E3b_force", lambda: (M.calls.clear(), {"answer": e.embed_nodes(model=M, label=L, force=True), "n_texts": sum(len(x) for x in M.calls)})[1])
    e.create_node(N("solo"), labels=[O])
    case("E4_node_ids", lambda: {"answer": e.embed_nodes(model=M, node_ids=[N("solo")]), "solo": has(N("solo")), "o1": has(N("o1"))})
    for x in ["g1", "g2"]:
        e.create_node(N(x), labels=[L], graph=G)
    e.create_node(N("o1"), graph=G)                      # same id as the default graph's Other node; no label here
    e.create_node(N("g3"), graph=G)                      # same id as a default-graph Gene; no label in G
    case("E7_unembedded_before", lambda: sorted(x[len(p):] for x in e.get_unembedded_nodes(graph=G, model_key=K)))
    case("E6_E8_graph", lambda: {"answer": e.embed_nodes(model=M, label=L, graph=G, model_key=K),
                                 "G": {x: has(N(x), G, K) for x in ["g1", "g2", "g3", "o1"]}})
    case("E7_unembedded_after", lambda: sorted(x[len(p):] for x in e.get_unembedded_nodes(graph=G, model_key=K)))
    dest = HERE / f"embed-nodes-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
