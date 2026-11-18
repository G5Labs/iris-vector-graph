# R1 erasure review - step 1 independent expectations (written BEFORE reading .g5 ontology/model/handoff)
Sources: docs/adr/0004, 0013, 0015; CONTEXT.md "Erasure" (l.198-207); iris_src/src/Graph/KG/Eraser.cls, GraphStores.cls,
Adjacency.cls RemoveGraph/RemoveNode/Remove, TemporalIndex.cls EraseGraph/EraseNodes; iris_vector_graph/_engine/nodes_edges.py
erase_graph/erase_all/delete_node/bulk_delete_nodes/delete_nodes_by_prefix/delete_edge/bulk_delete_adjacency;
stores/iris_sql_store.py delete_nodes/_eraser_txn/delete_edges/delete_nodes_by_prefix; _write_txn.py; api/gql mutation.py delete_protein;
cypher/translator.py DELETE lowering (l.10660-10810).

## Entry points
EP1 engine.erase_graph(g) / drop_graph -> Eraser.EraseGraph (native call directly; NOT wrapped by _eraser_txn; no caller-txn refusal)
EP2 engine.erase_all -> Eraser.EraseAll (also restore_snapshot non-merge)
EP3 engine.delete_node / bulk_delete_nodes -> _delete_in_scope -> store.delete_nodes -> _eraser_txn + EraseNodeIds per 500-id chunk; then reifier nodes in a 2nd call
EP4 engine.delete_nodes_by_prefix -> store.delete_nodes_by_prefix -> EraseNodes (one call)
EP5 store.delete_edges / engine.bulk_delete_adjacency -> EraseEdges per 500-triple chunk
EP6 Eraser.EraseBareNodes / RetireBareNodes (maintenance, batched txns, earlier batches committed)
EP7 (bypass) engine.delete_edge: raw SQL DELETE rdf_edges (+EdgeScan.DeleteAdjacency if no functional index) - no Eraser
EP8 (bypass) Cypher DELETE / DETACH DELETE: raw SQL DML (labels, props, kg_NodeEmbeddings, reifications, edges, nodes) - no Eraser
EP9 (bypass) GraphQL deleteProtein: raw unscoped SQL, autocommit connection
No HTTP route found for erase (api/routers no hits). No Cypher CALL procedure for erase found.

