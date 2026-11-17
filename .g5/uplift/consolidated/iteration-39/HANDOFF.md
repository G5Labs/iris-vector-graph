# Iteration 39: SHACL validation (W45)

Before image: seal 38 `50f9b680`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-cont-20261117-iris`;
provider pySHACL 0.40.2 / rdflib 7.6.0 from the pinned `[rdf]` extra.

## Why this workflow

A cross-check of the 243 public methods in the API reference against the ontology found 139 never named there and 110
of those unbound. `validate_shacl` decides conformance, is documented as an ingestion gate, and had no owner, finding or
binding.

## Result

Predictions frozen first ([PAIRS](shacl-PAIRS.md)); 6 of 6 held, two of them contradicting other authorities:

- **bug-str-107 (Medium, new):** one node ID in two graphs is validated as one node, so an invalid named-graph node
  passes on the strength of a valid default-graph node (against graph scope).
- **bug-str-108 (Low, new):** validating only new node IDs, as the guide's ingestion pattern does, refuses valid data
  whose shape checks an edge's target class.

New owner `install.shacl`; new model [`shacl_data`](../../../Verus_verification/models/shacl_data/NOTES.md): 4 verified,
4 controls EXPECTED_FAIL, native binding AGREES.

## Recount ([member-delta.json](member-delta.json))

Active bindings 409 → **412**: 3 newly reached and bound (`validate_shacl`, `_parse_shacl_report`,
`ValidationReport.__bool__`), 2 strengthened (`_build_rdflib_graph`, `_mint_iri`), overlap 0, lost 0;
`_load_shapes_graph` is a locator only. Correspondence: [delta from 38](correspondence-delta-from-38.json), fresh
[stamp](correspondence-inputs.json).
