# Cypher built-in functions at run time

Product `3eaa79cf`, unchanged. Iteration 47 (continuation, W54). Predictions frozen from openCypher, the owner and the
known-issues guide before the source was read: [cypherfn-PAIRS.md](../../../uplift/consolidated/iteration-47/cypherfn-PAIRS.md).
Owners (new): [query.functions](../../../ontology/features/cypher.g5.md#query.functions) and its children.

## What the model decides

Each section transcribes the translator's choice for one function and the body that answers it, beside the openCypher
rule over the same inputs:

- **List index** (`translated_index`): a literal index is wrapped by the 4.6.0 R267 `CASE`; any other index goes to
  `JSON_ARRAYGET` (`%DynamicArray.%Get`, `<RANGE>` for a negative position). `ivglistget` transcribes
  `CypherFn.IVGLISTGET`, which the translator does not emit for this shape.
- **reverse()** (`uses_cy_reverse`, `reverse_result`): `_scalar_string` sends a property read to SQL `REVERSE()`.
- **n[k]** (`node_key_read`): a variable that is not a parameter becomes its own name as the key.
- **range()** (`ivgrange`, `ivg_count`): `CypherFn.IVGRANGE` for a run-time step; `rule_range` is written separately
  (`rule_count`) so that a control on IVGRANGE cannot also change the rule.
- **randomUUID()/rand()** (`value_on_row`): a call with no row argument; the premise that IRIS evaluates it once per
  statement is observed on IRIS 2026.1 and stated as `evaluated_per_row() == false`.

## Theorems (11 verified; no imports)

As-built departures: `theorem_row_negative_index_fails` ([bug-cyp-111](../../bugs_issues.md#bug-cyp-111)),
`theorem_stored_list_reversed_as_text` ([bug-cyp-112](../../bugs_issues.md#bug-cyp-112)),
`theorem_row_key_reads_variable_name` ([bug-cyp-113](../../bugs_issues.md#bug-cyp-113)),
`theorem_runtime_zero_step_empty` ([F-C0841](../../bugs_issues.md#F-C0841), inherited),
`theorem_rows_share_one_value` ([bug-cyp-114](../../bugs_issues.md#bug-cyp-114), provider-conditional).
Agreeing neighbors (universal where a parameter is shown): `theorem_literal_index_follows_rule(len, i)`,
`theorem_row_nonnegative_index_follows_rule(len, i)`, `theorem_ivglistget_is_rule(len, i)`, `theorem_reverse_neighbors`,
`theorem_param_key_follows_rule(value)`, `theorem_nonzero_step_follows_rule(start, end, step)`.

## Controls

Eight, all EXPECTED_FAIL in the final run: `row-index-through-ivglistget` (the repair; the non-negative neighbor still
verifies), `ivglistget-no-wrap`, `literal-negative-unwrapped`, `property-to-cy-reverse` (the repair),
`row-key-by-value` (the repair), `range-zero-raises` (F-C0841's repair), `range-ignores-direction`,
`per-row-evaluation`. Retained failure: the first run of `range-ignores-direction` **survived**
([receipt](../../results/cypher_fns/20261117T015827Z-control-range-ignores-direction/receipt.json)) because the rule and
IVGRANGE shared one count helper; the rule's count was then written separately and the control fails as expected.

## Binding

[binding.py](binding.py): 43 cases on the fixture through the product's SQL Cypher path and the SQL-callable
`CypherFn_IVGLISTGET`, `CypherFn_IVGRANGE` and `JSON_ARRAYGET`, compared with a port of the spec: **AGREES**; each of
the eight mutations detected; altering the observed row index -1 to "the element" is detected
([receipt](../../results/cypher_fns/20261117T015955Z-binding/receipt.json)). The native executor declined all 24
function queries. Retained: the first binding run DISAGREED on its own harness (it bound `?` parameters to
`JSON_ARRAYGET`, which IRIS refuses; [receipt](../../results/cypher_fns/20261117T015937Z-binding/receipt.json)).

## Limits

The port is unverified Python; the binding observes outcomes classes (element position, null, failure; list or text;
which key was read; element counts; distinct values), not every byte. The translator's choice is transcribed for the
shapes probed, not for every AST kind. The map value types
([bug-cyp-115](../../bugs_issues.md#bug-cyp-115)), the error text ([bug-cyp-116](../../bugs_issues.md#bug-cyp-116)),
percentiles, `split`, `keys` and `=~` are observed only. The `CREATE` refusal with `randomUUID()` was not traced to its
source. The 13 `CypherFn` bodies that Cypher does not reach are not modeled.

## Iteration 50: repairs from review 47-49

[Review](../../../uplift/consolidated/iteration-50/REVIEW-47-49.md) items 2, 3, 4, 6 and m5; dispositions in [DISPOSITIONS.md](../../../uplift/consolidated/iteration-50/DISPOSITIONS.md). Earlier sections describe iteration 47
and are kept; where they differ, this section governs.

- **List index by source and kind** (item 2, item 6). `translated_index(src, kind, len, i)` now takes the list's source
  (`PropertyRead`, `WithLiteralList`, `WithOtherList`), the index kind (`LiteralInt`, `RowValue`, `Param`) and an
  optional index (`None` is null), following `_expr_subscript`'s branches and `_is_row_list_elem` (R308):
  `JSON_ARRAYGET(CAST(i))` for a property read, `CY_LIST_ELEM` (typed, wraps) for a row index into a WITH-held literal
  list, `JSON_VALUE('$.' || i)` for another WITH column, an inlined `JSON_ARRAYGET` for a parameter on a WITH column and
  a refused marker on a property read. `translated_type` says whether the element keeps its type. A null index reads
  position 0 on every run-time path (`json_arrayget_opt`, `json_value_index`): IRIS passes NULL to the ObjectScript
  function as `""`. The iteration-47 model routed every run-time index through `JSON_ARRAYGET`, so it predicted text and
  a failure for `WITH [1, 2, 3] AS l UNWIND [-1] AS i RETURN l[i]`, which answers the integer 3.
- **reverse()** (item 3). `ArgKind` gains `ListValuedCall`, `Slice`, `Subscript`, `OtherCall`; `reverse_result` takes
  whether the translator knows the column is a list, and `Rev` gains `ListAsJsonText`. The iteration-47 model predicted a
  list for `WITH n.l AS l RETURN reverse(l)`, which answers the string `'[3,2,1]'`.
- **n[k]** (m5). `KeyArg::WithColumn` fails ("Non-integer index type"): a node carried through `WITH` is a stage column.
- **randomUUID()/rand()** (item 4). Unchanged formally; reclassified: `evaluated_per_row()` is an observed IRIS premise,
  so the translator member `_scalar_numeric_and_datetime` is a locator only (`cites`) in the crosswalk, and the theorem
  is a premise witness, not a model of the emitter.

Theorems (16 verified): new `theorem_param_negative_index_fails`, `theorem_with_literal_row_index_follows_rule`,
`theorem_null_index_reads_first_element`, `theorem_unknown_list_variable_answered_as_text`,
`theorem_with_column_key_fails`; `theorem_row_negative_index_fails` now holds for every negative index and both
property sources; `theorem_stored_list_reversed_as_text` is stated per argument kind (its first generalization over
`!uses_cy_reverse(k)` let the control `property-to-cy-reverse` survive vacuously:
[receipt](../../results/cypher_fns/20261117T032008Z-control-property-to-cy-reverse/receipt.json), kept).

Controls (13, all EXPECTED_FAIL, each failing exactly its named theorems): new `with-literal-elem-unwrapped`,
`with-literal-elem-untyped`, `null-index-is-null`, `reverse-column-typed`, `with-key-by-value`; `row-index-through-ivglistget`
now also fails the null theorem (the repair tests for null). Final:
[prove](../../results/cypher_fns/20261117T033035Z-prove/receipt.json),
controls `results/cypher_fns/20261117T0330{36..49}Z-control-*`.

Binding: **AGREES 103 cases** (9 index shapes × 7 indexes incl. null, 11 reverse forms, 3 key forms, ranges, rand), all
13 mutations and the tamper check detected; the native executor declined all 84 queries
([receipt](../../results/cypher_fns/20261117T033050Z-binding/receipt.json)). The element type is compared for non-null
indexes only.

Limits added: the range model covers integer steps (a fractional run-time step, [bug-cyp-131](../../bugs_issues.md#bug-cyp-131),
is observed only); `CY_LIST_ELEM` with a null index of unknown kind (e.g. from a property) is read from source, not probed.
