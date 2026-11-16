# Ordinary export reporting: bounded source survey

This is a new source-first survey from sealed12/fresh13, with no model/family/proof and no convergence claim. All interrupted/quarantined work remains unpursued/unassessed. The source-first panel `next-reporting-PAIRS.md` SHAe80f0a06a73f65df8768264dc245c9832f0bcb0094b303ae745bdfda6c6e61c0 was frozen before selected export bodies. Only healthy ordinary ASCII IDs/keys/values and local in-memory SQL/file output were used. Frozen routine_reporting V2 and all existing packages/results remain untouched.

## Strongest remaining workflow

Select **raw relational rows → scoped RDF quad/triple construction → qualifier reification → serialized RDF file → returned summary counts** for a future authorized iteration. Ontology root explicitly leaves export_rdf/export_graph_ndjson/prov_export without detailed owning commitments. Current graph-scope owns isolation and default-vs-all meaning; primary SEMANTIC_LAYER39–148 and API_REFERENCE2253–2284 provide richer observable content/count semantics. Before a model, root should recover an ordinary export owner and retain any policy ambiguity below. No new owner text is edited here.

This is more than a wrapper: every label/property/edge row generates different term shapes, qualified physical rows allocate two fresh blank nodes, set insertion removes some repeated triples, graph contexts affect serialized quads while the final report reads the union, and property/qualifier literal paths can differ. The raw input cannot be replaced by a supplied triple map, per-format count, decoded literal-type flag or prepared graph/filter result.

The smaller alternative is default-graph NDJSON row selection → actual get_node hydration/alias projection → node and edge lines/counts. It is still underserved, but it overlaps node_read more and requires a broader IRIS-specific hydration provider to bind the full reader. The RDF SELECTs already execute unchanged in SQLite, making the stronger chain tractable without native or provider fiction.

## Actual deciding roles

| Source | Decision and final reader |
|---|---|
| _rdf_utils.py:102–294 `_build_rdflib_graph` | Three real SQL scans; None all graphs, empty default incl NULL, named equality; node IDs select subjects; label membership correlates both subject and graph for properties/edges. |
| same:166–209 local filter builders | Empty lists are unfiltered. Labels themselves are narrowed to matching labels; the property/edge membership condition uses EXISTS in that row's own graph. |
| same:210–238 label/property loops | Labels become rdf:type, properties become typed literal triples, None property literal omitted. Target context derives from each row's graph. No physical nodes scan. |
| same:240–291 edge loop | Each selected row adds base SPO. Each nonempty qualifier dict allocates fresh statement/reifier nodes, adds four envelope triples, and adds every qualifier except inferred. Inferred-only therefore still adds the envelope. |
| same:72–99 `_to_literal` | Integer only if int text canonicalizes identically; otherwise float attempt, then case-folded true/false, then plain literal. `007` is decimal7.0 here, not integer7. |
| rdf_export.py:96–157 `export_rdf` | Builds graph, binds namespaces, serializes, then derives triples=len(union), nodes=distinct union subjects, edges=union triples with URI object and predicate!=rdf:type. These are not physical row counts. |
| same:159–209 /212–258 | Separate query-result projection: exact s/p/o names win, otherwise first three columns; short rows only already-IRI string values become Node type. Not needed in the primary model. |
| snapshot.py:1857–1908 `export_graph_ndjson` | Default rows by graph_id='', actual get_node view, then physical edge rows excluding marked temporal rows; omits empty qualifiers; counts lines actually emitted. |
| nodes_edges.py:563–585 `get_node` | Delegates existing batched reader; stored structural-name properties are displayed under p_id/p_labels aliases. NDJSON exports that displayed map as its properties, so an inverse raw-key identity is not inferred. |

Line ranges describe the current pin, not whole-member verification. Exact selected current/export source SHA256 and the public pin are recorded in `next-reporting-sanity.json`; the four selected files match. No spec198 body was found/read, so no claim relies on it.

## Frozen neighboring outcomes and retained exposure

EX1: RDF scoping is correct across all three row tables; actual local source confirms None/all, ''/default and named. NDJSON source uses exact graph_id='' rather than COALESCE; ordinary current rows fit it. Legacy NULL NDJSON reach/correction is not tested or adjudicated.

EX2: RDF never scans nodes; an unlabeled/propertyless isolated physical node contributes no triple or subject count. NDJSON promises per-node lines, but only writes a selected node whose actual hydration is truthy. Do not equate its counters with RDF's nodes or with status's table census.

