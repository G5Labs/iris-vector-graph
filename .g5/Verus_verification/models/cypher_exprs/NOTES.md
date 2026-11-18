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

## Iteration 50: repairs from review 47-49

[Review](../../../uplift/consolidated/iteration-50/REVIEW-47-49.md) items 4, 5, 7 and m1; dispositions in [DISPOSITIONS.md](../../../uplift/consolidated/iteration-50/DISPOSITIONS.md). Earlier sections describe iteration 48 and are
kept; where they differ, this section governs.

- **A parameter on a relationship CREATE between new nodes** (item 5). `RelValue::Param` is dropped like a call
  (`translator.py:10213-10226`: an `ast.Parameter` is neither a Literal nor a Variable). Neighbors in the model:
  `create_node_param` (written) and `create_rel_matched_value` (the alias path writes a literal or a parameter and refuses
  a computed value, observed for `toUpper('ab')`, `size('ab')` and `a.num + 1`). `theorem_inline_rel_param_dropped`,
  control `rel-param-kept`.
- **Simple CASE across kinds** (item 7). `simple_case_takes`: `_expr_case` drops a WHEN of another kind only when both
  kinds are known statically (literals); otherwise IRIS's `CASE x WHEN y` compares a number with text that spells it as
  equal (`sql_case_eq`, an observed provider behavior over canonical spellings). `theorem_simple_case_coerces_across_kinds`,
  neighbor `theorem_simple_case_same_kind_or_literal_follows_rule`; controls `case-kinds-compared` (the repair),
  `case-literal-kinds-unchecked`.
- **A null list's slice** (m1). `as_built_slice_of` over `ListIn::Null` answers the empty list: `JSON_TABLE` over NULL
  has no rows and nothing tests the list. `theorem_null_list_slice_is_empty`, control `null-list-guard`.
- **Premise constants** (item 4). `identifier_branch_looks_ahead()` is gone: `parses(lo, upper)` now derives the
  parser's refusal from the observed tokens (`a..3` is DOT FLOAT, `a..b` and `a..]` DOT DOT) and the branch's
  `expect(IDENTIFIER)`. `node_update`'s `deployed` input now comes from `prop_set_deployed(cached, check)`, the member's
  own logic (cache, else the dictionary check; unreadable counts as deployed), with `theorem_prop_set_switch_decides_retype`
  and control `unreadable-taken-as-absent`; the binding drives its found, absent (an engine whose IVG Schema does not
  exist), unreadable (a closed connection) and cached branches without overriding them. `driver_accepts_ast()`,
  `iris_accepts_scalar_condition()` and `filer_writes_same_text()` stay: each is a provider's behavior (the driver, IRIS
  Prepare, IRIS's filer), observed and named as a premise; the emitter's choice beside each is modeled from its input
  (`folds(f)`, `condition_sql(syn)`, `setval`), so those bindings stay active.

Theorems (22 verified). Controls (22, all EXPECTED_FAIL, each failing exactly its named theorems): new `null-list-guard`,
`rel-param-kept`, `case-kinds-compared`, `case-literal-kinds-unchecked`, `unreadable-taken-as-absent`; `setval-skips-retype`,
`prop-set-not-emitted` and `filer-writes-same-text` now also name `theorem_prop_set_switch_decides_retype`, which their
change also breaks (their first iteration-50 runs failed it unnamed; receipts kept). Final:
[prove](../../results/cypher_exprs/20261117T033051Z-prove/receipt.json).

Binding: **AGREES 233 cases**, all 22 mutations and the tamper check detected
([receipt](../../results/cypher_exprs/20261117T033119Z-binding/receipt.json)).

Not modeled (observed only): a list literal holding a property read in `SET`/`CREATE` raises a Python `TypeError`
([bug-cyp-128](../../bugs_issues.md#bug-cyp-128)); `trim`'s whitespace ([bug-cyp-130](../../bugs_issues.md#bug-cyp-130));
a parameter list sliced by parameter bounds ([bug-cyp-125](../../bugs_issues.md#bug-cyp-125), driver premise plus the
null-guard marker order).

## Iteration 53 (review 50-52 m4, m5)

- **m5, the lexer premise is now observed.** `tokens_after_lower` was a constant table "as observed". The binding now
  reads the lexer's two tokens after the identifier for `a..3`, `a..b` and `a..]` (cases `lex_Int`, `lex_Ident`,
  `lex_Close`: `[Dot, FloatLit]`, `[Dot, Dot]`, `[Dot, Dot]`) and compares them with the table; the mutation
  `lexer_table_altered` (the integer form lexed as two dots) is detected. The table stays a premise of the model; it
  is observed at the pin, not derived from `Lexer._tokenize_number`, so the lexer is not claimed as a bound member.
- **m4, `_create_resolve_prop_value` relabeled.** Its crosswalk row is now a delegate of `folds`: it forwards the
  folded value and otherwise returns the call's AST. Whether an unfolded value is written is decided by `folds` and
  the driver premise `driver_accepts_ast`; the member's own choice to return the AST instead of refusing cleanly would
  leave the outcome (`RefusedNothingWritten`) and the binding unchanged, so the model does not distinguish it.

Binding: **AGREES 236 cases**, all 23 mutations and the tamper check detected
([receipt](../../results/cypher_exprs/20261117T044717Z-binding/receipt.json)). The model file is unchanged; prove and controls were
re-run on it for currency.

## Latest receipts (checked in iteration 64)

The latest receipt of each kind, as `tools/census.py` resolves it: prove [20261117T044807Z-prove](../../results/cypher_exprs/20261117T044807Z-prove/receipt.json), binding [20261117T044717Z-binding](../../results/cypher_exprs/20261117T044717Z-binding/receipt.json), and the latest receipt for each of the 22 named controls in [results/cypher_exprs/](../../results/cypher_exprs/). A receipt this file calls "final" or "latest" above is the one current when that paragraph was written; later reruns supersede it.
