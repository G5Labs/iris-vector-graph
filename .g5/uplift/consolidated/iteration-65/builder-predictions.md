# Iteration 65 builder predictions: erasure across stores (written before reading the erase code)

Written 2026-11-18 from features/erasure.g5.md (lead, bullets, metadata), search.erasure/.indexes,
structure.degree.cache.*, algorithms.cache.erasure, fhir.erase, structure.multigraph.switch, the census rows, and the
current models (ledger_redaction erased/erased_in, adjacency_maint erases, bulk_delete NOTES). NOT read before this file
was digested: iris_src/src/Graph/KG/Eraser.cls, GraphStores.cls, Adjacency.cls RemoveGraph/RemoveSource,
_engine/nodes_edges.py erase methods, stores/iris_sql_store.py delete_nodes/delete_edges/_eraser_txn.
I have NOT read the master's frozen predictions file contents (only its title line and digest).
Known from the owner's metadata (so these are not blind): erase-all empties temporal-only settings, label-set
interning, ^NKG and the embedding registry; quarantine kept; multigraph mode killed and FHIR watermarks reset on graph
erase; 500-entry chunking; delete_edge bypasses the Eraser; prefix erase selects through node rows.

Observable everywhere: per-store row counts / global node counts in namespace I65*, the return value, raised error.

## W1 graph erase (engine.erase_graph(g); drop_graph(g))
P1a. Two graphs g, h share node IDs n1,n2 with rows, labels, props, an edge n1->n2, a temporal edge, a document, a
     node embedding and an rdf_reifications row in each. erase_graph(g): every g row/entry goes, every h row/entry is
     kept byte-for-byte (rows, ^KG out/in under h, temporal under h, docs/embeddings of h). Neighbour: erase_graph(h).
     The return is 2 node rows + 1 edge row = 3 (labels/props/docs not counted).
P1b. Default graph: rows written through public writers with graph_id NULL (create_node without graph) and, if a
     public writer stores '' , rows with ''. erase_graph(None) and erase_graph('') both remove both spellings (same
     outcome). Neighbour: erase_graph('x') leaves both.
P1c. Unsafe name (e.g. containing a quote or '^' or a very long name): refused with an error before any change;
     every store count unchanged. Neighbour: a legal unusual name ('g-1.x') is erased normally.
P1d. Search indexes: a BM25 index built over g still answers g's node after erase_graph(g) (bug-srch-001 known);
     ^VecIdx / ^PLAID / ^IVF globals unchanged by a single-graph erase. I predict the BM25 index recorded for g is NOT
     cleared (owner promise refuted as built).
P1e. Ledger statements: a ledger-created relationship in g (commit with an edge) leaves ^IVG.Ledger stmt and tuple
     lookup; erase_graph(g) removes both for g and keeps h's. Ledger records/revisions unchanged.
P1f. Multigraph mode on g is cleared by erase_graph(g); h's mode kept. FHIR registration kept, watermarks reset
     (if a FHIR graph is reachable on Community).
P1g. drop_graph(g) gives exactly the same per-store outcome and return value as erase_graph(g).

## W2 prefix / ID-list / relationship-list erase
P2a. delete_nodes_by_prefix(g, 'acme|') removes nodes acme|1, acme|2 in g with their labels, props, incident edges in
     g, adjacency and temporal entries of edges whose endpoint has a node row; same IDs in h kept. Neighbour prefix
     'acme' also removes 'acme-health|x'. Return = node rows + edge rows removed.
P2b. delete_nodes_by_prefix(g, '') is refused (ValueError or Eraser error) and changes nothing. Neighbour: prefix
     with no matching node returns 0 without error.
P2c. ID-list erase (delete_node / bulk_delete_nodes / store.delete_nodes) of [n1] in g removes n1's rows and every g
     edge incident to n1, keeps n2 and n1 in h; a live ledger statement of an erased edge is removed (o03), a statement
     of an untouched edge kept.
P2d. Relationship-list erase (store.delete_edges, bulk_delete_adjacency) removes the listed triples in g (rows and
     adjacency, statements) and no node row. delete_edge(s,p,o) removes the row and adjacency but leaves the ledger
     statement and reifications (bypass; bug-str-013).
P2e. Prefix erase leaves a temporal-only event whose endpoints have no node row, and a prop row with no node row
     (bug-led-007/010 known).

## W3 erase-all (engine.erase_all())
P3a. Every graph's rows/adjacency/temporal/docs/embeddings go; temporal-only settings, label-set interning, ^NKG and
     the whole embedding registry go; quarantine rows and ledger records kept.
P3b. Named search indexes (^BM25Idx, ^IVF, ^PLAID, ^VecIdx) are NOT emptied by erase_all (iteration-63 §6.1 #3);
     the owner promise "erase-all empties every named index" is refuted as built.
P3c. Return value = all node rows + all relationship rows.

## W4 caller transaction
P4a. With a caller's open transaction on the engine's own connection (embedded/shared connection), erase_graph(g)
     joins it: the caller's rollback restores every SQL row and ^KG adjacency; the caller's commit makes it final.
     Neighbour: with no caller transaction the erase commits itself.
P4b. After a caller rollback, derived counters not journaled consistently (the temporal per-source bucket counter,
     witness_rolled_back_delete_undercounts) are not restored; routed tables, if dropped post-commit, are not dropped
     inside the caller txn. I predict the erase never issues COMMIT while $TLEVEL>0 on entry.
P4c. A failure inside the erase (a refused delete) rolls back only the erase's own level and raises; the caller's
     outer work survives until the caller decides.

## W5 routes
P5a. A routed embedding table registered for (g, model) is emptied in the transaction and dropped after commit; its
     registry row is removed. Neighbour: a table named like a route but not in the registry is emptied, not dropped.
P5b. Inside a caller transaction, the drop is deferred/omitted (no DDL inside the caller's transaction): the table is
     emptied and survives; after caller rollback the rows come back.

## W6 count
P6a. erase_graph on a graph that has only temporal-only events / docs and no node or edge rows returns 0 and raises
     nothing, while it removes that content.
P6b. A list erase of 3 IDs where 1 does not exist returns the rows actually removed (2 nodes + their edges), not 3;
     bulk_delete_nodes reports its own count (deleted/failed) separately.

## Owner statements to check (my expectation)
- erasure.atomic WA2 "Erasure ... holds [the ledger head lock] through the outer transaction": I expect EraseGraph
  DOES take ^IVG.Ledger("head") (HD-1201 indicates it was added), so the iteration-63 note "never takes" may be wrong;
  uncertain (50/50).
- single-path: delete_edge runs its own DELETE (expected true -> owner text "every path ... goes through" is a policy,
  as-built violated; keep 'Today').
- search.erasure.indexes bullets 1-2: expected as-built false (erase-all leaves ^BM25Idx/^IVF/^PLAID/^VecIdx).
- degree.cache.uncommitted bullet 3 "until the next rebuild": I predict RemoveGraph also clears AdjNoLock for g, so an
  erase re-enables caching too (bullet incomplete, not wrong).
