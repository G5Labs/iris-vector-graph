#!/usr/bin/env python3
"""Iteration 65 census regrade of the erasure family and its neighbours (replayable).

python3 .g5/uplift/consolidated/iteration-65/regrade-tools/regrade.py [--dry]

Reads the census TSVs, applies the per-obligation changes below (grades, checks, locators, premises, receipts, as-built
evidence, gaps), adds the three obligations the corrected owner text introduced, refreshes the four changed block
hashes and counts, records the excluded-row reason updates, and writes a ledger of every changed row to
iteration-65/regrade-ledger.tsv. The receipts cited are the latest erasure_stores prove and binding receipts.
"""
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
C = REPO / ".g5/Verus_verification/census"
sys.path.insert(0, str(REPO / ".g5/Verus_verification/tools"))
import census  # noqa: E402

RES = REPO / ".g5/Verus_verification/results/erasure_stores"
PROVE = sorted(p for p in RES.glob("*-prove") if (p / "receipt.json").exists())[-1]
BIND = sorted(p for p in RES.glob("*-binding") if (p / "receipt.json").exists())[-1]
PR = str((PROVE / "receipt.json").relative_to(REPO))
BR = str((BIND / "receipt.json").relative_to(REPO))
assert json.loads((BIND / "receipt.json").read_text())["verdict"] == "AGREES"
M = ".g5/Verus_verification/models/erasure_stores/erasure_stores.rs::"
AB = f"binding AGREES {BR}"
IT = "65"


def ml(*items):
    return "; ".join(M + i for i in items)


def rr(note):
    return "requires-reviewed: " + note


