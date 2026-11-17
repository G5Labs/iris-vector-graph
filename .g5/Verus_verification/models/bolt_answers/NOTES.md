# One answer through the pipeline to the Neo4j driver (bolt_answers)

Product `3eaa79cf`, unchanged. Iteration 55 (W60). Predictions frozen before the deciding source was read:
[pipeline-PAIRS.md](../../../uplift/consolidated/iteration-55/pipeline-PAIRS.md) (commit `ec9a8ac5`); post-read rows
T1-T7 were written before their probe ran (`6abf7508`). Owners:
[access.bolt.versions](../../../ontology/concepts/access.g5.md#access.bolt.versions),
[access.bolt.errors](../../../ontology/concepts/access.g5.md#access.bolt.errors),
[access.bolt.graph_values](../../../ontology/concepts/access.g5.md#access.bolt.graph_values),
[query.parameters](../../../ontology/features/cypher.g5.md#query.parameters),
[query.values.equality](../../../ontology/features/cypher.g5.md#query.values.equality).
An as-built Verus transcription with native agreement; **not** executable-body verification. Bundled vstd only; no
`assume`, `admit` or `external_body`.

## What each section derives, from which input

| Section | Deciding input | Derived decision | Reader |
|---|---|---|---|
| A versions | the four raw u32 proposals | `negotiate`: first proposal met (5.x at `min(minor, 4)` when `minor - range <= 4`; 4.x with minor ≥ 4 as 4.4), else 0 | the four bytes after the handshake |
| B integers | the integer value | `int_marker` (tiny, INT_8/16/32/64, none); `pull_value`: no marker → the session breaks | driver record / defunct connection |
| C codes | the failure's cause | `bolt_code`: AccessMode, Unauthorized, else SyntaxError | FAILURE `code` |
| D1 node ids | node id and its process hash `h` | `bolt_id = h mod 2^31`; with provider P-DRIVER-ID, `client_view2` | the driver's Node per record |
| D2 endpoints | the RETURN's column layout | `reported`: start = node triplet before, end = node triplet after, else 0 | Relationship start/end ids |
| D3 properties | kind and `len(str(value))` | `bolt_node_prop`: > 200 → 200 characters + `...`, kind string | Node property |
| E retry | error-text features; statement flags | `is_long`; `runs` ∈ {1, 2}, 1 for any transactional statement | how often a statement runs |
| F parameter lists | the IRIS driver; the order of bound values | `unwind_param`, `slice_answer` (JSON_TABLE reads the third bound value) | `execute_cypher` rows / error |
| G node equality | the stored value's kind/text; the operand's kind | `matches`: integer operands typed, string operands by text | `WHERE` rows |

## Value domains and exclusions

- A: any four `nat` proposals (bytes interpreted as in the source); manifest negotiation (Bolt 5.7+) is outside, observed
  only as "skipped".
- B: all mathematical integers; floats, strings, lists and maps are outside (observed equal on four readers, RT/BP rows).
- C: six causes; the transport-level failures (socket errors, encoder failures other than B) are outside.
- D1: two nodes per result in the theorems; `h` is abstract (Python's salted string hash), so the claim is conditional on a
  collision existing, which the binding exhibits. D2: one relationship column with node triplets around it; paths and
  variable-length relationships are outside. D3: `rendered` is `len(str(value))`; content beyond "whole or not" is
  abstracted (a 203-character string cut to 203 characters is still "not whole").
- E: the six features `_is_long_list_temp_error` reads; the retry's SQL rewrite and its second error text are outside.
- F: lists of integers; drivers 5.3.2 and 5.4.1 only (provider P-DRV-JT); JSON_TABLE over a scalar's text yields no row
  (provider P-JT-SCALAR, observed).
- G: stored node values that are numbers or strings, written by the API; booleans, relationship properties (owned by
  `typed_equality`) and Cypher-written values are outside.

## Theorems (27 verified units)

General: `theorem_answer_is_zero_or_supported`, `theorem_v5_rule`, `theorem_marker_is_smallest`,
`theorem_overflow_breaks_connection`, `theorem_int64_values_arrive`, `theorem_gate_codes_follow_rule`,
`theorem_hash_collision_loses_first_node`, `theorem_distinct_ids_keep_both`, `theorem_one_hop_right_iff_source_first`,
`theorem_long_property_truncated`, `theorem_short_property_kept`, `theorem_write_runs_once`,
`theorem_retry_only_for_long_list`, `theorem_param_slice_answers_empty`, `theorem_unwind_param_depends_on_driver`,
`theorem_string_operand_matches_number`, `theorem_int_operands_and_string_values_follow_rule`. Probe instances:
`theorem_probe_offers`, `theorem_probe_widths`, `theorem_runtime_failure_reported_as_syntax`,
`theorem_endpoints_follow_columns`, `theorem_rel_alone_or_last`, `theorem_other_400_not_retried`.

Departures (each with a passing neighbor in the same section): `theorem_overflow_breaks_connection` (bug-plt-125),
`theorem_runtime_failure_reported_as_syntax` (bug-plt-124), `theorem_hash_collision_loses_first_node` (bug-plt-122),
`theorem_endpoints_follow_columns` (bug-plt-123), `theorem_long_property_truncated` (bug-plt-121),
`theorem_param_slice_answers_empty` (bug-cyp-144), `theorem_unwind_param_depends_on_driver` (bug-cyp-125),
`theorem_string_operand_matches_number` (bug-cyp-145). Held: version negotiation, integer widths, the gate codes, the
retry never re-running a write (two guards: the transactional route and the retry's own `is_transactional` check).

## Controls (19, all EXPECTED_FAIL)

`range-unchecked`, `no-bolt5`, `tiny-to-255`, `i16-not-smallest`, `nofit-is-failure` (repair), `code-by-cause` (repair),
`gates-folded`, `id-from-node-id` (repair), `driver-no-id-cache` (provider flip), `swap-columns`, `no-prev-node`,
`no-truncation` (repair), `truncate-at-200`, `retry-any-400`, `retry-writes` (both guards removed; one guard alone
leaves `theorem_write_runs_once` verified, which is the double protection the source has), `slice-markers-in-order`
(repair), `driver-532-binds` (provider flip), `string-compare-typed` (repair), `int-param-raw` (a numeric parameter not resolved statically). The
first run of `no-prev-node` was ERROR (its replacement made `prev_node` non-recursive, so `reveal_with_fuel` failed to
build); that receipt is kept and the control was corrected to keep the recursion.

## Binding

[binding.py](binding.py): **AGREES, 400 cases**, all 19 port mutations detected, one tampered observation detected.
Unit part on the pin tree: `negotiate_version` over 240 single offers and four sequences, `PackStream._pack_int` at 26
boundary values (including past int64), `_node_int_id`, `_recompose_graph_row` on four layouts (decoding the emitted
Relationship struct), `_parse_props_field` on eight values, `_is_long_list_temp_error` on the 64 feature combinations.
Fixture part: the product's TCP listener with a real engine on its own connection, read by the neo4j Python driver 6.4.1
and an independent raw socket client (handshakes, integers, the overflow, FAILURE codes including `IVG_READ_ONLY` and
`IVG_API_KEY`, a found hash collision and a distinct pair, four relationship layouts, three long properties); node
filters on the SQL path; the parameter-list shapes under intersystems-irispython 5.3.2 (the fixture venv) and 5.4.1 (an
isolated venv outside the repository, `I55_VENV541`). Rows marked `E-inspected` transcribe the retry guards and run no
product code.

```sh
(cd $RUN_DIR/pin && IVG_REPO=$OLDPWD I55_VENV541=$RUN_DIR/i55/venv541/bin/python \
  $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/bolt_answers/binding.py)   # AGREES 400
```

## Exact source roles

| Pin declaration | Role |
|---|---|
| `bolt_server.py::negotiate_version` 331-347 | decision (A) |
| `bolt_server.py::BoltSession._do_handshake` 427-437, `TcpBoltSession._do_handshake` 962-972 | effect/reader of A (4 bytes, close on 0) |
| `bolt_server.py::PackStream._pack_int` 95-105, `PackStream.pack` 69-93 | decision/encoder (B) |
| `bolt_server.py::BoltSession._handle_pull` 624-660 | reader: records sent outside RUN's try (B), F-1602 suffix loss (inherited bolt_stream) |
| `bolt_server.py::BoltSession._handle_run` 567-622 | decision (C: codes; read-only gate; `result.error` re-raised) |
| `bolt_server.py::BoltSession._refuse_unauthorized` 523-528, `_authenticate` 530-545, `_handle_hello` 547-560, `_handle_logon` 562-565 | decision (C: Unauthorized gate) |
| `bolt_server.py::_node_int_id` 351-352, `pack_node` 355-357 | decision (D1) |
| `bolt_server.py::BoltSession._recompose_graph_row` 713-801, `_detect_graph_columns` 669-689 | decision (D2, node triplets) |
| `bolt_server.py::BoltSession._parse_props_field` 876-905, `_parse_json_field` 865-874 | decision (D3) |
| `bolt_server.py::BoltSession._coerce_scalar` 704-711 | scalar reader (Decimal to float; others unchanged) |
| `_engine/query.py::_is_long_list_temp_error` 1671-1678 | decision (E) |
| `_engine/query.py::QueryMixin._execute_parsed_sql` 2286-2311, `_unwind_by_index_retry` 2251-2284 | decision (E: route and guards; inspected transcription) |
| `_engine/query.py::QueryMixin.execute_cypher` 1746-1943, `_raise_if_error` 1681-1688 | reader (the result's `error`, no raise by default) |
| `cypher/translator.py::_expr_slice` 23679-23800 (bound values appended at 23778-23789) | decision (F: the order of bound values) |
| `cypher/translator.py::_stored_number_comparison` 16331-16358, `_static_number` | decision (G: a number operand, literal or parameter, gets the typed guard; a string operand falls through) |
| `cypher/translator.py::_number_eq_sql` 16287, `_node_number_eq_sql` 16264-16285 | effect (G: the typed guard) |
| intersystems-irispython 5.3.2 / 5.4.1 | provider P-DRV-JT (observed) |
| neo4j Python driver 6.4.1 | provider P-DRIVER-ID (observed) |

## Premises and limits

- P-DRV-JT, P-JT-SCALAR, P-IRIS-EQ (string side only) and P-DRIVER-ID are observed provider facts on this fixture (IRIS Community 2026.1)
  and these driver versions; other IRIS builds and drivers are unchecked.
- The long-list error itself does not occur on 2026.1 (T7); the retry is bound by unit cases and inspection only.
- WebSocket Bolt (bolt_stream's scope) and the Bolt 5 structure layouts for other drivers are not checked here.
- `_extract_sql_row_limit`/`_apply_sql_row_limit` (the var-length route's LIMIT): the probed var-length shapes did not
  reach that route (T6), so no claim is made.
