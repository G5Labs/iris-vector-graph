"""W52 second observation: re-insert of one node into a different IVF cell (run-isolated continuation fixture)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent / "iteration-36")); import runtime  # noqa: E402
TAG = time.strftime("%H%M%S", time.gmtime())
c = runtime.connect(); e = runtime.engine(c); G, K, NAME, p = f"ivh{TAG}", f"ivf-h-{TAG}", f"ivh{TAG}", f"ih{TAG}_"
for n, v in {"a": [1, 0, 0, 0], "a2": [0.9, 0.1, 0, 0], "b": [0, 0, 0, 1], "b2": [0, 0, 0.1, 0.9]}.items():
    e.create_node(p + n, graph=G); e.store_embedding(p + n, [float(x) for x in v], graph=G, model_key=K)
e.ivf_build(NAME, nlist=2, graph=G, model_key=K)
c1 = e.ivf_insert(NAME, p + "g", [1.0, 0.05, 0, 0]); c2 = e.ivf_insert(NAME, p + "g", [0, 0, 0.05, 1.0])
hits_old = [(n[len(p):], round(float(s), 3)) for n, s in e.ivf_search(NAME, [1.0, 0.05, 0, 0], k=10, nprobe=2)]
d1 = e.ivf_delete(NAME, p + "g"); hits_after_delete = [(n[len(p):], round(float(s), 3)) for n, s in e.ivf_search(NAME, [1.0, 0.05, 0, 0], k=10, nprobe=2)]
r = {"cells": [c1, c2], "hits_for_old_vector": hits_old, "indexed": e.ivf_info(NAME).get("indexed"), "delete": d1,
     "hits_after_one_delete": hits_after_delete}
dest = HERE / f"ivf-observed2-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"; dest.write_text(json.dumps(r, indent=2) + "\n"); print(json.dumps(r))
