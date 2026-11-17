# Breadth-first walk readers

Product `3eaa79cf`, unchanged. Iteration 37 (continuation). Predictions frozen from the owner blocks and the API
reference before the source was read: [traversal-PAIRS.md](../../../uplift/consolidated/iteration-37/traversal-PAIRS.md).
Owners: [algorithms.op.walks](../../../ontology/features/algorithms.g5.md#algorithms.op.walks),
[algorithms.op.khop](../../../ontology/features/algorithms.g5.md#algorithms.op.khop).

## What the model decides

`BFSFast` records every edge it walks as a row (source, type, target, hop), hop by hop. Two readers turn that list into
an answer:

- `stage` is what `BFSFastJsonSorted` writes for `kg_GRAPH_WALK`: one entry per (hop, target), a later row
  overwriting an earlier one. `walk_lists_edge` is the owner's reading that every walked edge is a row.
- `call_large` is `host.Host.call_large`: on a string overflow it falls back to a stream variant only for methods in
  `STREAM_FALLBACKS` (`has_stream`). `khop_read` reads `BFSFastJson` (which has one); `walk_read` reads
  `ReadBFSResults` (which has none), and the stage is cleared only when that read returns.

## Theorems (6 verified, including termination of `stage`; no imports)

| Theorem | Claim | Disposition |
|---|---|---|
| `lemma_last_wins` | the last row for a key is the one the walk returns | as-built |
| `theorem_distinct_keys_list_every_edge` | with distinct (hop, target) keys every walked edge is a row | as-built agrees with the owner |
| `theorem_same_hop_target_collapses` | two rows with the same (hop, target) leave one, the later | [bug-str-103](../../bugs_issues.md#bug-str-103) |
| `theorem_khop_answers_any_size` | khop answers whether or not the reply overflows | as-built agrees |
| `theorem_walk_overflow_raises_and_leaves_stage` | an overflowing walk raises and leaves the stage; one that fits answers and clears it | [bug-str-104](../../bugs_issues.md#bug-str-104) |

No `assume`, `admit` or `external_body`.

## Controls

Five, all EXPECTED_FAIL at the named functions: `stage-keeps-every-edge` (first wins), `walk-has-stream` (the repair),
`khop-no-stream`, `stage-killed-on-raise`, `stage-key-ignores-step` (fails in `lemma_last_wins` and
`theorem_same_hop_target_collapses`; its expected location was set after the first run failed elsewhere than named,
which is kept on record). The first two proof runs (`20261117T002605Z`, `20261117T002621Z`) were UNEXPECTED (a
missing unfolding), also kept.

## Binding

[binding.py](binding.py) builds five small graphs and one 40,000-edge star on the run-isolated continuation fixture.
For each small graph it takes the producer's own edge order from `khop` (every walked edge, in walk order), applies a
port of `stage`, and compares with `kg_GRAPH_WALK`'s rows: **AGREES** on `chain`, `diamond`, `two_types`, `cross`,
`back_edge`. For the star it checks that `khop` answers, that the walk raises, and that a new `^ArnoKG("bfs_r")` subtree
stays (the binding then removes it). Four port mutations mirror the controls; each is detected.

## Premises and limits

- `<MAXSTRING>` at 3,641,144 characters is an IRIS provider limit, observed on 2026.1 with this star.
- Not exercised: edge-type sequences and the next-hop lookahead (W43 observed one), inbound and both directions,
  `dstLabel`, named graphs (W43: the walk reads only the default graph), the Arno routes (library not installed).
