# W44: materialize and retract RDFS inference, through the edge readers

Selected from the product-wide inventory after iteration 37: `materialize_inference` and `retract_inference`
(`_engine/schema.py`) write and delete edges, have no binding, and no owner states what they derive; the only owner
text is `install.import` (refused in ledger strict mode). The register holds F-C0151 (a user edge whose qualifiers
contain a key named `inferred` is retracted; ledger-related, outside active reproduction), which this workflow does
not probe. Verus before this iteration: nothing.

## Predictions, frozen before reading the source (API reference, FHIR_GRAPH.md, USER_GUIDE.md only)

Vocabulary assumed from "RDFS entailments": `rdfs:subClassOf`, `rdf:type`, `rdfs:subPropertyOf`, `rdfs:domain`,
`rdfs:range` as edge predicates (exact spelling to be read from the source after the freeze).

| ID | Case (one graph unless said) | Reader | Predicted |
|---|---|---|---|
| I1 | A subClassOf B, B subClassOf C; x type A; `materialize_inference()` | edges out of x and A (Cypher, `^KG`) | x type B, x type C and A subClassOf C appear; the answer counts them |
| I2 | neighbor: run it a second time | the answer's counts; edges | nothing new; no duplicate edges |
| I3 | neighbor: x type B already asserted before materializing | edges after `retract_inference()` | the asserted x type B stays; only edges materialize wrote are gone |
| I4 | neighbor of I3 with the order reversed: materialize first, then a user `create_edge(x, type, B)` | edges after retract | the user's edge stays (it is an assertion) — not predicted with confidence: the docs do not say what a create of an existing derived edge does |
| I5 | the same classes in a named graph G and the default graph; materialize in G | edges in the default graph | the default graph gains nothing ("reads only that graph") |
| I6 | neighbor: retract in G | default-graph inferred edges | untouched |
| I7 | p subPropertyOf q; x p y | edges | x q y derived |
| I8 | p domain D, p range R; x p y | edges | x type D, y type R derived |
| I9 | after retract | `^KG` | the derived edges' adjacency entries are gone; asserted ones stay |

## Outcome (observed after the freeze)

[Observation](inference-observed-20261117T003415Z.json) (default and one named graph, multigraph off), then the
[binding](../../../Verus_verification/results/inference_rows/20261117T003857Z-binding/receipt.json) (fresh named graph,
AGREES with `inference_rows.rs`). Predicates are the full RDF/RDFS IRIs (read from the source after the freeze).

| ID | Held? | What happened |
|---|---|---|
| I1 | yes | x type B, x type C, A subClassOf C written, marked inferred; answer 3; Cypher sees all three types |
| I2 | yes | answer 0; no duplicates |
| I3 | yes | the asserted x type B was not rewritten and survived retract (row and `^KG`) |
| I4 | **no** | `create_edge` answered False and the row stayed inferred; retract deleted it and its `^KG` entry (new bug-str-105; question `install.inference.assert_after`) |
| I5 | yes | the named graph gained x type B; the default graph nothing |
| I6 | yes | retract in G left the default graph's rows |
| I7 | **no** | no x q y (no rdfs7; new bug-str-106) |
| I8 | yes | x type D, y type R |
| I9 | yes | inferred rows and their `^KG` entries gone; asserted rows and entries kept |

Added after reading the source (not frozen): I10, a domain type is not lifted to the domain class's superclass
(bug-str-106). Material prediction gained: the new owner `install.inference` predicts which triples are derived and
which survive retract, including the history-dependent I3/I4 pair. Formal claims that reject the wrong outcomes:
`theorem_asserted_after_is_retracted` (control `create-marks-asserted`), `theorem_no_subproperty_propagation` and
`theorem_domain_type_not_lifted` (controls `derive-rdfs7`, `derive-lifts-domain`).
