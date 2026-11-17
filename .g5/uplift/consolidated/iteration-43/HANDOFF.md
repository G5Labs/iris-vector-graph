# Iteration 43: bulk embedding (W49)

Before image: seal 42 `52d61aed`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-cont-20261117-iris`.

## Why this workflow

From the unowned, unbound public methods: `embed_nodes`, `get_unembedded_nodes`, `embedding_count` (the documented bulk
vector writer and its readers) had no owner statement, binding or finding.

## Result

Predictions frozen first ([PAIRS](embed-nodes-PAIRS.md)): the confident ones held except E1's exclusion. New, both Low:
bug-srch-105 (an exclusion glob containing `_` or `%` excludes nothing: backslash escapes without `ESCAPE`),
bug-srch-106 (a named-graph embed selects by a label from another graph). New owner `search.embedding.bulk`; new model
[`embed_selection`](../../../Verus_verification/models/embed_selection/NOTES.md): 4 verified, 4 controls EXPECTED_FAIL,
native binding AGREES (7 cases; an earlier DISAGREES run was a harness error and is annotated).

## Recount ([member-delta.json](member-delta.json))

Active bindings 428 → **433**: 5 newly reached and bound, lost 0. Correspondence: [delta from
42](correspondence-delta-from-42.json), fresh [stamp](correspondence-inputs.json).
