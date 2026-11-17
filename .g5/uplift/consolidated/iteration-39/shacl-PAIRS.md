# W45: SHACL validation over IVG's rows

Selected from the product-wide inventory after iteration 38: of 243 public methods in the API reference, 139 are never
named in the ontology and 110 of those are unbound. `validate_shacl` decides whether data conforms, has no owner, no
finding and no binding, and is documented as an ingestion gate (SEMANTIC_LAYER.md "a pattern for an ingestion step that
refuses bad data"). Provider: pySHACL 0.40.2 with rdflib 7.6.0 (installed by the pinned `[rdf]` extra).

## Predictions, frozen before reading the source (SEMANTIC_LAYER.md, API reference)

Shapes as in the doc: a `sh:NodeShape` targeting `<urn:ivg:Drug>`; IRIs per the doc's row-to-triple table.

| ID | Case | Reader | Predicted |
|---|---|---|---|
| S1 | a Drug with `approved`, and one without, shape `approved minCount 1` | `report.conforms`, `violations` | False; one violation, focus `urn:ivg:<id>`, the shape's message, severity `Violation` |
| S2 | neighbor of S1: `node_ids=[the valid drug]` | `conforms` | True ("validating only some nodes reads only their triples") |
| S3 | `sh:datatype xsd:integer` on `approved`, a drug whose `approved` is the string `"2011"` | `conforms` | True: the export rule turns text that reads as an integer into `xsd:integer`, so the string passes |
| S4 | the same node ID in the default graph (with `approved`) and in a named graph G (without) | `conforms` | True: every graph is read and both rows are the same IRI, so the union satisfies `minCount` (G's row is not checked on its own) |
| S5 | `sh:class <urn:ivg:Gene>` on `<urn:ivg:INHIBITS>`, a drug inhibiting a Gene node | `conforms` | True; with the target lacking the label, False |
| S6 | neighbor of S5: `node_ids=[the drug]` only | `conforms` | False: the target's `rdf:type` triple is not read, so `sh:class` fails although the graph is valid |

## Outcome (observed after the freeze)

[Observation](shacl-observed-20261117T004330Z.json), then the [binding](../../../Verus_verification/results/shacl_data/20261117T004553Z-binding/receipt.json) (AGREES with
`shacl_data.rs`). Every frozen prediction held (6 of 6). Two of them are defects against other owners or the guide's
own usage:

| ID | Held? | What happened |
|---|---|---|
| S1 | yes | conforms False; one violation with the shape's message, severity Violation |
| S2 | yes | True with only the valid drug listed |
| S3 | yes | a stored string "2011" passes `sh:datatype xsd:integer`, and fails `xsd:string` (S3b, added) |
| S4 | yes | True: the named-graph twin without `approved` is masked by the default-graph twin — against graph-scope (new Medium bug-str-107) |
| S5 | yes | True for a Gene target; False for a target without the label |
| S6 | yes | False with only the drug listed — the guide's ingestion pattern refuses valid data (new Low bug-str-108) |

Material prediction gained: the new owner `install.shacl` predicts all six, and says which two contradict graph scope
and the guide's pattern. Formal claims rejecting the wrong outcomes: `theorem_other_graph_masks_missing_property`
(control `data-graph-keeps-graphs-apart`) and `theorem_focus_only_breaks_class` (control `focus-loads-targets`).
