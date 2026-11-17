# Owner edits for files W3 does not own (iteration 56; apply verbatim)

Worker W3 applied its own owner edits directly in `features/temporal.g5.md` (`temporal.stats.window` bullet and
metadata, bug-tmp-108) and `features/graph-structure.g5.md` (`structure.adjacency.scan`: the `'0'` spelling and the
character-0 sentence, link to `access.iris_boundary`, metadata). The edits below are for `features/search.g5.md` and
`concepts/access.g5.md`.

## 1. `features/search.g5.md`, block `search.bm25.scoring` (tie order, review 53-55 minor)

Old:

```
- Equal scores are listed in node-ID order, and a search answers the first k of that order. This is as built; no document states a tie order.
```

New:

```
- Scores are compared to 12 decimal places. Equal scores are listed in IRIS subscript order of their node IDs: IDs that are whole numbers come first, in numeric order, and the others follow in character-code order, so `9` comes before `10`, `d10` before `d9` and `dB` before `da`. A search answers the first k of that order. This is as built; no document states a tie order.
```

## 2. `features/search.g5.md`, block `search.bm25` (k at the three readers, bug-srch-113)

Old:

```
- A search returns the top k documents by score, highest first.
```

New:

```
- A search returns the top k documents by score, highest first. `bm25_search` and `CALL ivg.bm25.search` refuse a k below 1. Today the SQL function `kg_BM25` accepts any k and answers an empty list for 0 or less ([finding](../../Verus_verification/bugs_issues.md#bug-srch-113)).
```

## 3. `features/search.g5.md`, metadata `### search.bm25.scoring`

Old:

```
- Formal: [`theorem_stopword_query_empty`, `theorem_repeat_adds_twice`, `theorem_unknown_term_adds_nothing`, `theorem_shorter_document_scores_higher`, `theorem_tf_raises_and_saturates`, `theorem_idf_arg_positive_and_decreasing`, `theorem_worked_example`, `theorem_ties_by_id`](../../Verus_verification/models/bm25_scoring/bm25_scoring.rs)
```

New:

```
- Formal: [`theorem_stopword_query_empty`, `theorem_repeat_adds_twice`, `theorem_unknown_term_adds_nothing`, `theorem_shorter_document_scores_higher`, `theorem_tf_raises_and_saturates`, `theorem_idf_arg_positive_and_decreasing`, `theorem_worked_example`, `theorem_ties_by_id`, `theorem_ties_in_subscript_order`](../../Verus_verification/models/bm25_scoring/bm25_scoring.rs)
```

and append after the "The model computes the length factor ..." paragraph:

```
Tie order (iteration 56, review 53-55): `before_id`/`id_lt` spell out IRIS subscript collation (premise P-COLLATE); the binding's six-way tie (two numeric ids, `d10`, `d9`, `dB`, `da`) agrees on three readers, and the controls `numeric-ids-as-text` and `text-case-folded` fail as expected.
```

## 4. `features/search.g5.md`, metadata `### search.bm25`

Append after the "Audit reproduction" paragraph:

```
Findings: [kg_BM25 answers an empty list for k of 0 or less](../../Verus_verification/bugs_issues.md#bug-srch-113) (review 53-55 minor; modeled as `bm25_scoring.rs::entry_k`, `theorem_sql_k_nonpositive_empty_others_refuse`, bound by binding cases `k:sql@0`, `k:sql@-1`, `k:py@0`, `k:cypher@0`, iteration 56).
```

## 5. `concepts/access.g5.md`, block `access.iris_boundary` (review 53-55 F4)

Old:

```
- SQL functions that read a global first check that the caller may SELECT the table the global stands for.
```

New:

```
- SQL functions that read a global first check that the caller may SELECT the table the global stands for, and otherwise fail naming that table.
- The caller holds a privilege when `%All` is among its roles, or when the login or any of its roles holds it on the table or on the table's whole schema. A privilege on only some of a table's columns does not count.
- A function that checks several tables or privileges names the first one missing, in the order it checks them.
```

## 6. `concepts/access.g5.md`, metadata `### access.iris_boundary`

Old:

```
- Sources: [ADMIN_GUIDE §3 Privileges](../../../docs/ADMIN_GUIDE.md); [SqlPrivilege.cls](../../../iris_src/src/Graph/KG/SqlPrivilege.cls)
```

New:

```
- Sources: [ADMIN_GUIDE §3 Privileges](../../../docs/ADMIN_GUIDE.md); [ADMIN_GUIDE, table or schema counts, columns do not](../../../docs/ADMIN_GUIDE.md#L566-L576); [SqlPrivilege.cls](../../../iris_src/src/Graph/KG/SqlPrivilege.cls)
- Formal: [`require`, `holds_priv`, `check_priv`, `theorem_all_passes`, `theorem_single_check_iff_holds`, `theorem_column_only_select_refused`, `theorem_table_schema_role_select_pass`, `theorem_write_names_first_missing`](../../Verus_verification/models/sql_procs/sql_procs.rs)
```

and append after the "Introduced in 4.6.0 ..." paragraph:

```
Iteration 56 (review 53-55 F4): the verdict is derived from the caller's recorded grants, not supplied. The sql_procs binding calls MatchEdges, MatchEdgesAllGraphs, DijkstraPath, backfill_temporal_rows and rebuild_edge_indices as eight users (no grant, schema SELECT, schema write, table SELECT, column-only SELECT, a role holding table SELECT, schema SELECT with INSERT on nodes only, %All) and compares the verdict and the table it names; CheckPrivilege's treatment of table, schema and column grants is the provider premise P-CHECKPRIV, observed there.
```
