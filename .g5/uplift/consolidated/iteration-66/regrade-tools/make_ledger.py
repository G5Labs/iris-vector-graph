#!/usr/bin/env python3
"""Build census-ledger.tsv for the erasure family (iteration 66) against the current census/obligations.tsv.
Usage: make_ledger.py <repo> <out.tsv>"""
import csv, sys, re
repo, out = sys.argv[1], sys.argv[2]
OB = f"{repo}/.g5/Verus_verification/census/obligations.tsv"
rows = {r['id']: r for r in csv.DictReader(open(OB), delimiter='\t')}
cols = list(next(csv.reader(open(OB), delimiter='\t')))
M = ".g5/Verus_verification/models/erasure_stores/erasure_stores.rs::"
PROVE = ".g5/Verus_verification/results/erasure_stores/20261118T051838Z-prove/receipt.json"
BIND = ".g5/Verus_verification/results/erasure_stores/20261118T052216Z-binding/receipt.json"
BASE = "erasure_stores store map (every kind the ontology names; one entry per row or global node); graph spelling via COALESCE"
led = []
def ch(i, col, new, why):
    old = rows[i][col]
    if old != new:
        led.append((i, col, old, new, why))
        rows[i][col] = new

# 1. repoint every erasure_stores receipt to the iteration-66 receipts (the rs changed; the old receipts are stale)
pat_p = re.compile(r"\.g5/Verus_verification/results/erasure_stores/\d{8}T\d{6}Z-prove/receipt\.json")
pat_b = re.compile(r"\.g5/Verus_verification/results/erasure_stores/\d{8}T\d{6}Z-binding/receipt\.json")
for i, r in list(rows.items()):
    for col in ("design_receipts", "as_built"):
        v = pat_b.sub(BIND, pat_p.sub(PROVE, r[col]))
        ch(i, col, v, "repoint: erasure_stores.rs changed in iteration 66; latest proof 051838Z (PASS 66), binding 052216Z (AGREES 36). "
                      "Rows citing 051023Z cited the worker's failed first run (UNEXPECTED 53/2)")

def src(i, add):
    ch(i, "grade_source", rows[i]["grade_source"] + "; " + add, "iteration 66 regrade note")
    ch(i, "iteration", "66", "iteration 66")

# 2. dispositioned regrades
i = "erasure.atomic#o01"
ch(i, "model_locators", "; ".join([M+"witness_list_erase_commits_earlier_chunk", M+"theorem_failed_call_leaves_stores",
   M+"witness_failed_call_keeps_increments", M+"eraser", M+"list_erase"]), "R1-CR-01: cite the witness that carries the refutation; drop the temporal caller-rollback witness (an #o04 case)")
ch(i, "premises", BASE + "; IRIS journal semantics (environment premise): TROLLBACK 1 restores every journalled row and global Set/Kill since the innermost TSTART; "
   "a failing step may leave any partial write (Fault::At.mid); open obligation (R1-CR-01, reachability unestablished): $Increment counters survive the rollback, "
   "the version stamp and the temporal bucket counters (TemporalIndex.RemoveTemporalRow 357), so a call failing after its temporal step would leave the bucket counters changed "
   "(witness_failed_call_keeps_increments); native temporal_rollback_counters shows the same IRIS fact on a temporal delete", "R1-CR-01 premise")
src(i, "it66 (review-1 R1-CR-01): refuted by witness_list_erase_commits_earlier_chunk (unjoined list path, E4); one call's own failure is theorem_failed_call_leaves_stores over any partial write")
for i in ("erasure.atomic#o02",):
    ch(i, "model_locators", "; ".join([M+"theorem_failed_call_leaves_stores", M+"eraser", M+"rollback_to", M+"witness_failed_call_keeps_increments"]), "R1-ER-02")
    ch(i, "premises", BASE + "; IRIS journal semantics (environment premise): TROLLBACK 1 restores every journalled row and global Set/Kill since the innermost TSTART, DDL included; "
       "the Eraser's own steps are modelled (found level, TSTART, TCOMMIT, the Catch's While $TLevel > tTxnLevel { TROLLBACK 1 } then Throw) over any partial write; "
       "open obligation (R1-CR-01, reachability unestablished): $Increment counters (version stamp, temporal bucket counters) are not restored; requires-reviewed: !refused(ep) and is_fault(f) are the statement's 'when an erase fails'", "R1-ER-02, R1-CR-01")
    src(i, "it66 (review-1 R1-ER-02): kept full: the theorem is no longer true by definition; it derives the rollback from the Catch step for any partial write and any caller level; controls failed-call-partial (the Catch closes its level) and catch-rolls-back-every-level (the pre-4.6.4 Catch) mutate that product step and fail it")
