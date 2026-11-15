#!/usr/bin/env python3
"""Assemble refusals/decoders/decoders.json from the static map and the registered live logs (no IRIS).

    python build_decoders_json.py STATIC_JSON RUN_ID_07 RUN_ID_10 RUN_ID_18

Per module: every decoder / status map the static check enumerated (server and client path:lines, wire keys or
codes), the live case(s) that drove it (from the registered run's log, checked against its recorded sha256), the
result, and the finding it maps to. The case-to-decoder mapping is by the decoder label each live case carries.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPLETION = HERE.parents[1]

# live case decoder label prefix -> static entry name prefix (module, kind)
LINK = {
    "bm25_build <- Build": "bm25_build <- BM25Index.Build",
    "bm25_info/_index_graph <- Info": "bm25_info / _index_graph <- BM25Index.Info",
    "bm25_search _parse <- Search": "bm25_search <- BM25Index.Search/SearchCore",
    "bm25_search(report) <- SearchReport": "bm25_search(report=True) <- BM25Index.SearchReport",
    "bm25_upgrade <- Upgrade": "bm25_upgrade <- BM25Index.Upgrade",
    "bm25_insert/delete <- Insert/Delete": "bm25_insert / bm25_delete <- BM25Index.Insert / Delete (integer)",
    "_build_index_registry <- List": "BM25Index.List comma-joined names -> _build_index_registry split(',') + strip()",
    "bm25_build/bm25_info <- Build/Info": "Build/Info graph string encoding",
    "kg_TXT error-text map / row decoder": "kg_TXT iFind error-text -> LIKE fallback / warning / raise",
    "_scored_node_rows <- PageRank.RunJson": "_scored_node_rows <- PageRank.RunJson / PageRankGlobalJson",
    "_scored_node_rows <- PageRankGlobalJson": "_kg_pagerank_global fallback <- PageRank.PageRankGlobalJson",
    "_membership_rows <- Algorithms.WCCJson": "_membership_rows <- Algorithms.WCCJson / CDLPJson",
    "_membership_rows <- Algorithms.CDLPJson": "_membership_rows <- Algorithms.WCCJson / CDLPJson",
    "ALG-I5 store error -> exception": "ALG-I5 store error -> exception (algorithms.py)",
    "_subgraph_payload <- Subgraph.SubgraphJson": "_subgraph_payload / kg_SUBGRAPH <- Subgraph.SubgraphJson",
    "execute_degree_centrality <- DegreeCentralityJson": "execute_degree_centrality <- Centrality.DegreeCentralityJson",
    "khop <- Traversal.BFSFastJson": "khop <- TraversalBFS.BFSFastJson",
    "error-text maps (_RUNJSON_MISSING, degree fallback)": "_RUNJSON_MISSING (PPR fast path falls back only on a missing RunJson)",
    "_scored_node_rows <- ArnoAccel (Native Reader)": "_scored_node_rows <- ArnoAccel *NativeJson (Native Reader)",
    "snapshot_info <- metadata.json": "snapshot_info / restore_snapshot <- metadata.json (save_snapshot)",
    "global value line <- NodeValueJSON": "global value line <- Snapshot.NodeValueJSON/Encode; import -> SetNodeJSON/Decode",
    "global value line (plain 'v' form) <- str(value)": "global value line <- Snapshot.NodeValueJSON/Encode; import -> SetNodeJSON/Decode",
    "SQL row encoder/decoder (ndjson rows)": "SQL table rows (save_snapshot ndjson encoder -> restore_snapshot INSERT decoder)",
    "_table_missing <- driver SQLCODE text": "_table_missing: SQLCODE -30 -> skip lazily created table, else SnapshotReadError",
    "POST /admin/snapshot HTTP status map": "POST /admin/snapshot HTTP status map",
}


def load_run(rid: str):
    rec = json.loads((COMPLETION / "evidence" / "runs" / f"{rid}.json").read_text())
    p = Path(rec["log"].replace("$RUN_DIR", os.environ["RUN_DIR"]))
    data = p.read_bytes()
    if hashlib.sha256(data).hexdigest() != rec["log_sha256"]:
        raise SystemExit(f"{rid}: log differs from its registered hash")
    return rec, json.loads(data)


def main() -> int:
    static = json.loads(Path(sys.argv[1]).read_text())
    runs = dict(zip(("07", "10", "18"), sys.argv[2:5]))
    out = {"gate": "3.5-decoders", "pin": static["pin"], "static_check": "run:rx-dec-map", "modules": {}}
    entries = {}
    for d in static["decoders"]:
        entries[d["name"]] = {"module": d["module"], "name": d["name"], "kind": d["kind"],
                              "server": d.get("server"), "client": d.get("client"),
                              "wire": d.get("wire_keys", d.get("server_forms", d.get("written"))),
                              "decoder_reads": d.get("decoder_reads", d.get("client_reads", d.get("read"))),
                              "dead_reads": d.get("dead_reads", []),
                              "dead_reads_explained": d.get("dead_reads_explained", {}),
                              "static": {k: d[k] for k in ("doc_not_emitted", "undocumented", "dropped",
                                                           "written_not_read", "undecoded_forms", "notes")
                                         if d.get(k)},
                              "live_cases": [], "result": None, "findings": []}
    for m in static["maps"]:
        entries[m["name"]] = {"module": m["module"], "name": m["name"], "kind": "status-map", "ref": m.get("ref"),
                              "codes": m.get("tokens", m.get("pattern", m.get("route_codes"))),
                              "middleware_codes": m.get("middleware_codes"), "live_cases": [], "result": None,
                              "findings": []}
    i5 = static["alg_i5"]
    entries[i5["name"]] = {"module": "10", "name": i5["name"], "kind": "error-propagation-map", "ref": i5["ref"],
                           "mapped": i5["mapped"], "unmapped": i5["unmapped"], "live_cases": [], "result": None,
                           "findings": []}
    ls = static["list_separator"]
    entries[ls["name"]] = {"module": "07", "name": ls["name"], "kind": "delimited-string", "server": ls["server"],
                           "client": ls["client"], "static": {k: ls[k] for k in ("separator",
                                                                                  "name_validator_refuses_separator")},
                           "live_cases": [], "result": None, "findings": []}
    entries["Build/Info graph string encoding"] = {
        "module": "07", "name": "Build/Info graph string encoding", "kind": "json-literal-encoding",
        "static": [e for e in static["encodings"] if e.get("string")], "live_cases": [], "result": None, "findings": []}
    entries["bm25_insert / bm25_delete <- BM25Index.Insert / Delete (integer)"] = {
        "module": "07", "name": "bm25_insert / bm25_delete <- BM25Index.Insert / Delete (integer)", "kind": "integer",
        "server": ["iris_src/src/Graph/KG/BM25Index.cls:442-493", "iris_src/src/Graph/KG/BM25Index.cls:496-514"],
        "client": ["iris_vector_graph/_engine/vector.py:1840-1856"], "live_cases": [], "result": None, "findings": []}
    entries["_scored_node_rows <- ArnoAccel *NativeJson (Native Reader)"] = {
        "module": "10", "name": "_scored_node_rows <- ArnoAccel *NativeJson (Native Reader)", "kind": "projecting",
        "server": ["iris_src/src/Graph/KG/ArnoAccel.cls"], "client": ["iris_vector_graph/stores/iris_sql_store.py:639-658"],
        "live_cases": [], "result": None, "findings": []}
    entries["SQL table rows (save_snapshot ndjson encoder -> restore_snapshot INSERT decoder)"] = {
        "module": "18", "name": "SQL table rows (save_snapshot ndjson encoder -> restore_snapshot INSERT decoder)",
        "kind": "row-encoding", "client": ["iris_vector_graph/_engine/snapshot.py:863-905",
                                           "iris_vector_graph/_engine/snapshot.py:1234-1300"],
        "live_cases": [], "result": None, "findings": []}
    entries["bm25_search _parse leading-dot patch"] = {
        "module": "07", "name": "bm25_search _parse leading-dot patch", "kind": "text-patch",
        "ref": static["text_patch"]["ref"], "pattern": static["text_patch"]["pattern"], "live_cases": [],
        "result": None, "findings": []}
    LINK["bm25_search _parse <- Search"] = ["bm25_search <- BM25Index.Search/SearchCore", "bm25_search _parse leading-dot patch"]
    LINK["bm25_search(report) <- SearchReport"] = ["bm25_search(report=True) <- BM25Index.SearchReport",
                                                   "bm25_search _parse leading-dot patch"]
    LINK["global value line <- NodeValueJSON"] = [LINK["global value line <- NodeValueJSON"]]
    for mod, rid in runs.items():
        rec, doc = load_run(rid)
        for c in doc["cases"]:
            if "decoder" not in c:
                continue
            targets = LINK.get(c["decoder"])
            for target in ([targets] if isinstance(targets, str) else (targets or [])):
                if target not in entries:
                    continue
                e = entries[target]
                e["live_cases"].append({"run": rid, "case": c["case"], "match": c.get("match"), "why": c.get("why"),
                                        "finding": c.get("finding"), "blocked": c.get("blocked")})
                if c.get("finding") and c["finding"] not in e["findings"]:
                    e["findings"].append(c["finding"])
    for e in entries.values():
        ms = [c["match"] for c in e["live_cases"]]
        if not ms:
            e["result"] = "static only (not driven live)"
        elif any(m is False for m in ms):
            e["result"] = "mismatch"
        elif all(m is True for m in ms):
            e["result"] = "match"
        else:
            e["result"] = "not decided (blocked)"
        out["modules"].setdefault(e["module"], []).append(e)
    extra = json.loads(Path(sys.argv[5]).read_text()) if len(sys.argv) > 5 else {}
    for name, fs in extra.items():
        if name in entries:
            for f in fs:
                if f not in entries[name]["findings"]:
                    entries[name]["findings"].append(f)
    (HERE / "decoders.json").write_text(json.dumps(out, indent=1) + "\n")
    for mod, es in sorted(out["modules"].items()):
        print(mod, {r: sum(1 for e in es if e["result"] == r) for r in sorted({e["result"] for e in es})})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
