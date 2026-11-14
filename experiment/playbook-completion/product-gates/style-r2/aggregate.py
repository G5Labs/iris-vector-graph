#!/usr/bin/env python3
"""Aggregate the 3.5-style counts: round 1 (modules 11-14, STYLE.md D-01..D-23) and round 2 (counts-G1..G4.json).

    python experiment/playbook-completion/product-gates/style-r2/aggregate.py   # writes style-r2/summary.json

Secondary-authority conventions (C-21..C-26, docs/dev/notes/research/alt-impl/BRIEF.md) are counted apart.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SECONDARY = {f"C-{n}" for n in range(21, 27)}
# round 1, STYLE.md "Deviations (counted)": module of each file (ontology scopes 11-14)
ROUND1 = {
    "11": {"C-21": 1, "C-14": 3, "C-16": 1, "C-17": 4},   # Ledger.cls; LedgerApply/LedgerStats/LedgerRevision; changeset.py; guard.py, _engine/ledger.py
    "12": {"C-7": 3, "C-8": 6, "C-14": 2, "C-9": 1},      # Eraser.cls, GraphStores.cls
    "13": {},
    "14": {"C-17": 2},                                    # replay.py
}


# One C-17 calibration for every group (round 1's rulings, written down by G1): a broad catch on a data-changing path
# is a deviation when its handler is silent or logs at DEBUG/INFO only; when a WARNING/ERROR line names what was not
# done (or a result field carries it) it is borderline. G2 and G4 counted these seven WARNING/ERROR-logged cases;
# moved to borderline here (each checked at the pin by the lane).
RECLASSIFY = {
    "D-04-11": "backfill_deg2p_exact: WARNING names the failure and the docstring documents 0 (_engine/schema.py:2958-2963)",
    "D-04-13": "bulk_load_session: WARNING 'final sync() failed' (_engine/nodes_edges.py:496-499)",
    "D-05-07": "temporal mirror: WARNING names the endpoint/edge not written (_engine/temporal.py:114-118, 324-332)",
    "D-05-08": "temporal mirror (bulk): WARNING names the edge not written (_engine/temporal.py:469-473)",
    "D-16-07": "fhir_event lazy-vec: WARNING names the node (api/routers/fhir_event.py:164-165)",
    "D-17-03": "insert_vector: ERROR log and return False (dbapi_utils.py:141-167)",
    "D-18-06": "restore: WARNING 'FHIR table DDL failed' (_engine/snapshot.py:1229-1231)",
}
# Items G1 left not reviewed (STYLE-G1.md L-1), reviewed by the lane: scripts/setup_security.sql was reviewed in full by
# G4 (module 17); schema.py:1640-1842 conforms (rewrite_schema_text at :1677, :1729; per-index status returned and a
# WARNING per index not rebuilt at :1764-1771); scripts/setup/__init__.py (a repo sample-data loader named by no scope,
# attached to module 01 with setup) has two deviations:
LANE_ADDED = {
    "01": [
        {"id": "D-01-L1", "convention": "C-17", "where": "scripts/setup/__init__.py:153-157",
         "what": "_ensure_nodes_exist: every failed node INSERT dropped with `except Exception: pass`, then commit"},
        {"id": "D-01-L2", "convention": "C-35", "where": "scripts/setup/__init__.py:155, 186-192, 212-217",
         "what": "unqualified `INSERT ... INTO nodes` before the schema is set; Graph_KG hard-coded whatever the recorded "
                 "IVG Schema, and a failed SET SCHEMA swallowed (`pass`)"},
    ],
}


def main() -> None:
    per = {m: {"by_convention": dict(v), "source": "round 1 (STYLE.md)"} for m, v in ROUND1.items()}
    per["00"] = {"by_convention": {}, "source": "lane (no files of its own; system-wide checks)"}
    candidates = []
    for f in sorted(HERE.glob("counts-G*.json")):
        d = json.loads(f.read_text())
        for m, v in d["modules"].items():
            m = m.zfill(2)
            devs = [x for x in v.get("deviations", []) if x["id"] not in RECLASSIFY] + LANE_ADDED.get(m, [])
            moved = [x["id"] for x in v.get("deviations", []) if x["id"] in RECLASSIFY]
            bc = {}
            for x in devs:
                bc[x["convention"]] = bc.get(x["convention"], 0) + 1
            per[m] = {"by_convention": bc, "source": f.name, "moved_to_borderline": moved,
                      "lane_added": [x["id"] for x in LANE_ADDED.get(m, [])],
                      "recorded_by_reviewer": dict(v.get("deviations_by_convention", {})),
                      "files_reviewed": len(v.get("files_reviewed", [])),
                      "borderline": (v.get("borderline") or 0) + len(moved),
                      "not_reviewed_by_group": sorted(p for p, c in v.get("coverage", {}).items()
                                                      if c not in ("full", "sweep")),
                      "sweep_files": sorted(p for p, c in v.get("coverage", {}).items() if c == "sweep")}
            for c in v.get("candidates", []):
                candidates.append(dict(c, module=m))
    rows, tot_p, tot_s = {}, 0, 0
    for m in sorted(per):
        bc = per[m]["by_convention"]
        p = sum(n for c, n in bc.items() if c not in SECONDARY)
        s = sum(n for c, n in bc.items() if c in SECONDARY)
        conv = sorted(c for c, n in bc.items() if n)
        rows[m] = {"deviations": p + s, "primary": p, "secondary": s, "conventions": conv,
                   **{k: v for k, v in per[m].items() if k != "by_convention"}, "by_convention": bc}
        tot_p += p
        tot_s += s
    out = {"modules": rows, "total": tot_p + tot_s, "total_primary": tot_p, "total_secondary": tot_s,
           "modules_reviewed": sorted(rows), "candidates": candidates}
    (HERE / "summary.json").write_text(json.dumps(out, indent=1))
    for m, r in rows.items():
        print(f"module {m}: {r['deviations']} deviations (primary {r['primary']}, secondary {r['secondary']}) "
              f"conventions {r['conventions']}")
    print(f"total {out['total']} (primary {tot_p}, secondary {tot_s}); modules {len(rows)}; candidates {len(candidates)}")


if __name__ == "__main__":
    main()
