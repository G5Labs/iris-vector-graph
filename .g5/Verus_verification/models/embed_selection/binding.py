"""embed_selection binding: fresh nodes on the run-isolated continuation fixture (ivg-cont-20261117-iris) through the
actual embed_nodes with a fixture model (numpy-returning encode; not a SentenceTransformer, so the per-text path), read
back with get_embedding; which nodes got a vector is compared with a port of embed_selection.rs. Ordinary data."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("ES_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
MUTS = ["escape_honoured", "label_scoped", "force_ignored", "exclusion_ignored"]


class FixtureModel:
    def encode(self, texts, **kw):
        import numpy as np
        one = isinstance(texts, str); batch = [texts] if one else list(texts)
        arr = np.array([[(len(t) + i) / 1000.0 for i in range(768)] for t in batch])
        return arr[0] if one else arr


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def port(n, special, force, m):
    excluded = (n["glob"] and (not special or m.get("escape_honoured"))) and not m.get("exclusion_ignored")
    label = n["here"] or (n["elsewhere"] and not m.get("label_scoped"))
    sel = label and n["listed"] and not excluded
    return sel and ((force and not m.get("force_ignored")) or not n["vec"])


def main():
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c); M = FixtureModel()
    p = f"es{TAG}_"; L = f"ESL{TAG}"; G, K = f"esg{TAG}", f"es-model-{TAG}"
    N = lambda x: p + x  # noqa: E731
    # default graph: a, b_x (matches the glob with an underscore), cx (matches a plain glob); G: twin without label
    for x in ["a", "b_x", "cx", "twin"]:
        e.create_node(N(x), labels=[L])
    e.create_node(N("twin"), graph=G); e.create_node(N("own"), labels=[L], graph=G)
    cases = []   # (name, node facts, special pattern?, force, call)
    got = {}
    r1 = e.embed_nodes(model=M, label=L, exclude_pattern=f"{p}b_*")            # pattern with an underscore
    got["underscore_pattern_b_x"] = e.get_embedding(N("b_x")) is not None
    got["underscore_pattern_a"] = e.get_embedding(N("a")) is not None
    e.create_node(N("dx"), labels=[L])
    r2 = e.embed_nodes(model=M, node_ids=[N("dx"), N("cx")], exclude_pattern="*dx*", force=True)
    got["plain_pattern_dx"] = e.get_embedding(N("dx")) is not None
    got["force_reembeds_cx"] = r2["embedded"] == 1
    r3 = e.embed_nodes(model=M, label=L)
    # four nodes already have vectors (a, b_x, cx, twin); dx was excluded above and has none
    got["no_force_skips_existing"] = r3["embedded"] == 1 and r3["skipped"] == 4
    r4 = e.embed_nodes(model=M, label=L, graph=G, model_key=K)
    got["twin_in_G_selected"] = e.get_embedding(N("twin"), graph=G, model_key=K) is not None
    got["own_in_G_selected"] = e.get_embedding(N("own"), graph=G, model_key=K) is not None
    c.close()

    def predict(m):
        F = dict(here=True, elsewhere=False, listed=True, glob=False, vec=False)
        return {"underscore_pattern_b_x": port({**F, "glob": True}, True, False, m),
                "underscore_pattern_a": port(F, True, False, m),
                "plain_pattern_dx": port({**F, "glob": True}, False, True, m),
                "force_reembeds_cx": port({**F, "vec": True}, False, True, m),
                "no_force_skips_existing": not port({**F, "vec": True}, False, False, m),
                "twin_in_G_selected": port({**F, "here": False, "elsewhere": True}, False, False, m),
                "own_in_G_selected": port(F, False, False, m)}

    want = predict({})
    mism = [{"case": k, "observed": got[k], "expected": want[k]} for k in want if got[k] != want[k]]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if v != got[k]) for mm in MUTS}
    body = {"kind": "binding", "model": "embed_selection", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "answers": [r1, r2, r3, r4], "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "embed_selection.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/_engine/embeddings.py", "iris_vector_graph/embed_selector.py"]}},
            "scope": "Actual embed_nodes on IRIS 2026.1 (pin 3eaa79cf) with a fixture model on the per-text path; the SentenceTransformer batch "
                     "path, text_fn and progress callbacks are not exercised. The default text is the node ID."}
    d = REPO / ".g5/Verus_verification/results/embed_selection" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "observed", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
