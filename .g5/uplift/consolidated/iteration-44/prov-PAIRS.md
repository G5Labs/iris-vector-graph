# W50: PROV-O export of temporal edges

Selected from the unowned, unbound public methods after iteration 43: `prov_export`, `prov_as_dict` and
`prov_export_from_cypher` (`_engine/prov.py`) read the temporal index and publish it; no owner statement names them and
nothing binds them. Source for the predictions: SEMANTIC_LAYER.md "PROV-O provenance from temporal edges" only.

## Predictions, frozen before reading the source

| ID | Case | Reader | Predicted |
|---|---|---|---|
| P1 | two temporal edges s→A at t1, s→B at t2 | `prov_export(ttl)` answer; the file (rdflib) | activities 2, entities 3; one `prov:startedAtTime` per edge, UTC; no `prov:endedAtTime` |
| P2 | neighbor: `ts_start=t2` (inclusive) | answer | activities 1, entities 2 |
| P3 | neighbor: `ts_end=t1` (inclusive) | answer | activities 1 |
| P4 | `prov_as_dict("s|p|A|t1")` and an ID that is not there | dict; exception | the documented dict; `KeyError` |
| P5 | the same edge pattern only in a named graph | `prov_export` | not exported (default graph only) |
| P6 | `prov_export_from_cypher` returning node B | answer | activities 1 (the edge ending at B) |
| P7 | the same (s, p, o, t) written twice | answer | one activity |
| P8 | a window of more edges than one IRIS string can hold (about 40,000 in one bucket range) | answer and file | documented limit: a warning and an empty file, not an error |

## Outcome (observed after the freeze)

[Observation](prov-observed-20261117T010711Z.json) (files under the run directory), then the
[binding](../../../Verus_verification/results/prov_window/20261117T011005Z-binding/receipt.json) (AGREES with `prov_window.rs`).

| ID | Held? | What happened |
|---|---|---|
| P1 | yes | activities 2, entities 3; two UTC start times; no end time |
| P2 | yes | `ts_start` inclusive: 1 activity |
| P3 | yes | `ts_end` inclusive: 1 activity |
| P4 | yes | the documented dict; `KeyError` for a missing ID |
| P5 | yes | the named graph's edge is not exported |
| P6 | yes | 1 activity (the edge ending at B) |
| P7 | yes | one activity for a repeated (s, p, o, t) |
| P8 | **no** | a 40,000-edge window raises `RuntimeError: <MAXSTRING>…`; no file (new Low bug-plt-109, the guide is wrong) |

Added after reading the source (not frozen): P9, once the default graph's history passes the string limit,
`prov_as_dict` fails for any edge (new Medium bug-plt-110; `prov_export_from_cypher` shares the read). Material
prediction gained: the new owner `install.export.prov` predicts all nine.
