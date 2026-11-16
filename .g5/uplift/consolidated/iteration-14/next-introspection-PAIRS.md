# Ordinary introspection survey before selected method bodies

Source-informed only by public API docs and current public census; not a private/blind draw. This is future-work preparation, not iteration14proof/model credit. Current before complement has get_schema_visualization, get_property_keys, get_labels, get_relationship_types, get_nodes_by_label, list_graphs unbound. Existing routine_reporting owns raw census but not diagram contents or label-selected hydrated records. No interrupted lane or related inputs/outcomes selected.

Primary public sources read: API_REFERENCE197–249,640–647,684–691; USER_GUIDE388–408. Signatures/member names only read before this panel. Public test names selected but selected implementation bodies not yet opened.

I1. Distinct labels/predicates across default and named graphs appear once, sorted, rather than physical row multiplicity. Empty rows produce empty lists. API explicitly promises all-graph label and predicate views.
I2. Property keys with label='Person' should derive from subjects carrying that label; same-ID labels/properties in different graphs should not accidentally join unless an explicit all-graph subject policy says so. API does not define that graph correlation. Before source, prediction is partial; preserve ambiguity rather than assume new failure.
I3. get_nodes_by_label has no graph argument, so graph.default predicts default-only hydrated records. A same-ID named label must not select an unlabeled default node, and named-only IDs must not pull default records.
I4. list_graphs lists only nonempty named graphs with edge rows; a named graph containing only nodes does not appear. One graph with two edges appears once; default edge rows do not appear.
I5. get_schema_visualization emits one label node and one relationship per predicate from raw relational contents. Two labels with different properties retain distinct attribute sets; a predicate linking several source/target labels must have a defined summary rather than arbitrary physical endpoints. Exact sampled schema/content and graph scope are unconfirmed before source.
I6. The schema diagram reader may deliberately cap expensive queries; a public test title mentions row caps/connection usability. Record any cap and partial summary semantics explicitly; do not turn a truncated answer into complete database schema.
I7. Full property lists/endpoint labels/relationship counts are actual observable diagram content. Existing scalar status/cardinality and node hydration theorems may reuse parts but cannot supply a whole prepared diagram/result map.
I8. Ordinary local SQL+actualPython output can discriminate selection/joins/dedup/caps/maps. Native SQL order/collation/typed values and stable cross-read view remain providers. No native execution, failure/security reproduction, product repair or new policy decision is authorized by this preparation.

After freezing this panel, inspect narrow primary tests then selected bodies, retain forecasts/misses, and run finite healthy local fixtures if useful. No new ontology/model/family/proof before next iteration's before image.
