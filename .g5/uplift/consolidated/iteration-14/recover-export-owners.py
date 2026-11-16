from pathlib import Path
import hashlib,json,datetime
R=Path.cwd();A=R/'.g5/uplift/consolidated/iteration-14';P=R/'.g5/ontology/concepts/install.g5.md';s=P.read_text();assert '[D · install.export.ndjson]' not in s
body='''## Ordinary graph exports

<a id="install.export.ndjson"></a>
[D · install.export.ndjson]

`export_graph_ndjson` writes the default graph's node records, then its non-temporal structural edge records, in the format `import_graph_ndjson` reads. Its `nodes` and `edges` answers count lines written; parallel structural edges each have a line.

- A node record uses the public [node-read projection](../features/graph-structure.g5.md#structure.node.read), including its property aliases and value conversions. Its properties omit only the structural `id` and `labels` fields; this does not promise an inverse of stored property keys.
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

The format argument overrides extension inference. N-Quads and TriG preserve graph contexts; flat formats do not establish a context-preserving export, and no successful answer promises file atomicity on an earlier error.

'''
s=s.replace('## Metadata\n',body+'## Metadata\n',1)
meta='''
### install.export.ndjson

- Sources: [User Guide export](../../../docs/USER_GUIDE.md#L1170-L1181), [API reference](../../../docs/API_REFERENCE.md#L2163-L2169), [NDJSON format](../../../docs/setup/DATA_FORMATS.md#3-ndjson), [`SnapshotMixin.export_graph_ndjson`](../../../iris_vector_graph/_engine/snapshot.py#L1857-L1908)
- Tests (live): [R088 default/named/temporal export](../../../tests/e2e/test_460_export_graph_ndjson_e2e.py); existing [import unit tests](../../../tests/unit/test_edgeprop_ndjson.py)
- Related: [node reads](../features/graph-structure.g5.md#structure.node.read), [reserved aliases](../features/graph-structure.g5.md#structure.node.read.aliases), [NDJSON admission](#install.import.ndjson)
- Evidence: [source-first root contrasts](../../uplift/consolidated/iteration-14/root-export-PAIRS.md), [sealed13 full-record survey](../../uplift/consolidated/iteration-13/next-records-survey.md)
- agent
- user-facing-behavior, data-integrity

Recovered ordinary export scope, not a new product requirement. A stable SQL view, actual hydration truthiness, SQL order and ordinary JSON/filesystem laws qualify a complete file claim. Known aliases and value normalization remain as owned; import callback agreement alone is not persistence or inverse proof. Formal content correspondence is pending.

### install.export.rdf.scope

- Sources: [Semantic Layer selection](../../../docs/SEMANTIC_LAYER.md#L95-L115), [API reference](../../../docs/API_REFERENCE.md#L2253-L2274), [`_build_rdflib_graph`](../../../iris_vector_graph/_engine/_rdf_utils.py#L102-L294)
- Tests (live): [R099 label filtering](../../../tests/e2e/test_460_rdf_export_label_filter_e2e.py), [R100 graph contexts](../../../tests/e2e/test_460_rdf_export_nquads_graphs_e2e.py), [graph scope unit tests](../../../tests/unit/test_230_rdf_export_scope.py)
- Related: [graph scope](graph-scope.g5.md#graph.default), [content](#install.export.rdf.content), [report](#install.export.rdf.report)
- Evidence: [source-first root contrasts](../../uplift/consolidated/iteration-14/root-export-PAIRS.md), [sealed13 ordinary RDF survey](../../uplift/consolidated/iteration-13/next-reporting-survey.md)
- agent
- user-facing-behavior, data-integrity

The label projection and own-graph membership are explicit source and regression behavior; no new policy about all labels of selected nodes is inferred. SQL equality, nullable graph normalization and a stable relational view remain correspondence conditions. Formal producer correspondence is pending.

### install.export.rdf.content

- Sources: [Semantic Layer row/term/qualifier rules](../../../docs/SEMANTIC_LAYER.md#L39-L65), [`_mint_iri`, `graph_iri`, `_to_literal`, `_build_rdflib_graph`](../../../iris_vector_graph/_engine/_rdf_utils.py#L29-L294)
- Tests (live): [literal/qualifier unit tests](../../../tests/unit/test_rdf_export.py), [R100 generated context contents](../../../tests/e2e/test_460_rdf_export_nquads_graphs_e2e.py), [R122 named-graph IRIs](../../../tests/e2e/test_460_rdf_graph_id_not_an_iri_e2e.py)
- Evidence: [sealed13 typed literal and actual file observations](../../uplift/consolidated/iteration-13/next-reporting-sanity.json)
- Related: [scope](#install.export.rdf.scope), [report](#install.export.rdf.report)
- agent
- user-facing-behavior, data-integrity

The public literal description does not directly adjudicate the false/zero qualifier exception; as-built support is kept separate from intended-policy approval. The general property-key IRI description is refined to the actual three pass-through prefixes, separately from node/edge FTP handling. Neither observation changes an existing confirmed requirement or claims a new owner decision. Graph-IRI encoding, arbitrary numeric text/IEEE normalization, JSON dictionary decoding, blank-node freshness and rdflib term/codec laws need explicit correspondence frames. Formal producer correspondence is pending.

### install.export.rdf.report

- Sources: [Semantic Layer metrics and formats](../../../docs/SEMANTIC_LAYER.md#L67-L93), [`RdfExportMixin.export_rdf`](../../../iris_vector_graph/_engine/rdf_export.py#L96-L157), [format inference](../../../iris_vector_graph/_engine/_rdf_utils.py#L56-L69)
- Evidence: [sealed13 ordinary union/quad contrast](../../uplift/consolidated/iteration-13/next-reporting-survey.md), [source-first root contrasts](../../uplift/consolidated/iteration-14/root-export-PAIRS.md)
- Related: [content](#install.export.rdf.content)
- agent
- user-facing-behavior, data-integrity

Public docs define triple/subject/IRI-object metrics; source and the ordinary10quad/8union-triple contrast settle their union reader. This clarifies the descriptive phrase "counts what was written" without promising equal serialized quad counts. Registered namespace binding and third-party serialization/parser details, provider failures and cross-read consistency remain qualified; no whole serializer or failed-file atomicity proof is inferred. Formal composition is pending.
'''
s+=meta;P.write_text(s)
p=R/'.g5/ontology/root.g5.md';t=p.read_text();old='Other read APIs (`count_nodes`, `list_graphs`, `get_nodes_by_label`) and exports (`export_graph_ndjson`, `export_rdf`, `prov_export`) still lack a detailed owning block; their graph scope follows [graph scope](concepts/graph-scope.g5.md).';new='Ordinary [NDJSON export](concepts/install.g5.md#install.export.ndjson) and [RDF export](concepts/install.g5.md#install.export.rdf.scope) now have detailed owners. Other read APIs (`count_nodes`, `list_graphs`, `get_nodes_by_label`) and `prov_export` still lack a detailed owning block; their graph scope follows [graph scope](concepts/graph-scope.g5.md).';assert old in t;p.write_text(t.replace(old,new))
p=R/'.g5/Verus_verification/crosswalk/statements.tsv';t=p.read_text();ids=['install.export.ndjson','install.export.rdf.scope','install.export.rdf.content','install.export.rdf.report'];assert all(x not in t for x in ids)
for x in ids:t+=f'{x}\t\tg-only\tordinary14-{x}\t.g5/ontology/concepts/install.g5.md\tnew ordinary14\n'
p.write_text(t)
sources=['docs/SEMANTIC_LAYER.md','docs/USER_GUIDE.md','docs/API_REFERENCE.md','docs/setup/DATA_FORMATS.md','iris_vector_graph/_engine/_rdf_utils.py','iris_vector_graph/_engine/rdf_export.py','iris_vector_graph/_engine/snapshot.py','tests/e2e/test_460_export_graph_ndjson_e2e.py','tests/e2e/test_460_rdf_export_nquads_graphs_e2e.py','tests/e2e/test_460_rdf_export_label_filter_e2e.py','tests/unit/test_rdf_export.py','tests/unit/test_230_rdf_export_scope.py']
(A/'root-owner-recovery.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),owners=ids,product_pin='3eaa79cf77d3e0a879b2cced634cf2729d81499e',inputs={x:hashlib.sha256((R/x).read_bytes()).hexdigest() for x in sources},new_policy_decisions=0,product_repairs=0,formal_status='pending; owners ready before new proof',uncertainties=['intended false/zero qualifier exception not adjudicated','doc property IRI broadness versus actual three-prefix projection; as-built scope explicit']),indent=2)+'\n')
print('Recovered four ordinary owners before proof')