i = "erasure.atomic#o03"
ch(i, "model_locators", "; ".join([M+"theorem_failed_call_leaves_stores", M+"theorem_joined_caller_decides", M+"theorem_joined_list_erase_keeps_caller_work",
   M+"lemma_eraser_keeps_levels", M+"lemma_list_keeps_levels", M+"joined_then", M+"list_erase_joined", M+"dedicated_then", M+"witness_dedicated_erase_survives_caller_rollback"]), "R1-ER-02")
ch(i, "premises", "joined by the caller's $TLEVEL (WriteTxn.begin; _iris_obj on the caller's connection); a from_connect engine erases on its own connection and leaves the caller's transaction alone; "
   "IRIS journal semantics (environment premise); the open levels are modelled as a stack; requires-reviewed: !refused(ep) is the statement's erase that runs", "R1-ER-02")
src(i, "it66 (review-1 R1-ER-02): kept full: derived from the Eraser's TSTART/TCOMMIT over the caller's level, its Catch's rollback to the found level, IVG's WriteTxn level (Txn_Undo) for the store path, and the caller's COMMIT/ROLLBACK; controls joined-commits-own (the Eraser's TCOMMIT ends every level), catch-rolls-back-every-level and writetxn-undo-ends-caller-level mutate those steps")
i = "erasure.atomic#o04"
src(i, "it66: theorem_joined_caller_decides is now derived from the transaction steps (R1-ER-02); grade unchanged")
i = "erasure.entry-points#o01"
ch(i, "grade", "partial", "R1-ER-03")
ch(i, "model_locators", "; ".join([M+"theorem_methods_reach_eraser", M+"eraser_of", M+"delete_in_scope"]), "R1-ER-03")
ch(i, "gap", "the method-to-entry-point table (eraser_of) is a transcription of the Python callers, so theorem_methods_reach_eraser restates it (review-1 R1-ER-03); each method's effect is evidenced live by the binding only; erase_bare_nodes not exercised", "R1-ER-03")
src(i, "it66 (review-1 R1-ER-03): full -> partial; delete_node / bulk_delete_nodes now modelled through delete_in_scope (EraseNodeIds, then the reifier sweep)")
i = "erasure.entry-points#o03"
ch(i, "grade", "partial", "review-1 erasure row sample")
ch(i, "check_scope", "narrowed", "review-1 erasure row sample")
ch(i, "gap", "the temporal aggregates of a prefix erase (^KG bucket, tagg, tlast, tin, edgeprop rewritten per bucket by TemporalIndex.EraseNodes) are not modelled for list erases and are skipped by the binding (TAgg, LIST_SKIP); 'what hangs off them' includes them", "review-1")
src(i, "it66 (review-1 erasure sample): full -> partial for the unmodelled temporal aggregates of list erases")
i = "erasure.entry-points.single-path#o02"
ch(i, "grade", "partial", "review-1 R1-ER-02/03 family")
ch(i, "check_scope", "narrowed", "review-1")
ch(i, "gap", "method_ep maps both methods to Ep::Graph by a constant table, so theorem_drop_graph_is_erase_graph is true by definition (review-1); the identity rests on the transcription of `return self.erase_graph(graph_id)` and the live B2 case", "review-1")
src(i, "it66 (review-1 erasure sample): full -> partial (definitional theorem)")
i = "erasure.live-statements#o03"
ch(i, "model_locators", "; ".join([M+"theorem_ids_erase_statements", M+"theorem_edges_erase_statements", M+"witness_list_erase_keeps_closed_statement", M+"live_stmt"]), "R1-ER-04")
ch(i, "premises", BASE + "; a statement entry is live or closed (deletedSeq set; Ledger.cls:8, LedgerApply.cls:680-682) and the row-level erase kills the one the tuple names (Eraser.cls 667-677); requires-reviewed: the entry is a Stmt or Tuple: the statement's subject; 'only those' is the iff", "R1-ER-04")
src(i, "it66 (review-1 R1-ER-04): kept full: the over-claim is repaired (the theorems now remove only the live statement; a closed one is kept); control edge-row-kills-closed mutates EraseEdgeRow's tuple-based kill and fails theorem_edges_erase_statements; live R4_relationship_erase_keeps_closed_statement")
i = "erasure.kept#o06"
ch(i, "check_scope", "narrowed", "R1-CB-08")
ch(i, "model_locators", rows[i]["model_locators"] + "; " + M + "theorem_node_delete_and_bypass_keep_never_kinds", "R1-CB-08")
src(i, "it66 (review-1 R1-CB-08): check_scope narrowed as dispositioned; the delete_edge bypass and the node-delete sweep are now covered too (theorem_node_delete_and_bypass_keep_never_kinds) but caller-transaction compositions and the other bypasses (Cypher DELETE, delete_reification, temporal purge, FHIR resync) are not")
i = "erasure.history#o01"
ch(i, "model_locators", rows[i]["model_locators"] + "; " + M + "theorem_node_delete_and_bypass_keep_never_kinds", "R1-ER-07")
src(i, "it66 (review-1 R1-ER-07): the binding observes every ^IVG.Ledger(rec) node by CRC and every ledger_revisions row by digest; detection observed_history_changed fires; also the node-delete sweep and delete_edge keep them")
i = "erasure.scope#o08"
ch(i, "model_locators", rows[i]["model_locators"] + "; " + M + "ctl", "R1-CB-07")
ch(i, "premises", BASE + "; requires-reviewed: refused(ep) is the statement's 'cannot be stored safely' (GraphKey.Validate: '0' or a control character by $ZStrip '*C': 0-31, 127 and 128-159; Python's mirror refuses 0-31 and 127 first); names carry no NUL (stripped by both)", "R1-CB-07")
src(i, "it66 (review-1 R1-CB-07): the character set is GraphKey's (control python-control-set; live B8_refuse_c1_control: Python passes \\x85, GraphKey refuses, every store unchanged)")
i = "erasure.scope#o02"
ch(i, "gap", "outside-statement: the reifier NODE (not the reification row) survives a graph erase; it is the obligation erasure.scope#o10 (F-1502; witness_named_erase_keeps_reifier_node)", "R1-ER-06")
src(i, "it66: reifier-node residue moved to its own obligation erasure.scope#o10")
i = "erasure.scope#o06"
src(i, "it66: the statement is the graph erase; the node-delete entry points' cross-graph reifier sweep is the split obligation erasure.scope#o09 (refuted, bug-str-121)")
# erasure.scope#o01: version bump (R1-CB-07)
i = "erasure.scope#o01"
ch(i, "model_locators", rows[i]["model_locators"] + "; " + M + "theorem_graph_erase_call", "R1-CB-07")
src(i, "it66 (review-1 R1-CB-07): theorem_graph_erase_call adds the successful call's count, stores and version bump")

