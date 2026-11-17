# Iteration 38: RDFS inference (W44)

Before image: seal 37 `30b190eb`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-cont-20261117-iris`.

## Why this workflow

From the product-wide inventory's unbound public methods: `materialize_inference` and `retract_inference` write and
delete edges, had no binding and no owner of what they derive (only strict-mode refusal in `install.import`).

## Result

Predictions frozen first ([PAIRS](inference-PAIRS.md)); 7 of 9 held.

- **bug-str-105 (Medium, new) and question `install.inference.assert_after`:** an edge the user creates after the same
  triple was inferred stays marked inferred and is deleted by retract; the same graph asserted in the other order keeps it.
- **bug-str-106 (Low, new):** no rdfs7 and no lifting of domain/range types, against the reference's "RDFS entailments".

New owner block `install.inference` (recovered intent, as built, with the open question). New model
[`inference_rows`](../../../Verus_verification/models/inference_rows/NOTES.md): 8 verified, 5 controls EXPECTED_FAIL,
native binding AGREES.

## Recount ([member-delta.json](member-delta.json))

Active bindings 407 → **409**: 2 newly reached and bound (`materialize_inference`, `retract_inference`), 1
strengthened (`NodesEdgesMixin.create_edge`, competing-writer claim), overlap 0, lost 0.
Correspondence: [delta from 37](correspondence-delta-from-37.json), fresh [stamp](correspondence-inputs.json).
