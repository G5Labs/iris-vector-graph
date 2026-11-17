# W54: Cypher built-in functions evaluated at run time (frozen predictions)

Frozen 2026-11-17T01:58Z, **before** reading `iris_src/src/Graph/KG/CypherFn.cls`, the `CypherFn*` wrappers in
`SqlProcs.cls` or the translator's function dispatch. Sources used: openCypher (the TCK features `List*`, `Map*`,
`String*`, `Aggregation6`, read from a vendored copy of the public TCK since the pin's submodule is empty), the owner
[query.conformance](../../../ontology/features/cypher.g5.md#query.conformance) ("IVG holds its Cypher to the openCypher
TCK and lists each known deviation in its known-issues guide"), `docs/KNOWN_ISSUES.md` and the CHANGELOG (R269, R274,
R295; the parenthesised-guard fix for `IVGLISTGET`). The owner has no block for built-in functions; the only
function finding is the inherited F-C0841 (`range()` with a run-time step of 0 answers `[]`).

Why this selection: the translator answers a literal argument itself (the TCK passes 3896 of 3896 eligible scenarios
with literals and `WITH`-bound literals), and F-C0841 shows that the same function over a value known only at run
time takes a different path. Each pair below therefore holds the function fixed and varies one input that the
run-time path must decide. Run-time values come from a stored property (written by Cypher `CREATE` or by the Python
API), an `UNWIND` row or a parameter. Expected outcome = openCypher unless KNOWN_ISSUES lists a deviation. Reader:
the `execute_cypher` result row on the SQL path; the native executor too where it accepts the shape.

| ID | Case (run-time input) | Neighbor varied | Predicted |
|---|---|---|---|
| L1 | `head`, `last`, `tail`, `reverse` of a stored list `[1,2,3]` (Cypher-written) | the same of a stored empty list `[]` | `1, 3, [2,3], [3,2,1]`; empty: `null, null, [], []` |
| L2 | `n.l[i]` for `i` from `UNWIND [0, -1, 2]` | `i` = 3 (past the end) and -4 (below `-size`) | `1, 3, 3`; `null`, `null` (no error) |
| L3 | `head`/`last` of a Python-written list `[1, 'a', 2.5, true]` | the same list written by Cypher `CREATE` | `1` (int) and `true` (bool) for both writers |
| L4 | `range(1, 5, s)` for `s` from `UNWIND [2, -1]` | `range(5, 1, s)` for `s` = -2 | `[1,3,5]`, `[]`; `[5,3,1]` |
| L5 | `split(n.s, ',')` of a stored `'a,b,,c'` | a stored `''`, and a missing property | `['a','b','','c']`; `['']`; `null` |
| L6 | `keys(n)` of a node with `a`, `b` | `keys(r)` of a relationship with `x`; `keys(m)` of a run-time map `{a: 1, b: n.missing}` | `['a','b']` (any order); `['x']`; `['a','b']` (a map keeps a null-valued key) |
| L7 | `m[k]` with `k` from a row, `m = {a: 1, b: 'x'}` | a key that is absent | `1` / `'x'`; `null` |
| L8 | `s =~ p` with `s = n.s` stored `'abc'`, `p = 'a.c'` | `p = 'b'` (substring only); `s` missing | `true`; `false` (whole-string match); `null` |
| L9 | `percentileDisc(x, 0.5)` and `percentileCont(x, 0.5)` over `x` in 10, 20, 30, 40 | over no rows; over 10, null, 30 | Disc `20` (nearest rank, as Neo4j), Cont `25.0`; empty: `null`, `null`; with null: Disc `10`, Cont `20.0` |
| L10 | `percentileCont(x, p)` with `p` = 1.5 from a parameter | `p` = 0.5 | `ArgumentError NumberOutOfRange`; `20.0` over 10, 30 |
| L11 | `head(n.num)` of a stored number 5 | `head(n.l)` of a stored list | TypeError (InvalidArgumentType); `1` |
| L12 | `randomUUID()` on three rows; `rand()` on three rows | — | three distinct 36-character UUID strings; three floats in [0, 1) |