# 3. new obligations
def new(i, block, locator, statement, cases, obs, locs, prem, grade, dc, cs, gap, gs, recs=PROVE, ab=None):
    d = dict.fromkeys(cols, "")
    d.update(id=i, block=block, locator=locator, statement=statement, cases=cases, observation=obs,
             model_locators="; ".join(M + x for x in locs), premises=prem, grade=grade, design_check=dc, check_scope=cs,
             design_receipts=recs, as_built=ab or f"binding AGREES {BIND}", parent_entailment="n/a", gap=gap, grade_source=gs, iteration="66")
    assert i not in rows, i
    led.append((i, "NEWROW", "", "\t".join(d[c] for c in cols), "new obligation"))
new("erasure.scope#o09", "erasure.scope", "bullet 1: 'Another graph's content is never touched' (the node-delete entry points: delete_node, bulk_delete_nodes)",
    "A node delete in graph g (delete_node, bulk_delete_nodes) never changes another graph's content, even where it uses the same node IDs.",
    "delete_node(a, g) where a's relationship in g is reified by ev1 and ev1 is also a node of graph h -> h's ev1 kept (as promised); as built it is erased",
    "Graph_KG.nodes and the node's rows in h, get_node(ev1, graph=h)",
    ["theorem_delete_node_sweeps_reifier_everywhere", "witness_delete_node_erases_reifier_in_other_graph", "delete_in_scope", "sweep"],
    BASE + "; the successful path of _delete_in_scope for one batch; holding_graphs is _graphs_holding's own result",
    "full", "refuted", "narrowed", "none",
    "new (iteration 66, split of bullet 1 by entry point; review-1 R1-ER-01): refuted as built by the reifier sweep (bug-str-121) [cases: R1_delete_node_reifier_other_graph, R1_reader_get_node_other_graph, R2_bulk_delete_nodes_reifier_other_graph]",
    ab=f"binding AGREES {BIND}; native OBSERVED_DEFECT .g5/uplift/consolidated/review-1/scratch-evidence/live/r1_reifier_cross_graph.out")
