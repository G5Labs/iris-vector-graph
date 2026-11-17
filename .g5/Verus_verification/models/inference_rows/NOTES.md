# RDFS inference rows

Product `3eaa79cf`, unchanged. Iteration 38 (continuation). Predictions frozen from the API reference and guides before
the source was read: [inference-PAIRS.md](../../../uplift/consolidated/iteration-38/inference-PAIRS.md). Owner (new):
[install.inference](../../../ontology/concepts/install.g5.md#install.inference).

## What the model decides

One graph's `rdf_edges` as a total function from a triple to no row, an asserted row, or a row with the qualifier
`{"inferred":true}`. `derives` transcribes the rules `materialize_inference` applies to asserted rows (subclass and
subproperty closures, rdf:type through subclasses, domain and range); `materialize` inserts each derived triple that has
no row, marked inferred; `create_edge` leaves an existing triple alone (multigraph off); `retract` keeps asserted rows only.

## Theorems (8 verified; no imports)

| Theorem | Claim | Disposition |
|---|---|---|
| `theorem_retract_keeps_asserted` | after retract a triple is present exactly when it was asserted | as-built agrees |
| `lemma_same_asserted`, `theorem_rerun_adds_nothing` | derivation depends only on asserted rows, so a second materialize adds nothing | as-built agrees |
| `theorem_asserted_first_survives` | a triple created before materializing survives retract | as-built agrees |
| `theorem_asserted_after_is_retracted` | the same triple created after materializing stays inferred and is retracted | [bug-str-105](../../bugs_issues.md#bug-str-105) |
| `lemma_derived_predicates`, `theorem_no_subproperty_propagation` | no user predicate is ever derived (no rdfs7) | [bug-str-106](../../bugs_issues.md#bug-str-106) |
| `theorem_domain_type_not_lifted` | a domain type is not lifted to the domain class's superclass | [bug-str-106](../../bugs_issues.md#bug-str-106) |

No `assume`, `admit` or `external_body`. Earlier attempts kept on record: a `Set::new` API mismatch (ERROR), the
reserved word `has` (ERROR), a finite-`Map::new` domain (ERROR), and two runs that needed explicit existential witnesses
(UNEXPECTED).

## Controls

Five, all EXPECTED_FAIL: `create-marks-asserted` (the repair), `derive-rdfs7`, `derive-lifts-domain`,
`retract-everything`, `materialize-overwrites`.

## Binding

[binding.py](binding.py) builds the W44 shapes in a fresh named graph and records rows (with markers) and `^KG` after
materialize, a second materialize, a create of an inferred triple, and retract; it compares them and the three answers
with the port: **AGREES**; every row has its `^KG` entry and every retracted row's entry is gone. Each of the five
mutations is detected.

## Premises and limits

- Subclass and subproperty chains of at most two links: `tc` composes once, which equals the product's fixpoint on
  that domain (all W44 shapes).
- Not exercised: OWL rules, multigraph mode (a create would add a second, asserted row), the ledger (F-C0151 and strict
  mode), concurrency with other writers.
