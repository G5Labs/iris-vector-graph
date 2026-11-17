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
shapes probed, not for every AST kind. The run-time element type (`'1'` for 1), the map value types
([bug-cyp-115](../../bugs_issues.md#bug-cyp-115)), the error text ([bug-cyp-116](../../bugs_issues.md#bug-cyp-116)),
percentiles, `split`, `keys` and `=~` are observed only. The `CREATE` refusal with `randomUUID()` was not traced to its
source. The 13 `CypherFn` bodies that Cypher does not reach are not modeled.
