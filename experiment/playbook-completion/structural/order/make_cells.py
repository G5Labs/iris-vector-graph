#!/usr/bin/env python3
"""Writes cells.json (MATRIX-INPUT format) and method.json for gates 3.4-storage-order and 3.6-row-permutation."""
import json
from pathlib import Path

H = Path(__file__).resolve().parent
SO_BASE = ["run:st-check-so-gate", "run:st-control-so-selftest", "experiment/playbook-completion/structural/order/dispositions.json"]
PM_BASE = ["run:st-control-so-perm-selftest"]
SO = {  # module: (product_obligation, findings, extra evidence, basis, remaining)
 "01": ("unknown", [], ["run:st-check-so-perm-01"],
        "36 scan sites in module 01's functions decided (9 single-row aggregates, 8 existence probes, 6 unique keys, 2 one-row system functions, 1 batch drain, 2 ORDER BY present) and 8 order-dependent sites, all inside get_schema_visualization's documented sample ('Sampled, not exact', _engine/schema.py:2775-2777); live, the sample differs by insertion order and every answer is a valid sample (st-check-so-perm-01). No reliance outside a documented sample", ""),
 "03": ("fails", ["F-C0302", "F-0206"], ["run:st-live-so-confirm", "run:st-check-so-perm-03"],
        "reliance shown live: get_node_ids_by_property / get_property_pairs_like with a limit answer the first n rows in scan order (F-C0302, nodes_edges.py:828, 911); _filter_edges_by_properties reads the first rdf_edges row of (s, p, o_id) in any graph (F-0206, nodes_edges.py:605). The other 9 module-03 sites are one-row functions, aggregates or existence probes", ""),
 "06": ("fails", ["F-C0603", "F-C0604", "F-C0642"], ["run:st-check-so-perm-06"],
        "45 sites decided; reliance: VectorRouteGuard TOP 1 over registry rows (F-C0603, GraphStores.cls:308, confirmed-source), _measured_width from one arbitrary row (F-C0604, graph_scoped_embeddings.py:1273, confirmed-source); the top-k statements order by score only, so ties at the cut follow storage order (F-C0642, live st-check-so-perm-06); kg_VECTOR_GRAPH_SEARCH's list(set())[:k] is Python hash order, documented 'in no particular order' (HD-0603, intent-undecided)",
        "F-C0603 and F-C0604 not reproduced live (need two default-model node routes for one graph / a legacy table without a declared width)"),
 "09": ("unknown", [], [],
        "6 sites: Anchors numbers the candidate set in cursor order but every ordered or limited plan sorts before it cuts (set-valued); NamedEnds' TOP 1001 is a count probe that falls back to the general walk; two $Order cut-offs are collation-ordered. No reliance (F-0907 is the shadow comparison's row-order rule, gate 3.7-differential)",
        "no row-permutation run for module 09 in this lane (not in the open list)"),
 "11": ("fails", ["F-0205", "F-C1108"], ["run:st-live-so-11", "run:st-check-so-perm-11"],
        "FindEdge takes the first rdf_edges row of a tuple without ekey or ORDER BY; live, a ledger delete by tuple on a multigraph removes the parallel edge inserted first (plan: idkeys from an index intersection, row-id order) (F-0205); OpDeleteNode allocates statement ids in cursor order (F-C1108, intent-undecided, reproduced again). 5 other sites are existence probes or unique-key reads; the genesis capture orders every scan", ""),
 "12": ("unknown", [], ["run:st-check-so-perm-12"],
        "2 sites in module 12's functions: one single-row aggregate and EraseBareNodes' batch over a $Order root (collation order, batches commit and resume by key); erase_graph and delete_nodes_by_prefix answers and the remaining rows are equal in three insertion orders. GraphStores.cls:308 (VectorRouteGuard) is in 12's class file but is module 06's route rule (F-C0603)", ""),
 "13": ("unknown", [], ["run:st-check-so-perm-13"],
        "2 sites: the revision row read by seq (unique key) and BatchInLock's cut-off, which walks ^IVG.Ledger('rec', seq, ordinal) in key order and resumes from the saved key (the restart-from-first after a stop is F-C1303, progress); receipt and history equal for three commit orders", ""),
 "14": ("unknown", [], ["run:st-check-so-perm-14"],
        "2 sites: fetch_history's TOP n is followed by ORDER BY seq on the assembled statement (replay.py:342-345: the earlier 'intent-undecided' reading of this site was the literal-only scan's false positive) and the revision read by seq (unique key); verify, reconstruct and canonical reads equal in three orders", ""),
 "16": ("fails", ["F-C1642"], ["run:st-live-so-confirm", "run:st-check-so-perm-16"],
        "resolve_nodes pages an unordered SELECT by slicing (gql/resolvers.py:40; F-C1642, live); the sample API's CoreQuery.nodes always orders (created_at by default; ties at a page cut would follow storage order), get_sampled_properties is a documented sample, the old api/gql/resolvers/query.py is not imported (api/gql/schema.py:16)", ""),
 "17": ("fails", ["F-C1742", "F-1701"], ["run:st-live-so-17b", "run:st-live-so-confirm"],
        "query_nodes(limit=n) cuts an unordered node scan (F-C1742, confirmed-source; the TOP spelling of the same statement answers by insertion order, st-live-so-17b) and its property filter reads (s, key) in any graph, first row wins (F-1701); active_queries_sql is a documented bounded sample; the vector helpers order by score (ties: the F-C0642 pattern). Found while confirming: query_nodes(limit) kills the client process with SIGSEGV (F-C1743, gates 3.7-failure-controls / 3.6-capacity)", ""),
 "18": ("unknown", [], [],
        "1 site: restore's registry read by table_name, which only routed tables reach and whose name is derived from (graph, model) (routing.py:32-78): unique. The save path reads whole tables (set-valued); no prefix cut or first-row read in snapshot.py or Snapshot.cls",
        "no row-permutation run for module 18 in this lane (its cell is closed by breadth C, inspected)"),
}
PM = {
 "01": ("unknown", [], "get_schema_visualization: answers differ (documented sample) and all pass the sample validator", "other module-01 reads (status, setup reports) not permuted"),
 "02": ("unknown", [], "list_graphs, count_nodes(graph), get_nodes(graph), get_node, _more_than_one_graph equal in three orders", "Bolt/ledger graph-scope surfaces are other modules'"),
 "03": ("fails", ["F-C0302", "F-0206"], "capped property lookups and the edge property filter differ by insertion order (st-check-so-perm-03); label/node/count reads equal", ""),
 "04": ("unknown", [], "kg_NEIGHBORS, get_edge_count, verify_graph, an unordered Cypher edge read and Adj.Degree equal in three orders", "rebuild/sync outputs (^NKG, degree caches) compared only through these reads"),
 "05": ("unknown", [], "window read (ordered, with a tie at one timestamp), aggregate, bucket groups, latest edges and burst nodes equal in three orders", "purges and the paged window reader across pages not permuted"),
 "06": ("fails", ["F-C0642"], "kg_KNN_VEC cuts three tied scores at k=2 differently per insertion order (st-check-so-perm-06)", ""),
 "07": ("fails", ["F-C0703"], "kg_TXT (LIKE fallback, TOP k without ORDER BY) cuts three tied documents differently per insertion order (st-check-so-perm-07: F-C0703 reproduced live); bm25_search breaks ties by node id and holds", "kg_RRF_FUSE's hash-order tie (F-C0703) not run"),
 "10": ("unknown", [], "PageRank, WCC, CDLP, degree centrality top-k with every degree tied, triangles, khop, subgraph equal in three orders", "random_walk (random by design), Leiden and the Arno/NKG accelerated paths not permuted"),
 "11": ("intent-undecided", ["F-C1108"], "genesis records, detach content, verify and history equal; the detach cascade's statement ids follow insertion order (F-C1108, intent-undecided)", ""),
 "12": ("unknown", [], "erase_graph, delete_nodes_by_prefix and the remaining rows equal in three orders", ""),
 "13": ("unknown", [], "redaction receipt and every revision record (normalised) equal for three commit orders", "the stop/resume path (F-C1303) not permuted"),
 "14": ("unknown", [], "verify, reconstruct(head) and canonical reads equal in three orders", "export_reconstruction files and paged readers not permuted"),
 "15": ("unknown", [], "export_rdf and prov_export (canonical rdflib graphs) and get_reifications equal in three orders", "FHIR sync paths not exercised (no FHIR server classes on Community)"),
 "16": ("fails", ["F-C1642"], "the generated GraphQL resolve_nodes pages differ by insertion order; the sample API's ordered pages hold", "Bolt, HTTP Cypher and REST surfaces not reachable in-process here"),
 "17": ("fails", ["F-C1742"], "query_nodes(label), get_nodes, get_node_count equal; query_nodes(limit=n) never answers here (SIGSEGV, F-C1743) and its statement shape answers by insertion order (st-live-so-17b, F-C1742)", ""),
}
PM_RUN = {m: f"run:st-check-so-perm-{m}" for m in PM}
PM_EXTRA = {"03": ["run:st-live-so-confirm"], "07": ["run:st-live-perm-b07"], "16": ["run:st-live-so-confirm"], "17": ["run:st-live-so-17b", "run:st-live-so-confirm"],
            "13": ["run:st-live-perm-c13"]}
