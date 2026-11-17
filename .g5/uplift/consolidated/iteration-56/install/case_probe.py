"""Iteration 56 Part B probe: setup with the recorded IVG Schema named in another letter case, over a populated vector
table at another width (fresh namespace I56SD in ivg-cont-20261117-iris only). Observation only.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-56/install/case_probe.py)
"""
import json, os, sys, time
from pathlib import Path
REPO = Path(os.environ["IVG_REPO"]).resolve()
sys.path.insert(0, str(REPO / ".g5/Verus_verification/models/install_lifecycle"))
import observe as ob  # noqa: E402

o = {}
ob.recreate_namespace("I56SD")
c = ob.connect("I56SD")
e = ob.engine(c, 8, "I56W")
o["setup_W"] = ob.attempt(lambda: ob.setup_obs(e.initialize_schema()))
e.create_node("v1", labels=["T"])
o["store8"] = ob.attempt(lambda: e.store_embedding("v1", [0.25] * 8))
from iris_vector_graph.schema import GraphSchema
def width(t):
    cur = c.cursor()
    try: return GraphSchema.get_embedding_dimension(cur, t)
    finally: cur.close()
o["width_upper_before"] = width("I56W.kg_NodeEmbeddings")
o["width_lower_lookup"] = width("i56w.kg_NodeEmbeddings")
o["upper16_dry"] = ob.attempt(lambda: ob.setup_obs(ob.engine(c, 16, "I56W").initialize_schema(dry_run=True)))
o["upper16_setup"] = ob.attempt(lambda: ob.setup_obs(ob.engine(c, 16, "I56W").initialize_schema()))
o["lower16_dry"] = ob.attempt(lambda: ob.setup_obs(ob.engine(c, 16, "i56w").initialize_schema(dry_run=True)))
o["lower16_setup"] = ob.attempt(lambda: ob.setup_obs(ob.engine(c, 16, "i56w").initialize_schema()))
o["width_upper_after"] = width("I56W.kg_NodeEmbeddings")
o["rows_after"] = ob.scalar(c, "SELECT COUNT(*) FROM I56W.kg_NodeEmbeddings")
o["vector_after"] = ob.attempt(lambda: str(ob.scalar(c, "SELECT emb FROM I56W.kg_NodeEmbeddings WHERE node_id = 'v1'"))[:200])
o["registry_after"] = ob.attempt(lambda: ob.scalar(c, "SELECT dimension FROM I56W.embedding_registry WHERE table_name = 'kg_NodeEmbeddings' AND graph_id = ''"))
o["store8_after"] = ob.attempt(lambda: ob.engine(c, 8, "I56W").store_embedding("v1", [0.5] * 8))
o["store16_after"] = ob.attempt(lambda: ob.engine(c, 16, "I56W").store_embedding("v1", [0.5] * 16))
o["search8_after"] = ob.attempt(lambda: len(ob.engine(c, 8, "I56W").kg_KNN_VEC(json.dumps([0.25] * 8), k=5)))
c.close()
out = REPO / ".g5/uplift/consolidated/iteration-56/install" / ("case-observed-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ".json")
out.write_text(json.dumps(o, indent=1, sort_keys=True, default=str) + "\n")
print(out); print(json.dumps(o, indent=1, sort_keys=True, default=str))