Not predicted with confidence: `split(s, '')` (openCypher leaves the empty delimiter to the implementation), the
order of `keys()`, and percentileDisc's rounding rule (openCypher says "nearest", the TCK only pins 3 rows; Neo4j
returns 20 for 0.5 over four values). A stored string that spells a list (`'[1, 2]'`) reads as the list
(KNOWN_ISSUES "A stored string that spells ... a list"); that documented deviation is not re-tested here.

## Result (iteration 47; [observation](cypherfn-observed-20261117T015433Z.json), follow-ups after the source reading [2](cypherfn-observed2-20261117T015618Z.json) and [3](cypherfn-observed3-20261117T020020Z.json))

Reader: the SQL Cypher path. The native executor declined every function shape probed (`_try_native` answered None),
so "both executors" reduces to one here.

| ID | Held? | Observed |
|---|---|---|
| L1 | **missed** (reverse) | `head`, `last`, `tail` held for both lists; `reverse(n.l)` answered the string `']3 ,2 ,1['`, `reverse(n.e)` `']['` → [bug-cyp-112](../../../Verus_verification/bugs_issues.md#bug-cyp-112) |
| L2 | **missed** | a run-time -1, -3 or -4 fails the query (`JSON_ARRAYGET <RANGE>`), 3 answers null; a run-time 0 answers `'1'` (text); literal indexes held → [bug-cyp-111](../../../Verus_verification/bugs_issues.md#bug-cyp-111) |
| L3 | held | `1` and `True` for both writers; `n.t[1]` `'a'`, `n.t[2]` 2.5 |
| L4 | held | `[1,3,5]`, `[]`, `[5,3,1]` (row and parameter); the run-time step 0 answers `[]` (inherited F-C0841, reproduced) |
| L5 | held | `['a','b','','c']`, `['']`, null; `split('abc', '')` `['a','b','c']` |
| L6 | partial | relationship `['x']` and map `['a','b']` held; `keys(n)` of a `create_node` node is `['a','b','id']` (the `id` entry not assessed) |
| L7 | **missed** | `m[k]` answers `'1'` for 1 → [bug-cyp-115](../../../Verus_verification/bugs_issues.md#bug-cyp-115); `n[k]` with `k` from `UNWIND` answers `n.k` (null, or `'gotcha'` when such a property exists) → [bug-cyp-113](../../../Verus_verification/bugs_issues.md#bug-cyp-113); `WITH $m AS m RETURN m[$k]` fails "Incorrect number of parameters" |
| L8 | held | `true`, `false`, null; parameters and rows agree; `'' =~ '.*'` true |
| L9 | held | Disc 20.0, Cont 25.0; empty null, null; with a null 10.0, 20.0; quartiles 10, 30, 17.5 |
| L10 | held | `ArgumentError: NumberOutOfRange` for 1.5 and -1; 20.0 for 0.5 |
| L11 | partial | `head(n.num)` fails, but the error text is empty (no `TypeError`) → [bug-cyp-116](../../../Verus_verification/bugs_issues.md#bug-cyp-116) |
| L12 | **missed** | one UUID and one `rand()` value on every row; `count(DISTINCT randomUUID())` over 50 rows is 1; a `CREATE` with `randomUUID()` is refused → [bug-cyp-114](../../../Verus_verification/bugs_issues.md#bug-cyp-114) |

Score: 6 held, 2 partial, 4 missed. The misses of L1, L2 and L12 came from values known only at run time, and the
literal neighbors of L1 and L2 held; L7's map case also loses the type with a literal key (`m['a']` is `'1'`), and
L11's literal `head(5)` fails without a `TypeError` name as well.
Source reading after the freeze also showed that Cypher reaches only 4 of the 17 `CypherFn` bodies
([query.functions.sql_helpers](../../../ontology/features/cypher.g5.md#query.functions.sql_helpers)).