new("erasure.scope#o10", "erasure.scope", "lead: 'An erase removes a graph's content from every store that holds it' (the reifier nodes of its relationships)",
    "A graph erase removes the reifier nodes of g's relationships, which hold the relationship's properties.",
    "erase_graph(g) with a->b of g reified (reifier node written in the default graph with the edge's properties) -> reifier node gone (as promised); as built it stays",
    "Graph_KG.nodes/rdf_props of the reifier, get_node(reifier)",
    ["witness_named_erase_keeps_reifier_node", "keep_graph"],
    BASE, "full", "refuted", "narrowed", "none",
    "new (iteration 66; review-1 R1-ER-06): F-1502's residue as its own obligation; refuted as built [cases: B1_reader_reifier_node_after_erase: the reifier node keeps secret-g1]")
new("erasure.scope#o11", "erasure.scope", "bullet 4: 'Today a graph erase keeps the reifier nodes of its relationships'",
    "Today a graph erase keeps the reifier node of each of its relationships, in the default graph, with its properties.",
    "erase_graph(g) with a reified relationship of g -> reification row gone, reifier node and properties kept",
    "Graph_KG.nodes/rdf_props of the reifier in the default graph",
    ["witness_named_erase_keeps_reifier_node", "theorem_graph_erase_removes_reifications_and_fhir_side"],
    BASE, "full", "proved", "narrowed", "none",
    "new (iteration 66): owner Today bullet (F-1502) [cases: B1_erase_graph_g1, B1_reader_reifier_node_after_erase]")
new("erasure.scope#o12", "erasure.scope", "bullet 5: 'Today delete_node and bulk_delete_nodes also delete, in every graph, any node whose ID is a reifier ID'",
    "Today delete_node and bulk_delete_nodes delete, in every graph holding it, the node whose ID is a reifier ID of a relationship they delete.",
    "delete_node(a, g) with a's relationship reified by ev1, ev1 a node of h and of the default graph -> ev1 gone from both; without a reified relationship nothing outside g changes",
    "Graph_KG.nodes of every graph, get_node",
    ["theorem_delete_node_sweeps_reifier_everywhere", "witness_delete_node_erases_reifier_in_other_graph", "lemma_sweep_removes", "delete_in_scope"],
    BASE + "; the successful path of _delete_in_scope for one batch (a sweep failure after the first delete is not modelled); requires-reviewed: holding_graphs is _graphs_holding's own result on the same rows; r[k] is a node row whose ID is such a reifier: the statement's subject",
    "full", "proved", "narrowed", "none",
    "new (iteration 66): owner Today bullet (bug-str-121); controls delete-node-is-erase-ids, reifier-sweep-default-graph-only [cases: R1, R2, C4 (no reified relationship)]")
new("erasure.entry-points#o07", "erasure.entry-points", "bullet 6: 'Today erasing a list of relationships leaves their temporal events readable'",
    "Today a relationship-list erase leaves the erased relationships' temporal events in place and readable.",
    "store.delete_edges([(s,p,o)], g) on a structural triple with a timestamped event -> row gone, event kept; an ID erase of s removes the event",
    "^KG tout/tin of g, get_edges_in_window",
    ["theorem_edges_erase_keeps_temporal", "witness_edge_erase_leaves_triple_events", "keep_edges"],
    BASE + "; requires-reviewed: 0 <= i < r.len() indexes an entry and its kind is Temporal: the statement's subject",
    "full", "proved", "full", "none",
    "new (iteration 66; review-1 R1-ER-05): owner Today bullet, question q-tmp-007; control edges-erase-temporal (the reviewer's mutant M1) fails [cases: R3_relationship_erase_keeps_events, R3_reader_event_after_relationship_erase]")
led.append(("erasure.scope", "BLOCKHASH", "", "", "governing text changed: two Today bullets (reifier residue, node-delete sweep); obligations 8 -> 12 (o09 split of bullet 1, o10-o12 new)"))
led.append(("erasure.entry-points", "BLOCKHASH", "", "", "governing text changed: Today bullet (relationship-list erase keeps temporal events); obligations 6 -> 7"))
newrows = [x for x in led if x[1] == "NEWROW"]
with open(out, "w") as f:
    f.write("id\tcolumn\told\tnew\treason\n")
    for i, col, o, n, why in led:
        if col == "NEWROW":
            n = "see census-newrows.tsv"
        for v in (i, col, o, n, why):
            assert "\t" not in v and "\n" not in v, (i, col)
        f.write("\t".join((i, col, o, n, why)) + "\n")
with open(out.replace("census-ledger.tsv", "census-newrows.tsv"), "w") as f:
    f.write("\t".join(cols) + "\n")
    for x in newrows:
        f.write(x[3] + "\n")
print(len(led), "ledger entries;", sum(1 for x in led if x[1] == "NEWROW"), "new rows")
