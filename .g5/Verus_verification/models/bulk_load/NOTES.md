# BulkLoader node loads, re-runs and index visibility

Product `3eaa79cf`, unchanged. Iteration 25 (retest from `cloud-iris-retest-start-20261116`). Predictions frozen before
native observation in [bulk-loader-PAIRS.md](../../../uplift/consolidated/iteration-25/bulk-loader-PAIRS.md). Owner:
[install.bulk_load.loader](../../../ontology/concepts/install.g5.md#install.bulk_load.loader).

## What the model decides

The store maps (graph, node id) to that node's rows: whether its node row is indexed, its labels and whether they are
indexed, its property keys and whether they are indexed. `load` transcribes `BulkLoader.load_nodes`
(`bulk_loader.py:252-378`): the skip scan (`_known_nodes_sql` :182-199, `%NOINDEX` hint, scoped to the loader's graph)
selects the input ids with no node row; phase 1 writes their node rows; phases 2 and 3 write labels, then properties
(`id` always added) for those same ids only (`nodes_to_process = new_nodes` :314). Each phase commits per batch, and a
failed phase rolls back its own batch and raises (`_executemany_batched` :115-120), so a failure in phase 2 leaves the
phase-1 rows and a failure in phase 3 leaves phases 1 and 2. `%NOINDEX` (`use_noindex=True`, the default) leaves a
row out of its index; `rebuild` transcribes `rebuild_all_indices` (:484-510). The reader is `get_node(n, graph=g)`: an
index read of the node row, then its indexed labels and properties.

Domain: one batch per phase, distinct input ids, `skip_existing=True` (the default). The index behavior of IRIS
(`%NOINDEX` rows invisible to index reads until `%BuildIndices`) is a provider premise, observed below, not derived.

## Theorems (8, all new; no imports)

| Theorem | Claim |
|---|---|
| `theorem_done_then_rebuild_reads_input` | a completed load followed by a rebuild reads back as its input |
| `theorem_indexed_load_reads_now` | an indexed load reads back as soon as it returns |
| `theorem_noindex_invisible_until_rebuild` | a `%NOINDEX` load has written its node rows, but the reader sees none of them (bug-plt-106) |
| `theorem_complete_rerun_is_noop` | the same load after a completed one changes nothing, in either index mode |
| `theorem_interrupted_load_is_never_completed` | after a phase-2 failure, no completed re-run, even with a rebuild, gives a node its labels or properties (bug-plt-011) |
| `witness_interrupted_rerun_strands` | the stranded node is readable but lacks its label, so it fails the owner's outcome |
| `theorem_other_graphs_untouched` | a load changes no other graph's rows |
| `theorem_same_id_other_graph_is_written` | an id that exists only in another graph is still loaded |

No `assume`, `admit` or `external_body`; bundled vstd only.

## Controls

Six, all EXPECTED_FAIL full and isolated ([receipts](../../results/bulk_load/)): `phase1-not-committed`,
`rerun-completes-stranded` (the repair proposal), `skip-sees-indexed-only` (the scan without the `%NOINDEX` hint),
`skip-across-graphs`, `reader-ignores-index`, `rebuild-skips-labels`. The first two runs of `phase1-not-committed` and
`rerun-completes-stranded` were FAIL_ELSEWHERE because the witness called the theorem as a lemma (verified alone, it
passed); the witness was made self-contained and both controls rerun. The earlier receipts are kept.

## Binding

[binding.py](binding.py) runs the actual `BulkLoader.load_nodes`, `rebuild_all_indices` and `get_node` on the
run-isolated retest fixture over 72 histories: first call indexed or `%NOINDEX`; completed, failed at the label insert or
failed at the property insert (injected: the first `executemany` into that table raises); re-run none, indexed or
`%NOINDEX`; rebuild or not; the first id already present in the default graph or not. It compares the readers'
presence, labels and property keys for both nodes, the re-run's returned counts and the default graph's node with a
port of the model: **AGREES, 360 comparisons**; every one of six port mutations mirroring the controls is detected
(12-27 histories each). Command (fixture running, from the pin directory):
`IVG_REPO=<repo> IVG_PIN_DIR=$RUN_DIR/pin $RUN_DIR/venv/bin/python -B <repo>/.g5/Verus_verification/models/bulk_load/binding.py`.

## Limits

Transcription with native agreement; no product body is verified. Not modeled: `load_edges` (dedupe, endpoint
registration), `load_networkx` beyond the reader check in the PAIRS probe, `build_graph_globals`, the
duplicate-or-refusal decision by error text, several batches per phase, `skip_existing=False`, concurrent loaders, and the
schema handling of bug-plt-012. The interruption is injected; that a connection loss or killed process leaves exactly
this state follows from the per-batch commit, not from an observed outage.
