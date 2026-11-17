# adjacency maintenance

The adjacency index derived from a history of row writes and deletes (create, Cypher CREATE / DELETE r, engine and store deletes, delete by prefix, set_edge_weight, sync) equals a rebuild from the rows, for every admissible history; per-writer effects, the merged ^NKG edge decision, labels, degree, and two-hop fast vs exact.

Evidence status: active. Variant: as-built transcription (declared index).

Verified and errors count obligations reported by the verifier. A control is judged against its named expected failure. Native observations have their recorded scope.

| Binding mutation | Mirrors control | Cases it changed (receipt 20261117T075252Z) |
|---|---|---|
| remove_keyed_takes_triple | remove-keyed-takes-triple | 3 |
| put_keyed_drops_others | put-keyed-drops-others | 5 |
| leaf_highest | canon-leaf-not-lowest | 3 |
| plain_remove_keeps | plain-remove-keeps | 2 |
| erase_ignores_graph | erase-ignores-graph | 5 |
| held_elsewhere_ignored | held-elsewhere-ignored | 1 |
| fresh_ignores_stamp | fresh-ignores-stamp | 1 |
| label_erase_by_label | label-erase-by-label | 2 |
| reweight_ignored | update-ignored | 1 |
| exact_is_sum | walk-counts-source-and-first-hop | 1 |
| transition_new_weight | transition-weight-not-old-leaf | 2 |
| create_ignores_mode | create-ignores-mode | 5 |

Controls with no binding mutation (proof-only): mark-gone-default-graph (the binding does not read the `^NKG` stale mark: the flag is namespace-wide and other workers write in USER), stamp-not-equality (the stamp comparison is exercised by fresh-ignores-stamp's case only). Tamper: +1 on the observed survivor leaf after `DELETE r`, detected.

[Formal source](adjacency_maint.rs)

[Formal claims, product bindings and limitations](NOTES.md)

[Premises](NOTES.md)

[Product and declaration crosswalk](../../crosswalk/decision-links.tsv)
