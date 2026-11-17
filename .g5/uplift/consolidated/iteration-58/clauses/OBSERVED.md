# Iteration 58 W1: clause combinations — outcomes of the frozen predictions C1-C9

Predictions: [w62-PAIRS.md](../w62-PAIRS.md) (frozen at `2429a0a3`, unedited), rows C1-C9 (this worker's scope).
Model: [clause_combos](../../../../Verus_verification/models/clause_combos/NOTES.md) (C1, C2, C3). Receipts under
`.g5/Verus_verification/results/clause_combos/`: prove `20261117T082328Z-prove` PASS 28; 17 controls
`20261117T082335Z`..`20261117T082408Z` all EXPECTED_FAIL; binding `20261117T082514Z-binding/receipt.json` AGREES 87/87,
17/17 mutations and 4/4 tampered observations detected. Earlier receipts in that directory belong to superseded
model versions (NOTES.md, "Receipts").

Fixture: run-isolated `ivg-cont-20261117-iris` (127.0.0.1:36317, USER), product pin `3eaa79cf` exported at
`$RUN_DIR/pin`, IRIS Python driver `intersystems-irispython` 5.3.2 from `$RUN_DIR/venv` for every observation (probe1
printed `driver None` from `iris.__version__`; the same venv answers 5.3.2 by `importlib.metadata`, probe2 and the
binding receipt record it). Data written by `create_node` / `create_edge` with prefix `i58c_<hhmmss>_`; reads by
`execute_cypher` on an engine with `native_cypher=False`. No `sync()`; no named graph used.

Raw: [probe1.py](probe1.py) / [probe1.out](probe1.out) (all nine rows, SQL text of the deciding cases),
[probe2.py](probe2.py) / [probe2.out](probe2.out) (leading OPTIONAL, WITH * and FOREACH neighbors, run-time list),
[probe3.py](probe3.py) / [probe3.out](probe3.out) (negation under the -94 boundary).

| Row | Verdict | Observed (actual values) |
|---|---|---|
| C1 OPTIONAL aggregates | **held** | Type with no edge: `a1 [0, 1]`, `a2 [0, 1]` (count(b), count(*)). `[:K]` with a1→b1 (v 10), a1→b2 (v 20): `a1 [2, 2]`, `a2 [0, 1]`; `collect(b.name)` `['b1','b2']` / `[]`, `sum(b.v)` 30 / 0, `avg(b.v)` 15.0 / None; min/max 10, 20 / None, None; `count(DISTINCT b)` 2 / 0. SQL: `COUNT(n2.node_id)`, `COUNT(*)`, sum `CASE WHEN SUM(..) IS NULL THEN CAST(0 AS INTEGER)`, collect `COALESCE(... , '[]')`. Beyond the prediction (probe2, binding A_leading_*): leading `OPTIONAL MATCH (b:NoLabel) RETURN count(b), count(*), sum(b.v), collect(b.v), avg(b.v), min(b.v)` → `[0, 1, 0, [], None, None]`; with a key, `RETURN b.v AS k, sum(b.v), count(b)` → `[None, None, 0]`: sum null, the registered bug-agg-001 (reproduced). |
| C2 UNWIND grouping | **missed** (as the PAIRS row expected) | `UNWIND [1,'1'] AS x RETURN x, count(*)` → `[[1, 2]]` (one group); `RETURN DISTINCT x` → `[[1]]`; `count(DISTINCT x)` 1 (owner Today note in query.aggregation.keys). `UNWIND [1,true]` → `[[1, 2]]` one group, `count(DISTINCT x)` 1, but `RETURN DISTINCT x` → `[[1],[True]]` two rows. `[0,false]` same (binding). `[[1],'[1]']` → one group `[[[1], 2]]`, count(DISTINCT) 1, DISTINCT two rows. Neighbors: `['true',true]` two groups, two DISTINCT rows, count(DISTINCT) 2; `[1,1.0]` one group, one DISTINCT row (open question). `WITH [1, true] AS l UNWIND l AS x` the same (probe2). SQL: `GROUP BY u0.x` while the kind column `x__t` / `x__b` / `x__k` beside it is unused. New: **bug-cyp-149** (1/true and list/spelling half). |
| C3 -94 boundary | **held** | `WHERE b.v = a.v + 1` → SQLCODE -94 (bug-cyp-142). `WHERE b.v = 10 OR b.v = 30` → `[a1, b1], [a2, None]`; `b.v - 1 = 9` → `[a1, b1], [a2, None]`; also `b.v * 2 = 40`, `NOT b.v = 10`, `b.v IN [10, 30]`, `b.v = 10 OR b.name = 'zz'` keep every anchor. `b.v = a.v OR b.v = 10` → -94. Beyond the prediction (probe3, binding C_*): negation decides — `NOT ((b.v = a.v) OR (b.v = 10))` and `NOT ((b.v + 1 = 11) OR (b.v = a.v))` run and keep both anchors; `NOT (b.v = a.v + 1)`, `NOT ((b.v = 10) AND (b.v = a.v))`, `NOT (NOT (... OR b.v = a.v ...))`, `(OR with a.v) AND b.v = 10` → -94. `NOT ((b.v = 10) OR (a.v = 1))` → -94 (outside the modeled domain). Same root as bug-cyp-142 (proposed addendum in [findings.md](findings.md)). |
| C4 UNION values | **partial** | Held: stored double → `'\x01D2.5'` beside `2.5` (two rows; bug-cyp-138), stored list `[1,2]` → `'[1, 2]'` text in a UNION ALL branch (`[[1, 2]]` alone). Missed: `MATCH ()-[r:K]->() RETURN r AS x UNION ALL ...` → each row the text `'{"type":"K…","props":{}}'`; alone the same RETURN answers the map `{'type': 'K…', 'props': {}}`. Not a relationship value either way. The UNION half is bug-cyp-138's root (a branch's relationship-text mark dropped, `_tts_union_branches` 4714); proposed addendum. |
| C5 CALL { } aggregation | **held (values)**; column order departs | `MATCH (a) CALL { WITH a MATCH (a)-[:K]->(b) RETURN count(b) AS c } RETURN a.name, c` → `[[2, 'a1'], [0, 'a2']]`, columns `['c', 'a.name']`: one row per anchor, c = 0 for a2, but the subquery column comes first — the documented deviation (docs/KNOWN_ISSUES.md "A CALL { ... } subquery's column comes first"). Neighbor without aggregate → `[['a1','b1'], ['a1','b2']]`, a2 has no row (held). |
| C6 FOREACH | **partial** | `FOREACH (x IN [1,2] \| SET n.f = x)` → `SyntaxError: UndefinedVariable: Variable 'x' not defined`, `n.f` stays 0 (missed). `FOREACH (x IN [1,2] \| SET n.f = 5)` sets 5 (probe2). `FOREACH (x IN [1,2] \| CREATE (:M {v:x}))` creates v 1 and 2 (held); `FOREACH (x IN [] \| SET n.f = 99)` changes nothing (held). New: **bug-cyp-152**. |
| C7 SET += | **held** | `SET n += {a: 1, b: null}` on `{a:'old', c:'keep'}` → returns `[1, None, 'keep']`; `get_node` `a: 1` (int), no `b`, `c: 'keep'`. `SET n = {a: 1}` → `get_node` holds only `a: 1` (`c` and the `p_id` mirror removed). `SET n += {t: toUpper('x')}` → `t: 'X'`. |
| C8 WITH * | **missed** | `MATCH (a)-[r:K]->(b) WITH * RETURN a.name, type(r), b.name` → SQLCODE -29 `Field 'STAGE1.R' not found`; without `WITH *` → `[['a1','K…','b1'], ['a1','K…','b2']]`. Neighbors (probe2): `WITH * RETURN a.name, b.name` and `WITH * RETURN a.name` (r bound, unused) run; `WITH a, r, b RETURN ..., type(r)` runs. `WITH *, a.v AS av RETURN av` → `CypherParseError: ... col 29: Expected EOF, got ,`. New: **bug-cyp-150**, **bug-cyp-151**. |
| C9 ORDER BY mixed after WITH | **held** | Values `'a'`, `true`, `2`, `1.5`, null (API-written; null = property absent): `WITH n.v AS v ORDER BY v RETURN v` → `'a', True, 1.5, 2, None`; `DESC` → `None, 2, 1.5, True, 'a'`. `RETURN n.v AS v ORDER BY v` (no WITH) the same. |

## Binding summary (C1, C2, C3)

87 cases: A 24 (after-MATCH, K and an edgeless type, both anchors, six aggregates) + 18 (leading pure no-match,
leading grouped no-match, leading pure matched); B 30 (10 two-element lists x groups, count(DISTINCT), DISTINCT rows);
C 15 condition shapes. All agree with the port of clause_combos.rs.
