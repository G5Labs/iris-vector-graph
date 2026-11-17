# Iteration 44: PROV-O export (W50)

Before image: seal 43 `43f51925`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-cont-20261117-iris`; the
fixture's default graph now holds a 40,000-edge temporal history (W50's load), which later bindings rely on as a premise.

## Result

Predictions frozen first from SEMANTIC_LAYER.md ([PAIRS](prov-PAIRS.md)): 7 of 8 held. New: bug-plt-110 (Medium,
`prov_as_dict` and `prov_export_from_cypher` fail on any large default history), bug-plt-109 (Low, an over-large window
raises where the guide promises an empty file). New owner `install.export.prov`; new model
[`prov_window`](../../../Verus_verification/models/prov_window/NOTES.md): 3 verified, 4 controls EXPECTED_FAIL, native
binding AGREES. The two findings were first numbered 110/111 in the working tree and renumbered 109/110 before commit.

## Recount ([member-delta.json](member-delta.json))

Active bindings 433 → **439**: 6 newly reached and bound (`prov.py`), lost 0. Correspondence: [delta from
43](correspondence-delta-from-43.json), fresh [stamp](correspondence-inputs.json).
