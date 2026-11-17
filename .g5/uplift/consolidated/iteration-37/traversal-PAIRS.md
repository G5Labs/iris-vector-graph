# W43: k-hop and graph walk through the ObjectScript traversal readers

Selected from the product-wide inventory after iteration 36: `Traversal.cls` (34 members, 1 bound) and `TraversalBFS.cls`
(23, 0) are the largest nearly unbound ObjectScript subsystem with public readers (`khop`, `kg_GRAPH_WALK`,
`kg_GRAPH_PATH`); `host.py` (42, 0) reassembles their large replies. Owners: `algorithms.op.khop`, `algorithms.op.walks`.
Verus before this iteration: no model of either; nothing distinguishes the cases below.

Iteration 37 also binds `IVGClient._post` and `_run_cypher` to the playbook's existing reviewed contract
(`proofs-d1f/call_l2.rs` `client_resends`, `server_reruns`; the pin's behavior is that family's controls fc1703 and
fc1604, live-reproduced by the playbook arm). That adds no prediction: the owner (`access.surfaces`, HD-1702) already
states it.

## Predictions, frozen before reading the traversal source (owner blocks and API reference only)

| ID | Case | Reader | Predicted |
|---|---|---|---|
| K1 | `khop(seed, hops=2)` on a chain s→a→b→c and s→d | returned nodes, edges with hop | nodes s, then a, d (hop 1), then b (hop 2), each once, in the order reached; c absent; edges s→a, s→d (hop 1), a→b (hop 2) |
| K2 | neighbor: a seed with no out-edge | same | the seed alone, no edges |
| K3 | neighbor: a missing seed | same | nothing |
| K4 | neighbor of K1: `max_nodes=2` | same | at most 2 nodes, and only edges among them |
| K5 | neighbor of K1: a diamond s→a→x, s→b→x | same | x once |
| W1 | `kg_GRAPH_WALK(s, max_depth=3)` on the chain | rows (source, type, target, hop) | rows s→a (1), s→d (1), a→b (2), b→c (3); outbound only |
| W2 | neighbor: edge types [T1, T2] on a chain whose hops alternate T1, T2, T2 | rows | hop 1 follows T1, hops 2 and 3 follow T2 (the last type repeats) |
| W3 | neighbor: `max_results=2` | rows | at most 2 rows |
| W4 | neighbor: the same edges in a named graph only | rows | the walk reads the default graph (working assumption), so nothing from the named graph |
| P1 | `kg_GRAPH_PATH(s, T1, T2)` | rows | one row per step of each two-hop path s -T1-> m -T2-> e |
| L1 | a walk whose answer is longer than an IRIS string (a star with tens of thousands of edges, `max_depth=1`, a large `max_results`) | rows | the same rows as the definition, every edge once (the reply is reassembled from chunks) |

## Outcome (observed after the freeze)

[Observation](traversal-observed-20261117T002418Z.json), then the
[binding](../../../Verus_verification/results/walk_reader/20261117T002834Z-binding/receipt.json) (AGREES with `walk_reader.rs`).

| ID | Held? | What happened |
|---|---|---|
| K1 | yes | nodes s, a, d, b; edges s→a, s→d (1), a→b (2) |
| K2 | yes | the seed alone |
| K3 | yes | nothing |
| K4 | yes | s, a and the one edge between them |
| K5 | yes | x once; both edges into x listed |
| W1 | yes | s→a, s→d (1), a→b (2), b→c (3) |
| W2 | yes | T1 at hop 1, T2 at hops 2 and 3; w2 -T1-> wy not followed at hop 2 |
| W3 | yes | two rows |
| W4 | yes | nothing (the walk reads the default graph; `khop` likewise answers only the seed, which exists in the named graph) |
| P1 | yes | one row per step of the one path |
| L1 | **no** | the walk raised `<MAXSTRING>` and left its stage in `^ArnoKG("bfs_r")` (new bug-str-104); `khop` over the same 40,000-edge star answered |

Added after reading the source (not frozen, so not counted as predictions): W5 diamond and W6 two types to one target.
The walk returned one row per (hop, target) (new bug-str-103, with the question `algorithms.op.walks.rows`), while
`khop` listed every edge (K6). Cross and back edges are listed (binding), so the walk is neither an edge list nor a
one-row-per-node tree.

Material prediction gained: from `algorithms.op.walks` a reader can now predict which edges a walk lists and that an
over-long walk fails while an over-long k-hop answers. Formal claims that reject the wrong outcome:
`theorem_same_hop_target_collapses` (with control `stage-keeps-every-edge`) and
`theorem_walk_overflow_raises_and_leaves_stage` (control `walk-has-stream`).
