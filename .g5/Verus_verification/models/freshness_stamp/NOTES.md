# freshness_stamp — notes

Consolidated uplift, 2026-11-14. Product baseline `3eaa79cf`. Root [freshness_stamp.rs](freshness_stamp.rs); controls in [model.json](model.json); binding [binding.py](binding.py). Public case M09. Owner block: [structure.rebuilt.stamp](../../../ontology/features/graph-structure.g5.md#structure.rebuilt.stamp).

## Obligations and theorems (all Proved, as-built transcription)

| Obligation | Theorem |
|---|---|
| current exactly when stamped and the stamp equals the live token | `theorem_is_current_iff_stamped_equal` |
| a never-stamped or empty-stamped store is stale at token zero (Python and ObjectScript readers) | `theorem_unstamped_stale_at_zero` |
| a store stamped at zero is current while the token is zero, unset or empty | `theorem_stamped_zero_current` |
| `Freshness.is_current` and `TraversalKHop.Fresh` decide alike | `theorem_python_agrees_with_objectscript` |
| `stale_stores` lists exactly the stores that are not current, in order | `theorem_stale_stores_exact` |
| the legitimate path (stamp, then a write makes it stale) | `witness_stamp_then_write` |

Expected: 7 verified, 0 errors; 4 controls EXPECTED_FAIL (`unset-stamp-reads-zero`, `unset-token-not-zero`, `os-fresh-without-data-check`, `stale-list-drops-unstamped`).

## Bindings

| Model | Product (pin) | Grade |
|---|---|---|
| `read_int` | `iris_vector_graph/freshness.py::Freshness._read_int` :45-52 | Observed (binding) |
| `token` | `::Freshness.token` :54-57 | Observed |
| `built_from` | `::Freshness.built_from` :66-68 | Observed |
| `is_current` | `::Freshness.is_current` :70-72 | Observed |
| `stale_stores` | `::Freshness.stale_stores` :74-77 | Observed |
| `os_fresh` | `iris_src/src/Graph/KG/TraversalKHop.cls::Fresh` :237-243 | Inspected; observation pending |

Binding: the pin's real `Freshness` over a dict host with IRIS `$Data` semantics (1 value, 10 children only), 64 stamp and token pairs plus 1,731 ordered store lists = 1,795 comparisons against a transcription of the spec functions; a flipped observation and a mutant that reads an unset stamp as 0 are both detected.

## Premises, trust and limits

- Stamps and tokens are canonical integers or unset or empty (the writers store `$Increment` results and `tVersion`). A non-canonical text such as `"007"` would split the two readers (Python `int()` reads 7; ObjectScript text equality does not); no writer produces one. Not modeled.
- The Python `Freshness` class has no caller inside `iris_vector_graph` at the pin (no module imports it); the run-time decision for the two-hop counts is `TraversalKHop.Fresh`. Other rebuilt stores (the interned snapshot, the algorithm cache) decide freshness by other means ([structure.rebuilt](../../../ontology/features/graph-structure.g5.md#structure.rebuilt)); this model says nothing about them.
- Trust inventory: none; bundled `vstd` only.
