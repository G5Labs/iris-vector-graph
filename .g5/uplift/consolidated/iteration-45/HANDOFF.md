# Iteration 45: RDF export from Cypher and namespace prefixes (W51)

Before image: seal 44 `99bef4d2`. Product `3eaa79cf` unchanged. Native evidence only from `ivg-cont-20261117-iris`.

## Result

Predictions frozen first from SEMANTIC_LAYER.md ([PAIRS](cyphexport-PAIRS.md)): every confident prediction held (C9
after a fairer test). From source reading: bug-plt-111 (Medium, a failed query exports an empty file reported as 0
triples) and bug-plt-112 (Low, a 0 value drops a row unless the columns are named). New owner
`install.export.rdf.cypher`; new model [`cypher_export`](../../../Verus_verification/models/cypher_export/NOTES.md):
3 verified, 4 controls EXPECTED_FAIL, native binding AGREES.

## Recount ([member-delta.json](member-delta.json))

Active bindings 439 → **441**: 2 newly reached and bound; `register_namespace` and `list_namespaces` are locators
(observed, no formal claim). Lost 0. Correspondence: [delta from 44](correspondence-delta-from-44.json), fresh
[stamp](correspondence-inputs.json).
