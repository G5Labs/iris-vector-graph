#!/usr/bin/env python3
"""Update the six least-privilege entries of refusals/audit/NN.json from the registered runs rx-live-priv
(results-r1.json) and rx-live-priv-vec (results-r3.json). Case names are copied from the logs, not retyped.

    python apply_priv.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

LANE = Path(__file__).resolve().parents[1]
RUN = Path(os.environ["RUN_DIR"]) / "refusals" / "priv"

UPDATES = {
    "INS-X10.7": ("01", "rx-live-priv", "results-r1.json", {
        "implementing_code": ["iris_src/src/Graph/KG/SqlPrivilege.cls:18-31", "iris_src/src/Graph/KG/SqlProcs.cls:133-162"],
        "notes": "Live as IVGAUDIT_RO holding only EXECUTE ON SCHEMA Graph_KG in AUDITE (window 15:31:49-15:31:56Z, "
                 "2026-11-14): each of the 8 global-reading SQL functions the pinned e2e test names was refused with "
                 "'SQLCODE=-99,%msg=User IVGAUDIT_RO lacks SELECT on Graph_KG.rdf_edges' (rdf_props for kg_BM25), "
                 "surfaced by the driver inside SQLCODE -149; 0 journal records. Earlier evidence: the e2e test passed "
                 "in val-gated-rag-1.",
    }),
    "INS-X1.5": ("01", "rx-live-priv", "results-r1.json", {
        "notes": "Live as IVGAUDIT_RO (SELECT and EXECUTE on the schema, database at R, no %CREATE_* privilege): "
                 "engine.initialize_schema() raised IVGSchemaError 'cannot create IVG's SQL objects in schema "
                 "Graph_KG: user IVGAUDIT_RO does not hold the SQL privilege %CREATE_TABLE ... Nothing was created.' "
                 "(names the user, the schema and the right); 0 journal records. Unit tests on fakes also passed in "
                 "val-unit-3-c01.",
    }),
    "ALG-B9.3": ("10", "rx-live-priv", "results-r1.json", {
        "notes": "Live as IVGAUDIT_RO (SELECT and EXECUTE on the schema; the documented reading role, database at R): "
                 "engine.kg_GRAPH_WALK('rxp:a') raised RuntimeError 'kg_GRAPH_WALK failed: it writes a work area, "
                 "^ArnoKG(\"bfs_r\"), and IRIS refused this login a write to the namespace's globals database "
                 "(<PROTECT>). It needs the namespace's database resource at RW ...'; 0 journal records.",
        "dependency": None,
    }),
    "SNP-X1.3": ("18", "rx-live-priv", "results-r1.json", {
        "notes": "Live as IVGAUDIT_RO holding SELECT on the 18 other Graph_KG tables of AUDITE and none on rdf_props "
                 "(CheckPrivilege rdf_props 0, nodes 1): engine.save_snapshot raised SnapshotReadError 'save_snapshot: "
                 "cannot read Graph_KG.rdf_props: ... SQLCODE -99 ... No archive was written'; the target directory "
                 "stayed empty; 0 journal records. Upstream unit test also passed in val-unit-3-c02. The native-index "
                 "half (an unreadable global) is not separable here: AUDITE's globals share one database resource.",
    }),
    "OPS-X4.84": ("17", "rx-live-priv", "results-r1.json", {
        "notes": "Live as IVGAUDIT_RO with the role's %DB_%DEFAULT resource removed for the window (restored at once; "
                 "AUDITE's globals and routines are one database, /usr/irissys/mgr/audite/, so the class dictionary "
                 "is unreadable; the login itself was accepted): building the engine / _detect_capabilities and khop "
                 "raised ClassesUnreadable 'IVG's classes are in this namespace's routines database "
                 "(/usr/irissys/mgr/audite/), which this user may not read: <PROTECT>...' instead of answering 'no "
                 "classes'; 0 journal records. Unit tests also passed in val-unit-3-c02.",
    }),
    "VEC-X1.16": ("06", "rx-live-priv-vec", "results-r3.json", {
        "outcome": "product-defect", "finding": "F-0601",
        "implementing_code": ["iris_vector_graph/_engine/schema.py:1042-1061", "iris_vector_graph/_engine/schema.py:1383-1385",
                              "iris_vector_graph/_engine/embeddings.py:377-430", "iris_vector_graph/_engine/embeddings.py:313-336"],
        "notes": "Live as IVGAUDIT_RO (database RW for the window only; SELECT on every Graph_KG table but "
                 "embedding_registry; INSERT/UPDATE/DELETE on the target tables): on a fresh engine the write is "
                 "refused, but by the route lookup, not by the identity check (frames store_embedding -> "
                 "_route_for_write -> _read_route, embeddings.py:420-427 re-raises any failure but -30, R161) for "
                 "both a routed model and the default pair. Once a route is cached (30 s, embeddings.py:313-336), the "
                 "identity check is the only registry read: after SELECT on the registry was revoked (CheckPrivilege "
                 "0), a second store_embedding on the same engine returned True and wrote its row "
                 "(get_embedding_identity answers None on the -99, schema.py:1054-1056; enforce lets it through, "
                 "1383-1385). The stated refusal is therefore not implemented by the code that states it (F-0601), "
                 "and holds only incidentally on a cache miss. Earlier: stand-in cursor probes "
                 "(breadth-a-probe-local-0101-0601, rx-probe-06-local).",
    }),
}


def main() -> int:
    for sid, (mod, run, res, upd) in UPDATES.items():
        doc = json.loads((RUN / res).read_text())
        cases = [c["case"] for c in doc["cases"] if c.get("statement") == sid
                 and c.get("outcome") in ("holds-live", "refused-but-changed", "not-refused-as-stated")]
        outcomes = {c["case"]: c["outcome"] for c in doc["cases"] if c.get("case") in cases}
        p = LANE / "audit" / f"{mod}.json"
        frag = json.loads(p.read_text())
        for e in frag["statements"]:
            if e["id"] != sid:
                continue
            old_runs = [x for x in e.get("evidence", []) if x.startswith("run:")]
            e["outcome"] = upd.get("outcome", "holds-live")
            e["evidence"] = [f"run:{run}"] + [x for x in old_runs if x != f"run:{run}"]
            e["live_cases"] = cases
            if e["outcome"] == "holds-live":
                e.pop("finding", None)
                e.pop("log_contains", None)
            e.pop("dependency", None)
            for k, v in upd.items():
                if k not in ("outcome",) and v is not None:
                    e[k] = v
            print(sid, e["outcome"], e["evidence"], {c: outcomes[c] for c in cases})
        p.write_text(json.dumps(frag, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
