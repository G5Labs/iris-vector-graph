"""W53 addition: IVF metric "cosine" with vectors of different lengths, against the route's own search
(search_nodes_by_vector) on the same vectors (run-isolated continuation fixture)."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent / "iteration-36")); import runtime  # noqa: E402
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
c = runtime.connect(); e = runtime.engine(c)
G, K, NAME, p = f"cog{TAG}", f"co-k-{TAG}", f"coi{TAG}", f"co{TAG}_"
for n, v in {"long_off": [10, 0, 0, 0], "unit_on": [0.6, 0.8, 0, 0], "other": [0, 0, 1, 0]}.items():
    e.create_node(p + n, graph=G); e.store_embedding(p + n, [float(x) for x in v], graph=G, model_key=K)
e.ivf_build(NAME, nlist=1, graph=G, model_key=K, metric="cosine")
q = [0.6, 0.8, 0.0, 0.0]
r = {"ivf_cosine": [(i[len(p):], round(s, 3)) for i, s in e.ivf_search(NAME, q, 3, 1)],
     "route_search": [(i[len(p):], round(float(s), 3)) for i, s in e.search_nodes_by_vector(q, k=3, graph=G, model_key=K)]}
(HERE / f"ivf-cosine-observed-{RUN}.json").write_text(json.dumps(r, indent=2) + "\n"); print(json.dumps(r))
