# W51: export_rdf_from_cypher and namespace prefixes

Selected from the unowned, unbound public methods after iteration 44: `export_rdf_from_cypher`, `register_namespace`
and `list_namespaces` (no owner statement, binding or finding), beside the modeled `export_rdf`. Source for the
predictions: SEMANTIC_LAYER.md "From a Cypher query" and "Namespace prefixes", and the API reference.

## Predictions, frozen before reading the source

| ID | Case | Reader | Predicted |
|---|---|---|---|
| C1 | a query returning `s, p, o` for two edges | answer; the file (rdflib) | `triples` 2; IRIs minted as node IDs are (`urn:ivg:` + id) |
| C2 | neighbor: three columns with other names | file | read in order as s, p, o |
| C3 | a row whose third value is a number (a property) | file | it becomes an IRI too ("each value becomes an IRI the way node IDs do") |
| C4 | a one-column query returning an IRI value and a plain id | file | `<iri> rdf:type <urn:ivg:Node>` for the IRI only |
| C5 | the same row twice | answer | not predicted with confidence (rows or distinct triples) |
| C6 | a row with a null (OPTIONAL MATCH) | file / answer | not predicted with confidence |
| C7 | `register_namespace("ex<run>", "http://example.org/<run>/")` | `list_namespaces()` on this and on a second engine | the pair, on both (stored in `rdf_namespaces`) |
| C8 | neighbor: the same prefix registered again with another URI | `list_namespaces()` | not predicted with confidence (replace or refuse) |
| C9 | an `export_rdf` Turtle file after C7 | the file's prefix declarations | `@prefix ex<run>: <http://example.org/<run>/>` |

## Outcome (observed after the freeze)

Observations: [1](cyphexport-observed-20261117T011128Z.json), [2](cyphexport-observed2-20261117T011146Z.json) (C9 with data in the namespace), then the
[binding](../../../Verus_verification/results/cypher_export/20261117T011234Z-binding/receipt.json) (AGREES with `cypher_export.rs`).

| ID | Held? | What happened |
|---|---|---|
| C1 | yes | 2 triples, `urn:ivg:` IRIs |
| C2 | yes | positional columns read in order |
| C3 | yes | the number 2011 became `<urn:ivg:2011>` |
| C4 | yes | only the IRI value got a type triple |
| C5 | (resolved) | the answer counts distinct triples (1) |
| C6 | (resolved) | a null row is skipped |
| C7 | yes | stored; a second engine sees it |
| C8 | (resolved) | re-registering replaces the IRI |
| C9 | yes, on a fair test | the first test's data did not use the namespace, and rdflib declares only used prefixes; with data in the namespace both exports declare it |

Added after reading the source (not frozen): C10, a failed query exports an empty file reported as 0 triples (new Medium
bug-plt-111); C11, a 0 value drops the row unless the columns are named s, p, o (new Low bug-plt-112). Material
prediction gained: the new owner `install.export.rdf.cypher` predicts every case.
