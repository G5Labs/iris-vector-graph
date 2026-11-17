"""embed_queue binding: fresh queue entries through the actual workers on the run-isolated continuation fixture
(ivg-cont-20261117-iris), compared with a port of embed_queue.rs; mutations mirror the controls.

Python worker: process_embed_queue with a fixture embedder (fails on POISON, answers 5 numbers on WIDE and [] on EMPTY).
IRIS worker: Graph.KG.EmbedQueue.ProcessBatch, the method EmbedQueueTask.OnTask calls, with the fixture-only provider
W42.FixtureEmbedding behind %Embedding.Config 'w42-fixture' (iteration-36/fixture; fails on POISON, answers nothing on
EMPTY). Readers: GetEntry (status and reason) and get_embedding in the entry's graph and model (the stored vector).
Ordinary data, fixture only."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("EQ_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
CFG = "w42-fixture"
MUTS = ["iris_unanswered_is_error", "iris_default_insert_ok", "python_done_on_provider_failure", "python_skips_identity"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---- port of embed_queue.rs (spec functions), with mutation switches mirroring the controls ----
def iris_worker(e, m):
    if not e["node_in_graph"]:
        return ("ERROR", True, False)
    if e["named_graph"] and not e["has_route"]:
        return ("ERROR", True, False)
    if e["named_graph"] and not e["dtype_ok"]:
        return ("ERROR", True, False)
    answered = e["config_known"] and e["provider"] == "Vector"
    if not answered:
        return ("ERROR", True, False) if m.get("iris_unanswered_is_error") else ("DONE", False, False)
    insert_ok = (e["named_graph"] or m.get("iris_default_insert_ok")) and e["width_ok"]
    return ("DONE", False, True) if insert_ok else ("ERROR", True, False)


def py_worker(e, m):
    if not e["own_model"] and not m.get("python_skips_identity"):
        return ("ERROR", True, False)
    if e["provider"] == "Fail":
        return ("DONE", False, False) if m.get("python_done_on_provider_failure") else ("ERROR", True, False)
    if e["provider"] == "Vector" and e["width_ok"]:
        return ("DONE", False, True)
    return ("ERROR", True, False)


def entry(named=False, node=True, route=True, dtype=True, known=True, provider="Vector", width=True, own=True):
    return dict(named_graph=named, node_in_graph=node, has_route=route, dtype_ok=dtype, config_known=known,
                provider=provider, width_ok=width, own_model=own)


def fixture_embedder(text):
    if "POISON" in text:
        raise RuntimeError("fixture embedder refused the text")
    if "WIDE" in text:
        return [0.5] * 5
    if "EMPTY" in text:
        return []
    return [(i + len(text)) / 1000 for i in range(1, 769)]


def main():
    from iris_vector_graph.schema import _call_classmethod
    t0 = time.time()
    c = runtime.connect(); e = runtime.engine(c); e.embedder = fixture_embedder
    o = runtime.connect(); O = runtime.engine(o)
    G = f"eqg{TAG}"; p = f"eq{TAG}"

    # (case id, worker, node id, node's graph, entry graph, config, model abstraction)
    cases = [
        ("P1", "py", f"{p}:pok", None, None, "", entry()),
        ("P2", "py", f"{p}:pPOISON", None, None, "", entry(provider="Fail")),
        ("P3", "py", f"{p}:pWIDE", None, None, "", entry(width=False)),
        ("P4", "py", f"{p}:pEMPTY", None, None, "", entry(provider="Empty")),
        ("P5", "py", f"{p}:pother", None, None, CFG, entry(own=False)),
        ("I1", "iris", f"{p}:dok", None, None, CFG, entry()),
        ("I2", "iris", f"{p}:dPOISON", None, None, CFG, entry(provider="Fail")),
        ("I3", "iris", f"{p}:dEMPTY", None, None, CFG, entry(provider="Empty")),
        ("I4", "iris", f"{p}:dnocfg", None, None, "", entry(known=False)),
        ("I5", "iris", f"{p}:nok", G, G, CFG, entry(named=True)),
        ("I6", "iris", f"{p}:nPOISON", G, G, CFG, entry(named=True, provider="Fail")),
        ("I7", "iris", f"{p}:nEMPTY", G, G, CFG, entry(named=True, provider="Empty")),
        ("I8", "iris", f"{p}:nnocfg", G, G, "", entry(named=True, known=False, route=False)),
        ("I9", "iris", f"{p}:nelsewhere", None, G, CFG, entry(named=True, node=False)),
    ]
    for _, _, n, ng, _, _, _ in cases:
        e.create_node(n, labels=["EQ"], properties={"k": n}, graph=ng)

    def enqueue(worker):
        for _, w, n, _, eg, cfg, _ in cases:
            if w == worker:
                assert e.enqueue_for_embedding(node_ids=[n], embedding_config=cfg, graph=eg) == 1, n

    def observe(n, eg, cfg):
        ent = json.loads(str(_call_classmethod(o, "Graph.KG.EmbedQueue", "GetEntry", n)))
        mk = (cfg or None) if eg else None
        g = O.get_embedding(n, graph=eg, model_key=mk)
        return (ent["status"], bool(ent["error"]), g is not None and len(g.get("embedding") or []) > 0)

    enqueue("py"); e.process_embed_queue(batch_size=100)
    enqueue("iris"); _call_classmethod(c, "Graph.KG.EmbedQueue", "ProcessBatch", 100)
    got = {cid: list(observe(n, eg, cfg)) for cid, _, n, _, eg, cfg, _ in cases}
    pending_after = O.embed_queue_pending()
    c.close(); o.close()

    def predict(m):
        return {cid: list((py_worker if w == "py" else iris_worker)(ab, m)) for cid, w, _, _, _, _, ab in cases}

    want = predict({})
    mism = [{"case": k, "observed": got[k], "expected": want[k]} for k in want if got[k] != want[k]]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if v != got[k]) for mm in MUTS}
    body = {"kind": "binding", "model": "embed_queue", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": RUN,
            "verdict": "AGREES" if not mism and pending_after == 0 else "DISAGREES", "cases": len(want),
            "comparisons": 3 * len(want), "mismatches": mism, "observed": got, "pending_after": pending_after,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "embed_queue.rs", HERE / "model.json",
                                                                      REPO / ".g5/uplift/consolidated/iteration-36/fixture/W42.FixtureEmbedding.cls"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/_engine/embeddings.py", "iris_src/src/Graph/KG/EmbedQueue.cls",
                                                                    "iris_src/src/Graph/KG/EmbedQueueTask.cls"]}},
            "scope": "Actual process_embed_queue and Graph.KG.EmbedQueue.ProcessBatch on IRIS 2026.1 (pin 3eaa79cf), one entry per case, "
                     "read back through GetEntry and get_embedding. Providers are fixture substitutes (a Python callable; an "
                     "%Embedding.Interface subclass); their failure, empty and vector answers are the modeled Provider cases. The "
                     "task path (start_background_embedding) was observed separately in iteration-36/embed-queue-observed2-*.json. "
                     "Not exercised: two workers at once; an interruption between the Python worker's two writes; free-text entries."}
    d = REPO / ".g5/Verus_verification/results/embed_queue" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "comparisons", "pending_after", "all_sensitivities_detected",
                                            "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
