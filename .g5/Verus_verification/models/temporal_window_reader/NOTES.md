# temporal_window_reader — notes

Consolidated uplift, 2026-11-14. Product baseline `3eaa79cf`. Root [temporal_window_reader.rs](temporal_window_reader.rs); controls in [model.json](model.json); unit-level binding [binding.py](binding.py). Public cases M06, M07, M08 (and the reader J02 reuses). Neither prior arm modeled this reader.

Status words: **Proved** (Verus, all sizes, about the model, as-built transcription); **Observed** at unit level (the real Python functions ran; the server was a scripted substitute); **Inspected** (the server's ObjectScript, by line).

## Obligations and theorems

| Ontology block | Obligation | Theorem (all as-built) |
|---|---|---|
| [temporal.window.sources](../../../ontology/features/temporal.g5.md#temporal.window.sources) | omitted `sources` sends no key; an explicit empty list sends an empty list | `theorem_spec_sources_omitted_vs_empty` |
| same | the server reads every source with no key and none for an empty list or a list of empty names | `theorem_server_filter_sources`, `theorem_m06_omitted_reads_all_empty_reads_none` |
| same | two of source, sources, prefix are refused before any call | `theorem_two_filters_refused` |
| [temporal.window.paging](../../../ontology/features/temporal.g5.md#temporal.window.paging) | iterating to the end returns the rows of every page up to the done page, in order, whatever empty pages come before it | `theorem_yield_is_concat_to_done` (inductive core `lemma_drain`); witness `witness_empty_middle_page` |
| [temporal.window.paging.release](../../../ontology/features/temporal.g5.md#temporal.window.paging.release) | exhaustion: no Close call, the handle freed by the server; one page: one round trip | `theorem_yield_is_concat_to_done`, `theorem_exhaustion_frees_without_close` |
| same | close mid-read: one Close, freed; a second close nothing; no further server call | `theorem_close_mid_read_once` |
| same | a failed page: raises after exactly one Close; a failed Open raises with nothing open | `theorem_failed_page_closes_once`, `theorem_failed_open_raises` |
| same (producer) | a page not marked done holds at least one row; an exact multiple ends with an empty done page | `theorem_server_full_page_nonempty`, `witness_exact_multiple_ends_with_empty_done_page` |

Expected: `prove` PASS, 16 verified, 0 errors; 8 controls, each EXPECTED_FAIL.

## Controls (each removes one decisive guard or effect)

| Control | What it changes | Fails in |
|---|---|---|
| `stop-on-empty-page` | an empty page ends the read | `lemma_drain` |
| `close-after-exhaustion` | the cursor calls Close after the server's done page | `lemma_drain` |
| `server-keeps-handle-at-done` | the server does not free at done (`Page :187-188` removed) | `lemma_drain` |
| `skip-close-on-failure` | a failed Next raises without `close()` | `theorem_failed_page_closes_once` |
| `close-not-idempotent` | `close()` ignores `closed` | `theorem_close_mid_read_once`, `theorem_exhaustion_frees_without_close` |
| `empty-list-sends-no-key` | `window_spec` drops an empty list | `theorem_spec_sources_omitted_vs_empty`, `theorem_server_filter_sources` |
| `server-empty-list-reads-all` | the server reads an empty list as no filter | `theorem_server_filter_sources` |
| `server-empty-page-not-done` | the server answers an empty page without done | `theorem_server_full_page_nonempty`, `witness_exact_multiple_ends_with_empty_done_page` |

`lemma_drain` is the induction that `theorem_yield_is_concat_to_done` and the exhaustion theorems consume; Verus checks each function against the others' specifications, so a control that breaks the induction fails there.

## Bindings (path::symbol at the pin)

| Model function | Product | Grade |
|---|---|---|
| `window_spec`, `sources_key`, `named_count` | `iris_vector_graph/_engine/temporal_window.py::window_spec` :37-58 | Observed (binding, 45 argument combinations) |
| `open` | `::TemporalWindowCursor.__init__` :82-93 | Observed (binding) |
| `step`, `after_page`, `page_ends_read` | `::TemporalWindowCursor.__next__` :102-113 | Observed (binding) |
| `close` | `::TemporalWindowCursor.close` :115-124; `__exit__` :129-130; `__del__` :132-136 | Observed (binding: close twice, with block, abandon and collect) |
| failure path | `::_server_call` :67-71 | Observed (binding) |
| `server_admits`, `list_admits` | `iris_src/src/Graph/KG/TemporalWindow.cls::Open` :54-66, `::NextKey` :196-239 | Inspected; observation pending (no IRIS here) |
| `page` | `TemporalWindow.cls::Page` :128-193 (`:185`, `:187-191`) | Inspected; observation pending |
| server free at done, Close | `TemporalWindow.cls::Page` :187-188, `::Close` :94-97 | Inspected; observation pending |

Binding run: `binding.py` drives the pin's real module from `$RUN_DIR/pin` with a scripted native object: 160 scripts (every script whose answers before the last are successful pages not marked done with 0-2 rows, and whose last answer is done with 0-2 rows or a failure, up to four answers) under four uses (iterate to the end; one event, close twice, next; a `with` block; abandon and collect) = 640 comparisons, plus 45 `window_spec` argument combinations. Expected outcomes come from a hand transcription of the model's spec functions in the harness, not from the product. Detection: a changed Close count in one observation, a cursor mutant that ends on an empty page, and a `window_spec` mutant that drops an empty list are each reported. Receipt: `results/temporal_window_reader/<stamp>-binding/receipt.json`.

## Premises and trust inventory

- The window ends: some answer is marked done (`ends_at`). Inspected: `Page` returns done when its `$Order` walk runs out (`:144-146`); a script that never ends is outside the theorem.
- A row's source is a global subscript and so never `""` (`server_admits`'s `s.len() > 0`).
- A failed Next may leave the handle open on the server (worst case); `close()` then frees it. A handle opened on another connection is not modeled (the cursor keeps its own native object; `TMP-B6.7`).
- Rows are abstract integers; attributes, ordering inside a page and the PAGECHARS text length are not modeled (the page producer's `lim` stands for the length limit).
- Trust inventory: none (no `assume`, `admit` or `external_body`); bundled `vstd` only. The harness's spec transcription is unverified Python.

## Not modeled

The live-read semantics between pages (`temporal.window.concurrent-writes`), the direction and predicate filters, the latest-event reader, and the one-call `QueryWindow` readers. A restored window (J02) reuses this reader; no model connects save, restore and this read.
