# PROV-O window readers

Product `3eaa79cf`, unchanged. Iteration 44 (continuation). Predictions frozen from SEMANTIC_LAYER.md:
[prov-PAIRS.md](../../../uplift/consolidated/iteration-44/prov-PAIRS.md). Owner (new):
[install.export.prov](../../../ontology/concepts/install.g5.md#install.export.prov).

## What the model decides

`read` (one `QueryWindow` string: an answer up to the cap, else a raise), `documented` (the guide's empty file with a
warning), `export_out` (reads its window), `as_dict_out` (reads the whole default history), `in_window` (inclusive).

## Theorems (3 verified; no imports)

`theorem_bounds_inclusive` (agrees), `theorem_large_window_raises` ([bug-plt-109](../../bugs_issues.md#bug-plt-109)),
`theorem_as_dict_fails_on_large_history` ([bug-plt-110](../../bugs_issues.md#bug-plt-110)).

## Controls

Four, all EXPECTED_FAIL: `read-streams`, `as-dict-bounded`, `exclusive-end`, `doc-matches-code`.

## Binding

[binding.py](binding.py): on the fixture's default graph with more than 40,000 temporal edges (W50's load), four
outcome classes through the actual `prov_export` and `prov_as_dict`: **AGREES**; each mutation detected.

## Premises and limits

The cap (about 35,000 edges of these sizes) is IRIS's string limit, observed. The PROV vocabulary mapping (P1, P4) was
observed in W50 and is stated in the owner, not modeled.
