# G02-cypher-b fork report (saved verbatim by the integrator)

G02-cypher-b regrade is finished. `rows.tsv` is in `scratch/iteration-64/forks/G02-cypher-b/` with 128 rows (69 full, 59 absent at the start), and the overlay exits 0. I made no edits to the repository, ran no Verus and made no commits. The rows come from the script `make_rows.py` in the same directory.

**1. Counts**
- **Full rows (69):** 56 held, 13 moved to partial, none moved to absent.
- **Absent rows (59):** all held; none moved to partial or full.
- **check_scope full → narrowed:** 8 rows.
- **Statements fixed:** 1 (list_index#o05).
- **Overlay summary:** `rows reviewed: 128; problems naming them: 0; errors: 0` (absent->absent 59, full->full 56, full->partial 13, scope full->narrowed 8, statement changed 1).

Of the 56 held full rows, 17 keep check_scope full: 9 had their `requires` reviewed against the statement and noted in premises, and 8 have no `requires`. Among the held full rows:
- 20 non-empty gaps were cleared or moved to premises. Most only restated the refutation, a finding id, or something a refutation does not need (unmodelled sources, element order, sorting as a delegate).
- 5 gaps were tagged `outside-statement:` (values#o01, sorting#o01, percentile#o12, path_elements#o01, and percentile#o10's moved to premises).

**2. Changed rows (grade or scope)**

| id | old → new | letters | reason |
|---|---|---|---|
| query.values#o05 | full → partial | b | `create_node` is the only Python node writer modelled; floats are integer payloads, so finite vs non-finite is not distinguished |
| query.values#o03 | scope full → narrowed | e | the cited theorem is a point check (texts 29 and 5) |
| relationship_text#o01 | full → partial | c | proved at the decoder; the column selection and arity guard that carry the value to the Cypher cell (#o03) are not modelled (same basis as iteration 63's #o04) |
| relationship_text#o02 | full → partial, scope → narrowed | c | same as #o01 |
| list_index#o05 | full → partial | f, a | statement fixed: "a literal index of any value" → "an integer index written in the query", because bullet 3 excepts a literal null on a list a row holds; the literal-index element type rests only on the `translated_type` definition |
| list_index#o08 | full → partial | b | "every list" includes UNWIND-row and parameter lists, which are not modelled sources |
| reverse#o04 | full → partial, scope → narrowed | d | `known_list` is supplied as false, not derived from the WITH source |
| reverse#o05 | full → partial, scope → narrowed | d | `known_list` is supplied as true |
| dynamic_access#o04 | full → partial | c | the model answers which name is read, not the value; null holds only under a premise |
| range#o01 | full → partial | b, c | run-time IVGRANGE only; the static range is not modelled; element counts stand in for the values |
| range#o02 | full → partial | b | static (literal) range not modelled |
| slice#o03 | full → partial | b | a run-time bound below -len clamps to 0 only by definition, with no theorem |
| strings#o04 | full → partial | b, e | `requires start + l <= n` excludes the "at most l" case past the end |
| coalesce#o03 | full → partial | b | two arguments only; the "only when" direction (node property beside a row value or list literal) is not proved |
| percentile#o07 | scope full → narrowed | e | point check of the three stated instances |
| percentile#o08 | scope full → narrowed | g | single point witness (still a valid refutation) |
| percentile#o10 | scope full → narrowed | e | point check; added the locator `theorem_float_and_cont_kinds_follow_rule` for percentileCont |
| slice#o07 | scope full → narrowed | e | rests on the observed lexer-token premise |

The 32 gap-only changes are listed with their reasons in the `reason` column of `rows.tsv`.

**3. Owner contradictions, duplicates and housekeeping**
- **query.functions.list_index:** bullet 1 says the rule holds for "an index written in the query", but bullet 3 says a literal `l[null]` on a list a row holds gives the first element. This is an internal inconsistency in the block, not a source contradiction, so I did not add an `owner-contradicted:` tag.
- **query.functions.percentile:** the owner's metadata leaves the null-p policy unsettled. I graded #o11 on the statement as written and noted this in `grade_source`.
- **Duplicates or missing obligations:** none found.
- **Housekeeping (report only):**
  - The `relationship_text` "Proved" row in coverage.md (M18) holds only at the decoder.
  - `cypher_fns` NOTES "Limits" still lists percentiles as observed only, but `percentile` is now its own model.

**4. Rows I was unsure about (good reviewer targets)**
- **relationship_text#o01, #o02:** partial follows the iteration-63 precedent for #o04. Arguably the decoder *is* the reader's decision for a marked column.
- **slice#o03:** the run-time below-start case agrees with the rule by definition only.
- **reverse#o04, #o05:** this depends on whether `known_list` counts as a decisive input.
- **dynamic_access#o04 vs #o06:** #o04 is downgraded because null is not represented, while #o06 is held as a "which property is read" claim.
- **list_index#o05:** the statement fix and the type resting on a definition.
- **Held at point-check level:** query.values.equality#o01 (the relationship side is a point check over the general `rel_where_eq` spec) and query.values.sorting#o01 (NaN and strings-before-booleans come from the `rank` definition plus `theorem_rank_order`).
