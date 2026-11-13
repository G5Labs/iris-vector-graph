"""Merge journal validations (live/breadth-a/journal/J*.json) into footprints/NN.json. Idempotent; run after
models/breadth-a/tools/footprints.py regenerates the footprints.

Each validated entry point gets `journal` = the observation and a classification of every mismatch:
- `extraction-gap`: the source does write the store (cited) but the static extraction missed the hop; the store is
  added to `writes` with `confidence: "journal"`;
- `product`: a write the source does not declare or a write outside a transaction the source claims (finding);
- `harness`: the oracle could not decode the run (no conclusion).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = "breadth-a-journal-footprints"

GAPS = {
    "J12": ("extraction-gap", "TraversalBuild.BuildKG rebuilds the functional indexes with %BuildIndices "
            "(iris_src/src/Graph/KG/TraversalBuild.cls:126-131), which writes the index storage of rdf_edges and "
            "rdf_labels; with 8 parallel jobs (the journal shows two other server processes) and after BuildKG's "
            "TCommit, so the ^KG refill is journaled outside any transaction, as the method's own comment says "
            "(TraversalBuild.cls:55-65, 150-158: a failed rebuild has already shown readers a partial ^KG)."),
    "J13": ("extraction-gap", "create_edge_temporal -> store.write_temporal_edge -> Graph.KG.TemporalIndex.InsertEdge -> "
            "WriteStores writes ^KG tout/tin/bucket/tagg/tlast (iris_src/src/Graph/KG/TemporalIndex.cls:80-130); the "
            "extractor did not follow the store hop. The journal also shows these written outside any transaction "
            "while the structural row is inside one (see F-C0501)."),
    "J14": ("extraction-gap", "as J13 (mode update: TemporalIndex.cls:80-83 then the same stores)."),
    "J15": ("extraction-gap", "delete_edge_temporal -> store.delete_temporal_edge -> TemporalIndex.DeleteTemporalEdge / "
            "RemoveTemporalRow kill tout/tin and decrement bucket/tagg (TemporalIndex.cls:325-370); then the engine's "
            "delete_edge removes the owned row (iris_vector_graph/_engine/temporal.py:374-388); the extractor did not "
            "follow the store hop."),
    "J18": ("extraction-gap", "store_embeddings -> _route_for_write(create=True) runs CREATE TABLE for the new route "
            "(class compile: ^oddDEP/^oddTSQL, the new table's storage ^t52S.D427.*) and inserts the registry row, "
            "each committed before the node check refuses the batch (iris_vector_graph/_engine/embeddings.py:470-558, "
            "1064-1084): the write-before-refusal is F-0615."),
    "J21": ("extraction-gap", "initialize_schema rewrites the schema record through the Native API (schema_name.write_record, "
            "iris_vector_graph/schema_name.py:194-198: ^IVG.Deploy('schema') and its 'recorded' stamp); the extractor sees "
            "ObjectScript Set and SQL only. On an already set-up namespace that record is the only data write in AUDITA's "
            "database; the class compile runs in worker processes (empty transactions in the journal)."),
    "J17": ("harness", "traces/journal.py's reader raised <VECTOR> encoding a $vector value; no conclusion."),
    "J19": ("harness", "as J17."),
}

TXN_NOTES = {
    "J01": "one committed transaction in the caller's process (WriteTxn nesting levels journaled as one outermost unit).",
    "J02": "one committed transaction; the row hook's ^KG out/in inside it; gen/__version as $Increment (non-transactional).",
    "J03": "duplicate swallowed: a transaction with no write (the marked row is not adopted: F-0304).",
    "J05": "engine on the caller's DB-API connection: the 3 server-loader chunks nest in one outermost transaction of "
           "one process (contrast the from_connect run breadth-a-live-03-bulk-atomicity: 2 transactions in another process).",
    "J06": "as J05 for bulk_ingest_edges (1,500 edges, 2 chunks, one outermost transaction).",
    "J07": "BulkLoader.load_edges commits per batch: two transactions (endpoint registration, edges), not one.",
    "J08": "GraphMode.Set: ^IVG.GraphMode killed with no transaction and no lock (corroborates F-0207).",
    "J09": "PutShadow called with no caller transaction: out/in written outside any transaction (by design of the call).",
    "J10": "Reweight: out/in/__version, no lock, no generation (F-0407).",
    "J11": "Adj.Degree stores ^KG('degc') (a reader that writes), no transaction.",
    "J16": "Purge: temporal stores killed for every graph; no rdf_edges write (F-0507).",
    "J20": "ProcessBatch: ^EmbedQueue status set with no vector written (F-0604).",
}


def main():
    jdir = HERE / "journal"
    by_mod = {}
    for p in sorted(jdir.glob("J*.json")):
        j = json.loads(p.read_text())
        by_mod.setdefault(j["module"], []).append(j)
    for mod, items in by_mod.items():
        fp_path = ROOT / "footprints" / f"{mod}.json"
        fp = json.loads(fp_path.read_text())
        idx = {e["id"]: e for e in fp["entry_points"]}
        fp["journal_validation"] = []
        for j in items:
            obs = j.get("observed") or {}
            kind, why = GAPS.get(j["id"], (None, None))
            und = j.get("undeclared_writes") or []
            rec = {
                "candidate": j["id"], "footprint": j["footprint"], "run": RUN,
                "result_file": f"experiment/playbook-completion/live/breadth-a/journal/{j['id']}.json",
                "call": j.get("call"),
                "pids": obs.get("pids"), "stores_written": obs.get("stores_written"),
                "outermost_transactions": obs.get("outermost_transactions"),
                "written_with_no_transaction_open": obs.get("written_with_no_transaction_open"),
                "undeclared_writes": und,
                "verdict": ("harness error" if kind == "harness" else
                            "covered" if not und else f"mismatch: {kind or 'unclassified'}"),
                "mismatch_classification": kind, "explanation": why, "transaction_note": TXN_NOTES.get(j["id"]),
            }
            fp["journal_validation"].append(rec)
            e = idx.get(j["footprint"])
            if e is None:
                continue
            e.setdefault("journal", None)
            prev = e["journal"] if isinstance(e["journal"], list) else ([] if e["journal"] is None else [e["journal"]])
            prev = [x for x in prev if x.get("candidate") != j["id"]]
            e["journal"] = prev + [rec]
            if kind == "extraction-gap":
                have = {w["store"] for w in e.get("writes", [])}
                for s in und:
                    if s not in have:
                        e.setdefault("writes", []).append({"store": s, "at": [f"journal:{RUN}:{j['id']}"],
                                                           "confidence": "journal"})
        if mod == "03":
            p305 = HERE / "results" / "p0305_bulk_chunks_not_one_transaction.json"
            if p305.exists():
                r = json.loads(p305.read_text())
                o = r.get("observed", {})
                rec = {"candidate": "J05-from_connect", "footprint": "py:IRISGraphEngine.bulk_create_nodes",
                       "run": "breadth-a-live-03-bulk-atomicity",
                       "result_file": "experiment/playbook-completion/live/breadth-a/results/p0305_bulk_chunks_not_one_transaction.json",
                       "call": str(o.get("call")), "pids": [o.get("cursor_pid")] + sorted({u["pid"] for u in o.get("journal_node_transactions", [])}),
                       "stores_written": sorted({s2 for u in o.get("journal_node_transactions", []) for s2 in u["stores"]}),
                       "outermost_transactions": o.get("journal_node_transactions"),
                       "written_with_no_transaction_open": [], "undeclared_writes": [],
                       "verdict": "mismatch: product",
                       "mismatch_classification": "product",
                       "explanation": "every write is declared, but on a from_connect engine the server-loader chunks commit in "
                                      "the engine's Native API process as separate transactions, outside the WriteTxn the "
                                      "source opens on the cursor (nodes_edges.py:1718-1757) and against USER_GUIDE.md:238-241: "
                                      "F-0305", "transaction_note": "contrast J05 (engine on the caller's connection): one transaction"}
                fp["journal_validation"].append(rec)
                e = idx.get(rec["footprint"])
                if e is not None:
                    prev = e["journal"] if isinstance(e.get("journal"), list) else []
                    e["journal"] = [x for x in prev if x.get("candidate") != rec["candidate"]] + [rec]
        n_cov = sum(1 for r in fp["journal_validation"] if r["verdict"] == "covered")
        fp["journal_summary"] = {"validated": len(fp["journal_validation"]), "covered": n_cov,
                                 "extraction_gaps": sum(1 for r in fp["journal_validation"] if r["mismatch_classification"] == "extraction-gap"),
                                 "harness_errors": sum(1 for r in fp["journal_validation"] if r["mismatch_classification"] == "harness"),
                                 "product_mismatches": sum(1 for r in fp["journal_validation"] if r["mismatch_classification"] == "product")}
        fp_path.write_text(json.dumps(fp, indent=1) + "\n")
        print(mod, fp["journal_summary"])


if __name__ == "__main__":
    main()
