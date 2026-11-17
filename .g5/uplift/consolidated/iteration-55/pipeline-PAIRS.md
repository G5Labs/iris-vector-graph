# Iteration 55 (W60): one answer through the pipeline to the driver — frozen predictions

Frozen before any deciding source in `iris_vector_graph/_engine/query.py` or `iris_vector_graph/bolt_server.py` was
read in this iteration (only `start_tcp_bolt_server`'s signature and the server's Bolt start-up lines in
`cypher_api.py` were looked at, to know how to start a listener). Sources of each expectation: the owners
([query.values](../../../ontology/features/cypher.g5.md#query.values),
[access.bolt](../../../ontology/concepts/access.g5.md#access.bolt),
[access.bolt.results](../../../ontology/concepts/access.g5.md#access.bolt.results),
[access.surfaces](../../../ontology/concepts/access.g5.md#access.surfaces),
[query.paging](../../../ontology/features/cypher.g5.md#query.paging),
[query.native.equal-answers](../../../ontology/features/cypher.g5.md#query.native.equal-answers)); the product docs at
the pin (USER_GUIDE §3 and "Shortest path", ADMIN_API "Authentication", KNOWN_ISSUES, README, `docs/dev/TCK.md`,
`docs/dev/driver-drift.md` item 6); the Bolt specification (handshake, PackStream, PULL `n`/`has_more`, FAILURE and
RESET); openCypher. Inherited findings named where they already decide a row.

Readers: **PY** `engine.execute_cypher` (SQL path, `native_cypher=False`, unless the row says native); **BOLT** the
real `neo4j` Python driver against the product's own TCP listener (`start_tcp_bolt_server` with a real engine);
**API** `POST /api/cypher`; **TX** `POST /db/neo4j/tx/commit` (in-process FastAPI `TestClient`, as in `http_rows`).
Fixture: `ivg-cont-20261117-iris`, namespace USER, prefix `i55_<tag>_`. "Driver" for bug-cyp-125 means the IRIS
DB-API driver `intersystems-irispython` (5.3.2 in the fixture's venv; 5.4.1 in an isolated venv outside the repo),
not the neo4j driver.

## W1 Result typing at the final reader (RT)

| ID | Changing input | Prediction (both neighbors) | Source |
|---|---|---|---|
| RT1 | stored node property `1` (int, API writer) vs `'1'` (string) | int `1` on PY, BOLT, API, TX; the string stays `'1'` on all four | query.values; USER_GUIDE §3 |
| RT2 | stored `2.5` vs whole float `1.0` | float `2.5`; `1.0` stays a float on all four (JSON `1.0`) | query.values (D mark → float) |
| RT3 | stored boolean `True` vs string `'true'` | both read back as boolean `True` on all four (documented known issue: a string spelling a boolean reads as one) | KNOWN_ISSUES "A stored string that spells a boolean…" |
| RT4 | stored list `[1, 2]` vs map `{'k': 1}` | list and dict on all four (not JSON text) | USER_GUIDE "A list, a map or a path … through `execute_cypher`, REST and Bolt alike" |
| RT5 | missing property vs stored empty string `''` | `None`/`null` vs `''` on all four | KNOWN_ISSUES (`"\u0000"` reads as `''`) |
| RT6 | literal `[]` vs `{}` vs nested `[[1,[2]],{a:[]}]` | equal values on all four | openCypher; USER_GUIDE |
| RT7 | stored `2**62` vs `2**64` (Python writer) | `2**62` int on all four; `2**64` is stored as text and reads as the string `'18446744073709551616'` | query.values ("larger integers … text") |
| RT8 | `RETURN n` vs `RETURN properties(n)` | PY/API: three columns `n_id`, `n_labels`, `n_props` vs one map; BOLT: one `Node` with the labels and properties (the server is "neo4j-driver compatible") vs the map; TX: Neo4j row of the property map vs the map | USER_GUIDE §3; README; Neo4j HTTP API |
| RT9 | the same node in two rows vs two different nodes (BOLT) | equal `element_id`/`id` for the same node; different for two nodes | Bolt spec (identity) |
| RT10 | `RETURN r` (API-written edge) vs `RETURN type(r)` | BOLT: one `Relationship` whose type is the edge type and whose start/end ids equal the endpoint `Node` ids in the same row; `type(r)` the string | Bolt spec |
| RT11 | `RETURN p` (shortestPath) vs `RETURN length(p)` | PY: `{'nodes': [...], 'rels': [...]}`; BOLT and API the same dict (not a Bolt `Path`); length an int | USER_GUIDE "Shortest path" ("REST and Bolt alike") |

## W2 Parameters (PA)

| ID | Changing input | Prediction | Source |
|---|---|---|---|
| PA1 | `RETURN $x` with int, float, string, bool, null, list, map | each value and type returned unchanged on PY and BOLT | openCypher; KNOWN_ISSUES ("a parameter … answers the string") |
| PA2 | `WHERE n.v = $x`, `$x = 1` vs `'1'` | matches the stored int with `1`, not with `'1'` | query.values.equality |
| PA3 | `UNWIND $xs AS a RETURN a`, `$xs = [1, 2]`, irispython **5.3.2** vs **5.4.1** | fails on **both** drivers (IRIS does not treat a `?` inside `JSON_TABLE`'s source as a marker: driver-drift item 6, a server fact); neighbor `WITH $xs AS l UNWIND l AS a RETURN a` answers `[1], [2]` on both. Competing reading (README/TCK: 3896/3896 on 5.4.0/5.4.1): works on 5.4.1 | bug-cyp-125; driver-drift §6; README |
| PA4 | `RETURN $l[$s..$e]` and `$l[$s]` on 5.3.2 vs 5.4.1 | same split as PA3: fails on both; `WITH $l AS l RETURN l[$s..$e]` answers `[2, 3]` on both | review 47-49 m2 |
| PA5 | `n.v IN $xs` vs `n.v IN [1, 2]` | same rows | openCypher |
| PA6 | `$m.k` and `RETURN $m` vs a missing parameter | `1` and the dict; a missing parameter is refused (Neo4j `ParameterMissing`), not read as null | openCypher; Neo4j |
| PA7 | one parameter used twice (`WHERE n.v = $x OR n.w = $x`) vs two parameters | same rows | openCypher |
| PA8 | `SKIP $s LIMIT $l` with ints over BOLT vs PY | same rows on both | query.paging |

## W3 Bolt protocol (BP)

| ID | Changing input | Prediction | Source |
|---|---|---|---|
| BP1 | raw handshake offering 4.4 vs only an unsupported version (3.0, 9.9) | agreed version `00 00 04 04`; for the unsupported offer four zero bytes and the connection closes | Bolt handshake spec; access.bolt.framing ("supported Bolt 4.4") |
| BP2 | neo4j driver 6.4.1 (offers 5.x and 4.4) vs a raw 5.0-only offer | the driver connects and runs `RETURN 1`; the 5.0-only offer is refused (zeros) if only 4.4 is supported | ADMIN_API (HELLO for Bolt 4/5.0, LOGON 5.1+) — competing reading: 5.x accepted |
| BP3 | `IVG_API_KEY` set: right vs wrong credentials | right key runs; wrong key raises the driver's `AuthError` (`Neo.ClientError.Security.Unauthorized`) and runs nothing; key unset: any credentials run | ADMIN_API "Authentication" |
| BP4 | a failing RUN (syntax error) then RESET and a new RUN in the same session vs a clean session | the driver raises `CypherSyntaxError` (`Neo.ClientError.Statement.SyntaxError`); the next query in the same session answers normally | Bolt FAILURE/RESET; access.bolt.results |
| BP5 | 5 rows with `fetch_size=2` vs `fetch_size=-1` | intended (owner, spec): 5 records both ways. As-built prediction from inherited F-1602: 2 records with `fetch_size=2` (PULL drops the unread suffix and `has_more` is absent), 5 with -1 | access.bolt.results; bolt_stream F-1602 |
| BP6 | integers 127, 128, -16, -17, 32767, 32768, 2**31, ±(2**63−1), −2**63 | each comes back equal over BOLT; the server packs each in the smallest PackStream width (tiny, INT_8, INT_16, INT_32, INT_64) | PackStream spec |
| BP7 | unicode `'héllo ✓ 𝄞'` (15 vs 16+ UTF-8 bytes) and an empty string | equal strings over BOLT; length marker by UTF-8 byte count | PackStream spec |
| BP8 | float `2.5`, `-0.0`, `1e308` vs int `2` | floats stay floats, the int stays an int over BOLT | PackStream spec |

## W4 Errors and limits (ER)

| ID | Changing input | Prediction | Source |
|---|---|---|---|
| ER1 | Cypher syntax error vs a valid query | PY raises `CypherParseError`; BOLT `CypherSyntaxError`; TX `errors[0].code` = `Neo.ClientError.Statement.SyntaxError` | USER_GUIDE; Neo4j codes |
| ER2 | a query IRIS refuses at run time (bug-cyp-140 label-count UNION, SQLCODE -1) vs its passing neighbor | PY raises (`RuntimeError` or `iris.dbapi` error, USER_GUIDE); BOLT a FAILURE (driver error, not zero rows); TX an `errors` entry | USER_GUIDE "catch (RuntimeError, iris.dbapi.Error)" |
| ER3 | `UNWIND $rows AS r CREATE (:L {i: r})` with 3 vs 5,000 rows | every row written exactly once in both (no duplicate from a retry) | access.bolt working assumption (no re-run of a write of unknown outcome) |
| ER4 | `UNWIND range(1, 1200) AS i RETURN i` vs the same with `LIMIT 5` | BOLT 1,200 records and PY 1,200 rows; API 1,000 (documented `limitRows`), TX 1,000 (bug-plt-108); `LIMIT 5` gives 5 everywhere | access.surfaces; bug-plt-108 |

## W5 Native/SQL at the final reader (NR)

| ID | Changing input | Prediction | Source |
|---|---|---|---|
| NR1 | `MATCH (n:L) RETURN n.v` over int, float, string, bool, list values; engine native on vs off | equal values and types on both paths | query.native.equal-answers |
| NR2 | BOLT (the server's engine: native default) vs PY native off, the same reads | equal values and types | access.surfaces |

## Result

Filled in after the observation (below this line only).
