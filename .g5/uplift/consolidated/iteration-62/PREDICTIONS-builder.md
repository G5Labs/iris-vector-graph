# Iteration 62 builder predictions (written before reading the deciding code)

Written 2026-11-18 by the iteration-62 builder **before** reading `_engine/query.py::_try_native/_execute_parsed/_shadow_compare`,
`cypher/native_plan.py` (`plan_query`, `native_gate`), `cypher/native_shadow.py`, `engine.py` (`_native_privileges`,
option resolution) or `Graph.KG.Cypher.Exec::Run`. Sources used: the owner blocks in
`.g5/ontology/architecture/query-execution.g5.md` (query.native*, query.shadow), the census rows, the current models
(`route_recheck`, proofs-d1d as described by the census) and the tests listed below. The master's frozen predictions
were **not** read before this file was committed.

Expectations marked **[test]** were learned from tests (not independent):
`tests/unit/test_253_native_gates.py`, `test_253_native_declines_mapped_tables.py`, `test_253_native_executor_version.py`,
`test_253_shadow_compare.py`, `test_253_shadow_unlimited.py`, `test_253_native_route.py`,
`tests/integration/test_native_privileges.py`, `tests/e2e/test_253_executor_version_e2e.py`, `test_253_native_plumbing_e2e.py`.
Unmarked expectations come from the owner text or are my own guesses where neither owner nor tests decide.

Common read: `R = MATCH (n:L) WHERE n.k = $k RETURN n.k AS k` over nodes the fixture wrote; reader `execute_cypher`
(columns, rows, Python types) plus whether the native executor answered (`_native_answers`) and the WARNING log.

## Admission (switch resolution and gates)

| id | changing input | neighbour A (predicted) | neighbour B (predicted) | source |
|---|---|---|---|---|
| PA1 | engine default vs `native_cypher=False`, index declared | default: native answers R | False: SQL answers R, same rows/types | owner lead; [test] default True |
| PA2 | `IVG_NATIVE_CYPHER=0` in the process with `native_cypher=True` passed explicitly | SQL answers (environment wins: "every engine in a process") | — the other reachable outcome, explicit True wins and native answers, is what I expect the code may do; I predict the owner's version (env wins), low confidence | owner lead; precedence untested |
| PA3 | same engine, R inside vs after `bulk_load_session` | inside: SQL answers | after exit: native answers again | owner bullet 3; [test] reason "inside bulk_load_session" |
| PA4 | R vs R plus a write clause (`SET`), vs `UNION`, vs `CALL db.labels()` | R native | each other query: no native run at all (planner declines), answered by SQL | owner; [test] planner declines |
| PA5 | read step inside a write (`MATCH ... MERGE` per row) | the owner says the read step "may still run natively" | I predict as built **no** part of a write query reaches the native executor through `execute_cypher` (planner declines the whole query), so this bullet describes no reachable path from `execute_cypher` | owner bullet vs [test] planner |
| PA6 | user holding SELECT on all four graph tables vs lacking it on `rdf_edges` (engine created after the grant state) | all four: native answers R | lacking one: SQL answers R (a label/property read the SQL path can still answer) | owner privileges; [test] probe answers False |
| PA7 | REVOKE on a running engine that already admitted R | native keeps answering (the privilege answer is cached per engine until setup) | a new engine after the REVOKE: SQL | owner metadata ("caches ... until setup runs again"), HD-0901 |
| PA8 | deployed executor at the planner's plan version vs another version / executor class missing | match: native | mismatch or missing: SQL answers, gate reason names "redeploy"; a missing method/class is remembered (asked once), a transient error is asked again | [test] |
| PA9 | label unmapped vs mapped with `map_sql_table` | unmapped: native | mapped: SQL answers the mapped table's rows (native would answer no rows) | owner bullet 6; [test] |
| PA10 | adjacency index declared vs not | declared: native | not declared: SQL | owner bullet 2 (the gate reads only the edge index, F-0906) |

## Fallback

| id | changing input | neighbour A | neighbour B | source |
|---|---|---|---|---|
| PF1 | native executor raises vs answers | raises: `execute_cypher` returns the SQL answer, no exception | answers: native rows | owner; [test] plumbing |
| PF2 | the same failure twice vs two different failures | same reason twice: one WARNING ("fell back to SQL") | two reasons: two WARNINGs | owner; [test] one warning |
| PF3 | what makes a reason "distinct" | I predict the key is the exception's message text, so two failures of one kind whose messages embed different values (e.g. a parameter or class name) warn twice | the other reachable outcome: keyed by exception type, one warning | own guess |
| PF4 | native fails and then the SQL path also fails | the SQL failure is what the reader sees (exception or error result); the native error is not surfaced | — | own guess |
| PF5 | warned-reason state scope | per engine: a new engine warns again for the same reason | per process: it does not | own guess: per engine |

## Shadow

| id | changing input | neighbour A | neighbour B | source |
|---|---|---|---|---|
| PS1 | shadow on, native answer equal to SQL vs differing | equal: an answer is returned (I predict the **native** result object) | differing: `NativeMismatch` raised naming query, parameters and first differing row; nothing returned | owner; [test] plumbing |
| PS2 | shadow on, native answered, SQL raises vs SQL returns an error result | raises: `NativeMismatch` (owner: a SQL failure is raised) | error result: also `NativeMismatch` (columns/rows differ) | owner; own guess for the error-result form |
| PS3 | shadow on, native fails | SQL answer returned, uncompared, no raise (the as-built working assumption; q-cyp-002, HD-0902) | — | owner working assumption |
| PS4 | `cypher_shadow=True` on one engine vs `IVG_CYPHER_SHADOW=1` | attribute: only that engine compares | env: every engine compares; I predict the env is read when the engine is built (an engine built before setting it does not compare) | owner bullet; own guess on timing |
| PS5 | shadow on vs off for a shape whose route already holds SQL | off: SQL answers (route) | on: native answers and is compared every call; no route consulted or recorded | owner route lead; [test] route |
| PS6 | `LIMIT` without full ORDER BY, native keeps other rows than SQL | same count, each native row in the unlimited SQL answer: no raise | a native row outside the unlimited answer, or another count: raise | owner bullet 3; [test] comparator |
| PS7 | value `1` vs `'1'`; also `1` vs `1.0` | `1` vs `'1'`: raise | `1` vs `1.0`: I predict the comparator compares types too and raises | owner; [test] for '1'; own guess for 1.0 |
| PS8 | ORDER BY with ties (not a complete order) | I predict the comparator compares in order whenever the plan is "ordered" (ORDER BY present), so tie order differences raise (F-0907) | if the planner marks only complete orders, ties pass | census gap F-0907 |
| PS9 | `SKIP` | the planner declines `SKIP`, so SKIP is never compared and the LIMIT/SKIP rule is reached only by LIMIT | — | census note |
