# W55: Cypher expressions over values known only at run time (frozen predictions)

Frozen 2026-11-17T02:12Z, **before** reading the translator's handling of string functions, slices, list
comprehensions, `CASE`, `coalesce`, aggregates or write maps, and before reading `Graph.KG.SqlProcs.PropSet`. Sources
used: openCypher (TCK features `String1`, `List2`, `TypeConversion1`-`4`, `Conditional1`-`2`, from a vendored copy of
the public TCK; the pin's submodule is empty), the Cypher 9 function reference for what the TCK leaves unpinned
(`substring`, `left`, `right`, `replace`, `trim` with negative or over-length arguments), the owners
[query.functions](../../../ontology/features/cypher.g5.md#query.functions),
[query.values](../../../ontology/features/cypher.g5.md#query.values) and
[query.aggregation](../../../ontology/features/cypher.g5.md#query.aggregation), and `docs/KNOWN_ISSUES.md`. Prior
knowledge carried in: iteration 47 showed that the translator picks a function's implementation by the argument's
syntax (literal, property read, row variable, parameter), so each pair below holds the expression fixed and varies only
how the argument is known.

Expected outcome = openCypher unless an owner block or KNOWN_ISSUES states a deviation; where they do, the row says so.
Run-time values come from a property written by Cypher `CREATE` (typed storage), an `UNWIND` row or a parameter.
Reader: the `execute_cypher` result row on the SQL path (and the native executor where it accepts the shape); for
writes, the value read back by a later `MATCH ... RETURN` and by `get_node()`.

Ranking by consequence: writes first (a wrong value is persisted), then slices and comprehensions (silent wrong
lists), then string functions and conversions, then `CASE`/`coalesce`, then aggregation (largely owned already by
`query.aggregation`; only the stored-value cases it does not state are sampled).

| ID | Case (run-time input) | Literal neighbor / valid neighbor | Predicted |
|---|---|---|---|
| W1 | `SET n.u = toUpper(n.s), n.c = size(n.l), n.h = n.l[0..2]` over stored `s: 'ab'`, `l: [1, 2, 3]`, then read back | the same `SET` from literals (`toUpper('ab')`, `size([1,2,3])`, `[1,2,3][0..2]`) | both store and read back `'AB'`, `3` (integer), `[1, 2]` (list); `get_node()` agrees |
| W2 | `UNWIND ['ab', 'cd'] AS s CREATE (:L {id: s, u: toUpper(s), k: size(s)})` | `CREATE (:L {id: 'x', u: toUpper('ab'), k: size('ab')})` | rows created with `u` `'AB'`/`'CD'`, `k` 2 (integer); literal neighbor the same |
| W3 | `CREATE (:L {id: 'r', u: randomUUID()})` and `{f: rand()}` | `CREATE (:L {id: 'r2', u: toString(1)})` | owner today: refused, nothing written ([query.functions.random](../../../ontology/features/cypher.g5.md#query.functions.random)); neighbor writes `'1'`. The refusal's source is traced, not predicted |
| W4 | `SET n.age = toInteger(n.age)` over a stored string `'30'` | `SET n.age = 30` over the string `'30'` | both store the integer 30: `RETURN n.age` is `30` (int), `n.age = 30` matches (KNOWN_ISSUES workaround, from 4.7.0, through `Prop_Set`) |
| W5 | `UNWIND [1, 2] AS i CREATE (:L {id: 'w' + toString(i), sq: i * i})` | literal `CREATE (:L {id: 'w9', sq: 3 * 3})` | `sq` read back as integers 1, 4; neighbor 9 |
| S1 | `toUpper`, `toLower`, `trim`, `ltrim`, `rtrim` of a stored `'  Ab c '` | the same of the literal, and of the value from `UNWIND` | `'  AB C '`, `'  ab c '`, `'Ab c'`, `'Ab c '`, `'  Ab c'` for all three; null for a missing property |
| S2 | `substring(n.s, a, b)` over stored `'hello'` with `(a, b)` from `UNWIND` rows `(1, 3)`, `(2, 99)`, `(5, 1)` | literal `substring('hello', 1, 3)`; `substring(n.s, 1)`; a run-time negative start `-1` | `'ell'`, `'llo'`, `''`; literal `'ell'`; `'ello'`; negative start fails the query (ArgumentError) |
| S3 | `left(n.s, k)` and `right(n.s, k)` with `k` from `UNWIND [2, 0, 99]` | literal `left('hello', 2)` | `'he'`/`'lo'`, `''`/`''`, `'hello'`/`'hello'`; literal `'he'` |
| S4 | `replace(n.s, n.f, n.t)` over stored `'banana'`, `'an'`, `'AN'` | literal; a search string not present; a null replacement | `'bANANa'`; same; `'banana'`; null |
| S5 | `size(n.s)` of stored `'hello'`, `size(n.l)` of stored `[1, 2, 3]`, `size(n.e)` of stored `[]` | `size('hello')`, `size([1,2,3])`; `size(x)` for `x` from `UNWIND ['hey']` | `5`, `3`, `0`; literals `5`, `3`; `3` |
| S6 | `toInteger`, `toFloat`, `toString` of stored `'42'`, `'2.9'`, `'foo'`, and of stored numbers `7`, `2.5` | the same of literals; `toBoolean` of stored `'true'`… | `toInteger`: `42`, `2`, null; `toFloat`: `42.0`, `2.9`, null; `toString(7)` `'7'`, `toString(2.5)` `'2.5'`; literals agree. `toBoolean` of a stored string `'true'` is not predicted (KNOWN_ISSUES: such a string reads as a boolean) |
| L1 | `n.l[a..b]` over stored `[1, 2, 3, 4, 5]` with `(a, b)` from `UNWIND` rows `(1, 3)`, `(-3, -1)`, `(3, 1)`, `(-9, 9)` | the same slices with literal bounds; parameters `$a`, `$b` | `[2, 3]`, `[3, 4]`, `[]`, `[1, 2, 3, 4, 5]` for every form (TCK List2) |
| L2 | `n.l[2..]`, `n.l[..-1]` over the stored list | the same over the literal list | `[3, 4, 5]`, `[1, 2, 3, 4]` |
| L3 | `2 IN n.l`, `9 IN n.l` over the stored list | over the literal list | `true`, `false` |
| L4 | `[x IN n.l WHERE x > 2 \| x * 10]` over the stored list | over the stored empty list; over the literal list | `[30, 40, 50]` (integers); `[]`; `[30, 40, 50]` |
| C1 | `CASE n.v WHEN 1 THEN 'one' WHEN 2 THEN 'two' ELSE 'other' END` over stored `v` = 1, 2, 3 and missing | the same over `UNWIND [1, 2, 3, null]` | `'one'`, `'two'`, `'other'`, `'other'` for both |
| C2 | `CASE WHEN n.v > 1 THEN 'big' WHEN n.v IS NULL THEN 'none' ELSE 'small' END` | the same over the `UNWIND` values | `'small'`, `'big'`, `'big'`, `'none'` |
| C3 | `coalesce(n.missing, n.v, 'z')` over a node with stored integer `v` = 1, and over one without `v` | `coalesce(null, 1, 'z')` | `1` (integer), `'z'`; literal `1`. (A relationship's `coalesce(r.p, 'z')` answers stored text: owned by [query.values.relationship_text](../../../ontology/features/cypher.g5.md#query.values.relationship_text), not re-tested) |
| C4 | `CASE WHEN n.flag THEN 'y' ELSE 'n' END` over stored booleans `true`, `false` | the same over `UNWIND [true, false]` | `'y'`, `'n'` for both |
| A1 | `max(n.v)`, `min(n.v)` over stored integers 1, 5, 3; `min(n.s)` over stored `'b'`, `'a'` | over `UNWIND` of the same | `5`, `1` (integers); `'a'` |
| A2 | `count(DISTINCT n.s)` over stored `'a'`, `'a'`, `'b'`, missing | over `UNWIND ['a', 'a', 'b', null]` | `2` for both |
| A3 | `collect(n.l)` over two nodes with stored lists `[1]`, `[2, 3]` | `collect` over `UNWIND [[1], [2, 3]]` | `[[1], [2, 3]]` (lists, any order) for both ([query.aggregation](../../../ontology/features/cypher.g5.md#query.aggregation): a nested list differs from its text) |

Not predicted with confidence: `size()` of a stored string that spells a list (documented deviation, not re-tested),
the error class names for a negative `substring` start (openCypher and Cypher 9 say an error is raised; the class name
is not pinned), and whether the native executor accepts any of these shapes (iteration 47: it declined every function
shape probed).

## Result (iteration 48; [observation](cypherexpr-observed-20261117T021241Z.json), follow-ups after the first observation [2](cypherexpr-observed2-20261117T021350Z.json) and after the source reading [3](cypherexpr-observed3-20261117T021604Z.json))

Reader: the SQL Cypher path (the native executor declined every read shape probed) and, for writes, a later `MATCH`
and `get_node()`.

| ID | Held? | Observed |
|---|---|---|
| W1 | held | run-time and literal `SET` both read back `'AB'`, `3`, `[1, 2]`; `get_node()` agrees |
| W2 | **missed** | refused, nothing written (`<LIST ERROR>`), for the run-time and the literal form alike; the cause is `size()`, not the run-time argument: `toUpper(s)` over `UNWIND` is stored → [bug-cyp-119](../../../Verus_verification/bugs_issues.md#bug-cyp-119) |
| W3 | held | `randomUUID()` and `rand()` refused, nothing written; neighbor `toString(1)` stored `'1'`; `SET n.v = randomUUID()` works |
| W4 | held | both store the integer 30 (`RETURN n.age` 30, `n.age = 30` matches both) |
| W5 | held | `sq` 1, 4; neighbor 9 |
| S1 | held | all five functions agree for stored, literal and `UNWIND`; missing → null |
| S2 | partial | `'ell'`, `'llo'`, `''`, `'ello'` held; a negative start answers `'h'` (literal and run-time alike) instead of an error → [bug-cyp-123](../../../Verus_verification/bugs_issues.md#bug-cyp-123) |
| S3 | partial | `'he'`/`'lo'`, `'hello'` held; length 0 answers null, literal and run-time alike → [bug-cyp-124](../../../Verus_verification/bugs_issues.md#bug-cyp-124) |
| S4 | held | `'bANANa'`, `'banana'`, null |
| S5 | held | `5`, `5` (the stored list has five elements), `0`; literals; `3` |
| S6 | held | `42`, `2`, null; `42.0`, `2.9`, null; `'7'`, `'2.5'`, for stored, literal and `UNWIND` |
| L1 | **missed** | literal bounds held; run-time `(-3, -1)` answers `[]`, `(-3, 5)` the whole list, also with parameters → [bug-cyp-117](../../../Verus_verification/bugs_issues.md#bug-cyp-117); the probe's `n.l[a..3]` did not parse → [bug-cyp-122](../../../Verus_verification/bugs_issues.md#bug-cyp-122) |
| L2 | held | `[3, 4, 5]`, `[1, 2, 3, 4]` for stored and literal |
| L3 | held | `true`, `false` |
| L4 | held | `[30, 40, 50]`, `[]` |
| C1 | held | `'one'`, `'two'`, `'other'`, `'other'` for stored and `UNWIND` |
| C2 | held | `'small'`, `'big'`, `'big'`, `'none'` for both |
| C3 | partial | stored held (`1`, `'z'`, integers kept); the literal neighbor `coalesce(null, 1, 'z')` answers `'1'` → [bug-cyp-121](../../../Verus_verification/bugs_issues.md#bug-cyp-121) |
| C4 | partial | stored booleans held (`'y'`, `'n'`); the `UNWIND` neighbor fails the query at Prepare (SQLCODE -14) → [bug-cyp-118](../../../Verus_verification/bugs_issues.md#bug-cyp-118) |
| A1 | held | `5`, `1` (integers); strings `'a'`/`'b'`; `UNWIND` agrees |
| A2 | held | `2` for both |
| A3 | held | `[[1], [2, 3]]` for both |

Score: 16 held, 4 partial, 2 missed (22). Unlike W54, the literal/run-time split decided only two of the six
departures (L1's negative bound and C4's condition); the others (W2, S2, S3, C3) depend on the function or the
argument's form in a way literals share, and the relationship-write drop (bug-cyp-120) was found by a follow-up probe
(before the source reading), not predicted.

Not frozen (found after the freeze): bug-cyp-120 (relationship `CREATE` between new nodes drops computed values),
bug-cyp-122 (the parse failure, found by the probe's own query), bug-cyp-125 (the driver-conditional `UNWIND $list`
failure, found by the binding harness).
