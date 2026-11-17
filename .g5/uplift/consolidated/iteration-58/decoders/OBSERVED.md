# Iteration 58 W2: result decoders — outcomes of the frozen predictions D1-D9

Predictions: [w62-PAIRS.md](../w62-PAIRS.md) (frozen at `2429a0a3`, unedited), rows D1-D9 (this worker's scope).
Model: [result_decoders](../../../../Verus_verification/models/result_decoders/NOTES.md). Receipts (under
`.g5/Verus_verification/results/result_decoders/`): prove `20261117T082127Z-prove` PASS 12; 17 controls
`20261117T082129Z`..`20261117T082152Z` all EXPECTED_FAIL; binding `20261117T082201Z-binding/receipt.json` AGREES 480/480
cases (IRIS drivers 5.3.2 and 5.4.1, four readers each), 17/17 port mutations detected, tamper detected.

Fixture: `ivg-cont-20261117-iris` (127.0.0.1:36317, USER), product pin `3eaa79cf` (the pin tree equals the working
tree's `query.py`). Fresh prefixes `i58d_080853_` (probe, 5.3.2), `i58d_080939_` (probe, 5.4.1), the binding's own
`i58d_<tag>_`. No `sync()`. Readers: **PY** `execute_cypher` on an engine with `native_cypher=False` (SQL path); **PYN**
the native-default engine; **BOLT** neo4j driver 6.4.1 against `start_tcp_bolt_server` with a real engine;
**API** `/api/cypher` and **TX** `/db/neo4j/tx/commit` (FastAPI TestClient, in process). Each observation was made
under both IRIS Python drivers: intersystems-irispython **5.3.2** (`$RUN_DIR/venv`) and **5.4.1** (`$RUN_DIR/i55/venv541`);
where the two differ it is said.

Raw files (this directory): [decoders_probe.py](decoders_probe.py) ->
[decoders-observed-5.3.2-20261117T080853Z.json](decoders-observed-5.3.2-20261117T080853Z.json),
[decoders-observed-5.4.1-20261117T080939Z.json](decoders-observed-5.4.1-20261117T080939Z.json) (each holds the
translated SQL and the `SQLQuery` column lists per query under `meta`); [d8_probe.py](d8_probe.py) ->
`d8-observed-venv.json` (5.3.2), `d8-observed-venv541.json` (5.4.1); [d9_probe.py](d9_probe.py) ->
`d9-observed-5.3.2.json`; [d9_route_probe.py](d9_route_probe.py) -> `d9-route-observed-5.3.2.txt`.

Data (probe): `i` {k:'i', v:3, s:'si', e:'', el:[], em:{}}, `f` {k:'f', v:2.5, s:'sf'}, `s` {k:'s', s:'txt'},
`b` {k:'b', s:true}, `w` {v:3.0}; edges i->f, f->s, s->b, i->s (type `I58DK080853`). All written by `create_node` /
`create_edge`; `rdf_props.val` holds 3 and 2.5 as IRIS numbers and `true` as the text `'true'` (read back raw).

Summary: 9 workflows; **6 held (D3, D4, D5, D6, D7, D9), 1 held with scope note (D8), 1 partial (D2), 1 missed (D1)**.
Findings: [bug-cyp-155](findings.md#bug-cyp-155) (Medium), [bug-cyp-156](findings.md#bug-cyp-156) (Medium),
[bug-plt-135](findings.md#bug-plt-135) (Low).

| ID | Verdict | Observation (all four readers agree unless a reader is named) | Keys |
|---|---|---|---|
| D1 | **missed** | A `WITH n, CASE WHEN n.k IN i/f THEN n.v ELSE n.s END AS x RETURN x`: **5.3.2** int `3`, float `2.5`, string `'txt'` kept, but the stored boolean answers the **string `'true'`** (PY `str`, BOLT `str`, API/TX JSON `"true"`). **5.4.1**: also `3` -> `'3'`, `2.5` -> `'2.5'` (strings) on all readers, PY and PYN alike. Same for the CASE directly in RETURN (`D1_ret_case`). A CASE over a stored list answers its JSON text `'[1, 2]'` (both drivers; [q](#d1-supplement)). Neighbor B `WITH n, coalesce(n.v, n.s) AS x RETURN x`: **`'3'`, `'2.5'`, `'true'` strings under both drivers** on all readers. Valid neighbor: `RETURN coalesce(n.v, n.s)` (no WITH) answers `3`, `2.5`, `true`, `'txt'` typed under both drivers (R259). Translator: the CASE/WITH-coalesce column is in no decoder list (meta: only `id` typed); the WITH stage CASTs coalesce's first argument to VARCHAR. | `D1_case`, `D1_case_noid`, `D1_ret_case`, `D1_coalesce`; binding `*_RetCase_*`, `*_WithCase_*`, `*_WithCoalesce_*`, `*_RetCoalesce_*` |
| D2 | partial | A `MATCH (a) OPTIONAL MATCH (a)-[:NONE]->(b) RETURN a.node_id, b, b.x`: `b.x` null on all four (both drivers). `b`: **BOLT `None`** (held); PY, API and TX answer the documented node triplet `b_id, b_labels, b_props` with `b_id` null but **`b_labels` `'[]'` and `b_props` `'[]'`** (strings), not nulls. Neighbor B: `WITH a, b` the same; `collect(b)` `[]` on all four (held). | `D2_opt`, `D2_with`, `D2_collect`; binding `*_Opt_labels` |
| D3 | held | `''` reads `''` (not null); stored `[]` reads `[]`, `{}` reads `{}`, directly and through `WITH n.e AS e`, on all readers, both drivers. | `D3_empty`, `D3_empty_with`; binding `*_empty`, `*_list0`, `*_map0` |
| D4 | held | `RETURN {a: n.v, b: 'x'}` -> `{a: 3 (int), b: 'x'}`; `{a: [1, n.v], t: true, s: n.s}` -> list of ints, boolean `true`, string. Column in `json_value_columns`. | `D4_map`, `D4_map_nested` |
| D5 | held | Stored int 3: `n.v + 1` = 4 (int), `n.v * 1.5` = 4.5, `n.v / 2` = 1 (int). Stored float 3.0: 4.0, 4.5, 1.5 (floats). PYN and the shadow run agree. Columns typed (`CY_TYPED`) with `a`, `c` also in `mixed_expr_columns`. | `D5_int`, `D5_float` |
| D6 | held | `n.v > 2.7` -> `true` (3), `false` (2.5), **null** for a node whose `v` is missing (`s`), on all readers. Binding: also null over `''`, `'txt'` and an absent property. | `D6_bool`; binding `*_Gt_*` |
| D7 | held | `RETURN a.node_id AS id, b.x AS bx` with no match: zero rows, columns `["id","bx"]` on all four (TX `columns` present, `data` `[]`). `count(*)` with no match: one row `0`. | `D7_empty`, `D7_count` |
| D8 | held (scope) | Native-accepted reads (`MATCH (a:L)-[:K]->(b) RETURN a.node_id, b.node_id`; `MATCH (n:L) RETURN n.node_id, n.v[, n.s]`): `_try_native` answered (counted 1) and the rows equal the SQL path's, with types, under compile modes `off`, `sync` and `job` (`Graph.KG.Cypher.Gen.Mode`); with `IVG_CYPHER_SHADOW=1` (mode sync) native answered and `_shadow_compare` ran once without `NativeMismatch`; the same reads through BOLT with `IVG_CYPHER_SHADOW=1` equal. Both drivers. Scope: the ORDER BY forms of these reads are not native-planned (`_try_native` None, SQL path); the second run in one engine went to the SQL route (`native_route_ms` routing), so a compiled class's second run was not isolated. | `d8-observed-*.json` `hop_plain`, `nohop_plain`, `nohop_typed` |
| D9 | held | `MATCH (a {node_id})-[:K*1..3]->(b) RETURN b.node_id LIMIT 2` -> 2 rows (of 5 paths); `ORDER BY id LIMIT 2` -> `b, b` (the two smallest; two paths end at b); `ORDER BY id DESC LIMIT 2` -> `s, s`; `SKIP 1 LIMIT 2` -> `b, f`; also with a relationship variable, a path variable, `length(p)` and OPTIONAL; all four readers agree for the plain form. Route: these translate to `CY_VLP_PATHS` + `JSON_TABLE` + `FETCH FIRST 2 ROWS ONLY` in SQL (`var_length_paths` empty, also with `engine=`); `_route_var_length` is reached only by the `shortestPath` shape tried (1 row, LIMIT not binding). | `D9_*`; `d9-observed-5.3.2.json`; `d9-route-observed-5.3.2.txt` |

<a id="d1-supplement"></a>
D1 supplement (both drivers, PY, run inline with the probe's data): `MATCH (n:L) RETURN n.node_id AS id, coalesce(n.v,
n.s) AS x` -> `true` (bool), `2.5`, `3`, `'txt'`; `typed_value_columns` and `prop_text_expr_columns` hold `x`.
`RETURN CASE WHEN n.k = 'l' THEN n.v ELSE n.s END AS x, n.v AS y` over `v: [1, 2]` -> `x` `'[1, 2]'` (str), `y` `[1, 2]`
(list). `WITH CASE ... n.s ... END AS x RETURN x` over `s: {a: 1}` -> `'{"a": 1}'` (str). The binding repeats these
kinds (`list0`, `map0`, `btrue`, `bfalse`) on all four readers and both drivers.

## Decoder order and column-kind decision (as read)

`_finish_sql_result` (`query.py:332-349`): `_drop_internal_columns`, `_decode_typed_value_columns` (1137),
`_decode_bool_text_columns` (1157), `_decode_rel_prop_text_columns` (1200), `_decode_numeric_expr_columns` (1307),
`_decode_map_text_columns` (1602), `_decode_mixed_expr_columns` (1397), `_decode_empty_json_strings` (475),
`_strip_node_graphs`, `_decode_json_value_columns` (497), `_decode_graph_json_values` (547). The variable-length BFS
routes run only the last two (`_execute_parsed_sql` 2291-2297). `_optional_null_columns` (1638) names the columns of
the null row an OPTIONAL var-length match with no target answers (`query.py:3228`, `3336`); `_fill_empty_columns`
(1651) gives an empty result the RETURN's names when a route answered `columns=[]` (`query.py:1942`).

The column kind is decided by the translator's RETURN item emission (`translator.py:30649-30715`): `_reads_node_value`
(7644-7678) -> `CY_TYPED(sql)` and `typed_value_columns`; `_is_bool_valued` -> `bool_expr_columns`; container kinds ->
`json_value_columns`; anything else is `sql AS alias` and reaches the reader as the IRIS driver hands it. CASE has no
arm in `_reads_node_value`; `coalesce` has one (`_is_typed_coalesce`, 7620-7641) only as a RETURN item, while a WITH
stage keeps `_scalar_coalesce`'s CAST to VARCHAR (24454-24470).

## Residual items

- D8: a compiled plan's second run isolated from the route chooser (first missing step: set `native_route_ms = 0` on
  the engine, run a hop shape twice under mode `sync`, and count `_run_native_plan` calls with the generated class
  recorded in `^IVG.CypherCompiled`).
- D9: a LIMIT through `_route_var_length` itself (first missing step: find a non-shortest shape that the translator
  hands to the BFS routes, e.g. one `_trp_vlp_native` declines with `_vlp_bfs_answers` true; none of the five shapes
  tried did).
- `_decode_numeric_expr_columns`, `_decode_map_text_columns`, `_decode_mixed_expr_columns` are observed only as
  end-to-end answers (D4, D5), not modeled (first missing step: a model section for `int_expr_columns`/
  `float_expr_columns` and `_mixed_scalar_value` over text spellings).
- Relationship-property columns and Cypher-written node values are outside this run.
