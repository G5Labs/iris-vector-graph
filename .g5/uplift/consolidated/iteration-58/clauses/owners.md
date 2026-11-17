# Iteration 58 W1: proposed owner-block edits (not applied; the builder integrates)

Additive bullets only; no existing statement changes. "Today ..." marks an as-built departure. Paths are relative to
`.g5/ontology/features/`. Finding links point at the entries proposed in this worker's findings (to be copied into
`bugs_issues.md` under the same anchors).

## query.optional (`cypher.g5.md#query.optional`)

Add:

- A leading `OPTIONAL MATCH` with no match gives one row: with aggregates alone, `count(*)` is 1, `count(b)` 0, `sum` 0,
  `avg` null and `collect` `[]`. Today, when the `RETURN` also has a grouping key, `sum` on that row is null instead of 0
  ([finding](../../Verus_verification/bugs_issues.md#bug-agg-001)).
- A `WHERE` inside it that reads only its new variables runs and keeps every row, whatever its `AND`, `OR`, `NOT` and
  arithmetic, such as `b.v = 2 OR b.v = 3` or `b.v - 1 = 2`.
- Today the SQLCODE -94 refusal follows negation: `NOT (b.v = a.v OR b.v = 10)` runs, while `NOT (b.v = a.v + 1)` and
  `NOT (b.v = 10 AND b.v = a.v)` are refused ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-142)).

Metadata: Evidence: [clause_combos](../../Verus_verification/models/clause_combos/NOTES.md) (iteration 58; 28
verified, 17 controls, binding AGREES 87 cases).

## query.aggregation.keys (`cypher.g5.md#query.aggregation.keys`)

Add:

- Today over a list the query holds, a grouping key and `count(DISTINCT)` also make the integer 1 and `true` (0 and
  `false`) one value, and a list and the string spelling it (`[1]` and `'[1]'`) one value, while `RETURN DISTINCT` keeps
  them apart ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-149)). The string `'true'` and `true` stay two
  groups.

## query.aggregation (`cypher.g5.md#query.aggregation`)

No new statement; the existing bullets hold for an `OPTIONAL MATCH` after a `MATCH` (iteration 58 binding `A_after_*`).

## query.union (`cypher.g5.md#query.union`)

Extend the existing Today bullet's list (no new finding): "... a relationship as its JSON text
(`'{"type":"K","props":{}}'`), ..." ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-138)).

## query.values.sorting (`cypher.g5.md#query.values.sorting`)

No change: `WITH n.v AS v ORDER BY v` over `'a'`, `true`, 2, 1.5 and a missing value answers `'a', true, 1.5, 2, null`
and the reverse for `DESC`, as stated (iteration 58 C9, observed only).

## query.writes.computed_values (`cypher.g5.md#query.writes.computed_values`)

Add:

- `SET n += {a: 1, b: null}` stores `a` as an integer, removes `b` and keeps the other properties; `SET n = {a: 1}`
  keeps only `a`; `SET n += {t: toUpper('x')}` stores `'X'` (iteration 58 C7, observed only).

## query.writes (`cypher.g5.md#query.writes`)

Add:

- Today a `FOREACH` over a literal list whose `SET` reads the loop variable, such as
  `FOREACH (x IN [1, 2] | SET n.f = x)`, fails with `UndefinedVariable` and writes nothing; a `CREATE` body reading it
  runs ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-152)).

## query.conformance (`cypher.g5.md#query.conformance`)

Add to the notable deviations:

- Today `WITH *` does not carry a relationship variable: a later `type(r)` fails with SQLCODE -29; list the variables
  instead ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-150)).
- Today `WITH *, a.v AS av` (a star with more items) does not parse
  ([finding](../../Verus_verification/bugs_issues.md#bug-cyp-151)).
- A `CALL { ... }` subquery's column comes first (already in docs/KNOWN_ISSUES.md); its values are right: an aggregate
  over no match answers `count` 0 per outer row (iteration 58 C5).
