# Iteration 37: breadth-first walk readers (W43), and the HTTP client's retry binding

Before image: seal 36 `7b48ec37`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-cont-20261117-iris`.

## Why these

From the product-wide inventory after iteration 36: `Traversal.cls` (34 members, 1 bound), `TraversalBFS.cls` (23, 0)
and `host.py` (42, 0) are the largest nearly unbound subsystem with public readers (`khop`, `kg_GRAPH_WALK`), and their
owners state precise cases. Separately, `sdk.py` (43, 0) had a consequential retry decision that the playbook's
`proofs-d1f/call_l2.rs` already distinguishes (reviewed rule; the pin's behavior is control `fc1703`, live-reproduced
by the playbook arm); only its source role was missing.

## Result

Predictions frozen first ([PAIRS](traversal-PAIRS.md)); 10 of 11 held. New findings:

- **bug-str-104 (Low, new):** a walk longer than one IRIS string raises `<MAXSTRING>` and leaves its staged rows in
  `^ArnoKG("bfs_r")`; the changelog's large-answer fix covers `khop` only.
- **bug-str-103 (Low, new) and question `algorithms.op.walks.rows`:** the walk keeps one row per (hop, target).

New model [`walk_reader`](../../../Verus_verification/models/walk_reader/NOTES.md): 6 verified, 5 controls
EXPECTED_FAIL, native binding AGREES (6 cases). Owner blocks `algorithms.op.walks` and `.khop` updated.
Bound by inspection to the existing reviewed contract: `IVGClient._post` → `call_l2.rs::client_resends` and
`cypher_api._run_cypher` → `server_reruns` (pin = controls fc1703, fc1604; inherited live evidence, not re-observed).
No new prediction from that binding: `access.surfaces` and HD-1702 already state it.

## Recount ([member-delta.json](member-delta.json))

Active bindings 392 → **407**: 15 newly reached and bound (8 `TraversalBFS.cls`, 4 `host.py`, 2 `algorithms.py`,
1 `sdk.py`), 1 strengthened (`_run_cypher`), overlap 0, lost 0. Locator only (forwarders and delegates): five
`Traversal.cls` forwarders, `khop`, `kg_GRAPH_WALK_TVF`, `_call_classmethod_large`, `IVGClient.execute_cypher`.

Process notes: `run_verus.py` writes control scratch under `$RUN_DIR`, which defaulted to an older shared path for
iterations 36's and 37's first runs; those new subdirectories were moved into this run's directory and `RUN_DIR` is
now set. The evidence gate caught a `model.json` edit after a passing proof; the model was re-proved.
Correspondence: [delta from 36](correspondence-delta-from-36.json), fresh [stamp](correspondence-inputs.json).
