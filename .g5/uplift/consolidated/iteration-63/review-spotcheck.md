# Iteration 63 independent spot-check — reviewer verdicts (verbatim content, saved by the builder)

Sample: [review-sample.tsv](review-sample.tsv): every 30th new full row and every 56th new absent row of the merged
census before correction. Reviewer: a fresh general-purpose agent given only the README rules and the sample. Read-only;
nothing rerun. The builder re-checked rows 21, 22, 32 and 33 in source. Paths: models relative to
`.g5/Verus_verification/models/`, ontology relative to `.g5/ontology/`.

| # | id | verdict | reason |
|---|---|---|---|
| 1 | structure.multigraph.layout#o01 | agree | theorem_incremental_equals_rebuild (adjacency_maint.rs:441-444) proves writers' entry = canon (:37-41); one row gives the same bare leaf in either mode, 2+ rows the keyed layout; narrowed fits |
| 2 | structure.degree.cache.warm#o02 | should-be-partial | warm_sources.rs:2 "SQL has no role", so SQL-rows-without-globals is not statable; sources is an input linked to ^KG(out) only by a comment; theorem (:23-26) covers one well-behaved source |
| 3 | temporal.structural.mark.readers#o05 | should-be-partial | RDF/Cypher theorems (temporal_marker.rs:186-209) cover only the marked row and bulk-adopted quals None row, not explicit adoption with the write's own qualifiers; Row has no weight field |
| 4 | algorithms.cache.pagerank#o04 | agree | theorem_added_isolate_recomputes (pagerank_admission.rs:41-46) |
| 5 | search.fusion.python#o05 | statement-wrong | cited theorem_vector_failure_dropped_text_failure_raises shows a text failure raises (fusion_ranking.rs:71-75); statement omits it and copies search.fusion.failed_leg#o03/#o04 |
| 6 | algorithms.op.subgraph.guided#o08 | agree | theorem_filled_cap_expands_only_first_node (retrieval_compose.rs:332-344); frontier order is an input (premises column empty) |
| 7 | query.paths.varlength#o05 | agree | theorem_other_graph_edges_invisible (traversal_strategy.rs:232-249); B2 (:152) covers both walks |
| 8 | query.system-procedures.results#o08 | agree | bad_tail refuses before the row count (procedure_results.rs:44-45); theorem (:119-123) all row counts; narrowing stated |
| 9 | query.paging#o08 | should-be-partial | the 'x' ValueError case only in as_built_page (cypher_clauses.rs:245), not in the theorem (:261-271); numeric-ness an input |
| 10 | query.functions.list_index#o05 | scope-wrong | literal theorem (cypher_fns.rs:115-117) covers only Some(i), no type; type rule only for a RETURN column (:68-72); native decline is a fixture observation |
| 11 | query.functions.slice#o01 | should-be-partial | only a row-variable lower bound proved (cypher_exprs.rs:72-75); l[a..b] does not parse (bug-cyp-122), $l[$s..$e] fails (bug-cyp-125); scope marked full |
| 12 | install.inference#o07 | should-be-partial | theorem_domain_type_not_lifted (inference_rows.rs:149-160) proves only the domain case in one 3-row world |
| 13 | install.export.rdf.content#o11 | should-be-partial | theorem (rdf_reporting.rs:176-178) proves only the two blank subjects; four triples only in the envelope definition (:128-130); parsed file not reached |
| 14 | fhir.graph.lifecycle.tasks#o14 | agree | tick reads saved GraphId and namespace (fhir_tasks.rs:105-108); theorem (:228-231) |
| 15 | structure.node.update#o02 | agree (weak) | replace and None-remove proved (node_edge_update.rs:35-39); "others stay" only by apply_props else-branch (:16) |
| 16 | search.embedding.check_on_write#o04 | should-be-partial | block scope is every vector-writing path (search.g5.md:54-56); model covers store_embedding only (search.rs:2596) |
| 17 | search.ivf.metric#o05 | agree (caveat) | cited theorems stop at the cell index (ivf_entries.rs:155-164); "two entries" needs uncited theorem_cross_cell_reinsert_leaves_stale_entry (:39-43) |
| 18 | search.fusion.rest#o02 | should-be-partial | only /vectorSearch modelled (retrieval_compose NOTES.md:23; rs:170-173); single width-4 witness (:181-188) |
| 19 | temporal.write.retry#o01 | agree | retry_replay.rs:59-62, 18-24, 63-68 |
| 20 | temporal.stats.distinct#o05 | scope-wrong | theorem requires one bucket and one event (temporal_stats.rs:894-897); untouched-bucket contrast not proved |
| 21 | temporal.labelset#o04 | should-be-absent | no resolve function; canon only builds text, store is a Set of texts (temporal_stats.rs:927, 975-977); ResolveLabelSet only in a header comment (:16) |
| 22 | install.schema.not_ready#o04 | should-be-partial | first_access maps input booleans legacy/traces to the reasons (install_lifecycle.rs:58-69); theorem requires record None and no marker (:78) |
| 23 | install.snapshot.temporal#o06 | agree | theorem_text_attribute_preserved (temporal_restore.rs:140-142) with weight_value (:13-15) |
| 24 | install.status.readiness#o02 | should-be-partial | "the operation would answer" is a proxy: route_rows>0 (operator_reports.rs:546), ready_for_bfs (:702); no search/traversal answer modelled |
| 25 | install.status.ledger#o02 | agree | theorem_ledger_stats_failure_reads_zero (operator_reports.rs:797-804) |
| 26 | structure.multigraph.layout#o05 | agree (absent) | no model computes the next key (adjacency_maint.rs:119,181 premise; coverage.md:230) |
| 27 | search.embedding.width.raw-helpers#o01 | agree (absent) | nothing mentions dbapi_utils, normalize_vector, insert_vector |
| 28 | algorithms.op.betweenness#o01 | agree (absent) | algo_options covers option ranges only; coverage.md:502 |
| 29 | query.writes.atomic#o01 | agree (absent) | write_routing.rs:27 Start{Sql, AutocommitOff} only; bolt_tx assumes P-AUTOCOMMIT |
| 30 | query.values#o02 | agree (absent) | node_read.rs:31 and NOTES.md:10 name the gap |
| 31 | install.import#o04 | agree (absent) | platform.rs:853 OtherGuarded does not cover load_obo |
| 32 | fhir.event#o01 | statement-wrong | "since 4.1.0" and "when called" come from api/routers/fhir_event.py:33, not the block (fhir.g5.md:144-145); drops "removed in 5.0" |
| 33 | search.scope.indexes#o03 | should-be-partial | search.rs:2870-2899 models Bm25.graph set by build (BM25Index.cls:168); fusion reader only in playbook proofs-d1d bmn_l2.rs:58-70 |
| 34 | temporal.labelset#o07 | should-be-partial | val_text passes LVal::Num text verbatim (temporal_stats.rs:953-956, 974-976); provider input represented |
| 35 | install.legacy#o06 | agree (absent) | no model of remove_legacy or CallerTransactionOpen |

Totals: agree 18; should-be-partial 12; scope-wrong 2; statement-wrong 2; should-be-absent 1; should-be-full 0.

Reviewer's patterns: (1) reused full grades often rest on what rule 2 excludes — a definition, a proxy, or one entry
point when the statement covers several; the row's own gap often admits it. (2) check_scope full claimed for
single-point witnesses or theorems with narrowing requires. (3) absent searches missed behaviour modelled under another
block; statements sometimes drift from the block text.
