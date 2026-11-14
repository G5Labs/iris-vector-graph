#!/usr/bin/env python3
"""Module 15 probes that need no IRIS (breadth lane C): product code run against local stand-ins.

    python probes15.py            # writes $RUN_DIR/breadth-c/15/probes.json

- F-1505: fhir_search_conditions / FHIRSearchTool against a local FHIR stub (127.0.0.1:185xx) whose first Bundle page
  has link[relation=next]; the stub logs every request, so a page the client never fetched is observable.
- F-1509: unified_clinical_pipeline with a fault injected at kg_PERSONALIZED_PAGERANK (an autospec of the real engine
  class, so the call binds to the real signature) and the FHIR stub supplying an ICD-10 Condition.
- F-1506: _build_rdflib_graph with rdflib's ConjunctiveGraph attribute removed in this process, which is how
  `from rdflib import ConjunctiveGraph` fails on a release without it (premise P-1507); rdflib itself stays importable.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import warnings
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import create_autospec

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))
warnings.simplefilter("ignore", DeprecationWarning)

OUT = Path(os.environ["RUN_DIR"]) / "breadth-c" / "15"
OUT.mkdir(parents=True, exist_ok=True)
PORT = 18531
REQUESTS: list = []


def bundle(page: int):
    codes = {1: ["C15.1", "C15.2"], 2: ["C15.3"]}[page]
    b = {"resourceType": "Bundle", "type": "searchset", "total": 3,
         "entry": [{"resource": {"resourceType": "Condition", "id": f"c{page}{i}",
                                 "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": c,
                                                      "display": c}]}}} for i, c in enumerate(codes)]}
    if page == 1:
        b["link"] = [{"relation": "self", "url": f"http://127.0.0.1:{PORT}/Condition?patient=p1"},
                     {"relation": "next", "url": f"http://127.0.0.1:{PORT}/Condition?patient=p1&page=2"}]
    return b


class Stub(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        REQUESTS.append(self.path)
        page = 2 if "page=2" in self.path else 1
        body = json.dumps(bundle(page)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/fhir+json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass


def main():
    res = {}
    srv = HTTPServer(("127.0.0.1", PORT), Stub)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        from iris_vector_graph import fhir_bridge
        base = f"http://127.0.0.1:{PORT}"
        # F-1505
        REQUESTS.clear()
        r = fhir_bridge.fhir_search_conditions(base, "p1")
        tool = fhir_bridge.FHIRSearchTool(base)(patient_id="p1")
        res["F-1505"] = {"conditions": [c["code"] for c in r["conditions"]], "error": r["error"],
                         "tool_conditions": [c["code"] for c in tool["conditions"]],
                         "requests_seen_by_stub": list(REQUESTS),
                         "server_total": 3,
                         "tool_docstring_claims_pagination": "pagination" in (fhir_bridge.FHIRSearchTool.__doc__ or "")}
        # F-1509
        from iris_vector_graph.engine import IRISGraphEngine
        eng = create_autospec(IRISGraphEngine, instance=True)
        eng.get_kg_anchors.return_value = ["c15:mesh1"]
        eng.kg_PERSONALIZED_PAGERANK.side_effect = RuntimeError("injected: IRIS refused the walk (SQLCODE -99)")
        out = fhir_bridge.unified_clinical_pipeline(eng, "c15 probe", base, "p1")
        res["F-1509"] = {"status": out["status"], "anchors": out["anchors"], "ppr_results": out["ppr_results"],
                         "ppr_step": [s for s in out["provenance"]["steps"] if s.get("step") == "ppr"],
                         "docstring_lists_fhir_error": "fhir_error" in (fhir_bridge.unified_clinical_pipeline.__doc__ or "")}
        eng2 = create_autospec(IRISGraphEngine, instance=True)
        eng2.get_kg_anchors.return_value = ["c15:mesh1"]
        eng2.kg_PERSONALIZED_PAGERANK.return_value = {}
        out2 = fhir_bridge.unified_clinical_pipeline(eng2, "c15 probe", base, "p1")
        res["F-1509"]["status_when_walk_really_empty"] = out2["status"]
        out3 = fhir_bridge.unified_clinical_pipeline(eng2, "c15 probe", "http://127.0.0.1:9", "p1", fhir_timeout=2)
        res["F-1509"]["status_when_fhir_unreachable"] = out3["status"]
    finally:
        srv.shutdown()
        srv.server_close()
    # F-1506
    import rdflib
    from iris_vector_graph._engine import _rdf_utils
    saved = rdflib.ConjunctiveGraph
    try:
        del rdflib.ConjunctiveGraph
        try:
            _rdf_utils._build_rdflib_graph(conn=None)
            res["F-1506"] = {"raised": None}
        except Exception as ex:  # noqa: BLE001
            res["F-1506"] = {"raised": f"{type(ex).__name__}: {ex}",
                             "cause": f"{type(ex.__cause__).__name__}: {ex.__cause__}" if ex.__cause__ else None,
                             "rdflib_importable": True, "rdflib_version": rdflib.__version__}
    finally:
        rdflib.ConjunctiveGraph = saved
    res["F-1506"]["installed_rdflib"] = rdflib.__version__
    (OUT / "probes.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