## Store x entry point (E=erased, K=kept, D=dropped-wholesale/invalidated, -=not touched)
store                         | EraseGraph            | EraseNodeIds/EraseNodes      | EraseEdges            | EraseAll
nodes                         | E (counted)           | E (counted)                  | -                     | E counted
rdf_edges                     | E (counted)           | E incident (NOT counted)     | E (counted)           | E counted
rdf_labels, rdf_props         | E                     | E                            | -                     | E
docs (BM25 SQL corpus)        | E                     | E                            | -                     | E
kg_NodeEmbeddings(+_optimized)| E                     | E                            | -                     | E
kg_EdgeEmbeddings             | E                     | E via incident edges         | E                     | E
routed kg_emb_/kg_eemb_       | rows E in txn; claimed tables DROPPED after commit (failure swallowed); orphans emptied only | rows E (node routes per id, edge routes per edge) | edge routes E | rows E, claimed tables dropped after commit
embedding_registry            | only claimed route rows, after commit; legacy-table rows for graph KEPT | -  | - | all rows E
embedding_quarantine          | K (FR-039)            | K                            | K                     | K
rdf_reifications              | E (by graph's edge ids)| E for incident edges        | E                     | E
reifier NODES (default graph) | K (!)                 | K in Eraser; engine.delete_node removes in a SECOND txn | K | E (all nodes)
fhir_unresolved/definitions/canonical_refs | E        | E per node (source / rsrc_key)| -                    | E
fhir_graphs registry          | K, watermarks zeroed  | -                            | -                     | K, watermarks zeroed
^KG out/in/gen/degc/degw      | E (Adjacency.RemoveGraph) | RemoveNode per id (degw not) | Remove per triple | E
^KG prop, label               | E                     | E per id                     | -                     | E
^KG deg2p, deg2p_exact        | E                     | E if edges touched            | E if removed/had adj  | E
^KG deg2p_exact_merged        | K (unscoped)          | K                            | K                     | E
^KG tout/tin/bucket/tagg/edgeprop/tlast | E          | TemporalIndex.EraseNodes (edges touching ids) | - (!) temporal edges kept | E
^KG labelset                  | K (append-only)       | K                            | K                     | E
^NKG                          | D if graph edges/nodes interned (marked invalidated) | D if at risk | D always | D
^ArnoKG                       | version bump only     | bump                         | bump                  | Killed
^IVG.AlgoCache                | Killed for ALL graphs | killed all if anything removed| killed all if removed | Killed
^IVG.GraphMode(g)             | E                     | -                            | -                     | E
^IVG.TemporalStructural(g)    | K (ADR-0015 config)   | -                            | -                     | E
^IVG.Ledger stmt/tuple        | E for graph (scan stmt by value pos 4) | E for incident edges | E per triple    | E
^IVG.Ledger rec / ledger_revisions | K (ADR-0004; redaction ADR-0013 separate) | K   | K                     | K
^BM25Idx(name) named BM25 index (records its graph) | NOT TOUCHED (!) | not touched | - | not touched
^IVF, ^PLAID, ^VecIdx named vector indexes | NOT TOUCHED (!) | not touched | - | not touched
GraphStores inventory does not list ^BM25Idx/^IVF/^PLAID/^VecIdx at all (neither scoped nor unscoped).

## Count
EraseGraph/EraseAll: nodes rows + rdf_edges rows removed (%ROWCOUNT), not globals. 0 = nothing matched.
EraseNodeIds/EraseNodes: nodes rows only (incident edges not counted). Absent ids not counted, not an error.
EraseEdges: rdf_edges rows. Duplicate triple in one call counted once (second finds no row).
engine.delete_node -> bool(deleted>0); reifier deletions not counted. bulk_delete_nodes -> DeleteResult(deleted, failed); failed counts whole batch.

## Transaction
- Each Eraser method: TSTART ... TCOMMIT; Catch: While $TLevel > entry level {TROLLBACK 1}; rethrow. Nested-safe.
- Invalid graph name: ForIndex/ForName throw BEFORE TSTART. EraseNodes empty prefix refused before anything.
- EraseGraph/EraseAll: DROP TABLE of claimed routes + registry row delete happen AFTER TCOMMIT; failures swallowed (empty route left).
  If called inside a caller transaction (engine.erase_graph has no _eraser_txn and no refuse_in_caller_transaction), TCOMMIT only lowers
  level; DROP TABLE then runs inside the caller's txn; a caller rollback restores rows but not the dropped table (DDL) -> partial state.
- store.delete_nodes/delete_edges: chunks of 500; _eraser_txn commits its own begin when not joined => with no caller txn EACH CHUNK is
  its own transaction. >500 ids: earlier chunks committed if a later chunk fails => non-atomic. bulk_delete_nodes default batch
  (_batch_size_for ~ 16384/(avg_len+3), e.g. ~1260 for 10-char ids) > 500 => "a batch that fails deleted nothing" is false.
- engine.delete_node / _delete_in_scope: node erase txn, then reifier nodes in separate call(s) -> documented partial ("the node is deleted; the reifier nodes are not").
- EraseBareNodes: batches, earlier batches committed (documented).
- Bypasses EP7-EP9: separate SQL txns/autocommit; don't reach ledger stmt/tuple, docs, routes, temporal, ^NKG, AlgoCache.

## Idempotency / edge inputs
- Repeat erase_graph -> 0; still kills ^IVG.AlgoCache for all graphs and bumps __version (side effect on unrelated caches).
- Missing graph -> 0. Missing ids -> 0, adjacency sweep still runs for every named id.
- Duplicates deduped (Python dict.fromkeys; ^||IVG.EraseIds keyed).
- Default graph: COALESCE both sides covers '' and NULL spellings.
- Graph scoping: every SQL delete scoped by COALESCE(graph_id,''); ledger stmt matched by ForName(pos 4)=name; ^NKG/AlgoCache/ArnoKG global.

## Kept by design (governing reason)
- ^IVG.Ledger("rec") + ledger_revisions: ADR-0004 (revision spans graphs; redaction ADR-0013 is the purge).
- ^IVG.TemporalStructural: ADR-0015 configuration.
- fhir_graphs registry row: configuration; watermarks zeroed (spec 231).
- embedding_quarantine: FR-039 (no graph attribution).
- ^KG labelset, ^NKG interning, deg2p_exact_merged, ^ArnoKG: not graph-scoped (GraphStores unscoped list); ^NKG dropped instead.
- orphan routed tables: emptied, never dropped (FR-011 registry is DDL authority).

## Candidate issues to check against ontology/model
C1 named indexes (^BM25Idx graph-recorded, ^IVF/^PLAID/^VecIdx) survive erase; not in inventory.
C2 reifier nodes (default graph) of erased graph's edges survive EraseGraph/EraseNodes/EraseEdges; only engine.delete_node removes, in 2nd txn.
C3 store.delete_nodes / delete_edges multi-chunk non-atomic; bulk_delete_nodes batch claim false.
C4 engine.erase_graph inside caller transaction: post-commit DDL inside caller txn; caller rollback -> partial.
C5 bypass deletion paths (delete_edge, Cypher DELETE, GraphQL deleteProtein) contradict ADR-0004 "every deletion path funnels through the Eraser".
C6 EraseEdges leaves temporal edges for the erased triple (ADR-0009 temporal edge implies structural edge?).
C7 EraseGraph keeps legacy-table embedding_registry rows for the graph (EraseAll removes for stated reason).
C8 count semantics differ per entry point (EraseNodeIds excludes edges).
C9 Eraser header claims inventory-derived list; actually hand-listed (textual test only).
