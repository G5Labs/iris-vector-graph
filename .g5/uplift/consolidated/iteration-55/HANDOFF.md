# Iteration 55: one answer through the query pipeline to the Neo4j driver (W60)

Before image `adea8019` (seal 54 `628f65f9` plus the master's inventory commit). Product `3eaa79cf` unchanged: nothing
outside `.g5/` changed (`git diff adea8019 -- . ':!.g5'` empty; no untracked file outside `.g5/`;
`check_consolidated.py` confinement PASS).
Commits:
- `ec9a8ac5`: the freeze, committing only [pipeline-PAIRS.md](pipeline-PAIRS.md) before any deciding source in
  `_engine/query.py` or `bolt_server.py` was read;
- `667bc9d4`: probes and observations (both IRIS drivers), before the source was read;
- `6abf7508`: post-read predictions T1-T7, before their probe ran;
- `8f89950e`: model `bolt_answers` and probe 2; `148c1f78`: its binding; `41abad69`: owners, registers, recount;
- the seal.

Guidance read at the start: `$G5_HARNESS/AGENTS.md`; `Verus/{uplift, uplift-iteration, uplift-scoring,
setup_foundation, verification}.md`; `uplift-intent-recovery.md`, `ontology-format.md`, `setup_foundation.md` (open
questions); the runbook's continuation section. `open_questions.md` changed only by one appended entry
(`query.parameters.drivers`); no existing card, anchor or saved answer was touched. Quarantine respected: no
iteration-13 Cypher `MERGE` material and no evaluator-private ledger was opened. Native evidence comes only from
`ivg-cont-20261117-iris`, namespace USER, fresh prefixes `i55_`, `i55b_`, `i55k_`; a Bolt listener was started
in-process on a free `127.0.0.1` port for each run and closed after it. No other container was touched. No sub-agents.

**The "driver" of bug-cyp-125 is the IRIS DB-API driver** (`intersystems-irispython`), not the neo4j driver: the
fixture venv has 5.3.2 (the version the product's `uv.lock` pins); 5.4.1 was downloaded from PyPI into an isolated
venv outside the repository (`$RUN_DIR/i55/venv541`: the fixture venv's site-packages behind a 5.4.1 `iris` package).
The neo4j driver used for Bolt is 6.4.1 (the fixture venv's); it negotiated Bolt 5.4.

## Why this batch

`_engine/query.py` (114 of 124 members unbound) and `bolt_server.py` (45 of 53) are the final readers between the
translator and every client. Five workflows, breadth first: result typing on four readers (Python, Bolt, `/api/cypher`,
`/db/neo4j/tx/commit`); parameters on two IRIS drivers; the Bolt protocol (versions, auth, RESET, PULL n, PackStream);
errors and limits; native/SQL routing at the final reader.

## Predictions: 33 frozen rows; 24 held, 5 partial, 4 missed; 7 post-read rows

Details: [pipeline-PAIRS.md](pipeline-PAIRS.md#result). Held: every value type on every reader (RT1-RT7), node
identity for distinct ids, paths, scalar parameters, IN/SKIP/LIMIT parameters, handshake refusals, auth, RESET after a
failure, PackStream widths, unicode, floats, the 1,000-row HTTP cap and its absence on Bolt, native/SQL agreement.
Missed: PA2 (a string equals a number), PA3 (5.4.1 binds the list marker; the frozen "fails on both" from
driver-drift item 6 was wrong, the recorded competing reading held), PA4 (5.4.1 slices to `[]`), BP2 (5.0-5.4 are
agreed). Partial: RT8 (TX node shape), PA6 (missing parameter as "Undefined variable"), BP5 (F-1602 as built), ER2 (the
code; and PY returns `error` rather than raising, which its docstring documents: a prediction error), ER3 (5,000-row
write not run). Post-read: T1, T2, T3, T5, T7 held; T4 partial; T6 not reached (the var-length route did not run).

## Findings

New (matched by trigger and observable consequence against the register and KNOWN_ISSUES; none duplicates):

| ID | Severity | Trigger → observable | Found by / reproduced by |
|---|---|---|---|
| [bug-plt-121](../../../Verus_verification/bugs_issues.md#bug-plt-121) | Medium | `RETURN n` over Bolt, a property > 200 characters → cut to 200 + `...`; a long list becomes that text | post-read T1 / probe 2, binding `D3_*` |
| [bug-plt-122](../../../Verus_verification/bugs_issues.md#bug-plt-122) | Medium | two node ids whose `hash() & 0x7FFFFFFF` collide → the driver shows the second node in both rows | post-read T3 / probe 2 (found pair), binding `D1_*` |
| [bug-plt-123](../../../Verus_verification/bugs_issues.md#bug-plt-123) | Medium | `RETURN b, r, a` / `(b)<-[r]-(a)` over stored `a→b` → start b, end a; `RETURN r` → no endpoints | post-read T2 / probe 2, binding `D2_*` |
| [bug-cyp-144](../../../Verus_verification/bugs_issues.md#bug-cyp-144) | Medium | `RETURN $l[$s..$e]` on IRIS driver 5.4.1 → `[]` (guard values bound out of order); 5.3.2 fails | PA4 missed / both drivers, binding `F_slice_*` |
| [bug-cyp-145](../../../Verus_verification/bugs_issues.md#bug-cyp-145) | Medium | `n.v = '1'` or `n.v = $x` (`'1'`) over a stored integer 1 → matches | PA2 missed / probe, probe 2, binding `G_*` |
| [bug-plt-124](../../../Verus_verification/bugs_issues.md#bug-plt-124) | Low | an IRIS SQL error, a driver parameter error or an undefined parameter on Bolt → `Neo.ClientError.Statement.SyntaxError` | ER2 / probe, binding `C_*` |
| [bug-plt-125](../../../Verus_verification/bugs_issues.md#bug-plt-125) | Low | `RETURN 9223372036854775807 + 1` → engine 9223372036854775810; Bolt session ends (defunct connection) | post-read T5 / probe 2, binding `B_wire_overflow` |
| [bug-plt-126](../../../Verus_verification/bugs_issues.md#bug-plt-126) | Low | `RETURN n` on `/db/neo4j/tx/commit` → three text columns, not a node | RT8 partial / probe |

All E2E reproduced at the unchanged pin, each with a passing neighbor. Inherited, strengthened:
- **bug-cyp-125 settled**: driver-dependent. 5.4.1 runs `UNWIND $list` (also after `MATCH`) and `$l[$s]`; 5.3.2 fails
  them on every reader. The lock file pins 5.3.2, so severity Low → Medium; question opened
  ([query.parameters.drivers](../../../Verus_verification/open_questions.md#query.parameters.drivers)).
  `UNWIND $rows ... CREATE` writes on both drivers. The review-47-49 m2 slice reading is now observed as bug-cyp-144.
- **bug-cyp-111**: a new list source (a parameter list with a parameter index answers `'2'` on 5.4.1); same decision.
- **F-1602**: the PULL suffix loss reproduced with a real client (neo4j 6.4.1, `fetch_size=2`: 2 of 5 records, no error).
- **bug-plt-108**: reconfirmed; Bolt answers all 1,200 rows, so the cap is HTTP-only.
- bug-cyp-102 shares bug-cyp-145's IRIS fact (a stored number's text equals a string) through its boolean arm; different trigger.

Questions: opened `query.parameters.drivers`. Simplifications: none proposed, tested or retired.

## Owners

New blocks: [access.bolt.versions](../../../ontology/concepts/access.g5.md#access.bolt.versions),
[access.bolt.errors](../../../ontology/concepts/access.g5.md#access.bolt.errors),
[access.bolt.graph_values](../../../ontology/concepts/access.g5.md#access.bolt.graph_values),
[query.parameters](../../../ontology/features/cypher.g5.md#query.parameters) (uncertain, linked to the question).
Extended: `query.values.equality` (a bullet and findings for bug-cyp-145), `access.bolt` (children),
`access.bolt.results` (F-1602 with a real client; bug-plt-125 back-link), `access.surfaces` (bug-plt-126 back-link).
Expected results come from the Bolt handshake/PackStream/status-code specifications, openCypher, README, USER_GUIDE,
ADMIN_API, KNOWN_ISSUES, `docs/dev/TCK.md` and `driver-drift.md`; none from a preferred repair. `check_ontology.py`: 402
blocks (398 before), 0 issues, 17 writing warnings (unchanged).

## Model

| Model | Verified | Controls | Binding |
|---|---|---|---|
| [`bolt_answers`](../../../Verus_verification/models/bolt_answers/NOTES.md) (new) | 27 ([prove](../../../Verus_verification/results/bolt_answers/20261117T063017Z-prove/receipt.json)) | 19/19 EXPECTED_FAIL (one earlier ERROR receipt kept: `no-prev-node` first built a non-recursive function) | AGREES 400 ([receipt](../../../Verus_verification/results/bolt_answers/20261117T063052Z-binding/receipt.json)); 19/19 mutations and the tamper detected; irispython 5.3.2 and 5.4.1 |

Each decision is derived from its input: the agreed version from the raw proposals; the PackStream marker from the
integer; the FAILURE code from the cause; the node id from its hash; relationship endpoints from the column layout;
property truncation from the rendered length; the retry from the error text's features and the statement's flags; the
slice answer from the order of bound values; node equality from the operand's kind. General theorems:
`theorem_answer_is_zero_or_supported`, `theorem_v5_rule`, `theorem_marker_is_smallest`,
`theorem_one_hop_right_iff_source_first`, `theorem_long_property_truncated`, `theorem_write_runs_once`,
`theorem_retry_only_for_long_list`, `theorem_param_slice_answers_empty`,
`theorem_int_operands_and_string_values_follow_rule` and the others in NOTES. Value domains, exclusions and the four
provider premises (P-DRV-JT, P-JT-SCALAR, P-IRIS-EQ string side, P-DRIVER-ID) are stated in the NOTES. Controls include
a repair for each departure, the removal of each decisive guard, and three provider/decision flips. Trust: no
`assume`, `admit` or `external_body`; vstd only.

## Recount ([member-delta.json](member-delta.json); `member_reach.py`, denominator 4,130)

Active bindings **619 → 640**; union reach (active plus baseline historical locators) **847 → 866**.
- Newly bound: 21. Newly reached: 19 (`negotiate_version`, `TcpBoltSession._do_handshake`,
  `BoltSession._do_handshake`, `start_tcp_bolt_server`, `PackStream._pack_int`, `_refuse_unauthorized`,
  `_authenticate`, `_handle_logon`, `_handle_hello`, `_node_int_id`, `_recompose_graph_row`, `_detect_graph_columns`,
  `_parse_props_field`, `_coerce_scalar` in `bolt_server.py`; `_raise_if_error`, `_is_long_list_temp_error`,
  `_unwind_by_index_retry` in `_engine/query.py`; `_stored_number_comparison`, `_static_number` in the translator).
  Existing locators gaining a binding: 2 (`PackStream.pack`, `TcpBoltSession.run`).
- Strengthened (a new claim beside inherited ones): `BoltSession._handle_run`, `_handle_pull`,
  `QueryMixin.execute_cypher`, `_execute_parsed_sql`, `_expr_slice`, `_node_number_eq_sql`.
- Lost: 0. Withdrawn: none; the `typed_equality` scope note "parameters were not checked" is now answered (numeric
  parameters take the typed guard; string literals and parameters do not).

Roles: `start_tcp_bolt_server` and `_do_handshake` (WebSocket) are an entry and a shared-decision reader (justified in
the crosswalk row); `_unwind_by_index_retry`'s guards and `_execute_parsed_sql`'s route are **inspected transcription**
only (the long-list error does not occur on IRIS 2026.1); `_is_long_list_temp_error` is bound by its 64 feature cases.

**Material predictions gained:** which Bolt versions are agreed; that a whole node's long property, two colliding node
ids and a reversed column order change what the driver sees while scalar reads do not; that every non-gate failure is
a SyntaxError and an int64 overflow drops the session; that list parameters depend on the IRIS driver and the slice
answers `[]` on 5.4.1; that a string operand equals a number it spells while numeric parameters are typed; that the
long-list retry never re-runs a write. **Withdrawn:** none.

## Correspondence

The [delta from 54](correspondence-delta-from-54.json) is STALE_ALL for proof and correspondence; the changed inputs are
the new model (`bolt_answers.rs`, `model.json`, `binding.py`), `decision-links.tsv` and `families.tsv` only; no product
file changed. The fresh [stamp](correspondence-inputs.json) checks as REUSABLE_INPUTS.

## Checks (final candidate)

| Check | Result |
|---|---|
| `check_ontology.py` | 402 blocks, 0 issues, 17 warnings (unchanged) |
| `check_findings.py` (`verification_root=.g5/Verus_verification`, `--previous adea8019`) | No problems found (after moving bug-cyp-125 into the Medium section and two metadata back-links) |
| `check_evidence.py` | FRESH |
| `check_consolidated.py` (G5_GUIDE set) | PASS (968 decision links resolve; statements 402 rows; correspondence stamp REUSABLE_INPUTS) |
| Product diff vs pin | none outside `.g5/`; no untracked file outside `.g5/` |

## Limitations

- **Review:** not independently reviewed; round 3 of the review budget remains.
- **Drivers:** IRIS drivers 5.3.2 and 5.4.1 only (5.4.0, the TCK's other driver, not tried); neo4j Python driver 6.4.1
  only. The Bolt 5 Node/Relationship structures keep the Bolt 4 field layout; the Python driver accepts them, other
  drivers (Java, JavaScript, Go) were not tried. P-DRIVER-ID (one Node object per id) is this driver's behavior.
- **Not checked:** WebSocket Bolt (bolt_stream's scope), the `/db/{db}/query/v2` route's node shape, shadow mode and
  compiled plans at the final reader (NR rows ran native on/off only), `_extract_sql_row_limit`/`_apply_sql_row_limit`
  (T6: the var-length route did not run), khop fast paths and approx count distinct, the decoders
  `_decode_*_columns` beyond what RT1-RT7 observed (bound as readers by earlier models, not re-modeled here).
- **Retry:** the long-list retry is unit- and inspection-bound only; the 5,000-row UNWIND write (ER3) was not run.
- **Repairs:** none run on the product; controls check the model's direction only.
- **Fixture state:** probe and binding nodes remain in USER under their fresh prefixes.

## Residual list (first missing step for each)

- **Shadow/compiled at the final reader:** run the NR reads with `IVG_CYPHER_SHADOW=1` and with compiled plans, then
  bind `_shadow_compare`/`_cypher_shadow`; first step: one read shape the native executor accepts, through Bolt.
- **Var-length LIMIT route:** find a shape that reaches `_route_var_length` (the BFS route) and check `LIMIT` with and
  without `ORDER BY` and an inner `WITH ... LIMIT`; first step: `translate_to_sql(...).var_length_paths` non-empty for
  a probed query.
- **Result decoders in Verus:** `_decode_json_value_columns`, `_decode_map_text_columns`, `_decode_mixed_expr_columns`,
  `_optional_null_columns`, `_fill_empty_columns` (query.py, unbound); first step: a mixed-kind `WITH` column and a
  null-row OPTIONAL column read on all four readers.
- **Bolt 5 structures for other drivers:** the Bolt 5 Node/Relationship field count; first step: a Java or JavaScript
  driver against the listener (needs a JVM or Node.js on the VM).
- **`query/v2` and `tx/commit` node shape (bug-plt-126 neighbor), and the HTTP error codes beyond SyntaxError.**
- **bug-cyp-125 decision:** the owner answer to `query.parameters.drivers`; with "require 5.4", only a packaging change.
- **Carried:** the iteration-54 residual list and the consolidated queue.

## Cost

About 30 minutes of builder wall clock (06:08 to about 06:40 UTC); no sub-agents. Tokens and currency are not
available to the builder.
