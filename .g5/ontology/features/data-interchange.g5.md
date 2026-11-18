# Import, validate and export graph data

Find the rules for reading and writing graph files, running inference, and checking a graph with SHACL. To move data through a namespace snapshot or bulk loader, see [snapshots and bulk loading](../operations/snapshots-and-bulk-load.g5.md).

## Import triples and graph records

<a id="install.import"></a>
[D · install.import]

Imports write as they go. `load_networkx`, `import_graph_ndjson` and `load_obo` write one node or relationship at a time, and `import_rdf` commits one batch at a time, so a failure keeps what was already written. Every import, and materializing or retracting inference, is refused in ledger strict mode.

<a id="install.import.rdf"></a>
[D · install.import.rdf]

An RDF import writes each statement into the graph its quad names, or else into the graph the caller gives. A statement whose object is an IRI or blank node becomes an edge, and one whose object is a literal becomes a property of the subject under the predicate's local name.
- Two predicates with the same local name write one property, so one of the two literals is lost.
- Today a literal is stored as its text without its datatype, so an imported integer reads back as text ([finding](../../Verus_verification/bugs_issues.md#bug-str-109)).
- Today a property already set is not changed by a later import, and the import counts it as not written ([finding](../../Verus_verification/bugs_issues.md#bug-str-110)).
- Today inference requested with an import runs on the graph the caller gives, not on the graphs the quads went to ([finding](../../Verus_verification/bugs_issues.md#bug-str-111)).

<a id="install.import.ndjson"></a>
[D · install.import.ndjson]

An NDJSON import ignores blank lines; logs and counts malformed JSON, non-object JSON, unknown kinds, nodes without IDs and edges without all endpoints and predicate as skipped; and continues to later lines. A writer exception stops the call and returns no counts; without a caller transaction, earlier successful writes remain.

- `kind: node|edge|temporal_edge` selects a record. Without a kind, the ledger export's `type: node|rel` selects nodes or edges, with `props` or `s/p/o/quals` respectively. An explicit kind takes precedence over `type`.
- Node and edge counters count processed lines, even when `create_node` or `create_edge` returns False for an existing item. Duplicate node lines leave the existing node's properties unchanged; `upsert_nodes` controls creation of temporal endpoints, not updating duplicate node records.
- Node lines use the caller's graph (default if omitted). Edge lines use the caller's graph if supplied, otherwise the line's graph; an explicitly empty caller graph overrides a named line graph. Temporal batches and any endpoints they create use the default graph even when the caller supplies a graph.
- Temporal lines buffer until `batch_size` or end of file. Their counter advances by the flushed batch length, independently of the writer's return count; an exception prevents that increment and prevents the final pending flush. These counters do not establish rows created or atomicity of a failed temporal batch.

<a id="install.inference"></a>
[D · install.inference]

Materializing inference in one graph adds the RDFS consequences of that graph's asserted edges as new edges marked inferred. Retracting inference removes that graph's inferred edges and their adjacency entries. Neither call touches another graph.
- It derives subclass and subproperty chains, the types an asserted type implies through its superclasses, and the types a property's domain and range give its subjects and objects.
- It does not copy an edge to a property's superproperty, and it does not lift a type that came from a domain or range to that class's superclasses ([finding](../../Verus_verification/bugs_issues.md#bug-str-106)).
- It reads only asserted edges, so a second run adds nothing. A triple that already has an edge is not written again, so an edge asserted first stays asserted and survives retracting.
- Creating an edge whose triple was already inferred answers False and leaves it marked inferred, so retracting deletes it ([open question](../../Verus_verification/open_questions.md#install.inference.assert_after)).

## Export graph data

<a id="install.export.ndjson"></a>
[D · install.export.ndjson]

`export_graph_ndjson` writes the default graph's node records, then its non-temporal structural edge records, in the format `import_graph_ndjson` reads. Its `nodes` and `edges` answers count lines written; parallel structural edges each have a line.

- A node record uses the public [node-read projection](graph-structure.g5.md#structure.node.read), including its property aliases and value conversions. Its properties omit only the structural `id` and `labels` fields; this does not promise an inverse of stored property keys.
- Named graphs and marked temporal rows are excluded. Import-format compatibility does not promise that a later import preserves physical edge IDs, multiplicity or every stored type; those depend on the import writers.

<a id="install.export.rdf.scope"></a>
[D · install.export.rdf.scope]

`export_rdf` writes labels, properties and outgoing edges from every graph when `graph_id` is None, only the default graph when it is empty, and only the named graph otherwise. Nonempty node and label filters narrow that selection; a label must belong to the source node in the row's own graph.

- Empty filter collections do not narrow the export. A label filter writes the matching labels, the selected source nodes' properties and their outgoing edges; it does not pull in a target's other rows.
- A physical node without any selected label, property or outgoing edge contributes no RDF subject. Context-aware formats keep each generated triple in its row's graph.

<a id="install.export.rdf.content"></a>
[D · install.export.rdf.content]

A selected label becomes an `rdf:type` triple, a non-null property becomes a literal triple, and an edge becomes an IRI-object triple. Each physical edge with a nonempty qualifier dictionary also gets its own statement and reifier blank nodes; the `inferred` qualifier is omitted, even when it is the only qualifier.

- Node IDs, labels and edge predicates use `base_uri` unless they already start with `http://`, `https://`, `urn:` or `ftp://`. Property keys pass through as IRIs for the first three prefixes; other keys use `urn:ivg:prop/`. Qualifier predicates use `urn:ivg:qualifier/`.
- Property text tries a canonical integer spelling first, then a float as `xsd:decimal`, then a case-insensitive boolean, then plain text. The current qualifier path falls back to plain text when that literal is falsey, so zero and false qualifiers can differ from the same property value. This describes the current projection; the intended qualifier exception is not settled by the general literal description.
- The envelope has statement subject, predicate and object triples, plus a reifier-to-statement `rdf:reifies` triple. All of these and the qualifier triples use the edge's context; equal unqualified triples can collapse while separate qualified rows retain separate envelopes.

<a id="install.export.rdf.report"></a>
[D · install.export.rdf.report]

After serialization succeeds, RDF export reports the number of distinct triples across the union of contexts, the number of distinct subjects including blank nodes, and the number of those triples with an IRI object whose predicate is not `rdf:type`. These counts include qualifier envelopes and are not physical node or edge counts; the same triple in two contexts can be two serialized quads but one reported triple.

- The format argument overrides extension inference. N-Quads and TriG preserve graph contexts; flat formats do not establish a context-preserving export, and no successful answer promises file atomicity on an earlier error.

<a id="install.export.prov"></a>
[D · install.export.prov]

The PROV-O export publishes the default graph's temporal edges, one activity per distinct edge and time, with its source, target and start time. A window's two ends are both included, and a named graph's temporal edges are not exported.
- A single-edge lookup and the export for the nodes of a Cypher query read the default graph's whole temporal history.
- Today a read of more edges than one IRIS string holds (about 35,000) raises an error. So the whole-history calls fail on any large history, even for one small edge ([finding](../../Verus_verification/bugs_issues.md#bug-plt-110)), and an over-large window raises rather than exporting an empty file as the guide says ([finding](../../Verus_verification/bugs_issues.md#bug-plt-109)).

<a id="install.export.rdf.cypher"></a>
[D · install.export.rdf.cypher]

An export from a Cypher query writes one triple per distinct result row, its three values made into IRIs as node IDs are, numbers included. A row with a null is skipped, and a one-column row adds a type triple only for a value that is already an IRI.
- Registered namespace prefixes are stored for the namespace, a second registration of a prefix replaces its IRI, and Turtle and JSON-LD exports declare each registered prefix their triples use.
- Today a row whose value is 0, false or empty is skipped unless the columns are named `s`, `p` and `o` ([finding](../../Verus_verification/bugs_issues.md#bug-plt-112)), and a query that fails exports an empty file reported as 0 triples ([finding](../../Verus_verification/bugs_issues.md#bug-plt-111)).

## Validating graph data with SHACL

<a id="install.shacl"></a>
[D · install.shacl]

SHACL validation checks the labels, properties and edges of every graph, or of listed nodes only, against SHACL Core shapes, without inference, and writes nothing.
- It sees the triples an RDF export writes. Node IDs, labels and edge types become IRIs by the export's rule, and property text that reads as a number or a boolean is typed as one, so a stored string "2011" is an integer.
- Today every graph's rows for one node ID are checked as one node, so a node passes a rule on the strength of the same ID in another graph ([finding](../../Verus_verification/bugs_issues.md#bug-str-107)).
- With listed nodes only their own rows are read, so a rule about an edge's target fails unless the target is listed too ([finding](../../Verus_verification/bugs_issues.md#bug-str-108)).

## Metadata

### install.import

- Children: [RDF](#install.import.rdf), [NDJSON](#install.import.ndjson), [inference](#install.inference)

- Sources: [snapshot.py load_networkx](../../../iris_vector_graph/_engine/snapshot.py#L446-L556), [import_rdf](../../../iris_vector_graph/_engine/snapshot.py#L557-L720), [import_graph_ndjson](../../../iris_vector_graph/_engine/snapshot.py#L1727-L1856), [load_obo](../../../iris_vector_graph/_engine/snapshot.py#L1694-L1726), [materialize_inference](../../../iris_vector_graph/_engine/schema.py#L2966), [ledger strict list](ledger.g5.md#ledger.strict), [operations inventory G7](../../uplift/ivg-verus-initial/intent/operations.md#L150-L158)
- agent
- data-integrity, operations

Added by review round 3 R3-reader M23 (the stage-A reconstruction check items 3, 4 and 7 had raised it). `import_rdf`'s docstring says it "commits per batch"; inside a caller's transaction each batch is an IVG level nested in it, and a non-indexed install refuses the caller's transaction. Whether re-running an import after a failure finishes it cleanly was not checked. The inference commit boundary was not traced. Not modelled and not observed natively.

### install.import.rdf

- Sources: [SEMANTIC_LAYER.md Importing RDF and Named graphs](../../../docs/SEMANTIC_LAYER.md#L56-L66); [API_REFERENCE import_rdf](../../../docs/API_REFERENCE.md); [`SnapshotMixin.import_rdf`](../../../iris_vector_graph/_engine/snapshot.py#L557), [`_literal_key`](../../../iris_vector_graph/_engine/snapshot.py#L381-L384)
- Expands: [imports](#install.import)
- Verus: active: [`rdf_import.rs`](../../Verus_verification/models/rdf_import/NOTES.md) `theorem_context_wins`, `theorem_local_name_collision`; as-built departures `theorem_datatype_dropped`, `theorem_reimport_keeps_old_value`, `theorem_infer_ignores_contexts`.
- agent
- data-integrity, user-facing-behavior

Recovered in iteration 41 from the semantic-layer guide, the docstring and observation ([W47](../../uplift/consolidated/iteration-41/rdfimport-PAIRS.md)). Not exercised: TriG, JSON-LD, language tags, blank-node identity across files, batch boundaries.

Findings: [import_rdf drops a literal's datatype](../../Verus_verification/bugs_issues.md#bug-str-109); [Re-importing RDF never updates a property](../../Verus_verification/bugs_issues.md#bug-str-110); [import_rdf(infer=True) infers in the graph argument](../../Verus_verification/bugs_issues.md#bug-str-111)

### install.import.ndjson

- design-verified
- Sources: [`SnapshotMixin.import_graph_ndjson`](../../../iris_vector_graph/_engine/snapshot.py#L1727-L1855), [`NodesEdgesMixin.create_node`](../../../iris_vector_graph/_engine/nodes_edges.py#L968-L1107), [unit tests](../../../tests/unit/test_edgeprop_ndjson.py#L45-L95)
- Playbook: [WRT-B7.86](../../../experiment/playbook-completion/ontology/03-writes.md#L221), [WRT-T7.87](../../../experiment/playbook-completion/ontology/03-writes.md#L222), [WRT-B2.80](../../../experiment/playbook-completion/ontology/03-writes.md#L92)
- Verus: [ndjson_import](../../Verus_verification/models/ndjson_import/NOTES.md), as-built node admission, width refusal, prefix preservation and duplicate counts. Edge routing and temporal batching are unit observations only and remain formal gaps; parser behavior is a scoped boundary assumption.
- agent
- user-facing-behavior, data-integrity
- Expands: [imports](#install.import)

State machines: [ndjson export](../../Verus_verification/models/ndjson_export/manifest.json), [ndjson import](../../Verus_verification/models/ndjson_import/manifest.json)

### install.inference

- Sources: [API_REFERENCE materialize_inference, retract_inference](../../../docs/API_REFERENCE.md); [FHIR_GRAPH.md](../../../docs/FHIR_GRAPH.md); [`SchemaMixin.materialize_inference`](../../../iris_vector_graph/_engine/schema.py#L2966-L3183), [`SchemaMixin.retract_inference`](../../../iris_vector_graph/_engine/schema.py#L3186-L3260), [`NodesEdgesMixin.create_edge`](../../../iris_vector_graph/_engine/nodes_edges.py#L1151)
- Expands: [imports](#install.import)
- Verus: active: [`inference_rows.rs`](../../Verus_verification/models/inference_rows/NOTES.md) `theorem_retract_keeps_asserted`, `theorem_rerun_adds_nothing`, `theorem_asserted_first_survives`; as-built departures `theorem_asserted_after_is_retracted`, `theorem_no_subproperty_propagation`, `theorem_domain_type_not_lifted`.
- agent
- data-integrity, user-facing-behavior

Recovered in iteration 38 from the API reference and observation ([W44](../../uplift/consolidated/iteration-38/inference-PAIRS.md)); no owner statement existed. OWL rules (`rules="owl"`), multigraph mode and the ledger-related retraction case F-C0151 were not exercised.

Findings: [retract_inference deletes an edge the user created after the same triple was inferred](../../Verus_verification/bugs_issues.md#bug-str-105); [materialize_inference derives less than the RDFS entailments the API reference promises](../../Verus_verification/bugs_issues.md#bug-str-106); [import_rdf(infer=True) infers in the graph argument](../../Verus_verification/bugs_issues.md#bug-str-111)

Open questions: [Should creating an edge that inference already wrote make it an asserted edge?](../../Verus_verification/open_questions.md#install.inference.assert_after)

### install.export.ndjson

- design-verified

- Sources: [User Guide export](../../../docs/USER_GUIDE.md#L1170-L1181), [API reference](../../../docs/API_REFERENCE.md#L2163-L2169), [NDJSON format](../../../docs/setup/DATA_FORMATS.md#3-ndjson), [`SnapshotMixin.export_graph_ndjson`](../../../iris_vector_graph/_engine/snapshot.py#L1857-L1908)
- Tests (live): [R088 default/named/temporal export](../../../tests/e2e/test_460_export_graph_ndjson_e2e.py); existing [import unit tests](../../../tests/unit/test_edgeprop_ndjson.py)
- Related: [node reads](graph-structure.g5.md#structure.node.read), [How should flat node reads preserve colliding property aliases?](../../Verus_verification/open_questions.md#q-iter-001), [NDJSON admission](#install.import.ndjson)
- Evidence: [source-first root contrasts](../../uplift/consolidated/iteration-14/root-export-PAIRS.md), [sealed13 full-record survey](../../uplift/consolidated/iteration-13/next-records-survey.md)
- Verus: [ndjson_export.rs](../../Verus_verification/models/ndjson_export/ndjson_export.rs) `theorem_complete_export_line_sequence_and_counts`, `theorem_default_census_derived`, `theorem_raw_node_event_content`, `theorem_edge_census_derived`, `theorem_edge_qualifier_zero_not_omitted` and `theorem_actual_generated_export_to_import_callbacks`, with final-file witnesses; [scope and provider limits](../../Verus_verification/models/ndjson_export/NOTES.md)
- agent
- user-facing-behavior, data-integrity

Exporting writes only the default graph: first one node line for each node whose node row has the empty graph name, in node-ID order, then one edge line for each default-graph edge row, in edge-ID order. It returns `nodes` and `edges` equal to the lines of each kind it wrote.

- A node line is written even when the node has no labels or properties. A node that exists only in a named graph gets no line, and its named-graph labels and properties do not enter a default node's line.
- A node line carries every default-graph label and the properties as the node reader reports them, including the [How should flat node reads preserve colliding property aliases?](../../Verus_verification/open_questions.md#q-iter-001): a stored property named `id` appears as `p_id`. When both `id` and `p_id` are stored, only the value delivered last survives.
- Every physical default-graph edge row is its own line, so two parallel rows with the same source, predicate and target give two lines. Temporal-marked rows (qualifiers starting `{"temporal"`) and named-graph rows are not written.
- A non-empty qualifier object is copied, including `{"q": 0}`; an absent or empty qualifier is left out.
- Reading the file with [NDJSON import](#install.import.ndjson) passes each line's labels, properties, graph and qualifiers to the create calls and counts the lines read. That is argument agreement, not a storage round trip: alias and value normalization mean a re-import need not restore the original rows.

This recovers ordinary export behavior; it is not a new product requirement. The file claim assumes a stable SQL view, ordinary SQL ordering and successful JSON and file writes; failure, partial-file and concurrent-writer behavior are not covered.

State machines: [ndjson export](../../Verus_verification/models/ndjson_export/manifest.json)

### install.export.rdf.scope

- design-verified

- Sources: [Semantic Layer selection](../../../docs/SEMANTIC_LAYER.md#L95-L115), [API reference](../../../docs/API_REFERENCE.md#L2253-L2274), [`_build_rdflib_graph`](../../../iris_vector_graph/_engine/_rdf_utils.py#L102-L294)
- Tests (live): [R099 label filtering](../../../tests/e2e/test_460_rdf_export_label_filter_e2e.py), [R100 graph contexts](../../../tests/e2e/test_460_rdf_export_nquads_graphs_e2e.py), [graph scope unit tests](../../../tests/unit/test_230_rdf_export_scope.py)
- Related: [graph scope](../concepts/graph-scope.g5.md#graph.default), [content](#install.export.rdf.content), [report](#install.export.rdf.report)
- Evidence: [source-first root contrasts](../../uplift/consolidated/iteration-14/root-export-PAIRS.md), [sealed13 ordinary RDF survey](../../uplift/consolidated/iteration-13/next-reporting-survey.md)
- Verus: [rdf_reporting.rs](../../Verus_verification/models/rdf_reporting/rdf_reporting.rs) `theorem_graph_filter_is_request_value`, `theorem_empty_filters_are_unfiltered`, `theorem_label_selection_is_raw`, `theorem_wrong_graph_membership_is_excluded`, `theorem_source_not_target_selects` and `theorem_outside_requested_ids_emits_nothing`; [scope and provider limits](../../Verus_verification/models/rdf_reporting/NOTES.md)
- agent
- user-facing-behavior, data-integrity

RDF export selects rows by graph, node ID and label before building any triple.

- `graph_id=None` exports every graph; `""` exports the default graph, including rows whose graph is SQL NULL; any other value exports only that named graph.
- An empty or omitted ID list or label list does not filter. A non-empty ID list selects label, property and edge rows by their subject (the edge's source, not its target).
- With a label filter, only matching label rows become `rdf:type` triples. A property or edge row is kept only when its subject carries a matching label in the row's own graph; a label on the edge's target, or on the same ID in another graph, does not qualify.

The label projection and own-graph membership are explicit source and regression behavior; no policy about exporting all labels of a selected node is inferred. SQL equality, nullable-graph normalization and a stable relational view are correspondence conditions.

State machines: [rdf reporting](../../Verus_verification/models/rdf_reporting/manifest.json)

### install.export.rdf.content

- design-verified

- Sources: [Semantic Layer row/term/qualifier rules](../../../docs/SEMANTIC_LAYER.md#L39-L65), [`_mint_iri`, `graph_iri`, `_to_literal`, `_build_rdflib_graph`](../../../iris_vector_graph/_engine/_rdf_utils.py#L29-L294)
- Tests (live): [literal/qualifier unit tests](../../../tests/unit/test_rdf_export.py), [R100 generated context contents](../../../tests/e2e/test_460_rdf_export_nquads_graphs_e2e.py), [R122 named-graph IRIs](../../../tests/e2e/test_460_rdf_graph_id_not_an_iri_e2e.py)
- Evidence: [sealed13 typed literal and actual file observations](../../uplift/consolidated/iteration-13/next-reporting-sanity.json)
- Related: [scope](#install.export.rdf.scope), [report](#install.export.rdf.report)
- Verus: [rdf_reporting.rs](../../Verus_verification/models/rdf_reporting/rdf_reporting.rs) `theorem_raw_rows_generate_exactly_the_quad_set`, `theorem_two_raw_digits_determine_value`, `theorem_dyadic_is_derived`, `theorem_property_null_is_omitted`, `theorem_node_property_prefixes_differ`, `theorem_original_object_decides_envelope`, `theorem_inferred_only_still_has_envelope`, `theorem_falsey_qualifier_fallback`, `theorem_unqualified_parallel_rows_collapse` and `theorem_selected_qualified_parallel_rows_keep_global_blanks`; [scope and provider limits](../../Verus_verification/models/rdf_reporting/NOTES.md)
- agent
- user-facing-behavior, data-integrity

Each selected row becomes triples in its graph's context: the default graph, or the named graph's IRI.

- A label row becomes an `rdf:type` triple. A property row with a NULL value emits nothing. Otherwise its value is typed: canonical integer text (`7`) becomes `xsd:integer`; other number text (`007`, `2.5`) becomes `xsd:decimal`; `true`/`false` in any case become booleans; anything else is a plain string.
- Node IDs, labels and edge predicates starting `http://`, `https://`, `urn:` or `ftp://` are used as IRIs unchanged; other values get the base prefix. Property keys pass through only for `http://`, `https://` and `urn:`; any other key, including `ftp://`, becomes `urn:ivg:prop/<key>` whatever the base prefix.
- Each edge row adds its subject–predicate–object triple. When its qualifier text decodes to a non-empty object, the row also gets its own fresh statement and reifier blank nodes: four envelope triples, then one `urn:ivg:qualifier/<key>` triple per key except `inferred`. An object holding only `inferred` still gets the envelope; an empty or absent qualifier gets none.
- A qualifier value that would become a false literal (`0`, JSON `false`) is written as plain text (`"0"`, `"False"`), while the same value as a property keeps its type.
- Two unqualified parallel rows give one triple; two qualified parallel rows keep separate blank nodes.

The public literal description does not settle the false/zero qualifier exception, so this as-built behavior is not intended-policy approval. Graph-IRI encoding, wider numeric and JSON text, and rdflib's term, blank-node and serializer behavior are named provider conditions.

State machines: [rdf reporting](../../Verus_verification/models/rdf_reporting/manifest.json)

### install.export.rdf.report

- design-verified

- Sources: [Semantic Layer metrics and formats](../../../docs/SEMANTIC_LAYER.md#L67-L93), [`RdfExportMixin.export_rdf`](../../../iris_vector_graph/_engine/rdf_export.py#L96-L157), [format inference](../../../iris_vector_graph/_engine/_rdf_utils.py#L56-L69)
- Evidence: [sealed13 ordinary union/quad contrast](../../uplift/consolidated/iteration-13/next-reporting-survey.md), [source-first root contrasts](../../uplift/consolidated/iteration-14/root-export-PAIRS.md)
- Related: [content](#install.export.rdf.content)
- Verus: [rdf_reporting.rs](../../Verus_verification/models/rdf_reporting/rdf_reporting.rs) `theorem_raw_rows_to_final_report`, `theorem_summary_reads_union_not_rows`, `theorem_summary_two_contexts_is_one_triple`, `theorem_summary_counts_subjects_not_objects` and `theorem_non_type_uri_count_rule`; [scope and provider limits](../../Verus_verification/models/rdf_reporting/NOTES.md)
- agent
- user-facing-behavior, data-integrity

The returned counts read the generated triples merged across contexts, not the rows or the lines in the file.

- `triples` counts distinct subject–predicate–object triples, so the same triple in two named graphs counts once even though N-Quads writes two lines.
- `nodes` counts distinct subjects, including the blank statement and reifier nodes of qualified edges; a node that appears only as an object is not counted.
- `edges` counts distinct triples whose object is an IRI and whose predicate is not `rdf:type`. This includes the IRI-valued envelope triples of qualified edges.

This settles the docs' "counts what was written" wording as a union reader without promising equal serialized line counts. Namespace binding, third-party serialization and parsing, provider failures and cross-read consistency remain qualified; no whole-serializer or failed-file guarantee follows.

State machines: [rdf reporting](../../Verus_verification/models/rdf_reporting/manifest.json)

### install.export.prov

- Sources: [SEMANTIC_LAYER.md PROV-O](../../../docs/SEMANTIC_LAYER.md); [API_REFERENCE prov_export, prov_as_dict, prov_export_from_cypher](../../../docs/API_REFERENCE.md); [`ProvMixin`](../../../iris_vector_graph/_engine/prov.py#L83-L219)
- Verus: active: [`prov_window.rs`](../../Verus_verification/models/prov_window/NOTES.md) `theorem_bounds_inclusive`; as-built departures `theorem_large_window_raises`, `theorem_as_dict_fails_on_large_history`.
- agent
- user-facing-behavior

Recovered in iteration 44 from the semantic-layer guide and observation ([W50](../../uplift/consolidated/iteration-44/prov-PAIRS.md)).

Findings: [prov_as_dict and prov_export_from_cypher fail once the history is large](../../Verus_verification/bugs_issues.md#bug-plt-110); [The guide says an over-large PROV window exports an empty file](../../Verus_verification/bugs_issues.md#bug-plt-109)

### install.export.rdf.cypher

- Sources: [SEMANTIC_LAYER.md From a Cypher query, Namespace prefixes](../../../docs/SEMANTIC_LAYER.md#L112-L137); [`RdfExportMixin.export_rdf_from_cypher`](../../../iris_vector_graph/_engine/rdf_export.py#L159), [`_project_row_as_rdf`](../../../iris_vector_graph/_engine/rdf_export.py#L212), [`register_namespace`](../../../iris_vector_graph/_engine/rdf_export.py#L53-L76)
- Verus: active: [`cypher_export.rs`](../../Verus_verification/models/cypher_export/NOTES.md) `theorem_ordinary_and_null_rows`; as-built departures `theorem_falsy_value_depends_on_names`, `theorem_failed_query_looks_empty`.
- agent
- user-facing-behavior

Recovered in iteration 45 from the semantic-layer guide and observation ([W51](../../uplift/consolidated/iteration-45/cyphexport-PAIRS.md); prefix declarations re-checked with data in the namespace, [observation 2](../../uplift/consolidated/iteration-45/cyphexport-observed2-20261117T011146Z.json)).

Findings: [export_rdf_from_cypher reports 0 triples when its query fails](../../Verus_verification/bugs_issues.md#bug-plt-111); [export_rdf_from_cypher drops a row whose value is 0 unless the columns are named](../../Verus_verification/bugs_issues.md#bug-plt-112)

### install.shacl

- Sources: [SEMANTIC_LAYER.md SHACL validation](../../../docs/SEMANTIC_LAYER.md#L156-L215); [API_REFERENCE validate_shacl](../../../docs/API_REFERENCE.md); [`ShaclMixin.validate_shacl`](../../../iris_vector_graph/_engine/shacl.py#L203-L241), [`_build_rdflib_graph`](../../../iris_vector_graph/_engine/_rdf_utils.py#L102)
- Verus: active: [`shacl_data.rs`](../../Verus_verification/models/shacl_data/NOTES.md) `theorem_single_graph_min_agrees`, `theorem_single_graph_class_agrees`; as-built departures `theorem_other_graph_masks_missing_property`, `theorem_focus_only_breaks_class`.
- agent
- data-integrity, user-facing-behavior

Recovered in iteration 39 from the semantic-layer guide and observation ([W45](../../uplift/consolidated/iteration-39/shacl-PAIRS.md)); no owner statement existed. Provider: pySHACL 0.40.2 with rdflib 7.6.0. Other Core constraints, URL-fetched shapes and SHACL-AF were not exercised.

Findings: [SHACL validation treats one node ID in two graphs as one node](../../Verus_verification/bugs_issues.md#bug-str-107); [Validating only new node IDs refuses valid data whose shape checks an edge's target](../../Verus_verification/bugs_issues.md#bug-str-108)
