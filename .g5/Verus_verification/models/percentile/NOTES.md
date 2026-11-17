# percentileDisc and percentileCont (W59, iteration 53)

Product `3eaa79cf`, unchanged. Predictions frozen first:
[bm25-percentile-PAIRS.md](../../../uplift/consolidated/iteration-53/bm25-percentile-PAIRS.md) (commit `5f4d435f`).
Owner: [query.functions.percentile](../../../ontology/features/cypher.g5.md#query.functions.percentile).

## What the model decides

Over a sorted list of integers (`SortArray` is a delegate: an ascending insertion sort) and p = pn/pd:
- `pdisc`: out of [0, 1] refused; no values null; index `disc_index = floor((n − 1) p)` clamped (`Percentile.cls` 6-18).
- `pcont`: the same checks; lower = floor((n − 1) p); at or past the last index the last value, otherwise the exact
  rational lo + frac (hi − lo) (21-36).
- The rule: `rule_disc_index = ceil(p n) − 1` (nearest rank, Neo4j) and `rule_cont` (interpolation between floor and
  ceil of (n − 1) p).
- Reached from the translator's `Percentile_PDISC|PCONT(JSON_ARRAYAGG(CAST(x AS DOUBLE)), p)`
  (`translator.py` 28570-28618, 6138-6150) through `SqlProcs.PercentilePDISC/PCONT` (109-117); the reader's column is
  FLOAT (`query.py` `_float_expr_value`).

## Theorems (26 verified; no assume, admit or external_body)

`theorem_cont_follows_rule` (every list and p, the last-index branch included); `theorem_disc_never_above_rule`
(every n, p); `theorem_disc_top_percentile_misses_max` (every n ≥ 2 and (n − 1)/n < p < 1: index n − 2 where the rule
takes n − 1); witnesses `theorem_disc_rounds_down_p90` (4 values at 0.9 and 0.6; 10 values at 0.95); neighbors
`theorem_disc_agrees_at_ends_and_median`, `theorem_empty_and_out_of_range`. Finding:
[bug-cyp-134](../../bugs_issues.md#bug-cyp-134) (Medium).

Final: [prove](../../results/percentile/20261117T052003Z-prove/receipt.json) and the `20261117T0520*` controls. The
`20261117T051303Z` prove and `0513*` controls ran on the same model before the finding was renumbered from
bug-cyp-133 (taken by the parallel graph-procedures worker) to bug-cyp-134 in a comment; superseded, not failed.

## Controls (4, all EXPECTED_FAIL)

`disc-nearest-rank` (the repair direction), `cont-floor-only`, `no-range-check`, `empty-is-zero` (before 4.6.0 R274).
A control removing PCONT's last-index branch was considered and dropped: at that index frac is 0, so the branch is
equivalent (ObjectScript's `%Get(n)` reads "" as 0 times 0), and no theorem should fail.

## Binding

[Receipt](../../results/percentile/20261117T052012Z-binding/receipt.json): **AGREES 156 cases**, 4/4 mutations and the
tamper detected. Readers: Cypher `UNWIND` of 9 literal lists × 11 p, stored values through `MATCH` with a `$p`
parameter (a null value, no rows), and the SQL functions directly. Kept: `20261117T051656Z-binding` DISAGREES on four
p = 1/3 cases. The port used the exact 1/3, but the product receives the double 0.333…315, and 3 × that is below 1, so
the floor is 0 (10, not 20). The port now uses the double's exact value. This is the same rounding-down rule, made
visible by binary p.

## Premises and limits

- P-AGG-NULL: `JSON_ARRAYAGG` leaves nulls out (observed: [10, null, 30] gives 10 and 20.0).
- A list parameter (`UNWIND $xs`) fails before the function with this driver ([bug-cyp-125](../../bugs_issues.md#bug-cyp-125)),
  so the binding uses literal lists and stored values.
- Integer answers read as floats (20.0): the translator types the column FLOAT; owned as built.
- Non-numeric values are cast to DOUBLE by the translator; not probed.
