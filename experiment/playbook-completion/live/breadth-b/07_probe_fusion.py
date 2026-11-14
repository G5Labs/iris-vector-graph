#!/usr/bin/env python3
"""Module 07 probes of the pin's fusion helpers and validators, run in-process with stub legs (no IRIS).

    python -I experiment/playbook-completion/live/breadth-b/07_probe_fusion.py

The product code (iris_vector_graph.fusion.HybridSearchFusion, RRFFusion, iris_vector_graph._validate) runs unmodified;
only the engine whose legs it calls is a stub that answers fixed lists or raises. Writes
$RUN_DIR/breadth-b/live/07-probe-fusion.json with one verdict per probe.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
logging.disable(logging.CRITICAL)

from iris_vector_graph.fusion import HybridSearchFusion, RRFFusion  # noqa: E402
from iris_vector_graph import _validate  # noqa: E402


class Stub:
    def __init__(self, txt=None, vec=None, graph=None, txt_raises=False, vec_raises=False):
        self.txt, self.vec, self.graph = txt or [], vec or [], graph or []
        self.txt_raises, self.vec_raises = txt_raises, vec_raises

    def kg_TXT(self, q, k=50, graph=None):
        if self.txt_raises:
            raise RuntimeError("text leg down")
        return list(self.txt)

    def kg_KNN_VEC(self, v, k=50, graph=None):
        if self.vec_raises:
            raise RuntimeError("vector leg down")
        return list(self.vec)

    def kg_NEIGHBORHOOD_EXPANSION(self, seeds, expansion_depth=1, confidence_threshold=600, graph=None):
        return [{"target": t, "confidence": c} for t, c in self.graph]


def main() -> int:
    out = {}
    # F-0710: text-only call with graph expansion, default weights
    eng = Stub(txt=[("a", 1.0)], graph=[("b", 1000)])
    res = HybridSearchFusion(eng).multi_modal_search(query_text="q", k=5, fusion_method="weighted")
    got = {r["entity_id"]: round(r["fusion_score"], 6) for r in res}
    promised = {"a": round(0.3 / 0.5, 6), "b": round(0.2 / 0.5, 6)}  # comment fusion.py:216: text=0.3, graph=0.2
    out["F-0710"] = {"modes": [m["mode"] for m in res[0]["search_modes"]], "got": got, "per_comment": promised,
                     "verdict": "defect-reproduced" if got != promised else "holds",
                     "contract": "fusion.py:216 comment: default weights vector=0.5, text=0.3, graph=0.2"}
    # F-0709: a failed vector leg is logged and dropped (multi_modal), all paths failing gives [] (adaptive)
    eng = Stub(txt=[("a", 1.0)], vec_raises=True)
    res = HybridSearchFusion(eng).multi_modal_search(query_vector="[1,2]", query_text="q", k=5)
    modes = sorted({m["mode"] for r in res for m in r["search_modes"]})
    out["F-0709-vector-leg"] = {"results": res, "modes": modes,
                                "verdict": "defect-reproduced" if (res and "vector" not in modes) else "holds",
                                "contract": "TXT-B17.3: a failed vector list is raised to the caller as well"}
    eng = Stub(txt_raises=True)
    err = None
    try:
        res = HybridSearchFusion(eng).adaptive_search("find something", k=5)
    except Exception as e:  # the contract wants a raise
        err = f"{type(e).__name__}: {e}"
        res = None
    out["F-0709-adaptive"] = {"result": res, "error": err,
                              "verdict": "defect-reproduced" if res == [] else "holds",
                              "contract": "TXT-B18.2: when every path fails, adaptive search raises rather than giving an empty list"}
    # F-0706 / HD-0704: the build validator accepts the stopword node's name
    try:
        _validate.BM25BuildInput(name="__stop__", text_props=["name"], k1=1.5, b=0.75)
        accepted = True
    except Exception as e:
        accepted = f"refused: {e}"
    out["F-0706-validator"] = {"BM25BuildInput('__stop__')": accepted,
                               "verdict": "defect-reproduced" if accepted is True else "holds",
                               "contract": "HD-0704 working assumption: reject __stop__ at public index-management entry points; spec 044 Edge Cases: sanitize_identifier"}
    # HD-0702 baseline: RRFFusion adds 0 for a missing item (characterization, not a defect)
    out["HD-0702-RRFFusion-missing-item"] = {"fuse": RRFFusion.fuse_results([[("a", 1)], [("b", 1)]]),
                                             "verdict": "characterized"}
    run_dir = Path(os.environ.get("RUN_DIR", "/tmp")) / "breadth-b" / "live"
    run_dir.mkdir(parents=True, exist_ok=True)
    p = run_dir / "07-probe-fusion.json"
    p.write_text(json.dumps(out, indent=1, default=repr) + "\n")
    print(p)
    print(json.dumps({k: v["verdict"] for k, v in out.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
