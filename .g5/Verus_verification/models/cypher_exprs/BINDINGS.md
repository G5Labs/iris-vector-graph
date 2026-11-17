# cypher exprs

Cypher expressions over run-time values: a negative run-time slice bound counts as 0; a run-time boolean cannot be a CASE WHEN or WHERE condition; a node CREATE refuses unfolded function values and a relationship CREATE between new nodes drops computed and parameter values; a simple CASE over a property or row value coerces across types; a null list slices to []; coalesce keeps a type only beside a node property; an identifier slice lower bound does not parse; a negative substring start answers a prefix; Prop_Set retypes a same-text SET, switched by the engine's dictionary check (unreadable counts as deployed)

Evidence status: active. Variant: as-built bounded transcription.

Verified and errors count obligations reported by the verifier. A control is judged against its named expected failure. Native observations have their recorded scope.

[Formal source](cypher_exprs.rs)

[Formal claims, product bindings and limitations](NOTES.md)

[Premises](NOTES.md)

[Product and declaration crosswalk](../../crosswalk/decision-links.tsv)