PM_LIVE = {"01": "st-live-perm-a", "02": "st-live-perm-a", "03": "st-live-perm-a", "04": "st-live-perm-a", "05": "st-live-perm-a",
           "06": "st-live-perm-b", "10": "st-live-perm-b", "11": "st-live-perm-c", "12": "st-live-perm-c", "14": "st-live-perm-c",
           "15": "st-live-perm-c", "16": "st-live-perm-c", "17": "st-live-perm-c"}
cells = []
for m, (po, fs, ev, basis, rem) in SO.items():
    cells.append({"gate": "3.4-storage-order", "module": m, "status": "closed", "evidence": SO_BASE + ev,
                  "evidence_grade": "check (extended scan, every site disposed with path:line cites) + inspected" + (" + live" if any("live" in e or "perm" in e for e in ev) else ""),
                  "level": "product", "product_obligation": po, "product_basis": basis, "as_built_findings": fs, "remaining": rem})
for m, (po, fs, basis, rem) in PM.items():
    ev = PM_BASE + [PM_RUN[m]] + ([f"$RUN_DIR/structural/order/{PM_LIVE[m].replace('st-live-', '')}.json (raw log of {PM_LIVE[m]}, which covers several modules)"] if m in PM_LIVE else []) + PM_EXTRA.get(m, [])
    cells.append({"gate": "3.6-row-permutation", "module": m, "status": "closed", "evidence": ev,
                  "evidence_grade": "live (three insertion orders, harness self-test)", "level": "product",
                  "product_obligation": po, "product_basis": basis, "as_built_findings": fs,
                  "remaining": ("permuted reads only; " + rem) if rem else "permuted reads only (listed in the verdict run); the module's other code is covered statically by 3.4-storage-order"})
(H / "cells.json").write_text(json.dumps({"cells": cells}, indent=1))
print(len(cells), "cells")
