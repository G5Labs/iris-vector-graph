# Cypher expressions over values known only at run time

Product `3eaa79cf`, unchanged. Iteration 48 (continuation, W55). Predictions frozen from openCypher, the owners and
the known-issues guide before the deciding source was read:
[cypherexpr-PAIRS.md](../../../uplift/consolidated/iteration-48/cypherexpr-PAIRS.md) (commit `d8fe862a`). Owners (new):
[query.functions.slice](../../../ontology/features/cypher.g5.md#query.functions.slice),
[.strings](../../../ontology/features/cypher.g5.md#query.functions.strings),
[.coalesce](../../../ontology/features/cypher.g5.md#query.functions.coalesce),
[query.values.conditions](../../../ontology/features/cypher.g5.md#query.values.conditions),
[query.writes.computed_values](../../../ontology/features/cypher.g5.md#query.writes.computed_values),
[query.writes.retype](../../../ontology/features/cypher.g5.md#query.writes.retype).

## What the model decides

Every section takes the argument's **syntax** (`Syntax`, `Fn`, `RelValue`, `CoArg`, `Lower`) as its input, the same
input the translator decides on, and derives the translator's choice from it; the choice is never a parameter.

- **Slices** (`translated_bound`, `as_built_slice` vs `rule_slice`): `_expr_slice` wraps a literal negative bound as
  `GREATEST(0, len + n)` and passes any other bound raw into `_slice_sql`'s window `rn > start AND rn <= end`.
- **Conditions** (`condition_sql`, `case_when`): `_translate_boolean_expression` makes predicates of literals, property
  reads, map access and comparisons, and leaves a bare row variable or parameter as its scalar. Premise
  `iris_accepts_scalar_condition() == false` (IRIS 2026.1, SQLCODE -14 at Prepare).
- **CREATE values** (`folds`, `create_node_value`, `create_rel_value`, `set_value`): `_create_resolve_prop_value` folds
  with `_fold_constant` or returns the AST; `_create_clause_relationship_entry` keeps only literals and UNWIND/FOREACH
  literals. Premise `driver_accepts_ast() == false` (`<LIST ERROR>`, the write transaction takes everything back).
- **coalesce** (`typed_coalesce`, `coalesce_number`): `_is_typed_coalesce` / `_scalar_coalesce`.
- **Parser** (`parses`): `Parser.parse_primary_expression` takes `.` after an identifier as a property access.
- **substring** (`as_built_substring` = `iris_substring(n, start + 1, l)` vs `rule_substring`): `_scalar_string`.
- **Prop_Set** (`setval`, `filer_update`, `node_update`): `_prop_set` emits `Prop_Set(%ID, val, v)` when the
  namespace has it (`engine._prop_set_deployed`); `PropWrite.SetVal` writes a same-text, other-type value into the row.
  Premise `filer_writes_same_text() == false` (the product's own measurement on 2026.3, and observed on this fixture
  through the product's path for a namespace without Prop_Set).

## Theorems (17 verified; no imports)

As-built departures: `theorem_row_negative_slice_departs(len, k)` (every list and every 0 < k < len;
[bug-cyp-117](../../bugs_issues.md#bug-cyp-117)), `theorem_row_boolean_condition_fails(v)`
([bug-cyp-118](../../bugs_issues.md#bug-cyp-118), provider-conditional), `theorem_unfolded_create_value_refused(f)`
([bug-cyp-119](../../bugs_issues.md#bug-cyp-119)), `theorem_inline_rel_expression_dropped(f)`
([bug-cyp-120](../../bugs_issues.md#bug-cyp-120)), `theorem_row_coalesce_number_as_text`
([bug-cyp-121](../../bugs_issues.md#bug-cyp-121)), `theorem_identifier_lower_bound_refused`
([bug-cyp-122](../../bugs_issues.md#bug-cyp-122)), `theorem_negative_start_answers_prefix(n, k, l)`
([bug-cyp-123](../../bugs_issues.md#bug-cyp-123)).
Agreeing neighbors: `theorem_literal_slice_follows_rule(len, s, e)`, `theorem_row_nonnegative_slice_follows_rule(syn,
len, s, e)`, `theorem_predicate_condition_follows_rule(v)`, `theorem_folded_create_value_written(f)` (with SET),
`theorem_inline_rel_literal_written`, `theorem_node_coalesce_keeps_type(b)`, `theorem_other_lower_bounds_parse`,
`theorem_inside_substring_follows_rule(n, start, l)`, `theorem_prop_set_retypes(old, new)`,
`theorem_without_prop_set_same_text_keeps_old(old, new)`.

## Controls

Seventeen, all EXPECTED_FAIL ([receipts](../../results/cypher_exprs/)); each fails exactly its named theorem except
`substring-zero-based` (an effect control), which fails the substring departure and its neighbor. Repairs that leave
their neighbor verified: `row-slice-wrapped`, `row-condition-compared`, `create-value-translated`, `rel-value-kept`
(partial repair), `coalesce-always-typed`, `identifier-lookahead`, `substring-checks-start`. Decisive guard or effect
removed: `literal-slice-unwrapped`, `property-condition-raw`, `toupper-not-folded`, `rel-literal-dropped`,
`coalesce-needs-two-props`, `setval-skips-retype`, `prop-set-not-emitted`. Premise flips: `iris-accepts-scalar-condition`,
`filer-writes-same-text`.

## Binding

[binding.py](binding.py): 209 cases on the fixture through `execute_cypher` (the native executor declined 156 of the queries
offered to it; a query it raised on is not counted, and none was answered natively in a case), compared with a port of the spec: **AGREES**
([receipt](../../results/cypher_exprs/20261117T022154Z-binding/receipt.json)); each of the 17 mutations is detected
(1 to 30 cases each) and altering the observed `slice_row_-3_5` to the rule's answer is detected. The Prop_Set cases
run once with the fixture's Prop_Set and once through the product's own path for a namespace without it
(`engine._prop_set_ok = False`), which observes the filer premise directly. Retained: the first binding run DISAGREED
on its own harness (an `UNWIND $pairs` read answered no rows with the fixture's driver;
[receipt](../../results/cypher_exprs/20261117T022138Z-binding/receipt.json)); that observation is
[bug-cyp-125](../../bugs_issues.md#bug-cyp-125), a driver-conditional potential problem.

## Limits

The port is unverified Python; the binding observes outcome classes (element window, branch or Prepare failure,
written / refused / dropped, int or text, parsed or not, character window, stored text and type), not every byte. The
translator's choices are transcribed for the syntaxes probed, not every AST kind (`_create_node_from_alias`, map
access conditions, CASE results and nested functions in CREATE are not separately bound). Zero-length string results
([bug-cyp-124](../../bugs_issues.md#bug-cyp-124)), `left`/`right` and the type conversions are observed only.
`PropWrite.Layout` and the lock path of `SetVal` are not modeled. Both IRIS premises and the driver premise are observed
on IRIS 2026.1 with intersystems-irispython 5.3.2 only.
