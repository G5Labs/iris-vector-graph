#!/usr/bin/env python3
"""Write module 07's audit artifacts from the reviewed source reading and the registered runs.

    python experiment/playbook-completion/live/breadth-b/07_artifacts.py

Outputs experiment/playbook-completion/{footprints,findings/audit,modules}/07.json. Journal-validation fields are read
from the live logs ($RUN_DIR/breadth-b/live/07-*.json); model results from models/breadth-b/results/m07-*.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMP = HERE.parents[1]
RUN = Path(os.environ["RUN_DIR"]) / "breadth-b" / "live"
INV = json.loads((COMP / "models/breadth-b/inventory/07.json").read_text())
FP_LOG = json.loads((RUN / "07-fp-writers.json").read_text())
RACE = json.loads((RUN / "07-f0701-race.json").read_text())
NEST = json.loads((RUN / "07-fc0702-nested-rollback.json").read_text())
MC = {p.stem: json.loads(p.read_text()) for p in (COMP / "models/breadth-b/results").glob("m07-*.json")}

B = "iris_src/src/Graph/KG/BM25Index.cls"
V = "iris_vector_graph/_engine/vector.py"
LOCK = {"lock": "^BM25Idx(name,\"lock\")", "mode": "Lock + (exclusive, incremental)",
        "timeout": "^BM25Idx(name,\"cfg\",\"lock_timeout\") else LOCKTIMEOUT=30 s", "source": f"{B}:380-410"}
STOP = "^BM25Idx(\"__stop__\",word) (InitStopwords, only when ^BM25Idx(\"__stop__\",\"the\") is missing)"


def jv(key, declared, notes=""):
    e = FP_LOG[key]
    obs = sorted({x for v in e["footprint"].values() for x in v})
    outside = len(e["outside_txn"])
    kinds = sorted({t["kind"] for t in e["transactions"]})
    return {"log": "$RUN_DIR/breadth-b/live/07-fp-writers.json#" + key, "run_id": "b-07-fp-writers",
            "declared_stores": declared, "observed_stores": obs, "match": set(obs) <= set(declared),
            "undeclared": sorted(set(obs) - set(declared)), "records": e["n_records"],
            "outside_txn": outside, "transaction_units": kinds, "notes": notes}


def ep(id_, role, source, reads, writes, transaction, locks=(), nolock=(), journal=None, notes=""):
    return {"id": id_, "role": role, "source": source,
            "reads": {"tables": reads[0], "globals": reads[1]}, "writes": {"tables": writes[0], "globals": writes[1]},
            "transaction": transaction, "locks": list(locks), "nolock": list(nolock),
            "journal_validation": journal, "notes": notes}


G = ["global:^BM25Idx"]
FPS = [
    ep("cls:Graph.KG.BM25Index.Build", "writer", f"{B}:97-175 (IndexDoc :178-204, Tokenize :56-87, InitStopwords :41-50)",
       (["Graph_KG.nodes", "Graph_KG.rdf_props"], ["^BM25Idx(\"__stop__\")"]),
       ([], ["^BM25Idx(name) (Kill :99, tf/df/doc/len :194-201, cfg N/totalLen/k1/b/vocab_size/graph/schema :160-170)", STOP]),
       "none: no TSTART; every write auto-committed one by one (journal: 106 of 106 records outside a transaction; race run: 30008 of 30008)",
       [], ["SQL read through %SQL.Statement at default isolation (read uncommitted, P-0002); no %NOLOCK hint"],
       jv("Build", G, "matches the source; the writes outside a transaction contradict ADR-0007 'every write under an index-level lock in a transaction' and spec 044 FR-016/FR-018 'at every committed point' (F-0701)"),
       "Takes no write lock (F-0701). Schema set last (:170)."),
    ep("cls:Graph.KG.BM25Index.Search", "reader", f"{B}:215-218 -> SearchCore :236-374",
       ([], ["^BM25Idx(name,cfg/df/tf/len/idf/avgdl)", "^BM25Idx(\"__stop__\")"]),
       ([], ["^||bm25scores, ^||bm25sorted, ^||bm25skip, ^||bm25fallback (process-private, not journaled)", STOP]),
       "none (reads committed and uncommitted data alike; a Search during a Build sees the build's partial state)",
       [], ["no lock (spec 044 FR-019: Search takes no lock)"],
       jv("Search-rebuilds-stopwords", G, "a Search of an existing index re-creates a missing stopword list: 77 SETs outside a transaction; a Search of a missing index returns before tokenizing (no write)"),
       "Returns [] when N is 0 or absent (:241) before tokenizing."),
    ep("cls:Graph.KG.BM25Index.SearchReport", "reader", f"{B}:221-234", ([], ["as Search"]),
       ([], ["^||bm25skip, ^||bm25fallback (process-private)", STOP]), "none", [], [],
       jv("SearchReport", [], "no journaled write (stopword list present)"), ""),
    ep("cls:Graph.KG.BM25Index.Insert", "writer", f"{B}:442-493 (RemoveDoc :416-437, RequireWritable :385-394, LockWrite :403-410)",
       ([], ["^BM25Idx(name,cfg N/upgrading/schema/lock_timeout/vocab_size/totalLen, doc, len, df)", "^BM25Idx(\"__stop__\")"]),
       ([], ["^BM25Idx(name, cfg N/totalLen/vocab_size/schema, tf, df, doc, len)", STOP + " (Tokenize runs before the lock and the transaction, :447)"]),
       f"own TSTART/TCOMMIT {B}:460-485 nested in any caller transaction; on error `If $TLevel > 0 TRollback` (:487) with no level ends EVERY level, the caller's too (F-C0702, live)",
       [LOCK], [],
       jv("Insert-new", G, "one transaction per Insert (Insert-replace: 19 records in 1 transaction; Insert creating a missing index: 14 records, no cfg graph written, F-0705)"),
       "A first Insert creates a schema 2 header with no recorded graph (:461-466)."),
    ep("cls:Graph.KG.BM25Index.Delete", "writer", f"{B}:496-514", ([], ["^BM25Idx(name,cfg N/upgrading/schema, doc, len, df)"]),
       ([], ["^BM25Idx(name, tf, df, doc, len, cfg N/totalLen/vocab_size)"]),
       f"own TSTART/TCOMMIT {B}:504-506; error path `If $TLevel > 0 TRollback` (:508) ends every level (F-C0702 pattern)",
       [LOCK], [], jv("Delete", G, "7 records in one transaction; Delete of an absent document writes nothing"),
       "Checks N before the lock (:498): a Delete that passed it before a concurrent Build's Kill runs RemoveDoc with $Get defaults (N can go negative; model only)."),
    ep("cls:Graph.KG.BM25Index.Upgrade", "writer", f"{B}:526-581", ([], ["^BM25Idx(name,cfg, tf, len)"]),
       ([], ["^BM25Idx(name, cfg upgrading/N/totalLen/vocab_size/schema/avgdl, df, doc, idf)"]),
       "none: flag, lock, one pass of plain SETs/KILLs with no TSTART (:533-578); 'safe to re-run after an interruption' (:524)",
       [LOCK], [],
       jv("Upgrade-schema2", [], "only the no-op path (schema 2: {upgraded:0, already:1}) is validated: no journaled write. The schema 1 -> 2 path needs a schema-1 index, which the pin's API cannot create (Build and Insert write schema 2); writing one directly would write a product global, outside CONVENTIONS' scratch rule. Not validated live."),
       "Sets the upgrading flag before taking the lock (:533-535)."),
    ep("cls:Graph.KG.BM25Index.Drop", "writer", f"{B}:587-591", ([], []), ([], ["^BM25Idx(name) (one Kill)"]),
       "none (one KILL, auto-committed)", [], ["no lock: does not wait for a writer that holds the write lock (TXT-B7.1, F-0701)"],
       jv("Drop", G, "one KILL outside a transaction; Drop('__stop__') is accepted and kills the stopword list (F-0706)"), ""),
    ep("cls:Graph.KG.BM25Index.Info", "reader", f"{B}:597-615", ([], ["^BM25Idx(name,cfg N/schema/totalLen/avgdl/vocab_size/graph)"]), ([], []),
       "none", [], ["no lock"], jv("Info", [], "no write"), "Answers graph \"\" when the cfg graph subscript is absent (:612), F-0705."),
    ep("cls:Graph.KG.BM25Index.SearchProc", "reader", f"{B}:621-624", ([], ["as Search"]), ([], [STOP]), "none", [], [], None, "Search with k only."),
    ep("cls:Graph.KG.BM25Index.List", "reader", f"{B}:628-633", ([], ["^BM25Idx first subscripts"]), ([], []), "none", [], [], None, "Skips __stop__."),
    ep("cls:Graph.KG.SqlProcs.kgBM25", "reader", "iris_src/src/Graph/KG/SqlProcs.cls:131-135", (["(privilege check on rdf_props)"], ["as Search"]), ([], [STOP]),
       "none", [], [], None, "SQL function kg_BM25; RequireSelect on rdf_props (Graph.KG.SqlPrivilege) before reading the global (TXT-X10)."),
    ep("cls:Graph.KG.PyOps.HybridSearch", "reader", "iris_src/src/Graph/KG/PyOps.cls:370-421",
       (["Graph_KG.kg_RRF_FUSE / kg_KNN_VEC / kg_TXT (procedures)", "Graph_KG.docs", "Graph_KG.kg_NodeEmbeddings or the graph's vector route"], []), ([], []),
       "none (embedded Python, SQL reads through ReadRows, PyOps.cls:200-219)", [], [], None, ""),
    ep("cls:Graph.KG.Service.HybridSearch", "reader", "iris_src/src/Graph/KG/Service.cls:286-302", (["as PyOps.HybridSearch"], []), ([], []), "none", [], [], None, "REST POST /hybridSearch body: vector, text, k, c, graph."),
    ep("route:POST /hybridSearch", "reader", "iris_src/src/Graph/KG/Service.cls:8", (["as PyOps.HybridSearch"], []), ([], []), "none", [], [], None, "%CSP.REST route."),
    ep("py:iris_vector_graph/fusion.py:RRFFusion.fuse_results", "pure", "iris_vector_graph/fusion.py:27-64", ([], []), ([], []), "n/a", [], [], None, "Missing item adds 0 (HD-0702)."),
    ep("py:iris_vector_graph/fusion.py:RRFFusion.weighted_fusion", "pure", "iris_vector_graph/fusion.py:67-97", ([], []), ([], []), "n/a", [], [], None, "Normalizes weights."),
    ep("py:iris_vector_graph/fusion.py:HybridSearchFusion.__init__", "pure", "iris_vector_graph/fusion.py:105-107", ([], []), ([], []), "n/a", [], [], None, ""),
    ep("py:iris_vector_graph/fusion.py:HybridSearchFusion.multi_modal_search", "reader", "iris_vector_graph/fusion.py:109-252",
       (["via engine.kg_KNN_VEC (kg_NodeEmbeddings / route), engine.kg_TXT (docs), engine.kg_NEIGHBORHOOD_EXPANSION (rdf_edges)"], []), ([], []),
       "none", [], [], None, "Vector and graph legs swallowed on error (:144-152, :193-195); text leg raises (:158-168)."),
    ep("py:iris_vector_graph/fusion.py:HybridSearchFusion.adaptive_search", "reader", "iris_vector_graph/fusion.py:254-310", (["as multi_modal_search; kg_TXT fallback"], []), ([], []), "none", [], [], None, "Answers [] when every path fails (:301-310)."),
    ep("py:iris_vector_graph/text_search.py:TextSearchEngine.__init__", "pure", "iris_vector_graph/text_search.py:22-29", ([], []), ([], []), "n/a", [], [], None, ""),
    ep("py:iris_vector_graph/text_search.py:TextSearchEngine.search_documents", "reader", "iris_vector_graph/text_search.py:31-94",
       (["docs (unqualified: resolves to SQLUSER.DOCS, SQLCODE -30 live)"], []), ([], []), "none", [], [], None, "%FIND(text, ?) is not IRIS syntax; fallback LIKE on the same unqualified table; [] on any error."),
    ep("py:iris_vector_graph/text_search.py:TextSearchEngine.search_entity_qualifiers", "reader", "iris_vector_graph/text_search.py:96-148", (["Graph_KG.rdf_edges (no graph_id predicate)"], []), ([], []), "none", [], [], None, "F-0711."),
    ep("py:iris_vector_graph/text_search.py:TextSearchEngine.extract_entity_names", "reader", "iris_vector_graph/text_search.py:150-194", (["Graph_KG.rdf_props (no graph_id predicate)"], []), ([], []), "none", [], [], None, "F-0711 (live: both graphs)."),
    ep("py:iris_vector_graph/text_search.py:TextSearchEngine.search_with_context", "reader", "iris_vector_graph/text_search.py:196-256", (["Graph_KG.rdf_props, Graph_KG.rdf_labels (label join on s alone)"], []), ([], []), "none", [], [], None, "F-0711 (live: both graphs)."),
    ep("py:iris_vector_graph/operators.py:IRISGraphOperators.kg_TXT", "reader", "iris_vector_graph/operators.py:30-35", (["as engine.kg_TXT"], []), ([], []), "none", [], [], None, "Shim."),
    ep("py:iris_vector_graph/operators.py:IRISGraphOperators.kg_RRF_FUSE", "reader", "iris_vector_graph/operators.py:37-44", (["as engine.kg_RRF_FUSE"], []), ([], []), "none", [], [], None, "Shim."),
    ep("py:iris_vector_graph/operators.py:IRISGraphOperators.kg_RERANK", "reader", "iris_vector_graph/operators.py:143-146", (["as engine kg_RERANK (fused leg rerank)"], []), ([], []), "none", [], [], None, ""),
    ep("eng:IRISGraphEngine.bm25_build", "writer", f"{V}:1749-1785", (["as Build"], []), ([], ["as Build"]), "as Build (none)", [], [],
       jv("Build", G, "captured through the engine call (same IRIS process)"), "Validates with BM25BuildInput (blank name only; __stop__ accepted, F-0706)."),
    ep("eng:IRISGraphEngine.bm25_delete", "writer", f"{V}:1849-1855", ([], ["as Delete"]), ([], ["as Delete"]), "as Delete", [LOCK], [], jv("Delete", G), ""),
    ep("eng:IRISGraphEngine.bm25_drop", "writer", f"{V}:1868-1870", ([], []), ([], ["as Drop"]), "as Drop (none)", [], [], jv("Drop", G), ""),
    ep("eng:IRISGraphEngine.bm25_info", "reader", f"{V}:1871-1879", ([], ["as Info"]), ([], []), "none", [], [], jv("Info", []), ""),
    ep("eng:IRISGraphEngine.bm25_insert", "writer", f"{V}:1840-1848", ([], ["as Insert"]), ([], ["as Insert"]), "as Insert; inside a caller's transaction a failure ends the caller's transaction (F-C0702, run b-07-fc0702-nested-rollback)", [LOCK], [], jv("Insert-new", G), ""),
    ep("eng:IRISGraphEngine.bm25_search", "reader", f"{V}:1786-1839", ([], ["as Search/SearchReport"]), ([], [STOP]), "none", [], [], jv("Search", []), "Refuses blank query (BM25SearchInput) contrary to spec 044 US2 sc.4 (F-0708)."),
    ep("eng:IRISGraphEngine.bm25_upgrade", "writer", f"{V}:1857-1866", ([], ["as Upgrade"]), ([], ["as Upgrade"]), "as Upgrade (none)", [LOCK], [], jv("Upgrade-schema2", []), ""),
    ep("eng:IRISGraphEngine.kg_RRF_FUSE", "reader", f"{V}:1382-1452",
       (["kg_NodeEmbeddings / IVF (^IVF) / route (VEC module)", "^BM25Idx via bm25_search and bm25_info"], []), ([], [STOP]),
       "none; both legs inside one try (:1421-1436): a failure logs and drops the remaining legs", [], [], None,
       "Leg index chosen by recorded graph (_fusion_leg_index :187-226); Info's \"\" for an absent graph is read as the default graph (F-0705)."),
    ep("eng:IRISGraphEngine.kg_TXT", "reader", f"{V}:917-1054", (["Graph_KG.docs (iFind idx_docs_text_ifind, else LIKE)"], []), ([], []), "none", [], [], None, "No BM25 fallback (spec 044 FR-012, HD-0703)."),
    ep("cypher:ivg.bm25.search", "reader", "iris_vector_graph/cypher/translator.py:3145-3200 (graph rows :3125-3142)", (["kg_BM25 SQL function -> ^BM25Idx; rdf_labels, rdf_props for the node"], []), ([], [STOP]), "the Cypher statement's (read)", [], [], None, "Under USE GRAPH no index-graph check (F-0707)."),
    ep("cypher:ivg.retrieve", "reader", "iris_vector_graph/cypher/translator.py:3248-3360", (["kg_BM25 (^BM25Idx bm25_name), the graph's vector table"], []), ([], [STOP]), "the Cypher statement's (read)", [], [], None, "BM25 arm reads bm25_name with no graph check (F-0707)."),
    ep("sqlfn:kg_TXT", "reader", "iris_vector_graph/schema.py:2485-2503", (["Graph_KG.docs via idx_docs_text_ifind (%ID %FIND search_index)"], []), ([], []), "none", [], [], None, "Generated SQL procedure."),
    ep("sqlfn:kg_RRF_FUSE", "reader", "iris_vector_graph/schema.py:2526-2560", (["kg_KNN_VEC, kg_TXT (docs)"], []), ([], []), "none", [], [], None, "Missing rank at 10^9 (HD-0702)."),
    ep("py:iris_vector_graph/index_protocol.py:Index.build[fulltext]", "writer", "iris_vector_graph/index_protocol.py:83-84 -> iris_vector_graph/_engine/vector.py:299-310", (["as Build"], []), ([], ["as Build"]),
       "as Build; raises IndexNotBuiltError after Build already replaced the index (F-0704, live b-07-f0704)", [], [], None, ""),
    ep("py:iris_vector_graph/index_protocol.py:Index.search[fulltext]", "reader", "iris_vector_graph/index_protocol.py:92-95", ([], ["as Info then Search"]), ([], []), "none", [], [], None, ""),
    ep("py:iris_vector_graph/index_protocol.py:Index.insert[fulltext]", "writer", "iris_vector_graph/index_protocol.py:97-98", ([], ["as Insert"]), ([], ["as Insert"]), "as Insert", [LOCK], [], None, ""),
    ep("py:iris_vector_graph/index_protocol.py:Index.drop[fulltext]", "writer", "iris_vector_graph/index_protocol.py:100-102", ([], []), ([], ["as Drop"]), "as Drop (none)", [], [], None, ""),
    ep("py:iris_vector_graph/index_protocol.py:Index.info[fulltext]", "reader", "iris_vector_graph/index_protocol.py:104-105", ([], ["as Info"]), ([], []), "none", [], [], None, ""),
    ep("eng:IRISGraphEngine.create_index[replace]", "writer", f"{V}:243-259", ([], []), ([], ["as Drop when replace=True"]), "as Drop (none)", [], [], None, ""),
    ep("eng:IRISGraphEngine.list_indexes[bm25 registry]", "reader", f"{V}:84-120", ([], ["^BM25Idx first subscripts (embedded gref walk, no __stop__ skip) or BM25Index.List"]), ([], []), "none", [], [], None, "F-0706 (embedded mode only)."),
    ep("py:iris_vector_graph/schema.py:GraphSchema.global_indexes", "reader", "iris_vector_graph/schema.py:1950-1966", ([], ["BM25Index.List"]), ([], []), "none", [], [], None, "SHOW INDEXES / status()."),
]


def write_footprints():
    ids = {e["id"] for e in INV["entry_points"]}
    have = {f["id"] for f in FPS}
    assert ids == have, (ids - have, have - ids)
    jvs = [f for f in FPS if f["journal_validation"]]
    out = {"module": "07", "pin": "3eaa79cf", "inventory": "experiment/playbook-completion/models/breadth-b/inventory/07.json",
           "oracle": "experiment/playbook-completion/traces/journal.py via live/breadth-b/blive.capture on AUDITB",
           "summary": {"entry_points": len(FPS), "writers": sum(1 for f in FPS if f["role"] == "writer"),
                       "readers": sum(1 for f in FPS if f["role"] == "reader"), "pure": sum(1 for f in FPS if f["role"] == "pure"),
                       "journal_validated": len(jvs),
                       "journal_validated_distinct_operations": sorted({f["journal_validation"]["log"].split("#")[1] for f in jvs}),
                       "store_mismatches": sum(1 for f in jvs if not f["journal_validation"]["match"]),
                       "writes_outside_a_transaction_claimed_atomic": ["cls:Graph.KG.BM25Index.Build (F-0701)", "cls:Graph.KG.BM25Index.Drop (F-0701)"],
                       "additional_journal_runs": {"b-07-f0701-race": RACE["journal_by_process"],
                                                   "b-07-fc0702-nested-rollback": {k: v["journal_transactions"] for k, v in NEST.items() if isinstance(v, dict) and "journal_transactions" in v}}},
           "entry_points": FPS}
    (COMP / "footprints/07.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


def ev(*pairs):
    return [{"kind": k, "ref": r} for k, r in pairs]


FINDINGS = [
    {"id": "F-0701", "title": "BM25 Build and Drop write without the write lock or a transaction",
     "intended": "ADR-0007 (docs/adr/0007-bm25-df-and-doc-record-schema-2.md:5): schema 2 'does every write under an index-level lock in a transaction'; spec 044 FR-016/FR-018 (specs/044-bm25-index/spec.md:162-164): df, N, totalLen consistent 'at every committed point'; FR-019 (:165) two writers never interleave; decisions.md HD-0701 working answer: serialize index modifications and publish a complete generation or unavailable, including crash.",
     "observed": "Live (b-07-f0701-race): an Insert from a second process landed during a 3000-node Build; final N=3000/totalLen=12000 against 3001 doc records summing 12003 (TXT-I2 broken, the inserted doc searchable but uncounted); a concurrent reader saw N=1, schema 2 mid-build. Journal: Build 30008 records, none in a transaction; Insert one transaction. Model: m07-bm25-as-built-I2/-I5 (insert during build), m07-bm25-as-built-settle (Drop during Build leaves a header over no postings), m07-bm25-as-built-quiesced-crash (a stopped build then an Insert breaks I2 even with operators keeping writers apart); reviewed design m07-bm25-reviewed passes; controls caught.",
     "disposition": "reproduced-live", "outcome": "product-defect",
     "evidence": ev(("live", "b-07-f0701-race"), ("live", "b-07-fp-writers"), ("mc", "m07-bm25-as-built-I2"), ("mc", "m07-bm25-as-built-I5"),
                    ("mc", "m07-bm25-as-built-settle"), ("mc", "m07-bm25-as-built-quiesced-crash"), ("mc", "m07-bm25-reviewed"),
                    ("inspected", f"{B}:97-175"), ("inspected", f"{B}:587-591")),
     "gates": ["3.3-L2", "3.5-lock-plans", "3.7-statement-log-vs-lock-plan", "3.3a-writesets"], "severity": "S2", "confidence": "high",
     "remedy": "Per HD-0701: Build takes the write lock for its run, writes a shadow generation and publishes it in one step (or sets a building flag that writers refuse); Drop takes the lock; a crash leaves the old generation or an explicit unavailable state.",
     "notes": "Upgrade's schema-1 path (Build or Drop during Upgrade) is covered by the model only: the pin's API cannot create a schema-1 index for a live run."},
    {"id": "F-0702", "title": "Erasure leaves BM25 indexes holding an erased graph's terms and node ids",
     "intended": "CONTEXT.md:198-208 (erasure removes content from every store that holds it); ADR-0004; Graph.KG.GraphStores comment 'no answer outlives erased content' (iris_src/src/Graph/KG/GraphStores.cls:112-115); TXT-I8.",
     "observed": "Live (b-07-f0702-f0703): after erase_graph('b07g2') (0 node rows left; journal footprint ^KG, ^NKG, docs, nodes, rdf_labels, rdf_props, no ^BM25Idx), bm25_search on the index built for b07g2 still answers both erased node ids with their scores and the term stays in df; Info unchanged.",
     "disposition": "reproduced-live", "outcome": "product-defect",
     "evidence": ev(("live", "b-07-f0702-f0703"), ("inspected", "iris_src/src/Graph/KG/Eraser.cls:138-147"), ("inspected", "iris_src/src/Graph/KG/GraphStores.cls:26-133")),
     "gates": ["3.3a-writesets", "3.6-composition"], "severity": "S1", "confidence": "high",
     "remedy": "List ^BM25Idx in GraphStores.Inventory scoped by its recorded graph and drop or prune every index built for the erased graph inside the erase (decisions.md HD-0601 style ownership for graph-owned derived stores).",
     "notes": "Borders the orchestrator's erasure module (12): the eraser is not in module 07's scope; the BM25 store is."},
    {"id": "F-0703", "title": "A BM25 index goes stale silently when node text changes",
     "intended": "CONTEXT.md:109-114 (a rebuilt store is current or says it is stale; SYS-I8); TXT-I6.",
     "observed": "Live (b-07-f0702-f0703): after delete_node('b07_s1') the index built for its graph still answers b07_s1 for its old text; bm25_info is byte-identical before and after (no staleness signal). docs/USER_GUIDE.md:893-894 leaves maintenance to the caller (bm25_insert/bm25_delete).",
     "disposition": "reproduced-live", "outcome": "intent-undecided",
     "evidence": ev(("live", "b-07-f0702-f0703"), ("inspected", "docs/USER_GUIDE.md:893-894")),
     "gates": ["3.3a-writesets"], "severity": "S2", "confidence": "high",
     "remedy": "Either a staleness signal (graph-version token recorded at build and compared in Info/Search) or a recorded SYS-I8 exemption for caller-maintained indexes.",
     "notes": "The behaviour is reproduced; whether it is a defect depends on whether a BM25 index is a 'rebuilt store' under SYS-I8 or a caller-maintained index (USER_GUIDE). No decision in decisions.md settles it: working assumption = defect against SYS-I8 unless the exemption is recorded."},
    {"id": "F-0704", "title": "A refused index-handle build has already destroyed the old BM25 index",
     "intended": "SYS-I3 / TXT-X2: a refused command leaves every store as it was (ontology/07 TXT-X2).",
     "observed": "Live (b-07-f0704): engine.index('b07h').build(properties=['no_such_property']) raised IndexNotBuiltError after Build had replaced the 2-document index with an empty header (N=0, no doc records); a search then answers []. Model: m07-bm25-as-built-X2(-existing); reviewed (refuse before writing) passes; control m07-bm25-control-late-refusal caught.",
     "disposition": "reproduced-live", "outcome": "product-defect",
     "evidence": ev(("live", "b-07-f0704"), ("mc", "m07-bm25-as-built-X2-existing"), ("mc", "m07-bm25-reviewed"), ("inspected", f"{V}:299-310"), ("inspected", f"{B}:99-111")),
     "gates": ["3.5-handlers", "3.3-L2"], "severity": "S2", "confidence": "high",
     "remedy": "Check the property list and the row count before killing, or build under a temporary name and swap.", "notes": ""},
    {"id": "F-0705", "title": "An index with no recorded graph is read as the default graph's own index",
     "intended": "TXT-B8.3 (an index whose graph is not known is never taken as the default graph's own index); decisions.md HD-0703 (never consult another graph's index); CONTEXT.md:27-43 (graph isolation).",
     "observed": "Live (b-07-f0705-f0707): an index created by bm25_insert has no cfg graph subscript; Info answers graph ''; a fresh engine's _index_graph answers ''; default-graph kg_RRF_FUSE answered node b07_n3, which exists only in graph b07g3; Cypher ivg.bm25.search without USE GRAPH labels its row graph_id ''. Model m07-leg-as-built-fusion-unknown / -label; reviewed passes.",
     "disposition": "reproduced-live", "outcome": "product-defect",
     "evidence": ev(("live", "b-07-f0705-f0707"), ("live", "b-07-fp-writers"), ("mc", "m07-leg-as-built-fusion-unknown"), ("mc", "m07-leg-as-built-label"), ("mc", "m07-leg-reviewed"),
                    ("inspected", f"{B}:608-612"), ("inspected", f"{V}:164-226"), ("inspected", "iris_vector_graph/cypher/translator.py:3125-3142")),
     "gates": ["3.4-declared-reads", "3.5-decoders"], "severity": "S1", "confidence": "high",
     "remedy": "Info answers graph null when the subscript is absent; Insert records the graph (or refuses to create an index); _index_graph treats null as unknown.", "notes": ""},
    {"id": "F-0706", "title": "The stopword node __stop__ is listed and writable as a BM25 index",
     "intended": "decisions.md HD-0704 working answer: reserve the stopword name and reject it at public index-management entry points; spec 044 Edge Cases (specs/044-bm25-index/spec.md:274) names sanitize_identifier.",
     "observed": "Live (b-07-f0706): bm25_build('__stop__', ...) accepted (BM25BuildInput accepts it, probe b-07-probe-fusion); Info('__stop__') answers an index; bm25_drop('__stop__') deletes the 77-word stopword list (rebuilt by the next tokenize, b-07-fp-writers). The embedded-mode registry walk (vector.py:84-104) was not exercised: it needs iris.gref inside IRIS embedded Python; over the Native API the registry uses BM25Index.List, which skips the name.",
     "disposition": "reproduced-live", "outcome": "product-defect",
     "evidence": ev(("live", "b-07-f0706"), ("live", "b-07-fp-writers"), ("probe", "b-07-probe-fusion"), ("inspected", f"{V}:84-104"), ("inspected", "iris_vector_graph/_validate.py:163-179")),
     "gates": ["3.5-decoders", "3.4-ownership"], "severity": "S2", "confidence": "high",
     "remedy": "Refuse __stop__ in BM25BuildInput and in Build/Insert/Delete/Drop; skip it in the registry walk; or move the stopwords to their own global.",
     "notes": "See F-C0701 for a further consequence observed live."},
    {"id": "F-0707", "title": "Under USE GRAPH, BM25 calls do not check that the index was built for that graph",
     "intended": "TXT-I7 (with a graph in scope, BM25 calls answer only from an index built for that graph); CONTEXT.md:27-43; HD-0703.",
     "observed": "Live (b-07-f0705-f0707): USE GRAPH 'b07g1' CALL ivg.bm25.search('b07g2idx','pineapple',5) answered b07g2's node b07_g2a (the generated SQL has no graph check on the index; labels/props joined for b07g1 come back empty). ivg.retrieve could not be run live (no embedder configured: blocked-access for that arm). Model m07-leg-as-built-scope; reviewed passes; control m07-leg-control-no-scope-check caught.",
     "disposition": "reproduced-live", "outcome": "product-defect",
     "evidence": ev(("live", "b-07-f0705-f0707"), ("mc", "m07-leg-as-built-scope"), ("mc", "m07-leg-reviewed"), ("mc", "m07-leg-control-no-scope-check"),
                    ("inspected", "iris_vector_graph/cypher/translator.py:3133-3134"), ("inspected", "iris_vector_graph/cypher/translator.py:3283-3292")),
     "gates": ["3.4-declared-reads", "3.5-handlers"], "severity": "S1", "confidence": "high",
     "remedy": "Compare the index's recorded graph with the graph context and refuse a mismatch or an unknown graph, in ivg.bm25.search and ivg.retrieve.",
     "notes": "ivg.retrieve's arm: inspected and modelled, not live (embedder dependency)."},
    {"id": "F-0708", "title": "Spec 044 states behaviour the code no longer has",
     "intended": "specs/044-bm25-index/spec.md (Status Draft): FR-002 (:148) stored avgdl/idf; FR-010 (:156) Info shape; US2 sc.4 (:78) empty query returns []; US4 sc.2 (:109) warning on a dropped index; Edge Cases (:274) sanitize_identifier; FR-012 (:158) kg_TXT falls back to BM25 'default'.",
     "observed": "Run (b-07-unit): tests/unit/test_bm25_index.py::TestBM25IndexUnit::test_bm25_search_empty_query_raises_validation_error passes (bm25_search raises on an empty query). Source: schema 2 stores no idf/avgdl (BM25Index.cls:6-22); kg_TXT has no BM25 fallback (vector.py:917-1054); names are not sanitized (F-0706 live).",
     "disposition": "reproduced-test", "outcome": "product-defect",
     "evidence": ev(("run", "b-07-unit"), ("inspected", "specs/044-bm25-index/spec.md:78-158"), ("inspected", f"{B}:6-22"), ("inspected", f"{V}:917-1054")),
     "gates": ["3.1-statements", "3.8-account"], "severity": "S3", "confidence": "high",
     "remedy": "Amend spec 044 to the 4.2/4.6.5 behaviour or implement what it keeps (HD-0703 keeps FR-012 for the matching graph); rename TestBM25IndexE2E::test_kgtxt_returns_bm25_scores_not_like_scores.",
     "notes": "A documentation conflict (S3): the product disagrees with its own (draft) spec."},
    {"id": "F-0709", "title": "Fused searches can hide a failed leg",
     "intended": "TXT-B13.7 (the fused search raises and names the leg), TXT-B17.3, TXT-B18.2; spec 044 US7 scenario 9 (text leg contributes); fusion.py:165-168 rationale.",
     "observed": "Live (b-07-f0709): engine kg_RRF_FUSE for a graph with docs but no BM25 index answered [] with no error while kg_TXT answered two matches; (b-07-f0705-f0707) a vector leg the route refused (0-dim vector) also dropped the text leg, answering []. Probe (b-07-probe-fusion, product code with stub legs): multi_modal_search drops a raising vector leg silently; adaptive_search answers [] when every path fails. Documented in docs/KNOWN_ISSUES.md:172-181 for the engine path (planned 4.7.1).",
     "disposition": "reproduced-live", "outcome": "product-defect",
     "evidence": ev(("live", "b-07-f0709"), ("live", "b-07-f0705-f0707"), ("probe", "b-07-probe-fusion"), ("inspected", f"{V}:1421-1436"), ("inspected", "iris_vector_graph/fusion.py:144-152"), ("inspected", "iris_vector_graph/fusion.py:301-310")),
     "gates": ["3.5-status-maps"], "severity": "S2", "confidence": "high",
     "remedy": "Raise naming the leg on every fusion path (the 4.7.1 plan), or return a field naming the legs that ran.",
     "notes": "Side observation for module 06: multi_modal_search with query_vector='not-a-vector' got [] from kg_KNN_VEC without an exception (live b-07-f0709 log)."},
    {"id": "F-0710", "title": "Weighted fusion's default weights go to legs by position, not by kind",
     "intended": "iris_vector_graph/fusion.py:216 comment: vector=0.5, text=0.3, graph=0.2.",
     "observed": "Probe (b-07-probe-fusion): a text-only weighted call with graph expansion scores text 0.625 and graph 0.375 (weights 0.5/0.3 normalized) where the comment's 0.3/0.2 give 0.6/0.4.",
     "disposition": "reproduced-test", "outcome": "product-defect",
     "evidence": ev(("probe", "b-07-probe-fusion"), ("inspected", "iris_vector_graph/fusion.py:214-219")),
     "gates": ["3.5-handlers"], "severity": "S4", "confidence": "high",
     "remedy": "Map default weights from search_modes.", "notes": "Reproduced by an audit probe that executes the product's fusion code in-process with stub legs (registry kind probe; not an upstream test, no IRIS). HybridSearchFusion's support status is HD-0705 (assumption: compatibility surface)."},
    {"id": "F-0711", "title": "TextSearchEngine answers across graphs and cannot reach iFind",
     "intended": "TXT-B19.1 (its searches answer from one graph only); CONTEXT.md:27-43; HD-0705 assumption (exported helpers are compatibility surfaces whose scope must be qualified).",
     "observed": "Live (b-07-f0711): extract_entity_names and search_with_context returned nodes of graphs b07g1 and b07g2 together; search_documents raised SQLCODE -30 on SQLUSER.DOCS (unqualified table) in both the %FIND path and its LIKE fallback and answered []. tests/unit/test_ifind_and_fusion_sql.py (run b-07-unit) documents %FIND(col, ?) as not IRIS syntax.",
     "disposition": "reproduced-live", "outcome": "product-defect",
     "evidence": ev(("live", "b-07-f0711"), ("run", "b-07-unit"), ("inspected", "iris_vector_graph/text_search.py:31-256"), ("inspected", "iris_vector_graph/__init__.py:93-125")),
     "gates": ["3.4-declared-reads"], "severity": "S1", "confidence": "high",
     "remedy": "Per HD-0705: add a graph argument and predicate to every query, use %ID %FIND search_index(...) on the schema-qualified docs table, or deprecate the export.", "notes": ""},
]

NEW = [
    {"id": "F-C0701", "title": "An index built under the stopword name makes index-structure words stopwords in every BM25 index",
     "intended": "TXT-D1 (a stopword is one of 77 common English words); HD-0704 (reserve the stopword name).",
     "observed": "Live (b-07-f0706): after bm25_build('__stop__', ['name'], graph='b07g1') the words 'doc', 'tf', 'len' (and 'cfg', 'df') are stopwords for every index in the namespace: a rebuild of index b07w drops them (searches for each answer [] where they answered b07_w1 before) because Tokenize's stopword test $Data(^BM25Idx(\"__stop__\", tok)) (BM25Index.cls:83) is true for the index's own subscripts. The effect lasts until the __stop__ index is dropped (which also deletes the stopword list until the next tokenize).",
     "disposition": "reproduced-live", "outcome": "product-defect",
     "evidence": ev(("live", "b-07-f0706"), ("inspected", f"{B}:41-50"), ("inspected", f"{B}:79-86")),
     "gates": ["3.4-ownership", "3.5-decoders"], "severity": "S2", "confidence": "high",
     "remedy": "Refuse the name (HD-0704) or move the stopword list to its own global.",
     "notes": "Same root cause as F-0706 (the stopword list shares the index key space); distinct impact: silent wrong answers in other indexes."},
    {"id": "F-C0702", "title": "A BM25 Insert or Delete that fails inside a caller's transaction rolls the caller's transaction back",
     "intended": "iris_vector_graph/_write_txn.py:1-30 (since 4.6.4 an IVG write nested in a caller's transaction undoes only its own level; TROLLBACK 1 nests, SQL ROLLBACK ends every level); spec 044 FR-019 (a failure leaves the index as it was); SYS-I3.",
     "observed": "Live (b-07-fc0702-nested-rollback): SQL START TRANSACTION and a caller INSERT into Graph_KG.docs ($TLEVEL 1); bm25_insert with a 604-character document id fails with <SUBSCRIPT> inside Insert's Try; $TLEVEL is then 0 and the caller's uncommitted row is gone, with no error naming the rollback. Control: a valid bm25_insert in the same setting returns to $TLEVEL 1 and keeps the caller's row. Cause: `If $TLevel > 0 TRollback` with no level (BM25Index.cls:487, :508).",
     "disposition": "reproduced-live", "outcome": "product-defect",
     "evidence": ev(("live", "b-07-fc0702-nested-rollback"), ("inspected", f"{B}:486-490"), ("inspected", f"{B}:507-511"), ("inspected", "iris_vector_graph/_write_txn.py:1-30")),
     "gates": ["3.5-handlers", "3.6-composition", "3.2-env-contract"], "severity": "S1", "confidence": "high",
     "remedy": "Roll back only the method's own level (TROLLBACK 1, and only when it started one), as _write_txn does; a test that fails an Insert inside a caller transaction.",
     "notes": "Any error inside the Try reaches it: RequireWritable after an Upgrade started, <SUBSCRIPT> on long ids or tokens, <UNDEFINED> after a concurrent Drop. The same bare TRollback appears once in iris_src/src/Graph/KG/TraversalBuild.cls (module 04, not audited here)."},
    {"id": "F-C0703", "title": "Text-search top-k answers and fused ranks depend on scan order",
     "intended": "Playbook principle 5 / gate 3.4-storage-order (never depend on storage or insertion order); decisions.md HD-0603/HD-0702 (a ranking contract with defined tie behaviour).",
     "observed": "Source (storage-order check $RUN_DIR/checks/storage-order.json, dispositions in modules/07.json storage_order): engine kg_TXT's LIKE fallback takes `SELECT TOP k d.id, 1.0 AS score ... WHERE <LIKE terms> AND <graph>` with no ORDER BY (iris_vector_graph/_engine/vector.py:1041-1046), so which k matching documents answer, and their ranks, are the scan's; this is the path that ran on AUDITB (every kg_TXT score 1.0 in b-07-f0709, iFind index unusable). The iFind path (vector.py:979-985, :998-1003), the generated kg_TXT procedure (iris_vector_graph/schema.py:2484-2520) and kg_RRF_FUSE's ROW_NUMBER() OVER (ORDER BY score DESC) legs (schema.py:2557-2572) order by a score that ties (an occurrence count), so the TOP cut and the ranks among tied documents are the scan's; the ranks feed fusion (RRF adds 1/(c + rank)). TextSearchEngine's three helper queries order by (score, length) or (score, confidence) only (text_search.py:111-127, :165-178, :212-233). The engine's kg_RRF_FUSE sorts a Python set by score with no tie key (vector.py:1438-1452), so its tie order follows string-hash order, which differs per process.",
     "disposition": "confirmed-source", "outcome": "product-defect",
     "evidence": ev(("inspected", f"{V}:1041-1046"), ("inspected", f"{V}:979-1003"), ("inspected", "iris_vector_graph/schema.py:2484-2578"), ("inspected", "iris_vector_graph/text_search.py:111-233"), ("inspected", f"{V}:1438-1452"), ("live", "b-07-f0709")),
     "gates": ["3.4-storage-order", "3.6-row-permutation"], "severity": "S3", "confidence": "high",
     "remedy": "Order every top-k text query by a total key (score DESC, then the node id), give ROW_NUMBER() the same tie key, and break ties in the engine fusion by node id; a test that inserts tied documents in two orders and compares answers.",
     "notes": "Not demonstrated live (two insertion orders) under the follow-up's no-IRIS instruction; the dependency is visible in the SQL text. The LIKE fallback is documented as unranked (scores 1.0, vector.py:925-930), but which documents survive the cut is not documented."},
]


def write_findings():
    for f in FINDINGS + NEW:
        f["module"] = "07"
        f["original_ref"] = ("experiment/playbook-uplift/findings/07.md#" + f["id"]) if not f["id"].startswith("F-C") else None
    by_d, by_o = {}, {}
    for f in FINDINGS:
        by_d[f["disposition"]] = by_d.get(f["disposition"], 0) + 1
        by_o[f["outcome"]] = by_o.get(f["outcome"], 0) + 1
    out = {"module": "07", "lane": "breadth-b", "pin": "3eaa79cf",
           "summary": {"original_findings": len(FINDINGS), "by_disposition": by_d, "by_outcome": by_o, "new_findings": len(NEW),
                       "new_by_outcome": {"product-defect": sum(1 for f in NEW if f["outcome"] == "product-defect")}},
           "findings": FINDINGS, "new_findings": NEW}
    (COMP / "findings/audit/07.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


ENV = []
SO_FILE = Path(os.environ["RUN_DIR"]) / "checks" / "storage-order.json"
VEC_SPANS = [(56, 84, "VectorMixin._detect_stored_vector_dtype (module 06)"), (333, 503, "edge_vector_search (module 06)"),
             (504, 619, "kg_KNN_VEC (module 06)"), (620, 725, "measure_route_recall (module 06)"),
             (748, 916, "search_nodes_by_vector (module 06)"), (917, 1054, "kg_TXT (module 07)"),
             (1122, 1168, "validate_vector_table (module 06)"), (1169, 1287, "vector_search (module 06)"),
             (1382, 1452, "kg_RRF_FUSE (module 07)"), (1749, 1879, "bm25_* (module 07)")]
OWN_DISP = {
    ("iris_vector_graph/text_search.py", 48): ("F-0711", "search_documents: has ORDER BY relevance_score DESC (text_search.py:54), which ties; the statement cannot run at the pin (%FIND(text, ?) is not IRIS syntax and `docs` is unqualified: SQLCODE -30 live, b-07-f0711), so the tie dependency is moot until F-0711 is fixed; then F-C0703 applies."),
    ("iris_vector_graph/text_search.py", 77): ("false-positive", "_fallback_text_search: ORDER BY id (text_search.py:82); rows tied on id differ only in graph and project the same (id, 1.0), so the answer does not depend on scan order (the statement itself fails at the pin: F-0711)."),
    ("iris_vector_graph/text_search.py", 111): ("F-C0703", "search_entity_qualifiers: ORDER BY text_match_score DESC, jt.confidence DESC (text_search.py:123); edges tied on both keys are cut at TOP k in scan order."),
    ("iris_vector_graph/text_search.py", 165): ("F-C0703", "extract_entity_names: ORDER BY match_score DESC, LENGTH(p.val) ASC (text_search.py:177); tied names are cut in scan order."),
    ("iris_vector_graph/text_search.py", 212): ("F-C0703", "search_with_context: ORDER BY relevance_score DESC, LENGTH(p.val) ASC (text_search.py:233); tied rows (and the label LEFT JOIN's duplicates) are cut in scan order."),
    ("iris_vector_graph/_engine/vector.py", 979): ("F-C0703", "kg_TXT iFind path with min_confidence: ORDER BY score DESC only (vector.py:984); score is an occurrence count that ties."),
    ("iris_vector_graph/_engine/vector.py", 998): ("F-C0703", "kg_TXT iFind path: ORDER BY score DESC only (vector.py:1002); ties cut in scan order."),
    ("iris_vector_graph/_engine/vector.py", 1042): ("F-C0703", "kg_TXT LIKE fallback: TOP k with no ORDER BY (vector.py:1041-1046); every score 1.0, so the answer set and its ranks are the scan's. The path that ran on AUDITB (b-07-f0709)."),
    ("iris_vector_graph/schema.py", 2484): ("F-C0703", "generated kg_TXT procedure: ORDER BY score DESC only (schema.py:2484-2520); ties cut in scan order, and kg_RRF_FUSE ranks them."),
}


def storage_order():
    sites = json.loads(SO_FILE.read_text())
    own, other = [], []
    for x in sites:
        f, ln = x["file"], x["line"]
        if f in ("iris_vector_graph/text_search.py", "iris_vector_graph/operators.py", "iris_vector_graph/fusion.py"):
            d, why = OWN_DISP[(f, ln)]
            own.append({"file": f, "line": ln, "kind": x["kind"], "sql": x["sql"], "disposition": d, "reason": why})
        elif f == "iris_vector_graph/_engine/vector.py":
            span = next((sp for sp in VEC_SPANS if sp[0] <= ln <= sp[1]), None)
            if span and "module 07" in span[2]:
                d, why = OWN_DISP[(f, ln)]
                own.append({"file": f, "line": ln, "kind": x["kind"], "sql": x["sql"], "disposition": d, "reason": why})
            else:
                other.append({"file": f, "line": ln, "kind": x["kind"], "sql": x["sql"], "disposition": "not-owned",
                              "owner": (f"{V}:{span[0]}-{span[1]} {span[2]}" if span else "vector.py outside module 07 spans (module 06)")})
        elif f == "iris_vector_graph/schema.py" and 2480 <= ln <= 2580:
            d, why = OWN_DISP[(f, ln)]
            own.append({"file": f, "line": ln, "kind": x["kind"], "sql": x["sql"], "disposition": d, "reason": why})
    unflagged = [
        {"file": "iris_vector_graph/schema.py", "line": 2557, "sql": "ROW_NUMBER() OVER (ORDER BY score DESC) ... kg_KNN_VEC / kg_TXT legs of kg_RRF_FUSE; final ORDER BY rrf DESC",
         "disposition": "F-C0703", "reason": "not flagged (it has ORDER BY), but the rank of tied leg scores and the TOP :k cut on tied rrf follow scan order (schema.py:2557-2578)."},
        {"file": "iris_vector_graph/_engine/vector.py", "line": 1438, "sql": "(Python) fused = [...] over set(vec_rank) | set(txt_rank); fused.sort(key=lambda x: -x[1]); fused[:k]",
         "disposition": "F-C0703", "reason": "no SQL prefix, but ties in rrf keep Python set iteration order (string hash, per process) before the cut (vector.py:1438-1452)."},
        {"file": "iris_src/src/Graph/KG/BM25Index.cls", "line": 300, "sql": "(ObjectScript) ^||bm25sorted walked backwards by score*10^12 then docId",
         "disposition": "unique-key", "reason": "SearchCore sorts by (score subscript, docId subscript); docId is the unique document key within the index, so ties are broken by collation, not storage order (BM25Index.cls:300-374, P-0705)."},
    ]
    counts = {}
    for e in own + unflagged:
        counts[e["disposition"]] = counts.get(e["disposition"], 0) + 1
    return {"input": "$RUN_DIR/checks/storage-order.json (prefix without ORDER BY scanner)",
            "sites_in_module_07": own, "reviewed_sites_not_flagged": unflagged, "adjacent_sites_not_owned": other,
            "counts": {"flagged_in_module_07": len(own), "by_disposition": counts, "not_owned": len(other)}}


def gate(g, status, reason, evidence=(), remaining=""):
    return {"gate": g, "status": status, "reason": reason, "evidence": list(evidence), "remaining": remaining}


def E(kind, ref):
    return {"kind": kind, "ref": ref}


def gates_by_id(gates, so):
    g = {x["gate"]: x for x in gates}
    def fromg(name, status=None, extra_ev=()):
        x = g[name]
        ev_ = [E(*e.split(":", 1)) if isinstance(e, str) and ":" in e else E("ref", e) for e in x["evidence"]] + list(extra_ev)
        return {"status": status or x["status"], "reason": x["reason"], "evidence": ev_, "remaining": x["remaining"]}
    mcids = sorted(MC)
    out = {
        # product-scope gates with module evidence
        "3.1-parent": {"status": "closed", "reason": "ontology_index.py --check --only 07: 0 violations (parent ids, grade, lexical-scope terms).", "evidence": [E("run", "python3 -I experiment/playbook-uplift/tools/ontology_index.py --check --only 07")], "remaining": ""},
        "3.1-grade": {"status": "closed", "reason": "0 Flesch-Kincaid violations in TXT statements (same run).", "evidence": [E("run", "python3 -I experiment/playbook-uplift/tools/ontology_index.py --check --only 07")], "remaining": ""},
        "3.1-terms": fromg("3.1-statements"),
        "3.3-progress-controls": {"status": "open", "reason": "AG EF 'the index can always settle' holds in m07-bm25-reviewed and fails as built (m07-bm25-as-built-settle); no control that fails only the progress property.", "evidence": [E("mc", "m07-bm25-reviewed"), E("mc", "m07-bm25-as-built-settle")], "remaining": "A progress-only mutant (e.g. a lock never released) that keeps safety."},
        "3.6-composition": fromg("3.6-composition"),
        "3.7-explorers": fromg("3.7-explorers"),
        "3.7-integration-worlds": fromg("3.7-integration-worlds"),
        "3.7-differential": fromg("3.7-differential"),
        "3.7-e2e": fromg("3.7-e2e"),
        "3.7-failure-controls": fromg("3.7-failure-scenarios"),
        "3.7-suites": {"status": "open", "reason": "69 module-07 unit tests (no IRIS) rerun on the unchanged pin and passed; the IRIS-backed integration/e2e BM25 and fusion suites were not run here (their fixture compiles classes).", "evidence": [E("run", "b-07-unit")], "remaining": "Validation lane runs the IRIS-backed suites in USER."},
        # module gates
        "3.1-cells": fromg("3.1-cells"),
        "3.1-coverage": fromg("3.1-entry-points"),
        "3.1-intent": {"status": "open", "reason": "HD-0701..HD-0705 carry working assumptions (decisions.md:93-111), not maintainer decisions; F-0703 is intent-undecided (SYS-I8 status of a caller-maintained BM25 index).", "evidence": [E("inspected", "experiment/playbook-completion/decisions.md:93-111")], "remaining": "Owned by the intent lanes."},
        "3.2-coverage": {"status": "open", "reason": f"{len(ENV)} IRIS features listed in env_features; none yet inside the orchestrator's IRIS contract. F-C0702 shows TROLLBACK-level semantics (bare TROLLBACK ends every level) matter to this module.", "evidence": [E("live", "b-07-fc0702-nested-rollback")], "remaining": "IRIS environment contract (AUDITENV) to cover or exclude each env feature."},
        "3.3-L1": fromg("3.3-L1"),
        "3.3-L2": fromg("3.3-L2"),
        "3.3-refinement": fromg("3.3-refinement"),
        "3.3-controls": fromg("3.3-controls"),
        "3.3-model-check": {"status": "closed", "reason": f"{len(mcids)} explorer checks, all met and exhaustive within bounds: as-built reproduces F-0701, F-0704, F-0705, F-0707; reviewed (HD-0701, HD-0703) passes incl. AG EF; 3 negative controls caught; 4 sharpness witnesses.", "evidence": [E("mc", m) for m in mcids], "remaining": "Bounds: 3 documents, 2 tokens, 1 build, 2 writer ops, 1 drop, 1 upgrade; 3 indexes x 2 graphs."},
        "3.4-storage-order": fromg("3.4-storage-order"),
        "3.4-declared-reads": fromg("3.4-declared-reads"),
        "3.5-handlers": fromg("3.5-handlers"),
        "3.5-decoders": fromg("3.5-decoders", extra_ev=[E("live", "b-07-f0709")]),
        "3.6-row-permutation": {"status": "failed", "reason": "Top-k text answers and fused ranks change with row order (F-C0703: kg_TXT LIKE fallback has no ORDER BY; score-only orderings tie).", "evidence": [E("finding", "F-C0703")], "remaining": "Total tie keys; a permutation test."},
        "3.6-capacity": {"status": "open", "reason": "Subscript capacity: document ids and tokens are global subscripts; a 604-character id raised <SUBSCRIPT> inside Insert (b-07-fc0702-nested-rollback), which also triggered F-C0702. Not checked: a token longer than a subscript in Build, which writes outside a transaction (would leave a partial index, cf. F-0701); lock-table limits not exercised.", "evidence": [E("live", "b-07-fc0702-nested-rollback"), E("inspected", f"{B}:194")], "remaining": "Live check of an over-long token in Build; document the id/token length limits."},
        "3.7-mutation": fromg("3.7-mutation"),
        "3.8-findings-disposed": {"status": "closed", "reason": "Every original finding F-0701..F-0711 and the 3 new ones has a recorded disposition, outcome and evidence in findings/audit/07.json (observation-only: the product obligations stay failed in their gates).", "evidence": [E("ref", "experiment/playbook-completion/findings/audit/07.json")], "remaining": ""},
        "5c-refusals": {"status": "failed", "reason": "25 refusal statements (kind X): 4 run here and held (TXT-X3, X4, X12, X15 via b-07-unit); 4 broken live (TXT-X2 by F-0704; TXT-B13.7, B17.3, B18.2 by F-0709); 10 upstream-tested but not run here (X5-X9, X13, X17-X20); 7 inspected only (X1, X10, X11, X14, X16, B12.7, B15.3).", "evidence": [E("run", "b-07-unit"), E("live", "b-07-f0704"), E("live", "b-07-f0709"), E("probe", "b-07-probe-fusion")], "remaining": "Run the 10 upstream-tested refusals in the validation lane; evidence the 7 inspected-only ones."},
        # module-writer gates
        "3.3a-writesets": fromg("3.3a-writesets"),
        "3.4-statements": fromg("3.4-statements"),
        "3.4-ownership": fromg("3.4-ownership"),
        "3.5-lockplans": fromg("3.5-lock-plans"),
        "3.6-frame": {"status": "open", "reason": "No frame obligation per statement shape for the ^BM25Idx writers (the model frames by construction only).", "evidence": [], "remaining": "Frame lemmas: Build/Insert/Delete/Upgrade/Drop touch only ^BM25Idx(name) and the stopword node."},
        "3.6-keys": {"status": "failed", "reason": "^BM25Idx is keyed by index name alone: the graph is a config value an Insert-created index lacks (F-0705), and the stopword list shares the index key space (F-0706, F-C0701), all live.", "evidence": [E("live", "b-07-f0705-f0707"), E("live", "b-07-f0706")], "remaining": "Graph-recorded or graph-keyed indexes; reserved or separate stopword root."},
        "3.6-fk": {"status": "not-applicable", "reason": "Module 07 writes no SQL row: every journaled write of its writers is in ^BM25Idx (b-07-fp-writers footprint; BM25Index.cls has no INSERT/UPDATE/DELETE), and its SQL is read-only (kg_TXT, kg_RRF_FUSE, TextSearchEngine). No foreign key is involved.", "evidence": [E("live", "b-07-fp-writers"), E("inspected", f"{B}:97-591")], "remaining": ""},
        "3.7-trace-replay": fromg("3.7-trace-replay"),
        "3.7-lock-log": fromg("3.7-statement-log-vs-lock-plan"),
    }
    return out


def write_module(fp, fa):
    mc = MC
    met = sum(1 for v in mc.values() if v["met"])
    by_design = {}
    for v in mc.values():
        d = by_design.setdefault(v["design"], {"met": 0, "not_met": 0})
        d["met" if v["met"] else "not_met"] += 1
    gates = [
        gate("3.1-statements", "open", "The original index gate passes for 07 under the lexical-scope reading (ontology_index.py --check --only 07: 0 violations), but decisions.md HD-0001 adopts the literal rule: check-literal-scope.py reports 49 TXT statement/term pairs using a term not defined by an ancestor or an earlier sibling.",
             ["inspected:experiment/playbook-uplift/tools/ontology_index.py", "inspected:experiment/playbook-completion/check-literal-scope.py"], "Rewrite or reparent the 49 TXT term uses (orchestrator's ontology lane)."),
        gate("3.1-cells", "open", "All 53 cells are defined or open; 4 cells are open on HD-0701 (building x build/insert/drop, upgrading x build/drop: 5 rows) whose working answer (serialize, complete-or-unavailable) the reviewed model now covers. The docs-table text search (kg_TXT engine/SQL/operators) and TextSearchEngine have no entity in Cells.",
             ["inventory:models/breadth-b/inventory/07.json"], "Add cells for kg_TXT (docs table: iFind present/absent x graph) and TextSearchEngine; resolve the HD-0701 cells to the reviewed outcome."),
        gate("3.1-entry-points", "open", "48 entry points derived mechanically; 0 cell commands lack an entry point; 7 entry points no statement covers: the Index handle's fulltext build/search/insert/drop/info (index_protocol.py:83-105; Index.build reaches TXT-X2 only via vector.py:299-310), create_index(replace=True)'s drop (vector.py:243-259) and HybridSearchFusion.__init__ (pure). 12 entry points are in no cell (kg_TXT x3, TextSearchEngine x5, RRFFusion x2, kg_RERANK, HybridSearchFusion.__init__).",
             ["inventory:models/breadth-b/inventory/07.json"], "Add statements for the Index handle fulltext path and create_index(replace=True)."),
        gate("3.2-env-contract", "open", "Module 07 relies on the IRIS features in env_features (timed LOCK, TSTART nesting with bare TROLLBACK, journaling of Kill/Set outside transactions, process-private globals, %iFind.Utils.Analyze, iFind index, embedded Python gref). None is covered by a differential environment contract yet; P-0702/P-0703 were premises in the submission. F-C0702 shows the TROLLBACK-level semantics matter.",
             ["live:b-07-fc0702-nested-rollback"], "Orchestrator's IRIS environment contract (AUDITENV) must cover the listed features."),
        gate("3.3-L1", "open", "No Verus L1 model for module 07. Executable explorer models exist (bm25, leg).", [], "Write the L1 for the BM25 index (I1-I3, I5, X2) if module 07 enters proof depth."),
        gate("3.3-L2", "closed", "The bm25 machine abstracts the real ^BM25Idx layout and every writer step at path:lines (m07.rs header); as-built reproduces F-0701/F-0704 and the reviewed design passes exhaustively within bounds (bounded mc, not a proof).",
             ["mc:m07-bm25-reviewed", "mc:m07-bm25-as-built-I2", "mc:m07-bm25-as-built-X2"], "Bounds: 3 documents, 2 tokens, 1 build, 2 writer ops, 1 drop, 1 upgrade."),
        gate("3.3-refinement", "open", "No refinement audit (explorer::refinement) between an L1 and the bm25 machine.", [], "Bind the bm25 machine to an L1 with explorer::refinement::audit."),
        gate("3.3-controls", "open", "No proof-level controls (no Verus L1/L2 for module 07). Explorer-level negative controls caught: m07-bm25-control-nolock (Build without the lock -> TXT-I5), m07-bm25-control-late-refusal (refusal after replacement -> TXT-X2), m07-leg-control-no-scope-check (-> TXT-I7).",
             ["mc:m07-bm25-control-nolock", "mc:m07-bm25-control-late-refusal", "mc:m07-leg-control-no-scope-check"]),
        gate("3.3-progress", "closed", "AG EF 'the index can always settle' holds in m07-bm25-reviewed (exhaustive within bounds) and fails as built (m07-bm25-as-built-settle: Drop during Build). Sharpness witnesses: complete index, insert serialized after build, insert after a crashed build, scoped fusion answer all reachable.",
             ["mc:m07-bm25-reviewed", "mc:m07-bm25-as-built-settle", "mc:m07-bm25-positive-complete", "mc:m07-bm25-positive-insert-after-build", "mc:m07-bm25-positive-crash-then-insert", "mc:m07-leg-positive-scoped"]),
        gate("3.3a-mechanisms", "open", "BM25 writers use a per-index lock + transaction mechanism (Insert/Delete/Upgrade) but Build and Drop bypass it (F-0701); no shared 'derived store generation' mechanism records staleness (F-0703) or erasure (F-0702).", ["live:b-07-f0701-race"], "Adopt HD-0701's serialized generation mechanism; decide the SYS-I8 status of BM25 indexes."),
        gate("3.3a-writesets", "failed", "Invariant/plan pairs computed below: TXT-I1/I2 x Build, Drop (F-0701, product defect, live), TXT-I8 x eraser.erase_graph (F-0702), TXT-B8.3/I7 x Insert-created index (F-0705). Remaining pairs discharged by guard (lock+transaction) or mc.",
             ["live:b-07-f0701-race", "live:b-07-f0702-f0703", "mc:m07-bm25-reviewed"], "Fixes per findings; rerun the pairs."),
        gate("3.4-statements", "open", "No storage statement (ObjectScript global operations on ^BM25Idx, the kg_TXT/kg_RRF_FUSE SQL) is proved against an IRIS contract; the bm25 machine abstracts the global operations at path:lines but is bounded mc, not a statement proof.", ["inspected:iris_src/src/Graph/KG/BM25Index.cls:97-591"], "Statement lemmas against the IRIS environment contract."),
        gate("3.4-ownership", "failed", "^BM25Idx('__stop__') (stopword list) shares the index key space and any index-management call can write it (F-0706, F-C0701 live); ^BM25Idx is written only by Graph.KG.BM25Index (grep), but erasure does not own its graph-scoped content (F-0702).", ["live:b-07-f0706", "live:b-07-f0702-f0703"], "Reserve or relocate the stopword node; give ^BM25Idx an owner in GraphStores."),
        gate("3.4-storage-order", "failed", "Storage-order scanner ($RUN_DIR/checks/storage-order.json): 9 flagged sites in module-07 code (text_search.py x6 records, vector.py kg_TXT x3 records... see storage_order) plus 2 unflagged reviewed sites: 1 false-positive, 1 subsumed by F-0711, the rest F-C0703 (top-k text answers and fused ranks follow scan order); BM25 SearchCore breaks ties by docId (unique-key). 15 other vector.py sites are module 06's.",
             ["finding:F-C0703", "inspected:iris_vector_graph/_engine/vector.py:1041-1046", "live:b-07-f0709"], "Total tie keys (node id) on every top-k text query and fusion rank (F-C0703)."),
        gate("3.4-declared-reads", "failed", "Reads not scoped to the declared graph: ivg.bm25.search/ivg.retrieve under USE GRAPH (F-0707), insert-created/legacy indexes read as the default graph's (F-0705), TextSearchEngine (F-0711): all reproduced live.", ["live:b-07-f0705-f0707", "live:b-07-f0711"], "Fixes per findings."),
        gate("3.5-handlers", "failed", "Handler contracts broken live: refused rebuild destroys (F-0704); failing Insert inside a caller transaction rolls it back (F-C0702); positional default weights (F-0710).", ["live:b-07-f0704", "live:b-07-fc0702-nested-rollback", "probe:b-07-probe-fusion"], "Fixes per findings."),
        gate("3.5-lock-plans", "failed", "Lock plan: Insert/Delete/Upgrade take Lock +^BM25Idx(name,'lock'):timeout; Build and Drop take none (journal: no transaction, model TXT-I5 violation); Upgrade sets its flag before the lock (by design).", ["live:b-07-fp-writers", "mc:m07-bm25-as-built-I5"], "Build/Drop under the lock (HD-0701)."),
        gate("3.5-decoders", "open", "Info's JSON maps an absent graph to '' (F-0705); bm25_search's parser patches '.5' numbers (vector.py:1816-1819); kg_TXT LIKE fallback scores 1.0. Not proved.", ["live:b-07-f0705-f0707"], "Info answers null for an absent graph; decoder unit tests."),
        gate("3.5-status-maps", "failed", "Error-to-outcome maps hide failures: kg_RRF_FUSE logs and drops legs, adaptive_search answers [], TextSearchEngine answers [] on SQL errors (F-0709, F-0711).", ["live:b-07-f0709", "probe:b-07-probe-fusion"], "Raise naming the leg."),
        gate("3.6-composition", "failed", "Composition with erasure (F-0702) and with caller transactions (F-C0702) breaks module contracts at the boundary, both live.", ["live:b-07-f0702-f0703", "live:b-07-fc0702-nested-rollback"], "Orchestrator: include ^BM25Idx in the erasure composition; transaction-level contract for nested IVG writes."),
        gate("3.7-explorers", "closed", f"{len(mc)} explorer checks for module 07, {met} met their expectation, all exhaustive within bounds.", [f"mc:{k}" for k in sorted(mc)]),
        gate("3.7-integration-worlds", "open", "Crash of a Build modelled (m07-bm25-as-built-quiesced-crash) but not injected live (no safe way to kill a server process mid-build on the shared container).", ["mc:m07-bm25-as-built-quiesced-crash"], "A crash world needs an orchestrator-approved process termination."),
        gate("3.7-differential", "open", "No differential run of the BM25 tokenizer/analyzer (P-0701) against the documented examples.", [], "Probe %iFind.Utils.Analyze on the USER_GUIDE examples in AUDITENV."),
        gate("3.7-e2e", "open", "Upstream e2e/integration BM25 tests (tests/integration/test_044_bm25_incremental.py, tests/e2e/test_230_retrieval_scope.py) not run: their session fixture LoadStream-compiles classes, which the audit rules forbid in AUDITB. 69 unit tests run and passed.", ["run:b-07-unit"], "Validation lane (USER namespace) runs the IRIS-backed suites."),
        gate("3.7-trace-replay", "open", "Journal traces of the writers exist (b-07-fp-writers, b-07-f0701-race) but are not replayed through the bm25 machine.", ["live:b-07-fp-writers", "live:b-07-f0701-race"], "Replay journal records as bm25 machine steps."),
        gate("3.7-statement-log-vs-lock-plan", "failed", "Journal vs lock plan: Insert/Delete each one transaction under the lock (match); Build 106/106 and 30008/30008 records outside any transaction and with no lock while a concurrent Insert committed (mismatch with ADR-0007).", ["live:b-07-fp-writers", "live:b-07-f0701-race"], "Fix F-0701 and rerun."),
        gate("3.7-mutation", "open", "Model mutants only (controls); no mutation testing of BM25Index.cls or fusion.py.", ["mc:m07-bm25-control-nolock"], "Mutation testing of the unverified layers."),
        gate("3.7-perf-ab", "not-applicable", "No structural change was made by this audit (product read-only), so there is nothing to A/B.", []),
        gate("3.7-failure-scenarios", "closed", "Failure scenarios each with a control: lock timeout refusal and refused rebuild (model), failing Insert in a caller transaction (live, with a valid-insert control), vector leg failure (live + probe).", ["live:b-07-fc0702-nested-rollback", "live:b-07-f0704", "mc:m07-bm25-control-late-refusal"]),
        gate("3.8-account", "open", "Module 07 account written here (footprints, findings audit, gates); no independent reviewer sign-off; 13 product defects open (11 original incl. 1 intent-undecided, 2 new).", ["findings:findings/audit/07.json"], "Reviewer sign-off; maintainer decisions HD-0701..0705."),
    ]
    writesets = [
        {"invariant": "TXT-I1/TXT-I2 (df, N, totalLen match the stored documents)", "reads": ["^BM25Idx(name,cfg N/totalLen)", "^BM25Idx(name,df/tf/doc/len)"],
         "plans": [
             {"plan": "cls:Graph.KG.BM25Index.Build", "writes": ["^BM25Idx(name)"], "discharge": "finding F-0701 (live b-07-f0701-race; mc m07-bm25-as-built-I2); reviewed design mc m07-bm25-reviewed"},
             {"plan": "cls:Graph.KG.BM25Index.Insert", "writes": ["^BM25Idx(name)"], "discharge": f"guard: lock + transaction {B}:456-491 (journal b-07-fp-writers); mc m07-bm25-reviewed"},
             {"plan": "cls:Graph.KG.BM25Index.Delete", "writes": ["^BM25Idx(name)"], "discharge": f"guard: lock + transaction {B}:500-512; mc m07-bm25-reviewed"},
             {"plan": "cls:Graph.KG.BM25Index.Upgrade", "writes": ["^BM25Idx(name)"], "discharge": f"guard: flag + lock {B}:533-579 (no transaction; recompute from postings); mc m07-bm25-reviewed"},
             {"plan": "cls:Graph.KG.BM25Index.Drop", "writes": ["^BM25Idx(name)"], "discharge": "finding F-0701 (mc m07-bm25-as-built-settle: Drop during Build)"}]},
        {"invariant": "TXT-I3 (schema 2 holds no idf)", "reads": ["^BM25Idx(name,cfg schema)", "^BM25Idx(name,idf)"],
         "plans": [{"plan": "cls:Graph.KG.BM25Index.Upgrade", "writes": ["schema", "idf"], "discharge": "mc m07-bm25-reviewed (atomic body); inspected :569-572 (flip then kill idf: a reader can see schema 2 with idf briefly)"},
                   {"plan": "cls:Graph.KG.BM25Index.Build", "writes": ["^BM25Idx(name)"], "discharge": f"inspected {B}:99 (Kill removes idf)"}]},
        {"invariant": "TXT-I5 (two writers never change one index at once)", "reads": ["write lock", "^BM25Idx(name)"],
         "plans": [{"plan": "Build", "writes": ["^BM25Idx(name)"], "discharge": "finding F-0701"}, {"plan": "Drop", "writes": ["^BM25Idx(name)"], "discharge": "finding F-0701"},
                   {"plan": "Insert/Delete/Upgrade", "writes": ["^BM25Idx(name)"], "discharge": f"guard {B}:403-410"}]},
        {"invariant": "TXT-I6 (an index matches its graph's text or says it is stale)", "reads": ["^BM25Idx(name)", "Graph_KG.nodes", "Graph_KG.rdf_props"],
         "plans": [{"plan": "engine node/property writers, delete_node, Cypher writes (modules 03/08)", "writes": ["nodes", "rdf_props"], "discharge": "finding F-0703 (live), intent-undecided"}]},
        {"invariant": "TXT-I8 (erasing a graph removes its BM25 content)", "reads": ["^BM25Idx(name) with cfg graph = g"],
         "plans": [{"plan": "eraser.erase_graph / erase_nodes (module 12)", "writes": ["content tables", "^KG", "^NKG", "docs"], "discharge": "finding F-0702 (live)"}]},
        {"invariant": "TXT-B8.3 / TXT-I7 (graph scope of an index)", "reads": ["^BM25Idx(name,cfg graph)"],
         "plans": [{"plan": "cls:Graph.KG.BM25Index.Insert (creates a header with no graph)", "writes": ["^BM25Idx(name,cfg)"], "discharge": "finding F-0705 (live)"},
                   {"plan": "cls:Graph.KG.BM25Index.Build", "writes": ["^BM25Idx(name,cfg graph)"], "discharge": f"inspected {B}:168"}]},
        {"invariant": "TXT-D1 stopword list is the 77 words (^BM25Idx('__stop__'))", "reads": ["^BM25Idx('__stop__')"],
         "plans": [{"plan": "Build/Insert/Drop with name '__stop__'", "writes": ["^BM25Idx('__stop__')"], "discharge": "finding F-0706, F-C0701 (live)"},
                   {"plan": "InitStopwords (any Tokenize)", "writes": ["^BM25Idx('__stop__',word)"], "discharge": "journal b-07-fp-writers (77 SETs, idempotent)"}]},
    ]
    env = [
        {"feature": "LOCK +name:timeout (incremental exclusive lock with timeout, $TEST)", "used_for": "BM25 write lock", "source": f"{B}:403-410, :534-539"},
        {"feature": "LOCK released when the owning process ends", "used_for": "reviewed-design crash safety (premise of the model)", "source": f"{B}:403-410"},
        {"feature": "TSTART/TCOMMIT nesting inside a caller's transaction; TROLLBACK with no argument ends every level", "used_for": "Insert/Delete atomicity; F-C0702", "source": f"{B}:460-490, :504-511"},
        {"feature": "$TLEVEL", "used_for": "Insert/Delete error path; SQL SELECT $TLEVEL probe", "source": f"{B}:487, :508; iris_vector_graph/_write_txn.py:64-85"},
        {"feature": "TROLLBACK undoes Set/Kill but not $Increment (P-0702)", "used_for": "plain Set counters in Insert/Delete", "source": f"{B}:24-26"},
        {"feature": "Global Kill of a subtree, Set/$Get/$Data/$Order on globals, no transaction (auto-commit per node)", "used_for": "Build, Drop, Upgrade", "source": f"{B}:99, :542-572, :587-591"},
        {"feature": "Visibility of other processes' uncommitted global writes (no read isolation for globals)", "used_for": "Search/Info during Build or Insert (reader saw N=1 mid-build)", "source": f"{B}:236-374"},
        {"feature": "Global subscript length limit (<SUBSCRIPT> error)", "used_for": "document ids and tokens as subscripts", "source": f"{B}:194, :418, :474"},
        {"feature": "Process-private globals ^|| (P-0704)", "used_for": "Search scores, sort, skipped terms", "source": f"{B}:223-233, :261"},
        {"feature": "Canonical numeric subscript collation (P-0705)", "used_for": "^||bm25sorted descending walk", "source": f"{B}:300-374"},
        {"feature": "%iFind.Utils.Analyze(text,'en',1) tokenizer (P-0701)", "used_for": "Tokenize", "source": f"{B}:60-64"},
        {"feature": "iFind index on docs and %ID %FIND search_index(...) predicate (P-0707)", "used_for": "kg_TXT engine and SQL procedure", "source": "iris_vector_graph/schema.py:2485-2503; iris_vector_graph/_engine/vector.py:917-1054"},
        {"feature": "%SQL.Statement dynamic SQL at default isolation (read uncommitted) with empty parameter bound as NULL (P-0706)", "used_for": "Build's node/property read", "source": f"{B}:123-131"},
        {"feature": "SQL procedures/functions (CREATE OR REPLACE PROCEDURE ... LANGUAGE SQL; [SqlProc] class methods), JSON_TABLE over a function result", "used_for": "kg_TXT, kg_RRF_FUSE, kg_BM25, ivg.bm25.search", "source": "iris_vector_graph/schema.py:2485-2560; iris_src/src/Graph/KG/SqlProcs.cls:131-135; iris_vector_graph/cypher/translator.py:3168-3190"},
        {"feature": "SQL privilege check ($SYSTEM.SQL.Security.CheckPrivilege via Graph.KG.SqlPrivilege)", "used_for": "kg_BM25 RequireSelect on rdf_props", "source": "iris_src/src/Graph/KG/SqlProcs.cls:131-135"},
        {"feature": "Embedded Python (Language = python) and iris.gref global walk", "used_for": "PyOps.HybridSearch; engine index registry in embedded mode", "source": "iris_src/src/Graph/KG/PyOps.cls:370-421; iris_vector_graph/_engine/vector.py:84-104"},
        {"feature": "Native API classMethodValue sharing the DBAPI connection's server process", "used_for": "engine bm25_* calls run in the caller's process and transaction", "source": f"{V}:1749-1880"},
        {"feature": "SQL START TRANSACTION/COMMIT/ROLLBACK end every level (driver autocommit)", "used_for": "caller transactions around BM25 calls (F-C0702 test)", "source": "iris_vector_graph/_write_txn.py:15-18"},
        {"feature": "Journaling of the database holding ^BM25Idx", "used_for": "audit oracle; crash recovery of transactions", "source": "experiment/playbook-completion/traces/journal.py"},
        {"feature": "%CSP.REST routing", "used_for": "POST /hybridSearch", "source": "iris_src/src/Graph/KG/Service.cls:7-9, :286-302"},
    ]
    global ENV
    ENV = env
    so = storage_order()
    # fix the gate's counts from the computed list
    for g_ in gates:
        if g_["gate"] == "3.4-storage-order":
            g_["reason"] = (f"Storage-order scanner ($RUN_DIR/checks/storage-order.json): {so['counts']['flagged_in_module_07']} flagged records in module-07 code "
                            f"plus {len(so['reviewed_sites_not_flagged'])} reviewed unflagged sites; dispositions {so['counts']['by_disposition']}; "
                            f"{so['counts']['not_owned']} other vector.py records are module 06's (adjacent_sites_not_owned). Top-k text answers and fused ranks follow scan order (F-C0703).")
    gid = gates_by_id(gates, so)
    out = {"module": "07", "lane": "breadth-b", "pin": "3eaa79cf", "gates": gates, "gates_by_id": gid, "storage_order": so,
           "invariant_writesets": writesets, "env_features": env,
           "counts": {"entry_points": INV["counts"]["entry_points"], "omissions": INV["counts"]["omissions"],
                      "cells": INV["counts"]["cells"], "cells_without_entry_point": INV["counts"]["cells_without_entry_point"],
                      "entry_points_in_no_cell": len(INV["entry_points_in_no_cell"]),
                      "footprints": fp["summary"]["entry_points"], "footprints_journal_validated": fp["summary"]["journal_validated"],
                      "footprint_store_mismatches": fp["summary"]["store_mismatches"],
                      "model_checks": len(mc), "model_checks_met": met, "model_checks_by_design": by_design,
                      "original_findings": fa["summary"]["original_findings"], "findings_by_disposition": fa["summary"]["by_disposition"],
                      "findings_by_outcome": fa["summary"]["by_outcome"], "new_findings": len(fa["new_findings"]),
                      "env_features": len(env),
                      "storage_order": so["counts"],
                      "gates_by_id_status": {k: sum(1 for v in gid.values() if v["status"] == k) for k in sorted({v["status"] for v in gid.values()})}},
           "registered_runs": ["b-07-fp-writers", "b-07-f0701-race", "b-07-f0704", "b-07-f0702-f0703", "b-07-f0705-f0707", "b-07-f0706",
                               "b-07-f0709", "b-07-f0711", "b-07-probe-fusion", "b-07-unit", "b-07-fc0702-nested-rollback"]}
    (COMP / "modules/07.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    fp = write_footprints()
    fa = write_findings()
    md = write_module(fp, fa)
    print(json.dumps(md["counts"], indent=1))
