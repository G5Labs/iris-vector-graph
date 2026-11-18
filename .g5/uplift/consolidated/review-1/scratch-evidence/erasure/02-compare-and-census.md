# Step 2-4 notes (before reading HANDOFF / bugs / open questions)
## Ontology vs my expectations
- C1 named indexes: covered (search.erasure.indexes I-block, bug-srch-001, bug-srch-117, HD-0601 open).
- C2 reifier nodes: recorded only in metadata as "kept as built" (F-1502); census treats as outside-statement for erasure.scope#o02.
- C3 chunk commits: erasure.atomic Today bullet + o05 + bug-led-011. bulk_delete_nodes batch claim: atomic metadata.
- C4 caller-txn DDL: bug-str-119; they observed caller rollback restores the dropped table on IRIS (I65Y/E1). My concern of non-restorable DDL not confirmed; not re-run.
- C5 bypasses: delete_edge/Cypher DELETE/delete_reification/temporal/FHIR listed in single-path. GraphQL api/gql/resolvers/mutation.py delete_protein is DEAD (schema.py routes to examples resolver -> engine.delete_node). Dropped.
- C6 EraseEdges leaves the triple's temporal events: NOT in erasure ontology; temporal.structural has q-tmp-006 for "explicit edge delete"; model keeps Temporal on edge erase silently; mutant M1 (edge erase also removes temporal) passes all 49 -> no claim pins it.
- C7 legacy registry rows kept by graph erase: model config_kind(Registry); erasure.history metadata calls them configuration kept "on purpose"; no governing source; EraseAll comment gives the opposite reasoning. minor.
- NEW C10: engine.delete_node/bulk_delete_nodes reifier cleanup (_delete_in_scope -> _graphs_holding(reifiers)) deletes the reifier id in EVERY graph holding a node/edge row with that id, in a 2nd transaction. Model maps DeleteNode->NodeIds only; binding C4 had no reified incident edge.
- NEW C11: model Stmt has no live/closed distinction; EraseEdgeRow kills only the tuple-referenced (live) stmt; model removes every Stmt with the triple (over-claim for list erases). Binding fixture had no closed stmt.
## Model
- call(): Failed => rows unchanged by definition; joined_then/dedicated_then definitional; theorem_failed_call_leaves_stores, theorem_joined_caller_decides, theorem_refusal_changes_nothing are {} proofs of definitions.
- method_ep: both arms Ep::Graph -> theorem_drop_graph_is_erase_graph definitional; eraser_of a constant table.
- TAgg (bucket/tagg/edgeprop/tlast/tin) not modelled for list erases; binding LIST_SKIP.
- binding observer: Rec and named indexes counted only (WHOLE); ledger_revisions not observed; Stmt observed without deletedSeq.
## Replays
- prove: PASS 49/0 (scratch receipt results/erasure_stores/20261118T045104Z-prove)
- controls frame-ignores-graph, edge-row-keeps-statement, failed-call-partial: EXPECTED_FAIL
- reviewer mutants (scratch/review-1/erasure/mutants): M1 edges-erase-temporal PASS 49 (survives); M2 ids-keep-stmt 1 err; M3 registry-other-graph 1 err; M4 dropgraph->All 1 err; M5 graph-kills-tstruct 1 err.
- binding NOT run: hard-coded namespaces I65B..I65E with assert ns.startswith("I65") and recreate(); cannot be R1E-prefixed without editing.
## Census disagreements (58 rows)
atomic#o02 full->partial; atomic#o03 full->partial; entry-points#o01 full->partial; single-path#o02 full->partial;
live-statements#o03 full->partial; entry-points#o03 full->partial (temporal aggregates/edgeprop of list erases unmodelled).