EX3/4: Unqualified parallel rows with equal SPO/context collapse; two graph contexts retain two quads but one union triple. The all-graph local fixture has10 parsed quads, returns8 triples; source-filter fixture7 quads returns5. This is an as-built count distinction, not an automatically filed defect. The guide says the answer counts what was written, then describes triple/subject metrics; root should state union-versus-quad reporting precisely before giving intent credit. No whole RDF format/serializer theorem is proposed.

EX5: Actual helper gives '7' integer7; '007' decimal7.0; '1.25' decimal1.25; true/false booleans; hello/empty text plain. These are lexical export semantics, not the stored type-preserving node_read law. Arbitrary native numeric formatting, NaN/Infinity, Unicode and float-rounding refinements are outside this healthy fragment and not investigated.

EX6/10: Inferred-only nonempty qualifier dict still creates the four-triple envelope. A qualifier value is `_to_literal(str(qv)) or Literal(str(qv))`; rdflib false/zero literals are falsey, so the final ordinary zero/false qualifiers are untyped strings while the property helper returns typed zero/false. This source-informed contrast is retained as a missing prediction to model, with no issue/intent adjudication. All qualifier reification increases summary subject/URI-object edge counts; these are not just IVG endpoint counts.

EX7/8/9: Empty node_ids/label_filter collections are unfiltered; outgoing source selection is used. Only matching label triples are written under label_filter, while matching source properties/edges are retained. The own-graph EXISTS condition correctly excludes a same-ID label from a different graph. My before-body question about cross-graph membership is resolved by the actual source; no miss/bug is invented. Whether users expect all labels of selected nodes versus only matching labels is not settled by a new inferred policy.

EX11: Query projection is a separate real data transformation, but lower priority than raw relational export; column aliases/falsey values and ordinary query-result errors need their own input/reader frame. Do not award its body from generic parser/result-admission proofs.

EX12: Missing rdflib raises at the public export entry. Local SQL/file/serializer failure propagation remains source-inspected, not a new ordinary failure harness or a filesystem atomicity theorem. Namespace binding errors alone are swallowed; namespace-list read failures can still stop before serialization. Current source stages matter if a later failure is modeled.

## Existing meaningful hits and gaps

- `node_read` derives writer storage, CY_TYPED tags, actual reader type/aliases and scalar finishing. It does not build RDF terms/contexts/reifiers or export record properties; JSON/container and native numeric refinements are explicit limits.
- `ndjson_import` derives line admission/node writes/counters and cross-call reads. It explicitly projects edge/temporal records outside its node theorem. It does not establish an arbitrary export/import inverse or physical-edge export multiplicity.
- `ledger_content` proves rich record fold, named reconstruction and typed entity/stream/export projection. Its producer is revision records and final exporter is ledger reconstruction, not relational SnapshotMixin.export_graph_ndjson or RDF. Retain the strong prior hit without using the shared word export to claim this different chain.
- `routine_reporting` closes SQL census/registry/report knowledge, not row content selection or RDF summary semantics. `graph.default`, `graph.membership` and multigraph.count supply intent for graph/row distinctions, not RDF set/reifier correctness.
- Existing public RDF memory finding was encountered by narrow export-name search but not investigated; it is not this plan's root or evidence. No new issue/policy answer/dedup claim is made for the ordinary literal/count observations. A first narrow search used nonexistent questions/simplification filenames; no private/evaluator search followed.

## Local feasibility and costs

`next-reporting-sanity.py` executes pinned actual `_build_rdflib_graph` through public `export_rdf`, original SQL over SQLite, actual rdflib serialize and parse. Seven scoped/filter/reification worlds match an independent raw-row set oracle for returned triple/subject/URI-object counts and parsed quad counts. A separate seven-value literal observation and false/zero qualifier file retain the final datatype contrast. No supplied SQL count/graph result is returned by the provider.0 socket/native/Git calls; one command attempt,0failed execution attempts. Exact script/panel/selected source snapshots, raw log/command/result/cost precede the attempt in `next-reporting-attempts`. Subprocess0.320s; source panel itself0.0124s; reading/planning time unmeasured, no invented token cost.

This is feasibility/source preparation, not a new proof, family, formal coverage credit, issue adjudication, independent grade or convergence result.