BASE = "erasure_stores store map (every kind the ontology names; one entry per row or global node); graph spelling via COALESCE"
U = {
    # ------------------------------------------------------------------ erasure.scope
    "erasure.scope#o01": dict(model_locators=ml("theorem_graph_erase_removes_scoped", "theorem_graph_erase_frame", "keep_graph"),
        premises=BASE + "; " + rr("graph_kill(e.k) && in_g(e, c) is the statement's 'node, label, property or relationship row of graph g'"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1)", gap="none"),
    "erasure.scope#o02": dict(model_locators=ml("theorem_graph_erase_removes_reifications_and_fhir_side", "theorem_graph_erase_keeps_other_reifications", "witness_named_erase_keeps_reifier_node"),
        premises=BASE + "; FHIR rows by direct SQL on the fixture (no FHIR repository); " + rr("an Edge of g and a Reif naming its edge_id, a FhirSide entry of g: the statement's subjects; eid_unique is edge_id's identity"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1)",
        gap="outside-statement: the reifier node itself lives in the default graph and survives with the edge's properties (F-1502; witness_named_erase_keeps_reifier_node, B1_reader_reifier_node_after_erase)"),
    "erasure.scope#o03": dict(model_locators=ml("theorem_graph_erase_removes_scoped", "graph_kill"),
        premises=BASE + "; Adjacency.RemoveGraph kills out/in/gen/degc/degw and ^IVG.AdjNoLock; " + rr("graph_kill(Adj|Gen|Degc|Degw|NoLock) and in_g: the statement's 'g's adjacency entries'"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1)", gap="none"),
    "erasure.scope#o04": dict(model_locators=ml("theorem_graph_erase_removes_scoped", "graph_kill"),
        premises=BASE + "; the Temporal kind stands for every temporal subtree TemporalIndex.EraseGraph kills (tout, tin, bucket, tagg, edgeprop, tlast), temporal-only and structural alike; " + rr("graph_kill(Temporal) and in_g: the statement's subject"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1: tout and the per-graph aggregates of g1 gone, g2's kept)", gap="none"),
    "erasure.scope#o05": dict(model_locators=ml("theorem_graph_erase_removes_scoped", "theorem_graph_erase_keeps_unscoped_except_nkg", "theorem_erase_clears_algo_cache", "witness_graph_erase_drops_unscoped_nkg"),
        premises=BASE + "; ^NKG is dropped (not split) when the graph has an interned node or edge; " + rr("graph_kill kinds (KLabel, KProp, Deg2p, Gen, Degc, GMode, ACache) of g: the statement's subjects"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1)",
        gap="outside-statement: a stale degree served after erase-and-recreate is structure.degree.cache.erase#o02; search-index content is search.erasure.indexes"),
    "erasure.scope#o06": dict(model_locators=ml("theorem_graph_erase_frame", "theorem_graph_erase_keeps_other_reifications", "theorem_graph_erase_routes"),
        premises=BASE + "; " + rr("frame_kind excludes only the derived ^IVG.AlgoCache and ^NKG (not content) and the reifications/routes covered by the other two theorems; eid_unique is edge_id's identity"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1: every g2 entry with node IDs a, b kept)",
        gap="outside-statement: other graphs' derived ^NKG and cached algorithm answers are dropped (bug-str-118)"),
    "erasure.scope#o07": dict(model_locators=ml("theorem_default_graph_both_spellings", "canon"),
        premises=BASE + "; at the pin every content table declares graph_id NOT NULL (binding B0), so only '' is reachable on a current schema; " + rr("graph_kill(k) is the statement's content row"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B3_erase_default_none; B0_null_spelling_reachability)", gap="none"),
    "erasure.scope#o08": dict(model_locators=ml("theorem_refusal_changes_nothing", "theorem_unsafe_or_empty_refused", "valid", "refused"),
        premises=BASE + "; " + rr("refused(ep) is the statement's 'cannot be stored safely' (GraphKey.Validate: '0' or a control character)"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B4_refuse_zero, B5_refuse_control, B6_eraser_refuses_zero_natively)", gap="none"),
    # ------------------------------------------------------------------ live statements
    "erasure.live-statements#o01": dict(model_locators="experiment/playbook-completion/proofs-d1c/src/cx_f0303.rs::counterexample_f0303; experiment/playbook-completion/proofs-d1c/src/stmt_l2.rs::step2; " + ml("witness_delete_edge_leaves_statement", "delete_edge"),
        as_built=AB + " (C7_delete_edge_bypass: statement, tuple and reification stay)"),
    "erasure.live-statements#o02": dict(model_locators=ml("theorem_graph_erase_statements"),
        premises=BASE + "; Stmt is every ^IVG.Ledger(stmt) entry (live or closed) whose graph is g; " + rr("the entry's kind is the statement's subject"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1: g1's stmt and tuple gone, g2's and the default graph's kept)", gap="none"),
    "erasure.live-statements#o03": dict(model_locators=ml("theorem_ids_erase_statements", "theorem_edges_erase_statements"),
        premises=BASE + "; " + rr("the entry is a Stmt or Tuple: the statement's subject; 'only those' is the iff"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (C1_prefix_acme_bar, C6_store_delete_edges)", gap="none"),
    # ------------------------------------------------------------------ history
    "erasure.history#o01": dict(model_locators=ml("theorem_no_erase_touches_history", "theorem_no_erase_touches_kind"),
        premises=BASE + "; every entry point, refused, failed or completed; " + rr("the entry's kind is Rec: the statement's subject"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (Rec counts equal before and after every case)", gap="none"),
    "erasure.history#o03": dict(model_locators=ml("witness_empty_digest_bm25_survives", "witness_digest_reports_kept_setting", "theorem_graph_erase_digest_empty", "digest_empty"),
        premises=BASE + "; the empty-graph reader is GraphStores.Digest(g) over the graph-scoped inventory",
        grade="full", design_check="refuted", check_scope="narrowed", as_built=AB + " (B1_reader_digest_after_erase, B1_reader_bm25_after_erase)", gap="none"),
    # ------------------------------------------------------------------ kept
    "erasure.kept#o01": dict(model_locators=ml("witness_graph_erase_drops_unscoped_nkg", "theorem_graph_erase_keeps_unscoped_except_nkg", "theorem_graph_erase_removes_reifications_and_fhir_side"),
        premises=BASE, grade="full", design_check="refuted", check_scope="narrowed", as_built=AB + " (B1_erase_graph_g1: ^NKG and the default graph's cached answer gone)",
        gap="owner-contradicted: InvalidateDerived drops ^NKG (GraphStores Unscoped) for every graph and EraseGraph deletes the reifications (also Unscoped) of g's edges (Eraser.cls 186-189, 1038-1053; bug-str-118)"),
    "erasure.kept#o02": dict(model_locators=ml("theorem_graph_erase_keeps_settings"),
        premises=BASE + "; " + rr("the entry is a TStruct entry: the statement's subject"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1; Digest still lists it)", gap="none"),
    "erasure.kept#o03": dict(model_locators=ml("theorem_graph_erase_keeps_settings"),
        premises=BASE + "; fhir_graphs rows by direct SQL on the fixture (no FHIR repository); " + rr("the entry is g's FhirReg: the statement's subject"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1)", gap="none"),
    "erasure.kept#o04": dict(model_locators=ml("theorem_graph_erase_removes_scoped", "graph_kill"),
        premises=BASE + "; " + rr("graph_kill(GMode) and in_g: g's mode"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1, B1_reader_is_multigraph_after_erase)", gap="none"),
    "erasure.kept#o05": dict(model_locators=ml("theorem_graph_erase_keeps_settings", "reset_in"),
        premises=BASE + "; fhir_graphs rows by direct SQL; " + rr("the entry is g's FhirReg: the statement's subject"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1: wm 7/9 -> 0/0 for g1, g2's kept)", gap="none"),
    "erasure.kept#o06": dict(model_locators=ml("theorem_no_erase_touches_quarantine", "theorem_no_erase_touches_kind"),
        premises=BASE + "; quarantine row by direct SQL (written only by a migration); " + rr("the entry's kind is Quar: the statement's subject; every Ep and every outcome"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1, B2, B3, D1)", gap="none"),
    "erasure.kept#o07": dict(model_locators=ml("theorem_erase_all_empties", "witness_erase_all_keeps_named_indexes", "keep_all"),
        premises=BASE, grade="full", design_check="refuted", check_scope="narrowed", as_built=AB + " (D1_erase_all: settings, label sets, ^NKG and the registry emptied; ^BM25Idx and ^VecIdx kept)",
        gap="owner-contradicted: the graphless ^IVF, ^PLAID and ^VecIdx record no graph and EraseAll empties none of them (bug-srch-117)"),
    # ------------------------------------------------------------------ atomic
    "erasure.atomic#o01": dict(model_locators=ml("theorem_failed_call_leaves_stores", "call") + "; .g5/Verus_verification/models/temporal/temporal.rs::witness_rolled_back_delete_undercounts",
        premises="IRIS transaction premise: TROLLBACK restores every journaled row and global set in the call, $Increment excepted (the version stamp may move); the temporal witness is the caller-rollback case",
        grade="full", design_check="refuted", check_scope="narrowed",
        design_receipts=PR + "; .g5/Verus_verification/results/temporal/20261116T160854Z-prove/receipt.json",
        as_built=AB + " (E5_graph_erase_fails_fk: every store unchanged after a failure at the nodes DELETE; E3, E4); native OBSERVED_DEFECT .g5/Verus_verification/receipts/native/temporal_rollback_counters.json",
        gap="none"),
    "erasure.atomic#o02": dict(model_locators=ml("theorem_failed_call_leaves_stores", "call"),
        premises="IRIS transaction premise (as #o01); the order 'rollback, then raise' is the Catch's (Eraser.cls 259-262), not split into steps",
        grade="full", design_check="proved", check_scope="narrowed", as_built=AB + " (E5_graph_erase_fails_fk: RuntimeError after its own rollback; E3, E4)", gap="none"),
    "erasure.atomic#o03": dict(model_locators=ml("theorem_joined_caller_decides", "joined_then", "dedicated_then", "witness_dedicated_erase_survives_caller_rollback"),
        premises="joined by the caller's $TLEVEL (WriteTxn.begin; _iris_obj on the caller's connection); a from_connect engine erases on its own connection and leaves the caller's transaction alone",
        grade="full", design_check="proved", check_scope="narrowed", as_built=AB + " (E1, E2, E3: the caller's own write survives the erase's failure and commits with the caller; E6)", gap="none"),
    "erasure.atomic#o04": dict(model_locators=ml("theorem_joined_caller_decides", "joined_then") + "; experiment/playbook-completion/proofs-d9b/src/witness.rs::witness_erasure_rollback; .g5/Verus_verification/models/temporal/temporal.rs::witness_rolled_back_delete_undercounts",
        premises="joined erase (the caller's connection); the post-commit DROP runs inside the caller's transaction and its rollback restored the table on IRIS 2026.1 (bug-str-119)",
        grade="full", design_check="refuted", check_scope="narrowed",
        design_receipts=PR + "; .g5/Verus_verification/results/temporal/20261116T160854Z-prove/receipt.json",
        as_built=AB + " (E1_joined_erase_caller_rollback, E2_joined_erase_caller_commit); native OBSERVED_DEFECT .g5/Verus_verification/receipts/native/temporal_rollback_counters.json",
        gap="outside-statement: what other connections see before the caller commits (bug-002 interplay with redaction) is not modelled"),
    "erasure.atomic#o05": dict(model_locators=ml("witness_list_erase_commits_earlier_chunk", "list_erase", "list_erase_joined"),
        premises="store.delete_nodes with the Eraser deployed; chunks of 500; the failure is an over-long caller-supplied ID (production-reachable)",
        grade="full", design_check="proved", check_scope="narrowed", as_built=AB + " (E4_unjoined_chunk_commits: 500 erased and committed, the second chunk raised and kept n0500; E3 joined erased nothing)", gap="none"),
    # ------------------------------------------------------------------ routes
    "erasure.atomic.routes#o01": dict(model_locators=ml("theorem_graph_erase_routes", "keep_graph"),
        premises=BASE + "; the route rows go in the same effect as the content (the transaction), the DROP after; " + rr("the entry's kind is a route row of g"),
        grade="full", design_check="proved", check_scope="narrowed", as_built=AB + " (B1_erase_graph_g1: the claimed route and the orphan both emptied of g1's rows)", gap="none"),
    "erasure.atomic.routes#o02": dict(model_locators=ml("theorem_graph_erase_routes", "claimed"),
        premises=BASE + "; claimed = a registry row of g names a route-shaped table; df (failed drops) is an input",
        grade="full", design_check="proved", check_scope="narrowed", as_built=AB + " (B1_erase_graph_g1: claimed route dropped, orphan kept; E1: inside a caller's transaction the DROP ran before the caller's commit)",
        gap="owner-contradicted: a joined erase drops the routed table inside the caller's still-open transaction, not after a commit (bug-str-119)"),
    "erasure.atomic.routes#o03": dict(model_locators=ml("theorem_graph_erase_routes", "theorem_erase_all_failed_drop"),
        premises=BASE + "; df (failed drops) is an input; no DROP failure was produced on the fixture",
        grade="full", design_check="refuted", check_scope="narrowed", as_built="none",
        gap="owner-contradicted: erase-all deletes the whole registry inside its transaction, so a failed drop leaves the table without its registry row (Eraser.cls 759; bug-str-120); graph erase keeps it (proved); not reproduced"),
    "erasure.atomic.routes#o04": dict(model_locators=ml("theorem_graph_erase_routes", "claimed"),
        premises=BASE + "; " + rr("the entry is a RouteTable or route row and no registry row of g claims the table: the statement's 'not named by the registry'"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1: orphan emptied of g1's rows, not dropped)", gap="none"),
    # ------------------------------------------------------------------ count
    "erasure.count#o01": dict(model_locators=ml("witness_id_erase_count_omits_relationships", "count_graph", "count_ids", "count_edges"),
        premises=BASE, grade="full", design_check="refuted", check_scope="narrowed", as_built=AB + " (C1_prefix_acme_bar returned 2 for two nodes and their relationships; B1 7 = nodes + relationships)",
        gap="owner-contradicted: prefix and ID erases return node rows only (Eraser.cls 587-590), relationship erases relationship rows only (q-007)"),
    "erasure.count#o02": dict(model_locators=ml("witness_zero_count_with_content_removed", "call"),
        premises=BASE, grade="full", design_check="proved", check_scope="narrowed", as_built=AB + " (B7_erase_empty_graph 0; C3_ids_without_node_rows 0 while removing a temporal event and a property row)", gap="none"),
    "erasure.count#o03": dict(model_locators=ml("theorem_count_ignores_derived"),
        premises=BASE + "; " + rr("!(e.k == Node || e.k == Edge) is the statement's 'derived store'"),
        grade="full", design_check="proved", check_scope="full", as_built=AB, gap="none"),
    "erasure.count#o04": dict(model_locators=ml("theorem_count_adds_rows", "theorem_count_ignores_derived"),
        premises=BASE + "; " + rr("row_of(e, c): a node or relationship row of the graph"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1: 7 = 3 node rows + 4 relationship rows)", gap="none"),
    # ------------------------------------------------------------------ entry points
    "erasure.entry-points#o01": dict(model_locators=ml("theorem_methods_reach_eraser", "eraser_of"),
        premises="the method-to-entry-point table is a transcription of the Python callers; erase_bare_nodes not exercised",
        grade="full", design_check="proved", check_scope="narrowed", as_built=AB + " (each method's observed effect equals its entry point's modelled effect: B1-B3, C1, C4-C6, C8, D1)", gap="none"),
    "erasure.entry-points#o02": dict(model_locators=ml("theorem_erase_all_empties", "keep_all"),
        premises=BASE + "; " + rr("the entry is no kept kind: every graph's content"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (D1_erase_all)", gap="none"),
    "erasure.entry-points#o03": dict(model_locators=ml("theorem_ids_erase", "theorem_prefix_selects_node_rows", "prefix_sel"),
        premises=BASE + "; the prefix selects through node rows of g; " + rr("0 <= i < r.len() only indexes an entry of the store map; the conclusions are conditioned on the statement's own selection"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (C1_prefix_acme_bar)", gap="none"),
    "erasure.entry-points#o04": dict(model_locators=ml("theorem_unsafe_or_empty_refused", "theorem_refusal_changes_nothing"),
        premises=BASE + "; " + rr("refused(ep) holds for every empty prefix (theorem_unsafe_or_empty_refused has no requires)"), grade="full", design_check="proved", check_scope="full", as_built=AB + " (C2_refuse_empty_prefix)", gap="none"),
    "erasure.entry-points#o05": dict(model_locators=ml("theorem_ids_erase", "list_sel"),
        premises=BASE + "; " + rr("0 <= i < r.len() only indexes an entry of the store map; the conclusions are conditioned on the statement's own selection"), grade="full", design_check="proved", check_scope="full", as_built=AB + " (C4_delete_node, C5_bulk_delete_nodes)", gap="none"),
    "erasure.entry-points#o06": dict(model_locators=ml("theorem_edges_erase_keeps_nodes", "keep_edges"),
        premises=BASE + "; " + rr("0 <= i < r.len() only indexes an entry of the store map; the conclusions are conditioned on the statement's own selection"), grade="full", design_check="proved", check_scope="full", as_built=AB + " (C6_store_delete_edges)", gap="none"),
    "erasure.entry-points.single-path#o01": dict(model_locators="experiment/playbook-completion/proofs-d1c/src/cx_f0303.rs::counterexample_f0303; .g5/Verus_verification/models/node_edge_update/node_edge_update.rs::delete_edge; " + ml("witness_delete_edge_leaves_statement", "theorem_methods_reach_eraser"),
        as_built=AB + " (C7_delete_edge_bypass)", gap="none"),
    "erasure.entry-points.single-path#o02": dict(model_locators=ml("theorem_drop_graph_is_erase_graph", "method_ep"),
        premises="drop_graph returns erase_graph (nodes_edges.py 1588-1596)", grade="full", design_check="proved", check_scope="full",
        as_built=AB + " (B2_drop_graph_g2)", gap="none"),
    "erasure.entry-points.single-path#o03": dict(model_locators=ml("theorem_bda_is_erase_edges", "bda_triples"),
        premises="one graph per theorem; across graphs bulk_delete_adjacency calls EraseEdges per graph in turn (observed only)",
        grade="full", design_check="proved", check_scope="narrowed", as_built=AB + " (C8_bulk_delete_adjacency across g1 and g2)", gap="none"),
    "erasure.prefix-match#o01": dict(model_locators=ml("theorem_prefix_selects_node_rows", "has_prefix") + "; .g5/Verus_verification/models/ledger_redaction/redaction.rs::has_prefix",
        premises=BASE, grade="full", design_check="proved", check_scope="full", as_built=AB + " (C1_prefix_acme_bar: acme-health|1 kept)", gap="none"),
    "erasure.prefix-match#o03": dict(model_locators=ml("witness_prefix_leaves_event_ids_remove", "theorem_prefix_selects_node_rows", "theorem_ids_erase") + "; .g5/Verus_verification/models/ledger_redaction/redaction.rs::witness_prefix_erase_leaves_temporal_only_content",
        premises=BASE, grade="full", design_check="proved", check_scope="narrowed", as_built=AB + " (C1: the event of acme|9 stays; C3: the explicit-ID erase removes it)", gap="none"),
    # ------------------------------------------------------------------ neighbours
    "search.erasure#o01": dict(model_locators=ml("theorem_graph_erase_removes_scoped", "graph_kill"),
        premises=BASE + "; " + rr("graph_kill(NEmb|NEmbOpt|NRoute|EEmb|ERoute) and in_g: g's vectors"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1: routed vectors; legacy and edge tables not populated on the fixture)", gap="none"),
    "search.erasure#o02": dict(model_locators=ml("theorem_graph_erase_removes_scoped"),
        premises=BASE + "; docs rows by direct SQL (no engine writer); " + rr("graph_kill(Doc) and in_g"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1_erase_graph_g1)", gap="none"),
    "search.erasure#o03": dict(model_locators=ml("theorem_graph_erase_frame"),
        premises=BASE + "; " + rr("frame_kind holds for every vector kind; !in_g: another graph's"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1: g2's routed vector for the shared id a kept)", gap="none"),
    "search.erasure.indexes#o03": dict(model_locators=ml("witness_erase_all_keeps_named_indexes", "theorem_no_erase_touches_kind"),
        premises=BASE, grade="full", design_check="refuted", check_scope="narrowed", as_built=AB + " (D1_erase_all, D1_reader_bm25_after_erase_all)", gap="none"),
    "algorithms.cache.erasure#o01": dict(model_locators=ml("theorem_erase_clears_algo_cache", "theorem_ids_erase"),
        premises=BASE + "; an ID or prefix erase that removes no node, relationship or adjacency entry keeps the cache (nothing structural was erased)",
        grade="full", design_check="proved", check_scope="narrowed", as_built=AB + " (B1_erase_graph_g1: the default graph's cached WCC answer gone)", gap="none"),
    "structure.degree.cache.erase#o01": dict(model_locators=ml("theorem_graph_erase_removes_scoped", "theorem_ids_erase") + "; .g5/Verus_verification/models/graph_structure/graph_structure.rs::lemma_killcommitted",
        premises=BASE + "; " + rr("Gen/Degc of g (graph erase) or of an erased id (node_kill): the statement's subjects"),
        grade="full", design_check="proved", check_scope="full", as_built=AB + " (B1, C4)", gap="none"),
}
# the obligations whose statement or locator moves with the corrected owner text
S = {
    "structure.degree.cache.uncommitted#o04": dict(
        locator="bullet 3: 'A writer that cannot get the lock within 5 seconds still writes, and turns degree caching off for its graph until the next rebuild or erase of that graph'",
        statement="A writer denied the lock for 5 seconds still writes its row and entry and turns degree caching off for its graph until the next rebuild or erase of that graph",
        model_locators=".g5/Verus_verification/models/graph_structure/graph_structure.rs::theorem_as_built_cache_sound; " + ml("witness_graph_erase_clears_nolock"),
        gap="lockless writers with AdjNoLock are modelled (graph_structure); the 5-second timeout and the rebuild's clearing are not; the erase's clearing is (witness_graph_erase_clears_nolock, B1)",
        as_built=AB + " (B1_erase_graph_g1: ^IVG.AdjNoLock(g1) gone, g2's kept)"),
}
NEW = [
    dict(id="erasure.atomic#o06", block="erasure.atomic", locator="working-assumption 2: 'Today no erase path takes the head lock, and only redaction's final step re-checks liveness under it'",
         statement="Today no erase path takes the ledger head lock; only redaction's final step re-checks liveness under it.",
         cases="erase_graph / EraseEdges concurrent with a ledger commit or redaction -> the erase does not wait on ^IVG.Ledger(head)",
         observation="lock table during an erase; the order of stmt kills against a commit", model_locators="", premises="",
         grade="absent", design_check="none", check_scope="n/a", design_receipts="", as_built="inspection read iris_src/src/Graph/KG/Eraser.cls",
         parent_entailment="", gap="no model of locks around an erase (erasure_stores has none); source: Eraser.cls takes no Lock on ^IVG.Ledger(head) (F-1114); LedgerRedact.cls:282 locks only the final step",
         grade_source="new (iteration 65): owner working assumption corrected to intent + Today", iteration=IT),
    dict(id="erasure.entry-points.single-path#o04", block="erasure.entry-points.single-path", locator="bullet 3: 'Today delete_edge runs its own delete'",
         statement="Today delete_edge removes the relationship row and its adjacency but leaves the relationship's live statement, reification and edge vector.",
         cases="delete_edge(s,p,o,g) on a ledger-created, reified relationship -> row and adjacency gone; stmt, tuple, reification, edge vector kept (store.delete_edges removes them)",
         observation="rdf_edges, ^KG out/in, ^IVG.Ledger stmt/tuple, rdf_reifications, kg_EdgeEmbeddings",
         model_locators=ml("witness_delete_edge_leaves_statement", "delete_edge"), premises=BASE,
         grade="full", design_check="proved", check_scope="narrowed", design_receipts=PR,
         as_built=AB + " (C7_delete_edge_bypass; the edge vector was not populated on the fixture)", parent_entailment="", gap="none",
         grade_source="new (iteration 65): owner Today bullet (bug-str-013)", iteration=IT),
    dict(id="search.erasure.indexes#o05", block="search.erasure.indexes", locator="bullet 3: 'Today no erase empties a named index'",
         statement="Today no erase empties a named index: after erasing every graph, BM25 and VecIndex indexes still hold the erased entries.",
         cases="erase_all (or any erase) with BM25 / VecIndex / IVF / PLAID entries -> every entry kept; bm25_search still answers",
         observation="^BM25Idx, ^VecIdx, ^IVF, ^PLAID; bm25_search",
         model_locators=ml("theorem_no_erase_touches_kind", "witness_erase_all_keeps_named_indexes"),
         premises=BASE + "; " + rr("never_kind(k) is the statement's 'named index'; every Ep and outcome"),
         grade="full", design_check="proved", check_scope="full", design_receipts=PR,
         as_built=AB + " (D1_erase_all: 95 ^BM25Idx and 10 ^VecIdx nodes kept; D1_reader_bm25_after_erase_all)", parent_entailment="", gap="none",
         grade_source="new (iteration 65): owner Today bullet (bug-srch-117)", iteration=IT),
]
EXCL = {"erasure.atomic#x02": "the intended serialisation (HD-1201, q-004 open); its Today half is erasure.atomic#o06"}


def split_cases(s):
    """'binding AGREES <path> (cases...)<rest>' -> ('binding AGREES <path><rest>', 'cases...'): the census reads the path."""
    if not s.startswith(AB + " ("):
        return s, ""
    i, d = len(AB) + 1, 0
    for j in range(i, len(s)):
        d += {"(": 1, ")": -1}.get(s[j], 0)
        if d == 0:
            return AB + s[j + 1:], s[i + 1:j]
    raise ValueError(s)


def main(dry):
    cols = census.OBL_COLS if hasattr(census, "OBL_COLS") else None
    rows = list(csv.DictReader(open(C / "obligations.tsv"), delimiter="\t"))
    cols = list(rows[0].keys())
    ledger = []
    by = {r["id"]: r for r in rows}
    for oid, ch in list(U.items()) + list(S.items()):
        r = by[oid]
        old = dict(r)
        ch = dict(ch)
        if ch.get("grade") or ch.get("design_check"):
            ch.setdefault("design_receipts", PR if ch.get("design_check", r["design_check"]) != "none" else "")
        if "model_locators" in ch and "design_receipts" not in ch and r["design_check"] != "none":
            # a row whose check is unchanged but cites erasure_stores: add the receipt
            ch["design_receipts"] = "; ".join(x for x in [r["design_receipts"], PR] if x)
        note = ""
        if "as_built" in ch:
            ch["as_built"], note = split_cases(ch["as_built"])
        r.update(ch)
        r["grade_source"] = (old["grade_source"] + "; " if old["grade_source"] else "") + "it65 erasure_stores regrade" + \
            (f" [cases: {note}]" if note else "")
        r["iteration"] = IT
        diff = {k: r[k] for k in cols if r[k] != old[k]}
        ledger.append({"id": oid, "old_grade": old["grade"], "new_grade": r["grade"], "old_check": old["design_check"],
                       "new_check": r["design_check"], "old_scope": old["check_scope"], "new_scope": r["check_scope"],
                       "changes": json.dumps(diff, sort_keys=True)})
    for n in NEW:
        assert n["id"] not in by
        n["as_built"], note = split_cases(n["as_built"])
        if note:
            n["grade_source"] += f" [cases: {note}]"
        row = {k: n.get(k, "") for k in cols}
        rows.append(row)
        ledger.append({"id": n["id"], "old_grade": "(new)", "new_grade": n["grade"], "old_check": "", "new_check": n["design_check"],
                       "old_scope": "", "new_scope": n["check_scope"], "changes": json.dumps(row, sort_keys=True)})
    order = {r["id"]: i for i, r in enumerate(rows)}
    rows.sort(key=lambda r: (r["block"], int(r["id"].split("#o")[1]) if "#o" in r["id"] else 0) if False else order[r["id"]])
    # keep each block's rows together: insert new rows after their block's last row
    out = []
    pending = {n["id"]: next(r for r in rows if r["id"] == n["id"]) for n in NEW}
    base = [r for r in rows if r["id"] not in pending]
    for i, r in enumerate(base):
        out.append(r)
        nxt = base[i + 1]["block"] if i + 1 < len(base) else None
        if nxt != r["block"]:
            out += [p for p in pending.values() if p["block"] == r["block"]]
    assert len(out) == len(rows)
    # blocks: hashes and counts
    onto = census.parse_ontology()
    brows = list(csv.DictReader(open(C / "blocks.tsv"), delimiter="\t"))
    bcols = list(brows[0].keys())
    for b in brows:
        if b["block"] in ("erasure.atomic", "erasure.entry-points.single-path", "search.erasure.indexes",
                          "structure.degree.cache.uncommitted"):
            ledger.append({"id": b["block"], "old_grade": "block", "new_grade": "block", "old_check": b["sha256"][:12],
                           "new_check": onto[b["block"]]["sha256"][:12], "old_scope": b["obligations"], "new_scope": "",
                           "changes": "governing text corrected (iteration 65)"})
            b["sha256"] = onto[b["block"]]["sha256"]
            b["obligations"] = str(sum(1 for r in out if r["block"] == b["block"]))
            ledger[-1]["new_scope"] = b["obligations"]
            b["iteration"] = IT
    erows = list(csv.DictReader(open(C / "excluded.tsv"), delimiter="\t"))
    ecols = list(erows[0].keys())
    for e in erows:
        if e["id"] in EXCL:
            e["reason"] = EXCL[e["id"]]
            e["iteration"] = IT
    if dry:
        print(json.dumps(ledger[:3], indent=1)[:2000])
        return
    census.write_tsv(C / "obligations.tsv", cols, out)
    census.write_tsv(C / "blocks.tsv", bcols, brows)
    census.write_tsv(C / "excluded.tsv", ecols, erows)
    lp = REPO / ".g5/uplift/consolidated/iteration-65/regrade-ledger.tsv"
    with open(lp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ledger[0].keys()), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(ledger)
    print(f"{len(ledger)} ledger rows; receipts {PR} {BR}")


if __name__ == "__main__":
    main("--dry" in sys.argv)
